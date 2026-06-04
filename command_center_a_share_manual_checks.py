from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from typing import Any

import market_data_capability as data_capability


MARGIN_SECTION = "margin"
MARGIN_API = "margin_detail"
MARGIN_LABEL = "融资融券"
LIMIT_CPT_SECTION = "limit_emotion"
LIMIT_CPT_API = "limit_cpt_list"
LIMIT_CPT_LABEL = "涨跌停/情绪"
CHIP_SECTION = "chip_radar"
CHIP_API = "cyq_perf/cyq_chips"
CHIP_LABEL = "筹码/胜率"
CYQ_PERF_API = "cyq_perf"
CYQ_CHIPS_API = "cyq_chips"
DRAGON_SECTION = "dragon_tiger"
DRAGON_API = "top_list/top_inst"
DRAGON_LABEL = "龙虎榜"
TOP_LIST_API = "top_list"
TOP_INST_API = "top_inst"
MONEYFLOW_SECTION = "moneyflow"
MONEYFLOW_API = "moneyflow"
MONEYFLOW_LABEL = "个股资金流"
HARD_RISK_SECTION = "hard_risk"
HARD_RISK_API = "anns_d/forecast/stk_holdertrade/share_float/pledge_stat/pledge_detail"
HARD_RISK_LABEL = "公告/硬风险"
HARD_RISK_APIS = (
    "anns_d",
    "forecast",
    "stk_holdertrade",
    "share_float",
    "pledge_stat",
    "pledge_detail",
)

SECTION_WRITES_PACKET = {
    MONEYFLOW_SECTION: "command_center_moneyflow_packet",
    DRAGON_SECTION: "command_center_dragon_tiger_packet",
    MARGIN_SECTION: "command_center_margin_packet",
    LIMIT_CPT_SECTION: "command_center_limit_emotion_packet",
    CHIP_SECTION: "command_center_chip_packet",
    HARD_RISK_SECTION: "command_center_hard_risk_packet",
}

API_SECTION = {
    MONEYFLOW_API: MONEYFLOW_SECTION,
    TOP_LIST_API: DRAGON_SECTION,
    TOP_INST_API: DRAGON_SECTION,
    DRAGON_API: DRAGON_SECTION,
    MARGIN_API: MARGIN_SECTION,
    LIMIT_CPT_API: LIMIT_CPT_SECTION,
    CYQ_PERF_API: CHIP_SECTION,
    CYQ_CHIPS_API: CHIP_SECTION,
    CHIP_API: CHIP_SECTION,
    HARD_RISK_API: HARD_RISK_SECTION,
}

SECTION_LABELS = {
    MONEYFLOW_SECTION: MONEYFLOW_LABEL,
    DRAGON_SECTION: DRAGON_LABEL,
    MARGIN_SECTION: MARGIN_LABEL,
    LIMIT_CPT_SECTION: LIMIT_CPT_LABEL,
    CHIP_SECTION: CHIP_LABEL,
    HARD_RISK_SECTION: HARD_RISK_LABEL,
}


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def normalize_a_share_ts_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if text.endswith((".SH", ".SZ", ".BJ")):
        return text
    if text.endswith(".SS"):
        return text[:-3] + ".SH"
    base = text.split(".")[0]
    if base.isdigit() and len(base) == 6:
        if base.startswith("6"):
            return f"{base}.SH"
        if base.startswith(("0", "3")):
            return f"{base}.SZ"
        if base.startswith(("4", "8")):
            return f"{base}.BJ"
    return text


def is_a_share_ts_code(value: Any) -> bool:
    return normalize_a_share_ts_code(value).endswith((".SH", ".SZ", ".BJ"))


def _date_text(value: _dt.date) -> str:
    return value.strftime("%Y%m%d")


def build_margin_detail_check_request(ticker: Any, today: Any = None, lookback_days: int = 30) -> dict:
    ts_code = normalize_a_share_ts_code(ticker)
    if isinstance(today, _dt.datetime):
        end = today.date()
    elif isinstance(today, _dt.date):
        end = today
    elif isinstance(today, str) and today.strip():
        end = _dt.date.fromisoformat(today.strip()[:10])
    else:
        end = _dt.date.today()
    start = end - _dt.timedelta(days=max(1, int(lookback_days or 30)))
    return {
        "section": MARGIN_SECTION,
        "label": MARGIN_LABEL,
        "api": MARGIN_API,
        "ts_code": ts_code,
        "start_date": _date_text(start),
        "end_date": _date_text(end),
        "refresh_policy": "button_gated",
        "deepseek_called": False,
    }


