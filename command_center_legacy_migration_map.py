from __future__ import annotations

from collections.abc import Iterable, Mapping
from numbers import Number
from typing import Any

import command_center_toolbox_summary as toolbox_summary


MIGRATION_STATE_LABELS = {
    "packet_ready": "已回流到综合中心",
    "blocked": "数据/权限阻断",
    "manual_required": "需要手动恢复",
    "wired_waiting_data": "已接 packet，待数据",
    "legacy_only": "仍在旧工具箱",
}

MIGRATION_STATE_TONES = {
    "packet_ready": "ready",
    "blocked": "failed",
    "manual_required": "stale",
    "wired_waiting_data": "missing",
    "legacy_only": "missing",
}

HOME_SURFACES = {
    "today_pool": "Home Action Snapshot / 市场口径",
    "tianyan_risk": "风险警报 / 今日总决策",
    "discipline_lab": "策略执行实验室 / 纪律证据",
    "quant_projection": "5-10 日趋势推演",
    "margin_etf": "ETF / 融资动作",
    "data_healthcheck": "数据新鲜度 / 数据恢复中心",
    "next_ticket_radar": "下一票 Top3 / A股证据雷达",
    "cloud_brain": "可选 DeepSeek 解释上下文",
}


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _text_items(value: Any, limit: int = 8) -> list[str]:
    result = []
    for item in as_list(value) if not isinstance(value, str) else [value]:
        text = to_text(item)
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def extract_packet_targets(packet_text: Any) -> list[str]:
    text = to_text(packet_text)
    if not text:
        return []
    normalized = (
        text.replace("/", " ")
        .replace("／", " ")
        .replace(",", " ")
        .replace("，", " ")
        .replace("|", " ")
    )
    result = []
    seen = set()
    for raw in normalized.split():
        token = raw.strip()
        if not token:
            continue
        if "_packet" not in token and not token.startswith(("last_", "radar_", "legacy_")):
            continue
        clean = token.strip("()[]{}")
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result


def _packet_status_from_state(state: Any, targets: Iterable[str]) -> str:
    state_map = as_mapping(state)
    for target in targets:
        packet = as_mapping(state_map.get(target))
        if not packet:
            continue
        status = to_text(packet.get("status"))
        data_status = to_text(packet.get("data_status"))
        if status == "failed":
            return "packet_failed"
        if data_status == "cached":
            return "packet_cached"
        return "packet_ready"
    return "packet_missing"


def _migration_state(packet_wiring: str, data_status: str) -> str:
    if data_status in {"blocked", "failed"}:
        return "blocked"
    if data_status == "manual":
        return "manual_required"
    if packet_wiring in {"packet_ready", "packet_cached"}:
        return "packet_ready"
    if packet_wiring == "packet_defined":
        return "wired_waiting_data"
    return "legacy_only"


def build_legacy_migration_item(item: Any, state: Any = None) -> dict:
    payload = as_mapping(item)
    label = to_text(payload.get("label"), "旧版工具")
    key = to_text(payload.get("key"), label)
    status = as_mapping(payload.get("capability_status"))
    status_key = to_text(status.get("status"), "missing")
    targets = extract_packet_targets(payload.get("packet"))
    packet_state = _packet_status_from_state(state, targets)
    if packet_state == "packet_missing" and any(target.startswith("command_center_") for target in targets):
        packet_wiring = "packet_defined"
    elif packet_state == "packet_cached":
        packet_wiring = "packet_cached"
    elif packet_state == "packet_ready":
        packet_wiring = "packet_ready"
    else:
        packet_wiring = "legacy_only"
    migration_state = _migration_state(packet_wiring, status_key)
    return {
        "key": key,
        "label": label,
        "legacy_entry": label,
        "home_surface": HOME_SURFACES.get(key, "综合推演中心 / 高级工具箱"),
        "command_center_packets": targets,
        "packet_wiring": packet_wiring,
        "packet_state": packet_state,
        "data_status": status_key,
        "data_status_label": to_text(status.get("status_label"), "待检测"),
        "migration_state": migration_state,
        "migration_label": MIGRATION_STATE_LABELS.get(migration_state, "待迁移"),
        "tone": MIGRATION_STATE_TONES.get(migration_state, "missing"),
        "purpose": to_text(payload.get("purpose"), "旧版能力保留为高级工具。"),
        "decision_chain_stage": to_text(payload.get("migration_target"), "逐步回流到综合推演中心 packet。"),
        "manual_gate": to_text(payload.get("gate"), "按钮手动触发"),
        "trigger_policy": "button_gated",
        "deepseek_policy": "manual_only",
        "safe_empty_state": to_text(payload.get("safe_empty_state"), "显示待验证，不自动触发重型请求。"),
        "data_dependencies": _text_items(payload.get("data_dependencies"), limit=6),
        "why_missing": _text_items(payload.get("common_missing_reasons"), limit=4),
        "current_blocker": to_text(status.get("summary"), "尚未读取到匹配的数据能力检测结果。"),
        "next_action": to_text(status.get("next_action"), payload.get("gate") or "按钮手动触发"),
        "deepseek_called": False,
    }


def _lane(items: list[dict], key: str, label: str) -> dict:
    lane_items = [item for item in items if item.get("migration_state") == key]
    return {
        "key": key,
        "label": label,
        "tone": MIGRATION_STATE_TONES.get(key, "missing"),
        "count": len(lane_items),
        "items": lane_items[:4],
        "summary": "、".join(item["label"] for item in lane_items[:4]) if lane_items else "暂无",
    }


def build_legacy_migration_map(
    state: Any = None,
    *,
    data_capability_packet: Any = None,
    keys: Iterable[str] | None = None,
) -> dict:
    toolbox_packet = toolbox_summary.build_advanced_toolbox_entry(
        keys=keys,
        data_capability_packet=data_capability_packet,
    )
    items = [build_legacy_migration_item(item, state=state) for item in as_list(toolbox_packet.get("items"))]
    lanes = [
        _lane(items, "blocked", "数据/权限阻断"),
        _lane(items, "manual_required", "需要手动恢复"),
        _lane(items, "packet_ready", "已回流到综合中心"),
        _lane(items, "wired_waiting_data", "已接 packet，待数据"),
        _lane(items, "legacy_only", "仍在旧工具箱"),
    ]
    blocked_count = sum(1 for item in items if item["migration_state"] == "blocked")
    manual_count = sum(1 for item in items if item["migration_state"] == "manual_required")
    packet_ready_count = sum(1 for item in items if item["migration_state"] == "packet_ready")
    waiting_count = sum(1 for item in items if item["migration_state"] in {"wired_waiting_data", "legacy_only"})
    next_actions = []
    for item in items:
        if item["migration_state"] in {"blocked", "manual_required", "wired_waiting_data", "legacy_only"}:
            next_actions.append(f"{item['label']}：{item['next_action']}")
        if len(next_actions) >= 4:
            break
    return {
        "status": "in_progress" if items else "missing",
        "title": "旧版能力迁移地图",
        "summary": (
            f"已回流 {packet_ready_count}｜受限 {blocked_count}｜手动 {manual_count}｜待迁移/待数据 {waiting_count}"
            if items
            else "尚未读取旧版能力迁移表。"
        ),
        "items": items,
        "lanes": lanes,
        "next_actions": next_actions or ["继续保持综合推演中心为主入口；旧工具只在按钮触发时运行。"],
        "safe_mode_text": "迁移地图只读取本地 packet 和数据能力状态；不会自动调用 DeepSeek、回测、全市场扫描或重型数据接口。",
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }
