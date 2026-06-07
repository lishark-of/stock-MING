"""Safety and aggregation helpers for Command Center 2.0.

This module deliberately has no Streamlit dependency.  The Streamlit page owns
UI rendering and legacy adapters; this service owns the refresh contract:
every module refresh is manual, DeepSeek is never called here, failures are
captured, and the last successful payload is preserved.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Callable, MutableMapping
from typing import Any


COMMAND_CENTER_MODULE_META_KEY = "command_center_module_refresh_meta"
COMMAND_CENTER_MODULE_STATE_KEY = "command_center_module_state"

REFRESH_LEVEL_AUTO_LIGHT = "auto_light"
REFRESH_LEVEL_MANUAL_BASIC = "manual_basic"
REFRESH_LEVEL_MANUAL_DEEP = "manual_deep"

MODULE_NAMES = {
    "market": "市场环境",
    "quant": "量化推演",
    "discipline": "交易纪律",
    "next_ticket": "下一票雷达",
    "margin_etf": "融资 ETF",
}


def _module_label(module_key: str) -> str:
    return MODULE_NAMES.get(module_key, module_key)


def command_center_now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def clone_packet(packet: Any) -> Any:
    payload = {} if packet is None else packet
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


def _ensure_dict_state(state: MutableMapping[str, Any], key: str) -> dict[str, Any]:
    value = state.get(key)
    if not isinstance(value, dict):
        value = {}
        state[key] = value
    return value


def module_meta(state: MutableMapping[str, Any]) -> dict[str, Any]:
    return _ensure_dict_state(state, COMMAND_CENTER_MODULE_META_KEY)


def module_state(state: MutableMapping[str, Any]) -> dict[str, Any]:
    return _ensure_dict_state(state, COMMAND_CENTER_MODULE_STATE_KEY)


def mark_module(
    state: MutableMapping[str, Any],
    module_key: str,
    status: str,
    source: str,
    error: str | Exception = "",
) -> dict[str, Any]:
    meta = module_meta(state)
    previous = meta.get(module_key) or {}
    payload = {
        **previous,
        "status": status,
        "updated_at": command_center_now(),
        "source": source,
        "error": str(error or ""),
        "deepseek": "未调用",
    }
    meta[module_key] = payload
    state[COMMAND_CENTER_MODULE_META_KEY] = meta
    return clone_packet(payload)


def get_module_meta(state: MutableMapping[str, Any], module_key: str) -> dict[str, Any]:
    return clone_packet(module_meta(state).get(module_key) or {})


def get_module_record(state: MutableMapping[str, Any], module_key: str) -> dict[str, Any]:
    return clone_packet(module_state(state).get(module_key) or {})


def _summary_from_result(result: dict[str, Any], label: str) -> str:
    for key in ("summary", "message", "status"):
        value = result.get(key)
        if value:
            return str(value)
    return f"{label}刷新完成"


def _is_today(value: Any, today: datetime.date | None = None) -> bool:
    if not value:
        return False
    today = today or datetime.datetime.now().date()
    text = str(value)
    try:
        return datetime.datetime.fromisoformat(text).date() == today
    except ValueError:
        try:
            return datetime.date.fromisoformat(text[:10]) == today
        except ValueError:
            return False


def get_refresh_label(section: dict[str, Any] | None) -> str:
    payload = section or {}
    status = str(payload.get("status") or "").lower()
    refresh_level = payload.get("refresh_level") or payload.get("refresh_tier") or ""
    has_last_success = bool(payload.get("last_success"))
    updated_today = _is_today(payload.get("updated_at"))

    if status in {"failed", "failure", "失败"} and has_last_success:
        return "使用缓存"
    if payload.get("needs_deep_refresh") or refresh_level == REFRESH_LEVEL_MANUAL_DEEP:
        return "需要深度刷新"
    if not payload.get("is_fresh") and not has_last_success and not payload.get("updated_at"):
        return "需要深度刷新"
    if refresh_level == REFRESH_LEVEL_AUTO_LIGHT and not payload.get("stale"):
        return "实时轻量"
    if refresh_level == REFRESH_LEVEL_MANUAL_BASIC and updated_today:
        return "今日已刷新"
    if has_last_success:
        return "使用缓存"
    return "需要深度刷新"


def _success_record(
    *,
    module_key: str,
    label: str,
    result: dict[str, Any],
    started_at: str,
    finished_at: str,
    refresh_level: str = REFRESH_LEVEL_MANUAL_BASIC,
) -> dict[str, Any]:
    payload = clone_packet(result)
    payload["refresh_level"] = payload.get("refresh_level") or refresh_level
    updated_at = str(payload.get("updated_at") or payload.get("generated_at") or finished_at)
    finished_at = str(payload.get("finished_at") or finished_at)
    duration_seconds = payload.get("duration_seconds")
    if duration_seconds is None:
        duration_seconds = _duration_seconds(started_at, finished_at)
    source = str(payload.get("source") or label)
    summary = _summary_from_result(payload, label)
    last_success = {
        "module_key": module_key,
        "module": label,
        "status": payload.get("status") or "ok",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "updated_at": updated_at,
        "source": source,
        "summary": summary,
        "data": payload,
        "refresh_level": payload["refresh_level"],
        "deepseek_called": False,
    }
    return {
        "module_key": module_key,
        "module": label,
        "ok": True,
        "status": payload.get("status") or "ok",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "message": payload.get("message") or payload.get("summary") or summary,
        "updated_at": updated_at,
        "source": source,
        "summary": summary,
        "data": payload,
        "last_success": last_success,
        "last_error": "",
        "stale": False,
        "deepseek_called": False,
        "refresh_level": payload["refresh_level"],
        "refresh_tier": payload.get("refresh_tier") or payload["refresh_level"],
    }


def _error_entry_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    message = record.get("last_error") or record.get("error") or ""
    if not message:
        return None
    return {
        "module": record.get("module") or _module_label(str(record.get("module_key") or "")),
        "message": str(message),
        "updated_at": record.get("updated_at") or command_center_now(),
        "source": record.get("source") or record.get("module") or "未加载",
    }


def collect_errors(
    state: MutableMapping[str, Any],
    module_keys: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    records = module_state(state)
    keys = list(module_keys or MODULE_NAMES.keys())
    errors = []
    for key in keys:
        record = records.get(key) or {}
        entry = _error_entry_from_record(record)
        if entry:
            errors.append(entry)
    return clone_packet(errors)


def _normalize_module_section(
    state: MutableMapping[str, Any],
    module_key: str,
    section: dict[str, Any] | None,
    default_refresh_level: str = REFRESH_LEVEL_AUTO_LIGHT,
) -> dict[str, Any]:
    raw_section = clone_packet(section or {})
    record = get_module_record(state, module_key)
    label = _module_label(module_key)
    last_success = record.get("last_success") or raw_section.get("last_success") or {}
    last_success_data = last_success.get("data") if isinstance(last_success, dict) else {}
    use_last_success = bool(record.get("last_error") and last_success and not raw_section.get("is_fresh"))
    last_error = record.get("last_error") or raw_section.get("last_error") or ""
    refresh_level = (
        raw_section.get("refresh_level")
        or record.get("refresh_level")
        or (last_success or {}).get("refresh_level")
        or default_refresh_level
    )
    normalized = {
        **raw_section,
        "status": (
            "使用缓存"
            if use_last_success
            else raw_section.get("status") or record.get("status") or "未刷新"
        ),
        "updated_at": (
            (last_success or {}).get("updated_at")
            if use_last_success
            else raw_section.get("updated_at") or record.get("updated_at") or ""
        ),
        "source": (
            (last_success or {}).get("source")
            if use_last_success
            else raw_section.get("source") or record.get("source") or "未加载"
        ),
        "summary": (
            (last_success or {}).get("summary")
            if use_last_success
            else raw_section.get("summary") or record.get("summary") or f"{label}待刷新。"
        ),
        "data": raw_section.get("data") or record.get("data") or last_success_data or raw_section,
        "last_success": last_success,
        "last_error": str(last_error or ""),
        "stale": bool(record.get("stale") or raw_section.get("stale")),
        "refresh_level": refresh_level,
        "deepseek_called": False,
    }
    normalized.setdefault("refresh_tier", record.get("refresh_tier") or raw_section.get("refresh_tier") or refresh_level)
    normalized["refresh_label"] = get_refresh_label(normalized)
    return normalized


def safe_refresh_module(
    state: MutableMapping[str, Any],
    module_key: str,
    label: str,
    handler: Callable[..., dict[str, Any] | None],
    refresh_level: str = REFRESH_LEVEL_MANUAL_BASIC,
    **handler_kwargs: Any,
) -> dict[str, Any]:
    """Run one manual refresh with a durable last-success fallback."""
    records = module_state(state)
    previous = records.get(module_key) or {}
    previous_success = clone_packet(previous.get("last_success") or {})
    started_at = command_center_now()

    try:
        raw_result = handler(**handler_kwargs) or {}
        if not isinstance(raw_result, dict):
            raw_result = {"status": "ok", "summary": str(raw_result)}
        raw_result["refresh_level"] = raw_result.get("refresh_level") or refresh_level
        raw_status = str(raw_result.get("status") or "").lower()
        if raw_result.get("ok") is False or raw_status in {"failed", "failure", "失败"}:
            raise RuntimeError(
                raw_result.get("error")
                or raw_result.get("last_error")
                or raw_result.get("message")
                or raw_result.get("summary")
                or f"{label}刷新失败"
            )
        finished_at = command_center_now()
        record = _success_record(
            module_key=module_key,
            label=label,
            result=raw_result,
            started_at=started_at,
            finished_at=finished_at,
            refresh_level=refresh_level,
        )
        records[module_key] = record
        state[COMMAND_CENTER_MODULE_STATE_KEY] = records
        mark_module(state, module_key, str(record.get("status") or "已刷新"), record.get("source") or label)
        return clone_packet(record)
    except Exception as exc:
        finished_at = command_center_now()
        error_text = str(exc)
        record = {
            "module_key": module_key,
            "module": label,
            "ok": False,
            "status": "failed",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": _duration_seconds(started_at, finished_at),
            "message": error_text,
            "updated_at": finished_at,
            "source": (previous_success or {}).get("source") or label,
            "summary": (
                f"{label}刷新失败，已保留上次成功结果。"
                if previous_success else f"{label}刷新失败，暂无上次成功结果。"
            ),
            "data": (previous_success or {}).get("data") or {},
            "last_success": previous_success,
            "last_error": error_text,
            "error": error_text,
            "stale": bool(previous_success),
            "deepseek_called": False,
            "refresh_level": refresh_level,
            "refresh_tier": refresh_level,
        }
        records[module_key] = record
        state[COMMAND_CENTER_MODULE_STATE_KEY] = records
        mark_module(state, module_key, "失败", label, error_text)
        return clone_packet(record)


def merge_module_state(
    state: MutableMapping[str, Any],
    module_key: str,
    section: dict[str, Any] | None,
    default_refresh_level: str = REFRESH_LEVEL_AUTO_LIGHT,
) -> dict[str, Any]:
    merged = _normalize_module_section(state, module_key, section, default_refresh_level)
    record = get_module_record(state, module_key)
    if not record:
        return merged

    if record.get("last_error"):
        merged["last_error"] = record.get("last_error")
        merged["stale"] = bool(record.get("last_success"))
    else:
        merged.setdefault("stale", False)
    merged["last_success"] = record.get("last_success") or {}
    merged["deepseek_called"] = False
    merged.setdefault("refresh_level", record.get("refresh_level") or default_refresh_level)
    merged.setdefault("refresh_tier", record.get("refresh_tier") or merged["refresh_level"])
    merged["refresh_label"] = get_refresh_label(merged)
    return merged


def build_live_conclusion(live_packet: dict[str, Any]) -> dict[str, Any]:
    refreshed = [
        MODULE_NAMES[key]
        for key, section in (live_packet or {}).items()
        if key in MODULE_NAMES and isinstance(section, dict) and section.get("is_fresh")
    ]
    if not refreshed:
        return {
            "mode": "当前为示例/待刷新状态",
            "included_modules": [],
            "summary": "当前为示例/待刷新状态：市场、量化、纪律、ETF、雷达均未刷新，不能假装已有真实综合结论。",
            "score": 0,
            "action": "只观察",
            "deepseek_called": False,
        }

    score = min(85, 40 + len(refreshed) * 9)
    action = "只观察"
    discipline_action = (live_packet.get("discipline") or {}).get("action_state") or ""
    next_action = (live_packet.get("next_ticket") or {}).get("action_state") or ""
    etf_action = (live_packet.get("margin_etf") or {}).get("action_state") or ""
    market_summary = (live_packet.get("market") or {}).get("summary") or ""
    if any(text in discipline_action for text in ["降风险"]) or "只观察" in market_summary:
        action = "降风险 / 只观察"
    elif "可准备" in next_action and any(text in etf_action for text in ["进攻", "可"]):
        action = "可准备，但必须等验证"
        score = min(90, score + 6)
    elif "等验证" in next_action or "只调仓" in discipline_action:
        action = "等验证 / 只调仓"

    mode = "综合推演结论" if len(refreshed) == len(MODULE_NAMES) else "部分刷新结论"
    return {
        "mode": mode,
        "included_modules": refreshed,
        "summary": (
            f"{mode}：已纳入 {'、'.join(refreshed)}。"
            f"当前动作倾向为 {action}；该判断只来自已缓存摘要，不调用 DeepSeek，也不输出确定性买卖结论。"
        ),
        "score": score,
        "action": action,
        "deepseek_called": False,
    }


def build_live_packet(
    state: MutableMapping[str, Any],
    section_builders: dict[str, Callable[[], dict[str, Any]]],
    refresh_level: str = REFRESH_LEVEL_AUTO_LIGHT,
) -> dict[str, Any]:
    """Aggregate cached sections only. It never invokes refresh handlers."""
    live_packet = {
        key: merge_module_state(state, key, builder(), refresh_level)
        for key, builder in section_builders.items()
    }
    live_packet["conclusion"] = build_live_conclusion(live_packet)
    live_packet["errors"] = collect_errors(state, tuple(section_builders.keys()))
    state["command_center_live_packet"] = clone_packet(live_packet)
    return clone_packet(live_packet)


def build_display_packet(
    live_packet: dict[str, Any],
    fallback_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback = fallback_packet or {}
    conclusion = live_packet.get("conclusion") or {}
    market = live_packet.get("market") or {}
    quant = live_packet.get("quant") or {}
    discipline = live_packet.get("discipline") or {}
    next_ticket = live_packet.get("next_ticket") or {}
    margin_etf = live_packet.get("margin_etf") or {}
    candidates = next_ticket.get("top_candidates") or []
    display = clone_packet(fallback)
    display.update(
        {
            "score": int(conclusion.get("score") or 0),
            "trend_label": conclusion.get("mode") or "待刷新",
            "probability": int(conclusion.get("score") or 0),
            "confidence": "待刷新" if not conclusion.get("included_modules") else "中",
            "one_sentence": conclusion.get("summary") or "当前为示例/待刷新状态。",
            "updated_at": command_center_now(),
            "quant_output": {
                "label": quant.get("direction") or quant.get("status") or "未刷新",
                "summary": quant.get("summary") or "请点击综合中心卡片按钮生成。",
            },
            "discipline_output": {
                "label": discipline.get("action_state") or discipline.get("status") or "未刷新",
                "summary": discipline.get("summary") or "交易纪律实验室暂未生成结构化缓存。",
            },
            "fusion_output": {
                "label": conclusion.get("action") or "只观察",
                "summary": conclusion.get("summary") or "",
                "composite_score": int(conclusion.get("score") or 0),
                "win_rate": "待验证",
                "suggested_position": conclusion.get("action") or "只观察",
                "suggested_amount": (fallback.get("allocation_budget") or {}).get("risk_budget_amount"),
                "amount_basis": "沿用预算展示",
            },
            "validated_data": [
                f"{name}：已纳入缓存摘要"
                for name in conclusion.get("included_modules") or []
            ] or ["当前没有真实刷新模块，综合结论处于待刷新状态。"],
            "cautious_inference": [
                market.get("summary", ""),
                quant.get("summary", ""),
                discipline.get("summary", ""),
            ],
            "watchlist": [
                "没有结果的模块显示空态，不自动拉取外部接口。",
                "DeepSeek 仍需手动点击解释按钮才会调用。",
                "综合中心卡片内刷新会写入统一 last_success；旧版工作台仅作为备份入口。",
            ],
            "next_observation_targets": [
                {
                    "code": item.get("ticker", ""),
                    "name": item.get("name", ""),
                    "theme": "下一票雷达",
                    "focus": f"规则分 {item.get('score', '暂无')}",
                    "action_state": item.get("action_state", "只观察"),
                    "observation_budget": (fallback.get("allocation_budget") or {}).get("next_ticket_budget_amount"),
                    "single_ticket_amount": None,
                    "budget_basis": "沿用预算展示",
                    "ticket_basis": "待验证",
                }
                for item in candidates[:3]
            ],
            "signal_confluence": [
                {"name": "市场环境", "strength": market.get("status"), "status": market.get("status"), "evaluation": "观察", "comment": market.get("summary")},
                {"name": "量化推演", "strength": quant.get("status"), "status": quant.get("status"), "evaluation": "观察", "comment": quant.get("summary")},
                {"name": "交易纪律", "strength": discipline.get("action_state"), "status": discipline.get("status"), "evaluation": "观察", "comment": discipline.get("summary")},
                {"name": "下一票雷达", "strength": next_ticket.get("action_state"), "status": next_ticket.get("status"), "evaluation": "观察", "comment": next_ticket.get("summary")},
                {"name": "融资 ETF", "strength": margin_etf.get("action_state"), "status": margin_etf.get("status"), "evaluation": "观察", "comment": margin_etf.get("summary")},
            ],
        }
    )
    return display


def run_refresh_sequence(
    steps: list[tuple[str, str, Callable[..., dict[str, Any] | None]]],
    runner: Callable[[str, str], dict[str, Any]],
    progress_callback: Callable[[str, str, dict[str, Any] | None], None] | None = None,
    refresh_level: str = REFRESH_LEVEL_MANUAL_BASIC,
) -> dict[str, Any]:
    results = []
    errors = []
    for module_key, label, _handler in steps:
        step_started_at = command_center_now()
        if progress_callback:
            progress_callback("start", label, None)
        result = runner(module_key, label)
        step_finished_at = command_center_now()
        result["refresh_level"] = result.get("refresh_level") or refresh_level
        result["started_at"] = result.get("started_at") or step_started_at
        result["finished_at"] = result.get("finished_at") or result.get("updated_at") or step_finished_at
        result["duration_seconds"] = result.get("duration_seconds")
        if result["duration_seconds"] is None:
            result["duration_seconds"] = _duration_seconds(result["started_at"], result["finished_at"])
        result["message"] = (
            result.get("message")
            or result.get("summary")
            or result.get("error")
            or result.get("last_error")
            or f"{label}刷新完成"
        )
        results.append(result)
        if result.get("ok"):
            if progress_callback:
                progress_callback("success", label, result)
        else:
            errors.append(
                {
                    "module": label,
                    "message": result.get("error") or result.get("last_error") or "未知错误",
                    "updated_at": result.get("updated_at") or command_center_now(),
                    "source": result.get("source") or label,
                }
            )
            if progress_callback:
                progress_callback("failure", label, result)
    return {
        "finished_at": command_center_now(),
        "results": clone_packet(results),
        "errors": clone_packet(errors),
        "refresh_level": refresh_level,
        "deepseek_called": False,
    }


def _duration_seconds(started_at: Any, finished_at: Any) -> float:
    try:
        start = datetime.datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        finish = datetime.datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
        return round(max(0.0, (finish - start).total_seconds()), 3)
    except Exception:
        return 0.0
