from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_adapter import as_mapping, clone_packet, get_nested


MAX_ERRORS = 8
MAX_SUMMARY_ERRORS = 5

REFRESH_LEVEL_ALIASES = {
    "light": "light",
    "auto_light": "light",
    "auto-light": "light",
    "轻量": "light",
    "轻量刷新": "light",
    "实时轻量": "light",
    "standard": "standard",
    "manual_basic": "standard",
    "manual-basic": "standard",
    "basic": "standard",
    "标准": "standard",
    "标准刷新": "standard",
    "今日已刷新": "standard",
    "full": "full",
    "manual_deep": "full",
    "manual-deep": "full",
    "deep": "full",
    "完整": "full",
    "完整刷新": "full",
    "深度刷新": "full",
}

REFRESH_LEVEL_LABELS = {
    "light": "轻量刷新",
    "standard": "标准刷新",
    "full": "完整刷新",
    "unknown": "未知刷新级别",
}

MODULE_LABELS = {
    "market": "市场",
    "quant": "量化",
    "discipline": "纪律",
    "margin_etf": "融资 ETF",
    "etf": "ETF",
    "next_ticket": "下一票",
    "strategy_execution": "策略执行",
    "decision": "今日总决策",
}

KNOWN_MODULE_ORDER = (
    "market",
    "quant",
    "discipline",
    "margin_etf",
    "etf",
    "next_ticket",
    "strategy_execution",
    "decision",
)

NON_MODULE_KEYS = {
    "errors",
    "conclusion",
    "refresh_level",
    "updated_at",
    "generated_at",
    "finished_at",
    "deepseek_called",
    "summary",
    "status",
}

READY_STATUSES = {"ok", "ready", "completed", "complete", "已刷新", "success", "succeeded"}
FAILED_STATUSES = {"failed", "failure", "失败", "error"}
PARTIAL_STATUSES = {"partial", "partial_failed", "部分刷新", "部分失败"}


def normalize_refresh_level(refresh_level: Any) -> str:
    if refresh_level is None:
        return "unknown"
    raw = str(refresh_level).strip()
    if not raw:
        return "unknown"
    return REFRESH_LEVEL_ALIASES.get(raw.lower(), REFRESH_LEVEL_ALIASES.get(raw, "unknown"))


def refresh_level_label(refresh_level: Any) -> str:
    return REFRESH_LEVEL_LABELS.get(normalize_refresh_level(refresh_level), REFRESH_LEVEL_LABELS["unknown"])


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (bool, Number)):
        return str(value)
    if isinstance(value, Mapping):
        for key in ("message", "error", "last_error", "summary", "updated_at", "finished_at"):
            text = _to_text(value.get(key))
            if text:
                module = _to_text(value.get("module"))
                if module and key in {"message", "error", "last_error"} and module not in text:
                    return f"{module}: {text}"
                return text
        return ""
    return str(value).strip()


def _append_error(errors: list[str], seen: set[str], value: Any, max_errors: int) -> None:
    if len(errors) >= max_errors:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _append_error(errors, seen, item, max_errors)
            if len(errors) >= max_errors:
                break
        return
    text = _to_text(value)
    if text and text not in seen:
        seen.add(text)
        errors.append(text)


def extract_refresh_errors(*packets_or_results: Any, max_errors: int = MAX_ERRORS) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    for item in packets_or_results:
        if len(errors) >= max_errors:
            break
        if isinstance(item, (list, tuple, set)):
            _append_error(errors, seen, item, max_errors)
            continue
        payload = as_mapping(item)
        if not payload:
            continue
        _append_error(errors, seen, payload.get("errors"), max_errors)
        _append_error(errors, seen, payload.get("last_error"), max_errors)
        _append_error(errors, seen, payload.get("error"), max_errors)

    return errors[:max_errors]


