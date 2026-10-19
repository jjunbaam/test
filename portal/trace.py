"""Conservative static candidates. Edges are textual evidence, not a compiler call graph."""
import hashlib
import json
import re
from collections import defaultdict, deque
from pathlib import PurePosixPath


def stable_id(*parts):
    return hashlib.sha256('\0'.join(parts).encode()).hexdigest()[:16]


def line_of(text, pos):
    return text.count('\n', 0, pos) + 1


def route_key(route):
    return '/' + route.split('?', 1)[0].strip('/')


def java_code(text):
    # Preserve offsets while removing comments; strings remain for route/view extraction.
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/'
    return re.sub(pattern, lambda m: re.sub(r'[^\n]', ' ', m.group()) if m.group().startswith(('//', '/*')) else m.group(), text)


def declarations(text):
    return list(dict.fromkeys(re.findall(r'\b(?:class|interface|enum|record)\s+(\w+)', java_code(text))))


def routes_in(text):
    code = java_code(text)
    anns = list(re.finditer(r'@(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\s*\(([^)]*)\)', code))
    cls = re.search(r'\bclass\s+\w+', code)
    prefixes, routes = [''], []
    for ann in anns:
        values = re.findall(r'["\']([^"\']+)["\']', ann[2].split('method=')[0])
        # Only positional/path/value attributes, not produces/consumes/header values.
        attr = re.search(r'(?:value|path)\s*=\s*(\{[^}]*\}|["\'][^"\']+["\'])', ann[2])
        if attr:
            values = re.findall(r'["\']([^"\']+)["\']', attr[1])
        elif not re.match(r'\s*["\'{]', ann[2]):
            values = []
        if cls and ann.start() < cls.start():
            prefixes = values or ['']
        else:
            for value in values:
                for prefix in prefixes:
                    routes.append((route_key(prefix.rstrip('/') + '/' + value.lstrip('/')), line_of(text, ann.start())))
    return routes


