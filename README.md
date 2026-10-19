# DLPCenter 변경 영향 검토 포털

사내 PC에서 GitLab의 개발 Branch와 커밋, 반영 대상 **PR (`master`) / R (`2025_ES5_Release_버전_분기`)**을 선택해 코드 적용 결과와 화면 영향 후보를 검토합니다. 사내 Sourcegraph와 기존 Pi 0.81.1의 Gemini 연결을 사용합니다.

**현재 버전은 사내 검증을 시작할 수 있는 첫 구현입니다.** 샘플 저장소와 모의 서비스로 검증했으며, 실제 DLPCenter 소스·사내 서버·Windows Pi 실행은 외부 개발 환경에서 검증하지 못했습니다. 정적 코드 참조와 AI 위험 가설은 실제 결함 발생의 증명이 아닙니다.

## Windows에서 시작

1. Git for Windows, Python 3.11 이상, 기존 Pi 0.81.1이 필요합니다. **평소 Pi가 동작하는 동일 사용자 PowerShell**을 사용하세요.
2. 이 저장소를 다운로드/복제하고 해당 폴더로 이동합니다.
3. 설치합니다.

```powershell
.\setup.ps1
```

PowerShell 정책으로 스크립트 실행이 막힌 경우 회사의 허용된 절차를 따르거나 아래 명령을 직접 실행하세요. 설정을 전역으로 완화할 필요는 없습니다.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# config.local.json이 없을 때만 실행합니다.
Copy-Item config.example.json config.local.json
```

4. `config.local.json`을 편집합니다. **비밀키를 넣지 마세요.** 기존 설정에서 가져온 GitLab 프로젝트 `317`, 저장소 URL 및 Sourcegraph 주소가 현재 환경과 일치하는지 확인하세요. PR/R 이름은 전달받은 값으로 설정되어 있습니다.
5. 아래 방법으로 필요한 토큰을 현재 PowerShell 프로세스에만 입력합니다. 키를 명령줄에 직접 쓰거나 Git에 저장하지 않습니다.

```powershell
$gitlabCredential = Read-Host 'GitLab token (read_api + read_repository)' -AsSecureString
$env:GITLAB_TOKEN = [System.Net.NetworkCredential]::new('', $gitlabCredential).Password
$sourcegraphCredential = Read-Host 'Sourcegraph access token' -AsSecureString
$env:SOURCEGRAPH_TOKEN = [System.Net.NetworkCredential]::new('', $sourcegraphCredential).Password
```

GitLab 토큰은 커밋 조회와 HTTPS Git 읽기에 사용합니다. Pi 키는 기존 Pi 설정을 그대로 사용하며 **다시 입력하거나 포털에 복사하지 않습니다.** 이전 첨부 소스의 하드코딩된 토큰은 재사용하지 말고 폐기·재발급하세요.

6. 실행합니다.

```powershell
.\run.ps1
# 또는
.\run.bat
```

이 PC의 브라우저에서 `http://127.0.0.1:8000`을 엽니다. 종료는 PowerShell에서 Ctrl+C입니다. 서버는 개인 PC의 loopback에만 바인딩합니다. 공유 서버 배포용 사용자 인증은 구현하지 않았습니다.

사내 PC가 외부 패키지 저장소에 접근하지 못하면 승인된 내부 Python 패키지 미러를 사용하거나, 승인된 외부 PC에서 대상 Windows/Python에 맞는 wheel을 준비해 오프라인 설치하세요. 인증서 검증을 끄는 옵션은 사용하지 않습니다.

## 첫 실행 순서

1. **GitLab · Sourcegraph · Pi 확인**을 누릅니다. GitLab·Sourcegraph·Pi와 PR/R 브랜치를 동시에 검사하며 완료된 결과부터 표시합니다. 각 항목에 경과 시간이 나오고, Pi 연결 확인은 최대 60초, 브라우저 요청 대기는 최대 90초입니다. 실제 분석의 Pi 제한시간은 별도 설정을 유지합니다. 이 검사는 분석 결과의 정확도 검증을 대신하지 않습니다.
2. 개발 Branch 이름을 검색하고 선택한 뒤 커밋을 조회합니다. 모르는 Branch 이름을 추정하거나 PR/R을 개발 Branch로 자동 지정하지 않습니다.
3. 작업에 포함된 일반 커밋을 1~30개 선택합니다. Git 이력상 순서로 적용합니다. 선행 변경이 필요하면 함께 선택하세요.
4. PR, R 또는 둘 다 선택하고 분석합니다. 첫 Git fetch는 저장소 크기와 네트워크에 따라 시간이 걸립니다.
5. 결과에서 대상 SHA, 커밋별 적용 여부, 화면 후보, 예상 위험, 근거, 미확인 파일 및 분석 범위를 확인합니다.
6. 실제 반영 후 저장된 보고서에서 화면별 검증 상태·메모·배포 SHA를 기록할 수 있습니다. 배포 SHA는 사용자 입력이며 배포 서버와 자동 대조하지 않습니다.

