from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from numbers import Number
from typing import Any

from market_analysis_profile import (
    MARKET_A_SHARE,
    MARKET_ETF,
    MARKET_US_STOCK,
    get_market_analysis_profile,
    identify_market_type,
)


SOURCE = "rule-based market profile"
READY_STATUSES = {"ok", "ready", "completed", "complete", "success", "succeeded", "已刷新"}


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _now_iso(now: Any = None) -> str:
    if isinstance(now, _dt.datetime):
        return now.isoformat(timespec="seconds")
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min).isoformat(timespec="seconds")
    if isinstance(now, str) and now.strip():
        return now.strip()
    return _dt.datetime.now().isoformat(timespec="seconds")


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


def _coverage(live_packet: Any, strategy_packet: Any, decision_packet: Any) -> dict:
    live = _as_mapping(live_packet)
    return {
        "market": _packet_state(live.get("market")),
        "quant": _packet_state(live.get("quant")),
        "discipline": _packet_state(live.get("discipline")),
        "margin_etf": _packet_state(live.get("margin_etf")),
        "next_ticket": _packet_state(live.get("next_ticket")),
        "strategy_execution": _packet_state(strategy_packet),
        "decision": _packet_state(decision_packet),
    }


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _method_status(name: str, profile: Mapping[str, Any], coverage: Mapping[str, str], context_text: str) -> str:
    market = _to_text(profile.get("market"))
    method_names = {item.get("name"): item for item in _as_list(profile.get("methods")) if isinstance(item, Mapping)}
    fit = _to_text(_as_mapping(method_names.get(name)).get("fit"))
    if fit == "不适用":
        return "不适用"

    has_any_data = any(state in {"ready", "cached"} for state in coverage.values())
    if not has_any_data:
        return "待验证"

    if _contains_any(context_text, ["降风险", "禁止", "卖出", "减仓", "回撤过高", "风险高"]):
        if name in {"风险预算 / 仓位管理", "资金流 / 机构行为", "事件驱动 / 财报 / 公告"}:
            return "失败"
        return "待验证"

    if name in {"趋势跟踪", "Stage Analysis", "量价结构"}:
        return "通过" if coverage.get("quant") == "ready" or coverage.get("market") == "ready" else "待验证"
    if name == "风险预算 / 仓位管理":
        return "通过" if coverage.get("strategy_execution") in {"ready", "cached"} or coverage.get("decision") in {"ready", "cached"} else "待验证"
    if name == "ETF 赛道配置":
        return "通过" if market == MARKET_ETF and coverage.get("margin_etf") in {"ready", "cached"} else ("不适用" if market != MARKET_ETF else "待验证")
    if market == MARKET_A_SHARE and name == "资金流 / 机构行为":
        return "通过" if coverage.get("market") == "ready" else "待验证"
    if market == MARKET_US_STOCK and name in {"CAN SLIM / 机构成长股", "事件驱动 / 财报 / 公告", "宏观流动性 / 利率 / 汇率"}:
        return "待验证"
    return "待验证"


def _method_by_name(profile: Mapping[str, Any], name: str) -> dict:
    for item in _as_list(profile.get("methods")):
        payload = _as_mapping(item)
        if payload.get("name") == name:
            return payload
    return {"name": name, "fit": "待适配", "evidence_focus": [], "risk_focus": [], "action_hint": "等待市场画像补齐。"}


def _method_evidence(method: Mapping[str, Any], coverage: Mapping[str, str]) -> str:
    focus = "、".join(_as_list(method.get("evidence_focus"))[:4]) or "暂无证据项"
    ready = [key for key, state in coverage.items() if state == "ready"]
    cached = [key for key, state in coverage.items() if state == "cached"]
    if ready:
        return f"关注 {focus}；已刷新模块：{', '.join(ready)}。"
    if cached:
        return f"关注 {focus}；当前主要使用缓存：{', '.join(cached)}。"
    return f"关注 {focus}；数据不足，待刷新验证。"


def _summary_text(market: str, coverage: Mapping[str, str], methods: list[dict]) -> str:
    passed = [item["name"] for item in methods if item["status"] == "通过"]
    failed = [item["name"] for item in methods if item["status"] == "失败"]
    if failed:
        return f"{market} 分析框架提示风险项：{'、'.join(failed[:3])}。先降风险或等待验证。"
    if passed:
        return f"{market} 分析框架已有可用证据：{'、'.join(passed[:3])}；其余方法继续待验证。"
    if any(state in {"ready", "cached"} for state in coverage.values()):
        return f"{market} 分析框架已读取缓存/刷新结果，但多数方法仍需验证。"
    return f"{market} 分析框架等待数据刷新，不假装生成完整结论。"


