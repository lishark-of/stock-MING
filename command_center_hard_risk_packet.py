from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_legacy_packet_contract import build_legacy_packet_decision_contract


MAX_ITEMS = 6
MAX_RISK_NOTES = 8

RESTRICTED_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
READY_STATES = {"ready", "ok", "completed", "success", "available"}


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


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = to_text(value)
        if text:
            return text
    return default


def _ticker_base(value: Any) -> str:
    text = to_text(value).upper()
    return text.split(".")[0] if text else ""


def _dedupe_text(values: Any, limit: int = MAX_RISK_NOTES) -> list[str]:
    raw_values = values if isinstance(values, (list, tuple)) else [values]
    items = []
    seen = set()
    for item in raw_values:
        if isinstance(item, Mapping):
            text = _first_text(
                item.get("message"),
                item.get("summary"),
                item.get("risk"),
                item.get("risk_flag"),
                item.get("title"),
                item.get("type"),
            )
        else:
            text = to_text(item)
        if text and text not in seen:
            seen.add(text)
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _source_from_state(state_map: Mapping[str, Any], live_packet: Mapping[str, Any]) -> dict:
    existing = as_mapping(state_map.get("command_center_hard_risk_packet"))
    if existing:
        return {"payload": existing, "source_key": "command_center_hard_risk_packet"}

    facts = as_mapping(state_map.get("a_share_professional_facts"))
    hard_risk = as_mapping(facts.get("hard_risk") or facts.get("verified_hard_risks"))
    if hard_risk:
        return {"payload": hard_risk, "source_key": "a_share_professional_facts.verified_hard_risks"}

    tianyan = as_mapping(state_map.get("tianyan_risk_fact_packet"))
    verified_hard = as_mapping(tianyan.get("verified_hard_risks"))
    if verified_hard:
        return {"payload": verified_hard, "source_key": "tianyan_risk_fact_packet.verified_hard_risks"}

    for key in ("hard_risk_radar_data", "cn_hard_risk_radar_data"):
        payload = as_mapping(state_map.get(key))
        if payload:
            return {"payload": payload, "source_key": key}

    facts_packet = as_mapping(state_map.get("command_center_facts_packet"))
    for item in as_list(facts_packet.get("items")):
        item_map = as_mapping(item)
        if item_map.get("key") in {"hard_risk", "hard_risks", "announcement_risk"}:
            return {"payload": item_map, "source_key": "command_center_facts_packet.items.hard_risk"}

    live = as_mapping(as_mapping(live_packet.get("facts")).get("hard_risk") or live_packet.get("hard_risk"))
    if live:
        return {"payload": live, "source_key": "command_center_live_packet.hard_risk"}

    return {"payload": {}, "source_key": ""}


def _section_payloads(payload: Mapping[str, Any]) -> list[tuple[str, dict]]:
    section_names = (
        "announcements",
        "free_announcement_radar",
        "earnings_forecast",
        "holder_reduction",
        "share_unlock",
        "pledge",
        "institution_surveys",
        "suspend",
        "namechange",
    )
    return [(name, as_mapping(payload.get(name))) for name in section_names if as_mapping(payload.get(name))]


def _section_has_rows(section: Mapping[str, Any]) -> bool:
    return bool(as_list(section.get("rows") or section.get("items") or section.get("records")))


def _section_error(section: Mapping[str, Any]) -> str:
    return _first_text(section.get("error"), section.get("last_error"), section.get("message"))


def _has_restricted_error(text: str) -> bool:
    lowered = text.lower()
    return any(
        word in lowered
        for word in (
            "permission",
            "not configured",
            "unauthorized",
            "权限",
            "未配置",
            "不可用",
            "未接入",
            "失败",
            "error",
        )
    )


def _status_from(payload: Mapping[str, Any]) -> str:
    raw_status = to_text(payload.get("status") or payload.get("state") or payload.get("capability_state")).lower()
    if raw_status in READY_STATES:
        return "ready"
    if raw_status in RESTRICTED_STATES or raw_status in {"error", "failure"}:
        return "failed"
    if payload.get("available") is True or any(_section_has_rows(section) for _, section in _section_payloads(payload)):
        return "ready"
    if payload:
        section_errors = [_section_error(section) for _, section in _section_payloads(payload)]
        if _has_restricted_error(_first_text(payload.get("error"), payload.get("message"), *section_errors)):
            return "failed"
        return "partial"
    return "waiting"


def _data_status(status: str, payload: Mapping[str, Any]) -> str:
    if status == "ready":
        return "ready"
    if status in {"partial", "failed"} and payload:
        return "cached" if payload.get("available") else "missing"
    return "missing"


