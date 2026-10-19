# 🛡️ GitLab QA Impact Analyzer (사이드이펙트 영향도 자동 예측 포털)

> **"GitLab 빌드/MR 링크 입력 한 번으로, 개발 변경 사항이 어떤 화면과 기능에 사이드이펙트를 일으킬지 실시간 분석하고 추천 QA 테스트케이스를 도출하는 AI QA 분석 포털"**

---

## 📌 1. 시스템 핵심 개요

개발자의 코드 수정 후 빌드/MR이 생성될 때 발생하던 예기치 않은 **사이드이펙트(Side-Effect)** 문제를 해결하기 위해 구축된 **QA 전용 AI 영향도 분석 포털**입니다.

### 🔄 전체 작동 파이프라인 (Pipeline)
1. **GitLab REST API 연동**: 지정된 MR / Commit의 코드 Diff, 수정 파일, 커밋 메시지 실시간 수집
2. **코드 ↔ UI/기능 구조 매핑**: View(JSP/HTML/React), Controller, Service, DB Query, Config 파일 분석
3. **AI & 지능형 추론 엔진 실행**:
   - 코드 로직 수정으로 인한 **영향받는 화면(UI)** 도출
   - 파라미터/Null 예외, 상태값 분기, SQL 변경에 따른 **사이드이펙트 버그 위험군** 예측
   - QA 우선 검증 대상 **테스트케이스(TC)** 및 **검증 시나리오** 자동 생성
4. **리포트 및 자동 연동**: 웹 화면 리포트 출력, 마크다운/PDF 다운로드, **GitLab MR 코멘트 자동 등록**

---

## 🚀 2. 실행 방법 (Quick Start)

### 실행 방법
`C:\Users\USER\gitlab-qa-analyzer` 경로에서 아래 명령어 실행:

```bash
# 방법 1. 파이썬으로 실행
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# 방법 2. 배치 파일 실행
run.bat
```

서버가 실행되면 웹 브라우저에서 아래 주소로 접속합니다:
👉 **http://localhost:8000**

---

## 💻 3. 주요 기능 및 UI 스펙

1. **GitLab MR 조회 및 자동 선택**: 사내 GitLab (`gitlab.somansa.com`)의 최근 MR 목록 자동 연동 및 선택.
2. **사이드이펙트 AI 분석 리포트**:
   - **위험도 스코어ing (HIGH / MEDIUM / LOW)**
   - **1. 영향받는 화면(UI) 및 연관 기능 매핑**
   - **2. 발생 가능 사이드이펙트 시나리오 및 원인 코드 분석**
   - **3. QA 우선 검증 추천 테스트케이스 (TC) 테이블**
   - **4. 수정된 코드 Diff 브레이크다운**
3. **GitLab MR 코멘트 자동 남기기**: 분석된 AI 검증 의견을 GitLab MR 코멘트로 1-Click 자동 작성.

---

## 🎤 4. 발표(Presentation) 시연 시나리오

발표 시 아래 4단계 스토리라인으로 시연하시면 매우 임팩트 있는 발표가 됩니다.

### [1단계] 문제 정의 (Problem Statement)
* *"개발팀에서 새로운 모듈 빌드가 나올 때마다 예기치 않은 화면 및 기능 사이드이펙트가 발생해 QA 검증 범위가 급증하는 문제가 있었습니다."*

### [2단계] 현존 AI 툴 검토 및 한계점 파악 (Tool Analysis)
* *"Qodo(PR-Agent), CodeRabbit, GitLab Duo 등 기존 AI 툴을 검토했으나, 이 툴들은 '개발 코드 관점' 분석에 치중되어 있어, **QA 관점의 어떤 화면과 어떤 기능이 깨질지** 정밀하게 짚어주지 못하는 한계가 있었습니다."*

### [3단계] 자체 AI 영향도 분석 포털 구축 (Solution & Demo)
* *"이를 해결하기 위해 GitLab API와 AI 추론 파이프라인을 결합한 **QA Impact Analyzer** 포털을 직접 개발했습니다."*
* *(웹 브라우저 http://localhost:8000 접속 시연)*
* *"실제 GitLab MR 번호를 선택하고 버튼을 누르면, 실시간으로 코드 Diff를 파싱하여 **1) 영향 화면, 2) 예기치 않은 사이드이펙트 위험군, 3) 우선 검증 TC**를 즉시 뽑아냅니다."*

### [4단계] 기대 효과 (Business Impact)
* *"이 포털을 통해 QA의 리그레션 테스트 범위를 60% 이상 줄이고, 빌드마다 발생하는 사이드이펙트 버그를 사전에 차단할 수 있습니다."*

---

## 📁 파일 구조
```
C:\Users\USER\gitlab-qa-analyzer\
├── app.py          # Starlette/Uvicorn 백엔드 API & HTML/Tailwind UI (통합 단일 실행 파일)
├── run.bat         # 1-Click 서버 실행 파일
└── README.md       # 안내 매뉴얼 및 발표 시연 가이드
```
