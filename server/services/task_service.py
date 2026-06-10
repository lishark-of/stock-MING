from __future__ import annotations

import datetime as _dt
import uuid
from pathlib import Path
from typing import Any

from config import DEEPSEEK_MODEL_CONFIG_KEYS
from storage.sqlite_meta import SQLiteMetaStore

from .model_strategy_service import build_deepseek_model_strategy_ref


_TASKS: dict[str, dict[str, Any]] = {}
TASK_STATUSES = {"pending", "running", "success", "failed", "cancelled"}
SECRET_KEYWORDS = ("token", "api_key", "secret", "password", "authorization", "bearer", "cookie")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
SQLITE_META_PATH = Path(__file__).resolve().parents[2] / ".stock_ming_3" / "meta.sqlite"

TASK_CATALOG = [
    {
        "task_type": "refresh_factor_data",
        "route": "POST /api/factor-quant/refresh-data",
        "label": "刷新因子数据",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_fallback_stub",
        "external_call_policy": "button_gated_tushare_capable",
        "possible_external_sources": ["tushare"],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_factor_light",
        "route": "POST /api/factor-quant/run-light",
        "label": "运行 light mode 因子计算",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "local_light_pipeline",
        "external_call_policy": "local_cache_only_current_mvp",
        "possible_external_sources": [],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_deepseek_factor_explanation",
        "route": "POST /api/factor-quant/deepseek-explain",
        "label": "DeepSeek 整理因子解释",
        "output_packet_key": "command_center_factor_quant_hub_packet",
        "button_gated": True,
        "current_backend": "guarded_prompt_or_payload_sanitizer",
        "external_call_policy": "manual_deepseek_capable_current_no_model_call",
        "possible_external_sources": ["deepseek"],
        "deepseek_model_strategy_purpose": "factor_explain",
        "deepseek_model_config_keys": list(DEEPSEEK_MODEL_CONFIG_KEYS["factor_explain"]),
        "deepseek_model_source": "config.get_deepseek_model('factor_explain')",
        "does_not_hardcode_deepseek_model": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "build_next_session_projection",
        "route": "POST /api/next-session/generate",
        "label": "生成次日操作图谱",
        "output_packet_key": "command_center_next_session_projection_packet",
        "button_gated": True,
        "current_backend": "local_cache_pipeline",
        "external_call_policy": "local_cache_only_current_mvp",
        "possible_external_sources": [],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "run_chokepoint_scan",
        "route": "POST /api/chokepoint/run",
        "label": "运行产业链瓶颈扫描",
        "output_packet_key": "command_center_chokepoint_scan_packet",
        "button_gated": True,
        "current_backend": "local_fallback_stub",
        "external_call_policy": "manual_deepseek_capable",
        "possible_external_sources": ["deepseek"],
        "deepseek_model_strategy_purpose": "explain",
        "deepseek_model_config_keys": list(DEEPSEEK_MODEL_CONFIG_KEYS["explain"]),
        "deepseek_model_source": "config.get_deepseek_model('explain')",
        "does_not_hardcode_deepseek_model": True,
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
    {
        "task_type": "probe_serenity_github",
        "route": "POST /api/serenity/github-probe",
        "label": "校验 Serenity GitHub 当前状态",
        "output_packet_key": "command_center_serenity_method_radar_packet",
        "button_gated": True,
        "current_backend": "local_fallback_stub",
        "external_call_policy": "manual_github_probe_capable",
        "possible_external_sources": ["github"],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    },
]

TASK_LIFECYCLE_POST_ROUTES = [
    {
        "route": "POST /api/tasks/{task_id}/cancel",
        "label": "取消本地任务",
        "route_type": "local_lifecycle",
        "button_gated": True,
        "current_backend": "local_status_update_only",
        "external_call_policy": "local_cancel_no_external_call",
        "possible_external_sources": [],
        "call_ledger_required": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
]


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _build_route_coverage() -> dict[str, Any]:
    task_routes = [str(item.get("route") or "") for item in TASK_CATALOG]
    lifecycle_routes = [str(item.get("route") or "") for item in TASK_LIFECYCLE_POST_ROUTES]
    known_post_routes = task_routes + lifecycle_routes
    return {
        "status": "ready",
        "scope": "command_center_3_button_gated_post_routes",
        "task_creation_route_count": len(task_routes),
        "local_lifecycle_route_count": len(lifecycle_routes),
        "known_post_route_count": len(known_post_routes),
        "task_creation_routes": task_routes,
        "local_lifecycle_routes": lifecycle_routes,
        "known_post_routes": known_post_routes,
        "uncovered_post_routes": [],
        "all_known_post_routes_button_gated": all(bool(item.get("button_gated")) for item in TASK_CATALOG + TASK_LIFECYCLE_POST_ROUTES),
        "call_ledger_required_for_all_known_post_routes": all(
            bool(item.get("call_ledger_required")) for item in TASK_CATALOG + TASK_LIFECYCLE_POST_ROUTES
        ),
        "cache_reads_create_no_tasks": True,
        "cancel_routes_external_calls": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _catalog_task_item(item: dict[str, Any]) -> dict[str, Any]:
    row = dict(item)
    purpose = row.get("deepseek_model_strategy_purpose")
    if purpose:
        strategy = build_deepseek_model_strategy_ref(str(purpose))
        strategy["model_source"] = str(row.get("deepseek_model_source") or strategy.get("model_source"))
        strategy["does_not_hardcode_model"] = bool(row.get("does_not_hardcode_deepseek_model"))
        row["deepseek_model_strategy"] = strategy
    return row


def build_task_catalog() -> dict[str, Any]:
    route_coverage = _build_route_coverage()
    return {
        "packet_key": "command_center_3_task_catalog",
        "schema_version": "command_center_3_task_catalog.v1",
        "status": "ready",
        "tasks": [_catalog_task_item(item) for item in TASK_CATALOG],
        "task_lifecycle_routes": [dict(item) for item in TASK_LIFECYCLE_POST_ROUTES],
        "route_coverage": route_coverage,
        "task_count": len(TASK_CATALOG),
        "policy": {
            "get_catalog_cache_only": True,
            "all_tasks_button_gated": all(bool(item.get("button_gated")) for item in TASK_CATALOG),
            "all_known_post_routes_button_gated": bool(route_coverage["all_known_post_routes_button_gated"]),
            "call_ledger_required_for_all": all(bool(item.get("call_ledger_required")) for item in TASK_CATALOG),
            "call_ledger_required_for_all_known_post_routes": bool(route_coverage["call_ledger_required_for_all_known_post_routes"]),
            "supports_local_task_cancel": True,
            "cancel_task_external_calls": False,
            "cancel_route_in_lifecycle_catalog": True,
            "post_task_may_trigger_external_request": True,
            "cache_api_external_calls": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        },
        "external_sources": sorted({source for item in TASK_CATALOG for source in item.get("possible_external_sources", [])}),
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "call_ledger": [
            {
                "api": "local_task_catalog_cache",
                "request_params_safe": {},
                "row_count": len(TASK_CATALOG),
                "data_date": None,
                "local_fetched_at": _now_iso(),
                "call_status": "cache_read",
                "error_message_safe": "",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "GET /api/tasks/catalog 只读取本地任务目录；不会调用 Tushare、DeepSeek、GitHub、Redis 或真实交易接口。"
        ],
    }


def _is_secret_key(key: Any) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in SECRET_KEYWORDS)


def _safe_text(value: Any, *, limit: int = 500) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_value(key: Any, value: Any) -> Any:
    if _is_secret_key(key):
        return None
    if isinstance(value, dict):
        return {str(child_key): safe for child_key, child_value in value.items() if (safe := _safe_value(child_key, child_value)) is not None}
    if isinstance(value, list):
        return [_safe_value(key, item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    return value


def _safe_payload(payload: Any = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {str(key): safe for key, value in payload.items() if (safe := _safe_value(key, value)) is not None}


def _status_event(status: str, *, progress: float, current_step: str, at: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "progress": float(progress),
        "current_step": current_step,
        "at": at or _now_iso(),
    }


def _persist_task(task: dict[str, Any]) -> dict[str, Any]:
    _TASKS[str(task["task_id"])] = task
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_task_status(task)
    except Exception:
        task.setdefault("warnings", []).append("task_metadata_sqlite_write_failed_safe")
    return task


def _read_persisted_task(task_id: str) -> dict[str, Any] | None:
    try:
        task = SQLiteMetaStore(SQLITE_META_PATH).read_task_status(str(task_id))
    except Exception:
        return None
    return task if isinstance(task, dict) else None


def _list_persisted_tasks() -> list[dict[str, Any]]:
    try:
        store = SQLiteMetaStore(SQLITE_META_PATH)
        tasks = [task for item in store.list_task_metadata() if (task := store.read_task_status(str(item.get("task_id") or "")))]
    except Exception:
        return []
    return [task for task in tasks if isinstance(task, dict)]


def _task_catalog_entry(task_type: str) -> dict[str, Any]:
    for item in TASK_CATALOG:
        if item.get("task_type") == task_type:
            return dict(item)
    return {}


def _stub_request_params_safe(task_type: str) -> dict[str, Any]:
    entry = _task_catalog_entry(task_type)
    purpose = entry.get("deepseek_model_strategy_purpose")
    if not purpose:
        return {}
    strategy = build_deepseek_model_strategy_ref(str(purpose))
    strategy["model_source"] = str(entry.get("deepseek_model_source") or strategy.get("model_source"))
    strategy["does_not_hardcode_model"] = bool(entry.get("does_not_hardcode_deepseek_model"))
    return {
        "deepseek_model_strategy": strategy
    }


def _stub_call_ledger(task_type: str, now: str) -> list[dict[str, Any]]:
    return [
        {
            "api": task_type,
            "request_params_safe": _stub_request_params_safe(task_type),
            "row_count": 0,
            "data_date": None,
            "local_fetched_at": now,
            "call_status": "stub_not_called",
            "error_message_safe": "",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def _cancel_call_ledger(task_id: str, now: str, *, reason_safe: str = "") -> dict[str, Any]:
    return {
        "api": "local_task_cancel",
        "task_id": str(task_id),
        "request_params_safe": {"reason": reason_safe} if reason_safe else {},
        "row_count": 0,
        "data_date": None,
        "local_fetched_at": now,
        "call_status": "cancelled_locally_no_external_call",
        "error_message_safe": "",
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def task_not_found_call_ledger(task_id: str, *, api: str = "local_task_status_lookup") -> list[dict[str, Any]]:
    return [
        {
            "api": api,
            "request_params_safe": {"task_id": _safe_text(task_id, limit=120)},
            "row_count": 0,
            "data_date": None,
            "local_fetched_at": _now_iso(),
            "call_status": "task_not_found_no_external_call",
            "error_message_safe": "task_not_found",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def task_not_found_warnings(route: str) -> list[str]:
    return [
        f"{route} 只执行本地任务状态查询；任务不存在时不调用 Tushare、DeepSeek、GitHub、Redis 或真实交易接口。"
    ]


def build_task_record(
    task_type: str,
    *,
    task_id: str | None = None,
    output_packet_key: str = "",
    payload: Any = None,
    status: str = "pending",
    progress: float = 0.0,
    current_step: str = "queued",
    warnings: list[str] | None = None,
    call_ledger: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected_status = status if status in TASK_STATUSES else "pending"
    now = _now_iso()
    record = {
        "task_id": task_id or f"local-{uuid.uuid4().hex[:12]}",
        "task_type": task_type,
        "status": selected_status,
        "created_at": now,
        "started_at": now if selected_status in {"running", "success", "failed"} else None,
        "finished_at": now if selected_status in {"success", "failed", "cancelled"} else None,
        "progress": max(0.0, min(1.0, float(progress))),
        "current_step": current_step,
        "error_message_safe": "",
        "output_packet_key": output_packet_key,
        "payload_safe": _safe_payload(payload),
        "warnings": list(warnings or []),
        "call_ledger": list(call_ledger or []),
        "backend": "local_fallback",
        "external_calls_triggered": False,
        "deepseek_called": False,
        "tushare_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "status_history": [_status_event(selected_status, progress=progress, current_step=current_step, at=now)],
    }
    return record


def create_task_record(
    task_type: str,
    *,
    output_packet_key: str = "",
    payload: Any = None,
    current_step: str = "queued",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    task = build_task_record(
        task_type,
        output_packet_key=output_packet_key,
        payload=payload,
        status="pending",
        progress=0.0,
        current_step=current_step,
        warnings=warnings,
    )
    return _persist_task(task)


def update_task_status(
    task_id: str,
    *,
    status: str,
    progress: float | None = None,
    current_step: str | None = None,
    error_message_safe: str | None = None,
    output_packet_key: str | None = None,
    call_ledger: list[dict[str, Any]] | None = None,
    warning: str | None = None,
) -> dict[str, Any] | None:
    task = read_task_status(task_id)
    if task is None:
        return None
    if status not in TASK_STATUSES:
        status = "failed"
        error_message_safe = error_message_safe or "invalid_task_status"
    now = _now_iso()
    task["status"] = status
    if progress is not None:
        task["progress"] = max(0.0, min(1.0, float(progress)))
    if current_step is not None:
        task["current_step"] = current_step
    if error_message_safe is not None:
        task["error_message_safe"] = _safe_text(error_message_safe)
    if output_packet_key is not None:
        task["output_packet_key"] = output_packet_key
    if call_ledger is not None:
        task["call_ledger"] = list(call_ledger)
    if warning:
        task.setdefault("warnings", []).append(warning)
    if status in {"running", "success", "failed"} and not task.get("started_at"):
        task["started_at"] = now
    if status in {"success", "failed", "cancelled"}:
        task["finished_at"] = now
    task.setdefault("status_history", []).append(
        _status_event(status, progress=float(task.get("progress") or 0.0), current_step=str(task.get("current_step") or ""), at=now)
    )
    return _persist_task(task)


def cancel_task(task_id: str, payload: Any = None) -> dict[str, Any] | None:
    task = read_task_status(task_id)
    if task is None:
        return None

    payload_safe = _safe_payload(payload)
    reason_safe = _safe_text(payload_safe.get("reason", "")) if isinstance(payload_safe, dict) else ""
    now = _now_iso()
    existing_ledger = list(task.get("call_ledger") or [])
    cancel_ledger = existing_ledger + [_cancel_call_ledger(str(task_id), now, reason_safe=reason_safe)]
    terminal = {"success", "failed", "cancelled"}
    if task.get("status") in terminal:
        task["call_ledger"] = cancel_ledger
        task.setdefault("warnings", []).append("task_cancel_noop_already_terminal")
        task["external_calls_triggered"] = False
        task["deepseek_called"] = False
        task["tushare_called"] = False
        task["github_called"] = False
        task["does_not_execute_trades"] = True
        task["does_not_modify_strategy_action"] = True
        return _persist_task(task)

    return update_task_status(
        str(task_id),
        status="cancelled",
        progress=float(task.get("progress") or 0.0),
        current_step="cancelled_by_user_no_external_call",
        error_message_safe="",
        call_ledger=cancel_ledger,
        warning="task_cancelled_locally_no_external_call",
    )


def create_task_stub(
    task_type: str,
    *,
    output_packet_key: str = "",
    payload: Any = None,
    current_step: str = "stub_created_no_external_call",
) -> dict[str, Any]:
    now = _now_iso()
    task = build_task_record(
        task_type,
        output_packet_key=output_packet_key,
        payload=payload,
        status="pending",
        progress=0.0,
        current_step="queued",
        warnings=["Command Center 3.0 MVP 任务接口为本地 lifecycle stub；没有调用 Tushare、DeepSeek、GitHub 或真实交易接口。"],
    )
    _persist_task(task)
    update_task_status(task["task_id"], status="running", progress=0.5, current_step="local_fallback_running")
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=current_step,
        call_ledger=_stub_call_ledger(task_type, now),
    ) or task


def read_task_status(task_id: str) -> dict[str, Any] | None:
    task_key = str(task_id)
    memory_task = _TASKS.get(task_key)
    persisted_task = _read_persisted_task(task_key)
    if memory_task is not None:
        row = dict(memory_task)
        row["storage_source"] = "memory_and_sqlite" if persisted_task is not None else "memory"
        return row
    if persisted_task is not None:
        row = dict(persisted_task)
        row["storage_source"] = "sqlite_meta"
        return row
    return None


def _merge_task_statuses() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    persisted_tasks = _list_persisted_tasks()
    persisted_ids = {str(task.get("task_id") or "") for task in persisted_tasks if task.get("task_id")}
    memory_ids = {str(task_id) for task_id in _TASKS}
    shared_ids = persisted_ids & memory_ids

    merged: dict[str, dict[str, Any]] = {}
    for task in persisted_tasks:
        task_id = str(task.get("task_id") or "")
        if not task_id:
            continue
        row = dict(task)
        row["storage_source"] = "sqlite_meta"
        merged[task_id] = row
    for task_id, task in _TASKS.items():
        row = dict(task)
        row["storage_source"] = "memory_and_sqlite" if str(task_id) in persisted_ids else "memory"
        merged[str(task_id)] = row

    sorted_tasks = sorted(
        merged.values(),
        key=lambda item: str(item.get("finished_at") or item.get("started_at") or item.get("created_at") or ""),
        reverse=True,
    )
    persistence = {
        "storage_backend": "memory_plus_sqlite_fallback",
        "sqlite_fallback_enabled": True,
        "sqlite_meta_path_label": ".stock_ming_3/meta.sqlite",
        "memory_task_count": len(memory_ids),
        "sqlite_task_count": len(persisted_ids),
        "deduplicated_task_count": len(sorted_tasks),
        "memory_only_task_count": len(memory_ids - persisted_ids),
        "sqlite_only_task_count": len(persisted_ids - memory_ids),
        "memory_and_sqlite_task_count": len(shared_ids),
        "task_rows_include_storage_source": True,
        "cache_read_external_calls": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    return sorted_tasks, persistence


def list_task_statuses() -> list[dict[str, Any]]:
    tasks, _ = _merge_task_statuses()
    return tasks


def build_task_status_index() -> dict[str, Any]:
    tasks, persistence = _merge_task_statuses()
    status_counts = {status: 0 for status in sorted(TASK_STATUSES)}
    for task in tasks:
        status = str(task.get("status") or "pending")
        status_counts[status] = status_counts.get(status, 0) + 1
    call_ledger_count = sum(len(task.get("call_ledger") or []) for task in tasks)
    external_calls_triggered = any(task.get("external_calls_triggered") is True for task in tasks)
    tushare_called = any(task.get("tushare_called") is True for task in tasks)
    deepseek_called = any(task.get("deepseek_called") is True for task in tasks)
    github_called = any(task.get("github_called") is True for task in tasks)
    does_not_execute_trades = all(task.get("does_not_execute_trades") is not False for task in tasks)
    does_not_modify_strategy_action = all(task.get("does_not_modify_strategy_action") is not False for task in tasks)
    latest_task = tasks[0] if tasks else {}
    return {
        "packet_key": "command_center_3_task_status_index",
        "schema_version": "command_center_3_task_status_index.v1",
        "mode": "cache_only",
        "status": "ready",
        "tasks": tasks,
        "task_count": len(tasks),
        "status_counts": status_counts,
        "latest_task_id": latest_task.get("task_id"),
        "latest_task_type": latest_task.get("task_type"),
        "latest_task_status": latest_task.get("status"),
        "call_ledger_count": call_ledger_count,
        "persistence": persistence,
        "persistence_source_rows": [
            {"source": "memory", "task_count": persistence["memory_task_count"], "external": False},
            {"source": "sqlite_meta", "task_count": persistence["sqlite_task_count"], "external": False},
            {"source": "deduplicated", "task_count": persistence["deduplicated_task_count"], "external": False},
        ],
        "policy": {
            "get_tasks_cache_only": True,
            "does_not_create_tasks": True,
            "does_not_call_external_sources": True,
            "reads_memory_and_sqlite_fallback": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        },
        "external_calls_triggered": external_calls_triggered,
        "tushare_called": tushare_called,
        "deepseek_called": deepseek_called,
        "github_called": github_called,
        "does_not_execute_trades": does_not_execute_trades,
        "does_not_modify_strategy_action": does_not_modify_strategy_action,
        "call_ledger": [
            {
                "api": "local_task_status_index",
                "request_params_safe": {},
                "row_count": len(tasks),
                "memory_task_count": persistence["memory_task_count"],
                "sqlite_task_count": persistence["sqlite_task_count"],
                "deduplicated_task_count": persistence["deduplicated_task_count"],
                "storage_backend": persistence["storage_backend"],
                "data_date": None,
                "local_fetched_at": _now_iso(),
                "call_status": "cache_read",
                "error_message_safe": "",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [
            "GET /api/tasks 只读取本地任务状态；不会调用 Tushare、DeepSeek、GitHub、Redis 或真实交易接口。",
            "任务明细中的 payload_safe 已在创建任务时剔除 token/api_key/authorization 等敏感字段。",
        ],
    }


def clear_task_statuses_for_tests(*, clear_persisted: bool = False) -> None:
    _TASKS.clear()
    if not clear_persisted:
        return
    try:
        SQLiteMetaStore(SQLITE_META_PATH).clear_task_statuses()
    except Exception:
        return