def _capability_state(payload: Mapping[str, Any], status: str) -> str:
    state = _first_text(payload.get("capability_state"), payload.get("state")).lower()
    if state:
        return state
    if status == "ready":
        return "available"
    if status == "failed":
        return "failed"
    if status == "partial":
        return "empty_recent"
    return "requires_manual_refresh"


def _status_label(payload: Mapping[str, Any], capability_state: str, status: str) -> str:
    explicit = _first_text(payload.get("status_label"), payload.get("capability_label"), payload.get("status"))
    if explicit and explicit.lower() not in {"ready", "ok", "completed", "success", "failed", "error", "partial", "waiting"}:
        return explicit
    return {
        "available": "可用",
        "permission_denied": "权限不足",
        "disabled_this_session": "本会话跳过",
        "empty_recent": "近期无数据",
        "stale_cache": "使用缓存",
        "fallback_used": "使用替代口径",
        "requires_manual_refresh": "需要手动刷新",
        "network_failed": "网络失败",
        "not_configured": "未配置",
        "failed": "调用失败",
    }.get(capability_state, {"ready": "可用", "failed": "调用失败", "partial": "待验证"}.get(status, "待刷新"))


def _recovery_state(status: str, capability_state: str, data_status: str) -> str:
    if status == "ready" or data_status in {"ready", "cached"}:
        return "recovered"
    if capability_state in RESTRICTED_STATES:
        return "blocked"
    return "waiting"


def _normalize_row(item: Any, *, risk_type: str, source: str, updated_at: str = "") -> dict:
    payload = as_mapping(item)
    if not payload:
        text = to_text(item)
        return {"type": risk_type, "message": text, "date": "", "source": source} if text else {}
    message = _first_text(
        payload.get("message"),
        payload.get("summary"),
        payload.get("title"),
        payload.get("risk_flag"),
        payload.get("type"),
        default=risk_type,
    )
    return {
        "type": _first_text(payload.get("type"), payload.get("risk_type"), default=risk_type),
        "message": message,
        "date": _first_text(
            payload.get("date"),
            payload.get("ann_date"),
            payload.get("trade_date"),
            payload.get("end_date"),
            payload.get("float_date"),
            payload.get("updated_at"),
            default=updated_at,
        ),
        "source": _first_text(payload.get("source"), default=source),
    }


def _rows_from_section(section: Mapping[str, Any], *, risk_type: str, source: str) -> list[dict]:
    rows = as_list(section.get("risk_items"))
    if not rows:
        rows = as_list(section.get("rows") or section.get("items") or section.get("records"))
    updated_at = _first_text(section.get("updated_at"), section.get("trade_date"))
    items = []
    for row in rows:
        item = _normalize_row(row, risk_type=risk_type, source=source, updated_at=updated_at)
        if item.get("message"):
            items.append(item)
        if len(items) >= MAX_ITEMS:
            break
    return items


def _explicit_risk_items(payload: Mapping[str, Any], source: str) -> list[dict]:
    rows = as_list(payload.get("risk_items") or payload.get("risks") or payload.get("warnings"))
    items = []
    for row in rows:
        item = _normalize_row(row, risk_type="硬风险", source=source, updated_at=_first_text(payload.get("updated_at")))
        if item.get("message"):
            items.append(item)
        if len(items) >= MAX_ITEMS:
            break
    return items


def _build_risk_items(payload: Mapping[str, Any], source: str) -> list[dict]:
    items = _explicit_risk_items(payload, source)
    section_types = {
        "announcements": "公告风险",
        "free_announcement_radar": "公告线索",
        "earnings_forecast": "业绩预告",
        "holder_reduction": "股东减持",
        "share_unlock": "限售解禁",
        "pledge": "股权质押",
        "institution_surveys": "机构调研",
        "suspend": "停牌",
        "namechange": "ST/名称变更",
    }
    for name, section in _section_payloads(payload):
        risk_type = section_types.get(name, name)
        flags = _dedupe_text(section.get("risk_flags"), limit=MAX_ITEMS)
        for flag in flags:
            items.append(
                {
                    "type": risk_type,
                    "message": flag,
                    "date": _first_text(section.get("updated_at"), section.get("trade_date")),
                    "source": _first_text(section.get("source"), default=source),
                }
            )
        if name in {"announcements", "free_announcement_radar", "holder_reduction", "pledge", "suspend", "namechange"}:
            items.extend(_rows_from_section(section, risk_type=risk_type, source=_first_text(section.get("source"), default=source)))
        if len(items) >= MAX_ITEMS:
            break
    deduped = []
    seen = set()
    for item in items:
        key = (item.get("type"), item.get("message"), item.get("date"), item.get("source"))
        if item.get("message") and key not in seen:
            seen.add(key)
            deduped.append(item)
        if len(deduped) >= MAX_ITEMS:
            break
    return deduped


