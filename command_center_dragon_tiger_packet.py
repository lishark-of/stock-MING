from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_legacy_packet_contract import build_legacy_packet_decision_contract


MAX_ROWS = 8
MAX_RISK_NOTES = 6


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


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = to_text(value)
        if text:
            return text
    return default


def _dedupe_text(values: Any, limit: int = MAX_RISK_NOTES) -> list[str]:
    raw_values = values if isinstance(values, (list, tuple)) else [values]
    items = []
    seen = set()
    for item in raw_values:
        if isinstance(item, Mapping):
            text = _first_text(item.get("message"), item.get("summary"), item.get("reason"), item.get("label"))
        else:
            text = to_text(item)
        if text and text not in seen:
            seen.add(text)
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _ticker_base(value: Any) -> str:
    text = to_text(value).upper()
    return text.split(".")[0] if text else ""


def _source_from_state(state_map: Mapping[str, Any], live_packet: Mapping[str, Any]) -> dict:
    existing = as_mapping(state_map.get("command_center_dragon_tiger_packet"))
    if existing:
        return {"payload": existing, "source_key": "command_center_dragon_tiger_packet"}

    facts = as_mapping(state_map.get("a_share_professional_facts"))
    dragon = as_mapping(facts.get("dragon_tiger"))
    if dragon:
        return {"payload": dragon, "source_key": "a_share_professional_facts.dragon_tiger"}

    facts_packet = as_mapping(state_map.get("command_center_facts_packet"))
    for item in as_list(facts_packet.get("items")):
        item_map = as_mapping(item)
        if item_map.get("key") == "dragon_tiger":
            return {"payload": item_map, "source_key": "command_center_facts_packet.items.dragon_tiger"}

    live_dragon = as_mapping(as_mapping(live_packet.get("facts")).get("dragon_tiger") or live_packet.get("dragon_tiger"))
    if live_dragon:
        return {"payload": live_dragon, "source_key": "command_center_live_packet.dragon_tiger"}

    return {"payload": {}, "source_key": ""}


def _status_from(payload: Mapping[str, Any]) -> str:
    raw_status = to_text(payload.get("status")).lower()
    if raw_status in {"ready", "ok", "completed", "success"}:
        return "ready"
    if raw_status in {"failed", "error", "failure"}:
        return "failed"
    if payload.get("available") is True:
        return "ready"
    state = to_text(payload.get("state") or payload.get("capability_state")).lower()
    if state == "available":
        return "ready"
    if state in {"permission_denied", "disabled_this_session", "failed", "network_failed", "not_configured"}:
        return "failed"
    if payload:
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
    if capability_state in {"permission_denied", "disabled_this_session", "network_failed", "not_configured", "failed"}:
        return "blocked"
    return "waiting"


def _normalize_rows(value: Any) -> list[dict]:
    rows = []
    for item in as_list(value):
        payload = as_mapping(item)
        if not payload:
            continue
        rows.append(
            {
                "name": _first_text(payload.get("name"), payload.get("exalter"), payload.get("营业部名称"), default="席位"),
                "buy": to_number(payload.get("buy")),
                "sell": to_number(payload.get("sell")),
                "net_buy": to_number(payload.get("net_buy") or payload.get("net_amount")),
            }
        )
        if len(rows) >= MAX_ROWS:
            break
    return rows


def _activity_state(status: str, net_buy_amount_yi: int | float | None, inst_rows: list[dict]) -> str:
    if status == "waiting":
        return "待验证"
    if status != "ready":
        return "近期无上榜或不可用"
    if net_buy_amount_yi is not None:
        if net_buy_amount_yi > 0:
            return "席位净买入"
        if net_buy_amount_yi < 0:
            return "席位净卖出"
    if inst_rows:
        return "有席位明细"
    return "已上榜待复核"


def _build_risk_notes(payload: Mapping[str, Any], status: str, activity_state: str) -> list[str]:
    notes = []
    for key in ("message", "warning", "error", "risk", "note"):
        text = to_text(payload.get(key))
        if text and text != "暂无可验证数据":
            notes.append(text)
    if status != "ready":
        notes.append("近期无龙虎榜记录只说明没有可验证上榜事件，不等于机构支持或无风险。")
    if activity_state == "席位净买入":
        notes.append("龙虎榜净买入只作席位行为线索，不单独构成买入理由。")
    if activity_state == "席位净卖出":
        notes.append("龙虎榜净卖出需要结合资金流、价格纪律和风险预算复核。")
    notes.append("页面打开不会自动请求 Tushare top_list/top_inst；需要手动刷新后再验证。")
    return _dedupe_text(notes)


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
    activity_state: str,
    net_buy_amount_yi: int | float | None,
    inst_rows: list[dict],
) -> str:
    if status == "ready":
        parts = [f"席位行为：{activity_state}"]
        if net_buy_amount_yi is not None:
            parts.append(f"净买入 {net_buy_amount_yi} 亿")
        if inst_rows:
            parts.append(f"席位明细 {len(inst_rows)} 条")
        if len(parts) == 1:
            parts.append("接口可用，上榜明细待验证")
        return "｜".join(parts)
    if recovery_state == "blocked":
        return f"{status_label}：龙虎榜不能进入席位行为依据。"
    return "龙虎榜待手动刷新；未回流前不能确认席位行为或机构参与。"


