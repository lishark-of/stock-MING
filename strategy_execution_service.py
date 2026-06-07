"""Pure service helpers for the Strategy Execution Lab MVP.

The service only reads already-computed session/cache packets. It deliberately
does not import Streamlit, call model providers, fetch market data, or run
backtests.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import MutableMapping
from typing import Any


PACKET_KEY = "strategy_execution_packet"
LAST_SUCCESS_KEY = "strategy_execution_last_success"

SOURCE = "strategy_execution_service / session_state cache"


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _clone(payload: Any) -> Any:
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _lower_text(*values: Any) -> str:
    return " ".join(str(value or "") for value in values).lower()


def _ticker_base(value: Any) -> str:
    text = str(value or "").upper().strip()
    return text.split(".")[0] if text else ""


def _status_from_payload(payload: Any, ready_keys: tuple[str, ...]) -> str:
    if not isinstance(payload, dict) or not payload:
        return "missing"
    if any(payload.get(key) not in (None, "", [], {}) for key in ready_keys):
        return "ready"
    return "cached"


def _trace_status(payload: Any, ready_keys: tuple[str, ...] = ("status", "summary")) -> str:
    return _status_from_payload(payload, ready_keys)


def _trace_item(name: str, status: str, used: bool, summary: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": status or "missing",
        "used": bool(used),
        "summary": summary or "暂无可读摘要。",
    }


def _extract_quant_context(state: MutableMapping[str, Any], live_packet: dict[str, Any] | None = None) -> dict[str, Any]:
    quant = state.get("legacy_quant_result") or {}
    live_quant = (live_packet or state.get("command_center_live_packet") or {}).get("quant") or {}
    payload = quant if isinstance(quant, dict) and quant else live_quant if isinstance(live_quant, dict) else {}
    score = _num(payload.get("score"))
    direction = str(payload.get("direction") or payload.get("label") or payload.get("status") or "")
    summary = str(payload.get("summary") or "")
    status = _status_from_payload(payload, ("score", "direction", "summary", "status"))
    strong = bool(
        (score is not None and score >= 60)
        or any(word in direction for word in ("偏积极", "强", "进攻", "可准备"))
        or any(word in summary for word in ("偏积极", "强", "可准备"))
    )
    weak = bool(
        (score is not None and score <= 50)
        or any(word in direction for word in ("防守", "弱", "降风险"))
        or any(word in summary for word in ("防守", "风险"))
    )
    return {
        "status": status,
        "score": score,
        "direction": direction,
        "summary": summary,
        "strong": strong,
        "weak": weak,
        "source": payload.get("source") or "legacy_quant_result",
    }


def _extract_backtest_context(
    state: MutableMapping[str, Any],
    target: str = "",
) -> dict[str, Any]:
    report = state.get("last_backtest_report") or {}
    multi_result = state.get("last_multi_backtest") or {}
    if isinstance(report, dict) and target and report.get("ticker") and _ticker_base(report.get("ticker")) != _ticker_base(target):
        report = {}
        multi_result = {}

    metrics = report.get("metrics") or report if isinstance(report, dict) else {}
    latest_signal = report.get("latest_signal") or {} if isinstance(report, dict) else {}
    trader_brief = report.get("trader_brief") or {} if isinstance(report, dict) else {}
    warnings = list(trader_brief.get("warnings") or [])
    multi_summary = multi_result.get("summary", "") if isinstance(multi_result, dict) else ""
    win_rate = _num(
        metrics.get("round_trip_win_rate")
        or metrics.get("win_rate")
        or metrics.get("win_rate_pct")
        or metrics.get("exit_action_win_rate")
    )
    max_drawdown = _num(metrics.get("max_drawdown_pct") or metrics.get("max_drawdown"))
    sharpe = _num(metrics.get("sharpe"))
    trade_count = int(_num(metrics.get("trade_count"), 0) or 0)
    signal_action = str(latest_signal.get("action") or trader_brief.get("action") or "")
    signal_reason = str(latest_signal.get("reason") or "")
    status = _status_from_payload(report, ("metrics", "latest_signal", "summary", "trader_brief"))
    return {
        "status": status,
        "report": report,
        "metrics": metrics if isinstance(metrics, dict) else {},
        "summary": str(report.get("summary") or multi_summary or ""),
        "win_rate": win_rate,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "trade_count": trade_count,
        "latest_signal": signal_action,
        "signal_reason": signal_reason,
        "warnings": warnings[:6],
        "trader_action": str(trader_brief.get("action") or ""),
    }


def _build_action(
    quant: dict[str, Any],
    backtest: dict[str, Any],
) -> tuple[str, str, str]:
    has_quant = quant.get("status") in {"ready", "cached"}
    has_backtest = backtest.get("status") in {"ready", "cached"}
    if not has_quant and not has_backtest:
        return "等待", "低", "数据不足，先等待刷新量化和纪律结果。"

    signal_text = _lower_text(backtest.get("latest_signal"), backtest.get("signal_reason"), backtest.get("trader_action"))
    drawdown = abs(_num(backtest.get("max_drawdown"), 0) or 0)
    warnings = backtest.get("warnings") or []
    win_rate = _num(backtest.get("win_rate"))
    trade_count = int(_num(backtest.get("trade_count"), 0) or 0)

    if any(word in signal_text for word in ("reduce", "sell", "exit", "止损", "退出", "减仓", "卖出")):
        return "降风险", "中", "纪律信号偏向减仓或退出，优先保护本金。"
    if drawdown >= 22 or len(warnings) >= 3:
        return "降风险", "中", "历史回撤或纪律警告偏多，当前不适合提高风险敞口。"
    if drawdown >= 18 or quant.get("weak"):
        return "只观察", "中", "风险处于偏高区间，先观察验证信号，不主动加仓。"

    signal_is_entry = any(word in signal_text for word in ("buy", "add", "watch", "小仓", "尝试", "继续观察", "买入"))
    if quant.get("strong") and signal_is_entry and win_rate is not None and win_rate >= 55 and drawdown < 18:
        confidence = "高" if trade_count >= 8 else "中"
        return "等待", confidence, "量化和纪律同向偏积极，可准备小幅试探，但必须等验证信号。"
    if quant.get("strong") or signal_is_entry:
        return "等待", "中", "有局部积极线索，但还不能直接转成激进买入。"
    return "只观察", "低", "现有缓存只能支持观察，不能证明进攻条件已经成立。"


def _build_strategy_execution_trace(
    state: MutableMapping[str, Any],
    *,
    profile: dict[str, Any],
    live: dict[str, Any],
    quant: dict[str, Any],
    backtest: dict[str, Any],
    action: str,
    confidence: str,
    summary: str,
) -> dict[str, Any]:
    decision = state.get("command_center_decision_packet") or {}
    data_capability = state.get("command_center_data_capability_packet") or state.get("data_capability_packet") or {}
    analysis_method = state.get("command_center_analysis_method_packet") or {}
    home_snapshot = state.get("command_center_home_snapshot") or {}
    moneyflow = state.get("command_center_moneyflow_packet") or state.get("moneyflow_packet") or {}
    dragon_tiger = state.get("command_center_dragon_tiger_packet") or state.get("dragon_tiger_packet") or {}
    margin = state.get("command_center_margin_packet") or state.get("margin_packet") or {}
    hard_risk = state.get("command_center_hard_risk_packet") or state.get("hard_risk_packet") or {}
    position_ready = bool(profile and any(profile.get(key) not in (None, "", [], {}) for key in ("ticker", "shares", "holding_units", "cost_price", "current_price", "normalized_position_state")))
    live_status = _trace_status(live, ("conclusion", "quant", "discipline"))
    decision_status = _trace_status(decision, ("overall_action", "status"))
    data_capability_status = _trace_status(data_capability, ("status_groups", "items", "summary"))
    analysis_status = _trace_status(analysis_method, ("market", "summary", "methods"))
    home_status = _trace_status(home_snapshot, ("holding_action", "today_action", "data_freshness"))
    input_sources = [
        _trace_item("当前持仓", "ready" if position_ready else "missing", position_ready, profile.get("profit_state") or profile.get("normalized_position_state") or "持仓输入用于生成仓位建议和风险预算。"),
        _trace_item("行情数据", live_status, live_status in {"ready", "cached"}, "综合推演中心已读取当前本地作战包。" if live_status != "missing" else "行情或综合作战包仍待刷新。"),
        _trace_item("今日总决策", decision_status, decision_status in {"ready", "cached"}, str(decision.get("overall_action") or decision.get("summary") or "今日总决策用于约束策略方向。")),
        _trace_item("市场分析方法", analysis_status, analysis_status in {"ready", "cached"}, str(analysis_method.get("market") or analysis_method.get("summary") or "市场类型和验证重点待确认。")),
        _trace_item("交易纪律/回测", backtest.get("status") or "missing", backtest.get("status") in {"ready", "cached"}, backtest.get("summary") or backtest.get("signal_reason") or "纪律/回测缓存用于判断是否等待或降风险。"),
        _trace_item("量化推演", quant.get("status") or "missing", quant.get("status") in {"ready", "cached"}, quant.get("summary") or quant.get("direction") or "量化缓存用于判断方向强弱。"),
        _trace_item("数据能力状态", data_capability_status, data_capability_status in {"ready", "cached"}, str(data_capability.get("summary") or "数据能力影响置信度和能否放大仓位。")),
        _trace_item("Home Snapshot", home_status, home_status in {"ready", "cached"}, "首页快照用于回填持仓、风险、ETF 和候选状态。" if home_status != "missing" else "首页快照尚未生成。"),
        _trace_item("资金/龙虎榜/融资融券", _trace_status({"moneyflow": moneyflow, "dragon_tiger": dragon_tiger, "margin": margin}, ("moneyflow", "dragon_tiger", "margin")), any(bool(item) for item in (moneyflow, dragon_tiger, margin)), "A股资金、龙虎榜和融资融券只作为待验证辅助证据。"),
        _trace_item("公告/硬风险", _trace_status(hard_risk, ("alerts", "items", "summary", "status")), bool(hard_risk), "公告/硬风险未排除前，不支持放大仓位。"),
    ]
    missing_inputs = [
        item["name"]
        for item in input_sources
        if item["status"] in {"missing", "waiting", "failed"} or not item["used"]
    ]
    rules_fired: list[dict[str, str]] = []
    if quant.get("status") == "missing" and backtest.get("status") == "missing":
        rules_fired.append({"rule": "数据不足", "result": "等待", "evidence": "量化推演和交易纪律均未生成", "impact": "不形成新的仓位动作"})
    if action in {"只观察", "等待"}:
        rules_fired.append({"rule": "验证不足", "result": action, "evidence": "现有线索不足以升级为进攻动作", "impact": "降低置信度，保留观察路径"})
    if action == "降风险":
        rules_fired.append({"rule": "纪律/回撤风险", "result": "降风险", "evidence": summary, "impact": "暂停新增风险，优先保护本金"})
    if backtest.get("status") == "missing":
        rules_fired.append({"rule": "纪律缺口", "result": action, "evidence": "交易纪律/回测仍待验证", "impact": "不能把策略结论升级为加仓依据"})
    if quant.get("weak"):
        rules_fired.append({"rule": "量化偏弱", "result": action, "evidence": quant.get("summary") or quant.get("direction") or "量化方向偏弱", "impact": "压低进攻倾向"})
    if not rules_fired:
        rules_fired.append({"rule": "本地规则汇总", "result": action, "evidence": summary, "impact": f"置信度为{confidence}"})
    return {
        "decision_source": "rule_based_packet",
        "deepseek_used": False,
        "input_sources": input_sources,
        "rules_fired": rules_fired,
        "missing_inputs": missing_inputs,
        "final_reason": summary,
        "safe_text": "策略执行建议由本地规则和结构化 packet 生成；DeepSeek 仅在手动点击后解释，不直接生成仓位建议。",
    }


def _build_conditions(action: str, position_profile: dict[str, Any], backtest: dict[str, Any]) -> dict[str, str]:
    position_state = position_profile.get("normalized_position_state") or "未知持仓状态"
    latest_signal = backtest.get("latest_signal") or "暂无"
    base_add = "仅在量化方向、纪律信号、市场环境至少两项同向改善后，才考虑小幅试探。"
    if position_profile.get("allow_trial_entry"):
        base_add = "未持仓但有参考价格时，只允许小幅 0.5-1 成试仓，并等待量价确认。"
    elif position_profile.get("is_holding"):
        base_add = "已持仓时不因单次强势追高加仓，只在回踩不破关键位且风险预算允许时考虑。"

    reduce_condition = "若跌破纪律止损线、回测信号转为减仓/退出，或浮亏扩大到预设边界，优先降风险。"
    if action == "降风险":
        reduce_condition = f"当前纪律信号为 {latest_signal}，先执行减仓/降低暴露检查。"
    invalidation = "若市场环境转弱、回测纪律失效、或最新验证信号与当前判断相反，本轮策略结论失效。"
    return {
        "position_advice": f"{position_state}：{action}。{base_add if action != '降风险' else reduce_condition}",
        "add_condition": base_add,
        "reduce_condition": reduce_condition,
        "invalidation_condition": invalidation,
    }


def _build_paths(action: str) -> list[dict[str, str]]:
    return [
        {
            "name": "乐观路径",
            "condition": "量化方向继续改善，纪律信号没有触发减仓，市场环境不转弱。",
            "action": "只允许小幅试探或持仓观察，不追求一次性重仓。",
        },
        {
            "name": "中性路径",
            "condition": "信号分歧或缺少新增验证，价格在关键区间震荡。",
            "action": "维持等待，继续观察量能、趋势和纪律信号。",
        },
        {
            "name": "谨慎路径",
            "condition": "出现减仓/退出信号、回撤扩大，或综合中心基础数据失败较多。",
            "action": "降风险，停止加仓，把仓位动作降到防守模式。",
        },
    ]


def _build_risk_budget(action: str, position_profile: dict[str, Any], backtest: dict[str, Any]) -> dict[str, Any]:
    capital = _num(position_profile.get("capital_plan"))
    drawdown = abs(_num(backtest.get("max_drawdown"), 0) or 0)
    if action == "降风险" or drawdown >= 22:
        risk_level = "高"
        add_ratio = 0
        cash_ratio = 0.5
    elif action == "只观察" or drawdown >= 18:
        risk_level = "中"
        add_ratio = 0.05
        cash_ratio = 0.35
    else:
        risk_level = "低"
        add_ratio = 0.1
        cash_ratio = 0.3
    return {
        "risk_level": risk_level,
        "max_add_amount": round(capital * add_ratio, 2) if capital is not None else None,
        "cash_buffer": round(capital * cash_ratio, 2) if capital is not None else None,
        "position_mode": position_profile.get("normalized_position_state") or "未知",
    }


def _fallback_packet(message: str = "数据不足，先等待刷新量化和纪律结果。") -> dict[str, Any]:
    packet = {
        "status": "waiting",
        "action": "等待",
        "confidence": "低",
        "position_advice": message,
        "add_condition": "先刷新今日基础数据或生成量化/纪律缓存。",
        "reduce_condition": "若已有持仓但缺少纪律缓存，先按既有止损线控制风险。",
        "invalidation_condition": "缺少基础数据时不形成新的交易结论。",
        "next_5_10_day_paths": _build_paths("等待"),
        "discipline_check": {
            "status": "missing",
            "win_rate": None,
            "max_drawdown": None,
            "latest_signal": "",
            "warnings": ["量化和回测缓存不足。"],
        },
        "risk_budget": {
            "risk_level": "未知",
            "max_add_amount": None,
            "cash_buffer": None,
            "position_mode": "未知",
        },
        "data_status": {
            "quant": "missing",
            "backtest": "missing",
            "live_packet": "missing",
        },
        "updated_at": _now(),
        "source": SOURCE,
        "deepseek_called": False,
        "summary": message,
        "last_error": None,
    }
    packet["strategy_execution_trace"] = {
        "decision_source": "rule_based_packet",
        "deepseek_used": False,
        "input_sources": [
            _trace_item("量化推演", "missing", False, "量化缓存不足。"),
            _trace_item("交易纪律/回测", "missing", False, "纪律/回测缓存不足。"),
            _trace_item("行情数据", "missing", False, "综合作战包待刷新。"),
        ],
        "rules_fired": [{"rule": "数据不足", "result": "等待", "evidence": "量化和纪律缓存不足", "impact": "不形成新的仓位动作"}],
        "missing_inputs": ["量化推演", "交易纪律/回测", "行情数据"],
        "final_reason": message,
        "safe_text": "策略执行建议由本地规则和结构化 packet 生成；DeepSeek 仅在手动点击后解释，不直接生成仓位建议。",
    }
    return packet


def build_strategy_execution_packet(
    state: MutableMapping[str, Any],
    target: str = "",
    position_profile: dict[str, Any] | None = None,
    live_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a conservative execution packet from already-cached data only."""
    live = live_packet or state.get("command_center_live_packet") or {}
    profile = position_profile or state.get("position_profile") or {}
    quant = _extract_quant_context(state, live)
    backtest = _extract_backtest_context(state, target=target)
    live_status = _status_from_payload(live, ("conclusion", "quant", "discipline"))

    if quant["status"] == "missing" and backtest["status"] == "missing":
        packet = _fallback_packet()
        packet["risk_budget"] = _build_risk_budget("等待", profile, backtest)
        return packet

    action, confidence, summary = _build_action(quant, backtest)
    conditions = _build_conditions(action, profile, backtest)
    trace = _build_strategy_execution_trace(
        state,
        profile=profile,
        live=live,
        quant=quant,
        backtest=backtest,
        action=action,
        confidence=confidence,
        summary=summary,
    )
    packet = {
        "status": "ready",
        "action": action,
        "confidence": confidence,
        "position_advice": conditions["position_advice"],
        "add_condition": conditions["add_condition"],
        "reduce_condition": conditions["reduce_condition"],
        "invalidation_condition": conditions["invalidation_condition"],
        "next_5_10_day_paths": _build_paths(action),
        "discipline_check": {
            "status": backtest["status"],
            "win_rate": backtest["win_rate"],
            "max_drawdown": backtest["max_drawdown"],
            "latest_signal": backtest["latest_signal"],
            "warnings": backtest["warnings"],
        },
        "risk_budget": _build_risk_budget(action, profile, backtest),
        "data_status": {
            "quant": quant["status"],
            "backtest": backtest["status"],
            "live_packet": live_status,
        },
        "updated_at": _now(),
        "source": SOURCE,
        "deepseek_called": False,
        "strategy_execution_trace": trace,
        "summary": summary,
        "last_error": None,
    }
    return _clone(packet)


def safe_generate_strategy_execution_packet(
    state: MutableMapping[str, Any],
    target: str = "",
    position_profile: dict[str, Any] | None = None,
    live_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate and persist a packet, preserving the last success on failure."""
    try:
        packet = build_strategy_execution_packet(
            state,
            target=target,
            position_profile=position_profile,
            live_packet=live_packet,
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
        packet = _fallback_packet("策略执行建议生成失败，暂无上次成功结果。")
        packet["status"] = "failed"
        packet["last_error"] = str(exc)
        packet["deepseek_called"] = False
        state[PACKET_KEY] = _clone(packet)
        return packet
