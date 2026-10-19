import re

file_path = "C:/Users/USER/gitlab-qa-analyzer/app.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Make the prompt stricter about NOT outputting fake .java files in symptom/detail
prompt_replacement = """[실제 코드 Diff 내용]:
{full_diff_text[:3500]}

중요 지침:
1. QA 엔지니어가 리포트를 읽습니다. `.java`나 `.jsp` 같은 소스코드 파일 경로를 '증상(symptom)'이나 '상세 가이드(detail)'에 절대로 노출하지 마세요.
2. 팩트 데이터에 화면명이 없다면, 수정된 파일명(예: ServerConnect)을 보고 "서버 연동 화면" 혹은 "서버 연결 관리 메뉴"처럼 QA가 알아들을 수 있는 한글 메뉴/기능명으로 100% 번역해서 작성하세요.
3. "oooo.java 백엔드 자바 로직 수정을 통해" 같은 개발자스러운 표현은 절대 금지합니다. 대신 "서버 연결 관리 기능 수정으로 인해"라고 작성하세요.

반드시 아래 JSON 형식으로 응답해:"""

content = content.replace("[실제 코드 Diff 내용]:\n{full_diff_text[:3500]}\n\n반드시 아래 JSON 형식으로 응답해:", prompt_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Prompt strict rules applied!")
