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
    "run_storage_backtest_results_schema_seed",
    "run_storage_schema_validation_acceptance",
    "run_storage_schema_migration_execution",
    "run_storage_dataset_version_manifest_dry_run",
    "run_storage_dataset_version_manifest_review",
    "run_storage_dataset_version_manifest_write",
    "run_storage_dataset_version_manifest_validate",
    "run_storage_partition_migration_dry_run",
    "run_storage_compaction_dry_run",
    "run_storage_cache_ttl_dry_run",
    "run_storage_physical_execution_request",
}
REQUIRED_PHYSICAL_MIGRATION_STAGES = (
    "physical_schema_validation",
    "schema_migration",
    "dataset_version_manifest_validation",
    "partition_migration",
    "physical_compaction",
    "cache_ttl_refresh",
    "artifact_cleanup_review",
    "production_promotion",
)
REQUIRED_STORAGE_PHYSICAL_EXECUTION_PHASES = (
    "physical_schema_validation_acceptance",
    "dataset_version_manifest_write_validate",
    "schema_migration_execution_plan",
    "partition_migration_execution_plan",
    "physical_compaction_execution_plan",
    "cache_ttl_refresh_execution_plan",
    "artifact_cleanup_delete_review",
    "duckdb_post_migration_validation",
    "production_promotion_review",
)
REQUIRED_STORAGE_PHYSICAL_DURABLE_EVIDENCE_KEYS = (
    "production_blocker_audit_visible",
    "readiness_receipt_visible",
    "activation_receipt_visible",
    "physical_execution_recipe_ready",
    "physical_execution_request_visible",
    "physical_schema_validation_evidence_required",
    "dataset_version_manifest_validation_required",
    "partition_migration_evidence_required",
    "physical_compaction_evidence_required",
    "cache_ttl_refresh_evidence_required",
    "artifact_cleanup_delete_review_required",
    "duckdb_post_migration_validation_required",
    "production_promotion_review_required",
    "no_provider_trade_action_secret_boundary",
)
PHYSICAL_MIGRATION_STAGE_LABELS = {
    "physical_schema_validation": "Physical schema validation",
    "schema_migration": "Schema migration",
    "dataset_version_manifest_validation": "Dataset version manifest validation",
    "partition_migration": "Partition migration",
    "physical_compaction": "Physical compaction",
    "cache_ttl_refresh": "Cache TTL refresh",
    "artifact_cleanup_review": "Artifact cleanup review",
    "production_promotion": "Production promotion",
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


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text.lower())


def _manifest_hash_evidence_is_consistent(evidence: dict[str, Any]) -> bool:
    if evidence.get("manifest_exists") is True:
        return evidence.get("manifest_hash_algorithm") == "sha256" and _is_sha256(
            evidence.get("manifest_content_sha256")
        )
    return evidence.get("manifest_hash_algorithm") == "" and evidence.get("manifest_content_sha256") == ""


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


def _physical_migration_stage_scope_rows() -> list[dict[str, Any]]:
    return [
        {
            "stage_key": stage_key,
            "stage_label": PHYSICAL_MIGRATION_STAGE_LABELS.get(stage_key, stage_key),
            "scope": "storage_physical_migration_stage_scope_manifest",
            "current_status": "local_preflight_or_dry_run_only",
            "target_status": "physical_execution_or_promotion_evidence_required",
            "required_before_production": True,
            "physical_schema_validation_done": False,
            "schema_migration_executed": False,
            "dataset_version_manifest_validated": False,
            "partition_migration_executed": False,
            "physical_compaction_executed": False,
            "cache_ttl_refresh_executed": False,
            "artifact_cleanup_delete_executed": False,
            "production_storage_complete": False,
            "writes_parquet_on_get": False,
            "writes_parquet_by_contract": False,
            "reads_row_payloads": False,
            "external_calls_triggered": False,
            "tushare_called_by_contract": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "required_real_evidence": [
                "explicit POST task evidence",
                "physical artifact or manifest validation evidence",
                "safe local task call ledger",
                "production promotion review",
            ],
        }
        for stage_key in REQUIRED_PHYSICAL_MIGRATION_STAGES
    ]


