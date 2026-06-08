from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


EVIDENCE_DEFS = (
    (
        "moneyflow_packet",
        "moneyflow",
        "个股资金流",
        "flow_state",
        ("five_day_main_net_yi", "main_net_yi"),
        "亿",
        1,
        "验证资金是否支持当前动作。",
    ),
    (
        "hard_risk_packet",
        "hard_risk",
        "公告/硬风险",
        "risk_state",
        ("risk_item_count",),
        "项",
        1,
        "排查公告、减持、质押、解禁等硬风险阻断。",
    ),
    (
        "margin_packet",
        "margin",
        "融资融券",
        "leverage_state",
        ("financing_buy_yi", "financing_balance_yi"),
        "亿",
        2,
        "观察杠杆变化和融资风险预算。",
    ),
    (
        "limit_emotion_packet",
        "limit_emotion",
        "涨跌停/情绪",
        "emotion_state",
        ("distance_to_up_pct", "up_limit"),
        "",
        2,
        "识别过热、追高和情绪边界。",
    ),
    (
        "dragon_tiger_packet",
        "dragon_tiger",
        "龙虎榜",
        "activity_state",
        ("net_buy_amount_yi",),
        "亿",
        3,
        "识别席位行为和短线情绪线索。",
    ),
    (
        "chip_packet",
        "chip_radar",
        "筹码/胜率",
        "pressure_state",
        ("winner_rate",),
        "%",
        3,
        "验证压力位、筹码结构和胜率口径。",
    ),
)


EVIDENCE_ACTIONS = {
    "moneyflow": {
        "button_label": "手动刷新个股资金流",
        "toolbox_entry": "高级工具箱 / A股专业实盘 / 个股资金流",
        "legacy_tab": "今日关注池",
        "writes_packet": "command_center_moneyflow_packet",
    },
    "hard_risk": {
        "button_label": "检测公告/硬风险",
        "toolbox_entry": "高级工具箱 / 天眼风控 / A股公告风险",
        "legacy_tab": "天眼风控",
        "writes_packet": "command_center_hard_risk_packet",
    },
    "margin": {
        "button_label": "手动刷新融资融券",
        "toolbox_entry": "高级工具箱 / 融资 ETF / 融资融券",
        "legacy_tab": "融资 ETF",
        "writes_packet": "command_center_margin_packet",
    },
    "limit_emotion": {
        "button_label": "手动刷新涨跌停/情绪",
        "toolbox_entry": "高级工具箱 / 数据源体检 / 涨跌停情绪",
        "legacy_tab": "数据源体检",
        "writes_packet": "command_center_limit_emotion_packet",
    },
    "dragon_tiger": {
        "button_label": "手动刷新龙虎榜",
        "toolbox_entry": "高级工具箱 / 下一票雷达 / 龙虎榜",
        "legacy_tab": "下一票雷达",
        "writes_packet": "command_center_dragon_tiger_packet",
    },
    "chip_radar": {
        "button_label": "手动刷新筹码/胜率",
        "toolbox_entry": "高级工具箱 / 量化推演 / 筹码胜率",
        "legacy_tab": "量化推演",
        "writes_packet": "command_center_chip_packet",
    },
}


WRITES_PACKET_TO_EVIDENCE_KEY = {
    config["writes_packet"]: key
    for key, config in EVIDENCE_ACTIONS.items()
    if config.get("writes_packet")
}

CORE_EVIDENCE_KEYS = ("dragon_tiger", "margin", "limit_emotion")

CORE_EVIDENCE_GUARDRAILS = {
    "dragon_tiger": "龙虎榜只验证席位行为；无上榜或受限不能写成机构支持。",
    "margin": "融资融券只验证杠杆变化；缺失时不能假设融资资金改善或允许加融资。",
    "limit_emotion": "涨跌停/情绪只验证追高边界；缺失时不能确认题材温度或涨跌停风险。",
}


FACT_LINEAGE_DEFS = (
    {
        "fact_key": "moneyflow",
        "fact_name": "资金流",
        "source_packet": "command_center_moneyflow_packet",
        "packet_keys": ("moneyflow_packet", "command_center_moneyflow_packet"),
        "source_interfaces": ("tushare.moneyflow",),
        "data_date_keys": ("date", "trade_date"),
        "local_fetched_at_keys": ("updated_at", "checked_at", "generated_at"),
        "enters_decision_explanation": True,
        "enters_strategy_trace": True,
        "enters_core_action": False,
        "enters_projection": True,
        "enters_deepseek_prompt": True,
    },
    {
        "fact_key": "dragon_tiger",
        "fact_name": "龙虎榜",
        "source_packet": "command_center_dragon_tiger_packet",
        "packet_keys": ("dragon_tiger_packet", "command_center_dragon_tiger_packet"),
        "source_interfaces": ("tushare.top_list", "tushare.top_inst"),
        "data_date_keys": ("latest_date", "date", "trade_date"),
        "local_fetched_at_keys": ("updated_at", "checked_at", "generated_at"),
        "enters_decision_explanation": True,
        "enters_strategy_trace": True,
        "enters_core_action": False,
        "enters_projection": True,
        "enters_deepseek_prompt": True,
    },
    {
        "fact_key": "margin",
        "fact_name": "融资融券",
        "source_packet": "command_center_margin_packet",
        "packet_keys": ("margin_packet", "command_center_margin_packet"),
        "source_interfaces": ("tushare.margin_detail",),
        "data_date_keys": ("date", "trade_date"),
        "local_fetched_at_keys": ("updated_at", "checked_at", "generated_at"),
        "enters_decision_explanation": True,
        "enters_strategy_trace": True,
        "enters_core_action": False,
        "enters_projection": True,
        "enters_deepseek_prompt": True,
    },
    {
        "fact_key": "hard_risk",
        "fact_name": "公告/硬风险",
        "source_packet": "command_center_hard_risk_packet",
        "packet_keys": ("hard_risk_packet", "command_center_hard_risk_packet"),
        "source_interfaces": (
            "tushare.anns_d",
            "tushare.forecast",
            "tushare.stk_holdertrade",
            "tushare.share_float",
            "tushare.pledge_stat",
            "tushare.pledge_detail",
            "tushare.stk_surv",
        ),
        "data_date_keys": ("date", "ann_date", "trade_date", "end_date", "float_date", "surv_date"),
        "local_fetched_at_keys": ("updated_at", "checked_at", "generated_at"),
        "enters_decision_explanation": True,
        "enters_strategy_trace": True,
        "enters_core_action": False,
        "enters_projection": True,
        "enters_deepseek_prompt": True,
    },
    {
        "fact_key": "limit_emotion",
        "fact_name": "涨跌停/情绪",
        "source_packet": "command_center_limit_emotion_packet",
        "packet_keys": ("limit_emotion_packet", "command_center_limit_emotion_packet"),
        "source_interfaces": ("tushare.stk_limit", "tushare.limit_list_d", "tushare.limit_cpt_list"),
        "data_date_keys": ("latest_date", "concept_date", "trade_date", "date"),
        "local_fetched_at_keys": ("updated_at", "checked_at", "generated_at"),
        "enters_decision_explanation": True,
        "enters_strategy_trace": False,
        "enters_core_action": False,
        "enters_projection": True,
        "enters_deepseek_prompt": True,
    },
    {
        "fact_key": "chip_radar",
        "fact_name": "筹码/胜率",
        "source_packet": "command_center_chip_packet",
        "packet_keys": ("chip_packet", "command_center_chip_packet"),
        "source_interfaces": ("tushare.cyq_perf", "tushare.cyq_chips"),
        "data_date_keys": ("trade_date", "date"),
        "local_fetched_at_keys": ("updated_at", "checked_at", "generated_at"),
        "enters_decision_explanation": True,
        "enters_strategy_trace": False,
        "enters_core_action": False,
        "enters_projection": True,
        "enters_deepseek_prompt": True,
    },
    {
        "fact_key": "volume_amount",
        "fact_name": "成交额/成交量",
        "source_packet": "verified_technical_facts",
        "packet_keys": ("verified_technical_facts", "technical_snapshot", "market_packet", "facts_packet"),
        "source_interfaces": ("tushare.daily", "tushare.daily_basic"),
        "data_date_keys": ("trade_date", "date", "latest_date", "asof"),
        "local_fetched_at_keys": ("updated_at", "checked_at", "generated_at"),
        "enters_decision_explanation": True,
        "enters_strategy_trace": False,
        "enters_core_action": False,
        "enters_projection": True,
        "enters_deepseek_prompt": True,
    },
)


