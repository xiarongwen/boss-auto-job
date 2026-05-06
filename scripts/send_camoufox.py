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

    # Wait for login success: check cookies every 2 seconds
    start = time.time()
    last_cookie_count = 0
    while time.time() - start < timeout:
        # Check URL first - if redirected away from login page, likely success
        current = page.url
        if "login" not in current and "user" not in current and "zhipin.com" in current:
            print(f"[login] ✅ URL 已跳转: {current[:80]}")
            return True
        
        # Show progress if cookie count changes
        cookies = page.context.cookies()
        if len(cookies) != last_cookie_count:
            last_cookie_count = len(cookies)
            print(f"[login] 等待中... (cookies: {last_cookie_count})")
            
        time.sleep(2)

    print("[login] ❌ 登录超时，请重新运行命令")
    return False


def ensure_logged_in(page, job_id: str) -> bool:
    """Test if we're actually logged in by calling an API that requires auth.
    If not, trigger QR code login."""
    _jid = json.dumps(job_id)
    try:
        test = page.evaluate(f"""() =>
            fetch('/wapi/zpgeek/job/card.json?encryptJobId=' + {_jid}, {{
                credentials: 'include',
                headers: {{'X-Requested-With': 'XMLHttpRequest'}}
            }})
                .then(r => r.json())
                .catch(e => ({{error: e.message}}))
        """)
        code = test.get('code')
        if code == 0:
            print("[auth] ✅ API test passed, already logged in")
            return True
        elif code == 17:
            print("[auth] ❌ API test failed (Code 17), need login")
        else:
            print(f"[auth] ⚠️ API test returned code {code}: {test.get('message', '')}")
    except Exception as e:
        print(f"[auth] ⚠️ API test error: {e}")
    
    # Need login
    if do_login(page):
        save_cookies(page.context)
        # Verify login worked
        try:
            retry = page.evaluate(f"""() =>
                fetch('/wapi/zpgeek/job/card.json?encryptJobId=' + {_jid}, {{
                    credentials: 'include',
                    headers: {{'X-Requested-With': 'XMLHttpRequest'}}
                }})
                    .then(r => r.json())
                    .catch(e => ({{error: e.message}}))
            """)
            if retry.get('code') == 0:
                print("[auth] ✅ Login verified, API now accessible")
                return True
            else:
                print(f"[auth] ❌ Login verification failed: code={retry.get('code')}")
                return False
        except Exception as e:
            print(f"[auth] ❌ Login verification error: {e}")
            return False
    return False


def send_message_by_click(page, job_id: str, greeting: str) -> dict:
    """Send greeting by simulating real user click on '立即沟通' button.
    
    CRITICAL: BOSS has anti-bot detection. Must use Playwright's real click()
    instead of evaluate() btn.click(), or the click won't register.
    """
    print(f"[click] Navigating to job detail page...")
    page.goto(f"https://www.zhipin.com/job_detail/{job_id}.html",
              wait_until="networkidle", timeout=30000)
    time.sleep(5)
    
    # Check current button state
    button_state = page.evaluate("""
        () => {
            const all = Array.from(document.querySelectorAll('*'));
            const liji = all.filter(el => el.textContent.trim() === '立即沟通');
            const jixu = all.filter(el => el.textContent.trim() === '继续沟通');
            return {
                state: jixu.length > 0 ? '继续沟通' : (liji.length > 0 ? '立即沟通' : 'not_found'),
                lijiCount: liji.length,
                jixuCount: jixu.length
            };
        }
    """)
    print(f"[click] Button state: {button_state['state']} (立即沟通={button_state['lijiCount']}, 继续沟通={button_state['jixuCount']})")
    
    if button_state['state'] == '继续沟通':
        print("[click] Already chatted with this recruiter")
        return {"success": True, "message": "Already chatted"}
    
    if button_state['state'] == 'not_found':
        return {"success": False, "error": "Chat button not found"}
    
    # Click using Playwright's real mouse (anti-bot requires this)
    print("[click] Clicking '立即沟通' with real mouse...")
    try:
        page.locator("text=立即沟通").first.click(timeout=5000)
        print("[click] Click executed")
    except Exception as e:
        return {"success": False, "error": f"Click failed: {e}"}
    
    time.sleep(5)
    
    # Check result
    final_state = page.evaluate("""
        () => {
            const all = Array.from(document.querySelectorAll('*'));
            const liji = all.filter(el => el.textContent.trim() === '立即沟通');
            const jixu = all.filter(el => el.textContent.trim() === '继续沟通');
            return {
                state: jixu.length > 0 ? '继续沟通' : (liji.length > 0 ? '立即沟通' : 'not_found'),
                lijiCount: liji.length,
                jixuCount: jixu.length
            };
        }
    """)
    print(f"[click] After click: {final_state['state']} (立即沟通={final_state['lijiCount']}, 继续沟通={final_state['jixuCount']})")
    
    if final_state['state'] == '继续沟通':
        return {"success": True}
    else:
        return {"success": False, "error": "Button did not change to '继续沟通'"}


