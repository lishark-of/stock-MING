from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from typing import Any

from server.services import packet_service


PACKET_KEY = "command_center_3_data_health_timeline_cache"
SCHEMA_VERSION = "data_health_timeline_cache.v1"
SENSITIVE_KEY_PARTS = ("secret", "token", "api_key", "apikey", "password", "passwd", "credential", "authorization")
SENSITIVE_TEXT_MARKERS = ("traceback", "api_key", "apikey", "authorization:", "bearer ", "token=", "secret=", "password=")
REAL_TRADE_CAL_QUERY_LIMIT = 10000
REAL_TRADE_CAL_MIN_WINDOW_DAYS = 180
REAL_TRADE_CAL_MIN_OPEN_DAYS = 60
REAL_TRADE_CAL_REQUIRED_COLUMNS = ("exchange", "cal_date", "is_open")


def _freshness_long_window_sample_validation() -> dict[str, Any]:
    from command_center_factor_research import build_a_share_freshness_long_window_sample_validation

    return build_a_share_freshness_long_window_sample_validation()


def _parse_cal_date(value: Any) -> _dt.date | None:
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        digits = digits[:8]
        try:
            return _dt.datetime.strptime(digits, "%Y%m%d").date()
        except ValueError:
            return None
    try:
        return _dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _trade_cal_is_open(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "open", "交易"}


def _local_trade_cal_physical_validation() -> dict[str, Any]:
    from command_center_factor_research import _expected_data_date
    from server.services import storage_service

    status = storage_service.parquet_dataset_status("trade_cal", limit=REAL_TRADE_CAL_QUERY_LIMIT)
    schema_metadata = storage_service.parquet_store.dataset_schema_metadata(
        root=storage_service.PARQUET_ROOT,
        name="trade_cal",
    )
    metadata = _as_dict(status.get("metadata"))
    query = _as_dict(status.get("query"))
    physical_columns = [str(column) for column in schema_metadata.get("columns") or query.get("available_columns") or []]
    missing_required_columns = [column for column in REAL_TRADE_CAL_REQUIRED_COLUMNS if column not in physical_columns]
    raw_rows = _as_list(query.get("rows"))
    cleaned_rows: list[dict[str, Any]] = []
    invalid_date_count = 0
    duplicate_key_count = 0
    seen_keys: set[tuple[str, _dt.date]] = set()

    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        cal_date = _parse_cal_date(raw.get("cal_date") or raw.get("trade_date") or raw.get("date"))
        if cal_date is None:
            invalid_date_count += 1
            continue
        exchange = _safe_text(raw.get("exchange") or "unknown", limit=40) or "unknown"
        key = (exchange, cal_date)
        if key in seen_keys:
            duplicate_key_count += 1
        seen_keys.add(key)
        cleaned_rows.append(
            {
                "exchange": exchange,
                "cal_date": cal_date,
                "is_open": _trade_cal_is_open(raw.get("is_open", 1)),
            }
        )
    cleaned_rows.sort(key=lambda row: (str(row.get("exchange") or ""), row["cal_date"]))
    dates = sorted({row["cal_date"] for row in cleaned_rows})
    open_dates = sorted({row["cal_date"] for row in cleaned_rows if row.get("is_open")})
    closed_dates = sorted({row["cal_date"] for row in cleaned_rows if not row.get("is_open")})
    start_date = dates[0] if dates else None
    end_date = dates[-1] if dates else None
    window_days = ((end_date - start_date).days + 1) if start_date and end_date else 0
    today = _dt.date.today()
    today_row_found = today in set(dates)
    latest_completed = max((day for day in open_dates if day <= today), default=None)
    previous_open = max((day for day in open_dates if day < today), default=None)
    next_open = min((day for day in open_dates if day > today), default=None)
    exchange_count = len({str(row.get("exchange") or "") for row in cleaned_rows})
    gate_context: dict[str, Any] = {}
    if cleaned_rows:
        gate_packet = {
            "rows": [
                {"cal_date": row["cal_date"].strftime("%Y%m%d"), "is_open": 1 if row.get("is_open") else 0}
                for row in cleaned_rows
            ]
        }
        gate_context = _expected_data_date(_now_iso(), gate_packet)

    blockers: list[str] = []
    if not metadata.get("exists"):
        blockers.append("local_trade_cal_parquet_missing")
    if schema_metadata.get("status") != "ready":
        blockers.append(f"schema_metadata_{schema_metadata.get('status') or 'unavailable'}")
    if missing_required_columns:
        blockers.append("missing_required_columns")
    if not cleaned_rows:
        blockers.append("local_trade_cal_rows_missing")
    if window_days < REAL_TRADE_CAL_MIN_WINDOW_DAYS:
        blockers.append("window_too_short_for_long_window_acceptance")
    if len(open_dates) < REAL_TRADE_CAL_MIN_OPEN_DAYS:
        blockers.append("open_day_count_too_low")
    if not closed_dates:
        blockers.append("closed_day_rows_missing")
    if not today_row_found:
        blockers.append("today_calendar_row_missing")
    if not latest_completed:
        blockers.append("latest_completed_trading_day_missing")
    if duplicate_key_count:
        blockers.append("duplicate_exchange_cal_date_keys")
    if invalid_date_count:
        blockers.append("invalid_cal_date_rows")
    if gate_context and gate_context.get("calendar_coverage_status") not in {"validated", "validated_no_next_open"}:
        blockers.append("freshness_gate_calendar_coverage_not_validated")

    validation_done = bool(not blockers)
    validation_status = (
        "local_trade_cal_validation_passed"
        if validation_done
        else "local_trade_cal_dataset_missing"
        if "local_trade_cal_parquet_missing" in blockers
        else "local_trade_cal_validation_pending"
    )
    validation_rows = [
        {
            "check": "physical_dataset",
            "status": "passed" if metadata.get("exists") else "blocked",
            "detail": metadata.get("status") or "missing",
            "path": metadata.get("path") or status.get("path") or "",
        },
        {
            "check": "schema_columns",
            "status": "passed" if not missing_required_columns and schema_metadata.get("status") == "ready" else "blocked",
            "required_columns": list(REAL_TRADE_CAL_REQUIRED_COLUMNS),
            "missing_required_columns": missing_required_columns,
            "physical_columns": physical_columns,
        },
        {
            "check": "long_window",
            "status": "passed"
            if window_days >= REAL_TRADE_CAL_MIN_WINDOW_DAYS and len(open_dates) >= REAL_TRADE_CAL_MIN_OPEN_DAYS
            else "blocked",
            "window_days": window_days,
            "min_window_days": REAL_TRADE_CAL_MIN_WINDOW_DAYS,
            "open_day_count": len(open_dates),
            "min_open_days": REAL_TRADE_CAL_MIN_OPEN_DAYS,
            "closed_day_count": len(closed_dates),
        },
        {
            "check": "current_coverage",
            "status": "passed" if today_row_found and latest_completed else "blocked",
            "today": today.isoformat(),
            "today_row_found": today_row_found,
            "latest_completed_trading_day": latest_completed.isoformat() if latest_completed else None,
            "previous_open_date": previous_open.isoformat() if previous_open else None,
            "next_open_date": next_open.isoformat() if next_open else None,
        },
        {
            "check": "freshness_gate_context",
            "status": "passed"
            if gate_context.get("calendar_coverage_status") in {"validated", "validated_no_next_open"}
            else "blocked",
            "expected_data_date": gate_context.get("expected_data_date"),
            "market_phase": gate_context.get("market_phase"),
            "calendar_coverage_status": gate_context.get("calendar_coverage_status"),
            "calendar_validated": bool(gate_context.get("calendar_validated")),
        },
    ]
    return {
        "status": validation_status,
        "scope": "local_physical_trade_cal_parquet_validation",
        "source_endpoint": "GET /api/storage/trade-cal",
        "dataset": "trade_cal",
        "path": metadata.get("path") or status.get("path") or "",
        "schema_metadata_status": schema_metadata.get("status"),
        "parquet_status": metadata.get("status") or status.get("status"),
        "query_status": query.get("status"),
        "query_limit": REAL_TRADE_CAL_QUERY_LIMIT,
        "query_returned_row_count": len(raw_rows),
        "row_count_metadata": schema_metadata.get("row_count_metadata"),
        "local_trade_cal_row_count": len(cleaned_rows),
        "exchange_count": exchange_count,
        "window_start": start_date.isoformat() if start_date else None,
        "window_end": end_date.isoformat() if end_date else None,
        "window_days": window_days,
        "min_window_days": REAL_TRADE_CAL_MIN_WINDOW_DAYS,
        "open_day_count": len(open_dates),
        "min_open_days": REAL_TRADE_CAL_MIN_OPEN_DAYS,
        "closed_day_count": len(closed_dates),
        "today": today.isoformat(),
        "today_row_found": today_row_found,
        "latest_completed_trading_day": latest_completed.isoformat() if latest_completed else None,
        "previous_open_date": previous_open.isoformat() if previous_open else None,
        "next_open_date": next_open.isoformat() if next_open else None,
        "missing_required_columns": missing_required_columns,
        "invalid_cal_date_count": invalid_date_count,
        "duplicate_key_count": duplicate_key_count,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "rows": validation_rows,
        "local_trade_cal_physical_validation_done": validation_done,
        "trade_cal_long_window_validation_done": validation_done,
        "real_provider_validation_done": False,
        "provider_backed_long_window_acceptance_done": False,
        "provider_acceptance_runbook_required": True,
        "provider_refresh_called_by_validation": False,
        "uses_actual_freshness_gate": bool(gate_context),
        "freshness_gate_context": gate_context,
        "fixture_is_synthetic": False,
        "cache_only": True,
        "cache_get_reads_local_trade_cal_rows": True,
        "cache_get_writes_files": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "note": "This validates an existing local trade_cal Parquet artifact only; it does not refresh providers and does not prove provider-backed acceptance.",
    }


