"""
Summary report generator for localized investment analysis reports.

This module generates comprehensive summary reports in the user's selected language,
translating the key findings from English reports created by the agent system.
"""

from typing import Dict, Any, Optional


LANGUAGE_TEMPLATES = {
    "English": {
        "title": "# Investment Analysis Summary Report",
        "decision": "## Final Decision",
        "rationale": "## Key Rationale",
        "analyst_findings": "## Analyst Findings Summary",
        "market_analyst": "### Market Analyst",
        "social_analyst": "### Social/Sentiment Analyst",
        "news_analyst": "### News Analyst",
        "fundamentals_analyst": "### Fundamentals Analyst",
        "risk_assessment": "## Risk Assessment Summary",
    },
    "한국어": {
        "title": "#투자 분석 요약 보고서",
        "decision": "## 최종 결정",
        "rationale": "## 핵심 근거",
        "analyst_findings": "## 분석가별 주요 발견",
        "market_analyst": "### 시장 분석가",
        "social_analyst": "### 소셜/감성 분석가",
        "news_analyst": "### 뉴스 분석가",
        "fundamentals_analyst": "### 펀더멘털 분석가",
        "risk_assessment": "## 리스크 평가 요약",
    },
    "日本語": {
        "title": "#投資分析サマリーレポート",
        "decision": "## 最終決定",
        "rationale": "## 主な根拠",
        "analyst_findings": "## アナリスト調査結果サマリー",
        "market_analyst": "### マーケットアナリスト",
        "social_analyst": "### ソーシャル/センチメントアナリスト",
        "news_analyst": "### ニュースアナリスト",
        "fundamentals_analyst": "### ファンダメンタルズアナリスト",
        "risk_assessment": "## リスク評価サマリー",
    },
    "中文": {
        "title": "# 投资分析摘要报告",
        "decision": "## 最终决定",
        "rationale": "## 核心理据",
        "analyst_findings": "## 分析师发现摘要",
        "market_analyst": "### 市场分析师",
        "social_analyst": "### 社交媒体/情绪分析师",
        "news_analyst": "### 新闻分析师",
        "fundamentals_analyst": "### 基本面分析师",
        "risk_assessment": "## 风险评估摘要",
    },
    "Español": {
        "title": "# Informe Resumido de Análisis de Inversión",
        "decision": "## Decisión Final",
        "rationale": "## Fundamentos Clave",
        "analyst_findings": "## Resumen de Hallazgos de Analistas",
        "market_analyst": "### Analista de Mercado",
        "social_analyst": "### Analista Social/Sentimiento",
        "news_analyst": "### Analista de Noticias",
        "fundamentals_analyst": "### Analista de Fundamentos",
        "risk_assessment": "## Resumen de Evaluación de Riesgos",
    },
}


SUMMARY_PROMPT_TEMPLATE = """You are a financial translator and summarizer. Your task is to create a comprehensive investment analysis summary report in {language}.

Below are the original English reports from various analysts and the final trading decision. Please create a well-structured summary report in {language} that includes:

1. Final Trading Decision (extract from the portfolio manager's decision)
2. Key Rationale (main reasons for the decision)
3. Analyst Findings Summary (brief summary of each analyst's key findings)
4. Risk Assessment Summary (key risks identified)

IMPORTANT INSTRUCTIONS:
- Write ALL content in {language} (not in English)
- Be concise but comprehensive
- Focus on actionable insights and key findings
- Maintain a professional tone appropriate for investment analysis
- Use clear headings and bullet points where appropriate

---

**MARKET ANALYST REPORT:**
{market_report}

---

**SOCIAL/SENTIMENT ANALYST REPORT:**
{sentiment_report}

---

**NEWS ANALYST REPORT:**
{news_report}

---

**FUNDAMENTALS ANALYST REPORT:**
{fundamentals_report}

---

**RESEARCH MANAGER INVESTMENT PLAN:**
{investment_plan}

---

**TRADER'S INVESTMENT PLAN:**
{trader_investment_plan}

---

**PORTFOLIO MANAGER FINAL DECISION:**
{final_trade_decision}

---

Please generate the summary report in {language} following this structure:

{template_structure}
"""


def get_template_structure(language: str) -> str:
    """Get the report structure template for the specified language."""
    lang_template = LANGUAGE_TEMPLATES.get(language, LANGUAGE_TEMPLATES["English"])

    structure = f"""
{lang_template["title"]}

{lang_template["decision"]}
[Extract and summarize the final trading decision]

{lang_template["rationale"]}
[Summarize the key reasons for this decision]

{lang_template["analyst_findings"]}

{lang_template["market_analyst"]}
[Key findings from market analysis]

{lang_template["social_analyst"]}
[Key findings from social/sentiment analysis]

{lang_template["news_analyst"]}
[Key findings from news analysis]

{lang_template["fundamentals_analyst"]}
[Key findings from fundamentals analysis]

{lang_template["risk_assessment"]}
[Summary of key risks and risk management considerations]
"""
    return structure


def generate_summary_report(state: Dict[str, Any], language: str, llm) -> str:
    """
    Generate a comprehensive summary report in the specified language.

    Args:
        state: The final state containing all analyst reports and decisions
        language: Target language for the report (e.g., "한국어", "日本語", "中文", "Español")
        llm: TheLLM instance to use for generation

    Returns:
        A formatted summary report string in the specified language
    """
    market_report = state.get("market_report", "")
    sentiment_report = state.get("sentiment_report", "")
    news_report = state.get("news_report", "")
    fundamentals_report = state.get("fundamentals_report", "")
    investment_plan = state.get("investment_plan", "")
    trader_investment_plan = state.get("trader_investment_plan", "")
    final_trade_decision = state.get("final_trade_decision", "")

    template_structure = get_template_structure(language)

    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        language=language,
        market_report=market_report,
        sentiment_report=sentiment_report,
        news_report=news_report,
        fundamentals_report=fundamentals_report,
        investment_plan=investment_plan,
        trader_investment_plan=trader_investment_plan,
        final_trade_decision=final_trade_decision,
        template_structure=template_structure,
    )

    response = llm.invoke(prompt)

    return response.content


def get_report_filename(language: str) -> str:
    """Get the filename suffix for the summary report based on language."""
    filename_map = {
        "English": "summary.md",
        "한국어": "summary_ko.md",
        "日本語": "summary_ja.md",
        "中文": "summary_zh.md",
        "Español": "summary_es.md",
    }
    return filename_map.get(language, "summary.md")
