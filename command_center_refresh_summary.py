from __future__ import annotations

import datetime
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

USER_MODULE_LABELS = {
    "market": "市场环境",
    "市场": "市场环境",
    "市场环境": "市场环境",
    "quant": "量化摘要",
    "量化": "量化摘要",
    "量化推演": "量化摘要",
    "discipline": "纪律校验",
    "纪律": "纪律校验",
    "交易纪律": "纪律校验",
    "next_ticket": "下一票雷达",
    "下一票": "下一票雷达",
    "下一票雷达": "下一票雷达",
    "margin_etf": "ETF 配置",
    "融资 ETF": "ETF 配置",
    "etf": "ETF 配置",
    "yfinance 行情": "持仓行情",
    "AkShare 资金穿透": "资金数据",
    "Tushare / Supabase 体检": "数据能力体检",
}

USER_STATUS_LABELS = {
    "completed": "完成",
    "cached": "使用缓存",
    "empty": "无可执行结果",
    "skipped": "已跳过",
    "failed": "失败",
    "timeout": "超时",
    "waiting": "待刷新",
    "running": "正在刷新",
    "partial": "部分完成",
    "unknown": "待确认",
}

FULL_REFRESH_STEP_KEY_ALIASES = {
    "market": "market",
    "市场": "market",
    "市场环境": "market",
    "quant": "quant",
    "量化": "quant",
    "量化推演": "quant",
    "量化摘要": "quant",
    "discipline": "discipline",
    "纪律": "discipline",
    "交易纪律": "discipline",
    "纪律校验": "discipline",
    "next_ticket": "next_ticket",
    "下一票": "next_ticket",
    "下一票雷达": "next_ticket",
    "margin_etf": "etf",
    "etf": "etf",
    "ETF": "etf",
    "ETF 配置": "etf",
    "融资 ETF": "etf",
    "持仓行情": "holding",
    "yfinance 行情": "holding",
    "数据能力": "data_capability",
    "数据能力体检": "data_capability",
    "Tushare / Supabase 体检": "data_capability",
    "资金数据": "data_capability",
    "AkShare 资金穿透": "data_capability",
}

FULL_REFRESH_DECISION_KEYS = {
    "market",
    "holding",
    "quant",
    "discipline",
    "next_ticket",
    "etf",
    "data_capability",
}

INTERNAL_TEXT_REPLACEMENTS = (
    ("command_center_", ""),
    ("command_center", "综合中心"),
    ("capability registry", "能力状态"),
    ("Capability Registry", "能力状态"),
    ("provider capability", "数据能力"),
    ("Provider Capability", "数据能力"),
    ("provider", "数据源"),
    ("Provider", "数据源"),
    ("packet", "结构化结果"),
    ("Packet", "结构化结果"),
    ("registry", "能力状态"),
    ("Registry", "能力状态"),
    ("manual_basic", "标准刷新"),
)


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


def _to_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, Number):
        return float(value)
    text = _to_text(value)
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _clean_user_text(value: Any, default: str = "") -> str:
    text = _to_text(value) or default
    if not text:
        return ""
    for needle, replacement in INTERNAL_TEXT_REPLACEMENTS:
        text = text.replace(needle, replacement)
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip(" ｜")


def _format_duration_seconds(value: Any) -> str:
    if value is None or value == "":
        return "暂无"
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return "暂无"
    seconds = max(0.0, seconds)
    if seconds < 0.05:
        return "0.0s"
    return f"{seconds:.1f}s"


def _parse_time(value: Any) -> datetime.datetime | None:
    text = _to_text(value)
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _running_too_long(result: Mapping[str, Any], threshold_seconds: int = 90) -> bool:
    started_at = _parse_time(result.get("started_at"))
    if not started_at:
        return False
    now = datetime.datetime.now(started_at.tzinfo)
    return (now - started_at).total_seconds() > threshold_seconds


def user_refresh_status_label(status: Any, *, module_label: str = "") -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "empty" and "下一票" in module_label:
        return "无可执行候选"
    return USER_STATUS_LABELS.get(normalized, USER_STATUS_LABELS["unknown"])


def _module_user_label(result: Mapping[str, Any]) -> str:
    raw = _clean_user_text(
        result.get("name")
        or result.get("module")
        or result.get("module_name")
        or result.get("module_label")
        or result.get("step_name")
        or result.get("step_label")
        or result.get("module_key")
        or result.get("key")
        or result.get("source")
        or result.get("label")
    )
    if not raw:
        return "刷新步骤"
    lower = raw.lower()
    if "yfinance" in lower or "报价" in raw or "行情" in raw:
        return "持仓行情"
    if "akshare" in lower or "资金" in raw:
        return "资金数据"
    if "tushare" in lower and "supabase" in lower:
        return "数据能力体检"
    return USER_MODULE_LABELS.get(raw, USER_MODULE_LABELS.get(lower, raw))


