#!/usr/bin/env python3
"""Validate the local Tushare / DeepSeek linkage contract.

This push-gate guard does not call Tushare, DeepSeek, GitHub, or any broker.
It verifies the mode-layered linkage between live_light bootstrap and
search-to-quant projection so local dry-runs cannot be mistaken for real
provider/model execution or production acceptance.
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

from server.services import bootstrap_service, candidate_service, migration_status_service, task_service  # noqa: E402


ENV_KEYS = (
    "COMMAND_CENTER_BOOTSTRAP_MODE",
    "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
    "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
    "COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE",
    "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
    "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
    "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL",
    "COMMAND_CENTER_LIVE_ALLOW_FULL_POOL",
    "TUSHARE_TOKEN",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_TOKEN_1",
    "DEEPSEEK_TOKEN_2",
)


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


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key in ENV_KEYS:
        if snapshot.get(key) is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(snapshot[key])


def _set_env(**values: str) -> None:
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    for key, value in values.items():
        os.environ[key] = value


def _candidate_quant_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    snapshot = {
        "radar_packet": {"status": "ready", "summary": "local linkage contract"},
        "data_freshness": {"state": "fresh", "expected_trade_date": "2026-06-12"},
    }
    quant_snapshot, _, _ = candidate_service._snapshot_with_quant_projection(
        snapshot,
        {"symbol": "002008", "include_tushare": True, "include_deepseek": True},
    )
    packet = candidate_service._build_candidate_radar_packet(
        quant_snapshot,
        mode=candidate_service.QUANT_PROJECTION_SCAN_MODE,
        cache_source="local_linkage_contract",
        scan_mode=candidate_service.QUANT_PROJECTION_SCAN_MODE,
        request_params_safe={
            "scan_mode": candidate_service.QUANT_PROJECTION_SCAN_MODE,
            "symbol": "002008.SZ",
            "external_sources_allowed": False,
        },
    )
    dry_run, dry_rows, credential_rows = candidate_service._build_quant_projection_acceptance_dry_run(
        quant_receipt=_dict(packet.get("search_quant_projection_receipt")),
        activation_receipt=_dict(packet.get("search_quant_projection_activation_receipt")),
        payload_safe={
            "symbol": "002008",
            "include_tushare": True,
            "include_deepseek": True,
            "user_approved": True,
            "selected_apis": ["trade_cal", "daily", "daily_basic", "moneyflow", "top_inst"],
        },
    )
    packet["search_quant_projection_acceptance_dry_run_receipt"] = dry_run
    packet["search_quant_projection_acceptance_dry_run_rows"] = dry_rows
    packet["search_quant_projection_credential_presence_rows"] = credential_rows
    return packet, dry_run, credential_rows


def build_contract() -> dict[str, Any]:
    original_env = {key: os.environ.get(key) for key in ENV_KEYS}
    original_meta_path = task_service.SQLITE_META_PATH
    rows: list[dict[str, Any]] = []
    try:
        with tempfile.TemporaryDirectory(prefix="stock_ming_linkage_contract_") as temp_dir:
            task_service.SQLITE_META_PATH = Path(temp_dir) / "meta.sqlite"

            _set_env(COMMAND_CENTER_BOOTSTRAP_MODE="cache_only")
            cache_status = bootstrap_service.read_bootstrap_status_cache()
            cache_policy = _dict(cache_status.get("policy"))
            cache_linkage = {
                str(row.get("linkage_key") or ""): row
                for row in _list(cache_status.get("provider_linkage_rows"))
                if isinstance(row, dict)
            }
            rows.append(
                _row(
                    "cache_only_render_and_get_are_provider_model_silent",
                    cache_status.get("mode") == "cache_only"
                    and cache_policy.get("cache_api_external_calls") is False
                    and cache_policy.get("react_initial_render_external_calls") is False
                    and cache_linkage.get("cache_startup_render_boundary", {}).get("status") == "offline_enforced"
                    and cache_status.get("tushare_called") is False
                    and cache_status.get("deepseek_called") is False
                    and cache_status.get("github_called") is False,
                    "cache_only keeps GET cache, FastAPI startup, and initial React render offline.",
                )
            )

            _set_env(
                COMMAND_CENTER_BOOTSTRAP_MODE="live_light",
                COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="true",
                COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="true",
                COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="light_provider_model",
                COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT="2",
                COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS="600",
                COMMAND_CENTER_LIVE_DEEPSEEK_MODEL="contract-linkage-pro",
                COMMAND_CENTER_LIVE_ALLOW_FULL_POOL="false",
                TUSHARE_TOKEN="TS_OK",
                DEEPSEEK_API_KEY="DS_OK",
            )
            task_service.clear_task_statuses_for_tests(clear_persisted=True)
            live_status = bootstrap_service.read_bootstrap_status_cache()
            live_task = bootstrap_service.run_live_startup_task(
                {
                    "source": "tushare_deepseek_linkage_contract",
                    "symbols": ["002008.SZ", "000001.SZ", "600519.SH"],
                    "tushare": True,
                    "deepseek": True,
                    "token": "SHOULD_DROP",
                }
            )
            live_payload = _dict(live_task.get("payload_safe"))
            live_summary = _dict(live_payload.get("bootstrap_plan_summary"))
            live_text = _json(live_task)
            live_linkage = {
                str(row.get("linkage_key") or ""): row
                for row in _list(live_status.get("provider_linkage_rows"))
                if isinstance(row, dict)
            }
            live_runbook = _dict(live_status.get("live_light_provider_model_acceptance_runbook"))
            live_activation = _dict(live_status.get("live_light_activation_receipt"))
            live_model_rows = _list(live_payload.get("bootstrap_model_ledger_preview_rows"))
            live_model = _dict(live_model_rows[0] if live_model_rows else {})
            rows.append(
                _row(
                    "live_light_plans_tushare_deepseek_without_calling",
                    live_task.get("current_step") == "live_bootstrap_plan_recorded_no_provider_execution"
                    and live_payload.get("symbols") == ["002008.SZ", "000001.SZ"]
                    and live_payload.get("truncated_by_symbol_limit") is True
                    and live_summary.get("planned_provider_stage_count") == 2
                    and live_summary.get("planned_model_stage_count") == 1
                    and live_summary.get("actual_provider_execution_count") == 0
                    and live_summary.get("actual_model_call_count") == 0
                    and live_summary.get("external_calls_triggered") is False
                    and live_task.get("tushare_called") is False
                    and live_task.get("deepseek_called") is False
                    and "SHOULD_DROP" not in live_text
                    and "TS_OK" not in live_text
                    and "DS_OK" not in live_text,
                    "live_light may create a bounded POST task plan, but provider/model execution stays false.",
                )
            )
            rows.append(
                _row(
                    "live_light_linkage_rows_require_ledgers_and_keep_production_pending",
                    live_linkage.get("tushare_light_refresh", {}).get("status")
                    == "planned_provider_pending_not_executed"
                    and live_linkage.get("tushare_light_refresh", {}).get("call_ledger_required") is True
                    and live_linkage.get("tushare_light_refresh", {}).get("token_key_exposure_allowed") is False
                    and live_linkage.get("deepseek_pro_after_task", {}).get("status")
                    == "planned_model_pending_not_executed"
                    and live_linkage.get("deepseek_pro_after_task", {}).get("model_ledger_required") is True
                    and live_linkage.get("github_probe_boundary", {}).get("live_light_on_open_allowed") is False
                    and live_linkage.get("real_trading_boundary", {}).get("real_trading_connected") is False
                    and live_runbook.get("provider_execution_implemented") is False
                    and live_runbook.get("model_execution_implemented") is False
                    and live_runbook.get("production_live_light_complete") is False
                    and live_activation.get("ready_for_provider_execution") is False
                    and live_activation.get("ready_for_model_execution") is False,
                    "provider/model ledgers are required, GitHub and real trading stay outside live_light startup.",
                )
            )
            rows.append(
                _row(
                    "deepseek_model_preview_is_sanitized_six_field_schema",
                    live_model.get("model") == "contract-linkage-pro"
                    and live_model.get("model_called") is False
                    and live_model.get("deepseek_called") is False
                    and set(_list(live_model.get("allowed_output_fields")))
                    == {
                        "summary",
                        "support_notes",
                        "suppress_notes",
                        "conflict_notes",
                        "missing_data_notes",
                        "discipline_notes",
                    }
                    and {"model_used", "status", "token_usage", "parse_status", "input_hash", "output_hash"}.issubset(
                        set(_list(live_model.get("required_model_ledger_fields")))
                    ),
                    "DeepSeek preview remains a model-ledger contract with the six-field sanitizer schema.",
                )
            )

            bootstrap_dry_run = bootstrap_service.run_provider_model_acceptance_dry_run(
                {
                    "source": "tushare_deepseek_linkage_contract",
                    "approved_by_user": True,
                    "symbols": ["002008.SZ", "000001.SZ", "600519.SH"],
                    "include_tushare": True,
                    "include_deepseek": True,
                    "apis": ["trade_cal", "daily", "daily_basic", "moneyflow", "fina_indicator"],
                    "secret": "SHOULD_DROP",
                }
            )
            dry_payload = _dict(bootstrap_dry_run.get("payload_safe"))
            dry_summary = _dict(dry_payload.get("acceptance_dry_run_summary"))
            dry_ticket = _dict(dry_payload.get("acceptance_scope_ticket"))
            dry_preflight = _dict(dry_payload.get("real_acceptance_preflight_receipt"))
            dry_text = _json(bootstrap_dry_run)
            rows.append(
                _row(
                    "bootstrap_acceptance_dry_run_is_secret_safe_and_not_real_execution",
                    dry_payload.get("selected_apis") == ["trade_cal", "daily", "daily_basic", "moneyflow"]
                    and dry_payload.get("ignored_apis") == ["fina_indicator"]
                    and dry_summary.get("credential_presence_status") == "all_required_env_keys_present_no_values_read"
                    and dry_summary.get("ready_for_user_approved_real_acceptance") is True
                    and dry_summary.get("real_acceptance_task_implemented") is False
                    and dry_preflight.get("ready_to_execute_real_task") is False
                    and dry_preflight.get("provider_execution_implemented") is False
                    and dry_preflight.get("model_execution_implemented") is False
                    and dry_ticket.get("credential_values_included") is False
                    and dry_ticket.get("env_key_names_included") is False
                    and bootstrap_dry_run.get("external_calls_triggered") is False
                    and bootstrap_dry_run.get("tushare_called") is False
                    and bootstrap_dry_run.get("deepseek_called") is False
                    and "SHOULD_DROP" not in dry_text
                    and "TS_OK" not in dry_text
                    and "DS_OK" not in dry_text,
                    "bootstrap acceptance dry-run binds scope and credentials by booleans only, without executing providers/models.",
                )
            )

            packet, candidate_dry_run, credential_rows = _candidate_quant_packet()
            credential_map = {str(row.get("provider") or ""): row for row in credential_rows if isinstance(row, dict)}
            quant_receipt = _dict(packet.get("search_quant_projection_receipt"))
            activation = _dict(packet.get("search_quant_projection_activation_receipt"))
            rows.append(
                _row(
                    "search_quant_projection_local_receipt_requires_tushare_deepseek_evidence",
                    quant_receipt.get("status") == "quant_projection_local_receipt_ready_provider_model_pending"
                    and quant_receipt.get("symbol") == "002008.SZ"
                    and quant_receipt.get("provider_execution_implemented") is False
                    and quant_receipt.get("model_execution_implemented") is False
                    and quant_receipt.get("production_quant_projection_complete") is False
                    and "real Tushare light call ledger" in _list(activation.get("missing_evidence_items"))
                    and "optional DeepSeek pro model ledger" in _list(activation.get("missing_evidence_items"))
                    and "call Tushare or DeepSeek from React render" in _list(activation.get("not_allowed_next_steps"))
                    and packet.get("external_calls_triggered") is False
                    and packet.get("does_not_modify_strategy_action") is True
                    and packet.get("does_not_execute_trades") is True,
                    "search-to-quant projection is a local receipt until real Tushare/model ledgers exist.",
                )
            )
            rows.append(
                _row(
                    "candidate_quant_acceptance_dry_run_limits_apis_and_hides_credentials",
                    candidate_dry_run.get("status")
                    == "quant_projection_acceptance_dry_run_ready_real_execution_still_blocked"
                    and candidate_dry_run.get("selected_apis") == ["trade_cal", "daily", "daily_basic", "moneyflow"]
                    and candidate_dry_run.get("ignored_apis") == ["top_inst"]
                    and candidate_dry_run.get("ready_for_user_approved_real_acceptance") is True
                    and candidate_dry_run.get("ready_to_execute_real_provider_model_task") is False
                    and candidate_dry_run.get("provider_execution_implemented") is False
                    and candidate_dry_run.get("model_execution_implemented") is False
                    and candidate_dry_run.get("production_quant_projection_complete") is False
                    and candidate_dry_run.get("credential_values_read") is False
                    and candidate_dry_run.get("credential_values_exposed") is False
                    and candidate_dry_run.get("env_key_names_included") is False
                    and _dict(candidate_dry_run.get("acceptance_scope_ticket")).get("credential_values_included")
                    is False
                    and _dict(candidate_dry_run.get("acceptance_scope_ticket")).get("env_key_names_included")
                    is False
                    and credential_map.get("tushare", {}).get("status") == "present_no_value_read"
                    and credential_map.get("deepseek", {}).get("status") == "present_no_value_read"
                    and candidate_dry_run.get("tushare_called") is False
                    and candidate_dry_run.get("deepseek_called") is False
                    and candidate_dry_run.get("does_not_modify_strategy_action") is True
                    and candidate_dry_run.get("candidate_is_not_buy_instruction") is True,
                    "candidate quant dry-run is scoped, credential-safe, and still blocked from real execution.",
                )
            )

            linkage_review_task = migration_status_service.run_tushare_deepseek_linkage_review(
                {
                    "approved_by_user": True,
                    "reviewer": "linkage_contract",
                    "token": "SHOULD_DROP",
                }
            )
            linkage_review_payload = _dict(linkage_review_task.get("payload_safe"))
            linkage_review_receipt = _dict(linkage_review_payload.get("tushare_deepseek_linkage_review_receipt"))
            linkage_review_rows = _list(linkage_review_payload.get("tushare_deepseek_linkage_review_rows"))
            linkage_review_text = _json(linkage_review_task)
            migration_status = migration_status_service.build_migration_status()
            latest_linkage_review = _dict(migration_status.get("latest_tushare_deepseek_linkage_review"))
            latest_linkage_review_rows = _list(migration_status.get("latest_tushare_deepseek_linkage_review_rows"))
            rows.append(
                _row(
                    "linkage_review_task_records_pending_evidence_without_calls",
                    linkage_review_task.get("task_type") == "run_tushare_deepseek_linkage_review"
                    and linkage_review_task.get("status") == "success"
                    and linkage_review_receipt.get("status")
                    == "tushare_deepseek_linkage_review_recorded_real_evidence_pending"
                    and linkage_review_receipt.get("user_confirmed") is True
                    and linkage_review_receipt.get("cache_render_silent") is True
                    and linkage_review_receipt.get("post_task_creation_button_gated") is True
                    and linkage_review_receipt.get("provider_execution_implemented") is False
                    and linkage_review_receipt.get("model_execution_implemented") is False
                    and linkage_review_receipt.get("production_live_light_complete") is False
                    and linkage_review_receipt.get("production_quant_projection_complete") is False
                    and linkage_review_receipt.get("blocking_row_count", 0) > 0
                    and "real_tushare_call_ledger" in _list(linkage_review_receipt.get("missing_evidence_items"))
                    and "deepseek_model_ledger_if_enabled"
                    in _list(linkage_review_receipt.get("missing_evidence_items"))
                    and linkage_review_task.get("external_calls_triggered") is False
                    and linkage_review_task.get("tushare_called") is False
                    and linkage_review_task.get("deepseek_called") is False
                    and linkage_review_task.get("github_called") is False
                    and linkage_review_receipt.get("contains_secret") is False
                    and "SHOULD_DROP" not in linkage_review_text,
                    "linkage review task records the pending real-provider/model evidence boundary without calls or secrets.",
                )
            )
            rows.append(
                _row(
                    "latest_linkage_review_cache_lookup_is_local_read_only",
                    latest_linkage_review.get("status") == "latest_tushare_deepseek_linkage_review_visible"
                    and latest_linkage_review.get("latest_task_id") == linkage_review_task.get("task_id")
                    and latest_linkage_review.get("review_status") == linkage_review_receipt.get("status")
                    and len(latest_linkage_review_rows) == len(linkage_review_rows)
                    and latest_linkage_review.get("cache_get_creates_task") is False
                    and latest_linkage_review.get("external_calls_triggered") is False
                    and latest_linkage_review.get("tushare_called") is False
                    and latest_linkage_review.get("deepseek_called") is False
                    and latest_linkage_review.get("github_called") is False
                    and latest_linkage_review.get("contains_secret") is False,
                    "GET migration status may replay the latest linkage review metadata, but it must not create tasks, call providers/models/probes, or expose secrets.",
                )
            )

            push_gate = (PROJECT_ROOT / "scripts" / "push_gate_3_0.sh").read_text(encoding="utf-8")
            this_script = (PROJECT_ROOT / "scripts" / "tushare_deepseek_linkage_contract.py").read_text(
                encoding="utf-8"
            )
            rows.append(
                _row(
                    "push_gate_runs_linkage_contract_in_correct_order",
                    "scripts/tushare_deepseek_linkage_contract.py" in push_gate
                    and "Tushare DeepSeek linkage contract" in push_gate
                    and "tushare_deepseek_linkage_contract: passed_local_linkage_contract_execution_pending"
                    in push_gate
                    and push_gate.find('run_step "Bootstrap runtime contract"')
                    < push_gate.find('run_step "Tushare DeepSeek linkage contract"')
                    < push_gate.find('run_step "Factor Test Lab contract"'),
                    "push gate must check cross-provider linkage after bootstrap runtime and before factor/model contracts.",
                )
            )
            rows.append(
                _row(
                    "script_is_local_no_provider_or_model_client",
                    "command_center_3_tushare_deepseek_linkage_contract.v1" in this_script
                    and "local_tushare_deepseek_linkage_contract_no_provider_or_model_execution" in this_script
                    and "provider_execution_implemented" in this_script
                    and "model_execution_implemented" in this_script
                    and "production_quant_projection_complete" in this_script
                    and "production_live_light_complete" in this_script
                    and "does_not_execute_trades" in this_script
                    and ("tushare" + "_adapter") not in this_script
                    and ("deepseek" + "_adapter") not in this_script
                    and ("api.github" + ".com") not in this_script,
                    "linkage contract must stay local and must not import provider/model/GitHub clients.",
                )
            )
    finally:
        task_service.clear_task_statuses_for_tests(clear_persisted=False)
        task_service.SQLITE_META_PATH = original_meta_path
        _restore_env(original_env)

    blockers = [row["criterion"] for row in rows if not row.get("passed")]
    return {
        "schema_version": "command_center_3_tushare_deepseek_linkage_contract.v1",
        "status": "tushare_deepseek_linkage_contract_passed" if not blockers else "tushare_deepseek_linkage_contract_blocked",
        "scope": "local_tushare_deepseek_linkage_contract_no_provider_or_model_execution",
        "ltg": "LTG-02/LTG-07/LTG-11/LTG-12/LTG-13",
        "contract_ready": not blockers,
        "runtime_mode_layering_ready": not blockers,
        "live_light_provider_linkage_visible": not blockers,
        "search_quant_projection_linkage_visible": not blockers,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "production_live_light_complete": False,
        "production_quant_projection_complete": False,
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
        "rows": rows,
        "note": (
            "This is a local linkage contract. Real Tushare provider calls, DeepSeek model calls, "
            "browser non-blocking evidence, and production promotion remain pending."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the full contract JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"tushare_deepseek_linkage_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "provider_execution_implemented: false; model_execution_implemented: false".format(**contract)
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
