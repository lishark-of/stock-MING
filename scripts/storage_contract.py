#!/usr/bin/env python3
"""Validate the local LTG-05 Storage production-boundary contract.

This push-gate guard is not a storage migration. It reads local storage cache
contracts and dry-run packet builders to keep schema/version/partition,
compaction, TTL, DuckDB query, and cleanup preflights separate from physical
production storage completion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import storage_service, task_service  # noqa: E402


REQUIRED_BLOCKER_CRITERIA = {
    "schema_physical_validation_complete",
    "schema_migration_executed",
    "dataset_version_manifest_validated",
    "partition_migration_executed",
    "physical_compaction_executed",
    "cache_ttl_refresh_pipeline_executed",
    "artifact_cleanup_manual_review_visible",
    "cache_get_remains_read_only",
}
REQUIRED_STORAGE_TASK_TYPES = {
    "run_storage_artifact_cleanup_dry_run",
    "run_storage_schema_validation_dry_run",
    "run_storage_dataset_version_manifest_dry_run",
    "run_storage_dataset_version_manifest_write",
    "run_storage_partition_migration_dry_run",
    "run_storage_compaction_dry_run",
    "run_storage_cache_ttl_dry_run",
}


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _storage_task_rows() -> dict[str, dict[str, Any]]:
    return {
        str(row.get("task_type") or ""): dict(row)
        for row in task_service.TASK_CATALOG
        if isinstance(row, dict) and row.get("task_type") in REQUIRED_STORAGE_TASK_TYPES
    }


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def build_contract() -> dict[str, Any]:
    overview = storage_service.storage_overview()
    catalog = storage_service.storage_dataset_catalog()
    schema_packet = storage_service.storage_schema_validation_dry_run_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    manifest_packet = storage_service.storage_dataset_version_manifest_dry_run_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    partition_packet = storage_service.storage_partition_migration_dry_run_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    compaction_packet = storage_service.storage_compaction_dry_run_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    ttl_packet = storage_service.storage_cache_ttl_dry_run_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    cleanup_packet = storage_service.storage_artifact_cleanup_dry_run_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    production_readiness = _dict(overview.get("production_readiness"))
    blocker_audit = _dict(overview.get("storage_production_blocker_audit"))
    blocker_criteria = {
        str(row.get("criterion") or "")
        for row in _list(overview.get("storage_production_blocker_rows"))
        if isinstance(row, dict)
    }
    schema_preflight = _dict(overview.get("schema_migration_preflight"))
    dataset_version_policy = _dict(overview.get("dataset_version_policy"))
    dataset_version_manifest_evidence = _dict(overview.get("dataset_version_manifest_evidence_audit"))
    duckdb_policy = _dict(overview.get("duckdb_query_service"))
    duckdb_rows = [row for row in _list(overview.get("duckdb_query_service_rows")) if isinstance(row, dict)]
    cleanup_review = _dict(overview.get("artifact_cleanup_review_contract"))
    task_rows = _storage_task_rows()
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/storage_contract.py")

    canonical_datasets = set(storage_service.CANONICAL_PARQUET_DATASETS)
    catalog_datasets = {
        str(row.get("dataset") or "")
        for row in _list(catalog.get("dataset_catalog"))
        if isinstance(row, dict)
    }
    overview_datasets = set(_dict(overview.get("dataset_status")).keys())

    rows = [
        _row(
            "storage_overview_cache_is_read_only",
            overview.get("schema_version") == "command_center_3_storage_overview.v1"
            and overview.get("cache_only") is True
            and _flag_false(overview, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and overview.get("does_not_execute_trades") is True
            and overview.get("does_not_modify_strategy_action") is True,
            "GET storage overview must remain cache-only and must not refresh providers, write data, or mutate actions.",
        ),
        _row(
            "canonical_dataset_contracts_declared",
            overview.get("dataset_count") == len(canonical_datasets)
            and catalog.get("dataset_count") == len(canonical_datasets)
            and overview_datasets == canonical_datasets
            and catalog_datasets == canonical_datasets
            and catalog.get("cache_only") is True
            and _flag_false(catalog, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and catalog.get("does_not_execute_trades") is True
            and catalog.get("does_not_modify_strategy_action") is True,
            "Storage catalog must expose all canonical datasets locally without provider refresh or trading side effects.",
        ),
        _row(
            "production_blocker_audit_keeps_storage_blocked",
            blocker_audit.get("schema_version") == "command_center_3_storage_production_blocker_audit.v1"
            and blocker_audit.get("status") == "storage_production_blocked"
            and blocker_audit.get("production_storage_complete") is False
            and blocker_audit.get("dry_runs_are_not_production_completion") is True
            and blocker_audit.get("preflight_is_not_physical_migration") is True
            and blocker_audit.get("dataset_version_policy_is_not_manifest_validation") is True
            and REQUIRED_BLOCKER_CRITERIA.issubset(blocker_criteria)
            and int(blocker_audit.get("blocking_criterion_count") or 0) > 0
            and _flag_false(blocker_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Storage production blocker audit must keep physical migration, manifest validation, partitioning, compaction, TTL refresh, and cleanup pending.",
        ),
        _row(
            "schema_migration_preflight_is_not_physical_migration",
            schema_preflight.get("schema_version") == "command_center_3_storage_schema_migration_preflight.v1"
            and schema_preflight.get("status") == "preflight_ready"
            and schema_preflight.get("physical_validation_done_count") == 0
            and schema_preflight.get("migration_executed_count") == 0
            and schema_preflight.get("schema_migration_ready_count") == 0
            and schema_preflight.get("manual_migration_task_required") is True
            and schema_preflight.get("schema_migration_task_executed") is False
            and schema_preflight.get("cache_get_writes_files") is False
            and schema_preflight.get("payload_reads_on_get") is False
            and _flag_false(schema_preflight, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Schema migration preflight may be ready, but physical validation and migration execution must remain pending.",
        ),
        _row(
            "dataset_version_policy_is_not_manifest_validation",
            dataset_version_policy.get("schema_version") == "command_center_3_storage_dataset_version_policy.v1"
            and dataset_version_policy.get("status") == "policy_ready"
            and dataset_version_policy.get("target_version_declared_count") == len(canonical_datasets)
            and dataset_version_policy.get("physical_dataset_version_validated_count") == 0
            and dataset_version_policy.get("dataset_version_migration_executed_count") == 0
            and dataset_version_policy.get("manifest_written_on_get") is False
            and dataset_version_policy.get("cache_get_writes_files") is False
            and dataset_version_policy.get("cache_get_reads_payloads") is False
            and _flag_false(dataset_version_policy, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Dataset version policy is a contract only; it must not imply manifest write or physical version validation.",
        ),
        _row(
            "dataset_version_manifest_evidence_is_read_only",
            dataset_version_manifest_evidence.get("schema_version")
            == "command_center_3_storage_dataset_version_manifest_evidence.v1"
            and dataset_version_manifest_evidence.get("scope") == "read_only_local_manifest_evidence_not_manifest_writer"
            and dataset_version_manifest_evidence.get("mode") == "cache_only_read_only_manifest_evidence"
            and dataset_version_manifest_evidence.get("dataset_count") == len(canonical_datasets)
            and len(_list(dataset_version_manifest_evidence.get("rows"))) == len(canonical_datasets)
            and dataset_version_manifest_evidence.get("dataset_version_manifest_written") is False
            and dataset_version_manifest_evidence.get("manifest_writer_task_executed") is False
            and dataset_version_manifest_evidence.get("dataset_version_migration_executed_count") == 0
            and dataset_version_manifest_evidence.get("manifest_written_on_get") is False
            and dataset_version_manifest_evidence.get("cache_get_writes_files") is False
            and dataset_version_manifest_evidence.get("cache_get_reads_parquet_payloads") is False
            and _flag_false(dataset_version_manifest_evidence, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and dataset_version_manifest_evidence.get("does_not_execute_trades") is True
            and dataset_version_manifest_evidence.get("does_not_modify_strategy_action") is True,
            "Dataset version manifest evidence may read local _dataset_versions.json metadata only; it must not write a manifest, read Parquet payloads, call providers, or mark production storage complete.",
        ),
        _row(
            "dataset_version_manifest_dry_run_writes_no_manifest",
            manifest_packet.get("schema_version") == "command_center_3_storage_dataset_version_manifest_dry_run.v1"
            and manifest_packet.get("status")
            in {"dry_run_completed", "dry_run_blocked_existing_manifest_unreadable"}
            and manifest_packet.get("dataset_count") == len(canonical_datasets)
            and len(_list(manifest_packet.get("rows"))) == len(canonical_datasets)
            and manifest_packet.get("manifest_write_executed") is False
            and manifest_packet.get("manifest_written_on_post") is False
            and manifest_packet.get("post_dry_run_writes_manifest") is False
            and manifest_packet.get("post_dry_run_writes_parquet") is False
            and manifest_packet.get("post_dry_run_reads_parquet_payloads") is False
            and manifest_packet.get("manual_approval_required_before_write") is True
            and manifest_packet.get("separate_write_task_required") is True
            and manifest_packet.get("production_storage_complete") is False
            and _flag_false(manifest_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and manifest_packet.get("does_not_execute_trades") is True
            and manifest_packet.get("does_not_modify_strategy_action") is True,
            "Dataset version manifest dry-run may propose _dataset_versions.json content, but it must not write the manifest, write Parquet, read payloads, call providers, or complete production storage.",
        ),
        _row(
            "schema_validation_dry_run_writes_no_parquet",
            schema_packet.get("schema_version") == "command_center_3_storage_schema_validation_dry_run.v1"
            and schema_packet.get("status") == "dry_run_completed"
            and schema_packet.get("dataset_count") == len(canonical_datasets)
            and schema_packet.get("post_dry_run_writes_parquet") is False
            and schema_packet.get("post_dry_run_reads_row_payloads") is False
            and schema_packet.get("schema_migration_executed") is False
            and schema_packet.get("schema_migration_executed_count") == 0
            and _flag_false(schema_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and schema_packet.get("does_not_execute_trades") is True
            and schema_packet.get("does_not_modify_strategy_action") is True,
            "Schema validation dry-run must read schema metadata only and must not write Parquet or execute migration.",
        ),
        _row(
            "partition_migration_dry_run_writes_no_parquet",
            partition_packet.get("schema_version") == "command_center_3_storage_partition_migration_dry_run.v1"
            and partition_packet.get("status") == "dry_run_completed"
            and partition_packet.get("dataset_count") == len(canonical_datasets)
            and partition_packet.get("post_dry_run_writes_parquet") is False
            and partition_packet.get("post_dry_run_reads_row_payloads") is False
            and partition_packet.get("partition_migration_executed") is False
            and partition_packet.get("partition_migration_executed_count") == 0
            and _flag_false(partition_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and partition_packet.get("does_not_execute_trades") is True
            and partition_packet.get("does_not_modify_strategy_action") is True,
            "Partition migration dry-run must remain plan-only and must not write partitioned Parquet.",
        ),
        _row(
            "compaction_dry_run_rewrites_no_parquet",
            compaction_packet.get("schema_version") == "command_center_3_storage_compaction_dry_run.v1"
            and compaction_packet.get("status") == "dry_run_completed"
            and compaction_packet.get("dataset_count") == len(canonical_datasets)
            and compaction_packet.get("post_dry_run_writes_parquet") is False
            and compaction_packet.get("post_dry_run_reads_row_payloads") is False
            and compaction_packet.get("compaction_executed") is False
            and compaction_packet.get("physical_compaction_executed") is False
            and compaction_packet.get("compaction_executed_count") == 0
            and _flag_false(compaction_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and compaction_packet.get("does_not_execute_trades") is True
            and compaction_packet.get("does_not_modify_strategy_action") is True,
            "Compaction dry-run must not rewrite Parquet or read row payloads.",
        ),
        _row(
            "cache_ttl_dry_run_refreshes_no_provider",
            ttl_packet.get("schema_version") == "command_center_3_storage_cache_ttl_dry_run.v1"
            and ttl_packet.get("status") == "dry_run_completed"
            and ttl_packet.get("dataset_count") == len(canonical_datasets)
            and ttl_packet.get("auto_refresh_on_get") is False
            and ttl_packet.get("post_dry_run_writes_parquet") is False
            and ttl_packet.get("post_dry_run_reads_row_payloads") is False
            and ttl_packet.get("refresh_executed") is False
            and ttl_packet.get("refresh_executed_count") == 0
            and _flag_false(ttl_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and ttl_packet.get("does_not_execute_trades") is True
            and ttl_packet.get("does_not_modify_strategy_action") is True,
            "Cache TTL dry-run may recommend refreshes, but it must not call providers or write Parquet.",
        ),
        _row(
            "artifact_cleanup_review_deletes_nothing",
            cleanup_packet.get("schema_version") == "command_center_3_storage_artifact_cleanup_dry_run.v1"
            and cleanup_packet.get("status") == "ready"
            and cleanup_packet.get("delete_executed_count") == 0
            and cleanup_packet.get("safe_delete_command_generated") is False
            and cleanup_packet.get("cleanup_review_is_not_delete_execution") is True
            and cleanup_packet.get("production_cleanup_complete") is False
            and cleanup_packet.get("does_not_read_file_payloads") is True
            and cleanup_packet.get("does_not_scan_secret_values") is True
            and cleanup_review.get("schema_version") == "command_center_3_storage_artifact_cleanup_review_contract.v1"
            and cleanup_review.get("delete_executed") is False
            and cleanup_review.get("safe_delete_command_generated") is False
            and cleanup_review.get("production_cleanup_complete") is False
            and _flag_false(cleanup_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Artifact cleanup dry-run and manual review must not delete files, generate delete commands, or read payloads.",
        ),
        _row(
            "duckdb_query_service_is_read_only",
            duckdb_policy.get("schema_version") == "command_center_3_storage_duckdb_query_service.v1"
            and duckdb_policy.get("dataset_count") == len(canonical_datasets)
            and duckdb_policy.get("safe_limit_enforced") is True
            and duckdb_policy.get("safe_parameter_binding") is True
            and duckdb_policy.get("typed_projection_enabled") is True
            and duckdb_policy.get("query_result_contract_enabled") is True
            and duckdb_policy.get("query_result_contract_schema_version") == "duckdb_query_result_contract.v1"
            and duckdb_policy.get("cursor_pagination_enabled") is True
            and duckdb_policy.get("frontend_executes_query") is False
            and duckdb_policy.get("ui_direct_dataframe_read") is False
            and duckdb_policy.get("cache_get_external_calls") is False
            and duckdb_policy.get("cache_get_writes_files") is False
            and duckdb_policy.get("writes_parquet_on_get") is False
            and all(row.get("query_result_contract_schema_version") == "duckdb_query_result_contract.v1" for row in duckdb_rows)
            and all(row.get("frontend_executes_query") is False for row in duckdb_rows)
            and _flag_false(duckdb_policy, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "DuckDB query service must remain local, parameter-bound, cursor-paginated, and hidden behind FastAPI.",
        ),
        _row(
            "storage_dry_run_tasks_are_button_gated",
            set(task_rows) == REQUIRED_STORAGE_TASK_TYPES
            and all(row.get("button_gated") is True for row in task_rows.values())
            and all(row.get("possible_external_sources") == [] for row in task_rows.values())
            and all(row.get("call_ledger_required") is True for row in task_rows.values())
            and all(row.get("cache_get_external_calls") is False for row in task_rows.values())
            and all(row.get("does_not_execute_trades") is True for row in task_rows.values())
            and all(row.get("does_not_modify_strategy_action") is True for row in task_rows.values())
            and task_rows["run_storage_schema_validation_dry_run"].get("writes_parquet_on_post") is False
            and task_rows["run_storage_dataset_version_manifest_dry_run"].get("writes_manifest_on_post") is False
            and task_rows["run_storage_dataset_version_manifest_dry_run"].get("manifest_write_executed") is False
            and task_rows["run_storage_dataset_version_manifest_write"].get("writes_manifest_on_post") is True
            and task_rows["run_storage_dataset_version_manifest_write"].get("requires_confirm_manifest_write") is True
            and task_rows["run_storage_dataset_version_manifest_write"].get("writes_parquet_on_post") is False
            and task_rows["run_storage_dataset_version_manifest_write"].get("reads_row_payloads") is False
            and task_rows["run_storage_dataset_version_manifest_write"].get("cache_get_external_calls") is False
            and task_rows["run_storage_partition_migration_dry_run"].get("partition_migration_executed") is False
            and task_rows["run_storage_compaction_dry_run"].get("physical_compaction_executed") is False
            and task_rows["run_storage_cache_ttl_dry_run"].get("refresh_executed") is False
            and task_rows["run_storage_artifact_cleanup_dry_run"].get("delete_files_on_post") is False,
            "Storage tasks must be button-gated local pipelines; dry-runs stay no-write while the manifest writer is explicit, confirm-gated, manifest-only, no-provider, no-Parquet, and no-trade.",
        ),
        _row(
            "push_gate_runs_storage_contract_after_candidate",
            "scripts/storage_contract.py" in push_gate_script
            and "Storage contract" in push_gate_script
            and "storage_contract: passed_local_contract_physical_migration_pending" in push_gate_script
            and push_gate_script.find('run_step "Candidate Radar contract"') < push_gate_script.find('run_step "Storage contract"')
            and push_gate_script.find('run_step "Storage contract"') < push_gate_script.find('run_step "Motion viewport QA contract"'),
            "Push gate must run LTG-05 storage contract after Candidate Radar and before motion/static QA.",
        ),
        _row(
            "script_is_local_no_provider_execution",
            "command_center_3_storage_contract.v1" in this_script
            and "local_storage_contract_no_physical_migration" in this_script
            and "production_storage_complete" in this_script
            and "dry_runs_are_not_production_completion" in this_script
            and "does_not_execute_trades" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script,
            "The push-gate contract script must stay local and must not import provider clients.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_storage_contract.v1",
        "status": "storage_contract_passed" if not blockers else "storage_contract_blocked",
        "scope": "local_storage_contract_no_physical_migration",
        "ltg": "LTG-05/LTG-11",
        "contract_ready": not blockers,
        "production_storage_complete": False,
        "physical_schema_validation_done": False,
        "schema_migration_executed": False,
        "dataset_version_manifest_validated": False,
        "dataset_version_manifest_evidence_validated": bool(
            dataset_version_manifest_evidence.get("dataset_version_manifest_validated")
        ),
        "dataset_version_manifest_dry_run_writes_manifest": False,
        "dataset_version_manifest_write_task_available": True,
        "partition_migration_executed": False,
        "physical_compaction_executed": False,
        "cache_ttl_refresh_executed": False,
        "artifact_cleanup_delete_executed": False,
        "dry_runs_are_not_production_completion": True,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "writes_parquet_on_get": False,
        "does_not_read_row_payloads": True,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "dataset_count": overview.get("dataset_count"),
            "production_readiness_status": production_readiness.get("status"),
            "storage_production_blocker_status": blocker_audit.get("status"),
            "storage_production_blocker_count": blocker_audit.get("blocking_criterion_count"),
            "schema_migration_preflight_status": schema_preflight.get("status"),
            "dataset_version_policy_status": dataset_version_policy.get("status"),
            "dataset_version_manifest_evidence_status": dataset_version_manifest_evidence.get("status"),
            "dataset_version_manifest_evidence_validated_count": dataset_version_manifest_evidence.get("validated_dataset_count"),
            "dataset_version_manifest_dry_run_status": manifest_packet.get("status"),
            "dataset_version_manifest_dry_run_would_change_count": manifest_packet.get("would_change_count"),
            "duckdb_query_service_status": duckdb_policy.get("status"),
            "schema_validation_status": schema_packet.get("status"),
            "partition_migration_status": partition_packet.get("status"),
            "compaction_status": compaction_packet.get("status"),
            "cache_ttl_status": ttl_packet.get("status"),
            "artifact_cleanup_status": cleanup_packet.get("status"),
        },
        "rows": rows,
        "note": "This is a local push-gate contract. Physical schema validation, schema migration, dataset version manifest validation, partition migration, physical compaction, TTL refresh execution, and delete cleanup remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-05 Storage contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"storage_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "production_storage_complete: false; schema_migration_executed: false".format(**contract)
        )
        print(
            "external_calls_triggered: false; tushare_called: false; "
            "deepseek_called: false; github_called: false; does_not_execute_trades: true"
        )
        if contract["blockers"]:
            print("blockers: " + ", ".join(contract["blockers"]))
    return 0 if contract["contract_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