def _full_refresh_step_key(result: Mapping[str, Any], module_label: str) -> str:
    raw = _to_text(
        result.get("key")
        or result.get("module_key")
        or result.get("module")
        or result.get("name")
        or result.get("source")
    )
    key = FULL_REFRESH_STEP_KEY_ALIASES.get(raw, FULL_REFRESH_STEP_KEY_ALIASES.get(raw.lower()))
    if key:
        return key
    label = module_label or _module_user_label(result)
    lowered = label.lower()
    if "yfinance" in lowered or "行情" in label or "报价" in label:
        return "holding"
    if "下一票" in label:
        return "next_ticket"
    if "etf" in lowered or "ETF" in label:
        return "etf"
    if "纪律" in label:
        return "discipline"
    if "量化" in label:
        return "quant"
    if "市场" in label:
        return "market"
    if "数据能力" in label or "体检" in label or "资金" in label or "tushare" in lowered or "akshare" in lowered:
        return "data_capability"
    return raw.lower() if raw else "unknown"


def _step_status_key(result: Mapping[str, Any], module_label: str = "") -> str:
    raw_status = str(result.get("status") or "").strip()
    normalized = raw_status.lower()
    message_text = _to_text(result.get("message") or result.get("summary"))
    ok_value = result.get("ok")

    if "timeout" in normalized or "超时" in raw_status:
        return "timeout"
    if normalized in {"empty", "no_candidates", "no_candidate", "no_actionable"}:
        return "empty"
    if normalized in FAILED_STATUSES or raw_status in FAILED_STATUSES or ok_value is False:
        return "failed"
    if result.get("stale") or normalized in {"cached", "stale", "cache"} or "使用缓存" in message_text:
        return "cached"
    if normalized in {"skipped", "skip", "跳过"}:
        return "skipped"
    if normalized in {"running", "刷新中", "in_progress"}:
        return "running"
    if normalized in {"waiting", "pending", "待刷新"}:
        return "waiting"
    if normalized in PARTIAL_STATUSES or raw_status in PARTIAL_STATUSES:
        return "partial"
    if ok_value is True or raw_status in READY_STATUSES or normalized in READY_STATUSES:
        return "completed"
    if result.get("finished_at") and not result.get("error") and not result.get("last_error"):
        return "completed"
    return "unknown"


def _step_user_message(result: Mapping[str, Any], module_label: str, status_key: str) -> str:
    raw_error = _clean_user_text(result.get("error") or result.get("last_error"))
    raw_message = _clean_user_text(result.get("message") or result.get("summary"))
    has_last_success = bool(result.get("last_success") or result.get("stale"))

    if status_key == "timeout":
        if "下一票" in module_label:
            return "下一票雷达超时，已保留上次结果。"
        return f"{module_label}超时，已保留上次结果。"
    if status_key == "failed":
        if has_last_success:
            return f"{module_label}失败，已保留上次成功结果。"
        if raw_error:
            return f"{module_label}失败：{raw_error}"
        return f"{module_label}失败，失败原因待确认。"
    if status_key == "cached":
        return f"{module_label}使用缓存，未重新拉取。"
    if status_key == "empty":
        if "下一票" in module_label:
            return "本轮轻量雷达未产生可执行候选。"
        return f"{module_label}没有生成可执行结果。"
    if status_key == "skipped":
        return raw_message or f"{module_label}已跳过；不影响后续步骤继续执行。"
    if status_key == "running":
        if _running_too_long(result):
            return "可能仍在运行；如持续不动，请重新刷新。"
        return f"{module_label}正在刷新。"
    if status_key == "completed":
        return raw_message or f"{module_label}完成。"
    if status_key == "partial":
        return raw_message or f"{module_label}部分完成，当前继续使用可用结果。"
    return raw_message or f"{module_label}待刷新。"


def _build_user_refresh_step_item(result: Any) -> dict:
    payload = as_mapping(result)
    module_label = _module_user_label(payload)
    status_key = _step_status_key(payload, module_label)
    return {
        "label": module_label,
        "status": status_key,
        "status_label": user_refresh_status_label(status_key, module_label=module_label),
        "duration": _format_duration_seconds(payload.get("duration_seconds")),
        "message": _step_user_message(payload, module_label, status_key),
        "started_at": _to_text(payload.get("started_at")),
        "finished_at": _to_text(payload.get("finished_at") or payload.get("updated_at")),
    }


