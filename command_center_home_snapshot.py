from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from numbers import Number
from pathlib import Path
from typing import Any

import command_center_facts_packet as facts_packet_service
import command_center_radar_packet as radar_packet_service
import command_center_etf_packet as etf_packet_service
import command_center_discipline_packet as discipline_packet_service


CACHE_DIR_NAME = ".stock_ming_cache"
SNAPSHOT_FILENAME = "command_center_latest.json"
SNAPSHOT_SOURCE = "command_center_home_snapshot"
MAX_CANDIDATES = 3
MAX_ERRORS = 8
MAX_CAPABILITY_ITEMS = 8

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "access_token",
    "refresh_token",
    "auth_token",
    "bearer",
    "deepseek_prompt",
    "raw_prompt",
    "prompt_text",
    "system_prompt",
    "user_prompt",
)

MODULE_LABELS = {
    "market": "市场",
    "quant": "量化",
    "discipline": "纪律",
    "margin_etf": "融资 ETF",
    "next_ticket": "下一票",
    "strategy_execution": "策略执行",
}

DATA_GAP_LABELS = {
    **MODULE_LABELS,
    "decision": "今日总决策",
}

CAPABILITY_RESTRICTED_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
CAPABILITY_PENDING_STATES = {"empty_recent", "stale_cache", "fallback_used", "requires_manual_refresh", "unknown"}


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


def _to_number(value: Any) -> int | float | None:
    if value in [None, ""]:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Number):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("¥", "").replace("￥", "").replace("%", "")
        if not text or text in {"暂无", "None", "nan", "--"}:
            return None
        try:
            number = float(text)
            return int(number) if number.is_integer() else number
        except Exception:
            return None
    return None


def _now_iso(now: Any = None) -> str:
    if isinstance(now, _dt.datetime):
        return now.isoformat(timespec="seconds")
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min).isoformat(timespec="seconds")
    if isinstance(now, str) and now.strip():
        return now.strip()
    return _dt.datetime.now().isoformat(timespec="seconds")


def _today_string(today: Any = None) -> str:
    if isinstance(today, _dt.datetime):
        return today.date().isoformat()
    if isinstance(today, _dt.date):
        return today.isoformat()
    if isinstance(today, str) and len(today) >= 10:
        return today[:10]
    return _dt.date.today().isoformat()


def _is_sensitive_key(key: Any) -> bool:
    text = str(key or "").lower()
    return any(part in text for part in SENSITIVE_KEY_PARTS)


