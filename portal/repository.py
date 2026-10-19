"""Read-only remote access and isolated Git-index patch simulation (no worktrees)."""
import base64
import hashlib
import os
import re
import subprocess
import tempfile
from pathlib import Path
from .config import SetupError

TEXT_SUFFIXES = {'.java', '.jsp', '.jspx', '.html', '.htm', '.js', '.jsx', '.ts', '.tsx', '.vue', '.xml', '.sql', '.json', '.properties', '.yml', '.yaml'}


class Repository:
    def __init__(self, config, local_path=None):
        self.config = config
        identity = hashlib.sha256(config['repository_url'].encode()).hexdigest()[:16]
        self.path = Path(local_path) if local_path else config.path_for('data_directory') / ('repository-' + identity + '.git')
        self.environment = os.environ.copy()
        # Keep credentials out of command arguments, remote URLs and on-disk configuration.
        settings = [('credential.interactive', 'false'), ('core.hooksPath', str(config.path_for('data_directory') / 'no-hooks'))]
        token = config.secret('GITLAB_TOKEN')
        if token:
            auth = base64.b64encode(('oauth2:' + token).encode()).decode()
            settings.append(('http.' + config['gitlab_url'].rstrip('/') + '/.extraHeader', 'Authorization: Basic ' + auth))
        if config['ca_bundle']:
            settings.append(('http.sslCAInfo', str(config.path_for('ca_bundle'))))
        settings.append(('http.sslVerify', 'true'))
        # Existing runtime Git authentication configuration is preserved, then scoped settings appended.
        offset = int(self.environment.get('GIT_CONFIG_COUNT', '0'))
        for i, (key, value) in enumerate(settings, offset):
            self.environment[f'GIT_CONFIG_KEY_{i}'] = key
            self.environment[f'GIT_CONFIG_VALUE_{i}'] = value
        self.environment['GIT_CONFIG_COUNT'] = str(offset + len(settings))
        self.environment['GIT_TERMINAL_PROMPT'] = '0'
        self.environment['GCM_INTERACTIVE'] = 'never'

    def run(self, *args, input=None, env=None, check=True):
        try:
            p = subprocess.run(['git', '--git-dir', str(self.path), *args], input=input, capture_output=True, env=env or self.environment, timeout=self.config['git_timeout_seconds'])
        except FileNotFoundError:
            raise SetupError('Git을 찾을 수 없습니다. Git for Windows를 설치하고 PowerShell을 다시 여세요.') from None
        except subprocess.TimeoutExpired:
            raise SetupError('Git 작업 제한시간을 초과했습니다. 네트워크와 저장소 크기를 확인하세요.') from None
        if check and p.returncode:
            # Git diagnostics can contain URLs/credentials. Return a fixed message, never raw stderr.
            raise SetupError('Git ' + args[0] + ' 실패. 저장소 주소·브랜치·인증·사내 CA 설정을 확인하세요.')
        return p

    def prepare(self, branches):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.run('init', '--bare', str(self.path))
            self.run('remote', 'add', 'origin', self.config['repository_url'])
        refs = {}
        for branch in dict.fromkeys(branches):
            if not branch or self.run('check-ref-format', 'refs/heads/' + branch, check=False).returncode:
                raise SetupError('유효하지 않은 브랜치 이름입니다.')
            key = hashlib.sha256(branch.encode()).hexdigest()[:20]
            ref = 'refs/qa/' + key
            self.run('fetch', '--no-tags', 'origin', '+refs/heads/' + branch + ':' + ref)
            refs[branch] = self.run('rev-parse', '--verify', ref + '^{commit}').stdout.decode().strip()
        return refs

    def ordered_commits(self, source_sha, selected):
        if not selected or len(selected) > 30 or len(set(selected)) != len(selected):
            raise SetupError('중복 없이 1~30개 커밋을 선택하세요.')
        for sha in selected:
            if not re.fullmatch('[0-9a-f]{40,64}', sha):
                raise SetupError('전체 커밋 SHA가 필요합니다.')
            if self.run('merge-base', '--is-ancestor', sha, source_sha, check=False).returncode:
                raise SetupError('선택 커밋이 현재 개발 브랜치 이력에 없습니다. 목록을 새로 조회하세요.')
        order = self.run('rev-list', '--topo-order', '--reverse', source_sha).stdout.decode().splitlines()
        return [sha for sha in order if sha in selected]

    def simulate(self, target_sha, selected):
        results = []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='qa-index-', dir=self.path.parent) as tmp:
            index = Path(tmp) / 'index'
            env = dict(self.environment, GIT_INDEX_FILE=str(index))
            self.run('read-tree', target_sha, env=env)
            for sha in selected:
                parents = self.run('rev-list', '--parents', '-n', '1', sha).stdout.decode().split()[1:]
                if len(parents) != 1:
                    raise SetupError('루트 또는 merge 커밋은 지원하지 않습니다. 실제 개발 변경 커밋을 선택하세요. Merge 방식 분석은 아직 지원하지 않습니다.')
                patch = self.run('diff', '--binary', '--full-index', '--no-ext-diff', '--no-renames', parents[0], sha).stdout
                if not patch:
                    results.append({'sha': sha, 'status': 'empty'})
                    continue
                if self.run('merge-base', '--is-ancestor', sha, target_sha, check=False).returncode == 0:
                    results.append({'sha': sha, 'status': 'already_in_history'})
                    continue
                before = index.read_bytes()
                applied = self.run('apply', '--cached', '--3way', '--whitespace=nowarn', '-', input=patch, env=env, check=False)
                if applied.returncode:
                    index.write_bytes(before)
                    reverse = self.run('apply', '--cached', '--reverse', '--check', '-', input=patch, env=env, check=False)
                    if reverse.returncode == 0:
                        results.append({'sha': sha, 'status': 'patch_already_present'})
                        continue
                    return {'status': 'conflict', 'target_sha': target_sha, 'commits': results + [{'sha': sha, 'status': 'conflict'}], 'message': '선택 변경을 대상 코드에 자동 적용할 수 없습니다. 충돌 또는 선행 커밋 누락을 확인하세요. 충돌 해결 후 코드는 분석하지 않았습니다.'}
                results.append({'sha': sha, 'status': 'applied'})
            tree = self.run('write-tree', env=env).stdout.decode().strip()
        raw = self.run('diff', '--name-status', '-z', '--no-renames', target_sha, tree).stdout.decode('utf-8', 'replace').split('\0')
        changed = [{'status': raw[i], 'path': raw[i + 1]} for i in range(0, len(raw) - 1, 2)]
        return {'status': 'applied' if changed else 'no_change', 'target_sha': target_sha, 'tree': tree, 'commits': results, 'changed': changed}

    def snapshot(self, revision):
        raw = self.run('ls-tree', '-r', '-l', '-z', revision).stdout.decode('utf-8', 'replace')
        entries, omitted, total = [], [], 0
        for line in raw.split('\0'):
            if not line:
                continue
            info, path = line.split('\t', 1)
            mode, kind, oid, size = info.split()
            if kind != 'blob' or mode == '120000' or Path(path).suffix.lower() not in TEXT_SUFFIXES:
                continue
            size = int(size)
            if size > self.config['max_file_bytes'] or len(entries) >= self.config['max_files'] or total + size > self.config['max_source_bytes']:
                omitted.append(path)
                continue
            entries.append((path, oid))
            total += size
        files = {}
        if entries:
            result = self.run('cat-file', '--batch', input=('\n'.join(oid for _, oid in entries) + '\n').encode()).stdout
            cursor = 0
            for path, oid in entries:
                end = result.index(b'\n', cursor)
                header = result[cursor:end].split()
                if len(header) != 3 or header[1] != b'blob':
                    raise SetupError('Git 객체 내용을 읽지 못했습니다.')
                size = int(header[2]); start = end + 1
                blob = result[start:start + size]
                cursor = start + size + 1
                if b'\0' in blob:
                    omitted.append(path)
                    continue
                try:
                    files[path] = blob.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        files[path] = blob.decode('cp949')
                    except UnicodeDecodeError:
                        omitted.append(path)
        return files, omitted

    def diff_for(self, before, after, path):
        return self.run('diff', '--no-ext-diff', '--unified=5', before, after, '--', path).stdout.decode('utf-8', 'replace')
