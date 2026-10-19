"""Offline defect characterization; passing checks confirm defects, not readiness.
Run from repository root with installed requests, uvicorn, starlette and httpx:
  python -m unittest discover -s review -p reproduce_findings.py -v
No external services or real credentials are used.
"""
import json
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from starlette.testclient import TestClient
import app


class Findings(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)

    def test_connected_label_without_service_check(self):
        with patch.object(app.requests, 'post', side_effect=AssertionError('unexpected network')):
            response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Sourcegraph Live API Connected', response.text)

    def test_mapping_silently_empty_on_linux(self):
        self.assertTrue(Path('url_mapping.json').is_file())
        self.assertEqual(app.URL_MAP, {})

    def test_pr_and_r_fetch_identical_sources_and_hide_ai_failure(self):
        calls = []
        def get(url, **kwargs):
            calls.append(url)
            payload = [{'new_path': 'view.jsp', 'diff': '-old\n+new'}] if url.endswith('/diff') else {'title': 'sample'}
            return Mock(status_code=200, json=lambda: payload)
        with patch.object(app.requests, 'get', side_effect=get), patch.object(app.requests, 'post', side_effect=AssertionError('unexpected network')), patch.object(app.subprocess, 'run', side_effect=FileNotFoundError('simulated missing Pi')):
            pr = self.client.post('/api/analyze-commit', json={'commit_sha': 'abc123', 'base_branch': 'PR'}).json()
            rr = self.client.post('/api/analyze-commit', json={'commit_sha': 'abc123', 'base_branch': 'R'}).json()
        self.assertEqual(calls[:2], calls[2:])
        self.assertEqual(pr['status'], 'success')
        self.assertEqual(rr['status'], 'success')
        self.assertEqual(pr['data']['side_effects'], rr['data']['side_effects'])
        self.assertNotIn('engine', pr['data'])

    def test_comment_only_java_change_produces_high_500_risk(self):
        with patch.object(app, 'get_mapped_screen_deep', return_value=''):
            r = app.analyze_fact_based_diff_engine('comment', '', [{'path': 'Example.java', 'diff_preview': '-// old comment\n+// new comment'}])
        self.assertEqual(r['risk_level'], 'HIGH')
        self.assertIn('500', r['side_effects'][0]['symptom'])

    def test_first_match_loses_second_screen_and_revision(self):
        calls = []
        def post(url, **kwargs):
            calls.append(kwargs['json']['query'])
            return Mock(status_code=200, json=lambda: {'data': {'search': {'results': {'results': [{'file': {'path': 'A.java'}}, {'file': {'path': 'B.java'}}]}}}})
        with patch.object(app, 'URL_MAP', {'A.java': {'screen_name': '화면 A'}, 'B.java': {'screen_name': '화면 B'}}), patch.object(app.requests, 'post', side_effect=post):
            r = app.query_sourcegraph_api('chosen_sha_123', [{'path': 'Example.java'}])
        self.assertIn('화면 A', r)
        self.assertNotIn('화면 B', r)
        self.assertNotIn('chosen_sha_123', ''.join(calls))

    def test_twenty_file_cap(self):
        diffs = [{'new_path': f'view{i}.jsp', 'diff': '+' + 'a' * 2000} for i in range(25)]
        def get(url, **kwargs):
            return Mock(status_code=200, json=lambda: diffs if url.endswith('/diff') else {'title': 'large change'})
        with patch.object(app.requests, 'get', side_effect=get), patch.object(app, 'query_sourcegraph_api', return_value=''), patch.object(app, 'analyze_with_pi_cli', return_value={}):
            r = self.client.post('/api/analyze-commit', json={'commit_sha': 'abc123'}).json()['data']
        self.assertEqual(r['changes_count'], 25)
        self.assertEqual(len(r['files']), 20)
        self.assertIn('[중략]', r['files'][0]['diff_preview'])

    def test_mapping_contains_generic_names(self):
        mappings = json.loads(Path('url_mapping.json').read_text())
        self.assertEqual(len(mappings), 97)
        self.assertEqual(sum(v.get('screen_name', '').startswith('API 컨트롤러') for v in mappings.values()), 57)


if __name__ == '__main__':
    unittest.main()
