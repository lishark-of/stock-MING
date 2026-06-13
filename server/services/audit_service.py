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
MOTION_VIEWPORT_QA_CONTRACT_PATH = PROJECT_ROOT / "scripts" / "motion_viewport_qa_contract.py"
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
    motion_qa_script = _read_local_text(MOTION_VIEWPORT_QA_CONTRACT_PATH)
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
        "motion_viewport_qa_contract_exists": MOTION_VIEWPORT_QA_CONTRACT_PATH.exists() and bool(motion_qa_script),
        "motion_viewport_qa_contract_step": "scripts/motion_viewport_qa_contract.py" in script
        and "Motion viewport QA contract" in script,
        "uses_project_venv_python": 'PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"' in script,
        "refuses_missing_project_python": "Do not use system Python" in script and 'if [ ! -x "$PYTHON_BIN" ]' in script,
        "python_unittest_step": "-m unittest discover -s tests" in script,
        "desktop_build_step": "cd desktop && npm run build" in script,
        "smoke_step": "scripts/smoke_3_0.sh" in script,
        "diff_check_step": "git diff --check" in script,
        "high_risk_secret_scan_step": "secret_high_risk_scan" in script and "high-risk secret value scan" in script,
        "keyword_review_scan_step": "keyword scan for review" in script,
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
    }
    ci_mirror_ready = any(bool(row.get("mirrors_local_push_gate")) for row in workflow_rows)
    false_positive_allowlist_review_ready = False
    local_gate_ready = all(
        bool(checks[key])
        for key in (
            "push_gate_script_exists",
            "push_gate_script_executable",
            "smoke_script_exists",
            "motion_viewport_qa_contract_exists",
            "motion_viewport_qa_contract_step",
            "motion_viewport_qa_contract_is_local_static",
            "uses_project_venv_python",
            "refuses_missing_project_python",
            "python_unittest_step",
            "desktop_build_step",
            "smoke_step",
            "diff_check_step",
            "high_risk_secret_scan_step",
            "keyword_review_scan_step",
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
        _motion_row("no_timer_or_raf_motion_loop", checks["no_timer_or_raf_motion_loop"], evidence="no setTimeout/requestAnimationFrame motion loop; bounded setInterval is task polling only"),
        _motion_row("no_provider_call_markers", checks["no_provider_call_markers"], evidence="audited motion files contain no provider invocation markers"),
        _motion_row("visual_only_boundary_visible", checks["visual_only_boundary_visible"], evidence="motion state labels remain visual-only and trade guarded"),
        _motion_row("motion_viewport_qa_contract_ready", checks["motion_viewport_qa_contract_ready"], evidence="scripts/motion_viewport_qa_contract.py pins routes, viewports, and pending browser QA state"),
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
        ],
    }
    return _json_safe(packet)
