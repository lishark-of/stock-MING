from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def _as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _dump_fact_packet(value: Any) -> str:
    return json.dumps(value if isinstance(value, Mapping) else {}, ensure_ascii=False, indent=2, default=str)


def build_a_share_deep_research_prompt(
    target: str = "",
    current_price: Any = "未知",
    verified_technical_prompt: str = "",
    unverified_inject: str = "",
) -> str:
    target = target or "未指定标的"
    price_text = current_price if current_price not in (None, "") else "未知"
    return f"""
            你是顶级A股量化基金经理。请对 {target}（最新价 ¥{price_text}）出具深度研报。

            {verified_technical_prompt}

            【事实边界硬规则】：
            1. 云记忆、manager_rules、processed_sources、用户投喂资料不能作为已验证事实，只能放入“投喂资料观点 / 历史假设 / 待验证线索”。
            2. market_news / yfinance.news 只能作为新闻线索，不是公告、监管、诉讼、处罚、减持、业绩预告等官方事实。
            3. 已验证事实只能来自 Tushare、verified_technical_facts、交易所/公司公告或其他可信结构化返回；其他资料必须标注为待验证线索。
            4. 如果缺少 Tushare / 官方公告 / 可信原文验证，对订单、授权、客户、机构席位、资金流统一写“暂无可验证数据”。
            5. 不得仅凭技术形态写“主力高度控盘、机构加仓、游资接力、资金涌入”等资金事实；没有 Tushare 验证时，只能写“资金行为待验证”。

            【要求】：
            1. 字数不少于 800 字
            2. 从四大维度深度拆解：基本面、情绪共振、技术面、操作指令
            3. 明确的买入/卖出信号和止损止盈位
            4. 如果【已验证技术事实】中已有 MA60、RSI、量能、20日/60日涨跌或60日回撤，不得说缺少对应技术数据。
            5. 技术指标只能作为观察条件和验证条件，不得因为 RSI 高、RSI 低、站上 MA60 或量能变化直接给确定性买入/卖出结论。
            6. 技术事实必须和 moneyflow、龙虎榜、涨跌停、融资融券分层，不得混为同一类证据。
            {unverified_inject}
            """


