from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import statistics
from collections.abc import Mapping
from numbers import Number
from typing import Any


LIBRARY_PACKET_KEY = "command_center_factor_library_packet"
LEDGER_PACKET_KEY = "command_center_factor_data_ledger_packet"
GOVERNANCE_PACKET_KEY = "command_center_factor_governance_packet"
RUNTIME_PACKET_KEY = "command_center_factor_runtime_packet"
TEST_PACKET_KEY = "command_center_factor_test_packet"
SCORE_PACKET_KEY = "command_center_factor_score_packet"
QUANT_HUB_PACKET_KEY = "command_center_factor_quant_hub_packet"

PHASE = "phase_1_research_ledger_library"
MVP_PHASE = "phase_2_light_factor_quant_hub"
SOURCE_TYPE = "local_factor_research_scaffold"
QUANT_HUB_SCHEMA_VERSION = "factor_quant_hub.v1"

DEEPSEEK_EXPLANATION_ALLOWED_KEYS = {
    "summary",
    "support_notes",
    "suppress_notes",
    "conflict_notes",
    "missing_data_notes",
    "discipline_notes",
}
SCORE_EXCLUDED_FACTOR_KEYS = {"chokepoint_method_hint", "serenity_method_source"}
FRESHNESS_MAX_AGE_DAYS = 7
FRESHNESS_STALE_MAX_AGE_DAYS = 30
FRESHNESS_STALE_TRADING_DAY_LAG = 3
A_SHARE_MARKET_OPEN_TIME = _dt.time(9, 30)
A_SHARE_CALL_AUCTION_START_TIME = _dt.time(9, 15)
A_SHARE_MORNING_CLOSE_TIME = _dt.time(11, 30)
A_SHARE_AFTERNOON_OPEN_TIME = _dt.time(13, 0)
A_SHARE_MARKET_CLOSE_TIME = _dt.time(15, 0)
A_SHARE_DATA_READY_TIME = _dt.time(16, 30)

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
    "not_enough_data": "样本、forward return、行业/市值或 PIT 信息不足，只能保留为待检验研究项。",
}

FACTOR_TEST_METRIC_SCHEMA = [
    {"metric_key": "coverage", "label": "数据覆盖率", "required": True, "unit": "ratio"},
    {"metric_key": "missing_rate", "label": "缺失率", "required": True, "unit": "ratio"},
    {"metric_key": "ic_mean", "label": "IC 均值", "required": True, "unit": "decimal"},
    {"metric_key": "ic_std", "label": "IC 标准差", "required": True, "unit": "decimal"},
    {"metric_key": "icir", "label": "ICIR", "required": True, "unit": "ratio"},
    {"metric_key": "rank_ic_mean", "label": "Rank IC 均值", "required": True, "unit": "decimal"},
    {"metric_key": "top_bottom_group_return", "label": "Top-Bottom 分组收益", "required": True, "unit": "return"},
    {"metric_key": "group_return_monotonicity", "label": "分组收益单调性", "required": True, "unit": "boolean"},
    {"metric_key": "turnover", "label": "换手率", "required": True, "unit": "ratio"},
    {"metric_key": "cost_adjusted_return", "label": "成本后收益", "required": True, "unit": "return"},
    {"metric_key": "max_drawdown", "label": "最大回撤", "required": True, "unit": "return"},
    {"metric_key": "industry_neutral_ic", "label": "行业中性 IC", "required": True, "unit": "decimal"},
    {"metric_key": "market_cap_neutral_ic", "label": "市值中性 IC", "required": True, "unit": "decimal"},
    {"metric_key": "out_of_sample_stability", "label": "样本外稳定性", "required": True, "unit": "status"},
    {"metric_key": "recent_decay", "label": "近期衰减", "required": True, "unit": "status"},
    {"metric_key": "pit_check", "label": "PIT 检查", "required": True, "unit": "status"},
    {"metric_key": "lookahead_check", "label": "未来函数检查", "required": True, "unit": "status"},
    {"metric_key": "survivorship_check", "label": "幸存者偏差检查", "required": True, "unit": "status"},
]

FACTOR_TEST_MODE_PLAN = [
    {
        "mode": "light",
        "scope": "当前持仓 / 当前标的 / 关注池",
        "status": "scaffold_ready",
        "allowed": True,
        "notes": "先生成研究指标结构；只用小样本和缓存/按钮任务数据，不跑全市场重回测。",
    },
    {
        "mode": "small_research",
        "scope": "小股票池 + 短窗口",
        "status": "planned",
        "allowed": False,
        "notes": "下一阶段再接横截面 forward return 与分组收益。",
    },
    {
        "mode": "full",
        "scope": "全市场 / 长窗口",
        "status": "disabled",
        "allowed": False,
        "notes": "需要独立审批、成本/停牌/涨跌停/PIT 全检查后才允许。",
    },
]

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
    {
        "factor_key": "serenity_method_source",
        "factor_name": "Serenity 方法来源",
        "category": "Serenity 方法来源",
        "formula_summary": "本地方法来源基线与防幻觉机制标签",
        "source_interfaces": ["local.command_center_serenity_method_radar_packet"],
        "required_packets": ["command_center_serenity_method_radar_packet"],
        "PIT_safe": "n/a",
        "known_risks": ["方法来源不是因子收益", "不进入交易评分"],
        "first_stage_usage": "research_only",
    },
]


def _copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _to_number(value: Any, default: float | None = None) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return default
    if isinstance(value, Number):
        number = float(value)
        return number if math.isfinite(number) else default
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text in {"--", "N/A", "None", "nan", "暂无"}:
        return default
    try:
        number = float(text)
    except Exception:
        return default
    return number if math.isfinite(number) else default


def _safe_round(value: Any, digits: int = 6) -> float | None:
    number = _to_number(value)
    if number is None:
        return None
    return round(number, digits)


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10] if len(text) >= 10 else text


def _now_iso(now: Any = None) -> str:
    if isinstance(now, _dt.datetime):
        return now.isoformat(timespec="seconds")
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min).isoformat(timespec="seconds")
    if isinstance(now, str) and now.strip():
        return now.strip()
    return _dt.datetime.now().isoformat(timespec="seconds")


def _parse_date(value: Any) -> _dt.date | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = _date_text(text)
    for candidate, fmt in ((text[:8], "%Y%m%d"), (normalized[:10], "%Y-%m-%d"), (text[:10], "%Y/%m/%d")):
        try:
            return _dt.datetime.strptime(candidate, fmt).date()
        except (TypeError, ValueError):
            continue
    return None


def _now_datetime(now: Any = None) -> _dt.datetime:
    if isinstance(now, _dt.datetime):
        return now
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min)
    text = str(now or "").strip()
    if text:
        try:
            return _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            parsed = _parse_date(text)
            if parsed is not None:
                return _dt.datetime.combine(parsed, _dt.time.min)
    return _dt.datetime.now()


def _now_date(now: Any = None) -> _dt.date:
    return _now_datetime(now).date()


def _rows_from_packet(packet: Any) -> list[dict]:
    mapping = _as_mapping(packet)
    candidates = packet if isinstance(packet, list) else []
    if mapping:
        for key in ("rows", "data", "items", "records"):
            value = mapping.get(key)
            if isinstance(value, list):
                candidates = value
                break
        if not candidates and isinstance(mapping.get("data"), Mapping):
            nested = _as_mapping(mapping.get("data"))
            for key in ("rows", "items", "records"):
                value = nested.get(key)
                if isinstance(value, list):
                    candidates = value
                    break
    return [dict(item) for item in candidates if isinstance(item, Mapping)]


def _calendar_is_open(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "open", "交易"}


def _clean_trade_calendar_rows(trade_calendar_packet: Any = None) -> list[dict[str, Any]]:
    rows = []
    for item in _rows_from_packet(trade_calendar_packet):
        date_value = _parse_date(item.get("cal_date") or item.get("trade_date") or item.get("date"))
        if date_value is None:
            continue
        rows.append({"cal_date": date_value, "is_open": _calendar_is_open(item.get("is_open", 1))})
    rows.sort(key=lambda row: row["cal_date"])
    return rows


def _fallback_weekday_calendar(today: _dt.date, *, lookback_days: int = 120, lookahead_days: int = 10) -> list[dict[str, Any]]:
    start = today - _dt.timedelta(days=lookback_days)
    end = today + _dt.timedelta(days=lookahead_days)
    rows = []
    cursor = start
    while cursor <= end:
        rows.append({"cal_date": cursor, "is_open": cursor.weekday() < 5})
        cursor += _dt.timedelta(days=1)
    return rows


def _previous_open_day(open_days: list[_dt.date], today: _dt.date) -> _dt.date | None:
    candidates = [day for day in open_days if day < today]
    return candidates[-1] if candidates else None


def _next_open_day(open_days: list[_dt.date], today: _dt.date) -> _dt.date | None:
    candidates = [day for day in open_days if day > today]
    return candidates[0] if candidates else None


def _calendar_coverage_status(rows: list[dict[str, Any]], today: _dt.date, *, validated: bool) -> str:
    if not validated:
        return "fallback_weekday_calendar"
    if not rows:
        return "missing_calendar_rows"
    cal_dates = {row["cal_date"] for row in rows}
    if today not in cal_dates:
        return "partial_missing_today"
    if not any(row["cal_date"] < today and row.get("is_open") for row in rows):
        return "partial_missing_previous_open"
    if not any(row["cal_date"] > today and row.get("is_open") for row in rows):
        return "validated_no_next_open"
    return "validated"


def _market_session_detail(now_dt: _dt.datetime, *, today_is_open: bool) -> str:
    if not today_is_open:
        return "non_trading_day"
    current = now_dt.time()
    if current < A_SHARE_CALL_AUCTION_START_TIME:
        return "before_call_auction"
    if current < A_SHARE_MARKET_OPEN_TIME:
        return "opening_call_auction"
    if current < A_SHARE_MORNING_CLOSE_TIME:
        return "morning_continuous_auction"
    if current < A_SHARE_AFTERNOON_OPEN_TIME:
        return "lunch_break"
    if current < A_SHARE_MARKET_CLOSE_TIME:
        return "afternoon_continuous_auction"
    if current < A_SHARE_DATA_READY_TIME:
        return "post_close_data_delay_window"
    return "after_eod_data_ready"


