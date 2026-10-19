import json
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent


class SetupError(RuntimeError):
    pass


class Config:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get('QA_CONFIG', ROOT / 'config.local.json')).resolve()
        if not self.path.is_file():
            raise SetupError('config.local.json이 없습니다. config.example.json을 복사하고 사내 설정을 확인하세요.')
        defaults = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8-sig'))
        defaults.update(json.loads(self.path.read_text(encoding='utf-8-sig')))
        self.values = defaults
        self.base = self.path.parent
        for key in ('gitlab_url', 'repository_url', 'sourcegraph_url'):
            url = defaults.get(key, '')
            if key == 'sourcegraph_url' and not url:
                continue
            parsed = urlsplit(url)
            if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
                raise SetupError(f'{key}: 인증정보 없는 HTTP(S) 주소가 필요합니다.')
        if urlsplit(defaults['repository_url']).netloc != urlsplit(defaults['gitlab_url']).netloc:
            raise SetupError('repository_url과 gitlab_url의 호스트가 같아야 합니다.')
        if not isinstance(defaults['pi_command'], list) or not defaults['pi_command'] or not all(isinstance(x, str) for x in defaults['pi_command']):
            raise SetupError('pi_command는 명령 인수의 JSON 배열이어야 합니다.')
        if not defaults['targets'] or not all(isinstance(v, str) and v for v in defaults['targets'].values()):
            raise SetupError('targets에 실제 PR/R 브랜치를 지정하세요.')
        for key in ('max_files', 'max_file_bytes', 'max_source_bytes', 'max_graph_hops', 'max_evidence_paths', 'max_sourcegraph_queries', 'max_ai_requests', 'max_prompt_chars', 'pi_timeout_seconds', 'request_timeout_seconds', 'git_timeout_seconds'):
            if not isinstance(defaults[key], int) or defaults[key] < 1:
                raise SetupError(f'{key}는 양의 정수여야 합니다.')

    def __getitem__(self, key):
        return self.values[key]

    def path_for(self, key):
        path = Path(self[key])
        return path if path.is_absolute() else self.base / path

    @property
    def verify(self):
        return str(self.path_for('ca_bundle')) if self['ca_bundle'] else True

    def secret(self, name):
        return os.environ.get(name, '')

    def redact(self, message):
        text = str(message)
        for name in ('GITLAB_TOKEN', 'SOURCEGRAPH_TOKEN', 'GEMINI_API_KEY'):
            value = self.secret(name)
            if value:
                text = text.replace(value, '[REDACTED]')
        return text
