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


def _freshness_long_window_sample_validation() -> dict[str, Any]:
    from command_center_factor_research import build_a_share_freshness_long_window_sample_validation

    return build_a_share_freshness_long_window_sample_validation()


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


def read_data_health_timeline_cache() -> dict[str, Any]:
    snapshot = packet_service.load_snapshot_cache()
    safe_snapshot = _safe_value(snapshot)
    snapshot_map = safe_snapshot if isinstance(safe_snapshot, dict) else {}

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
            "real_trade_cal_long_window_validation_done": False,
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
        ],
    }
    if status == "cache_missing":
        packet["warnings"].append("当前没有数据健康时间线缓存；3.0 cache 页不会自动创建 provider 探测任务。")
    return _json_safe(packet)
