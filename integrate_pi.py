import re

file_path = "C:/Users/USER/gitlab-qa-analyzer/app.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add subprocess
if "import subprocess" not in content:
    content = content.replace("import requests", "import requests\nimport subprocess")

pi_integration_code = """def analyze_with_pi_cli(commit_title, full_diff_text, files_summary, base_branch, sg_symbol_data):
    try:
        print("[INFO] Calling local Pi Agent (CLI) to generate AI report...")
        prompt = f'''
너는 소만사 DLPCenter 15년 차 수석 QA 엔지니어야.
이번 커밋에 포함된 파일들이 실제 화면(UI)이나 API와 어떻게 매핑되는지에 대한 팩트 데이터를 바탕으로, QA 담당자가 직관적으로 이해할 수 있는 "화면 중심의 검증 가이드"를 작성해.

[커밋 제목]: {commit_title}
[비교 기준]: {base_branch} 브랜치
[코드 ↔ 화면 매핑 팩트 데이터]:
{sg_symbol_data}

[실제 코드 Diff 내용]:
{full_diff_text[:3000]}

중요 지침:
1. QA 엔지니어가 리포트를 읽습니다. `.java`나 `.jsp` 같은 소스코드 파일 경로나 개발 용어를 '증상(symptom)'이나 '상세 가이드(detail)'에 절대로 노출하지 마세요.
2. 팩트 데이터에 화면명이 없다면, 수정된 파일명(예: ServerConnect)을 보고 "서버 연동 화면" 혹은 "서버 연결 관리 메뉴"처럼 QA가 알아들을 수 있는 한글 메뉴/기능명으로 번역해서 작성하세요.
3. 반드시 아래 JSON 형식만 반환하세요 (마크다운 없이 순수 JSON만 출력).

{{
  "risk_level": "HIGH 또는 MEDIUM",
  "impacted_screens": [
    {{
      "module_code": "해당 제품군(PRIVACYI 등)",
      "module_name": "제품 모듈명",
      "raw_file": "수정한 실제 파일 경로",
      "screen_name": "팩트 데이터에 명시된 한글 화면명/메뉴명 (없을시 유추)",
      "impact_degree": "직접 영향 (HIGH) 또는 간접",
      "description": "어떤 화면의 어떤 기능이 수정되었는지 QA가 알기 쉽게 설명",
      "affected_features": ["영향받는 화면 내 UI 요소나 기능 1", "기능 2"]
    }}
  ],
  "side_effects": [
    {{
      "module_name": "제품 모듈명",
      "category": "🔴 [화면 오류 위험] 또는 🎨 [UI 깨짐 위험] 등",
      "symptom": "해당 화면(메뉴)에서 발생 가능한 구체적 결함 증상",
      "severity": "HIGH 또는 MEDIUM",
      "detail": "QA가 이 증상을 확인하기 위해 어떤 화면 메뉴에 들어가서 어떤 행동을 해야하는지 가이드",
      "code_fact": "수정된 주요 설정(예: 서버 주소 변경, 조회 조건 변경 등)",
      "target_menu": "테스트해야 할 화면명/메뉴명",
      "root_cause": "어떤 로직이 수정되었는지"
    }}
  ],
  "recommended_tcs": [
    {{
      "id": "TC-SG-001",
      "module_name": "제품 모듈명",
      "target_screen": "테스트할 화면명",
      "test_scenario": "수동 테스트 수행 스텝 (예: OO메뉴 접속 -> 버튼 클릭 -> XX 확인)",
      "priority": "High 또는 Medium",
      "expected_result": "정상 동작 시 기대되는 결과"
    }}
  ]
}}
'''
        # Pi CLI를 non-interactive 모드(-p)로 실행하여 출력값을 캡처합니다.
        result = subprocess.run(["pi", "-p", prompt], capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            raise Exception(f"Pi execution failed: {result.stderr}")
            
        output = result.stdout.strip()
        # 마크다운 코드블록 제거
        output = re.sub(r'```(?:json)?\n?', '', output)
        output = re.sub(r'```', '', output).strip()
        
        return json.loads(output)
    except Exception as e:
        print("[ERROR] Pi Agent generation failed:", e)
        return analyze_fact_based_diff_engine(commit_title, full_diff_text, files_summary, base_branch, sg_symbol_data)
"""

# Inject function
if "def analyze_with_pi_cli" not in content:
    content = content.replace("def analyze_with_openai_fact_engine", pi_integration_code + "\ndef analyze_with_openai_fact_engine")

# Route to Pi when OpenAI key is absent
routing_replacement = """        if openai_key and len(openai_key.strip()) > 5:
            analysis_result = analyze_with_openai_fact_engine(commit_title, full_diff_text, files_summary, base_branch, openai_key, sg_symbol_data)
        else:
            analysis_result = analyze_with_pi_cli(commit_title, full_diff_text, files_summary, base_branch, sg_symbol_data)"""

content = re.sub(r'        if openai_key and len\(openai_key\.strip\(\)\) > 5:.*?else:\s*analysis_result = analyze_fact_based_diff_engine\([^)]+\)', routing_replacement, content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Pi CLI integration applied!")
