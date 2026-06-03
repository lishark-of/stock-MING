from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


COVERAGE_LABELS = {
    "market": "市场",
    "quant": "量化",
    "discipline": "纪律",
    "margin_etf": "融资 ETF",
    "next_ticket": "下一票",
    "strategy_execution": "策略执行",
}

COVERAGE_ORDER = (
    "market",
    "quant",
    "discipline",
    "margin_etf",
    "next_ticket",
    "strategy_execution",
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


def _list_text(value: Any, fallback: str) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        items = [_to_text(item) for item in value]
        items = [item for item in items if item]
        return items or [fallback]
    text = _to_text(value)
    return [text] if text else [fallback]


def normalize_decision_status(packet: Any) -> str:
    payload = _as_mapping(packet)
    raw = _to_text(payload.get("status")).lower()
    if raw in {"waiting", "partial", "ready", "failed"}:
        return raw
    return "waiting" if not payload else "ready"


def decision_status_label(packet: Any) -> str:
    return {
        "waiting": "待刷新判断",
        "partial": "部分刷新结论",
        "ready": "综合推演结论",
        "failed": "失败后缓存",
    }.get(normalize_decision_status(packet), "待刷新判断")


def decision_status_tone(packet: Any) -> str:
    return {
        "waiting": "muted",
        "partial": "warning",
        "ready": "success",
        "failed": "danger",
    }.get(normalize_decision_status(packet), "muted")


def decision_action_label(packet: Any) -> str:
    payload = _as_mapping(packet)
    return _to_text(payload.get("overall_action")) or "等待"


def decision_action_tone(packet: Any) -> str:
    action = decision_action_label(packet)
    if any(key in action for key in ["降风险", "禁止", "卖", "减仓", "降低"]):
        return "danger"
    if any(key in action for key in ["小幅进攻", "进攻", "试探"]):
        return "success"
    if any(key in action for key in ["只观察", "等待", "观望"]):
        return "warning"
    return "muted"


def decision_risk_tone(packet: Any) -> str:
    risk = _to_text(_as_mapping(packet).get("risk_level")) or "中"
    if risk == "高":
        return "danger"
    if risk == "低":
        return "success"
    return "warning"


def decision_action_guardrail_text(packet: Any) -> str:
    action = decision_action_label(packet)
    if any(key in action for key in ["小幅进攻", "进攻", "试探"]):
        return "只允许小额试探，禁止追高、一次性重仓或冲动加杠杆。"
    if any(key in action for key in ["降风险", "减仓", "降低", "禁止"]):
        return "优先降低风险暴露、降杠杆并保留现金缓冲。"
    if any(key in action for key in ["只观察", "等待", "观望"]):
        return "今天不是必须交易，先等待验证条件出现。"
    return "任何动作都必须先过纪律、预算和风险线校验。"


def decision_user_boundary_text(packet: Any) -> str:
    del packet
    return "本卡不是荐股或自动交易指令，不保证收益；DeepSeek 只解释当前 packet，不替你决定仓位。"


def decision_evidence_summary_text(packet: Any) -> str:
    coverage_items = build_data_coverage_items(packet)
    ready = [item["label"] for item in coverage_items if item["state"] == "ready"]
    cached = [item["label"] for item in coverage_items if item["state"] == "cached"]
    missing = [item["label"] for item in coverage_items if item["state"] == "missing"]
    parts = [
        f"已刷新：{'、'.join(ready) if ready else '无'}",
        f"使用缓存：{'、'.join(cached) if cached else '无'}",
        f"待验证：{'、'.join(missing) if missing else '无'}",
    ]
    return "｜".join(parts)


def decision_deepseek_text(packet: Any) -> str:
    return "DeepSeek：已调用" if bool(_as_mapping(packet).get("deepseek_called")) else "DeepSeek：未调用"


def decision_updated_text(packet: Any) -> str:
    return _to_text(_as_mapping(packet).get("updated_at")) or "暂无"


def decision_source_text(packet: Any) -> str:
    return _to_text(_as_mapping(packet).get("source")) or "command_center_decision_engine"


def _coverage_tone(state: str) -> str:
    if state == "ready":
        return "success"
    if state == "cached":
        return "warning"
    return "muted"


def build_data_coverage_items(packet: Any) -> list[dict]:
    coverage = _as_mapping(_as_mapping(packet).get("data_coverage"))
    items = []
    for key in COVERAGE_ORDER:
        state = _to_text(coverage.get(key)) or "missing"
        if state not in {"missing", "cached", "ready"}:
            state = "missing"
        items.append(
            {
                "key": key,
                "label": COVERAGE_LABELS.get(key, key),
                "state": state,
                "tone": _coverage_tone(state),
            }
        )
    return items


def _limited_join(items: Any, fallback: str = "无", limit: int = 2) -> str:
    values = [_to_text(item) for item in (items or [])]
    values = [item for item in values if item]
    if not values:
        return fallback
    visible = values[:limit]
    suffix = f" 等 {len(values)} 项" if len(values) > limit else ""
    return "、".join(visible) + suffix


def _a_share_data_basis_tone(readiness: str, summary: str = "") -> str:
    if any(key in readiness for key in ["可进入", "可用", "已可用"]):
        return "success"
    if any(key in readiness for key in ["阻断", "受限", "权限"]):
        return "danger"
    if any(key in readiness for key in ["谨慎", "暂无数据", "缓存"]):
        return "warning"
    if any(key in readiness for key in ["待手动", "待检测", "待验证"]):
        return "muted"
    text = f"{readiness} {summary}"
    if any(key in text for key in ["阻断", "受限", "权限"]):
        return "danger"
    if any(key in text for key in ["谨慎", "暂无数据", "缓存"]):
        return "warning"
    if any(key in text for key in ["待手动", "待检测", "待验证"]):
        return "muted"
    if any(key in text for key in ["可进入", "可用", "已可用"]):
        return "success"
    return "muted"


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_a_share_data_basis_items(a_share_data_console: Any = None) -> list[dict]:
    console = _as_mapping(a_share_data_console)
    if not console:
        return []

    readiness = _to_text(console.get("decision_readiness_label")) or _to_text(console.get("headline")) or "待检测"
    summary = _to_text(console.get("summary"))
    items = [
        {
            "label": "A股数据能力",
            "value": readiness,
            "tone": _a_share_data_basis_tone(readiness, summary),
            "summary": summary,
        }
    ]

    groups = {
        _to_text(group.get("key")): _as_mapping(group)
        for group in (console.get("groups") or [])
        if _as_mapping(group)
    }
    group_specs = [
        ("permission_denied", "受限", "danger"),
        ("stale_or_empty", "暂无数据", "warning"),
        ("manual_required", "待手动", "muted"),
        ("available", "可用", "success"),
    ]
    for key, label, fallback_tone in group_specs:
        group = groups.get(key) or {}
        count = _safe_int(group.get("count"))
        if count <= 0:
            continue
        tone = _to_text(group.get("tone")) or fallback_tone
        if tone == "failed":
            tone = "danger"
        elif tone == "stale":
            tone = "warning"
        elif tone == "ready":
            tone = "success"
        items.append(
            {
                "label": label,
                "value": _limited_join(group.get("items"), fallback=_to_text(group.get("summary")) or label),
                "tone": tone,
                "count": count,
            }
        )

    return items[:5]


def build_a_share_data_basis_summary_text(a_share_data_console: Any = None) -> str:
    console = _as_mapping(a_share_data_console)
    if not console:
        return ""
    readiness = _to_text(console.get("decision_readiness_label")) or _to_text(console.get("headline")) or "待检测"
    summary = _to_text(console.get("summary"))
    return f"{readiness}｜{summary}" if summary else readiness


def build_decision_evidence_chain_items(
    analysis_method_packet: Any = None,
    evidence_radar_packet: Any = None,
    a_share_data_console: Any = None,
) -> list[dict]:
    analysis = _as_mapping(analysis_method_packet)
    market = _to_text(analysis.get("market")) or "市场类型待确认"
    items = [{"label": "市场类型", "value": market, "tone": "success" if market in {"A股", "美股", "ETF"} else "muted"}]
    methods = [_as_mapping(item) for item in (analysis.get("methods") or []) if _as_mapping(item)]
    passed = [item.get("name") for item in methods if item.get("status") == "通过"]
    pending = [item.get("name") for item in methods if item.get("status") == "待验证"]
    not_applicable = [item.get("name") for item in methods if item.get("status") == "不适用"]
    if passed:
        items.append({"label": "已通过", "value": "、".join(passed[:2]), "tone": "success"})
    else:
        items.append({"label": "已通过", "value": "暂无", "tone": "muted"})
    if pending:
        items.append({"label": "待验证", "value": "、".join(pending[:2]), "tone": "warning"})
    if not_applicable:
        not_applicable_item = {"label": "不适用", "value": "、".join(not_applicable[:2]), "tone": "muted"}
    else:
        not_applicable_item = None
    a_share_basis = build_a_share_data_basis_items(a_share_data_console)
    if a_share_basis:
        items.append(a_share_basis[0])
    evidence = _as_mapping(evidence_radar_packet)
    if evidence:
        blockers = len(evidence.get("blocker_items") or [])
        support = len(evidence.get("support_items") or [])
        cached = len(evidence.get("cached_items") or [])
        missing = len(evidence.get("missing_items") or [])
        if blockers:
            items.append({"label": "阻断证据", "value": f"{blockers} 项", "tone": "danger"})
        if support:
            items.append({"label": "支持证据", "value": f"{support} 项", "tone": "success"})
        if cached or missing:
            items.append({"label": "待复核证据", "value": f"缓存 {cached}｜缺失 {missing}", "tone": "warning"})
    if not_applicable_item:
        items.append(not_applicable_item)
    if len(items) < 5:
        source = _to_text(analysis.get("source")) or "rule-based market profile"
        items.append({"label": "来源", "value": source, "tone": "muted"})
    return items[:5]


def build_decision_summary_view_model(
    packet: Any,
    analysis_method_packet: Any = None,
    evidence_radar_packet: Any = None,
    a_share_data_console: Any = None,
) -> dict:
    payload = _as_mapping(packet)
    status = normalize_decision_status(payload)
    action = decision_action_label(payload)
    risk = _to_text(payload.get("risk_level")) or "中"
    reason = _to_text(payload.get("reason_summary")) or "基础数据未刷新，先等待或点击刷新今日基础数据。"
    stale_note = (
        "当前为待刷新/缓存判断，不是完整实时结论。"
        if status in {"waiting", "partial", "failed"}
        else "当前为综合推演结论，仍需按纪律验证执行。"
    )
    return {
        "status": status,
        "status_label": decision_status_label(payload),
        "status_tone": decision_status_tone(payload),
        "action_label": action,
        "action_tone": decision_action_tone(payload),
        "risk_label": risk,
        "risk_tone": decision_risk_tone(payload),
        "market_text": _to_text(payload.get("market_bias")) or "未刷新",
        "position_text": _to_text(payload.get("position_mode")) or "空仓等待",
        "margin_text": _to_text(payload.get("margin_mode")) or "不使用融资",
        "etf_text": _to_text(payload.get("etf_priority")) or "待刷新",
        "next_ticket_text": _to_text(payload.get("next_ticket_priority")) or "待刷新",
        "reason_summary": reason,
        "action_guardrail": decision_action_guardrail_text(payload),
        "user_boundary_text": decision_user_boundary_text(payload),
        "evidence_summary_text": decision_evidence_summary_text(payload),
        "evidence_chain_items": build_decision_evidence_chain_items(
            analysis_method_packet,
            evidence_radar_packet=evidence_radar_packet,
            a_share_data_console=a_share_data_console,
        ),
        "a_share_evidence_summary_text": _to_text(_as_mapping(evidence_radar_packet).get("decision_summary")),
        "a_share_data_basis_items": build_a_share_data_basis_items(a_share_data_console),
        "a_share_data_basis_summary_text": build_a_share_data_basis_summary_text(a_share_data_console),
        "stale_note": stale_note,
        "must_not_do_items": _list_text(payload.get("must_not_do"), "暂无新增禁止动作，但仍需遵守交易纪律。"),
        "validation_items": _list_text(payload.get("next_validation_conditions"), "等待基础数据刷新后再生成验证条件。"),
        "coverage_items": build_data_coverage_items(payload),
        "deepseek_text": decision_deepseek_text(payload),
        "updated_text": decision_updated_text(payload),
        "source_text": decision_source_text(payload),
        "empty_message": "当前为待刷新/缓存判断，不是完整实时结论。",
    }
