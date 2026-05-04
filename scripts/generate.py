#!/usr/bin/env python3
"""
Generate tailored self-introduction based on JD and resume.

Usage: python generate.py <jd.json> --resume=path/to/resume.txt
Outputs the generated introduction text.
"""

import argparse
import json
import sys
from pathlib import Path


def build_prompt(jd: dict, resume: str) -> str:
    return f"""You are a professional job applicant coach.

Based on the following job description and my resume, write a concise, enthusiastic self-introduction in Chinese (max 150 characters) that I can send to the recruiter on BOSS Zhipin.

## Job Description
Title: {jd.get('title', '')}
Company: {jd.get('company', '')}
Requirements: {', '.join(jd.get('requirements', []))}
JD Text:
{jd.get('jd_text', '')}

## My Resume
{resume}

## Requirements for the introduction:
1. Mention 2-3 specific skills/experiences that match this JD
2. Show genuine interest in THIS specific company/role
3. Keep it conversational and natural, not robotic
4. Max 150 Chinese characters
5. End with a polite request to chat further

Output ONLY the introduction text, no markdown, no quotes around it.
"""


def main():
    parser = argparse.ArgumentParser(description="Generate tailored self-introduction")
    parser.add_argument("jd_file", help="JD JSON file")
    parser.add_argument("--resume", default=str(Path.home() / ".hermes" / "credentials" / "resume.txt"), help="Resume file path")
    args = parser.parse_args()

    with open(args.jd_file, "r", encoding="utf-8") as f:
        jd = json.load(f)

    with open(args.resume, "r", encoding="utf-8") as f:
        resume = f.read().strip()

    prompt = build_prompt(jd, resume)
    print(prompt)


if __name__ == "__main__":
    main()
