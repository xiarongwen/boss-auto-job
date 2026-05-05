#!/usr/bin/env python3
"""
BOSS Zhipin Send Message - Camoufox Mode

Send greeting message to a recruiter using Camoufox stealth browser.

Usage:
  python send_camoufox.py <encrypt_job_id> "你好，我对这个职位很感兴趣"
  python send_camoufox.py 8dfbfbf75af172d10nd82tq-EVtZ --auto  # Auto-generate greeting
"""

import argparse
import json
import sys
import time
from pathlib import Path

AUTH_FILE = Path.home() / '.agent-browser' / 'auth' / 'boss-zhipin.json'


def load_cookies() -> list:
    if not AUTH_FILE.exists():
        return []
    with open(AUTH_FILE) as f:
        auth = json.load(f)
    pw_cookies = []
    for c in auth.get('cookies', []):
        cookie = {
            "name": c["name"], "value": c["value"],
            "domain": c["domain"], "path": c.get("path", "/"),
        }
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
    """Export updated cookies back to auth file."""
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
        backup = AUTH_FILE.parent / (AUTH_FILE.stem + '.backup.json')
        shutil.copy(AUTH_FILE, backup)
    with open(AUTH_FILE, 'w') as f:
        json.dump({"cookies": export, "origins": []}, f, indent=2)
    print(f"[save] Updated {len(export)} cookies")


def is_logged_in(cookies: list) -> bool:
    """Check if cookies contain login session markers."""
    names = {c["name"] for c in cookies}
    # wt2 and __a are session markers for logged-in state
    return "wt2" in names and "__a" in names


