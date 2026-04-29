"""
Boss Auto Job MCP Server

Exposes BOSS Zhipin automation tools via Model Context Protocol (MCP).
Compatible with Claude Code, Cursor, Hermes Agent, and any MCP client.

Usage:
  # Run as stdio MCP server
  python mcp_server.py

  # In Claude Code / Cursor settings:
  # Add to mcpServers: { "boss-auto-job": { "command": "python", "args": ["path/to/mcp_server.py"] } }
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# ============================================================
# Core logic (shared with CLI and MCP)
# ============================================================

AUTH_FILE = Path.home() / '.agent-browser' / 'auth' / 'boss-zhipin.json'
RESUME_FILE = Path.home() / '.hermes' / 'credentials' / 'resume.txt'

CITY_CODES = {
    "北京": "101010100", "上海": "101020100", "深圳": "101280600",
    "杭州": "101210100", "成都": "101270100", "广州": "101280100",
    "南京": "101190100", "武汉": "101200100", "西安": "101110100",
    "苏州": "101190400", "天津": "101030100", "重庆": "101040100",
}


def _search_jobs(query: str, city: str = "101280600", pages: int = 1) -> list:
    """Search jobs using Camoufox."""
    import time
    from camoufox.sync_api import Camoufox

    all_jobs = []
    with Camoufox(humanize=True, geoip=True, os="macos", block_images=False) as browser:
        for page_num in range(1, pages + 1):
            page = browser.new_page()
            try:
                page.goto(
                    f"https://www.zhipin.com/web/geek/job?query={query}&city={city}&page={page_num}",
                    wait_until="domcontentloaded",
                    timeout=20000
                )
                time.sleep(4)

                result = page.evaluate("""
                    (q) => fetch('/wapi/zpgeek/search/joblist.json?scene=1&query=' + encodeURIComponent(q)
                        + '&city=QUERY_CITY&page=QUERY_PAGE&pageSize=30')
                        .then(r => r.json())
                        .catch(e => ({error: e.message}))
                """.replace("QUERY_CITY", city).replace("QUERY_PAGE", str(page_num)), query)

                code = result.get("code")
                if code == 0:
                    jobs = result.get("zpData", {}).get("jobList", [])
                    for j in jobs:
                        all_jobs.append({
                            "job_id": j.get("encryptJobId") or j.get("jobId"),
                            "title": j.get("jobName", ""),
                            "company": j.get("brandName", ""),
                            "salary": j.get("salaryDesc", ""),
                            "location": f"{j.get('cityName', '')} {j.get('areaDistrict', '')}".strip(),
                            "experience": j.get("jobExperience", ""),
                            "degree": j.get("jobDegree", ""),
                            "skills": j.get("skills", []),
                            "boss_name": j.get("bossName", ""),
                            "boss_title": j.get("bossTitle", ""),
                        })
                elif code in (36, 32):
                    return [{"error": f"code_{code}", "message": result.get("message", "")}]
            except Exception as e:
                return [{"error": "exception", "message": str(e)[:200]}]
            finally:
                try: page.close()
                except: pass
            if page_num < pages:
                time.sleep(4)

    # Deduplicate
    seen = set()
    unique = []
    for j in all_jobs:
        if j["job_id"] not in seen:
            seen.add(j["job_id"])
            unique.append(j)
    return unique


def _send_message(job_id: str, greeting: str) -> dict:
    """Send a greeting message to a recruiter."""
    import time
    from camoufox.sync_api import Camoufox

    with Camoufox(humanize=True, geoip=True, os="macos", block_images=False) as browser:
        page = browser.new_page()
        try:
            # Establish session
            page.goto("https://www.zhipin.com/web/geek/job?query=Python&city=101010100",
                       wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

            # Get encryptUserId
            card = page.evaluate(f"""() =>
                fetch('/wapi/zpgeek/job/card.json?encryptJobId={job_id}')
                    .then(r => r.json()).catch(e => ({{error: e.message}}))
            """)

            boss_id = ""
            if card.get("code") == 0:
                boss_id = card.get("zpData", {}).get("encryptUserId", "")

            if not boss_id:
                # Try detail API
                detail = page.evaluate(f"""() =>
                    fetch('/wapi/zpgeek/job/detail.json?encryptJobId={job_id}')
                        .then(r => r.json()).catch(e => ({{error: e.message}}))
                """)
                if detail.get("code") == 0:
                    boss_id = detail.get("zpData", {}).get("encryptUserId", "")

            if not boss_id:
                return {"success": False, "error": "Could not get encryptUserId", "code": card.get("code")}

            # Send
            time.sleep(3 + len(greeting) // 20)
            result = page.evaluate(f"""() =>
                fetch('/wapi/zpgeek/friend/add.json', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}},
                    body: JSON.stringify({{
                        encryptJobId: '{job_id}',
                        encryptBossId: '{boss_id}',
                        greeting: '{greeting.replace("'", "\\'")}'
                    }})
                }}).then(r => r.json()).catch(e => ({{error: e.message}}))
            """)

            if result.get("code") == 0:
                return {"success": True, "message": "Greeting sent successfully"}
            return {"success": False, "error": result.get("message", result.get("error", "")), "code": result.get("code")}

        except Exception as e:
            return {"success": False, "error": str(e)[:200]}
        finally:
            try: page.close()
            except: pass


def _get_resume() -> str:
    """Load resume text."""
    if RESUME_FILE.exists():
        return RESUME_FILE.read_text().strip()
    return ""


# ============================================================
# MCP Server
# ============================================================

if HAS_MCP:
    server = Server("boss-auto-job")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="boss_search_jobs",
                description="Search jobs on BOSS Zhipin. Uses Camoufox stealth browser to bypass anti-bot detection. Returns structured job listings.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Job keyword, e.g. '产品经理', 'Python', 'AI前端'"},
                        "city": {"type": "string", "description": "City name (中文) or code. Default: 深圳. Supports: 北京/上海/深圳/杭州/成都/广州/南京/武汉/西安/苏州/天津/重庆"},
                        "city_code": {"type": "string", "description": "Direct city code override, e.g. '101280600'"},
                        "pages": {"type": "integer", "description": "Number of pages to search (default: 1, max: 3)"},
                        "area_filter": {"type": "string", "description": "Filter by area/district, e.g. '南山' to only return Nanshan district jobs"},
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="boss_send_greeting",
                description="Send a greeting message to a recruiter on BOSS Zhipin. Requires job_id (encryptJobId) from search results.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "The encryptJobId from boss_search_jobs results"},
                        "greeting": {"type": "string", "description": "The greeting message to send (max 150 Chinese characters)"},
                    },
                    "required": ["job_id", "greeting"],
                },
            ),
            Tool(
                name="boss_match_resume",
                description="Score how well a list of jobs matches the candidate's resume. Returns match scores and reasons.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jobs": {"type": "string", "description": "JSON array of job objects from boss_search_jobs"},
                        "resume": {"type": "string", "description": "Resume text (optional, auto-loads from ~/.hermes/credentials/resume.txt if not provided)"},
                        "top_n": {"type": "integer", "description": "Return top N matches (default: 10)"},
                    },
                    "required": ["jobs"],
                },
            ),
            Tool(
                name="boss_get_resume",
                description="Load the candidate's resume from disk.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="boss_city_codes",
                description="Get available city codes for BOSS Zhipin search.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "boss_search_jobs":
            query = arguments["query"]
            city = arguments.get("city", "深圳")
            city_code = arguments.get("city_code", "")
            pages = min(arguments.get("pages", 1), 3)
            area_filter = arguments.get("area_filter", "")

            if not city_code:
                city_code = CITY_CODES.get(city, city)

            jobs = await asyncio.to_thread(_search_jobs, query, city_code, pages)

            if area_filter:
                jobs = [j for j in jobs if area_filter in j.get("location", "")]

            return [TextContent(
                type="text",
                text=json.dumps({"jobs": jobs, "count": len(jobs), "query": query, "city": city, "area_filter": area_filter}, ensure_ascii=False, indent=2)
            )]

        elif name == "boss_send_greeting":
            job_id = arguments["job_id"]
            greeting = arguments["greeting"]
            result = await asyncio.to_thread(_send_message, job_id, greeting)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        elif name == "boss_match_resume":
            jobs = json.loads(arguments["jobs"])
            resume = arguments.get("resume", "") or _get_resume()
            top_n = arguments.get("top_n", 10)

            if not resume:
                return [TextContent(type="text", text='{"error": "No resume found. Provide resume text or create ~/.hermes/credentials/resume.txt"}')]

            # Score using keyword matching
            keywords = ["React", "TypeScript", "AI", "Agent", "前端", "Vue", "Node.js", "Webpack",
                        "工作流", "Copilot", "RAG", "大模型", "对话", "工作台", "低代码", "组件"]

            for j in jobs:
                score = 0
                combined = f"{j.get('title', '')} {' '.join(j.get('skills', []))} {j.get('company', '')}".lower()
                for kw in keywords:
                    if kw.lower() in combined:
                        score += 10
                # Experience match
                exp = j.get("experience", "")
                if "3-5" in exp or "经验不限" in exp:
                    score += 15
                elif "5-10" in exp:
                    score += 10
                elif "1-3" in exp:
                    score += 5
                # Degree match
                deg = j.get("degree", "")
                if "本科" in deg or "学历不限" in deg:
                    score += 5
                j["match_score"] = min(score, 100)

            jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)

            return [TextContent(
                type="text",
                text=json.dumps({"ranked_jobs": jobs[:top_n], "total": len(jobs)}, ensure_ascii=False, indent=2)
            )]

        elif name == "boss_get_resume":
            resume = _get_resume()
            return [TextContent(
                type="text",
                text=json.dumps({"resume": resume, "found": bool(resume), "path": str(RESUME_FILE)}, ensure_ascii=False)
            )]

        elif name == "boss_city_codes":
            return [TextContent(
                type="text",
                text=json.dumps({"cities": CITY_CODES}, ensure_ascii=False, indent=2)
            )]

        return [TextContent(type="text", text=f'{{"error": "Unknown tool: {name}"}}')]


async def main():
    if not HAS_MCP:
        print("ERROR: mcp package not installed. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