def build_a_share_next_day_plan_prompt(
    target: str = "",
    fact_packet: Any = None,
    verified_technical_prompt: str = "",
) -> str:
    target = target or "未指定标的"
    fact_packet_text = _dump_fact_packet(fact_packet)
    return f"""
你是A股次日观察计划生成器。标的：{target}。本功能只生成“次日观察计划”，不是自动交易指令。

请严格基于下方【次日交易计划事实包】输出，不允许引用事实包以外的公告、订单、客户、席位或实时资金。

{verified_technical_prompt}

【次日交易计划事实包】
{fact_packet_text}

【固定输出格式】
必须逐字使用以下标题与条目，不要改标题：

【次日交易计划】

一、当前状态摘要
- 当前价格：
- 涨停价：
- 跌停价：
- moneyflow 状态：
	- 龙虎榜状态：
	- 融资融券状态：
	- 涨跌停/炸板记录：
	- 筹码压力：
	- 持仓状态：
	- 数据缺失项：

二、强势高开 / 冲高情景
- 观察条件：
- 可考虑动作：
- 不追高条件：
- 放弃条件：

三、平开震荡情景
- 观察条件：
- 可考虑动作：
- 做T条件：
- 放弃条件：

四、低开走弱情景
- 观察条件：
- 风控条件：
- 减仓 / 只观察条件：
- 放弃条件：

五、次日验证清单
- 资金验证：
- 量价验证：
	- 龙虎榜验证：
	- 情绪验证：
	- 筹码压力验证：
	- 公告/新闻验证：

六、纪律提醒
- 未满足验证条件前仅观察。
- 所有交易动作需要用户人工确认。
- 不得因为单一指标直接买入或卖出。
- 不得自动下单。

【强制规则】
1. 本功能是“次日观察计划”，不是自动交易指令。
2. 不允许写“必买、必卖、满仓、梭哈、确定上涨、确定反包”。
3. 不允许自动下单。
4. 不允许编造公告、订单、客户、席位。
5. 涨停价/跌停价只作为交易边界参考，不能作为长期支撑/压力。
6. 不得写“跌破跌停价”。
7. 没有真实 moneyflow，不得写主力流入/流出。
8. 没有真实龙虎榜，不得写机构席位。
9. 没有真实 limit_list_d，不得写涨停/炸板/连板。
10. margin_detail 只能代表融资融券/杠杆资金，不能等同于主力资金或机构资金。
11. 所有结论必须区分“已验证数据”和“谨慎推断”。
12. 若数据缺失，必须写“暂无可验证数据”。
13. 不得给确定性买卖建议；只能输出观察条件、人工确认前提和风险边界。
14. 可考虑动作只能使用“观察、等待验证、小仓试错需人工确认、降低风险暴露、只观察、放弃观察”等非确定性措辞。
15. 涉及 moneyflow、龙虎榜、limit_list_d 时，必须先检查对应 available 或 records_available 字段；字段为 false 时只能写“暂无可验证数据”。
16. 必须优先读取 position_profile.normalized_position_state，不得只根据 position_status 或 position_summary 的自然语言判断持仓。
17. 当 normalized_position_state == "已持仓" 时：可以输出浮盈/浮亏、做T条件、减仓条件、持仓风控、止损/止盈观察。
18. 当 normalized_position_state == "未买入，有参考成本/计划价格" 时：必须说明该价格是参考成本/计划价格；不得计算浮盈/浮亏；不得输出做T、T出、降低成本；可以输出观察条件、试仓条件、放弃条件；试仓如出现，必须写“0.5–1成试仓，需人工确认”。
19. 当 normalized_position_state == "未买入，纯观察" 时：不得计算浮盈/浮亏；不得输出做T；只输出观察条件和放弃条件；除非资金、量价、情绪至少两项改善，否则不得输出试仓。
20. 当 normalized_position_state == "已持仓但缺少持仓数量" 时：不得计算精确浮盈；不得输出精确做T数量；可以输出低置信度持仓风控提醒，并必须提示“缺少持仓数量，持仓计划将按低置信度处理”。
21. 若 position_profile.allow_pnl 为 false，当前状态摘要里必须写“不计算浮盈浮亏”；若 allow_t_plan 为 false，“做T条件”只能写“不适用：未确认实际持仓，不做T”。
22. 若 verified_technical_facts.available 为 true，必须引用至少 2 个【已验证技术事实】；已有字段不得再写“缺少该技术数据”。
23. 如果技术事实显示 RSI 高位、涨幅较大、回撤较小，只能用于风险提示和次日验证条件，不得直接写买入或卖出。
24. 技术指标只能作为观察条件和验证条件；RSI 高位不等于必跌，RSI 低位不等于必涨，站上 MA60 不等于买入信号，量能放大/缩小不得单独推断主力行为。
25. 技术事实必须和 moneyflow、龙虎榜、涨跌停、融资融券分层，不得混为同一类证据。
26. 筹码/胜率只能作为观察和验证条件，不得直接触发买卖。
27. 筹码集中不是必涨，获利盘高不是必卖，套牢盘重不是必买。
28. 必须把筹码压力分为获利盘兑现压力、套牢盘压力、当前价相对筹码中枢三类观察项。
	"""