FACT_LINEAGE_STATUS_LABELS = {
    "verified": "已验证",
    "blocked": "阻断",
    "missing": "缺失",
    "stale": "缓存过期",
    "cached": "使用缓存",
    "pending": "待验证",
}


FACT_LINEAGE_STATUS_PRIORITY = {
    "verified": 0,
    "pending": 1,
    "cached": 2,
    "stale": 3,
    "missing": 4,
    "blocked": 5,
}


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
        text = value.strip().replace(",", "").replace("%", "").replace("亿", "")
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


def _first_number(packet: Mapping[str, Any], keys: tuple[str, ...]) -> int | float | None:
    for key in keys:
        number = to_number(packet.get(key))
        if number is not None:
            return number
    return None


def _first_text_from_mapping(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        text = to_text(payload.get(key))
        if text:
            return text
    return ""


def _lineage_payload_candidates(value: Any) -> list[dict]:
    payload = as_mapping(value)
    if not payload:
        return []
    candidates = [payload]
    for key in (
        "items",
        "rows",
        "records",
        "evidence_items",
        "risk_items",
        "alerts",
        "announcements",
        "sections",
        "verified_technical_facts",
        "data",
    ):
        raw = payload.get(key)
        if isinstance(raw, Mapping):
            candidates.append(as_mapping(raw))
        for item in as_list(raw):
            item_map = as_mapping(item)
            if item_map:
                candidates.append(item_map)
                candidates.extend(_lineage_payload_candidates(item_map))
    return candidates


def _is_reliable_external_date_text(value: Any, *, local_fetched_at: str = "") -> bool:
    text = to_text(value)
    if not text or text == local_fetched_at:
        return False
    # External trade/announcement dates should be date-like. Local fetch timestamps
    # such as 2026-06-08T16:33:12 must stay in local_fetched_at, not data_date.
    if "T" in text or ":" in text:
        return False
    return True


def _extract_lineage_date(payload: Mapping[str, Any], keys: tuple[str, ...], *, local_fetched_at: str = "") -> str:
    for candidate in _lineage_payload_candidates(payload):
        text = _first_text_from_mapping(candidate, keys)
        if _is_reliable_external_date_text(text, local_fetched_at=local_fetched_at):
            return text
    return ""


def _extract_lineage_local_fetched_at(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for candidate in _lineage_payload_candidates(payload):
        text = _first_text_from_mapping(candidate, keys)
        if text:
            return text
    return ""


def _lineage_packet_from_snapshot(snapshot: Mapping[str, Any], packet_keys: tuple[str, ...]) -> dict:
    for key in packet_keys:
        payload = as_mapping(snapshot.get(key))
        if payload:
            return payload
    professional = as_mapping(snapshot.get("a_share_professional_facts"))
    for key in packet_keys:
        payload = as_mapping(professional.get(key))
        if payload:
            return payload
    verified = as_mapping(professional.get("verified_technical_facts"))
    if verified and any(key == "verified_technical_facts" for key in packet_keys):
        return verified
    return {}


def _evidence_item_by_key(evidence_radar_packet: Mapping[str, Any]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for group_key in (
        "items",
        "decision_evidence_queue",
        "support_items",
        "blocker_items",
        "cached_items",
        "missing_items",
    ):
        for raw in as_list(evidence_radar_packet.get(group_key)):
            item = as_mapping(raw)
            key = to_text(item.get("key"))
            if key and key not in result:
                result[key] = item
    return result


def _normalize_lineage_status_from_evidence(item: Mapping[str, Any]) -> str:
    evidence_state = to_text(item.get("evidence_state") or item.get("recovery_state")).lower()
    status = to_text(item.get("status")).lower()
    data_status = to_text(item.get("data_status")).lower()
    tone = to_text(item.get("tone")).lower()
    raw_values = {evidence_state, status, data_status, tone}
    if raw_values & {"blocked", "failed", "danger", "permission_denied", "no_permission", "forbidden"}:
        return "blocked"
    if raw_values & {"missing", "empty", "unavailable"}:
        return "missing"
    if raw_values & {"stale", "expired"}:
        return "stale"
    if raw_values & {"cached", "cache"}:
        return "cached"
    if evidence_state == "supporting" or raw_values & {"ready", "verified", "success", "available"}:
        return "verified"
    if raw_values & {"waiting", "pending", "partial"}:
        return "pending"
    return ""


def _normalize_lineage_status_from_packet(packet: Mapping[str, Any]) -> str:
    if not packet:
        return "missing"
    status = to_text(packet.get("status")).lower()
    data_status = to_text(packet.get("data_status")).lower()
    tone = to_text(packet.get("tone")).lower()
    if bool(packet.get("stale")):
        return "stale"
    raw_values = {status, data_status, tone}
    if raw_values & {"blocked", "failed", "danger", "permission_denied", "no_permission", "forbidden"}:
        return "blocked"
    if raw_values & {"missing", "empty", "unavailable"}:
        return "missing"
    if raw_values & {"stale", "expired"}:
        return "stale"
    if raw_values & {"cached", "cache"}:
        return "cached"
    if raw_values & {"ready", "verified", "success", "available", "completed"}:
        return "verified"
    if raw_values & {"waiting", "pending", "partial"}:
        return "pending"
    return "pending"


def _merge_lineage_status(*statuses: str) -> str:
    cleaned = [status for status in statuses if status in FACT_LINEAGE_STATUS_PRIORITY]
    if not cleaned:
        return "pending"
    return max(cleaned, key=lambda status: FACT_LINEAGE_STATUS_PRIORITY.get(status, 0))


def _lineage_status_tone(status: str) -> str:
    if status == "verified":
        return "success"
    if status in {"cached", "stale", "pending"}:
        return "warning"
    if status in {"blocked", "missing"}:
        return "danger"
    return "muted"


def _lineage_usage_note(fact_name: str, status: str, enters_core_action: bool) -> str:
    boundary = "已由现有策略算法显式使用。" if enters_core_action else "进入证据链/风险解释和路径置信度说明，不直接覆盖核心交易 action。"
    if status != "verified":
        return f"{fact_name}当前为{FACT_LINEAGE_STATUS_LABELS.get(status, '待验证')}，不能当作已验证事实；{boundary}"
    return boundary


def _build_lineage_item(
    definition: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    evidence_items: Mapping[str, dict],
) -> dict:
    fact_key = to_text(definition.get("fact_key"))
    packet = _lineage_packet_from_snapshot(snapshot, tuple(definition.get("packet_keys") or ()))
    evidence_status = _normalize_lineage_status_from_evidence(evidence_items.get(fact_key) or {})
    packet_status = _normalize_lineage_status_from_packet(packet)
    status = _merge_lineage_status(evidence_status, packet_status)
    local_fetched_at = _extract_lineage_local_fetched_at(
        packet,
        tuple(definition.get("local_fetched_at_keys") or ()),
    )
    data_date = _extract_lineage_date(
        packet,
        tuple(definition.get("data_date_keys") or ()),
        local_fetched_at=local_fetched_at,
    )
    enters_core_action = bool(definition.get("enters_core_action"))
    fact_name = to_text(definition.get("fact_name"), fact_key)
    return {
        "fact_key": fact_key,
        "fact_name": fact_name,
        "status": status,
        "status_label": FACT_LINEAGE_STATUS_LABELS.get(status, "待验证"),
        "tone": _lineage_status_tone(status),
        "data_date": data_date or None,
        "local_fetched_at": local_fetched_at or None,
        "source_interfaces": list(definition.get("source_interfaces") or []),
        "source_packet": to_text(definition.get("source_packet")),
        "enters_decision_explanation": bool(definition.get("enters_decision_explanation")),
        "enters_strategy_trace": bool(definition.get("enters_strategy_trace")),
        "enters_core_action": enters_core_action,
        "enters_projection": bool(definition.get("enters_projection")),
        "enters_deepseek_prompt": bool(definition.get("enters_deepseek_prompt")),
        "usage_note": _lineage_usage_note(fact_name, status, enters_core_action),
        "deepseek_called": False,
    }


def build_a_share_fact_lineage_summary(snapshot: Any = None, evidence_radar_packet: Any = None) -> dict:
    payload = as_mapping(snapshot)
    evidence = as_mapping(evidence_radar_packet) or as_mapping(payload.get("command_center_evidence_radar_packet")) or as_mapping(payload.get("a_share_evidence_packet"))
    evidence_items = _evidence_item_by_key(evidence)
    items = [_build_lineage_item(definition, payload, evidence_items) for definition in FACT_LINEAGE_DEFS]
    counts = {key: 0 for key in FACT_LINEAGE_STATUS_LABELS}
    for item in items:
        status = to_text(item.get("status"))
        if status in counts:
            counts[status] += 1
    updated_at = _first_text(
        *[item.get("local_fetched_at") for item in items if item.get("local_fetched_at")],
        payload.get("timestamp"),
        payload.get("updated_at"),
    )
    summary = (
        f"已验证 {counts['verified']}｜阻断 {counts['blocked']}｜缓存 {counts['cached']}｜"
        f"过期 {counts['stale']}｜缺失 {counts['missing']}｜待验证 {counts['pending']}"
    )
    return {
        "schema_version": "a_share_fact_lineage_summary.v1",
        "updated_at": updated_at or None,
        "summary": summary,
        "items": items,
        "counts": counts,
        "boundary_note": "A 股事实用于证据链、风险解释和路径置信度说明，不直接覆盖核心交易 action，除非现有策略算法已经显式使用。",
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def _status_label(status: str, data_status: str) -> str:
    if status == "failed":
        return "失败/受限"
    if data_status == "ready":
        return "已刷新"
    if data_status == "cached":
        return "使用缓存"
    return "待验证"


def _status_tone(status: str, data_status: str) -> str:
    if status == "failed":
        return "failed"
    if data_status == "ready":
        return "ready"
    if data_status == "cached":
        return "stale"
    return "missing"


def _evidence_state(status: str, data_status: str) -> str:
    if status == "failed":
        return "blocked"
    if data_status == "ready":
        return "supporting"
    if data_status == "cached":
        return "cached"
    return "missing"


def _evidence_label(evidence_state: str) -> str:
    return {
        "supporting": "支持证据",
        "blocked": "阻断证据",
        "cached": "缓存证据",
        "missing": "缺失证据",
    }.get(evidence_state, "待验证证据")


def _decision_signal(label: str, headline: str, evidence_state: str) -> str:
    if evidence_state == "supporting":
        return f"{label}已刷新，可辅助验证：{headline}"
    if evidence_state == "blocked":
        return f"{label}失败/受限，不能支撑加仓或放大仓位。"
    if evidence_state == "cached":
        return f"{label}使用缓存，执行前必须复核日期和口径。"
    return f"{label}待验证，当前不进入核心决策依据。"


def _evidence_action_hint(label: str, evidence_state: str) -> str:
    if evidence_state == "blocked":
        return f"先确认{label}是否权限不足、接口失败或本会话跳过；未恢复前不要把缺失写成利好。"
    if evidence_state == "cached":
        return f"交易前复核{label}交易日和更新时间；需要最新口径时手动刷新。"
    if evidence_state == "missing":
        return f"点击对应入口手动补齐{label}，补齐前只作为待验证证据。"
    return f"{label}已可辅助验证，仍需和价格纪律、仓位规则一起看。"


def _join_labels(items: Any, limit: int = 3, fallback: str = "暂无") -> str:
    labels = [to_text(as_mapping(item).get("label")) for item in as_list(items)]
    labels = [label for label in labels if label]
    if not labels:
        return fallback
    suffix = f" 等 {len(labels)} 项" if len(labels) > limit else ""
    return "、".join(labels[:limit]) + suffix


def _short_decision_signals(items: Any, limit: int = 3) -> list[str]:
    signals = []
    for raw in as_list(items):
        item = as_mapping(raw)
        text = to_text(item.get("decision_signal")) or to_text(item.get("next_action")) or to_text(item.get("headline"))
        if text:
            signals.append(text)
        if len(signals) >= limit:
            break
    return signals


def _prioritize_evidence_items(items: Any = None, promoted_key: str = "") -> list[dict]:
    rows = [as_mapping(item) for item in as_list(items) if as_mapping(item)]
    key = to_text(promoted_key)
    if not key:
        return rows
    promoted = [item for item in rows if to_text(item.get("key")) == key]
    rest = [item for item in rows if to_text(item.get("key")) != key]
    return promoted + rest


def build_recovered_evidence_modules(support_items: Any = None, limit: int = 4, promoted_key: str = "") -> list[dict]:
    modules = []
    for raw in _prioritize_evidence_items(support_items, promoted_key):
        item = as_mapping(raw)
        if not item:
            continue
        modules.append(
            {
                "key": to_text(item.get("key"), "a_share_evidence"),
                "label": to_text(item.get("label"), "A股证据"),
                "headline": to_text(item.get("headline"), "已回流"),
                "metric": to_text(item.get("metric"), "暂无数值"),
                "decision_role": to_text(item.get("decision_role"), "辅助验证。"),
                "decision_signal": to_text(item.get("decision_signal"), "已回流，可辅助验证。"),
                "source": to_text(item.get("source"), "本地 packet"),
                "updated_at": to_text(item.get("updated_at"), "暂无时间"),
                "writes_packet": to_text(as_mapping(item.get("manual_action")).get("writes_packet")),
                "deepseek_called": False,
            }
        )
        if len(modules) >= max(1, int(limit or 4)):
            break
    return modules


def recovered_evidence_summary_text(support_items: Any = None, promoted_key: str = "") -> str:
    modules = build_recovered_evidence_modules(support_items, promoted_key=promoted_key)
    if not modules:
        return "暂无已回流 A股证据模块"
    labels = [item["label"] for item in modules if item.get("label")]
    return "已回流：" + "、".join(labels[:4])


def build_core_evidence_items(items: Any = None) -> list[dict]:
    by_key = {to_text(as_mapping(item).get("key")): as_mapping(item) for item in as_list(items)}
    result = []
    for key in CORE_EVIDENCE_KEYS:
        item = by_key.get(key, {})
        manual_action = as_mapping(item.get("manual_action"))
        label = to_text(item.get("label"), EVIDENCE_ACTIONS.get(key, {}).get("button_label", key)).replace("手动刷新", "")
        evidence_state = to_text(item.get("evidence_state"), "missing")
        result.append(
            {
                "key": key,
                "label": label,
                "status_label": to_text(item.get("status_label"), "待验证"),
                "tone": to_text(item.get("tone"), "missing"),
                "evidence_state": evidence_state,
                "evidence_label": to_text(item.get("evidence_label"), "待验证证据"),
                "headline": to_text(item.get("headline"), "待验证"),
                "metric": to_text(item.get("metric"), "暂无数值"),
                "decision_role": to_text(item.get("decision_role"), "A股交易证据。"),
                "decision_signal": to_text(item.get("decision_signal"), f"{label}待验证，当前不进入核心决策依据。"),
                "guardrail": CORE_EVIDENCE_GUARDRAILS.get(key, "缺失时不能作为交易依据。"),
                "next_action": to_text(item.get("next_action"), f"手动补齐{label}后再回到综合中心复核。"),
                "source": to_text(item.get("source"), "本地 packet"),
                "updated_at": to_text(item.get("updated_at"), "暂无时间"),
                "button_label": to_text(manual_action.get("button_label"), f"手动刷新{label}"),
                "workspace_target": to_text(manual_action.get("workspace_target"), "高级工具箱（旧版保留）"),
                "workspace_state_key": to_text(manual_action.get("workspace_state_key"), "workspace_mode_v2"),
                "legacy_tab": to_text(manual_action.get("legacy_tab"), "数据源体检"),
                "legacy_tab_state_key": to_text(manual_action.get("legacy_tab_state_key"), "legacy_workspace_selected_tab"),
                "navigation_label": to_text(manual_action.get("navigation_label"), "切换到高级工具箱对应模块；不自动执行旧工具。"),
                "writes_packet": to_text(manual_action.get("writes_packet")),
                "refresh_policy": to_text(manual_action.get("refresh_policy"), "button_gated"),
                "external_call_policy": "not_triggered",
                "deepseek_called": False,
            }
        )
    return result


def core_evidence_summary_text(core_items: Any = None) -> str:
    rows = [as_mapping(item) for item in as_list(core_items) if as_mapping(item)]
    if not rows:
        return "核心证据待验证"
    ready = [item for item in rows if item.get("evidence_state") == "supporting"]
    blocked = [item for item in rows if item.get("evidence_state") == "blocked"]
    cached = [item for item in rows if item.get("evidence_state") == "cached"]
    missing = [item for item in rows if item.get("evidence_state") == "missing"]
    return f"已刷新 {len(ready)}｜受限 {len(blocked)}｜缓存 {len(cached)}｜待验证 {len(missing)}"


def _core_evidence_action_mode(item: Mapping[str, Any]) -> tuple[str, str, str]:
    state = to_text(item.get("evidence_state"), "missing")
    if state == "supporting":
        return "support", "可辅助验证", "已回流，可作为辅助证据；仍需价格纪律和仓位预算确认。"
    if state == "blocked":
        return "block", "阻断加仓", "仍受限或失败；不能把缺失写成利好，也不能支持加仓。"
    if state == "cached":
        return "verify_cache", "执行前复核", "当前使用缓存；执行前必须复核交易日、来源和覆盖口径。"
    return "manual_required", "待手动补证", "尚未形成可验证 packet；补齐前只作为待验证。"


def build_core_evidence_action_brief(core_items: Any = None) -> dict:
    rows = [as_mapping(item) for item in as_list(core_items) if as_mapping(item)]
    if not rows:
        return {
            "title": "A股核心证据执行摘要",
            "status": "missing",
            "tone": "missing",
            "headline": "核心证据待验证",
            "summary": "龙虎榜、融资融券、涨跌停/情绪尚未形成可读摘要。",
            "action_summary": "先按数据恢复中心手动补证；页面打开不会自动请求 Tushare。",
            "items": [],
            "deepseek_called": False,
            "external_call_policy": "not_triggered",
        }

    items = []
    for raw in rows:
        mode, action_label, fallback = _core_evidence_action_mode(raw)
        items.append(
            {
                "key": to_text(raw.get("key"), "core_evidence"),
                "label": to_text(raw.get("label"), "A股核心证据"),
                "status_label": to_text(raw.get("status_label"), "待验证"),
                "tone": to_text(raw.get("tone"), "missing"),
                "evidence_state": to_text(raw.get("evidence_state"), "missing"),
                "action_mode": mode,
                "action_label": action_label,
                "guardrail_text": to_text(raw.get("decision_signal") or raw.get("guardrail"), fallback),
                "next_action": to_text(raw.get("next_action"), fallback),
                "writes_packet": to_text(raw.get("writes_packet"), "command_center_packet"),
                "legacy_tab": to_text(raw.get("legacy_tab"), "高级工具箱"),
                "source": to_text(raw.get("source"), "本地 packet"),
                "updated_at": to_text(raw.get("updated_at"), "暂无时间"),
                "external_call_policy": "not_triggered",
                "deepseek_called": False,
            }
        )

    blocked = [item for item in items if item["action_mode"] == "block"]
    cached = [item for item in items if item["action_mode"] == "verify_cache"]
    missing = [item for item in items if item["action_mode"] == "manual_required"]
    support = [item for item in items if item["action_mode"] == "support"]
    if blocked:
        status = "blocked"
        tone = "failed"
        headline = "核心证据阻断加仓"
        action_summary = f"先处理{_join_labels(blocked, fallback='阻断证据')}；未恢复前不追高、不加融资、不把缺失写成利好。"
    elif cached or missing:
        status = "partial"
        tone = "stale"
        headline = "核心证据仍需复核"
        action_summary = f"{_join_labels(cached + missing, fallback='缓存/缺失证据')}仍需手动复核；执行前保持小仓位或观察。"
    elif support:
        status = "ready"
        tone = "ready"
        headline = "核心证据可辅助验证"
        action_summary = "核心证据已回流，可辅助验证；仍不自动交易，最终动作必须结合纪律和仓位规则。"
    else:
        status = "missing"
        tone = "missing"
        headline = "核心证据待验证"
        action_summary = "先补齐龙虎榜、融资融券、涨跌停/情绪；缺失时只观察。"
    return {
        "title": "A股核心证据执行摘要",
        "status": status,
        "tone": tone,
        "headline": headline,
        "summary": f"可辅助 {len(support)}｜阻断 {len(blocked)}｜缓存 {len(cached)}｜待补 {len(missing)}",
        "action_summary": action_summary,
        "items": items,
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def _evidence_group_items(items: Any = None, limit: int = 4) -> list[dict]:
    result = []
    for raw in as_list(items):
        item = as_mapping(raw)
        if not item:
            continue
        manual_action = as_mapping(item.get("manual_action"))
        result.append(
            {
                "key": to_text(item.get("key"), "a_share_evidence"),
                "label": to_text(item.get("label"), "A股证据"),
                "status_label": to_text(item.get("status_label"), "待验证"),
                "evidence_label": to_text(item.get("evidence_label"), "待验证证据"),
                "headline": to_text(item.get("headline"), "待验证"),
                "metric": to_text(item.get("metric"), "暂无数值"),
                "source": to_text(item.get("source"), "本地 packet"),
                "updated_at": to_text(item.get("updated_at"), "暂无时间"),
                "next_action": to_text(item.get("next_action"), "按数据恢复中心手动处理。"),
                "writes_packet": to_text(manual_action.get("writes_packet")),
                "refresh_policy": to_text(manual_action.get("refresh_policy"), "button_gated"),
                "deepseek_called": False,
            }
        )
        if len(result) >= max(1, int(limit or 4)):
            break
    return result


def build_evidence_status_groups(
    support_items: Any = None,
    blocker_items: Any = None,
    cached_items: Any = None,
    missing_items: Any = None,
) -> list[dict]:
    groups = [
        ("recovered", "已回流", "ready", "可进入证据链，但仍需复核日期、来源和仓位纪律。", support_items),
        ("blocked", "仍受限", "failed", "权限、接口、网络或本会话跳过仍未恢复；不能把缺失写成利好。", blocker_items),
        ("cached", "使用缓存", "stale", "缓存只能防白屏，执行前必须复核交易日和更新时间。", cached_items),
        ("manual", "待手动", "missing", "尚未形成可验证 packet；需要时从高级工具箱手动补齐。", missing_items),
    ]
    result = []
    for key, label, tone, summary, raw_items in groups:
        items = _evidence_group_items(raw_items)
        result.append(
            {
                "key": key,
                "label": label,
                "tone": tone,
                "count": len(as_list(raw_items)),
                "summary": summary,
                "items": items,
                "labels_text": _join_labels(raw_items, fallback="无", limit=4),
                "deepseek_called": False,
            }
        )
    return result


def build_latest_recovery_evidence_impact(latest_recovery_result_notice: Any = None) -> dict:
    notice = as_mapping(latest_recovery_result_notice)
    if not notice:
        return {}
    status = to_text(notice.get("status"), "waiting")
    label = to_text(notice.get("label"), "数据恢复")
    writes_packet = to_text(notice.get("writes_packet"))
    evidence_key = WRITES_PACKET_TO_EVIDENCE_KEY.get(writes_packet, "")
    message = to_text(notice.get("message"), "已更新本地恢复状态。")
    if status == "recovered":
        evidence_state = "supporting"
        tone = "ready"
        impact_text = f"{label}刚刚回流；可进入证据链，但执行前仍需复核交易日、来源和仓位纪律。"
        action_hint = "返回综合推演中心查看 Home Action Snapshot；不要把单项恢复写成自动加仓。"
    elif status == "blocked":
        evidence_state = "blocked"
        tone = "failed"
        impact_text = f"{label}恢复仍受限；证据门槛维持阻断，不能把缺失数据当成利好。"
        action_hint = "先处理权限、积分、交易日、网络或覆盖范围问题；策略保持观察/降风险。"
    else:
        evidence_state = "missing"
        tone = "missing"
        impact_text = f"{label}恢复结果待验证；尚不能进入核心证据链。"
        action_hint = "在高级工具箱对应模块手动运行后，再回到综合推演中心查看回流状态。"
    return {
        "key": "latest_recovery_result",
        "evidence_key": evidence_key,
        "label": label,
        "status": status,
        "evidence_state": evidence_state,
        "tone": tone,
        "impact_text": impact_text,
        "action_hint": action_hint,
        "message": message,
        "writes_packet": writes_packet,
        "updated_at": to_text(notice.get("updated_at")),
        "source": to_text(notice.get("source"), "最近恢复结果"),
        "external_call_policy": to_text(notice.get("external_call_policy"), "not_triggered"),
        "deepseek_called": False,
    }


def build_evidence_radar_card_view_model(
    support_items: Any = None,
    blocker_items: Any = None,
    cached_items: Any = None,
    missing_items: Any = None,
    latest_recovery_impact: Any = None,
) -> dict:
    support = as_list(support_items)
    blockers = as_list(blocker_items)
    cached = as_list(cached_items)
    missing = as_list(missing_items)
    support_count = len(support)
    blocker_count = len(blockers)
    cached_count = len(cached)
    missing_count = len(missing)
    latest_impact = as_mapping(latest_recovery_impact)
    latest_state = to_text(latest_impact.get("evidence_state"))
    promoted_key = to_text(latest_impact.get("evidence_key")) if latest_state == "supporting" else ""
    if latest_state == "blocked" and not blocker_count:
        blocker_count = 1
    if latest_state == "supporting" and not support_count:
        support_count = 1
    if latest_state == "missing" and not missing_count:
        missing_count = 1
    blocker_text_items = blockers or ([latest_impact] if latest_state == "blocked" else [])
    recovery_text_items = blockers + cached + missing
    if latest_state in {"blocked", "missing"} and latest_impact:
        recovery_text_items = [latest_impact] + recovery_text_items
    support_text_items = support or ([latest_impact] if latest_state == "supporting" else [])
    if blocker_count:
        status = "blocked"
        status_label = "阻断加仓"
        tone = "danger"
        confidence_gate = "低置信度"
        execution_guardrail = (
            f"先处理{_join_labels(blocker_text_items, fallback='阻断证据')}；未排除前不能把缺失数据写成利好，"
            "策略只能观察、降风险或小额试探。"
        )
    elif cached_count or missing_count:
        status = "partial"
        status_label = "谨慎验证"
        tone = "warning"
        confidence_gate = "中低置信度"
        recovery = _join_labels(recovery_text_items, fallback="缓存/缺失证据")
        execution_guardrail = f"{recovery}仍需复核；未补齐前不要追高、满仓或加融资。"
    elif support_count:
        status = "ready"
        status_label = "可进入证据链"
        tone = "success"
        confidence_gate = "可验证"
        execution_guardrail = "关键 A股证据已形成支持链，但仍需价格纪律、仓位预算和失效条件共同确认。"
    else:
        status = "missing"
        status_label = "待刷新"
        tone = "muted"
        confidence_gate = "不可验证"
        execution_guardrail = "A股证据雷达尚未生成；只能显示空态或上次缓存，不支撑交易动作。"
    if latest_impact:
        impact_text = to_text(latest_impact.get("impact_text"))
        if impact_text:
            execution_guardrail = f"{execution_guardrail} 最近恢复：{impact_text}"
    return {
        "status": status,
        "status_label": status_label,
        "tone": tone,
        "confidence_gate": confidence_gate,
        "summary": f"支持 {support_count}｜阻断 {blocker_count}｜缓存 {cached_count}｜缺失 {missing_count}",
        "top_supports": [as_mapping(item) for item in _prioritize_evidence_items(support, promoted_key)[:3]],
        "primary_blockers": [as_mapping(item) for item in blockers[:3]],
        "required_recovery": [as_mapping(item) for item in (blockers + cached + missing)[:4]],
        "support_text": _join_labels(support_text_items, fallback="暂无支持证据"),
        "blocker_text": _join_labels(blocker_text_items, fallback="暂无阻断证据"),
        "recovery_text": _join_labels(recovery_text_items, fallback="暂无待补证据"),
        "decision_guardrail": execution_guardrail,
        "execution_guardrail": execution_guardrail,
        "decision_signals": _short_decision_signals(blockers + cached + missing + support),
        "latest_recovery_impact": latest_impact,
        "manual_note": "证据雷达只读取本地 packet；所有补齐动作都必须手动触发。",
        "deepseek_called": False,
    }


def _home_loop_tone(card_tone: str, card_status: str) -> str:
    if card_tone in {"danger", "failed"} or card_status == "blocked":
        return "failed"
    if card_tone in {"warning", "stale"} or card_status == "partial":
        return "stale"
    if card_tone in {"success", "ready"} or card_status == "ready":
        return "ready"
    return "missing"


def build_evidence_loop_status(
    radar_card: Any = None,
    *,
    support_items: Any = None,
    blocker_items: Any = None,
    cached_items: Any = None,
    missing_items: Any = None,
) -> dict:
    card = as_mapping(radar_card)
    status = to_text(card.get("status"), "missing")
    status_label = to_text(card.get("status_label"), "待刷新")
    summary = to_text(
        card.get("summary"),
        f"支持 {len(as_list(support_items))}｜阻断 {len(as_list(blocker_items))}｜缓存 {len(as_list(cached_items))}｜缺失 {len(as_list(missing_items))}",
    )
    return {
        "key": "a_share_evidence_loop",
        "label": "证据闭环",
        "status": status,
        "status_label": status_label,
        "tone": _home_loop_tone(to_text(card.get("tone")), status),
        "confidence_gate": to_text(card.get("confidence_gate"), "不可验证"),
        "summary": summary,
        "decision_guardrail": to_text(card.get("execution_guardrail"), "证据未补齐前，不支撑放大仓位。"),
        "support_count": len(as_list(support_items)),
        "blocker_count": len(as_list(blocker_items)),
        "cached_count": len(as_list(cached_items)),
        "missing_count": len(as_list(missing_items)),
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
        "manual_note": "证据闭环只读取本地 packet；补证、刷新和外部接口必须手动触发。",
    }


def _manual_action(key: str, label: str, evidence_state: str) -> dict:
    config = EVIDENCE_ACTIONS.get(key, {})
    writes_packet = to_text(config.get("writes_packet"), f"command_center_{key}_packet")
    legacy_tab = to_text(config.get("legacy_tab"), "数据源体检")
    return {
        "button_label": to_text(config.get("button_label"), f"手动刷新{label}"),
        "toolbox_entry": to_text(config.get("toolbox_entry"), "高级工具箱 / 数据源体检"),
        "workspace_target": "高级工具箱（旧版保留）",
        "workspace_state_key": "workspace_mode_v2",
        "legacy_tab": legacy_tab,
        "legacy_tab_state_key": "legacy_workspace_selected_tab",
        "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
        "writes_packet": writes_packet,
        "refresh_policy": "button_gated",
        "reason": _evidence_action_hint(label, evidence_state),
        "source_label": "A股证据雷达",
        "deepseek_called": False,
    }


def _format_metric(key: str, value: int | float | None, suffix: str) -> str:
    if value is None:
        return "暂无数值"
    if key == "limit_emotion":
        if suffix:
            return f"{value:+.2f}{suffix}"
        return f"{value:.2f}"
    if suffix == "%":
        return f"{value:.2f}%"
    if suffix == "亿":
        return f"{value:+.2f}亿"
    if suffix == "项":
        return f"{int(value)}项" if float(value).is_integer() else f"{value}项"
    return f"{value}"


def _risk_text(packet: Mapping[str, Any]) -> str:
    notes = [to_text(item) for item in as_list(packet.get("risk_notes"))]
    notes = [item for item in notes if item]
    return notes[0] if notes else _first_text(
        packet.get("decision_guardrail"),
        packet.get("manual_required_text"),
        packet.get("summary"),
        default="待验证，不能单独作为交易依据。",
    )


def build_evidence_item(
    packet: Any,
    *,
    key: str,
    label: str,
    headline_key: str,
    metric_keys: tuple[str, ...],
    metric_suffix: str = "",
    priority: int = 3,
    decision_role: str = "",
) -> dict:
    payload = as_mapping(packet)
    status = to_text(payload.get("status"), "waiting")
    data_status = to_text(payload.get("data_status"), "missing")
    metric = _first_number(payload, metric_keys)
    headline = _first_text(
        payload.get(headline_key),
        payload.get("evidence_summary"),
        payload.get("summary"),
        default="待验证" if data_status == "missing" else "已读取",
    )
    evidence_state = _evidence_state(status, data_status)
    label_text = to_text(label, "A股证据")
    evidence_summary = _first_text(payload.get("evidence_summary"), payload.get("summary"), default=headline)
    packet_guardrail = _first_text(payload.get("decision_guardrail"), default="")
    packet_action_hint = _first_text(payload.get("action_hint"), default="")
    return {
        "key": key,
        "label": label_text,
        "priority": priority,
        "decision_role": decision_role,
        "status": status,
        "data_status": data_status,
        "evidence_state": evidence_state,
        "evidence_label": _evidence_label(evidence_state),
        "status_label": _status_label(status, data_status),
        "tone": _status_tone(status, data_status),
        "headline": headline,
        "metric": _format_metric(key, metric, metric_suffix),
        "evidence_summary": evidence_summary,
        "evidence_items": as_list(payload.get("evidence_items")),
        "verification_status": _first_text(payload.get("verification_status"), default=_evidence_label(evidence_state)),
        "packet_role": _first_text(payload.get("packet_role"), default=label_text),
        "decision_guardrail": packet_guardrail,
        "decision_signal": packet_guardrail or _decision_signal(label, headline, evidence_state),
        "source": _first_text(payload.get("source"), payload.get("api"), default="本地缓存"),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("trade_date"), default="暂无时间"),
        "risk_text": _risk_text(payload),
        "manual_required_text": _first_text(payload.get("manual_required_text"), default="缺失时需要手动刷新或权限校验。"),
        "next_action": packet_action_hint or _evidence_action_hint(label_text, evidence_state),
        "manual_action": _manual_action(key, label_text, evidence_state),
        "deepseek_called": False,
    }


def build_a_share_evidence_radar_view_model(snapshot: Any = None) -> dict:
    payload = as_mapping(snapshot)
    items = [
        build_evidence_item(
            payload.get(packet_key),
            key=key,
            label=label,
            headline_key=headline_key,
            metric_keys=metric_keys,
            metric_suffix=suffix,
            priority=priority,
            decision_role=decision_role,
        )
        for packet_key, key, label, headline_key, metric_keys, suffix, priority, decision_role in EVIDENCE_DEFS
    ]
    ready = [item for item in items if item["data_status"] == "ready"]
    cached = [item for item in items if item["data_status"] == "cached"]
    failed = [item for item in items if item["status"] == "failed"]
    missing = [item for item in items if item["data_status"] == "missing" and item["status"] != "failed"]
    support_items = [item for item in items if item["evidence_state"] == "supporting"]
    blocker_items = [item for item in items if item["evidence_state"] == "blocked"]
    cached_items = [item for item in items if item["evidence_state"] == "cached"]
    missing_items = [item for item in items if item["evidence_state"] == "missing"]
    decision_evidence_queue = sorted(
        items,
        key=lambda item: (
            item["priority"],
            {"blocked": 0, "missing": 1, "cached": 2, "supporting": 3}.get(item["evidence_state"], 4),
            item["label"],
        ),
    )
    next_evidence_actions = [
        {
            "key": item["key"],
            "label": item["label"],
            "priority": item["priority"],
            "evidence_state": item["evidence_state"],
            "evidence_label": item["evidence_label"],
            "status_label": item["status_label"],
            "tone": item["tone"],
            "action_hint": item["next_action"],
            "manual_action": item["manual_action"],
            "action_label": item["manual_action"]["button_label"],
            "toolbox_entry": item["manual_action"]["toolbox_entry"],
            "workspace_target": item["manual_action"]["workspace_target"],
            "workspace_state_key": item["manual_action"]["workspace_state_key"],
            "legacy_tab": item["manual_action"]["legacy_tab"],
            "legacy_tab_state_key": item["manual_action"]["legacy_tab_state_key"],
            "navigation_label": item["manual_action"]["navigation_label"],
            "writes_packet": item["manual_action"]["writes_packet"],
            "refresh_policy": item["manual_action"]["refresh_policy"],
            "source_label": "A股证据雷达",
            "decision_role": item["decision_role"],
            "deepseek_called": False,
        }
        for item in decision_evidence_queue
        if item["evidence_state"] != "supporting"
    ]
    summary = (
        f"已刷新 {len(ready)} 项｜使用缓存 {len(cached)} 项｜失败/受限 {len(failed)} 项｜待验证 {len(missing)} 项"
    )
    decision_summary = (
        f"支持 {len(support_items)}｜阻断 {len(blocker_items)}｜缓存 {len(cached_items)}｜缺失 {len(missing_items)}"
    )
    latest_recovery_impact = build_latest_recovery_evidence_impact(payload.get("latest_recovery_result_notice"))
    promoted_evidence_key = to_text(latest_recovery_impact.get("evidence_key")) if latest_recovery_impact.get("evidence_state") == "supporting" else ""
    recovered_modules = build_recovered_evidence_modules(support_items, promoted_key=promoted_evidence_key)
    core_evidence_items = build_core_evidence_items(items)
    core_evidence_action_brief = build_core_evidence_action_brief(core_evidence_items)
    evidence_status_groups = build_evidence_status_groups(
        support_items=support_items,
        blocker_items=blocker_items,
        cached_items=cached_items,
        missing_items=missing_items,
    )
    radar_card = build_evidence_radar_card_view_model(
        support_items=support_items,
        blocker_items=blocker_items,
        cached_items=cached_items,
        missing_items=missing_items,
        latest_recovery_impact=latest_recovery_impact,
    )
    loop_status = build_evidence_loop_status(
        radar_card,
        support_items=support_items,
        blocker_items=blocker_items,
        cached_items=cached_items,
        missing_items=missing_items,
    )
    return {
        "title": "A股证据雷达",
        "summary": summary,
        "decision_summary": decision_summary,
        "radar_card": radar_card,
        "loop_status": loop_status,
        "latest_recovery_impact": latest_recovery_impact,
        "recovered_evidence_modules": recovered_modules,
        "recovered_evidence_summary": recovered_evidence_summary_text(support_items, promoted_key=promoted_evidence_key),
        "core_evidence_items": core_evidence_items,
        "core_evidence_summary": core_evidence_summary_text(core_evidence_items),
        "core_evidence_action_brief": core_evidence_action_brief,
        "core_evidence_manual_note": "龙虎榜、融资融券、涨跌停/情绪只读取本地 packet；补证和接口请求必须手动触发。",
        "evidence_status_groups": evidence_status_groups,
        "items": items,
        "support_items": support_items,
        "blocker_items": blocker_items,
        "cached_items": cached_items,
        "missing_items": missing_items,
        "decision_evidence_queue": decision_evidence_queue,
        "next_evidence_actions": next_evidence_actions,
        "ready_count": len(ready),
        "cached_count": len(cached),
        "failed_count": len(failed),
        "missing_count": len(missing),
        "manual_note": "证据雷达只读取本地 packet；页面打开不会自动请求 Tushare、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }


def build_home_evidence_backfill_actions(
    evidence_radar_packet: Any = None,
    runnable_keys: Any = None,
    limit: int = 2,
) -> list[dict]:
    packet = as_mapping(evidence_radar_packet)
    if isinstance(runnable_keys, (set, frozenset)):
        raw_keys = list(runnable_keys)
    else:
        raw_keys = as_list(runnable_keys)
    allowed = {to_text(key) for key in raw_keys}
    if not allowed:
        allowed = set(EVIDENCE_ACTIONS)
    result = []
    for raw in as_list(packet.get("next_evidence_actions")):
        item = as_mapping(raw)
        key = to_text(item.get("key"))
        manual_action = as_mapping(item.get("manual_action"))
        if not key or key not in allowed:
            continue
        if manual_action.get("refresh_policy") != "button_gated":
            continue
        result.append({**item, "manual_action": manual_action, "deepseek_called": False})
        if len(result) >= max(1, int(limit or 2)):
            break
    return result


def build_home_evidence_recovery_summary(
    evidence_radar_packet: Any = None,
    runnable_keys: Any = None,
    limit: int = 2,
) -> dict:
    actions = build_home_evidence_backfill_actions(
        evidence_radar_packet,
        runnable_keys=runnable_keys,
        limit=limit,
    )
    if not actions:
        return {
            "status": "ready",
            "title": "数据恢复建议",
            "summary": "关键 A股证据暂不需要手动补齐；继续以价格纪律、仓位规则和已验证 packet 为准。",
            "actions": [],
            "deepseek_called": False,
        }
    labels = [to_text(item.get("label")) for item in actions]
    labels = [label for label in labels if label]
    packet_names = [
        to_text(as_mapping(item.get("manual_action")).get("writes_packet"))
        for item in actions
    ]
    packet_names = [name for name in packet_names if name]
    first_action = as_mapping(actions[0].get("manual_action"))
    first_label = labels[0] if labels else "关键证据"
    return {
        "status": "needs_recovery",
        "title": "数据恢复建议｜补齐关键 A股证据",
        "summary": (
            f"优先补齐：{'、'.join(labels)}。先点「{to_text(first_action.get('button_label'), '手动刷新')}」；"
            f"结果会回流到 {'、'.join(packet_names)}，页面不会自动调用 DeepSeek 或全市场扫描。"
        ),
        "primary_label": first_label,
        "primary_button_label": to_text(first_action.get("button_label"), "手动刷新"),
        "actions": actions,
        "deepseek_called": False,
    }
