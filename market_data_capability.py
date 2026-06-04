from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


SOURCE_TUSHARE = "Tushare"
SOURCE_UNIFIED = "Unified data capability"
MAX_ERROR_LENGTH = 180

STATE_AVAILABLE = "available"
STATE_PERMISSION_DENIED = "permission_denied"
STATE_EMPTY_RECENT = "empty_recent"
STATE_STALE_CACHE = "stale_cache"
STATE_FALLBACK_USED = "fallback_used"
STATE_DISABLED_THIS_SESSION = "disabled_this_session"
STATE_REQUIRES_MANUAL_REFRESH = "requires_manual_refresh"
STATE_NETWORK_FAILED = "network_failed"
STATE_NOT_CONFIGURED = "not_configured"
STATE_FAILED = "failed"

STATE_LABELS = {
    STATE_AVAILABLE: "可用",
    STATE_PERMISSION_DENIED: "权限不足",
    STATE_EMPTY_RECENT: "近期无数据",
    STATE_STALE_CACHE: "使用缓存",
    STATE_FALLBACK_USED: "使用替代口径",
    STATE_DISABLED_THIS_SESSION: "本会话跳过",
    STATE_REQUIRES_MANUAL_REFRESH: "需要手动刷新",
    STATE_NETWORK_FAILED: "网络失败",
    STATE_NOT_CONFIGURED: "未配置",
    STATE_FAILED: "调用失败",
}

ROOT_CAUSE_LABELS = {
    "available": "已有可用返回",
    "permission_scope": "接口权限/积分",
    "session_skip": "本会话跳过防卡顿",
    "publish_window": "近期无记录/发布窗口",
    "cache_guard": "使用缓存防白屏",
    "fallback_proxy": "替代口径",
    "manual_gate": "手动刷新门控",
    "configuration": "配置/网络/调用失败",
    "not_checked": "尚未检测",
}

PERMISSION_KEYWORDS = (
    "权限",
    "无接口访问权限",
    "permission",
    "积分",
    "没有访问",
    "抱歉",
    "denied",
    "forbidden",
    "unauthorized",
)

NETWORK_KEYWORDS = (
    "connection",
    "network",
    "timed out",
    "timeout",
    "nameresolution",
    "name resolution",
    "max retries",
    "网络",
)

NOT_CONFIGURED_KEYWORDS = (
    "缺少",
    "未配置",
    "token",
    "api key",
    "apikey",
)

SESSION_SKIP_KEYWORDS = (
    "本会话跳过",
    "跳过重复请求",
    "disabled_this_session",
    "skip",
)

EMPTY_RECENT_KEYWORDS = (
    "无数据",
    "未见",
    "未取得",
    "暂无",
    "尚未",
    "empty",
    "no data",
)

FACT_SECTION_LABELS = {
    "dragon_tiger": "龙虎榜",
    "margin": "融资融券",
    "moneyflow": "个股资金流",
    "limit_emotion": "涨跌停/情绪",
    "chip_radar": "筹码/胜率",
}

FACT_SECTION_APIS = {
    "dragon_tiger": "top_list/top_inst",
    "margin": "margin_detail",
    "moneyflow": "moneyflow",
    "limit_emotion": "stk_limit / limit_list_d / limit_cpt_list",
    "chip_radar": "cyq_perf/cyq_chips",
}

HARD_RISK_SECTION_LABELS = {
    "announcements": "公告风险",
    "free_announcement_radar": "免费公告雷达",
    "earnings_forecast": "业绩预告",
    "holder_reduction": "股东减持",
    "share_unlock": "限售解禁",
    "pledge": "股权质押",
    "institution_surveys": "机构调研",
}

HARD_RISK_SECTION_APIS = {
    "announcements": "anns_d",
    "free_announcement_radar": "stock_reports.announcement_summary",
    "earnings_forecast": "forecast",
    "holder_reduction": "stk_holdertrade",
    "share_unlock": "share_float",
    "pledge": "pledge_stat/pledge_detail",
    "institution_surveys": "stk_surv",
}

MANUAL_PROVIDER_ITEMS = (
    {
        "provider": "AkShare",
        "api": "akshare_manual_refresh",
        "label": "AkShare 重型刷新",
        "error": "尚未手动检测；页面打开不自动调用 AkShare 重型刷新。",
        "requires_manual_refresh": True,
    },
    {
        "provider": "yfinance",
        "api": "yfinance_market_data",
        "label": "yfinance 行情/新闻",
        "error": "尚未手动检测；页面打开不自动调用 yfinance。",
        "requires_manual_refresh": True,
    },
)

