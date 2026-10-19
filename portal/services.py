import json
import re
from urllib.parse import quote
import requests
from .config import SetupError


class GitLab:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        token = config.secret('GITLAB_TOKEN')
        if token:
            self.session.headers['PRIVATE-TOKEN'] = token
        self.root = config['gitlab_url'].rstrip('/') + '/api/v4/projects/' + quote(str(config['project_id']), safe='')

    def get(self, path='', params=None):
        try:
            r = self.session.get(self.root + path, params=params, timeout=self.config['request_timeout_seconds'], verify=self.config.verify, allow_redirects=False)
        except requests.RequestException as e:
            raise SetupError(f'GitLab 요청 실패 ({type(e).__name__}). 주소·VPN·인증서·접근 권한을 확인하세요.') from None
        if r.status_code != 200:
            raise SetupError(f'GitLab HTTP {r.status_code}. 주소·토큰 권한을 확인하세요.')
        try:
            return r.json(), r.headers.get('X-Next-Page', '')
        except ValueError:
            raise SetupError('GitLab이 JSON 대신 다른 응답을 반환했습니다.') from None

    def branches(self, search=''):
        result, page = [], '1'
        while page:
            data, page = self.get('/repository/branches', {'search': search, 'page': page, 'per_page': 100})
            result.extend({'name': b['name'], 'sha': b['commit']['id']} for b in data)
            if len(result) >= 2000 and page:
                raise SetupError('브랜치가 2,000개를 넘습니다. 검색어를 입력하세요.')
        return result

    def commits(self, branch, page=1):
        data, next_page = self.get('/repository/commits', {'ref_name': branch, 'page': page, 'per_page': 50})
        return {'items': [{'sha': x['id'], 'title': x['title'], 'date': x['created_at'], 'author': x['author_name']} for x in data], 'next_page': next_page}


class Sourcegraph:
    def __init__(self, config):
        self.config = config

    def search(self, sha, symbol):
        if not self.config['sourcegraph_url']:
            return {'status': 'disabled', 'paths': [], 'warning': 'Sourcegraph가 설정되지 않았습니다.'}
        # A complete SHA fixes the search revision; only safe identifier searches are accepted.
        if not re.fullmatch(r'[0-9a-f]{40,64}', sha) or not re.fullmatch(r'[\w$]+', symbol):
            raise SetupError('Sourcegraph 검색 리비전 또는 식별자가 잘못되었습니다.')
        repo = '^' + re.escape(self.config['sourcegraph_repository']) + '$'
        query = f'repo:{repo}@{sha} patternType:literal {symbol} count:100 timeout:15s'
        headers = {'Accept': 'text/event-stream'}
        if self.config.secret('SOURCEGRAPH_TOKEN'):
            headers['Authorization'] = 'token ' + self.config.secret('SOURCEGRAPH_TOKEN')
        try:
            r = requests.get(self.config['sourcegraph_url'].rstrip('/') + '/.api/search/stream', params={'q': query, 'v': 'V3'}, headers=headers, timeout=self.config['request_timeout_seconds'], verify=self.config.verify, allow_redirects=False)
        except requests.RequestException as e:
            return {'status': 'error', 'paths': [], 'warning': f'Sourcegraph 연결 실패 ({type(e).__name__}). 로컬 코드 탐색 결과만 사용합니다.'}
        if r.status_code != 200:
            return {'status': 'error', 'paths': [], 'warning': f'Sourcegraph HTTP {r.status_code}. 로컬 코드 탐색 결과만 사용합니다.'}
        paths, warnings, complete = [], [], False
        blocks = re.split(r'\r?\n\r?\n', r.text)
        for block in blocks:
            event, lines = '', []
            for line in block.splitlines():
                if line.startswith('event:'):
                    event = line[6:].strip()
                elif line.startswith('data:'):
                    lines.append(line[5:].strip())
            if not lines:
                continue
            try:
                data = json.loads('\n'.join(lines))
            except ValueError:
                warnings.append('Sourcegraph 응답 일부를 해석하지 못했습니다.')
                continue
            if event == 'matches' and isinstance(data, list):
                for match in data:
                    if match.get('repository') == self.config['sourcegraph_repository'] and match.get('commit') == sha and match.get('path'):
                        paths.append(match['path'])
                    else:
                        warnings.append('리비전·저장소가 확인되지 않은 Sourcegraph 결과를 제외했습니다.')
            if event == 'progress':
                complete = bool(data.get('done'))
                if data.get('skipped'):
                    warnings.append('Sourcegraph 검색에서 제외되거나 제한된 결과가 있습니다.')
            if event in ('error', 'alert'):
                warnings.append('Sourcegraph가 검색 경고/오류를 반환했습니다.')
        if not complete:
            warnings.append('Sourcegraph 검색 완료를 확인하지 못했습니다.')
        return {'status': 'ok' if complete and not warnings else 'partial', 'paths': sorted(set(paths)), 'warning': ' '.join(dict.fromkeys(warnings)), 'query': query}
