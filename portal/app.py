import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, FileResponse
from starlette.routing import Route
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool
from .config import Config, SetupError
from .services import GitLab, Sourcegraph
from .pi import Pi
from .analysis import Analyzer

executor = ThreadPoolExecutor(max_workers=1)
jobs = {}
lock = threading.Lock()


def response_error(error, status=400):
    # No upstream response bodies, commands or secrets are returned.
    message = str(error) if isinstance(error, SetupError) else '처리에 실패했습니다. 설정·연결 상태와 설치 버전을 확인하세요.'
    return JSONResponse({'error': message}, status_code=status)


def config():
    return Config()


async def home(request):
    return HTMLResponse((Path(__file__).parent / 'index.html').read_text(encoding='utf-8'))


async def settings(request):
    try:
        c = config()
        return JSONResponse({'targets': c['targets'], 'project_id': c['project_id'], 'gitlab_url': c['gitlab_url'], 'sourcegraph_url': c['sourcegraph_url'], 'gitlab_token_present': bool(c.secret('GITLAB_TOKEN')), 'sourcegraph_token_present': bool(c.secret('SOURCEGRAPH_TOKEN')), 'catalog_present': c.path_for('screen_catalog').is_file()})
    except Exception as e:
        return response_error(e)


async def branches(request):
    try:
        values = await run_in_threadpool(GitLab(config()).branches, request.query_params.get('search', ''))
        return JSONResponse({'items': values})
    except Exception as e:
        return response_error(e)


async def commits(request):
    try:
        branch = request.query_params.get('branch', '')
        page = int(request.query_params.get('page', 1))
        if not branch or page < 1:
            raise SetupError('개발 브랜치와 올바른 페이지를 지정하세요.')
        return JSONResponse(await run_in_threadpool(GitLab(config()).commits, branch, page))
    except Exception as e:
        return response_error(e)


def connection_checks(c):
    result = {}
    try:
        project, _ = GitLab(c).get()
        result['gitlab'] = {'status': 'ok', 'message': '프로젝트 조회 성공: ' + project.get('name', '')}
        # Verify configured branch names independently.
        from urllib.parse import quote
        first_sha = None
        for label, branch in c['targets'].items():
            try:
                data, _ = GitLab(c).get('/repository/branches/' + quote(branch, safe=''))
                first_sha = first_sha or data['commit']['id']
                result[label] = {'status': 'ok', 'message': branch + ' / ' + data['commit']['id'][:12]}
            except SetupError as e:
                result[label] = {'status': 'error', 'message': str(e)}
        if first_sha:
            found = Sourcegraph(c).search(first_sha, 'class')
            result['sourcegraph'] = {'status': found['status'], 'message': found.get('warning') or ('대상 SHA 검색 완료. 결과 ' + str(len(found['paths'])) + '개. 검색 결과 0개는 인덱싱 준비를 증명하지 않습니다.')}
        else:
            result['sourcegraph'] = {'status': 'not_run', 'message': '대상 SHA를 가져오지 못해 검색 미실행'}
    except SetupError as e:
        result['gitlab'] = {'status': 'error', 'message': str(e)}
        result['sourcegraph'] = {'status': 'not_run', 'message': 'GitLab 대상 SHA 조회 실패로 미실행'}
    try:
        result['pi'] = Pi(c).check()
    except SetupError as e:
        result['pi'] = {'status': 'error', 'message': str(e)}
    return result


async def checks(request):
    try:
        return JSONResponse(await run_in_threadpool(connection_checks, config()))
    except Exception as e:
        return response_error(e)


def report_path(c, job_id):
    return c.path_for('data_directory') / 'reports' / (job_id + '.json')


