"""Pure rule engine for Command Center daily decisions.

This module only reads already-built packets and session-style dictionaries. It
does not import Streamlit, call DeepSeek, fetch market data, or run backtests.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import MutableMapping
from typing import Any


PACKET_KEY = "command_center_decision_packet"
LAST_SUCCESS_KEY = "command_center_decision_last_success"
SOURCE = "command_center_decision_engine"

MODULE_KEYS = ("market", "quant", "discipline", "margin_etf", "next_ticket", "strategy_execution")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _clone(payload: Any) -> Any:
    return json.loads(json.dumps(payload or {}, ensure_ascii=False, default=str))


def _text(*values: Any) -> str:
    return " ".join(str(value or "") for value in values)


def _lower_text(*values: Any) -> str:
    return _text(*values).lower()


def _coverage_for_section(section: Any) -> str:
    if not isinstance(section, dict) or not section:
        return "missing"
    status = str(section.get("status") or "").lower()
    refresh_label = str(section.get("refresh_label") or "")
    if section.get("is_fresh") or status in {"ready", "completed", "ok", "已刷新"}:
        return "ready"
    if section.get("last_success") or section.get("stale") or refresh_label == "使用缓存":
        return "cached"
    if status in {"failed", "failure", "失败"} and section.get("data"):
        return "cached"
    if status in {"waiting", "partial"}:
        return "cached"
    return "missing"


def _build_data_coverage(
    live_packet: dict[str, Any],
    strategy_packet: dict[str, Any],
) -> dict[str, str]:
    coverage = {
        key: _coverage_for_section((live_packet or {}).get(key))
        for key in MODULE_KEYS
        if key != "strategy_execution"
    }
    coverage["strategy_execution"] = _coverage_for_section(strategy_packet)
    return coverage


def _market_bias(market: dict[str, Any]) -> str:
    if _coverage_for_section(market) == "missing":
        return "未刷新"
    blob = _lower_text(market.get("summary"), market.get("market_state"), market.get("status"), market.get("data"))
    if any(word in blob for word in ("偏弱", "弱", "防守", "风险", "降风险", "退潮", "冰点")):
        return "偏弱"
    if any(word in blob for word in ("偏强", "强", "进攻", "暖", "活跃", "修复")):
        return "偏强"
    return "震荡"


def _has_positive_quant(quant: dict[str, Any]) -> bool:
    blob = _lower_text(quant.get("direction"), quant.get("summary"), quant.get("status"), quant.get("data"))
    score = quant.get("score")
    try:
        score_ok = score is not None and float(score) >= 60
    except (TypeError, ValueError):
        score_ok = False
    return score_ok or any(word in blob for word in ("偏积极", "偏强", "可准备", "进攻"))


def _has_discipline_risk(discipline: dict[str, Any]) -> bool:
    blob = _lower_text(discipline.get("action_state"), discipline.get("summary"), discipline.get("key_rules"), discipline.get("data"))
    return any(word in blob for word in ("降风险", "减仓", "退出", "止损", "禁止", "待补充", "回撤偏大"))


def _has_discipline_support(discipline: dict[str, Any]) -> bool:
    blob = _lower_text(discipline.get("action_state"), discipline.get("summary"), discipline.get("data"))
    return any(word in blob for word in ("允许进攻", "小仓", "继续观察", "可参考", "已刷新"))


def _strategy_action(strategy_packet: dict[str, Any]) -> str:
    return str(strategy_packet.get("overall_action") or strategy_packet.get("action") or "")


def _margin_risk(margin_etf: dict[str, Any], strategy_packet: dict[str, Any]) -> bool:
    blob = _lower_text(
        margin_etf.get("action_state"),
        margin_etf.get("summary"),
        margin_etf.get("today_main_direction"),
        margin_etf.get("data"),
        (strategy_packet.get("risk_budget") or {}).get("risk_level"),
    )
    cash_ratio = margin_etf.get("recommended_cash_ratio")
    try:
        cash_low = cash_ratio is not None and float(cash_ratio) < 0.2
    except (TypeError, ValueError):
        cash_low = False
    return cash_low or any(word in blob for word in ("高", "禁止融资", "降低杠杆", "降风险", "现金不足"))


def _next_ticket_has_candidate(next_ticket: dict[str, Any]) -> bool:
    candidates = next_ticket.get("top_candidates") or []
    data = next_ticket.get("data") or {}
    if isinstance(data, dict):
        candidates = candidates or data.get("top_candidates") or data.get("rule_rows") or []
    return bool(candidates)


def _build_modes(
    overall_action: str,
    market_bias: str,
    margin_etf: dict[str, Any],
    next_ticket: dict[str, Any],
    strategy_packet: dict[str, Any],
) -> dict[str, str]:
    strategy_position_mode = (strategy_packet.get("risk_budget") or {}).get("position_mode") or ""
    if overall_action == "小幅进攻":
        position_mode = "轻仓试探"
    elif overall_action == "降风险":
        position_mode = "降低仓位"
    elif "持仓" in strategy_position_mode:
        position_mode = "持仓观察"
    elif overall_action == "只观察":
        position_mode = "空仓等待"
    else:
        position_mode = "空仓等待"

    if _margin_risk(margin_etf, strategy_packet):
        margin_mode = "禁止融资"
    elif overall_action == "降风险":
        margin_mode = "降低杠杆"
    elif overall_action == "小幅进攻" and market_bias == "偏强":
        margin_mode = "小幅融资"
    else:
        margin_mode = "不使用融资"

    etf_priority = margin_etf.get("today_main_direction") or margin_etf.get("action_state") or "等待 ETF 配置刷新"
    if _coverage_for_section(margin_etf) == "missing":
        etf_priority = "待刷新"

    next_ticket_priority = "待刷新"
    if _next_ticket_has_candidate(next_ticket):
        next_ticket_priority = "放入观察池，等待验证"
    elif _coverage_for_section(next_ticket) != "missing":
        next_ticket_priority = next_ticket.get("action_state") or "暂无候选，只观察"

    return {
        "position_mode": position_mode,
        "margin_mode": margin_mode,
        "etf_priority": etf_priority,
        "next_ticket_priority": next_ticket_priority,
    }


def _default_must_not_do(margin_mode: str) -> list[str]:
    items = ["不追高", "不满仓", "不在未刷新数据下加融资"]
    if margin_mode in {"禁止融资", "降低杠杆"}:
        items.append("不加融资")
    return list(dict.fromkeys(items))


def _validation_conditions(overall_action: str, coverage: dict[str, str]) -> list[str]:
    conditions = [
        "先确认市场环境、量化、纪律三项至少两项同向。",
        "下一票候选必须进入观察池，等待验证条件出现。",
    ]
    if overall_action in {"等待", "只观察"}:
        conditions.insert(0, "点击刷新今日基础数据，补齐缺失模块后再判断。")
    if coverage.get("strategy_execution") == "missing":
        conditions.append("生成策略执行建议后，再确认仓位边界。")
    return conditions[:4]


def _status_from_coverage(coverage: dict[str, str]) -> str:
    useful = sum(1 for value in coverage.values() if value in {"ready", "cached"})
    ready = sum(1 for value in coverage.values() if value == "ready")
    if useful < 3:
        return "waiting"
    if ready >= 4 or useful >= 5:
        return "ready"
    return "partial"


def _decide(
    live_packet: dict[str, Any],
    strategy_packet: dict[str, Any],
    coverage: dict[str, str],
) -> dict[str, str]:
    market = live_packet.get("market") or {}
    quant = live_packet.get("quant") or {}
    discipline = live_packet.get("discipline") or {}
    margin_etf = live_packet.get("margin_etf") or {}
    next_ticket = live_packet.get("next_ticket") or {}

    status = _status_from_coverage(coverage)
    market_bias = _market_bias(market)
    strategy_action = _strategy_action(strategy_packet)
    discipline_risk = _has_discipline_risk(discipline)
    discipline_support = _has_discipline_support(discipline)
    quant_positive = _has_positive_quant(quant)
    margin_risk = _margin_risk(margin_etf, strategy_packet)

    if status == "waiting":
        overall_action = "等待"
        risk_level = "中"
        reason = "基础数据未刷新，先等待或点击刷新今日基础数据。"
    elif market_bias == "偏弱" and discipline_risk and strategy_action == "降风险":
        overall_action = "降风险"
        risk_level = "高"
        reason = "市场偏弱、纪律提示风险且策略执行要求降风险，优先降低暴露。"
    elif margin_risk and strategy_action in {"降风险", "只观察"}:
        overall_action = "降风险"
        risk_level = "高"
        reason = "融资 ETF 或策略风险预算偏高，禁止新增融资并降低杠杆。"
    elif market_bias == "偏强" and quant_positive and discipline_support and not margin_risk:
        overall_action = "小幅进攻"
        risk_level = "中"
        reason = "市场、量化和纪律同向偏积极，但只允许小幅试探。"
    elif (market_bias == "偏强" and (discipline_risk or strategy_action == "降风险")) or (
        market_bias == "偏弱" and (quant_positive or strategy_action in {"等待", "小幅试探"})
    ):
        overall_action = "只观察"
        risk_level = "中"
        reason = "模块信号冲突：市场、量化、纪律或策略执行没有形成一致方向。"
    else:
        overall_action = "只观察"
        risk_level = "中" if status == "partial" else "低"
        reason = "当前只形成缓存/部分刷新判断，先观察验证，不输出激进动作。"

    if _next_ticket_has_candidate(next_ticket) and not (discipline_support and risk_level == "低"):
        reason = f"{reason} 下一票候选只放入观察池，等待纪律和风险确认。"

    return {
        "status": status,
        "overall_action": overall_action,
        "market_bias": market_bias,
        "risk_level": risk_level,
        "reason_summary": reason,
    }


def _fallback_packet(message: str = "基础数据未刷新，先等待或点击刷新今日基础数据。") -> dict[str, Any]:
    return {
        "status": "waiting",
        "overall_action": "等待",
        "market_bias": "未刷新",
        "position_mode": "空仓等待",
        "margin_mode": "不使用融资",
        "etf_priority": "待刷新",
        "next_ticket_priority": "待刷新",
        "risk_level": "中",
        "must_not_do": ["不追高", "不满仓", "不在未刷新数据下加融资"],
        "next_validation_conditions": ["点击刷新今日基础数据，补齐缺失模块后再判断。"],
        "reason_summary": message,
        "data_coverage": {key: "missing" for key in MODULE_KEYS},
        "updated_at": _now(),
        "source": SOURCE,
        "deepseek_called": False,
        "last_error": None,
    }


def build_command_center_decision_packet(
    state: MutableMapping[str, Any],
    live_packet: dict[str, Any] | None = None,
    strategy_packet: dict[str, Any] | None = None,
    refresh_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build today's conservative decision from already available packets."""
    del refresh_summary
    live = live_packet or state.get("command_center_live_packet") or {}
    strategy = strategy_packet or live.get("strategy_execution") or state.get("strategy_execution_packet") or {}
    if not isinstance(live, dict):
        live = {}
    if not isinstance(strategy, dict):
        strategy = {}

    coverage = _build_data_coverage(live, strategy)
    if all(value == "missing" for value in coverage.values()):
        return _fallback_packet()

    decision = _decide(live, strategy, coverage)
    modes = _build_modes(
        decision["overall_action"],
        decision["market_bias"],
        live.get("margin_etf") or {},
        live.get("next_ticket") or {},
        strategy,
    )
    packet = {
        **decision,
        **modes,
        "must_not_do": _default_must_not_do(modes["margin_mode"]),
        "next_validation_conditions": _validation_conditions(decision["overall_action"], coverage),
        "data_coverage": coverage,
        "updated_at": _now(),
        "source": SOURCE,
        "deepseek_called": False,
        "last_error": None,
    }
    return _clone(packet)