def build_dragon_tiger_check_request(ticker: Any, today: Any = None, lookback_days: int = 30) -> dict:
    ts_code = normalize_a_share_ts_code(ticker)
    if isinstance(today, _dt.datetime):
        end = today.date()
    elif isinstance(today, _dt.date):
        end = today
    elif isinstance(today, str) and today.strip():
        end = _dt.date.fromisoformat(today.strip()[:10])
    else:
        end = _dt.date.today()
    start = end - _dt.timedelta(days=max(1, int(lookback_days or 30)))
    return {
        "section": DRAGON_SECTION,
        "label": DRAGON_LABEL,
        "api": DRAGON_API,
        "ts_code": ts_code,
        "start_date": _date_text(start),
        "end_date": _date_text(end),
        "refresh_policy": "button_gated",
        "deepseek_called": False,
    }


def build_moneyflow_check_request(ticker: Any, today: Any = None, lookback_days: int = 10) -> dict:
    ts_code = normalize_a_share_ts_code(ticker)
    if isinstance(today, _dt.datetime):
        end = today.date()
    elif isinstance(today, _dt.date):
        end = today
    elif isinstance(today, str) and today.strip():
        end = _dt.date.fromisoformat(today.strip()[:10])
    else:
        end = _dt.date.today()
    start = end - _dt.timedelta(days=max(1, int(lookback_days or 10)))
    return {
        "section": MONEYFLOW_SECTION,
        "label": MONEYFLOW_LABEL,
        "api": MONEYFLOW_API,
        "ts_code": ts_code,
        "start_date": _date_text(start),
        "end_date": _date_text(end),
        "refresh_policy": "button_gated",
        "deepseek_called": False,
    }


def build_limit_cpt_check_request(today: Any = None, lookback_days: int = 10) -> dict:
    if isinstance(today, _dt.datetime):
        end = today.date()
    elif isinstance(today, _dt.date):
        end = today
    elif isinstance(today, str) and today.strip():
        end = _dt.date.fromisoformat(today.strip()[:10])
    else:
        end = _dt.date.today()
    start = end - _dt.timedelta(days=max(1, int(lookback_days or 10)))
    return {
        "section": LIMIT_CPT_SECTION,
        "label": LIMIT_CPT_LABEL,
        "api": LIMIT_CPT_API,
        "start_date": _date_text(start),
        "end_date": _date_text(end),
        "refresh_policy": "button_gated",
        "deepseek_called": False,
    }


def build_chip_radar_check_request(ticker: Any, today: Any = None, lookback_days: int = 30) -> dict:
    ts_code = normalize_a_share_ts_code(ticker)
    if isinstance(today, _dt.datetime):
        end = today.date()
    elif isinstance(today, _dt.date):
        end = today
    elif isinstance(today, str) and today.strip():
        end = _dt.date.fromisoformat(today.strip()[:10])
    else:
        end = _dt.date.today()
    start = end - _dt.timedelta(days=max(1, int(lookback_days or 30)))
    return {
        "section": CHIP_SECTION,
        "label": CHIP_LABEL,
        "api": CHIP_API,
        "ts_code": ts_code,
        "start_date": _date_text(start),
        "end_date": _date_text(end),
        "refresh_policy": "button_gated",
        "deepseek_called": False,
    }


def build_hard_risk_check_request(ticker: Any, today: Any = None) -> dict:
    ts_code = normalize_a_share_ts_code(ticker)
    if isinstance(today, _dt.datetime):
        end = today.date()
    elif isinstance(today, _dt.date):
        end = today
    elif isinstance(today, str) and today.strip():
        end = _dt.date.fromisoformat(today.strip()[:10])
    else:
        end = _dt.date.today()
    return {
        "section": HARD_RISK_SECTION,
        "label": HARD_RISK_LABEL,
        "api": HARD_RISK_API,
        "apis": list(HARD_RISK_APIS),
        "ts_code": ts_code,
        "ann_start_date": _date_text(end - _dt.timedelta(days=90)),
        "forecast_start_date": _date_text(end - _dt.timedelta(days=180)),
        "holder_start_date": _date_text(end - _dt.timedelta(days=180)),
        "unlock_start_date": _date_text(end),
        "unlock_end_date": _date_text(end + _dt.timedelta(days=90)),
        "end_date": _date_text(end),
        "refresh_policy": "button_gated",
        "deepseek_called": False,
    }


