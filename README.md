# 🎯 Boss Auto Job

> 自动在 BOSS 直聘上搜索职位、智能匹配简历、生成个性化打招呼语、自动发送消息。

基于 **Camoufox**（C++ 级 Firefox 指纹修改）绕过 BOSS 直聘全部 4 层反爬虫检测。

## ✨ 特性

- 🔍 **智能搜索** — 自动搜索职位，支持多城市、多页
- 🧠 **AI 匹配** — 多 Agent 并行打分，基于简历匹配最合适的职位
- ✍️ **个性生成** — 根据 JD 自动生成定制打招呼语
- 📤 **自动发送** — 一键发送消息给招聘者
- 🛡️ **完全隐身** — Camoufox C++ 级指纹修改，通过所有反 bot 检测
- 🔐 **安全机制** — 检测到风控自动停止，不会导致账户封禁

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                   Boss Auto Job                          │
├──────────┬──────────┬───────────┬───────────────────────┤
│ Camoufox │ AST 解密  │ 多Agent    │   安全策略            │
│ (引擎)    │ (Gateway)│ (匹配)     │   (风控防护)          │
│ C++ 指纹  │ zp_stoken│ 并行打分    │   Code 36/32 停止     │
└────┬─────┴────┬─────┴─────┬─────┴──────────┬────────────┘
     │          │           │                │
     ▼          ▼           ▼                ▼
┌─────────────────────────────────────────────────────────┐
│                   BOSS 直聘                               │
├──────────┬──────────┬───────────┬───────────────────────┤
│ 环境检测  │ 行为分析  │ 网关验证    │   风控引擎            │
│ TLS/Canvas│ Warlock  │ zp_stoken  │   账户/IP/设备        │
└──────────┴──────────┴───────────┴───────────────────────┘
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装 Camoufox（C++ 级隐身浏览器）
pip install "camoufox[geoip]"

# 下载 Firefox 二进制（~100MB）
camoufox fetch
```

### 2. 准备简历

```bash
# 创建简历文件
mkdir -p ~/.hermes/credentials
echo "你的简历内容（一句话即可）" > ~/.hermes/credentials/resume.txt
```

### 3. 一键运行

```bash
# 搜索 + 匹配 + 生成打招呼语
python scripts/boss_apply.py "产品经理"

# 搜索 + 匹配 + 生成 + 自动发送
python scripts/boss_apply.py "产品经理" --send

# 指定城市（上海）
python scripts/boss_apply.py "产品经理" --city=101020100

# 只看 Top 5
python scripts/boss_apply.py "产品经理" --top=5
```

### 4. 单独使用

```bash
# 只搜索
python scripts/search_camoufox.py "Python" --city=101010100 --pages=3

# 只发送消息
python scripts/send_camoufox.py <job_id> "你好，我对这个职位很感兴趣"
```

## 📁 项目结构

```
boss-auto-job/
├── README.md                   # 本文件
├── SKILL.md                    # 完整技术文档
├── REVERSE_ENGINEERING.md      # BOSS 风控逆向分析报告
├── BYPASS_SOLUTION.md          # 绕过方案（整合 8 个开源项目）
├── LICENSE                     # MIT License
└── scripts/
    ├── boss_apply.py           # 🎯 一键流水线
    ├── search_camoufox.py      # 🔍 Camoufox 搜索（推荐）
    ├── send_camoufox.py        # 📤 Camoufox 发送（推荐）
    ├── search_playwright.py    # 搜索（Playwright，legacy）
    ├── search_chrome_cdp.py    # 搜索（Chrome CDP，legacy）
    ├── search_curl_cffi.py     # 搜索（curl_cffi，legacy）
    ├── match.py                # 匹配（多 Agent 并行）
    ├── generate.py             # 生成（打招呼语）
    └── refresh_cookies.py      # Cookie 刷新工具
```

## 🛡️ BOSS 风控机制分析

BOSS 直聘采用 **4 层纵深防御**：

| 层级 | 机制 | 说明 |
|------|------|------|
| Layer 1 | 环境检测 | TLS 指纹、Canvas/WebGL、navigator.webdriver |
| Layer 2 | 行为分析 | 鼠标轨迹、键盘时序、滚动模式（Warlock） |
| Layer 3 | 网关验证 | `__zp_stoken__` 加密 token（security-js AST 解密） |
| Layer 4 | 风控引擎 | 账户风险评分、IP 信誉、设备指纹 |

**Camoufox 如何绕过：**
- ✅ C++ 级 Canvas/WebGL/Audio 指纹修改（不可被 JS 检测）
- ✅ humanize=True：C++ HumanCursor 鼠标/键盘/滚动模拟
- ✅ geoip=True：自动时区/语言匹配
- ✅ BrowserForge：真实设备指纹分布
- ✅ 安全网关：zp_stoken 自动生成

详细分析见 [REVERSE_ENGINEERING.md](./REVERSE_ENGINEERING.md)

## 🔧 API 错误码处理

| Code | 含义 | 处理策略 |
|------|------|----------|
| 0 | 成功 | 正常处理 |
| 37 | 环境异常 | 自动生成 zp_stoken，重试 1 次 |
| 36 | 账户异常 | **立即停止**，通知用户手动验证 |
| 32 | 账户封禁 | **立即停止**，通知用户手动发消息恢复 |
| 1006 | 限速 | 等待 10 秒后重试 |

**关键原则：绝不重试 Code 36/32，否则会升级封禁！**

## 📊 频率限制

| 操作 | 限制 |
|------|------|
| 搜索 API | 间隔 3-5 秒 |
| 发消息 API | 间隔 5 秒 |
| 单次运行搜索 | 最多 3 页 |
| 单次运行发送 | 最多 5 条消息 |
| 每日发送上限 | 20 条 |

## 🗺️ 城市代码

| 代码 | 城市 |
|------|------|
| 101010100 | 北京 |
| 101020100 | 上海 |
| 101280600 | 深圳 |
| 101210100 | 杭州 |
| 101270100 | 成都 |
| 101030100 | 天津 |
| 101110100 | 西安 |
| 101190400 | 苏州 |
| 101200100 | 武汉 |

## 📚 技术文档

- [SKILL.md](./SKILL.md) — 完整技术文档（安装、使用、故障排除）
- [REVERSE_ENGINEERING.md](./REVERSE_ENGINEERING.md) — BOSS 风控逆向分析
- [BYPASS_SOLUTION.md](./BYPASS_SOLUTION.md) — 绕过方案（整合 GitHub 开源项目）

## 🤝 相关项目

| 项目 | 用途 |
|------|------|
| [Camoufox](https://github.com/AugustoAleGon/camoufox) | C++ 级 Firefox 指纹修改 |
| [CloakBrowser](https://github.com/AugustoAleGon/CloakBrowser) | 定制 Chromium（49 个 C++ 补丁） |
| [rebrowser-playwright](https://github.com/AugustoAleGon/rebrowser-playwright) | Playwright 源码修补 |
| [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) | Selenium 反检测 |
| [curl_cffi](https://github.com/lexiforest/curl_cffi) | TLS 指纹伪装 |

## ⚠️ 免责声明

本项目仅供学习和研究使用。请遵守 BOSS 直聘的服务条款。使用本项目造成的任何后果由用户自行承担。

## 📄 License

MIT License

---

**如果这个项目对你有帮助，请给个 ⭐ Star！**
