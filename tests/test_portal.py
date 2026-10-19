import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from starlette.testclient import TestClient
from portal.config import Config, SetupError, ROOT
from portal.repository import Repository
from portal.trace import Trace, routes_in
from portal.pi import Pi, parse_output, validate_analysis
from portal.services import Sourcegraph, GitLab
from portal.analysis import Analyzer
from portal import app as web


def make_config(root, **overrides):
    data = json.loads((ROOT / 'config.example.json').read_text())
    data.update(data_directory=str(root / 'data'), screen_catalog=str(root / 'screens.json'))
    data.update(overrides)
    path = root / 'config.json'; path.write_text(json.dumps(data))
    return Config(path)


def command(root, *args):
    p = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
    if p.returncode:
        raise AssertionError(p.stderr)
    return p.stdout.strip()


class GitFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.work = self.root / 'repo'; self.work.mkdir()
        command(self.work, 'init', '-b', 'master')
        command(self.work, 'config', 'user.name', 'Fixture')
        command(self.work, 'config', 'user.email', 'fixture@example.invalid')
        self.files = {
            'src/PolicyService.java': 'class PolicyService {\n public int limit() {\n  return 10;\n }\n}\n',
            'src/PolicyController.java': 'class PolicyController {\n PolicyService service;\n @GetMapping("/policy.sms")\n public String index() { return "policy"; }\n}\n',
            'web/policy.jsp': '<title>정책 관리</title>\n<button onclick="savePolicy()">저장</button>\n',
            'web/other.jsp': '<title>무관한 화면</title>\n',
        }
        for path, text in self.files.items():
            p = self.work / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
        command(self.work, 'add', '.'); command(self.work, 'commit', '-m', 'base')
        self.base = command(self.work, 'rev-parse', 'HEAD')
        command(self.work, 'checkout', '-b', 'development')
        (self.work / 'src/PolicyService.java').write_text(self.files['src/PolicyService.java'].replace('return 10', 'return 20'))
        command(self.work, 'commit', '-am', 'change limit')
        self.dev = command(self.work, 'rev-parse', 'HEAD')
        command(self.work, 'checkout', '-b', '2025_ES5_Release_버전_분기', self.base)
        (self.work / 'src/PolicyController.java').write_text(self.files['src/PolicyController.java'].replace('"policy"', '"releasePolicy"'))
        (self.work / 'web/policy.jsp').unlink()
        (self.work / 'web/releasePolicy.jsp').write_text('<title>릴리스 정책 관리</title>\n')
        command(self.work, 'add', '.'); command(self.work, 'commit', '-m', 'release view')
        self.release = command(self.work, 'rev-parse', 'HEAD')
        self.config = make_config(self.root)
        self.repo = Repository(self.config, self.work / '.git')

    def tearDown(self):
        self.tmp.cleanup()

    def test_patch_applied_without_touching_working_tree_or_heads(self):
        r = self.repo.simulate(self.base, [self.dev])
        self.assertEqual(r['status'], 'applied')
        after, omitted = self.repo.snapshot(r['tree'])
        self.assertIn('return 20', after['src/PolicyService.java'])
        self.assertEqual(omitted, [])
        self.assertEqual(command(self.work, 'status', '--porcelain'), '')
        self.assertEqual(command(self.work, 'rev-parse', 'master'), self.base)
        self.assertEqual(command(self.work, 'rev-parse', 'HEAD'), self.release)

    def test_already_present_is_no_change(self):
        r = self.repo.simulate(self.dev, [self.dev])
        self.assertEqual(r['status'], 'no_change')
        self.assertEqual(r['commits'][0]['status'], 'already_in_history')

    def test_conflict_does_not_claim_analysis(self):
        (self.work / 'src/PolicyService.java').write_text(self.files['src/PolicyService.java'].replace('return 10', 'return 30'))
        command(self.work, 'commit', '-am', 'conflicting target')
        target = command(self.work, 'rev-parse', 'HEAD')
        r = self.repo.simulate(target, [self.dev])
        self.assertEqual(r['status'], 'conflict')
        self.assertNotIn('tree', r)
        self.assertEqual(command(self.work, 'status', '--porcelain'), '')

    def test_nonancestor_patch_already_present(self):
        (self.work / 'src/PolicyService.java').write_text(self.files['src/PolicyService.java'].replace('return 10', 'return 20'))
        command(self.work, 'commit', '-am', 'same patch different commit')
        target = command(self.work, 'rev-parse', 'HEAD')
        r = self.repo.simulate(target, [self.dev])
        self.assertEqual(r['status'], 'no_change')

    def test_missing_source_commit_rejected(self):
        with self.assertRaises(SetupError):
            self.repo.ordered_commits(self.dev, [self.release])

    def test_target_specific_screen_and_ai_failure_visible(self):
        refs = {'development': self.dev, 'master': self.base, '2025_ES5_Release_버전_분기': self.release}
        sg = Mock(); sg.search.return_value = {'status': 'error', 'paths': [], 'warning': 'offline fixture'}
        pi = Mock(); pi.analyze.side_effect = SetupError('offline Pi failure')
        with patch.object(self.repo, 'prepare', return_value=refs):
            report = Analyzer(self.config, self.repo, pi, sg).run('development', [self.dev], ['PR', 'R'])
        self.assertEqual(report['targets'][0]['screens'][0]['screen']['name'], '정책 관리')
        self.assertEqual(report['targets'][1]['screens'][0]['screen']['name'], '릴리스 정책 관리')
        for result in report['targets']:
            self.assertEqual(result['screens'][0]['ai_status'], 'error')
            self.assertNotIn('analysis', result['screens'][0])
            self.assertEqual(result['screens'][0]['screen']['menu_path'], '')
        self.assertEqual(sg.search.call_args_list[0].args[0], self.base)
        self.assertEqual(sg.search.call_args_list[1].args[0], self.release)

    def test_end_to_end_evidence_bound_result(self):
        pi = Mock()
        def analyze(payload):
            self.assertIn('return 20', payload['target_changes']['src/PolicyService.java'])
            self.assertEqual(payload['target']['sha'], self.base)
            return validate_analysis({'screen_id': payload['screen']['id'], 'risks': [], 'uncertainties': ['테스트 입력: 실제 업무 조건 미확인']}, payload['screen']['id'], {x['id'] for x in payload['evidence']})
        pi.analyze.side_effect = analyze
        sg = Mock(); sg.search.return_value = {'status': 'ok', 'paths': ['src/PolicyController.java'], 'warning': ''}
        with patch.object(self.repo, 'prepare', return_value={'development': self.dev, 'master': self.base}):
            report = Analyzer(self.config, self.repo, pi, sg).run('development', [self.dev], ['PR'])
        self.assertEqual(report['targets'][0]['screens'][0]['ai_status'], 'complete')
        self.assertEqual(report['targets'][0]['screens'][0]['analysis']['risks'], [])

    def test_snapshot_limits_report_omission(self):
        self.config.values['max_file_bytes'] = 10
        files, omitted = self.repo.snapshot(self.base)
        self.assertEqual(files, {})
        self.assertEqual(len(omitted), 4)

    def test_real_fetch_from_fixture_remote(self):
        dest = self.root / 'cache.git'
        command(self.work, 'init', '--bare', str(dest))
        subprocess.run(['git', '--git-dir', str(dest), 'remote', 'add', 'origin', str(self.work)], check=True, capture_output=True)
        repo = Repository(self.config, dest)
        refs = repo.prepare(['master', '2025_ES5_Release_버전_분기'])
        self.assertEqual(refs['master'], self.base)
        self.assertEqual(refs['2025_ES5_Release_버전_분기'], self.release)


