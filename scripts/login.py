#!/usr/bin/env python3
"""
BOSS Zhipin Login & Session Manager

First run: opens browser for manual login, saves cookies.
Subsequent runs: validates and refreshes session.
"""

import json
import os
import sys
import time
from pathlib import Path

COOKIE_PATH = Path.home() / ".hermes" / "credentials" / "boss_cookies.json"
COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)


def save_cookies(cookies: dict):
    with open(COOKIE_PATH, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"[login] Cookies saved to {COOKIE_PATH}")


def load_cookies() -> dict | None:
    if not COOKIE_PATH.exists():
        return None
    with open(COOKIE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def is_session_valid(cookies: dict) -> bool:
    """Quick check: try to fetch user profile API."""
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.zhipin.com/",
    }
    # Use a lightweight endpoint to verify login
    url = "https://www.zhipin.com/wapi/zpgeek/chat/status.json"
    resp = requests.get(url, headers=headers, cookies=cookies, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("code") == 0
    return False


def prompt_login():
    print("=" * 50)
    print("BOSS 直聘登录")
    print("=" * 50)
    print("请在弹出的浏览器中完成登录（扫码或密码）")
    print("登录成功后，按回车键保存登录态...")
    print("=" * 50)
    input("按回车继续...")


def main():
    cookies = load_cookies()
    if cookies and is_session_valid(cookies):
        print("[login] Session valid, no need to login.")
        sys.exit(0)

    print("[login] No valid session found. Please login manually.")
    prompt_login()
    # After user confirms, read cookies from browser via external tool
    # This script is called by the agent which uses browser tools to extract cookies
    print("[login] Waiting for agent to extract cookies from browser...")
    # Agent should call browser_console to extract document.cookie or storage
    # and then call save_cookies() via python execution
    print("[login] Done. Run 'python scripts/search.py <job_name>' next.")


if __name__ == "__main__":
    main()