def _build_full_refresh_step_item(result: Any) -> dict | None:
    payload = as_mapping(result)
    if not payload:
        return None
    module_label = _module_user_label(payload)
    key = _full_refresh_step_key(payload, module_label)
    if key == "deepseek":
        return None
    status_key = _step_status_key(payload, module_label)
    error_text = _clean_user_text(payload.get("error") or payload.get("last_error"))
    return {
        "name": module_label,
        "key": key,
        "status": status_key,
        "label": user_refresh_status_label(status_key, module_label=module_label),
        "started_at": _to_text(payload.get("started_at")),
        "finished_at": _to_text(payload.get("finished_at") or payload.get("updated_at")),
        "duration_seconds": round(max(0.0, _to_float(payload.get("duration_seconds"))), 3),
        "message": _step_user_message(payload, module_label, status_key),
        "error": error_text or None,
        "affects_decision": key in FULL_REFRESH_DECISION_KEYS,
    }


def build_full_refresh_steps(refresh_result: Any = None, live_packet: Any = None) -> list[dict]:
    del live_packet
    payload = as_mapping(refresh_result)
    raw_steps = payload.get("full_refresh_steps")
    if not isinstance(raw_steps, (list, tuple)):
        raw_steps = payload.get("steps")
    if not isinstance(raw_steps, (list, tuple)):
        raw_steps = payload.get("results")
    if not isinstance(raw_steps, (list, tuple)):
        raw_steps = []

    steps: list[dict] = []
    for raw in raw_steps:
        step = _build_full_refresh_step_item(raw)
        if step is not None:
            steps.append(step)
    return clone_packet({"steps": steps}).get("steps", [])


def _status_group_count(groups: Mapping[str, Any], key: str) -> int:
    value = groups.get(key)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return _to_int(value)


def _status_group_labels(groups: Mapping[str, Any], key: str) -> list[str]:
    value = groups.get(key)
    if not isinstance(value, (list, tuple, set)):
        return []
    return [_clean_user_text(item) for item in value if _clean_user_text(item)]


def _capability_category_status(groups: Mapping[str, Any], keywords: tuple[str, ...], missing_label: str = "未刷新") -> str:
    order = (
        ("failed", "失败"),
        ("no_permission", "权限不足"),
        ("cached", "使用缓存"),
        ("no_data", "无数据"),
        ("available", "已可用"),
        ("skipped", "未刷新"),
        ("unknown", missing_label),
    )
    for group_key, label in order:
        for item in _status_group_labels(groups, group_key):
            lowered = item.lower()
            if any(keyword.lower() in lowered or keyword in item for keyword in keywords):
                return label
    return missing_label


def build_user_data_capability_summary(refresh_result: Any = None) -> dict:
    payload = as_mapping(refresh_result)
    groups = as_mapping(payload.get("data_capability_status_groups"))
    counts = {
        "available": _status_group_count(groups, "available"),
        "failed": _status_group_count(groups, "failed"),
        "no_permission": _status_group_count(groups, "no_permission"),
        "cached": _status_group_count(groups, "cached"),
        "no_data": _status_group_count(groups, "no_data"),
        "skipped": _status_group_count(groups, "skipped"),
        "unknown": _status_group_count(groups, "unknown"),
    }
    issue_count = counts["failed"] + counts["no_permission"] + counts["no_data"]
    soft_issue_count = counts["cached"] + counts["skipped"] + counts["unknown"]
    if issue_count >= 2 or counts["failed"]:
        impact = "高"
    elif issue_count or soft_issue_count:
        impact = "中"
    else:
        impact = "低"
    return {
        "line": (
            f"数据能力：可用 {counts['available']} / 失败 {counts['failed']} / "
            f"权限不足 {counts['no_permission']} / 使用缓存 {counts['cached']}"
        ),
        "counts": counts,
        "impact": impact,
        "items": [
            {"label": "行情数据", "status": _capability_category_status(groups, ("行情", "quote", "price", "yfinance"))},
            {"label": "资金数据", "status": _capability_category_status(groups, ("资金", "money", "龙虎榜", "融资融券", "margin", "dragon"))},
            {"label": "ETF 数据", "status": _capability_category_status(groups, ("ETF", "etf"), missing_label="无数据")},
            {"label": "云端记忆", "status": _capability_category_status(groups, ("Supabase", "云端", "记忆", "历史", "brain"))},
        ],
    }


