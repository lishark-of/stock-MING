from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


DATA_STATUS_LABELS = {
    "quant": "量化",
    "backtest": "纪律/回测",
    "live_packet": "综合包",
}

DEFAULT_PATHS = (
    {"name": "乐观路径", "condition": "数据补齐且市场、量化、纪律转为同向。", "action": "只允许小幅试探。"},
    {"name": "中性路径", "condition": "信号继续分歧或缺少新增验证。", "action": "等待或只观察。"},
    {"name": "防守路径", "condition": "纪律信号转弱、回撤扩大或数据失败。", "action": "降风险。"},
)


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip()


def _money_text(value: Any) -> str:
    if value in [None, ""]:
        return "暂无"
    try:
        if isinstance(value, str):
            number = float(value.replace(",", "").replace("¥", "").strip())
        else:
            number = float(value)
        return f"¥{number:,.0f}"
    except Exception:
        return _to_text(value) or "暂无"


def normalize_strategy_status(packet: Any) -> str:
    payload = _as_mapping(packet)
    raw = _to_text(payload.get("status")).lower()
    if raw in {"waiting", "ready", "failed"}:
        return raw
    if raw in {"ok", "completed", "complete", "success"}:
        return "ready"
    return "waiting" if not payload else "ready"


def strategy_status_label(packet: Any) -> str:
    return {
        "waiting": "待生成",
        "ready": "策略建议已生成",
        "failed": "失败后缓存",
    }.get(normalize_strategy_status(packet), "待生成")


def strategy_status_tone(packet: Any) -> str:
    return {
        "waiting": "muted",
        "ready": "success",
        "failed": "danger",
    }.get(normalize_strategy_status(packet), "muted")


def strategy_action_label(packet: Any) -> str:
    payload = _as_mapping(packet)
    action = _to_text(payload.get("action") or payload.get("overall_action"))
    mapping = {
        "小幅试探": "可轻仓试探",
        "小幅进攻": "可轻仓试探",
        "持仓观察": "可持有",
        "允许进攻": "可加仓",
    }
    return mapping.get(action, action or "等待")


def strategy_action_tone(packet: Any) -> str:
    action = strategy_action_label(packet)
    if any(key in action for key in ["降风险", "减仓", "退出", "止损", "风险"]):
        return "danger"
    if any(key in action for key in ["等待", "观察", "尚未生成"]):
        return "warning"
    return "success"


def strategy_confidence_tone(packet: Any) -> str:
    confidence = _to_text(_as_mapping(packet).get("confidence")) or "低"
    if confidence == "高":
        return "success"
    if confidence == "中":
        return "warning"
    return "muted"


def build_strategy_path_items(packet: Any) -> list[dict]:
    payload = _as_mapping(packet)
    paths = payload.get("next_5_10_day_paths") or payload.get("paths") or payload.get("scenario_paths") or []
    if not isinstance(paths, list):
        paths = []
    source = paths[:3] if paths else list(DEFAULT_PATHS)
    names = ["乐观路径", "中性路径", "防守路径"]
    items = []
    for index, item in enumerate(source[:3]):
        path = _as_mapping(item)
        if path:
            items.append(
                {
                    "name": _to_text(path.get("name")) or names[index],
                    "condition": _to_text(path.get("condition") or path.get("trigger")) or "等待验证条件。",
                    "action": _to_text(path.get("action") or path.get("advice")) or "只观察。",
                }
            )
        else:
            items.append({"name": names[index], "condition": _to_text(item) or "等待验证。", "action": "按纪律执行。"})
    return items


def build_strategy_condition_items(packet: Any) -> dict:
    payload = _as_mapping(packet)
    return {
        "add": _to_text(payload.get("add_condition")) or "等待量化、纪律和市场至少两项同向后再考虑。",
        "reduce": _to_text(payload.get("reduce_condition")) or "触发止损、减仓或风险预算失效时优先降低暴露。",
        "invalidation": _to_text(payload.get("invalidation_condition")) or "市场环境转弱或纪律信号反向时，本轮建议失效。",
    }


def build_strategy_discipline_items(packet: Any) -> list[dict]:
    payload = _as_mapping(packet)
    discipline = _as_mapping(payload.get("discipline_check"))
    warnings = discipline.get("warnings") or payload.get("warnings") or []
    action = strategy_action_label(payload)
    data_status = _as_mapping(payload.get("data_status"))
    lines = [
        ("是否违反交易纪律", "待确认" if discipline.get("status") in [None, "", "missing"] else ("需复核" if warnings else "未发现明确违反")),
        ("是否需要等待确认", "是" if action in {"等待", "只观察", "尚未生成"} else "按条件执行"),
        ("纪律状态", _to_text(discipline.get("status")) or "missing"),
        ("最新信号", _to_text(discipline.get("latest_signal")) or "暂无"),
        ("胜率", _to_text(discipline.get("win_rate")) or "暂无"),
        ("最大回撤", _to_text(discipline.get("max_drawdown")) or "暂无"),
        ("是否禁止追高", "是"),
        ("是否禁止自动重仓", "是"),
    ]
    if (_to_text(payload.get("confidence")) or "低") == "低" or "missing" in set(_to_text(value) for value in data_status.values()):
        lines.append(("数据覆盖", "不足 / 建议谨慎"))
    return [{"label": label, "value": value} for label, value in lines]


