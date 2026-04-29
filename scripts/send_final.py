#!/usr/bin/env python3
"""Send greeting using search page context (which we know works)."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

AUTH_FILE = Path.home() / '.agent-browser/auth/boss-zhipin.json'
CHROME_PATH = '/Users/it/.agent-browser/browsers/chrome-147.0.7727.57/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'

def main():
    encrypt_job_id = sys.argv[1]
    greeting = sys.argv[2]

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

    print(f"[send] JobId: {encrypt_job_id}")
    print(f"[send] Greeting: {greeting}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, executable_path=CHROME_PATH,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_cookies(pw_cookies)
        page = context.new_page()

        # Use search page to establish context (proven to work)
        print("[step1] Establishing search context...")
        page.goto("https://www.zhipin.com/web/geek/job?query=产品经理&city=101010100&page=1", wait_until="networkidle", timeout=30000)
        time.sleep(3)
        print(f"[step1] URL: {page.url}")
        
        # Verify search works
        search_test = page.evaluate("""() => {
            return fetch('https://www.zhipin.com/wapi/zpgeek/search/joblist.json?scene=1&query=产品经理&city=101010100&page=1&pageSize=5')
                .then(r => r.json())
                .then(d => ({code: d.code, count: d.zpData?.jobList?.length || 0}))
                .catch(e => ({error: e.message}));
        }""")
        print(f"[step1] Search API: {json.dumps(search_test)}")
        
        if search_test.get('code') != 0:
            print("❌ Search API not working, aborting")
            browser.close()
            return
        
        # Step 2: Get encryptUserId via job card API
        print("\n[step2] Getting job card...")
        card = page.evaluate(f"""() => {{
            return fetch('https://www.zhipin.com/wapi/zpgeek/job/card.json?encryptJobId={encrypt_job_id}')
                .then(r => r.json())
                .catch(e => ({{error: e.message}}));
        }}""")
        print(f"[step2] Card code: {card.get('code')}, msg: {card.get('message', '')}")
        
        encrypt_boss_id = ''
        if card.get('code') == 0:
            zpData = card.get('zpData', {})
            encrypt_boss_id = zpData.get('encryptUserId', '')
            print(f"[step2] BossId: {encrypt_boss_id}")
            print(f"[step2] Job: {zpData.get('jobName', '')} @ {zpData.get('brandName', '')}")
            print(f"[step2] Boss: {zpData.get('bossName', '')} ({zpData.get('bossTitle', '')})")
        else:
            # Try detail API
            print("[step2] Trying detail API...")
            detail = page.evaluate(f"""() => {{
                return fetch('https://www.zhipin.com/wapi/zpgeek/job/detail.json?encryptJobId={encrypt_job_id}')
                    .then(r => r.json())
                    .catch(e => ({{error: e.message}}));
            }}""")
            print(f"[step2] Detail code: {detail.get('code')}, msg: {detail.get('message', '')}")
            if detail.get('code') == 0:
                encrypt_boss_id = detail.get('zpData', {}).get('encryptUserId', '')
                print(f"[step2] BossId from detail: {encrypt_boss_id}")

        if not encrypt_boss_id:
            # Last resort: try friend/add without bossId (some endpoints accept just jobId)
            print("\n[step3] No bossId. Trying friend/add with just jobId...")
            result = page.evaluate(f"""() => {{
                return fetch('https://www.zhipin.com/wapi/zpgeek/friend/add.json', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    }},
                    body: JSON.stringify({{
                        encryptJobId: '{encrypt_job_id}',
                        greeting: '{greeting}',
                    }})
                }})
                .then(r => r.json())
                .catch(e => ({{error: e.message}}));
            }}""")
            print(f"[step3] Result: {json.dumps(result, ensure_ascii=False)[:500]}")
            
            if result.get('code') == 0:
                print(f"\n✅ 消息发送成功！（仅用 jobId）")
            else:
                print(f"\n❌ 发送失败: {result.get('message', result.get('error', ''))}")
                print("   需要先在浏览器中手动访问该职位页面获取 bossId")
        else:
            # Send with bossId
            print(f"\n[step3] Sending to boss {encrypt_boss_id}...")
            result = page.evaluate(f"""() => {{
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
            print(f"[step3] Result: {json.dumps(result, ensure_ascii=False)[:500]}")
            
            if result.get('code') == 0:
                print(f"\n✅ 消息发送成功！")
            else:
                print(f"\n❌ 发送失败: {result.get('message', result.get('error', ''))}")

        # Save cookies
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
        print(f"\n[save] Updated {len(export)} cookies")
        
        browser.close()

if __name__ == "__main__":
    main()
