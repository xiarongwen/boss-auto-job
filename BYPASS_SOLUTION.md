# BOSS 直聘风控绕过方案

> 基于逆向分析 + GitHub 开源项目研究，针对 BOSS 4层防御的完整绕过策略。

---

## 总体策略：分层绕过

```
BOSS 4 层防御              我们的 4 层绕过
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 1: 环境检测           → rebrowser-patches / CloakBrowser / Camoufox
Layer 2: 行为分析 (Warlock) → humanize 鼠标/键盘/滚动模拟
Layer 3: 网关验证 (Gateway) → AST 解密 zp_stoken 自动注入
Layer 4: 风控引擎 (Backend) → 请求节奏控制 + Cookie 健康管理
```

---

## 方案一：rebrowser-playwright（推荐度：⭐⭐⭐⭐）

### 原理

rebrowser-patches 直接修补 Playwright/Puppeteer 源码，消除自动化库的可检测特征：

| 检测点 | 原版 Playwright | rebrowser-playwright |
|--------|-----------------|---------------------|
| `Runtime.Enable` CDP 泄露 | ❌ 被检测 | ✅ 已修补 |
| `navigator.webdriver = true` | ❌ 被检测 | ✅ 返回 false |
| `iframe.sourceURL` 泄露 | ❌ 内部URL可见 | ✅ 中性URL |
| `chrome.runtime` 异常 | ❌ 可检测 | ✅ 已修补 |
| mainWorldExecution 检测 | ❌ 被检测 | ✅ 已修补 |

### 安装

```bash
# Python（drop-in 替换 playwright）
pip install rebrowser-playwright
rebrowser-playwright install chromium

# Node.js（在 package.json 中替换）
# "playwright": "npm:rebrowser-playwright@^1.52.0"
```

### 代码

```python
# 替换 import 即可
# from playwright.sync_api import sync_playwright  # 原版
from rebrowser_playwright.sync_api import sync_playwright  # 替换后

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.zhipin.com/web/geek/job?query=Python")
    # 此时 navigator.webdriver = false，Runtime.Enable 不泄露
```

### 针对 BOSS 的适配

```python
from rebrowser_playwright.sync_api import sync_playwright

browser = p.chromium.launch(
    headless=True,
    args=[
        '--disable-blink-features=AutomationControlled',  # 额外保护
        '--no-sandbox',
    ]
)

context = browser.new_context(
    viewport={"width": 1920, "height": 1080},
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    locale="zh-CN",
    timezone_id="Asia/Shanghai",
)

# 注入登录态
context.add_cookies(load_cookies())

page = context.new_page()

# === 注入行为模拟脚本（绕过 Warlock 行为检测）===
page.add_init_script("""
    // 模拟真实鼠标移动
    let mouseX = 0, mouseY = 0;
    setInterval(() => {
        mouseX += Math.random() * 10 - 5;
        mouseY += Math.random() * 10 - 5;
        document.dispatchEvent(new MouseEvent('mousemove', {
            clientX: mouseX, clientY: mouseY
        }));
    }, 100 + Math.random() * 200);

    // 模拟随机滚动
    setInterval(() => {
        window.scrollBy(0, Math.random() * 100 - 50);
    }, 3000 + Math.random() * 5000);
""")

page.goto("https://www.zhipin.com/web/geek/job?query=Python&city=101010100")
```

### 验证效果

rebrowser 通过了以下检测：
- ✅ bot-detector.rebrowser.net (所有测试)
- ✅ navigator.webdriver = false
- ✅ Runtime.Enable 不泄露
- ✅ iframe sourceURL 中性化

### 局限

- ❌ Canvas/WebGL 指纹未处理（headless 渲染差异）
- ❌ 不处理 Proxy 检测
- ❌ 不处理字体枚举
- ⚠️ 如果 BOSS 检查 Canvas 指纹一致性，仍可能被标记

---

## 方案二：Camoufox（推荐度：⭐⭐⭐⭐⭐）

### 原理

Camoufox 基于 Firefox，在 **C++ 源码级别** 修改指纹，所有欺骗都发生在浏览器内核内部，JS 层完全无法检测。