def _build_evidence_items(
    status: str,
    status_label: str,
    verification_status: str,
    activity_state: str,
    net_buy_amount_yi: int | float | None,
    inst_rows: list[dict],
) -> list[dict]:
    if status != "ready":
        return [
            {
                "key": "dragon_tiger",
                "label": "龙虎榜",
                "value": status_label,
                "status": verification_status,
            }
        ]
    return [
        {
            "key": "activity_state",
            "label": "席位行为",
            "value": activity_state,
            "status": verification_status,
        },
        {
            "key": "net_buy_amount",
            "label": "净买入",
            "value": f"{net_buy_amount_yi} 亿" if net_buy_amount_yi is not None else "待验证",
            "status": "已验证" if net_buy_amount_yi is not None else "待验证",
        },
        {
            "key": "inst_rows",
            "label": "席位明细",
            "value": f"{len(inst_rows)} 条" if inst_rows else "待验证",
            "status": "已回流" if inst_rows else "待验证",
        },
    ]


def _action_hint(status: str, capability_state: str, activity_state: str) -> str:
    if status == "ready" and activity_state == "席位净买入":
        return "把龙虎榜净买入作为席位行为线索；仍需资金流、价格纪律和仓位预算共同确认。"
    if status == "ready" and activity_state == "席位净卖出":
        return "先复核席位净卖出是否削弱短线情绪；策略应偏观察或降风险。"
    if status == "ready":
        return "把龙虎榜作为短线席位和情绪线索；不上榜或无明细不能写成机构支持。"
    if capability_state in {"permission_denied", "disabled_this_session", "network_failed", "not_configured", "failed"}:
        return "先在数据恢复中心处理 Tushare top_list/top_inst 权限、积分、网络或接口状态。"
    return "需要时手动刷新龙虎榜能力；缺失时不把席位行为写入买入依据。"


def _decision_guardrail(status: str, activity_state: str) -> str:
    if status != "ready":
        return "缺少龙虎榜时，不能确认席位行为、机构参与或短线情绪支持。"
    if activity_state == "席位净买入":
        return "龙虎榜净买入只作辅助证据；不能单独构成买入或加仓理由。"
    if activity_state == "席位净卖出":
        return "席位净卖出需要降低短线追高冲动，并复核资金流和价格纪律。"
    return "龙虎榜只验证上榜和席位行为，不替代趋势、资金流和风险预算。"


def build_command_center_dragon_tiger_packet(
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

    status = _status_from(payload)
    data_status = _data_status(status, payload)
    capability_state = _capability_state(payload, status)
    status_label = _status_label(payload, capability_state, status)
    recovery_state = _recovery_state(status, capability_state, data_status)
    net_buy_amount_yi = to_number(payload.get("net_buy_amount_yi") or payload.get("net_buy_amount") or payload.get("net_buy"))
    inst_rows = _normalize_rows(payload.get("inst_rows"))
    activity_state = _activity_state(status, net_buy_amount_yi, inst_rows)
    verification_status = _verification_status(status, recovery_state)
    summary = _first_text(
        payload.get("summary"),
        payload.get("inst_summary"),
        payload.get("message"),
        default=(
            "龙虎榜待刷新；页面打开不会自动请求 Tushare top_list/top_inst。"
            if status == "waiting"
            else f"龙虎榜状态：{activity_state}。"
        ),
    )
    packet = {
        "status": status,
        "data_status": data_status,
        "capability_state": capability_state,
        "status_label": status_label,
        "recovery_state": recovery_state,
        "source": _first_text(payload.get("source"), default="Tushare 龙虎榜缓存"),
        "source_key": to_text(source.get("source_key")),
        "api": _first_text(payload.get("api"), default="top_list/top_inst"),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("checked_at"), payload.get("latest_date"), payload.get("trade_date")),
        "checked_at": _first_text(payload.get("checked_at"), payload.get("updated_at")),
        "trade_date": _first_text(payload.get("latest_date"), payload.get("trade_date"), payload.get("date")),
        "target": _first_text(target, existing_target),
        "ticker": _first_text(payload.get("ticker"), payload.get("ts_code"), target),
        "reason": to_text(payload.get("reason")),
        "close": to_number(payload.get("close")),
        "pct_change": to_number(payload.get("pct_change")),
        "buy_amount_yi": to_number(payload.get("buy_amount_yi") or payload.get("buy_amount")),
        "sell_amount_yi": to_number(payload.get("sell_amount_yi") or payload.get("sell_amount")),
        "net_buy_amount_yi": net_buy_amount_yi,
        "inst_summary": to_text(payload.get("inst_summary")),
        "inst_rows": inst_rows,
        "raw_rows": [as_mapping(item) for item in as_list(payload.get("raw_rows"))[:MAX_ROWS]],
        "activity_state": activity_state,
        "summary": summary,
        "packet_role": "A股龙虎榜席位证据",
        "verification_status": verification_status,
        "evidence_summary": _first_text(
            payload.get("evidence_summary"),
            default=_build_evidence_summary(
                status,
                status_label,
                recovery_state,
                activity_state,
                net_buy_amount_yi,
                inst_rows,
            ),
        ),
        "evidence_items": as_list(payload.get("evidence_items"))
        or _build_evidence_items(
            status,
            status_label,
            verification_status,
            activity_state,
            net_buy_amount_yi,
            inst_rows,
        ),
        "action_hint": _first_text(payload.get("action_hint"), default=_action_hint(status, capability_state, activity_state)),
        "decision_guardrail": _first_text(payload.get("decision_guardrail"), default=_decision_guardrail(status, activity_state)),
        "risk_notes": _build_risk_notes(payload, status, activity_state),
        "manual_required_text": "龙虎榜来自 Tushare top_list/top_inst 缓存；缺失时必须手动刷新或权限校验，综合中心不会自动请求。",
        "deepseek_called": False,
    }
    packet.update(
        build_legacy_packet_decision_contract(
            payload,
            label="龙虎榜",
            status=status,
            data_status=data_status,
            recovery_state=recovery_state,
            capability_state=capability_state,
        )
    )
    return packet
