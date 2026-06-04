"""Service layer for data-capability governance.

Responsibilities:
1. 把 registry 状态转换为现有 command_center 能识别的 capability item 结构。
2. 将外部探测结果映射到 registry 状态（不直接发起请求）。
3. 为两类主按钮提供统一的能力状态快照入口。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import market_data_capability as data_capability
from data_capability_registry import (
    STATUS_AVAILABLE,
    STATUS_CACHED,
    STATUS_FAILED,
    STATUS_NO_DATA,
    STATUS_NO_PERMISSION,
    STATUS_SKIPPED,
    STATUS_UNKNOWN,
    TIER_CORE,
    build_initial_capability_registry,
    to_status_dict,
    update_capability_status,
)


STATUS_TO_LEGACY_STATE = {
    STATUS_AVAILABLE: data_capability.STATE_AVAILABLE,
    STATUS_NO_PERMISSION: data_capability.STATE_PERMISSION_DENIED,
    STATUS_FAILED: data_capability.STATE_FAILED,
    STATUS_NO_DATA: data_capability.STATE_EMPTY_RECENT,
    STATUS_CACHED: data_capability.STATE_STALE_CACHE,
    STATUS_SKIPPED: data_capability.STATE_REQUIRES_MANUAL_REFRESH,
    STATUS_UNKNOWN: "unknown",
}


_PROVIDER_ITEM_API_FALLBACK = {
    "deepseek": "deepseek_explain",
    "yfinance_quote": "yfinance_quote",
    "brain_memory": "brain_memory",
    "market_news": "market_news",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def map_status_to_legacy_state(status: Any) -> str:
    normalized = to_status_dict(status)
    if normalized == STATUS_UNKNOWN:
        return data_capability.STATE_EMPTY_RECENT
    return STATUS_TO_LEGACY_STATE.get(normalized, data_capability.STATE_EMPTY_RECENT)


def _legacy_capability_item(item: dict[str, Any]) -> dict[str, Any]:
    payload = dict(item)
    status = to_status_dict(payload.get("status"))
    legacy_state = map_status_to_legacy_state(status)

    latest_at = str(payload.get("last_success_at") or payload.get("updated_at") or "")
    ok = legacy_state == data_capability.STATE_AVAILABLE
    rows = 1 if ok else 0
    cached = legacy_state == data_capability.STATE_STALE_CACHE

    reason = str(payload.get("last_error") or "")
    requires_manual_refresh = bool(
        legacy_state == data_capability.STATE_REQUIRES_MANUAL_REFRESH
        or payload.get("requires_user_action")
    )
    skipped = legacy_state == data_capability.STATE_DISABLED_THIS_SESSION

    packet = data_capability.build_provider_capability_item(
        payload.get("provider") or "",
        payload.get("api") or "",
        label=payload.get("name") or payload.get("label") or payload.get("api") or "数据能力",
        ok=ok,
        rows=rows,
        latest_date=latest_at,
        latency_ms=payload.get("latency_ms") or 0,
        error=reason,
        cached=cached,
        stale=False,
        fallback_used=False,
        skipped=skipped,
        requires_manual_refresh=requires_manual_refresh,
    )
    packet.update(
        {
            "name": payload.get("name") or "",
            "provider": payload.get("provider") or payload.get("source") or "",
            "api": payload.get("api") or "",
            "market": payload.get("market") or "",
            "tier": payload.get("tier") or TIER_CORE,
            "status": reason or payload.get("status") or status,
            "capability_state": legacy_state,
            "capability_label": data_capability.state_label(legacy_state),
            "last_success_at": latest_at,
            "last_error": reason,
            "used_in_decision": bool(payload.get("used_in_decision", False)),
            "requires_user_action": bool(payload.get("requires_user_action", False)),
            "action_hint": payload.get("action_hint") or packet.get("action_hint") or "页面打开不自动调用。",
            "message": reason,
            "updated_at": now_iso() if latest_at else "",
            "source": payload.get("source") or payload.get("provider") or "数据能力",
        }
    )
    return packet


def build_data_capability_packet(registry: dict[str, Any] | None) -> dict[str, Any]:
    """Convert registry items to the legacy packet consumed by snapshots and overview."""

    packet = dict(registry or {})
    raw_items = packet.get("items") or []
    normalized_items = [_legacy_capability_item(item) for item in raw_items if isinstance(item, dict)]

    unified_packet = data_capability.build_tushare_capability_packet(
        normalized_items,
        checked_at=packet.get("updated_at") or packet.get("checked_at") or now_iso(),
        source="数据能力治理中心",
    )

    # keep registry 原始字段以便界面回读。
    unified_packet["registry_version"] = "mvp_v1"
    unified_packet["items"] = normalized_items
    return unified_packet


def _infer_single_item_status(
    item: dict[str, Any],
    *,
    default_status: str = STATUS_UNKNOWN,
) -> str:
    """Infer status from a capability probe item without changing any source shape."""

    if not isinstance(item, dict):
        return STATUS_FAILED
    if item.get("capability_state"):
        current = str(item.get("capability_state") or "").lower()
        if current in {
            data_capability.STATE_AVAILABLE,
            data_capability.STATE_EMPTY_RECENT,
            data_capability.STATE_STALE_CACHE,
            data_capability.STATE_FAILED,
            data_capability.STATE_PERMISSION_DENIED,
            data_capability.STATE_DISABLED_THIS_SESSION,
            data_capability.STATE_NETWORK_FAILED,
            data_capability.STATE_NOT_CONFIGURED,
            data_capability.STATE_REQUIRES_MANUAL_REFRESH,
        }:
            if current == data_capability.STATE_AVAILABLE:
                return STATUS_AVAILABLE
            if current == data_capability.STATE_EMPTY_RECENT:
                return STATUS_NO_DATA
            if current == data_capability.STATE_STALE_CACHE:
                return STATUS_CACHED
            if current == data_capability.STATE_PERMISSION_DENIED:
                return STATUS_NO_PERMISSION
            if current == data_capability.STATE_DISABLED_THIS_SESSION:
                return STATUS_SKIPPED
            if current == data_capability.STATE_REQUIRES_MANUAL_REFRESH:
                return STATUS_SKIPPED
            return STATUS_FAILED
    if item.get("ok") is True:
        return STATUS_AVAILABLE
    if item.get("available") is True:
        return STATUS_AVAILABLE
    if item.get("disabled") is True:
        return STATUS_SKIPPED
    if item.get("permission") is True or "permission" in str(item.get("error") or "").lower():
        return STATUS_NO_PERMISSION
    if item.get("cached") is True:
        return STATUS_CACHED
    if item.get("skipped") is True:
        return STATUS_SKIPPED
    if item.get("need_refresh") is True:
        return STATUS_SKIPPED
    if item.get("error"):
        return STATUS_FAILED
    return default_status


def update_from_snapshot(registry: dict[str, Any], name: str, snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return a registry copy with one capability updated from a snapshot result."""

    snapshot = snapshot or {}
    status = _infer_single_item_status(snapshot)
    if not snapshot and name:
        status = STATUS_UNKNOWN

    return update_capability_status(
        registry,
        name,
        status,
        last_success_at=str(snapshot.get("last_success_at") or snapshot.get("updated_at") or snapshot.get("generated_at") or ""),
        last_error=str(snapshot.get("last_error") or snapshot.get("error") or ""),
        latency_ms=snapshot.get("latency_ms") if snapshot else 0,
        requires_user_action=bool(snapshot.get("requires_user_action", snapshot.get("manual", False)))
        if isinstance(snapshot, dict)
        else None,
        used_in_decision=bool(snapshot.get("used_in_decision", False)) if isinstance(snapshot, dict) else None,
    )


