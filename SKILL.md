---
name: boss-auto-job
description: "BOSS直聘自动求职: Camoufox隐身搜索→多Agent匹配→生成打招呼→自动投递。4层反爬绕过(TLS/行为/网关/风控)，AST解密zp_stoken，Code 36/32安全停止机制。"
---

# BOSS Auto Job

## Overview

General-purpose web platform automation framework demonstrated on BOSS Zhipin. Pattern: login session persistence → data scraping → multi-agent analysis → automated action execution. Adaptable to any web platform requiring cookie-based auth and batch AI processing.

## When to Use

- Automating any web platform requiring login/session persistence
- Scraping structured data from authenticated pages
- Using multi-agent parallel analysis on scraped content
- Generating tailored content per-item based on AI analysis
- Executing browser automation actions (click, type, send) at scale
- Job hunting, social outreach, e-commerce monitoring, data collection

## Core Pattern

```
1. Login & Session Persistence
   └─ Browser login → Extract cookies → Save to ~/.hermes/credentials/
   └─ Subsequent runs: load cookies → validate → refresh if needed

2. Data Scraping
   └─ Authenticated requests with persisted cookies
   └─ HTML parsing + API fallback strategy
   └─ Output structured JSON with delimiters (===JSON_START/END===)

3. Multi-Agent Analysis
   └─ Delegate each item to subagent with structured prompt
   └─ Parallel scoring/matching/generation
   └─ Collect results, filter by threshold

4. Automated Action Execution
   └─ Generate browser action sequences (navigate, click, type, verify)
   └─ Agent executes via browser_* tools
   └─ Rate limiting between actions
```

## Prerequisites

1. Resume file at `~/.hermes/credentials/resume.txt` (plain text)
2. BOSS account (phone/password or QR code login)
3. Python 3 with `requests`, `beautifulsoup4` installed

## Workflow (BOSS Zhipin Example)

```
1. Check/Restore Login
   └─ Cookie exists? → Valid? → Proceed / Re-login
2. Search Jobs
   └─ Input job name → Search → Scrape JD list
3. Multi-Agent Match
   └─ Delegate each JD to subagent → Score 0-100
4. Filter & Rank
   └─ Sort by score → Keep top N (default 10)
5. Generate Introductions
   └─ Per JD: analyze requirements → generate tailored intro
6. Send Applications
   └─ Per target JD: send with generated intro
```

## Adaptation Guide

To adapt this pattern to another platform:

1. **Replace login URL** in `login.py` → target platform login page
2. **Replace search endpoint** in `search.py` → target platform search API/HTML
3. **Adjust prompt template** in `match.py` → your analysis criteria
4. **Adjust generation prompt** in `generate.py` → your output format
5. **Adjust selectors** in `send.py` → target platform DOM selectors

## Step 1: Login & Session

**First run:**
```bash
python scripts/login.py
```
- Opens browser to BOSS login page
- User completes login manually
- Saves cookies to `~/.hermes/credentials/boss_cookies.json`

**Subsequent runs:**
- Script loads cookies automatically
- Validates session with a profile page check
- If expired, prompts re-login

## Step 2: Search Jobs

### Camoufox Mode (PRIMARY — Recommended)

Uses Camoufox (C++ level Firefox fingerprint spoofing) to bypass ALL 4 layers of BOSS anti-bot detection.

```bash
python scripts/search_camoufox.py "产品经理" --city=101010100 --pages=3
```

**Why Camoufox wins:**
- C++ level Canvas/WebGL/Audio/Font fingerprint spoofing (not JS injection)
- humanize=True: C++ HumanCursor mouse/keyboard/scroll simulation
- geoip=True: auto timezone/locale from IP
- BrowserForge: real-world device fingerprint distribution
- Passes: FingerprintJS, Cloudflare, DataDome, BrowserScan, CreepJS
- **No login cookies required** — verified: Code 0 without any cookies