def _freshness_acceptance_matrix_rows() -> list[dict[str, Any]]:
    base = {
        "acceptance_contract": "a_share_trading_calendar_freshness",
        "current_evidence_requires_expected_trade_date": True,
        "stale_expired_historical_unknown_are_research_only": True,
        "blocks_composite_score": True,
        "blocks_support_factors": True,
        "blocks_evidence_preview": True,
        "blocks_next_session_bridge_preview": True,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "validation_status": "contract_ready_real_long_window_trade_cal_pending",
    }
    rows = [
        {
            "scenario_id": "premarket_open_day",
            "scenario": "盘前交易日",
            "market_window": "open_day_before_09_30",
            "expected_trade_date_rule": "previous_completed_trading_day",
            "accepted_current_evidence": "data_date_equals_expected_trade_date",
            "fallback_behavior": "fallback_calendar_warns_when_trade_cal_missing",
            "provider_delay_grace": "not_needed_before_regular_session",
            "trade_cal_requirement": "trade_cal_preferred_for_previous_completed_trading_day",
            "research_only_states": "stale, expired, historical, unknown",
            "action_boundary": "never_mutates_strategy_action",
        },
        {
            "scenario_id": "intraday_before_eod_ready",
            "scenario": "盘中未到 EOD 可得时间",
            "market_window": "09_30_to_before_16_30",
            "expected_trade_date_rule": "previous_completed_trading_day_until_eod_data_ready",
            "accepted_current_evidence": "previous_completed_trade_date_or_bounded_provider_delay_grace",
            "fallback_behavior": "fallback_calendar_marks_calendar_validated_false",
            "provider_delay_grace": "bounded_previous_completed_trading_day_only",
            "trade_cal_requirement": "trade_cal_needed_for_open_day_and_previous_completed_date",
            "research_only_states": "same_day_intraday_unavailable, stale, expired, historical, unknown",
            "action_boundary": "never_mutates_strategy_action",
        },
        {
            "scenario_id": "closing_auction_1457_1500",
            "scenario": "收盘集合竞价",
            "market_window": "14_57_to_15_00",
            "expected_trade_date_rule": "previous_completed_trading_day_until_eod_data_ready",
            "accepted_current_evidence": "previous_completed_trade_date_only_unless_current_eod_cache_is_verified",
            "fallback_behavior": "do_not_assume_current_day_eod_available",
            "provider_delay_grace": "allowed_only_as_audited_previous_day_grace",
            "trade_cal_requirement": "trade_cal_needed_to_avoid_false_current_day_evidence",
            "research_only_states": "current_day_partial, stale, expired, historical, unknown",
            "action_boundary": "never_mutates_strategy_action",
        },
        {
            "scenario_id": "postclose_after_1630",
            "scenario": "盘后 16:30 后",
            "market_window": "open_day_at_or_after_16_30",
            "expected_trade_date_rule": "current_trading_day",
            "accepted_current_evidence": "current_day_data_only_when_data_date_equals_expected_trade_date",
            "fallback_behavior": "fallback_calendar_warns_and_blocks_unknown_current_evidence",
            "provider_delay_grace": "previous_day_grace_may_be_reported_but_not_full_fresh",
            "trade_cal_requirement": "trade_cal_needed_to_confirm_open_day",
            "research_only_states": "previous_day_after_grace, stale, expired, historical, unknown",
            "action_boundary": "never_mutates_strategy_action",
        },
        {
            "scenario_id": "weekend_or_holiday",
            "scenario": "周末或节假日",
            "market_window": "non_trading_day",
            "expected_trade_date_rule": "most_recent_completed_trading_day",
            "accepted_current_evidence": "most_recent_completed_trade_date",
            "fallback_behavior": "fallback_calendar_uses_business_day_approximation_with_warning",
            "provider_delay_grace": "not_used_as_current_day_freshness",
            "trade_cal_requirement": "trade_cal_required_for_holiday_clusters_before_production_acceptance",
            "research_only_states": "unknown_calendar, stale, expired, historical",
            "action_boundary": "never_mutates_strategy_action",
        },
        {
            "scenario_id": "trade_cal_missing_fallback",
            "scenario": "trade_cal 缺失",
            "market_window": "any_window_without_valid_trade_cal",
            "expected_trade_date_rule": "business_day_fallback_with_calendar_validated_false",
            "accepted_current_evidence": "only_if_data_date_matches_fallback_expected_date_and_warning_is_visible",
            "fallback_behavior": "emit_warning_and_keep_real_trade_cal_validation_pending",
            "provider_delay_grace": "must_remain_audited_and_bounded",
            "trade_cal_requirement": "missing_trade_cal_blocks_production_acceptance",
            "research_only_states": "unknown, stale, expired, historical",
            "action_boundary": "never_mutates_strategy_action",
        },
        {
            "scenario_id": "provider_delay_grace",
            "scenario": "Provider 延迟宽限",
            "market_window": "after_close_before_provider_ready_or_configured_grace",
            "expected_trade_date_rule": "current_trading_day_after_ready_time_else_previous_completed_trading_day",
            "accepted_current_evidence": "grace_is_audited_not_equal_to_full_fresh",
            "fallback_behavior": "after_grace_window_previous_day_becomes_stale",
            "provider_delay_grace": "bounded_by_ready_time_and_counted_separately",
            "trade_cal_requirement": "trade_cal_needed_to_confirm_current_and_previous_sessions",
            "research_only_states": "expired_grace, stale, expired, historical, unknown",
            "action_boundary": "never_mutates_strategy_action",
        },
        {
            "scenario_id": "stale_expired_historical_unknown",
            "scenario": "stale / expired / historical / unknown",
            "market_window": "any_window",
            "expected_trade_date_rule": "blocked_unless_data_date_matches_expected_and_state_is_fresh_or_bounded_grace",
            "accepted_current_evidence": "none_for_current_decision_surfaces",
            "fallback_behavior": "display_as_research_only_with_reason",
            "provider_delay_grace": "not_applicable_when_state_is_expired_or_unknown",
            "trade_cal_requirement": "trade_cal_can_explain_but_not_override_bad_state",
            "research_only_states": "stale, expired, historical, unknown",
            "action_boundary": "cannot_enter_score_support_evidence_preview_next_session_bridge_or_strategy_action",
        },
    ]
    return [{**base, **row} for row in rows]


def _freshness_acceptance_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "acceptance_matrix_ready",
        "scope": "local_contract_not_real_trade_cal_validation",
        "scenario_count": len(rows),
        "trade_cal_long_window_validation_done": False,
        "real_provider_validation_done": False,
        "cache_api_external_calls": False,
        "react_render_external_calls": False,
        "current_evidence_requires_expected_trade_date": True,
        "stale_expired_historical_unknown_are_research_only": True,
        "blocks_composite_score": True,
        "blocks_support_factors": True,
        "blocks_evidence_preview": True,
        "blocks_next_session_bridge_preview": True,
        "provider_delay_grace_is_bounded": True,
        "missing_trade_cal_falls_back_with_warning": True,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "note": "Matrix documents LTG-01 acceptance boundaries; it is not a real long-window trade_cal acceptance run.",
    }