def apply_tushare_health(registry: dict[str, Any], health_result: dict[str, Any] | None) -> dict[str, Any]:
    if not health_result:
        return registry

    tushare_packet = health_result.get("tushare") or {}
    if not isinstance(tushare_packet, dict):
        return registry
    items = tushare_packet.get("items") or []
    updated = registry

    # 将同类指标收敛到一个总项
    grouped = {
        "Tushare 日线/行情": ["daily", "daily_basic"],
        "Tushare 个股资金流": ["moneyflow"],
        "Tushare 融资融券": ["margin_detail"],
        "Tushare 龙虎榜": ["top_list", "top_inst"],
        "Tushare ETF": ["etf_basic", "get_etf_basic", "etf_index", "get_etf_index"],
        "Tushare 公告": ["anns_d", "announcements"],
        "Tushare 涨跌停": ["stk_limit", "limit_list_d", "limit_cpt_list"],
        "Tushare 指数成分/权重": ["index_weight", "index_member"],
        "Tushare 筹码/胜率": ["cyq_perf", "cyq_chips"],
    }

    latest = {}
    for row in items:
        if not isinstance(row, dict):
            continue
        api = str(row.get("api") or "").strip()
        row_status = _infer_single_item_status(row)
        last_success = str(row.get("latest_date") or row.get("updated_at") or row.get("checked_at") or "")
        row_error = str(row.get("error") or "")
        for name, api_list in grouped.items():
            if api in api_list:
                current = latest.setdefault(name, (STATUS_UNKNOWN, "", ""))
                if row_status == STATUS_AVAILABLE:
                    latest[name] = (row_status, last_success, "")
                else:
                    latest[name] = (
                        STATUS_SKIPPED if current[0] == STATUS_AVAILABLE else row_status,
                        current[1] if current[1] else last_success,
                        current[2] or row_error,
                    )

    for name, (status, last_success_at, last_error) in latest.items():
        updated = update_capability_status(
            updated,
            name,
            status,
            last_success_at=last_success_at,
            last_error=last_error,
            provider="Tushare",
            api=grouped.get(name, [""])[0],
        )
    return updated