**Tested result:**
```
普通 Playwright + Cookie → Code 0 (but gets Code 36 after heavy use)
Camoufox without Cookie  → Code 0 (passes all 4 layers automatically)
```

### Legacy: Playwright Mode (Fallback)

If Camoufox is not installed, use Playwright with user cookies:

```bash
python scripts/search_playwright.py "产品经理" 101010100 1
```

Requires: valid cookies in `~/.agent-browser/auth/boss-zhipin.json`

### Legacy: Chrome CDP Mode (Fallback)

Controls user's real Chrome browser via remote debugging port:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --remote-allow-origins='*'
python scripts/search_chrome_cdp.py "产品经理" --city=101010100 --pages=3
```

### Legacy: curl_cffi Mode (HTTP only)

TLS fingerprint bypass without browser:

```bash
python scripts/search_curl_cffi.py "产品经理" --city=101010100
```

Note: curl_cffi bypasses TLS fingerprint but cannot pass behavior detection (code 37).

**BOSS renders job cards on `<canvas>` to prevent DOM scraping.** Always use the API (`/wapi/zpgeek/search/joblist.json`) instead of parsing HTML.

**Output format:**
[
  "https://www.zhipin.com/web/geek/job?query=产品经理&city=101010100&page=1",
  "https://www.zhipin.com/web/geek/job?query=产品经理&city=101010100&page=2"
]
```

**Agent workflow per URL:**
1. `browser_navigate(url)` — open search page
2. `browser_snapshot(full=true)` — get page HTML
3. Pass HTML to `extract_jobs_from_page()` (built into script)
4. Wait 2-3 seconds between pages

**Output format:**
```json
[
  {
    "job_id": "123456",
    "title": "高级产品经理",
    "company": "某某科技",
    "salary": "25-40K",
    "location": "北京·朝阳区",
    "requirements": ["3-5年经验", "本科", "电商经验"],
    "jd_text": "负责...",
    "boss_name": "张先生",
    "boss_title": "HR"
  }
]
```

## Step 3: Multi-Agent Resume Matching

Use `delegate_task` with parallel subagents. Each subagent receives:
- One JD (title, requirements, jd_text)
- Resume content from `resume.txt`

**Subagent prompt:**
```
You are a professional HR recruiter. Compare this JD against the candidate's resume.

JD: {jd_text}
Resume: {resume_content}

Score 0-100 based on:
- Skills match (40%)
- Experience relevance (30%)
- Education fit (10%)
- Industry alignment (20%)

Return ONLY JSON: {"score": 85, "reason": "brief explanation"}
```

**Parallel execution (max 3 concurrent — batch accordingly):**
```python
# delegate_task maxes at 3 concurrent children
# Batch 10 jobs into 3-4 subagent calls, each scoring 3-4 jobs
tasks = [
    {"goal": "Score these 3 jobs", "context": f"JDs: {batch1}\nResume: {resume}", "toolsets": []},
    {"goal": "Score these 3 jobs", "context": f"JDs: {batch2}\nResume: {resume}", "toolsets": []},
    {"goal": "Score these 4 jobs", "context": f"JDs: {batch3}\nResume: {resume}", "toolsets": []},
]
delegate_task(tasks=tasks)
```

## Step 4: Filter & Rank

Collect all scores, sort descending. Default keep top 10.

## Step 5: Generate Introduction (Agent-Powered)

**不再使用固定模板，也不调外部 API。** 招呼语由 Agent 自己根据 JD 和简历的内容直接生成。

Agent 就是 LLM，它读取搜索结果中的 JD 信息和简历内容后，直接写出个性化招呼语。
无需额外的 Python 脚本或 API 配置。

### 生成规则（Agent 内部遵循）
- 基于 JD 和简历的实际内容分析 2-3 个匹配亮点（技能/经验/项目）
- 不使用固定模板，每条消息都独特
- 语气自然真诚，像在和招聘者对话
- 不以"您好"千篇一律开头，用更自然的方式切入
- 体现对该具体公司/岗位的兴趣（从 JD 中提取线索）
- 控制在 80-150 个中文字符
- 结尾礼貌表达沟通意愿

