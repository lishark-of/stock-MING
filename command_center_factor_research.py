from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any


LIBRARY_PACKET_KEY = "command_center_factor_library_packet"
LEDGER_PACKET_KEY = "command_center_factor_data_ledger_packet"
GOVERNANCE_PACKET_KEY = "command_center_factor_governance_packet"

PHASE = "phase_1_research_ledger_library"
SOURCE_TYPE = "local_factor_research_scaffold"

DECISION_USAGE_POLICY = {
    "display_only": True,
    "enters_strategy_action": False,
    "enters_core_action": False,
    "enters_next_session_projection": False,
    "enters_evidence_effects": False,
    "enters_deepseek_prompt": False,
    "note": "因子研究仅用于证据质量和研究解释，不作为交易指令。",
}

RISK_BOUNDARIES = [
    "因子研究不是交易建议。",
    "因子分数不直接生成买卖。",
    "回测收益不代表未来收益。",
    "Forum/blog 只作产品灵感，不作有效性证据。",
    "DeepSeek 不能发明因子检验结果。",
    "Tushare 必须区分 data_date 与 local_fetched_at。",
    "财报因子必须使用公告日期，不得用报告期冒充可得日期。",
    "涨跌停、停牌、ST、次新、流动性必须进入过滤和风险说明。",
    "因子进入 strategy action 需要单独审批、独立测试和用户确认。",
    "所有外部调用必须 button-gated 或 cache-gated。",
]

VALIDATION_STANDARDS = {
    "invalid": "PIT/公告日/未来函数检查失败，或样本覆盖不足，或样本外方向反转，或成本后收益长期为负。",
    "disabled": "缺失率过高、ICIR 为负、分组收益不单调、换手成本不可用，或近期明显衰减。",
    "watchlist": "覆盖率和方向线索尚可，但 IC、Rank IC 或滚动稳定性不足。",
    "research_pass": "覆盖率、缺失率、ICIR、分组收益、成本后表现和中性化检验均达到研究通过阈值。",
}

