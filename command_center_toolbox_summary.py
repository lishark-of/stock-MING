from __future__ import annotations

from collections.abc import Iterable
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


ADVANCED_TOOLBOX_ITEMS = [
    {
        "key": "today_pool",
        "label": "今日关注池",
        "purpose": "查看市场风格、投喂反馈和旧版投研驾驶舱。",
        "packet": "legacy_market_style_fact_packet / command_center_market_packet",
        "gate": "刷新市场风格数据按钮",
        "data_dependencies": [
            "Tushare daily / daily_basic",
            "本地市场风格缓存",
            "投喂/资讯缓存",
        ],
        "data_dependency_terms": ["daily", "daily_basic", "market_style", "market"],
        "common_missing_reasons": [
            "非交易日、数据尚未发布或本地缓存过期。",
            "Tushare token 可用不等于每个行情/基础接口都有当日数据。",
            "使用缓存时只能说明上次成功结果，不代表实时状态。",
        ],
        "safe_empty_state": "显示待刷新或缓存标记，不把缺口写成市场确认。",
        "migration_target": "市场风格 packet 回流到 Home Action Snapshot。",
    },
    {
        "key": "tianyan_risk",
        "label": "天眼风控",
        "purpose": "排查公告、减持、质押、解禁等硬风险线索。",
        "packet": "tianyan_risk_fact_packet / command_center_hard_risk_packet",
        "gate": "手动运行风险扫描按钮",
        "data_dependencies": [
            "Tushare anns_d",
            "forecast / stk_holdertrade / share_float",
            "pledge_stat / pledge_detail / stk_surv",
        ],
        "data_dependency_terms": [
            "anns_d",
            "forecast",
            "stk_holdertrade",
            "share_float",
            "pledge_stat",
            "pledge_detail",
            "stk_surv",
            "公告",
            "减持",
            "质押",
        ],
        "common_missing_reasons": [
            "公告或风险事件近期没有记录，不能等同于无风险。",
            "部分硬风险接口可能需要额外权限/积分。",
            "失败后本会话会跳过重复请求，避免旧页面卡住。",
        ],
        "safe_empty_state": "保留上次成功硬风险摘要；缺失项进入风险警报待验证。",
        "migration_target": "硬风险 packet 回流到今日总决策依据链。",
    },
    {
        "key": "discipline_lab",
        "label": "交易纪律实验室",
        "purpose": "查看纪律规则、回测缓存和策略边界。",
        "packet": "last_backtest_report / command_center_discipline_packet",
        "gate": "运行纪律校验 / 回测按钮",
        "data_dependencies": [
            "last_backtest_report",
            "本地回测缓存",
            "策略纪律规则缓存",
        ],
        "data_dependency_terms": ["last_backtest_report", "backtest", "discipline", "纪律", "回测"],
        "common_missing_reasons": [
            "回测结果未手动运行或缓存已过期。",
            "页面打开不会自动跑回测。",
            "没有回测缓存时只能显示待验证纪律状态。",
        ],
        "safe_empty_state": "显示待刷新纪律状态，不把缺少回测当成策略通过。",
        "migration_target": "纪律 packet 回流到策略执行实验室。",
    },
    {
        "key": "quant_projection",
        "label": "量化推演",
        "purpose": "运行旧版完整量化底座和 A股专业事实整理。",
        "packet": "legacy_quant_result / command_center_quant_packet",
        "gate": "生成量化推演按钮",
        "data_dependencies": [
            "Tushare daily / daily_basic / adj_factor",
            "yfinance technical fallback",
            "本地量化推演缓存",
        ],
        "data_dependency_terms": ["daily", "daily_basic", "adj_factor", "yfinance", "quant", "technical"],
        "common_missing_reasons": [
            "行情字段缺失、复权因子缺失或缓存日期不匹配。",
            "Tushare 与 yfinance 口径不同，不能混成同一条实时结论。",
            "完整底座需要按钮触发，不在首页自动运行。",
        ],
        "safe_empty_state": "显示路径推演待验证；趋势图用 fallback 并明确标注。",
        "migration_target": "量化 packet 回流到 5-10 日趋势推演。",
    },
    {
        "key": "margin_etf",
        "label": "融资 ETF",
        "purpose": "刷新 ETF 日线、融资配置和赛道候选。",
        "packet": "legacy_margin_etf_allocation_result / command_center_etf_packet",
        "gate": "刷新 ETF 配置按钮",
        "data_dependencies": [
            "Tushare fund_daily / fund_basic",
            "Tushare margin_detail",
            "本地 ETF universe / allocation cache",
        ],
        "data_dependency_terms": ["fund_daily", "fund_basic", "margin_detail", "etf", "fund", "融资融券"],
        "common_missing_reasons": [
            "ETF 日线、融资融券或基金基础接口可能权限不足。",
            "跨市场/QDII ETF 可能存在日期和汇率口径差异。",
            "缓存可展示上次计划，但不能说明今日可追。",
        ],
        "safe_empty_state": "显示现金缓冲和不追高提示；不自动放大融资比例。",
        "migration_target": "ETF packet 回流到 Home Action Snapshot 的 ETF/融资栏。",
    },
    {
        "key": "data_healthcheck",
        "label": "数据源体检",
        "purpose": "手动检查 Tushare / AkShare / yfinance / Supabase 数据能力。",
        "packet": "last_data_source_healthcheck / data_capability_console",
        "gate": "运行数据源体检按钮",
        "data_dependencies": [
            "Tushare capability packet",
            "AkShare manual refresh status",
            "yfinance / Supabase capability status",
        ],
        "data_dependency_terms": ["tushare", "akshare", "yfinance", "supabase", "capability"],
        "common_missing_reasons": [
            "token 配置成功不等于所有接口都有权限。",
            "AkShare/yfinance/Supabase 默认不在页面打开时自动 ping。",
            "本会话跳过表示此前已失败或受限，需要手动重新检测。",
        ],
        "safe_empty_state": "只读取本地检测 packet；没有检测结果时显示未检测。",
        "migration_target": "统一数据能力控制台回流到首页数据新鲜度。",
    },
    {
        "key": "next_ticket_radar",
        "label": "下一票雷达",
        "purpose": "运行候选池扫描和触发条件排查。",
        "packet": "radar_scan_results / command_center_radar_packet",
        "gate": "运行下一票雷达按钮",
        "data_dependencies": [
            "radar_scan_results",
            "Tushare moneyflow / top_list",
            "limit_list_d / limit_cpt_list",
        ],
        "data_dependency_terms": ["radar", "moneyflow", "top_list", "limit_list_d", "limit_cpt_list", "龙虎榜", "资金流", "涨跌停"],
        "common_missing_reasons": [
            "全市场扫描必须按钮触发，首页不会自动跑。",
            "龙虎榜、资金流、涨跌停接口可能无记录、权限不足或本会话跳过。",
            "候选池为空只能说明待验证，不代表没有机会。",
        ],
        "safe_empty_state": "显示暂无可执行候选；等待刷新而不是自动补扫。",
        "migration_target": "雷达 packet 回流到下一票 Top3。",
    },
    {
        "key": "cloud_brain",
        "label": "云端外脑",
        "purpose": "查看 Supabase 记忆和云端资料缓存。",
        "packet": "legacy_cloud_memories / Supabase capability",
        "gate": "手动读取云端外脑按钮",
        "data_dependencies": [
            "Supabase brain_memory",
            "Supabase market_news",
            "本地外脑缓存",
        ],
        "data_dependency_terms": ["supabase", "brain_memory", "market_news", "cloud"],
        "common_missing_reasons": [
            "Supabase 未配置或表权限不足时不会自动重试。",
            "云端资料是辅助记忆，不等同于已验证行情事实。",
            "DeepSeek 仍只在按钮触发时解释结构化结果。",
        ],
        "safe_empty_state": "显示本地缓存或未配置；不把云端缺失当成交易信号。",
        "migration_target": "外脑摘要回流到可选 DeepSeek 解释上下文。",
    },
]


