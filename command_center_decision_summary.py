from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_data_health_ledger import build_data_health_impact_summary
from command_center_projection import build_projection_confidence_summary


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


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


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


def _a_share_fact_recovery_tone(summary: Mapping[str, Any]) -> str:
    blocked = _safe_int(summary.get("blocked_count"))
    waiting = _safe_int(summary.get("waiting_count"))
    recovered = _safe_int(summary.get("recovered_count"))
    total = _safe_int(summary.get("total_count"))
    if blocked:
        return "danger"
    if waiting:
        return "warning"
    if total and recovered >= total:
        return "success"
    return "muted"


def build_a_share_fact_recovery_basis_item(a_share_fact_recovery_summary: Any = None) -> dict:
    summary = _as_mapping(a_share_fact_recovery_summary)
    if not summary:
        return {}
    text = _to_text(summary.get("summary"))
    if not text:
        total = _safe_int(summary.get("total_count")) or 5
        text = (
            f"A股事实 {total} 项：已回流 {_safe_int(summary.get('recovered_count'))}"
            f"｜仍受限 {_safe_int(summary.get('blocked_count'))}"
            f"｜待验证 {_safe_int(summary.get('waiting_count'))}"
        )
    return {
        "label": "A股事实回流",
        "value": text,
        "tone": _a_share_fact_recovery_tone(summary),
        "summary": text,
        "next_action": _to_text(summary.get("next_action")),
    }


def build_a_share_fact_recovery_summary_text(a_share_fact_recovery_summary: Any = None) -> str:
    item = build_a_share_fact_recovery_basis_item(a_share_fact_recovery_summary)
    return _to_text(item.get("summary"))


def _latest_recovery_tone(status: str) -> str:
    if status == "recovered":
        return "success"
    if status == "blocked":
        return "danger"
    if status == "waiting":
        return "warning"
    return "muted"


def build_latest_recovery_result_basis_item(latest_recovery_result_notice: Any = None) -> dict:
    notice = _as_mapping(latest_recovery_result_notice)
    if not notice:
        return {}
    status = _to_text(notice.get("status")) or "waiting"
    label = _to_text(notice.get("label")) or "数据恢复"
    message = _to_text(notice.get("message")) or "已更新本地恢复状态。"
    return {
        "label": "最近恢复",
        "value": f"{label}｜{message}",
        "tone": _latest_recovery_tone(status),
        "summary": message,
        "next_action": _to_text(notice.get("next_action")),
        "writes_packet": _to_text(notice.get("writes_packet")),
        "external_call_policy": _to_text(notice.get("external_call_policy")) or "not_triggered",
    }


def build_latest_recovery_result_summary_text(latest_recovery_result_notice: Any = None) -> str:
    item = build_latest_recovery_result_basis_item(latest_recovery_result_notice)
    return _to_text(item.get("value"))


def _group_count(group: Mapping[str, Any]) -> int:
    raw_count = group.get("count")
    try:
        return max(0, int(float(raw_count)))
    except Exception:
        return len(_as_list(group.get("items")))


def _fallback_evidence_status_groups(evidence_radar_packet: Mapping[str, Any]) -> list[dict]:
    group_configs = [
        ("recovered", "已回流", "ready", evidence_radar_packet.get("support_items")),
        ("blocked", "仍受限", "failed", evidence_radar_packet.get("blocker_items")),
        ("cached", "使用缓存", "stale", evidence_radar_packet.get("cached_items")),
        ("manual", "待手动", "missing", evidence_radar_packet.get("missing_items")),
    ]
    result = []
    for key, label, tone, raw_items in group_configs:
        items = [_as_mapping(item) for item in _as_list(raw_items) if _as_mapping(item)]
        labels = [_to_text(item.get("label")) for item in items]
        result.append(
            {
                "key": key,
                "label": label,
                "tone": tone,
                "count": len(items),
                "labels_text": "、".join([label for label in labels if label][:4]) or "无",
                "items": items,
                "deepseek_called": False,
            }
        )
    return result


def _first_evidence_item(evidence: Mapping[str, Any], key: str) -> tuple[str, dict]:
    state_sources = [
        ("supporting", evidence.get("support_items")),
        ("blocked", evidence.get("blocker_items")),
        ("cached", evidence.get("cached_items")),
        ("missing", evidence.get("missing_items")),
    ]
    for state, raw_items in state_sources:
        for item in _as_list(raw_items):
            payload = _as_mapping(item)
            if _to_text(payload.get("key")) == key:
                return state, payload
    return "", {}


def _legacy_evidence_state_label(state: str) -> str:
    return {
        "supporting": "已验证",
        "blocked": "仍受限",
        "cached": "使用缓存",
        "missing": "待验证",
    }.get(state, "待验证")


def _legacy_evidence_tone(states: list[str]) -> str:
    if any(state == "blocked" for state in states):
        return "danger"
    if any(state in {"cached", "missing"} for state in states):
        return "warning"
    if states:
        return "success"
    return "muted"


