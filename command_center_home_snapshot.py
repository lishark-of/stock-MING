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
import command_center_data_gap_report as data_gap_report_service
import command_center_market_packet as market_packet_service
import command_center_quant_packet as quant_packet_service
import command_center_chip_packet as chip_packet_service
import command_center_moneyflow_packet as moneyflow_packet_service
import command_center_dragon_tiger_packet as dragon_tiger_packet_service
import command_center_margin_packet as margin_packet_service
import command_center_limit_emotion_packet as limit_emotion_packet_service
import command_center_hard_risk_packet as hard_risk_packet_service
import command_center_market_profile_summary as market_profile_summary_service
import command_center_data_issue_explainer as data_issue_explainer_service
import command_center_data_capability_console as data_capability_console_service
import command_center_a_share_capability_matrix as a_share_capability_matrix_service
import command_center_legacy_a_share_debug_summary as legacy_a_share_debug_summary_service
import command_center_legacy_a_share_gate as legacy_a_share_gate_service
import market_data_capability as data_capability_service


CACHE_DIR_NAME = ".stock_ming_cache"
SNAPSHOT_FILENAME = "command_center_latest.json"
SNAPSHOT_SOURCE = "command_center_home_snapshot"
MAX_CANDIDATES = 3
MAX_ERRORS = 8
MAX_CAPABILITY_ITEMS = 8