def build_margin_detail_capability_item(result: Any = None, latency_ms: int | float | None = 0) -> dict:
    item = data_capability.summarize_tushare_result(MARGIN_API, result=result, latency_ms=latency_ms)
    item.update(
        {
            "section": MARGIN_SECTION,
            "label": MARGIN_LABEL,
            "api": MARGIN_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
        }
    )
    return item


def build_moneyflow_capability_item(result: Any = None, latency_ms: int | float | None = 0) -> dict:
    item = data_capability.summarize_tushare_result(MONEYFLOW_API, result=result, latency_ms=latency_ms)
    item.update(
        {
            "section": MONEYFLOW_SECTION,
            "label": MONEYFLOW_LABEL,
            "api": MONEYFLOW_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
        }
    )
    return item


def _state_from_item(item: Any) -> str:
    return str(as_mapping(item).get("capability_state") or "")


def _combine_latest_date(items: list[dict]) -> str:
    values = [str(item.get("latest_date") or "") for item in items if item.get("latest_date")]
    return sorted(values, reverse=True)[0] if values else ""


def _combine_errors(items: list[dict]) -> str:
    parts = []
    for item in items:
        api = str(item.get("api") or "")
        error = str(item.get("error") or item.get("status") or "").strip()
        if error:
            parts.append(f"{api}: {error}" if api else error)
    return "；".join(parts)


def _manual_section_from_item(item: Mapping[str, Any]) -> str:
    section = str(item.get("section") or "").strip()
    if section:
        return section
    api = str(item.get("api") or "").strip()
    return API_SECTION.get(api, "")


def _manual_writes_packet(section: str) -> str:
    return SECTION_WRITES_PACKET.get(str(section or ""), "command_center_facts_packet")


def _manual_recovery_state(state: str) -> str:
    normalized = data_capability.normalize_capability_state_value(state)
    if normalized == data_capability.STATE_AVAILABLE:
        return "recovered"
    if normalized in {data_capability.STATE_STALE_CACHE, data_capability.STATE_FALLBACK_USED}:
        return "cached"
    if normalized in {
        data_capability.STATE_PERMISSION_DENIED,
        data_capability.STATE_DISABLED_THIS_SESSION,
        data_capability.STATE_NOT_CONFIGURED,
        data_capability.STATE_NETWORK_FAILED,
        data_capability.STATE_FAILED,
    }:
        return "blocked"
    return "waiting"


def _manual_data_status(state: str) -> str:
    normalized = data_capability.normalize_capability_state_value(state)
    if normalized == data_capability.STATE_AVAILABLE:
        return "ready"
    if normalized == data_capability.STATE_STALE_CACHE:
        return "cached"
    if normalized == data_capability.STATE_FALLBACK_USED:
        return "fallback"
    if normalized == data_capability.STATE_EMPTY_RECENT:
        return "no_recent_data"
    if normalized == data_capability.STATE_REQUIRES_MANUAL_REFRESH:
        return "manual_required"
    if normalized in {
        data_capability.STATE_PERMISSION_DENIED,
        data_capability.STATE_DISABLED_THIS_SESSION,
        data_capability.STATE_NOT_CONFIGURED,
        data_capability.STATE_NETWORK_FAILED,
        data_capability.STATE_FAILED,
    }:
        return "blocked"
    return "waiting"


def _manual_decision_chain_state(state: str) -> str:
    normalized = data_capability.normalize_capability_state_value(state)
    if normalized == data_capability.STATE_AVAILABLE:
        return "ready"
    if normalized in {data_capability.STATE_STALE_CACHE, data_capability.STATE_FALLBACK_USED}:
        return "cache_only"
    if normalized in {
        data_capability.STATE_PERMISSION_DENIED,
        data_capability.STATE_DISABLED_THIS_SESSION,
        data_capability.STATE_NOT_CONFIGURED,
        data_capability.STATE_NETWORK_FAILED,
        data_capability.STATE_FAILED,
    }:
        return "blocked"
    return "waiting"