def build_legacy_a_share_evidence_basis_item(evidence_radar_packet: Any = None) -> dict:
    evidence = _as_mapping(evidence_radar_packet)
    if not evidence:
        return {}
    configs = [
        ("limit_emotion", "涨跌停/情绪", "追高/情绪边界"),
        ("chip_radar", "筹码/胜率", "压力位/胜率口径"),
    ]
    parts = []
    states = []
    summaries = []
    for key, label, role in configs:
        state, item = _first_evidence_item(evidence, key)
        if not state:
            continue
        state_label = _legacy_evidence_state_label(state)
        headline = _to_text(item.get("headline") or item.get("status_label") or item.get("evidence_label") or item.get("metric"))
        parts.append(f"{label}{state_label}")
        states.append(state)
        summaries.append(f"{label}用于验证{role}：{headline or state_label}")
    if not parts:
        return {}
    if any(state == "blocked" for state in states):
        guardrail = "旧能力仍受限时，今日总动作不能把情绪、筹码或胜率写成已验证依据。"
    elif any(state in {"cached", "missing"} for state in states):
        guardrail = "旧能力缓存/待验证时，今日总动作只能保留观察或谨慎试探。"
    else:
        guardrail = "旧能力已回流，可增强依据链；仍需价格纪律和仓位规则共同确认。"
    return {
        "label": "旧能力证据",
        "value": "｜".join(parts),
        "tone": _legacy_evidence_tone(states),
        "summary": "；".join(summaries),
        "guardrail": guardrail,
        "states": states,
        "deepseek_called": False,
    }


def build_a_share_evidence_group_basis_item(evidence_radar_packet: Any = None) -> dict:
    evidence = _as_mapping(evidence_radar_packet)
    if not evidence:
        return {}
    groups = [_as_mapping(item) for item in _as_list(evidence.get("evidence_status_groups")) if _as_mapping(item)]
    if not groups:
        groups = _fallback_evidence_status_groups(evidence)
    counts = {group.get("key"): _group_count(group) for group in groups}
    if not any(counts.values()):
        return {}
    recovered = counts.get("recovered", 0)
    blocked = counts.get("blocked", 0)
    cached = counts.get("cached", 0)
    manual = counts.get("manual", 0)
    tone = "danger" if blocked else "warning" if cached or manual else "success" if recovered else "muted"
    summary_parts = []
    for group in groups:
        count = _group_count(group)
        if not count:
            continue
        label = _to_text(group.get("label")) or "证据分组"
        labels_text = _to_text(group.get("labels_text")) or "、".join(
            _to_text(_as_mapping(item).get("label"))
            for item in _as_list(group.get("items"))[:3]
            if _as_mapping(item)
        )
        summary_parts.append(f"{label}：{labels_text or f'{count} 项'}")
    value = f"已回流 {recovered}｜仍受限 {blocked}｜缓存 {cached}｜待手动 {manual}"
    if blocked:
        guardrail = "仍受限证据未恢复前，不支持加仓、追高或加融资。"
    elif cached or manual:
        guardrail = "缓存和待手动证据只能辅助观察，执行前必须复核日期、来源和回流 packet。"
    else:
        guardrail = "已回流证据可进入证据链，但仍需价格纪律和仓位规则共同确认。"
    return {
        "label": "A股证据分组",
        "value": value,
        "tone": tone,
        "summary": "；".join(summary_parts) or value,
        "guardrail": guardrail,
        "groups": groups,
        "deepseek_called": False,
    }


def build_a_share_evidence_group_summary_text(evidence_radar_packet: Any = None) -> str:
    item = build_a_share_evidence_group_basis_item(evidence_radar_packet)
    if not item:
        return "A股证据分组待生成"
    return f"{item['value']}｜{item['guardrail']}"


