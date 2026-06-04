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


def _to_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Number):
        return int(value)
    text = _to_text(value)
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


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


def extract_completed_modules(refresh_result: Any = None) -> list[str]:
    payload = as_mapping(refresh_result)
    results = payload.get("results") or []
    if not isinstance(results, (list, tuple)):
        return []

    completed: list[str] = []
    seen: set[str] = set()
    for item in results:
        result = as_mapping(item)
        if result.get("ok") is not True:
            continue
        module = _to_text(
            result.get("module")
            or result.get("label")
            or result.get("module_key")
            or result.get("key")
            or result.get("source")
        )
        if module and module not in seen:
            seen.add(module)
            completed.append(module)
    return completed


def _error_message(value: Any) -> str:
    payload = as_mapping(value)
    if payload:
        return _to_text(
            payload.get("message")
            or payload.get("error")
            or payload.get("last_error")
            or payload.get("summary")
        )
    return _to_text(value)


def _error_item(value: Any, parent: Any = None) -> dict | None:
    payload = as_mapping(value)
    parent_payload = as_mapping(parent)
    if not payload and not isinstance(value, (str, bool, Number)):
        return None
    message = _error_message(payload or value)
    if not message:
        return None

    module = _to_text(
        payload.get("module")
        or payload.get("module_key")
        or payload.get("key")
        or parent_payload.get("module")
        or parent_payload.get("module_key")
        or parent_payload.get("key")
    )
    updated_at = _to_text(
        payload.get("updated_at")
        or payload.get("finished_at")
        or parent_payload.get("updated_at")
        or parent_payload.get("finished_at")
    )
    source = _to_text(
        payload.get("source")
        or parent_payload.get("source")
        or module
    )
    return {
        "module": module,
        "message": message,
        "updated_at": updated_at,
        "source": source,
    }


def _append_error_item(
    items: list[dict],
    seen: set[tuple[str, str, str, str]],
    value: Any,
    parent: Any,
    max_errors: int,
) -> None:
    if len(items) >= max_errors:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _append_error_item(items, seen, item, parent, max_errors)
            if len(items) >= max_errors:
                break
        return

    payload = as_mapping(value)
    if payload and "errors" in payload:
        _append_error_item(items, seen, payload.get("errors"), payload, max_errors)

    if payload:
        raw_status = str(payload.get("status") or "").strip().lower()
        message_is_error = parent is not None or payload.get("ok") is False or raw_status in FAILED_STATUSES
        keys = ("last_error", "error", "message") if message_is_error else ("last_error", "error")
        for key in keys:
            if payload.get(key):
                item = _error_item(payload, parent)
                break
        else:
            item = None
    else:
        item = _error_item(value, parent)

    if not item:
        return
    dedupe_key = (
        item.get("module") or "",
        item.get("message") or "",
        item.get("updated_at") or "",
        item.get("source") or "",
    )
    if dedupe_key not in seen and item.get("message"):
        seen.add(dedupe_key)
        items.append(item)


def extract_refresh_error_items(*packets_or_results: Any, max_errors: int = MAX_ERRORS) -> list[dict]:
    items: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()

    for value in packets_or_results:
        if len(items) >= max_errors:
            break
        _append_error_item(items, seen, value, None, max_errors)

    return clone_packet({"items": items}).get("items", [])


def extract_refresh_errors(*packets_or_results: Any, max_errors: int = MAX_ERRORS) -> list[str]:
    error_items = extract_refresh_error_items(*packets_or_results, max_errors=max_errors)
    if error_items:
        errors: list[str] = []
        seen: set[str] = set()
        for item in error_items:
            module = _to_text(item.get("module"))
            message = _to_text(item.get("message"))
            text = f"{module}: {message}" if module and module not in message else message
            if text and text not in seen:
                seen.add(text)
                errors.append(text)
            if len(errors) >= max_errors:
                break
        return errors[:max_errors]

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
    error_items = extract_refresh_error_items(result_payload, live_payload, max_errors=MAX_SUMMARY_ERRORS)
    errors = extract_refresh_errors(error_items, max_errors=MAX_SUMMARY_ERRORS)
    completed_modules = extract_completed_modules(result_payload)
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
        "error_items": error_items,
        "completed_modules": completed_modules,
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
                "updated_at": _to_text(section.get("updated_at")) or None,
                "source": _to_text(section.get("source")) or None,
                "last_success": _last_success_text(section),
                "last_error": last_error,
                "error": last_error,
            }
        )
    return statuses


