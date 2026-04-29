#!/usr/bin/env python3
"""
BOSS Zhipin Search - Camoufox Mode (Ultimate Stealth)

Uses Camoufox (C++ level Firefox fingerprint spoofing) to bypass ALL
4 layers of BOSS anti-bot detection without any login cookies.

Usage:
  python search_camoufox.py "产品经理" --city=101010100 --pages=3
  python search_camoufox.py "Python" --output=/tmp/jobs.json
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

AUTH_FILE = Path.home() / '.agent-browser' / 'auth' / 'boss-zhipin.json'


def load_cookies() -> list:
    """Load cookies from auth file (optional, Camoufox may not need them)."""
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


def search_jobs(query: str, city: str, pages: int) -> list:
    """Search jobs using Camoufox."""
    from camoufox.sync_api import Camoufox

    print(f"[search] Query: {query}, City: {city}, Pages: {pages}")
    print(f"[search] Launching Camoufox (C++ stealth Firefox)...")

    all_jobs = []

    with Camoufox(
        humanize=True,     # C++ HumanCursor mouse/keyboard simulation
        geoip=True,        # Auto timezone/locale from IP
        os="macos",        # Fingerprint as macOS
        block_images=False, # Need images for captcha if triggered
    ) as browser:
        context = browser.contexts[0]

        # Load cookies if available (not required but may help)
        cookies = load_cookies()
        if cookies:
            context.add_cookies(cookies)
            print(f"[search] Loaded {len(cookies)} cookies")

        page = context.new_page()

        for page_num in range(1, pages + 1):
            url = f"https://www.zhipin.com/web/geek/job?query={query}&city={city}&page={page_num}"
            print(f"\n[search] Page {page_num}: {url}")

            # Navigate to search page (triggers zp_stoken auto-generation)
            resp = page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            current_url = page.url
            print(f"[search] URL: {current_url[:120]}")
            print(f"[search] Status: {resp.status}")

            # Check if blocked
            if "security-check" in current_url:
                print("[search] ⚠️ Security check triggered, waiting for auto-solve...")
                time.sleep(8)
                current_url = page.url
                if "security-check" in current_url:
                    print("[search] ❌ Still on security check page")
                    break

            if "verify" in current_url:
                print("[search] ❌ Hit verify page (need manual captcha)")
                break

            if "403" in current_url:
                print("[search] ❌ 403 forbidden")
                break

            # Call the job list API from within the page context
            print("[search] Calling job list API...")
            try:
                api_result = page.evaluate(f"""
                    () => fetch('/wapi/zpgeek/search/joblist.json?scene=1&query={query}&city={city}&page={page_num}&pageSize=30')
                        .then(r => r.json())
                        .catch(e => ({{error: e.message}}))
                """)
            except Exception as e:
                print(f"[search] ❌ API call failed: {e}")
                break

            code = api_result.get('code')
            msg = api_result.get('message', '')
            print(f"[search] Code: {code}, Message: {msg}")

            if code == 0:
                jobs = api_result.get('zpData', {}).get('jobList', [])
                print(f"[search] ✅ Found {len(jobs)} jobs on page {page_num}")
                all_jobs.extend(jobs)

            elif code == 37:
                # Environment check - let the security-check JS handle it
                print("[search] ⚠️ Code 37: Environment check. Navigating to security-check...")
                zpData = api_result.get('zpData', {})
                seed = zpData.get('seed', '')
                ts = zpData.get('ts', '')
                name = zpData.get('name', '')

                if seed and name:
                    sec_url = f"https://www.zhipin.com/web/common/security-check.html?seed={seed}&name={name}&ts={ts}&callbackUrl=%2Fweb%2Fgeek%2Fjob%3Fquery%3D{query}%26city%3D{city}%26page%3D{page_num}"
                    page.goto(sec_url, wait_until="networkidle", timeout=20000)
                    time.sleep(8)

                    if "security-check" not in page.url:
                        # Retry API
                        try:
                            retry = page.evaluate(f"""
                                () => fetch('/wapi/zpgeek/search/joblist.json?scene=1&query={query}&city={city}&page={page_num}&pageSize=30')
                                    .then(r => r.json())
                            """)
                            if retry.get('code') == 0:
                                jobs = retry.get('zpData', {}).get('jobList', [])
                                print(f"[search] ✅ Found {len(jobs)} jobs after zp_stoken bypass")
                                all_jobs.extend(jobs)
                            else:
                                print(f"[search] ❌ Retry failed: code={retry.get('code')}")
                        except Exception as e:
                            print(f"[search] ❌ Retry error: {e}")
                else:
                    print("[search] ❌ Missing seed/name/ts for bypass")

            elif code == 36:
                print("[search] ❌ Code 36: Account flagged. STOP. Tell user to manually verify.")
                break

            elif code == 32:
                print("[search] ❌ Code 32: Account banned. STOP. Tell user to manually recover.")
                break

            elif code == 1006:
                print("[search] ⚠️ Code 1006: Rate limited. Waiting 10s...")
                time.sleep(10)

            else:
                print(f"[search] ❌ Unexpected code {code}: {msg}")
                break

            # Rate limit between pages
            if page_num < pages:
                delay = 3 + (page_num % 3)
                print(f"[search] Waiting {delay}s before next page...")
                time.sleep(delay)

    return all_jobs


def format_jobs(raw_jobs: list) -> list:
    """Format raw API jobs into clean structure."""
    output = []
    for j in raw_jobs:
        output.append({
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
    return output


def main():
    parser = argparse.ArgumentParser(description="Search BOSS Zhipin using Camoufox (ultimate stealth)")
    parser.add_argument("query", help="Job keyword to search")
    parser.add_argument("--city", default="101010100", help="City code (default: 101010100=Beijing)")
    parser.add_argument("--pages", type=int, default=3, help="Number of pages (default: 3)")
    parser.add_argument("--output", help="Output file path")
    args = parser.parse_args()

    ts_start = time.time()

    # Search
    raw_jobs = search_jobs(args.query, args.city, args.pages)

    if not raw_jobs:
        print("\n[search] ❌ No jobs found. Check error messages above.")
        sys.exit(1)

    # Format
    jobs = format_jobs(raw_jobs)

    elapsed = time.time() - ts_start
    print(f"\n{'='*60}")
    print(f"✅ Done! Found {len(jobs)} jobs in {elapsed:.1f}s")
    print(f"{'='*60}")

    # Print first 5
    print(f"\nTop {min(5, len(jobs))} results:")
    for i, j in enumerate(jobs[:5]):
        print(f"  {i+1}. {j['title']} @ {j['company']} ({j['salary']})")
        print(f"     {j['location']} {j['area']} | {j['experience']} | {j['degree']}")
        print(f"     👤 {j['boss_name']} ({j['boss_title']})")
        print(f"     Skills: {', '.join(j['skills'][:5])}")
        print()

    # Output
    output = json.dumps(jobs, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"[search] Saved to {args.output}")
    else:
        # Save to default location
        default_path = f"/tmp/boss_jobs_{args.query}_{args.city}_p{args.pages}.json"
        with open(default_path, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"[search] Saved to {default_path}")

        print("===JOBS_JSON_START===")
        print(output)
        print("===JOBS_JSON_END===")


if __name__ == "__main__":
    main()
