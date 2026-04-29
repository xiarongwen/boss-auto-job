#!/usr/bin/env python3
"""
BOSS Zhipin Job Search - Browser Mode

Usage: python search_browser.py "产品经理" --city=101010100 --pages=3

Uses browser automation to navigate BOSS search pages and extract job listings.
This avoids requests-based detection by using a real browser environment.

Output: JSON array of job listings to stdout.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path


def extract_jobs_from_page(html: str) -> list:
    """Extract job listings from BOSS search page HTML."""
    jobs = []
    
    # Method 1: Extract from __INITIAL_STATE__ script tag
    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', html, re.DOTALL)
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
            pass
    
    # Method 2: Extract from API response embedded in HTML
    if not jobs:
        match2 = re.search(r'"jobList":\s*(\[.*?\])', html, re.DOTALL)
        if match2:
            try:
                job_list = json.loads(match2.group(1))
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
            except (json.JSONDecodeError, AttributeError):
                pass
    
    return jobs


def build_search_url(keyword: str, city: str, page: int) -> str:
    """Build BOSS search URL."""
    return f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city}&page={page}"


def main():
    parser = argparse.ArgumentParser(description="Search jobs on BOSS Zhipin using browser")
    parser.add_argument("keyword", help="Job keyword to search")
    parser.add_argument("--city", default="101010100", help="City code (default: Beijing)")
    parser.add_argument("--pages", type=int, default=3, help="Number of pages to fetch")
    args = parser.parse_args()

    print(f"[search] Browser mode: searching '{args.keyword}' in city {args.city}, {args.pages} pages")
    print("[search] Agent should use browser_navigate to open these URLs and extract jobs:")
    
    urls = []
    for page in range(1, args.pages + 1):
        url = build_search_url(args.keyword, args.city, page)
        urls.append(url)
    
    # Output URL list for agent to process
    print("===SEARCH_URLS_START===")
    print(json.dumps(urls, ensure_ascii=False, indent=2))
    print("===SEARCH_URLS_END===")
    
    print("\n[search] For each URL:")
    print("  1. browser_navigate(url)")
    print("  2. browser_snapshot(full=true) or browser_console to get HTML")
    print("  3. Pass HTML to extract_jobs_from_page()")
    print("  4. Wait 2-3 seconds between pages")


if __name__ == "__main__":
    main()
