from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

from command_center_legacy_packet_contract import build_legacy_packet_decision_contract


MAX_RECOMMENDED_ETFS = 3
MAX_RISK_NOTES = 6
MAX_EVIDENCE_ITEMS = 5
MAX_EVIDENCE_CHAIN_ITEMS = 5
ACTIONABLE_ETF_LABELS = {"可配置", "可小额配置", "可用现金配置", "回踩确认后配置"}
WATCH_ETF_LABELS = {"观察", "等回踩", "等量能确认", "只观察不追"}
AVOID_ETF_LABELS = {"不追高", "过热", "重叠过高", "流动性不足", "融资风险不支持"}
EXCLUDED_ETF_LABELS = {"数据不足", "暂不纳入", "无法评分", "接口失败", "权限失败", "不可判断"}
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
        text = value.strip().replace(",", "").replace("%", "").replace("¥", "").replace("￥", "")
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


def _first_number(*values: Any) -> int | float | None:
    for value in values:
        number = to_number(value)
        if number is not None:
            return number
    return None


def _looks_like_etf_code(value: Any) -> bool:
    text = to_text(value).upper()
    if not text:
        return False
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return False
    compact = text.replace(".", "").replace("-", "").replace("_", "")
    return any(ch.isdigit() for ch in compact) and compact.isalnum()


def _dedupe_text(values: Any, fallback: str = "", limit: int = MAX_RISK_NOTES) -> list[str]:
    items = []
    raw_values = values if isinstance(values, (list, tuple)) else [values]
    seen = set()
    for item in raw_values:
        if isinstance(item, Mapping):
            text = _first_text(item.get("message"), item.get("summary"), item.get("name"), item.get("warning"))
        else:
            text = to_text(item)
        if text and text not in seen:
            seen.add(text)
            items.append(text)
        if len(items) >= limit:
            break
    if not items and fallback:
        items.append(fallback)
    return items


def _action_tone(action_state: str) -> str:
    label = _status_label(action_state)
    if label in ACTIONABLE_ETF_LABELS:
        return "ready"
    if label in WATCH_ETF_LABELS:
        return "stale"
    if label in AVOID_ETF_LABELS or label in EXCLUDED_ETF_LABELS:
        return "failed"
    return "missing"


def _status_label(action_state: str) -> str:
    text = to_text(action_state)
    if text.lower() in {"ready", "cached", "cache", "partial", "waiting", "missing"}:
        return "观察"
    if any(word in text for word in ("数据不足", "暂不纳入", "无法评分", "不可判断")):
        return "数据不足" if "数据不足" in text else "暂不纳入" if "暂不纳入" in text else "无法评分" if "无法评分" in text else "不可判断"
    if any(word in text for word in ("权限", "接口失败", "接口")) and any(word in text for word in ("失败", "不可", "不足")):
        return "接口失败"
    if any(word in text for word in ("融资风险不支持", "融资压力", "不支持融资")):
        return "融资风险不支持"
    if any(word in text for word in ("流动性不足", "成交额不足")):
        return "流动性不足"
    if any(word in text for word in ("重叠过高", "高重叠")):
        return "重叠过高"
    if any(word in text for word in ("不追高", "只观察不追")):
        return "不追高" if "不追高" in text else "只观察不追"
    if any(word in text for word in ("过热", "追高", "溢价")):
        return "过热"
    if any(word in text for word in ("等回踩", "回踩确认")):
        return "回踩确认后配置" if "配置" in text else "等回踩"
    if any(word in text for word in ("等量能", "量能确认")):
        return "等量能确认"
    if any(word in text for word in ("可用现金", "现金配置")):
        return "可用现金配置"
    if any(word in text for word in ("小额", "试探")):
        return "可小额配置"
    if any(word in text for word in ("可", "配置", "准备")):
        return "可配置"
    if any(word in text for word in ("观察", "等待", "只观察")):
        return "观察"
    return text or "观察"


def _etf_group_for_status(status_label: str) -> str:
    label = _status_label(status_label)
    if label in ACTIONABLE_ETF_LABELS:
        return "actionable"
    if label in WATCH_ETF_LABELS:
        return "watch"
    if label in AVOID_ETF_LABELS:
        return "avoid"
    if label in EXCLUDED_ETF_LABELS:
        return "excluded"
    return "watch"


def _etf_sort_key(item: Any = None) -> tuple:
    payload = as_mapping(item)
    status_priority = {
        "可配置": 0,
        "可小额配置": 1,
        "可用现金配置": 2,
        "回踩确认后配置": 3,
        "观察": 4,
        "等回踩": 5,
        "等量能确认": 6,
        "只观察不追": 7,
    }
    status = _status_label(payload.get("status_label") or payload.get("action_state"))
    score = to_number(payload.get("score"))
    rank = to_number(payload.get("rank"))
    return (status_priority.get(status, 99), -(score if score is not None else -1), rank if rank is not None else 999)


