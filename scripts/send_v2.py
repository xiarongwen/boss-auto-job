#!/usr/bin/env python3
"""Get job detail and send message via Playwright."""
import json, sys, time
from pathlib import Path

AUTH_FILE = Path.home() / '.agent-browser/auth/boss-zhipin.json'

def main():
    from playwright.sync_api import sync_playwright

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

    encrypt_job_id = sys.argv[1] if len(sys.argv) > 1 else "853dc15346f31d2f0nV72tS5GFJW"
    message = sys.argv[2] if len(sys.argv) > 2 else "您好！我有5年产品经验，精通Python和SQL，对贵司Python岗位很感兴趣，期望进一步沟通，谢谢！"

    chrome_path = '/Users/it/.agent-browser/browsers/chrome-147.0.7727.57/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=chrome_path, args=['--disable-blink-features=AutomationControlled', '--no-sandbox'])
        context = browser.new_context(viewport={"width": 1280, "height": 800}, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        context.add_cookies(pw_cookies)
        page = context.new_page()

        # Step 1: Get job detail via API to find encryptUserId
        print(f"[step1] Getting job detail for {encrypt_job_id}...")
        detail_url = f"https://www.zhipin.com/wapi/zpgeek/job/card.json?encryptJobId={encrypt_job_id}"
        
        # First visit a page to establish context
        page.goto("https://www.zhipin.com/web/geek/job?query=Python&city=101010100", wait_until="domcontentloaded")
        time.sleep(3)
        
        # Call job detail API
        detail_result = page.evaluate(f"""
            () => fetch('/wapi/zpgeek/job/card.json?encryptJobId={encrypt_job_id}')
                .then(r => r.json())
        """)
        
        print(f"[api] Job detail code: {detail_result.get('code')}")
        
        encrypt_user_id = ''
        if detail_result.get('code') == 0:
            zpData = detail_result.get('zpData', {})
            encrypt_user_id = zpData.get('encryptUserId', '')
            boss_name = zpData.get('bossName', '')
            boss_title = zpData.get('bossTitle', '')
            job_name = zpData.get('jobName', '')
            brand_name = zpData.get('brandName', '')
            print(f"[detail] Job: {job_name} @ {brand_name}")
            print(f"[detail] Boss: {boss_name} ({boss_title})")
            print(f"[detail] encryptUserId: {encrypt_user_id}")
        
        if not encrypt_user_id:
            # Try alternative API
            print("[alt] Trying job detail page API...")
            alt_result = page.evaluate(f"""
                () => fetch('/wapi/zpgeek/job/detail.json?encryptJobId={encrypt_job_id}')
                    .then(r => r.json())
            """)
            print(f"[alt] Code: {alt_result.get('code')}")
            if alt_result.get('code') == 0:
                zpData = alt_result.get('zpData', {})
                encrypt_user_id = zpData.get('encryptUserId', '')
                print(f"[alt] encryptUserId: {encrypt_user_id}")
        
        if not encrypt_user_id:
            print("[warn] Could not get encryptUserId. Trying direct page navigation...")
            # Navigate to job detail page
            page.goto(f"https://www.zhipin.com/job_detail/{encrypt_job_id}.html", wait_until="domcontentloaded")
            time.sleep(3)
            
            # Extract from page
            page_data = page.evaluate("""
                () => {
                    // Try __INITIAL_STATE__
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        if (s.textContent.includes('__INITIAL_STATE__')) {
                            try {
                                const match = s.textContent.match(/window\\.__INITIAL_STATE__\\s*=\\s*({.+?});/);
                                if (match) {
                                    const data = JSON.parse(match[1]);
                                    return {fromState: true, data: JSON.stringify(data).substring(0, 2000)};
                                }
                            } catch(e) {}
                        }
                    }
                    return {fromState: false, url: window.location.href, title: document.title};
                }
            """)
            print(f"[page] {json.dumps(page_data, ensure_ascii=False)[:500]}")
        
        if encrypt_user_id:
            # Step 2: Send greeting message
            print(f"\n[step2] Sending message to {encrypt_user_id}...")
            
            send_result = page.evaluate(f"""
                () => fetch('/wapi/zpgeek/friend/add.json', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    }},
                    body: JSON.stringify({{
                        encryptJobId: '{encrypt_job_id}',
                        encryptBossId: '{encrypt_user_id}',
                        greeting: '{message}',
                    }})
                }}).then(r => r.json())
            """)
            
            print(f"[send] Result: {json.dumps(send_result, ensure_ascii=False)}")
            
            if send_result.get('code') == 0:
                print(f"\n✅ 消息发送成功！")
            else:
                print(f"\n❌ 发送失败: {send_result.get('message')}")
        
        # Save updated cookies
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
