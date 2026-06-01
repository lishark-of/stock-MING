from __future__ import annotations

import datetime
from collections.abc import Mapping
from numbers import Number
from typing import Any


KNOWN_MODULES = (
    ("market", "市场环境"),
    ("quant", "量化推演"),
    ("discipline", "交易纪律"),
    ("margin_etf", "融资 ETF"),
    ("next_ticket", "下一票雷达"),
    ("strategy_execution", "策略执行"),
)

FAILED_STATUSES = {"failed", "failure", "error", "失败"}
READY_STATUSES = {"ok", "ready", "completed", "complete", "success", "succeeded", "已刷新"}
WAITING_STATUSES = {"", "未刷新", "待刷新", "waiting", "missing"}


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip()


def _first_text(*values: Any) -> str:
    for value in values:
        text = _to_text(value)
        if text:
            return text
    return ""


def _has_last_success(section: Mapping[str, Any]) -> bool:
    value = section.get("last_success")
    if isinstance(value, Mapping):
        return bool(value)
    return bool(_to_text(value))


def _is_today(value: Any) -> bool:
    text = _to_text(value)
    if not text:
        return False
    return text.startswith(datetime.date.today().isoformat())


def module_error_text(section: Any) -> str:
    payload = _as_mapping(section)
    direct = _first_text(payload.get("last_error"), payload.get("error"))
    if direct:
        return direct

    errors = payload.get("errors")
    if isinstance(errors, (list, tuple)):
        for item in errors:
            if isinstance(item, Mapping):
                text = _first_text(item.get("message"), item.get("error"), item.get("last_error"))
            else:
                text = _to_text(item)
            if text:
                return text
    elif errors:
        return _to_text(errors)
    return ""


def normalize_module_status(section: Any) -> str:
    payload = _as_mapping(section)
    if not payload:
        return "missing"

    refresh_label = _to_text(payload.get("refresh_label"))
    if refresh_label == "实时轻量":
        return "auto_light"
    if refresh_label == "今日已刷新":
        return "manual_basic_today"
    if refresh_label == "使用缓存":
        return "cached"
    if refresh_label == "需要深度刷新":
        return "needs_deep"

    raw_status = _to_text(payload.get("status"))
    if raw_status == "实时轻量":
        return "auto_light"
    if raw_status == "今日已刷新":
        return "manual_basic_today"
    if raw_status == "使用缓存":
        return "cached"
    if raw_status == "需要深度刷新":
        return "needs_deep"
    normalized_status = raw_status.lower()
    error_text = module_error_text(payload)
    has_last_success = _has_last_success(payload)
    is_stale = bool(payload.get("stale"))

    if normalized_status in FAILED_STATUSES or raw_status in FAILED_STATUSES:
        return "cached" if has_last_success or is_stale else "failed"
    if error_text and (has_last_success or is_stale):
        return "cached"
    if is_stale or has_last_success and raw_status in WAITING_STATUSES:
        return "cached"
    if raw_status in WAITING_STATUSES or normalized_status in WAITING_STATUSES:
        return "missing"

    refresh_level = _to_text(payload.get("refresh_level") or payload.get("refresh_tier"))
    if refresh_level in {"auto_light", "auto-light", "light"}:
        return "auto_light"
    if refresh_level in {"manual_basic", "manual-basic", "basic", "standard"}:
        return "manual_basic_today" if _is_today(payload.get("updated_at")) or not payload.get("updated_at") else "cached"
    if refresh_level in {"manual_deep", "manual-deep", "deep", "full"}:
        return "needs_deep"

    if raw_status in READY_STATUSES or normalized_status in READY_STATUSES or payload.get("is_fresh") is True:
        return "manual_basic_today" if _is_today(payload.get("updated_at")) else "auto_light"
    return "missing"


def module_status_label(section: Any) -> str:
    return {
        "missing": "未刷新",
        "auto_light": "实时轻量",
        "manual_basic_today": "今日已刷新",
        "cached": "使用缓存",
        "needs_deep": "需要深度刷新",
        "failed": "failed / error",
    }.get(normalize_module_status(section), "未刷新")


def module_status_tone(section: Any) -> str:
    return {
        "missing": "muted",
        "auto_light": "info",
        "manual_basic_today": "success",
        "cached": "warning",
        "needs_deep": "info",
        "failed": "danger",
    }.get(normalize_module_status(section), "muted")


def module_updated_text(section: Any) -> str:
    return _first_text(_as_mapping(section).get("updated_at"), "暂无")


def module_source_text(section: Any) -> str:
    return _first_text(_as_mapping(section).get("source"), "未加载")


def module_deepseek_text(section: Any) -> str:
    return "DeepSeek：已调用" if bool(_as_mapping(section).get("deepseek_called")) else "DeepSeek：未调用"


def _status_reason(status: str, error_text: str) -> str:
    if status == "missing":
        return "未刷新，请点击按钮生成。"
    if status == "auto_light":
        return "当前为页面允许的轻量快照，不包含 DeepSeek 或重型刷新。"
    if status == "manual_basic_today":
        return "今日基础数据已刷新，重型深度任务仍需手动触发。"
    if status == "cached":
        if error_text:
            return "当前展示为上次成功结果；最近一次刷新失败。"
        return "当前展示缓存或上次成功结果。"
    if status == "needs_deep":
        return "基础摘要可展示；深度解释或完整流程需要手动触发。"
    if status == "failed":
        return "刷新失败，暂无可用成功缓存。"
    return "状态待确认。"


def build_module_summary_view_model(section: Any, module_name: str | None = None) -> dict:
    payload = _as_mapping(section)
    status = normalize_module_status(payload)
    error_text = module_error_text(payload)
    updated_text = module_updated_text(payload)
    source_text = module_source_text(payload)
    deepseek_text = module_deepseek_text(payload)
    badge = module_status_label(payload)
    reason = _status_reason(status, error_text)
    caption = f"状态：{badge}｜最后刷新：{updated_text}｜来源：{source_text}｜{deepseek_text}"

    return {
        "module_name": module_name or _first_text(payload.get("module"), payload.get("module_key"), "模块"),
        "status": status,
        "label": badge,
        "badge": badge,
        "tone": module_status_tone(payload),
        "caption": caption,
        "reason": reason,
        "source_text": source_text,
        "updated_text": updated_text,
        "error_text": error_text,
        "is_stale": bool(payload.get("stale")) or status == "cached",
        "deepseek_text": deepseek_text,
        "empty_text": "未刷新，请点击按钮生成。",
    }


def build_all_module_summary_view_model(live_packet: Any) -> dict:
    payload = _as_mapping(live_packet)
    modules = {}
    for key, label in KNOWN_MODULES:
        modules[key] = build_module_summary_view_model(payload.get(key), module_name=label)
    return {"modules": modules}
