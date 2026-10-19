import re

file_path = "C:/Users/USER/gitlab-qa-analyzer/app.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add URL_MAP loading at the top
if "URL_MAP =" not in content:
    replacement = """import urllib3
import requests

URL_MAP = {}
try:
    with open("C:/Users/USER/gitlab-qa-analyzer/url_mapping.json", "r", encoding="utf-8") as f:
        URL_MAP = json.load(f)
except:
    pass
"""
    content = content.replace("import urllib3\nimport requests", replacement)

# 2. Replace query_sourcegraph_api with map_screens_from_files
new_query_sourcegraph = """def query_sourcegraph_api(commit_sha, files_summary):
    # 이제 Sourcegraph API 대신 사전에 스캔된 URL_MAP을 사용하여 정확한 화면(메뉴) 매핑 정보를 리턴합니다.
    mapped_info = []
    for f in files_summary:
        path = f['path']
        if path in URL_MAP:
            mapped_info.append(f"[{path}] -> 실제 연동 화면명: {URL_MAP[path].get('screen_name', '알수없음')}")
        else:
            filename = path.split('/')[-1]
            mapped_info.append(f"[{path}] -> 연동 화면: [DLPCenter] 공통/백엔드/기타 모듈 ({filename})")
    return "\n".join(mapped_info)"""

content = re.sub(r'def query_sourcegraph_api.*?return f"Sourcegraph 라이브 API 스캔 완료\."\s*except Exception as e:\s*return f"Sourcegraph 라이브 API 스캔 완료\."', new_query_sourcegraph, content, flags=re.DOTALL)

# 3. Replace analyze_with_openai_fact_engine
new_openai_engine = """def analyze_with_openai_fact_engine(commit_title, full_diff_text, files_summary, base_branch, openai_key, sg_symbol_data):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        prompt = f'''
너는 소만사 DLPCenter 15년 차 수석 QA 엔지니어야.
이번 커밋에 포함된 파일들이 실제 화면(UI)이나 API와 어떻게 매핑되는지에 대한 팩트 데이터를 바탕으로, QA 담당자가 직관적으로 이해할 수 있는 "화면 중심의 검증 가이드"를 작성해줘. "oooo.java 파일을 확인하라"는 식의 답변은 절대 금지하며, 반드시 아래 팩트 데이터를 바탕으로 한글 화면명이나 모듈명을 명시해야 해.

[커밋 제목]: {commit_title}
[비교 기준]: {base_branch} 브랜치
[코드 ↔ 화면 매핑 팩트 데이터]:
{sg_symbol_data}

[실제 코드 Diff 내용]:
{full_diff_text[:3500]}

반드시 아래 JSON 형식으로 응답해:
{{
  "risk_level": "HIGH 또는 MEDIUM 또는 LOW",
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
      "code_fact": "원인이 되는 코드의 주요 수정 내용",
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
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print("OpenAI Error:", e)
        return analyze_fact_based_diff_engine(commit_title, full_diff_text, files_summary, base_branch, sg_symbol_data)"""

content = re.sub(r'def analyze_with_openai_fact_engine.*?return analyze_fact_based_diff_engine\(commit_title, full_diff_text, files_summary, base_branch\)', new_openai_engine, content, flags=re.DOTALL)


# 4. Modify endpoint to pass sg_symbol_data to openai
content = content.replace("analyze_result = analyze_with_openai_fact_engine(commit_title, full_diff_text, files_summary, base_branch, openai_key)",
                          "analyze_result = analyze_with_openai_fact_engine(commit_title, full_diff_text, files_summary, base_branch, openai_key, sg_symbol_data)")

# 5. Fix analyze_fact_based_diff_engine to use URL_MAP
content = content.replace('filename = file_path.split(\'/\')[-1]', 'filename = file_path.split(\'/\')[-1]\n        mapped_screen = URL_MAP.get(file_path, {}).get("screen_name", "")')

content = content.replace('f"[{module_name}] UI 리소스 파일 ({filename})"', 'f"[{module_name}] {mapped_screen} (UI 리소스)" if mapped_screen else f"[{module_name}] UI 리소스 ({filename})"')
content = content.replace('f"[{module_name}] 웹 화면 스크립트/뷰 파일 ({filename})"', 'f"[{module_name}] {mapped_screen}" if mapped_screen else f"[{module_name}] 웹 화면 ({filename})"')
content = content.replace('f"[{module_name}] 백엔드 로직/컨트롤러 모듈 ({filename})"', 'f"[{module_name}] {mapped_screen}" if mapped_screen else f"[{module_name}] API 컨트롤러 ({filename})"')
content = content.replace('f"[{module_name}] DB 쿼리/매퍼 모듈 ({filename})"', 'f"[{module_name}] {mapped_screen} (DB 쿼리)" if mapped_screen else f"[{module_name}] DB 쿼리 ({filename})"')

# 6. Change hardcoded fake report sentences to be more helpful
content = content.replace('f"수정한 파일: `{file_path}`"', 'f"{mapped_screen} 화면" if mapped_screen else f"수정한 파일: `{file_path}`"')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Patch applied to app.py")
