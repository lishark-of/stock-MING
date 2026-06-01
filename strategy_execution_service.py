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
    return {
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
