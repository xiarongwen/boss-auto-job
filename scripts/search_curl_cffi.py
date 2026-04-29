#!/usr/bin/env python3
"""
BOSS Zhipin Search - curl_cffi Mode with TLS Fingerprint Bypass

Uses curl_cffi to mimic Chrome's TLS fingerprint, combined with
user's real cookies from browser for authentication.

Usage:
  python search_curl_cffi.py "Python" --city=101010100 --pages=3
  python search_curl_cffi.py "Python" --cookies=/path/to/cookies.json
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from curl_cffi import requests as cffi_requests

DEFAULT_COOKIE_PATH = Path.home() / '.agent-browser' / 'auth' / 'boss-zhipin.json'
FALLBACK_COOKIE_PATH = Path.home() / '.hermes' / 'credentials' / 'boss_cookies.json'

SECURITY_JS_URL = 'https://www.zhipin.com/web/common/security-js/{name}.js'
API_URL = 'https://www.zhipin.com/wapi/zpgeek/search/joblist.json'
PAGE_URL = 'https://www.zhipin.com/web/geek/job?query={query}&city={city}&page={page}'


def load_cookies(cookie_path: str = None) -> dict:
    """Load cookies from auth file."""
    paths = [cookie_path, DEFAULT_COOKIE_PATH, FALLBACK_COOKIE_PATH]
    
    for p in paths:
        if p and Path(p).exists():
            with open(p) as f:
                data = json.load(f)
            
            cookies = {}
            for cookie in data.get('cookies', []):
                if 'zhipin.com' in cookie.get('domain', ''):
                    cookies[cookie['name']] = cookie['value']
            
            if cookies:
                print(f"[cookies] Loaded {len(cookies)} cookies from {p}")
                return cookies
    
    print("[cookies] ERROR: No valid cookie file found")
    print(f"[cookies] Tried: {paths}")
    sys.exit(1)


def generate_zp_stoken(seed: str, ts: str, name: str, session) -> str:
    """Generate __zp_stoken__ using Node.js VM."""
    # Fetch security JS
    js_url = SECURITY_JS_URL.format(name=name)
    js_resp = session.get(js_url, headers={
        'Referer': 'https://www.zhipin.com/web/geek/job',
    }, timeout=10)
    
    if js_resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch security JS: {js_resp.status_code}")
    
    # Save JS to temp file
    js_path = f'/tmp/boss_security_{name}.js'
    with open(js_path, 'w') as f:
        f.write(js_resp.text)
    
    # Generate token using Node.js
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync('{js_path}', 'utf8');
const ctx = {{
    window: {{}}, document: {{}},
    navigator: {{ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' }},
    location: {{ href: 'https://www.zhipin.com/web/common/security-check.html', search: '?seed=' + encodeURIComponent('{seed}') + '&ts={ts}' }},
    console: console, setTimeout: setTimeout, setInterval: setInterval
}};
vm.createContext(ctx);
vm.runInContext(code, ctx);
const ABC = ctx.window.ABC;
const instance = new ABC();
const offset = new Date().getTimezoneOffset();
const tsValue = parseInt('{ts}') + (480 + offset) * 60 * 1000;
const result = instance.z('{seed}', tsValue);
console.log('ZP_STOKEN:' + result);
"""
    node_path = f'/tmp/gen_zp_{name}.js'
    with open(node_path, 'w') as f:
        f.write(node_script)
    
    result = subprocess.run(['node', node_path], capture_output=True, text=True, timeout=10)
    
    for line in result.stdout.split('\n'):
        if line.startswith('ZP_STOKEN:'):
            return line.split(':', 1)[1]
    
    raise RuntimeError(f"Failed to generate zp_stoken: {result.stderr[:200]}")


