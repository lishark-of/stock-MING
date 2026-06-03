from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_analysis_methods import build_analysis_method_packet
from market_analysis_profile import (
    MARKET_A_SHARE,
    MARKET_ETF,
    MARKET_US_STOCK,
    MARKET_UNKNOWN,
    get_market_analysis_profile,
    identify_market_type,
)


KNOWN_MARKETS = {MARKET_A_SHARE, MARKET_US_STOCK, MARKET_ETF}
MAX_METHOD_ITEMS = 5
MAX_FOCUS_ITEMS = 10
MAX_RISK_NOTES = 5
MAX_DATA_SOURCES = 4


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


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


def _unique_text(items: Any, limit: int) -> list[str]:
    result = []
    seen = set()
    for item in _as_list(items):
        text = _to_text(item)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
        if len(result) >= limit:
            break
    return result


def _get_nested(mapping: Any, *path: str) -> Any:
    current = _as_mapping(mapping)
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _resolve_ticker_and_name(
    ticker: Any = "",
    name: Any = "",
    live_packet: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    home_snapshot: Any = None,
) -> tuple[str, str]:
    snapshot = _as_mapping(home_snapshot)
    holding = _as_mapping(snapshot.get("holding_action"))
    candidates = _as_list(snapshot.get("next_ticket_candidates"))
    first_candidate = _as_mapping(candidates[0]) if candidates else {}
    live = _as_mapping(live_packet)
    decision = _as_mapping(decision_packet)
    strategy = _as_mapping(strategy_packet)
    resolved_ticker = (
        _to_text(ticker)
        or _to_text(holding.get("ticker"))
        or _to_text(decision.get("ticker") or decision.get("target") or decision.get("symbol"))
        or _to_text(strategy.get("ticker") or strategy.get("target") or strategy.get("symbol"))
        or _to_text(live.get("ticker") or live.get("target") or live.get("symbol"))
        or _to_text(first_candidate.get("ticker") or first_candidate.get("code"))
    )
    resolved_name = (
        _to_text(name)
        or _to_text(holding.get("name"))
        or _to_text(decision.get("name") or decision.get("security_name"))
        or _to_text(strategy.get("name") or strategy.get("security_name"))
        or _to_text(live.get("name") or live.get("security_name"))
        or _to_text(first_candidate.get("name"))
    )
    return resolved_ticker, resolved_name


def _resolve_market(
    market_type: Any = "",
    ticker: Any = "",
    name: Any = "",
    analysis_method_packet: Any = None,
    live_packet: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    home_snapshot: Any = None,
) -> str:
    analysis = _as_mapping(analysis_method_packet)
    explicit = _to_text(market_type) or _to_text(analysis.get("market"))
    if explicit and explicit not in {MARKET_UNKNOWN, "UNKNOWN", "未知市场"}:
        return explicit
    for packet in (home_snapshot, decision_packet, strategy_packet, live_packet):
        payload = _as_mapping(packet)
        market = _to_text(payload.get("market_type") or payload.get("asset_type"))
        if not market and not isinstance(payload.get("market"), Mapping):
            market = _to_text(payload.get("market"))
        if market and market not in {MARKET_UNKNOWN, "UNKNOWN", "未知市场"}:
            return market
    return identify_market_type(ticker=ticker, name=name)


def _method_tone(status: Any) -> str:
    text = _to_text(status)
    if text == "通过":
        return "ready"
    if text == "失败":
        return "failed"
    if text == "不适用":
        return "missing"
    return "stale"


def _method_rank(item: Mapping[str, Any]) -> tuple[int, str]:
    status = _to_text(item.get("status"))
    fit = _to_text(item.get("fit"))
    priority = {
        "通过": 0,
        "失败": 1,
        "待验证": 2,
        "数据不足": 2,
        "不适用": 4,
    }.get(status, 3)
    if fit == "核心" and priority > 0:
        priority -= 1
    return priority, _to_text(item.get("name"))