LATEST_DATE_KEYS = (
    "latest_date",
    "date",
    "trade_date",
    "ann_date",
    "end_date",
    "float_date",
    "surv_date",
    "concept_date",
    "updated_at",
)


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def compact_error(error: Any, limit: int = MAX_ERROR_LENGTH) -> str:
    text = str(error or "").strip()
    if not text:
        return ""
    return text if len(text) <= limit else text[:limit] + "..."


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lower = str(text or "").lower()
    return any(keyword.lower() in lower for keyword in keywords)


def is_permission_error(error: Any) -> bool:
    text = str(error or "")
    lower = text.lower()
    strict_keywords = (
        "无接口访问权限",
        "当前权限不足",
        "没有访问",
        "抱歉",
        "permission",
        "denied",
        "forbidden",
        "unauthorized",
    )
    if "可能" in text and not any(keyword.lower() in lower for keyword in strict_keywords):
        return False
    return _contains_any(text, PERMISSION_KEYWORDS)


def is_network_error(error: Any) -> bool:
    return _contains_any(str(error or ""), NETWORK_KEYWORDS)


def is_not_configured_error(error: Any) -> bool:
    return _contains_any(str(error or ""), NOT_CONFIGURED_KEYWORDS)


def is_session_skip_error(error: Any) -> bool:
    return _contains_any(str(error or ""), SESSION_SKIP_KEYWORDS)


def is_empty_recent_message(error: Any) -> bool:
    text = str(error or "")
    if is_permission_error(text) or is_network_error(text) or is_not_configured_error(text):
        return False
    return _contains_any(text, EMPTY_RECENT_KEYWORDS)


def extract_frame_summary(data: Any) -> tuple[int, str]:
    if data is None:
        return 0, ""
    try:
        rows = len(data)
    except Exception:
        rows = 0
    latest_date = ""
    try:
        empty = bool(getattr(data, "empty", False))
        columns = list(getattr(data, "columns", []) or [])
        if not empty and columns:
            for column in ("trade_date", "cal_date", "ann_date", "end_date", "float_date", "surv_date", "date"):
                if column not in columns:
                    continue
                series = data[column]
                values = series.dropna().tolist() if hasattr(series, "dropna") else list(series)
                values = [str(value) for value in values if str(value).strip()]
                if values:
                    latest_date = sorted(values, reverse=True)[0]
                    break
    except Exception:
        latest_date = ""
    return rows, latest_date


def classify_capability_state(
    ok: bool = False,
    rows: int | float | None = 0,
    error: Any = "",
    cached: bool = False,
    stale: bool = False,
    fallback_used: bool = False,
    skipped: bool = False,
    requires_manual_refresh: bool = False,
) -> str:
    error_text = compact_error(error)
    if skipped or is_session_skip_error(error_text):
        return STATE_DISABLED_THIS_SESSION
    if requires_manual_refresh:
        return STATE_REQUIRES_MANUAL_REFRESH
    if fallback_used:
        return STATE_FALLBACK_USED
    if cached or stale:
        return STATE_STALE_CACHE
    if is_not_configured_error(error_text):
        return STATE_NOT_CONFIGURED
    if is_permission_error(error_text):
        return STATE_PERMISSION_DENIED
    if is_network_error(error_text):
        return STATE_NETWORK_FAILED
    numeric_rows = rows if isinstance(rows, Number) else 0
    if ok and numeric_rows == 0:
        return STATE_EMPTY_RECENT
    if not ok and is_empty_recent_message(error_text):
        return STATE_EMPTY_RECENT
    if ok:
        return STATE_AVAILABLE
    return STATE_FAILED


def state_label(state: str) -> str:
    return STATE_LABELS.get(str(state or ""), STATE_LABELS[STATE_FAILED])


def normalize_capability_state_value(value: Any) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if lower in set(STATE_LABELS):
        return lower
    if lower in {"missing", "waiting", "pending"} or text in {"待刷新", "待验证"}:
        return STATE_EMPTY_RECENT
    if is_session_skip_error(text):
        return STATE_DISABLED_THIS_SESSION
    if is_permission_error(text):
        return STATE_PERMISSION_DENIED
    if is_not_configured_error(text):
        return STATE_NOT_CONFIGURED
    if is_network_error(text):
        return STATE_NETWORK_FAILED
    if "手动" in text or "manual" in lower:
        return STATE_REQUIRES_MANUAL_REFRESH
    if "缓存" in text or "cache" in lower:
        return STATE_STALE_CACHE
    if "替代" in text or "fallback" in lower:
        return STATE_FALLBACK_USED
    if is_empty_recent_message(text):
        return STATE_EMPTY_RECENT
    if "失败" in text or "error" in lower:
        return STATE_FAILED
    if "可用" in text or "通过" in text or lower in {"ready", "ok", "success"}:
        return STATE_AVAILABLE
    return "unknown"