### Agent 工作流
```
1. 搜索结果返回后，Agent 读取每个职位的 title、company、requirements、jd_text
2. 读取 resume.txt
3. 对每个职位，Agent 直接生成个性化招呼语（这一步不需要调任何工具）
4. 用 send_camoufox.py <job_id> "招呼语" 发送
```

## Step 6: Send Application

**Critical: `encryptUserId` is NOT returned by the search API.**
You must fetch it from the job detail API:
```
/wapi/zpgeek/job/card.json?encryptJobId={job_id}
```
Or use `search_playwright.py` which runs inside a browser context where you can call both APIs.

```bash
python scripts/send_v2.py --job-id=123456 --intro="生成的介绍"
```
- Uses browser automation to open chat
- Pastes introduction
- Sends message

## File Structure

```
boss-auto-job/
  SKILL.md                    # Main docs
  REVERSE_ENGINEERING.md      # BOSS anti-bot reverse engineering report
  BYPASS_SOLUTION.md          # Bypass strategy with GitHub projects
  scripts/
    boss_apply.py             # 🎯 One-click pipeline (Camoufox)
    search_camoufox.py        # 🏆 Search via Camoufox (PRIMARY)
    send_camoufox.py          # 🏆 Send via Camoufox (PRIMARY)
    search_playwright.py      # Search via Playwright (legacy)
    search_chrome_cdp.py      # Search via Chrome CDP (legacy)
    search_curl_cffi.py       # Search via curl_cffi (legacy)
    search_browser.py         # Search via browser automation (legacy)
    search.py                 # requests-based search (deprecated)
    match.py                  # Multi-agent matching orchestrator
    generate.py               # Introduction prompt builder (reference)
    send_final.py             # Message sender (legacy)
    refresh_cookies.py        # Cookie refresh tool
    login.py                  # Login helper
    orchestrator.py           # Full pipeline orchestrator
```

### Script Priority

| Priority | Script | Command | Status |
|----------|--------|---------|--------|
| 🥇 | `search_camoufox.py` | `python search_camoufox.py "产品经理"` | ✅ Best stealth |
| 🥇 | `send_camoufox.py` | `python send_camoufox.py <job_id> "msg"` | ✅ Best stealth |
| 🥇 | `boss_apply.py` | `python boss_apply.py "产品经理" --send` | ✅ One-click |
| 🥈 | `search_playwright.py` | `python search_playwright.py "产品经理" 101010100 1` | ⚠️ Legacy |
| 🥉 | `search_chrome_cdp.py` | `python search_chrome_cdp.py "产品经理"` | ⚠️ Legacy |

## Anti-Bot Research Notes

### Reusable Pattern: AST Deobfuscation + Token Bypass

This pattern applies to any web platform using dynamically loaded obfuscated JS for bot detection:

1. **Capture the redirect** — Note the 302 location and extract parameters (seed, ts, name)
2. **Fetch the security JS** — `security-js/{name}.js` (or equivalent endpoint)
3. **AST parse to find the encryption entry point** — Look for `window.ABC` or similar global constructor
4. **Execute in Node.js VM** — Replicate minimal browser environment (`window`, `document`, `navigator`, `location`)
5. **Generate the token** — Call the exposed method with correct parameters
6. **Inject via CDP** — Use `Network.setCookie` to inject into real browser
7. **Navigate to target** — Bypass complete

### AST Deobfuscation Results (BOSS Zhipin)

BOSS security-check uses dynamically named JS files (`security-js/{hash}.js`) with the following structure:

```javascript
// IIFE pattern, exposes window.ABC
(function() {
  window.md5 = ...
  window.s = ...
  window.ABC = function() {
    this.z = function(seed, ts) {
      // Complex string manipulation using md5 + timestamp
      // Returns base64-like encoded string (265 chars)
    }
  }
})();
```

