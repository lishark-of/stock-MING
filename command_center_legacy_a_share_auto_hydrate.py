from __future__ import annotations

import datetime as _dt
import time
from collections.abc import Mapping, MutableMapping
from typing import Any, Callable

import market_data_capability as data_capability


FINGERPRINT_KEY = "legacy_auto_hydrate_fingerprint"
LAST_AT_KEY = "legacy_auto_hydrate_last_at"
TTL_KEY = "legacy_auto_hydrate_ttl_seconds"
STATUS_KEY = "legacy_auto_hydrate_status"
FACT_PACKET_KEY = "legacy_a_share_fact_packet"
DEFAULT_TTL_SECONDS = 600

MODULE_ORDER = (
    "moneyflow",
    "dragon_tiger",
    "margin",
    "limit_emotion",
    "chip_radar",
    "hard_risk",
)

LEGACY_PACKET_KEYS = {
    "moneyflow": "legacy_moneyflow_packet",
    "dragon_tiger": "legacy_dragon_tiger_packet",
    "margin": "legacy_margin_packet",
    "limit_emotion": "legacy_limit_emotion_packet",
    "chip_radar": "legacy_chip_packet",
    "hard_risk": "legacy_hard_risk_packet",
}

COMMAND_CENTER_PACKET_KEYS = {
    "moneyflow": "command_center_moneyflow_packet",
    "dragon_tiger": "command_center_dragon_tiger_packet",
    "margin": "command_center_margin_packet",
    "limit_emotion": "command_center_limit_emotion_packet",
    "chip_radar": "command_center_chip_packet",
    "hard_risk": "command_center_hard_risk_packet",
}

MODULE_LABELS = {
    "moneyflow": "资金流",
    "dragon_tiger": "龙虎榜",
    "margin": "融资融券",
    "limit_emotion": "涨跌停/情绪",
    "chip_radar": "筹码/胜率",
    "hard_risk": "公告/硬风险",
}

STATUS_LABELS = {
    "available": "已刷新",
    "failed": "失败",
    "no_permission": "权限不足",
    "no_data": "无数据",
    "cached": "使用缓存",
    "skipped": "本轮跳过",
    "unknown": "待验证",
}

RUNTIME_SECRET_MISSING_HINT = "运行时未注入配置"
RUNTIME_SECRET_MISSING_TEXT = (
    "当前页面进程没有拿到 Tushare 运行时配置；Streamlit Cloud 请到 App settings → Secrets 添加 "
    "TUSHARE_TOKEN，本地桌面请用 .streamlit/secrets.toml 或环境变量注入。"
)

SUMMARY_STATUSES = tuple(STATUS_LABELS)
NOISY_DETAIL_TERMS = (
    "风险路径",
    "回流路径",
    "恢复路径",
    "决策影响",
    "provider",
    "packet",
    "入口",
)


