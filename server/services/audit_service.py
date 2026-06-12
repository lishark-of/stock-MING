from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Callable, Mapping
from typing import Any

from config import get_deepseek_model_strategy
from server.services import (
    candidate_service,
    data_capability_service,
    data_health_service,
    desktop_service,
    discipline_service,
    evidence_service,
    factor_service,
    legacy_service,
    market_service,
    migration_status_service,
    model_strategy_service,
    next_session_service,
    packet_service,
    position_service,
    quant_service,
    recovery_service,
    risk_service,
    storage_service,
    strategy_service,
    task_service,
    trade_review_service,
    worker_service,
)


PACKET_KEY = "command_center_3_call_ledger_audit_cache"
SCHEMA_VERSION = "call_ledger_audit_cache.v1"
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _is_sensitive_key(key: Any) -> bool:
    lower = str(key or "").lower()
    return any(part in lower for part in SENSITIVE_KEY_PARTS)


def _safe_text(value: Any, *, limit: int = 1000) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[truncated]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            _safe_text(key, limit=100): _safe_value(val, depth=depth + 1)
            for key, val in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:120]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:120]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "call_ledger_audit_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _bool(value: Any) -> bool:
    return bool(value)


def _health_check_packet() -> dict[str, Any]:
    checked_at = _now_iso()
    return {
        "packet_key": "command_center_3_health_check",
        "schema_version": "health_check.v1",
        "status": "ok",
        "mode": "cache_only",
        "cache_only": True,
        "service": "stock-MING Command Center 3.0",
        "legacy_streamlit": "retained_for_admin_debug",
        "external_calls_on_startup": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "real_trading_enabled": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "deepseek_model_strategy": get_deepseek_model_strategy(),
        "call_ledger": [
            {
                "api": "local_health_check",
                "source": "FastAPI health route and local config",
                "call_status": "cache_read",
                "local_fetched_at": checked_at,
                "external": False,
            }
        ],
        "warnings": [
            "GET /health 只读检查 FastAPI 启动状态和本地模型策略配置；不会调用 Tushare、DeepSeek 或 GitHub。",
            "健康检查不读取 token/key，不执行真实交易，不修改 strategy action。",
        ],
    }


def _cache_endpoint_specs() -> list[tuple[str, str, Callable[[], dict[str, Any]]]]:
    return [
        ("GET /health", "health", _health_check_packet),
        ("GET /api/packets", "packet_index", packet_service.list_packets),
        ("GET /api/migration/status", "migration_status", migration_status_service.build_migration_status),
        ("GET /api/model-strategy/cache", "model_strategy", model_strategy_service.read_deepseek_model_strategy_cache),
        ("GET /api/desktop/preflight-cache", "desktop_preflight", desktop_service.read_desktop_shell_preflight_cache),
        ("GET /api/worker/cache", "worker_runtime", worker_service.read_worker_runtime_cache),
        ("GET /api/tasks", "task_status_index", task_service.build_task_status_index),
        ("GET /api/tasks/catalog", "task_catalog", task_service.build_task_catalog),
        ("GET /api/market/cache", "market_context", market_service.read_market_context_cache),
        ("GET /api/discipline/cache", "discipline_loop", discipline_service.read_discipline_loop_cache),
        ("GET /api/evidence/cache", "a_share_evidence", evidence_service.read_a_share_evidence_cache),
        ("GET /api/data-capability/cache", "data_capability", data_capability_service.read_data_capability_cache),
        ("GET /api/data-health/cache", "data_health", data_health_service.read_data_health_timeline_cache),
        ("GET /api/recovery/cache", "recovery_center", recovery_service.read_recovery_center_cache),
        ("GET /api/next-session/cache", "next_session", next_session_service.read_next_session_cache),
        ("GET /api/factor-quant/cache", "factor_quant", factor_service.read_factor_quant_cache),
        ("GET /api/serenity/cache", "serenity", packet_service.build_serenity_cache),
        ("GET /api/chokepoint/cache", "chokepoint", packet_service.build_chokepoint_cache),
        ("GET /api/storage", "storage_overview", storage_service.storage_overview),
        ("GET /api/storage/catalog", "storage_dataset_catalog", storage_service.storage_dataset_catalog),
        ("GET /api/storage/factor-values", "storage_factor_values", storage_service.factor_values_status),
        ("GET /api/storage/sqlite-meta", "storage_sqlite_meta", storage_service.sqlite_meta_status),
        ("GET /api/strategy/cache", "strategy_trace", strategy_service.read_strategy_trace_cache),
        ("GET /api/position/cache", "position_context", position_service.read_position_context_cache),
        ("GET /api/candidate-radar/cache", "candidate_radar", candidate_service.read_candidate_radar_cache),
        ("GET /api/risk/cache", "risk_guardrails", risk_service.read_risk_guardrails_cache),
        ("GET /api/trade-review/cache", "trade_review", trade_review_service.read_trade_review_cache),
        ("GET /api/quant/cache", "quant_backtest", quant_service.read_quant_backtest_cache),
        ("GET /api/legacy/cache", "legacy_bridge", legacy_service.read_legacy_bridge_cache),
    ]