def apply_supabase_health(registry: dict[str, Any], health_result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(health_result, dict):
        return registry
    supabase_packet = health_result.get("supabase") or {}
    items = supabase_packet.get("items") or []
    if not items:
        return update_capability_status(
            registry,
            "Supabase 记忆",
            STATUS_FAILED,
            last_success_at="",
            last_error="Supabase 健康数据缺失",
        )

    status_by_api = {}
    for row in items:
        if not isinstance(row, dict):
            continue
        api = str(row.get("table") or row.get("api") or "").strip()
        inferred = _infer_single_item_status(row, default_status=STATUS_AVAILABLE)
        status_by_api[api] = {
            "status": inferred,
            "last_success_at": str(row.get("updated_at") or row.get("checked_at") or ""),
            "last_error": str(row.get("error") or ""),
            "latency_ms": int(row.get("latency_ms") or 0),
        }

    for api, fields in status_by_api.items():
        key = {
            "brain_memory": "Supabase 记忆",
            "market_news": "Supabase 投喂",
            "processed_sources": "Supabase 投喂",
            "trade_history": "Supabase 历史记录",
            "backtest_cache": "Supabase 回测缓存",
        }.get(api, "")
        if not key:
            continue
        updated = update_capability_status(
            registry,
            key,
            fields.get("status", STATUS_UNKNOWN),
            last_success_at=fields["last_success_at"],
            last_error=fields["last_error"],
            latency_ms=fields["latency_ms"],
            provider="Supabase",
            api=api,
        )
        registry = updated
    return registry


def apply_deepseek_status(registry: dict[str, Any], is_configured: bool, key_count: int = 0) -> dict[str, Any]:
    if is_configured:
        return update_capability_status(
            registry,
            "DeepSeek 解释",
            STATUS_AVAILABLE,
            last_success_at=now_iso(),
            last_error="",
        )
    return update_capability_status(
        registry,
        "DeepSeek 解释",
        STATUS_NO_PERMISSION,
        last_error=f"DeepSeek 未配置或 key 为空（key_count={key_count}）",
    )


def apply_yfinance_quote(registry: dict[str, Any], quote_snapshot: dict[str, Any] | None, market_type: str = "") -> dict[str, Any]:
    if not isinstance(quote_snapshot, dict):
        return registry

    source = str(quote_snapshot.get("raw_source") or "").lower()
    has_price = quote_snapshot.get("price") not in (None, "")
    if market_type and not str(market_type).startswith("A_SHARE") and not has_price:
        return update_capability_status(
            registry,
            "yfinance 行情",
            STATUS_FAILED,
            last_error="yfinance 未返回可用价格",
        )

    if has_price and source:
        return update_capability_status(
            registry,
            "yfinance 行情",
            STATUS_AVAILABLE,
            last_success_at=str(quote_snapshot.get("data_date") or now_iso()),
            last_error="",
        )

    return update_capability_status(
        registry,
        "yfinance 行情",
        STATUS_FAILED,
        last_error=str(quote_snapshot.get("warning") or "yfinance 响应空数据"),
    )


def apply_akshare_snapshot(registry: dict[str, Any], flow_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(flow_snapshot, dict):
        return update_capability_status(
            registry,
            "AkShare 个股资金",
            STATUS_SKIPPED,
            last_error="AkShare 未触发本次探测",
        )

    source_status = flow_snapshot.get("source_status") or {}
    if not isinstance(source_status, dict):
        source_status = {}

    # 个股资金：首选 primary source 返回状态
    primary = source_status.get("individual_fund_flow_primary") or {}
    fallback = source_status.get("individual_fund_flow_fallback") or {}

    used_primary = bool(primary.get("used"))
    error = primary.get("error") or fallback.get("error") or ""
    if primary.get("ok") is True or fallback.get("ok") is True:
        status = STATUS_AVAILABLE
        last_error = ""
        at = now_iso()
    elif any(
        (
            str(primary.get("error", "")).strip(),
            str(fallback.get("error", "")).strip(),
        )
    ):
        if "permission" in str(error).lower():
            status = STATUS_NO_PERMISSION
        else:
            status = STATUS_FAILED
        last_error = str(error)
        at = now_iso()
    elif used_primary:
        status = STATUS_SKIPPED if flow_snapshot.get("mode") == "quick" else STATUS_FAILED
        at = now_iso()
        last_error = str(flow_snapshot.get("warnings")[-1]) if flow_snapshot.get("warnings") else ""
    else:
        status = STATUS_SKIPPED
        at = ""
        last_error = str(flow_snapshot.get("warnings")[-1]) if flow_snapshot.get("warnings") else ""

    updated = update_capability_status(
        registry,
        "AkShare 个股资金",
        status,
        last_success_at=at,
        last_error=last_error,
        latency_ms=0,
    )

    concept_status = STATUS_AVAILABLE if flow_snapshot.get("concepts") else status
    updated = update_capability_status(
        updated,
        "AkShare 概念",
        STATUS_AVAILABLE if concept_status == STATUS_AVAILABLE and status != STATUS_NO_PERMISSION else (STATUS_FAILED if status == STATUS_FAILED else STATUS_SKIPPED),
        last_success_at=at,
        last_error="无统一概念数据面接口，缺省按资金能力状态映射" if concept_status != STATUS_AVAILABLE else "",
    )

    industry_status = STATUS_AVAILABLE if flow_snapshot.get("industries") else status
    updated = update_capability_status(
        updated,
        "AkShare 行业",
        STATUS_AVAILABLE if industry_status == STATUS_AVAILABLE and status != STATUS_NO_PERMISSION else (STATUS_FAILED if status == STATUS_FAILED else STATUS_SKIPPED),
        last_success_at=at,
        last_error="无统一行业数据面接口，缺省按资金能力状态映射" if industry_status != STATUS_AVAILABLE else "",
    )
    board_status = STATUS_AVAILABLE if flow_snapshot.get("realtime_board") or flow_snapshot.get("quote_board") else status
    updated = update_capability_status(
        updated,
        "AkShare 盘口/补充数据",
        STATUS_AVAILABLE if board_status == STATUS_AVAILABLE and status != STATUS_NO_PERMISSION else (STATUS_FAILED if status == STATUS_FAILED else STATUS_SKIPPED),
        last_success_at=at,
        last_error="AkShare 盘口/补充数据未触发或无统一返回" if board_status != STATUS_AVAILABLE else "",
    )
    return updated


def apply_home_snapshot_status(
    registry: dict[str, Any],
    snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return update_capability_status(
            registry,
            "Home Snapshot",
            STATUS_UNKNOWN,
            last_error="本地快照未初始化",
        )

    freshness = snapshot.get("data_freshness") or {}
    state = str(freshness.get("state") or "missing")
    if state == "today":
        status = STATUS_AVAILABLE
    elif state in {"recent", "stale", "partial_failed"}:
        status = STATUS_CACHED
    elif state in {"missing", "empty", "error"}:
        status = STATUS_FAILED
    else:
        status = STATUS_UNKNOWN

    return update_capability_status(
        registry,
        "Home Snapshot",
        status,
        last_success_at=str(snapshot.get("generated_at") or snapshot.get("checked_at") or snapshot.get("updated_at") or ""),
        last_error=str(freshness.get("message") or snapshot.get("last_error") or ""),
    )


def apply_basic_refresh_capability_probe(
    registry: dict[str, Any],
    health_result: dict[str, Any] | None,
    yfinance_snapshot: dict[str, Any] | None,
    akshare_snapshot: dict[str, Any] | None,
    supabase_result: dict[str, Any] | None,
    deepseek_configured: bool,
    deepseek_key_count: int,
    home_snapshot: dict[str, Any] | None,
    market_type: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one-button status results and return (registry, packet)."""

    updated = build_initial_capability_registry(
        target=registry.get("target") or "",
        market_type=market_type,
        checked_at=now_iso(),
    )
    updated = apply_tushare_health(updated, health_result)
    updated = apply_yfinance_quote(updated, yfinance_snapshot, market_type=market_type)
    updated = apply_supabase_health(updated, supabase_result)
    updated = apply_deepseek_status(updated, deepseek_configured, deepseek_key_count)
    updated = apply_akshare_snapshot(updated, akshare_snapshot)
    updated = apply_home_snapshot_status(updated, home_snapshot)
    return updated, build_data_capability_packet(updated)


def diagnose_capability(registry: dict[str, Any], name: str, probe: Any) -> dict[str, Any]:
    """Button-gated ability probe adapter.

    这里不直接调用外部接口，按入参 probe 执行状态归类并回写。
    """

    try:
        snapshot = probe() if callable(probe) else (probe or {})
    except Exception as exc:
        return update_capability_status(
            registry,
            name,
            STATUS_FAILED,
            last_error=str(exc),
        )
    return update_from_snapshot(registry, name, snapshot)
