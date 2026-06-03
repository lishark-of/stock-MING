from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


AVAILABLE_STATES = {"available", "ready", "ok", "success"}
BLOCKED_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
MANUAL_STATES = {"requires_manual_refresh"}
STALE_STATES = {"empty_recent", "stale_cache", "fallback_used", "unknown", "missing"}

STATE_LABELS = {
    "available": "可用",
    "permission_denied": "权限不足",
    "disabled_this_session": "本会话跳过",
    "not_configured": "未配置",
    "network_failed": "网络失败",
    "failed": "调用失败",
    "empty_recent": "近期无数据",
    "stale_cache": "使用缓存",
    "fallback_used": "替代口径",
    "requires_manual_refresh": "需要手动刷新",
    "unknown": "待验证",
    "missing": "待刷新",
}

MANUAL_ACTIONS = {
    "moneyflow": {
        "action_key": "manual_check_moneyflow",
        "button_label": "重新检测个股资金流",
        "toolbox_entry": "高级工具箱入口 / 数据源体检",
        "writes_packet": "command_center_moneyflow_packet / a_share_professional_data_capability",
    },
    "dragon_tiger": {
        "action_key": "manual_check_dragon_tiger",
        "button_label": "重新检测龙虎榜",
        "toolbox_entry": "高级工具箱入口 / 下一票雷达",
        "writes_packet": "command_center_dragon_tiger_packet / command_center_facts_packet",
    },
    "margin": {
        "action_key": "manual_check_margin_detail",
        "button_label": "重新检测融资融券权限",
        "toolbox_entry": "高级工具箱入口 / 融资 ETF",
        "writes_packet": "command_center_margin_packet / a_share_professional_data_capability",
    },
    "limit_emotion": {
        "action_key": "manual_check_limit_emotion",
        "button_label": "重新检测涨跌停/情绪",
        "toolbox_entry": "高级工具箱入口 / 数据源体检",
        "writes_packet": "command_center_limit_emotion_packet / command_center_facts_packet",
    },
    "chip_radar": {
        "action_key": "manual_check_chip_radar",
        "button_label": "重新检测筹码/胜率",
        "toolbox_entry": "高级工具箱入口 / 量化推演",
        "writes_packet": "command_center_chip_packet / command_center_facts_packet",
    },
    "hard_risk": {
        "action_key": "manual_check_hard_risk",
        "button_label": "运行天眼风控检测",
        "toolbox_entry": "高级工具箱入口 / 天眼风控",
        "writes_packet": "command_center_hard_risk_packet / command_center_facts_packet",
    },
}