def tone_for_capability_state(state: str) -> str:
    normalized = normalize_capability_state_value(state)
    if normalized == STATE_AVAILABLE:
        return "ready"
    if normalized in {STATE_PERMISSION_DENIED, STATE_DISABLED_THIS_SESSION, STATE_NOT_CONFIGURED, STATE_NETWORK_FAILED, STATE_FAILED}:
        return "failed"
    if normalized in {STATE_STALE_CACHE, STATE_FALLBACK_USED}:
        return "stale"
    return "missing"


def meaning_for_capability_state(state: str, provider: Any = "数据源", label: Any = "数据能力") -> str:
    normalized = normalize_capability_state_value(state)
    provider_text = str(provider or "数据源").strip() or "数据源"
    label_text = str(label or "数据能力").strip() or "数据能力"
    if normalized == STATE_AVAILABLE:
        return f"{label_text}已有可用返回，可作为辅助证据。"
    if normalized == STATE_PERMISSION_DENIED:
        return f"{provider_text} token 可用不等于 {label_text} 有权限；这是接口权限/积分问题，不是行情不存在。"
    if normalized == STATE_DISABLED_THIS_SESSION:
        return f"{label_text}此前已判定不可用，本会话跳过重复请求，避免页面反复卡住。"
    if normalized == STATE_EMPTY_RECENT:
        return f"{label_text}近期无记录，常见原因是非交易日、数据尚未发布、标的未上榜或接口暂不覆盖。"
    if normalized == STATE_STALE_CACHE:
        return f"{label_text}正在展示上次成功结果；这是缓存，不是实时数据。"
    if normalized == STATE_FALLBACK_USED:
        return f"{label_text}使用替代口径，不能等同于原始接口事实。"
    if normalized == STATE_REQUIRES_MANUAL_REFRESH:
        return f"{label_text}属于手动刷新能力；页面打开不会自动请求。"
    if normalized == STATE_NOT_CONFIGURED:
        return f"{provider_text} 未配置或本地 token/secrets 不可用。"
    if normalized == STATE_NETWORK_FAILED:
        return f"{label_text}网络请求失败；保留缓存或安全空态。"
    if normalized == STATE_FAILED:
        return f"{label_text}调用失败；当前不能作为交易依据。"
    return f"{label_text}状态待验证；当前只能作为数据缺口记录。"


def decision_impact_for_capability_state(state: str, label: Any = "数据能力") -> str:
    normalized = normalize_capability_state_value(state)
    label_text = str(label or "数据能力").strip() or "数据能力"
    if normalized == STATE_AVAILABLE:
        return f"{label_text}可进入证据链，但仍需和价格、纪律、仓位一起验证。"
    if normalized == STATE_EMPTY_RECENT:
        return f"{label_text}近期无记录不能写成利好或无风险，只能说明缺少可验证事件。"
    if normalized == STATE_PERMISSION_DENIED:
        return f"{label_text}权限不足，不能把缺失数据当成利好，也不能支撑加仓、追高或放大仓位。"
    if normalized in {STATE_DISABLED_THIS_SESSION, STATE_NOT_CONFIGURED, STATE_NETWORK_FAILED, STATE_FAILED}:
        return f"{label_text}不可用，不能支撑加仓、追高或放大仓位。"
    if normalized in {STATE_STALE_CACHE, STATE_FALLBACK_USED}:
        return f"{label_text}只能作为缓存/替代证据，执行前要复核交易日、来源和更新时间。"
    if normalized == STATE_REQUIRES_MANUAL_REFRESH:
        return f"{label_text}需要手动刷新后才能进入当日判断。"
    return f"{label_text}待验证，不能作为核心依据。"


