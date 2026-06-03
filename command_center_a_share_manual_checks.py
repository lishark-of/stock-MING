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


def merge_a_share_capability_item(packet: Any = None, item: Any = None, checked_at: Any = "") -> dict:
    existing = dict(packet) if isinstance(packet, Mapping) else {}
    new_item = dict(item) if isinstance(item, Mapping) else {}
    merged_items = []
    replaced = False
    section = str(new_item.get("section") or "")
    api = str(new_item.get("api") or "")
    for raw in existing.get("items") or []:
        payload = dict(raw) if isinstance(raw, Mapping) else {}
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
