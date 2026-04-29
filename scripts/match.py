#!/usr/bin/env python3
"""
Multi-Agent Resume Matching Orchestrator

Usage: python match.py <jobs.json> --top=10

Reads jobs JSON from stdin or file, delegates each JD to subagent for scoring,
outputs ranked results.
"""

import argparse
import json
import os
import sys
from pathlib import Path

RESUME_PATH = Path.home() / ".hermes" / "credentials" / "resume.txt"


def load_resume() -> str:
    if not RESUME_PATH.exists():
        print("[match] ERROR: No resume found. Create ~/.hermes/credentials/resume.txt", file=sys.stderr)
        sys.exit(1)
    with open(RESUME_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def build_subagent_prompt(jd: dict, resume: str) -> str:
    return f"""You are a professional HR recruiter with 10 years of experience.
Compare the following job description against the candidate's resume and give a match score.

## CRITICAL RULES
- ONLY use the resume text provided below. DO NOT search for other files or external information.
- If the resume text is short or mock data, score based ONLY on what is provided.
- Do NOT assume additional skills or experiences beyond what is explicitly stated.

## Job Description
Title: {jd.get('title', '')}
Company: {jd.get('company', '')}
Salary: {jd.get('salary', '')}
Requirements: {', '.join(jd.get('requirements', []))}
JD Text:
{jd.get('jd_text', '')}

## Candidate Resume (USE ONLY THIS)
{resume}

## Scoring Criteria
- Skills match (40%): How well do the candidate's skills align with required skills?
- Experience relevance (30%): Does the candidate's past experience match the role's needs?
- Education fit (10%): Does education background meet requirements?
- Industry alignment (20%): Is the candidate familiar with this industry/domain?

## Output Format (STRICT)
Return ONLY a JSON object. No markdown, no tables, no explanation outside the JSON:
{"score": 85, "reason": "Brief 1-sentence explanation"}

## ABSOLUTE RULES
1. ONLY use the resume text provided above. DO NOT search files or external info.
2. Score based ONLY on what is explicitly stated in the resume.
3. Output must be valid JSON, nothing else.
"""


def main():
    parser = argparse.ArgumentParser(description="Match jobs against resume using subagents")
    parser.add_argument("input", nargs="?", help="Jobs JSON file (default: stdin)")
    parser.add_argument("--top", type=int, default=10, help="Keep top N matches")
    args = parser.parse_args()

    resume = load_resume()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            jobs = json.load(f)
    else:
        jobs = json.load(sys.stdin)

    print(f"[match] Loaded {len(jobs)} jobs and resume ({len(resume)} chars)")
    print(f"[match] Ready to delegate to subagents. Call delegate_task with the following tasks:")

    tasks = []
    for jd in jobs:
        prompt = build_subagent_prompt(jd, resume)
        tasks.append({
            "job_id": jd.get("job_id"),
            "title": jd.get("title"),
            "company": jd.get("company"),
            "prompt": prompt,
        })

    # Output tasks as JSON for the agent to consume
    print("===TASKS_JSON_START===")
    print(json.dumps(tasks[:args.top], ensure_ascii=False, indent=2))
    print("===TASKS_JSON_END===")


if __name__ == "__main__":
    main()