def safe_generate_command_center_decision_packet(
    state: MutableMapping[str, Any],
    live_packet: dict[str, Any] | None = None,
    strategy_packet: dict[str, Any] | None = None,
    refresh_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate and persist a decision packet, preserving last success on failure."""
    try:
        packet = build_command_center_decision_packet(
            state,
            live_packet=live_packet,
            strategy_packet=strategy_packet,
            refresh_summary=refresh_summary,
        )
        packet["deepseek_called"] = False
        state[PACKET_KEY] = _clone(packet)
        if packet.get("status") != "failed":
            state[LAST_SUCCESS_KEY] = _clone(packet)
        return _clone(packet)
    except Exception as exc:
        last_success = state.get(LAST_SUCCESS_KEY)
        if isinstance(last_success, dict) and last_success:
            packet = _clone(last_success)
            packet["status"] = "failed"
            packet["stale"] = True
            packet["last_error"] = str(exc)
            packet["deepseek_called"] = False
            state[PACKET_KEY] = _clone(packet)
            return packet
        packet = _fallback_packet("今日总决策生成失败，暂无上次成功结果。")
        packet["status"] = "failed"
        packet["last_error"] = str(exc)
        packet["deepseek_called"] = False
        state[PACKET_KEY] = _clone(packet)
        return packet