def build_contract() -> dict[str, Any]:
    overview = storage_service.storage_overview()
    catalog = storage_service.storage_dataset_catalog()
    schema_packet = storage_service.storage_schema_validation_dry_run_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    schema_seed_packet = storage_service.storage_backtest_results_schema_seed_packet(
        payload_safe={
            "source": "storage_contract",
            "confirm_schema_seed": False,
            "external_sources_allowed": False,
        }
    )
    schema_acceptance_packet = storage_service.storage_schema_validation_acceptance_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    manifest_packet = storage_service.storage_dataset_version_manifest_dry_run_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    manifest_review_packet = storage_service.storage_dataset_version_manifest_review_packet(
        payload_safe={"source": "storage_contract", "external_sources_allowed": False}
    )
    manifest_validate_packet = storage_service.storage_dataset_version_manifest_validate_packet(
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
    readiness_receipt = _dict(overview.get("storage_production_readiness_receipt"))
    receipt_criteria = {
        str(row.get("criterion") or "")
        for row in _list(overview.get("storage_production_readiness_receipt_rows"))
        if isinstance(row, dict)
    }
    activation_receipt = _dict(overview.get("storage_physical_migration_activation_receipt"))
    activation_criteria = {
        str(row.get("criterion") or "")
        for row in _list(overview.get("storage_physical_migration_activation_rows"))
        if isinstance(row, dict)
    }
    physical_execution_recipe = _dict(overview.get("storage_physical_execution_recipe"))
    physical_execution_rows = {
        str(row.get("phase") or ""): row
        for row in _list(overview.get("storage_physical_execution_recipe_rows"))
        if isinstance(row, dict)
    }
    physical_execution_request_packet = storage_service.storage_physical_execution_request_packet(
        payload_safe={
            "source": "storage_contract",
            "approved_by_user": True,
            "physical_execution_scope_hash": physical_execution_recipe.get("physical_execution_scope_hash"),
        }
    )
    durable_evidence_recipe = _dict(overview.get("storage_physical_durable_evidence_recipe"))
    durable_evidence_rows = {
        str(row.get("evidence_key") or ""): row
        for row in _list(overview.get("storage_physical_durable_evidence_rows"))
        if isinstance(row, dict)
    }
    manifest_validate_evidence = storage_service.storage_dataset_version_manifest_validate_evidence()
    duckdb_read_validation_evidence = storage_service.storage_duckdb_read_validation_evidence()
    blocker_criteria = {
        str(row.get("criterion") or "")
        for row in _list(overview.get("storage_production_blocker_rows"))
        if isinstance(row, dict)
    }
    schema_preflight = _dict(overview.get("schema_migration_preflight"))
    schema_migration_execution_evidence = _dict(overview.get("schema_migration_execution_evidence"))
    backtest_schema_seed_evidence = _dict(overview.get("backtest_results_schema_seed_evidence"))
    schema_acceptance_evidence = _dict(overview.get("schema_validation_acceptance_evidence"))
    dataset_version_policy = _dict(overview.get("dataset_version_policy"))
    dataset_version_manifest_evidence = _dict(overview.get("dataset_version_manifest_evidence_audit"))
    duckdb_policy = _dict(overview.get("duckdb_query_service"))
    duckdb_rows = [row for row in _list(overview.get("duckdb_query_service_rows")) if isinstance(row, dict)]
    cleanup_review = _dict(overview.get("artifact_cleanup_review_contract"))
    task_rows = _storage_task_rows()
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/storage_contract.py")
    physical_migration_stage_scope_rows = _physical_migration_stage_scope_rows()

    canonical_datasets = set(storage_service.CANONICAL_PARQUET_DATASETS)
    catalog_datasets = {
        str(row.get("dataset") or "")
        for row in _list(catalog.get("dataset_catalog"))
        if isinstance(row, dict)
    }
    overview_datasets = set(_dict(overview.get("dataset_status")).keys())
    schema_evidence_done = schema_acceptance_evidence.get("physical_schema_validation_done") is True
    schema_migration_executed = schema_migration_execution_evidence.get("schema_migration_executed") is True
    schema_migration_noop_verified = bool(
        schema_migration_execution_evidence.get("status") == "schema_migration_execution_completed_noop_verified"
        and schema_migration_execution_evidence.get("schema_migration_noop_verified") is True
        and schema_migration_execution_evidence.get("schema_migration_rewrite_executed") is False
        and schema_migration_execution_evidence.get("post_task_writes_parquet") is False
        and schema_migration_execution_evidence.get("post_task_reads_row_payloads") is False
        and schema_migration_execution_evidence.get("production_storage_complete") is False
        and _flag_false(
            schema_migration_execution_evidence,
            "external_calls_triggered",
            "tushare_called",
            "deepseek_called",
            "github_called",
            "contains_secret",
        )
        and schema_migration_execution_evidence.get("does_not_execute_trades") is True
    )
    manifest_validation_done = bool(
        manifest_validate_evidence.get("schema_version")
        == "command_center_3_storage_dataset_version_manifest_validate.v1"
        and manifest_validate_evidence.get("status") == "manifest_validate_passed_local_only"
        and manifest_validate_evidence.get("dataset_version_manifest_validated") is True
        and int(manifest_validate_evidence.get("validated_dataset_count") or 0) > 0
        and int(manifest_validate_evidence.get("validated_dataset_count") or 0)
        == int(manifest_validate_evidence.get("dataset_count") or 0)
        and manifest_validate_evidence.get("manifest_write_executed") is False
        and manifest_validate_evidence.get("manifest_written_on_post") is False
        and manifest_validate_evidence.get("post_validate_writes_manifest") is False
        and manifest_validate_evidence.get("post_validate_writes_parquet") is False
        and manifest_validate_evidence.get("post_validate_reads_parquet_payloads") is False
        and manifest_validate_evidence.get("post_validate_reads_env_files") is False
        and manifest_validate_evidence.get("production_storage_complete") is False
        and _flag_false(
            manifest_validate_evidence,
            "external_calls_triggered",
            "tushare_called",
            "deepseek_called",
            "github_called",
            "contains_secret",
        )
        and manifest_validate_evidence.get("does_not_execute_trades") is True
        and manifest_validate_evidence.get("does_not_modify_strategy_action") is True
    )
    duckdb_read_validation_done = bool(
        duckdb_read_validation_evidence.get("schema_version")
        == "command_center_3_storage_duckdb_read_validation.v1"
        and duckdb_read_validation_evidence.get("status")
        == "storage_duckdb_read_validation_ready_local_query_contract"
        and duckdb_read_validation_evidence.get("local_duckdb_read_validation_ready") is True
        and duckdb_read_validation_evidence.get("duckdb_dependency_available") is True
        and int(duckdb_read_validation_evidence.get("dataset_count") or 0) > 0
        and int(duckdb_read_validation_evidence.get("contract_ready_count") or 0)
        == int(duckdb_read_validation_evidence.get("dataset_count") or 0)
        and duckdb_read_validation_evidence.get("query_result_contract_schema_version")
        == "duckdb_query_result_contract.v1"
        and duckdb_read_validation_evidence.get("query_wrapper") == "duckdb_filtered_parquet.v1"
        and duckdb_read_validation_evidence.get("safe_parameter_binding") is True
        and duckdb_read_validation_evidence.get("typed_projection_enabled") is True
        and duckdb_read_validation_evidence.get("cursor_pagination_enabled") is True
        and duckdb_read_validation_evidence.get("frontend_executes_query") is False
        and duckdb_read_validation_evidence.get("cache_get_writes_files") is False
        and duckdb_read_validation_evidence.get("writes_parquet_on_get") is False
        and duckdb_read_validation_evidence.get("writes_parquet") is False
        and duckdb_read_validation_evidence.get("writes_manifest") is False
        and duckdb_read_validation_evidence.get("deletes_artifacts") is False
        and duckdb_read_validation_evidence.get("refreshes_providers") is False
        and duckdb_read_validation_evidence.get("production_storage_complete") is False
        and _flag_false(
            duckdb_read_validation_evidence,
            "external_calls_triggered",
            "tushare_called",
            "deepseek_called",
            "github_called",
            "contains_secret",
        )
        and duckdb_read_validation_evidence.get("does_not_execute_trades") is True
        and duckdb_read_validation_evidence.get("does_not_modify_strategy_action") is True
    )
    artifact_cleanup_review_done = bool(
        cleanup_review.get("schema_version")
        == "command_center_3_storage_artifact_cleanup_review_contract.v1"
        and cleanup_review.get("status")
        in {"manual_review_ready_delete_pending", "manual_review_ready_no_candidates"}
        and cleanup_review.get("artifact_cleanup_review_done") is True
        and int(cleanup_review.get("required_review_step_count") or 0) > 0
        and cleanup_review.get("manual_approval_required") is True
        and cleanup_review.get("dry_run_required_before_delete") is True
        and cleanup_review.get("delete_execution_task_available") is False
        and cleanup_review.get("delete_executed") is False
        and int(cleanup_review.get("delete_executed_count") or 0) == 0
        and cleanup_review.get("safe_delete_command_generated") is False
        and cleanup_review.get("delete_command_not_generated") is True
        and cleanup_review.get("cleanup_review_is_not_delete_execution") is True
        and cleanup_review.get("production_cleanup_complete") is False
        and cleanup_review.get("reads_payloads") is False
        and cleanup_review.get("reads_file_payloads") is False
        and cleanup_review.get("reads_env_files") is False
        and cleanup_review.get("scans_secret_values") is False
        and cleanup_review.get("does_not_scan_secret_values") is True
        and _flag_false(
            cleanup_review,
            "external_calls_triggered",
            "tushare_called",
            "deepseek_called",
            "github_called",
            "contains_secret",
        )
        and cleanup_review.get("does_not_execute_trades") is True
        and cleanup_review.get("does_not_modify_strategy_action") is True
    )
    expected_durable_missing = {
        "dataset_version_manifest_validation_required",
        "partition_migration_evidence_required",
        "physical_compaction_evidence_required",
        "cache_ttl_refresh_evidence_required",
        "artifact_cleanup_delete_review_required",
        "duckdb_post_migration_validation_required",
        "production_promotion_review_required",
    }
    if physical_execution_request_packet.get("local_execution_request_ready") is not True:
        expected_durable_missing.add("physical_execution_request_visible")
    if not schema_evidence_done:
        expected_durable_missing.add("physical_schema_validation_evidence_required")
    if manifest_validation_done:
        expected_durable_missing.discard("dataset_version_manifest_validation_required")
    if duckdb_read_validation_done:
        expected_durable_missing.discard("duckdb_post_migration_validation_required")
    if artifact_cleanup_review_done:
        expected_durable_missing.discard("artifact_cleanup_delete_review_required")

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
            "production_readiness_receipt_allows_only_explicit_next_step",
            readiness_receipt.get("schema_version") == "command_center_3_storage_production_readiness_receipt.v1"
            and readiness_receipt.get("scope") == "local_storage_production_readiness_receipt_no_physical_migration"
            and readiness_receipt.get("status") == "storage_readiness_receipt_ready_physical_migration_pending"
            and readiness_receipt.get("local_receipt_ready") is True
            and readiness_receipt.get("ready_for_explicit_storage_review_tasks") is True
            and readiness_receipt.get("allowed_next_step") == "explicit_post_task_storage_schema_acceptance_manifest_review"
            and "GET /api/storage physical migration" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "GET /api/storage provider refresh" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "dry-run/preflight/receipt as production storage completion"
            in _list(readiness_receipt.get("not_allowed_next_steps"))
            and readiness_receipt.get("production_storage_complete") is False
            and readiness_receipt.get("physical_schema_validation_done") is schema_evidence_done
            and readiness_receipt.get("schema_migration_executed") is False
            and readiness_receipt.get("partition_migration_executed") is False
            and readiness_receipt.get("physical_compaction_executed") is False
            and readiness_receipt.get("cache_ttl_refresh_executed") is False
            and readiness_receipt.get("artifact_cleanup_delete_executed") is False
            and readiness_receipt.get("provider_refresh_called_by_receipt") is False
            and readiness_receipt.get("cache_get_external_calls") is False
            and readiness_receipt.get("receipt_external_calls_triggered") is False
            and readiness_receipt.get("tushare_called_by_receipt") is False
            and _flag_false(readiness_receipt, "deepseek_called", "github_called")
            and readiness_receipt.get("does_not_execute_trades") is True
            and readiness_receipt.get("does_not_modify_strategy_action") is True
            and readiness_receipt.get("production_blocker_count") == blocker_audit.get("blocking_criterion_count")
            and {
                "local_contracts_visible",
                "explicit_post_task_boundaries",
                "cache_get_read_only_boundary",
                "manifest_write_is_guarded",
                "physical_schema_validation_pending",
                "physical_migration_and_versioning_pending",
                "maintenance_execution_pending",
                "production_completion_evidence_ticket",
            }.issubset(receipt_criteria),
            "Storage readiness receipt must permit only explicit POST review tasks and must keep GET migration, provider refresh, cleanup deletion, and production completion blocked.",
        ),
        _row(
            "physical_migration_activation_receipt_keeps_execution_pending",
            activation_receipt.get("schema_version")
            == "command_center_3_storage_physical_migration_activation_receipt.v1"
            and activation_receipt.get("scope")
            == "local_storage_physical_migration_activation_receipt_no_physical_execution"
            and activation_receipt.get("status")
            == "storage_physical_migration_activation_receipt_ready_execution_pending"
            and activation_receipt.get("local_activation_receipt_ready") is True
            and activation_receipt.get("ready_for_explicit_physical_migration_review") is True
            and activation_receipt.get("allowed_next_step")
            == "explicit_schema_acceptance_manifest_validate_then_partition_compaction_ttl_cleanup_reviews"
            and "GET /api/storage physical migration" in _list(activation_receipt.get("not_allowed_next_steps"))
            and "GET /api/storage Parquet write" in _list(activation_receipt.get("not_allowed_next_steps"))
            and "GET /api/storage provider refresh" in _list(activation_receipt.get("not_allowed_next_steps"))
            and "activation receipt as production storage completion"
            in _list(activation_receipt.get("not_allowed_next_steps"))
            and (
                schema_evidence_done
                or "physical schema validation acceptance for all canonical datasets"
                in _list(activation_receipt.get("missing_evidence"))
            )
            and (
                not schema_evidence_done
                or "physical schema validation acceptance for all canonical datasets"
                not in _list(activation_receipt.get("missing_evidence"))
            )
            and "manifest validation backed by schema acceptance" in _list(activation_receipt.get("missing_evidence"))
            and "production promotion review" in _list(activation_receipt.get("missing_evidence"))
            and activation_receipt.get("production_storage_complete") is False
            and activation_receipt.get("physical_schema_validation_done") is schema_evidence_done
            and activation_receipt.get("schema_migration_executed") is False
            and activation_receipt.get("dataset_version_manifest_validated") is False
            and activation_receipt.get("partition_migration_executed") is False
            and activation_receipt.get("physical_compaction_executed") is False
            and activation_receipt.get("cache_ttl_refresh_executed") is False
            and activation_receipt.get("artifact_cleanup_delete_executed") is False
            and activation_receipt.get("provider_refresh_called_by_receipt") is False
            and activation_receipt.get("parquet_written_by_receipt") is False
            and activation_receipt.get("manifest_written_by_receipt") is False
            and activation_receipt.get("cleanup_delete_generated_by_receipt") is False
            and activation_receipt.get("cache_get_external_calls") is False
            and activation_receipt.get("receipt_external_calls_triggered") is False
            and _flag_false(activation_receipt, "tushare_called", "deepseek_called", "github_called")
            and activation_receipt.get("does_not_execute_trades") is True
            and activation_receipt.get("does_not_modify_strategy_action") is True
            and activation_receipt.get("production_blocker_count") == blocker_audit.get("blocking_criterion_count")
            and {
                "readiness_receipt_ready",
                "schema_acceptance_required",
                "manifest_validation_required",
                "partition_migration_required",
                "compaction_execution_required",
                "cache_ttl_refresh_required",
                "cleanup_manual_approval_required",
                "duckdb_query_boundary_ready",
                "no_get_migration_or_provider_refresh",
                "no_trade_or_action_boundary",
            }.issubset(activation_criteria),
            "Storage physical migration activation receipt must expose the next explicit execution prerequisites while keeping all physical writes, provider refreshes, deletes, trades, and production completion pending.",
        ),
        _row(
            "physical_execution_recipe_is_local_pending",
            physical_execution_recipe.get("schema_version") == "command_center_3_storage_physical_execution_recipe.v1"
            and physical_execution_recipe.get("scope") == "local_storage_physical_execution_recipe_no_write_no_provider"
            and physical_execution_recipe.get("status") == "storage_physical_execution_recipe_ready_execution_pending"
            and physical_execution_recipe.get("local_recipe_ready") is True
            and physical_execution_recipe.get("execution_done") is False
            and physical_execution_recipe.get("physical_execution_done") is False
            and physical_execution_recipe.get("production_storage_complete") is False
            and physical_execution_recipe.get("requires_explicit_post_sequence") is True
            and physical_execution_recipe.get("requires_manual_review") is True
            and tuple(physical_execution_recipe.get("allowed_execution_sequence") or ())
            == REQUIRED_STORAGE_PHYSICAL_EXECUTION_PHASES
            and tuple(physical_execution_recipe.get("phase_keys") or ()) == REQUIRED_STORAGE_PHYSICAL_EXECUTION_PHASES
            and set(physical_execution_recipe.get("pending_phases") or []) == set(REQUIRED_STORAGE_PHYSICAL_EXECUTION_PHASES)
            and int(physical_execution_recipe.get("pending_phase_count") or 0)
            == len(REQUIRED_STORAGE_PHYSICAL_EXECUTION_PHASES)
            and int(physical_execution_recipe.get("phase_count") or 0) == len(REQUIRED_STORAGE_PHYSICAL_EXECUTION_PHASES)
            and set(physical_execution_rows) == set(REQUIRED_STORAGE_PHYSICAL_EXECUTION_PHASES)
            and {
                "schema validation acceptance packet",
                "confirm-gated dataset version manifest write receipt",
                "manifest validation receipt",
                "DuckDB post-migration query contract",
                "production promotion review",
            }.issubset(set(physical_execution_recipe.get("required_evidence") or []))
            and {
                "treat_recipe_as_physical_execution_evidence",
                "write_parquet_from_get_storage_cache",
                "refresh_providers_from_get_storage_cache",
                "delete_artifacts_from_dry_run",
                "mark_production_storage_complete_from_preflight_or_dry_run",
            }.issubset(set(physical_execution_recipe.get("not_allowed_next_steps") or []))
            and physical_execution_recipe.get("writes_parquet") is False
            and physical_execution_recipe.get("writes_manifest") is False
            and physical_execution_recipe.get("reads_row_payloads") is False
            and physical_execution_recipe.get("refreshes_providers") is False
            and physical_execution_recipe.get("deletes_artifacts") is False
            and _flag_false(physical_execution_recipe, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and physical_execution_recipe.get("does_not_execute_trades") is True
            and physical_execution_recipe.get("does_not_modify_strategy_action") is True
            and physical_execution_recipe.get("contains_secret") is False
            and all(row.get("required_before_production") is True for row in physical_execution_rows.values())
            and all(row.get("execution_done") is False for row in physical_execution_rows.values())
            and all(row.get("production_ready") is False for row in physical_execution_rows.values())
            and all(row.get("production_blocker") is True for row in physical_execution_rows.values())
            and all(row.get("writes_parquet") is False for row in physical_execution_rows.values())
            and all(row.get("writes_manifest") is False for row in physical_execution_rows.values())
            and all(row.get("reads_row_payloads") is False for row in physical_execution_rows.values())
            and all(row.get("refreshes_providers") is False for row in physical_execution_rows.values())
            and all(row.get("deletes_artifacts") is False for row in physical_execution_rows.values())
            and all(row.get("external_calls_triggered") is False for row in physical_execution_rows.values())
            and all(row.get("tushare_called") is False for row in physical_execution_rows.values())
            and all(row.get("deepseek_called") is False for row in physical_execution_rows.values())
            and all(row.get("github_called") is False for row in physical_execution_rows.values())
            and all(row.get("does_not_execute_trades") is True for row in physical_execution_rows.values())
            and all(row.get("does_not_modify_strategy_action") is True for row in physical_execution_rows.values())
            and all(row.get("contains_secret") is False for row in physical_execution_rows.values()),
            "Physical execution recipe must sequence LTG-05 production work while staying local-only, no-write, no-provider, no-delete, no-trade, and pending.",
        ),
        _row(
            "physical_execution_request_is_scope_bound_local",
            physical_execution_request_packet.get("schema_version")
            == "command_center_3_storage_physical_execution_request.v1"
            and physical_execution_request_packet.get("scope")
            == "local_storage_physical_execution_request_no_write_no_delete_no_provider"
            and physical_execution_request_packet.get("status")
            == "storage_physical_execution_request_ready_manual_physical_tasks_pending"
            and physical_execution_request_packet.get("local_execution_request_ready") is True
            and physical_execution_request_packet.get("ready_for_manual_physical_task_submission") is True
            and physical_execution_request_packet.get("approved_by_user") is True
            and physical_execution_request_packet.get("requested_scope_hash_matches_latest") is True
            and _is_sha256(physical_execution_request_packet.get("physical_execution_scope_hash"))
            and physical_execution_request_packet.get("target_storage_task_route")
            == "future POST /api/storage/physical-execution"
            and physical_execution_request_packet.get("target_storage_task_type") == "run_storage_physical_execution"
            and tuple(physical_execution_request_packet.get("target_phases") or ())
            == REQUIRED_STORAGE_PHYSICAL_EXECUTION_PHASES
            and physical_execution_request_packet.get("physical_task_created") is False
            and physical_execution_request_packet.get("physical_task_executed") is False
            and physical_execution_request_packet.get("physical_execution_implemented") is False
            and physical_execution_request_packet.get("production_storage_complete") is False
            and physical_execution_request_packet.get("writes_parquet") is False
            and physical_execution_request_packet.get("writes_manifest") is False
            and physical_execution_request_packet.get("deletes_artifacts") is False
            and physical_execution_request_packet.get("refreshes_providers") is False
            and physical_execution_request_packet.get("runs_commands") is False
            and physical_execution_request_packet.get("reads_row_payloads") is False
            and physical_execution_request_packet.get("reads_env_files") is False
            and _flag_false(
                physical_execution_request_packet,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and physical_execution_request_packet.get("does_not_execute_trades") is True
            and physical_execution_request_packet.get("does_not_modify_strategy_action") is True
            and physical_execution_request_packet.get("contains_secret") is False
            and {
                "treat_execution_request_as_physical_storage_execution",
                "write_parquet_from_execution_request",
                "write_manifest_from_execution_request",
                "delete_artifacts_from_execution_request",
                "refresh_providers_from_execution_request",
                "mark_production_storage_complete_from_execution_request",
            }.issubset(set(physical_execution_request_packet.get("not_allowed_next_steps") or []))
            and all(
                row.get("request_only") is True
                and row.get("writes_parquet") is False
                and row.get("writes_manifest") is False
                and row.get("deletes_artifacts") is False
                and row.get("external_calls_triggered") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                and row.get("contains_secret") is False
                for row in _list(physical_execution_request_packet.get("rows"))
                if isinstance(row, dict)
            ),
            "Storage physical execution request must bind the current recipe scope hash without writing Parquet, writing manifests, deleting files, calling providers/models/GitHub, trading, or completing production storage.",
        ),
        _row(
            "schema_validation_acceptance_evidence_is_read_only",
            schema_acceptance_evidence.get("schema_version")
            == "command_center_3_storage_schema_validation_acceptance_evidence.v1"
            and schema_acceptance_evidence.get("status")
            in {
                "schema_acceptance_evidence_meta_missing",
                "schema_acceptance_evidence_packet_missing",
                "schema_acceptance_evidence_packet_read_failed",
                "schema_acceptance_evidence_packet_decode_failed",
                "schema_acceptance_evidence_partial_or_blocked",
                "schema_acceptance_evidence_passed_all_local_datasets",
            }
            and schema_acceptance_evidence.get("dataset_count") == len(canonical_datasets)
            and schema_acceptance_evidence.get("physical_schema_validation_done") is schema_evidence_done
            and schema_acceptance_evidence.get("physical_schema_validation_done_count")
            == schema_acceptance_evidence.get("accepted_dataset_count")
            and schema_acceptance_evidence.get("cache_get_writes_files") is False
            and schema_acceptance_evidence.get("cache_get_reads_row_payloads") is False
            and schema_acceptance_evidence.get("schema_migration_executed") is False
            and schema_acceptance_evidence.get("production_storage_complete") is False
            and _flag_false(
                schema_acceptance_evidence,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and schema_acceptance_evidence.get("does_not_execute_trades") is True
            and schema_acceptance_evidence.get("does_not_modify_strategy_action") is True,
            "Latest schema acceptance evidence may be missing, partial, or passed, but GET must remain read-only, no-provider, no-trade, and no action mutation.",
        ),
        _row(
            "physical_durable_evidence_recipe_is_local_pending",
            durable_evidence_recipe.get("schema_version")
            == "command_center_3_storage_physical_durable_evidence_recipe.v1"
            and durable_evidence_recipe.get("scope")
            == "local_storage_physical_durable_evidence_recipe_no_write_no_delete_no_provider"
            and durable_evidence_recipe.get("status")
            == "storage_physical_durable_evidence_recipe_ready_production_pending"
            and durable_evidence_recipe.get("local_recipe_ready") is True
            and durable_evidence_recipe.get("durable_evidence_complete") is False
            and durable_evidence_recipe.get("durable_promotion_ready") is False
            and durable_evidence_recipe.get("production_storage_complete") is False
            and durable_evidence_recipe.get("physical_schema_validation_done") is schema_evidence_done
            and durable_evidence_recipe.get("schema_migration_executed") is schema_migration_noop_verified
            and durable_evidence_recipe.get("dataset_version_manifest_validated") is manifest_validation_done
            and durable_evidence_recipe.get("partition_migration_executed") is False
            and durable_evidence_recipe.get("physical_compaction_executed") is False
            and durable_evidence_recipe.get("cache_ttl_refresh_executed") is False
            and durable_evidence_recipe.get("artifact_cleanup_review_done") is artifact_cleanup_review_done
            and durable_evidence_recipe.get("artifact_cleanup_delete_executed") is False
            and durable_evidence_recipe.get("duckdb_read_validation_done") is duckdb_read_validation_done
            and durable_evidence_recipe.get("dataset_version_manifest_written_by_recipe") is False
            and durable_evidence_recipe.get("provider_refresh_called_by_recipe") is False
            and durable_evidence_recipe.get("cache_get_writes_files") is False
            and durable_evidence_recipe.get("writes_parquet") is False
            and durable_evidence_recipe.get("writes_manifest") is False
            and durable_evidence_recipe.get("deletes_artifacts") is False
            and _flag_false(durable_evidence_recipe, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and durable_evidence_recipe.get("does_not_execute_trades") is True
            and durable_evidence_recipe.get("does_not_modify_strategy_action") is True
            and durable_evidence_recipe.get("contains_secret") is False
            and tuple(durable_evidence_recipe.get("evidence_keys") or ())
            == REQUIRED_STORAGE_PHYSICAL_DURABLE_EVIDENCE_KEYS
            and set(durable_evidence_recipe.get("missing_durable_evidence") or []) == expected_durable_missing
            and set(durable_evidence_rows) == set(REQUIRED_STORAGE_PHYSICAL_DURABLE_EVIDENCE_KEYS)
            and {
                "physical schema validation acceptance packet",
                "dataset version manifest write and validation receipts",
                "DuckDB post-migration read-only query contract",
                "production promotion review",
            }.issubset(set(durable_evidence_recipe.get("required_evidence") or []))
            and {
                "treat_durable_recipe_as_physical_execution",
                "create_storage_write_from_get_cache",
                "write_parquet_from_recipe",
                "delete_artifacts_from_recipe",
                "call_Tushare_from_recipe",
                "mark_production_storage_complete_from_recipe",
            }.issubset(set(durable_evidence_recipe.get("not_allowed_next_steps") or []))
            and all(row.get("required_before_production") is True for row in durable_evidence_rows.values())
            and all(row.get("production_ready") is False for row in durable_evidence_rows.values())
            and all(row.get("writes_parquet") is False for row in durable_evidence_rows.values())
            and all(row.get("writes_manifest") is False for row in durable_evidence_rows.values())
            and all(row.get("deletes_artifacts") is False for row in durable_evidence_rows.values())
            and all(row.get("refreshes_providers") is False for row in durable_evidence_rows.values())
            and all(row.get("external_calls_triggered") is False for row in durable_evidence_rows.values())
            and all(row.get("tushare_called") is False for row in durable_evidence_rows.values())
            and all(row.get("deepseek_called") is False for row in durable_evidence_rows.values())
            and all(row.get("github_called") is False for row in durable_evidence_rows.values())
            and all(row.get("does_not_execute_trades") is True for row in durable_evidence_rows.values())
            and all(row.get("does_not_modify_strategy_action") is True for row in durable_evidence_rows.values())
            and all(row.get("contains_secret") is False for row in durable_evidence_rows.values()),
            "Physical durable evidence recipe must expose the production evidence gap while remaining local-only, no-write, no-provider, no-delete, no-trade, and pending.",
        ),
        _row(
            "physical_migration_stage_scope_manifest_is_complete_and_pending",
            [row.get("stage_key") for row in physical_migration_stage_scope_rows]
            == list(REQUIRED_PHYSICAL_MIGRATION_STAGES)
            and all(
                isinstance(row, dict)
                and row.get("scope") == "storage_physical_migration_stage_scope_manifest"
                and row.get("required_before_production") is True
                and row.get("physical_schema_validation_done") is False
                and row.get("schema_migration_executed") is False
                and row.get("dataset_version_manifest_validated") is False
                and row.get("partition_migration_executed") is False
                and row.get("physical_compaction_executed") is False
                and row.get("cache_ttl_refresh_executed") is False
                and row.get("artifact_cleanup_delete_executed") is False
                and row.get("production_storage_complete") is False
                and row.get("writes_parquet_on_get") is False
                and row.get("writes_parquet_by_contract") is False
                and row.get("reads_row_payloads") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called_by_contract") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                and row.get("contains_secret") is False
                for row in physical_migration_stage_scope_rows
            ),
            "Physical storage migration stages must be visible as a pending local scope manifest without writes, provider calls, deletes, or production completion.",
        ),
        _row(
            "schema_migration_preflight_is_not_physical_migration",
            schema_preflight.get("schema_version") == "command_center_3_storage_schema_migration_preflight.v1"
            and (
                (
                    schema_preflight.get("status") == "preflight_ready"
                    and schema_preflight.get("physical_validation_done_count") == 0
                    and schema_preflight.get("migration_executed_count") == 0
                    and schema_preflight.get("schema_migration_ready_count") == 0
                    and schema_preflight.get("manual_migration_task_required") is True
                    and schema_preflight.get("schema_migration_task_executed") is False
                )
                or (
                    schema_preflight.get("status") == "schema_migration_execution_noop_verified"
                    and schema_preflight.get("physical_validation_done_count") == len(canonical_datasets)
                    and schema_preflight.get("migration_executed_count") == len(canonical_datasets)
                    and schema_preflight.get("schema_migration_ready_count") == len(canonical_datasets)
                    and schema_preflight.get("manual_migration_task_required") is False
                    and schema_preflight.get("schema_migration_task_executed") is True
                    and schema_migration_noop_verified
                )
            )
            and schema_preflight.get("cache_get_writes_files") is False
            and schema_preflight.get("payload_reads_on_get") is False
            and _flag_false(schema_preflight, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Schema migration preflight may be pending or backed by no-op local evidence; neither state is production storage completion.",
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
            and _manifest_hash_evidence_is_consistent(dataset_version_manifest_evidence)
            and _flag_false(dataset_version_manifest_evidence, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and dataset_version_manifest_evidence.get("does_not_execute_trades") is True
            and dataset_version_manifest_evidence.get("does_not_modify_strategy_action") is True,
            "Dataset version manifest evidence may read local _dataset_versions.json metadata and expose a safe sha256 fingerprint only; it must not write a manifest, read Parquet payloads, call providers, or mark production storage complete.",
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
            and manifest_packet.get("proposed_manifest_hash_algorithm") == "sha256"
            and _is_sha256(manifest_packet.get("proposed_manifest_content_sha256"))
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
            "backtest_results_schema_seed_is_confirm_gated_zero_row",
            schema_seed_packet.get("schema_version") == "command_center_3_storage_backtest_results_schema_seed.v1"
            and schema_seed_packet.get("status") == "backtest_results_schema_seed_blocked_confirmation_required"
            and schema_seed_packet.get("confirm_schema_seed") is False
            and schema_seed_packet.get("schema_seed_write_executed") is False
            and schema_seed_packet.get("schema_seed_written_on_post") is False
            and schema_seed_packet.get("schema_seed_written_on_get") is False
            and schema_seed_packet.get("schema_seed_ready_for_schema_acceptance") is False
            and schema_seed_packet.get("target_dataset") == "backtest_results"
            and schema_seed_packet.get("row_count_written") == 0
            and schema_seed_packet.get("expected_row_count_written") == 0
            and schema_seed_packet.get("writes_only_ignored_local_parquet") is True
            and schema_seed_packet.get("writes_backtest_result_rows") is False
            and schema_seed_packet.get("mock_backtest_result_written") is False
            and schema_seed_packet.get("post_task_reads_row_payloads") is False
            and schema_seed_packet.get("post_task_reads_env_files") is False
            and schema_seed_packet.get("writes_manifest") is False
            and schema_seed_packet.get("schema_migration_executed") is False
            and schema_seed_packet.get("production_storage_complete") is False
            and _flag_false(schema_seed_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and schema_seed_packet.get("does_not_execute_trades") is True
            and schema_seed_packet.get("does_not_modify_strategy_action") is True
            and schema_seed_packet.get("contains_secret") is False
            and backtest_schema_seed_evidence.get("schema_version")
            == "command_center_3_storage_backtest_results_schema_seed.v1"
            and backtest_schema_seed_evidence.get("cache_get_writes_files") is False
            and backtest_schema_seed_evidence.get("post_task_reads_row_payloads") is False
            and backtest_schema_seed_evidence.get("writes_backtest_result_rows") is False
            and backtest_schema_seed_evidence.get("mock_backtest_result_written") is False,
            "backtest_results schema seed must be a confirm-gated zero-row local Parquet schema seed; GET evidence stays read-only and no mock backtest rows may be written.",
        ),
        _row(
            "dataset_version_manifest_review_writes_no_manifest",
            manifest_review_packet.get("schema_version") == "command_center_3_storage_dataset_version_manifest_review.v1"
            and manifest_review_packet.get("status")
            in {"manifest_review_ready_for_manual_write", "manifest_review_blocked"}
            and manifest_review_packet.get("dataset_count") == len(canonical_datasets)
            and len(_list(manifest_review_packet.get("rows"))) == len(canonical_datasets)
            and manifest_review_packet.get("manifest_write_executed") is False
            and manifest_review_packet.get("manifest_written_on_post") is False
            and manifest_review_packet.get("post_review_writes_manifest") is False
            and manifest_review_packet.get("post_review_writes_parquet") is False
            and manifest_review_packet.get("post_review_reads_parquet_payloads") is False
            and manifest_review_packet.get("post_review_reads_env_files") is False
            and manifest_review_packet.get("schema_migration_executed") is False
            and manifest_review_packet.get("dataset_version_manifest_validated") is False
            and manifest_review_packet.get("production_storage_complete") is False
            and manifest_review_packet.get("manual_review_required_before_write") is True
            and manifest_review_packet.get("separate_write_task_required") is True
            and _flag_false(manifest_review_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and manifest_review_packet.get("does_not_execute_trades") is True
            and manifest_review_packet.get("does_not_modify_strategy_action") is True,
            "Dataset version manifest review may compare dry-run and schema acceptance rows, but it must not write the manifest, write Parquet, read payloads, call providers, or complete production storage.",
        ),
        _row(
            "schema_validation_acceptance_writes_no_parquet",
            schema_acceptance_packet.get("schema_version") == "command_center_3_storage_schema_validation_acceptance.v1"
            and schema_acceptance_packet.get("status")
            in {"schema_acceptance_passed_all_local_datasets", "schema_acceptance_partial_or_blocked"}
            and schema_acceptance_packet.get("dataset_count") == len(canonical_datasets)
            and len(_list(schema_acceptance_packet.get("rows"))) == len(canonical_datasets)
            and schema_acceptance_packet.get("post_acceptance_writes_parquet") is False
            and schema_acceptance_packet.get("post_acceptance_reads_row_payloads") is False
            and schema_acceptance_packet.get("post_acceptance_reads_env_files") is False
            and schema_acceptance_packet.get("schema_migration_executed") is False
            and schema_acceptance_packet.get("production_storage_complete") is False
            and _flag_false(schema_acceptance_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and schema_acceptance_packet.get("does_not_execute_trades") is True
            and schema_acceptance_packet.get("does_not_modify_strategy_action") is True,
            "Schema validation acceptance may record physical schema metadata acceptance rows, but it must not read payloads, write Parquet, execute migration, call providers, trade, or complete production storage.",
        ),
        _row(
            "dataset_version_manifest_validate_writes_no_manifest",
            manifest_validate_packet.get("schema_version") == "command_center_3_storage_dataset_version_manifest_validate.v1"
            and manifest_validate_packet.get("status")
            in {"manifest_validate_passed_local_only", "manifest_validate_blocked"}
            and manifest_validate_packet.get("dataset_count") == len(canonical_datasets)
            and len(_list(manifest_validate_packet.get("rows"))) == len(canonical_datasets)
            and manifest_validate_packet.get("manifest_write_executed") is False
            and manifest_validate_packet.get("manifest_written_on_post") is False
            and manifest_validate_packet.get("post_validate_writes_manifest") is False
            and manifest_validate_packet.get("post_validate_writes_parquet") is False
            and manifest_validate_packet.get("post_validate_reads_parquet_payloads") is False
            and manifest_validate_packet.get("post_validate_reads_env_files") is False
            and manifest_validate_packet.get("schema_migration_executed") is False
            and manifest_validate_packet.get("partition_migration_executed") is False
            and manifest_validate_packet.get("physical_compaction_executed") is False
            and manifest_validate_packet.get("cache_ttl_refresh_executed") is False
            and manifest_validate_packet.get("production_storage_complete") is False
            and manifest_validate_packet.get("separate_production_promotion_required") is True
            and _flag_false(manifest_validate_packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and manifest_validate_packet.get("does_not_execute_trades") is True
            and manifest_validate_packet.get("does_not_modify_strategy_action") is True,
            "Dataset version manifest validate may read local manifest evidence, but it must not write manifest, write Parquet, read payloads, call providers, or complete production storage.",
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
            and task_rows["run_storage_schema_validation_acceptance"].get("writes_parquet_on_post") is False
            and task_rows["run_storage_schema_validation_acceptance"].get("reads_row_payloads") is False
            and task_rows["run_storage_schema_validation_acceptance"].get("schema_migration_executed") is False
            and task_rows["run_storage_schema_validation_acceptance"].get("production_storage_complete") is False
            and task_rows["run_storage_schema_migration_execution"].get("requires_confirm_schema_migration_execution") is True
            and task_rows["run_storage_schema_migration_execution"].get("writes_parquet_on_post") is False
            and task_rows["run_storage_schema_migration_execution"].get("writes_manifest_on_post") is False
            and task_rows["run_storage_schema_migration_execution"].get("reads_row_payloads") is False
            and task_rows["run_storage_schema_migration_execution"].get("reads_env_files") is False
            and task_rows["run_storage_schema_migration_execution"].get("schema_migration_rewrite_executed") is False
            and task_rows["run_storage_schema_migration_execution"].get("production_storage_complete") is False
            and task_rows["run_storage_backtest_results_schema_seed"].get("current_backend") == "local_schema_seed_pipeline"
            and task_rows["run_storage_backtest_results_schema_seed"].get("requires_confirm_schema_seed") is True
            and task_rows["run_storage_backtest_results_schema_seed"].get("writes_parquet_on_post") is True
            and task_rows["run_storage_backtest_results_schema_seed"].get("writes_only_ignored_local_parquet") is True
            and task_rows["run_storage_backtest_results_schema_seed"].get("target_dataset") == "backtest_results"
            and task_rows["run_storage_backtest_results_schema_seed"].get("writes_backtest_result_rows") is False
            and task_rows["run_storage_backtest_results_schema_seed"].get("mock_backtest_result_written") is False
            and task_rows["run_storage_backtest_results_schema_seed"].get("writes_manifest_on_post") is False
            and task_rows["run_storage_backtest_results_schema_seed"].get("reads_row_payloads") is False
            and task_rows["run_storage_backtest_results_schema_seed"].get("reads_env_files") is False
            and task_rows["run_storage_backtest_results_schema_seed"].get("schema_migration_executed") is False
            and task_rows["run_storage_backtest_results_schema_seed"].get("production_storage_complete") is False
            and task_rows["run_storage_dataset_version_manifest_dry_run"].get("writes_manifest_on_post") is False
            and task_rows["run_storage_dataset_version_manifest_dry_run"].get("manifest_write_executed") is False
            and task_rows["run_storage_dataset_version_manifest_review"].get("writes_manifest_on_post") is False
            and task_rows["run_storage_dataset_version_manifest_review"].get("manifest_write_executed") is False
            and task_rows["run_storage_dataset_version_manifest_review"].get("production_storage_complete") is False
            and task_rows["run_storage_dataset_version_manifest_review"].get("requires_separate_manifest_write") is True
            and task_rows["run_storage_dataset_version_manifest_write"].get("writes_manifest_on_post") is True
            and task_rows["run_storage_dataset_version_manifest_write"].get("requires_confirm_manifest_write") is True
            and task_rows["run_storage_dataset_version_manifest_write"].get("writes_parquet_on_post") is False
            and task_rows["run_storage_dataset_version_manifest_write"].get("reads_row_payloads") is False
            and task_rows["run_storage_dataset_version_manifest_write"].get("cache_get_external_calls") is False
            and task_rows["run_storage_dataset_version_manifest_validate"].get("writes_manifest_on_post") is False
            and task_rows["run_storage_dataset_version_manifest_validate"].get("manifest_write_executed") is False
            and task_rows["run_storage_dataset_version_manifest_validate"].get("requires_prior_manifest_write") is True
            and task_rows["run_storage_dataset_version_manifest_validate"].get("requires_separate_production_promotion") is True
            and task_rows["run_storage_dataset_version_manifest_validate"].get("schema_migration_executed") is False
            and task_rows["run_storage_dataset_version_manifest_validate"].get("production_storage_complete") is False
            and task_rows["run_storage_partition_migration_dry_run"].get("partition_migration_executed") is False
            and task_rows["run_storage_compaction_dry_run"].get("physical_compaction_executed") is False
            and task_rows["run_storage_cache_ttl_dry_run"].get("refresh_executed") is False
            and task_rows["run_storage_physical_execution_request"].get("local_execution_request_only") is True
            and task_rows["run_storage_physical_execution_request"].get("requires_bound_scope_hash") is True
            and task_rows["run_storage_physical_execution_request"].get("creates_physical_task") is False
            and task_rows["run_storage_physical_execution_request"].get("physical_task_executed_by_request") is False
            and task_rows["run_storage_physical_execution_request"].get("physical_execution_implemented") is False
            and task_rows["run_storage_physical_execution_request"].get("writes_parquet_on_post") is False
            and task_rows["run_storage_physical_execution_request"].get("writes_manifest_on_post") is False
            and task_rows["run_storage_physical_execution_request"].get("deletes_artifacts_on_post") is False
            and task_rows["run_storage_physical_execution_request"].get("refreshes_external_sources_on_post") is False
            and task_rows["run_storage_physical_execution_request"].get("production_storage_complete") is False
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
            and "command_center_3_storage_physical_migration_activation_receipt.v1" in this_script
            and "command_center_3_storage_physical_execution_recipe.v1" in this_script
            and "command_center_3_storage_physical_execution_request.v1" in this_script
            and "command_center_3_storage_physical_durable_evidence_recipe.v1" in this_script
            and "physical_migration_activation_receipt_keeps_execution_pending" in this_script
            and "physical_execution_recipe_is_local_pending" in this_script
            and "physical_execution_request_is_scope_bound_local" in this_script
            and "physical_durable_evidence_recipe_is_local_pending" in this_script
            and "physical_migration_stage_scope_manifest_is_complete_and_pending" in this_script
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
        "physical_schema_validation_done": schema_evidence_done,
        "schema_validation_acceptance_evidence_status": schema_acceptance_evidence.get("status"),
        "schema_validation_acceptance_accepted_dataset_count": schema_acceptance_evidence.get(
            "accepted_dataset_count"
        ),
        "schema_validation_acceptance_blocked_dataset_count": schema_acceptance_evidence.get("blocked_dataset_count"),
        "schema_migration_executed": schema_migration_executed,
        "schema_migration_execution_status": schema_migration_execution_evidence.get("status"),
        "schema_migration_rewrite_executed": False,
        "dataset_version_manifest_validated": manifest_validation_done,
        "dataset_version_manifest_validate_status": manifest_validate_evidence.get("status"),
        "dataset_version_manifest_evidence_validated": bool(
            dataset_version_manifest_evidence.get("dataset_version_manifest_validated")
        ),
        "dataset_version_manifest_dry_run_writes_manifest": False,
        "dataset_version_manifest_review_writes_manifest": False,
        "dataset_version_manifest_write_task_available": True,
        "dataset_version_manifest_validate_writes_manifest": False,
        "storage_production_readiness_receipt_ready": bool(readiness_receipt.get("local_receipt_ready")),
        "storage_production_readiness_receipt_status": readiness_receipt.get("status"),
        "storage_physical_migration_activation_receipt_ready": bool(
            activation_receipt.get("local_activation_receipt_ready")
        ),
        "storage_physical_migration_activation_status": activation_receipt.get("status"),
        "storage_physical_execution_recipe_ready": bool(physical_execution_recipe.get("local_recipe_ready")),
        "storage_physical_execution_recipe_status": physical_execution_recipe.get("status"),
        "storage_physical_durable_evidence_recipe_ready": bool(
            durable_evidence_recipe.get("local_recipe_ready")
        ),
        "storage_physical_durable_evidence_recipe_status": durable_evidence_recipe.get("status"),
        "storage_physical_durable_evidence_production_blocker_count": durable_evidence_recipe.get(
            "production_blocker_count"
        ),
        "duckdb_read_validation_done": duckdb_read_validation_done,
        "duckdb_read_validation_status": duckdb_read_validation_evidence.get("status"),
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
            "storage_production_readiness_receipt_status": readiness_receipt.get("status"),
            "storage_production_readiness_receipt_ready": readiness_receipt.get("local_receipt_ready"),
            "storage_physical_migration_activation_status": activation_receipt.get("status"),
            "storage_physical_migration_activation_ready": activation_receipt.get("local_activation_receipt_ready"),
            "storage_physical_execution_recipe_status": physical_execution_recipe.get("status"),
            "storage_physical_execution_recipe_ready": physical_execution_recipe.get("local_recipe_ready"),
            "storage_physical_execution_phase_count": len(physical_execution_rows),
            "storage_physical_execution_phase_keys": [
                row.get("phase") for row in physical_execution_rows.values()
            ],
            "storage_physical_execution_pending_phase_count": sum(
                1 for row in physical_execution_rows.values() if row.get("execution_done") is False
            ),
            "storage_physical_execution_request_status": physical_execution_request_packet.get("status"),
            "storage_physical_execution_request_ready": physical_execution_request_packet.get(
                "local_execution_request_ready"
            ),
            "storage_physical_execution_request_scope_hash_present": _is_sha256(
                physical_execution_request_packet.get("physical_execution_scope_hash")
            ),
            "storage_physical_durable_evidence_recipe_status": durable_evidence_recipe.get("status"),
            "storage_physical_durable_evidence_recipe_ready": durable_evidence_recipe.get("local_recipe_ready"),
            "storage_physical_durable_evidence_key_count": len(durable_evidence_rows),
            "storage_physical_durable_evidence_keys": [
                row.get("evidence_key") for row in durable_evidence_rows.values()
            ],
            "storage_physical_durable_evidence_production_blocker_count": durable_evidence_recipe.get(
                "production_blocker_count"
            ),
            "schema_validation_acceptance_evidence_status": schema_acceptance_evidence.get("status"),
            "schema_validation_acceptance_source_packet_status": schema_acceptance_evidence.get(
                "source_packet_status"
            ),
            "schema_validation_acceptance_accepted_dataset_count": schema_acceptance_evidence.get(
                "accepted_dataset_count"
            ),
            "schema_validation_acceptance_blocked_dataset_count": schema_acceptance_evidence.get(
                "blocked_dataset_count"
            ),
            "physical_schema_validation_done": schema_evidence_done,
            "schema_migration_preflight_status": schema_preflight.get("status"),
            "schema_migration_execution_status": schema_migration_execution_evidence.get("status"),
            "schema_migration_noop_verified": schema_migration_noop_verified,
            "dataset_version_policy_status": dataset_version_policy.get("status"),
            "dataset_version_manifest_evidence_status": dataset_version_manifest_evidence.get("status"),
            "dataset_version_manifest_evidence_validated_count": dataset_version_manifest_evidence.get("validated_dataset_count"),
            "dataset_version_manifest_dry_run_status": manifest_packet.get("status"),
            "dataset_version_manifest_dry_run_would_change_count": manifest_packet.get("would_change_count"),
            "dataset_version_manifest_dry_run_hash_algorithm": manifest_packet.get("proposed_manifest_hash_algorithm"),
            "dataset_version_manifest_dry_run_hash_present": _is_sha256(
                manifest_packet.get("proposed_manifest_content_sha256")
            ),
            "dataset_version_manifest_review_status": manifest_review_packet.get("status"),
            "dataset_version_manifest_validate_status": manifest_validate_packet.get("status"),
            "dataset_version_manifest_evidence_hash_algorithm": dataset_version_manifest_evidence.get(
                "manifest_hash_algorithm"
            ),
            "dataset_version_manifest_evidence_hash_present": _is_sha256(
                dataset_version_manifest_evidence.get("manifest_content_sha256")
            ),
            "duckdb_query_service_status": duckdb_policy.get("status"),
            "schema_validation_status": schema_packet.get("status"),
            "schema_validation_acceptance_status": schema_acceptance_packet.get("status"),
            "partition_migration_status": partition_packet.get("status"),
            "compaction_status": compaction_packet.get("status"),
            "cache_ttl_status": ttl_packet.get("status"),
            "artifact_cleanup_status": cleanup_packet.get("status"),
            "artifact_cleanup_review_done": artifact_cleanup_review_done,
            "artifact_cleanup_review_status": cleanup_review.get("status"),
            "artifact_cleanup_review_required_step_count": cleanup_review.get("required_review_step_count"),
            "physical_migration_stage_scope_count": len(physical_migration_stage_scope_rows),
            "physical_migration_stage_scope_keys": [
                row.get("stage_key") for row in physical_migration_stage_scope_rows
            ],
            "physical_migration_stage_scope_pending_count": sum(
                1
                for row in physical_migration_stage_scope_rows
                if row.get("production_storage_complete") is False
            ),
        },
        "storage_physical_execution_request_packet": physical_execution_request_packet,
        "storage_physical_execution_recipe_rows": list(physical_execution_rows.values()),
        "storage_physical_durable_evidence_rows": list(durable_evidence_rows.values()),
        "physical_migration_stage_scope_rows": physical_migration_stage_scope_rows,
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
            "production_storage_complete: false; schema_migration_executed: {schema_migration_executed}".format(
                **{
                    **contract,
                    "schema_migration_executed": str(bool(contract.get("schema_migration_executed"))).lower(),
                }
            )
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