def _expected_data_date(now: Any = None, trade_calendar_packet: Any = None) -> dict[str, Any]:
    now_dt = _now_datetime(now)
    today = now_dt.date()
    rows = _clean_trade_calendar_rows(trade_calendar_packet)
    calendar_validated = bool(rows)
    if not rows:
        rows = _fallback_weekday_calendar(today)
    open_days = sorted(row["cal_date"] for row in rows if row.get("is_open"))
    today_is_open = today in open_days
    previous_open = _previous_open_day(open_days, today)
    next_open = _next_open_day(open_days, today)
    today_eod_available = bool(today_is_open and now_dt.time() >= A_SHARE_DATA_READY_TIME)
    session_detail = _market_session_detail(now_dt, today_is_open=today_is_open)
    data_update_delay_guard_active = bool(today_is_open and A_SHARE_MARKET_CLOSE_TIME <= now_dt.time() < A_SHARE_DATA_READY_TIME)
    current_time = now_dt.time()
    if today_is_open and now_dt.time() < A_SHARE_MARKET_OPEN_TIME:
        phase = "pre_open"
        expected = previous_open
        expected_source = "previous_completed_trading_day"
    elif today_is_open and now_dt.time() < A_SHARE_MARKET_CLOSE_TIME:
        phase = "intraday"
        expected = previous_open
        expected_source = "previous_completed_trading_day"
    elif today_is_open and now_dt.time() < A_SHARE_DATA_READY_TIME:
        phase = "post_close_pending_eod"
        expected = previous_open
        expected_source = "previous_completed_trading_day"
    elif today_is_open:
        phase = "post_close_data_ready"
        expected = today
        expected_source = "current_trading_day_after_ready_time"
    else:
        phase = "market_closed"
        expected = max((day for day in open_days if day < today), default=previous_open)
        expected_source = "previous_completed_trading_day"
    if expected is None:
        expected_source = "unavailable"
    warnings = []
    coverage_status = _calendar_coverage_status(rows, today, validated=calendar_validated)
    expected_is_open = bool(expected and any(row["cal_date"] == expected and row.get("is_open") for row in rows))
    expected_validated_by_calendar = bool(calendar_validated and expected_is_open)
    if data_update_delay_guard_active:
        data_update_delay_reason = "post_close_before_data_ready_time"
    elif today_is_open and current_time < A_SHARE_MARKET_OPEN_TIME:
        data_update_delay_reason = "pre_open_uses_previous_completed_trading_day"
    elif today_is_open and current_time < A_SHARE_MARKET_CLOSE_TIME:
        data_update_delay_reason = "intraday_uses_previous_completed_trading_day"
    elif today_is_open and current_time >= A_SHARE_DATA_READY_TIME:
        data_update_delay_reason = "after_ready_time_current_trading_day_allowed"
    elif not today_is_open:
        data_update_delay_reason = "non_trading_day_uses_previous_completed_trading_day"
    else:
        data_update_delay_reason = "standard_previous_completed_trading_day_policy"
    if not calendar_validated:
        warnings.append("未接入交易所 trade_cal，本次 freshness 使用工作日 fallback；节假日判断需降级。")
    elif coverage_status != "validated":
        warnings.append("trade_cal 覆盖不完整，已保守输出 freshness 审计字段。")
    if expected is None:
        warnings.append("无法确认最近应可得交易日，已禁止相关数据进入当前 composite score。")
    return {
        "market": "A_SHARE",
        "now": _now_iso(now_dt),
        "today": today.isoformat(),
        "market_phase": phase,
        "today_is_trading_day": today_is_open,
        "expected_data_date": expected.isoformat() if expected else None,
        "expected_data_date_source": expected_source,
        "expected_data_date_available": bool(expected),
        "expected_data_date_calendar_validated": expected_validated_by_calendar,
        "latest_completed_trading_day": expected.isoformat() if expected else None,
        "previous_open_date": previous_open.isoformat() if previous_open else None,
        "next_open_date": next_open.isoformat() if next_open else None,
        "previous_open_found": bool(previous_open),
        "next_open_found": bool(next_open),
        "calendar_source": "trade_cal_packet" if calendar_validated else "fallback_weekday_calendar",
        "calendar_validated": calendar_validated,
        "calendar_coverage_status": coverage_status,
        "calendar_requires_refresh": bool(not calendar_validated or coverage_status not in {"validated", "validated_no_next_open"}),
        "calendar_row_count": len(rows),
        "market_session_detail": session_detail,
        "today_eod_available": today_eod_available,
        "current_eod_available": bool(expected and (not today_is_open or today_eod_available)),
        "data_update_delay_guard_active": data_update_delay_guard_active,
        "data_update_delay_reason": data_update_delay_reason,
        "data_ready_time": A_SHARE_DATA_READY_TIME.strftime("%H:%M"),
        "data_availability_policy": "A 股 EOD 因子仅在交易日 16:30 后把当日数据视为当前证据；盘中和盘后未就绪时使用上一已完成交易日。",
        "warnings": warnings,
        "note": "盘中或盘后未到数据可得时间时，EOD 因子应使用上一已完成交易日。",
    }


def _trading_day_lag(data_date: _dt.date, expected_date: _dt.date, trade_calendar_packet: Any = None) -> int | None:
    if data_date > expected_date:
        return None
    rows = _clean_trade_calendar_rows(trade_calendar_packet)
    if not rows:
        rows = _fallback_weekday_calendar(expected_date, lookback_days=max((expected_date - data_date).days + 10, 120), lookahead_days=0)
    open_days = sorted(row["cal_date"] for row in rows if row.get("is_open"))
    if not open_days:
        return None
    return len([day for day in open_days if data_date < day <= expected_date])


def _freshness_row_fields(
    data_date: Any,
    *,
    now: Any = None,
    max_age_days: int = FRESHNESS_MAX_AGE_DAYS,
    calendar_context: Mapping[str, Any] | None = None,
    trade_calendar_packet: Any = None,
) -> dict[str, Any]:
    parsed = _parse_date(data_date)
    context = dict(calendar_context or _expected_data_date(now, trade_calendar_packet))
    expected = _parse_date(context.get("expected_data_date"))
    base = {
        "expected_data_date": context.get("expected_data_date"),
        "expected_data_date_source": context.get("expected_data_date_source"),
        "expected_data_date_available": bool(context.get("expected_data_date_available")),
        "expected_data_date_calendar_validated": bool(context.get("expected_data_date_calendar_validated")),
        "latest_completed_trading_day": context.get("latest_completed_trading_day"),
        "next_open_date": context.get("next_open_date"),
        "previous_open_found": bool(context.get("previous_open_found")),
        "next_open_found": bool(context.get("next_open_found")),
        "market_phase": context.get("market_phase"),
        "calendar_source": context.get("calendar_source"),
        "calendar_validated": bool(context.get("calendar_validated")),
        "calendar_coverage_status": context.get("calendar_coverage_status"),
        "calendar_requires_refresh": bool(context.get("calendar_requires_refresh")),
        "market_session_detail": context.get("market_session_detail"),
        "current_eod_available": bool(context.get("current_eod_available")),
        "data_update_delay_guard_active": bool(context.get("data_update_delay_guard_active")),
        "data_update_delay_reason": context.get("data_update_delay_reason"),
        "trading_day_lag": None,
    }
    if expected is None:
        return {
            **base,
            "data_age_days": None if parsed is None else max(0, (_now_date(now) - parsed).days),
            "freshness_state": "unknown",
            "freshness_reason": "expected_data_date_unavailable",
            "freshness_max_age_days": max_age_days,
            "freshness_usable_for_score": False,
            "freshness_blocks_composite_score": True,
        }
    if parsed is None:
        return {
            **base,
            "data_age_days": None,
            "freshness_state": "unknown",
            "freshness_reason": "missing_or_unparseable_data_date",
            "freshness_max_age_days": max_age_days,
            "freshness_usable_for_score": False,
            "freshness_blocks_composite_score": True,
        }
    age_days = max(0, (_now_date(now) - parsed).days)
    trading_lag = _trading_day_lag(parsed, expected, trade_calendar_packet) if expected else None
    if expected and parsed > expected:
        state = "future_unavailable"
        usable = False
        reason = "data_date_after_expected_trading_day"
    elif trading_lag == 0:
        state = "fresh"
        usable = True
        reason = "matches_expected_trading_day"
    elif trading_lag is not None and trading_lag <= FRESHNESS_STALE_TRADING_DAY_LAG:
        state = "stale"
        usable = False
        reason = f"lags_expected_by_{trading_lag}_trading_days"
    elif trading_lag is not None:
        state = "expired"
        usable = False
        reason = "lags_expected_beyond_stale_trading_day_threshold"
    elif age_days <= max_age_days:
        state = "fresh"
        usable = True
        reason = "calendar_lag_unavailable_age_within_threshold"
    elif age_days <= FRESHNESS_STALE_MAX_AGE_DAYS:
        state = "stale"
        usable = False
        reason = "calendar_lag_unavailable_age_stale"
    else:
        state = "expired"
        usable = False
        reason = "calendar_lag_unavailable_age_expired"
    return {
        **base,
        "data_age_days": age_days,
        "freshness_state": state,
        "freshness_reason": reason,
        "freshness_max_age_days": max_age_days,
        "freshness_usable_for_score": usable,
        "freshness_blocks_composite_score": not usable,
        "trading_day_lag": trading_lag,
    }


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


def _clean_daily_rows(daily_close_packet: Any = None) -> list[dict]:
    packet = _as_mapping(daily_close_packet)
    rows = []
    for raw in _as_list(packet.get("rows") or packet.get("historical_series") or packet.get("data")):
        item = _as_mapping(raw)
        close = _to_number(item.get("close") or item.get("value") or item.get("price"))
        if close is None or close <= 0:
            continue
        rows.append(
            {
                "trade_date": _date_text(item.get("trade_date") or item.get("date") or item.get("asof")),
                "open": _to_number(item.get("open")),
                "high": _to_number(item.get("high")),
                "low": _to_number(item.get("low")),
                "close": close,
                "vol": _to_number(item.get("vol") or item.get("volume")),
                "amount": _to_number(item.get("amount")),
            }
        )
    rows.sort(key=lambda item: item.get("trade_date") or "")
    return rows


