import json
import re
from datetime import datetime, timezone
from .config import SetupError
from .repository import Repository
from .services import Sourcegraph
from .trace import Trace, declarations, load_catalog
from .pi import Pi


def excerpt(files, path, line, radius=18):
    lines = files.get(path, '').splitlines()
    start, end = max(0, line - 1 - radius), min(len(lines), line + radius)
    return {'path': path, 'start_line': start + 1, 'end_line': end, 'total_lines': len(lines), 'is_excerpt': start > 0 or end < len(lines), 'text': '\n'.join(f'{i + 1}: {lines[i]}' for i in range(start, end))}


class Analyzer:
    def __init__(self, config, repository=None, pi=None, sourcegraph=None):
        self.config = config
        self.repo = repository or Repository(config)
        self.pi = pi or Pi(config)
        self.sg = sourcegraph or Sourcegraph(config)

    def run(self, source_branch, selected, targets, progress=lambda s: None):
        if not source_branch or not targets or any(t not in self.config['targets'] for t in targets) or len(set(targets)) != len(targets):
            raise SetupError('개발 브랜치와 유효한 반영 대상을 선택하세요.')
        progress('최신 개발/대상 브랜치를 가져오는 중입니다. 첫 실행은 저장소 크기에 따라 오래 걸릴 수 있습니다.')
        branches = [self.config['targets'][t] for t in targets]
        refs = self.repo.prepare([source_branch, *branches])
        ordered = self.repo.ordered_commits(refs[source_branch], selected)
        catalog, warnings = load_catalog(self.config)
        report = {'created_at': datetime.now(timezone.utc).isoformat(), 'source_branch': source_branch, 'source_sha': refs[source_branch], 'selected_commits': ordered, 'application_mode': '선택 커밋의 변경을 대상에 순서대로 적용하는 3-way 패치 시뮬레이션', 'assumption': '실제 반영 절차는 미확인입니다. 브랜치 전체 merge 또는 개발자의 수동 수정 결과와 다를 수 있습니다. 원격 저장소에 변경하지 않습니다.', 'warnings': warnings, 'targets': []}
        for target in targets:
            branch, sha = self.config['targets'][target], refs[self.config['targets'][target]]
            progress(f'{target}: 선택 변경을 {branch}에 적용해 보는 중입니다.')
            result = self.repo.simulate(sha, ordered)
            result.update({'label': target, 'branch': branch, 'warnings': [], 'screens': [], 'unresolved_files': []})
            report['targets'].append(result)
            if result['status'] != 'applied':
                continue
            progress(f'{target}: 변경 전후 코드에서 화면 후보와 참조 경로를 찾고 있습니다.')
            before, omitted_before = self.repo.snapshot(sha)
            after, omitted_after = self.repo.snapshot(result['tree'])
            result['coverage'] = {'before_text_files': len(before), 'after_text_files': len(after), 'omitted_files': sorted(set(omitted_before + omitted_after)), 'changed_files': len(result['changed'])}
            if omitted_before or omitted_after:
                result['warnings'].append('일부 파일이 크기·인코딩·개수 제한으로 제외됐습니다. 분석 범위를 확인하세요.')
            changed = [x['path'] for x in result['changed']]
            old_graph = Trace(before, sha, catalog, branch)
            new_graph = Trace(after, result['tree'], catalog, branch)
            result['warnings'] += old_graph.warnings + new_graph.warnings
            # Sourcegraph searches pin the existing target commit. Hypothetical post-apply
            # trees cannot be indexed by the remote service, so those are traced locally.
            symbols = list(dict.fromkeys(s for p in changed for s in declarations(after.get(p, before.get(p, ''))) if p.endswith('.java')))
            result['sourcegraph'] = []
            for symbol in symbols[:self.config['max_sourcegraph_queries']]:
                sg = self.sg.search(sha, symbol)
                result['sourcegraph'].append({'symbol': symbol, **sg})
                if sg.get('warning'):
                    result['warnings'].append(sg['warning'])
                # Use Sourcegraph for cross-language candidates too, but validate the
                # identifier in the pinned local content; these remain textual edges.
                providers = [p for p in changed if symbol in declarations(before.get(p, after.get(p, '')))]
                for candidate in sg['paths']:
                    for graph, snapshot in ((old_graph, before), (new_graph, after)):
                        match = re.search(r'\b' + re.escape(symbol) + r'\b', snapshot.get(candidate, ''))
                        if match:
                            for provider in providers:
                                graph.edge(provider, candidate, 'Sourcegraph 검색 + 로컬 식별자 확인: ' + symbol + ' (호출 확정 아님)', snapshot[candidate].count('\n', 0, match.start()) + 1)
                if any(path not in before for path in sg['paths']):
                    result['warnings'].append('Sourcegraph 후보 중 로컬 분석 범위에 없는 파일이 있습니다.')
            if len(symbols) > self.config['max_sourcegraph_queries']:
                result['warnings'].append('Sourcegraph 검색 개수 제한에 도달했습니다. 나머지는 로컬 정적 탐색만 수행했습니다.')
            findings, unresolved, limited = new_graph.trace(changed, self.config['max_graph_hops'], self.config['max_evidence_paths'])
            old_findings, old_unresolved, old_limited = old_graph.trace(changed, self.config['max_graph_hops'], self.config['max_evidence_paths'])
            merged = {x['screen']['id']: x for x in findings}
            for finding in old_findings:
                key = finding['screen']['id']
                if key not in merged:
                    finding['before_only'] = True
                    merged[key] = finding
                else:
                    merged[key]['evidence'].extend(finding['evidence'])
            result['screens'] = list(merged.values())
            linked = {e['changed_file'] for f in merged.values() for e in f['evidence']}
            result['unresolved_files'] = [p for p in changed if p not in linked]
            if limited or old_limited:
                result['warnings'].append('정적 추적 깊이/경로 제한에 도달했습니다. 연결된 다른 화면이 있을 수 있습니다.')
            if result['unresolved_files']:
                result['warnings'].append('실제 화면에 연결하지 못한 변경 파일이 있습니다. 영향 없음으로 해석하지 마세요.')
            result['warnings'].append('정적 참조는 화면 영향 후보입니다. 리플렉션·동적 URL·권한·배포 설정·런타임 데이터에 따른 연결은 누락될 수 있습니다. 실제 결함 발생은 검증이 필요합니다.')
            for index, finding in enumerate(result['screens']):
                if index >= self.config['max_ai_requests']:
                    finding['ai_status'] = 'not_run'
                    finding['ai_error'] = 'AI 요청 개수 제한으로 미실행. max_ai_requests 또는 선택 변경 범위를 조정하세요.'
                    continue
                progress(f'{target}: 화면 후보 {index + 1}/{len(result["screens"])}의 변경 근거를 Pi로 분석하고 있습니다.')
                sources = {}
                for evidence in finding['evidence']:
                    snapshot = before if evidence['revision'] == sha else after
                    for edge in evidence['chain']:
                        key = (evidence['revision'], edge['to'], edge['line'])
                        sources[key] = {'revision': evidence['revision'], **excerpt(snapshot, edge['to'], edge['line'])}
                    path = evidence['screen_file']
                    text = snapshot.get(path, '')
                    # Include screen title and event/route lines, preserving explicit excerpt scope.
                    for number, line in enumerate(text.splitlines(), 1):
                        if any(token in line for token in ('<title', '<h1', 'onclick', '$.ajax', 'fetch(', 'url:', 'url :', '@RequestMapping', '@GetMapping', '@PostMapping')):
                            sources[(evidence['revision'], path, number)] = {'revision': evidence['revision'], **excerpt(snapshot, path, number)}
                diffs = {e['changed_file']: self.repo.diff_for(sha, result['tree'], e['changed_file']) for e in finding['evidence']}
                payload = {'target': {'branch': branch, 'sha': sha, 'simulated_tree': result['tree']}, 'application_assumption': report['assumption'], 'screen': finding['screen'], 'before_only': finding.get('before_only', False), 'evidence': finding['evidence'], 'target_changes': diffs, 'source_excerpts': list(sources.values()), 'limits': result['warnings']}
                try:
                    finding['analysis'] = self.pi.analyze(payload)
                    finding['ai_status'] = 'complete'
                except SetupError as e:
                    finding['ai_status'] = 'error'
                    finding['ai_error'] = str(e)
            result['warnings'] = list(dict.fromkeys(result['warnings']))
            result['analysis_status'] = 'partial' if result['unresolved_files'] or omitted_before or omitted_after or limited or old_limited or any(f['ai_status'] != 'complete' or not f['screen']['menu_verified'] for f in result['screens']) or any(sg['status'] != 'ok' for sg in result['sourcegraph']) else 'completed_with_static_limitations'
        return report
