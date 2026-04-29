#!/usr/bin/env python3
"""
BOSS Zhipin Job Search Scraper

Usage: python search.py "产品经理" --city=101010100 --pages=3

Outputs JSON array of job listings to stdout.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

COOKIE_PATH = Path.home() / ".hermes" / "credentials" / "boss_cookies.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.zhipin.com/",
}


def load_cookies() -> dict:
    if not COOKIE_PATH.exists():
        print("[search] ERROR: No cookies found. Run login.py first.", file=sys.stderr)
        sys.exit(1)
    with open(COOKIE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def search_jobs(keyword: str, city: str, pages: int) -> list:
    cookies = load_cookies()
    jobs = []
    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.update(cookies)

    for page in range(1, pages + 1):
        url = f"https://www.zhipin.com/web/geek/job"
        params = {
            "query": keyword,
            "city": city,
            "page": page,
        }
        try:
            resp = session.get(url, params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[search] Page {page} request failed: {e}", file=sys.stderr)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        # BOSS uses React, data may be in script tags or API calls
        # Try to extract from __INITIAL_STATE__ or similar
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.string or ""
            if "__INITIAL_STATE__" in text or "jobList" in text:
                # Extract JSON from script
                match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        job_list = data.get("jobList", {}).get("list", [])
                        for item in job_list:
                            job = {
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
                            }
                            jobs.append(job)
                    except json.JSONDecodeError:
                        continue

        # Also try API endpoint if page rendering fails
        if not jobs:
            api_url = "https://www.zhipin.com/wapi/zpgeek/search/joblist.json"
            api_params = {
                "query": keyword,
                "city": city,
                "page": page,
                "pageSize": 30,
            }
            try:
                resp = session.get(api_url, params=api_params, timeout=15)
                data = resp.json()
                if data.get("code") == 0:
                    for item in data.get("zpData", {}).get("list", []):
                        job = {
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
                        }
                        jobs.append(job)
            except Exception as e:
                print(f"[search] API fallback failed: {e}", file=sys.stderr)

        time.sleep(2)  # Rate limiting

    return jobs


def main():
    parser = argparse.ArgumentParser(description="Search jobs on BOSS Zhipin")
    parser.add_argument("keyword", help="Job keyword to search")
    parser.add_argument("--city", default="101010100", help="City code (default: Beijing)")
    parser.add_argument("--pages", type=int, default=3, help="Number of pages to fetch")
    args = parser.parse_args()

    jobs = search_jobs(args.keyword, args.city, args.pages)
    print(json.dumps(jobs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