| 检测点 | JS 注入方案 | Camoufox (C++级) |
|--------|------------|-----------------|
| Canvas 指纹 | ❌ toString() 可检测 | ✅ C++ 原生修改 |
| WebGL 指纹 | ❌ 参数可检测 | ✅ C++ 原生修改 |
| Audio 指纹 | ❌ 不完整 | ✅ 6种 Web Audio API 全覆盖 |
| 字体枚举 | ❌ 不完整 | ✅ anti-font-fingerprinting.patch |
| WebRTC IP | ❌ 不完整 | ✅ 协议级 IP 伪装 |
| 时区 | ❌ JS 级别 | ✅ per-realm DateTimeInfo |
| 屏幕尺寸 | ❌ JS 级别 | ✅ per-context 屏幕尺寸 |
| 鼠标轨迹 | ❌ 简单模拟 | ✅ C++ HumanCursor 算法 |
| Playwright 检测 | ❌ 部分可检测 | ✅ 沙箱化 Page Agent |
| navigator 属性 | ❌ defineProperty 可检测 | ✅ C++ 原生修改 |

### 安装

```bash
pip install camoufox
# 首次运行会自动下载 Firefox 二进制（~100MB）
```

### 代码

```python
from camoufox.sync_api import Camoufox

with Camoufox(
    humanize=True,           # 启用类人鼠标/键盘/滚动
    geoip=True,              # 自动根据IP设置时区/语言
    block_images=False,      # 允许图片（验证码需要）
    os="macos",              # 伪装为 macOS
) as browser:
    page = browser.new_page()
    
    # 注入 Cookie
    context = browser.contexts[0]
    context.add_cookies(load_cookies())
    
    page.goto("https://www.zhipin.com/web/geek/job?query=Python&city=101010100")
    
    # 调用 API
    result = page.evaluate("""
        () => fetch('/wapi/zpgeek/search/joblist.json?scene=1&query=Python&city=101010100&page=1&pageSize=30')
              .then(r => r.json())
    """)
    
    print(f"Code: {result['code']}")  # 应为 0
```

### BrowserForge 自动指纹

Camoufox 内置 BrowserForge，自动生成一致的浏览器指纹：

```python
from camoufox.sync_api import Camoufox
from browserforge.fingerprints import Screen

with Camoufox(
    humanize=True,
    geoip=True,
    screen=Screen(max_width=1920, max_height=1080),  # 限制屏幕尺寸范围
    navigator={
        "platform": "MacIntel",
        "hardwareConcurrency": 8,
        "deviceMemory": 16,
    },
) as browser:
    # 每次运行自动生成不同的、但内部一致的指纹
    # 不会出现 "Windows UA + Apple GPU" 这种不一致
    pass
```

### 验证效果

Camoufox 通过了所有主流检测：
- ✅ FingerprintJS (web-scraping-demo)
- ✅ Cloudflare Turnstile
- ✅ DataDome
- ✅ BrowserScan
- ✅ bot.sannysoft.com
- ✅ creepjs
- ✅ 30+ 检测站点

### 针对 BOSS 的完整方案

```python
#!/usr/bin/env python3
"""BOSS Zhipin search using Camoufox - ultimate stealth."""

import json, time
from pathlib import Path
from camoufox.sync_api import Camoufox

AUTH_FILE = Path.home() / '.agent-browser/auth/boss-zhipin.json'

def load_cookies():
    with open(AUTH_FILE) as f:
        auth = json.load(f)
    cookies = []
    for c in auth.get('cookies', []):
        cookie = {
            "name": c["name"], "value": c["value"],
            "domain": c["domain"], "path": c.get("path", "/"),
        }
        expires = c.get("expires", -1)
        if expires and expires > 0:
            cookie["expires"] = expires
        if c.get("httpOnly"):
            cookie["httpOnly"] = True
        if c.get("secure"):
            cookie["secure"] = True
        cookies.append(cookie)
    return cookies

def search_boss(query, city="101010100", page=1):
    with Camoufox(
        humanize=True,     # 类人行为
        geoip=True,        # 自动地理定位
        os="macos",        # 伪装 macOS
        block_images=False,
    ) as browser:
        context = browser.contexts[0]
        context.add_cookies(load_cookies())
        
        page_obj = context.new_page()
        
        # 访问搜索页（触发网关注入 zp_stoken）
        page_obj.goto(
            f"https://www.zhipin.com/web/geek/job?query={query}&city={city}&page={page}",
            wait_until="networkidle",
            timeout=30000
        )
        time.sleep(3)
        
        # 调用 API
        result = page_obj.evaluate("""
            (args) => fetch(
                `/wapi/zpgeek/search/joblist.json?scene=1&query=${args.q}&city=${args.c}&page=${args.p}&pageSize=30`
            ).then(r => r.json())
        """, {"q": query, "c": city, "p": page})
        
        if result.get("code") == 0:
            return result["zpData"]["jobList"]
        else:
            raise RuntimeError(f"API error: code={result['code']}, msg={result['message']}")
```

