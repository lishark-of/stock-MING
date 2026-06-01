from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MODULES = (
    ("market", "市场"),
    ("quant", "量化"),
    ("discipline", "纪律"),
    ("margin_etf", "融资 ETF"),
    ("next_ticket", "下一票"),
    ("strategy_execution", "策略执行"),
)

READY_STATUSES = {"ok", "ready", "completed", "complete", "success", "succeeded", "已刷新"}


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


def _packet_state(section: Any) -> str:
    payload = _as_mapping(section)
    if not payload:
        return "missing"
    status = _to_text(payload.get("status"))
    if payload.get("is_fresh") is True or status in READY_STATUSES or status.lower() in READY_STATUSES:
        return "ready"
    if payload.get("last_success") or payload.get("stale") or _to_text(payload.get("refresh_label")) == "使用缓存":
        return "cached"
    return "missing"


def _state_tone(state: str) -> str:
    if state == "ready":
        return "success"
    if state == "cached":
        return "warning"
    return "muted"


def build_center_usage_boundary_text() -> str:
    return "当前结论只用于辅助复核，不是荐股、自动交易或收益承诺；DeepSeek 只在你点击解释按钮后读取当前 packet。"


def build_center_coverage_items(live_packet: Any, strategy_packet: Any = None, decision_packet: Any = None) -> list[dict]:
    live = _as_mapping(live_packet)
    items = []
    for key, label in MODULES:
        packet = strategy_packet if key == "strategy_execution" and strategy_packet is not None else live.get(key)
        state = _packet_state(packet)
        items.append({"key": key, "label": label, "state": state, "tone": _state_tone(state)})
    if decision_packet is not None:
        state = _packet_state(decision_packet)
        items.append({"key": "decision", "label": "今日总决策", "state": state, "tone": _state_tone(state)})
    return items


def _error_text(item: Any) -> str:
    payload = _as_mapping(item)
    if payload:
        return _to_text(payload.get("message") or payload.get("error") or payload.get("last_error"))
    return _to_text(item)


