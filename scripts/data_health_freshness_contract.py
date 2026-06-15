#!/usr/bin/env python3
"""Validate the local LTG-01 Data Health freshness contract.

This script is a push-gate guard, not a provider acceptance run. It calls only
the local Data Health cache builder and fails on unsafe regressions such as
external-call flags, trade/action mutation flags, or false provider-backed
completion claims.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import data_health_service, packet_service, task_service, tushare_task_service  # noqa: E402
from storage.sqlite_meta import SQLiteMetaStore  # noqa: E402


CONTRACT_KEYS = [
    "freshness_acceptance_summary",
    "freshness_long_window_sample_validation",
    "trade_cal_physical_validation",
    "trade_cal_provider_acceptance_runbook",
    "local_tushare_refresh_packet_summary",
    "trade_cal_provider_acceptance_promotion_audit",
    "freshness_production_blocker_audit",
    "freshness_provider_acceptance_readiness_receipt",
    "freshness_provider_acceptance_activation_receipt",
    "latest_trade_cal_provider_acceptance_dry_run",
    "trade_cal_provider_acceptance_next_execution_recipe",
    "latest_trade_cal_provider_acceptance_execution_request",
    "latest_tushare_provider_target_sample_execution_request",
    "current_evidence_freshness_qa_contract",
    "current_evidence_decision_surface_audit",
    "current_evidence_producer_coverage_audit",
    "current_evidence_producer_generation_contract",
]
REQUIRED_FRESHNESS_PRODUCTION_STAGE_KEYS = {
    "acceptance_matrix_boundary",
    "synthetic_long_window_replay",
    "local_trade_cal_artifact_validation",
    "provider_trade_cal_long_window_task",
    "provider_call_ledger_safe_fields",
    "provider_freshness_replay_evidence",
    "provider_failure_mode_evidence",
    "current_evidence_producer_expected_dates",
    "decision_surface_isolation_review",
    "promotion_and_release_review",
}
FRESHNESS_PRODUCTION_STAGE_LABELS = {
    "acceptance_matrix_boundary": "local acceptance matrix stays separate from provider evidence",
    "synthetic_long_window_replay": "synthetic long-window replay stays fixture evidence",
    "local_trade_cal_artifact_validation": "local trade_cal artifact validation stays physical evidence",
    "provider_trade_cal_long_window_task": "explicit provider trade_cal long-window task is required",
    "provider_call_ledger_safe_fields": "provider call ledger safe fields are required",
    "provider_freshness_replay_evidence": "provider-backed freshness replay evidence is required",
    "provider_failure_mode_evidence": "provider-backed failure-mode evidence is required",
    "current_evidence_producer_expected_dates": "current evidence producers need expected-date coverage",
    "decision_surface_isolation_review": "decision surfaces must stay isolated from stale evidence",
    "promotion_and_release_review": "promotion and release review is required",
}
LOCAL_FRESHNESS_STAGE_EVIDENCE_KEYS = {
    "acceptance_matrix_boundary",
    "synthetic_long_window_replay",
    "local_trade_cal_artifact_validation",
    "current_evidence_producer_expected_dates",
    "decision_surface_isolation_review",
}
REQUIRED_FRESHNESS_DURABLE_EVIDENCE_KEYS = {
    "local_freshness_matrix_regression",
    "local_trade_cal_artifact_validation",
    "provider_trade_cal_scope_ticket",
    "explicit_provider_trade_cal_task",
    "safe_provider_call_ledger",
    "provider_freshness_replay",
    "provider_failure_mode_evidence",
    "current_evidence_producer_coverage",
    "decision_surface_isolation",
    "production_promotion_review",
}


def _get(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _serialized(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _freshness_production_stage_scope_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    missing_evidence = [
        "explicit provider trade_cal long-window task",
        "provider call ledger with safe fields",
        "730-day schema and window evidence",
        "provider-backed freshness replay evidence",
        "provider-backed failure-mode evidence",
        "current evidence producer coverage review",
        "promotion and release review",
    ]
    for stage_key in sorted(REQUIRED_FRESHNESS_PRODUCTION_STAGE_KEYS):
        rows.append(
            {
                "stage_key": stage_key,
                "stage_label": FRESHNESS_PRODUCTION_STAGE_LABELS[stage_key],
                "scope": "freshness_production_stage_scope_manifest",
                "current_status": (
                    "local_evidence_ready_provider_acceptance_pending"
                    if stage_key in LOCAL_FRESHNESS_STAGE_EVIDENCE_KEYS
                    else "provider_direct_evidence_pending"
                ),
                "target_status": "provider_backed_freshness_direct_evidence_required",
                "local_stage_evidence_present": stage_key in LOCAL_FRESHNESS_STAGE_EVIDENCE_KEYS,
                "required_before_production_freshness": True,
                "provider_backed_trade_cal_acceptance_done": False,
                "production_freshness_gate_complete": False,
                "real_trade_cal_long_window_validation_done": False,
                "provider_refresh_called_by_contract": False,
                "provider_execution_implemented": False,
                "provider_call_ledger_evidence_done": False,
                "freshness_replay_provider_evidence_done": False,
                "failure_mode_provider_evidence_done": False,
                "current_evidence_producer_coverage_complete": False,
                "decision_surface_mutated_by_contract": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "missing_evidence": missing_evidence,
            }
        )
    return rows


def _run_trade_cal_dry_run_contract_cases() -> dict[str, dict[str, Any]]:
    original_token = os.environ.get("TUSHARE_TOKEN")
    original_packet_path = packet_service.SQLITE_META_PATH
    original_meta_path = task_service.SQLITE_META_PATH
    original_tushare_task_path = tushare_task_service.SQLITE_META_PATH
    fake_token = "TS_OK"
    try:
        with tempfile.TemporaryDirectory(prefix="stock_ming_data_health_contract_") as temp_dir:
            db_path = Path(temp_dir) / "meta.sqlite"
            packet_service.SQLITE_META_PATH = db_path
            task_service.SQLITE_META_PATH = db_path
            tushare_task_service.SQLITE_META_PATH = db_path
            task_service.clear_task_statuses_for_tests(clear_persisted=True)

            os.environ["TUSHARE_TOKEN"] = fake_token
            ready = data_health_service.run_trade_cal_provider_acceptance_dry_run(
                {
                    "approved_by_user": True,
                    "apis": ["trade_cal", "daily_basic"],
                    "exchange": ["SSE", "SZSE"],
                    "start_date": "20240614",
                    "end_date": "20260614",
                    "token": "SHOULD_DROP",
                }
            )
            latest_after_ready_cache = data_health_service.read_data_health_timeline_cache()
            ready_payload = _as_dict(ready.get("payload_safe"))
            ready_receipt = _as_dict(ready_payload.get("trade_cal_provider_acceptance_dry_run_receipt"))
            execution_request = data_health_service.run_trade_cal_provider_acceptance_execution_request(
                {
                    "approved_by_user": True,
                    "acceptance_scope_hash_short": ready_receipt.get("acceptance_scope_hash_short"),
                    "apis": ["trade_cal"],
                    "exchange": ["SSE", "SZSE"],
                    "start_date": "20240614",
                    "end_date": "20260614",
                    "requested_by": "contract",
                    "token": "SHOULD_DROP",
                }
            )
            latest_after_execution_request_cache = data_health_service.read_data_health_timeline_cache()
            execution_request_mismatch = data_health_service.run_trade_cal_provider_acceptance_execution_request(
                {
                    "approved_by_user": True,
                    "acceptance_scope_hash_short": "deadbeefdeadbeef",
                    "apis": ["trade_cal"],
                    "exchange": ["SSE", "SZSE"],
                    "start_date": "20240614",
                    "end_date": "20260614",
                }
            )

            target_sample_scope_hash = "targetsampledeadbeef0011223344556677"
            target_sample_scope_hash_short = target_sample_scope_hash[:16]
            SQLiteMetaStore(db_path).write_packet(
                "command_center_tushare_refresh_packet",
                {
                    "packet_key": "command_center_tushare_refresh_packet",
                    "schema_version": "command_center_tushare_refresh_packet.v1",
                    "status": "local_contract_target_sample_execution_recipe_fixture",
                    "selected_apis": ["margin_detail"],
                    "call_ledger": [
                        {
                            "api": "local_contract_target_sample_execution_recipe_fixture",
                            "external": False,
                            "external_calls_triggered": False,
                            "tushare_called": False,
                            "deepseek_called": False,
                            "github_called": False,
                            "does_not_execute_trades": True,
                            "does_not_modify_strategy_action": True,
                        }
                    ],
                    "provider_target_sample_execution_recipe": {
                        "schema_version": "tushare_provider_target_sample_execution_recipe.v1",
                        "status": "target_sample_execution_recipe_ready_user_confirmation_required",
                        "scope": "local_contract_target_sample_execution_recipe_no_provider",
                        "recipe_ready_for_user_confirmation": True,
                        "provider_task_created_by_recipe": False,
                        "recipe_external_calls_triggered": False,
                        "tushare_called_by_recipe": False,
                        "execution_recipe_scope_hash": target_sample_scope_hash,
                        "execution_recipe_scope_hash_short": target_sample_scope_hash_short,
                        "requested_targets": ["margin_financing"],
                        "rows": [
                            {
                                "target": "margin_financing",
                                "requested_for_execution_recipe": True,
                                "selected_apis": ["margin_detail"],
                                "status": "ready",
                                "external_calls_triggered": False,
                                "tushare_called": False,
                                "deepseek_called": False,
                                "github_called": False,
                            }
                        ],
                    },
                    "external_calls_triggered": False,
                    "tushare_called": False,
                    "deepseek_called": False,
                    "github_called": False,
                    "does_not_execute_trades": True,
                    "does_not_modify_strategy_action": True,
                },
            )
            target_sample_execution_request = tushare_task_service.run_tushare_provider_target_sample_execution_request(
                {
                    "operator_approved": True,
                    "execution_recipe_scope_hash": target_sample_scope_hash_short,
                    "target_sample_acceptance_groups": ["margin_financing"],
                    "apis": ["margin_detail"],
                    "ts_code": "002008.SZ",
                    "trade_date": "20260610",
                    "token": "SHOULD_DROP",
                }
            )
            latest_after_target_sample_execution_request_cache = data_health_service.read_data_health_timeline_cache()

            missing_approval = data_health_service.run_trade_cal_provider_acceptance_dry_run(
                {
                    "apis": ["trade_cal"],
                    "exchange": ["SSE"],
                    "start_date": "20240614",
                    "end_date": "20260614",
                }
            )

            short_window = data_health_service.run_trade_cal_provider_acceptance_dry_run(
                {
                    "approved_by_user": True,
                    "apis": ["trade_cal"],
                    "exchange": ["SSE"],
                    "start_date": "20260613",
                    "end_date": "20260614",
                }
            )

            os.environ.pop("TUSHARE_TOKEN", None)
            missing_credentials = data_health_service.run_trade_cal_provider_acceptance_dry_run(
                {
                    "approved_by_user": True,
                    "apis": ["trade_cal"],
                    "exchange": ["SSE", "SZSE"],
                    "start_date": "20240614",
                    "end_date": "20260614",
                }
            )

            return {
                "ready": ready,
                "missing_approval": missing_approval,
                "short_window": short_window,
                "missing_credentials": missing_credentials,
                "latest_after_ready_cache": latest_after_ready_cache,
                "execution_request": execution_request,
                "latest_after_execution_request_cache": latest_after_execution_request_cache,
                "execution_request_mismatch": execution_request_mismatch,
                "target_sample_execution_request": target_sample_execution_request,
                "latest_after_target_sample_execution_request_cache": (
                    latest_after_target_sample_execution_request_cache
                ),
                "_fake_token": {"value": fake_token},
            }
    finally:
        if original_token is None:
            os.environ.pop("TUSHARE_TOKEN", None)
        else:
            os.environ["TUSHARE_TOKEN"] = original_token
        task_service.clear_task_statuses_for_tests(clear_persisted=False)
        packet_service.SQLITE_META_PATH = original_packet_path
        task_service.SQLITE_META_PATH = original_meta_path
        tushare_task_service.SQLITE_META_PATH = original_tushare_task_path


def build_contract() -> dict[str, Any]:
    packet = data_health_service.read_data_health_timeline_cache()
    dry_run_cases = _run_trade_cal_dry_run_contract_cases()
    dry_ready = dry_run_cases["ready"]
    dry_missing_approval = dry_run_cases["missing_approval"]
    dry_short_window = dry_run_cases["short_window"]
    dry_missing_credentials = dry_run_cases["missing_credentials"]
    execution_request = dry_run_cases["execution_request"]
    execution_request_mismatch = dry_run_cases["execution_request_mismatch"]
    target_sample_execution_request = dry_run_cases["target_sample_execution_request"]
    dry_ready_payload = _as_dict(dry_ready.get("payload_safe"))
    dry_ready_receipt = _as_dict(dry_ready_payload.get("trade_cal_provider_acceptance_dry_run_receipt"))
    dry_ready_rows = {
        str(row.get("criterion") or ""): row
        for row in _as_list(dry_ready_payload.get("trade_cal_provider_acceptance_dry_run_rows"))
        if isinstance(row, dict)
    }
    dry_ready_ledger = [_as_dict(row) for row in _as_list(dry_ready.get("call_ledger"))]
    latest_after_ready_cache = _as_dict(dry_run_cases.get("latest_after_ready_cache"))
    latest_after_ready = _get(latest_after_ready_cache, "latest_trade_cal_provider_acceptance_dry_run")
    latest_after_ready_recipe = _get(
        latest_after_ready_cache, "trade_cal_provider_acceptance_next_execution_recipe"
    )
    latest_after_ready_counts = _get(latest_after_ready_cache, "counts")
    latest_after_ready_policy = _get(latest_after_ready_cache, "policy")
    latest_after_ready_rows = _as_list(latest_after_ready_cache.get("latest_trade_cal_provider_acceptance_dry_run_rows"))
    latest_after_ready_recipe_rows = _as_list(
        latest_after_ready_cache.get("trade_cal_provider_acceptance_next_execution_rows")
    )
    execution_request_payload = _as_dict(execution_request.get("payload_safe"))
    execution_request_receipt = _as_dict(
        execution_request_payload.get("trade_cal_provider_acceptance_execution_request_receipt")
    )
    execution_request_rows = {
        str(row.get("phase") or ""): row
        for row in _as_list(execution_request_payload.get("trade_cal_provider_acceptance_execution_request_rows"))
        if isinstance(row, dict)
    }
    execution_request_ledger = [_as_dict(row) for row in _as_list(execution_request.get("call_ledger"))]
    latest_after_execution_request_cache = _as_dict(dry_run_cases.get("latest_after_execution_request_cache"))
    latest_after_execution_request = _get(
        latest_after_execution_request_cache,
        "latest_trade_cal_provider_acceptance_execution_request",
    )
    latest_after_execution_request_rows = _as_list(
        latest_after_execution_request_cache.get("latest_trade_cal_provider_acceptance_execution_request_rows")
    )
    latest_after_execution_request_counts = _get(latest_after_execution_request_cache, "counts")
    latest_after_execution_request_policy = _get(latest_after_execution_request_cache, "policy")
    target_sample_execution_request_payload = _as_dict(target_sample_execution_request.get("payload_safe"))
    target_sample_execution_request_receipt = _as_dict(
        target_sample_execution_request_payload.get("provider_target_sample_execution_request_receipt")
    )
    target_sample_execution_request_rows = {
        str(row.get("criterion") or ""): row
        for row in _as_list(
            target_sample_execution_request_payload.get("provider_target_sample_execution_request_rows")
        )
        if isinstance(row, dict)
    }
    target_sample_execution_request_ledger = [
        _as_dict(row) for row in _as_list(target_sample_execution_request.get("call_ledger"))
    ]
    latest_after_target_sample_execution_request_cache = _as_dict(
        dry_run_cases.get("latest_after_target_sample_execution_request_cache")
    )
    latest_after_target_sample_execution_request = _get(
        latest_after_target_sample_execution_request_cache,
        "latest_tushare_provider_target_sample_execution_request",
    )
    latest_after_target_sample_execution_request_rows = _as_list(
        latest_after_target_sample_execution_request_cache.get(
            "latest_tushare_provider_target_sample_execution_request_rows"
        )
    )
    latest_after_target_sample_execution_request_counts = _get(
        latest_after_target_sample_execution_request_cache, "counts"
    )
    latest_after_target_sample_execution_request_policy = _get(
        latest_after_target_sample_execution_request_cache, "policy"
    )
    execution_request_mismatch_receipt = _as_dict(
        _as_dict(execution_request_mismatch.get("payload_safe")).get(
            "trade_cal_provider_acceptance_execution_request_receipt"
        )
    )
    latest_after_ready_credential_rows = [
        _as_dict(row)
        for row in _as_list(latest_after_ready_cache.get("latest_trade_cal_provider_acceptance_dry_run_credential_rows"))
    ]
    dry_missing_approval_receipt = _as_dict(
        _as_dict(dry_missing_approval.get("payload_safe")).get("trade_cal_provider_acceptance_dry_run_receipt")
    )
    dry_short_window_receipt = _as_dict(
        _as_dict(dry_short_window.get("payload_safe")).get("trade_cal_provider_acceptance_dry_run_receipt")
    )
    dry_missing_credentials_receipt = _as_dict(
        _as_dict(dry_missing_credentials.get("payload_safe")).get("trade_cal_provider_acceptance_dry_run_receipt")
    )
    dry_run_serialized = _serialized(
        {
            "ready": dry_ready,
            "missing_approval": dry_missing_approval,
            "short_window": dry_short_window,
            "missing_credentials": dry_missing_credentials,
            "latest_after_ready_cache": latest_after_ready_cache,
            "execution_request": execution_request,
            "latest_after_execution_request_cache": latest_after_execution_request_cache,
            "execution_request_mismatch": execution_request_mismatch,
            "target_sample_execution_request": target_sample_execution_request,
            "latest_after_target_sample_execution_request_cache": (
                latest_after_target_sample_execution_request_cache
            ),
        }
    )
    fake_token = str(_as_dict(dry_run_cases.get("_fake_token")).get("value") or "")
    summary = _get(packet, "freshness_acceptance_summary")
    sample = _get(packet, "freshness_long_window_sample_validation")
    physical = _get(packet, "trade_cal_physical_validation")
    runbook = _get(packet, "trade_cal_provider_acceptance_runbook")
    local_tushare_refresh = _get(packet, "local_tushare_refresh_packet_summary")
    promotion = _get(packet, "trade_cal_provider_acceptance_promotion_audit")
    blockers_audit = _get(packet, "freshness_production_blocker_audit")
    readiness_receipt = _get(packet, "freshness_provider_acceptance_readiness_receipt")
    activation_receipt = _get(packet, "freshness_provider_acceptance_activation_receipt")
    next_execution_recipe = _get(packet, "trade_cal_provider_acceptance_next_execution_recipe")
    next_execution_recipe_rows = _as_list(packet.get("trade_cal_provider_acceptance_next_execution_rows"))
    latest_execution_request = _get(packet, "latest_trade_cal_provider_acceptance_execution_request")
    durable_evidence_recipe = _get(packet, "freshness_durable_evidence_recipe")
    durable_evidence_rows = [
        row for row in _as_list(packet.get("freshness_durable_evidence_rows")) if isinstance(row, dict)
    ]
    durable_evidence_keys = {str(row.get("evidence_key") or "") for row in durable_evidence_rows}
    current = _get(packet, "current_evidence_freshness_qa_contract")
    surfaces = _get(packet, "current_evidence_decision_surface_audit")
    producers = _get(packet, "current_evidence_producer_coverage_audit")
    producer_generation = _get(packet, "current_evidence_producer_generation_contract")
    producer_generation_rows = [
        row for row in _as_list(packet.get("current_evidence_producer_generation_rows")) if isinstance(row, dict)
    ]
    policy = _get(packet, "policy")
    counts = _get(packet, "counts")
    production_stage_scope_rows = _freshness_production_stage_scope_rows()
    production_stage_scope_keys = {str(row.get("stage_key") or "") for row in production_stage_scope_rows}
    production_stage_scope_ready = (
        production_stage_scope_keys == REQUIRED_FRESHNESS_PRODUCTION_STAGE_KEYS
        and all(
            row.get("scope") == "freshness_production_stage_scope_manifest"
            and row.get("target_status") == "provider_backed_freshness_direct_evidence_required"
            and row.get("required_before_production_freshness") is True
            and row.get("provider_backed_trade_cal_acceptance_done") is False
            and row.get("production_freshness_gate_complete") is False
            and row.get("real_trade_cal_long_window_validation_done") is False
            and row.get("provider_refresh_called_by_contract") is False
            and row.get("provider_execution_implemented") is False
            and row.get("provider_call_ledger_evidence_done") is False
            and row.get("freshness_replay_provider_evidence_done") is False
            and row.get("failure_mode_provider_evidence_done") is False
            and row.get("current_evidence_producer_coverage_complete") is False
            and row.get("decision_surface_mutated_by_contract") is False
            and row.get("cache_get_external_calls") is False
            and row.get("react_render_external_calls") is False
            and row.get("external_calls_triggered") is False
            and row.get("tushare_called") is False
            and row.get("deepseek_called") is False
            and row.get("github_called") is False
            and row.get("does_not_execute_trades") is True
            and row.get("does_not_modify_strategy_action") is True
            and row.get("contains_secret") is False
            and len(_as_list(row.get("missing_evidence"))) >= 7
            for row in production_stage_scope_rows
        )
    )

    rows = [
        _row(
            "packet_cache_only_boundary",
            packet.get("mode") == "cache_only"
            and packet.get("cache_only") is True
            and packet.get("read_only") is True
            and _flag_false(packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "GET data health cache must remain local/read-only and no-provider.",
        ),
        _row(
            "packet_no_trade_or_action_mutation",
            packet.get("does_not_execute_trades") is True and packet.get("does_not_modify_strategy_action") is True,
            "Data Health must not execute trades or mutate strategy action.",
        ),
        _row(
            "acceptance_matrix_is_not_provider_acceptance",
            summary.get("scope") == "local_contract_not_real_trade_cal_validation"
            and summary.get("trade_cal_long_window_validation_done") is False
            and summary.get("real_provider_validation_done") is False
            and summary.get("blocks_composite_score") is True
            and summary.get("blocks_support_factors") is True
            and summary.get("blocks_evidence_preview") is True
            and summary.get("blocks_next_session_bridge_preview") is True,
            "Freshness matrix must stay a local boundary contract, not a real trade_cal acceptance run.",
        ),
        _row(
            "synthetic_sample_is_fixture",
            sample.get("fixture_is_synthetic") is True
            and sample.get("uses_actual_freshness_gate") is True
            and sample.get("trade_cal_long_window_validation_done") is False
            and _flag_false(sample, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Long-window sample must remain a local fixture that exercises the gate without provider calls.",
        ),
        _row(
            "local_trade_cal_physical_not_provider_backed",
            physical.get("scope") == "local_physical_trade_cal_parquet_validation"
            and physical.get("provider_backed_long_window_acceptance_done") is False
            and physical.get("provider_refresh_called_by_validation") is False
            and _flag_false(physical, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Local trade_cal artifact validation cannot imply provider-backed acceptance.",
        ),
        _row(
            "provider_runbook_execution_pending",
            runbook.get("schema_version") == "data_health_trade_cal_provider_acceptance_runbook.v1"
            and runbook.get("local_runbook_ready") is True
            and runbook.get("provider_backed_long_window_acceptance_done") is False
            and runbook.get("provider_refresh_called_by_runbook") is False
            and runbook.get("production_freshness_gate_complete") is False
            and _flag_false(runbook, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Provider runbook may be ready, but execution and provider-backed acceptance must remain pending.",
        ),
        _row(
            "provider_promotion_audit_is_read_only_pending",
            promotion.get("schema_version") == "data_health_trade_cal_provider_acceptance_promotion_audit.v1"
            and promotion.get("scope") == "local_snapshot_evidence_promotion_audit_no_provider_execution"
            and promotion.get("status")
            in {
                "trade_cal_provider_acceptance_promotion_pending",
                "trade_cal_provider_acceptance_promotion_ready",
            }
            and promotion.get("provider_refresh_called_by_audit") is False
            and promotion.get("production_freshness_gate_complete") is False
            and _flag_false(promotion, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "Provider acceptance promotion audit must read local prior evidence only and never run trade_cal refresh itself.",
        ),
        _row(
            "local_tushare_refresh_packet_lookup_is_read_only",
            local_tushare_refresh.get("schema_version") == "data_health_local_tushare_refresh_packet_summary.v1"
            and local_tushare_refresh.get("source_packet_key") == "command_center_tushare_refresh_packet"
            and local_tushare_refresh.get("read_only_sqlite_packet_lookup") is True
            and local_tushare_refresh.get("cache_get_external_calls") is False
            and local_tushare_refresh.get("provider_backed_acceptance_done") is False
            and local_tushare_refresh.get("production_tushare_pipeline_complete") is False
            and _flag_false(
                local_tushare_refresh,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and policy.get("local_tushare_refresh_packet_lookup_is_read_only") is True
            and policy.get("local_tushare_refresh_packet_lookup_calls_provider") is False,
            "Data Health may read the persisted Tushare refresh packet as local evidence, but the lookup must stay read-only and no-provider.",
        ),
        _row(
            "freshness_production_blocker_audit_is_local_pending",
            blockers_audit.get("schema_version") == "data_health_freshness_production_blocker_audit.v1"
            and blockers_audit.get("scope") == "local_read_only_freshness_production_blocker_audit_no_provider_execution"
            and blockers_audit.get("status") == "freshness_production_blockers_visible"
            and blockers_audit.get("production_ready") is False
            and blockers_audit.get("provider_backed_trade_cal_acceptance_done") is False
            and blockers_audit.get("production_freshness_gate_complete") is False
            and int(blockers_audit.get("production_blocker_count") or 0) > 0
            and "provider_backed_trade_cal_acceptance" in blockers_audit.get("production_blockers", [])
            and _flag_false(blockers_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and blockers_audit.get("does_not_execute_trades") is True
            and blockers_audit.get("does_not_modify_strategy_action") is True,
            "Freshness production blocker audit must stay local and keep provider-backed production blockers visible.",
        ),
        _row(
            "provider_acceptance_readiness_receipt_is_local",
            readiness_receipt.get("schema_version")
            == "data_health_freshness_provider_acceptance_readiness_receipt.v1"
            and readiness_receipt.get("scope") == "local_readiness_receipt_no_provider_execution"
            and readiness_receipt.get("status")
            in {
                "provider_acceptance_receipt_ready_execution_pending",
                "provider_acceptance_receipt_ready_for_promotion_review",
                "provider_acceptance_receipt_blocked",
            }
            and readiness_receipt.get("production_freshness_gate_complete") is False
            and readiness_receipt.get("provider_refresh_called_by_receipt") is False
            and "GET /api/data-health/cache provider refresh"
            in readiness_receipt.get("not_allowed_next_steps", [])
            and _flag_false(readiness_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and readiness_receipt.get("does_not_execute_trades") is True
            and readiness_receipt.get("does_not_modify_strategy_action") is True,
            "Provider acceptance readiness receipt must summarize the next safe step without calling providers or claiming production completion.",
        ),
        _row(
            "provider_acceptance_activation_receipt_is_local_pending",
            activation_receipt.get("schema_version")
            == "data_health_freshness_provider_acceptance_activation_receipt.v1"
            and activation_receipt.get("scope") == "local_activation_receipt_no_provider_execution"
            and activation_receipt.get("status")
            in {
                "provider_acceptance_activation_ready_execution_pending",
                "provider_acceptance_activation_blocked_local_readiness",
                "provider_acceptance_activation_blocked_local_contract",
            }
            and activation_receipt.get("local_activation_receipt_ready") is True
            and activation_receipt.get("allowed_next_step")
            in {
                "explicit_post_task_trade_cal_provider_acceptance",
                "resolve_local_freshness_acceptance_blockers",
            }
            and "GET /api/data-health/cache provider refresh"
            in activation_receipt.get("not_allowed_next_steps", [])
            and "activation receipt as production freshness completion"
            in activation_receipt.get("not_allowed_next_steps", [])
            and "provider-backed trade_cal task execution" in activation_receipt.get("missing_evidence_items", [])
            and "provider call ledger with safe fields" in activation_receipt.get("missing_evidence_items", [])
            and activation_receipt.get("provider_acceptance_task_executed_by_receipt") is False
            and activation_receipt.get("provider_refresh_called_by_receipt") is False
            and activation_receipt.get("cache_get_external_calls") is False
            and activation_receipt.get("react_render_external_calls") is False
            and activation_receipt.get("production_freshness_gate_complete") is False
            and _flag_false(activation_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and activation_receipt.get("does_not_execute_trades") is True
            and activation_receipt.get("does_not_modify_strategy_action") is True
            and activation_receipt.get("contains_secret") is False,
            "Provider acceptance activation receipt must stay a local checklist: either explicit POST is the next step or local blockers remain visible, provider evidence remains missing, and cache/render paths must not call providers or claim production completion.",
        ),
        _row(
            "trade_cal_next_execution_recipe_is_local_and_not_execution",
            next_execution_recipe.get("schema_version")
            == "data_health_trade_cal_provider_acceptance_next_execution_recipe.v1"
            and next_execution_recipe.get("scope") == "local_next_execution_recipe_no_provider_execution"
            and next_execution_recipe.get("status")
            in {
                "trade_cal_provider_acceptance_recipe_ready_user_confirmation_required",
                "trade_cal_provider_acceptance_recipe_waiting_for_dry_run_scope_ticket",
                "trade_cal_provider_acceptance_recipe_blocked_local_readiness",
            }
            and next_execution_recipe.get("ready_to_execute_from_cache") is False
            and next_execution_recipe.get("requires_explicit_user_confirmation") is True
            and next_execution_recipe.get("requires_prior_dry_run_scope_ticket") is True
            and next_execution_recipe.get("dry_run_route") == "POST /api/data-health/trade-cal-provider-acceptance-dry-run"
            and next_execution_recipe.get("target_post_task_route") == "POST /api/tasks/refresh-tushare-facts"
            and next_execution_recipe.get("target_task_type") == "refresh_tushare_facts"
            and next_execution_recipe.get("target_acceptance_mode") == "provider_backed_trade_cal_long_window"
            and _as_dict(next_execution_recipe.get("target_payload_safe")).get("apis") == ["trade_cal"]
            and "skip dry-run scope ticket" in next_execution_recipe.get("not_allowed_next_steps", [])
            and "skip user confirmation" in next_execution_recipe.get("not_allowed_next_steps", [])
            and "promote recipe to provider-backed acceptance"
            in next_execution_recipe.get("not_allowed_next_steps", [])
            and next_execution_recipe.get("provider_refresh_called_by_recipe") is False
            and next_execution_recipe.get("cache_get_external_calls") is False
            and next_execution_recipe.get("react_render_external_calls") is False
            and next_execution_recipe.get("provider_backed_long_window_acceptance_done") is False
            and next_execution_recipe.get("production_freshness_gate_complete") is False
            and _flag_false(
                next_execution_recipe,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
                "contains_secret",
            )
            and next_execution_recipe.get("does_not_execute_trades") is True
            and next_execution_recipe.get("does_not_modify_strategy_action") is True
            and int(next_execution_recipe.get("row_count") or 0) == len(next_execution_recipe_rows)
            and len(next_execution_recipe_rows) >= 10
            and policy.get("trade_cal_provider_acceptance_next_execution_recipe_is_local") is True
            and policy.get("trade_cal_provider_acceptance_next_execution_recipe_calls_provider") is False
            and policy.get("trade_cal_provider_acceptance_next_execution_recipe_requires_dry_run") is True
            and policy.get("trade_cal_provider_acceptance_next_execution_recipe_is_not_acceptance") is True,
            "The next-execution recipe may describe the explicit future POST task, but it must stay local, require a dry-run scope ticket plus user confirmation, and never run provider calls itself.",
        ),
        _row(
            "freshness_durable_evidence_recipe_is_local_provider_pending",
            durable_evidence_recipe.get("schema_version") == "data_health_freshness_durable_evidence_recipe.v1"
            and durable_evidence_recipe.get("scope")
            == "local_freshness_durable_evidence_recipe_no_provider_execution"
            and durable_evidence_recipe.get("status")
            in {
                "freshness_durable_evidence_recipe_ready_provider_pending",
                "freshness_durable_evidence_recipe_blocked_local_contract",
            }
            and durable_evidence_recipe.get("local_recipe_ready") is True
            and durable_evidence_recipe.get("durable_evidence_complete") is False
            and durable_evidence_recipe.get("durable_promotion_ready") is False
            and durable_evidence_recipe.get("provider_backed_trade_cal_acceptance_done") is False
            and durable_evidence_recipe.get("production_freshness_gate_complete") is False
            and durable_evidence_recipe.get("real_trade_cal_long_window_validation_done") is False
            and durable_evidence_recipe.get("provider_execution_implemented") is False
            and durable_evidence_recipe.get("provider_refresh_called_by_recipe") is False
            and durable_evidence_keys == REQUIRED_FRESHNESS_DURABLE_EVIDENCE_KEYS
            and len(durable_evidence_rows) == len(REQUIRED_FRESHNESS_DURABLE_EVIDENCE_KEYS)
            and int(durable_evidence_recipe.get("durable_evidence_blocker_count") or 0) > 0
            and int(durable_evidence_recipe.get("durable_evidence_blocker_count") or 0)
            == sum(1 for row in durable_evidence_rows if row.get("production_blocker") is True)
            and "explicit_provider_trade_cal_task" in set(durable_evidence_recipe.get("blocking_evidence_keys") or [])
            and "safe_provider_call_ledger" in set(durable_evidence_recipe.get("blocking_evidence_keys") or [])
            and "provider_freshness_replay" in set(durable_evidence_recipe.get("blocking_evidence_keys") or [])
            and "provider_failure_mode_evidence" in set(durable_evidence_recipe.get("blocking_evidence_keys") or [])
            and "treat durable recipe as provider-backed trade_cal acceptance"
            in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "treat dry-run scope ticket as provider execution"
            in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "treat synthetic replay as provider replay"
            in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "treat local trade_cal artifact as provider acceptance"
            in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and "set production_freshness_gate_complete from cache/render"
            in durable_evidence_recipe.get("not_allowed_next_steps", [])
            and all(row.get("scope") == "freshness_durable_evidence_recipe" for row in durable_evidence_rows)
            and all(row.get("provider_backed_trade_cal_acceptance_done") is False for row in durable_evidence_rows)
            and all(row.get("production_freshness_gate_complete") is False for row in durable_evidence_rows)
            and all(row.get("provider_refresh_called_by_recipe") is False for row in durable_evidence_rows)
            and all(row.get("provider_execution_implemented") is False for row in durable_evidence_rows)
            and all(row.get("provider_call_ledger_evidence_done") is False for row in durable_evidence_rows)
            and all(row.get("freshness_replay_provider_evidence_done") is False for row in durable_evidence_rows)
            and all(row.get("failure_mode_provider_evidence_done") is False for row in durable_evidence_rows)
            and all(row.get("cache_get_external_calls") is False for row in durable_evidence_rows)
            and all(row.get("react_render_external_calls") is False for row in durable_evidence_rows)
            and all(row.get("external_calls_triggered") is False for row in durable_evidence_rows)
            and all(row.get("tushare_called") is False for row in durable_evidence_rows)
            and all(row.get("deepseek_called") is False for row in durable_evidence_rows)
            and all(row.get("github_called") is False for row in durable_evidence_rows)
            and all(row.get("does_not_execute_trades") is True for row in durable_evidence_rows)
            and all(row.get("does_not_modify_strategy_action") is True for row in durable_evidence_rows)
            and all(row.get("contains_secret") is False for row in durable_evidence_rows)
            and _as_list(durable_evidence_recipe.get("call_ledger"))
            and _as_dict(_as_list(durable_evidence_recipe.get("call_ledger"))[0]).get("api")
            == "local_freshness_durable_evidence_recipe"
            and _as_dict(_as_list(durable_evidence_recipe.get("call_ledger"))[0]).get("external") is False
            and policy.get("freshness_durable_evidence_recipe_is_local") is True
            and policy.get("freshness_durable_evidence_recipe_calls_provider") is False
            and policy.get("freshness_durable_evidence_recipe_creates_task") is False
            and policy.get("freshness_durable_evidence_recipe_is_not_provider_acceptance") is True
            and policy.get("freshness_durable_evidence_recipe_is_not_production_completion") is True
            and policy.get("freshness_durable_evidence_requires_provider_call_ledger") is True,
            "Freshness durable evidence recipe must enumerate provider task, call ledger, replay, failure-mode, producer, decision-surface, and promotion evidence without calling providers or claiming production completion.",
        ),
        _row(
            "trade_cal_dry_run_scope_ticket_is_local_no_provider",
            dry_ready.get("status") == "success"
            and dry_ready.get("task_type") == "run_trade_cal_provider_acceptance_dry_run"
            and dry_ready.get("current_step") == "trade_cal_acceptance_dry_run_ready_real_execution_still_blocked"
            and dry_ready_receipt.get("status") == "trade_cal_acceptance_dry_run_ready_real_execution_still_blocked"
            and dry_ready_receipt.get("route") == "POST /api/data-health/trade-cal-provider-acceptance-dry-run"
            and dry_ready_receipt.get("target_route") == "POST /api/tasks/refresh-tushare-facts"
            and dry_ready_receipt.get("selected_apis") == ["trade_cal"]
            and dry_ready_receipt.get("ignored_apis") == ["daily_basic"]
            and dry_ready_receipt.get("acceptance_mode") == "provider_backed_trade_cal_long_window"
            and len(str(dry_ready_receipt.get("acceptance_scope_hash_short") or "")) == 16
            and _as_dict(dry_ready_receipt.get("credential_presence_summary")).get("status")
            == "all_required_env_keys_present_no_values_read"
            and dry_ready_receipt.get("ready_to_execute_real_provider_task") is False
            and dry_ready_receipt.get("provider_execution_implemented") is False
            and dry_ready_receipt.get("production_freshness_gate_complete") is False
            and dry_ready_rows.get("server_credential_presence_checked", {}).get("status") == "passed_no_values_read"
            and dry_ready_ledger
            and dry_ready_ledger[0].get("api") == "local_trade_cal_provider_acceptance_dry_run"
            and dry_ready_ledger[0].get("external") is False
            and _flag_false(dry_ready, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and dry_ready.get("does_not_execute_trades") is True
            and dry_ready.get("does_not_modify_strategy_action") is True,
            "The dry-run ticket may bind a future trade_cal acceptance scope, but it must stay local and keep real execution/promotion blocked.",
        ),
        _row(
            "latest_trade_cal_dry_run_cache_lookup_is_local_read_only",
            latest_after_ready_cache.get("mode") == "cache_only"
            and latest_after_ready_cache.get("read_only") is True
            and latest_after_ready.get("schema_version")
            == "data_health_latest_trade_cal_provider_acceptance_dry_run.v1"
            and latest_after_ready.get("status") == "latest_trade_cal_provider_acceptance_dry_run_visible"
            and latest_after_ready.get("scope") == "local_task_status_lookup_no_provider_execution"
            and latest_after_ready.get("latest_task_found") is True
            and latest_after_ready.get("receipt_visible") is True
            and latest_after_ready.get("latest_task_id") == dry_ready.get("task_id")
            and latest_after_ready.get("dry_run_status") == dry_ready_receipt.get("status")
            and latest_after_ready.get("selected_apis") == ["trade_cal"]
            and latest_after_ready.get("ignored_apis") == ["daily_basic"]
            and latest_after_ready.get("row_count") == len(dry_ready_rows)
            and latest_after_ready.get("credential_row_count") == len(latest_after_ready_credential_rows)
            and latest_after_ready.get("provider_execution_implemented") is False
            and latest_after_ready.get("provider_backed_long_window_acceptance_done") is False
            and latest_after_ready.get("production_freshness_gate_complete") is False
            and latest_after_ready.get("cache_get_creates_task") is False
            and latest_after_ready.get("cache_get_external_calls") is False
            and _flag_false(
                latest_after_ready,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
                "contains_secret",
            )
            and latest_after_ready.get("does_not_execute_trades") is True
            and latest_after_ready.get("does_not_modify_strategy_action") is True
            and int(latest_after_ready_counts.get("latest_trade_cal_provider_acceptance_dry_run_found") or 0) == 1
            and int(latest_after_ready_counts.get("latest_trade_cal_provider_acceptance_dry_run_row_count") or 0)
            == len(latest_after_ready_rows)
            and latest_after_ready_policy.get("latest_trade_cal_provider_acceptance_dry_run_lookup_is_local") is True
            and latest_after_ready_policy.get("latest_trade_cal_provider_acceptance_dry_run_lookup_creates_task")
            is False
            and latest_after_ready_policy.get("latest_trade_cal_provider_acceptance_dry_run_lookup_calls_provider")
            is False
            and latest_after_ready_policy.get("latest_trade_cal_provider_acceptance_dry_run_is_not_acceptance") is True
            and latest_after_ready_credential_rows
            and "credential_refs" not in latest_after_ready_credential_rows[0]
            and fake_token not in dry_run_serialized
            and "SHOULD_DROP" not in dry_run_serialized
            and "TUSHARE_TOKEN" not in dry_run_serialized,
            "GET Data Health cache may replay the latest local trade_cal dry-run task metadata, but it must not create a task, call providers, leak credentials, or claim provider-backed acceptance.",
        ),
        _row(
            "trade_cal_next_execution_recipe_binds_dry_run_scope_without_execution",
            latest_after_ready_recipe.get("schema_version")
            == "data_health_trade_cal_provider_acceptance_next_execution_recipe.v1"
            and latest_after_ready_recipe.get("status")
            in {
                "trade_cal_provider_acceptance_recipe_ready_user_confirmation_required",
                "trade_cal_provider_acceptance_recipe_blocked_local_readiness",
            }
            and latest_after_ready_recipe.get("recipe_ready_for_user_confirmation")
            is (
                latest_after_ready_recipe.get("status")
                == "trade_cal_provider_acceptance_recipe_ready_user_confirmation_required"
            )
            and latest_after_ready_recipe.get("latest_dry_run_scope_ticket_visible") is True
            and latest_after_ready_recipe.get("latest_dry_run_scope_hash_short")
            == dry_ready_receipt.get("acceptance_scope_hash_short")
            and _as_dict(latest_after_ready_recipe.get("target_payload_safe")).get("acceptance_scope_hash_short")
            == dry_ready_receipt.get("acceptance_scope_hash_short")
            and latest_after_ready_recipe.get("allowed_next_step")
            in {
                "user_confirmed_post_refresh_tushare_facts_with_bound_scope_ticket",
                "resolve_local_freshness_acceptance_blockers_before_provider_task",
            }
            and latest_after_ready_recipe.get("ready_to_execute_from_cache") is False
            and latest_after_ready_recipe.get("provider_refresh_called_by_recipe") is False
            and latest_after_ready_recipe.get("provider_backed_long_window_acceptance_done") is False
            and latest_after_ready_recipe.get("production_freshness_gate_complete") is False
            and _flag_false(
                latest_after_ready_recipe,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
                "contains_secret",
            )
            and any(
                _as_dict(row).get("phase") == "dry_run_scope_ticket_required"
                and _as_dict(row).get("status") == "passed_scope_ticket_visible"
                for row in latest_after_ready_recipe_rows
            )
            and int(latest_after_ready_recipe.get("blocking_row_count") or 0)
            == int(latest_after_ready_counts.get("trade_cal_provider_acceptance_next_execution_blocker_count") or 0)
            and int(latest_after_ready_counts.get("trade_cal_provider_acceptance_next_execution_row_count") or 0)
            == len(latest_after_ready_recipe_rows)
            and len(latest_after_ready_recipe_rows) >= 10,
            "After a local dry-run scope ticket is visible, the recipe must bind that scope and remain local; it may still require local freshness blockers to be resolved before user-confirmed provider execution.",
        ),
        _row(
            "trade_cal_execution_request_binds_scope_without_provider_call",
            execution_request.get("status") == "success"
            and execution_request.get("task_type") == "run_trade_cal_provider_acceptance_execution_request"
            and execution_request.get("current_step")
            in {
                "trade_cal_execution_request_ready_manual_provider_task_pending_no_provider_call",
                "trade_cal_execution_request_blocked_local_readiness_no_provider_call",
            }
            and execution_request_receipt.get("schema_version")
            == "data_health_trade_cal_provider_acceptance_execution_request.v1"
            and execution_request_receipt.get("route")
            == "POST /api/data-health/trade-cal-provider-acceptance-execution-request"
            and execution_request_receipt.get("dry_run_route")
            == "POST /api/data-health/trade-cal-provider-acceptance-dry-run"
            and execution_request_receipt.get("target_post_task_route") == "POST /api/tasks/refresh-tushare-facts"
            and execution_request_receipt.get("target_task_type") == "refresh_tushare_facts"
            and execution_request_receipt.get("selected_apis") == ["trade_cal"]
            and execution_request_receipt.get("latest_dry_run_scope_hash_short")
            == dry_ready_receipt.get("acceptance_scope_hash_short")
            and execution_request_receipt.get("requested_scope_hash_short")
            == dry_ready_receipt.get("acceptance_scope_hash_short")
            and execution_request_receipt.get("scope_hash_matches_latest_dry_run") is True
            and execution_request_receipt.get("ready_for_manual_provider_task_submission")
            is (
                execution_request_receipt.get("status")
                == "trade_cal_provider_acceptance_execution_request_ready_manual_provider_task_pending"
            )
            and execution_request_receipt.get("ready_to_execute_from_cache") is False
            and execution_request_receipt.get("creates_provider_task") is False
            and execution_request_receipt.get("provider_task_executed_by_request") is False
            and execution_request_receipt.get("provider_execution_implemented") is False
            and execution_request_receipt.get("provider_backed_long_window_acceptance_done") is False
            and execution_request_receipt.get("production_freshness_gate_complete") is False
            and "execute provider from execution request ticket"
            in execution_request_receipt.get("not_allowed_next_steps", [])
            and "promote execution request to provider-backed acceptance"
            in execution_request_receipt.get("not_allowed_next_steps", [])
            and execution_request_rows.get("scope_hash_matches_latest_dry_run", {}).get("status")
            == "passed_scope_hash_match"
            and execution_request_rows.get("safe_payload_fields_only", {}).get("status") == "passed_safe_payload"
            and execution_request_ledger
            and execution_request_ledger[0].get("api") == "local_trade_cal_provider_acceptance_execution_request"
            and execution_request_ledger[0].get("external") is False
            and _flag_false(
                execution_request,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and execution_request.get("does_not_execute_trades") is True
            and execution_request.get("does_not_modify_strategy_action") is True,
            "The execution request ticket must bind the latest dry-run scope hash and remain a local request artifact; it cannot create provider tasks, call Tushare, or promote production freshness.",
        ),
        _row(
            "latest_trade_cal_execution_request_cache_lookup_is_local_read_only",
            latest_after_execution_request_cache.get("mode") == "cache_only"
            and latest_after_execution_request_cache.get("read_only") is True
            and latest_after_execution_request.get("schema_version")
            == "data_health_latest_trade_cal_provider_acceptance_execution_request.v1"
            and latest_after_execution_request.get("status")
            == "latest_trade_cal_provider_acceptance_execution_request_visible"
            and latest_after_execution_request.get("scope") == "local_task_status_lookup_no_provider_execution"
            and latest_after_execution_request.get("latest_task_found") is True
            and latest_after_execution_request.get("receipt_visible") is True
            and latest_after_execution_request.get("latest_task_id") == execution_request.get("task_id")
            and latest_after_execution_request.get("execution_request_status") == execution_request_receipt.get("status")
            and latest_after_execution_request.get("scope_hash_matches_latest_dry_run") is True
            and latest_after_execution_request.get("creates_provider_task") is False
            and latest_after_execution_request.get("provider_task_executed_by_request") is False
            and latest_after_execution_request.get("provider_execution_implemented") is False
            and latest_after_execution_request.get("provider_backed_long_window_acceptance_done") is False
            and latest_after_execution_request.get("production_freshness_gate_complete") is False
            and latest_after_execution_request.get("cache_get_creates_task") is False
            and latest_after_execution_request.get("cache_get_external_calls") is False
            and _flag_false(
                latest_after_execution_request,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
                "contains_secret",
            )
            and int(
                latest_after_execution_request_counts.get(
                    "latest_trade_cal_provider_acceptance_execution_request_found"
                )
                or 0
            )
            == 1
            and int(
                latest_after_execution_request_counts.get(
                    "latest_trade_cal_provider_acceptance_execution_request_row_count"
                )
                or 0
            )
            == len(latest_after_execution_request_rows)
            and latest_after_execution_request_policy.get(
                "latest_trade_cal_provider_acceptance_execution_request_lookup_is_local"
            )
            is True
            and latest_after_execution_request_policy.get(
                "latest_trade_cal_provider_acceptance_execution_request_lookup_creates_task"
            )
            is False
            and latest_after_execution_request_policy.get(
                "latest_trade_cal_provider_acceptance_execution_request_lookup_calls_provider"
            )
            is False
            and latest_after_execution_request_policy.get(
                "latest_trade_cal_provider_acceptance_execution_request_is_not_acceptance"
            )
            is True
            and latest_after_execution_request_policy.get(
                "latest_trade_cal_provider_acceptance_execution_request_creates_provider_task"
            )
            is False
            and latest_after_execution_request_policy.get(
                "trade_cal_provider_acceptance_execution_request_requires_bound_scope_hash"
            )
            is True
            and fake_token not in dry_run_serialized
            and "SHOULD_DROP" not in dry_run_serialized
            and "TUSHARE_TOKEN" not in dry_run_serialized,
            "GET Data Health cache may replay the latest local execution request metadata, but it must not create a task, call providers, leak credentials, or claim provider-backed acceptance.",
        ),
        _row(
            "tushare_target_sample_execution_request_binds_scope_without_provider_call",
            target_sample_execution_request.get("status") == "success"
            and target_sample_execution_request.get("task_type")
            == "run_tushare_provider_target_sample_execution_request"
            and target_sample_execution_request.get("current_step")
            == "tushare_provider_target_sample_execution_request_ready"
            and target_sample_execution_request_receipt.get("schema_version")
            == "tushare_provider_target_sample_execution_request.v1"
            and target_sample_execution_request_receipt.get("status")
            == "target_sample_execution_request_ready_manual_provider_task_pending"
            and target_sample_execution_request_receipt.get("route")
            == "POST /api/tasks/tushare-provider-target-sample-execution-request"
            and target_sample_execution_request_receipt.get("target_post_task_route")
            == "POST /api/tasks/refresh-tushare-facts"
            and target_sample_execution_request_receipt.get("target_task_type") == "refresh_tushare_facts"
            and target_sample_execution_request_receipt.get("target_acceptance_mode")
            == "provider_target_sample_acceptance"
            and target_sample_execution_request_receipt.get("selected_apis") == ["margin_detail"]
            and target_sample_execution_request_receipt.get("requested_targets") == ["margin_financing"]
            and target_sample_execution_request_receipt.get("local_execution_request_ready") is True
            and target_sample_execution_request_receipt.get("ready_for_manual_provider_task_submission") is True
            and target_sample_execution_request_receipt.get("ready_to_execute_from_cache") is False
            and target_sample_execution_request_receipt.get("execution_recipe_scope_hash_matches_latest") is True
            and target_sample_execution_request_receipt.get("operator_confirmation_recorded") is True
            and target_sample_execution_request_receipt.get("creates_provider_task") is False
            and target_sample_execution_request_receipt.get("provider_task_executed_by_request") is False
            and target_sample_execution_request_receipt.get("provider_execution_implemented") is False
            and target_sample_execution_request_receipt.get("provider_call_ledger_evidence_done") is False
            and target_sample_execution_request_receipt.get("provider_backed_target_sample_acceptance_done") is False
            and target_sample_execution_request_receipt.get("full_interface_acceptance_done") is False
            and target_sample_execution_request_receipt.get("production_tushare_pipeline_complete") is False
            and target_sample_execution_request_rows.get("execution_recipe_scope_hash_bound", {}).get("status")
            == "passed"
            and target_sample_execution_request_rows.get("provider_task_still_pending", {}).get("status")
            == "passed"
            and target_sample_execution_request_ledger
            and target_sample_execution_request_ledger[0].get("api")
            == "local_tushare_provider_target_sample_execution_request"
            and target_sample_execution_request_ledger[0].get("external") is False
            and _flag_false(
                target_sample_execution_request,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and target_sample_execution_request.get("does_not_execute_trades") is True
            and target_sample_execution_request.get("does_not_modify_strategy_action") is True,
            "The Tushare target-sample execution-request ticket must bind a local recipe scope and remain a local request artifact; it cannot create provider tasks, call Tushare, or promote LTG-02 production completion.",
        ),
        _row(
            "latest_tushare_target_sample_execution_request_cache_lookup_is_local_read_only",
            latest_after_target_sample_execution_request_cache.get("mode") == "cache_only"
            and latest_after_target_sample_execution_request_cache.get("read_only") is True
            and latest_after_target_sample_execution_request.get("schema_version")
            == "data_health_latest_tushare_provider_target_sample_execution_request.v1"
            and latest_after_target_sample_execution_request.get("status")
            == "latest_tushare_provider_target_sample_execution_request_visible"
            and latest_after_target_sample_execution_request.get("scope")
            == "local_task_status_lookup_no_provider_execution"
            and latest_after_target_sample_execution_request.get("latest_task_found") is True
            and latest_after_target_sample_execution_request.get("receipt_visible") is True
            and latest_after_target_sample_execution_request.get("latest_task_id")
            == target_sample_execution_request.get("task_id")
            and latest_after_target_sample_execution_request.get("execution_request_status")
            == target_sample_execution_request_receipt.get("status")
            and latest_after_target_sample_execution_request.get("target_post_task_route")
            == "POST /api/tasks/refresh-tushare-facts"
            and latest_after_target_sample_execution_request.get("target_task_type") == "refresh_tushare_facts"
            and latest_after_target_sample_execution_request.get("target_acceptance_mode")
            == "provider_target_sample_acceptance"
            and latest_after_target_sample_execution_request.get("requested_targets") == ["margin_financing"]
            and latest_after_target_sample_execution_request.get("selected_apis") == ["margin_detail"]
            and latest_after_target_sample_execution_request.get("execution_recipe_scope_hash_matches_latest")
            is True
            and latest_after_target_sample_execution_request.get("local_execution_request_ready") is True
            and latest_after_target_sample_execution_request.get("ready_for_manual_provider_task_submission")
            is True
            and latest_after_target_sample_execution_request.get("creates_provider_task") is False
            and latest_after_target_sample_execution_request.get("provider_task_created") is False
            and latest_after_target_sample_execution_request.get("provider_task_executed_by_request") is False
            and latest_after_target_sample_execution_request.get("provider_execution_implemented") is False
            and latest_after_target_sample_execution_request.get("provider_call_ledger_evidence_done") is False
            and latest_after_target_sample_execution_request.get("provider_backed_target_sample_acceptance_done")
            is False
            and latest_after_target_sample_execution_request.get("full_interface_acceptance_done") is False
            and latest_after_target_sample_execution_request.get("production_tushare_pipeline_complete") is False
            and latest_after_target_sample_execution_request.get("cache_get_creates_task") is False
            and latest_after_target_sample_execution_request.get("cache_get_external_calls") is False
            and _flag_false(
                latest_after_target_sample_execution_request,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
                "contains_secret",
            )
            and int(
                latest_after_target_sample_execution_request_counts.get(
                    "latest_tushare_provider_target_sample_execution_request_found"
                )
                or 0
            )
            == 1
            and int(
                latest_after_target_sample_execution_request_counts.get(
                    "latest_tushare_provider_target_sample_execution_request_row_count"
                )
                or 0
            )
            == len(latest_after_target_sample_execution_request_rows)
            and latest_after_target_sample_execution_request_policy.get(
                "latest_tushare_provider_target_sample_execution_request_lookup_is_local"
            )
            is True
            and latest_after_target_sample_execution_request_policy.get(
                "latest_tushare_provider_target_sample_execution_request_lookup_creates_task"
            )
            is False
            and latest_after_target_sample_execution_request_policy.get(
                "latest_tushare_provider_target_sample_execution_request_lookup_calls_provider"
            )
            is False
            and latest_after_target_sample_execution_request_policy.get(
                "latest_tushare_provider_target_sample_execution_request_is_not_acceptance"
            )
            is True
            and latest_after_target_sample_execution_request_policy.get(
                "latest_tushare_provider_target_sample_execution_request_creates_provider_task"
            )
            is False
            and latest_after_target_sample_execution_request_policy.get(
                "tushare_provider_target_sample_execution_request_requires_bound_scope_hash"
            )
            is True
            and fake_token not in dry_run_serialized
            and "SHOULD_DROP" not in dry_run_serialized
            and "TUSHARE_TOKEN" not in dry_run_serialized,
            "GET Data Health cache may replay the latest local Tushare target-sample execution request metadata, but it must not create a task, call providers, leak credentials, or claim provider-backed LTG-02 acceptance.",
        ),
        _row(
            "trade_cal_execution_request_blocks_scope_mismatch",
            execution_request_mismatch.get("current_step")
            == "trade_cal_execution_request_blocked_scope_hash_mismatch_no_provider_call"
            and execution_request_mismatch_receipt.get("status")
            == "trade_cal_provider_acceptance_execution_request_blocked_scope_hash_mismatch"
            and execution_request_mismatch_receipt.get("allowed_next_step")
            == "rerun_execution_request_with_latest_dry_run_scope_hash"
            and execution_request_mismatch_receipt.get("scope_hash_matches_latest_dry_run") is False
            and execution_request_mismatch_receipt.get("creates_provider_task") is False
            and execution_request_mismatch_receipt.get("provider_execution_implemented") is False
            and execution_request_mismatch_receipt.get("production_freshness_gate_complete") is False
            and _flag_false(
                execution_request_mismatch,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and fake_token not in dry_run_serialized
            and "SHOULD_DROP" not in dry_run_serialized
            and "TUSHARE_TOKEN" not in dry_run_serialized,
            "Execution request must reject a stale or mismatched dry-run scope hash and still avoid provider/model/GitHub calls or secret leakage.",
        ),
        _row(
            "trade_cal_dry_run_blocks_missing_approval",
            dry_missing_approval.get("current_step")
            == "trade_cal_acceptance_dry_run_blocked_user_approval_required_no_provider_call"
            and dry_missing_approval_receipt.get("status")
            == "trade_cal_acceptance_dry_run_blocked_user_approval_required"
            and dry_missing_approval_receipt.get("allowed_next_step") == "rerun_dry_run_with_explicit_user_approval"
            and dry_missing_approval_receipt.get("provider_execution_implemented") is False
            and _flag_false(
                dry_missing_approval,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            ),
            "Missing explicit approval must block the dry-run from being ready for any later real provider task.",
        ),
        _row(
            "trade_cal_dry_run_blocks_short_window",
            dry_short_window.get("current_step")
            == "trade_cal_acceptance_dry_run_blocked_window_too_short_no_provider_call"
            and dry_short_window_receipt.get("status") == "trade_cal_acceptance_dry_run_blocked_window_too_short"
            and dry_short_window_receipt.get("allowed_next_step") == "rerun_dry_run_with_730_day_window"
            and dry_short_window_receipt.get("minimum_acceptance_window_days") == 730
            and dry_short_window_receipt.get("provider_execution_implemented") is False
            and _flag_false(
                dry_short_window,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            ),
            "A too-short window must remain a local blocker and must not trigger provider execution.",
        ),
        _row(
            "trade_cal_dry_run_blocks_missing_credentials_without_leakage",
            dry_missing_credentials.get("current_step")
            == "trade_cal_acceptance_dry_run_blocked_missing_credentials_no_provider_call"
            and dry_missing_credentials_receipt.get("status")
            == "trade_cal_acceptance_dry_run_blocked_missing_credentials"
            and dry_missing_credentials_receipt.get("allowed_next_step") == "configure_server_credentials_then_rerun_dry_run"
            and _as_dict(dry_missing_credentials_receipt.get("credential_presence_summary")).get("status")
            == "required_env_key_missing_no_values_read"
            and dry_missing_credentials_receipt.get("provider_execution_implemented") is False
            and _flag_false(
                dry_missing_credentials,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and fake_token not in dry_run_serialized
            and "SHOULD_DROP" not in dry_run_serialized
            and "TUSHARE_TOKEN" not in dry_run_serialized,
            "Credential presence may be checked as a boolean, but token values, submitted secret-like payloads, and raw env key names must not appear in dry-run output.",
        ),
        _row(
            "current_evidence_boundary_contract",
            current.get("schema_version") == "data_health_current_evidence_freshness_qa.v1"
            and current.get("current_evidence_requires_expected_trade_date") is True
            and current.get("provider_backed_long_window_acceptance_done") is False
            and current.get("blocks_composite_score") is True
            and current.get("blocks_support_factors") is True
            and current.get("blocks_evidence_preview") is True
            and current.get("blocks_next_session_bridge_preview") is True,
            "Current evidence QA must keep expected-date and research-only boundaries visible.",
        ),
        _row(
            "decision_surface_audit_is_read_only",
            surfaces.get("schema_version") == "data_health_current_evidence_decision_surface_audit.v1"
            and surfaces.get("does_not_rescore") is True
            and surfaces.get("does_not_filter_packet") is True
            and surfaces.get("does_not_mutate_decision_surfaces") is True
            and surfaces.get("provider_backed_long_window_acceptance_done") is False,
            "Decision-surface audit must stay read-only and cannot prove provider-backed freshness.",
        ),
        _row(
            "producer_coverage_audit_is_read_only",
            producers.get("schema_version") == "data_health_current_evidence_producer_coverage.v1"
            and producers.get("does_not_build_missing_packets") is True
            and producers.get("not_observed_is_not_production_proof") is True
            and producers.get("provider_backed_long_window_acceptance_done") is False,
            "Producer coverage audit checks visible fields only; not_observed cannot be production proof.",
        ),
        _row(
            "producer_generation_contract_is_local_refresh_pending",
            producer_generation.get("schema_version")
            == "data_health_current_evidence_producer_generation_contract.v1"
            and producer_generation.get("scope")
            == "local_home_snapshot_builder_contract_no_provider_execution"
            and producer_generation.get("status")
            == "producer_generation_contract_ready_current_cache_refresh_pending"
            and producer_generation.get("local_generation_contract_ready") is True
            and producer_generation.get("current_cache_refresh_pending") is True
            and producer_generation.get("writes_snapshot_cache") is False
            and producer_generation.get("builds_missing_packets_in_current_cache") is False
            and producer_generation.get("does_not_refresh_provider") is True
            and producer_generation.get("does_not_use_generated_at_as_data_date") is True
            and producer_generation.get("provider_backed_long_window_acceptance_done") is False
            and producer_generation.get("production_freshness_gate_complete") is False
            and _flag_false(
                producer_generation,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and len(producer_generation_rows) == 3
            and all(row.get("status") == "passed_generation_contract" for row in producer_generation_rows)
            and all(row.get("writes_snapshot_cache") is False for row in producer_generation_rows)
            and all(row.get("local_generation_contract") is True for row in producer_generation_rows)
            and all(row.get("does_not_use_generated_at_as_data_date") is True for row in producer_generation_rows)
            and all(row.get("external_calls_triggered") is False for row in producer_generation_rows)
            and all(row.get("tushare_called") is False for row in producer_generation_rows)
            and all(row.get("deepseek_called") is False for row in producer_generation_rows)
            and all(row.get("github_called") is False for row in producer_generation_rows)
            and policy.get("current_evidence_producer_generation_contract_is_local") is True
            and policy.get("current_evidence_producer_generation_contract_writes_snapshot_cache") is False
            and policy.get("current_evidence_producer_generation_contract_calls_provider") is False
            and policy.get("current_evidence_producer_generation_is_not_provider_acceptance") is True,
            "Producer generation contract may prove the local home snapshot builder can attach expected-date fields to market/radar/evidence packets, but current cache refresh and provider acceptance must remain pending.",
        ),
        _row(
            "freshness_production_stage_scope_manifest_is_complete_and_pending",
            production_stage_scope_ready,
            "Freshness production stages are listed as pending direct evidence while provider trade_cal acceptance, provider replay/failure evidence, producer coverage completion, decision-surface mutation, cache/render external calls, trades, action mutation, and secrets stay disabled.",
        ),
        _row(
            "policy_flags_remain_conservative",
            policy.get("freshness_acceptance_matrix_is_local_contract") is True
            and policy.get("freshness_acceptance_matrix_calls_trade_cal") is False
            and policy.get("freshness_long_window_sample_calls_trade_cal") is False
            and policy.get("trade_cal_physical_validation_calls_trade_cal_provider") is False
            and policy.get("real_trade_cal_long_window_validation_done") is False
            and policy.get("provider_backed_trade_cal_acceptance_still_pending") is True
            and policy.get("latest_trade_cal_provider_acceptance_execution_request_lookup_is_local") is True
            and policy.get("latest_trade_cal_provider_acceptance_execution_request_lookup_calls_provider") is False
            and policy.get("latest_trade_cal_provider_acceptance_execution_request_creates_provider_task") is False,
            "Policy flags must keep local contracts separate from provider-backed production acceptance.",
        ),
        _row(
            "contract_rows_are_present",
            all(key in packet for key in CONTRACT_KEYS)
            and int(counts.get("freshness_acceptance_scenario_count") or 0) >= 8
            and int(counts.get("trade_cal_provider_acceptance_promotion_row_count") or 0) >= 10
            and int(counts.get("freshness_production_blocker_row_count") or 0) >= 8
            and int(counts.get("freshness_provider_acceptance_readiness_row_count") or 0) >= 7
            and int(counts.get("freshness_provider_acceptance_activation_row_count") or 0) >= 11
            and int(counts.get("latest_trade_cal_provider_acceptance_dry_run_found") or 0) >= 0
            and int(counts.get("trade_cal_provider_acceptance_next_execution_row_count") or 0) >= 10
            and int(counts.get("latest_trade_cal_provider_acceptance_execution_request_found") or 0) >= 0
            and int(counts.get("current_evidence_freshness_qa_row_count") or 0) >= 8
            and int(counts.get("current_evidence_decision_surface_row_count") or 0) >= 5
            and int(counts.get("current_evidence_producer_coverage_row_count") or 0) >= 6
            and int(counts.get("current_evidence_producer_generation_row_count") or 0) == 3,
            "Push gate expects all LTG-01 Data Health contracts and row groups to be present.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "data_health_freshness_push_gate_contract.v1",
        "status": "data_health_freshness_contract_passed" if not blockers else "data_health_freshness_contract_blocked",
        "scope": "local_cache_contract_no_provider_execution",
        "ltg": "LTG-01/LTG-11",
        "contract_ready": not blockers,
        "provider_backed_trade_cal_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "freshness_production_stage_scope_count": len(production_stage_scope_rows),
        "freshness_durable_evidence_recipe_ready": durable_evidence_recipe.get("local_recipe_ready") is True,
        "freshness_durable_evidence_recipe_status": durable_evidence_recipe.get("status"),
        "freshness_durable_evidence_complete": False,
        "freshness_durable_evidence_blocker_count": durable_evidence_recipe.get(
            "durable_evidence_blocker_count"
        ),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "rows": rows,
        "freshness_production_stage_scope_rows": production_stage_scope_rows,
        "freshness_durable_evidence_rows": durable_evidence_rows,
        "observed_counts": {
            "freshness_acceptance_scenario_count": counts.get("freshness_acceptance_scenario_count"),
            "current_evidence_freshness_qa_row_count": counts.get("current_evidence_freshness_qa_row_count"),
            "current_evidence_decision_surface_row_count": counts.get("current_evidence_decision_surface_row_count"),
            "current_evidence_producer_coverage_row_count": counts.get("current_evidence_producer_coverage_row_count"),
            "current_evidence_producer_generation_row_count": counts.get(
                "current_evidence_producer_generation_row_count"
            ),
            "current_evidence_producer_generation_blocker_count": counts.get(
                "current_evidence_producer_generation_blocker_count"
            ),
            "current_evidence_producer_generation_status": producer_generation.get("status"),
            "current_evidence_producer_generation_current_cache_refresh_pending": producer_generation.get(
                "current_cache_refresh_pending"
            ),
            "trade_cal_provider_acceptance_pending_count": counts.get("trade_cal_provider_acceptance_pending_count"),
            "trade_cal_provider_acceptance_promotion_blocker_count": counts.get(
                "trade_cal_provider_acceptance_promotion_blocker_count"
            ),
            "trade_cal_provider_acceptance_evidence_row_count": counts.get(
                "trade_cal_provider_acceptance_evidence_row_count"
            ),
            "local_tushare_refresh_packet_trade_cal_evidence_row_count": counts.get(
                "local_tushare_refresh_packet_trade_cal_evidence_row_count"
            ),
            "freshness_production_blocker_count": counts.get("freshness_production_blocker_count"),
            "freshness_provider_acceptance_readiness_blocker_count": counts.get(
                "freshness_provider_acceptance_readiness_blocker_count"
            ),
            "freshness_provider_acceptance_activation_blocker_count": counts.get(
                "freshness_provider_acceptance_activation_blocker_count"
            ),
            "trade_cal_dry_run_contract_case_count": 4,
            "latest_trade_cal_dry_run_cache_found_count": latest_after_ready_counts.get(
                "latest_trade_cal_provider_acceptance_dry_run_found"
            ),
            "latest_trade_cal_dry_run_cache_row_count": latest_after_ready_counts.get(
                "latest_trade_cal_provider_acceptance_dry_run_row_count"
            ),
            "trade_cal_provider_acceptance_next_execution_blocker_count": counts.get(
                "trade_cal_provider_acceptance_next_execution_blocker_count"
            ),
            "latest_trade_cal_execution_request_cache_found_count": latest_after_execution_request_counts.get(
                "latest_trade_cal_provider_acceptance_execution_request_found"
            ),
            "latest_trade_cal_execution_request_cache_row_count": latest_after_execution_request_counts.get(
                "latest_trade_cal_provider_acceptance_execution_request_row_count"
            ),
            "latest_trade_cal_execution_request_status": latest_after_execution_request.get(
                "execution_request_status"
            ),
            "latest_trade_cal_execution_request_scope_hash_matches": latest_after_execution_request.get(
                "scope_hash_matches_latest_dry_run"
            ),
            "current_cache_latest_trade_cal_execution_request_status": latest_execution_request.get(
                "execution_request_status"
            ),
            "latest_trade_cal_next_execution_recipe_status": latest_after_ready_recipe.get("status"),
            "latest_trade_cal_next_execution_recipe_ready_for_user_confirmation": latest_after_ready_recipe.get(
                "recipe_ready_for_user_confirmation"
            ),
            "latest_trade_cal_next_execution_recipe_blocker_count": latest_after_ready_counts.get(
                "trade_cal_provider_acceptance_next_execution_blocker_count"
            ),
            "freshness_production_stage_scope_count": len(production_stage_scope_rows),
            "freshness_production_stage_scope_keys": sorted(production_stage_scope_keys),
            "freshness_production_stage_scope_pending_count": sum(
                1
                for row in production_stage_scope_rows
                if row.get("target_status") == "provider_backed_freshness_direct_evidence_required"
                and row.get("production_freshness_gate_complete") is False
            ),
            "freshness_durable_evidence_row_count": len(durable_evidence_rows),
            "freshness_durable_evidence_keys": sorted(durable_evidence_keys),
            "freshness_durable_evidence_blocker_count": durable_evidence_recipe.get(
                "durable_evidence_blocker_count"
            ),
            "freshness_durable_evidence_blocking_keys": durable_evidence_recipe.get("blocking_evidence_keys"),
        },
        "note": "This is a local push-gate contract. Pending/provider-backed blockers are expected until explicit provider acceptance is run later.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-01 Data Health freshness contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"data_health_freshness_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "provider_backed_trade_cal_acceptance_done: false".format(**contract)
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
