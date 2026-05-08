def build_strict_risk_decision(valuation, news_rows, replay_rules="", technical=None):
    reasons = []
    action = "允许继续分析"

    valuation_flag = valuation.get("valuation_flag") if valuation else ""
    if valuation_flag and valuation_flag != "估值未触发明显高危标签":
        reasons.append(f"估值风险：{valuation_flag}")

    for row in news_rows or []:
        text = " ".join(str(row.get(k, "")) for k in ["title", "summary", "risk_tag", "sentiment"])
        if any(word in text for word in ["减持", "监管", "问询", "立案", "财报风险", "财报暴雷", "指引下修", "大宗折价"]):
            reasons.append(f"舆情风险：{row.get('title', '')[:60]}")

    if technical:
        if technical.get("rsi", 0) >= 78:
            reasons.append("技术风险：RSI高位，追买胜率下降")
        if technical.get("drawdown", 0) <= -18:
            reasons.append("技术风险：近期回撤过深，需确认止跌")

    if replay_rules and any(word in replay_rules for word in ["禁止", "不能追", "高位", "止损", "回撤"]):
        reasons.append("炼丹炉规则提示：该票已有历史纪律约束，需优先遵守")

    if len(reasons) >= 2:
        action = "禁止开仓/只观察"
    elif reasons:
        action = "谨慎观察/小仓试错"

    return {
        "risk_score": min(100, len(reasons) * 28),
        "action": action,
        "reasons": reasons or ["未触发硬性否决，但仍需结合实时盘口确认"],
    }


def build_counter_argument_prompt(ticker, bull_case, context):
    return f"""
你是反方投研专家。请只基于给定材料，反驳用户对 {ticker} 的看多理由。

【用户看多理由】
{bull_case}

【系统材料】
{context}

输出：
1. 最可能被忽略的三条利空
2. 哪个指标会证明看多逻辑失效
3. 禁止买入或减仓触发条件
4. 反方结论：可买 / 只观察 / 禁止开仓

不要编造新闻、公告、持仓或资金流。
"""


def build_ai_context_packet(supply_chain, valuation, news_rows, replay_rules):
    news_text = "\n".join(
        f"- {row.get('title', '')}｜情绪:{row.get('sentiment', '')}｜风险:{row.get('risk_tag', '')}｜相关:{row.get('relevance_score', '')}"
        for row in (news_rows or [])[:8]
    )
    return f"""
【产业链】
主题：{supply_chain.get('theme')}
位置：{supply_chain.get('position')}
风险传导：{supply_chain.get('risk_transmission')}

【估值】
{valuation}

【近48小时高相关舆情】
{news_text or '暂无高相关舆情'}

【炼丹炉专属规则】
{replay_rules or '暂无该票专属规则'}
"""