def _state_get(state: Mapping[str, Any] | MutableMapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return state.get(key, default)
    except Exception:
        return default


def _state_set(state: MutableMapping[str, Any], key: str, value: Any) -> None:
    state[key] = value


def _as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _module_sort_key(module_key: str) -> tuple[int, str]:
    try:
        return MODULE_ORDER.index(module_key), module_key
    except ValueError:
        return len(MODULE_ORDER), module_key


def normalize_modules(modules: Any = None) -> list[str]:
    if not modules:
        return list(MODULE_ORDER)
    cleaned = []
    for module in modules:
        key = str(module or "").strip()
        if key and key not in cleaned:
            cleaned.append(key)
    return sorted(cleaned, key=_module_sort_key)


def build_fingerprint(
    *,
    target: Any = "",
    market_type: Any = "",
    modules: Any = None,
    trade_date: Any = None,
    scope: str = "legacy_a_share_diagnostic_v1",
) -> str:
    module_text = ",".join(normalize_modules(modules))
    date_text = str(trade_date or _dt.date.today().isoformat())
    return "|".join(
        [
            scope,
            str(target or "").strip().upper(),
            str(market_type or "A股").strip() or "A股",
            date_text,
            module_text,
        ]
    )


def should_hydrate(
    state: Mapping[str, Any],
    fingerprint: str,
    *,
    ttl_seconds: int | float | None = None,
    now_ts: int | float | None = None,
    force: bool = False,
) -> dict:
    now_value = float(now_ts if now_ts is not None else time.time())
    ttl = int(ttl_seconds or _state_get(state, TTL_KEY, DEFAULT_TTL_SECONDS) or DEFAULT_TTL_SECONDS)
    last_fingerprint = str(_state_get(state, FINGERPRINT_KEY, "") or "")
    last_at = _state_get(state, LAST_AT_KEY)
    try:
        last_at_value = float(last_at)
    except Exception:
        last_at_value = 0.0
    elapsed = now_value - last_at_value if last_at_value else None
    if force:
        return {"should_hydrate": True, "reason": "force_refresh", "ttl_seconds": ttl, "elapsed_seconds": elapsed}
    if not last_fingerprint:
        return {"should_hydrate": True, "reason": "initial", "ttl_seconds": ttl, "elapsed_seconds": elapsed}
    if last_fingerprint != fingerprint:
        return {"should_hydrate": True, "reason": "fingerprint_changed", "ttl_seconds": ttl, "elapsed_seconds": elapsed}
    if not last_at_value:
        return {"should_hydrate": True, "reason": "missing_last_refresh", "ttl_seconds": ttl, "elapsed_seconds": elapsed}
    if elapsed is not None and elapsed >= ttl:
        return {"should_hydrate": True, "reason": "ttl_expired", "ttl_seconds": ttl, "elapsed_seconds": elapsed}
    remaining = max(0, ttl - int(elapsed or 0))
    return {
        "should_hydrate": False,
        "reason": "ttl_active",
        "ttl_seconds": ttl,
        "elapsed_seconds": elapsed,
        "remaining_seconds": remaining,
    }


def normalize_status(value: Any = "", packet: Any = None, *, has_error: bool = False) -> str:
    packet_payload = _as_mapping(packet)
    raw = value
    if raw in [None, ""]:
        raw = (
            packet_payload.get("capability_state")
            or packet_payload.get("state")
            or packet_payload.get("data_status")
            or packet_payload.get("status")
        )
    normalized = data_capability.normalize_capability_state_value(raw)
    if normalized == data_capability.STATE_AVAILABLE:
        return "available"
    if normalized in {data_capability.STATE_STALE_CACHE, data_capability.STATE_FALLBACK_USED}:
        return "cached"
    if normalized in {data_capability.STATE_PERMISSION_DENIED, data_capability.STATE_NOT_CONFIGURED}:
        return "no_permission"
    if normalized == data_capability.STATE_EMPTY_RECENT:
        return "no_data"
    if normalized == data_capability.STATE_DISABLED_THIS_SESSION:
        return "skipped"
    if normalized in {data_capability.STATE_NETWORK_FAILED, data_capability.STATE_FAILED}:
        return "failed"
    if normalized == data_capability.STATE_REQUIRES_MANUAL_REFRESH:
        return "no_data"
    if has_error:
        return "failed"
    data_status = str(packet_payload.get("data_status") or packet_payload.get("status") or "").strip().lower()
    if data_status in {"ready", "ok", "success", "available", "已刷新", "可用"}:
        return "available"
    if data_status in {"cached", "stale", "partial", "using_cache", "使用缓存"}:
        return "cached"
    if data_status in {"permission_denied", "no_permission", "not_configured", "权限不足"}:
        return "no_permission"
    if data_status in {"missing", "waiting", "pending", "empty", "no_data", "no_recent_data", "待刷新", "待验证"}:
        return "no_data"
    if data_status in {"failed", "error", "blocked", "network_failed", "失败"}:
        return "failed"
    return "unknown"


def _packet_has_cache(packet: Any = None) -> bool:
    status = normalize_status(packet=packet)
    payload = _as_mapping(packet)
    return bool(payload) and status in {"available", "cached", "no_data"}


def is_runtime_secret_missing_message(value: Any = "") -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return data_capability.is_not_configured_error(text)


def _result_item(result: Any = None) -> dict:
    payload = _as_mapping(result)
    item = _as_mapping(payload.get("item"))
    if item:
        return item
    if payload.get("error"):
        return {
            "capability_state": data_capability.STATE_FAILED,
            "error": str(payload.get("error") or ""),
            "deepseek_called": False,
        }
    return {}


def build_module_status(
    spec: Mapping[str, Any],
    *,
    result: Any = None,
    previous_packet: Any = None,
    current_packet: Any = None,
    updated_at: str = "",
) -> dict:
    key = str(spec.get("key") or "")
    label = str(spec.get("label") or MODULE_LABELS.get(key) or key or "A股数据")
    item = _result_item(result)
    result_payload = _as_mapping(result)
    error = _text(
        result_payload.get("error")
        or item.get("error")
        or item.get("warning")
        or item.get("message")
    )
    runtime_secret_missing = is_runtime_secret_missing_message(error)
    status = normalize_status(
        item.get("capability_state") or item.get("state") or item.get("status"),
        current_packet or previous_packet,
        has_error=bool(error),
    )
    if runtime_secret_missing:
        status = "skipped"
    cache_available = _packet_has_cache(previous_packet) and status == "failed"
    status_label = RUNTIME_SECRET_MISSING_HINT if runtime_secret_missing else STATUS_LABELS.get(status, STATUS_LABELS["unknown"])
    source = _text(
        spec.get("source")
        or item.get("source")
        or item.get("provider")
        or "Tushare",
        "Tushare",
    )
    module_updated_at = _text(
        item.get("checked_at")
        or item.get("updated_at")
        or _as_mapping(current_packet).get("updated_at")
        or _as_mapping(previous_packet).get("updated_at")
        or updated_at
    )
    if status == "available":
        conclusion = _text(item.get("action_hint") or item.get("message"), f"{label}已取得可用返回，可进入旧版工作台证据链。")
    elif status == "cached":
        conclusion = _text(item.get("action_hint") or item.get("message"), f"{label}正在使用缓存，执行前复核交易日和来源。")
    elif status == "no_permission":
        conclusion = _text(error or item.get("action_hint"), f"{label}权限不足或未配置，不能当作无风险。")
    elif status == "no_data":
        conclusion = _text(error or item.get("action_hint"), f"{label}近期无数据或仍待发布，先按缺口处理。")
    elif status == "skipped":
        if runtime_secret_missing:
            conclusion = f"{RUNTIME_SECRET_MISSING_HINT}：{RUNTIME_SECRET_MISSING_TEXT}"
        else:
            conclusion = _text(error or item.get("action_hint"), f"{label}本轮跳过，避免重复请求。")
    elif cache_available:
        conclusion = f"本次检测失败，保留上次缓存：{error or '未知错误'}"
    elif status == "failed":
        conclusion = _text(error or item.get("action_hint"), f"{label}检测失败，页面保留安全状态。")
    else:
        conclusion = _text(item.get("action_hint") or item.get("message"), f"{label}待验证。")
    return {
        "key": key,
        "label": label,
        "status": status,
        "status_label": status_label,
        "conclusion": conclusion,
        "updated_at": module_updated_at,
        "source": source,
        "api": _text(spec.get("api") or item.get("api")),
        "writes_packet": _text(spec.get("packet_key") or COMMAND_CENTER_PACKET_KEYS.get(key)),
        "legacy_packet_key": _text(spec.get("legacy_packet_key") or LEGACY_PACKET_KEYS.get(key)),
        "cache_available": cache_available,
        "error": error,
        "runtime_secret_missing": runtime_secret_missing,
        "deepseek_called": bool(result_payload.get("deepseek_called") or item.get("deepseek_called", False)),
    }


def summarize_modules(modules: Any = None) -> dict:
    items = [_as_mapping(item) for item in (modules or []) if _as_mapping(item)]
    counts = {status: 0 for status in SUMMARY_STATUSES}
    cache_count = 0
    latest_values = []
    sources = []
    for item in items:
        status = str(item.get("status") or "unknown")
        counts[status if status in counts else "unknown"] += 1
        if item.get("cache_available") or status == "cached":
            cache_count += 1
        if item.get("updated_at"):
            latest_values.append(str(item.get("updated_at")))
        if item.get("source"):
            sources.append(str(item.get("source")))
    return {
        "total": len(items),
        "available": counts["available"],
        "failed": counts["failed"],
        "no_permission": counts["no_permission"],
        "no_data": counts["no_data"],
        "cached": cache_count,
        "skipped": counts["skipped"],
        "unknown": counts["unknown"],
        "pending": counts["no_data"] + counts["unknown"],
        "last_updated_at": sorted(latest_values, reverse=True)[0] if latest_values else "",
        "sources": list(dict.fromkeys(sources)),
    }


def build_status_packet(
    *,
    target: Any = "",
    market_type: Any = "",
    modules: Any = None,
    fingerprint: str = "",
    decision: Any = None,
    hydrated: bool = False,
    forced: bool = False,
    updated_at: str = "",
) -> dict:
    module_items = [_as_mapping(item) for item in (modules or []) if _as_mapping(item)]
    summary = summarize_modules(module_items)
    packet = {
        "target": str(target or ""),
        "market_type": str(market_type or "A股"),
        "fingerprint": fingerprint,
        "hydrated": bool(hydrated),
        "forced": bool(forced),
        "skipped_by_ttl": not bool(hydrated),
        "decision": _as_mapping(decision),
        "modules": module_items,
        "summary": summary,
        "updated_at": updated_at or summary.get("last_updated_at") or "",
        "deepseek_called": any(bool(item.get("deepseek_called")) for item in module_items),
    }
    packet["summary_text"] = build_main_summary_text(packet)
    return packet


def build_main_summary_text(packet: Any = None) -> str:
    payload = _as_mapping(packet)
    summary = _as_mapping(payload.get("summary"))
    target = _text(payload.get("target"), "当前标的")
    return (
        f"A股专业数据：已刷新 {summary.get('available', 0)} / "
        f"缓存 {summary.get('cached', 0)} / "
        f"权限不足 {summary.get('no_permission', 0)} / "
        f"失败 {summary.get('failed', 0)} / "
        f"跳过 {summary.get('skipped', 0)} / "
        f"待验证 {summary.get('pending', 0)}｜"
        f"当前标的 {target}｜"
        f"最近刷新 {summary.get('last_updated_at') or payload.get('updated_at') or '暂无'}"
    )


def execute_auto_hydrate(
    state: MutableMapping[str, Any],
    *,
    target: Any = "",
    market_type: Any = "A股",
    module_specs: Any = None,
    handlers: Mapping[str, Callable[..., Any]] | None = None,
    module_keys: Any = None,
    fingerprint_modules: Any = None,
    ttl_seconds: int | float | None = None,
    now_ts: int | float | None = None,
    now_text: str = "",
    trade_date: Any = None,
    force: bool = False,
    position_profile: Any = None,
    live_packet: Any = None,
) -> dict:
    specs = [_as_mapping(spec) for spec in (module_specs or []) if _as_mapping(spec)]
    selected = set(normalize_modules(module_keys)) if module_keys else {str(spec.get("key") or "") for spec in specs}
    run_specs = [spec for spec in specs if str(spec.get("key") or "") in selected]
    fingerprint_source = fingerprint_modules if fingerprint_modules is not None else [spec.get("key") for spec in specs]
    fingerprint = build_fingerprint(
        target=target,
        market_type=market_type,
        modules=fingerprint_source,
        trade_date=trade_date,
    )
    ttl = int(ttl_seconds or _state_get(state, TTL_KEY, DEFAULT_TTL_SECONDS) or DEFAULT_TTL_SECONDS)
    _state_set(state, TTL_KEY, ttl)
    decision = should_hydrate(
        state,
        fingerprint,
        ttl_seconds=ttl,
        now_ts=now_ts,
        force=force,
    )
    now_value = float(now_ts if now_ts is not None else time.time())
    stamp = now_text or _dt.datetime.now().isoformat(timespec="seconds")
    if not decision.get("should_hydrate"):
        previous = _as_mapping(_state_get(state, STATUS_KEY))
        if previous.get("modules"):
            packet = dict(previous)
            packet["decision"] = decision
            packet["hydrated"] = False
            packet["forced"] = False
            packet["skipped_by_ttl"] = True
            packet["summary_text"] = build_main_summary_text(packet)
        else:
            module_items = []
            for spec in run_specs:
                key = str(spec.get("key") or "")
                packet_key = str(spec.get("packet_key") or COMMAND_CENTER_PACKET_KEYS.get(key) or "")
                legacy_key = str(spec.get("legacy_packet_key") or LEGACY_PACKET_KEYS.get(key) or "")
                existing_packet = _state_get(state, packet_key) or _state_get(state, legacy_key)
                module_items.append(
                    build_module_status(
                        spec,
                        previous_packet=existing_packet,
                        current_packet=existing_packet,
                        updated_at=stamp,
                    )
                )
            packet = build_status_packet(
                target=target,
                market_type=market_type,
                modules=module_items,
                fingerprint=fingerprint,
                decision=decision,
                hydrated=False,
                updated_at=stamp,
            )
        _state_set(state, STATUS_KEY, packet)
        return packet

    handler_map = dict(handlers or {})
    module_items = []
    for spec in run_specs:
        key = str(spec.get("key") or "")
        packet_key = str(spec.get("packet_key") or COMMAND_CENTER_PACKET_KEYS.get(key) or "")
        legacy_key = str(spec.get("legacy_packet_key") or LEGACY_PACKET_KEYS.get(key) or "")
        previous_packet = _state_get(state, packet_key) or _state_get(state, legacy_key)
        handler = handler_map.get(key)
        try:
            if handler is None:
                result = {
                    "item": {
                        "capability_state": data_capability.STATE_DISABLED_THIS_SESSION,
                        "error": "未接入自动检测函数。",
                        "deepseek_called": False,
                    },
                    "deepseek_called": False,
                }
            else:
                result = handler(
                    target=target,
                    position_profile=position_profile,
                    live_packet=live_packet,
                )
        except Exception as exc:
            result = {
                "item": {
                    "capability_state": data_capability.STATE_FAILED,
                    "error": str(exc),
                    "deepseek_called": False,
                },
                "error": str(exc),
                "deepseek_called": False,
            }
        current_packet = _state_get(state, packet_key) or previous_packet
        if legacy_key and current_packet:
            _state_set(state, legacy_key, current_packet)
        if _as_mapping(result).get("professional_packet"):
            _state_set(state, FACT_PACKET_KEY, _as_mapping(result).get("professional_packet"))
        module_items.append(
            build_module_status(
                spec,
                result=result,
                previous_packet=previous_packet,
                current_packet=current_packet,
                updated_at=stamp,
            )
        )

    if module_keys:
        previous_status = _as_mapping(_state_get(state, STATUS_KEY))
        merged_by_key = {
            str(item.get("key") or ""): item
            for item in (previous_status.get("modules") or [])
            if _as_mapping(item)
        }
        for item in module_items:
            merged_by_key[str(item.get("key") or "")] = item
        ordered_keys = [str(spec.get("key") or "") for spec in specs]
        module_items = [merged_by_key[key] for key in ordered_keys if key in merged_by_key]

    packet = build_status_packet(
        target=target,
        market_type=market_type,
        modules=module_items,
        fingerprint=fingerprint,
        decision=decision,
        hydrated=True,
        forced=force,
        updated_at=stamp,
    )
    _state_set(state, FINGERPRINT_KEY, fingerprint)
    _state_set(state, LAST_AT_KEY, now_value)
    _state_set(state, STATUS_KEY, packet)
    return packet