class Trace:
    def __init__(self, files, revision, catalog, branch):
        self.files, self.revision = files, revision
        self.edges = defaultdict(list)
        self.screens = defaultdict(list)
        self.routes = defaultdict(list)
        self.warnings = []
        self._build(catalog, branch)

    def edge(self, source, dest, reason, line):
        if source != dest:
            edge = {'from': source, 'to': dest, 'reason': reason, 'line': line, 'revision': self.revision}
            if edge not in self.edges[source]:
                self.edges[source].append(edge)

    def _build(self, catalog, branch):
        classes = defaultdict(list)
        for path, text in self.files.items():
            if path.endswith('.java'):
                for name in declarations(text):
                    classes[name].append(path)
                for route, line in routes_in(text):
                    self.routes[route].append((path, line))
        # Tokenization builds a reverse class-reference index in linear source size.
        for consumer, text in self.files.items():
            if consumer.endswith('.java'):
                seen = set()
                for token in re.finditer(r'\b[A-Za-z_$][\w$]*\b', java_code(text)):
                    name = token.group()
                    if name in classes and name not in seen:
                        seen.add(name)
                        for provider in classes[name]:
                            self.edge(provider, consumer, f'클래스 식별자 참조: {name} (메서드 호출 확정 아님)', line_of(text, token.start()))
        views = [p for p in self.files if p.endswith(('.jsp', '.jspx', '.html', '.vue', '.jsx', '.tsx'))]
        frontends = [p for p in self.files if p.endswith(('.jsp', '.jspx', '.html', '.js', '.ts', '.vue', '.jsx', '.tsx'))]
        basename_index = defaultdict(list)
        for path in frontends:
            basename_index[PurePosixPath(path).name].append(path)
        for path in frontends:
            text = self.files[path]
            # URL literals: do not infer routing from arbitrary filenames.
            for match in re.finditer(r'["\']([^"\'\n]+)["\']', text):
                literal = re.sub(r'\$\{[^}]*\}|<%.*?%>', '', match[1]).strip()
                for owner, _ in self.routes.get(route_key(literal), []):
                    self.edge(owner, path, '요청 경로 문자열 일치: ' + literal, line_of(text, match.start()))
            for match in re.finditer(r'(?:src|file|page)\s*=\s*["\']([^"\']+)["\']', text):
                literal = match[1].split('?', 1)[0]
                name = PurePosixPath(literal).name
                for dependency in basename_index.get(name, []):
                    suffix = re.sub(r'\$\{[^}]*\}|<%.*?%>', '', literal).lstrip('./')
                    if dependency.endswith(suffix) and suffix:
                        self.edge(dependency, path, '스크립트/뷰 포함 경로: ' + literal, line_of(text, match.start()))
        # Controller -> rendered view, with evidence and all matching candidates retained.
        for path, text in self.files.items():
            if not path.endswith('.java'):
                continue
            for match in re.finditer(r'(?:return\s+|new\s+ModelAndView\s*\(|setViewName\s*\()\s*"([^"\n]+)"', java_code(text)):
                view = match[1]
                if view.startswith(('redirect:', 'http:', 'https:')):
                    continue
                view = view.removeprefix('forward:').lstrip('/')
                for candidate in views:
                    if any(candidate.endswith('/' + view + ext) or candidate == view + ext for ext in ('', '.jsp', '.html')):
                        self.edge(path, candidate, '반환 뷰 이름 일치: ' + view, line_of(text, match.start()))
        # MyBatis XML namespace -> mapper interface/class, then Java references carry upstream.
        for path, text in self.files.items():
            if path.endswith('.xml'):
                match = re.search(r'<mapper\b[^>]*namespace=["\']([^"\']+)["\']', text)
                if match:
                    for owner in classes.get(match[1].split('.')[-1], []):
                        self.edge(path, owner, 'MyBatis namespace: ' + match[1], line_of(text, match.start()))
        translations = defaultdict(set)
        for resource_path, resource_text in self.files.items():
            if resource_path.endswith('.properties'):
                for line in resource_text.splitlines():
                    entry = re.match(r'\s*([^#!\s][^=:]*?)\s*[=:]\s*(.*)', line)
                    if entry:
                        value = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), entry[2])
                        translations[entry[1].strip()].add(value.strip())
        registered = set()
        for item in catalog:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item.get('name'):
                self.warnings.append('화면 카탈로그의 잘못된 항목을 제외했습니다.')
                continue
            paths = [p for p in item.get('view_paths', []) if p in self.files]
            for route in item.get('routes', []):
                paths.extend(p for p, _ in self.routes.get(route_key(route), []))
            verified = branch in item.get('verified_refs', []) or self.revision in item.get('verified_refs', [])
            if not paths:
                self.warnings.append(f'카탈로그 화면 {item["id"]}: 이 버전에서 연결 파일/경로를 찾지 못했습니다.')
            for path in dict.fromkeys(paths):
                screen = {'id': item['id'], 'name': item['name'], 'menu_path': item.get('menu_path', ''), 'features': item.get('features', []), 'routes': item.get('routes', []), 'identity_source': '사용자 관리 카탈로그', 'menu_verified': verified and bool(item.get('menu_path')), 'path': path}
                self.screens[path].append(screen)
                registered.add(path)
        for path in views:
            if path in registered:
                continue
            text = self.files[path]
            match = re.search(r'<(?:title|h1)\b[^>]*>([\s\S]*?)</(?:title|h1)>', text, re.I)
            title = ''
            if match:
                title = match[1].strip()
                message = re.fullmatch(r'<(?:spring:message|fmt:message)\b[^>]*(?:code|key)=[\"\']([^\"\']+)[\"\'][^>]*/?>', title)
                if message:
                    values = translations.get(message[1], set())
                    korean = {value for value in values if re.search('[가-힣]', value)}
                    candidates = korean or values
                    title = next(iter(candidates)) if len(candidates) == 1 else ''
            if title and not re.search(r'\$\{|<|\{\{|#\{', title):
                self.screens[path].append({'id': stable_id(path), 'name': title, 'menu_path': '', 'features': [], 'routes': [], 'identity_source': '소스의 title/h1·메시지 리소스 (실제 메뉴 경로 미확인)', 'menu_verified': False, 'path': path})

    def trace(self, changed, max_hops=5, max_paths=60):
        findings, unresolved, limited = {}, [], False
        for root in changed:
            if root not in self.files:
                continue
            queue, visited, found = deque([(root, [])]), {root}, False
            while queue:
                node, chain = queue.popleft()
                for screen in self.screens.get(node, []):
                    found = True
                    key = screen['id']
                    if key not in findings:
                        findings[key] = {'screen': screen, 'evidence': []}
                    evidence = {'id': stable_id(root, node, self.revision), 'changed_file': root, 'revision': self.revision, 'screen_file': node, 'chain': chain, 'kind': '직접 변경' if not chain else '정적 참조 경로 후보'}
                    if len(findings[key]['evidence']) < max_paths:
                        findings[key]['evidence'].append(evidence)
                    else:
                        limited = True
                if len(chain) >= max_hops:
                    if self.edges[node]:
                        limited = True
                    continue
                for edge in self.edges[node]:
                    if edge['to'] not in visited:
                        visited.add(edge['to'])
                        queue.append((edge['to'], chain + [edge]))
            if not found:
                unresolved.append(root)
        return list(findings.values()), unresolved, limited


def load_catalog(config):
    path = config.path_for('screen_catalog')
    if not path.is_file():
        return [], ['화면 카탈로그가 없습니다. 소스에서 찾은 화면 제목을 사용하며 정확한 메뉴 경로는 미확인으로 표시합니다.']
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data.get('screens'), list):
            raise ValueError()
        return data['screens'], []
    except (ValueError, OSError):
        return [], ['화면 카탈로그를 읽지 못했습니다. 파일 형식을 확인하세요.']