def _clean_daily_basic_rows(daily_basic_packet: Any = None) -> list[dict]:
    packet = _as_mapping(daily_basic_packet)
    rows = []
    for raw in _as_list(packet.get("rows") or packet.get("data")):
        item = _as_mapping(raw)
        if not item:
            continue
        row = dict(item)
        row["trade_date"] = _date_text(item.get("trade_date") or item.get("date"))
        rows.append(row)
    rows.sort(key=lambda item: item.get("trade_date") or "")
    return rows


def _factor_missing(factor: Mapping[str, Any], *, reason: str, now: str, status: str = "missing") -> dict:
    return {
        "factor_key": factor.get("factor_key"),
        "factor_name": factor.get("factor_name"),
        "category": factor.get("category"),
        "raw_value": None,
        "zscore": None,
        "rank_pct": None,
        "direction": "missing",
        "coverage": 0.0,
        "data_status": status,
        "status_note": reason,
        "calculated_at": now,
        "pit_validated": False,
        "effect": "missing",
        "score_impact": 0.0,
        "excluded_from_score": factor.get("factor_key") in SCORE_EXCLUDED_FACTOR_KEYS,
        "enters_composite_score": False,
    }


def _factor_value(
    factor: Mapping[str, Any],
    *,
    raw_value: Any,
    direction: str,
    effect: str,
    score_impact: float,
    now: str,
    coverage: float = 1.0,
    data_status: str = "ready",
    status_note: str = "",
    pit_validated: bool = True,
) -> dict:
    excluded = factor.get("factor_key") in SCORE_EXCLUDED_FACTOR_KEYS
    if not pit_validated and effect == "support":
        effect = "neutral"
        score_impact = 0.0
        status_note = (status_note + "；" if status_note else "") + "PIT 未验证，不能成为强 support。"
    return {
        "factor_key": factor.get("factor_key"),
        "factor_name": factor.get("factor_name"),
        "category": factor.get("category"),
        "raw_value": _safe_round(raw_value),
        "zscore": None,
        "rank_pct": None,
        "direction": direction,
        "coverage": round(max(0.0, min(1.0, float(coverage or 0))), 4),
        "data_status": data_status,
        "status_note": status_note or "light mode 已计算；样本不足时不生成横截面 zscore/rank。",
        "calculated_at": now,
        "pit_validated": bool(pit_validated),
        "effect": "neutral" if excluded else effect,
        "score_impact": 0.0 if excluded else round(float(score_impact or 0.0), 4),
        "excluded_from_score": excluded,
        "enters_composite_score": bool(not excluded and data_status in {"ready", "degraded"} and effect in {"support", "suppress", "neutral"}),
    }


def _pct_change(rows: list[dict], periods: int) -> float | None:
    if len(rows) <= periods:
        return None
    latest = _to_number(rows[-1].get("close"))
    base = _to_number(rows[-periods - 1].get("close"))
    if latest is None or base in (None, 0):
        return None
    return latest / base - 1


def _daily_returns(rows: list[dict]) -> list[float]:
    returns = []
    for idx in range(1, len(rows)):
        prev = _to_number(rows[idx - 1].get("close"))
        curr = _to_number(rows[idx].get("close"))
        if prev not in (None, 0) and curr is not None:
            returns.append(curr / prev - 1)
    return returns


def _effect_from_signed_value(value: float, *, positive_threshold: float, negative_threshold: float | None = None) -> tuple[str, str, float]:
    negative_threshold = -positive_threshold if negative_threshold is None else negative_threshold
    if value >= positive_threshold:
        return "positive", "support", 1.0
    if value <= negative_threshold:
        return "negative", "suppress", -1.0
    return "flat", "neutral", 0.0


def _latest_daily_basic_value(rows: list[dict], key: str) -> float | None:
    if not rows:
        return None
    return _to_number(rows[-1].get(key))


def _packet_number(packet: Any, *keys: str) -> float | None:
    mapping = _as_mapping(packet)
    candidates = [mapping]
    for key in ("data", "summary", "latest", "metrics"):
        nested = _as_mapping(mapping.get(key))
        if nested:
            candidates.append(nested)
    for candidate in candidates:
        for key in keys:
            number = _to_number(candidate.get(key))
            if number is not None:
                return number
    return None


def _call_ledger_rows(
    call_ledger: Any = None,
    *,
    now: Any = None,
    calendar_context: Mapping[str, Any] | None = None,
    trade_calendar_packet: Any = None,
) -> list[dict]:
    if isinstance(call_ledger, Mapping):
        rows = call_ledger.get("items") or call_ledger.get("call_ledger") or []
    else:
        rows = call_ledger
    cleaned = []
    for raw in _as_list(rows):
        item = _as_mapping(raw)
        if not item:
            continue
        data_date = _date_text(item.get("data_date") or item.get("trade_date"))
        cleaned.append(
            {
                "api": item.get("api") or item.get("source_interface") or item.get("fact_key"),
                "source_interfaces": list(item.get("source_interfaces") or ([] if not item.get("source_interface") else [item.get("source_interface")])),
                "ts_code": item.get("ts_code") or item.get("target_ts_code"),
                "row_count": int(_to_number(item.get("row_count"), 0) or 0),
                "data_date": data_date,
                "local_fetched_at": item.get("local_fetched_at") or item.get("updated_at"),
                "call_status": item.get("call_status") or item.get("status") or "not_called",
                "error_message_safe": item.get("error_message_safe") or item.get("error") or "",
                **_freshness_row_fields(data_date, now=now, calendar_context=calendar_context, trade_calendar_packet=trade_calendar_packet),
            }
        )
    return cleaned