def _filter_items(items: Iterable[dict[str, Any]], keys: Iterable[str] | None = None) -> list[dict]:
    allowed = {str(key) for key in keys or []}
    result = []
    for item in items:
        payload = dict(item)
        if allowed and payload.get("key") not in allowed and payload.get("label") not in allowed:
            continue
        payload["status"] = "高级工具"
        payload["trigger_policy"] = "button_gated"
        payload["deepseek_policy"] = "manual_only"
        payload["capability_summary"] = build_tool_capability_summary(payload)
        payload["capability_status"] = build_tool_data_capability_status(payload)
        result.append(payload)
    return result


def _string_list(value: Any, limit: int = 4) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Iterable):
        values = list(value)
    else:
        values = []
    result = []
    for item in values:
        text = str(item or "").strip()
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _lower_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_state(value: Any) -> str:
    text = _lower_text(value)
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
    if "无数据" in text or "近期无" in text or "暂无" in text:
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


def _capability_items(data_capability_packet: Any = None) -> list[dict]:
    packet = data_capability_packet if isinstance(data_capability_packet, dict) else {}
    rows = []
    for raw in packet.get("items") or []:
        if not isinstance(raw, dict):
            continue
        state = _normalize_state(raw.get("state") or raw.get("capability_state") or raw.get("status"))
        rows.append(
            {
                "key": str(raw.get("key") or raw.get("section") or raw.get("api") or raw.get("table") or "data_capability"),
                "label": str(raw.get("label") or raw.get("section") or raw.get("api") or raw.get("table") or "数据能力"),
                "provider": str(raw.get("provider") or raw.get("source") or packet.get("source") or "数据源"),
                "api": str(raw.get("api") or raw.get("table") or ""),
                "state": state,
                "status_label": str(raw.get("status") or raw.get("capability_label") or STATE_LABELS.get(state, "待验证")),
                "action_hint": str(raw.get("action_hint") or raw.get("error") or raw.get("reason") or ""),
                "latest_date": str(raw.get("latest_date") or raw.get("updated_at") or ""),
            }
        )
    return rows