## 반영 방식에 대한 가정

실제 조직의 반영 방식은 아직 확인되지 않았습니다. 이 버전은 각 선택 커밋의 **단일 부모 대비 변경**을 대상 코드에 순서대로 3-way 적용하는 시뮬레이션입니다. 전체 Branch merge나 개발자가 수정 내용을 옮기는 작업을 동일하게 재현한다고 주장하지 않습니다.

- 개발 Branch와 대상 Branch를 fetch한 뒤 정확한 SHA를 기록합니다.
- 별도의 Git index에서만 변경을 적용합니다. 원격 push, commit 작성, 실제 PR/R 변경, Git worktree 생성은 하지 않습니다.
- 이미 포함된 커밋, 같은 패치, 빈 변경을 구분합니다. 충돌하면 해당 대상의 화면 분석을 중단하고 충돌/선행 변경 확인을 안내합니다.
- merge 커밋과 루트 커밋은 거절합니다. merge의 mainline을 임의로 선택하지 않습니다.
- 가상의 반영 결과는 Git tree SHA로 저장합니다. 실제 배포 커밋 SHA와는 다릅니다.

## 화면 이름과 메뉴 경로

새 분석기는 기존 `url_mapping.json`을 사실로 재사용하지 않습니다. 이전 파일에는 일반 컨트롤러명이 다수 들어 있고 버전/생성 근거가 불확실하기 때문입니다.

자동 탐색은 실제 소스에서 다음 연결의 **후보와 근거 위치**를 수집합니다.

- Java 클래스/인터페이스 식별자 참조
- MyBatis XML namespace → Java 참조
- Spring Request/Get/Post/Put/Delete/PatchMapping → 프런트엔드 URL 문자열
- Controller 반환 뷰 → JSP/HTML
- JSP/HTML의 script/include 참조
- JSP/HTML 등의 title/h1, Spring/fmt 메시지 키와 properties의 한글 제목
- Sourcegraph에서 대상 SHA로 검색한 클래스명 후보를 같은 리비전의 로컬 코드에서 다시 확인

실제 메뉴 경로가 코드에 없거나 동적으로 구성되면 자동 확정할 수 없습니다. 제목을 찾으면 제목을 표시하고 **메뉴 경로 미확인**이라고 명시합니다. 제목도 확인하지 못하면 파일을 “화면 미확인” 목록에 둡니다. 파일명을 한글 메뉴로 번역해 발명하지 않습니다.

정확한 QA 메뉴 경로를 확정하려면 실제 UI와 대조한 `screens.local.json`을 추가할 수 있습니다. `screens.example.json`의 형식을 참고하되 예시 내용을 실제 화면으로 오인하지 마세요. 실제 경로/라우트가 해당 대상 코드에 존재하는 항목만 사용합니다. `verified_refs`에 확인한 대상 브랜치 또는 SHA를 기록합니다. 클래스 전체를 라우트 하나와 연결하면 검증 범위가 넓어질 수 있으므로 가급적 실제 view_paths와 기능 단위 routes를 등록하세요.

**이 추적은 Java 컴파일러의 메서드 수준 호출 그래프가 아닙니다.** 동명 클래스, 문자열 URL, 동적 호출 등으로 오탐/누락이 있을 수 있습니다. 자동으로 찾은 참조 경로를 “결함 확정”으로 표시하지 않으며 AI도 구체적인 변경 근거가 있을 때만 위험을 작성하도록 제한합니다. 실제 코드에서 정확도를 검증하며 필요한 추적기를 보완해야 합니다.

## 사내 Pi 연결

사용자 제공 Pi 0.81.1 도움말의 옵션을 사용합니다.

- `--provider google --mode json -p`
- `--no-session --no-tools --no-extensions --no-skills --no-prompt-templates --no-context-files --no-approve`
- `--offline`: Pi 시작 시 부수적인 네트워크 작업을 끕니다. 모델 API 호출은 수행합니다.
- `PI_TELEMETRY=0`

