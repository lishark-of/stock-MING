from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_RECOMMENDED_ETFS = 3
MAX_RISK_NOTES = 6
MAX_EVIDENCE_ITEMS = 5
MAX_EVIDENCE_CHAIN_ITEMS = 5


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
    if any(word in action_state for word in ("可", "配置", "小幅", "准备")):
        return "ready"
    if any(word in action_state for word in ("不追", "观察", "等待", "只观察")):
        return "stale"
    if any(word in action_state for word in ("降", "暂停", "规避", "过热")):
        return "failed"
    return "missing"


def _status_label(action_state: str) -> str:
    if any(word in action_state for word in ("可", "配置", "小幅", "准备")):
        return "可配置"
    if any(word in action_state for word in ("降", "暂停", "规避", "过热")):
        return "降风险"
    return action_state or "只观察不追"


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
    action_state = _first_text(payload.get("action_state"), payload.get("advice"), payload.get("signal"), default="只观察不追")
    trigger_condition = _first_text(
        payload.get("trigger_condition"),
        payload.get("condition"),
        payload.get("reason"),
        default="等待回踩、量能和风险线确认。",
    )
    evidence_items = _build_evidence_items(payload, score, bucket, action_state, trigger_condition)
    evidence_chain = _build_evidence_chain(payload, bucket, context)
    return {
        "rank": rank,
        "code": _first_text(payload.get("etf_code"), payload.get("code"), payload.get("ts_code"), payload.get("symbol")),
        "name": _first_text(payload.get("etf_name"), payload.get("name"), payload.get("fund_name")),
        "bucket": bucket,
        "score": score,
        "weight": _first_number(payload.get("weight"), payload.get("target_weight"), payload.get("allocation_ratio")),
        "action_state": action_state,
        "status_label": _status_label(action_state),
        "tone": _action_tone(action_state),
        "trigger_condition": trigger_condition,
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
    for row in rows:
        item = normalize_etf_candidate(row, rank=len(normalized) + 1, margin_context=margin_context)
        key = item.get("code") or item.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(item)
        if len(normalized) >= int(limit or MAX_RECOMMENDED_ETFS):
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
        return {
            **existing,
            "recommended_etfs": [
                normalize_etf_candidate(
                    item,
                    rank=index + 1,
                    default_source=to_text(existing.get("source"), "融资 ETF 本地配置"),
                    margin_context=existing_context,
                )
                for index, item in enumerate(as_list(existing.get("recommended_etfs"))[: int(limit or MAX_RECOMMENDED_ETFS)])
            ],
            "watch_not_chase": _dedupe_text(existing.get("watch_not_chase"), fallback="不追高 ETF；等待回踩、量能和风险线确认。", limit=MAX_RECOMMENDED_ETFS),
            "risk_notes": _dedupe_text(existing.get("risk_notes"), fallback="DeepSeek 未调用；ETF 深度调研仍需手动按钮触发。"),
            "cache_state": _first_text(existing.get("cache_state"), existing.get("data_status"), default="ready"),
            "manual_required_text": _first_text(
                existing.get("manual_required_text"),
                default="融资 ETF 只读取本地配置或手动刷新结果；页面打开不会自动全量发现。",
            ),
            "deepseek_called": False,
        }
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
    status = _derive_status(allocation, daily, live_section, etfs)
    updated_at = _first_text(
        live_section.get("updated_at"),
        daily.get("updated_at"),
        allocation.get("generated_at"),
        allocation.get("updated_at"),
    )
    source = _first_text(live_section.get("source"), daily.get("source"), allocation.get("data_source"), default="融资 ETF 本地配置快照")
    return {
        "status": status,
        "cache_state": _derive_data_status(status, daily, etfs),
        "source": source,
        "updated_at": updated_at,
        "current_margin_ratio": current_ratio,
        "recommended_margin_ratio": recommended_ratio,
        "recommended_cash_ratio": recommended_cash_ratio,
        "today_main_direction": _derive_main_direction(live_section, allocation, etfs),
        "recommended_etfs": etfs,
        "watch_not_chase": _watch_not_chase_items(allocation, etfs),
        "risk_state": _derive_risk_state(allocation, current_ratio, recommended_ratio, etfs),
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
        "deepseek_called": False,
    }