class TraceTests(unittest.TestCase):
    def test_all_screens_not_first_only(self):
        files = {'Service.java': 'class Service {}', 'One.java': 'class One { Service service; String f(){return "one";} }', 'Two.java': 'class Two { Service service; String f(){return "two";} }', 'web/one.jsp': '<title>첫 화면</title>', 'web/two.jsp': '<title>둘째 화면</title>'}
        found, unresolved, _ = Trace(files, 'a'*40, [], 'master').trace(['Service.java'])
        self.assertEqual({x['screen']['name'] for x in found}, {'첫 화면', '둘째 화면'})
        self.assertEqual(unresolved, [])

    def test_i18n_screen_title_comes_from_resource(self):
        files = {'one.jsp': '<title><spring:message code="policy.title"/></title>', 'messages_ko.properties': 'policy.title=정책 관리', 'messages_en.properties': 'policy.title=Policy management'}
        found, _, _ = Trace(files, 'a'*40, [], 'master').trace(['one.jsp'])
        self.assertEqual(found[0]['screen']['name'], '정책 관리')

    def test_dynamic_title_not_invented(self):
        found, unresolved, _ = Trace({'x.jsp': '<title>${message}</title>'}, 'a'*40, [], 'master').trace(['x.jsp'])
        self.assertEqual(found, [])
        self.assertEqual(unresolved, ['x.jsp'])

    def test_catalog_requires_matching_version_and_file(self):
        catalog = [{'id': 'one', 'name': '정책', 'menu_path': '관리 > 정책', 'view_paths': ['one.jsp'], 'verified_refs': ['master']}]
        pr = Trace({'one.jsp': 'body'}, 'a'*40, catalog, 'master').trace(['one.jsp'])[0][0]
        rr = Trace({'one.jsp': 'body'}, 'a'*40, catalog, 'release').trace(['one.jsp'])[0][0]
        self.assertTrue(pr['screen']['menu_verified'])
        self.assertFalse(rr['screen']['menu_verified'])

    def test_route_prefix_and_ajax_path(self):
        java = '@RequestMapping("/policy")\nclass C {\n@GetMapping(value="/list.sms", produces="application/json")\nString f() {}\n}'
        self.assertEqual(routes_in(java), [('/policy/list.sms', 3)])
        files = {'C.java': java, 'web/page.jsp': '<title>목록</title><script>fetch("/policy/list.sms")</script>'}
        found, _, _ = Trace(files, 'a'*40, [], 'master').trace(['C.java'])
        self.assertEqual(found[0]['screen']['name'], '목록')

    def test_comment_class_names_do_not_link(self):
        files = {'S.java': 'class S {}', 'C.java': 'class C { /* S service; */ String f(){return "one";} }', 'web/one.jsp': '<title>One</title>'}
        found, _, _ = Trace(files, 'a'*40, [], 'master').trace(['S.java'])
        self.assertEqual(found, [])


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.config = make_config(self.root)
    def tearDown(self):
        self.tmp.cleanup()

    def test_sourcegraph_pins_revision_and_excludes_other_commit(self):
        sha = 'a'*40
        matches = [{'repository': self.config['sourcegraph_repository'], 'commit': sha, 'path': 'one.java'}, {'repository': self.config['sourcegraph_repository'], 'commit': 'b'*40, 'path': 'wrong.java'}]
        text = 'event: matches\ndata: '+json.dumps(matches)+'\n\nevent: progress\ndata: {"done": true}\n\n'
        with patch('portal.services.requests.get', return_value=Mock(status_code=200, text=text)) as get:
            r = Sourcegraph(self.config).search(sha, 'Service')
        self.assertEqual(r['paths'], ['one.java'])
        self.assertIn('@'+sha, get.call_args.kwargs['params']['q'])
        self.assertTrue(get.call_args.kwargs['verify'])
        self.assertEqual(r['status'], 'partial')

    def test_sourcegraph_html_is_not_connected(self):
        with patch('portal.services.requests.get', return_value=Mock(status_code=200, text='<html>login</html>')):
            r = Sourcegraph(self.config).search('a'*40, 'Service')
        self.assertEqual(r['status'], 'partial')
        self.assertIn('완료', r['warning'])

    def test_gitlab_branch_pagination(self):
        gl = GitLab(self.config)
        with patch.object(gl, 'get', side_effect=[([{'name': 'a', 'commit': {'id': 'a'*40}}], '2'), ([{'name': 'b', 'commit': {'id': 'b'*40}}], '')]):
            self.assertEqual(len(gl.branches()), 2)

    def test_real_pi_subprocess_protocol_using_fake_cli(self):
        script = self.root / 'fake_pi.py'
        script.write_text('''import sys,json,pathlib,os
assert '--no-tools' in sys.argv and '--no-session' in sys.argv
assert 'GITLAB_TOKEN' not in os.environ
p=next(x[1:] for x in sys.argv if x.startswith('@'))
data=json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
answer={'screen_id':data['screen']['id'],'risks':[],'uncertainties':[]}
print(json.dumps({'type':'message_end','message':{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':json.dumps(answer)}]}}))
''')
        self.config.values['pi_command'] = [sys.executable, str(script)]
        pi_config = self.root / 'pi-config'; pi_config.mkdir()
        (pi_config / 'models.json').write_text(json.dumps({'providers': {'google': {'baseUrl': self.config['pi_expected_base_url'], 'api': 'google-generative-ai'}}}))
        self.config.values['pi_config_directory'] = str(pi_config)
        with patch.dict(os.environ, {'GITLAB_TOKEN': 'test-value-not-real'}):
            result = Pi(self.config).analyze({'screen': {'id': 'screen-one'}, 'evidence': []})
        self.assertEqual(result['risks'], [])
        self.assertFalse(list(self.config.path_for('data_directory').glob('pi-*')))

    def test_pi_rejects_wrong_provider_endpoint(self):
        folder = self.root / 'pi-config'; folder.mkdir()
        (folder / 'models.json').write_text(json.dumps({'providers': {'google': {'baseUrl': 'https://unexpected.example', 'api': 'google-generative-ai'}}}))
        self.config.values['pi_config_directory'] = str(folder)
        with self.assertRaisesRegex(SetupError, '사내 Gemini'):
            Pi(self.config).provider_config()

    def test_pi_rejects_fabricated_evidence(self):
        risk = {'feature': 'f', 'condition': 'c', 'symptom': 's', 'reason': 'r', 'steps': ['a'], 'expected_result': 'e', 'evidence_ids': ['fake']}
        with self.assertRaises(SetupError):
            validate_analysis({'screen_id': 'one', 'risks': [risk], 'uncertainties': []}, 'one', {'actual'})

    def test_pi_rejects_error_and_wrong_schema(self):
        with self.assertRaises(SetupError):
            parse_output('{"type":"message_end","message":{"role":"assistant","stopReason":"error","content":[]}}')
        with self.assertRaises(SetupError):
            parse_output('not json')
        with self.assertRaises(SetupError):
            validate_analysis({'screen_id': 'invented', 'risks': [], 'uncertainties': []}, 'actual', set())

    def test_pi_does_not_silently_truncate(self):
        self.config.values['max_prompt_chars'] = 10
        with self.assertRaisesRegex(SetupError, '한도'):
            Pi(self.config).invoke({'long': 'a'*100})

    def test_connection_checks_have_independent_timeouts(self):
        seen = {}
        def fake_check(pi):
            seen['timeout'] = pi.config['pi_timeout_seconds']
            return {'status': 'ok', 'message': 'fixture'}
        with patch.object(Pi, 'check', fake_check):
            result = web.connection_check(self.config, 'pi')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(seen['timeout'], 60)
        self.assertEqual(self.config['pi_timeout_seconds'], 180)
        with patch.object(GitLab, 'get', side_effect=SetupError('fixture GitLab unavailable')):
            result = web.connection_check(self.config, 'sourcegraph')
        self.assertEqual(result['status'], 'not_run')
        self.assertIn('대상 SHA', result['message'])

    def test_slow_pi_does_not_hide_gitlab_result(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        started, release = threading.Event(), threading.Event()
        def slow_check(pi):
            started.set()
            if not release.wait(5):
                raise AssertionError('GitLab check was blocked behind Pi')
            return {'status': 'ok', 'message': 'Pi fixture'}
        with patch.object(web, 'config', return_value=self.config), patch.object(Pi, 'check', slow_check), patch.object(GitLab, 'get', return_value=({'name': 'fixture project'}, '')):
            with TestClient(web.app) as client, ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(client.post, '/api/checks/pi', json={})
                try:
                    self.assertTrue(started.wait(2))
                    result = client.post('/api/checks/gitlab', json={})
                    self.assertEqual(result.json()['status'], 'ok')
                    self.assertFalse(future.done())
                finally:
                    release.set()
                self.assertEqual(future.result(timeout=2).json()['status'], 'ok')

    def test_portal_http_and_manual_record(self):
        with patch.object(web, 'config', return_value=self.config):
            client = TestClient(web.app)
            self.assertEqual(client.get('/').status_code, 200)
            self.assertNotIn('Live API Connected', client.get('/').text)
            self.assertEqual(client.get('/api/settings').json()['targets']['PR'], 'master')
            self.assertEqual(client.post('/api/analyze', json={}, headers={'Origin': 'http://untrusted.example'}).status_code, 403)
            self.assertEqual(client.post('/api/analyze', json={}).status_code, 400)
            job_id = 'a'*32
            data = {'id': job_id, 'created_at': '2026-01-01', 'source_branch': 'dev', 'targets': [{'label': 'PR', 'screens': [{'screen': {'id': 'one'}}]}], 'manual_checks': {}}
            web.save_report(self.config, job_id, data)
            result = client.post('/api/reports/'+job_id+'/check', json={'key': 'PR:one', 'status': 'pass', 'note': 'checked', 'deployed_sha': 'b'*40})
            self.assertEqual(result.status_code, 200)
            saved = client.get('/api/reports/'+job_id).json()
            self.assertEqual(saved['manual_checks']['PR:one']['status'], 'pass')
            self.assertFalse(saved['manual_checks']['PR:one']['deployment_verified'])
            self.assertEqual(client.get('/api/reports').json()['items'][0]['id'], job_id)


if __name__ == '__main__':
    unittest.main()
