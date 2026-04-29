#!/usr/bin/env python3
"""Send greeting to a BOSS recruiter - fixed version."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

AUTH_FILE = Path.home() / '.agent-browser/auth/boss-zhipin.json'
CHROME_PATH = '/Users/it/.agent-browser/browsers/chrome-147.0.7727.57/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'

def load_cookies():
    with open(AUTH_FILE) as f:
        auth = json.load(f)
    pw_cookies = []
    for c in auth.get('cookies', []):
        cookie = {"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c.get("path", "/")}
        expires = c.get("expires", -1)
        if expires and expires > 0:
            cookie["expires"] = expires
        if c.get("httpOnly"):
            cookie["httpOnly"] = True
        if c.get("secure"):
            cookie["secure"] = True
        pw_cookies.append(cookie)
    return pw_cookies

def save_cookies(context):
    all_cookies = context.cookies()
    export = []
    for c in all_cookies:
        export.append({
            "name": c["name"], "value": c["value"], "domain": c["domain"],
            "path": c.get("path", "/"), "expires": c.get("expires", -1),
            "size": len(c.get("value", "")), "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False), "session": c.get("expires", -1) == -1,
        })
    with open(AUTH_FILE, 'w') as f:
        json.dump({"cookies": export, "origins": []}, f, indent=2)
    print(f"[save] Updated {len(export)} cookies")

def main():
    encrypt_job_id = sys.argv[1]
    greeting = sys.argv[2]
    
    print(f"[send] JobId: {encrypt_job_id}")
    print(f"[send] Greeting: {greeting}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, executable_path=CHROME_PATH,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_cookies(load_cookies())
        page = context.new_page()

        # Step 1: Establish session on zhipin.com
        print("[step1] Establishing session on zhipin.com...")
        page.goto("https://www.zhipin.com/", wait_until="networkidle", timeout=30000)
        time.sleep(3)
        
        current_url = page.url
        print(f"[step1] URL: {current_url}")
        print(f"[step1] Title: {page.title()}")
        
        # Navigate to search page (we know this triggers the API correctly)
        page.goto("https://www.zhipin.com/web/geek/job?query=产品经理&city=101010100&page=1", wait_until="networkidle", timeout=30000)
        time.sleep(3)
        print(f"[step1] Search URL: {page.url}")
        
        # Step 2: Get encryptUserId via job card API (from within the zhipin page context)
        print("[step2] Getting job card info...")
        card_result = page.evaluate(f"""() => {{
            return fetch('https://www.zhipin.com/wapi/zpgeek/job/card.json?encryptJobId={encrypt_job_id}')
                .then(r => r.json())
                .catch(e => ({{error: e.message}}));
        }}""")
        
        code = card_result.get('code')
        print(f"[step2] Code: {code}")
        
        encrypt_boss_id = ''
        job_name = ''
        brand_name = ''
        
        if code == 0:
            zpData = card_result.get('zpData', {})
            encrypt_boss_id = zpData.get('encryptUserId', '')
            job_name = zpData.get('jobName', '')
            brand_name = zpData.get('brandName', '')
            print(f"[step2] Job: {job_name} @ {brand_name}")
            print(f"[step2] BossId: {encrypt_boss_id}")
        else:
            print(f"[step2] Card failed: {card_result.get('message', card_result.get('error', 'unknown'))}")
            # Try job detail API
            print("[step2] Trying job detail API...")
            detail = page.evaluate(f"""() => {{
                return fetch('https://www.zhipin.com/wapi/zpgeek/job/detail.json?encryptJobId={encrypt_job_id}')
                    .then(r => r.json())
                    .catch(e => ({{error: e.message}}));
            }}""")
            print(f"[step2] Detail code: {detail.get('code')}, msg: {detail.get('message', detail.get('error', ''))}")
            if detail.get('code') == 0:
                encrypt_boss_id = detail.get('zpData', {}).get('encryptUserId', '')
                job_name = detail.get('zpData', {}).get('jobName', '')
                print(f"[step2] BossId from detail: {encrypt_boss_id}")

        if not encrypt_boss_id:
            print("[step2] No encryptBossId. Trying to navigate to job page...")
            # Navigate to the job detail page
            page.goto(f"https://www.zhipin.com/job_detail/{encrypt_job_id}.html", wait_until="domcontentloaded", timeout=15000)
            time.sleep(5)
            
            new_url = page.url
            print(f"[step2] After nav: {new_url}")
            
            if "security-check" not in new_url and "verify" not in new_url:
                # Extract from page
                page_info = page.evaluate("""() => {
                    try {
                        const scripts = document.querySelectorAll('script');
                        for (const s of scripts) {
                            if (s.textContent.includes('__INITIAL_STATE__')) {
                                const match = s.textContent.match(/window\\.__INITIAL_STATE__\\s*=\\s*({.+?});/);
                                if (match) {
                                    const data = JSON.parse(match[1]);
                                    // Look for encryptUserId in various keys
                                    const search = (obj, depth) => {
                                        if (depth > 3) return null;
                                        if (typeof obj !== 'object' || obj === null) return null;
                                        for (const [k, v] of Object.entries(obj)) {
                                            if (k === 'encryptUserId' && v) return v;
                                            if (k === 'encryptBossId' && v) return v;
                                            const found = search(v, depth + 1);
                                            if (found) return found;
                                        }
                                        return null;
                                    };
                                    return {userId: search(data, 0), raw: JSON.stringify(data).substring(0, 500)};
                                }
                            }
                        }
                    } catch(e) {}
                    return {userId: null, url: window.location.href};
                }""")
                print(f"[step2] Page info: {json.dumps(page_info, ensure_ascii=False)[:500]}")
                encrypt_boss_id = page_info.get('userId') or ''
            else:
                print("[step2] Hit security/verify page, can't navigate")

        # Step 3: Send the greeting
        if encrypt_boss_id:
            print(f"\n[step3] Sending message to boss {encrypt_boss_id}...")
            
            send_result = page.evaluate(f"""() => {{
                return fetch('https://www.zhipin.com/wapi/zpgeek/friend/add.json', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    }},
                    body: JSON.stringify({{
                        encryptJobId: '{encrypt_job_id}',
                        encryptBossId: '{encrypt_boss_id}',
                        greeting: '{greeting}',
                    }})
                }})
                .then(r => r.json())
                .catch(e => ({{error: e.message}}));
            }}""")
            
            send_code = send_result.get('code')
            print(f"[step3] Code: {send_code}")
            print(f"[step3] Result: {json.dumps(send_result, ensure_ascii=False)[:500]}")
            
            if send_code == 0:
                print(f"\n✅ 消息发送成功！")
                print(f"   职位: {job_name}")
                print(f"   公司: {brand_name}")
                print(f"   招呼语: {greeting}")
            else:
                print(f"\n❌ 发送失败: {send_result.get('message', send_result.get('error', 'unknown'))}")
        else:
            print("\n❌ 无法获取 encryptBossId，发送失败")
            print("   可能需要用户在浏览器中手动打开职位页面并发送消息")

        save_cookies(context)
        browser.close()

if __name__ == "__main__":
    main()