def _parameterized_get_route_specs() -> list[dict[str, Any]]:
    return [
        {
            "route": "GET /api/audit/cache",
            "source": "call_ledger_audit_self",
            "route_type": "self_audit_local_detail",
            "cache_only": True,
            "external_calls_triggered": False,
            "requires_runtime_parameter": False,
            "not_invoked_by_audit_reader": True,
        },
        {
            "route": "GET /api/packets/{packet_key}",
            "source": "packet_detail",
            "route_type": "parameterized_local_detail",
            "cache_only": True,
            "external_calls_triggered": False,
            "requires_runtime_parameter": True,
        },
        {
            "route": "GET /api/storage/{dataset}",
            "source": "storage_dataset",
            "route_type": "parameterized_local_detail",
            "cache_only": True,
            "external_calls_triggered": False,
            "requires_runtime_parameter": True,
        },
        {
            "route": "GET /api/tasks/{task_id}",
            "source": "task_detail",
            "route_type": "parameterized_local_detail",
            "cache_only": True,
            "external_calls_triggered": False,
            "requires_runtime_parameter": True,
        },
        {
            "route": "GET /api/tasks/{task_id}/logs",
            "source": "task_log_detail",
            "route_type": "parameterized_local_detail",
            "cache_only": True,
            "external_calls_triggered": False,
            "requires_runtime_parameter": True,
        },
    ]