**Key parameters:**
- `seed`: Random string from redirect URL (URL-encoded base64)
- `ts`: Timestamp from redirect URL
- `name`: JS file identifier (e.g., `b23b7024`)
- `offset`: `new Date().getTimezoneOffset()` (China = -480)
- Formula: `parseInt(ts) + 60 * (480 + offset) * 1000`

**Security check page flow:**
1. Browser hits 302 redirect to `security-check.html`
2. Page creates iframe, loads `security-js/{name}.js`
3. JS executes, `window.ABC` becomes available
4. Page calls `new ABC().z(seed, adjusted_ts)` → generates `__zp_stoken__`
5. Sets cookie: `__zp_stoken__={token}; domain=.zhipin.com; path=/; expires={now+2304e5}`
6. Redirects to `callbackUrl`

**Why requests alone fails:**
Even with correct `zp_stoken`, BOSS detects non-browser TLS fingerprint and missing browser APIs. The token alone is necessary but not sufficient.

**Why CDP works:**
Chrome CDP controls a real browser instance. When we inject the `zp_stoken` cookie via `Network.setCookie`, the browser presents a legitimate environment (correct TLS, canvas, WebGL, etc.), passing all checks.

### API Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Process job data |
| 37 | Environment abnormal | Auto-generate `zp_stoken` (see below) |
| 36 | Account flagged | User must manually verify in browser, then run `refresh_cookies.py` |
| 32 | Account banned temporarily | More severe than 36. Stop all automation. User must manually verify AND send a message in their browser to restore full access. |
| 1006 | Rate limited | Wait 10s and retry |

### curl_cffi TLS Fingerprint Bypass

`curl_cffi` with `impersonate='chrome120'` mimics Chrome's TLS/JA3 fingerprint. This alone is enough to pass Layer 2 (environment fingerprinting) — the page loads as 200 instead of 302. However, if the account itself is flagged (code 36), even correct TLS fingerprint won't help. The user must manually verify first.

**Tested flow:**
1. `curl_cffi.get(page_url, impersonate='chrome120')` → 200 ✅ (not 302)
2. `curl_cffi.get(api_url, impersonate='chrome120')` → code 36 or 37
3. If code 37: generate `zp_stoken` via Node.js VM, inject cookie, retry → code 0 or 36
4. If code 36: must run `refresh_cookies.py` for manual verification

### Cookie Refresh Workflow

When cookies are expired or account is flagged (code 36):

```bash
cd ~/.hermes/skills/productivity/boss-auto-job/scripts
python refresh_cookies.py
```

This opens a visible Chromium window with existing cookies loaded. If verification appears, user completes it manually. Script detects successful login, exports updated cookies to `~/.agent-browser/auth/boss-zhipin.json`, and validates the API.

**Cookie source file:** `~/.agent-browser/auth/boss-zhipin.json` (Playwright CDP format with `cookies` array containing `name`, `value`, `domain`, `path`, `expires`, `httpOnly`, `secure` fields)

### Adapting to Other Platforms

To adapt this bypass pattern to another platform:

1. **Trigger the security check** — Visit a protected page, capture the 302 redirect URL
2. **Identify the JS source** — Check the redirect page HTML for `<script src="...">` tags
3. **Fetch and AST parse** — Use Node.js `esprima` or manual regex to find the global constructor
4. **Replicate the browser env** — Create a `vm.Context` with `window`, `document`, `navigator`, `location`
5. **Call the encryption method** — Pass the extracted parameters (seed, ts, etc.)
6. **Inject the resulting cookie** — Via CDP `Network.setCookie` or browser automation
7. **Navigate to the original target** — The security check should now pass

## One-Click Pipeline: `boss_apply.py` (Camoufox Edition)