def next_action_for_capability_state(state: str, label: Any = "数据能力") -> str:
    normalized = normalize_capability_state_value(state)
    label_text = str(label or "数据能力").strip() or "数据能力"
    if normalized == STATE_AVAILABLE:
        return f"继续核对 {label_text} 的交易日、来源和是否匹配当前标的。"
    if normalized == STATE_PERMISSION_DENIED:
        return f"检查 {label_text} 对应接口权限/积分；接口接入成功不等于当前账户有权限。"
    if normalized == STATE_DISABLED_THIS_SESSION:
        return f"如权限已恢复，手动重试并重新检测 {label_text}。"
    if normalized == STATE_EMPTY_RECENT:
        return f"确认是否交易日、是否已发布、标的是否属于 {label_text} 覆盖范围。"
    if normalized == STATE_STALE_CACHE:
        return f"需要最新口径时手动刷新 {label_text}；否则按缓存标注使用。"
    if normalized == STATE_FALLBACK_USED:
        return f"把 {label_text} 标记为替代口径，并等待原始接口恢复。"
    if normalized == STATE_REQUIRES_MANUAL_REFRESH:
        return f"点击对应按钮后再请求 {label_text}。"
    if normalized == STATE_NOT_CONFIGURED:
        return f"检查 {label_text} 的本地 token/secrets 配置。"
    if normalized == STATE_NETWORK_FAILED:
        return f"网络恢复后手动重试 {label_text}。"
    return f"保留 {label_text} 的安全空态或上次成功结果。"


def root_cause_code_for_capability_state(state: Any) -> str:
    normalized = normalize_capability_state_value(state)
    if normalized == STATE_AVAILABLE:
        return "available"
    if normalized == STATE_PERMISSION_DENIED:
        return "permission_scope"
    if normalized == STATE_DISABLED_THIS_SESSION:
        return "session_skip"
    if normalized == STATE_EMPTY_RECENT:
        return "publish_window"
    if normalized == STATE_STALE_CACHE:
        return "cache_guard"
    if normalized == STATE_FALLBACK_USED:
        return "fallback_proxy"
    if normalized == STATE_REQUIRES_MANUAL_REFRESH:
        return "manual_gate"
    if normalized in {STATE_NOT_CONFIGURED, STATE_NETWORK_FAILED, STATE_FAILED}:
        return "configuration"
    return "not_checked"


def root_cause_label_for_capability_state(state: Any) -> str:
    return ROOT_CAUSE_LABELS.get(root_cause_code_for_capability_state(state), ROOT_CAUSE_LABELS["not_checked"])


def why_previous_full_refresh_not_enough(
    state: Any,
    provider: Any = "数据源",
    label: Any = "数据能力",
    api: Any = "",
) -> str:
    cause_code = root_cause_code_for_capability_state(state)
    provider_text = str(provider or "数据源").strip() or "数据源"
    label_text = str(label or "数据能力").strip() or "数据能力"
    api_text = str(api or "专业接口").strip() or "专业接口"
    if provider_text == SOURCE_TUSHARE and cause_code == "permission_scope":
        return f"之前“拉满”多半覆盖基础行情或已授权接口；{label_text} 的 {api_text} 仍需要单独权限/积分。"
    if cause_code == "permission_scope":
        return f"{provider_text} 可用不等于 {label_text} 的 {api_text} 已授权。"
    if cause_code == "session_skip":
        return f"{label_text} 此前已被判定受限或失败，本会话为了防卡顿跳过重复请求；这不是数据被清空。"
    if cause_code == "publish_window":
        return f"{label_text} 可能接口可用但近窗口无记录；非交易日、尚未发布、标的未上榜都会让结果为空。"
    if cause_code == "cache_guard":
        return f"{label_text} 现在显示的是上次成功缓存；这是为了防白屏，不代表今天已经重新验证。"
    if cause_code == "fallback_proxy":
        return f"{label_text} 当前使用替代口径；能辅助观察，但不能当作原始 {api_text} 已恢复。"
    if cause_code == "manual_gate":
        return f"{label_text} 被设置为手动按钮触发；首页打开不会自动请求 {api_text}。"
    if cause_code == "available":
        return f"{label_text} 已有可用返回；仍要核对日期、标的和接口口径是否匹配当前决策。"
    if cause_code == "configuration":
        return f"{label_text} 当前更像配置、网络或接口调用失败；先修复环境，再手动验证。"
    return f"{label_text} 尚未检测；不能用“之前拉过”证明当前这个接口已可用。"