FACTOR_RESEARCH_LIBRARY = [
    {
        "factor_key": "momentum_5d",
        "factor_name": "5日动量",
        "category": "价格动量",
        "formula_summary": "close / close_5d - 1",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["追涨", "涨跌停约束"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "momentum_20d",
        "factor_name": "20日动量",
        "category": "价格动量",
        "formula_summary": "close / close_20d - 1",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["趋势拥挤"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "momentum_60d",
        "factor_name": "60日动量",
        "category": "价格动量",
        "formula_summary": "close / close_60d - 1",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["长周期滞后"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "breakout_20d",
        "factor_name": "20日突破强度",
        "category": "价格动量",
        "formula_summary": "close / max(high_20d)",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["假突破"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "reversal_1d",
        "factor_name": "1日反转",
        "category": "短期反转",
        "formula_summary": "-1 * return_1d",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["T+1", "涨跌停"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "reversal_5d",
        "factor_name": "5日短反转",
        "category": "短期反转",
        "formula_summary": "-1 * return_5d",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["趋势票误杀"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "bias_ma20",
        "factor_name": "MA20乖离",
        "category": "短期反转",
        "formula_summary": "close / ma20 - 1",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["verified_technical_facts"],
        "PIT_safe": True,
        "known_risks": ["强趋势中失效"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "volatility_20d",
        "factor_name": "20日波动率",
        "category": "波动/风险",
        "formula_summary": "std(return_1d, 20)",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["高波动非方向"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "atr_pct_14d",
        "factor_name": "ATR比例",
        "category": "波动/风险",
        "formula_summary": "ATR14 / close",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["缺 high/low"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "max_drawdown_60d",
        "factor_name": "60日最大回撤",
        "category": "波动/风险",
        "formula_summary": "min(close / rolling_peak_60d - 1)",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["回撤后反弹"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "turnover_rate",
        "factor_name": "换手率",
        "category": "成交/流动性",
        "formula_summary": "daily_basic.turnover_rate",
        "source_interfaces": ["tushare.daily_basic"],
        "required_packets": ["facts/data_capability"],
        "PIT_safe": True,
        "known_risks": ["权限", "更新滞后"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "amount_20d_rank",
        "factor_name": "20日成交额分位",
        "category": "成交/流动性",
        "formula_summary": "rank(mean(amount_20d))",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["daily_close_packet"],
        "PIT_safe": True,
        "known_risks": ["大票偏置"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "volume_ratio_20d",
        "factor_name": "放量比例",
        "category": "成交/流动性",
        "formula_summary": "volume / mean(volume_20d)",
        "source_interfaces": ["tushare.daily"],
        "required_packets": ["verified_technical_facts"],
        "PIT_safe": True,
        "known_risks": ["缩量涨停误判"],
        "first_stage_usage": "evidence_effect_only",
    },
    {
        "factor_key": "main_net_5d",
        "factor_name": "近5日主力净流",
        "category": "资金流",
        "formula_summary": "sum(main_net_yi, 5d)",
        "source_interfaces": ["tushare.moneyflow"],
        "required_packets": ["command_center_moneyflow_packet"],
        "PIT_safe": True,
        "known_risks": ["盘后口径"],
        "first_stage_usage": "evidence_effect_only",
    },
    {
        "factor_key": "retail_net_5d",
        "factor_name": "近5日小单净流",
        "category": "资金流",
        "formula_summary": "sum(small_net_yi, 5d)",
        "source_interfaces": ["tushare.moneyflow"],
        "required_packets": ["command_center_moneyflow_packet"],
        "PIT_safe": True,
        "known_risks": ["资金口径误读"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "pe_ttm_rank",
        "factor_name": "PE_TTM分位",
        "category": "估值",
        "formula_summary": "rank(pe_ttm)",
        "source_interfaces": ["tushare.daily_basic"],
        "required_packets": [LEDGER_PACKET_KEY],
        "PIT_safe": True,
        "known_risks": ["亏损股异常"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "pb_rank",
        "factor_name": "PB分位",
        "category": "估值",
        "formula_summary": "rank(pb)",
        "source_interfaces": ["tushare.daily_basic"],
        "required_packets": [LEDGER_PACKET_KEY],
        "PIT_safe": True,
        "known_risks": ["行业差异"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "ps_ttm_rank",
        "factor_name": "PS_TTM分位",
        "category": "估值",
        "formula_summary": "rank(ps_ttm)",
        "source_interfaces": ["tushare.daily_basic"],
        "required_packets": [LEDGER_PACKET_KEY],
        "PIT_safe": True,
        "known_risks": ["高成长误杀"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "roe_latest",
        "factor_name": "ROE",
        "category": "质量",
        "formula_summary": "latest disclosed ROE",
        "source_interfaces": ["tushare.fina_indicator"],
        "required_packets": ["future_financial_packet"],
        "PIT_safe": "conditional",
        "known_risks": ["公告日错位"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "gross_margin_latest",
        "factor_name": "毛利率",
        "category": "质量",
        "formula_summary": "latest disclosed gross margin",
        "source_interfaces": ["tushare.fina_indicator"],
        "required_packets": ["future_financial_packet"],
        "PIT_safe": "conditional",
        "known_risks": ["财报口径", "PIT"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "revenue_growth_yoy",
        "factor_name": "营收增长",
        "category": "成长",
        "formula_summary": "latest disclosed yoy_sales",
        "source_interfaces": ["tushare.fina_indicator"],
        "required_packets": ["future_financial_packet"],
        "PIT_safe": "conditional",
        "known_risks": ["公告日错位"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "profit_growth_yoy",
        "factor_name": "利润增长",
        "category": "成长",
        "formula_summary": "latest disclosed yoy_profit",
        "source_interfaces": ["tushare.fina_indicator"],
        "required_packets": ["future_financial_packet"],
        "PIT_safe": "conditional",
        "known_risks": ["单季波动"],
        "first_stage_usage": "research_only",
    },
    {
        "factor_key": "hard_risk_flag",
        "factor_name": "硬风险标记",
        "category": "公告/硬风险",
        "formula_summary": "减持 / 质押 / 解禁 / 公告风险",
        "source_interfaces": ["tushare.anns_d", "tushare.pledge_stat", "tushare.share_float"],
        "required_packets": ["command_center_hard_risk_packet"],
        "PIT_safe": True,
        "known_risks": ["无记录不等于无风险"],
        "first_stage_usage": "evidence_effect_only",
    },
    {
        "factor_key": "limit_heat_score",
        "factor_name": "涨跌停情绪",
        "category": "涨跌停/情绪",
        "formula_summary": "limit records + concept heat",
        "source_interfaces": ["tushare.stk_limit", "tushare.limit_list_d", "tushare.limit_cpt_list"],
        "required_packets": ["command_center_limit_emotion_packet"],
        "PIT_safe": True,
        "known_risks": ["概念不等于个股"],
        "first_stage_usage": "evidence_effect_only",
    },
    {
        "factor_key": "chip_winner_rate",
        "factor_name": "获利盘比例",
        "category": "筹码/胜率",
        "formula_summary": "cyq_perf.winner_rate",
        "source_interfaces": ["tushare.cyq_perf"],
        "required_packets": ["command_center_chip_packet"],
        "PIT_safe": True,
        "known_risks": ["胜率不能等于买点"],
        "first_stage_usage": "evidence_effect_only",
    },
    {
        "factor_key": "chokepoint_method_hint",
        "factor_name": "瓶颈方法启发",
        "category": "产业链/方法",
        "formula_summary": "产业链瓶颈与政策适配标签",
        "source_interfaces": ["local.command_center_chokepoint_scan_packet"],
        "required_packets": ["command_center_chokepoint_scan_packet"],
        "PIT_safe": "n/a",
        "known_risks": ["方法论不是因子收益"],
        "first_stage_usage": "research_only",
    },
]


def _copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _now_iso(now: Any = None) -> str:
    if isinstance(now, _dt.datetime):
        return now.isoformat(timespec="seconds")
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min).isoformat(timespec="seconds")
    if isinstance(now, str) and now.strip():
        return now.strip()
    return _dt.datetime.now().isoformat(timespec="seconds")


def _packet_keys(available_packets: Any = None) -> set[str]:
    if isinstance(available_packets, Mapping):
        return {str(key) for key, value in available_packets.items() if value}
    if isinstance(available_packets, (list, tuple, set)):
        return {str(value) for value in available_packets if value}
    return set()


def _ledger_status_for_factor(factor: Mapping[str, Any], available_keys: set[str]) -> tuple[str, str, bool]:
    required_packets = [str(item) for item in factor.get("required_packets") or []]
    if not required_packets:
        return "definition_only", "仅定义因子，暂无绑定 packet。", False
    if all(packet in available_keys for packet in required_packets):
        return "verified_present", "所需 packet 在当前会话中可见；仍需后续 PIT 与缺失率检验。", True
    if any(packet in available_keys for packet in required_packets):
        return "partial_packet_present", "部分依赖 packet 可见，不能据此计算完整因子。", False
    return "not_loaded", "当前只展示依赖关系，不自动调用 Tushare 或外部接口补数。", False


def _factor_display_row(factor: Mapping[str, Any]) -> dict:
    row = _copy_json(factor)
    row["source_interfaces"] = list(row.get("source_interfaces") or [])
    row["required_packets"] = list(row.get("required_packets") or [])
    row["known_risks"] = list(row.get("known_risks") or [])
    row["pit_requirement"] = _pit_requirement(row)
    row["pit_validated"] = False
    row["lookahead_risk_note"] = _lookahead_risk_note(row)
    row["enabled_phase"] = PHASE
    row["source_type"] = SOURCE_TYPE
    row["enters_core_action"] = False
    row["enters_strategy_action"] = False
    row["enters_next_session_projection"] = False
    row["enters_deepseek_prompt"] = False
    return row


def _pit_requirement(factor: Mapping[str, Any]) -> str:
    interfaces = {str(item) for item in factor.get("source_interfaces") or []}
    if any("fina_indicator" in item for item in interfaces):
        return "必须使用公告日期 / 实际可得日期，不能用报告期冒充可得日期。"
    if any(item in interfaces for item in {"tushare.daily", "tushare.daily_basic", "tushare.moneyflow"}):
        return "必须使用交易日收盘后可得数据，并记录 data_date 与 local_fetched_at。"
    if any("anns_d" in item or "share_float" in item or "pledge" in item for item in interfaces):
        return "必须使用公告披露时间和本地抓取时间，缺公告不等于无风险。"
    if any("local." in item for item in interfaces):
        return "本地方法启发只可记录生成时间，不可当作已验证收益因子。"
    return "已声明 PIT 处理要求，Phase 1 尚未验证。"


def _lookahead_risk_note(factor: Mapping[str, Any]) -> str:
    pit_value = factor.get("PIT_safe")
    if pit_value == "conditional":
        return "存在公告日错位风险；需后续用公告日期 / 实际可得日期复核。"
    if pit_value == "n/a":
        return "方法论标签不计算收益，不能作为交易信号。"
    return "Phase 1 仅声明要求，尚未完成 lookahead / survivorship / missing-rate 检验。"


def build_factor_library_packet(now: Any = None) -> dict:
    factors = [_factor_display_row(factor) for factor in FACTOR_RESEARCH_LIBRARY]
    categories: dict[str, int] = {}
    usage_counts: dict[str, int] = {}
    for factor in factors:
        category = str(factor.get("category") or "未分类")
        usage = str(factor.get("first_stage_usage") or "research_only")
        categories[category] = categories.get(category, 0) + 1
        usage_counts[usage] = usage_counts.get(usage, 0) + 1
    return {
        "packet_key": LIBRARY_PACKET_KEY,
        "phase": PHASE,
        "source_type": SOURCE_TYPE,
        "title": "Factor Research Lab 因子库",
        "summary": "Phase 1 只定义基础因子、数据依赖和研究边界；不回测、不评分、不交易。",
        "updated_at": _now_iso(now),
        "factor_count": len(factors),
        "category_counts": categories,
        "first_stage_usage_counts": usage_counts,
        "factors": factors,
        "decision_usage_policy": _copy_json(DECISION_USAGE_POLICY),
        "risk_boundaries": _copy_json(RISK_BOUNDARIES),
        "validation_standards": _copy_json(VALIDATION_STANDARDS),
        "deepseek_called": False,
        "tushare_called": False,
        "external_calls_triggered": False,
    }


def build_factor_data_ledger_packet(
    factor_library: Any = None,
    available_packets: Any = None,
    now: Any = None,
) -> dict:
    if isinstance(factor_library, Mapping):
        factors = factor_library.get("factors") or []
    elif isinstance(factor_library, list):
        factors = factor_library
    else:
        factors = [_factor_display_row(factor) for factor in FACTOR_RESEARCH_LIBRARY]
    available_keys = _packet_keys(available_packets)
    ledger_rows = []
    status_counts: dict[str, int] = {}
    for factor in factors:
        if not isinstance(factor, Mapping):
            continue
        status, status_note, has_local_packet = _ledger_status_for_factor(factor, available_keys)
        status_counts[status] = status_counts.get(status, 0) + 1
        pit_value = factor.get("PIT_safe")
        ledger_rows.append(
            {
                "factor_key": factor.get("factor_key"),
                "factor_name": factor.get("factor_name"),
                "category": factor.get("category"),
                "source_interfaces": list(factor.get("source_interfaces") or []),
                "required_packets": list(factor.get("required_packets") or []),
                "data_date_range": [],
                "local_fetched_at": None,
                "PIT_safe": pit_value,
                "pit_requirement": factor.get("pit_requirement") or _pit_requirement(factor),
                "pit_validated": False,
                "point_in_time_safe": False,
                "lookahead_risk": pit_value in {"conditional", False},
                "lookahead_risk_note": factor.get("lookahead_risk_note") or _lookahead_risk_note(factor),
                "missing_rate": None,
                "universe": "a_share_watchlist | hs300 | custom_pool",
                "status": status,
                "status_note": status_note,
                "has_local_packet": has_local_packet,
                "first_stage_usage": factor.get("first_stage_usage") or "research_only",
                "source_type": SOURCE_TYPE,
                "enters_strategy_action": False,
                "enters_core_action": False,
                "enters_next_session_projection": False,
                "enters_deepseek_prompt": False,
            }
        )
    return {
        "packet_key": LEDGER_PACKET_KEY,
        "phase": PHASE,
        "source_type": SOURCE_TYPE,
        "title": "Factor Data Ledger 因子数据血缘",
        "summary": "只读展示因子所需接口、packet、PIT 与缺失风险；不会自动取数。",
        "updated_at": _now_iso(now),
        "ledger_rows": ledger_rows,
        "factor_count": len(ledger_rows),
        "status_counts": status_counts,
        "available_packet_keys": sorted(available_keys),
        "decision_usage_policy": _copy_json(DECISION_USAGE_POLICY),
        "deepseek_called": False,
        "tushare_called": False,
        "external_calls_triggered": False,
    }


def build_factor_governance_packet(now: Any = None) -> dict:
    return {
        "packet_key": GOVERNANCE_PACKET_KEY,
        "phase": PHASE,
        "source_type": SOURCE_TYPE,
        "title": "Factor Governance 因子治理边界",
        "summary": "Phase 1 仅允许 research display；进入 evidence_effects、strategy trace 或 core action 都需要后续审批。",
        "updated_at": _now_iso(now),
        "allow_research_display": True,
        "allow_evidence_effects": False,
        "allow_strategy_trace": False,
        "allow_core_action": False,
        "decision_usage_policy": _copy_json(DECISION_USAGE_POLICY),
        "risk_boundaries": _copy_json(RISK_BOUNDARIES),
        "validation_standards": _copy_json(VALIDATION_STANDARDS),
        "deepseek_called": False,
        "tushare_called": False,
        "external_calls_triggered": False,
    }