def _manual_can_enter_decision_chain(state: str) -> bool:
    return _manual_decision_chain_state(state) in {"ready", "cache_only"}


def normalize_manual_result_item(item: Any = None, *, checked_at: Any = "", writes_packet: Any = "") -> dict:
    """Attach the standard command-center contract to one button-gated A-share check result."""
    payload = as_mapping(item)
    if not payload:
        return {}
    section = _manual_section_from_item(payload)
    label = str(payload.get("label") or SECTION_LABELS.get(section) or payload.get("api") or "A股数据能力")
    state = data_capability.normalize_capability_state_value(
        payload.get("capability_state") or payload.get("state") or payload.get("status") or ""
    )
    if state == "unknown":
        state = data_capability.STATE_FAILED if payload.get("error") else data_capability.STATE_EMPTY_RECENT
    status_label = data_capability.state_label(state)
    updated_at = str(checked_at or payload.get("checked_at") or payload.get("updated_at") or payload.get("latest_date") or "")
    normalized = dict(payload)
    normalized.update(
        {
            "section": section,
            "label": label,
            "manual_check": True,
            "manual_check_key": section,
            "manual_check_label": label,
            "writes_packet": str(writes_packet or payload.get("writes_packet") or _manual_writes_packet(section)),
            "capability_state": state,
            "status": status_label,
            "status_label": status_label,
            "capability_label": status_label,
            "data_status": _manual_data_status(state),
            "recovery_state": _manual_recovery_state(state),
            "decision_chain_state": _manual_decision_chain_state(state),
            "can_enter_decision_chain": _manual_can_enter_decision_chain(state),
            "decision_chain_stage": "数据能力状态 → 市场分析方法 → 趋势推演 → 策略执行 → 今日总决策",
            "decision_chain_effect": data_capability.decision_impact_for_capability_state(state, label),
            "meaning": data_capability.meaning_for_capability_state(state, "Tushare", label),
            "next_action": data_capability.next_action_for_capability_state(state, label),
            "refresh_policy": "button_gated",
            "external_call_policy": "button_gated",
            "auto_run": False,
            "deepseek_called": False,
            "checked_at": updated_at,
            "updated_at": updated_at,
        }
    )
    return normalized


def build_chip_radar_capability_item(
    perf_result: Any = None,
    chips_result: Any = None,
    latency_ms: int | float | None = 0,
) -> dict:
    perf_item = data_capability.summarize_tushare_result(CYQ_PERF_API, result=perf_result, latency_ms=latency_ms)
    chips_item = data_capability.summarize_tushare_result(CYQ_CHIPS_API, result=chips_result, latency_ms=latency_ms)
    sub_items = [perf_item, chips_item]
    states = {_state_from_item(item) for item in sub_items}
    available_count = sum(1 for item in sub_items if _state_from_item(item) == data_capability.STATE_AVAILABLE)
    row_count = sum(int(item.get("rows") or 0) for item in sub_items)
    latest_date = _combine_latest_date(sub_items)
    error_text = _combine_errors(sub_items)
    if data_capability.STATE_PERMISSION_DENIED in states:
        item = data_capability.build_capability_item(CHIP_API, rows=row_count, latest_date=latest_date, latency_ms=latency_ms, error=error_text)
    elif data_capability.STATE_DISABLED_THIS_SESSION in states:
        item = data_capability.build_capability_item(CHIP_API, rows=row_count, latest_date=latest_date, latency_ms=latency_ms, error=error_text, skipped=True)
    elif available_count == len(sub_items):
        item = data_capability.build_capability_item(CHIP_API, ok=True, rows=row_count, latest_date=latest_date, latency_ms=latency_ms)
    elif available_count:
        partial_error = "仅取得部分筹码/胜率接口结果。"
        if error_text:
            partial_error = f"{partial_error} {error_text}"
        item = data_capability.build_capability_item(
            CHIP_API,
            rows=row_count,
            latest_date=latest_date,
            latency_ms=latency_ms,
            error=partial_error,
            fallback_used=True,
        )
    elif states and states <= {data_capability.STATE_EMPTY_RECENT}:
        item = data_capability.build_capability_item(CHIP_API, ok=True, rows=0, latest_date=latest_date, latency_ms=latency_ms)
    else:
        item = data_capability.build_capability_item(CHIP_API, rows=row_count, latest_date=latest_date, latency_ms=latency_ms, error=error_text)
    item.update(
        {
            "section": CHIP_SECTION,
            "label": CHIP_LABEL,
            "api": CHIP_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
            "sub_items": sub_items,
        }
    )
    return item


