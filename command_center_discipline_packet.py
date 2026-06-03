from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_RULES = 5
MAX_WARNINGS = 6


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def to_number(value: Any) -> int | float | None:
    if value in [None, ""]:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Number):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("%", "")
        if not text or text in {"--", "暂无", "N/A", "None", "nan"}:
            return None
        try:
            number = float(text)
            return int(number) if number.is_integer() else number
        except Exception:
            return None
    return None


def _ticker_base(value: Any) -> str:
    text = to_text(value).upper()
    return text.split(".")[0] if text else ""


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = to_text(value)
        if text:
            return text
    return default


def _first_number(*values: Any) -> int | float | None:
    for value in values:
        number = to_number(value)
        if number is not None:
            return number
    return None


def _dedupe_text(values: Any, limit: int = MAX_WARNINGS) -> list[str]:
    raw_values = values if isinstance(values, (list, tuple)) else [values]
    items = []
    seen = set()
    for item in raw_values:
        if isinstance(item, Mapping):
            text = _first_text(item.get("message"), item.get("summary"), item.get("reason"), item.get("name"))
        else:
            text = to_text(item)
        if text and text not in seen:
            seen.add(text)
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _rules_from_value(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = [part.strip(" ；;\n\t") for part in value.replace("\n", "；").split("；")]
        return [part for part in parts if part][:MAX_RULES]
    return _dedupe_text(value, limit=MAX_RULES)


def _status_from(report: Mapping[str, Any], check: Mapping[str, Any], live_section: Mapping[str, Any]) -> str:
    check_status = to_text(check.get("status"))
    if report:
        return "ready"
    if check_status in {"skipped", "missing", "waiting"}:
        return "waiting"
    if check or live_section:
        return "partial"
    return "waiting"


def _normalize_drawdown(value: Any) -> int | float | None:
    number = to_number(value)
    if number is None:
        return None
    return abs(number)


def _format_number(value: Any, suffix: str = "") -> str:
    number = to_number(value)
    if number is None:
        return "待验证"
    if isinstance(number, float) and not number.is_integer():
        return f"{number:.2f}{suffix}"
    return f"{int(number)}{suffix}"


def _metric_tone(label: str, value: int | float | None) -> str:
    if value is None:
        return "missing"
    if label == "最大回撤":
        if value >= 20:
            return "failed"
        if value >= 15:
            return "stale"
        return "ready"
    if label == "胜率":
        if value >= 60:
            return "ready"
        if value >= 50:
            return "stale"
        return "failed"
    return "ready"


def _date_range_from(report: Mapping[str, Any]) -> dict:
    date_range = as_mapping(report.get("date_range"))
    return {
        "start": _first_text(date_range.get("start"), report.get("start_date")),
        "end": _first_text(date_range.get("end"), report.get("end_date"), report.get("updated_at")),
    }


def _build_metric_items(
    win_rate: int | float | None,
    max_drawdown: int | float | None,
    sharpe: int | float | None,
    trade_count: int | float | None,
) -> list[dict]:
    rows = [
        ("胜率", win_rate, "%"),
        ("最大回撤", max_drawdown, "%"),
        ("夏普", sharpe, ""),
        ("交易次数", trade_count, "次"),
    ]
    return [
        {
            "label": label,
            "value": _format_number(value, suffix),
            "tone": _metric_tone(label, value),
        }
        for label, value, suffix in rows
    ]


def _backtest_status_text(status: str, data_status: str) -> str:
    if status == "ready":
        return "已读取回测缓存"
    if data_status == "cached":
        return "使用上次回测缓存"
    return "待手动运行回测"


def _build_evidence_items(
    report: Mapping[str, Any],
    multi_result: Mapping[str, Any],
    latest_signal_text: str,
    action_state: str,
    summary: str,
) -> list[dict]:
    if not report:
        return [
            {
                "label": "回测缓存",
                "value": "待刷新",
                "detail": "综合中心不会自动跑回测；需要在高级工具箱手动运行。",
                "tone": "missing",
            }
        ]
    date_range = _date_range_from(report)
    items = [
        {
            "label": "动作边界",
            "value": action_state or "只观察",
            "detail": latest_signal_text or summary or "最新信号待验证。",
            "tone": "failed" if action_state == "降风险" else "ready",
        },
        {
            "label": "回测区间",
            "value": " - ".join(item for item in [date_range.get("start"), date_range.get("end")] if item) or "待验证",
            "detail": "只引用旧版手动回测缓存，不自动拉行情。",
            "tone": "ready" if date_range.get("end") else "stale",
        },
    ]
    multi_summary = _first_text(multi_result.get("summary"))
    if multi_summary:
        items.append(
            {
                "label": "多模式验证",
                "value": "已缓存",
                "detail": multi_summary,
                "tone": "ready",
            }
        )
    return items[:MAX_RULES]


def _derive_action_state(
    report: Mapping[str, Any],
    check: Mapping[str, Any],
    live_section: Mapping[str, Any],
    win_rate: int | float | None,
    max_drawdown: int | float | None,
    latest_signal: str,
) -> str:
    explicit = _first_text(live_section.get("action_state"), check.get("action_state"))
    if explicit and explicit not in {"待刷新", "待补充"}:
        return explicit
    signal = latest_signal.lower()
    if any(token in latest_signal for token in ("减仓", "卖出", "止损", "退出")) or any(token in signal for token in ("sell", "exit", "reduce")):
        return "降风险"
    if max_drawdown is not None and max_drawdown >= 20:
        return "降风险"
    if win_rate is not None and win_rate >= 60 and (max_drawdown is None or max_drawdown < 18):
        return "允许小幅试探"
    if report:
        return "只观察"
    return "待刷新"


def _derive_data_status(status: str, report: Mapping[str, Any], live_section: Mapping[str, Any]) -> str:
    if status == "ready":
        return "ready"
    if report or live_section.get("last_success"):
        return "cached"
    return "missing"


def _build_key_rules(report: Mapping[str, Any], multi_result: Mapping[str, Any], win_rate: Any, max_drawdown: Any) -> list[str]:
    rules = _rules_from_value(report.get("key_rules") or report.get("discipline_rules"))
    if rules:
        return rules[:MAX_RULES]
    summary_rules = _rules_from_value(multi_result.get("summary"))
    if summary_rules:
        return summary_rules[:MAX_RULES]
    if report:
        return [
            f"胜率：{win_rate if win_rate is not None else '待验证'}",
            f"最大回撤：{max_drawdown if max_drawdown is not None else '待验证'}",
            "仅按已缓存回测摘要判断，不自动跑新回测。",
        ]
    return ["暂无回测缓存；请在高级工具箱手动运行回测后再验证纪律边界。"]


def _build_warnings(report: Mapping[str, Any], check: Mapping[str, Any], max_drawdown: Any) -> list[str]:
    trader_brief = as_mapping(report.get("trader_brief"))
    warnings = []
    warnings.extend(_dedupe_text(trader_brief.get("warnings")))
    warnings.extend(_dedupe_text(report.get("warnings")))
    error = _first_text(check.get("last_error"), check.get("error"))
    if error:
        warnings.append(error)
    if max_drawdown is not None and max_drawdown >= 20:
        warnings.append("历史最大回撤偏高，纪律边界应优先防守。")
    if not report:
        warnings.append("缺少回测缓存；综合中心不会自动跑回测。")
    warnings.append("DeepSeek 未调用；回测解释仍需手动按钮触发。")
    return _dedupe_text(warnings, limit=MAX_WARNINGS)


def build_command_center_discipline_packet(
    state: Any = None,
    live_packet: Any = None,
    target: str = "",
) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    live_section = as_mapping(live.get("discipline"))
    existing = as_mapping(state_map.get("command_center_discipline_packet"))
    existing_target = _first_text(existing.get("target"), existing.get("ticker"))
    if existing.get("status") in {"ready", "partial"} and not (target and existing_target and _ticker_base(existing_target) != _ticker_base(target)):
        win_rate = to_number(existing.get("win_rate"))
        max_drawdown = _normalize_drawdown(existing.get("max_drawdown"))
        sharpe = to_number(existing.get("sharpe"))
        trade_count = to_number(existing.get("trade_count"))
        data_status = _first_text(existing.get("data_status"), default=_derive_data_status(existing.get("status"), existing, live_section))
        return {
            **existing,
            "key_rules": _rules_from_value(existing.get("key_rules")) or ["仅按已缓存纪律 packet 展示。"],
            "warnings": _dedupe_text(existing.get("warnings")) or ["DeepSeek 未调用；回测解释仍需手动按钮触发。"],
            "backtest_status": _first_text(existing.get("backtest_status"), default=_backtest_status_text(existing.get("status"), data_status)),
            "cache_state": data_status,
            "metric_items": as_list(existing.get("metric_items")) or _build_metric_items(win_rate, max_drawdown, sharpe, trade_count),
            "evidence_items": as_list(existing.get("evidence_items")) or [
                {
                    "label": "纪律缓存",
                    "value": _first_text(existing.get("action_state"), default="已读取"),
                    "detail": _first_text(existing.get("summary"), default="仅按已缓存纪律 packet 展示。"),
                    "tone": "ready",
                }
            ],
            "deepseek_called": False,
        }
    report = as_mapping(state_map.get("last_backtest_report"))
    if report and target and report.get("ticker") and _ticker_base(report.get("ticker")) != _ticker_base(target):
        report = {}
    multi_result = as_mapping(state_map.get("last_multi_backtest")) if report else {}
    check = as_mapping(state_map.get("command_center_discipline_check"))
    metrics = as_mapping(report.get("metrics")) or report
    latest_signal = as_mapping(report.get("latest_signal"))
    trader_brief = as_mapping(report.get("trader_brief"))
    win_rate = _first_number(
        metrics.get("round_trip_win_rate"),
        metrics.get("win_rate"),
        metrics.get("win_rate_pct"),
        metrics.get("exit_action_win_rate"),
        check.get("win_rate"),
    )
    max_drawdown = _normalize_drawdown(
        _first_number(metrics.get("max_drawdown_pct"), metrics.get("max_drawdown"), check.get("max_drawdown"))
    )
    sharpe = _first_number(metrics.get("sharpe"), check.get("sharpe"))
    trade_count = _first_number(metrics.get("trade_count"), check.get("trade_count"))
    latest_signal_text = _first_text(
        latest_signal.get("action"),
        trader_brief.get("action"),
        live_section.get("latest_signal"),
        check.get("latest_signal"),
    )
    status = _status_from(report, check, live_section)
    action_state = _derive_action_state(report, check, live_section, win_rate, max_drawdown, latest_signal_text)
    updated_at = _first_text(
        as_mapping(report.get("date_range")).get("end"),
        report.get("updated_at"),
        check.get("checked_at"),
        live_section.get("updated_at"),
    )
    summary = _first_text(
        report.get("summary"),
        check.get("summary"),
        live_section.get("summary"),
        default=(
            f"已读取 {report.get('ticker') or target or '当前标的'} 的旧版回测缓存，动作边界为：{action_state}。"
            if report
            else "暂无回测缓存；点击纪律校验只读取缓存，不自动跑两年回测。"
        ),
    )
    data_status = _derive_data_status(status, report, live_section)
    return {
        "status": status,
        "source": _first_text(report.get("source"), check.get("source"), live_section.get("source"), default="交易纪律实验室回测缓存"),
        "updated_at": updated_at,
        "target": _first_text(target, report.get("ticker"), check.get("target")),
        "ticker": to_text(report.get("ticker")),
        "summary": summary,
        "backtest_status": _backtest_status_text(status, data_status),
        "cache_state": data_status,
        "date_range": _date_range_from(report),
        "action_state": action_state,
        "score": win_rate if win_rate is not None else live_section.get("score"),
        "win_rate": win_rate,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "trade_count": trade_count,
        "latest_signal": latest_signal_text,
        "signal_reason": _first_text(latest_signal.get("reason"), trader_brief.get("plain_summary")),
        "metric_items": _build_metric_items(win_rate, max_drawdown, sharpe, trade_count),
        "evidence_items": _build_evidence_items(report, multi_result, latest_signal_text, action_state, summary),
        "key_rules": _build_key_rules(report, multi_result, win_rate, max_drawdown),
        "warnings": _build_warnings(report, check, max_drawdown),
        "data_status": data_status,
        "backtest_required_text": "回测必须在高级工具箱手动触发；综合中心不会自动跑回测。",
        "deepseek_called": False,
    }
