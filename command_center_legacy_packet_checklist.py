from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

import command_center_packet_registry as packet_registry


CHECKLIST_VERSION = "2026-06-legacy-packet-checklist-v1"

READY_PACKET_STATUSES = {"ready", "partial", "completed", "success", "ok"}
READY_DATA_STATUSES = {"ready", "cached"}
BLOCKED_PACKET_STATUSES = {
    "failed",
    "failure",
    "error",
    "permission_denied",
    "disabled_this_session",
    "not_configured",
    "network_failed",
}
MANUAL_STATES = {"requires_manual_refresh", "manual_required", "manual", "needs_check"}


LEGACY_PACKET_ABILITIES = (
    {
        "key": "moneyflow",
        "label": "个股资金流",
        "target_packet": "command_center_moneyflow_packet",
        "packet_alias": "moneyflow_packet",
        "legacy_entry": "高级工具箱 / A股专业实盘 / 个股资金流",
        "home_surface": "市场分析方法 / 策略执行实验室",
        "decision_chain_stage": "数据能力状态 → 市场分析方法 → 策略执行",
        "recovery_action_label": "手动刷新个股资金流",
        "decision_guardrail": "缺少资金流时，A股趋势和加仓条件只能标记为待验证。",
    },
    {
        "key": "dragon_tiger",
        "label": "龙虎榜",
        "target_packet": "command_center_dragon_tiger_packet",
        "packet_alias": "dragon_tiger_packet",
        "legacy_entry": "高级工具箱 / 下一票雷达 / 龙虎榜",
        "home_surface": "下一票 Top3 / A股证据雷达",
        "decision_chain_stage": "数据能力状态 → 下一票雷达 → 今日总决策",
        "recovery_action_label": "手动检测龙虎榜",
        "decision_guardrail": "缺少龙虎榜时，不能把机构席位或游资行为当成已验证证据。",
    },
    {
        "key": "limit_emotion",
        "label": "涨跌停/情绪",
        "target_packet": "command_center_limit_emotion_packet",
        "packet_alias": "limit_emotion_packet",
        "legacy_entry": "高级工具箱 / 数据源体检 / 涨跌停情绪",
        "home_surface": "5-10 日趋势推演 / 风险警报",
        "decision_chain_stage": "数据能力状态 → 趋势推演 → 风险警报",
        "recovery_action_label": "手动检测涨跌停/情绪",
        "decision_guardrail": "缺少涨跌停/情绪时，A股过热和退潮风险只能显示待验证。",
    },
    {
        "key": "margin",
        "label": "融资融券",
        "target_packet": "command_center_margin_packet",
        "packet_alias": "margin_packet",
        "legacy_entry": "高级工具箱 / 融资 ETF / 融资融券",
        "home_surface": "ETF / 融资动作 / 风险预算",
        "decision_chain_stage": "数据能力状态 → ETF/融资动作 → 今日总决策",
        "recovery_action_label": "手动检测融资融券",
        "decision_guardrail": "缺少融资融券时，融资比例、风险预算和降杠杆判断必须保守。",
    },
    {
        "key": "chip_radar",
        "label": "筹码/胜率",
        "target_packet": "command_center_chip_packet",
        "packet_alias": "chip_packet",
        "legacy_entry": "高级工具箱 / 量化推演 / 筹码胜率",
        "home_surface": "策略执行实验室 / 趋势推演",
        "decision_chain_stage": "数据能力状态 → 策略执行 → 趋势推演",
        "recovery_action_label": "手动刷新筹码/胜率",
        "decision_guardrail": "缺少筹码和胜率时，突破延续和路径概率只能作为待验证参考。",
    },
    {
        "key": "discipline_backtest",
        "label": "纪律/回测",
        "target_packet": "command_center_discipline_packet",
        "packet_alias": "discipline_packet",
        "legacy_entry": "高级工具箱 / 交易纪律实验室",
        "home_surface": "策略执行实验室 / 风险预算",
        "decision_chain_stage": "数据能力状态 → 策略执行 → 今日总决策",
        "recovery_action_label": "手动运行纪律/回测",
        "decision_guardrail": "缺少纪律/回测缓存时，策略不能被标记为纪律已验证。",
    },
    {
        "key": "next_ticket_radar",
        "label": "下一票雷达",
        "target_packet": "command_center_radar_packet",
        "packet_alias": "radar_packet",
        "legacy_entry": "高级工具箱 / 下一票雷达",
        "home_surface": "下一票 Top3",
        "decision_chain_stage": "数据能力状态 → 下一票 Top3 → 今日总决策",
        "recovery_action_label": "手动运行下一票雷达",
        "decision_guardrail": "缺少雷达 packet 时，首页不能把候选池当成可执行清单。",
    },
)


