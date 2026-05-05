# 🎯 Boss Auto Job

> 自动在 BOSS 直聘上搜索职位、智能匹配简历、生成个性化打招呼语、自动发送消息。

基于 **Camoufox**（C++ 级 Firefox 指纹修改）绕过 BOSS 直聘全部 4 层反爬虫检测。

**支持所有 Agent CLI：** Claude Code / Cursor / Codex / OpenCode / Hermes Agent

---

## ✨ 特性

- 🔍 **智能搜索** — 多关键词、多城市、多页搜索
- 🧠 **简历匹配** — 按技能/经验/学历/行业多维度打分
- 📝 **简历优化** — 根据 JD 针对性优化简历（支持 PDF/Word）
- 📤 **自动发送** — 定制打招呼语一键发送
- 🛡️ **完全隐身** — Camoufox C++ 级指纹修改，通过所有反 bot 检测
- 🤖 **Agent 原生** — `AGENTS.md` / `CLAUDE.md` / `.cursorrules` 即插即用
- ⌨️ **CLI 工具** — 不依赖任何 Agent 框架，纯命令行也能用
- 🔐 **安全机制** — Code 36/32 自动停止，不导致账户封禁

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install "camoufox[geoip]"
camoufox fetch  # 下载 Firefox 二进制 (~100MB)
```

### 2. 准备简历

```bash
mkdir -p ~/.hermes/credentials
echo "你的简历简介" > ~/.hermes/credentials/resume.txt
```

### 3. 使用

#### 方式一：在 Claude Code / Cursor 中使用

把这个仓库克隆到你的项目目录：

```bash
git clone https://github.com/xiarongwen/boss-auto-job.git
```

然后直接对 Agent 说：

```
帮我搜索深圳南山区的 Agent 应用开发岗位
```

Agent 会自动读取 `CLAUDE.md` 或 `.cursorrules`，知道怎么用 `boss` CLI。

#### 方式二：直接命令行

```bash
# 搜索
./boss search "Agent应用开发" --city 深圳 --area 南山

# 搜索 + 匹配简历
./boss search "AI前端" --city 深圳 --match --top 5

# 搜索 + 匹配 + 自动发送
./boss search "AI应用开发" --city 深圳 --match --send --top 3

# 发送消息
./boss send <job_id> "你好，我对这个职位很感兴趣"

# 根据 JD 针对性优化简历（支持 PDF/Word/DOCX/TXT）
./boss optimize <job_id> <resume.pdf>
./boss optimize <job_id> ~/resumes/resume.docx -o report.json

# 查看简历
./boss resume

# 查看城市代码
./boss cities
```

#### 方式三：Python 脚本

```bash
python scripts/search_camoufox.py "Python" --city=101280600
python scripts/boss_apply.py "产品经理" --send
python scripts/send_camoufox.py <job_id> "消息"
```

## 🤖 Agent 兼容性

| Agent CLI | 配置文件 | 状态 |
|-----------|---------|------|
| Claude Code | `CLAUDE.md` | ✅ 自动读取 |
| Cursor | `.cursorrules` | ✅ 自动读取 |
| Codex CLI | `AGENTS.md` | ✅ 自动读取 |
| OpenCode | `AGENTS.md` | ✅ 自动读取 |
| Hermes Agent | `SKILL.md` | ✅ 自动加载 |
| 其他 Agent | `AGENTS.md` | ✅ 通用格式 |

## 📝 简历优化

针对特定 JD 针对性优化你的简历，支持 PDF / Word / TXT 格式。

### 工作流程

```
1. 输入目标职位（job_id 或 URL）+ 简历文件（PDF/Word）
2. 解析简历为纯文本（pymupdf 处理 PDF，python-docx 处理 Word）
3. Camoufox 隐身访问 BOSS 获取完整 JD
4. Agent 自动分析：匹配度打分 / 优势 / 差距 / 关键词匹配
5. Agent 生成优化后的简历（保留真实经历，调整表达和侧重点）
6. 输出完整报告（匹配分析 + 优化建议 + 优化后简历）
```

### 使用方式

```bash
# 安装依赖
pip install pymupdf python-docx

# 优化简历
./boss optimize <job_id> <resume.pdf>

