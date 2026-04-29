#!/usr/bin/env python3
"""
BOSS Zhipin Cookie Refresh Tool - Opens YOUR browser, loads cookies,
waits for verification, then saves updated cookies.
"""
import json, sys, time
from pathlib import Path

AUTH_FILE = Path.home() / '.agent-browser/auth/boss-zhipin.json'
BACKUP_FILE = Path.home() / '.agent-browser/auth/boss-zhipin.backup.json'
CHROME_PATH = '/Users/it/.agent-browser/browsers/chrome-147.0.7727.57/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'

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

    print(f"[init] Loaded {len(pw_cookies)} cookies")
    print("[init] Opening visible browser window...")
    print()

    with sync_playwright() as p:
        chrome_path = CHROME_PATH if Path(CHROME_PATH).exists() else None

        browser = p.chromium.launch(
            headless=False,  # VISIBLE browser
            executable_path=chrome_path,
            args=['--disable-blink-features=AutomationControlled']
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        context.add_cookies(pw_cookies)
        page = context.new_page()

        # Navigate to BOSS search
        print("[nav] Navigating to BOSS Zhipin...")
        page.goto("https://www.zhipin.com/web/geek/job?query=产品经理&city=101010100&page=1", wait_until="domcontentloaded")
        time.sleep(3)

        # Check state
        content = page.content()
        current_url = page.url
        print(f"[check] URL: {current_url[:100]}")

        needs_verify = "安全验证" in content or "verify" in current_url
        is_logged_in = "夏荣文" in content

        if is_logged_in and not needs_verify:
            print("[check] ✅ Already logged in, no verification needed!")
        else:
            print()
            print("=" * 60)
            print("  ⚠️  请在弹出的浏览器窗口中完成安全验证！")
            print("  验证完成后脚本会自动检测并保存 Cookie")
            print("  超时: 5 分钟")
            print("=" * 60)
            print()

            start = time.time()
            while time.time() - start < 300:
                time.sleep(3)
                try:
                    cur = page.url
                    txt = page.content()
                    elapsed = int(time.time() - start)

                    if "夏荣文" in txt or ("job" in cur and "verify" not in cur and "security" not in cur):
                        print(f"\n[check] ✅ Verification complete! ({elapsed}s)")
                        break

                    sys.stdout.write(f"\r[wait] Waiting for verification... ({elapsed}s)")
                    sys.stdout.flush()
                except:
                    pass
            else:
                print("\n[timeout] 5 min timeout. Please try again.")

        # Wait a bit for cookies to settle
        time.sleep(2)

        # Extract and save cookies
        all_cookies = context.cookies()
        export = []
        for c in all_cookies:
            export.append({
                "name": c["name"], "value": c["value"], "domain": c["domain"],
                "path": c.get("path", "/"), "expires": c.get("expires", -1),
                "size": len(c.get("value", "")), "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False), "session": c.get("expires", -1) == -1,
            })

        # Backup
        if AUTH_FILE.exists():
            import shutil
            shutil.copy(AUTH_FILE, BACKUP_FILE)

        with open(AUTH_FILE, 'w') as f:
            json.dump({"cookies": export, "origins": []}, f, indent=2)
        print(f"\n[save] Saved {len(export)} cookies to {AUTH_FILE}")

        # Validate
        print("[validate] Testing API...")
        try:
            result = page.evaluate("""() =>
                fetch('/wapi/zpgeek/search/joblist.json?scene=1&query=产品经理&city=101010100&page=1&pageSize=5')
                .then(r => r.json())
                .then(d => ({code: d.code, msg: d.message, jobs: d.zpData?.jobList?.length || 0}))
            """)
            print(f"[validate] {json.dumps(result, ensure_ascii=False)}")
            if result.get('code') == 0:
                print(f"\n✅ SUCCESS! API returned {result.get('jobs')} jobs. Cookies are valid!")
        except Exception as e:
            print(f"[validate] Error: {e}")

        time.sleep(3)
        browser.close()

    print("\n[done] Cookie refresh complete!")

if __name__ == "__main__":
    main()
