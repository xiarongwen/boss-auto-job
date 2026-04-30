# Boss Auto Job — Skill Instructions

> 在 BOSS 直聘上自动搜索职位、匹配简历、生成打招呼语、发送消息。

## 何时使用

当用户提到以下关键词时激活此技能：
- 找工作、求职、投简历、看机会
- BOSS直聘、BOSS、招聘
- 搜索职位、发消息、打招呼
- 简历匹配

## 前置条件

```bash
pip install "camoufox[geoip]" && camoufox fetch
```

简历文件：`~/.hermes/credentials/resume.txt`

### LLM 招呼语生成配置（可选但推荐）

```bash
export BOSS_LLM_API_KEY="sk-xxx"           # 或 OPENAI_API_KEY
export BOSS_LLM_BASE_URL="https://api.openai.com/v1"  # 或 OPENAI_BASE_URL
export BOSS_LLM_MODEL="gpt-4o-mini"        # 或 OPENAI_MODEL
```

未配置时自动降级为简单 fallback 模板。

## 工具

项目路径下有一个 `boss` CLI，支持以下命令：

### 搜索职位

```bash
./boss search "关键词" --city 深圳 --area 南山 --pages 2
```

- `--city`: 城市名（北京/上海/深圳/杭州/成都/广州/南京/武汉/西安/苏州/天津）或城市代码
- `--area`: 区域过滤，如 南山、海淀、朝阳
- `--pages`: 页数（默认1，最多3）

### 搜索 + 简历匹配

```bash
./boss search "AI前端" --city 深圳 --match --top 5
```

### 搜索 + 匹配 + 自动发送

```bash
./boss search "Agent应用开发" --city 深圳 --match --send --top 3
```

### 发送消息

```bash
./boss send <job_id> "你好，我对这个职位很感兴趣"
```

### 其他

```bash
./boss resume       # 查看简历
./boss cities       # 查看城市代码
```

## 工作流程

当用户说"帮我找XX方面的工作"时：

1. **理解需求** — 确认关键词、城市、区域
2. **搜索** — `./boss search "关键词" --city 城市 --area 区域`
3. **匹配** — 如果用户有简历，加 `--match --top N`
4. **展示结果** — 列出匹配度最高的职位，让用户选择
5. **生成招呼语** — 根据 JD + 简历，用 LLM 自动生成个性化打招呼语（详见下方）
6. **确认发送** — 让用户确认后再发（不要自动发！）
7. **发送** — `./boss send <job_id> "招呼语"`

## 招呼语生成

**不再使用固定模板。** 招呼语由 LLM 分析 JD 和简历的实际内容后自动生成。

### 生成方式

```bash
# 方式1: boss_apply.py 流水线自动生成（推荐）
python boss_apply.py "AI工程师" --pages=2
# 输出 JSON 中 jobs_with_greeting 字段已包含每个职位的个性化招呼语

# 方式2: 独立生成
echo '{"title":"AI工程师","company":"某科技","requirements":["Python"],"jd_text":"负责..."}' | \
  python scripts/generate_greeting.py --stdin

# 方式3: --auto 模式
python scripts/send_camoufox.py <job_id> --auto
```

### 生成规则（由 LLM prompt 控制）
- 基于 JD 和简历的实际内容分析 2-3 个匹配亮点
- 不使用固定模板，每条消息独特
- 语气自然真诚，不像在念简历
- 不以"您好"千篇一律开头
- 80-150 个中文字符
- 结尾礼貌表达沟通意愿

## 安全规则（必须遵守）

| 情况 | 行动 |
|------|------|
| Code 0 | 正常处理 |
| Code 37 | 自动生成 zp_stoken，重试 1 次 |
| Code 36 | **立即停止**，告诉用户"请在浏览器中打开 zhipin.com 完成验证后告诉我" |
| Code 32 | **立即停止**，告诉用户"请在浏览器中完成验证，并手动发一条消息后告诉我" |
| Code 1006 | 等待 10 秒重试 |

**绝不重试 Code 36/32，否则会升级封禁。**

## 频率限制

- 搜索间隔：3-5 秒
- 发送间隔：5 秒
- 单次搜索：最多 3 页
- 单次发送：最多 5 条
- 每日发送：不超过 20 条

## 技术文档

- `REVERSE_ENGINEERING.md` — BOSS 风控逆向分析
- `BYPASS_SOLUTION.md` — 绕过方案
- `SKILL.md` — 完整技术文档
