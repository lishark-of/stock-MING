from __future__ import annotations

import datetime as _dt
import json
import uuid
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any


CACHE_DIR = Path(__file__).resolve().parent / ".stock_ming_cache"
DEFAULT_LOG_PATH = CACHE_DIR / "trade_review_log.jsonl"
USER_DECISIONS = ("未执行", "已执行", "观察", "放弃")
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").replace("¥", "").strip())
    except Exception:
        return None


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _display_a_share_ticker(value: Any) -> str:
    text = _text(value).upper()
    if text.endswith(".SS"):
        return f"{text[:-3]}.SH"
    if text.isdigit() and len(text) == 6:
        if text.startswith("6"):
            return f"{text}.SH"
        if text.startswith(("0", "3")):
            return f"{text}.SZ"
    return text


def _is_sensitive_key(key: Any) -> bool:
    lower = str(key or "").lower()
    return any(part in lower for part in SENSITIVE_KEY_PARTS)


def _scrub(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _scrub(val) for key, val in value.items() if not _is_sensitive_key(key)}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, tuple):
        return [_scrub(item) for item in value]
    return value


def _compact_candidates(items: Any, limit: int = 3) -> list[dict]:
    result = []
    for item in _as_list(items):
        payload = _as_mapping(item)
        if not payload:
            continue
        result.append(
            _scrub(
                {
                    "ticker": _display_a_share_ticker(_first(payload.get("ticker"), payload.get("code"))),
                    "name": _text(payload.get("name") or payload.get("stock_name")),
                    "status": _text(payload.get("action_state") or payload.get("status"), "待验证"),
                    "score": _first(payload.get("score"), payload.get("total_score"), payload.get("rank_reason")),
                    "reason": _text(payload.get("reason") or payload.get("summary") or payload.get("why")),
                    "trigger": _text(payload.get("trigger") or payload.get("trigger_condition")),
                    "invalid_condition": _text(payload.get("invalid_condition") or payload.get("invalidation_condition")),
                    "source": _text(payload.get("source")),
                    "updated_at": _text(payload.get("updated_at") or payload.get("generated_at")),
                }
            )
        )
        if len(result) >= limit:
            break
    return result


def _compact_etfs(*sources: Any, limit: int = 6) -> list[dict]:
    result = []
    for source in sources:
        for item in _as_list(source):
            payload = _as_mapping(item)
            if not payload:
                continue
            result.append(
                _scrub(
                    {
                        "name": _text(payload.get("name") or payload.get("etf_name")),
                        "code": _text(payload.get("code") or payload.get("ticker")),
                        "bucket": _text(payload.get("bucket") or payload.get("theme")),
                        "status": _text(payload.get("status") or payload.get("action_state"), "观察"),
                        "ratio": _first(payload.get("weight"), payload.get("suggested_ratio"), payload.get("ratio")),
                        "amount": _first(payload.get("amount"), payload.get("suggested_amount")),
                        "reason": _text(payload.get("reason") or payload.get("summary")),
                        "updated_at": _text(payload.get("updated_at") or payload.get("generated_at")),
                    }
                )
            )
            if len(result) >= limit:
                return result
    return result


def _floating_values(holding: dict, shares: float | None, cost_price: float | None, current_price: float | None) -> tuple[float | None, float | None]:
    floating = _as_mapping(holding.get("floating_pnl"))
    amount = _num(_first(holding.get("floating_pnl_amount"), floating.get("amount"), holding.get("pnl_amount")))
    pct = _num(_first(holding.get("floating_pnl_pct"), floating.get("pct"), holding.get("pnl_pct")))
    if amount is None and shares is not None and cost_price is not None and current_price is not None:
        amount = round((current_price - cost_price) * shares, 2)
    if pct is None and cost_price not in (None, 0) and current_price is not None:
        pct = round((current_price - cost_price) / cost_price * 100, 4)
    return amount, pct