def build_dragon_tiger_capability_item(
    top_list_result: Any = None,
    top_inst_result: Any = None,
    latency_ms: int | float | None = 0,
) -> dict:
    top_list_item = data_capability.summarize_tushare_result(TOP_LIST_API, result=top_list_result, latency_ms=latency_ms)
    top_inst_item = data_capability.summarize_tushare_result(TOP_INST_API, result=top_inst_result, latency_ms=latency_ms)
    sub_items = [top_list_item, top_inst_item]
    states = {_state_from_item(item) for item in sub_items}
    top_list_state = _state_from_item(top_list_item)
    top_inst_state = _state_from_item(top_inst_item)
    row_count = sum(int(item.get("rows") or 0) for item in sub_items)
    latest_date = _combine_latest_date(sub_items)
    error_text = _combine_errors(sub_items)
    if data_capability.STATE_PERMISSION_DENIED in states:
        item = data_capability.build_capability_item(DRAGON_API, rows=row_count, latest_date=latest_date, latency_ms=latency_ms, error=error_text)
    elif data_capability.STATE_DISABLED_THIS_SESSION in states:
        item = data_capability.build_capability_item(DRAGON_API, rows=row_count, latest_date=latest_date, latency_ms=latency_ms, error=error_text, skipped=True)
    elif top_list_state == data_capability.STATE_AVAILABLE and top_inst_state == data_capability.STATE_AVAILABLE:
        item = data_capability.build_capability_item(DRAGON_API, ok=True, rows=row_count, latest_date=latest_date, latency_ms=latency_ms)
    elif top_list_state == data_capability.STATE_AVAILABLE:
        partial_error = "已取得龙虎榜上榜事实，但席位明细仍待验证。"
        if error_text:
            partial_error = f"{partial_error} {error_text}"
        item = data_capability.build_capability_item(
            DRAGON_API,
            rows=row_count,
            latest_date=latest_date,
            latency_ms=latency_ms,
            error=partial_error,
            fallback_used=True,
        )
    elif states and states <= {data_capability.STATE_EMPTY_RECENT}:
        item = data_capability.build_capability_item(DRAGON_API, ok=True, rows=0, latest_date=latest_date, latency_ms=latency_ms)
    else:
        item = data_capability.build_capability_item(DRAGON_API, rows=row_count, latest_date=latest_date, latency_ms=latency_ms, error=error_text)
    item.update(
        {
            "section": DRAGON_SECTION,
            "label": DRAGON_LABEL,
            "api": DRAGON_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
            "sub_items": sub_items,
        }
    )
    return item


def build_limit_cpt_capability_item(result: Any = None, latency_ms: int | float | None = 0) -> dict:
    item = data_capability.summarize_tushare_result(LIMIT_CPT_API, result=result, latency_ms=latency_ms)
    item.update(
        {
            "section": LIMIT_CPT_SECTION,
            "label": LIMIT_CPT_LABEL,
            "api": LIMIT_CPT_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
        }
    )
    return item


def _result_rows(result: Any = None, limit: int = 5, sort_key: str = "") -> list[dict]:
    payload = as_mapping(result)
    data = payload.get("data")
    if data is None:
        return []
    if hasattr(data, "empty") and data.empty:
        return []
    try:
        rows = data.to_dict("records") if hasattr(data, "to_dict") else list(data)
    except Exception:
        return []
    cleaned = []
    for raw in rows:
        row = as_mapping(raw)
        if not row:
            continue
        item = {}
        for key, value in row.items():
            if value is None:
                item[key] = ""
            elif isinstance(value, float) and value != value:
                item[key] = ""
            else:
                item[key] = value
        cleaned.append(item)
    if sort_key:
        cleaned = sorted(cleaned, key=lambda item: str(item.get(sort_key) or ""), reverse=True)
    return cleaned[: max(1, int(limit or 5))]


