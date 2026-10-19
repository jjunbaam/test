import re

file_path = "C:/Users/USER/gitlab-qa-analyzer/app.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace hardcoded messages in analyze_fact_based_diff_engine

# 1. UI resources
content = content.replace(
    'f"`{filename}` 수정 파일 연동 화면에서 아이콘 이미지 깨짐(X표시) 또는 UI 레이아웃 정렬 이상 발생 가능성"',
    'f"해당 UI/디자인 리소스 변경으로 인해 연동 화면에서 아이콘 깨짐 또는 레이아웃 정렬 이상 발생 가능성"'
)
content = content.replace(
    'f"Sourcegraph SG 팩트 검증: 수정 파일 `{file_path}` 패치건입니다. 해당 화면 접속 후 아이콘 이미지 렌더링 및 UI 레이아웃 정렬 상태 수동 확인을 권장합니다."',
    'f"디자인 리소스 패치건입니다. 해당 화면 접속 후 전반적인 UI 렌더링 및 레이아웃 상태 수동 확인을 권장합니다."'
)

# 2. Scripts/JSP
content = content.replace(
    'f"`{filename}` 연동 화면에서 주요 기능 버튼 클릭 시 반응 없음 또는 멈춤 가능성"',
    'f"해당 화면에서 주요 기능 버튼 클릭 시 반응이 없거나 스크립트 오류로 인해 멈출 가능성"'
)
content = content.replace(
    'f"Sourcegraph SG 팩트 검증: 수정한 파일 `{file_path}` 스크립트 패치로, 브라우저에서 해당 화면 접속 후 버튼 클릭 시 클릭 반응 먹통 가능성이 높습니다. 수동 검증을 권장합니다."',
    'f"스크립트 로직 패치로 인해 브라우저 환경에서 버튼 클릭 이벤트 먹통이나 데이터 렌더링 실패 가능성이 있습니다. 화면 내 주요 기능 수동 검증을 권장합니다."'
)

# 3. Java Backend
content = content.replace(
    'f"`{filename}` 연동 백엔드 화면 접근 시 500 에러 팝업 또는 데이터 미출력 가능성"',
    'f"해당 서버 로직과 연동되는 화면에 접근하거나 데이터 조회 시 500 에러 팝업 또는 데이터 미출력 가능성"'
)
content = content.replace(
    'f"Sourcegraph SG 팩트 검증: `{file_path}` 백엔드 자바 로직 수정을 통해 API 데이터 파싱 시 예외가 터져 해당 연동 화면이 비어서 나올 위험이 있습니다. 수동 검증을 권장합니다."',
    'f"서버 데이터 처리 로직 수정으로 인해 API 응답 시 예외가 발생할 위험이 있습니다. 해당 기능(조회/저장 등) 수행 시 데이터가 비어서 나오는지 수동 검증을 권장합니다."'
)
content = content.replace(
    'f"`{file_path}` 백엔드 메서드/변수 패치"',
    'f"서버 기능/데이터 처리 로직 패치"'
)

# 4. DB XML/SQL
content = content.replace(
    'f"`{filename}` 연동 화면에서 \'검색\' 클릭 시 목록 결과가 0건으로 누락될 가능성"',
    'f"해당 화면에서 데이터를 \'검색\'하거나 조회할 때 목록 결과가 누락되거나 에러가 발생할 가능성"'
)
content = content.replace(
    'f"Sourcegraph SG 팩트 검증: `{file_path}` 내 SQL WHERE 조건 및 매핑 파라미터 수정으로 데이터 조회 결과 누락 유무 수동 확인을 권장합니다."',
    'f"DB 쿼리 조건 및 매핑 파라미터 수정으로 인해, 화면에서 데이터 조회 시 결과가 누락되거나 잘못된 데이터가 노출되는지 수동 확인을 권장합니다."'
)
content = content.replace(
    'f"`{file_path}` SQL 쿼리 조건절 패치"',
    'f"DB 조회/저장 쿼리 패치"'
)

# 5. System/Others
content = content.replace(
    'f"Sourcegraph SG 팩트 검증: 수정 파일 `{file_path}` 패치 적용 후 관리자 콘솔에서 해당 모듈의 상태값 변경 및 패치 버전 적용 유무를 수동 확인하세요."',
    'f"시스템 설정 파일 패치 적용 후, 관리자 콘솔 또는 관련 기능에서 상태값 변경 및 정상 동작 유무를 수동 확인하세요."'
)
content = content.replace(
    'f"`{file_path}` 스크립트/설정 패치"',
    'f"시스템 스크립트 및 환경설정 패치"'
)

# 6. Test Cases (TCs)
content = content.replace(
    'f"`{sc[\'raw_file\']}` 연관 화면"',
    'f"{sc[\'screen_name\']} 연관 화면/기능"'
)
content = content.replace(
    'f"Sourcegraph 팩트 추천: 수정한 파일 `{sc[\'raw_file\']}`의 성격({sc[\'screen_name\']})에 맞춰 실제 연동 화면 접속 후 주요 기능 수동 검증"',
    'f"[{sc[\'screen_name\']}] 화면에 접속하여 관련된 주요 기능 및 버튼들이 정상적으로 동작하는지 수동 검증 진행"'
)

# Also fix the fallback mapping names to be human readable
content = content.replace(
    'f"[{module_name}] API 컨트롤러 ({filename})"',
    'f"[{module_name}] API 서버 컨트롤러"'
)
content = content.replace(
    'f"[{module_name}] DB 쿼리 ({filename})"',
    'f"[{module_name}] DB 데이터 처리 쿼리"'
)
content = content.replace(
    'f"[{module_name}] 웹 화면 ({filename})"',
    'f"[{module_name}] 웹 UI 화면"'
)
content = content.replace(
    'f"[{module_name}] UI 리소스 ({filename})"',
    'f"[{module_name}] UI 디자인 리소스"'
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Hardcoded messages cleaned up!")
