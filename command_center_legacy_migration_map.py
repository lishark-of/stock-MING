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

READY_PACKET_STATUSES = {"ready", "partial", "completed", "success", "ok"}
READY_DATA_STATUSES = {"ready", "cached"}
BLOCKED_PACKET_STATUSES = {"failed", "error", "failure"}
BLOCKED_CAPABILITY_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
READY_CAPABILITY_STATES = {"available", "ready", "ok", "success"}

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

COMPLETION_REQUIREMENTS = {
    "today_pool": [
        ("packet", "command_center_market_packet", "市场风格 packet"),
    ],
    "tianyan_risk": [
        ("packet", "command_center_hard_risk_packet", "公告/硬风险 packet"),
    ],
    "discipline_lab": [
        ("packet", "command_center_discipline_packet", "纪律/回测 packet"),
    ],
    "quant_projection": [
        ("packet", "command_center_quant_packet", "量化推演 packet"),
    ],
    "margin_etf": [
        ("packet", "command_center_etf_packet", "ETF 配置 packet"),
        ("packet", "command_center_margin_packet", "融资融券 packet"),
    ],
    "data_healthcheck": [
        ("capability", "data_capability", "数据能力检测 packet"),
    ],
    "next_ticket_radar": [
        ("packet", "command_center_radar_packet", "下一票雷达 packet"),
    ],
    "cloud_brain": [
        ("capability", "supabase", "Supabase 能力检测"),
    ],
}

LEGACY_TOOL_ROUTES = {
    "today_pool": ("今日关注池", "高级工具箱 / 今日关注池"),
    "tianyan_risk": ("天眼风控", "高级工具箱 / 天眼风控"),
    "discipline_lab": ("交易纪律实验室", "高级工具箱 / 交易纪律实验室"),
    "quant_projection": ("量化推演", "高级工具箱 / 量化推演"),
    "margin_etf": ("融资 ETF", "高级工具箱 / 融资 ETF"),
    "data_healthcheck": ("数据源体检", "高级工具箱 / 数据源体检"),
    "next_ticket_radar": ("下一票雷达", "高级工具箱 / 下一票雷达"),
    "cloud_brain": ("云端外脑", "高级工具箱 / 云端外脑"),
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


def _packet_completion_check(state: Any, packet_key: str, label: str) -> dict:
    state_map = as_mapping(state)
    packet = as_mapping(state_map.get(packet_key))
    status = to_text(packet.get("status"), "missing").lower() if packet else "missing"
    data_status = to_text(packet.get("data_status") or packet.get("cache_state"), "").lower()
    if not packet:
        state_key = "missing"
        state_label = "待回流"
        passed = False
        reason = f"{label} 尚未写入 {packet_key}。"
    elif status in BLOCKED_PACKET_STATUSES:
        state_key = "blocked"
        state_label = "失败/受限"
        passed = False
        reason = to_text(packet.get("manual_required_text") or packet.get("summary"), f"{label} 已失败或受限。")
    elif status in READY_PACKET_STATUSES or data_status in READY_DATA_STATUSES:
        state_key = "complete"
        state_label = "已完成"
        passed = True
        reason = f"{label} 已回流 {packet_key}，状态 {status or data_status}。"
    else:
        state_key = "waiting"
        state_label = "待数据"
        passed = False
        reason = to_text(packet.get("manual_required_text") or packet.get("summary"), f"{label} 已接入但仍待数据。")
    return {
        "kind": "packet",
        "key": packet_key,
        "label": label,
        "required": f"{packet_key}.status/data_status 可用于综合中心",
        "current_state": state_key,
        "current_label": state_label,
        "passed": passed,
        "reason": reason,
        "deepseek_called": False,
    }


def _capability_rows(data_capability_packet: Any = None, term: str = "") -> list[dict]:
    packet = as_mapping(data_capability_packet)
    rows = []
    term_text = to_text(term).lower()
    for raw in as_list(packet.get("items")):
        item = as_mapping(raw)
        if not item:
            continue
        haystack = " ".join(
            to_text(item.get(key)).lower()
            for key in ("provider", "api", "label", "state", "capability_state", "status")
        )
        if term_text and term_text not in haystack:
            continue
        state = to_text(item.get("state") or item.get("capability_state") or item.get("status"), "unknown").lower()
        rows.append({**item, "normalized_state": state})
    return rows


def _capability_completion_check(data_capability_packet: Any, term: str, label: str) -> dict:
    rows = _capability_rows(data_capability_packet, "" if term == "data_capability" else term)
    states = {to_text(row.get("normalized_state")).lower() for row in rows}
    if not rows:
        state_key = "missing"
        state_label = "待检测"
        passed = False
        reason = f"{label} 尚未形成本地能力检测结果。"
    elif term == "data_capability":
        state_key = "complete"
        state_label = "已检测"
        passed = True
        reason = f"{label} 已形成 {len(rows)} 项本地能力状态；受限项进入恢复队列。"
    elif states & BLOCKED_CAPABILITY_STATES:
        state_key = "blocked"
        state_label = "受限/失败"
        passed = False
        reason = f"{label} 检测到权限、配置、网络或本会话跳过问题。"
    elif states & READY_CAPABILITY_STATES:
        state_key = "complete"
        state_label = "已检测"
        passed = True
        reason = f"{label} 已形成本地能力检测结果。"
    else:
        state_key = "waiting"
        state_label = "待验证"
        passed = False
        reason = f"{label} 仍需手动检测或复核缓存状态。"
    return {
        "kind": "capability",
        "key": term,
        "label": label,
        "required": f"{label} 有本地数据能力状态",
        "current_state": state_key,
        "current_label": state_label,
        "passed": passed,
        "reason": reason,
        "deepseek_called": False,
    }


def build_completion_checks(
    key: str,
    targets: list[str],
    state: Any = None,
    data_capability_packet: Any = None,
) -> list[dict]:
    requirements = COMPLETION_REQUIREMENTS.get(key)
    if not requirements:
        requirements = [("packet", target, target) for target in targets if target.startswith("command_center_")]
    checks = []
    for kind, target, label in requirements:
        if kind == "capability":
            checks.append(_capability_completion_check(data_capability_packet, target, label))
        else:
            checks.append(_packet_completion_check(state, target, label))
    return checks


def _completion_status(checks: list[dict]) -> tuple[str, str, str, bool]:
    if not checks:
        return "missing", "完成条件待定义", "尚未定义可验证完成条件。", False
    passed_count = sum(1 for item in checks if item.get("passed"))
    blocked_count = sum(1 for item in checks if item.get("current_state") == "blocked")
    if passed_count == len(checks):
        return "complete", "迁移完成", "所有目标 packet / 能力状态已满足完成条件。", True
    if blocked_count:
        return "blocked", "迁移受阻", f"{blocked_count} 项完成条件受限或失败。", False
    if passed_count:
        return "partial", "部分完成", f"{passed_count}/{len(checks)} 项完成条件已满足。", False
    return "waiting", "待回流", "目标 packet / 能力状态仍待手动恢复。", False


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


def _primary_write_packet(targets: list[str]) -> str:
    for target in targets:
        if target.startswith("command_center_"):
            return target
    return targets[0] if targets else "command_center_packet"


def _manual_action_for_item(key: str, label: str, payload: Mapping[str, Any], targets: list[str]) -> dict:
    legacy_tab, toolbox_entry = LEGACY_TOOL_ROUTES.get(key, (label, f"高级工具箱 / {label}"))
    writes_packet = _primary_write_packet(targets)
    action_label = to_text(payload.get("gate"), f"手动打开{legacy_tab}")
    return {
        "key": f"legacy_migration:{key}",
        "label": label,
        "action_label": action_label,
        "toolbox_entry": toolbox_entry,
        "workspace_target": "高级工具箱（旧版保留）",
        "workspace_state_key": "workspace_mode_v2",
        "legacy_tab": legacy_tab,
        "legacy_tab_state_key": "legacy_workspace_selected_tab",
        "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
        "writes_packet": writes_packet,
        "refresh_policy": "button_gated",
        "deepseek_called": False,
    }


def build_legacy_migration_item(item: Any, state: Any = None) -> dict:
    payload = as_mapping(item)
    label = to_text(payload.get("label"), "旧版工具")
    key = to_text(payload.get("key"), label)
    status = as_mapping(payload.get("capability_status"))
    status_key = to_text(status.get("status"), "missing")
    targets = extract_packet_targets(payload.get("packet"))
    packet_state = _packet_status_from_state(state, targets)
    checks = build_completion_checks(key, targets, state=state)
    completion_status, completion_label, completion_summary, is_complete = _completion_status(checks)
    if packet_state == "packet_missing" and any(target.startswith("command_center_") for target in targets):
        packet_wiring = "packet_defined"
    elif packet_state == "packet_cached":
        packet_wiring = "packet_cached"
    elif packet_state == "packet_ready":
        packet_wiring = "packet_ready"
    else:
        packet_wiring = "legacy_only"
    migration_state = "packet_ready" if is_complete else _migration_state(packet_wiring, status_key)
    manual_action = _manual_action_for_item(key, label, payload, targets)
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
        "completion_status": completion_status,
        "completion_label": completion_label,
        "completion_summary": completion_summary,
        "completion_checks": checks,
        "is_complete": is_complete,
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
        "next_action": (
            f"{manual_action['toolbox_entry']} → {manual_action['action_label']}；"
            f"回流 {manual_action['writes_packet']}。"
        ),
        "manual_action": manual_action,
        "action_label": manual_action["action_label"],
        "toolbox_entry": manual_action["toolbox_entry"],
        "workspace_target": manual_action["workspace_target"],
        "workspace_state_key": manual_action["workspace_state_key"],
        "legacy_tab": manual_action["legacy_tab"],
        "legacy_tab_state_key": manual_action["legacy_tab_state_key"],
        "navigation_label": manual_action["navigation_label"],
        "writes_packet": manual_action["writes_packet"],
        "refresh_policy": "button_gated",
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
    state_map = as_mapping(state)
    if data_capability_packet is not None:
        state_map = {**state_map, "data_capability": data_capability_packet}
    items = []
    for raw in as_list(toolbox_packet.get("items")):
        item = build_legacy_migration_item(raw, state=state_map)
        targets = item.get("command_center_packets") or []
        checks = build_completion_checks(
            item.get("key", ""),
            targets,
            state=state_map,
            data_capability_packet=data_capability_packet,
        )
        completion_status, completion_label, completion_summary, is_complete = _completion_status(checks)
        item.update(
            {
                "completion_status": completion_status,
                "completion_label": completion_label,
                "completion_summary": completion_summary,
                "completion_checks": checks,
                "is_complete": is_complete,
                "migration_state": "packet_ready" if is_complete else item.get("migration_state", "wired_waiting_data"),
                "migration_label": MIGRATION_STATE_LABELS.get(
                    "packet_ready" if is_complete else item.get("migration_state", "wired_waiting_data"),
                    "待迁移",
                ),
                "tone": MIGRATION_STATE_TONES.get(
                    "packet_ready" if is_complete else item.get("migration_state", "wired_waiting_data"),
                    "missing",
                ),
            }
        )
        items.append(item)
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
