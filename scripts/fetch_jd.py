#!/usr/bin/env python3
"""
JD 爬取模块 - 根据 job_id 获取完整职位描述

Usage:
  from fetch_jd import fetch_jd
  jd = fetch_jd("abc123jobid")
  jd = fetch_jd("https://www.zhipin.com/job_detail/abc123.html")
"""
import json
import sys
import re
from pathlib import Path


def extract_job_id(input_str: str) -> str:
    """从 URL 或直接 job_id 提取 encryptJobId。"""
    # 如果是 URL，提取最后的 job id
    m = re.search(r'job_detail[/\?]([^\.&?]+)', input_str)
    if m:
        return m.group(1)
    # 已经是 job_id
    return input_str.strip()


def fetch_jd(job_input: str) -> dict:
    """用 Camoufox 获取完整 JD。

    Returns: {"title", "company", "salary", "requirements", "jd_text", "skills", "boss_name", "boss_title"}
    """
    from camoufox.sync_api import Camoufox

    job_id = extract_job_id(job_input)
    url = f"https://www.zhipin.com/job_detail/{job_id}.html"

    with Camoufox(humanize=True, geoip=True, os="macos", block_images=True) as browser:
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # 从 __INITIAL_STATE__ 提取 JD
        data = page.evaluate("""() => {
            try {
                for (const s of document.querySelectorAll('script')) {
                    if (s.textContent.includes('__INITIAL_STATE__')) {
                        const m = s.textContent.match(/window\\.__INITIAL_STATE__\\s*=\\s*({.+?});/);
                        if (m) return JSON.parse(m[1]);
                    }
                }
            } catch(e) {}
            return null;
        }""")

        if not data:
            print("[warn] 无法从页面提取JD，尝试API", file=sys.stderr)
            data = page.evaluate(f"""() => {{
                return fetch('/wapi/zpgeek/job/detail.json?encryptJobId={job_id}')
                    .then(r => r.json())
                    .catch(e => ({{error: e.message}}));
            }}""")

        page.close()

    return _parse_job_data(data, job_id)


def _parse_job_data(data: dict, job_id: str) -> dict:
    """从页面数据提取结构化JD。"""
    result = {
        "job_id": job_id,
        "title": "", "company": "", "salary": "",
        "location": "", "experience": "", "degree": "",
        "requirements": [], "jd_text": "", "skills": [],
        "boss_name": "", "boss_title": ""
    }
    if not data:
        return result

    # 尝试从 __INITIAL_STATE__ 结构提取
    try:
        job_info = data.get("jobInfo", data.get("data", {}))
        if isinstance(job_info, dict):
            result["title"] = job_info.get("title", job_info.get("jobName", ""))
            result["company"] = job_info.get("brandName", job_info.get("company", ""))
            result["salary"] = job_info.get("salaryDesc", job_info.get("salary", ""))
            result["location"] = job_info.get("cityName", "") + " " + job_info.get("areaDistrict", "")
            result["experience"] = job_info.get("experienceName", "")
            result["degree"] = job_info.get("degreeName", "")
            result["jd_text"] = job_info.get("postDescription", job_info.get("jd", ""))
            result["skills"] = job_info.get("skills", [])
            result["boss_name"] = jobInfo.get("bossName", "") if isinstance(jobInfo := data.get("jobInfo", {}), dict) else ""
            result["boss_title"] = jobInfo.get("bossTitle", "") if isinstance(jobInfo, dict) else ""
    except Exception:
        pass

    # 尝试 zpData 结构 (API 返回)
    try:
        zp = data.get("zpData", {})
        if isinstance(zp, dict) and not result["title"]:
            result["title"] = zp.get("jobName", "")
            result["company"] = zp.get("brandName", "")
            result["jd_text"] = zp.get("postDescription", "")
            result["skills"] = zp.get("skills", [])
    except Exception:
        pass

    # 清理
    result["location"] = result["location"].strip()
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="获取BOSS职位完整JD")
    parser.add_argument("job", help="job_id 或 职位URL")
    parser.add_argument("-o", "--output", help="保存JSON到文件")
    args = parser.parse_args()

    jd = fetch_jd(args.job)
    output = json.dumps(jd, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"\n[ok] 已保存: {args.output}", file=sys.stderr)