def action_hint_for_state(state: str) -> str:
    if state == STATE_AVAILABLE:
        return "可作为已验证数据使用。"
    if state == STATE_PERMISSION_DENIED:
        return "检查 Tushare 积分/接口权限；保留缓存，不要重复自动请求。"
    if state == STATE_EMPTY_RECENT:
        return "这可能是非交易日、数据尚未发布或标的近期无记录。"
    if state == STATE_STALE_CACHE:
        return "当前使用上次成功结果；需要时手动刷新。"
    if state == STATE_FALLBACK_USED:
        return "已使用替代口径，不能等同于原始接口事实。"
    if state == STATE_DISABLED_THIS_SESSION:
        return "本会话已跳过重复请求；如权限已恢复，请手动重新检测。"
    if state == STATE_REQUIRES_MANUAL_REFRESH:
        return "点击对应刷新按钮后再请求；页面打开不自动调用。"
    if state == STATE_NETWORK_FAILED:
        return "检查网络后手动重试；保留缓存或显示待验证。"
    if state == STATE_NOT_CONFIGURED:
        return "检查本地 token / secrets 配置。"
    return "保留安全空态或上次成功结果。"


def build_capability_item(
    api: str,
    ok: bool = False,
    rows: int | float | None = 0,
    latest_date: Any = "",
    latency_ms: int | float | None = 0,
    error: Any = "",
    source: str = SOURCE_TUSHARE,
    cached: bool = False,
    stale: bool = False,
    fallback_used: bool = False,
    skipped: bool = False,
    requires_manual_refresh: bool = False,
) -> dict:
    error_text = compact_error(error)
    state = classify_capability_state(
        ok=bool(ok),
        rows=rows,
        error=error_text,
        cached=bool(cached),
        stale=bool(stale),
        fallback_used=bool(fallback_used),
        skipped=bool(skipped),
        requires_manual_refresh=bool(requires_manual_refresh),
    )
    row_count = int(rows) if isinstance(rows, Number) else 0
    return {
        "api": str(api or ""),
        "source": source,
        "provider": source,
        "ok": bool(ok) and state == STATE_AVAILABLE,
        "rows": row_count,
        "latest_date": str(latest_date or ""),
        "latency_ms": int(latency_ms or 0),
        "error": error_text,
        "permission_likely": state == STATE_PERMISSION_DENIED,
        "status": state_label(state),
        "capability_state": state,
        "capability_label": state_label(state),
        "action_hint": action_hint_for_state(state),
        "should_skip_session": state == STATE_PERMISSION_DENIED,
        "can_retry": state in {STATE_NETWORK_FAILED, STATE_FAILED, STATE_DISABLED_THIS_SESSION},
    }


def build_provider_capability_item(
    provider: str,
    api: str,
    label: str = "",
    ok: bool = False,
    rows: int | float | None = 0,
    latest_date: Any = "",
    latency_ms: int | float | None = 0,
    error: Any = "",
    cached: bool = False,
    stale: bool = False,
    fallback_used: bool = False,
    skipped: bool = False,
    requires_manual_refresh: bool = False,
) -> dict:
    item = build_capability_item(
        api,
        ok=ok,
        rows=rows,
        latest_date=latest_date,
        latency_ms=latency_ms,
        error=error,
        source=provider,
        cached=cached,
        stale=stale,
        fallback_used=fallback_used,
        skipped=skipped,
        requires_manual_refresh=requires_manual_refresh,
    )
    item["provider"] = provider
    item["label"] = label or api or provider
    return item


def summarize_tushare_result(api: str, result: Any = None, latency_ms: int | float | None = 0) -> dict:
    payload = as_mapping(result)
    if not payload:
        return build_capability_item(
            api,
            latency_ms=latency_ms,
            error=f"返回类型异常：{type(result).__name__}",
        )
    data = payload.get("data")
    rows, latest_date = extract_frame_summary(data)
    ok = bool(payload.get("ok"))
    error_text = payload.get("error") if not ok else ""
    if payload.get("rows") is not None:
        try:
            rows = int(payload.get("rows"))
        except Exception:
            pass
    latest_date = payload.get("latest_date") or latest_date
    return build_capability_item(
        api,
        ok=ok,
        rows=rows,
        latest_date=latest_date,
        latency_ms=latency_ms,
        error=error_text,
        source=str(payload.get("source") or SOURCE_TUSHARE),
        cached=bool(payload.get("cached") or payload.get("from_cache")),
        stale=bool(payload.get("stale")),
        fallback_used=bool(payload.get("fallback_used")),
        skipped=bool(payload.get("skipped") or payload.get("disabled_this_session")),
        requires_manual_refresh=bool(payload.get("requires_manual_refresh")),
    )