def _date_text_from_mapping(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value in (None, "", {}, []):
            continue
        parsed = _parse_cal_date(value)
        if parsed is not None:
            return parsed.isoformat()
        return _safe_text(value, limit=40)
    return ""


def _current_evidence_freshness_qa_contract(
    data_freshness: Mapping[str, Any],
    freshness_sample: Mapping[str, Any],
    trade_cal_physical: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = _safe_text(
        data_freshness.get("state")
        or data_freshness.get("freshness_state")
        or data_freshness.get("status")
        or "unknown",
        limit=80,
    ).lower()
    expected_trade_date = _date_text_from_mapping(
        data_freshness,
        "expected_trade_date",
        "expected_data_date",
        "expected_date",
    )
    data_date = _date_text_from_mapping(
        data_freshness,
        "data_date",
        "latest_data_date",
        "latest_trade_date",
        "trade_date",
        "as_of_date",
    )
    full_fresh_states = {"fresh"}
    grace_states = {"provider_delay_grace"}
    research_only_states = {"stale", "expired", "historical", "unknown", "missing", "future_unavailable"}
    date_matches_expected = bool(expected_trade_date and data_date and expected_trade_date == data_date)
    state_allows_current = state in full_fresh_states or state in grace_states
    full_current_evidence_ready = bool(date_matches_expected and state in full_fresh_states)
    grace_current_evidence_ready = bool(date_matches_expected and state in grace_states)
    candidate_status = (
        "current_evidence_ready"
        if full_current_evidence_ready
        else "bounded_grace_audited_not_full_fresh"
        if grace_current_evidence_ready
        else "research_only"
    )
    blockers: list[str] = []
    if not expected_trade_date:
        blockers.append("expected_trade_date_missing")
    if not data_date:
        blockers.append("data_date_missing")
    if expected_trade_date and data_date and expected_trade_date != data_date:
        blockers.append("data_date_does_not_match_expected_trade_date")
    if not state_allows_current:
        blockers.append(f"state_{state or 'unknown'}_research_only")
    blockers.append("provider_backed_trade_cal_acceptance_pending")

    base = {
        "acceptance_contract": "current_evidence_freshness_qa",
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "current_evidence_requires_expected_trade_date": True,
        "historical_samples_are_research_only": True,
        "stale_expired_historical_unknown_are_research_only": True,
        "blocks_composite_score": True,
        "blocks_support_factors": True,
        "blocks_evidence_preview": True,
        "blocks_next_session_bridge_preview": True,
    }
    rows = [
        {
            **base,
            "criterion": "expected_trade_date_required",
            "status": "passed" if expected_trade_date else "blocked",
            "detail": "current evidence must carry expected_trade_date or expected_data_date",
            "observed_value": expected_trade_date or "missing",
        },
        {
            **base,
            "criterion": "current_data_date_matches_expected",
            "status": "passed" if date_matches_expected else "research_only",
            "detail": "data_date must match expected_trade_date before a row can be treated as current evidence",
            "expected_trade_date": expected_trade_date or "missing",
            "data_date": data_date or "missing",
        },
        {
            **base,
            "criterion": "freshness_state_allows_current_evidence",
            "status": "passed"
            if state in full_fresh_states
            else "bounded_grace"
            if state in grace_states
            else "research_only",
            "detail": "fresh is eligible; provider_delay_grace is audited separately; stale/expired/historical/unknown remain research-only",
            "observed_state": state,
        },
        {
            **base,
            "criterion": "stale_expired_historical_unknown_boundary",
            "status": "enforced",
            "detail": "bad or historical freshness states cannot enter current decision surfaces",
            "research_only_states": sorted(research_only_states),
        },
        {
            **base,
            "criterion": "historical_sample_separation",
            "status": "enforced",
            "detail": "synthetic samples, long-window fixtures, and historical rows stay separate from current evidence",
            "synthetic_sample_status": freshness_sample.get("status"),
            "synthetic_sample_is_fixture": bool(freshness_sample.get("fixture_is_synthetic")),
            "local_trade_cal_validation_status": trade_cal_physical.get("status"),
        },
        {
            **base,
            "criterion": "decision_surface_isolation",
            "status": "enforced",
            "detail": "blocked rows cannot enter composite_score, support_factors, evidence preview, next_session_bridge.preview, or strategy action",
            "blocked_surfaces": [
                "composite_score",
                "support_factors",
                "evidence_preview",
                "next_session_bridge.preview",
                "strategy_action",
            ],
        },
        {
            **base,
            "criterion": "provider_backed_trade_cal_acceptance",
            "status": "pending_provider_backed_acceptance",
            "detail": "local matrix, fixture, and Parquet artifact checks do not prove provider-backed trade_cal acceptance",
            "local_trade_cal_artifact_validation_done": bool(
                trade_cal_physical.get("local_trade_cal_physical_validation_done")
            ),
            "provider_backed_long_window_acceptance_done": False,
            "provider_refresh_called_by_validation": False,
        },
        {
            **base,
            "criterion": "external_and_trade_boundary",
            "status": "enforced",
            "detail": "GET data health cache never calls providers, models, GitHub, or trading chains",
        },
    ]
    contract = {
        "schema_version": "data_health_current_evidence_freshness_qa.v1",
        "status": "current_evidence_qa_ready_provider_trade_cal_acceptance_pending",
        "scope": "local_cache_only_current_evidence_boundary_contract",
        "data_freshness_state": state,
        "expected_trade_date": expected_trade_date or None,
        "data_date": data_date or None,
        "date_matches_expected_trade_date": date_matches_expected,
        "current_evidence_candidate_status": candidate_status,
        "current_evidence_blockers": blockers,
        "current_evidence_blocker_count": len(blockers),
        "row_count": len(rows),
        "local_trade_cal_artifact_validation_done": bool(
            trade_cal_physical.get("local_trade_cal_physical_validation_done")
        ),
        "synthetic_sample_validation_done": bool(freshness_sample.get("local_sample_validation_done")),
        "provider_backed_long_window_acceptance_done": False,
        "provider_refresh_called_by_validation": False,
        "current_evidence_requires_expected_trade_date": True,
        "historical_samples_are_research_only": True,
        "stale_expired_historical_unknown_are_research_only": True,
        "blocks_composite_score": True,
        "blocks_support_factors": True,
        "blocks_evidence_preview": True,
        "blocks_next_session_bridge_preview": True,
        "does_not_modify_strategy_action": True,
        "does_not_execute_trades": True,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "note": "This is a local QA contract for current-evidence boundaries; it does not refresh trade_cal or prove provider-backed production acceptance.",
    }
    return contract, rows


BAD_CURRENT_EVIDENCE_STATES = {"stale", "expired", "historical", "unknown", "missing", "future_unavailable", "stale_data"}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in _as_list(value) if isinstance(item, Mapping)]


def _surface_state(row: Mapping[str, Any]) -> str:
    for key in ("freshness_state", "data_freshness_state", "freshness_status", "data_status", "state"):
        text = _safe_text(row.get(key), limit=80).lower()
        if text:
            return text
    return ""


def _decision_surface_row(
    *,
    surface: str,
    source_packet: str,
    entries: list[dict[str, Any]],
    scalar_observed: bool,
    current_evidence_status: str,
    requires_current_evidence_ready: bool,
    detail: str,
) -> dict[str, Any]:
    observed_count = len(entries) + (1 if scalar_observed else 0)
    entry_states = [_surface_state(row) for row in entries]
    bad_state_count = len([state for state in entry_states if state in BAD_CURRENT_EVIDENCE_STATES])
    blocked_by_current_status = bool(
        requires_current_evidence_ready
        and observed_count
        and current_evidence_status != "current_evidence_ready"
    )
    if observed_count == 0:
        status = "not_observed"
    elif bad_state_count:
        status = "blocked_bad_freshness_state_observed"
    elif blocked_by_current_status:
        status = "blocked_current_evidence_not_ready"
    elif requires_current_evidence_ready:
        status = "passed_read_only_audit"
    else:
        status = "observed_read_only"
    return {
        "surface": surface,
        "source_packet": source_packet,
        "status": status,
        "detail": detail,
        "observed_value_count": observed_count,
        "requires_current_evidence_ready": bool(requires_current_evidence_ready),
        "current_evidence_candidate_status": current_evidence_status,
        "blocked_by_current_freshness": status.startswith("blocked_"),
        "bad_freshness_state_count": bad_state_count,
        "observed_entry_states": [state for state in entry_states if state][:8],
        "cache_only": True,
        "read_only_snapshot_audit": True,
        "does_not_rescore": True,
        "does_not_filter_packet": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _current_evidence_decision_surface_audit(
    snapshot: Mapping[str, Any],
    current_evidence_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current_status = _safe_text(
        current_evidence_contract.get("current_evidence_candidate_status") or "research_only",
        limit=80,
    )
    factor_packet = _first_mapping(
        snapshot,
        "command_center_factor_quant_hub_packet",
        "factor_quant_hub_packet",
    )
    score_packet = _as_dict(factor_packet.get("score")) or _first_mapping(
        snapshot,
        "command_center_factor_score_packet",
        "factor_score_packet",
    )
    bridge_packet = _as_dict(factor_packet.get("next_session_bridge"))
    strategy_packet = _first_mapping(
        snapshot,
        "strategy_execution_packet",
        "command_center_strategy_execution_packet",
        "strategy_packet",
    )
    evidence_preview_entries = _mapping_list(
        factor_packet.get("evidence_preview") or score_packet.get("evidence_preview")
    )
    bridge_preview_entries = _mapping_list(bridge_packet.get("preview"))
    rows = [
        _decision_surface_row(
            surface="composite_score",
            source_packet="command_center_factor_quant_hub_packet.score",
            entries=[],
            scalar_observed=score_packet.get("composite_score") not in (None, ""),
            current_evidence_status=current_status,
            requires_current_evidence_ready=True,
            detail="composite_score must stay empty or blocked when current evidence is research-only.",
        ),
        _decision_surface_row(
            surface="support_factors",
            source_packet="command_center_factor_quant_hub_packet.score",
            entries=_mapping_list(score_packet.get("support_factors")),
            scalar_observed=False,
            current_evidence_status=current_status,
            requires_current_evidence_ready=True,
            detail="support_factors must not contain stale/expired/historical/unknown current evidence.",
        ),
        _decision_surface_row(
            surface="evidence_preview",
            source_packet="command_center_factor_quant_hub_packet",
            entries=evidence_preview_entries,
            scalar_observed=False,
            current_evidence_status=current_status,
            requires_current_evidence_ready=True,
            detail="factor evidence preview must remain separate from research-only or blocked current evidence.",
        ),
        _decision_surface_row(
            surface="next_session_bridge.preview",
            source_packet="command_center_factor_quant_hub_packet.next_session_bridge",
            entries=bridge_preview_entries,
            scalar_observed=False,
            current_evidence_status=current_status,
            requires_current_evidence_ready=True,
            detail="next_session_bridge.preview cannot carry stale/expired/historical/unknown evidence into next-session display.",
        ),
        _decision_surface_row(
            surface="strategy_action",
            source_packet="strategy_execution_packet",
            entries=[],
            scalar_observed=bool(strategy_packet.get("action") or strategy_packet.get("overall_action")),
            current_evidence_status=current_status,
            requires_current_evidence_ready=False,
            detail="strategy action is read-only here; Data Health does not compute, overwrite, or execute it.",
        ),
    ]
    blocked_rows = [row for row in rows if str(row.get("status", "")).startswith("blocked_")]
    observed_rows = [row for row in rows if int(row.get("observed_value_count") or 0) > 0]
    contract = {
        "schema_version": "data_health_current_evidence_decision_surface_audit.v1",
        "status": "decision_surface_audit_ready_blockers_visible"
        if blocked_rows
        else "decision_surface_audit_ready_no_observed_blockers",
        "scope": "local_snapshot_only_no_rescore_no_action_mutation",
        "current_evidence_candidate_status": current_status,
        "expected_trade_date": current_evidence_contract.get("expected_trade_date"),
        "data_date": current_evidence_contract.get("data_date"),
        "date_matches_expected_trade_date": bool(current_evidence_contract.get("date_matches_expected_trade_date")),
        "row_count": len(rows),
        "observed_surface_count": len(observed_rows),
        "blocked_surface_count": len(blocked_rows),
        "blocked_surface_keys": [row["surface"] for row in blocked_rows],
        "snapshot_packet_observed": bool(factor_packet or score_packet or strategy_packet),
        "read_only_snapshot_audit": True,
        "does_not_rescore": True,
        "does_not_filter_packet": True,
        "does_not_mutate_decision_surfaces": True,
        "provider_backed_long_window_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "cache_only": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This audits only decision surfaces visible in the local snapshot. Missing packets are reported as not_observed, not as production proof.",
    }
    return contract, rows


CURRENT_EVIDENCE_PRODUCER_SPECS: tuple[dict[str, Any], ...] = (
    {
        "producer": "global_data_freshness",
        "path_options": (("data_freshness",),),
        "required": True,
        "detail": "Global current-evidence freshness context used by Data Health and downstream pages.",
    },
    {
        "producer": "factor_quant_hub",
        "path_options": (
            ("command_center_factor_quant_hub_packet", "data_freshness_gate"),
            ("factor_quant_hub_packet", "data_freshness_gate"),
        ),
        "required": False,
        "detail": "Factor Quant Hub freshness gate must expose expected date, latest data date, and freshness status when packet is present.",
    },
    {
        "producer": "candidate_radar",
        "path_options": (
            ("command_center_3_candidate_radar_cache", "freshness_state"),
            ("candidate_radar_packet", "freshness_state"),
            ("radar_packet", "freshness_state"),
        ),
        "required": False,
        "detail": "Candidate radar scans must carry freshness_state so radar candidates remain research-only when inputs are stale.",
    },
    {
        "producer": "next_session_projection",
        "path_options": (
            ("command_center_next_session_projection_packet", "data_freshness"),
            ("command_center_next_session_projection_packet", "data_freshness_gate"),
            ("next_session_projection_packet", "data_freshness"),
        ),
        "required": False,
        "detail": "Next-session projection evidence must declare freshness context before it can be treated as current evidence.",
    },
    {
        "producer": "a_share_evidence_radar",
        "path_options": (
            ("command_center_evidence_radar_packet", "data_freshness"),
            ("a_share_evidence_packet", "data_freshness"),
            ("a_share_fact_lineage_summary", "data_freshness"),
        ),
        "required": False,
        "detail": "Evidence radar and fact-lineage summaries need expected-date context when promoted to current evidence.",
    },
    {
        "producer": "market_context",
        "path_options": (
            ("market_packet", "data_freshness"),
            ("command_center_market_context_packet", "data_freshness"),
            ("moneyflow_packet", "data_freshness"),
        ),
        "required": False,
        "detail": "Market context packets must keep market data freshness visible instead of implying current evidence.",
    },
)


def _mapping_at_path(root: Mapping[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    value: Any = root
    for key in path:
        if not isinstance(value, Mapping):
            return {}
        value = value.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _first_mapping_at_paths(root: Mapping[str, Any], paths: tuple[tuple[str, ...], ...]) -> tuple[dict[str, Any], tuple[str, ...] | None, bool]:
    packet_observed = False
    for path in paths:
        if path and isinstance(root.get(path[0]), Mapping):
            packet_observed = True
        mapping = _mapping_at_path(root, path)
        if mapping:
            return mapping, path, True
    return {}, None, packet_observed


def _producer_freshness_status(mapping: Mapping[str, Any]) -> str:
    return _safe_text(
        mapping.get("state")
        or mapping.get("freshness_state")
        or mapping.get("freshness_status")
        or mapping.get("status")
        or "",
        limit=80,
    ).lower()


def _producer_coverage_row(spec: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    path_options = tuple(tuple(str(part) for part in path) for path in spec.get("path_options") or ())
    mapping, observed_path, mapping_observed = _first_mapping_at_paths(snapshot, path_options)
    required = bool(spec.get("required"))
    packet_observed = mapping_observed or (observed_path is not None) or any(
        path and isinstance(snapshot.get(path[0]), Mapping) for path in path_options
    )
    expected_trade_date = _date_text_from_mapping(
        mapping,
        "expected_trade_date",
        "expected_data_date",
        "expected_date",
    )
    data_date = _date_text_from_mapping(
        mapping,
        "data_date",
        "latest_data_date",
        "latest_trade_date",
        "trade_date",
        "as_of_date",
    )
    state = _producer_freshness_status(mapping)
    missing_fields: list[str] = []
    if not expected_trade_date:
        missing_fields.append("expected_trade_date")
    if not data_date:
        missing_fields.append("data_date")
    if not state:
        missing_fields.append("freshness_state")
    date_matches = bool(expected_trade_date and data_date and expected_trade_date == data_date)
    if not packet_observed and not required:
        status = "not_observed"
    elif not mapping_observed:
        status = "blocked_freshness_contract_missing"
    elif "expected_trade_date" in missing_fields:
        status = "blocked_expected_trade_date_missing"
    elif "data_date" in missing_fields:
        status = "blocked_data_date_missing"
    elif "freshness_state" in missing_fields:
        status = "blocked_freshness_state_missing"
    elif not date_matches:
        status = "date_mismatch_research_only"
    elif state in BAD_CURRENT_EVIDENCE_STATES:
        status = "research_only_state_visible"
    else:
        status = "passed_read_only_contract"
    return {
        "producer": spec.get("producer"),
        "status": status,
        "detail": spec.get("detail"),
        "observed_path": ".".join(observed_path or path_options[0]) if path_options else "",
        "packet_observed": bool(packet_observed),
        "freshness_mapping_observed": bool(mapping_observed),
        "required_for_current_evidence": required,
        "expected_trade_date_present": bool(expected_trade_date),
        "data_date_present": bool(data_date),
        "freshness_state_present": bool(state),
        "expected_trade_date": expected_trade_date or None,
        "data_date": data_date or None,
        "date_matches_expected_trade_date": date_matches,
        "freshness_state": state or None,
        "missing_fields": missing_fields,
        "cache_only": True,
        "read_only_snapshot_audit": True,
        "does_not_build_missing_packets": True,
        "does_not_refresh_provider": True,
        "does_not_rescore": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _current_evidence_producer_coverage_audit(
    snapshot: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [_producer_coverage_row(spec, snapshot) for spec in CURRENT_EVIDENCE_PRODUCER_SPECS]
    blocked_rows = [row for row in rows if str(row.get("status", "")).startswith("blocked_")]
    observed_rows = [row for row in rows if row.get("packet_observed")]
    passed_rows = [row for row in rows if row.get("status") == "passed_read_only_contract"]
    contract = {
        "schema_version": "data_health_current_evidence_producer_coverage.v1",
        "status": "producer_freshness_coverage_ready_blockers_visible"
        if blocked_rows
        else "producer_freshness_coverage_ready_no_observed_blockers",
        "scope": "local_snapshot_only_expected_date_field_coverage",
        "producer_count": len(rows),
        "observed_producer_count": len(observed_rows),
        "passed_producer_count": len(passed_rows),
        "blocked_producer_count": len(blocked_rows),
        "blocked_producer_keys": [row["producer"] for row in blocked_rows],
        "required_producer_keys": [
            str(spec.get("producer")) for spec in CURRENT_EVIDENCE_PRODUCER_SPECS if spec.get("required")
        ],
        "all_observed_producers_have_expected_trade_date": all(
            row.get("expected_trade_date_present") for row in observed_rows if row.get("freshness_mapping_observed")
        ),
        "not_observed_is_not_production_proof": True,
        "provider_backed_long_window_acceptance_done": False,
        "production_freshness_gate_complete": False,
        "cache_only": True,
        "read_only_snapshot_audit": True,
        "does_not_build_missing_packets": True,
        "does_not_refresh_provider": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This audits expected-date/freshness fields on visible local producers only; missing packets are not production proof.",
    }
    return contract, rows


def _trade_cal_provider_acceptance_row(
    criterion: str,
    status: str,
    *,
    evidence: str,
    required_for_provider_acceptance: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "required_for_provider_acceptance": bool(required_for_provider_acceptance),
        "runbook_criterion_ready": status in {"passed_static_policy", "execution_ready"},
        "provider_acceptance_done": False,
        "evidence": evidence,
        "cache_only": True,
        "runs_no_provider_call": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _trade_cal_provider_acceptance_runbook(
    trade_cal_physical: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    local_artifact_done = bool(trade_cal_physical.get("local_trade_cal_physical_validation_done"))
    local_window_days = int(trade_cal_physical.get("window_days") or 0)
    rows = [
        _trade_cal_provider_acceptance_row(
            "explicit_post_task_required",
            "passed_static_policy",
            evidence="Only POST /api/tasks/refresh-tushare-facts with selected api trade_cal may refresh provider data.",
        ),
        _trade_cal_provider_acceptance_row(
            "safe_payload_declared",
            "execution_ready",
            evidence="Payload must declare api=trade_cal, exchange, start_date, end_date, and acceptance_mode without token/key material.",
        ),
        _trade_cal_provider_acceptance_row(
            "call_ledger_required",
            "execution_ready",
            evidence="Provider run must record api, row_count, data_date/window, local_fetched_at, call_status, and error_message_safe.",
        ),
        _trade_cal_provider_acceptance_row(
            "long_window_sample_required",
            "execution_pending",
            evidence="Acceptance requires at least 730 calendar days, current-date coverage, open rows, closed rows, and holiday/weekend clusters.",
        ),
        _trade_cal_provider_acceptance_row(
            "schema_required",
            "execution_pending",
            evidence="Provider result must contain exchange, cal_date, is_open, and safe optional pretrade_date fields before Parquet promotion.",
        ),
        _trade_cal_provider_acceptance_row(
            "local_artifact_cross_check",
            "passed_static_policy" if local_artifact_done else "execution_pending",
            evidence=f"local_artifact_done={local_artifact_done}; local_window_days={local_window_days}",
            required_for_provider_acceptance=False,
        ),
        _trade_cal_provider_acceptance_row(
            "freshness_gate_replay_required",
            "execution_pending",
            evidence="Provider-backed rows must replay premarket, intraday, closing auction, post-16:30, weekend, holiday, missing-row, and delay-grace scenarios.",
        ),
        _trade_cal_provider_acceptance_row(
            "failure_modes_required",
            "execution_pending",
            evidence="Permission denied, empty window, no records, parse failure, missing params, and provider errors must be distinguishable and redacted.",
        ),
        _trade_cal_provider_acceptance_row(
            "artifact_promotion_boundary",
            "execution_pending",
            evidence="Fetched rows may be promoted to Parquet only after schema, window, freshness replay, and call-ledger checks pass.",
        ),
        _trade_cal_provider_acceptance_row(
            "current_evidence_boundary",
            "passed_static_policy",
            evidence="Until provider acceptance is complete, current evidence remains gated and cannot enter score/support/evidence/action through this runbook.",
        ),
        _trade_cal_provider_acceptance_row(
            "secret_and_trade_boundary",
            "passed_static_policy",
            evidence="Runbook stores no token/key and never touches trading or strategy action.",
        ),
    ]
    pending = [row["criterion"] for row in rows if row["status"] == "execution_pending"]
    contract = {
        "schema_version": "data_health_trade_cal_provider_acceptance_runbook.v1",
        "status": "trade_cal_provider_acceptance_runbook_ready_execution_pending",
        "scope": "local_provider_acceptance_runbook_not_provider_execution",
        "ltg": "LTG-01/LTG-02",
        "local_runbook_ready": True,
        "provider_backed_long_window_acceptance_done": False,
        "provider_refresh_called_by_runbook": False,
        "production_freshness_gate_complete": False,
        "post_task_route": "POST /api/tasks/refresh-tushare-facts",
        "required_api": "trade_cal",
        "required_payload_safe": {
            "apis": ["trade_cal"],
            "acceptance_mode": "provider_backed_trade_cal_long_window",
            "exchange": ["SSE", "SZSE"],
            "start_date": "YYYYMMDD",
            "end_date": "YYYYMMDD",
        },
        "minimum_acceptance_window_days": 730,
        "local_artifact_cross_check_done": local_artifact_done,
        "local_artifact_window_days": local_window_days,
        "row_count": len(rows),
        "pending_execution_count": len(pending),
        "pending_execution_items": pending,
        "cache_only": True,
        "runs_no_provider_call": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This runbook fixes provider-backed trade_cal acceptance requirements. It does not call Tushare or prove provider-backed acceptance.",
    }
    return contract, rows


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
        return [_safe_value(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:100]]
    return _safe_text(value)


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "data_health_timeline_cache_not_json_serializable"}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_value(snapshot: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = snapshot.get(key)
        if value not in (None, {}, []):
            return value
    return None


def _first_mapping(snapshot: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    value = _first_value(snapshot, *keys)
    return _as_dict(value)


def _rows(value: Any, *, source: str, text_key: str = "label") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for list_key in ("items", "rows", "events", "timeline", "actions", "providers", "cards", "capabilities", "gaps"):
            items = value.get(list_key)
            if isinstance(items, list):
                return _rows(items, source=f"{source}.{list_key}", text_key=text_key)
        for key, val in value.items():
            if isinstance(val, Mapping):
                row = dict(val)
                row.setdefault("key", key)
                row.setdefault("source", source)
                rows.append(row)
            elif isinstance(val, list):
                rows.extend(_rows(val, source=f"{source}.{key}", text_key=text_key))
        return rows[:120]
    for idx, raw in enumerate(_as_list(value), start=1):
        if isinstance(raw, Mapping):
            row = dict(raw)
            row.setdefault("index", idx)
            row.setdefault("source", source)
            rows.append(row)
        elif raw is not None:
            rows.append({"index": idx, "source": source, text_key: _safe_text(raw)})
    return rows[:120]


def _combined_rows(*values: tuple[Any, str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value, source, text_key in values:
        rows.extend(_rows(value, source=source, text_key=text_key))
    return rows[:180]


def _trade_cal_provider_acceptance_promotion_row(
    criterion: str,
    passed: bool,
    *,
    evidence: str,
    required_for_promotion: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": "passed" if passed else "blocked",
        "passed": bool(passed),
        "required_for_promotion": bool(required_for_promotion),
        "evidence": evidence,
        "cache_only": True,
        "read_only_snapshot_audit": True,
        "provider_refresh_called_by_audit": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _trade_cal_provider_acceptance_evidence_rows(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    sources = (
        (_first_value(snapshot, "data_health_ledger", "command_center_data_health_ledger"), "data_health_ledger"),
        (
            _first_value(snapshot, "tushare_refresh_facts_packet", "command_center_tushare_refresh_facts_packet"),
            "tushare_refresh_facts_packet",
        ),
        (_first_value(snapshot, "tushare_refresh_packet", "command_center_tushare_refresh_packet"), "tushare_refresh_packet"),
        (
            _first_value(snapshot, "trade_cal_provider_acceptance_result", "trade_cal_acceptance_packet"),
            "trade_cal_provider_acceptance_result",
        ),
    )
    evidence_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value, source in sources:
        candidate_rows: list[dict[str, Any]] = []
        if isinstance(value, Mapping):
            if str(value.get("api") or value.get("required_api") or "").strip().lower() == "trade_cal":
                candidate_rows.append(dict(value))
            for key in ("call_ledger", "rows"):
                for raw in _as_list(value.get(key)):
                    if isinstance(raw, Mapping):
                        candidate_rows.append(dict(raw))
        else:
            candidate_rows.extend(_rows(value, source=source, text_key="ledger"))
        for row in candidate_rows:
            api_name = str(row.get("api") or row.get("required_api") or "").strip().lower()
            has_trade_cal_evidence_field = any(
                key in row
                for key in (
                    "call_status",
                    "row_count",
                    "window_days",
                    "acceptance_mode",
                    "provider_backed_long_window_acceptance_done",
                    "provider_backed_trade_cal_acceptance_done",
                    "trade_cal_provider_acceptance_done",
                )
            )
            if api_name != "trade_cal" or not has_trade_cal_evidence_field:
                continue
            row.setdefault("source", source)
            signature = json.dumps(_json_safe(row), ensure_ascii=False, sort_keys=True)
            if signature in seen:
                continue
            seen.add(signature)
            evidence_rows.append(row)
    return evidence_rows[:40]


def _local_tushare_refresh_packet_for_data_health() -> dict[str, Any]:
    try:
        packet = packet_service.read_packet("command_center_tushare_refresh_packet")
    except Exception:
        packet = {}
    if not isinstance(packet, Mapping) or packet.get("status") == "cache_missing":
        return {}
    return dict(_safe_value(packet))


def _local_tushare_refresh_packet_summary(packet: Mapping[str, Any]) -> dict[str, Any]:
    call_ledger = _as_list(packet.get("call_ledger"))
    trade_cal_rows = [
        row
        for row in call_ledger
        if isinstance(row, Mapping) and str(row.get("api") or "").lower() == "trade_cal"
    ]
    accepted_rows = [row for row in trade_cal_rows if row.get("provider_backed_long_window_acceptance_done") is True]
    return {
        "schema_version": "data_health_local_tushare_refresh_packet_summary.v1",
        "available": bool(packet),
        "source_packet_key": "command_center_tushare_refresh_packet",
        "source_cache": packet.get("cache_source"),
        "status": packet.get("status"),
        "selected_apis": [str(item) for item in _as_list(packet.get("selected_apis"))],
        "call_ledger_count": len(call_ledger),
        "trade_cal_call_ledger_count": len(trade_cal_rows),
        "trade_cal_provider_acceptance_evidence_row_count": len(accepted_rows),
        "provider_backed_long_window_acceptance_done": bool(accepted_rows),
        "provider_backed_acceptance_done": False,
        "production_tushare_pipeline_complete": False,
        "cache_get_external_calls": False,
        "read_only_sqlite_packet_lookup": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "Data Health reads this persisted packet only as local evidence. It does not create tasks or call Tushare.",
    }


def _row_truthy(row: Mapping[str, Any], *keys: str) -> bool:
    return any(row.get(key) is True for key in keys)


def _max_int(rows: list[dict[str, Any]], *keys: str) -> int:
    best = 0
    for row in rows:
        for key in keys:
            try:
                best = max(best, int(row.get(key) or 0))
            except (TypeError, ValueError):
                continue
    return best


def _trade_cal_provider_acceptance_promotion_audit(
    snapshot: Mapping[str, Any],
    trade_cal_physical: Mapping[str, Any],
    provider_runbook: Mapping[str, Any],
    current_evidence_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    evidence_rows = _trade_cal_provider_acceptance_evidence_rows(snapshot)
    min_window_days = int(provider_runbook.get("minimum_acceptance_window_days") or 730)
    max_window_days = _max_int(evidence_rows, "window_days", "acceptance_window_days", "calendar_window_days")
    max_row_count = _max_int(evidence_rows, "row_count", "rows", "fetched_row_count", "trade_cal_row_count")
    max_open_days = _max_int(evidence_rows, "open_day_count", "open_days")
    max_failure_mode_count = _max_int(evidence_rows, "failure_mode_count", "failure_mode_validated_count")
    max_replay_scenarios = _max_int(evidence_rows, "freshness_replay_scenario_count", "replay_scenario_count")
    success_statuses = {"success", "succeeded", "validated", "passed", "ready", "provider_backed_acceptance_passed"}
    provider_call_evidence = any(
        str(row.get("api") or row.get("required_api") or "").lower() == "trade_cal"
        and (
            str(row.get("call_status") or row.get("status") or "").lower() in success_statuses
            or row.get("success") is True
        )
        and _row_truthy(row, "external", "provider_called", "tushare_called", "provider_refresh_called")
        for row in evidence_rows
    )
    explicit_promotion_marker = any(
        _row_truthy(
            row,
            "provider_backed_long_window_acceptance_done",
            "provider_backed_trade_cal_acceptance_done",
            "trade_cal_provider_acceptance_done",
        )
        or str(row.get("acceptance_mode") or "") == "provider_backed_trade_cal_long_window"
        for row in evidence_rows
    )
    safe_call_ledger_fields = any(
        str(row.get("api") or row.get("required_api") or "").lower() == "trade_cal"
        and any(row.get(key) not in (None, "", [], {}) for key in ("row_count", "fetched_row_count", "trade_cal_row_count"))
        and any(row.get(key) not in (None, "", [], {}) for key in ("data_date", "window_end", "end_date"))
        and row.get("local_fetched_at") not in (None, "")
        and row.get("call_status") not in (None, "")
        and "token" not in json.dumps(_json_safe(row), ensure_ascii=False).lower()
        for row in evidence_rows
    )
    freshness_replay_done = any(_row_truthy(row, "freshness_replay_passed", "freshness_gate_replay_passed") for row in evidence_rows) and max_replay_scenarios >= 8
    failure_modes_done = any(_row_truthy(row, "failure_modes_validated", "failure_mode_qa_passed") for row in evidence_rows) and max_failure_mode_count >= 4
    local_artifact_ready = bool(trade_cal_physical.get("local_trade_cal_physical_validation_done")) and not trade_cal_physical.get("blockers")
    current_boundary_ready = (
        current_evidence_contract.get("schema_version") == "data_health_current_evidence_freshness_qa.v1"
        and current_evidence_contract.get("current_evidence_requires_expected_trade_date") is True
        and current_evidence_contract.get("blocks_composite_score") is True
        and current_evidence_contract.get("blocks_support_factors") is True
        and current_evidence_contract.get("blocks_evidence_preview") is True
        and current_evidence_contract.get("blocks_next_session_bridge_preview") is True
        and current_evidence_contract.get("does_not_modify_strategy_action") is True
    )
    rows = [
        _trade_cal_provider_acceptance_promotion_row(
            "explicit_provider_call_ledger",
            provider_call_evidence,
            evidence=f"trade_cal provider call evidence rows={len(evidence_rows)}",
        ),
        _trade_cal_provider_acceptance_promotion_row(
            "safe_call_ledger_fields",
            safe_call_ledger_fields,
            evidence="Provider-backed acceptance needs api, row_count, data/window date, local_fetched_at, call_status, and redacted error fields.",
        ),
        _trade_cal_provider_acceptance_promotion_row(
            "minimum_long_window",
            max_window_days >= min_window_days or max_row_count >= min_window_days,
            evidence=f"observed_window_days={max_window_days}; observed_row_count={max_row_count}; required_days={min_window_days}",
        ),
        _trade_cal_provider_acceptance_promotion_row(
            "schema_and_local_artifact_cross_check",
            local_artifact_ready
            and int(trade_cal_physical.get("window_days") or 0) >= REAL_TRADE_CAL_MIN_WINDOW_DAYS
            and int(trade_cal_physical.get("open_day_count") or 0) >= REAL_TRADE_CAL_MIN_OPEN_DAYS,
            evidence=f"local_artifact_ready={local_artifact_ready}; physical_status={trade_cal_physical.get('status')}",
        ),
        _trade_cal_provider_acceptance_promotion_row(
            "open_closed_current_coverage",
            max_open_days >= REAL_TRADE_CAL_MIN_OPEN_DAYS
            and trade_cal_physical.get("today_row_found") is True
            and bool(trade_cal_physical.get("latest_completed_trading_day")),
            evidence=f"observed_open_days={max_open_days}; today_row_found={trade_cal_physical.get('today_row_found')}",
        ),
        _trade_cal_provider_acceptance_promotion_row(
            "freshness_gate_replay_evidence",
            freshness_replay_done,
            evidence=f"freshness_replay_scenario_count={max_replay_scenarios}",
        ),
        _trade_cal_provider_acceptance_promotion_row(
            "failure_mode_evidence",
            failure_modes_done,
            evidence=f"failure_mode_validated_count={max_failure_mode_count}",
        ),
        _trade_cal_provider_acceptance_promotion_row(
            "current_evidence_boundary_rechecked",
            current_boundary_ready,
            evidence=f"current_evidence_status={current_evidence_contract.get('status')}",
        ),
        _trade_cal_provider_acceptance_promotion_row(
            "explicit_promotion_marker",
            explicit_promotion_marker,
            evidence="A prior provider-backed acceptance task must explicitly mark the long-window trade_cal acceptance as done.",
        ),
        _trade_cal_provider_acceptance_promotion_row(
            "audit_is_read_only_no_provider_call",
            True,
            evidence="GET /api/data-health/cache only audits local evidence and never refreshes trade_cal.",
            required_for_promotion=False,
        ),
    ]
    blockers = [row["criterion"] for row in rows if row["required_for_promotion"] and not row["passed"]]
    promotion_ready = not blockers
    contract = {
        "schema_version": "data_health_trade_cal_provider_acceptance_promotion_audit.v1",
        "status": "trade_cal_provider_acceptance_promotion_ready"
        if promotion_ready
        else "trade_cal_provider_acceptance_promotion_pending",
        "scope": "local_snapshot_evidence_promotion_audit_no_provider_execution",
        "ltg": "LTG-01/LTG-02",
        "promotion_ready": promotion_ready,
        "provider_backed_long_window_acceptance_done": promotion_ready,
        "production_freshness_gate_complete": False,
        "provider_refresh_called_by_audit": False,
        "provider_evidence_from_prior_task": provider_call_evidence,
        "explicit_promotion_marker_found": explicit_promotion_marker,
        "safe_call_ledger_fields_present": safe_call_ledger_fields,
        "evidence_row_count": len(evidence_rows),
        "observed_window_days": max_window_days,
        "observed_row_count": max_row_count,
        "observed_open_day_count": max_open_days,
        "minimum_acceptance_window_days": min_window_days,
        "freshness_replay_scenario_count": max_replay_scenarios,
        "failure_mode_validated_count": max_failure_mode_count,
        "local_artifact_cross_check_done": local_artifact_ready,
        "current_evidence_boundary_ready": current_boundary_ready,
        "row_count": len(rows),
        "blocking_criterion_count": len(blockers),
        "blockers": blockers,
        "cache_only": True,
        "read_only_snapshot_audit": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This audit decides whether prior provider-backed trade_cal evidence is sufficient to promote acceptance. It does not call Tushare and keeps production freshness incomplete until evidence is explicit.",
    }
    return contract, rows


def _freshness_production_blocker_row(
    phase: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    blockers: list[str] | None = None,
    production_blocker: bool | None = None,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool((not passed) if production_blocker is None else production_blocker),
        "blockers": blockers or [],
        "blocker_count": len(blockers or []),
        "evidence": evidence,
        "cache_only": True,
        "read_only_snapshot_audit": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _freshness_production_blocker_audit(
    *,
    freshness_acceptance_summary: Mapping[str, Any],
    freshness_sample: Mapping[str, Any],
    trade_cal_physical: Mapping[str, Any],
    provider_runbook: Mapping[str, Any],
    provider_promotion: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    decision_surface: Mapping[str, Any],
    producer_coverage: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sample_passed = bool(
        freshness_sample.get("status") == "local_sample_validation_passed"
        and int(freshness_sample.get("failed_count") or 0) == 0
        and freshness_sample.get("uses_actual_freshness_gate") is True
    )
    local_artifact_ready = bool(trade_cal_physical.get("local_trade_cal_physical_validation_done"))
    provider_promotion_ready = bool(provider_promotion.get("promotion_ready"))
    current_boundary_ready = bool(
        current_evidence.get("current_evidence_requires_expected_trade_date") is True
        and current_evidence.get("blocks_composite_score") is True
        and current_evidence.get("blocks_support_factors") is True
        and current_evidence.get("blocks_evidence_preview") is True
        and current_evidence.get("blocks_next_session_bridge_preview") is True
        and current_evidence.get("does_not_modify_strategy_action") is True
    )
    decision_surface_clear = int(decision_surface.get("blocked_surface_count") or 0) == 0
    producer_coverage_clear = int(producer_coverage.get("blocked_producer_count") or 0) == 0
    runbook_ready = bool(
        provider_runbook.get("schema_version") == "data_health_trade_cal_provider_acceptance_runbook.v1"
        and provider_runbook.get("local_runbook_ready") is True
        and provider_runbook.get("provider_refresh_called_by_runbook") is False
    )
    rows = [
        _freshness_production_blocker_row(
            "freshness_acceptance_matrix",
            "passed_local_contract" if freshness_acceptance_summary.get("status") == "acceptance_matrix_ready" else "blocked_contract_missing",
            freshness_acceptance_summary.get("status") == "acceptance_matrix_ready"
            and freshness_acceptance_summary.get("trade_cal_long_window_validation_done") is False,
            evidence=(
                f"status={freshness_acceptance_summary.get('status')}; "
                "matrix remains local and does not claim real trade_cal acceptance."
            ),
            production_blocker=False,
        ),
        _freshness_production_blocker_row(
            "long_window_replay_fixture",
            "passed_local_fixture" if sample_passed else "blocked_fixture_regression",
            sample_passed,
            evidence=f"sample_status={freshness_sample.get('status')}; failed={freshness_sample.get('failed_count')}",
            blockers=[] if sample_passed else ["freshness_long_window_sample_regression"],
        ),
        _freshness_production_blocker_row(
            "local_trade_cal_artifact",
            "passed_local_artifact" if local_artifact_ready else "pending_local_artifact_validation",
            local_artifact_ready,
            evidence=(
                f"physical_status={trade_cal_physical.get('status')}; "
                f"blocker_count={trade_cal_physical.get('blocker_count')}"
            ),
            blockers=list(trade_cal_physical.get("blockers") or []),
        ),
        _freshness_production_blocker_row(
            "provider_acceptance_runbook",
            "passed_local_runbook" if runbook_ready else "blocked_runbook_contract",
            runbook_ready,
            evidence=(
                f"runbook_status={provider_runbook.get('status')}; "
                f"pending_execution={provider_runbook.get('pending_execution_count')}"
            ),
            production_blocker=False,
        ),
        _freshness_production_blocker_row(
            "provider_backed_trade_cal_acceptance",
            "passed_provider_acceptance" if provider_promotion_ready else "pending_provider_acceptance",
            provider_promotion_ready,
            evidence=(
                f"promotion_status={provider_promotion.get('status')}; "
                f"blocker_count={provider_promotion.get('blocking_criterion_count')}; "
                f"evidence_row_count={provider_promotion.get('evidence_row_count')}"
            ),
            blockers=list(provider_promotion.get("blockers") or []),
        ),
        _freshness_production_blocker_row(
            "current_evidence_boundary",
            "passed_boundary_contract" if current_boundary_ready else "blocked_boundary_contract",
            current_boundary_ready,
            evidence=(
                f"candidate_status={current_evidence.get('current_evidence_candidate_status')}; "
                f"current_blockers={current_evidence.get('current_evidence_blocker_count')}"
            ),
            blockers=[] if current_boundary_ready else list(current_evidence.get("current_evidence_blockers") or []),
            production_blocker=not current_boundary_ready,
        ),
        _freshness_production_blocker_row(
            "decision_surface_isolation",
            "passed_no_visible_surface_blockers" if decision_surface_clear else "blocked_visible_surface_leak",
            decision_surface_clear,
            evidence=(
                f"decision_surface_status={decision_surface.get('status')}; "
                f"blocked_surfaces={decision_surface.get('blocked_surface_count')}"
            ),
            blockers=list(decision_surface.get("blocked_surface_keys") or []),
        ),
        _freshness_production_blocker_row(
            "producer_expected_date_coverage",
            "passed_no_observed_producer_blockers" if producer_coverage_clear else "blocked_producer_freshness_fields",
            producer_coverage_clear,
            evidence=(
                f"producer_status={producer_coverage.get('status')}; "
                f"blocked_producers={producer_coverage.get('blocked_producer_count')}; "
                f"observed_producers={producer_coverage.get('observed_producer_count')}"
            ),
            blockers=list(producer_coverage.get("blocked_producer_keys") or []),
        ),
    ]
    production_blockers = [row for row in rows if row.get("production_blocker")]
    production_ready = not production_blockers
    contract = {
        "schema_version": "data_health_freshness_production_blocker_audit.v1",
        "status": "freshness_production_ready_for_provider_promotion" if production_ready else "freshness_production_blockers_visible",
        "scope": "local_read_only_freshness_production_blocker_audit_no_provider_execution",
        "ltg": "LTG-01/LTG-11",
        "production_ready": production_ready,
        "provider_backed_trade_cal_acceptance_done": provider_promotion_ready,
        "production_freshness_gate_complete": False,
        "row_count": len(rows),
        "production_blocker_count": len(production_blockers),
        "production_blockers": [row["phase"] for row in production_blockers],
        "local_trade_cal_artifact_ready": local_artifact_ready,
        "provider_promotion_ready": provider_promotion_ready,
        "current_evidence_boundary_ready": current_boundary_ready,
        "decision_surface_clear": decision_surface_clear,
        "producer_coverage_clear": producer_coverage_clear,
        "cache_only": True,
        "read_only_snapshot_audit": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "note": "This audit centralizes remaining LTG-01 production blockers. It does not call providers, does not rescore packets, and does not prove production completion.",
    }
    return contract, rows


def _freshness_provider_acceptance_readiness_row(
    criterion: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    required_before_promotion: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "required_before_promotion": bool(required_before_promotion),
        "evidence": evidence,
        "cache_only": True,
        "read_only_receipt": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _freshness_provider_acceptance_readiness_receipt(
    *,
    provider_runbook: Mapping[str, Any],
    provider_promotion: Mapping[str, Any],
    freshness_blockers: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    decision_surface: Mapping[str, Any],
    producer_coverage: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    runbook_ready = bool(
        provider_runbook.get("schema_version") == "data_health_trade_cal_provider_acceptance_runbook.v1"
        and provider_runbook.get("local_runbook_ready") is True
        and provider_runbook.get("post_task_route") == "POST /api/tasks/refresh-tushare-facts"
        and provider_runbook.get("required_api") == "trade_cal"
    )
    cache_boundary_safe = bool(
        provider_runbook.get("provider_refresh_called_by_runbook") is False
        and provider_promotion.get("provider_refresh_called_by_audit") is False
        and provider_promotion.get("external_calls_triggered") is False
    )
    current_boundary_ready = bool(
        current_evidence.get("current_evidence_requires_expected_trade_date") is True
        and current_evidence.get("blocks_composite_score") is True
        and current_evidence.get("blocks_support_factors") is True
        and current_evidence.get("blocks_evidence_preview") is True
        and current_evidence.get("blocks_next_session_bridge_preview") is True
        and current_evidence.get("does_not_modify_strategy_action") is True
    )
    decision_surface_clear = int(decision_surface.get("blocked_surface_count") or 0) == 0
    producer_coverage_clear = int(producer_coverage.get("blocked_producer_count") or 0) == 0
    promotion_ready = bool(provider_promotion.get("promotion_ready"))
    production_blockers = list(freshness_blockers.get("production_blockers") or [])
    promotion_blockers = list(provider_promotion.get("blockers") or [])
    missing_evidence_items = sorted({str(item) for item in production_blockers + promotion_blockers if item})
    ready_for_explicit_provider_task = bool(
        runbook_ready
        and cache_boundary_safe
        and current_boundary_ready
        and decision_surface_clear
        and producer_coverage_clear
    )
    rows = [
        _freshness_provider_acceptance_readiness_row(
            "explicit_post_task_route_ready",
            "passed_static_policy" if runbook_ready else "blocked_runbook_missing",
            runbook_ready,
            evidence=(
                f"post_task_route={provider_runbook.get('post_task_route')}; "
                f"required_api={provider_runbook.get('required_api')}"
            ),
        ),
        _freshness_provider_acceptance_readiness_row(
            "cache_and_render_do_not_call_provider",
            "passed_no_provider_call" if cache_boundary_safe else "blocked_external_call_boundary",
            cache_boundary_safe,
            evidence="GET cache, React render, runbook, and promotion audit are local/read-only until explicit POST task.",
        ),
        _freshness_provider_acceptance_readiness_row(
            "current_evidence_boundary_ready",
            "passed_boundary_contract" if current_boundary_ready else "blocked_current_evidence_boundary",
            current_boundary_ready,
            evidence=(
                f"candidate_status={current_evidence.get('current_evidence_candidate_status')}; "
                f"blocker_count={current_evidence.get('current_evidence_blocker_count')}"
            ),
        ),
        _freshness_provider_acceptance_readiness_row(
            "decision_surface_isolation_clear",
            "passed_no_visible_leak" if decision_surface_clear else "blocked_visible_surface_leak",
            decision_surface_clear,
            evidence=f"blocked_surface_count={decision_surface.get('blocked_surface_count')}",
        ),
        _freshness_provider_acceptance_readiness_row(
            "producer_expected_date_coverage_clear",
            "passed_no_observed_producer_blockers" if producer_coverage_clear else "blocked_producer_fields",
            producer_coverage_clear,
            evidence=f"blocked_producer_count={producer_coverage.get('blocked_producer_count')}",
        ),
        _freshness_provider_acceptance_readiness_row(
            "provider_evidence_ticket",
            "ready_for_promotion_review" if promotion_ready else "pending_provider_execution_evidence",
            promotion_ready,
            evidence=(
                f"promotion_status={provider_promotion.get('status')}; "
                f"promotion_blockers={len(promotion_blockers)}; "
                f"evidence_rows={provider_promotion.get('evidence_row_count')}"
            ),
        ),
        _freshness_provider_acceptance_readiness_row(
            "production_completion_boundary",
            "enforced_not_complete",
            True,
            evidence="Provider readiness or promotion review cannot mark production_freshness_gate_complete=true.",
            required_before_promotion=False,
        ),
    ]
    blocked_rows = [row["criterion"] for row in rows if row["required_before_promotion"] and not row["passed"]]
    contract = {
        "schema_version": "data_health_freshness_provider_acceptance_readiness_receipt.v1",
        "status": "provider_acceptance_receipt_ready_for_promotion_review"
        if promotion_ready
        else "provider_acceptance_receipt_ready_execution_pending"
        if ready_for_explicit_provider_task
        else "provider_acceptance_receipt_blocked",
        "scope": "local_readiness_receipt_no_provider_execution",
        "ltg": "LTG-01/LTG-02/LTG-11",
        "local_receipt_ready": not blocked_rows or ready_for_explicit_provider_task,
        "ready_for_explicit_provider_task": ready_for_explicit_provider_task,
        "allowed_next_step": "review_prior_provider_evidence_for_promotion"
        if promotion_ready
        else "explicit_post_task_trade_cal_provider_acceptance"
        if ready_for_explicit_provider_task
        else "resolve_local_freshness_acceptance_blockers",
        "not_allowed_next_steps": [
            "GET /api/data-health/cache provider refresh",
            "React render provider refresh",
            "synthetic fixture promotion",
            "local Parquet-only provider acceptance",
            "strategy action mutation",
            "real trade execution",
        ],
        "provider_backed_long_window_acceptance_done": promotion_ready,
        "production_freshness_gate_complete": False,
        "provider_refresh_called_by_receipt": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "row_count": len(rows),
        "blocked_readiness_count": len(blocked_rows),
        "blocked_readiness_items": blocked_rows,
        "missing_evidence_items": missing_evidence_items,
        "provider_promotion_ready": promotion_ready,
        "provider_evidence_row_count": int(provider_promotion.get("evidence_row_count") or 0),
        "production_blocker_count": int(freshness_blockers.get("production_blocker_count") or 0),
        "rows": rows,
        "note": "This receipt tells the next safe LTG-01 step. It never calls Tushare and cannot promote local fixtures, Parquet checks, or runbooks to production completion.",
    }
    return contract, rows


def _freshness_provider_acceptance_activation_row(
    criterion: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    required_before_activation: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "required_before_activation": bool(required_before_activation),
        "evidence": evidence,
        "cache_only": True,
        "read_only_receipt": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _freshness_provider_acceptance_activation_receipt(
    *,
    provider_runbook: Mapping[str, Any],
    provider_promotion: Mapping[str, Any],
    freshness_blockers: Mapping[str, Any],
    readiness_receipt: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    decision_surface: Mapping[str, Any],
    producer_coverage: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    runbook_ready = bool(provider_runbook.get("local_runbook_ready"))
    ready_for_explicit_task = bool(readiness_receipt.get("ready_for_explicit_provider_task"))
    promotion_ready = bool(provider_promotion.get("promotion_ready"))
    current_boundary_ready = bool(
        current_evidence.get("current_evidence_requires_expected_trade_date") is True
        and current_evidence.get("blocks_composite_score") is True
        and current_evidence.get("blocks_support_factors") is True
        and current_evidence.get("blocks_evidence_preview") is True
        and current_evidence.get("blocks_next_session_bridge_preview") is True
        and current_evidence.get("does_not_modify_strategy_action") is True
    )
    decision_surface_clear = int(decision_surface.get("blocked_surface_count") or 0) == 0
    producer_coverage_clear = int(producer_coverage.get("blocked_producer_count") or 0) == 0
    local_activation_receipt_ready = bool(
        runbook_ready
        and readiness_receipt.get("schema_version")
        == "data_health_freshness_provider_acceptance_readiness_receipt.v1"
        and readiness_receipt.get("provider_refresh_called_by_receipt") is False
        and current_boundary_ready
    )
    rows = [
        _freshness_provider_acceptance_activation_row(
            "readiness_receipt_visible",
            "passed_local_receipt" if local_activation_receipt_ready else "blocked_readiness_receipt",
            local_activation_receipt_ready,
            evidence=(
                f"readiness_status={readiness_receipt.get('status')}; "
                f"ready_for_explicit_task={ready_for_explicit_task}"
            ),
        ),
        _freshness_provider_acceptance_activation_row(
            "explicit_post_task_required",
            "passed_static_policy" if ready_for_explicit_task else "blocked_local_readiness",
            ready_for_explicit_task,
            evidence="Only a future explicit POST task may call Tushare trade_cal provider acceptance.",
        ),
        _freshness_provider_acceptance_activation_row(
            "provider_execution_evidence_required",
            "pending_provider_execution_evidence",
            False,
            evidence=(
                f"provider_evidence_row_count={provider_promotion.get('evidence_row_count')}; "
                f"provider_call_evidence={provider_promotion.get('provider_evidence_from_prior_task')}"
            ),
        ),
        _freshness_provider_acceptance_activation_row(
            "promotion_review_required",
            "ready_for_promotion_review" if promotion_ready else "pending_promotion_review",
            promotion_ready,
            evidence=(
                f"promotion_status={provider_promotion.get('status')}; "
                f"promotion_blockers={provider_promotion.get('blocking_criterion_count')}"
            ),
        ),
        _freshness_provider_acceptance_activation_row(
            "current_evidence_boundary_preserved",
            "passed_boundary_contract" if current_boundary_ready else "blocked_current_boundary",
            current_boundary_ready,
            evidence=f"current_evidence_status={current_evidence.get('current_evidence_candidate_status')}",
        ),
        _freshness_provider_acceptance_activation_row(
            "decision_surface_isolation_preserved",
            "passed_no_visible_surface_leak" if decision_surface_clear else "blocked_surface_leak",
            decision_surface_clear,
            evidence=f"blocked_surface_count={decision_surface.get('blocked_surface_count')}",
        ),
        _freshness_provider_acceptance_activation_row(
            "producer_expected_date_coverage_preserved",
            "passed_no_observed_producer_blockers" if producer_coverage_clear else "blocked_producer_fields",
            producer_coverage_clear,
            evidence=f"blocked_producer_count={producer_coverage.get('blocked_producer_count')}",
        ),
        _freshness_provider_acceptance_activation_row(
            "fixture_and_local_artifact_not_acceptance",
            "enforced_not_provider_acceptance",
            True,
            evidence="Synthetic fixtures, local Parquet checks, runbooks, and this activation receipt are not provider-backed acceptance.",
            required_before_activation=False,
        ),
        _freshness_provider_acceptance_activation_row(
            "cache_render_provider_boundary",
            "passed_no_provider_call",
            True,
            evidence="GET cache and React render do not call Tushare, DeepSeek, or GitHub and do not create provider tasks.",
            required_before_activation=False,
        ),
        _freshness_provider_acceptance_activation_row(
            "production_completion_boundary",
            "enforced_not_complete",
            True,
            evidence="Provider acceptance activation receipt cannot mark production_freshness_gate_complete=true.",
            required_before_activation=False,
        ),
        _freshness_provider_acceptance_activation_row(
            "no_trade_or_action_boundary",
            "passed",
            True,
            evidence="Freshness activation receipt does not execute trades and does not mutate strategy action.",
            required_before_activation=False,
        ),
    ]
    blocking_rows = [row for row in rows if row["required_before_activation"] and not row["passed"]]
    missing_evidence_items = sorted(
        {
            *[str(item) for item in provider_promotion.get("blockers", []) if item],
            *[str(item) for item in freshness_blockers.get("production_blockers", []) if item],
            *[str(item) for item in readiness_receipt.get("missing_evidence_items", []) if item],
            "provider-backed trade_cal task execution",
            "provider call ledger with safe fields",
            "explicit production promotion marker",
        }
    )
    contract = {
        "schema_version": "data_health_freshness_provider_acceptance_activation_receipt.v1",
        "status": "provider_acceptance_activation_ready_execution_pending"
        if local_activation_receipt_ready and ready_for_explicit_task
        else "provider_acceptance_activation_blocked_local_readiness"
        if local_activation_receipt_ready
        else "provider_acceptance_activation_blocked_local_contract",
        "scope": "local_activation_receipt_no_provider_execution",
        "ltg": "LTG-01/LTG-02/LTG-11",
        "local_activation_receipt_ready": local_activation_receipt_ready,
        "ready_for_explicit_provider_task": ready_for_explicit_task,
        "allowed_next_step": "explicit_post_task_trade_cal_provider_acceptance"
        if ready_for_explicit_task
        else "resolve_local_freshness_acceptance_blockers",
        "not_allowed_next_steps": [
            "GET /api/data-health/cache provider refresh",
            "React render provider refresh",
            "direct Tushare call from page render",
            "synthetic fixture promotion",
            "local Parquet-only provider acceptance",
            "activation receipt as production freshness completion",
            "strategy action mutation",
            "real trade execution",
        ],
        "missing_evidence_items": missing_evidence_items,
        "provider_backed_long_window_acceptance_done": promotion_ready,
        "provider_acceptance_task_executed_by_receipt": False,
        "provider_refresh_called_by_receipt": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "production_freshness_gate_complete": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "provider_evidence_row_count": int(provider_promotion.get("evidence_row_count") or 0),
        "provider_promotion_ready": promotion_ready,
        "production_blocker_count": int(freshness_blockers.get("production_blocker_count") or 0),
        "blocking_criterion_count": len(blocking_rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_freshness_provider_acceptance_activation_receipt",
                "source": "data health local provider acceptance contracts",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_activation_receipt_provider_execution_pending",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This receipt is a local activation checklist for future explicit trade_cal provider acceptance. It does not call Tushare, create tasks, promote fixtures/artifacts/runbooks, execute trades, mutate action, or prove production completion.",
    }
    return contract, rows


def read_data_health_timeline_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}
    local_tushare_refresh_packet = _local_tushare_refresh_packet_for_data_health()
    if local_tushare_refresh_packet:
        snapshot_map = dict(snapshot_map)
        snapshot_map.setdefault("command_center_tushare_refresh_packet", local_tushare_refresh_packet)
        snapshot_map.setdefault("tushare_refresh_packet", local_tushare_refresh_packet)
    local_tushare_refresh_packet_summary = _local_tushare_refresh_packet_summary(local_tushare_refresh_packet)

    timeline_value = _first_value(snapshot_map, "data_health_timeline", "command_center_data_health_timeline")
    recovery_actions_value = _first_value(
        snapshot_map,
        "data_health_timeline_recovery_actions",
        "command_center_data_health_timeline_recovery_actions",
    )
    visibility_summary = _first_mapping(
        snapshot_map,
        "data_health_visibility_summary",
        "command_center_data_health_visibility_summary",
    )
    provider_cockpit = _first_mapping(snapshot_map, "provider_data_capability_cockpit")
    provider_recovery_matrix = _first_value(snapshot_map, "provider_recovery_matrix")
    capability_matrix = _first_value(snapshot_map, "a_share_capability_matrix")
    health_ledger = _first_value(snapshot_map, "data_health_ledger", "command_center_data_health_ledger")
    data_freshness = _first_mapping(snapshot_map, "data_freshness")
    data_coverage = _first_mapping(snapshot_map, "data_coverage")
    data_gap_report = _first_value(snapshot_map, "data_gap_report")
    home_issue_brief = _first_value(snapshot_map, "home_data_issue_brief")
    issue_explainer = _first_value(snapshot_map, "data_issue_explainer")
    freshness_acceptance_matrix = _freshness_acceptance_matrix_rows()
    freshness_acceptance_summary = _freshness_acceptance_summary(freshness_acceptance_matrix)
    freshness_long_window_sample_validation = _freshness_long_window_sample_validation()
    freshness_long_window_sample_rows = _as_list(freshness_long_window_sample_validation.get("rows"))
    trade_cal_physical_validation = _local_trade_cal_physical_validation()
    trade_cal_physical_validation_rows = _as_list(trade_cal_physical_validation.get("rows"))
    trade_cal_provider_acceptance_runbook, trade_cal_provider_acceptance_runbook_rows = (
        _trade_cal_provider_acceptance_runbook(trade_cal_physical_validation)
    )
    current_evidence_freshness_qa_contract, current_evidence_freshness_qa_rows = (
        _current_evidence_freshness_qa_contract(
            data_freshness,
            freshness_long_window_sample_validation,
            trade_cal_physical_validation,
        )
    )
    current_evidence_decision_surface_audit, current_evidence_decision_surface_rows = (
        _current_evidence_decision_surface_audit(
            snapshot_map,
            current_evidence_freshness_qa_contract,
        )
    )
    current_evidence_producer_coverage_audit, current_evidence_producer_coverage_rows = (
        _current_evidence_producer_coverage_audit(snapshot_map)
    )
    trade_cal_provider_acceptance_promotion_audit, trade_cal_provider_acceptance_promotion_rows = (
        _trade_cal_provider_acceptance_promotion_audit(
            snapshot_map,
            trade_cal_physical_validation,
            trade_cal_provider_acceptance_runbook,
            current_evidence_freshness_qa_contract,
        )
    )
    freshness_production_blocker_audit, freshness_production_blocker_rows = (
        _freshness_production_blocker_audit(
            freshness_acceptance_summary=freshness_acceptance_summary,
            freshness_sample=freshness_long_window_sample_validation,
            trade_cal_physical=trade_cal_physical_validation,
            provider_runbook=trade_cal_provider_acceptance_runbook,
            provider_promotion=trade_cal_provider_acceptance_promotion_audit,
            current_evidence=current_evidence_freshness_qa_contract,
            decision_surface=current_evidence_decision_surface_audit,
            producer_coverage=current_evidence_producer_coverage_audit,
        )
    )
    freshness_provider_acceptance_readiness_receipt, freshness_provider_acceptance_readiness_rows = (
        _freshness_provider_acceptance_readiness_receipt(
            provider_runbook=trade_cal_provider_acceptance_runbook,
            provider_promotion=trade_cal_provider_acceptance_promotion_audit,
            freshness_blockers=freshness_production_blocker_audit,
            current_evidence=current_evidence_freshness_qa_contract,
            decision_surface=current_evidence_decision_surface_audit,
            producer_coverage=current_evidence_producer_coverage_audit,
        )
    )
    freshness_provider_acceptance_activation_receipt, freshness_provider_acceptance_activation_rows = (
        _freshness_provider_acceptance_activation_receipt(
            provider_runbook=trade_cal_provider_acceptance_runbook,
            provider_promotion=trade_cal_provider_acceptance_promotion_audit,
            freshness_blockers=freshness_production_blocker_audit,
            readiness_receipt=freshness_provider_acceptance_readiness_receipt,
            current_evidence=current_evidence_freshness_qa_contract,
            decision_surface=current_evidence_decision_surface_audit,
            producer_coverage=current_evidence_producer_coverage_audit,
        )
    )

    timeline_rows = _combined_rows(
        (timeline_value, "data_health_timeline", "event"),
        (data_freshness, "data_freshness", "freshness"),
        (data_coverage, "data_coverage", "coverage"),
    )
    recovery_action_rows = _rows(recovery_actions_value, source="data_health_timeline_recovery_actions")
    provider_rows = _combined_rows(
        (provider_cockpit, "provider_data_capability_cockpit", "provider"),
        (provider_recovery_matrix, "provider_recovery_matrix", "provider"),
    )
    capability_rows = _rows(capability_matrix, source="a_share_capability_matrix", text_key="capability")
    ledger_rows = _rows(health_ledger, source="data_health_ledger", text_key="ledger")
    gap_rows = _combined_rows(
        (data_gap_report, "data_gap_report", "gap"),
        (home_issue_brief, "home_data_issue_brief", "issue"),
        (issue_explainer, "data_issue_explainer", "issue"),
    )

    has_specific_cache = any(
        bool(item)
        for item in (
            timeline_rows,
            recovery_action_rows,
            visibility_summary,
            provider_rows,
            capability_rows,
            ledger_rows,
            gap_rows,
            local_tushare_refresh_packet_summary.get("available"),
        )
    )
    status = "ready" if timeline_rows or provider_rows or capability_rows or ledger_rows else "partial" if has_specific_cache or snapshot else "cache_missing"

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "snapshot_available": bool(snapshot),
        "source_packet_keys": [
            "data_health_timeline",
            "command_center_data_health_timeline",
            "data_health_timeline_recovery_actions",
            "command_center_data_health_timeline_recovery_actions",
            "data_health_visibility_summary",
            "command_center_data_health_visibility_summary",
            "provider_data_capability_cockpit",
            "provider_recovery_matrix",
            "a_share_capability_matrix",
            "data_health_ledger",
            "command_center_data_health_ledger",
            "data_freshness",
            "data_coverage",
            "data_gap_report",
            "home_data_issue_brief",
            "data_issue_explainer",
            "freshness_acceptance_matrix",
            "freshness_long_window_sample_validation",
            "trade_cal_physical_validation",
            "trade_cal_provider_acceptance_runbook",
            "trade_cal_provider_acceptance_promotion_audit",
            "freshness_production_blocker_audit",
            "freshness_provider_acceptance_readiness_receipt",
            "freshness_provider_acceptance_activation_receipt",
            "current_evidence_freshness_qa_contract",
            "current_evidence_decision_surface_audit",
            "current_evidence_producer_coverage_audit",
            "command_center_tushare_refresh_packet",
        ],
        "summary": visibility_summary.get("summary")
        or visibility_summary.get("headline")
        or "数据健康时间线 cache 只读展示；页面打开不会 ping provider 或刷新数据。",
        "data_health_visibility_summary": visibility_summary,
        "provider_data_capability_cockpit": provider_cockpit,
        "a_share_capability_matrix": _safe_value(capability_matrix),
        "data_health_timeline": _safe_value(timeline_value),
        "data_health_timeline_recovery_actions": _safe_value(recovery_actions_value),
        "data_health_ledger": _safe_value(health_ledger),
        "data_gap_report": _safe_value(data_gap_report),
        "home_data_issue_brief": _safe_value(home_issue_brief),
        "data_issue_explainer": _safe_value(issue_explainer),
        "data_freshness": data_freshness,
        "data_coverage": data_coverage,
        "freshness_acceptance_matrix": freshness_acceptance_matrix,
        "freshness_acceptance_summary": freshness_acceptance_summary,
        "freshness_long_window_sample_validation": freshness_long_window_sample_validation,
        "freshness_long_window_sample_rows": freshness_long_window_sample_rows,
        "trade_cal_physical_validation": trade_cal_physical_validation,
        "trade_cal_physical_validation_rows": trade_cal_physical_validation_rows,
        "trade_cal_provider_acceptance_runbook": trade_cal_provider_acceptance_runbook,
        "trade_cal_provider_acceptance_runbook_rows": trade_cal_provider_acceptance_runbook_rows,
        "local_tushare_refresh_packet_summary": local_tushare_refresh_packet_summary,
        "trade_cal_provider_acceptance_promotion_audit": trade_cal_provider_acceptance_promotion_audit,
        "trade_cal_provider_acceptance_promotion_rows": trade_cal_provider_acceptance_promotion_rows,
        "freshness_production_blocker_audit": freshness_production_blocker_audit,
        "freshness_production_blocker_rows": freshness_production_blocker_rows,
        "freshness_provider_acceptance_readiness_receipt": freshness_provider_acceptance_readiness_receipt,
        "freshness_provider_acceptance_readiness_rows": freshness_provider_acceptance_readiness_rows,
        "freshness_provider_acceptance_activation_receipt": freshness_provider_acceptance_activation_receipt,
        "freshness_provider_acceptance_activation_rows": freshness_provider_acceptance_activation_rows,
        "current_evidence_freshness_qa_contract": current_evidence_freshness_qa_contract,
        "current_evidence_freshness_qa_rows": current_evidence_freshness_qa_rows,
        "current_evidence_decision_surface_audit": current_evidence_decision_surface_audit,
        "current_evidence_decision_surface_rows": current_evidence_decision_surface_rows,
        "current_evidence_producer_coverage_audit": current_evidence_producer_coverage_audit,
        "current_evidence_producer_coverage_rows": current_evidence_producer_coverage_rows,
        "timeline_rows": timeline_rows,
        "recovery_action_rows": recovery_action_rows,
        "provider_rows": provider_rows,
        "capability_rows": capability_rows,
        "ledger_rows": ledger_rows,
        "gap_rows": gap_rows,
        "counts": {
            "timeline_count": len(timeline_rows),
            "provider_count": len(provider_rows),
            "capability_count": len(capability_rows),
            "ledger_count": len(ledger_rows),
            "recovery_action_count": len(recovery_action_rows),
            "gap_count": len(gap_rows),
            "freshness_acceptance_scenario_count": len(freshness_acceptance_matrix),
            "freshness_long_window_sample_scenario_count": len(freshness_long_window_sample_rows),
            "freshness_long_window_sample_passed_count": int(freshness_long_window_sample_validation.get("passed_count") or 0),
            "freshness_long_window_sample_failed_count": int(freshness_long_window_sample_validation.get("failed_count") or 0),
            "trade_cal_physical_validation_row_count": len(trade_cal_physical_validation_rows),
            "trade_cal_physical_validation_blocker_count": int(trade_cal_physical_validation.get("blocker_count") or 0),
            "trade_cal_provider_acceptance_runbook_row_count": len(trade_cal_provider_acceptance_runbook_rows),
            "trade_cal_provider_acceptance_pending_count": int(
                trade_cal_provider_acceptance_runbook.get("pending_execution_count") or 0
            ),
            "trade_cal_provider_acceptance_promotion_row_count": len(
                trade_cal_provider_acceptance_promotion_rows
            ),
            "trade_cal_provider_acceptance_promotion_blocker_count": int(
                trade_cal_provider_acceptance_promotion_audit.get("blocking_criterion_count") or 0
            ),
            "trade_cal_provider_acceptance_evidence_row_count": int(
                trade_cal_provider_acceptance_promotion_audit.get("evidence_row_count") or 0
            ),
            "local_tushare_refresh_packet_trade_cal_evidence_row_count": int(
                local_tushare_refresh_packet_summary.get("trade_cal_provider_acceptance_evidence_row_count") or 0
            ),
            "freshness_production_blocker_row_count": len(freshness_production_blocker_rows),
            "freshness_production_blocker_count": int(
                freshness_production_blocker_audit.get("production_blocker_count") or 0
            ),
            "freshness_provider_acceptance_readiness_row_count": len(
                freshness_provider_acceptance_readiness_rows
            ),
            "freshness_provider_acceptance_readiness_blocker_count": int(
                freshness_provider_acceptance_readiness_receipt.get("blocked_readiness_count") or 0
            ),
            "freshness_provider_acceptance_activation_row_count": len(
                freshness_provider_acceptance_activation_rows
            ),
            "freshness_provider_acceptance_activation_blocker_count": int(
                freshness_provider_acceptance_activation_receipt.get("blocking_criterion_count") or 0
            ),
            "current_evidence_freshness_qa_row_count": len(current_evidence_freshness_qa_rows),
            "current_evidence_freshness_qa_blocker_count": int(
                current_evidence_freshness_qa_contract.get("current_evidence_blocker_count") or 0
            ),
            "current_evidence_decision_surface_row_count": len(current_evidence_decision_surface_rows),
            "current_evidence_decision_surface_blocker_count": int(
                current_evidence_decision_surface_audit.get("blocked_surface_count") or 0
            ),
            "current_evidence_producer_coverage_row_count": len(current_evidence_producer_coverage_rows),
            "current_evidence_producer_coverage_blocker_count": int(
                current_evidence_producer_coverage_audit.get("blocked_producer_count") or 0
            ),
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_ping_tushare": True,
            "does_not_ping_akshare": True,
            "does_not_ping_yfinance": True,
            "does_not_ping_supabase": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_refresh_data": True,
            "does_not_run_recovery_actions": True,
            "does_not_run_backtest": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_holdings": True,
            "data_health_is_diagnostic_only": True,
            "post_task_required_for_provider_probe": True,
            "freshness_acceptance_matrix_is_local_contract": True,
            "freshness_acceptance_matrix_calls_trade_cal": False,
            "freshness_long_window_sample_is_local_fixture": True,
            "freshness_long_window_sample_uses_actual_gate": bool(
                freshness_long_window_sample_validation.get("uses_actual_freshness_gate")
            ),
            "freshness_long_window_sample_calls_trade_cal": False,
            "trade_cal_physical_validation_is_local_artifact": True,
            "trade_cal_physical_validation_calls_trade_cal_provider": False,
            "trade_cal_physical_validation_reads_local_rows": True,
            "trade_cal_physical_validation_writes_files": False,
            "local_trade_cal_physical_validation_done": bool(
                trade_cal_physical_validation.get("local_trade_cal_physical_validation_done")
            ),
            "real_trade_cal_long_window_validation_done": False,
            "trade_cal_provider_acceptance_runbook_is_local": True,
            "trade_cal_provider_acceptance_runbook_calls_provider": False,
            "trade_cal_provider_acceptance_still_pending": True,
            "trade_cal_provider_acceptance_promotion_audit_is_local": True,
            "trade_cal_provider_acceptance_promotion_audit_calls_provider": False,
            "local_tushare_refresh_packet_lookup_is_read_only": True,
            "local_tushare_refresh_packet_lookup_calls_provider": False,
            "trade_cal_provider_acceptance_promotion_ready": bool(
                trade_cal_provider_acceptance_promotion_audit.get("promotion_ready")
            ),
            "trade_cal_provider_acceptance_promotion_still_pending": not bool(
                trade_cal_provider_acceptance_promotion_audit.get("promotion_ready")
            ),
            "freshness_production_blocker_audit_is_local": True,
            "freshness_production_blocker_audit_calls_provider": False,
            "freshness_production_ready": bool(freshness_production_blocker_audit.get("production_ready")),
            "freshness_provider_acceptance_readiness_receipt_is_local": True,
            "freshness_provider_acceptance_readiness_receipt_calls_provider": False,
            "freshness_provider_acceptance_ready_for_explicit_task": bool(
                freshness_provider_acceptance_readiness_receipt.get("ready_for_explicit_provider_task")
            ),
            "freshness_provider_acceptance_activation_receipt_is_local": True,
            "freshness_provider_acceptance_activation_receipt_calls_provider": False,
            "freshness_provider_acceptance_activation_receipt_is_not_completion": True,
            "current_evidence_freshness_qa_is_local_contract": True,
            "current_evidence_requires_expected_trade_date": True,
            "historical_samples_are_research_only": True,
            "provider_backed_trade_cal_acceptance_still_pending": True,
            "current_evidence_decision_surface_audit_is_local": True,
            "current_evidence_decision_surface_audit_rescores": False,
            "current_evidence_decision_surface_audit_mutates_action": False,
            "current_evidence_producer_coverage_audit_is_local": True,
            "current_evidence_producer_coverage_audit_builds_missing_packets": False,
            "current_evidence_producer_coverage_requires_expected_trade_date": True,
        },
        "call_ledger": [
            {
                "api": "local_data_health_timeline_cache",
                "source_snapshot": "command_center_latest.json",
                "timeline_count": len(timeline_rows),
                "provider_count": len(provider_rows),
                "capability_count": len(capability_rows),
                "recovery_action_count": len(recovery_action_rows),
                "gap_count": len(gap_rows),
                "freshness_acceptance_scenario_count": len(freshness_acceptance_matrix),
                "freshness_long_window_sample_scenario_count": len(freshness_long_window_sample_rows),
                "freshness_long_window_sample_status": freshness_long_window_sample_validation.get("status"),
                "trade_cal_physical_validation_status": trade_cal_physical_validation.get("status"),
                "trade_cal_physical_validation_done": bool(
                    trade_cal_physical_validation.get("local_trade_cal_physical_validation_done")
                ),
                "trade_cal_physical_validation_blocker_count": int(
                    trade_cal_physical_validation.get("blocker_count") or 0
                ),
                "trade_cal_provider_acceptance_runbook_status": trade_cal_provider_acceptance_runbook.get("status"),
                "trade_cal_provider_acceptance_pending_count": int(
                    trade_cal_provider_acceptance_runbook.get("pending_execution_count") or 0
                ),
                "trade_cal_provider_acceptance_promotion_audit_status": (
                    trade_cal_provider_acceptance_promotion_audit.get("status")
                ),
                "trade_cal_provider_acceptance_promotion_blocker_count": int(
                    trade_cal_provider_acceptance_promotion_audit.get("blocking_criterion_count") or 0
                ),
                "trade_cal_provider_acceptance_evidence_row_count": int(
                    trade_cal_provider_acceptance_promotion_audit.get("evidence_row_count") or 0
                ),
                "local_tushare_refresh_packet_available": bool(
                    local_tushare_refresh_packet_summary.get("available")
                ),
                "local_tushare_refresh_packet_trade_cal_evidence_row_count": int(
                    local_tushare_refresh_packet_summary.get("trade_cal_provider_acceptance_evidence_row_count") or 0
                ),
                "trade_cal_provider_acceptance_promotion_ready": bool(
                    trade_cal_provider_acceptance_promotion_audit.get("promotion_ready")
                ),
                "freshness_production_blocker_audit_status": freshness_production_blocker_audit.get("status"),
                "freshness_production_blocker_count": int(
                    freshness_production_blocker_audit.get("production_blocker_count") or 0
                ),
                "freshness_provider_acceptance_readiness_receipt_status": (
                    freshness_provider_acceptance_readiness_receipt.get("status")
                ),
                "freshness_provider_acceptance_ready_for_explicit_task": bool(
                    freshness_provider_acceptance_readiness_receipt.get("ready_for_explicit_provider_task")
                ),
                "freshness_provider_acceptance_readiness_blocker_count": int(
                    freshness_provider_acceptance_readiness_receipt.get("blocked_readiness_count") or 0
                ),
                "freshness_provider_acceptance_activation_receipt_status": (
                    freshness_provider_acceptance_activation_receipt.get("status")
                ),
                "freshness_provider_acceptance_activation_blocker_count": int(
                    freshness_provider_acceptance_activation_receipt.get("blocking_criterion_count") or 0
                ),
                "freshness_provider_acceptance_activation_ready_for_explicit_task": bool(
                    freshness_provider_acceptance_activation_receipt.get("ready_for_explicit_provider_task")
                ),
                "current_evidence_freshness_qa_status": current_evidence_freshness_qa_contract.get("status"),
                "current_evidence_candidate_status": current_evidence_freshness_qa_contract.get(
                    "current_evidence_candidate_status"
                ),
                "current_evidence_freshness_qa_blocker_count": int(
                    current_evidence_freshness_qa_contract.get("current_evidence_blocker_count") or 0
                ),
                "current_evidence_decision_surface_audit_status": current_evidence_decision_surface_audit.get("status"),
                "current_evidence_decision_surface_blocker_count": int(
                    current_evidence_decision_surface_audit.get("blocked_surface_count") or 0
                ),
                "current_evidence_producer_coverage_audit_status": current_evidence_producer_coverage_audit.get(
                    "status"
                ),
                "current_evidence_producer_coverage_blocker_count": int(
                    current_evidence_producer_coverage_audit.get("blocked_producer_count") or 0
                ),
                "call_status": "cache_read" if snapshot else "cache_missing",
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "akshare_called": False,
        "yfinance_called": False,
        "supabase_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/data-health/cache 只读本地数据健康时间线；不会 ping provider 或刷新数据。",
            "数据健康只做诊断说明，不进入 strategy action，不执行真实交易。",
            "本页不调用 Tushare、AkShare、yfinance、Supabase、DeepSeek 或 GitHub。",
            "freshness 长窗口样本验收只使用本地 synthetic trade_cal fixture，不代表真实 Tushare trade_cal 长窗口验收完成。",
            "trade_cal 本地文件验收只读取已有 Parquet/DuckDB cache；不会刷新 provider，缺失或覆盖不足时仍保持待验收。",
            "trade_cal provider-backed 长窗口验收必须通过显式 POST task 执行；runbook 只固定验收要求，不调用 Tushare。",
            "current evidence freshness QA 只固定当前证据/历史样本边界；provider-backed trade_cal 长窗口验收仍需后续按钮任务证明。",
            "decision-surface audit 只检查本地 snapshot 可见字段，不重新评分、不过滤 packet、不修改 action；缺失字段不等于生产验收完成。",
            "producer coverage audit 只检查本地 snapshot 可见 producer 是否带 expected_trade_date、data_date 和 freshness_state；不构建缺失 packet。",
            "freshness production blocker audit 只汇总本地阻断项；不会调用 provider、不会重算分数、不会宣称生产完成。",
            "freshness provider acceptance activation receipt 只是显式 provider 验收前的本地清单；不会调用 Tushare、不会创建任务、不会宣称生产完成。",
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有数据健康时间线缓存；3.0 cache 页不会自动创建 provider 探测任务。")
    return _json_safe(packet)