def generate_greeting_with_llm(job_info: dict, resume_text: str) -> str:
    """Generate personalized greeting using LLM API."""
    import urllib.request
    import urllib.parse
    import os

    # Check for MIMO API key (OpenAI compatible)
    api_key = os.environ.get('MIMO_ANTHROPIC_API_KEY') or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("[auto] ⚠️ No LLM API key found (MIMO_ANTHROPIC_API_KEY or OPENAI_API_KEY)")
        print("[auto] Falling back to template greeting")
        return None
    
    print(f"[auto] Using LLM API key: {api_key[:20]}...")

    # Build prompt
    job_name = job_info.get('jobName', '这个岗位')
    company = job_info.get('brandName', '贵司')
    salary = job_info.get('salaryDesc', '')
    city = job_info.get('cityName', '')
    jd = job_info.get('jobDesc', '')[:500]  # First 500 chars
    skills = job_info.get('skills', [])

    prompt = f"""你是一位专业的求职者，需要根据职位JD和个人简历生成一段个性化的BOSS直聘打招呼语。

要求：
1. 简洁有力，50-100字
2. 突出与岗位的匹配度
3. 提及1-2个关键技能或经验亮点
4. 语气专业且真诚
5. 不要套话，要有针对性

职位信息：
- 岗位：{job_name}
- 公司：{company}
- 薪资：{salary}
- 城市：{city}
- 技能要求：{', '.join(skills) if skills else '未指定'}
- JD摘要：{jd[:300]}

我的简历：
{resume_text[:800]}

请直接输出招呼语内容，不要加任何解释或前缀。"""

    # Try MIMO API first (OpenAI compatible)
    try:
        req = urllib.request.Request(
            "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
            data=json.dumps({
                "model": "mimo-v2.5-pro",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 200
            }).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            greeting = data['choices'][0]['message']['content'].strip()
            # Remove quotes if present
            greeting = greeting.strip('"').strip("'")
            print(f"[auto] LLM generated greeting: {greeting[:60]}...")
            return greeting
    except Exception as e:
        print(f"[auto] LLM API failed: {e}")
        return None


def extract_job_info_from_page(page, job_id: str) -> dict:
    """Extract job info from page since API often returns Code 17."""
    print("[auto] Extracting job info from page...")
    
    page.goto(f"https://www.zhipin.com/job_detail/{job_id}.html",
              wait_until="networkidle", timeout=30000)
    time.sleep(5)
    
    info = page.evaluate("""
        () => {
            const text = document.body.innerText;
            const title = document.title || '';
            
            // Extract job name and company from title
            // Format: "职位名称招聘"_公司招聘-BOSS直聘
            const titleParts = title.split('_');
            let jobName = '';
            let brandName = '';
            if (titleParts[0]) {
                jobName = titleParts[0].replace(/招聘/g, '').trim();
            }
            if (titleParts[1]) {
                brandName = titleParts[1].replace(/招聘-BOSS直聘/g, '').trim();
            }
            
            // Clean up: remove year prefix and suffix from jobName
            jobName = jobName.replace(/^[0-9]{4}年/, '').replace(/工作要求$/, '').trim();
            brandName = brandName.replace(/[0-9]{4}年.*$/, '').trim();
            
            // Find salary like 15-30K
            const salaryMatch = text.match(/([0-9]+-[0-9]+K)/);
            
            return {
                jobName: jobName,
                salaryDesc: salaryMatch ? salaryMatch[1] : '',
                brandName: brandName,
                jobDesc: text.slice(0, 500),
                fullText: text.slice(0, 1000)
            };
        }
    """)
    
    # Also try API as backup
    try:
        api_result = page.evaluate(f"""() =>
            fetch('/wapi/zpgeek/job/detail.json?encryptJobId={json.dumps(job_id)[1:-1]}', {{
                credentials: 'include',
                headers: {{'X-Requested-With': 'XMLHttpRequest'}}
            }})
                .then(r => r.json())
                .catch(e => ({{error: e.message}}))
        """)
        if api_result.get('code') == 0:
            zpData = api_result.get('zpData', {})
            info['jobName'] = info['jobName'] or zpData.get('jobName', '')
            info['brandName'] = info['brandName'] or zpData.get('brandName', '')
            info['salaryDesc'] = info['salaryDesc'] or zpData.get('salaryDesc', '')
            info['cityName'] = zpData.get('cityName', '')
            info['jobDesc'] = zpData.get('jobDesc', info['jobDesc'])[:500]
            info['skills'] = zpData.get('skills', [])
            print(f"[auto] Got job info from API: {info['jobName']} @ {info['brandName']}")
    except Exception as e:
        print(f"[auto] API fallback failed: {e}")
    
    return info


def main():
    parser = argparse.ArgumentParser(description="Send message to BOSS recruiter")
    parser.add_argument("job_id", help="encryptJobId of the target job")
    parser.add_argument("greeting", nargs="?", help="Greeting message to send")
    parser.add_argument("--auto", action="store_true", help="Auto mode: extract JD + resume info for agent greeting generation")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually send, just show what would be sent")
    args = parser.parse_args()

    greeting = args.greeting
    resume_text = ""
    
    if args.auto:
        # Load resume
        resume_path = Path.home() / '.hermes' / 'credentials' / 'resume.txt'
        if resume_path.exists():
            resume_text = resume_path.read_text().strip()
            print(f"[auto] Loaded resume ({len(resume_text)} chars)")
        else:
            print("[auto] ⚠️ No resume found at ~/.hermes/credentials/resume.txt")

    if not greeting and not args.auto:
        print("[error] No greeting provided. Use: python send_camoufox.py <job_id> \"your message\"")
        print("       Or use --auto to extract JD info for agent greeting generation")
        sys.exit(1)

    print(f"[send] Job: {args.job_id}")
    if greeting:
        print(f"[send] Greeting: {greeting}")

    from camoufox.sync_api import Camoufox

    with Camoufox(humanize=True, geoip=True, os="macos", block_images=False) as browser:
        page = browser.new_page()

        # Load existing cookies (they work for page interaction even if API returns Code 17)
        cookies = load_cookies()
        if cookies:
            page.context.add_cookies(cookies)
            print(f"[send] Loaded {len(cookies)} cookies")
        
        # Step 1: Visit search page to establish context
        print("[step1] Establishing session...")
        page.goto("https://www.zhipin.com/web/geek/job?query=Python&city=101010100&page=1",
                   wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Step 2: Quick login check via page state (not API)
        print("[step2] Checking login state...")
        login_check = page.evaluate("""
            () => {
                const userName = document.querySelector('.user-name') || 
                                document.querySelector('[class*="user"]');
                const hasUserMenu = !!document.querySelector('.nav-resume-box') ||
                                   !!document.querySelector('[ka*="resume"]');
                return {hasUserMenu, bodyText: document.body.innerText.slice(0, 50)};
            }
        """)
        print(f"[step2] Login check: {json.dumps(login_check, ensure_ascii=False)}")
        
        if not login_check.get('hasUserMenu'):
            print("[step2] Not logged in, triggering QR login...")
            if do_login(page):
                save_cookies(page.context)
            else:
                print("[send] ❌ Login failed")
                sys.exit(1)

        # Step 3: Get job info (for auto greeting generation or display)
        print("[step3] Getting job card info...")
        _job_id = json.dumps(args.job_id)
        
        job_info = {}
        try:
            card = page.evaluate(f"""() =>
                fetch('/wapi/zpgeek/job/card.json?encryptJobId=' + {_job_id}, {{
                    credentials: 'include',
                    headers: {{'X-Requested-With': 'XMLHttpRequest'}}
                }})
                    .then(r => r.json())
                    .catch(e => ({{error: e.message}}))
            """)
            if card.get('code') == 0:
                zpData = card.get('zpData', {})
                job_info = {
                    'jobName': zpData.get('jobName', ''),
                    'brandName': zpData.get('brandName', ''),
                    'salaryDesc': zpData.get('salaryDesc', ''),
                    'cityName': zpData.get('cityName', ''),
                    'jobDesc': zpData.get('jobDesc', '')[:500],
                    'skills': zpData.get('skills', []),
                    'bossName': zpData.get('bossName', ''),
                    'bossTitle': zpData.get('bossTitle', '')
                }
                print(f"[step3] Job: {job_info['jobName']} @ {job_info['brandName']}")
                print(f"[step3] Boss: {job_info['bossName']} ({job_info['bossTitle']})")
        except Exception as e:
            print(f"[step3] Card API failed: {e}")
        
        # If API failed, try to extract from page
        if not job_info.get('jobName'):
            print("[step3] Trying job detail API...")
            try:
                detail = page.evaluate(f"""() =>
                    fetch('/wapi/zpgeek/job/detail.json?encryptJobId=' + {_job_id}, {{
                        credentials: 'include',
                        headers: {{'X-Requested-With': 'XMLHttpRequest'}}
                    }})
                        .then(r => r.json())
                        .catch(e => ({{error: e.message}}))
                """)
                if detail.get('code') == 0:
                    zpData = detail.get('zpData', {})
                    job_info = {
                        'jobName': zpData.get('jobName', job_info.get('jobName', '')),
                        'brandName': zpData.get('brandName', job_info.get('brandName', '')),
                        'salaryDesc': zpData.get('salaryDesc', job_info.get('salaryDesc', '')),
                        'cityName': zpData.get('cityName', job_info.get('cityName', '')),
                        'jobDesc': zpData.get('jobDesc', job_info.get('jobDesc', ''))[:500],
                        'skills': zpData.get('skills', job_info.get('skills', []))
                    }
            except Exception as e:
                print(f"[step3] Detail API failed: {e}")
        
        # If still no job info, extract from page
        if not job_info.get('jobName'):
            job_info = extract_job_info_from_page(page, args.job_id)

        # Auto mode: output JD + resume info for agent to generate greeting
        if args.auto and not greeting:
            print("\n===AUTO_GREETING_INFO===")
            print(f"JOB_ID: {args.job_id}")
            print(f"JOB_NAME: {job_info.get('jobName', '')}")
            print(f"COMPANY: {job_info.get('brandName', '')}")
            print(f"SALARY: {job_info.get('salaryDesc', '')}")
            print(f"CITY: {job_info.get('cityName', '')}")
            print(f"SKILLS: {', '.join(job_info.get('skills', []))}")
            print(f"JD: {job_info.get('jobDesc', '')[:300]}")
            print(f"RESUME: {resume_text[:500] if resume_text else 'Not found'}")
            print("===END_AUTO_GREETING_INFO===")
            print("\n[auto] Agent should generate greeting based on above info and call:")
            print(f"       python send_camoufox.py {args.job_id} \"generated greeting\"")
            
            if args.dry_run:
                print("\n[auto] Dry run mode, exiting without sending")
                sys.exit(0)
            else:
                print("\n[auto] Waiting for agent to provide greeting...")
                sys.exit(2)  # Special exit code: need agent input

        # Step 4: Send message by clicking (most reliable method)
        print(f"\n[step4] Sending greeting via page interaction...")
        result = send_message_by_click(page, args.job_id, greeting)
        
        if result.get('success'):
            print(f"\n✅ 消息发送成功！")
        else:
            print(f"\n❌ 发送失败: {result.get('error', '')}")

        # Save updated cookies
        save_cookies(page.context)


if __name__ == "__main__":
    main()