def _dependency_terms(item: dict[str, Any]) -> list[str]:
    terms = _string_list(item.get("data_dependency_terms"), limit=16)
    if not terms:
        for dependency in _string_list(item.get("data_dependencies"), limit=8):
            for raw in dependency.replace("/", " ").replace(",", " ").replace("，", " ").split():
                text = raw.strip()
                if len(text) >= 3:
                    terms.append(text)
    result = []
    seen = set()
    for term in terms:
        text = _lower_text(term)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _matches_tool_dependency(item: dict[str, Any], capability: dict[str, Any]) -> bool:
    haystack = " ".join(
        _lower_text(capability.get(key))
        for key in ("key", "label", "provider", "api", "status_label", "action_hint")
    )
    return any(term in haystack for term in _dependency_terms(item))


def _status_from_matches(matches: list[dict]) -> tuple[str, str, str]:
    states = [match.get("state") for match in matches]
    if not matches:
        return "missing", "待检测", "missing"
    if "permission_denied" in states:
        return "blocked", "权限不足", "failed"
    if "disabled_this_session" in states:
        return "blocked", "本会话跳过", "failed"
    if any(state in {"not_configured", "network_failed", "failed"} for state in states):
        return "blocked", "调用失败/未配置", "failed"
    if any(state in MANUAL_STATES for state in states):
        return "manual", "需要手动刷新", "stale"
    if any(state in {"stale_cache", "fallback_used"} for state in states):
        return "stale", "使用缓存", "stale"
    if any(state in {"empty_recent", "unknown", "missing"} for state in states):
        return "pending", "待验证/近期无数据", "missing"
    if all(state in AVAILABLE_STATES for state in states):
        return "ready", "可用", "ready"
    return "partial", "部分可用", "stale"


