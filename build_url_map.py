import os
import re
import json
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GITLAB_URL = "https://gitlab.somansa.com"
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")
PROJECT_ID = "317"  # git-dlpcenter

def build_somansa_url_map():
    print("[INFO] DLPCenter Source Code URL Router Mapping Scan Started...")
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    
    # GitLab repository tree API를 통해 자바 컨트롤러 및 JSP 파일 목록 수집
    tree_url = f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/repository/tree?recursive=true&per_page=100"
    
    try:
        res = requests.get(tree_url, headers=headers, verify=False, timeout=10)
        if res.status_code != 200:
            print(f"[ERROR] GitLab API Error: {res.status_code}")
            return {}
        
        files = res.json()
        url_map = {}

        controller_files = [f for f in files if f.get('path', '').endswith('.java') or f.get('path', '').endswith('.jsp')]
        print(f"[INFO] Target Files Found: {len(controller_files)} files")

        for f in controller_files[:30]:  # 주요 컨트롤러 파일 스캔
            file_path = f.get('path')
            raw_url = f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/repository/files/{requests.utils.quote(file_path, safe='')}/raw?ref=master"
            
            f_res = requests.get(raw_url, headers=headers, verify=False, timeout=5)
            if f_res.status_code == 200:
                content = f_res.text
                
                # @RequestMapping 및 *.sms URL 정규식 추출
                mappings = re.findall(r'@RequestMapping\s*\(\s*["\']([^"\']+\.sms)["\']', content)
                sms_urls = re.findall(r'([\w/]+\.sms)', content)
                titles = re.findall(r'<title>(.*?)</title>', content)
                
                found_url = mappings[0] if mappings else (sms_urls[0] if sms_urls else None)
                found_title = titles[0] if titles else file_path.split('/')[-1]

                if found_url:
                    url_map[file_path] = {
                        "sms_url": found_url if found_url.startswith('DLPCenter/') else f"DLPCenter/{found_url.lstrip('/')}",
                        "screen_name": found_title
                    }

        # 결과 매핑 파일 저장
        output_path = "C:/Users/USER/gitlab-qa-analyzer/url_mapping.json"
        with open(output_path, "w", encoding="utf-8") as out:
            json.dump(url_map, out, indent=2, ensure_ascii=False)
            
        print(f"[SUCCESS] URL Mapping Completed: {len(url_map)} files mapped -> {output_path}")
        return url_map

    except Exception as e:
        print(f"[ERROR] Scan Exception: {e}")
        return {}

if __name__ == "__main__":
    build_somansa_url_map()
