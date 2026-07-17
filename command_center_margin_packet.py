from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_legacy_packet_contract import build_legacy_packet_decision_contract


MAX_RISK_NOTES = 6
LOCAL_READ_FALSE_SAFETY_FIELDS = (
    "external",
    "external_calls_triggered",
    "provider_or_model_calls",
    "provider_called",
    "model_called",
    "worker_called",
    "tushare_called",
    "deepseek_called",
    "github_called",
    "trade_called",
    "trading_called",
    "broker_called",
    "order_called",
    "real_trading_enabled",
    "contains_secret",
)
LOCAL_READ_TRUE_SAFETY_FIELDS = ("does_not_execute_trades", "does_not_modify_strategy_action")


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
    existing = as_mapping(state_map.get("command_center_margin_packet"))
    if existing:
        return {"payload": existing, "source_key": "command_center_margin_packet"}

    facts = as_mapping(state_map.get("a_share_professional_facts"))
    margin = as_mapping(facts.get("margin"))
    if margin:
        return {"payload": margin, "source_key": "a_share_professional_facts.margin"}

    facts_packet = as_mapping(state_map.get("command_center_facts_packet"))
    for item in facts_packet.get("items") or []:
        item_map = as_mapping(item)
        if item_map.get("key") == "margin":
            return {"payload": item_map, "source_key": "command_center_facts_packet.items.margin"}

    live_margin = as_mapping(as_mapping(live_packet.get("facts")).get("margin") or live_packet.get("margin"))
    if live_margin:
        return {"payload": live_margin, "source_key": "command_center_live_packet.margin"}

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


def _leverage_state(
    financing_balance_yi: int | float | None,
    financing_buy_yi: int | float | None,
    margin_balance_yi: int | float | None,
    status: str,
) -> str:
    if status in {"waiting", "failed"} or all(value is None for value in [financing_balance_yi, financing_buy_yi, margin_balance_yi]):
        return "待验证"
    if financing_buy_yi is not None and financing_buy_yi > 0:
        return "融资买入增加"
    if financing_buy_yi is not None and financing_buy_yi < 0:
        return "融资买入减少"
    if margin_balance_yi is not None or financing_balance_yi is not None:
        return "杠杆余额可参考"
    return "中性待验证"


def _build_risk_notes(payload: Mapping[str, Any], status: str, leverage_state: str) -> list[str]:
    notes = []
    for key in ("message", "warning", "error", "risk", "note"):
        text = to_text(payload.get(key))
        if text and text != "暂无可验证数据":
            notes.append(text)
    if status != "ready":
        notes.append("融资融券不可用或权限不足时，不能假设杠杆资金改善。")
    if leverage_state == "融资买入增加":
        notes.append("融资买入增加只代表杠杆资金行为，不等于主力资金或机构资金。")
    if leverage_state == "融资买入减少":
        notes.append("融资买入减少需要结合价格纪律和风险预算复核。")
    notes.append("页面打开不会自动请求 Tushare margin_detail；需要手动刷新后再验证。")
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
    leverage_state: str,
    financing_balance_yi: int | float | None,
    financing_buy_yi: int | float | None,
    margin_balance_yi: int | float | None,
) -> str:
    if status == "ready":
        parts = [f"杠杆状态：{leverage_state}"]
        if financing_buy_yi is not None:
            parts.append(f"融资买入 {financing_buy_yi} 亿")
        if financing_balance_yi is not None:
            parts.append(f"融资余额 {financing_balance_yi} 亿")
        if margin_balance_yi is not None:
            parts.append(f"两融余额 {margin_balance_yi} 亿")
        if len(parts) == 1:
            parts.append("接口可用，个股余额待验证")
        return "｜".join(parts)
    if recovery_state == "blocked":
        return f"{status_label}：融资融券不能进入杠杆依据。"
    return "融资融券待手动刷新；未回流前不能确认杠杆资金是否改善。"


def _build_evidence_items(
    status: str,
    status_label: str,
    verification_status: str,
    leverage_state: str,
    financing_balance_yi: int | float | None,
    financing_buy_yi: int | float | None,
    margin_balance_yi: int | float | None,
) -> list[dict]:
    if status != "ready":
        return [
            {
                "key": "margin",
                "label": "融资融券",
                "value": status_label,
                "status": verification_status,
            }
        ]
    return [
        {
            "key": "leverage_state",
            "label": "杠杆状态",
            "value": leverage_state,
            "status": verification_status,
        },
        {
            "key": "financing_buy",
            "label": "融资买入",
            "value": f"{financing_buy_yi} 亿" if financing_buy_yi is not None else "待验证",
            "status": "已验证" if financing_buy_yi is not None else "待验证",
        },
        {
            "key": "financing_balance",
            "label": "融资余额",
            "value": f"{financing_balance_yi} 亿" if financing_balance_yi is not None else "待验证",
            "status": "已验证" if financing_balance_yi is not None else "待验证",
        },
        {
            "key": "margin_balance",
            "label": "两融余额",
            "value": f"{margin_balance_yi} 亿" if margin_balance_yi is not None else "待验证",
            "status": "已验证" if margin_balance_yi is not None else "待验证",
        },
    ]