def build_tool_data_capability_status(item: dict[str, Any], data_capability_packet: Any = None) -> dict:
    capabilities = _capability_items(data_capability_packet)
    matches = [capability for capability in capabilities if _matches_tool_dependency(item, capability)]
    status, status_label, tone = _status_from_matches(matches)
    available = [row for row in matches if row.get("state") in AVAILABLE_STATES]
    blocked = [row for row in matches if row.get("state") in BLOCKED_STATES]
    manual = [row for row in matches if row.get("state") in MANUAL_STATES]
    stale = [row for row in matches if row.get("state") in STALE_STATES]
    if not matches:
        summary = "尚未读取到匹配的数据能力检测结果；进入工具箱也不会自动请求外部接口。"
    else:
        summary = f"匹配 {len(matches)} 项｜可用 {len(available)}｜受限/失败 {len(blocked)}｜手动 {len(manual)}｜缓存/待验证 {len(stale)}"
    return {
        "key": str(item.get("key") or "advanced_tool"),
        "label": str(item.get("label") or "高级工具"),
        "status": status,
        "status_label": status_label,
        "tone": tone,
        "summary": summary,
        "matched_items": matches[:5],
        "available_count": len(available),
        "blocked_count": len(blocked),
        "manual_count": len(manual),
        "stale_count": len(stale),
        "next_action": str(item.get("gate") or "按钮手动触发"),
        "deepseek_called": False,
    }


def build_tool_capability_summary(item: dict[str, Any]) -> dict:
    dependencies = _string_list(item.get("data_dependencies"), limit=6)
    reasons = _string_list(item.get("common_missing_reasons"), limit=4)
    label = str(item.get("label") or "高级工具")
    return {
        "key": str(item.get("key") or label),
        "label": label,
        "depends_on": dependencies,
        "why_missing": reasons,
        "safe_empty_state": str(item.get("safe_empty_state") or "显示待验证，不自动触发重型请求。"),
        "migration_target": str(item.get("migration_target") or "逐步回流到综合推演中心 packet。"),
        "manual_gate": str(item.get("gate") or "按钮手动触发"),
        "deepseek_called": False,
    }


def build_legacy_tool_capability_map(
    keys: Iterable[str] | None = None,
    data_capability_packet: Any = None,
) -> list[dict]:
    return [
        {
            **item["capability_summary"],
            "capability_status": build_tool_data_capability_status(item, data_capability_packet),
        }
        for item in _filter_items(ADVANCED_TOOLBOX_ITEMS, keys=keys)
    ]


def build_advanced_toolbox_entry(
    keys: Iterable[str] | None = None,
    data_capability_packet: Any = None,
) -> dict:
    items = _filter_items(ADVANCED_TOOLBOX_ITEMS, keys=keys)
    for item in items:
        item["capability_status"] = build_tool_data_capability_status(item, data_capability_packet)
    return {
        "status": "ready",
        "title": "高级工具箱",
        "summary": "旧版工作台保留为排查和深度工具；综合推演中心仍是默认主入口。",
        "items": items,
        "capability_map": [
            {
                **item["capability_summary"],
                "capability_status": item["capability_status"],
            }
            for item in items
        ],
        "manual_note": "进入高级工具箱不会自动触发 DeepSeek、回测、全市场扫描或重型数据接口；具体模块仍由按钮手动触发。",
        "data_gap_note": "Tushare 拉满或 token 可用，只代表接入成功；单个接口仍可能因权限、交易日、标的覆盖、缓存过期或本会话跳过而没有结果。",
        "next_step": "旧版工具的结果会逐步写入统一 packet，再回到 Home Action Snapshot 和数据能力控制台。",
        "deepseek_called": False,
    }
