from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_legacy_packet_contract import build_legacy_packet_decision_contract


MAX_TOP_CANDIDATES = 3
MAX_EVIDENCE_ITEMS = 5
MAX_BRIEF_ITEMS = 4

RADAR_EVIDENCE_LINKS = (
    {
        "key": "moneyflow",
        "label": "资金流",
        "score_key": "money_score",
        "writes_packet": "command_center_moneyflow_packet",
        "guardrail": "资金流未验证前，候选不能升级为加仓理由。",
    },
    {
        "key": "dragon_tiger",
        "label": "龙虎榜",
        "score_key": "",
        "writes_packet": "command_center_dragon_tiger_packet",
        "guardrail": "龙虎榜缺失或无上榜不等于机构支持。",
    },
    {
        "key": "limit_emotion",
        "label": "涨跌停/情绪",
        "score_key": "",
        "writes_packet": "command_center_limit_emotion_packet",
        "guardrail": "涨跌停/情绪未验证前，不能确认追高边界。",
    },
    {
        "key": "hard_risk",
        "label": "硬风险",
        "score_key": "risk_score",
        "writes_packet": "command_center_hard_risk_packet",
        "guardrail": "硬风险未排除前，候选只能观察。",
    },
)


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


def _first_list(*values: Any) -> list:
    for value in values:
        rows = as_list(value)
        if rows:
            return rows
    return []


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = to_text(value)
        if text:
            return text
    return default


def _conditions_text(values: Any, fallback: str) -> str:
    items = [to_text(item) for item in as_list(values)]
    items = [item for item in items if item]
    return "；".join(items[:3]) if items else fallback


def _action_tone(action_state: str) -> str:
    if action_state in {"可准备", "准备", "ready"}:
        return "ready"
    if action_state in {"等验证", "待验证"}:
        return "stale"
    if action_state in {"暂不纳入", "排除", "不纳入"}:
        return "failed"
    return "missing"


def _candidate_status_label(action_state: str) -> str:
    if action_state in {"可准备", "准备", "ready"}:
        return "可准备"
    if action_state in {"等验证", "待验证"}:
        return "等验证"
    if action_state in {"暂不纳入", "排除", "不纳入"}:
        return "暂不纳入"
    return action_state or "只观察"


def _evidence_items(
    *,
    score: int | float | None,
    action_state: str,
    reason: str,
    trigger_text: str,
    invalidation_text: str,
    data_gaps: list[str],
) -> list[dict]:
    items = [
        {
            "label": "综合分",
            "value": "待验证" if score is None else str(score),
            "detail": "分数只作排序线索，不等于买入建议。",
            "tone": "ready" if score is not None and score >= 75 else "stale" if score is not None else "missing",
        },
        {
            "label": "候选状态",
            "value": _candidate_status_label(action_state),
            "detail": reason or "规则雷达缓存候选。",
            "tone": _action_tone(action_state),
        },
        {
            "label": "触发条件",
            "value": "待验证",
            "detail": trigger_text,
            "tone": "stale",
        },
        {
            "label": "失效条件",
            "value": "必须遵守",
            "detail": invalidation_text,
            "tone": "failed",
        },
    ]
    if data_gaps:
        items.append(
            {
                "label": "数据缺口",
                "value": f"{len(data_gaps)}项",
                "detail": "；".join(data_gaps[:3]),
                "tone": "missing",
            }
        )
    return items[:MAX_EVIDENCE_ITEMS]


def _score_status(value: int | float | None) -> dict:
    if value is None:
        return {"status": "missing", "status_label": "待验证", "tone": "missing", "value": "待验证"}
    if value >= 70:
        return {"status": "ready", "status_label": "可参考", "tone": "ready", "value": str(value)}
    if value >= 50:
        return {"status": "cached", "status_label": "需复核", "tone": "stale", "value": str(value)}
    return {"status": "blocked", "status_label": "偏弱", "tone": "failed", "value": str(value)}


def _gap_mentions(gaps: list[str], *keywords: str) -> bool:
    text = "；".join(to_text(item) for item in gaps)
    return any(keyword and keyword in text for keyword in keywords)


