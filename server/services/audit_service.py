from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Callable, Mapping
from pathlib import Path
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
RELEASE_GATE_SCHEMA_VERSION = "command_center_3_release_gate_readiness_audit.v1"
MOTION_CLARITY_SCHEMA_VERSION = "command_center_3_motion_clarity_audit.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUSH_GATE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "push_gate_3_0.sh"
SMOKE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "smoke_3_0.sh"
DATA_HEALTH_FRESHNESS_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "data_health_freshness_contract.py"
TUSHARE_ACCEPTANCE_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "tushare_acceptance_contract.py"
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
        "factor_test_lab_contract_is_local": "command_center_3_factor_test_lab_contract.v1" in factor_test_lab_script
        and "local_factor_test_lab_contract_no_provider_execution" in factor_test_lab_script
        and "provider_backed_small_pool_validation_done" in factor_test_lab_script
        and "production_factor_test_validation_complete" in factor_test_lab_script
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
            "factor_test_lab_contract_exists",
            "factor_test_lab_contract_step",
            "factor_test_lab_contract_is_local",
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
        "--motion-ease-emphasized",
    )
    keyframe_markers = (
        "@keyframes cc-route-reveal",
        "@keyframes cc-surface-rise",
        "@keyframes cc-state-clarity",
        "@keyframes cc-chart-clarity",
        "@keyframes cc-clarity-sweep",
        "@keyframes cc-focus-settle",
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
    for path in report_paths[-20:]:
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
    motion_clarity_audit, motion_clarity_rows = _motion_clarity_readiness_audit()
    motion_production_qa_contract, motion_production_qa_rows = _motion_production_qa_contract(
        motion_clarity_audit,
        motion_clarity_rows,
    )
    motion_browser_qa_runbook_contract, motion_browser_qa_runbook_rows, motion_browser_qa_matrix_rows = (
        _motion_browser_qa_runbook_contract()
    )
    motion_browser_qa_evidence_contract, motion_browser_qa_evidence_rows = _motion_browser_qa_evidence_contract()
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
        "motion_clarity_audit": motion_clarity_audit,
        "motion_clarity_rows": motion_clarity_rows,
        "motion_production_qa_contract": motion_production_qa_contract,
        "motion_production_qa_rows": motion_production_qa_rows,
        "motion_browser_qa_runbook_contract": motion_browser_qa_runbook_contract,
        "motion_browser_qa_runbook_rows": motion_browser_qa_runbook_rows,
        "motion_browser_qa_matrix_rows": motion_browser_qa_matrix_rows,
        "motion_browser_qa_evidence_contract": motion_browser_qa_evidence_contract,
        "motion_browser_qa_evidence_rows": motion_browser_qa_evidence_rows,
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
            "motion_clarity_audit_is_static": True,
            "motion_clarity_audit_runs_no_commands": True,
            "motion_clarity_static_ready_is_not_visual_qa": True,
            "motion_production_qa_contract_is_local": True,
            "motion_production_qa_is_not_browser_visual_or_perf_proof": True,
            "motion_browser_qa_runbook_is_local": True,
            "motion_browser_qa_runbook_is_not_browser_execution": True,
            "motion_browser_qa_evidence_is_local_ignored_artifact_summary": True,
            "motion_browser_qa_evidence_is_not_production_completion": True,
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
            "motion_clarity_audit 只读解析本地 React/CSS 源码；static_ready 不是浏览器视觉验收或生产动效完成证明。",
            "motion_production_qa_contract 是本地生产验收清单；不运行浏览器视觉 QA 或性能 trace。",
        ],
    }
    return _json_safe(packet)
