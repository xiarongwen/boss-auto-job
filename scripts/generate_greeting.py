#!/usr/bin/env python3
"""
BOSS Zhipin - LLM-Powered Greeting Generator

Generates personalized greeting messages based on JD and resume analysis.
No fixed templates — the LLM analyzes JD requirements and resume strengths
to craft a natural, compelling first message.

Usage:
  python generate_greeting.py --jd=job.json --resume=resume.txt
  python generate_greeting.py --jd=job.json                     # uses default resume
  echo '{"title":"...","jd_text":"..."}' | python generate_greeting.py --stdin

Environment variables (any OpenAI-compatible API):
  BOSS_LLM_API_KEY   or OPENAI_API_KEY    — API key
  BOSS_LLM_BASE_URL  or OPENAI_BASE_URL   — API endpoint (default: https://api.openai.com/v1)
  BOSS_LLM_MODEL     or OPENAI_MODEL      — Model name (default: gpt-4o-mini)
"""

import argparse
import json
import os
import sys
from pathlib import Path

RESUME_FILE = Path.home() / '.hermes' / 'credentials' / 'resume.txt'


def get_llm_config():
    """Get LLM API configuration from environment."""
    api_key = os.environ.get('BOSS_LLM_API_KEY') or os.environ.get('OPENAI_API_KEY', '')
    base_url = os.environ.get('BOSS_LLM_BASE_URL') or os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    model = os.environ.get('BOSS_LLM_MODEL') or os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
    return api_key, base_url.rstrip('/'), model


def build_greeting_prompt(jd: dict, resume: str) -> str:
    """Build the prompt for LLM to generate a personalized greeting."""
    jd_text = jd.get('jd_text', '')
    title = jd.get('title', '')
    company = jd.get('company', '')
    requirements = ', '.join(jd.get('requirements', []))

    return f"""你是一位资深求职顾问。请根据以下职位描述（JD）和候选人简历，生成一条精炼的BOSS直聘打招呼消息。

## 职位信息
职位名称：{title}
公司：{company}
任职要求：{requirements}
完整JD：
{jd_text}

## 候选人简历
{resume}

## 生成规则
1. **必须基于JD和简历的实际内容**分析出2-3个最匹配的亮点（技能/经验/项目），不要泛泛而谈
2. **不要使用固定模板**，每条消息都应该是独特的，体现这个JD和这份简历的特定匹配点
3. 语气自然真诚，像在和招聘者对话，不要像在念简历
4. 开头不要用"您好"这种千篇一律的开场白，可以用更自然的方式切入
5. 体现对该公司/岗位的具体兴趣（从JD中提取线索）
6. 总长度控制在80-150个中文字符
7. 结尾礼貌地表达沟通意愿

## 输出要求
只输出招呼语正文，不要有任何前缀、后缀、引号、markdown格式或解释说明。
"""


def call_llm(prompt: str) -> str:
    """Call an OpenAI-compatible LLM API to generate the greeting."""
    api_key, base_url, model = get_llm_config()

    if not api_key:
        print("[warn] No LLM API key configured, using fallback generation", file=sys.stderr)
        return fallback_generate(prompt)

    try:
        import requests
        url = f"{base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是求职打招呼消息生成专家。只输出招呼语正文，不要有任何其他内容。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 300
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data['choices'][0]['message']['content'].strip()

        # Clean up: remove surrounding quotes if present
        if (content.startswith('"') and content.endswith('"')) or \
           (content.startswith("'") and content.endswith("'")):
            content = content[1:-1]

        return content

    except Exception as e:
        print(f"[error] LLM API call failed: {e}", file=sys.stderr)
        return fallback_generate(prompt)


def fallback_generate(prompt: str) -> str:
    """Fallback: extract key info and build a simple but personalized greeting."""
    # Parse JD and resume from the prompt
    import re

    # Extract title
    title_match = re.search(r'职位名称[：:]\s*(.+)', prompt)
    company_match = re.search(r'公司[：:]\s*(.+)', prompt)
    title = title_match.group(1).strip() if title_match else '该职位'
    company = company_match.group(1).strip() if company_match else '贵司'

    # This is a very basic fallback — the LLM path is strongly preferred
    return f"看了贵司{title}的JD，我的背景和岗位需求比较匹配，期望有机会详细聊聊。"


def main():
    parser = argparse.ArgumentParser(description='LLM-powered BOSS greeting generator')
    parser.add_argument('--jd', help='Path to JD JSON file')
    parser.add_argument('--resume', default=str(RESUME_FILE), help='Path to resume file')
    parser.add_argument('--stdin', action='store_true', help='Read JD JSON from stdin')
    parser.add_argument('--job-id', help='Fetch JD from BOSS API (requires browser context)')
    args = parser.parse_args()

    # Load JD
    if args.stdin:
        jd = json.loads(sys.stdin.read())
    elif args.jd:
        with open(args.jd, 'r', encoding='utf-8') as f:
            jd = json.load(f)
    else:
        print("[error] Must provide --jd or --stdin", file=sys.stderr)
        sys.exit(1)

    # Load resume
    resume_path = Path(args.resume)
    if not resume_path.exists():
        print(f"[error] Resume not found: {resume_path}", file=sys.stderr)
        sys.exit(1)
    resume = resume_path.read_text().strip()

    # Generate
    prompt = build_greeting_prompt(jd, resume)
    greeting = call_llm(prompt)

    # Output
    print(greeting)


if __name__ == '__main__':
    main()