---

## 方案三：CloakBrowser（推荐度：⭐⭐⭐⭐）

### 原理

CloakBrowser 是定制的 Chromium 二进制，包含 **49 个 C++ 源码级补丁**，是所有方案中 stealth 等级最高的。

### 安装

```bash
pip install cloakbrowser
# 首次运行自动下载 stealth Chromium (~200MB)
```

### 代码

```python
from cloakbrowser import launch

browser = launch(
    humanize=True,  # 启用类人行为模拟
    proxy={
        "server": "http://proxy:port",
        "username": "user",
        "password": "pass",
    },
)
page = browser.new_page()
page.goto("https://www.zhipin.com/web/geek/job?query=Python")
browser.close()
```

### 验证效果

- ✅ Cloudflare Turnstile (非交互式)
- ✅ reCAPTCHA v3 (得分 0.9 = 人类水平)
- ✅ FingerprintJS
- ✅ BrowserScan (4/4)
- ✅ deviceandbrowserinfo.com ("You are human!")
- ✅ 30+ 检测站点全部通过

### 局限

- ⚠️ 200MB 二进制下载
- ⚠️ Python 包较新，可能不稳定
- ⚠️ 需要确认 Playwright API 兼容性

---

## 方案四：组合方案（最稳健）

将多个方案组合使用，针对 BOSS 的每一层选择最优工具：

