from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


READY_STATUSES = {"ready", "ok", "success", "completed", "complete", "available", "已刷新", "综合推演结论"}
CACHED_STATUSES = {"cached", "stale", "partial", "fallback_used", "stale_cache", "使用缓存", "部分刷新结论"}
FAILED_STATUSES = {"failed", "error", "blocked", "permission_denied", "network_failed", "not_configured", "失败"}
PENDING_STATUSES = {"waiting", "missing", "unknown", "manual", "requires_manual_refresh", "待验证", "待刷新"}


def _as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, Number):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except Exception:
            return 0
    return 0


def _tone(status: str) -> str:
    return {
        "ready": "ready",
        "manual": "stale",
        "stale": "stale",
        "waiting": "missing",
        "blocked": "failed",
    }.get(status, "missing")


def _status_label(status: str) -> str:
    return {
        "ready": "已就绪",
        "manual": "手动可选",
        "stale": "使用缓存",
        "waiting": "待验证",
        "blocked": "阻断",
    }.get(status, "待验证")


def _status_item(
    key: str,
    label: str,
    status: str,
    summary: str,
    guardrail: str,
    source: str = "本地 packet",
) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "status_label": _status_label(status),
        "tone": _tone(status),
        "summary": summary,
        "guardrail": guardrail,
        "source": source,
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def _packet_status(packet: Any, ready_fields: tuple[str, ...] = ()) -> str:
    payload = _as_mapping(packet)
    if not payload:
        return "waiting"
    status_text = _to_text(payload.get("status") or payload.get("state") or payload.get("data_status")).lower()
    status_cn = _to_text(payload.get("status") or payload.get("state") or payload.get("data_status"))
    if status_text in FAILED_STATUSES or status_cn in FAILED_STATUSES or payload.get("last_error"):
        return "blocked"
    if status_text in CACHED_STATUSES or status_cn in CACHED_STATUSES or payload.get("stale"):
        return "stale"
    if status_text in READY_STATUSES or status_cn in READY_STATUSES:
        return "ready"
    for field in ready_fields:
        if _to_text(payload.get(field)):
            return "ready"
    if payload.get("last_success"):
        return "stale"
    return "waiting"


def _data_capability_item(data_capability_console: Any = None) -> dict:
    console = _as_mapping(data_capability_console)
    blocked_count = _to_int(console.get("blocked_count")) or len(_as_list(console.get("blocked_items")))
    manual_count = _to_int(console.get("manual_count")) or len(_as_list(console.get("manual_items")))
    stale_count = _to_int(console.get("stale_count")) or len(_as_list(console.get("stale_items")))
    ready_count = _to_int(console.get("ready_count")) or len(_as_list(console.get("ready_items")))
    headline = _to_text(console.get("headline"))
    readiness = _to_text(console.get("decision_readiness_label"))
    if blocked_count:
        status = "blocked"
    elif manual_count or stale_count:
        status = "stale"
    elif ready_count or "可进入证据链" in readiness or "已读取" in headline:
        status = "ready"
    else:
        status = "waiting"
    summary = headline or f"可用 {ready_count}｜阻断 {blocked_count}｜待手动 {manual_count}｜缓存/待验证 {stale_count}"
    guardrail = _to_text(
        console.get("safe_mode_text"),
        "页面打开不会自动请求 Tushare、AkShare、yfinance 或 Supabase；缺口必须按钮触发恢复。",
    )
    return _status_item("data_capability", "数据能力", status, summary, guardrail, "command_center_data_capability_console")


def _analysis_methods_item(analysis_method_packet: Any = None, market_profile_evidence: Any = None) -> dict:
    packet = _as_mapping(analysis_method_packet)
    profile = _as_mapping(market_profile_evidence)
    methods = [_as_mapping(item) for item in _as_list(packet.get("methods")) if _as_mapping(item)]
    market = _to_text(packet.get("market") or profile.get("market_label") or profile.get("market_type"), "市场类型待确认")
    if market in {"未知", "市场类型待确认", "未识别"}:
        status = "waiting"
    else:
        passed = [item for item in methods if _to_text(item.get("status")) == "通过"]
        failed = [item for item in methods if _to_text(item.get("status")) == "失败"]
        pending = [item for item in methods if _to_text(item.get("status")) in {"待验证", "数据不足"}]
        if failed:
            status = "blocked"
        elif passed and not pending:
            status = "ready"
        elif passed or methods or profile:
            status = "stale"
        else:
            status = "waiting"
    summary = _to_text(packet.get("summary") or profile.get("summary"), f"{market} 分析方法待验证。")
    guardrail = "分析方法只解释当前市场口径；数据不足时必须显示待验证，不自动生成交易结论。"
    return _status_item("analysis_methods", "分析方法", status, summary, guardrail, "command_center_analysis_method_packet")


