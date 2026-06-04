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
    detail_items = build_a_share_fact_recovery_detail_items(summary)
    focus_text = "；".join(_to_text(item.get("value")) for item in detail_items[:2] if _to_text(item.get("value")))
    guardrail = (
        _to_text(summary.get("decision_guardrail"))
        or "A股事实未完全回流前，今日总动作不能把缺口写成已验证依据。"
    )
    return {
        "label": "A股事实回流",
        "value": text,
        "tone": _a_share_fact_recovery_tone(summary),
        "summary": text,
        "focus_text": focus_text,
        "guardrail": guardrail,
        "detail_items": detail_items,
        "next_action": _to_text(summary.get("next_action")),
    }


def _data_capability_brief_tone(brief: Mapping[str, Any]) -> str:
    status = _to_text(brief.get("status"))
    tone = _to_text(brief.get("tone"))
    if status == "blocked" or tone in {"failed", "danger"}:
        return "danger"
    if status == "partial" or tone in {"stale", "warning"}:
        return "warning"
    if status == "ready" or tone in {"ready", "success"}:
        return "success"
    return "muted"


def build_data_capability_brief_basis_item(data_capability_brief: Any = None) -> dict:
    brief = _as_mapping(data_capability_brief)
    if not brief:
        return {}
    headline = _to_text(brief.get("headline")) or "数据能力待检测"
    trust_label = _to_text(brief.get("trust_label"))
    summary = _to_text(brief.get("summary"))
    value = f"{headline}｜{trust_label}" if trust_label else headline
    guardrail = (
        _to_text(brief.get("guardrail"))
        or "数据能力未确认前，今日总动作只能作为待验证快照。"
    )
    next_action = _to_text(brief.get("next_action"))
    return {
        "label": "数据能力",
        "value": value,
        "tone": _data_capability_brief_tone(brief),
        "summary": summary or value,
        "guardrail": guardrail,
        "next_action": next_action,
        "status": _to_text(brief.get("status")) or "missing",
        "external_call_policy": _to_text(brief.get("external_call_policy")) or "not_triggered",
        "deepseek_called": False,
    }


def build_data_capability_brief_summary_text(data_capability_brief: Any = None) -> str:
    item = build_data_capability_brief_basis_item(data_capability_brief)
    if not item:
        return ""
    summary = _to_text(item.get("summary"))
    return f"{item['value']}｜{summary}" if summary and summary != item["value"] else item["value"]


def _fact_recovery_detail_tone(state: str) -> str:
    if state == "recovered":
        return "success"
    if state == "blocked":
        return "danger"
    if state == "waiting":
        return "warning"
    return "muted"


def _fact_recovery_detail_label(state: str) -> str:
    return {
        "recovered": "已回流事实",
        "blocked": "受限事实",
        "waiting": "待验证事实",
    }.get(state, "A股事实")


def _fact_recovery_detail_guardrail(state: str, labels: str) -> str:
    target = labels or "A股事实"
    if state == "recovered":
        return f"{target} 可进入依据链，但仍需价格、纪律和仓位共同确认。"
    if state == "blocked":
        return f"{target} 仍受限，不能支持加仓、追高、加融资或把风险写成已排除。"
    return f"{target} 待验证，只能保留安全空态或低置信度解释。"


def build_a_share_fact_recovery_detail_items(a_share_fact_recovery_summary: Any = None) -> list[dict]:
    summary = _as_mapping(a_share_fact_recovery_summary)
    items = [_as_mapping(item) for item in _as_list(summary.get("items")) if _as_mapping(item)]
    if not items:
        return []
    detail_items = []
    for state in ("blocked", "waiting", "recovered"):
        rows = [
            item
            for item in items
            if _to_text(item.get("recovery_state")).lower() == state
        ]
        if not rows:
            continue
        labels = "、".join(_to_text(item.get("label")) for item in rows[:3] if _to_text(item.get("label")))
        root_causes = "、".join(
            _to_text(item.get("root_cause_label"))
            for item in rows[:3]
            if _to_text(item.get("root_cause_label"))
        )
        value = labels or _fact_recovery_detail_label(state)
        if root_causes and state != "recovered":
            value = f"{value}｜{root_causes}"
        detail_items.append(
            {
                "key": f"a_share_fact_{state}",
                "label": _fact_recovery_detail_label(state),
                "value": value,
                "tone": _fact_recovery_detail_tone(state),
                "guardrail": _fact_recovery_detail_guardrail(state, labels),
                "count": len(rows),
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            }
        )
    return detail_items[:3]


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