def _build_data_freshness_gate(
    call_rows: list[dict],
    *,
    now: Any = None,
    calendar_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context = dict(calendar_context or _expected_data_date(now))
    context_warnings = list(context.get("warnings") or [])
    dated_rows = [row for row in call_rows if _parse_date(row.get("data_date")) is not None]
    if not dated_rows:
        return {
            "status": "unknown",
            "gate_applied": False,
            "usable_for_score": True,
            "latest_data_date": None,
            "expected_data_date": context.get("expected_data_date"),
            "expected_data_date_source": context.get("expected_data_date_source"),
            "expected_data_date_available": bool(context.get("expected_data_date_available")),
            "expected_data_date_calendar_validated": bool(context.get("expected_data_date_calendar_validated")),
            "latest_completed_trading_day": context.get("latest_completed_trading_day"),
            "next_open_date": context.get("next_open_date"),
            "previous_open_found": bool(context.get("previous_open_found")),
            "next_open_found": bool(context.get("next_open_found")),
            "market_phase": context.get("market_phase"),
            "market_session_detail": context.get("market_session_detail"),
            "calendar_source": context.get("calendar_source"),
            "calendar_validated": bool(context.get("calendar_validated")),
            "calendar_coverage_status": context.get("calendar_coverage_status"),
            "calendar_requires_refresh": bool(context.get("calendar_requires_refresh")),
            "current_eod_available": bool(context.get("current_eod_available")),
            "data_update_delay_guard_active": bool(context.get("data_update_delay_guard_active")),
            "data_update_delay_reason": context.get("data_update_delay_reason"),
            "data_ready_time": context.get("data_ready_time"),
            "max_data_age_days": None,
            "max_trading_day_lag": None,
            "fresh_count": 0,
            "stale_count": 0,
            "expired_count": 0,
            "future_unavailable_count": 0,
            "unknown_count": len(call_rows),
            "blocking_reasons": [],
            "warnings": context_warnings,
            "max_age_days": FRESHNESS_MAX_AGE_DAYS,
            "note": "未发现可解析 data_date；保持原有 cache-only 降级，不强行判定过期。",
        }
    latest = max((_parse_date(row.get("data_date")) for row in dated_rows if _parse_date(row.get("data_date")) is not None), default=None)
    ages = [row.get("data_age_days") for row in dated_rows if isinstance(row.get("data_age_days"), int)]
    lags = [row.get("trading_day_lag") for row in dated_rows if isinstance(row.get("trading_day_lag"), int)]
    states = [str(row.get("freshness_state") or "unknown") for row in dated_rows]
    future_count = states.count("future_unavailable")
    expired_count = states.count("expired")
    stale_count = states.count("stale")
    fresh_count = states.count("fresh")
    if future_count:
        status = "future_unavailable"
    elif expired_count:
        status = "expired"
    elif stale_count:
        status = "stale"
    elif fresh_count == len(dated_rows):
        status = "fresh"
    else:
        status = "unknown"
    usable = status == "fresh"
    blocking_reasons = sorted(
        {
            str(row.get("freshness_reason"))
            for row in dated_rows
            if row.get("freshness_usable_for_score") is False and row.get("freshness_reason")
        }
    )
    warnings = list(context_warnings)
    if not context.get("calendar_validated"):
        warnings.append("交易日历未验证：freshness 可用于保守门控，但不代表交易所日历级最终验收。")
    if not usable:
        warnings.append("存在非当前 expected_data_date 的数据，已禁止进入当前 composite score 和 evidence preview。")
    return {
        "status": status,
        "gate_applied": True,
        "usable_for_score": usable,
        "latest_data_date": latest.isoformat() if latest else None,
        "expected_data_date": context.get("expected_data_date"),
        "expected_data_date_source": context.get("expected_data_date_source"),
        "expected_data_date_available": bool(context.get("expected_data_date_available")),
        "expected_data_date_calendar_validated": bool(context.get("expected_data_date_calendar_validated")),
        "latest_completed_trading_day": context.get("latest_completed_trading_day"),
        "next_open_date": context.get("next_open_date"),
        "previous_open_found": bool(context.get("previous_open_found")),
        "next_open_found": bool(context.get("next_open_found")),
        "market_phase": context.get("market_phase"),
        "market_session_detail": context.get("market_session_detail"),
        "calendar_source": context.get("calendar_source"),
        "calendar_validated": bool(context.get("calendar_validated")),
        "calendar_coverage_status": context.get("calendar_coverage_status"),
        "calendar_requires_refresh": bool(context.get("calendar_requires_refresh")),
        "current_eod_available": bool(context.get("current_eod_available")),
        "data_update_delay_guard_active": bool(context.get("data_update_delay_guard_active")),
        "data_update_delay_reason": context.get("data_update_delay_reason"),
        "today_is_trading_day": bool(context.get("today_is_trading_day")),
        "data_ready_time": context.get("data_ready_time"),
        "max_data_age_days": max(ages) if ages else None,
        "max_trading_day_lag": max(lags) if lags else None,
        "fresh_count": fresh_count,
        "stale_count": stale_count,
        "expired_count": expired_count,
        "future_unavailable_count": future_count,
        "unknown_count": len(call_rows) - len(dated_rows),
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "max_age_days": FRESHNESS_MAX_AGE_DAYS,
        "stale_after_trading_day_lag": 0,
        "expired_after_trading_day_lag": FRESHNESS_STALE_TRADING_DAY_LAG,
        "note": "非 expected_data_date 的过期、陈旧或未来不可得数据仅允许审计展示，不得进入 composite score 或强 support。",
    }


def _apply_freshness_gate_to_runtime(runtime: Mapping[str, Any], freshness_gate: Mapping[str, Any]) -> dict[str, Any]:
    gated = dict(runtime)
    if freshness_gate.get("usable_for_score") is not False or not freshness_gate.get("gate_applied"):
        gated["data_freshness_gate"] = dict(freshness_gate)
        return gated
    values = []
    for raw in _as_list(gated.get("factor_values")):
        item = dict(_as_mapping(raw))
        if item.get("enters_composite_score"):
            note = item.get("status_note") or ""
            item["status_note"] = (note + "；" if note else "") + "数据时效门控未通过，保留原值审计但不进入 composite score。"
            item["data_status"] = "stale_data"
            item["freshness_usable_for_score"] = False
            item["effect_before_freshness_gate"] = item.get("effect")
            item["effect"] = "neutral"
            item["score_impact"] = 0.0
            item["enters_composite_score"] = False
        values.append(item)
    gated["factor_values"] = values
    gated["available_count_before_freshness_gate"] = gated.get("available_count")
    gated["available_count"] = sum(1 for item in values if item.get("enters_composite_score"))
    gated["data_freshness_gate"] = dict(freshness_gate)
    gated["status"] = "stale_data" if values else gated.get("status")
    warnings = list(gated.get("warnings") or [])
    warnings.append("数据时效门控未通过：本轮 runtime 只保留审计展示，不进入 composite score。")
    gated["warnings"] = warnings
    return gated


def _calculate_factor_value(
    factor: Mapping[str, Any],
    *,
    rows: list[dict],
    daily_basic_rows: list[dict],
    moneyflow_packet: Any = None,
    hard_risk_packet: Any = None,
    limit_emotion_packet: Any = None,
    chip_packet: Any = None,
    now: str,
) -> dict:
    key = str(factor.get("factor_key") or "")
    if key in SCORE_EXCLUDED_FACTOR_KEYS:
        return _factor_value(
            factor,
            raw_value=None,
            direction="research_context",
            effect="neutral",
            score_impact=0.0,
            now=now,
            data_status="research_context",
            status_note="方法来源/产业链上下文只进入 research_context，不进入 composite score。",
            pit_validated=False,
        )
    if key in {"momentum_5d", "momentum_20d", "momentum_60d"}:
        period = int(key.split("_")[1].replace("d", ""))
        value = _pct_change(rows, period)
        if value is None:
            return _factor_missing(factor, reason=f"真实日线不足 {period + 1} 条。", now=now)
        direction, effect, impact = _effect_from_signed_value(value, positive_threshold=0.03 if period <= 20 else 0.06)
        return _factor_value(factor, raw_value=value, direction=direction, effect=effect, score_impact=impact, now=now)
    if key in {"reversal_1d", "reversal_5d"}:
        period = 1 if key == "reversal_1d" else 5
        change = _pct_change(rows, period)
        if change is None:
            return _factor_missing(factor, reason=f"真实日线不足 {period + 1} 条。", now=now)
        value = -change
        direction, effect, impact = _effect_from_signed_value(value, positive_threshold=0.025 if period == 1 else 0.05)
        return _factor_value(factor, raw_value=value, direction=direction, effect=effect, score_impact=impact, now=now)
    if key == "breakout_20d":
        if len(rows) < 20:
            return _factor_missing(factor, reason="真实日线不足 20 条。", now=now)
        latest = _to_number(rows[-1].get("close"))
        highs = [_to_number(item.get("high")) for item in rows[-20:]]
        highs = [value for value in highs if value is not None and value > 0]
        if latest is None or not highs:
            return _factor_missing(factor, reason="缺少 high/close 字段。", now=now)
        value = latest / max(highs) - 1
        direction, effect, impact = _effect_from_signed_value(value, positive_threshold=-0.005, negative_threshold=-0.08)
        return _factor_value(factor, raw_value=value, direction=direction, effect=effect, score_impact=impact, now=now)
    if key == "bias_ma20":
        if len(rows) < 20:
            return _factor_missing(factor, reason="真实日线不足 20 条。", now=now)
        closes = [_to_number(item.get("close")) for item in rows[-20:]]
        closes = [value for value in closes if value is not None and value > 0]
        latest = _to_number(rows[-1].get("close"))
        if latest is None or len(closes) < 20:
            return _factor_missing(factor, reason="缺少 close 字段。", now=now)
        value = latest / statistics.fmean(closes) - 1
        direction, effect, impact = _effect_from_signed_value(value, positive_threshold=0.03, negative_threshold=-0.08)
        return _factor_value(factor, raw_value=value, direction=direction, effect=effect, score_impact=impact, now=now)
    if key == "volatility_20d":
        returns = _daily_returns(rows)[-20:]
        if len(returns) < 10:
            return _factor_missing(factor, reason="收益率样本不足。", now=now)
        value = statistics.pstdev(returns)
        if value >= 0.055:
            return _factor_value(factor, raw_value=value, direction="high_risk", effect="suppress", score_impact=-1.0, now=now)
        return _factor_value(factor, raw_value=value, direction="normal", effect="neutral", score_impact=0.0, now=now)
    if key == "atr_pct_14d":
        if len(rows) < 15:
            return _factor_missing(factor, reason="真实日线不足 15 条。", now=now)
        true_ranges = []
        for idx in range(1, len(rows)):
            high = _to_number(rows[idx].get("high"))
            low = _to_number(rows[idx].get("low"))
            prev_close = _to_number(rows[idx - 1].get("close"))
            if high is None or low is None or prev_close is None:
                continue
            true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        latest = _to_number(rows[-1].get("close"))
        if latest in (None, 0) or len(true_ranges) < 14:
            return _factor_missing(factor, reason="缺 high/low/close，无法计算 ATR。", now=now)
        value = statistics.fmean(true_ranges[-14:]) / latest
        effect = "suppress" if value >= 0.08 else "neutral"
        return _factor_value(factor, raw_value=value, direction="high_risk" if effect == "suppress" else "normal", effect=effect, score_impact=-0.8 if effect == "suppress" else 0.0, now=now)
    if key == "max_drawdown_60d":
        closes = [_to_number(item.get("close")) for item in rows[-60:]]
        closes = [value for value in closes if value is not None and value > 0]
        if len(closes) < 20:
            return _factor_missing(factor, reason="真实日线不足 20 条。", now=now)
        peak = closes[0]
        drawdowns = []
        for close in closes:
            peak = max(peak, close)
            drawdowns.append(close / peak - 1)
        value = min(drawdowns)
        effect = "suppress" if value <= -0.22 else "neutral"
        return _factor_value(factor, raw_value=value, direction="drawdown_risk" if effect == "suppress" else "normal", effect=effect, score_impact=-1.0 if effect == "suppress" else 0.0, now=now)
    if key == "amount_20d_rank":
        amounts = [_to_number(item.get("amount")) for item in rows[-20:]]
        amounts = [value for value in amounts if value is not None and value > 0]
        if len(amounts) < 10:
            return _factor_missing(factor, reason="成交额样本不足。", now=now)
        return _factor_value(factor, raw_value=statistics.fmean(amounts), direction="liquidity_context", effect="neutral", score_impact=0.0, now=now, data_status="degraded", status_note="light mode 无横截面 universe，成交额分位降级为 20 日均额。")
    if key == "volume_ratio_20d":
        vols = [_to_number(item.get("vol")) for item in rows[-21:]]
        vols = [value for value in vols if value is not None and value > 0]
        if len(vols) < 11:
            return _factor_missing(factor, reason="成交量样本不足。", now=now)
        latest = vols[-1]
        base = statistics.fmean(vols[:-1]) if len(vols) > 1 else None
        if not base:
            return _factor_missing(factor, reason="成交量均值不可用。", now=now)
        value = latest / base
        effect = "support" if value >= 1.5 else ("suppress" if value <= 0.55 else "neutral")
        return _factor_value(factor, raw_value=value, direction="volume_expansion" if effect == "support" else ("volume_shrink" if effect == "suppress" else "normal"), effect=effect, score_impact=0.7 if effect == "support" else (-0.5 if effect == "suppress" else 0), now=now)
    if key == "turnover_rate":
        value = _latest_daily_basic_value(daily_basic_rows, "turnover_rate")
        if value is None:
            return _factor_missing(factor, reason="daily_basic.turnover_rate 缺失。", now=now)
        return _factor_value(factor, raw_value=value, direction="liquidity_context", effect="neutral", score_impact=0.0, now=now, data_status="degraded", status_note="light mode 只展示换手率原值，不生成交易分。")
    if key in {"pe_ttm_rank", "pb_rank", "ps_ttm_rank"}:
        field = {"pe_ttm_rank": "pe_ttm", "pb_rank": "pb", "ps_ttm_rank": "ps_ttm"}[key]
        value = _latest_daily_basic_value(daily_basic_rows, field)
        if value is None:
            return _factor_missing(factor, reason=f"daily_basic.{field} 缺失。", now=now)
        return _factor_value(factor, raw_value=value, direction="valuation_context", effect="neutral", score_impact=0.0, now=now, data_status="degraded", status_note="light mode 无行业横截面，估值分位降级为原值展示。")
    if key in {"main_net_5d", "retail_net_5d"}:
        field_candidates = ("main_net_yi", "net_mf_amount", "buy_lg_amount", "buy_elg_amount") if key == "main_net_5d" else ("small_net_yi", "buy_sm_amount", "sell_sm_amount")
        value = _packet_number(moneyflow_packet, *field_candidates)
        if value is None:
            return _factor_missing(factor, reason="资金流 packet 缺失或字段不可用。", now=now)
        direction, effect, impact = _effect_from_signed_value(value, positive_threshold=0.0)
        return _factor_value(factor, raw_value=value, direction=direction, effect=effect, score_impact=0.8 * impact, now=now)
    if key in {"roe_latest", "gross_margin_latest", "revenue_growth_yoy", "profit_growth_yoy"}:
        return _factor_missing(factor, reason="财务类因子尚未完成公告日期 / 实际可得日期 PIT 校验。", now=now, status="pending_pit")
    if key == "hard_risk_flag":
        packet = _as_mapping(hard_risk_packet)
        flags = _as_list(packet.get("risk_flags") or packet.get("warnings") or packet.get("alerts"))
        if not packet:
            return _factor_missing(factor, reason="硬风险 packet 未加载；缺失不等于无风险。", now=now)
        value = len(flags)
        if value > 0:
            return _factor_value(factor, raw_value=value, direction="risk_present", effect="suppress", score_impact=-1.0, now=now)
        return _factor_value(factor, raw_value=0, direction="no_verified_risk_record", effect="neutral", score_impact=0.0, now=now, status_note="当前无可见硬风险记录；不把无记录当正面。")
    if key == "limit_heat_score":
        value = _packet_number(limit_emotion_packet, "limit_heat_score", "heat_score", "record_count", "target_match_count")
        if value is None:
            return _factor_missing(factor, reason="涨跌停/情绪 packet 缺失。", now=now)
        effect = "support" if value > 0 else "neutral"
        return _factor_value(factor, raw_value=value, direction="emotion_heat" if effect == "support" else "neutral", effect=effect, score_impact=0.6 if effect == "support" else 0, now=now)
    if key == "chip_winner_rate":
        value = _packet_number(chip_packet, "winner_rate", "chip_winner_rate", "profit_ratio")
        if value is None:
            return _factor_missing(factor, reason="筹码/胜率 packet 缺失。", now=now)
        effect = "suppress" if value >= 85 else ("support" if value <= 35 else "neutral")
        return _factor_value(factor, raw_value=value, direction="crowded_profit" if effect == "suppress" else ("low_winner_rate" if effect == "support" else "neutral"), effect=effect, score_impact=-0.6 if effect == "suppress" else (0.4 if effect == "support" else 0), now=now)
    return _factor_missing(factor, reason="MVP light mode 暂不计算该因子。", now=now, status="pending")


def build_factor_runtime_packet(
    *,
    factor_library: Any = None,
    daily_close_packet: Any = None,
    daily_basic_packet: Any = None,
    trade_calendar_packet: Any = None,
    moneyflow_packet: Any = None,
    hard_risk_packet: Any = None,
    limit_emotion_packet: Any = None,
    chip_packet: Any = None,
    mode: str = "light",
    universe: Any = None,
    now: Any = None,
) -> dict:
    now_text = _now_iso(now)
    library = factor_library if isinstance(factor_library, Mapping) else build_factor_library_packet(now=now_text)
    factors = [_as_mapping(item) for item in _as_list(library.get("factors")) if _as_mapping(item)]
    rows = _clean_daily_rows(daily_close_packet)
    daily_basic_rows = _clean_daily_basic_rows(daily_basic_packet)
    factor_values = [
        _calculate_factor_value(
            factor,
            rows=rows,
            daily_basic_rows=daily_basic_rows,
            moneyflow_packet=moneyflow_packet,
            hard_risk_packet=hard_risk_packet,
            limit_emotion_packet=limit_emotion_packet,
            chip_packet=chip_packet,
            now=now_text,
        )
        for factor in factors
    ]
    missing_count = sum(1 for item in factor_values if item.get("effect") == "missing")
    usable_count = sum(1 for item in factor_values if item.get("data_status") in {"ready", "degraded", "research_context"})
    coverage = usable_count / len(factor_values) if factor_values else 0.0
    status = "ready" if factor_values and missing_count == 0 else ("partial" if factor_values and usable_count else "not_run")
    universe_map = _as_mapping(universe)
    return {
        "packet_key": RUNTIME_PACKET_KEY,
        "schema_version": "factor_runtime.v1",
        "phase": MVP_PHASE,
        "mode": mode if mode in {"cache_only", "light", "full", "research"} else "light",
        "universe": {
            "type": universe_map.get("type") or "current_target",
            "items": list(universe_map.get("items") or []),
            "size": int(_to_number(universe_map.get("size"), len(universe_map.get("items") or [])) or 0),
        },
        "status": status,
        "factor_values": factor_values,
        "available_count": usable_count,
        "coverage": round(coverage, 4),
        "missing_count": missing_count,
        "calculated_at": now_text,
        "warnings": ["light mode 无全市场横截面，zscore/rank_pct 缺省时必须按降级解释。"],
        "deepseek_called": False,
        "tushare_called": False,
        "external_calls_triggered": False,
    }


def _classify_factor_test_row(row: Mapping[str, Any]) -> str:
    pit_check = str(row.get("pit_check") or "pending")
    lookahead_check = str(row.get("lookahead_check") or "pending")
    if pit_check == "failed" or lookahead_check == "failed":
        return "invalid"
    coverage = _to_number(row.get("coverage"))
    missing_rate = _to_number(row.get("missing_rate"))
    ic_mean = _to_number(row.get("ic_mean"))
    icir = _to_number(row.get("icir"))
    rank_ic = _to_number(row.get("rank_ic_mean"))
    top_bottom = _to_number(row.get("top_bottom_group_return"))
    cost_adjusted = _to_number(row.get("cost_adjusted_return"))
    monotonic = row.get("group_return_monotonicity")
    if any(value is None for value in (coverage, missing_rate, ic_mean, icir, rank_ic, top_bottom, cost_adjusted)):
        return "not_enough_data"
    if coverage < 0.6:
        return "not_enough_data"
    if missing_rate > 0.25 or icir < 0 or monotonic is False:
        return "disabled"
    same_direction_rank_ic = (ic_mean >= 0 and rank_ic >= 0) or (ic_mean <= 0 and rank_ic <= 0)
    pit_and_lookahead_passed = pit_check == "passed" and lookahead_check == "passed"
    if (
        pit_and_lookahead_passed
        and coverage >= 0.8
        and missing_rate <= 0.15
        and abs(ic_mean) >= 0.02
        and icir >= 0.3
        and same_direction_rank_ic
        and top_bottom > 0
        and cost_adjusted > 0
        and monotonic is True
    ):
        return "research_pass"
    return "watchlist"


def _rank(values: list[float]) -> list[float]:
    sorted_values = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(sorted_values):
        end = cursor + 1
        while end < len(sorted_values) and sorted_values[end][0] == sorted_values[cursor][0]:
            end += 1
        avg_rank = (cursor + 1 + end) / 2.0
        for _, index in sorted_values[cursor:end]:
            ranks[index] = avg_rank
        cursor = end
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    x_diffs = [value - x_mean for value in xs]
    y_diffs = [value - y_mean for value in ys]
    x_var = sum(value * value for value in x_diffs)
    y_var = sum(value * value for value in y_diffs)
    if x_var <= 0 or y_var <= 0:
        return None
    return sum(x * y for x, y in zip(x_diffs, y_diffs)) / math.sqrt(x_var * y_var)


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    return _pearson(_rank(xs), _rank(ys))


def _max_drawdown_from_returns(returns: list[float]) -> float | None:
    if not returns:
        return None
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, equity / peak - 1)
    return max_drawdown