```bash
cd ~/.hermes/skills/productivity/boss-auto-job/scripts

# 搜索+匹配+生成（不发送）
python boss_apply.py "产品经理"

# 搜索+匹配+生成+发送
python boss_apply.py "产品经理" --send

# 指定城市、页数、Top N
python boss_apply.py "产品经理" --city=101020100 --pages=2 --top=5

# 模拟发送（不实际发消息）
python boss_apply.py "产品经理" --send --dry-run

# 单独搜索
python search_camoufox.py "Python" --city=101010100 --pages=3

# 单独发送
python send_camoufox.py <job_id> "你好，我对这个职位很感兴趣"
```

**底层引擎: Camoufox (C++级Firefox指纹修改)**
- `pip install "camoufox[geoip]"`
- humanize=True: C++ HumanCursor 鼠标/键盘/滚动模拟
- geoip=True: 自动根据IP设置时区/语言
- BrowserForge: 统计分布的真实设备指纹
- 无需登录Cookie即可通过BOSS所有4层风控检测
- 安装: `camoufox fetch` (下载~100MB Firefox二进制)

### Agent Workflow (使用 boss_apply.py)

1. **运行搜索**: `python boss_apply.py "关键词" --send`
2. **解析输出**: 从 `===SEARCH_RESULT===` 块提取 jobs 列表（含 JD 详情）
3. **并行匹配**: 用 `delegate_task(tasks=batches)` 对每批3个职位打分
4. **排名筛选**: 按分数排序，取 Top N
5. **生成招呼语**: Agent 直接根据每个职位的 JD + 简历生成个性化招呼语（不调工具）
6. **发送消息**: `python send_camoufox.py <job_id> "招呼语"`，间隔 5 秒

### 完整 Agent 代码模板

```
# 1. 搜索
terminal("cd scripts && python boss_apply.py '产品经理' --send")
# 解析 SEARCH_RESULT 块中的 first_5、jobs_file 等

# 2. 匹配（每批3个，delegate_task max 3 concurrent）
delegate_task(tasks=[
  {"goal": "Score these 3 jobs...", "context": "Resume: ...\nJob 1: ...\nJob 2: ...\nJob 3: ...", "toolsets": []},
  {"goal": "Score these 3 jobs...", "context": "...", "toolsets": []},
  {"goal": "Score these 4 jobs...", "context": "...", "toolsets": []},
])

# 3. 排名+生成招呼语
# 取 score >= 60 的职位，delegate_task 生成打招呼语

# 4. 发送（间隔 3 秒，每次发完检查返回码）
```

## ⚠️ CRITICAL SAFETY RULES

### API 错误码处理（必须遵守）

| Code | 含义 | 正确操作 | ❌ 错误操作 |
|------|------|----------|-------------|
| 0 | 成功 | 处理数据 | — |
| 37 | 环境异常 | 自动生成 zp_stoken 重试一次 | 反复重试 |
| 36 | 账户异常 | **立即停止**，告诉用户手动验证 | 换脚本重试 |
| 32 | 账户封禁 | **立即停止**，告诉用户手动发消息恢复 | 继续搜索 |

### 遇到 Code 36/32 时的 Agent 操作

```
1. 停止所有自动化操作
2. 告诉用户:
   - Code 36: "BOSS 检测到异常，请在 Chrome 中打开 zhipin.com 完成验证后告诉我"
   - Code 32: "BOSS 账户被临时封禁。请：① 在 Chrome 中完成验证 ② 随便找一个职位点'立即沟通'发一条消息"
3. 等待用户确认恢复
4. 确认后用 AppleScript 导出 Cookie:
   osascript -e 'tell application "Google Chrome" to tell active tab of front window to return execute javascript "document.cookie"'
5. 合并 Cookie 并保存到 ~/.agent-browser/auth/boss-zhipin.json
6. 再恢复自动化
```

### 频率限制规则

- 搜索 API：每次间隔 **3-5 秒**
- 发消息 API：每次间隔 **5 秒**
- 单次运行最多搜索 **3 页**
- 单次运行最多发送 **5 条消息**
- 收到 code 1006（限速）时等待 **10 秒**