def build_strategy_risk_budget_items(packet: Any) -> list[dict]:
    payload = _as_mapping(packet)
    budget = _as_mapping(payload.get("risk_budget"))
    position_mode = _to_text(budget.get("position_mode") or payload.get("position_mode")) or "待确认"
    position_advice = _to_text(payload.get("position_advice")) or f"{position_mode}：等待策略执行建议补齐。"
    items = [
        {"label": "仓位建议", "value": position_advice},
        {"label": "当前建议仓位", "value": position_mode},
        {"label": "最大风险预算", "value": _money_text(budget.get("max_add_amount"))},
        {"label": "现金缓冲", "value": _money_text(budget.get("cash_buffer"))},
    ]
    financing = _to_text(budget.get("margin_mode") or budget.get("financing_advice") or payload.get("margin_mode") or payload.get("financing_advice"))
    if financing:
        items.append({"label": "融资建议", "value": financing})
    return items[:5]


def build_strategy_data_status_items(packet: Any) -> list[dict]:
    data_status = _as_mapping(_as_mapping(packet).get("data_status"))
    return [
        {"key": key, "label": label, "state": _to_text(data_status.get(key)) or "missing"}
        for key, label in DATA_STATUS_LABELS.items()
    ]


def _warning_items(packet: Mapping[str, Any]) -> list[str]:
    discipline = _as_mapping(packet.get("discipline_check"))
    warnings = [_to_text(item) for item in (discipline.get("warnings") or packet.get("warnings") or [])]
    warnings = [item for item in warnings if item]
    errors = packet.get("errors") or []
    if isinstance(errors, (list, tuple)):
        for item in errors[:3]:
            payload = _as_mapping(item)
            if payload:
                warnings.append(f"{_to_text(payload.get('module')) or '模块'}：{_to_text(payload.get('message') or payload.get('error')) or '未知错误'}")
            else:
                text = _to_text(item)
                if text:
                    warnings.append(text)
    if packet.get("stale"):
        warnings.append("当前展示为上次成功结果。")
    if packet.get("last_error"):
        warnings.append(f"上次生成失败：{_to_text(packet.get('last_error'))}")
    if packet.get("last_success") and not packet.get("stale"):
        warnings.append("已有上次成功结果可回退。")
    return warnings[:6] or ["暂无新增异常；仍需遵守不追高、不自动重仓。"]


def build_strategy_summary_view_model(packet: Any) -> dict:
    payload = _as_mapping(packet)
    is_empty = not bool(payload)
    action = "尚未生成" if is_empty else strategy_action_label(payload)
    confidence = "待生成" if is_empty else (_to_text(payload.get("confidence")) or "低")
    summary = _to_text(payload.get("summary")) or "尚未生成策略执行建议。点击按钮后只读取缓存、量化摘要和纪律结果，不调用 DeepSeek，不跑回测。"
    return {
        "status": normalize_strategy_status(payload),
        "status_label": strategy_status_label(payload),
        "status_tone": strategy_status_tone(payload),
        "action_label": action,
        "action_tone": strategy_action_tone({"action": action}),
        "confidence_label": confidence,
        "confidence_tone": strategy_confidence_tone({"confidence": confidence}),
        "summary": summary,
        "position_advice": _to_text(payload.get("position_advice")) or "等待策略执行建议补齐。",
        "conditions": build_strategy_condition_items(payload),
        "path_items": build_strategy_path_items(payload),
        "discipline_items": build_strategy_discipline_items(payload),
        "risk_budget_items": build_strategy_risk_budget_items(payload),
        "data_status_items": build_strategy_data_status_items(payload),
        "warning_items": _warning_items(payload),
        "risk_label": _to_text(_as_mapping(payload.get("risk_budget")).get("risk_level")) or "未知",
        "deepseek_text": "DeepSeek：已调用" if bool(payload.get("deepseek_called")) else "DeepSeek：未调用",
        "updated_text": _to_text(payload.get("updated_at")) or "暂无",
        "source_text": _to_text(payload.get("source")) or "strategy_execution_service / session_state cache",
        "last_error_text": _to_text(payload.get("last_error")),
        "empty_message": "尚未生成策略执行建议。",
    }
