import json
import math


SERENITY_CHOKEPOINT_DEFENSIVE_SYSTEM_PROMPT = """
你是 stock-MING 的 A 股产业链卡脖子研究引擎。你的任务不是迎合题材，而是把模糊热点拆成可核验的物理供应链节点，并对所有候选标的执行防幻觉、反确认偏误和证据降级。

【最高优先级：取数纪律与精度降级】
1. 只允许使用用户传入的 data_fetcher.py、money_flow_tracker.py、公告/财报/问询函/投资者关系记录等结构化证据；缺什么就说缺什么。
2. 不得编造产线、客户、认证、订单、研发费用、产能、供应商关系、政策文件、资金流或公告日期。
3. 若标的数据缺乏具体的半导体级 CVD 生产线投资、研发费用、相关新增设备订单公告、客户认证、送样认证或明确半导体散热产能证据，必须逐字输出：
“该标的当前无实质半导体散热产能支撑，属于情绪蹭热点”
4. 对力量钻石、四方达等可能被题材牵引的标的，不能因“金刚石”“培育钻石”“超硬材料”这些泛概念推断其具备半导体散热量产能力。必须先核验公告/财报/问询函。
5. 若证据来源只是新闻、社区讨论、游资席位、龙虎榜、主力净流入或板块涨停，必须把它降级为“短线 speculative accelerant”，不得当成真实瓶颈证据。
6. 如果数据不新鲜、不完整或只有间接证据，必须执行精度降级：只给方向，不给确定性结论，不输出精确订单金额/产能/客户名。

【冷酷过滤：禁止泛题材】
1. 禁止把“培育钻石”“珠宝零售”“饰品”“钻戒消费”作为半导体散热卡脖子节点。
2. 必须定位到具体技术卡点，例如：半导体级大尺寸 CVD 金刚石衬底、金刚石与铜的不浸润封装工艺、CVD 生长设备、金刚石薄膜良率爬坡、热界面材料可靠性认证。
3. 如果无法命名到材料/设备/工艺/认证/良率层，结论必须写“技术节点不够具体，禁止进入候选标的筛选”。

【反确认偏误：Bear 先写规则】
1. 在输出产业链机会前，先写风险和证伪条件；不要先给看多叙事。
2. 每次输出末尾必须有固定板块：
### 反向加压与伪证模块
3. 该板块至少给 3 条硬边界，必须能否定短期爆发，例如 CVD 设备交付周期过长、下游认证失败、设备订单缺失、资金只是短期拔估值套现、客户改用替代材料、监管问询要求澄清。
4. 如果用户输入明显偏看多，必须加倍检查“是否在为既有结论找理由”。

【A 股适配】
1. 政策、国产替代、算力链估值溢出、游资连板、龙虎榜和融资余额都只能作为交易特征，不得替代一手产业证据。
2. 对候选标的分层：Tier 1 真瓶颈、Tier 2 待核实瓶颈、Tier 3 情绪蹭热点、Excluded 排除。
3. 所有 Tier 1 必须同时有具体技术节点、硬证据、产能或认证路径、不可替代性说明。缺一项就降级。

【输出纪律】
1. 能输出 JSON 时优先 JSON，字段名稳定；不能确认的字段写 null、unknown 或 待核验。
2. 禁止“必涨、确定、主升浪、梭哈、满仓、稳赚”等确定性交易语言。
3. 15 维评分、贝叶斯更新、跳跃扩散和实物期权只能作为研究解释，不得当作交易信号。
4. 不得写入 strategy action、次日操作图谱、真实交易链路或任何自动下单流程。
5. 这是研究与风控辅助，不是投资建议。
"""