def do_login(page, timeout: int = 120) -> bool:
    """Open BOSS login page and wait for user to scan QR code."""
    print("\n" + "="*60)
    print("🔐 未登录或登录已过期，需要重新扫码登录")
    print("="*60)
    print("[login] 正在打开 BOSS 直聘登录页...")
    print("[login] 请用手机 BOSS App 扫描页面上的二维码")
    print(f"[login] 等待登录中... (超时: {timeout}秒)")
    print("="*60 + "\n")

    page.goto("https://www.zhipin.com/web/user/?ka=header-login", wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # Wait for login success: URL changes away from login page
    start = time.time()
    while time.time() - start < timeout:
        current = page.url
        if "login" not in current and "user" not in current:
            print("[login] ✅ 登录成功！检测到页面跳转")
            return True
        # Also check for logged-in cookies
        cookies = page.context.cookies()
        if is_logged_in(cookies):
            print("[login] ✅ 登录成功！检测到登录 Cookie")
            return True
        time.sleep(2)

    print("[login] ❌ 登录超时，请重新运行命令")
    return False


def try_send_message(page, job_id: str, boss_id: str, greeting: str, use_boss_id: bool = True) -> dict:
    """Attempt to send greeting message via page.evaluate fetch."""
    _job_id = json.dumps(job_id)
    _greeting = json.dumps(greeting)
    
    if use_boss_id:
        _boss_id = json.dumps(boss_id)
        result = page.evaluate(f"""() =>
            fetch('/wapi/zpgeek/friend/add.json', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}},
                body: JSON.stringify({{
                    encryptJobId: {_job_id},
                    encryptBossId: {_boss_id},
                    greeting: {_greeting}
                }})
            }}).then(r => r.json()).catch(e => ({{error: e.message}}))
        """)
    else:
        result = page.evaluate(f"""() =>
            fetch('/wapi/zpgeek/friend/add.json', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}},
                body: JSON.stringify({{encryptJobId: {_job_id}, greeting: {_greeting}}})
            }}).then(r => r.json()).catch(e => ({{error: e.message}}))
        """)
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Send message to BOSS recruiter")
    parser.add_argument("job_id", help="encryptJobId of the target job")
    parser.add_argument("greeting", nargs="?", help="Greeting message to send")
    parser.add_argument("--auto", action="store_true", help="Auto-generate greeting (requires resume)")
    args = parser.parse_args()

    greeting = args.greeting
    if args.auto:
        resume_path = Path.home() / '.hermes' / 'credentials' / 'resume.txt'
        if not resume_path.exists():
            print("[auto] ❌ No resume found at ~/.hermes/credentials/resume.txt")
            sys.exit(1)
        resume = resume_path.read_text().strip()
        greeting = f"您好！{resume[:50]}对贵司这个岗位很感兴趣，方便进一步沟通吗？"
        print(f"[auto] Using fallback greeting: {greeting}")
        print("[auto] ⚠️ Recommend: agent should generate personalized greeting and pass it directly")

    if not greeting:
        print("[error] No greeting provided. Use: python send_camoufox.py <job_id> \"your message\"")
        sys.exit(1)

    print(f"[send] Job: {args.job_id}")
    print(f"[send] Greeting: {greeting}")

    from camoufox.sync_api import Camoufox

    with Camoufox(humanize=True, geoip=True, os="macos", block_images=False) as browser:
        page = browser.new_page()

        # Check if we have valid login cookies
        cookies = load_cookies()
        logged_in = is_logged_in(cookies) if cookies else False
        print(f"[send] Cookie login state: {'logged in' if logged_in else 'not logged in'}")

        if cookies:
            page.context.add_cookies(cookies)
            print(f"[send] Loaded {len(cookies)} cookies")

        # Step 1: Visit search page to establish context
        print("[step1] Establishing session...")
        page.goto("https://www.zhipin.com/web/geek/job?query=Python&city=101010100&page=1",
                   wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Step 2: Get encryptUserId from job card API
        print("[step2] Getting job card info...")
        try:
            resp = page.request.get(
                f"https://www.zhipin.com/wapi/zpgeek/job/card.json?encryptJobId={args.job_id}",
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            card = resp.json()
        except Exception as e:
            card = {"code": -1, "error": str(e)}

        code = card.get('code')
        print(f"[step2] Card code: {code}")

        # Handle Code 17: not logged in
        if code == 17:
            print("[step2] Code 17: Authentication required")
            if do_login(page):
                # Save new cookies
                save_cookies(page.context)
                # Retry getting card info
                print("[step2] Retrying job card after login...")
                try:
                    resp = page.request.get(
                        f"https://www.zhipin.com/wapi/zpgeek/job/card.json?encryptJobId={args.job_id}",
                        headers={"X-Requested-With": "XMLHttpRequest"}
                    )
                    card = resp.json()
                    code = card.get('code')
                    print(f"[step2] Retry card code: {code}")
                except Exception as e:
                    print(f"[step2] Retry failed: {e}")
                    card = {"code": -1}
            else:
                print("[send] ❌ Login failed, cannot proceed")
                sys.exit(1)

        encrypt_boss_id = ''
        if code == 0:
            zpData = card.get('zpData', {})
            encrypt_boss_id = zpData.get('encryptUserId', '')
            print(f"[step2] Job: {zpData.get('jobName')} @ {zpData.get('brandName')}")
            print(f"[step2] Boss: {zpData.get('bossName')} ({zpData.get('bossTitle')})")
            print(f"[step2] BossId: {encrypt_boss_id}")
        else:
            msg = card.get('message', card.get('error', ''))
            print(f"[step2] ❌ Card failed: {msg}")

            # Try job detail API
            print("[step2] Trying job detail API...")
            try:
                resp = page.request.get(
                    f"https://www.zhipin.com/wapi/zpgeek/job/detail.json?encryptJobId={args.job_id}",
                    headers={"X-Requested-With": "XMLHttpRequest"}
                )
                detail = resp.json()
            except Exception as e:
                detail = {"code": -1, "error": str(e)}
            print(f"[step2] Detail code: {detail.get('code')}")
            if detail.get('code') == 0:
                encrypt_boss_id = detail.get('zpData', {}).get('encryptUserId', '')
                print(f"[step2] BossId from detail: {encrypt_boss_id}")

        if not encrypt_boss_id:
            # Try navigating to job page
            print("[step2] Trying direct page navigation...")
            page.goto(f"https://www.zhipin.com/job_detail/{args.job_id}.html",
                      wait_until="networkidle", timeout=20000)
            time.sleep(5)

            page_info = page.evaluate("""() => {
                try {
                    for (const s of document.querySelectorAll('script')) {
                        if (s.textContent.includes('INITIAL_STATE')) {
                            const m = s.textContent.match(/window\\.__INITIAL_STATE__\\s*=\\s*({.+?});/);
                            if (m) {
                                const d = JSON.parse(m[1]);
                                const find = (o, depth) => {
                                    if (depth > 4 || typeof o !== 'object' || !o) return null;
                                    for (const [k, v] of Object.entries(o)) {
                                        if ((k === 'encryptUserId' || k === 'encryptBossId') && typeof v === 'string' && v.length > 5) return v;
                                        const f = find(v, depth + 1);
                                        if (f) return f;
                                    }
                                    return null;
                                };
                                return {userId: find(d, 0)};
                            }
                        }
                    }
                } catch(e) {}
                return {userId: null, url: window.location.href};
            }""")
            encrypt_boss_id = page_info.get('userId') or ''
            if encrypt_boss_id:
                print(f"[step2] Found BossId from page: {encrypt_boss_id}")
            else:
                print(f"[step2] ❌ Could not find BossId. URL: {page_info.get('url', '')[:100]}")

        if not encrypt_boss_id:
            # Last resort: try without bossId
            print("[step2] Trying friend/add without bossId...")
            result = try_send_message(page, args.job_id, '', greeting, use_boss_id=False)
            print(f"[send] Result: {json.dumps(result, ensure_ascii=False)[:300]}")
            if result.get('code') == 0:
                print(f"\n✅ 消息发送成功！（仅用 jobId）")
            else:
                print(f"\n❌ 发送失败: {result.get('message', result.get('error', ''))}")
            save_cookies(page.context)
            return

        # Step 3: Send message
        print(f"\n[step3] Sending to boss {encrypt_boss_id}...")
        
        # Humanize: simulate reading JD before sending
        read_time = 3 + (len(greeting) // 20) * 2
        print(f"[step3] Simulating JD reading ({read_time}s)...")
        time.sleep(read_time)

        result = try_send_message(page, args.job_id, encrypt_boss_id, greeting, use_boss_id=True)

        send_code = result.get('code')
        print(f"[step3] Code: {send_code}")
        print(f"[step3] Result: {json.dumps(result, ensure_ascii=False)[:300]}")

        if send_code == 0:
            print(f"\n✅ 消息发送成功！")
        elif send_code == 17:
            print("[step3] Code 17: Session expired during send, need re-login")
            if do_login(page):
                save_cookies(page.context)
                print("[step3] Retrying send after re-login...")
                result = try_send_message(page, args.job_id, encrypt_boss_id, greeting, use_boss_id=True)
                send_code = result.get('code')
                print(f"[step3] Retry code: {send_code}")
                if send_code == 0:
                    print(f"\n✅ 消息发送成功！")
                else:
                    print(f"\n❌ 发送失败: {result.get('message', result.get('error', ''))}")
            else:
                print("\n❌ 登录失败，无法发送")
        else:
            print(f"\n❌ 发送失败: {result.get('message', result.get('error', ''))}")

        # Save updated cookies
        save_cookies(page.context)


if __name__ == "__main__":
    main()