A_SHARE_FACT_RECOVERY_SOURCES = (
    {
        "key": "moneyflow",
        "label": "个股资金流",
        "packet_key": "moneyflow_packet",
        "writes_packet": "command_center_moneyflow_packet",
        "source_fallback": "Tushare moneyflow",
    },
    {
        "key": "dragon_tiger",
        "label": "龙虎榜",
        "packet_key": "dragon_tiger_packet",
        "writes_packet": "command_center_dragon_tiger_packet",
        "source_fallback": "Tushare top_list/top_inst",
    },
    {
        "key": "margin",
        "label": "融资融券",
        "packet_key": "margin_packet",
        "writes_packet": "command_center_margin_packet",
        "source_fallback": "Tushare margin_detail",
    },
    {
        "key": "limit_emotion",
        "label": "涨跌停/情绪",
        "packet_key": "limit_emotion_packet",
        "writes_packet": "command_center_limit_emotion_packet",
        "source_fallback": "Tushare stk_limit/limit_list_d/limit_cpt_list",
    },
    {
        "key": "chip_radar",
        "label": "筹码/胜率",
        "packet_key": "chip_packet",
        "writes_packet": "command_center_chip_packet",
        "source_fallback": "Tushare cyq_perf/cyq_chips",
    },
)

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
    snapshot = {
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
        "quant_packet": quant_packet_service.build_command_center_quant_packet({}),
        "chip_packet": chip_packet_service.build_command_center_chip_packet({}),
        "moneyflow_packet": moneyflow_packet_service.build_command_center_moneyflow_packet({}),
        "dragon_tiger_packet": dragon_tiger_packet_service.build_command_center_dragon_tiger_packet({}),
        "margin_packet": margin_packet_service.build_command_center_margin_packet({}),
        "limit_emotion_packet": limit_emotion_packet_service.build_command_center_limit_emotion_packet({}),
        "hard_risk_packet": hard_risk_packet_service.build_command_center_hard_risk_packet({}),
        "market_profile_evidence": market_profile_summary_service.build_market_profile_evidence_strip(),
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
        "a_share_capability_matrix": a_share_capability_matrix_service.build_a_share_capability_matrix(),
        "facts_packet": facts_packet_service.build_command_center_facts_packet({}),
        "data_gap_report": data_gap_report_service.build_command_center_data_gap_report(),
        "data_issue_explainer": data_issue_explainer_service.build_data_issue_explainer_packet(),
        "data_capability_console": data_capability_console_service.build_data_capability_console_packet(),
        "a_share_user_data_diagnostic": legacy_a_share_debug_summary_service.build_user_data_diagnostic_view_model(),
        "data_recovery_actions": [],
        "legacy_a_share_fact_recovery_actions": [],
        "tool_recovery_actions": [],
        "data_recovery_center": build_home_data_recovery_center(),
        "market_packet": market_packet_service.build_command_center_market_packet({}),
        "errors": [],
        "empty_message": reason,
        "deepseek_called": False,
    }
    snapshot["a_share_fact_recovery_summary"] = build_a_share_fact_recovery_summary(snapshot)
    return snapshot


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
    snapshot["a_share_capability_matrix"] = a_share_capability_matrix_service.build_a_share_capability_matrix(
        snapshot.get("data_capability") or {},
        snapshot.get("facts_packet") or {},
    )
    snapshot["facts_packet"] = facts_packet_service.build_command_center_facts_packet(
        {"command_center_facts_packet": snapshot.get("facts_packet") or {}}
    )
    snapshot["data_gap_report"] = data_gap_report_service.build_command_center_data_gap_report(
        snapshot.get("data_capability") or {},
        snapshot.get("facts_packet") or {},
        errors=snapshot.get("errors") or [],
    )
    snapshot["data_issue_explainer"] = data_issue_explainer_service.build_data_issue_explainer_packet(
        snapshot.get("data_capability") or {},
        snapshot.get("data_gap_report") or {},
        errors=snapshot.get("errors") or [],
    )
    snapshot["data_capability_console"] = data_capability_console_service.build_data_capability_console_packet(
        snapshot.get("data_capability") or {},
        snapshot.get("data_gap_report") or {},
        data_issue_explainer=snapshot.get("data_issue_explainer") or {},
        errors=snapshot.get("errors") or [],
    )
    snapshot["a_share_user_data_diagnostic"] = (
        _as_mapping(snapshot.get("a_share_user_data_diagnostic"))
        or legacy_a_share_debug_summary_service.build_user_data_diagnostic_view_model()
    )
    snapshot["data_recovery_actions"] = build_data_recovery_actions_snapshot(snapshot.get("data_capability_console") or {})
    snapshot["market_packet"] = market_packet_service.build_command_center_market_packet(
        {"command_center_market_packet": snapshot.get("market_packet") or {}}
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
    snapshot["quant_packet"] = quant_packet_service.build_command_center_quant_packet(
        {"command_center_quant_packet": snapshot.get("quant_packet") or {}}
    )
    snapshot["chip_packet"] = chip_packet_service.build_command_center_chip_packet(
        {"command_center_chip_packet": snapshot.get("chip_packet") or {}}
    )
    snapshot["moneyflow_packet"] = moneyflow_packet_service.build_command_center_moneyflow_packet(
        {"command_center_moneyflow_packet": snapshot.get("moneyflow_packet") or {}}
    )
    snapshot["dragon_tiger_packet"] = dragon_tiger_packet_service.build_command_center_dragon_tiger_packet(
        {"command_center_dragon_tiger_packet": snapshot.get("dragon_tiger_packet") or {}}
    )
    snapshot["margin_packet"] = margin_packet_service.build_command_center_margin_packet(
        {"command_center_margin_packet": snapshot.get("margin_packet") or {}}
    )
    snapshot["limit_emotion_packet"] = limit_emotion_packet_service.build_command_center_limit_emotion_packet(
        {"command_center_limit_emotion_packet": snapshot.get("limit_emotion_packet") or {}}
    )
    snapshot["hard_risk_packet"] = hard_risk_packet_service.build_command_center_hard_risk_packet(
        {"command_center_hard_risk_packet": snapshot.get("hard_risk_packet") or {}}
    )
    snapshot["a_share_fact_recovery_summary"] = build_a_share_fact_recovery_summary(snapshot)
    snapshot["legacy_a_share_fact_recovery_actions"] = build_legacy_a_share_fact_recovery_actions_snapshot(snapshot)
    snapshot["tool_recovery_actions"] = build_tool_recovery_actions_snapshot(snapshot)
    snapshot["data_recovery_center"] = build_home_data_recovery_center(snapshot)
    snapshot["risk_alerts"] = attach_hard_risk_risk_alerts(
        snapshot.get("risk_alerts") or {},
        snapshot.get("hard_risk_packet") or {},
    )
    existing_market_profile = _as_mapping(snapshot.get("market_profile_evidence"))
    normalized_market_profile = market_profile_summary_service.build_market_profile_evidence_strip(
        market_type=existing_market_profile.get("market_type"),
        ticker=existing_market_profile.get("ticker"),
        name=existing_market_profile.get("name"),
        home_snapshot=snapshot,
    )
    if existing_market_profile:
        normalized_market_profile.update(existing_market_profile)
        normalized_market_profile["deepseek_called"] = False
    snapshot["market_profile_evidence"] = normalized_market_profile
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


def build_data_recovery_actions_snapshot(data_capability_console: Any = None, limit: int = MAX_CAPABILITY_ITEMS) -> list[dict]:
    console = _as_mapping(data_capability_console)
    actions = []
    for raw in _as_list(console.get("recovery_actions")):
        item = _as_mapping(raw)
        if not item:
            continue
        label = _to_text(item.get("label"), "数据能力")
        actions.append(
            {
                "provider": _to_text(item.get("provider"), "数据源"),
                "label": label,
                "api": _to_text(item.get("api")),
                "state": _to_text(item.get("state"), "unknown"),
                "status_label": _to_text(item.get("status_label"), "待验证"),
                "priority": int(_to_number(item.get("priority")) or 3),
                "reason": _to_text(item.get("reason") or item.get("action_hint"), f"{label}仍待验证。"),
                "diagnostic_answer": _to_text(item.get("diagnostic_answer") or item.get("meaning"), f"{label}仍需核对接口状态、日期和覆盖范围。"),
                "action_label": _to_text(item.get("action_label"), f"手动检查{label}"),
                "toolbox_entry": _to_text(item.get("toolbox_entry"), "高级工具箱 / 数据源体检"),
                "writes_packet": _to_text(item.get("writes_packet"), "command_center_data_capability_packet"),
                "refresh_policy": _to_text(item.get("refresh_policy"), "button_gated"),
                "deepseek_called": False,
            }
        )
        if len(actions) >= max(1, int(limit or MAX_CAPABILITY_ITEMS)):
            break
    return actions


def _a_share_fact_recovery_state(packet: Mapping[str, Any], writes_packet: str = "") -> str:
    explicit = _to_text(packet.get("recovery_state")).lower()
    if explicit in {"recovered", "blocked", "waiting"}:
        return explicit
    return _tool_packet_recovery_state(packet, writes_packet)


def _a_share_fact_next_action(label: str, recovery_state: str, writes_packet: str, action_label: str) -> str:
    if recovery_state == "recovered":
        return f"{label}已写回 {writes_packet}；执行前复核交易日、来源和风险纪律。"
    if recovery_state == "blocked":
        return f"{label}仍受限；点击“{action_label}”后只检测这一项，结果回流 {writes_packet}。"
    return f"{label}待验证；需要时点击“{action_label}”，页面打开不会自动请求 Tushare。"


def _a_share_fact_diagnostic_text(label: str, recovery_state: str, status_label: str) -> str:
    if recovery_state == "recovered":
        return f"{label}已有可读 packet，可进入综合中心证据链。"
    if recovery_state == "blocked":
        return f"{label}当前为{status_label}，不能把缺失数据当成利好或无风险。"
    return f"{label}尚未形成当日可验证事实；保持空态或缓存，等待手动检测。"


def _a_share_fact_summary_item(config: Mapping[str, Any], packet: Any = None) -> dict:
    payload = _as_mapping(packet)
    writes_packet = _to_text(config.get("writes_packet"), "command_center_packet")
    recovery_state = _a_share_fact_recovery_state(payload, writes_packet)
    status = _to_text(payload.get("status"), "waiting")
    data_status = _to_text(payload.get("data_status") or payload.get("cache_state"), "missing")
    capability_state = _to_text(payload.get("capability_state") or payload.get("state"), "requires_manual_refresh")
    status_label = _to_text(payload.get("status_label") or payload.get("capability_label") or status, "待验证")
    updated_at = _to_text(
        payload.get("updated_at")
        or payload.get("checked_at")
        or payload.get("generated_at")
        or payload.get("trade_date")
        or payload.get("latest_date"),
        "暂无",
    )
    source = _to_text(payload.get("source") or payload.get("source_key"), _to_text(config.get("source_fallback"), "本地 packet"))
    if recovery_state == "recovered":
        tone = "ready"
        readable_state = "已回流"
    elif recovery_state == "blocked":
        tone = "failed"
        readable_state = "仍受限"
    else:
        tone = "missing"
        readable_state = "待验证"
    manual_config = TOOL_RECOVERY_MANUAL_CHECKS.get(writes_packet, {})
    action_label = _to_text(manual_config.get("button_label"), f"手动检测{_to_text(config.get('label'), 'A股事实')}")
    label = _to_text(config.get("label"), "A股事实")
    return {
        "key": _to_text(config.get("key")),
        "label": label,
        "packet_key": _to_text(config.get("packet_key")),
        "writes_packet": writes_packet,
        "recovery_state": recovery_state,
        "readable_state": readable_state,
        "tone": tone,
        "status": status,
        "data_status": data_status,
        "capability_state": capability_state,
        "status_label": status_label,
        "updated_at": updated_at,
        "source": source,
        "action_label": action_label if recovery_state != "recovered" else "查看回流结果",
        "next_action": _a_share_fact_next_action(label, recovery_state, writes_packet, action_label),
        "diagnostic_answer": _a_share_fact_diagnostic_text(label, recovery_state, status_label),
        "packet_status_text": f"{readable_state}｜{status_label}｜{writes_packet}",
        "deepseek_called": False,
    }


def build_a_share_fact_recovery_summary(snapshot: Any = None) -> dict:
    payload = _as_mapping(snapshot)
    items = [
        _a_share_fact_summary_item(config, payload.get(config["packet_key"]) or payload.get(config["writes_packet"]))
        for config in A_SHARE_FACT_RECOVERY_SOURCES
    ]
    recovered = [item for item in items if item["recovery_state"] == "recovered"]
    blocked = [item for item in items if item["recovery_state"] == "blocked"]
    waiting = [item for item in items if item["recovery_state"] == "waiting"]
    total = len(items)
    if len(recovered) == total:
        tone = "ready"
        next_action = "五类 A股事实已回流；执行前仍需复核交易日、来源和风险纪律。"
    elif blocked:
        tone = "failed"
        first = blocked[0]
        next_action = f"优先处理 {first['label']}：检查权限、积分、交易日或进入数据恢复中心手动恢复。"
    elif recovered:
        tone = "stale"
        next_action = "继续手动补齐待验证事实；不要把缺失数据当成无风险。"
    else:
        tone = "missing"
        next_action = "点击刷新今日基础数据或进入数据恢复中心；页面打开不会自动请求 Tushare。"
    summary = f"A股事实 {total} 项：已回流 {len(recovered)}｜仍受限 {len(blocked)}｜待验证 {len(waiting)}"
    return {
        "title": "A股事实回流",
        "summary": summary,
        "tone": tone,
        "recovered_count": len(recovered),
        "blocked_count": len(blocked),
        "waiting_count": len(waiting),
        "total_count": total,
        "items": items,
        "next_action": next_action,
        "safe_mode_text": "这里只汇总本地 packet 状态；不会自动调用 Tushare、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }


TOOL_RECOVERY_CONFIG = {
    "radar_packet": {
        "key": "next_ticket_radar",
        "label": "下一票雷达",
        "action_label": "手动运行下一票雷达",
        "toolbox_entry": "高级工具箱 / 下一票雷达",
        "legacy_tab": "下一票雷达",
        "writes_packet": "command_center_radar_packet",
        "reason": "候选池来自缓存或手动扫描；缺失时不能把空候选当作无机会。",
    },
    "etf_packet": {
        "key": "margin_etf",
        "label": "融资 ETF",
        "action_label": "手动刷新 ETF 配置/日线",
        "toolbox_entry": "高级工具箱 / 融资 ETF",
        "legacy_tab": "融资 ETF",
        "writes_packet": "command_center_etf_packet",
        "reason": "ETF 配置和赛道强弱来自本地快照；缺失时不能放大融资或追高。",
    },
    "discipline_packet": {
        "key": "discipline_backtest",
        "label": "交易纪律/回测",
        "action_label": "手动运行回测或读取纪律缓存",
        "toolbox_entry": "高级工具箱 / 交易纪律实验室",
        "legacy_tab": "交易纪律实验室",
        "writes_packet": "command_center_discipline_packet",
        "reason": "回测必须按钮触发；缺少纪律缓存时只能观察或降风险。",
    },
    "quant_packet": {
        "key": "quant_projection",
        "label": "量化推演",
        "action_label": "手动生成量化推演",
        "toolbox_entry": "高级工具箱 / 量化推演",
        "legacy_tab": "量化推演",
        "writes_packet": "command_center_quant_packet",
        "reason": "完整量化推演和回测必须手动触发；缺失时不能把评分写成事实。",
    },
}


def _tool_recovery_priority(packet: Mapping[str, Any]) -> int:
    status = _to_text(packet.get("status"), "waiting")
    data_status = _to_text(packet.get("data_status") or packet.get("cache_state"), "missing")
    if status == "failed":
        return 1
    if data_status == "missing" or status in {"waiting", "missing"}:
        return 2
    if data_status in {"cached", "stale"} or status == "partial":
        return 3
    return 4


def _tool_needs_recovery(packet: Mapping[str, Any]) -> bool:
    status = _to_text(packet.get("status"), "waiting")
    data_status = _to_text(packet.get("data_status") or packet.get("cache_state"), "missing")
    if status == "failed":
        return True
    if data_status in {"missing", "cached", "stale"}:
        return True
    return status in {"waiting", "missing", "partial"}


def build_tool_recovery_actions_snapshot(snapshot: Any = None, limit: int = MAX_CAPABILITY_ITEMS) -> list[dict]:
    payload = _as_mapping(snapshot)
    actions = []
    for packet_key, config in TOOL_RECOVERY_CONFIG.items():
        packet = _as_mapping(payload.get(packet_key))
        if not packet or not _tool_needs_recovery(packet):
            continue
        label = config["label"]
        legacy_tab = config["legacy_tab"]
        actions.append(
            {
                "key": config["key"],
                "label": label,
                "status": _to_text(packet.get("status"), "waiting"),
                "data_status": _to_text(packet.get("data_status") or packet.get("cache_state"), "missing"),
                "priority": _tool_recovery_priority(packet),
                "reason": _to_text(packet.get("manual_required_text") or packet.get("backtest_required_text") or config["reason"]),
                "action_label": config["action_label"],
                "toolbox_entry": config["toolbox_entry"],
                "workspace_target": "高级工具箱（旧版保留）",
                "workspace_state_key": "workspace_mode_v2",
                "legacy_tab": legacy_tab,
                "legacy_tab_state_key": "legacy_workspace_selected_tab",
                "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}",
                "writes_packet": config["writes_packet"],
                "refresh_policy": "button_gated",
                "deepseek_called": False,
            }
        )
    actions = sorted(actions, key=lambda item: (item["priority"], item["label"]))
    return actions[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]


def _legacy_a_share_fact_priority(action: Mapping[str, Any]) -> int:
    state = _to_text(action.get("state") or action.get("status"), "waiting")
    if state in {"failed", "error", "permission_denied", "权限不足", "失败"}:
        return 1
    if state in {"cached", "stale", "partial", "using_cache", "使用缓存"}:
        return 2
    return 3


def _legacy_a_share_fact_legacy_tab(key: Any = "", writes_packet: Any = "") -> str:
    text = _to_text(key) or _to_text(writes_packet)
    return {
        "dragon_tiger": "下一票雷达",
        "command_center_dragon_tiger_packet": "下一票雷达",
        "margin": "融资 ETF",
        "command_center_margin_packet": "融资 ETF",
        "moneyflow": "今日关注池",
        "command_center_moneyflow_packet": "今日关注池",
        "limit_emotion": "数据源体检",
        "command_center_limit_emotion_packet": "数据源体检",
        "chip_radar": "量化推演",
        "command_center_chip_packet": "量化推演",
    }.get(text, "今日关注池")


def _legacy_a_share_fact_recovery_actions_from_view(view_model: Any = None) -> list[dict]:
    payload = _as_mapping(view_model)
    entries = _as_list(payload.get("cards")) + _as_list(payload.get("sections"))
    actions = []
    for entry in entries:
        item = _as_mapping(entry)
        action = _as_mapping(item.get("recovery_action"))
        if not action or _to_text(action.get("refresh_policy")) == "not_needed":
            continue
        key = _to_text(action.get("key") or item.get("key"))
        writes_packet = _to_text(action.get("writes_packet"), "command_center_packet")
        toolbox_entry = _to_text(action.get("toolbox_entry"), "高级工具箱")
        legacy_tab = _legacy_a_share_fact_legacy_tab(key, writes_packet)
        actions.append(
            {
                "key": f"legacy_a_share_fact:{key or writes_packet}",
                "label": _to_text(action.get("label") or item.get("label") or item.get("title"), "A股事实卡"),
                "status": _to_text(action.get("state") or item.get("status"), "waiting"),
                "status_label": _to_text(action.get("status_label") or item.get("status"), "待验证"),
                "priority": _legacy_a_share_fact_priority(action),
                "reason": _to_text(action.get("reason") or item.get("message"), "旧版 A股事实卡仍待手动恢复。"),
                "action_label": _to_text(action.get("action_label"), "手动刷新 A股事实卡"),
                "toolbox_entry": toolbox_entry,
                "workspace_target": "高级工具箱（旧版保留）",
                "workspace_state_key": "workspace_mode_v2",
                "legacy_tab": legacy_tab,
                "legacy_tab_state_key": "legacy_workspace_selected_tab",
                "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
                "writes_packet": writes_packet,
                "refresh_policy": "button_gated",
                "source_label": "旧版 A股事实卡",
                "deepseek_called": False,
            }
        )
    return actions


def build_legacy_a_share_fact_recovery_actions_snapshot(
    snapshot: Any = None,
    limit: int = MAX_CAPABILITY_ITEMS,
) -> list[dict]:
    payload = _as_mapping(snapshot)
    primary_view = legacy_a_share_gate_service.build_legacy_a_share_primary_fact_cards(
        dragon_tiger_packet=payload.get("dragon_tiger_packet") or payload.get("command_center_dragon_tiger_packet"),
        margin_packet=payload.get("margin_packet") or payload.get("command_center_margin_packet"),
        moneyflow_packet=payload.get("moneyflow_packet") or payload.get("command_center_moneyflow_packet"),
    )
    secondary_view = legacy_a_share_gate_service.build_legacy_a_share_secondary_fact_sections(
        limit_emotion_packet=payload.get("limit_emotion_packet") or payload.get("command_center_limit_emotion_packet"),
        chip_packet=payload.get("chip_packet") or payload.get("command_center_chip_packet"),
    )
    actions = (
        _legacy_a_share_fact_recovery_actions_from_view(primary_view)
        + _legacy_a_share_fact_recovery_actions_from_view(secondary_view)
    )
    deduped = []
    seen = set()
    for action in sorted(actions, key=lambda item: (item["priority"], item["label"])):
        writes_packet = action.get("writes_packet")
        if writes_packet in seen:
            continue
        seen.add(writes_packet)
        deduped.append(action)
    return deduped[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]


def _normalize_recovery_center_action(
    action: Any = None,
    source_type: str = "",
    source_label: str = "",
    default_priority: int = 3,
) -> dict:
    item = _as_mapping(action)
    if not item:
        return {}
    label = _to_text(item.get("label"), "数据能力")
    writes_packet = _to_text(item.get("writes_packet"), "command_center_packet")
    status = _to_text(item.get("status") or item.get("state") or item.get("data_status"), "waiting")
    return {
        "key": _to_text(item.get("key") or item.get("api") or writes_packet or label),
        "label": label,
        "source_type": _to_text(source_type, "recovery"),
        "source_label": _to_text(source_label, "恢复队列"),
        "status": status,
        "status_label": _to_text(item.get("status_label") or item.get("capability_label"), "待验证"),
        "priority": int(_to_number(item.get("priority")) or default_priority),
        "reason": _to_text(item.get("reason") or item.get("action_hint"), f"{label}仍待验证。"),
        "diagnostic_answer": _to_text(item.get("diagnostic_answer") or item.get("meaning"), f"{label}仍需核对接口状态、日期和覆盖范围。"),
        "action_label": _to_text(item.get("action_label"), f"手动恢复{label}"),
        "toolbox_entry": _to_text(item.get("toolbox_entry") or item.get("advanced_entry"), "高级工具箱"),
        "workspace_target": _to_text(item.get("workspace_target"), "高级工具箱（旧版保留）"),
        "workspace_state_key": _to_text(item.get("workspace_state_key"), "workspace_mode_v2"),
        "legacy_tab_state_key": _to_text(item.get("legacy_tab_state_key"), "legacy_workspace_selected_tab"),
        "navigation_label": _to_text(item.get("navigation_label"), "从首页恢复队列进入对应手动工具。"),
        "legacy_tab": _to_text(item.get("legacy_tab")),
        "writes_packet": writes_packet,
        "refresh_policy": _to_text(item.get("refresh_policy"), "button_gated"),
        "deepseek_called": False,
    }


def build_home_data_recovery_center(snapshot: Any = None, limit: int = MAX_CAPABILITY_ITEMS) -> dict:
    payload = _as_mapping(snapshot)
    data_actions = _as_list(payload.get("data_recovery_actions"))
    legacy_fact_actions = _as_list(payload.get("legacy_a_share_fact_recovery_actions"))
    a_share_actions = _as_list(_as_mapping(payload.get("a_share_user_data_diagnostic")).get("recovery_actions"))
    tool_actions = _as_list(payload.get("tool_recovery_actions"))
    action_sources = [
        ("data_source", "数据源能力", data_actions, 1),
        ("a_share_fact", "旧版 A股事实卡", legacy_fact_actions, 2),
        ("a_share", "A股数据能力", a_share_actions, 3),
        ("legacy_tool", "旧工具能力", tool_actions, 3),
    ]
    seen = set()
    actions = []
    groups = []
    for source_type, source_label, source_actions, default_priority in action_sources:
        group_items = []
        for raw in source_actions:
            item = _normalize_recovery_center_action(raw, source_type, source_label, default_priority)
            if not item or item.get("refresh_policy") == "not_needed":
                continue
            dedupe_key = item.get("writes_packet") or f"{source_type}:{item.get('key')}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            group_items.append(item)
            actions.append(item)
        groups.append(
            {
                "key": source_type,
                "label": source_label,
                "count": len(group_items),
                "items": group_items,
            }
        )
    actions = sorted(actions, key=lambda item: (item["priority"], item["source_label"], item["label"]))
    actions = actions[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]
    if not actions:
        tone = "ready"
        headline = "恢复队列为空"
        summary = "当前没有需要恢复的数据源、A股诊断项或旧工具 packet。"
        next_action = "继续查看交易快照；如需更新，使用刷新今日基础数据按钮。"
    else:
        has_blocker = any(str(item.get("status") or "") in {"permission_denied", "failed", "error"} for item in actions)
        tone = "failed" if has_blocker else "stale"
        headline = f"待恢复 {len(actions)} 项数据/工具能力"
        first = actions[0]
        summary = f"优先处理 {first['label']}：{first['action_label']}，回流 {first['writes_packet']}。"
        next_action = "按队列手动恢复；页面打开不会自动请求 DeepSeek、回测、全市场扫描或批量数据接口。"
    return {
        "title": "数据恢复中心",
        "tone": tone,
        "headline": headline,
        "summary": summary,
        "next_action": next_action,
        "actions": actions,
        "groups": groups,
        "action_count": len(actions),
        "safe_mode_text": "这里只整理恢复队列；所有数据请求仍由按钮触发，DeepSeek 不参与恢复动作。",
        "deepseek_called": False,
    }


def build_tool_recovery_navigation_state(action: Any = None) -> dict:
    item = _as_mapping(action)
    workspace_state_key = _to_text(item.get("workspace_state_key"), "workspace_mode_v2")
    legacy_tab_state_key = _to_text(item.get("legacy_tab_state_key"), "legacy_workspace_selected_tab")
    workspace_target = _to_text(item.get("workspace_target"), "高级工具箱（旧版保留）")
    legacy_tab = _to_text(item.get("legacy_tab"))
    if not legacy_tab:
        return {}
    return {
        workspace_state_key: workspace_target,
        legacy_tab_state_key: legacy_tab,
        "command_center_last_tool_recovery_key": _to_text(item.get("key")),
        "command_center_last_tool_recovery_label": _to_text(item.get("label"), legacy_tab),
        "command_center_last_tool_recovery_writes_packet": _to_text(item.get("writes_packet")),
        "command_center_last_tool_recovery_policy": "navigation_only",
    }


def build_tool_recovery_context_notice(state: Any = None, selected_tab: Any = "") -> dict:
    state_map = _as_mapping(state)
    if _to_text(state_map.get("command_center_last_tool_recovery_policy")) != "navigation_only":
        return {}
    label = _to_text(state_map.get("command_center_last_tool_recovery_label"), "旧工具能力")
    writes_packet = _to_text(state_map.get("command_center_last_tool_recovery_writes_packet"), "command_center_packet")
    tab = _to_text(selected_tab, _to_text(state_map.get("legacy_workspace_selected_tab"), "高级工具"))
    return {
        "status": "ready",
        "title": "来自首页恢复队列",
        "label": label,
        "selected_tab": tab,
        "writes_packet": writes_packet,
        "message": f"你是从首页恢复队列进入“{tab}”；请在本模块手动点击对应按钮恢复 {writes_packet}。",
        "action_hint": "这里只是导航提示，不会自动运行扫描、回测、DeepSeek 或重型数据接口。",
        "safety_text": "恢复成功后的结构化结果会回流到 Home Action Snapshot。",
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


TOOL_RECOVERY_MANUAL_CHECKS = {
    "command_center_moneyflow_packet": {
        "check_key": "moneyflow",
        "label": "个股资金流",
        "button_label": "手动检测个股资金流",
        "status_label": "正在手动检测个股资金流...",
        "result_label": "资金流",
    },
    "command_center_dragon_tiger_packet": {
        "check_key": "dragon_tiger",
        "label": "龙虎榜",
        "button_label": "手动检测龙虎榜",
        "status_label": "正在手动检测龙虎榜...",
        "result_label": "龙虎榜",
    },
    "command_center_margin_packet": {
        "check_key": "margin",
        "label": "融资融券",
        "button_label": "手动检测融资融券",
        "status_label": "正在手动检测融资融券权限...",
        "result_label": "融资融券",
    },
    "command_center_limit_emotion_packet": {
        "check_key": "limit_emotion",
        "label": "涨跌停/情绪",
        "button_label": "手动检测涨跌停/情绪",
        "status_label": "正在手动检测涨跌停/情绪权限...",
        "result_label": "涨跌停/情绪",
    },
    "command_center_chip_packet": {
        "check_key": "chip_radar",
        "label": "筹码/胜率",
        "button_label": "手动检测筹码/胜率",
        "status_label": "正在手动检测筹码/胜率...",
        "result_label": "筹码/胜率",
    },
    "command_center_hard_risk_packet": {
        "check_key": "hard_risk",
        "label": "公告/硬风险",
        "button_label": "手动检测公告/硬风险",
        "status_label": "正在手动检测公告/硬风险...",
        "result_label": "公告/硬风险",
    },
}


def build_tool_recovery_manual_check_hint(state: Any = None, selected_tab: Any = "") -> dict:
    context = build_tool_recovery_context_notice(state, selected_tab=selected_tab)
    if not context:
        return {}
    writes_packet = context["writes_packet"]
    config = TOOL_RECOVERY_MANUAL_CHECKS.get(writes_packet)
    if not config:
        return {
            "available": False,
            "label": context["label"],
            "selected_tab": context["selected_tab"],
            "writes_packet": writes_packet,
            "message": f"{writes_packet} 还没有绑定单项检测按钮；请在当前高级工具模块手动查找对应刷新入口。",
            "external_call_policy": "not_triggered",
            "deepseek_called": False,
        }
    return {
        "available": True,
        "label": config["label"],
        "selected_tab": context["selected_tab"],
        "writes_packet": writes_packet,
        "check_key": config["check_key"],
        "button_label": config["button_label"],
        "status_label": config["status_label"],
        "result_label": config["result_label"],
        "help_text": f"只检测 {config['label']} 并回流 {writes_packet}；不自动运行 DeepSeek、回测、全市场扫描或批量刷新。",
        "external_call_policy": "button_gated",
        "deepseek_called": False,
    }


def _tool_packet_has_payload(packet: Mapping[str, Any], writes_packet: str = "") -> bool:
    if not packet:
        return False
    status = _to_text(packet.get("status")).lower()
    data_status = _to_text(packet.get("data_status") or packet.get("cache_state")).lower()
    if status in {"ready", "completed", "ok", "success"} or data_status in {"ready", "cached"}:
        return True
    payload_keys = {
        "command_center_radar_packet": ("top_candidates", "display_count", "total_count"),
        "command_center_etf_packet": ("recommended_etfs", "today_main_direction"),
        "command_center_discipline_packet": ("metric_items", "evidence_items", "backtest_status"),
        "command_center_quant_packet": ("score", "evidence_items", "summary"),
    }.get(writes_packet, ("summary", "items", "updated_at"))
    for key in payload_keys:
        value = packet.get(key)
        if isinstance(value, (list, tuple)) and value:
            return True
        if isinstance(value, Mapping) and value:
            return True
        if _to_text(value):
            return True
    return False


def _tool_packet_recovery_state(packet: Mapping[str, Any], writes_packet: str = "") -> str:
    if not packet:
        return "waiting"
    status = _to_text(packet.get("status")).lower()
    data_status = _to_text(packet.get("data_status") or packet.get("cache_state")).lower()
    blocked_states = {
        "failed",
        "error",
        "failure",
        "permission_denied",
        "disabled_this_session",
        "network_failed",
        "not_configured",
        "权限不足",
        "本会话跳过",
        "失败",
    }
    ready_states = {"ready", "completed", "ok", "success", "available", "cached", "using_cache", "今日已刷新", "使用缓存"}
    if status in blocked_states or data_status in blocked_states:
        return "blocked"
    if status in ready_states or data_status in ready_states:
        return "recovered"
    if _tool_packet_has_payload(packet, writes_packet):
        return "recovered"
    return "waiting"


def build_tool_recovery_result_notice(state: Any = None, selected_tab: Any = "") -> dict:
    context = build_tool_recovery_context_notice(state, selected_tab=selected_tab)
    if not context:
        return {}
    state_map = _as_mapping(state)
    writes_packet = context["writes_packet"]
    packet = _as_mapping(state_map.get(writes_packet))
    recovery_state = _tool_packet_recovery_state(packet, writes_packet)
    updated_at = _to_text(packet.get("updated_at") or packet.get("generated_at") or packet.get("checked_at"))
    source = _to_text(packet.get("source"), context["selected_tab"])
    if recovery_state == "recovered":
        status = "recovered"
        title = "恢复结果已回流"
        message = f"{context['label']} 已写入 {writes_packet}；首页快照会读取该结构化结果。"
        next_action = "返回综合推演中心 2.0 后查看 Home Action Snapshot。"
    elif recovery_state == "blocked":
        status = "blocked"
        title = "恢复结果仍受限"
        reason = _to_text(packet.get("risk_note") or packet.get("message") or packet.get("summary"), "接口权限、积分、网络或交易日状态仍待处理。")
        message = f"{context['label']} 仍未形成可用回流：{reason}"
        next_action = "先检查权限/积分/交易日/网络；不要把缺失数据当作利好或安全信号。"
    else:
        status = "waiting"
        title = "恢复结果待验证"
        message = f"尚未检测到 {writes_packet} 的可读结果；请在“{context['selected_tab']}”中手动运行对应按钮。"
        next_action = "运行完成后不要刷新外部重接口，先确认本模块是否显示缓存/已刷新状态。"
    return {
        "status": status,
        "title": title,
        "label": context["label"],
        "selected_tab": context["selected_tab"],
        "writes_packet": writes_packet,
        "message": message,
        "next_action": next_action,
        "updated_at": updated_at,
        "source": source,
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def build_a_share_diagnostic_recovery_result_notice(state: Any = None) -> dict:
    state_map = _as_mapping(state)
    result = _as_mapping(state_map.get("command_center_last_a_share_diagnostic_recovery_result"))
    if not result:
        return {}
    label = _to_text(result.get("label"), "A股数据")
    writes_packet = _to_text(result.get("writes_packet"), "command_center_facts_packet")
    capability_state = _to_text(result.get("capability_state") or result.get("state"), "unknown")
    status_label = _to_text(result.get("status_label") or result.get("status"), "待验证")
    message = _to_text(result.get("message") or result.get("action_hint") or result.get("error"), "已完成手动检测。")
    updated_at = _to_text(result.get("checked_at") or result.get("updated_at"))
    packet = _as_mapping(state_map.get(writes_packet))
    has_packet_payload = _tool_packet_has_payload(packet, writes_packet)
    if capability_state == "available" or has_packet_payload:
        status = "recovered"
        tone = "ready"
        title = "A股数据恢复结果已回流"
        next_action = "继续查看 Home Action Snapshot；执行前仍需复核日期、来源和仓位纪律。"
    elif capability_state in {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}:
        status = "blocked"
        tone = "failed"
        title = "A股数据恢复仍受限"
        next_action = "保持安全空态或缓存观察；权限、网络或配置恢复后再手动检测。"
    else:
        status = "waiting"
        tone = "stale"
        title = "A股数据恢复待验证"
        next_action = "等待交易日数据发布或稍后再次手动检测；不要把缺失数据当成无风险。"
    return {
        "status": status,
        "tone": tone,
        "title": title,
        "label": label,
        "capability_state": capability_state,
        "status_label": status_label,
        "message": f"{label}：{status_label}｜{message}",
        "next_action": next_action,
        "writes_packet": writes_packet,
        "updated_at": updated_at,
        "source": _to_text(result.get("source") or result.get("api_hint"), "A股手动检测"),
        "deepseek_called": False,
        "external_call_policy": "button_gated",
    }


def resolve_data_capability_packet(state: Any = None) -> dict:
    state_map = _as_mapping(state)
    healthcheck = _as_mapping(state_map.get("last_data_source_healthcheck"))
    command_packet = _as_mapping(state_map.get("command_center_data_capability_packet"))
    a_share_packet = _as_mapping(state_map.get("a_share_professional_data_capability"))
    professional_facts = _as_mapping(state_map.get("a_share_professional_facts"))
    facts_capability = _as_mapping(professional_facts.get("data_capability"))
    health_data_capability = _as_mapping(healthcheck.get("data_capability"))
    if health_data_capability and not a_share_packet:
        return health_data_capability
    if a_share_packet or healthcheck:
        unified = data_capability_service.build_unified_provider_capability_packet(
            health_result=healthcheck,
            a_share_packet=a_share_packet or facts_capability,
            include_manual_providers=bool(healthcheck or a_share_packet or facts_capability or command_packet),
        )
        if unified.get("items"):
            return unified
    for explicit in (
        command_packet,
        health_data_capability,
        facts_capability,
        _as_mapping(healthcheck.get("tushare")),
    ):
        if explicit:
            return explicit
    if professional_facts:
        return data_capability_service.build_a_share_professional_capability_packet(
            professional_facts,
            checked_at=professional_facts.get("updated_at") or "",
        )
    return {}


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


def _dedupe_text_items(values: Any, limit: int = MAX_ERRORS) -> list[str]:
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


def attach_data_capability_risk_alerts(risk_alerts: Any = None, data_capability_console: Any = None) -> dict:
    alerts = _as_mapping(risk_alerts)
    console = _as_mapping(data_capability_console)
    blockers = [_to_text(item) for item in _as_list(console.get("decision_blockers"))]
    blockers = [item for item in blockers if item]
    if not blockers:
        return alerts
    data_gaps = [_to_text(item) for item in _as_list(alerts.get("data_gaps"))]
    reduce_conditions = [_to_text(item) for item in _as_list(alerts.get("reduce_conditions"))]
    safe_mode = _to_text(console.get("safe_mode_text"))
    data_gaps.extend(blockers[:4])
    if safe_mode:
        reduce_conditions.insert(0, safe_mode)
    alerts["data_gaps"] = _dedupe_text_items(data_gaps, limit=8)
    alerts["reduce_conditions"] = _dedupe_text_items(reduce_conditions, limit=MAX_CANDIDATES)
    alerts["data_capability_mode"] = _to_text(console.get("decision_readiness_label"), "待检测")
    return alerts


def _hard_risk_item_text(item: Any) -> str:
    payload = _as_mapping(item)
    if not payload:
        return _to_text(item)
    risk_type = _to_text(payload.get("type") or payload.get("risk_type"), "硬风险")
    message = _to_text(payload.get("message") or payload.get("summary") or payload.get("title") or payload.get("risk"))
    date_text = _to_text(payload.get("date") or payload.get("ann_date") or payload.get("updated_at"))
    source = _to_text(payload.get("source"))
    parts = [risk_type]
    if message:
        parts.append(message)
    if date_text:
        parts.append(date_text)
    if source:
        parts.append(source)
    return "｜".join(parts)


def attach_hard_risk_risk_alerts(risk_alerts: Any = None, hard_risk_packet: Any = None) -> dict:
    alerts = _as_mapping(risk_alerts)
    hard = _as_mapping(hard_risk_packet)
    if not hard:
        return alerts
    status = _to_text(hard.get("status"))
    data_status = _to_text(hard.get("data_status"))
    risk_items = [_hard_risk_item_text(item) for item in _as_list(hard.get("risk_items"))]
    risk_items = [item for item in risk_items if item]
    risk_notes = [_to_text(item) for item in _as_list(hard.get("risk_notes"))]
    risk_notes = [item for item in risk_notes if item]
    must_not_do = [_to_text(item) for item in _as_list(alerts.get("must_not_do"))]
    reduce_conditions = [_to_text(item) for item in _as_list(alerts.get("reduce_conditions"))]
    data_gaps = [_to_text(item) for item in _as_list(alerts.get("data_gaps"))]
    if risk_items:
        must_not_do.insert(0, "公告/硬风险线索未复核前不加仓、不加融资。")
        reduce_conditions.extend(risk_items[:MAX_CANDIDATES])
        data_gaps.append("公告/硬风险存在待复核线索")
    elif status in {"failed", "partial"} or data_status in {"missing", "cached"}:
        must_not_do.append("公告/硬风险未验证前不新增风险暴露。")
        data_gaps.append(
            _to_text(
                hard.get("manual_required_text")
                or hard.get("summary")
                or "公告/硬风险仍待手动检测，不能当作无风险。",
            )
        )
    elif status == "ready":
        reduce_conditions.append("公告/硬风险无记录不等于无风险；公告正文和监管事实仍需复核。")
    alerts["must_not_do"] = _dedupe_text_items(must_not_do, limit=5)
    alerts["reduce_conditions"] = _dedupe_text_items(reduce_conditions, limit=MAX_CANDIDATES)
    alerts["data_gaps"] = _dedupe_text_items(data_gaps, limit=MAX_ERRORS)
    alerts["hard_risk_alerts"] = _dedupe_text_items(risk_items or risk_notes, limit=MAX_CANDIDATES)
    alerts["hard_risk_status"] = _to_text(hard.get("risk_state") or hard.get("summary") or status, "待验证")
    alerts["hard_risk_updated_at"] = _to_text(hard.get("updated_at") or hard.get("trade_date"), "暂无")
    return alerts


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
        data_capability_packet = resolve_data_capability_packet(state_map)
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
    market_packet = market_packet_service.build_command_center_market_packet(state_map, live)
    quant_packet = quant_packet_service.build_command_center_quant_packet(state_map, live, target=target)
    chip_packet = chip_packet_service.build_command_center_chip_packet(state_map, live, target=target)
    moneyflow_packet = moneyflow_packet_service.build_command_center_moneyflow_packet(state_map, live, target=target)
    dragon_tiger_packet = dragon_tiger_packet_service.build_command_center_dragon_tiger_packet(state_map, live, target=target)
    margin_packet = margin_packet_service.build_command_center_margin_packet(state_map, live, target=target)
    limit_emotion_packet = limit_emotion_packet_service.build_command_center_limit_emotion_packet(
        state_map,
        live,
        target=target,
    )
    hard_risk_packet = hard_risk_packet_service.build_command_center_hard_risk_packet(
        state_map,
        live,
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
    data_capability_snapshot = build_data_capability_snapshot(data_capability_packet)
    facts_packet_snapshot = facts_packet_service.build_command_center_facts_packet(
        {"command_center_facts_packet": facts_packet},
        target=target,
    )
    a_share_capability_matrix = a_share_capability_matrix_service.build_a_share_capability_matrix(
        data_capability_snapshot,
        facts_packet_snapshot,
    )
    data_gap_report = data_gap_report_service.build_command_center_data_gap_report(
        data_capability_snapshot,
        facts_packet_snapshot,
        refresh_summary=refresh,
        live_packet=live,
        errors=errors,
    )
    data_issue_explainer = data_issue_explainer_service.build_data_issue_explainer_packet(
        data_capability_snapshot,
        data_gap_report,
        refresh_summary=refresh,
        errors=errors,
    )
    data_capability_console = data_capability_console_service.build_data_capability_console_packet(
        data_capability_snapshot,
        data_gap_report,
        data_issue_explainer=data_issue_explainer,
        refresh_summary=refresh,
        errors=errors,
    )
    a_share_professional_facts = _as_mapping(state_map.get("a_share_professional_facts"))
    a_share_user_data_diagnostic = legacy_a_share_debug_summary_service.build_user_data_diagnostic_view_model(
        verified_technical_facts=(
            _as_mapping(a_share_professional_facts.get("verified_technical_facts"))
            or _as_mapping(state_map.get("verified_technical_facts"))
            or _as_mapping(live.get("verified_technical_facts"))
        ),
        moneyflow_data=(
            _as_mapping(a_share_professional_facts.get("moneyflow"))
            or _as_mapping(state_map.get("moneyflow_data"))
            or _as_mapping(state_map.get("a_share_moneyflow_data"))
        ),
        dragon_data=(
            _as_mapping(a_share_professional_facts.get("dragon_tiger"))
            or _as_mapping(state_map.get("dragon_data"))
            or _as_mapping(state_map.get("a_share_dragon_tiger_data"))
        ),
        margin_data=(
            _as_mapping(a_share_professional_facts.get("margin"))
            or _as_mapping(state_map.get("margin_data"))
            or _as_mapping(state_map.get("a_share_margin_data"))
        ),
        limit_emotion_data=(
            _as_mapping(a_share_professional_facts.get("limit_emotion"))
            or _as_mapping(state_map.get("limit_emotion_data"))
            or _as_mapping(state_map.get("a_share_limit_emotion_data"))
        ),
        chip_radar_data=(
            _as_mapping(a_share_professional_facts.get("chip_radar"))
            or _as_mapping(state_map.get("command_center_chip_packet"))
            or chip_packet
        ),
        hard_risk_data=(
            _as_mapping(a_share_professional_facts.get("verified_hard_risks"))
            or _as_mapping(a_share_professional_facts.get("hard_risk"))
            or _as_mapping(state_map.get("command_center_hard_risk_packet"))
            or hard_risk_packet
        ),
    )
    data_recovery_actions = build_data_recovery_actions_snapshot(data_capability_console)
    risk_alerts = attach_hard_risk_risk_alerts(
        attach_data_capability_risk_alerts(
            build_risk_alerts(decision, strategy, coverage, errors),
            data_capability_console,
        ),
        hard_risk_packet,
    )
    analysis_method_packet = (
        state_map.get("command_center_analysis_method_packet")
        or state_map.get("analysis_method_packet")
        or {}
    )
    position_map = _as_mapping(position_profile)
    market_profile_evidence = market_profile_summary_service.build_market_profile_evidence_strip(
        market_type=state_map.get("market_type") or position_map.get("market_type"),
        ticker=target or position_map.get("ticker"),
        name=position_map.get("name") or state_map.get("current_stock_name"),
        live_packet=live,
        decision_packet=decision,
        strategy_packet=strategy,
        home_snapshot=state_map.get("command_center_home_snapshot") or {},
        analysis_method_packet=analysis_method_packet,
    )
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
        "quant_packet": quant_packet,
        "chip_packet": chip_packet,
        "moneyflow_packet": moneyflow_packet,
        "dragon_tiger_packet": dragon_tiger_packet,
        "margin_packet": margin_packet,
        "limit_emotion_packet": limit_emotion_packet,
        "hard_risk_packet": hard_risk_packet,
        "a_share_fact_recovery_summary": {},
        "margin_etf_summary": build_margin_etf_summary(state_map, live, etf_packet=etf_packet),
        "risk_alerts": risk_alerts,
        "data_coverage": coverage,
        "data_freshness": build_data_freshness(timestamp, errors, deepseek_called=deepseek_called),
        "data_capability": data_capability_snapshot,
        "a_share_capability_matrix": a_share_capability_matrix,
        "facts_packet": facts_packet_snapshot,
        "data_gap_report": data_gap_report,
        "data_issue_explainer": data_issue_explainer,
        "data_capability_console": data_capability_console,
        "a_share_user_data_diagnostic": a_share_user_data_diagnostic,
        "data_recovery_actions": data_recovery_actions,
        "legacy_a_share_fact_recovery_actions": [],
        "tool_recovery_actions": [],
        "data_recovery_center": {},
        "market_packet": market_packet,
        "market_profile_evidence": market_profile_evidence,
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
        empty["risk_alerts"] = attach_hard_risk_risk_alerts(
            attach_data_capability_risk_alerts(
                build_risk_alerts(decision, strategy, coverage, errors),
                data_capability_console,
            ),
            hard_risk_packet,
        )
        empty["data_freshness"] = build_data_freshness("", errors, deepseek_called=deepseek_called)
        empty["data_capability"] = snapshot["data_capability"]
        empty["a_share_capability_matrix"] = snapshot["a_share_capability_matrix"]
        empty["facts_packet"] = snapshot["facts_packet"]
        empty["data_gap_report"] = snapshot["data_gap_report"]
        empty["data_issue_explainer"] = snapshot["data_issue_explainer"]
        empty["data_capability_console"] = snapshot["data_capability_console"]
        empty["a_share_user_data_diagnostic"] = snapshot["a_share_user_data_diagnostic"]
        empty["data_recovery_actions"] = snapshot["data_recovery_actions"]
        empty["legacy_a_share_fact_recovery_actions"] = build_legacy_a_share_fact_recovery_actions_snapshot(snapshot)
        empty["tool_recovery_actions"] = build_tool_recovery_actions_snapshot(snapshot)
        empty["data_recovery_center"] = build_home_data_recovery_center(empty)
        empty["market_packet"] = snapshot["market_packet"]
        empty["market_profile_evidence"] = snapshot["market_profile_evidence"]
        empty["radar_packet"] = snapshot["radar_packet"]
        empty["etf_packet"] = snapshot["etf_packet"]
        empty["discipline_packet"] = snapshot["discipline_packet"]
        empty["quant_packet"] = snapshot["quant_packet"]
        empty["chip_packet"] = snapshot["chip_packet"]
        empty["moneyflow_packet"] = snapshot["moneyflow_packet"]
        empty["dragon_tiger_packet"] = snapshot["dragon_tiger_packet"]
        empty["margin_packet"] = snapshot["margin_packet"]
        empty["limit_emotion_packet"] = snapshot["limit_emotion_packet"]
        empty["hard_risk_packet"] = snapshot["hard_risk_packet"]
        empty["a_share_fact_recovery_summary"] = build_a_share_fact_recovery_summary(empty)
        empty["errors"] = errors
        return empty
    snapshot["a_share_fact_recovery_summary"] = build_a_share_fact_recovery_summary(snapshot)
    snapshot["legacy_a_share_fact_recovery_actions"] = build_legacy_a_share_fact_recovery_actions_snapshot(snapshot)
    snapshot["tool_recovery_actions"] = build_tool_recovery_actions_snapshot(snapshot)
    snapshot["data_recovery_center"] = build_home_data_recovery_center(snapshot)
    return sanitize_snapshot_payload(snapshot)


def has_action_snapshot_data(snapshot: Any) -> bool:
    payload = _as_mapping(snapshot)
    if not payload or payload.get("is_empty"):
        return False
    return bool(
        _as_mapping(payload.get("decision_packet"))
        or _as_mapping(payload.get("strategy_packet"))
        or _as_mapping(payload.get("market_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("quant_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("chip_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("moneyflow_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("dragon_tiger_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("margin_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("limit_emotion_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("hard_risk_packet")).get("data_status") == "ready"
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
