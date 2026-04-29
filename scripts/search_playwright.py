#!/usr/bin/env python3
"""Search BOSS Zhipin using Playwright with real cookies."""
import json, sys, time
from pathlib import Path

AUTH_FILE = Path.home() / '.agent-browser/auth/boss-zhipin.json'

def main():
    from playwright.sync_api import sync_playwright
    
    # Load cookies
    with open(AUTH_FILE) as f:
        auth = json.load(f)
    
    pw_cookies = []
    for c in auth.get('cookies', []):
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
        }
        expires = c.get("expires", -1)
        if expires and expires > 0:
            cookie["expires"] = expires
        if c.get("httpOnly"):
            cookie["httpOnly"] = True
        if c.get("secure"):
            cookie["secure"] = True
        pw_cookies.append(cookie)
    
    print(f"[init] Loaded {len(pw_cookies)} cookies")
    
    with sync_playwright() as p:
        # Use agent-browser's Chrome for Testing if available
        chrome_path = '/Users/it/.agent-browser/browsers/chrome-147.0.7727.57/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'
        if not Path(chrome_path).exists():
            chrome_path = None
        
        browser = p.chromium.launch(
            headless=True,
            executable_path=chrome_path,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ],
        )
        
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        
        context.add_cookies(pw_cookies)
        page = context.new_page()
        
        # Visit the job search page
        query = sys.argv[1] if len(sys.argv) > 1 else "Python"
        city = sys.argv[2] if len(sys.argv) > 2 else "101010100"
        page_num = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        
        url = f"https://www.zhipin.com/web/geek/job?query={query}&city={city}&page={page_num}"
        print(f"[nav] {url}")
        
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(3)
        
        # Check if we hit security check
        current_url = page.url
        page_content = page.content()
        
        if "安全验证" in page_content or "verify" in current_url:
            print("[warn] Hit security check page, waiting for auto-solve...")
            time.sleep(5)
        
        # Try the API from within the page context
        print("[api] Calling job list API from browser context...")
        
        api_result = page.evaluate("""
            () => fetch('/wapi/zpgeek/search/joblist.json?scene=1&query=""" + query + """&city=""" + city + """&page=""" + str(page_num) + """&pageSize=30')
                .then(r => r.json())
        """)
        
        code = api_result.get('code')
        message = api_result.get('message', '')
        print(f"[api] Code: {code}, Message: {message}")
        
        if code == 0:
            jobs = api_result.get('zpData', {}).get('jobList', [])
            print(f"\n✅ Found {len(jobs)} jobs!\n")
            
            for i, j in enumerate(jobs[:10]):
                print(f"{i+1}. {j.get('jobName')} @ {j.get('brandName')}")
                print(f"   💰 {j.get('salaryDesc')} | 📍 {j.get('cityName')} {j.get('areaDistrict', '')}")
                print(f"   📋 {j.get('jobExperience')} | {j.get('jobDegree')}")
                print(f"   👤 {j.get('bossName')} ({j.get('bossTitle')})")
                print(f"   🔑 {j.get('encryptJobId')}")
                print()
            
            # Save full results
            output_file = f"/tmp/boss_jobs_{query}_{city}_p{page_num}.json"
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
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_jobs, f, ensure_ascii=False, indent=2)
            
            print(f"💾 Saved to {output_file}")
            
            # Output in delimiter format
            print("===JOBS_JSON_START===")
            print(json.dumps(output_jobs, ensure_ascii=False, indent=2))
            print("===JOBS_JSON_END===")
            
        elif code == 37:
            print("[warn] Code 37 - env check. Trying to auto-generate zp_stoken...")
            
            zpData = api_result.get('zpData', {})
            seed = zpData.get('seed', '')
            ts = str(zpData.get('ts', ''))
            name = zpData.get('name', '')
            
            # Navigate to security-check page to let the browser handle it
            sec_url = f"https://www.zhipin.com/web/common/security-check.html?seed={seed}&name={name}&ts={ts}&callbackUrl=%2Fweb%2Fgeek%2Fjob%3Fquery%3D{query}%26city%3D{city}%26page%3D{page_num}"
            print(f"[sec] Navigating to security-check page...")
            page.goto(sec_url, wait_until="domcontentloaded")
            time.sleep(5)
            
            # Check if redirected back
            new_url = page.url
            print(f"[sec] After security check: {new_url}")
            
            if "security-check" not in new_url:
                # Try API again
                api_result2 = page.evaluate("""
                    () => fetch('/wapi/zpgeek/search/joblist.json?scene=1&query=""" + query + """&city=""" + city + """&page=""" + str(page_num) + """&pageSize=30')
                        .then(r => r.json())
                """)
                code2 = api_result2.get('code')
                print(f"[api] Retry code: {code2}")
                
                if code2 == 0:
                    jobs = api_result2.get('zpData', {}).get('jobList', [])
                    print(f"\n✅ Found {len(jobs)} jobs after security bypass!")
                    for i, j in enumerate(jobs[:5]):
                        print(f"  {i+1}. {j.get('jobName')} @ {j.get('brandName')} - {j.get('salaryDesc')}")
                else:
                    print(f"❌ Still failed: code={code2}, msg={api_result2.get('message')}")
            else:
                print("❌ Still on security check page")
        
        elif code == 36:
            print(f"❌ Account flagged (code 36). Need manual verification.")
        
        else:
            print(f"❌ Unexpected: {json.dumps(api_result, ensure_ascii=False)[:500]}")
        
        browser.close()

if __name__ == "__main__":
    main()