def _build_method_items(methods: Any) -> list[dict]:
    method_payloads = [_as_mapping(item) for item in _as_list(methods)]
    method_payloads = [item for item in method_payloads if item]
    ordered = sorted(method_payloads, key=_method_rank)
    result = []
    for item in ordered[:MAX_METHOD_ITEMS]:
        result.append(
            {
                "name": _to_text(item.get("name"), "分析方法"),
                "status": _to_text(item.get("status"), "待验证"),
                "tone": _method_tone(item.get("status")),
                "evidence": _to_text(item.get("evidence"), "数据不足，待刷新验证。"),
                "risk": _to_text(item.get("risk"), "数据缺口"),
                "action_hint": _to_text(item.get("action_hint"), "待验证后再行动。"),
                "fit": _to_text(item.get("fit"), "待适配"),
            }
        )
    return result


def _status(market: str, ticker: str) -> str:
    if market in KNOWN_MARKETS:
        return "ready"
    if ticker:
        return "waiting"
    return "waiting"


def _data_gap_text(analysis_method_packet: Mapping[str, Any], method_items: list[dict]) -> str:
    coverage = _as_mapping(analysis_method_packet.get("data_coverage"))
    missing = [key for key, state in coverage.items() if state == "missing"]
    pending = [item["name"] for item in method_items if item.get("status") in {"待验证", "数据不足"}]
    if missing:
        return f"待验证模块：{'、'.join(missing[:4])}。"
    if pending:
        return f"待验证方法：{'、'.join(pending[:4])}。"
    return "暂无显式数据缺口；仍需按市场口径复核。"


def build_market_profile_evidence_strip(
    market_type: Any = None,
    ticker: Any = "",
    name: Any = "",
    live_packet: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    home_snapshot: Any = None,
    analysis_method_packet: Any = None,
) -> dict:
    resolved_ticker, resolved_name = _resolve_ticker_and_name(
        ticker=ticker,
        name=name,
        live_packet=live_packet,
        decision_packet=decision_packet,
        strategy_packet=strategy_packet,
        home_snapshot=home_snapshot,
    )
    resolved_market = _resolve_market(
        market_type=market_type,
        ticker=resolved_ticker,
        name=resolved_name,
        analysis_method_packet=analysis_method_packet,
        live_packet=live_packet,
        decision_packet=decision_packet,
        strategy_packet=strategy_packet,
        home_snapshot=home_snapshot,
    )
    profile = get_market_analysis_profile(resolved_market, ticker=resolved_ticker, name=resolved_name)
    analysis = _as_mapping(analysis_method_packet)
    if not analysis:
        analysis = build_analysis_method_packet(
            market_type=resolved_market,
            ticker=resolved_ticker,
            name=resolved_name,
            live_packet=live_packet,
            strategy_packet=strategy_packet,
            decision_packet=decision_packet,
            profile=profile,
        )

    market = _to_text(analysis.get("market"), _to_text(profile.get("market"), resolved_market or MARKET_UNKNOWN))
    method_items = _build_method_items(analysis.get("methods"))
    focus_items = _unique_text(
        _as_list(profile.get("indicator_focus")) + _as_list(profile.get("core_features")),
        MAX_FOCUS_ITEMS,
    )
    risk_notes = _unique_text(profile.get("risk_focus"), MAX_RISK_NOTES)
    data_sources = _unique_text(profile.get("data_source_priority"), MAX_DATA_SOURCES)
    market_label = _to_text(profile.get("label")) or (market if market in KNOWN_MARKETS else "市场类型待确认")

    return {
        "status": _status(market, resolved_ticker),
        "market_type": market,
        "market_label": market_label if market in KNOWN_MARKETS else "市场类型待确认",
        "ticker": resolved_ticker,
        "name": resolved_name,
        "summary": _to_text(analysis.get("summary"), f"{market_label} 分析口径待验证。"),
        "data_sources": data_sources,
        "focus_items": focus_items,
        "method_items": method_items,
        "risk_notes": risk_notes,
        "data_gap_text": _data_gap_text(analysis, method_items),
        "source": "rule-based market profile / command_center_analysis_methods",
        "deepseek_called": False,
        "manual_required_text": "只读取本地 packet/profile；不会自动请求 Tushare、AkShare、yfinance、Supabase 或 DeepSeek。",
    }
