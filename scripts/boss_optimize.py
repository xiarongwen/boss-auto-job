#!/usr/bin/env python3
"""
简历优化 CLI - 根据 JD 针对性优化简历

Usage:
  python boss_optimize.py <job_id_or_url> <resume_file>

  # 示例
  python boss_optimize.py abc123jobid ~/resumes/my_resume.pdf
  python boss_optimize.py https://www.zhipin.com/job_detail/abc123.html ./resume.docx
  python boss_optimize.py abc123jobid ./resume.txt --output report.md

输出:
  1. 匹配分析（JSON）
  2. 优化建议
  3. 优化后的简历
  4. 可选保存完整报告
"""
import argparse
import json
import sys
from pathlib import Path

# 确保 scripts 目录在 path 中
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from parse_resume import parse_resume
from fetch_jd import fetch_jd
from resume_optimizer import build_analysis_prompt, build_optimize_prompt, build_full_report


def log(level, msg):
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    icons = {"info": "📋", "ok": "✅", "warn": "⚠️", "err": "❌"}
    print(f"[{ts}] {icons.get(level, '📋')} {msg}")


def main():
    parser = argparse.ArgumentParser(description="根据JD针对性优化简历")
    parser.add_argument("job", help="job_id 或 BOSS职位URL")
    parser.add_argument("resume", help="简历文件路径 (PDF/DOCX/DOC/TXT)")
    parser.add_argument("-o", "--output", help="保存报告到文件 (markdown)")
    args = parser.parse_args()

    # Step 1: 解析简历
    log("info", f"解析简历: {args.resume}")
    try:
        resume_text = parse_resume(args.resume)
        log("ok", f"简历解析成功 ({len(resume_text)} 字符)")
    except Exception as e:
        log("err", f"简历解析失败: {e}")
        sys.exit(1)

    # Step 2: 获取 JD
    log("info", f"获取JD: {args.job}")
    try:
        jd = fetch_jd(args.job)
        log("ok", f"JD获取成功: {jd.get('title', '?')} @ {jd.get('company', '?')}")
    except Exception as e:
        log("err", f"JD获取失败: {e}")
        sys.exit(1)

    # Step 3: 输出分析和优化 prompt（给 Agent 处理）
    print("\n===RESUME_OPTIMIZER===")
    print(json.dumps({
        "status": "ok",
        "jd": jd,
        "resume_length": len(resume_text),
        "analysis_prompt": build_analysis_prompt(jd, resume_text),
        "optimize_prompt": build_optimize_prompt(jd, resume_text),
    }, ensure_ascii=False, indent=2))
    print("===RESUME_OPTIMIZER_END===")

    # 保存原始数据供 Agent 使用
    data_dir = Path("/tmp/boss_optimize")
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "jd.json").write_text(json.dumps(jd, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "resume.txt").write_text(resume_text, encoding="utf-8")
    log("ok", f"数据已保存到 {data_dir}")


if __name__ == "__main__":
    main()