## Agent Workflow: When Code 36 Appears

When the agent encounters code 36 ("您的账户存在异常行为") during any API call:

1. **Stop all automated operations immediately** — don't keep retrying
2. **Tell the user**: "BOSS 检测到异常行为，请在你的 Chrome 中打开 https://www.zhipin.com ，完成安全验证后告诉我"
3. **Wait for user confirmation** — they will manually complete verification
4. **After confirmation**: use AppleScript to export cookies (see Cookie Export below)
5. **Then resume** the automation

**Never try to auto-solve code 36** — it requires human verification (Geetest CAPTCHA).

## Agent Workflow: When Code 32 Appears

Code 32 ("已暂时被禁止使用") is more severe than 36. The user's account is temporarily banned from detail/send APIs.

1. **Stop immediately** — same as code 36
2. **Tell the user**: "BOSS 账户被临时封禁。请在你的 Chrome 中完成两步：① 打开 zhipin.com 完成验证 ② 随便找一个职位点'立即沟通'发一条消息"
3. **The manual message is critical** — BOSS's risk engine uses it as a trust signal to restore API access
4. **After confirmation**: export cookies via AppleScript and retry
5. **Search API may still work (code 0) even when detail/send return code 32** — this is expected

## Cookie Export from User's Chrome

When `refresh_cookies.py` can't launch a visible browser (missing Playwright browser install), ask the user to export cookies manually:

1. User opens https://www.zhipin.com in their Chrome (must be logged in)
2. User presses `Cmd+Option+I` → Console tab
3. User runs:
```javascript
copy(JSON.stringify({cookies: document.cookie.split('; ').map(c => {const [n,...v]=c.split('='); return {name:n, value:v.join('='), domain:'.zhipin.com', path:'/', expires:-1, size:v.join('=').length, httpOnly:false, secure:false, session:true};}), origins:[]}, null, 2))
```
4. Content is now on clipboard. Agent saves it with:
```bash
pbpaste > ~/.agent-browser/auth/boss-zhipin.json
```

**Note:** This only gets non-HttpOnly cookies. Key cookies (`wt2`, `zp_at`, `bst`) ARE accessible via `document.cookie` and are sufficient for the search API to work.

**AppleScript fallback (when DevTools is blocked):** BOSS auto-closes the page when DevTools opens (anti-debug). If user can't open Console, use AppleScript to read cookies directly from their running Chrome:
```bash
osascript -e 'tell application "Google Chrome" to tell active tab of front window to return execute javascript "document.cookie"'
```
This returns all non-HttpOnly cookies as a single string. Parse and save:
```python
raw = "lastCity=101280600; __g=-; bst=xxx; ..."
cookies = {k: v for k, v in (p.split('=', 1) for p in raw.split('; ') if '=' in p)}
# Merge with existing auth file to preserve httpOnly cookies (wt2, zp_at, etc.)
```
The merged result (fresh non-HttpOnly + stale httpOnly) works for the search API.

**Important:** After any verification/code-36 recovery, user MUST also send a manual message to any BOSS recruiter in their browser. This signals to BOSS's risk engine that the account is active and human-operated, restoring full API access for detail/send endpoints.

## Reverse Engineering Report

Full reverse engineering analysis: `REVERSE_ENGINEERING.md` in skill directory.

## Bypass Solution

Full bypass strategy based on GitHub open source research: `BYPASS_SOLUTION.md` in skill directory.

Recommended approach (ranked):
1. **Camoufox** (`pip install camoufox`) — C++ level fingerprint spoofing, humanize=True, geoip=True, passes all 30+ detection sites
2. **CloakBrowser** (`pip install cloakbrowser`) — Custom Chromium with 49 C++ patches, passes Cloudflare/reCAPTCHA/FingerprintJS
3. **rebrowser-playwright** (`pip install rebrowser-playwright`) — Drop-in Playwright replacement fixing Runtime.Enable leak + navigator.webdriver
4. **curl_cffi** (already installed) — TLS/JA3 fingerprint for pure HTTP requests (no browser)