def _action_hint(status: str, capability_state: str, leverage_state: str) -> str:
    if status == "ready" and leverage_state == "融资买入增加":
        return "把融资买入增加作为杠杆行为证据；不能直接等同主力资金改善或允许加融资。"
    if status == "ready" and leverage_state == "融资买入减少":
        return "先复核融资买入减少是否削弱风险偏好；策略应偏观察或降风险。"
    if status == "ready":
        return "把融资融券作为杠杆和风险预算证据；执行前仍需价格纪律确认。"
    if capability_state in {"permission_denied", "disabled_this_session", "network_failed", "not_configured", "failed"}:
        return "先在数据恢复中心处理 Tushare margin_detail 权限、积分、网络或接口状态。"
    return "需要时手动刷新融资融券能力；缺失时融资比例和风险预算必须保守。"


def _decision_guardrail(status: str, leverage_state: str) -> str:
    if status != "ready":
        return "缺少融资融券时，不能确认杠杆资金、融资余额或风险预算改善。"
    if leverage_state == "融资买入增加":
        return "融资买入增加不等于主力资金改善；不能单独支持加融资或放大仓位。"
    if leverage_state == "融资买入减少":
        return "融资买入减少时先降低杠杆假设，复核价格纪律和现金缓冲。"
    return "融资融券只验证杠杆变化，不替代资金流、趋势和纪律条件。"


def build_command_center_margin_packet(
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
    financing_balance_yi = to_number(payload.get("financing_balance_yi"))
    financing_buy_yi = to_number(payload.get("financing_buy_yi"))
    margin_balance_yi = to_number(payload.get("margin_balance_yi"))
    short_sell_volume = to_number(payload.get("short_sell_volume"))
    leverage_state = _leverage_state(financing_balance_yi, financing_buy_yi, margin_balance_yi, status)
    verification_status = _verification_status(status, recovery_state)
    summary = _first_text(
        payload.get("summary"),
        payload.get("evidence"),
        payload.get("message"),
        default=(
            "融资融券待刷新；页面打开不会自动请求 Tushare margin_detail。"
            if status == "waiting"
            else f"融资融券状态：{leverage_state}。"
        ),
    )
    packet = {
        "status": status,
        "data_status": data_status,
        "capability_state": capability_state,
        "status_label": status_label,
        "recovery_state": recovery_state,
        "source": _first_text(payload.get("source"), default="Tushare margin_detail 缓存"),
        "source_key": to_text(source.get("source_key")),
        "api": _first_text(payload.get("api"), default="margin_detail"),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("checked_at"), payload.get("date"), payload.get("trade_date")),
        "checked_at": _first_text(payload.get("checked_at"), payload.get("updated_at")),
        "trade_date": _first_text(payload.get("date"), payload.get("trade_date"), payload.get("latest_date")),
        "target": _first_text(target, existing_target),
        "ticker": _first_text(payload.get("ticker"), payload.get("ts_code"), target),
        "financing_balance_yi": financing_balance_yi,
        "financing_buy_yi": financing_buy_yi,
        "margin_balance_yi": margin_balance_yi,
        "short_sell_volume": short_sell_volume,
        "leverage_state": leverage_state,
        "summary": summary,
        "packet_role": "A股融资融券杠杆证据",
        "verification_status": verification_status,
        "evidence_summary": _first_text(
            payload.get("evidence_summary"),
            default=_build_evidence_summary(
                status,
                status_label,
                recovery_state,
                leverage_state,
                financing_balance_yi,
                financing_buy_yi,
                margin_balance_yi,
            ),
        ),
        "evidence_items": as_list(payload.get("evidence_items"))
        or _build_evidence_items(
            status,
            status_label,
            verification_status,
            leverage_state,
            financing_balance_yi,
            financing_buy_yi,
            margin_balance_yi,
        ),
        "action_hint": _first_text(payload.get("action_hint"), default=_action_hint(status, capability_state, leverage_state)),
        "decision_guardrail": _first_text(payload.get("decision_guardrail"), default=_decision_guardrail(status, leverage_state)),
        "risk_notes": _build_risk_notes(payload, status, leverage_state),
        "manual_required_text": "融资融券来自 Tushare margin_detail 缓存；缺失时必须手动刷新或权限校验，综合中心不会自动请求。",
    }
    packet.update(
        build_legacy_packet_decision_contract(
            payload,
            label="融资融券",
            status=status,
            data_status=data_status,
            recovery_state=recovery_state,
            capability_state=capability_state,
        )
    )
    if "warnings" in payload:
        packet["warnings"] = payload.get("warnings")
    else:
        packet.pop("warnings", None)
    for field in (*LOCAL_READ_FALSE_SAFETY_FIELDS, *LOCAL_READ_TRUE_SAFETY_FIELDS):
        if field in payload:
            packet[field] = payload[field]
        else:
            packet.pop(field, None)
    return packet