def build_user_refresh_summary(refresh_result: Any = None, live_packet: Any = None) -> dict:
    del live_packet
    payload = as_mapping(refresh_result)
    raw_results = payload.get("full_refresh_steps")
    if not isinstance(raw_results, (list, tuple)):
        raw_results = payload.get("results")
    if not isinstance(raw_results, (list, tuple)):
        raw_results = []
    step_items = [_build_user_refresh_step_item(result) for result in raw_results]
    counts = {
        "completed": sum(1 for item in step_items if item["status"] == "completed"),
        "cached": sum(1 for item in step_items if item["status"] == "cached"),
        "failed": sum(1 for item in step_items if item["status"] == "failed"),
        "timeout": sum(1 for item in step_items if item["status"] == "timeout"),
        "empty": sum(1 for item in step_items if item["status"] == "empty"),
        "skipped": sum(1 for item in step_items if item["status"] == "skipped"),
        "running": sum(1 for item in step_items if item["status"] == "running"),
    }
    if not step_items:
        headline = "暂无满血数据刷新结果。"
    else:
        parts = [f"{counts['completed']} 完成"]
        if counts["cached"]:
            parts.append(f"{counts['cached']} 使用缓存")
        if counts["empty"]:
            parts.append(f"{counts['empty']} 无可执行结果")
        if counts["skipped"]:
            parts.append(f"{counts['skipped']} 跳过")
        if counts["timeout"]:
            parts.append(f"{counts['timeout']} 超时")
        if counts["failed"]:
            parts.append(f"{counts['failed']} 失败")
        if counts["running"]:
            parts.append(f"{counts['running']} 正在刷新")
        headline = "满血数据刷新结果：" + " / ".join(parts)

    data_summary = build_user_data_capability_summary(payload)
    deepseek_called = bool(payload.get("deepseek_called"))
    deepseek_line = "DeepSeek：已解释" if deepseek_called else "DeepSeek：未调用"
    display_lines = [headline, data_summary["line"], deepseek_line, f"对当前结论影响：{data_summary['impact']}"]
    return clone_packet(
        {
            "has_refresh": bool(step_items or payload),
            "headline": _clean_user_text(headline),
            "step_items": step_items,
            "detail_items": step_items,
            "data_capability": data_summary,
            "deepseek": {"status": "已解释" if deepseek_called else "未调用", "line": deepseek_line},
            "display_lines": [_clean_user_text(line) for line in display_lines],
            "updated_at": _to_text(payload.get("finished_at") or payload.get("updated_at")),
        }
    )


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


def summarize_recovery_result_notice(recovery_result_notice: Any = None) -> dict:
    payload = as_mapping(recovery_result_notice)
    if not payload:
        return {}
    return {
        "status": _to_text(payload.get("status")) or "waiting",
        "tone": _to_text(payload.get("tone")) or "missing",
        "title": _to_text(payload.get("title")) or "最近恢复结果",
        "label": _to_text(payload.get("label")) or "数据能力",
        "message": _to_text(payload.get("message")) or "",
        "next_action": _to_text(payload.get("next_action")) or "",
        "writes_packet": _to_text(payload.get("writes_packet")) or "",
        "updated_at": _to_text(payload.get("updated_at")) or "",
        "source": _to_text(payload.get("source")) or "",
        "source_type": _to_text(payload.get("source_type")) or "",
        "external_call_policy": _to_text(payload.get("external_call_policy")) or "not_triggered",
        "deepseek_called": bool(payload.get("deepseek_called")) if "deepseek_called" in payload else False,
    }


def build_refresh_summary_view_model(
    live_packet: Any = None,
    refresh_result: Any = None,
    refresh_level: Any = None,
    generated_at: Any = None,
    a_share_fact_recovery_summary: Any = None,
    latest_recovery_result_notice: Any = None,
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
    latest_recovery_result = summarize_recovery_result_notice(latest_recovery_result_notice)
    user_summary = build_user_refresh_summary(refresh_result, live_payload)
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
        "latest_recovery_result_notice": latest_recovery_result,
        "latest_recovery_result_summary": (
            f"{latest_recovery_result.get('title')}｜{latest_recovery_result.get('message')}"
            if latest_recovery_result
            else ""
        ),
        "has_latest_recovery_result": bool(latest_recovery_result),
        "user_summary": user_summary,
    }
    return clone_packet(view_model)