Key insight: JS-level fingerprint spoofing (Object.defineProperty) is ALWAYS detectable via toString()/getOwnPropertyDescriptor/Worker context mismatch. C++ level modification (Camoufox/CloakBrowser) is the only truly undetectable approach.

Key findings:
- 853 anti-bot patterns in app.js (2.4MB bundle)
- 4-layer defense: Environment → Behavior (Warlock) → Gateway (zp_stoken) → Risk Engine (Backend)
- Warlockdata.js (70KB) collects: click, input, focus, scroll, visibility, ajaxError events
- Patas.js (113KB) APM: LCP/FID/CLS/FP/FCP, resource timing, JS errors
- XOR-encoded risk constants (2539 strings)
- Proxy detection (64 occurrences) catches Playwright/Puppeteer
- Canvas/WebGL fingerprinting (16+14 occurrences)
- Geetest CAPTCHA integration via captcha-sdk@5.1.2.min.js
- Error code cascade: 0 → 37 (env) → 36 (account) → 32 (banned)
- API endpoints: shink.zhipin.com, warlock.zhipin.com, logapi.zhipin.com

## Common Mistakes

- **Resume too long:** Keep resume.txt under 1000 words for better matching
- **Cookie expired:** Always validate session before search
- **Rate limiting:** Add 2-3 second delays between sends
- **JD changes:** Re-scrape JDs if search is >1 day old
- **delegate_task max is 3 concurrent**: Batch jobs into groups of 3-4 for parallel matching
- **Navigation timeout**: Use `wait_until="networkidle"` and increase timeout to 30s for BOSS pages
- **evaluate after navigation fails**: Page.evaluate() throws "Execution context was destroyed" if page navigated during evaluation. Always wait for `networkidle` before evaluating.
- **About:blank fallback**: If page.goto() lands on about:blank, the cookies are likely expired or session is invalid. Re-run `refresh_cookies.py` or ask user to re-export cookies.
- **Camoufox contexts is empty**: `Camoufox()` returns a standard Playwright `Browser` object, but `browser.contexts` is an empty list at start. Use `browser.new_page()` directly — NOT `browser.contexts[0].new_page()`. The latter throws `IndexError: list index out of range`.
- **Camoufox page timeout on second query**: When calling multiple `page.goto()` in sequence, the second one may fail with `TargetClosedError`. Fix: create a new page per query with `page = browser.new_page()` and `page.close()` after each, instead of reusing one page.
- **Camoufox `wait_until` safety**: Use `wait_until="domcontentloaded"` instead of `wait_until="networkidle"` for BOSS pages. The `networkidle` timeout is unreliable with BOSS's continuous polling scripts (warlock, patas, heartbeat).
- **GitHub repo published**: The skill is published at https://github.com/xiarongwen/boss-auto-job

## Security Notes

- Cookies stored in plain JSON (consider encrypting)
- Don't share credential directory
- BOSS may detect automation; use reasonable delays

## Known Limitations

1. **Geetest CAPTCHA** — BOSS Zhipin uses Geetest (极验) point-select verification for suspicious accounts. Cannot be automated.
   - **Solution**: Run `refresh_cookies.py` to open a visible browser, complete verification manually, script auto-saves new cookies
   - **Chrome CDP mode**: Use `search_chrome_cdp.py` to control your real Chrome browser (completely bypasses detection)
2. **Account-level flag (code 36)** — When BOSS flags an account (not just environment), manual verification is required. No programmatic bypass exists.
   - **Detection**: API returns `{"code": 36, "message": "您的账户存在异常行为"}`
   - **Fix**: `python refresh_cookies.py` → complete verification → cookies auto-exported