def summarize_tushare_exception(api: str, exc: Any, latency_ms: int | float | None = 0) -> dict:
    return build_capability_item(api, latency_ms=latency_ms, error=exc)


def empty_tushare_item(api: str, error: Any = "") -> dict:
    return build_capability_item(api, error=error)


def build_tushare_capability_packet(items: Any, checked_at: Any = "", source: str = SOURCE_TUSHARE) -> dict:
    normalized = [as_mapping(item) for item in (items or [])]
    normalized = [item for item in normalized if item]
    ok_count = sum(1 for item in normalized if item.get("capability_state") == STATE_AVAILABLE or item.get("ok"))
    permission_denied_count = sum(1 for item in normalized if item.get("capability_state") == STATE_PERMISSION_DENIED or item.get("permission_likely"))
    empty_count = sum(1 for item in normalized if item.get("capability_state") == STATE_EMPTY_RECENT)
    cache_count = sum(1 for item in normalized if item.get("capability_state") == STATE_STALE_CACHE)
    skipped_count = sum(1 for item in normalized if item.get("capability_state") == STATE_DISABLED_THIS_SESSION)
    failed_count = len(normalized) - ok_count
    return {
        "source": source,
        "checked_at": str(checked_at or ""),
        "ok_count": ok_count,
        "failed_count": failed_count,
        "permission_denied_count": permission_denied_count,
        "empty_count": empty_count,
        "cache_count": cache_count,
        "skipped_count": skipped_count,
        "items": normalized,
        "summary": (
            f"{source}：{ok_count}/{len(normalized)} 可用，"
            f"权限不足 {permission_denied_count}，无数据 {empty_count}，缓存 {cache_count}，本会话跳过 {skipped_count}。"
        ),
        "deepseek_called": False,
    }


def _normalize_existing_item(item: Any, provider: str = "", label_key: str = "label") -> dict:
    payload = as_mapping(item)
    if not payload:
        return {}
    provider_text = str(provider or payload.get("provider") or payload.get("source") or SOURCE_TUSHARE)
    state = str(payload.get("capability_state") or payload.get("state") or "")
    if state:
        normalized = build_provider_capability_item(
            provider_text,
            str(payload.get("api") or payload.get("table") or payload.get("section") or ""),
            label=str(payload.get(label_key) or payload.get("label") or payload.get("table") or payload.get("api") or ""),
            ok=state == STATE_AVAILABLE,
            rows=payload.get("rows") or 0,
            latest_date=payload.get("latest_date") or payload.get("updated_at") or "",
            latency_ms=payload.get("latency_ms") or 0,
            error=payload.get("error") or "",
            cached=state == STATE_STALE_CACHE,
            fallback_used=state == STATE_FALLBACK_USED,
            skipped=state == STATE_DISABLED_THIS_SESSION,
            requires_manual_refresh=state == STATE_REQUIRES_MANUAL_REFRESH,
        )
        normalized["capability_state"] = state
        normalized["status"] = str(payload.get("status") or state_label(state))
        normalized["capability_label"] = str(payload.get("capability_label") or normalized["status"])
        normalized["ok"] = state == STATE_AVAILABLE
        normalized["permission_likely"] = state == STATE_PERMISSION_DENIED
        normalized["should_skip_session"] = state == STATE_PERMISSION_DENIED
        normalized["can_retry"] = state in {STATE_NETWORK_FAILED, STATE_FAILED, STATE_DISABLED_THIS_SESSION}
        normalized["action_hint"] = str(payload.get("action_hint") or action_hint_for_state(state))
    else:
        normalized = build_provider_capability_item(
            provider_text,
            str(payload.get("api") or payload.get("table") or payload.get("section") or ""),
            label=str(payload.get(label_key) or payload.get("label") or payload.get("table") or payload.get("api") or ""),
            ok=bool(payload.get("ok")),
            rows=payload.get("rows") or payload.get("count") or 0,
            latest_date=payload.get("latest_date") or payload.get("updated_at") or "",
            latency_ms=payload.get("latency_ms") or 0,
            error=payload.get("error") or payload.get("message") or "",
            cached=bool(payload.get("cached") or payload.get("from_cache")),
            stale=bool(payload.get("stale")),
            fallback_used=bool(payload.get("fallback_used")),
            skipped=bool(payload.get("skipped") or payload.get("disabled_this_session")),
            requires_manual_refresh=bool(payload.get("requires_manual_refresh")),
        )
    normalized.update(
        {
            "provider": provider_text,
            "source": str(payload.get("source") or provider_text),
            "section": str(payload.get("section") or normalized.get("api") or ""),
            "updated_at": str(payload.get("updated_at") or ""),
            "message": str(payload.get("message") or ""),
            "warning": str(payload.get("warning") or ""),
        }
    )
    return normalized