# 保存报告到文件
./boss optimize <job_id> <resume.docx> -o report.json
```

### 支持格式

| 格式 | 扩展名 | 依赖 |
|------|--------|------|
| PDF | `.pdf` | pymupdf / pdfplumber / PyPDF2 |
| Word | `.docx` | python-docx |
| 旧版 Word | `.doc` | LibreOffice / antiword |
| 纯文本 | `.txt` | 无 |

### 优化规则

- ✅ 保留真实经历，不编造不夸大
- ✅ 将与 JD 匹配的经历放在更显眼的位置
- ✅ 自然融入 JD 要求的关键词
- ✅ 将模糊描述改为量化表达
- ✅ 弱化与 JD 无关的经历
- ✅ 输出标准简历格式，控制篇幅

## 📁 项目结构

```
boss-auto-job/
├── boss                       # ⌨️ CLI 入口（chmod +x）
├── AGENTS.md                  # 🤖 Agent 通用技能说明
├── CLAUDE.md                  # Claude Code 配置（= AGENTS.md）
├── .cursorrules               # Cursor 配置（= AGENTS.md）
├── SKILL.md                   # Hermes Agent 技能文档
├── README.md                  # 📖 本文件
├── REVERSE_ENGINEERING.md     # BOSS 风控逆向分析
├── BYPASS_SOLUTION.md         # 绕过方案（8个开源项目）
├── requirements.txt           # Python 依赖
├── LICENSE                    # MIT License
└── scripts/
    ├── boss_apply.py          # 🎯 一键流水线
    ├── boss_optimize.py       # 📝 简历优化 CLI
    ├── search_camoufox.py     # 🔍 Camoufox 搜索
    ├── send_camoufox.py       # 📤 Camoufox 发送
    ├── fetch_jd.py            # 📋 JD 爬取
    ├── parse_resume.py        # 📄 简历解析（PDF/Word）
    ├── resume_optimizer.py    # 🧠 简历优化器
    ├── match.py               # 多 Agent 匹配
    ├── generate.py            # 生成打招呼语
    └── ...                    # 其他脚本
```

## 🛡️ BOSS 风控机制

BOSS 直聘采用 4 层纵深防御：

| 层级 | 机制 | Camoufox 绕过方式 |
|------|------|-------------------|
| Layer 1 | 环境检测（TLS/Canvas/WebGL） | C++ 级指纹修改 |
| Layer 2 | 行为分析（Warlock 鼠标/键盘） | humanize=True |
| Layer 3 | 网关验证（zp_stoken） | 浏览器自动执行 JS |
| Layer 4 | 风控引擎（账户/IP/设备） | 住宅代理 + 频率控制 |

详细分析见 [REVERSE_ENGINEERING.md](./REVERSE_ENGINEERING.md)

## 🔧 API 错误码

| Code | 含义 | 处理策略 |
|------|------|----------|
| 0 | 成功 | 正常处理 |
| 37 | 环境异常 | 自动生成 zp_stoken，重试 1 次 |
| 36 | 账户异常 | **立即停止**，通知用户手动验证 |
| 32 | 账户封禁 | **立即停止**，通知用户手动恢复 |
| 1006 | 限速 | 等待 10 秒后重试 |

**关键原则：绝不重试 Code 36/32！**

## 📊 频率限制

| 操作 | 限制 |
|------|------|
| 搜索 API | 间隔 3-5 秒 |
| 发消息 API | 间隔 5 秒 |
| 单次搜索 | 最多 3 页 |
| 单次发送 | 最多 5 条 |
| 每日发送 | 20 条 |

## 🗺️ 城市代码

| 代码 | 城市 | 代码 | 城市 |
|------|------|------|------|
| 101010100 | 北京 | 101280600 | 深圳 |
| 101020100 | 上海 | 101210100 | 杭州 |
| 101270100 | 成都 | 101280100 | 广州 |
| 101190100 | 南京 | 101200100 | 武汉 |
| 101110100 | 西安 | 101190400 | 苏州 |

## 📚 文档

- [AGENTS.md](./AGENTS.md) — Agent 技能说明（所有 Agent 通用）
- [SKILL.md](./SKILL.md) — Hermes Agent 专用技能文档
- [REVERSE_ENGINEERING.md](./REVERSE_ENGINEERING.md) — 风控逆向分析
- [BYPASS_SOLUTION.md](./BYPASS_SOLUTION.md) — 绕过方案

## 🤝 相关项目

| 项目 | 用途 |
|------|------|
| [Camoufox](https://github.com/AugustoAleGon/camoufox) | C++ 级 Firefox 指纹修改 |
| [CloakBrowser](https://github.com/AugustoAleGon/CloakBrowser) | 定制 Chromium |
| [rebrowser-playwright](https://github.com/AugustoAleGon/rebrowser-playwright) | Playwright 源码修补 |
| [curl_cffi](https://github.com/lexiforest/curl_cffi) | TLS 指纹伪装 |

## ⚠️ 免责声明

本项目仅供学习和研究使用。请遵守 BOSS 直聘的服务条款。使用本项目造成的任何后果由用户自行承担。

## 📄 License

MIT License

---

**如果这个项目对你有帮助，请给个 ⭐ Star！**
