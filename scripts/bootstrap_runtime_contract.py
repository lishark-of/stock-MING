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

from config import (  # noqa: E402
    COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE,
    COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE,
    COMMAND_CENTER_DEFAULT_RUNTIME_MODE,
    COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES,
    COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES,
    COMMAND_CENTER_RUNTIME_CONFIG_NAMES,
    COMMAND_CENTER_RUNTIME_MODES,
)
from server.services import bootstrap_service, task_service  # noqa: E402


ENV_KEYS = (
    *COMMAND_CENTER_RUNTIME_CONFIG_NAMES,
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


def _safe_config_rows() -> list[dict[str, Any]]:
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="token=DROP_MODE_TOKEN",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="maybe",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="maybe",
        COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART="maybe",
        COMMAND_CENTER_LIVE_STARTUP_AUTOSTART="maybe",
        COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="Bearer DROP_PROFILE_SECRET",
        COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE="Bearer DROP_SCOPE_SECRET",
        COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT="maybe",
        COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT="maybe",
        COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT="9999",
        COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS="1",
        COMMAND_CENTER_LIVE_DEEPSEEK_MODEL="Bearer DROP_MODEL_SECRET",
        COMMAND_CENTER_LIVE_ALLOW_FULL_POOL="maybe",
    )
    task_service.clear_task_statuses_for_tests(clear_persisted=True)
    status = bootstrap_service.read_bootstrap_status_cache()
    config_rows = {
        str(row.get("config") or ""): row
        for row in _list(status.get("config_rows"))
        if isinstance(row, dict)
    }
    safe_config = _dict(status.get("safe_config_contract"))
    status_text = _serialized(status)
    mode_row = config_rows.get("COMMAND_CENTER_BOOTSTRAP_MODE", {})
    model_row = config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_MODEL", {})
    search_submit_row = config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {})
    startup_autostart_row = config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {})
    external_execution_profile_row = config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {})
    live_light_research_scope_row = config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {})
    provider_model_enablement_row = config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {})
    frontend_enablement_row = config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {})
    symbol_limit_row = config_rows.get("COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT", {})
    rate_limit_row = config_rows.get("COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS", {})
    full_pool_row = config_rows.get("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL", {})
    return [
        _row(
            "safe_config_contract_redacts_invalid_secret_like_values",
            status.get("mode") == "cache_only"
            and status.get("status") == "invalid_mode_defaulted_to_cache_only"
            and status.get("configured_mode_raw") == "[invalid_redacted]"
            and status.get("configured_mode_raw_safe") == "[invalid_redacted]"
            and status.get("configured_mode_valid") is False
            and status.get("configured_mode_invalid_raw_redacted") is True
            and safe_config.get("schema_version") == "command_center_bootstrap_safe_config_contract.v1"
            and safe_config.get("status") == "safe_config_visible_invalid_values_redacted"
            and safe_config.get("runtime_mode_config_contract_visible") is True
            and safe_config.get("runtime_mode_config_evidence_factory_rule")
            == "runtime_vocabulary_safe_config_rows_and_post_task_boundary_only_not_execution"
            and safe_config.get("runtime_mode_config_current_acceptance_scope")
            == "runtime_mode_vocabulary_config_rows_and_contract_tests_only"
            and safe_config.get("runtime_mode_config_current_acceptance_rule")
            == "docs_config_contract_evidence_only_not_live_light_implementation"
            and safe_config.get("runtime_mode_config_current_acceptance_excludes")
            == [
                "frontend_autostart_wiring",
                "provider_model_executor",
                "worker_dispatch",
                "cache_write_promotion",
                "production_acceptance",
            ]
            and safe_config.get("runtime_mode_vocab_source") == "config.COMMAND_CENTER_RUNTIME_MODES"
            and safe_config.get("allowed_modes") == list(COMMAND_CENTER_RUNTIME_MODES)
            and safe_config.get("default_mode_source") == "config.COMMAND_CENTER_DEFAULT_RUNTIME_MODE"
            and safe_config.get("default_mode") == COMMAND_CENTER_DEFAULT_RUNTIME_MODE
            and safe_config.get("mode_raw_value_safe") == "[invalid_redacted]"
            and safe_config.get("mode_raw_invalid_value_redacted") is True
            and safe_config.get("invalid_mode_defaults_to_cache_only") is True
            and safe_config.get("raw_config_values_exposed") is False
            and safe_config.get("secret_like_model_value_redacted") is True
            and safe_config.get("configured_source_switches_visible") is True
            and safe_config.get("effective_source_switches_mode_gated") is True
            and safe_config.get("effective_tushare_on_open") is False
            and safe_config.get("effective_deepseek_on_open") is False
            and safe_config.get("configured_search_submit_autostart") is False
            and safe_config.get("effective_search_submit_autostart") is False
            and safe_config.get("search_submit_autostart_requires_live_light") is True
            and safe_config.get("search_submit_autostart_creates_local_projection_task_only") is True
            and safe_config.get("search_submit_autostart_calls_provider_model") is False
            and safe_config.get("configured_startup_autostart") is False
            and safe_config.get("effective_startup_autostart") is False
            and safe_config.get("startup_autostart_requires_live_light") is True
            and safe_config.get("startup_autostart_requires_sources_enabled") is True
            and safe_config.get("startup_autostart_creates_local_task_only") is True
            and safe_config.get("startup_autostart_calls_provider_model") is False
            and safe_config.get("configured_external_execution_profile") == "plan_only"
            and safe_config.get("effective_external_execution_profile") == "plan_only"
            and safe_config.get("external_execution_profile_vocab_source")
            == "config.COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES"
            and safe_config.get("external_execution_profile_default_source")
            == "config.COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE"
            and safe_config.get("external_execution_profile_valid") is False
            and safe_config.get("external_execution_profile_invalid_value_redacted") is True
            and safe_config.get("external_execution_profile_provider_stage_allowed") is False
            and safe_config.get("external_execution_profile_model_stage_allowed") is False
            and safe_config.get("external_execution_profile_executor_implemented") is False
            and safe_config.get("external_execution_profile_calls_provider_model_now") is False
            and safe_config.get("external_execution_profile_requires_post_task_worker_or_local_fallback") is True
            and safe_config.get("external_execution_profile_requires_call_ledger") is True
            and safe_config.get("external_execution_profile_requires_model_ledger_for_deepseek") is False
            and safe_config.get("configured_live_light_research_scope") == COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE
            and safe_config.get("effective_live_light_research_scope") == "bootstrap_only"
            and safe_config.get("live_light_research_scope_vocab_source")
            == "config.COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES"
            and safe_config.get("live_light_research_scope_default_source")
            == "config.COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE"
            and safe_config.get("live_light_research_scope_valid") is False
            and safe_config.get("live_light_research_scope_invalid_value_redacted") is True
            and safe_config.get("live_light_research_scope_requires_live_light") is True
            and safe_config.get("live_light_research_scope_requires_sources_enabled") is True
            and safe_config.get("live_light_research_scope_provider_stage_allowed") is False
            and safe_config.get("live_light_research_scope_factor_light_allowed") is False
            and safe_config.get("live_light_research_scope_next_session_cache_allowed") is False
            and safe_config.get("live_light_research_scope_model_stage_allowed") is False
            and safe_config.get("live_light_research_scope_creates_task") is False
            and safe_config.get("live_light_research_scope_creates_provider_model_task") is False
            and safe_config.get("live_light_research_scope_calls_provider_model_now") is False
            and safe_config.get("live_light_research_scope_local_compute_executes_now") is False
            and safe_config.get("live_light_research_scope_is_production_evidence") is False
            and safe_config.get("configured_provider_model_enablement") is False
            and safe_config.get("effective_provider_model_enablement") is False
            and safe_config.get("provider_model_enablement_requires_live_light") is True
            and safe_config.get("provider_model_enablement_requires_execution_request") is True
            and safe_config.get("provider_model_enablement_requires_promotion") is True
            and safe_config.get("provider_model_enablement_creates_task") is False
            and safe_config.get("provider_model_enablement_creates_provider_model_task") is False
            and safe_config.get("provider_model_enablement_calls_provider_model_now") is False
            and safe_config.get("provider_model_enablement_frontend_writeback_allowed") is False
            and safe_config.get("configured_frontend_enablement") is False
            and safe_config.get("effective_frontend_enablement") is False
            and safe_config.get("frontend_enablement_requires_live_light") is True
            and safe_config.get("frontend_enablement_requires_promotion") is True
            and safe_config.get("frontend_enablement_creates_task") is False
            and safe_config.get("frontend_enablement_frontend_writeback_allowed") is False
            and safe_config.get("effective_sources_enabled") is False
            and safe_config.get("source_switch_mode_gate") == "live_light"
            and safe_config.get("manual_or_cache_only_switches_do_not_autostart") is True
            and safe_config.get("non_live_light_switches_do_not_autostart") is True
            and safe_config.get("token_key_exposure_allowed") is False
            and safe_config.get("external_calls_triggered") is False
            and safe_config.get("tushare_called") is False
            and safe_config.get("deepseek_called") is False
            and safe_config.get("github_called") is False
            and "DROP_MODE_TOKEN" not in status_text
            and "DROP_MODEL_SECRET" not in status_text
            and "DROP_PROFILE_SECRET" not in status_text
            and "DROP_SCOPE_SECRET" not in status_text,
            f"safe_config={safe_config}",
        ),
        _row(
            "safe_config_rows_show_defaults_clamps_without_raw_value_exposure",
            mode_row.get("value_safe") == "cache_only"
            and mode_row.get("raw_value_safe") == "[invalid_redacted]"
            and mode_row.get("raw_value_valid") is False
            and mode_row.get("raw_value_exposed") is False
            and mode_row.get("raw_value_safe_visible") is True
            and mode_row.get("fallback_value_safe") == "cache_only"
            and mode_row.get("source") == "configured_invalid_defaulted"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("source") == "invalid_defaulted"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("automation_effective") is False
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("source") == "invalid_defaulted"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("automation_effective") is False
            and search_submit_row.get("source") == "invalid_defaulted"
            and search_submit_row.get("value_safe") is False
            and search_submit_row.get("effective_value_safe") is False
            and search_submit_row.get("automation_effective") is False
            and search_submit_row.get("creates_provider_model_task") is False
            and startup_autostart_row.get("source") == "invalid_defaulted"
            and startup_autostart_row.get("value_safe") is False
            and startup_autostart_row.get("configured_value_safe") is False
            and startup_autostart_row.get("effective_value_safe") is False
            and startup_autostart_row.get("automation_effective") is False
            and startup_autostart_row.get("mode_gate") == "live_light_after_cache_render_and_sources_enabled"
            and startup_autostart_row.get("effective_status") == "cache_only_startup_autostart_disabled"
            and startup_autostart_row.get("inactive_reason") == "cache_only_read_only"
            and startup_autostart_row.get("creates_local_background_task_only") is False
            and startup_autostart_row.get("creates_provider_model_task") is False
            and external_execution_profile_row.get("source") == "invalid_defaulted"
            and external_execution_profile_row.get("allowed_values")
            == list(COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES)
            and external_execution_profile_row.get("default_value_safe")
            == COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE
            and external_execution_profile_row.get("value_safe") == COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE
            and external_execution_profile_row.get("configured_value_safe")
            == COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE
            and external_execution_profile_row.get("effective_value_safe")
            == COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE
            and external_execution_profile_row.get("raw_value_safe") == "[redacted_sensitive_text]"
            and external_execution_profile_row.get("raw_value_valid") is False
            and external_execution_profile_row.get("raw_invalid_value_redacted") is True
            and external_execution_profile_row.get("effective_status")
            == "cache_only_external_execution_profile_disabled"
            and external_execution_profile_row.get("inactive_reason") == "cache_only_read_only"
            and external_execution_profile_row.get("provider_stage_allowed_by_profile") is False
            and external_execution_profile_row.get("model_stage_allowed_by_profile") is False
            and external_execution_profile_row.get("creates_provider_model_task") is False
            and external_execution_profile_row.get("calls_provider_model_now") is False
            and live_light_research_scope_row.get("source") == "invalid_defaulted"
            and live_light_research_scope_row.get("allowed_values")
            == list(COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES)
            and live_light_research_scope_row.get("default_value_safe")
            == COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE
            and live_light_research_scope_row.get("value_safe")
            == COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE
            and live_light_research_scope_row.get("configured_value_safe")
            == COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE
            and live_light_research_scope_row.get("effective_value_safe") == "bootstrap_only"
            and live_light_research_scope_row.get("raw_value_safe") == "[redacted_sensitive_text]"
            and live_light_research_scope_row.get("raw_value_valid") is False
            and live_light_research_scope_row.get("raw_invalid_value_redacted") is True
            and live_light_research_scope_row.get("effective_status")
            == "cache_only_live_light_research_scope_disabled"
            and live_light_research_scope_row.get("inactive_reason") == "cache_only_read_only"
            and live_light_research_scope_row.get("provider_stage_allowed_by_scope") is False
            and live_light_research_scope_row.get("factor_light_allowed_by_scope") is False
            and live_light_research_scope_row.get("next_session_cache_allowed_by_scope") is False
            and live_light_research_scope_row.get("model_stage_allowed_by_scope") is False
            and live_light_research_scope_row.get("creates_task") is False
            and live_light_research_scope_row.get("creates_provider_model_task") is False
            and live_light_research_scope_row.get("calls_provider_model_now") is False
            and provider_model_enablement_row.get("source") == "invalid_defaulted"
            and provider_model_enablement_row.get("value_safe") is False
            and provider_model_enablement_row.get("effective_value_safe") is False
            and provider_model_enablement_row.get("automation_effective") is False
            and provider_model_enablement_row.get("mode_gate") == "live_light_and_provider_model_promotion"
            and provider_model_enablement_row.get("provider_model_task_creation_allowed") is False
            and provider_model_enablement_row.get("creates_task") is False
            and provider_model_enablement_row.get("creates_provider_model_task") is False
            and provider_model_enablement_row.get("calls_provider_model_now") is False
            and provider_model_enablement_row.get("frontend_writeback_allowed") is False
            and frontend_enablement_row.get("source") == "invalid_defaulted"
            and frontend_enablement_row.get("value_safe") is False
            and frontend_enablement_row.get("effective_value_safe") is False
            and frontend_enablement_row.get("automation_effective") is False
            and frontend_enablement_row.get("mode_gate") == "live_light_and_frontend_enablement_promotion"
            and frontend_enablement_row.get("effective_status") == "cache_only_frontend_enablement_disabled"
            and frontend_enablement_row.get("inactive_reason") == "cache_only_read_only"
            and frontend_enablement_row.get("frontend_enablement_allowed") is False
            and frontend_enablement_row.get("frontend_writeback_allowed") is False
            and frontend_enablement_row.get("creates_task") is False
            and symbol_limit_row.get("source") == "clamped_max"
            and symbol_limit_row.get("value_safe") == 200
            and rate_limit_row.get("source") == "clamped_min"
            and rate_limit_row.get("value_safe") == 60
            and model_row.get("value_safe") == "[redacted_sensitive_text]"
            and model_row.get("secret_like_raw_redacted") is True
            and model_row.get("raw_value_exposed") is False
            and full_pool_row.get("source") == "invalid_defaulted"
            and full_pool_row.get("value_safe") is False
            and full_pool_row.get("effective_value_safe") is False
            and full_pool_row.get("live_full_reserved") is True
            and all(row.get("contains_secret") is False for row in config_rows.values()),
            f"config_rows={config_rows}",
        ),
    ]


def _cache_only_rows() -> list[dict[str, Any]]:
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="cache_only",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="true",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="true",
        COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART="true",
        COMMAND_CENTER_LIVE_STARTUP_AUTOSTART="true",
        COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="light_provider_model",
        COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE="provider_factor_next_model",
        COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT="true",
        COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT="true",
    )
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
    ledger = _ledger(task)
    first_ledger = ledger[0] if ledger else {}
    payload_safe = _dict(task.get("payload_safe"))
    local_compute_handoff = _dict(payload_safe.get("bootstrap_local_compute_handoff_summary"))
    local_compute_handoff_rows = [
        row for row in _list(payload_safe.get("bootstrap_local_compute_handoff_rows")) if isinstance(row, dict)
    ]
    task_text = _serialized(task)
    config_rows = {
        str(row.get("config") or ""): row
        for row in _list(status.get("config_rows"))
        if isinstance(row, dict)
    }
    mode_rows = {
        str(row.get("mode") or ""): row
        for row in _list(status.get("mode_rows"))
        if isinstance(row, dict)
    }
    safe_config = _dict(status.get("safe_config_contract"))
    submit_contract = _dict(status.get("search_quant_projection_submit_autostart_contract"))
    provider_linkage = {
        str(row.get("linkage_key") or ""): row
        for row in _list(status.get("provider_linkage_rows"))
        if isinstance(row, dict)
    }
    activation = _dict(status.get("live_light_activation_receipt"))
    activation_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(status.get("live_light_activation_rows"))
        if isinstance(row, dict)
    }
    runbook = _dict(status.get("live_light_provider_model_acceptance_runbook"))
    acceptance_rows = {
        str(row.get("phase_key") or ""): row
        for row in _list(status.get("live_light_provider_model_acceptance_rows"))
        if isinstance(row, dict)
    }
    return [
        _row(
            "cache_only_status_is_offline_default",
            status.get("mode") == "cache_only"
            and _dict(status.get("policy")).get("cache_api_external_calls") is False
            and _dict(status.get("policy")).get("cache_only_switches_do_not_autostart") is True
            and _dict(status.get("policy")).get("react_initial_render_external_calls") is False
            and status.get("tushare_called") is False
            and status.get("deepseek_called") is False
            and status.get("github_called") is False,
            f"mode={status.get('mode')} status={status.get('status')}",
        ),
        _row(
            "cache_only_mode_trigger_matrix_is_quiet",
            mode_rows.get("cache_only", {}).get("trigger_matrix_schema_version")
            == "command_center_bootstrap_mode_trigger_matrix.v1"
            and mode_rows.get("cache_only", {}).get("page_open_task_allowed") is False
            and mode_rows.get("cache_only", {}).get("page_open_task_policy") == "disabled_cache_only"
            and mode_rows.get("cache_only", {}).get("react_initial_render_creates_task") is False
            and mode_rows.get("cache_only", {}).get("react_mounted_task_allowed_after_cache_render") is False
            and mode_rows.get("cache_only", {}).get("search_input_auto_task_allowed") is False
            and mode_rows.get("cache_only", {}).get("search_input_task_policy") == "never_on_typing"
            and mode_rows.get("cache_only", {}).get("search_action_task_allowed") is False
            and mode_rows.get("cache_only", {}).get("search_action_task_policy") == "disabled_cache_only"
            and mode_rows.get("cache_only", {}).get("provider_model_execution_without_execution_request_allowed")
            is False
            and mode_rows.get("cache_only", {}).get("real_trading_task_allowed") is False,
            f"cache_only_mode_row={mode_rows.get('cache_only')}",
        ),
        _row(
            "safe_config_rows_are_frontend_display_only",
            len(config_rows) == 13
            and safe_config.get("config_rows_frontend_visible") is True
            and safe_config.get("config_rows_frontend_display_policy") == "safe_value_only"
            and safe_config.get("config_rows_frontend_editable") is False
            and safe_config.get("config_rows_frontend_writeback_allowed") is False
            and safe_config.get("status_endpoint_writeback_allowed") is False
            and safe_config.get("config_source_of_truth") == "server_config_layer"
            and safe_config.get("config_change_channel") == "server_config_layer_only"
            and safe_config.get("config_rows_are_operator_guidance_not_controls") is True
            and all(row.get("config_source_of_truth") == "server_config_layer" for row in config_rows.values())
            and all(row.get("frontend_visible") is True for row in config_rows.values())
            and all(row.get("frontend_display_policy") == "safe_value_only" for row in config_rows.values())
            and all(row.get("frontend_editable") is False for row in config_rows.values())
            and all(row.get("frontend_writeback_allowed") is False for row in config_rows.values())
            and all(row.get("status_endpoint_writeback_allowed") is False for row in config_rows.values())
            and all(row.get("operator_change_channel") == "server_config_layer_only" for row in config_rows.values()),
            f"config_rows={config_rows} safe_config={safe_config}",
        ),
        _row(
            "cache_only_source_switches_are_configured_but_never_effective",
            config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("configured_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("configured_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "configured_value_safe"
            )
            == "light_provider_model"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("effective_value_safe")
            == "plan_only"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_status")
            == "cache_only_source_switch_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_status")
            == "cache_only_source_switch_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("effective_status")
            == "cache_only_submit_autostart_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("effective_status")
            == "cache_only_startup_autostart_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("effective_status")
            == "cache_only_external_execution_profile_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_status")
            == "cache_only_frontend_enablement_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("automation_effective") is False
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("automation_effective") is False
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("inactive_reason")
            == "cache_only_read_only"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("inactive_reason")
            == "cache_only_read_only"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("inactive_reason")
            == "cache_only_read_only"
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("inactive_reason")
            == "cache_only_read_only"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("inactive_reason")
            == "cache_only_read_only"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("inactive_reason")
            == "cache_only_read_only"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("creates_provider_model_task")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "creates_local_background_task_only"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("creates_provider_model_task")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "provider_stage_allowed_by_profile"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "model_stage_allowed_by_profile"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "calls_provider_model_now"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "configured_value_safe"
            )
            == "provider_factor_next_model"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("effective_value_safe")
            == "bootstrap_only"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("effective_status")
            == "cache_only_live_light_research_scope_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("inactive_reason")
            == "cache_only_read_only"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "provider_stage_allowed_by_scope"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "factor_light_allowed_by_scope"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "next_session_cache_allowed_by_scope"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("model_stage_allowed_by_scope")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("creates_task") is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "creates_provider_model_task"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("calls_provider_model_now")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("effective_status")
            == "cache_only_provider_model_enablement_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("inactive_reason")
            == "cache_only_read_only"
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "provider_model_task_creation_allowed"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "creates_provider_model_task"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "calls_provider_model_now"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("creates_task") is False
            and safe_config.get("configured_frontend_enablement") is True
            and safe_config.get("effective_frontend_enablement") is False
            and safe_config.get("frontend_enablement_creates_task") is False
            and safe_config.get("configured_search_submit_autostart") is True
            and safe_config.get("effective_search_submit_autostart") is False
            and safe_config.get("configured_startup_autostart") is True
            and safe_config.get("effective_startup_autostart") is False
            and safe_config.get("startup_autostart_creates_local_task_only") is True
            and safe_config.get("startup_autostart_calls_provider_model") is False
            and safe_config.get("configured_external_execution_profile") == "light_provider_model"
            and safe_config.get("effective_external_execution_profile") == "plan_only"
            and safe_config.get("external_execution_profile_provider_stage_allowed") is False
            and safe_config.get("external_execution_profile_model_stage_allowed") is False
            and safe_config.get("external_execution_profile_executor_implemented") is False
            and safe_config.get("external_execution_profile_calls_provider_model_now") is False
            and safe_config.get("cache_only_switches_do_not_autostart") is True
            and safe_config.get("non_live_light_switches_do_not_autostart") is True
            and safe_config.get("effective_tushare_on_open") is False
            and safe_config.get("effective_deepseek_on_open") is False
            and safe_config.get("effective_sources_enabled") is False
            and safe_config.get("cache_get_creates_task") is False
            and safe_config.get("cache_get_external_calls") is False,
            f"config_rows={config_rows} safe_config={safe_config}",
        ),
        _row(
            "cache_only_search_submit_autostart_stays_read_only_disabled",
            submit_contract.get("schema_version")
            == "command_center_search_quant_projection_submit_autostart_contract.v1"
            and submit_contract.get("status") == "cache_only_submit_autostart_disabled"
            and submit_contract.get("mode") == "cache_only"
            and submit_contract.get("configured_submit_autostart") is True
            and submit_contract.get("effective_submit_autostart") is False
            and submit_contract.get("autostart_readiness_stage") == "cache_only_read_only_no_submit_task"
            and submit_contract.get("inactive_reason") == "cache_only_read_only"
            and submit_contract.get("active_mode_submit_autostart_allowed") is False
            and submit_contract.get("search_submit_task_creation_allowed_in_active_mode") is False
            and submit_contract.get("cache_only_search_submit_auto_start_allowed") is False
            and submit_contract.get("cache_only_read_only") is True
            and submit_contract.get("cache_only_blocks_local_projection_task") is True
            and submit_contract.get("configured_true_but_cache_only_mode") is True
            and submit_contract.get("search_typing_creates_task") is False
            and submit_contract.get("react_render_creates_task") is False
            and submit_contract.get("cache_get_creates_task") is False
            and submit_contract.get("fastapi_startup_creates_task") is False
            and submit_contract.get("latest_status_replay_lookup_creates_task") is False
            and submit_contract.get("current_submit_autostart_calls_provider_model") is False
            and submit_contract.get("provider_model_autostart_without_execution_request_allowed") is False
            and submit_contract.get("external_calls_triggered") is False
            and submit_contract.get("tushare_called") is False
            and submit_contract.get("deepseek_called") is False
            and submit_contract.get("github_called") is False
            and submit_contract.get("does_not_execute_trades") is True
            and submit_contract.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_allowed") is False
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_allowed") is False
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_configured") is True
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_effective") is False,
            f"submit_contract={submit_contract}",
        ),
        _row(
            "cache_only_task_skips_provider_execution",
            task.get("current_step") == "live_bootstrap_skipped_mode_not_live_light"
            and payload_safe.get("tushare_on_open") is False
            and payload_safe.get("deepseek_on_open") is False
            and payload_safe.get("sources_enabled") is False
            and summary.get("external_calls_triggered") is False
            and summary.get("planned_provider_stage_count") == 0
            and summary.get("planned_model_stage_count") == 0,
            f"current_step={task.get('current_step')} summary={summary}",
        ),
        _row(
            "cache_only_local_compute_handoff_mode_gated",
            summary.get("local_compute_handoff_row_count") == 3
            and summary.get("local_compute_handoff_enabled_row_count") == 0
            and summary.get("local_compute_handoff_executed_row_count") == 0
            and local_compute_handoff.get("schema_version")
            == "command_center_live_bootstrap_local_compute_handoff.v1"
            and local_compute_handoff.get("status") == "local_compute_handoff_inactive_cache_only_read_only"
            and local_compute_handoff.get("mode") == "cache_only"
            and local_compute_handoff.get("mode_gate") == "live_light"
            and local_compute_handoff.get("mode_gate_satisfied") is False
            and local_compute_handoff.get("source_switch_satisfied") is False
            and local_compute_handoff.get("inactive_reason") == "cache_only_read_only"
            and local_compute_handoff.get("handoff_row_count") == 3
            and local_compute_handoff.get("enabled_handoff_row_count") == 0
            and local_compute_handoff.get("executed_handoff_row_count") == 0
            and local_compute_handoff.get("output_written_row_count") == 0
            and local_compute_handoff.get("bootstrap_task_executes_local_compute_now") is False
            and local_compute_handoff.get("bootstrap_task_writes_output_now") is False
            and all(
                row.get("mode") == "cache_only"
                and row.get("mode_gate") == "live_light"
                and row.get("mode_gate_satisfied") is False
                and row.get("source_switch_satisfied") is False
                and row.get("inactive_reason") == "cache_only_read_only"
                and row.get("handoff_effective_status")
                == "local_compute_handoff_inactive_cache_only_read_only"
                and row.get("enabled_in_current_mode") is False
                and row.get("local_compute_executed_now") is False
                and row.get("output_written_now") is False
                for row in local_compute_handoff_rows
            ),
            f"local_compute_handoff={local_compute_handoff}",
        ),
        _row(
            "cache_only_call_ledger_records_handoff_mode_gate_without_execution",
            first_ledger.get("call_status") == "skipped_mode_not_live_light"
            and first_ledger.get("local_compute_handoff_status")
            == "local_compute_handoff_inactive_cache_only_read_only"
            and first_ledger.get("local_compute_handoff_mode_gate") == "live_light"
            and first_ledger.get("local_compute_handoff_mode_gate_satisfied") is False
            and first_ledger.get("local_compute_handoff_source_switch_satisfied") is False
            and first_ledger.get("local_compute_handoff_inactive_reason") == "cache_only_read_only"
            and first_ledger.get("local_compute_handoff_row_count") == 3
            and first_ledger.get("local_compute_handoff_enabled_row_count") == 0
            and first_ledger.get("local_compute_handoff_executed_row_count") == 0
            and first_ledger.get("local_compute_handoff_output_written_row_count") == 0
            and first_ledger.get("local_compute_handoff_ledger_executes_local_compute") is False
            and first_ledger.get("local_compute_handoff_ledger_writes_output") is False
            and first_ledger.get("local_compute_handoff_ledger_is_execution_evidence") is False
            and first_ledger.get("local_compute_handoff_ledger_is_production_evidence") is False
            and _dict(first_ledger.get("request_params_safe")).get("local_compute_handoff_status")
            == "local_compute_handoff_inactive_cache_only_read_only"
            and _dict(first_ledger.get("request_params_safe")).get("local_compute_handoff_inactive_reason")
            == "cache_only_read_only"
            and first_ledger.get("external_calls_triggered") is False,
            f"ledger={first_ledger}",
        ),
        _row(
            "cache_only_provider_linkage_rows_are_offline",
            status.get("provider_linkage_schema_version") == "command_center_bootstrap_provider_linkage.v1"
            and provider_linkage.get("cache_startup_render_boundary", {}).get("status") == "offline_enforced"
            and provider_linkage.get("tushare_light_refresh", {}).get("status")
            == "skipped_mode_not_live_light"
            and provider_linkage.get("deepseek_pro_after_task", {}).get("status")
            == "skipped_mode_not_live_light"
            and provider_linkage.get("github_probe_boundary", {}).get("live_light_on_open_allowed") is False
            and provider_linkage.get("real_trading_boundary", {}).get("real_trading_connected") is False,
            f"provider_linkage_keys={sorted(provider_linkage)}",
        ),
        _row(
            "cache_only_activation_receipt_keeps_execution_blocked",
            status.get("activation_receipt_schema_version") == "command_center_live_bootstrap_activation_receipt.v1"
            and activation.get("status") == "live_light_activation_receipt_ready_execution_blocked"
            and activation.get("scope") == "local_live_light_activation_receipt_no_provider_or_model_execution"
            and activation.get("local_activation_receipt_ready") is True
            and activation.get("ready_for_provider_execution_design") is True
            and activation.get("ready_for_provider_execution") is False
            and activation.get("ready_for_model_execution") is False
            and activation.get("production_live_light_complete") is False
            and activation.get("external_calls_triggered") is False
            and activation_rows.get("cache_render_boundary_enforced", {}).get("status") == "passed"
            and activation_rows.get("tushare_stage_requires_provider_adapter", {}).get("status")
            == "pending_provider_execution_implementation"
            and activation_rows.get("deepseek_stage_requires_model_execution_gate", {}).get("status")
            == "pending_model_execution_implementation"
            and activation_rows.get("production_activation_pending", {}).get("passed") is False,
            f"activation_status={activation.get('status')} rows={sorted(activation_rows)}",
        ),
        _row(
            "cache_only_acceptance_runbook_is_local_execution_pending",
            status.get("acceptance_runbook_schema_version")
            == "command_center_live_bootstrap_provider_model_acceptance_runbook.v1"
            and runbook.get("status") == "live_light_provider_model_acceptance_runbook_ready_execution_pending"
            and runbook.get("scope") == "local_runbook_no_provider_or_model_execution"
            and runbook.get("local_runbook_ready") is True
            and runbook.get("ready_for_acceptance_design") is True
            and runbook.get("ready_for_user_approved_acceptance_task") is False
            and runbook.get("provider_execution_implemented") is False
            and runbook.get("model_execution_implemented") is False
            and runbook.get("production_live_light_complete") is False
            and runbook.get("external_calls_triggered") is False
            and runbook.get("phase_count") == 10
            and runbook.get("provider_phase_count") == 2
            and runbook.get("model_phase_count") == 1
            and acceptance_rows.get("tushare_trade_cal_acceptance_sample", {}).get("status")
            == "pending_provider_execution"
            and acceptance_rows.get("deepseek_pro_model_acceptance_sample", {}).get("status")
            == "pending_model_execution",
            f"runbook_status={runbook.get('status')} rows={sorted(acceptance_rows)}",
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


def _manual_rows() -> list[dict[str, Any]]:
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="manual",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="true",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="true",
        COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART="true",
        COMMAND_CENTER_LIVE_STARTUP_AUTOSTART="true",
        COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="light_provider_model",
        COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE="provider_factor_next_model",
        COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT="true",
        COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT="true",
    )
    task_service.clear_task_statuses_for_tests(clear_persisted=True)
    status = bootstrap_service.read_bootstrap_status_cache()
    before_tasks = task_service.list_task_statuses()
    task = bootstrap_service.run_live_startup_task(
        {
            "source": "bootstrap_runtime_contract_manual",
            "symbols": ["000001.SZ"],
            "tushare": True,
            "deepseek": True,
            "api_key": "SHOULD_DROP",
            "token": "SHOULD_DROP",
        }
    )
    after_tasks = task_service.list_task_statuses()
    stages = _stage_rows(task)
    models = _model_rows(task)
    summary = _summary(task)
    payload_safe = _dict(task.get("payload_safe"))
    local_compute_handoff = _dict(payload_safe.get("bootstrap_local_compute_handoff_summary"))
    local_compute_handoff_rows = [
        row for row in _list(payload_safe.get("bootstrap_local_compute_handoff_rows")) if isinstance(row, dict)
    ]
    ledger = _ledger(task)
    first_ledger = ledger[0] if ledger else {}
    task_text = _serialized(task)
    manual_policy = _dict(status.get("manual"))
    provider_linkage = {
        str(row.get("linkage_key") or ""): row
        for row in _list(status.get("provider_linkage_rows"))
        if isinstance(row, dict)
    }
    mode_rows = {
        str(row.get("mode") or ""): row
        for row in _list(status.get("mode_rows"))
        if isinstance(row, dict)
    }
    config_rows = {
        str(row.get("config") or ""): row
        for row in _list(status.get("config_rows"))
        if isinstance(row, dict)
    }
    safe_config = _dict(status.get("safe_config_contract"))
    submit_contract = _dict(status.get("search_quant_projection_submit_autostart_contract"))
    return [
        _row(
            "manual_status_is_explicit_post_task_only",
            status.get("mode") == "manual"
            and status.get("status") == "manual_ready_explicit_task_only"
            and manual_policy.get("enabled") is True
            and manual_policy.get("button_gated_post_tasks_only") is True
            and manual_policy.get("auto_bootstrap_allowed") is False
            and manual_policy.get("react_mounted_auto_task_allowed") is False
            and _dict(status.get("policy")).get("manual_requires_explicit_post_task") is True
            and _dict(status.get("policy")).get("manual_auto_bootstrap_allowed") is False
            and status.get("external_calls_triggered") is False,
            f"mode={status.get('mode')} manual={manual_policy}",
        ),
        _row(
            "manual_get_status_creates_no_task",
            before_tasks == []
            and _dict(status.get("policy")).get("cache_api_external_calls") is False
            and _dict(status.get("policy")).get("react_initial_render_external_calls") is False
            and status.get("tushare_called") is False
            and status.get("deepseek_called") is False
            and status.get("github_called") is False,
            f"before_task_count={len(before_tasks)} status={status.get('status')}",
        ),
        _row(
            "manual_mode_row_requires_post_task",
            mode_rows.get("manual", {}).get("active") is True
            and mode_rows.get("manual", {}).get("external_calls") == "selected_post_task_only"
            and mode_rows.get("manual", {}).get("post_task_required") is True
            and mode_rows.get("manual", {}).get("trigger_matrix_schema_version")
            == "command_center_bootstrap_mode_trigger_matrix.v1"
            and mode_rows.get("manual", {}).get("page_open_task_allowed") is False
            and mode_rows.get("manual", {}).get("page_open_task_policy") == "disabled_requires_explicit_post_task"
            and mode_rows.get("manual", {}).get("react_initial_render_creates_task") is False
            and mode_rows.get("manual", {}).get("react_mounted_task_allowed_after_cache_render") is False
            and mode_rows.get("manual", {}).get("search_input_auto_task_allowed") is False
            and mode_rows.get("manual", {}).get("search_input_task_policy") == "never_on_typing"
            and mode_rows.get("manual", {}).get("search_action_task_allowed") is True
            and mode_rows.get("manual", {}).get("search_action_task_policy") == "explicit_post_task_only"
            and mode_rows.get("manual", {}).get("provider_model_execution_without_execution_request_allowed")
            is False
            and mode_rows.get("manual", {}).get("real_trading_task_allowed") is False
            and mode_rows.get("manual", {}).get("provider_execution_implemented") is False,
            f"manual_mode_row={mode_rows.get('manual')}",
        ),
        _row(
            "manual_source_switches_are_configured_but_not_effective",
            config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("configured_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("configured_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("mode_gate") == "live_light"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("mode_gate") == "live_light"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("mode_gate")
            == "live_light"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("mode_gate")
            == "live_light_and_frontend_enablement_promotion"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_status")
            == "manual_source_switch_disabled_explicit_task_only"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_status")
            == "manual_source_switch_disabled_explicit_task_only"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("effective_status")
            == "manual_explicit_button_submit_autostart_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("effective_status")
            == "manual_startup_autostart_disabled_explicit_task_only"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_status")
            == "manual_frontend_enablement_disabled_explicit_task_only"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("automation_effective") is False
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("automation_effective") is False
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("inactive_reason")
            == "manual_requires_explicit_post_task"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("inactive_reason")
            == "manual_requires_explicit_post_task"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("inactive_reason")
            == "manual_requires_explicit_button"
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("inactive_reason")
            == "manual_requires_explicit_post_task"
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "creates_local_background_task_only"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("creates_provider_model_task")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("inactive_reason")
            == "manual_requires_explicit_post_task"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "configured_value_safe"
            )
            == "light_provider_model"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "effective_value_safe"
            )
            == "plan_only"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("effective_status")
            == "manual_external_execution_profile_disabled_explicit_task_only"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("inactive_reason")
            == "manual_requires_explicit_post_task"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "provider_stage_allowed_by_profile"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "model_stage_allowed_by_profile"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "calls_provider_model_now"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "configured_value_safe"
            )
            == "provider_factor_next_model"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("effective_value_safe")
            == "bootstrap_only"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("effective_status")
            == "manual_live_light_research_scope_disabled_explicit_task_only"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("inactive_reason")
            == "manual_requires_explicit_post_task"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "provider_stage_allowed_by_scope"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "factor_light_allowed_by_scope"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "next_session_cache_allowed_by_scope"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("model_stage_allowed_by_scope")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("creates_task") is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "creates_provider_model_task"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("calls_provider_model_now")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("effective_status")
            == "manual_provider_model_enablement_disabled_explicit_task_only"
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("inactive_reason")
            == "manual_requires_explicit_provider_model_task"
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "provider_model_task_creation_allowed"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "creates_provider_model_task"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "calls_provider_model_now"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("creates_task") is False
            and safe_config.get("configured_source_switches_visible") is True
            and safe_config.get("effective_source_switches_mode_gated") is True
            and safe_config.get("effective_tushare_on_open") is False
            and safe_config.get("effective_deepseek_on_open") is False
            and safe_config.get("configured_search_submit_autostart") is True
            and safe_config.get("effective_search_submit_autostart") is False
            and safe_config.get("configured_frontend_enablement") is True
            and safe_config.get("effective_frontend_enablement") is False
            and safe_config.get("frontend_enablement_creates_task") is False
            and safe_config.get("effective_sources_enabled") is False
            and safe_config.get("manual_or_cache_only_switches_do_not_autostart") is True
            and safe_config.get("non_live_light_switches_do_not_autostart") is True,
            f"config_rows={config_rows} safe_config={safe_config}",
        ),
        _row(
            "manual_search_submit_autostart_stays_explicit_button_only",
            submit_contract.get("schema_version")
            == "command_center_search_quant_projection_submit_autostart_contract.v1"
            and submit_contract.get("status") == "manual_explicit_button_submit_autostart_disabled"
            and submit_contract.get("mode") == "manual"
            and submit_contract.get("configured_submit_autostart") is True
            and submit_contract.get("effective_submit_autostart") is False
            and submit_contract.get("autostart_readiness_stage") == "manual_explicit_post_task_only"
            and submit_contract.get("inactive_reason") == "manual_requires_explicit_button"
            and submit_contract.get("active_mode_submit_autostart_allowed") is False
            and submit_contract.get("search_submit_task_creation_allowed_in_active_mode") is False
            and submit_contract.get("manual_search_submit_auto_start_allowed") is False
            and submit_contract.get("manual_requires_explicit_button") is True
            and submit_contract.get("manual_mode_blocks_submit_autostart") is True
            and submit_contract.get("configured_true_but_manual_mode") is True
            and submit_contract.get("search_typing_creates_task") is False
            and submit_contract.get("react_render_creates_task") is False
            and submit_contract.get("cache_get_creates_task") is False
            and submit_contract.get("fastapi_startup_creates_task") is False
            and submit_contract.get("latest_status_replay_lookup_creates_task") is False
            and submit_contract.get("current_submit_autostart_calls_provider_model") is False
            and submit_contract.get("provider_model_autostart_without_execution_request_allowed") is False
            and submit_contract.get("external_calls_triggered") is False
            and submit_contract.get("tushare_called") is False
            and submit_contract.get("deepseek_called") is False
            and submit_contract.get("github_called") is False
            and submit_contract.get("does_not_execute_trades") is True
            and submit_contract.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_allowed") is False
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_allowed") is False
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_configured") is True
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_effective") is False,
            f"submit_contract={submit_contract}",
        ),
        _row(
            "manual_live_startup_post_is_explicit_and_skips_auto_provider_execution",
            len(after_tasks) == 1
            and task.get("current_step") == "live_bootstrap_skipped_mode_not_live_light"
            and payload_safe.get("bootstrap_mode") == "manual"
            and summary.get("planned_provider_stage_count") == 0
            and summary.get("planned_model_stage_count") == 0
            and summary.get("external_calls_triggered") is False
            and first_ledger.get("call_status") == "skipped_mode_not_live_light"
            and first_ledger.get("external_calls_triggered") is False,
            f"after_task_count={len(after_tasks)} current_step={task.get('current_step')} summary={summary}",
        ),
        _row(
            "manual_local_compute_handoff_mode_gated",
            summary.get("local_compute_handoff_row_count") == 3
            and summary.get("local_compute_handoff_enabled_row_count") == 0
            and summary.get("local_compute_handoff_executed_row_count") == 0
            and local_compute_handoff.get("schema_version")
            == "command_center_live_bootstrap_local_compute_handoff.v1"
            and local_compute_handoff.get("status") == "local_compute_handoff_inactive_manual_explicit_task_only"
            and local_compute_handoff.get("mode") == "manual"
            and local_compute_handoff.get("mode_gate") == "live_light"
            and local_compute_handoff.get("mode_gate_satisfied") is False
            and local_compute_handoff.get("source_switch_satisfied") is False
            and local_compute_handoff.get("inactive_reason") == "manual_requires_explicit_post_task"
            and local_compute_handoff.get("handoff_row_count") == 3
            and local_compute_handoff.get("enabled_handoff_row_count") == 0
            and local_compute_handoff.get("executed_handoff_row_count") == 0
            and local_compute_handoff.get("output_written_row_count") == 0
            and local_compute_handoff.get("bootstrap_task_executes_local_compute_now") is False
            and local_compute_handoff.get("bootstrap_task_writes_output_now") is False
            and all(
                row.get("mode") == "manual"
                and row.get("mode_gate") == "live_light"
                and row.get("mode_gate_satisfied") is False
                and row.get("source_switch_satisfied") is False
                and row.get("inactive_reason") == "manual_requires_explicit_post_task"
                and row.get("handoff_effective_status")
                == "local_compute_handoff_inactive_manual_explicit_task_only"
                and row.get("enabled_in_current_mode") is False
                and row.get("local_compute_executed_now") is False
                and row.get("output_written_now") is False
                for row in local_compute_handoff_rows
            ),
            f"local_compute_handoff={local_compute_handoff}",
        ),
        _row(
            "manual_call_ledger_records_handoff_mode_gate_without_execution",
            first_ledger.get("call_status") == "skipped_mode_not_live_light"
            and first_ledger.get("local_compute_handoff_status")
            == "local_compute_handoff_inactive_manual_explicit_task_only"
            and first_ledger.get("local_compute_handoff_mode_gate") == "live_light"
            and first_ledger.get("local_compute_handoff_mode_gate_satisfied") is False
            and first_ledger.get("local_compute_handoff_source_switch_satisfied") is False
            and first_ledger.get("local_compute_handoff_inactive_reason") == "manual_requires_explicit_post_task"
            and first_ledger.get("local_compute_handoff_row_count") == 3
            and first_ledger.get("local_compute_handoff_enabled_row_count") == 0
            and first_ledger.get("local_compute_handoff_executed_row_count") == 0
            and first_ledger.get("local_compute_handoff_output_written_row_count") == 0
            and first_ledger.get("local_compute_handoff_ledger_executes_local_compute") is False
            and first_ledger.get("local_compute_handoff_ledger_writes_output") is False
            and first_ledger.get("local_compute_handoff_ledger_is_execution_evidence") is False
            and first_ledger.get("local_compute_handoff_ledger_is_production_evidence") is False
            and _dict(first_ledger.get("request_params_safe")).get("local_compute_handoff_status")
            == "local_compute_handoff_inactive_manual_explicit_task_only"
            and _dict(first_ledger.get("request_params_safe")).get("local_compute_handoff_inactive_reason")
            == "manual_requires_explicit_post_task"
            and first_ledger.get("external_calls_triggered") is False,
            f"ledger={first_ledger}",
        ),
        _row(
            "manual_stage_and_model_rows_are_not_executed",
            len(stages) == 9
            and len(models) == 1
            and all(row.get("status") == "skipped_mode_not_live_light" for row in stages)
            and _all_false(stages, "actual_external_calls_triggered", "tushare_called", "deepseek_called", "github_called")
            and models[0].get("model_called") is False
            and models[0].get("deepseek_called") is False,
            f"stage_count={len(stages)} model_preview_count={len(models)}",
        ),
        _row(
            "manual_provider_linkage_keeps_startup_offline",
            provider_linkage.get("cache_startup_render_boundary", {}).get("status") == "offline_enforced"
            and provider_linkage.get("live_light_bootstrap_task_boundary", {}).get("status")
            == "inactive_until_live_light"
            and provider_linkage.get("tushare_light_refresh", {}).get("status")
            == "skipped_mode_not_live_light"
            and provider_linkage.get("deepseek_pro_after_task", {}).get("status")
            == "skipped_mode_not_live_light"
            and provider_linkage.get("github_probe_boundary", {}).get("status") == "manual_or_explicit_task_only"
            and provider_linkage.get("real_trading_boundary", {}).get("real_trading_connected") is False,
            f"provider_linkage={provider_linkage}",
        ),
        _row(
            "manual_payload_sanitizes_secret_like_inputs",
            "SHOULD_DROP" not in task_text and '"api_key"' not in task_text and '"token"' not in task_text,
            "raw secret-like payload keys/values are not serialized into manual task output",
        ),
    ]


def _live_full_reserved_rows() -> list[dict[str, Any]]:
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="live_full",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="true",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="true",
        COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART="true",
        COMMAND_CENTER_LIVE_STARTUP_AUTOSTART="true",
        COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="light_provider_model",
        COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE="provider_factor_next_model",
        COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT="true",
        COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT="true",
        COMMAND_CENTER_LIVE_ALLOW_FULL_POOL="true",
    )
    task_service.clear_task_statuses_for_tests(clear_persisted=True)
    status = bootstrap_service.read_bootstrap_status_cache()
    before_tasks = task_service.list_task_statuses()
    task = bootstrap_service.run_live_startup_task(
        {
            "source": "bootstrap_runtime_contract_live_full_reserved",
            "symbols": ["000001.SZ"],
            "tushare": True,
            "deepseek": True,
        }
    )
    config_rows = {
        str(row.get("config") or ""): row
        for row in _list(status.get("config_rows"))
        if isinstance(row, dict)
    }
    safe_config = _dict(status.get("safe_config_contract"))
    live_full = _dict(status.get("live_full"))
    contract = _dict(status.get("live_full_reserved_contract"))
    submit_contract = _dict(status.get("search_quant_projection_submit_autostart_contract"))
    provider_linkage = {
        str(row.get("linkage_key") or ""): row
        for row in _list(status.get("provider_linkage_rows"))
        if isinstance(row, dict)
    }
    payload = _dict(task.get("payload_safe"))
    summary = _dict(payload.get("bootstrap_plan_summary"))
    local_compute_handoff = _dict(payload.get("bootstrap_local_compute_handoff_summary"))
    local_compute_handoff_rows = [
        row for row in _list(payload.get("bootstrap_local_compute_handoff_rows")) if isinstance(row, dict)
    ]
    ledger = _ledger(task)
    first_ledger = ledger[0] if ledger else {}
    return [
        _row(
            "live_full_status_is_reserved_disabled_no_startup_task",
            status.get("mode") == "live_full"
            and status.get("status") == "live_full_reserved_disabled"
            and before_tasks == []
            and status.get("external_calls_triggered") is False
            and status.get("tushare_called") is False
            and status.get("deepseek_called") is False
            and status.get("github_called") is False
            and _dict(status.get("policy")).get("live_full_enabled") is False
            and _dict(status.get("policy")).get("live_full_reserved") is True
            and _dict(status.get("policy")).get("live_full_requires_separate_authorization") is True
            and _dict(status.get("policy")).get("live_full_full_pool_on_open_allowed") is False,
            f"status={status.get('status')} policy={_dict(status.get('policy'))}",
        ),
        _row(
            "live_full_configured_switches_are_never_effective_without_future_authorization",
            config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("configured_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("configured_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL", {}).get("configured_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_status")
            == "live_full_source_switch_disabled_reserved"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_status")
            == "live_full_source_switch_disabled_reserved"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("effective_status")
            == "live_full_reserved_submit_autostart_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("effective_status")
            == "live_full_startup_autostart_disabled_reserved"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_status")
            == "live_full_frontend_enablement_disabled_reserved"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "creates_local_background_task_only"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get("creates_provider_model_task")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("creates_task") is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "configured_value_safe"
            )
            == "light_provider_model"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "effective_value_safe"
            )
            == "plan_only"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("effective_status")
            == "live_full_external_execution_profile_disabled_reserved"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "provider_stage_allowed_by_profile"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "model_stage_allowed_by_profile"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "calls_provider_model_now"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "configured_value_safe"
            )
            == "provider_factor_next_model"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("effective_value_safe")
            == "bootstrap_only"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("effective_status")
            == "live_full_live_light_research_scope_disabled_reserved"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "provider_stage_allowed_by_scope"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "factor_light_allowed_by_scope"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "next_session_cache_allowed_by_scope"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("model_stage_allowed_by_scope")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("creates_task") is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "creates_provider_model_task"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get("calls_provider_model_now")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("effective_status")
            == "live_full_provider_model_enablement_disabled_reserved"
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get("inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "provider_model_task_creation_allowed"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "creates_provider_model_task"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "calls_provider_model_now"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL", {}).get("mode_gate")
            == "live_full_future_authorization"
            and config_rows.get("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL", {}).get("automation_effective") is False
            and config_rows.get("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL", {}).get("full_pool_on_open_allowed") is False
            and safe_config.get("effective_tushare_on_open") is False
            and safe_config.get("effective_deepseek_on_open") is False
            and safe_config.get("configured_search_submit_autostart") is True
            and safe_config.get("effective_search_submit_autostart") is False
            and safe_config.get("configured_frontend_enablement") is True
            and safe_config.get("effective_frontend_enablement") is False
            and safe_config.get("frontend_enablement_creates_task") is False
            and safe_config.get("effective_sources_enabled") is False
            and safe_config.get("non_live_light_switches_do_not_autostart") is True,
            f"config_rows={config_rows} safe_config={safe_config}",
        ),
        _row(
            "live_full_search_submit_autostart_stays_reserved_disabled",
            submit_contract.get("schema_version")
            == "command_center_search_quant_projection_submit_autostart_contract.v1"
            and submit_contract.get("status") == "live_full_reserved_submit_autostart_disabled"
            and submit_contract.get("mode") == "live_full"
            and submit_contract.get("configured_submit_autostart") is True
            and submit_contract.get("effective_submit_autostart") is False
            and submit_contract.get("autostart_readiness_stage")
            == "live_full_reserved_requires_separate_authorization"
            and submit_contract.get("inactive_reason") == "live_full_reserved_requires_separate_authorization"
            and submit_contract.get("active_mode_submit_autostart_allowed") is False
            and submit_contract.get("search_submit_task_creation_allowed_in_active_mode") is False
            and submit_contract.get("live_full_search_submit_auto_start_allowed") is False
            and submit_contract.get("live_full_reserved") is True
            and submit_contract.get("live_full_requires_separate_authorization") is True
            and submit_contract.get("configured_true_but_reserved_mode") is True
            and submit_contract.get("reserved_mode_blocks_local_projection_task") is True
            and submit_contract.get("reserved_mode_blocks_provider_model_task") is True
            and submit_contract.get("reserved_mode_blocks_full_pool_or_deep_scan") is True
            and submit_contract.get("search_typing_creates_task") is False
            and submit_contract.get("react_render_creates_task") is False
            and submit_contract.get("cache_get_creates_task") is False
            and submit_contract.get("fastapi_startup_creates_task") is False
            and submit_contract.get("latest_status_replay_lookup_creates_task") is False
            and submit_contract.get("current_submit_autostart_calls_provider_model") is False
            and submit_contract.get("provider_model_autostart_without_execution_request_allowed") is False
            and submit_contract.get("external_calls_triggered") is False
            and submit_contract.get("tushare_called") is False
            and submit_contract.get("deepseek_called") is False
            and submit_contract.get("github_called") is False
            and submit_contract.get("does_not_execute_trades") is True
            and submit_contract.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_allowed") is False
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_allowed") is False
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_configured") is True
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_effective") is False,
            f"submit_contract={submit_contract}",
        ),
        _row(
            "live_full_reserved_contract_blocks_full_pool_deep_scan_and_worker_execution",
            live_full.get("enabled") is False
            and live_full.get("active_mode_requested") is True
            and live_full.get("configured_allow_full_pool") is True
            and live_full.get("effective_allow_full_pool") is False
            and live_full.get("future_worker_mode_only") is True
            and live_full.get("separate_authorization_required") is True
            and live_full.get("full_pool_on_open_allowed") is False
            and live_full.get("deep_scan_on_open_allowed") is False
            and live_full.get("worker_execution_implemented") is False
            and contract.get("schema_version") == "command_center_live_full_reserved_contract.v1"
            and contract.get("status") == "live_full_reserved_disabled"
            and contract.get("reserved_mode") is True
            and contract.get("page_open_task_allowed") is False
            and contract.get("react_mounted_auto_task_allowed") is False
            and contract.get("search_input_auto_task_allowed") is False
            and contract.get("cache_get_creates_task") is False
            and contract.get("full_pool_on_open_allowed") is False
            and contract.get("deep_scan_on_open_allowed") is False
            and contract.get("worker_execution_implemented") is False
            and contract.get("production_live_full_complete") is False
            and contract.get("external_calls_triggered") is False,
            f"live_full={live_full} contract={contract}",
        ),
        _row(
            "live_full_live_startup_post_skips_without_provider_model_or_worker_execution",
            task.get("current_step") == "live_bootstrap_skipped_mode_not_live_light"
            and payload.get("bootstrap_mode") == "live_full"
            and payload.get("tushare_on_open") is False
            and payload.get("deepseek_on_open") is False
            and payload.get("sources_enabled") is False
            and summary.get("planned_provider_stage_count") == 0
            and summary.get("planned_model_stage_count") == 0
            and summary.get("external_calls_triggered") is False
            and task.get("external_calls_triggered") is False
            and task.get("tushare_called") is False
            and task.get("deepseek_called") is False
            and task.get("github_called") is False
            and task.get("does_not_execute_trades") is True
            and task.get("does_not_modify_strategy_action") is True,
            f"task_step={task.get('current_step')} summary={summary}",
        ),
        _row(
            "live_full_local_compute_handoff_reserved_without_execution",
            summary.get("local_compute_handoff_row_count") == 3
            and summary.get("local_compute_handoff_enabled_row_count") == 0
            and summary.get("local_compute_handoff_executed_row_count") == 0
            and local_compute_handoff.get("schema_version")
            == "command_center_live_bootstrap_local_compute_handoff.v1"
            and local_compute_handoff.get("status") == "local_compute_handoff_inactive_live_full_reserved"
            and local_compute_handoff.get("mode") == "live_full"
            and local_compute_handoff.get("mode_gate") == "live_light"
            and local_compute_handoff.get("mode_gate_satisfied") is False
            and local_compute_handoff.get("source_switch_satisfied") is False
            and local_compute_handoff.get("inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and local_compute_handoff.get("handoff_row_count") == 3
            and local_compute_handoff.get("enabled_handoff_row_count") == 0
            and local_compute_handoff.get("executed_handoff_row_count") == 0
            and local_compute_handoff.get("output_written_row_count") == 0
            and local_compute_handoff.get("bootstrap_task_executes_local_compute_now") is False
            and local_compute_handoff.get("bootstrap_task_writes_output_now") is False
            and all(
                row.get("mode") == "live_full"
                and row.get("mode_gate") == "live_light"
                and row.get("mode_gate_satisfied") is False
                and row.get("source_switch_satisfied") is False
                and row.get("inactive_reason") == "live_full_reserved_requires_separate_authorization"
                and row.get("handoff_effective_status")
                == "local_compute_handoff_inactive_live_full_reserved"
                and row.get("enabled_in_current_mode") is False
                and row.get("local_compute_executed_now") is False
                and row.get("output_written_now") is False
                for row in local_compute_handoff_rows
            )
            and first_ledger.get("local_compute_handoff_status")
            == "local_compute_handoff_inactive_live_full_reserved"
            and first_ledger.get("local_compute_handoff_mode_gate") == "live_light"
            and first_ledger.get("local_compute_handoff_mode_gate_satisfied") is False
            and first_ledger.get("local_compute_handoff_source_switch_satisfied") is False
            and first_ledger.get("local_compute_handoff_inactive_reason")
            == "live_full_reserved_requires_separate_authorization"
            and first_ledger.get("local_compute_handoff_ledger_executes_local_compute") is False
            and first_ledger.get("local_compute_handoff_ledger_writes_output") is False
            and first_ledger.get("local_compute_handoff_ledger_is_execution_evidence") is False
            and first_ledger.get("local_compute_handoff_ledger_is_production_evidence") is False,
            f"local_compute_handoff={local_compute_handoff} ledger={first_ledger}",
        ),
    ]


def _live_light_disabled_rows() -> list[dict[str, Any]]:
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="live_light",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="false",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="false",
    )
    task_service.clear_task_statuses_for_tests(clear_persisted=True)
    status = bootstrap_service.read_bootstrap_status_cache()
    task = bootstrap_service.run_live_startup_task({"source": "bootstrap_runtime_contract", "symbols": ["000001.SZ"]})
    stages = _stage_rows(task)
    summary = _summary(task)
    ledger = _ledger(task)
    first_ledger = ledger[0] if ledger else {}
    payload_safe = _dict(task.get("payload_safe"))
    local_compute_handoff = _dict(payload_safe.get("bootstrap_local_compute_handoff_summary"))
    local_compute_handoff_rows = [
        row for row in _list(payload_safe.get("bootstrap_local_compute_handoff_rows")) if isinstance(row, dict)
    ]
    provider_or_model = [row for row in stages if row.get("stage_kind") in {"provider", "model"}]
    linkage = {
        str(row.get("linkage_key") or ""): row
        for row in _list(status.get("provider_linkage_rows"))
        if isinstance(row, dict)
    }
    activation = _dict(status.get("live_light_activation_receipt"))
    activation_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(status.get("live_light_activation_rows"))
        if isinstance(row, dict)
    }
    runbook = _dict(status.get("live_light_provider_model_acceptance_runbook"))
    acceptance_rows = {
        str(row.get("phase_key") or ""): row
        for row in _list(status.get("live_light_provider_model_acceptance_rows"))
        if isinstance(row, dict)
    }
    submit_autostart_contract = _dict(status.get("search_quant_projection_submit_autostart_contract"))
    frontend_wiring_contract = _dict(status.get("search_quant_projection_frontend_wiring_acceptance_contract"))
    config_rows = {
        str(row.get("config") or ""): row
        for row in _list(status.get("config_rows"))
        if isinstance(row, dict)
    }
    safe_config = _dict(status.get("safe_config_contract"))
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
            "live_light_disabled_local_compute_handoff_source_gated",
            summary.get("local_compute_handoff_row_count") == 3
            and summary.get("local_compute_handoff_enabled_row_count") == 0
            and summary.get("local_compute_handoff_executed_row_count") == 0
            and local_compute_handoff.get("schema_version")
            == "command_center_live_bootstrap_local_compute_handoff.v1"
            and local_compute_handoff.get("status") == "local_compute_handoff_inactive_source_switch_false"
            and local_compute_handoff.get("mode") == "live_light"
            and local_compute_handoff.get("mode_gate") == "live_light"
            and local_compute_handoff.get("mode_gate_satisfied") is True
            and local_compute_handoff.get("source_switch_satisfied") is False
            and local_compute_handoff.get("inactive_reason") == "source_switch_false"
            and local_compute_handoff.get("handoff_row_count") == 3
            and local_compute_handoff.get("enabled_handoff_row_count") == 0
            and local_compute_handoff.get("executed_handoff_row_count") == 0
            and local_compute_handoff.get("output_written_row_count") == 0
            and local_compute_handoff.get("bootstrap_task_executes_local_compute_now") is False
            and local_compute_handoff.get("bootstrap_task_writes_output_now") is False
            and all(
                row.get("mode") == "live_light"
                and row.get("mode_gate") == "live_light"
                and row.get("mode_gate_satisfied") is True
                and row.get("source_switch_satisfied") is False
                and row.get("inactive_reason") == "source_switch_false"
                and row.get("handoff_effective_status") == "local_compute_handoff_inactive_source_switch_false"
                and row.get("enabled_in_current_mode") is False
                and row.get("local_compute_executed_now") is False
                and row.get("output_written_now") is False
                for row in local_compute_handoff_rows
            ),
            f"local_compute_handoff={local_compute_handoff}",
        ),
        _row(
            "live_light_disabled_call_ledger_records_source_gate_without_execution",
            first_ledger.get("call_status") == "skipped_sources_disabled"
            and first_ledger.get("local_compute_handoff_status") == "local_compute_handoff_inactive_source_switch_false"
            and first_ledger.get("local_compute_handoff_mode_gate") == "live_light"
            and first_ledger.get("local_compute_handoff_mode_gate_satisfied") is True
            and first_ledger.get("local_compute_handoff_source_switch_satisfied") is False
            and first_ledger.get("local_compute_handoff_inactive_reason") == "source_switch_false"
            and first_ledger.get("local_compute_handoff_row_count") == 3
            and first_ledger.get("local_compute_handoff_enabled_row_count") == 0
            and first_ledger.get("local_compute_handoff_executed_row_count") == 0
            and first_ledger.get("local_compute_handoff_output_written_row_count") == 0
            and first_ledger.get("local_compute_handoff_ledger_executes_local_compute") is False
            and first_ledger.get("local_compute_handoff_ledger_writes_output") is False
            and first_ledger.get("local_compute_handoff_ledger_is_execution_evidence") is False
            and first_ledger.get("local_compute_handoff_ledger_is_production_evidence") is False
            and _dict(first_ledger.get("request_params_safe")).get("local_compute_handoff_status")
            == "local_compute_handoff_inactive_source_switch_false"
            and _dict(first_ledger.get("request_params_safe")).get("local_compute_handoff_inactive_reason")
            == "source_switch_false"
            and first_ledger.get("external_calls_triggered") is False,
            f"ledger={first_ledger}",
        ),
        _row(
            "live_light_disabled_source_switches_show_switch_false_reason",
            config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("configured_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("configured_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("configured_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("configured_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_value_safe") is False
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_status")
            == "source_switch_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_status")
            == "source_switch_disabled"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("inactive_reason")
            == "source_switch_false"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("inactive_reason")
            == "source_switch_false"
            and config_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get("inactive_reason")
            == "source_switch_false"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_status")
            == "release_switch_default_off"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("inactive_reason")
            == "release_switch_default_off"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("creates_task") is False
            and safe_config.get("configured_search_submit_autostart") is False
            and safe_config.get("effective_search_submit_autostart") is False
            and safe_config.get("configured_frontend_enablement") is False
            and safe_config.get("effective_frontend_enablement") is False
            and safe_config.get("effective_sources_enabled") is False
            and safe_config.get("non_live_light_switches_do_not_autostart") is False,
            f"config_rows={config_rows} safe_config={safe_config}",
        ),
        _row(
            "live_light_submit_autostart_disabled_until_server_config_switch_enabled",
            submit_autostart_contract.get("status") == "disabled_by_search_submit_autostart_config"
            and submit_autostart_contract.get("config_switch") == "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
            and submit_autostart_contract.get("configured_submit_autostart") is False
            and submit_autostart_contract.get("effective_submit_autostart") is False
            and submit_autostart_contract.get("live_light_search_submit_auto_start_allowed") is False
            and submit_autostart_contract.get("manual_search_submit_auto_start_allowed") is False
            and submit_autostart_contract.get("cache_only_search_submit_auto_start_allowed") is False
            and submit_autostart_contract.get("autostart_readiness_stage")
            == "server_config_switch_disabled_frontend_wiring_pending"
            and frontend_wiring_contract.get("status") == "frontend_wiring_acceptance_pending_config_disabled"
            and frontend_wiring_contract.get("active_mode_frontend_submit_autostart_allowed") is False
            and frontend_wiring_contract.get("active_mode_expected_frontend_behavior")
            == "explicit_button_until_submit_autostart_config_enabled"
            and frontend_wiring_contract.get("active_mode_task_creation_surface")
            == "explicit_button_until_autostart_config_enabled",
            f"submit_autostart_contract={submit_autostart_contract} frontend={frontend_wiring_contract}",
        ),
        _row(
            "live_light_disabled_provider_linkage_rows_are_config_skipped",
            linkage.get("live_light_bootstrap_task_boundary", {}).get("status") == "available_after_cache_render"
            and linkage.get("live_light_bootstrap_task_boundary", {}).get("external_calls_allowed") is False
            and linkage.get("tushare_light_refresh", {}).get("status") == "skipped_by_config"
            and linkage.get("deepseek_pro_after_task", {}).get("status") == "skipped_by_config",
            f"linkage={linkage}",
        ),
        _row(
            "live_light_disabled_activation_receipt_visible_execution_blocked",
            activation.get("mode") == "live_light"
            and activation.get("live_light_enabled") is True
            and activation.get("ready_for_provider_execution_design") is True
            and activation.get("ready_for_provider_execution") is False
            and activation.get("ready_for_model_execution") is False
            and activation.get("production_live_light_complete") is False
            and activation_rows.get("post_task_boundary_visible", {}).get("status") == "passed"
            and activation_rows.get("real_trading_disconnected", {}).get("status") == "passed",
            f"activation={activation}",
        ),
        _row(
            "live_light_disabled_acceptance_runbook_visible_execution_pending",
            runbook.get("mode") == "live_light"
            and runbook.get("live_light_enabled") is True
            and runbook.get("tushare_on_open") is False
            and runbook.get("deepseek_on_open") is False
            and runbook.get("ready_for_acceptance_design") is True
            and runbook.get("ready_for_user_approved_acceptance_task") is False
            and runbook.get("external_calls_triggered") is False
            and acceptance_rows.get("explicit_user_approval_required", {}).get("status")
            == "pending_user_approved_acceptance_run"
            and acceptance_rows.get("production_promotion_review", {}).get("status")
            == "blocked_until_all_acceptance_evidence_present",
            f"runbook={runbook}",
        ),
        _row(
            "live_light_disabled_provider_model_rows_are_skipped_by_config",
            provider_or_model
            and all(row.get("status") == "skipped_by_config" for row in provider_or_model)
            and _all_false(provider_or_model, "actual_external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            f"provider_model_row_count={len(provider_or_model)}",
        ),
    ]


def _live_light_light_provider_profile_rows() -> list[dict[str, Any]]:
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="live_light",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="true",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="true",
        COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="light_provider",
        COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT="2",
        COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS="600",
    )
    task_service.clear_task_statuses_for_tests(clear_persisted=True)
    status = bootstrap_service.read_bootstrap_status_cache()
    task = bootstrap_service.run_live_startup_task(
        {
            "source": "bootstrap_runtime_contract_light_provider_profile",
            "symbols": ["000001.SZ", "000002.SZ"],
            "tushare": True,
            "deepseek": True,
        }
    )
    status_after_bootstrap = bootstrap_service.read_bootstrap_status_cache()
    safe_config = _dict(status.get("safe_config_contract"))
    unified = _dict(status.get("live_light_unified_startup_task_contract"))
    unified_rows = {
        str(row.get("stage_key") or ""): row
        for row in _list(unified.get("stage_rows"))
        if isinstance(row, dict)
    }
    stages_by_key = _stages_by_key(task)
    model_rows = _model_rows(task)
    model = model_rows[0] if model_rows else {}
    summary = _summary(task)
    ledger_rows = _ledger(task)
    first_ledger = ledger_rows[0] if ledger_rows else {}
    latest_bootstrap_status = _dict(status_after_bootstrap.get("live_light_latest_bootstrap_task_status"))
    return [
        _row(
            "live_light_light_provider_profile_safe_config_allows_provider_only",
            safe_config.get("configured_external_execution_profile") == "light_provider"
            and safe_config.get("effective_external_execution_profile") == "light_provider"
            and safe_config.get("external_execution_profile_provider_stage_allowed") is True
            and safe_config.get("external_execution_profile_model_stage_allowed") is False
            and safe_config.get("external_execution_profile_executor_implemented") is False
            and safe_config.get("external_execution_profile_calls_provider_model_now") is False
            and safe_config.get("external_execution_profile_requires_call_ledger") is True
            and safe_config.get("external_execution_profile_requires_model_ledger_for_deepseek") is False,
            f"safe_config={safe_config}",
        ),
        _row(
            "live_light_light_provider_profile_unified_startup_contract_blocks_model_stage",
            unified.get("external_execution_profile") == "light_provider"
            and unified.get("external_execution_profile_provider_stage_allowed") is True
            and unified.get("external_execution_profile_model_stage_allowed") is False
            and unified.get("external_execution_profile_executor_implemented") is False
            and unified.get("external_execution_profile_calls_provider_model_now") is False
            and unified.get("provider_stage_planned_by_profile") is True
            and unified.get("model_stage_planned_by_profile") is False
            and unified_rows.get("tushare_light_refresh", {}).get("profile_stage_allowed") is True
            and unified_rows.get("deepseek_pro_explanation", {}).get("profile_stage_allowed") is False
            and unified_rows.get("deepseek_pro_explanation", {}).get("profile_required") == "light_provider_model"
            and unified_rows.get("deepseek_pro_explanation", {}).get("profile_inactive_reason")
            == "external_execution_profile_does_not_allow_model_stage"
            and unified.get("external_calls_triggered") is False,
            f"unified={unified}",
        ),
        _row(
            "live_light_light_provider_profile_task_plans_provider_only_without_execution",
            task.get("current_step") == "live_bootstrap_plan_recorded_no_provider_execution"
            and summary.get("external_execution_profile") == "light_provider"
            and summary.get("external_execution_profile_provider_stage_allowed") is True
            and summary.get("external_execution_profile_model_stage_allowed") is False
            and summary.get("external_execution_profile_executor_implemented") is False
            and summary.get("planned_provider_stage_count") == 2
            and summary.get("planned_model_stage_count") == 0
            and summary.get("actual_provider_execution_count") == 0
            and summary.get("actual_model_call_count") == 0
            and summary.get("external_calls_triggered") is False,
            f"summary={summary}",
        ),
        _row(
            "live_light_light_provider_profile_stage_rows_skip_deepseek_model",
            stages_by_key.get("trade_cal_if_needed", {}).get("status") == "planned_provider_pending_not_executed"
            and stages_by_key.get("tushare_light_refresh", {}).get("status") == "planned_provider_pending_not_executed"
            and stages_by_key.get("deepseek_pro_explanation", {}).get("status") == "skipped_by_config"
            and stages_by_key.get("trade_cal_if_needed", {}).get("profile_stage_allowed") is True
            and stages_by_key.get("tushare_light_refresh", {}).get("profile_stage_allowed") is True
            and stages_by_key.get("deepseek_pro_explanation", {}).get("profile_stage_allowed") is False
            and stages_by_key.get("deepseek_pro_explanation", {}).get("profile_inactive_reason")
            == "external_execution_profile_does_not_allow_stage"
            and model.get("external_execution_profile") == "light_provider"
            and model.get("profile_stage_allowed") is False
            and model.get("model_called") is False
            and model.get("deepseek_called") is False
            and _all_false(_list(task.get("payload_safe", {}).get("bootstrap_stage_rows")), "actual_external_calls_triggered", "tushare_called", "deepseek_called", "github_called"),
            f"stages={stages_by_key} model={model}",
        ),
        _row(
            "live_light_light_provider_profile_ledger_and_latest_replay_keep_model_off",
            first_ledger.get("external_execution_profile") == "light_provider"
            and first_ledger.get("external_execution_profile_provider_stage_allowed") is True
            and first_ledger.get("external_execution_profile_model_stage_allowed") is False
            and first_ledger.get("planned_provider_stage_count") == 2
            and first_ledger.get("planned_model_stage_count") == 0
            and first_ledger.get("external_calls_triggered") is False
            and latest_bootstrap_status.get("external_execution_profile") == "light_provider"
            and latest_bootstrap_status.get("external_execution_profile_provider_stage_allowed") is True
            and latest_bootstrap_status.get("external_execution_profile_model_stage_allowed") is False
            and latest_bootstrap_status.get("planned_provider_stage_count") == 2
            and latest_bootstrap_status.get("planned_model_stage_count") == 0
            and latest_bootstrap_status.get("external_calls_triggered") is False
            and latest_bootstrap_status.get("deepseek_called") is False,
            f"ledger={first_ledger} latest={latest_bootstrap_status}",
        ),
    ]


def _live_light_enabled_rows() -> list[dict[str, Any]]:
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="live_light",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="true",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="true",
        COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART="true",
        COMMAND_CENTER_LIVE_STARTUP_AUTOSTART="true",
        COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="light_provider_model",
        COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT="true",
        COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT="true",
        COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT="2",
        COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS="600",
        COMMAND_CENTER_LIVE_DEEPSEEK_MODEL="contract-live-pro",
        COMMAND_CENTER_LIVE_ALLOW_FULL_POOL="false",
        TUSHARE_TOKEN="DROP_TS",
        DEEPSEEK_API_KEY="DROP_DS",
    )
    task_service.clear_task_statuses_for_tests(clear_persisted=True)
    status = bootstrap_service.read_bootstrap_status_cache()
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
    status_after_bootstrap = bootstrap_service.read_bootstrap_status_cache()
    dry_run = bootstrap_service.run_provider_model_acceptance_dry_run(
        {
            "source": "bootstrap_runtime_contract",
            "approved_by_user": True,
            "symbols": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "include_tushare": True,
            "include_deepseek": True,
            "apis": ["trade_cal", "daily", "moneyflow", "fina_indicator"],
            "api_key": "SHOULD_DROP",
            "token": "SHOULD_DROP",
        }
    )
    dry_payload = _dict(dry_run.get("payload_safe"))
    dry_scope_ticket = _dict(dry_payload.get("acceptance_scope_ticket"))
    status_after_dry_run = bootstrap_service.read_bootstrap_status_cache()
    execution_request = bootstrap_service.run_provider_model_execution_request(
        {
            "source": "bootstrap_runtime_contract",
            "confirmed_by_user": True,
            "acceptance_scope_hash": dry_scope_ticket.get("scope_hash"),
            "selected_apis": ["trade_cal", "daily", "moneyflow"],
            "include_tushare": True,
            "include_deepseek": True,
            "api_key": "SHOULD_DROP",
            "token": "SHOULD_DROP",
        }
    )
    status_after_request = bootstrap_service.read_bootstrap_status_cache()
    quant_projection_seed = task_service.create_task_record(
        "run_candidate_radar_quant_projection",
        output_packet_key="command_center_3_candidate_radar_cache",
        payload={"source": "bootstrap_runtime_contract", "symbol": "000001.SZ"},
        current_step="candidate_radar_quant_projection_queued",
    )
    quant_projection_ledger = {
        "api": "local_candidate_radar_quant_projection",
        "endpoint": "POST /api/candidate-radar/quant-projection",
        "call_status": "quant_projection_local_receipt_ready_provider_model_pending",
        "row_count": 1,
        "request_params_safe": {
            "scan_mode": "search_quant_projection",
            "symbol": "000001.SZ",
            "symbol_valid": True,
            "include_tushare_requested": True,
            "include_deepseek_requested": True,
            "selected_light_apis": ["trade_cal_if_needed", "daily", "daily_basic", "moneyflow"],
            "external_sources_allowed": False,
            "provider_execution_implemented": False,
            "model_execution_implemented": False,
            "production_quant_projection_complete": False,
        },
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    quant_projection = task_service.update_task_status(
        str(quant_projection_seed.get("task_id") or ""),
        status="success",
        progress=1.0,
        current_step="candidate_radar_quant_projection_ready",
        output_packet_key="command_center_3_candidate_radar_cache",
        call_ledger=[quant_projection_ledger],
        warning="candidate_radar_quant_projection_ready_no_external_call",
    ) or quant_projection_seed
    status_after_quant_projection = bootstrap_service.read_bootstrap_status_cache()
    quant_provider_model_seed = task_service.create_task_record(
        "run_candidate_radar_quant_projection_provider_model_acceptance",
        output_packet_key="command_center_3_candidate_radar_cache",
        payload={"source": "bootstrap_runtime_contract", "symbol": "000001.SZ"},
        current_step="candidate_radar_quant_projection_provider_model_acceptance_queued",
    )
    quant_provider_model_ledger = {
        "api": "local_candidate_radar_quant_projection_provider_model_acceptance",
        "endpoint": "POST /api/candidate-radar/quant-projection-provider-model-acceptance",
        "call_status": "search_quant_provider_model_acceptance_waiting_deepseek_output_acceptance",
        "row_count": 2,
        "request_params_safe": {
            "symbol": "000001.SZ",
            "selected_apis": ["trade_cal", "daily", "daily_basic", "moneyflow"],
            "include_deepseek": True,
            "provider_execution_implemented": True,
            "model_execution_implemented": False,
            "tushare_call_ledger_evidence_done": True,
            "deepseek_model_ledger_evidence_done": False,
            "production_quant_projection_complete": False,
        },
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    quant_provider_tushare_ledger = {
        "api": "daily",
        "endpoint": "tushare.daily",
        "call_status": "success",
        "row_count": 2,
        "request_params_safe": {"ts_code": "000001.SZ"},
        "external": False,
        "external_calls_triggered": False,
        "tushare_called": True,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    quant_provider_model = task_service.update_task_status(
        str(quant_provider_model_seed.get("task_id") or ""),
        status="success",
        progress=1.0,
        current_step="search_quant_provider_model_acceptance_waiting_deepseek_output_acceptance",
        output_packet_key="command_center_3_candidate_radar_cache",
        call_ledger=[quant_provider_model_ledger, quant_provider_tushare_ledger],
        warning="candidate_radar_quant_projection_provider_model_acceptance_output_acceptance_pending_no_external_call",
    ) or quant_provider_model_seed
    status_after_provider_model = bootstrap_service.read_bootstrap_status_cache()
    _set_env(
        COMMAND_CENTER_BOOTSTRAP_MODE="live_light",
        COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN="true",
        COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN="true",
        COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART="true",
        COMMAND_CENTER_LIVE_STARTUP_AUTOSTART="true",
        COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="light_provider_model",
        COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT="true",
        COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT="true",
        COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT="2",
        COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS="600",
        COMMAND_CENTER_LIVE_DEEPSEEK_MODEL="contract-live-pro",
        COMMAND_CENTER_LIVE_ALLOW_FULL_POOL="false",
    )
    dry_run_missing_credentials = bootstrap_service.run_provider_model_acceptance_dry_run(
        {
            "source": "bootstrap_runtime_contract_missing_credentials",
            "approved_by_user": True,
            "symbols": ["000001.SZ"],
            "include_tushare": True,
            "include_deepseek": True,
            "apis": ["trade_cal", "daily"],
        }
    )
    stages = _stage_rows(task)
    stages_by_key = _stages_by_key(task)
    models = _model_rows(task)
    model = models[0] if models else {}
    payload = _dict(task.get("payload_safe"))
    summary = _summary(task)
    local_compute_handoff = _dict(payload.get("bootstrap_local_compute_handoff_summary"))
    local_compute_handoff_rows = {
        str(row.get("handoff_key") or ""): row
        for row in _list(payload.get("bootstrap_local_compute_handoff_rows"))
        if isinstance(row, dict)
    }
    call_ledger = _ledger(task)
    first_ledger = call_ledger[0] if call_ledger else {}
    repeated_ledger = _ledger(repeated)
    last_repeated = repeated_ledger[-1] if repeated_ledger else {}
    latest_bootstrap_status = _dict(status_after_bootstrap.get("live_light_latest_bootstrap_task_status"))
    latest_bootstrap_live_light = _dict(status_after_bootstrap.get("live_light"))
    latest_bootstrap_policy = _dict(status_after_bootstrap.get("policy"))
    latest_bootstrap_status_text = _serialized(status_after_bootstrap)
    required_handoff_lineage_fields = [
        "source_task_id",
        "source_task_type",
        "source_route",
        "runtime_mode",
        "scope_hash",
        "provider_call_ledger_ids",
        "model_ledger_ids",
        "input_packet_keys",
        "output_packet_key",
        "cache_source",
        "storage_backend",
        "local_fetched_at",
        "freshness_state",
        "data_date",
        "provider_gap",
        "safe_error",
    ]
    dry_summary = _dict(dry_payload.get("acceptance_dry_run_summary"))
    dry_real_preflight = _dict(dry_payload.get("real_acceptance_preflight_receipt"))
    dry_real_preflight_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(dry_payload.get("real_acceptance_preflight_rows"))
        if isinstance(row, dict)
    }
    credential_rows = {
        str(row.get("provider") or ""): row
        for row in _list(dry_payload.get("credential_presence_rows"))
        if isinstance(row, dict)
    }
    dry_rows = {
        str(row.get("phase_key") or ""): row
        for row in _list(dry_payload.get("acceptance_dry_run_rows"))
        if isinstance(row, dict)
    }
    dry_ledger = _ledger(dry_run)
    first_dry_ledger = dry_ledger[0] if dry_ledger else {}
    dry_text = _serialized(dry_run)
    latest_dry_run_status = _dict(status_after_dry_run.get("live_light_latest_acceptance_dry_run_status"))
    latest_dry_run_live_light = _dict(status_after_dry_run.get("live_light"))
    latest_dry_run_policy = _dict(status_after_dry_run.get("policy"))
    latest_dry_run_status_text = _serialized(status_after_dry_run)
    request_payload = _dict(execution_request.get("payload_safe"))
    request_receipt = _dict(request_payload.get("execution_request_receipt"))
    request_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(request_payload.get("execution_request_rows"))
        if isinstance(row, dict)
    }
    request_ledger = _ledger(execution_request)
    first_request_ledger = request_ledger[0] if request_ledger else {}
    request_text = _serialized(execution_request)
    latest_execution_status = _dict(status_after_request.get("live_light_latest_execution_request_status"))
    latest_live_light = _dict(status_after_request.get("live_light"))
    latest_policy = _dict(status_after_request.get("policy"))
    latest_status_text = _serialized(status_after_request)
    latest_quant_projection_status = _dict(status_after_quant_projection.get("search_quant_projection_latest_status"))
    latest_quant_projection_live_light = _dict(status_after_quant_projection.get("live_light"))
    latest_quant_projection_policy = _dict(status_after_quant_projection.get("policy"))
    latest_quant_projection_status_text = _serialized(status_after_quant_projection)
    latest_provider_model_status = _dict(
        status_after_provider_model.get("search_quant_projection_provider_model_latest_status")
    )
    latest_provider_model_live_light = _dict(status_after_provider_model.get("live_light"))
    latest_provider_model_policy = _dict(status_after_provider_model.get("policy"))
    latest_provider_model_status_text = _serialized(status_after_provider_model)
    missing_payload = _dict(dry_run_missing_credentials.get("payload_safe"))
    missing_summary = _dict(missing_payload.get("acceptance_dry_run_summary"))
    missing_scope_ticket = _dict(missing_payload.get("acceptance_scope_ticket"))
    missing_real_preflight = _dict(missing_payload.get("real_acceptance_preflight_receipt"))
    missing_real_preflight_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(missing_payload.get("real_acceptance_preflight_rows"))
        if isinstance(row, dict)
    }
    missing_credential_rows = {
        str(row.get("provider") or ""): row
        for row in _list(missing_payload.get("credential_presence_rows"))
        if isinstance(row, dict)
    }
    missing_rows = {
        str(row.get("phase_key") or ""): row
        for row in _list(missing_payload.get("acceptance_dry_run_rows"))
        if isinstance(row, dict)
    }
    missing_ledger = _ledger(dry_run_missing_credentials)
    first_missing_ledger = missing_ledger[0] if missing_ledger else {}
    required_fields = set(_list(model.get("required_model_ledger_fields")))
    allowed_fields = set(_list(model.get("allowed_output_fields")))
    linkage = {
        str(row.get("linkage_key") or ""): row
        for row in _list(status.get("provider_linkage_rows"))
        if isinstance(row, dict)
    }
    activation = _dict(status.get("live_light_activation_receipt"))
    activation_rows = {
        str(row.get("criterion") or ""): row
        for row in _list(status.get("live_light_activation_rows"))
        if isinstance(row, dict)
    }
    runbook = _dict(status.get("live_light_provider_model_acceptance_runbook"))
    acceptance_rows = {
        str(row.get("phase_key") or ""): row
        for row in _list(status.get("live_light_provider_model_acceptance_rows"))
        if isinstance(row, dict)
    }
    background_contract = _dict(status.get("live_light_background_task_contract"))
    startup_autostart_readiness = _dict(status.get("live_light_startup_autostart_readiness_contract"))
    startup_autostart_readiness_rows = {
        str(row.get("readiness_key") or ""): row
        for row in _list(startup_autostart_readiness.get("readiness_rows"))
        if isinstance(row, dict)
    }
    unified_startup_contract = _dict(status.get("live_light_unified_startup_task_contract"))
    unified_startup_rows = {
        str(row.get("stage_key") or ""): row
        for row in _list(unified_startup_contract.get("stage_rows"))
        if isinstance(row, dict)
    }
    scope_intake_contract = _dict(status.get("live_light_scope_intake_contract"))
    stage_dependency_contract = _dict(status.get("live_light_stage_dependency_contract"))
    freshness_contract = _dict(status.get("live_light_freshness_provider_gap_contract"))
    lifecycle_contract = _dict(status.get("live_light_task_lifecycle_contract"))
    queue_budget_contract = _dict(status.get("live_light_task_queue_budget_contract"))
    queue_budget_rows = {
        str(row.get("budget_key") or ""): row
        for row in _list(queue_budget_contract.get("queue_rows"))
        if isinstance(row, dict)
    }
    evidence_contract = _dict(status.get("live_light_evidence_grade_contract"))
    credential_contract = _dict(status.get("live_light_credential_preflight_contract"))
    execution_request_contract = _dict(status.get("live_light_provider_model_execution_request_contract"))
    execution_request_handoff_contract = _dict(status.get("live_light_execution_request_handoff_contract"))
    ledger_contract = _dict(status.get("live_light_ledger_contract"))
    ledger_redaction_invariant = _dict(status.get("live_light_ledger_redaction_invariant_contract"))
    search_contract = _dict(status.get("search_quant_projection_workflow_contract"))
    submit_autostart_contract = _dict(status.get("search_quant_projection_submit_autostart_contract"))
    config_handoff_contract = _dict(
        status.get("search_quant_projection_submit_autostart_config_handoff_contract")
    )
    config_promotion_contract = _dict(
        status.get("search_quant_projection_submit_autostart_config_promotion_contract")
    )
    config_promotion_rows = {
        str(row.get("step_key") or ""): row
        for row in _list(config_promotion_contract.get("promotion_rows"))
        if isinstance(row, dict)
    }
    frontend_wiring_contract = _dict(status.get("search_quant_projection_frontend_wiring_acceptance_contract"))
    unified_handoff_contract = _dict(status.get("search_quant_projection_unified_startup_handoff_contract"))
    unified_handoff_rows = {
        str(row.get("handoff_key") or ""): row
        for row in _list(unified_handoff_contract.get("handoff_rows"))
        if isinstance(row, dict)
    }
    result_surface_contract = _dict(status.get("search_quant_projection_result_surface_contract"))
    factor_next_handoff_contract = _dict(status.get("search_quant_projection_factor_next_handoff_contract"))
    factor_next_handoff_rows = {
        str(row.get("handoff_key") or ""): row
        for row in _list(factor_next_handoff_contract.get("handoff_rows"))
        if isinstance(row, dict)
    }
    cache_write_preflight_contract = _dict(status.get("search_quant_projection_cache_write_preflight_contract"))
    cache_write_preflight_rows = {
        str(row.get("preflight_key") or ""): row
        for row in _list(cache_write_preflight_contract.get("preflight_rows"))
        if isinstance(row, dict)
    }
    deepseek_model_preflight_contract = _dict(status.get("search_quant_projection_deepseek_model_preflight_contract"))
    deepseek_model_preflight_rows = {
        str(row.get("preflight_key") or ""): row
        for row in _list(deepseek_model_preflight_contract.get("preflight_rows"))
        if isinstance(row, dict)
    }
    deepseek_output_acceptance_contract = _dict(
        status.get("search_quant_projection_deepseek_output_acceptance_contract")
    )
    deepseek_output_acceptance_rows = {
        str(row.get("acceptance_key") or ""): row
        for row in _list(deepseek_output_acceptance_contract.get("acceptance_rows"))
        if isinstance(row, dict)
    }
    deepseek_readiness_contract = _dict(status.get("search_quant_projection_deepseek_readiness_contract"))
    deepseek_readiness_rows = {
        str(row.get("readiness_key") or ""): row
        for row in _list(deepseek_readiness_contract.get("readiness_rows"))
        if isinstance(row, dict)
    }
    tushare_contract = _dict(status.get("tushare_light_strategy_contract"))
    deepseek_contract = _dict(status.get("deepseek_pro_strategy_contract"))
    ui_contract = _dict(status.get("ui_nonblocking_runtime_contract"))
    fallback_contract = _dict(status.get("live_light_local_fallback_contract"))
    lineage_contract = _dict(status.get("live_light_cache_lineage_contract"))
    output_surface_contract = _dict(status.get("live_light_output_surface_contract"))
    budget_contract = _dict(status.get("live_light_runtime_budget_contract"))
    task_control_contract = _dict(status.get("live_light_task_control_contract"))
    operator_status_contract = _dict(status.get("live_light_operator_status_contract"))
    promotion_gate_contract = _dict(status.get("live_light_promotion_gate_contract"))
    worker_dispatch_contract = _dict(status.get("live_light_worker_dispatch_contract"))
    config_rows = {
        str(row.get("config") or ""): row
        for row in _list(status.get("config_rows"))
        if isinstance(row, dict)
    }
    mode_rows = {
        str(row.get("mode") or ""): row
        for row in _list(status.get("mode_rows"))
        if isinstance(row, dict)
    }
    runtime_mode_policy_rows = {
        str(row.get("mode") or ""): row
        for row in _list(status.get("runtime_mode_policy_rows"))
        if isinstance(row, dict)
    }
    safe_config = _dict(status.get("safe_config_contract"))
    runtime_config_reference = _dict(status.get("runtime_config_reference_contract"))
    runtime_config_reference_rows = {
        str(row.get("config") or ""): row
        for row in _list(runtime_config_reference.get("reference_rows"))
        if isinstance(row, dict)
    }
    runtime_config_ownership = _dict(status.get("runtime_config_ownership_invariant_contract"))
    runtime_config_ownership_rows = {
        str(row.get("config") or ""): row
        for row in _list(runtime_config_ownership.get("ownership_rows"))
        if isinstance(row, dict)
    }
    runtime_mode_acceptance = _dict(status.get("runtime_mode_acceptance_contract"))
    runtime_mode_acceptance_rows = {
        str(row.get("mode") or ""): row
        for row in _list(runtime_mode_acceptance.get("acceptance_rows"))
        if isinstance(row, dict)
    }
    rollout_roadmap = _dict(status.get("live_light_rollout_roadmap_contract"))
    rollout_rows = {
        str(row.get("stage_key") or ""): row
        for row in _list(rollout_roadmap.get("rollout_rows"))
        if isinstance(row, dict)
    }
    task_creation_invariant = _dict(status.get("task_creation_invariant_contract"))
    task_creation_rows = {
        str(row.get("surface_key") or ""): row
        for row in _list(task_creation_invariant.get("invariant_rows"))
        if isinstance(row, dict)
    }
    external_silence = _dict(status.get("runtime_external_silence_contract"))
    external_silence_rows = {
        str(row.get("surface_key") or ""): row
        for row in _list(external_silence.get("silence_rows"))
        if isinstance(row, dict)
    }
    hard_boundary = _dict(status.get("runtime_hard_boundary_contract"))
    hard_boundary_rows = {
        str(row.get("boundary_key") or ""): row
        for row in _list(hard_boundary.get("boundary_rows"))
        if isinstance(row, dict)
    }
    cache_first_polling = _dict(status.get("runtime_cache_first_polling_contract"))
    cache_first_polling_rows = {
        str(row.get("phase_key") or ""): row
        for row in _list(cache_first_polling.get("phase_rows"))
        if isinstance(row, dict)
    }
    frontend_enablement_gate = _dict(status.get("runtime_frontend_enablement_gate_contract"))
    frontend_enablement_gate_rows = {
        str(row.get("gate_key") or ""): row
        for row in _list(frontend_enablement_gate.get("gate_rows"))
        if isinstance(row, dict)
    }
    browser_evidence = _dict(status.get("runtime_browser_evidence_contract"))
    browser_evidence_rows = {
        str(row.get("evidence_key") or ""): row
        for row in _list(browser_evidence.get("evidence_rows"))
        if isinstance(row, dict)
    }
    frontend_wiring_manifest = _dict(status.get("runtime_frontend_wiring_manifest_contract"))
    frontend_wiring_manifest_rows = {
        str(row.get("manifest_key") or ""): row
        for row in _list(frontend_wiring_manifest.get("manifest_rows"))
        if isinstance(row, dict)
    }
    frontend_acceptance_runbook = _dict(status.get("runtime_frontend_acceptance_runbook_contract"))
    frontend_acceptance_runbook_rows = {
        str(row.get("runbook_key") or ""): row
        for row in _list(frontend_acceptance_runbook.get("runbook_rows"))
        if isinstance(row, dict)
    }
    frontend_acceptance_artifact = _dict(status.get("runtime_frontend_acceptance_artifact_contract"))
    frontend_acceptance_artifact_rows = {
        str(row.get("artifact_key") or ""): row
        for row in _list(frontend_acceptance_artifact.get("artifact_rows"))
        if isinstance(row, dict)
    }
    frontend_enablement_promotion = _dict(status.get("runtime_frontend_enablement_promotion_contract"))
    frontend_enablement_promotion_rows = {
        str(row.get("promotion_key") or ""): row
        for row in _list(frontend_enablement_promotion.get("promotion_rows"))
        if isinstance(row, dict)
    }
    frontend_release_switch = _dict(status.get("runtime_frontend_enablement_release_switch_contract"))
    frontend_release_switch_rows = {
        str(row.get("release_switch_key") or ""): row
        for row in _list(frontend_release_switch.get("release_switch_rows"))
        if isinstance(row, dict)
    }
    frontend_enablement_config_promotion = _dict(
        status.get("runtime_frontend_enablement_config_promotion_contract")
    )
    frontend_enablement_config_promotion_rows = {
        str(row.get("step_key") or ""): row
        for row in _list(frontend_enablement_config_promotion.get("promotion_rows"))
        if isinstance(row, dict)
    }
    runtime_operator_summary = _dict(status.get("runtime_operator_summary_contract"))
    runtime_operator_rows = {
        str(row.get("mode") or ""): row
        for row in _list(runtime_operator_summary.get("summary_rows"))
        if isinstance(row, dict)
    }
    latest_acceptance_dry_run_status = _dict(status.get("live_light_latest_acceptance_dry_run_status"))
    latest_execution_request_status = _dict(status.get("live_light_latest_execution_request_status"))
    return [
        _row(
            "live_light_records_plan_without_provider_execution",
            task.get("current_step") == "live_bootstrap_plan_recorded_no_provider_execution"
            and len(stages) == 9
            and len(models) == 1
            and summary.get("external_execution_profile") == "light_provider_model"
            and summary.get("external_execution_profile_provider_stage_allowed") is True
            and summary.get("external_execution_profile_model_stage_allowed") is True
            and summary.get("external_execution_profile_executor_implemented") is False
            and summary.get("planned_provider_stage_count") == 2
            and summary.get("planned_model_stage_count") == 1
            and summary.get("actual_provider_execution_count") == 0
            and summary.get("actual_model_call_count") == 0
            and summary.get("external_calls_triggered") is False,
            f"current_step={task.get('current_step')} summary={summary}",
        ),
        _row(
            "live_light_bootstrap_local_compute_handoff_maps_factor_next_without_execution",
            payload.get("bootstrap_local_compute_handoff_schema_version")
            == "command_center_live_bootstrap_local_compute_handoff.v1"
            and summary.get("local_compute_handoff_row_count") == 3
            and summary.get("local_compute_handoff_enabled_row_count") == 3
            and summary.get("local_compute_handoff_executed_row_count") == 0
            and local_compute_handoff.get("schema_version")
            == "command_center_live_bootstrap_local_compute_handoff.v1"
            and local_compute_handoff.get("status") == "local_compute_handoff_visible_execution_pending"
            and local_compute_handoff.get("mode") == "live_light"
            and local_compute_handoff.get("mode_gate") == "live_light"
            and local_compute_handoff.get("mode_gate_satisfied") is True
            and local_compute_handoff.get("source_switch_satisfied") is True
            and local_compute_handoff.get("inactive_reason") == ""
            and local_compute_handoff.get("handoff_row_count") == 3
            and local_compute_handoff.get("enabled_handoff_row_count") == 3
            and local_compute_handoff.get("executed_handoff_row_count") == 0
            and local_compute_handoff.get("output_written_row_count") == 0
            and local_compute_handoff.get("required_handoff_keys")
            == ["factor_light_runtime", "factor_quant_hub_cache_refresh", "next_session_cache_refresh"]
            and local_compute_handoff.get("future_local_routes")
            == ["POST /api/factor-quant/run-light", "POST /api/next-session/generate"]
            and local_compute_handoff.get("future_task_types")
            == ["build_next_session_projection", "run_factor_light"]
            and local_compute_handoff.get("output_packet_keys")
            == ["command_center_factor_quant_hub_packet", "command_center_next_session_projection_packet"]
            and local_compute_handoff.get("input_packet_keys")
            == ["command_center_factor_quant_hub_packet", "command_center_next_session_projection_packet"]
            and local_compute_handoff.get("lineage_contract_schema_version")
            == "command_center_live_light_cache_lineage_contract.v1"
            and local_compute_handoff.get("lineage_write_policy") == "post_task_worker_or_local_pipeline_only"
            and local_compute_handoff.get("required_output_lineage_fields") == required_handoff_lineage_fields
            and local_compute_handoff.get("lineage_required_field_count") == len(required_handoff_lineage_fields)
            and local_compute_handoff.get("lineage_written_row_count") == 0
            and local_compute_handoff.get("cache_get_may_write_lineage") is False
            and local_compute_handoff.get("react_render_may_write_lineage") is False
            and local_compute_handoff.get("fastapi_startup_may_write_lineage") is False
            and local_compute_handoff.get("lineage_is_execution_evidence") is False
            and local_compute_handoff.get("lineage_is_production_evidence") is False
            and local_compute_handoff.get("local_compute_from_existing_cache_allowed") is True
            and local_compute_handoff.get("bootstrap_task_executes_local_compute_now") is False
            and local_compute_handoff.get("bootstrap_task_writes_output_now") is False
            and local_compute_handoff.get("cache_get_may_execute_local_compute") is False
            and local_compute_handoff.get("react_render_may_execute_local_compute") is False
            and local_compute_handoff.get("fastapi_startup_may_execute_local_compute") is False
            and local_compute_handoff.get("search_typing_may_execute_local_compute") is False
            and local_compute_handoff.get("local_compute_may_synthesize_provider_rows") is False
            and local_compute_handoff.get("local_compute_may_synthesize_model_output") is False
            and local_compute_handoff.get("output_lineage_required") is True
            and local_compute_handoff.get("safe_error_required_when_missing_cache") is True
            and local_compute_handoff.get("provider_gap_visible_when_provider_data_missing") is True
            and local_compute_handoff.get("provider_execution_implemented") is False
            and local_compute_handoff.get("model_execution_implemented") is False
            and local_compute_handoff.get("handoff_is_provider_execution_evidence") is False
            and local_compute_handoff.get("handoff_is_model_correctness_evidence") is False
            and local_compute_handoff.get("handoff_is_production_evidence") is False
            and local_compute_handoff.get("external_calls_triggered") is False
            and local_compute_handoff.get("tushare_called") is False
            and local_compute_handoff.get("deepseek_called") is False
            and local_compute_handoff.get("github_called") is False
            and local_compute_handoff.get("does_not_execute_trades") is True
            and local_compute_handoff.get("does_not_modify_strategy_action") is True
            and set(local_compute_handoff_rows)
            == {"factor_light_runtime", "factor_quant_hub_cache_refresh", "next_session_cache_refresh"}
            and local_compute_handoff_rows.get("factor_light_runtime", {}).get("future_local_route")
            == "POST /api/factor-quant/run-light"
            and local_compute_handoff_rows.get("factor_light_runtime", {}).get("future_task_type")
            == "run_factor_light"
            and local_compute_handoff_rows.get("factor_light_runtime", {}).get("input_packet_keys")
            == ["command_center_factor_quant_hub_packet"]
            and local_compute_handoff_rows.get("factor_quant_hub_cache_refresh", {}).get("input_packet_keys")
            == ["command_center_factor_quant_hub_packet"]
            and local_compute_handoff_rows.get("factor_quant_hub_cache_refresh", {}).get("output_packet_key")
            == "command_center_factor_quant_hub_packet"
            and local_compute_handoff_rows.get("next_session_cache_refresh", {}).get("future_local_route")
            == "POST /api/next-session/generate"
            and local_compute_handoff_rows.get("next_session_cache_refresh", {}).get("future_task_type")
            == "build_next_session_projection"
            and local_compute_handoff_rows.get("next_session_cache_refresh", {}).get("input_packet_keys")
            == ["command_center_factor_quant_hub_packet", "command_center_next_session_projection_packet"]
            and local_compute_handoff_rows.get("next_session_cache_refresh", {}).get("output_packet_key")
            == "command_center_next_session_projection_packet"
            and all(
                row.get("enabled_in_current_mode") is True
                and row.get("mode_gate") == "live_light"
                and row.get("mode_gate_satisfied") is True
                and row.get("source_switch_satisfied") is True
                and row.get("inactive_reason") == ""
                and row.get("handoff_effective_status") == "local_compute_handoff_visible_execution_pending"
                and row.get("future_queue") == "local_compute"
                and row.get("local_compute_from_existing_cache_allowed") is True
                and row.get("local_task_created_now") is False
                and row.get("local_compute_executed_now") is False
                and row.get("output_written_now") is False
                and row.get("cache_get_may_execute") is False
                and row.get("react_render_may_execute") is False
                and row.get("fastapi_startup_may_execute") is False
                and row.get("search_typing_may_execute") is False
                and row.get("provider_execution_required") is False
                and row.get("model_execution_required") is False
                and row.get("provider_rows_synthesized") is False
                and row.get("model_output_synthesized") is False
                and row.get("output_lineage_required") is True
                and row.get("lineage_contract_schema_version")
                == "command_center_live_light_cache_lineage_contract.v1"
                and row.get("lineage_write_policy") == "post_task_worker_or_local_pipeline_only"
                and row.get("required_output_lineage_fields") == required_handoff_lineage_fields
                and row.get("lineage_required_field_count") == len(required_handoff_lineage_fields)
                and row.get("lineage_written_now") is False
                and row.get("cache_get_may_write_lineage") is False
                and row.get("react_render_may_write_lineage") is False
                and row.get("fastapi_startup_may_write_lineage") is False
                and row.get("lineage_is_execution_evidence") is False
                and row.get("lineage_is_production_evidence") is False
                and row.get("safe_error_required_when_missing_cache") is True
                and row.get("provider_gap_visible_when_provider_data_missing") is True
                and row.get("row_is_provider_execution_evidence") is False
                and row.get("row_is_model_correctness_evidence") is False
                and row.get("row_is_production_evidence") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in local_compute_handoff_rows.values()
            ),
            f"local_compute_handoff={local_compute_handoff}",
        ),
        _row(
            "live_light_mode_trigger_matrix_allows_only_bounded_task_creation",
            mode_rows.get("live_light", {}).get("active") is True
            and mode_rows.get("live_light", {}).get("trigger_matrix_schema_version")
            == "command_center_bootstrap_mode_trigger_matrix.v1"
            and mode_rows.get("live_light", {}).get("page_open_task_allowed") is True
            and mode_rows.get("live_light", {}).get("page_open_task_policy")
            == "after_cache_render_rate_limited_local_task"
            and mode_rows.get("live_light", {}).get("react_initial_render_creates_task") is False
            and mode_rows.get("live_light", {}).get("react_mounted_task_allowed_after_cache_render") is True
            and mode_rows.get("live_light", {}).get("search_input_auto_task_allowed") is False
            and mode_rows.get("live_light", {}).get("search_input_task_policy") == "never_on_typing"
            and mode_rows.get("live_light", {}).get("search_action_task_allowed") is True
            and mode_rows.get("live_light", {}).get("search_action_task_policy")
            == "explicit_search_action_local_task_provider_model_requires_execution_request"
            and mode_rows.get("live_light", {}).get("provider_model_execution_without_execution_request_allowed")
            is False
            and mode_rows.get("live_light", {}).get("real_trading_task_allowed") is False
            and mode_rows.get("cache_only", {}).get("page_open_task_allowed") is False
            and mode_rows.get("cache_only", {}).get("search_action_task_allowed") is False
            and mode_rows.get("live_full", {}).get("page_open_task_allowed") is False
            and mode_rows.get("live_full", {}).get("search_action_task_allowed") is False,
            f"mode_rows={mode_rows}",
        ),
        _row(
            "runtime_mode_policy_rows_carry_config_boundary_fields",
            set(runtime_mode_policy_rows) == set(COMMAND_CENTER_RUNTIME_MODES)
            and all(
                row.get("policy_source") == "config.COMMAND_CENTER_RUNTIME_MODE_POLICIES"
                and row.get("cache_get_rule") == "read_only_no_provider_model_worker_or_trade"
                and row.get("react_render_rule") == "read_only_no_provider_model_worker_or_trade"
                and row.get("ordinary_entrance_visibility_rule")
                == "show_task_boundary_in_user_summary_before_settings_developer_audit"
                and row.get("ordinary_mode_banner_rule")
                == "read_only_status_banner_not_task_launcher_or_config_writer"
                and row.get("production_evidence_rule") == "config_policy_row_is_not_production_evidence"
                and row.get("frontend_visible") is True
                and row.get("frontend_editable") is False
                and row.get("frontend_writeback_allowed") is False
                and row.get("status_endpoint_writeback_allowed") is False
                and row.get("cache_get_external_calls") is False
                and row.get("react_render_provider_calls") is False
                and row.get("fastapi_startup_external_calls") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                and row.get("is_production_evidence") is False
                for row in runtime_mode_policy_rows.values()
            )
            and runtime_mode_policy_rows.get("cache_only", {}).get("ledger_rule")
            == "no_external_call_no_ledger_required"
            and runtime_mode_policy_rows.get("manual", {}).get("ledger_rule")
            == "call_ledger_and_model_ledger_required_for_external_work"
            and runtime_mode_policy_rows.get("live_light", {}).get("ledger_rule")
            == "call_ledger_and_model_ledger_required_for_external_work"
            and runtime_mode_policy_rows.get("live_full", {}).get("ledger_rule")
            == "reserved_future_authorization_required",
            f"runtime_mode_policy_rows={runtime_mode_policy_rows}",
        ),
        _row(
            "runtime_mode_acceptance_contract_keeps_mode_boundaries_read_only",
            runtime_mode_acceptance.get("schema_version") == "command_center_bootstrap_runtime_mode_acceptance.v1"
            and runtime_mode_acceptance.get("status") == "runtime_mode_acceptance_matrix_visible_read_only"
            and runtime_mode_acceptance.get("mode") == "live_light"
            and runtime_mode_acceptance.get("acceptance_row_count") == 4
            and runtime_mode_acceptance.get("active_acceptance_mode") == "live_light"
            and set(runtime_mode_acceptance_rows) == {"cache_only", "manual", "live_light", "live_full"}
            and runtime_mode_acceptance_rows.get("cache_only", {}).get("acceptance_status")
            == "default_offline_cache_read_only"
            and runtime_mode_acceptance_rows.get("cache_only", {}).get("external_call_surface") == "none"
            and runtime_mode_acceptance_rows.get("cache_only", {}).get("page_open_task_allowed") is False
            and runtime_mode_acceptance_rows.get("cache_only", {}).get("search_submit_task_allowed") is False
            and runtime_mode_acceptance_rows.get("cache_only", {}).get("manual_button_task_allowed") is False
            and runtime_mode_acceptance_rows.get("cache_only", {}).get("provider_model_execution_allowed") is False
            and runtime_mode_acceptance_rows.get("manual", {}).get("acceptance_status") == "explicit_post_task_only"
            and runtime_mode_acceptance_rows.get("manual", {}).get("page_open_task_allowed") is False
            and runtime_mode_acceptance_rows.get("manual", {}).get("search_submit_task_allowed") is False
            and runtime_mode_acceptance_rows.get("manual", {}).get("manual_button_task_allowed") is True
            and runtime_mode_acceptance_rows.get("manual", {}).get("live_light_background_task_allowed") is False
            and runtime_mode_acceptance_rows.get("manual", {}).get("provider_model_execution_allowed") is True
            and runtime_mode_acceptance_rows.get("manual", {}).get("provider_model_execution_surface")
            == "selected_explicit_post_task_only"
            and runtime_mode_acceptance_rows.get("manual", {}).get("provider_model_direct_execution_allowed")
            is False
            and runtime_mode_acceptance_rows.get("manual", {}).get("provider_model_requires_explicit_post_task")
            is True
            and runtime_mode_acceptance_rows.get("manual", {}).get(
                "provider_model_execution_requires_task_contract"
            )
            is True
            and runtime_mode_acceptance_rows.get("live_light", {}).get("acceptance_status")
            == "bounded_background_task_creation_only"
            and runtime_mode_acceptance_rows.get("live_light", {}).get("page_open_task_allowed") is True
            and runtime_mode_acceptance_rows.get("live_light", {}).get("page_open_task_policy")
            == "after_cache_render_rate_limited_local_task"
            and runtime_mode_acceptance_rows.get("live_light", {}).get("search_submit_task_allowed") is True
            and runtime_mode_acceptance_rows.get("live_light", {}).get("search_submit_task_policy")
            == "safe_submit_local_projection_task_provider_model_request_gated"
            and runtime_mode_acceptance_rows.get("live_light", {}).get("live_light_background_task_allowed") is True
            and runtime_mode_acceptance_rows.get("live_light", {}).get("provider_model_execution_allowed") is False
            and runtime_mode_acceptance_rows.get("live_light", {}).get("provider_model_execution_surface")
            == "execution_request_post_task_only"
            and runtime_mode_acceptance_rows.get("live_light", {}).get(
                "provider_model_direct_execution_allowed"
            )
            is False
            and runtime_mode_acceptance_rows.get("live_light", {}).get(
                "provider_model_requires_explicit_post_task"
            )
            is True
            and runtime_mode_acceptance_rows.get("live_light", {}).get(
                "provider_model_execution_requires_task_contract"
            )
            is True
            and runtime_mode_acceptance_rows.get("live_light", {}).get(
                "provider_model_execution_requires_execution_request"
            )
            is True
            and runtime_mode_acceptance_rows.get("live_full", {}).get("acceptance_status")
            == "reserved_disabled_requires_future_authorization"
            and runtime_mode_acceptance_rows.get("live_full", {}).get("page_open_task_allowed") is False
            and runtime_mode_acceptance_rows.get("live_full", {}).get("search_submit_task_allowed") is False
            and runtime_mode_acceptance_rows.get("live_full", {}).get("provider_model_execution_surface")
            == "reserved_none_now"
            and runtime_mode_acceptance_rows.get("live_full", {}).get("provider_model_direct_execution_allowed")
            is False
            and runtime_mode_acceptance_rows.get("live_full", {}).get(
                "provider_model_requires_explicit_post_task"
            )
            is False
            and runtime_mode_acceptance_rows.get("live_full", {}).get("full_pool_or_deep_scan_allowed") is False
            and all(
                row.get("schema_version") == "command_center_bootstrap_runtime_mode_acceptance.v1"
                and row.get("cache_get_external_calls") is False
                and row.get("react_initial_render_creates_task") is False
                and row.get("react_render_direct_provider_calls") is False
                and row.get("search_typing_creates_task") is False
                and row.get("fastapi_startup_creates_task") is False
                and row.get("token_key_exposure_allowed") is False
                and row.get("credential_values_exposed") is False
                and row.get("radar_candidate_is_buy_instruction") is False
                and row.get("deepseek_is_data_source") is False
                and row.get("deepseek_may_overwrite_numeric_or_action_fields") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("production_evidence") is False
                for row in runtime_mode_acceptance_rows.values()
            )
            and runtime_mode_acceptance.get("cache_only_default_offline") is True
            and runtime_mode_acceptance.get("manual_explicit_post_only") is True
            and runtime_mode_acceptance.get("manual_provider_model_surface")
            == "selected_explicit_post_task_only"
            and runtime_mode_acceptance.get("manual_provider_model_direct_execution_allowed") is False
            and runtime_mode_acceptance.get("manual_provider_model_requires_explicit_post_task") is True
            and runtime_mode_acceptance.get("live_light_bounded_background_task_only") is True
            and runtime_mode_acceptance.get("live_light_provider_model_surface")
            == "execution_request_post_task_only"
            and runtime_mode_acceptance.get("live_light_provider_model_direct_execution_allowed") is False
            and runtime_mode_acceptance.get("live_full_reserved_disabled") is True
            and runtime_mode_acceptance.get("all_modes_require_post_task_for_external_calls") is True
            and runtime_mode_acceptance.get("provider_model_direct_execution_allowed") is False
            and runtime_mode_acceptance.get("provider_model_execution_requires_execution_request") is True
            and runtime_mode_acceptance.get("frontend_visible") is True
            and runtime_mode_acceptance.get("frontend_editable") is False
            and runtime_mode_acceptance.get("frontend_writeback_allowed") is False
            and runtime_mode_acceptance.get("status_endpoint_writeback_allowed") is False
            and runtime_mode_acceptance.get("cache_get_external_calls") is False
            and runtime_mode_acceptance.get("react_initial_render_creates_task") is False
            and runtime_mode_acceptance.get("react_render_direct_provider_calls") is False
            and runtime_mode_acceptance.get("search_typing_creates_task") is False
            and runtime_mode_acceptance.get("fastapi_startup_creates_task") is False
            and runtime_mode_acceptance.get("token_key_exposure_allowed") is False
            and runtime_mode_acceptance.get("credential_values_exposed") is False
            and runtime_mode_acceptance.get("credential_env_key_names_included") is False
            and runtime_mode_acceptance.get("runtime_mode_acceptance_is_production_evidence") is False
            and runtime_mode_acceptance.get("production_live_light_complete") is False
            and runtime_mode_acceptance.get("external_calls_triggered") is False
            and runtime_mode_acceptance.get("tushare_called") is False
            and runtime_mode_acceptance.get("deepseek_called") is False
            and runtime_mode_acceptance.get("github_called") is False
            and runtime_mode_acceptance.get("contains_secret") is False
            and _dict(status.get("live_light")).get("runtime_mode_acceptance_contract_visible") is True
            and _dict(status.get("live_light")).get("runtime_mode_acceptance_row_count") == 4
            and _dict(status.get("live_light")).get("runtime_mode_acceptance_is_production_evidence") is False
            and _dict(status.get("policy")).get("runtime_mode_acceptance_contract_visible") is True
            and _dict(status.get("policy")).get("runtime_mode_acceptance_row_count") == 4
            and _dict(status.get("policy")).get("runtime_mode_acceptance_is_production_evidence") is False,
            f"runtime_mode_acceptance={runtime_mode_acceptance}",
        ),
        _row(
            "task_creation_invariant_contract_blocks_get_render_typing_task_sources",
            task_creation_invariant.get("schema_version") == "command_center_bootstrap_task_creation_invariant.v1"
            and task_creation_invariant.get("status") == "task_creation_invariant_visible_read_only"
            and task_creation_invariant.get("mode") == "live_light"
            and task_creation_invariant.get("surface_row_count") == 9
            and task_creation_invariant.get("allowed_task_surface_count") == 3
            and set(task_creation_rows)
            == {
                "fastapi_startup",
                "get_bootstrap_status",
                "get_cache_api",
                "react_initial_render",
                "react_after_cache_render_live_light_bootstrap",
                "search_typing",
                "safe_search_submit_autostart",
                "manual_button_post_task",
                "task_status_polling",
            }
            and task_creation_rows.get("fastapi_startup", {}).get("task_creation_allowed") is False
            and task_creation_rows.get("get_bootstrap_status", {}).get("task_creation_allowed") is False
            and task_creation_rows.get("get_cache_api", {}).get("task_creation_allowed") is False
            and task_creation_rows.get("react_initial_render", {}).get("task_creation_allowed") is False
            and task_creation_rows.get("search_typing", {}).get("task_creation_allowed") is False
            and task_creation_rows.get("task_status_polling", {}).get("task_creation_allowed") is False
            and task_creation_rows.get("react_after_cache_render_live_light_bootstrap", {}).get(
                "task_creation_allowed"
            )
            is True
            and task_creation_rows.get("react_after_cache_render_live_light_bootstrap", {}).get("route_or_component")
            == "POST /api/bootstrap/live-startup"
            and task_creation_rows.get("react_after_cache_render_live_light_bootstrap", {}).get("task_type")
            == "command_center_live_bootstrap"
            and task_creation_rows.get("react_after_cache_render_live_light_bootstrap", {}).get("requires_rate_limit")
            is True
            and task_creation_rows.get("react_after_cache_render_live_light_bootstrap", {}).get(
                "creates_provider_model_task"
            )
            is False
            and task_creation_rows.get("safe_search_submit_autostart", {}).get("task_creation_allowed") is True
            and task_creation_rows.get("safe_search_submit_autostart", {}).get("route_or_component")
            == "POST /api/candidate-radar/quant-projection"
            and task_creation_rows.get("safe_search_submit_autostart", {}).get("task_type")
            == "run_candidate_radar_quant_projection"
            and task_creation_rows.get("safe_search_submit_autostart", {}).get("requires_safe_symbol") is True
            and task_creation_rows.get("safe_search_submit_autostart", {}).get("requires_submit_autostart_config")
            is True
            and task_creation_rows.get("safe_search_submit_autostart", {}).get("creates_provider_model_task")
            is False
            and task_creation_rows.get("manual_button_post_task", {}).get("task_creation_allowed") is True
            and task_creation_rows.get("manual_button_post_task", {}).get("requires_user_action") is True
            and all(
                row.get("schema_version") == "command_center_bootstrap_task_creation_invariant.v1"
                and row.get("get_creates_task") is False
                and row.get("typing_creates_task") is False
                and row.get("render_direct_provider_calls") is False
                and row.get("external_calls_triggered_by_contract") is False
                and row.get("provider_model_execution_requires_execution_request") is True
                and row.get("task_success_is_production_evidence") is False
                and row.get("radar_candidate_is_buy_instruction") is False
                and row.get("token_key_exposure_allowed") is False
                and row.get("credential_values_exposed") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in task_creation_rows.values()
            )
            and task_creation_invariant.get("startup_task_creation_allowed") is False
            and task_creation_invariant.get("get_status_task_creation_allowed") is False
            and task_creation_invariant.get("get_cache_task_creation_allowed") is False
            and task_creation_invariant.get("react_initial_render_task_creation_allowed") is False
            and task_creation_invariant.get("search_typing_task_creation_allowed") is False
            and task_creation_invariant.get("task_status_polling_creates_task") is False
            and task_creation_invariant.get("live_light_after_cache_render_task_requires_rate_limit") is True
            and task_creation_invariant.get("safe_search_submit_requires_live_light_and_config") is True
            and task_creation_invariant.get("manual_task_creation_requires_explicit_user_action") is True
            and task_creation_invariant.get("provider_model_execution_requires_execution_request") is True
            and task_creation_invariant.get("contract_creates_task") is False
            and task_creation_invariant.get("contract_is_production_evidence") is False
            and task_creation_invariant.get("external_calls_triggered") is False
            and task_creation_invariant.get("tushare_called") is False
            and task_creation_invariant.get("deepseek_called") is False
            and task_creation_invariant.get("github_called") is False
            and task_creation_invariant.get("contains_secret") is False
            and task_creation_invariant.get("credential_values_exposed") is False
            and task_creation_invariant.get("credential_env_key_names_included") is False
            and _dict(status.get("live_light")).get("task_creation_invariant_contract_visible") is True
            and _dict(status.get("live_light")).get("task_creation_invariant_surface_row_count") == 9
            and _dict(status.get("live_light")).get("task_creation_invariant_allowed_surface_count") == 3
            and _dict(status.get("live_light")).get("task_creation_invariant_is_production_evidence") is False
            and _dict(status.get("policy")).get("task_creation_invariant_contract_visible") is True
            and _dict(status.get("policy")).get("task_creation_invariant_surface_row_count") == 9
            and _dict(status.get("policy")).get("task_creation_invariant_allowed_surface_count") == 3
            and _dict(status.get("policy")).get("task_creation_invariant_is_production_evidence") is False,
            f"task_creation_invariant={task_creation_invariant}",
        ),
        _row(
            "runtime_external_silence_contract_blocks_direct_provider_model_network_surfaces",
            external_silence.get("schema_version") == "command_center_runtime_external_silence_contract.v1"
            and external_silence.get("status") == "runtime_external_silence_visible_read_only"
            and external_silence.get("mode") == "live_light"
            and external_silence.get("silence_row_count") == 10
            and external_silence.get("local_post_exception_count") == 3
            and external_silence.get("direct_external_call_allowed_count") == 0
            and external_silence.get("task_creation_allowed_surface_count") == 3
            and external_silence.get("silent_read_surface_count") == 7
            and set(external_silence_rows)
            == {
                "fastapi_startup",
                "get_bootstrap_status",
                "get_cache_api",
                "react_initial_render",
                "react_after_cache_render_live_light_bootstrap",
                "search_typing",
                "safe_search_submit_autostart",
                "manual_button_post_task",
                "task_status_polling",
                "operator_summary_display",
            }
            and external_silence_rows.get("fastapi_startup", {}).get("local_backend_post_allowed") is False
            and external_silence_rows.get("get_bootstrap_status", {}).get("local_backend_post_allowed") is False
            and external_silence_rows.get("get_cache_api", {}).get("local_backend_post_allowed") is False
            and external_silence_rows.get("react_initial_render", {}).get("local_backend_post_allowed") is False
            and external_silence_rows.get("search_typing", {}).get("local_backend_post_allowed") is False
            and external_silence_rows.get("task_status_polling", {}).get("local_backend_post_allowed") is False
            and external_silence_rows.get("react_after_cache_render_live_light_bootstrap", {}).get(
                "local_backend_post_allowed"
            )
            is True
            and external_silence_rows.get("safe_search_submit_autostart", {}).get("local_backend_post_allowed")
            is True
            and external_silence_rows.get("manual_button_post_task", {}).get("local_backend_post_allowed") is True
            and external_silence_rows.get("react_after_cache_render_live_light_bootstrap", {}).get(
                "task_creation_allowed"
            )
            is True
            and external_silence_rows.get("safe_search_submit_autostart", {}).get("task_creation_allowed") is True
            and external_silence_rows.get("manual_button_post_task", {}).get("task_creation_allowed") is True
            and all(
                _dict(row).get("direct_external_calls_allowed") is False
                and _dict(row).get("direct_provider_calls_allowed") is False
                and _dict(row).get("direct_model_calls_allowed") is False
                and _dict(row).get("github_calls_allowed") is False
                and _dict(row).get("trading_calls_allowed") is False
                and _dict(row).get("reads_credential_values") is False
                and _dict(row).get("safe_summary_only") is True
                and _dict(row).get("provider_model_execution_requires_post_task") is True
                and _dict(row).get("provider_model_execution_requires_execution_request") is True
                and _dict(row).get("row_is_production_evidence") is False
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("tushare_called") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("github_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("does_not_execute_trades") is True
                and _dict(row).get("does_not_modify_strategy_action") is True
                for row in external_silence_rows.values()
            )
            and external_silence.get("provider_model_calls_must_use_post_task_worker_or_local_fallback") is True
            and external_silence.get("provider_model_execution_requires_execution_request") is True
            and external_silence.get("get_cache_direct_external_calls_allowed") is False
            and external_silence.get("react_render_direct_provider_calls_allowed") is False
            and external_silence.get("fastapi_startup_external_calls_allowed") is False
            and external_silence.get("search_typing_task_creation_allowed") is False
            and external_silence.get("task_status_polling_creates_task") is False
            and external_silence.get("operator_summary_creates_task") is False
            and external_silence.get("frontend_visible") is True
            and external_silence.get("frontend_editable") is False
            and external_silence.get("frontend_writeback_allowed") is False
            and external_silence.get("status_endpoint_writeback_allowed") is False
            and external_silence.get("contract_creates_task") is False
            and external_silence.get("contract_calls_provider_or_model") is False
            and external_silence.get("external_silence_contract_is_production_evidence") is False
            and external_silence.get("production_live_light_complete") is False
            and _dict(status.get("live_light")).get("runtime_external_silence_contract_visible") is True
            and _dict(status.get("live_light")).get("runtime_external_silence_row_count") == 10
            and _dict(status.get("live_light")).get("runtime_external_silence_local_post_exception_count") == 3
            and _dict(status.get("live_light")).get("runtime_external_silence_direct_external_call_allowed_count")
            == 0
            and _dict(status.get("live_light")).get("runtime_external_silence_is_production_evidence") is False
            and _dict(status.get("policy")).get("runtime_external_silence_contract_visible") is True
            and _dict(status.get("policy")).get("runtime_external_silence_row_count") == 10
            and _dict(status.get("policy")).get("runtime_external_silence_local_post_exception_count") == 3
            and _dict(status.get("policy")).get("runtime_external_silence_direct_external_call_allowed_count") == 0
            and _dict(status.get("policy")).get("runtime_external_silence_is_production_evidence") is False
            and external_silence.get("external_calls_triggered") is False
            and external_silence.get("tushare_called") is False
            and external_silence.get("deepseek_called") is False
            and external_silence.get("github_called") is False
            and external_silence.get("contains_secret") is False
            and external_silence.get("credential_values_exposed") is False
            and external_silence.get("credential_env_key_names_included") is False
            and external_silence.get("does_not_execute_trades") is True
            and external_silence.get("does_not_modify_strategy_action") is True,
            f"external_silence={external_silence}",
        ),
        _row(
            "runtime_hard_boundary_contract_aggregates_user_nonnegotiable_boundaries",
            hard_boundary.get("schema_version") == "command_center_runtime_hard_boundary_contract.v1"
            and hard_boundary.get("status") == "runtime_hard_boundaries_visible_read_only"
            and hard_boundary.get("mode") == "live_light"
            and hard_boundary.get("boundary_row_count") == 12
            and hard_boundary.get("passed_boundary_count") == 12
            and hard_boundary.get("blocking_boundary_count") == 0
            and set(hard_boundary_rows)
            == {
                "get_cache_api_no_direct_external_calls",
                "react_render_no_direct_provider_calls",
                "fastapi_startup_no_auto_external_calls",
                "external_work_requires_post_task_worker_or_local_fallback",
                "provider_calls_require_call_ledger",
                "deepseek_calls_require_model_ledger",
                "deepseek_not_data_source",
                "deepseek_no_price_holding_factor_zone_or_action_overwrite",
                "no_real_trading_or_auto_orders",
                "radar_candidate_not_buy_instruction",
                "token_key_never_frontend_log_packet_or_cache",
                "mock_receipt_matrix_sanitizer_not_production_evidence",
            }
            and all(
                _dict(row).get("passed") is True
                and _dict(row).get("row_is_production_evidence") is False
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("tushare_called") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("github_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("does_not_execute_trades") is True
                and _dict(row).get("does_not_modify_strategy_action") is True
                for row in hard_boundary_rows.values()
            )
            and hard_boundary.get("get_cache_api_direct_external_calls_allowed") is False
            and hard_boundary.get("react_render_direct_provider_calls_allowed") is False
            and hard_boundary.get("fastapi_startup_external_calls_allowed") is False
            and hard_boundary.get("external_work_requires_post_task_worker_or_local_fallback") is True
            and hard_boundary.get("call_ledger_required_for_provider_calls") is True
            and hard_boundary.get("model_ledger_required_for_deepseek_calls") is True
            and hard_boundary.get("deepseek_is_data_source") is False
            and hard_boundary.get("deepseek_may_overwrite_price") is False
            and hard_boundary.get("deepseek_may_overwrite_holding") is False
            and hard_boundary.get("deepseek_may_overwrite_factor") is False
            and hard_boundary.get("deepseek_may_overwrite_operation_zones") is False
            and hard_boundary.get("deepseek_may_modify_strategy_action") is False
            and hard_boundary.get("real_trading_allowed") is False
            and hard_boundary.get("auto_order_allowed") is False
            and hard_boundary.get("radar_candidate_is_buy_instruction") is False
            and hard_boundary.get("token_key_frontend_log_packet_cache_allowed") is False
            and hard_boundary.get("mock_receipt_matrix_sanitizer_are_production_evidence") is False
            and hard_boundary.get("frontend_visible") is True
            and hard_boundary.get("frontend_editable") is False
            and hard_boundary.get("frontend_writeback_allowed") is False
            and hard_boundary.get("status_endpoint_writeback_allowed") is False
            and hard_boundary.get("contract_creates_task") is False
            and hard_boundary.get("contract_calls_provider_or_model") is False
            and hard_boundary.get("contract_is_production_evidence") is False
            and _dict(status.get("live_light")).get("runtime_hard_boundary_contract_visible") is True
            and _dict(status.get("live_light")).get("runtime_hard_boundary_row_count") == 12
            and _dict(status.get("live_light")).get("runtime_hard_boundary_blocking_count") == 0
            and _dict(status.get("live_light")).get("runtime_hard_boundary_get_cache_external_calls_allowed")
            is False
            and _dict(status.get("live_light")).get("runtime_hard_boundary_react_render_provider_calls_allowed")
            is False
            and _dict(status.get("live_light")).get("runtime_hard_boundary_fastapi_startup_external_calls_allowed")
            is False
            and _dict(status.get("live_light")).get(
                "runtime_hard_boundary_post_task_worker_local_fallback_required"
            )
            is True
            and _dict(status.get("live_light")).get("runtime_hard_boundary_call_ledger_required") is True
            and _dict(status.get("live_light")).get(
                "runtime_hard_boundary_model_ledger_required_for_deepseek"
            )
            is True
            and _dict(status.get("live_light")).get("runtime_hard_boundary_deepseek_is_data_source")
            is False
            and _dict(status.get("live_light")).get("runtime_hard_boundary_real_trading_allowed")
            is False
            and _dict(status.get("live_light")).get(
                "runtime_hard_boundary_token_key_frontend_log_packet_cache_allowed"
            )
            is False
            and _dict(status.get("live_light")).get("runtime_hard_boundary_contract_is_production_evidence")
            is False
            and _dict(status.get("policy")).get("runtime_hard_boundary_contract_visible") is True
            and _dict(status.get("policy")).get("runtime_hard_boundary_row_count") == 12
            and _dict(status.get("policy")).get("runtime_hard_boundary_blocking_count") == 0
            and _dict(status.get("policy")).get("runtime_hard_boundary_get_cache_external_calls_allowed")
            is False
            and _dict(status.get("policy")).get("runtime_hard_boundary_react_render_provider_calls_allowed")
            is False
            and _dict(status.get("policy")).get("runtime_hard_boundary_fastapi_startup_external_calls_allowed")
            is False
            and _dict(status.get("policy")).get(
                "runtime_hard_boundary_post_task_worker_local_fallback_required"
            )
            is True
            and _dict(status.get("policy")).get("runtime_hard_boundary_call_ledger_required") is True
            and _dict(status.get("policy")).get("runtime_hard_boundary_model_ledger_required_for_deepseek")
            is True
            and _dict(status.get("policy")).get("runtime_hard_boundary_deepseek_is_data_source") is False
            and _dict(status.get("policy")).get("runtime_hard_boundary_real_trading_allowed") is False
            and _dict(status.get("policy")).get(
                "runtime_hard_boundary_token_key_frontend_log_packet_cache_allowed"
            )
            is False
            and _dict(status.get("policy")).get("runtime_hard_boundary_contract_is_production_evidence")
            is False
            and hard_boundary.get("external_calls_triggered") is False
            and hard_boundary.get("tushare_called") is False
            and hard_boundary.get("deepseek_called") is False
            and hard_boundary.get("github_called") is False
            and hard_boundary.get("contains_secret") is False
            and hard_boundary.get("does_not_execute_trades") is True
            and hard_boundary.get("does_not_modify_strategy_action") is True,
            f"hard_boundary={hard_boundary}",
        ),
        _row(
            "runtime_operator_summary_contract_is_cross_mode_read_only_guidance",
            runtime_operator_summary.get("schema_version")
            == "command_center_runtime_operator_summary_contract.v1"
            and runtime_operator_summary.get("status") == "runtime_operator_summary_visible_read_only"
            and runtime_operator_summary.get("mode") == "live_light"
            and runtime_operator_summary.get("summary_row_count") == 4
            and set(runtime_operator_rows) == {"cache_only", "manual", "live_light", "live_full"}
            and runtime_operator_rows.get("live_light", {}).get("active") is True
            and runtime_operator_rows.get("live_light", {}).get("display_status")
            == "bounded_background_task_after_cache_render"
            and runtime_operator_rows.get("cache_only", {}).get("display_status") == "safe_read_only_cache"
            and runtime_operator_summary.get("active_mode_operator_label") == "Live light"
            and runtime_operator_summary.get("active_mode_display_status")
            == "bounded_background_task_after_cache_render"
            and runtime_operator_summary.get("release_blocker_summary_visible") is True
            and runtime_operator_summary.get("release_blocker_source_contract")
            == "live_light_promotion_gate_contract"
            and runtime_operator_summary.get("release_real_provider_model_evidence_complete") is False
            and runtime_operator_summary.get("release_browser_nonblocking_runtime_evidence_required") is True
            and runtime_operator_summary.get("release_ledger_redaction_review_required") is True
            and runtime_operator_summary.get("release_fresh_local_gate_run_required") is True
            and runtime_operator_summary.get("release_remote_ci_status_known") is False
            and runtime_operator_summary.get("release_remote_ci_green") is False
            and runtime_operator_summary.get("release_github_api_called") is False
            and runtime_operator_summary.get("release_production_promotion_review_required") is True
            and runtime_operator_summary.get("release_ready_for_promotion") is False
            and runtime_operator_summary.get("release_local_contracts_are_production_evidence") is False
            and runtime_operator_summary.get("release_blocker_summary_is_production_evidence") is False
            and runtime_operator_summary.get("operator_trigger_policy_summary_visible") is True
            and runtime_operator_summary.get("operator_trigger_policy_source_contract")
            == "runtime_mode_acceptance_contract"
            and runtime_operator_summary.get("active_page_open_task_allowed") is True
            and runtime_operator_summary.get("active_search_submit_task_allowed") is True
            and runtime_operator_summary.get("active_manual_button_task_allowed") is True
            and runtime_operator_summary.get("active_live_light_background_task_allowed") is True
            and runtime_operator_summary.get("active_provider_model_execution_allowed") is False
            and runtime_operator_summary.get("active_provider_model_execution_surface")
            == "execution_request_post_task_only"
            and runtime_operator_summary.get("active_provider_model_direct_execution_allowed") is False
            and runtime_operator_summary.get("active_provider_model_requires_explicit_post_task") is True
            and runtime_operator_summary.get("active_provider_model_execution_requires_task_contract") is True
            and runtime_operator_summary.get("active_provider_model_execution_requires_execution_request")
            is True
            and runtime_operator_summary.get("active_full_pool_or_deep_scan_allowed") is False
            and runtime_operator_summary.get("trigger_policy_summary_is_production_evidence") is False
            and runtime_operator_summary.get("allowed_operator_action_count") == 4
            and runtime_operator_summary.get("blocked_operator_action_count") == 5
            and "create_or_reuse_rate_limited_bootstrap_task_after_cache_render"
            in _list(runtime_operator_summary.get("allowed_operator_actions"))
            and "safe_search_submit_may_create_local_projection_task"
            in _list(runtime_operator_summary.get("allowed_operator_actions"))
            and "provider_model_execution_without_execution_request"
            in _list(runtime_operator_summary.get("blocked_operator_actions"))
            and "production_promotion_from_local_contracts"
            in _list(runtime_operator_summary.get("blocked_operator_actions"))
            and all(
                _dict(row).get("trigger_policy_summary_visible") is True
                and _dict(row).get("trigger_policy_source_contract") == "runtime_mode_acceptance_contract"
                and _dict(row).get("frontend_visible") is True
                and _dict(row).get("frontend_editable") is False
                and _dict(row).get("frontend_writeback_allowed") is False
                and _dict(row).get("status_endpoint_writeback_allowed") is False
                and _dict(row).get("cache_get_creates_task") is False
                and _dict(row).get("react_initial_render_creates_task") is False
                and _dict(row).get("search_typing_creates_task") is False
                and _dict(row).get("operator_row_is_production_evidence") is False
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("tushare_called") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("github_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("does_not_execute_trades") is True
                and _dict(row).get("does_not_modify_strategy_action") is True
                for row in runtime_operator_rows.values()
            )
            and runtime_operator_rows.get("cache_only", {}).get("page_open_task_allowed") is False
            and runtime_operator_rows.get("cache_only", {}).get("search_submit_task_allowed") is False
            and runtime_operator_rows.get("cache_only", {}).get("manual_button_task_allowed") is False
            and runtime_operator_rows.get("cache_only", {}).get("provider_model_execution_allowed") is False
            and runtime_operator_rows.get("manual", {}).get("page_open_task_allowed") is False
            and runtime_operator_rows.get("manual", {}).get("search_submit_task_allowed") is False
            and runtime_operator_rows.get("manual", {}).get("manual_button_task_allowed") is True
            and runtime_operator_rows.get("manual", {}).get("provider_model_execution_allowed") is True
            and runtime_operator_rows.get("manual", {}).get("provider_model_execution_surface")
            == "selected_explicit_post_task_only"
            and runtime_operator_rows.get("manual", {}).get("provider_model_direct_execution_allowed") is False
            and runtime_operator_rows.get("manual", {}).get("provider_model_requires_explicit_post_task")
            is True
            and runtime_operator_rows.get("manual", {}).get("provider_model_execution_requires_task_contract")
            is True
            and runtime_operator_rows.get("live_light", {}).get("page_open_task_allowed") is True
            and runtime_operator_rows.get("live_light", {}).get("search_submit_task_allowed") is True
            and runtime_operator_rows.get("live_light", {}).get("manual_button_task_allowed") is True
            and runtime_operator_rows.get("live_light", {}).get("live_light_background_task_allowed") is True
            and runtime_operator_rows.get("live_light", {}).get("provider_model_execution_allowed") is False
            and runtime_operator_rows.get("live_light", {}).get("provider_model_execution_surface")
            == "execution_request_post_task_only"
            and runtime_operator_rows.get("live_light", {}).get("provider_model_direct_execution_allowed")
            is False
            and runtime_operator_rows.get("live_light", {}).get("provider_model_requires_explicit_post_task")
            is True
            and runtime_operator_rows.get("live_light", {}).get("provider_model_execution_requires_task_contract")
            is True
            and runtime_operator_rows.get("live_light", {}).get(
                "provider_model_execution_requires_execution_request"
            )
            is True
            and runtime_operator_rows.get("live_light", {}).get("full_pool_or_deep_scan_allowed") is False
            and runtime_operator_rows.get("live_full", {}).get("page_open_task_allowed") is False
            and runtime_operator_rows.get("live_full", {}).get("search_submit_task_allowed") is False
            and runtime_operator_rows.get("live_full", {}).get("manual_button_task_allowed") is False
            and runtime_operator_rows.get("live_full", {}).get("provider_model_execution_surface")
            == "reserved_none_now"
            and runtime_operator_rows.get("live_full", {}).get("provider_model_direct_execution_allowed") is False
            and runtime_operator_rows.get("live_full", {}).get("provider_model_requires_explicit_post_task")
            is False
            and runtime_operator_rows.get("live_full", {}).get("full_pool_or_deep_scan_allowed") is False
            and runtime_operator_summary.get("mode_rows_visible_required") is True
            and runtime_operator_summary.get("config_rows_visible_required") is True
            and runtime_operator_summary.get("config_ownership_visible_required") is True
            and runtime_operator_summary.get("runtime_vocab_source_visible_required") is True
            and runtime_operator_summary.get("runtime_mode_vocab_source")
            == safe_config.get("runtime_mode_vocab_source")
            and runtime_operator_summary.get("default_mode_source") == safe_config.get("default_mode_source")
            and runtime_operator_summary.get("external_execution_profile_vocab_source")
            == safe_config.get("external_execution_profile_vocab_source")
            and runtime_operator_summary.get("external_execution_profile_default_source")
            == safe_config.get("external_execution_profile_default_source")
            and runtime_operator_summary.get("effective_source_switches_visible_required") is True
            and runtime_operator_summary.get("latest_bootstrap_task_visible_required") is True
            and runtime_operator_summary.get("latest_search_quant_projection_visible_required") is True
            and runtime_operator_summary.get("provider_model_execution_flags_visible_required") is True
            and runtime_operator_summary.get("production_blockers_visible_required") is True
            and runtime_operator_summary.get("hard_boundary_summary_visible") is True
            and runtime_operator_summary.get("hard_boundary_source_contract") == "runtime_hard_boundary_contract"
            and runtime_operator_summary.get("hard_boundary_row_count") == hard_boundary.get("boundary_row_count")
            and runtime_operator_summary.get("hard_boundary_blocking_count")
            == hard_boundary.get("blocking_boundary_count")
            and runtime_operator_summary.get("hard_boundary_get_cache_external_calls_allowed") is False
            and runtime_operator_summary.get("hard_boundary_react_render_provider_calls_allowed") is False
            and runtime_operator_summary.get("hard_boundary_fastapi_startup_external_calls_allowed") is False
            and runtime_operator_summary.get("hard_boundary_post_task_worker_local_fallback_required") is True
            and runtime_operator_summary.get("hard_boundary_call_ledger_required") is True
            and runtime_operator_summary.get("hard_boundary_model_ledger_required_for_deepseek") is True
            and runtime_operator_summary.get("hard_boundary_deepseek_is_data_source") is False
            and runtime_operator_summary.get("hard_boundary_real_trading_allowed") is False
            and runtime_operator_summary.get("hard_boundary_token_key_frontend_log_packet_cache_allowed") is False
            and runtime_operator_summary.get("hard_boundary_summary_is_production_evidence") is False
            and runtime_operator_summary.get("cache_first_polling_summary_visible") is True
            and runtime_operator_summary.get("cache_first_polling_source_contract")
            == "runtime_cache_first_polling_contract"
            and runtime_operator_summary.get("cache_first_polling_schema_version")
            == cache_first_polling.get("schema_version")
            and runtime_operator_summary.get("cache_first_polling_phase_count")
            == cache_first_polling.get("phase_count")
            and runtime_operator_summary.get("cache_first_polling_cache_first_render_required") is True
            and runtime_operator_summary.get("cache_first_polling_task_polling_required") is True
            and runtime_operator_summary.get("cache_first_polling_success_refresh_required") is True
            and runtime_operator_summary.get("cache_first_polling_last_good_cache_required") is True
            and runtime_operator_summary.get("cache_first_polling_manual_retry_only_after_failure") is True
            and runtime_operator_summary.get("cache_first_polling_task_creation_allowed_phase_count")
            == cache_first_polling.get("task_creation_allowed_phase_count")
            and runtime_operator_summary.get("cache_first_polling_direct_external_call_allowed_phase_count")
            == cache_first_polling.get("direct_external_call_allowed_phase_count")
            and runtime_operator_summary.get("cache_first_polling_browser_evidence_complete") is False
            and runtime_operator_summary.get("cache_first_polling_summary_is_production_evidence") is False
            and runtime_operator_summary.get("safe_config_contract_status") == safe_config.get("status")
            and runtime_operator_summary.get("configured_source_switches_visible") is True
            and runtime_operator_summary.get("effective_source_switches_mode_gated") is True
            and runtime_operator_summary.get("effective_sources_enabled") is True
            and runtime_operator_summary.get("external_execution_profile_visible_required") is True
            and runtime_operator_summary.get("effective_external_execution_profile") == "light_provider_model"
            and runtime_operator_summary.get("external_execution_profile_provider_stage_allowed") is True
            and runtime_operator_summary.get("external_execution_profile_model_stage_allowed") is True
            and runtime_operator_summary.get("external_execution_profile_executor_implemented") is False
            and runtime_operator_summary.get("external_execution_profile_calls_provider_model_now") is False
            and runtime_operator_summary.get("provider_model_enablement_summary_visible") is True
            and runtime_operator_summary.get("provider_model_enablement_source_config")
            == "COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT"
            and runtime_operator_summary.get("provider_model_enablement_configured")
            == safe_config.get("configured_provider_model_enablement")
            and runtime_operator_summary.get("provider_model_enablement_effective") is False
            and runtime_operator_summary.get("provider_model_enablement_requires_live_light") is True
            and runtime_operator_summary.get("provider_model_enablement_requires_execution_request") is True
            and runtime_operator_summary.get("provider_model_enablement_requires_promotion") is True
            and runtime_operator_summary.get("provider_model_enablement_creates_task") is False
            and runtime_operator_summary.get("provider_model_enablement_creates_provider_model_task") is False
            and runtime_operator_summary.get("provider_model_enablement_calls_provider_model_now") is False
            and runtime_operator_summary.get("provider_model_enablement_frontend_writeback_allowed") is False
            and runtime_operator_summary.get("provider_model_enablement_summary_is_production_evidence")
            is False
            and runtime_operator_summary.get("operator_profile_source_rate_summary_visible") is True
            and runtime_operator_summary.get("operator_profile_source_rate_summary_status")
            == "profile_selected_executor_pending"
            and runtime_operator_summary.get("operator_rate_limit_seconds_visible_safe") == 600
            and runtime_operator_summary.get("config_ownership_row_count") == 13
            and runtime_operator_summary.get("config_reference_audit_id")
            == runtime_config_reference.get("config_audit_id")
            and runtime_operator_summary.get("config_ownership_audit_id")
            == runtime_config_ownership.get("ownership_audit_id")
            and runtime_operator_summary.get("config_audit_input_surface")
            == "safe_reference_and_ownership_rows_only"
            and runtime_operator_summary.get("config_audit_visible_required") is True
            and runtime_operator_summary.get("config_audit_includes_raw_values") is False
            and runtime_operator_summary.get("config_audit_includes_credential_values") is False
            and runtime_operator_summary.get("config_audit_is_production_evidence") is False
            and runtime_operator_summary.get("bootstrap_local_env_fallback_count") == 0
            and runtime_operator_summary.get("global_config_allowlist_promotion_pending_count") == 0
            and runtime_operator_summary.get("runtime_mode_acceptance_row_count") == 4
            and runtime_operator_summary.get("task_creation_invariant_surface_row_count") == 9
            and runtime_operator_summary.get("task_creation_invariant_allowed_surface_count") == 3
            and runtime_operator_summary.get("task_control_contract_visible") is True
            and runtime_operator_summary.get("task_control_row_count") == 2
            and runtime_operator_summary.get("task_control_cancel_route") == "POST /api/tasks/{task_id}/cancel"
            and runtime_operator_summary.get("task_control_retry_route") == "POST /api/tasks/{task_id}/retry"
            and runtime_operator_summary.get("task_control_manual_only") is True
            and runtime_operator_summary.get("task_control_auto_retry_enabled") is False
            and runtime_operator_summary.get("task_control_safe_reason_required") is True
            and runtime_operator_summary.get("task_control_call_ledger_required") is True
            and runtime_operator_summary.get("task_control_is_production_evidence") is False
            and runtime_operator_summary.get("operator_status_surface_count")
            == operator_status_contract.get("status_surface_count")
            and runtime_operator_summary.get("provider_model_handoff_contract_visible") is True
            and runtime_operator_summary.get("provider_model_handoff_row_count")
            == execution_request_handoff_contract.get("handoff_row_count")
            and runtime_operator_summary.get("provider_model_handoff_route")
            == "POST /api/bootstrap/provider-model-execution-request"
            and runtime_operator_summary.get("provider_model_handoff_route_implemented") is True
            and runtime_operator_summary.get("provider_model_handoff_receipt_service_implemented") is True
            and runtime_operator_summary.get("provider_model_handoff_creates_provider_model_task") is False
            and runtime_operator_summary.get("provider_model_handoff_is_production_evidence") is False
            and runtime_operator_summary.get("latest_bootstrap_task_found") is False
            and runtime_operator_summary.get("latest_bootstrap_task_status") == "no_bootstrap_task_found"
            and runtime_operator_summary.get("latest_acceptance_dry_run_visible_required") is True
            and runtime_operator_summary.get("latest_acceptance_dry_run_receipt_found")
            == latest_acceptance_dry_run_status.get("receipt_found")
            and runtime_operator_summary.get("latest_acceptance_dry_run_status")
            == latest_acceptance_dry_run_status.get("status")
            and runtime_operator_summary.get("latest_acceptance_dry_run_ready_for_execution_request")
            == latest_acceptance_dry_run_status.get("dry_run_ready_for_execution_request")
            and runtime_operator_summary.get("latest_acceptance_dry_run_lookup_creates_task") is False
            and runtime_operator_summary.get("latest_acceptance_dry_run_is_production_evidence") is False
            and runtime_operator_summary.get("latest_execution_request_visible_required") is True
            and runtime_operator_summary.get("latest_execution_request_receipt_found")
            == latest_execution_request_status.get("receipt_found")
            and runtime_operator_summary.get("latest_execution_request_status")
            == latest_execution_request_status.get("status")
            and runtime_operator_summary.get("latest_execution_request_ready")
            == latest_execution_request_status.get("local_execution_request_ready")
            and runtime_operator_summary.get("latest_execution_request_scope_hash_matches_latest") is False
            and runtime_operator_summary.get("latest_execution_request_lookup_creates_task") is False
            and runtime_operator_summary.get("latest_execution_request_is_production_evidence") is False
            and runtime_operator_summary.get("latest_quant_projection_task_found") is False
            and runtime_operator_summary.get("latest_quant_projection_status") == "no_quant_projection_task_found"
            and runtime_operator_summary.get("provider_model_task_created") is False
            and runtime_operator_summary.get("provider_model_task_dispatched") is False
            and runtime_operator_summary.get("provider_model_execution_implemented") is False
            and runtime_operator_summary.get("provider_model_operator_summary_is_production_evidence") is False
            and runtime_operator_summary.get("frontend_visible") is True
            and runtime_operator_summary.get("frontend_editable") is False
            and runtime_operator_summary.get("frontend_writeback_allowed") is False
            and runtime_operator_summary.get("status_endpoint_writeback_allowed") is False
            and runtime_operator_summary.get("status_get_creates_task") is False
            and runtime_operator_summary.get("cache_get_creates_task") is False
            and runtime_operator_summary.get("react_initial_render_creates_task") is False
            and runtime_operator_summary.get("react_render_direct_provider_calls") is False
            and runtime_operator_summary.get("search_typing_creates_task") is False
            and runtime_operator_summary.get("safe_summary_only") is True
            and runtime_operator_summary.get("raw_config_values_exposed") is False
            and runtime_operator_summary.get("raw_task_payload_visible_allowed") is False
            and runtime_operator_summary.get("raw_prompt_or_raw_model_output_visible_allowed") is False
            and runtime_operator_summary.get("credential_values_exposed") is False
            and runtime_operator_summary.get("credential_env_key_names_included") is False
            and runtime_operator_summary.get("latest_task_success_is_provider_model_evidence") is False
            and runtime_operator_summary.get("operator_summary_is_provider_execution_evidence") is False
            and runtime_operator_summary.get("operator_summary_is_model_execution_evidence") is False
            and runtime_operator_summary.get("operator_summary_is_production_evidence") is False
            and runtime_operator_summary.get("provider_execution_implemented") is False
            and runtime_operator_summary.get("model_execution_implemented") is False
            and runtime_operator_summary.get("production_live_light_complete") is False
            and _dict(status.get("live_light")).get("runtime_operator_summary_contract_visible") is True
            and _dict(status.get("live_light")).get("runtime_operator_active_mode") == "live_light"
            and _dict(status.get("live_light")).get("runtime_operator_active_display_status")
            == "bounded_background_task_after_cache_render"
            and _dict(status.get("live_light")).get("runtime_operator_release_blocker_summary_visible")
            is True
            and _dict(status.get("live_light")).get("runtime_operator_release_remote_ci_status_known")
            is False
            and _dict(status.get("live_light")).get("runtime_operator_release_remote_ci_green") is False
            and _dict(status.get("live_light")).get("runtime_operator_release_github_api_called") is False
            and _dict(status.get("live_light")).get("runtime_operator_release_fresh_local_gate_run_required")
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_release_production_promotion_review_required"
            )
            is True
            and _dict(status.get("live_light")).get("runtime_operator_release_ready_for_promotion") is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_release_local_contracts_are_production_evidence"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_release_blocker_summary_is_production_evidence"
            )
            is False
            and _dict(status.get("live_light")).get("runtime_operator_trigger_policy_summary_visible")
            is True
            and _dict(status.get("live_light")).get("runtime_operator_active_page_open_task_allowed")
            is True
            and _dict(status.get("live_light")).get("runtime_operator_active_search_submit_task_allowed")
            is True
            and _dict(status.get("live_light")).get("runtime_operator_active_manual_button_task_allowed")
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_active_live_light_background_task_allowed"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_active_provider_model_execution_allowed"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_active_provider_model_execution_surface"
            )
            == "execution_request_post_task_only"
            and _dict(status.get("live_light")).get(
                "runtime_operator_active_provider_model_direct_execution_allowed"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_active_provider_model_requires_explicit_post_task"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_active_provider_model_execution_requires_task_contract"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_active_provider_model_execution_requires_execution_request"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_active_full_pool_or_deep_scan_allowed"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_trigger_policy_summary_is_production_evidence"
            )
            is False
            and _dict(status.get("live_light")).get("runtime_operator_config_reference_audit_id")
            == runtime_config_reference.get("config_audit_id")
            and _dict(status.get("live_light")).get("runtime_operator_config_ownership_audit_id")
            == runtime_config_ownership.get("ownership_audit_id")
            and _dict(status.get("live_light")).get("runtime_operator_config_audit_uses_safe_rows_only")
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_summary_visible"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_source_config"
            )
            == "COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT"
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_configured"
            )
            == safe_config.get("configured_provider_model_enablement")
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_effective"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_requires_live_light"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_requires_execution_request"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_requires_promotion"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_creates_provider_model_task"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_calls_provider_model_now"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_enablement_is_production_evidence"
            )
            is False
            and _dict(status.get("live_light")).get("runtime_operator_task_control_visible") is True
            and _dict(status.get("live_light")).get("runtime_operator_task_control_row_count") == 2
            and _dict(status.get("live_light")).get("runtime_operator_task_control_manual_only") is True
            and _dict(status.get("live_light")).get("runtime_operator_task_control_auto_retry_enabled") is False
            and _dict(status.get("live_light")).get("runtime_operator_task_control_is_production_evidence") is False
            and _dict(status.get("live_light")).get("runtime_operator_provider_model_handoff_visible") is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_handoff_route_implemented"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_handoff_receipt_service_implemented"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_latest_acceptance_dry_run_receipt_found"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_latest_acceptance_dry_run_ready_for_execution_request"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_latest_execution_request_receipt_found"
            )
            is False
            and _dict(status.get("live_light")).get("runtime_operator_latest_execution_request_ready") is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_latest_execution_request_lookup_creates_task"
            )
            is False
            and _dict(status.get("live_light")).get("runtime_operator_provider_model_task_created") is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_execution_implemented"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_provider_model_is_production_evidence"
            )
            is False
            and _dict(status.get("live_light")).get("runtime_operator_summary_row_count") == 4
            and _dict(status.get("live_light")).get("runtime_operator_allowed_action_count") == 4
            and _dict(status.get("live_light")).get("runtime_operator_blocked_action_count") == 5
            and _dict(status.get("live_light")).get("runtime_operator_summary_is_production_evidence") is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_cache_first_polling_summary_visible"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_cache_first_polling_source_contract"
            )
            == "runtime_cache_first_polling_contract"
            and _dict(status.get("live_light")).get("runtime_operator_cache_first_polling_phase_count") == 7
            and _dict(status.get("live_light")).get(
                "runtime_operator_cache_first_polling_cache_first_render_required"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_cache_first_polling_task_polling_required"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_cache_first_polling_last_good_cache_required"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_operator_cache_first_polling_browser_evidence_complete"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_operator_cache_first_polling_summary_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("runtime_operator_summary_contract_visible") is True
            and _dict(status.get("policy")).get("runtime_operator_active_mode") == "live_light"
            and _dict(status.get("policy")).get("runtime_operator_active_display_status")
            == "bounded_background_task_after_cache_render"
            and _dict(status.get("policy")).get("runtime_operator_release_blocker_summary_visible") is True
            and _dict(status.get("policy")).get("runtime_operator_release_remote_ci_status_known") is False
            and _dict(status.get("policy")).get("runtime_operator_release_remote_ci_green") is False
            and _dict(status.get("policy")).get("runtime_operator_release_github_api_called") is False
            and _dict(status.get("policy")).get("runtime_operator_release_fresh_local_gate_run_required")
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_release_production_promotion_review_required"
            )
            is True
            and _dict(status.get("policy")).get("runtime_operator_release_ready_for_promotion") is False
            and _dict(status.get("policy")).get(
                "runtime_operator_release_local_contracts_are_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get(
                "runtime_operator_release_blocker_summary_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("runtime_operator_trigger_policy_summary_visible") is True
            and _dict(status.get("policy")).get("runtime_operator_active_page_open_task_allowed") is True
            and _dict(status.get("policy")).get("runtime_operator_active_search_submit_task_allowed") is True
            and _dict(status.get("policy")).get("runtime_operator_active_manual_button_task_allowed") is True
            and _dict(status.get("policy")).get(
                "runtime_operator_active_live_light_background_task_allowed"
            )
            is True
            and _dict(status.get("policy")).get("runtime_operator_active_provider_model_execution_allowed")
            is False
            and _dict(status.get("policy")).get("runtime_operator_active_provider_model_execution_surface")
            == "execution_request_post_task_only"
            and _dict(status.get("policy")).get(
                "runtime_operator_active_provider_model_direct_execution_allowed"
            )
            is False
            and _dict(status.get("policy")).get(
                "runtime_operator_active_provider_model_requires_explicit_post_task"
            )
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_active_provider_model_execution_requires_task_contract"
            )
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_active_provider_model_execution_requires_execution_request"
            )
            is True
            and _dict(status.get("policy")).get("runtime_operator_active_full_pool_or_deep_scan_allowed")
            is False
            and _dict(status.get("policy")).get(
                "runtime_operator_trigger_policy_summary_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("runtime_operator_config_reference_audit_id")
            == runtime_config_reference.get("config_audit_id")
            and _dict(status.get("policy")).get("runtime_operator_config_ownership_audit_id")
            == runtime_config_ownership.get("ownership_audit_id")
            and _dict(status.get("policy")).get("runtime_operator_config_audit_uses_safe_rows_only") is True
            and _dict(status.get("policy")).get(
                "runtime_operator_provider_model_enablement_summary_visible"
            )
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_provider_model_enablement_source_config"
            )
            == "COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT"
            and _dict(status.get("policy")).get("runtime_operator_provider_model_enablement_configured")
            == safe_config.get("configured_provider_model_enablement")
            and _dict(status.get("policy")).get("runtime_operator_provider_model_enablement_effective")
            is False
            and _dict(status.get("policy")).get(
                "runtime_operator_provider_model_enablement_requires_live_light"
            )
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_provider_model_enablement_requires_execution_request"
            )
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_provider_model_enablement_requires_promotion"
            )
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_provider_model_enablement_creates_provider_model_task"
            )
            is False
            and _dict(status.get("policy")).get(
                "runtime_operator_provider_model_enablement_calls_provider_model_now"
            )
            is False
            and _dict(status.get("policy")).get(
                "runtime_operator_provider_model_enablement_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("runtime_operator_task_control_visible") is True
            and _dict(status.get("policy")).get("runtime_operator_task_control_row_count") == 2
            and _dict(status.get("policy")).get("runtime_operator_task_control_manual_only") is True
            and _dict(status.get("policy")).get("runtime_operator_task_control_auto_retry_enabled") is False
            and _dict(status.get("policy")).get("runtime_operator_task_control_is_production_evidence") is False
            and _dict(status.get("policy")).get("runtime_operator_provider_model_handoff_visible") is True
            and _dict(status.get("policy")).get("runtime_operator_provider_model_handoff_route_implemented")
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_provider_model_handoff_receipt_service_implemented"
            )
            is True
            and _dict(status.get("policy")).get("runtime_operator_latest_acceptance_dry_run_receipt_found")
            is False
            and _dict(status.get("policy")).get(
                "runtime_operator_latest_acceptance_dry_run_ready_for_execution_request"
            )
            is False
            and _dict(status.get("policy")).get("runtime_operator_latest_execution_request_receipt_found")
            is False
            and _dict(status.get("policy")).get("runtime_operator_latest_execution_request_ready") is False
            and _dict(status.get("policy")).get(
                "runtime_operator_latest_execution_request_lookup_creates_task"
            )
            is False
            and _dict(status.get("policy")).get("runtime_operator_provider_model_task_created") is False
            and _dict(status.get("policy")).get("runtime_operator_provider_model_execution_implemented")
            is False
            and _dict(status.get("policy")).get("runtime_operator_provider_model_is_production_evidence")
            is False
            and _dict(status.get("policy")).get("runtime_operator_summary_row_count") == 4
            and _dict(status.get("policy")).get("runtime_operator_allowed_action_count") == 4
            and _dict(status.get("policy")).get("runtime_operator_blocked_action_count") == 5
            and _dict(status.get("policy")).get("runtime_operator_summary_is_production_evidence") is False
            and _dict(status.get("policy")).get("runtime_operator_cache_first_polling_summary_visible")
            is True
            and _dict(status.get("policy")).get("runtime_operator_cache_first_polling_source_contract")
            == "runtime_cache_first_polling_contract"
            and _dict(status.get("policy")).get("runtime_operator_cache_first_polling_phase_count") == 7
            and _dict(status.get("policy")).get(
                "runtime_operator_cache_first_polling_cache_first_render_required"
            )
            is True
            and _dict(status.get("policy")).get("runtime_operator_cache_first_polling_task_polling_required")
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_cache_first_polling_last_good_cache_required"
            )
            is True
            and _dict(status.get("policy")).get(
                "runtime_operator_cache_first_polling_browser_evidence_complete"
            )
            is False
            and _dict(status.get("policy")).get(
                "runtime_operator_cache_first_polling_summary_is_production_evidence"
            )
            is False
            and runtime_operator_summary.get("external_calls_triggered") is False
            and runtime_operator_summary.get("tushare_called") is False
            and runtime_operator_summary.get("deepseek_called") is False
            and runtime_operator_summary.get("github_called") is False
            and runtime_operator_summary.get("contains_secret") is False
            and runtime_operator_summary.get("does_not_execute_trades") is True
            and runtime_operator_summary.get("does_not_modify_strategy_action") is True,
            f"runtime_operator_summary={runtime_operator_summary}",
        ),
        _row(
            "live_light_rollout_roadmap_keeps_next_steps_pending_without_execution",
            rollout_roadmap.get("schema_version") == "command_center_live_light_rollout_roadmap.v1"
            and rollout_roadmap.get("status") == "live_light_rollout_roadmap_visible_execution_pending"
            and rollout_roadmap.get("mode") == "live_light"
            and rollout_roadmap.get("stage_count") == 9
            and rollout_roadmap.get("local_ready_stage_count") == 4
            and rollout_roadmap.get("production_evidence_complete_stage_count") == 0
            and rollout_roadmap.get("next_implementation_stage_key") == "stage_04_frontend_nonblocking_wiring"
            and rollout_roadmap.get("next_browser_stage_key") == "stage_04_frontend_nonblocking_wiring"
            and rollout_roadmap.get("next_execution_request_stage_key")
            == "stage_05_provider_model_execution_request_route"
            and rollout_roadmap.get("next_provider_stage_key") == "stage_06_tushare_light_provider_acceptance"
            and set(rollout_rows)
            == {
                "stage_01_mode_config_contracts",
                "stage_02_local_bootstrap_skeleton",
                "stage_03_search_submit_local_projection",
                "stage_04_frontend_nonblocking_wiring",
                "stage_05_provider_model_execution_request_route",
                "stage_06_tushare_light_provider_acceptance",
                "stage_07_deepseek_pro_after_data_acceptance",
                "stage_08_cache_lineage_and_output_surfaces",
                "stage_09_release_promotion",
            }
            and rollout_rows.get("stage_01_mode_config_contracts", {}).get("local_ready") is True
            and rollout_rows.get("stage_01_mode_config_contracts", {}).get("implementation_pending") is False
            and rollout_rows.get("stage_02_local_bootstrap_skeleton", {}).get("local_ready") is True
            and rollout_rows.get("stage_03_search_submit_local_projection", {}).get("status")
            == "backend_local_route_ready_frontend_wiring_pending"
            and rollout_rows.get("stage_03_search_submit_local_projection", {}).get("local_ready") is True
            and rollout_rows.get("stage_03_search_submit_local_projection", {}).get("local_ready_scope")
            == "backend_local_route_task_status_replay_and_contracts"
            and rollout_rows.get("stage_03_search_submit_local_projection", {}).get("frontend_wiring_pending")
            is True
            and rollout_rows.get("stage_03_search_submit_local_projection", {}).get(
                "browser_runtime_evidence_pending"
            )
            is True
            and rollout_rows.get("stage_03_search_submit_local_projection", {}).get("implementation_pending") is True
            and rollout_rows.get("stage_04_frontend_nonblocking_wiring", {}).get("status")
            == "frontend_wiring_and_browser_evidence_pending"
            and "runtime_cache_first_polling_contract"
            in _list(rollout_rows.get("stage_04_frontend_nonblocking_wiring", {}).get("current_evidence"))
            and rollout_rows.get("stage_05_provider_model_execution_request_route", {}).get("status")
            == "execution_request_route_registered_receipt_service_ready"
            and "runtime_operator_summary_contract"
            in _list(rollout_rows.get("stage_05_provider_model_execution_request_route", {}).get("current_evidence"))
            and rollout_rows.get("stage_05_provider_model_execution_request_route", {}).get(
                "local_receipt_service_ready"
            )
            is True
            and rollout_rows.get("stage_05_provider_model_execution_request_route", {}).get(
                "operator_readiness_visible"
            )
            is True
            and rollout_rows.get("stage_05_provider_model_execution_request_route", {}).get(
                "route_implemented"
            )
            is True
            and rollout_rows.get("stage_05_provider_model_execution_request_route", {}).get(
                "provider_model_task_creation_allowed"
            )
            is False
            and rollout_rows.get("stage_06_tushare_light_provider_acceptance", {}).get("status")
            == "real_tushare_call_ledger_pending_user_approved_run"
            and rollout_rows.get("stage_07_deepseek_pro_after_data_acceptance", {}).get("status")
            == "real_deepseek_model_ledger_pending_user_approved_run"
            and rollout_rows.get("stage_09_release_promotion", {}).get("status")
            == "production_promotion_pending_remote_ci_redaction_and_review"
            and all(
                row.get("schema_version") == "command_center_live_light_rollout_roadmap.v1"
                and row.get("creates_task") is False
                and row.get("cache_get_creates_task") is False
                and row.get("react_render_creates_task") is False
                and row.get("fastapi_startup_creates_task") is False
                and row.get("search_typing_creates_task") is False
                and row.get("provider_execution_implemented") is False
                and row.get("model_execution_implemented") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("credential_values_exposed") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                and row.get("production_evidence_complete") is False
                for row in rollout_rows.values()
            )
            and rollout_roadmap.get("frontend_wiring_pending") is True
            and rollout_roadmap.get("backend_local_search_projection_ready") is True
            and rollout_roadmap.get("execution_request_route_pending") is False
            and rollout_roadmap.get("execution_request_receipt_service_ready") is True
            and rollout_roadmap.get("execution_request_operator_readiness_visible") is True
            and rollout_roadmap.get("execution_request_provider_model_task_creation_allowed") is False
            and rollout_roadmap.get("real_tushare_call_ledger_pending") is True
            and rollout_roadmap.get("real_deepseek_model_ledger_pending") is True
            and rollout_roadmap.get("browser_nonblocking_evidence_pending") is True
            and rollout_roadmap.get("cache_lineage_writeback_pending") is True
            and rollout_roadmap.get("remote_ci_and_redaction_review_pending") is True
            and rollout_roadmap.get("provider_model_execution_requires_execution_request") is True
            and rollout_roadmap.get("rollout_roadmap_is_production_evidence") is False
            and rollout_roadmap.get("production_live_light_complete") is False
            and rollout_roadmap.get("creates_task") is False
            and rollout_roadmap.get("cache_get_creates_task") is False
            and rollout_roadmap.get("react_render_creates_task") is False
            and rollout_roadmap.get("fastapi_startup_creates_task") is False
            and rollout_roadmap.get("search_typing_creates_task") is False
            and rollout_roadmap.get("external_calls_triggered") is False
            and rollout_roadmap.get("tushare_called") is False
            and rollout_roadmap.get("deepseek_called") is False
            and rollout_roadmap.get("github_called") is False
            and rollout_roadmap.get("contains_secret") is False
            and rollout_roadmap.get("credential_values_exposed") is False
            and rollout_roadmap.get("credential_env_key_names_included") is False
            and _dict(status.get("live_light")).get("live_light_rollout_roadmap_contract_visible") is True
            and _dict(status.get("live_light")).get("live_light_rollout_roadmap_stage_count") == 9
            and _dict(status.get("live_light")).get("live_light_rollout_next_implementation_stage_key")
            == "stage_04_frontend_nonblocking_wiring"
            and _dict(status.get("live_light")).get("live_light_rollout_next_execution_request_stage_key")
            == "stage_05_provider_model_execution_request_route"
            and _dict(status.get("live_light")).get(
                "live_light_rollout_execution_request_receipt_service_ready"
            )
            is True
            and _dict(status.get("live_light")).get(
                "live_light_rollout_execution_request_operator_readiness_visible"
            )
            is True
            and _dict(status.get("live_light")).get("live_light_rollout_execution_request_route_pending")
            is False
            and _dict(status.get("live_light")).get(
                "live_light_rollout_execution_request_provider_model_task_creation_allowed"
            )
            is False
            and _dict(status.get("live_light")).get("live_light_rollout_roadmap_is_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_rollout_roadmap_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_rollout_roadmap_stage_count") == 9
            and _dict(status.get("policy")).get("live_light_rollout_next_implementation_stage_key")
            == "stage_04_frontend_nonblocking_wiring"
            and _dict(status.get("policy")).get("live_light_rollout_next_execution_request_stage_key")
            == "stage_05_provider_model_execution_request_route"
            and _dict(status.get("policy")).get(
                "live_light_rollout_execution_request_receipt_service_ready"
            )
            is True
            and _dict(status.get("policy")).get(
                "live_light_rollout_execution_request_operator_readiness_visible"
            )
            is True
            and _dict(status.get("policy")).get("live_light_rollout_execution_request_route_pending") is False
            and _dict(status.get("policy")).get(
                "live_light_rollout_execution_request_provider_model_task_creation_allowed"
            )
            is False
            and _dict(status.get("policy")).get("live_light_rollout_roadmap_is_production_evidence") is False,
            f"rollout_roadmap={rollout_roadmap}",
        ),
        _row(
            "live_light_source_switches_and_external_execution_profile_are_effective_without_executor",
            config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("configured_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("configured_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("configured_value_safe")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "configured_value_safe"
            )
            == "light_provider_model"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_value_safe") is True
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("effective_value_safe")
            == "light_provider_model"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_value_safe")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("mode_gate") == "live_light"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("mode_gate") == "live_light"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("mode_gate")
            == "live_light_and_frontend_enablement_promotion"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("mode_gate")
            == "live_light_post_task_worker_ledger"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("effective_status")
            == "effective_in_live_light"
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("effective_status")
            == "effective_in_live_light"
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("effective_status")
            == "release_switch_blocked_until_promotion"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("effective_status")
            == "profile_selected_executor_pending"
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("automation_effective") is True
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("automation_effective") is True
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("automation_effective")
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("automation_effective")
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("inactive_reason") == ""
            and config_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get("inactive_reason") == ""
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("inactive_reason")
            == "frontend_enablement_promotion_required"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get("inactive_reason")
            == "execution_engine_pending"
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "provider_stage_allowed_by_profile"
            )
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "model_stage_allowed_by_profile"
            )
            is True
            and config_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "calls_provider_model_now"
            )
            is False
            and config_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get("creates_task") is False
            and safe_config.get("configured_source_switches_visible") is True
            and safe_config.get("effective_source_switches_mode_gated") is True
            and safe_config.get("effective_tushare_on_open") is True
            and safe_config.get("effective_deepseek_on_open") is True
            and safe_config.get("configured_frontend_enablement") is True
            and safe_config.get("effective_frontend_enablement") is False
            and safe_config.get("frontend_enablement_creates_task") is False
            and safe_config.get("configured_external_execution_profile") == "light_provider_model"
            and safe_config.get("effective_external_execution_profile") == "light_provider_model"
            and safe_config.get("external_execution_profile_provider_stage_allowed") is True
            and safe_config.get("external_execution_profile_model_stage_allowed") is True
            and safe_config.get("external_execution_profile_executor_implemented") is False
            and safe_config.get("external_execution_profile_calls_provider_model_now") is False
            and safe_config.get("external_execution_profile_requires_post_task_worker_or_local_fallback") is True
            and safe_config.get("external_execution_profile_requires_call_ledger") is True
            and safe_config.get("external_execution_profile_requires_model_ledger_for_deepseek") is True
            and safe_config.get("configured_provider_model_enablement") is True
            and safe_config.get("effective_provider_model_enablement") is False
            and safe_config.get("provider_model_enablement_requires_execution_request") is True
            and safe_config.get("provider_model_enablement_requires_promotion") is True
            and safe_config.get("provider_model_enablement_creates_task") is False
            and safe_config.get("provider_model_enablement_creates_provider_model_task") is False
            and safe_config.get("provider_model_enablement_calls_provider_model_now") is False
            and safe_config.get("provider_model_enablement_frontend_writeback_allowed") is False
            and safe_config.get("effective_sources_enabled") is True
            and safe_config.get("manual_or_cache_only_switches_do_not_autostart") is False
            and safe_config.get("non_live_light_switches_do_not_autostart") is False
            and summary.get("actual_provider_execution_count") == 0
            and summary.get("actual_model_call_count") == 0
            and summary.get("external_calls_triggered") is False,
            f"config_rows={config_rows} safe_config={safe_config}",
        ),
        _row(
            "runtime_config_reference_contract_lists_mode_layered_config_without_execution",
            runtime_config_reference.get("schema_version") == "command_center_bootstrap_runtime_config_reference.v1"
            and runtime_config_reference.get("status") == "runtime_config_reference_visible_read_only"
            and runtime_config_reference.get("mode") == "live_light"
            and runtime_config_reference.get("config_reference_row_count") == 13
            and runtime_config_reference.get("runtime_config_names_source")
            == "config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES"
            and runtime_config_reference.get("runtime_config_names")
            == list(COMMAND_CENTER_RUNTIME_CONFIG_NAMES)
            and runtime_config_reference.get("runtime_config_name_count") == 13
            and runtime_config_reference.get("runtime_config_names_match_reference_rows") is True
            and runtime_config_reference.get("runtime_config_names_are_allowlisted") is True
            and runtime_config_reference.get("runtime_config_names_missing_from_allowlist") == []
            and runtime_config_reference.get("source_switch_count") == 3
            and runtime_config_reference.get("runtime_budget_config_count") == 2
            and _dict(runtime_config_reference.get("category_counts")).get("runtime_mode") == 1
            and _dict(runtime_config_reference.get("category_counts")).get("source_switch") == 3
            and _dict(runtime_config_reference.get("category_counts")).get("startup_autostart_switch") == 1
            and _dict(runtime_config_reference.get("category_counts")).get("external_execution_profile") == 1
            and _dict(runtime_config_reference.get("category_counts")).get("live_light_research_scope") == 1
            and _dict(runtime_config_reference.get("category_counts")).get("provider_model_release_switch") == 1
            and _dict(runtime_config_reference.get("category_counts")).get("frontend_release_switch") == 1
            and _dict(runtime_config_reference.get("category_counts")).get("runtime_budget") == 2
            and _dict(runtime_config_reference.get("category_counts")).get("model_label") == 1
            and _dict(runtime_config_reference.get("category_counts")).get("reserved_full_mode") == 1
            and len(str(runtime_config_reference.get("config_audit_id") or "")) == 16
            and runtime_config_reference.get("config_audit_algorithm") == "sha256_safe_reference_rows_v1"
            and runtime_config_reference.get("config_audit_input_surface") == "safe_reference_rows_only"
            and runtime_config_reference.get("config_audit_row_count") == 13
            and runtime_config_reference.get("config_audit_bound_to_mode") == "live_light"
            and runtime_config_reference.get("config_audit_includes_raw_values") is False
            and runtime_config_reference.get("config_audit_includes_credential_values") is False
            and runtime_config_reference.get("config_audit_is_production_evidence") is False
            and set(runtime_config_reference_rows)
            == {
                "COMMAND_CENTER_BOOTSTRAP_MODE",
                "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
                "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
                "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
                "COMMAND_CENTER_LIVE_STARTUP_AUTOSTART",
                "COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE",
                "COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE",
                "COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT",
                "COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT",
                "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
                "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
                "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL",
                "COMMAND_CENTER_LIVE_ALLOW_FULL_POOL",
            }
            and runtime_config_reference_rows.get("COMMAND_CENTER_BOOTSTRAP_MODE", {}).get("effective_value_safe")
            == "live_light"
            and runtime_config_reference_rows.get("COMMAND_CENTER_BOOTSTRAP_MODE", {}).get("cache_only_behavior")
            == "read_cache_only_no_external_calls"
            and runtime_config_reference_rows.get("COMMAND_CENTER_BOOTSTRAP_MODE", {}).get("manual_behavior")
            == "explicit_post_task_only"
            and runtime_config_reference_rows.get("COMMAND_CENTER_BOOTSTRAP_MODE", {}).get("live_light_behavior")
            == "bounded_background_task_after_cache_render_or_safe_submit"
            and runtime_config_reference_rows.get("COMMAND_CENTER_BOOTSTRAP_MODE", {}).get("live_full_behavior")
            == "reserved_disabled_requires_future_authorization"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get(
                "effective_value_safe"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get("mode_gate")
            == "live_light"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get(
                "creates_provider_model_task"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN", {}).get(
                "provider_execution_requires_execution_request"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get(
                "effective_value_safe"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get(
                "model_execution_requires_execution_request"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN", {}).get(
                "deepseek_is_data_source"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "effective_value_safe"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "automation_surface"
            )
            == "safe_search_submit_local_projection_task_only"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "provider_model_execution_requires_execution_request"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "bootstrap_local_env_fallback_removal_pending"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "bootstrap_local_env_fallback_removed"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "category"
            )
            == "startup_autostart_switch"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "configured_value_safe"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "effective_value_safe"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "mode_gate"
            )
            == "live_light_after_cache_render_and_sources_enabled"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "automation_surface"
            )
            == "react_after_cache_render_local_bootstrap_task_only"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "creates_local_background_task_only"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "creates_provider_model_task"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "provider_model_execution_requires_execution_request"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "category"
            )
            == "external_execution_profile"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "default_value_safe"
            )
            == COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "configured_value_safe"
            )
            == "light_provider_model"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "effective_value_safe"
            )
            == "light_provider_model"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "allowed_values"
            )
            == list(COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES)
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "mode_gate"
            )
            == "live_light_post_task_worker_ledger"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "automation_surface"
            )
            == "post_bootstrap_or_search_task_worker_only"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "provider_stage_allowed_by_profile"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "model_stage_allowed_by_profile"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "provider_execution_implemented"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "model_execution_implemented"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "calls_provider_model_now"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "requires_post_task_worker_or_local_fallback"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "requires_call_ledger"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "requires_model_ledger_for_deepseek"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "category"
            )
            == "live_light_research_scope"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "default_value_safe"
            )
            == COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "effective_value_safe"
            )
            == COMMAND_CENTER_DEFAULT_LIVE_LIGHT_RESEARCH_SCOPE
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "allowed_values"
            )
            == list(COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPES)
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "automation_surface"
            )
            == "stage_bundle_only_no_execution"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "provider_stage_allowed_by_scope"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "factor_light_allowed_by_scope"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "next_session_cache_allowed_by_scope"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "model_stage_allowed_by_scope"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "creates_task"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "creates_provider_model_task"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "calls_provider_model_now"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "category"
            )
            == "provider_model_release_switch"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "configured_value_safe"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "effective_value_safe"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "mode_gate"
            )
            == "live_light_and_provider_model_promotion"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "provider_model_task_creation_allowed"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "provider_model_execution_requires_execution_request"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "requires_call_ledger"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "requires_model_ledger_for_deepseek"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "category"
            )
            == "frontend_release_switch"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "configured_value_safe"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "effective_value_safe"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "mode_gate"
            )
            == "live_light_and_frontend_enablement_promotion"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "automation_surface"
            )
            == "frontend_enablement_release_switch_only_no_task"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "frontend_enablement_allowed"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "rollback_on_evidence_regression_required"
            )
            is True
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT", {}).get(
                "effective_value_safe"
            )
            == 2
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS", {}).get(
                "effective_value_safe"
            )
            == 600
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_DEEPSEEK_MODEL", {}).get(
                "automation_surface"
            )
            == "label_only_no_model_call"
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL", {}).get(
                "effective_value_safe"
            )
            is False
            and runtime_config_reference_rows.get("COMMAND_CENTER_LIVE_ALLOW_FULL_POOL", {}).get(
                "full_pool_on_open_allowed"
            )
            is False
            and runtime_config_reference.get("frontend_visible") is True
            and runtime_config_reference.get("frontend_editable") is False
            and runtime_config_reference.get("frontend_writeback_allowed") is False
            and runtime_config_reference.get("status_endpoint_writeback_allowed") is False
            and runtime_config_reference.get("provider_model_execution_requires_execution_request") is True
            and runtime_config_reference.get("config_reference_is_production_evidence") is False
            and runtime_config_reference.get("production_config_complete") is False
            and runtime_config_reference.get("raw_value_exposed") is False
            and runtime_config_reference.get("credential_values_exposed") is False
            and runtime_config_reference.get("credential_env_key_names_included") is False
            and runtime_config_reference.get("cache_get_creates_task") is False
            and runtime_config_reference.get("react_render_creates_task") is False
            and runtime_config_reference.get("fastapi_startup_creates_task") is False
            and runtime_config_reference.get("external_calls_triggered") is False
            and runtime_config_reference.get("tushare_called") is False
            and runtime_config_reference.get("deepseek_called") is False
            and runtime_config_reference.get("github_called") is False
            and runtime_config_reference.get("contains_secret") is False
            and _dict(status.get("live_light")).get("runtime_config_reference_contract_visible") is True
            and _dict(status.get("live_light")).get("runtime_config_reference_row_count") == 13
            and _dict(status.get("live_light")).get("runtime_config_reference_source_switch_count") == 3
            and _dict(status.get("live_light")).get("runtime_config_reference_audit_id")
            == runtime_config_reference.get("config_audit_id")
            and _dict(status.get("live_light")).get("runtime_config_reference_audit_uses_safe_rows_only") is True
            and _dict(status.get("live_light")).get("runtime_config_reference_is_production_evidence") is False
            and _dict(status.get("policy")).get("runtime_config_reference_contract_visible") is True
            and _dict(status.get("policy")).get("runtime_config_reference_row_count") == 13
            and _dict(status.get("policy")).get("runtime_config_reference_source_switch_count") == 3
            and _dict(status.get("policy")).get("runtime_config_reference_audit_id")
            == runtime_config_reference.get("config_audit_id")
            and _dict(status.get("policy")).get("runtime_config_reference_audit_uses_safe_rows_only") is True
            and _dict(status.get("policy")).get("runtime_config_reference_is_production_evidence") is False,
            f"runtime_config_reference={runtime_config_reference}",
        ),
        _row(
            "runtime_config_ownership_invariant_blocks_frontend_writeback_and_tracks_fallback",
            runtime_config_ownership.get("schema_version")
            == "command_center_bootstrap_runtime_config_ownership_invariant.v1"
            and runtime_config_ownership.get("status")
            == "runtime_config_ownership_invariant_visible_global_config_allowlist_promoted_frontend_default_off"
            and runtime_config_ownership.get("mode") == "live_light"
            and runtime_config_ownership.get("ownership_row_count") == 13
            and runtime_config_ownership.get("frontend_editable_row_count") == 0
            and runtime_config_ownership.get("frontend_writeback_allowed_count") == 0
            and runtime_config_ownership.get("status_endpoint_writeback_allowed_count") == 0
            and runtime_config_ownership.get("bootstrap_local_env_fallback_count") == 0
            and runtime_config_ownership.get("global_config_allowlist_promotion_pending_count") == 0
            and set(runtime_config_ownership_rows) == set(runtime_config_reference_rows)
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "ownership_status"
            )
            == "server_config_layer_owned_global_config_allowlist_promoted"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "current_read_path"
            )
            == "global_config_layer_only"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "target_read_path"
            )
            == "global_config_layer_only"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "bootstrap_local_env_fallback_available"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "bootstrap_local_env_fallback_is_temporary"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "bootstrap_local_env_fallback_removed"
            )
            is True
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "fallback_removal_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "requires_future_config_py_file_scope"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART", {}).get(
                "fallback_is_production_config_evidence"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "ownership_status"
            )
            == "server_config_layer_owned_global_config_allowlist_promoted_default_off"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "current_read_path"
            )
            == "global_config_layer_default_false_startup_autostart_guard"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "target_read_path"
            )
            == "global_config_layer_only"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "bootstrap_local_env_fallback_available"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "fallback_removal_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "requires_future_config_py_file_scope"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_STARTUP_AUTOSTART", {}).get(
                "fallback_is_production_config_evidence"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "ownership_status"
            )
            == "server_config_layer_owned_global_config_allowlist_promoted_default_plan_only"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "current_read_path"
            )
            == "global_config_layer_default_plan_only_external_execution_guard"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "target_read_path"
            )
            == "global_config_layer_only"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "bootstrap_local_env_fallback_available"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "fallback_removal_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "requires_future_config_py_file_scope"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE", {}).get(
                "fallback_is_production_config_evidence"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "ownership_status"
            )
            == "server_config_layer_owned_global_config_allowlist_promoted_default_research_scope"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "current_read_path"
            )
            == "global_config_layer_default_live_light_research_scope_guard"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "target_read_path"
            )
            == "global_config_layer_only"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "bootstrap_local_env_fallback_available"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "fallback_removal_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "requires_future_config_py_file_scope"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE", {}).get(
                "fallback_is_production_config_evidence"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "ownership_status"
            )
            == "server_config_layer_owned_global_config_allowlist_promoted_default_off"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "current_read_path"
            )
            == "global_config_layer_default_false_provider_model_enablement_guard"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "target_read_path"
            )
            == "global_config_layer_only"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "bootstrap_local_env_fallback_available"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "global_config_allowlist_promoted"
            )
            is True
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "fallback_removal_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "requires_future_config_py_file_scope"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT", {}).get(
                "fallback_is_production_config_evidence"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "ownership_status"
            )
            == "server_config_layer_owned_global_config_allowlist_promoted_default_off"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "current_read_path"
            )
            == "global_config_layer_default_false_release_switch_guard"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "target_read_path"
            )
            == "global_config_layer_only"
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "bootstrap_local_env_fallback_available"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "global_config_allowlist_promotion_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "fallback_removal_pending"
            )
            is False
            and runtime_config_ownership_rows.get("COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT", {}).get(
                "requires_future_config_py_file_scope"
            )
            is False
            and all(
                (
                    _dict(row).get("ownership_status") == "server_config_layer_owned"
                    or str(_dict(row).get("config") or "")
                    in {
                        "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART",
                        "COMMAND_CENTER_LIVE_STARTUP_AUTOSTART",
                        "COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE",
                        "COMMAND_CENTER_LIVE_LIGHT_RESEARCH_SCOPE",
                        "COMMAND_CENTER_LIVE_PROVIDER_MODEL_ENABLEMENT",
                        "COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT",
                    }
                )
                and _dict(row).get("frontend_visible") is True
                and _dict(row).get("frontend_editable") is False
                and _dict(row).get("frontend_writeback_allowed") is False
                and _dict(row).get("status_endpoint_writeback_allowed") is False
                and _dict(row).get("config_change_channel") == "server_config_layer_only"
                and _dict(row).get("config_source_of_truth") == "server_config_layer"
                and _dict(row).get("safe_value_visible_only") is True
                and _dict(row).get("raw_value_exposed") is False
                and _dict(row).get("credential_values_exposed") is False
                and _dict(row).get("credential_env_key_names_included") is False
                and _dict(row).get("config_row_is_production_evidence") is False
                and _dict(row).get("cache_get_creates_task") is False
                and _dict(row).get("react_render_creates_task") is False
                and _dict(row).get("fastapi_startup_creates_task") is False
                and _dict(row).get("search_typing_creates_task") is False
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("tushare_called") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("github_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("does_not_execute_trades") is True
                and _dict(row).get("does_not_modify_strategy_action") is True
                for row in runtime_config_ownership_rows.values()
            )
            and runtime_config_ownership.get("config_source_of_truth") == "server_config_layer"
            and runtime_config_ownership.get("operator_change_channel") == "server_config_layer_only"
            and runtime_config_ownership.get("frontend_visible") is True
            and runtime_config_ownership.get("frontend_editable") is False
            and runtime_config_ownership.get("frontend_writeback_allowed") is False
            and runtime_config_ownership.get("status_endpoint_writeback_allowed") is False
            and runtime_config_ownership.get("current_cycle_modifies_global_config_file") is False
            and runtime_config_ownership.get("current_cycle_file_limit_respected") is True
            and runtime_config_ownership.get("requires_future_config_py_file_scope") is False
            and runtime_config_ownership.get("bootstrap_local_env_fallback_removed") is True
            and runtime_config_ownership.get("bootstrap_local_env_fallback_removal_pending") is False
            and runtime_config_ownership.get("production_config_complete") is False
            and runtime_config_ownership.get("ownership_invariant_is_production_evidence") is False
            and runtime_config_ownership.get("linked_runtime_config_reference_schema")
            == "command_center_bootstrap_runtime_config_reference.v1"
            and runtime_config_ownership.get("linked_runtime_config_reference_audit_id")
            == runtime_config_reference.get("config_audit_id")
            and runtime_config_ownership.get("linked_search_submit_config_handoff_schema")
            == "command_center_search_quant_projection_submit_autostart_config_handoff.v1"
            and runtime_config_ownership.get("linked_search_submit_config_promotion_schema")
            == "command_center_search_quant_projection_submit_autostart_config_promotion.v1"
            and runtime_config_ownership.get("promotion_step_count") == 5
            and len(str(runtime_config_ownership.get("ownership_audit_id") or "")) == 16
            and runtime_config_ownership.get("ownership_audit_algorithm") == "sha256_safe_ownership_rows_v1"
            and runtime_config_ownership.get("ownership_audit_input_surface")
            == "safe_ownership_rows_and_reference_audit_id_only"
            and runtime_config_ownership.get("ownership_audit_row_count") == 13
            and runtime_config_ownership.get("ownership_audit_includes_raw_values") is False
            and runtime_config_ownership.get("ownership_audit_includes_credential_values") is False
            and runtime_config_ownership.get("ownership_audit_is_production_evidence") is False
            and runtime_config_ownership.get("raw_value_exposed") is False
            and runtime_config_ownership.get("credential_values_exposed") is False
            and runtime_config_ownership.get("credential_env_key_names_included") is False
            and runtime_config_ownership.get("cache_get_creates_task") is False
            and runtime_config_ownership.get("react_render_creates_task") is False
            and runtime_config_ownership.get("fastapi_startup_creates_task") is False
            and runtime_config_ownership.get("search_typing_creates_task") is False
            and _dict(status.get("live_light")).get("runtime_config_ownership_invariant_contract_visible")
            is True
            and _dict(status.get("live_light")).get("runtime_config_ownership_row_count") == 13
            and _dict(status.get("live_light")).get("runtime_config_ownership_audit_id")
            == runtime_config_ownership.get("ownership_audit_id")
            and _dict(status.get("live_light")).get("runtime_config_ownership_linked_reference_audit_id")
            == runtime_config_reference.get("config_audit_id")
            and _dict(status.get("live_light")).get("runtime_config_bootstrap_local_env_fallback_count") == 0
            and _dict(status.get("live_light")).get(
                "runtime_config_global_config_allowlist_promotion_pending_count"
            )
            == 0
            and _dict(status.get("live_light")).get("runtime_config_frontend_writeback_allowed") is False
            and _dict(status.get("live_light")).get("runtime_config_production_config_complete") is False
            and _dict(status.get("live_light")).get(
                "runtime_config_ownership_invariant_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("runtime_config_ownership_invariant_contract_visible")
            is True
            and _dict(status.get("policy")).get("runtime_config_ownership_row_count") == 13
            and _dict(status.get("policy")).get("runtime_config_ownership_audit_id")
            == runtime_config_ownership.get("ownership_audit_id")
            and _dict(status.get("policy")).get("runtime_config_ownership_linked_reference_audit_id")
            == runtime_config_reference.get("config_audit_id")
            and _dict(status.get("policy")).get("runtime_config_bootstrap_local_env_fallback_count") == 0
            and _dict(status.get("policy")).get(
                "runtime_config_global_config_allowlist_promotion_pending_count"
            )
            == 0
            and _dict(status.get("policy")).get("runtime_config_frontend_writeback_allowed") is False
            and _dict(status.get("policy")).get("runtime_config_production_config_complete") is False
            and _dict(status.get("policy")).get(
                "runtime_config_ownership_invariant_is_production_evidence"
            )
            is False
            and runtime_config_ownership.get("external_calls_triggered") is False
            and runtime_config_ownership.get("tushare_called") is False
            and runtime_config_ownership.get("deepseek_called") is False
            and runtime_config_ownership.get("github_called") is False
            and runtime_config_ownership.get("contains_secret") is False
            and runtime_config_ownership.get("does_not_execute_trades") is True
            and runtime_config_ownership.get("does_not_modify_strategy_action") is True,
            f"runtime_config_ownership={runtime_config_ownership}",
        ),
        _row(
            "live_light_provider_linkage_rows_are_planned_not_called",
            linkage.get("live_light_bootstrap_task_boundary", {}).get("status") == "available_after_cache_render"
            and linkage.get("live_light_bootstrap_task_boundary", {}).get("external_calls_allowed") is True
            and linkage.get("tushare_light_refresh", {}).get("status") == "planned_provider_pending_not_executed"
            and linkage.get("tushare_light_refresh", {}).get("tushare_called") is False
            and linkage.get("tushare_light_refresh", {}).get("provider_execution_implemented") is False
            and linkage.get("deepseek_pro_after_task", {}).get("status") == "planned_model_pending_not_executed"
            and linkage.get("deepseek_pro_after_task", {}).get("deepseek_called") is False
            and linkage.get("deepseek_pro_after_task", {}).get("model_execution_implemented") is False
            and linkage.get("github_probe_boundary", {}).get("live_light_on_open_allowed") is False
            and linkage.get("real_trading_boundary", {}).get("real_trading_connected") is False,
            f"linkage={linkage}",
        ),
        _row(
            "live_light_background_task_contract_allows_only_rate_limited_task_creation",
            background_contract.get("schema_version") == "command_center_live_light_background_task_contract.v1"
            and background_contract.get("status") == "ready_local_task_skeleton_no_provider_execution"
            and background_contract.get("mode") == "live_light"
            and background_contract.get("route") == "POST /api/bootstrap/live-startup"
            and background_contract.get("config_switch") == "COMMAND_CENTER_LIVE_STARTUP_AUTOSTART"
            and background_contract.get("startup_autostart_configured") is True
            and background_contract.get("startup_autostart_effective") is True
            and background_contract.get("auto_trigger_allowed") is True
            and background_contract.get("cache_get_creates_task") is False
            and background_contract.get("fastapi_startup_creates_task") is False
            and background_contract.get("react_initial_render_creates_task") is False
            and background_contract.get("react_render_calls_provider") is False
            and background_contract.get("initial_cache_render_required") is True
            and background_contract.get("creates_or_reuses_background_task_only") is True
            and background_contract.get("task_creation_rate_limited") is True
            and background_contract.get("rate_limit_seconds") == 600
            and background_contract.get("rate_limit_reuses_existing_task") is True
            and background_contract.get("rate_limit_skip_creates_new_task") is False
            and background_contract.get("session_dedupe_required") is True
            and background_contract.get("symbol_limit") == 2
            and background_contract.get("symbol_dedupe_required") is True
            and background_contract.get("symbol_limit_truncation_required") is True
            and background_contract.get("allowed_symbol_sources")
            == ["current_target", "searched_symbol", "symbols", "watchlist", "holdings"]
            and background_contract.get("allowed_scope")
            == "current_target_holdings_watchlist_searched_symbol_light_only"
            and background_contract.get("full_pool_scope_allowed") is False
            and background_contract.get("deep_scan_scope_allowed") is False
            and background_contract.get("payload_safe_only") is True
            and background_contract.get("payload_secret_fields_dropped") is True
            and _dict(status.get("policy")).get("live_light_background_task_rate_limit_reuses_existing_task")
            is True
            and _dict(status.get("policy")).get("live_light_background_task_scope_light_only") is True
            and _dict(status.get("policy")).get("live_light_background_task_full_pool_scope_allowed") is False
            and _dict(status.get("policy")).get("live_light_background_task_payload_safe_only") is True
            and background_contract.get("tushare_planned") is True
            and background_contract.get("deepseek_planned") is True
            and background_contract.get("provider_execution_implemented") is False
            and background_contract.get("model_execution_implemented") is False
            and background_contract.get("real_provider_model_execution_allowed_now") is False
            and background_contract.get("external_calls_must_use_post_task_worker_or_local_fallback") is True
            and background_contract.get("call_ledger_required") is True
            and background_contract.get("model_ledger_required_for_deepseek") is True
            and background_contract.get("ui_nonblocking_required") is True
            and background_contract.get("external_calls_triggered") is False
            and background_contract.get("tushare_called") is False
            and background_contract.get("deepseek_called") is False
            and background_contract.get("github_called") is False
            and background_contract.get("does_not_execute_trades") is True
            and background_contract.get("does_not_modify_strategy_action") is True,
            f"background_contract={background_contract}",
        ),
        _row(
            "live_light_startup_autostart_readiness_requires_cache_first_local_post_without_execution",
            startup_autostart_readiness.get("schema_version")
            == "command_center_live_light_startup_autostart_readiness_contract.v1"
            and startup_autostart_readiness.get("status")
            == "startup_autostart_readiness_visible_frontend_wiring_pending"
            and startup_autostart_readiness.get("mode") == "live_light"
            and startup_autostart_readiness.get("task_route") == "POST /api/bootstrap/live-startup"
            and startup_autostart_readiness.get("task_type") == "command_center_live_bootstrap"
            and startup_autostart_readiness.get("task_status_route") == "GET /api/tasks/{task_id}"
            and startup_autostart_readiness.get("trigger_surface") == "react_mounted_after_initial_cache_render"
            and startup_autostart_readiness.get("readiness_row_count") == 7
            and startup_autostart_readiness.get("condition_satisfied_row_count") == 7
            and startup_autostart_readiness.get("browser_evidence_collected_row_count") == 0
            and startup_autostart_readiness.get("readiness_evidence_complete_row_count") == 0
            and startup_autostart_readiness.get("blocking_readiness_row_count") == 7
            and startup_autostart_readiness.get("required_readiness_keys")
            == [
                "bootstrap_status_read_before_autostart",
                "initial_cache_render_completed",
                "live_light_mode_and_source_switch_effective",
                "single_local_post_task_boundary",
                "rate_limit_and_session_dedupe_visible",
                "task_polling_and_safe_failure_visible",
                "provider_model_execution_deferred",
            ]
            and startup_autostart_readiness.get("active_mode_live_light") is True
            and startup_autostart_readiness.get("sources_effective") is True
            and startup_autostart_readiness.get("startup_autostart_configured") is True
            and startup_autostart_readiness.get("startup_autostart_config_effective") is True
            and startup_autostart_readiness.get("frontend_startup_autostart_wiring_implemented") is False
            and startup_autostart_readiness.get("browser_runtime_evidence_complete") is False
            and startup_autostart_readiness.get("startup_autostart_effective_allowed") is False
            and startup_autostart_readiness.get("startup_autostart_creates_local_task_only") is True
            and startup_autostart_readiness.get("startup_autostart_provider_model_execution_allowed")
            is False
            and startup_autostart_readiness.get("cache_first_render_required") is True
            and startup_autostart_readiness.get("bootstrap_status_read_required") is True
            and startup_autostart_readiness.get("rate_limit_reuse_required") is True
            and startup_autostart_readiness.get("session_dedupe_required") is True
            and startup_autostart_readiness.get("task_polling_required") is True
            and startup_autostart_readiness.get("safe_failure_display_required") is True
            and startup_autostart_readiness.get("linked_background_task_schema_version")
            == "command_center_live_light_background_task_contract.v1"
            and startup_autostart_readiness.get("linked_background_task_auto_trigger_allowed") is True
            and startup_autostart_readiness.get("linked_background_task_rate_limit_seconds") == 600
            and startup_autostart_readiness.get("linked_cache_first_polling_schema_version")
            == "command_center_runtime_cache_first_polling_contract.v1"
            and startup_autostart_readiness.get("linked_cache_first_polling_phase_count") == 7
            and startup_autostart_readiness.get(
                "linked_cache_first_polling_task_creation_allowed_phase_count"
            )
            == 2
            and set(startup_autostart_readiness_rows)
            == {
                "bootstrap_status_read_before_autostart",
                "initial_cache_render_completed",
                "live_light_mode_and_source_switch_effective",
                "single_local_post_task_boundary",
                "rate_limit_and_session_dedupe_visible",
                "task_polling_and_safe_failure_visible",
                "provider_model_execution_deferred",
            }
            and [
                startup_autostart_readiness_rows.get(key, {}).get("readiness_order")
                for key in [
                    "bootstrap_status_read_before_autostart",
                    "initial_cache_render_completed",
                    "live_light_mode_and_source_switch_effective",
                    "single_local_post_task_boundary",
                    "rate_limit_and_session_dedupe_visible",
                    "task_polling_and_safe_failure_visible",
                    "provider_model_execution_deferred",
                ]
            ]
            == [1, 2, 3, 4, 5, 6, 7]
            and startup_autostart_readiness_rows.get(
                "bootstrap_status_read_before_autostart", {}
            ).get("linked_contract")
            == "runtime_operator_summary_contract"
            and startup_autostart_readiness_rows.get(
                "single_local_post_task_boundary", {}
            ).get("required_state")
            == "startup autostart may only call POST /api/bootstrap/live-startup"
            and startup_autostart_readiness_rows.get(
                "provider_model_execution_deferred", {}
            ).get("current_blocker")
            == "provider_model_execution_request_still_required"
            and all(
                row.get("required_before_frontend_startup_autostart") is True
                and row.get("condition_currently_satisfied") is True
                and row.get("browser_evidence_collected") is False
                and row.get("readiness_evidence_complete") is False
                and row.get("blocks_frontend_startup_wiring") is True
                and row.get("cache_get_creates_task") is False
                and row.get("react_initial_render_creates_task") is False
                and row.get("react_mounted_may_post_after_cache_render_only") is True
                and row.get("fastapi_startup_creates_task") is False
                and row.get("search_typing_creates_task") is False
                and row.get("creates_provider_model_task") is False
                and row.get("frontend_provider_call_allowed") is False
                and row.get("frontend_model_call_allowed") is False
                and row.get("provider_model_execution_requires_execution_request") is True
                and row.get("row_is_production_evidence") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in startup_autostart_readiness_rows.values()
            )
            and startup_autostart_readiness.get("cache_get_creates_task") is False
            and startup_autostart_readiness.get("react_initial_render_creates_task") is False
            and startup_autostart_readiness.get("react_render_calls_provider") is False
            and startup_autostart_readiness.get("fastapi_startup_creates_task") is False
            and startup_autostart_readiness.get("search_typing_creates_task") is False
            and startup_autostart_readiness.get("creates_provider_model_task") is False
            and startup_autostart_readiness.get("frontend_provider_call_allowed") is False
            and startup_autostart_readiness.get("frontend_model_call_allowed") is False
            and startup_autostart_readiness.get("provider_execution_implemented") is False
            and startup_autostart_readiness.get("model_execution_implemented") is False
            and startup_autostart_readiness.get("provider_model_execution_requires_execution_request") is True
            and startup_autostart_readiness.get("external_calls_triggered") is False
            and startup_autostart_readiness.get("tushare_called") is False
            and startup_autostart_readiness.get("deepseek_called") is False
            and startup_autostart_readiness.get("github_called") is False
            and startup_autostart_readiness.get("contains_secret") is False
            and startup_autostart_readiness.get("credential_values_exposed") is False
            and startup_autostart_readiness.get("credential_env_key_names_included") is False
            and startup_autostart_readiness.get("does_not_execute_trades") is True
            and startup_autostart_readiness.get("does_not_modify_strategy_action") is True
            and startup_autostart_readiness.get("contract_is_production_evidence") is False
            and startup_autostart_readiness.get("production_live_light_complete") is False
            and _dict(status.get("live_light")).get("startup_autostart_readiness_contract_visible") is True
            and _dict(status.get("live_light")).get("startup_autostart_readiness_row_count") == 7
            and _dict(status.get("live_light")).get("startup_autostart_condition_satisfied_row_count")
            == 7
            and _dict(status.get("live_light")).get("startup_autostart_frontend_wiring_implemented")
            is False
            and _dict(status.get("live_light")).get("startup_autostart_browser_evidence_complete")
            is False
            and _dict(status.get("live_light")).get("startup_autostart_effective_allowed") is False
            and _dict(status.get("live_light")).get("startup_autostart_readiness_is_production_evidence")
            is False
            and _dict(status.get("policy")).get("live_light_startup_autostart_readiness_contract_visible")
            is True
            and _dict(status.get("policy")).get("live_light_startup_autostart_readiness_row_count")
            == 7
            and _dict(status.get("policy")).get(
                "live_light_startup_autostart_condition_satisfied_row_count"
            )
            == 7
            and _dict(status.get("policy")).get(
                "live_light_startup_autostart_frontend_wiring_implemented"
            )
            is False
            and _dict(status.get("policy")).get(
                "live_light_startup_autostart_browser_evidence_complete"
            )
            is False
            and _dict(status.get("policy")).get("live_light_startup_autostart_effective_allowed")
            is False
            and _dict(status.get("policy")).get(
                "live_light_startup_autostart_readiness_is_production_evidence"
            )
            is False,
            f"startup_autostart_readiness={startup_autostart_readiness}",
        ),
        _row(
            "live_light_unified_startup_task_contract_links_startup_provider_model_and_ui_polling_without_execution",
            unified_startup_contract.get("schema_version")
            == "command_center_live_light_unified_startup_task_contract.v1"
            and unified_startup_contract.get("status")
            == "unified_startup_task_contract_visible_executor_pending"
            and unified_startup_contract.get("mode") == "live_light"
            and unified_startup_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and unified_startup_contract.get("task_type") == "command_center_live_bootstrap"
            and unified_startup_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and unified_startup_contract.get("trigger_surface")
            == "react_mounted_after_initial_cache_render_or_safe_search_submit"
            and unified_startup_contract.get("stage_count") == 8
            and unified_startup_contract.get("required_stage_keys")
            == [
                "cache_first_status_read",
                "startup_task_envelope",
                "scope_resolution",
                "tushare_light_refresh",
                "factor_light_runtime",
                "next_session_cache_refresh",
                "deepseek_pro_explanation",
                "ui_polling_and_cache_refresh",
            ]
            and set(unified_startup_rows)
            == {
                "cache_first_status_read",
                "startup_task_envelope",
                "scope_resolution",
                "tushare_light_refresh",
                "factor_light_runtime",
                "next_session_cache_refresh",
                "deepseek_pro_explanation",
                "ui_polling_and_cache_refresh",
            }
            and [
                unified_startup_rows.get(key, {}).get("stage_order")
                for key in [
                    "cache_first_status_read",
                    "startup_task_envelope",
                    "scope_resolution",
                    "tushare_light_refresh",
                    "factor_light_runtime",
                    "next_session_cache_refresh",
                    "deepseek_pro_explanation",
                    "ui_polling_and_cache_refresh",
                ]
            ]
            == [1, 2, 3, 4, 5, 6, 7, 8]
            and unified_startup_rows.get("cache_first_status_read", {}).get("route")
            == "GET /api/bootstrap/status"
            and unified_startup_rows.get("startup_task_envelope", {}).get("current_runtime")
            == "local_task_skeleton"
            and unified_startup_rows.get("tushare_light_refresh", {}).get("future_external_provider")
            == "tushare"
            and unified_startup_rows.get("tushare_light_refresh", {}).get("allowed_apis")
            == ["trade_cal_if_needed", "daily", "daily_basic", "moneyflow"]
            and unified_startup_rows.get("tushare_light_refresh", {}).get("source_switch_effective")
            is True
            and unified_startup_rows.get("tushare_light_refresh", {}).get("external_execution_profile")
            == "light_provider_model"
            and unified_startup_rows.get("tushare_light_refresh", {}).get("profile_required")
            == "light_provider_or_light_provider_model"
            and unified_startup_rows.get("tushare_light_refresh", {}).get("profile_stage_allowed")
            is True
            and unified_startup_rows.get("tushare_light_refresh", {}).get("profile_inactive_reason") == ""
            and unified_startup_rows.get("tushare_light_refresh", {}).get("requires_execution_request_now")
            is True
            and unified_startup_rows.get("factor_light_runtime", {}).get("stage_kind") == "local_compute"
            and unified_startup_rows.get("next_session_cache_refresh", {}).get("stage_kind")
            == "local_compute"
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("future_external_provider")
            == "deepseek"
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("external_execution_profile")
            == "light_provider_model"
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("profile_required")
            == "light_provider_model"
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("profile_stage_allowed")
            is True
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("profile_inactive_reason") == ""
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("deepseek_model")
            == "contract-live-pro"
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("allowed_output_fields")
            == [
                "summary",
                "support_notes",
                "suppress_notes",
                "conflict_notes",
                "missing_data_notes",
                "discipline_notes",
            ]
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("source_switch_effective")
            is True
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("requires_data_ready")
            is True
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("requires_model_ledger")
            is True
            and unified_startup_rows.get("deepseek_pro_explanation", {}).get("deepseek_is_data_source")
            is False
            and all(
                _dict(row).get("stage_status_must_be_pollable") is True
                and _dict(row).get("safe_skip_allowed") is True
                and _dict(row).get("cache_get_may_execute_stage") is False
                and _dict(row).get("react_render_may_execute_stage") is False
                and _dict(row).get("fastapi_startup_may_execute_stage") is False
                and _dict(row).get("search_typing_may_execute_stage") is False
                and _dict(row).get("provider_or_model_execution_allowed_now") is False
                and _dict(row).get("provider_execution_implemented") is False
                and _dict(row).get("model_execution_implemented") is False
                and _dict(row).get("worker_dispatch_implemented") is False
                and _dict(row).get("local_compute_may_synthesize_provider_rows") is False
                and _dict(row).get("local_compute_may_synthesize_model_output") is False
                and _dict(row).get("deepseek_may_overwrite_numeric_or_action_fields") is False
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("tushare_called") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("github_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("does_not_execute_trades") is True
                and _dict(row).get("does_not_modify_strategy_action") is True
                and _dict(row).get("does_not_modify_prices_positions_or_operation_zones") is True
                and _dict(row).get("row_is_production_evidence") is False
                for row in unified_startup_rows.values()
            )
            and unified_startup_contract.get("symbol_limit") == 2
            and unified_startup_contract.get("rate_limit_seconds") == 600
            and unified_startup_contract.get("allowed_symbol_sources")
            == ["current_target", "searched_symbol", "symbols", "watchlist", "holdings"]
            and unified_startup_contract.get("allowed_light_tushare_apis")
            == ["trade_cal_if_needed", "daily", "daily_basic", "moneyflow"]
            and unified_startup_contract.get("deepseek_model") == "contract-live-pro"
            and unified_startup_contract.get("external_execution_profile") == "light_provider_model"
            and unified_startup_contract.get("external_execution_profile_provider_stage_allowed") is True
            and unified_startup_contract.get("external_execution_profile_model_stage_allowed") is True
            and unified_startup_contract.get("external_execution_profile_executor_implemented") is False
            and unified_startup_contract.get("external_execution_profile_calls_provider_model_now") is False
            and unified_startup_contract.get("provider_stage_planned_by_profile") is True
            and unified_startup_contract.get("model_stage_planned_by_profile") is True
            and unified_startup_contract.get("active_mode_live_light") is True
            and unified_startup_contract.get("sources_effective") is True
            and unified_startup_contract.get("live_light_background_task_allowed_after_cache_render")
            is True
            and unified_startup_contract.get("cache_first_render_required") is True
            and unified_startup_contract.get("post_task_boundary_required") is True
            and unified_startup_contract.get("worker_or_local_fallback_required") is True
            and unified_startup_contract.get("ui_nonblocking_required") is True
            and unified_startup_contract.get("task_status_polling_required") is True
            and unified_startup_contract.get("rate_limit_required") is True
            and unified_startup_contract.get("session_dedupe_required") is True
            and unified_startup_contract.get("call_ledger_required") is True
            and unified_startup_contract.get("model_ledger_required_for_deepseek") is True
            and unified_startup_contract.get("provider_model_execution_requires_execution_request_now")
            is True
            and unified_startup_contract.get("future_live_light_provider_model_stage_inside_startup_task")
            is True
            and unified_startup_contract.get("future_external_execution_requires_worker_or_local_fallback")
            is True
            and unified_startup_contract.get("external_execution_profile_required_for_provider_model_stages")
            is True
            and unified_startup_contract.get("cache_get_creates_task") is False
            and unified_startup_contract.get("status_get_creates_task") is False
            and unified_startup_contract.get("react_initial_render_creates_task") is False
            and unified_startup_contract.get("react_render_calls_provider") is False
            and unified_startup_contract.get("fastapi_startup_creates_task") is False
            and unified_startup_contract.get("search_typing_creates_task") is False
            and unified_startup_contract.get("frontend_direct_provider_call_allowed") is False
            and unified_startup_contract.get("frontend_direct_model_call_allowed") is False
            and unified_startup_contract.get("provider_execution_implemented") is False
            and unified_startup_contract.get("model_execution_implemented") is False
            and unified_startup_contract.get("worker_dispatch_implemented") is False
            and unified_startup_contract.get("celery_dispatch_implemented") is False
            and unified_startup_contract.get("scheduler_auto_dispatch_allowed") is False
            and unified_startup_contract.get("deepseek_is_data_source") is False
            and unified_startup_contract.get("deepseek_may_overwrite_numeric_or_action_fields") is False
            and unified_startup_contract.get("radar_candidate_is_buy_instruction") is False
            and unified_startup_contract.get("token_key_exposure_allowed") is False
            and unified_startup_contract.get("credential_values_exposed") is False
            and unified_startup_contract.get("credential_env_key_names_included") is False
            and unified_startup_contract.get("linked_background_task_schema_version")
            == "command_center_live_light_background_task_contract.v1"
            and unified_startup_contract.get("linked_stage_dependency_schema_version")
            == "command_center_live_light_stage_dependency_contract.v1"
            and unified_startup_contract.get("linked_stage_dependency_stage_count") == 9
            and unified_startup_contract.get("linked_worker_dispatch_schema_version")
            == "command_center_live_light_worker_dispatch_contract.v1"
            and unified_startup_contract.get("linked_worker_dispatch_row_count") == 5
            and unified_startup_contract.get("linked_startup_readiness_schema_version")
            == "command_center_live_light_startup_autostart_readiness_contract.v1"
            and unified_startup_contract.get("linked_startup_readiness_row_count") == 7
            and unified_startup_contract.get("external_calls_triggered") is False
            and unified_startup_contract.get("tushare_called") is False
            and unified_startup_contract.get("deepseek_called") is False
            and unified_startup_contract.get("github_called") is False
            and unified_startup_contract.get("contains_secret") is False
            and unified_startup_contract.get("does_not_execute_trades") is True
            and unified_startup_contract.get("does_not_modify_strategy_action") is True
            and unified_startup_contract.get("does_not_modify_prices_positions_or_operation_zones")
            is True
            and unified_startup_contract.get("unified_startup_task_contract_is_execution_evidence")
            is False
            and unified_startup_contract.get("unified_startup_task_contract_is_production_evidence")
            is False
            and unified_startup_contract.get("production_live_light_complete") is False
            and _dict(status.get("live_light")).get("unified_startup_task_contract_visible") is True
            and _dict(status.get("live_light")).get("unified_startup_task_stage_count") == 8
            and _dict(status.get("live_light")).get("unified_startup_task_route")
            == "POST /api/bootstrap/live-startup"
            and _dict(status.get("live_light")).get(
                "unified_startup_task_provider_execution_implemented"
            )
            is False
            and _dict(status.get("live_light")).get(
                "unified_startup_task_model_execution_implemented"
            )
            is False
            and _dict(status.get("live_light")).get(
                "unified_startup_task_worker_dispatch_implemented"
            )
            is False
            and _dict(status.get("live_light")).get("unified_startup_task_is_production_evidence")
            is False
            and _dict(status.get("policy")).get("live_light_unified_startup_task_contract_visible")
            is True
            and _dict(status.get("policy")).get("live_light_unified_startup_task_stage_count") == 8
            and _dict(status.get("policy")).get("live_light_unified_startup_task_route")
            == "POST /api/bootstrap/live-startup"
            and _dict(status.get("policy")).get(
                "live_light_unified_startup_task_provider_execution_implemented"
            )
            is False
            and _dict(status.get("policy")).get(
                "live_light_unified_startup_task_model_execution_implemented"
            )
            is False
            and _dict(status.get("policy")).get(
                "live_light_unified_startup_task_worker_dispatch_implemented"
            )
            is False
            and _dict(status.get("policy")).get("live_light_unified_startup_task_is_production_evidence")
            is False,
            f"unified_startup_contract={unified_startup_contract}",
        ),
        _row(
            "live_light_scope_intake_contract_normalizes_symbols_without_external_scope_expansion",
            scope_intake_contract.get("schema_version") == "command_center_live_light_scope_intake_contract.v1"
            and scope_intake_contract.get("status") == "scope_intake_contract_visible_normalization_pending"
            and scope_intake_contract.get("mode") == "live_light"
            and scope_intake_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and scope_intake_contract.get("search_quant_projection_route")
            == "POST /api/candidate-radar/quant-projection"
            and scope_intake_contract.get("allowed_symbol_sources")
            == ["current_target", "searched_symbol", "symbols", "watchlist", "holdings"]
            and scope_intake_contract.get("default_symbol_source_order")
            == ["current_target", "searched_symbol", "symbols", "watchlist", "holdings"]
            and scope_intake_contract.get("symbol_limit") == 2
            and scope_intake_contract.get("symbol_normalization_required") is True
            and scope_intake_contract.get("symbol_dedupe_required") is True
            and scope_intake_contract.get("symbol_limit_truncation_required") is True
            and scope_intake_contract.get("empty_symbol_list_allowed") is True
            and scope_intake_contract.get("empty_symbol_list_status")
            == "scope_empty_local_task_allowed_no_provider_execution"
            and scope_intake_contract.get("scope_hash_required") is True
            and scope_intake_contract.get("scope_hash_algorithm") == "sha256_json_sorted_safe_payload"
            and scope_intake_contract.get("scope_hash_excludes_secret_fields") is True
            and scope_intake_contract.get("safe_payload_required") is True
            and scope_intake_contract.get("secret_like_payload_fields_dropped") is True
            and scope_intake_contract.get("raw_user_input_logged") is False
            and scope_intake_contract.get("raw_user_input_cached") is False
            and scope_intake_contract.get("frontend_packet_may_contain_raw_query") is False
            and scope_intake_contract.get("cache_get_may_expand_scope") is False
            and scope_intake_contract.get("react_render_may_expand_scope") is False
            and scope_intake_contract.get("fastapi_startup_may_expand_scope") is False
            and scope_intake_contract.get("search_typing_may_create_task") is False
            and scope_intake_contract.get("explicit_search_action_required") is True
            and scope_intake_contract.get("full_pool_scope_allowed") is False
            and scope_intake_contract.get("deep_scan_scope_allowed") is False
            and scope_intake_contract.get("watchlist_scope_bounded") is True
            and scope_intake_contract.get("holdings_scope_bounded") is True
            and scope_intake_contract.get("provider_model_execution_from_scope_intake_allowed") is False
            and scope_intake_contract.get("scope_intake_is_provider_execution_evidence") is False
            and scope_intake_contract.get("scope_intake_is_production_evidence") is False
            and _dict(status.get("live_light")).get("scope_intake_contract_visible") is True
            and _dict(status.get("live_light")).get("scope_intake_symbol_limit") == 2
            and _dict(status.get("live_light")).get("scope_intake_symbol_dedupe_required") is True
            and _dict(status.get("live_light")).get("scope_intake_scope_hash_required") is True
            and _dict(status.get("live_light")).get("scope_intake_secret_like_payload_fields_dropped") is True
            and _dict(status.get("live_light")).get("scope_intake_is_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_scope_intake_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_scope_intake_symbol_dedupe_required") is True
            and _dict(status.get("policy")).get("live_light_scope_intake_scope_hash_required") is True
            and _dict(status.get("policy")).get("live_light_scope_intake_search_typing_creates_task") is False
            and _dict(status.get("policy")).get("live_light_scope_intake_secret_like_payload_fields_dropped")
            is True
            and _dict(status.get("policy")).get("live_light_scope_intake_is_production_evidence") is False
            and scope_intake_contract.get("external_calls_triggered") is False
            and scope_intake_contract.get("tushare_called") is False
            and scope_intake_contract.get("deepseek_called") is False
            and scope_intake_contract.get("github_called") is False
            and scope_intake_contract.get("contains_secret") is False
            and scope_intake_contract.get("does_not_execute_trades") is True
            and scope_intake_contract.get("does_not_modify_strategy_action") is True,
            f"scope_intake_contract={scope_intake_contract}",
        ),
        _row(
            "live_light_stage_dependency_contract_orders_tushare_factor_next_deepseek_without_execution",
            stage_dependency_contract.get("schema_version")
            == "command_center_live_light_stage_dependency_contract.v1"
            and stage_dependency_contract.get("status") == "stage_dependency_contract_visible_executor_pending"
            and stage_dependency_contract.get("mode") == "live_light"
            and stage_dependency_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and stage_dependency_contract.get("task_type") == "command_center_live_bootstrap"
            and stage_dependency_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and stage_dependency_contract.get("stage_sequence")
            == [
                "initial_cache_render",
                "scope_resolution",
                "trade_cal_if_needed",
                "tushare_light_refresh",
                "factor_light_runtime",
                "factor_quant_hub_cache_refresh",
                "next_session_cache_refresh",
                "deepseek_pro_explanation",
                "ui_task_polling",
            ]
            and stage_dependency_contract.get("stage_count") == 9
            and stage_dependency_contract.get("dependency_edge_count") == 9
            and {
                ("initial_cache_render", "scope_resolution", "cache_first_render_complete"),
                ("scope_resolution", "trade_cal_if_needed", "safe_scope_hash_ready"),
                (
                    "trade_cal_if_needed",
                    "tushare_light_refresh",
                    "trade_calendar_ready_or_safe_skip",
                ),
                (
                    "tushare_light_refresh",
                    "factor_light_runtime",
                    "tushare_light_facts_ready_or_provider_gap_visible",
                ),
                (
                    "factor_light_runtime",
                    "factor_quant_hub_cache_refresh",
                    "factor_light_runtime_ready_or_safe_skip",
                ),
                (
                    "factor_light_runtime",
                    "next_session_cache_refresh",
                    "factor_light_runtime_ready_or_safe_skip",
                ),
                (
                    "factor_quant_hub_cache_refresh",
                    "deepseek_pro_explanation",
                    "factor_quant_hub_cache_ready",
                ),
                (
                    "next_session_cache_refresh",
                    "deepseek_pro_explanation",
                    "next_session_cache_ready",
                ),
                (
                    "deepseek_pro_explanation",
                    "ui_task_polling",
                    "terminal_or_safe_skip_status_visible",
                ),
            }
            == {
                (
                    str(_dict(row).get("from_stage") or ""),
                    str(_dict(row).get("to_stage") or ""),
                    str(_dict(row).get("gate") or ""),
                )
                for row in _list(stage_dependency_contract.get("dependency_edges"))
            }
            and {
                "factor_quant_hub_cache_refresh",
                "next_session_cache_refresh",
            }
            == set(
                _list(
                    {
                        str(_dict(row).get("stage_key") or ""): _dict(row)
                        for row in _list(stage_dependency_contract.get("dependency_rows"))
                    }
                    .get("deepseek_pro_explanation", {})
                    .get("depends_on")
                )
            )
            and all(
                _dict(row).get("stage_status_must_be_pollable") is True
                and _dict(row).get("cache_get_may_execute_stage") is False
                and _dict(row).get("react_render_may_execute_stage") is False
                and _dict(row).get("fastapi_startup_may_execute_stage") is False
                for row in _list(stage_dependency_contract.get("dependency_rows"))
            )
            and stage_dependency_contract.get("initial_cache_render_first") is True
            and stage_dependency_contract.get("scope_intake_before_provider") is True
            and stage_dependency_contract.get("tushare_before_factor_light") is True
            and stage_dependency_contract.get("factor_light_before_factor_quant_hub") is True
            and stage_dependency_contract.get("factor_light_before_next_session") is True
            and stage_dependency_contract.get("deepseek_after_factor_and_next_ready") is True
            and stage_dependency_contract.get("deepseek_may_run_without_data_ready") is False
            and stage_dependency_contract.get("provider_gap_blocks_deepseek_or_requires_safe_skip") is True
            and stage_dependency_contract.get("safe_skip_propagates_to_dependents") is True
            and stage_dependency_contract.get("ui_polling_after_terminal_or_safe_skip") is True
            and stage_dependency_contract.get("stage_status_history_required") is True
            and stage_dependency_contract.get("stage_safe_error_required") is True
            and stage_dependency_contract.get("stage_provider_gap_visible_required") is True
            and stage_dependency_contract.get("cache_get_may_execute_stage") is False
            and stage_dependency_contract.get("react_render_may_execute_stage") is False
            and stage_dependency_contract.get("fastapi_startup_may_execute_stage") is False
            and stage_dependency_contract.get("tushare_source_switch_enabled") is True
            and stage_dependency_contract.get("deepseek_source_switch_enabled") is True
            and stage_dependency_contract.get("provider_model_acceptance_requires_execution_request") is True
            and _dict(status.get("live_light")).get("stage_dependency_contract_visible") is True
            and _dict(status.get("live_light")).get("stage_dependency_stage_count") == 9
            and _dict(status.get("live_light")).get("stage_dependency_deepseek_requires_data_ready") is True
            and _dict(status.get("live_light")).get("stage_dependency_safe_skip_required") is True
            and _dict(status.get("live_light")).get("stage_dependency_executor_implemented") is False
            and _dict(status.get("live_light")).get("stage_dependency_contract_is_production_evidence")
            is False
            and _dict(status.get("policy")).get("live_light_stage_dependency_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_stage_dependency_deepseek_requires_data_ready")
            is True
            and _dict(status.get("policy")).get("live_light_stage_dependency_safe_skip_required") is True
            and _dict(status.get("policy")).get("live_light_stage_dependency_executor_implemented") is False
            and _dict(status.get("policy")).get("live_light_stage_dependency_contract_is_production_evidence")
            is False
            and stage_dependency_contract.get("live_light_executor_implemented") is False
            and stage_dependency_contract.get("provider_execution_implemented") is False
            and stage_dependency_contract.get("model_execution_implemented") is False
            and stage_dependency_contract.get("stage_dependency_contract_is_execution_evidence") is False
            and stage_dependency_contract.get("stage_dependency_contract_is_production_evidence") is False
            and stage_dependency_contract.get("external_calls_triggered") is False
            and stage_dependency_contract.get("tushare_called") is False
            and stage_dependency_contract.get("deepseek_called") is False
            and stage_dependency_contract.get("github_called") is False
            and stage_dependency_contract.get("contains_secret") is False
            and stage_dependency_contract.get("does_not_execute_trades") is True
            and stage_dependency_contract.get("does_not_modify_strategy_action") is True,
            f"stage_dependency_contract={stage_dependency_contract}",
        ),
        _row(
            "live_light_freshness_provider_gap_contract_keeps_empty_permission_cache_states_unverified",
            freshness_contract.get("schema_version")
            == "command_center_live_light_freshness_provider_gap_contract.v1"
            and freshness_contract.get("status")
            == "freshness_provider_gap_contract_visible_runtime_evidence_pending"
            and freshness_contract.get("mode") == "live_light"
            and freshness_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and freshness_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and freshness_contract.get("required_surfaces")
            == ["factor_quant_hub_cache", "next_session_cache", "deepseek_explanation_cache"]
            and freshness_contract.get("freshness_row_count") == 3
            and {
                "fresh_provider",
                "cache_hit_fresh",
                "cache_hit_stale",
                "provider_gap",
                "safe_error",
                "credential_missing",
                "permission_denied",
                "empty_result",
                "no_record",
                "skipped_by_mode",
                "skipped_by_source_switch",
                "skipped_by_rate_limit",
                "skipped_budget_exceeded",
            }.issubset(set(_list(freshness_contract.get("freshness_state_values"))))
            and {
                "credential_missing",
                "permission_denied",
                "empty_result",
                "no_record",
                "safe_error",
                "provider_unavailable",
            }.issubset(set(_list(freshness_contract.get("provider_gap_state_values"))))
            and {
                "factor_quant_hub_cache",
                "next_session_cache",
                "deepseek_explanation_cache",
            }
            == {
                str(_dict(row).get("surface_key") or "")
                for row in _list(freshness_contract.get("freshness_rows"))
            }
            and all(
                _dict(row).get("freshness_state_required") is True
                and _dict(row).get("provider_gap_visible_required") is True
                and _dict(row).get("safe_error_visible_required") is True
                and _dict(row).get("empty_result_may_be_verified") is False
                and _dict(row).get("no_record_may_be_negative_evidence") is False
                and _dict(row).get("permission_denied_may_be_verified") is False
                and _dict(row).get("cache_hit_is_provider_execution_evidence") is False
                for row in _list(freshness_contract.get("freshness_rows"))
            )
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(freshness_contract.get("freshness_rows"))
                }.get("deepseek_explanation_cache", {})
            ).get("deepseek_skipped_when_data_not_ready")
            is True
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(freshness_contract.get("freshness_rows"))
                }.get("deepseek_explanation_cache", {})
            ).get("deepseek_skip_is_model_correctness_evidence")
            is False
            and freshness_contract.get("freshness_state_visible_required") is True
            and freshness_contract.get("data_date_visible_required") is True
            and freshness_contract.get("local_fetched_at_visible_required") is True
            and freshness_contract.get("cache_source_visible_required") is True
            and freshness_contract.get("provider_gap_visible_required") is True
            and freshness_contract.get("safe_error_visible_required") is True
            and freshness_contract.get("stale_cache_label_required") is True
            and freshness_contract.get("last_good_cache_lineage_required") is True
            and freshness_contract.get("cache_hit_is_provider_execution_evidence") is False
            and freshness_contract.get("cache_hit_is_model_execution_evidence") is False
            and freshness_contract.get("stale_cache_is_freshness_evidence") is False
            and freshness_contract.get("empty_result_may_be_verified") is False
            and freshness_contract.get("empty_result_may_close_provider_gap") is False
            and freshness_contract.get("no_record_may_be_negative_evidence") is False
            and freshness_contract.get("permission_denied_may_be_verified") is False
            and freshness_contract.get("credential_missing_may_be_verified") is False
            and freshness_contract.get("safe_error_may_be_verified") is False
            and freshness_contract.get("provider_gap_may_be_synthesized") is False
            and freshness_contract.get("fallback_may_synthesize_provider_rows") is False
            and freshness_contract.get("fallback_may_synthesize_model_output") is False
            and freshness_contract.get("deepseek_skipped_when_data_not_ready") is True
            and freshness_contract.get("deepseek_skip_is_model_correctness_evidence") is False
            and _dict(status.get("live_light")).get("freshness_provider_gap_contract_visible") is True
            and _dict(status.get("live_light")).get("freshness_state_visible_required") is True
            and _dict(status.get("live_light")).get("provider_gap_visible_required") is True
            and _dict(status.get("live_light")).get("stale_cache_label_required") is True
            and _dict(status.get("live_light")).get("empty_or_no_record_is_verified") is False
            and _dict(status.get("live_light")).get(
                "freshness_provider_gap_contract_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("live_light_freshness_provider_gap_contract_visible")
            is True
            and _dict(status.get("policy")).get("live_light_freshness_state_visible_required") is True
            and _dict(status.get("policy")).get("live_light_provider_gap_visible_required") is True
            and _dict(status.get("policy")).get("live_light_stale_cache_label_required") is True
            and _dict(status.get("policy")).get("live_light_empty_or_no_record_is_verified") is False
            and _dict(status.get("policy")).get(
                "live_light_freshness_provider_gap_contract_is_production_evidence"
            )
            is False
            and freshness_contract.get("freshness_contract_is_provider_execution_evidence") is False
            and freshness_contract.get("freshness_contract_is_model_execution_evidence") is False
            and freshness_contract.get("freshness_contract_is_production_evidence") is False
            and freshness_contract.get("external_calls_triggered") is False
            and freshness_contract.get("tushare_called") is False
            and freshness_contract.get("deepseek_called") is False
            and freshness_contract.get("github_called") is False
            and freshness_contract.get("contains_secret") is False
            and freshness_contract.get("does_not_execute_trades") is True
            and freshness_contract.get("does_not_modify_strategy_action") is True,
            f"freshness_contract={freshness_contract}",
        ),
        _row(
            "live_light_task_lifecycle_contract_exposes_pollable_safe_status_without_execution_claims",
            lifecycle_contract.get("schema_version") == "command_center_live_light_task_lifecycle_contract.v1"
            and lifecycle_contract.get("status") == "task_lifecycle_contract_visible_status_polling_pending"
            and lifecycle_contract.get("mode") == "live_light"
            and lifecycle_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and lifecycle_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and lifecycle_contract.get("task_index_route") == "GET /api/tasks"
            and lifecycle_contract.get("task_type") == "command_center_live_bootstrap"
            and lifecycle_contract.get("output_packet_key") == "command_center_live_bootstrap_packet"
            and lifecycle_contract.get("lifecycle_surface") == "task_service_status_only"
            and lifecycle_contract.get("allowed_task_statuses") == ["pending", "running", "success", "failed", "cancelled"]
            and lifecycle_contract.get("terminal_task_statuses") == ["success", "failed", "cancelled"]
            and lifecycle_contract.get("success_status_may_still_mean_safe_skip") is True
            and lifecycle_contract.get("expected_live_light_success_current_step")
            == "live_bootstrap_plan_recorded_no_provider_execution"
            and {
                "live_bootstrap_skipped_mode_not_live_light",
                "live_bootstrap_skipped_sources_disabled_no_external_call",
                "live_bootstrap_skipped_due_to_rate_limit",
            }.issubset(set(_list(lifecycle_contract.get("safe_skip_current_steps"))))
            and {
                "task_id",
                "task_type",
                "status",
                "progress",
                "current_step",
                "error_message_safe",
                "status_history",
                "call_ledger",
                "output_packet_key",
            }.issubset(set(_list(lifecycle_contract.get("required_visible_task_fields"))))
            and lifecycle_contract.get("required_status_history_fields") == ["status", "progress", "current_step", "at"]
            and lifecycle_contract.get("progress_min") == 0.0
            and lifecycle_contract.get("progress_max") == 1.0
            and lifecycle_contract.get("progress_visible_required") is True
            and lifecycle_contract.get("current_step_visible_required") is True
            and lifecycle_contract.get("task_id_visible_required") is True
            and lifecycle_contract.get("task_status_visible_required") is True
            and lifecycle_contract.get("status_history_visible_required") is True
            and lifecycle_contract.get("safe_error_visible_required") is True
            and lifecycle_contract.get("rate_limit_skipped_state_visible_required") is True
            and lifecycle_contract.get("rate_limit_reuses_existing_task") is True
            and lifecycle_contract.get("rate_limit_seconds") == 600
            and lifecycle_contract.get("status_get_creates_task") is False
            and lifecycle_contract.get("status_index_creates_task") is False
            and lifecycle_contract.get("status_get_calls_provider") is False
            and lifecycle_contract.get("status_index_calls_provider") is False
            and lifecycle_contract.get("react_initial_render_creates_task") is False
            and lifecycle_contract.get("react_render_calls_provider") is False
            and lifecycle_contract.get("polling_ui_thread_blocking_allowed") is False
            and lifecycle_contract.get("raw_exception_exposed") is False
            and lifecycle_contract.get("call_ledger_required") is True
            and lifecycle_contract.get("call_ledger_visible_safe_summary_only") is True
            and lifecycle_contract.get("task_success_is_provider_execution_evidence") is False
            and lifecycle_contract.get("task_success_is_model_execution_evidence") is False
            and lifecycle_contract.get("task_success_is_production_evidence") is False
            and lifecycle_contract.get("safe_skip_is_provider_execution_evidence") is False
            and lifecycle_contract.get("safe_skip_is_production_evidence") is False
            and _dict(status.get("live_light")).get("task_lifecycle_contract_visible") is True
            and _dict(status.get("live_light")).get("task_status_polling_required") is True
            and _dict(status.get("live_light")).get("task_success_is_provider_model_evidence") is False
            and _dict(status.get("live_light")).get("task_success_is_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_task_lifecycle_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_task_status_polling_required") is True
            and _dict(status.get("policy")).get("live_light_task_status_route_read_only") is True
            and _dict(status.get("policy")).get("live_light_task_status_get_creates_task") is False
            and _dict(status.get("policy")).get("live_light_task_success_is_provider_model_evidence") is False
            and _dict(status.get("policy")).get("live_light_task_success_is_production_evidence") is False
            and lifecycle_contract.get("provider_execution_implemented") is False
            and lifecycle_contract.get("model_execution_implemented") is False
            and lifecycle_contract.get("external_calls_triggered") is False
            and lifecycle_contract.get("tushare_called") is False
            and lifecycle_contract.get("deepseek_called") is False
            and lifecycle_contract.get("github_called") is False
            and lifecycle_contract.get("contains_secret") is False
            and lifecycle_contract.get("does_not_execute_trades") is True
            and lifecycle_contract.get("does_not_modify_strategy_action") is True,
            f"lifecycle_contract={lifecycle_contract}",
        ),
        _row(
            "live_light_task_queue_budget_contract_bounds_startup_tasks_without_execution",
            queue_budget_contract.get("schema_version") == "command_center_live_light_task_queue_budget_contract.v1"
            and queue_budget_contract.get("status") == "task_queue_budget_visible_frontend_wiring_pending"
            and queue_budget_contract.get("mode") == "live_light"
            and queue_budget_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and queue_budget_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and queue_budget_contract.get("task_index_route") == "GET /api/tasks"
            and queue_budget_contract.get("task_type") == "command_center_live_bootstrap"
            and queue_budget_contract.get("queue_row_count") == 5
            and queue_budget_contract.get("condition_satisfied_row_count") == 5
            and set(queue_budget_rows) == {
                "startup_autostart_gate",
                "single_active_local_startup_task",
                "rate_limit_reuse_or_skip",
                "status_reads_never_enqueue",
                "provider_model_queue_blocked",
            }
            and queue_budget_contract.get("max_active_local_startup_tasks_per_session") == 1
            and queue_budget_contract.get("max_new_tasks_per_rate_limit_window") == 1
            and queue_budget_contract.get("rate_limit_seconds") == 600
            and queue_budget_contract.get("symbol_limit") == 2
            and queue_budget_contract.get("startup_autostart_effective") is True
            and queue_budget_contract.get("bounded_queue_required") is True
            and queue_budget_contract.get("unbounded_queue_allowed") is False
            and queue_budget_contract.get("queue_overflow_policy") == "reuse_or_skip_existing_local_task"
            and queue_budget_contract.get("rate_limit_reuses_existing_task") is True
            and queue_budget_contract.get("rate_limit_skip_creates_new_task") is False
            and queue_budget_contract.get("session_dedupe_required") is True
            and queue_budget_contract.get("task_polling_required") is True
            and queue_budget_contract.get("status_get_creates_task") is False
            and queue_budget_contract.get("task_polling_creates_task") is False
            and queue_budget_contract.get("search_typing_creates_task") is False
            and queue_budget_contract.get("cache_get_creates_task") is False
            and queue_budget_contract.get("fastapi_startup_creates_task") is False
            and queue_budget_contract.get("react_initial_render_creates_task") is False
            and queue_budget_contract.get("react_mounted_may_post_after_cache_render_only") is True
            and queue_budget_contract.get("creates_provider_model_task") is False
            and queue_budget_contract.get("provider_model_execution_requires_execution_request") is True
            and queue_budget_contract.get("provider_execution_implemented") is False
            and queue_budget_contract.get("model_execution_implemented") is False
            and queue_budget_contract.get("queue_contract_is_execution_evidence") is False
            and queue_budget_contract.get("queue_contract_is_production_evidence") is False
            and queue_budget_rows.get("single_active_local_startup_task", {}).get("current_policy")
            == "max_one_active_local_startup_task_per_session"
            and queue_budget_rows.get("rate_limit_reuse_or_skip", {}).get("current_policy")
            == "rate_limit_reuses_existing_task_no_new_queue_item"
            and queue_budget_rows.get("status_reads_never_enqueue", {}).get("current_policy")
            == "status_surfaces_are_read_only"
            and all(
                _dict(row).get("condition_currently_satisfied") is True
                and _dict(row).get("max_active_local_startup_tasks_per_session") == 1
                and _dict(row).get("unbounded_queue_allowed") is False
                and _dict(row).get("queue_overflow_policy") == "reuse_or_skip_existing_local_task"
                and _dict(row).get("status_get_creates_task") is False
                and _dict(row).get("task_polling_creates_task") is False
                and _dict(row).get("search_typing_creates_task") is False
                and _dict(row).get("react_initial_render_creates_task") is False
                and _dict(row).get("creates_provider_model_task") is False
                and _dict(row).get("provider_model_execution_requires_execution_request") is True
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("tushare_called") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("github_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("row_is_production_evidence") is False
                for row in queue_budget_rows.values()
            )
            and _dict(status.get("live_light")).get("task_queue_budget_contract_visible") is True
            and _dict(status.get("live_light")).get("task_queue_budget_row_count") == 5
            and _dict(status.get("live_light")).get("task_queue_budget_condition_satisfied_row_count") == 5
            and _dict(status.get("live_light")).get(
                "task_queue_budget_max_active_local_startup_tasks_per_session"
            )
            == 1
            and _dict(status.get("live_light")).get("task_queue_budget_unbounded_queue_allowed") is False
            and _dict(status.get("live_light")).get("task_queue_budget_status_get_creates_task") is False
            and _dict(status.get("live_light")).get("task_queue_budget_task_polling_creates_task") is False
            and _dict(status.get("live_light")).get("task_queue_budget_creates_provider_model_task") is False
            and _dict(status.get("live_light")).get("task_queue_budget_is_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_task_queue_budget_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_task_queue_budget_row_count") == 5
            and _dict(status.get("policy")).get(
                "live_light_task_queue_budget_condition_satisfied_row_count"
            )
            == 5
            and _dict(status.get("policy")).get(
                "live_light_task_queue_budget_max_active_local_startup_tasks_per_session"
            )
            == 1
            and _dict(status.get("policy")).get("live_light_task_queue_budget_unbounded_queue_allowed") is False
            and _dict(status.get("policy")).get("live_light_task_queue_budget_status_get_creates_task") is False
            and _dict(status.get("policy")).get("live_light_task_queue_budget_task_polling_creates_task")
            is False
            and _dict(status.get("policy")).get("live_light_task_queue_budget_creates_provider_model_task")
            is False
            and _dict(status.get("policy")).get("live_light_task_queue_budget_is_production_evidence")
            is False
            and queue_budget_contract.get("external_calls_triggered") is False
            and queue_budget_contract.get("tushare_called") is False
            and queue_budget_contract.get("deepseek_called") is False
            and queue_budget_contract.get("github_called") is False
            and queue_budget_contract.get("contains_secret") is False
            and queue_budget_contract.get("does_not_execute_trades") is True
            and queue_budget_contract.get("does_not_modify_strategy_action") is True,
            f"queue_budget_contract={queue_budget_contract}",
        ),
        _row(
            "live_light_task_control_contract_allows_manual_cancel_retry_without_external_work",
            task_control_contract.get("schema_version") == "command_center_live_light_task_control_contract.v1"
            and task_control_contract.get("status") == "task_control_contract_visible_manual_cancel_retry_only"
            and task_control_contract.get("mode") == "live_light"
            and task_control_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and task_control_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and task_control_contract.get("task_index_route") == "GET /api/tasks"
            and task_control_contract.get("cancel_route") == "POST /api/tasks/{task_id}/cancel"
            and task_control_contract.get("retry_route") == "POST /api/tasks/{task_id}/retry"
            and task_control_contract.get("control_row_count") == 2
            and {
                "cancel",
                "retry",
            }
            == {
                str(_dict(row).get("control_key") or "")
                for row in _list(task_control_contract.get("control_rows"))
            }
            and _dict(
                {
                    str(_dict(row).get("control_key") or ""): _dict(row)
                    for row in _list(task_control_contract.get("control_rows"))
                }.get("cancel", {})
            ).get("allowed_task_statuses")
            == ["pending", "running"]
            and _dict(
                {
                    str(_dict(row).get("control_key") or ""): _dict(row)
                    for row in _list(task_control_contract.get("control_rows"))
                }.get("cancel", {})
            ).get("creates_new_task")
            is False
            and _dict(
                {
                    str(_dict(row).get("control_key") or ""): _dict(row)
                    for row in _list(task_control_contract.get("control_rows"))
                }.get("retry", {})
            ).get("allowed_task_statuses")
            == ["failed"]
            and _dict(
                {
                    str(_dict(row).get("control_key") or ""): _dict(row)
                    for row in _list(task_control_contract.get("control_rows"))
                }.get("retry", {})
            ).get("creates_new_task")
            is True
            and all(
                _dict(row).get("manual_operator_action_required") is True
                and _dict(row).get("safe_reason_required") is True
                and _dict(row).get("provider_or_model_execution_allowed") is False
                for row in _list(task_control_contract.get("control_rows"))
            )
            and task_control_contract.get("cancel_route_available") is True
            and task_control_contract.get("retry_route_available") is True
            and task_control_contract.get("manual_operator_action_required") is True
            and task_control_contract.get("auto_cancel_enabled") is False
            and task_control_contract.get("auto_retry_enabled") is False
            and task_control_contract.get("retry_requires_failed_task") is True
            and task_control_contract.get("retry_creates_new_local_task_only") is True
            and task_control_contract.get("cancel_may_stop_provider_call_in_flight") is False
            and task_control_contract.get("control_reason_sanitized") is True
            and task_control_contract.get("raw_control_reason_logged") is False
            and task_control_contract.get("raw_control_reason_cached") is False
            and task_control_contract.get("credential_values_exposed") is False
            and task_control_contract.get("task_id_sanitized_when_missing") is True
            and task_control_contract.get("control_call_ledger_required") is True
            and task_control_contract.get("control_call_ledger_safe_summary_only") is True
            and task_control_contract.get("status_history_append_required") is True
            and task_control_contract.get("task_log_append_required") is True
            and task_control_contract.get("cache_get_may_cancel_or_retry") is False
            and task_control_contract.get("react_render_may_cancel_or_retry") is False
            and task_control_contract.get("fastapi_startup_may_cancel_or_retry") is False
            and _dict(status.get("live_light")).get("task_control_contract_visible") is True
            and _dict(status.get("live_light")).get("task_control_manual_only") is True
            and _dict(status.get("live_light")).get("task_control_auto_retry_enabled") is False
            and _dict(status.get("live_light")).get("task_control_is_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_task_control_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_task_control_manual_only") is True
            and _dict(status.get("policy")).get("live_light_task_control_auto_retry_enabled") is False
            and _dict(status.get("policy")).get("live_light_task_control_is_production_evidence") is False
            and task_control_contract.get("provider_execution_implemented") is False
            and task_control_contract.get("model_execution_implemented") is False
            and task_control_contract.get("control_contract_is_provider_execution_evidence") is False
            and task_control_contract.get("control_contract_is_model_execution_evidence") is False
            and task_control_contract.get("control_contract_is_production_evidence") is False
            and task_control_contract.get("external_calls_triggered") is False
            and task_control_contract.get("tushare_called") is False
            and task_control_contract.get("deepseek_called") is False
            and task_control_contract.get("github_called") is False
            and task_control_contract.get("contains_secret") is False
            and task_control_contract.get("does_not_execute_trades") is True
            and task_control_contract.get("does_not_modify_strategy_action") is True,
            f"task_control_contract={task_control_contract}",
        ),
        _row(
            "live_light_operator_status_contract_exposes_read_only_safe_task_status_without_execution_claims",
            operator_status_contract.get("schema_version")
            == "command_center_live_light_operator_status_contract.v1"
            and operator_status_contract.get("status")
            == "operator_status_contract_visible_read_only_task_status_pending"
            and operator_status_contract.get("mode") == "live_light"
            and operator_status_contract.get("status_route") == "GET /api/bootstrap/status"
            and operator_status_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and operator_status_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and operator_status_contract.get("task_index_route") == "GET /api/tasks"
            and operator_status_contract.get("task_type") == "command_center_live_bootstrap"
            and operator_status_contract.get("status_surface_count") == 7
            and operator_status_contract.get("required_operator_surfaces")
            == [
                "runtime_mode",
                "source_switches",
                "external_execution_profile",
                "latest_bootstrap_task",
                "rate_limit_state",
                "safe_error_state",
                "evidence_boundary_state",
            ]
            and {
                "runtime_mode",
                "source_switches",
                "external_execution_profile",
                "latest_bootstrap_task",
                "rate_limit_state",
                "safe_error_state",
                "evidence_boundary_state",
            }
            == {
                str(_dict(row).get("surface_key") or "")
                for row in _list(operator_status_contract.get("status_rows"))
            }
            and all(
                _dict(row).get("frontend_visible") is True
                and _dict(row).get("frontend_editable") is False
                and _dict(row).get("provider_or_model_execution_evidence") is False
                for row in _list(operator_status_contract.get("status_rows"))
            )
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("source_switches", {})
            ).get("effective_tushare_on_open")
            is True
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("source_switches", {})
            ).get("effective_deepseek_on_open")
            is True
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("external_execution_profile", {})
            ).get("current_value_safe")
            == "light_provider_model"
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("external_execution_profile", {})
            ).get("provider_stage_allowed_by_profile")
            is True
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("external_execution_profile", {})
            ).get("model_stage_allowed_by_profile")
            is True
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("external_execution_profile", {})
            ).get("calls_provider_model_now")
            is False
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("external_execution_profile", {})
            ).get("linked_rate_limit_seconds_visible_safe")
            == 600
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("latest_bootstrap_task", {})
            ).get("latest_task_status_may_be_skeleton_or_safe_skip")
            is True
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("rate_limit_state", {})
            ).get("rate_limit_skip_creates_new_task")
            is False
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(operator_status_contract.get("status_rows"))
                }.get("safe_error_state", {})
            ).get("raw_exception_visible_allowed")
            is False
            and operator_status_contract.get("current_mode_visible_required") is True
            and operator_status_contract.get("configured_source_switches_visible_required") is True
            and operator_status_contract.get("effective_source_switches_visible_required") is True
            and operator_status_contract.get("external_execution_profile_visible_required") is True
            and operator_status_contract.get("latest_bootstrap_task_status_visible_required") is True
            and operator_status_contract.get("latest_bootstrap_safe_error_visible_required") is True
            and operator_status_contract.get("rate_limit_skipped_state_visible_required") is True
            and operator_status_contract.get("source_switches_effective") is True
            and operator_status_contract.get("external_execution_profile") == "light_provider_model"
            and operator_status_contract.get("external_execution_profile_provider_stage_allowed") is True
            and operator_status_contract.get("external_execution_profile_model_stage_allowed") is True
            and operator_status_contract.get("external_execution_profile_executor_implemented") is False
            and operator_status_contract.get("external_execution_profile_calls_provider_model_now") is False
            and operator_status_contract.get("profile_source_rate_summary_visible_required") is True
            and operator_status_contract.get("symbol_limit_visible_safe") == 2
            and operator_status_contract.get("rate_limit_seconds_visible_safe") == 600
            and operator_status_contract.get("operator_status_read_only") is True
            and operator_status_contract.get("operator_status_frontend_editable") is False
            and operator_status_contract.get("frontend_writeback_allowed") is False
            and operator_status_contract.get("status_get_creates_task") is False
            and operator_status_contract.get("status_get_calls_provider") is False
            and operator_status_contract.get("status_get_calls_model") is False
            and operator_status_contract.get("task_index_creates_task") is False
            and operator_status_contract.get("task_status_get_creates_task") is False
            and operator_status_contract.get("safe_summary_only") is True
            and operator_status_contract.get("raw_config_values_exposed") is False
            and operator_status_contract.get("raw_task_payload_visible_allowed") is False
            and operator_status_contract.get("raw_exception_visible_allowed") is False
            and operator_status_contract.get("raw_prompt_or_raw_model_output_visible_allowed") is False
            and operator_status_contract.get("credential_values_exposed") is False
            and operator_status_contract.get("credential_env_key_names_exposed") is False
            and operator_status_contract.get("latest_task_success_is_provider_model_evidence") is False
            and operator_status_contract.get("operator_status_contract_is_production_evidence") is False
            and _dict(status.get("live_light")).get("operator_status_contract_visible") is True
            and _dict(status.get("live_light")).get("operator_status_external_execution_profile")
            == "light_provider_model"
            and _dict(status.get("live_light")).get("operator_status_profile_provider_stage_allowed") is True
            and _dict(status.get("live_light")).get("operator_status_profile_model_stage_allowed") is True
            and _dict(status.get("live_light")).get("operator_status_profile_calls_provider_model_now") is False
            and _dict(status.get("live_light")).get("operator_status_read_only") is True
            and _dict(status.get("live_light")).get("operator_status_is_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_operator_status_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_operator_status_external_execution_profile")
            == "light_provider_model"
            and _dict(status.get("policy")).get("live_light_operator_status_profile_provider_stage_allowed")
            is True
            and _dict(status.get("policy")).get("live_light_operator_status_profile_model_stage_allowed")
            is True
            and _dict(status.get("policy")).get("live_light_operator_status_profile_calls_provider_model_now")
            is False
            and _dict(status.get("policy")).get("live_light_operator_status_read_only") is True
            and _dict(status.get("policy")).get("live_light_operator_status_is_production_evidence") is False
            and operator_status_contract.get("provider_execution_implemented") is False
            and operator_status_contract.get("model_execution_implemented") is False
            and operator_status_contract.get("external_calls_triggered") is False
            and operator_status_contract.get("tushare_called") is False
            and operator_status_contract.get("deepseek_called") is False
            and operator_status_contract.get("github_called") is False
            and operator_status_contract.get("contains_secret") is False
            and operator_status_contract.get("does_not_execute_trades") is True
            and operator_status_contract.get("does_not_modify_strategy_action") is True,
            f"operator_status_contract={operator_status_contract}",
        ),
        _row(
            "live_light_promotion_gate_contract_keeps_l3_l4_release_blocked_until_real_evidence_and_ci",
            promotion_gate_contract.get("schema_version")
            == "command_center_live_light_promotion_gate_contract.v1"
            and promotion_gate_contract.get("status") == "promotion_gate_visible_release_blockers_pending"
            and promotion_gate_contract.get("mode") == "live_light"
            and promotion_gate_contract.get("status_route") == "GET /api/bootstrap/status"
            and promotion_gate_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and promotion_gate_contract.get("acceptance_dry_run_route")
            == "POST /api/bootstrap/provider-model-acceptance-dry-run"
            and promotion_gate_contract.get("execution_request_route")
            == "POST /api/bootstrap/provider-model-execution-request"
            and promotion_gate_contract.get("provider_model_acceptance_route")
            == "future POST /api/bootstrap/provider-model-acceptance"
            and promotion_gate_contract.get("promotion_layer_count") == 4
            and promotion_gate_contract.get("required_layer_order")
            == [
                "l1_mode_contract",
                "l2_local_bootstrap_readiness",
                "l3_real_provider_model_evidence",
                "l4_release_promotion",
            ]
            and {
                "l1_mode_contract",
                "l2_local_bootstrap_readiness",
                "l3_real_provider_model_evidence",
                "l4_release_promotion",
            }
            == {
                str(_dict(row).get("layer_key") or "")
                for row in _list(promotion_gate_contract.get("layer_rows"))
            }
            and _dict(
                {
                    str(_dict(row).get("layer_key") or ""): _dict(row)
                    for row in _list(promotion_gate_contract.get("layer_rows"))
                }.get("l1_mode_contract", {})
            ).get("status")
            == "passed_local_mode_contract_visible"
            and _dict(
                {
                    str(_dict(row).get("layer_key") or ""): _dict(row)
                    for row in _list(promotion_gate_contract.get("layer_rows"))
                }.get("l2_local_bootstrap_readiness", {})
            ).get("status")
            == "passed_local_bootstrap_scaffold_visible_provider_model_pending"
            and _dict(
                {
                    str(_dict(row).get("layer_key") or ""): _dict(row)
                    for row in _list(promotion_gate_contract.get("layer_rows"))
                }.get("l3_real_provider_model_evidence", {})
            ).get("status")
            == "blocked_real_provider_model_evidence_pending"
            and _dict(
                {
                    str(_dict(row).get("layer_key") or ""): _dict(row)
                    for row in _list(promotion_gate_contract.get("layer_rows"))
                }.get("l4_release_promotion", {})
            ).get("status")
            == "blocked_remote_ci_and_promotion_review_pending"
            and _dict(
                {
                    str(_dict(row).get("layer_key") or ""): _dict(row)
                    for row in _list(promotion_gate_contract.get("layer_rows"))
                }.get("l3_real_provider_model_evidence", {})
            ).get("production_blocker")
            is True
            and _dict(
                {
                    str(_dict(row).get("layer_key") or ""): _dict(row)
                    for row in _list(promotion_gate_contract.get("layer_rows"))
                }.get("l4_release_promotion", {})
            ).get("remote_ci_required")
            is True
            and promotion_gate_contract.get("local_mode_contract_visible") is True
            and promotion_gate_contract.get("local_bootstrap_readiness_visible") is True
            and promotion_gate_contract.get("real_provider_model_evidence_complete") is False
            and promotion_gate_contract.get("production_promotion_review_complete") is False
            and promotion_gate_contract.get("remote_ci_status_known") is False
            and promotion_gate_contract.get("remote_ci_green") is False
            and promotion_gate_contract.get("github_api_called") is False
            and promotion_gate_contract.get("fresh_local_gate_run_required") is True
            and promotion_gate_contract.get("remote_ci_green_required") is True
            and promotion_gate_contract.get("production_promotion_review_required") is True
            and promotion_gate_contract.get("local_contracts_may_pass") is True
            and promotion_gate_contract.get("local_contracts_are_production_evidence") is False
            and promotion_gate_contract.get("provider_model_execution_required_before_promotion") is True
            and promotion_gate_contract.get("browser_nonblocking_runtime_evidence_required") is True
            and promotion_gate_contract.get("ledger_redaction_review_required") is True
            and promotion_gate_contract.get("secret_artifact_scan_required") is True
            and promotion_gate_contract.get("release_safe_docs_required") is True
            and promotion_gate_contract.get("ready_for_provider_execution_design") is True
            and promotion_gate_contract.get("ready_for_local_research_client_iteration") is True
            and promotion_gate_contract.get("ready_for_release_promotion") is False
            and promotion_gate_contract.get("production_live_light_complete") is False
            and "treat local bootstrap skeleton as production evidence"
            in set(_list(promotion_gate_contract.get("not_allowed_next_steps")))
            and "promote live_light without remote CI green"
            in set(_list(promotion_gate_contract.get("not_allowed_next_steps")))
            and promotion_gate_contract.get("symbol_limit_visible_safe") == 2
            and promotion_gate_contract.get("rate_limit_seconds_visible_safe") == 600
            and promotion_gate_contract.get("source_switches_effective") is True
            and _dict(status.get("live_light")).get("promotion_gate_contract_visible") is True
            and _dict(status.get("live_light")).get("promotion_gate_layer_count") == 4
            and _dict(status.get("live_light")).get("promotion_gate_ready_for_release") is False
            and _dict(status.get("policy")).get("live_light_promotion_gate_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_promotion_gate_remote_ci_green") is False
            and _dict(status.get("policy")).get("live_light_promotion_gate_ready_for_release") is False
            and _dict(status.get("policy")).get("live_light_promotion_gate_contract_is_production_evidence")
            is False
            and promotion_gate_contract.get("provider_execution_implemented") is False
            and promotion_gate_contract.get("model_execution_implemented") is False
            and promotion_gate_contract.get("external_calls_triggered") is False
            and promotion_gate_contract.get("tushare_called") is False
            and promotion_gate_contract.get("deepseek_called") is False
            and promotion_gate_contract.get("github_called") is False
            and promotion_gate_contract.get("contains_secret") is False
            and promotion_gate_contract.get("does_not_execute_trades") is True
            and promotion_gate_contract.get("does_not_modify_strategy_action") is True,
            f"promotion_gate_contract={promotion_gate_contract}",
        ),
        _row(
            "live_light_worker_dispatch_contract_declares_future_queues_without_starting_worker_or_execution",
            worker_dispatch_contract.get("schema_version")
            == "command_center_live_light_worker_dispatch_contract.v1"
            and worker_dispatch_contract.get("status") == "worker_dispatch_contract_visible_executor_pending"
            and worker_dispatch_contract.get("mode") == "live_light"
            and worker_dispatch_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and worker_dispatch_contract.get("task_type") == "command_center_live_bootstrap"
            and worker_dispatch_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and worker_dispatch_contract.get("dispatch_row_count") == 5
            and worker_dispatch_contract.get("declared_future_queues")
            == ["provider_refresh", "model_explain", "local_compute", "local_maintenance"]
            and {
                "bootstrap_entrypoint",
                "tushare_light_refresh",
                "factor_light_runtime",
                "next_session_cache_refresh",
                "deepseek_pro_explanation",
            }
            == {
                str(_dict(row).get("stage_key") or "")
                for row in _list(worker_dispatch_contract.get("dispatch_rows"))
            }
            and _dict(
                {
                    str(_dict(row).get("stage_key") or ""): _dict(row)
                    for row in _list(worker_dispatch_contract.get("dispatch_rows"))
                }.get("bootstrap_entrypoint", {})
            ).get("future_queue")
            == "local_maintenance"
            and _dict(
                {
                    str(_dict(row).get("stage_key") or ""): _dict(row)
                    for row in _list(worker_dispatch_contract.get("dispatch_rows"))
                }.get("tushare_light_refresh", {})
            ).get("future_queue")
            == "provider_refresh"
            and _dict(
                {
                    str(_dict(row).get("stage_key") or ""): _dict(row)
                    for row in _list(worker_dispatch_contract.get("dispatch_rows"))
                }.get("tushare_light_refresh", {})
            ).get("requires_execution_request")
            is True
            and _dict(
                {
                    str(_dict(row).get("stage_key") or ""): _dict(row)
                    for row in _list(worker_dispatch_contract.get("dispatch_rows"))
                }.get("deepseek_pro_explanation", {})
            ).get("future_queue")
            == "model_explain"
            and _dict(
                {
                    str(_dict(row).get("stage_key") or ""): _dict(row)
                    for row in _list(worker_dispatch_contract.get("dispatch_rows"))
                }.get("deepseek_pro_explanation", {})
            ).get("model_ledger_required")
            is True
            and all(
                _dict(row).get("worker_dispatch_implemented") is False
                and _dict(row).get("provider_or_model_execution_allowed_now") is False
                and _dict(row).get("safe_ledger_required") is True
                for row in _list(worker_dispatch_contract.get("dispatch_rows"))
            )
            and worker_dispatch_contract.get("current_runtime") == "local_fallback_task_skeleton"
            and worker_dispatch_contract.get("post_task_boundary_required") is True
            and worker_dispatch_contract.get("worker_or_local_fallback_required") is True
            and worker_dispatch_contract.get("local_fallback_allowed_now") is True
            and worker_dispatch_contract.get("celery_dispatch_implemented") is False
            and worker_dispatch_contract.get("redis_broker_required_for_current_contract") is False
            and worker_dispatch_contract.get("redis_broker_pinged") is False
            and worker_dispatch_contract.get("worker_process_started") is False
            and worker_dispatch_contract.get("scheduler_auto_dispatch_allowed") is False
            and worker_dispatch_contract.get("cache_get_dispatches_worker") is False
            and worker_dispatch_contract.get("status_get_dispatches_worker") is False
            and worker_dispatch_contract.get("react_render_dispatches_worker") is False
            and worker_dispatch_contract.get("fastapi_startup_dispatches_worker") is False
            and worker_dispatch_contract.get("page_open_direct_worker_dispatch_allowed") is False
            and worker_dispatch_contract.get("react_after_cache_render_may_create_post_task") is True
            and worker_dispatch_contract.get("post_task_may_route_to_worker_in_future") is True
            and worker_dispatch_contract.get("provider_worker_requires_execution_request") is True
            and worker_dispatch_contract.get("model_worker_requires_execution_request") is True
            and worker_dispatch_contract.get("provider_worker_requires_call_ledger") is True
            and worker_dispatch_contract.get("model_worker_requires_model_ledger") is True
            and worker_dispatch_contract.get("local_compute_may_refresh_from_existing_cache") is True
            and worker_dispatch_contract.get("local_compute_may_synthesize_provider_rows") is False
            and worker_dispatch_contract.get("local_compute_may_synthesize_model_output") is False
            and worker_dispatch_contract.get("unbounded_queue_allowed") is False
            and worker_dispatch_contract.get("rate_limit_must_apply_before_dispatch") is True
            and worker_dispatch_contract.get("session_dedupe_must_apply_before_dispatch") is True
            and worker_dispatch_contract.get("source_switches_effective") is True
            and _dict(status.get("live_light")).get("worker_dispatch_contract_visible") is True
            and _dict(status.get("live_light")).get("worker_dispatch_row_count") == 5
            and _dict(status.get("live_light")).get("worker_dispatch_current_runtime")
            == "local_fallback_task_skeleton"
            and _dict(status.get("live_light")).get("worker_dispatch_celery_implemented") is False
            and _dict(status.get("policy")).get("live_light_worker_dispatch_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_worker_dispatch_celery_implemented") is False
            and _dict(status.get("policy")).get("live_light_worker_dispatch_is_production_evidence") is False
            and worker_dispatch_contract.get("worker_dispatch_contract_is_provider_execution_evidence") is False
            and worker_dispatch_contract.get("worker_dispatch_contract_is_model_execution_evidence") is False
            and worker_dispatch_contract.get("worker_dispatch_contract_is_production_evidence") is False
            and worker_dispatch_contract.get("provider_execution_implemented") is False
            and worker_dispatch_contract.get("model_execution_implemented") is False
            and worker_dispatch_contract.get("external_calls_triggered") is False
            and worker_dispatch_contract.get("tushare_called") is False
            and worker_dispatch_contract.get("deepseek_called") is False
            and worker_dispatch_contract.get("github_called") is False
            and worker_dispatch_contract.get("contains_secret") is False
            and worker_dispatch_contract.get("does_not_execute_trades") is True
            and worker_dispatch_contract.get("does_not_modify_strategy_action") is True,
            f"worker_dispatch_contract={worker_dispatch_contract}",
        ),
        _row(
            "live_light_credential_preflight_contract_is_post_only_no_secret_value_exposure",
            credential_contract.get("schema_version")
            == "command_center_live_light_credential_preflight_contract.v1"
            and credential_contract.get("status") == "credential_preflight_contract_visible_post_only"
            and credential_contract.get("mode") == "live_light"
            and credential_contract.get("status_get_reads_credential_values") is False
            and credential_contract.get("status_get_checks_credential_presence") is False
            and credential_contract.get("status_get_exposes_env_key_names") is False
            and credential_contract.get("status_get_exposes_credential_values") is False
            and credential_contract.get("credential_presence_check_route")
            == "POST /api/bootstrap/provider-model-acceptance-dry-run"
            and credential_contract.get("credential_presence_check_requires_post") is True
            and credential_contract.get("credential_presence_check_requires_user_approval") is True
            and credential_contract.get("credential_presence_check_method") == "environment_key_membership_only"
            and credential_contract.get("credential_presence_check_reads_values") is False
            and credential_contract.get("credential_presence_check_exposes_values") is False
            and credential_contract.get("credential_presence_check_exposes_env_key_names") is False
            and credential_contract.get("credential_presence_check_exposes_value_lengths") is False
            and credential_contract.get("safe_provider_labels_only") is True
            and credential_contract.get("allowed_provider_labels") == ["tushare", "deepseek"]
            and credential_contract.get("frontend_packet_may_contain_token_key") is False
            and credential_contract.get("logs_may_contain_token_key") is False
            and credential_contract.get("cache_may_contain_token_key") is False
            and credential_contract.get("raw_config_dump_allowed") is False
            and credential_contract.get("provider_execution_allowed_from_preflight") is False
            and credential_contract.get("model_execution_allowed_from_preflight") is False
            and credential_contract.get("production_promotion_allowed_from_preflight") is False
            and _dict(status.get("policy")).get("live_light_credential_preflight_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_status_get_checks_credential_presence") is False
            and _dict(status.get("policy")).get("live_light_credential_presence_check_requires_post") is True
            and _dict(status.get("policy")).get("live_light_credential_presence_check_requires_user_approval")
            is True
            and _dict(status.get("policy")).get("live_light_credential_values_exposed") is False
            and credential_contract.get("external_calls_triggered") is False
            and credential_contract.get("tushare_called") is False
            and credential_contract.get("deepseek_called") is False
            and credential_contract.get("github_called") is False
            and credential_contract.get("contains_secret") is False
            and credential_contract.get("does_not_execute_trades") is True
            and credential_contract.get("does_not_modify_strategy_action") is True,
            f"credential_contract={credential_contract}",
        ),
        _row(
            "live_light_provider_model_execution_request_contract_binds_scope_before_real_execution",
            execution_request_contract.get("schema_version")
            == "command_center_live_light_provider_model_execution_request_contract.v1"
            and execution_request_contract.get("status") == "execution_request_contract_visible_provider_model_pending"
            and execution_request_contract.get("mode") == "live_light"
            and execution_request_contract.get("acceptance_dry_run_route")
            == "POST /api/bootstrap/provider-model-acceptance-dry-run"
            and execution_request_contract.get("execution_request_route")
            == "POST /api/bootstrap/provider-model-execution-request"
            and execution_request_contract.get("target_provider_model_route")
            == "future POST /api/bootstrap/provider-model-acceptance"
            and execution_request_contract.get("target_provider_model_task_type")
            == "command_center_live_bootstrap_provider_model_acceptance"
            and execution_request_contract.get("dry_run_is_execution_request") is False
            and execution_request_contract.get("dry_run_may_call_provider_or_model") is False
            and execution_request_contract.get("execution_request_is_provider_execution") is False
            and execution_request_contract.get("execution_request_creates_provider_model_task") is False
            and execution_request_contract.get("cache_get_initializes_execution_request") is False
            and execution_request_contract.get("react_render_initializes_execution_request") is False
            and execution_request_contract.get("page_open_initializes_execution_request") is False
            and execution_request_contract.get("search_typing_initializes_execution_request") is False
            and execution_request_contract.get("requires_latest_acceptance_scope_hash") is True
            and execution_request_contract.get("requires_scope_hash_match") is True
            and execution_request_contract.get("requires_explicit_user_confirmation") is True
            and execution_request_contract.get("requires_credential_preflight_ready") is True
            and execution_request_contract.get("requires_selected_provider_or_model_scope") is True
            and execution_request_contract.get("requires_call_ledger") is True
            and execution_request_contract.get("requires_model_ledger_for_deepseek") is True
            and execution_request_contract.get("requires_ledger_redaction_review_before_promotion") is True
            and execution_request_contract.get("provider_model_execution_implemented") is False
            and execution_request_contract.get("execution_request_route_implemented") is True
            and execution_request_contract.get("local_execution_request_receipt_service_implemented") is True
            and execution_request_contract.get("local_execution_request_receipt_task_type")
            == "command_center_live_bootstrap_provider_model_execution_request"
            and execution_request_contract.get("local_execution_request_receipt_packet_key")
            == "command_center_live_bootstrap_provider_model_execution_request_packet"
            and execution_request_contract.get("local_execution_request_receipt_persists_to_task_status")
            is True
            and execution_request_contract.get("provider_execution_implemented") is False
            and execution_request_contract.get("model_execution_implemented") is False
            and execution_request_contract.get("automatic_provider_model_execution_allowed") is False
            and execution_request_contract.get("production_promotion_allowed_from_execution_request") is False
            and execution_request_contract.get("allowed_next_step")
            == "verify_button_gated_execution_request_route_before_provider_model_task"
            and "treat acceptance dry-run as execution request"
            in set(_list(execution_request_contract.get("not_allowed_next_steps")))
            and "execute provider/model without latest scope hash match"
            in set(_list(execution_request_contract.get("not_allowed_next_steps")))
            and _dict(status.get("policy")).get("live_light_provider_model_execution_request_contract_visible")
            is True
            and _dict(status.get("policy")).get("live_light_provider_model_acceptance_requires_execution_request")
            is True
            and _dict(status.get("policy")).get("live_light_provider_model_execution_request_implemented") is True
            and _dict(status.get("policy")).get("live_light_dry_run_is_execution_request") is False
            and _dict(status.get("policy")).get("live_light_execution_request_requires_latest_scope_hash") is True
            and _dict(status.get("policy")).get("live_light_execution_request_requires_user_confirmation") is True
            and execution_request_contract.get("external_calls_triggered") is False
            and execution_request_contract.get("tushare_called") is False
            and execution_request_contract.get("deepseek_called") is False
            and execution_request_contract.get("github_called") is False
            and execution_request_contract.get("contains_secret") is False
            and execution_request_contract.get("does_not_execute_trades") is True
            and execution_request_contract.get("does_not_modify_strategy_action") is True,
            f"execution_request_contract={execution_request_contract}",
        ),
        _row(
            "live_light_execution_request_handoff_contract_requires_durable_receipt_before_provider_model_task",
            execution_request_handoff_contract.get("schema_version")
            == "command_center_live_light_execution_request_handoff_contract.v1"
            and execution_request_handoff_contract.get("status")
            == "execution_request_handoff_contract_visible_route_registered"
            and execution_request_handoff_contract.get("mode") == "live_light"
            and execution_request_handoff_contract.get("acceptance_dry_run_route")
            == "POST /api/bootstrap/provider-model-acceptance-dry-run"
            and execution_request_handoff_contract.get("execution_request_route")
            == "POST /api/bootstrap/provider-model-execution-request"
            and execution_request_handoff_contract.get("target_provider_model_route")
            == "future POST /api/bootstrap/provider-model-acceptance"
            and execution_request_handoff_contract.get("handoff_row_count") == 5
            and {
                "dry_run_receipt_lookup",
                "scope_hash_binding",
                "operator_confirmation",
                "credential_preflight_summary",
                "provider_model_task_handoff",
            }
            == {
                str(_dict(row).get("handoff_key") or "")
                for row in _list(execution_request_handoff_contract.get("handoff_rows"))
            }
            and {"latest_acceptance_dry_run_task_id", "acceptance_scope_hash", "user_confirmed", "safe_payload_only"}.issubset(
                set(_list(execution_request_handoff_contract.get("required_handoff_fields")))
            )
            and _dict(
                {
                    str(_dict(row).get("handoff_key") or ""): _dict(row)
                    for row in _list(execution_request_handoff_contract.get("handoff_rows"))
                }.get("dry_run_receipt_lookup", {})
            ).get("source")
            == "task_service_status_or_sqlite_meta"
            and _dict(
                {
                    str(_dict(row).get("handoff_key") or ""): _dict(row)
                    for row in _list(execution_request_handoff_contract.get("handoff_rows"))
                }.get("scope_hash_binding", {})
            ).get("scope_hash_mismatch_blocks_handoff")
            is True
            and _dict(
                {
                    str(_dict(row).get("handoff_key") or ""): _dict(row)
                    for row in _list(execution_request_handoff_contract.get("handoff_rows"))
                }.get("operator_confirmation", {})
            ).get("requires_explicit_user_confirmation")
            is True
            and _dict(
                {
                    str(_dict(row).get("handoff_key") or ""): _dict(row)
                    for row in _list(execution_request_handoff_contract.get("handoff_rows"))
                }.get("credential_preflight_summary", {})
            ).get("booleans_only")
            is True
            and _dict(
                {
                    str(_dict(row).get("handoff_key") or ""): _dict(row)
                    for row in _list(execution_request_handoff_contract.get("handoff_rows"))
                }.get("credential_preflight_summary", {})
            ).get("credential_values_exposed")
            is False
            and _dict(
                {
                    str(_dict(row).get("handoff_key") or ""): _dict(row)
                    for row in _list(execution_request_handoff_contract.get("handoff_rows"))
                }.get("provider_model_task_handoff", {})
            ).get("creates_provider_model_task_now")
            is False
            and execution_request_handoff_contract.get("dry_run_receipt_required") is True
            and execution_request_handoff_contract.get("latest_dry_run_task_id_required") is True
            and execution_request_handoff_contract.get("acceptance_scope_hash_required") is True
            and execution_request_handoff_contract.get("scope_hash_algorithm_required") is True
            and execution_request_handoff_contract.get("scope_hash_mismatch_blocks_handoff") is True
            and execution_request_handoff_contract.get("explicit_user_confirmation_required") is True
            and execution_request_handoff_contract.get("selected_provider_or_model_scope_required") is True
            and execution_request_handoff_contract.get("credential_preflight_ready_required") is True
            and execution_request_handoff_contract.get("credential_presence_booleans_only") is True
            and execution_request_handoff_contract.get("safe_payload_only") is True
            and execution_request_handoff_contract.get("durable_receipt_visibility_required") is True
            and execution_request_handoff_contract.get("memory_only_dry_run_receipt_is_durable_evidence")
            is False
            and execution_request_handoff_contract.get("dry_run_is_execution_request") is False
            and execution_request_handoff_contract.get("execution_request_route_implemented") is True
            and execution_request_handoff_contract.get("route_adapter_contract_visible") is True
            and execution_request_handoff_contract.get("route_adapter_target_file")
            == "server/api/routes_bootstrap.py"
            and execution_request_handoff_contract.get("route_adapter_function_name")
            == "post_bootstrap_provider_model_execution_request"
            and execution_request_handoff_contract.get("route_adapter_service_function")
            == "run_provider_model_execution_request"
            and execution_request_handoff_contract.get("route_adapter_response_envelope") == "task_envelope"
            and execution_request_handoff_contract.get("route_adapter_payload_type") == "dict[str, Any] | None"
            and execution_request_handoff_contract.get("route_adapter_current_status")
            == "registered_local_receipt_route"
            and execution_request_handoff_contract.get("route_adapter_must_be_button_gated") is True
            and execution_request_handoff_contract.get("route_adapter_accepts_safe_payload_only") is True
            and execution_request_handoff_contract.get("route_adapter_must_return_task_envelope") is True
            and execution_request_handoff_contract.get("route_adapter_creates_provider_model_task") is False
            and execution_request_handoff_contract.get("route_adapter_calls_provider_or_model") is False
            and execution_request_handoff_contract.get("route_adapter_external_calls_triggered") is False
            and execution_request_handoff_contract.get("route_adapter_allowed_next_step")
            == "verify_button_gated_route_adapter_then_keep_provider_model_pending"
            and "call provider/model from route adapter"
            in set(_list(execution_request_handoff_contract.get("route_adapter_not_allowed_next_steps")))
            and "treat route adapter success as provider/model acceptance"
            in set(_list(execution_request_handoff_contract.get("route_adapter_not_allowed_next_steps")))
            and execution_request_handoff_contract.get("local_execution_request_receipt_service_implemented")
            is True
            and execution_request_handoff_contract.get("local_execution_request_receipt_task_type")
            == "command_center_live_bootstrap_provider_model_execution_request"
            and execution_request_handoff_contract.get("local_execution_request_receipt_packet_key")
            == "command_center_live_bootstrap_provider_model_execution_request_packet"
            and execution_request_handoff_contract.get("local_execution_request_receipt_persists_to_task_status")
            is True
            and execution_request_handoff_contract.get("execution_request_creates_provider_model_task") is False
            and execution_request_handoff_contract.get("execution_request_receipt_persisted") is False
            and execution_request_handoff_contract.get("provider_model_task_created") is False
            and execution_request_handoff_contract.get("status_get_initializes_handoff") is False
            and execution_request_handoff_contract.get("cache_get_initializes_handoff") is False
            and execution_request_handoff_contract.get("react_render_initializes_handoff") is False
            and execution_request_handoff_contract.get("page_open_initializes_handoff") is False
            and execution_request_handoff_contract.get("search_typing_initializes_handoff") is False
            and execution_request_handoff_contract.get("fastapi_startup_initializes_handoff") is False
            and execution_request_handoff_contract.get("call_ledger_required") is True
            and execution_request_handoff_contract.get("model_ledger_required_for_deepseek") is True
            and execution_request_handoff_contract.get("redaction_review_required_before_promotion") is True
            and execution_request_handoff_contract.get("credential_values_exposed") is False
            and execution_request_handoff_contract.get("credential_env_key_names_exposed") is False
            and _dict(status.get("live_light")).get("execution_request_handoff_contract_visible") is True
            and _dict(status.get("live_light")).get("execution_request_handoff_row_count") == 5
            and _dict(status.get("live_light")).get("execution_request_handoff_route_implemented") is True
            and _dict(status.get("live_light")).get("execution_request_receipt_service_implemented") is True
            and _dict(status.get("live_light")).get("execution_request_route_adapter_contract_visible") is True
            and _dict(status.get("live_light")).get("execution_request_route_adapter_target_file")
            == "server/api/routes_bootstrap.py"
            and _dict(status.get("live_light")).get("execution_request_route_adapter_service_function")
            == "run_provider_model_execution_request"
            and _dict(status.get("live_light")).get("execution_request_route_adapter_response_envelope")
            == "task_envelope"
            and _dict(status.get("live_light")).get("execution_request_route_adapter_current_status")
            == "registered_local_receipt_route"
            and _dict(status.get("live_light")).get(
                "execution_request_route_adapter_provider_model_task_creation_allowed"
            )
            is False
            and _dict(status.get("live_light")).get("execution_request_route_adapter_calls_provider_or_model")
            is False
            and _dict(status.get("policy")).get("live_light_execution_request_handoff_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_execution_request_handoff_route_implemented")
            is True
            and _dict(status.get("policy")).get("live_light_execution_request_receipt_service_implemented")
            is True
            and _dict(status.get("policy")).get(
                "live_light_execution_request_route_adapter_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get("live_light_execution_request_route_adapter_target_file")
            == "server/api/routes_bootstrap.py"
            and _dict(status.get("policy")).get(
                "live_light_execution_request_route_adapter_service_function"
            )
            == "run_provider_model_execution_request"
            and _dict(status.get("policy")).get(
                "live_light_execution_request_route_adapter_response_envelope"
            )
            == "task_envelope"
            and _dict(status.get("policy")).get(
                "live_light_execution_request_route_adapter_current_status"
            )
            == "registered_local_receipt_route"
            and _dict(status.get("policy")).get(
                "live_light_execution_request_route_adapter_provider_model_task_creation_allowed"
            )
            is False
            and _dict(status.get("policy")).get(
                "live_light_execution_request_route_adapter_calls_provider_or_model"
            )
            is False
            and _dict(status.get("policy")).get("live_light_execution_request_handoff_is_production_evidence")
            is False
            and execution_request_handoff_contract.get("local_handoff_contract_is_provider_execution_evidence")
            is False
            and execution_request_handoff_contract.get("local_handoff_contract_is_model_execution_evidence")
            is False
            and execution_request_handoff_contract.get("local_handoff_contract_is_production_evidence") is False
            and execution_request_handoff_contract.get("provider_execution_implemented") is False
            and execution_request_handoff_contract.get("model_execution_implemented") is False
            and execution_request_handoff_contract.get("provider_model_execution_implemented") is False
            and execution_request_handoff_contract.get("external_calls_triggered") is False
            and execution_request_handoff_contract.get("tushare_called") is False
            and execution_request_handoff_contract.get("deepseek_called") is False
            and execution_request_handoff_contract.get("github_called") is False
            and execution_request_handoff_contract.get("contains_secret") is False
            and execution_request_handoff_contract.get("does_not_execute_trades") is True
            and execution_request_handoff_contract.get("does_not_modify_strategy_action") is True,
            f"execution_request_handoff_contract={execution_request_handoff_contract}",
        ),
        _row(
            "live_light_evidence_grade_contract_blocks_local_artifact_promotion",
            evidence_contract.get("schema_version") == "command_center_live_light_evidence_grade_contract.v1"
            and evidence_contract.get("status") == "local_evidence_visible_production_evidence_pending"
            and evidence_contract.get("mode") == "live_light"
            and evidence_contract.get("local_evidence_grade") == "contract_receipt_plan_only"
            and evidence_contract.get("production_evidence_grade")
            == "pending_real_provider_model_runtime_promotion"
            and evidence_contract.get("local_task_skeleton_is_production_evidence") is False
            and evidence_contract.get("activation_receipt_is_production_evidence") is False
            and evidence_contract.get("acceptance_runbook_is_production_evidence") is False
            and evidence_contract.get("provider_linkage_matrix_is_provider_evidence") is False
            and evidence_contract.get("model_ledger_preview_is_model_execution_evidence") is False
            and evidence_contract.get("sanitizer_is_model_correctness_evidence") is False
            and evidence_contract.get("mock_receipt_matrix_sanitizer_can_promote") is False
            and evidence_contract.get("provider_execution_evidence_done") is False
            and evidence_contract.get("model_execution_evidence_done") is False
            and evidence_contract.get("browser_runtime_evidence_done") is False
            and evidence_contract.get("ledger_redaction_review_done") is False
            and evidence_contract.get("production_promotion_review_done") is False
            and evidence_contract.get("production_live_light_complete") is False
            and "real Tushare call ledger with safe request params and result status"
            in set(_list(evidence_contract.get("required_production_evidence")))
            and "real DeepSeek model ledger with redacted token usage and prompt/output hashes"
            in set(_list(evidence_contract.get("required_production_evidence")))
            and "promote local task skeleton as production evidence"
            in set(_list(evidence_contract.get("not_allowed_next_steps")))
            and _dict(status.get("policy")).get("live_light_evidence_grade_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_local_artifacts_are_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_production_evidence_pending") is True
            and _dict(status.get("policy")).get("live_light_mock_receipt_matrix_sanitizer_can_promote") is False
            and evidence_contract.get("external_calls_triggered") is False
            and evidence_contract.get("tushare_called") is False
            and evidence_contract.get("deepseek_called") is False
            and evidence_contract.get("github_called") is False
            and evidence_contract.get("does_not_execute_trades") is True
            and evidence_contract.get("does_not_modify_strategy_action") is True,
            f"evidence_contract={evidence_contract}",
        ),
        _row(
            "live_light_ledger_contract_requires_redacted_call_and_model_ledgers",
            ledger_contract.get("schema_version") == "command_center_live_light_ledger_contract.v1"
            and ledger_contract.get("status") == "ledger_contract_visible_runtime_execution_pending"
            and ledger_contract.get("mode") == "live_light"
            and ledger_contract.get("call_ledger_required_for_provider") is True
            and ledger_contract.get("model_ledger_required_for_deepseek") is True
            and {"api", "endpoint", "call_status", "request_params_safe", "external", "external_calls_triggered"}.issubset(
                set(_list(ledger_contract.get("required_call_ledger_fields")))
            )
            and {"model_used", "purpose", "status", "token_usage", "input_hash", "output_hash", "parse_status", "cache_hit", "sanitizer_status"}.issubset(
                set(_list(ledger_contract.get("required_model_ledger_fields")))
            )
            and ledger_contract.get("request_params_must_be_safe") is True
            and ledger_contract.get("credential_values_exposed") is False
            and ledger_contract.get("credential_env_key_names_exposed_to_frontend") is False
            and ledger_contract.get("frontend_packet_may_contain_token_key") is False
            and ledger_contract.get("logs_may_contain_token_key") is False
            and ledger_contract.get("cache_may_contain_token_key") is False
            and ledger_contract.get("raw_prompt_or_raw_model_output_exposed") is False
            and ledger_contract.get("prompt_output_hashes_required") is True
            and ledger_contract.get("token_usage_required") is True
            and ledger_contract.get("parse_status_required") is True
            and ledger_contract.get("cache_hit_or_miss_required") is True
            and ledger_contract.get("sanitizer_status_required") is True
            and ledger_contract.get("redaction_review_required_before_promotion") is True
            and ledger_contract.get("provider_execution_implemented") is False
            and ledger_contract.get("model_execution_implemented") is False
            and ledger_contract.get("production_promotion_allowed_without_ledger") is False
            and _dict(status.get("policy")).get("live_light_ledger_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_call_ledger_required") is True
            and _dict(status.get("policy")).get("live_light_model_ledger_required") is True
            and _dict(status.get("policy")).get("live_light_redaction_review_required_before_promotion") is True
            and _dict(status.get("policy")).get("live_light_production_promotion_allowed_without_ledger") is False
            and ledger_contract.get("external_calls_triggered") is False
            and ledger_contract.get("tushare_called") is False
            and ledger_contract.get("deepseek_called") is False
            and ledger_contract.get("github_called") is False
            and ledger_contract.get("contains_secret") is False
            and ledger_contract.get("does_not_execute_trades") is True
            and ledger_contract.get("does_not_modify_strategy_action") is True,
            f"ledger_contract={ledger_contract}",
        ),
        _row(
            "live_light_ledger_redaction_invariant_blocks_secret_and_raw_surfaces",
            ledger_redaction_invariant.get("schema_version")
            == "command_center_live_light_ledger_redaction_invariant.v1"
            and ledger_redaction_invariant.get("status")
            == "ledger_redaction_invariant_visible_promotion_blocking"
            and ledger_redaction_invariant.get("mode") == "live_light"
            and ledger_redaction_invariant.get("prohibited_surface_count") == 6
            and ledger_redaction_invariant.get("required_ledger_row_count") == 5
            and {
                "credential_value",
                "credential_env_key_name",
                "credential_material_label",
                "secret_material_label",
                "authorization_header",
                "raw_prompt",
                "raw_model_output",
                "raw_provider_response",
            }.issubset(set(_list(ledger_redaction_invariant.get("prohibited_fields"))))
            and {
                str(row.get("surface_key") or "")
                for row in _list(ledger_redaction_invariant.get("prohibited_surface_rows"))
                if isinstance(row, dict)
            }
            == {
                "frontend_packet",
                "log_line",
                "cache_payload",
                "task_status_payload",
                "call_ledger_request_params_safe",
                "model_ledger_safe_summary",
            }
            and all(
                _dict(row).get("safe_summary_only") is True
                and _dict(row).get("credential_value_allowed") is False
                and _dict(row).get("credential_env_key_name_allowed") is False
                and _dict(row).get("token_key_allowed") is False
                and _dict(row).get("authorization_header_allowed") is False
                and _dict(row).get("raw_prompt_allowed") is False
                and _dict(row).get("raw_model_output_allowed") is False
                and _dict(row).get("raw_provider_response_allowed") is False
                and _dict(row).get("redacted_safe_summary_required") is True
                for row in _list(ledger_redaction_invariant.get("prohibited_surface_rows"))
            )
            and {
                str(row.get("ledger_key") or "")
                for row in _list(ledger_redaction_invariant.get("required_ledger_rows"))
                if isinstance(row, dict)
            }
            == {
                "tushare_call_ledger",
                "deepseek_model_ledger",
                "redaction_review",
                "prompt_output_hashes",
                "no_action_mutation_flags",
            }
            and all(
                _dict(row).get("required_before_promotion") is True
                and _dict(row).get("production_promotion_blocker_until_complete") is True
                and _dict(row).get("contract_row_is_production_evidence") is False
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("tushare_called") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("github_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("does_not_execute_trades") is True
                and _dict(row).get("does_not_modify_strategy_action") is True
                for row in _list(ledger_redaction_invariant.get("required_ledger_rows"))
            )
            and ledger_redaction_invariant.get("frontend_packet_may_contain_token_key") is False
            and ledger_redaction_invariant.get("logs_may_contain_token_key") is False
            and ledger_redaction_invariant.get("cache_may_contain_token_key") is False
            and ledger_redaction_invariant.get("task_status_may_contain_token_key") is False
            and ledger_redaction_invariant.get("credential_values_exposed") is False
            and ledger_redaction_invariant.get("credential_env_key_names_included") is False
            and ledger_redaction_invariant.get("raw_prompt_or_raw_model_output_exposed") is False
            and ledger_redaction_invariant.get("raw_provider_response_exposed") is False
            and ledger_redaction_invariant.get("request_params_must_be_safe") is True
            and ledger_redaction_invariant.get("safe_summary_only") is True
            and ledger_redaction_invariant.get("call_ledger_required_for_provider") is True
            and ledger_redaction_invariant.get("model_ledger_required_for_deepseek") is True
            and ledger_redaction_invariant.get("redaction_review_required_before_promotion") is True
            and ledger_redaction_invariant.get("provider_model_execution_requires_execution_request") is True
            and ledger_redaction_invariant.get("deepseek_is_data_source") is False
            and ledger_redaction_invariant.get(
                "deepseek_may_overwrite_prices_positions_factors_zones_or_actions"
            )
            is False
            and ledger_redaction_invariant.get("production_promotion_allowed_without_redaction_review") is False
            and ledger_redaction_invariant.get("ledger_redaction_invariant_is_production_evidence") is False
            and ledger_redaction_invariant.get("production_live_light_complete") is False
            and ledger_redaction_invariant.get("provider_execution_implemented") is False
            and ledger_redaction_invariant.get("model_execution_implemented") is False
            and _dict(status.get("live_light")).get("ledger_redaction_invariant_contract_visible") is True
            and _dict(status.get("live_light")).get("ledger_redaction_prohibited_surface_count") == 6
            and _dict(status.get("live_light")).get("ledger_redaction_required_ledger_row_count") == 5
            and _dict(status.get("live_light")).get("ledger_redaction_review_required_before_promotion") is True
            and _dict(status.get("live_light")).get("ledger_redaction_raw_payload_exposed") is False
            and _dict(status.get("live_light")).get("ledger_redaction_credential_material_exposed") is False
            and _dict(status.get("live_light")).get("ledger_redaction_invariant_is_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_ledger_redaction_invariant_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_ledger_redaction_prohibited_surface_count") == 6
            and _dict(status.get("policy")).get("live_light_ledger_redaction_required_ledger_row_count") == 5
            and _dict(status.get("policy")).get("live_light_ledger_redaction_review_required_before_promotion")
            is True
            and _dict(status.get("policy")).get("live_light_ledger_redaction_raw_payload_exposed") is False
            and _dict(status.get("policy")).get("live_light_ledger_redaction_credential_material_exposed")
            is False
            and _dict(status.get("policy")).get("live_light_ledger_redaction_invariant_is_production_evidence")
            is False
            and ledger_redaction_invariant.get("external_calls_triggered") is False
            and ledger_redaction_invariant.get("tushare_called") is False
            and ledger_redaction_invariant.get("deepseek_called") is False
            and ledger_redaction_invariant.get("github_called") is False
            and ledger_redaction_invariant.get("contains_secret") is False
            and ledger_redaction_invariant.get("does_not_execute_trades") is True
            and ledger_redaction_invariant.get("does_not_modify_strategy_action") is True,
            f"ledger_redaction_invariant={ledger_redaction_invariant}",
        ),
        _row(
            "search_quant_projection_workflow_contract_is_button_task_gated",
            search_contract.get("schema_version") == "command_center_search_quant_projection_workflow_contract.v1"
            and search_contract.get("status")
            == "search_quant_projection_task_contract_visible_provider_model_pending"
            and search_contract.get("mode") == "live_light"
            and search_contract.get("display_action") == "生成 3.0 量化推演"
            and search_contract.get("allowed_modes") == ["manual", "live_light"]
            and search_contract.get("search_input_creates_task") is False
            and search_contract.get("react_render_creates_task") is False
            and search_contract.get("cache_get_creates_task") is False
            and search_contract.get("react_render_calls_provider") is False
            and search_contract.get("provider_model_route_requires_execution_request") is True
            and search_contract.get("provider_model_route_is_button_gated") is True
            and search_contract.get("automatic_provider_model_execution_allowed") is False
            and search_contract.get("allowed_light_apis") == ["trade_cal", "daily", "daily_basic", "moneyflow"]
            and search_contract.get("call_ledger_required") is True
            and search_contract.get("model_ledger_required_for_deepseek") is True
            and search_contract.get("ui_progress_required") is True
            and search_contract.get("freshness_visible_required") is True
            and search_contract.get("provider_gap_visible_required") is True
            and search_contract.get("full_pool_or_deep_scan_on_render_allowed") is False
            and search_contract.get("radar_candidate_is_buy_instruction") is False
            and search_contract.get("deepseek_is_data_source") is False
            and search_contract.get("deepseek_may_overwrite_numeric_or_action_fields") is False
            and search_contract.get("production_quant_projection_complete") is False
            and search_contract.get("external_calls_triggered") is False
            and search_contract.get("tushare_called") is False
            and search_contract.get("deepseek_called") is False
            and search_contract.get("github_called") is False
            and search_contract.get("does_not_execute_trades") is True
            and search_contract.get("does_not_modify_strategy_action") is True,
            f"search_contract={search_contract}",
        ),
        _row(
            "search_quant_projection_submit_autostart_contract_allows_live_light_local_task_only",
            submit_autostart_contract.get("schema_version")
            == "command_center_search_quant_projection_submit_autostart_contract.v1"
            and submit_autostart_contract.get("status") == "ready_after_safe_search_submit_local_task_only"
            and submit_autostart_contract.get("mode") == "live_light"
            and submit_autostart_contract.get("surface") == "searched_symbol_submit"
            and submit_autostart_contract.get("allowed_auto_start_mode") == "live_light"
            and submit_autostart_contract.get("config_switch") == "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
            and submit_autostart_contract.get("config_switch_default") is False
            and submit_autostart_contract.get("config_switch_source") == "configured"
            and submit_autostart_contract.get("server_config_switch_required") is True
            and submit_autostart_contract.get("configured_submit_autostart") is True
            and submit_autostart_contract.get("effective_submit_autostart") is True
            and submit_autostart_contract.get("task_route") == "POST /api/candidate-radar/quant-projection"
            and submit_autostart_contract.get("task_type") == "run_candidate_radar_quant_projection"
            and submit_autostart_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and submit_autostart_contract.get("provider_model_route")
            == "POST /api/candidate-radar/quant-projection-provider-model-acceptance"
            and submit_autostart_contract.get("acceptance_dry_run_route")
            == "POST /api/candidate-radar/quant-projection-acceptance-dry-run"
            and submit_autostart_contract.get("execution_request_route")
            == "POST /api/candidate-radar/quant-projection-execution-request"
            and submit_autostart_contract.get("task_catalog_route") == "GET /api/tasks/catalog"
            and submit_autostart_contract.get("task_catalog_task_type") == "run_candidate_radar_quant_projection"
            and submit_autostart_contract.get("task_catalog_button_gated") is True
            and submit_autostart_contract.get("task_catalog_current_backend") == "local_cache_pipeline"
            and submit_autostart_contract.get("task_catalog_external_call_policy")
            == "local_search_quant_projection_receipt_only_no_external_call"
            and submit_autostart_contract.get("task_catalog_possible_external_sources") == []
            and submit_autostart_contract.get("task_catalog_future_external_sources") == ["tushare", "deepseek"]
            and submit_autostart_contract.get("local_projection_route_implemented") is True
            and submit_autostart_contract.get("local_projection_creates_task_status_record") is True
            and submit_autostart_contract.get("local_projection_writes_output_packet_key")
            == "command_center_3_candidate_radar_cache"
            and submit_autostart_contract.get("latest_status_replay_after_submit_required") is True
            and submit_autostart_contract.get("latest_status_replay_route") == "GET /api/bootstrap/status"
            and submit_autostart_contract.get("latest_status_replay_lookup_creates_task") is False
            and submit_autostart_contract.get("autostart_readiness_stage")
            == "backend_local_route_ready_frontend_wiring_pending"
            and submit_autostart_contract.get("backend_local_task_creation_ready") is True
            and submit_autostart_contract.get("frontend_submit_autostart_wiring_implemented") is False
            and submit_autostart_contract.get("ui_can_poll_created_task") is True
            and submit_autostart_contract.get("no_new_frontend_config_switch") is False
            and submit_autostart_contract.get("inherits_bootstrap_mode_config") is True
            and submit_autostart_contract.get("inherits_symbol_limit_and_rate_limit") is True
            and submit_autostart_contract.get("safe_submit_payload_fields")
            == ["symbol", "include_tushare", "include_deepseek"]
            and submit_autostart_contract.get("secret_like_payload_fields_dropped") is True
            and submit_autostart_contract.get("live_light_search_submit_auto_start_allowed") is True
            and submit_autostart_contract.get("manual_search_submit_auto_start_allowed") is False
            and submit_autostart_contract.get("cache_only_search_submit_auto_start_allowed") is False
            and submit_autostart_contract.get("live_full_search_submit_auto_start_allowed") is False
            and submit_autostart_contract.get("search_typing_creates_task") is False
            and submit_autostart_contract.get("search_input_change_creates_task") is False
            and submit_autostart_contract.get("react_render_creates_task") is False
            and submit_autostart_contract.get("cache_get_creates_task") is False
            and submit_autostart_contract.get("fastapi_startup_creates_task") is False
            and submit_autostart_contract.get("safe_search_submit_event_required") is True
            and submit_autostart_contract.get("safe_symbol_normalization_required") is True
            and submit_autostart_contract.get("symbol_limit") == 2
            and submit_autostart_contract.get("symbol_dedupe_required") is True
            and submit_autostart_contract.get("create_or_reuse_local_projection_task_only") is True
            and submit_autostart_contract.get("rate_limit_seconds") == 600
            and submit_autostart_contract.get("rate_limit_reuses_existing_task") is True
            and submit_autostart_contract.get("rate_limit_skip_creates_new_task") is False
            and submit_autostart_contract.get("session_dedupe_required") is True
            and submit_autostart_contract.get("ui_nonblocking_required") is True
            and submit_autostart_contract.get("task_status_polling_required") is True
            and submit_autostart_contract.get("result_surface_count") == 6
            and submit_autostart_contract.get("local_receipt_only_until_execution_request") is True
            and submit_autostart_contract.get("provider_model_route_requires_execution_request") is True
            and submit_autostart_contract.get("future_provider_model_after_submit_allowed_with_execution_request")
            is True
            and submit_autostart_contract.get("current_submit_autostart_calls_provider_model") is False
            and submit_autostart_contract.get("provider_model_autostart_without_execution_request_allowed") is False
            and submit_autostart_contract.get("provider_execution_implemented") is False
            and submit_autostart_contract.get("model_execution_implemented") is False
            and submit_autostart_contract.get("factor_refresh_executed") is False
            and submit_autostart_contract.get("next_session_refresh_executed") is False
            and submit_autostart_contract.get("echarts_payload_refreshed") is False
            and submit_autostart_contract.get("production_quant_projection_complete") is False
            and submit_autostart_contract.get("call_ledger_required") is True
            and submit_autostart_contract.get("model_ledger_required_for_deepseek") is True
            and submit_autostart_contract.get("safe_error_required") is True
            and submit_autostart_contract.get("raw_user_query_logged") is False
            and submit_autostart_contract.get("raw_user_query_cached") is False
            and submit_autostart_contract.get("token_key_exposure_allowed") is False
            and submit_autostart_contract.get("radar_candidate_is_buy_instruction") is False
            and submit_autostart_contract.get("deepseek_is_data_source") is False
            and submit_autostart_contract.get("deepseek_may_overwrite_numeric_or_action_fields") is False
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_contract_visible")
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_allowed") is True
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_config_switch")
            == "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_configured") is True
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_effective") is True
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_route")
            == "POST /api/candidate-radar/quant-projection"
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_readiness_stage")
            == "backend_local_route_ready_frontend_wiring_pending"
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_backend_ready")
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_frontend_wiring_implemented"
            )
            is False
            and _dict(status.get("live_light")).get("search_quant_projection_submit_autostart_task_catalog_covered")
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_provider_model_pending"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_contract_visible")
            is True
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_allowed") is True
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_config_switch")
            == "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_configured") is True
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_effective") is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_search_typing_creates_task"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_provider_model_without_request_allowed"
            )
            is False
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_backend_ready")
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_frontend_wiring_implemented"
            )
            is False
            and _dict(status.get("policy")).get("search_quant_projection_submit_autostart_task_catalog_covered")
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_latest_status_lookup_creates_task"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_is_production_evidence"
            )
            is False
            and submit_autostart_contract.get("external_calls_triggered") is False
            and submit_autostart_contract.get("tushare_called") is False
            and submit_autostart_contract.get("deepseek_called") is False
            and submit_autostart_contract.get("github_called") is False
            and submit_autostart_contract.get("contains_secret") is False
            and submit_autostart_contract.get("does_not_execute_trades") is True
            and submit_autostart_contract.get("does_not_modify_strategy_action") is True,
            f"submit_autostart_contract={submit_autostart_contract}",
        ),
        _row(
            "search_quant_projection_submit_autostart_config_handoff_is_visible_not_production",
            config_handoff_contract.get("schema_version")
            == "command_center_search_quant_projection_submit_autostart_config_handoff.v1"
            and config_handoff_contract.get("status")
            == "global_config_allowlist_promoted_bootstrap_fallback_removed"
            and config_handoff_contract.get("mode") == "live_light"
            and config_handoff_contract.get("config_key") == "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
            and config_handoff_contract.get("default_value_safe") is False
            and config_handoff_contract.get("configured_value_safe") is True
            and config_handoff_contract.get("effective_value_safe") is True
            and config_handoff_contract.get("source") == "configured"
            and config_handoff_contract.get("current_read_path")
            == "global_config_layer_only"
            and config_handoff_contract.get("target_read_path")
            == "global_config_layer_only"
            and config_handoff_contract.get("bootstrap_local_env_fallback_available") is False
            and config_handoff_contract.get("bootstrap_local_env_fallback_is_temporary") is False
            and config_handoff_contract.get("bootstrap_local_env_fallback_removed") is True
            and config_handoff_contract.get("uses_env_value_when_config_layer_omits_key") is False
            and config_handoff_contract.get("fallback_effective_after_global_config_read") is False
            and config_handoff_contract.get("global_config_allowlist_promoted") is True
            and config_handoff_contract.get("global_config_key_registered") is True
            and config_handoff_contract.get("global_config_allowlist_promotion_pending") is False
            and config_handoff_contract.get("config_py_update_pending") is False
            and config_handoff_contract.get("fallback_removal_pending") is False
            and config_handoff_contract.get("fallback_removal_complete") is True
            and config_handoff_contract.get("fallback_removal_allowed_after_global_config_promotion") is True
            and config_handoff_contract.get("frontend_visible") is True
            and config_handoff_contract.get("frontend_editable") is False
            and config_handoff_contract.get("frontend_writeback_allowed") is False
            and config_handoff_contract.get("status_endpoint_writeback_allowed") is False
            and config_handoff_contract.get("live_light_required_for_effective_autostart") is True
            and config_handoff_contract.get("creates_local_projection_task_only") is True
            and config_handoff_contract.get("creates_provider_model_task") is False
            and config_handoff_contract.get("provider_model_execution_requires_execution_request") is True
            and config_handoff_contract.get("config_handoff_is_production_evidence") is False
            and config_handoff_contract.get("production_config_complete") is False
            and config_handoff_contract.get("search_typing_creates_task") is False
            and config_handoff_contract.get("react_render_creates_task") is False
            and config_handoff_contract.get("cache_get_creates_task") is False
            and config_handoff_contract.get("fastapi_startup_creates_task") is False
            and config_handoff_contract.get("external_calls_triggered") is False
            and config_handoff_contract.get("tushare_called") is False
            and config_handoff_contract.get("deepseek_called") is False
            and config_handoff_contract.get("github_called") is False
            and config_handoff_contract.get("contains_secret") is False
            and config_handoff_contract.get("credential_values_exposed") is False
            and config_handoff_contract.get("credential_env_key_names_included") is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_config_handoff_visible"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_config_allowlist_promotion_pending"
            )
            is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_global_config_allowlist_promoted"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_config_handoff_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_config_handoff_visible"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_config_allowlist_promotion_pending"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_global_config_allowlist_promoted"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_config_handoff_is_production_evidence"
            )
            is False,
            f"config_handoff_contract={config_handoff_contract}",
        ),
        _row(
            "search_quant_projection_submit_autostart_config_promotion_runbook_is_visible_not_production",
            config_promotion_contract.get("schema_version")
            == "command_center_search_quant_projection_submit_autostart_config_promotion.v1"
            and config_promotion_contract.get("status")
            == "config_allowlist_promoted_fallback_removed_validation_pending"
            and config_promotion_contract.get("mode") == "live_light"
            and config_promotion_contract.get("config_key") == "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
            and config_promotion_contract.get("current_handoff_status")
            == "global_config_allowlist_promoted_bootstrap_fallback_removed"
            and config_promotion_contract.get("current_read_path")
            == "global_config_layer_only"
            and config_promotion_contract.get("target_read_path")
            == "global_config_layer_only"
            and config_promotion_contract.get("promotion_step_count") == 5
            and set(config_promotion_rows)
            == {
                "add_global_config_allowlist_key",
                "prove_global_config_read_path",
                "remove_bootstrap_local_env_fallback",
                "preserve_safe_config_surface",
                "rerun_validation_gate",
            }
            and config_promotion_rows.get("add_global_config_allowlist_key", {}).get("target_file")
            == "config.py"
            and config_promotion_rows.get("add_global_config_allowlist_key", {}).get("status")
            == "passed_global_config_allowlist_key_present"
            and config_promotion_rows.get("add_global_config_allowlist_key", {}).get("requires_future_file_scope")
            is False
            and config_promotion_rows.get("add_global_config_allowlist_key", {}).get("step_complete") is True
            and config_promotion_rows.get("add_global_config_allowlist_key", {}).get("external_calls_triggered")
            is False
            and config_promotion_rows.get("add_global_config_allowlist_key", {}).get("production_evidence")
            is False
            and config_promotion_rows.get("prove_global_config_read_path", {}).get("status")
            == "passed_safe_config_row_reads_global_config_layer"
            and config_promotion_rows.get("prove_global_config_read_path", {}).get("step_complete") is True
            and config_promotion_rows.get("remove_bootstrap_local_env_fallback", {}).get("status")
            == "passed_bootstrap_local_env_fallback_removed"
            and config_promotion_rows.get("remove_bootstrap_local_env_fallback", {}).get("step_complete") is True
            and config_promotion_rows.get("preserve_safe_config_surface", {}).get("status")
            == "passed_safe_config_surface_read_only"
            and config_promotion_rows.get("preserve_safe_config_surface", {}).get("step_complete") is True
            and config_promotion_rows.get("rerun_validation_gate", {}).get("status")
            == "ready_for_local_validation_after_fallback_removal"
            and config_promotion_contract.get("current_cycle_modifies_global_config_file") is False
            and config_promotion_contract.get("global_config_file_already_promoted") is True
            and config_promotion_contract.get("current_cycle_file_limit_respected") is True
            and config_promotion_contract.get("requires_future_config_py_file_scope") is False
            and config_promotion_contract.get("config_py_update_pending") is False
            and config_promotion_contract.get("bootstrap_local_env_fallback_removal_pending") is False
            and config_promotion_contract.get("bootstrap_local_env_fallback_removed") is True
            and config_promotion_contract.get("fallback_removal_allowed_after_global_config_promotion") is True
            and config_promotion_contract.get("global_config_allowlist_promoted") is True
            and config_promotion_contract.get("global_config_allowlist_promotion_pending") is False
            and config_promotion_contract.get("frontend_visible") is True
            and config_promotion_contract.get("frontend_editable") is False
            and config_promotion_contract.get("frontend_writeback_allowed") is False
            and config_promotion_contract.get("status_endpoint_writeback_allowed") is False
            and config_promotion_contract.get("status_get_creates_task") is False
            and config_promotion_contract.get("react_render_creates_task") is False
            and config_promotion_contract.get("search_typing_creates_task") is False
            and config_promotion_contract.get("fastapi_startup_creates_task") is False
            and config_promotion_contract.get("provider_model_execution_requires_execution_request") is True
            and config_promotion_contract.get("promotion_contract_is_production_evidence") is False
            and config_promotion_contract.get("production_config_complete") is False
            and config_promotion_contract.get("external_calls_triggered") is False
            and config_promotion_contract.get("tushare_called") is False
            and config_promotion_contract.get("deepseek_called") is False
            and config_promotion_contract.get("github_called") is False
            and config_promotion_contract.get("contains_secret") is False
            and config_promotion_contract.get("credential_values_exposed") is False
            and config_promotion_contract.get("credential_env_key_names_included") is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_config_promotion_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_config_promotion_step_count"
            )
            == 5
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_config_py_update_pending"
            )
            is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_bootstrap_fallback_removal_pending"
            )
            is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_submit_autostart_config_promotion_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_config_promotion_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_config_promotion_step_count"
            )
            == 5
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_config_py_update_pending"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_bootstrap_fallback_removal_pending"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_submit_autostart_config_promotion_is_production_evidence"
            )
            is False,
            f"config_promotion_contract={config_promotion_contract}",
        ),
        _row(
            "search_quant_projection_frontend_wiring_acceptance_contract_keeps_browser_evidence_pending",
            frontend_wiring_contract.get("schema_version")
            == "command_center_search_quant_projection_frontend_wiring_acceptance_contract.v1"
            and frontend_wiring_contract.get("status") == "frontend_wiring_acceptance_pending_backend_ready"
            and frontend_wiring_contract.get("mode") == "live_light"
            and frontend_wiring_contract.get("surface") == "candidate_radar_search_quant_projection"
            and frontend_wiring_contract.get("config_switch") == "COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART"
            and frontend_wiring_contract.get("configured_submit_autostart") is True
            and frontend_wiring_contract.get("effective_submit_autostart") is True
            and frontend_wiring_contract.get("target_frontend_route") == "desktop/src/routes/CandidateRadar.tsx"
            and frontend_wiring_contract.get("target_client_helper") == "postCandidateRadarQuantProjection"
            and frontend_wiring_contract.get("target_task_receipt_component") == "TaskLaunchReceipt"
            and frontend_wiring_contract.get("target_task_status_component") == "TaskStatusPanel"
            and frontend_wiring_contract.get("task_route") == "POST /api/candidate-radar/quant-projection"
            and frontend_wiring_contract.get("task_type") == "run_candidate_radar_quant_projection"
            and frontend_wiring_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and frontend_wiring_contract.get("status_replay_route") == "GET /api/bootstrap/status"
            and frontend_wiring_contract.get("cache_refresh_route") == "GET /api/candidate-radar/cache"
            and frontend_wiring_contract.get("manual_button_path_available") is True
            and frontend_wiring_contract.get("mode_acceptance_row_count") == 4
            and frontend_wiring_contract.get("mode_acceptance_matrix_visible") is True
            and {
                str(_dict(row).get("mode") or "")
                for row in _list(frontend_wiring_contract.get("mode_acceptance_rows"))
            }
            == {"cache_only", "manual", "live_light", "live_full"}
            and all(
                _dict(row).get("typing_creates_task") is False
                and _dict(row).get("render_creates_task") is False
                and _dict(row).get("cache_get_creates_task") is False
                and _dict(row).get("provider_model_execution_allowed") is False
                for row in _list(frontend_wiring_contract.get("mode_acceptance_rows"))
            )
            and _dict(
                {
                    str(_dict(row).get("mode") or ""): _dict(row)
                    for row in _list(frontend_wiring_contract.get("mode_acceptance_rows"))
                }.get("cache_only", {})
            ).get("expected_frontend_behavior")
            == "read_cache_only_no_submit_task"
            and _dict(
                {
                    str(_dict(row).get("mode") or ""): _dict(row)
                    for row in _list(frontend_wiring_contract.get("mode_acceptance_rows"))
                }.get("manual", {})
            ).get("expected_frontend_behavior")
            == "explicit_button_only"
            and _dict(
                {
                    str(_dict(row).get("mode") or ""): _dict(row)
                    for row in _list(frontend_wiring_contract.get("mode_acceptance_rows"))
                }.get("live_light", {})
            ).get("expected_frontend_behavior")
            == "safe_submit_may_create_or_reuse_local_task"
            and _dict(
                {
                    str(_dict(row).get("mode") or ""): _dict(row)
                    for row in _list(frontend_wiring_contract.get("mode_acceptance_rows"))
                }.get("live_light", {})
            ).get("task_creation_surface")
            == "safe_submit_after_bootstrap_status"
            and _dict(
                {
                    str(_dict(row).get("mode") or ""): _dict(row)
                    for row in _list(frontend_wiring_contract.get("mode_acceptance_rows"))
                }.get("live_full", {})
            ).get("expected_frontend_behavior")
            == "reserved_disabled_requires_future_authorization"
            and frontend_wiring_contract.get("active_mode_frontend_submit_autostart_allowed") is True
            and frontend_wiring_contract.get("active_mode_expected_frontend_behavior")
            == "safe_submit_may_create_or_reuse_local_task"
            and frontend_wiring_contract.get("active_mode_task_creation_surface")
            == "safe_submit_after_bootstrap_status"
            and frontend_wiring_contract.get("browser_acceptance_row_count") == 7
            and frontend_wiring_contract.get("browser_acceptance_evidence_required") is True
            and frontend_wiring_contract.get("browser_acceptance_evidence_complete") is False
            and frontend_wiring_contract.get("browser_network_trace_required") is True
            and frontend_wiring_contract.get("browser_viewports_required")
            == ["desktop", "laptop", "tablet", "mobile"]
            and frontend_wiring_contract.get("browser_reduced_motion_check_required") is True
            and frontend_wiring_contract.get("browser_acceptance_can_promote_frontend_wiring") is False
            and {
                str(_dict(row).get("criterion") or "")
                for row in _list(frontend_wiring_contract.get("browser_acceptance_rows"))
            }
            == {
                "initial_cache_render_silent",
                "typing_does_not_create_task",
                "safe_submit_creates_single_local_task",
                "task_status_polling_visible",
                "success_refreshes_research_surfaces",
                "frontend_provider_model_silence",
                "research_only_boundaries_visible",
            }
            and all(
                _dict(row).get("required_before_wiring_done") is True
                for row in _list(frontend_wiring_contract.get("browser_acceptance_rows"))
            )
            and frontend_wiring_contract.get("failure_recovery_row_count") == 7
            and frontend_wiring_contract.get("failure_recovery_evidence_required") is True
            and frontend_wiring_contract.get("failure_recovery_evidence_complete") is False
            and frontend_wiring_contract.get("safe_error_display_required") is True
            and frontend_wiring_contract.get("rate_limit_reuse_visible_required") is True
            and frontend_wiring_contract.get("manual_retry_only_required") is True
            and frontend_wiring_contract.get("last_good_cache_fallback_required") is True
            and frontend_wiring_contract.get("unbounded_task_queue_allowed") is False
            and {
                str(_dict(row).get("criterion") or "")
                for row in _list(frontend_wiring_contract.get("failure_recovery_rows"))
            }
            == {
                "invalid_symbol_safe_block",
                "post_failure_preserves_cache",
                "task_failure_safe_error_visible",
                "rate_limit_reuse_visible",
                "manual_retry_only",
                "stale_cache_fallback_visible",
                "queue_boundaries_visible",
            }
            and all(
                _dict(row).get("required_before_wiring_done") is True
                for row in _list(frontend_wiring_contract.get("failure_recovery_rows"))
            )
            and frontend_wiring_contract.get("frontend_submit_autostart_wiring_implemented") is False
            and frontend_wiring_contract.get("frontend_acceptance_test_implemented") is False
            and frontend_wiring_contract.get("browser_runtime_evidence_complete") is False
            and frontend_wiring_contract.get("live_light_wiring_allowed") is True
            and frontend_wiring_contract.get("manual_mode_requires_explicit_button") is True
            and frontend_wiring_contract.get("cache_only_wiring_disabled") is False
            and frontend_wiring_contract.get("live_full_wiring_reserved_disabled") is False
            and frontend_wiring_contract.get("safe_symbol_required") is True
            and frontend_wiring_contract.get("safe_submit_payload_fields")
            == ["symbol", "include_tushare", "include_deepseek"]
            and frontend_wiring_contract.get("symbol_limit") == 2
            and frontend_wiring_contract.get("rate_limit_seconds") == 600
            and frontend_wiring_contract.get("must_read_bootstrap_status_before_autostart") is True
            and frontend_wiring_contract.get("must_require_live_light_mode") is True
            and frontend_wiring_contract.get("must_require_submit_autostart_config_switch") is True
            and frontend_wiring_contract.get("must_require_submit_autostart_contract_allowed") is True
            and frontend_wiring_contract.get("must_not_create_task_on_typing") is True
            and frontend_wiring_contract.get("must_not_create_task_on_react_initial_render") is True
            and frontend_wiring_contract.get("must_not_create_task_from_get_cache") is True
            and frontend_wiring_contract.get("must_not_call_provider_from_frontend") is True
            and frontend_wiring_contract.get("must_set_task_id_from_post_response") is True
            and frontend_wiring_contract.get("must_render_task_launch_receipt") is True
            and frontend_wiring_contract.get("must_poll_task_status_panel") is True
            and frontend_wiring_contract.get("must_refresh_candidate_cache_on_success") is True
            and frontend_wiring_contract.get("must_refresh_bootstrap_status_after_task") is True
            and frontend_wiring_contract.get("must_show_latest_status_replay") is True
            and frontend_wiring_contract.get("must_show_provider_model_pending") is True
            and frontend_wiring_contract.get("must_show_no_trade_no_action_boundary") is True
            and frontend_wiring_contract.get("provider_model_execution_requires_execution_request") is True
            and frontend_wiring_contract.get("frontend_packet_may_contain_token_key") is False
            and frontend_wiring_contract.get("raw_user_query_logged") is False
            and frontend_wiring_contract.get("raw_user_query_cached") is False
            and frontend_wiring_contract.get("local_receipt_is_production_evidence") is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_acceptance_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_frontend_wiring_status")
            == "frontend_wiring_acceptance_pending_backend_ready"
            and _dict(status.get("live_light")).get("search_quant_projection_frontend_wiring_mode_matrix_visible")
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_frontend_wiring_mode_row_count")
            == 4
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_active_mode_behavior"
            )
            == "safe_submit_may_create_or_reuse_local_task"
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_browser_acceptance_row_count"
            )
            == 7
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_browser_network_trace_required"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_failure_recovery_row_count"
            )
            == 7
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_safe_error_display_required"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_rate_limit_reuse_visible_required"
            )
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_frontend_wiring_implemented")
            is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_browser_evidence_complete"
            )
            is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_failure_recovery_evidence_complete"
            )
            is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_frontend_wiring_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_frontend_wiring_acceptance_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get("search_quant_projection_frontend_wiring_mode_matrix_visible")
            is True
            and _dict(status.get("policy")).get("search_quant_projection_frontend_wiring_active_mode_behavior")
            == "safe_submit_may_create_or_reuse_local_task"
            and _dict(status.get("policy")).get(
                "search_quant_projection_frontend_wiring_browser_acceptance_evidence_required"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_frontend_wiring_browser_network_trace_required"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_frontend_wiring_failure_recovery_evidence_required"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_frontend_wiring_unbounded_task_queue_allowed"
            )
            is False
            and _dict(status.get("policy")).get("search_quant_projection_frontend_wiring_implemented") is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_frontend_wiring_requires_task_status_polling"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_frontend_wiring_browser_evidence_complete"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_frontend_wiring_is_production_evidence"
            )
            is False
            and frontend_wiring_contract.get("provider_execution_implemented") is False
            and frontend_wiring_contract.get("model_execution_implemented") is False
            and frontend_wiring_contract.get("production_quant_projection_complete") is False
            and frontend_wiring_contract.get("external_calls_triggered") is False
            and frontend_wiring_contract.get("tushare_called") is False
            and frontend_wiring_contract.get("deepseek_called") is False
            and frontend_wiring_contract.get("github_called") is False
            and frontend_wiring_contract.get("contains_secret") is False
            and frontend_wiring_contract.get("does_not_execute_trades") is True
            and frontend_wiring_contract.get("does_not_modify_strategy_action") is True,
            f"frontend_wiring_contract={frontend_wiring_contract}",
        ),
        _row(
            "search_quant_projection_unified_startup_handoff_contract_links_submit_to_unified_stage_vocabulary_without_execution",
            unified_handoff_contract.get("schema_version")
            == "command_center_search_quant_projection_unified_startup_handoff_contract.v1"
            and unified_handoff_contract.get("status")
            == "search_quant_unified_startup_handoff_visible_frontend_wiring_pending"
            and unified_handoff_contract.get("mode") == "live_light"
            and unified_handoff_contract.get("surface") == "candidate_radar_search_submit_to_unified_startup"
            and unified_handoff_contract.get("source_route") == "POST /api/candidate-radar/quant-projection"
            and unified_handoff_contract.get("source_task_type") == "run_candidate_radar_quant_projection"
            and unified_handoff_contract.get("target_route") == "POST /api/bootstrap/live-startup"
            and unified_handoff_contract.get("target_task_type") == "command_center_live_bootstrap"
            and unified_handoff_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and unified_handoff_contract.get("handoff_row_count") == 6
            and unified_handoff_contract.get("required_handoff_keys")
            == [
                "bootstrap_status_precheck",
                "safe_symbol_scope_intake",
                "local_projection_receipt",
                "provider_model_stage_mapping",
                "execution_request_boundary",
                "ui_polling_refresh",
            ]
            and set(unified_handoff_rows)
            == {
                "bootstrap_status_precheck",
                "safe_symbol_scope_intake",
                "local_projection_receipt",
                "provider_model_stage_mapping",
                "execution_request_boundary",
                "ui_polling_refresh",
            }
            and [
                unified_handoff_rows.get(key, {}).get("handoff_order")
                for key in [
                    "bootstrap_status_precheck",
                    "safe_symbol_scope_intake",
                    "local_projection_receipt",
                    "provider_model_stage_mapping",
                    "execution_request_boundary",
                    "ui_polling_refresh",
                ]
            ]
            == [1, 2, 3, 4, 5, 6]
            and unified_handoff_rows.get("bootstrap_status_precheck", {}).get("maps_to_unified_stage")
            == "cache_first_status_read"
            and unified_handoff_rows.get("safe_symbol_scope_intake", {}).get("maps_to_unified_stage")
            == "scope_resolution"
            and unified_handoff_rows.get("local_projection_receipt", {}).get("current_runtime")
            == "local_projection_receipt_only"
            and "deepseek_pro_explanation"
            in str(unified_handoff_rows.get("provider_model_stage_mapping", {}).get("maps_to_unified_stage"))
            and unified_handoff_rows.get("execution_request_boundary", {}).get("current_runtime")
            == "provider_model_execution_pending"
            and unified_handoff_rows.get("ui_polling_refresh", {}).get("maps_to_unified_stage")
            == "ui_polling_and_cache_refresh"
            and all(
                _dict(row).get("handoff_contract_only") is True
                and _dict(row).get("handoff_implemented_now") is False
                and _dict(row).get("cache_get_creates_task") is False
                and _dict(row).get("react_render_creates_task") is False
                and _dict(row).get("search_typing_creates_task") is False
                and _dict(row).get("fastapi_startup_creates_task") is False
                and _dict(row).get("search_submit_creates_unified_startup_task_now") is False
                and _dict(row).get("frontend_direct_provider_call_allowed") is False
                and _dict(row).get("provider_or_model_execution_allowed_now") is False
                and _dict(row).get("provider_execution_implemented") is False
                and _dict(row).get("model_execution_implemented") is False
                and _dict(row).get("worker_dispatch_implemented") is False
                and _dict(row).get("call_ledger_required") is True
                and _dict(row).get("model_ledger_required_for_deepseek") is True
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("tushare_called") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("github_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("does_not_execute_trades") is True
                and _dict(row).get("does_not_modify_strategy_action") is True
                and _dict(row).get("does_not_modify_prices_positions_or_operation_zones") is True
                and _dict(row).get("row_is_production_evidence") is False
                for row in unified_handoff_rows.values()
            )
            and unified_handoff_contract.get("linked_search_workflow_schema_version")
            == "command_center_search_quant_projection_workflow_contract.v1"
            and unified_handoff_contract.get("linked_submit_autostart_schema_version")
            == "command_center_search_quant_projection_submit_autostart_contract.v1"
            and unified_handoff_contract.get("linked_frontend_wiring_schema_version")
            == "command_center_search_quant_projection_frontend_wiring_acceptance_contract.v1"
            and unified_handoff_contract.get("linked_unified_startup_schema_version")
            == "command_center_live_light_unified_startup_task_contract.v1"
            and unified_handoff_contract.get("linked_unified_startup_stage_count") == 8
            and unified_handoff_contract.get("search_submit_autostart_allowed") is True
            and unified_handoff_contract.get("frontend_wiring_implemented") is False
            and unified_handoff_contract.get("browser_runtime_evidence_complete") is False
            and unified_handoff_contract.get("unified_stage_vocabulary_shared") is True
            and unified_handoff_contract.get("search_submit_creates_local_projection_task_now") is True
            and unified_handoff_contract.get("search_submit_creates_unified_startup_task_now") is False
            and unified_handoff_contract.get("search_submit_fans_out_provider_model_now") is False
            and unified_handoff_contract.get("future_unified_task_handoff_allowed_after_frontend_acceptance")
            is True
            and unified_handoff_contract.get("future_handoff_requires_execution_request_for_provider_model")
            is True
            and unified_handoff_contract.get("safe_symbol_scope_required") is True
            and unified_handoff_contract.get("cache_first_status_read_required") is True
            and unified_handoff_contract.get("task_status_polling_required") is True
            and unified_handoff_contract.get("candidate_cache_refresh_required_after_success") is True
            and unified_handoff_contract.get("bootstrap_status_refresh_required_after_success") is True
            and unified_handoff_contract.get("cache_get_creates_task") is False
            and unified_handoff_contract.get("react_render_creates_task") is False
            and unified_handoff_contract.get("search_typing_creates_task") is False
            and unified_handoff_contract.get("fastapi_startup_creates_task") is False
            and unified_handoff_contract.get("frontend_direct_provider_call_allowed") is False
            and unified_handoff_contract.get("provider_execution_implemented") is False
            and unified_handoff_contract.get("model_execution_implemented") is False
            and unified_handoff_contract.get("worker_dispatch_implemented") is False
            and unified_handoff_contract.get("deepseek_is_data_source") is False
            and unified_handoff_contract.get("deepseek_may_overwrite_numeric_or_action_fields") is False
            and unified_handoff_contract.get("radar_candidate_is_buy_instruction") is False
            and unified_handoff_contract.get("token_key_exposure_allowed") is False
            and unified_handoff_contract.get("credential_values_exposed") is False
            and unified_handoff_contract.get("credential_env_key_names_included") is False
            and unified_handoff_contract.get("external_calls_triggered") is False
            and unified_handoff_contract.get("tushare_called") is False
            and unified_handoff_contract.get("deepseek_called") is False
            and unified_handoff_contract.get("github_called") is False
            and unified_handoff_contract.get("contains_secret") is False
            and unified_handoff_contract.get("does_not_execute_trades") is True
            and unified_handoff_contract.get("does_not_modify_strategy_action") is True
            and unified_handoff_contract.get("does_not_modify_prices_positions_or_operation_zones") is True
            and unified_handoff_contract.get("handoff_contract_is_execution_evidence") is False
            and unified_handoff_contract.get("handoff_contract_is_production_evidence") is False
            and unified_handoff_contract.get("production_search_unified_handoff_complete") is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_unified_startup_handoff_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_unified_startup_handoff_row_count"
            )
            == 6
            and _dict(status.get("live_light")).get(
                "search_quant_projection_unified_startup_handoff_implemented"
            )
            is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_unified_startup_task_created_now"
            )
            is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_unified_startup_handoff_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_unified_startup_handoff_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_unified_startup_handoff_row_count"
            )
            == 6
            and _dict(status.get("policy")).get(
                "search_quant_projection_unified_startup_handoff_implemented"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_unified_startup_task_created_now"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_unified_startup_handoff_is_production_evidence"
            )
            is False,
            f"unified_handoff_contract={unified_handoff_contract}",
        ),
        _row(
            "search_quant_projection_result_surface_contract_keeps_one_click_research_non_trading",
            result_surface_contract.get("schema_version")
            == "command_center_search_quant_projection_result_surface_contract.v1"
            and result_surface_contract.get("status")
            == "search_quant_projection_result_surface_contract_visible_execution_pending"
            and result_surface_contract.get("mode") == "live_light"
            and result_surface_contract.get("display_action") == "生成 3.0 量化推演"
            and result_surface_contract.get("allowed_modes") == ["manual", "live_light"]
            and result_surface_contract.get("task_route") == "POST /api/candidate-radar/quant-projection"
            and result_surface_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and result_surface_contract.get("provider_model_route")
            == "POST /api/candidate-radar/quant-projection-provider-model-acceptance"
            and result_surface_contract.get("provider_model_route_requires_execution_request") is True
            and result_surface_contract.get("live_light_bootstrap_can_prepare_context") is True
            and result_surface_contract.get("search_input_creates_result_surface") is False
            and result_surface_contract.get("search_typing_creates_task") is False
            and result_surface_contract.get("react_render_creates_result_surface") is False
            and result_surface_contract.get("cache_get_creates_result_surface") is False
            and result_surface_contract.get("explicit_search_action_required") is True
            and result_surface_contract.get("result_surface_count") == 6
            and result_surface_contract.get("required_result_surfaces")
            == [
                "task_progress",
                "data_provenance",
                "freshness_provider_gap",
                "factor_evidence_effects",
                "next_session_echarts_projection",
                "deepseek_status",
            ]
            and {
                "task_progress",
                "data_provenance",
                "freshness_provider_gap",
                "factor_evidence_effects",
                "next_session_echarts_projection",
                "deepseek_status",
            }
            == {
                str(_dict(row).get("surface_key") or "")
                for row in _list(result_surface_contract.get("result_surface_rows"))
            }
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(result_surface_contract.get("result_surface_rows"))
                }.get("factor_evidence_effects", {})
            ).get("research_only")
            is True
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(result_surface_contract.get("result_surface_rows"))
                }.get("next_session_echarts_projection", {})
            ).get("operation_zone_action_mode_required")
            == "condition_only"
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(result_surface_contract.get("result_surface_rows"))
                }.get("deepseek_status", {})
            ).get("source")
            == "search_quant_projection_deepseek_output_acceptance_contract"
            and _dict(
                {
                    str(_dict(row).get("surface_key") or ""): _dict(row)
                    for row in _list(result_surface_contract.get("result_surface_rows"))
                }.get("deepseek_status", {})
            ).get("model_correctness_evidence")
            is False
            and result_surface_contract.get("task_progress_visible_required") is True
            and result_surface_contract.get("data_provenance_visible_required") is True
            and result_surface_contract.get("freshness_state_visible_required") is True
            and result_surface_contract.get("provider_gap_visible_required") is True
            and result_surface_contract.get("factor_support_suppress_neutral_missing_required") is True
            and result_surface_contract.get("next_session_echarts_payload_required") is True
            and result_surface_contract.get("deepseek_status_visible_required") is True
            and result_surface_contract.get("call_ledger_safe_summary_visible_required") is True
            and result_surface_contract.get("model_ledger_safe_summary_visible_when_deepseek_used") is True
            and result_surface_contract.get("raw_prompt_or_raw_model_output_visible_allowed") is False
            and result_surface_contract.get("token_key_exposure_allowed") is False
            and result_surface_contract.get("radar_candidate_is_buy_instruction") is False
            and result_surface_contract.get("factor_score_is_buy_instruction") is False
            and result_surface_contract.get("deepseek_text_is_buy_instruction") is False
            and result_surface_contract.get("trade_instruction_allowed") is False
            and result_surface_contract.get("may_overwrite_price") is False
            and result_surface_contract.get("may_overwrite_holding") is False
            and result_surface_contract.get("may_overwrite_factor") is False
            and result_surface_contract.get("may_overwrite_operation_zones") is False
            and result_surface_contract.get("may_modify_strategy_action") is False
            and _dict(status.get("live_light")).get("search_quant_projection_result_surface_contract_visible")
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_result_surface_count") == 6
            and _dict(status.get("live_light")).get("search_quant_projection_result_surfaces_research_only")
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_result_surface_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("search_quant_projection_result_surface_contract_visible")
            is True
            and _dict(status.get("policy")).get("search_quant_projection_result_surfaces_research_only")
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_result_surface_trade_instruction_allowed"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_result_surface_contract_is_production_evidence"
            )
            is False
            and result_surface_contract.get("provider_execution_implemented") is False
            and result_surface_contract.get("model_execution_implemented") is False
            and result_surface_contract.get("result_surface_contract_is_provider_execution_evidence")
            is False
            and result_surface_contract.get("result_surface_contract_is_model_correctness_evidence")
            is False
            and result_surface_contract.get("result_surface_contract_is_production_evidence") is False
            and result_surface_contract.get("external_calls_triggered") is False
            and result_surface_contract.get("tushare_called") is False
            and result_surface_contract.get("deepseek_called") is False
            and result_surface_contract.get("github_called") is False
            and result_surface_contract.get("contains_secret") is False
            and result_surface_contract.get("does_not_execute_trades") is True
            and result_surface_contract.get("does_not_modify_strategy_action") is True,
            f"result_surface_contract={result_surface_contract}",
        ),
        _row(
            "search_quant_projection_factor_next_handoff_contract_maps_search_receipt_to_cache_lineage_without_execution",
            factor_next_handoff_contract.get("schema_version")
            == "command_center_search_quant_projection_factor_next_handoff_contract.v1"
            and factor_next_handoff_contract.get("status")
            == "search_quant_factor_next_handoff_visible_cache_write_pending"
            and factor_next_handoff_contract.get("mode") == "live_light"
            and factor_next_handoff_contract.get("display_action") == "生成 3.0 量化推演"
            and factor_next_handoff_contract.get("allowed_modes") == ["manual", "live_light"]
            and factor_next_handoff_contract.get("task_route") == "POST /api/candidate-radar/quant-projection"
            and factor_next_handoff_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and factor_next_handoff_contract.get("future_factor_route") == "POST /api/factor-quant/run-light"
            and factor_next_handoff_contract.get("future_next_session_route") == "POST /api/next-session/generate"
            and factor_next_handoff_contract.get("future_task_types")
            == ["run_factor_light", "build_next_session_projection"]
            and factor_next_handoff_contract.get("output_packet_keys")
            == ["command_center_factor_quant_hub_packet", "command_center_next_session_projection_packet"]
            and factor_next_handoff_contract.get("input_packet_keys")
            == [
                "command_center_candidate_radar_quant_projection_receipt",
                "command_center_factor_quant_hub_packet",
                "command_center_next_session_projection_packet",
            ]
            and factor_next_handoff_contract.get("handoff_row_count") == 6
            and factor_next_handoff_contract.get("ready_now_row_count") == 0
            and factor_next_handoff_contract.get("executed_handoff_row_count") == 0
            and factor_next_handoff_contract.get("output_written_row_count") == 0
            and factor_next_handoff_contract.get("required_handoff_keys")
            == [
                "safe_symbol_scope_bound",
                "local_projection_receipt_ready",
                "provider_fact_ledger_or_gap_ready",
                "factor_light_runtime_pending",
                "factor_quant_hub_cache_lineage_pending",
                "next_session_cache_lineage_pending",
            ]
            and set(factor_next_handoff_rows)
            == {
                "safe_symbol_scope_bound",
                "local_projection_receipt_ready",
                "provider_fact_ledger_or_gap_ready",
                "factor_light_runtime_pending",
                "factor_quant_hub_cache_lineage_pending",
                "next_session_cache_lineage_pending",
            }
            and _dict(factor_next_handoff_rows.get("provider_fact_ledger_or_gap_ready")).get("source_contract")
            == "tushare_light_strategy_contract"
            and _dict(factor_next_handoff_rows.get("factor_light_runtime_pending")).get("future_local_route")
            == "POST /api/factor-quant/run-light"
            and _dict(factor_next_handoff_rows.get("factor_light_runtime_pending")).get("future_task_type")
            == "run_factor_light"
            and _dict(factor_next_handoff_rows.get("factor_quant_hub_cache_lineage_pending")).get(
                "output_packet_key"
            )
            == "command_center_factor_quant_hub_packet"
            and _dict(factor_next_handoff_rows.get("next_session_cache_lineage_pending")).get("future_local_route")
            == "POST /api/next-session/generate"
            and _dict(factor_next_handoff_rows.get("next_session_cache_lineage_pending")).get(
                "future_task_type"
            )
            == "build_next_session_projection"
            and _dict(factor_next_handoff_rows.get("next_session_cache_lineage_pending")).get(
                "output_packet_key"
            )
            == "command_center_next_session_projection_packet"
            and factor_next_handoff_contract.get("live_light_bootstrap_can_prepare_context") is True
            and factor_next_handoff_contract.get("requires_safe_symbol_scope") is True
            and factor_next_handoff_contract.get("requires_local_projection_receipt") is True
            and factor_next_handoff_contract.get("requires_call_ledger_or_provider_gap") is True
            and factor_next_handoff_contract.get("requires_factor_light_cache_lineage") is True
            and factor_next_handoff_contract.get("requires_next_session_cache_lineage") is True
            and factor_next_handoff_contract.get("requires_stale_cache_label") is True
            and factor_next_handoff_contract.get("requires_safe_error_when_missing_cache") is True
            and factor_next_handoff_contract.get("feeds_deepseek_readiness_contract") is True
            and factor_next_handoff_contract.get("deepseek_may_run_before_factor_next_ready") is False
            and factor_next_handoff_contract.get("search_input_creates_handoff") is False
            and factor_next_handoff_contract.get("search_typing_creates_task") is False
            and factor_next_handoff_contract.get("react_render_executes_factor_next") is False
            and factor_next_handoff_contract.get("cache_get_executes_factor_next") is False
            and factor_next_handoff_contract.get("fastapi_startup_executes_factor_next") is False
            and factor_next_handoff_contract.get("current_search_submit_executes_factor_next_now") is False
            and factor_next_handoff_contract.get("current_search_submit_writes_factor_next_cache_now") is False
            and factor_next_handoff_contract.get("local_compute_execution_implemented") is False
            and factor_next_handoff_contract.get("cache_write_implemented") is False
            and all(_dict(row).get("handoff_contract_only") is True for row in factor_next_handoff_rows.values())
            and all(_dict(row).get("ready_now") is False for row in factor_next_handoff_rows.values())
            and all(
                _dict(row).get("local_compute_execution_implemented") is False
                for row in factor_next_handoff_rows.values()
            )
            and all(_dict(row).get("cache_write_implemented") is False for row in factor_next_handoff_rows.values())
            and all(_dict(row).get("output_written_now") is False for row in factor_next_handoff_rows.values())
            and all(
                _dict(row).get("cache_get_may_execute_local_compute") is False
                for row in factor_next_handoff_rows.values()
            )
            and all(
                _dict(row).get("react_render_may_execute_local_compute") is False
                for row in factor_next_handoff_rows.values()
            )
            and all(
                _dict(row).get("search_typing_may_execute_local_compute") is False
                for row in factor_next_handoff_rows.values()
            )
            and all(
                _dict(row).get("fastapi_startup_may_execute_local_compute") is False
                for row in factor_next_handoff_rows.values()
            )
            and all(_dict(row).get("call_ledger_required") is True for row in factor_next_handoff_rows.values())
            and all(_dict(row).get("cache_lineage_required") is True for row in factor_next_handoff_rows.values())
            and all(
                _dict(row).get("provider_gap_visible_required") is True
                for row in factor_next_handoff_rows.values()
            )
            and all(_dict(row).get("row_is_production_evidence") is False for row in factor_next_handoff_rows.values())
            and _dict(status.get("live_light")).get(
                "search_quant_projection_factor_next_handoff_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_factor_next_handoff_row_count") == 6
            and _dict(status.get("live_light")).get(
                "search_quant_projection_factor_next_handoff_ready_now_row_count"
            )
            == 0
            and _dict(status.get("live_light")).get(
                "search_quant_projection_factor_next_handoff_output_written_row_count"
            )
            == 0
            and _dict(status.get("live_light")).get(
                "search_quant_projection_factor_next_handoff_feeds_deepseek_readiness"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_factor_next_executes_local_compute_now"
            )
            is False
            and _dict(status.get("live_light")).get("search_quant_projection_factor_next_writes_cache_now")
            is False
            and _dict(status.get("policy")).get("search_quant_projection_factor_next_handoff_contract_visible")
            is True
            and _dict(status.get("policy")).get("search_quant_projection_factor_next_handoff_row_count") == 6
            and _dict(status.get("policy")).get(
                "search_quant_projection_factor_next_handoff_requires_call_ledger_or_gap"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_factor_next_handoff_requires_cache_lineage"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_factor_next_handoff_feeds_deepseek_readiness"
            )
            is True
            and _dict(status.get("policy")).get("search_quant_projection_factor_next_executes_local_compute_now")
            is False
            and _dict(status.get("policy")).get("search_quant_projection_factor_next_writes_cache_now") is False
            and factor_next_handoff_contract.get("provider_execution_implemented") is False
            and factor_next_handoff_contract.get("model_execution_implemented") is False
            and factor_next_handoff_contract.get("handoff_contract_is_provider_execution_evidence") is False
            and factor_next_handoff_contract.get("handoff_contract_is_model_correctness_evidence") is False
            and factor_next_handoff_contract.get("handoff_contract_is_production_evidence") is False
            and factor_next_handoff_contract.get("token_key_exposure_allowed") is False
            and factor_next_handoff_contract.get("external_calls_triggered") is False
            and factor_next_handoff_contract.get("tushare_called") is False
            and factor_next_handoff_contract.get("deepseek_called") is False
            and factor_next_handoff_contract.get("github_called") is False
            and factor_next_handoff_contract.get("contains_secret") is False
            and factor_next_handoff_contract.get("does_not_execute_trades") is True
            and factor_next_handoff_contract.get("does_not_modify_strategy_action") is True
            and factor_next_handoff_contract.get("does_not_modify_prices_positions_or_operation_zones") is True,
            f"factor_next_handoff_contract={factor_next_handoff_contract}",
        ),
        _row(
            "search_quant_projection_cache_write_preflight_contract_blocks_writes_until_lineage_and_no_overwrite_guards",
            cache_write_preflight_contract.get("schema_version")
            == "command_center_search_quant_projection_cache_write_preflight_contract.v1"
            and cache_write_preflight_contract.get("status")
            == "search_quant_cache_write_preflight_visible_write_pending"
            and cache_write_preflight_contract.get("mode") == "live_light"
            and cache_write_preflight_contract.get("display_action") == "生成 3.0 量化推演"
            and cache_write_preflight_contract.get("allowed_modes") == ["manual", "live_light"]
            and cache_write_preflight_contract.get("task_route") == "POST /api/candidate-radar/quant-projection"
            and cache_write_preflight_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and cache_write_preflight_contract.get("future_factor_route") == "POST /api/factor-quant/run-light"
            and cache_write_preflight_contract.get("future_next_session_route") == "POST /api/next-session/generate"
            and cache_write_preflight_contract.get("target_cache_keys")
            == ["factor_quant_hub_cache", "next_session_projection_cache"]
            and cache_write_preflight_contract.get("output_packet_keys")
            == ["command_center_factor_quant_hub_packet", "command_center_next_session_projection_packet"]
            and cache_write_preflight_contract.get("preflight_row_count") == 7
            and cache_write_preflight_contract.get("ready_now_row_count") == 0
            and cache_write_preflight_contract.get("cache_written_row_count") == 0
            and cache_write_preflight_contract.get("lineage_written_row_count") == 0
            and cache_write_preflight_contract.get("required_preflight_keys")
            == [
                "scope_hash_matches_projection_receipt",
                "provider_ledger_or_gap_bound",
                "factor_next_handoff_rows_bound",
                "lineage_fields_complete",
                "stale_cache_and_safe_error_policy_bound",
                "deepseek_cache_dependency_blocked_until_factor_next_written",
                "no_price_position_factor_action_overwrite_guard",
            ]
            and set(cache_write_preflight_rows)
            == {
                "scope_hash_matches_projection_receipt",
                "provider_ledger_or_gap_bound",
                "factor_next_handoff_rows_bound",
                "lineage_fields_complete",
                "stale_cache_and_safe_error_policy_bound",
                "deepseek_cache_dependency_blocked_until_factor_next_written",
                "no_price_position_factor_action_overwrite_guard",
            }
            and cache_write_preflight_contract.get("linked_factor_next_handoff_schema_version")
            == "command_center_search_quant_projection_factor_next_handoff_contract.v1"
            and cache_write_preflight_contract.get("linked_factor_next_handoff_row_count") == 6
            and _dict(cache_write_preflight_rows.get("factor_next_handoff_rows_bound")).get("source_contract")
            == "search_quant_projection_factor_next_handoff_contract"
            and _dict(cache_write_preflight_rows.get("lineage_fields_complete")).get("source_contract")
            == "live_light_cache_lineage_contract"
            and "scope_hash"
            in _list(_dict(cache_write_preflight_rows.get("scope_hash_matches_projection_receipt")).get("required_fields"))
            and "storage_backend"
            in _list(_dict(cache_write_preflight_rows.get("lineage_fields_complete")).get("required_fields"))
            and "stale_cache_label"
            in _list(
                _dict(cache_write_preflight_rows.get("stale_cache_and_safe_error_policy_bound")).get(
                    "required_fields"
                )
            )
            and "target_fields_allowlist"
            in _list(
                _dict(cache_write_preflight_rows.get("no_price_position_factor_action_overwrite_guard")).get(
                    "required_fields"
                )
            )
            and cache_write_preflight_contract.get("live_light_bootstrap_can_prepare_context") is True
            and cache_write_preflight_contract.get("requires_scope_hash_match") is True
            and cache_write_preflight_contract.get("requires_provider_call_ledger_or_gap") is True
            and cache_write_preflight_contract.get("requires_factor_next_handoff") is True
            and cache_write_preflight_contract.get("requires_cache_lineage") is True
            and cache_write_preflight_contract.get("requires_storage_backend") is True
            and cache_write_preflight_contract.get("requires_freshness_state") is True
            and cache_write_preflight_contract.get("requires_stale_cache_label") is True
            and cache_write_preflight_contract.get("requires_safe_error_when_missing_cache") is True
            and cache_write_preflight_contract.get("requires_no_overwrite_guard") is True
            and cache_write_preflight_contract.get("feeds_deepseek_readiness_contract") is True
            and cache_write_preflight_contract.get(
                "deepseek_cache_write_blocked_until_factor_next_cache_lineage"
            )
            is True
            and cache_write_preflight_contract.get("cache_get_may_write_cache") is False
            and cache_write_preflight_contract.get("react_render_may_write_cache") is False
            and cache_write_preflight_contract.get("search_typing_may_write_cache") is False
            and cache_write_preflight_contract.get("fastapi_startup_may_write_cache") is False
            and cache_write_preflight_contract.get("current_search_submit_writes_factor_next_cache_now")
            is False
            and cache_write_preflight_contract.get("current_search_submit_writes_deepseek_cache_now")
            is False
            and cache_write_preflight_contract.get("cache_write_allowed_now") is False
            and cache_write_preflight_contract.get("cache_write_implemented") is False
            and cache_write_preflight_contract.get("local_compute_execution_implemented") is False
            and all(
                _dict(row).get("preflight_contract_only") is True
                and _dict(row).get("ready_now") is False
                and _dict(row).get("cache_write_allowed_now") is False
                and _dict(row).get("cache_write_implemented") is False
                and _dict(row).get("cache_written_now") is False
                and _dict(row).get("lineage_written_now") is False
                and _dict(row).get("post_task_or_worker_required_for_write") is True
                and _dict(row).get("call_ledger_required") is True
                and _dict(row).get("cache_lineage_required") is True
                and _dict(row).get("provider_gap_visible_required") is True
                and _dict(row).get("safe_error_required") is True
                and _dict(row).get("stale_cache_label_required") is True
                and _dict(row).get("row_is_production_evidence") is False
                for row in cache_write_preflight_rows.values()
            )
            and _dict(status.get("live_light")).get(
                "search_quant_projection_cache_write_preflight_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_cache_write_preflight_row_count")
            == 7
            and _dict(status.get("live_light")).get(
                "search_quant_projection_cache_write_preflight_ready_now_row_count"
            )
            == 0
            and _dict(status.get("live_light")).get(
                "search_quant_projection_cache_write_preflight_cache_written_row_count"
            )
            == 0
            and _dict(status.get("live_light")).get(
                "search_quant_projection_cache_write_preflight_feeds_deepseek_readiness"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_cache_write_preflight_writes_cache_now"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_cache_write_preflight_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get("search_quant_projection_cache_write_preflight_row_count") == 7
            and _dict(status.get("policy")).get(
                "search_quant_projection_cache_write_preflight_requires_scope_hash_match"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_cache_write_preflight_requires_cache_lineage"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_cache_write_preflight_requires_no_overwrite_guard"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_cache_write_preflight_feeds_deepseek_readiness"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_cache_write_preflight_writes_cache_now"
            )
            is False
            and cache_write_preflight_contract.get("may_overwrite_price") is False
            and cache_write_preflight_contract.get("may_overwrite_holding") is False
            and cache_write_preflight_contract.get("may_overwrite_factor") is False
            and cache_write_preflight_contract.get("may_overwrite_operation_zones") is False
            and cache_write_preflight_contract.get("may_modify_strategy_action") is False
            and cache_write_preflight_contract.get("preflight_contract_is_provider_execution_evidence")
            is False
            and cache_write_preflight_contract.get("preflight_contract_is_model_correctness_evidence")
            is False
            and cache_write_preflight_contract.get("preflight_contract_is_production_evidence") is False
            and cache_write_preflight_contract.get("token_key_exposure_allowed") is False
            and cache_write_preflight_contract.get("external_calls_triggered") is False
            and cache_write_preflight_contract.get("tushare_called") is False
            and cache_write_preflight_contract.get("deepseek_called") is False
            and cache_write_preflight_contract.get("github_called") is False
            and cache_write_preflight_contract.get("contains_secret") is False
            and cache_write_preflight_contract.get("does_not_execute_trades") is True
            and cache_write_preflight_contract.get("does_not_modify_strategy_action") is True
            and cache_write_preflight_contract.get("does_not_modify_prices_positions_or_operation_zones")
            is True,
            f"cache_write_preflight_contract={cache_write_preflight_contract}",
        ),
        _row(
            "search_quant_projection_deepseek_model_preflight_contract_blocks_model_until_cache_lineage_and_ledger_ready",
            deepseek_model_preflight_contract.get("schema_version")
            == "command_center_search_quant_projection_deepseek_model_preflight_contract.v1"
            and deepseek_model_preflight_contract.get("status")
            == "search_quant_deepseek_model_preflight_visible_model_call_pending"
            and deepseek_model_preflight_contract.get("mode") == "live_light"
            and deepseek_model_preflight_contract.get("display_action") == "生成 3.0 量化推演"
            and deepseek_model_preflight_contract.get("allowed_modes") == ["manual", "live_light"]
            and deepseek_model_preflight_contract.get("task_route") == "POST /api/candidate-radar/quant-projection"
            and deepseek_model_preflight_contract.get("provider_model_route")
            == "POST /api/candidate-radar/quant-projection-provider-model-acceptance"
            and deepseek_model_preflight_contract.get("provider_model_route_requires_execution_request") is True
            and deepseek_model_preflight_contract.get("deepseek_configured_for_live_light") is True
            and deepseek_model_preflight_contract.get("deepseek_model_label") == "contract-live-pro"
            and deepseek_model_preflight_contract.get("linked_cache_write_preflight_schema_version")
            == "command_center_search_quant_projection_cache_write_preflight_contract.v1"
            and deepseek_model_preflight_contract.get("linked_cache_write_preflight_row_count") == 7
            and deepseek_model_preflight_contract.get("preflight_row_count") == 7
            and deepseek_model_preflight_contract.get("ready_now_row_count") == 0
            and deepseek_model_preflight_contract.get("model_called_row_count") == 0
            and deepseek_model_preflight_contract.get("model_cache_written_row_count") == 0
            and deepseek_model_preflight_contract.get("model_ledger_written_row_count") == 0
            and deepseek_model_preflight_contract.get("required_preflight_keys")
            == [
                "factor_next_cache_lineage_ready",
                "model_input_packet_whitelist_bound",
                "prompt_redaction_boundary_bound",
                "model_ledger_fields_bound",
                "output_schema_whitelist_bound",
                "model_cache_lineage_policy_bound",
                "execution_request_and_rate_limit_bound",
            ]
            and set(deepseek_model_preflight_rows)
            == {
                "factor_next_cache_lineage_ready",
                "model_input_packet_whitelist_bound",
                "prompt_redaction_boundary_bound",
                "model_ledger_fields_bound",
                "output_schema_whitelist_bound",
                "model_cache_lineage_policy_bound",
                "execution_request_and_rate_limit_bound",
            }
            and _dict(deepseek_model_preflight_rows.get("factor_next_cache_lineage_ready")).get(
                "source_contract"
            )
            == "search_quant_projection_cache_write_preflight_contract"
            and _dict(deepseek_model_preflight_rows.get("prompt_redaction_boundary_bound")).get(
                "source_contract"
            )
            == "live_light_ledger_redaction_invariant_contract"
            and _dict(deepseek_model_preflight_rows.get("model_ledger_fields_bound")).get("source_contract")
            == "deepseek_pro_strategy_contract"
            and _dict(deepseek_model_preflight_rows.get("execution_request_and_rate_limit_bound")).get(
                "source_contract"
            )
            == "live_light_execution_request_handoff_contract"
            and "input_hash"
            in _list(_dict(deepseek_model_preflight_rows.get("model_ledger_fields_bound")).get("required_fields"))
            and "summary"
            in _list(
                _dict(deepseek_model_preflight_rows.get("output_schema_whitelist_bound")).get("required_fields")
            )
            and "rate_limit_seconds"
            in _list(
                _dict(deepseek_model_preflight_rows.get("execution_request_and_rate_limit_bound")).get(
                    "required_fields"
                )
            )
            and deepseek_model_preflight_contract.get("required_input_packet_keys")
            == ["command_center_factor_quant_hub_packet", "command_center_next_session_projection_packet"]
            and deepseek_model_preflight_contract.get("allowed_output_fields")
            == [
                "summary",
                "support_notes",
                "suppress_notes",
                "conflict_notes",
                "missing_data_notes",
                "discipline_notes",
            ]
            and deepseek_model_preflight_contract.get("allowed_output_field_count") == 6
            and deepseek_model_preflight_contract.get("required_model_ledger_fields")
            == [
                "model_used",
                "purpose",
                "token_usage",
                "parse_status",
                "cache_status",
                "sanitizer_status",
                "input_hash",
                "output_hash",
            ]
            and deepseek_model_preflight_contract.get("requires_cache_write_preflight") is True
            and deepseek_model_preflight_contract.get("requires_factor_next_cache_lineage") is True
            and deepseek_model_preflight_contract.get("requires_model_input_whitelist") is True
            and deepseek_model_preflight_contract.get("requires_prompt_redaction_boundary") is True
            and deepseek_model_preflight_contract.get("requires_model_ledger") is True
            and deepseek_model_preflight_contract.get("requires_output_schema_whitelist") is True
            and deepseek_model_preflight_contract.get("requires_model_cache_lineage") is True
            and deepseek_model_preflight_contract.get("requires_execution_request_and_rate_limit") is True
            and deepseek_model_preflight_contract.get("safe_skip_allowed_when_preflight_missing") is True
            and deepseek_model_preflight_contract.get("cache_get_may_call_deepseek") is False
            and deepseek_model_preflight_contract.get("react_render_may_call_deepseek") is False
            and deepseek_model_preflight_contract.get("search_typing_may_call_deepseek") is False
            and deepseek_model_preflight_contract.get("fastapi_startup_may_call_deepseek") is False
            and deepseek_model_preflight_contract.get("search_submit_may_call_deepseek_now") is False
            and deepseek_model_preflight_contract.get("current_submit_autostart_calls_model") is False
            and deepseek_model_preflight_contract.get("model_call_allowed_now") is False
            and deepseek_model_preflight_contract.get("model_execution_implemented") is False
            and deepseek_model_preflight_contract.get("deepseek_called") is False
            and deepseek_model_preflight_contract.get("model_cache_write_implemented") is False
            and deepseek_model_preflight_contract.get("model_ledger_write_implemented") is False
            and all(
                _dict(row).get("preflight_contract_only") is True
                and _dict(row).get("ready_now") is False
                and _dict(row).get("model_call_allowed_now") is False
                and _dict(row).get("model_execution_implemented") is False
                and _dict(row).get("model_called_now") is False
                and _dict(row).get("model_cache_written_now") is False
                and _dict(row).get("model_ledger_written_now") is False
                and _dict(row).get("cache_get_may_call_deepseek") is False
                and _dict(row).get("react_render_may_call_deepseek") is False
                and _dict(row).get("search_typing_may_call_deepseek") is False
                and _dict(row).get("fastapi_startup_may_call_deepseek") is False
                and _dict(row).get("search_submit_may_call_deepseek_now") is False
                and _dict(row).get("provider_model_execution_requires_execution_request") is True
                and _dict(row).get("model_ledger_required") is True
                and _dict(row).get("raw_prompt_visible_allowed") is False
                and _dict(row).get("raw_model_output_visible_allowed") is False
                and _dict(row).get("token_key_exposure_allowed") is False
                and _dict(row).get("deepseek_is_data_source") is False
                and _dict(row).get("deepseek_may_overwrite_numeric_or_action_fields") is False
                and _dict(row).get("row_is_model_correctness_evidence") is False
                and _dict(row).get("row_is_production_evidence") is False
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("contains_secret") is False
                for row in deepseek_model_preflight_rows.values()
            )
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_model_preflight_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_deepseek_model_preflight_row_count")
            == 7
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_model_preflight_ready_now_row_count"
            )
            == 0
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_model_preflight_model_called_row_count"
            )
            == 0
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_model_preflight_allowed_output_field_count"
            )
            == 6
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_model_preflight_requires_model_ledger"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_model_preflight_calls_model_now"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_model_preflight_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get("search_quant_projection_deepseek_model_preflight_row_count")
            == 7
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_model_preflight_requires_cache_write_preflight"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_model_preflight_requires_model_ledger"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_model_preflight_raw_prompt_or_output_visible_allowed"
            )
            is False
            and _dict(status.get("policy")).get("search_quant_projection_deepseek_model_preflight_calls_model_now")
            is False
            and deepseek_model_preflight_contract.get("raw_prompt_visible_allowed") is False
            and deepseek_model_preflight_contract.get("raw_model_output_visible_allowed") is False
            and deepseek_model_preflight_contract.get("token_key_exposure_allowed") is False
            and deepseek_model_preflight_contract.get("deepseek_is_data_source") is False
            and deepseek_model_preflight_contract.get("may_overwrite_price") is False
            and deepseek_model_preflight_contract.get("may_overwrite_holding") is False
            and deepseek_model_preflight_contract.get("may_overwrite_factor") is False
            and deepseek_model_preflight_contract.get("may_overwrite_operation_zones") is False
            and deepseek_model_preflight_contract.get("may_modify_strategy_action") is False
            and deepseek_model_preflight_contract.get("preflight_contract_is_model_correctness_evidence")
            is False
            and deepseek_model_preflight_contract.get("preflight_contract_is_production_evidence") is False
            and deepseek_model_preflight_contract.get("external_calls_triggered") is False
            and deepseek_model_preflight_contract.get("tushare_called") is False
            and deepseek_model_preflight_contract.get("github_called") is False
            and deepseek_model_preflight_contract.get("contains_secret") is False
            and deepseek_model_preflight_contract.get("does_not_execute_trades") is True
            and deepseek_model_preflight_contract.get("does_not_modify_strategy_action") is True
            and deepseek_model_preflight_contract.get("does_not_modify_prices_positions_or_operation_zones")
            is True,
            f"deepseek_model_preflight_contract={deepseek_model_preflight_contract}",
        ),
        _row(
            "search_quant_projection_deepseek_output_acceptance_contract_blocks_display_and_cache_until_parse_sanitize_lineage",
            deepseek_output_acceptance_contract.get("schema_version")
            == "command_center_search_quant_projection_deepseek_output_acceptance_contract.v1"
            and deepseek_output_acceptance_contract.get("status")
            == "search_quant_deepseek_output_acceptance_visible_output_pending"
            and deepseek_output_acceptance_contract.get("mode") == "live_light"
            and deepseek_output_acceptance_contract.get("display_action") == "生成 3.0 量化推演"
            and deepseek_output_acceptance_contract.get("allowed_modes") == ["manual", "live_light"]
            and deepseek_output_acceptance_contract.get("task_route")
            == "POST /api/candidate-radar/quant-projection"
            and deepseek_output_acceptance_contract.get("provider_model_route")
            == "POST /api/candidate-radar/quant-projection-provider-model-acceptance"
            and deepseek_output_acceptance_contract.get("provider_model_route_requires_execution_request") is True
            and deepseek_output_acceptance_contract.get("deepseek_configured_for_live_light") is True
            and deepseek_output_acceptance_contract.get("deepseek_model_label") == "contract-live-pro"
            and deepseek_output_acceptance_contract.get("linked_model_preflight_schema_version")
            == "command_center_search_quant_projection_deepseek_model_preflight_contract.v1"
            and deepseek_output_acceptance_contract.get("linked_model_preflight_row_count") == 7
            and deepseek_output_acceptance_contract.get("acceptance_row_count") == 7
            and deepseek_output_acceptance_contract.get("ready_now_row_count") == 0
            and deepseek_output_acceptance_contract.get("output_accepted_row_count") == 0
            and deepseek_output_acceptance_contract.get("model_cache_written_row_count") == 0
            and deepseek_output_acceptance_contract.get("model_ledger_written_row_count") == 0
            and deepseek_output_acceptance_contract.get("required_acceptance_keys")
            == [
                "model_ledger_evidence_bound",
                "parse_status_gate_bound",
                "sanitizer_status_gate_bound",
                "output_schema_whitelist_enforced",
                "safe_summary_surface_bound",
                "model_cache_lineage_bound",
                "no_numeric_or_action_overwrite_bound",
            ]
            and set(deepseek_output_acceptance_rows)
            == {
                "model_ledger_evidence_bound",
                "parse_status_gate_bound",
                "sanitizer_status_gate_bound",
                "output_schema_whitelist_enforced",
                "safe_summary_surface_bound",
                "model_cache_lineage_bound",
                "no_numeric_or_action_overwrite_bound",
            }
            and deepseek_output_acceptance_contract.get("accepted_output_fields")
            == [
                "summary",
                "support_notes",
                "suppress_notes",
                "conflict_notes",
                "missing_data_notes",
                "discipline_notes",
            ]
            and deepseek_output_acceptance_contract.get("accepted_output_field_count") == 6
            and deepseek_output_acceptance_contract.get("safe_surface_fields")
            == ["status", "model_label", "parse_status", "safe_summary", "safe_error"]
            and deepseek_output_acceptance_contract.get("requires_model_preflight") is True
            and deepseek_output_acceptance_contract.get("requires_model_ledger_evidence") is True
            and deepseek_output_acceptance_contract.get("requires_parse_status_passed") is True
            and deepseek_output_acceptance_contract.get("requires_sanitizer_status_passed") is True
            and deepseek_output_acceptance_contract.get("requires_output_schema_whitelist") is True
            and deepseek_output_acceptance_contract.get("requires_safe_summary_surface") is True
            and deepseek_output_acceptance_contract.get("requires_model_cache_lineage") is True
            and deepseek_output_acceptance_contract.get("requires_no_numeric_or_action_overwrite") is True
            and deepseek_output_acceptance_contract.get("safe_skip_allowed_when_parse_or_sanitizer_fails") is True
            and _dict(deepseek_output_acceptance_rows.get("model_ledger_evidence_bound")).get("source_contract")
            == "search_quant_projection_deepseek_model_preflight_contract"
            and _dict(deepseek_output_acceptance_rows.get("sanitizer_status_gate_bound")).get("source_contract")
            == "live_light_ledger_redaction_invariant_contract"
            and _dict(deepseek_output_acceptance_rows.get("safe_summary_surface_bound")).get("source_contract")
            == "search_quant_projection_result_surface_contract"
            and _dict(deepseek_output_acceptance_rows.get("model_cache_lineage_bound")).get("source_contract")
            == "live_light_cache_lineage_contract"
            and "safe_summary"
            in _list(_dict(deepseek_output_acceptance_rows.get("safe_summary_surface_bound")).get("required_fields"))
            and "summary"
            in _list(
                _dict(deepseek_output_acceptance_rows.get("output_schema_whitelist_enforced")).get(
                    "required_fields"
                )
            )
            and "trade_instruction_allowed"
            in _list(
                _dict(deepseek_output_acceptance_rows.get("no_numeric_or_action_overwrite_bound")).get(
                    "required_fields"
                )
            )
            and deepseek_output_acceptance_contract.get("cache_get_may_accept_model_output") is False
            and deepseek_output_acceptance_contract.get("react_render_may_accept_model_output") is False
            and deepseek_output_acceptance_contract.get("search_typing_may_accept_model_output") is False
            and deepseek_output_acceptance_contract.get("fastapi_startup_may_accept_model_output") is False
            and deepseek_output_acceptance_contract.get("search_submit_may_accept_model_output_now") is False
            and deepseek_output_acceptance_contract.get("model_output_acceptance_implemented") is False
            and deepseek_output_acceptance_contract.get("model_cache_write_implemented") is False
            and deepseek_output_acceptance_contract.get("model_ledger_write_implemented") is False
            and deepseek_output_acceptance_contract.get("model_execution_implemented") is False
            and deepseek_output_acceptance_contract.get("deepseek_called") is False
            and all(
                _dict(row).get("acceptance_contract_only") is True
                and _dict(row).get("ready_now") is False
                and _dict(row).get("output_accepted_now") is False
                and _dict(row).get("model_cache_written_now") is False
                and _dict(row).get("model_ledger_written_now") is False
                and _dict(row).get("model_called_now") is False
                and _dict(row).get("parse_passed_now") is False
                and _dict(row).get("sanitizer_passed_now") is False
                and _dict(row).get("safe_skip_allowed") is True
                and _dict(row).get("cache_get_may_accept_model_output") is False
                and _dict(row).get("react_render_may_accept_model_output") is False
                and _dict(row).get("search_typing_may_accept_model_output") is False
                and _dict(row).get("fastapi_startup_may_accept_model_output") is False
                and _dict(row).get("search_submit_may_accept_model_output_now") is False
                and _dict(row).get("provider_model_execution_requires_execution_request") is True
                and _dict(row).get("model_ledger_required") is True
                and _dict(row).get("model_cache_lineage_required") is True
                and _dict(row).get("allowed_output_fields_only") is True
                and _dict(row).get("raw_prompt_visible_allowed") is False
                and _dict(row).get("raw_model_output_visible_allowed") is False
                and _dict(row).get("token_key_exposure_allowed") is False
                and _dict(row).get("deepseek_is_data_source") is False
                and _dict(row).get("deepseek_may_overwrite_numeric_or_action_fields") is False
                and _dict(row).get("row_is_model_correctness_evidence") is False
                and _dict(row).get("row_is_production_evidence") is False
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("does_not_execute_trades") is True
                and _dict(row).get("does_not_modify_strategy_action") is True
                for row in deepseek_output_acceptance_rows.values()
            )
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_output_acceptance_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_output_acceptance_row_count"
            )
            == 7
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_output_accepted_row_count"
            )
            == 0
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_output_acceptance_cache_written_row_count"
            )
            == 0
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_output_acceptance_safe_field_count"
            )
            == 6
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_output_acceptance_raw_output_visible_allowed"
            )
            is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_output_acceptance_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_output_acceptance_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_output_acceptance_row_count"
            )
            == 7
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_output_acceptance_requires_model_preflight"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_output_acceptance_requires_parse_and_sanitizer"
            )
            is True
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_output_acceptance_raw_prompt_or_output_visible_allowed"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_output_acceptance_is_model_correctness_evidence"
            )
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_output_acceptance_is_production_evidence"
            )
            is False
            and deepseek_output_acceptance_contract.get("raw_prompt_visible_allowed") is False
            and deepseek_output_acceptance_contract.get("raw_model_output_visible_allowed") is False
            and deepseek_output_acceptance_contract.get("token_key_exposure_allowed") is False
            and deepseek_output_acceptance_contract.get("deepseek_is_data_source") is False
            and deepseek_output_acceptance_contract.get("may_overwrite_price") is False
            and deepseek_output_acceptance_contract.get("may_overwrite_holding") is False
            and deepseek_output_acceptance_contract.get("may_overwrite_factor") is False
            and deepseek_output_acceptance_contract.get("may_overwrite_operation_zones") is False
            and deepseek_output_acceptance_contract.get("may_modify_strategy_action") is False
            and deepseek_output_acceptance_contract.get("accepted_output_is_buy_sell_instruction") is False
            and deepseek_output_acceptance_contract.get("acceptance_contract_is_model_correctness_evidence")
            is False
            and deepseek_output_acceptance_contract.get("acceptance_contract_is_production_evidence") is False
            and deepseek_output_acceptance_contract.get("external_calls_triggered") is False
            and deepseek_output_acceptance_contract.get("tushare_called") is False
            and deepseek_output_acceptance_contract.get("github_called") is False
            and deepseek_output_acceptance_contract.get("contains_secret") is False
            and deepseek_output_acceptance_contract.get("does_not_execute_trades") is True
            and deepseek_output_acceptance_contract.get("does_not_modify_strategy_action") is True
            and deepseek_output_acceptance_contract.get(
                "does_not_modify_prices_positions_or_operation_zones"
            )
            is True,
            f"deepseek_output_acceptance_contract={deepseek_output_acceptance_contract}",
        ),
        _row(
            "search_quant_projection_deepseek_readiness_contract_blocks_model_until_provider_factor_next_ready",
            deepseek_readiness_contract.get("schema_version")
            == "command_center_search_quant_projection_deepseek_readiness_contract.v1"
            and deepseek_readiness_contract.get("status")
            == "search_quant_deepseek_readiness_visible_model_execution_pending"
            and deepseek_readiness_contract.get("mode") == "live_light"
            and deepseek_readiness_contract.get("display_action") == "生成 3.0 量化推演"
            and deepseek_readiness_contract.get("allowed_modes") == ["manual", "live_light"]
            and deepseek_readiness_contract.get("task_route") == "POST /api/candidate-radar/quant-projection"
            and deepseek_readiness_contract.get("provider_model_route")
            == "POST /api/candidate-radar/quant-projection-provider-model-acceptance"
            and deepseek_readiness_contract.get("provider_model_route_requires_execution_request") is True
            and deepseek_readiness_contract.get("live_light_bootstrap_can_prepare_context") is True
            and deepseek_readiness_contract.get("deepseek_configured_for_live_light") is True
            and deepseek_readiness_contract.get("deepseek_model_label") == "contract-live-pro"
            and deepseek_readiness_contract.get("readiness_row_count") == 6
            and deepseek_readiness_contract.get("ready_now_row_count") == 0
            and deepseek_readiness_contract.get("required_readiness_keys")
            == [
                "safe_symbol_scope_bound",
                "provider_call_ledger_ready",
                "factor_light_cache_ready",
                "next_session_cache_ready",
                "model_ledger_contract_ready",
                "safe_skip_if_data_not_ready",
            ]
            and deepseek_readiness_contract.get("requires_safe_symbol_scope") is True
            and deepseek_readiness_contract.get("requires_provider_call_ledger_or_gap") is True
            and deepseek_readiness_contract.get("requires_factor_light_cache") is True
            and deepseek_readiness_contract.get("requires_next_session_cache") is True
            and deepseek_readiness_contract.get("requires_model_ledger") is True
            and deepseek_readiness_contract.get("requires_safe_skip_when_data_not_ready") is True
            and deepseek_readiness_contract.get("allowed_output_fields")
            == [
                "summary",
                "support_notes",
                "suppress_notes",
                "conflict_notes",
                "missing_data_notes",
                "discipline_notes",
            ]
            and deepseek_readiness_contract.get("allowed_output_field_count") == 6
            and {
                "model_used",
                "purpose",
                "token_usage",
                "parse_status",
                "cache_status",
                "sanitizer_status",
                "input_hash",
                "output_hash",
            }.issubset(set(_list(deepseek_readiness_contract.get("model_ledger_required_fields"))))
            and set(deepseek_readiness_rows)
            == {
                "safe_symbol_scope_bound",
                "provider_call_ledger_ready",
                "factor_light_cache_ready",
                "next_session_cache_ready",
                "model_ledger_contract_ready",
                "safe_skip_if_data_not_ready",
            }
            and deepseek_readiness_rows.get("provider_call_ledger_ready", {}).get("source_contract")
            == "tushare_light_strategy_contract"
            and deepseek_readiness_rows.get("factor_light_cache_ready", {}).get("source_contract")
            == "search_quant_projection_cache_write_preflight_contract"
            and deepseek_readiness_rows.get("next_session_cache_ready", {}).get("source_contract")
            == "search_quant_projection_cache_write_preflight_contract"
            and deepseek_readiness_rows.get("model_ledger_contract_ready", {}).get("source_contract")
            == "search_quant_projection_deepseek_model_preflight_contract"
            and all(
                _dict(row).get("required_before_deepseek_call") is True
                and _dict(row).get("ready_now") is False
                and _dict(row).get("safe_skip_allowed") is True
                and _dict(row).get("cache_get_may_call_deepseek") is False
                and _dict(row).get("react_render_may_call_deepseek") is False
                and _dict(row).get("search_typing_may_call_deepseek") is False
                and _dict(row).get("fastapi_startup_may_call_deepseek") is False
                and _dict(row).get("search_submit_may_call_deepseek_now") is False
                and _dict(row).get("provider_model_execution_requires_execution_request") is True
                and _dict(row).get("model_ledger_required") is True
                and _dict(row).get("raw_prompt_visible_allowed") is False
                and _dict(row).get("raw_model_output_visible_allowed") is False
                and _dict(row).get("token_key_exposure_allowed") is False
                and _dict(row).get("deepseek_is_data_source") is False
                and _dict(row).get("deepseek_may_overwrite_numeric_or_action_fields") is False
                and _dict(row).get("row_is_model_correctness_evidence") is False
                and _dict(row).get("row_is_production_evidence") is False
                and _dict(row).get("external_calls_triggered") is False
                and _dict(row).get("deepseek_called") is False
                and _dict(row).get("contains_secret") is False
                and _dict(row).get("does_not_execute_trades") is True
                and _dict(row).get("does_not_modify_strategy_action") is True
                for row in deepseek_readiness_rows.values()
            )
            and deepseek_readiness_contract.get("cache_get_may_call_deepseek") is False
            and deepseek_readiness_contract.get("react_render_may_call_deepseek") is False
            and deepseek_readiness_contract.get("search_typing_may_call_deepseek") is False
            and deepseek_readiness_contract.get("fastapi_startup_may_call_deepseek") is False
            and deepseek_readiness_contract.get("search_submit_may_call_deepseek_now") is False
            and deepseek_readiness_contract.get("current_submit_autostart_calls_model") is False
            and deepseek_readiness_contract.get("provider_model_execution_requires_execution_request") is True
            and deepseek_readiness_contract.get("model_execution_implemented") is False
            and deepseek_readiness_contract.get("deepseek_called") is False
            and deepseek_readiness_contract.get("external_calls_triggered") is False
            and deepseek_readiness_contract.get("raw_prompt_visible_allowed") is False
            and deepseek_readiness_contract.get("raw_model_output_visible_allowed") is False
            and deepseek_readiness_contract.get("token_key_exposure_allowed") is False
            and deepseek_readiness_contract.get("deepseek_is_data_source") is False
            and deepseek_readiness_contract.get("may_overwrite_price") is False
            and deepseek_readiness_contract.get("may_overwrite_holding") is False
            and deepseek_readiness_contract.get("may_overwrite_factor") is False
            and deepseek_readiness_contract.get("may_overwrite_operation_zones") is False
            and deepseek_readiness_contract.get("may_modify_strategy_action") is False
            and deepseek_readiness_contract.get("readiness_contract_is_model_correctness_evidence") is False
            and deepseek_readiness_contract.get("readiness_contract_is_production_evidence") is False
            and deepseek_readiness_contract.get("production_deepseek_explanation_complete") is False
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_readiness_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_deepseek_readiness_row_count")
            == 6
            and _dict(status.get("live_light")).get("search_quant_projection_deepseek_ready_now_row_count")
            == 0
            and _dict(status.get("live_light")).get(
                "search_quant_projection_deepseek_allowed_output_field_count"
            )
            == 6
            and _dict(status.get("live_light")).get("search_quant_projection_deepseek_requires_model_ledger")
            is True
            and _dict(status.get("live_light")).get("search_quant_projection_deepseek_calls_model_now")
            is False
            and _dict(status.get("live_light")).get("search_quant_projection_deepseek_is_production_evidence")
            is False
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_readiness_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get("search_quant_projection_deepseek_readiness_row_count") == 6
            and _dict(status.get("policy")).get("search_quant_projection_deepseek_ready_now_row_count") == 0
            and _dict(status.get("policy")).get(
                "search_quant_projection_deepseek_requires_provider_factor_next_ready"
            )
            is True
            and _dict(status.get("policy")).get("search_quant_projection_deepseek_requires_model_ledger")
            is True
            and _dict(status.get("policy")).get("search_quant_projection_deepseek_calls_model_now") is False
            and _dict(status.get("policy")).get("search_quant_projection_deepseek_is_production_evidence")
            is False
            and deepseek_readiness_contract.get("contains_secret") is False
            and deepseek_readiness_contract.get("does_not_execute_trades") is True
            and deepseek_readiness_contract.get("does_not_modify_strategy_action") is True,
            f"deepseek_readiness_contract={deepseek_readiness_contract}",
        ),
        _row(
            "search_quant_projection_latest_status_surface_replays_local_task_without_creating_task",
            latest_quant_projection_status.get("schema_version")
            == "command_center_search_quant_projection_latest_status.v1"
            and latest_quant_projection_status.get("status")
            == "latest_quant_projection_receipt_visible_provider_model_pending"
            and latest_quant_projection_status.get("lookup_source") == "task_service.list_task_statuses"
            and latest_quant_projection_status.get("lookup_creates_task") is False
            and latest_quant_projection_status.get("route") == "POST /api/candidate-radar/quant-projection"
            and latest_quant_projection_status.get("route_implemented") is True
            and latest_quant_projection_status.get("task_found") is True
            and latest_quant_projection_status.get("task_id") == quant_projection.get("task_id")
            and latest_quant_projection_status.get("task_status") == "success"
            and latest_quant_projection_status.get("current_step") == "candidate_radar_quant_projection_ready"
            and latest_quant_projection_status.get("output_packet_key") == "command_center_3_candidate_radar_cache"
            and latest_quant_projection_status.get("storage_source") in {"memory_and_sqlite", "sqlite_meta"}
            and latest_quant_projection_status.get("durable_task_visible") is True
            and latest_quant_projection_status.get("memory_only_task_is_durable_evidence") is False
            and latest_quant_projection_status.get("symbol") == "000001.SZ"
            and latest_quant_projection_status.get("symbol_valid") is True
            and latest_quant_projection_status.get("scan_mode") == "search_quant_projection"
            and latest_quant_projection_status.get("selected_light_apis")
            == ["trade_cal_if_needed", "daily", "daily_basic", "moneyflow"]
            and latest_quant_projection_status.get("include_tushare_requested") is True
            and latest_quant_projection_status.get("include_deepseek_requested") is True
            and latest_quant_projection_status.get("local_receipt_visible") is True
            and latest_quant_projection_status.get("provider_model_pending") is True
            and latest_quant_projection_status.get("acceptance_dry_run_required") is True
            and latest_quant_projection_status.get("execution_request_required") is True
            and latest_quant_projection_status.get("provider_model_route")
            == "POST /api/candidate-radar/quant-projection-provider-model-acceptance"
            and latest_quant_projection_status.get("result_surface_count") == 6
            and latest_quant_projection_status.get("call_ledger_count") == 1
            and latest_quant_projection_status.get("call_status")
            == "quant_projection_local_receipt_ready_provider_model_pending"
            and latest_quant_projection_status.get("task_success_is_provider_model_evidence") is False
            and latest_quant_projection_status.get("task_success_is_production_evidence") is False
            and latest_quant_projection_status.get("provider_execution_implemented") is False
            and latest_quant_projection_status.get("model_execution_implemented") is False
            and latest_quant_projection_status.get("factor_refresh_executed") is False
            and latest_quant_projection_status.get("next_session_refresh_executed") is False
            and latest_quant_projection_status.get("echarts_payload_refreshed") is False
            and latest_quant_projection_status.get("production_quant_projection_complete") is False
            and latest_quant_projection_status.get("external_calls_triggered") is False
            and latest_quant_projection_status.get("tushare_called") is False
            and latest_quant_projection_status.get("deepseek_called") is False
            and latest_quant_projection_status.get("github_called") is False
            and latest_quant_projection_status.get("credential_values_exposed") is False
            and latest_quant_projection_status.get("env_key_names_included") is False
            and latest_quant_projection_status.get("candidate_is_not_buy_instruction") is True
            and latest_quant_projection_status.get("does_not_execute_trades") is True
            and latest_quant_projection_status.get("does_not_modify_strategy_action") is True
            and latest_quant_projection_live_light.get("search_quant_projection_latest_status_visible") is True
            and latest_quant_projection_live_light.get("search_quant_projection_latest_task_found") is True
            and latest_quant_projection_live_light.get("search_quant_projection_latest_status")
            == "latest_quant_projection_receipt_visible_provider_model_pending"
            and latest_quant_projection_live_light.get("search_quant_projection_latest_task_id")
            == quant_projection.get("task_id")
            and latest_quant_projection_live_light.get("search_quant_projection_latest_symbol") == "000001.SZ"
            and latest_quant_projection_live_light.get("search_quant_projection_latest_local_receipt_visible") is True
            and latest_quant_projection_live_light.get("search_quant_projection_latest_lookup_creates_task") is False
            and latest_quant_projection_live_light.get("search_quant_projection_latest_is_production_evidence") is False
            and latest_quant_projection_policy.get("search_quant_projection_latest_status_visible") is True
            and latest_quant_projection_policy.get("search_quant_projection_latest_lookup_creates_task") is False
            and latest_quant_projection_policy.get("search_quant_projection_latest_is_production_evidence") is False
            and "DROP_TS" not in latest_quant_projection_status_text
            and "DROP_DS" not in latest_quant_projection_status_text
            and '"api_key"' not in latest_quant_projection_status_text
            and '"token"' not in latest_quant_projection_status_text,
            f"latest_quant_projection_status={latest_quant_projection_status}",
        ),
        _row(
            "search_quant_projection_provider_model_latest_status_replays_local_task_without_creating_task",
            latest_provider_model_status.get("schema_version")
            == "command_center_search_quant_projection_provider_model_latest_status.v1"
            and latest_provider_model_status.get("status")
            == "latest_quant_projection_provider_model_task_visible_output_acceptance_pending"
            and latest_provider_model_status.get("lookup_source") == "task_service.list_task_statuses"
            and latest_provider_model_status.get("lookup_creates_task") is False
            and latest_provider_model_status.get("route")
            == "POST /api/candidate-radar/quant-projection-provider-model-acceptance"
            and latest_provider_model_status.get("route_implemented") is True
            and latest_provider_model_status.get("task_type")
            == "run_candidate_radar_quant_projection_provider_model_acceptance"
            and latest_provider_model_status.get("task_catalog_covered") is True
            and latest_provider_model_status.get("task_found") is True
            and latest_provider_model_status.get("task_id") == quant_provider_model.get("task_id")
            and latest_provider_model_status.get("task_status") == "success"
            and latest_provider_model_status.get("current_step")
            == "search_quant_provider_model_acceptance_waiting_deepseek_output_acceptance"
            and latest_provider_model_status.get("output_packet_key") == "command_center_3_candidate_radar_cache"
            and latest_provider_model_status.get("storage_source") in {"memory_and_sqlite", "sqlite_meta"}
            and latest_provider_model_status.get("durable_task_visible") is True
            and latest_provider_model_status.get("memory_only_task_is_durable_evidence") is False
            and latest_provider_model_status.get("symbol") == "000001.SZ"
            and latest_provider_model_status.get("selected_apis") == ["trade_cal", "daily", "daily_basic", "moneyflow"]
            and latest_provider_model_status.get("include_deepseek_requested") is True
            and latest_provider_model_status.get("call_ledger_count") == 2
            and latest_provider_model_status.get("provider_call_ledger_count") == 1
            and latest_provider_model_status.get("provider_api_success_count") == 1
            and latest_provider_model_status.get("model_ledger_count") == 0
            and latest_provider_model_status.get("call_status")
            == "search_quant_provider_model_acceptance_waiting_deepseek_output_acceptance"
            and latest_provider_model_status.get("provider_model_acceptance_visible") is False
            and latest_provider_model_status.get("provider_call_ledger_evidence_done") is True
            and latest_provider_model_status.get("tushare_call_ledger_evidence_done") is True
            and latest_provider_model_status.get("deepseek_model_ledger_evidence_done") is False
            and latest_provider_model_status.get("deepseek_output_acceptance_contract_visible") is True
            and latest_provider_model_status.get("deepseek_output_acceptance_required_when_deepseek_used") is True
            and latest_provider_model_status.get("deepseek_output_acceptance_required") is True
            and latest_provider_model_status.get("deepseek_output_acceptance_done") is False
            and latest_provider_model_status.get("deepseek_output_acceptance_status")
            == "pending_model_ledger"
            and latest_provider_model_status.get("deepseek_output_cache_written") is False
            and latest_provider_model_status.get("deepseek_output_safe_summary_visible") is False
            and latest_provider_model_status.get("deepseek_skipped_by_default") is True
            and latest_provider_model_status.get("provider_execution_observed") is True
            and latest_provider_model_status.get("model_execution_observed") is False
            and latest_provider_model_status.get("task_success_is_provider_call_evidence") is True
            and latest_provider_model_status.get("task_success_is_model_evidence") is False
            and latest_provider_model_status.get("task_success_is_model_output_evidence") is False
            and latest_provider_model_status.get("task_success_is_provider_model_evidence") is False
            and latest_provider_model_status.get("task_success_is_production_evidence") is False
            and latest_provider_model_status.get("production_quant_projection_complete") is False
            and latest_provider_model_status.get("production_radar_replacement_complete") is False
            and latest_provider_model_status.get("status_get_external_calls") is False
            and latest_provider_model_status.get("external_calls_triggered") is False
            and latest_provider_model_status.get("tushare_called") is True
            and latest_provider_model_status.get("deepseek_called") is False
            and latest_provider_model_status.get("github_called") is False
            and latest_provider_model_status.get("credential_values_exposed") is False
            and latest_provider_model_status.get("env_key_names_included") is False
            and latest_provider_model_status.get("candidate_is_not_buy_instruction") is True
            and latest_provider_model_status.get("does_not_execute_trades") is True
            and latest_provider_model_status.get("does_not_modify_strategy_action") is True
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_status_visible"
            )
            is True
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_task_found"
            )
            is True
            and latest_provider_model_live_light.get("search_quant_projection_provider_model_latest_status")
            == "latest_quant_projection_provider_model_task_visible_output_acceptance_pending"
            and latest_provider_model_live_light.get("search_quant_projection_provider_model_latest_task_id")
            == quant_provider_model.get("task_id")
            and latest_provider_model_live_light.get("search_quant_projection_provider_model_latest_symbol")
            == "000001.SZ"
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_provider_call_ledger_evidence_done"
            )
            is True
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_deepseek_model_ledger_evidence_done"
            )
            is False
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_deepseek_output_acceptance_done"
            )
            is False
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_deepseek_output_acceptance_status"
            )
            == "pending_model_ledger"
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_deepseek_output_cache_written"
            )
            is False
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_acceptance_visible"
            )
            is False
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_task_success_is_model_output_evidence"
            )
            is False
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_lookup_creates_task"
            )
            is False
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_status_get_external_calls"
            )
            is False
            and latest_provider_model_live_light.get(
                "search_quant_projection_provider_model_latest_is_production_evidence"
            )
            is False
            and latest_provider_model_policy.get(
                "search_quant_projection_provider_model_latest_status_visible"
            )
            is True
            and latest_provider_model_policy.get(
                "search_quant_projection_provider_model_latest_lookup_creates_task"
            )
            is False
            and latest_provider_model_policy.get(
                "search_quant_projection_provider_model_latest_status_get_external_calls"
            )
            is False
            and latest_provider_model_policy.get(
                "search_quant_projection_provider_model_latest_requires_deepseek_output_acceptance"
            )
            is True
            and latest_provider_model_policy.get(
                "search_quant_projection_provider_model_latest_output_cache_write_requires_acceptance"
            )
            is True
            and latest_provider_model_policy.get(
                "search_quant_projection_provider_model_latest_task_success_is_model_output_evidence"
            )
            is False
            and latest_provider_model_policy.get(
                "search_quant_projection_provider_model_latest_task_success_is_provider_model_evidence"
            )
            is False
            and latest_provider_model_policy.get(
                "search_quant_projection_provider_model_latest_is_production_evidence"
            )
            is False
            and "DROP_TS" not in latest_provider_model_status_text
            and "DROP_DS" not in latest_provider_model_status_text
            and '"api_key"' not in latest_provider_model_status_text
            and '"token"' not in latest_provider_model_status_text,
            f"latest_provider_model_status={latest_provider_model_status}",
        ),
        _row(
            "tushare_light_strategy_contract_keeps_provider_evidence_pending",
            tushare_contract.get("schema_version") == "command_center_tushare_light_strategy_contract.v1"
            and tushare_contract.get("status") == "tushare_light_strategy_visible_provider_execution_pending"
            and tushare_contract.get("mode") == "live_light"
            and tushare_contract.get("provider") == "tushare"
            and tushare_contract.get("allowed_live_light_startup_apis")
            == ["trade_cal_if_needed", "daily", "daily_basic", "moneyflow"]
            and tushare_contract.get("allowed_acceptance_apis") == ["trade_cal", "daily", "daily_basic", "moneyflow"]
            and tushare_contract.get("allowed_scope") == "current_target_holdings_watchlist_light_only"
            and tushare_contract.get("symbol_limit") == 2
            and tushare_contract.get("live_light_tushare_planned") is True
            and tushare_contract.get("cache_get_calls_tushare") is False
            and tushare_contract.get("fastapi_startup_calls_tushare") is False
            and tushare_contract.get("react_render_calls_tushare") is False
            and tushare_contract.get("post_task_required") is True
            and tushare_contract.get("call_ledger_required") is True
            and tushare_contract.get("request_params_safe_required") is True
            and tushare_contract.get("safe_error_required") is True
            and tushare_contract.get("provider_execution_implemented") is False
            and tushare_contract.get("production_tushare_light_verified") is False
            and tushare_contract.get("matrix_or_receipt_is_provider_evidence") is False
            and tushare_contract.get("no_record_is_negative_evidence") is False
            and tushare_contract.get("permission_denied_is_verified") is False
            and tushare_contract.get("empty_dataframe_is_verified") is False
            and tushare_contract.get("unselected_api_may_be_marked_verified") is False
            and tushare_contract.get("full_pool_on_open_allowed") is False
            and tushare_contract.get("token_key_exposure_allowed") is False
            and tushare_contract.get("external_calls_triggered") is False
            and tushare_contract.get("tushare_called") is False
            and tushare_contract.get("deepseek_called") is False
            and tushare_contract.get("github_called") is False
            and tushare_contract.get("does_not_execute_trades") is True
            and tushare_contract.get("does_not_modify_strategy_action") is True,
            f"tushare_contract={tushare_contract}",
        ),
        _row(
            "deepseek_pro_strategy_contract_keeps_model_explanation_governed",
            deepseek_contract.get("schema_version") == "command_center_deepseek_pro_strategy_contract.v1"
            and deepseek_contract.get("status") == "deepseek_pro_strategy_visible_model_execution_pending"
            and deepseek_contract.get("mode") == "live_light"
            and deepseek_contract.get("provider") == "deepseek"
            and deepseek_contract.get("model") == "contract-live-pro"
            and deepseek_contract.get("purpose") == "explain_after_data_ready"
            and deepseek_contract.get("allowed_modes") == ["manual", "live_light"]
            and deepseek_contract.get("live_light_deepseek_planned") is True
            and deepseek_contract.get("cache_get_calls_deepseek") is False
            and deepseek_contract.get("fastapi_startup_calls_deepseek") is False
            and deepseek_contract.get("react_render_calls_deepseek") is False
            and deepseek_contract.get("post_task_required") is True
            and deepseek_contract.get("model_ledger_required") is True
            and {"model_used", "status", "token_usage", "parse_status", "cache_hit", "input_hash", "output_hash"}.issubset(
                set(_list(deepseek_contract.get("required_model_ledger_fields")))
            )
            and deepseek_contract.get("input_hash_required") is True
            and deepseek_contract.get("output_hash_required") is True
            and deepseek_contract.get("token_usage_required") is True
            and deepseek_contract.get("parse_status_required") is True
            and deepseek_contract.get("sanitizer_required") is True
            and deepseek_contract.get("parse_failed_discard_required") is True
            and set(_list(deepseek_contract.get("allowed_output_fields")))
            == {
                "summary",
                "support_notes",
                "suppress_notes",
                "conflict_notes",
                "missing_data_notes",
                "discipline_notes",
            }
            and deepseek_contract.get("allowed_output_fields_only") is True
            and deepseek_contract.get("deepseek_is_data_source") is False
            and deepseek_contract.get("may_overwrite_price") is False
            and deepseek_contract.get("may_overwrite_holding") is False
            and deepseek_contract.get("may_overwrite_factor") is False
            and deepseek_contract.get("may_overwrite_operation_zones") is False
            and deepseek_contract.get("may_overwrite_strategy_action") is False
            and deepseek_contract.get("numeric_field_overwrite_allowed") is False
            and deepseek_contract.get("buy_sell_instruction_allowed") is False
            and deepseek_contract.get("sanitizer_is_model_correctness_evidence") is False
            and deepseek_contract.get("prompt_preview_is_model_evidence") is False
            and deepseek_contract.get("mock_or_receipt_is_model_evidence") is False
            and deepseek_contract.get("model_execution_implemented") is False
            and deepseek_contract.get("production_deepseek_pro_verified") is False
            and deepseek_contract.get("token_key_exposure_allowed") is False
            and deepseek_contract.get("external_calls_triggered") is False
            and deepseek_contract.get("tushare_called") is False
            and deepseek_contract.get("deepseek_called") is False
            and deepseek_contract.get("github_called") is False
            and deepseek_contract.get("does_not_execute_trades") is True
            and deepseek_contract.get("does_not_modify_strategy_action") is True,
            f"deepseek_contract={deepseek_contract}",
        ),
        _row(
            "ui_nonblocking_runtime_contract_requires_cache_first_task_polling",
            ui_contract.get("schema_version") == "command_center_ui_nonblocking_runtime_contract.v1"
            and ui_contract.get("status") == "ui_nonblocking_contract_visible_browser_evidence_pending"
            and ui_contract.get("mode") == "live_light"
            and ui_contract.get("cache_first_render_required") is True
            and ui_contract.get("initial_cache_render_calls_provider") is False
            and ui_contract.get("fastapi_startup_external_calls") is False
            and ui_contract.get("react_initial_render_external_calls") is False
            and ui_contract.get("react_render_direct_provider_calls") is False
            and ui_contract.get("get_status_creates_task") is False
            and ui_contract.get("background_post_task_after_cache_render_only") is True
            and ui_contract.get("live_light_auto_task_allowed_after_cache_render") is True
            and ui_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and ui_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and ui_contract.get("task_polling_required") is True
            and ui_contract.get("task_id_visible_required") is True
            and ui_contract.get("task_status_visible_required") is True
            and ui_contract.get("progress_visible_required") is True
            and ui_contract.get("safe_error_visible_required") is True
            and ui_contract.get("rate_limit_skipped_state_visible_required") is True
            and ui_contract.get("rate_limit_seconds") == 600
            and ui_contract.get("ui_thread_blocking_provider_call_allowed") is False
            and ui_contract.get("streamlit_style_sync_rerun_blocking_allowed") is False
            and ui_contract.get("browser_runtime_evidence_complete") is False
            and ui_contract.get("performance_trace_evidence_complete") is False
            and ui_contract.get("local_contract_only") is True
            and ui_contract.get("provider_execution_implemented") is False
            and ui_contract.get("model_execution_implemented") is False
            and ui_contract.get("production_ui_nonblocking_verified") is False
            and ui_contract.get("external_calls_triggered") is False
            and ui_contract.get("tushare_called") is False
            and ui_contract.get("deepseek_called") is False
            and ui_contract.get("github_called") is False
            and ui_contract.get("does_not_execute_trades") is True
            and ui_contract.get("does_not_modify_strategy_action") is True,
            f"ui_contract={ui_contract}",
        ),
        _row(
            "runtime_cache_first_polling_contract_sequences_cache_post_poll_refresh_fallback",
            cache_first_polling.get("schema_version") == "command_center_runtime_cache_first_polling_contract.v1"
            and cache_first_polling.get("status") == "runtime_cache_first_polling_visible_browser_evidence_pending"
            and cache_first_polling.get("mode") == "live_light"
            and cache_first_polling.get("phase_count") == 7
            and cache_first_polling.get("phase_order")
            == [
                "initial_cache_render",
                "mode_and_config_status_read",
                "after_cache_render_bootstrap_post",
                "search_submit_local_projection_post",
                "task_status_polling",
                "success_refresh_cache_and_status",
                "failure_recovery_last_good_cache",
            ]
            and set(cache_first_polling_rows)
            == {
                "initial_cache_render",
                "mode_and_config_status_read",
                "after_cache_render_bootstrap_post",
                "search_submit_local_projection_post",
                "task_status_polling",
                "success_refresh_cache_and_status",
                "failure_recovery_last_good_cache",
            }
            and [
                cache_first_polling_rows.get(key, {}).get("phase_order")
                for key in cache_first_polling.get("phase_order", [])
            ]
            == [1, 2, 3, 4, 5, 6, 7]
            and cache_first_polling_rows.get("initial_cache_render", {}).get("cache_read_required") is True
            and cache_first_polling_rows.get("initial_cache_render", {}).get("must_complete_before_local_post")
            is True
            and cache_first_polling_rows.get("initial_cache_render", {}).get("local_backend_post_allowed")
            is False
            and cache_first_polling_rows.get("mode_and_config_status_read", {}).get(
                "bootstrap_status_read_required"
            )
            is True
            and cache_first_polling_rows.get("mode_and_config_status_read", {}).get("task_creation_allowed")
            is False
            and cache_first_polling_rows.get("after_cache_render_bootstrap_post", {}).get(
                "local_backend_post_allowed"
            )
            is True
            and cache_first_polling_rows.get("after_cache_render_bootstrap_post", {}).get("task_creation_allowed")
            is True
            and cache_first_polling_rows.get("after_cache_render_bootstrap_post", {}).get("task_route")
            == "POST /api/bootstrap/live-startup"
            and cache_first_polling_rows.get("search_submit_local_projection_post", {}).get(
                "local_backend_post_allowed"
            )
            is True
            and cache_first_polling_rows.get("search_submit_local_projection_post", {}).get(
                "task_creation_allowed"
            )
            is True
            and cache_first_polling_rows.get("search_submit_local_projection_post", {}).get("safe_submit_required")
            is True
            and cache_first_polling_rows.get("search_submit_local_projection_post", {}).get("task_route")
            == "POST /api/candidate-radar/quant-projection"
            and cache_first_polling_rows.get("task_status_polling", {}).get("polling_required") is True
            and cache_first_polling_rows.get("task_status_polling", {}).get("task_creation_allowed") is False
            and cache_first_polling_rows.get("success_refresh_cache_and_status", {}).get(
                "success_refresh_required"
            )
            is True
            and cache_first_polling_rows.get("success_refresh_cache_and_status", {}).get("cache_read_required")
            is True
            and cache_first_polling_rows.get("failure_recovery_last_good_cache", {}).get(
                "last_good_cache_required"
            )
            is True
            and cache_first_polling_rows.get("failure_recovery_last_good_cache", {}).get("manual_retry_only")
            is True
            and cache_first_polling_rows.get("failure_recovery_last_good_cache", {}).get("safe_error_required")
            is True
            and all(row.get("react_render_blocks_on_task") is False for row in cache_first_polling_rows.values())
            and all(
                row.get("direct_provider_or_model_call_allowed") is False
                for row in cache_first_polling_rows.values()
            )
            and all(row.get("frontend_provider_call_allowed") is False for row in cache_first_polling_rows.values())
            and all(row.get("frontend_model_call_allowed") is False for row in cache_first_polling_rows.values())
            and all(row.get("phase_is_production_evidence") is False for row in cache_first_polling_rows.values())
            and all(row.get("external_calls_triggered") is False for row in cache_first_polling_rows.values())
            and all(row.get("tushare_called") is False for row in cache_first_polling_rows.values())
            and all(row.get("deepseek_called") is False for row in cache_first_polling_rows.values())
            and all(row.get("github_called") is False for row in cache_first_polling_rows.values())
            and all(row.get("contains_secret") is False for row in cache_first_polling_rows.values())
            and all(row.get("does_not_execute_trades") is True for row in cache_first_polling_rows.values())
            and all(row.get("does_not_modify_strategy_action") is True for row in cache_first_polling_rows.values())
            and cache_first_polling.get("cache_first_render_required") is True
            and cache_first_polling.get("post_task_after_cache_render_only") is True
            and cache_first_polling.get("safe_search_submit_after_status_gate_only") is True
            and cache_first_polling.get("polling_required") is True
            and cache_first_polling.get("success_refreshes_cache_and_status") is True
            and cache_first_polling.get("failure_recovery_keeps_last_good_cache") is True
            and cache_first_polling.get("manual_retry_only_after_failure") is True
            and cache_first_polling.get("unbounded_task_queue_allowed") is False
            and cache_first_polling.get("rate_limit_seconds") == 600
            and cache_first_polling.get("task_creation_allowed_phase_count") == 2
            and cache_first_polling.get("local_backend_post_phase_count") == 2
            and cache_first_polling.get("direct_external_call_allowed_phase_count") == 0
            and cache_first_polling.get("direct_provider_or_model_call_allowed_phase_count") == 0
            and cache_first_polling.get("linked_external_silence_schema_version")
            == "command_center_runtime_external_silence_contract.v1"
            and cache_first_polling.get("linked_external_silence_row_count") == 10
            and cache_first_polling.get("linked_operator_summary_schema_version")
            == "command_center_runtime_operator_summary_contract.v1"
            and cache_first_polling.get("linked_frontend_wiring_schema_version")
            == "command_center_search_quant_projection_frontend_wiring_acceptance_contract.v1"
            and cache_first_polling.get("frontend_wiring_implemented") is False
            and cache_first_polling.get("frontend_acceptance_test_implemented") is False
            and cache_first_polling.get("browser_runtime_evidence_pending") is True
            and cache_first_polling.get("browser_runtime_evidence_complete") is False
            and cache_first_polling.get("performance_trace_evidence_complete") is False
            and cache_first_polling.get("contract_creates_task") is False
            and cache_first_polling.get("contract_calls_provider_or_model") is False
            and cache_first_polling.get("provider_execution_implemented") is False
            and cache_first_polling.get("model_execution_implemented") is False
            and cache_first_polling.get("contract_is_production_evidence") is False
            and cache_first_polling.get("production_live_light_complete") is False
            and cache_first_polling.get("external_calls_triggered") is False
            and cache_first_polling.get("tushare_called") is False
            and cache_first_polling.get("deepseek_called") is False
            and cache_first_polling.get("github_called") is False
            and cache_first_polling.get("contains_secret") is False
            and cache_first_polling.get("does_not_execute_trades") is True
            and cache_first_polling.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get("runtime_cache_first_polling_contract_visible") is True
            and _dict(status.get("live_light")).get("runtime_cache_first_polling_phase_count") == 7
            and _dict(status.get("live_light")).get("runtime_cache_first_polling_cache_first_render_required")
            is True
            and _dict(status.get("live_light")).get("runtime_cache_first_polling_task_polling_required")
            is True
            and _dict(status.get("live_light")).get("runtime_cache_first_polling_last_good_cache_required")
            is True
            and _dict(status.get("live_light")).get("runtime_cache_first_polling_browser_evidence_complete")
            is False
            and _dict(status.get("live_light")).get("runtime_cache_first_polling_is_production_evidence")
            is False
            and _dict(status.get("policy")).get("runtime_cache_first_polling_contract_visible") is True
            and _dict(status.get("policy")).get("runtime_cache_first_polling_phase_count") == 7
            and _dict(status.get("policy")).get("runtime_cache_first_polling_cache_first_render_required")
            is True
            and _dict(status.get("policy")).get("runtime_cache_first_polling_task_polling_required") is True
            and _dict(status.get("policy")).get("runtime_cache_first_polling_last_good_cache_required") is True
            and _dict(status.get("policy")).get("runtime_cache_first_polling_browser_evidence_complete")
            is False
            and _dict(status.get("policy")).get("runtime_cache_first_polling_is_production_evidence")
            is False,
            f"cache_first_polling={cache_first_polling}",
        ),
        _row(
            "runtime_frontend_enablement_gate_blocks_stage_04_until_browser_wiring_evidence",
            frontend_enablement_gate.get("schema_version")
            == "command_center_live_light_frontend_enablement_gate.v1"
            and frontend_enablement_gate.get("status")
            == "frontend_enablement_blocked_browser_and_wiring_evidence_pending"
            and frontend_enablement_gate.get("mode") == "live_light"
            and frontend_enablement_gate.get("target_stage_key") == "stage_04_frontend_nonblocking_wiring"
            and frontend_enablement_gate.get("target_frontend_route") == "desktop/src/routes/CandidateRadar.tsx"
            and frontend_enablement_gate.get("gate_row_count") == 12
            and frontend_enablement_gate.get("passed_gate_count") == 5
            and frontend_enablement_gate.get("blocking_row_count") == 7
            and frontend_enablement_gate.get("frontend_enablement_allowed") is False
            and frontend_enablement_gate.get("frontend_submit_autostart_wiring_can_be_enabled") is False
            and frontend_enablement_gate.get("browser_network_trace_required") is True
            and frontend_enablement_gate.get("browser_runtime_evidence_complete") is False
            and frontend_enablement_gate.get("failure_recovery_evidence_complete") is False
            and frontend_enablement_gate.get("frontend_wiring_implemented") is False
            and frontend_enablement_gate.get("frontend_acceptance_test_implemented") is False
            and frontend_enablement_gate.get("backend_local_search_projection_ready") is True
            and frontend_enablement_gate.get("linked_rollout_schema_version")
            == "command_center_live_light_rollout_roadmap.v1"
            and frontend_enablement_gate.get("linked_cache_first_polling_schema_version")
            == "command_center_runtime_cache_first_polling_contract.v1"
            and frontend_enablement_gate.get("linked_frontend_wiring_schema_version")
            == "command_center_search_quant_projection_frontend_wiring_acceptance_contract.v1"
            and frontend_enablement_gate.get("linked_external_silence_schema_version")
            == "command_center_runtime_external_silence_contract.v1"
            and set(frontend_enablement_gate_rows)
            == {
                "stage_04_is_next_implementation",
                "live_light_mode_and_safe_config_visible",
                "backend_local_search_projection_ready",
                "cache_first_polling_contract_ready",
                "frontend_wiring_acceptance_contract_ready",
                "initial_cache_render_silent_browser_trace",
                "safe_submit_single_local_post_browser_trace",
                "task_polling_and_success_refresh_browser_trace",
                "failure_recovery_last_good_cache_browser_trace",
                "frontend_provider_model_silence_browser_trace",
                "research_only_boundaries_visible_browser_trace",
                "frontend_code_wiring_implemented",
            }
            and [
                frontend_enablement_gate_rows.get(key, {}).get("gate_order")
                for key in [
                    "stage_04_is_next_implementation",
                    "live_light_mode_and_safe_config_visible",
                    "backend_local_search_projection_ready",
                    "cache_first_polling_contract_ready",
                    "frontend_wiring_acceptance_contract_ready",
                    "initial_cache_render_silent_browser_trace",
                    "safe_submit_single_local_post_browser_trace",
                    "task_polling_and_success_refresh_browser_trace",
                    "failure_recovery_last_good_cache_browser_trace",
                    "frontend_provider_model_silence_browser_trace",
                    "research_only_boundaries_visible_browser_trace",
                    "frontend_code_wiring_implemented",
                ]
            ]
            == list(range(1, 13))
            and all(
                frontend_enablement_gate_rows.get(key, {}).get("passed") is True
                and frontend_enablement_gate_rows.get(key, {}).get("blocks_enablement") is False
                for key in [
                    "stage_04_is_next_implementation",
                    "live_light_mode_and_safe_config_visible",
                    "backend_local_search_projection_ready",
                    "cache_first_polling_contract_ready",
                    "frontend_wiring_acceptance_contract_ready",
                ]
            )
            and all(
                frontend_enablement_gate_rows.get(key, {}).get("passed") is False
                and frontend_enablement_gate_rows.get(key, {}).get("blocks_enablement") is True
                for key in [
                    "initial_cache_render_silent_browser_trace",
                    "safe_submit_single_local_post_browser_trace",
                    "task_polling_and_success_refresh_browser_trace",
                    "failure_recovery_last_good_cache_browser_trace",
                    "frontend_provider_model_silence_browser_trace",
                    "research_only_boundaries_visible_browser_trace",
                    "frontend_code_wiring_implemented",
                ]
            )
            and frontend_enablement_gate.get("blocking_gate_keys")
            == [
                "initial_cache_render_silent_browser_trace",
                "safe_submit_single_local_post_browser_trace",
                "task_polling_and_success_refresh_browser_trace",
                "failure_recovery_last_good_cache_browser_trace",
                "frontend_provider_model_silence_browser_trace",
                "research_only_boundaries_visible_browser_trace",
                "frontend_code_wiring_implemented",
            ]
            and frontend_enablement_gate.get("next_required_evidence")
            == [
                "frontend_task_receipt_and_status_panel_wiring",
                "browser_network_trace",
                "failure_recovery_browser_trace",
                "research_only_boundary_visual_check",
            ]
            and all(row.get("required_before_enable") is True for row in frontend_enablement_gate_rows.values())
            and all(row.get("enables_external_call_directly") is False for row in frontend_enablement_gate_rows.values())
            and all(row.get("creates_task") is False for row in frontend_enablement_gate_rows.values())
            and all(row.get("cache_get_creates_task") is False for row in frontend_enablement_gate_rows.values())
            and all(row.get("react_render_creates_task") is False for row in frontend_enablement_gate_rows.values())
            and all(
                row.get("react_render_direct_provider_calls") is False
                for row in frontend_enablement_gate_rows.values()
            )
            and all(
                row.get("provider_model_execution_requires_execution_request") is True
                for row in frontend_enablement_gate_rows.values()
            )
            and all(
                row.get("gate_row_is_production_evidence") is False
                for row in frontend_enablement_gate_rows.values()
            )
            and all(row.get("external_calls_triggered") is False for row in frontend_enablement_gate_rows.values())
            and all(row.get("tushare_called") is False for row in frontend_enablement_gate_rows.values())
            and all(row.get("deepseek_called") is False for row in frontend_enablement_gate_rows.values())
            and all(row.get("github_called") is False for row in frontend_enablement_gate_rows.values())
            and all(row.get("contains_secret") is False for row in frontend_enablement_gate_rows.values())
            and all(row.get("does_not_execute_trades") is True for row in frontend_enablement_gate_rows.values())
            and all(row.get("does_not_modify_strategy_action") is True for row in frontend_enablement_gate_rows.values())
            and frontend_enablement_gate.get("contract_creates_task") is False
            and frontend_enablement_gate.get("contract_calls_provider_or_model") is False
            and frontend_enablement_gate.get("provider_execution_implemented") is False
            and frontend_enablement_gate.get("model_execution_implemented") is False
            and frontend_enablement_gate.get("contract_is_production_evidence") is False
            and frontend_enablement_gate.get("production_live_light_complete") is False
            and frontend_enablement_gate.get("external_calls_triggered") is False
            and frontend_enablement_gate.get("tushare_called") is False
            and frontend_enablement_gate.get("deepseek_called") is False
            and frontend_enablement_gate.get("github_called") is False
            and frontend_enablement_gate.get("contains_secret") is False
            and frontend_enablement_gate.get("does_not_execute_trades") is True
            and frontend_enablement_gate.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get("runtime_frontend_enablement_gate_contract_visible")
            is True
            and _dict(status.get("live_light")).get("runtime_frontend_enablement_allowed") is False
            and _dict(status.get("live_light")).get("runtime_frontend_enablement_blocking_row_count") == 7
            and _dict(status.get("live_light")).get("runtime_frontend_enablement_target_stage_key")
            == "stage_04_frontend_nonblocking_wiring"
            and _dict(status.get("live_light")).get("runtime_frontend_enablement_browser_evidence_complete")
            is False
            and _dict(status.get("live_light")).get("runtime_frontend_enablement_is_production_evidence")
            is False
            and _dict(status.get("policy")).get("runtime_frontend_enablement_gate_contract_visible") is True
            and _dict(status.get("policy")).get("runtime_frontend_enablement_allowed") is False
            and _dict(status.get("policy")).get("runtime_frontend_enablement_blocking_row_count") == 7
            and _dict(status.get("policy")).get("runtime_frontend_enablement_target_stage_key")
            == "stage_04_frontend_nonblocking_wiring"
            and _dict(status.get("policy")).get("runtime_frontend_enablement_browser_evidence_complete")
            is False
            and _dict(status.get("policy")).get("runtime_frontend_enablement_is_production_evidence") is False,
            f"frontend_enablement_gate={frontend_enablement_gate}",
        ),
        _row(
            "runtime_browser_evidence_contract_defines_stage_04_trace_requirements_without_collection",
            browser_evidence.get("schema_version") == "command_center_live_light_browser_evidence_contract.v1"
            and browser_evidence.get("status") == "browser_evidence_contract_visible_collection_pending"
            and browser_evidence.get("mode") == "live_light"
            and browser_evidence.get("target_stage_key") == "stage_04_frontend_nonblocking_wiring"
            and browser_evidence.get("target_frontend_route") == "desktop/src/routes/CandidateRadar.tsx"
            and browser_evidence.get("evidence_row_count") == 7
            and browser_evidence.get("collected_evidence_row_count") == 0
            and browser_evidence.get("passed_evidence_row_count") == 0
            and browser_evidence.get("blocking_evidence_row_count") == 7
            and browser_evidence.get("required_viewports") == ["desktop", "laptop", "tablet", "mobile"]
            and browser_evidence.get("network_trace_required") is True
            and browser_evidence.get("failure_recovery_trace_required") is True
            and browser_evidence.get("visual_boundary_check_required") is True
            and browser_evidence.get("browser_evidence_complete") is False
            and browser_evidence.get("failure_recovery_evidence_complete") is False
            and browser_evidence.get("research_only_visual_evidence_complete") is False
            and browser_evidence.get("frontend_wiring_implemented") is False
            and browser_evidence.get("frontend_enablement_allowed_after_browser_evidence") is False
            and browser_evidence.get("contract_can_promote_frontend_enablement") is False
            and browser_evidence.get("linked_frontend_enablement_gate_schema_version")
            == "command_center_live_light_frontend_enablement_gate.v1"
            and browser_evidence.get("linked_frontend_enablement_blocking_row_count") == 7
            and browser_evidence.get("linked_cache_first_polling_schema_version")
            == "command_center_runtime_cache_first_polling_contract.v1"
            and browser_evidence.get("linked_frontend_wiring_schema_version")
            == "command_center_search_quant_projection_frontend_wiring_acceptance_contract.v1"
            and browser_evidence.get("linked_external_silence_schema_version")
            == "command_center_runtime_external_silence_contract.v1"
            and set(browser_evidence_rows)
            == {
                "initial_cache_render_silent_browser_trace",
                "search_typing_silent_browser_trace",
                "safe_submit_single_local_post_browser_trace",
                "task_polling_and_success_refresh_browser_trace",
                "failure_recovery_last_good_cache_browser_trace",
                "frontend_provider_model_secret_silence_browser_trace",
                "research_only_boundaries_visible_browser_trace",
            }
            and [
                browser_evidence_rows.get(key, {}).get("evidence_order")
                for key in [
                    "initial_cache_render_silent_browser_trace",
                    "search_typing_silent_browser_trace",
                    "safe_submit_single_local_post_browser_trace",
                    "task_polling_and_success_refresh_browser_trace",
                    "failure_recovery_last_good_cache_browser_trace",
                    "frontend_provider_model_secret_silence_browser_trace",
                    "research_only_boundaries_visible_browser_trace",
                ]
            ]
            == [1, 2, 3, 4, 5, 6, 7]
            and "POST /api/bootstrap/live-startup before cache render completes"
            in _list(browser_evidence_rows.get("initial_cache_render_silent_browser_trace", {}).get(
                "forbidden_route_patterns"
            ))
            and "POST /api/candidate-radar/quant-projection"
            in _list(browser_evidence_rows.get("search_typing_silent_browser_trace", {}).get(
                "forbidden_route_patterns"
            ))
            and "GET /api/tasks/{task_id}"
            in _list(browser_evidence_rows.get("safe_submit_single_local_post_browser_trace", {}).get(
                "allowed_route_patterns"
            ))
            and "GET /api/candidate-radar/cache"
            in _list(browser_evidence_rows.get("task_polling_and_success_refresh_browser_trace", {}).get(
                "allowed_route_patterns"
            ))
            and "automatic retry POST"
            in _list(browser_evidence_rows.get("failure_recovery_last_good_cache_browser_trace", {}).get(
                "forbidden_route_patterns"
            ))
            and "Authorization/Bearer/token/key in packet"
            in _list(browser_evidence_rows.get("frontend_provider_model_secret_silence_browser_trace", {}).get(
                "forbidden_route_patterns"
            ))
            and "strategy action mutation route"
            in _list(browser_evidence_rows.get("research_only_boundaries_visible_browser_trace", {}).get(
                "forbidden_route_patterns"
            ))
            and all(
                row.get("required_before_frontend_enablement") is True
                and row.get("evidence_collected") is False
                and row.get("passed") is False
                and row.get("blocks_frontend_enablement") is True
                and row.get("requires_browser_network_trace") is True
                and row.get("frontend_wiring_required") is True
                and row.get("creates_task") is False
                and row.get("cache_get_creates_task") is False
                and row.get("react_render_creates_task") is False
                and row.get("react_render_direct_provider_calls") is False
                and row.get("provider_model_execution_requires_execution_request") is True
                and row.get("evidence_row_is_production_evidence") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in browser_evidence_rows.values()
            )
            and browser_evidence.get("contract_creates_task") is False
            and browser_evidence.get("contract_calls_provider_or_model") is False
            and browser_evidence.get("provider_execution_implemented") is False
            and browser_evidence.get("model_execution_implemented") is False
            and browser_evidence.get("contract_is_production_evidence") is False
            and browser_evidence.get("production_live_light_complete") is False
            and browser_evidence.get("external_calls_triggered") is False
            and browser_evidence.get("tushare_called") is False
            and browser_evidence.get("deepseek_called") is False
            and browser_evidence.get("github_called") is False
            and browser_evidence.get("contains_secret") is False
            and browser_evidence.get("does_not_execute_trades") is True
            and browser_evidence.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get("runtime_browser_evidence_contract_visible") is True
            and _dict(status.get("live_light")).get("runtime_browser_evidence_row_count") == 7
            and _dict(status.get("live_light")).get("runtime_browser_evidence_network_trace_required") is True
            and _dict(status.get("live_light")).get("runtime_browser_evidence_complete") is False
            and _dict(status.get("live_light")).get("runtime_browser_evidence_blocking_row_count") == 7
            and _dict(status.get("live_light")).get("runtime_browser_evidence_is_production_evidence") is False
            and _dict(status.get("policy")).get("runtime_browser_evidence_contract_visible") is True
            and _dict(status.get("policy")).get("runtime_browser_evidence_row_count") == 7
            and _dict(status.get("policy")).get("runtime_browser_evidence_network_trace_required") is True
            and _dict(status.get("policy")).get("runtime_browser_evidence_complete") is False
            and _dict(status.get("policy")).get("runtime_browser_evidence_blocking_row_count") == 7
            and _dict(status.get("policy")).get("runtime_browser_evidence_is_production_evidence") is False,
            f"browser_evidence={browser_evidence}",
        ),
        _row(
            "runtime_frontend_wiring_manifest_contract_lists_stage_04_touchpoints_without_implementation",
            frontend_wiring_manifest.get("schema_version")
            == "command_center_live_light_frontend_wiring_manifest.v1"
            and frontend_wiring_manifest.get("status")
            == "frontend_wiring_manifest_visible_implementation_pending"
            and frontend_wiring_manifest.get("mode") == "live_light"
            and frontend_wiring_manifest.get("target_stage_key") == "stage_04_frontend_nonblocking_wiring"
            and frontend_wiring_manifest.get("target_frontend_route") == "desktop/src/routes/CandidateRadar.tsx"
            and frontend_wiring_manifest.get("manifest_row_count") == 9
            and frontend_wiring_manifest.get("implementation_done_row_count") == 0
            and frontend_wiring_manifest.get("pending_manifest_row_count") == 9
            and frontend_wiring_manifest.get("target_components") == ["TaskLaunchReceipt", "TaskStatusPanel"]
            and frontend_wiring_manifest.get("target_client_helpers") == ["postCandidateRadarQuantProjection"]
            and frontend_wiring_manifest.get("required_local_routes")
            == [
                "GET /api/bootstrap/status",
                "GET /api/candidate-radar/cache",
                "POST /api/candidate-radar/quant-projection",
                "GET /api/tasks/{task_id}",
            ]
            and frontend_wiring_manifest.get("frontend_wiring_implemented") is False
            and frontend_wiring_manifest.get("frontend_acceptance_test_implemented") is False
            and frontend_wiring_manifest.get("browser_evidence_complete") is False
            and frontend_wiring_manifest.get("frontend_enablement_allowed") is False
            and frontend_wiring_manifest.get("manifest_can_enable_frontend") is False
            and frontend_wiring_manifest.get("linked_frontend_enablement_gate_schema_version")
            == "command_center_live_light_frontend_enablement_gate.v1"
            and frontend_wiring_manifest.get("linked_frontend_enablement_allowed") is False
            and frontend_wiring_manifest.get("linked_browser_evidence_schema_version")
            == "command_center_live_light_browser_evidence_contract.v1"
            and frontend_wiring_manifest.get("linked_browser_evidence_complete") is False
            and frontend_wiring_manifest.get("linked_cache_first_polling_schema_version")
            == "command_center_runtime_cache_first_polling_contract.v1"
            and frontend_wiring_manifest.get("linked_frontend_wiring_schema_version")
            == "command_center_search_quant_projection_frontend_wiring_acceptance_contract.v1"
            and set(frontend_wiring_manifest_rows)
            == {
                "bootstrap_status_mode_gate",
                "cache_first_initial_render_guard",
                "safe_submit_handler",
                "task_launch_receipt_binding",
                "task_status_panel_polling",
                "success_refresh_cache_and_status",
                "failure_recovery_last_good_cache",
                "provider_model_pending_boundary",
                "browser_evidence_hook",
            }
            and [
                frontend_wiring_manifest_rows.get(key, {}).get("manifest_order")
                for key in [
                    "bootstrap_status_mode_gate",
                    "cache_first_initial_render_guard",
                    "safe_submit_handler",
                    "task_launch_receipt_binding",
                    "task_status_panel_polling",
                    "success_refresh_cache_and_status",
                    "failure_recovery_last_good_cache",
                    "provider_model_pending_boundary",
                    "browser_evidence_hook",
                ]
            ]
            == [1, 2, 3, 4, 5, 6, 7, 8, 9]
            and frontend_wiring_manifest_rows.get("bootstrap_status_mode_gate", {}).get("required_route")
            == "GET /api/bootstrap/status"
            and frontend_wiring_manifest_rows.get("safe_submit_handler", {}).get(
                "target_helper_or_component"
            )
            == "postCandidateRadarQuantProjection"
            and frontend_wiring_manifest_rows.get("safe_submit_handler", {}).get(
                "local_post_allowed_after_behavior"
            )
            is True
            and frontend_wiring_manifest_rows.get("task_launch_receipt_binding", {}).get(
                "target_helper_or_component"
            )
            == "TaskLaunchReceipt"
            and frontend_wiring_manifest_rows.get("task_status_panel_polling", {}).get(
                "target_helper_or_component"
            )
            == "TaskStatusPanel"
            and "candidate_cache_refreshed"
            in _list(frontend_wiring_manifest_rows.get("success_refresh_cache_and_status", {}).get(
                "required_state"
            ))
            and "manual_retry_only"
            in _list(frontend_wiring_manifest_rows.get("failure_recovery_last_good_cache", {}).get(
                "required_state"
            ))
            and "no_action_mutation"
            in _list(frontend_wiring_manifest_rows.get("provider_model_pending_boundary", {}).get(
                "required_state"
            ))
            and "network_trace"
            in _list(frontend_wiring_manifest_rows.get("browser_evidence_hook", {}).get("required_state"))
            and frontend_wiring_manifest.get("required_manifest_keys")
            == [
                "bootstrap_status_mode_gate",
                "cache_first_initial_render_guard",
                "safe_submit_handler",
                "task_launch_receipt_binding",
                "task_status_panel_polling",
                "success_refresh_cache_and_status",
                "failure_recovery_last_good_cache",
                "provider_model_pending_boundary",
                "browser_evidence_hook",
            ]
            and all(
                row.get("required_before_frontend_enablement") is True
                and row.get("implementation_done") is False
                and row.get("browser_evidence_required") is True
                and row.get("creates_task_from_render") is False
                and row.get("creates_task_from_typing") is False
                and row.get("cache_get_creates_task") is False
                and row.get("react_render_direct_provider_calls") is False
                and row.get("frontend_provider_call_allowed") is False
                and row.get("frontend_model_call_allowed") is False
                and row.get("token_key_exposure_allowed") is False
                and row.get("provider_model_execution_requires_execution_request") is True
                and row.get("manifest_row_is_production_evidence") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in frontend_wiring_manifest_rows.values()
            )
            and frontend_wiring_manifest.get("contract_creates_task") is False
            and frontend_wiring_manifest.get("contract_calls_provider_or_model") is False
            and frontend_wiring_manifest.get("provider_execution_implemented") is False
            and frontend_wiring_manifest.get("model_execution_implemented") is False
            and frontend_wiring_manifest.get("contract_is_production_evidence") is False
            and frontend_wiring_manifest.get("production_live_light_complete") is False
            and frontend_wiring_manifest.get("external_calls_triggered") is False
            and frontend_wiring_manifest.get("tushare_called") is False
            and frontend_wiring_manifest.get("deepseek_called") is False
            and frontend_wiring_manifest.get("github_called") is False
            and frontend_wiring_manifest.get("contains_secret") is False
            and frontend_wiring_manifest.get("does_not_execute_trades") is True
            and frontend_wiring_manifest.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get(
                "runtime_frontend_wiring_manifest_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("runtime_frontend_wiring_manifest_row_count") == 9
            and _dict(status.get("live_light")).get("runtime_frontend_wiring_manifest_pending_row_count")
            == 9
            and _dict(status.get("live_light")).get("runtime_frontend_wiring_manifest_implemented")
            is False
            and _dict(status.get("live_light")).get(
                "runtime_frontend_wiring_manifest_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("runtime_frontend_wiring_manifest_contract_visible") is True
            and _dict(status.get("policy")).get("runtime_frontend_wiring_manifest_row_count") == 9
            and _dict(status.get("policy")).get("runtime_frontend_wiring_manifest_pending_row_count") == 9
            and _dict(status.get("policy")).get("runtime_frontend_wiring_manifest_implemented") is False
            and _dict(status.get("policy")).get("runtime_frontend_wiring_manifest_is_production_evidence")
            is False,
            f"frontend_wiring_manifest={frontend_wiring_manifest}",
        ),
        _row(
            "runtime_frontend_acceptance_runbook_contract_lists_stage_04_artifacts_without_collection",
            frontend_acceptance_runbook.get("schema_version")
            == "command_center_live_light_frontend_acceptance_runbook.v1"
            and frontend_acceptance_runbook.get("status")
            == "frontend_acceptance_runbook_visible_collection_pending"
            and frontend_acceptance_runbook.get("mode") == "live_light"
            and frontend_acceptance_runbook.get("target_stage_key") == "stage_04_frontend_nonblocking_wiring"
            and frontend_acceptance_runbook.get("target_frontend_route") == "desktop/src/routes/CandidateRadar.tsx"
            and frontend_acceptance_runbook.get("runbook_row_count") == 8
            and frontend_acceptance_runbook.get("completed_runbook_row_count") == 0
            and frontend_acceptance_runbook.get("pending_runbook_row_count") == 8
            and frontend_acceptance_runbook.get("required_runbook_keys")
            == [
                "prepare_cache_only_baseline",
                "prepare_live_light_config_probe",
                "capture_initial_cache_render_silence",
                "capture_search_typing_silence",
                "capture_safe_submit_task_lifecycle",
                "capture_success_refresh",
                "capture_failure_recovery",
                "capture_research_only_boundaries",
            ]
            and frontend_acceptance_runbook.get("required_artifacts")
            == [
                "cache_only_network_trace.json",
                "live_light_status_packet.json",
                "initial_cache_render_trace.json",
                "search_typing_trace.json",
                "safe_submit_task_lifecycle_trace.json",
                "success_refresh_trace.json",
                "failure_recovery_trace.json",
                "research_only_boundary_trace.json",
            ]
            and frontend_acceptance_runbook.get("browser_evidence_contract_required") is True
            and frontend_acceptance_runbook.get("frontend_wiring_manifest_required") is True
            and frontend_acceptance_runbook.get("frontend_enablement_allowed_after_runbook") is False
            and frontend_acceptance_runbook.get("runbook_can_promote_frontend_enablement") is False
            and frontend_acceptance_runbook.get("linked_frontend_enablement_gate_schema_version")
            == "command_center_live_light_frontend_enablement_gate.v1"
            and frontend_acceptance_runbook.get("linked_frontend_enablement_allowed") is False
            and frontend_acceptance_runbook.get("linked_browser_evidence_schema_version")
            == "command_center_live_light_browser_evidence_contract.v1"
            and frontend_acceptance_runbook.get("linked_browser_evidence_complete") is False
            and frontend_acceptance_runbook.get("linked_frontend_wiring_manifest_schema_version")
            == "command_center_live_light_frontend_wiring_manifest.v1"
            and frontend_acceptance_runbook.get("linked_frontend_wiring_manifest_pending_row_count") == 9
            and set(frontend_acceptance_runbook_rows)
            == {
                "prepare_cache_only_baseline",
                "prepare_live_light_config_probe",
                "capture_initial_cache_render_silence",
                "capture_search_typing_silence",
                "capture_safe_submit_task_lifecycle",
                "capture_success_refresh",
                "capture_failure_recovery",
                "capture_research_only_boundaries",
            }
            and [
                frontend_acceptance_runbook_rows.get(key, {}).get("runbook_order")
                for key in [
                    "prepare_cache_only_baseline",
                    "prepare_live_light_config_probe",
                    "capture_initial_cache_render_silence",
                    "capture_search_typing_silence",
                    "capture_safe_submit_task_lifecycle",
                    "capture_success_refresh",
                    "capture_failure_recovery",
                    "capture_research_only_boundaries",
                ]
            ]
            == [1, 2, 3, 4, 5, 6, 7, 8]
            and frontend_acceptance_runbook_rows.get("prepare_cache_only_baseline", {}).get(
                "required_artifact"
            )
            == "cache_only_network_trace.json"
            and frontend_acceptance_runbook_rows.get("prepare_live_light_config_probe", {}).get(
                "required_route"
            )
            == "GET /api/bootstrap/status"
            and frontend_acceptance_runbook_rows.get("capture_search_typing_silence", {}).get(
                "future_collection_local_post_expected"
            )
            is False
            and frontend_acceptance_runbook_rows.get("capture_safe_submit_task_lifecycle", {}).get(
                "future_collection_local_post_expected"
            )
            is True
            and frontend_acceptance_runbook_rows.get("capture_safe_submit_task_lifecycle", {}).get(
                "future_collection_local_post_route"
            )
            == "POST /api/candidate-radar/quant-projection"
            and "GET /api/tasks/{task_id}"
            in str(frontend_acceptance_runbook_rows.get("capture_failure_recovery", {}).get("required_route"))
            and "no provider/model/GitHub/trading calls"
            in str(
                frontend_acceptance_runbook_rows.get("capture_research_only_boundaries", {}).get(
                    "required_observation"
                )
            )
            and all(
                row.get("required_before_frontend_enablement") is True
                and row.get("runbook_step_complete") is False
                and row.get("artifact_collected") is False
                and row.get("blocks_frontend_enablement") is True
                and row.get("creates_task") is False
                and row.get("cache_get_creates_task") is False
                and row.get("react_render_creates_task") is False
                and row.get("frontend_provider_call_allowed") is False
                and row.get("frontend_model_call_allowed") is False
                and row.get("token_key_exposure_allowed") is False
                and row.get("provider_model_execution_requires_execution_request") is True
                and row.get("runbook_row_is_production_evidence") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in frontend_acceptance_runbook_rows.values()
            )
            and frontend_acceptance_runbook.get("frontend_wiring_implemented") is False
            and frontend_acceptance_runbook.get("browser_evidence_complete") is False
            and frontend_acceptance_runbook.get("contract_creates_task") is False
            and frontend_acceptance_runbook.get("contract_calls_provider_or_model") is False
            and frontend_acceptance_runbook.get("provider_execution_implemented") is False
            and frontend_acceptance_runbook.get("model_execution_implemented") is False
            and frontend_acceptance_runbook.get("contract_is_production_evidence") is False
            and frontend_acceptance_runbook.get("production_live_light_complete") is False
            and frontend_acceptance_runbook.get("external_calls_triggered") is False
            and frontend_acceptance_runbook.get("tushare_called") is False
            and frontend_acceptance_runbook.get("deepseek_called") is False
            and frontend_acceptance_runbook.get("github_called") is False
            and frontend_acceptance_runbook.get("contains_secret") is False
            and frontend_acceptance_runbook.get("does_not_execute_trades") is True
            and frontend_acceptance_runbook.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get(
                "runtime_frontend_acceptance_runbook_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("runtime_frontend_acceptance_runbook_row_count") == 8
            and _dict(status.get("live_light")).get("runtime_frontend_acceptance_runbook_pending_row_count")
            == 8
            and _dict(status.get("live_light")).get("runtime_frontend_acceptance_runbook_complete")
            is False
            and _dict(status.get("live_light")).get(
                "runtime_frontend_acceptance_runbook_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("runtime_frontend_acceptance_runbook_contract_visible")
            is True
            and _dict(status.get("policy")).get("runtime_frontend_acceptance_runbook_row_count") == 8
            and _dict(status.get("policy")).get("runtime_frontend_acceptance_runbook_pending_row_count") == 8
            and _dict(status.get("policy")).get("runtime_frontend_acceptance_runbook_complete") is False
            and _dict(status.get("policy")).get(
                "runtime_frontend_acceptance_runbook_is_production_evidence"
            )
            is False,
            f"frontend_acceptance_runbook={frontend_acceptance_runbook}",
        ),
        _row(
            "runtime_frontend_acceptance_artifact_contract_locks_redacted_stage_04_artifacts_without_collection",
            frontend_acceptance_artifact.get("schema_version")
            == "command_center_live_light_frontend_acceptance_artifact_contract.v1"
            and frontend_acceptance_artifact.get("status")
            == "frontend_acceptance_artifact_contract_visible_collection_pending"
            and frontend_acceptance_artifact.get("mode") == "live_light"
            and frontend_acceptance_artifact.get("target_stage_key") == "stage_04_frontend_nonblocking_wiring"
            and frontend_acceptance_artifact.get("target_frontend_route") == "desktop/src/routes/CandidateRadar.tsx"
            and frontend_acceptance_artifact.get("artifact_row_count") == 8
            and frontend_acceptance_artifact.get("collected_artifact_count") == 0
            and frontend_acceptance_artifact.get("pending_artifact_count") == 8
            and frontend_acceptance_artifact.get("artifact_collection_complete") is False
            and frontend_acceptance_artifact.get("required_artifact_keys")
            == [
                "cache_only_network_trace",
                "live_light_status_packet",
                "initial_cache_render_trace",
                "search_typing_trace",
                "safe_submit_task_lifecycle_trace",
                "success_refresh_trace",
                "failure_recovery_trace",
                "research_only_boundary_trace",
            ]
            and frontend_acceptance_artifact.get("required_artifact_files")
            == [
                "cache_only_network_trace.json",
                "live_light_status_packet.json",
                "initial_cache_render_trace.json",
                "search_typing_trace.json",
                "safe_submit_task_lifecycle_trace.json",
                "success_refresh_trace.json",
                "failure_recovery_trace.json",
                "research_only_boundary_trace.json",
            ]
            and frontend_acceptance_artifact.get("required_storage_target")
            == "local_redacted_stage_04_acceptance_artifacts"
            and frontend_acceptance_artifact.get("artifact_manifest_write_pending") is True
            and frontend_acceptance_artifact.get("artifact_hashes_required") is True
            and frontend_acceptance_artifact.get("artifact_redaction_review_required") is True
            and frontend_acceptance_artifact.get("artifact_redaction_review_complete") is False
            and frontend_acceptance_artifact.get("raw_trace_upload_allowed") is False
            and frontend_acceptance_artifact.get("frontend_packet_may_include_artifact_body") is False
            and frontend_acceptance_artifact.get("frontend_packet_may_include_artifact_hash") is True
            and frontend_acceptance_artifact.get("linked_frontend_acceptance_runbook_schema_version")
            == "command_center_live_light_frontend_acceptance_runbook.v1"
            and frontend_acceptance_artifact.get("linked_frontend_acceptance_runbook_pending_row_count") == 8
            and frontend_acceptance_artifact.get("linked_browser_evidence_schema_version")
            == "command_center_live_light_browser_evidence_contract.v1"
            and frontend_acceptance_artifact.get("linked_browser_evidence_complete") is False
            and set(frontend_acceptance_artifact_rows)
            == {
                "cache_only_network_trace",
                "live_light_status_packet",
                "initial_cache_render_trace",
                "search_typing_trace",
                "safe_submit_task_lifecycle_trace",
                "success_refresh_trace",
                "failure_recovery_trace",
                "research_only_boundary_trace",
            }
            and [
                frontend_acceptance_artifact_rows.get(key, {}).get("artifact_order")
                for key in [
                    "cache_only_network_trace",
                    "live_light_status_packet",
                    "initial_cache_render_trace",
                    "search_typing_trace",
                    "safe_submit_task_lifecycle_trace",
                    "success_refresh_trace",
                    "failure_recovery_trace",
                    "research_only_boundary_trace",
                ]
            ]
            == [1, 2, 3, 4, 5, 6, 7, 8]
            and frontend_acceptance_artifact_rows.get("cache_only_network_trace", {}).get(
                "linked_runbook_key"
            )
            == "prepare_cache_only_baseline"
            and frontend_acceptance_artifact_rows.get("live_light_status_packet", {}).get("artifact_kind")
            == "bootstrap_status_snapshot"
            and frontend_acceptance_artifact_rows.get("safe_submit_task_lifecycle_trace", {}).get(
                "artifact_kind"
            )
            == "browser_network_and_task_trace"
            and "trade_or_order_payload"
            in _list(frontend_acceptance_artifact_rows.get("research_only_boundary_trace", {}).get(
                "prohibited_content"
            ))
            and "token_like_values"
            in _list(frontend_acceptance_artifact_rows.get("research_only_boundary_trace", {}).get(
                "required_redaction"
            ))
            and all(
                row.get("storage_target") == "local_redacted_stage_04_acceptance_artifacts"
                and row.get("artifact_manifest_write_pending") is True
                and row.get("artifact_collected") is False
                and row.get("artifact_exists") is False
                and row.get("artifact_hash_recorded") is False
                and row.get("artifact_redaction_reviewed") is False
                and "local_route_method_status_timing" in _list(row.get("allowed_content"))
                and "credential_values" in _list(row.get("prohibited_content"))
                and "authorization_headers" in _list(row.get("required_redaction"))
                and row.get("required_before_frontend_enablement") is True
                and row.get("blocks_frontend_enablement") is True
                and row.get("artifact_row_is_production_evidence") is False
                and row.get("creates_task") is False
                and row.get("cache_get_creates_task") is False
                and row.get("react_render_creates_task") is False
                and row.get("frontend_provider_call_allowed") is False
                and row.get("frontend_model_call_allowed") is False
                and row.get("token_key_exposure_allowed") is False
                and row.get("provider_model_execution_requires_execution_request") is True
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in frontend_acceptance_artifact_rows.values()
            )
            and frontend_acceptance_artifact.get("frontend_wiring_implemented") is False
            and frontend_acceptance_artifact.get("browser_evidence_complete") is False
            and frontend_acceptance_artifact.get("contract_creates_task") is False
            and frontend_acceptance_artifact.get("contract_calls_provider_or_model") is False
            and frontend_acceptance_artifact.get("provider_execution_implemented") is False
            and frontend_acceptance_artifact.get("model_execution_implemented") is False
            and frontend_acceptance_artifact.get("contract_is_production_evidence") is False
            and frontend_acceptance_artifact.get("production_live_light_complete") is False
            and frontend_acceptance_artifact.get("external_calls_triggered") is False
            and frontend_acceptance_artifact.get("tushare_called") is False
            and frontend_acceptance_artifact.get("deepseek_called") is False
            and frontend_acceptance_artifact.get("github_called") is False
            and frontend_acceptance_artifact.get("contains_secret") is False
            and frontend_acceptance_artifact.get("does_not_execute_trades") is True
            and frontend_acceptance_artifact.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get(
                "runtime_frontend_acceptance_artifact_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("runtime_frontend_acceptance_artifact_row_count") == 8
            and _dict(status.get("live_light")).get("runtime_frontend_acceptance_artifact_pending_count")
            == 8
            and _dict(status.get("live_light")).get(
                "runtime_frontend_acceptance_artifact_redaction_review_required"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_frontend_acceptance_artifact_collection_complete"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_frontend_acceptance_artifact_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("runtime_frontend_acceptance_artifact_contract_visible")
            is True
            and _dict(status.get("policy")).get("runtime_frontend_acceptance_artifact_row_count") == 8
            and _dict(status.get("policy")).get("runtime_frontend_acceptance_artifact_pending_count") == 8
            and _dict(status.get("policy")).get(
                "runtime_frontend_acceptance_artifact_redaction_review_required"
            )
            is True
            and _dict(status.get("policy")).get("runtime_frontend_acceptance_artifact_collection_complete")
            is False
            and _dict(status.get("policy")).get(
                "runtime_frontend_acceptance_artifact_is_production_evidence"
            )
            is False,
            f"frontend_acceptance_artifact={frontend_acceptance_artifact}",
        ),
        _row(
            "runtime_frontend_enablement_promotion_contract_blocks_stage_04_until_evidence_chain_complete",
            frontend_enablement_promotion.get("schema_version")
            == "command_center_live_light_frontend_enablement_promotion_contract.v1"
            and frontend_enablement_promotion.get("status")
            == "frontend_enablement_promotion_visible_blocked"
            and frontend_enablement_promotion.get("mode") == "live_light"
            and frontend_enablement_promotion.get("target_stage_key") == "stage_04_frontend_nonblocking_wiring"
            and frontend_enablement_promotion.get("target_frontend_route") == "desktop/src/routes/CandidateRadar.tsx"
            and frontend_enablement_promotion.get("promotion_row_count") == 8
            and frontend_enablement_promotion.get("satisfied_promotion_row_count") == 0
            and frontend_enablement_promotion.get("blocking_promotion_row_count") == 8
            and frontend_enablement_promotion.get("required_promotion_keys")
            == [
                "frontend_wiring_manifest_implemented",
                "browser_evidence_collected",
                "acceptance_runbook_completed",
                "acceptance_artifacts_hashed_and_reviewed",
                "cache_only_baseline_passed",
                "safe_submit_lifecycle_passed",
                "failure_recovery_passed",
                "research_only_boundary_passed",
            ]
            and frontend_enablement_promotion.get("frontend_enablement_allowed") is False
            and frontend_enablement_promotion.get("promotion_can_enable_frontend") is False
            and frontend_enablement_promotion.get("browser_evidence_required") is True
            and frontend_enablement_promotion.get("artifact_redaction_review_required") is True
            and frontend_enablement_promotion.get("production_promotion_required_after_frontend_enablement")
            is True
            and frontend_enablement_promotion.get("linked_frontend_enablement_gate_schema_version")
            == "command_center_live_light_frontend_enablement_gate.v1"
            and frontend_enablement_promotion.get("linked_frontend_enablement_allowed") is False
            and frontend_enablement_promotion.get("linked_browser_evidence_schema_version")
            == "command_center_live_light_browser_evidence_contract.v1"
            and frontend_enablement_promotion.get("linked_browser_evidence_complete") is False
            and frontend_enablement_promotion.get("linked_frontend_wiring_manifest_schema_version")
            == "command_center_live_light_frontend_wiring_manifest.v1"
            and frontend_enablement_promotion.get("linked_frontend_wiring_manifest_pending_row_count") == 9
            and frontend_enablement_promotion.get("linked_frontend_acceptance_runbook_schema_version")
            == "command_center_live_light_frontend_acceptance_runbook.v1"
            and frontend_enablement_promotion.get("linked_frontend_acceptance_runbook_pending_row_count") == 8
            and frontend_enablement_promotion.get("linked_frontend_acceptance_artifact_schema_version")
            == "command_center_live_light_frontend_acceptance_artifact_contract.v1"
            and frontend_enablement_promotion.get("linked_frontend_acceptance_artifact_pending_count") == 8
            and set(frontend_enablement_promotion_rows)
            == {
                "frontend_wiring_manifest_implemented",
                "browser_evidence_collected",
                "acceptance_runbook_completed",
                "acceptance_artifacts_hashed_and_reviewed",
                "cache_only_baseline_passed",
                "safe_submit_lifecycle_passed",
                "failure_recovery_passed",
                "research_only_boundary_passed",
            }
            and [
                frontend_enablement_promotion_rows.get(key, {}).get("promotion_order")
                for key in [
                    "frontend_wiring_manifest_implemented",
                    "browser_evidence_collected",
                    "acceptance_runbook_completed",
                    "acceptance_artifacts_hashed_and_reviewed",
                    "cache_only_baseline_passed",
                    "safe_submit_lifecycle_passed",
                    "failure_recovery_passed",
                    "research_only_boundary_passed",
                ]
            ]
            == [1, 2, 3, 4, 5, 6, 7, 8]
            and frontend_enablement_promotion_rows.get("frontend_wiring_manifest_implemented", {}).get(
                "current_blocker"
            )
            == "frontend_wiring_manifest_implemented_false"
            and frontend_enablement_promotion_rows.get("browser_evidence_collected", {}).get(
                "required_source_contract"
            )
            == "runtime_browser_evidence_contract"
            and frontend_enablement_promotion_rows.get("acceptance_artifacts_hashed_and_reviewed", {}).get(
                "current_blocker"
            )
            == "pending_artifacts_or_redaction_review"
            and "one local POST"
            in str(frontend_enablement_promotion_rows.get("safe_submit_lifecycle_passed", {}).get(
                "required_evidence"
            ))
            and "no provider/model/GitHub/trading leakage"
            in str(frontend_enablement_promotion_rows.get("research_only_boundary_passed", {}).get(
                "required_evidence"
            ))
            and all(
                row.get("required_before_frontend_enablement") is True
                and row.get("promotion_criterion_met") is False
                and row.get("blocks_frontend_enablement") is True
                and row.get("creates_task") is False
                and row.get("cache_get_creates_task") is False
                and row.get("react_render_creates_task") is False
                and row.get("frontend_provider_call_allowed") is False
                and row.get("frontend_model_call_allowed") is False
                and row.get("token_key_exposure_allowed") is False
                and row.get("provider_model_execution_requires_execution_request") is True
                and row.get("promotion_row_is_production_evidence") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in frontend_enablement_promotion_rows.values()
            )
            and frontend_enablement_promotion.get("frontend_wiring_implemented") is False
            and frontend_enablement_promotion.get("browser_evidence_complete") is False
            and frontend_enablement_promotion.get("acceptance_runbook_complete") is False
            and frontend_enablement_promotion.get("acceptance_artifact_collection_complete") is False
            and frontend_enablement_promotion.get("artifact_redaction_review_complete") is False
            and frontend_enablement_promotion.get("contract_creates_task") is False
            and frontend_enablement_promotion.get("contract_calls_provider_or_model") is False
            and frontend_enablement_promotion.get("provider_execution_implemented") is False
            and frontend_enablement_promotion.get("model_execution_implemented") is False
            and frontend_enablement_promotion.get("contract_is_production_evidence") is False
            and frontend_enablement_promotion.get("production_live_light_complete") is False
            and frontend_enablement_promotion.get("external_calls_triggered") is False
            and frontend_enablement_promotion.get("tushare_called") is False
            and frontend_enablement_promotion.get("deepseek_called") is False
            and frontend_enablement_promotion.get("github_called") is False
            and frontend_enablement_promotion.get("contains_secret") is False
            and frontend_enablement_promotion.get("does_not_execute_trades") is True
            and frontend_enablement_promotion.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_promotion_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("runtime_frontend_enablement_promotion_row_count") == 8
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_promotion_blocking_row_count"
            )
            == 8
            and _dict(status.get("live_light")).get("runtime_frontend_enablement_promotion_allowed")
            is False
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_promotion_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get("runtime_frontend_enablement_promotion_contract_visible")
            is True
            and _dict(status.get("policy")).get("runtime_frontend_enablement_promotion_row_count") == 8
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_promotion_blocking_row_count"
            )
            == 8
            and _dict(status.get("policy")).get("runtime_frontend_enablement_promotion_allowed") is False
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_promotion_is_production_evidence"
            )
            is False,
            f"frontend_enablement_promotion={frontend_enablement_promotion}",
        ),
        _row(
            "runtime_frontend_enablement_release_switch_contract_defaults_off_and_requires_rollback",
            frontend_release_switch.get("schema_version")
            == "command_center_live_light_frontend_enablement_release_switch_contract.v1"
            and frontend_release_switch.get("status") == "frontend_enablement_release_switch_visible_default_off"
            and frontend_release_switch.get("mode") == "live_light"
            and frontend_release_switch.get("target_stage_key") == "stage_04_frontend_nonblocking_wiring"
            and frontend_release_switch.get("target_frontend_route") == "desktop/src/routes/CandidateRadar.tsx"
            and frontend_release_switch.get("release_switch_key") == "COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT"
            and frontend_release_switch.get("release_switch_row_count") == 7
            and frontend_release_switch.get("satisfied_release_switch_row_count") == 0
            and frontend_release_switch.get("blocking_release_switch_row_count") == 7
            and frontend_release_switch.get("required_release_switch_keys")
            == [
                "frontend_enablement_switch_default_off",
                "live_light_mode_required",
                "promotion_contract_required",
                "server_config_source_required",
                "rollback_on_evidence_regression",
                "research_only_boundary_required",
                "production_promotion_separate",
            ]
            and frontend_release_switch.get("release_switch_default_enabled") is False
            and frontend_release_switch.get("release_switch_configured") is True
            and frontend_release_switch.get("effective_frontend_enablement_allowed") is False
            and frontend_release_switch.get("frontend_enablement_allowed") is False
            and frontend_release_switch.get("release_switch_can_enable_frontend") is False
            and frontend_release_switch.get("release_switch_source_of_truth")
            == "server_config_layer_global_config_key_default_off"
            and frontend_release_switch.get("frontend_writeback_allowed") is False
            and frontend_release_switch.get("cache_only_manual_live_full_force_off") is True
            and frontend_release_switch.get("rollback_on_evidence_regression_required") is True
            and frontend_release_switch.get("rollback_if_artifact_redaction_fails") is True
            and frontend_release_switch.get("rollback_if_browser_evidence_missing") is True
            and frontend_release_switch.get("rollback_if_research_only_boundary_missing") is True
            and frontend_release_switch.get("linked_frontend_enablement_promotion_schema_version")
            == "command_center_live_light_frontend_enablement_promotion_contract.v1"
            and frontend_release_switch.get("linked_frontend_enablement_promotion_blocking_row_count") == 8
            and frontend_release_switch.get("linked_frontend_enablement_promotion_allowed") is False
            and frontend_release_switch.get("requires_live_light_mode") is True
            and frontend_release_switch.get("requires_promotion_allowed") is True
            and frontend_release_switch.get("requires_browser_evidence_complete") is True
            and frontend_release_switch.get("requires_artifact_redaction_review_complete") is True
            and frontend_release_switch.get("requires_operator_opt_in") is True
            and frontend_release_switch.get("production_promotion_required_after_switch") is True
            and set(frontend_release_switch_rows)
            == {
                "frontend_enablement_switch_default_off",
                "live_light_mode_required",
                "promotion_contract_required",
                "server_config_source_required",
                "rollback_on_evidence_regression",
                "research_only_boundary_required",
                "production_promotion_separate",
            }
            and [
                frontend_release_switch_rows.get(key, {}).get("release_switch_order")
                for key in [
                    "frontend_enablement_switch_default_off",
                    "live_light_mode_required",
                    "promotion_contract_required",
                    "server_config_source_required",
                    "rollback_on_evidence_regression",
                    "research_only_boundary_required",
                    "production_promotion_separate",
                ]
            ]
            == [1, 2, 3, 4, 5, 6, 7]
            and frontend_release_switch_rows.get("frontend_enablement_switch_default_off", {}).get(
                "current_blocker"
            )
            == "release_switch_default_off_until_promotion_allowed"
            and frontend_release_switch_rows.get("server_config_source_required", {}).get("required_evidence")
            == "frontend cannot write enablement state or override server mode"
            and "forces off"
            in str(frontend_release_switch_rows.get("rollback_on_evidence_regression", {}).get(
                "required_evidence"
            ))
            and frontend_release_switch_rows.get("production_promotion_separate", {}).get("current_blocker")
            == "production_promotion_pending"
            and all(
                row.get("required_before_frontend_enablement") is True
                and row.get("release_switch_criterion_met") is False
                and row.get("blocks_frontend_enablement") is True
                and row.get("effective_frontend_enablement_allowed") is False
                and row.get("creates_task") is False
                and row.get("cache_get_creates_task") is False
                and row.get("react_render_creates_task") is False
                and row.get("frontend_provider_call_allowed") is False
                and row.get("frontend_model_call_allowed") is False
                and row.get("frontend_writeback_allowed") is False
                and row.get("token_key_exposure_allowed") is False
                and row.get("provider_model_execution_requires_execution_request") is True
                and row.get("release_switch_row_is_production_evidence") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in frontend_release_switch_rows.values()
            )
            and frontend_release_switch.get("frontend_wiring_implemented") is False
            and frontend_release_switch.get("browser_evidence_complete") is False
            and frontend_release_switch.get("acceptance_artifact_collection_complete") is False
            and frontend_release_switch.get("artifact_redaction_review_complete") is False
            and frontend_release_switch.get("contract_creates_task") is False
            and frontend_release_switch.get("contract_calls_provider_or_model") is False
            and frontend_release_switch.get("provider_execution_implemented") is False
            and frontend_release_switch.get("model_execution_implemented") is False
            and frontend_release_switch.get("contract_is_production_evidence") is False
            and frontend_release_switch.get("production_live_light_complete") is False
            and frontend_release_switch.get("external_calls_triggered") is False
            and frontend_release_switch.get("tushare_called") is False
            and frontend_release_switch.get("deepseek_called") is False
            and frontend_release_switch.get("github_called") is False
            and frontend_release_switch.get("contains_secret") is False
            and frontend_release_switch.get("does_not_execute_trades") is True
            and frontend_release_switch.get("does_not_modify_strategy_action") is True
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_release_switch_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get("runtime_frontend_enablement_release_switch_row_count")
            == 7
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_release_switch_blocking_row_count"
            )
            == 7
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_release_switch_effective_allowed"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_release_switch_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_release_switch_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get("runtime_frontend_enablement_release_switch_row_count") == 7
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_release_switch_blocking_row_count"
            )
            == 7
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_release_switch_effective_allowed"
            )
            is False
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_release_switch_is_production_evidence"
            )
            is False,
            f"frontend_release_switch={frontend_release_switch}",
        ),
        _row(
            "runtime_frontend_enablement_config_promotion_tracks_global_key_default_off_without_fallback",
            frontend_enablement_config_promotion.get("schema_version")
            == "command_center_live_light_frontend_enablement_config_promotion_contract.v1"
            and frontend_enablement_config_promotion.get("status")
            == "frontend_enablement_config_promotion_visible_global_config_promoted_default_off_validation_pending"
            and frontend_enablement_config_promotion.get("mode") == "live_light"
            and frontend_enablement_config_promotion.get("config_key")
            == "COMMAND_CENTER_LIVE_FRONTEND_ENABLEMENT"
            and frontend_enablement_config_promotion.get("target_stage_key")
            == "stage_04_frontend_nonblocking_wiring"
            and frontend_enablement_config_promotion.get("target_frontend_route")
            == "desktop/src/routes/CandidateRadar.tsx"
            and frontend_enablement_config_promotion.get("promotion_step_count") == 6
            and frontend_enablement_config_promotion.get("completed_promotion_step_count") == 2
            and frontend_enablement_config_promotion.get("pending_promotion_step_count") == 4
            and frontend_enablement_config_promotion.get("required_promotion_step_keys")
            == [
                "add_global_config_allowlist_key",
                "prove_default_false_read_path",
                "bind_to_promotion_contract",
                "bind_to_release_switch_rollback",
                "block_frontend_writeback",
                "rerun_validation_gate",
            ]
            and frontend_enablement_config_promotion.get("default_value_safe") is False
            and frontend_enablement_config_promotion.get("configured_value_safe") is True
            and frontend_enablement_config_promotion.get("effective_value_safe") is False
            and frontend_enablement_config_promotion.get("bootstrap_local_env_fallback_allowed") is False
            and frontend_enablement_config_promotion.get("bootstrap_local_env_fallback_count") == 0
            and frontend_enablement_config_promotion.get("global_config_allowlist_promoted") is True
            and frontend_enablement_config_promotion.get("global_config_allowlist_promotion_pending") is False
            and frontend_enablement_config_promotion.get("current_cycle_modifies_global_config_file") is False
            and frontend_enablement_config_promotion.get("requires_future_config_py_file_scope") is False
            and frontend_enablement_config_promotion.get("config_py_update_pending") is False
            and frontend_enablement_config_promotion.get("effective_frontend_enablement_allowed") is False
            and frontend_enablement_config_promotion.get("release_switch_default_enabled") is False
            and frontend_enablement_config_promotion.get("frontend_enablement_allowed") is False
            and frontend_enablement_config_promotion.get("frontend_writeback_allowed") is False
            and frontend_enablement_config_promotion.get("status_endpoint_writeback_allowed") is False
            and frontend_enablement_config_promotion.get("linked_runtime_config_ownership_schema_version")
            == "command_center_bootstrap_runtime_config_ownership_invariant.v1"
            and frontend_enablement_config_promotion.get("linked_runtime_config_ownership_row_count") == 13
            and frontend_enablement_config_promotion.get("linked_frontend_enablement_ownership_status")
            == "server_config_layer_owned_global_config_allowlist_promoted_default_off"
            and frontend_enablement_config_promotion.get("linked_frontend_enablement_current_read_path")
            == "global_config_layer_default_false_release_switch_guard"
            and frontend_enablement_config_promotion.get("linked_frontend_enablement_target_read_path")
            == "global_config_layer_only"
            and frontend_enablement_config_promotion.get(
                "linked_frontend_enablement_global_config_allowlist_promotion_pending"
            )
            is False
            and frontend_enablement_config_promotion.get(
                "linked_frontend_enablement_bootstrap_local_env_fallback_available"
            )
            is False
            and frontend_enablement_config_promotion.get("linked_release_switch_schema_version")
            == "command_center_live_light_frontend_enablement_release_switch_contract.v1"
            and frontend_enablement_config_promotion.get("linked_release_switch_row_count") == 7
            and frontend_enablement_config_promotion.get("linked_release_switch_blocking_row_count") == 7
            and frontend_enablement_config_promotion.get("linked_release_switch_effective_allowed") is False
            and set(frontend_enablement_config_promotion_rows)
            == {
                "add_global_config_allowlist_key",
                "prove_default_false_read_path",
                "bind_to_promotion_contract",
                "bind_to_release_switch_rollback",
                "block_frontend_writeback",
                "rerun_validation_gate",
            }
            and [
                frontend_enablement_config_promotion_rows.get(key, {}).get("step_order")
                for key in [
                    "add_global_config_allowlist_key",
                    "prove_default_false_read_path",
                    "bind_to_promotion_contract",
                    "bind_to_release_switch_rollback",
                    "block_frontend_writeback",
                    "rerun_validation_gate",
                ]
            ]
            == [1, 2, 3, 4, 5, 6]
            and frontend_enablement_config_promotion_rows.get(
                "add_global_config_allowlist_key", {}
            ).get("current_blocker")
            == "none_global_config_allowlist_key_present"
            and "no bootstrap-local env fallback"
            in str(
                frontend_enablement_config_promotion_rows.get(
                    "prove_default_false_read_path", {}
                ).get("required_evidence")
            )
            and frontend_enablement_config_promotion_rows.get(
                "bind_to_release_switch_rollback", {}
            ).get("current_blocker")
            == "release_switch_rollback_contract_pending"
            and frontend_enablement_config_promotion_rows.get("block_frontend_writeback", {}).get(
                "target_file"
            )
            == "desktop/src/routes/CandidateRadar.tsx"
            and frontend_enablement_config_promotion_rows.get(
                "add_global_config_allowlist_key", {}
            ).get("status")
            == "passed_global_config_allowlist_key_present"
            and frontend_enablement_config_promotion_rows.get(
                "prove_default_false_read_path", {}
            ).get("status")
            == "passed_default_false_global_config_read_path"
            and frontend_enablement_config_promotion_rows.get(
                "add_global_config_allowlist_key", {}
            ).get("promotion_step_complete")
            is True
            and frontend_enablement_config_promotion_rows.get(
                "prove_default_false_read_path", {}
            ).get("promotion_step_complete")
            is True
            and frontend_enablement_config_promotion_rows.get(
                "add_global_config_allowlist_key", {}
            ).get("blocks_frontend_enablement")
            is False
            and frontend_enablement_config_promotion_rows.get(
                "prove_default_false_read_path", {}
            ).get("blocks_frontend_enablement")
            is False
            and all(
                frontend_enablement_config_promotion_rows.get(key, {}).get("status")
                == "pending_frontend_enablement_validation_scope"
                and frontend_enablement_config_promotion_rows.get(key, {}).get(
                    "promotion_step_complete"
                )
                is False
                and frontend_enablement_config_promotion_rows.get(key, {}).get(
                    "blocks_frontend_enablement"
                )
                is True
                for key in [
                    "bind_to_promotion_contract",
                    "bind_to_release_switch_rollback",
                    "block_frontend_writeback",
                    "rerun_validation_gate",
                ]
            )
            and all(
                row.get("config_row_is_production_evidence") is False
                and row.get("current_cycle_modifies_global_config_file") is False
                and row.get("bootstrap_local_env_fallback_allowed") is False
                and row.get("frontend_writeback_allowed") is False
                and row.get("status_endpoint_writeback_allowed") is False
                and row.get("cache_get_creates_task") is False
                and row.get("react_render_creates_task") is False
                and row.get("fastapi_startup_creates_task") is False
                and row.get("search_typing_creates_task") is False
                and row.get("external_calls_triggered") is False
                and row.get("tushare_called") is False
                and row.get("deepseek_called") is False
                and row.get("github_called") is False
                and row.get("contains_secret") is False
                and row.get("does_not_execute_trades") is True
                and row.get("does_not_modify_strategy_action") is True
                for row in frontend_enablement_config_promotion_rows.values()
            )
            and frontend_enablement_config_promotion.get("cache_get_creates_task") is False
            and frontend_enablement_config_promotion.get("react_render_creates_task") is False
            and frontend_enablement_config_promotion.get("fastapi_startup_creates_task") is False
            and frontend_enablement_config_promotion.get("search_typing_creates_task") is False
            and frontend_enablement_config_promotion.get("contract_creates_task") is False
            and frontend_enablement_config_promotion.get("contract_calls_provider_or_model") is False
            and frontend_enablement_config_promotion.get("provider_execution_implemented") is False
            and frontend_enablement_config_promotion.get("model_execution_implemented") is False
            and frontend_enablement_config_promotion.get("external_calls_triggered") is False
            and frontend_enablement_config_promotion.get("tushare_called") is False
            and frontend_enablement_config_promotion.get("deepseek_called") is False
            and frontend_enablement_config_promotion.get("github_called") is False
            and frontend_enablement_config_promotion.get("contains_secret") is False
            and frontend_enablement_config_promotion.get("credential_values_exposed") is False
            and frontend_enablement_config_promotion.get("credential_env_key_names_included") is False
            and frontend_enablement_config_promotion.get("does_not_execute_trades") is True
            and frontend_enablement_config_promotion.get("does_not_modify_strategy_action") is True
            and frontend_enablement_config_promotion.get("contract_is_production_evidence") is False
            and frontend_enablement_config_promotion.get("production_config_complete") is False
            and frontend_enablement_config_promotion.get("production_live_light_complete") is False
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_config_promotion_contract_visible"
            )
            is True
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_config_promotion_step_count"
            )
            == 6
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_config_promotion_pending_step_count"
            )
            == 4
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_config_promotion_effective_allowed"
            )
            is False
            and _dict(status.get("live_light")).get(
                "runtime_frontend_enablement_config_promotion_is_production_evidence"
            )
            is False
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_config_promotion_contract_visible"
            )
            is True
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_config_promotion_step_count"
            )
            == 6
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_config_promotion_pending_step_count"
            )
            == 4
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_config_promotion_effective_allowed"
            )
            is False
            and _dict(status.get("policy")).get(
                "runtime_frontend_enablement_config_promotion_is_production_evidence"
            )
            is False,
            f"frontend_enablement_config_promotion={frontend_enablement_config_promotion}",
        ),
        _row(
            "live_light_local_fallback_contract_degrades_safely_without_production_evidence",
            fallback_contract.get("schema_version") == "command_center_live_light_local_fallback_contract.v1"
            and fallback_contract.get("status") == "local_fallback_contract_visible_runtime_evidence_pending"
            and fallback_contract.get("mode") == "live_light"
            and fallback_contract.get("fallback_surface") == "post_task_worker_or_local_pipeline_only"
            and fallback_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and fallback_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and fallback_contract.get("cache_first_render_required") is True
            and fallback_contract.get("fallback_after_provider_error_allowed") is True
            and fallback_contract.get("fallback_after_model_error_allowed") is True
            and fallback_contract.get("fallback_from_get_cache_allowed") is False
            and fallback_contract.get("fallback_from_react_render_allowed") is False
            and fallback_contract.get("fastapi_startup_fallback_refresh_allowed") is False
            and fallback_contract.get("uses_last_good_cache_allowed") is True
            and fallback_contract.get("last_good_cache_lineage_required") is True
            and fallback_contract.get("stale_cache_label_required") is True
            and fallback_contract.get("provider_gap_visible_required") is True
            and fallback_contract.get("safe_error_visible_required") is True
            and fallback_contract.get("rate_limit_skipped_state_visible_required") is True
            and fallback_contract.get("fallback_may_refresh_local_factor_from_existing_cache") is True
            and fallback_contract.get("fallback_may_refresh_next_session_from_existing_cache") is True
            and fallback_contract.get("fallback_may_synthesize_provider_rows") is False
            and fallback_contract.get("fallback_may_synthesize_model_output") is False
            and fallback_contract.get("fallback_is_provider_evidence") is False
            and fallback_contract.get("fallback_is_model_correctness_evidence") is False
            and fallback_contract.get("fallback_is_production_evidence") is False
            and fallback_contract.get("fallback_may_overwrite_price") is False
            and fallback_contract.get("fallback_may_overwrite_holding") is False
            and fallback_contract.get("fallback_may_overwrite_factor") is False
            and fallback_contract.get("fallback_may_overwrite_operation_zones") is False
            and fallback_contract.get("fallback_may_modify_strategy_action") is False
            and fallback_contract.get("fallback_may_create_radar_buy_instruction") is False
            and _dict(status.get("policy")).get("live_light_local_fallback_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_local_fallback_uses_last_good_cache_allowed") is True
            and _dict(status.get("policy")).get("live_light_local_fallback_stale_cache_label_required") is True
            and _dict(status.get("policy")).get("live_light_local_fallback_provider_gap_visible_required")
            is True
            and _dict(status.get("policy")).get("live_light_local_fallback_is_production_evidence") is False
            and fallback_contract.get("browser_runtime_evidence_complete") is False
            and fallback_contract.get("performance_trace_evidence_complete") is False
            and fallback_contract.get("provider_execution_implemented") is False
            and fallback_contract.get("model_execution_implemented") is False
            and fallback_contract.get("external_calls_triggered") is False
            and fallback_contract.get("tushare_called") is False
            and fallback_contract.get("deepseek_called") is False
            and fallback_contract.get("github_called") is False
            and fallback_contract.get("contains_secret") is False
            and fallback_contract.get("does_not_execute_trades") is True
            and fallback_contract.get("does_not_modify_strategy_action") is True,
            f"fallback_contract={fallback_contract}",
        ),
        _row(
            "live_light_cache_lineage_contract_requires_durable_safe_output_lineage",
            lineage_contract.get("schema_version") == "command_center_live_light_cache_lineage_contract.v1"
            and lineage_contract.get("status") == "cache_lineage_contract_visible_runtime_evidence_pending"
            and lineage_contract.get("mode") == "live_light"
            and {
                "source_task_id",
                "source_task_type",
                "source_route",
                "source_mode",
                "source_scope_hash",
                "provider_call_ledger_ids",
                "model_ledger_ids",
                "input_packet_keys",
                "output_packet_keys",
                "cache_source",
                "storage_backend",
                "local_fetched_at",
                "freshness_state",
                "data_date",
            }.issubset(set(_list(lineage_contract.get("required_lineage_fields"))))
            and lineage_contract.get("lineage_required_for_factor_quant_hub_cache") is True
            and lineage_contract.get("lineage_required_for_next_session_cache") is True
            and lineage_contract.get("lineage_required_for_deepseek_explanation_cache") is True
            and lineage_contract.get("sqlite_meta_visibility_required") is True
            and lineage_contract.get("snapshot_visibility_allowed_as_fallback") is True
            and lineage_contract.get("memory_only_lineage_is_durable_evidence") is False
            and lineage_contract.get("cache_get_may_write_lineage") is False
            and lineage_contract.get("react_render_may_write_lineage") is False
            and lineage_contract.get("fastapi_startup_may_write_lineage") is False
            and lineage_contract.get("lineage_written_by_post_task_only") is True
            and lineage_contract.get("lineage_must_reference_call_ledger") is True
            and lineage_contract.get("lineage_must_reference_model_ledger_for_deepseek") is True
            and lineage_contract.get("lineage_must_include_safe_error_when_degraded") is True
            and lineage_contract.get("lineage_must_include_provider_gap_when_degraded") is True
            and lineage_contract.get("lineage_must_exclude_credential_values") is True
            and lineage_contract.get("lineage_must_exclude_env_key_names") is True
            and lineage_contract.get("lineage_must_exclude_raw_prompt_or_output") is True
            and lineage_contract.get("lineage_may_overwrite_price") is False
            and lineage_contract.get("lineage_may_overwrite_holding") is False
            and lineage_contract.get("lineage_may_overwrite_factor") is False
            and lineage_contract.get("lineage_may_overwrite_operation_zones") is False
            and lineage_contract.get("lineage_may_modify_strategy_action") is False
            and lineage_contract.get("lineage_is_provider_execution_evidence") is False
            and lineage_contract.get("lineage_is_model_correctness_evidence") is False
            and lineage_contract.get("lineage_is_production_evidence_without_real_ledgers") is False
            and _dict(status.get("policy")).get("live_light_cache_lineage_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_cache_lineage_required_for_outputs") is True
            and _dict(status.get("policy")).get("live_light_cache_lineage_written_by_post_task_only") is True
            and _dict(status.get("policy")).get("live_light_memory_only_lineage_is_durable_evidence") is False
            and lineage_contract.get("provider_execution_implemented") is False
            and lineage_contract.get("model_execution_implemented") is False
            and lineage_contract.get("external_calls_triggered") is False
            and lineage_contract.get("tushare_called") is False
            and lineage_contract.get("deepseek_called") is False
            and lineage_contract.get("github_called") is False
            and lineage_contract.get("contains_secret") is False
            and lineage_contract.get("does_not_execute_trades") is True
            and lineage_contract.get("does_not_modify_strategy_action") is True,
            f"lineage_contract={lineage_contract}",
        ),
        _row(
            "live_light_output_surface_contract_binds_factor_next_deepseek_cache_outputs_without_writes",
            output_surface_contract.get("schema_version") == "command_center_live_light_output_surface_contract.v1"
            and output_surface_contract.get("status") == "output_surface_contract_visible_runtime_evidence_pending"
            and output_surface_contract.get("mode") == "live_light"
            and output_surface_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and output_surface_contract.get("task_status_route") == "GET /api/tasks/{task_id}"
            and output_surface_contract.get("required_output_surfaces")
            == ["factor_quant_hub_cache", "next_session_cache", "deepseek_explanation_cache"]
            and {
                "command_center_factor_quant_hub_packet",
                "command_center_next_session_projection_packet",
                "command_center_factor_quant_hub_packet:data.deepseek_explanation",
            }.issubset(set(_list(output_surface_contract.get("output_packet_keys"))))
            and output_surface_contract.get("output_surface_count") == 3
            and {
                "factor_quant_hub_cache",
                "next_session_cache",
                "deepseek_explanation_cache",
            }.issubset(
                {
                    str(row.get("surface_key") or "")
                    for row in _list(output_surface_contract.get("output_surface_rows"))
                    if isinstance(row, dict)
                }
            )
            and all(
                _dict(row).get("allowed_writer") == "post_task_worker_or_local_pipeline_only"
                and _dict(row).get("lineage_required") is True
                and _dict(row).get("call_ledger_required") is True
                and _dict(row).get("freshness_state_required") is True
                and _dict(row).get("provider_gap_visible_required") is True
                and _dict(row).get("safe_error_visible_required") is True
                and _dict(row).get("cache_get_may_write") is False
                and _dict(row).get("react_render_may_write") is False
                and _dict(row).get("fastapi_startup_may_write") is False
                and _dict(row).get("may_overwrite_price") is False
                and _dict(row).get("may_overwrite_holding") is False
                and _dict(row).get("may_overwrite_factor") is False
                and _dict(row).get("may_overwrite_operation_zones") is False
                and _dict(row).get("may_modify_strategy_action") is False
                and _dict(row).get("production_output_ready") is False
                for row in _list(output_surface_contract.get("output_surface_rows"))
                if isinstance(row, dict)
            )
            and any(
                _dict(row).get("surface_key") == "factor_quant_hub_cache"
                and _dict(row).get("packet_key") == "command_center_factor_quant_hub_packet"
                and _dict(row).get("source_stage") == "factor_quant_hub_cache_refresh"
                for row in _list(output_surface_contract.get("output_surface_rows"))
                if isinstance(row, dict)
            )
            and any(
                _dict(row).get("surface_key") == "next_session_cache"
                and _dict(row).get("packet_key") == "command_center_next_session_projection_packet"
                and _dict(row).get("source_stage") == "next_session_cache_refresh"
                for row in _list(output_surface_contract.get("output_surface_rows"))
                if isinstance(row, dict)
            )
            and any(
                _dict(row).get("surface_key") == "deepseek_explanation_cache"
                and _dict(row).get("packet_key") == "command_center_factor_quant_hub_packet"
                and _dict(row).get("nested_path") == "data.deepseek_explanation"
                and _dict(row).get("source_stage") == "deepseek_pro_explanation"
                and _dict(row).get("model_ledger_required") is True
                and set(_list(_dict(row).get("allowed_output_fields")))
                == {
                    "summary",
                    "support_notes",
                    "suppress_notes",
                    "conflict_notes",
                    "missing_data_notes",
                    "discipline_notes",
                }
                and _dict(row).get("fallback_may_synthesize_model_output") is False
                and _dict(row).get("deepseek_is_data_source") is False
                for row in _list(output_surface_contract.get("output_surface_rows"))
                if isinstance(row, dict)
            )
            and output_surface_contract.get("output_written_by_post_task_only") is True
            and output_surface_contract.get("cache_get_may_write_output") is False
            and output_surface_contract.get("react_render_may_write_output") is False
            and output_surface_contract.get("fastapi_startup_may_write_output") is False
            and output_surface_contract.get("all_outputs_require_lineage") is True
            and output_surface_contract.get("all_outputs_require_safe_error_or_provider_gap_when_degraded") is True
            and output_surface_contract.get("factor_quant_hub_cache_required") is True
            and output_surface_contract.get("next_session_cache_required") is True
            and output_surface_contract.get("deepseek_explanation_optional_after_data_ready") is True
            and output_surface_contract.get("deepseek_output_fields_whitelisted") is True
            and output_surface_contract.get("deepseek_is_data_source") is False
            and output_surface_contract.get("fallback_may_synthesize_provider_rows") is False
            and output_surface_contract.get("fallback_may_synthesize_model_output") is False
            and output_surface_contract.get("may_overwrite_price") is False
            and output_surface_contract.get("may_overwrite_holding") is False
            and output_surface_contract.get("may_overwrite_factor") is False
            and output_surface_contract.get("may_overwrite_operation_zones") is False
            and output_surface_contract.get("may_modify_strategy_action") is False
            and output_surface_contract.get("radar_candidate_is_buy_instruction") is False
            and _dict(status.get("live_light")).get("output_surface_contract_visible") is True
            and _dict(status.get("live_light")).get("output_surface_count") == 3
            and _dict(status.get("live_light")).get("factor_quant_hub_output_surface_required") is True
            and _dict(status.get("live_light")).get("next_session_output_surface_required") is True
            and _dict(status.get("live_light")).get("deepseek_explanation_output_surface_governed") is True
            and _dict(status.get("live_light")).get("output_surface_written_by_post_task_only") is True
            and _dict(status.get("live_light")).get("output_surface_contract_is_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_output_surface_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_output_surface_written_by_post_task_only") is True
            and _dict(status.get("policy")).get("live_light_output_surface_count") == 3
            and _dict(status.get("policy")).get("live_light_factor_quant_hub_output_surface_required") is True
            and _dict(status.get("policy")).get("live_light_next_session_output_surface_required") is True
            and _dict(status.get("policy")).get("live_light_deepseek_explanation_output_surface_governed") is True
            and _dict(status.get("policy")).get("live_light_output_surface_contract_is_production_evidence") is False
            and output_surface_contract.get("provider_execution_implemented") is False
            and output_surface_contract.get("model_execution_implemented") is False
            and output_surface_contract.get("output_surface_contract_is_execution_evidence") is False
            and output_surface_contract.get("output_surface_contract_is_production_evidence") is False
            and output_surface_contract.get("external_calls_triggered") is False
            and output_surface_contract.get("tushare_called") is False
            and output_surface_contract.get("deepseek_called") is False
            and output_surface_contract.get("github_called") is False
            and output_surface_contract.get("contains_secret") is False
            and output_surface_contract.get("does_not_execute_trades") is True
            and output_surface_contract.get("does_not_modify_strategy_action") is True,
            f"output_surface_contract={output_surface_contract}",
        ),
        _row(
            "live_light_runtime_budget_contract_caps_provider_model_runtime_without_execution",
            budget_contract.get("schema_version") == "command_center_live_light_runtime_budget_contract.v1"
            and budget_contract.get("status") == "runtime_budget_contract_visible_execution_pending"
            and budget_contract.get("mode") == "live_light"
            and budget_contract.get("task_route") == "POST /api/bootstrap/live-startup"
            and budget_contract.get("acceptance_dry_run_route")
            == "POST /api/bootstrap/provider-model-acceptance-dry-run"
            and budget_contract.get("execution_request_route") == "POST /api/bootstrap/provider-model-execution-request"
            and budget_contract.get("allowed_scope") == "current_target_holdings_watchlist_searched_symbol_light_only"
            and budget_contract.get("symbol_limit") == 2
            and budget_contract.get("rate_limit_seconds") == 600
            and budget_contract.get("allowed_live_light_tushare_apis")
            == ["trade_cal_if_needed", "daily", "daily_basic", "moneyflow"]
            and budget_contract.get("allowed_acceptance_apis") == ["trade_cal", "daily", "daily_basic", "moneyflow"]
            and budget_contract.get("allowed_deepseek_purposes") == ["explain_after_data_ready"]
            and budget_contract.get("provider_budget_surface") == "post_task_worker_only"
            and budget_contract.get("model_budget_surface") == "post_data_ready_model_step_only"
            and budget_contract.get("max_provider_api_count_per_task") == 4
            and budget_contract.get("max_model_call_count_per_task") == 1
            and budget_contract.get("max_background_task_count_per_rate_window") == 1
            and budget_contract.get("cache_hit_skips_provider_call_allowed") is True
            and budget_contract.get("input_hash_dedupe_required") is True
            and budget_contract.get("scope_hash_dedupe_required") is True
            and budget_contract.get("model_input_hash_dedupe_required") is True
            and budget_contract.get("rate_limit_skip_must_reuse_existing_task") is True
            and budget_contract.get("budget_exceeded_status") == "skipped_budget_exceeded_no_external_call"
            and budget_contract.get("rate_limited_status") == "skipped_due_to_rate_limit_reused_existing_task"
            and budget_contract.get("credential_missing_status") == "blocked_missing_credentials_no_external_call"
            and budget_contract.get("permission_denied_status") == "provider_permission_denied_safe_error"
            and budget_contract.get("empty_result_status") == "provider_empty_result_not_verified"
            and budget_contract.get("no_record_status") == "provider_no_record_not_negative_evidence"
            and {
                "scope_hash",
                "input_hash",
                "cache_hit",
                "provider_api_count",
                "model_call_count",
                "token_usage",
                "model_cost_estimate",
                "budget_status",
                "rate_limit_status",
                "safe_error",
            }.issubset(set(_list(budget_contract.get("required_budget_ledger_fields"))))
            and budget_contract.get("token_usage_record_required") is True
            and budget_contract.get("model_cost_estimate_record_required") is True
            and budget_contract.get("budget_status_record_required") is True
            and set(_list(budget_contract.get("budget_status_values")))
            == {"within_budget", "skipped_budget_exceeded", "unknown_until_runtime"}
            and budget_contract.get("budget_state_visible_required") is True
            and budget_contract.get("token_usage_visible_safe_summary_only") is True
            and budget_contract.get("raw_prompt_or_output_budget_log_allowed") is False
            and budget_contract.get("credential_value_budget_log_allowed") is False
            and budget_contract.get("env_key_name_budget_log_allowed") is False
            and budget_contract.get("deepseek_is_data_source") is False
            and budget_contract.get("deepseek_may_overwrite_price") is False
            and budget_contract.get("deepseek_may_overwrite_holding") is False
            and budget_contract.get("deepseek_may_overwrite_factor") is False
            and budget_contract.get("deepseek_may_overwrite_operation_zones") is False
            and budget_contract.get("deepseek_may_modify_strategy_action") is False
            and _dict(status.get("live_light")).get("runtime_budget_contract_visible") is True
            and _dict(status.get("live_light")).get("runtime_budget_symbol_limit") == 2
            and _dict(status.get("live_light")).get("runtime_budget_rate_limit_seconds") == 600
            and _dict(status.get("live_light")).get("runtime_budget_enforcement_implemented") is False
            and _dict(status.get("live_light")).get("runtime_budget_contract_is_production_evidence") is False
            and _dict(status.get("policy")).get("live_light_runtime_budget_contract_visible") is True
            and _dict(status.get("policy")).get("live_light_runtime_budget_token_usage_required") is True
            and _dict(status.get("policy")).get("live_light_runtime_budget_cache_hit_skips_provider_call_allowed")
            is True
            and _dict(status.get("policy")).get("live_light_runtime_budget_input_hash_dedupe_required") is True
            and _dict(status.get("policy")).get("live_light_runtime_budget_rate_limit_reuses_existing_task") is True
            and _dict(status.get("policy")).get("live_light_runtime_budget_enforcement_implemented") is False
            and _dict(status.get("policy")).get("live_light_runtime_budget_contract_is_production_evidence")
            is False
            and budget_contract.get("provider_execution_implemented") is False
            and budget_contract.get("model_execution_implemented") is False
            and budget_contract.get("budget_enforcement_implemented") is False
            and budget_contract.get("budget_contract_is_execution_evidence") is False
            and budget_contract.get("budget_contract_is_production_evidence") is False
            and budget_contract.get("external_calls_triggered") is False
            and budget_contract.get("tushare_called") is False
            and budget_contract.get("deepseek_called") is False
            and budget_contract.get("github_called") is False
            and budget_contract.get("contains_secret") is False
            and budget_contract.get("does_not_execute_trades") is True
            and budget_contract.get("does_not_modify_strategy_action") is True,
            f"budget_contract={budget_contract}",
        ),
        _row(
            "live_light_activation_receipt_blocks_provider_model_completion",
            activation.get("mode") == "live_light"
            and activation.get("tushare_on_open") is True
            and activation.get("deepseek_on_open") is True
            and activation.get("ready_for_provider_execution_design") is True
            and activation.get("ready_for_provider_execution") is False
            and activation.get("ready_for_model_execution") is False
            and activation.get("provider_execution_implemented") is False
            and activation.get("model_execution_implemented") is False
            and activation.get("production_live_light_complete") is False
            and activation.get("external_calls_triggered") is False
            and activation.get("tushare_called") is False
            and activation.get("deepseek_called") is False
            and activation.get("github_called") is False
            and activation_rows.get("tushare_stage_requires_provider_adapter", {}).get("status")
            == "pending_provider_execution_implementation"
            and activation_rows.get("deepseek_stage_requires_model_execution_gate", {}).get("status")
            == "pending_model_execution_implementation"
            and activation_rows.get("production_activation_pending", {}).get("status")
            == "blocked_until_explicit_provider_and_model_acceptance",
            f"activation={activation}",
        ),
        _row(
            "live_light_provider_model_acceptance_runbook_lists_real_evidence_without_running",
            runbook.get("mode") == "live_light"
            and runbook.get("tushare_on_open") is True
            and runbook.get("deepseek_on_open") is True
            and runbook.get("phase_count") == 10
            and runbook.get("provider_phase_count") == 2
            and runbook.get("model_phase_count") == 1
            and runbook.get("external_call_expected_phase_count") == 3
            and runbook.get("ready_for_acceptance_design") is True
            and runbook.get("ready_for_user_approved_acceptance_task") is False
            and runbook.get("external_calls_triggered") is False
            and runbook.get("tushare_called") is False
            and runbook.get("deepseek_called") is False
            and runbook.get("github_called") is False
            and acceptance_rows.get("tushare_trade_cal_acceptance_sample", {}).get(
                "external_call_expected_when_executed"
            )
            is True
            and acceptance_rows.get("tushare_light_fact_acceptance_sample", {}).get(
                "external_call_expected_when_executed"
            )
            is True
            and acceptance_rows.get("deepseek_pro_model_acceptance_sample", {}).get(
                "external_call_expected_when_executed"
            )
            is True
            and acceptance_rows.get("ui_nonblocking_runtime_acceptance", {}).get("status")
            == "pending_browser_or_runtime_evidence",
            f"runbook={runbook}",
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
            and stages_by_key.get("trade_cal_if_needed", {}).get("external_execution_profile")
            == "light_provider_model"
            and stages_by_key.get("tushare_light_refresh", {}).get("external_execution_profile")
            == "light_provider_model"
            and stages_by_key.get("trade_cal_if_needed", {}).get("profile_stage_allowed") is True
            and stages_by_key.get("tushare_light_refresh", {}).get("profile_stage_allowed") is True
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
            and stages_by_key.get("deepseek_pro_explanation", {}).get("external_execution_profile")
            == "light_provider_model"
            and stages_by_key.get("deepseek_pro_explanation", {}).get("profile_stage_allowed") is True
            and model.get("model") == "contract-live-pro"
            and model.get("external_execution_profile") == "light_provider_model"
            and model.get("profile_stage_allowed") is True
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
            and first_ledger.get("local_compute_handoff_status")
            == "local_compute_handoff_visible_execution_pending"
            and first_ledger.get("local_compute_handoff_mode_gate") == "live_light"
            and first_ledger.get("local_compute_handoff_mode_gate_satisfied") is True
            and first_ledger.get("local_compute_handoff_source_switch_satisfied") is True
            and first_ledger.get("local_compute_handoff_inactive_reason") == ""
            and first_ledger.get("local_compute_handoff_row_count") == 3
            and first_ledger.get("local_compute_handoff_enabled_row_count") == 3
            and first_ledger.get("local_compute_handoff_executed_row_count") == 0
            and first_ledger.get("local_compute_handoff_output_written_row_count") == 0
            and first_ledger.get("local_compute_handoff_ledger_executes_local_compute") is False
            and first_ledger.get("local_compute_handoff_ledger_writes_output") is False
            and first_ledger.get("local_compute_handoff_ledger_is_execution_evidence") is False
            and first_ledger.get("local_compute_handoff_ledger_is_production_evidence") is False
            and _dict(first_ledger.get("request_params_safe")).get("local_compute_handoff_status")
            == "local_compute_handoff_visible_execution_pending"
            and _dict(first_ledger.get("request_params_safe")).get("local_compute_handoff_inactive_reason") == ""
            and first_ledger.get("planned_provider_stage_count") == 2
            and first_ledger.get("planned_model_stage_count") == 1
            and first_ledger.get("external_execution_profile") == "light_provider_model"
            and first_ledger.get("external_execution_profile_provider_stage_allowed") is True
            and first_ledger.get("external_execution_profile_model_stage_allowed") is True
            and first_ledger.get("external_execution_profile_executor_implemented") is False
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
            and last_repeated.get("local_compute_handoff_status")
            == "local_compute_handoff_visible_execution_pending"
            and last_repeated.get("local_compute_handoff_mode_gate") == "live_light"
            and last_repeated.get("local_compute_handoff_mode_gate_satisfied") is True
            and last_repeated.get("local_compute_handoff_source_switch_satisfied") is True
            and last_repeated.get("local_compute_handoff_inactive_reason") == ""
            and last_repeated.get("local_compute_handoff_row_count") == 3
            and last_repeated.get("local_compute_handoff_enabled_row_count") == 3
            and last_repeated.get("local_compute_handoff_executed_row_count") == 0
            and last_repeated.get("local_compute_handoff_output_written_row_count") == 0
            and last_repeated.get("local_compute_handoff_ledger_executes_local_compute") is False
            and last_repeated.get("local_compute_handoff_ledger_writes_output") is False
            and last_repeated.get("local_compute_handoff_ledger_is_execution_evidence") is False
            and last_repeated.get("local_compute_handoff_ledger_is_production_evidence") is False
            and last_repeated.get("planned_provider_stage_count") == 2
            and last_repeated.get("planned_model_stage_count") == 1
            and last_repeated.get("external_execution_profile") == "light_provider_model"
            and last_repeated.get("external_execution_profile_provider_stage_allowed") is True
            and last_repeated.get("external_execution_profile_model_stage_allowed") is True
            and last_repeated.get("external_calls_triggered") is False,
            f"task_id={task.get('task_id')} repeated_step={repeated.get('current_step')}",
        ),
        _row(
            "live_light_latest_bootstrap_task_status_surface_replays_task_without_creating_task",
            latest_bootstrap_status.get("schema_version")
            == "command_center_live_light_latest_bootstrap_task_status.v1"
            and latest_bootstrap_status.get("status") == "latest_bootstrap_task_visible_rate_limited_reuse"
            and latest_bootstrap_status.get("lookup_source") == "task_service.list_task_statuses"
            and latest_bootstrap_status.get("lookup_creates_task") is False
            and latest_bootstrap_status.get("route") == "POST /api/bootstrap/live-startup"
            and latest_bootstrap_status.get("route_implemented") is True
            and latest_bootstrap_status.get("task_found") is True
            and latest_bootstrap_status.get("task_id") == task.get("task_id")
            and latest_bootstrap_status.get("task_status") == "success"
            and latest_bootstrap_status.get("current_step") == "live_bootstrap_skipped_due_to_rate_limit"
            and latest_bootstrap_status.get("output_packet_key") == "command_center_live_bootstrap_packet"
            and latest_bootstrap_status.get("storage_source") in {"memory_and_sqlite", "sqlite_meta"}
            and latest_bootstrap_status.get("durable_task_visible") is True
            and latest_bootstrap_status.get("memory_only_task_is_durable_evidence") is False
            and latest_bootstrap_status.get("bootstrap_mode") == "live_light"
            and latest_bootstrap_status.get("source") == "bootstrap_runtime_contract"
            and latest_bootstrap_status.get("symbol_count") == 2
            and latest_bootstrap_status.get("symbol_limit") == 2
            and latest_bootstrap_status.get("truncated_by_symbol_limit") is True
            and latest_bootstrap_status.get("sources_enabled") is True
            and latest_bootstrap_status.get("tushare_on_open") is True
            and latest_bootstrap_status.get("deepseek_on_open") is True
            and latest_bootstrap_status.get("external_execution_profile") == "light_provider_model"
            and latest_bootstrap_status.get("external_execution_profile_provider_stage_allowed") is True
            and latest_bootstrap_status.get("external_execution_profile_model_stage_allowed") is True
            and latest_bootstrap_status.get("external_execution_profile_executor_implemented") is False
            and latest_bootstrap_status.get("bootstrap_stage_count") == 9
            and latest_bootstrap_status.get("model_ledger_preview_count") == 1
            and latest_bootstrap_status.get("local_compute_handoff_visible") is True
            and latest_bootstrap_status.get("local_compute_handoff_schema_version")
            == "command_center_live_bootstrap_local_compute_handoff.v1"
            and latest_bootstrap_status.get("local_compute_handoff_status")
            == "local_compute_handoff_visible_execution_pending"
            and latest_bootstrap_status.get("local_compute_handoff_mode_gate") == "live_light"
            and latest_bootstrap_status.get("local_compute_handoff_mode_gate_satisfied") is True
            and latest_bootstrap_status.get("local_compute_handoff_source_switch_satisfied") is True
            and latest_bootstrap_status.get("local_compute_handoff_inactive_reason") == ""
            and latest_bootstrap_status.get("local_compute_handoff_row_count") == 3
            and latest_bootstrap_status.get("local_compute_handoff_enabled_row_count") == 3
            and latest_bootstrap_status.get("local_compute_handoff_executed_row_count") == 0
            and latest_bootstrap_status.get("local_compute_handoff_output_written_row_count") == 0
            and latest_bootstrap_status.get("local_compute_handoff_future_local_routes")
            == ["POST /api/factor-quant/run-light", "POST /api/next-session/generate"]
            and latest_bootstrap_status.get("local_compute_handoff_future_task_types")
            == ["build_next_session_projection", "run_factor_light"]
            and latest_bootstrap_status.get("local_compute_handoff_output_packet_keys")
            == ["command_center_factor_quant_hub_packet", "command_center_next_session_projection_packet"]
            and latest_bootstrap_status.get("local_compute_handoff_input_packet_keys")
            == ["command_center_factor_quant_hub_packet", "command_center_next_session_projection_packet"]
            and latest_bootstrap_status.get("local_compute_handoff_lineage_contract_schema_version")
            == "command_center_live_light_cache_lineage_contract.v1"
            and latest_bootstrap_status.get("local_compute_handoff_lineage_write_policy")
            == "post_task_worker_or_local_pipeline_only"
            and latest_bootstrap_status.get("local_compute_handoff_lineage_required_field_count")
            == len(required_handoff_lineage_fields)
            and latest_bootstrap_status.get("local_compute_handoff_lineage_written_row_count") == 0
            and latest_bootstrap_status.get("local_compute_handoff_cache_get_may_write_lineage") is False
            and latest_bootstrap_status.get("local_compute_handoff_react_render_may_write_lineage") is False
            and latest_bootstrap_status.get("local_compute_handoff_fastapi_startup_may_write_lineage") is False
            and latest_bootstrap_status.get("local_compute_handoff_lineage_is_execution_evidence") is False
            and latest_bootstrap_status.get("local_compute_handoff_lineage_is_production_evidence") is False
            and latest_bootstrap_status.get("local_compute_handoff_replay_executes_local_compute") is False
            and latest_bootstrap_status.get("local_compute_handoff_replay_writes_output") is False
            and latest_bootstrap_status.get("local_compute_handoff_replay_is_execution_evidence") is False
            and latest_bootstrap_status.get("local_compute_handoff_replay_is_production_evidence") is False
            and latest_bootstrap_status.get("planned_provider_stage_count") == 2
            and latest_bootstrap_status.get("planned_model_stage_count") == 1
            and latest_bootstrap_status.get("actual_provider_execution_count") == 0
            and latest_bootstrap_status.get("actual_model_call_count") == 0
            and latest_bootstrap_status.get("rate_limit_reused_existing_task") is True
            and latest_bootstrap_status.get("call_ledger_count") == 2
            and latest_bootstrap_status.get("task_success_is_provider_model_evidence") is False
            and latest_bootstrap_status.get("task_success_is_production_evidence") is False
            and latest_bootstrap_status.get("provider_execution_implemented") is False
            and latest_bootstrap_status.get("model_execution_implemented") is False
            and latest_bootstrap_status.get("provider_model_execution_implemented") is False
            and latest_bootstrap_status.get("production_live_light_complete") is False
            and latest_bootstrap_status.get("is_production_evidence") is False
            and latest_bootstrap_status.get("external_calls_triggered") is False
            and latest_bootstrap_status.get("tushare_called") is False
            and latest_bootstrap_status.get("deepseek_called") is False
            and latest_bootstrap_status.get("github_called") is False
            and latest_bootstrap_status.get("credential_values_exposed") is False
            and latest_bootstrap_status.get("env_key_names_included") is False
            and latest_bootstrap_status.get("does_not_execute_trades") is True
            and latest_bootstrap_status.get("does_not_modify_strategy_action") is True
            and latest_bootstrap_live_light.get("latest_bootstrap_task_status_visible") is True
            and latest_bootstrap_live_light.get("latest_bootstrap_task_found") is True
            and latest_bootstrap_live_light.get("latest_bootstrap_task_status")
            == "latest_bootstrap_task_visible_rate_limited_reuse"
            and latest_bootstrap_live_light.get("latest_bootstrap_task_id") == task.get("task_id")
            and latest_bootstrap_live_light.get("latest_bootstrap_task_current_step")
            == "live_bootstrap_skipped_due_to_rate_limit"
            and latest_bootstrap_live_light.get("latest_bootstrap_task_durable_visible") is True
            and latest_bootstrap_live_light.get("latest_bootstrap_task_lookup_creates_task") is False
            and latest_bootstrap_live_light.get("latest_bootstrap_task_success_is_provider_model_evidence") is False
            and latest_bootstrap_live_light.get("latest_bootstrap_task_is_production_evidence") is False
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_visible") is True
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_status")
            == "local_compute_handoff_visible_execution_pending"
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_mode_gate") == "live_light"
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_mode_gate_satisfied") is True
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_source_switch_satisfied")
            is True
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_inactive_reason") == ""
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_row_count") == 3
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_enabled_row_count") == 3
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_executed_row_count") == 0
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_output_written_row_count") == 0
            and latest_bootstrap_live_light.get(
                "latest_bootstrap_local_compute_handoff_lineage_required_field_count"
            )
            == len(required_handoff_lineage_fields)
            and latest_bootstrap_live_light.get(
                "latest_bootstrap_local_compute_handoff_lineage_written_row_count"
            )
            == 0
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_lineage_write_policy")
            == "post_task_worker_or_local_pipeline_only"
            and latest_bootstrap_live_light.get(
                "latest_bootstrap_local_compute_handoff_cache_get_may_write_lineage"
            )
            is False
            and latest_bootstrap_live_light.get(
                "latest_bootstrap_local_compute_handoff_react_render_may_write_lineage"
            )
            is False
            and latest_bootstrap_live_light.get(
                "latest_bootstrap_local_compute_handoff_fastapi_startup_may_write_lineage"
            )
            is False
            and latest_bootstrap_live_light.get(
                "latest_bootstrap_local_compute_handoff_lineage_is_execution_evidence"
            )
            is False
            and latest_bootstrap_live_light.get(
                "latest_bootstrap_local_compute_handoff_lineage_is_production_evidence"
            )
            is False
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_executes_compute") is False
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_writes_output") is False
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_is_execution_evidence")
            is False
            and latest_bootstrap_live_light.get("latest_bootstrap_local_compute_handoff_is_production_evidence")
            is False
            and latest_bootstrap_policy.get("live_light_latest_bootstrap_task_status_visible") is True
            and latest_bootstrap_policy.get("live_light_latest_bootstrap_task_lookup_creates_task") is False
            and latest_bootstrap_policy.get("live_light_latest_bootstrap_task_success_is_provider_model_evidence")
            is False
            and latest_bootstrap_policy.get("live_light_latest_bootstrap_task_is_production_evidence") is False
            and latest_bootstrap_policy.get("live_light_latest_bootstrap_local_compute_handoff_visible") is True
            and latest_bootstrap_policy.get("live_light_latest_bootstrap_local_compute_handoff_lookup_creates_task")
            is False
            and latest_bootstrap_policy.get("live_light_latest_bootstrap_local_compute_handoff_executes_compute")
            is False
            and latest_bootstrap_policy.get("live_light_latest_bootstrap_local_compute_handoff_writes_output") is False
            and latest_bootstrap_policy.get(
                "live_light_latest_bootstrap_local_compute_handoff_is_execution_evidence"
            )
            is False
            and latest_bootstrap_policy.get(
                "live_light_latest_bootstrap_local_compute_handoff_is_production_evidence"
            )
            is False
            and "DROP_TS" not in latest_bootstrap_status_text
            and "DROP_DS" not in latest_bootstrap_status_text
            and '"api_key"' not in latest_bootstrap_status_text
            and '"token"' not in latest_bootstrap_status_text,
            f"latest_bootstrap_status={latest_bootstrap_status}",
        ),
        _row(
            "live_light_provider_model_acceptance_dry_run_records_preflight_without_external_call",
            dry_run.get("task_type") == "command_center_live_bootstrap_provider_model_acceptance_dry_run"
            and dry_run.get("current_step")
            == "provider_model_acceptance_dry_run_recorded_user_approval_no_external_call"
            and dry_payload.get("selected_apis") == ["trade_cal", "daily", "moneyflow"]
            and dry_payload.get("ignored_apis") == ["fina_indicator"]
            and dry_summary.get("phase_count") == 10
            and dry_summary.get("selected_provider_phase_count") == 2
            and dry_summary.get("selected_model_phase_count") == 1
            and dry_summary.get("status") == "acceptance_dry_run_ready_execution_pending"
            and dry_summary.get("credential_presence_status") == "all_required_env_keys_present_no_values_read"
            and dry_summary.get("credential_required_provider_count") == 2
            and dry_summary.get("credential_present_provider_count") == 2
            and dry_summary.get("credential_missing_provider_count") == 0
            and dry_summary.get("blocked_by_missing_credentials") is False
            and dry_summary.get("ready_for_user_approved_real_acceptance") is True
            and dry_summary.get("allowed_next_step")
            == "explicit_user_confirmed_real_provider_model_acceptance_task_pending_implementation"
            and dry_summary.get("real_acceptance_task_implemented") is False
            and dry_summary.get("acceptance_scope_hash") == dry_scope_ticket.get("scope_hash")
            and dry_summary.get("acceptance_scope_hash_short") == dry_scope_ticket.get("scope_hash_short")
            and dry_summary.get("real_acceptance_preflight_receipt_status")
            == "real_acceptance_preflight_blocked_execution_not_implemented"
            and dry_summary.get("real_acceptance_preflight_ready_to_execute") is False
            and int(dry_summary.get("real_acceptance_preflight_blocking_row_count") or 0) > 0
            and dry_scope_ticket.get("scope_hash_algorithm") == "sha256"
            and len(str(dry_scope_ticket.get("scope_hash") or "")) == 64
            and len(str(dry_scope_ticket.get("scope_hash_short") or "")) == 16
            and dry_scope_ticket.get("credential_values_included") is False
            and dry_scope_ticket.get("env_key_names_included") is False
            and _dict(dry_scope_ticket.get("scope_hash_input")).get("symbols") == ["000001.SZ", "000002.SZ"]
            and _dict(dry_scope_ticket.get("scope_hash_input")).get("selected_apis")
            == ["trade_cal", "daily", "moneyflow"]
            and "real provider call ledger" in _list(dry_summary.get("missing_evidence_items"))
            and "skip credential presence gate" in _list(dry_summary.get("not_allowed_next_steps"))
            and dry_summary.get("credential_values_read") is False
            and dry_summary.get("credential_values_exposed") is False
            and credential_rows.get("tushare", {}).get("status") == "present_no_value_read"
            and credential_rows.get("deepseek", {}).get("status") == "present_no_value_read"
            and credential_rows.get("tushare", {}).get("values_read") is False
            and credential_rows.get("deepseek", {}).get("values_exposed") is False
            and dry_rows.get("tushare_trade_cal_acceptance_sample", {}).get("status")
            == "dry_run_ready_provider_execution_not_called"
            and dry_rows.get("deepseek_pro_model_acceptance_sample", {}).get("status")
            == "dry_run_ready_model_execution_not_called"
            and dry_rows.get("server_secret_preflight", {}).get("status")
            == "dry_run_secret_presence_checked_no_values_exposed"
            and dry_real_preflight.get("status")
            == "real_acceptance_preflight_blocked_execution_not_implemented"
            and dry_real_preflight.get("dry_run_ready_for_user_approved_real_acceptance") is True
            and dry_real_preflight.get("acceptance_scope_hash") == dry_scope_ticket.get("scope_hash")
            and dry_real_preflight.get("ready_to_design_real_task") is True
            and dry_real_preflight.get("ready_to_execute_real_task") is False
            and dry_real_preflight.get("provider_execution_implemented") is False
            and dry_real_preflight.get("model_execution_implemented") is False
            and dry_real_preflight.get("browser_runtime_evidence_complete") is False
            and dry_real_preflight.get("ledger_redaction_review_complete") is False
            and dry_real_preflight.get("production_live_light_complete") is False
            and dry_real_preflight.get("external_calls_triggered") is False
            and dry_real_preflight.get("tushare_called") is False
            and dry_real_preflight.get("deepseek_called") is False
            and dry_real_preflight_rows.get("scope_ticket_binds_user_confirmation", {}).get("status") == "passed"
            and dry_real_preflight_rows.get("credential_presence_ready_without_value_exposure", {}).get("status") == "passed"
            and dry_real_preflight_rows.get("provider_execution_task_not_implemented", {}).get("status")
            == "blocked_real_tushare_execution_pending"
            and dry_real_preflight_rows.get("model_execution_task_not_implemented", {}).get("status")
            == "blocked_real_deepseek_execution_pending"
            and first_dry_ledger.get("call_status") == "local_acceptance_dry_run_recorded_no_external_call"
            and first_dry_ledger.get("external_calls_triggered") is False
            and first_dry_ledger.get("tushare_called") is False
            and first_dry_ledger.get("deepseek_called") is False
            and "DROP_TS" not in dry_text
            and "DROP_DS" not in dry_text
            and '"api_key"' not in dry_text
            and '"token"' not in dry_text,
            f"dry_step={dry_run.get('current_step')} summary={dry_summary}",
        ),
        _row(
            "live_light_latest_acceptance_dry_run_status_surface_replays_receipt_without_creating_task",
            latest_dry_run_status.get("schema_version")
            == "command_center_live_light_latest_acceptance_dry_run_status.v1"
            and latest_dry_run_status.get("status") == "latest_acceptance_dry_run_receipt_visible_ready"
            and latest_dry_run_status.get("lookup_source") == "task_service.list_task_statuses"
            and latest_dry_run_status.get("lookup_creates_task") is False
            and latest_dry_run_status.get("route") == "POST /api/bootstrap/provider-model-acceptance-dry-run"
            and latest_dry_run_status.get("route_implemented") is True
            and latest_dry_run_status.get("receipt_found") is True
            and latest_dry_run_status.get("task_id") == dry_run.get("task_id")
            and latest_dry_run_status.get("task_status") == "success"
            and latest_dry_run_status.get("current_step")
            == "provider_model_acceptance_dry_run_recorded_user_approval_no_external_call"
            and latest_dry_run_status.get("output_packet_key")
            == "command_center_live_bootstrap_provider_model_acceptance_dry_run_packet"
            and latest_dry_run_status.get("storage_source") in {"memory_and_sqlite", "sqlite_meta"}
            and latest_dry_run_status.get("durable_receipt_visible") is True
            and latest_dry_run_status.get("memory_only_receipt_is_durable_evidence") is False
            and latest_dry_run_status.get("receipt_status") == "acceptance_dry_run_ready_execution_pending"
            and latest_dry_run_status.get("acceptance_scope_hash_short") == dry_scope_ticket.get("scope_hash_short")
            and latest_dry_run_status.get("acceptance_scope_hash_algorithm") == "sha256"
            and latest_dry_run_status.get("user_approved") is True
            and latest_dry_run_status.get("selected_apis") == ["trade_cal", "daily", "moneyflow"]
            and latest_dry_run_status.get("ignored_apis") == ["fina_indicator"]
            and latest_dry_run_status.get("include_tushare") is True
            and latest_dry_run_status.get("include_deepseek") is True
            and latest_dry_run_status.get("credential_presence_status")
            == "all_required_env_keys_present_no_values_read"
            and latest_dry_run_status.get("credential_preflight_ready") is True
            and latest_dry_run_status.get("credential_required_provider_count") == 2
            and latest_dry_run_status.get("credential_present_provider_count") == 2
            and latest_dry_run_status.get("credential_missing_provider_count") == 0
            and latest_dry_run_status.get("dry_run_ready_for_execution_request") is True
            and latest_dry_run_status.get("ready_for_user_approved_real_acceptance") is True
            and latest_dry_run_status.get("selected_provider_phase_count") == 2
            and latest_dry_run_status.get("selected_model_phase_count") == 1
            and latest_dry_run_status.get("real_acceptance_preflight_status")
            == "real_acceptance_preflight_blocked_execution_not_implemented"
            and latest_dry_run_status.get("real_acceptance_preflight_ready_to_execute") is False
            and latest_dry_run_status.get("provider_model_task_created") is False
            and latest_dry_run_status.get("provider_model_task_dispatched") is False
            and latest_dry_run_status.get("provider_execution_implemented") is False
            and latest_dry_run_status.get("model_execution_implemented") is False
            and latest_dry_run_status.get("provider_model_execution_implemented") is False
            and latest_dry_run_status.get("production_live_light_complete") is False
            and latest_dry_run_status.get("is_production_evidence") is False
            and latest_dry_run_status.get("external_calls_triggered") is False
            and latest_dry_run_status.get("tushare_called") is False
            and latest_dry_run_status.get("deepseek_called") is False
            and latest_dry_run_status.get("github_called") is False
            and latest_dry_run_status.get("credential_values_exposed") is False
            and latest_dry_run_status.get("env_key_names_included") is False
            and latest_dry_run_status.get("does_not_execute_trades") is True
            and latest_dry_run_status.get("does_not_modify_strategy_action") is True
            and latest_dry_run_live_light.get("latest_acceptance_dry_run_found") is True
            and latest_dry_run_live_light.get("latest_acceptance_dry_run_status")
            == "latest_acceptance_dry_run_receipt_visible_ready"
            and latest_dry_run_live_light.get("latest_acceptance_dry_run_task_id") == dry_run.get("task_id")
            and latest_dry_run_live_light.get("latest_acceptance_dry_run_ready_for_execution_request") is True
            and latest_dry_run_live_light.get("latest_acceptance_dry_run_durable_receipt_visible") is True
            and latest_dry_run_live_light.get("latest_acceptance_dry_run_lookup_creates_task") is False
            and latest_dry_run_live_light.get("latest_acceptance_dry_run_is_production_evidence") is False
            and latest_dry_run_policy.get("live_light_latest_acceptance_dry_run_status_visible") is True
            and latest_dry_run_policy.get("live_light_latest_acceptance_dry_run_lookup_creates_task") is False
            and latest_dry_run_policy.get("live_light_latest_acceptance_dry_run_is_production_evidence") is False
            and "DROP_TS" not in latest_dry_run_status_text
            and "DROP_DS" not in latest_dry_run_status_text
            and '"api_key"' not in latest_dry_run_status_text
            and '"token"' not in latest_dry_run_status_text,
            f"latest_dry_run_status={latest_dry_run_status}",
        ),
        _row(
            "live_light_provider_model_execution_request_receipt_binds_latest_dry_run_without_external_call",
            execution_request.get("task_type")
            == "command_center_live_bootstrap_provider_model_execution_request"
            and execution_request.get("current_step")
            == "provider_model_execution_request_ready_manual_provider_model_task_pending"
            and execution_request.get("output_packet_key")
            == "command_center_live_bootstrap_provider_model_execution_request_packet"
            and request_payload.get("schema_version")
            == "command_center_live_bootstrap_provider_model_execution_request.v1"
            and request_payload.get("execution_request_only") is True
            and request_receipt.get("schema_version")
            == "command_center_live_bootstrap_provider_model_execution_request.v1"
            and request_receipt.get("status")
            == "execution_request_ready_manual_provider_model_task_pending"
            and request_receipt.get("latest_acceptance_dry_run_task_id") == dry_run.get("task_id")
            and request_receipt.get("latest_acceptance_dry_run_status")
            == "acceptance_dry_run_ready_execution_pending"
            and request_receipt.get("latest_acceptance_dry_run_storage_source")
            in {"memory_and_sqlite", "sqlite_meta"}
            and request_receipt.get("durable_receipt_visible") is True
            and request_receipt.get("memory_only_dry_run_receipt_is_durable_evidence") is False
            and request_receipt.get("acceptance_scope_hash") == dry_scope_ticket.get("scope_hash")
            and request_receipt.get("acceptance_scope_hash_short") == dry_scope_ticket.get("scope_hash_short")
            and request_receipt.get("acceptance_scope_hash_algorithm") == "sha256"
            and request_receipt.get("requested_acceptance_scope_hash_matches_latest") is True
            and request_receipt.get("user_confirmed") is True
            and request_receipt.get("selected_apis") == ["trade_cal", "daily", "moneyflow"]
            and request_receipt.get("include_tushare") is True
            and request_receipt.get("include_deepseek") is True
            and request_receipt.get("credential_presence_status") == "all_required_env_keys_present_no_values_read"
            and request_receipt.get("credential_preflight_ready") is True
            and request_receipt.get("credential_values_read") is False
            and request_receipt.get("credential_values_exposed") is False
            and request_receipt.get("env_key_names_included") is False
            and request_receipt.get("call_ledger_required") is True
            and request_receipt.get("model_ledger_required_for_deepseek") is True
            and request_receipt.get("redaction_review_required_before_promotion") is True
            and request_receipt.get("local_execution_request_ready") is True
            and request_receipt.get("ready_for_manual_provider_model_task_submission") is True
            and request_receipt.get("provider_model_task_created") is False
            and request_receipt.get("provider_model_task_dispatched") is False
            and request_receipt.get("provider_execution_implemented") is False
            and request_receipt.get("model_execution_implemented") is False
            and request_receipt.get("provider_model_execution_implemented") is False
            and request_receipt.get("execution_request_route_implemented") is True
            and request_receipt.get("production_live_light_complete") is False
            and request_receipt.get("local_blocker_count") == 0
            and int(request_receipt.get("production_blocker_count") or 0) > 0
            and request_rows.get("latest_acceptance_dry_run_receipt_visible", {}).get("status")
            == "passed_durable_dry_run_receipt_visible"
            and request_rows.get("acceptance_dry_run_ready", {}).get("status") == "passed_dry_run_ready"
            and request_rows.get("acceptance_scope_hash_bound", {}).get("status") == "passed_scope_hash_bound"
            and request_rows.get("explicit_user_confirmation_recorded", {}).get("status")
            == "passed_user_confirmed"
            and request_rows.get("credential_preflight_ready", {}).get("status")
            == "passed_credential_preflight_ready"
            and request_rows.get("provider_model_task_not_created", {}).get("status") == "passed_request_only"
            and request_rows.get("provider_model_task_not_created", {}).get("production_blocker") is True
            and first_request_ledger.get("api") == "local_live_light_provider_model_execution_request"
            and first_request_ledger.get("call_status") == "local_execution_request_ready_no_external_call"
            and _dict(first_request_ledger.get("request_params_safe")).get(
                "requested_acceptance_scope_hash_matches_latest"
            )
            is True
            and _dict(first_request_ledger.get("request_params_safe")).get("local_execution_request_ready")
            is True
            and _dict(first_request_ledger.get("request_params_safe")).get("provider_model_task_created")
            is False
            and first_request_ledger.get("external_calls_triggered") is False
            and first_request_ledger.get("tushare_called") is False
            and first_request_ledger.get("deepseek_called") is False
            and execution_request.get("external_calls_triggered") is False
            and execution_request.get("tushare_called") is False
            and execution_request.get("deepseek_called") is False
            and execution_request.get("github_called") is False
            and "DROP_TS" not in request_text
            and "DROP_DS" not in request_text
            and '"api_key"' not in request_text
            and '"token"' not in request_text,
            f"execution_request_receipt={request_receipt}",
        ),
        _row(
            "live_light_latest_execution_request_status_surface_replays_receipt_without_creating_task",
            latest_execution_status.get("schema_version")
            == "command_center_live_light_latest_execution_request_status.v1"
            and latest_execution_status.get("status") == "latest_execution_request_receipt_visible_ready"
            and latest_execution_status.get("lookup_source") == "task_service.list_task_statuses"
            and latest_execution_status.get("lookup_creates_task") is False
            and latest_execution_status.get("route") == "POST /api/bootstrap/provider-model-execution-request"
            and latest_execution_status.get("route_implemented") is True
            and latest_execution_status.get("receipt_found") is True
            and latest_execution_status.get("task_id") == execution_request.get("task_id")
            and latest_execution_status.get("task_status") == "success"
            and latest_execution_status.get("current_step")
            == "provider_model_execution_request_ready_manual_provider_model_task_pending"
            and latest_execution_status.get("output_packet_key")
            == "command_center_live_bootstrap_provider_model_execution_request_packet"
            and latest_execution_status.get("storage_source") in {"memory_and_sqlite", "sqlite_meta"}
            and latest_execution_status.get("durable_receipt_visible") is True
            and latest_execution_status.get("memory_only_receipt_is_durable_evidence") is False
            and latest_execution_status.get("local_execution_request_ready") is True
            and latest_execution_status.get("ready_for_manual_provider_model_task_submission") is True
            and latest_execution_status.get("receipt_status")
            == "execution_request_ready_manual_provider_model_task_pending"
            and latest_execution_status.get("latest_acceptance_dry_run_task_id") == dry_run.get("task_id")
            and latest_execution_status.get("acceptance_scope_hash_short") == dry_scope_ticket.get("scope_hash_short")
            and latest_execution_status.get("requested_acceptance_scope_hash_short")
            == dry_scope_ticket.get("scope_hash_short")
            and latest_execution_status.get("scope_hash_matches_latest") is True
            and latest_execution_status.get("credential_presence_status")
            == "all_required_env_keys_present_no_values_read"
            and latest_execution_status.get("credential_preflight_ready") is True
            and latest_execution_status.get("local_blocker_count") == 0
            and int(latest_execution_status.get("production_blocker_count") or 0) > 0
            and latest_execution_status.get("provider_model_task_created") is False
            and latest_execution_status.get("provider_model_task_dispatched") is False
            and latest_execution_status.get("provider_execution_implemented") is False
            and latest_execution_status.get("model_execution_implemented") is False
            and latest_execution_status.get("provider_model_execution_implemented") is False
            and latest_execution_status.get("production_live_light_complete") is False
            and latest_execution_status.get("external_calls_triggered") is False
            and latest_execution_status.get("tushare_called") is False
            and latest_execution_status.get("deepseek_called") is False
            and latest_execution_status.get("github_called") is False
            and latest_execution_status.get("credential_values_exposed") is False
            and latest_execution_status.get("env_key_names_included") is False
            and latest_execution_status.get("does_not_execute_trades") is True
            and latest_execution_status.get("does_not_modify_strategy_action") is True
            and latest_live_light.get("latest_execution_request_found") is True
            and latest_live_light.get("latest_execution_request_status")
            == "latest_execution_request_receipt_visible_ready"
            and latest_live_light.get("latest_execution_request_task_id") == execution_request.get("task_id")
            and latest_live_light.get("latest_execution_request_ready") is True
            and latest_live_light.get("latest_execution_request_durable_receipt_visible") is True
            and latest_live_light.get("latest_execution_request_lookup_creates_task") is False
            and latest_live_light.get("latest_execution_request_is_production_evidence") is False
            and latest_policy.get("live_light_latest_execution_request_status_visible") is True
            and latest_policy.get("live_light_latest_execution_request_lookup_creates_task") is False
            and latest_policy.get("live_light_latest_execution_request_is_production_evidence") is False
            and "DROP_TS" not in latest_status_text
            and "DROP_DS" not in latest_status_text
            and '"api_key"' not in latest_status_text
            and '"token"' not in latest_status_text,
            f"latest_execution_status={latest_execution_status}",
        ),
        _row(
            "live_light_provider_model_acceptance_dry_run_blocks_missing_credentials",
            dry_run_missing_credentials.get("current_step")
            == "provider_model_acceptance_dry_run_blocked_missing_credentials_no_external_call"
            and missing_summary.get("status") == "acceptance_dry_run_blocked_missing_credentials"
            and missing_summary.get("credential_presence_status") == "required_env_key_missing_no_values_read"
            and missing_summary.get("credential_required_provider_count") == 2
            and missing_summary.get("credential_present_provider_count") == 0
            and missing_summary.get("credential_missing_provider_count") == 2
            and missing_summary.get("blocked_by_missing_credentials") is True
            and missing_summary.get("ready_for_user_approved_real_acceptance") is False
            and missing_summary.get("allowed_next_step") == "configure_server_credentials_then_rerun_dry_run"
            and missing_summary.get("real_acceptance_task_implemented") is False
            and missing_summary.get("acceptance_scope_hash") == missing_scope_ticket.get("scope_hash")
            and missing_summary.get("real_acceptance_preflight_receipt_status")
            == "real_acceptance_preflight_blocked_dry_run_not_ready"
            and missing_summary.get("real_acceptance_preflight_ready_to_execute") is False
            and missing_scope_ticket.get("scope_hash_algorithm") == "sha256"
            and len(str(missing_scope_ticket.get("scope_hash") or "")) == 64
            and missing_scope_ticket.get("credential_values_included") is False
            and missing_scope_ticket.get("env_key_names_included") is False
            and _dict(missing_scope_ticket.get("scope_hash_input")).get("credential_presence_status")
            == "required_env_key_missing_no_values_read"
            and "server credential presence for selected providers" in _list(
                missing_summary.get("missing_evidence_items")
            )
            and "promote dry-run to provider-backed acceptance" in _list(
                missing_summary.get("not_allowed_next_steps")
            )
            and missing_credential_rows.get("tushare", {}).get("status") == "missing_no_value_read"
            and missing_credential_rows.get("deepseek", {}).get("status") == "missing_no_value_read"
            and missing_rows.get("server_secret_preflight", {}).get("status")
            == "dry_run_secret_presence_missing_no_values_exposed"
            and missing_real_preflight.get("status") == "real_acceptance_preflight_blocked_dry_run_not_ready"
            and missing_real_preflight.get("dry_run_ready_for_user_approved_real_acceptance") is False
            and missing_real_preflight.get("ready_to_execute_real_task") is False
            and missing_real_preflight.get("provider_execution_implemented") is False
            and missing_real_preflight.get("model_execution_implemented") is False
            and missing_real_preflight_rows.get("credential_presence_ready_without_value_exposure", {}).get("status")
            == "blocked_missing_server_credentials"
            and first_missing_ledger.get("call_status")
            == "local_acceptance_dry_run_blocked_missing_credentials_no_external_call"
            and first_missing_ledger.get("external_calls_triggered") is False
            and first_missing_ledger.get("tushare_called") is False
            and first_missing_ledger.get("deepseek_called") is False,
            f"missing_step={dry_run_missing_credentials.get('current_step')} summary={missing_summary}",
        ),
    ]


def build_contract() -> dict[str, Any]:
    original_env = {key: os.environ.get(key) for key in ENV_KEYS}
    original_meta_path = task_service.SQLITE_META_PATH
    rows: list[dict[str, Any]] = []
    try:
        with tempfile.TemporaryDirectory(prefix="stock_ming_bootstrap_contract_") as temp_dir:
            task_service.SQLITE_META_PATH = Path(temp_dir) / "meta.sqlite"
            rows.extend(_safe_config_rows())
            rows.extend(_cache_only_rows())
            rows.extend(_manual_rows())
            rows.extend(_live_full_reserved_rows())
            rows.extend(_live_light_disabled_rows())
            rows.extend(_live_light_light_provider_profile_rows())
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