def _get_route_coverage(endpoint_rows: list[dict[str, Any]]) -> dict[str, Any]:
    audited_routes = [str(row.get("endpoint") or "") for row in endpoint_rows]
    parameterized_routes = [row["route"] for row in _parameterized_get_route_specs()]
    known_get_routes = audited_routes + parameterized_routes
    return {
        "status": "ready",
        "scope": "command_center_3_cache_get_routes",
        "audited_cache_route_count": len(audited_routes),
        "parameterized_local_route_count": len(parameterized_routes),
        "known_get_route_count": len(known_get_routes),
        "audited_cache_routes": audited_routes,
        "parameterized_local_routes": _parameterized_get_route_specs(),
        "known_get_routes": known_get_routes,
        "uncovered_get_routes": [],
        "cache_routes_create_no_tasks": True,
        "all_known_get_routes_cache_only": True,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _packet_flags(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "external_calls_triggered": _bool(packet.get("external_calls_triggered") or packet.get("cache_api_external_calls_triggered")),
        "tushare_called": _bool(packet.get("tushare_called") or packet.get("cache_api_tushare_called")),
        "deepseek_called": _bool(packet.get("deepseek_called") or packet.get("cache_api_deepseek_called")),
        "github_called": _bool(packet.get("github_called") or packet.get("cache_api_github_called")),
        "does_not_execute_trades": packet.get("does_not_execute_trades", True) is not False,
        "does_not_modify_strategy_action": packet.get("does_not_modify_strategy_action", True) is not False,
    }


def _endpoint_audit_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    endpoint_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    for endpoint, source, reader in _cache_endpoint_specs():
        try:
            raw_packet = reader()
            packet = _safe_value(raw_packet)
            packet = packet if isinstance(packet, dict) else {"value": packet}
            flags = _packet_flags(packet)
            call_ledger = _as_list(packet.get("call_ledger"))
            endpoint_rows.append(
                {
                    "endpoint": endpoint,
                    "source": source,
                    "packet_key": packet.get("packet_key"),
                    "status": packet.get("status"),
                    "mode": packet.get("mode"),
                    "call_ledger_count": len(call_ledger),
                    **flags,
                    "read_status": "cache_read",
                }
            )
            for idx, item in enumerate(call_ledger, start=1):
                row = _as_dict(item)
                row.setdefault("source_endpoint", endpoint)
                row.setdefault("source", source)
                row.setdefault("index", idx)
                ledger_rows.append(row)
        except Exception as exc:
            endpoint_rows.append(
                {
                    "endpoint": endpoint,
                    "source": source,
                    "read_status": "failed",
                    "error_message_safe": _safe_text(exc),
                    "external_calls_triggered": False,
                    "tushare_called": False,
                    "deepseek_called": False,
                    "github_called": False,
                    "does_not_execute_trades": True,
                    "does_not_modify_strategy_action": True,
                    "call_ledger_count": 0,
                }
            )
    return endpoint_rows, ledger_rows


def _task_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task_rows: list[dict[str, Any]] = []
    task_ledger_rows: list[dict[str, Any]] = []
    for task in task_service.list_task_statuses():
        safe_task = _safe_value(task)
        task_map = safe_task if isinstance(safe_task, dict) else {}
        ledger = _as_list(task_map.get("call_ledger"))
        task_rows.append(
            {
                "task_id": task_map.get("task_id"),
                "task_type": task_map.get("task_type"),
                "status": task_map.get("status"),
                "progress": task_map.get("progress"),
                "current_step": task_map.get("current_step"),
                "backend": task_map.get("backend"),
                "storage_source": task_map.get("storage_source"),
                "output_packet_key": task_map.get("output_packet_key"),
                "call_ledger_count": len(ledger),
                "external_calls_triggered": _bool(task_map.get("external_calls_triggered")),
                "tushare_called": _bool(task_map.get("tushare_called")),
                "deepseek_called": _bool(task_map.get("deepseek_called")),
                "github_called": _bool(task_map.get("github_called")),
                "does_not_execute_trades": task_map.get("does_not_execute_trades", True) is not False,
                "does_not_modify_strategy_action": task_map.get("does_not_modify_strategy_action", True) is not False,
            }
        )
        for idx, item in enumerate(ledger, start=1):
            row = _as_dict(item)
            row.setdefault("source_task_id", task_map.get("task_id"))
            row.setdefault("source_task_type", task_map.get("task_type"))
            row.setdefault("index", idx)
            task_ledger_rows.append(row)
    return task_rows, task_ledger_rows


def _model_strategy_rows() -> list[dict[str, Any]]:
    packet = model_strategy_service.read_deepseek_model_strategy_cache()
    rows = []
    for row in _as_list(packet.get("model_rows")):
        item = _as_dict(_safe_value(row))
        rows.append(
            {
                "purpose": item.get("purpose"),
                "model": item.get("model"),
                "config_keys": item.get("config_keys"),
                "active_config_key": item.get("active_config_key"),
                "does_not_hardcode_model": item.get("does_not_hardcode_model") is True,
                "contains_secret": item.get("contains_secret") is True,
                "external_call_on_cache_read": item.get("external_call_on_cache_read") is True,
                "call_policy": item.get("call_policy"),
            }
        )
    return rows


def read_call_ledger_audit_cache() -> dict[str, Any]:
    endpoint_rows, endpoint_ledger_rows = _endpoint_audit_rows()
    task_rows, task_ledger_rows = _task_rows()
    task_catalog = _safe_value(task_service.build_task_catalog())
    task_catalog = task_catalog if isinstance(task_catalog, dict) else {}
    task_implementation_status = _as_dict(task_catalog.get("implementation_status"))
    task_status_index = _safe_value(task_service.build_task_status_index())
    task_status_index = task_status_index if isinstance(task_status_index, dict) else {}
    task_persistence = _as_dict(task_status_index.get("persistence"))
    task_persistence_source_rows = _as_list(task_status_index.get("persistence_source_rows"))
    model_strategy_rows = _model_strategy_rows()
    get_route_coverage = _get_route_coverage(endpoint_rows)
    all_ledger_rows = (endpoint_ledger_rows + task_ledger_rows)[:240]
    external_rows = [row for row in endpoint_rows + task_rows if row.get("external_calls_triggered")]
    action_risk_rows = [
        row
        for row in endpoint_rows + task_rows
        if row.get("does_not_execute_trades") is False or row.get("does_not_modify_strategy_action") is False
    ]
    missing_ledger_rows = [row for row in endpoint_rows + task_rows if int(row.get("call_ledger_count") or 0) == 0]
    status = "ready" if endpoint_rows else "cache_missing"

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "summary": "调用审计 cache 只读聚合本地 cache API 与任务 call_ledger；页面打开不会触发任何外部请求。",
        "endpoint_rows": endpoint_rows,
        "task_rows": task_rows,
        "get_route_coverage": get_route_coverage,
        "call_ledger_rows": all_ledger_rows,
        "endpoint_call_ledger_rows": endpoint_ledger_rows[:160],
        "task_call_ledger_rows": task_ledger_rows[:160],
        "task_implementation_status": task_implementation_status,
        "task_persistence": task_persistence,
        "task_persistence_source_rows": task_persistence_source_rows,
        "model_strategy_rows": model_strategy_rows,
        "external_call_rows": external_rows,
        "action_risk_rows": action_risk_rows,
        "missing_call_ledger_rows": missing_ledger_rows,
        "counts": {
            "cache_endpoint_count": len(endpoint_rows),
            "known_get_route_count": get_route_coverage["known_get_route_count"],
            "audited_cache_route_count": get_route_coverage["audited_cache_route_count"],
            "uncovered_get_route_count": len(get_route_coverage["uncovered_get_routes"]),
            "task_count": len(task_rows),
            "call_ledger_count": len(all_ledger_rows),
            "endpoint_call_ledger_count": len(endpoint_ledger_rows),
            "task_call_ledger_count": len(task_ledger_rows),
            "stub_task_count": task_implementation_status.get("stub_task_count", 0),
            "local_pipeline_task_count": task_implementation_status.get("local_pipeline_task_count", 0),
            "guarded_local_task_count": task_implementation_status.get("guarded_local_task_count", 0),
            "implemented_local_task_count": task_implementation_status.get("implemented_local_task_count", 0),
            "external_capable_task_count": task_implementation_status.get("external_capable_task_count", 0),
            "memory_task_count": task_persistence.get("memory_task_count", 0),
            "sqlite_task_count": task_persistence.get("sqlite_task_count", 0),
            "deduplicated_task_count": task_persistence.get("deduplicated_task_count", len(task_rows)),
            "model_strategy_purpose_count": len(model_strategy_rows),
            "model_strategy_cache_read_external_call_count": sum(
                1 for row in model_strategy_rows if row.get("external_call_on_cache_read")
            ),
            "external_call_count": len(external_rows),
            "action_risk_count": len(action_risk_rows),
            "missing_call_ledger_count": len(missing_ledger_rows),
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_ping_redis": True,
            "does_not_refresh_data": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "audit_is_read_only": True,
            "post_task_required_for_external_work": True,
            "reads_memory_and_sqlite_fallback": True,
            "task_implementation_status_is_read_only": True,
            "stub_tasks_must_not_be_reported_as_complete": True,
            "contains_secret": False,
        },
        "call_ledger": [
            {
                "api": "local_call_ledger_audit_cache",
                "source": "local cache API packets and task metadata",
                "row_count": len(all_ledger_rows),
                "endpoint_count": len(endpoint_rows),
                "known_get_route_count": get_route_coverage["known_get_route_count"],
                "task_count": len(task_rows),
                "memory_task_count": task_persistence.get("memory_task_count", 0),
                "sqlite_task_count": task_persistence.get("sqlite_task_count", 0),
                "deduplicated_task_count": task_persistence.get("deduplicated_task_count", len(task_rows)),
                "storage_backend": task_persistence.get("storage_backend", "memory_plus_sqlite_fallback"),
                "local_fetched_at": _now_iso(),
                "call_status": "cache_read",
                "external": False,
            }
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "redis_pinged": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/audit/cache 只读聚合本地 call_ledger；不会调用 Tushare、DeepSeek、GitHub 或 Redis。",
            "审计页只展示 cache/task 边界，不刷新数据、不运行回测、不执行真实交易、不修改 strategy action。",
            "发现 missing_call_ledger 只代表该本地 cache 返回包没有附带调用血缘，不代表自动外联。",
        ],
    }
    return _json_safe(packet)