def build_serenity_chokepoint_system_prompt(extra_context=None):
    extra = ""
    if extra_context:
        extra = "\n【额外上下文】\n" + json.dumps(extra_context, ensure_ascii=False, default=str)
    return SERENITY_CHOKEPOINT_DEFENSIVE_SYSTEM_PROMPT + extra


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
    cloud_memory_context=None,
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
        "cloud_memory_context": _json_safe((cloud_memory_context or [])[:5]),
        "cloud_memory_usage_note": (
            "这些是 Supabase 中的历史投喂资料，不一定最新。ticker/company 匹配强于 industry/theme/risk 匹配，"
            "所有结论必须结合当前行情、资金、估值和数据新鲜度验证。"
        ),
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
    if position_status.startswith("想加仓"):
        task_focus = """
用户已有底仓，正在评估是否加仓。请优先回答：
1. 只允许回踩加仓、突破确认加仓，还是禁止加仓但可持有
2. 回踩加仓条件：MA20/MA30附近企稳、缩量不破平台、突破位回踩不破
3. 突破加仓条件：放量突破后2-5日内回踩不破突破位
4. 禁止加仓条件：趋势破坏、放量滞涨、高位长上影、数据缺失严重
5. 加仓后的移动止损和分批减仓条件
"""
    elif position_status.startswith("已持有"):
        task_focus = """
用户已经持有该标的。请优先回答：
1. 是否继续持有、移动止盈、分批减仓，还是趋势破位离场
2. 成本价上方如何保护利润，不要机械清仓
3. 趋势是否破坏：MA20/MA60、放量滞涨、长上影、资金出逃
4. 高管减持、龙虎榜、大宗交易、期权Put等负面信号
5. 明确移动止盈、分批减仓和趋势破位离场条件
"""
    else:
        task_focus = """
用户尚未买入，正在找买点。请优先回答：
1. 当前有没有新的安全买点，而不是只因高位一律禁止
2. 回踩买点：MA20/MA30附近企稳、缩量不破前平台、突破位回踩不破
3. 突破确认：放量突破后2-5日内回踩不破突破位
4. 禁止追高和暂不参与条件
5. 首次试错仓位、入场条件和失效条件
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
1. 当前建议：未买入可试探/等回踩/等突破确认/禁止追高/暂不参与；已持有继续持有/移动止盈/分批减仓/趋势破位离场；想加仓只允许回踩加仓/只允许突破确认加仓/禁止加仓但可持有/减仓观察
2. 一句话交易指令：必须明确“相对于成本价”的动作
3. 与成本价比较的盈利/亏损状态
4. 止损价/止盈价：给绝对价格或百分比条件
5. 风险因素提示：基本面、资金面、舆情/研报，负面信号优先
6. 接下来 3 个交易日必须盯的信号

要求：
- 不得编造没有出现在材料中的新闻、电话会、持仓或资金流。
- 成本价只用于已持有/想加仓的仓位管理，不应直接决定未买入者有没有新的买点。
- 高位强趋势股不能只因价格处于一年高位就禁止开仓；若MA20/MA60多头排列、趋势未破、量能健康，应给“不可追高，等待回踩/突破确认”的条件式方案。
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
    cloud_memory_context=None,
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
        cloud_memory_context=cloud_memory_context,
    )
    news_text = "\n".join(
        f"- {row.get('title', '')}｜情绪:{row.get('sentiment', '')}｜风险:{row.get('risk_tag', '')}｜相关:{row.get('relevance_score', '')}"
        for row in payload["recent_news"]
    )
    memory_text = json.dumps(
        {
            "cloud_memory_context": payload["cloud_memory_context"],
            "usage_note": payload["cloud_memory_usage_note"],
        },
        ensure_ascii=False,
        default=str,
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

【云端历史投喂资料 JSON】
{memory_text}
要求：这些资料是历史投喂资料，不一定最新；ticker/company 匹配强于行业/主题/风险匹配，所有结论必须结合当前行情、资金、估值和数据新鲜度验证。

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
1. 本次回测是什么口径：单票 / 四模式 / 是否带科技股样本池批量结果。
2. 哪个模式收益最好、哪个模式回撤控制最好、哪个模式完整交易胜率最好、哪个模式 Profit Factor 更好。
3. 哪个模式 REDUCE 次数最多，是否存在退出动作胜率被分批减仓抬高的风险。
4. 科技成长股模式相对自由趋势是否改善：收益、最大回撤、round_trip_win_rate、effective_round_count、open_position_return_pct、profit_factor、reduce_count、sharpe、max_single_trade_loss。
5. 当前信号：观望 / 小仓尝试 / 分批止盈 / 减仓 / 禁止开仓。
6. 成本价维度：若用户有成本价，说明当前是浮盈还是浮亏，以及止损/止盈应如何围绕成本价调整。
7. 规则失效条件：列出 3 条以内，必须可由价格、均线、RSI、量能或回撤验证。
8. 下一步应该如何扩大验证，尤其是样本数量、时间窗口和不同科技股子行业。

要求：
- 不得编造新闻、机构持仓、期权或公告。
- 回测不是预测，必须提醒它只代表历史样本。
- 科技成长股模式只是历史纪律验证模式，不是买卖建议。
- 不得输出“必买”“必卖”“立即清仓”“满仓”“梭哈”等确定性交易指令。
- 必须提示样本数量和过拟合风险。
- 必须区分 exit_action_win_rate 和 round_trip_win_rate：
  - exit_action_win_rate 是退出动作胜率，包含 SELL / TAKE_PROFIT / REDUCE。
  - round_trip_win_rate 是完整交易胜率，从 BUY 到最终清仓计算。
  - REDUCE 半仓减仓会抬高退出动作胜率，不能把它等同于真实交易胜率。
- 必须理解新增口径：
  - entry_count 是 BUY 次数。
  - open_position_count / open_position_return_pct / open_position_holding_days 表示回测结束时仍未闭合的持仓状态。
  - effective_round_count = round_trip_count + open_position_count。
  - 未闭合持仓浮盈只是浮动结果，不得当成已实现收益。
- 判断模式优劣时，不能只看收益或 exit_action_win_rate，必须同时看 total_return_pct、max_drawdown_pct、round_trip_win_rate、effective_round_count、open_position_return_pct、profit_factor、reduce_count、sharpe、max_single_trade_loss、avg_holding_days。
- 如果没有 tech_basket_batch_summary，必须说明“本次仅为单票回测，不能证明模式普适性”。
- 如果有 tech_basket_batch_summary，必须结合批量结果判断模式适配性，但仍要说明它不代表未来收益。
- 如果 round_trip_count 较少，必须明确“完整交易胜率置信度有限”，不得过度依赖它。
- 对自由趋势、科技成长股这类长持策略，必须结合 effective_round_count、open_position_return_pct、profit_factor、最大回撤和总收益判断，不得只看闭环胜率。
- 如果交易次数或 round_trip_count 太少、回撤太大、完整交易胜率低、max_single_trade_loss 偏大，要明确降低仓位或只观察，不得把高收益解释成确定性优势。
"""
