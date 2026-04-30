#!/usr/bin/env python3
"""
Generate tailored self-introduction based on JD and resume.
Uses LLM API to generate personalized greetings (no fixed templates).

Usage:
  python generate.py <jd.json> --resume=path/to/resume.txt
  python generate.py <jd.json>    # uses default resume

Output: the generated introduction text.
"""

import argparse
import json
import sys
from pathlib import Path
from generate_greeting import build_greeting_prompt, call_llm


def main():
    parser = argparse.ArgumentParser(description="Generate tailored self-introduction")
    parser.add_argument("jd_file", help="JD JSON file")
    parser.add_argument("--resume", default=str(Path.home() / ".hermes" / "credentials" / "resume.txt"), help="Resume file path")
    args = parser.parse_args()

    with open(args.jd_file, "r", encoding="utf-8") as f:
        jd = json.load(f)

    with open(args.resume, "r", encoding="utf-8") as f:
        resume = f.read().strip()

    prompt = build_greeting_prompt(jd, resume)
    greeting = call_llm(prompt)
    print(greeting)


if __name__ == "__main__":
    main()
