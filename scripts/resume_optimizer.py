#!/usr/bin/env python3
"""
简历优化器 - 根据 JD 分析简历匹配度并生成优化建议

用法由 Agent 直接调用：读取 JD + 简历文本后，Agent 分析并输出优化结果。
此模块提供辅助函数。

Usage:
  from resume_optimizer import build_analysis_prompt, build_optimize_prompt
  prompt = build_analysis_prompt(jd_text, resume_text)
  prompt = build_optimize_prompt(jd_text, resume_text)
"""
import json
from pathlib import Path


def build_analysis_prompt(jd: dict, resume_text: str) -> str:
    """构建 JD-简历匹配分析 prompt。

    Agent 收到此 prompt 后直接分析，不需要调用任何工具。
    """
    jd_text = jd.get("jd_text", "")
    title = jd.get("title", "")
    company = jd.get("company", "")
    skills = ", ".join(jd.get("skills", []))
    requirements = "\n".join(f"- {r}" for r in jd.get("requirements", []))

    return f"""你是一位资深HR和职业顾问。请分析以下职位描述（JD）和候选人简历的匹配度。

## 职位信息
公司：{company}
职位：{title}
技能标签：{skills}
岗位要求：
{requirements or "(从JD正文中提取)"}

完整JD：
{jd_text}

## 候选人简历
{resume_text}

## 请输出以下分析（JSON格式）：

{{
  "match_score": 0-100的匹配分数,
  "strengths": ["优势1: 具体说明", "优势2: 具体说明"],
  "gaps": ["差距1: 具体说明及建议", "差距2: 具体说明及建议"],
  "keyword_missing": ["JD中要求但简历缺失的关键词1", "关键词2"],
  "keyword_matched": ["简历中匹配JD的关键词1", "关键词2"],
  "suggestions": ["优化建议1: 具体可执行的修改", "优化建议2: 具体可执行的修改"]
}}

只输出JSON，不要其他内容。"""


def build_optimize_prompt(jd: dict, resume_text: str) -> str:
    """构建简历优化 prompt。

    Agent 收到此 prompt 后直接输出优化后的简历内容。
    """
    jd_text = jd.get("jd_text", "")
    title = jd.get("title", "")
    company = jd.get("company", "")
    skills = ", ".join(jd.get("skills", []))

    return f"""你是一位资深HR简历优化专家。请根据以下JD，针对性地优化候选人的简历。

## 目标职位
公司：{company}
职位：{title}
技能标签：{skills}

完整JD：
{jd_text}

## 候选人原始简历
{resume_text}

## 优化规则
1. **保留真实经历**：不编造、不夸大，只调整表达方式和侧重点
2. **突出匹配点**：将简历中与JD匹配的经历放在更显眼的位置
3. **补充关键词**：在经历描述中自然融入JD要求的关键词
4. **量化成果**：将模糊描述改为数据化表达（如"提升20%转化率"）
5. **精简无关内容**：弱化与JD无关的经历，突出相关的
6. **保持格式**：输出标准简历格式，清晰易读
7. **控制篇幅**：不超过原始简历的1.5倍长度

## 输出要求
请输出优化后的完整简历文本（纯文本格式），不要有其他解释。"""


def build_full_report(jd: dict, resume_text: str, analysis: dict, optimized_resume: str) -> str:
    """生成完整的优化报告。"""
    title = jd.get("title", "")
    company = jd.get("company", "")

    report = f"""# 简历优化报告
目标职位：{title} @ {company}

## 匹配分析
- 匹配分数：{analysis.get('match_score', 'N/A')}/100

### 你的优势
"""
    for s in analysis.get("strengths", []):
        report += f"- ✅ {s}\n"

    report += "\n### 需要弥补的差距\n"
    for g in analysis.get("gaps", []):
        report += f"- ⚠️ {g}\n"

    matched = analysis.get("keyword_matched", [])
    if matched:
        report += f"\n### 已匹配关键词\n{', '.join(matched)}\n"

    missing = analysis.get("keyword_missing", [])
    if missing:
        report += f"\n### 缺失关键词\n{', '.join(missing)}\n"

    report += "\n### 优化建议\n"
    for i, sug in enumerate(analysis.get("suggestions", []), 1):
        report += f"{i}. {sug}\n"

    report += f"""
---

## 优化后的简历

{optimized_resume}
"""
    return report