def _build_section_items(payload: Mapping[str, Any], section_name: str, source: str) -> list[dict]:
    section = as_mapping(payload.get(section_name))
    label = {
        "announcements": "公告风险",
        "free_announcement_radar": "公告线索",
        "pledge": "股权质押",
        "suspend": "停牌",
    }.get(section_name, section_name)
    return _rows_from_section(section, risk_type=label, source=_first_text(section.get("source"), default=source))[:MAX_ITEMS]


def _risk_state(status: str, risk_items: list[dict]) -> str:
    if risk_items:
        return "风险线索存在"
    if status == "ready":
        return "暂无硬风险"
    if status == "failed":
        return "硬风险待排查"
    return "待验证"


def _risk_level(status: str, risk_items: list[dict]) -> str:
    joined = " ".join(item.get("message", "") for item in risk_items)
    if any(word in joined for word in ("立案", "监管", "处罚", "诉讼", "退市", "停牌", "ST", "减持", "质押")):
        return "high"
    if risk_items:
        return "medium"
    if status == "ready":
        return "low"
    return "unknown"


def _build_risk_notes(payload: Mapping[str, Any], status: str, risk_items: list[dict]) -> list[str]:
    notes = []
    notes.extend(_dedupe_text(payload.get("risk_notes") or payload.get("risk_flags") or payload.get("missing_items")))
    for _, section in _section_payloads(payload):
        notes.extend(_dedupe_text(section.get("risk_flags")))
        error = _section_error(section)
        if error and error != "暂无可验证数据":
            notes.append(error)
    if status != "ready":
        notes.append("硬风险数据缺失或受限时，不能把缺口写成无风险。")
    elif not risk_items:
        notes.append("无记录不等于无风险；公告正文和监管事实仍需人工复核。")
    notes.append("页面打开不会自动请求 Tushare 公告、减持、质押或停牌接口；需要手动刷新后再验证。")
    return _dedupe_text(notes, limit=MAX_RISK_NOTES)


def _verification_status(status: str, recovery_state: str) -> str:
    if status == "ready":
        return "已验证"
    if recovery_state == "blocked":
        return "阻断决策"
    return "待验证"


def _build_evidence_summary(
    status: str,
    status_label: str,
    recovery_state: str,
    risk_state: str,
    risk_level: str,
    risk_items: list[dict],
) -> str:
    if status == "ready":
        parts = [f"硬风险状态：{risk_state}", f"风险等级：{risk_level}"]
        if risk_items:
            parts.append(f"风险线索 {len(risk_items)} 条")
        else:
            parts.append("未见结构化硬风险线索")
        return "｜".join(parts)
    if recovery_state == "blocked":
        return f"{status_label}：公告/硬风险不能进入风险排除依据。"
    return "公告/硬风险待手动刷新；未回流前不能把缺口写成无风险。"


def _build_evidence_items(
    status: str,
    status_label: str,
    verification_status: str,
    risk_state: str,
    risk_level: str,
    risk_items: list[dict],
) -> list[dict]:
    if status != "ready":
        return [
            {
                "key": "hard_risk",
                "label": "公告/硬风险",
                "value": status_label,
                "status": verification_status,
            }
        ]
    return [
        {
            "key": "risk_state",
            "label": "硬风险状态",
            "value": risk_state,
            "status": verification_status,
        },
        {
            "key": "risk_level",
            "label": "风险等级",
            "value": risk_level,
            "status": verification_status,
        },
        {
            "key": "risk_items",
            "label": "风险线索",
            "value": f"{len(risk_items)} 条" if risk_items else "未见结构化线索",
            "status": "已回流" if risk_items else "待人工复核",
        },
    ]


def _action_hint(status: str, capability_state: str, risk_state: str, risk_level: str) -> str:
    if status == "ready" and risk_state == "风险线索存在":
        return "先复核公告、减持、质押或停牌线索；硬风险未排除前不加仓、不追高。"
    if status == "ready":
        return "把硬风险 packet 作为风险排查结果；无记录仍需人工复核公告正文。"
    if capability_state in RESTRICTED_STATES:
        return "先在数据恢复中心处理公告、减持、质押或停牌接口权限、网络或覆盖范围。"
    return "需要时手动刷新公告/硬风险能力；缺失时不能把风险缺口写成安全。"


