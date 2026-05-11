import json
import math


def _dedupe_rows(rows, keys=("url", "title")):
    deduped = []
    seen = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        identity = tuple(str(row.get(key, "")).strip() for key in keys)
        if not any(identity):
            identity = (json.dumps(row, ensure_ascii=False, sort_keys=True, default=str),)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(row)
    return deduped


def _dedupe_items(items):
    deduped = []
    seen = set()
    for item in items or []:
        identity = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(item)
    return deduped


def _json_safe(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item") and callable(value.item):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            pass
    if value.__class__.__name__ == "DataFrame" and hasattr(value, "to_json"):
        try:
            return json.loads(value.tail(20).to_json(orient="records", date_format="iso", force_ascii=False))
        except Exception:
            return []
    if value.__class__.__name__ == "Series" and hasattr(value, "to_dict"):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        return value
    except Exception:
        return str(value)


def _compact_backtest_report(report):
    if not report:
        return {}
    try:
        from backtester import compact_report_for_prompt

        return _json_safe(compact_report_for_prompt(report))
    except Exception:
        return _json_safe(report)


def build_ai_context_payload(
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
    backtest_report=None,
):
    """Build a structured, JSON-serializable context for DeepSeek prompts."""

    return {
        "task": "stock_ming_single_stock_analysis",
        "schema_version": "1.0",
        "supply_chain": _json_safe(supply_chain or {}),
        "valuation": _json_safe(valuation or {}),
        "technical": _json_safe(technical or {}),
        "scenario": _json_safe(scenario or {}),
        "data_quality": _json_safe(data_quality or {}),
        "money_flow": _json_safe(money_flow or {}),
        "recent_news": _json_safe(_dedupe_rows(news_rows)[:8]),
        "replay_rules": _json_safe(replay_rules or ""),
        "peer_rows": _json_safe(peer_rows or []),
        "research_links": _json_safe(_dedupe_items(research_links)),
        "backtest_report": _compact_backtest_report(backtest_report),
        "analysis_requirements": {
            "no_fabricated_news": True,
            "prefer_structured_fields": True,
            "respect_data_quality": True,
            "use_monte_carlo_range_for_targets": True,
            "prioritize_negative_signals": True,
        },
    }


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
    position_profile=None,
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

【用户持仓画像】
{position_profile or '未提供成本价/持仓数量'}

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
1. 当前建议：观望 / 小仓尝试 / 分批止盈 / 继续持有 / 减仓 / 禁止开仓
2. 一句话交易指令：必须明确“相对于成本价”的动作
3. 与成本价比较的盈利/亏损状态
4. 止损价/止盈价：给绝对价格或百分比条件
5. 风险因素提示：基本面、资金面、舆情/研报，负面信号优先
6. 接下来 3 个交易日必须盯的信号

要求：
- 不得编造没有出现在材料中的新闻、电话会、持仓或资金流。
- 必须把用户成本价作为锚点：当前价低于成本价时优先判断亏损幅度和止损纪律；当前价高于成本价时优先判断移动止盈或继续持有。
- 每只股票必须独立分析，不能使用“价格高就止盈、价格低就止损”的模板。
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
    payload = build_ai_context_payload(
        supply_chain,
        valuation,
        news_rows,
        replay_rules,
        peer_rows=peer_rows,
        research_links=research_links,
        technical=technical,
        scenario=scenario,
        data_quality=data_quality,
        money_flow=money_flow,
    )
    news_text = "\n".join(
        f"- {row.get('title', '')}｜情绪:{row.get('sentiment', '')}｜风险:{row.get('risk_tag', '')}｜相关:{row.get('relevance_score', '')}"
        for row in payload["recent_news"]
    )
    return f"""
【产业链】
主题：{payload['supply_chain'].get('theme')}
位置：{payload['supply_chain'].get('position')}
风险传导：{payload['supply_chain'].get('risk_transmission')}

【估值】
{payload['valuation']}

【实时技术面】
{payload['technical'] or '暂无实时技术面'}

【量化情景区间】
{payload['scenario'] or '暂无情景推演'}

【数据可信度】
{payload['data_quality'] or '暂无可信度报告'}

【资金面】
{payload['money_flow'] or '暂无资金面结构化数据'}

【近48小时高相关舆情】
{news_text or '暂无高相关舆情'}

【炼丹炉专属规则】
{payload['replay_rules'] or '暂无该票专属规则'}

【同行估值对比】
{payload['peer_rows'] or '暂无同行对比'}

【深度信息挖掘入口】
{payload['research_links'] or '暂无深度信息入口'}
"""


def build_backtest_explanation_prompt(ticker, backtest_report, stock_context=None):
    return f"""
你是私人量化回测教练。请解释 {ticker} 的回测结果，并把它转成可执行交易纪律。

【回测报告】
{backtest_report}

【当前诊股上下文】
{stock_context or '暂无补充上下文'}

请输出：
1. 这套规则在历史上是否有效：只看收益、夏普、最大回撤、胜率和交易次数。
2. 当前信号：观望 / 小仓尝试 / 分批止盈 / 减仓 / 禁止开仓。
3. 成本价维度：若用户有成本价，说明当前是浮盈还是浮亏，以及止损/止盈应如何围绕成本价调整。
4. 规则失效条件：列出 3 条以内，必须可由价格、均线、RSI、量能或回撤验证。
5. 下一次复盘要看什么。

要求：
- 不得编造新闻、机构持仓、期权或公告。
- 回测不是预测，必须提醒它只代表历史样本。
- 如果交易次数太少、回撤太大或胜率低，要明确降低仓位或禁止开仓。
"""