def sanitize_snapshot_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        clean = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                continue
            clean[str(key)] = sanitize_snapshot_payload(item)
        return clean
    if isinstance(value, (list, tuple, set)):
        return [sanitize_snapshot_payload(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return _to_text(value)


def get_home_snapshot_path(base_dir: str | Path | None = None) -> Path:
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    return root / CACHE_DIR_NAME / SNAPSHOT_FILENAME


def _empty_snapshot(reason: str = "暂无可执行候选。点击刷新今日基础数据生成。") -> dict:
    return {
        "status": "empty",
        "is_empty": True,
        "timestamp": "",
        "source": SNAPSHOT_SOURCE,
        "decision_packet": {},
        "strategy_packet": {},
        "today_action": {
            "overall_action": "等待",
            "risk_level": "中",
            "market_bias": "未刷新",
            "position_mode": "空仓等待",
            "margin_mode": "不使用融资",
        },
        "holding_action": {
            "ticker": "",
            "name": "",
            "investment_horizon": "",
            "cost": None,
            "shares": None,
            "current_price": None,
            "floating_pnl": None,
            "floating_pnl_text": "暂无",
            "action_state": "待刷新",
            "add_condition": "等待量化、纪律和市场至少两项同向后再考虑。",
            "reduce_condition": "触发止损、减仓或风险预算失效时优先降低暴露。",
            "invalidation_condition": "市场环境转弱或纪律信号反向时，本轮建议失效。",
        },
        "next_ticket_candidates": [],
        "radar_packet": radar_packet_service.build_command_center_radar_packet({}),
        "etf_packet": etf_packet_service.build_command_center_etf_packet({}),
        "discipline_packet": discipline_packet_service.build_command_center_discipline_packet({}),
        "margin_etf_summary": {
            "current_margin_ratio": None,
            "recommended_margin_ratio": None,
            "recommended_cash_ratio": None,
            "today_main_direction": "待刷新",
            "recommended_etfs": [],
            "watch_not_chase": ["暂无 ETF 快照；不追高，等待刷新后再判断。"],
        },
        "risk_alerts": {
            "must_not_do": ["不追高", "不满仓", "不在未刷新数据下加融资"],
            "reduce_conditions": [],
            "data_gaps": [reason],
            "uses_cache": False,
        },
        "data_coverage": {key: "missing" for key in DATA_GAP_LABELS},
        "data_freshness": {
            "state": "missing",
            "label": "待刷新",
            "last_updated": "暂无",
            "deepseek_called": False,
        },
        "data_capability": build_data_capability_snapshot({}),
        "facts_packet": facts_packet_service.build_command_center_facts_packet({}),
        "errors": [],
        "empty_message": reason,
        "deepseek_called": False,
    }


def load_home_action_snapshot(path: str | Path | None = None, base_dir: str | Path | None = None) -> dict:
    snapshot_path = Path(path) if path is not None else get_home_snapshot_path(base_dir)
    if not snapshot_path.exists():
        return _empty_snapshot()
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception as exc:
        snapshot = _empty_snapshot("本地交易快照读取失败。点击刷新今日基础数据重新生成。")
        snapshot["status"] = "failed"
        snapshot["errors"] = [{"module": "home_snapshot", "message": _to_text(exc), "source": str(snapshot_path), "updated_at": ""}]
        return snapshot
    if not isinstance(payload, Mapping):
        return _empty_snapshot("本地交易快照格式不可用。点击刷新今日基础数据重新生成。")
    snapshot = sanitize_snapshot_payload(payload)
    snapshot.setdefault("source", SNAPSHOT_SOURCE)
    snapshot.setdefault("deepseek_called", False)
    snapshot["is_empty"] = bool(snapshot.get("is_empty"))
    snapshot["data_freshness"] = build_data_freshness(
        snapshot.get("timestamp"),
        snapshot.get("errors"),
        deepseek_called=bool(snapshot.get("deepseek_called")),
    )
    snapshot["data_capability"] = build_data_capability_snapshot(snapshot.get("data_capability") or {})
    snapshot["facts_packet"] = facts_packet_service.build_command_center_facts_packet(
        {"command_center_facts_packet": snapshot.get("facts_packet") or {}}
    )
    snapshot["radar_packet"] = radar_packet_service.build_command_center_radar_packet(
        {"command_center_radar_packet": snapshot.get("radar_packet") or {}}
    )
    snapshot["etf_packet"] = etf_packet_service.build_command_center_etf_packet(
        {"command_center_etf_packet": snapshot.get("etf_packet") or {}}
    )
    snapshot["discipline_packet"] = discipline_packet_service.build_command_center_discipline_packet(
        {"command_center_discipline_packet": snapshot.get("discipline_packet") or {}}
    )
    return snapshot


def save_home_action_snapshot(snapshot: Mapping[str, Any], path: str | Path | None = None, base_dir: str | Path | None = None) -> Path:
    snapshot_path = Path(path) if path is not None else get_home_snapshot_path(base_dir)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload = sanitize_snapshot_payload(snapshot)
    temp_path = snapshot_path.with_suffix(snapshot_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(snapshot_path)
    return snapshot_path


def classify_data_freshness(timestamp: Any, today: Any = None) -> str:
    text = _to_text(timestamp)
    if not text or text == "暂无":
        return "missing"
    return "today" if text[:10] == _today_string(today) else "stale"


def build_data_freshness(timestamp: Any = None, errors: Any = None, deepseek_called: bool = False, today: Any = None) -> dict:
    error_list = _as_list(errors)
    if error_list:
        state, label = "partial_failed", "部分失败"
    else:
        state = classify_data_freshness(timestamp, today=today)
        label = {"today": "今日已刷新", "stale": "使用缓存", "missing": "待刷新"}[state]
    return {
        "state": state,
        "label": label,
        "last_updated": _to_text(timestamp, "暂无"),
        "deepseek_called": bool(deepseek_called),
    }


def _packet_data_coverage(live_packet: Any, decision_packet: Any, strategy_packet: Any) -> dict:
    decision = _as_mapping(decision_packet)
    coverage = _as_mapping(decision.get("data_coverage"))
    result = {}
    live = _as_mapping(live_packet)
    for key in MODULE_LABELS:
        state = _to_text(coverage.get(key))
        if not state:
            section = _as_mapping(live.get(key))
            if section.get("is_fresh") or _to_text(section.get("status")) in {"已刷新", "ready", "ok", "completed"}:
                state = "ready"
            elif section.get("last_success") or section.get("stale"):
                state = "cached"
            else:
                state = "missing"
        result[key] = state if state in {"ready", "cached", "missing"} else "missing"
    strategy_state = result.get("strategy_execution")
    if strategy_packet:
        status = _to_text(_as_mapping(strategy_packet).get("status"))
        strategy_state = "ready" if status in {"ready", "completed", "ok", "success"} else ("cached" if _as_mapping(strategy_packet).get("stale") else strategy_state)
    result["strategy_execution"] = strategy_state or "missing"
    result["decision"] = "ready" if decision else "missing"
    return result


def _extract_errors(*packets: Any) -> list[dict]:
    items = []
    for packet in packets:
        payload = _as_mapping(packet)
        raw_errors = payload.get("errors") or []
        if isinstance(raw_errors, (str, Mapping)):
            raw_errors = [raw_errors]
        if isinstance(raw_errors, (list, tuple)):
            for item in raw_errors:
                err = _as_mapping(item)
                if err:
                    message = _to_text(err.get("message") or err.get("error") or err.get("last_error"))
                    module = _to_text(err.get("module"), "模块")
                    updated_at = _to_text(err.get("updated_at") or payload.get("updated_at") or payload.get("finished_at"), "暂无")
                    source = _to_text(err.get("source"), "未加载")
                else:
                    message = _to_text(item)
                    module = "模块"
                    updated_at = _to_text(payload.get("updated_at") or payload.get("finished_at"), "暂无")
                    source = "未加载"
                if message:
                    items.append({"module": module, "message": message, "updated_at": updated_at, "source": source})
        for key in ("last_error", "error"):
            message = _to_text(payload.get(key))
            if message:
                items.append(
                    {
                        "module": _to_text(payload.get("module"), "模块"),
                        "message": message,
                        "updated_at": _to_text(payload.get("updated_at") or payload.get("finished_at"), "暂无"),
                        "source": _to_text(payload.get("source"), "未加载"),
                    }
                )
    deduped = []
    seen = set()
    for item in items:
        key = (item["module"], item["message"], item["updated_at"], item["source"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:MAX_ERRORS]


def _normalize_capability_state(item: Mapping[str, Any]) -> str:
    state = _to_text(item.get("capability_state") or item.get("state"))
    if state:
        return state
    if item.get("permission_likely"):
        return "permission_denied"
    if item.get("ok"):
        return "available"
    return "unknown"


def build_data_capability_snapshot(data_capability_packet: Any = None) -> dict:
    packet = _as_mapping(data_capability_packet)
    raw_items = packet.get("items") or []
    if not isinstance(raw_items, (list, tuple)):
        raw_items = []
    items = []
    for raw in raw_items:
        payload = _as_mapping(raw)
        if not payload:
            continue
        state = _normalize_capability_state(payload)
        label = _to_text(payload.get("label") or payload.get("api") or payload.get("section"), "数据能力")
        items.append(
            {
                "key": _to_text(payload.get("section") or payload.get("api"), "data_capability"),
                "label": label,
                "provider": _to_text(payload.get("provider") or payload.get("source") or packet.get("source"), "数据能力"),
                "api": _to_text(payload.get("api")),
                "status": _to_text(payload.get("status") or payload.get("capability_label") or state, "待验证"),
                "state": state,
                "latest_date": _to_text(payload.get("latest_date")),
                "updated_at": _to_text(payload.get("updated_at")),
                "source": _to_text(payload.get("source") or packet.get("source"), "数据能力"),
                "action_hint": _to_text(payload.get("action_hint")),
                "error": _to_text(payload.get("error")),
            }
        )
    items = items[:MAX_CAPABILITY_ITEMS]
    available = [item["label"] for item in items if item["state"] == "available"]
    restricted = [item["label"] for item in items if item["state"] in CAPABILITY_RESTRICTED_STATES]
    pending = [item["label"] for item in items if item["state"] in CAPABILITY_PENDING_STATES]
    summary = (
        f"可用：{'、'.join(available) if available else '无'}｜"
        f"受限：{'、'.join(restricted) if restricted else '无'}｜"
        f"待验证：{'、'.join(pending) if pending else '无'}"
        if items
        else "尚未检测；页面打开不会自动请求 Tushare、AkShare 或 yfinance。"
    )
    return {
        "source": _to_text(packet.get("source"), "数据能力"),
        "checked_at": _to_text(packet.get("checked_at") or packet.get("updated_at")),
        "summary": summary,
        "available_count": len(available),
        "restricted_count": len(restricted),
        "pending_count": len(pending),
        "items": items,
        "deepseek_called": False,
    }


def build_holding_action(target: str = "", position_profile: Any = None, strategy_packet: Any = None, state: Any = None) -> dict:
    state_map = _as_mapping(state)
    profile = _as_mapping(position_profile) or _as_mapping(state_map.get("position_profile")) or _as_mapping(state_map.get("current_holding_context"))
    strategy = _as_mapping(strategy_packet)
    ticker = _to_text(profile.get("ticker") or profile.get("current_holding_ticker") or target)
    pnl_pct = _to_number(profile.get("pnl_pct") or profile.get("floating_profit_pct"))
    pnl_amount = _to_number(profile.get("pnl_amount") or profile.get("floating_profit_amount"))
    pnl_text = _to_text(profile.get("profit_state"))
    if not pnl_text:
        if pnl_pct is not None and pnl_amount is not None:
            pnl_text = f"{pnl_pct:+.2f}% / ¥{pnl_amount:,.0f}"
        elif pnl_pct is not None:
            pnl_text = f"{pnl_pct:+.2f}%"
        else:
            pnl_text = "暂无"
    return {
        "ticker": ticker,
        "name": _to_text(profile.get("name") or profile.get("current_holding_name")),
        "investment_horizon": _to_text(
            profile.get("investment_horizon")
            or profile.get("holding_period")
            or profile.get("trade_horizon")
            or state_map.get("investment_horizon")
            or state_map.get("holding_period")
        ),
        "cost": _to_number(profile.get("cost_price") or profile.get("cost")),
        "shares": _to_number(profile.get("holding_units") or profile.get("shares")),
        "current_price": _to_number(profile.get("current_price")),
        "floating_pnl": {"pct": pnl_pct, "amount": pnl_amount},
        "floating_pnl_text": pnl_text,
        "action_state": _to_text(strategy.get("action") or profile.get("holding_action_state") or profile.get("normalized_position_state"), "待刷新"),
        "add_condition": _to_text(strategy.get("add_condition"), "等待量化、纪律和市场至少两项同向后再考虑。"),
        "reduce_condition": _to_text(strategy.get("reduce_condition"), "触发止损、减仓或风险预算失效时优先降低暴露。"),
        "invalidation_condition": _to_text(strategy.get("invalidation_condition"), "市场环境转弱或纪律信号反向时，本轮建议失效。"),
    }


def _candidate_from_row(row: Any, scan_state: Any = None, live_section: Any = None) -> dict:
    row_map = _as_mapping(row)
    scan = _as_mapping(scan_state)
    live = _as_mapping(live_section)
    candidate = _as_mapping(row_map.get("candidate")) or row_map
    score = _as_mapping(row_map.get("score")) or row_map
    return {
        "ticker": _to_text(candidate.get("ticker") or score.get("ticker")),
        "name": _to_text(candidate.get("name") or score.get("name")),
        "action_state": _to_text(score.get("battle_state") or row_map.get("action_state") or candidate.get("action_state"), "只观察"),
        "score": _to_number(score.get("total_score") or score.get("score") or row_map.get("score")),
        "trigger_condition": _to_text(
            score.get("trigger_condition")
            or row_map.get("trigger_condition")
            or score.get("one_sentence_conclusion")
            or row_map.get("summary"),
            "等待规则雷达触发条件确认。",
        ),
        "invalidation_condition": _to_text(
            score.get("invalidation_condition")
            or row_map.get("invalidation_condition")
            or score.get("fail_condition"),
            "市场转弱、候选评分下降或纪律信号反向时失效。",
        ),
        "source": _to_text(row_map.get("source") or scan.get("source") or live.get("source"), "下一票雷达缓存"),
        "updated_at": _to_text(row_map.get("updated_at") or row_map.get("generated_at") or scan.get("generated_at") or live.get("updated_at"), "暂无"),
    }


def extract_next_ticket_candidates(state: Any = None, live_packet: Any = None, limit: int = MAX_CANDIDATES) -> list[dict]:
    state_map = _as_mapping(state)
    radar_packet = _as_mapping(state_map.get("command_center_radar_packet"))
    if radar_packet.get("top_candidates"):
        return _as_list(radar_packet.get("top_candidates"))[:limit]
    live = _as_mapping(live_packet)
    live_section = _as_mapping(live.get("next_ticket"))
    scan_state = _as_mapping(state_map.get("radar_scan_results"))
    rows = _as_list(live_section.get("top_candidates"))
    if not rows:
        rows = _as_list(scan_state.get("rule_rows") or scan_state.get("results"))
    candidates = []
    seen = set()
    for row in rows:
        item = _candidate_from_row(row, scan_state=scan_state, live_section=live_section)
        key = item.get("ticker") or item.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append(item)
    return candidates[:limit]


def _flatten_etf_candidates(candidates: Any) -> list[dict]:
    rows = []
    if isinstance(candidates, Mapping):
        for bucket, items in candidates.items():
            for item in _as_list(items):
                payload = _as_mapping(item)
                if payload:
                    payload.setdefault("bucket", bucket)
                    rows.append(payload)
    else:
        rows = [_as_mapping(item) for item in _as_list(candidates)]
    normalized = []
    for row in rows:
        if not row:
            continue
        normalized.append(
            {
                "code": _to_text(row.get("etf_code") or row.get("code") or row.get("ts_code")),
                "name": _to_text(row.get("etf_name") or row.get("name")),
                "bucket": _to_text(row.get("bucket") or row.get("theme"), "ETF"),
                "score": _to_number(row.get("total_score") or row.get("score")),
                "action_state": _to_text(row.get("action_state") or row.get("advice"), "只观察不追"),
            }
        )
    return normalized[:MAX_CANDIDATES]


def _current_margin_ratio_from_state(state: Mapping[str, Any], allocation: Mapping[str, Any]) -> int | float | None:
    explicit = _to_number(
        allocation.get("current_margin_debt_ratio")
        or state.get("current_margin_debt_ratio")
        or state.get("margin_current_margin_ratio")
        or state.get("margin_ratio")
    )
    if explicit is not None:
        return explicit
    margin_debt = _to_number(state.get("margin_debt"))
    total_asset = _to_number(state.get("margin_total_asset"))
    cash = _to_number(state.get("margin_cash_balance")) or 0
    stock_value = _to_number(state.get("margin_stock_value")) or 0
    etf_value = _to_number(state.get("margin_etf_value")) or 0
    if margin_debt is None:
        return None
    gross_assets = max(total_asset or 0, cash + stock_value + etf_value, margin_debt)
    net_asset = gross_assets - margin_debt
    if net_asset <= 0:
        return None
    ratio = margin_debt / net_asset * 100
    return round(ratio, 2)


def build_margin_etf_summary(state: Any = None, live_packet: Any = None, etf_packet: Any = None) -> dict:
    state_map = _as_mapping(state)
    live_section = _as_mapping(_as_mapping(live_packet).get("margin_etf"))
    etf = _as_mapping(etf_packet) or etf_packet_service.build_command_center_etf_packet(state_map, live_packet)
    allocation = _as_mapping(state_map.get("legacy_margin_etf_allocation_result"))
    candidates = _as_list(etf.get("recommended_etfs")) or _flatten_etf_candidates(allocation.get("selected_etf_candidates") or allocation.get("recommended_etfs"))
    watch_not_chase = etf.get("watch_not_chase") or allocation.get("watch_not_chase") or allocation.get("watch_not_chase_etfs") or []
    watch_not_chase_items = [_to_text(item) for item in _as_list(watch_not_chase)]
    watch_not_chase_items = [item for item in watch_not_chase_items if item]
    if not watch_not_chase_items:
        watch_not_chase_items = ["不追高 ETF；等待回踩、量能和风险线确认。"]
    current_margin_ratio = _to_number(etf.get("current_margin_ratio"))
    if current_margin_ratio is None:
        current_margin_ratio = _current_margin_ratio_from_state(state_map, allocation)
    return {
        "current_margin_ratio": current_margin_ratio,
        "recommended_margin_ratio": _to_number(etf.get("recommended_margin_ratio") or live_section.get("recommended_margin_ratio") or allocation.get("recommended_margin_ratio")),
        "recommended_cash_ratio": _to_number(etf.get("recommended_cash_ratio") or live_section.get("recommended_cash_ratio") or allocation.get("recommended_cash_ratio")),
        "today_main_direction": _to_text(etf.get("today_main_direction") or live_section.get("today_main_direction") or allocation.get("today_main_direction") or allocation.get("action_state"), "待刷新"),
        "recommended_etfs": candidates[:MAX_CANDIDATES],
        "watch_not_chase": watch_not_chase_items[:MAX_CANDIDATES],
    }


def build_today_action(decision_packet: Any = None) -> dict:
    decision = _as_mapping(decision_packet)
    return {
        "overall_action": _to_text(decision.get("overall_action"), "等待"),
        "risk_level": _to_text(decision.get("risk_level"), "中"),
        "market_bias": _to_text(decision.get("market_bias"), "未刷新"),
        "position_mode": _to_text(decision.get("position_mode"), "空仓等待"),
        "margin_mode": _to_text(decision.get("margin_mode"), "不使用融资"),
    }


def build_risk_alerts(decision_packet: Any = None, strategy_packet: Any = None, coverage: Any = None, errors: Any = None) -> dict:
    decision = _as_mapping(decision_packet)
    strategy = _as_mapping(strategy_packet)
    must_not_do = [_to_text(item) for item in _as_list(decision.get("must_not_do"))]
    must_not_do = [item for item in must_not_do if item] or ["不追高", "不满仓", "不在未刷新数据下加融资"]
    reduce_conditions = [_to_text(strategy.get("reduce_condition")) or _to_text(item) for item in _as_list(decision.get("next_validation_conditions"))]
    reduce_conditions = [item for item in reduce_conditions if item][:MAX_CANDIDATES]
    coverage_map = _as_mapping(coverage)
    data_gaps = [DATA_GAP_LABELS.get(key, key) for key, state in coverage_map.items() if state == "missing"]
    if _as_list(errors):
        data_gaps.append("存在刷新失败模块")
    return {
        "must_not_do": must_not_do[:5],
        "reduce_conditions": reduce_conditions,
        "data_gaps": data_gaps[:8] or ["暂无显式数据缺口"],
        "uses_cache": any(state == "cached" for state in coverage_map.values()),
    }


def build_home_action_snapshot(
    state: Any = None,
    target: str = "",
    position_profile: Any = None,
    live_packet: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    refresh_summary: Any = None,
    data_capability_packet: Any = None,
    facts_packet: Any = None,
    radar_packet: Any = None,
    now: Any = None,
) -> dict:
    state_map = _as_mapping(state)
    live = _as_mapping(live_packet or state_map.get("command_center_live_packet"))
    decision = _as_mapping(
        decision_packet
        or state_map.get("command_center_decision_packet")
        or state_map.get("command_center_decision_last_success")
    )
    strategy = _as_mapping(
        strategy_packet
        or state_map.get("strategy_execution_packet")
        or state_map.get("strategy_execution_last_success")
    )
    if data_capability_packet is None:
        healthcheck = _as_mapping(state_map.get("last_data_source_healthcheck"))
        data_capability_packet = (
            state_map.get("command_center_data_capability_packet")
            or state_map.get("a_share_professional_data_capability")
            or healthcheck.get("data_capability")
            or healthcheck.get("tushare")
        )
    if facts_packet is None:
        facts_packet = facts_packet_service.build_command_center_facts_packet(
            state_map,
            target=target,
            name=_to_text(_as_mapping(position_profile).get("name") or state_map.get("current_stock_name")),
        )
    if radar_packet is None:
        radar_packet = radar_packet_service.build_command_center_radar_packet(state_map, live)
    etf_packet = etf_packet_service.build_command_center_etf_packet(state_map, live)
    discipline_packet = discipline_packet_service.build_command_center_discipline_packet(
        state_map,
        live_packet=live,
        target=target,
    )
    refresh = _as_mapping(refresh_summary or state_map.get("command_center_refresh_summary"))
    timestamp = _to_text(
        refresh.get("finished_at")
        or refresh.get("updated_at")
        or decision.get("updated_at")
        or strategy.get("updated_at")
        or live.get("updated_at")
        or live.get("generated_at")
        or _now_iso(now)
    )
    errors = _extract_errors(live, refresh, decision, strategy)
    coverage = _packet_data_coverage(live, decision, strategy)
    deepseek_called = any(bool(_as_mapping(packet).get("deepseek_called")) for packet in (live, decision, strategy))
    snapshot = {
        "status": "ready",
        "is_empty": False,
        "timestamp": timestamp,
        "source": SNAPSHOT_SOURCE,
        "decision_packet": decision,
        "strategy_packet": strategy,
        "today_action": build_today_action(decision),
        "holding_action": build_holding_action(target=target, position_profile=position_profile, strategy_packet=strategy, state=state_map),
        "next_ticket_candidates": extract_next_ticket_candidates({"command_center_radar_packet": radar_packet}, live),
        "radar_packet": radar_packet_service.build_command_center_radar_packet(
            {"command_center_radar_packet": radar_packet},
            live_packet=live,
        ),
        "etf_packet": etf_packet,
        "discipline_packet": discipline_packet,
        "margin_etf_summary": build_margin_etf_summary(state_map, live, etf_packet=etf_packet),
        "risk_alerts": build_risk_alerts(decision, strategy, coverage, errors),
        "data_coverage": coverage,
        "data_freshness": build_data_freshness(timestamp, errors, deepseek_called=deepseek_called),
        "data_capability": build_data_capability_snapshot(data_capability_packet),
        "facts_packet": facts_packet_service.build_command_center_facts_packet(
            {"command_center_facts_packet": facts_packet},
            target=target,
        ),
        "errors": errors,
        "deepseek_called": deepseek_called,
        "safety_line": "本系统不自动交易，不保证收益；DeepSeek 只解释当前结构化结果。",
    }
    has_payload = bool(decision or strategy or snapshot["next_ticket_candidates"] or snapshot["margin_etf_summary"]["recommended_etfs"])
    if not has_payload:
        empty = _empty_snapshot()
        empty["timestamp"] = timestamp
        empty["holding_action"] = snapshot["holding_action"]
        empty["data_coverage"] = coverage
        empty["risk_alerts"] = build_risk_alerts(decision, strategy, coverage, errors)
        empty["data_freshness"] = build_data_freshness("", errors, deepseek_called=deepseek_called)
        empty["data_capability"] = snapshot["data_capability"]
        empty["facts_packet"] = snapshot["facts_packet"]
        empty["radar_packet"] = snapshot["radar_packet"]
        empty["etf_packet"] = snapshot["etf_packet"]
        empty["discipline_packet"] = snapshot["discipline_packet"]
        empty["errors"] = errors
        return empty
    return sanitize_snapshot_payload(snapshot)


def has_action_snapshot_data(snapshot: Any) -> bool:
    payload = _as_mapping(snapshot)
    if not payload or payload.get("is_empty"):
        return False
    return bool(
        _as_mapping(payload.get("decision_packet"))
        or _as_mapping(payload.get("strategy_packet"))
        or _as_list(payload.get("next_ticket_candidates"))
        or _as_list(_as_mapping(payload.get("radar_packet")).get("top_candidates"))
        or _as_list(_as_mapping(payload.get("etf_packet")).get("recommended_etfs"))
        or _as_mapping(payload.get("discipline_packet")).get("data_status") == "ready"
        or _as_list(_as_mapping(payload.get("margin_etf_summary")).get("recommended_etfs"))
        or _as_list(_as_mapping(payload.get("facts_packet")).get("items"))
    )


def choose_home_action_snapshot(primary: Any, fallback: Any) -> dict:
    primary_map = _as_mapping(primary)
    fallback_map = _as_mapping(fallback)
    if has_action_snapshot_data(primary_map):
        return primary_map
    if has_action_snapshot_data(fallback_map):
        return fallback_map
    return primary_map or fallback_map or _empty_snapshot()


def update_home_action_snapshot(
    state: Any,
    target: str = "",
    position_profile: Any = None,
    live_packet: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    refresh_summary: Any = None,
    data_capability_packet: Any = None,
    facts_packet: Any = None,
    radar_packet: Any = None,
    path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> dict:
    snapshot = build_home_action_snapshot(
        state,
        target=target,
        position_profile=position_profile,
        live_packet=live_packet,
        decision_packet=decision_packet,
        strategy_packet=strategy_packet,
        refresh_summary=refresh_summary,
        data_capability_packet=data_capability_packet,
        facts_packet=facts_packet,
        radar_packet=radar_packet,
    )
    if isinstance(state, dict):
        state["command_center_home_snapshot"] = snapshot
    save_home_action_snapshot(snapshot, path=path, base_dir=base_dir)
    return snapshot
