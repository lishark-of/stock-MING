from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from market_data_capability import (
    decision_impact_for_capability_state,
    next_action_for_capability_state,
    normalize_capability_state_value,
    tone_for_capability_state,
)


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

GAP_CAUSE_LABELS = {
    "available": "已有可用返回",
    "permission_scope": "接口权限/积分",
    "session_skip": "本会话跳过",
    "publish_window": "交易日/标的覆盖",
    "cache_guard": "缓存防白屏",
    "fallback_proxy": "替代口径",
    "manual_gate": "按钮触发",
    "configuration": "配置或网络",
    "not_checked": "尚未检测",
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
    return normalize_capability_state_value(value)


def tone_for_state(state: str) -> str:
    return tone_for_capability_state(state)


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
    return decision_impact_for_capability_state(state, label)


def _next_action(state: str, label: str) -> str:
    return next_action_for_capability_state(state, label)


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


def _gap_reason_for_state(item: Mapping[str, Any]) -> str:
    label = to_text(item.get("label"), "A股数据")
    state = normalize_state(item.get("state"))
    if state == "available":
        return f"{label}已有可用返回，但仍需核对交易日和当前标的。"
    if state == "permission_denied":
        return f"{label}不是没搜到，而是 Tushare 专业接口权限/积分不足。"
    if state == "disabled_this_session":
        return f"{label}此前已被判定受限或失败，本会话跳过重复请求以避免卡顿。"
    if state == "empty_recent":
        return f"{label}近期无记录，可能是非交易日、尚未发布、标的未上榜或接口不覆盖。"
    if state == "stale_cache":
        return f"{label}正在使用缓存；这是防白屏结果，不是实时已验证事实。"
    if state == "fallback_used":
        return f"{label}使用替代口径；不能等同于原始 Tushare 专业事实。"
    if state == "requires_manual_refresh":
        return f"{label}需要按钮触发；页面打开不会自动请求 Tushare。"
    if state in {"not_configured", "network_failed", "failed"}:
        return f"{label}当前不可用；先保留安全空态或上次成功结果。"
    return f"{label}尚未检测；不能把缺失写成无风险。"


def _gap_cause_code_for_state(item: Mapping[str, Any]) -> str:
    state = normalize_state(item.get("state"))
    if state == "available":
        return "available"
    if state == "permission_denied":
        return "permission_scope"
    if state == "disabled_this_session":
        return "session_skip"
    if state == "empty_recent":
        return "publish_window"
    if state == "stale_cache":
        return "cache_guard"
    if state == "fallback_used":
        return "fallback_proxy"
    if state == "requires_manual_refresh":
        return "manual_gate"
    if state in {"not_configured", "network_failed", "failed"}:
        return "configuration"
    return "not_checked"


def _gap_cause_label(item: Mapping[str, Any]) -> str:
    return GAP_CAUSE_LABELS.get(_gap_cause_code_for_state(item), "尚未检测")


def _why_previous_full_not_enough(item: Mapping[str, Any]) -> str:
    label = to_text(item.get("label"), "A股数据")
    api_hint = to_text(item.get("api_hint") or item.get("api"), "Tushare 专业接口")
    cause_code = _gap_cause_code_for_state(item)
    if cause_code == "permission_scope":
        return f"之前“拉满”多半覆盖基础行情或已授权接口；{label} 的 {api_hint} 仍需要单独权限/积分。"
    if cause_code == "session_skip":
        return f"{label}此前已被判定受限或失败，本会话为了防卡顿跳过重复请求；这不是数据被清空。"
    if cause_code == "publish_window":
        return f"{label}可能接口可用但近窗口无记录；非交易日、尚未发布、标的未上榜都会让结果为空。"
    if cause_code == "cache_guard":
        return f"{label}现在显示的是上次成功缓存；这是为了防白屏，不代表今天已经重新验证。"
    if cause_code == "fallback_proxy":
        return f"{label}当前使用替代口径；能辅助观察，但不能当作原始 {api_hint} 已恢复。"
    if cause_code == "manual_gate":
        return f"{label}被设置为手动按钮触发；首页打开不会自动请求 {api_hint}。"
    if cause_code == "available":
        return f"{label}已有可用返回；仍要核对日期、标的和接口口径是否匹配当前决策。"
    if cause_code == "configuration":
        return f"{label}当前更像配置、网络或接口调用失败；先修复环境，再手动验证。"
    return f"{label}尚未检测；不能用“之前拉过”证明当前这个专业接口已可用。"


def _safe_recovery_steps(item: Mapping[str, Any]) -> list[str]:
    label = to_text(item.get("label"), "A股数据")
    manual_action = as_mapping(item.get("manual_action"))
    button_label = to_text(manual_action.get("button_label"), f"手动检测{label}")
    writes_packet = to_text(manual_action.get("writes_packet"), "command_center_facts_packet")
    toolbox_entry = to_text(manual_action.get("toolbox_entry"), "高级工具箱入口 / 数据源体检")
    cause_code = _gap_cause_code_for_state(item)
    first_step = {
        "permission_scope": f"先确认 {label} 对应 Tushare 专业接口权限/积分。",
        "session_skip": f"先确认 {label} 权限或接口状态已恢复，再解除本会话跳过的影响。",
        "publish_window": f"先核对 {label} 的交易日、发布时间、窗口期和标的覆盖。",
        "cache_guard": f"先核对 {label} 的缓存日期、来源和是否匹配当前标的。",
        "fallback_proxy": f"先确认 {label} 当前是替代口径，不是原始接口事实。",
        "manual_gate": f"确认确实需要最新 {label} 后再手动触发。",
        "configuration": f"先检查 {label} 的 token、网络或接口错误。",
        "available": f"先核对 {label} 的日期、来源和当前标的。",
    }.get(cause_code, f"先复核 {label} 的状态、来源和适用范围。")
    return [
        first_step,
        f"进入 {toolbox_entry}，点击“{button_label}”。",
        f"结果回流 {writes_packet} 后，再进入综合中心决策链。",
    ]


def _gap_guardrail_for_state(item: Mapping[str, Any]) -> str:
    label = to_text(item.get("label"), "A股数据")
    state = normalize_state(item.get("state"))
    if state == "available":
        return f"{label}可辅助验证，但不单独决定买卖。"
    if state in {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}:
        return f"{label}未恢复前阻断加仓、追高和加融资。"
    if state in {"empty_recent", "stale_cache", "fallback_used", "requires_manual_refresh"}:
        return f"{label}执行前必须复核来源、日期和覆盖口径。"
    return f"{label}待验证时只观察，不放大仓位。"


def _diagnostic_answer_for_state(item: Mapping[str, Any]) -> str:
    label = to_text(item.get("label"), "A股数据")
    api_hint = to_text(item.get("api_hint") or item.get("api"), "Tushare 专业接口")
    state = normalize_state(item.get("state"))
    if state == "permission_denied":
        return (
            f"{label}不是“没搜到”，而是 {api_hint} 权限/积分不足；"
            "之前拉满基础数据不代表这个专业接口已开通。"
        )
    if state == "disabled_this_session":
        return (
            f"{label}此前已判定受限或失败，本会话跳过重复请求以防卡顿；"
            "确认权限恢复后再手动检测。"
        )
    if state == "empty_recent":
        return (
            f"{label}接口可能可读但近窗口无记录；常见原因是非交易日、数据尚未发布、"
            "标的未上榜或接口暂不覆盖。"
        )
    if state == "stale_cache":
        return f"{label}当前使用上次成功缓存；这是防白屏结果，不是实时新数据。"
    if state == "fallback_used":
        return f"{label}使用替代口径；可辅助观察，但不能等同于原始 Tushare 专业事实。"
    if state == "requires_manual_refresh":
        return f"{label}需要按钮触发；页面打开不会自动请求 {api_hint}。"
    if state == "available":
        return f"{label}已有可用返回；仍需核对交易日、来源和是否匹配当前标的。"
    return f"{label}尚未形成可验证结果；当前只能记录为数据缺口。"


def _gap_action_mode(state: str) -> str:
    normalized = normalize_state(state)
    if normalized == "available":
        return "usable"
    if normalized in BLOCKED_STATES:
        return "blocked"
    if normalized in {"stale_cache", "fallback_used"}:
        return "verify_cache"
    if normalized == "empty_recent":
        return "verify_window"
    if normalized == "requires_manual_refresh":
        return "manual_required"
    return "missing"


def _count_by_state(items: list[dict], states: set[str]) -> int:
    return len([item for item in items if normalize_state(item.get("state")) in states])


def _cause_summary(items: list[dict]) -> str:
    if not items:
        return "原因分类：暂无"
    counts = {}
    for item in items:
        label = GAP_CAUSE_LABELS.get(to_text(item.get("cause_code")), "尚未检测")
        counts[label] = counts.get(label, 0) + 1
    return "原因分类：" + "｜".join(f"{label} {count}" for label, count in counts.items())


def build_tushare_gap_explainer(matrix_packet: Any = None) -> dict:
    packet = as_mapping(matrix_packet)
    raw_items = packet.get("items") if packet else matrix_packet
    rows = [as_mapping(item) for item in as_list(raw_items) if as_mapping(item)]
    if not rows:
        return {
            "title": "Tushare 专业接口为什么搜不到",
            "status": "missing",
            "tone": "missing",
            "headline": "尚未检测 A股专业接口",
            "summary": "页面打开不会自动请求 Tushare；需要手动刷新或读取上次快照。",
            "cause_summary": "原因分类：暂无",
            "plain_answer": "还没有本地检测结果；页面打开不会自动拉取 Tushare 专业接口，以避免白屏和卡顿。",
            "explanation": "Tushare token 可用不代表龙虎榜、融资融券、涨跌停/情绪、筹码等专业接口都已验证。",
            "items": [],
            "next_action": "先刷新今日基础数据，或在数据源体检里手动检测对应接口。",
            "deepseek_called": False,
            "external_call_policy": "not_triggered",
        }

    blocked = [item for item in rows if normalize_state(item.get("state")) in BLOCKED_STATES]
    manual = [item for item in rows if normalize_state(item.get("state")) in MANUAL_STATES]
    stale = [item for item in rows if normalize_state(item.get("state")) in STALE_STATES]
    available = [item for item in rows if normalize_state(item.get("state")) in AVAILABLE_STATES]
    if blocked:
        status = "blocked"
        tone = "failed"
        headline = "拉满基础数据 ≠ 专业接口全可用"
        plain_answer = (
            "之前“拉满”通常表示基础行情或已授权接口已取到；现在搜不到，多半是细分专业接口权限、"
            "本会话跳过、交易日发布或标的覆盖问题，不是系统自动把数据清空。"
        )
        next_action = "先处理权限不足、本会话跳过或失败项；未恢复前不要把缺失写成利好。"
    elif manual or stale:
        status = "partial"
        tone = "stale"
        headline = "部分接口是缓存、近期无记录或待手动刷新"
        plain_answer = (
            "当前不是完全没数据，而是部分结果来自缓存、近期无记录或需要手动刷新；"
            "执行前要核对交易日、来源和覆盖口径。"
        )
        next_action = "执行前复核交易日、来源和覆盖口径；需要最新数据时再点手动检测。"
    elif available:
        status = "ready"
        tone = "ready"
        headline = "A股专业接口当前可辅助验证"
        plain_answer = "当前有可用 Tushare 证据；仍要核对交易日、接口口径和当前标的，不能单独决定买卖。"
        next_action = "继续把可用接口回流到综合中心 packet，并结合价格纪律与仓位规则。"
    else:
        status = "missing"
        tone = "missing"
        headline = "A股专业接口仍待验证"
        plain_answer = "当前缺少足够本地检测结果；综合中心会保留安全空态或上次成功结果，不自动请求重接口。"
        next_action = "保留安全空态或上次成功结果；不要自动请求重接口。"
    ordered = blocked + manual + stale + available
    seen = set()
    items = []
    for raw in ordered:
        key = to_text(raw.get("key"), raw.get("label") or "a_share_capability")
        if key in seen:
            continue
        seen.add(key)
        manual_action = as_mapping(raw.get("manual_action"))
        state = normalize_state(raw.get("state"))
        cause_code = _gap_cause_code_for_state(raw)
        items.append(
            {
                "key": key,
                "label": to_text(raw.get("label"), "A股数据"),
                "api_hint": to_text(raw.get("api_hint"), "Tushare 专业接口"),
                "state": state,
                "status_label": to_text(raw.get("status_label"), STATE_LABELS.get(state, "待验证")),
                "tone": tone_for_state(state),
                "cause_code": cause_code,
                "cause_label": GAP_CAUSE_LABELS.get(cause_code, "尚未检测"),
                "action_mode": _gap_action_mode(state),
                "why_not_found": _gap_reason_for_state(raw),
                "why_previous_full_not_enough": _why_previous_full_not_enough(raw),
                "diagnostic_answer": _diagnostic_answer_for_state(raw),
                "decision_guardrail": _gap_guardrail_for_state(raw),
                "safe_recovery_steps": _safe_recovery_steps(raw),
                "next_action": to_text(raw.get("next_action"), next_action),
                "manual_button_label": to_text(manual_action.get("button_label"), "手动检测"),
                "writes_packet": to_text(manual_action.get("writes_packet"), "command_center_facts_packet"),
                "toolbox_entry": to_text(manual_action.get("toolbox_entry"), "高级工具箱入口 / 数据源体检"),
                "refresh_policy": to_text(manual_action.get("refresh_policy"), "button_gated"),
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            }
        )
    summary = (
        f"可用 {_count_by_state(rows, AVAILABLE_STATES)}｜受限 {_count_by_state(rows, BLOCKED_STATES)}｜"
        f"手动 {_count_by_state(rows, MANUAL_STATES)}｜缓存/近期无数据 {_count_by_state(rows, STALE_STATES)}"
    )
    return {
        "title": "Tushare 专业接口为什么搜不到",
        "status": status,
        "tone": tone,
        "headline": headline,
        "summary": summary,
        "cause_summary": _cause_summary(items),
        "plain_answer": plain_answer,
        "explanation": "基础行情或 token 正常，不代表每个 A股专业接口都有权限、当日数据或当前标的覆盖。",
        "items": items[:6],
        "next_action": next_action,
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
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
    tushare_gap_explainer = build_tushare_gap_explainer({"items": items})
    return {
        "status": status,
        "tone": tone,
        "title": "A股数据能力矩阵",
        "summary": summary,
        "items": items,
        "tushare_gap_explainer": tushare_gap_explainer,
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