def _recovery_impact_basis_tone(levels: list[str], timeline_status: str = "") -> str:
    if any(level in {"blocks_position_increase", "blocks_candidate_execution", "blocks_strategy_validation"} for level in levels):
        return "danger"
    if any(level in {"requires_review", "confidence_only"} for level in levels):
        return "warning"
    if levels and all(level == "restored" for level in levels):
        return "success"
    if timeline_status == "blocked":
        return "danger"
    if timeline_status in {"cached", "waiting"}:
        return "warning"
    return "muted"


def build_recovery_timeline_basis_item(recovery_result_timeline: Any = None) -> dict:
    timeline = _as_mapping(recovery_result_timeline)
    if not timeline:
        return {}
    items = [_as_mapping(item) for item in _as_list(timeline.get("items")) if _as_mapping(item)]
    counts = _as_mapping(timeline.get("decision_impact_counts"))
    if not items and not counts:
        return {}
    levels = [_to_text(item.get("decision_impact_level")) for item in items]
    levels = [level for level in levels if level]
    blocked_items = [
        item
        for item in items
        if _to_text(item.get("decision_impact_level")) in {
            "blocks_position_increase",
            "blocks_candidate_execution",
            "blocks_strategy_validation",
        }
    ]
    review_items = [
        item
        for item in items
        if _to_text(item.get("decision_impact_level")) in {"requires_review", "confidence_only"}
    ]
    impact_summary = _to_text(timeline.get("decision_impact_summary"))
    if blocked_items:
        focus_text = "、".join((_to_text(item.get("label")) or "恢复项") for item in blocked_items[:2])
        guardrail = "阻断项未恢复前，今日总动作不能支持加仓、追高、加融资或把风险写成已排除。"
    elif review_items:
        focus_text = "、".join((_to_text(item.get("label")) or "恢复项") for item in review_items[:2])
        guardrail = "缓存/置信度项需要复核，今日总动作只能保持谨慎验证，不自动放大仓位。"
    else:
        focus_text = "、".join((_to_text(item.get("label")) or "恢复项") for item in items[:2])
        guardrail = "旧工具恢复结果已进入证据链；仍需价格、纪律和仓位规则共同确认。"
    value = impact_summary or _to_text(timeline.get("summary")) or "恢复影响待验证"
    return {
        "label": "旧工具恢复影响",
        "value": value,
        "tone": _recovery_impact_basis_tone(levels, _to_text(timeline.get("status"))),
        "summary": f"{focus_text}｜{guardrail}" if focus_text else guardrail,
        "guardrail": guardrail,
        "focus_text": focus_text,
        "impact_counts": counts,
        "items": items,
        "external_call_policy": _to_text(timeline.get("external_call_policy")) or "not_triggered",
        "deepseek_called": False,
    }


def build_recovery_timeline_summary_text(recovery_result_timeline: Any = None) -> str:
    item = build_recovery_timeline_basis_item(recovery_result_timeline)
    if not item:
        return ""
    return f"{item['value']}｜{item['guardrail']}"


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


def _impact_tone(statuses: list[str]) -> str:
    if any(status in {"blocked", "仍不可执行", "仍不可放大"} for status in statuses):
        return "danger"
    if any(status in {"still_verify", "review", "waiting", "cached"} for status in statuses):
        return "warning"
    if any(status in {"recovered", "verified"} for status in statuses):
        return "success"
    return "muted"


def _recovery_impact_label(item: Any = None) -> str:
    payload = _as_mapping(item)
    if not payload:
        return "待验证"
    return _to_text(payload.get("label") or payload.get("status_label") or payload.get("status")) or "待验证"


