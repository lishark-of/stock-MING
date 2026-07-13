"""Read-only, evidence-driven Command Center 3.0 v1 closeout evaluation.

Only allowlisted SQLite packets and gitignored local acceptance artifacts are
read.  The evaluator never initializes storage, creates tasks, calls an
external service, or exposes raw packet/account/config payloads.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .tushare_production_store import validate_tushare_full_market_production_version


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"

ROOT_PACKET_KEYS = (
    "command_center_trade_cal_provider_acceptance_packet",
    "command_center_factor_test_provider_small_pool_tushare_packet",
    "command_center_3_qmt_replay_current",
    "command_center_3_qmt_replay_last_good",
    "command_center_deepseek_provider_benchmark_current",
    "command_center_deepseek_provider_benchmark_last_good",
    "command_center_tushare_full_interface_production_packet",
    "command_center_tushare_full_market_universe_production_current",
)
V04_PACKET_KEYS = (
    "command_center_3_storage_physical_execution_phase_a_packet",
    "command_center_3_worker_runtime_qa_execution_packet",
)
V05_PACKET_KEYS = (
    "command_center_3_candidate_radar_v05_last_good_packet",
    "command_center_next_session_projection_packet",
)

_SAFE_PACKET_FIELDS = (
    "schema_version",
    "status",
    "mode",
    "call_count",
    "success_count",
    "failed_count",
    "blocked_count",
    "selected_apis",
    "api_acceptance_audit_passed",
    "pool_count",
    "processed_count",
    "local_phase_a_execution_ready",
    "phase_a_local_evidence_done",
    "v04_duckdb_query_parity",
    "v04_sqlite_readback_verified",
    "production_storage_complete",
    "production_tushare_pipeline_complete",
    "production_replacement_complete",
    "next_session_browser_qa_evidence_ready",
    "next_session_production_promotion_review_ready",
    "next_session_streamlit_parity_review_ready",
    "caller_supplied_export_compatibility_verified",
    "external_qmt_integration_verified",
    "paper_trading_sandbox_ready",
    "external_calls_triggered",
    "external_call_count",
    "qmt_called",
    "qmt_connection_count",
    "qmt_external_connection_attempted",
    "qmt_process_discovered",
    "qmt_client_imported",
    "xtquant_imported",
    "broker_called",
    "broker_session_opened",
    "broker_session_count",
    "account_query_executed",
    "real_order_submitted",
    "real_order_count",
    "real_order_cancelled",
    "real_trade_executed",
    "real_trade_count",
    "real_holdings_modified",
    "real_trading_enabled",
    "tushare_called",
    "deepseek_called",
    "github_called",
    "worker_dispatched",
    "evidence_source",
    "sample_count",
    "json_success_rate",
    "required_json_success_rate",
    "response_format",
    "provider_response_format_enforced",
    "response_schema_validated",
    "safety_review_passed",
    "unsafe_output_accepted_count",
    "model_ledger_count",
    "model_ledger_complete",
    "provider_benchmark_done",
    "production_fact_ready",
    "governed_model_runtime",
    "raw_prompt_stored",
    "raw_output_stored",
    "does_not_execute_trades",
    "does_not_modify_strategy_action",
    "does_not_modify_holdings",
    "contains_secret",
)

_SAFE_FILE_FIELDS = (
    "schema_version",
    "status",
    "row_count",
    "current_version_id",
    "passed_count",
    "review_required_count",
    "route_count",
    "viewport_count",
    "reduced_motion",
    "visual_qa_complete",
    "browser_performance_verified",
    "production_motion_complete",
    "local_packaged_runtime_evidence_ready",
    "backend_offline_packaged_ux_verified",
    "health_ready_during_launch",
    "codesign_verified",
    "developer_id_signing_verified",
    "notarization_ticket_detected",
    "dmg_checksum_verified",
    "dmg_distribution_detected",
    "production_package_complete",
    "latest_remote_run_verified_green",
    "remote_ci_run_observed_for_current_head",
    "artifact_digest_verified",
    "release_gate_complete",
    "release_review_complete",
    "production_release_complete",
    "external_calls_triggered",
    "tushare_called",
    "deepseek_called",
    "github_called",
    "does_not_execute_trades",
    "does_not_modify_strategy_action",
    "contains_secret",
)

_LOCAL_VERSION_REQUIREMENTS = {
    "LTG-01": ("v0.2",),
    "LTG-02": ("v0.2", "v0.3"),
    "LTG-03": ("v0.3",),
    "LTG-04": ("v0.3", "v0.4"),
    "LTG-05": ("v0.4",),
    "LTG-06": ("v0.4",),
    "LTG-07": ("v0.5",),
    "LTG-08": ("v0.5", "v0.6"),
    "LTG-09": ("v0.6",),
    "LTG-10": ("v0.5", "v0.6"),
    "LTG-11": ("v0.6",),
    "LTG-12": ("v0.7",),
    "LTG-13": ("v0.5", "v0.6"),
    "LTG-14": ("v0.6",),
}

_PRODUCTION_REQUIREMENTS = {
    "LTG-01": ("trade_cal_provider_direct", "release_promotion_current_head"),
    "LTG-02": ("full_interface_provider_production", "release_promotion_current_head"),
    "LTG-03": ("factor_small_pool_provider_direct", "factor_production_promotion", "release_promotion_current_head"),
    "LTG-04": ("full_market_worker_runtime", "production_storage", "release_promotion_current_head"),
    "LTG-05": ("production_storage", "release_promotion_current_head"),
    "LTG-06": ("celery_redis_runtime", "release_promotion_current_head"),
    "LTG-07": ("governed_model_runtime", "release_promotion_current_head"),
    "LTG-08": ("next_session_production_replacement", "release_promotion_current_head"),
    "LTG-09": ("desktop_production_package", "developer_signing_notarization", "release_promotion_current_head"),
    "LTG-10": ("streamlit_primary_retired", "release_promotion_current_head"),
    "LTG-11": ("remote_ci_current_head", "release_promotion_current_head"),
    "LTG-13": (
        "candidate_radar_production_replacement",
        "full_market_worker_runtime",
        "release_promotion_current_head",
    ),
    "LTG-14": ("motion_production_promoted", "release_promotion_current_head"),
}


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_head_full(value: object) -> str:
    candidate = str(value or "").strip().lower()
    if len(candidate) not in {40, 64}:
        return ""
    if any(character not in "0123456789abcdef" for character in candidate):
        return ""
    return candidate


def _read_current_head_full(project_root: Path | None = None) -> str:
    root = project_root if project_root is not None else PROJECT_ROOT
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return _normalize_head_full(result.stdout)


def _canonical_value_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _safe_projection(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    projection: dict[str, Any] = {}
    for field in fields:
        item = source.get(field)
        if isinstance(item, (str, int, float, bool)) or item is None:
            projection[field] = item
        elif field == "selected_apis" and isinstance(item, list):
            projection[field] = [str(api) for api in item if str(api)]
    return projection


def _safe_summary(value: Any, fields: tuple[str, ...], *, observed: bool) -> dict[str, Any]:
    projection = _safe_projection(value, fields)
    return {
        "observed": observed,
        "schema_version": str(projection.get("schema_version") or "missing"),
        "status": str(projection.get("status") or "missing"),
        "safe_fields": projection if observed else {},
        "safe_evidence_digest": _canonical_digest(projection) if observed else "",
        "raw_payload_exposed": False,
    }


def _read_packets(db_path: Path, packet_keys: tuple[str, ...]) -> dict[str, Any]:
    if not db_path.is_file():
        return {}
    connection: sqlite3.Connection | None = None
    try:
        uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        placeholders = ",".join("?" for _ in packet_keys)
        rows = connection.execute(
            f"SELECT packet_key, payload_json FROM packets WHERE packet_key IN ({placeholders})",
            packet_keys,
        ).fetchall()
    except Exception:
        return {}
    finally:
        if connection is not None:
            connection.close()
    packets: dict[str, Any] = {}
    for packet_key, payload_json in rows:
        try:
            payload = json.loads(payload_json)
        except Exception:
            continue
        if isinstance(payload, Mapping):
            packets[str(packet_key)] = payload
    return packets


def _read_task_history(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []
    connection: sqlite3.Connection | None = None
    try:
        uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        rows = connection.execute("SELECT payload_json FROM task_status").fetchall()
    except Exception:
        return []
    finally:
        if connection is not None:
            connection.close()
    history: list[dict[str, Any]] = []
    for (payload_json,) in rows:
        try:
            payload = json.loads(payload_json)
        except Exception:
            continue
        if isinstance(payload, Mapping):
            history.append(
                {
                    "task_type": str(payload.get("task_type") or ""),
                    "status": str(payload.get("status") or ""),
                    "current_step": str(payload.get("current_step") or ""),
                }
            )
    return history


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, Mapping) else None


def _latest_json(root: Path, pattern: str) -> Any:
    if not root.is_dir():
        return None
    paths = sorted(path for path in root.glob(pattern) if path.is_file())
    return _read_json(paths[-1]) if paths else None


def _boundary_safe(value: Any, *, external_expected: bool = False) -> bool:
    source = value if isinstance(value, Mapping) else {}
    if source.get("contains_secret") is True:
        return False
    if source.get("does_not_execute_trades") is not True:
        return False
    if source.get("does_not_modify_strategy_action") is not True:
        return False
    if source.get("deepseek_called") is True or source.get("github_called") is True:
        return False
    if not external_expected and source.get("external_calls_triggered") is True:
        return False
    return True


def _provider_ready(packet: Any, required_apis: set[str]) -> bool:
    source = packet if isinstance(packet, Mapping) else {}
    selected = {str(api) for api in source.get("selected_apis") or []}
    return bool(
        source.get("status") == "success"
        and int(source.get("call_count") or 0) > 0
        and int(source.get("success_count") or 0) > 0
        and int(source.get("failed_count") or 0) == 0
        and int(source.get("blocked_count") or 0) == 0
        and required_apis.issubset(selected)
        and source.get("tushare_called") is True
        and source.get("external_calls_triggered") is True
        and _boundary_safe(source, external_expected=True)
    )


_FULL_INTERFACE_APIS = {
    "daily", "daily_basic", "moneyflow", "trade_cal", "margin_detail", "top_list",
    "top_inst", "stk_limit", "limit_list_d", "limit_cpt_list", "cyq_perf", "cyq_chips",
    "anns_d", "forecast", "fina_indicator", "stk_holdertrade", "share_float", "pledge_stat",
    "pledge_detail", "stk_surv",
}
_FULL_INTERFACE_TARGETS = {
    "chip_distribution", "margin_financing", "dragon_tiger", "limit_emotion",
    "trade_calendar", "financial_disclosure", "hard_risk",
}
_PARQUET_APIS = {"daily", "daily_basic", "moneyflow", "trade_cal"}


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in {"token", "api_key", "apikey", "secret", "password", "credential"}:
                return True
            if _contains_sensitive_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _parquet_artifact_readback_matches(record: Any) -> bool:
    if not isinstance(record, Mapping):
        return False
    path = Path(str(record.get("versioned_path") or record.get("canonical_path") or ""))
    digest = str(record.get("sha256") or record.get("canonical_digest") or "")
    required_columns = [str(column) for column in record.get("required_columns") or []]
    if not path.is_file() or len(digest) != 64:
        return False
    try:
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(path)
        row_count = int(parquet.metadata.num_rows) if parquet.metadata is not None else 0
        columns = {str(column) for column in parquet.schema_arrow.names}
    except Exception:
        return False
    expected_rows = int(record.get("rows") or record.get("row_count") or 0)
    return bool(
        hashlib.sha256(path.read_bytes()).hexdigest() == digest
        and row_count == expected_rows > 0
        and set(required_columns).issubset(columns)
    )


def _legacy_full_interface_packet_internally_consistent(packet: Any) -> bool:
    """Compatibility audit only; never used as production closeout truth."""
    source = packet if isinstance(packet, Mapping) else {}
    contract = source.get("production_contract") if isinstance(source.get("production_contract"), Mapping) else {}
    ledger = [row for row in source.get("call_ledger", []) if isinstance(row, Mapping)]
    selected = [str(api) for api in source.get("selected_apis") or []]
    targets = [str(target) for target in source.get("required_target_groups") or []]
    provider_scope = source.get("provider_scope") if isinstance(source.get("provider_scope"), Mapping) else {}
    scope_hash = str(provider_scope.get("scope_hash") or "")
    recipe_hash = str(source.get("execution_recipe_scope_hash") or "")
    recipe_version = str(source.get("execution_recipe_version") or "")
    api_contexts = source.get("api_contexts") if isinstance(source.get("api_contexts"), Mapping) else {}
    target_contexts = source.get("target_contexts") if isinstance(source.get("target_contexts"), Mapping) else {}
    universe_context = source.get("universe_context") if isinstance(source.get("universe_context"), Mapping) else {}
    approval_material = {
        "schema_version": "tushare_full_interface_provider_approval_scope.v1",
        "recipe_scope_hash": recipe_hash,
        "recipe_version": recipe_version,
        "selected_apis": sorted(selected),
        "requested_targets": sorted(targets),
        "api_contexts": dict(api_contexts),
        "target_contexts": dict(target_contexts),
        "universe_context": dict(universe_context),
    }
    approval_hash = _canonical_digest(approval_material)
    provider_rows = [row for row in ledger if str(row.get("api") or "") in _FULL_INTERFACE_APIS]
    ledger_ready = bool(
        len(provider_rows) == len(_FULL_INTERFACE_APIS)
        and {str(row.get("api") or "") for row in provider_rows} == _FULL_INTERFACE_APIS
        and all(
            row.get("runtime_adapter_module_identity_verified") is True
            and row.get("provider_transport_verified") is True
            and int(row.get("provider_transport_receipt_count") or 0) > 0
            and (
                row.get("representative_sample_verified") is True
                or row.get("valid_empty_semantics_verified") is True
            )
            and row.get("scope_hash") == scope_hash
            and row.get("authoritative_recipe_scope_hash") == recipe_hash
            and row.get("approval_scope_hash") == approval_hash
            and row.get("approval_scope_matches") is True
            and not _contains_sensitive_key(row.get("request_params_safe"))
            for row in provider_rows
        )
    )
    parquet = source.get("parquet_promotion") if isinstance(source.get("parquet_promotion"), Mapping) else {}
    parquet_rows = [row for row in parquet.get("rows", []) if isinstance(row, Mapping)]
    parquet_ready = bool(
        parquet.get("promotion_verified") is True
        and int(parquet.get("promoted_dataset_count") or 0) == len(_PARQUET_APIS)
        and {str(row.get("api") or "") for row in parquet_rows} == _PARQUET_APIS
        and all(
            _parquet_artifact_readback_matches(
                {
                    **dict(row),
                    "row_count": row.get("parquet_row_count") or row.get("row_count"),
                    "required_columns": row.get("required_columns") or [],
                }
            )
            for row in parquet_rows
        )
    )
    digest_material = dict(source)
    immutable_digest = str(digest_material.pop("immutable_packet_digest", "") or "")
    return bool(
        source.get("schema_version") == "command_center_tushare_full_interface_production_packet.v1"
        and source.get("status") == "full_interface_provider_production_complete"
        and source.get("full_interface_provider_production") is True
        and source.get("production_tushare_pipeline_complete") is True
        and len(selected) == len(_FULL_INTERFACE_APIS)
        and set(selected) == _FULL_INTERFACE_APIS
        and len(targets) == len(_FULL_INTERFACE_TARGETS)
        and set(targets) == _FULL_INTERFACE_TARGETS
        and len(scope_hash) == 64
        and len(recipe_hash) == 64
        and recipe_version == "tushare_full_interface_provider_recipe.v2"
        and source.get("approval_scope_matches") is True
        and str(source.get("approval_scope_hash") or "") == approval_hash
        and contract.get("schema_version") == "tushare_full_interface_provider_production_acceptance.v2"
        and contract.get("status") == "full_interface_provider_production_complete"
        and contract.get("scope_hash") == scope_hash
        and contract.get("full_interface_provider_production") is True
        and contract.get("production_tushare_pipeline_complete") is True
        and contract.get("parquet_promotion_verified") is True
        and contract.get("sqlite_stage_readback_verified") is True
        and contract.get("sqlite_atomic_promotion_verified") is True
        and int(contract.get("blocking_criterion_count") or 0) == 0
        and not contract.get("blockers")
        and ledger_ready
        and parquet_ready
        and source.get("sqlite_stage_readback_verified") is True
        and source.get("sqlite_atomic_promotion_verified") is True
        and len(immutable_digest) == 64
        and immutable_digest == _canonical_digest(digest_material)
        and _boundary_safe(source, external_expected=True)
        and source.get("tushare_called") is True
        and source.get("external_calls_triggered") is True
        and not _contains_sensitive_key(source)
    )


def _legacy_full_market_packet_internally_consistent(packet: Any) -> bool:
    """Compatibility audit only; never used as production closeout truth."""
    source = packet if isinstance(packet, Mapping) else {}
    artifacts = source.get("artifacts") if isinstance(source.get("artifacts"), Mapping) else {}
    ledger = [row for row in source.get("direct_ledger", []) if isinstance(row, Mapping)]
    digest_material = dict(source)
    packet_digest = str(digest_material.pop("packet_digest", "") or "")
    required = {"stock_basic", "trade_cal", "daily", "daily_basic", "moneyflow"}
    pointer = source.get("current_pointer") if isinstance(source.get("current_pointer"), Mapping) else {}
    lineage = pointer.get("lineage") if isinstance(pointer.get("lineage"), Mapping) else {}
    files_ready = bool(
        set(artifacts) == required
        and all(isinstance(record, Mapping) for record in artifacts.values())
        and all(
            record.get("required_columns")
            and _parquet_artifact_readback_matches(record)
            for record in artifacts.values()
        )
    )
    validation = source.get("dataset_validation") if isinstance(source.get("dataset_validation"), Mapping) else {}
    return bool(
        source.get("schema_version") == "tushare_full_market_universe_production.v1"
        and source.get("status") == "full_market_universe_production_complete"
        and source.get("production_complete") is True
        and len(str(source.get("scope_hash") or "")) == 64
        and len(str(source.get("approval_scope_hash") or "")) == 64
        and len(str(source.get("execution_recipe_scope_hash") or "")) == 64
        and source.get("list_status") == "L"
        and int(source.get("row_count") or 0) >= 3000
        and int(source.get("scored_symbol_count") or 0) >= 3000
        and int(source.get("duplicate_count") or 0) == 0
        and int(source.get("invalid_symbol_count") or 0) == 0
        and set(source.get("markets") or []) == {"SH", "SZ", "BJ"}
        and int(source.get("feature_session_count") or 0) == 90
        and source.get("validated_trade_date")
        and source.get("as_of")
        and source.get("freshness") == "current_trade_calendar_validated"
        and source.get("provider_provenance_verified") is True
        and pointer.get("status") == "ready"
        and pointer.get("scope_hash") == source.get("scope_hash")
        and lineage.get("approval_scope_hash") == source.get("approval_scope_hash")
        and lineage.get("execution_recipe_scope_hash") == source.get("execution_recipe_scope_hash")
        and lineage.get("validated_trade_date") == source.get("validated_trade_date")
        and lineage.get("as_of") == source.get("as_of")
        and lineage.get("provider_provenance_verified") is True
        and lineage.get("direct_ledger_digest") == _canonical_value_digest(ledger)
        and {str(row.get("api") or "") for row in ledger} == required
        and all(
            row.get("provider_transport_verified") is True
            and row.get("scope_hash") == source.get("scope_hash")
            and row.get("approval_scope_hash") == source.get("approval_scope_hash")
            and row.get("execution_recipe_scope_hash") == source.get("execution_recipe_scope_hash")
            and row.get("as_of") == source.get("as_of")
            for row in ledger
        )
        and all(
            isinstance(validation.get(api), Mapping)
            and validation[api].get("coverage_complete") is True
            and int(validation[api].get("duplicate_count") or 0) == 0
            and not validation[api].get("missing_required_columns")
            for api in ("daily", "daily_basic", "moneyflow")
        )
        and files_ready
        and len(packet_digest) == 64
        and packet_digest == _canonical_digest(digest_material)
        and _boundary_safe(source, external_expected=True)
        and not _contains_sensitive_key(source)
def _governed_model_runtime_ready(packet: Any) -> bool:
    source = packet if isinstance(packet, Mapping) else {}
    sample_count = int(source.get("sample_count") or 0)
    success_count = int(source.get("success_count") or 0)
    threshold = float(source.get("required_json_success_rate") or 0.0)
    success_rate = float(source.get("json_success_rate") or 0.0)
    return bool(
        source.get("schema_version") == "factor_deepseek_provider_benchmark_result.v1"
        and source.get("status") == "deepseek_provider_benchmark_passed"
        and source.get("evidence_source") == "real_provider"
        and sample_count == 40
        and success_count >= 36
        and threshold >= 0.9
        and success_rate >= threshold
        and source.get("response_format") == "json_schema"
        and source.get("provider_response_format_enforced") is True
        and source.get("response_schema_validated") is True
        and source.get("safety_review_passed") is True
        and int(source.get("unsafe_output_accepted_count") or 0) == 0
        and int(source.get("model_ledger_count") or 0) >= sample_count
        and source.get("model_ledger_complete") is True
        and source.get("provider_benchmark_done") is True
        and source.get("production_fact_ready") is True
        and source.get("governed_model_runtime") is True
        and source.get("raw_prompt_stored") is False
        and source.get("raw_output_stored") is False
        and source.get("contains_secret") is False
        and source.get("external_calls_triggered") is True
        and source.get("deepseek_called") is True
        and source.get("tushare_called") is False
        and source.get("github_called") is False
        and source.get("does_not_execute_trades") is True
        and source.get("does_not_modify_strategy_action") is True
    )


def _qmt_isolation_ready(packet: Any) -> bool:
    source = packet if isinstance(packet, Mapping) else {}
    false_fields = (
        "external_calls_triggered",
        "qmt_called",
        "qmt_external_connection_attempted",
        "qmt_process_discovered",
        "qmt_client_imported",
        "xtquant_imported",
        "broker_called",
        "broker_session_opened",
        "account_query_executed",
        "real_order_submitted",
        "real_order_cancelled",
        "real_trade_executed",
        "real_holdings_modified",
        "real_trading_enabled",
        "external_qmt_integration_verified",
        "paper_trading_sandbox_ready",
        "worker_dispatched",
    )
    zero_fields = (
        "external_call_count",
        "qmt_connection_count",
        "broker_session_count",
        "real_order_count",
        "real_trade_count",
    )
    accepted_statuses = {
        "local_export_contract_and_replay_verified",
        "local_scope_replay_verified_export_pending",
    }
    return bool(
        source.get("schema_version") == "qmt_readonly_local_replay_result.v1"
        and source.get("status") in accepted_statuses
        and source.get("mode") == "local_research_replay"
        and all(source.get(field) is False for field in false_fields)
        and all(int(source.get(field) or 0) == 0 for field in zero_fields)
        and source.get("does_not_modify_holdings") is True
        and _boundary_safe(source)
    )


def _version_row(
    version: str,
    source_summaries: list[dict[str, Any]],
    ready: bool,
    blockers: list[str],
) -> dict[str, Any]:
    digest_material = {
        "version": version,
        "ready": ready,
        "source_digests": [row.get("safe_evidence_digest") or "" for row in source_summaries],
        "blockers": blockers,
    }
    return {
        "version": version,
        "local_direct_evidence_ready": ready,
        "observed_source_count": sum(1 for row in source_summaries if row.get("observed") is True),
        "required_source_count": len(source_summaries),
        "source_summaries": source_summaries,
        "blockers": blockers,
        "safe_evidence_digest": _canonical_digest(digest_material),
        "evidence_boundary": "read_only_sanitized_local_version_evidence_not_production_promotion",
    }


def _build_version_rows(
    evidence_root: Path,
    *,
    expected_head_full: str,
) -> tuple[list[dict[str, Any]], dict[str, bool], dict[str, Any]]:
    root_packets = _read_packets(evidence_root / "meta.sqlite", ROOT_PACKET_KEYS)
    v04_db = evidence_root / "v04_acceptance_runtime" / "runtime_meta.sqlite"
    v05_db = evidence_root / "v05_acceptance_runtime" / "meta.sqlite"
    v04_packets = _read_packets(v04_db, V04_PACKET_KEYS)
    v05_packets = _read_packets(v05_db, V05_PACKET_KEYS)

    home_qa = _latest_json(evidence_root / "user_route_home_after_collapse_smoke", "**/user_route_qa_report.json")
    factor_qa = _latest_json(evidence_root / "user_route_factor_after_amend_smoke", "**/user_route_qa_report.json")
    trade_cal = root_packets.get(ROOT_PACKET_KEYS[0])
    factor = root_packets.get(ROOT_PACKET_KEYS[1])
    storage = v04_packets.get(V04_PACKET_KEYS[0])
    worker = v04_packets.get(V04_PACKET_KEYS[1])
    candidate = v05_packets.get(V05_PACKET_KEYS[0])
    next_session = v05_packets.get(V05_PACKET_KEYS[1])

    v04_manifest = _latest_json(evidence_root / "v04_acceptance_runtime", "*/manifest.json")
    v04_history = _read_task_history(v04_db)
    storage_success_history = any(
        row["task_type"] == "run_storage_physical_execution_phase_a"
        and row["status"] == "success"
        and row["current_step"] == "storage_physical_execution_phase_a_v04_durable_execution_success"
        for row in v04_history
    )

    offline_desktop = _read_json(evidence_root / "desktop_runtime" / "tauri_packaged_runtime_offline_smoke.json")
    online_desktop = _read_json(evidence_root / "desktop_runtime" / "tauri_packaged_runtime_online_smoke.json")
    latest_default: Any = None
    latest_reduced: Any = None
    motion_root = evidence_root / "motion_qa"
    motion_paths = (
        sorted(motion_root.glob("**/motion_browser_qa_report.json"), reverse=True)
        if motion_root.is_dir()
        else []
    )
    for path in motion_paths:
        report = _read_json(path)
        passed = bool(
            isinstance(report, Mapping)
            and report.get("status") == "motion_browser_qa_passed"
            and int(report.get("passed_count") or 0) > 0
            and int(report.get("review_required_count") or 0) == 0
            and report.get("visual_qa_complete") is True
            and report.get("browser_performance_verified") is True
            and _boundary_safe(report)
        )
        if not passed:
            continue
        if report.get("reduced_motion") is True and latest_reduced is None:
            latest_reduced = report
        if report.get("reduced_motion") is False and latest_default is None:
            latest_default = report
        if latest_default is not None and latest_reduced is not None:
            break

    qmt_current = root_packets.get(ROOT_PACKET_KEYS[2])
    qmt_last_good = root_packets.get(ROOT_PACKET_KEYS[3])
    production_version = validate_tushare_full_market_production_version(evidence_root)
    qmt = qmt_current if _qmt_isolation_ready(qmt_current) else qmt_last_good
    model_current = root_packets.get(ROOT_PACKET_KEYS[4])
    model_last_good = root_packets.get(ROOT_PACKET_KEYS[5])
    governed_model = model_current if _governed_model_runtime_ready(model_current) else model_last_good

    user_qa_ready = lambda value: bool(
        isinstance(value, Mapping)
        and value.get("schema_version") == "command_center_3_user_route_qa_result.v1"
        and value.get("status") == "user_route_qa_passed"
        and int(value.get("passed_count") or 0) > 0
        and _boundary_safe(value)
    )
    v04_manifest_ready = bool(
        isinstance(v04_manifest, Mapping)
        and v04_manifest.get("schema_version") == "storage_v04_durable_execution_manifest.v1"
        and int(v04_manifest.get("row_count") or 0) > 0
        and v04_manifest.get("contains_secret") is not True
    )
    worker_ready = bool(
        isinstance(worker, Mapping)
        and worker.get("schema_version") == "worker_v04_local_batch_runtime_packet.v1"
        and worker.get("status") == "worker_v04_local_batch_runtime_success"
        and int(worker.get("pool_count") or 0) > 0
        and int(worker.get("processed_count") or 0) == int(worker.get("pool_count") or 0)
        and worker.get("contains_secret") is not True
    )
    candidate_ready = bool(
        isinstance(candidate, Mapping)
        and candidate.get("schema_version") == "candidate_radar_cache.v1"
        and candidate.get("status") == "candidate_radar_v05_local_batch_ready"
        and _boundary_safe(candidate)
    )
    next_ready = bool(
        isinstance(next_session, Mapping)
        and next_session.get("schema_version") == "next_session_projection.v1"
        and next_session.get("status") == "ready_cache_replay"
        and next_session.get("next_session_browser_qa_evidence_ready") is True
        and _boundary_safe(next_session)
    )
    desktop_ready = lambda value: bool(
        isinstance(value, Mapping)
        and value.get("schema_version") == "tauri_packaged_runtime_smoke.v1"
        and value.get("status") == "tauri_packaged_runtime_smoke_passed"
        and value.get("local_packaged_runtime_evidence_ready") is True
        and value.get("dmg_checksum_verified") is True
        and _boundary_safe(value)
    )

    specs = [
        ("v0.1", [home_qa], user_qa_ready(home_qa), ["home_user_route_qa_missing_or_failed"]),
        (
            "v0.2",
            [trade_cal],
            _provider_ready(trade_cal, {"trade_cal"}),
            ["trade_cal_provider_acceptance_missing_or_failed"],
        ),
        (
            "v0.3",
            [factor, factor_qa],
            _provider_ready(factor, {"daily", "daily_basic"}) and user_qa_ready(factor_qa),
            ["factor_provider_or_user_route_evidence_missing"],
        ),
        (
            "v0.4",
            [storage, worker, v04_manifest],
            storage_success_history and worker_ready and v04_manifest_ready,
            ["storage_worker_runtime_acceptance_missing"],
        ),
        (
            "v0.5",
            [candidate, next_session],
            candidate_ready and next_ready,
            ["candidate_next_session_acceptance_missing"],
        ),
        (
            "v0.6",
            [offline_desktop, online_desktop, latest_default, latest_reduced],
            desktop_ready(offline_desktop)
            and desktop_ready(online_desktop)
            and latest_default is not None
            and latest_reduced is not None,
            ["desktop_or_motion_acceptance_missing"],
        ),
        ("v0.7", [qmt], _qmt_isolation_ready(qmt), ["qmt_research_isolation_receipt_missing_or_unsafe"]),
    ]
    rows: list[dict[str, Any]] = []
    for version, sources, ready, blockers in specs:
        fields = (
            _SAFE_PACKET_FIELDS
            if version in {"v0.2", "v0.3", "v0.4", "v0.5", "v0.7"}
            else _SAFE_FILE_FIELDS
        )
        summaries = [
            _safe_summary(source, fields, observed=isinstance(source, Mapping))
            for source in sources
        ]
        rows.append(_version_row(version, summaries, ready, [] if ready else blockers))

    release_receipt = _read_json(evidence_root / "release_gate" / "release_gate_review_receipt.json")
    remote_receipt = _read_json(evidence_root / "release_gate" / "remote_ci_review_receipt.json")
    facts = {
        "trade_cal_provider_direct": _provider_ready(trade_cal, {"trade_cal"}),
        "factor_small_pool_provider_direct": _provider_ready(factor, {"daily", "daily_basic"}),
        "full_interface_provider_production": production_version.get("ready") is True,
        "factor_production_promotion": bool(
            isinstance(factor, Mapping)
            and factor.get("production_tushare_pipeline_complete") is True
        ),
        "production_storage": bool(
            isinstance(storage, Mapping) and storage.get("production_storage_complete") is True
        ),
        "full_market_worker_runtime": False,
        "celery_redis_runtime": False,
        "governed_model_runtime": _governed_model_runtime_ready(governed_model),
        "next_session_production_replacement": bool(
            isinstance(next_session, Mapping)
            and next_session.get("production_replacement_complete") is True
        ),
        "candidate_radar_production_replacement": False,
        "streamlit_primary_retired": False,
        "desktop_production_package": bool(
            isinstance(online_desktop, Mapping)
            and online_desktop.get("production_package_complete") is True
        ),
        "developer_signing_notarization": bool(
            isinstance(online_desktop, Mapping)
            and online_desktop.get("developer_id_signing_verified") is True
            and online_desktop.get("notarization_ticket_detected") is True
        ),
        "motion_production_promoted": bool(
            latest_default
            and latest_reduced
            and latest_default.get("production_motion_complete") is True
            and latest_reduced.get("production_motion_complete") is True
        ),
        "remote_ci_current_head": bool(
            isinstance(remote_receipt, Mapping)
            and expected_head_full
            and _normalize_head_full(remote_receipt.get("head_full")) == expected_head_full
            and remote_receipt.get("latest_remote_run_verified_green") is True
            and remote_receipt.get("remote_ci_run_observed_for_current_head") is True
            and remote_receipt.get("artifact_digest_verified") is True
        ),
        "release_promotion_current_head": bool(
            isinstance(release_receipt, Mapping)
            and release_receipt.get("release_gate_complete") is True
            and release_receipt.get("release_review_complete") is True
            and release_receipt.get("production_release_complete") is True
        ),
        "qmt_research_isolation": _qmt_isolation_ready(qmt),
    }
    context = {
        "qmt_summary": _safe_summary(qmt, _SAFE_PACKET_FIELDS, observed=isinstance(qmt, Mapping)),
        "governed_model_summary": _safe_summary(
            governed_model,
            _SAFE_PACKET_FIELDS,
            observed=isinstance(governed_model, Mapping),
        ),
        "release_receipt_summary": _safe_summary(
            release_receipt,
            _SAFE_FILE_FIELDS,
            observed=isinstance(release_receipt, Mapping),
        ),
        "remote_receipt_summary": _safe_summary(
            remote_receipt,
            _SAFE_FILE_FIELDS,
            observed=isinstance(remote_receipt, Mapping),
        ),
        "tushare_production_version": {
            key: production_version.get(key)
            for key in (
                "ready",
                "status",
                "scope_hash",
                "approval_scope_hash",
                "execution_recipe_scope_hash",
                "validated_trade_date",
                "as_of",
                "universe_digest",
                "universe_count",
                "current_listed_count",
                "current_listed_digest",
                "excluded_recent_symbols",
                "excluded_recent_count",
                "excluded_recent_digest",
                "scored_universe_policy",
                "artifact_manifest_digest",
                "version_digest",
                "blockers",
            )
        },
    }
    return rows, facts, context


def _build_ltg_rows(version_rows: list[dict[str, Any]], facts: Mapping[str, bool]) -> list[dict[str, Any]]:
    version_ready = {str(row["version"]): row.get("local_direct_evidence_ready") is True for row in version_rows}
    rows: list[dict[str, Any]] = []
    for index in range(1, 15):
        goal_id = f"LTG-{index:02d}"
        required_versions = list(_LOCAL_VERSION_REQUIREMENTS[goal_id])
        missing_local = [version for version in required_versions if not version_ready.get(version, False)]
        local_ready = not missing_local
        if goal_id == "LTG-12":
            production_requirements = ["qmt_research_isolation"]
            missing_production = [] if facts.get("qmt_research_isolation") is True else production_requirements
            production_complete = local_ready and not missing_production
            blockers = [f"local_direct_evidence_missing:{version}" for version in missing_local]
        else:
            production_requirements = list(_PRODUCTION_REQUIREMENTS[goal_id])
            missing_production = [name for name in production_requirements if facts.get(name) is not True]
            production_complete = local_ready and not missing_production
            blockers = [f"local_direct_evidence_missing:{version}" for version in missing_local]
            blockers.extend(f"external_or_environment_evidence_missing:{name}" for name in missing_production)
        row = {
            "id": goal_id,
            "local_direct_evidence_ready": local_ready,
            "required_local_versions": required_versions,
            "missing_local_direct_evidence": missing_local,
            "required_production_evidence": production_requirements,
            "missing_production_evidence": missing_production,
            "external_or_environment_blockers": blockers,
            "production_complete": production_complete,
            "can_close": production_complete,
            "closeout_decision": "strict_closeout_allowed" if production_complete else "strict_closeout_blocked",
            "evidence_boundary": "direct_evidence_and_explicit_production_facts_required_no_label_only_closeout",
        }
        if goal_id == "LTG-12":
            row.update(
                {
                    "goal_scope": "research_trade_isolation_only",
                    "future_real_trading_is_separate_unapproved_scope": True,
                    "future_real_trading_blockers": [
                        "broker_connection_not_authorized",
                        "real_order_path_not_authorized",
                        "real_trading_not_implemented",
                    ],
                }
            )
        rows.append(row)
    return rows


def build_v1_closeout_evaluation(
    *,
    evidence_root: Path | None = None,
    expected_head_full: str | None = None,
) -> dict[str, Any]:
    root = evidence_root if evidence_root is not None else EVIDENCE_ROOT
    authoritative_head_full = (
        _normalize_head_full(expected_head_full)
        if expected_head_full is not None
        else _read_current_head_full()
    )
    version_rows, facts, context = _build_version_rows(
        root,
        expected_head_full=authoritative_head_full,
    )
    ltg_rows = _build_ltg_rows(version_rows, facts)
    version_ready_count = sum(1 for row in version_rows if row.get("local_direct_evidence_ready") is True)
    closeout_count = sum(1 for row in ltg_rows if row.get("can_close") is True)
    goal_count = len(ltg_rows)
    local_rc_ready = version_ready_count == len(version_rows)
    production_closeout_complete = closeout_count == goal_count
    return {
        "packet_key": "command_center_3_v1_local_rc",
        "schema_version": "command_center_3_v1_local_rc.v1",
        "status": (
            "v1_local_evidence_ready_production_closeout_complete"
            if local_rc_ready and production_closeout_complete
            else "v1_local_evidence_ready_production_closeout_pending"
            if local_rc_ready
            else "v1_local_evidence_incomplete_production_closeout_pending"
        ),
        "mode": "read_only_local_evidence_closeout",
        "local_direct_evidence_ready": local_rc_ready,
        "local_version_ready_count": version_ready_count,
        "local_version_total_count": len(version_rows),
        "missing_local_versions": [
            row["version"]
            for row in version_rows
            if row.get("local_direct_evidence_ready") is not True
        ],
        "production_strict_closeout_complete": production_closeout_complete,
        "strict_closeout": f"{closeout_count}/{goal_count}",
        "strict_closeout_done_count": closeout_count,
        "strict_closeout_total_count": goal_count,
        "strict_closeout_remaining_count": goal_count - closeout_count,
        "version_evidence_rows": version_rows,
        "ltg_closure_rows": ltg_rows,
        "production_fact_rows": [
            {"evidence_key": key, "observed": value is True}
            for key, value in sorted(facts.items())
        ],
        "qmt_research_isolation_summary": context["qmt_summary"],
        "governed_model_runtime_summary": context["governed_model_summary"],
        "release_review_summary": context["release_receipt_summary"],
        "remote_ci_review_summary": context["remote_receipt_summary"],
        "tushare_production_version": context["tushare_production_version"],
        "cache_only": True,
        "read_only": True,
        "creates_task": False,
        "writes_storage": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "qmt_called": False,
        "broker_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "raw_packet_payloads_exposed": False,
        "raw_account_or_config_exposed": False,
        "evidence_boundary": "v1_local_rc_is_local_direct_evidence_summary_production_strict_closeout_is_separate",
    }
