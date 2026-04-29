#!/usr/bin/env python3
"""
BOSS Zhipin Search - Chrome CDP Mode with Anti-Bot Bypass

Controls your existing Chrome browser via Chrome DevTools Protocol.
Automatically handles BOSS security-check by generating __zp_stoken__.

Usage:
  1. Start Chrome with remote debugging:
     /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

  2. Run this script:
     python search_chrome_cdp.py "产品经理" --city=101010100 --pages=3
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import requests

CDP_URL = "http://localhost:9222"
SECURITY_JS_URL = "https://www.zhipin.com/web/common/security-js/{name}.js"


def get_ws_url() -> str:
    """Get WebSocket URL for the first page."""
    resp = requests.get(f"{CDP_URL}/json/list")
    pages = resp.json()
    for page in pages:
        if page["type"] == "page":
            return page["webSocketDebuggerUrl"]
    raise RuntimeError("No page found")


def send_cdp_command(ws_url: str, method: str, params: dict = None) -> dict:
    """Send CDP command via WebSocket."""
    import websocket
    ws = websocket.create_connection(ws_url)
    cmd = {"id": 1, "method": method, "params": params or {}}
    ws.send(json.dumps(cmd))
    resp = ws.recv()
    ws.close()
    return json.loads(resp)


def navigate_to_url(ws_url: str, url: str):
    """Navigate to URL via CDP."""
    return send_cdp_command(ws_url, "Page.navigate", {"url": url})


def get_page_html(ws_url: str) -> str:
    """Get page HTML via CDP."""
    result = send_cdp_command(ws_url, "Runtime.evaluate", {
        "expression": "document.documentElement.outerHTML",
        "returnByValue": True
    })
    return result.get("result", {}).get("result", {}).get("value", "")


def get_current_url(ws_url: str) -> str:
    """Get current page URL."""
    result = send_cdp_command(ws_url, "Runtime.evaluate", {
        "expression": "window.location.href",
        "returnByValue": True
    })
    return result.get("result", {}).get("result", {}).get("value", "")


def fetch_security_js(name: str) -> str:
    """Fetch the security JS file from BOSS CDN."""
    url = SECURITY_JS_URL.format(name=name)
    resp = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.zhipin.com/web/common/security-check.html",
    }, timeout=10)
    if resp.status_code == 200:
        return resp.text
    raise RuntimeError(f"Failed to fetch security JS: {resp.status_code}")


def generate_zp_stoken(seed: str, ts: str, js_code: str) -> str:
    """Generate __zp_stoken__ using Node.js VM."""
    node_script = f"""
const vm = require('vm');

const code = `{js_code.replace('`', '\\`').replace('\\', '\\\\')}`;