def _rerank_etfs(items: Any = None) -> list[dict]:
    result = []
    for index, item in enumerate(as_list(items), start=1):
        payload = as_mapping(item)
        payload["rank"] = index
        result.append(payload)
    return result


def split_etf_candidates(candidates: Any = None, limit: int = MAX_RECOMMENDED_ETFS) -> dict:
    buckets = {"actionable": [], "watch": [], "avoid": [], "excluded": []}
    seen = set()
    for index, item in enumerate(as_list(candidates), start=1):
        payload = as_mapping(item)
        key = payload.get("code") or payload.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        payload["rank"] = index
        status = _status_label(payload.get("status_label") or payload.get("action_state"))
        payload["status_label"] = status
        payload["action_state"] = _first_text(payload.get("action_state"), default=status)
        payload["tone"] = _action_tone(status)
        buckets[_etf_group_for_status(status)].append(payload)
    actionable = sorted(buckets["actionable"], key=_etf_sort_key)
    watch = sorted(buckets["watch"], key=_etf_sort_key)
    avoid = sorted(buckets["avoid"], key=_etf_sort_key)
    excluded = sorted(buckets["excluded"], key=_etf_sort_key)
    recommended = _rerank_etfs([*actionable, *watch][: int(limit or MAX_RECOMMENDED_ETFS)])
    return {
        "actionable_etfs": _rerank_etfs(actionable),
        "watch_etfs": _rerank_etfs(watch),
        "avoid_etfs": _rerank_etfs(avoid),
        "excluded_etfs": _rerank_etfs(excluded),
        "recommended_etfs": recommended,
        "has_main_etfs": bool(recommended),
    }


def _etf_risk_text(payload: Mapping[str, Any], bucket: str) -> str:
    explicit = _first_text(
        payload.get("risk_note"),
        payload.get("risk"),
        payload.get("warning"),
        payload.get("no_chase_reason"),
    )
    if explicit:
        return explicit
    if any(word in bucket for word in ("科技", "半导体", "芯片", "成长")):
        return "赛道波动大，不追高；等待回踩、成交额和趋势确认。"
    if any(word in bucket for word in ("防守", "黄金", "货币", "债")):
        return "防守仓位也需看流动性、溢价折价和资金拥挤度。"
    return "ETF 需复核流动性、跟踪指数、同类重叠和追高风险。"


def _liquidity_text(payload: Mapping[str, Any]) -> str:
    value = _first_number(
        payload.get("turnover_yi"),
        payload.get("amount_yi"),
        payload.get("成交额(亿)"),
        payload.get("liquidity_score"),
    )
    if value is None:
        return _first_text(payload.get("liquidity"), payload.get("liquidity_text"), default="待验证")
    return f"{value:g}亿" if value > 0 else "待验证"


def _build_evidence_items(payload: Mapping[str, Any], score: int | float | None, bucket: str, action_state: str, trigger: str) -> list[dict]:
    liquidity = _liquidity_text(payload)
    items = [
        {
            "label": "赛道",
            "value": bucket or "ETF",
            "detail": "按本地配置/缓存归类；不等于自动买入。",
            "tone": "ready" if bucket else "missing",
        },
        {
            "label": "综合分",
            "value": "待验证" if score is None else str(score),
            "detail": "只作候选排序线索，不能替代成交额和风险线复核。",
            "tone": "ready" if score is not None and score >= 70 else "stale" if score is not None else "missing",
        },
        {
            "label": "动作",
            "value": _status_label(action_state),
            "detail": trigger or "等待回踩、量能和风险线确认。",
            "tone": _action_tone(action_state),
        },
        {
            "label": "流动性",
            "value": liquidity,
            "detail": "缺少成交额/流动性时，只能视为待验证。",
            "tone": "missing" if liquidity == "待验证" else "ready",
        },
        {
            "label": "追高风险",
            "value": "必须复核",
            "detail": _etf_risk_text(payload, bucket),
            "tone": "failed",
        },
    ]
    return items[:MAX_EVIDENCE_ITEMS]


def _chain_status(value: str, *, risk_text: str = "") -> tuple[str, str, str]:
    text = to_text(value)
    risk = to_text(risk_text)
    if not text or text in {"待验证", "暂无", "N/A", "--"}:
        return "missing", "待验证", "missing"
    if any(word in text + risk for word in ("不足", "过热", "追高", "异常", "高重叠", "偏高", "风险")):
        return "stale", "需复核", "stale"
    return "ready", "可参考", "ready"