입력 근거는 사내 PC의 임시 JSON 파일로 전달하고 실행 후 삭제합니다. AI에는 GitLab/Sourcegraph 토큰을 전달하지 않습니다. 응답은 완료된 assistant 메시지에서 추출하고 화면 ID·필수 필드·인용 근거 ID를 검사합니다. 이는 형식/인용 무결성 검사이며 내용의 진실성을 완전히 보증하지 않습니다.

기본 설정 폴더는 `PI_CODING_AGENT_DIR` 또는 사용자 홈의 `.pi/agent`입니다. `models.json`의 google provider가 `pi_expected_base_url`의 사내 주소 및 `google-generative-ai` 방식인지 확인한 뒤 실행합니다. 다른 위치라면 `pi_config_directory`에 실제 설정 폴더를 지정하세요. 원본 설정 파일과 키를 변경하지 않습니다.

`pi_model`을 비워두면 Pi가 선택하는 기본 모델을 사용합니다. 특정 모델이 필요하면 `pi --list-models`에서 확인한 사내 모델 ID를 설정하세요. Windows에서는 npm의 `pi.cmd`에서 JavaScript 진입점을 찾아 Node를 직접 실행합니다. 비표준 설치라 자동 탐지가 실패하면 `pi_command`를 `["node", "C:/실제/Pi/경로/dist/cli.js"]` 형태로 지정합니다. 실제 경로는 설치 환경에서 확인하세요.

AI 오류, JSON 오류, 시간 초과, 입력 한도 초과는 **AI 분석 미완료**로 표시합니다. 고정 위험 문구로 대체하지 않습니다. 여러 화면은 개별 요청으로 분석하며 모든 화면에 AI 요청이 실행됐는지 상태를 표시합니다.

## 설정·데이터와 문제 해결

- `config.local.json`: 주소, 브랜치, Pi 실행 명령, 제한값. Git 제외.
- `.qa-data/`: bare Git 캐시와 분석 보고서/검증 기록. 사내 코드가 들어 있으므로 외부에 업로드하지 마세요. Git 제외.
- `screens.local.json`: 검증된 실제 메뉴 카탈로그. Git 제외.
- 최초 Git fetch가 제한시간을 넘으면 네트워크 확인 후 `git_timeout_seconds`를 조정할 수 있습니다.
- HTTPS 사내 CA가 필요한 경우 `ca_bundle`에 인증기관 PEM 묶음 경로를 지정합니다. GitLab/Sourcegraph HTTPS 요청과 Git에 적용됩니다. Pi의 CA 설정은 기존 사내 Node/Pi 정책을 따릅니다. **TLS 검증을 끄지 않습니다.**
- 기존 Sourcegraph 주소는 HTTP입니다. 사내에 승인된 HTTPS 주소가 있으면 `sourcegraph_url`을 교체하세요.
- GitLab 401/403은 토큰 범위·접근 권한을, 404는 프로젝트 ID·브랜치 이름을 확인하세요.
- Sourcegraph는 선택 대상 SHA를 검색해야 합니다. 과거/대상 리비전 검색이 서버에서 불가능하면 결과가 부분 분석으로 표시됩니다. 검색 0건은 인덱싱 완료의 증명이 아닙니다.
- 각 파일/전체 소스/추적 깊이/AI 요청의 제한은 config.example.json에 있습니다. 한도 초과 항목은 표시하며 “영향 없음”으로 처리하지 않습니다. 프런트엔드에 없는 파일 타입·서브모듈 내부·런타임 설정은 분석 범위 밖입니다.
- 개발 중인 파일을 원격에 반영하기 전 단계는 지원하지 않습니다. GitLab에서 조회되는 커밋을 분석합니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux 개발 검증은 같은 명령에서 `.venv/bin/python`을 사용합니다. 테스트는 임시 Git 저장소와 모의 GitLab/Sourcegraph/Pi를 사용하며 회사 서버에 연결하지 않습니다. 실제 사내 연결 및 화면 적중률은 내부에서 대표 커밋으로 확인해야 합니다. 알려진 영향 화면이 있는 변경과 주석만 변경한 커밋을 함께 검증하는 것을 권장합니다.

기존 구현과 진단 자료는 비교를 위해 남아 있습니다. **새 실행 진입점은 `portal.app:app`**입니다. 기존 `app.py`, `apply_*.py`, `integrate_pi.py`, `prompt_fix.py`, `clean_hardcoded_messages.py`, `build_url_map.py`를 실행하지 마세요. 이전 진단은 [review/DIAGNOSIS.ko.md](review/DIAGNOSIS.ko.md)에 있습니다.