def build_supabase_capability_packet(supabase_result: Any = None) -> dict:
    payload = as_mapping(supabase_result)
    raw_items = payload.get("items") or []
    items = [_normalize_existing_item(item, provider="Supabase", label_key="table") for item in raw_items]
    items = [item for item in items if item]
    return build_tushare_capability_packet(
        items,
        checked_at=payload.get("checked_at") or "",
        source="Supabase",
    )


def build_manual_provider_items(include_akshare: bool = True, include_yfinance: bool = True) -> list[dict]:
    items = []
    for spec in MANUAL_PROVIDER_ITEMS:
        if spec["provider"] == "AkShare" and not include_akshare:
            continue
        if spec["provider"] == "yfinance" and not include_yfinance:
            continue
        items.append(
            build_provider_capability_item(
                spec["provider"],
                spec["api"],
                label=spec["label"],
                error=spec["error"],
                requires_manual_refresh=bool(spec.get("requires_manual_refresh")),
            )
        )
    return items


def build_unified_provider_capability_packet(
    health_result: Any = None,
    a_share_packet: Any = None,
    include_manual_providers: bool = True,
    checked_at: Any = "",
) -> dict:
    health = as_mapping(health_result)
    a_share = as_mapping(a_share_packet)
    items = []

    if a_share.get("items"):
        items.extend(_normalize_existing_item(item, provider=SOURCE_TUSHARE) for item in a_share.get("items") or [])
    elif a_share:
        a_share_professional = build_a_share_professional_capability_packet(a_share)
        items.extend(_normalize_existing_item(item, provider=SOURCE_TUSHARE) for item in a_share_professional.get("items") or [])

    tushare_packet = as_mapping(health.get("tushare"))
    if tushare_packet.get("items"):
        items.extend(_normalize_existing_item(item, provider=tushare_packet.get("source") or SOURCE_TUSHARE) for item in tushare_packet.get("items") or [])

    supabase_packet = as_mapping(health.get("supabase"))
    if supabase_packet.get("items"):
        items.extend(_normalize_existing_item(item, provider="Supabase", label_key="table") for item in supabase_packet.get("items") or [])

    if include_manual_providers and (health or a_share):
        existing_providers = {str(item.get("provider") or item.get("source") or "") for item in items}
        items.extend(
            item
            for item in build_manual_provider_items()
            if item.get("provider") not in existing_providers
        )

    normalized = [item for item in items if item]
    packet = build_tushare_capability_packet(
        normalized,
        checked_at=checked_at or health.get("checked_at") or a_share.get("checked_at") or a_share.get("updated_at") or "",
        source=SOURCE_UNIFIED,
    )
    providers: dict[str, dict] = {}
    for item in normalized:
        provider = str(item.get("provider") or item.get("source") or "数据源")
        provider_summary = providers.setdefault(provider, {"total": 0, "available": 0, "restricted": 0, "pending": 0})
        provider_summary["total"] += 1
        state = item.get("capability_state")
        if state == STATE_AVAILABLE:
            provider_summary["available"] += 1
        elif state in {STATE_PERMISSION_DENIED, STATE_DISABLED_THIS_SESSION, STATE_NOT_CONFIGURED, STATE_NETWORK_FAILED, STATE_FAILED}:
            provider_summary["restricted"] += 1
        else:
            provider_summary["pending"] += 1
    packet["providers"] = providers
    packet["deepseek_called"] = False
    return packet