3. **Canvas-rendered job cards** — BOSS renders job listing cards on `<canvas>` elements to prevent text scraping from the DOM. Even when the page loads successfully, `document.querySelectorAll('.job-card')` returns empty.
   - **Workaround**: Use the API (`/wapi/zpgeek/search/joblist.json`) instead of DOM scraping
   - **The API requires**: valid auth cookies + `__zp_stoken__` + correct TLS fingerprint
4. **Environment fingerprinting** — BOSS detects non-browser TLS/JA3 fingerprints. `requests` alone will always fail with "您的环境存在异常" (code: 37). Use `curl_cffi` with `chrome120` impersonation or real browser.
5. **Playwright Chromium install** — `playwright install chromium` requires ~100MB disk space and may fail with ENOSPC. Use Chrome CDP mode instead if disk is tight.
6. **Rate limiting** — Search and send APIs have undisclosed rate limits. Add 2-3 second delays between requests.
7. **DOM changes** — BOSS frontend updates frequently. `send.py` selectors may need adjustment after major UI updates.
8. **DevTools anti-debug** — BOSS detects and auto-closes pages when DevTools (F12 / Cmd+Option+I) opens. This makes Console-based cookie export impossible. Use AppleScript instead (see Cookie Export section).
9. **Partial cookie set** — `document.cookie` returns ~16 cookies (non-HttpOnly). HttpOnly cookies (`wt2`, `zp_at`, `wbg`) must come from the existing auth file. Merge fresh non-HttpOnly + stale HttpOnly cookies for best results.
10. **Code 32 vs 36 cascade** — When automation is heavy, BOSS escalates: code 0 (normal) → 37 (env check) → 36 (account flagged) → 32 (temporarily banned). Stop at the first sign of 36. Don't push through to 32.
- Respect robots.txt and terms of service

## Cross-Agent CLI

The project also has a standalone CLI (`boss`) and cross-agent config files:

```
boss-auto-job/
  boss                  # CLI entry point (chmod +x, Python shebang)
  AGENTS.md             # Agent-agnostic skill instructions
  CLAUDE.md             # = AGENTS.md (Claude Code auto-reads)
  .cursorrules          # = AGENTS.md (Cursor auto-reads)
```

**Usage from any Agent CLI:**
```bash
./boss search "Agent应用开发" --city 深圳 --area 南山 --match --top 5
./boss search "AI前端" --city 深圳 --match --send
./boss send <job_id> "你好"
```

**GitHub repo:** https://github.com/xiarongwen/boss-auto-job

The CLI wraps search_camoufox.py and send_camoufox.py with a unified interface.
AGENTS.md teaches any Agent CLI how to use the `boss` command.

## Testing Notes

From testing this pattern:
- `execute_code` may cache old module versions — use subprocess for reliable CLI testing
- JSON output from scripts should use delimiters (`===JSON_START/END===`) to avoid regex matching issues with log prefixes like `[match]`
- Browser action sequences should handle both direct URLs (with entity ID) and indirect flows (click to open interaction)
- Cookie validation endpoint should be lightweight (profile/status API, not full page load)
- **Bot detection fallback pattern**: When requests fail with environment errors, immediately pivot to browser-based navigation + HTML extraction instead of trying to fix headers
- **Subagent containment**: Always include "ABSOLUTE RULES" in prompts forbidding external file searches — subagents will otherwise search the filesystem and use unrelated resumes
- **Cookie format compatibility**: `.agent-browser/auth/*.json` uses Puppeteer/Playwright format with `cookies` array — convert to `requests` dict by filtering on domain and extracting `name`/`value` pairs
- **JS reverse engineering works**: BOSS's `__zp_stoken__` can be generated server-side by fetching `security-js/{name}.js` and executing in Node.js VM. See `search_chrome_cdp.py::bypass_security_check()` and `search_curl_cffi.py::generate_zp_stoken()`. However, the token alone is not sufficient — TLS fingerprint must also match.
