"""Explicit, local-only LTG-08 production packet producer.

The producer is callable only from the POST route.  It re-reads the immutable
production dataset and the matching current/latest-history task payload before
performing one atomic packet replacement.  It never refreshes provider data.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from . import next_session_replacement_promotion_service as replacement
from . import tushare_production_store
from .sqlite_evidence_reader import immutable_evidence_connection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
SQLITE_META_PATH = EVIDENCE_ROOT / "meta.sqlite"
PACKET_KEY = "command_center_next_session_projection_packet"
PROVENANCE_SCHEMA = "next_session_production_replacement_provenance.v2"
PRODUCER_SCHEMA = "next_session_production_packet_result.v1"
SCOPE = "ltg08_next_session_current_head_production_packet"
_HEAD = re.compile(r"^[0-9a-f]{40}$")
_SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_MIN_CLOSE_ROWS = 60
_REQUIRED_COVERAGE_KEYS = {
    "latest_close_anchor",
    "scenario_paths",
    "reference_and_limit_lines",
    "operation_zones_and_guardrails",
    "position_conflict_warnings",
    "freshness_and_data_trust",
    "deepseek_status_display",
    "hover_click_drilldown",
    "read_only_action_boundary",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _date_text(value: object) -> str:
    text = str(value or "").strip().replace("-", "")
    if text.endswith(".0"):
        text = text[:-2]
    if not re.fullmatch(r"[0-9]{8}", text):
        return ""
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError:
        return ""
    return text


def _read_packet_read_only(db_path: Path) -> dict[str, Any]:
    if not db_path.is_file() or db_path.is_symlink():
        return {}
    connection: sqlite3.Connection | None = None
    try:
        connection = immutable_evidence_connection(db_path)
        if connection is None:
            return {}
        row = connection.execute(
            "SELECT payload_json FROM packets WHERE packet_key = ?",
            (PACKET_KEY,),
        ).fetchone()
        payload = json.loads(str(row[0])) if row is not None else None
        return dict(payload) if isinstance(payload, Mapping) else {}
    except Exception:
        return {}
    finally:
        if connection is not None:
            connection.close()


def _blocked(head_full: str, blockers: list[str]) -> dict[str, Any]:
    return {
        "schema_version": PRODUCER_SCHEMA,
        "status": "next_session_production_packet_blocked",
        "head_full": head_full,
        "packet_written": False,
        "result_version": "",
        "packet_scope_hash": "",
        "blockers": sorted(set(blockers)),
        "explicit_post_required": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _coverage_rows(packet: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    coverage = packet.get("next_session_same_packet_signal_capability_coverage")
    coverage = dict(coverage) if isinstance(coverage, Mapping) else {}
    rows_value = packet.get("next_session_same_packet_signal_capability_coverage_rows")
    if not isinstance(rows_value, list):
        rows_value = coverage.get("rows")
    rows = [dict(row) for row in rows_value or [] if isinstance(row, Mapping)]
    row_keys = {str(row.get("coverage_key") or "") for row in rows}
    rows_ready = bool(
        len(rows) == len(_REQUIRED_COVERAGE_KEYS)
        and row_keys == _REQUIRED_COVERAGE_KEYS
        and all(
            row.get("retained") is True
            and row.get("direct_observation") is True
            and row.get("same_packet") is True
            and row.get("external_calls_triggered") is False
            and row.get("does_not_execute_trades") is True
            and row.get("does_not_modify_strategy_action") is True
            and row.get("does_not_modify_operation_zones") is True
            and row.get("contains_secret") is False
            for row in rows
        )
    )
    ready = bool(
        coverage.get("schema_version")
        == "next_session_same_packet_signal_capability_coverage.v1"
        and coverage.get("status") == "same_packet_signal_capability_coverage_ready"
        and coverage.get("same_packet") is True
        and coverage.get("lineage_bound") is True
        and coverage.get("direct_evidence_ready") is True
        and coverage.get("required_feature_group_count") == 9
        and coverage.get("retained_feature_group_count") == 9
        and coverage.get("missing_feature_groups") == []
        and rows_ready
    )
    return rows, ready


def _authoritative_rows(
    evidence_root: Path,
    *,
    symbol: str,
    source_task: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    try:
        verified = tushare_production_store.validate_tushare_full_market_production_version(
            evidence_root,
            include_frames=True,
        )
    except Exception as exc:
        return {}, [], [f"next_session_production_dataset_verifier_failed_{type(exc).__name__}"]
    if verified.get("ready") is not True:
        blockers.extend(str(item) for item in verified.get("blockers") or [])
        blockers.append("next_session_production_dataset_not_verified")
        return dict(verified), [], sorted(set(blockers))
    symbol = str(symbol or "").strip().upper()
    if not tushare_production_store.is_listed_a_share_code(symbol):
        blockers.append("next_session_production_source_symbol_invalid")
    frames = verified.get("frames") if isinstance(verified.get("frames"), Mapping) else {}
    daily = frames.get("daily")
    trade_cal = frames.get("trade_cal")
    normalized_daily: list[dict[str, Any]] = []
    normalized_calendar: list[dict[str, Any]] = []
    try:
        selected = daily.loc[
            daily["ts_code"].astype(str).str.upper() == symbol,
            ["ts_code", "trade_date", "close"],
        ].copy()
        selected["trade_date"] = selected["trade_date"].map(_date_text)
        selected = selected.sort_values("trade_date").tail(_MIN_CLOSE_ROWS)
        for row in selected.to_dict("records"):
            price = float(row["close"])
            if not math.isfinite(price) or price <= 0:
                raise ValueError("invalid_close")
            normalized_daily.append(
                {
                    "ts_code": str(row["ts_code"]).upper(),
                    "trade_date": _date_text(row["trade_date"]),
                    "close": round(price, 8),
                }
            )
        dates = [row["trade_date"] for row in normalized_daily]
        calendar = trade_cal.loc[
            trade_cal["cal_date"].map(_date_text).isin(dates)
            & (trade_cal["is_open"].astype(int) == 1),
            ["cal_date", "is_open"],
        ].drop_duplicates(subset=["cal_date"])
        normalized_calendar = sorted(
            (
                {"cal_date": _date_text(row["cal_date"]), "is_open": int(row["is_open"])}
                for row in calendar.to_dict("records")
            ),
            key=lambda row: row["cal_date"],
        )
    except Exception:
        blockers.append("next_session_production_dataset_frames_invalid")
        normalized_daily = []
        normalized_calendar = []
    dates = [row["trade_date"] for row in normalized_daily]
    if len(normalized_daily) != _MIN_CLOSE_ROWS or len(set(dates)) != _MIN_CLOSE_ROWS:
        blockers.append("next_session_production_60_session_close_missing")
    if [row["cal_date"] for row in normalized_calendar] != dates:
        blockers.append("next_session_production_trade_calendar_binding_invalid")
    if not dates or dates[-1] != str(verified.get("validated_trade_date") or ""):
        blockers.append("next_session_production_data_date_not_current")
    authoritative = {
        "symbol": symbol,
        "data_date": dates[-1] if dates else "",
        "provider_scope_hash": str(verified.get("scope_hash") or ""),
        "dataset_version_digest": str(verified.get("version_digest") or ""),
        "daily_rows_digest": _digest(normalized_daily) if normalized_daily else "",
        "trade_calendar_digest": _digest(normalized_calendar) if normalized_calendar else "",
        "source_task_call_ledger_digest": str(verified.get("official_call_ledger_digest") or ""),
        "official_execution_event_digest": str(
            verified.get("official_execution_event_digest") or ""
        ),
    }
    source_call_ledger_digest = _digest(source_task.get("call_ledger") or [])
    if not authoritative["source_task_call_ledger_digest"]:
        blockers.append("next_session_production_official_call_ledger_digest_missing")
    elif source_call_ledger_digest != authoritative["source_task_call_ledger_digest"]:
        blockers.append("next_session_production_source_task_call_ledger_digest_mismatch")
    if len(authoritative["official_execution_event_digest"]) != 64:
        blockers.append("next_session_production_official_execution_event_digest_missing")
    historical = [
        {
            "x": datetime.strptime(row["trade_date"], "%Y%m%d").date().isoformat(),
            "price": row["close"],
            "source": "tushare.daily.close",
        }
        for row in normalized_daily
    ]
    return authoritative, historical, sorted(set(blockers))


def produce_next_session_production_packet(
    payload: Any,
    *,
    evidence_root: Path | str = EVIDENCE_ROOT,
    project_root: Path = PROJECT_ROOT,
    sqlite_path: Path | None = None,
) -> dict[str, Any]:
    """Build and atomically persist one current-head packet; never refresh data."""

    request = dict(payload) if isinstance(payload, Mapping) else {}
    head_full = replacement._current_head(project_root)
    if set(request) != {"source_task_id"}:
        return _blocked(head_full, ["next_session_production_source_task_id_only_required"])
    source_task_id = str(request.get("source_task_id") or "")
    if not _SAFE_TASK_ID.fullmatch(source_task_id):
        return _blocked(head_full, ["next_session_production_source_task_id_invalid"])
    root = Path(evidence_root).expanduser().absolute()
    if replacement._evidence_tree_symlink_blocker(root):
        return _blocked(head_full, ["next_session_production_evidence_tree_symlink_invalid"])
    db_path = Path(sqlite_path) if sqlite_path is not None else root / "meta.sqlite"
    source_task = replacement._read_immutable_source_task_status(root, source_task_id)
    blockers: list[str] = []
    if not (
        source_task.get("task_id") == source_task_id
        and source_task.get("task_type") == "refresh_tushare_facts"
        and source_task.get("status") == "success"
        and source_task.get("progress") == 1.0
        and source_task.get("output_packet_key") == "command_center_tushare_refresh_packet"
        and isinstance(source_task.get("payload_safe"), Mapping)
        and source_task.get("payload_safe", {}).get("acceptance_mode")
        == "full_interface_provider_production"
        and source_task.get("external_calls_triggered") is True
        and source_task.get("tushare_called") is True
        and source_task.get("does_not_execute_trades") is True
        and source_task.get("does_not_modify_strategy_action") is True
    ):
        blockers.append("next_session_production_source_task_current_history_invalid")
    packet = _read_packet_read_only(db_path)
    chart = packet.get("chart_payload") if isinstance(packet.get("chart_payload"), Mapping) else {}
    summary = packet.get("chart_summary") if isinstance(packet.get("chart_summary"), Mapping) else {}
    chart_contract = chart.get("chart_contract") if isinstance(chart.get("chart_contract"), Mapping) else {}
    coverage_rows, coverage_ready = _coverage_rows(packet)
    packet_symbol = str(packet.get("symbol") or chart.get("symbol") or "").strip().upper()
    if not (
        packet.get("packet_key") == PACKET_KEY
        and packet.get("schema_version") == "next_session_projection.v1"
        and chart.get("status") == "ready"
        and chart.get("is_exact_next_session_packet") is True
        and summary.get("is_exact_next_session_packet") is True
        and chart_contract.get("cache_only") is True
        and chart_contract.get("external_calls_triggered") is False
        and chart_contract.get("does_not_execute_trades") is True
        and chart_contract.get("frontend_computes_trade_action") is False
        and chart_contract.get("does_not_modify_action") is True
        and chart_contract.get("does_not_modify_operation_zones") is True
        and coverage_ready
    ):
        blockers.append("next_session_production_base_packet_contract_invalid")
    authoritative, historical, authoritative_blockers = _authoritative_rows(
        root,
        symbol=packet_symbol,
        source_task=source_task,
    )
    blockers.extend(authoritative_blockers)
    if blockers:
        return _blocked(head_full, blockers)
    source_task_payload_digest = _digest(source_task.get("payload_safe") or {})
    coverage_rows_digest = _digest(coverage_rows)
    binding_material = {
        "scope": SCOPE,
        "head_full": head_full,
        "source_task_id": source_task_id,
        "source_task_payload_digest": source_task_payload_digest,
        **authoritative,
        "coverage_rows_digest": coverage_rows_digest,
        "chart_structure_digest": _digest(
            {
                "scenario_series": chart.get("scenario_series") or [],
                "reference_lines": chart.get("reference_lines") or [],
                "operation_zones": chart.get("operation_zones") or [],
            }
        ),
    }
    binding_digest = _digest(binding_material)
    result_version = f"next-session-prod-{binding_digest[:24]}"
    packet_scope_hash = _digest({**binding_material, "result_version": result_version})
    provenance = {
        "schema_version": PROVENANCE_SCHEMA,
        "status": "authoritative_provider_dataset_current_head",
        "head_full": head_full,
        "source_task_id": source_task_id,
        "source_task_status": "success",
        "source_task_payload_digest": source_task_payload_digest,
        "result_version": result_version,
        "packet_scope_hash": packet_scope_hash,
        "coverage_rows_digest": coverage_rows_digest,
        **authoritative,
        "provider_backed": True,
        "authoritative_dataset": True,
        "trade_calendar_validated": True,
        "synthetic_fixture": False,
        "local_preview": False,
    }
    produced = dict(packet)
    produced_chart = dict(chart)
    produced_summary = dict(summary)
    produced_maturity = dict(
        produced_chart.get("chart_maturity")
        if isinstance(produced_chart.get("chart_maturity"), Mapping)
        else {}
    )
    produced_chart.update(
        {
            "historical_points": historical,
            "uses_real_daily_close": True,
            "symbol": authoritative["symbol"],
            "result_version": result_version,
            "packet_scope_hash": packet_scope_hash,
        }
    )
    produced_maturity.update({"status": "production_ready", "has_real_60d_close": True})
    produced_chart["chart_maturity"] = produced_maturity
    produced_summary.update(
        {
            "uses_real_daily_close": True,
            "historical_point_count": len(historical),
            "symbol": authoritative["symbol"],
            "result_version": result_version,
        }
    )
    produced.update(
        {
            "status": "ready_cache_replay",
            "symbol": authoritative["symbol"],
            "data_date": authoritative["data_date"],
            "result_version": result_version,
            "packet_scope_hash": packet_scope_hash,
            "coverage_rows_digest": coverage_rows_digest,
            "source_task_id": source_task_id,
            "source_task_payload_digest": source_task_payload_digest,
            "production_replacement_provenance": provenance,
            "chart_payload": produced_chart,
            "chart_summary": produced_summary,
            "provider_backed": True,
            "production_replacement_complete": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_operation_zones": True,
            "contains_secret": False,
        }
    )
    try:
        receipt = SQLiteMetaStore(db_path).promote_packet_atomic(PACKET_KEY, produced)
    except Exception:
        return _blocked(head_full, ["next_session_production_packet_atomic_write_failed"])
    if not (
        receipt.get("transaction_committed") is True
        and receipt.get("readback_verified_before_commit") is True
        and receipt.get("payload_digest")
        == hashlib.sha256(
            json.dumps(
                produced,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
    ):
        return {
            **_blocked(head_full, ["next_session_production_packet_commit_receipt_invalid"]),
            "packet_written": True,
        }
    return {
        "schema_version": PRODUCER_SCHEMA,
        "status": "next_session_production_packet_written_current_head",
        "head_full": head_full,
        "packet_written": True,
        "packet_key": PACKET_KEY,
        "result_version": result_version,
        "packet_scope_hash": packet_scope_hash,
        "coverage_rows_digest": coverage_rows_digest,
        "source_task_id": source_task_id,
        "source_task_payload_digest": source_task_payload_digest,
        "dataset_version_digest": authoritative["dataset_version_digest"],
        "daily_rows_digest": authoritative["daily_rows_digest"],
        "trade_calendar_digest": authoritative["trade_calendar_digest"],
        "atomic_payload_digest": receipt.get("payload_digest") or "",
        "blockers": [],
        "explicit_post_required": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


__all__ = ["produce_next_session_production_packet"]