def _hard_risk_section(api: str, result: Any = None, rows: list[dict] | None = None, checked_at: Any = "") -> dict:
    payload = as_mapping(result)
    error = str(payload.get("error") or "")
    section_rows = rows if rows is not None else _result_rows(payload)
    return {
        "available": bool(section_rows),
        "source": "Tushare",
        "api": api,
        "rows": section_rows or [],
        "summary": f"取得 {len(section_rows or [])} 条记录。" if section_rows else "",
        "risk_flags": [],
        "message": "" if section_rows else (error or "暂无可验证数据"),
        "error": error,
        "updated_at": payload.get("updated_at") or checked_at,
    }


def _risk_keywords(text: Any) -> list[str]:
    haystack = str(text or "")
    keywords = ["处罚", "问询", "监管", "诉讼", "仲裁", "立案", "调查", "退市", "风险提示", "担保", "冻结", "减持", "质押", "解禁", "亏损", "修正"]
    return [keyword for keyword in keywords if keyword in haystack]


def build_hard_risk_fact_packet_from_results(
    ts_code: Any = "",
    stock_name: Any = "",
    results: Any = None,
    checked_at: Any = "",
) -> dict:
    payload = as_mapping(results)
    updated_at = str(checked_at or _dt.datetime.now().isoformat(timespec="seconds"))

    ann_rows = []
    ann_flags = []
    for item in _result_rows(payload.get("anns_d"), limit=6, sort_key="ann_date"):
        title = str(item.get("title") or "")
        matched = _risk_keywords(title)
        if matched:
            ann_flags.append(f"公告标题线索涉及：{','.join(matched[:3])}")
        ann_rows.append(
            {
                "ann_date": item.get("ann_date") or "",
                "title": title,
                "url": item.get("url") or "",
                "rec_time": item.get("rec_time") or "",
                "source": "Tushare anns_d",
            }
        )
    announcements = _hard_risk_section("anns_d", payload.get("anns_d"), ann_rows, updated_at)
    announcements["risk_flags"] = ann_flags
    announcements["summary"] = (
        f"近90天取得公告标题 {len(ann_rows)} 条；标题只作公告线索。"
        if ann_rows
        else announcements["summary"]
    )

    forecast_rows = []
    for item in _result_rows(payload.get("forecast"), limit=5, sort_key="ann_date"):
        forecast_rows.append(
            {
                "ann_date": item.get("ann_date") or "",
                "type": item.get("type") or "",
                "p_change_min": item.get("p_change_min") or "",
                "p_change_max": item.get("p_change_max") or "",
                "net_profit_min": item.get("net_profit_min") or "",
                "net_profit_max": item.get("net_profit_max") or "",
                "summary": item.get("type") or item.get("summary") or "业绩预告待解读",
            }
        )
    forecast = _hard_risk_section("forecast", payload.get("forecast"), forecast_rows, updated_at)

    holder_rows = []
    holder_flags = []
    for item in _result_rows(payload.get("stk_holdertrade"), limit=5, sort_key="ann_date"):
        trade_type = str(item.get("trade_type") or item.get("in_de") or "")
        holder_name = str(item.get("holder_name") or item.get("name") or "")
        holder_rows.append(
            {
                "ann_date": item.get("ann_date") or "",
                "holder_name": holder_name,
                "trade_type": trade_type,
                "change_vol": item.get("change_vol") or "",
                "change_ratio": item.get("change_ratio") or "",
                "summary": f"{holder_name} {trade_type}".strip() or "股东交易记录",
            }
        )
        if "减" in trade_type:
            holder_flags.append("存在股东减持记录")
    holder_reduction = _hard_risk_section("stk_holdertrade", payload.get("stk_holdertrade"), holder_rows, updated_at)
    holder_reduction["risk_flags"] = holder_flags

    unlock_rows = []
    for item in _result_rows(payload.get("share_float"), limit=5, sort_key="float_date"):
        unlock_rows.append(
            {
                "ann_date": item.get("ann_date") or "",
                "float_date": item.get("float_date") or "",
                "float_share": item.get("float_share") or "",
                "holder_name": item.get("holder_name") or "",
                "summary": item.get("holder_name") or "限售解禁记录",
            }
        )
    share_unlock = _hard_risk_section("share_float", payload.get("share_float"), unlock_rows, updated_at)

    pledge_rows = []
    pledge_flags = []
    for item in _result_rows(payload.get("pledge_stat"), limit=3):
        ratio = item.get("pledge_ratio") or item.get("p_total_ratio") or item.get("h_total_ratio") or ""
        pledge_rows.append(
            {
                "end_date": item.get("end_date") or "",
                "pledge_ratio": ratio,
                "pledge_count": item.get("pledge_count") or "",
                "summary": f"质押比例：{ratio}" if ratio not in ["", None] else "股权质押统计",
            }
        )
        try:
            if float(ratio) >= 15:
                pledge_flags.append(f"最近一期质押比例较高：{float(ratio):.2f}%")
        except Exception:
            pass
    for item in _result_rows(payload.get("pledge_detail"), limit=5):
        pledge_rows.append(
            {
                "ann_date": item.get("ann_date") or "",
                "holder_name": item.get("holder_name") or "",
                "pledge_amount": item.get("pledge_amount") or "",
                "summary": item.get("holder_name") or "股权质押明细",
            }
        )
    pledge = _hard_risk_section("pledge_stat/pledge_detail", payload.get("pledge_detail") or payload.get("pledge_stat"), pledge_rows, updated_at)
    pledge["risk_flags"] = pledge_flags

    sections = [announcements, forecast, holder_reduction, share_unlock, pledge]
    missing_items = []
    for section in sections:
        if not section.get("available"):
            missing_items.append(f"{section.get('api')}: {section.get('error') or section.get('message') or '暂无可验证数据'}")
    hard_risks = {
        "announcements": announcements,
        "earnings_forecast": forecast,
        "holder_reduction": holder_reduction,
        "share_unlock": share_unlock,
        "pledge": pledge,
        "available": any(section.get("available") for section in sections),
        "risk_flags": ann_flags + holder_flags + pledge_flags,
        "missing_items": missing_items,
        "updated_at": updated_at,
        "policy": {
            "ann_titles_are_clues_not_conclusions": True,
            "hard_risk_manual_check_is_button_gated": True,
        },
    }
    return {
        "stock": {"ts_code": normalize_a_share_ts_code(ts_code), "name": str(stock_name or "")},
        "verified_hard_risks": hard_risks,
        "missing_items": missing_items,
        "updated_at": updated_at,
        "deepseek_called": False,
    }