CORE_CAPABILITIES = (
    {
        "key": "moneyflow",
        "label": "个股资金流",
        "api_hint": "moneyflow",
        "terms": ("moneyflow", "资金流"),
        "decision_role": "验证资金是否支持当前动作，不替代价格纪律。",
        "migration_priority": 1,
        "decision_chain_stage": "市场分析方法 → 策略执行验证",
        "home_module": "今日总决策 / 策略执行实验室",
        "migration_target": "command_center_moneyflow_packet 回流到资金流证据和策略条件。",
    },
    {
        "key": "dragon_tiger",
        "label": "龙虎榜",
        "api_hint": "top_list / top_inst",
        "terms": ("dragon_tiger", "top_list", "top_inst", "龙虎榜"),
        "decision_role": "识别席位行为和情绪线索，不单独构成买入理由。",
        "migration_priority": 3,
        "decision_chain_stage": "市场分析方法 → 下一票候选验证",
        "home_module": "下一票 Top3 / A股证据雷达",
        "migration_target": "command_center_dragon_tiger_packet 回流到候选证据和情绪验证。",
    },
    {
        "key": "margin",
        "label": "融资融券",
        "api_hint": "margin_detail",
        "terms": ("margin", "margin_detail", "融资融券"),
        "decision_role": "观察杠杆变化；权限不足时不能假设融资改善。",
        "migration_priority": 2,
        "decision_chain_stage": "数据能力状态 → 风险预算",
        "home_module": "ETF / 融资动作",
        "migration_target": "command_center_margin_packet 回流到融资比例和杠杆风险。",
    },
    {
        "key": "limit_emotion",
        "label": "涨跌停/情绪",
        "api_hint": "stk_limit / limit_list_d / limit_cpt_list",
        "terms": ("limit_emotion", "stk_limit", "limit_list_d", "limit_cpt_list", "涨跌停", "情绪"),
        "decision_role": "识别过热、追高和情绪边界。",
        "migration_priority": 2,
        "decision_chain_stage": "市场分析方法 → 趋势路径风险",
        "home_module": "5-10 日趋势推演 / 风险警报",
        "migration_target": "command_center_limit_emotion_packet 回流到路径风险和不追高提示。",
    },
    {
        "key": "chip_radar",
        "label": "筹码/胜率",
        "api_hint": "cyq_perf / cyq_chips",
        "terms": ("chip_radar", "cyq_perf", "cyq_chips", "筹码", "胜率"),
        "decision_role": "验证压力位、筹码结构和胜率口径；缺失时保持待验证。",
        "migration_priority": 3,
        "decision_chain_stage": "趋势推演 → 策略执行验证",
        "home_module": "策略执行实验室 / 趋势推演",
        "migration_target": "command_center_chip_packet 回流到路径触发条件和纪律证据。",
    },
    {
        "key": "hard_risk",
        "label": "公告/硬风险",
        "api_hint": "anns_d / forecast / holder / pledge / unlock",
        "terms": (
            "hard_risk",
            "announcements",
            "anns_d",
            "forecast",
            "holder_reduction",
            "stk_holdertrade",
            "share_float",
            "pledge",
            "stk_surv",
            "公告",
            "减持",
            "质押",
            "解禁",
        ),
        "decision_role": "排查公告、减持、质押、解禁等硬风险；无记录不能写成无风险。",
        "migration_priority": 1,
        "decision_chain_stage": "数据能力状态 → 今日总决策阻断",
        "home_module": "风险警报 / 今日总决策",
        "migration_target": "command_center_hard_risk_packet 回流到禁止动作和降风险条件。",
    },
)


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


def normalize_state(value: Any) -> str:
    text = to_text(value).lower()
    if text in AVAILABLE_STATES | BLOCKED_STATES | MANUAL_STATES | STALE_STATES:
        return text
    if "权限" in text or "denied" in text or "unauthorized" in text:
        return "permission_denied"
    if "跳过" in text or "skip" in text:
        return "disabled_this_session"
    if "缓存" in text:
        return "stale_cache"
    if "手动" in text:
        return "requires_manual_refresh"
    if "无数据" in text or "近期无" in text or "暂无" in text or "未取得" in text:
        return "empty_recent"
    if "未配置" in text:
        return "not_configured"
    if "网络" in text or "timeout" in text:
        return "network_failed"
    if "失败" in text or "error" in text:
        return "failed"
    if "可用" in text or "通过" in text:
        return "available"
    return "unknown"


def tone_for_state(state: str) -> str:
    if state in AVAILABLE_STATES:
        return "ready"
    if state in BLOCKED_STATES:
        return "failed"
    if state in {"stale_cache", "fallback_used"}:
        return "stale"
    return "missing"


def _capability_rows(data_capability_packet: Any = None, facts_packet: Any = None) -> list[dict]:
    rows = []
    for packet in (as_mapping(data_capability_packet), as_mapping(facts_packet)):
        source = to_text(packet.get("source"), "A股数据能力")
        for raw in as_list(packet.get("items")):
            payload = as_mapping(raw)
            if not payload:
                continue
            state = normalize_state(payload.get("state") or payload.get("capability_state") or payload.get("status"))
            rows.append(
                {
                    "key": to_text(payload.get("key") or payload.get("section") or payload.get("api"), "a_share_capability"),
                    "section": to_text(payload.get("section") or payload.get("key")),
                    "label": to_text(payload.get("label") or payload.get("api") or payload.get("section"), "A股数据"),
                    "api": to_text(payload.get("api")),
                    "state": state,
                    "status_label": to_text(payload.get("status") or payload.get("capability_label"), STATE_LABELS.get(state, "待验证")),
                    "source": to_text(payload.get("source") or source, source),
                    "latest_date": to_text(payload.get("latest_date") or payload.get("updated_at")),
                    "reason": to_text(payload.get("error") or payload.get("reason") or payload.get("message") or payload.get("risk")),
                    "action_hint": to_text(payload.get("action_hint")),
                }
            )
    return rows


