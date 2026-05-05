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
    m = re.search(r'job_detail[/\?]([^\.&?]+)', input_str)
    if m:
        return m.group(1)
    return input_str.strip()


def fetch_jd(job_input: str) -> dict:
    """用 Camoufox 获取完整 JD。

    Returns: {"title", "company", "salary", "requirements", "jd_text", "skills", "boss_name", "boss_title"}
    """
    from camoufox.sync_api import Camoufox

    job_id = extract_job_id(job_input)
    url = f"https://www.zhipin.com/job_detail/{job_id}.html"

    result = {
        "job_id": job_id,
        "title": "", "company": "", "salary": "",
        "location": "", "experience": "", "degree": "",
        "requirements": [], "jd_text": "", "skills": [],
        "boss_name": "", "boss_title": ""
    }

    with Camoufox(humanize=True, geoip=True, os="macos", block_images=False) as browser:
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        # 方法1: 从页面 DOM 直接提取
        dom_data = page.evaluate("""() => {
            const getText = (sel) => {
                const el = document.querySelector(sel);
                return el ? el.textContent.trim() : '';
            };
            const getAll = (sel) => {
                return Array.from(document.querySelectorAll(sel)).map(el => el.textContent.trim()).filter(Boolean);
            };

            return {
                title: getText('.job-name') || getText('h1') || getText('[class*="job-title"]') || getText('[class*="jobName"]'),
                salary: getText('.salary') || getText('[class*="salary"]') || getText('[class*="pay"]'),
                company: getText('.company-name a') || getText('.company-name') || getText('[class*="company"] a') || getText('[class*="brand"]'),
                location: getText('.job-area') || getText('[class*="area"]') || getText('[class*="location"]'),
                jd_text: getText('.job-detail-section') || getText('.job-sec-text') || getText('[class*="job-detail"]') || getText('[class*="description"]'),
                boss_name: getText('.boss-name') || getText('[class*="boss"] [class*="name"]'),
                boss_title: getText('.boss-title') || getText('[class*="boss"] [class*="title"]'),
                tags: getAll('.tag-list li') || getAll('[class*="tag"] li') || getAll('[class*="skill"] li'),
                requirements: getAll('.job-requirements li') || getAll('[class*="requirement"] li'),
            };
        }""")

        if dom_data and dom_data.get("title"):
            result["title"] = dom_data.get("title", "")
            result["salary"] = dom_data.get("salary", "")
            result["company"] = dom_data.get("company", "")
            result["location"] = dom_data.get("location", "")
            result["jd_text"] = dom_data.get("jd_text", "")
            result["boss_name"] = dom_data.get("boss_name", "")
            result["boss_title"] = dom_data.get("boss_title", "")
            result["skills"] = dom_data.get("tags", [])
            result["requirements"] = dom_data.get("requirements", [])
            print(f"[fetch] DOM提取成功: {result['title']} @ {result['company']}", file=sys.stderr)

        # 方法2: 从 __INITIAL_STATE__ 提取
        if not result["jd_text"]:
            state_data = page.evaluate("""() => {
                try {
                    for (const s of document.querySelectorAll('script')) {
                        const t = s.textContent;
                        if (t.includes('__INITIAL_STATE__')) {
                            const m = t.match(/__INITIAL_STATE__\\s*=\\s*({.+?})\\s*;?\\s*$/m);
                            if (m) return JSON.parse(m[1]);
                        }
                    }
                } catch(e) { return {error: e.message}; }
                return null;
            }""")

            if state_data and isinstance(state_data, dict) and not state_data.get("error"):
                _extract_from_state(state_data, result)
                if result["jd_text"]:
                    print(f"[fetch] __INITIAL_STATE__ 提取成功", file=sys.stderr)

        # 方法3: 尝试 API
        if not result["jd_text"]:
            api_data = page.evaluate(f"""() => {{
                return fetch('/wapi/zpgeek/job/detail.json?encryptJobId={job_id}')
                    .then(r => r.json())
                    .catch(e => ({{error: e.message}}));
            }}""")

            if api_data and isinstance(api_data, dict):
                code = api_data.get("code", -1)
                if code == 0:
                    zp = api_data.get("zpData", {})
                    result["title"] = zp.get("jobName", result["title"])
                    result["company"] = zp.get("brandName", result["company"])
                    result["salary"] = zp.get("salaryDesc", result["salary"])
                    result["jd_text"] = zp.get("postDescription", result["jd_text"])
                    result["skills"] = zp.get("skills", result["skills"])
                    result["boss_name"] = zp.get("bossName", result["boss_name"])
                    result["boss_title"] = zp.get("bossTitle", result["boss_title"])
                    print(f"[fetch] API提取成功", file=sys.stderr)
                else:
                    print(f"[fetch] API code={code}: {api_data.get('message', '')}", file=sys.stderr)

        page.close()

    # 清理 jd_text 中的 CSS/JS 噪音
    if result["jd_text"]:
        result["jd_text"] = _clean_jd_text(result["jd_text"])

    # 清理 boss_name 中的多余信息
    if result["boss_name"]:
        result["boss_name"] = result["boss_name"].split("\n")[0].strip()

    # 提取 requirements from jd_text if empty
    if not result["requirements"] and result["jd_text"]:
        result["requirements"] = _extract_requirements(result["jd_text"])

    result["location"] = result["location"].strip()
    return result


def _extract_from_state(data: dict, result: dict):
    """递归搜索 __INITIAL_STATE__ 中的 JD 数据。"""
    def search(obj, depth=0):
        if depth > 6 or not isinstance(obj, (dict, list)):
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("postDescription", "description") and isinstance(v, str) and len(v) > 50:
                    result["jd_text"] = v
                if k == "jobName" and isinstance(v, str) and v:
                    result["title"] = v
                if k == "brandName" and isinstance(v, str) and v:
                    result["company"] = v
                if k == "salaryDesc" and isinstance(v, str) and v:
                    result["salary"] = v
                if k == "bossName" and isinstance(v, str) and v:
                    result["boss_name"] = v
                if k == "bossTitle" and isinstance(v, str) and v:
                    result["boss_title"] = v
                if k == "skills" and isinstance(v, list):
                    result["skills"] = v
                if k in ("cityName", "areaDistrict") and isinstance(v, str) and v:
                    result["location"] = (result["location"] + " " + v).strip()
                if k in ("experienceName",) and isinstance(v, str) and v:
                    result["experience"] = v
                if k in ("degreeName",) and isinstance(v, str) and v:
                    result["degree"] = v
                search(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                search(item, depth + 1)

    search(data)


def _clean_jd_text(text: str) -> str:
    """清理 JD 文本中的 CSS/JS 噪音。"""
    import re
    # 移除 CSS 代码块
    text = re.sub(r'\.[a-zA-Z_]\w*\{[^}]*\}', '', text)
    # 移除 JS 代码
    text = re.sub(r'(?:function|var|let|const)\s.*?[{;]', '', text)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 移除 BOSS直聘 反爬水印文字
    text = re.sub(r'(?:来自|举来自|扫码|直聘码|直聘报|报错|登录查看完整内容)', '', text)
    # 移除多余空白
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def _extract_requirements(jd_text: str) -> list:
    """从 JD 文本中提取任职要求。"""
    lines = jd_text.split("\n")
    in_req = False
    reqs = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "任职要求" in line or "岗位要求" in line or "职位要求" in line or "任职资格" in line:
            in_req = True
            continue
        if in_req:
            if line.startswith(("任职", "岗位", "我们提供", "福利", "薪资")):
                break
            reqs.append(line.lstrip("0123456789.、·-• "))
    return reqs


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