def build_center_error_items(live_packet: Any) -> list[dict]:
    live = _as_mapping(live_packet)
    items = []
    raw_errors = live.get("errors") or []
    if isinstance(raw_errors, (list, tuple)):
        for item in raw_errors:
            payload = _as_mapping(item)
            message = _error_text(payload or item)
            if message:
                items.append(
                    {
                        "module": _to_text(payload.get("module")) or "模块",
                        "message": message,
                        "updated_at": _to_text(payload.get("updated_at")) or "暂无时间",
                        "source": _to_text(payload.get("source")) or "未加载",
                    }
                )
    elif raw_errors:
        items.append({"module": "模块", "message": _to_text(raw_errors), "updated_at": "暂无时间", "source": "未加载"})

    for key, label in MODULES:
        section = _as_mapping(live.get(key))
        message = _to_text(section.get("last_error") or section.get("error"))
        if message:
            items.append(
                {
                    "module": label,
                    "message": message,
                    "updated_at": _to_text(section.get("updated_at")) or "暂无时间",
                    "source": _to_text(section.get("source")) or label,
                }
            )
    deduped = []
    seen = set()
    for item in items:
        key = (item["module"], item["message"], item["updated_at"], item["source"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:8]


def _refresh_error_items(refresh_summary: Any) -> list[dict]:
    refresh = _as_mapping(refresh_summary)
    errors = refresh.get("errors") or []
    if not isinstance(errors, (list, tuple)):
        errors = [errors] if errors else []
    items = []
    for item in errors:
        payload = _as_mapping(item)
        message = _error_text(payload or item)
        if not message:
            continue
        items.append(
            {
                "module": _to_text(payload.get("module")) or "模块",
                "message": message,
                "updated_at": _to_text(payload.get("updated_at")) or _to_text(refresh.get("finished_at")) or "暂无时间",
                "source": _to_text(payload.get("source")) or "未加载",
            }
        )
    return items


def _dedupe_items(items: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for item in items:
        key = (
            item.get("module") or "",
            item.get("message") or "",
            item.get("updated_at") or "",
            item.get("source") or "",
        )
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:8]


def build_center_stale_items(live_packet: Any) -> list[dict]:
    live = _as_mapping(live_packet)
    items = []
    for key, label in MODULES:
        section = _as_mapping(live.get(key))
        if section.get("stale"):
            items.append(
                {
                    "key": key,
                    "label": label,
                    "updated_at": _to_text(section.get("updated_at")) or "暂无",
                    "source": _to_text(section.get("source")) or label,
                }
            )
    return items


def build_center_next_action_items(
    live_packet: Any = None,
    strategy_packet: Any = None,
    decision_packet: Any = None,
    deepseek_summary: Any = None,
) -> list[dict]:
    coverage = build_center_coverage_items(live_packet, strategy_packet, decision_packet)
    live_ready = any(item["state"] in {"ready", "cached"} for item in coverage if item["key"] not in {"strategy_execution", "decision"})
    strategy_ready = _packet_state(strategy_packet) in {"ready", "cached"}
    decision_ready = _packet_state(decision_packet) in {"ready", "cached"}
    deepseek_ready = bool(_to_text(deepseek_summary))
    return [
        {"key": "refresh_basic", "label": "刷新今日基础数据", "status": "ready" if live_ready else "recommended"},
        {"key": "strategy_execution", "label": "生成策略执行建议", "status": "ready" if strategy_ready else "recommended"},
        {"key": "daily_decision", "label": "生成今日总决策", "status": "ready" if decision_ready else "recommended"},
        {"key": "deepseek", "label": "DeepSeek 综合解释", "status": "ready" if deepseek_ready else "optional"},
    ]


def _latest_updated_text(live_packet: Any, refresh_summary: Any) -> str:
    refresh = _as_mapping(refresh_summary)
    live = _as_mapping(live_packet)
    return (
        _to_text(refresh.get("finished_at") or refresh.get("updated_at"))
        or _to_text(live.get("updated_at") or live.get("generated_at"))
        or "暂无"
    )


def _coverage_summary_text(coverage_items: list[dict]) -> str:
    ready = [item["label"] for item in coverage_items if item["state"] == "ready"]
    cached = [item["label"] for item in coverage_items if item["state"] == "cached"]
    missing = [item["label"] for item in coverage_items if item["state"] == "missing"]
    return (
        f"已刷新：{'、'.join(ready) if ready else '无'}｜"
        f"使用缓存：{'、'.join(cached) if cached else '无'}｜"
        f"待验证：{'、'.join(missing) if missing else '无'}"
    )


def build_command_center_overview_view_model(
    live_packet: Any = None,
    refresh_summary: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    deepseek_summary: Any = None,
) -> dict:
    coverage_items = build_center_coverage_items(live_packet, strategy_packet, decision_packet)
    error_items = _dedupe_items(build_center_error_items(live_packet) + _refresh_error_items(refresh_summary))
    stale_items = build_center_stale_items(live_packet)
    live_states = [item["state"] for item in coverage_items if item["key"] != "decision"]
    ready_count = sum(1 for state in live_states if state in {"ready", "cached"})

    if error_items:
        status_label, tone = "有错误", "danger"
    elif ready_count == 0:
        status_label, tone = "待刷新", "muted"
    elif ready_count >= len(live_states):
        status_label, tone = "已刷新", "success"
    else:
        status_label, tone = "部分刷新", "warning"

    deepseek_called = any(
        bool(_as_mapping(packet).get("deepseek_called"))
        for packet in (live_packet, decision_packet, strategy_packet)
    )
    return {
        "overall_status_label": status_label,
        "overall_status_tone": tone,
        "coverage_items": coverage_items,
        "coverage_summary_text": _coverage_summary_text(coverage_items),
        "error_items": error_items,
        "stale_items": stale_items,
        "updated_text": _latest_updated_text(live_packet, refresh_summary),
        "deepseek_text": "DeepSeek：已调用" if deepseek_called else "DeepSeek：未调用",
        "usage_boundary_text": build_center_usage_boundary_text(),
        "next_action_items": build_center_next_action_items(live_packet, strategy_packet, decision_packet, deepseek_summary),
    }