def build_trade_review_record(
    *,
    target: Any = "",
    name: Any = "",
    market_type: Any = "",
    position_profile: Any = None,
    price_detail: Any = None,
    home_snapshot: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    radar_packet: Any = None,
    etf_packet: Any = None,
    projection_packet: Any = None,
    full_refresh_steps: Any = None,
    deepseek_summary: Any = "",
    deepseek_used: bool | None = None,
    user_decision: Any = "未执行",
    user_note: Any = "",
    follow_up_date: Any = "",
    validation_conditions: Any = None,
    record_id: Any = "",
    created_at: Any = "",
) -> dict:
    snapshot = _as_mapping(home_snapshot)
    profile = _as_mapping(position_profile)
    price_info = _as_mapping(price_detail)
    holding = _as_mapping(snapshot.get("holding_action"))
    decision = _as_mapping(decision_packet) or _as_mapping(snapshot.get("today_action"))
    strategy = _as_mapping(strategy_packet) or _as_mapping(snapshot.get("strategy_packet"))
    radar = _as_mapping(radar_packet) or _as_mapping(snapshot.get("radar_packet"))
    etf = _as_mapping(etf_packet) or _as_mapping(snapshot.get("etf_packet"))
    margin_summary = _as_mapping(snapshot.get("margin_etf_summary"))
    projection = _as_mapping(projection_packet) or _as_mapping(snapshot.get("projection_packet"))
    data_freshness = _as_mapping(snapshot.get("data_freshness"))
    refresh_steps = _as_list(full_refresh_steps)[:8]
    if refresh_steps and "full_refresh_steps" not in data_freshness:
        data_freshness["full_refresh_steps"] = refresh_steps
    if not data_freshness:
        data_freshness = {"full_refresh_steps": refresh_steps}

    ticker = _display_a_share_ticker(
        _first(
            target,
            holding.get("ticker"),
            profile.get("ticker"),
            decision.get("ticker"),
            snapshot.get("ticker"),
        )
    )
    shares = _num(_first(holding.get("shares"), holding.get("holding_units"), profile.get("shares"), profile.get("holding_units")))
    cost_price = _num(_first(holding.get("cost_price"), holding.get("cost"), profile.get("cost_price"), profile.get("cost")))
    current_price = _num(_first(holding.get("current_price"), price_info.get("price"), profile.get("current_price")))
    floating_pnl, floating_pnl_pct = _floating_values(holding, shares, cost_price, current_price)
    margin_ratio = _num(
        _first(
            profile.get("margin_ratio_pct"),
            holding.get("margin_ratio"),
            margin_summary.get("current_margin_ratio"),
        )
    )
    decision_text = _text(user_decision, "未执行")
    if decision_text not in USER_DECISIONS:
        decision_text = "未执行"

    next_ticket_top3 = _compact_candidates(
        _first(
            radar.get("top_candidates"),
            radar.get("watch_candidates"),
            snapshot.get("next_ticket_candidates"),
            radar.get("results"),
        ),
        limit=3,
    )
    etf_actions = _compact_etfs(
        etf.get("actionable_etfs"),
        etf.get("watch_etfs"),
        margin_summary.get("actionable_etfs"),
        margin_summary.get("watch_etfs"),
        margin_summary.get("recommended_etfs"),
        etf.get("recommended_etfs"),
    )
    conditions = {
        "add": _text(_first(strategy.get("add_condition"), holding.get("add_condition")), "待验证"),
        "reduce": _text(_first(strategy.get("reduce_condition"), holding.get("reduce_condition")), "待验证"),
        "invalidation": _text(_first(strategy.get("invalidation_condition"), holding.get("invalidation_condition")), "待验证"),
    }
    deepseek_text = _text(deepseek_summary)
    record = {
        "id": _text(record_id) or uuid.uuid4().hex,
        "created_at": _text(created_at) or _dt.datetime.now().isoformat(timespec="seconds"),
        "ticker": ticker,
        "name": _text(_first(name, holding.get("name"), profile.get("name"), snapshot.get("name"))),
        "market_type": _text(_first(market_type, profile.get("market_type"), snapshot.get("market_type"))),
        "shares": shares,
        "cost_price": cost_price,
        "current_price": current_price,
        "floating_pnl": floating_pnl,
        "floating_pnl_pct": floating_pnl_pct,
        "horizon": _text(_first(profile.get("analysis_horizon"), holding.get("investment_horizon"), snapshot.get("horizon")), "短中期"),
        "margin_ratio": margin_ratio,
        "overall_action": _text(_first(decision.get("overall_action"), strategy.get("overall_action"), strategy.get("action")), "等待"),
        "position_action": _text(_first(decision.get("position_mode"), decision.get("position_action"), strategy.get("position_action")), "待验证"),
        "margin_action": _text(_first(decision.get("margin_mode"), decision.get("margin_action")), "不使用融资"),
        "risk_breakdown": _scrub(_first(snapshot.get("risk_breakdown"), decision.get("risk_breakdown"), {})),
        "position_budget": _scrub(_first(strategy.get("risk_budget"), decision.get("position_budget"), snapshot.get("position_budget"), {})),
        "next_ticket_top3": next_ticket_top3,
        "etf_actions": etf_actions,
        "projection_paths": _scrub(_as_list(projection.get("paths"))[:3]),
        "strategy_action": _text(_first(strategy.get("overall_action"), strategy.get("action")), "待验证"),
        "strategy_conditions": _scrub(conditions),
        "data_freshness": _scrub(data_freshness),
        "deepseek_used": bool(deepseek_used) if deepseek_used is not None else bool(deepseek_text),
        "deepseek_summary": deepseek_text[:1200],
        "user_decision": decision_text,
        "user_note": _text(user_note),
        "follow_up_date": _text(follow_up_date),
        "validation_conditions": [_text(item) for item in _as_list(validation_conditions) if _text(item)],
    }
    return _scrub(record)


def append_trade_review_record(record: Mapping[str, Any], path: Any = None) -> dict:
    payload = _scrub(dict(record or {}))
    log_path = Path(path) if path else DEFAULT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    return payload


def load_trade_review_records(limit: int | None = 20, path: Any = None) -> list[dict]:
    log_path = Path(path) if path else DEFAULT_LOG_PATH
    if not log_path.exists():
        return []
    records = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(_scrub(item))
    records = list(reversed(records))
    if limit is None or limit <= 0:
        return records
    return records[:limit]


def summarize_trade_review_records(records: Any) -> dict:
    items = [item for item in _as_list(records) if isinstance(item, Mapping)]
    ticker_counts = Counter(_text(item.get("ticker"), "未知") for item in items)
    decision_counts = Counter(_text(item.get("user_decision"), "未执行") for item in items)
    action_counts = Counter(_text(item.get("overall_action"), "等待") for item in items)
    return {
        "total": len(items),
        "latest": dict(items[0]) if items else {},
        "tickers": dict(ticker_counts),
        "user_decisions": dict(decision_counts),
        "overall_actions": dict(action_counts),
    }
