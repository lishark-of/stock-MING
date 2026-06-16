#!/usr/bin/env python3
"""Validate the local LTG-09 Tauri desktop production-boundary contract.

This push-gate guard is not a Tauri build, packaged-app launch, or production
desktop acceptance run. It reads the local desktop preflight cache and source
contracts to keep preflight/dev readiness separate from package QA, runtime
validation, signing/notarization, provider calls, and trading paths.
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

from server.services import desktop_service  # noqa: E402


REQUIRED_PACKAGE_BLOCKERS = {
    "backend_startup_strategy",
    "backend_offline_ui_runtime_verified",
    "macos_signing_notarization_ready",
}
REQUIRED_PACKAGED_QA_CRITERIA = {
    "release_artifact_qa",
    "backend_startup_strategy_qa",
    "backend_offline_ux_packaged_qa",
    "config_log_runtime_path_qa",
    "macos_signing_notarization_qa",
    "startup_external_call_boundary",
    "secret_bundle_boundary",
}
REQUIRED_RELEASE_MANIFEST_CRITERIA = {
    "app_identity_manifest_declared",
    "frontend_dist_manifest_declared",
    "local_dev_url_manifest_declared",
    "icon_asset_present",
    "generated_artifacts_gitignored",
    "backend_startup_policy_manifest_declared",
    "config_log_path_manifest_declared",
    "release_artifact_manifest_observed",
    "packaged_runtime_qa_manifest_pending",
    "signing_notarization_manifest_pending",
    "startup_safety_boundary_declared",
}
REQUIRED_PACKAGE_READINESS_RECEIPT_CRITERIA = {
    "local_tauri_contracts_visible",
    "explicit_build_task_boundary",
    "artifact_detection_not_runtime_qa",
    "packaged_runtime_qa_pending",
    "backend_startup_strategy_pending",
    "backend_offline_packaged_ux_pending",
    "config_log_runtime_validation_pending",
    "signing_notarization_pending",
    "startup_external_call_boundary",
    "secret_bundle_boundary",
    "production_completion_evidence_ticket",
}
REQUIRED_TAURI_PRODUCTION_PACKAGE_STAGES = {
    "tauri_dev_runtime_smoke",
    "tauri_build_repeatability",
    "app_bundle_detection",
    "dmg_distribution_detection",
    "backend_startup_strategy_runtime_qa",
    "backend_offline_packaged_ux_qa",
    "config_log_runtime_path_qa",
    "signing_notarization_review",
}
REQUIRED_TAURI_DURABLE_EVIDENCE_KEYS = {
    "preflight_cache_boundary_visible",
    "release_manifest_visible",
    "readiness_receipt_visible",
    "packaged_runtime_qa_matrix_visible",
    "release_artifact_shape_visible",
    "app_bundle_dmg_evidence_required",
    "packaged_app_launch_qa_required",
    "backend_startup_runtime_evidence_required",
    "backend_offline_packaged_ux_required",
    "config_log_runtime_path_evidence_required",
    "signing_notarization_review_required",
    "production_package_promotion_review_required",
    "no_build_runtime_provider_trade_secret_boundary",
}
TAURI_PRODUCTION_PACKAGE_STAGE_LABELS = {
    "tauri_dev_runtime_smoke": "tauri dev runtime smoke",
    "tauri_build_repeatability": "repeatable tauri build",
    "app_bundle_detection": ".app bundle detection and QA",
    "dmg_distribution_detection": "DMG distribution artifact detection",
    "backend_startup_strategy_runtime_qa": "backend startup strategy runtime QA",
    "backend_offline_packaged_ux_qa": "backend-offline packaged UX QA",
    "config_log_runtime_path_qa": "config and log runtime path QA",
    "signing_notarization_review": "macOS signing and notarization review",
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


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _tauri_production_package_stage_scope_rows(
    release_binary_detected: bool,
    app_bundle_detected: bool,
    dmg_distribution_detected: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_key in sorted(REQUIRED_TAURI_PRODUCTION_PACKAGE_STAGES):
        rows.append(
            {
                "stage_key": stage_key,
                "stage_label": TAURI_PRODUCTION_PACKAGE_STAGE_LABELS[stage_key],
                "scope": "tauri_production_package_stage_scope_manifest",
                "current_status": "local_manifest_or_static_qa_only",
                "target_status": "explicit_build_or_packaged_runtime_evidence_required",
                "required_before_production_package": True,
                "release_binary_detected": bool(release_binary_detected),
                "release_binary_is_completion": False,
                "tauri_dev_runtime_smoke_done": False,
                "tauri_build_repeatability_done": False,
                "app_bundle_detected": bool(app_bundle_detected),
                "dmg_distribution_detected": bool(dmg_distribution_detected),
                "backend_startup_runtime_validated": False,
                "backend_offline_packaged_ux_verified": False,
                "config_log_runtime_paths_validated": False,
                "signing_notarization_done": False,
                "production_package_complete": False,
                "tauri_build_executed_by_contract": False,
                "npm_or_cargo_executed_by_contract": False,
                "tauri_runtime_started_by_contract": False,
                "packaged_app_opened_by_contract": False,
                "fastapi_started_by_contract": False,
                "config_values_read_by_contract": False,
                "log_files_written_by_contract": False,
                "provider_model_task_dispatched_by_contract": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
                "contains_secret": False,
                "missing_evidence": [
                    "explicit tauri dev runtime smoke",
                    "repeatable tauri build log",
                    ".app bundle and DMG artifact QA",
                    "backend startup strategy runtime evidence",
                    "packaged backend-offline UX evidence",
                    "config/log runtime path evidence without values",
                    "signing and notarization review",
                    "explicit production package promotion approval",
                ],
            }
        )
    return rows


def build_contract() -> dict[str, Any]:
    packet = desktop_service.read_desktop_shell_preflight_cache()
    runtime = _dict(packet.get("runtime"))
    policy = _dict(packet.get("policy"))
    readiness = _dict(packet.get("production_readiness"))
    runtime_contract = _dict(packet.get("production_runtime_contract"))
    offline_ux = _dict(packet.get("backend_offline_ux_contract"))
    packaged_qa = _dict(packet.get("packaged_runtime_qa_contract"))
    blocker_audit = _dict(packet.get("production_blocker_audit"))
    blocker_rows = [row for row in _list(packet.get("production_blocker_rows")) if isinstance(row, dict)]
    blocker_criteria = {str(row.get("criterion") or "") for row in blocker_rows}
    qa_rows = [row for row in _list(packet.get("packaged_runtime_qa_rows")) if isinstance(row, dict)]
    qa_criteria = {str(row.get("criterion") or "") for row in qa_rows}
    qa_rows_by_criterion = {str(row.get("criterion") or ""): row for row in qa_rows}
    release_manifest = _dict(packet.get("tauri_release_manifest_contract"))
    release_manifest_rows = [row for row in _list(packet.get("tauri_release_manifest_rows")) if isinstance(row, dict)]
    release_manifest_criteria = {str(row.get("criterion") or "") for row in release_manifest_rows}
    readiness_receipt = _dict(packet.get("production_package_readiness_receipt"))
    readiness_receipt_rows = [row for row in _list(packet.get("production_package_readiness_receipt_rows")) if isinstance(row, dict)]
    readiness_receipt_criteria = {str(row.get("criterion") or "") for row in readiness_receipt_rows}
    durable_recipe = _dict(packet.get("tauri_package_durable_evidence_recipe"))
    durable_rows = [row for row in _list(packet.get("tauri_package_durable_evidence_rows")) if isinstance(row, dict)]
    durable_rows_by_key = {str(row.get("evidence_key") or ""): row for row in durable_rows}
    build_artifact = _dict(packet.get("tauri_build_artifact"))
    release_binary_detected = build_artifact.get("binary_exists") is True
    app_bundle_detected = build_artifact.get("packaged_app_bundle_detected") is True
    dmg_distribution_detected = build_artifact.get("distribution_dmg_detected") is True
    release_binary_state_valid = (
        (
            release_binary_detected
            and int(build_artifact.get("binary_size_bytes") or 0) > 0
            and build_artifact.get("binary_executable") is True
            and build_artifact.get("binary_kind") == "macos_mach_o_release_binary"
            and packaged_qa.get("release_binary_qa_passed") is True
            and packaged_qa.get("release_binary_executable") is True
            and qa_rows_by_criterion.get("release_artifact_qa", {}).get("status") == "passed_local_binary_artifact"
            and qa_rows_by_criterion.get("release_artifact_qa", {}).get("passed") is True
        )
        or (
            not release_binary_detected
            and int(build_artifact.get("binary_size_bytes") or 0) == 0
            and build_artifact.get("binary_executable") is False
            and build_artifact.get("binary_kind") == "missing"
            and packaged_qa.get("release_binary_qa_passed") is False
            and packaged_qa.get("release_binary_executable") is False
            and qa_rows_by_criterion.get("release_artifact_qa", {}).get("status") == "pending"
            and qa_rows_by_criterion.get("release_artifact_qa", {}).get("passed") is False
        )
    )
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    preflight_script = _read_script("scripts/check_tauri_env.sh")
    route_source = _read_script("desktop/src/routes/DesktopShellPreflight.tsx")
    api_client_source = _read_script("desktop/src/api/client.ts")
    this_script = _read_script("scripts/tauri_desktop_contract.py")
    production_package_stage_scope_rows = _tauri_production_package_stage_scope_rows(
        release_binary_detected,
        app_bundle_detected,
        dmg_distribution_detected,
    )

    frontend_secret_boundary = (
        "getDesktopPreflightCache" in route_source
        and "DesktopShellPreflight" in route_source
        and "does_not_read_config_values" in route_source
        and "does_not_write_log_files" in route_source
        and "API_BASE_DISPLAY_URL" in api_client_source
        and "safeApiBaseDisplay" in api_client_source
        and 'parsed.search = ""' in api_client_source
        and 'parsed.hash = ""' in api_client_source
        and "parsed.username" in api_client_source
        and "parsed.password" in api_client_source
        and "localStorage" not in route_source
        and "sessionStorage" not in route_source
    )
    rows = [
        _row(
            "preflight_cache_is_read_only",
            packet.get("schema_version") == "desktop_shell_preflight_cache.v1"
            and packet.get("mode") == "cache_only"
            and packet.get("cache_only") is True
            and packet.get("read_only") is True
            and policy.get("cache_api_external_calls") is False
            and policy.get("does_not_run_npm_build") is True
            and policy.get("does_not_run_tauri") is True
            and policy.get("does_not_run_cargo") is True
            and _flag_false(packet, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and packet.get("does_not_execute_trades") is True
            and packet.get("does_not_modify_strategy_action") is True,
            "GET desktop preflight must remain read-only and must not run npm, cargo, Tauri, providers, models, GitHub, or trades.",
        ),
        _row(
            "production_runtime_contract_is_policy_only",
            runtime_contract.get("schema_version") == "tauri_production_runtime_contract.v1"
            and runtime_contract.get("status") == "runtime_contract_ready_packaged_validation_pending"
            and runtime_contract.get("scope") == "path_policy_and_startup_contract_not_packaged_runtime_validation"
            and runtime_contract.get("manual_backend_launch_required") is True
            and runtime_contract.get("backend_sidecar_autostart_enabled") is False
            and runtime_contract.get("config_paths_declared") is True
            and runtime_contract.get("log_paths_declared") is True
            and runtime_contract.get("reads_config_values") is False
            and runtime_contract.get("writes_log_files") is False
            and runtime_contract.get("packaged_runtime_validated") is False
            and _flag_false(runtime_contract, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and runtime_contract.get("does_not_execute_trades") is True
            and runtime_contract.get("does_not_modify_strategy_action") is True,
            "Runtime contract may declare startup/config/log policy only; package runtime validation remains pending.",
        ),
        _row(
            "backend_offline_ux_is_source_contract_only",
            offline_ux.get("schema_version") == "tauri_backend_offline_ux_contract.v1"
            and offline_ux.get("status") == "frontend_offline_notice_ready_packaged_runtime_validation_pending"
            and offline_ux.get("scope") == "static_frontend_source_contract_not_packaged_runtime_qa"
            and offline_ux.get("frontend_contract_ready") is True
            and offline_ux.get("packaged_runtime_validated") is False
            and offline_ux.get("backend_offline_ui_packaged_runtime_verified") is False
            and _flag_false(offline_ux, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and offline_ux.get("does_not_execute_trades") is True
            and offline_ux.get("does_not_modify_strategy_action") is True,
            "Backend-offline UX is source-audited only; packaged runtime offline behavior is still unproven.",
        ),
        _row(
            "packaged_runtime_qa_stays_pending",
            packaged_qa.get("schema_version") == "tauri_packaged_runtime_qa_contract.v1"
            and packaged_qa.get("status") == "packaged_runtime_qa_contract_ready_validation_pending"
            and packaged_qa.get("scope") == "local_static_qa_matrix_not_packaged_runtime_execution"
            and packaged_qa.get("production_package_ready") is False
            and packaged_qa.get("packaged_runtime_validated") is False
            and packaged_qa.get("qa_contract_ready") is True
            and int(packaged_qa.get("pending_qa_count") or 0) > 0
            and REQUIRED_PACKAGED_QA_CRITERIA.issubset(qa_criteria)
            and release_binary_state_valid
            and packaged_qa.get("packaged_app_bundle_detected") is app_bundle_detected
            and packaged_qa.get("distribution_dmg_detected") is dmg_distribution_detected
            and qa_rows_by_criterion.get("backend_startup_strategy_qa", {}).get("passed") is False
            and qa_rows_by_criterion.get("backend_offline_ux_packaged_qa", {}).get("passed") is False
            and qa_rows_by_criterion.get("config_log_runtime_path_qa", {}).get("passed") is False
            and qa_rows_by_criterion.get("macos_signing_notarization_qa", {}).get("passed") is False
            and packaged_qa.get("browser_or_packaged_app_opened") is False
            and packaged_qa.get("npm_or_cargo_executed") is False
            and packaged_qa.get("config_values_read") is False
            and packaged_qa.get("log_files_written") is False
            and _flag_false(packaged_qa, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and packaged_qa.get("does_not_execute_trades") is True
            and packaged_qa.get("does_not_modify_strategy_action") is True,
            "Packaged runtime QA must remain a static matrix until a future explicit packaged-app run verifies it.",
        ),
        _row(
            "production_blocker_audit_blocks_completion",
            blocker_audit.get("schema_version") == "tauri_production_package_blocker_audit.v1"
            and blocker_audit.get("status") == "production_package_blocked"
            and blocker_audit.get("package_ready") is False
            and blocker_audit.get("tauri_package_build_attempted") is False
            and blocker_audit.get("backend_offline_ui_packaged_runtime_verified") is False
            and blocker_audit.get("macos_signing_notarization_ready") is False
            and int(blocker_audit.get("blocker_count") or 0) > 0
            and REQUIRED_PACKAGE_BLOCKERS.issubset(blocker_criteria)
            and _flag_false(blocker_audit, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and blocker_audit.get("does_not_execute_trades") is True
            and blocker_audit.get("does_not_modify_strategy_action") is True,
            "Production blocker audit must keep sidecar/manual backend, offline UX, package QA, and signing/notarization blockers visible.",
        ),
        _row(
            "release_manifest_contract_is_local_package_manifest_only",
            release_manifest.get("schema_version") == "tauri_release_manifest_contract.v1"
            and release_manifest.get("status") == "release_manifest_contract_ready_packaged_execution_pending"
            and release_manifest.get("scope") == "local_tauri_release_manifest_contract_no_build_or_runtime_execution"
            and release_manifest.get("local_release_manifest_ready") is True
            and release_manifest.get("ready_for_explicit_tauri_build_review") is True
            and release_manifest.get("ready_for_production_package_promotion") is False
            and release_manifest.get("production_package_complete") is False
            and release_manifest.get("product_name") == "stock-MING Command Center"
            and release_manifest.get("app_version") == "3.0.0"
            and release_manifest.get("bundle_identifier") == "com.stockming.commandcenter"
            and release_manifest.get("frontend_dist") == "../dist"
            and release_manifest.get("before_build_command") == "npm run build"
            and release_manifest.get("dev_url_is_localhost") is True
            and release_manifest.get("icon_asset_present") is True
            and release_manifest.get("desktop_dist_gitignored") is True
            and release_manifest.get("tauri_target_gitignored") is True
            and release_manifest.get("manual_backend_launch_required") is True
            and release_manifest.get("backend_sidecar_autostart_enabled") is False
            and release_manifest.get("config_values_read") is False
            and release_manifest.get("log_files_written") is False
            and release_manifest.get("tauri_build_executed") is False
            and release_manifest.get("npm_or_cargo_executed") is False
            and release_manifest.get("tauri_runtime_started") is False
            and release_manifest.get("packaged_app_opened") is False
            and release_manifest.get("fastapi_started") is False
            and release_manifest.get("signing_notarization_done") is False
            and int(release_manifest.get("local_blocker_count") or 0) == 0
            and int(release_manifest.get("production_blocker_count") or 0) > 0
            and REQUIRED_RELEASE_MANIFEST_CRITERIA.issubset(release_manifest_criteria)
            and _flag_false(release_manifest, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and release_manifest.get("does_not_execute_trades") is True
            and release_manifest.get("does_not_modify_strategy_action") is True
            and release_manifest.get("contains_secret") is False
            and _list(release_manifest.get("call_ledger"))
            and _dict(_list(release_manifest.get("call_ledger"))[0]).get("api") == "local_tauri_release_manifest_contract"
            and _dict(_list(release_manifest.get("call_ledger"))[0]).get("external") is False
            and policy.get("tauri_release_manifest_contract_is_local") is True
            and policy.get("tauri_release_manifest_contract_is_not_build") is True
            and policy.get("tauri_release_manifest_contract_is_not_runtime_execution") is True
            and policy.get("tauri_release_manifest_contract_is_not_production_completion") is True,
            "Release manifest may expose app identity, dist, artifact ignore policy, backend startup policy, config/log policy, QA gaps, and signing gaps only; it must not run build/runtime commands or claim production package completion.",
        ),
        _row(
            "production_readiness_receipt_allows_only_explicit_package_qa",
            readiness_receipt.get("schema_version") == "tauri_production_package_readiness_receipt.v1"
            and readiness_receipt.get("status")
            in {
                "tauri_package_readiness_receipt_ready_build_pending",
                "tauri_package_readiness_receipt_ready_packaged_qa_pending",
                "tauri_package_readiness_receipt_ready_for_promotion_review",
            }
            and readiness_receipt.get("scope") == "local_tauri_production_package_readiness_receipt_no_build_or_runtime_execution"
            and readiness_receipt.get("local_receipt_ready") is True
            and readiness_receipt.get("ready_for_explicit_tauri_build") is True
            and readiness_receipt.get("ready_for_production_package_promotion") is False
            and readiness_receipt.get("allowed_next_step") == "explicit_tauri_build_then_packaged_runtime_qa_review"
            and REQUIRED_PACKAGE_READINESS_RECEIPT_CRITERIA.issubset(readiness_receipt_criteria)
            and "GET /api/desktop/preflight-cache npm build" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "GET /api/desktop/preflight-cache cargo build" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "GET /api/desktop/preflight-cache tauri build" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "GET /api/desktop/preflight-cache packaged app launch" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "release artifact detection as packaged runtime QA" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and "preflight receipt as production package completion" in _list(readiness_receipt.get("not_allowed_next_steps"))
            and readiness_receipt.get("production_package_complete") is False
            and readiness_receipt.get("tauri_build_executed_by_receipt") is False
            and readiness_receipt.get("npm_or_cargo_executed_by_receipt") is False
            and readiness_receipt.get("tauri_runtime_started_by_receipt") is False
            and readiness_receipt.get("packaged_app_opened_by_receipt") is False
            and readiness_receipt.get("fastapi_started_by_receipt") is False
            and readiness_receipt.get("config_values_read_by_receipt") is False
            and readiness_receipt.get("log_files_written_by_receipt") is False
            and readiness_receipt.get("provider_model_task_dispatched_by_receipt") is False
            and readiness_receipt.get("receipt_external_calls_triggered") is False
            and _flag_false(readiness_receipt, "external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and readiness_receipt.get("does_not_execute_trades") is True
            and readiness_receipt.get("does_not_modify_strategy_action") is True
            and readiness_receipt.get("contains_secret") is False
            and _list(readiness_receipt.get("call_ledger"))
            and _dict(_list(readiness_receipt.get("call_ledger"))[0]).get("api") == "local_tauri_production_package_readiness_receipt"
            and _dict(_list(readiness_receipt.get("call_ledger"))[0]).get("external") is False
            and policy.get("production_package_readiness_receipt_is_local") is True
            and policy.get("production_package_readiness_receipt_is_not_build") is True
            and policy.get("production_package_readiness_receipt_is_not_runtime_execution") is True
            and policy.get("production_package_readiness_receipt_is_not_production_completion") is True,
            "Tauri package readiness receipt may select the next explicit build/package-QA step, but it must not run build/runtime commands, read config, write logs, call providers, or claim production completion.",
        ),
        _row(
            "tauri_package_durable_evidence_recipe_is_local_production_pending",
            durable_recipe.get("schema_version") == desktop_service.TAURI_PACKAGE_DURABLE_EVIDENCE_SCHEMA_VERSION
            and durable_recipe.get("status") == "tauri_package_durable_evidence_recipe_ready_production_pending"
            and durable_recipe.get("scope")
            == "local_tauri_package_durable_evidence_recipe_no_build_or_runtime_execution"
            and durable_recipe.get("local_recipe_ready") is True
            and durable_recipe.get("durable_evidence_complete") is False
            and durable_recipe.get("durable_promotion_ready") is False
            and durable_recipe.get("production_package_complete") is False
            and durable_recipe.get("tauri_build_repeatability_done") is False
            and durable_recipe.get("packaged_app_launch_qa_done") is False
            and durable_recipe.get("backend_startup_strategy_runtime_validated") is False
            and durable_recipe.get("backend_offline_packaged_ux_verified") is False
            and durable_recipe.get("config_log_runtime_paths_validated") is False
            and durable_recipe.get("signing_notarization_done") is False
            and durable_recipe.get("provider_execution_implemented") is False
            and durable_recipe.get("model_execution_implemented") is False
            and durable_recipe.get("cache_get_external_calls") is False
            and durable_recipe.get("react_render_external_calls") is False
            and durable_recipe.get("preflight_runs_build") is False
            and durable_recipe.get("preflight_opens_packaged_app") is False
            and durable_recipe.get("preflight_starts_fastapi") is False
            and durable_recipe.get("preflight_reads_config_values") is False
            and durable_recipe.get("preflight_writes_log_files") is False
            and durable_recipe.get("evidence_keys")
            == list(desktop_service.TAURI_PACKAGE_DURABLE_EVIDENCE_KEYS)
            and {row.get("evidence_key") for row in durable_rows} == REQUIRED_TAURI_DURABLE_EVIDENCE_KEYS
            and int(durable_recipe.get("row_count") or 0) == len(durable_rows)
            and int(durable_recipe.get("evidence_key_count") or 0)
            == len(desktop_service.TAURI_PACKAGE_DURABLE_EVIDENCE_KEYS)
            and int(durable_recipe.get("durable_evidence_blocker_count") or 0) >= 6
            and ".app bundle and DMG artifact QA or explicit accepted equivalent"
            in _list(durable_recipe.get("required_evidence"))
            and "packaged app launch QA" in _list(durable_recipe.get("required_evidence"))
            and "config/log runtime path evidence without secret values"
            in _list(durable_recipe.get("required_evidence"))
            and "treat release binary detection as packaged app launch QA"
            in _list(durable_recipe.get("not_allowed_next_steps"))
            and "run npm, cargo, or Tauri from GET preflight" in _list(durable_recipe.get("not_allowed_next_steps"))
            and "call Tushare, DeepSeek, or GitHub from GET preflight or React render"
            in _list(durable_recipe.get("not_allowed_next_steps"))
            and durable_rows_by_key.get("preflight_cache_boundary_visible", {}).get("passed") is True
            and durable_rows_by_key.get("release_manifest_visible", {}).get("passed") is True
            and durable_rows_by_key.get("readiness_receipt_visible", {}).get("passed") is True
            and durable_rows_by_key.get("packaged_runtime_qa_matrix_visible", {}).get("passed") is True
            and durable_rows_by_key.get("release_artifact_shape_visible", {}).get("passed") is True
            and durable_rows_by_key.get("packaged_app_launch_qa_required", {}).get("production_blocker") is True
            and durable_rows_by_key.get("backend_offline_packaged_ux_required", {}).get("production_blocker") is True
            and durable_rows_by_key.get("no_build_runtime_provider_trade_secret_boundary", {}).get("passed") is True
            and _flag_false(
                durable_recipe,
                "external_calls_triggered",
                "tushare_called",
                "deepseek_called",
                "github_called",
                "contains_secret",
            )
            and durable_recipe.get("does_not_execute_trades") is True
            and durable_recipe.get("does_not_modify_strategy_action") is True
            and _list(durable_recipe.get("call_ledger"))
            and _dict(_list(durable_recipe.get("call_ledger"))[0]).get("api")
            == "local_tauri_package_durable_evidence_recipe"
            and _dict(_list(durable_recipe.get("call_ledger"))[0]).get("external") is False
            and policy.get("tauri_package_durable_evidence_recipe_is_local") is True
            and policy.get("tauri_package_durable_evidence_recipe_is_not_build") is True
            and policy.get("tauri_package_durable_evidence_recipe_is_not_runtime_execution") is True
            and policy.get("tauri_package_durable_evidence_recipe_is_not_production_completion") is True
            and "tauri_package_durable_evidence_recipe" in route_source,
            "Tauri durable evidence recipe must pin remaining package/runtime/config/signing evidence without running build/runtime commands, opening apps, reading config, writing logs, calling providers, trading, or claiming production package completion.",
        ),
        _row(
            "production_package_stage_scope_manifest_is_complete_and_pending",
            {row.get("stage_key") for row in production_package_stage_scope_rows}
            == REQUIRED_TAURI_PRODUCTION_PACKAGE_STAGES
            and len(production_package_stage_scope_rows) == len(REQUIRED_TAURI_PRODUCTION_PACKAGE_STAGES)
            and all(
                row.get("scope") == "tauri_production_package_stage_scope_manifest"
                for row in production_package_stage_scope_rows
            )
            and all(row.get("required_before_production_package") is True for row in production_package_stage_scope_rows)
            and all(row.get("current_status") == "local_manifest_or_static_qa_only" for row in production_package_stage_scope_rows)
            and all(
                row.get("target_status") == "explicit_build_or_packaged_runtime_evidence_required"
                for row in production_package_stage_scope_rows
            )
            and all(row.get("release_binary_is_completion") is False for row in production_package_stage_scope_rows)
            and all(row.get("tauri_dev_runtime_smoke_done") is False for row in production_package_stage_scope_rows)
            and all(row.get("tauri_build_repeatability_done") is False for row in production_package_stage_scope_rows)
            and all(row.get("app_bundle_detected") is app_bundle_detected for row in production_package_stage_scope_rows)
            and all(
                row.get("dmg_distribution_detected") is dmg_distribution_detected
                for row in production_package_stage_scope_rows
            )
            and all(row.get("backend_startup_runtime_validated") is False for row in production_package_stage_scope_rows)
            and all(row.get("backend_offline_packaged_ux_verified") is False for row in production_package_stage_scope_rows)
            and all(row.get("config_log_runtime_paths_validated") is False for row in production_package_stage_scope_rows)
            and all(row.get("signing_notarization_done") is False for row in production_package_stage_scope_rows)
            and all(row.get("production_package_complete") is False for row in production_package_stage_scope_rows)
            and all(row.get("tauri_build_executed_by_contract") is False for row in production_package_stage_scope_rows)
            and all(row.get("npm_or_cargo_executed_by_contract") is False for row in production_package_stage_scope_rows)
            and all(row.get("tauri_runtime_started_by_contract") is False for row in production_package_stage_scope_rows)
            and all(row.get("packaged_app_opened_by_contract") is False for row in production_package_stage_scope_rows)
            and all(row.get("fastapi_started_by_contract") is False for row in production_package_stage_scope_rows)
            and all(row.get("config_values_read_by_contract") is False for row in production_package_stage_scope_rows)
            and all(row.get("log_files_written_by_contract") is False for row in production_package_stage_scope_rows)
            and all(row.get("provider_model_task_dispatched_by_contract") is False for row in production_package_stage_scope_rows)
            and all(row.get("external_calls_triggered") is False for row in production_package_stage_scope_rows)
            and all(row.get("tushare_called") is False for row in production_package_stage_scope_rows)
            and all(row.get("deepseek_called") is False for row in production_package_stage_scope_rows)
            and all(row.get("github_called") is False for row in production_package_stage_scope_rows)
            and all(row.get("does_not_execute_trades") is True for row in production_package_stage_scope_rows)
            and all(row.get("does_not_modify_strategy_action") is True for row in production_package_stage_scope_rows)
            and all(row.get("contains_secret") is False for row in production_package_stage_scope_rows),
            "Tauri production package stage rows must enumerate every runtime/package/signing evidence stage without running build commands, opening the app, reading config values, writing logs, calling providers, executing trades, or claiming production completion.",
        ),
        _row(
            "tauri_task_policy_does_not_run_build_or_runtime",
            "tauri_dev_command=cd desktop && npm run tauri dev" in preflight_script
            and "tauri_build_command=cd desktop && npm run tauri build" in preflight_script
            and "production_package_build_attempted=false" in preflight_script
            and "tauri_package_build_required_for_production=true" in preflight_script
            and runtime.get("tauri_build_attempted") is False
            and runtime.get("vite_build_attempted") is False
            and runtime.get("fastapi_dev_server_started") is False
            and runtime.get("production_package_build_attempted") is False
            and policy.get("does_not_start_fastapi") is True
            and policy.get("backend_autostart_enabled") is False,
            "Tauri preflight may display manual commands, but cache GET and push-gate contracts must not run build/dev/runtime commands.",
        ),
        _row(
            "frontend_does_not_expose_secrets",
            frontend_secret_boundary
            and runtime_contract.get("frontend_stores_tokens") is False
            and runtime_contract.get("token_key_frontend_exposure") is False
            and blocker_audit.get("frontend_stores_tokens") is False
            and blocker_audit.get("contains_secret") is False
            and release_binary_state_valid
            and build_artifact.get("packaged_app_bundle_detected") is app_bundle_detected
            and build_artifact.get("distribution_dmg_detected") is dmg_distribution_detected
            and build_artifact.get("build_command_executed_by_get_cache") is False
            and build_artifact.get("contains_secret") is False
            and policy.get("contains_secret") is False,
            "Desktop frontend must display sanitized local API base and must not store token/key material.",
        ),
        _row(
            "push_gate_runs_tauri_contract_after_worker",
            "scripts/tauri_desktop_contract.py" in push_gate_script
            and "Tauri desktop contract" in push_gate_script
            and "tauri_desktop_contract: passed_local_contract_package_validation_pending" in push_gate_script
            and push_gate_script.find('run_step "Worker contract"') < push_gate_script.find('run_step "Tauri desktop contract"')
            and push_gate_script.find('run_step "Tauri desktop contract"') < push_gate_script.find('run_step "Motion viewport QA contract"'),
            "Push gate must run LTG-09 Tauri desktop contract after Worker and before motion/static QA.",
        ),
        _row(
            "script_is_local_no_build_or_provider_execution",
            "command_center_3_tauri_desktop_contract.v1" in this_script
            and "local_tauri_desktop_contract_no_build_or_runtime_execution" in this_script
            and "release_manifest_contract_is_local_package_manifest_only" in this_script
            and "tauri_package_durable_evidence_recipe.v1" in this_script
            and "tauri_production_package_stage_scope_manifest" in this_script
            and "production_package_complete" in this_script
            and "packaged_runtime_qa_done" in this_script
            and "tauri_build_executed" in this_script
            and "does_not_run_tauri" in this_script
            and "does_not_execute_trades" in this_script
            and ("sub" + "process") not in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script
            and ("deepseek" + "_adapter") not in this_script,
            "The Tauri contract must stay local and must not import network/provider clients or run shell/build/runtime commands.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_tauri_desktop_contract.v1",
        "status": "tauri_desktop_contract_passed" if not blockers else "tauri_desktop_contract_blocked",
        "scope": "local_tauri_desktop_contract_no_build_or_runtime_execution",
        "ltg": "LTG-09/LTG-11",
        "contract_ready": not blockers,
        "preflight_cache_ready": packet.get("schema_version") == "desktop_shell_preflight_cache.v1"
        and packet.get("cache_only") is True,
        "runtime_contract_visible": runtime_contract.get("schema_version") == "tauri_production_runtime_contract.v1",
        "backend_offline_ux_contract_visible": offline_ux.get("schema_version") == "tauri_backend_offline_ux_contract.v1",
        "packaged_runtime_qa_visible": packaged_qa.get("schema_version") == "tauri_packaged_runtime_qa_contract.v1",
        "release_manifest_visible": release_manifest.get("schema_version") == "tauri_release_manifest_contract.v1",
        "production_package_complete": False,
        "tauri_build_executed": False,
        "packaged_runtime_qa_done": False,
        "signing_notarization_done": False,
        "production_package_readiness_receipt_ready": readiness_receipt.get("local_receipt_ready") is True,
        "production_package_readiness_receipt_status": readiness_receipt.get("status"),
        "tauri_release_manifest_ready": release_manifest.get("local_release_manifest_ready") is True,
        "tauri_release_manifest_status": release_manifest.get("status"),
        "tauri_package_durable_evidence_recipe_ready": durable_recipe.get("local_recipe_ready") is True,
        "tauri_package_durable_evidence_recipe_status": durable_recipe.get("status"),
        "tauri_package_durable_evidence_complete": False,
        "tauri_package_durable_evidence_blocker_count": durable_recipe.get("durable_evidence_blocker_count", 0),
        "cache_only": True,
        "does_not_run_tauri": True,
        "does_not_run_npm": True,
        "does_not_run_cargo": True,
        "does_not_read_config_values": True,
        "does_not_write_logs": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "observed": {
            "preflight_status": readiness.get("status"),
            "cache_status": packet.get("status"),
            "production_blocker_status": blocker_audit.get("status"),
            "production_blocker_count": blocker_audit.get("blocker_count"),
            "packaged_runtime_qa_status": packaged_qa.get("status"),
            "packaged_runtime_pending_qa_count": packaged_qa.get("pending_qa_count"),
            "tauri_release_manifest_status": release_manifest.get("status"),
            "tauri_release_manifest_local_blocker_count": release_manifest.get("local_blocker_count"),
            "tauri_release_manifest_production_blocker_count": release_manifest.get("production_blocker_count"),
            "backend_offline_ux_status": offline_ux.get("status"),
            "production_runtime_status": runtime_contract.get("status"),
            "tauri_build_artifact_status": build_artifact.get("status"),
            "app_bundle_detected": app_bundle_detected,
            "dmg_distribution_detected": dmg_distribution_detected,
            "tauri_package_build_attempted": blocker_audit.get("tauri_package_build_attempted"),
            "backend_offline_ui_packaged_runtime_verified": blocker_audit.get(
                "backend_offline_ui_packaged_runtime_verified"
            ),
            "macos_signing_notarization_ready": blocker_audit.get("macos_signing_notarization_ready"),
            "production_package_readiness_receipt_status": readiness_receipt.get("status"),
            "production_package_readiness_receipt_blocker_count": readiness_receipt.get("blocking_criterion_count"),
            "production_package_readiness_allowed_next_step": readiness_receipt.get("allowed_next_step"),
            "tauri_package_durable_evidence_recipe_status": durable_recipe.get("status"),
            "tauri_package_durable_evidence_ready": durable_recipe.get("local_recipe_ready"),
            "tauri_package_durable_evidence_blocker_count": durable_recipe.get("durable_evidence_blocker_count"),
            "tauri_package_durable_evidence_missing": durable_recipe.get("missing_durable_evidence"),
            "api_base_is_localhost": _dict(packet.get("api_base_info")).get("is_localhost"),
            "production_package_stage_scope_count": len(production_package_stage_scope_rows),
            "production_package_stage_scope_keys": sorted(
                row.get("stage_key") for row in production_package_stage_scope_rows
            ),
            "production_package_stage_scope_pending_count": sum(
                1 for row in production_package_stage_scope_rows if row.get("production_package_complete") is False
            ),
        },
        "tauri_package_durable_evidence_rows": durable_rows,
        "production_package_stage_scope_rows": production_package_stage_scope_rows,
        "rows": rows,
        "note": "This is a local push-gate contract. Tauri dev/build execution, packaged runtime launch QA, backend sidecar/manual startup acceptance, config/log runtime behavior, signing/notarization, and production desktop package completion remain pending.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-09 Tauri desktop contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"tauri_desktop_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "production_package_complete: false; tauri_build_executed: false; packaged_runtime_qa_done: false".format(
                **contract
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