def _projection_item(projection_packet: Any = None) -> dict:
    packet = _as_mapping(projection_packet)
    status = _packet_status(packet)
    recovery = _as_mapping(packet.get("path_recovery_impact"))
    recovery_state = _to_text(recovery.get("evidence_state") or recovery.get("status"))
    if recovery_state in {"blocked", "failed", "permission_denied", "阻断"}:
        status = "blocked"
    elif packet.get("is_fallback") and status == "ready":
        status = "waiting"
    basis = _to_text(packet.get("path_basis") or packet.get("market_method_summary"))
    summary = basis or _to_text(packet.get("note"), "未来 5-10 日路径待生成。")
    guardrail = "趋势推演是条件路径，不是价格预测；不会调用 DeepSeek 或外部行情接口。"
    return _status_item("projection", "趋势推演", status, summary, guardrail, "command_center_projection_packet")


def _strategy_item(strategy_packet: Any = None) -> dict:
    status = _packet_status(strategy_packet, ready_fields=("action", "summary", "position_advice"))
    packet = _as_mapping(strategy_packet)
    action = _to_text(packet.get("action"), "策略执行建议待生成")
    confidence = _to_text(packet.get("confidence"), "低")
    summary = _to_text(packet.get("summary"), f"{action}｜置信度 {confidence}")
    guardrail = "策略执行只基于现有结构化结果；不自动跑回测、不自动调用 DeepSeek。"
    return _status_item("strategy_execution", "策略执行", status, summary, guardrail, "strategy_execution_packet")


def _decision_item(decision_packet: Any = None) -> dict:
    status = _packet_status(decision_packet, ready_fields=("overall_action", "risk_level", "position_mode"))
    packet = _as_mapping(decision_packet)
    action = _to_text(packet.get("overall_action"), "等待")
    risk = _to_text(packet.get("risk_level"), "中")
    summary = _to_text(packet.get("reason_summary"), f"总动作 {action}｜风险 {risk}")
    guardrail = "今日总决策不自动交易；执行前仍需价格、纪律、仓位和数据缺口共同确认。"
    return _status_item("decision", "今日总决策", status, summary, guardrail, "command_center_decision_packet")


def _deepseek_item(*packets: Any) -> dict:
    called = any(bool(_as_mapping(packet).get("deepseek_called")) for packet in packets)
    status = "ready" if called else "manual"
    summary = "DeepSeek 已解释当前结构化结果。" if called else "DeepSeek 未调用；需要用户点击按钮后才解释当前 packet。"
    guardrail = "DeepSeek 只解释，不决定仓位；页面打开、刷新基础数据和生成规则结论都不会自动调用。"
    item = _status_item("deepseek", "DeepSeek解释", status, summary, guardrail, "manual_deep")
    item["deepseek_called"] = called
    item["external_call_policy"] = "manual_button_only"
    return item


def _recovery_loop_key(action: Mapping[str, Any]) -> str:
    source_type = _to_text(action.get("source_type"))
    writes_packet = _to_text(action.get("writes_packet"))
    if source_type in {"data_source", "data_health_timeline", "a_share"}:
        return "data_capability"
    if "strategy" in writes_packet or "discipline" in writes_packet or "quant" in writes_packet:
        return "strategy_execution"
    if "decision" in writes_packet:
        return "decision"
    if source_type in {"next_ticket_evidence", "a_share_fact", "legacy_migration", "legacy_tool"}:
        return "projection"
    return "data_capability"


def _recovery_loop_label(loop_key: str) -> str:
    return {
        "data_capability": "数据能力",
        "analysis_methods": "分析方法",
        "projection": "趋势推演",
        "strategy_execution": "策略执行",
        "decision": "今日总决策",
    }.get(loop_key, "数据能力")


def _normalize_recovery_action(action: Any) -> dict:
    item = _as_mapping(action)
    if not item:
        return {}
    loop_key = _recovery_loop_key(item)
    label = _to_text(item.get("label"), "恢复项")
    writes_packet = _to_text(item.get("writes_packet"), "command_center_packet")
    return {
        "key": _to_text(item.get("key"), writes_packet or label),
        "loop_key": loop_key,
        "loop_label": _recovery_loop_label(loop_key),
        "label": label,
        "priority_label": _to_text(item.get("priority_label"), "P1 执行前验证"),
        "tone": _to_text(item.get("tone") or item.get("recovery_result_tone"), "missing"),
        "status": _to_text(item.get("status"), "waiting"),
        "status_label": _to_text(item.get("status_label") or item.get("recovery_result_status_label"), "待验证"),
        "action_label": _to_text(item.get("action_label"), f"手动恢复{label}"),
        "navigation_label": _to_text(item.get("navigation_label"), "从首页恢复队列进入对应手动工具。"),
        "toolbox_entry": _to_text(item.get("toolbox_entry"), "高级工具箱"),
        "workspace_target": _to_text(item.get("workspace_target"), "高级工具箱（旧版保留）"),
        "workspace_state_key": _to_text(item.get("workspace_state_key"), "workspace_mode_v2"),
        "legacy_tab_state_key": _to_text(item.get("legacy_tab_state_key"), "legacy_workspace_selected_tab"),
        "legacy_tab": _to_text(item.get("legacy_tab")),
        "writes_packet": writes_packet,
        "refresh_policy": _to_text(item.get("refresh_policy"), "button_gated"),
        "decision_impact": _to_text(
            item.get("decision_impact") or item.get("decision_guardrail") or item.get("diagnostic_answer"),
            "未恢复前不能作为加仓、追高或加融资依据。",
        ),
        "recovery_button_context": _to_text(
            item.get("recovery_button_context") or item.get("button_context"),
            f"按钮只打开 {label} 的恢复入口；不会自动调用 DeepSeek、回测或全市场扫描。",
        ),
        "external_call_policy": "navigation_only",
        "deepseek_called": False,
    }