def build_hard_risk_capability_item(results: Any = None, latency_ms: int | float | None = 0) -> dict:
    payload = as_mapping(results)
    sub_items = [
        data_capability.summarize_tushare_result(api, result=payload.get(api), latency_ms=latency_ms)
        for api in HARD_RISK_APIS
    ]
    states = {_state_from_item(item) for item in sub_items}
    available_count = sum(1 for item in sub_items if _state_from_item(item) == data_capability.STATE_AVAILABLE)
    row_count = sum(int(item.get("rows") or 0) for item in sub_items)
    latest_date = _combine_latest_date(sub_items)
    error_text = _combine_errors(sub_items)
    if available_count == len(sub_items):
        item = data_capability.build_capability_item(HARD_RISK_API, ok=True, rows=row_count, latest_date=latest_date, latency_ms=latency_ms)
    elif available_count:
        item = data_capability.build_capability_item(
            HARD_RISK_API,
            rows=row_count,
            latest_date=latest_date,
            latency_ms=latency_ms,
            error=f"仅取得部分公告/硬风险接口结果。 {error_text}".strip(),
            fallback_used=True,
        )
    elif data_capability.STATE_PERMISSION_DENIED in states:
        item = data_capability.build_capability_item(HARD_RISK_API, rows=row_count, latest_date=latest_date, latency_ms=latency_ms, error=error_text)
    elif data_capability.STATE_DISABLED_THIS_SESSION in states:
        item = data_capability.build_capability_item(HARD_RISK_API, rows=row_count, latest_date=latest_date, latency_ms=latency_ms, error=error_text, skipped=True)
    elif states and states <= {data_capability.STATE_EMPTY_RECENT}:
        item = data_capability.build_capability_item(HARD_RISK_API, ok=True, rows=0, latest_date=latest_date, latency_ms=latency_ms)
    else:
        item = data_capability.build_capability_item(HARD_RISK_API, rows=row_count, latest_date=latest_date, latency_ms=latency_ms, error=error_text)
    item.update(
        {
            "section": HARD_RISK_SECTION,
            "label": HARD_RISK_LABEL,
            "api": HARD_RISK_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
            "sub_items": sub_items,
        }
    )
    return item