def _matches(capability: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    haystack = " ".join(
        to_text(row.get(key)).lower()
        for key in ("key", "section", "label", "api", "source", "status_label", "reason", "action_hint")
    )
    return any(term.lower() in haystack for term in capability["terms"])


def _aggregate_state(rows: list[dict]) -> tuple[str, str]:
    states = [row.get("state") for row in rows]
    if not rows:
        return "missing", "待刷新"
    if "permission_denied" in states:
        return "permission_denied", "权限不足"
    if "disabled_this_session" in states:
        return "disabled_this_session", "本会话跳过"
    if any(state in {"not_configured", "network_failed", "failed"} for state in states):
        return "failed", "调用失败/未配置"
    if any(state in MANUAL_STATES for state in states):
        return "requires_manual_refresh", "需要手动刷新"
    if any(state in {"stale_cache", "fallback_used"} for state in states):
        return "stale_cache", "使用缓存"
    if any(state in {"empty_recent", "unknown", "missing"} for state in states):
        if any(state in AVAILABLE_STATES for state in states):
            return "fallback_used", "部分可用/待验证"
        return "empty_recent", "近期无数据/待验证"
    if all(state in AVAILABLE_STATES for state in states):
        return "available", "可用"
    return "unknown", "待验证"


def _decision_impact(state: str, label: str) -> str:
    if state == "available":
        return f"{label}可进入证据链，但仍需结合价格、纪律和仓位。"
    if state == "permission_denied":
        return f"{label}权限不足，不能把缺失数据当成利好或加仓依据。"
    if state == "disabled_this_session":
        return f"{label}本会话已跳过，避免旧页面重复卡顿；如权限恢复需手动检测。"
    if state == "requires_manual_refresh":
        return f"{label}需要手动刷新，页面打开不会自动触发。"
    if state == "stale_cache":
        return f"{label}正在使用缓存，执行前必须复核交易日和更新时间。"
    if state == "empty_recent":
        return f"{label}近期无记录或待验证，不能推导为无风险。"
    if state in {"failed", "not_configured", "network_failed"}:
        return f"{label}不可用，只能展示上次成功或安全空态。"
    return f"{label}待验证，当前不能作为核心依据。"


def _next_action(state: str, label: str) -> str:
    if state == "available":
        return f"核对 {label} 日期和标的口径，再进入决策链。"
    if state == "permission_denied":
        return f"检查 {label} 对应 Tushare 接口权限/积分。"
    if state == "disabled_this_session":
        return f"如权限已恢复，手动重新检测 {label}。"
    if state == "requires_manual_refresh":
        return f"点击对应按钮后再刷新 {label}。"
    if state == "stale_cache":
        return f"需要最新口径时手动刷新 {label}。"
    if state == "empty_recent":
        return f"确认是否交易日、是否已发布、标的是否覆盖 {label}。"
    return f"保留 {label} 安全空态或上次成功结果。"


def _manual_action(capability: Mapping[str, Any], state: str, status_label: str) -> dict:
    config = MANUAL_ACTIONS.get(str(capability.get("key")), {})
    return {
        "action_key": to_text(config.get("action_key"), f"manual_check_{capability.get('key') or 'a_share'}"),
        "button_label": to_text(config.get("button_label"), f"手动检测{capability.get('label') or 'A股数据'}"),
        "toolbox_entry": to_text(config.get("toolbox_entry"), "高级工具箱入口 / 数据源体检"),
        "writes_packet": to_text(config.get("writes_packet"), "command_center_facts_packet"),
        "refresh_policy": "button_gated",
        "status_label": status_label,
        "reason": _next_action(state, to_text(capability.get("label"), "A股数据")),
        "deepseek_called": False,
    }


def build_a_share_capability_matrix(
    data_capability_packet: Any = None,
    facts_packet: Any = None,
) -> dict:
    rows = _capability_rows(data_capability_packet, facts_packet)
    items = []
    for capability in CORE_CAPABILITIES:
        matches = [row for row in rows if _matches(capability, row)]
        state, status_label = _aggregate_state(matches)
        manual_action = _manual_action(capability, state, status_label)
        items.append(
            {
                "key": capability["key"],
                "label": capability["label"],
                "api_hint": capability["api_hint"],
                "state": state,
                "status_label": status_label,
                "tone": tone_for_state(state),
                "decision_role": capability["decision_role"],
                "migration_priority": capability["migration_priority"],
                "decision_chain_stage": capability["decision_chain_stage"],
                "home_module": capability["home_module"],
                "migration_target": capability["migration_target"],
                "decision_impact": _decision_impact(state, capability["label"]),
                "next_action": _next_action(state, capability["label"]),
                "manual_action": manual_action,
                "matched_items": matches[:5],
            }
        )
    available = [item for item in items if item["state"] in AVAILABLE_STATES]
    blocked = [item for item in items if item["state"] in BLOCKED_STATES]
    manual = [item for item in items if item["state"] in MANUAL_STATES]
    stale = [item for item in items if item["state"] in STALE_STATES]
    if not rows:
        summary = "尚未检测 A股专业数据能力；页面打开不会自动请求 Tushare。"
        status = "missing"
        tone = "missing"
    else:
        summary = f"A股数据能力：可用 {len(available)}｜受限/失败 {len(blocked)}｜手动 {len(manual)}｜缓存/待验证 {len(stale)}"
        status = "blocked" if blocked else ("partial" if manual or stale else "ready")
        tone = "failed" if blocked else ("stale" if manual or stale else "ready")
    manual_action_queue = [
        item["manual_action"]
        for item in items
        if item["state"] not in AVAILABLE_STATES
    ]
    migration_queue = [
        {
            "key": item["key"],
            "label": item["label"],
            "priority": item["migration_priority"],
            "state": item["state"],
            "status_label": item["status_label"],
            "decision_chain_stage": item["decision_chain_stage"],
            "home_module": item["home_module"],
            "migration_target": item["migration_target"],
            "manual_action": item["manual_action"],
            "deepseek_called": False,
        }
        for item in sorted(items, key=lambda row: (row["migration_priority"], row["label"]))
        if item["state"] not in AVAILABLE_STATES
    ]
    return {
        "status": status,
        "tone": tone,
        "title": "A股数据能力矩阵",
        "summary": summary,
        "items": items,
        "manual_action_queue": manual_action_queue,
        "migration_queue": migration_queue,
        "available_count": len(available),
        "blocked_count": len(blocked),
        "manual_count": len(manual),
        "stale_count": len(stale),
        "manual_note": "本矩阵只读取本地 packet；不会自动调用 Tushare、AkShare、yfinance、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }


def build_a_share_capability_summary_text(matrix_packet: Any = None) -> str:
    packet = as_mapping(matrix_packet)
    items = as_list(packet.get("items"))
    if not packet or not items or packet.get("status") == "missing":
        return "尚未检测 A股数据能力"
    available_count = int(packet.get("available_count") or 0)
    blocked_count = int(packet.get("blocked_count") or 0)
    manual_count = int(packet.get("manual_count") or 0)
    stale_count = int(packet.get("stale_count") or 0)
    pending_count = manual_count + stale_count
    return f"可用 {available_count}｜受限 {blocked_count}｜待验证 {pending_count}"