```
┌────────────────────────────────────────────────────┐
│              最终推荐方案：Camoufox + curl_cffi       │
├────────────────────────────────────────────────────┤
│                                                    │
│  Layer 1 (环境检测):                                │
│    → Camoufox C++ 级指纹修改（Canvas/WebGL/Audio）    │
│    → humanize=True 自动鼠标/键盘/滚动模拟            │
│    → BrowserForge 一致性指纹                        │
│                                                    │
│  Layer 2 (行为分析):                                │
│    → Camoufox humanize=True（C++ HumanCursor）      │
│    → geoip=True 时区/语言自动匹配                    │
│    → 人工操作间隔（3-5秒）                           │
│                                                    │
│  Layer 3 (网关验证):                                │
│    → zp_stoken 自动生成（已有 Node.js VM 方案）       │
│    → security-js AST 解密（已有完整逆向）             │
│    → Cookie 注入（context.add_cookies）              │
│                                                    │
│  Layer 4 (风控引擎):                                │
│    → 请求节奏控制（搜索 3-5 秒，发送 5 秒）            │
│    → Code 36/32 立即停止机制                        │
│    → Cookie 健康检查（每次运行前验证）                 │
│                                                    │
│  辅助方案（纯 HTTP）:                                │
│    → curl_cffi impersonate='chrome120'              │
│    → 用于 Cookie 刷新后的快速 API 调用               │
│    → 仅用于非敏感接口（搜索、详情）                    │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## 开源项目对比表

| 项目 | 技术层级 | 浏览器 | Canvas | WebGL | Audio | 字体 | WebRTC | 鼠标 | Playwright检测 | 适合BOSS |
|------|----------|--------|--------|-------|-------|------|--------|------|---------------|---------|
| **Camoufox** | C++ | Firefox | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⭐⭐⭐⭐⭐ |
| **CloakBrowser** | C++ | Chromium | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⭐⭐⭐⭐ |
| **rebrowser** | 源码修补 | Chromium | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ⭐⭐⭐ |
| **undetected-cd** | 二进制修补 | Chromium | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ⭐⭐⭐ |
| **curl_cffi** | TLS层 | 无浏览器 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ⭐⭐ (纯HTTP) |

### 核心洞察

> **JS 级指纹修改（Object.defineProperty）始终可被检测。**
> 
> 检测方法：
> - `Object.getOwnPropertyDescriptor(navigator, 'webdriver')` → 如果返回 descriptor 说明被修改
> - `navigator.webdriver.toString()` → 如果不是 `function get webdriver() { [native code] }` 说明被修改
> - Worker 线程上下文不一致 → JS 注入只在主线程生效
>
> **C++ 级修改（Camoufox / CloakBrowser）是唯一完全不可检测的方案。**

---

## 具体实施计划

### Phase 1: 安装 Camoufox（5分钟）

```bash
pip install camoufox
camoufox fetch  # 下载 Firefox 二进制
```

### Phase 2: 创建 stealth 搜索脚本（替换 search_playwright.py）

```python
# search_camoufox.py - 基于 Camoufox 的终极搜索脚本
# 核心改进：
# 1. C++ 级指纹修改，不可检测
# 2. humanize=True 自动行为模拟
# 3. geoip=True 自动地理定位
# 4. BrowserForge 一致指纹
```

### Phase 3: Cookie 管理优化

```python
# Cookie 刷新时用 Camoufox（不是 Playwright）
# 避免触发 code 36/32
# Camoufox 的 humanize 模式让操作看起来像真人
```

### Phase 4: 发消息模块

```python
# 发消息时注入随机延迟
# 模拟阅读 JD 的时间（5-15秒）
# 模拟打字时间（基于消息长度）
# 不要在一天内发超过 20 条消息
```

### Phase 5: 监控 + 自愈

```python
# 每次 API 调用后检查 code
# code 0 → 继续
# code 37 → 自动生成 zp_stoken，重试 1 次
# code 36 → 立即停止，通知用户手动验证
# code 32 → 立即停止，通知用户手动发消息
# code 1006 → 等待 10 秒重试
```

---

## 额外建议

### 1. 代理 IP

```
BOSS 的后端会关联 IP 信誉 + TLS 指纹。
建议使用住宅代理（residential proxy），而非数据中心 IP。

推荐：
- Bright Data (最稳定)
- Oxylabs
- Smartproxy

避免：
- 免费代理
- 数据中心 IP（容易被标记）
- 频繁切换 IP（反而更可疑）
```

### 2. Cookie 新鲜度

```
Cookie 每 2.67 天过期（__zp_stoken__ 的 expires）。
建议每天用 Camoufox 打开一次 BOSS，自动刷新 Cookie。
如果超过 2 天没用，先用 refresh_cookies.py 刷新。
```

### 3. 请求频率

```
搜索 API：每天不超过 100 次（约 3 页 × 30 个关键词）
发消息：每天不超过 20 条
每次请求间隔：3-5 秒（搜索），5-10 秒（发消息）
每周至少手动正常使用 BOSS 1-2 次（维护账户信任度）
```

---

## 参考项目

| 项目 | GitHub | Stars | 用途 |
|------|--------|-------|------|
| Camoufox | github.com/daijro/camoufox | 4k+ | C++ 级指纹修改 |
| CloakBrowser | github.com/CloakHQ/CloakBrowser | 新 | 定制 Chromium |
| rebrowser-patches | github.com/rebrowser/rebrowser-patches | 2k+ | Playwright 源码修补 |
| rebrowser-playwright | github.com/rebrowser/rebrowser-playwright | 2k+ | 修补后的 Playwright |
| undetected-chromedriver | github.com/ultrafunkamsterdam/undetected-chromedriver | 12k+ | Selenium 反检测 |
| curl_cffi | github.com/lexiforest/curl_cffi | 2k+ | TLS 指纹伪装 |
| auto-zhipin | github.com/ufownl/auto-zhipin | 1k+ | BOSS 直聘自动投递 |
| BossZP-Spider | github.com/SolidifyTime/BossZP-Spider | - | BOSS Selenium 爬虫 |