def build_decision_evidence_chain_items(
    analysis_method_packet: Any = None,
    projection_packet: Any = None,
    evidence_radar_packet: Any = None,
    a_share_data_console: Any = None,
    data_health_ledger: Any = None,
    a_share_fact_recovery_summary: Any = None,
    latest_recovery_result_notice: Any = None,
) -> list[dict]:
    analysis = _as_mapping(analysis_method_packet)
    market = _to_text(analysis.get("market")) or "市场类型待确认"
    items = [{"label": "市场类型", "value": market, "tone": "success" if market in {"A股", "美股", "ETF"} else "muted"}]
    projection_confidence = build_projection_confidence_summary(projection_packet)
    if projection_confidence.get("status") != "missing":
        items.append(
            {
                "label": "趋势推演",
                "value": f"{projection_confidence['label']}｜{projection_confidence['confidence_label']}",
                "tone": projection_confidence["tone"],
                "summary": projection_confidence["guardrail"],
            }
        )
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
    health_impact = build_data_health_impact_summary(data_health_ledger, market_type=market)
    if health_impact.get("status") != "missing":
        items.append(
            {
                "label": "接口健康",
                "value": health_impact["label"],
                "tone": health_impact["tone"],
                "summary": health_impact["decision_impact"],
                "blocked_count": health_impact["blocked_count"],
                "manual_count": health_impact["manual_count"],
                "stale_count": health_impact["stale_count"],
            }
        )
    fact_recovery_basis = build_a_share_fact_recovery_basis_item(a_share_fact_recovery_summary)
    if fact_recovery_basis:
        items.append(fact_recovery_basis)
    latest_recovery_basis = build_latest_recovery_result_basis_item(latest_recovery_result_notice)
    if latest_recovery_basis:
        items.append(latest_recovery_basis)
    evidence = _as_mapping(evidence_radar_packet)
    if evidence:
        legacy_evidence_basis = build_legacy_a_share_evidence_basis_item(evidence)
        if legacy_evidence_basis:
            items.append(legacy_evidence_basis)
        radar_card = _as_mapping(evidence.get("radar_card"))
        if radar_card:
            items.append(
                {
                    "label": "A股证据雷达",
                    "value": f"{_to_text(radar_card.get('status_label')) or '待验证'}｜{_to_text(radar_card.get('confidence_gate')) or '不可验证'}",
                    "tone": _to_text(radar_card.get("tone")) or "warning",
                    "summary": _to_text(radar_card.get("decision_guardrail")),
                }
            )
        evidence_group_basis = build_a_share_evidence_group_basis_item(evidence)
        if evidence_group_basis:
            items.append(evidence_group_basis)
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
    return items[:6]


def build_decision_summary_view_model(
    packet: Any,
    analysis_method_packet: Any = None,
    projection_packet: Any = None,
    evidence_radar_packet: Any = None,
    a_share_data_console: Any = None,
    data_health_ledger: Any = None,
    a_share_fact_recovery_summary: Any = None,
    latest_recovery_result_notice: Any = None,
) -> dict:
    payload = _as_mapping(packet)
    analysis = _as_mapping(analysis_method_packet)
    market = _to_text(analysis.get("market"))
    status = normalize_decision_status(payload)
    action = decision_action_label(payload)
    risk = _to_text(payload.get("risk_level")) or "中"
    reason = _to_text(payload.get("reason_summary")) or "基础数据未刷新，先等待或点击刷新今日基础数据。"
    stale_note = (
        "当前为待刷新/缓存判断，不是完整实时结论。"
        if status in {"waiting", "partial", "failed"}
        else "当前为综合推演结论，仍需按纪律验证执行。"
    )
    projection_confidence = build_projection_confidence_summary(projection_packet)
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
            projection_packet=projection_packet,
            evidence_radar_packet=evidence_radar_packet,
            a_share_data_console=a_share_data_console,
            data_health_ledger=data_health_ledger,
            a_share_fact_recovery_summary=a_share_fact_recovery_summary,
            latest_recovery_result_notice=latest_recovery_result_notice,
        ),
        "projection_confidence_summary": projection_confidence,
        "data_health_impact": build_data_health_impact_summary(data_health_ledger, market_type=market),
        "a_share_evidence_radar_card": _as_mapping(_as_mapping(evidence_radar_packet).get("radar_card")),
        "a_share_evidence_summary_text": _to_text(_as_mapping(evidence_radar_packet).get("decision_summary")),
        "a_share_evidence_group_basis_item": build_a_share_evidence_group_basis_item(evidence_radar_packet),
        "a_share_evidence_group_summary_text": build_a_share_evidence_group_summary_text(evidence_radar_packet),
        "legacy_a_share_evidence_basis_item": build_legacy_a_share_evidence_basis_item(evidence_radar_packet),
        "a_share_data_basis_items": build_a_share_data_basis_items(a_share_data_console),
        "a_share_data_basis_summary_text": build_a_share_data_basis_summary_text(a_share_data_console),
        "a_share_fact_recovery_basis_item": build_a_share_fact_recovery_basis_item(a_share_fact_recovery_summary),
        "a_share_fact_recovery_summary_text": build_a_share_fact_recovery_summary_text(a_share_fact_recovery_summary),
        "latest_recovery_result_basis_item": build_latest_recovery_result_basis_item(latest_recovery_result_notice),
        "latest_recovery_result_summary_text": build_latest_recovery_result_summary_text(latest_recovery_result_notice),
        "stale_note": stale_note,
        "must_not_do_items": _list_text(payload.get("must_not_do"), "暂无新增禁止动作，但仍需遵守交易纪律。"),
        "validation_items": _list_text(payload.get("next_validation_conditions"), "等待基础数据刷新后再生成验证条件。"),
        "coverage_items": build_data_coverage_items(payload),
        "deepseek_text": decision_deepseek_text(payload),
        "updated_text": decision_updated_text(payload),
        "source_text": decision_source_text(payload),
        "empty_message": "当前为待刷新/缓存判断，不是完整实时结论。",
    }
