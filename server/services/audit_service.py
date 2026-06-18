from __future__ import annotations

import datetime as _dt
import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from config import get_deepseek_model_strategy
from storage.sqlite_meta import SQLiteMetaStore
from server.services import (
    bootstrap_service,
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
RELEASE_GATE_SCHEMA_VERSION = "command_center_3_release_gate_readiness_audit.v1"
CI_NOTIFICATION_TRIAGE_SCHEMA_VERSION = "command_center_3_ci_notification_triage.v1"
PUSH_READINESS_RECEIPT_SCHEMA_VERSION = "command_center_3_push_readiness_receipt.v1"
LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION = "command_center_3_local_push_gate_run_receipt.v1"
MOTION_CLARITY_SCHEMA_VERSION = "command_center_3_motion_clarity_audit.v1"
RELEASE_GATE_STAGE_SCOPE = "release_gate_stage_scope_manifest"
REQUIRED_RELEASE_GATE_STAGE_KEYS = {
    "local_push_gate_static_contract",
    "fresh_local_gate_command_run",
    "secret_artifact_allowlist_review",
    "ci_mirror_workflow_contract",
    "matching_remote_actions_status",
    "failure_email_triage_evidence",
    "release_report_artifact_policy",
    "explicit_push_approval_boundary",
}
RELEASE_GATE_STAGE_LABELS = {
    "local_push_gate_static_contract": "local push gate static contract",
    "fresh_local_gate_command_run": "fresh local push gate command run",
    "secret_artifact_allowlist_review": "secret/artifact allowlist review",
    "ci_mirror_workflow_contract": "CI mirror workflow contract",
    "matching_remote_actions_status": "matching remote Actions status",
    "failure_email_triage_evidence": "failure email triage evidence",
    "release_report_artifact_policy": "release readiness report artifact policy",
    "explicit_push_approval_boundary": "explicit push approval boundary",
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
LOCAL_PUSH_GATE_RUN_RECEIPT_PATH = PROJECT_ROOT / ".stock_ming_3" / "release_gate" / "local_push_gate_run_receipt.json"
PUSH_GATE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "push_gate_3_0.sh"
SMOKE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "smoke_3_0.sh"
DATA_HEALTH_FRESHNESS_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "data_health_freshness_contract.py"
TUSHARE_ACCEPTANCE_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "tushare_acceptance_contract.py"
BOOTSTRAP_RUNTIME_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "bootstrap_runtime_contract.py"
TUSHARE_DEEPSEEK_LINKAGE_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "tushare_deepseek_linkage_contract.py"
FACTOR_TEST_LAB_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "factor_test_lab_contract.py"
FACTOR_UNIVERSE_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "factor_universe_contract.py"
DEEPSEEK_GOVERNANCE_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "deepseek_governance_contract.py"
NEXT_SESSION_MAP_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "next_session_map_contract.py"
CANDIDATE_RADAR_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "candidate_radar_contract.py"
CANDIDATE_RADAR_BROWSER_QA_RUNBOOK_PATH = PROJECT_ROOT / "scripts" / "candidate_radar_browser_qa_runbook.py"
STORAGE_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "storage_contract.py"
WORKER_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "worker_contract.py"
TAURI_DESKTOP_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "tauri_desktop_contract.py"
STREAMLIT_LEGACY_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "streamlit_legacy_contract.py"
TRADE_ISOLATION_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "trade_isolation_contract.py"
MOTION_VIEWPORT_QA_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "motion_viewport_qa_contract.py"
MOTION_BROWSER_QA_RUNBOOK_PATH = PROJECT_ROOT / "scripts" / "motion_browser_qa_runbook.py"
MOTION_BROWSER_QA_RUNNER_PATH = PROJECT_ROOT / "scripts" / "motion_browser_qa_runner.mjs"
MOTION_QA_ARTIFACT_ROOT = PROJECT_ROOT / ".stock_ming_3" / "motion_qa"
SECRET_KEYWORD_REVIEW_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "secret_keyword_review_contract.py"
GITHUB_WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"
DESKTOP_SRC_DIR = PROJECT_ROOT / "desktop" / "src"
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
        ("GET /api/bootstrap/status", "bootstrap_status", bootstrap_service.read_bootstrap_status_cache),
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


def _read_local_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _git_dir_path() -> Path:
    dot_git = PROJECT_ROOT / ".git"
    if dot_git.is_file():
        text = _read_local_text(dot_git).strip()
        if text.startswith("gitdir:"):
            raw_path = text.split(":", 1)[1].strip()
            path = Path(raw_path)
            return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    return dot_git


def _current_git_head_summary() -> dict[str, Any]:
    git_dir = _git_dir_path()
    head_file = git_dir / "HEAD"
    head_text = _read_local_text(head_file).strip()
    if not head_text:
        return {
            "read_status": "git_head_missing",
            "branch": "",
            "head_full": "",
            "head": "",
        }
    if head_text.startswith("ref:"):
        ref_name = head_text.split(":", 1)[1].strip()
        ref_text = _read_local_text(git_dir / ref_name).strip()
        head_full = ref_text if ref_text else ""
        branch = ref_name.removeprefix("refs/heads/")
        return {
            "read_status": "git_head_ref_present" if head_full else "git_head_ref_missing",
            "branch": branch,
            "head_full": head_full,
            "head": head_full[:7],
            "ref": ref_name,
        }
    return {
        "read_status": "git_head_detached",
        "branch": "HEAD",
        "head_full": head_text,
        "head": head_text[:7],
        "ref": "",
    }


def _read_local_push_gate_run_receipt() -> dict[str, Any]:
    current_head = _current_git_head_summary()
    if not LOCAL_PUSH_GATE_RUN_RECEIPT_PATH.exists():
        return {
            "schema_version": LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION,
            "status": "local_push_gate_run_receipt_missing",
            "scope": "ignored_local_push_gate_run_receipt_no_push_no_github_api",
            "receipt_path": _relative_path(LOCAL_PUSH_GATE_RUN_RECEIPT_PATH),
            "read_status": "receipt_missing",
            "current_head": current_head.get("head"),
            "current_head_full": current_head.get("head_full"),
            "current_branch": current_head.get("branch"),
            "head_matches_current": False,
            "fresh_local_gate_run_observed": False,
            "did_not_push": True,
            "git_add_dot_used": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    try:
        raw = json.loads(LOCAL_PUSH_GATE_RUN_RECEIPT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "schema_version": LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION,
            "status": "local_push_gate_run_receipt_unreadable",
            "scope": "ignored_local_push_gate_run_receipt_no_push_no_github_api",
            "receipt_path": _relative_path(LOCAL_PUSH_GATE_RUN_RECEIPT_PATH),
            "read_status": "receipt_read_failed",
            "current_head": current_head.get("head"),
            "current_head_full": current_head.get("head_full"),
            "current_branch": current_head.get("branch"),
            "head_matches_current": False,
            "fresh_local_gate_run_observed": False,
            "did_not_push": True,
            "git_add_dot_used": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    raw_receipt = _as_dict(raw)
    receipt = _as_dict(_safe_value(raw_receipt))
    receipt_head_full = str(raw_receipt.get("head_full") or "")
    receipt_head = str(raw_receipt.get("head") or "")
    current_head_full = str(current_head.get("head_full") or "")
    current_head_short = str(current_head.get("head") or "")
    head_matches_current = bool(
        current_head_full
        and (
            receipt_head_full == current_head_full
            or (receipt_head and current_head_short and receipt_head == current_head_short)
        )
    )
    schema_ok = raw_receipt.get("schema_version") == LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION
    status_ok = raw_receipt.get("status") == "local_push_gate_passed_current_head"
    boundary_ok = (
        raw_receipt.get("did_not_push") is True
        and raw_receipt.get("git_add_dot_used") is False
        and raw_receipt.get("external_calls_triggered") is False
        and raw_receipt.get("tushare_called") is False
        and raw_receipt.get("deepseek_called") is False
        and raw_receipt.get("github_api_called") is False
        and raw_receipt.get("does_not_execute_trades") is True
        and raw_receipt.get("does_not_modify_strategy_action") is True
        and raw_receipt.get("contains_secret") is False
    )
    fresh = bool(schema_ok and status_ok and head_matches_current and boundary_ok)
    receipt.update(
        {
            "schema_version": str(receipt.get("schema_version") or LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION),
            "status": receipt.get("status") if schema_ok else "local_push_gate_run_receipt_schema_mismatch",
            "scope": str(receipt.get("scope") or "ignored_local_push_gate_run_receipt_no_push_no_github_api"),
            "receipt_path": _relative_path(LOCAL_PUSH_GATE_RUN_RECEIPT_PATH),
            "read_status": "receipt_present",
            "current_head": current_head_short,
            "current_head_full": current_head_full,
            "current_branch": current_head.get("branch"),
            "head_matches_current": head_matches_current,
            "boundary_flags_valid": boundary_ok,
            "fresh_local_gate_run_observed": fresh,
            "remote_actions_status_known": False,
            "latest_remote_run_verified_green": False,
            "local_gate_pass_is_not_ci_status": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    )
    return receipt


def _script_contains_any(script: str, markers: tuple[str, ...]) -> bool:
    lower_script = script.lower()
    return any(marker.lower() in lower_script for marker in markers)


def _release_gate_row(
    criterion: str,
    passed: bool,
    *,
    evidence: str,
    production_blocker: bool = True,
    status_override: str | None = None,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status_override or ("passed" if passed else "blocked"),
        "passed": passed,
        "evidence": evidence,
        "production_blocker": production_blocker and not passed,
    }


def _release_gate_workflow_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not GITHUB_WORKFLOWS_DIR.exists():
        return rows
    for path in sorted(GITHUB_WORKFLOWS_DIR.glob("*.y*ml")):
        text = _read_local_text(path)
        mirrors_push_gate = "push_gate_3_0.sh" in text or (
            "-m unittest discover -s tests" in text and "npm run build" in text and "smoke_3_0.sh" in text
        )
        rows.append(
            {
                "workflow": _relative_path(path),
                "status": "mirrors_push_gate" if mirrors_push_gate else "unrelated_or_partial",
                "mirrors_local_push_gate": mirrors_push_gate,
                "contains_unittest_step": "-m unittest discover -s tests" in text,
                "contains_desktop_build_step": "npm run build" in text,
                "contains_smoke_step": "smoke_3_0.sh" in text,
                "contains_diff_check_step": "git diff --check" in text,
                "contains_secret_scan_step": "secret_high_risk_scan" in text or "api_key|token|secret|password" in text,
                "contains_artifact_scan_step": "artifact_scan" in text or "git ls-files" in text,
                "github_api_call_detected": _script_contains_any(
                    text,
                    ("gh api", "api.github.com", "github/graphql", "curl https://api.github"),
                ),
                "external_calls_triggered": False,
            }
        )
    return rows


def _release_gate_readiness_audit() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    script = _read_local_text(PUSH_GATE_SCRIPT_PATH)
    smoke_script = _read_local_text(SMOKE_SCRIPT_PATH)
    data_health_freshness_script = _read_local_text(DATA_HEALTH_FRESHNESS_CONTRACT_PATH)
    tushare_acceptance_script = _read_local_text(TUSHARE_ACCEPTANCE_CONTRACT_PATH)
    bootstrap_runtime_script = _read_local_text(BOOTSTRAP_RUNTIME_CONTRACT_PATH)
    tushare_deepseek_linkage_script = _read_local_text(TUSHARE_DEEPSEEK_LINKAGE_CONTRACT_PATH)
    factor_test_lab_script = _read_local_text(FACTOR_TEST_LAB_CONTRACT_PATH)
    factor_universe_script = _read_local_text(FACTOR_UNIVERSE_CONTRACT_PATH)
    deepseek_governance_script = _read_local_text(DEEPSEEK_GOVERNANCE_CONTRACT_PATH)
    next_session_map_script = _read_local_text(NEXT_SESSION_MAP_CONTRACT_PATH)
    candidate_radar_script = _read_local_text(CANDIDATE_RADAR_CONTRACT_PATH)
    candidate_radar_browser_qa_runbook_script = _read_local_text(CANDIDATE_RADAR_BROWSER_QA_RUNBOOK_PATH)
    storage_script = _read_local_text(STORAGE_CONTRACT_PATH)
    worker_script = _read_local_text(WORKER_CONTRACT_PATH)
    tauri_desktop_script = _read_local_text(TAURI_DESKTOP_CONTRACT_PATH)
    streamlit_legacy_script = _read_local_text(STREAMLIT_LEGACY_CONTRACT_PATH)
    trade_isolation_script = _read_local_text(TRADE_ISOLATION_CONTRACT_PATH)
    motion_qa_script = _read_local_text(MOTION_VIEWPORT_QA_CONTRACT_PATH)
    motion_browser_qa_runbook = _read_local_text(MOTION_BROWSER_QA_RUNBOOK_PATH)
    motion_browser_qa_runner = _read_local_text(MOTION_BROWSER_QA_RUNNER_PATH)
    secret_keyword_review_script = _read_local_text(SECRET_KEYWORD_REVIEW_CONTRACT_PATH)
    workflow_rows = _release_gate_workflow_rows()
    provider_invocation_markers = (
        "tushare_adapter",
        "refresh-tushare",
        "tushare.pro_api",
        "ts.pro_api",
        "deepseek_adapter",
        "deepseek.chat",
        "deepseek.com",
        "gh api",
        "api.github.com",
        "github/graphql",
        "curl https://api.github",
    )
    trade_invocation_markers = (
        "execute_trade(",
        "execute_trade ",
        "place_order(",
        "place_order ",
        "broker.submit(",
        "real_trading_enabled=true",
        "live_order(",
        "live_order ",
    )
    checks = {
        "push_gate_script_exists": PUSH_GATE_SCRIPT_PATH.exists(),
        "push_gate_script_executable": PUSH_GATE_SCRIPT_PATH.exists()
        and bool(PUSH_GATE_SCRIPT_PATH.stat().st_mode & 0o111),
        "smoke_script_exists": SMOKE_SCRIPT_PATH.exists() and bool(smoke_script),
        "data_health_freshness_contract_exists": DATA_HEALTH_FRESHNESS_CONTRACT_PATH.exists()
        and bool(data_health_freshness_script),
        "tushare_acceptance_contract_exists": TUSHARE_ACCEPTANCE_CONTRACT_PATH.exists()
        and bool(tushare_acceptance_script),
        "bootstrap_runtime_contract_exists": BOOTSTRAP_RUNTIME_CONTRACT_PATH.exists()
        and bool(bootstrap_runtime_script),
        "tushare_deepseek_linkage_contract_exists": TUSHARE_DEEPSEEK_LINKAGE_CONTRACT_PATH.exists()
        and bool(tushare_deepseek_linkage_script),
        "factor_test_lab_contract_exists": FACTOR_TEST_LAB_CONTRACT_PATH.exists()
        and bool(factor_test_lab_script),
        "factor_universe_contract_exists": FACTOR_UNIVERSE_CONTRACT_PATH.exists()
        and bool(factor_universe_script),
        "deepseek_governance_contract_exists": DEEPSEEK_GOVERNANCE_CONTRACT_PATH.exists()
        and bool(deepseek_governance_script),
        "next_session_map_contract_exists": NEXT_SESSION_MAP_CONTRACT_PATH.exists()
        and bool(next_session_map_script),
        "candidate_radar_contract_exists": CANDIDATE_RADAR_CONTRACT_PATH.exists()
        and bool(candidate_radar_script),
        "candidate_radar_browser_qa_runbook_exists": CANDIDATE_RADAR_BROWSER_QA_RUNBOOK_PATH.exists()
        and bool(candidate_radar_browser_qa_runbook_script),
        "storage_contract_exists": STORAGE_CONTRACT_PATH.exists() and bool(storage_script),
        "worker_contract_exists": WORKER_CONTRACT_PATH.exists() and bool(worker_script),
        "tauri_desktop_contract_exists": TAURI_DESKTOP_CONTRACT_PATH.exists() and bool(tauri_desktop_script),
        "streamlit_legacy_contract_exists": STREAMLIT_LEGACY_CONTRACT_PATH.exists() and bool(streamlit_legacy_script),
        "trade_isolation_contract_exists": TRADE_ISOLATION_CONTRACT_PATH.exists() and bool(trade_isolation_script),
        "motion_viewport_qa_contract_exists": MOTION_VIEWPORT_QA_CONTRACT_PATH.exists() and bool(motion_qa_script),
        "motion_browser_qa_runbook_exists": MOTION_BROWSER_QA_RUNBOOK_PATH.exists() and bool(motion_browser_qa_runbook),
        "secret_keyword_review_contract_exists": SECRET_KEYWORD_REVIEW_CONTRACT_PATH.exists() and bool(secret_keyword_review_script),
        "motion_viewport_qa_contract_step": "scripts/motion_viewport_qa_contract.py" in script
        and "Motion viewport QA contract" in script,
        "motion_browser_qa_runbook_step": "scripts/motion_browser_qa_runbook.py" in script
        and "Motion browser QA runbook" in script,
        "data_health_freshness_contract_step": "scripts/data_health_freshness_contract.py" in script
        and "Data Health freshness contract" in script,
        "tushare_acceptance_contract_step": "scripts/tushare_acceptance_contract.py" in script
        and "Tushare acceptance contract" in script,
        "bootstrap_runtime_contract_step": "scripts/bootstrap_runtime_contract.py" in script
        and "Bootstrap runtime contract" in script,
        "tushare_deepseek_linkage_contract_step": "scripts/tushare_deepseek_linkage_contract.py" in script
        and "Tushare DeepSeek linkage contract" in script,
        "factor_test_lab_contract_step": "scripts/factor_test_lab_contract.py" in script
        and "Factor Test Lab contract" in script,
        "factor_universe_contract_step": "scripts/factor_universe_contract.py" in script
        and "Factor universe contract" in script,
        "deepseek_governance_contract_step": "scripts/deepseek_governance_contract.py" in script
        and "DeepSeek governance contract" in script,
        "next_session_map_contract_step": "scripts/next_session_map_contract.py" in script
        and "Next-session map contract" in script,
        "candidate_radar_contract_step": "scripts/candidate_radar_contract.py" in script
        and "Candidate Radar contract" in script,
        "candidate_radar_browser_qa_runbook_step": "scripts/candidate_radar_browser_qa_runbook.py" in script
        and "Candidate Radar browser QA runbook" in script,
        "storage_contract_step": "scripts/storage_contract.py" in script and "Storage contract" in script,
        "worker_contract_step": "scripts/worker_contract.py" in script and "Worker contract" in script,
        "tauri_desktop_contract_step": "scripts/tauri_desktop_contract.py" in script
        and "Tauri desktop contract" in script,
        "streamlit_legacy_contract_step": "scripts/streamlit_legacy_contract.py" in script
        and "Streamlit legacy contract" in script,
        "trade_isolation_contract_step": "scripts/trade_isolation_contract.py" in script
        and "Trade isolation contract" in script,
        "secret_keyword_review_contract_step": "scripts/secret_keyword_review_contract.py" in script
        and "Secret keyword review contract" in script,
        "uses_project_venv_python": 'PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"' in script,
        "refuses_missing_project_python": "Do not use system Python" in script and 'if [ ! -x "$PYTHON_BIN" ]' in script,
        "python_unittest_step": "-m unittest discover -s tests" in script,
        "desktop_build_step": "cd desktop && npm run build" in script,
        "smoke_step": "scripts/smoke_3_0.sh" in script,
        "diff_check_step": "git diff --check" in script,
        "high_risk_secret_scan_step": "secret_high_risk_scan" in script and "high-risk secret value scan" in script,
        "keyword_review_scan_step": "keyword scan for review" in script,
        "keyword_review_raw_lines_suppressed": "raw lines suppressed" in script and "showing first 120" not in script,
        "secret_keyword_review_contract_is_structured": "command_center_3_secret_keyword_review_contract.v1" in secret_keyword_review_script
        and "raw_keyword_lines_emitted" in secret_keyword_review_script
        and "outputs_source_line_text" in secret_keyword_review_script
        and "category_rows" in secret_keyword_review_script,
        "data_health_freshness_contract_is_local": "data_health_freshness_push_gate_contract.v1" in data_health_freshness_script
        and "local_cache_contract_no_provider_execution" in data_health_freshness_script
        and "provider_backed_trade_cal_acceptance_done" in data_health_freshness_script
        and "does_not_execute_trades" in data_health_freshness_script,
        "tushare_acceptance_contract_is_local": "command_center_3_tushare_acceptance_contract.v1" in tushare_acceptance_script
        and "local_matrix_and_readiness_contract_no_provider_execution" in tushare_acceptance_script
        and "provider_backed_acceptance_done" in tushare_acceptance_script
        and "production_tushare_pipeline_complete" in tushare_acceptance_script
        and "does_not_execute_trades" in tushare_acceptance_script
        and "tushare_adapter" not in tushare_acceptance_script
        and "api.github.com" not in tushare_acceptance_script,
        "tushare_production_stage_scope_manifest_is_local": "tushare_production_stage_scope_manifest"
        in tushare_acceptance_script
        and "tushare_production_stage_scope_manifest_is_complete_and_pending" in tushare_acceptance_script
        and "provider_backed_acceptance_done" in tushare_acceptance_script
        and "production_tushare_pipeline_complete" in tushare_acceptance_script
        and "external_calls_triggered" in tushare_acceptance_script
        and "does_not_execute_trades" in tushare_acceptance_script
        and "tushare_adapter" not in tushare_acceptance_script
        and "api.github.com" not in tushare_acceptance_script,
        "bootstrap_runtime_contract_is_local": "command_center_3_bootstrap_runtime_contract.v1" in bootstrap_runtime_script
        and "local_bootstrap_runtime_contract_no_provider_or_model_execution" in bootstrap_runtime_script
        and "cache_only_payload_sanitizes_secret_like_inputs" in bootstrap_runtime_script
        and "live_light_records_plan_without_provider_execution" in bootstrap_runtime_script
        and "live_light_rate_limit_reuses_existing_task" in bootstrap_runtime_script
        and "provider_execution_implemented" in bootstrap_runtime_script
        and "model_execution_implemented" in bootstrap_runtime_script
        and "does_not_execute_trades" in bootstrap_runtime_script
        and "tushare_adapter" not in bootstrap_runtime_script
        and "deepseek_adapter" not in bootstrap_runtime_script
        and "api.github.com" not in bootstrap_runtime_script,
        "tushare_deepseek_linkage_contract_is_local": (
            "command_center_3_tushare_deepseek_linkage_contract.v1" in tushare_deepseek_linkage_script
            and "local_tushare_deepseek_linkage_contract_no_provider_or_model_execution"
            in tushare_deepseek_linkage_script
            and "live_light_plans_tushare_deepseek_without_calling" in tushare_deepseek_linkage_script
            and "candidate_quant_acceptance_dry_run_limits_apis_and_hides_credentials"
            in tushare_deepseek_linkage_script
            and "provider_execution_implemented" in tushare_deepseek_linkage_script
            and "model_execution_implemented" in tushare_deepseek_linkage_script
            and "production_quant_projection_complete" in tushare_deepseek_linkage_script
            and "does_not_execute_trades" in tushare_deepseek_linkage_script
            and "tushare_adapter" not in tushare_deepseek_linkage_script
            and "deepseek_adapter" not in tushare_deepseek_linkage_script
            and "api.github.com" not in tushare_deepseek_linkage_script
        ),
        "factor_test_lab_contract_is_local": "command_center_3_factor_test_lab_contract.v1" in factor_test_lab_script
        and "local_factor_test_lab_contract_no_provider_execution" in factor_test_lab_script
        and "provider_backed_small_pool_validation_done" in factor_test_lab_script
        and "production_factor_test_validation_complete" in factor_test_lab_script
        and "does_not_execute_trades" in factor_test_lab_script
        and "tushare_adapter" not in factor_test_lab_script
        and "api.github.com" not in factor_test_lab_script,
        "factor_test_production_stage_scope_manifest_is_local": "factor_test_production_stage_scope_manifest"
        in factor_test_lab_script
        and "factor_test_production_stage_scope_manifest_is_complete_and_pending" in factor_test_lab_script
        and "provider_backed_small_pool_validation_done" in factor_test_lab_script
        and "full_market_validation_done" in factor_test_lab_script
        and "production_factor_test_validation_complete" in factor_test_lab_script
        and "external_calls_triggered" in factor_test_lab_script
        and "does_not_execute_trades" in factor_test_lab_script
        and "tushare_adapter" not in factor_test_lab_script
        and "api.github.com" not in factor_test_lab_script,
        "factor_universe_contract_is_local": "command_center_3_factor_universe_contract.v1" in factor_universe_script
        and "local_factor_universe_contract_no_batch_or_provider_execution" in factor_universe_script
        and "production_factor_universe_complete" in factor_universe_script
        and "full_pool_validation_done" in factor_universe_script
        and "cross_sectional_rank_zscore_done" in factor_universe_script
        and "does_not_execute_trades" in factor_universe_script
        and "tushare_adapter" not in factor_universe_script
        and "deepseek_adapter" not in factor_universe_script
        and "api.github.com" not in factor_universe_script,
        "deepseek_governance_contract_is_local": "command_center_3_deepseek_governance_contract.v1" in deepseek_governance_script
        and "local_deepseek_governance_contract_no_model_call" in deepseek_governance_script
        and "provider_benchmark_done" in deepseek_governance_script
        and "production_deepseek_explanation_complete" in deepseek_governance_script
        and "response_format_enforced" in deepseek_governance_script
        and "does_not_execute_trades" in deepseek_governance_script
        and "tushare_adapter" not in deepseek_governance_script
        and "deepseek_adapter" not in deepseek_governance_script
        and "deepseek.chat" not in deepseek_governance_script
        and "api.github.com" not in deepseek_governance_script,
        "next_session_map_contract_is_local": "command_center_3_next_session_map_contract.v1" in next_session_map_script
        and "local_next_session_map_contract_no_browser_no_provider" in next_session_map_script
        and "streamlit_parity_complete" in next_session_map_script
        and "production_replacement_complete" in next_session_map_script
        and "browser_visual_qa_done" in next_session_map_script
        and "does_not_execute_trades" in next_session_map_script
        and "tushare_adapter" not in next_session_map_script
        and "deepseek_adapter" not in next_session_map_script
        and "api.github.com" not in next_session_map_script,
        "candidate_radar_contract_is_local": "command_center_3_candidate_radar_contract.v1" in candidate_radar_script
        and "local_candidate_radar_contract_no_provider_execution" in candidate_radar_script
        and "production_radar_replacement_complete" in candidate_radar_script
        and "legacy_retirement_ready" in candidate_radar_script
        and "candidate_is_not_buy_instruction" in candidate_radar_script
        and "does_not_execute_trades" in candidate_radar_script
        and "tushare_adapter" not in candidate_radar_script
        and "api.github.com" not in candidate_radar_script,
        "candidate_radar_browser_qa_runbook_is_local": "candidate_radar_browser_qa_runbook.v1" in candidate_radar_browser_qa_runbook_script
        and "local_candidate_radar_browser_qa_runbook_not_browser_execution" in candidate_radar_browser_qa_runbook_script
        and "visual_qa_complete" in candidate_radar_browser_qa_runbook_script
        and "browser_performance_trace_done" in candidate_radar_browser_qa_runbook_script
        and "production_radar_replacement_complete" in candidate_radar_browser_qa_runbook_script
        and "opens_no_browser" in candidate_radar_browser_qa_runbook_script
        and "writes_no_artifacts" in candidate_radar_browser_qa_runbook_script
        and "tushare_adapter" not in candidate_radar_browser_qa_runbook_script
        and "deepseek_adapter" not in candidate_radar_browser_qa_runbook_script
        and "api.github.com" not in candidate_radar_browser_qa_runbook_script,
        "storage_contract_is_local": "command_center_3_storage_contract.v1" in storage_script
        and "local_storage_contract_no_physical_migration" in storage_script
        and "production_storage_complete" in storage_script
        and "dry_runs_are_not_production_completion" in storage_script
        and "schema_migration_executed" in storage_script
        and "does_not_execute_trades" in storage_script
        and "tushare_adapter" not in storage_script
        and "api.github.com" not in storage_script,
        "worker_contract_is_local": "command_center_3_worker_contract.v1" in worker_script
        and "local_worker_contract_no_process_start" in worker_script
        and "production_worker_complete" in worker_script
        and "healthcheck_executed" in worker_script
        and "activation_ready" in worker_script
        and "does_not_execute_trades" in worker_script
        and "tushare_adapter" not in worker_script
        and "api.github.com" not in worker_script,
        "tauri_desktop_contract_is_local": "command_center_3_tauri_desktop_contract.v1" in tauri_desktop_script
        and "local_tauri_desktop_contract_no_build_or_runtime_execution" in tauri_desktop_script
        and "production_package_complete" in tauri_desktop_script
        and "packaged_runtime_qa_done" in tauri_desktop_script
        and "tauri_build_executed" in tauri_desktop_script
        and "does_not_run_tauri" in tauri_desktop_script
        and "does_not_execute_trades" in tauri_desktop_script
        and "tushare_adapter" not in tauri_desktop_script
        and "deepseek_adapter" not in tauri_desktop_script
        and "api.github.com" not in tauri_desktop_script,
        "streamlit_legacy_contract_is_local": "command_center_3_streamlit_legacy_contract.v1" in streamlit_legacy_script
        and "local_streamlit_legacy_contract_not_streamlit_execution" in streamlit_legacy_script
        and "ordinary_workflow_exit_complete" in streamlit_legacy_script
        and "full_streamlit_removal_ready" in streamlit_legacy_script
        and "streamlit_fallback_retained" in streamlit_legacy_script
        and "does_not_open_streamlit" in streamlit_legacy_script
        and "does_not_execute_trades" in streamlit_legacy_script
        and "tushare_adapter" not in streamlit_legacy_script
        and "deepseek_adapter" not in streamlit_legacy_script
        and "api.github.com" not in streamlit_legacy_script,
        "trade_isolation_contract_is_local": "command_center_3_trade_isolation_contract.v1" in trade_isolation_script
        and "local_trade_isolation_contract_no_broker_or_order_execution" in trade_isolation_script
        and "real_trading_connected" in trade_isolation_script
        and "broker_adapter_connected" in trade_isolation_script
        and "order_endpoint_present" in trade_isolation_script
        and "trade_execution_api_enabled" in trade_isolation_script
        and "future_real_trading_requires_separate_project" in trade_isolation_script
        and "does_not_execute_trades" in trade_isolation_script
        and "tushare_adapter" not in trade_isolation_script
        and "deepseek_adapter" not in trade_isolation_script
        and "api.github.com" not in trade_isolation_script,
        "generated_artifact_scan_step": "artifact_scan" in script and "git ls-files" in script,
        "release_report_step": "PUSH_GATE_REPORT_PATH" in script and "write_release_readiness_report" in script,
        "clean_worktree_after_report": script.find('run_step "Release readiness report"') >= 0
        and script.find('run_step "Release readiness report"') < script.find('run_step "Clean worktree check"'),
        "local_push_gate_run_receipt_step": "LOCAL_PUSH_GATE_RECEIPT_PATH" in script
        and "write_local_push_gate_run_receipt" in script,
        "local_push_gate_run_receipt_after_clean": script.find('run_step "Clean worktree check"') >= 0
        and script.find('run_step "Clean worktree check"') < script.find('run_step "Local push gate run receipt"'),
        "no_git_push": "git push" not in script,
        "no_git_add_dot": "git add ." not in script,
        "does_not_call_tushare": not _script_contains_any(script, ("tushare_adapter", "refresh-tushare", "tushare.pro_api", "ts.pro_api")),
        "does_not_call_deepseek": not _script_contains_any(script, ("deepseek_adapter", "deepseek.chat", "deepseek.com")),
        "does_not_call_github_api": not _script_contains_any(
            script,
            ("gh api", "api.github.com", "github/graphql", "curl https://api.github"),
        ),
        "does_not_execute_trades": not _script_contains_any(script, trade_invocation_markers),
        "does_not_invoke_external_providers": not _script_contains_any(script, provider_invocation_markers),
        "motion_viewport_qa_contract_is_local_static": "local_static_contract_not_browser_execution" in motion_qa_script
        and "visual_qa_complete" in motion_qa_script
        and "browser_performance_verified" in motion_qa_script
        and "external_calls_triggered" in motion_qa_script,
        "motion_browser_qa_runbook_is_local_static": "local_browser_qa_runbook_not_browser_execution" in motion_browser_qa_runbook
        and "opens_no_browser" in motion_browser_qa_runbook
        and "writes_no_artifacts" in motion_browser_qa_runbook
        and "external_calls_triggered" in motion_browser_qa_runbook
        and "motion_browser_qa_runner.mjs" in motion_browser_qa_runbook
        and "command_center_3_motion_browser_qa_result.v1" in motion_browser_qa_runner
        and "explicit_local_browser_visual_performance_run" in motion_browser_qa_runner
        and "chromium.launch" in motion_browser_qa_runner
        and "page.goto" in motion_browser_qa_runner
        and ".stock_ming_3/motion_qa" in motion_browser_qa_runner
        and "starts_no_servers" in motion_browser_qa_runner
        and "local_urls_only" in motion_browser_qa_runner
        and "tushare_adapter" not in motion_browser_qa_runner
        and "deepseek_adapter" not in motion_browser_qa_runner
        and "api.github.com" not in motion_browser_qa_runner,
    }
    ci_mirror_ready = any(bool(row.get("mirrors_local_push_gate")) for row in workflow_rows)
    false_positive_allowlist_review_ready = False
    local_gate_ready = all(
        bool(checks[key])
        for key in (
            "push_gate_script_exists",
            "push_gate_script_executable",
            "smoke_script_exists",
            "data_health_freshness_contract_exists",
            "data_health_freshness_contract_step",
            "data_health_freshness_contract_is_local",
            "tushare_acceptance_contract_exists",
            "tushare_acceptance_contract_step",
            "tushare_acceptance_contract_is_local",
            "tushare_production_stage_scope_manifest_is_local",
            "bootstrap_runtime_contract_exists",
            "bootstrap_runtime_contract_step",
            "bootstrap_runtime_contract_is_local",
            "tushare_deepseek_linkage_contract_exists",
            "tushare_deepseek_linkage_contract_step",
            "tushare_deepseek_linkage_contract_is_local",
            "factor_test_lab_contract_exists",
            "factor_test_lab_contract_step",
            "factor_test_lab_contract_is_local",
            "factor_test_production_stage_scope_manifest_is_local",
            "factor_universe_contract_exists",
            "factor_universe_contract_step",
            "factor_universe_contract_is_local",
            "deepseek_governance_contract_exists",
            "deepseek_governance_contract_step",
            "deepseek_governance_contract_is_local",
            "next_session_map_contract_exists",
            "next_session_map_contract_step",
            "next_session_map_contract_is_local",
            "candidate_radar_contract_exists",
            "candidate_radar_contract_step",
            "candidate_radar_contract_is_local",
            "candidate_radar_browser_qa_runbook_exists",
            "candidate_radar_browser_qa_runbook_step",
            "candidate_radar_browser_qa_runbook_is_local",
            "storage_contract_exists",
            "storage_contract_step",
            "storage_contract_is_local",
            "worker_contract_exists",
            "worker_contract_step",
            "worker_contract_is_local",
            "tauri_desktop_contract_exists",
            "tauri_desktop_contract_step",
            "tauri_desktop_contract_is_local",
            "streamlit_legacy_contract_exists",
            "streamlit_legacy_contract_step",
            "streamlit_legacy_contract_is_local",
            "trade_isolation_contract_exists",
            "trade_isolation_contract_step",
            "trade_isolation_contract_is_local",
            "motion_viewport_qa_contract_exists",
            "motion_viewport_qa_contract_step",
            "motion_viewport_qa_contract_is_local_static",
            "motion_browser_qa_runbook_exists",
            "motion_browser_qa_runbook_step",
            "motion_browser_qa_runbook_is_local_static",
            "secret_keyword_review_contract_exists",
            "secret_keyword_review_contract_step",
            "secret_keyword_review_contract_is_structured",
            "uses_project_venv_python",
            "refuses_missing_project_python",
            "python_unittest_step",
            "desktop_build_step",
            "smoke_step",
            "diff_check_step",
            "high_risk_secret_scan_step",
            "keyword_review_scan_step",
            "keyword_review_raw_lines_suppressed",
            "generated_artifact_scan_step",
            "release_report_step",
            "clean_worktree_after_report",
            "local_push_gate_run_receipt_step",
            "local_push_gate_run_receipt_after_clean",
            "no_git_push",
            "no_git_add_dot",
            "does_not_call_tushare",
            "does_not_call_deepseek",
            "does_not_call_github_api",
            "does_not_execute_trades",
            "does_not_invoke_external_providers",
        )
    )
    rows = [
        _release_gate_row("push_gate_script_exists", checks["push_gate_script_exists"], evidence=_relative_path(PUSH_GATE_SCRIPT_PATH)),
        _release_gate_row(
            "push_gate_script_executable",
            checks["push_gate_script_executable"],
            evidence="script has executable bit",
        ),
        _release_gate_row("smoke_script_exists", checks["smoke_script_exists"], evidence=_relative_path(SMOKE_SCRIPT_PATH)),
        _release_gate_row(
            "data_health_freshness_contract_exists",
            checks["data_health_freshness_contract_exists"],
            evidence=_relative_path(DATA_HEALTH_FRESHNESS_CONTRACT_PATH),
        ),
        _release_gate_row(
            "data_health_freshness_contract_step",
            checks["data_health_freshness_contract_step"],
            evidence="push gate runs scripts/data_health_freshness_contract.py after smoke and before motion QA",
        ),
        _release_gate_row(
            "data_health_freshness_contract_is_local",
            checks["data_health_freshness_contract_is_local"],
            evidence="contract keeps LTG-01 provider-backed acceptance pending and validates local no-provider boundaries",
        ),
        _release_gate_row(
            "tushare_acceptance_contract_exists",
            checks["tushare_acceptance_contract_exists"],
            evidence=_relative_path(TUSHARE_ACCEPTANCE_CONTRACT_PATH),
        ),
        _release_gate_row(
            "tushare_acceptance_contract_step",
            checks["tushare_acceptance_contract_step"],
            evidence="push gate runs scripts/tushare_acceptance_contract.py after Data Health and before motion QA",
        ),
        _release_gate_row(
            "tushare_acceptance_contract_is_local",
            checks["tushare_acceptance_contract_is_local"],
            evidence="contract keeps LTG-02 matrix/readiness/provider-sample plans separate from provider-backed production acceptance",
        ),
        _release_gate_row(
            "tushare_production_stage_scope_manifest_is_local",
            checks["tushare_production_stage_scope_manifest_is_local"],
            evidence="contract exposes LTG-02 production stage scope while provider execution, full-interface acceptance, and production completion remain pending",
        ),
        _release_gate_row(
            "bootstrap_runtime_contract_exists",
            checks["bootstrap_runtime_contract_exists"],
            evidence=_relative_path(BOOTSTRAP_RUNTIME_CONTRACT_PATH),
        ),
        _release_gate_row(
            "bootstrap_runtime_contract_step",
            checks["bootstrap_runtime_contract_step"],
            evidence="push gate runs scripts/bootstrap_runtime_contract.py after Tushare acceptance and before Factor Test Lab",
        ),
        _release_gate_row(
            "bootstrap_runtime_contract_is_local",
            checks["bootstrap_runtime_contract_is_local"],
            evidence="contract keeps cache_only offline and live_light bootstrap as a local plan/model-ledger skeleton with no provider/model execution",
        ),
        _release_gate_row(
            "tushare_deepseek_linkage_contract_exists",
            checks["tushare_deepseek_linkage_contract_exists"],
            evidence=_relative_path(TUSHARE_DEEPSEEK_LINKAGE_CONTRACT_PATH),
        ),
        _release_gate_row(
            "tushare_deepseek_linkage_contract_step",
            checks["tushare_deepseek_linkage_contract_step"],
            evidence="push gate runs scripts/tushare_deepseek_linkage_contract.py after Bootstrap runtime and before Factor Test Lab",
        ),
        _release_gate_row(
            "tushare_deepseek_linkage_contract_is_local",
            checks["tushare_deepseek_linkage_contract_is_local"],
            evidence="contract ties live_light and search quant projection to safe Tushare/DeepSeek ledger boundaries without provider/model execution",
        ),
        _release_gate_row(
            "factor_test_lab_contract_exists",
            checks["factor_test_lab_contract_exists"],
            evidence=_relative_path(FACTOR_TEST_LAB_CONTRACT_PATH),
        ),
        _release_gate_row(
            "factor_test_lab_contract_step",
            checks["factor_test_lab_contract_step"],
            evidence="push gate runs scripts/factor_test_lab_contract.py after Tushare acceptance and before motion QA",
        ),
        _release_gate_row(
            "factor_test_lab_contract_is_local",
            checks["factor_test_lab_contract_is_local"],
            evidence="contract keeps LTG-03 light metrics, small-pool readiness, and production QA separate from provider-backed/full-market validation",
        ),
        _release_gate_row(
            "factor_test_production_stage_scope_manifest_is_local",
            checks["factor_test_production_stage_scope_manifest_is_local"],
            evidence="contract exposes LTG-03 production stage scope while provider-backed small-pool, full-market validation, and production completion remain pending",
        ),
        _release_gate_row(
            "factor_universe_contract_exists",
            checks["factor_universe_contract_exists"],
            evidence=_relative_path(FACTOR_UNIVERSE_CONTRACT_PATH),
        ),
        _release_gate_row(
            "factor_universe_contract_step",
            checks["factor_universe_contract_step"],
            evidence="push gate runs scripts/factor_universe_contract.py after Factor Test Lab and before DeepSeek governance",
        ),
        _release_gate_row(
            "factor_universe_contract_is_local",
            checks["factor_universe_contract_is_local"],
            evidence="contract keeps LTG-04 read-plan readiness separate from worker batch execution, rank/zscore, neutralization, full-pool validation, and production factor universe completion",
        ),
        _release_gate_row(
            "deepseek_governance_contract_exists",
            checks["deepseek_governance_contract_exists"],
            evidence=_relative_path(DEEPSEEK_GOVERNANCE_CONTRACT_PATH),
        ),
        _release_gate_row(
            "deepseek_governance_contract_step",
            checks["deepseek_governance_contract_step"],
            evidence="push gate runs scripts/deepseek_governance_contract.py after Factor Test Lab and before Candidate Radar",
        ),
        _release_gate_row(
            "deepseek_governance_contract_is_local",
            checks["deepseek_governance_contract_is_local"],
            evidence="contract keeps LTG-07 manual/sanitizer governance separate from provider benchmark, response_format enforcement, retry/repair, and production automatic explanation",
        ),
        _release_gate_row(
            "next_session_map_contract_exists",
            checks["next_session_map_contract_exists"],
            evidence=_relative_path(NEXT_SESSION_MAP_CONTRACT_PATH),
        ),
        _release_gate_row(
            "next_session_map_contract_step",
            checks["next_session_map_contract_step"],
            evidence="push gate runs scripts/next_session_map_contract.py after DeepSeek governance and before Candidate Radar",
        ),
        _release_gate_row(
            "next_session_map_contract_is_local",
            checks["next_session_map_contract_is_local"],
            evidence="contract keeps LTG-08 ECharts payload, interaction readiness, and frontend read-only boundaries separate from browser QA, Streamlit parity, and production replacement",
        ),
        _release_gate_row(
            "candidate_radar_contract_exists",
            checks["candidate_radar_contract_exists"],
            evidence=_relative_path(CANDIDATE_RADAR_CONTRACT_PATH),
        ),
        _release_gate_row(
            "candidate_radar_contract_step",
            checks["candidate_radar_contract_step"],
            evidence="push gate runs scripts/candidate_radar_contract.py after Factor Test Lab and before motion QA",
        ),
        _release_gate_row(
            "candidate_radar_contract_is_local",
            checks["candidate_radar_contract_is_local"],
            evidence="contract keeps LTG-13 quick scan, full/deep plans, no-feature-loss QA, and legacy-retirement blockers separate from production radar replacement",
        ),
        _release_gate_row(
            "candidate_radar_browser_qa_runbook_exists",
            checks["candidate_radar_browser_qa_runbook_exists"],
            evidence=_relative_path(CANDIDATE_RADAR_BROWSER_QA_RUNBOOK_PATH),
        ),
        _release_gate_row(
            "candidate_radar_browser_qa_runbook_step",
            checks["candidate_radar_browser_qa_runbook_step"],
            evidence="push gate runs scripts/candidate_radar_browser_qa_runbook.py after Candidate Radar contract and before motion QA",
        ),
        _release_gate_row(
            "candidate_radar_browser_qa_runbook_is_local",
            checks["candidate_radar_browser_qa_runbook_is_local"],
            evidence="runbook pins #candidates browser QA route/viewports while keeping visual/performance execution pending",
        ),
        _release_gate_row(
            "storage_contract_exists",
            checks["storage_contract_exists"],
            evidence=_relative_path(STORAGE_CONTRACT_PATH),
        ),
        _release_gate_row(
            "storage_contract_step",
            checks["storage_contract_step"],
            evidence="push gate runs scripts/storage_contract.py after Candidate Radar and before motion QA",
        ),
        _release_gate_row(
            "storage_contract_is_local",
            checks["storage_contract_is_local"],
            evidence="contract keeps LTG-05 preflights/dry-runs/query policies separate from physical storage migration and production completion",
        ),
        _release_gate_row(
            "worker_contract_exists",
            checks["worker_contract_exists"],
            evidence=_relative_path(WORKER_CONTRACT_PATH),
        ),
        _release_gate_row(
            "worker_contract_step",
            checks["worker_contract_step"],
            evidence="push gate runs scripts/worker_contract.py after Storage and before motion QA",
        ),
        _release_gate_row(
            "worker_contract_is_local",
            checks["worker_contract_is_local"],
            evidence="contract keeps LTG-06 dispatch plans, blocker audits, healthcheck QA, and activation review separate from process start and production worker completion",
        ),
        _release_gate_row(
            "tauri_desktop_contract_exists",
            checks["tauri_desktop_contract_exists"],
            evidence=_relative_path(TAURI_DESKTOP_CONTRACT_PATH),
        ),
        _release_gate_row(
            "tauri_desktop_contract_step",
            checks["tauri_desktop_contract_step"],
            evidence="push gate runs scripts/tauri_desktop_contract.py after Worker and before motion QA",
        ),
        _release_gate_row(
            "tauri_desktop_contract_is_local",
            checks["tauri_desktop_contract_is_local"],
            evidence="contract keeps LTG-09 Tauri preflight/runtime/offline/package QA separate from build execution, packaged runtime validation, signing/notarization, and production desktop completion",
        ),
        _release_gate_row(
            "streamlit_legacy_contract_exists",
            checks["streamlit_legacy_contract_exists"],
            evidence=_relative_path(STREAMLIT_LEGACY_CONTRACT_PATH),
        ),
        _release_gate_row(
            "streamlit_legacy_contract_step",
            checks["streamlit_legacy_contract_step"],
            evidence="push gate runs scripts/streamlit_legacy_contract.py after Tauri desktop and before motion QA",
        ),
        _release_gate_row(
            "streamlit_legacy_contract_is_local",
            checks["streamlit_legacy_contract_is_local"],
            evidence="contract keeps LTG-10 legacy/admin/debug fallback, ordinary workflow blockers, no-feature-cut requirements, and no Streamlit execution separate from full retirement",
        ),
        _release_gate_row(
            "trade_isolation_contract_exists",
            checks["trade_isolation_contract_exists"],
            evidence=_relative_path(TRADE_ISOLATION_CONTRACT_PATH),
        ),
        _release_gate_row(
            "trade_isolation_contract_step",
            checks["trade_isolation_contract_step"],
            evidence="push gate runs scripts/trade_isolation_contract.py after Streamlit legacy and before motion QA",
        ),
        _release_gate_row(
            "trade_isolation_contract_is_local",
            checks["trade_isolation_contract_is_local"],
            evidence="contract keeps LTG-12 real trading, broker/order execution, holdings mutation, and action mutation separate from research/cache/task UI",
        ),
        _release_gate_row(
            "motion_viewport_qa_contract_exists",
            checks["motion_viewport_qa_contract_exists"],
            evidence=_relative_path(MOTION_VIEWPORT_QA_CONTRACT_PATH),
        ),
        _release_gate_row(
            "motion_viewport_qa_contract_step",
            checks["motion_viewport_qa_contract_step"],
            evidence="push gate runs scripts/motion_viewport_qa_contract.py before diff/secret checks",
        ),
        _release_gate_row(
            "motion_viewport_qa_contract_is_local_static",
            checks["motion_viewport_qa_contract_is_local_static"],
            evidence="contract declares visual QA and browser performance remain pending",
        ),
        _release_gate_row(
            "motion_browser_qa_runbook_exists",
            checks["motion_browser_qa_runbook_exists"],
            evidence=_relative_path(MOTION_BROWSER_QA_RUNBOOK_PATH),
        ),
        _release_gate_row(
            "motion_browser_qa_runbook_step",
            checks["motion_browser_qa_runbook_step"],
            evidence="push gate runs scripts/motion_browser_qa_runbook.py before diff/secret checks",
        ),
        _release_gate_row(
            "motion_browser_qa_runbook_is_local_static",
            checks["motion_browser_qa_runbook_is_local_static"],
            evidence="runbook declares no browser execution, no artifact writes, no external calls, and pending visual/performance QA",
        ),
        _release_gate_row(
            "secret_keyword_review_contract_exists",
            checks["secret_keyword_review_contract_exists"],
            evidence=_relative_path(SECRET_KEYWORD_REVIEW_CONTRACT_PATH),
        ),
        _release_gate_row(
            "secret_keyword_review_contract_step",
            checks["secret_keyword_review_contract_step"],
            evidence="push gate runs scripts/secret_keyword_review_contract.py after high-risk secret scan",
        ),
        _release_gate_row(
            "secret_keyword_review_contract_is_structured",
            checks["secret_keyword_review_contract_is_structured"],
            evidence="contract emits category counts and suppresses raw matched source lines",
        ),
        _release_gate_row(
            "uses_project_venv_python",
            checks["uses_project_venv_python"],
            evidence='PYTHON_BIN defaults to .venv/bin/python',
        ),
        _release_gate_row(
            "refuses_missing_project_python",
            checks["refuses_missing_project_python"],
            evidence="missing project Python fails before tests",
        ),
        _release_gate_row("python_unittest", checks["python_unittest_step"], evidence="-m unittest discover -s tests"),
        _release_gate_row("desktop_build", checks["desktop_build_step"], evidence="cd desktop && npm run build"),
        _release_gate_row("command_center_3_smoke", checks["smoke_step"], evidence="scripts/smoke_3_0.sh"),
        _release_gate_row("diff_whitespace_check", checks["diff_check_step"], evidence="git diff --check"),
        _release_gate_row("high_risk_secret_scan", checks["high_risk_secret_scan_step"], evidence="secret_high_risk_scan"),
        _release_gate_row("keyword_review_scan", checks["keyword_review_scan_step"], evidence="keyword scan for review"),
        _release_gate_row(
            "keyword_review_raw_lines_suppressed",
            checks["keyword_review_raw_lines_suppressed"],
            evidence="push gate reports keyword count and delegates details to structured contract",
        ),
        _release_gate_row("generated_artifact_scan", checks["generated_artifact_scan_step"], evidence="artifact_scan + git ls-files"),
        _release_gate_row("release_readiness_report", checks["release_report_step"], evidence="PUSH_GATE_REPORT_PATH"),
        _release_gate_row(
            "clean_worktree_after_report",
            checks["clean_worktree_after_report"],
            evidence="Release readiness report runs before clean worktree check",
        ),
        _release_gate_row(
            "local_push_gate_run_receipt_step",
            checks["local_push_gate_run_receipt_step"],
            evidence="push gate writes ignored .stock_ming_3 release receipt only after local checks pass",
        ),
        _release_gate_row(
            "local_push_gate_run_receipt_after_clean",
            checks["local_push_gate_run_receipt_after_clean"],
            evidence="ignored local push gate receipt is written after clean worktree check and before final PASS",
        ),
        _release_gate_row("no_git_push", checks["no_git_push"], evidence="script contains no git push"),
        _release_gate_row("no_git_add_dot", checks["no_git_add_dot"], evidence="script contains no git add ."),
        _release_gate_row("does_not_call_tushare", checks["does_not_call_tushare"], evidence="no provider invocation markers"),
        _release_gate_row("does_not_call_deepseek", checks["does_not_call_deepseek"], evidence="no model invocation markers"),
        _release_gate_row("does_not_call_github_api", checks["does_not_call_github_api"], evidence="no GitHub API markers"),
        _release_gate_row("does_not_execute_trades", checks["does_not_execute_trades"], evidence="no live trade markers"),
        _release_gate_row(
            "local_gate_ready",
            local_gate_ready,
            evidence="local push gate contract is statically complete" if local_gate_ready else "local push gate contract has blockers",
        ),
        _release_gate_row(
            "ci_mirror_not_proven",
            ci_mirror_ready,
            evidence=".github workflows do not mirror scripts/push_gate_3_0.sh" if not ci_mirror_ready else "CI mirrors local push gate",
            status_override="pending" if not ci_mirror_ready else None,
        ),
        _release_gate_row(
            "false_positive_allowlist_review_pending",
            false_positive_allowlist_review_ready,
            evidence="secret/artifact review allowlists still require periodic human review",
            production_blocker=False,
            status_override="pending",
        ),
    ]
    blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    soft_blockers = [row["criterion"] for row in rows if row.get("status") == "pending" and not row.get("production_blocker")]
    release_gate_complete = local_gate_ready and ci_mirror_ready and false_positive_allowlist_review_ready
    if release_gate_complete:
        release_gate_status = "release_gate_ready"
    elif local_gate_ready and ci_mirror_ready:
        release_gate_status = "local_gate_ready_allowlist_review_pending"
    elif local_gate_ready:
        release_gate_status = "local_gate_ready_ci_mirror_pending"
    else:
        release_gate_status = "local_gate_blocked"
    audit = {
        "schema_version": RELEASE_GATE_SCHEMA_VERSION,
        "status": release_gate_status,
        "scope": "local_static_push_gate_contract_not_ci_status",
        "local_gate_ready": local_gate_ready,
        "release_gate_complete": release_gate_complete,
        "ci_mirror_ready": ci_mirror_ready,
        "ci_mirror_detected": ci_mirror_ready,
        "false_positive_allowlist_review_ready": false_positive_allowlist_review_ready,
        "provider_calls_triggered": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": checks["does_not_execute_trades"],
        "does_not_modify_strategy_action": True,
        "optional_report_is_local_only": checks["release_report_step"],
        "report_path_must_not_be_tracked": True,
        "workflow_count": len(workflow_rows),
        "github_workflow_files": [str(row.get("workflow")) for row in workflow_rows],
        "check_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "soft_blocker_count": len(soft_blockers),
        "blockers": blockers,
        "soft_blockers": soft_blockers,
        **checks,
    }
    return audit, rows, workflow_rows


def _ci_notification_triage_contract(
    release_gate_readiness_audit: Mapping[str, Any],
    release_gate_workflow_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    push_gate_workflow = next(
        (
            row
            for row in release_gate_workflow_rows
            if str(row.get("workflow") or "").endswith("command-center-3-push-gate.yml")
        ),
        {},
    )
    local_gate_ready = release_gate_readiness_audit.get("local_gate_ready") is True
    ci_mirror_ready = release_gate_readiness_audit.get("ci_mirror_ready") is True
    workflow_declared = bool(push_gate_workflow)
    workflow_mirrors_local_gate = bool(push_gate_workflow.get("mirrors_local_push_gate"))
    workflow_calls_github_api = bool(push_gate_workflow.get("github_api_call_detected"))
    remote_logs_required = True
    remote_actions_status_known = False
    rows = [
        _release_gate_row(
            "email_notification_is_remote_ci_signal",
            True,
            evidence="GitHub Actions failure email is a remote workflow signal, not local worktree status.",
            production_blocker=False,
        ),
        _release_gate_row(
            "local_gate_contract_available",
            local_gate_ready,
            evidence=f"release_gate_status={release_gate_readiness_audit.get('status')}",
        ),
        _release_gate_row(
            "push_gate_workflow_declared",
            workflow_declared,
            evidence=push_gate_workflow.get("workflow") or ".github/workflows/command-center-3-push-gate.yml",
        ),
        _release_gate_row(
            "push_gate_workflow_mirrors_local_script",
            workflow_mirrors_local_gate,
            evidence=f"mirrors_local_push_gate={workflow_mirrors_local_gate}; contains_smoke_step={push_gate_workflow.get('contains_smoke_step')}",
        ),
        _release_gate_row(
            "remote_run_logs_required_for_failure_root_cause",
            False,
            evidence="The cache does not call GitHub API or fetch remote run logs; failed step/log text must be supplied from the Actions run page.",
            production_blocker=False,
            status_override="pending_remote_log",
        ),
        _release_gate_row(
            "local_pass_does_not_clear_remote_ci_failure",
            True,
            evidence="A local push gate pass narrows risk but cannot prove the remote runner status.",
            production_blocker=False,
        ),
        _release_gate_row(
            "old_email_does_not_prove_current_head_failed",
            True,
            evidence="Compare email commit sha/date with current HEAD and remote HEAD before treating the notification as current.",
            production_blocker=False,
        ),
        _release_gate_row(
            "ci_triage_calls_no_github_api",
            not workflow_calls_github_api,
            evidence="triage reads local workflow inventory only; it does not use gh, GraphQL, api.github.com, or workflow logs.",
        ),
        _release_gate_row(
            "provider_trade_boundaries_preserved",
            True,
            evidence="CI notification triage does not call providers, run models, refresh data, or execute trades.",
            production_blocker=False,
        ),
    ]
    blocking_rows = [row for row in rows if row.get("production_blocker")]
    pending_rows = [row for row in rows if str(row.get("status") or "").startswith("pending")]
    status = (
        "ci_notification_triage_ready_remote_logs_required"
        if not blocking_rows
        else "ci_notification_triage_blocked"
    )
    contract = {
        "schema_version": CI_NOTIFICATION_TRIAGE_SCHEMA_VERSION,
        "status": status,
        "scope": "local_ci_failure_email_triage_no_github_api",
        "local_gate_ready": local_gate_ready,
        "ci_mirror_ready": ci_mirror_ready,
        "push_gate_workflow_declared": workflow_declared,
        "push_gate_workflow": push_gate_workflow.get("workflow") or ".github/workflows/command-center-3-push-gate.yml",
        "remote_actions_status_known": remote_actions_status_known,
        "remote_failure_logs_available": False,
        "remote_logs_required_for_root_cause": remote_logs_required,
        "can_dismiss_failure_email_without_matching_head_and_logs": False,
        "latest_remote_run_verified_green": False,
        "old_email_may_be_stale": True,
        "local_pass_is_not_ci_status": True,
        "requires_failed_step_name": True,
        "requires_failed_log_excerpt": True,
        "row_count": len(rows),
        "pending_remote_evidence_count": len(pending_rows),
        "blocking_criterion_count": len(blocking_rows),
        "blockers": [row["criterion"] for row in blocking_rows],
        "pending_remote_evidence": [row["criterion"] for row in pending_rows],
        "external_calls_triggered": False,
        "provider_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This is local CI-notification triage. It explains what evidence is needed, but it does not fetch GitHub Actions logs or prove the remote run is green.",
    }
    return contract, rows


def _release_gate_push_readiness_receipt(
    release_gate_readiness_audit: Mapping[str, Any],
    ci_notification_triage_contract: Mapping[str, Any],
    local_push_gate_run_receipt: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    local_gate_ready = release_gate_readiness_audit.get("local_gate_ready") is True
    ci_mirror_ready = release_gate_readiness_audit.get("ci_mirror_ready") is True
    local_run_receipt = _as_dict(local_push_gate_run_receipt)
    fresh_local_gate_run_observed = local_run_receipt.get("fresh_local_gate_run_observed") is True
    remote_actions_status_known = ci_notification_triage_contract.get("remote_actions_status_known") is True
    latest_remote_run_verified_green = ci_notification_triage_contract.get("latest_remote_run_verified_green") is True
    false_positive_allowlist_review_ready = (
        release_gate_readiness_audit.get("false_positive_allowlist_review_ready") is True
    )
    ready_for_explicit_push_sequence = local_gate_ready and ci_mirror_ready
    rows = [
        _release_gate_row(
            "local_push_gate_contract_ready",
            local_gate_ready,
            evidence=f"release_gate_status={release_gate_readiness_audit.get('status')}",
        ),
        _release_gate_row(
            "ci_mirror_declared",
            ci_mirror_ready,
            evidence=f"workflow_count={release_gate_readiness_audit.get('workflow_count')}",
        ),
        _release_gate_row(
            "fresh_local_gate_run_required_before_push",
            fresh_local_gate_run_observed,
            evidence=(
                f"local receipt head={local_run_receipt.get('head')}; "
                f"current head={local_run_receipt.get('current_head')}; "
                f"head_matches_current={local_run_receipt.get('head_matches_current')}"
            ),
            production_blocker=False,
            status_override="pending_local_gate_run" if not fresh_local_gate_run_observed else None,
        ),
        _release_gate_row(
            "local_gate_pass_not_remote_green",
            True,
            evidence="Local pass and static CI mirror do not prove the latest remote Actions run is green.",
            production_blocker=False,
        ),
        _release_gate_row(
            "remote_actions_status_known",
            remote_actions_status_known,
            evidence="GET /api/audit/cache does not fetch remote Actions run status.",
            production_blocker=False,
            status_override="pending_remote_status" if not remote_actions_status_known else None,
        ),
        _release_gate_row(
            "latest_remote_run_verified_green",
            latest_remote_run_verified_green,
            evidence="Remote green requires matching pushed commit and Actions run evidence.",
            production_blocker=False,
            status_override="pending_remote_status" if not latest_remote_run_verified_green else None,
        ),
        _release_gate_row(
            "failure_email_requires_commit_match_and_logs",
            True,
            evidence="Failure emails must be matched by commit/head, failed step name, and safe log excerpt.",
            production_blocker=False,
        ),
        _release_gate_row(
            "optional_report_not_ci_status",
            True,
            evidence="PUSH_GATE_REPORT_PATH report is local evidence only and not CI status.",
            production_blocker=False,
        ),
        _release_gate_row(
            "periodic_allowlist_review_pending",
            false_positive_allowlist_review_ready,
            evidence="Secret/artifact allowlists remain a periodic human review item.",
            production_blocker=False,
            status_override="pending_human_review" if not false_positive_allowlist_review_ready else None,
        ),
        _release_gate_row(
            "cache_receipt_calls_no_github_api",
            True,
            evidence="Receipt reads local audit contracts only; it does not use gh, GraphQL, api.github.com, or workflow logs.",
        ),
        _release_gate_row(
            "cache_receipt_calls_no_external_providers",
            True,
            evidence="Receipt does not call Tushare, DeepSeek, GitHub, Redis, or broker APIs.",
        ),
        _release_gate_row(
            "cache_receipt_does_not_push",
            True,
            evidence="GET cache emits readiness data only; git push remains an explicit user/operator action.",
        ),
        _release_gate_row(
            "no_git_add_dot_policy_visible",
            release_gate_readiness_audit.get("no_git_add_dot") is True,
            evidence="push gate static audit checks script contains no git add .",
        ),
        _release_gate_row(
            "no_real_trading_boundary_visible",
            release_gate_readiness_audit.get("does_not_execute_trades") is True,
            evidence="push gate static audit contains no live trade markers.",
        ),
    ]
    blocking_rows = [row for row in rows if row.get("production_blocker")]
    pending_rows = [row for row in rows if str(row.get("status") or "").startswith("pending")]
    if blocking_rows:
        status = "push_readiness_receipt_blocked"
    elif ready_for_explicit_push_sequence and fresh_local_gate_run_observed:
        status = "push_readiness_receipt_ready_local_gate_passed_remote_ci_pending"
    elif ready_for_explicit_push_sequence:
        status = "push_readiness_receipt_ready_local_gate_required_remote_ci_pending"
    else:
        status = "push_readiness_receipt_pending"
    receipt = {
        "schema_version": PUSH_READINESS_RECEIPT_SCHEMA_VERSION,
        "status": status,
        "scope": "local_push_readiness_receipt_no_command_or_github_api",
        "local_receipt_ready": not blocking_rows,
        "ready_for_explicit_local_gate_then_push": ready_for_explicit_push_sequence,
        "allowed_next_step": "run_scripts_push_gate_3_0_then_git_push_then_inspect_remote_actions_if_needed",
        "not_allowed_next_steps": [
            "treat local gate pass as remote Actions green",
            "treat static CI mirror as latest remote run evidence",
            "dismiss failure email without matching commit/head and logs",
            "fetch GitHub logs from GET /api/audit/cache",
            "run Tushare/DeepSeek/GitHub from page render",
            "execute real trading during release gate",
            "use git add .",
            "push when scripts/push_gate_3_0.sh fails",
        ],
        "missing_evidence_items": (
            ([] if fresh_local_gate_run_observed else ["fresh_local_push_gate_command_output"])
            + [
                "matching_remote_actions_run_status",
                "latest_remote_run_green_evidence",
                "periodic_secret_artifact_allowlist_review",
            ]
        ),
        "local_gate_contract_ready": local_gate_ready,
        "ci_mirror_ready": ci_mirror_ready,
        "fresh_local_gate_run_observed": fresh_local_gate_run_observed,
        "local_push_gate_run_receipt": local_run_receipt,
        "local_push_gate_run_receipt_status": local_run_receipt.get("status"),
        "local_push_gate_run_receipt_head": local_run_receipt.get("head"),
        "local_push_gate_run_receipt_current_head": local_run_receipt.get("current_head"),
        "local_push_gate_run_receipt_head_matches_current": local_run_receipt.get("head_matches_current") is True,
        "remote_actions_status_known": remote_actions_status_known,
        "latest_remote_run_verified_green": latest_remote_run_verified_green,
        "can_clear_failure_email_without_matching_head_and_logs": False,
        "old_failure_email_may_be_stale": ci_notification_triage_contract.get("old_email_may_be_stale") is True,
        "local_gate_pass_is_not_ci_status": True,
        "static_ci_mirror_is_not_ci_status": True,
        "optional_report_is_not_ci_status": True,
        "periodic_allowlist_review_ready": false_positive_allowlist_review_ready,
        "row_count": len(rows),
        "pending_evidence_count": len(pending_rows),
        "blocking_criterion_count": len(blocking_rows),
        "blockers": [row["criterion"] for row in blocking_rows],
        "pending_evidence": [row["criterion"] for row in pending_rows],
        "did_not_push": True,
        "git_add_dot_used": False,
        "external_calls_triggered": False,
        "provider_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "call_ledger": [
            {
                "api": "local_release_gate_push_readiness_receipt",
                "source": "local release gate, local push gate run receipt, and CI notification triage contracts",
                "call_status": "cache_read",
                "fresh_local_gate_run_observed": fresh_local_gate_run_observed,
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
        "note": "This receipt selects the safe push sequence. It does not run the gate, call GitHub, push commits, or prove remote CI is green.",
    }
    return receipt, rows


def _release_gate_stage_scope_rows(
    release_gate_readiness_audit: Mapping[str, Any],
    release_gate_push_readiness_receipt: Mapping[str, Any],
    ci_notification_triage_contract: Mapping[str, Any],
    local_push_gate_run_receipt: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    local_gate_ready = release_gate_readiness_audit.get("local_gate_ready") is True
    ci_mirror_ready = release_gate_readiness_audit.get("ci_mirror_ready") is True
    for_push_ready = release_gate_push_readiness_receipt.get("ready_for_explicit_local_gate_then_push") is True
    fresh_local_gate_run_observed = (
        release_gate_push_readiness_receipt.get("fresh_local_gate_run_observed") is True
        or _as_dict(local_push_gate_run_receipt).get("fresh_local_gate_run_observed") is True
    )
    rows: list[dict[str, Any]] = []
    for stage_key in sorted(REQUIRED_RELEASE_GATE_STAGE_KEYS):
        stage_complete = (
            (stage_key == "local_push_gate_static_contract" and local_gate_ready)
            or (stage_key == "ci_mirror_workflow_contract" and ci_mirror_ready)
        )
        if stage_key == "fresh_local_gate_command_run":
            stage_complete = fresh_local_gate_run_observed
        rows.append(
            {
                "stage_key": stage_key,
                "stage_label": RELEASE_GATE_STAGE_LABELS[stage_key],
                "scope": RELEASE_GATE_STAGE_SCOPE,
                "current_status": "stage_complete" if stage_complete else "local_static_or_pending_evidence",
                "target_status": "fresh_local_gate_or_remote_ci_evidence_required",
                "required_before_release_push": True,
                "local_static_contract_ready": local_gate_ready,
                "ci_mirror_ready": ci_mirror_ready,
                "ready_for_explicit_push_sequence": for_push_ready,
                "fresh_local_gate_run_observed": fresh_local_gate_run_observed,
                "local_push_gate_receipt_head": _as_dict(local_push_gate_run_receipt).get("head", ""),
                "local_push_gate_receipt_current_head": _as_dict(local_push_gate_run_receipt).get("current_head", ""),
                "remote_actions_status_known": False,
                "latest_remote_run_verified_green": False,
                "failure_email_has_matching_head_and_logs": False,
                "can_dismiss_failure_email_without_matching_head_and_logs": False,
                "periodic_allowlist_review_ready": False,
                "release_report_written_by_cache": False,
                "release_report_is_ci_status": False,
                "release_gate_complete": False,
                "stage_complete": stage_complete,
                "did_not_push": True,
                "git_add_dot_used": False,
                "github_api_called": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "missing_evidence": [
                    "fresh scripts/push_gate_3_0.sh output for current HEAD",
                    "matching remote Actions run for pushed commit",
                    "latest remote Actions green evidence",
                    "safe failure log excerpt when email reports a failure",
                    "periodic secret/artifact allowlist review",
                    "explicit user/operator push approval",
                ],
            }
        )
    return rows


def _motion_source(path: str) -> str:
    return _read_local_text(DESKTOP_SRC_DIR / path)


def _motion_row(
    criterion: str,
    passed: bool,
    *,
    evidence: str,
    production_blocker: bool = True,
    status_override: str | None = None,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status_override or ("passed" if passed else "blocked"),
        "passed": passed,
        "evidence": evidence,
        "production_blocker": production_blocker and not passed,
    }


def _motion_clarity_readiness_audit() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    styles = _motion_source("styles.css")
    app = _motion_source("App.tsx")
    layout = _motion_source("components/Layout.tsx")
    packet_card = _motion_source("components/PacketCard.tsx")
    metric_grid = _motion_source("components/MetricGrid.tsx")
    status_badge = _motion_source("components/StatusBadge.tsx")
    state_rail = _motion_source("components/StateClarityRail.tsx")
    page_state = _motion_source("components/PageStateBanner.tsx")
    task_panel = _motion_source("components/TaskStatusPanel.tsx")
    task_receipt = _motion_source("components/TaskLaunchReceipt.tsx")
    next_chart = _motion_source("components/NextSessionChart.tsx")
    candidate_radar = _motion_source("routes/CandidateRadar.tsx")
    motion_viewport_qa_contract = _read_local_text(MOTION_VIEWPORT_QA_CONTRACT_PATH)
    motion_browser_qa_runbook = _read_local_text(MOTION_BROWSER_QA_RUNBOOK_PATH)
    audited_text = "\n".join(
        [
            styles,
            app,
            layout,
            packet_card,
            metric_grid,
            status_badge,
            state_rail,
            page_state,
            task_panel,
            task_receipt,
            next_chart,
            candidate_radar,
        ]
    )
    token_markers = (
        "--motion-duration-fast",
        "--motion-duration-panel",
        "--motion-duration-route",
        "--motion-duration-chart",
        "--motion-duration-state",
        "--motion-duration-clarity",
        "--motion-duration-focus",
        "--motion-duration-hierarchy",
        "--motion-ease-emphasized",
    )
    keyframe_markers = (
        "@keyframes cc-route-reveal",
        "@keyframes cc-surface-rise",
        "@keyframes cc-state-clarity",
        "@keyframes cc-chart-clarity",
        "@keyframes cc-clarity-sweep",
        "@keyframes cc-focus-settle",
        "@keyframes cc-hierarchy-focus",
        "@keyframes cc-keynote-focus-sweep",
        "@keyframes cc-context-sweep",
        "@keyframes cc-status-settle",
        "@keyframes cc-phase-confirm",
    )
    task_polling_interval_is_bounded = "window.setInterval" in task_panel and "getTask(taskId)" in task_panel and "window.clearInterval" in task_panel
    checks = {
        "motion_tokens_present": all(marker in styles for marker in token_markers),
        "finite_keyframes_present": all(marker in styles for marker in keyframe_markers),
        "single_iteration_motion": "animation-iteration-count: 1;" in styles
        and "animation-fill-mode: both" in styles,
        "reduced_motion_css": "@media (prefers-reduced-motion: reduce)" in styles
        and "animation-duration: 1ms !important" in styles
        and "transition-duration: 1ms !important" in styles
        and "transform: none !important" in styles,
        "state_clarity_rail_present": "data-step-state={step.state}" in state_rail
        and "StateClarityRail" in page_state
        and "StateClarityRail" in task_panel
        and "StateClarityRail" in task_receipt,
        "route_and_surface_staging": "route-stage" in app
        and 'key={route}' in app
        and "motion-surface" in packet_card
        and "motion-surface" in metric_grid,
        "visual_hierarchy_clarity_cue": 'data-motion-purpose="visual_hierarchy_clarity"' in packet_card
        and 'data-motion-purpose="visual_hierarchy_clarity"' in metric_grid
        and "data-metric-tone={item.tone ?? \"neutral\"}" in metric_grid
        and '.motion-surface[data-motion-purpose="visual_hierarchy_clarity"]::before' in styles
        and "@keyframes cc-hierarchy-focus" in styles
        and "pointer-events: none" in styles
        and "isolation: isolate" in styles,
        "keynote_focus_sweep_cue": '.motion-surface[data-motion-purpose="visual_hierarchy_clarity"]::after' in styles
        and "@keyframes cc-keynote-focus-sweep" in styles
        and "linear-gradient(105deg" in styles
        and '.motion-surface[data-motion-purpose="visual_hierarchy_clarity"] > *' in styles
        and "z-index: 1" in styles
        and "@media (prefers-reduced-motion: reduce)" in styles,
        "packet_status_clarity_cue": 'data-motion-scope="packet_status_clarity"' in packet_card
        and "function statusTone" in packet_card
        and "data-status-tone={tone}" in packet_card
        and 'StatusBadge label={status} tone={tone}' in packet_card
        and '.packet-card[data-motion-scope="packet_status_clarity"][data-status-tone="good"]' in styles
        and '.packet-card[data-motion-scope="packet_status_clarity"][data-status-tone="warn"]' in styles
        and '.packet-card[data-motion-scope="packet_status_clarity"][data-status-tone="bad"]' in styles,
        "navigation_context_cue": 'aria-current={active === route.key ? "page" : undefined}' in layout
        and 'data-route-active={active === route.key ? "true" : "false"}' in layout
        and 'className="nav-label"' in layout
        and ".sidebar button.nav-active::after" in styles
        and "@keyframes cc-context-sweep" in styles,
        "status_badge_context_cue": "data-status-tone={tone}" in status_badge
        and ".status-badge::before" in styles
        and "@keyframes cc-status-settle" in styles,
        "task_progress_motion_present": "task-panel--${task.status}" in task_panel
        and "data-task-state={task.status}" in task_panel
        and "task-progress" in task_panel
        and "task-progress" in styles,
        "task_phase_confirmation_cue": 'data-motion-scope="task_phase_clarity"' in task_panel
        and 'data-motion-purpose="state_change_confirmation"' in task_panel
        and '.task-panel[data-motion-purpose="state_change_confirmation"]::after' in styles
        and "@keyframes cc-phase-confirm" in styles,
        "task_receipt_confirmation_cue": 'data-motion-scope="task_receipt_clarity"' in task_receipt
        and 'data-motion-purpose="state_change_confirmation"' in task_receipt
        and "task-panel--receipt" in styles
        and "@keyframes cc-phase-confirm" in styles,
        "cache_refresh_confirmation_cue": 'data-motion-scope="cache_refresh_clarity"' in page_state
        and 'data-motion-purpose="state_change_confirmation"' in page_state
        and '.page-state[data-motion-purpose="state_change_confirmation"]::after' in styles
        and "@keyframes cc-phase-confirm" in styles,
        "chart_reduced_motion_runtime": "useReducedMotionPreference" in next_chart
        and 'window.matchMedia("(prefers-reduced-motion: reduce)")' in next_chart
        and "animation: !reducedMotion" in next_chart
        and "animationDurationUpdate: reducedMotion ? 0 : 260" in next_chart,
        "chart_clarity_scope": 'className="chart-refresh-frame"' in next_chart
        and "data-chart-state={chartMotionState}" in next_chart
        and ".chart-refresh-frame" in styles,
        "radar_clarity_scope": "radarMotionState" in candidate_radar
        and 'className="grid radar-result-cluster"' in candidate_radar
        and "data-radar-state={radarMotionState}" in candidate_radar
        and ".radar-result-cluster" in styles,
        "layout_containment_guard": "contain: layout paint" in styles
        and ".chart-refresh-frame" in styles
        and ".state-clarity-rail" in styles,
        "mobile_responsive_motion_layout": "@media (max-width: 760px)" in styles
        and ".app-shell" in styles
        and "display: block;" in styles
        and ".sidebar nav" in styles
        and "overflow-x: auto;" in styles
        and ".content" in styles
        and "grid-template-columns: minmax(0, 1fr);" in styles
        and "repeat(auto-fit, minmax(118px, 1fr))" in styles,
        "no_timer_or_raf_motion_loop": "setTimeout" not in audited_text
        and "requestAnimationFrame" not in audited_text
        and ("setInterval" not in audited_text or task_polling_interval_is_bounded),
        "no_provider_call_markers": not _script_contains_any(
            audited_text,
            ("tushare_adapter", "deepseek.chat", "gh api", "api.github.com", "curl "),
        ),
        "visual_only_boundary_visible": "candidate radar visual state" in candidate_radar
        and "trade guard" in candidate_radar
        and "图谱交互说明" in next_chart,
        "motion_viewport_qa_contract_ready": "command_center_3_motion_viewport_qa_contract.v1" in motion_viewport_qa_contract
        and "local_static_contract_not_browser_execution" in motion_viewport_qa_contract
        and "visual_qa_complete" in motion_viewport_qa_contract
        and "browser_performance_verified" in motion_viewport_qa_contract,
        "motion_browser_qa_runbook_ready": "command_center_3_motion_browser_qa_runbook.v1" in motion_browser_qa_runbook
        and "local_browser_qa_runbook_not_browser_execution" in motion_browser_qa_runbook
        and "visual_acceptance_criteria" in motion_browser_qa_runbook
        and "PERFORMANCE_BUDGETS" in motion_browser_qa_runbook,
    }
    rows = [
        _motion_row("motion_tokens_present", checks["motion_tokens_present"], evidence=", ".join(token_markers)),
        _motion_row("finite_keyframes_present", checks["finite_keyframes_present"], evidence=", ".join(keyframe_markers)),
        _motion_row("single_iteration_motion", checks["single_iteration_motion"], evidence="animation-iteration-count: 1 + animation-fill-mode: both"),
        _motion_row("reduced_motion_css", checks["reduced_motion_css"], evidence="prefers-reduced-motion disables transform and duration"),
        _motion_row("state_clarity_rail_present", checks["state_clarity_rail_present"], evidence="PageStateBanner / TaskStatusPanel / TaskLaunchReceipt use StateClarityRail"),
        _motion_row("route_and_surface_staging", checks["route_and_surface_staging"], evidence="route-stage + motion-surface"),
        _motion_row("visual_hierarchy_clarity_cue", checks["visual_hierarchy_clarity_cue"], evidence="metric cards and packet cards expose visual_hierarchy_clarity with finite non-interactive cue"),
        _motion_row("keynote_focus_sweep_cue", checks["keynote_focus_sweep_cue"], evidence="visual hierarchy surfaces use a finite keynote-style focus sweep while keeping content above the cue"),
        _motion_row("packet_status_clarity_cue", checks["packet_status_clarity_cue"], evidence="packet cards derive good/warn/bad visual hierarchy from status strings and pass the same tone to StatusBadge"),
        _motion_row("navigation_context_cue", checks["navigation_context_cue"], evidence="aria-current + data-route-active + finite active-nav sweep"),
        _motion_row("status_badge_context_cue", checks["status_badge_context_cue"], evidence="status badges expose data-status-tone and visual dot cue"),
        _motion_row("task_progress_motion_present", checks["task_progress_motion_present"], evidence="task status classes + progress transition"),
        _motion_row("task_phase_confirmation_cue", checks["task_phase_confirmation_cue"], evidence="task panels expose state_change_confirmation cue with finite cc-phase-confirm"),
        _motion_row("task_receipt_confirmation_cue", checks["task_receipt_confirmation_cue"], evidence="task receipts expose state_change_confirmation cue with no task execution side effects"),
        _motion_row("cache_refresh_confirmation_cue", checks["cache_refresh_confirmation_cue"], evidence="page cache states expose state_change_confirmation cue for loading/error/empty boundaries"),
        _motion_row("chart_reduced_motion_runtime", checks["chart_reduced_motion_runtime"], evidence="NextSessionChart runtime reduced-motion check"),
        _motion_row("chart_clarity_scope", checks["chart_clarity_scope"], evidence="chart-refresh-frame and chartMotionState"),
        _motion_row("radar_clarity_scope", checks["radar_clarity_scope"], evidence="radar-result-cluster and radarMotionState"),
        _motion_row("layout_containment_guard", checks["layout_containment_guard"], evidence="contain: layout paint"),
        _motion_row(
            "mobile_responsive_motion_layout",
            checks["mobile_responsive_motion_layout"],
            evidence="mobile breakpoint keeps navigation scrollable and content/state rails readable",
        ),
        _motion_row("no_timer_or_raf_motion_loop", checks["no_timer_or_raf_motion_loop"], evidence="no setTimeout/requestAnimationFrame motion loop; bounded setInterval is task polling only"),
        _motion_row("no_provider_call_markers", checks["no_provider_call_markers"], evidence="audited motion files contain no provider invocation markers"),
        _motion_row("visual_only_boundary_visible", checks["visual_only_boundary_visible"], evidence="motion state labels remain visual-only and trade guarded"),
        _motion_row("motion_viewport_qa_contract_ready", checks["motion_viewport_qa_contract_ready"], evidence="scripts/motion_viewport_qa_contract.py pins routes, viewports, and pending browser QA state"),
        _motion_row("motion_browser_qa_runbook_ready", checks["motion_browser_qa_runbook_ready"], evidence="scripts/motion_browser_qa_runbook.py pins local startup, artifact, visual, and performance QA criteria"),
        _motion_row(
            "desktop_mobile_viewport_visual_qa_pending",
            False,
            evidence="static source audit cannot prove overlap, occlusion, or perceived clarity across viewports",
            production_blocker=False,
            status_override="pending",
        ),
        _motion_row(
            "browser_performance_trace_pending",
            False,
            evidence="static source audit cannot prove runtime frame stability under large packets",
            production_blocker=False,
            status_override="pending",
        ),
    ]
    static_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    soft_blockers = [row["criterion"] for row in rows if row.get("status") == "pending" and not row.get("production_blocker")]
    static_ready = not static_blockers
    audit = {
        "schema_version": MOTION_CLARITY_SCHEMA_VERSION,
        "status": "motion_clarity_static_ready_visual_qa_pending" if static_ready else "motion_clarity_static_blocked",
        "scope": "local_static_source_audit_not_browser_visual_qa",
        "ltg": "LTG-14",
        "static_ready": static_ready,
        "production_motion_complete": False,
        "visual_qa_complete": False,
        "browser_performance_verified": False,
        "row_count": len(rows),
        "passed_count": len([row for row in rows if row.get("status") == "passed"]),
        "blocking_criterion_count": len(static_blockers),
        "soft_blocker_count": len(soft_blockers),
        "blockers": static_blockers,
        "soft_blockers": soft_blockers,
        "audited_files": [
            "desktop/src/styles.css",
            "desktop/src/App.tsx",
            "desktop/src/components/Layout.tsx",
            "desktop/src/components/PacketCard.tsx",
            "desktop/src/components/MetricGrid.tsx",
            "desktop/src/components/StatusBadge.tsx",
            "desktop/src/components/StateClarityRail.tsx",
            "desktop/src/components/PageStateBanner.tsx",
            "desktop/src/components/TaskStatusPanel.tsx",
            "desktop/src/components/TaskLaunchReceipt.tsx",
            "desktop/src/components/NextSessionChart.tsx",
            "desktop/src/routes/CandidateRadar.tsx",
            "scripts/motion_viewport_qa_contract.py",
            "scripts/motion_browser_qa_runbook.py",
        ],
        "cache_only": True,
        "runs_no_commands": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_packets": True,
        "next_action": "run browser viewport and performance QA before calling LTG-14 production motion complete.",
        **checks,
    }
    return audit, rows


def _motion_production_qa_row(
    criterion: str,
    status: str,
    *,
    local_contract_passed: bool,
    production_ready: bool,
    evidence: str,
    next_action: str,
    visual_qa_required: bool = False,
    performance_trace_required: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "local_contract_passed": bool(local_contract_passed),
        "production_ready": bool(production_ready),
        "blocks_production_motion": not bool(production_ready),
        "visual_qa_required": bool(visual_qa_required),
        "performance_trace_required": bool(performance_trace_required),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_packets": True,
    }


def _motion_production_qa_contract(
    motion_clarity_audit: Mapping[str, Any],
    motion_clarity_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows_by_criterion = {str(row.get("criterion")): row for row in motion_clarity_rows}
    static_ready = motion_clarity_audit.get("static_ready") is True

    def _row_passed(criterion: str) -> bool:
        return rows_by_criterion.get(criterion, {}).get("passed") is True

    rows = [
        _motion_production_qa_row(
            "purposeful_motion_tokens",
            "passed" if _row_passed("motion_tokens_present") and _row_passed("finite_keyframes_present") else "blocked",
            local_contract_passed=_row_passed("motion_tokens_present") and _row_passed("finite_keyframes_present"),
            production_ready=_row_passed("motion_tokens_present") and _row_passed("finite_keyframes_present"),
            evidence="duration/easing tokens and finite keyframes define a restrained motion system.",
            next_action="Keep any new motion tied to state clarity, not decoration.",
        ),
        _motion_production_qa_row(
            "state_change_clarity",
            "passed"
            if _row_passed("state_clarity_rail_present")
            and _row_passed("task_phase_confirmation_cue")
            and _row_passed("task_receipt_confirmation_cue")
            and _row_passed("cache_refresh_confirmation_cue")
            else "blocked",
            local_contract_passed=_row_passed("state_clarity_rail_present")
            and _row_passed("task_phase_confirmation_cue")
            and _row_passed("task_receipt_confirmation_cue")
            and _row_passed("cache_refresh_confirmation_cue"),
            production_ready=_row_passed("state_clarity_rail_present")
            and _row_passed("task_phase_confirmation_cue")
            and _row_passed("task_receipt_confirmation_cue")
            and _row_passed("cache_refresh_confirmation_cue"),
            evidence="cache, task, and receipt state transitions expose visible confirmation cues.",
            next_action="Extend the same visual grammar to future heavy-task progress and radar result deltas.",
        ),
        _motion_production_qa_row(
            "chart_and_radar_motion_scope",
            "passed" if _row_passed("chart_clarity_scope") and _row_passed("radar_clarity_scope") else "blocked",
            local_contract_passed=_row_passed("chart_clarity_scope") and _row_passed("radar_clarity_scope"),
            production_ready=_row_passed("chart_clarity_scope") and _row_passed("radar_clarity_scope"),
            evidence="Next-session chart and candidate radar expose state attributes for visual grouping.",
            next_action="Add visual delta review after real browser viewport QA is available.",
        ),
        _motion_production_qa_row(
            "visual_hierarchy_clarity",
            "static_passed_visual_pending"
            if _row_passed("visual_hierarchy_clarity_cue")
            and _row_passed("keynote_focus_sweep_cue")
            and _row_passed("packet_status_clarity_cue")
            else "blocked",
            local_contract_passed=_row_passed("visual_hierarchy_clarity_cue")
            and _row_passed("keynote_focus_sweep_cue")
            and _row_passed("packet_status_clarity_cue"),
            production_ready=False,
            evidence="Metric cards and packet cards expose finite hierarchy cues, keynote-style focus sweep, and matching good/warn/bad visual tone.",
            next_action="Verify dense pages in browser QA so hierarchy cues never obscure warnings, freshness, or row text.",
            visual_qa_required=True,
        ),
        _motion_production_qa_row(
            "reduced_motion_accessibility",
            "passed" if _row_passed("reduced_motion_css") and _row_passed("chart_reduced_motion_runtime") else "blocked",
            local_contract_passed=_row_passed("reduced_motion_css") and _row_passed("chart_reduced_motion_runtime"),
            production_ready=_row_passed("reduced_motion_css") and _row_passed("chart_reduced_motion_runtime"),
            evidence="CSS and ECharts runtime honor reduced-motion preferences.",
            next_action="Keep all future motion behind the same reduced-motion boundary.",
        ),
        _motion_production_qa_row(
            "layout_containment_and_readability",
            "static_passed_visual_pending" if _row_passed("layout_containment_guard") else "blocked",
            local_contract_passed=_row_passed("layout_containment_guard"),
            production_ready=False,
            evidence="static containment markers exist, but overlap/occlusion cannot be proven without viewport execution.",
            next_action="Run desktop/tablet/mobile visual QA for text overlap, warning visibility, and dense-table readability.",
            visual_qa_required=True,
        ),
        _motion_production_qa_row(
            "no_timer_or_raf_motion_loop",
            "passed" if _row_passed("no_timer_or_raf_motion_loop") else "blocked",
            local_contract_passed=_row_passed("no_timer_or_raf_motion_loop"),
            production_ready=_row_passed("no_timer_or_raf_motion_loop"),
            evidence="motion audit allows only bounded task polling, not timer/RAF animation loops.",
            next_action="Keep motion CSS/attribute driven unless a separately reviewed animation runtime is needed.",
        ),
        _motion_production_qa_row(
            "visual_qa_execution_pending",
            "pending_browser_visual_qa",
            local_contract_passed=True,
            production_ready=False,
            evidence="motion viewport matrix is pinned, but a browser run has not marked visual_qa_complete=true.",
            next_action="Execute the pinned route/viewport matrix before production motion completion.",
            visual_qa_required=True,
        ),
        _motion_production_qa_row(
            "browser_qa_runbook_ready",
            "passed" if _row_passed("motion_browser_qa_runbook_ready") else "blocked",
            local_contract_passed=_row_passed("motion_browser_qa_runbook_ready"),
            production_ready=_row_passed("motion_browser_qa_runbook_ready"),
            evidence="local browser QA runbook pins startup, local URLs, artifact policy, visual criteria, and performance budgets.",
            next_action="Use the runbook for the future explicit browser pass; do not mark visual QA complete from the runbook alone.",
        ),
        _motion_production_qa_row(
            "performance_trace_pending",
            "pending_browser_performance_trace",
            local_contract_passed=True,
            production_ready=False,
            evidence="static source audit cannot prove frame stability, layout shift, or interaction smoothness under large packets.",
            next_action="Capture browser performance traces for route transitions, chart updates, task polling, and candidate radar.",
            performance_trace_required=True,
        ),
        _motion_production_qa_row(
            "provider_and_trade_isolation",
            "passed"
            if _row_passed("no_provider_call_markers") and _row_passed("visual_only_boundary_visible")
            else "blocked",
            local_contract_passed=_row_passed("no_provider_call_markers") and _row_passed("visual_only_boundary_visible"),
            production_ready=_row_passed("no_provider_call_markers") and _row_passed("visual_only_boundary_visible"),
            evidence="motion files contain no provider markers and keep trade guardrails visible.",
            next_action="Do not let visual emphasis imply certainty, urgency, or trade recommendation.",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if not row.get("local_contract_passed")]
    production_blockers = [row["criterion"] for row in rows if row.get("blocks_production_motion")]
    visual_pending = [row["criterion"] for row in rows if row.get("visual_qa_required") and not row.get("production_ready")]
    performance_pending = [
        row["criterion"] for row in rows if row.get("performance_trace_required") and not row.get("production_ready")
    ]
    local_ready = static_ready and not local_blockers
    contract = {
        "schema_version": "command_center_3_motion_production_qa_contract.v1",
        "status": "motion_production_qa_local_ready_visual_perf_pending" if local_ready else "motion_production_qa_blocked",
        "scope": "local_motion_production_qa_contract_not_browser_visual_or_perf_proof",
        "ltg": "LTG-14",
        "design_intent": "state_clarity_first_restrained_keynote_motion",
        "local_motion_qa_ready": local_ready,
        "production_motion_complete": False,
        "visual_qa_complete": False,
        "browser_performance_verified": False,
        "static_ready": static_ready,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "visual_pending_count": len(visual_pending),
        "performance_pending_count": len(performance_pending),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "visual_pending": visual_pending,
        "performance_pending": performance_pending,
        "cache_only": True,
        "runs_no_commands": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_packets": True,
        "note": "This contract organizes LTG-14 production motion acceptance. It does not execute browser visual QA or performance tracing.",
    }
    return contract, rows


def _motion_keynote_roadmap_row(
    phase: str,
    status: str,
    *,
    local_ready: bool,
    production_ready: bool,
    evidence: str,
    next_action: str,
    priority: str,
    visual_qa_required: bool = False,
    performance_trace_required: bool = False,
    browser_review_required: bool = False,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "priority": priority,
        "local_ready": bool(local_ready),
        "production_ready": bool(production_ready),
        "blocks_keynote_motion_promotion": not bool(production_ready),
        "visual_qa_required": bool(visual_qa_required),
        "performance_trace_required": bool(performance_trace_required),
        "browser_review_required": bool(browser_review_required),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_packets": True,
    }


def _motion_keynote_roadmap_audit(
    motion_clarity_audit: Mapping[str, Any],
    motion_production_qa_contract: Mapping[str, Any],
    motion_browser_qa_evidence_contract: Mapping[str, Any],
    motion_browser_qa_review_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    static_ready = motion_clarity_audit.get("static_ready") is True
    local_qa_ready = motion_production_qa_contract.get("local_motion_qa_ready") is True
    browser_evidence_available = int(motion_browser_qa_evidence_contract.get("passing_report_count") or 0) >= 2
    browser_review_ready = motion_browser_qa_review_contract.get("local_browser_qa_review_ready") is True
    visual_promoted = motion_browser_qa_review_contract.get("browser_visual_qa_promoted") is True
    performance_promoted = motion_browser_qa_review_contract.get("browser_performance_promoted") is True
    rows = [
        _motion_keynote_roadmap_row(
            "state_clarity_foundation",
            "passed" if static_ready else "blocked",
            local_ready=static_ready,
            production_ready=static_ready,
            priority="P0",
            evidence="motion_clarity_audit.static_ready covers finite tokens, state rails, route context, status cues, reduced motion, and no timer/RAF loops.",
            next_action="Keep new motion anchored to explicit state changes instead of decoration.",
        ),
        _motion_keynote_roadmap_row(
            "keynote_route_staging",
            "local_ready_browser_review_pending" if local_qa_ready else "blocked",
            local_ready=local_qa_ready,
            production_ready=False,
            priority="P1",
            visual_qa_required=True,
            browser_review_required=True,
            evidence="route-stage, motion-surface, navigation context, and status tone cues exist, but perceived staging quality still needs browser review.",
            next_action="Use the pinned desktop/tablet/mobile route matrix to verify the staging feels clear and never hides warnings.",
        ),
        _motion_keynote_roadmap_row(
            "chart_and_radar_delta_choreography",
            "local_scope_ready_browser_review_pending" if local_qa_ready else "blocked",
            local_ready=local_qa_ready,
            production_ready=False,
            priority="P1",
            visual_qa_required=True,
            browser_review_required=True,
            evidence="Next-session chart and Candidate Radar expose visual state scopes; local reports cannot yet promote chart/radar delta choreography.",
            next_action="Review chart updates and radar result deltas in default and reduced-motion runs before promotion.",
        ),
        _motion_keynote_roadmap_row(
            "task_feedback_microinteractions",
            "local_ready_browser_review_pending" if local_qa_ready else "blocked",
            local_ready=local_qa_ready,
            production_ready=False,
            priority="P2",
            visual_qa_required=True,
            browser_review_required=True,
            evidence="task panels, task receipts, and cache refresh cues use state_change_confirmation; browser review must confirm they clarify rather than distract.",
            next_action="Verify task accepted/running/success/failure cues with dense audit pages and reduced-motion mode.",
        ),
        _motion_keynote_roadmap_row(
            "dense_data_readability",
            "pending_browser_visual_qa",
            local_ready=local_qa_ready,
            production_ready=False,
            priority="P1",
            visual_qa_required=True,
            browser_review_required=True,
            evidence="static containment exists, but dense tables/cards still require viewport checks for overlap, clipping, and warning visibility.",
            next_action="Run browser QA across data-heavy pages and block any motion that reduces scanability.",
        ),
        _motion_keynote_roadmap_row(
            "visual_hierarchy_cues",
            "local_cue_ready_browser_review_pending" if local_qa_ready else "blocked",
            local_ready=local_qa_ready,
            production_ready=False,
            priority="P1",
            visual_qa_required=True,
            browser_review_required=True,
            evidence="Packet and metric surfaces expose visual_hierarchy_clarity cues and a finite keynote-style focus sweep so status, blockers, and key packet groups are easier to scan without changing data.",
            next_action="Review dense pages in default and reduced-motion browser runs before promoting this as production polish.",
        ),
        _motion_keynote_roadmap_row(
            "reduced_motion_accessibility_promotion",
            "local_artifact_review_pending" if browser_evidence_available else "pending_browser_artifact",
            local_ready=browser_evidence_available,
            production_ready=False,
            priority="P0",
            visual_qa_required=True,
            browser_review_required=True,
            evidence=f"default/reduced local passing reports={motion_browser_qa_evidence_contract.get('passing_report_count')}; review_ready={browser_review_ready}",
            next_action="Review ignored local artifacts, then require durable evidence before any production accessibility claim.",
        ),
        _motion_keynote_roadmap_row(
            "performance_trace_promotion",
            "pending_performance_trace_promotion",
            local_ready=browser_evidence_available,
            production_ready=False,
            priority="P0",
            performance_trace_required=True,
            browser_review_required=True,
            evidence=f"browser_performance_verified={motion_browser_qa_evidence_contract.get('browser_performance_verified')}; promoted={performance_promoted}",
            next_action="Promote performance only after reviewed trace evidence shows no layout shift or route/update stalls.",
        ),
        _motion_keynote_roadmap_row(
            "visual_evidence_promotion",
            "pending_visual_promotion",
            local_ready=browser_review_ready,
            production_ready=False,
            priority="P0",
            visual_qa_required=True,
            browser_review_required=True,
            evidence=f"local_browser_qa_review_ready={browser_review_ready}; browser_visual_qa_promoted={visual_promoted}",
            next_action="Keep production_motion_complete=false until visual QA promotion is explicit and durable.",
        ),
        _motion_keynote_roadmap_row(
            "no_trade_urgency_boundary",
            "passed",
            local_ready=True,
            production_ready=True,
            priority="P0",
            evidence="Motion contracts remain visual-only and keep provider/model/trade/action boundaries false.",
            next_action="Do not use motion to imply certainty, urgency, buy/sell pressure, or hidden priority.",
        ),
    ]
    blockers = [str(row.get("phase")) for row in rows if row.get("blocks_keynote_motion_promotion")]
    visual_required = [str(row.get("phase")) for row in rows if row.get("visual_qa_required")]
    performance_required = [str(row.get("phase")) for row in rows if row.get("performance_trace_required")]
    review_required = [str(row.get("phase")) for row in rows if row.get("browser_review_required")]
    roadmap_ready = static_ready and local_qa_ready
    contract = {
        "schema_version": "command_center_3_motion_keynote_roadmap_audit.v1",
        "status": "motion_keynote_roadmap_local_ready_promotion_pending" if roadmap_ready else "motion_keynote_roadmap_blocked",
        "scope": "local_keynote_motion_roadmap_not_browser_execution",
        "ltg": "LTG-14",
        "design_target": "apple_keynote_grade_clarity_restrained_motion",
        "roadmap_ready": roadmap_ready,
        "production_motion_complete": False,
        "visual_qa_complete": False,
        "browser_performance_verified": False,
        "browser_visual_qa_promoted": False,
        "browser_performance_promoted": False,
        "durable_ci_evidence_complete": False,
        "row_count": len(rows),
        "promotion_blocker_count": len(blockers),
        "visual_qa_required_count": len(visual_required),
        "performance_trace_required_count": len(performance_required),
        "browser_review_required_count": len(review_required),
        "promotion_blockers": blockers,
        "visual_qa_required_phases": visual_required,
        "performance_trace_required_phases": performance_required,
        "browser_review_required_phases": review_required,
        "cache_only": True,
        "runs_no_commands": True,
        "opens_no_browser": True,
        "writes_no_artifacts": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_packets": True,
        "note": "This roadmap turns the Apple-keynote-style polish goal into auditable phases. It does not run browser QA, promote local artifacts, or complete production motion.",
    }
    return contract, rows


def _motion_browser_qa_runbook_contract() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    script = _read_local_text(MOTION_BROWSER_QA_RUNBOOK_PATH)
    runner_script = _read_local_text(MOTION_BROWSER_QA_RUNNER_PATH)
    route_specs = [
        ("#home", "Command Center", "page staging and status summary clarity"),
        ("#next", "Next Session Map", "chart update clarity and reduced-motion chart updates"),
        ("#candidates", "Candidate Radar", "radar result cluster and runtime-budget visibility"),
        ("#tasks", "Task Monitor", "task phase confirmation and progress readability"),
        ("#audit", "Call Ledger Audit", "motion audit rows and warning density"),
    ]
    viewport_specs = [
        ("desktop", 1440, 900),
        ("laptop", 1280, 800),
        ("tablet", 834, 1112),
        ("mobile", 390, 844),
    ]
    local_runbook_ready = (
        MOTION_BROWSER_QA_RUNBOOK_PATH.exists()
        and "command_center_3_motion_browser_qa_runbook.v1" in script
        and "local_browser_qa_runbook_not_browser_execution" in script
        and "127.0.0.1:5173" in script
        and "127.0.0.1:8710" in script
        and "writes_no_artifacts" in script
    )
    runner_available = (
        MOTION_BROWSER_QA_RUNNER_PATH.exists()
        and "command_center_3_motion_browser_qa_result.v1" in runner_script
        and "explicit_local_browser_visual_performance_run" in runner_script
        and "chromium.launch" in runner_script
        and "page.goto" in runner_script
        and ".stock_ming_3/motion_qa" in runner_script
        and "starts_no_servers" in runner_script
        and "local_urls_only" in runner_script
        and "tushare_adapter" not in runner_script
        and "deepseek_adapter" not in runner_script
        and "api.github.com" not in runner_script
    )
    rows = [
        {
            "phase": "start_fastapi_backend",
            "status": "manual_required",
            "evidence": "scripts/dev_server.sh uses project .venv and serves FastAPI on 127.0.0.1:8710",
        },
        {
            "phase": "start_vite_frontend",
            "status": "manual_required",
            "evidence": "cd desktop && npm run dev serves local Vite on 127.0.0.1:5173",
        },
        {
            "phase": "load_pinned_routes",
            "status": "execution_pending",
            "evidence": f"{len(route_specs)} local hash routes are pinned for visual QA",
        },
        {
            "phase": "apply_viewports",
            "status": "execution_pending",
            "evidence": f"{len(viewport_specs)} desktop/tablet/mobile viewports are pinned",
        },
        {
            "phase": "capture_visual_artifacts",
            "status": "execution_pending",
            "evidence": "screenshots or recordings belong under ignored local path .stock_ming_3/motion_qa",
        },
        {
            "phase": "capture_performance_trace",
            "status": "execution_pending",
            "evidence": "record route transition, chart update, task panel, and candidate radar render budgets",
        },
        {
            "phase": "provider_trade_isolation",
            "status": "passed_static_policy",
            "evidence": "browser QA must only visit local FastAPI/Vite URLs and must not click provider/model/trading task buttons",
        },
        {
            "phase": "explicit_runner_available",
            "status": "passed_static_policy" if runner_available else "blocked",
            "evidence": "scripts/motion_browser_qa_runner.mjs can execute the pinned local route/viewport matrix and write ignored local artifacts without starting services",
        },
    ]
    for row in rows:
        row.update(
            {
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )
    qa_matrix_rows = [
        {
            "route": route,
            "label": label,
            "viewport": viewport,
            "width": width,
            "height": height,
            "risk_focus": risk_focus,
            "url": f"http://127.0.0.1:5173/{route}",
            "visual_qa_complete": False,
            "performance_trace_complete": False,
        }
        for route, label, risk_focus in route_specs
        for viewport, width, height in viewport_specs
    ]
    performance_budget_rows = [
        {
            "metric": "route_transition_observed_ms",
            "budget": 500,
            "scope": "hash route change after cache is loaded",
            "verified": False,
        },
        {
            "metric": "largest_motion_layout_shift",
            "budget": 0.1,
            "scope": "state confirmation cue and card staging",
            "verified": False,
        },
        {
            "metric": "long_task_over_50ms_count",
            "budget": 0,
            "scope": "route change, chart update, candidate radar render",
            "verified": False,
        },
        {
            "metric": "candidate_radar_first_stable_ms",
            "budget": 1200,
            "scope": "cache already local; no provider refresh",
            "verified": False,
        },
    ]
    local_runbook_with_runner_ready = local_runbook_ready and runner_available
    contract = {
        "schema_version": "command_center_3_motion_browser_qa_runbook.v1",
        "status": "motion_browser_qa_runbook_ready_execution_pending" if local_runbook_with_runner_ready else "motion_browser_qa_runbook_blocked",
        "scope": "local_browser_qa_runbook_not_browser_execution",
        "ltg": "LTG-14",
        "local_runbook_ready": local_runbook_with_runner_ready,
        "visual_qa_complete": False,
        "browser_performance_verified": False,
        "production_motion_complete": False,
        "local_api_base": "http://127.0.0.1:8710",
        "local_vite_base": "http://127.0.0.1:5173",
        "runner_script": "scripts/motion_browser_qa_runner.mjs",
        "browser_runner_available": runner_available,
        "runner_executes_only_when_called": True,
        "runner_starts_no_servers": True,
        "runner_writes_ignored_local_artifacts": True,
        "artifact_root": ".stock_ming_3/motion_qa",
        "route_count": len(route_specs),
        "viewport_count": len(viewport_specs),
        "qa_matrix_count": len(qa_matrix_rows),
        "runbook_row_count": len(rows),
        "performance_budget_count": len(performance_budget_rows),
        "cache_only": True,
        "runs_no_commands": True,
        "opens_no_browser": True,
        "writes_no_artifacts": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This runbook makes the future browser pass executable. It does not itself prove visual QA, performance, or production motion completion.",
    }
    return contract, rows, qa_matrix_rows + performance_budget_rows


def _read_motion_browser_qa_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    safe_payload = _safe_value(payload)
    if not isinstance(safe_payload, dict):
        return {}
    return safe_payload


def _motion_browser_qa_evidence_contract() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report_paths = sorted(MOTION_QA_ARTIFACT_ROOT.glob("*/motion_browser_qa_report.json")) if MOTION_QA_ARTIFACT_ROOT.exists() else []
    rows: list[dict[str, Any]] = []
    for path in report_paths:
        report = _read_motion_browser_qa_report(path)
        if not report:
            continue
        status = str(report.get("status") or "unknown")
        row = {
            "run_id": report.get("run_id") or path.parent.name,
            "generated_at": report.get("generated_at"),
            "reduced_motion": report.get("reduced_motion") is True,
            "status": status,
            "visual_qa_complete": report.get("visual_qa_complete") is True,
            "browser_performance_verified": report.get("browser_performance_verified") is True,
            "qa_matrix_count": int(report.get("qa_matrix_count") or 0),
            "passed_count": int(report.get("passed_count") or 0),
            "review_required_count": int(report.get("review_required_count") or 0),
            "console_error_count": int(report.get("console_error_count") or 0),
            "route_count": int(report.get("route_count") or 0),
            "viewport_count": int(report.get("viewport_count") or 0),
            "artifact_report_path": str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path),
            "artifact_root_should_stay_ignored": True,
            "production_motion_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
        rows.append(row)
    rows.sort(
        key=lambda row: (
            str(row.get("generated_at") or ""),
            str(row.get("run_id") or ""),
            str(row.get("artifact_report_path") or ""),
        )
    )
    rows = rows[-20:]
    passed_rows = [
        row
        for row in rows
        if row["status"] == "motion_browser_qa_passed"
        and row["visual_qa_complete"] is True
        and row["browser_performance_verified"] is True
        and row["qa_matrix_count"] >= 20
        and row["passed_count"] >= 20
        and row["review_required_count"] == 0
        and row["console_error_count"] == 0
    ]
    default_rows = [row for row in passed_rows if row["reduced_motion"] is False]
    reduced_rows = [row for row in passed_rows if row["reduced_motion"] is True]
    default_passed = bool(default_rows)
    reduced_passed = bool(reduced_rows)
    evidence_ready = default_passed and reduced_passed
    latest_default = default_rows[-1] if default_rows else {}
    latest_reduced = reduced_rows[-1] if reduced_rows else {}
    contract = {
        "schema_version": "command_center_3_motion_browser_qa_evidence.v1",
        "status": "motion_browser_qa_evidence_available_review_pending"
        if evidence_ready
        else "motion_browser_qa_evidence_pending",
        "scope": "local_ignored_browser_qa_reports_summary_not_tracked_artifact",
        "ltg": "LTG-14",
        "artifact_root": ".stock_ming_3/motion_qa",
        "report_count": len(rows),
        "passing_report_count": len(passed_rows),
        "default_motion_passed": default_passed,
        "reduced_motion_passed": reduced_passed,
        "visual_qa_complete": evidence_ready,
        "browser_performance_verified": evidence_ready,
        "production_motion_complete": False,
        "latest_default_run_id": latest_default.get("run_id"),
        "latest_reduced_motion_run_id": latest_reduced.get("run_id"),
        "latest_default_report_path": latest_default.get("artifact_report_path"),
        "latest_reduced_motion_report_path": latest_reduced.get("artifact_report_path"),
        "row_count": len(rows),
        "cache_only": True,
        "reads_ignored_local_reports_only": True,
        "screenshots_are_not_tracked": True,
        "report_artifacts_are_not_tracked": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This is a summary of explicit local browser QA reports under an ignored artifact directory. It does not commit screenshots/reports and does not mark production motion complete.",
    }
    return contract, rows


def _motion_browser_qa_review_row(
    criterion: str,
    passed: bool,
    *,
    status: str | None = None,
    evidence: str,
    blocks_review: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status or ("passed" if passed else "blocked"),
        "passed": bool(passed),
        "blocks_review": bool(blocks_review and not passed),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "production_motion_complete": False,
    }


def _motion_browser_qa_review_contract(
    evidence_contract: Mapping[str, Any],
    evidence_rows: list[dict[str, Any]],
    *,
    explicit_review: bool = False,
    task_id: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    report_count = int(evidence_contract.get("report_count") or 0)
    passing_report_count = int(evidence_contract.get("passing_report_count") or 0)
    rows = [
        _motion_browser_qa_review_row(
            "explicit_post_review_task_done",
            explicit_review,
            evidence="Motion browser QA evidence must be reviewed through POST /api/audit/motion-browser-qa-review.",
        ),
        _motion_browser_qa_review_row(
            "local_browser_qa_evidence_exists",
            report_count > 0,
            evidence="At least one ignored .stock_ming_3/motion_qa report is available for review.",
        ),
        _motion_browser_qa_review_row(
            "default_and_reduced_motion_coverage",
            evidence_contract.get("default_motion_passed") is True
            and evidence_contract.get("reduced_motion_passed") is True,
            evidence="Both default-motion and reduced-motion runner reports must pass before local review can be ready.",
        ),
        _motion_browser_qa_review_row(
            "visual_qa_evidence_passed",
            evidence_contract.get("visual_qa_complete") is True,
            evidence="Local ignored reports must show all pinned route/viewport visual checks passed.",
        ),
        _motion_browser_qa_review_row(
            "performance_evidence_passed",
            evidence_contract.get("browser_performance_verified") is True,
            evidence="Local ignored reports must show route, layout-shift, long-task, and candidate-radar budgets passed.",
        ),
        _motion_browser_qa_review_row(
            "artifact_policy_preserved",
            evidence_contract.get("screenshots_are_not_tracked") is True
            and evidence_contract.get("report_artifacts_are_not_tracked") is True,
            evidence="Screenshots and JSON reports must remain ignored local artifacts, not tracked release evidence.",
        ),
        _motion_browser_qa_review_row(
            "production_motion_completion_stays_blocked",
            evidence_contract.get("production_motion_complete") is False,
            evidence="Local artifact review must not mark production_motion_complete=true.",
        ),
        _motion_browser_qa_review_row(
            "review_starts_no_browser_or_services",
            True,
            evidence="The POST review reads summarized local artifact evidence only; it does not open browsers or start services.",
            blocks_review=False,
        ),
    ]
    blockers = [row["criterion"] for row in rows if row["blocks_review"]]
    review_ready = not blockers
    return {
        "schema_version": "command_center_3_motion_browser_qa_review.v1",
        "status": "motion_browser_qa_review_ready_local_artifact"
        if review_ready
        else "motion_browser_qa_review_pending",
        "scope": "button_gated_local_motion_browser_qa_review_no_browser_execution",
        "ltg": "LTG-14",
        "explicit_review_task_done": bool(explicit_review),
        "review_task_id": task_id,
        "reviewed_at": reviewed_at,
        "local_browser_qa_review_ready": review_ready,
        "review_report_count": report_count,
        "passing_report_count": passing_report_count,
        "default_motion_passed": evidence_contract.get("default_motion_passed") is True,
        "reduced_motion_passed": evidence_contract.get("reduced_motion_passed") is True,
        "visual_qa_complete": evidence_contract.get("visual_qa_complete") is True,
        "browser_performance_verified": evidence_contract.get("browser_performance_verified") is True,
        "production_motion_complete": False,
        "browser_visual_qa_promoted": False,
        "browser_performance_promoted": False,
        "ci_evidence_complete": False,
        "review_row_count": len(rows),
        "blocking_review_count": len(blockers),
        "blockers": blockers,
        "evidence_row_count": len(evidence_rows),
        "cache_only": True,
        "button_gated": True,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": True,
        "screenshots_are_not_tracked": evidence_contract.get("screenshots_are_not_tracked") is True,
        "report_artifacts_are_not_tracked": evidence_contract.get("report_artifacts_are_not_tracked") is True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "note": "This review records an explicit local artifact review only. It does not run browser QA, create CI evidence, or complete production motion.",
    }


def _motion_activation_row(
    activation_key: str,
    status: str,
    *,
    local_ready: bool,
    production_ready: bool,
    evidence: str,
    next_action: str,
    visual_qa_required: bool = False,
    performance_required: bool = False,
    ci_required: bool = False,
) -> dict[str, Any]:
    return {
        "activation_key": activation_key,
        "status": status,
        "local_ready": bool(local_ready),
        "production_ready": bool(production_ready),
        "production_blocker": not bool(production_ready),
        "visual_qa_required": bool(visual_qa_required),
        "performance_required": bool(performance_required),
        "ci_required": bool(ci_required),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_packets": True,
    }


def _motion_production_activation_receipt(
    motion_clarity_audit: Mapping[str, Any],
    motion_production_qa_contract: Mapping[str, Any],
    motion_keynote_roadmap_audit: Mapping[str, Any],
    motion_browser_qa_runbook_contract: Mapping[str, Any],
    motion_browser_qa_evidence_contract: Mapping[str, Any],
    motion_browser_qa_review_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    static_ready = motion_clarity_audit.get("static_ready") is True
    local_qa_ready = motion_production_qa_contract.get("local_motion_qa_ready") is True
    roadmap_ready = motion_keynote_roadmap_audit.get("roadmap_ready") is True
    runbook_ready = motion_browser_qa_runbook_contract.get("local_runbook_ready") is True
    evidence_ready = motion_browser_qa_evidence_contract.get("visual_qa_complete") is True and (
        motion_browser_qa_evidence_contract.get("browser_performance_verified") is True
    )
    explicit_review_done = motion_browser_qa_review_contract.get("explicit_review_task_done") is True
    review_ready = motion_browser_qa_review_contract.get("local_browser_qa_review_ready") is True
    visual_promoted = motion_browser_qa_review_contract.get("browser_visual_qa_promoted") is True
    performance_promoted = motion_browser_qa_review_contract.get("browser_performance_promoted") is True
    ci_complete = motion_browser_qa_review_contract.get("ci_evidence_complete") is True
    production_complete = bool(visual_promoted and performance_promoted and ci_complete)
    rows = [
        _motion_activation_row(
            "static_motion_clarity_ready",
            "passed" if static_ready else "blocked",
            local_ready=static_ready,
            production_ready=static_ready,
            evidence=str(motion_clarity_audit.get("status") or "missing"),
            next_action="Keep CSS/React motion finite, reduced-motion-safe, and visual-only.",
        ),
        _motion_activation_row(
            "local_production_qa_contract_ready",
            "passed" if local_qa_ready else "blocked",
            local_ready=local_qa_ready,
            production_ready=local_qa_ready,
            evidence=str(motion_production_qa_contract.get("status") or "missing"),
            next_action="Use this contract as the local guard before browser execution.",
        ),
        _motion_activation_row(
            "keynote_roadmap_ready",
            "passed" if roadmap_ready else "blocked",
            local_ready=roadmap_ready,
            production_ready=roadmap_ready,
            evidence=str(motion_keynote_roadmap_audit.get("status") or "missing"),
            next_action="Keep the polish target tied to clarity, not decorative motion.",
        ),
        _motion_activation_row(
            "browser_runbook_ready",
            "passed" if runbook_ready else "blocked",
            local_ready=runbook_ready,
            production_ready=runbook_ready,
            evidence=str(motion_browser_qa_runbook_contract.get("status") or "missing"),
            next_action="Run the explicit local browser QA runner only after FastAPI/Vite are already started.",
        ),
        _motion_activation_row(
            "local_browser_evidence_required",
            "local_artifact_available_review_pending" if evidence_ready else "pending_browser_runner_execution",
            local_ready=evidence_ready,
            production_ready=False,
            visual_qa_required=True,
            performance_required=True,
            evidence=(
                f"passing_report_count={motion_browser_qa_evidence_contract.get('passing_report_count')}; "
                f"default={motion_browser_qa_evidence_contract.get('default_motion_passed')}; "
                f"reduced={motion_browser_qa_evidence_contract.get('reduced_motion_passed')}"
            ),
            next_action="Create or refresh local ignored browser reports for default and reduced-motion passes.",
        ),
        _motion_activation_row(
            "explicit_review_required",
            "review_ready_local_artifact" if review_ready else "pending_button_gated_review",
            local_ready=review_ready,
            production_ready=False,
            visual_qa_required=True,
            performance_required=True,
            evidence=(
                f"explicit_review_task_done={explicit_review_done}; "
                f"blocking_review_count={motion_browser_qa_review_contract.get('blocking_review_count')}"
            ),
            next_action="Use POST /api/audit/motion-browser-qa-review to review ignored local artifacts.",
        ),
        _motion_activation_row(
            "visual_promotion_required",
            "pending_visual_promotion",
            local_ready=review_ready,
            production_ready=visual_promoted,
            visual_qa_required=True,
            evidence=f"browser_visual_qa_promoted={visual_promoted}",
            next_action="Promote visual QA only with reviewed durable evidence across all pinned routes and viewports.",
        ),
        _motion_activation_row(
            "performance_promotion_required",
            "pending_performance_promotion",
            local_ready=review_ready,
            production_ready=performance_promoted,
            performance_required=True,
            evidence=f"browser_performance_promoted={performance_promoted}",
            next_action="Promote performance only after route, layout-shift, long-task, and radar-stability budgets are reviewed.",
        ),
        _motion_activation_row(
            "durable_ci_evidence_required",
            "pending_ci_evidence",
            local_ready=False,
            production_ready=ci_complete,
            ci_required=True,
            evidence=f"ci_evidence_complete={ci_complete}",
            next_action="Add durable CI or release evidence before claiming production motion completion.",
        ),
        _motion_activation_row(
            "no_provider_trade_or_action_side_effects",
            "passed",
            local_ready=True,
            production_ready=True,
            evidence="Motion activation receipt is cache-only and visual-only.",
            next_action="Do not use motion to imply buy/sell urgency, hidden priority, or strategy-action mutation.",
        ),
    ]
    local_blockers = [row["activation_key"] for row in rows if not row["local_ready"] and row["activation_key"] in {
        "static_motion_clarity_ready",
        "local_production_qa_contract_ready",
        "keynote_roadmap_ready",
        "browser_runbook_ready",
    }]
    production_blockers = [str(row["activation_key"]) for row in rows if row["production_blocker"]]
    missing_evidence_items = [
        "default_and_reduced_motion_browser_runner_reports" if not evidence_ready else "",
        "explicit_motion_browser_qa_review" if not review_ready else "",
        "browser_visual_qa_promotion" if not visual_promoted else "",
        "browser_performance_promotion" if not performance_promoted else "",
        "durable_ci_or_release_evidence" if not ci_complete else "",
    ]
    missing_evidence_items = [item for item in missing_evidence_items if item]
    local_activation_ready = static_ready and local_qa_ready and roadmap_ready and runbook_ready and not local_blockers
    receipt = {
        "schema_version": "command_center_3_motion_production_activation_receipt.v1",
        "status": "motion_activation_receipt_ready_production_blocked"
        if local_activation_ready
        else "motion_activation_receipt_blocked",
        "scope": "local_motion_activation_receipt_no_browser_execution_or_external_call",
        "ltg": "LTG-14",
        "design_target": "apple_keynote_grade_clarity_restrained_motion",
        "local_activation_receipt_ready": local_activation_ready,
        "production_motion_complete": production_complete,
        "visual_qa_complete": visual_promoted,
        "browser_performance_verified": performance_promoted,
        "durable_ci_evidence_complete": ci_complete,
        "local_browser_evidence_available": evidence_ready,
        "explicit_review_task_done": explicit_review_done,
        "local_browser_qa_review_ready": review_ready,
        "allowed_next_step": "explicit_local_motion_browser_qa_runner_then_button_review_then_durable_visual_performance_promotion",
        "not_allowed_next_steps": [
            "treat_static_motion_contract_as_browser_visual_qa",
            "treat_local_ignored_artifacts_as_ci_evidence",
            "promote_visual_or_performance_without_explicit_review",
            "mark_production_motion_complete_without_durable_evidence",
            "use_motion_to_imply_trade_urgency_or_strategy_action",
        ],
        "missing_evidence_items": missing_evidence_items,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "missing_evidence_count": len(missing_evidence_items),
        "production_blockers": production_blockers,
        "cache_only": True,
        "runs_no_commands": True,
        "opens_no_browser": True,
        "writes_no_artifacts": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_packets": True,
        "note": "This receipt sequences LTG-14 activation. It does not run browser QA, promote local artifacts, create CI evidence, call providers, or complete production motion.",
    }
    return receipt, rows


def _motion_promotion_dry_run_row(
    criterion: str,
    passed: bool,
    *,
    status: str | None = None,
    evidence: str,
    next_action: str,
    local_required: bool = True,
    production_required: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status or ("passed" if passed else "blocked"),
        "passed": bool(passed),
        "blocks_local_promotion_review": bool(local_required and not passed),
        "production_blocker": bool(production_required and not passed),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "production_motion_complete": False,
    }


def _motion_promotion_bool(payload_safe: Mapping[str, Any], *keys: str) -> bool:
    return any(payload_safe.get(key) is True for key in keys)


def _motion_promotion_scope_ticket(
    payload_safe: Mapping[str, Any],
    motion_browser_qa_evidence_contract: Mapping[str, Any],
    motion_browser_qa_review_contract: Mapping[str, Any],
) -> dict[str, Any]:
    ci_ref = str(payload_safe.get("ci_evidence_ref") or payload_safe.get("release_evidence_ref") or "")[:160]
    ticket = {
        "schema_version": "command_center_3_motion_promotion_scope_ticket.v1",
        "user_approved": _motion_promotion_bool(payload_safe, "user_approved", "approved"),
        "promote_visual": _motion_promotion_bool(payload_safe, "promote_visual", "visual_promotion_requested"),
        "promote_performance": _motion_promotion_bool(payload_safe, "promote_performance", "performance_promotion_requested"),
        "ci_evidence_reference_provided": bool(ci_ref),
        "ci_evidence_ref_safe": ci_ref,
        "review_report_count": int(motion_browser_qa_evidence_contract.get("report_count") or 0),
        "passing_report_count": int(motion_browser_qa_evidence_contract.get("passing_report_count") or 0),
        "default_motion_passed": motion_browser_qa_evidence_contract.get("default_motion_passed") is True,
        "reduced_motion_passed": motion_browser_qa_evidence_contract.get("reduced_motion_passed") is True,
        "visual_qa_complete": motion_browser_qa_evidence_contract.get("visual_qa_complete") is True,
        "browser_performance_verified": motion_browser_qa_evidence_contract.get("browser_performance_verified") is True,
        "local_browser_qa_review_ready": motion_browser_qa_review_contract.get("local_browser_qa_review_ready") is True,
        "review_task_id": str(motion_browser_qa_review_contract.get("review_task_id") or ""),
        "production_motion_complete": False,
    }
    digest = hashlib.sha256(json.dumps(ticket, ensure_ascii=True, sort_keys=True).encode("utf-8")).hexdigest()
    ticket["scope_hash"] = digest
    ticket["scope_hash_short"] = digest[:12]
    return ticket


def _motion_production_promotion_dry_run_contract(
    motion_browser_qa_evidence_contract: Mapping[str, Any],
    motion_browser_qa_review_contract: Mapping[str, Any],
    motion_production_activation_receipt: Mapping[str, Any],
    *,
    payload_safe: Mapping[str, Any] | None = None,
    explicit_dry_run: bool = False,
    task_id: str | None = None,
    dry_run_at: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    safe_payload = payload_safe if isinstance(payload_safe, Mapping) else {}
    scope_ticket = _motion_promotion_scope_ticket(
        safe_payload,
        motion_browser_qa_evidence_contract,
        motion_browser_qa_review_contract,
    )
    user_approved = scope_ticket["user_approved"] is True
    promote_visual = scope_ticket["promote_visual"] is True
    promote_performance = scope_ticket["promote_performance"] is True
    evidence_ready = bool(scope_ticket["visual_qa_complete"] and scope_ticket["browser_performance_verified"])
    review_ready = motion_browser_qa_review_contract.get("local_browser_qa_review_ready") is True
    activation_ready = motion_production_activation_receipt.get("local_activation_receipt_ready") is True
    rows = [
        _motion_promotion_dry_run_row(
            "explicit_promotion_dry_run_task_done",
            explicit_dry_run,
            evidence="Promotion dry-run must be created through POST /api/audit/motion-production-promotion-dry-run.",
            next_action="Use the button-gated dry-run before any visual/performance promotion claim.",
        ),
        _motion_promotion_dry_run_row(
            "explicit_user_approval_recorded",
            user_approved,
            evidence="Payload must include user_approved=true or approved=true for local promotion review scoping.",
            next_action="Record explicit human approval for the dry-run scope; do not infer approval from local artifact presence.",
        ),
        _motion_promotion_dry_run_row(
            "local_browser_qa_evidence_ready",
            evidence_ready,
            evidence=(
                f"visual_qa_complete={motion_browser_qa_evidence_contract.get('visual_qa_complete')}; "
                f"browser_performance_verified={motion_browser_qa_evidence_contract.get('browser_performance_verified')}"
            ),
            next_action="Keep default and reduced-motion local browser reports reviewed before promotion scoping.",
        ),
        _motion_promotion_dry_run_row(
            "explicit_browser_review_ready",
            review_ready,
            evidence=(
                f"local_browser_qa_review_ready={review_ready}; "
                f"blocking_review_count={motion_browser_qa_review_contract.get('blocking_review_count')}"
            ),
            next_action="Run the button-gated motion browser QA review first if review is not ready.",
        ),
        _motion_promotion_dry_run_row(
            "activation_receipt_ready",
            activation_ready,
            evidence=str(motion_production_activation_receipt.get("status") or "missing"),
            next_action="Use the activation receipt as the local checklist before promotion scoping.",
        ),
        _motion_promotion_dry_run_row(
            "default_and_reduced_motion_coverage",
            scope_ticket["default_motion_passed"] is True and scope_ticket["reduced_motion_passed"] is True,
            evidence=(
                f"default={scope_ticket['default_motion_passed']}; "
                f"reduced={scope_ticket['reduced_motion_passed']}"
            ),
            next_action="Refresh local browser QA reports if either motion mode is missing.",
        ),
        _motion_promotion_dry_run_row(
            "visual_promotion_scope_bound",
            promote_visual and review_ready and motion_browser_qa_evidence_contract.get("visual_qa_complete") is True,
            status="visual_promotion_scope_ready" if promote_visual and review_ready else "visual_promotion_scope_pending",
            evidence=f"promote_visual={promote_visual}; local_browser_qa_review_ready={review_ready}",
            next_action="Promote visual QA only in a later explicit review with durable evidence; this dry-run only binds scope.",
        ),
        _motion_promotion_dry_run_row(
            "performance_promotion_scope_bound",
            promote_performance and review_ready and motion_browser_qa_evidence_contract.get("browser_performance_verified") is True,
            status="performance_promotion_scope_ready" if promote_performance and review_ready else "performance_promotion_scope_pending",
            evidence=f"promote_performance={promote_performance}; local_browser_qa_review_ready={review_ready}",
            next_action="Promote performance only in a later explicit review with trace/budget evidence; this dry-run only binds scope.",
        ),
        _motion_promotion_dry_run_row(
            "durable_ci_or_release_evidence_required",
            False,
            status="pending_durable_ci_or_release_evidence",
            evidence=f"ci_evidence_reference_provided={scope_ticket['ci_evidence_reference_provided']}; dry_run_does_not_verify_remote_ci=true",
            next_action="Attach durable CI or release evidence in a separate promotion step; do not call GitHub API from this dry-run.",
            local_required=False,
            production_required=True,
        ),
        _motion_promotion_dry_run_row(
            "production_completion_stays_blocked",
            True,
            evidence="Dry-run must keep production_motion_complete=false and promoted flags false.",
            next_action="Only a later explicit promotion with durable visual, performance, and CI/release evidence can change production state.",
            local_required=False,
            production_required=False,
        ),
        _motion_promotion_dry_run_row(
            "no_provider_trade_or_action_side_effects",
            True,
            evidence="Promotion dry-run reads local audit cache and ignored summaries only; it does not call providers/models/GitHub or execute trades.",
            next_action="Keep motion as visual clarity, never trade urgency or strategy-action mutation.",
            local_required=False,
            production_required=False,
        ),
    ]
    local_blockers = [str(row["criterion"]) for row in rows if row.get("blocks_local_promotion_review")]
    production_blockers = [str(row["criterion"]) for row in rows if row.get("production_blocker")]
    ready_for_local_promotion_review = not local_blockers
    status = (
        "motion_promotion_dry_run_blocked_user_approval_required"
        if explicit_dry_run and not user_approved
        else "motion_promotion_dry_run_ready_production_still_blocked"
        if ready_for_local_promotion_review
        else "motion_promotion_dry_run_blocked_local_evidence_or_scope_missing"
    )
    request_params_safe = {
        "promotion_scope": "motion_visual_performance_local_promotion_dry_run",
        "user_approved": user_approved,
        "promote_visual": promote_visual,
        "promote_performance": promote_performance,
        "ci_evidence_ref_provided": scope_ticket["ci_evidence_reference_provided"],
        "scope_hash_short": scope_ticket["scope_hash_short"],
        "external_sources_allowed": False,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "production_motion_complete": False,
    }
    receipt = {
        "schema_version": "command_center_3_motion_production_promotion_dry_run.v1",
        "status": status,
        "scope": "button_gated_local_motion_promotion_dry_run_no_browser_no_external_call",
        "ltg": "LTG-14",
        "design_target": "apple_keynote_grade_clarity_restrained_motion",
        "explicit_promotion_dry_run_task_done": bool(explicit_dry_run),
        "promotion_task_id": task_id,
        "dry_run_at": dry_run_at,
        "button_gated": True,
        "local_dry_run_only": True,
        "ready_for_local_promotion_review": ready_for_local_promotion_review,
        "ready_to_mark_production_motion_complete": False,
        "production_motion_complete": False,
        "browser_visual_qa_promoted": False,
        "browser_performance_promoted": False,
        "ci_evidence_complete": False,
        "browser_visual_qa_promotion_requested": promote_visual,
        "browser_performance_promotion_requested": promote_performance,
        "durable_ci_or_release_evidence_required": True,
        "dry_run_verifies_remote_ci": False,
        "local_browser_evidence_available": evidence_ready,
        "local_browser_qa_review_ready": review_ready,
        "activation_receipt_ready": activation_ready,
        "scope_ticket": scope_ticket,
        "scope_hash": scope_ticket["scope_hash"],
        "scope_hash_short": scope_ticket["scope_hash_short"],
        "request_params_safe": request_params_safe,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "promotion_row_count": len(rows),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "allowed_next_step": "review_motion_visual_and_performance_promotion_then_attach_durable_ci_or_release_evidence",
        "not_allowed_next_steps": [
            "mark_production_motion_complete_from_dry_run",
            "treat_local_ignored_artifacts_as_durable_ci_evidence",
            "promote_visual_without_reviewed_scope",
            "promote_performance_without_trace_or_budget_review",
            "call_github_api_or_browser_from_promotion_dry_run",
            "use_motion_to_imply_trade_urgency_or_strategy_action",
        ],
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": True,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "note": "This dry-run binds the LTG-14 promotion scope after local evidence review. It does not run browsers, verify remote CI, promote artifacts, or complete production motion.",
    }
    return receipt, rows


def _motion_durable_evidence_recipe_row(
    evidence_key: str,
    passed: bool,
    *,
    status: str | None = None,
    evidence: str,
    next_action: str,
    local_required: bool = False,
    production_required: bool = True,
) -> dict[str, Any]:
    return {
        "evidence_key": evidence_key,
        "status": status or ("passed" if passed else "pending"),
        "passed": bool(passed),
        "blocks_local_recipe": bool(local_required and not passed),
        "production_blocker": bool(production_required and not passed),
        "evidence": evidence,
        "next_action": next_action,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "production_motion_complete": False,
    }


def _motion_durable_evidence_recipe(
    motion_browser_qa_evidence_contract: Mapping[str, Any],
    motion_browser_qa_review_contract: Mapping[str, Any],
    motion_production_activation_receipt: Mapping[str, Any],
    motion_promotion_dry_run_receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    local_reports_ready = motion_browser_qa_evidence_contract.get("visual_qa_complete") is True and (
        motion_browser_qa_evidence_contract.get("browser_performance_verified") is True
    )
    default_and_reduced_ready = motion_browser_qa_evidence_contract.get("default_motion_passed") is True and (
        motion_browser_qa_evidence_contract.get("reduced_motion_passed") is True
    )
    review_ready = motion_browser_qa_review_contract.get("local_browser_qa_review_ready") is True
    promotion_scope_bound = motion_promotion_dry_run_receipt.get("ready_for_local_promotion_review") is True
    activation_ready = motion_production_activation_receipt.get("local_activation_receipt_ready") is True
    rows = [
        _motion_durable_evidence_recipe_row(
            "local_activation_sequence_visible",
            activation_ready,
            status="passed" if activation_ready else "blocked_local_activation_receipt",
            evidence=str(motion_production_activation_receipt.get("status") or "missing"),
            next_action="Keep the activation receipt as the local source of truth before durable promotion.",
            local_required=True,
            production_required=False,
        ),
        _motion_durable_evidence_recipe_row(
            "local_browser_reports_available",
            local_reports_ready,
            status="local_report_available" if local_reports_ready else "pending_local_runner_report",
            evidence=(
                f"report_count={motion_browser_qa_evidence_contract.get('report_count')}; "
                f"passing_report_count={motion_browser_qa_evidence_contract.get('passing_report_count')}; "
                f"visual={motion_browser_qa_evidence_contract.get('visual_qa_complete')}; "
                f"performance={motion_browser_qa_evidence_contract.get('browser_performance_verified')}"
            ),
            next_action="Use the explicit local runner to create default and reduced-motion ignored reports.",
            production_required=False,
        ),
        _motion_durable_evidence_recipe_row(
            "default_and_reduced_motion_covered",
            default_and_reduced_ready,
            status="local_motion_modes_covered" if default_and_reduced_ready else "pending_default_or_reduced_motion_report",
            evidence=(
                f"default={motion_browser_qa_evidence_contract.get('default_motion_passed')}; "
                f"reduced={motion_browser_qa_evidence_contract.get('reduced_motion_passed')}"
            ),
            next_action="Require both default and reduced-motion reports before any durable visual promotion.",
            production_required=False,
        ),
        _motion_durable_evidence_recipe_row(
            "button_gated_local_review_ready",
            review_ready,
            status="local_review_ready" if review_ready else "pending_button_gated_review",
            evidence=(
                f"explicit_review_task_done={motion_browser_qa_review_contract.get('explicit_review_task_done')}; "
                f"blocking_review_count={motion_browser_qa_review_contract.get('blocking_review_count')}"
            ),
            next_action="Run POST /api/audit/motion-browser-qa-review before binding durable evidence.",
            production_required=False,
        ),
        _motion_durable_evidence_recipe_row(
            "promotion_scope_bound_by_dry_run",
            promotion_scope_bound,
            status="promotion_scope_bound" if promotion_scope_bound else "pending_promotion_dry_run",
            evidence=str(motion_promotion_dry_run_receipt.get("status") or "missing"),
            next_action="Use POST /api/audit/motion-production-promotion-dry-run to bind the human-reviewed scope.",
            production_required=False,
        ),
        _motion_durable_evidence_recipe_row(
            "browser_visual_promotion_evidence_required",
            False,
            status="pending_durable_visual_promotion",
            evidence="Local ignored reports and review are not durable visual promotion evidence.",
            next_action="Attach reviewed release/CI visual evidence across home, next, candidates, tasks, and audit routes.",
        ),
        _motion_durable_evidence_recipe_row(
            "browser_performance_trace_required",
            False,
            status="pending_browser_performance_trace",
            evidence="No durable route transition, long-task, layout-shift, or radar stability trace is promoted.",
            next_action="Attach performance traces that prove motion does not reintroduce stalls.",
        ),
        _motion_durable_evidence_recipe_row(
            "reduced_motion_durable_evidence_required",
            False,
            status="pending_reduced_motion_durable_evidence",
            evidence="Reduced-motion local reports must be promoted with durable review evidence before production.",
            next_action="Promote reduced-motion route/viewport evidence alongside default-motion visual evidence.",
        ),
        _motion_durable_evidence_recipe_row(
            "durable_ci_or_release_evidence_required",
            False,
            status="pending_durable_ci_or_release_evidence",
            evidence="This recipe does not inspect GitHub Actions or release artifacts.",
            next_action="Attach durable CI/release evidence in a separate explicit promotion step.",
        ),
        _motion_durable_evidence_recipe_row(
            "artifact_retention_and_redaction_policy",
            True,
            evidence=".stock_ming_3/motion_qa remains ignored; screenshots/videos/reports are not committed as proof.",
            next_action="Keep raw artifacts local or release-scoped, and expose only safe summaries in packets.",
            production_required=False,
        ),
        _motion_durable_evidence_recipe_row(
            "no_provider_model_github_trade_boundary",
            True,
            evidence="Recipe is cache-only and visual-only; it calls no providers, models, GitHub API, or trading path.",
            next_action="Keep motion evidence separate from Tushare, DeepSeek, GitHub probes, and strategy action.",
            production_required=False,
        ),
    ]
    local_blockers = [str(row["evidence_key"]) for row in rows if row.get("blocks_local_recipe")]
    production_blockers = [str(row["evidence_key"]) for row in rows if row.get("production_blocker")]
    local_recipe_ready = not local_blockers
    durable_evidence_ready = not production_blockers
    receipt = {
        "schema_version": "command_center_3_motion_durable_evidence_recipe.v1",
        "status": "motion_durable_evidence_recipe_ready_production_pending"
        if local_recipe_ready
        else "motion_durable_evidence_recipe_blocked_local_activation",
        "scope": "local_motion_durable_evidence_recipe_no_browser_no_ci_no_github",
        "ltg": "LTG-14",
        "design_target": "apple_keynote_grade_clarity_restrained_motion",
        "local_recipe_ready": local_recipe_ready,
        "durable_evidence_ready": durable_evidence_ready,
        "ready_to_mark_production_motion_complete": False,
        "production_motion_complete": False,
        "browser_visual_qa_promoted": False,
        "browser_performance_promoted": False,
        "ci_evidence_complete": False,
        "durable_ci_evidence_complete": False,
        "local_browser_reports_available": local_reports_ready,
        "default_and_reduced_motion_covered": default_and_reduced_ready,
        "local_browser_qa_review_ready": review_ready,
        "promotion_scope_bound": promotion_scope_bound,
        "row_count": len(rows),
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "allowed_next_step": "attach_durable_visual_performance_reduced_motion_and_ci_release_evidence_in_explicit_promotion",
        "not_allowed_next_steps": [
            "treat_local_ignored_reports_as_durable_evidence",
            "treat_button_review_as_browser_execution",
            "treat_promotion_dry_run_as_visual_or_performance_promotion",
            "inspect_github_actions_from_recipe",
            "mark_production_motion_complete_from_recipe",
            "use_motion_to_imply_trade_urgency_or_strategy_action",
        ],
        "cache_only": True,
        "runs_no_commands": True,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "reads_ignored_local_reports_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_packets": True,
        "rows": rows,
        "note": "This recipe maps reviewed local LTG-14 motion evidence to the durable promotion evidence still required. It does not run browser QA, inspect CI, promote artifacts, call providers/models/GitHub, or complete production motion.",
    }
    return receipt, rows


def _read_persisted_audit_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(PACKET_KEY)
    except Exception:
        return {}
    return packet if isinstance(packet, dict) else {}


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
    release_gate_readiness_audit, release_gate_readiness_rows, release_gate_workflow_rows = _release_gate_readiness_audit()
    ci_notification_triage_contract, ci_notification_triage_rows = _ci_notification_triage_contract(
        release_gate_readiness_audit,
        release_gate_workflow_rows,
    )
    local_push_gate_run_receipt = _read_local_push_gate_run_receipt()
    release_gate_push_readiness_receipt, release_gate_push_readiness_rows = _release_gate_push_readiness_receipt(
        release_gate_readiness_audit,
        ci_notification_triage_contract,
        local_push_gate_run_receipt,
    )
    release_gate_stage_scope_rows = _release_gate_stage_scope_rows(
        release_gate_readiness_audit,
        release_gate_push_readiness_receipt,
        ci_notification_triage_contract,
        local_push_gate_run_receipt,
    )
    motion_clarity_audit, motion_clarity_rows = _motion_clarity_readiness_audit()
    motion_production_qa_contract, motion_production_qa_rows = _motion_production_qa_contract(
        motion_clarity_audit,
        motion_clarity_rows,
    )
    motion_browser_qa_runbook_contract, motion_browser_qa_runbook_rows, motion_browser_qa_matrix_rows = (
        _motion_browser_qa_runbook_contract()
    )
    motion_browser_qa_evidence_contract, motion_browser_qa_evidence_rows = _motion_browser_qa_evidence_contract()
    persisted_packet = _read_persisted_audit_packet()
    persisted_review = _as_dict(persisted_packet.get("motion_browser_qa_review_contract"))
    review_was_explicit = persisted_review.get("explicit_review_task_done") is True
    motion_browser_qa_review_contract = _motion_browser_qa_review_contract(
        motion_browser_qa_evidence_contract,
        motion_browser_qa_evidence_rows,
        explicit_review=review_was_explicit,
        task_id=str(persisted_review.get("review_task_id") or "") or None,
        reviewed_at=str(persisted_review.get("reviewed_at") or "") or None,
    )
    motion_browser_qa_review_rows = _as_list(motion_browser_qa_review_contract.get("rows"))
    motion_keynote_roadmap_audit, motion_keynote_roadmap_rows = _motion_keynote_roadmap_audit(
        motion_clarity_audit,
        motion_production_qa_contract,
        motion_browser_qa_evidence_contract,
        motion_browser_qa_review_contract,
    )
    motion_production_activation_receipt, motion_production_activation_rows = _motion_production_activation_receipt(
        motion_clarity_audit,
        motion_production_qa_contract,
        motion_keynote_roadmap_audit,
        motion_browser_qa_runbook_contract,
        motion_browser_qa_evidence_contract,
        motion_browser_qa_review_contract,
    )
    persisted_promotion = _as_dict(persisted_packet.get("motion_promotion_dry_run_receipt"))
    promotion_was_explicit = persisted_promotion.get("explicit_promotion_dry_run_task_done") is True
    motion_promotion_dry_run_receipt, motion_promotion_dry_run_rows = _motion_production_promotion_dry_run_contract(
        motion_browser_qa_evidence_contract,
        motion_browser_qa_review_contract,
        motion_production_activation_receipt,
        payload_safe=_as_dict(persisted_promotion.get("request_params_safe")),
        explicit_dry_run=promotion_was_explicit,
        task_id=str(persisted_promotion.get("promotion_task_id") or "") or None,
        dry_run_at=str(persisted_promotion.get("dry_run_at") or "") or None,
    )
    motion_durable_evidence_recipe, motion_durable_evidence_rows = _motion_durable_evidence_recipe(
        motion_browser_qa_evidence_contract,
        motion_browser_qa_review_contract,
        motion_production_activation_receipt,
        motion_promotion_dry_run_receipt,
    )
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
        "release_gate_readiness_audit": release_gate_readiness_audit,
        "release_gate_readiness_rows": release_gate_readiness_rows,
        "release_gate_workflow_rows": release_gate_workflow_rows,
        "local_push_gate_run_receipt": local_push_gate_run_receipt,
        "release_gate_push_readiness_receipt": release_gate_push_readiness_receipt,
        "release_gate_push_readiness_rows": release_gate_push_readiness_rows,
        "release_gate_stage_scope_rows": release_gate_stage_scope_rows,
        "ci_notification_triage_contract": ci_notification_triage_contract,
        "ci_notification_triage_rows": ci_notification_triage_rows,
        "motion_clarity_audit": motion_clarity_audit,
        "motion_clarity_rows": motion_clarity_rows,
        "motion_production_qa_contract": motion_production_qa_contract,
        "motion_production_qa_rows": motion_production_qa_rows,
        "motion_browser_qa_runbook_contract": motion_browser_qa_runbook_contract,
        "motion_browser_qa_runbook_rows": motion_browser_qa_runbook_rows,
        "motion_browser_qa_matrix_rows": motion_browser_qa_matrix_rows,
        "motion_browser_qa_evidence_contract": motion_browser_qa_evidence_contract,
        "motion_browser_qa_evidence_rows": motion_browser_qa_evidence_rows,
        "motion_browser_qa_review_contract": motion_browser_qa_review_contract,
        "motion_browser_qa_review_rows": motion_browser_qa_review_rows,
        "motion_keynote_roadmap_audit": motion_keynote_roadmap_audit,
        "motion_keynote_roadmap_rows": motion_keynote_roadmap_rows,
        "motion_production_activation_receipt": motion_production_activation_receipt,
        "motion_production_activation_rows": motion_production_activation_rows,
        "motion_promotion_dry_run_receipt": motion_promotion_dry_run_receipt,
        "motion_promotion_dry_run_rows": motion_promotion_dry_run_rows,
        "motion_durable_evidence_recipe": motion_durable_evidence_recipe,
        "motion_durable_evidence_rows": motion_durable_evidence_rows,
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
            "release_gate_check_count": release_gate_readiness_audit.get("check_count", 0),
            "release_gate_blocker_count": release_gate_readiness_audit.get("blocking_criterion_count", 0),
            "release_gate_soft_blocker_count": release_gate_readiness_audit.get("soft_blocker_count", 0),
            "release_gate_local_ready": release_gate_readiness_audit.get("local_gate_ready") is True,
            "release_gate_complete": release_gate_readiness_audit.get("release_gate_complete") is True,
            "release_gate_ci_mirror_ready": release_gate_readiness_audit.get("ci_mirror_ready") is True,
            "release_gate_workflow_count": release_gate_readiness_audit.get("workflow_count", 0),
            "release_gate_stage_scope_count": len(release_gate_stage_scope_rows),
            "release_gate_stage_scope_pending_count": sum(
                1 for row in release_gate_stage_scope_rows if row.get("stage_complete") is False
            ),
            "local_push_gate_run_observed": local_push_gate_run_receipt.get("fresh_local_gate_run_observed") is True,
            "local_push_gate_receipt_head_matches_current": local_push_gate_run_receipt.get("head_matches_current")
            is True,
            "push_readiness_receipt_ready": release_gate_push_readiness_receipt.get("local_receipt_ready") is True,
            "push_readiness_remote_status_known": release_gate_push_readiness_receipt.get(
                "remote_actions_status_known"
            )
            is True,
            "push_readiness_pending_evidence_count": release_gate_push_readiness_receipt.get(
                "pending_evidence_count",
                0,
            ),
            "push_readiness_blocker_count": release_gate_push_readiness_receipt.get("blocking_criterion_count", 0),
            "ci_notification_triage_ready": ci_notification_triage_contract.get("status")
            == "ci_notification_triage_ready_remote_logs_required",
            "ci_notification_pending_remote_evidence_count": ci_notification_triage_contract.get(
                "pending_remote_evidence_count",
                0,
            ),
            "ci_notification_remote_status_known": ci_notification_triage_contract.get("remote_actions_status_known")
            is True,
            "motion_clarity_check_count": motion_clarity_audit.get("row_count", 0),
            "motion_clarity_static_ready": motion_clarity_audit.get("static_ready") is True,
            "motion_clarity_blocker_count": motion_clarity_audit.get("blocking_criterion_count", 0),
            "motion_clarity_soft_blocker_count": motion_clarity_audit.get("soft_blocker_count", 0),
            "motion_production_qa_row_count": motion_production_qa_contract.get("row_count", 0),
            "motion_production_qa_local_ready": motion_production_qa_contract.get("local_motion_qa_ready") is True,
            "motion_production_blocker_count": motion_production_qa_contract.get("production_blocker_count", 0),
            "motion_visual_pending_count": motion_production_qa_contract.get("visual_pending_count", 0),
            "motion_performance_pending_count": motion_production_qa_contract.get("performance_pending_count", 0),
            "motion_browser_qa_runbook_ready": motion_browser_qa_runbook_contract.get("local_runbook_ready") is True,
            "motion_browser_qa_matrix_count": motion_browser_qa_runbook_contract.get("qa_matrix_count", 0),
            "motion_browser_qa_performance_budget_count": motion_browser_qa_runbook_contract.get("performance_budget_count", 0),
            "motion_browser_qa_evidence_report_count": motion_browser_qa_evidence_contract.get("report_count", 0),
            "motion_browser_qa_evidence_passing_report_count": motion_browser_qa_evidence_contract.get("passing_report_count", 0),
            "motion_browser_qa_default_passed": motion_browser_qa_evidence_contract.get("default_motion_passed") is True,
            "motion_browser_qa_reduced_motion_passed": motion_browser_qa_evidence_contract.get("reduced_motion_passed") is True,
            "motion_browser_qa_evidence_visual_complete": motion_browser_qa_evidence_contract.get("visual_qa_complete") is True,
            "motion_browser_qa_evidence_performance_verified": motion_browser_qa_evidence_contract.get("browser_performance_verified") is True,
            "motion_browser_qa_review_ready": motion_browser_qa_review_contract.get("local_browser_qa_review_ready") is True,
            "motion_browser_qa_review_blocking_count": motion_browser_qa_review_contract.get("blocking_review_count", 0),
            "motion_keynote_roadmap_ready": motion_keynote_roadmap_audit.get("roadmap_ready") is True,
            "motion_keynote_promotion_blocker_count": motion_keynote_roadmap_audit.get("promotion_blocker_count", 0),
            "motion_keynote_visual_required_count": motion_keynote_roadmap_audit.get("visual_qa_required_count", 0),
            "motion_keynote_performance_required_count": motion_keynote_roadmap_audit.get("performance_trace_required_count", 0),
            "motion_keynote_browser_review_required_count": motion_keynote_roadmap_audit.get("browser_review_required_count", 0),
            "motion_activation_receipt_ready": motion_production_activation_receipt.get("local_activation_receipt_ready") is True,
            "motion_activation_local_blocker_count": motion_production_activation_receipt.get("local_blocker_count", 0),
            "motion_activation_production_blocker_count": motion_production_activation_receipt.get("production_blocker_count", 0),
            "motion_activation_missing_evidence_count": motion_production_activation_receipt.get("missing_evidence_count", 0),
            "motion_activation_row_count": motion_production_activation_receipt.get("row_count", 0),
            "motion_promotion_dry_run_ready": motion_promotion_dry_run_receipt.get("ready_for_local_promotion_review") is True,
            "motion_promotion_dry_run_local_blocker_count": motion_promotion_dry_run_receipt.get("local_blocker_count", 0),
            "motion_promotion_dry_run_production_blocker_count": motion_promotion_dry_run_receipt.get("production_blocker_count", 0),
            "motion_promotion_dry_run_row_count": motion_promotion_dry_run_receipt.get("row_count", 0),
            "motion_durable_evidence_recipe_ready": motion_durable_evidence_recipe.get("local_recipe_ready") is True,
            "motion_durable_evidence_production_blocker_count": motion_durable_evidence_recipe.get("production_blocker_count", 0),
            "motion_durable_evidence_row_count": motion_durable_evidence_recipe.get("row_count", 0),
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
            "release_gate_audit_is_static": True,
            "release_gate_audit_runs_no_commands": True,
            "release_gate_audit_calls_no_github_api": True,
            "release_gate_local_ready_is_not_ci_status": True,
            "release_gate_stage_scope_is_local": True,
            "release_gate_stage_scope_is_not_fresh_gate_or_remote_ci": True,
            "push_readiness_receipt_is_local": True,
            "push_readiness_receipt_runs_no_commands": True,
            "push_readiness_receipt_calls_no_github_api": True,
            "push_readiness_receipt_is_not_remote_ci_status": True,
            "push_readiness_receipt_does_not_push": True,
            "ci_notification_triage_is_local": True,
            "ci_notification_triage_calls_no_github_api": True,
            "ci_notification_requires_remote_logs": True,
            "ci_notification_local_pass_is_not_remote_green": True,
            "motion_clarity_audit_is_static": True,
            "motion_clarity_audit_runs_no_commands": True,
            "motion_clarity_static_ready_is_not_visual_qa": True,
            "motion_production_qa_contract_is_local": True,
            "motion_production_qa_is_not_browser_visual_or_perf_proof": True,
            "motion_browser_qa_runbook_is_local": True,
            "motion_browser_qa_runbook_is_not_browser_execution": True,
            "motion_browser_qa_evidence_is_local_ignored_artifact_summary": True,
            "motion_browser_qa_evidence_is_not_production_completion": True,
            "motion_browser_qa_review_is_button_gated": True,
            "motion_browser_qa_review_does_not_open_browser": True,
            "motion_browser_qa_review_is_not_production_completion": True,
            "motion_keynote_roadmap_audit_is_local": True,
            "motion_keynote_roadmap_is_not_browser_execution": True,
            "motion_keynote_roadmap_is_not_production_completion": True,
            "motion_activation_receipt_is_local": True,
            "motion_activation_receipt_runs_no_commands": True,
            "motion_activation_receipt_is_not_browser_execution": True,
            "motion_activation_receipt_is_not_production_completion": True,
            "motion_promotion_dry_run_is_button_gated": True,
            "motion_promotion_dry_run_does_not_open_browser": True,
            "motion_promotion_dry_run_calls_no_github_api": True,
            "motion_promotion_dry_run_is_not_production_completion": True,
            "motion_durable_evidence_recipe_is_local": True,
            "motion_durable_evidence_recipe_runs_no_commands": True,
            "motion_durable_evidence_recipe_calls_no_github_api": True,
            "motion_durable_evidence_recipe_is_not_production_completion": True,
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
                "release_gate_status": release_gate_readiness_audit.get("status"),
                "release_gate_local_ready": release_gate_readiness_audit.get("local_gate_ready"),
                "release_gate_complete": release_gate_readiness_audit.get("release_gate_complete"),
                "push_readiness_receipt_status": release_gate_push_readiness_receipt.get("status"),
                "local_push_gate_run_receipt_status": local_push_gate_run_receipt.get("status"),
                "local_push_gate_run_observed": local_push_gate_run_receipt.get("fresh_local_gate_run_observed"),
                "push_readiness_allowed_next_step": release_gate_push_readiness_receipt.get("allowed_next_step"),
                "push_readiness_remote_status_known": release_gate_push_readiness_receipt.get(
                    "remote_actions_status_known"
                ),
                "ci_notification_triage_status": ci_notification_triage_contract.get("status"),
                "ci_notification_remote_logs_required": ci_notification_triage_contract.get(
                    "remote_logs_required_for_root_cause"
                ),
                "ci_notification_remote_actions_status_known": ci_notification_triage_contract.get(
                    "remote_actions_status_known"
                ),
                "motion_clarity_status": motion_clarity_audit.get("status"),
                "motion_clarity_static_ready": motion_clarity_audit.get("static_ready"),
                "motion_clarity_visual_qa_complete": motion_clarity_audit.get("visual_qa_complete"),
                "motion_production_qa_status": motion_production_qa_contract.get("status"),
                "motion_production_qa_local_ready": motion_production_qa_contract.get("local_motion_qa_ready"),
                "motion_production_complete": motion_production_qa_contract.get("production_motion_complete"),
                "motion_browser_qa_runbook_status": motion_browser_qa_runbook_contract.get("status"),
                "motion_browser_qa_runbook_ready": motion_browser_qa_runbook_contract.get("local_runbook_ready"),
                "motion_browser_qa_evidence_status": motion_browser_qa_evidence_contract.get("status"),
                "motion_browser_qa_evidence_visual_complete": motion_browser_qa_evidence_contract.get("visual_qa_complete"),
                "motion_browser_qa_evidence_performance_verified": motion_browser_qa_evidence_contract.get("browser_performance_verified"),
                "motion_browser_qa_review_status": motion_browser_qa_review_contract.get("status"),
                "motion_browser_qa_review_ready": motion_browser_qa_review_contract.get("local_browser_qa_review_ready"),
                "motion_keynote_roadmap_status": motion_keynote_roadmap_audit.get("status"),
                "motion_keynote_promotion_blocker_count": motion_keynote_roadmap_audit.get("promotion_blocker_count"),
                "motion_activation_receipt_status": motion_production_activation_receipt.get("status"),
                "motion_activation_receipt_allowed_next_step": motion_production_activation_receipt.get("allowed_next_step"),
                "motion_activation_production_blocker_count": motion_production_activation_receipt.get("production_blocker_count"),
                "motion_promotion_dry_run_status": motion_promotion_dry_run_receipt.get("status"),
                "motion_promotion_ready_for_local_review": motion_promotion_dry_run_receipt.get("ready_for_local_promotion_review"),
                "motion_promotion_production_blocker_count": motion_promotion_dry_run_receipt.get("production_blocker_count"),
                "motion_durable_evidence_recipe_status": motion_durable_evidence_recipe.get("status"),
                "motion_durable_evidence_recipe_ready": motion_durable_evidence_recipe.get("local_recipe_ready"),
                "motion_durable_evidence_production_blocker_count": motion_durable_evidence_recipe.get("production_blocker_count"),
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
            "release_gate_readiness_audit 只读解析本地脚本和 workflow；local_gate_ready 不是 CI 状态，也不是生产完成证明。",
            "release_gate_push_readiness_receipt 只选择显式本地 gate -> push -> 远端 Actions 复核路径；不运行命令、不调用 GitHub、不证明远端已绿。",
            "local_push_gate_run_receipt 只读取 ignored 本地 receipt 并匹配当前 HEAD；它不是远端 Actions 状态，也不会触发 push。",
            "ci_notification_triage_contract 只解释失败邮件需要的远端日志证据；不调用 GitHub API，也不证明远端 run 已变绿。",
            "motion_clarity_audit 只读解析本地 React/CSS 源码；static_ready 不是浏览器视觉验收或生产动效完成证明。",
            "motion_production_qa_contract 是本地生产验收清单；不运行浏览器视觉 QA 或性能 trace。",
            "motion_keynote_roadmap_audit 只是高级动效路线图审计；不运行浏览器、不推广本地 artifact、不完成 production motion。",
            "motion_production_activation_receipt 只串联 LTG-14 下一步验收路径；不运行浏览器、不创建 CI 证据、不完成 production motion。",
            "motion_browser_qa_review_contract 只记录显式本地 artifact 审查；不运行浏览器、不创建 CI 证据、不完成生产动效。",
            "motion_promotion_dry_run_receipt 只做 LTG-14 本地推广预检；不打开浏览器、不调用 GitHub、不推广 artifact、不完成 production motion。",
            "motion_durable_evidence_recipe 只列出本地动效证据到 durable promotion 的缺口；不运行浏览器、不读取 GitHub、不完成 production motion。",
        ],
    }
    return _json_safe(packet)


def run_motion_browser_qa_review_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_motion_browser_qa_review",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="motion_browser_qa_review_queued",
        warnings=[
            "Motion browser QA review 只读取本地 ignored runner 报告摘要；不会打开浏览器、不会启动服务、不会调用 Tushare/DeepSeek/GitHub。",
            "review 结果只代表本地 artifact 审查状态；不代表 CI evidence 或 production motion complete。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_motion_browser_qa_evidence",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_call_ledger_audit_cache()
    evidence_contract = _as_dict(packet.get("motion_browser_qa_evidence_contract"))
    evidence_rows = [row for row in _as_list(packet.get("motion_browser_qa_evidence_rows")) if isinstance(row, dict)]
    reviewed_at = _now_iso()
    review_contract = _motion_browser_qa_review_contract(
        evidence_contract,
        evidence_rows,
        explicit_review=True,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    request_params_safe = {
        "review_scope": "motion_browser_qa_local_artifact",
        "external_sources_allowed": False,
        "opens_no_browser": True,
        "starts_no_servers": True,
        "writes_no_artifacts": True,
        "production_motion_complete": False,
    }
    request_params_safe.update(
        {
            key: payload_safe.get(key)
            for key in ("review_note", "reviewer")
            if payload_safe.get(key) is not None
        }
    )
    ledger = {
        "api": "local_motion_browser_qa_review",
        "source": ".stock_ming_3/motion_qa",
        "row_count": len(review_contract.get("rows") or []),
        "call_status": review_contract["status"],
        "request_params_safe": request_params_safe,
        "local_fetched_at": reviewed_at,
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    packet["motion_browser_qa_review_completed_at"] = reviewed_at
    packet["motion_browser_qa_review_contract"] = review_contract
    packet["motion_browser_qa_review_rows"] = review_contract["rows"]
    counts = _as_dict(packet.get("counts"))
    counts["motion_browser_qa_review_ready"] = review_contract["local_browser_qa_review_ready"]
    counts["motion_browser_qa_review_blocking_count"] = review_contract["blocking_review_count"]
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["motion_browser_qa_review_is_button_gated"] = True
    policy["motion_browser_qa_review_does_not_open_browser"] = True
    policy["motion_browser_qa_review_is_not_production_completion"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "Motion browser QA review 只审查本地 ignored artifact；不打开浏览器、不提交截图、不调用 provider、不完成 production motion。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "browser QA review" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "motion_browser_qa_review_storage_write_failed"
        ledger["error_message_safe"] = "motion_browser_qa_review_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="motion_browser_qa_review_storage_write_failed",
            error_message_safe="motion_browser_qa_review_sqlite_write_failed",
            call_ledger=[ledger],
            warning="motion_browser_qa_review_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="motion_browser_qa_review_ready",
        call_ledger=[ledger],
        warning="motion_browser_qa_review_ready_no_external_call",
    ) or task


def run_motion_production_promotion_dry_run_task(payload: Any = None) -> dict[str, Any]:
    task = task_service.create_task_record(
        "run_motion_production_promotion_dry_run",
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="motion_production_promotion_dry_run_queued",
        warnings=[
            "Motion promotion dry-run 只读取本地 audit cache 与 ignored runner 摘要；不会打开浏览器、不会启动服务、不会调用 Tushare/DeepSeek/GitHub。",
            "promotion dry-run 只是生产推广预检；不代表 CI evidence、visual/performance promotion 或 production motion complete。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    task_service.update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_motion_promotion_inputs",
    )
    payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), dict) else {}
    packet = read_call_ledger_audit_cache()
    evidence_contract = _as_dict(packet.get("motion_browser_qa_evidence_contract"))
    review_contract = _as_dict(packet.get("motion_browser_qa_review_contract"))
    activation_receipt = _as_dict(packet.get("motion_production_activation_receipt"))
    dry_run_at = _now_iso()
    promotion_receipt, promotion_rows = _motion_production_promotion_dry_run_contract(
        evidence_contract,
        review_contract,
        activation_receipt,
        payload_safe=payload_safe,
        explicit_dry_run=True,
        task_id=str(task["task_id"]),
        dry_run_at=dry_run_at,
    )
    ledger = {
        "api": "local_motion_production_promotion_dry_run",
        "source": "command_center_3_call_ledger_audit_cache + .stock_ming_3/motion_qa summary",
        "row_count": len(promotion_rows),
        "call_status": promotion_receipt["status"],
        "request_params_safe": promotion_receipt["request_params_safe"],
        "scope_hash_short": promotion_receipt["scope_hash_short"],
        "local_fetched_at": dry_run_at,
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    packet["motion_promotion_dry_run_completed_at"] = dry_run_at
    packet["motion_promotion_dry_run_receipt"] = promotion_receipt
    packet["motion_promotion_dry_run_rows"] = promotion_rows
    counts = _as_dict(packet.get("counts"))
    counts["motion_promotion_dry_run_ready"] = promotion_receipt["ready_for_local_promotion_review"]
    counts["motion_promotion_dry_run_local_blocker_count"] = promotion_receipt["local_blocker_count"]
    counts["motion_promotion_dry_run_production_blocker_count"] = promotion_receipt["production_blocker_count"]
    counts["motion_promotion_dry_run_row_count"] = promotion_receipt["row_count"]
    packet["counts"] = counts
    policy = _as_dict(packet.get("policy"))
    policy["motion_promotion_dry_run_is_button_gated"] = True
    policy["motion_promotion_dry_run_does_not_open_browser"] = True
    policy["motion_promotion_dry_run_calls_no_github_api"] = True
    policy["motion_promotion_dry_run_is_not_production_completion"] = True
    packet["policy"] = policy
    packet["call_ledger"] = [ledger]
    packet["warnings"] = [
        "Motion promotion dry-run 只做本地推广预检；不打开浏览器、不调用 provider/model/GitHub、不推广 artifact、不完成 production motion。"
    ] + [warning for warning in _as_list(packet.get("warnings")) if "promotion dry-run" not in str(warning)]
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(PACKET_KEY, packet)
    except Exception:
        ledger["call_status"] = "motion_production_promotion_dry_run_storage_write_failed"
        ledger["error_message_safe"] = "motion_production_promotion_dry_run_sqlite_write_failed"
        return task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="motion_production_promotion_dry_run_storage_write_failed",
            error_message_safe="motion_production_promotion_dry_run_sqlite_write_failed",
            call_ledger=[ledger],
            warning="motion_production_promotion_dry_run_failed_no_external_call",
        ) or task

    return task_service.update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="motion_production_promotion_dry_run_ready",
        call_ledger=[ledger],
        warning="motion_production_promotion_dry_run_ready_no_external_call",
    ) or task
