# 🎯 Boss Auto Job

> AI 自动求职工具 — 搜索职位、匹配简历、优化简历、自动投递

基于 Camoufox（C++ 级指纹伪装）绕过 BOSS 直聘全部反爬虫检测。
支持 Claude Code / Cursor / Hermes Agent 等所有 Agent CLI。

---

## 它能做什么？

| 功能 | 说明 |
|------|------|
| 🔍 **搜索职位** | 按关键词 + 城市 + 区域批量搜索，一次扫几十个岗位 |
| 🧠 **简历匹配** | AI 自动给每个 JD 打分，告诉你哪些最匹配 |
| 📝 **简历优化** | 针对目标 JD，分析差距并生成优化后的简历（PDF/Word） |
| 💬 **个性化招呼** | 根据 JD 和简历生成独一无二的打招呼语，不是固定模板 |
| 📤 **自动投递** | 确认后一键发送，间隔控制防风控 |

---

## 快速开始

### 1. 安装

```bash
pip install "camoufox[geoip]" && camoufox fetch
```

### 2. 准备简历

```bash
mkdir -p ~/.hermes/credentials
echo "你的简历简介" > ~/.hermes/credentials/resume.txt
```

### 3. 使用

```bash
# 搜索职位
./boss search "产品经理" --city 深圳 --area 南山

# 搜索 + 匹配简历
./boss search "AI前端" --city 深圳 --match --top 5

# 搜索 + 匹配 + 自动发送招呼语
./boss search "产品经理" --city 深圳 --match --send --top 3

# 针对某个 JD 优化简历（支持 PDF/Word）
./boss optimize <job_id> <resume.pdf>

# 单独发消息
./boss send <job_id> "招呼语内容"
```

### 在 Agent 中使用

克隆仓库后，直接对 Agent 说：

```
帮我搜索深圳南山区的前端开发岗位
```

Agent 会自动读取 `CLAUDE.md` / `.cursorrules` / `AGENTS.md`，知道怎么调用 `boss` CLI。

---

## 简历优化

针对一个你特别想去的公司岗位，上传简历后 AI 自动：

1. 爬取完整 JD
2. 分析你的简历与 JD 的匹配度（分数 / 优势 / 差距 / 关键词）
3. 生成优化后的简历（保留真实经历，调整表达和侧重点）

```bash
# 基本用法
./boss optimize <job_id> <resume.pdf>

# 保存报告
./boss optimize <job_id> <resume.docx> -o report.json
```

支持格式：PDF / Word (.docx) / 旧版 Word (.doc) / 纯文本 (.txt)

---

## 常见问题

### Code 36 — 账户异常
BOSS 检测到异常行为。**不要重试**，请：
1. 打开 Chrome 访问 zhipin.com
2. 完成安全验证（极验 CAPTCHA）
3. 随便找一个职位发一条消息
4. 回来告诉 Agent "已验证"，自动恢复

### Code 32 — 账户被临时封禁
比 36 更严重。需要：
1. 在 Chrome 中完成验证
2. **手动发一条消息**（这是关键信号，BOSS 需要确认你是真人）
3. 等待 10-30 分钟恢复

### Code 37 — 环境异常
Camoufox 会自动处理，通常不需要手动干预。

### Code 1006 — 限速
搜索太频繁了。等 10 秒自动重试，或者减少搜索页数。

### 搜索没有结果
- 检查网络连接
- 确认城市代码正确（`./boss cities` 查看）
- Camoufox 可能需要更新：`camoufox fetch`

### 简历解析失败
```bash
# PDF 解析
pip install pymupdf

# Word 解析
pip install python-docx
```

### 打招呼语被限流
- 单次最多发 5 条
- 每条间隔 5 秒
- 每天不超过 20 条

---

## 频率限制

| 操作 | 限制 |
|------|------|
| 搜索间隔 | 3-5 秒 |
| 发送间隔 | 5 秒 |
| 单次搜索 | 最多 3 页 |
| 单次发送 | 最多 5 条 |
| 每日发送 | ≤ 20 条 |

---

## 项目结构

```
boss-auto-job/
├── boss                      # CLI 入口
├── scripts/
│   ├── search_camoufox.py    # 搜索（Camoufox 隐身）
│   ├── send_camoufox.py      # 发送消息
│   ├── boss_optimize.py      # 简历优化
│   ├── fetch_jd.py           # JD 爬取
│   ├── parse_resume.py       # 简历解析（PDF/Word）
│   ├── resume_optimizer.py   # 优化器核心
│   ├── boss_apply.py         # 一键流水线
│   └── match.py              # 简历匹配
├── AGENTS.md                 # Agent 通用配置
├── CLAUDE.md                 # Claude Code 配置
├── .cursorrules              # Cursor 配置
└── SKILL.md                  # Hermes Agent 技能文档
```

---

## 技术原理

BOSS 直聘 4 层反爬虫：

| 层 | 机制 | 绕过方式 |
|----|------|---------|
| 1 | TLS/Canvas/WebGL 指纹 | C++ 级修改 |
| 2 | 鼠标/键盘行为分析 | humanize=True |
| 3 | zp_stoken 网关验证 | 浏览器自动执行 |
| 4 | 账户/IP 风控引擎 | 频率控制 |

详见 [REVERSE_ENGINEERING.md](./REVERSE_ENGINEERING.md)

---

## 免责声明

本项目仅供学习研究。请遵守 BOSS 直聘服务条款。使用后果自负。

## License

MIT

---

**⭐ Star 支持一下！**