def _candidate_evidence_chain(score: Mapping[str, Any], data_gaps: list[str]) -> list[dict]:
    result = []
    for link in RADAR_EVIDENCE_LINKS:
        score_key = to_text(link.get("score_key"))
        value = to_number(score.get(score_key)) if score_key else None
        status = _score_status(value)
        key = to_text(link.get("key"))
        if key == "moneyflow" and _gap_mentions(data_gaps, "资金", "moneyflow"):
            status = {"status": "missing", "status_label": "待补证", "tone": "missing", "value": "缺口"}
        elif key == "dragon_tiger" and _gap_mentions(data_gaps, "龙虎", "top_list", "top_inst"):
            status = {"status": "missing", "status_label": "待补证", "tone": "missing", "value": "缺口"}
        elif key == "limit_emotion" and _gap_mentions(data_gaps, "涨跌停", "情绪", "limit"):
            status = {"status": "missing", "status_label": "待补证", "tone": "missing", "value": "缺口"}
        elif key == "hard_risk" and _gap_mentions(data_gaps, "公告", "硬风险", "减持", "质押"):
            status = {"status": "missing", "status_label": "待补证", "tone": "missing", "value": "缺口"}
        result.append(
            {
                "key": key,
                "label": to_text(link.get("label"), "证据"),
                "status": status["status"],
                "status_label": status["status_label"],
                "tone": status["tone"],
                "value": status["value"],
                "detail": (
                    f"{to_text(link.get('label'), '证据')}评分 {status['value']}。"
                    if value is not None
                    else f"{to_text(link.get('label'), '证据')}待从对应 packet 补证。"
                ),
                "writes_packet": to_text(link.get("writes_packet")),
                "guardrail": to_text(link.get("guardrail"), "缺失时不能作为交易依据。"),
                "external_call_policy": "not_triggered",
                "deepseek_called": False,
            }
        )
    return result


def _candidate_evidence_chain_summary(chain: Any = None) -> str:
    rows = [as_mapping(item) for item in as_list(chain)]
    if not rows:
        return "证据链待验证"
    ready = [item for item in rows if item.get("status") == "ready"]
    missing = [item for item in rows if item.get("status") == "missing"]
    blocked = [item for item in rows if item.get("status") == "blocked"]
    stale = [item for item in rows if item.get("status") == "cached"]
    return f"可参考 {len(ready)}｜待补证 {len(missing)}｜偏弱 {len(blocked)}｜需复核 {len(stale)}"


def _candidate_execution_mode(action_state: str) -> dict:
    label = _candidate_status_label(action_state)
    if label == "可准备":
        return {
            "execution_status": "prepare",
            "execution_label": "可准备",
            "tone": "ready",
            "summary": "候选可进入作战准备，但不是买入指令。",
            "next_action": "复核触发条件、风险预算和当前持仓纪律；缺失证据先补证。",
        }
    if label == "等验证":
        return {
            "execution_status": "verify",
            "execution_label": "等验证",
            "tone": "stale",
            "summary": "先补齐关键证据，再判断是否进入作战准备。",
            "next_action": "手动恢复资金流、龙虎榜、涨跌停/情绪、硬风险等证据 packet。",
        }
    if label == "暂不纳入":
        return {
            "execution_status": "blocked",
            "execution_label": "暂不纳入",
            "tone": "failed",
            "summary": "当前候选暂不纳入交易准备。",
            "next_action": "保持排除；除非下一票雷达手动扫描重新给出有效信号。",
        }
    return {
        "execution_status": "observe",
        "execution_label": "只观察",
        "tone": "missing",
        "summary": "只观察，不主动买入。",
        "next_action": "等待下一次手动扫描、基础数据刷新或证据链改善。",
    }


def _evidence_labels_by_status(chain: Any, statuses: set[str]) -> list[str]:
    labels = []
    seen = set()
    for item in as_list(chain):
        payload = as_mapping(item)
        status = to_text(payload.get("status"))
        label = to_text(payload.get("label"), "证据")
        if status in statuses and label and label not in seen:
            labels.append(label)
            seen.add(label)
        if len(labels) >= MAX_BRIEF_ITEMS:
            break
    return labels