def search_jobs(query: str, city: str, pages: int, cookie_path: str = None) -> list:
    """Search jobs using curl_cffi with TLS fingerprint bypass."""
    # Load cookies
    cookies = load_cookies(cookie_path)
    
    # Create session with Chrome TLS fingerprint
    session = cffi_requests.Session(impersonate='chrome120')
    
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.zhipin.com/',
    }
    
    api_headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': PAGE_URL.format(query=query, city=city, page=1),
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    all_jobs = []
    zp_stoken_generated = False
    
    for page_num in range(1, pages + 1):
        page_url = PAGE_URL.format(query=query, city=city, page=page_num)
        print(f"[search] Page {page_num}: {page_url}")
        
        # Visit the page first (to establish session)
        resp1 = session.get(page_url, headers=headers, cookies=cookies, timeout=15)
        print(f"  Page status: {resp1.status_code}")
        
        # Call the job list API
        params = {
            'scene': '1',
            'query': query,
            'city': city,
            'page': str(page_num),
            'pageSize': '30',
        }
        
        resp2 = session.get(API_URL, headers=api_headers, params=params, timeout=15)
        
        try:
            data = resp2.json()
            code = data.get('code')
            
            if code == 0:
                # Success!
                jobs = data.get('zpData', {}).get('jobList', [])
                print(f"  ✅ Found {len(jobs)} jobs")
                all_jobs.extend(jobs)
                
            elif code == 37 and not zp_stoken_generated:
                # Environment check - need zp_stoken
                print(f"  ⚠️ Code 37: Environment check, generating zp_stoken...")
                zpData = data.get('zpData', {})
                seed = zpData.get('seed', '')
                ts = str(zpData.get('ts', ''))
                name = zpData.get('name', '')
                
                try:
                    new_token = generate_zp_stoken(seed, ts, name, session)
                    cookies['__zp_stoken__'] = new_token
                    zp_stoken_generated = True
                    print(f"  ✅ Generated zp_stoken: {new_token[:50]}...")
                    
                    # Retry the API call
                    resp3 = session.get(API_URL, headers=api_headers, params=params, cookies=cookies, timeout=15)
                    data3 = resp3.json()
                    
                    if data3.get('code') == 0:
                        jobs = data3.get('zpData', {}).get('jobList', [])
                        print(f"  ✅ Found {len(jobs)} jobs after zp_stoken")
                        all_jobs.extend(jobs)
                    else:
                        print(f"  ❌ Still failed: code={data3.get('code')} - {data3.get('message')}")
                        
                except Exception as e:
                    print(f"  ❌ zp_stoken generation failed: {e}")
                    
            elif code == 36:
                # Account flagged
                print(f"  ❌ Code 36: Account flagged as abnormal")
                print(f"  Message: {data.get('message')}")
                print(f"  Solution: Login manually in Chrome, complete verification, then re-export cookies")
                break
                
            elif code == 1006:
                # Rate limited
                print(f"  ⚠️ Code 1006: Rate limited, waiting 10s...")
                time.sleep(10)
                
            else:
                print(f"  ❌ Unexpected code {code}: {data.get('message')}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Rate limiting
        if page_num < pages:
            time.sleep(3)
    
    return all_jobs


def main():
    parser = argparse.ArgumentParser(description="Search jobs on BOSS Zhipin")
    parser.add_argument("query", help="Job keyword to search")
    parser.add_argument("--city", default="101010100", help="City code (default: 101010100 = Beijing)")
    parser.add_argument("--pages", type=int, default=3, help="Number of pages to scrape")
    parser.add_argument("--cookies", help="Path to cookies JSON file")
    parser.add_argument("--output", help="Output file (default: stdout)")
    args = parser.parse_args()
    
    print(f"[search] Query: {args.query}")
    print(f"[search] City: {args.city}")
    print(f"[search] Pages: {args.pages}")
    print()
    
    jobs = search_jobs(args.query, args.city, args.pages, args.cookies)
    
    print(f"\n[search] Total: {len(jobs)} jobs found")
    
    # Format output
    output_jobs = []
    for j in jobs:
        output_jobs.append({
            'job_id': j.get('encryptJobId') or j.get('jobId'),
            'title': j.get('jobName', ''),
            'company': j.get('brandName', ''),
            'salary': j.get('salaryDesc', ''),
            'location': j.get('cityName', ''),
            'area': j.get('areaDistrict', ''),
            'experience': j.get('jobExperience', ''),
            'degree': j.get('jobDegree', ''),
            'labels': j.get('jobLabels', []),
            'skills': j.get('skills', []),
            'description': j.get('jobDesc', ''),
            'boss_name': j.get('bossName', ''),
            'boss_title': j.get('bossTitle', ''),
            'encrypt_user_id': j.get('encryptUserId', ''),
            'company_size': j.get('scaleName', ''),
            'company_type': j.get('typeName', ''),
        })
    
    output = json.dumps(output_jobs, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"[search] Saved to {args.output}")
    else:
        print("===JOBS_JSON_START===")
        print(output)
        print("===JOBS_JSON_END===")


if __name__ == "__main__":
    main()
