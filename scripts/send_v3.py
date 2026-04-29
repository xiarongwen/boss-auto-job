#!/usr/bin/env python3
"""Get encryptUserId and send greeting to a BOSS recruiter."""
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

    encrypt_job_id = sys.argv[1]
    greeting = sys.argv[2]

    print(f"[send] JobId: {encrypt_job_id}")
    print(f"[send] Greeting: {greeting}")

    chrome_path = '/Users/it/.agent-browser/browsers/chrome-147.0.7727.57/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, executable_path=chrome_path,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_cookies(pw_cookies)
        page = context.new_page()

        # Step 1: Visit job page to establish session
        print("[step1] Visiting job page...")
        page.goto(f"https://www.zhipin.com/job_detail/{encrypt_job_id}.html", wait_until="domcontentloaded")
        time.sleep(4)

        # Check if security check
        content = page.content()
        current_url = page.url
        print(f"[check] URL: {current_url}")

        if "安全验证" in content or "security-check" in current_url:
            print("[info] Security check triggered. Waiting for auto-solve...")
            # The security-check page loads JS that generates zp_stoken and redirects
            time.sleep(8)
            current_url = page.url
            print(f"[check] After wait: {current_url}")

        # Step 2: Try to get job detail from the page's __INITIAL_STATE__
        print("[step2] Extracting job detail from page...")
        page_data = page.evaluate("""() => {
            // Try to get from __INITIAL_STATE__
            try {
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    if (s.textContent.includes('__INITIAL_STATE__')) {
                        const match = s.textContent.match(/window\\.__INITIAL_STATE__\\s*=\\s*({.+?});/);
                        if (match) {
                            const data = JSON.parse(match[1]);
                            // Look for encryptUserId in various places
                            const jobIdData = data.jobInfo || data.jobDetail || data;
                            return {
                                found: true,
                                data: JSON.stringify(jobIdData).substring(0, 3000)
                            };
                        }
                    }
                }
            } catch(e) {}

            // Try API from page context
            return fetch('/wapi/zpgeek/job/detail.json?encryptJobId=""" + encrypt_job_id + """')
                .then(r => r.json())
                .then(d => ({api: true, code: d.code, data: d.zpData ? JSON.stringify(d.zpData).substring(0, 2000) : null, msg: d.message}))
                .catch(e => ({api: true, error: e.message}));
        }""")

        print(f"[step2] Result: {json.dumps(page_data, ensure_ascii=False)[:500]}")

        # Step 3: Try direct friend/add API (doesn't always need encryptUserId)
        print("[step3] Trying direct friend/add API...")

        # The friend/add endpoint can work with just encryptJobId
        send_result = page.evaluate(f"""() => {{
            return fetch('/wapi/zpgeek/friend/add.json', {{
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
            .then(d => d)
            .catch(e => ({{error: e.message}}));
        }}""")

        print(f"[step3] Result: {json.dumps(send_result, ensure_ascii=False)}")

        if send_result.get('code') == 0:
            print(f"\n✅ 消息发送成功！")
            zpData = send_result.get('zpData', {})
            if zpData:
                print(f"   详情: {json.dumps(zpData, ensure_ascii=False)[:200]}")
        else:
            print(f"\n❌ 发送失败 (code={send_result.get('code')}): {send_result.get('message')}")

            # Try with encryptUserId if available
            if 'encryptUserId' not in str(send_result) and not send_result.get('zpData'):
                print("[step4] Trying job card API for encryptUserId...")
                card_result = page.evaluate(f"""() => {{
                    return fetch('/wapi/zpgeek/job/card.json?encryptJobId={encrypt_job_id}')
                        .then(r => r.json())
                        .then(d => d)
                        .catch(e => ({{error: e.message}}));
                }}""")
                print(f"[step4] Card: {json.dumps(card_result, ensure_ascii=False)[:500]}")

                if card_result.get('code') == 0:
                    boss_id = card_result.get('zpData', {}).get('encryptUserId', '')
                    if boss_id:
                        print(f"[step4] Found encryptUserId: {boss_id}")
                        # Retry with boss_id
                        send_result2 = page.evaluate(f"""() => {{
                            return fetch('/wapi/zpgeek/friend/add.json', {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json',
                                    'X-Requested-With': 'XMLHttpRequest',
                                }},
                                body: JSON.stringify({{
                                    encryptJobId: '{encrypt_job_id}',
                                    encryptBossId: '{boss_id}',
                                    greeting: '{greeting}',
                                }})
                            }})
                            .then(r => r.json())
                            .catch(e => ({{error: e.message}}));
                        }}""")
                        print(f"[step4] Retry result: {json.dumps(send_result2, ensure_ascii=False)}")
                        if send_result2.get('code') == 0:
                            print(f"\n✅ 消息发送成功！(with encryptBossId)")

        # Update cookies
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
