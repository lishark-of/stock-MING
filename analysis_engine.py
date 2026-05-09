def build_strict_risk_decision(
    valuation,
    news_rows,
    replay_rules="",
    technical=None,
    money_flow=None,
    position_status="未买入 (观望/找买点)",
    data_quality=None,
    scenario=None,
):
    reasons = []
    action = "允许继续分析"

    valuation_flag = valuation.get("valuation_flag") if valuation else ""
    if valuation_flag and valuation_flag != "估值未触发明显高危标签":
        reasons.append(f"估值风险：{valuation_flag}")

    for row in news_rows or []:
        text = " ".join(str(row.get(k, "")) for k in ["title", "summary", "risk_tag", "sentiment"])
        lowered = text.lower()
        if any(word in text for word in ["减持", "监管", "问询", "立案", "财报风险", "财报暴雷", "指引下修", "大宗折价"]) or any(
            word in lowered
            for word in ["guidance cut", "guidance risk", "earnings miss", "margin pressure", "insider selling", "selloff"]
        ):
            reasons.append(f"舆情风险：{row.get('title', '')[:60]}")

    if technical:
        rsi = technical.get("rsi")
        drawdown = technical.get("drawdown_60d")
        if drawdown is None:
            drawdown = technical.get("drawdown")
        volume_vs_20d = technical.get("volume_vs_20d")
        if rsi is not None and rsi >= 78:
            reasons.append("技术风险：RSI高位，追买胜率下降")
        if drawdown is not None and drawdown <= -18:
            reasons.append("技术风险：60日内回撤过深，需确认止跌")
        if technical.get("ma60_state") == "低于MA60":
            reasons.append("技术风险：仍在MA60下方，趋势确认不足")
        if volume_vs_20d is not None and volume_vs_20d < 0.55:
            reasons.append("技术风险：量能明显低于20日均量，买盘确认不足")

    if replay_rules and any(word in replay_rules for word in ["禁止", "不能追", "高位", "止损", "回撤"]):
        reasons.append("炼丹炉规则提示：该票已有历史纪律约束，需优先遵守")

    flow_summary = (money_flow or {}).get("summary") or {}
    for item in flow_summary.get("negative", []):
        reasons.append(f"资金面风险：{item}")

    if scenario:
        if scenario.get("probability_down_10_pct", 0) >= 45:
            reasons.append(f"情景风险：Monte Carlo显示未来区间下跌10%以上概率约 {scenario.get('probability_down_10_pct')}%")

    if data_quality:
        if data_quality.get("score", 100) < 55:
            reasons.append(f"数据可信度风险：{data_quality.get('grade')}，{data_quality.get('instruction')}")
        elif data_quality.get("missing"):
            reasons.append(f"数据缺口提示：{'; '.join(data_quality.get('missing', [])[:3])}")

    if position_status.startswith("已持有") and any("减持" in r or "卖出" in r or "出逃" in r for r in reasons):
        reasons.append("持仓状态风险：已持有时负面资金信号需优先处理")

    hard_keywords = [
        "内部人卖出",
        "指引下修",
        "guidance",
        "财报暴雷",
        "监管",
        "问询",
        "立案",
        "60日内回撤过深",
        "RSI高位",
        "Put活跃度偏高",
        "数据可信度风险",
    ]
    hard_count = sum(1 for reason in reasons if any(keyword in reason for keyword in hard_keywords))

    if hard_count >= 2 or len(reasons) >= 4:
        action = "禁止开仓/只观察"
    elif reasons:
        action = "谨慎观察/小仓试错"

    soft_count = max(0, len(reasons) - hard_count)

    return {
        "risk_score": min(100, hard_count * 35 + soft_count * 15),
        "action": action,
        "reasons": reasons or ["未触发硬性否决，但仍需结合实时盘口确认"],
    }


def build_position_aware_prompt(
    ticker,
    price,
    position_status,
    capital_plan,
    base_context,
    strict_decision,
    money_flow_text_block,
    technical=None,
    scenario=None,
    data_quality=None,
):
    if position_status.startswith("已持有"):
        task_focus = """
用户已经持有该标的。请优先回答：
1. 是否继续持有，还是减仓/清仓
2. 核心护城河是否仍成立
3. 机构资金是否有出逃迹象
4. 高管减持、龙虎榜、大宗交易、期权Put等负面信号
5. 明确止损位、止盈位、减仓条件
"""
    else:
        task_focus = """
用户尚未买入，正在找买点。请优先回答：
1. 当前是否有安全边际
2. 潜在催化剂是否足够强
3. 是否存在禁止开仓信号
4. 分批建仓计划，最多三档
5. 首次试错仓位和失效条件
"""

    return f"""
标的：{ticker}
当前价格：{price}
用户状态：{position_status}
本金/计划仓位：{capital_plan}

【任务侧重】
{task_focus}

【系统严格风控结论】
{strict_decision}

【资金面结构化数据】
{money_flow_text_block}

【实时技术指标】
{technical or '技术指标缺失'}

【Monte Carlo 情景区间】
{scenario or '情景推演缺失'}

【数据可信度】
{data_quality or '未生成数据可信度报告'}

【统一诊股底座】
{base_context}

请输出：
1. 结论：可买 / 分批低吸 / 继续持有 / 减仓 / 禁止开仓
2. 主要风险提示，负面信号优先
3. 止损点：给出价格或条件
4. 止盈/减仓点：给出价格或条件
5. 分批建仓或持仓调整方案，必须结合本金/计划仓位
6. 接下来 3 个交易日必须盯的信号

要求：
- 不得编造没有出现在材料中的新闻、电话会、持仓或资金流。
- 若资金面数据为空，要明确说“资金面公开数据不足”，但仍基于已有量价/估值/舆情判断。
- 若数据可信度为“低”，禁止给确定买入结论，只能给等待条件。
- 三个月目标价必须优先参考 Monte Carlo 的 p10/p50/p90 区间，不允许纯主观分配概率。
- 对减持、监管、业绩不及预期、Put放量、大宗折价、龙虎榜负反馈要高度敏感。
"""


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


def build_ai_context_packet(
    supply_chain,
    valuation,
    news_rows,
    replay_rules,
    peer_rows=None,
    research_links=None,
    technical=None,
    scenario=None,
    data_quality=None,
    money_flow=None,
):
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

【实时技术面】
{technical or '暂无实时技术面'}

【量化情景区间】
{scenario or '暂无情景推演'}

【数据可信度】
{data_quality or '暂无可信度报告'}

【资金面】
{money_flow or '暂无资金面结构化数据'}

【近48小时高相关舆情】
{news_text or '暂无高相关舆情'}

【炼丹炉专属规则】
{replay_rules or '暂无该票专属规则'}

【同行估值对比】
{peer_rows or '暂无同行对比'}

【深度信息挖掘入口】
{research_links or '暂无深度信息入口'}
"""