def _group_return_summary(xs: list[float], ys: list[float]) -> tuple[float | None, bool | None]:
    if len(xs) != len(ys) or len(xs) < 5:
        return None, None
    ordered = [item for item in sorted(zip(xs, ys), key=lambda pair: pair[0]) if item[1] is not None]
    if len(ordered) < 5:
        return None, None
    bucket_size = max(1, len(ordered) // 3)
    bottom = [value for _, value in ordered[:bucket_size]]
    middle_start = max(bucket_size, (len(ordered) - bucket_size) // 2)
    middle = [value for _, value in ordered[middle_start : middle_start + bucket_size]]
    top = [value for _, value in ordered[-bucket_size:]]
    if not bottom or not middle or not top:
        return None, None
    bottom_mean = statistics.fmean(bottom)
    middle_mean = statistics.fmean(middle)
    top_mean = statistics.fmean(top)
    return top_mean - bottom_mean, bottom_mean <= middle_mean <= top_mean


def _demean_by_group(values: list[float], groups: list[str]) -> list[float] | None:
    if len(values) != len(groups) or len(values) < 3 or not all(groups):
        return None
    grouped: dict[str, list[float]] = {}
    for value, group in zip(values, groups):
        grouped.setdefault(str(group), []).append(value)
    if len(grouped) < 2:
        return None
    means = {group: statistics.fmean(items) for group, items in grouped.items() if items}
    return [value - means[str(group)] for value, group in zip(values, groups)]


def _linear_residuals(values: list[float], controls: list[float]) -> list[float] | None:
    if len(values) != len(controls) or len(values) < 3:
        return None
    x_mean = statistics.fmean(controls)
    y_mean = statistics.fmean(values)
    x_diffs = [value - x_mean for value in controls]
    denominator = sum(value * value for value in x_diffs)
    if denominator <= 0:
        return None
    slope = sum(x * (y - y_mean) for x, y in zip(x_diffs, values)) / denominator
    intercept = y_mean - slope * x_mean
    return [value - (intercept + slope * control) for value, control in zip(values, controls)]


def _neutral_ic_from_observations(
    valid_pairs: list[tuple[str, float, float, dict[str, Any]]],
    *,
    neutralizer: str,
) -> float | None:
    xs = [item[1] for item in valid_pairs]
    ys = [item[2] for item in valid_pairs]
    if neutralizer == "industry":
        groups = [
            str(row.get("industry") or row.get("industry_name") or row.get("sector") or "")
            for _, _, _, row in valid_pairs
        ]
        x_resid = _demean_by_group(xs, groups)
        y_resid = _demean_by_group(ys, groups)
    elif neutralizer == "market_cap":
        caps = [
            _to_number(row.get("market_cap", row.get("total_mv", row.get("float_mv"))))
            for _, _, _, row in valid_pairs
        ]
        if any(value is None or value <= 0 for value in caps):
            return None
        controls = [math.log(float(value)) for value in caps if value is not None]
        x_resid = _linear_residuals(xs, controls)
        y_resid = _linear_residuals(ys, controls)
    else:
        return None
    if x_resid is None or y_resid is None:
        return None
    return _pearson(x_resid, y_resid)


def _stability_from_date_splits(by_date: Mapping[str, list[tuple[float, float]]]) -> tuple[str, str]:
    dates = sorted(key for key, pairs in by_date.items() if len(pairs) >= 3)
    if len(dates) < 4:
        return "not_enough_data", "not_enough_data"
    midpoint = len(dates) // 2

    def _date_ic(date_keys: list[str]) -> float | None:
        values = []
        for key in date_keys:
            pairs = by_date.get(key) or []
            ic = _pearson([item[0] for item in pairs], [item[1] for item in pairs])
            if ic is not None:
                values.append(ic)
        return statistics.fmean(values) if values else None

    early = _date_ic(dates[:midpoint])
    recent = _date_ic(dates[midpoint:])
    if early is None or recent is None:
        return "not_enough_data", "not_enough_data"
    stable = early == 0 or (early > 0 and recent > 0) or (early < 0 and recent < 0)
    if not stable:
        stability = "unstable_direction"
    elif abs(recent) >= abs(early) * 0.5:
        stability = "stable"
    else:
        stability = "weak_recent_window"
    decay = "decaying" if abs(recent) < abs(early) * 0.5 else "not_detected"
    return stability, decay


def _factor_test_rows_from_observations(observations: Any, *, now: str) -> list[dict]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in _as_list(observations):
        row = _as_mapping(item)
        factor_key = str(row.get("factor_key") or "")
        if not factor_key:
            continue
        grouped.setdefault(factor_key, []).append(row)

    metric_rows: list[dict] = []
    for factor_key, rows in sorted(grouped.items()):
        valid_pairs: list[tuple[str, float, float, dict[str, Any]]] = []
        for row in rows:
            factor_value = _to_number(row.get("factor_value", row.get("raw_value")))
            forward_return = _to_number(row.get("forward_return", row.get("future_return")))
            trade_date = str(row.get("trade_date") or row.get("data_date") or "")
            if factor_value is None or forward_return is None:
                continue
            valid_pairs.append((trade_date, factor_value, forward_return, row))
        total = len(rows)
        valid_count = len(valid_pairs)
        xs = [item[1] for item in valid_pairs]
        ys = [item[2] for item in valid_pairs]
        coverage = valid_count / total if total else 0.0
        missing_rate = 1 - coverage if total else 1.0
        per_date_ic = []
        per_date_rank_ic = []
        by_date: dict[str, list[tuple[float, float]]] = {}
        for trade_date, factor_value, forward_return, _ in valid_pairs:
            by_date.setdefault(trade_date, []).append((factor_value, forward_return))
        for pairs in by_date.values():
            date_xs = [item[0] for item in pairs]
            date_ys = [item[1] for item in pairs]
            ic = _pearson(date_xs, date_ys)
            rank_ic = _spearman(date_xs, date_ys)
            if ic is not None:
                per_date_ic.append(ic)
            if rank_ic is not None:
                per_date_rank_ic.append(rank_ic)
        if per_date_ic:
            ic_mean = statistics.fmean(per_date_ic)
            ic_std = statistics.pstdev(per_date_ic) if len(per_date_ic) > 1 else 0.0
        else:
            ic_mean = _pearson(xs, ys)
            ic_std = None
        rank_ic_mean = statistics.fmean(per_date_rank_ic) if per_date_rank_ic else _spearman(xs, ys)
        if ic_mean is not None and ic_std not in (None, 0):
            icir = ic_mean / ic_std
        elif ic_mean is not None and ic_std == 0 and len(per_date_ic) >= 2:
            icir = 9.99 if ic_mean > 0 else (-9.99 if ic_mean < 0 else 0.0)
        else:
            icir = None
        top_bottom, monotonicity = _group_return_summary(xs, ys)
        costs = [_to_number(row.get("transaction_cost", row.get("cost"))) for _, _, _, row in valid_pairs]
        avg_cost = statistics.fmean([value for value in costs if value is not None]) if any(value is not None for value in costs) else None
        turnover_values = [_to_number(row.get("turnover")) for _, _, _, row in valid_pairs]
        turnover = statistics.fmean([value for value in turnover_values if value is not None]) if any(value is not None for value in turnover_values) else None
        pit_passed = all(row.get("pit_validated") is True or row.get("pit_check") == "passed" for _, _, _, row in valid_pairs) if valid_pairs else False
        lookahead_passed = all(row.get("lookahead_check") == "passed" for _, _, _, row in valid_pairs) if valid_pairs else False
        industry_neutral_ic = _neutral_ic_from_observations(valid_pairs, neutralizer="industry")
        market_cap_neutral_ic = _neutral_ic_from_observations(valid_pairs, neutralizer="market_cap")
        stability, recent_decay = _stability_from_date_splits(by_date)
        row = {
            "factor_key": factor_key,
            "mode": "light",
            "sample_scope": "current_holding_watchlist",
            "data_status": "computed_from_light_observations" if valid_count >= 3 else "not_enough_data",
            "coverage": round(coverage, 4),
            "missing_rate": round(missing_rate, 4),
            "ic_mean": round(ic_mean, 6) if ic_mean is not None else None,
            "ic_std": round(ic_std, 6) if ic_std is not None else None,
            "icir": round(icir, 6) if icir is not None else None,
            "rank_ic_mean": round(rank_ic_mean, 6) if rank_ic_mean is not None else None,
            "top_bottom_group_return": round(top_bottom, 6) if top_bottom is not None else None,
            "group_return_monotonicity": monotonicity,
            "turnover": round(turnover, 6) if turnover is not None else None,
            "cost_adjusted_return": round(top_bottom - (avg_cost or 0), 6) if top_bottom is not None else None,
            "max_drawdown": round(_max_drawdown_from_returns(ys), 6) if ys else None,
            "industry_neutral_ic": round(industry_neutral_ic, 6) if industry_neutral_ic is not None else None,
            "market_cap_neutral_ic": round(market_cap_neutral_ic, 6) if market_cap_neutral_ic is not None else None,
            "neutralization_scope": {
                "industry": "computed_light_observation_residual_ic" if industry_neutral_ic is not None else "not_enough_data",
                "market_cap": "computed_light_observation_residual_ic" if market_cap_neutral_ic is not None else "not_enough_data",
            },
            "out_of_sample_stability": stability,
            "recent_decay": recent_decay,
            "pit_check": "passed" if pit_passed else "pending",
            "lookahead_check": "passed" if lookahead_passed else "pending",
            "survivorship_check": "pending",
            "test_window": {
                "trade_date_count": len(by_date),
                "observation_count": total,
                "valid_pair_count": valid_count,
            },
            "forward_return_horizon": rows[0].get("forward_return_horizon") or "unspecified",
            "calculated_at": now,
        }
        row["result_status"] = _classify_factor_test_row(row)
        metric_rows.append(row)
    return metric_rows


def _factor_test_scaffold_row(factor: Mapping[str, Any], *, mode: str, now: str) -> dict:
    return {
        "factor_key": factor.get("factor_key"),
        "factor_name": factor.get("factor_name"),
        "category": factor.get("category"),
        "mode": mode,
        "sample_scope": "current_holding_watchlist" if mode == "light" else mode,
        "result_status": "not_enough_data",
        "data_status": "metric_scaffold_only",
        "coverage": None,
        "missing_rate": None,
        "ic_mean": None,
        "ic_std": None,
        "icir": None,
        "rank_ic_mean": None,
        "top_bottom_group_return": None,
        "group_return_monotonicity": None,
        "turnover": None,
        "cost_adjusted_return": None,
        "max_drawdown": None,
        "industry_neutral_ic": None,
        "market_cap_neutral_ic": None,
        "out_of_sample_stability": "not_run",
        "recent_decay": "not_run",
        "pit_check": "pending" if not factor.get("pit_validated") else "declared",
        "lookahead_check": "pending",
        "survivorship_check": "pending",
        "test_window": None,
        "forward_return_horizon": None,
        "calculated_at": now,
        "enters_strategy_action": False,
        "enters_core_action": False,
        "enters_next_session_projection": False,
        "enters_evidence_effects": False,
        "does_not_modify_strategy_action": True,
        "warning": "指标结构已声明；尚未计算 IC/Rank IC/分组收益/换手/成本后收益。",
    }


def _merge_factor_test_items(scaffold_rows: list[dict], supplied_items: Any, now: str) -> list[dict]:
    overrides = {
        str(item.get("factor_key")): dict(item)
        for item in _as_list(supplied_items)
        if isinstance(item, Mapping) and item.get("factor_key")
    }
    rows: list[dict] = []
    for row in scaffold_rows:
        merged = dict(row)
        override = overrides.get(str(row.get("factor_key")))
        if override:
            for key, value in override.items():
                if key in {"strategy_action", "core_action", "operation_zones", "price", "holding"}:
                    continue
                merged[key] = value
            merged["calculated_at"] = merged.get("calculated_at") or now
            merged["result_status"] = _classify_factor_test_row(merged)
            merged["data_status"] = "metric_supplied"
        rows.append(merged)
    return rows


def _factor_test_required_metric_gaps(rows: list[dict]) -> dict[str, int]:
    required_keys = [str(item["metric_key"]) for item in FACTOR_TEST_METRIC_SCHEMA if item.get("required")]
    return {
        key: sum(1 for row in rows if row.get(key) in (None, "", [], {}))
        for key in required_keys
    }


def _factor_test_window_summary(rows: list[dict]) -> dict[str, Any]:
    observation_count = 0
    valid_pair_count = 0
    trade_date_count = 0
    for row in rows:
        window = row.get("test_window") if isinstance(row.get("test_window"), Mapping) else {}
        observation_count += int(_to_number(window.get("observation_count"), 0) or 0)
        valid_pair_count += int(_to_number(window.get("valid_pair_count"), 0) or 0)
        trade_date_count = max(trade_date_count, int(_to_number(window.get("trade_date_count"), 0) or 0))
    return {
        "observation_count": observation_count,
        "valid_pair_count": valid_pair_count,
        "max_trade_date_count": trade_date_count,
        "has_forward_returns": valid_pair_count > 0,
        "sample_scope": "current_holding_watchlist",
        "full_market_research": False,
    }


def _factor_test_quality_summary(rows: list[dict], *, computed_count: int) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("result_status") or "not_enough_data")
        status_counts[key] = status_counts.get(key, 0) + 1
    metric_gaps = _factor_test_required_metric_gaps(rows)
    return {
        "status": "computed_light_metrics_ready" if computed_count else "scaffold_only",
        "computed_item_count": computed_count,
        "factor_count": len(rows),
        "research_pass_count": status_counts.get("research_pass", 0),
        "watchlist_count": status_counts.get("watchlist", 0),
        "disabled_count": status_counts.get("disabled", 0),
        "invalid_count": status_counts.get("invalid", 0),
        "not_enough_data_count": status_counts.get("not_enough_data", 0),
        "required_metric_gap_counts": metric_gaps,
        "largest_required_metric_gap": max(metric_gaps.values()) if metric_gaps else 0,
        "window_summary": _factor_test_window_summary(rows),
        "allow_evidence_effects": False,
        "allow_strategy_trace": False,
        "allow_core_action": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "Factor Test Lab 指标只用于研究检验；即使 research_pass 也不会直接进入 strategy action。",
    }


def build_factor_test_packet(*, mode: str = "light", factor_library: Any = None, items: Any = None, observations: Any = None, now: Any = None) -> dict:
    now_text = _now_iso(now)
    selected_mode = mode if mode in {"light", "small_research", "full", "research", "cache_only"} else "light"
    library = factor_library if isinstance(factor_library, Mapping) else build_factor_library_packet(now=now_text)
    factors = [_as_mapping(item) for item in _as_list(library.get("factors")) if _as_mapping(item)]
    scaffold_rows = [_factor_test_scaffold_row(factor, mode=selected_mode, now=now_text) for factor in factors]
    computed_items = _factor_test_rows_from_observations(observations, now=now_text) if observations is not None else []
    supplied_items = list(_as_list(items)) + computed_items
    rows = _merge_factor_test_items(scaffold_rows, supplied_items, now_text)
    computed_count = len(computed_items)
    status_counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("result_status") or "not_enough_data")
        status_counts[key] = status_counts.get(key, 0) + 1
    quality_summary = _factor_test_quality_summary(rows, computed_count=computed_count)
    return {
        "packet_key": TEST_PACKET_KEY,
        "schema_version": "factor_test.v2",
        "phase": "phase_3_factor_test_lab_scaffold",
        "mode": selected_mode,
        "status": "ready" if computed_count else "scaffold_ready",
        "items": rows,
        "computed_item_count": computed_count,
        "quality_summary": quality_summary,
        "required_metric_gap_counts": quality_summary["required_metric_gap_counts"],
        "window_summary": quality_summary["window_summary"],
        "metric_schema": FACTOR_TEST_METRIC_SCHEMA,
        "mode_plan": FACTOR_TEST_MODE_PLAN,
        "result_categories": VALIDATION_STANDARDS,
        "status_counts": status_counts,
        "summary": "Factor Test Lab 已声明 IC/Rank IC/ICIR/分组收益/换手/成本后收益等研究指标；light observations 仅用于小样本研究计算，不跑全市场回测。",
        "validation_thresholds": {
            "research_pass": {
                "coverage_min": 0.8,
                "missing_rate_max": 0.15,
                "abs_ic_mean_min": 0.02,
                "icir_min": 0.3,
                "top_bottom_group_return": "positive",
                "cost_adjusted_return": "positive",
                "group_return_monotonicity": True,
            },
            "disabled": {
                "missing_rate_gt": 0.25,
                "icir_lt": 0,
                "group_return_monotonicity": False,
            },
            "not_enough_data": {
                "coverage_lt": 0.6,
                "missing_required_metrics": True,
            },
        },
        "governance": {
            "state": "research_only",
            "allow_research_display": True,
            "allow_evidence_effects": False,
            "allow_strategy_trace": False,
            "allow_core_action": False,
        },
        "decision_usage_policy": DECISION_USAGE_POLICY,
        "call_ledger": [
            {
                "api": "local_factor_test_lab_scaffold",
                "request_params_safe": {"mode": selected_mode, "factor_count": len(rows)},
                "row_count": len(rows),
                "data_date": None,
                "local_fetched_at": now_text,
                "call_status": "scaffold_ready",
                "error_message_safe": "",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "当前是 Factor Test Lab research metrics scaffold，不代表因子已通过检验。",
            "回测收益不代表未来收益；缺失因子不得当负面。",
            "pit_validated=False 不得成为强 support；任何进入 strategy action 都需要后续单独审批。",
        ],
        "updated_at": now_text,
        "deepseek_called": False,
        "tushare_called": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def compute_light_mode_factor_ic_metrics(*, observations: Any, factor_library: Any = None, now: Any = None) -> dict:
    """Build a light-mode factor test packet from caller-supplied local observations."""
    return build_factor_test_packet(mode="light", factor_library=factor_library, observations=observations, now=now)


def build_factor_score_packet(*, runtime_packet: Any = None, now: Any = None) -> dict:
    now_text = _now_iso(now)
    runtime = _as_mapping(runtime_packet)
    values = [_as_mapping(item) for item in _as_list(runtime.get("factor_values")) if _as_mapping(item)]
    support = [item for item in values if item.get("effect") == "support" and item.get("enters_composite_score")]
    suppress = [item for item in values if item.get("effect") == "suppress" and item.get("enters_composite_score")]
    neutral = [item for item in values if item.get("effect") == "neutral" and not item.get("excluded_from_score")]
    missing = [item for item in values if item.get("effect") == "missing"]
    conflict = []
    if support and suppress:
        conflict.append(
            {
                "conflict_key": "support_and_suppress_coexist",
                "summary": "支持因子与压制因子同时存在，需要进入人工核验。",
                "support_count": len(support),
                "suppress_count": len(suppress),
            }
        )
    scoreable = [item for item in values if item.get("enters_composite_score")]
    if scoreable:
        avg = statistics.fmean(float(item.get("score_impact") or 0.0) for item in scoreable)
        composite = round(50 + avg * 25, 2)
    else:
        avg = 0.0
        composite = None
    if composite is None:
        band = "missing"
    elif avg >= 0.65:
        band = "strong"
    elif avg >= 0.2:
        band = "positive"
    elif avg <= -0.2:
        band = "weak"
    else:
        band = "neutral"
    coverage = _to_number(runtime.get("coverage"), 0.0) or 0.0
    strength = "high" if coverage >= 0.7 and len(scoreable) >= 6 else ("medium" if coverage >= 0.35 and len(scoreable) >= 3 else "low")
    return {
        "packet_key": SCORE_PACKET_KEY,
        "schema_version": "factor_score.v1",
        "phase": MVP_PHASE,
        "status": "ready" if values else "not_run",
        "composite_score": composite,
        "score_band": band,
        "support_factors": support,
        "suppress_factors": suppress,
        "neutral_factors": neutral,
        "missing_factors": missing,
        "conflict_factors": conflict,
        "evidence_strength": strength,
        "updated_at": now_text,
        "warnings": [
            "缺失/无记录不作为负面。",
            "pit_validated=False 的因子不能成为强 support。",
            "Serenity/瓶颈方法来源不进入 composite score。",
        ],
        "deepseek_called": False,
        "tushare_called": False,
        "external_calls_triggered": False,
    }


def _build_factor_evidence_preview(score_packet: Mapping[str, Any]) -> list[dict]:
    preview = []
    for effect_key, effect in (("support_factors", "support"), ("suppress_factors", "suppress")):
        for item in _as_list(score_packet.get(effect_key))[:4]:
            factor = _as_mapping(item)
            if not factor:
                continue
            preview.append(
                {
                    "source": SCORE_PACKET_KEY,
                    "factor_key": factor.get("factor_key"),
                    "label": factor.get("factor_name"),
                    "effect": effect,
                    "summary": factor.get("status_note") or factor.get("direction") or "",
                    "enters_evidence_effects": True,
                    "does_not_modify_action": True,
                    "does_not_modify_operation_zones": True,
                }
            )
    for item in _as_list(score_packet.get("conflict_factors")):
        conflict = _as_mapping(item)
        preview.append(
            {
                "source": SCORE_PACKET_KEY,
                "factor_key": conflict.get("conflict_key"),
                "label": "因子冲突",
                "effect": "conflict",
                "summary": conflict.get("summary"),
                "enters_evidence_effects": True,
                "does_not_modify_action": True,
                "does_not_modify_operation_zones": True,
            }
        )
    return preview


def _research_context(chokepoint_packet: Any = None, serenity_packet: Any = None) -> dict:
    chokepoint = _as_mapping(chokepoint_packet)
    serenity = _as_mapping(serenity_packet)
    return {
        "chokepoint": {
            "available": bool(chokepoint),
            "summary": chokepoint.get("summary") or "",
            "source_packet": "command_center_chokepoint_scan_packet",
            "enters_composite_score": False,
        },
        "serenity": {
            "available": bool(serenity),
            "summary": serenity.get("summary") or "",
            "source_packet": "command_center_serenity_method_radar_packet",
            "enters_composite_score": False,
        },
    }


def build_factor_quant_hub_packet(
    *,
    mode: str = "cache_only",
    universe: Any = None,
    factor_library: Any = None,
    data_ledger: Any = None,
    runtime_packet: Any = None,
    factor_test_packet: Any = None,
    score_packet: Any = None,
    daily_close_packet: Any = None,
    daily_basic_packet: Any = None,
    trade_calendar_packet: Any = None,
    moneyflow_packet: Any = None,
    hard_risk_packet: Any = None,
    limit_emotion_packet: Any = None,
    chip_packet: Any = None,
    a_share_fact_lineage_summary: Any = None,
    next_session_projection_packet: Any = None,
    strategy_execution_packet: Any = None,
    decision_packet: Any = None,
    trade_review_summary: Any = None,
    legacy_quant_packet: Any = None,
    chokepoint_packet: Any = None,
    serenity_packet: Any = None,
    call_ledger: Any = None,
    deepseek_explanation: Any = None,
    now: Any = None,
) -> dict:
    now_text = _now_iso(now)
    selected_mode = mode if mode in {"cache_only", "light", "full", "research"} else "cache_only"
    library = factor_library if isinstance(factor_library, Mapping) else build_factor_library_packet(now=now_text)
    ledger = data_ledger if isinstance(data_ledger, Mapping) else build_factor_data_ledger_packet(factor_library=library, now=now_text)
    if isinstance(runtime_packet, Mapping):
        runtime = dict(runtime_packet)
    elif selected_mode == "light":
        runtime = build_factor_runtime_packet(
            factor_library=library,
            daily_close_packet=daily_close_packet,
            daily_basic_packet=daily_basic_packet,
            moneyflow_packet=moneyflow_packet,
            hard_risk_packet=hard_risk_packet,
            limit_emotion_packet=limit_emotion_packet,
            chip_packet=chip_packet,
            mode="light",
            universe=universe,
            now=now_text,
        )
    else:
        runtime = {
            "packet_key": RUNTIME_PACKET_KEY,
            "schema_version": "factor_runtime.v1",
            "status": "not_run",
            "factor_values": [],
            "available_count": 0,
            "coverage": 0.0,
            "missing_count": len(library.get("factors") or []),
            "calculated_at": now_text,
        }
    trading_calendar_context = _expected_data_date(now_text, trade_calendar_packet)
    call_rows = _call_ledger_rows(
        call_ledger,
        now=now_text,
        calendar_context=trading_calendar_context,
        trade_calendar_packet=trade_calendar_packet,
    )
    freshness_gate = _build_data_freshness_gate(call_rows, now=now_text, calendar_context=trading_calendar_context)
    runtime = _apply_freshness_gate_to_runtime(runtime, freshness_gate)
    tests = factor_test_packet if isinstance(factor_test_packet, Mapping) else build_factor_test_packet(mode=selected_mode, now=now_text)
    score = score_packet if isinstance(score_packet, Mapping) else build_factor_score_packet(runtime_packet=runtime, now=now_text)
    sanitized_deepseek = sanitize_factor_deepseek_explanation(deepseek_explanation) if deepseek_explanation else {"called": False, "payload": None}
    universe_map = _as_mapping(universe)
    governance_state = "evidence_effect_only" if score.get("status") == "ready" else "research_only"
    bridge_preview = _build_factor_evidence_preview(score)
    warnings = list(score.get("warnings") or [])
    if runtime.get("coverage", 0) < 0.35:
        warnings.append("多因子覆盖率偏低，仅可作为研究解释。")
    if freshness_gate.get("gate_applied") and freshness_gate.get("status") != "fresh":
        warnings.append("数据时效门控未通过：过期或陈旧数据不得进入 composite score、强 support 或交易解释。")
    return {
        "packet_key": QUANT_HUB_PACKET_KEY,
        "schema_version": QUANT_HUB_SCHEMA_VERSION,
        "phase": MVP_PHASE,
        "mode": selected_mode,
        "universe": {
            "type": universe_map.get("type") or "current_target",
            "items": list(universe_map.get("items") or []),
            "size": int(_to_number(universe_map.get("size"), len(universe_map.get("items") or [])) or 0),
        },
        "data_ledger": _copy_json(ledger),
        "factor_library": _copy_json(library),
        "runtime": _copy_json(runtime),
        "factor_tests": _copy_json(tests),
        "score": _copy_json(score),
        "data_freshness_gate": _copy_json(freshness_gate),
        "trading_calendar_context": _copy_json(trading_calendar_context),
        "governance": {
            "state": governance_state,
            "allow_evidence_effects": True,
            "allow_strategy_trace": False,
            "allow_core_action": False,
        },
        "next_session_bridge": {
            "enters_evidence_effects": True,
            "does_not_modify_action": True,
            "does_not_modify_prices": True,
            "does_not_modify_holdings": True,
            "does_not_modify_operation_zones": True,
            "preview": bridge_preview,
            "source_packet": "command_center_factor_score_packet",
        },
        "deepseek_explanation": sanitized_deepseek,
        "research_context": _research_context(chokepoint_packet, serenity_packet),
        "linked_packets": {
            "a_share_fact_lineage_summary": bool(_as_mapping(a_share_fact_lineage_summary)),
            "trade_calendar_packet": bool(_as_mapping(trade_calendar_packet)),
            "command_center_daily_close_packet": bool(_as_mapping(daily_close_packet)),
            "command_center_next_session_projection_packet": bool(_as_mapping(next_session_projection_packet)),
            "strategy_execution_packet": bool(_as_mapping(strategy_execution_packet)),
            "decision_packet": bool(_as_mapping(decision_packet)),
            "trade_review_summary": bool(_as_mapping(trade_review_summary)),
            "legacy_quant_packet": bool(_as_mapping(legacy_quant_packet)),
        },
        "warnings": warnings,
        "call_ledger": call_rows,
        "updated_at": now_text,
        "deepseek_called": bool(_as_mapping(sanitized_deepseek).get("called")),
        "tushare_called": bool(call_rows),
        "external_calls_triggered": bool(call_rows),
        "does_not_modify_strategy_action": True,
        "does_not_modify_next_session_operation_zones": True,
        "does_not_execute_trades": True,
    }


def build_factor_deepseek_explanation_prompt(hub_packet: Any) -> dict:
    hub = _as_mapping(hub_packet)
    score = _as_mapping(hub.get("score"))
    prompt_payload = {
        "schema": sorted(DEEPSEEK_EXPLANATION_ALLOWED_KEYS),
        "mode": hub.get("mode"),
        "coverage": _as_mapping(hub.get("runtime")).get("coverage"),
        "score_band": score.get("score_band"),
        "support_factors": [
            {"factor_key": item.get("factor_key"), "factor_name": item.get("factor_name"), "direction": item.get("direction")}
            for item in _as_list(score.get("support_factors"))[:6]
            if isinstance(item, Mapping)
        ],
        "suppress_factors": [
            {"factor_key": item.get("factor_key"), "factor_name": item.get("factor_name"), "direction": item.get("direction")}
            for item in _as_list(score.get("suppress_factors"))[:6]
            if isinstance(item, Mapping)
        ],
        "conflict_factors": _as_list(score.get("conflict_factors"))[:4],
        "missing_factors": [
            {"factor_key": item.get("factor_key"), "factor_name": item.get("factor_name"), "status_note": item.get("status_note")}
            for item in _as_list(score.get("missing_factors"))[:8]
            if isinstance(item, Mapping)
        ],
        "discipline": {
            "does_not_modify_action": True,
            "does_not_output_price_or_position": True,
            "not_trading_advice": True,
        },
    }
    prompt_json = json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True, default=str)
    input_hash = hashlib.sha256(prompt_json.encode("utf-8")).hexdigest()
    token_estimate = max(1, math.ceil(len(prompt_json) / 4))
    return {
        "system_prompt": "你是多因子研究结果整理器。只解释用户提供的结构化因子结果，不生成或覆盖任何数值，不输出交易动作。",
        "user_prompt": (
            "请只输出 JSON object，顶层键只能是 summary、support_notes、suppress_notes、"
            "conflict_notes、missing_data_notes、discipline_notes。不得输出价格、持仓、因子值、strategy action、买卖指令或完整 packet。\n\n"
            + json.dumps(prompt_payload, ensure_ascii=False, indent=2, default=str)
        ),
        "input_hash": input_hash,
        "token_estimate": token_estimate,
        "prompt_payload_summary": {
            "mode": prompt_payload.get("mode"),
            "coverage": prompt_payload.get("coverage"),
            "score_band": prompt_payload.get("score_band"),
            "support_count": len(prompt_payload.get("support_factors") or []),
            "suppress_count": len(prompt_payload.get("suppress_factors") or []),
            "missing_count": len(prompt_payload.get("missing_factors") or []),
        },
        "allowed_top_level_keys": sorted(DEEPSEEK_EXPLANATION_ALLOWED_KEYS),
        "enters_deepseek_prompt": True,
        "does_not_include_full_packet": True,
    }


def _extract_json_object_text(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    return text[start : end + 1] if start >= 0 and end > start else ""


def _payload_hash(payload: Any) -> str:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def sanitize_factor_deepseek_explanation(payload: Any, *, model_used: str | None = None, input_hash: str | None = None) -> dict:
    parsed = payload if isinstance(payload, Mapping) else {}
    parse_error = ""
    if isinstance(payload, str):
        text = _extract_json_object_text(payload)
        try:
            parsed = json.loads(text) if text else {}
        except Exception as exc:
            parsed = {}
            parse_error = f"DeepSeek JSON 解析失败：{exc}"
    sanitized = {}
    ignored_keys = []
    for key, value in _as_mapping(parsed).items():
        if key not in DEEPSEEK_EXPLANATION_ALLOWED_KEYS:
            ignored_keys.append(str(key))
            continue
        if key == "summary":
            sanitized[key] = str(value or "")[:500]
        else:
            sanitized[key] = [str(item)[:240] for item in _as_list(value)[:8] if str(item).strip()]
    for key in DEEPSEEK_EXPLANATION_ALLOWED_KEYS:
        sanitized.setdefault(key, "" if key == "summary" else [])
    output_hash = _payload_hash(payload) if payload else ""
    output_token_estimate = max(0, math.ceil(len(str(payload or "")) / 4))
    parse_failed = not (sanitized.get("summary") or any(sanitized.get(key) for key in DEEPSEEK_EXPLANATION_ALLOWED_KEYS if key != "summary"))
    return {
        "called": bool(payload),
        "status": "parse_failed" if parse_failed else "success",
        "parse_failed": parse_failed,
        "payload": sanitized,
        "ignored_keys": sorted(ignored_keys),
        "error_message_safe": parse_error,
        "model_used": model_used or "",
        "input_hash": input_hash or "",
        "output_hash": output_hash,
        "token_estimate": output_token_estimate,
        "does_not_override_numeric_values": True,
        "does_not_output_strategy_action": True,
    }