def build_a_share_war_room_prompt(
    target: str = "",
    fact_packet: Any = None,
    verified_technical_prompt: str = "",
) -> str:
    target = target or "未指定标的"
    packet = _as_mapping(fact_packet)
    chip_radar = _as_mapping(packet.get("chip_radar"))
    fact_packet_text = _dump_fact_packet(packet)
    return f"""
你是A股单票作战室与换仓雷达。标的：{target}。本功能是作战计划，不是自动交易指令。

请严格基于下方【单票作战室事实包】输出，不允许引用事实包以外的公告、订单、客户、席位或实时资金。

{verified_technical_prompt}

	【单票作战室事实包】
	{fact_packet_text}

	【已验证筹码事实】
	- 胜率 / 获利盘比例：{chip_radar.get("winner_rate") or "暂无可验证数据"}
	- 平均筹码成本：{chip_radar.get("weight_avg") or "暂无可验证数据"}
	- 筹码分位：{chip_radar.get("cost_5pct") or "暂无"} / {chip_radar.get("cost_50pct") or "暂无"} / {chip_radar.get("cost_95pct") or "暂无"}
	- 筹码压力评价：{chip_radar.get("chip_pressure_comment") or "暂无可验证数据"}

【固定输出格式】
必须逐字使用以下标题与条目，不要改标题：
只能输出以下五段，五段后立即结束；不得新增总结、免责声明、复盘、补充建议或任何额外段落。

【单票作战室】

一、当前票状态
- 持仓状态：
- 当前价格：
- 技术状态：
- 资金状态：
- 龙虎榜状态：
- 涨跌停/情绪状态：
- 主升浪状态：
- 风险等级：

二、卖出 / 减仓信号
- 继续持有条件：
- 分批减仓条件：
- 清仓/放弃条件：
- 只做T不加仓条件：

三、主升浪持有纪律
- 哪些条件没坏就继续拿：
- 哪些条件坏了要降低仓位：
- 哪些是假跌破/正常震荡：
- 哪些是真破位：

四、换仓候选
- 候选方向：
- 候选标的：
- 已验证数据依据：
- 买入触发条件：
- 放弃条件：
- 建议观察仓位：

五、仓位建议
- 当前票建议仓位：
- 新票试仓仓位：
- 是否允许加仓：
- 是否禁止追高：
- 最大风险暴露：

【硬规则】
1. 本功能是作战计划，不是自动交易指令。
2. 不自动下单。
3. 不写必买、必卖、满仓、梭哈、确定上涨。
4. 仓位建议只能是区间：0、0.5–1成、1–2成、2–3成；不得建议满仓。
5. 未持仓不得输出做T、T出、降低成本。
6. 已持仓才允许输出做T/减仓/持仓风控。
7. 主升浪判断必须基于 verified_technical_facts、moneyflow_data、limit_emotion_data、market_style_fact_packet，不得只靠故事、投喂资料或主观判断。
8. 如果当前票仍在主升结构中，不得因为单日震荡直接建议卖出。
9. 如果资金、量价、情绪三项共振转弱，必须提示降低仓位或只观察。
10. 没有真实 Tushare 数据时，必须写“暂无可验证数据”。
11. 换仓候选如果只来自 session_state 或今日关注池文本，必须标注“待验证线索”，不能写成已验证机会。
12. 投喂资料、云记忆、manager_rules 只能作为待验证线索。
13. 涨停价/跌停价只作为交易边界参考，不能作为长期支撑/压力。
14. 不得写“跌破跌停价”。
15. 如果 rotation_context.watch_targets 为空，四、换仓候选的“候选标的”必须写“暂无可验证换仓候选”。
16. 当 position_permissions.allow_t_plan 为 false，“只做T不加仓条件”只能写“不适用：未确认实际持仓，不做T”。
17. 当 position_permissions.allow_reduce_plan 为 false，不得输出实际减仓动作，只能输出观察或放弃条件。
18. 当 position_permissions.allow_trial_entry 为 false，新票试仓仓位只能写“0”或“不适用”。
19. 所有交易动作都必须写明“需人工确认”。
20. 所有结论必须区分“已验证数据”和“待验证线索/谨慎推断”。
21. 禁止在“五、仓位建议”后追加【作战计划总结】、总结段、风险提示段或任何额外内容。
22. 筹码集中不是必涨。
23. 获利盘高不是必卖。
24. 筹码只能用于主升浪健康度、风险压力和持仓纪律验证。
25. 不得把筹码数据写成确定性买卖信号。
	"""
