#!/usr/bin/env python3
"""Validate the local Command Center 3 runtime bootstrap contract.

This push-gate guard never calls providers or models. It verifies that
cache_only startup stays offline, live_light creates only a rate-limited local
task skeleton, and planned Tushare / DeepSeek work remains behind auditable
POST task boundaries until provider execution is explicitly implemented later.
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

from server.services import bootstrap_service, task_service  # noqa: E402


ENV_KEYS = (
    "COMMAND_CENTER_BOOTSTRAP_MODE",
    "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
    "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
    "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
    "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
    "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL",
    "COMMAND_CENTER_LIVE_ALLOW_FULL_POOL",
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


def _set_env(**values: str) -> None:
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    for key, value in values.items():
        os.environ[key] = value


def _restore_env(snapshot: dict[str, str | None]) -> None:
    for key in ENV_KEYS:
        if snapshot.get(key) is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(snapshot[key])


def _serialized(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _stage_rows(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in _list(_dict(task.get("payload_safe")).get("bootstrap_stage_rows")) if isinstance(row, dict)]


def _model_rows(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in _list(_dict(task.get("payload_safe")).get("bootstrap_model_ledger_preview_rows"))
        if isinstance(row, dict)
    ]


def _summary(task: dict[str, Any]) -> dict[str, Any]:
    return _dict(_dict(task.get("payload_safe")).get("bootstrap_plan_summary"))


def _ledger(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in _list(task.get("call_ledger")) if isinstance(row, dict)]


def _stages_by_key(task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("stage_key") or ""): row for row in _stage_rows(task)}


def _all_false(rows: list[dict[str, Any]], *keys: str) -> bool:
    return all(row.get(key) is False for row in rows for key in keys)


def _cache_only_rows() -> list[dict[str, Any]]:
    _set_env(COMMAND_CENTER_BOOTSTRAP_MODE="cache_only")
    task_service.clear_task_statuses_for_tests(clear_persisted=True)
    status = bootstrap_service.read_bootstrap_status_cache()
    task = bootstrap_service.run_live_startup_task(
        {
            "source": "bootstrap_runtime_contract",
            "ts_code": "000001.SZ",
            "api_key": "SHOULD_DROP",
            "token": "SHOULD_DROP",
        }
    )
    stages = _stage_rows(task)
    models = _model_rows(task)
    summary = _summary(task)
    task_text = _serialized(task)
    return [
        _row(
            "cache_only_status_is_offline_default",
            status.get("mode") == "cache_only"
            and _dict(status.get("policy")).get("cache_api_external_calls") is False
            and _dict(status.get("policy")).get("react_initial_render_external_calls") is False
            and status.get("tushare_called") is False
            and status.get("deepseek_called") is False
            and status.get("github_called") is False,
            f"mode={status.get('mode')} status={status.get('status')}",
        ),
        _row(
            "cache_only_task_skips_provider_execution",
            task.get("current_step") == "live_bootstrap_skipped_mode_not_live_light"
            and summary.get("external_calls_triggered") is False
            and summary.get("planned_provider_stage_count") == 0
            and summary.get("planned_model_stage_count") == 0,
            f"current_step={task.get('current_step')} summary={summary}",
        ),
        _row(
            "cache_only_stage_and_model_plan_visible",
            len(stages) == 9
            and len(models) == 1
            and all(row.get("status") == "skipped_mode_not_live_light" for row in stages)
            and models[0].get("model_called") is False
            and models[0].get("deepseek_called") is False,
            f"stage_count={len(stages)} model_preview_count={len(models)}",
        ),
        _row(
            "cache_only_payload_sanitizes_secret_like_inputs",
            "SHOULD_DROP" not in task_text and '"api_key"' not in task_text and '"token"' not in task_text,
            "raw secret-like payload keys/values are not serialized into task output",
        ),
    ]


def _live_light_disabled_rows() -> list[dict[str, Any]]:
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="live_light",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="false",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="false",
    )
    task_service.clear_task_statuses_for_tests(clear_persisted=True)
    task = bootstrap_service.run_live_startup_task({"source": "bootstrap_runtime_contract", "symbols": ["000001.SZ"]})
    stages = _stage_rows(task)
    summary = _summary(task)
    provider_or_model = [row for row in stages if row.get("stage_kind") in {"provider", "model"}]
    return [
        _row(
            "live_light_sources_disabled_skips_safely",
            task.get("current_step") == "live_bootstrap_skipped_sources_disabled_no_external_call"
            and summary.get("planned_provider_stage_count") == 0
            and summary.get("planned_model_stage_count") == 0
            and summary.get("external_calls_triggered") is False,
            f"current_step={task.get('current_step')} summary={summary}",
        ),
        _row(
            "live_light_disabled_provider_model_rows_are_skipped_by_config",
            provider_or_model
            and all(row.get("status") == "skipped_by_config" for row in provider_or_model)
            and _all_false(provider_or_model, "actual_external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            f"provider_model_row_count={len(provider_or_model)}",
        ),
    ]


def _live_light_enabled_rows() -> list[dict[str, Any]]:
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="live_light",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="true",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="true",
        COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT="2",
        COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS="600",
        COMMAND_CENTER_LIVE_DEEPSEEK_MODEL="contract-live-pro",
        COMMAND_CENTER_LIVE_ALLOW_FULL_POOL="false",
    )
    task_service.clear_task_statuses_for_tests(clear_persisted=True)
    task = bootstrap_service.run_live_startup_task(
        {
            "source": "bootstrap_runtime_contract",
            "symbols": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "tushare": True,
            "deepseek": True,
        }
    )
    repeated = bootstrap_service.run_live_startup_task(
        {
            "source": "bootstrap_runtime_contract",
            "symbols": ["000001.SZ"],
            "tushare": True,
            "deepseek": True,
        }
    )
    stages = _stage_rows(task)
    stages_by_key = _stages_by_key(task)
    models = _model_rows(task)
    model = models[0] if models else {}
    payload = _dict(task.get("payload_safe"))
    summary = _summary(task)
    call_ledger = _ledger(task)
    first_ledger = call_ledger[0] if call_ledger else {}
    repeated_ledger = _ledger(repeated)
    last_repeated = repeated_ledger[-1] if repeated_ledger else {}
    required_fields = set(_list(model.get("required_model_ledger_fields")))
    allowed_fields = set(_list(model.get("allowed_output_fields")))
    return [
        _row(
            "live_light_records_plan_without_provider_execution",
            task.get("current_step") == "live_bootstrap_plan_recorded_no_provider_execution"
            and len(stages) == 9
            and len(models) == 1
            and summary.get("planned_provider_stage_count") == 2
            and summary.get("planned_model_stage_count") == 1
            and summary.get("actual_provider_execution_count") == 0
            and summary.get("actual_model_call_count") == 0
            and summary.get("external_calls_triggered") is False,
            f"current_step={task.get('current_step')} summary={summary}",
        ),
        _row(
            "live_light_symbol_limit_is_enforced",
            payload.get("symbols") == ["000001.SZ", "000002.SZ"]
            and payload.get("symbol_count") == 2
            and payload.get("truncated_by_symbol_limit") is True,
            f"symbols={payload.get('symbols')} truncated={payload.get('truncated_by_symbol_limit')}",
        ),
        _row(
            "live_light_tushare_stages_are_planned_not_executed",
            stages_by_key.get("trade_cal_if_needed", {}).get("status") == "planned_provider_pending_not_executed"
            and stages_by_key.get("tushare_light_refresh", {}).get("status") == "planned_provider_pending_not_executed"
            and stages_by_key.get("trade_cal_if_needed", {}).get("provider_execution_implemented") is False
            and stages_by_key.get("tushare_light_refresh", {}).get("provider_execution_implemented") is False
            and _all_false(stages, "actual_external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            "trade_cal and light Tushare stages are planned but not executed",
        ),
        _row(
            "live_light_local_stages_are_planned",
            stages_by_key.get("factor_light_runtime", {}).get("status") == "planned_local_step_pending_not_executed"
            and stages_by_key.get("factor_quant_hub_cache_refresh", {}).get("status")
            == "planned_local_step_pending_not_executed"
            and stages_by_key.get("next_session_cache_refresh", {}).get("status")
            == "planned_local_step_pending_not_executed"
            and stages_by_key.get("ui_task_polling", {}).get("status") == "planned_local_step_pending_not_executed",
            "local cache/factor/UI stages remain visible as skeleton plan rows",
        ),
        _row(
            "live_light_deepseek_model_ledger_preview_is_governed",
            stages_by_key.get("deepseek_pro_explanation", {}).get("status") == "planned_model_pending_not_executed"
            and model.get("model") == "contract-live-pro"
            and model.get("model_call_implemented") is False
            and model.get("model_called") is False
            and model.get("deepseek_called") is False
            and {"model_used", "status", "token_usage", "parse_status", "input_hash", "output_hash"}.issubset(
                required_fields
            )
            and allowed_fields
            == {
                "summary",
                "support_notes",
                "suppress_notes",
                "conflict_notes",
                "missing_data_notes",
                "discipline_notes",
            },
            f"model={model.get('model')} required_fields={sorted(required_fields)}",
        ),
        _row(
            "live_light_call_ledger_counts_match_plan",
            first_ledger.get("bootstrap_stage_count") == 9
            and first_ledger.get("model_ledger_preview_count") == 1
            and first_ledger.get("planned_provider_stage_count") == 2
            and first_ledger.get("planned_model_stage_count") == 1
            and first_ledger.get("external_calls_triggered") is False
            and first_ledger.get("tushare_called") is False
            and first_ledger.get("deepseek_called") is False
            and first_ledger.get("github_called") is False,
            f"ledger={first_ledger}",
        ),
        _row(
            "live_light_rate_limit_reuses_existing_task",
            repeated.get("task_id") == task.get("task_id")
            and repeated.get("current_step") == "live_bootstrap_skipped_due_to_rate_limit"
            and last_repeated.get("call_status") == "skipped_due_to_rate_limit_reused_existing_task"
            and last_repeated.get("bootstrap_stage_count") == 9
            and last_repeated.get("model_ledger_preview_count") == 1
            and last_repeated.get("planned_provider_stage_count") == 2
            and last_repeated.get("planned_model_stage_count") == 1
            and last_repeated.get("external_calls_triggered") is False,
            f"task_id={task.get('task_id')} repeated_step={repeated.get('current_step')}",
        ),
    ]


def build_contract() -> dict[str, Any]:
    original_env = {key: os.environ.get(key) for key in ENV_KEYS}
    original_meta_path = task_service.SQLITE_META_PATH
    rows: list[dict[str, Any]] = []
    try:
        with tempfile.TemporaryDirectory(prefix="stock_ming_bootstrap_contract_") as temp_dir:
            task_service.SQLITE_META_PATH = Path(temp_dir) / "meta.sqlite"
            rows.extend(_cache_only_rows())
            rows.extend(_live_light_disabled_rows())
            rows.extend(_live_light_enabled_rows())
    finally:
        task_service.clear_task_statuses_for_tests(clear_persisted=False)
        task_service.SQLITE_META_PATH = original_meta_path
        _restore_env(original_env)

    blockers = [row["criterion"] for row in rows if not row.get("passed")]
    return {
        "schema_version": "command_center_3_bootstrap_runtime_contract.v1",
        "status": "bootstrap_runtime_contract_passed" if not blockers else "bootstrap_runtime_contract_blocked",
        "scope": "local_bootstrap_runtime_contract_no_provider_or_model_execution",
        "rows": rows,
        "row_count": len(rows),
        "blockers": blockers,
        "blocking_criterion_count": len(blockers),
        "stage_count": 9,
        "model_ledger_preview_count": 1,
        "planned_provider_stage_count": 2,
        "planned_model_stage_count": 1,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the full contract JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"bootstrap_runtime_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "stage_count: {stage_count}; model_ledger_preview_count: {model_ledger_preview_count}".format(
                **contract
            )
        )
        print(
            "provider_execution_implemented: {provider_execution_implemented}; "
            "model_execution_implemented: {model_execution_implemented}".format(**contract)
        )
        print(
            "external_calls_triggered: {external_calls_triggered}; "
            "tushare_called: {tushare_called}; deepseek_called: {deepseek_called}; "
            "github_called: {github_called}; does_not_execute_trades: {does_not_execute_trades}".format(
                **contract
            )
        )
        if contract["blockers"]:
            print("blockers:")
            for blocker in contract["blockers"]:
                print(f"- {blocker}")
    return 0 if not contract["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