def summarize_a_share_fact_recovery(recovery_summary: Any = None) -> dict:
    payload = as_mapping(recovery_summary)
    raw_items = payload.get("items")
    items: list[dict] = []
    if isinstance(raw_items, (list, tuple)):
        for raw_item in raw_items[:MAX_ERRORS]:
            item = as_mapping(raw_item)
            if not item:
                continue
            items.append(
                {
                    "key": _to_text(item.get("key")) or "",
                    "label": _to_text(item.get("label")) or _to_text(item.get("key")) or "A股事实",
                    "recovery_state": _to_text(item.get("recovery_state")) or "waiting",
                    "status_label": _to_text(item.get("status_label")) or "待验证",
                    "capability_state": _to_text(item.get("capability_state")) or "",
                    "packet_status_text": _to_text(item.get("packet_status_text")) or "",
                    "writes_packet": _to_text(item.get("writes_packet")) or "",
                    "action_label": _to_text(item.get("action_label")) or "",
                    "next_action": _to_text(item.get("next_action")) or "",
                    "diagnostic_answer": _to_text(item.get("diagnostic_answer")) or "",
                    "source": _to_text(item.get("source")) or "",
                    "updated_at": _to_text(item.get("updated_at")) or "",
                    "toolbox_entry": _to_text(item.get("toolbox_entry")) or "",
                    "workspace_target": _to_text(item.get("workspace_target")) or "",
                    "workspace_state_key": _to_text(item.get("workspace_state_key")) or "",
                    "legacy_tab": _to_text(item.get("legacy_tab")) or "",
                    "legacy_tab_state_key": _to_text(item.get("legacy_tab_state_key")) or "",
                    "navigation_label": _to_text(item.get("navigation_label")) or "",
                    "refresh_policy": _to_text(item.get("refresh_policy")) or "button_gated",
                    "source_label": _to_text(item.get("source_label")) or "",
                }
            )

    recovered_count = _to_int(payload.get("recovered_count"))
    blocked_count = _to_int(payload.get("blocked_count"))
    waiting_count = _to_int(payload.get("waiting_count"))
    if items and not any((recovered_count, blocked_count, waiting_count)):
        recovered_count = sum(1 for item in items if item.get("recovery_state") == "recovered")
        blocked_count = sum(1 for item in items if item.get("recovery_state") == "blocked")
        waiting_count = sum(1 for item in items if item.get("recovery_state") not in {"recovered", "blocked"})
    total_count = _to_int(payload.get("total_count"), len(items) or 0)
    summary_text = _to_text(payload.get("summary"))
    if not summary_text and total_count:
        summary_text = f"A股事实 {total_count} 项：已回流 {recovered_count}｜仍受限 {blocked_count}｜待验证 {waiting_count}"

    return {
        "title": _to_text(payload.get("title")) or "A股事实回流",
        "summary": summary_text,
        "tone": _to_text(payload.get("tone")) or ("failed" if blocked_count else "missing"),
        "recovered_count": recovered_count,
        "blocked_count": blocked_count,
        "waiting_count": waiting_count,
        "total_count": total_count,
        "items": items,
        "next_action": _to_text(payload.get("next_action")) or "",
        "safe_mode_text": _to_text(payload.get("safe_mode_text")) or "这里只汇总本地 packet 状态；不会自动调用外部接口。",
        "deepseek_called": bool(payload.get("deepseek_called")) if "deepseek_called" in payload else False,
    }


def build_refresh_summary_view_model(
    live_packet: Any = None,
    refresh_result: Any = None,
    refresh_level: Any = None,
    generated_at: Any = None,
    a_share_fact_recovery_summary: Any = None,
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
    module_error_items = [
        {
            "module": item.get("label") or item.get("key") or "",
            "message": item.get("error") or "",
            "updated_at": item.get("updated_at") or "",
            "source": item.get("source") or item.get("label") or "",
        }
        for item in module_statuses
        if item.get("error")
    ]
    error_items = extract_refresh_error_items(
        {"errors": summary.get("error_items") or []},
        {"errors": module_error_items},
        max_errors=MAX_ERRORS,
    )
    errors = extract_refresh_errors(
        {"errors": error_items or summary.get("errors") or []},
        {"errors": module_errors},
        max_errors=MAX_ERRORS,
    )
    a_share_fact_recovery = summarize_a_share_fact_recovery(a_share_fact_recovery_summary)
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
        "completed_modules": summary.get("completed_modules") or [],
        "error_items": error_items,
        "errors": errors,
        "has_errors": bool(errors),
        "has_stale": bool(summary.get("stale") or any(item.get("stale") for item in module_statuses)),
        "a_share_fact_recovery": a_share_fact_recovery,
        "a_share_fact_recovery_summary": a_share_fact_recovery.get("summary") or "",
        "a_share_fact_recovery_tone": a_share_fact_recovery.get("tone") or "missing",
        "a_share_fact_recovery_items": a_share_fact_recovery.get("items") or [],
        "has_a_share_fact_blockers": bool(a_share_fact_recovery.get("blocked_count")),
        "has_a_share_fact_waiting": bool(a_share_fact_recovery.get("waiting_count")),
    }
    return clone_packet(view_model)