def build_candidate_decision_brief(candidate: Any = None) -> dict:
    payload = as_mapping(candidate)
    mode = _candidate_execution_mode(
        _first_text(payload.get("status_label"), payload.get("action_state"), default="只观察")
    )
    chain = as_list(payload.get("evidence_chain"))
    missing_evidence = _evidence_labels_by_status(chain, {"missing", "cached"})
    blocking_evidence = _evidence_labels_by_status(chain, {"blocked", "failed"})
    data_gaps = [to_text(item) for item in as_list(payload.get("data_gaps")) if to_text(item)][:MAX_BRIEF_ITEMS]
    trigger = _first_text(payload.get("trigger_condition"), default="等待规则雷达触发条件确认。")
    invalidation = _first_text(payload.get("invalidation_condition"), default="风险转弱或触发条件失效。")
    confidence_gate = "可验证"
    if blocking_evidence or mode["execution_status"] == "blocked":
        confidence_gate = "不可执行"
    elif missing_evidence or data_gaps or mode["execution_status"] in {"verify", "observe"}:
        confidence_gate = "待补证"
    next_action = mode["next_action"]
    if missing_evidence:
        next_action = f"{next_action} 优先补证：{'、'.join(missing_evidence[:MAX_BRIEF_ITEMS])}。"
    elif data_gaps:
        next_action = f"{next_action} 优先处理数据缺口：{'、'.join(data_gaps[:MAX_BRIEF_ITEMS])}。"
    return {
        "execution_status": mode["execution_status"],
        "execution_label": mode["execution_label"],
        "tone": mode["tone"],
        "confidence_gate": confidence_gate,
        "summary": mode["summary"],
        "trigger_text": trigger,
        "invalidation_text": invalidation,
        "next_action": next_action,
        "missing_evidence": missing_evidence,
        "blocking_evidence": blocking_evidence,
        "data_gaps": data_gaps,
        "recovery_route": (
            "高级工具箱 → 下一票雷达 / A股数据恢复"
            if missing_evidence or data_gaps
            else "下一票雷达手动扫描"
        ),
        "guardrail": "候选不是买入指令；证据链、触发条件、纪律和仓位预算同时通过后，才允许进入执行准备。",
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def _with_candidate_decision_brief(candidate: Any = None, rank: int = 0) -> dict:
    payload = as_mapping(candidate)
    if rank and not payload.get("rank"):
        payload["rank"] = rank
    payload["decision_brief"] = build_candidate_decision_brief(payload)
    return payload


def build_radar_decision_summary(candidates: Any = None) -> dict:
    rows = [_with_candidate_decision_brief(item, rank=index + 1) for index, item in enumerate(as_list(candidates))]
    if not rows:
        return {
            "headline": "暂无可执行候选",
            "tone": "missing",
            "summary": "下一票雷达没有可展示 Top3；点击手动扫描或刷新基础数据后再看。",
            "next_action": "先手动刷新今日基础数据或进入高级工具箱运行下一票雷达。",
            "guardrail": "页面打开不会自动全市场扫描，DeepSeek 未调用。",
            "deepseek_called": False,
            "external_call_policy": "not_triggered",
        }
    counts = {"prepare": 0, "verify": 0, "observe": 0, "blocked": 0}
    for row in rows:
        status = to_text(as_mapping(row.get("decision_brief")).get("execution_status"), "observe")
        if status in counts:
            counts[status] += 1
    headline = f"可准备 {counts['prepare']}｜等验证 {counts['verify']}｜只观察 {counts['observe']}｜暂不纳入 {counts['blocked']}"
    tone = "ready" if counts["prepare"] else "stale" if counts["verify"] else "missing"
    return {
        "headline": headline,
        "tone": tone,
        "summary": "Top3 候选已转成执行摘要；它们是待验证线索，不是自动买入指令。",
        "next_action": "先看每只候选的待补证、触发条件和失效条件，再决定是否进入作战准备。",
        "guardrail": "下一票候选不自动触发扫描、DeepSeek 或下单。",
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def _radar_brief_counts(candidates: Any = None) -> dict[str, int]:
    counts = {"prepare": 0, "verify": 0, "observe": 0, "blocked": 0}
    for row in as_list(candidates):
        brief = as_mapping(as_mapping(row).get("decision_brief"))
        status = to_text(brief.get("execution_status"), "observe")
        if status in counts:
            counts[status] += 1
    return counts


def _radar_verification_status(status: str, data_status: str, candidates: Any = None, errors: Any = None) -> str:
    if status == "failed" or as_list(errors):
        return "阻断决策" if status == "failed" else "待验证"
    if data_status == "missing" or not as_list(candidates):
        return "待验证"
    counts = _radar_brief_counts(candidates)
    if counts["prepare"]:
        return "已验证"
    if data_status in {"cached", "cache_only"}:
        return "缓存辅助"
    return "待验证"


def _build_radar_packet_evidence_summary(status: str, data_status: str, candidates: Any = None, errors: Any = None) -> str:
    rows = as_list(candidates)
    if not rows:
        if status == "failed":
            return "下一票雷达读取失败；候选池不能进入执行准备。"
        return "暂无下一票 Top3；页面打开不会自动全市场扫描，需手动扫描或刷新基础数据。"
    counts = _radar_brief_counts(rows)
    error_count = len(as_list(errors))
    parts = [
        f"下一票 Top{len(rows)}",
        f"可准备 {counts['prepare']}",
        f"等验证 {counts['verify']}",
        f"只观察 {counts['observe']}",
        f"暂不纳入 {counts['blocked']}",
    ]
    if error_count:
        parts.append(f"错误 {error_count}")
    first = as_mapping(rows[0])
    chain_summary = to_text(first.get("evidence_chain_summary"))
    if chain_summary:
        parts.append(f"首位证据链：{chain_summary}")
    return "｜".join(parts)


def _build_radar_packet_evidence_items(status: str, data_status: str, candidates: Any = None, errors: Any = None) -> list[dict]:
    rows = as_list(candidates)
    counts = _radar_brief_counts(rows)
    error_count = len(as_list(errors))
    return [
        {
            "label": "候选覆盖",
            "value": f"Top{len(rows)}" if rows else "待生成",
            "detail": "只读取本地缓存或手动扫描结果；不会自动全市场扫描。",
            "tone": "ready" if rows else "missing",
        },
        {
            "label": "执行分层",
            "value": f"可准备 {counts['prepare']}｜等验证 {counts['verify']}",
            "detail": f"只观察 {counts['observe']}｜暂不纳入 {counts['blocked']}",
            "tone": "ready" if counts["prepare"] else "stale" if counts["verify"] else "missing",
        },
        {
            "label": "数据状态",
            "value": data_status or "missing",
            "detail": "候选进入交易前仍需资金流、龙虎榜、情绪、硬风险等证据复核。",
            "tone": "ready" if data_status == "ready" else "stale" if data_status == "cached" else "missing",
        },
        {
            "label": "错误/缺口",
            "value": f"{error_count}项" if error_count else "暂无",
            "detail": "错误或缺口不会被写成利好，也不会触发自动补数。",
            "tone": "failed" if error_count else "ready",
        },
    ][:MAX_EVIDENCE_ITEMS]


def _radar_action_hint(status: str, candidates: Any = None, errors: Any = None) -> str:
    rows = as_list(candidates)
    if status == "failed":
        return "先处理下一票雷达错误；未恢复前候选池不能进入执行准备。"
    if not rows:
        return "进入高级工具箱手动运行下一票雷达，或刷新今日基础数据后再查看 Top3。"
    counts = _radar_brief_counts(rows)
    if counts["prepare"]:
        return "先复核可准备候选的触发条件、失效条件、证据链和仓位预算，再进入策略执行。"
    if counts["verify"]:
        return "优先补齐等验证候选的资金流、龙虎榜、涨跌停/情绪和硬风险证据。"
    return "当前候选只观察；等待手动扫描、基础数据刷新或证据链改善。"


def _radar_decision_guardrail(status: str, candidates: Any = None) -> str:
    if status == "failed" or not as_list(candidates):
        return "没有可验证 Top3 时，不能把下一票雷达写成买入、追高或加融资依据。"
    return "下一票候选不是买入指令；只有触发条件成立、证据链不阻断、纪律和仓位预算同时通过，才允许进入执行准备。"


def _apply_radar_packet_contract(packet: Any = None, errors: Any = None) -> dict:
    payload = as_mapping(packet)
    candidates = as_list(payload.get("top_candidates"))
    status = to_text(payload.get("status"), "waiting")
    data_status = to_text(payload.get("data_status") or payload.get("cache_state"), "missing")
    error_items = as_list(errors) or as_list(payload.get("errors"))
    payload.update(
        {
            "packet_role": _first_text(payload.get("packet_role"), default="下一票 Top3 候选证据"),
            "verification_status": _first_text(
                payload.get("verification_status"),
                default=_radar_verification_status(status, data_status, candidates, error_items),
            ),
            "evidence_summary": _first_text(
                payload.get("evidence_summary"),
                default=_build_radar_packet_evidence_summary(status, data_status, candidates, error_items),
            ),
            "evidence_items": as_list(payload.get("evidence_items"))
            or _build_radar_packet_evidence_items(status, data_status, candidates, error_items),
            "action_hint": _first_text(payload.get("action_hint"), default=_radar_action_hint(status, candidates, error_items)),
            "decision_guardrail": _first_text(
                payload.get("decision_guardrail"),
                default=_radar_decision_guardrail(status, candidates),
            ),
        }
    )
    return payload


def normalize_radar_candidate(row: Any = None, scan_packet: Any = None, live_section: Any = None, rank: int = 0) -> dict:
    row_map = as_mapping(row)
    scan = as_mapping(scan_packet)
    live = as_mapping(live_section)
    candidate = as_mapping(row_map.get("candidate")) or row_map
    score = as_mapping(row_map.get("score")) or row_map
    context = as_mapping(row_map.get("candidate_context"))
    trigger_conditions = _first_list(
        score.get("trigger_conditions"),
        row_map.get("trigger_conditions"),
        candidate.get("trigger_conditions"),
    )
    invalidation_conditions = _first_list(
        score.get("invalid_conditions"),
        score.get("invalidation_conditions"),
        row_map.get("invalid_conditions"),
        row_map.get("invalidation_conditions"),
        candidate.get("invalid_conditions"),
    )
    ticker = _first_text(candidate.get("ticker"), score.get("ticker"), row_map.get("ticker"))
    name = _first_text(candidate.get("name"), score.get("name"), row_map.get("name"))
    action_state = _first_text(
        score.get("battle_state"),
        row_map.get("battle_state"),
        row_map.get("action_state"),
        candidate.get("action_state"),
        default="只观察",
    )
    trigger_text = _conditions_text(
        trigger_conditions,
        _first_text(score.get("trigger_condition"), row_map.get("trigger_condition"), score.get("one_sentence_conclusion"), row_map.get("summary"), default="等待规则雷达触发条件确认。"),
    )
    invalidation_text = _conditions_text(
        invalidation_conditions,
        _first_text(score.get("invalidation_condition"), row_map.get("invalidation_condition"), score.get("fail_condition"), default="市场转弱、候选评分下降或纪律信号反向时失效。"),
    )
    data_gaps = _first_list(
        context.get("data_gaps"),
        as_mapping(score.get("score_notes")).get("data_gaps"),
        row_map.get("data_gaps"),
    )
    score_value = to_number(score.get("total_score") or score.get("score") or row_map.get("score"))
    reason = _first_text(score.get("battle_state_reason"), row_map.get("reason"), score.get("one_sentence_conclusion"), default="规则雷达缓存候选。")
    gap_items = [to_text(item) for item in data_gaps if to_text(item)][:5]
    evidence_chain = _candidate_evidence_chain(score, gap_items)
    result = {
        "rank": rank,
        "ticker": ticker,
        "name": name,
        "action_state": action_state,
        "status_label": _candidate_status_label(action_state),
        "tone": _action_tone(action_state),
        "score": score_value,
        "trigger_conditions": trigger_conditions[:5],
        "trigger_condition": trigger_text,
        "invalidation_conditions": invalidation_conditions[:5],
        "invalidation_condition": invalidation_text,
        "reason": reason,
        "evidence_items": _evidence_items(
            score=score_value,
            action_state=action_state,
            reason=reason,
            trigger_text=trigger_text,
            invalidation_text=invalidation_text,
            data_gaps=gap_items,
        ),
        "evidence_chain": evidence_chain,
        "evidence_chain_summary": _candidate_evidence_chain_summary(evidence_chain),
        "action_guardrail": "下一票候选不是买入指令；只有触发条件成立、核心证据不阻断且当前持仓纪律允许时，才进入作战准备。",
        "data_gaps": gap_items,
        "source": _first_text(row_map.get("source"), row_map.get("scan_source"), context.get("scan_source"), scan.get("source"), live.get("source"), default="下一票雷达缓存"),
        "updated_at": _first_text(row_map.get("updated_at"), row_map.get("generated_at"), scan.get("generated_at"), live.get("updated_at"), default="暂无"),
        "manual_required_text": "下一票候选来自本地缓存或手动扫描结果；页面打开不会自动全市场扫描。",
        "deepseek_called": False,
    }
    result["decision_brief"] = build_candidate_decision_brief(result)
    return result


def _packet_status(scan_packet: Mapping[str, Any], rows: list, errors: list, status_raw: str) -> str:
    if status_raw == "failed":
        return "failed"
    if status_raw == "partial_failed" or errors:
        return "partial"
    if rows:
        return "ready"
    if scan_packet:
        return "waiting"
    return "waiting"


def build_command_center_radar_packet(
    state: Any = None,
    live_packet: Any = None,
    limit: int = MAX_TOP_CANDIDATES,
) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    live_section = as_mapping(live.get("next_ticket"))
    existing = as_mapping(state_map.get("command_center_radar_packet"))
    if existing.get("top_candidates"):
        top_candidates = [
            _with_candidate_decision_brief(item, rank=index + 1)
            for index, item in enumerate(as_list(existing.get("top_candidates"))[: int(limit or MAX_TOP_CANDIDATES)])
        ]
        data_status = _first_text(existing.get("data_status"), existing.get("cache_state"), default="ready")
        packet = {
            **existing,
            "top_candidates": top_candidates,
            "display_count": len(top_candidates),
            "cache_state": data_status,
            "decision_summary": build_radar_decision_summary(top_candidates),
            "manual_required_text": _first_text(
                existing.get("manual_required_text"),
                default="下一票雷达必须手动扫描或读取缓存；页面打开不会自动全市场扫描。",
            ),
            "deepseek_called": bool(existing.get("deepseek_called", False)),
        }
        packet.update(
            build_legacy_packet_decision_contract(
                packet,
                label="下一票雷达",
                status=packet.get("status"),
                data_status=data_status,
                recovery_state=packet.get("recovery_state"),
                capability_state=packet.get("capability_state"),
            )
        )
        return _apply_radar_packet_contract(packet)
    scan_packet = as_mapping(state_map.get("radar_scan_results"))
    summary = as_mapping(state_map.get("radar_scan_summary") or scan_packet.get("summary"))
    rows = _first_list(
        live_section.get("top_candidates"),
        scan_packet.get("rule_rows"),
        scan_packet.get("results"),
        scan_packet.get("top_candidates"),
        scan_packet.get("candidates"),
        scan_packet.get("candidate_rows"),
    )
    errors = _first_list(state_map.get("radar_scan_errors"), summary.get("errors"), scan_packet.get("errors"))
    status_raw = to_text(state_map.get("radar_scan_status") or scan_packet.get("status"))
    top_candidates = []
    seen = set()
    for row in rows:
        candidate = normalize_radar_candidate(row, scan_packet=scan_packet, live_section=live_section, rank=len(top_candidates) + 1)
        key = candidate.get("ticker") or candidate.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        top_candidates.append(candidate)
        if len(top_candidates) >= int(limit or MAX_TOP_CANDIDATES):
            break
    status = _packet_status(scan_packet, rows, errors, status_raw)
    generated_at = _first_text(
        scan_packet.get("generated_at"),
        state_map.get("radar_scan_finished_at"),
        live_section.get("updated_at"),
        default="",
    )
    total_count = len(rows)
    data_status = "ready" if top_candidates else "missing"
    packet = {
        "status": status,
        "cache_state": "ready" if top_candidates else "missing",
        "source": _first_text(summary.get("source_mode"), scan_packet.get("source_mode"), live_section.get("source"), default="下一票雷达缓存"),
        "generated_at": generated_at,
        "total_count": total_count,
        "display_count": len(top_candidates),
        "top_candidates": top_candidates,
        "summary": _first_text(
            summary.get("note"),
            summary.get("summary"),
            default=(
                f"规则雷达缓存 {total_count} 条，首页展示 Top {len(top_candidates)}。"
                if rows
                else "暂无下一票雷达缓存；点击刷新今日基础数据不会自动全市场扫描。"
            ),
        ),
        "errors": [to_text(item) for item in errors if to_text(item)][:8],
        "data_status": data_status,
        "decision_summary": build_radar_decision_summary(top_candidates),
        "manual_required_text": "下一票雷达只读取本地缓存或手动扫描结果；页面打开不会自动全市场扫描。",
        "deepseek_called": bool(summary.get("deepseek_called", False)),
    }
    packet.update(
        build_legacy_packet_decision_contract(
            packet,
            label="下一票雷达",
            status=status,
            data_status=data_status,
            recovery_state=summary.get("recovery_state"),
            capability_state=summary.get("capability_state"),
        )
    )
    return _apply_radar_packet_contract(packet, errors=errors)