def save_report(c, job_id, data):
    path = report_path(c, job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def run_job(c, job_id, body):
    def progress(message):
        with lock:
            jobs[job_id].update(status='running', message=message)
    try:
        result = Analyzer(c).run(body['source_branch'], body['commits'], body['targets'], progress)
        result['id'] = job_id
        result['manual_checks'] = {}
        save_report(c, job_id, result)
        with lock:
            jobs[job_id].update(status='complete', message='분석 결과를 저장했습니다. 결과의 제한·미확인 항목을 확인하세요.')
    except Exception as e:
        with lock:
            jobs[job_id].update(status='error', message=str(e) if isinstance(e, SetupError) else '분석 내부 오류입니다. 입력·설정과 설치 버전을 확인하세요.')


async def analyze(request):
    try:
        c = config()
        body = await request.json()
        if not isinstance(body, dict) or not isinstance(body.get('source_branch'), str) or not isinstance(body.get('commits'), list) or not isinstance(body.get('targets'), list) or not all(isinstance(x, str) for x in body['commits'] + body['targets']):
            raise SetupError('개발 브랜치·커밋 목록·대상 목록을 지정하세요.')
        with lock:
            if any(j['status'] in ('queued', 'running') for j in jobs.values()):
                return response_error(SetupError('분석이 진행 중입니다. 완료 후 다음 분석을 시작하세요.'), 409)
            job_id = uuid.uuid4().hex
            jobs[job_id] = {'status': 'queued', 'message': '분석을 준비하고 있습니다.'}
        executor.submit(run_job, c, job_id, body)
        return JSONResponse({'id': job_id}, status_code=202)
    except Exception as e:
        return response_error(e)


async def job(request):
    job_id = request.path_params['job_id']
    with lock:
        data = jobs.get(job_id)
        data = dict(data) if data else None
    if not data:
        return JSONResponse({'error': '진행 정보를 찾지 못했습니다. 저장된 보고서를 확인하세요.'}, status_code=404)
    return JSONResponse(data)


async def reports(request):
    try:
        root = config().path_for('data_directory') / 'reports'
        items = []
        for path in sorted(root.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
            data = json.loads(path.read_text(encoding='utf-8'))
            items.append({k: data.get(k) for k in ('id', 'created_at', 'source_branch', 'selected_commits')})
        return JSONResponse({'items': items})
    except Exception as e:
        return response_error(e)


async def report(request):
    try:
        job_id = request.path_params['job_id']
        if len(job_id) != 32 or any(c not in '0123456789abcdef' for c in job_id):
            raise SetupError('잘못된 보고서 ID입니다.')
        path = report_path(config(), job_id)
        if not path.is_file():
            return JSONResponse({'error': '보고서를 찾지 못했습니다.'}, status_code=404)
        return FileResponse(path, media_type='application/json', filename='qa-report-' + job_id + '.json' if request.query_params.get('download') else None)
    except Exception as e:
        return response_error(e)


async def manual_check(request):
    try:
        import re
        c = config(); job_id = request.path_params['job_id']; body = await request.json()
        if not re.fullmatch('[0-9a-f]{32}', job_id):
            raise SetupError('잘못된 보고서 ID입니다.')
        if body.get('status') not in ('not_run', 'pass', 'fail', 'blocked'):
            raise SetupError('올바른 검증 상태를 지정하세요.')
        with lock:
            path = report_path(c, job_id)
            data = json.loads(path.read_text(encoding='utf-8'))
            allowed = {t['label'] + ':' + f['screen']['id'] for t in data['targets'] for f in t['screens']}
            key = body.get('key')
            if key not in allowed:
                raise SetupError('보고서에 없는 화면입니다.')
            deployed_sha = body.get('deployed_sha', '').strip()
            if deployed_sha and not re.fullmatch('[0-9a-fA-F]{40,64}', deployed_sha):
                raise SetupError('배포 커밋은 전체 SHA를 입력하세요.')
            note = body.get('note', '')
            if not isinstance(note, str) or len(note) > 10000:
                raise SetupError('검증 메모는 10,000자 이내여야 합니다.')
            data['manual_checks'][key] = {'status': body['status'], 'note': note, 'deployed_sha': deployed_sha, 'deployment_verified': False, 'updated_at': datetime.now(timezone.utc).isoformat()}
            save_report(c, job_id, data)
        return JSONResponse({'status': 'saved'})
    except Exception as e:
        return response_error(e)


app = Starlette(debug=False, routes=[Route('/', home), Route('/api/settings', settings), Route('/api/branches', branches), Route('/api/commits', commits), Route('/api/checks', checks, methods=['POST']), Route('/api/analyze', analyze, methods=['POST']), Route('/api/jobs/{job_id}', job), Route('/api/reports', reports), Route('/api/reports/{job_id}', report), Route('/api/reports/{job_id}/check', manual_check, methods=['POST'])])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', 'testserver'])


@app.middleware('http')
async def local_requests_only(request, call_next):
    # Loopback-only UI; disallow cross-origin form/API writes and DNS rebinding.
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD'):
        if origin and origin not in (f'http://{request.headers.get("host")}', f'https://{request.headers.get("host")}'):
            return JSONResponse({'error': '다른 사이트에서 보낸 요청은 허용하지 않습니다.'}, status_code=403)
        if not request.headers.get('content-type', '').startswith('application/json'):
            return JSONResponse({'error': 'JSON 요청만 허용합니다.'}, status_code=415)
    return await call_next(request)