def _chain_item(key: str, label: str, value: str, detail: str, guardrail: str, *, risk_text: str = "") -> dict:
    status, status_label, tone = _chain_status(value, risk_text=risk_text)
    return {
        "key": key,
        "label": label,
        "status": status,
        "status_label": status_label,
        "tone": tone,
        "value": value or "待验证",
        "detail": detail,
        "guardrail": guardrail,
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def _overlap_text(payload: Mapping[str, Any]) -> str:
    return _first_text(
        payload.get("overlap_risk"),
        payload.get("holding_overlap"),
        payload.get("same_bucket_overlap"),
        payload.get("similar_etf_overlap"),
        payload.get("overlap"),
        default="待验证",
    )


def _overheat_text(payload: Mapping[str, Any], bucket: str) -> str:
    explicit = _first_text(
        payload.get("overheat_risk"),
        payload.get("premium_discount"),
        payload.get("premium_rate"),
        payload.get("valuation_heat"),
        payload.get("no_chase_reason"),
    )
    if explicit:
        return explicit
    risk = _etf_risk_text(payload, bucket)
    if risk:
        return risk
    return "追高/溢价折价待验证"


def _margin_cash_text(payload: Mapping[str, Any], margin_context: Mapping[str, Any]) -> str:
    explicit = _first_text(
        payload.get("cash_buffer"),
        payload.get("cash_buffer_text"),
        payload.get("margin_guardrail"),
        payload.get("margin_note"),
    )
    if explicit:
        return explicit
    cash_ratio = _first_number(payload.get("recommended_cash_ratio"), margin_context.get("recommended_cash_ratio"))
    margin_ratio = _first_number(payload.get("recommended_margin_ratio"), margin_context.get("recommended_margin_ratio"))
    current_ratio = _first_number(payload.get("current_margin_ratio"), margin_context.get("current_margin_ratio"))
    parts = []
    if cash_ratio is not None:
        parts.append(f"现金缓冲 {cash_ratio:g}%")
    if margin_ratio is not None:
        parts.append(f"建议融资 {margin_ratio:g}%")
    if current_ratio is not None:
        parts.append(f"当前融资 {current_ratio:g}%")
    return "；".join(parts) if parts else "待验证"


def _summarize_evidence_chain(chain: list[dict]) -> str:
    ready = len([item for item in chain if item.get("status") == "ready"])
    missing = len([item for item in chain if item.get("status") == "missing"])
    review = len([item for item in chain if item.get("status") in {"stale", "failed"}])
    return f"可参考 {ready}｜待补证 {missing}｜需复核 {review}"


def _packet_verification_status(status: str, data_status: str, etfs: Any = None, risk_state: str = "") -> str:
    rows = as_list(etfs)
    risk = to_text(risk_state)
    if status == "failed":
        return "阻断决策"
    if not rows:
        return "待验证"
    if data_status in {"cached", "cache_only"}:
        return "缓存辅助"
    if any(word in risk for word in ("降", "过热", "暂停", "规避")):
        return "待验证"
    if any(as_list(as_mapping(item).get("data_gaps")) for item in rows):
        return "待验证"
    return "已验证"


def _build_packet_evidence_summary(
    status: str,
    data_status: str,
    etfs: Any = None,
    *,
    main_direction: str = "",
    recommended_margin_ratio: Any = None,
    recommended_cash_ratio: Any = None,
    risk_state: str = "",
) -> str:
    rows = as_list(etfs)
    if not rows:
        if status == "failed":
            return "ETF/融资快照读取失败；不能作为加融资或追高依据。"
        return "暂无 ETF/融资快照；页面打开不会自动全量发现或拉取重行情。"
    margin = to_number(recommended_margin_ratio)
    cash = to_number(recommended_cash_ratio)
    parts = [
        f"ETF Top{len(rows)}",
        f"主方向：{main_direction or '待验证'}",
        f"融资：{margin:g}%" if margin is not None else "融资：待验证",
        f"现金：{cash:g}%" if cash is not None else "现金：待验证",
        f"风险：{risk_state or '只观察不追'}",
    ]
    if data_status == "cached":
        parts.append("使用缓存")
    return "｜".join(parts)


def _build_packet_evidence_items(
    data_status: str,
    etfs: Any = None,
    *,
    main_direction: str = "",
    recommended_margin_ratio: Any = None,
    recommended_cash_ratio: Any = None,
    risk_state: str = "",
) -> list[dict]:
    rows = as_list(etfs)
    margin = to_number(recommended_margin_ratio)
    cash = to_number(recommended_cash_ratio)
    data_gap_count = sum(len(as_list(as_mapping(item).get("data_gaps"))) for item in rows)
    return [
        {
            "label": "ETF覆盖",
            "value": f"Top{len(rows)}" if rows else "待刷新",
            "detail": "只读取本地配置或手动刷新结果；不会自动全量发现。",
            "tone": "ready" if rows else "missing",
        },
        {
            "label": "主方向",
            "value": main_direction or "待验证",
            "detail": "方向只代表配置倾向，仍需跟踪指数、流动性和追高边界复核。",
            "tone": "ready" if main_direction and main_direction != "待刷新" else "missing",
        },
        {
            "label": "融资/现金",
            "value": (
                f"融资 {margin:g}%｜现金 {cash:g}%"
                if margin is not None and cash is not None
                else "待验证"
            ),
            "detail": "融资比例不能自动放大仓位；现金缓冲必须先确认。",
            "tone": "ready" if margin is not None and cash is not None else "missing",
        },
        {
            "label": "风险边界",
            "value": risk_state or "只观察不追",
            "detail": "追高、溢价折价、同类重叠和流动性不足会阻断加仓。",
            "tone": _action_tone(risk_state or "只观察不追"),
        },
        {
            "label": "数据缺口",
            "value": f"{data_gap_count}项" if data_gap_count else "暂无",
            "detail": "缺口不会被写成利好，也不会触发自动补数。",
            "tone": "missing" if data_gap_count else "ready",
        },
    ][:MAX_EVIDENCE_ITEMS]


def _packet_action_hint(status: str, etfs: Any = None, risk_state: str = "") -> str:
    rows = as_list(etfs)
    risk = to_text(risk_state)
    if status == "failed":
        return "先处理 ETF/融资快照错误；未恢复前不能加融资或追高。"
    if not rows:
        return "先手动刷新融资 ETF 配置或读取缓存；没有快照时只保留观察。"
    if any(word in risk for word in ("降", "过热", "暂停", "规避")):
        return "优先降风险或等待回踩确认；不要把 ETF 候选写成加融资指令。"
    return "复核跟踪指数、流动性、同类重叠、追高/溢价和现金缓冲后，再考虑小额配置。"


def _packet_decision_guardrail(status: str, etfs: Any = None) -> str:
    if status == "failed" or not as_list(etfs):
        return "缺少 ETF/融资快照时，不能作为买入、追高、加融资或放大仓位依据。"
    return "ETF 候选不是买入指令；跟踪指数、流动性、同类重叠、追高风险和现金缓冲同时确认前，不允许放大仓位。"


def _apply_etf_packet_contract(packet: Any = None) -> dict:
    payload = as_mapping(packet)
    explicit_safety = {
        field: payload.get(field)
        for field in (*LOCAL_READ_FALSE_SAFETY_FIELDS, *LOCAL_READ_TRUE_SAFETY_FIELDS)
        if field in payload
    }
    has_explicit_warnings = "warnings" in payload
    explicit_warnings = payload.get("warnings")
    etfs = as_list(payload.get("recommended_etfs"))
    status = to_text(payload.get("status"), "waiting")
    data_status = to_text(payload.get("data_status") or payload.get("cache_state"), "missing")
    risk_state = to_text(payload.get("risk_state"))
    payload.update(
        {
            "packet_role": _first_text(payload.get("packet_role"), default="ETF/融资配置证据"),
            "verification_status": _first_text(
                payload.get("verification_status"),
                default=_packet_verification_status(status, data_status, etfs, risk_state),
            ),
            "evidence_summary": _first_text(
                payload.get("evidence_summary"),
                default=_build_packet_evidence_summary(
                    status,
                    data_status,
                    etfs,
                    main_direction=to_text(payload.get("today_main_direction")),
                    recommended_margin_ratio=payload.get("recommended_margin_ratio"),
                    recommended_cash_ratio=payload.get("recommended_cash_ratio"),
                    risk_state=risk_state,
                ),
            ),
            "evidence_items": as_list(payload.get("evidence_items"))
            or _build_packet_evidence_items(
                data_status,
                etfs,
                main_direction=to_text(payload.get("today_main_direction")),
                recommended_margin_ratio=payload.get("recommended_margin_ratio"),
                recommended_cash_ratio=payload.get("recommended_cash_ratio"),
                risk_state=risk_state,
            ),
            "action_hint": _first_text(payload.get("action_hint"), default=_packet_action_hint(status, etfs, risk_state)),
            "decision_guardrail": _first_text(
                payload.get("decision_guardrail"),
                default=_packet_decision_guardrail(status, etfs),
            ),
        }
    )
    payload.update(
        build_legacy_packet_decision_contract(
            payload,
            label="ETF/融资配置",
            status=status,
            data_status=data_status,
            recovery_state=payload.get("recovery_state"),
            capability_state=payload.get("capability_state"),
        )
    )
    if has_explicit_warnings:
        payload["warnings"] = explicit_warnings
    else:
        payload.pop("warnings", None)
    for field in (*LOCAL_READ_FALSE_SAFETY_FIELDS, *LOCAL_READ_TRUE_SAFETY_FIELDS):
        if field in explicit_safety:
            payload[field] = explicit_safety[field]
        else:
            payload.pop(field, None)
    return payload


def _build_evidence_chain(payload: Mapping[str, Any], bucket: str, margin_context: Mapping[str, Any] | None = None) -> list[dict]:
    context = as_mapping(margin_context)
    tracking = _first_text(payload.get("tracking_index"), payload.get("index_name"), payload.get("index"), default="待验证")
    liquidity = _liquidity_text(payload)
    overlap = _overlap_text(payload)
    overheat = _overheat_text(payload, bucket)
    margin_cash = _margin_cash_text(payload, context)
    return [
        _chain_item(
            "tracking_index",
            "跟踪指数",
            tracking,
            "确认跟踪指数、主题和成分暴露，避免把 ETF 当作普通个股处理。",
            "跟踪指数未确认前，只能观察，不放大仓位。",
        ),
        _chain_item(
            "liquidity",
            "流动性",
            liquidity,
            "以成交额/流动性作为可交易性线索；缺失时不适合融资放大。",
            "流动性未验证前，不加融资、不追高。",
        ),
        _chain_item(
            "overlap",
            "同类重叠",
            overlap,
            "检查是否与已有 ETF 或同赛道持仓重复暴露。",
            "同类重叠未确认前，不重复配置同一赛道。",
        ),
        _chain_item(
            "overheat",
            "追高/溢价",
            overheat,
            "复核赛道是否过热、是否存在溢价折价或拥挤交易。",
            "追高/溢价风险未排除前，只能等待回踩确认。",
            risk_text=overheat,
        ),
        _chain_item(
            "margin_cash",
            "融资/现金",
            margin_cash,
            "把 ETF 动作和融资比例、现金缓冲放在同一条风控线上。",
            "现金缓冲和融资比例未确认前，不能放大仓位。",
        ),
    ][:MAX_EVIDENCE_CHAIN_ITEMS]


def _data_gaps(payload: Mapping[str, Any], evidence_items: list[dict]) -> list[str]:
    gaps = _dedupe_text(payload.get("data_gaps") or payload.get("missing_items"), limit=MAX_RISK_NOTES)
    if not _first_text(payload.get("tracking_index"), payload.get("index_name"), payload.get("index")):
        gaps.append("跟踪指数待验证")
    if any(item.get("label") == "流动性" and item.get("value") == "待验证" for item in evidence_items):
        gaps.append("流动性/成交额待验证")
    return _dedupe_text(gaps, limit=MAX_RISK_NOTES)


def _candidate_rows(candidates: Any) -> list[dict]:
    rows = []
    if isinstance(candidates, Mapping):
        for bucket, items in candidates.items():
            if isinstance(items, Mapping):
                nested_items = (
                    items.get("candidate_etfs")
                    or items.get("recommended_etfs")
                    or items.get("selected_etfs")
                    or items.get("items")
                    or items.get("candidates")
                )
                if nested_items:
                    for item in as_list(nested_items):
                        payload = as_mapping(item)
                        if payload:
                            payload.setdefault("bucket", bucket)
                            for source_key, target_key in (
                                ("ratio_pct", "recommended_ratio"),
                                ("amount", "recommended_amount"),
                                ("suggested_ratio", "recommended_ratio"),
                                ("suggested_amount", "recommended_amount"),
                            ):
                                if items.get(source_key) is not None and payload.get(target_key) is None:
                                    payload[target_key] = items.get(source_key)
                            rows.append(payload)
                    continue
                items = [items]
            for item in as_list(items):
                payload = as_mapping(item)
                if payload:
                    payload.setdefault("bucket", bucket)
                    rows.append(payload)
    else:
        rows = [as_mapping(item) for item in as_list(candidates)]
    return [row for row in rows if row]


def normalize_etf_candidate(
    row: Any = None,
    rank: int = 0,
    default_source: str = "融资 ETF 本地配置",
    margin_context: Any = None,
) -> dict:
    payload = as_mapping(row)
    context = as_mapping(margin_context)
    bucket = _first_text(payload.get("bucket"), payload.get("theme"), payload.get("category"), default="ETF")
    score = _first_number(payload.get("total_score"), payload.get("score"), payload.get("composite_score"))
    action_state = _first_text(
        payload.get("action_state"),
        payload.get("state"),
        payload.get("advice"),
        payload.get("signal"),
        payload.get("decision"),
        default=_first_text(payload.get("status"), default="只观察不追"),
    )
    status_label = _status_label(
        _first_text(payload.get("status_label"), payload.get("state"), payload.get("action"), action_state)
    )
    current_margin_ratio = _first_number(context.get("current_margin_ratio"))
    if current_margin_ratio is not None and current_margin_ratio >= 20 and status_label in {"可配置", "可小额配置"}:
        status_label = "可用现金配置"
    trigger_condition = _first_text(
        payload.get("trigger_condition"),
        payload.get("condition"),
        payload.get("reason"),
        default="等待回踩、量能和风险线确认。",
    )
    evidence_items = _build_evidence_items(payload, score, bucket, status_label, trigger_condition)
    evidence_chain = _build_evidence_chain(payload, bucket, context)
    code = _first_text(payload.get("etf_code"), payload.get("code"), payload.get("ts_code"), payload.get("symbol"))
    name = _first_text(payload.get("etf_name"), payload.get("name"), payload.get("fund_name"))
    if code and not name and not _looks_like_etf_code(code):
        name = code
        code = ""
    return {
        "rank": rank,
        "code": code,
        "name": name,
        "bucket": bucket,
        "score": score,
        "weight": _first_number(payload.get("weight"), payload.get("target_weight"), payload.get("allocation_ratio")),
        "recommended_ratio": _first_number(
            payload.get("recommended_ratio"),
            payload.get("suggested_ratio"),
            payload.get("target_ratio"),
            payload.get("ratio_pct"),
            payload.get("weight"),
        ),
        "recommended_amount": _first_number(
            payload.get("recommended_amount"),
            payload.get("suggested_amount"),
            payload.get("target_amount"),
            payload.get("allocation_amount"),
            payload.get("amount"),
        ),
        "action_state": action_state,
        "status_label": status_label,
        "tone": _action_tone(status_label),
        "trigger_condition": trigger_condition,
        "reason": _first_text(payload.get("reason"), payload.get("summary"), trigger_condition),
        "risk_note": _etf_risk_text(payload, bucket),
        "evidence_items": evidence_items,
        "evidence_chain": evidence_chain,
        "evidence_chain_summary": _summarize_evidence_chain(evidence_chain),
        "action_guardrail": _first_text(
            payload.get("action_guardrail"),
            default="ETF 候选不是买入指令；跟踪指数、流动性、同类重叠、追高风险和融资现金缓冲未确认前不能放大仓位。",
        ),
        "data_gaps": _data_gaps(payload, evidence_items),
        "liquidity_text": _liquidity_text(payload),
        "source": _first_text(payload.get("source"), default=default_source),
        "updated_at": _first_text(payload.get("updated_at"), payload.get("generated_at")),
        "manual_required_text": "ETF 候选来自本地配置或手动刷新结果；页面打开不会自动全量发现或拉取重行情。",
        "deepseek_called": False,
    }


def extract_recommended_etfs(
    allocation_result: Any = None,
    daily_packet: Any = None,
    limit: int = MAX_RECOMMENDED_ETFS,
    margin_context: Any = None,
) -> list[dict]:
    allocation = as_mapping(allocation_result)
    daily = as_mapping(daily_packet)
    candidates = (
        allocation.get("selected_etf_candidates")
        or allocation.get("recommended_etfs")
        or allocation.get("recommended_etf_allocation")
        or daily.get("selected_etf_candidates")
    )
    rows = _candidate_rows(candidates)
    if not rows:
        score_packet = as_mapping(daily.get("score_packet"))
        rows = _candidate_rows(score_packet.get("rows") or allocation.get("etf_score_table"))
    normalized = []
    seen = set()
    collect_limit = max(int(limit or MAX_RECOMMENDED_ETFS) * 4, MAX_RECOMMENDED_ETFS * 4)
    for row in rows:
        item = normalize_etf_candidate(row, rank=len(normalized) + 1, margin_context=margin_context)
        key = item.get("code") or item.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(item)
        if len(normalized) >= collect_limit:
            break
    return normalized


def _derive_main_direction(live_section: Mapping[str, Any], allocation: Mapping[str, Any], etfs: list[dict]) -> str:
    explicit = _first_text(
        live_section.get("today_main_direction"),
        allocation.get("today_main_direction"),
        allocation.get("main_direction"),
        allocation.get("style_tilt"),
    )
    if explicit:
        return explicit
    buckets = []
    seen = set()
    for item in etfs:
        bucket = to_text(item.get("bucket"))
        if bucket and bucket not in seen:
            seen.add(bucket)
            buckets.append(bucket)
    if buckets:
        return " / ".join(buckets[:3])
    return "待刷新"


def _derive_status(allocation: Mapping[str, Any], daily: Mapping[str, Any], live_section: Mapping[str, Any], etfs: list[dict]) -> str:
    if etfs:
        return "ready"
    if allocation or daily or live_section:
        return "partial"
    return "waiting"


def _derive_data_status(status: str, daily: Mapping[str, Any], etfs: list[dict]) -> str:
    if status == "waiting":
        return "missing"
    dataset = as_mapping(daily.get("daily_dataset"))
    text = _first_text(dataset.get("status"), daily.get("refresh_level"), daily.get("source"))
    if "manual_basic" in text or "本地" in text or "local" in text.lower():
        return "cached" if not etfs else "ready"
    return "ready" if etfs else "cached"


def _derive_risk_state(allocation: Mapping[str, Any], current_ratio: int | float | None, recommended_ratio: int | float | None, etfs: list[dict]) -> str:
    action_state = to_text(allocation.get("action_state"))
    if allocation.get("need_deleverage") or "降" in action_state:
        return "降杠杆"
    if not etfs:
        return "待刷新"
    if current_ratio is not None and recommended_ratio is not None and current_ratio > recommended_ratio:
        return "只观察，优先降融资暴露"
    if allocation.get("allow_margin_add"):
        return "可小幅配置"
    return _first_text(action_state, default="只观察不追")


def _allow_new_margin(current_ratio: int | float | None, recommended_ratio: int | float | None, risk_state: str = "") -> bool:
    risk = to_text(risk_state)
    if any(word in risk for word in ("降", "过热", "暂停", "规避", "不支持")):
        return False
    if current_ratio is not None and current_ratio >= 20:
        return False
    if current_ratio is not None and recommended_ratio is not None and current_ratio >= recommended_ratio:
        return False
    return bool(recommended_ratio is not None and recommended_ratio > 0)


def _margin_risk_notice(current_ratio: int | float | None, recommended_ratio: int | float | None, allow_new_margin: bool) -> str:
    if current_ratio is not None and current_ratio >= 20:
        base = f"当前融资比例 {current_ratio:g}% 偏高，ETF 只能作为风险替代/分散工具，不建议新增融资。"
        if recommended_ratio is not None:
            base += f" 建议融资比例 {recommended_ratio:g}%。"
        return base
    if not allow_new_margin:
        return "当前不建议新增融资；ETF 强弱只能作为配置线索，不能作为加杠杆追高依据。"
    return "允许范围内也只考虑现金或小额配置，不建议因为 ETF 强而额外加杠杆追高。"


def _replacement_hint(current_ratio: int | float | None, recommended_ratio: int | float | None) -> str:
    if current_ratio is not None and current_ratio >= 20:
        return "可评估用低重叠 ETF 替代部分单票风险，但先降杠杆或保持现金缓冲。"
    if recommended_ratio is not None and recommended_ratio > 0:
        return "ETF 可作为分散单票波动的观察工具，优先使用现金预算。"
    return "ETF 暂只作为观察清单，不作为新增风险暴露依据。"


def _build_risk_notes(allocation: Mapping[str, Any], daily: Mapping[str, Any], etfs: list[dict]) -> list[str]:
    notes = []
    for key in (
        "no_chase_warning",
        "risk_flags",
        "risk_lines",
        "must_reduce_risk_conditions",
        "holdings_data_gaps",
        "notes",
    ):
        notes.extend(_dedupe_text(allocation.get(key)))
    if not etfs:
        notes.append("暂无 ETF 配置快照；不触发全量 ETF 发现，等待手动刷新。")
    dataset = as_mapping(daily.get("daily_dataset"))
    note = to_text(dataset.get("note"))
    if note:
        notes.append(note)
    notes.append("DeepSeek 未调用；ETF 深度调研仍需手动按钮触发。")
    return _dedupe_text(notes, fallback="不追高 ETF；等待回踩、量能和风险线确认。")


def _watch_not_chase_items(allocation: Mapping[str, Any], etfs: list[dict]) -> list[str]:
    items = _dedupe_text(
        allocation.get("watch_not_chase") or allocation.get("watch_not_chase_etfs") or allocation.get("no_chase_warning"),
        limit=MAX_RECOMMENDED_ETFS,
    )
    if items:
        return items
    if etfs:
        return ["不追高 ETF；等待回踩、量能和风险线确认。"]
    return ["暂无 ETF 快照；不追高，等待刷新后再判断。"]


def build_command_center_etf_packet(
    state: Any = None,
    live_packet: Any = None,
    limit: int = MAX_RECOMMENDED_ETFS,
) -> dict:
    state_map = as_mapping(state)
    live = as_mapping(live_packet)
    live_section = as_mapping(live.get("margin_etf"))
    existing = as_mapping(state_map.get("command_center_etf_packet"))
    if existing.get("recommended_etfs") or existing.get("status") in {"ready", "partial"}:
        existing_context = {
            "current_margin_ratio": existing.get("current_margin_ratio"),
            "recommended_margin_ratio": existing.get("recommended_margin_ratio"),
            "recommended_cash_ratio": existing.get("recommended_cash_ratio"),
        }
        normalized_etfs = [
            normalize_etf_candidate(
                item,
                rank=index + 1,
                default_source=to_text(existing.get("source"), "融资 ETF 本地配置"),
                margin_context=existing_context,
            )
            for index, item in enumerate(
                [
                    *as_list(existing.get("recommended_etfs")),
                    *as_list(existing.get("actionable_etfs")),
                    *as_list(existing.get("watch_etfs")),
                    *as_list(existing.get("avoid_etfs")),
                    *as_list(existing.get("excluded_etfs")),
                ]
            )
        ]
        split = split_etf_candidates(normalized_etfs, limit=limit)
        current_ratio = to_number(existing.get("current_margin_ratio"))
        recommended_ratio = to_number(existing.get("recommended_margin_ratio"))
        risk_state = _first_text(existing.get("risk_state"), default=_derive_risk_state({}, current_ratio, recommended_ratio, split["recommended_etfs"]))
        allow_new_margin = _allow_new_margin(current_ratio, recommended_ratio, risk_state)
        packet = {
            **existing,
            "actionable_etfs": split["actionable_etfs"],
            "watch_etfs": split["watch_etfs"],
            "avoid_etfs": split["avoid_etfs"],
            "excluded_etfs": split["excluded_etfs"],
            "recommended_etfs": split["recommended_etfs"],
            "watch_not_chase": _dedupe_text(existing.get("watch_not_chase"), fallback="不追高 ETF；等待回踩、量能和风险线确认。", limit=MAX_RECOMMENDED_ETFS),
            "risk_notes": _dedupe_text(existing.get("risk_notes"), fallback="DeepSeek 未调用；ETF 深度调研仍需手动按钮触发。"),
            "cache_state": _first_text(existing.get("cache_state"), existing.get("data_status"), default="ready"),
            "risk_state": risk_state,
            "allow_new_margin": allow_new_margin,
            "margin_risk_notice": _first_text(
                existing.get("margin_risk_notice"),
                default=_margin_risk_notice(current_ratio, recommended_ratio, allow_new_margin),
            ),
            "etf_replacement_hint": _first_text(
                existing.get("etf_replacement_hint"),
                default=_replacement_hint(current_ratio, recommended_ratio),
            ),
            "leverage_guardrail": "不建议因为 ETF 强而额外加杠杆追高。",
            "manual_required_text": _first_text(
                existing.get("manual_required_text"),
                default="融资 ETF 只读取本地配置或手动刷新结果；页面打开不会自动全量发现。",
            ),
        }
        return _apply_etf_packet_contract(packet)
    allocation = as_mapping(state_map.get("legacy_margin_etf_allocation_result"))
    daily = as_mapping(state_map.get("legacy_margin_etf_daily_packet"))
    current_ratio = _first_number(
        live_section.get("current_margin_ratio"),
        live_section.get("current_margin_debt_ratio"),
        allocation.get("current_margin_debt_ratio"),
        state_map.get("current_margin_debt_ratio"),
        state_map.get("margin_current_margin_ratio"),
        state_map.get("margin_ratio"),
    )
    recommended_ratio = _first_number(live_section.get("recommended_margin_ratio"), allocation.get("recommended_margin_ratio"))
    recommended_cash_ratio = _first_number(live_section.get("recommended_cash_ratio"), allocation.get("recommended_cash_ratio"))
    margin_context = {
        "current_margin_ratio": current_ratio,
        "recommended_margin_ratio": recommended_ratio,
        "recommended_cash_ratio": recommended_cash_ratio,
    }
    etfs = extract_recommended_etfs(allocation, daily, limit=limit, margin_context=margin_context)
    split = split_etf_candidates(etfs, limit=limit)
    recommended_etfs = split["recommended_etfs"]
    status = _derive_status(allocation, daily, live_section, etfs)
    updated_at = _first_text(
        live_section.get("updated_at"),
        daily.get("updated_at"),
        allocation.get("generated_at"),
        allocation.get("updated_at"),
    )
    source = _first_text(live_section.get("source"), daily.get("source"), allocation.get("data_source"), default="融资 ETF 本地配置快照")
    packet = {
        "status": status,
        "cache_state": _derive_data_status(status, daily, etfs),
        "source": source,
        "updated_at": updated_at,
        "current_margin_ratio": current_ratio,
        "recommended_margin_ratio": recommended_ratio,
        "recommended_cash_ratio": recommended_cash_ratio,
        "today_main_direction": _derive_main_direction(live_section, allocation, etfs),
        "actionable_etfs": split["actionable_etfs"],
        "watch_etfs": split["watch_etfs"],
        "avoid_etfs": split["avoid_etfs"],
        "excluded_etfs": split["excluded_etfs"],
        "recommended_etfs": recommended_etfs,
        "watch_not_chase": _watch_not_chase_items(allocation, etfs),
        "risk_state": _derive_risk_state(allocation, current_ratio, recommended_ratio, recommended_etfs),
        "risk_notes": _build_risk_notes(allocation, daily, etfs),
        "data_status": _derive_data_status(status, daily, etfs),
        "manual_required_text": "融资 ETF 只读取本地配置或手动刷新结果；页面打开不会自动全量发现。",
        "summary": _first_text(
            allocation.get("summary"),
            live_section.get("summary"),
            default=(
                "已读取融资 ETF 本地配置快照；深度行情、全量发现和同赛道比较仍需手动触发。"
                if status != "waiting"
                else "暂无 ETF 配置快照；点击刷新今日基础数据只生成本地配置快照，不自动全量发现。"
            ),
        ),
    }
    packet["allow_new_margin"] = _allow_new_margin(current_ratio, recommended_ratio, packet["risk_state"])
    packet["margin_risk_notice"] = _margin_risk_notice(current_ratio, recommended_ratio, packet["allow_new_margin"])
    packet["etf_replacement_hint"] = _replacement_hint(current_ratio, recommended_ratio)
    packet["leverage_guardrail"] = "不建议因为 ETF 强而额外加杠杆追高。"
    return _apply_etf_packet_contract(packet)
