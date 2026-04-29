#!/usr/bin/env python3
"""
BOSS Auto Job Orchestrator

One-command workflow:
1. Check login
2. Search jobs
3. Match against resume
4. Generate introductions
5. Send applications

Usage: python orchestrator.py "产品经理" --city=101010100 --pages=3 --top=10 --dry-run
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"


def run_login():
    print("[orchestrator] Step 1: Checking login session...")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "login.py")],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("[orchestrator] Login required. Please run login manually first.")
        sys.exit(1)


def run_search(keyword: str, city: str, pages: int) -> list:
    print(f"[orchestrator] Step 2: Searching '{keyword}' in city {city}...")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "search.py"), keyword,
         "--city", city, "--pages", str(pages)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[orchestrator] Search failed: {result.stderr}")
        sys.exit(1)
    try:
        jobs = json.loads(result.stdout)
        print(f"[orchestrator] Found {len(jobs)} jobs")
        return jobs
    except json.JSONDecodeError:
        print(f"[orchestrator] Failed to parse search results")
        sys.exit(1)


def run_match(jobs: list, top: int) -> list:
    print("[orchestrator] Step 3: Matching jobs against resume...")
    # Write jobs to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False)
        tmp_path = f.name

    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "match.py"), tmp_path, "--top", str(top)],
        capture_output=True, text=True
    )
    # match.py outputs tasks for agent to delegate
    print(result.stdout)
    # For now, return top N jobs (agent will handle actual matching via delegate_task)
    return jobs[:top]


def run_generate(jd: dict) -> str:
    print(f"[orchestrator] Step 4: Generating introduction for {jd.get('title')}...")
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(jd, f, ensure_ascii=False)
        tmp_path = f.name

    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "generate.py"), tmp_path],
        capture_output=True, text=True
    )
    print(result.stdout)
    # Agent should extract prompt and call LLM
    return "[AGENT_SHOULD_GENERATE]"


def run_send(job_id: str, intro: str, boss_id: str = None, dry_run: bool = False):
    print(f"[orchestrator] Step 5: Sending application to {job_id}...")
    cmd = [sys.executable, str(SCRIPTS_DIR / "send.py"), "--job-id", job_id, "--intro", intro]
    if boss_id:
        cmd.extend(["--boss-id", boss_id])
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    # Agent should execute browser actions from output


def main():
    parser = argparse.ArgumentParser(description="BOSS Auto Job - Full workflow")
    parser.add_argument("keyword", help="Job keyword to search")
    parser.add_argument("--city", default="101010100", help="City code")
    parser.add_argument("--pages", type=int, default=3, help="Search pages")
    parser.add_argument("--top", type=int, default=10, help="Top matches to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually send")
    args = parser.parse_args()

    print("=" * 60)
    print("BOSS Auto Job - Starting workflow")
    print("=" * 60)

    # Step 1: Login
    run_login()

    # Step 2: Search
    jobs = run_search(args.keyword, args.city, args.pages)
    if not jobs:
        print("[orchestrator] No jobs found. Exiting.")
        sys.exit(0)

    # Step 3: Match (agent delegates to subagents)
    top_jobs = run_match(jobs, args.top)

    # Step 4+5: Generate and Send (per job)
    for jd in top_jobs:
        print(f"\n[orchestrator] Processing: {jd.get('title')} @ {jd.get('company')}")
        intro = run_generate(jd)
        if not args.dry_run and intro != "[AGENT_SHOULD_GENERATE]":
            run_send(jd.get("job_id"), intro, jd.get("encrypt_user_id"), dry_run=False)
        else:
            print(f"[orchestrator] Dry run - would send to {jd.get('job_id')}")

    print("\n" + "=" * 60)
    print("BOSS Auto Job - Workflow complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