def build_execution_recovery_basis_item(
    next_ticket_candidates: Any = None,
    margin_etf_summary: Any = None,
) -> dict:
    next_rows = [_as_mapping(item) for item in _as_list(next_ticket_candidates)]
    next_rows = [item for item in next_rows if item]
    etf_rows = [_as_mapping(item) for item in _as_list(_as_mapping(margin_etf_summary).get("recommended_etfs"))]
    etf_rows = [item for item in etf_rows if item]
    next_impacts = [_as_mapping(item.get("evidence_recovery_impact")) for item in next_rows]
    next_impacts = [item for item in next_impacts if item]
    etf_impacts = [_as_mapping(item.get("evidence_recovery_impact")) for item in etf_rows]
    etf_impacts = [item for item in etf_impacts if item]
    if not next_impacts and not etf_impacts:
        return {}
    next_label = _recovery_impact_label(next_impacts[0]) if next_impacts else "待验证"
    etf_label = _recovery_impact_label(etf_impacts[0]) if etf_impacts else "待验证"
    statuses = [
        _to_text(item.get("status")) or _to_text(item.get("label"))
        for item in next_impacts + etf_impacts
    ]
    blocked_count = len([item for item in next_impacts + etf_impacts if _to_text(item.get("status")) == "blocked"])
    review_count = len(
        [
            item
            for item in next_impacts + etf_impacts
            if _to_text(item.get("status")) in {"still_verify", "review", "waiting"}
        ]
    )
    recovered_count = len(
        [
            item
            for item in next_impacts + etf_impacts
            if _to_text(item.get("status")) in {"recovered", "verified"}
        ]
    )
    if blocked_count:
        guardrail = "候选或 ETF 仍有阻断证据，不能把 Top3 或 ETF 清单当作可执行买入依据。"
    elif review_count:
        guardrail = "候选或 ETF 证据仍需复核，执行前必须确认触发条件、流动性和风险预算。"
    elif recovered_count:
        guardrail = "候选/ETF 证据已回流；仍需策略纪律和仓位预算共同确认。"
    else:
        guardrail = "候选/ETF 证据待验证，不自动触发扫描或 DeepSeek。"
    return {
        "label": "候选/ETF证据",
        "value": f"下一票:{next_label}｜ETF:{etf_label}",
        "tone": _impact_tone(statuses),
        "summary": guardrail,
        "next_ticket_count": len(next_rows),
        "etf_count": len(etf_rows),
        "blocked_count": blocked_count,
        "review_count": review_count,
        "recovered_count": recovered_count,
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def build_old_workspace_packet_bridge_basis_item(old_workspace_packet_bridge: Any = None) -> dict:
    bridge = _as_mapping(old_workspace_packet_bridge)
    if not bridge:
        return {}
    items = [_as_mapping(item) for item in _as_list(bridge.get("items")) if _as_mapping(item)]
    counts = {
        "blocked": len([item for item in items if _to_text(item.get("bridge_status")) == "blocked"]),
        "waiting": len([item for item in items if _to_text(item.get("bridge_status")) == "waiting"]),
        "cached": len([item for item in items if _to_text(item.get("bridge_status")) == "cached"]),
        "recovered": len([item for item in items if _to_text(item.get("bridge_status")) == "recovered"]),
    }
    status = _to_text(bridge.get("status"))
    if status == "blocked" or counts["blocked"]:
        tone = "danger"
        guardrail = "旧工具能力未回流或仍阻断时，相关证据只能待验证，不能把旧页面缺失结果当成交易依据。"
    elif status in {"partial", "stale"} or counts["waiting"] or counts["cached"]:
        tone = "warning"
        guardrail = "旧工具能力仍有待回流/缓存复核项；执行前需要确认目标 packet、日期和来源。"
    elif status == "ready" or counts["recovered"]:
        tone = "success"
        guardrail = "旧工具能力已回流为综合中心 packet；仍需和价格、纪律、仓位规则共同复核。"
    else:
        tone = "muted"
        guardrail = "旧工具能力 packet 桥待生成；页面不会自动运行旧工具或重型接口。"
    summary = _to_text(
        bridge.get("summary")
    ) or f"已回流 {counts['recovered']}｜使用缓存 {counts['cached']}｜仍阻断 {counts['blocked']}｜待回流 {counts['waiting']}"
    focus_items = [
        item
        for item in items
        if _to_text(item.get("bridge_status")) in {"blocked", "waiting", "cached"}
    ] or items[:2]
    focus_text = "、".join(_to_text(item.get("label")) for item in focus_items[:2] if _to_text(item.get("label")))
    return {
        "label": "旧能力回流",
        "value": summary,
        "tone": tone,
        "summary": f"{focus_text}｜{guardrail}" if focus_text else guardrail,
        "guardrail": guardrail,
        "blocked_count": counts["blocked"],
        "waiting_count": counts["waiting"],
        "cached_count": counts["cached"],
        "recovered_count": counts["recovered"],
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def build_legacy_decision_chain_basis_item(projection_packet: Any = None) -> dict:
    packet = _as_mapping(projection_packet)
    if not packet:
        return {}

    status = _to_text(packet.get("path_legacy_decision_chain_status")).lower()
    label = _to_text(packet.get("path_legacy_decision_chain_label")) or "旧能力决策链"
    summary = _to_text(packet.get("path_legacy_decision_chain_summary"))
    raw_items = packet.get("path_legacy_decision_chain_items")
    items = [_as_mapping(item) for item in _as_list(raw_items) if _as_mapping(item)]
    if not status and not summary and not items:
        return {}

    counts = {"blocked": 0, "cache_only": 0, "waiting": 0, "ready": 0}
    for item in items:
        state = _to_text(item.get("decision_chain_state")).lower()
        if state in counts:
            counts[state] += 1
        elif item.get("can_enter_decision_chain") is False:
            counts["blocked"] += 1

    if not status:
        if counts["blocked"]:
            status = "blocked"
        elif counts["cache_only"] or counts["waiting"]:
            status = "partial"
        elif counts["ready"]:
            status = "ready"
        else:
            status = "waiting"

    focus_items = [
        item
        for item in items
        if _to_text(item.get("decision_chain_state")).lower() in {"blocked", "cache_only", "waiting"}
    ] or items[:3]
    focus_text = "、".join(_to_text(item.get("label")) for item in focus_items[:3] if _to_text(item.get("label")))

    if status == "blocked":
        tone = "danger"
        value = summary or "仍有阻断项"
        guardrail = "旧能力链有阻断项时，今日总动作不能支持加仓、追高或加融资。"
    elif status in {"cache_only", "partial"}:
        tone = "warning"
        value = summary or "缓存/待验证"
        guardrail = "旧能力链未完全回流时，执行前必须复核日期、来源和覆盖口径。"
    elif status == "ready":
        tone = "success"
        value = summary or "旧能力链已验证"
        guardrail = "旧能力链可进入依据链，但仍需价格、纪律、仓位和失效条件共同确认。"
    else:
        tone = "muted"
        value = summary or "旧能力链待验证"
        guardrail = "旧能力链待验证时，今日总动作只能保留安全空态或低置信度解释。"

    return {
        "label": "旧能力链",
        "value": value,
        "tone": tone,
        "summary": f"{focus_text}｜{guardrail}" if focus_text else guardrail,
        "guardrail": guardrail,
        "status": status,
        "source_label": label,
        "blocked_count": counts["blocked"],
        "cache_count": counts["cache_only"],
        "waiting_count": counts["waiting"],
        "ready_count": counts["ready"],
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def build_decision_evidence_chain_items(
    analysis_method_packet: Any = None,
    projection_packet: Any = None,
    data_capability_brief: Any = None,
    evidence_radar_packet: Any = None,
    a_share_data_console: Any = None,
    data_health_ledger: Any = None,
    a_share_fact_recovery_summary: Any = None,
    latest_recovery_result_notice: Any = None,
    recovery_result_timeline: Any = None,
    next_ticket_candidates: Any = None,
    margin_etf_summary: Any = None,
    old_workspace_packet_bridge: Any = None,
) -> list[dict]:
    analysis = _as_mapping(analysis_method_packet)
    market = _to_text(analysis.get("market")) or "市场类型待确认"
    items = [{"label": "市场类型", "value": market, "tone": "success" if market in {"A股", "美股", "ETF"} else "muted"}]
    data_capability_basis = build_data_capability_brief_basis_item(data_capability_brief)
    if data_capability_basis:
        items.append(data_capability_basis)
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
    legacy_chain_basis = build_legacy_decision_chain_basis_item(projection_packet)
    if legacy_chain_basis:
        items.append(legacy_chain_basis)
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
    execution_recovery_basis = build_execution_recovery_basis_item(
        next_ticket_candidates=next_ticket_candidates,
        margin_etf_summary=margin_etf_summary,
    )
    if execution_recovery_basis:
        items.append(execution_recovery_basis)
    old_workspace_basis = build_old_workspace_packet_bridge_basis_item(old_workspace_packet_bridge)
    if old_workspace_basis:
        items.append(old_workspace_basis)
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
        items.extend(fact_recovery_basis.get("detail_items") or [])
    recovery_timeline_basis = build_recovery_timeline_basis_item(recovery_result_timeline)
    if recovery_timeline_basis:
        items.append(recovery_timeline_basis)
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
    data_capability_brief: Any = None,
    evidence_radar_packet: Any = None,
    a_share_data_console: Any = None,
    data_health_ledger: Any = None,
    a_share_fact_recovery_summary: Any = None,
    latest_recovery_result_notice: Any = None,
    recovery_result_timeline: Any = None,
    next_ticket_candidates: Any = None,
    margin_etf_summary: Any = None,
    old_workspace_packet_bridge: Any = None,
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
            data_capability_brief=data_capability_brief,
            evidence_radar_packet=evidence_radar_packet,
            a_share_data_console=a_share_data_console,
            data_health_ledger=data_health_ledger,
            a_share_fact_recovery_summary=a_share_fact_recovery_summary,
            latest_recovery_result_notice=latest_recovery_result_notice,
            recovery_result_timeline=recovery_result_timeline,
            next_ticket_candidates=next_ticket_candidates,
            margin_etf_summary=margin_etf_summary,
            old_workspace_packet_bridge=old_workspace_packet_bridge,
        ),
        "projection_confidence_summary": projection_confidence,
        "data_capability_brief_basis_item": build_data_capability_brief_basis_item(data_capability_brief),
        "data_capability_brief_summary_text": build_data_capability_brief_summary_text(data_capability_brief),
        "data_health_impact": build_data_health_impact_summary(data_health_ledger, market_type=market),
        "a_share_evidence_radar_card": _as_mapping(_as_mapping(evidence_radar_packet).get("radar_card")),
        "a_share_evidence_summary_text": _to_text(_as_mapping(evidence_radar_packet).get("decision_summary")),
        "a_share_evidence_group_basis_item": build_a_share_evidence_group_basis_item(evidence_radar_packet),
        "a_share_evidence_group_summary_text": build_a_share_evidence_group_summary_text(evidence_radar_packet),
        "legacy_a_share_evidence_basis_item": build_legacy_a_share_evidence_basis_item(evidence_radar_packet),
        "a_share_data_basis_items": build_a_share_data_basis_items(a_share_data_console),
        "a_share_data_basis_summary_text": build_a_share_data_basis_summary_text(a_share_data_console),
        "a_share_fact_recovery_basis_item": build_a_share_fact_recovery_basis_item(a_share_fact_recovery_summary),
        "a_share_fact_recovery_detail_items": build_a_share_fact_recovery_detail_items(a_share_fact_recovery_summary),
        "a_share_fact_recovery_summary_text": build_a_share_fact_recovery_summary_text(a_share_fact_recovery_summary),
        "latest_recovery_result_basis_item": build_latest_recovery_result_basis_item(latest_recovery_result_notice),
        "latest_recovery_result_summary_text": build_latest_recovery_result_summary_text(latest_recovery_result_notice),
        "recovery_timeline_basis_item": build_recovery_timeline_basis_item(recovery_result_timeline),
        "recovery_timeline_summary_text": build_recovery_timeline_summary_text(recovery_result_timeline),
        "execution_recovery_basis_item": build_execution_recovery_basis_item(next_ticket_candidates, margin_etf_summary),
        "old_workspace_packet_bridge_basis_item": build_old_workspace_packet_bridge_basis_item(old_workspace_packet_bridge),
        "legacy_decision_chain_basis_item": build_legacy_decision_chain_basis_item(projection_packet),
        "stale_note": stale_note,
        "must_not_do_items": _list_text(payload.get("must_not_do"), "暂无新增禁止动作，但仍需遵守交易纪律。"),
        "validation_items": _list_text(payload.get("next_validation_conditions"), "等待基础数据刷新后再生成验证条件。"),
        "coverage_items": build_data_coverage_items(payload),
        "deepseek_text": decision_deepseek_text(payload),
        "updated_text": decision_updated_text(payload),
        "source_text": decision_source_text(payload),
        "empty_message": "当前为待刷新/缓存判断，不是完整实时结论。",
    }