def _first_text(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in [None, ""]:
            return str(value)
    return ""


def _row_count(payload: Mapping[str, Any]) -> int:
    for key in ("rows", "items", "records", "top5"):
        value = payload.get(key)
        if isinstance(value, Number) and not isinstance(value, bool):
            return int(value)
        try:
            return len(value)
        except Exception:
            continue
    return 0


def _section_latest_date(payload: Mapping[str, Any]) -> str:
    data_date_keys = tuple(key for key in LATEST_DATE_KEYS if key != "updated_at")
    latest = _first_text(payload, data_date_keys)
    if latest:
        return latest
    rows = payload.get("rows") or payload.get("items") or payload.get("records") or []
    if not isinstance(rows, (list, tuple)):
        return _first_text(payload, ("updated_at",))
    values = []
    for row in rows:
        row_map = as_mapping(row)
        text = _first_text(row_map, data_date_keys)
        if text:
            values.append(text)
    return sorted(values, reverse=True)[0] if values else _first_text(payload, ("updated_at",))


def build_tushare_fact_capability_item(section_key: str, fact_packet: Any) -> dict:
    payload = as_mapping(fact_packet)
    api = str(payload.get("api") or FACT_SECTION_APIS.get(section_key, section_key))
    label = FACT_SECTION_LABELS.get(section_key, section_key)
    available = bool(
        payload.get("available")
        or payload.get("boundary_available")
        or payload.get("records_available")
        or payload.get("concept_available")
    )
    latest_date = _section_latest_date(payload)
    error_text = (
        payload.get("error")
        or payload.get("warning")
        or payload.get("message")
        or ("暂无可验证数据" if not available else "")
    )
    item = build_capability_item(
        api,
        ok=available,
        rows=_row_count(payload) or (1 if available else 0),
        latest_date=latest_date,
        latency_ms=payload.get("latency_ms") or 0,
        error=error_text,
        source=str(payload.get("source") or SOURCE_TUSHARE),
        cached=bool(payload.get("cached") or payload.get("from_cache")),
        stale=bool(payload.get("stale")),
        fallback_used=bool(payload.get("fallback_used")),
        skipped=bool(payload.get("skipped") or payload.get("disabled_this_session")),
        requires_manual_refresh=bool(payload.get("requires_manual_refresh")),
    )
    item.update(
        {
            "section": section_key,
            "label": label,
            "message": str(payload.get("message") or ""),
            "warning": str(payload.get("warning") or ""),
            "updated_at": str(payload.get("updated_at") or ""),
        }
    )
    return item


def build_tushare_hard_risk_capability_item(section_key: str, fact_packet: Any) -> dict:
    payload = as_mapping(fact_packet)
    api = str(payload.get("api") or HARD_RISK_SECTION_APIS.get(section_key, section_key))
    label = HARD_RISK_SECTION_LABELS.get(section_key, section_key)
    available = bool(payload.get("available") or _row_count(payload) or payload.get("risk_flags"))
    error_text = (
        payload.get("error")
        or payload.get("warning")
        or payload.get("message")
        or ("暂无可验证数据" if not available else "")
    )
    item = build_capability_item(
        api,
        ok=available,
        rows=_row_count(payload) or (len(payload.get("risk_flags") or []) if isinstance(payload.get("risk_flags"), list) else 0),
        latest_date=_section_latest_date(payload),
        latency_ms=payload.get("latency_ms") or 0,
        error=error_text,
        source=str(payload.get("source") or SOURCE_TUSHARE),
        cached=bool(payload.get("cached") or payload.get("from_cache")),
        stale=bool(payload.get("stale")),
        fallback_used=bool(payload.get("fallback_used")),
        skipped=bool(payload.get("skipped") or payload.get("disabled_this_session")),
        requires_manual_refresh=bool(payload.get("requires_manual_refresh")),
    )
    item.update(
        {
            "section": f"hard_risk.{section_key}",
            "label": label,
            "message": str(payload.get("message") or ""),
            "warning": str(payload.get("warning") or ""),
            "updated_at": str(payload.get("updated_at") or ""),
        }
    )
    return item


def build_hard_risk_capability_items(fact_packet: Any) -> list[dict]:
    payload = as_mapping(fact_packet)
    hard_risk = as_mapping(payload.get("verified_hard_risks") or payload.get("hard_risk") or payload)
    if not hard_risk:
        return []
    return [
        build_tushare_hard_risk_capability_item(section, hard_risk.get(section) or {})
        for section in HARD_RISK_SECTION_LABELS
    ]


def build_a_share_professional_capability_packet(fact_packet: Any, checked_at: Any = "") -> dict:
    payload = as_mapping(fact_packet)
    items = [
        build_tushare_fact_capability_item(section, payload.get(section) or {})
        for section in FACT_SECTION_LABELS
    ]
    items.extend(build_hard_risk_capability_items(payload))
    packet = build_tushare_capability_packet(
        items,
        checked_at=checked_at or payload.get("updated_at") or "",
        source="Tushare A股专业事实",
    )
    packet.update(
        {
            "stock_code": str(payload.get("stock_code") or ""),
            "data_source": str(payload.get("data_source") or "Tushare + yfinance technical"),
            "sections": FACT_SECTION_LABELS.copy(),
            "deepseek_called": False,
        }
    )
    return packet