def _recovery_actions_from_center(data_recovery_center: Any = None, limit: int = 3) -> list[dict]:
    center = _as_mapping(data_recovery_center)
    candidates = _as_list(center.get("decision_priority_queue")) or _as_list(center.get("actions"))
    actions = []
    seen = set()
    for raw in candidates:
        action = _normalize_recovery_action(raw)
        if not action:
            continue
        dedupe_key = (action["loop_key"], action["writes_packet"], action["label"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        actions.append(action)
        if len(actions) >= max(1, int(limit or 3)):
            break
    return actions


def build_command_center_loop_status_view_model(
    data_capability_console: Any = None,
    analysis_method_packet: Any = None,
    market_profile_evidence: Any = None,
    projection_packet: Any = None,
    strategy_packet: Any = None,
    decision_packet: Any = None,
    deepseek_summary: Any = None,
    data_recovery_center: Any = None,
) -> dict:
    items = [
        _data_capability_item(data_capability_console),
        _analysis_methods_item(analysis_method_packet, market_profile_evidence),
        _projection_item(projection_packet),
        _strategy_item(strategy_packet),
        _decision_item(decision_packet),
        _deepseek_item(deepseek_summary, strategy_packet, decision_packet, projection_packet, analysis_method_packet),
    ]
    recovery_actions = _recovery_actions_from_center(data_recovery_center)
    if recovery_actions:
        actions_by_loop: dict[str, list[dict]] = {}
        for action in recovery_actions:
            actions_by_loop.setdefault(action["loop_key"], []).append(action)
        for item in items:
            item_actions = actions_by_loop.get(item["key"], [])
            if item_actions:
                item["recovery_actions"] = item_actions
                item["recovery_action_count"] = len(item_actions)
    blocked_count = len([item for item in items if item["status"] == "blocked"])
    waiting_count = len([item for item in items if item["status"] == "waiting"])
    stale_count = len([item for item in items if item["status"] == "stale"])
    ready_count = len([item for item in items if item["status"] == "ready"])
    manual_count = len([item for item in items if item["status"] == "manual"])
    if blocked_count:
        tone = "failed"
        headline = f"阻断 {blocked_count}｜待验证 {waiting_count}｜缓存 {stale_count}｜已就绪 {ready_count}"
        summary = "先处理阻断项，再考虑执行；不能把数据缺口当成已验证依据。"
    elif waiting_count or stale_count:
        tone = "stale"
        headline = f"已就绪 {ready_count}｜待验证 {waiting_count}｜缓存 {stale_count}｜手动 {manual_count}"
        summary = "闭环已部分成形；执行前仍需补齐待验证环节。"
    else:
        tone = "ready"
        headline = f"闭环已就绪 {ready_count}｜DeepSeek 手动 {manual_count}"
        summary = "结构化链路可用于复核今日动作；仍不是自动交易指令。"
    return {
        "title": "决策闭环状态",
        "status": "blocked" if blocked_count else ("partial" if waiting_count or stale_count else "ready"),
        "tone": tone,
        "headline": headline,
        "summary": summary,
        "items": items,
        "blocked_count": blocked_count,
        "waiting_count": waiting_count,
        "stale_count": stale_count,
        "ready_count": ready_count,
        "manual_count": manual_count,
        "recovery_actions": recovery_actions,
        "recovery_action_count": len(recovery_actions),
        "recovery_summary": (
            f"优先恢复 {recovery_actions[0]['loop_label']}：{recovery_actions[0]['label']}，回流 {recovery_actions[0]['writes_packet']}。"
            if recovery_actions
            else "暂无闭环恢复入口；继续查看快照或使用刷新今日基础数据。"
        ),
        "deepseek_called": any(bool(item.get("deepseek_called")) for item in items),
        "safe_mode_text": "页面打开只读取本地 packet / 快照；DeepSeek、回测、全市场扫描和重型数据接口仍保持按钮触发。",
        "external_call_policy": "not_triggered",
        "source": "command_center_loop_status",
    }