MIGRATION_LABELS = {
    "packet_ready": "已回流",
    "blocked": "数据/权限阻断",
    "manual_required": "需要手动恢复",
    "wired_waiting_data": "已接 packet，待数据",
    "legacy_only": "仍在旧工具箱",
}

MIGRATION_TONES = {
    "packet_ready": "ready",
    "blocked": "failed",
    "manual_required": "stale",
    "wired_waiting_data": "missing",
    "legacy_only": "missing",
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


def _packet_for(state: Mapping[str, Any], target_packet: str, alias: str = "") -> dict:
    for key in (target_packet, alias):
        packet = as_mapping(state.get(key))
        if packet:
            return packet
    return {}


def _packet_status(packet: Any) -> str:
    payload = as_mapping(packet)
    if not payload:
        return "missing"
    status = to_text(payload.get("status") or payload.get("state"), "unknown").lower()
    data_status = to_text(payload.get("data_status") or payload.get("cache_state"), "").lower()
    if status in BLOCKED_PACKET_STATUSES or data_status in BLOCKED_PACKET_STATUSES:
        return "blocked"
    if status in READY_PACKET_STATUSES or data_status in READY_DATA_STATUSES:
        return "ready"
    if data_status == "cached":
        return "ready"
    return "waiting"


def _action_state(action: Mapping[str, Any]) -> str:
    text = " ".join(
        to_text(action.get(key)).lower()
        for key in (
            "state",
            "status",
            "status_key",
            "status_label",
            "capability_state",
            "recovery_mode",
            "recovery_mode_label",
            "summary",
            "reason",
            "next_action",
        )
    )
    if any(token in text for token in ("permission", "权限", "disabled", "跳过", "not_configured", "network", "failed", "失败", "受限", "阻断")):
        return "blocked"
    if any(token in text for token in ("manual", "手动", "requires_manual_refresh", "needs_check", "待检测", "待刷新")):
        return "manual_required"
    if any(token in text for token in ("empty", "暂无", "stale", "cache", "缓存", "待数据")):
        return "wired_waiting_data"
    return "legacy_only"


def _collect_recovery_actions(state: Mapping[str, Any]) -> list[dict]:
    actions: list[dict] = []
    for key in (
        "data_recovery_actions",
        "legacy_a_share_fact_recovery_actions",
        "tool_recovery_actions",
        "next_ticket_evidence_recovery_actions",
    ):
        for raw in as_list(state.get(key)):
            action = as_mapping(raw)
            if action:
                actions.append(action)
    center = as_mapping(state.get("data_recovery_center"))
    for raw in as_list(center.get("actions")):
        action = as_mapping(raw)
        if action:
            actions.append(action)
    for group in as_list(center.get("groups")):
        for raw in as_list(as_mapping(group).get("items")):
            action = as_mapping(raw)
            if action:
                actions.append(action)
    return actions


def _action_matches(action: Mapping[str, Any], ability: Mapping[str, Any]) -> bool:
    target = to_text(ability.get("target_packet"))
    alias = to_text(ability.get("packet_alias"))
    key = to_text(ability.get("key"))
    label = to_text(ability.get("label"))
    haystack = " ".join(
        to_text(action.get(field))
        for field in (
            "writes_packet",
            "target_packet",
            "packet_key",
            "key",
            "source_key",
            "source_type",
            "label",
            "source_label",
            "toolbox_entry",
            "legacy_tab",
            "summary",
            "next_action",
        )
    )
    return any(token and token in haystack for token in (target, alias, key, label))


def _migration_item_for(state: Mapping[str, Any], ability: Mapping[str, Any]) -> dict:
    migration = as_mapping(state.get("legacy_migration_map"))
    target = to_text(ability.get("target_packet"))
    key = to_text(ability.get("key"))
    label = to_text(ability.get("label"))
    for raw in as_list(migration.get("items")):
        item = as_mapping(raw)
        if not item:
            continue
        packets = [to_text(packet) for packet in as_list(item.get("command_center_packets"))]
        if target in packets or target == to_text(item.get("writes_packet")):
            return item
        if key == to_text(item.get("key")) or label == to_text(item.get("label")):
            return item
    return {}


def _state_from_inputs(
    packet_state: str,
    recovery_action: Mapping[str, Any],
    migration_item: Mapping[str, Any],
) -> str:
    if packet_state == "ready":
        return "packet_ready"
    if packet_state == "blocked":
        return "blocked"
    action_state = _action_state(recovery_action) if recovery_action else ""
    if action_state == "blocked":
        return "blocked"
    migration_state = to_text(migration_item.get("migration_state")).lower()
    if migration_state == "blocked":
        return "blocked"
    if action_state == "manual_required" or migration_state == "manual_required":
        return "manual_required"
    if action_state == "wired_waiting_data" or migration_state in {"wired_waiting_data", "packet_defined"}:
        return "wired_waiting_data"
    if packet_state == "waiting":
        return "wired_waiting_data"
    return "legacy_only"


def _next_action(ability: Mapping[str, Any], migration_state: str, recovery_action: Mapping[str, Any]) -> str:
    if migration_state == "packet_ready":
        return "已进入综合中心；执行前复核日期、来源和缓存状态。"
    if migration_state == "blocked":
        reason = to_text(recovery_action.get("reason") or recovery_action.get("summary"))
        suffix = f"；当前阻断：{reason}" if reason else ""
        return f"{ability['legacy_entry']} → {ability['recovery_action_label']}；权限/数据恢复后回流 {ability['target_packet']}{suffix}。"
    if migration_state == "manual_required":
        return f"{ability['legacy_entry']} → {ability['recovery_action_label']}；完成后回流 {ability['target_packet']}。"
    if migration_state == "wired_waiting_data":
        return f"{ability['target_packet']} 已在清单中；等待手动恢复或缓存写入后再进入决策链。"
    return f"{ability['legacy_entry']} 仍作为高级工具保留；下一步迁入 {ability['target_packet']}。"


def build_legacy_packet_migration_checklist(state: Any = None) -> dict:
    state_map = as_mapping(state)
    actions = _collect_recovery_actions(state_map)
    items: list[dict] = []
    for ability in LEGACY_PACKET_ABILITIES:
        target_packet = to_text(ability["target_packet"])
        alias = to_text(ability.get("packet_alias"))
        packet = _packet_for(state_map, target_packet, alias)
        packet_status = _packet_status(packet)
        recovery_action = next((action for action in actions if _action_matches(action, ability)), {})
        migration_item = _migration_item_for(state_map, ability)
        migration_state = _state_from_inputs(packet_status, recovery_action, migration_item)
        spec = packet_registry.get_command_center_packet_spec(target_packet)
        item = {
            "key": ability["key"],
            "label": ability["label"],
            "legacy_entry": ability["legacy_entry"],
            "target_packet": target_packet,
            "packet_alias": alias,
            "packet_label": to_text(spec.get("label"), ability["label"]),
            "home_surface": ability["home_surface"],
            "decision_chain_stage": ability["decision_chain_stage"],
            "migration_state": migration_state,
            "migration_label": MIGRATION_LABELS.get(migration_state, "待迁移"),
            "tone": MIGRATION_TONES.get(migration_state, "missing"),
            "recovery_action_label": to_text(
                recovery_action.get("action_label") or recovery_action.get("label"),
                ability["recovery_action_label"],
            ),
            "writes_packet": target_packet,
            "refresh_policy": "button_gated",
            "external_call_policy": "not_triggered",
            "deepseek_called": False,
            "next_action": _next_action(ability, migration_state, recovery_action),
            "decision_guardrail": ability["decision_guardrail"],
            "source_packet_state": packet_status,
            "source_summary": to_text(packet.get("summary") or packet.get("status_label"), "暂无本地 packet 摘要。"),
            "registry_owner": to_text(spec.get("owner"), "待定义 owner"),
            "registry_source": to_text(spec.get("source"), "待定义来源"),
        }
        items.append(item)
    packet_ready_count = sum(1 for item in items if item["migration_state"] == "packet_ready")
    blocked_count = sum(1 for item in items if item["migration_state"] == "blocked")
    manual_count = sum(1 for item in items if item["migration_state"] == "manual_required")
    waiting_count = sum(1 for item in items if item["migration_state"] in {"wired_waiting_data", "legacy_only"})
    if blocked_count:
        status = "blocked"
        tone = "failed"
    elif packet_ready_count and packet_ready_count == len(items):
        status = "ready"
        tone = "ready"
    elif packet_ready_count or manual_count:
        status = "partial"
        tone = "stale"
    else:
        status = "missing"
        tone = "missing"
    next_actions = [
        f"{item['label']}：{item['next_action']}"
        for item in items
        if item["migration_state"] != "packet_ready"
    ][:4]
    return {
        "version": CHECKLIST_VERSION,
        "title": "旧工作台能力迁移清单",
        "status": status,
        "tone": tone,
        "summary": f"已回流 {packet_ready_count}｜受限 {blocked_count}｜需手动 {manual_count}｜待迁移/待数据 {waiting_count}",
        "items": items,
        "next_actions": next_actions or ["旧工作台关键能力已形成 packet 清单；继续保持按钮触发和执行前复核。"],
        "safe_mode_text": "这里只读取本地 packet、迁移地图和恢复队列；不会自动调用 Tushare、AkShare、DeepSeek、回测或全市场扫描。",
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }
