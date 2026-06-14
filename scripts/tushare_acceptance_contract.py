#!/usr/bin/env python3
"""Validate the local LTG-02 Tushare acceptance contract.

This script is a push-gate guard, not a provider acceptance run. It imports
only local task contract helpers and fails on unsafe regressions such as
matrix-only rows being promoted to verified, provider-backed acceptance being
claimed from local QA contracts, or lost no-trade/no-action boundaries.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import task_service, tushare_task_service  # noqa: E402


CONTRACT_KEYS = [
    "api_acceptance_audit",
    "failure_mode_qa_contract",
    "request_parameter_qa_contract",
    "provider_target_sample_plan_contract",
    "provider_target_sample_acceptance_contract",
    "provider_acceptance_readiness_audit",
    "provider_acceptance_promotion_audit",
    "provider_evidence_gap_audit",
    "provider_sample_readiness_receipt",
    "provider_sample_activation_receipt",
    "provider_target_sample_runbook_contract",
]


def _row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "evidence": evidence,
    }


def _flag_false(contract: dict[str, Any], *keys: str) -> bool:
    return all(contract.get(key) is False for key in keys)


def _success_ledger_row(api: str, params: dict[str, Any], *, data_date: str) -> dict[str, Any]:
    return {
        "api": api,
        "request_params_safe": params,
        "row_count": 1,
        "data_date": data_date,
        "local_fetched_at": "2026-06-10T16:31:00",
        "call_status": "success",
        "failure_mode": "none",
        "failure_mode_status": "success_non_empty",
        "safe_failure_mode_visible": True,
        "error_message_safe": "",
        "parquet_dataset": None,
        "parquet_status": "not_enabled",
        "parquet_row_count": 0,
        "external": True,
        "external_calls_triggered": True,
        "tushare_called": True,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _catalog_by_type(task_type: str) -> dict[str, Any]:
    for row in task_service.TASK_CATALOG:
        if row.get("task_type") == task_type:
            return dict(row)
    return {}


def _read_script(path: str) -> str:
    try:
        return (PROJECT_ROOT / path).read_text(encoding="utf-8")
    except Exception:
        return ""


def build_contract() -> dict[str, Any]:
    selected_apis: list[str] = []
    call_ledger: list[dict[str, Any]] = []
    validation_rows = tushare_task_service._api_validation_rows(selected_apis, call_ledger)
    validation_target_rows = tushare_task_service._validation_target_rows(validation_rows)
    acceptance_audit = tushare_task_service._api_acceptance_audit(validation_rows, call_ledger)
    failure_mode_qa = tushare_task_service._failure_mode_qa_contract(validation_rows, call_ledger)
    request_parameter_qa = tushare_task_service._request_parameter_qa_contract(selected_apis, {})
    target_sample_plan = tushare_task_service._provider_target_sample_plan_contract(
        selected_apis=selected_apis,
        payload={},
        api_validation_rows=validation_rows,
    )
    target_sample_acceptance = tushare_task_service._provider_target_sample_acceptance_contract(
        selected_apis=selected_apis,
        payload={},
        api_validation_rows=validation_rows,
        validation_target_rows=validation_target_rows,
        provider_target_sample_plan_contract=target_sample_plan,
        call_ledger=call_ledger,
    )
    provider_readiness = tushare_task_service._provider_acceptance_readiness_audit(
        api_validation_rows=validation_rows,
        validation_target_rows=validation_target_rows,
        api_acceptance_audit=acceptance_audit,
    )
    provider_promotion = tushare_task_service._provider_acceptance_promotion_audit(
        api_validation_rows=validation_rows,
        validation_target_rows=validation_target_rows,
        api_acceptance_audit=acceptance_audit,
        provider_target_sample_plan_contract=target_sample_plan,
        provider_acceptance_readiness_audit=provider_readiness,
        call_ledger=call_ledger,
    )
    provider_evidence_gap = tushare_task_service._provider_evidence_gap_audit(
        api_validation_rows=validation_rows,
        validation_target_rows=validation_target_rows,
        provider_target_sample_plan_contract=target_sample_plan,
        provider_acceptance_promotion_audit=provider_promotion,
        call_ledger=call_ledger,
    )
    provider_sample_receipt = tushare_task_service._provider_sample_readiness_receipt(
        provider_target_sample_plan_contract=target_sample_plan,
        provider_acceptance_readiness_audit=provider_readiness,
        provider_acceptance_promotion_audit=provider_promotion,
        provider_evidence_gap_audit=provider_evidence_gap,
    )
    provider_sample_activation = tushare_task_service._provider_sample_activation_receipt(
        provider_target_sample_plan_contract=target_sample_plan,
        provider_sample_readiness_receipt=provider_sample_receipt,
        provider_acceptance_promotion_audit=provider_promotion,
        provider_evidence_gap_audit=provider_evidence_gap,
    )
    provider_target_sample_runbook = tushare_task_service._provider_target_sample_runbook_contract(
        selected_apis=selected_apis,
        payload={},
        provider_target_sample_plan_contract=target_sample_plan,
        provider_target_sample_acceptance_contract=target_sample_acceptance,
        provider_evidence_gap_audit=provider_evidence_gap,
        provider_sample_activation_receipt=provider_sample_activation,
    )

    refresh_catalog = _catalog_by_type("refresh_tushare_facts")
    factor_refresh_catalog = _catalog_by_type("refresh_factor_data")
    push_gate_script = _read_script("scripts/push_gate_3_0.sh")
    this_script = _read_script("scripts/tushare_acceptance_contract.py")

    api_count = len(tushare_task_service.REFRESH_API_SPECS)
    core_apis = list(tushare_task_service.CORE_REFRESH_APIS)
    calendar_apis = list(tushare_task_service.CALENDAR_REFRESH_APIS)
    extended_apis = list(tushare_task_service.EXTENDED_REFRESH_APIS)
    parquet_apis = list(tushare_task_service.PARQUET_DATASETS.keys())
    matrix_only_rows = [row for row in validation_rows if row.get("validation_scope") == "capability_matrix_only"]
    target_matrix_only_rows = [row for row in validation_target_rows if row.get("readiness") == "matrix_only"]
    readiness_criteria = {row.get("criterion") for row in provider_readiness.get("rows", [])}
    provider_evidence_gap_rows = provider_evidence_gap.get("rows", [])

    default_selection = tushare_task_service._selected_apis({}, tushare_task_service.CORE_REFRESH_APIS)
    calendar_selection = tushare_task_service._selected_apis(
        {"include_calendar": True},
        tushare_task_service.CORE_REFRESH_APIS,
    )
    extended_selection = tushare_task_service._selected_apis(
        {"include_extended": True},
        tushare_task_service.CORE_REFRESH_APIS,
    )
    trade_cal_start = _dt.date(2024, 1, 1)
    trade_cal_end = trade_cal_start + _dt.timedelta(days=820)
    trade_cal_rows = []
    cursor = trade_cal_start
    while cursor <= trade_cal_end:
        trade_cal_rows.append(
            {
                "exchange": "SSE",
                "cal_date": cursor.strftime("%Y%m%d"),
                "is_open": 1 if cursor.weekday() < 5 else 0,
            }
        )
        cursor += _dt.timedelta(days=1)
    trade_cal_partial_acceptance = tushare_task_service._trade_cal_provider_acceptance_fields(
        "trade_cal",
        params={"start_date": trade_cal_start.strftime("%Y%m%d"), "end_date": trade_cal_end.strftime("%Y%m%d")},
        rows=trade_cal_rows,
        payload={"acceptance_mode": "provider_backed_trade_cal_long_window"},
        call_status="success",
    )
    trade_cal_full_acceptance = tushare_task_service._trade_cal_provider_acceptance_fields(
        "trade_cal",
        params={"start_date": trade_cal_start.strftime("%Y%m%d"), "end_date": trade_cal_end.strftime("%Y%m%d")},
        rows=trade_cal_rows,
        payload={
            "acceptance_mode": "provider_backed_trade_cal_long_window",
            "freshness_replay_passed": True,
            "freshness_replay_scenario_count": 8,
            "failure_modes_validated": True,
            "failure_mode_validated_count": 6,
        },
        call_status="success",
    )
    target_sample_selected_apis = ["margin_detail"]
    target_sample_call_ledger = [
        {
            "api": "margin_detail",
            "request_params_safe": {
                "ts_code": "002008.SZ",
                "trade_date": "20260610",
                "start_date": "20260601",
                "end_date": "20260610",
            },
            "row_count": 1,
            "data_date": "20260610",
            "local_fetched_at": "2026-06-10T16:31:00",
            "call_status": "success",
            "failure_mode": "none",
            "failure_mode_status": "success_non_empty",
            "safe_failure_mode_visible": True,
            "error_message_safe": "",
            "parquet_dataset": None,
            "parquet_status": "not_enabled",
            "parquet_row_count": 0,
            "external": True,
            "external_calls_triggered": True,
            "tushare_called": True,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]
    target_sample_payload = {
        "apis": target_sample_selected_apis,
        "ts_code": "002008.SZ",
        "trade_date": "20260610",
        "start_date": "20260601",
        "end_date": "20260610",
        "acceptance_mode": "provider_target_sample_acceptance",
        "target_sample_acceptance_groups": ["margin_financing"],
        "failure_modes_validated": True,
        "failure_mode_validated_count": 6,
    }
    target_sample_validation_rows = tushare_task_service._api_validation_rows(
        target_sample_selected_apis,
        target_sample_call_ledger,
    )
    target_sample_validation_target_rows = tushare_task_service._validation_target_rows(target_sample_validation_rows)
    target_sample_plan_ready = tushare_task_service._provider_target_sample_plan_contract(
        selected_apis=target_sample_selected_apis,
        payload=target_sample_payload,
        api_validation_rows=target_sample_validation_rows,
    )
    target_sample_acceptance_ready = tushare_task_service._provider_target_sample_acceptance_contract(
        selected_apis=target_sample_selected_apis,
        payload=target_sample_payload,
        api_validation_rows=target_sample_validation_rows,
        validation_target_rows=target_sample_validation_target_rows,
        provider_target_sample_plan_contract=target_sample_plan_ready,
        call_ledger=target_sample_call_ledger,
    )
    target_sample_acceptance_audit = tushare_task_service._api_acceptance_audit(
        target_sample_validation_rows,
        target_sample_call_ledger,
    )
    target_sample_readiness = tushare_task_service._provider_acceptance_readiness_audit(
        api_validation_rows=target_sample_validation_rows,
        validation_target_rows=target_sample_validation_target_rows,
        api_acceptance_audit=target_sample_acceptance_audit,
    )
    target_sample_promotion = tushare_task_service._provider_acceptance_promotion_audit(
        api_validation_rows=target_sample_validation_rows,
        validation_target_rows=target_sample_validation_target_rows,
        api_acceptance_audit=target_sample_acceptance_audit,
        provider_target_sample_plan_contract=target_sample_plan_ready,
        provider_acceptance_readiness_audit=target_sample_readiness,
        call_ledger=target_sample_call_ledger,
    )
    target_sample_gap = tushare_task_service._provider_evidence_gap_audit(
        api_validation_rows=target_sample_validation_rows,
        validation_target_rows=target_sample_validation_target_rows,
        provider_target_sample_plan_contract=target_sample_plan_ready,
        provider_acceptance_promotion_audit=target_sample_promotion,
        call_ledger=target_sample_call_ledger,
        provider_target_sample_acceptance_contract=target_sample_acceptance_ready,
    )
    target_sample_receipt = tushare_task_service._provider_sample_readiness_receipt(
        provider_target_sample_plan_contract=target_sample_plan_ready,
        provider_target_sample_acceptance_contract=target_sample_acceptance_ready,
        provider_acceptance_readiness_audit=target_sample_readiness,
        provider_acceptance_promotion_audit=target_sample_promotion,
        provider_evidence_gap_audit=target_sample_gap,
    )
    target_sample_activation = tushare_task_service._provider_sample_activation_receipt(
        provider_target_sample_plan_contract=target_sample_plan_ready,
        provider_sample_readiness_receipt=target_sample_receipt,
        provider_acceptance_promotion_audit=target_sample_promotion,
        provider_evidence_gap_audit=target_sample_gap,
    )
    target_sample_runbook = tushare_task_service._provider_target_sample_runbook_contract(
        selected_apis=target_sample_selected_apis,
        payload=target_sample_payload,
        provider_target_sample_plan_contract=target_sample_plan_ready,
        provider_target_sample_acceptance_contract=target_sample_acceptance_ready,
        provider_evidence_gap_audit=target_sample_gap,
        provider_sample_activation_receipt=target_sample_activation,
    )
    target_sample_gap_rows = {row.get("target"): row for row in target_sample_gap.get("rows", [])}
    target_sample_receipt_rows = {row.get("criterion"): row for row in target_sample_receipt.get("rows", [])}
    target_sample_runbook_rows = {row.get("target"): row for row in target_sample_runbook.get("rows", [])}
    target_sample_rows = {row.get("target"): row for row in target_sample_acceptance_ready.get("rows", [])}
    multi_target_groups = [
        "dragon_tiger",
        "limit_emotion",
        "chip_distribution",
        "financial_disclosure",
        "hard_risk",
    ]
    multi_target_selected_apis = [
        "top_list",
        "top_inst",
        "stk_limit",
        "limit_list_d",
        "limit_cpt_list",
        "cyq_perf",
        "cyq_chips",
        "forecast",
        "fina_indicator",
        "anns_d",
        "stk_holdertrade",
        "share_float",
        "pledge_stat",
        "pledge_detail",
        "stk_surv",
    ]
    multi_target_payload = {
        "apis": multi_target_selected_apis,
        "ts_code": "002008.SZ",
        "trade_date": "20260610",
        "start_date": "20260601",
        "end_date": "20260610",
        "ann_date": "20260610",
        "period": "20260630",
        "float_date": "20260610",
        "acceptance_mode": "provider_target_sample_acceptance",
        "target_sample_acceptance_groups": multi_target_groups,
        "failure_modes_validated": True,
        "failure_mode_validated_count": 6,
    }
    common_target_params = {
        "ts_code": "002008.SZ",
        "trade_date": "20260610",
        "start_date": "20260601",
        "end_date": "20260610",
        "ann_date": "20260610",
        "period": "20260630",
        "float_date": "20260610",
    }
    multi_target_call_ledger = [
        _success_ledger_row(api, common_target_params, data_date="20260610")
        for api in multi_target_selected_apis
    ]
    multi_target_validation_rows = tushare_task_service._api_validation_rows(
        multi_target_selected_apis,
        multi_target_call_ledger,
    )
    multi_target_validation_target_rows = tushare_task_service._validation_target_rows(multi_target_validation_rows)
    multi_target_plan = tushare_task_service._provider_target_sample_plan_contract(
        selected_apis=multi_target_selected_apis,
        payload=multi_target_payload,
        api_validation_rows=multi_target_validation_rows,
    )
    multi_target_acceptance = tushare_task_service._provider_target_sample_acceptance_contract(
        selected_apis=multi_target_selected_apis,
        payload=multi_target_payload,
        api_validation_rows=multi_target_validation_rows,
        validation_target_rows=multi_target_validation_target_rows,
        provider_target_sample_plan_contract=multi_target_plan,
        call_ledger=multi_target_call_ledger,
    )
    multi_target_acceptance_audit = tushare_task_service._api_acceptance_audit(
        multi_target_validation_rows,
        multi_target_call_ledger,
    )
    multi_target_readiness = tushare_task_service._provider_acceptance_readiness_audit(
        api_validation_rows=multi_target_validation_rows,
        validation_target_rows=multi_target_validation_target_rows,
        api_acceptance_audit=multi_target_acceptance_audit,
    )
    multi_target_promotion = tushare_task_service._provider_acceptance_promotion_audit(
        api_validation_rows=multi_target_validation_rows,
        validation_target_rows=multi_target_validation_target_rows,
        api_acceptance_audit=multi_target_acceptance_audit,
        provider_target_sample_plan_contract=multi_target_plan,
        provider_acceptance_readiness_audit=multi_target_readiness,
        call_ledger=multi_target_call_ledger,
    )
    multi_target_gap = tushare_task_service._provider_evidence_gap_audit(
        api_validation_rows=multi_target_validation_rows,
        validation_target_rows=multi_target_validation_target_rows,
        provider_target_sample_plan_contract=multi_target_plan,
        provider_acceptance_promotion_audit=multi_target_promotion,
        call_ledger=multi_target_call_ledger,
        provider_target_sample_acceptance_contract=multi_target_acceptance,
    )
    multi_target_receipt = tushare_task_service._provider_sample_readiness_receipt(
        provider_target_sample_plan_contract=multi_target_plan,
        provider_target_sample_acceptance_contract=multi_target_acceptance,
        provider_acceptance_readiness_audit=multi_target_readiness,
        provider_acceptance_promotion_audit=multi_target_promotion,
        provider_evidence_gap_audit=multi_target_gap,
    )
    multi_target_activation = tushare_task_service._provider_sample_activation_receipt(
        provider_target_sample_plan_contract=multi_target_plan,
        provider_sample_readiness_receipt=multi_target_receipt,
        provider_acceptance_promotion_audit=multi_target_promotion,
        provider_evidence_gap_audit=multi_target_gap,
    )
    multi_target_runbook = tushare_task_service._provider_target_sample_runbook_contract(
        selected_apis=multi_target_selected_apis,
        payload=multi_target_payload,
        provider_target_sample_plan_contract=multi_target_plan,
        provider_target_sample_acceptance_contract=multi_target_acceptance,
        provider_evidence_gap_audit=multi_target_gap,
        provider_sample_activation_receipt=multi_target_activation,
    )
    multi_target_rows = {row.get("target"): row for row in multi_target_acceptance.get("rows", [])}
    multi_target_gap_rows = {row.get("target"): row for row in multi_target_gap.get("rows", [])}
    multi_target_receipt_rows = {row.get("criterion"): row for row in multi_target_receipt.get("rows", [])}
    multi_target_runbook_rows = {row.get("target"): row for row in multi_target_runbook.get("rows", [])}
    validation_target_group_keys = [target for target, _label, _apis in tushare_task_service.VALIDATION_TARGET_GROUPS]
    extended_target_group_keys = [target for target in validation_target_group_keys if target != "trade_calendar"]
    interface_group_scope_rows: list[dict[str, Any]] = []
    for target_key, label, apis in tushare_task_service.VALIDATION_TARGET_GROUPS:
        if target_key == "trade_calendar":
            acceptance_layer = "provider_backed_trade_cal_long_window"
            review_fixture_status = "trade_cal_long_window_fixture_exercised_not_real_provider"
            review_ready = bool(trade_cal_full_acceptance.get("provider_backed_long_window_acceptance_done"))
            source_fixture = "trade_cal_long_window_acceptance_fields"
        elif target_key == "margin_financing":
            acceptance_layer = tushare_task_service.PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE
            review_fixture_status = str(
                target_sample_rows.get(target_key, {}).get("target_sample_acceptance_status")
                or "target_sample_acceptance_not_requested"
            )
            review_ready = review_fixture_status == "target_sample_acceptance_ready_for_review"
            source_fixture = "single_target_sample_acceptance_fixture"
        else:
            acceptance_layer = tushare_task_service.PROVIDER_TARGET_SAMPLE_ACCEPTANCE_MODE
            review_fixture_status = str(
                multi_target_rows.get(target_key, {}).get("target_sample_acceptance_status")
                or "target_sample_acceptance_not_requested"
            )
            review_ready = review_fixture_status == "target_sample_acceptance_ready_for_review"
            source_fixture = "multi_target_sample_acceptance_fixture"
        interface_group_scope_rows.append(
            {
                "target": target_key,
                "label": label,
                "apis": list(apis),
                "group_category": "calendar" if target_key == "trade_calendar" else "extended",
                "post_task_route": "POST /api/tasks/refresh-tushare-facts",
                "acceptance_layer": acceptance_layer,
                "review_fixture_status": review_fixture_status,
                "push_gate_review_fixture_ready": review_ready,
                "push_gate_fixture_source": source_fixture,
                "push_gate_fixture_is_not_real_provider_acceptance": True,
                "requires_explicit_post_task": True,
                "real_provider_sample_still_required": True,
                "provider_promotion_still_required": True,
                "provider_backed_acceptance_done": False,
                "full_interface_acceptance_done": False,
                "production_tushare_pipeline_complete": False,
                "cache_get_external_calls": False,
                "react_render_external_calls": False,
                "contract_external_calls_triggered": False,
                "tushare_called_by_contract": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        )

    rows = [
        _row(
            "post_task_catalog_button_gate",
            refresh_catalog.get("route") == "POST /api/tasks/refresh-tushare-facts"
            and refresh_catalog.get("button_gated") is True
            and refresh_catalog.get("cache_get_external_calls") is False
            and refresh_catalog.get("default_core_apis") == core_apis
            and refresh_catalog.get("calendar_apis") == calendar_apis
            and refresh_catalog.get("optional_extended_apis") == extended_apis
            and refresh_catalog.get("parquet_enabled_apis") == parquet_apis
            and refresh_catalog.get("call_ledger_required") is True
            and refresh_catalog.get("provider_acceptance_modes")
            == ["provider_backed_trade_cal_long_window", "provider_target_sample_acceptance"]
            and refresh_catalog.get("trade_cal_provider_acceptance_mode_requires_explicit_payload") is True
            and refresh_catalog.get("trade_cal_provider_acceptance_is_full_interface_acceptance") is False
            and refresh_catalog.get("provider_target_sample_acceptance_mode_requires_explicit_payload") is True
            and refresh_catalog.get("provider_target_sample_acceptance_is_full_interface_acceptance") is False
            and refresh_catalog.get("full_interface_acceptance_done") is False,
            "Tushare refresh must remain a button-gated POST task with core defaults, optional calendar/extended APIs, and no GET cache external call.",
        ),
        _row(
            "factor_refresh_delegate_is_conservative",
            factor_refresh_catalog.get("route") == "POST /api/factor-quant/refresh-data"
            and factor_refresh_catalog.get("button_gated") is True
            and factor_refresh_catalog.get("cache_get_external_calls") is False
            and factor_refresh_catalog.get("api_acceptance_audit_contract")
            and factor_refresh_catalog.get("provider_target_sample_plan_is_provider_acceptance") is False
            and factor_refresh_catalog.get("provider_target_sample_acceptance_is_full_interface_acceptance") is False
            and factor_refresh_catalog.get("request_parameter_qa_is_provider_acceptance") is False
            and factor_refresh_catalog.get("failure_mode_qa_is_provider_acceptance") is False,
            "Delegated factor refresh must inherit Tushare task contracts and cannot promote local QA to provider acceptance.",
        ),
        _row(
            "api_declarations_complete",
            api_count == len(core_apis) + len(calendar_apis) + len(extended_apis)
            and api_count >= 20
            and set(parquet_apis) == set(core_apis + calendar_apis)
            and "trade_cal" in calendar_apis
            and "fina_indicator" in extended_apis,
            "Declared Tushare APIs must keep core, trade_cal, and extended groups explicit while Parquet remains limited to approved datasets.",
        ),
        _row(
            "selection_policy_conservative",
            default_selection == core_apis
            and calendar_selection == core_apis + calendar_apis
            and set(extended_selection) == set(core_apis + calendar_apis + extended_apis),
            "Default selection is core only; trade_cal and extended APIs require explicit payload flags or API selection.",
        ),
        _row(
            "trade_cal_provider_acceptance_mode_is_explicit",
            trade_cal_partial_acceptance.get("acceptance_mode") == "provider_backed_trade_cal_long_window"
            and trade_cal_partial_acceptance.get("minimum_window_days_passed") is True
            and trade_cal_partial_acceptance.get("provider_backed_long_window_acceptance_done") is False
            and "freshness_replay_evidence_missing" in trade_cal_partial_acceptance.get("provider_acceptance_blockers", [])
            and "failure_mode_evidence_missing" in trade_cal_partial_acceptance.get("provider_acceptance_blockers", [])
            and trade_cal_full_acceptance.get("provider_backed_long_window_acceptance_done") is True
            and trade_cal_full_acceptance.get("provider_backed_trade_cal_acceptance_done") is True
            and int(trade_cal_full_acceptance.get("freshness_replay_scenario_count") or 0) >= 8
            and int(trade_cal_full_acceptance.get("failure_mode_validated_count") or 0) >= 6
            and trade_cal_full_acceptance.get("production_tushare_pipeline_complete") is False
            and trade_cal_full_acceptance.get("does_not_modify_strategy_action") is True,
            "trade_cal provider-backed long-window acceptance requires explicit payload, 730-day schema/window evidence, freshness replay evidence, and failure-mode evidence.",
        ),
        _row(
            "matrix_only_rows_not_verified",
            len(matrix_only_rows) == api_count
            and acceptance_audit.get("matrix_only_api_count") == api_count
            and acceptance_audit.get("matrix_only_not_verified_count") == api_count
            and acceptance_audit.get("does_not_claim_unselected_apis_verified") is True
            and all(row.get("validation_status") == "not_requested" for row in matrix_only_rows),
            "Unselected APIs must stay capability matrix rows and must not be marked verified.",
        ),
        _row(
            "api_acceptance_audit_is_semantic_only",
            acceptance_audit.get("schema_version") == "tushare_api_acceptance_audit.v1"
            and acceptance_audit.get("scope") == "local_call_ledger_semantic_audit_not_provider_call"
            and acceptance_audit.get("status") == "acceptance_audit_passed"
            and acceptance_audit.get("full_interface_acceptance_done") is False
            and acceptance_audit.get("provider_validation_done_in_this_task") is False
            and acceptance_audit.get("audit_calls_tushare") is False
            and _flag_false(acceptance_audit, "cache_get_external_calls", "audit_external_calls_triggered", "deepseek_called", "github_called")
            and acceptance_audit.get("does_not_execute_trades") is True
            and acceptance_audit.get("does_not_modify_strategy_action") is True,
            "Acceptance audit validates local call-ledger semantics only; it must not imply provider-backed coverage.",
        ),
        _row(
            "failure_mode_qa_is_local_pending",
            failure_mode_qa.get("schema_version") == "tushare_failure_mode_qa_contract.v1"
            and failure_mode_qa.get("status") == "failure_mode_qa_ready_provider_acceptance_pending"
            and failure_mode_qa.get("provider_backed_acceptance_done") is False
            and failure_mode_qa.get("production_tushare_pipeline_complete") is False
            and failure_mode_qa.get("matrix_only_not_requested_distinguishable") is True
            and _flag_false(failure_mode_qa, "cache_get_external_calls", "qa_external_calls_triggered", "tushare_called_by_qa", "deepseek_called", "github_called")
            and failure_mode_qa.get("does_not_execute_trades") is True
            and failure_mode_qa.get("does_not_modify_strategy_action") is True,
            "Failure-mode QA classifies visible ledger states only and keeps provider acceptance pending.",
        ),
        _row(
            "request_parameter_qa_is_local_pending",
            request_parameter_qa.get("schema_version") == "tushare_request_parameter_qa_contract.v1"
            and request_parameter_qa.get("status") == "request_parameter_qa_ready_provider_acceptance_pending"
            and request_parameter_qa.get("provider_backed_acceptance_done") is False
            and request_parameter_qa.get("production_tushare_pipeline_complete") is False
            and request_parameter_qa.get("matrix_only_api_count") == api_count
            and _flag_false(request_parameter_qa, "cache_get_external_calls", "qa_external_calls_triggered", "tushare_called_by_qa", "deepseek_called", "github_called")
            and request_parameter_qa.get("does_not_execute_trades") is True
            and request_parameter_qa.get("does_not_modify_strategy_action") is True,
            "Request-parameter QA checks safe local parameters and matrix boundaries without provider calls.",
        ),
        _row(
            "target_sample_plan_is_plan_only",
            target_sample_plan.get("schema_version") == "tushare_provider_target_sample_plan_contract.v1"
            and target_sample_plan.get("status") == "local_plan_ready_provider_execution_pending"
            and target_sample_plan.get("ready_to_execute_target_count") == 0
            and target_sample_plan.get("pending_or_blocked_target_count") == target_sample_plan.get("target_count")
            and target_sample_plan.get("provider_backed_acceptance_done") is False
            and target_sample_plan.get("production_tushare_pipeline_complete") is False
            and _flag_false(target_sample_plan, "cache_get_external_calls", "plan_external_calls_triggered", "tushare_called_by_plan", "deepseek_called", "github_called")
            and target_sample_plan.get("does_not_execute_trades") is True
            and target_sample_plan.get("does_not_modify_strategy_action") is True,
            "Target sample plan declares future real-provider samples only; it is not provider-backed acceptance.",
        ),
        _row(
            "target_sample_acceptance_contract_is_explicit_and_non_promoting",
            target_sample_acceptance.get("schema_version") == "tushare_provider_target_sample_acceptance_contract.v1"
            and target_sample_acceptance.get("status") == "target_sample_acceptance_not_requested"
            and target_sample_acceptance.get("target_sample_acceptance_ready_for_review") is False
            and target_sample_acceptance.get("provider_backed_acceptance_done") is False
            and target_sample_acceptance.get("production_tushare_pipeline_complete") is False
            and target_sample_acceptance_ready.get("status") == "target_sample_acceptance_ready_for_review"
            and target_sample_acceptance_ready.get("target_sample_acceptance_ready_for_review") is True
            and target_sample_acceptance_ready.get("requested_targets") == ["margin_financing"]
            and target_sample_acceptance_ready.get("ready_target_count") == 1
            and target_sample_acceptance_ready.get("blocking_criterion_count") == 0
            and target_sample_acceptance_ready.get("source_task_tushare_called") is True
            and target_sample_acceptance_ready.get("acceptance_contract_external_calls_triggered") is False
            and target_sample_acceptance_ready.get("provider_backed_target_sample_acceptance_done") is False
            and target_sample_acceptance_ready.get("provider_backed_acceptance_done") is False
            and target_sample_acceptance_ready.get("production_tushare_pipeline_complete") is False
            and target_sample_acceptance_ready.get("full_interface_acceptance_done") is False
            and _flag_false(
                target_sample_acceptance_ready,
                "cache_get_external_calls",
                "react_render_external_calls",
                "deepseek_called",
                "github_called",
            )
            and target_sample_acceptance_ready.get("does_not_execute_trades") is True
            and target_sample_acceptance_ready.get("does_not_modify_strategy_action") is True,
            "Explicit target-sample acceptance may make one target domain review-ready, but the contract itself must not call providers or promote full-interface production acceptance.",
        ),
        _row(
            "target_sample_acceptance_feeds_gap_and_receipt_without_promotion",
            target_sample_gap.get("schema_version") == "tushare_provider_evidence_gap_audit.v1"
            and target_sample_gap.get("target_sample_acceptance_ready_count") == 1
            and target_sample_gap.get("target_sample_acceptance_ready_for_review") is True
            and target_sample_gap_rows["margin_financing"].get("gap_status") == "target_sample_ready_promotion_pending"
            and target_sample_gap_rows["margin_financing"].get("target_sample_acceptance_ready_for_review") is True
            and target_sample_gap_rows["margin_financing"].get("target_sample_review_ready_not_promotion") is True
            and target_sample_gap_rows["margin_financing"].get("gap_blockers") == ["provider_promotion_not_ready"]
            and target_sample_receipt.get("target_sample_acceptance_ready_count") == 1
            and target_sample_receipt.get("target_sample_acceptance_ready_for_review") is True
            and target_sample_receipt_rows["target_sample_acceptance_review_evidence"].get("status")
            == "ready_for_review_not_promotion"
            and target_sample_receipt.get("provider_backed_acceptance_done") is False
            and target_sample_receipt.get("production_tushare_pipeline_complete") is False
            and _flag_false(
                target_sample_gap,
                "cache_get_external_calls",
                "audit_external_calls_triggered",
                "tushare_called_by_audit",
                "deepseek_called",
                "github_called",
            )
            and _flag_false(
                target_sample_receipt,
                "cache_get_external_calls",
                "receipt_external_calls_triggered",
                "tushare_called_by_receipt",
                "deepseek_called",
                "github_called",
            )
            and target_sample_gap.get("does_not_execute_trades") is True
            and target_sample_gap.get("does_not_modify_strategy_action") is True
            and target_sample_receipt.get("does_not_execute_trades") is True
            and target_sample_receipt.get("does_not_modify_strategy_action") is True,
            "Target-sample review evidence must feed the gap ledger and receipt as review-ready only, while provider promotion and production completion remain false.",
        ),
        _row(
            "multi_target_sample_acceptance_feeds_gap_and_receipt_without_promotion",
            multi_target_acceptance.get("schema_version") == "tushare_provider_target_sample_acceptance_contract.v1"
            and multi_target_acceptance.get("status") == "target_sample_acceptance_ready_for_review"
            and multi_target_acceptance.get("requested_targets") == multi_target_groups
            and multi_target_acceptance.get("requested_target_count") == len(multi_target_groups)
            and multi_target_acceptance.get("ready_target_count") == len(multi_target_groups)
            and multi_target_acceptance.get("blocking_criterion_count") == 0
            and multi_target_acceptance.get("target_sample_acceptance_ready_for_review") is True
            and multi_target_acceptance.get("source_task_tushare_called") is True
            and multi_target_acceptance.get("acceptance_contract_external_calls_triggered") is False
            and multi_target_acceptance.get("provider_backed_target_sample_acceptance_done") is False
            and multi_target_acceptance.get("provider_backed_acceptance_done") is False
            and multi_target_acceptance.get("production_tushare_pipeline_complete") is False
            and multi_target_acceptance.get("full_interface_acceptance_done") is False
            and all(
                multi_target_rows[target].get("target_sample_acceptance_status")
                == "target_sample_acceptance_ready_for_review"
                and multi_target_rows[target].get("requested_for_acceptance") is True
                and multi_target_rows[target].get("target_sample_acceptance_blocker_count") == 0
                for target in multi_target_groups
            )
            and multi_target_gap.get("target_sample_acceptance_ready_count") == len(multi_target_groups)
            and multi_target_gap.get("target_sample_acceptance_ready_for_review") is True
            and all(
                multi_target_gap_rows[target].get("gap_status") == "target_sample_ready_promotion_pending"
                and multi_target_gap_rows[target].get("gap_blockers") == ["provider_promotion_not_ready"]
                and multi_target_gap_rows[target].get("target_sample_acceptance_ready_for_review") is True
                and multi_target_gap_rows[target].get("target_sample_review_ready_not_promotion") is True
                and multi_target_gap_rows[target].get("provider_backed_acceptance_done") is False
                and multi_target_gap_rows[target].get("production_tushare_pipeline_complete") is False
                for target in multi_target_groups
            )
            and multi_target_receipt.get("target_sample_acceptance_ready_count") == len(multi_target_groups)
            and multi_target_receipt.get("target_sample_acceptance_ready_for_review") is True
            and multi_target_receipt_rows["target_sample_acceptance_review_evidence"].get("status")
            == "ready_for_review_not_promotion"
            and multi_target_receipt.get("provider_backed_acceptance_done") is False
            and multi_target_receipt.get("production_tushare_pipeline_complete") is False
            and _flag_false(
                multi_target_acceptance,
                "cache_get_external_calls",
                "react_render_external_calls",
                "deepseek_called",
                "github_called",
            )
            and _flag_false(
                multi_target_gap,
                "cache_get_external_calls",
                "audit_external_calls_triggered",
                "tushare_called_by_audit",
                "deepseek_called",
                "github_called",
            )
            and _flag_false(
                multi_target_receipt,
                "cache_get_external_calls",
                "receipt_external_calls_triggered",
                "tushare_called_by_receipt",
                "deepseek_called",
                "github_called",
            )
            and multi_target_acceptance.get("does_not_execute_trades") is True
            and multi_target_acceptance.get("does_not_modify_strategy_action") is True
            and multi_target_gap.get("does_not_execute_trades") is True
            and multi_target_gap.get("does_not_modify_strategy_action") is True
            and multi_target_receipt.get("does_not_execute_trades") is True
            and multi_target_receipt.get("does_not_modify_strategy_action") is True,
            "Multiple target domains can become review-ready from explicit button-task evidence, but gap/receipt rows must keep promotion and production completion pending.",
        ),
        _row(
            "interface_group_scope_complete_but_provider_acceptance_pending",
            [row.get("target") for row in interface_group_scope_rows] == validation_target_group_keys
            and len(interface_group_scope_rows) == len(tushare_task_service.VALIDATION_TARGET_GROUPS)
            and {row.get("target") for row in interface_group_scope_rows if row.get("group_category") == "extended"}
            == set(extended_target_group_keys)
            and interface_group_scope_rows[0].get("target") == "trade_calendar"
            and interface_group_scope_rows[0].get("acceptance_layer") == "provider_backed_trade_cal_long_window"
            and all(row.get("post_task_route") == "POST /api/tasks/refresh-tushare-facts" for row in interface_group_scope_rows)
            and all(row.get("requires_explicit_post_task") is True for row in interface_group_scope_rows)
            and all(row.get("real_provider_sample_still_required") is True for row in interface_group_scope_rows)
            and all(row.get("provider_promotion_still_required") is True for row in interface_group_scope_rows)
            and all(row.get("push_gate_fixture_is_not_real_provider_acceptance") is True for row in interface_group_scope_rows)
            and all(row.get("provider_backed_acceptance_done") is False for row in interface_group_scope_rows)
            and all(row.get("full_interface_acceptance_done") is False for row in interface_group_scope_rows)
            and all(row.get("production_tushare_pipeline_complete") is False for row in interface_group_scope_rows)
            and all(
                row.get("cache_get_external_calls") is False
                and row.get("react_render_external_calls") is False
                and row.get("contract_external_calls_triggered") is False
                and row.get("tushare_called_by_contract") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                for row in interface_group_scope_rows
            )
            and all(row.get("does_not_execute_trades") is True for row in interface_group_scope_rows)
            and all(row.get("does_not_modify_strategy_action") is True for row in interface_group_scope_rows),
            "All LTG-02 interface target groups must be in the explicit acceptance scope, while every group remains pending real provider samples, promotion review, and production acceptance.",
        ),
        _row(
            "provider_readiness_stays_pending",
            provider_readiness.get("schema_version") == "tushare_provider_acceptance_readiness_audit.v1"
            and provider_readiness.get("status") == "provider_acceptance_pending"
            and provider_readiness.get("provider_backed_acceptance_done") is False
            and provider_readiness.get("production_tushare_pipeline_complete") is False
            and provider_readiness.get("full_interface_acceptance_done") is False
            and int(provider_readiness.get("production_blocker_count") or 0) > 0
            and "provider_backed_acceptance_evidence" in readiness_criteria
            and _flag_false(provider_readiness, "cache_get_external_calls", "audit_external_calls_triggered", "deepseek_called", "github_called")
            and provider_readiness.get("does_not_execute_trades") is True
            and provider_readiness.get("does_not_modify_strategy_action") is True,
            "Provider readiness must remain pending until explicit real-provider full-interface samples are proven.",
        ),
        _row(
            "provider_promotion_audit_stays_local_pending",
            provider_promotion.get("schema_version") == "tushare_provider_acceptance_promotion_audit.v1"
            and provider_promotion.get("scope") == "local_call_ledger_promotion_audit_no_provider_execution"
            and provider_promotion.get("status") == "provider_acceptance_promotion_pending"
            and provider_promotion.get("promotion_ready") is False
            and provider_promotion.get("provider_backed_acceptance_done") is False
            and provider_promotion.get("production_tushare_pipeline_complete") is False
            and int(provider_promotion.get("blocking_criterion_count") or 0) > 0
            and _flag_false(
                provider_promotion,
                "cache_get_external_calls",
                "audit_external_calls_triggered",
                "tushare_called_by_audit",
                "deepseek_called",
                "github_called",
            )
            and provider_promotion.get("does_not_execute_trades") is True
            and provider_promotion.get("does_not_modify_strategy_action") is True,
            "Provider promotion audit must stay local/read-only and cannot promote matrix/local QA into provider-backed acceptance.",
        ),
        _row(
            "provider_evidence_gap_audit_is_local_pending",
            provider_evidence_gap.get("schema_version") == "tushare_provider_evidence_gap_audit.v1"
            and provider_evidence_gap.get("scope") == "local_provider_evidence_gap_ledger_no_provider_execution"
            and provider_evidence_gap.get("status") == "provider_evidence_gaps_pending"
            and provider_evidence_gap.get("target_count") == len(tushare_task_service.VALIDATION_TARGET_GROUPS)
            and provider_evidence_gap.get("target_with_gap_count") == provider_evidence_gap.get("target_count")
            and int(provider_evidence_gap.get("gap_blocker_count") or 0) > 0
            and provider_evidence_gap.get("provider_backed_acceptance_done") is False
            and provider_evidence_gap.get("production_tushare_pipeline_complete") is False
            and provider_evidence_gap.get("full_interface_acceptance_done") is False
            and _flag_false(
                provider_evidence_gap,
                "cache_get_external_calls",
                "audit_external_calls_triggered",
                "tushare_called_by_audit",
                "deepseek_called",
                "github_called",
            )
            and provider_evidence_gap.get("does_not_execute_trades") is True
            and provider_evidence_gap.get("does_not_modify_strategy_action") is True
            and all(row.get("gap_status") == "matrix_only_gap_pending" for row in provider_evidence_gap_rows)
            and all(row.get("provider_backed_acceptance_done") is False for row in provider_evidence_gap_rows),
            "Provider evidence gap audit must stay a local target-domain gap ledger and cannot call Tushare or promote acceptance.",
        ),
        _row(
            "provider_sample_readiness_receipt_is_local",
            provider_sample_receipt.get("schema_version") == "tushare_provider_sample_readiness_receipt.v1"
            and provider_sample_receipt.get("scope") == "local_provider_sample_readiness_receipt_no_provider_execution"
            and provider_sample_receipt.get("status")
            in {
                "provider_sample_receipt_ready_execution_pending",
                "provider_sample_receipt_ready_for_promotion_review",
                "provider_sample_receipt_blocked",
            }
            and provider_sample_receipt.get("provider_backed_acceptance_done") is False
            and provider_sample_receipt.get("production_tushare_pipeline_complete") is False
            and provider_sample_receipt.get("full_interface_acceptance_done") is False
            and "GET cache provider refresh" in provider_sample_receipt.get("not_allowed_next_steps", [])
            and _flag_false(
                provider_sample_receipt,
                "cache_get_external_calls",
                "receipt_external_calls_triggered",
                "tushare_called_by_receipt",
                "deepseek_called",
                "github_called",
            )
            and provider_sample_receipt.get("does_not_execute_trades") is True
            and provider_sample_receipt.get("does_not_modify_strategy_action") is True,
            "Provider sample readiness receipt must stay local and only identify the next explicit POST sample step.",
        ),
        _row(
            "provider_sample_activation_receipt_is_local_pending",
            provider_sample_activation.get("schema_version") == "tushare_provider_sample_activation_receipt.v1"
            and provider_sample_activation.get("scope") == "local_provider_sample_activation_receipt_no_provider_execution"
            and provider_sample_activation.get("status")
            in {
                "provider_sample_activation_ready_execution_pending",
                "provider_sample_activation_blocked_local_readiness",
                "provider_sample_activation_blocked_local_contract",
            }
            and provider_sample_activation.get("local_activation_receipt_ready") is True
            and provider_sample_activation.get("allowed_next_step")
            in {"explicit_post_task_target_sample_acceptance", "complete_target_sample_payload_and_selection"}
            and "GET cache provider refresh" in provider_sample_activation.get("not_allowed_next_steps", [])
            and "activation receipt as production Tushare completion"
            in provider_sample_activation.get("not_allowed_next_steps", [])
            and "explicit provider target-sample task execution"
            in provider_sample_activation.get("missing_evidence_items", [])
            and "safe provider call ledger rows for every target domain"
            in provider_sample_activation.get("missing_evidence_items", [])
            and provider_sample_activation.get("provider_acceptance_task_executed_by_receipt") is False
            and provider_sample_activation.get("provider_refresh_called_by_receipt") is False
            and provider_sample_activation.get("cache_get_external_calls") is False
            and provider_sample_activation.get("react_render_external_calls") is False
            and provider_sample_activation.get("production_tushare_pipeline_complete") is False
            and provider_sample_activation.get("full_interface_acceptance_done") is False
            and _flag_false(
                provider_sample_activation,
                "receipt_external_calls_triggered",
                "external_calls_triggered",
                "tushare_called_by_receipt",
                "tushare_called",
                "deepseek_called",
                "github_called",
            )
            and provider_sample_activation.get("does_not_execute_trades") is True
            and provider_sample_activation.get("does_not_modify_strategy_action") is True
            and provider_sample_activation.get("contains_secret") is False,
            "Provider sample activation receipt must stay a local checklist: explicit POST or local blockers remain the next step, provider evidence remains missing, and cache/render paths must not call providers or claim production completion.",
        ),
        _row(
            "provider_target_sample_runbook_is_local_not_acceptance",
            provider_target_sample_runbook.get("schema_version")
            == "tushare_provider_target_sample_runbook_contract.v1"
            and provider_target_sample_runbook.get("scope")
            == "local_target_sample_provider_runbook_no_provider_execution"
            and provider_target_sample_runbook.get("status") == "target_sample_runbook_blocked_or_not_requested"
            and provider_target_sample_runbook.get("runbook_ready") is False
            and provider_target_sample_runbook.get("requested_target_count") == 0
            and provider_target_sample_runbook.get("provider_backed_acceptance_done") is False
            and provider_target_sample_runbook.get("production_tushare_pipeline_complete") is False
            and provider_target_sample_runbook.get("full_interface_acceptance_done") is False
            and "runbook as provider-backed acceptance"
            in provider_target_sample_runbook.get("not_allowed_next_steps", [])
            and _flag_false(
                provider_target_sample_runbook,
                "cache_get_external_calls",
                "react_render_external_calls",
                "runbook_external_calls_triggered",
                "tushare_called_by_runbook",
                "deepseek_called",
                "github_called",
            )
            and provider_target_sample_runbook.get("does_not_execute_trades") is True
            and provider_target_sample_runbook.get("does_not_modify_strategy_action") is True,
            "Target-sample runbook must stay local/no-provider and cannot be treated as provider-backed acceptance.",
        ),
        _row(
            "target_sample_runbook_ready_review_pending_without_promotion",
            target_sample_runbook.get("status") == "target_sample_runbook_ready_provider_review_pending"
            and target_sample_runbook.get("runbook_ready") is True
            and target_sample_runbook.get("requested_targets") == ["margin_financing"]
            and target_sample_runbook.get("runbook_ready_target_count") == 1
            and target_sample_runbook_rows["margin_financing"].get("runbook_status")
            == "target_sample_runbook_ready_provider_review_pending"
            and target_sample_runbook_rows["margin_financing"].get("post_task_route")
            == "POST /api/tasks/refresh-tushare-facts"
            and target_sample_runbook_rows["margin_financing"].get("required_acceptance_mode")
            == "provider_target_sample_acceptance"
            and target_sample_runbook_rows["margin_financing"].get("provider_promotion_blockers")
            == ["provider_promotion_not_ready"]
            and target_sample_runbook.get("provider_backed_acceptance_done") is False
            and target_sample_runbook.get("production_tushare_pipeline_complete") is False
            and target_sample_runbook.get("full_interface_acceptance_done") is False
            and _flag_false(
                target_sample_runbook,
                "cache_get_external_calls",
                "react_render_external_calls",
                "runbook_external_calls_triggered",
                "tushare_called_by_runbook",
                "deepseek_called",
                "github_called",
            ),
            "A ready target-sample runbook only prepares review/promotion evidence; it must not call providers or promote acceptance.",
        ),
        _row(
            "multi_target_sample_runbook_ready_review_pending_without_promotion",
            multi_target_runbook.get("status") == "target_sample_runbook_ready_provider_review_pending"
            and multi_target_runbook.get("runbook_ready") is True
            and multi_target_runbook.get("requested_targets") == multi_target_groups
            and multi_target_runbook.get("runbook_ready_target_count") == len(multi_target_groups)
            and multi_target_runbook.get("blocked_runbook_target_count") == 0
            and all(
                multi_target_runbook_rows[target].get("runbook_status")
                == "target_sample_runbook_ready_provider_review_pending"
                and multi_target_runbook_rows[target].get("post_task_route")
                == "POST /api/tasks/refresh-tushare-facts"
                and multi_target_runbook_rows[target].get("required_acceptance_mode")
                == "provider_target_sample_acceptance"
                and multi_target_runbook_rows[target].get("provider_promotion_blockers")
                == ["provider_promotion_not_ready"]
                and multi_target_runbook_rows[target].get("provider_backed_acceptance_done") is False
                and multi_target_runbook_rows[target].get("production_tushare_pipeline_complete") is False
                for target in multi_target_groups
            )
            and multi_target_runbook.get("provider_backed_acceptance_done") is False
            and multi_target_runbook.get("production_tushare_pipeline_complete") is False
            and multi_target_runbook.get("full_interface_acceptance_done") is False
            and _flag_false(
                multi_target_runbook,
                "cache_get_external_calls",
                "react_render_external_calls",
                "runbook_external_calls_triggered",
                "tushare_called_by_runbook",
                "deepseek_called",
                "github_called",
            )
            and multi_target_runbook.get("does_not_execute_trades") is True
            and multi_target_runbook.get("does_not_modify_strategy_action") is True,
            "Multi-target runbook readiness is a local review checklist only; provider promotion and production completion remain false.",
        ),
        _row(
            "target_groups_matrix_only",
            len(target_matrix_only_rows) == len(tushare_task_service.VALIDATION_TARGET_GROUPS)
            and all(row.get("does_not_claim_unselected_apis_verified") is True for row in target_matrix_only_rows)
            and all(row.get("button_gated_external_calls_only") is True for row in target_matrix_only_rows),
            "Validation target groups must show matrix-only status until selected APIs produce ledger evidence.",
        ),
        _row(
            "push_gate_runs_contract_before_static_qa",
            "scripts/tushare_acceptance_contract.py" in push_gate_script
            and "Tushare acceptance contract" in push_gate_script
            and "tushare_acceptance_contract: passed_local_contract_provider_execution_pending" in push_gate_script
            and push_gate_script.find('run_step "Data Health freshness contract"') < push_gate_script.find('run_step "Tushare acceptance contract"')
            and push_gate_script.find('run_step "Tushare acceptance contract"') < push_gate_script.find('run_step "Motion viewport QA contract"'),
            "Push gate must run the LTG-02 local contract after Data Health and before motion/static QA.",
        ),
        _row(
            "script_is_local_no_provider_execution",
            "command_center_3_tushare_acceptance_contract.v1" in this_script
            and "local_matrix_and_readiness_contract_no_provider_execution" in this_script
            and "provider_backed_acceptance_done" in this_script
            and "production_tushare_pipeline_complete" in this_script
            and "does_not_execute_trades" in this_script
            and ("request" + "s") not in this_script
            and ("ht" + "tpx") not in this_script
            and ("api.github" + ".com") not in this_script
            and ("tushare" + "_adapter") not in this_script,
            "The push-gate contract script must stay local/static and must not import provider clients.",
        ),
    ]
    blockers = [row["criterion"] for row in rows if not row["passed"]]
    return {
        "schema_version": "command_center_3_tushare_acceptance_contract.v1",
        "status": "tushare_acceptance_contract_passed" if not blockers else "tushare_acceptance_contract_blocked",
        "scope": "local_matrix_and_readiness_contract_no_provider_execution",
        "ltg": "LTG-02/LTG-11",
        "contract_ready": not blockers,
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "full_interface_acceptance_done": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "api_count": api_count,
        "core_api_count": len(core_apis),
        "calendar_api_count": len(calendar_apis),
        "extended_api_count": len(extended_apis),
        "parquet_enabled_api_count": len(parquet_apis),
        "matrix_only_api_count": len(matrix_only_rows),
        "target_group_count": len(validation_target_rows),
        "matrix_only_target_count": len(target_matrix_only_rows),
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "contract_keys": CONTRACT_KEYS,
        "rows": rows,
        "interface_group_scope_rows": interface_group_scope_rows,
        "observed": {
            "refresh_task_route": refresh_catalog.get("route"),
            "default_core_apis": core_apis,
            "calendar_apis": calendar_apis,
            "extended_api_count": len(extended_apis),
            "parquet_enabled_apis": parquet_apis,
            "provider_readiness_status": provider_readiness.get("status"),
            "provider_readiness_blocker_count": provider_readiness.get("production_blocker_count"),
            "provider_promotion_status": provider_promotion.get("status"),
            "provider_promotion_blocker_count": provider_promotion.get("blocking_criterion_count"),
            "provider_evidence_gap_status": provider_evidence_gap.get("status"),
            "provider_evidence_gap_target_with_gap_count": provider_evidence_gap.get("target_with_gap_count"),
            "provider_evidence_gap_blocker_count": provider_evidence_gap.get("gap_blocker_count"),
            "provider_sample_readiness_status": provider_sample_receipt.get("status"),
            "provider_sample_ready_for_explicit_task": provider_sample_receipt.get(
                "ready_for_explicit_provider_sample_task"
            ),
            "provider_sample_readiness_blocker_count": provider_sample_receipt.get("blocked_readiness_count"),
            "provider_sample_activation_status": provider_sample_activation.get("status"),
            "provider_sample_activation_ready_for_explicit_task": provider_sample_activation.get(
                "ready_for_explicit_provider_sample_task"
            ),
            "provider_sample_activation_blocker_count": provider_sample_activation.get("blocking_criterion_count"),
            "provider_target_sample_runbook_status": provider_target_sample_runbook.get("status"),
            "provider_target_sample_runbook_ready": provider_target_sample_runbook.get("runbook_ready"),
            "multi_target_sample_runbook_status": multi_target_runbook.get("status"),
            "multi_target_sample_runbook_ready_count": multi_target_runbook.get("runbook_ready_target_count"),
            "target_sample_plan_ready_count": target_sample_plan.get("ready_to_execute_target_count"),
            "target_sample_plan_pending_count": target_sample_plan.get("pending_or_blocked_target_count"),
            "trade_cal_acceptance_mode": trade_cal_full_acceptance.get("acceptance_mode"),
            "trade_cal_acceptance_window_days": trade_cal_full_acceptance.get("window_days"),
            "trade_cal_acceptance_done_when_replay_and_failure_evidence_present": trade_cal_full_acceptance.get(
                "provider_backed_long_window_acceptance_done"
            ),
            "multi_target_sample_acceptance_requested_count": multi_target_acceptance.get("requested_target_count"),
            "multi_target_sample_acceptance_ready_count": multi_target_acceptance.get("ready_target_count"),
            "multi_target_sample_acceptance_targets": multi_target_acceptance.get("requested_targets"),
            "multi_target_sample_acceptance_status": multi_target_acceptance.get("status"),
            "validation_target_groups": validation_target_group_keys,
            "extended_target_groups": extended_target_group_keys,
            "interface_group_scope_count": len(interface_group_scope_rows),
            "interface_group_review_fixture_ready_count": len(
                [row for row in interface_group_scope_rows if row.get("push_gate_review_fixture_ready") is True]
            ),
            "interface_group_real_provider_sample_pending_count": len(
                [row for row in interface_group_scope_rows if row.get("real_provider_sample_still_required") is True]
            ),
        },
        "note": "This is a local push-gate contract. Real Tushare samples remain pending until a future explicit POST task/provider acceptance run.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LTG-02 Tushare acceptance contracts.")
    parser.add_argument("--json", action="store_true", help="Print the full contract as JSON.")
    args = parser.parse_args()

    contract = build_contract()
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"tushare_acceptance_contract: {contract['status']}")
        print(
            "rows: {row_count}; blockers: {blocking_criterion_count}; "
            "provider_backed_acceptance_done: false; production_tushare_pipeline_complete: false".format(
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
