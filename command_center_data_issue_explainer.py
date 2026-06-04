from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from market_data_capability import (
    decision_impact_for_capability_state,
    meaning_for_capability_state,
    next_action_for_capability_state,
    normalize_capability_state_value,
    tone_for_capability_state,
)


MAX_ITEMS = 8
MAX_ACTIONS = 6

AVAILABLE_STATES = {"available", "ready", "ok", "success"}
RESTRICTED_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
PENDING_STATES = {"empty_recent", "stale_cache", "fallback_used", "requires_manual_refresh", "unknown", "missing"}

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


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = _to_text(value)
        if text:
            return text
    return default


def _dedupe(values: Any, limit: int = MAX_ACTIONS) -> list[str]:
    result = []
    seen = set()
    for value in _as_list(values):
        text = _to_text(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
        if len(result) >= limit:
            break
    return result


def normalize_data_issue_state(value: Any) -> str:
    return normalize_capability_state_value(value)


def _tone(state: str) -> str:
    return tone_for_capability_state(state)


def _meaning_for_state(state: str, provider: str, label: str) -> str:
    return meaning_for_capability_state(state, provider, label)


def _decision_impact_for_state(state: str, label: str) -> str:
    return decision_impact_for_capability_state(state, label)


def _next_action_for_state(state: str, label: str) -> str:
    return next_action_for_capability_state(state, label)


def explain_data_issue_item(raw: Any, provider_default: str = "数据源") -> dict:
    payload = _as_mapping(raw)
    label = _first_text(payload.get("label"), payload.get("section"), payload.get("api"), payload.get("table"), default="数据能力")
    provider = _first_text(payload.get("provider"), payload.get("source"), default=provider_default)
    state = normalize_data_issue_state(payload.get("state") or payload.get("capability_state") or payload.get("status"))
    api = _to_text(payload.get("api") or payload.get("table"))
    return {
        "key": _first_text(payload.get("key"), payload.get("section"), payload.get("api"), payload.get("table"), default="data_issue"),
        "label": label,
        "provider": provider,
        "api": api,
        "state": state,
        "status_label": _first_text(payload.get("status"), payload.get("capability_label"), default=STATE_LABELS.get(state, "待验证")),
        "tone": _tone(state),
        "latest_date": _first_text(payload.get("latest_date"), payload.get("updated_at")),
        "reason": _first_text(payload.get("error"), payload.get("reason"), payload.get("message"), payload.get("action_hint")),
        "meaning": _meaning_for_state(state, provider, label),
        "decision_impact": _decision_impact_for_state(state, label),
        "next_action": _first_text(payload.get("action_hint"), default=_next_action_for_state(state, label)),
    }


def _items_from_packet(packet: Any, provider_default: str = "数据源") -> list[dict]:
    payload = _as_mapping(packet)
    return [
        explain_data_issue_item(item, provider_default=provider_default or _to_text(payload.get("source"), "数据源"))
        for item in _as_list(payload.get("items"))
        if _as_mapping(item)
    ]


def _items_from_refresh_errors(refresh_summary: Any = None, errors: Any = None) -> list[dict]:
    rows = []
    refresh = _as_mapping(refresh_summary)
    for key in ("error_items", "errors"):
        raw = refresh.get(key) or []
        if isinstance(raw, (str, Mapping)):
            raw = [raw]
        rows.extend(_as_list(raw))
    raw_errors = errors
    if isinstance(raw_errors, (str, Mapping)):
        raw_errors = [raw_errors]
    rows.extend(_as_list(raw_errors))

    result = []
    for row in rows:
        payload = _as_mapping(row)
        if payload:
            label = _first_text(payload.get("module"), payload.get("label"), default="刷新错误")
            result.append(
                explain_data_issue_item(
                    {
                        "label": label,
                        "provider": _first_text(payload.get("provider"), payload.get("source"), default="刷新结果"),
                        "api": payload.get("api"),
                        "state": "failed",
                        "status": "失败",
                        "error": _first_text(payload.get("message"), payload.get("error"), payload.get("last_error")),
                        "updated_at": _first_text(payload.get("updated_at"), payload.get("finished_at")),
                    }
                )
            )
        else:
            text = _to_text(row)
            if text:
                result.append(
                    explain_data_issue_item(
                        {
                            "label": "刷新错误",
                            "provider": "刷新结果",
                            "state": "failed",
                            "status": "失败",
                            "error": text,
                        }
                    )
                )
    return result


def _merge_items(*groups: list[dict]) -> list[dict]:
    merged = []
    seen = set()
    for group in groups:
        for item in group:
            key = (item.get("provider"), item.get("key"), item.get("api"), item.get("label"), item.get("state"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= MAX_ITEMS:
                return merged
    return merged


def _headline(available: int, restricted: int, pending: int) -> str:
    if not any([available, restricted, pending]):
        return "尚未检测数据能力"
    if restricted:
        return "部分数据接口受限，不能把缺失写成利好"
    if pending:
        return "部分数据待验证或使用缓存"
    return "数据能力已读取，可继续核对日期和口径"


def _short_answer(items: list[dict]) -> str:
    if not items:
        return "还没有本地检测结果；页面打开不会自动 ping Tushare、AkShare、yfinance 或 Supabase。"
    states = {item["state"] for item in items}
    if "permission_denied" in states or "disabled_this_session" in states:
        return "Tushare 配置成功只代表 token 可用；单个接口仍可能需要额外权限/积分，失败后本会话会跳过重复请求以避免卡顿。"
    if "empty_recent" in states:
        return "接口可用也可能搜不到：近期无数据通常来自非交易日、尚未发布、标的未上榜或接口不覆盖。"
    if "stale_cache" in states or "fallback_used" in states:
        return "当前主要展示缓存或替代口径；它能防白屏，但不能当作实时已验证事实。"
    if "requires_manual_refresh" in states:
        return "这类数据必须按钮触发；页面打开不会自动请求重型接口。"
    return "当前数据能力有可用结果；执行前仍需核对日期、来源和适用市场。"


def _root_cause_items(items: list[dict]) -> list[dict]:
    states = {item["state"] for item in items}
    result = []
    if not items:
        return [
            {
                "key": "not_checked",
                "label": "尚未检测",
                "tone": "missing",
                "detail": "还没有本地数据能力检测结果；页面打开不会自动请求外部接口。",
                "next_action": "先点击对应刷新或检测按钮，再查看接口状态。",
            }
        ]
    if "permission_denied" in states:
        result.append(
            {
                "key": "endpoint_permission",
                "label": "接口权限/积分",
                "tone": "failed",
                "detail": "Tushare token 可用不等于每个专业接口都有权限；融资融券、筹码、涨跌停情绪等可能需要额外权限或积分。",
                "next_action": "检查具体接口权限，不要把权限不足写成行情不存在。",
            }
        )
    if "disabled_this_session" in states:
        result.append(
            {
                "key": "session_skip",
                "label": "本会话跳过",
                "tone": "failed",
                "detail": "某接口已经被判定受限或失败，本会话会跳过重复请求，避免页面反复卡顿。",
                "next_action": "确认权限恢复后，手动点击对应检测按钮重试。",
            }
        )
    if "empty_recent" in states:
        result.append(
            {
                "key": "empty_recent",
                "label": "近期无记录",
                "tone": "missing",
                "detail": "接口可用也可能搜不到：常见原因是非交易日、数据尚未发布、标的未上榜或该接口暂不覆盖。",
                "next_action": "核对交易日、发布时间和标的覆盖范围，不能把无记录写成利好。",
            }
        )
    if "stale_cache" in states or "fallback_used" in states:
        result.append(
            {
                "key": "cache_or_fallback",
                "label": "缓存/替代口径",
                "tone": "stale",
                "detail": "缓存能防白屏，但不是实时事实；替代口径也不能等同于原始接口数据。",
                "next_action": "执行前复核日期、来源和口径，必要时手动刷新。",
            }
        )
    if "requires_manual_refresh" in states:
        result.append(
            {
                "key": "manual_required",
                "label": "必须手动触发",
                "tone": "missing",
                "detail": "重型接口、批量扫描和外部刷新不会在页面打开时自动执行。",
                "next_action": "只在需要时点击对应按钮，并等待结果回流到综合中心。",
            }
        )
    if not result:
        result.append(
            {
                "key": "verify_scope",
                "label": "口径复核",
                "tone": "ready",
                "detail": "当前已有可用数据，但仍要确认日期、市场类型、标的范围和接口口径。",
                "next_action": "把可用接口当作辅助证据，不要单独作为交易动作依据。",
            }
        )
    return result[:MAX_ACTIONS]


def _tushare_provider_diagnostic_cards(items: list[dict]) -> list[dict]:
    tushare_items = [item for item in items if _to_text(item.get("provider")).lower() == "tushare"]
    if not tushare_items:
        return []
    states = {item["state"] for item in tushare_items}
    permission_items = [item for item in tushare_items if item["state"] == "permission_denied"]
    skipped_items = [item for item in tushare_items if item["state"] == "disabled_this_session"]
    empty_items = [item for item in tushare_items if item["state"] == "empty_recent"]
    cache_items = [item for item in tushare_items if item["state"] in {"stale_cache", "fallback_used"}]
    ready_items = [item for item in tushare_items if item["state"] in AVAILABLE_STATES]
    blocked_count = len(permission_items) + len(skipped_items)
    pending_count = len(empty_items) + len(cache_items)
    if blocked_count:
        tone = "failed"
        headline = "Tushare 已接入，但部分专业接口受权限/会话限制"
        answer = (
            "这不是“没拉满”或“没搜到行情”的同一类问题：token 可用只说明 Tushare 基础连接存在，"
            "龙虎榜、融资融券、涨跌停情绪、筹码等专业接口仍可能需要单独权限或积分；受限后本会话会跳过重复请求来防卡顿。"
        )
        next_action = "先看受限接口名称，再按数据恢复中心手动检测；不要把权限缺口写成利好、无风险或可加仓依据。"
    elif pending_count:
        tone = "stale"
        headline = "Tushare 可读，但当前结果以无记录/缓存/替代口径为主"
        answer = (
            "接口可用也可能暂时没有记录：常见原因是非交易日、数据尚未发布、标的未上榜、窗口期太短，"
            "或当前只保留上次成功缓存。"
        )
        next_action = "核对交易日、发布时间、标的覆盖范围和缓存时间；需要实时证据时再手动刷新。"
    elif ready_items:
        tone = "ready"
        headline = "Tushare 当前有可用证据"
        answer = "已有 Tushare 数据可进入证据链，但仍要核对交易日、来源、市场类型和是否匹配当前标的。"
        next_action = "把可用接口作为辅助证据，和价格、纪律、仓位一起确认。"
    else:
        tone = "missing"
        headline = "Tushare 状态待检测"
        answer = "当前没有足够的 Tushare 本地检测结果；页面打开不会自动 ping 专业接口。"
        next_action = "需要时点击对应检测或刷新按钮，再查看数据恢复中心。"
    evidence = []
    for label, rows in (
        ("可用", ready_items),
        ("权限不足", permission_items),
        ("本会话跳过", skipped_items),
        ("近期无数据", empty_items),
        ("缓存/替代", cache_items),
    ):
        if not rows:
            continue
        evidence.append(
            {
                "label": label,
                "count": len(rows),
                "apis": [_first_text(item.get("api"), item.get("label"), default="Tushare 接口") for item in rows[:4]],
            }
        )
    return [
        {
            "provider": "Tushare",
            "tone": tone,
            "headline": headline,
            "answer": answer,
            "full_refresh_answer": _tushare_full_refresh_answer(
                permission_items=permission_items,
                skipped_items=skipped_items,
                empty_items=empty_items,
                cache_items=cache_items,
                ready_items=ready_items,
            ),
            "scope_checks": _tushare_scope_checks(
                permission_items=permission_items,
                skipped_items=skipped_items,
                empty_items=empty_items,
                cache_items=cache_items,
                ready_items=ready_items,
            ),
            "next_action": next_action,
            "states": sorted(states),
            "available_count": len(ready_items),
            "blocked_count": blocked_count,
            "pending_count": pending_count,
            "evidence_items": evidence[:MAX_ACTIONS],
            "deepseek_called": False,
        }
    ]


CORE_NON_TUSHARE_PROVIDERS = ("AkShare", "yfinance", "Supabase")


def _provider_group(items: list[dict], provider_name: str) -> list[dict]:
    provider_key = provider_name.lower()
    return [item for item in items if _to_text(item.get("provider")).lower() == provider_key]


def _generic_provider_text(provider: str, states: set[str]) -> tuple[str, str, str]:
    if provider == "AkShare":
        if "requires_manual_refresh" in states:
            return (
                "AkShare 被标记为手动刷新型补充源",
                "AkShare 适合补充资金穿透、情绪或部分行情，但重型刷新必须按钮触发；不可用不代表 Tushare 主证据链失效。",
                "只在确实需要补充视角时进入对应模块手动刷新，结果回流后再复核。",
            )
        return (
            "AkShare 补充源状态待复核",
            "AkShare 远端接口和页面结构可能变化；它只能作为补充证据，不能替代 Tushare A股专业事实。",
            "需要时手动刷新，并确认日期、来源和是否覆盖当前标的。",
        )
    if provider == "yfinance":
        return (
            "yfinance 全球行情能力待复核" if states - AVAILABLE_STATES else "yfinance 当前有可用结果",
            "yfinance 主要服务美股/全球行情、财报和新闻线索；不能用来替代 A股 Tushare 资金流、龙虎榜、融资融券或涨跌停口径。",
            "美股/全球标的需要手动复核行情、财报、RS、行业和宏观口径。",
        )
    if provider == "Supabase":
        return (
            "Supabase 云端外脑配置待复核" if states - AVAILABLE_STATES else "Supabase 云端记忆可读取",
            "Supabase 是云端记忆/资料库，不是实时行情源；未配置或连接失败不应被解释成行情不存在。",
            "先检查本地配置和表连接，再决定是否手动读取云端记忆档案。",
        )
    return (
        f"{provider} 数据能力待复核",
        f"{provider} 需要按接口、日期和覆盖范围单独诊断。",
        "按数据恢复中心手动处理。",
    )


def _generic_provider_scope_checks(provider: str, items: list[dict]) -> list[dict]:
    states = {item["state"] for item in items}
    blocked_items = [item for item in items if item["state"] in RESTRICTED_STATES]
    manual_items = [item for item in items if item["state"] == "requires_manual_refresh"]
    cache_items = [item for item in items if item["state"] in {"stale_cache", "fallback_used"}]
    ready_items = [item for item in items if item["state"] in AVAILABLE_STATES]
    blocked_label = _labels_for_items(blocked_items)
    manual_label = _labels_for_items(manual_items)
    cache_label = _labels_for_items(cache_items)
    ready_label = _labels_for_items(ready_items)
    if provider == "AkShare":
        scope_label = "补充源/重型刷新边界"
        scope_message = "AkShare 只作为补充证据；资金穿透、重型刷新或批量刷新必须按钮触发。"
    elif provider == "yfinance":
        scope_label = "市场口径/美股全球边界"
        scope_message = "yfinance 用于美股/全球行情，不替代 A股 Tushare 专业接口。"
    elif provider == "Supabase":
        scope_label = "云端记忆/资料边界"
        scope_message = "Supabase 存储资料和记忆，不是实时行情源，也不会自动决定仓位。"
    else:
        scope_label = "接口口径"
        scope_message = f"{provider} 仍需按接口和市场范围复核。"
    return [
        {
            "key": "provider_config",
            "label": "配置/连接",
            "status": "blocked" if blocked_items else ("ready" if ready_items or manual_items or cache_items else "missing"),
            "tone": "failed" if blocked_items else ("ready" if ready_items else "missing"),
            "status_label": "有阻断" if blocked_items else ("已检测" if ready_items or manual_items or cache_items else "待检测"),
            "message": (
                f"阻断：{blocked_label}；先检查配置、网络、权限或本地连接。"
                if blocked_items
                else "未见配置/连接阻断；仍需按接口复核。"
            ),
        },
        {
            "key": "manual_gate",
            "label": "手动触发边界",
            "status": "partial" if manual_items else "ready",
            "tone": "stale" if manual_items else "ready",
            "status_label": "需要手动" if manual_items else "未触发",
            "message": (
                f"需手动：{manual_label}；页面打开不会自动运行该 provider 的重型刷新。"
                if manual_items
                else "当前没有被标记为自动刷新；仍保持按钮触发。"
            ),
        },
        {
            "key": "provider_scope",
            "label": scope_label,
            "status": "ready" if ready_items else ("partial" if manual_items or cache_items else "missing"),
            "tone": "ready" if ready_items else ("stale" if manual_items or cache_items else "missing"),
            "status_label": "可参考" if ready_items else "待验证",
            "message": scope_message,
        },
        {
            "key": "cache_result_guard",
            "label": "缓存/结果保护",
            "status": "partial" if cache_items else ("ready" if ready_items else "missing"),
            "tone": "stale" if cache_items else ("ready" if ready_items else "missing"),
            "status_label": "使用缓存" if cache_items else ("已返回" if ready_items else "待检测"),
            "message": (
                f"缓存/替代：{cache_label}；只能防白屏，不能当作实时已验证事实。"
                if cache_items
                else f"可用结果：{ready_label}；执行前仍需核对日期和口径。"
            ),
        },
    ]


def _generic_provider_diagnostic_cards(items: list[dict]) -> list[dict]:
    cards = []
    for provider in CORE_NON_TUSHARE_PROVIDERS:
        provider_items = _provider_group(items, provider)
        if not provider_items:
            continue
        states = {item["state"] for item in provider_items}
        ready_items = [item for item in provider_items if item["state"] in AVAILABLE_STATES]
        blocked_items = [item for item in provider_items if item["state"] in RESTRICTED_STATES]
        manual_items = [item for item in provider_items if item["state"] == "requires_manual_refresh"]
        pending_items = [
            item
            for item in provider_items
            if item["state"] in PENDING_STATES and item["state"] != "requires_manual_refresh"
        ]
        if blocked_items:
            tone = "failed"
        elif manual_items or pending_items:
            tone = "stale"
        elif ready_items:
            tone = "ready"
        else:
            tone = "missing"
        headline, answer, next_action = _generic_provider_text(provider, states)
        evidence = []
        for label, rows in (
            ("可用", ready_items),
            ("阻断", blocked_items),
            ("手动刷新", manual_items),
            ("缓存/待验证", pending_items),
        ):
            if not rows:
                continue
            evidence.append(
                {
                    "label": label,
                    "count": len(rows),
                    "apis": [_first_text(item.get("api"), item.get("label"), default=f"{provider} 接口") for item in rows[:4]],
                }
            )
        cards.append(
            {
                "provider": provider,
                "tone": tone,
                "headline": headline,
                "answer": answer,
                "full_refresh_answer": answer,
                "scope_checks": _generic_provider_scope_checks(provider, provider_items),
                "next_action": next_action,
                "states": sorted(states),
                "available_count": len(ready_items),
                "blocked_count": len(blocked_items),
                "pending_count": len(manual_items) + len(pending_items),
                "evidence_items": evidence[:MAX_ACTIONS],
                "deepseek_called": False,
            }
        )
    return cards


def _provider_diagnostic_cards(items: list[dict]) -> list[dict]:
    return [
        *_tushare_provider_diagnostic_cards(items),
        *_generic_provider_diagnostic_cards(items),
    ][:MAX_ACTIONS]


def _labels_for_items(items: list[dict], default: str = "暂无") -> str:
    labels = []
    for item in items:
        label = _first_text(item.get("label"), item.get("api"), default="")
        api = _to_text(item.get("api"))
        if label and api and api not in label:
            label = f"{label}({api})"
        if label:
            labels.append(label)
    labels = [label for label in labels if label]
    return "、".join(labels[:4]) if labels else default


def _tushare_full_refresh_answer(
    permission_items: list[dict],
    skipped_items: list[dict],
    empty_items: list[dict],
    cache_items: list[dict],
    ready_items: list[dict],
) -> str:
    if permission_items or skipped_items:
        blocked_labels = _labels_for_items([*permission_items, *skipped_items], "受限接口")
        return (
            f"“拉满 Tushare”只说明已经尝试连接和读取；{blocked_labels} 仍卡在专业接口权限、积分或本会话跳过，"
            "所以不能把缺失结果理解成行情不存在。"
        )
    if empty_items:
        empty_labels = _labels_for_items(empty_items, "近期无记录接口")
        return (
            f"Tushare 可读不等于每个接口当日都有记录；{empty_labels} 可能受交易日、发布时间、上榜条件或标的覆盖影响。"
        )
    if cache_items:
        cache_labels = _labels_for_items(cache_items, "缓存/替代接口")
        return f"{cache_labels} 当前依赖缓存或替代口径，能防白屏，但还不是当日实时验证。"
    if ready_items:
        return "Tushare 已有可用接口结果；仍要逐项核对接口口径、交易日、标的覆盖和是否能写入对应 packet。"
    return "尚未形成 Tushare 接口级诊断；页面打开不会自动 ping 专业接口。"


def _tushare_scope_checks(
    permission_items: list[dict],
    skipped_items: list[dict],
    empty_items: list[dict],
    cache_items: list[dict],
    ready_items: list[dict],
) -> list[dict]:
    blocked_items = [*permission_items, *skipped_items]
    checks = [
        {
            "key": "base_connection",
            "label": "基础连接/token",
            "status": "ready" if ready_items or blocked_items or empty_items or cache_items else "missing",
            "tone": "ready" if ready_items or blocked_items or empty_items or cache_items else "missing",
            "status_label": "已检测" if ready_items or blocked_items or empty_items or cache_items else "待检测",
            "message": "已有本地 Tushare 能力结果；这只证明连接链路被检测过，不等于所有专业接口可用。",
        },
        {
            "key": "interface_permission",
            "label": "专业接口权限/积分",
            "status": "blocked" if blocked_items else ("ready" if ready_items else "missing"),
            "tone": "failed" if blocked_items else ("ready" if ready_items else "missing"),
            "status_label": "受限" if blocked_items else ("未见受限" if ready_items else "待检测"),
            "message": (
                f"受限：{_labels_for_items(blocked_items)}；需要单独核对接口权限、积分或本会话跳过。"
                if blocked_items
                else "当前未见权限阻断项；仍需按接口核对。"
            ),
        },
        {
            "key": "publish_window",
            "label": "交易日/发布窗口",
            "status": "partial" if empty_items else ("ready" if ready_items else "missing"),
            "tone": "stale" if empty_items else ("ready" if ready_items else "missing"),
            "status_label": "待核对" if empty_items else ("可参考" if ready_items else "待检测"),
            "message": (
                f"近期无记录：{_labels_for_items(empty_items)}；可能不是接口坏，而是交易日、发布时间或上榜窗口问题。"
                if empty_items
                else "未见近期无记录项；执行前仍需核对日期。"
            ),
        },
        {
            "key": "symbol_coverage",
            "label": "标的/接口覆盖",
            "status": "partial" if empty_items or cache_items else ("ready" if ready_items else "missing"),
            "tone": "stale" if empty_items or cache_items else ("ready" if ready_items else "missing"),
            "status_label": "待验证" if empty_items or cache_items else ("可参考" if ready_items else "待检测"),
            "message": "部分接口可能只覆盖上榜、特定市场或特定数据窗口；不能用一个接口缺失推导标的无风险。",
        },
        {
            "key": "cache_session_guard",
            "label": "缓存/会话保护",
            "status": "blocked" if skipped_items else ("partial" if cache_items else "ready"),
            "tone": "failed" if skipped_items else ("stale" if cache_items else "ready"),
            "status_label": "本会话跳过" if skipped_items else ("使用缓存" if cache_items else "未触发"),
            "message": (
                "受限或失败后本会话会跳过重复请求，避免旧工作台反复卡顿；确认恢复后再手动检测。"
                if skipped_items
                else "缓存/替代口径只用于防白屏，不能当作实时事实。"
            ),
        },
    ]
    return checks


def _interface_diagnostic_key(state: str) -> str:
    if state == "permission_denied":
        return "permission_or_points"
    if state == "disabled_this_session":
        return "session_skip"
    if state == "empty_recent":
        return "no_recent_record"
    if state in {"stale_cache", "fallback_used"}:
        return "cache_or_fallback"
    if state == "requires_manual_refresh":
        return "manual_gate"
    if state in AVAILABLE_STATES:
        return "available"
    if state == "not_configured":
        return "not_configured"
    if state == "network_failed":
        return "network_failed"
    return "unverified"


def _interface_diagnostic_label(state: str) -> str:
    return {
        "permission_denied": "权限/积分不足",
        "disabled_this_session": "本会话已跳过",
        "empty_recent": "近期无记录",
        "stale_cache": "正在使用缓存",
        "fallback_used": "替代口径",
        "requires_manual_refresh": "需要手动触发",
        "available": "接口可用",
        "not_configured": "本地未配置",
        "network_failed": "网络失败",
        "failed": "调用失败",
    }.get(state, "状态待验证")


def _interface_diagnostic_answer(item: Mapping[str, Any]) -> str:
    provider = _to_text(item.get("provider"), "数据源")
    label = _to_text(item.get("label"), "数据能力")
    api = _to_text(item.get("api"))
    state = _to_text(item.get("state"))
    api_text = f" {api}" if api else ""
    if provider.lower() == "tushare" and state == "permission_denied":
        return (
            f"{label}不是“没搜到”，而是 Tushare{api_text} 返回权限/积分不足；"
            "token 可用、积分较高或其他接口正常，都不等于这个专业接口已开通。"
        )
    if provider.lower() == "tushare" and state == "disabled_this_session":
        return (
            f"{label}此前已被判定受限或失败，本会话跳过重复请求来防卡顿；"
            "确认权限或接口恢复后，再手动检测。"
        )
    if provider.lower() == "tushare" and state == "empty_recent":
        return (
            f"{label}接口可读但近窗口无记录；常见原因是非交易日、数据尚未发布、"
            "标的未上榜、窗口期过短或接口暂不覆盖。"
        )
    if state == "stale_cache":
        return f"{label}正在使用上次成功缓存，能防白屏，但不是实时已验证事实。"
    if state == "fallback_used":
        return f"{label}使用替代口径，只能辅助观察，不能等同于原始接口事实。"
    if state == "requires_manual_refresh":
        return f"{label}属于按钮触发型能力；页面打开不会自动请求 {provider} 重型接口。"
    if state in AVAILABLE_STATES:
        return f"{label}已有可用返回，可进入证据链；执行前仍需核对日期、来源和当前标的。"
    if state == "not_configured":
        return f"{label}本地配置缺失；需要先检查 token、secrets 或连接设置。"
    if state == "network_failed":
        return f"{label}网络请求失败；保留缓存或安全空态，网络恢复后再手动重试。"
    return _to_text(item.get("meaning") or item.get("decision_impact"), f"{label}仍待验证。")


def _interface_sort_key(item: Mapping[str, Any]) -> tuple[int, str, str]:
    state = _to_text(item.get("state"))
    if state in RESTRICTED_STATES:
        priority = 0
    elif state in PENDING_STATES:
        priority = 1
    elif state in AVAILABLE_STATES:
        priority = 2
    else:
        priority = 3
    return (priority, _to_text(item.get("provider")), _to_text(item.get("label")))


def _interface_diagnostic_items(items: list[dict]) -> list[dict]:
    rows = []
    for item in sorted(items, key=_interface_sort_key):
        state = _to_text(item.get("state"), "unknown")
        rows.append(
            {
                "key": item.get("key") or "data_issue",
                "provider": item.get("provider") or "数据源",
                "label": item.get("label") or "数据能力",
                "api": item.get("api") or "",
                "state": state,
                "status_label": item.get("status_label") or STATE_LABELS.get(state, "待验证"),
                "tone": item.get("tone") or _tone(state),
                "cause_key": _interface_diagnostic_key(state),
                "cause_label": _interface_diagnostic_label(state),
                "diagnostic_answer": _interface_diagnostic_answer(item),
                "decision_impact": item.get("decision_impact") or _decision_impact_for_state(state, item.get("label")),
                "next_action": item.get("next_action") or _next_action_for_state(state, item.get("label")),
                "latest_date": item.get("latest_date") or "",
                "deepseek_called": False,
            }
        )
        if len(rows) >= MAX_ITEMS:
            break
    return rows


def build_data_issue_explainer_packet(
    data_capability_packet: Any = None,
    data_gap_report: Any = None,
    refresh_summary: Any = None,
    errors: Any = None,
) -> dict:
    capability = _as_mapping(data_capability_packet)
    gap_report = _as_mapping(data_gap_report)
    items = _merge_items(
        _items_from_packet(capability, provider_default=_to_text(capability.get("source"), "数据能力")),
        _items_from_packet(gap_report, provider_default=_to_text(gap_report.get("source"), "数据缺口")),
        _items_from_refresh_errors(refresh_summary=refresh_summary, errors=errors),
    )
    available = [item for item in items if item["state"] in AVAILABLE_STATES]
    restricted = [item for item in items if item["state"] in RESTRICTED_STATES]
    pending = [item for item in items if item["state"] in PENDING_STATES]
    actions = _dedupe([item["next_action"] for item in restricted + pending], limit=MAX_ACTIONS)
    return {
        "status": "ready" if items else "missing",
        "headline": _headline(len(available), len(restricted), len(pending)),
        "short_answer": _short_answer(items),
        "available_count": len(available),
        "restricted_count": len(restricted),
        "pending_count": len(pending),
        "items": items,
        "root_cause_items": _root_cause_items(items),
        "provider_diagnostic_cards": _provider_diagnostic_cards(items),
        "interface_diagnostic_items": _interface_diagnostic_items(items),
        "next_actions": actions,
        "source": "local data capability packet / gap report",
        "deepseek_called": False,
    }