def build_analysis_method_packet(
    market_type: Any = None,
    live_packet: Any = None,
    strategy_packet: Any = None,
    decision_packet: Any = None,
    ticker: Any = "",
    name: Any = "",
    profile: Any = None,
    now: Any = None,
) -> dict:
    resolved_market = _to_text(market_type)
    if not resolved_market:
        resolved_market = identify_market_type(ticker=ticker, name=name)
    market_profile = _as_mapping(profile) or get_market_analysis_profile(resolved_market, ticker=ticker, name=name)
    market = _to_text(market_profile.get("market"), resolved_market or "未知")
    coverage = _coverage(live_packet, strategy_packet, decision_packet)
    context_text = " ".join(
        [
            _to_text(_as_mapping(decision_packet).get("overall_action")),
            _to_text(_as_mapping(decision_packet).get("risk_level")),
            _to_text(_as_mapping(strategy_packet).get("action")),
            _to_text(_as_mapping(strategy_packet).get("summary")),
        ]
    )

    method_names = [
        "趋势跟踪",
        "Stage Analysis",
        "CAN SLIM / 机构成长股",
        "VCP / 波动收敛突破",
        "相对强弱 RS / 行业轮动",
        "量价结构",
        "资金流 / 机构行为",
        "风险预算 / 仓位管理",
        "事件驱动 / 财报 / 公告",
        "宏观流动性 / 利率 / 汇率",
        "ETF 赛道配置",
    ]
    methods = []
    for method_name in method_names:
        method = _method_by_name(market_profile, method_name)
        status = _method_status(method_name, market_profile, coverage, context_text)
        methods.append(
            {
                "name": method_name,
                "status": status,
                "evidence": _method_evidence(method, coverage),
                "risk": "、".join(_as_list(method.get("risk_focus"))[:4]) or "数据缺口",
                "action_hint": _to_text(method.get("action_hint"), "待验证后再行动。"),
                "fit": _to_text(method.get("fit"), "待适配"),
            }
        )

    return {
        "market": market,
        "profile": market_profile,
        "methods": methods,
        "summary": _summary_text(market, coverage, methods),
        "data_coverage": dict(coverage),
        "updated_at": _now_iso(now),
        "source": SOURCE,
        "deepseek_called": False,
        "last_error": None,
    }


def _home_method_tone(status: str) -> str:
    if status == "通过":
        return "success"
    if status == "失败":
        return "danger"
    if status == "不适用":
        return "muted"
    return "warning"


def _home_method_rank(item: Mapping[str, Any]) -> tuple[int, int]:
    status = _to_text(item.get("status"))
    fit = _to_text(item.get("fit"))
    status_rank = {"失败": 0, "通过": 1, "待验证": 2, "不适用": 9}.get(status, 3)
    fit_rank = {"核心": 0, "辅助": 1, "待适配": 2, "不适用": 9}.get(fit, 3)
    return status_rank, fit_rank


def build_home_analysis_method_summary(packet: Any = None) -> dict:
    payload = _as_mapping(packet)
    profile = _as_mapping(payload.get("profile"))
    market = _to_text(payload.get("market")) or _to_text(profile.get("market")) or "未知"
    label = _to_text(profile.get("label")) or ("市场类型待确认" if market in {"", "未知"} else market)
    methods = [_as_mapping(item) for item in _as_list(payload.get("methods")) if _as_mapping(item)]
    applicable = [item for item in methods if _to_text(item.get("status")) != "不适用"]
    ranked = sorted(applicable, key=_home_method_rank)
    visible_methods = []
    for item in ranked[:4]:
        visible_methods.append(
            {
                "name": _to_text(item.get("name"), "分析方法"),
                "status": _to_text(item.get("status"), "待验证"),
                "tone": _home_method_tone(_to_text(item.get("status"))),
                "fit": _to_text(item.get("fit"), "待适配"),
                "action_hint": _to_text(item.get("action_hint"), "待验证后再行动。"),
            }
        )
    if not visible_methods:
        visible_methods = [
            {
                "name": "市场画像",
                "status": "待验证",
                "tone": "warning",
                "fit": "待适配",
                "action_hint": "先确认标的和市场类型。",
            }
        ]

    coverage = _as_mapping(payload.get("data_coverage"))
    ready_count = len([state for state in coverage.values() if state == "ready"])
    cached_count = len([state for state in coverage.values() if state == "cached"])
    pending_count = len([item for item in visible_methods if item.get("status") == "待验证"])
    failed_count = len([item for item in visible_methods if item.get("status") == "失败"])
    if failed_count:
        headline = f"{label}：先处理风险方法"
        next_action = "风险方法未解除前，主路径只观察或降风险。"
        tone = "danger"
    elif ready_count:
        headline = f"{label}：已有可用分析口径"
        next_action = "按已通过方法验证趋势、仓位和失效条件。"
        tone = "success"
    elif cached_count:
        headline = f"{label}：读取缓存口径"
        next_action = "缓存只辅助判断，执行前等待价格和纪律确认。"
        tone = "warning"
    else:
        headline = f"{label}：等待数据验证"
        next_action = "先刷新基础数据，不把通用框架当成结论。"
        tone = "warning"

    focus_items = _as_list(profile.get("indicator_focus"))[:5]
    risk_items = _as_list(profile.get("risk_focus"))[:4]
    return {
        "market": market or "未知",
        "label": label,
        "headline": headline,
        "summary": _to_text(payload.get("summary"), f"{label} 分析框架等待数据验证。"),
        "tone": tone,
        "method_items": visible_methods,
        "focus_items": focus_items or ["趋势", "量价", "风险预算"],
        "risk_items": risk_items or ["数据缺口", "流动性"],
        "status_counts": {
            "ready_modules": ready_count,
            "cached_modules": cached_count,
            "pending_methods": pending_count,
            "failed_methods": failed_count,
        },
        "next_action": next_action,
        "updated_at": _to_text(payload.get("updated_at"), "暂无"),
        "deepseek_called": False,
        "deepseek_text": "DeepSeek：未调用",
    }