def _decision_guardrail(status: str, risk_state: str, risk_level: str) -> str:
    if status != "ready":
        return "缺少公告/硬风险时，不能把数据缺口写成无风险，也不能支持加仓。"
    if risk_state == "风险线索存在" or risk_level in {"high", "medium"}:
        return "硬风险线索未排除前不能加仓、追高或提高融资比例。"
    return "未见结构化硬风险不等于绝对安全；仍需人工复核公告正文和监管事实。"


def build_command_center_hard_risk_packet(
    state: Any = None,
    live_packet: Any = None,
    target: str = "",
) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    source = _source_from_state(state_map, live)
    payload = as_mapping(source.get("payload"))
    existing_target = _first_text(payload.get("target"), payload.get("ticker"), payload.get("ts_code"))
    if payload and target and existing_target and _ticker_base(existing_target) != _ticker_base(target):
        payload = {}

    source_text = _first_text(payload.get("source"), default="Tushare 硬风险缓存")
    status = _status_from(payload)
    risk_items = _build_risk_items(payload, source_text)
    announcement_items = _build_section_items(payload, "announcements", source_text) + _build_section_items(
        payload,
        "free_announcement_radar",
        source_text,
    )
    pledge_items = _build_section_items(payload, "pledge", source_text)
    suspend_items = _build_section_items(payload, "suspend", source_text) + _build_section_items(
        payload,
        "namechange",
        source_text,
    )
    data_status = _data_status(status, payload)
    capability_state = _capability_state(payload, status)
    status_label = _status_label(payload, capability_state, status)
    recovery_state = _recovery_state(status, capability_state, data_status)
    risk_state = _risk_state(status, risk_items)
    risk_level = _risk_level(status, risk_items)
    verification_status = _verification_status(status, recovery_state)
    summary = _first_text(
        payload.get("summary"),
        default=(
            "硬风险证据待刷新；页面打开不会自动请求公告、减持、质押或停牌接口。"
            if status == "waiting"
            else f"硬风险状态：{risk_state}。"
        ),
    )
    api = _first_text(
        payload.get("api"),
        *[
            section.get("api")
            for _, section in _section_payloads(payload)
            if section.get("api")
        ],
        default="anns_d / forecast / stk_holdertrade / pledge_stat / suspend_d",
    )
    updated_at = _first_text(
        payload.get("updated_at"),
        *[
            section.get("updated_at")
            for _, section in _section_payloads(payload)
            if section.get("updated_at")
        ],
    )
    packet = {
        "status": status,
        "data_status": data_status,
        "capability_state": capability_state,
        "status_label": status_label,
        "recovery_state": recovery_state,
        "source": source_text,
        "source_key": to_text(source.get("source_key")),
        "api": api,
        "updated_at": updated_at,
        "trade_date": _first_text(payload.get("trade_date"), payload.get("date"), payload.get("latest_date")),
        "target": _first_text(target, existing_target),
        "ticker": _first_text(payload.get("ticker"), payload.get("ts_code"), target),
        "risk_state": risk_state,
        "risk_level": risk_level,
        "risk_item_count": len(risk_items),
        "risk_items": risk_items,
        "announcement_items": announcement_items[:MAX_ITEMS],
        "pledge_items": pledge_items[:MAX_ITEMS],
        "suspend_items": suspend_items[:MAX_ITEMS],
        "summary": summary,
        "packet_role": "A股公告/硬风险证据",
        "verification_status": verification_status,
        "evidence_summary": _first_text(
            payload.get("evidence_summary"),
            default=_build_evidence_summary(
                status,
                status_label,
                recovery_state,
                risk_state,
                risk_level,
                risk_items,
            ),
        ),
        "evidence_items": as_list(payload.get("evidence_items"))
        or _build_evidence_items(
            status,
            status_label,
            verification_status,
            risk_state,
            risk_level,
            risk_items,
        ),
        "action_hint": _first_text(payload.get("action_hint"), default=_action_hint(status, capability_state, risk_state, risk_level)),
        "decision_guardrail": _first_text(payload.get("decision_guardrail"), default=_decision_guardrail(status, risk_state, risk_level)),
        "risk_notes": _build_risk_notes(payload, status, risk_items),
        "manual_required_text": "硬风险来自本地缓存或旧工作台事实包；缺失时必须手动刷新/权限校验，不能视为无风险。",
        "deepseek_called": False,
    }
    packet.update(
        build_legacy_packet_decision_contract(
            payload,
            label="硬风险",
            status=status,
            data_status=data_status,
            recovery_state=recovery_state,
            capability_state=capability_state,
        )
    )
    return packet