def _last_success_text(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("last_success")
    if isinstance(value, Mapping):
        text = _to_text(
            value.get("updated_at")
            or value.get("finished_at")
            or value.get("generated_at")
            or value.get("summary")
        )
    else:
        text = _to_text(value)
    return text or None


def _last_error_text(payload: Mapping[str, Any], errors: list[str] | None = None) -> str | None:
    text = _to_text(payload.get("last_error") or payload.get("error"))
    if text:
        return text
    if errors:
        return errors[0]
    return None


def _result_status(result: Mapping[str, Any], live_packet: Mapping[str, Any], errors: list[str], stale: bool) -> str:
    raw_status = str(result.get("status") or live_packet.get("status") or "").strip()
    normalized = raw_status.lower()
    ok_value = result.get("ok")

    if errors:
        if ok_value is False or normalized in FAILED_STATUSES:
            return "failed"
        return "partial"
    if ok_value is True or raw_status in READY_STATUSES or normalized in READY_STATUSES:
        return "ok"
    if stale or normalized in PARTIAL_STATUSES or raw_status in PARTIAL_STATUSES:
        return "partial"
    if ok_value is False or normalized in FAILED_STATUSES or raw_status in FAILED_STATUSES:
        return "failed"
    return "unknown"


def summarize_refresh_result(result: Any = None, live_packet: Any = None) -> dict:
    result_payload = as_mapping(result)
    live_payload = as_mapping(live_packet)
    errors = extract_refresh_errors(result_payload, live_payload, max_errors=MAX_SUMMARY_ERRORS)
    stale = bool(result_payload.get("stale") or live_payload.get("stale"))
    status = _result_status(result_payload, live_payload, errors, stale)
    label = {
        "ok": "刷新完成",
        "partial": "部分刷新",
        "failed": "刷新失败",
        "unknown": "暂无刷新结果",
    }[status]
    message = (
        _to_text(result_payload.get("message"))
        or _to_text(result_payload.get("summary"))
        or _to_text(get_nested(live_payload, "conclusion.summary"))
        or label
    )

    return {
        "ok": status == "ok",
        "status": status,
        "label": label,
        "message": message,
        "stale": stale,
        "error_count": len(errors),
        "errors": errors,
        "last_success": _last_success_text(result_payload) or _last_success_text(live_payload),
        "last_error": _last_error_text(result_payload, errors) or _last_error_text(live_payload, errors),
    }


def _module_status(section: Mapping[str, Any], errors: list[str]) -> str:
    raw_status = str(section.get("status") or "").strip()
    normalized = raw_status.lower()
    if errors:
        return "failed"
    if section.get("stale"):
        return "stale"
    if section.get("is_fresh") is True or raw_status in READY_STATUSES or normalized in READY_STATUSES:
        return "ok"
    if normalized in FAILED_STATUSES or raw_status in FAILED_STATUSES:
        return "failed"
    return "unknown"


def _module_keys(live_payload: Mapping[str, Any]) -> list[str]:
    keys = [key for key in KNOWN_MODULE_ORDER if key in live_payload]
    for key, value in live_payload.items():
        if key in keys or key in NON_MODULE_KEYS or not isinstance(value, Mapping):
            continue
        keys.append(str(key))
    return keys


def summarize_module_refresh_statuses(live_packet: Any = None) -> list[dict]:
    live_payload = as_mapping(live_packet)
    statuses: list[dict] = []
    for key in _module_keys(live_payload):
        section = as_mapping(live_payload.get(key))
        errors = extract_refresh_errors(section, max_errors=MAX_SUMMARY_ERRORS)
        last_error = _last_error_text(section, errors)
        statuses.append(
            {
                "key": key,
                "label": MODULE_LABELS.get(key, key),
                "status": _module_status(section, errors),
                "stale": bool(section.get("stale")),
                "last_success": _last_success_text(section),
                "last_error": last_error,
                "error": last_error,
            }
        )
    return statuses


def build_refresh_summary_view_model(
    live_packet: Any = None,
    refresh_result: Any = None,
    refresh_level: Any = None,
    generated_at: Any = None,
) -> dict:
    live_payload = as_mapping(live_packet)
    level = normalize_refresh_level(
        refresh_level
        or get_nested(refresh_result, "refresh_level")
        or live_payload.get("refresh_level")
    )
    summary = summarize_refresh_result(refresh_result, live_payload)
    module_statuses = summarize_module_refresh_statuses(live_payload)
    module_errors = [
        item.get("error")
        for item in module_statuses
        if item.get("error")
    ]
    errors = extract_refresh_errors(
        {"errors": summary.get("errors") or []},
        {"errors": module_errors},
        max_errors=MAX_ERRORS,
    )
    view_model = {
        "refresh_level": level,
        "refresh_level_label": refresh_level_label(level),
        "generated_at": _to_text(
            generated_at
            or get_nested(refresh_result, "finished_at")
            or get_nested(refresh_result, "updated_at")
            or live_payload.get("updated_at")
            or live_payload.get("generated_at")
        ) or None,
        "summary": summary,
        "module_statuses": module_statuses,
        "errors": errors,
        "has_errors": bool(errors),
        "has_stale": bool(summary.get("stale") or any(item.get("stale") for item in module_statuses)),
    }
    return clone_packet(view_model)
