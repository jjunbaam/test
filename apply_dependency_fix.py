import re

file_path = "C:/Users/USER/gitlab-qa-analyzer/app.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

new_query_sourcegraph = """def query_sourcegraph_api(commit_sha, files_summary):
    import requests
    mapped_info = []
    
    for f in files_summary:
        path = f['path']
        filename = path.split('/')[-1]
        
        # 1. 파일이 지도에 직접 있으면 바로 사용
        if path in URL_MAP:
            mapped_info.append(f"[{path}] -> 실제 연동 화면명: {URL_MAP[path].get('screen_name', '알수없음')}")
            continue
            
        # 2. 파일이 지도에 없으면, Sourcegraph를 통해 이 파일을 Import하는 다른 Controller나 파일을 역추적!
        try:
            class_name = filename.split('.')[0] # 예: ServerConnectByRAServerImpl
            # Sourcegraph로 이 클래스를 사용하는 파일 검색
            query = f'repo:gitlab.somansa.com/platform/git-dlpcenter lang:java {class_name} count:5'
            headers = {'Authorization': f'token {SOURCEGRAPH_TOKEN}', 'Content-Type': 'application/json'}
            graphql_query = f'query {{ search(query: "{query}", version: V3) {{ results {{ results {{ ... on FileMatch {{ file {{ path }} }} }} }} }} }}'
            
            res = requests.post(f"{SOURCEGRAPH_URL}/.api/graphql", json={'query': graphql_query}, headers=headers, timeout=5)
            if res.status_code == 200:
                matches = res.json().get('data', {}).get('search', {}).get('results', {}).get('results', [])
                found_parent = False
                for match in matches:
                    parent_path = match['file']['path']
                    # 만약 찾은 부모 파일이 지도에 있다면!
                    if parent_path in URL_MAP:
                        parent_screen = URL_MAP[parent_path].get('screen_name', '알수없음')
                        mapped_info.append(f"[{path}] -> 의존성 추적 팩트: 이 공통/서비스 파일은 [{parent_screen}] 화면에서 주로 호출됨.")
                        found_parent = True
                        break
                
                if not found_parent:
                     mapped_info.append(f"[{path}] -> 연동 화면: 직접 연결된 화면을 찾을 수 없는 코어 로직 ({filename})")
            else:
                mapped_info.append(f"[{path}] -> 연동 화면: 코어 백엔드 모듈 ({filename})")
        except:
             mapped_info.append(f"[{path}] -> 연동 화면: 공통/백엔드/기타 모듈 ({filename})")
             
    return "\n".join(mapped_info)"""

content = re.sub(r'def query_sourcegraph_api.*?return "\n"\.join\(mapped_info\)', new_query_sourcegraph, content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Dependency tracking logic applied!")