def build_margin_detail_exception_item(exc: Any, latency_ms: int | float | None = 0) -> dict:
    item = data_capability.summarize_tushare_exception(MARGIN_API, exc, latency_ms=latency_ms)
    item.update(
        {
            "section": MARGIN_SECTION,
            "label": MARGIN_LABEL,
            "api": MARGIN_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
        }
    )
    return item


def build_moneyflow_exception_item(exc: Any, latency_ms: int | float | None = 0) -> dict:
    item = data_capability.summarize_tushare_exception(MONEYFLOW_API, exc, latency_ms=latency_ms)
    item.update(
        {
            "section": MONEYFLOW_SECTION,
            "label": MONEYFLOW_LABEL,
            "api": MONEYFLOW_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
        }
    )
    return item


def build_chip_radar_exception_item(exc: Any, latency_ms: int | float | None = 0) -> dict:
    item = data_capability.summarize_tushare_exception(CHIP_API, exc, latency_ms=latency_ms)
    item.update(
        {
            "section": CHIP_SECTION,
            "label": CHIP_LABEL,
            "api": CHIP_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
            "sub_items": [],
        }
    )
    return item


def build_dragon_tiger_exception_item(exc: Any, latency_ms: int | float | None = 0) -> dict:
    item = data_capability.summarize_tushare_exception(DRAGON_API, exc, latency_ms=latency_ms)
    item.update(
        {
            "section": DRAGON_SECTION,
            "label": DRAGON_LABEL,
            "api": DRAGON_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
            "sub_items": [],
        }
    )
    return item


def build_limit_cpt_exception_item(exc: Any, latency_ms: int | float | None = 0) -> dict:
    item = data_capability.summarize_tushare_exception(LIMIT_CPT_API, exc, latency_ms=latency_ms)
    item.update(
        {
            "section": LIMIT_CPT_SECTION,
            "label": LIMIT_CPT_LABEL,
            "api": LIMIT_CPT_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
        }
    )
    return item


def build_hard_risk_exception_item(exc: Any, latency_ms: int | float | None = 0) -> dict:
    item = data_capability.summarize_tushare_exception(HARD_RISK_API, exc, latency_ms=latency_ms)
    item.update(
        {
            "section": HARD_RISK_SECTION,
            "label": HARD_RISK_LABEL,
            "api": HARD_RISK_API,
            "manual_check": True,
            "refresh_policy": "button_gated",
            "deepseek_called": False,
            "sub_items": [],
        }
    )
    return item


def merge_a_share_capability_item(packet: Any = None, item: Any = None, checked_at: Any = "") -> dict:
    existing = dict(packet) if isinstance(packet, Mapping) else {}
    new_item = normalize_manual_result_item(item, checked_at=checked_at)
    merged_items = []
    replaced = False
    section = str(new_item.get("section") or "")
    api = str(new_item.get("api") or "")
    for raw in existing.get("items") or []:
        payload = normalize_manual_result_item(raw, checked_at=raw.get("checked_at") if isinstance(raw, Mapping) else "")
        if not payload:
            continue
        same_section = section and str(payload.get("section") or "") == section
        same_api = api and str(payload.get("api") or "") == api
        if same_section or same_api:
            if new_item:
                merged_items.append(new_item)
                replaced = True
            continue
        merged_items.append(payload)
    if new_item and not replaced:
        merged_items.append(new_item)
    return data_capability.build_tushare_capability_packet(
        merged_items,
        checked_at=checked_at or existing.get("checked_at") or "",
        source=str(existing.get("source") or "Tushare A股专业事实"),
    )