const context = {{
    window: {{}},
    document: {{}},
    navigator: {{ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' }},
    location: {{
        href: 'https://www.zhipin.com/web/common/security-check.html',
        search: '?seed=' + encodeURIComponent('{seed}') + '&ts={ts}'
    }},
    console: console,
    setTimeout: setTimeout,
    setInterval: setInterval,
}};

vm.createContext(context);
vm.runInContext(code, context);

const ABC = context.window.ABC;
const instance = new ABC();
const offset = new Date().getTimezoneOffset();
const tsValue = parseInt('{ts}') + (480 + offset) * 60 * 1000;
const result = instance.z('{seed}', tsValue);
console.log('ZP_STOKEN:' + result);
"""
    with open("/tmp/gen_zp_stoken.js", "w") as f:
        f.write(node_script)
    
    result = subprocess.run(
        ["node", "/tmp/gen_zp_stoken.js"],
        capture_output=True, text=True, timeout=10
    )
    
    for line in result.stdout.split("\n"):
        if line.startswith("ZP_STOKEN:"):
            return line.split(":", 1)[1]
    
    raise RuntimeError(f"Failed to generate zp_stoken: {result.stderr}")


def bypass_security_check(ws_url: str, current_url: str) -> bool:
    """Bypass BOSS security-check by injecting __zp_stoken__ cookie."""
    if "security-check" not in current_url:
        return True  # Not on security check page
    
    print("[bypass] Detected security-check page, generating zp_stoken...")
    
    # Parse seed, ts, name from URL
    parsed = urllib.parse.urlparse(current_url)
    params = urllib.parse.parse_qs(parsed.query)
    
    seed = urllib.parse.unquote(params.get("seed", [""])[0])
    ts = params.get("ts", [""])[0]
    name = params.get("name", [""])[0]
    callback_url = urllib.parse.unquote(params.get("callbackUrl", ["/"])[0])
    
    if not seed or not ts or not name:
        print("[bypass] ERROR: Missing required parameters in URL")
        return False
    
    try:
        # Fetch security JS
        print(f"[bypass] Fetching security JS: {name}.js")
        js_code = fetch_security_js(name)
        
        # Generate zp_stoken
        print("[bypass] Generating __zp_stoken__...")
        zp_stoken = generate_zp_stoken(seed, ts, js_code)
        print(f"[bypass] Generated zp_stoken: {zp_stoken[:50]}...")
        
        # Inject cookie via CDP
        print("[bypass] Injecting cookie into Chrome...")
        send_cdp_command(ws_url, "Network.setCookie", {
            "name": "__zp_stoken__",
            "value": zp_stoken,
            "domain": ".zhipin.com",
            "path": "/",
            "httpOnly": False,
            "secure": True,
        })
        
        # Navigate to callback URL
        target = f"https://www.zhipin.com{callback_url}"
        print(f"[bypass] Navigating to: {target}")
        navigate_to_url(ws_url, target)
        time.sleep(3)
        
        # Verify we're no longer on security-check
        new_url = get_current_url(ws_url)
        if "security-check" in new_url:
            print("[bypass] WARNING: Still on security-check page")
            return False
        
        print("[bypass] SUCCESS: Security check bypassed!")
        return True
        
    except Exception as e:
        print(f"[bypass] ERROR: {e}")
        return False


def extract_jobs_from_html(html: str) -> list:
    """Extract job listings from BOSS search page HTML."""
    jobs = []
    
    # Try to extract from __INITIAL_STATE__
    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            job_list = data.get("jobList", {}).get("list", [])
            for item in job_list:
                jobs.append({
                    "job_id": item.get("encryptJobId") or item.get("jobId"),
                    "title": item.get("jobName", ""),
                    "company": item.get("brandName", ""),
                    "salary": item.get("salaryDesc", ""),
                    "location": item.get("cityName", ""),
                    "requirements": item.get("jobLabels", []),
                    "jd_text": item.get("jobDesc", ""),
                    "boss_name": item.get("bossName", ""),
                    "boss_title": item.get("bossTitle", ""),
                    "encrypt_user_id": item.get("encryptUserId", ""),
                })
        except json.JSONDecodeError:
            pass
    
    return jobs


def search_jobs(keyword: str, city: str, pages: int) -> list:
    """Search jobs using Chrome CDP with anti-bot bypass."""
    try:
        ws_url = get_ws_url()
    except Exception as e:
        print(f"[ERROR] Cannot connect to Chrome. Make sure Chrome is running with --remote-debugging-port=9222")
        print(f"[ERROR] {e}")
        sys.exit(1)
    
    all_jobs = []
    
    for page_num in range(1, pages + 1):
        url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city}&page={page_num}"
        print(f"[search] Navigating to page {page_num}: {url}")
        
        navigate_to_url(ws_url, url)
        time.sleep(3)
        
        # Check if we hit security-check
        current_url = get_current_url(ws_url)
        if "security-check" in current_url:
            success = bypass_security_check(ws_url, current_url)
            if not success:
                print("[search] Failed to bypass security check")
                break
        
        html = get_page_html(ws_url)
        
        # Check for other verification
        if "安全验证" in html or "verify" in html.lower():
            print(f"[search] WARNING: Hit verification page on page {page_num}")
            break
        
        jobs = extract_jobs_from_html(html)
        print(f"[search] Found {len(jobs)} jobs on page {page_num}")
        all_jobs.extend(jobs)
        
        if page_num < pages:
            time.sleep(3)
    
    return all_jobs


def main():
    parser = argparse.ArgumentParser(description="Search jobs on BOSS Zhipin using Chrome CDP")
    parser.add_argument("keyword", help="Job keyword to search")
    parser.add_argument("--city", default="101010100", help="City code")
    parser.add_argument("--pages", type=int, default=3, help="Number of pages")
    parser.add_argument("--output", help="Output file (default: stdout)")
    args = parser.parse_args()
    
    jobs = search_jobs(args.keyword, args.city, args.pages)
    
    output = json.dumps(jobs, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"[search] Saved {len(jobs)} jobs to {args.output}")
    else:
        print("===JOBS_JSON_START===")
        print(output)
        print("===JOBS_JSON_END===")


if __name__ == "__main__":
    main()
