from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import inspect
import json
import math
import os
import re
import sqlite3
import subprocess
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from server.services.sqlite_evidence_reader import immutable_evidence_connection
from server.services.full_market_industry_service import (
    INDUSTRY_BINDING_DIGEST_KEYS,
    validate_full_market_industry_membership,
)
from storage import parquet_store
from storage.sqlite_meta import SQLiteMetaStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
SQLITE_META_PATH = EVIDENCE_ROOT / "meta.sqlite"
PARQUET_ROOT = EVIDENCE_ROOT / "parquet"

PACKET_KEY = "command_center_3_full_market_worker_production_acceptance"
LAST_GOOD_PACKET_KEY = f"{PACKET_KEY}_last_good"
ATTEMPT_PACKET_KEY = f"{PACKET_KEY}_latest_attempt"
LOCK_PACKET_KEY = f"{PACKET_KEY}_lock"
STAGE_PACKET_PREFIX = f"{PACKET_KEY}_stage"
CHECKPOINT_PACKET_PREFIX = f"{PACKET_KEY}_checkpoint"
TRANSPORT_PACKET_PREFIX = f"{PACKET_KEY}_transport"
EXECUTION_EVENT_PACKET_PREFIX = f"{PACKET_KEY}_execution_event"
SCHEMA_VERSION = "full_market_worker_production_acceptance.v3"
STAGE_SCHEMA_VERSION = "full_market_worker_production_stage.v3"
CHECKPOINT_SCHEMA_VERSION = "full_market_worker_checkpoint.v2"
TRANSPORT_SCHEMA_VERSION = "redis_celery_direct_attestation.v1"
EXECUTION_EVENT_SCHEMA_VERSION = "full_market_worker_execution_event.v1"
PROMOTION_JOURNAL_SCHEMA_VERSION = "full_market_worker_promotion_journal.v1"

CANDIDATE_TASK_NAME = "run_candidate_radar_full_pool_local_scan"
CANDIDATE_TASK_TYPE = CANDIDATE_TASK_NAME
CANDIDATE_QUEUE = "command_center_candidate_production"
RESULT_DATASET = "full_market_candidate_radar_results"
FACTOR_RESULT_DATASET = "full_market_factor_research_results"
FACTOR_PACKET_KEY = "command_center_3_factor_full_market_worker_production_acceptance"
FACTOR_LAST_GOOD_PACKET_KEY = f"{FACTOR_PACKET_KEY}_last_good"
FACTOR_SCHEMA_VERSION = "factor_full_market_worker_production_acceptance.v2"
CANDIDATE_CACHE_PACKET_KEY = "command_center_3_candidate_radar_cache"
CANDIDATE_CACHE_SCHEMA_VERSION = "candidate_radar_cache.v1"
CANDIDATE_CACHE_REPLACEMENT_SCHEMA_VERSION = (
    "candidate_radar_full_market_cache_replacement_binding.v1"
)
PRODUCTION_LINEAGE_KEY_RELATIVE_PATH = Path(
    "full_market_worker/.production_lineage_hmac_key"
)
PRODUCTION_LINEAGE_LOCAL_QA_SCHEMA_VERSION = (
    "full_market_worker_production_lineage_local_qa.v1"
)
PRODUCTION_LINEAGE_EXTERNAL_RUNNER_BLOCKER = (
    "external_trusted_production_lineage_runner_unavailable"
)
FACTOR_LINEAGE_EVENT_KIND = "factor_full_market_research"
RADAR_LINEAGE_EVENT_KIND = "candidate_radar_authoritative_cache_replacement"

DEFAULT_MINIMUM_UNIVERSE_SIZE = 3000
MAXIMUM_MINIMUM_UNIVERSE_SIZE = 7000
DEFAULT_BATCH_SIZE = 100
MIN_BATCH_SIZE = 60
MAX_BATCH_SIZE = 120
MIN_DAILY_SESSIONS = 60
TARGET_DAILY_SESSIONS = 90
MIN_MONEYFLOW_SESSIONS = 5
DEFAULT_RESULT_TIMEOUT_SECONDS = 900
MAX_RESULT_TIMEOUT_SECONDS = 3600
LOCK_TTL_SECONDS = 3600
WORKER_CHALLENGE_TTL_SECONDS = 900
WORKER_RECEIPT_TTL_SECONDS = 86400
PROMOTION_JOURNAL_NAME = "promotion_journal.json"

REQUIRED_PROVIDER_FRAMES = ("stock_basic", "trade_cal", "daily", "daily_basic", "moneyflow")
FEATURE_CONTRACT = {
    "schema_version": "candidate_radar_full_market_feature_contract.v1",
    "source_contract": "next_stock_radar_full_market_rough_and_rule_score",
    "daily_target_sessions": TARGET_DAILY_SESSIONS,
    "daily_minimum_sessions": MIN_DAILY_SESSIONS,
    "moneyflow_minimum_sessions": MIN_MONEYFLOW_SESSIONS,
    "required_artifacts": list(REQUIRED_PROVIDER_FRAMES),
    "provider_contract_source": "validate_tushare_full_market_production_version",
    "scoring_contract_source": "next_stock_radar.build_cross_section_rough_candidates+score_candidate",
    "research_only": True,
    "does_not_execute_trades": True,
}
FEATURE_CONTRACT_DIGEST = hashlib.sha256(
    json.dumps(FEATURE_CONTRACT, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

FACTOR_OUTPUT_CONTRACT = {
    "schema_version": "factor_full_market_output_contract.v1",
    "output_kind": "factor_full_market_cross_sectional_research",
    "required_metrics": [
        "cross_sectional_rank",
        "cross_sectional_zscore",
        "industry_neutral_score",
        "size_neutral_score",
        "combined_factor_score",
    ],
    "requires_full_universe_symbol_coverage": True,
    "candidate_radar_scores_are_not_factor_outputs": True,
    "research_only": True,
    "does_not_execute_trades": True,
}
FACTOR_OUTPUT_CONTRACT_DIGEST = hashlib.sha256(
    json.dumps(
        FACTOR_OUTPUT_CONTRACT,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()

_HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
_SH_PREFIXES = ("600", "601", "603", "605", "688", "689")
_SZ_PREFIXES = ("000", "001", "002", "003", "300", "301")
_BJ_PREFIXES = ("4", "8", "920")
_SENSITIVE_MARKERS = (
    "token",
    "password",
    "secret",
    "credential",
    "authorization",
    "broker_url",
    "backend_url",
    "api_key",
    "env_key",
    "redis://",
    "rediss://",
    "bearer ",
)


def _make_public_acceptance_runner(implementation: Any) -> tuple[Any, Any]:
    active: dict[int, dict[str, Any]] = {}

    def register(run_id: str) -> tuple[Any, dict[str, Any]]:
        capability = object()
        state = {
            "capability": capability,
            "run_id": run_id,
            "official_transport_probed": True,
            "transport_event_persisted": False,
            "verified_worker_task_ids": set(),
        }
        active[id(capability)] = state
        return capability, state

    def resolve(capability: Any, run_id: str) -> dict[str, Any]:
        state = active.get(id(capability), {})
        return state if state.get("capability") is capability and state.get("run_id") == run_id else {}

    def revoke(capability: Any) -> None:
        active.pop(id(capability), None)

    def public_runner(payload: Any = None) -> dict[str, Any]:
        return implementation(payload, register, revoke)

    return public_runner, resolve


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _current_head_full() -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    value = completed.stdout.strip().lower() if completed.returncode == 0 else ""
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else ""


def _lineage_key_path(evidence_root: Path) -> Path:
    """Return the retired local-key path for non-mutation audits only."""

    return evidence_root / PRODUCTION_LINEAGE_KEY_RELATIVE_PATH


def _persist_official_production_lineage_event(
    evidence_root: Path,
    *,
    capability: Any,
    run_id: str,
    event_kind: str,
    worker_packet_digest: str,
    output_binding_digest: str,
    factor_output_contract_digest: str = "",
    neutralization_audit_digest: str = "",
    candidate_cache_packet_digest: str = "",
    candidate_cache_write_task_digest: str = "",
    deep_scan_execution_evidence: Mapping[str, Any] | None = None,
    browser_visual_evidence: Mapping[str, Any] | None = None,
    browser_performance_evidence: Mapping[str, Any] | None = None,
    legacy_retirement_evidence: Mapping[str, Any] | None = None,
    global_candidate_cache_overwritten: bool = False,
    deep_scan_worker_execution_verified: bool = False,
    browser_visual_qa_verified: bool = False,
    browser_performance_verified: bool = False,
    legacy_fallback_retired: bool = False,
) -> dict[str, Any]:
    """Report a sealed local-QA result without writing production lineage.

    A capability held in this Python process is enumerable through ordinary
    introspection and therefore cannot establish an independent production trust
    boundary.  Until an external trusted runner and verifier are integrated, this
    entry point is deliberately write-free and production-ineligible.
    """

    del (
        evidence_root,
        capability,
        worker_packet_digest,
        output_binding_digest,
        factor_output_contract_digest,
        neutralization_audit_digest,
        candidate_cache_packet_digest,
        candidate_cache_write_task_digest,
        deep_scan_execution_evidence,
        browser_visual_evidence,
        browser_performance_evidence,
        legacy_retirement_evidence,
        global_candidate_cache_overwritten,
        deep_scan_worker_execution_verified,
        browser_visual_qa_verified,
        browser_performance_verified,
        legacy_fallback_retired,
    )
    return {
        "schema_version": PRODUCTION_LINEAGE_LOCAL_QA_SCHEMA_VERSION,
        "status": "external_trusted_production_lineage_runner_required",
        "event_kind": (
            event_kind
            if event_kind in {FACTOR_LINEAGE_EVENT_KIND, RADAR_LINEAGE_EVENT_KIND}
            else "invalid"
        ),
        "acceptance_run_id": (
            run_id if _normalize_uuid4(run_id) == run_id else ""
        ),
        "production_eligible": False,
        "external_trusted_runner_observed": False,
        "writes_storage": False,
        "evidence_root_mutated": False,
        "blockers": [PRODUCTION_LINEAGE_EXTERNAL_RUNNER_BLOCKER],
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _matching_production_lineage_event(
    evidence_root: Path,
    *,
    event_kind: str,
    run_id: str,
    worker_packet_digest: str,
    output_binding_digest: str,
) -> dict[str, Any]:
    """Fail closed until production lineage comes from an external trust root."""

    del (
        evidence_root,
        event_kind,
        run_id,
        worker_packet_digest,
        output_binding_digest,
    )
    return {}


def _candidate_radar_replacement_claim_fields(
    *,
    authoritative_cache_validated: bool,
    external_lineage_validated: bool,
) -> dict[str, bool]:
    replacement_ready = bool(
        authoritative_cache_validated is True
        and external_lineage_validated is True
    )
    return {
        "candidate_radar_production_replacement": replacement_ready,
        "global_candidate_cache_overwritten": replacement_ready,
    }


def _integer(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bounded_integer(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(_integer(value, default=default), maximum))


def _read_packet_no_init(db_path: Path, packet_key: str) -> dict[str, Any]:
    connection = immutable_evidence_connection(db_path)
    if connection is None:
        return {}
    try:
        row = connection.execute(
            "SELECT payload_json FROM packets WHERE packet_key = ?",
            (packet_key,),
        ).fetchone()
        value = json.loads(row[0]) if row else {}
    except Exception:
        return {}
    finally:
        connection.close()
    return dict(value) if isinstance(value, Mapping) else {}


def _read_task_no_init(db_path: Path, task_id: str) -> dict[str, Any]:
    if not task_id:
        return {}
    connection = immutable_evidence_connection(db_path)
    if connection is None:
        return {}
    try:
        row = connection.execute(
            "SELECT payload_json FROM task_status WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        value = json.loads(row[0]) if row else {}
    except Exception:
        return {}
    finally:
        connection.close()
    return dict(value) if isinstance(value, Mapping) else {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    encoded = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")
    try:
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _valid_a_share_symbol(value: Any) -> bool:
    symbol = str(value or "").strip().upper()
    if not re.fullmatch(r"[0-9]{6}\.(?:SH|SZ|BJ)", symbol):
        return False
    code, exchange = symbol.split(".")
    if exchange == "SH":
        return code.startswith(_SH_PREFIXES)
    if exchange == "SZ":
        return code.startswith(_SZ_PREFIXES)
    return code.startswith(_BJ_PREFIXES)


def _normalize_uuid4(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = uuid.UUID(text)
    except (ValueError, AttributeError, TypeError):
        return ""
    return parsed.hex if parsed.version == 4 else ""


def _normalize_symbols(values: Any) -> tuple[list[str], int, int]:
    raw = list(values) if isinstance(values, (list, tuple, set)) else []
    valid: list[str] = []
    invalid = 0
    for value in raw:
        symbol = str(value or "").strip().upper()
        if _valid_a_share_symbol(symbol):
            valid.append(symbol)
        else:
            invalid += 1
    unique = sorted(set(valid))
    return unique, len(valid) - len(unique), invalid


def _industry_binding(universe: Mapping[str, Any]) -> dict[str, str]:
    return {
        key: str(universe.get(key) or "")
        for key in INDUSTRY_BINDING_DIGEST_KEYS
    }


def _industry_binding_ready(universe: Mapping[str, Any]) -> bool:
    binding = _industry_binding(universe)
    return all(_HEX_64_RE.fullmatch(value) for value in binding.values())


def _industry_input_digest(universe: Mapping[str, Any]) -> str:
    return _canonical_digest(_industry_binding(universe))


def _authoritative_provider_universe(
    evidence_root: Path,
    *,
    minimum_universe_size: int,
    include_frames: bool = False,
    require_industry_membership: bool = False,
) -> dict[str, Any]:
    try:
        from server.services.tushare_production_store import (
            validate_tushare_full_market_production_version,
        )
    except ImportError:
        return {
            "ready": False,
            "status": "shared_tushare_full_market_verifier_unavailable",
            "symbols": [],
            "universe_count": 0,
            "minimum_universe_size": minimum_universe_size,
            "blockers": ["shared_tushare_full_market_verifier_unavailable"],
            "external_calls_triggered": False,
            "writes_storage": False,
        }
    try:
        verified = validate_tushare_full_market_production_version(
            evidence_root,
            include_frames=include_frames,
        )
    except Exception as exc:
        return {
            "ready": False,
            "status": "shared_tushare_full_market_verifier_failed",
            "symbols": [],
            "universe_count": 0,
            "minimum_universe_size": minimum_universe_size,
            "blockers": [f"shared_tushare_full_market_verifier_failed_{type(exc).__name__}"],
            "external_calls_triggered": False,
            "writes_storage": False,
        }
    source = dict(verified) if isinstance(verified, Mapping) else {}
    frames = source.get("frames") if isinstance(source.get("frames"), Mapping) else {}
    symbols, duplicates, invalid = _normalize_symbols(source.get("symbols"))
    scope_hash = str(source.get("scope_hash") or "").strip().lower()
    universe_digest = str(source.get("universe_digest") or "").strip().lower()
    version_digest = str(
        source.get("version_digest")
        or source.get("artifact_manifest_digest")
        or ""
    ).strip().lower()
    blockers = [str(item) for item in source.get("blockers") or [] if str(item)]
    required_frames = {"stock_basic", "trade_cal", "daily", "daily_basic", "moneyflow"}
    if source.get("ready") is not True:
        blockers.append("shared_tushare_full_market_verifier_blocked")
    if duplicates or invalid or len(symbols) < minimum_universe_size:
        blockers.append("shared_provider_universe_identity_invalid")
    if source.get("universe_count") != len(symbols) or universe_digest != _canonical_digest(symbols):
        blockers.append("shared_provider_universe_digest_mismatch")
    if not _HEX_64_RE.fullmatch(scope_hash) or not _HEX_64_RE.fullmatch(version_digest):
        blockers.append("shared_provider_version_binding_missing")
    if include_frames and (
        not required_frames.issubset(frames)
        or any(getattr(frames.get(name), "empty", True) for name in required_frames)
    ):
        blockers.append("shared_provider_verified_frames_missing")
    industry = validate_full_market_industry_membership(
        evidence_root,
        expected_symbols=symbols,
        expected_universe_digest=universe_digest,
        expected_validated_trade_date=source.get("validated_trade_date"),
    ) if require_industry_membership else {
        "ready": False,
        "status": "full_market_industry_membership_not_requested",
        "blockers": [],
        "production_industry_verified": False,
        "external_calls_triggered": False,
        "writes_storage": False,
    }
    if require_industry_membership and industry.get("ready") is not True:
        blockers.append("authoritative_full_market_industry_membership_missing_or_invalid")
    result = {
        **source,
        "ready": not blockers,
        "status": (
            "authoritative_full_market_universe_ready"
            if not blockers
            else "authoritative_full_market_universe_missing_or_below_threshold"
        ),
        "scope_hash": scope_hash,
        "version_digest": version_digest,
        "symbols": symbols,
        "universe_count": len(symbols),
        "minimum_universe_size": minimum_universe_size,
        "universe_digest": universe_digest,
        "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
        "industry_membership": industry,
        "industry_membership_required": require_industry_membership,
        "industry_membership_verified": bool(
            require_industry_membership and industry.get("ready") is True
        ),
        "industry_scope_digest": str(industry.get("scope_digest") or ""),
        "industry_source_version_digest": str(
            industry.get("source_version_digest") or ""
        ),
        "industry_artifact_sha256": str(industry.get("artifact_sha256") or ""),
        "industry_manifest_digest": str(industry.get("manifest_digest") or ""),
        "industry_pointer_digest": str(industry.get("pointer_digest") or ""),
        "industry_semantic_evidence_sha256": str(
            industry.get("semantic_evidence_sha256") or ""
        ),
        "blockers": list(dict.fromkeys(blockers)),
        "provider_execution_triggered": False,
        "external_calls_triggered": False,
        "writes_storage": False,
    }
    if include_frames:
        result["_frames"] = dict(frames)
    result.pop("frames", None)
    if require_industry_membership and not _industry_binding_ready(result):
        result["ready"] = False
        result["status"] = "authoritative_full_market_universe_missing_or_below_threshold"
        result["blockers"] = list(
            dict.fromkeys(
                list(result.get("blockers") or [])
                + ["authoritative_full_market_industry_digest_binding_incomplete"]
            )
        )
    return result


def _frame_subset(frame: Any, symbols: list[str]) -> Any:
    if frame is None or getattr(frame, "empty", True) or "ts_code" not in frame.columns:
        return frame.copy() if frame is not None else None
    return frame[frame["ts_code"].astype(str).str.upper().isin(set(symbols))].copy()


def _frame_records_for_digest(frame: Any, symbols: list[str]) -> list[dict[str, Any]]:
    subset = _frame_subset(frame, symbols)
    if subset is None or getattr(subset, "empty", True):
        return []
    columns = sorted(str(column) for column in subset.columns)
    order = [column for column in ("ts_code", "trade_date", "cal_date") if column in columns]
    normalized = subset[columns].sort_values(order or columns, kind="stable").reset_index(drop=True)
    normalized = normalized.where(normalized.notna(), None)
    return [dict(row) for row in normalized.to_dict(orient="records")]


def _batch_input_hash(universe: Mapping[str, Any], symbols: list[str]) -> str:
    frames = universe.get("_frames") if isinstance(universe.get("_frames"), Mapping) else {}
    material = {
        "provider_scope_hash": universe.get("scope_hash"),
        "provider_version_digest": universe.get("version_digest"),
        "universe_digest": universe.get("universe_digest"),
        "industry_scope_digest": universe.get("industry_scope_digest"),
        "industry_source_version_digest": universe.get(
            "industry_source_version_digest"
        ),
        "industry_artifact_sha256": universe.get("industry_artifact_sha256"),
        "industry_manifest_digest": universe.get("industry_manifest_digest"),
        "industry_pointer_digest": universe.get("industry_pointer_digest"),
        "industry_semantic_evidence_sha256": universe.get(
            "industry_semantic_evidence_sha256"
        ),
        "industry_input_digest": _industry_input_digest(universe),
        "symbols": list(symbols),
        "frames": {
            name: _frame_records_for_digest(frames.get(name), symbols)
            for name in REQUIRED_PROVIDER_FRAMES
        },
    }
    return _canonical_digest(material)


class _VerifiedFrameRadarAdapter:
    def __init__(self, frames: Mapping[str, Any], symbols: list[str]) -> None:
        self.frames = dict(frames)
        self.symbols = list(symbols)

    @staticmethod
    def _result(frame: Any) -> dict[str, Any]:
        return {"ok": frame is not None and not getattr(frame, "empty", True), "data": frame}

    def get_stock_basic(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._result(_frame_subset(self.frames.get("stock_basic"), self.symbols))

    def get_trade_cal(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        frame = self.frames.get("trade_cal")
        return self._result(frame.copy() if frame is not None else None)

    def get_daily(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._result(_frame_subset(self.frames.get("daily"), self.symbols))

    def get_daily_basic(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._result(_frame_subset(self.frames.get("daily_basic"), self.symbols))


def _score_candidate_rows(universe: Mapping[str, Any], symbols: list[str]) -> list[dict[str, Any]]:
    from next_stock_radar import build_cross_section_rough_candidates, score_candidate

    frames = universe.get("_frames") if isinstance(universe.get("_frames"), Mapping) else {}
    if not set(REQUIRED_PROVIDER_FRAMES).issubset(frames):
        return []
    adapter = _VerifiedFrameRadarAdapter(frames, symbols)
    candidates, meta = build_cross_section_rough_candidates(
        {"tushare_adapter": adapter},
        refine_candidate_limit=len(symbols),
        exclude_st=False,
        exclude_chinext=False,
        exclude_star=False,
        exclude_bj=False,
        exclude_low_amount=False,
        trend_up_only=False,
    )
    if meta.get("degraded") is True:
        return []
    by_symbol = {
        str(row.get("ticker") or "").upper(): row
        for row in candidates
        if isinstance(row, Mapping)
    }
    basic = _frame_subset(frames.get("daily_basic"), symbols)
    flow = _frame_subset(frames.get("moneyflow"), symbols)
    if basic is None or flow is None:
        return []
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        candidate = by_symbol.get(symbol)
        if not isinstance(candidate, Mapping):
            return []
        rough = candidate.get("rough_context") if isinstance(candidate.get("rough_context"), Mapping) else {}
        basic_rows = basic[basic["ts_code"].astype(str).str.upper().eq(symbol)].sort_values("trade_date")
        flow_rows = flow[flow["ts_code"].astype(str).str.upper().eq(symbol)].sort_values("trade_date")
        if basic_rows.empty or len(flow_rows) < MIN_MONEYFLOW_SESSIONS:
            return []
        basic_latest = basic_rows.iloc[-1]
        flow_latest = flow_rows.iloc[-1]
        flow_recent = flow_rows.tail(MIN_MONEYFLOW_SESSIONS)
        today_main = float(flow_latest["buy_lg_amount"]) + float(flow_latest["buy_elg_amount"])
        today_main -= float(flow_latest["sell_lg_amount"]) + float(flow_latest["sell_elg_amount"])
        five_day_main = float(flow_recent["buy_lg_amount"].sum()) + float(flow_recent["buy_elg_amount"].sum())
        five_day_main -= float(flow_recent["sell_lg_amount"].sum()) + float(flow_recent["sell_elg_amount"].sum())
        data_gaps = ["筹码", "公告", "news_digest", "两融", "龙虎榜"]
        candidate_context = {
            **dict(rough),
            "ticker": symbol,
            "name": candidate.get("name") or "",
            "today_main_net_yi": today_main,
            "five_day_main_net_yi": five_day_main,
            "data_gaps": data_gaps,
            "candidate_switch_relation": "暂不替代",
            "has_reduction_risk": False,
            "near_limit_up": False,
            "chase_zone": False,
            "margin": {},
        }
        scored = score_candidate(candidate_context, {})
        row = {
            "ts_code": symbol,
            "data_date": str(rough.get("data_date") or ""),
            "score": _integer(scored.get("total_score")),
            "rough_score": _integer(rough.get("rough_score")),
            "trend_score": _integer(scored.get("trend_score")),
            "money_score": _integer(scored.get("money_score")),
            "risk_score": _integer(scored.get("risk_score")),
            "position_score": _integer(scored.get("position_score")),
            "information_score": _integer(scored.get("information_score")),
            "holding_compare_score": _integer(scored.get("holding_compare_score")),
            "battle_state": str(scored.get("battle_state") or ""),
            "battle_state_reason": str(scored.get("battle_state_reason") or ""),
            "trigger_conditions_json": json.dumps(
                list(scored.get("trigger_conditions") or []), ensure_ascii=False, separators=(",", ":")
            ),
            "invalid_conditions_json": json.dumps(
                list(scored.get("invalid_conditions") or []), ensure_ascii=False, separators=(",", ":")
            ),
            "close": rough.get("current_price"),
            "ma20": rough.get("MA20"),
            "ma60": rough.get("MA60"),
            "return_20d_pct": rough.get("twenty_day_return_pct"),
            "amount": rough.get("amount"),
            "turnover_rate": basic_latest.get("turnover_rate"),
            "volume_ratio": basic_latest.get("volume_ratio"),
            "total_mv": basic_latest.get("total_mv"),
            "circ_mv": basic_latest.get("circ_mv"),
            "pe_ttm": basic_latest.get("pe_ttm"),
            "pb": basic_latest.get("pb"),
            "today_main_net_amount": today_main,
            "five_day_main_net_amount": five_day_main,
            "rough_notes": str(rough.get("rough_notes") or ""),
            "data_gaps_json": json.dumps(data_gaps, ensure_ascii=False, separators=(",", ":")),
            "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
            "radar_scoring_contract": "next_stock_radar.score_candidate",
            "research_only": True,
            "candidate_is_not_buy_instruction": True,
            "does_not_execute_trades": True,
        }
        rows.append(json.loads(json.dumps(row, ensure_ascii=False, default=str)))
    normalized, duplicates, invalid = _normalize_symbols([row.get("ts_code") for row in rows])
    if normalized != symbols or duplicates or invalid:
        return []
    return sorted(rows, key=lambda row: str(row["ts_code"]))


def _persist_task(task: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(task)
    SQLiteMetaStore(SQLITE_META_PATH).write_task_status(payload)
    return payload


def _worker_challenge_key(run_id: str, challenge_id: str) -> str:
    return f"cc3:full-market:{run_id}:worker-challenge:{challenge_id}"


def _worker_challenge_receipt_key(run_id: str, challenge_id: str) -> str:
    return f"cc3:full-market:{run_id}:worker-receipt:{challenge_id}"


def _worker_execution_proof_material(
    payload: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "acceptance_run_id": str(payload.get("acceptance_run_id") or ""),
        "challenge_id": str(payload.get("worker_challenge_id") or ""),
        "celery_request_id": str(runtime.get("celery_request_id") or ""),
        "worker_hostname": str(runtime.get("worker_hostname") or ""),
        "worker_pid": _integer(runtime.get("worker_pid")),
        "worker_queue": str(runtime.get("worker_queue") or ""),
        "provider_version_digest": str(payload.get("provider_version_digest") or ""),
        "universe_digest": str(payload.get("universe_digest") or ""),
        "batch_symbol_hash": str(payload.get("batch_symbol_hash") or ""),
        "batch_input_hash": str(payload.get("batch_input_hash") or ""),
        "industry_pointer_digest": str(payload.get("industry_pointer_digest") or ""),
        "industry_input_digest": str(payload.get("industry_input_digest") or ""),
    }


def _worker_execution_receipt_value(
    task: Mapping[str, Any],
    specification: Mapping[str, Any],
    transport: Mapping[str, Any],
) -> str:
    runtime = task.get("runtime_provenance") if isinstance(task.get("runtime_provenance"), Mapping) else {}
    return _canonical_digest(
        {
            "acceptance_run_id": specification.get("acceptance_run_id"),
            "worker_challenge_id": specification.get("worker_challenge_id"),
            "celery_task_id": specification.get("celery_task_id"),
            "worker_task_id": task.get("task_id"),
            "worker_execution_proof": runtime.get("worker_execution_proof"),
            "persisted_task_digest": _canonical_digest(task),
            "transport_attestation_digest": _canonical_digest(transport),
            "transport_execution_event_digest": transport.get("execution_event_digest"),
        }
    )


def _consume_official_worker_challenge(
    payload: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    run_id = _normalize_uuid4(payload.get("acceptance_run_id"))
    challenge_id = _normalize_uuid4(payload.get("worker_challenge_id"))
    if not run_id or not challenge_id:
        return {}
    try:
        from redis import Redis

        redis_url = os.getenv(
            "COMMAND_CENTER_CELERY_RESULT_BACKEND",
            os.getenv("COMMAND_CENTER_REDIS_URL", "redis://localhost:6379/0"),
        )
        if not _redis_endpoint_binding(redis_url):
            return {}
        client = Redis.from_url(redis_url)
        if not (
            type(client) is Redis
            and _method_has_official_owner(client, "getdel", module_prefixes=("redis.",))
        ):
            return {}
        try:
            secret = client.getdel(_worker_challenge_key(run_id, challenge_id))
        finally:
            client.close()
    except Exception:
        return {}
    if not isinstance(secret, (bytes, bytearray)) or len(secret) < 32:
        return {}
    material = _worker_execution_proof_material(payload, runtime)
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    proof = hmac.new(bytes(secret), encoded, hashlib.sha256).hexdigest()
    return {
        "worker_challenge_id": challenge_id,
        "worker_challenge_consumed": True,
        "worker_execution_proof": proof,
    }


def _execute_candidate_radar_batch_after_challenge(
    payload: Any,
    *,
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    runtime_map = dict(runtime) if isinstance(runtime, Mapping) else {}
    request_id = str(runtime_map.get("celery_request_id") or "")
    symbols, duplicates, invalid = _normalize_symbols(payload_map.get("symbols"))
    worker_task_id = f"candidate-worker-{request_id or uuid.uuid4().hex}"
    base = {
        "task_id": worker_task_id,
        "task_type": CANDIDATE_TASK_TYPE,
        "status": "failed",
        "current_step": "candidate_radar_full_market_batch_blocked",
        "payload_safe": {
            "acceptance_run_id": str(payload_map.get("acceptance_run_id") or ""),
            "celery_dispatch_id": str(payload_map.get("celery_dispatch_id") or ""),
            "batch_index": _integer(payload_map.get("batch_index"), default=-1),
            "batch_count": _integer(payload_map.get("batch_count")),
            "batch_symbol_count": len(symbols),
            "batch_symbol_hash": str(payload_map.get("batch_symbol_hash") or ""),
            "batch_input_hash": str(payload_map.get("batch_input_hash") or ""),
            "universe_digest": str(payload_map.get("universe_digest") or ""),
            "provider_scope_hash": str(payload_map.get("provider_scope_hash") or ""),
            "provider_version_digest": str(payload_map.get("provider_version_digest") or ""),
            **{
                key: str(payload_map.get(key) or "")
                for key in INDUSTRY_BINDING_DIGEST_KEYS
            },
            "industry_input_digest": str(payload_map.get("industry_input_digest") or ""),
            "worker_challenge_id": str(payload_map.get("worker_challenge_id") or ""),
        },
        "runtime_provenance": runtime_map,
        "candidate_rows": [],
        "candidate_output_hash": "",
        "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "synthetic_fixture": runtime_map.get("synthetic_fixture") is not False,
    }
    runtime_ready = bool(
        runtime_map.get("bound_task_request") is True
        and runtime_map.get("synthetic_fixture") is False
        and request_id
        and request_id == payload_map.get("celery_dispatch_id")
        and runtime_map.get("worker_hostname")
        and _integer(runtime_map.get("worker_pid")) > 0
        and runtime_map.get("worker_queue") == CANDIDATE_QUEUE
        and runtime_map.get("worker_challenge_consumed") is True
        and runtime_map.get("worker_challenge_id") == payload_map.get("worker_challenge_id")
        and _normalize_uuid4(runtime_map.get("worker_challenge_id"))
        and _HEX_64_RE.fullmatch(str(runtime_map.get("worker_execution_proof") or ""))
    )
    payload_ready = bool(
        payload_map.get("full_market_worker_acceptance") is True
        and payload_map.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and not duplicates
        and not invalid
        and MIN_BATCH_SIZE <= len(symbols) <= MAX_BATCH_SIZE
        and payload_map.get("batch_symbol_hash") == _canonical_digest(symbols)
        and _industry_binding_ready(payload_map)
        and payload_map.get("industry_input_digest")
        == _industry_input_digest(payload_map)
        and _normalize_uuid4(payload_map.get("worker_challenge_id"))
    )
    if not runtime_ready or not payload_ready:
        base["failure_reason_safe"] = "bound_celery_runtime_or_batch_contract_invalid"
        return _persist_task(base)

    minimum = _bounded_integer(
        payload_map.get("minimum_universe_size"),
        default=DEFAULT_MINIMUM_UNIVERSE_SIZE,
        minimum=DEFAULT_MINIMUM_UNIVERSE_SIZE,
        maximum=MAXIMUM_MINIMUM_UNIVERSE_SIZE,
    )
    universe = _authoritative_provider_universe(
        EVIDENCE_ROOT,
        minimum_universe_size=minimum,
        include_frames=True,
        require_industry_membership=True,
    )
    if not (
        universe.get("ready") is True
        and universe.get("scope_hash") == payload_map.get("provider_scope_hash")
        and universe.get("version_digest") == payload_map.get("provider_version_digest")
        and universe.get("universe_digest") == payload_map.get("universe_digest")
        and _industry_binding(universe) == _industry_binding(payload_map)
        and payload_map.get("industry_input_digest") == _industry_input_digest(universe)
        and set(symbols).issubset(set(universe.get("symbols") or []))
    ):
        base["failure_reason_safe"] = "worker_independent_provider_universe_validation_failed"
        return _persist_task(base)
    input_hash = _batch_input_hash(universe, symbols)
    if input_hash != payload_map.get("batch_input_hash"):
        base["failure_reason_safe"] = "worker_independent_provider_input_hash_mismatch"
        return _persist_task(base)
    try:
        candidate_rows = _score_candidate_rows(universe, symbols)
    except Exception as exc:
        base["failure_reason_safe"] = f"candidate_scoring_failed_{type(exc).__name__}"
        return _persist_task(base)
    output_hash = _canonical_digest(candidate_rows) if candidate_rows else ""
    output_symbols, output_duplicates, output_invalid = _normalize_symbols(
        [row.get("ts_code") for row in candidate_rows]
    )
    if not (
        candidate_rows
        and output_symbols == symbols
        and not output_duplicates
        and not output_invalid
        and _HEX_64_RE.fullmatch(output_hash)
        and all(row.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST for row in candidate_rows)
    ):
        base["failure_reason_safe"] = "candidate_scored_output_incomplete_or_invalid"
        return _persist_task(base)
    base.update(
        {
            "status": "success",
            "current_step": "candidate_radar_full_market_batch_completed",
            "candidate_rows": candidate_rows,
            "candidate_output_hash": output_hash,
            "batch_input_hash": input_hash,
            "worker_runtime_digest": _canonical_digest(runtime_map),
            "candidate_row_count": len(candidate_rows),
            "provider_scope_hash": universe["scope_hash"],
            "provider_version_digest": universe["version_digest"],
            "universe_digest": universe["universe_digest"],
            "validated_trade_date": universe["validated_trade_date"],
            **_industry_binding(universe),
            "industry_input_digest": _industry_input_digest(universe),
            "synthetic_fixture": False,
            "call_ledger": [
                {
                    "api": "local_candidate_radar_full_market_scoring",
                    "call_status": "success",
                    "row_count": len(candidate_rows),
                    "batch_symbol_hash": _canonical_digest(symbols),
                    "batch_input_hash": input_hash,
                    "candidate_output_hash": output_hash,
                    "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
                    "external_calls_triggered": False,
                    "tushare_called": False,
                    "deepseek_called": False,
                    "github_called": False,
                    "does_not_execute_trades": True,
                    "does_not_modify_strategy_action": True,
                    "contains_secret": False,
                }
            ],
        }
    )
    return _persist_task(base)


def execute_candidate_radar_batch_worker(
    payload: Any,
    *,
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    """Caller-supplied runtime mappings are never production worker proof."""

    rejected_runtime = {
        **(dict(runtime) if isinstance(runtime, Mapping) else {}),
        "bound_task_request": False,
        "synthetic_fixture": True,
        "worker_challenge_consumed": False,
        "worker_execution_proof": "",
    }
    return _execute_candidate_radar_batch_after_challenge(payload, runtime=rejected_runtime)


def execute_candidate_radar_batch_from_bound_celery(
    payload: Any,
    *,
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    """Consume the one-time Redis challenge before entering worker execution."""

    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    runtime_map = dict(runtime) if isinstance(runtime, Mapping) else {}
    proof = _consume_official_worker_challenge(payload_map, runtime_map)
    if not proof:
        runtime_map.update(
            {
                "bound_task_request": False,
                "synthetic_fixture": True,
                "worker_challenge_consumed": False,
                "worker_execution_proof": "",
            }
        )
    else:
        runtime_map.update(proof)
    return _execute_candidate_radar_batch_after_challenge(payload_map, runtime=runtime_map)


def _load_celery_app() -> Any:
    """Legacy test seam; production does not consume this value."""

    return None


def _mock_like(value: Any) -> bool:
    return type(value).__module__.startswith("unittest.mock")


def _method_has_official_owner(value: Any, name: str, *, module_prefixes: tuple[str, ...]) -> bool:
    if name in getattr(value, "__dict__", {}):
        return False
    owner = next((item for item in type(value).__mro__ if name in item.__dict__), None)
    if owner is None or not owner.__module__.startswith(module_prefixes):
        return False
    method = inspect.getattr_static(type(value), name, None)
    module = str(getattr(method, "__module__", owner.__module__) or "")
    return module.startswith((*module_prefixes, "kombu."))


def _redis_endpoint_binding(value: Any) -> dict[str, Any]:
    try:
        parsed = urlsplit(str(value or ""))
        port = parsed.port
    except Exception:
        return {}
    if parsed.scheme.lower() not in {"redis", "rediss"} or not parsed.hostname or port is None:
        return {}
    material = {
        "scheme": parsed.scheme.lower(),
        "hostname": parsed.hostname.lower(),
        "port": port,
        "database_path": parsed.path or "/0",
    }
    return {
        "scheme": material["scheme"],
        "explicit_host": True,
        "explicit_port": True,
        "endpoint_digest": _canonical_digest(material),
    }


def _transport_probe(app: Any, *, acceptance_run_id: str) -> dict[str, Any]:
    """Test/injected probes can exercise shape checks but never produce truth."""

    return {
        "ready": False,
        "status": "injected_or_caller_supplied_transport_non_production",
        "acceptance_run_id": acceptance_run_id,
        "dispatch_count": 0,
        "synthetic_fixture": True,
        "production_eligible": False,
        "contains_secret": False,
    }


def _build_and_probe_official_transport(*, acceptance_run_id: str) -> tuple[Any, dict[str, Any]]:
    try:
        from celery import Celery
        from celery.app.control import Control, Inspect
        from celery.backends.redis import RedisBackend
        from kombu import Connection
        from kombu.transport.redis import Channel as RedisChannel
        from redis import Redis
    except Exception:
        return None, {"ready": False, "status": "official_celery_dependencies_unavailable", "dispatch_count": 0}

    redis_url = os.getenv("COMMAND_CENTER_REDIS_URL", "redis://localhost:6379/0")
    broker_url = os.getenv("COMMAND_CENTER_CELERY_BROKER_URL", redis_url)
    result_backend = os.getenv("COMMAND_CENTER_CELERY_RESULT_BACKEND", redis_url)
    broker_binding = _redis_endpoint_binding(broker_url)
    backend_binding = _redis_endpoint_binding(result_backend)
    if not broker_binding or not backend_binding:
        return None, {
            "ready": False,
            "status": "explicit_redis_host_and_port_required",
            "dispatch_count": 0,
            "synthetic_fixture": False,
            "production_eligible": False,
        }
    try:
        app = Celery(
            "stock_ming_command_center_3_full_market_production",
            broker=broker_url,
            backend=result_backend,
            include=["worker.tasks_candidate"],
        )
        app.conf.task_track_started = True
    except Exception:
        return None, {"ready": False, "status": "official_celery_app_construction_failed", "dispatch_count": 0}
    if not (
        type(app) is Celery
        and _method_has_official_owner(app, "connection_for_write", module_prefixes=("celery.",))
        and _method_has_official_owner(app, "send_task", module_prefixes=("celery.",))
        and _method_has_official_owner(app, "AsyncResult", module_prefixes=("celery.",))
    ):
        return None, {"ready": False, "status": "official_celery_app_identity_required", "dispatch_count": 0}
    eager = bool(app.conf.task_always_eager)
    if eager:
        return None, {"ready": False, "status": "eager_inproc_transport_rejected", "dispatch_count": 0}

    broker_direct = False
    backend_direct = False
    backend_delete_verified = False
    backend_post_delete_missing = False
    probe_digest = _canonical_digest({"run": acceptance_run_id, "nonce": uuid.uuid4().hex})
    probe_key = f"cc3:full-market:{acceptance_run_id}:probe"
    try:
        connection = app.connection_for_write()
        if not (
            type(connection) is Connection
            and _method_has_official_owner(connection, "ensure_connection", module_prefixes=("kombu.",))
            and _method_has_official_owner(connection, "channel", module_prefixes=("kombu.",))
            and _method_has_official_owner(connection, "release", module_prefixes=("kombu.",))
        ):
            raise RuntimeError("real_kombu_connection_required")
        connection.ensure_connection(max_retries=0)
        channel = connection.channel()
        broker_client = channel.client
        if (
            type(channel) is not RedisChannel
            or type(broker_client) is not Redis
            or not _method_has_official_owner(broker_client, "ping", module_prefixes=("redis.",))
        ):
            raise RuntimeError("real_kombu_redis_channel_required")
        broker_direct = bool(connection.connected and broker_client.ping() is True)
        channel.close()
        connection.release()
    except Exception:
        broker_direct = False
    try:
        if type(app.backend) is not RedisBackend:
            raise RuntimeError("real_celery_redis_backend_required")
        client = app.backend.client
        if not (
            type(client) is Redis
            and all(
                _method_has_official_owner(client, name, module_prefixes=("redis.",))
                for name in ("ping", "set", "get", "delete")
            )
        ):
            raise RuntimeError("real_redis_backend_client_required")
        ping = client.ping()
        client.set(probe_key, probe_digest, ex=30)
        roundtrip = client.get(probe_key)
        deleted = client.delete(probe_key)
        after_delete = client.get(probe_key)
        decoded = roundtrip.decode("utf-8") if isinstance(roundtrip, bytes) else str(roundtrip or "")
        backend_delete_verified = _integer(deleted) == 1
        backend_post_delete_missing = after_delete is None
        backend_direct = bool(
            ping is True
            and decoded == probe_digest
            and backend_delete_verified
            and backend_post_delete_missing
        )
    except Exception:
        backend_direct = False
    if not broker_direct or not backend_direct:
        return None, {"ready": False, "status": "redis_broker_or_backend_direct_probe_failed", "dispatch_count": 0}

    try:
        control = app.control
        if not (
            type(control) is Control
            and _method_has_official_owner(control, "inspect", module_prefixes=("celery.",))
        ):
            raise RuntimeError("real_celery_control_required")
        inspector = control.inspect(timeout=3)
        if not (
            isinstance(inspector, Inspect)
            and all(
                _method_has_official_owner(inspector, name, module_prefixes=("celery.",))
                for name in ("ping", "registered", "active_queues")
            )
        ):
            raise RuntimeError("real_celery_inspector_required")
        pings = inspector.ping() or {}
        registered = inspector.registered() or {}
        queues = inspector.active_queues() or {}
    except Exception:
        pings, registered, queues = {}, {}, {}
    workers = sorted(set(pings).intersection(registered).intersection(queues))
    eligible_workers: list[str] = []
    for worker in workers:
        task_names = {
            str(item).split(" ", 1)[0].split("(", 1)[0]
            for item in registered.get(worker) or []
        }
        queue_names = {str(item.get("name") or "") for item in queues.get(worker) or [] if isinstance(item, Mapping)}
        if CANDIDATE_TASK_NAME in task_names and CANDIDATE_QUEUE in queue_names:
            eligible_workers.append(worker)
    ready = bool(eligible_workers)
    official_origin = {
        "celery_app_type": f"{type(app).__module__}.{type(app).__qualname__}",
        "broker_connection_type": "kombu.connection.Connection",
        "broker_channel_type": "kombu.transport.redis.Channel",
        "redis_client_type": "redis.client.Redis",
        "redis_backend_type": "celery.backends.redis.RedisBackend",
        "inspector_type": "celery.app.control.Inspect",
        "broker_endpoint_digest": broker_binding["endpoint_digest"],
        "backend_endpoint_digest": backend_binding["endpoint_digest"],
    }
    return app if ready else None, {
        "ready": ready,
        "status": "external_redis_celery_direct_attested" if ready else "registered_task_or_queue_missing",
        "schema_version": TRANSPORT_SCHEMA_VERSION,
        "acceptance_run_id": acceptance_run_id,
        "broker_direct_ping": broker_direct,
        "backend_roundtrip_verified": backend_direct,
        "backend_delete_verified": backend_delete_verified,
        "backend_post_delete_missing": backend_post_delete_missing,
        "registered_task_verified": bool(eligible_workers),
        "registered_queue_verified": bool(eligible_workers),
        "eligible_worker_count": len(eligible_workers),
        "eligible_worker_names": eligible_workers,
        "task_always_eager": eager,
        "probe_digest": probe_digest,
        "broker_endpoint_digest": broker_binding["endpoint_digest"],
        "backend_endpoint_digest": backend_binding["endpoint_digest"],
        "broker_explicit_host_port": True,
        "backend_explicit_host_port": True,
        "official_runtime_origin_digest": _canonical_digest(official_origin),
        "production_eligible": ready,
        "call_ledger": [
            {
                "api": "redis_celery_direct_transport_probe",
                "call_status": "success" if ready else "blocked",
                "broker_ping": broker_direct,
                "backend_roundtrip": backend_direct,
                "backend_delete_verified": backend_delete_verified,
                "backend_post_delete_missing": backend_post_delete_missing,
                "eligible_worker_count": len(eligible_workers),
                "external_calls_triggered": True,
                "redis_called": True,
                "celery_called": True,
                "does_not_execute_trades": True,
                "contains_secret": False,
            }
        ],
        "synthetic_fixture": False,
        "contains_secret": False,
    }


def _partition_symbols(symbols: list[str], requested_size: int) -> list[list[str]]:
    size = _bounded_integer(
        requested_size,
        default=DEFAULT_BATCH_SIZE,
        minimum=MIN_BATCH_SIZE,
        maximum=MAX_BATCH_SIZE,
    )
    batches = [symbols[index : index + size] for index in range(0, len(symbols), size)]
    if len(batches) > 1 and len(batches[-1]) < MIN_BATCH_SIZE:
        tail = batches.pop()
        while tail:
            target = min(range(len(batches)), key=lambda index: len(batches[index]))
            if len(batches[target]) >= MAX_BATCH_SIZE:
                return []
            batches[target].append(tail.pop(0))
    return [sorted(batch) for batch in batches if batch]


def _checkpoint_key(run_id: str) -> str:
    return f"{CHECKPOINT_PACKET_PREFIX}:{run_id}"


def _stage_key(run_id: str) -> str:
    return f"{STAGE_PACKET_PREFIX}:{run_id}"


def _transport_key(run_id: str) -> str:
    return f"{TRANSPORT_PACKET_PREFIX}:{run_id}"


def _execution_event_key(run_id: str) -> str:
    return f"{EXECUTION_EVENT_PACKET_PREFIX}:{run_id}"


def _promotion_journal_path() -> Path:
    return PARQUET_ROOT / RESULT_DATASET / PROMOTION_JOURNAL_NAME


def _quarantine_key(run_id: str) -> str:
    return f"{ATTEMPT_PACKET_KEY}:quarantine:{run_id}"


def _quarantined_task_ids_for_db(db_path: Path, run_id: str) -> set[str]:
    packet = _read_packet_no_init(db_path, _quarantine_key(run_id))
    return {str(item) for item in packet.get("celery_task_ids") or [] if str(item)}


def _quarantined_task_ids(run_id: str) -> set[str]:
    return _quarantined_task_ids_for_db(SQLITE_META_PATH, run_id)


def _acquire_lock(run_id: str) -> bool:
    SQLiteMetaStore(SQLITE_META_PATH)
    connection = sqlite3.connect(SQLITE_META_PATH, timeout=5)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT payload_json FROM packets WHERE packet_key = ?",
            (LOCK_PACKET_KEY,),
        ).fetchone()
        existing = json.loads(row[0]) if row else {}
        started = _dt.datetime.fromisoformat(str(existing.get("started_at") or "")) if existing else None
        age = (_dt.datetime.now(_dt.timezone.utc) - started).total_seconds() if started else LOCK_TTL_SECONDS + 1
        if existing.get("active") is True and age < LOCK_TTL_SECONDS:
            connection.rollback()
            return False
        payload = {
            "schema_version": "full_market_worker_lock.v1",
            "active": True,
            "acceptance_run_id": run_id,
            "started_at": _now_iso(),
            "contains_secret": False,
        }
        connection.execute(
            "INSERT INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(packet_key) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at",
            (LOCK_PACKET_KEY, json.dumps(payload, sort_keys=True), _now_iso()),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        return False
    finally:
        connection.close()


def _release_lock(run_id: str) -> None:
    current = _read_packet_no_init(SQLITE_META_PATH, LOCK_PACKET_KEY)
    if current.get("acceptance_run_id") != run_id:
        return
    current.update({"active": False, "released_at": _now_iso()})
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(LOCK_PACKET_KEY, current)
    except Exception:
        pass


def _write_coordinator_task(run_id: str, *, status: str, step: str, checkpoint_key: str) -> dict[str, Any]:
    task = {
        "task_id": f"full-market-coordinator-{run_id}",
        "task_type": "run_candidate_radar_full_market_production_acceptance",
        "status": status,
        "current_step": step,
        "payload_safe": {"acceptance_run_id": run_id, "checkpoint_key": checkpoint_key},
        "backend": "fastapi_explicit_post_coordinator",
        "external_calls_triggered": status in {"running", "success"},
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "synthetic_fixture": False,
    }
    return _persist_task(task)


def _validate_worker_task(
    task: Mapping[str, Any],
    *,
    batch: Mapping[str, Any],
    universe: Mapping[str, Any],
    transport: Mapping[str, Any] | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    payload = task.get("payload_safe") if isinstance(task.get("payload_safe"), Mapping) else {}
    runtime = task.get("runtime_provenance") if isinstance(task.get("runtime_provenance"), Mapping) else {}
    rows = [dict(row) for row in task.get("candidate_rows") or [] if isinstance(row, Mapping)]
    symbols, duplicates, invalid = _normalize_symbols([row.get("ts_code") for row in rows])
    expected_symbols = list(batch.get("symbols") or [])
    expected_input_hash = _batch_input_hash(universe, expected_symbols)
    expected_rows = _score_candidate_rows(universe, expected_symbols)
    expected_output_hash = _canonical_digest(expected_rows) if expected_rows else ""
    transport_map = dict(transport) if isinstance(transport, Mapping) else {}
    call_ledger = [
        dict(item)
        for item in task.get("call_ledger") or []
        if isinstance(item, Mapping)
    ]
    eligible_workers = {
        str(item) for item in transport_map.get("eligible_worker_names") or [] if str(item)
    }
    hostname = str(runtime.get("worker_hostname") or "")
    ready = bool(
        task.get("task_type") == CANDIDATE_TASK_TYPE
        and task.get("status") == "success"
        and task.get("current_step") == "candidate_radar_full_market_batch_completed"
        and task.get("synthetic_fixture") is False
        and runtime.get("bound_task_request") is True
        and runtime.get("synthetic_fixture") is False
        and runtime.get("celery_request_id") == batch.get("celery_task_id")
        and hostname
        and (not eligible_workers or hostname in eligible_workers)
        and _integer(runtime.get("worker_pid")) > 0
        and runtime.get("worker_queue") == CANDIDATE_QUEUE
        and payload.get("acceptance_run_id") == batch.get("acceptance_run_id")
        and payload.get("celery_dispatch_id") == batch.get("celery_task_id")
        and _integer(payload.get("batch_index"), default=-1) == _integer(batch.get("batch_index"), default=-2)
        and _integer(payload.get("batch_count")) == _integer(batch.get("batch_count"))
        and _integer(payload.get("batch_symbol_count")) == len(expected_symbols)
        and payload.get("batch_symbol_hash") == batch.get("batch_symbol_hash")
        and payload.get("batch_input_hash") == expected_input_hash
        and payload.get("universe_digest") == universe.get("universe_digest")
        and payload.get("provider_scope_hash") == universe.get("scope_hash")
        and payload.get("provider_version_digest") == universe.get("version_digest")
        and _industry_binding(payload) == _industry_binding(universe)
        and payload.get("industry_input_digest") == _industry_input_digest(universe)
        and _industry_binding(batch) == _industry_binding(universe)
        and batch.get("industry_input_digest") == _industry_input_digest(universe)
        and _normalize_uuid4(payload.get("worker_challenge_id"))
        and payload.get("worker_challenge_id") == runtime.get("worker_challenge_id")
        and runtime.get("worker_challenge_consumed") is True
        and _HEX_64_RE.fullmatch(str(runtime.get("worker_execution_proof") or ""))
        and symbols == expected_symbols
        and not duplicates
        and not invalid
        and rows == expected_rows
        and task.get("batch_input_hash") == expected_input_hash
        and task.get("candidate_output_hash") == expected_output_hash == _canonical_digest(rows)
        and task.get("worker_runtime_digest") == _canonical_digest(runtime)
        and task.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and len(call_ledger) == 1
        and call_ledger[0].get("api") == "local_candidate_radar_full_market_scoring"
        and call_ledger[0].get("call_status") == "success"
        and _integer(call_ledger[0].get("row_count")) == len(rows)
        and call_ledger[0].get("external_calls_triggered") is False
        and call_ledger[0].get("contains_secret") is False
        and _ledger_sanitized(call_ledger)
        and all(row.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST for row in rows)
        and all(row.get("does_not_execute_trades") is True for row in rows)
    )
    return ready, rows


def _dispatch_chain_ready(
    success: Mapping[str, Any],
    task: Mapping[str, Any],
    *,
    run_id: str,
    transport: Mapping[str, Any],
) -> bool:
    chain = success.get("dispatch_chain") if isinstance(success.get("dispatch_chain"), Mapping) else {}
    task_digest = _canonical_digest(task) if task else ""
    runtime = task.get("runtime_provenance") if isinstance(task.get("runtime_provenance"), Mapping) else {}
    chain_workers = {
        str(item) for item in chain.get("eligible_worker_names") or [] if str(item)
    }
    attestation = (
        chain.get("transport_attestation")
        if isinstance(chain.get("transport_attestation"), Mapping)
        else {}
    )
    transport_map = dict(transport) if isinstance(transport, Mapping) else {}
    attestation_workers = {
        str(item) for item in attestation.get("eligible_worker_names") or [] if str(item)
    }
    persisted_workers = {
        str(item) for item in transport_map.get("eligible_worker_names") or [] if str(item)
    }
    hostname = str(runtime.get("worker_hostname") or "")
    return bool(
        chain
        and success.get("dispatch_chain_digest") == _canonical_digest(chain)
        and chain.get("acceptance_run_id") == run_id
        and _integer(chain.get("batch_index"), default=-1)
        == _integer(success.get("batch_index"), default=-2)
        and chain.get("batch_input_hash") == success.get("batch_input_hash")
        and chain.get("celery_task_id") == success.get("celery_task_id")
        and chain.get("dispatch_result_id") == success.get("celery_task_id")
        and chain.get("async_result_id") == success.get("celery_task_id")
        and chain.get("async_result_state") == "SUCCESS"
        and chain.get("persisted_task_digest") == task_digest
        and chain.get("candidate_output_hash") == task.get("candidate_output_hash")
        and chain.get("worker_runtime_digest") == task.get("worker_runtime_digest")
        and _normalize_uuid4(chain.get("worker_challenge_id"))
        and chain.get("worker_challenge_id") == runtime.get("worker_challenge_id")
        and chain.get("worker_challenge_consumed") is True
        and chain.get("worker_execution_proof_verified") is True
        and attestation == transport_map
        and chain.get("transport_attestation_digest") == _canonical_digest(transport_map)
        and _transport_attestation_ready(attestation, run_id=run_id)
        and chain_workers == attestation_workers == persisted_workers
        and hostname in persisted_workers
        and success.get("worker_hostname") == hostname
        and _integer(success.get("worker_pid")) == _integer(runtime.get("worker_pid")) > 0
        and success.get("worker_queue") == runtime.get("worker_queue") == CANDIDATE_QUEUE
    )


def _transport_attestation_ready(attestation: Mapping[str, Any], *, run_id: str) -> bool:
    workers = [str(item) for item in attestation.get("eligible_worker_names") or [] if str(item)]
    call_ledger = [
        dict(item)
        for item in attestation.get("call_ledger") or []
        if isinstance(item, Mapping)
    ]
    return bool(
        attestation.get("ready") is True
        and attestation.get("schema_version") == TRANSPORT_SCHEMA_VERSION
        and attestation.get("status") == "external_redis_celery_direct_attested"
        and attestation.get("acceptance_run_id") == run_id
        and attestation.get("broker_direct_ping") is True
        and attestation.get("backend_roundtrip_verified") is True
        and attestation.get("backend_delete_verified") is True
        and attestation.get("backend_post_delete_missing") is True
        and attestation.get("registered_task_verified") is True
        and attestation.get("registered_queue_verified") is True
        and _integer(attestation.get("eligible_worker_count")) == len(workers) > 0
        and workers == sorted(set(workers))
        and attestation.get("task_always_eager") is False
        and attestation.get("broker_explicit_host_port") is True
        and attestation.get("backend_explicit_host_port") is True
        and _HEX_64_RE.fullmatch(str(attestation.get("broker_endpoint_digest") or ""))
        and _HEX_64_RE.fullmatch(str(attestation.get("backend_endpoint_digest") or ""))
        and _HEX_64_RE.fullmatch(str(attestation.get("official_runtime_origin_digest") or ""))
        and attestation.get("production_eligible") is True
        and attestation.get("synthetic_fixture") is False
        and len(call_ledger) == 1
        and call_ledger[0].get("api") == "redis_celery_direct_transport_probe"
        and call_ledger[0].get("call_status") == "success"
        and call_ledger[0].get("contains_secret") is False
        and _ledger_sanitized(attestation)
    )


_TRANSPORT_EVENT_FIELDS = {
    "transport_core_digest",
    "execution_event_key",
    "execution_event_digest",
}


def _transport_core(attestation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(attestation).items()
        if key not in _TRANSPORT_EVENT_FIELDS
    }


def _persist_transport_execution_event_atomic(
    run_id: str,
    attestation: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Module callers cannot turn a mapping into production transport truth."""

    del run_id, attestation
    return {}, {}


def _persist_official_transport_execution_event_atomic(
    run_id: str,
    attestation: Mapping[str, Any],
    *,
    capability: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = _official_orchestrator_state(capability, run_id)
    if not state or state.get("official_transport_probed") is not True:
        return {}, {}
    if not _transport_attestation_ready(attestation, run_id=run_id):
        return {}, {}
    core = _transport_core(attestation)
    core_digest = _canonical_digest(core)
    worker_names = sorted(str(item) for item in core.get("eligible_worker_names") or [] if str(item))
    event_key = _execution_event_key(run_id)
    event = {
        "packet_key": event_key,
        "schema_version": EXECUTION_EVENT_SCHEMA_VERSION,
        "status": "official_redis_celery_transport_execution_succeeded",
        "created_at": _now_iso(),
        "acceptance_run_id": run_id,
        "transport_core_digest": core_digest,
        "official_runtime_origin_digest": core.get("official_runtime_origin_digest"),
        "probe_digest": core.get("probe_digest"),
        "eligible_worker_set_digest": _canonical_digest(worker_names),
        "broker_endpoint_digest": core.get("broker_endpoint_digest"),
        "backend_endpoint_digest": core.get("backend_endpoint_digest"),
        "ping_set_get_delete_post_delete_verified": True,
        "synthetic_fixture": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
    }
    final = {
        **core,
        "transport_core_digest": core_digest,
        "execution_event_key": event_key,
        "execution_event_digest": _canonical_digest(event),
    }
    SQLiteMetaStore(SQLITE_META_PATH)
    connection = sqlite3.connect(SQLITE_META_PATH, timeout=5)
    try:
        connection.execute("BEGIN IMMEDIATE")
        now = _now_iso()
        for key, value in ((_transport_key(run_id), final), (event_key, event)):
            connection.execute(
                "INSERT INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(packet_key) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at",
                (key, json.dumps(value, ensure_ascii=False, sort_keys=True), now),
            )
        rows = dict(
            connection.execute(
                "SELECT packet_key, payload_json FROM packets WHERE packet_key IN (?, ?)",
                (_transport_key(run_id), event_key),
            ).fetchall()
        )
        transport_readback = json.loads(rows.get(_transport_key(run_id), "{}"))
        event_readback = json.loads(rows.get(event_key, "{}"))
        if transport_readback != final or event_readback != event:
            raise RuntimeError("transport_execution_event_readback_mismatch")
        connection.commit()
        state["transport_event_persisted"] = True
        return final, event
    except Exception:
        connection.rollback()
        return {}, {}
    finally:
        connection.close()


def _transport_execution_event_ready(
    attestation: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    run_id: str,
) -> bool:
    core = _transport_core(attestation)
    workers = sorted(str(item) for item in core.get("eligible_worker_names") or [] if str(item))
    return bool(
        _transport_attestation_ready(attestation, run_id=run_id)
        and attestation.get("transport_core_digest") == _canonical_digest(core)
        and attestation.get("execution_event_key") == _execution_event_key(run_id)
        and attestation.get("execution_event_digest") == _canonical_digest(event)
        and event.get("packet_key") == _execution_event_key(run_id)
        and event.get("schema_version") == EXECUTION_EVENT_SCHEMA_VERSION
        and event.get("status") == "official_redis_celery_transport_execution_succeeded"
        and event.get("acceptance_run_id") == run_id
        and event.get("transport_core_digest") == _canonical_digest(core)
        and event.get("official_runtime_origin_digest") == core.get("official_runtime_origin_digest")
        and event.get("probe_digest") == core.get("probe_digest")
        and event.get("eligible_worker_set_digest") == _canonical_digest(workers)
        and event.get("broker_endpoint_digest") == core.get("broker_endpoint_digest")
        and event.get("backend_endpoint_digest") == core.get("backend_endpoint_digest")
        and event.get("ping_set_get_delete_post_delete_verified") is True
        and event.get("synthetic_fixture") is False
        and event.get("contains_secret") is False
    )


def _revoke_and_quarantine(app: Any, task_ids: list[str], run_id: str, reason: str) -> None:
    for task_id in task_ids:
        try:
            app.control.revoke(task_id, terminate=False)
        except Exception:
            pass
    previous = _read_packet_no_init(SQLITE_META_PATH, _quarantine_key(run_id))
    quarantined = sorted(
        {str(item) for item in previous.get("celery_task_ids") or [] if str(item)}
        | {str(item) for item in task_ids if str(item)}
    )
    reasons = [str(item) for item in previous.get("reasons") or [] if str(item)]
    reasons.append(reason)
    packet = {
        "schema_version": "full_market_worker_late_result_quarantine.v1",
        "status": "late_results_quarantined",
        "acceptance_run_id": run_id,
        "celery_task_ids": quarantined,
        "reason": reason,
        "reasons": list(dict.fromkeys(reasons)),
        "global_candidate_cache_overwritten": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(_quarantine_key(run_id), packet)
    except Exception:
        pass


def _dispatch_batches(
    app: Any,
    *,
    batches: list[list[str]],
    run_id: str,
    universe: Mapping[str, Any],
    transport: Mapping[str, Any],
    timeout_seconds: int,
    prior_successes: list[dict[str, Any]] | None = None,
    challenge_issuer: Any = None,
    challenge_verifier: Any = None,
    challenge_cleanup: Any = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        from celery.result import AsyncResult as OfficialAsyncResult
    except Exception:
        return list(prior_successes or []), []
    successes = list(prior_successes or [])
    if not callable(challenge_issuer) or not callable(challenge_verifier):
        return successes, []
    completed_indexes = {_integer(row.get("batch_index"), default=-1) for row in successes}
    quarantined_ids = _quarantined_task_ids(run_id)
    allocated_ids = quarantined_ids | {
        str(row.get("celery_task_id") or "") for row in successes if str(row.get("celery_task_id") or "")
    }
    sent: list[tuple[Any, dict[str, Any]]] = []
    all_dispatched_ids: list[str] = []
    for batch_index, symbols in enumerate(batches):
        if batch_index in completed_indexes:
            continue
        celery_task_id = f"fmw-{run_id}-{batch_index:04d}-{uuid.uuid4().hex}"
        while celery_task_id in allocated_ids:
            celery_task_id = f"fmw-{run_id}-{batch_index:04d}-{uuid.uuid4().hex}"
        allocated_ids.add(celery_task_id)
        specification = {
            "acceptance_run_id": run_id,
            "batch_index": batch_index,
            "batch_count": len(batches),
            "symbols": symbols,
            "batch_symbol_hash": _canonical_digest(symbols),
            "batch_input_hash": _batch_input_hash(universe, symbols),
            **_industry_binding(universe),
            "industry_input_digest": _industry_input_digest(universe),
            "celery_task_id": celery_task_id,
        }
        challenge_id = str(challenge_issuer(specification) or "")
        if not _normalize_uuid4(challenge_id):
            if callable(challenge_cleanup):
                challenge_cleanup([challenge_id])
            _revoke_and_quarantine(app, all_dispatched_ids, run_id, "worker_challenge_issue_failed")
            return successes, all_dispatched_ids
        specification["worker_challenge_id"] = challenge_id
        payload = {
            **specification,
            "celery_dispatch_id": celery_task_id,
            "full_market_worker_acceptance": True,
            "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
            "universe_digest": universe["universe_digest"],
            "provider_scope_hash": universe["scope_hash"],
            "provider_version_digest": universe["version_digest"],
            "minimum_universe_size": universe["minimum_universe_size"],
            **_industry_binding(universe),
            "industry_input_digest": _industry_input_digest(universe),
            "worker_challenge_id": challenge_id,
        }
        try:
            result = app.send_task(
                CANDIDATE_TASK_NAME,
                args=[payload],
                task_id=celery_task_id,
                queue=CANDIDATE_QUEUE,
                routing_key=CANDIDATE_QUEUE,
            )
        except Exception:
            if callable(challenge_cleanup):
                challenge_cleanup(
                    [str(item[1].get("worker_challenge_id") or "") for item in sent]
                    + [challenge_id]
                )
            _revoke_and_quarantine(app, all_dispatched_ids, run_id, "dispatch_exception")
            return successes, all_dispatched_ids
        if not (
            isinstance(result, OfficialAsyncResult)
            and type(result).__module__ == "celery.result"
            and type(result).__qualname__ == "AsyncResult"
            and _method_has_official_owner(result, "get", module_prefixes=("celery.",))
            and str(result.id or "") == celery_task_id
        ):
            if callable(challenge_cleanup):
                challenge_cleanup([challenge_id])
            _revoke_and_quarantine(app, all_dispatched_ids + [celery_task_id], run_id, "async_result_id_mismatch")
            return successes, all_dispatched_ids + [celery_task_id]
        sent.append((result, specification))
        all_dispatched_ids.append(celery_task_id)

    deadline = time.monotonic() + timeout_seconds
    for result, specification in sent:
        celery_task_id = specification["celery_task_id"]
        try:
            returned = _get_result_before_deadline(result, deadline=deadline)
            async_result = app.AsyncResult(celery_task_id)
            if not (
                isinstance(async_result, OfficialAsyncResult)
                and type(async_result).__module__ == "celery.result"
                and type(async_result).__qualname__ == "AsyncResult"
                and _method_has_official_owner(async_result, "get", module_prefixes=("celery.",))
                and async_result.id == celery_task_id
                and async_result.state == "SUCCESS"
            ):
                raise RuntimeError("async_result_state_or_id_mismatch")
        except Exception:
            completed_ids = {item.get("celery_task_id") for item in successes}
            outstanding = [
                row[1]["celery_task_id"]
                for row in sent
                if row[1]["celery_task_id"] not in completed_ids
            ]
            _revoke_and_quarantine(app, outstanding, run_id, "result_timeout_or_failure")
            if callable(challenge_cleanup):
                challenge_cleanup(
                    [
                        str(row[1].get("worker_challenge_id") or "")
                        for row in sent
                        if row[1]["celery_task_id"] in outstanding
                    ]
                )
            return successes, all_dispatched_ids
        result_task = dict(returned) if isinstance(returned, Mapping) else {}
        worker_task_id = str(result_task.get("task_id") or "")
        persisted = _read_task_no_init(SQLITE_META_PATH, worker_task_id)
        valid, rows = _validate_worker_task(
            persisted,
            batch=specification,
            universe=universe,
            transport=transport,
        )
        returned_digest = _canonical_digest(result_task) if result_task else ""
        persisted_digest = _canonical_digest(persisted) if persisted else ""
        proof_verified = bool(valid and challenge_verifier(persisted, specification))
        if not proof_verified or returned_digest != persisted_digest:
            if callable(challenge_cleanup):
                challenge_cleanup([str(specification.get("worker_challenge_id") or "")])
            _revoke_and_quarantine(app, [celery_task_id], run_id, "worker_result_direct_readback_invalid")
            return successes, all_dispatched_ids
        chain = {
            "acceptance_run_id": run_id,
            "batch_index": specification["batch_index"],
            "batch_input_hash": specification["batch_input_hash"],
            "celery_task_id": celery_task_id,
            "dispatch_result_id": str(result.id or ""),
            "async_result_id": str(async_result.id or ""),
            "async_result_state": str(async_result.state or ""),
            "persisted_task_digest": persisted_digest,
            "candidate_output_hash": persisted["candidate_output_hash"],
            "worker_runtime_digest": persisted["worker_runtime_digest"],
            "worker_challenge_id": specification["worker_challenge_id"],
            "worker_challenge_consumed": True,
            "worker_execution_proof_verified": True,
            "transport_attestation_digest": _canonical_digest(transport),
            "transport_attestation": dict(transport),
            "eligible_worker_names": sorted(
                str(item) for item in transport.get("eligible_worker_names") or [] if str(item)
            ),
        }
        successes.append(
            {
                **specification,
                "worker_task_id": worker_task_id,
                "candidate_output_hash": persisted["candidate_output_hash"],
                "batch_input_hash": specification["batch_input_hash"],
                "candidate_row_count": len(rows),
                "worker_hostname": persisted.get("runtime_provenance", {}).get("worker_hostname"),
                "worker_pid": persisted.get("runtime_provenance", {}).get("worker_pid"),
                "worker_queue": persisted.get("runtime_provenance", {}).get("worker_queue"),
                "dispatch_chain": chain,
                "dispatch_chain_digest": _canonical_digest(chain),
            }
        )
    return sorted(successes, key=lambda row: _integer(row.get("batch_index"))), all_dispatched_ids


def _get_result_before_deadline(
    result: Any,
    *,
    deadline: float,
    clock: Any = None,
) -> Any:
    current_time = clock or time.monotonic
    remaining = deadline - float(current_time())
    if remaining <= 0:
        raise TimeoutError("global_result_deadline_exceeded_before_wait")
    returned = result.get(timeout=remaining)
    if float(current_time()) > deadline:
        raise TimeoutError("global_result_deadline_exceeded_after_response")
    return returned


def _write_checkpoint(
    *,
    run_id: str,
    universe: Mapping[str, Any],
    batches: list[list[str]],
    successes: list[dict[str, Any]],
    status: str,
    transport: Mapping[str, Any],
) -> dict[str, Any]:
    packet = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "status": status,
        "acceptance_run_id": run_id,
        "provider_scope_hash": universe.get("scope_hash"),
        "provider_version_digest": universe.get("version_digest"),
        "universe_digest": universe.get("universe_digest"),
        **_industry_binding(universe),
        "industry_input_digest": _industry_input_digest(universe),
        "transport_attestation_digest": _canonical_digest(transport),
        "transport_execution_event_key": transport.get("execution_event_key"),
        "transport_execution_event_digest": transport.get("execution_event_digest"),
        "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
        "batch_count": len(batches),
        "batch_specifications": [
            {
                "batch_index": index,
                "batch_count": len(batches),
                "symbols": symbols,
                "batch_symbol_hash": _canonical_digest(symbols),
                "batch_input_hash": _batch_input_hash(universe, symbols),
                **_industry_binding(universe),
                "industry_input_digest": _industry_input_digest(universe),
            }
            for index, symbols in enumerate(batches)
        ],
        "successful_batches": successes,
        "successful_batch_count": len(successes),
        "resume_available": status != "complete" and bool(successes),
        "global_candidate_cache_overwritten": False,
        "synthetic_fixture": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }
    packet["checkpoint_binding_digest"] = _canonical_digest(packet)
    SQLiteMetaStore(SQLITE_META_PATH).write_packet(_checkpoint_key(run_id), packet)
    return packet


def _validated_resume_successes(
    checkpoint: Mapping[str, Any],
    *,
    run_id: str,
    universe: Mapping[str, Any],
    batches: list[list[str]],
    transport: Mapping[str, Any],
    execution_event: Mapping[str, Any],
    resume_proof_verifier: Any = None,
) -> list[dict[str, Any]]:
    if not (
        checkpoint.get("schema_version") == CHECKPOINT_SCHEMA_VERSION
        and checkpoint.get("status") == "partial_failure_resume_available"
        and checkpoint.get("resume_available") is True
        and checkpoint.get("acceptance_run_id") == run_id
        and checkpoint.get("synthetic_fixture") is False
        and checkpoint.get("provider_scope_hash") == universe.get("scope_hash")
        and checkpoint.get("provider_version_digest") == universe.get("version_digest")
        and checkpoint.get("universe_digest") == universe.get("universe_digest")
        and _industry_binding(checkpoint) == _industry_binding(universe)
        and checkpoint.get("industry_input_digest") == _industry_input_digest(universe)
        and checkpoint.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and _integer(checkpoint.get("batch_count")) == len(batches)
        and checkpoint.get("transport_attestation_digest") == _canonical_digest(transport)
        and checkpoint.get("transport_execution_event_key") == transport.get("execution_event_key")
        and checkpoint.get("transport_execution_event_digest") == transport.get("execution_event_digest")
        and _transport_execution_event_ready(transport, execution_event, run_id=run_id)
        and checkpoint.get("checkpoint_binding_digest")
        == _canonical_digest(
            {key: value for key, value in checkpoint.items() if key != "checkpoint_binding_digest"}
        )
    ):
        return []
    valid: list[dict[str, Any]] = []
    seen: set[int] = set()
    quarantined = _quarantined_task_ids(run_id)
    for row in checkpoint.get("successful_batches") or []:
        if not isinstance(row, Mapping):
            return []
        batch_index = _integer(row.get("batch_index"), default=-1)
        if batch_index < 0 or batch_index >= len(batches) or batch_index in seen:
            return []
        specification = {
            **dict(row),
            "acceptance_run_id": checkpoint.get("acceptance_run_id"),
            "symbols": batches[batch_index],
            "batch_symbol_hash": _canonical_digest(batches[batch_index]),
        }
        task = _read_task_no_init(SQLITE_META_PATH, str(row.get("worker_task_id") or ""))
        task_ready, _rows = _validate_worker_task(
            task,
            batch=specification,
            universe=universe,
            transport=None,
        )
        if (
            not task_ready
            or str(row.get("celery_task_id") or "") in quarantined
            or not _dispatch_chain_ready(row, task, run_id=run_id, transport=transport)
            or not callable(resume_proof_verifier)
            or resume_proof_verifier(row, task) is not True
        ):
            return []
        seen.add(batch_index)
        valid.append(dict(row))
    return sorted(valid, key=lambda row: _integer(row.get("batch_index")))


def _result_rows_from_batches(
    successes: list[dict[str, Any]],
    *,
    universe: Mapping[str, Any],
    transport: Mapping[str, Any],
    execution_event: Mapping[str, Any],
) -> list[dict[str, Any]]:
    run_ids = {
        str(batch.get("acceptance_run_id") or "")
        for batch in successes
        if str(batch.get("acceptance_run_id") or "")
    }
    if len(run_ids) != 1 or not _transport_execution_event_ready(
        transport,
        execution_event,
        run_id=next(iter(run_ids), ""),
    ):
        return []
    rows: list[dict[str, Any]] = []
    for batch in sorted(successes, key=lambda row: _integer(row.get("batch_index"))):
        task = _read_task_no_init(SQLITE_META_PATH, str(batch.get("worker_task_id") or ""))
        ready, task_rows = _validate_worker_task(
            task,
            batch=batch,
            universe=universe,
            transport=None,
        )
        if not ready or not _dispatch_chain_ready(
            batch,
            task,
            run_id=str(batch.get("acceptance_run_id") or ""),
            transport=transport,
        ):
            return []
        for row in task_rows:
            rows.append(
                {
                    **row,
                    "batch_index": _integer(batch.get("batch_index")),
                    "celery_task_id": str(batch.get("celery_task_id") or ""),
                    "worker_task_id": str(batch.get("worker_task_id") or ""),
                    "worker_hostname": str(batch.get("worker_hostname") or ""),
                    "worker_pid": _integer(batch.get("worker_pid")),
                    "worker_queue": str(batch.get("worker_queue") or ""),
                    "provider_scope_hash": universe.get("scope_hash"),
                    "universe_digest": universe.get("universe_digest"),
                }
            )
    symbols, duplicates, invalid = _normalize_symbols([row.get("ts_code") for row in rows])
    if symbols != universe.get("symbols") or duplicates or invalid:
        return []
    ranked = sorted(rows, key=lambda row: (-_integer(row.get("score")), str(row.get("ts_code"))))
    for rank, row in enumerate(ranked, start=1):
        row["full_market_rank"] = rank
    return ranked


def _pointer_snapshot(root: Path, name: str, pointer: str) -> dict[str, Any]:
    return _read_json(root / name / f"{pointer}.json")


def _restore_pointer(
    root: Path,
    name: str,
    previous: Mapping[str, Any],
    *,
    pointer: str = "current",
) -> bool:
    path = root / name / f"{pointer}.json"
    try:
        if previous:
            _atomic_write_json(path, previous)
        else:
            path.unlink(missing_ok=True)
            _fsync_directory(path.parent)
        return True
    except Exception:
        return False


def _restore_packet(packet_key: str, previous: Mapping[str, Any]) -> bool:
    try:
        if previous:
            SQLiteMetaStore(SQLITE_META_PATH).write_packet(packet_key, dict(previous))
        else:
            connection = sqlite3.connect(SQLITE_META_PATH)
            try:
                connection.execute("DELETE FROM packets WHERE packet_key = ?", (packet_key,))
                connection.commit()
            finally:
                connection.close()
        return True
    except Exception:
        return False


def _write_promotion_journal(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    payload["updated_at"] = _now_iso()
    _atomic_write_json(_promotion_journal_path(), payload)
    return payload


def _promotion_snapshot_targets() -> dict[str, dict[str, str]]:
    dataset_root = (PARQUET_ROOT / RESULT_DATASET).resolve()
    database_path = str(SQLITE_META_PATH.resolve())
    return {
        "current_packet": {
            "kind": "sqlite_packet",
            "database_path": database_path,
            "packet_key": PACKET_KEY,
        },
        "last_good_packet": {
            "kind": "sqlite_packet",
            "database_path": database_path,
            "packet_key": LAST_GOOD_PACKET_KEY,
        },
        "current_pointer": {
            "kind": "json_pointer",
            "path": str((dataset_root / "current.json").resolve()),
        },
        "last_good_pointer": {
            "kind": "json_pointer",
            "path": str((dataset_root / "last_good.json").resolve()),
        },
    }


def _promotion_snapshot_entry(name: str, value: Mapping[str, Any]) -> dict[str, Any]:
    target = _promotion_snapshot_targets()[name]
    snapshot = dict(value)
    return {
        "target": target,
        "value": snapshot,
        "value_digest": _canonical_digest(snapshot),
    }


def _promotion_journal_ready(journal: Mapping[str, Any]) -> bool:
    run_id = str(journal.get("acceptance_run_id") or "")
    snapshots = journal.get("snapshots")
    targets = _promotion_snapshot_targets()
    if not (
        journal.get("schema_version") == PROMOTION_JOURNAL_SCHEMA_VERSION
        and journal.get("status")
        in {
            "prepared",
            "stage_written",
            "current_pointer_promoted",
            "pending_packet_written",
            "last_good_pointer_promoted",
            "completed",
            "rolled_back",
            "rollback_incomplete",
        }
        and run_id == _normalize_uuid4(run_id)
        and journal.get("contains_secret") is False
        and isinstance(snapshots, Mapping)
        and set(snapshots) == set(targets)
        and _HEX_64_RE.fullmatch(str(journal.get("journal_binding_digest") or ""))
    ):
        return False
    normalized_snapshots: dict[str, dict[str, Any]] = {}
    for name, expected_target in targets.items():
        entry = snapshots.get(name)
        if not (
            isinstance(entry, Mapping)
            and set(entry) == {"target", "value", "value_digest"}
            and entry.get("target") == expected_target
            and isinstance(entry.get("value"), Mapping)
            and _HEX_64_RE.fullmatch(str(entry.get("value_digest") or ""))
            and entry.get("value_digest") == _canonical_digest(entry.get("value"))
        ):
            return False
        normalized_snapshots[name] = dict(entry)
    expected_binding = _canonical_digest(
        {
            "schema_version": PROMOTION_JOURNAL_SCHEMA_VERSION,
            "acceptance_run_id": run_id,
            "snapshots": normalized_snapshots,
        }
    )
    return hmac.compare_digest(
        str(journal.get("journal_binding_digest") or ""),
        expected_binding,
    )


def _begin_promotion_journal(
    run_id: str,
    *,
    previous_current: Mapping[str, Any],
    previous_last_good: Mapping[str, Any],
    previous_pointer: Mapping[str, Any],
    previous_last_good_pointer: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_run_id = _normalize_uuid4(run_id)
    if not normalized_run_id or normalized_run_id != run_id:
        raise ValueError("promotion_journal_run_id_must_be_canonical_uuid4")
    snapshots = {
        "current_packet": _promotion_snapshot_entry("current_packet", previous_current),
        "last_good_packet": _promotion_snapshot_entry("last_good_packet", previous_last_good),
        "current_pointer": _promotion_snapshot_entry("current_pointer", previous_pointer),
        "last_good_pointer": _promotion_snapshot_entry(
            "last_good_pointer",
            previous_last_good_pointer,
        ),
    }
    journal = {
        "schema_version": PROMOTION_JOURNAL_SCHEMA_VERSION,
        "status": "prepared",
        "acceptance_run_id": run_id,
        "created_at": _now_iso(),
        "snapshots": snapshots,
        "rollback_results": {},
        "contains_secret": False,
    }
    journal["journal_binding_digest"] = _canonical_digest(
        {
            "schema_version": PROMOTION_JOURNAL_SCHEMA_VERSION,
            "acceptance_run_id": run_id,
            "snapshots": snapshots,
        }
    )
    if not _promotion_journal_ready(journal):
        raise ValueError("promotion_journal_self_validation_failed")
    return _write_promotion_journal(journal)


def _update_promotion_journal(journal: Mapping[str, Any], status: str, **fields: Any) -> dict[str, Any]:
    return _write_promotion_journal({**dict(journal), "status": status, **fields})


def _rollback_from_promotion_journal(journal: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    if not _promotion_journal_ready(journal):
        return {
            "complete": False,
            "pointer_complete": False,
            "packet_complete": False,
            "results": {},
            "journal": dict(journal),
            "invalid": True,
        }
    snapshots = journal.get("snapshots") if isinstance(journal.get("snapshots"), Mapping) else {}
    operations = (
        (
            "current_pointer",
            lambda: _restore_pointer(
                PARQUET_ROOT,
                RESULT_DATASET,
                snapshots.get("current_pointer", {}).get("value"),
            ),
        ),
        (
            "last_good_pointer",
            lambda: _restore_pointer(
                PARQUET_ROOT,
                RESULT_DATASET,
                snapshots.get("last_good_pointer", {}).get("value"),
                pointer="last_good",
            ),
        ),
        (
            "current_packet",
            lambda: _restore_packet(
                PACKET_KEY,
                snapshots.get("current_packet", {}).get("value"),
            ),
        ),
        (
            "last_good_packet",
            lambda: _restore_packet(
                LAST_GOOD_PACKET_KEY,
                snapshots.get("last_good_packet", {}).get("value"),
            ),
        ),
    )
    results: dict[str, bool] = {}
    for name, operation in operations:
        try:
            results[name] = operation() is True
        except Exception:
            results[name] = False
    complete = all(results.values())
    try:
        updated = _update_promotion_journal(
            journal,
            "rolled_back" if complete else "rollback_incomplete",
            rollback_reason=reason,
            rollback_results=results,
            recovery_required=not complete,
        )
    except Exception:
        updated = {**dict(journal), "status": "rollback_journal_write_failed", "rollback_results": results}
    return {
        "complete": complete,
        "pointer_complete": results.get("current_pointer") is True and results.get("last_good_pointer") is True,
        "packet_complete": results.get("current_packet") is True and results.get("last_good_packet") is True,
        "results": results,
        "journal": updated,
    }


def _recover_interrupted_promotion() -> dict[str, Any]:
    path = _promotion_journal_path()
    if not path.exists():
        return {"ready": True, "status": "promotion_journal_missing_no_recovery_needed"}
    journal = _read_json(path)
    if not _promotion_journal_ready(journal):
        return {"ready": False, "status": "promotion_journal_invalid"}
    if journal.get("status") in {"completed", "rolled_back"}:
        return {"ready": True, "status": "promotion_journal_terminal"}
    rollback = _rollback_from_promotion_journal(journal, reason="restart_recovery")
    return {
        "ready": rollback["complete"] is True,
        "status": "promotion_recovery_completed" if rollback["complete"] else "promotion_recovery_incomplete",
        "rollback_results": rollback["results"],
    }


def _promote_packet_pair_atomic(packet: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    SQLiteMetaStore(SQLITE_META_PATH)
    connection = sqlite3.connect(SQLITE_META_PATH, timeout=5)
    payload = json.dumps(dict(packet), ensure_ascii=False, sort_keys=True, default=str)
    now = _now_iso()
    try:
        connection.execute("BEGIN IMMEDIATE")
        for key in (PACKET_KEY, LAST_GOOD_PACKET_KEY):
            connection.execute(
                "INSERT INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(packet_key) DO UPDATE SET "
                "payload_json=excluded.payload_json, updated_at=excluded.updated_at",
                (key, payload, now),
            )
        rows = dict(
            connection.execute(
                "SELECT packet_key, payload_json FROM packets WHERE packet_key IN (?, ?)",
                (PACKET_KEY, LAST_GOOD_PACKET_KEY),
            ).fetchall()
        )
        current = json.loads(rows.get(PACKET_KEY, "{}"))
        last_good = json.loads(rows.get(LAST_GOOD_PACKET_KEY, "{}"))
        if current != dict(packet) or last_good != dict(packet):
            raise RuntimeError("worker_packet_pair_readback_mismatch")
        connection.commit()
        return current, last_good
    except Exception:
        connection.rollback()
        return {}, {}
    finally:
        connection.close()


def _blocked_attempt(status: str, *, run_id: str = "", **fields: Any) -> dict[str, Any]:
    call_ledger = fields.pop("call_ledger", [])
    safe_ledger = [dict(row) for row in call_ledger if isinstance(row, Mapping)]
    if not _ledger_sanitized(safe_ledger):
        safe_ledger = []
    packet = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "acceptance_run_id": run_id,
        "production_worker_complete": False,
        "full_market_worker_runtime": False,
        "celery_redis_runtime": False,
        **_candidate_radar_replacement_claim_fields(
            authoritative_cache_validated=False,
            external_lineage_validated=False,
        ),
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": safe_ledger,
        **fields,
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(ATTEMPT_PACKET_KEY, packet)
    except Exception:
        packet["attempt_write_failed"] = True
    return packet


def _promote_candidate_results(
    *,
    run_id: str,
    universe: Mapping[str, Any],
    transport: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    result_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Module callers may review inputs but cannot promote production truth."""

    del universe, transport, checkpoint, result_rows
    return _blocked_attempt(
        "full_market_worker_module_level_promotion_disabled",
        run_id=run_id,
        module_level_promotion_disabled=True,
    )


def _promote_official_candidate_results(
    *,
    run_id: str,
    universe: Mapping[str, Any],
    transport: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    result_rows: list[dict[str, Any]],
    capability: Any,
) -> dict[str, Any]:
    import pandas as pd

    state = _official_orchestrator_state(capability, run_id)
    expected_task_ids = {
        str(row.get("celery_task_id") or "")
        for row in checkpoint.get("successful_batches") or []
        if isinstance(row, Mapping) and str(row.get("celery_task_id") or "")
    }
    if not (
        state
        and state.get("transport_event_persisted") is True
        and expected_task_ids
        and set(state.get("verified_worker_task_ids") or set()) == expected_task_ids
    ):
        return _blocked_attempt(
            "full_market_worker_official_challenge_proof_incomplete",
            run_id=run_id,
        )
    store = SQLiteMetaStore(SQLITE_META_PATH)
    previous_current = _read_packet_no_init(SQLITE_META_PATH, PACKET_KEY)
    previous_last_good = _read_packet_no_init(SQLITE_META_PATH, LAST_GOOD_PACKET_KEY)
    previous_pointer = _pointer_snapshot(PARQUET_ROOT, RESULT_DATASET, "current")
    previous_last_good_pointer = _pointer_snapshot(PARQUET_ROOT, RESULT_DATASET, "last_good")
    try:
        journal = _begin_promotion_journal(
            run_id,
            previous_current=previous_current,
            previous_last_good=previous_last_good,
            previous_pointer=previous_pointer,
            previous_last_good_pointer=previous_last_good_pointer,
        )
    except Exception:
        return _blocked_attempt("full_market_worker_promotion_journal_prepare_failed", run_id=run_id)

    def _rollback_response(status: str) -> dict[str, Any]:
        rollback = _rollback_from_promotion_journal(journal, reason=status)
        return _blocked_attempt(
            status,
            run_id=run_id,
            pointer_rollback_verified=rollback["pointer_complete"],
            packet_rollback_verified=rollback["packet_complete"],
            rollback_results=rollback["results"],
            recovery_required=not rollback["complete"],
        )

    output_hash = _canonical_digest(result_rows)
    dispatch_chain_digest = _canonical_digest(
        [row.get("dispatch_chain_digest") for row in checkpoint.get("successful_batches") or []]
    )
    task_ids = [str(row.get("worker_task_id") or "") for row in checkpoint.get("successful_batches") or []]
    celery_ids = [str(row.get("celery_task_id") or "") for row in checkpoint.get("successful_batches") or []]
    stage = {
        "schema_version": STAGE_SCHEMA_VERSION,
        "status": "full_market_worker_stage_ready_production_pending",
        "acceptance_run_id": run_id,
        "provider_scope_hash": universe.get("scope_hash"),
        "provider_version_digest": universe.get("version_digest"),
        "universe_digest": universe.get("universe_digest"),
        **_industry_binding(universe),
        "industry_input_digest": _industry_input_digest(universe),
        "universe_count": universe.get("universe_count"),
        "validated_trade_date": universe.get("validated_trade_date"),
        "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
        "result_output_hash": output_hash,
        "dispatch_chain_digest": dispatch_chain_digest,
        "celery_task_ids": celery_ids,
        "worker_task_ids": task_ids,
        "checkpoint_key": _checkpoint_key(run_id),
        "transport_key": _transport_key(run_id),
        "production_worker_complete": False,
        "synthetic_fixture": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }
    stage["stage_binding_digest"] = _canonical_digest(stage)
    try:
        store.write_packet(_stage_key(run_id), stage)
        stage_readback = store.read_packet(_stage_key(run_id)) or {}
    except Exception:
        stage_readback = {}
    if stage_readback.get("stage_binding_digest") != stage.get("stage_binding_digest"):
        return _rollback_response("full_market_worker_stage_sqlite_readback_failed_rolled_back")
    try:
        journal = _update_promotion_journal(journal, "stage_written")
    except Exception:
        return _rollback_response("full_market_worker_stage_journal_update_failed_rolled_back")

    promotion = parquet_store.atomic_promote_versioned_dataset(
        pd.DataFrame(result_rows),
        root=PARQUET_ROOT,
        name=RESULT_DATASET,
        version_id=f"fmw-{run_id}",
        required_columns=[
            "ts_code",
            "score",
            "rough_score",
            "full_market_rank",
            "batch_index",
            "celery_task_id",
            "worker_task_id",
            "candidate_is_not_buy_instruction",
            "does_not_execute_trades",
        ],
        lineage={
            "acceptance_run_id": run_id,
            "provider_scope_hash": universe.get("scope_hash"),
            "provider_version_digest": universe.get("version_digest"),
            "universe_digest": universe.get("universe_digest"),
            **_industry_binding(universe),
            "industry_input_digest": _industry_input_digest(universe),
            "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
            "result_output_hash": output_hash,
            "dispatch_chain_digest": dispatch_chain_digest,
            "stage_binding_digest": stage.get("stage_binding_digest"),
            "synthetic_fixture": False,
            "contains_secret": False,
        },
    )
    if promotion.get("atomic_promoted") is not True:
        return _rollback_response("full_market_worker_parquet_stage_or_pointer_failed_rolled_back")
    try:
        journal = _update_promotion_journal(journal, "current_pointer_promoted")
    except Exception:
        return _rollback_response("full_market_worker_current_pointer_journal_update_failed_rolled_back")
    current_pointer_payload = _pointer_snapshot(PARQUET_ROOT, RESULT_DATASET, "current")
    if not previous_pointer and not previous_last_good_pointer:
        try:
            first_last_good = dict(current_pointer_payload)
            first_last_good["pointer_kind"] = "last_good"
            first_last_good["preserved_at"] = _now_iso()
            _atomic_write_json(PARQUET_ROOT / RESULT_DATASET / "last_good.json", first_last_good)
        except Exception:
            return _rollback_response("full_market_worker_first_last_good_pointer_failed_rolled_back")
    packet = {
        "schema_version": SCHEMA_VERSION,
        "status": "full_market_worker_production_complete",
        "acceptance_run_id": run_id,
        "provider_version_source": (
            "server.services.tushare_production_store."
            "validate_tushare_full_market_production_version"
        ),
        "provider_scope_hash": universe.get("scope_hash"),
        "provider_version_digest": universe.get("version_digest"),
        "universe_digest": universe.get("universe_digest"),
        **_industry_binding(universe),
        "industry_input_digest": _industry_input_digest(universe),
        "universe_count": universe.get("universe_count"),
        "minimum_universe_size": universe.get("minimum_universe_size"),
        "validated_trade_date": universe.get("validated_trade_date"),
        "feature_contract": FEATURE_CONTRACT,
        "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
        "checkpoint_key": _checkpoint_key(run_id),
        "transport_key": _transport_key(run_id),
        "stage_key": _stage_key(run_id),
        "stage_binding_digest": stage.get("stage_binding_digest"),
        "batch_count": checkpoint.get("batch_count"),
        "celery_task_ids": celery_ids,
        "worker_task_ids": task_ids,
        "result_dataset": RESULT_DATASET,
        "result_version_id": promotion.get("version_id"),
        "result_artifact_sha256": promotion.get("artifact_sha256"),
        "result_output_hash": output_hash,
        "dispatch_chain_digest": dispatch_chain_digest,
        "checkpoint_binding_digest": checkpoint.get("checkpoint_binding_digest"),
        "result_row_count": len(result_rows),
        "transport_attestation_digest": _canonical_digest(transport),
        "transport_execution_event_key": transport.get("execution_event_key"),
        "transport_execution_event_digest": transport.get("execution_event_digest"),
        "promotion_journal_binding_digest": journal.get("journal_binding_digest"),
        "direct_provenance_complete": True,
        "production_worker_complete": False,
        "full_market_worker_runtime": False,
        "celery_redis_runtime": False,
        "local_production_worker_complete": True,
        "local_full_market_worker_runtime": True,
        "local_celery_redis_runtime": True,
        **_candidate_radar_replacement_claim_fields(
            authoritative_cache_validated=False,
            external_lineage_validated=False,
        ),
        "synthetic_fixture": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            *[
                dict(row)
                for row in transport.get("call_ledger") or []
                if isinstance(row, Mapping)
            ],
            {
                "api": "celery_full_market_candidate_batches",
                "call_status": "success",
                "batch_count": checkpoint.get("batch_count"),
                "row_count": len(result_rows),
                "external_calls_triggered": True,
                "redis_called": True,
                "celery_called": True,
                "provider_called": False,
                "does_not_execute_trades": True,
                "contains_secret": False,
            },
        ],
    }
    final_packet = dict(packet)
    final_packet["production_binding_digest"] = _canonical_digest(final_packet)
    pending_packet = {
        **final_packet,
        "status": "full_market_worker_promotion_pending_direct_validation",
        "production_worker_complete": False,
        "full_market_worker_runtime": False,
        "celery_redis_runtime": False,
        "candidate_radar_production_replacement": False,
    }
    pending_packet["production_binding_digest"] = _canonical_digest(
        {key: value for key, value in pending_packet.items() if key != "production_binding_digest"}
    )
    try:
        store.write_packet(PACKET_KEY, pending_packet)
        pending_readback = store.read_packet(PACKET_KEY) or {}
    except Exception:
        pending_readback = {}
    try:
        journal = _update_promotion_journal(journal, "pending_packet_written")
    except Exception:
        return _rollback_response("full_market_worker_pending_packet_journal_update_failed_rolled_back")
    candidate_fact = _validate_full_market_worker_local_fact(
        EVIDENCE_ROOT,
        _candidate_packet=pending_packet,
    )
    if not (
        pending_readback.get("production_binding_digest") == pending_packet["production_binding_digest"]
        and candidate_fact.get("ready") is True
    ):
        return _rollback_response("full_market_worker_direct_candidate_validation_failed_rolled_back")
    latest_last_good_pointer = dict(current_pointer_payload)
    latest_last_good_pointer["pointer_kind"] = "last_good"
    latest_last_good_pointer["preserved_at"] = _now_iso()
    try:
        _atomic_write_json(
            PARQUET_ROOT / RESULT_DATASET / "last_good.json",
            latest_last_good_pointer,
        )
        last_good_pointer_readback = _pointer_snapshot(
            PARQUET_ROOT,
            RESULT_DATASET,
            "last_good",
        )
    except Exception:
        last_good_pointer_readback = {}
    if not (
        last_good_pointer_readback.get("version_id") == current_pointer_payload.get("version_id")
        and last_good_pointer_readback.get("artifact_sha256")
        == current_pointer_payload.get("artifact_sha256")
    ):
        return _rollback_response("full_market_worker_last_good_pointer_promotion_failed_rolled_back")
    try:
        journal = _update_promotion_journal(journal, "last_good_pointer_promoted")
    except Exception:
        return _rollback_response("full_market_worker_last_good_journal_update_failed_rolled_back")
    persisted, persisted_good = _promote_packet_pair_atomic(final_packet)
    try:
        journal = _update_promotion_journal(journal, "completed")
    except Exception:
        return _rollback_response("full_market_worker_promotion_journal_finalize_failed_rolled_back")
    fact = _validate_full_market_worker_local_fact(EVIDENCE_ROOT)
    if not (
        persisted.get("production_binding_digest") == final_packet["production_binding_digest"]
        and persisted_good.get("production_binding_digest") == final_packet["production_binding_digest"]
        and fact.get("ready") is True
    ):
        return _rollback_response("full_market_worker_final_readback_failed_rolled_back")
    return dict(persisted)


def _ledger_sanitized(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered != "contains_secret" and any(marker in lowered for marker in _SENSITIVE_MARKERS):
                return False
            if not _ledger_sanitized(item):
                return False
    elif isinstance(value, list):
        return all(_ledger_sanitized(item) for item in value)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in _SENSITIVE_MARKERS):
            return False
    return True


def _candidate_cache_replacement_ready(
    cache_packet: Mapping[str, Any],
    worker_packet: Mapping[str, Any],
    cache_write_task: Mapping[str, Any],
    *,
    evidence_root: Path | None = None,
) -> bool:
    """Validate that the authoritative Radar cache consumed this exact worker output.

    The full-market worker's Parquet dataset is an upstream candidate artifact.  It
    is not the cache served by ``GET /api/candidate-radar/cache``.  A replacement
    claim therefore needs a separately persisted binding in that authoritative
    cache; a boolean copied into the worker packet cannot close LTG-13.
    """

    binding = cache_packet.get("full_market_worker_replacement")
    binding_map = dict(binding) if isinstance(binding, Mapping) else {}
    task_map = dict(cache_write_task) if isinstance(cache_write_task, Mapping) else {}
    candidate_rows = [
        dict(row)
        for row in cache_packet.get("candidate_rows") or []
        if isinstance(row, Mapping)
    ]
    candidate_symbols, duplicate_count, invalid_count = _normalize_symbols(
        [row.get("ts_code") for row in candidate_rows]
    )
    expected_binding_digest = (
        _canonical_digest(
            {
                key: value
                for key, value in binding_map.items()
                if key != "binding_digest"
            }
        )
        if binding_map
        else ""
    )
    expected_task_digest = (
        _canonical_digest(
            {
                key: value
                for key, value in task_map.items()
                if key != "task_binding_digest"
            }
        )
        if task_map
        else ""
    )
    structural_ready = bool(
        cache_packet.get("packet_key") == CANDIDATE_CACHE_PACKET_KEY
        and cache_packet.get("schema_version") == CANDIDATE_CACHE_SCHEMA_VERSION
        and cache_packet.get("status") == "candidate_radar_full_market_replacement_ready"
        and cache_packet.get("cache_only") is True
        and cache_packet.get("global_candidate_cache_overwritten") is True
        and cache_packet.get("candidate_is_not_buy_instruction") is True
        and cache_packet.get("does_not_execute_trades") is True
        and cache_packet.get("does_not_modify_strategy_action") is True
        and cache_packet.get("contains_secret") is False
        and candidate_rows
        and not duplicate_count
        and not invalid_count
        and len(candidate_symbols) == len(candidate_rows)
        and binding_map.get("schema_version")
        == CANDIDATE_CACHE_REPLACEMENT_SCHEMA_VERSION
        and binding_map.get("status") == "authoritative_candidate_cache_replaced"
        and binding_map.get("global_candidate_cache_overwritten") is True
        and _normalize_uuid4(binding_map.get("cache_write_task_id"))
        == binding_map.get("cache_write_task_id")
        and binding_map.get("acceptance_run_id")
        == worker_packet.get("acceptance_run_id")
        and binding_map.get("source_result_dataset") == RESULT_DATASET
        and binding_map.get("source_result_version_id")
        == worker_packet.get("result_version_id")
        and binding_map.get("source_result_artifact_sha256")
        == worker_packet.get("result_artifact_sha256")
        and binding_map.get("source_result_output_hash")
        == worker_packet.get("result_output_hash")
        and binding_map.get("provider_version_digest")
        == worker_packet.get("provider_version_digest")
        and binding_map.get("universe_digest") == worker_packet.get("universe_digest")
        and _integer(binding_map.get("candidate_row_count")) == len(candidate_rows)
        and binding_map.get("candidate_rows_digest") == _canonical_digest(candidate_rows)
        and all(
            _HEX_64_RE.fullmatch(str(binding_map.get(key) or ""))
            for key in (
                "deep_scan_execution_evidence_digest",
                "browser_visual_evidence_digest",
                "browser_performance_evidence_digest",
                "legacy_retirement_evidence_digest",
            )
        )
        and binding_map.get("binding_digest") == expected_binding_digest
        and binding_map.get("contains_secret") is False
        and binding_map.get("does_not_execute_trades") is True
        and task_map.get("schema_version")
        == "candidate_radar_full_market_cache_write_task.v1"
        and task_map.get("task_id") == binding_map.get("cache_write_task_id")
        and task_map.get("task_type") == "publish_candidate_radar_full_market_cache"
        and task_map.get("status") == "success"
        and task_map.get("output_packet_key") == CANDIDATE_CACHE_PACKET_KEY
        and task_map.get("acceptance_run_id") == worker_packet.get("acceptance_run_id")
        and task_map.get("source_result_version_id")
        == worker_packet.get("result_version_id")
        and task_map.get("source_result_output_hash")
        == worker_packet.get("result_output_hash")
        and task_map.get("candidate_rows_digest") == _canonical_digest(candidate_rows)
        and all(
            task_map.get(key) == binding_map.get(key)
            for key in (
                "deep_scan_execution_evidence_digest",
                "browser_visual_evidence_digest",
                "browser_performance_evidence_digest",
                "legacy_retirement_evidence_digest",
            )
        )
        and task_map.get("global_candidate_cache_overwritten") is True
        and task_map.get("task_binding_digest") == expected_task_digest
        and task_map.get("external_calls_triggered") is False
        and task_map.get("does_not_execute_trades") is True
        and task_map.get("contains_secret") is False
    )
    if not structural_ready or evidence_root is None:
        return False
    cache_packet_digest = _canonical_digest(cache_packet)
    cache_write_task_digest = _canonical_digest(task_map)
    worker_packet_digest = _canonical_digest(worker_packet)
    output_binding_digest = _canonical_digest(
        {
            "event_kind": RADAR_LINEAGE_EVENT_KIND,
            "acceptance_run_id": worker_packet.get("acceptance_run_id"),
            "source_result_dataset": RESULT_DATASET,
            "source_result_version_id": worker_packet.get("result_version_id"),
            "source_result_artifact_sha256": worker_packet.get("result_artifact_sha256"),
            "source_result_output_hash": worker_packet.get("result_output_hash"),
            "provider_version_digest": worker_packet.get("provider_version_digest"),
            "universe_digest": worker_packet.get("universe_digest"),
        }
    )
    event = _matching_production_lineage_event(
        evidence_root,
        event_kind=RADAR_LINEAGE_EVENT_KIND,
        run_id=str(worker_packet.get("acceptance_run_id") or ""),
        worker_packet_digest=worker_packet_digest,
        output_binding_digest=output_binding_digest,
    )
    return bool(
        event
        and event.get("candidate_cache_packet_digest") == cache_packet_digest
        and event.get("candidate_cache_write_task_digest") == cache_write_task_digest
        and event.get("deep_scan_execution_evidence_digest")
        == binding_map.get("deep_scan_execution_evidence_digest")
        and event.get("browser_visual_evidence_digest")
        == binding_map.get("browser_visual_evidence_digest")
        and event.get("browser_performance_evidence_digest")
        == binding_map.get("browser_performance_evidence_digest")
        and event.get("legacy_retirement_evidence_digest")
        == binding_map.get("legacy_retirement_evidence_digest")
        and event.get("global_candidate_cache_overwritten") is True
        and event.get("deep_scan_worker_execution_verified") is True
        and event.get("browser_visual_qa_verified") is True
        and event.get("browser_performance_verified") is True
        and event.get("legacy_fallback_retired") is True
    )


def _finite_number(value: Any) -> bool:
    return bool(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _pearson_correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right)
    )
    left_scale = math.sqrt(sum((value - left_mean) ** 2 for value in left))
    right_scale = math.sqrt(sum((value - right_mean) ** 2 for value in right))
    if left_scale <= 0 or right_scale <= 0:
        return None
    return numerator / (left_scale * right_scale)


def _factor_metric_validation_audit(
    result_rows: list[dict[str, Any]],
    *,
    universe_digest: str,
    result_output_hash: str,
) -> dict[str, Any]:
    required_metrics = tuple(FACTOR_OUTPUT_CONTRACT["required_metrics"])
    numeric_complete = bool(
        result_rows
        and all(
            all(_finite_number(row.get(metric)) for metric in required_metrics)
            for row in result_rows
        )
    )
    ranks = [row.get("cross_sectional_rank") for row in result_rows]
    rank_coverage_ready = bool(
        numeric_complete
        and all(float(value).is_integer() for value in ranks)
        and sorted(int(value) for value in ranks) == list(range(1, len(result_rows) + 1))
    )
    zscores = [float(row.get("cross_sectional_zscore")) for row in result_rows] if numeric_complete else []
    zscore_mean = sum(zscores) / len(zscores) if zscores else math.inf
    zscore_range_ready = bool(
        len(zscores) >= 3
        and max(abs(value) for value in zscores) <= 20.0
        and abs(zscore_mean) <= 0.05
        and max(zscores) > min(zscores)
    )
    industry_codes = [str(row.get("industry_code") or "").strip() for row in result_rows]
    market_caps = [row.get("market_cap") for row in result_rows]
    neutralization_input_coverage = bool(
        result_rows
        and all(industry_codes)
        and len(set(industry_codes)) >= 2
        and all(_finite_number(value) and float(value) > 0 for value in market_caps)
    )
    industry_means: dict[str, float] = {}
    if numeric_complete and neutralization_input_coverage:
        for code in sorted(set(industry_codes)):
            values = [
                float(row.get("industry_neutral_score"))
                for row, row_code in zip(result_rows, industry_codes)
                if row_code == code
            ]
            industry_means[code] = sum(values) / len(values)
    industry_neutralization_ready = bool(
        industry_means
        and all(abs(value) <= 0.10 for value in industry_means.values())
    )
    size_correlation = None
    if numeric_complete and neutralization_input_coverage:
        size_correlation = _pearson_correlation(
            [math.log(float(value)) for value in market_caps],
            [float(row.get("size_neutral_score")) for row in result_rows],
        )
    size_neutralization_ready = bool(
        size_correlation is not None and abs(size_correlation) <= 0.10
    )
    combined_score_range_ready = bool(
        numeric_complete
        and all(abs(float(row.get("combined_factor_score"))) <= 50.0 for row in result_rows)
    )
    checks = {
        "metric_numeric_finite_complete": numeric_complete,
        "rank_exact_full_universe_coverage": rank_coverage_ready,
        "zscore_cross_sectional_range_and_center": zscore_range_ready,
        "neutralization_input_coverage": neutralization_input_coverage,
        "industry_neutralization_group_means": industry_neutralization_ready,
        "size_neutralization_log_cap_correlation": size_neutralization_ready,
        "combined_factor_score_range": combined_score_range_ready,
    }
    audit = {
        "schema_version": "factor_full_market_metric_validation_audit.v1",
        "row_count": len(result_rows),
        "required_metrics": list(required_metrics),
        "universe_digest": universe_digest,
        "result_output_hash": result_output_hash,
        "checks": checks,
        "zscore_mean": zscore_mean if math.isfinite(zscore_mean) else None,
        "industry_group_count": len(industry_means),
        "maximum_absolute_industry_mean": (
            max(abs(value) for value in industry_means.values())
            if industry_means
            else None
        ),
        "size_log_cap_correlation": size_correlation,
        "ready": all(checks.values()),
        "blockers": [key for key, passed in checks.items() if not passed],
        "contains_secret": False,
        "does_not_execute_trades": True,
    }
    audit["audit_digest"] = _canonical_digest(audit)
    return audit


def _factor_output_binding_digest(packet: Mapping[str, Any]) -> str:
    return _canonical_digest(
        {
            "event_kind": FACTOR_LINEAGE_EVENT_KIND,
            "acceptance_run_id": packet.get("acceptance_run_id"),
            "result_dataset": FACTOR_RESULT_DATASET,
            "result_version_id": packet.get("result_version_id"),
            "result_artifact_sha256": packet.get("result_artifact_sha256"),
            "result_output_hash": packet.get("result_output_hash"),
            "provider_version_digest": packet.get("provider_version_digest"),
            "universe_digest": packet.get("universe_digest"),
            "validated_trade_date": packet.get("validated_trade_date"),
            "factor_output_contract_digest": packet.get("factor_output_contract_digest"),
            "neutralization_audit_digest": packet.get("neutralization_audit_digest"),
            **_industry_binding(packet),
            "industry_input_digest": packet.get("industry_input_digest"),
            "factor_batch_input_digest": packet.get("factor_batch_input_digest"),
        }
    )


def _validate_factor_full_market_local_fact(evidence_root: Path) -> dict[str, Any]:
    """Validate the independent LTG-04 Factor worker output, fail closed.

    Candidate Radar scoring rows intentionally cannot satisfy this contract.  A
    future shared map/reduce run may reuse provider reads and transport, but it
    must persist a separate Factor dataset with rank/zscore, industry and size
    neutralization, and factor-combination outputs.
    """

    db_path = evidence_root / "meta.sqlite"
    packet = _read_packet_no_init(db_path, FACTOR_PACKET_KEY)
    last_good = _read_packet_no_init(db_path, FACTOR_LAST_GOOD_PACKET_KEY)
    minimum = _bounded_integer(
        packet.get("minimum_universe_size"),
        default=DEFAULT_MINIMUM_UNIVERSE_SIZE,
        minimum=DEFAULT_MINIMUM_UNIVERSE_SIZE,
        maximum=MAXIMUM_MINIMUM_UNIVERSE_SIZE,
    )
    universe = _authoritative_provider_universe(
        evidence_root,
        minimum_universe_size=minimum,
        include_frames=False,
        require_industry_membership=True,
    )
    packet_binding = (
        _canonical_digest(
            {
                key: value
                for key, value in packet.items()
                if key != "production_binding_digest"
            }
        )
        if packet
        else ""
    )
    run_id = str(packet.get("acceptance_run_id") or "")
    expected_factor_batch_input_digest = _canonical_digest(
        {
            "provider_scope_hash": universe.get("scope_hash"),
            "provider_version_digest": universe.get("version_digest"),
            "universe_digest": universe.get("universe_digest"),
            "validated_trade_date": universe.get("validated_trade_date"),
            "symbols": universe.get("symbols"),
            "industry_binding": _industry_binding(universe),
            "industry_input_digest": _industry_input_digest(universe),
        }
    )
    packet_core_ready = bool(
        packet
        and packet == last_good
        and packet.get("schema_version") == FACTOR_SCHEMA_VERSION
        and packet.get("status") == "factor_full_market_worker_production_complete"
        and packet.get("output_kind") == "factor_full_market_cross_sectional_research"
        and packet.get("factor_output_contract") == FACTOR_OUTPUT_CONTRACT
        and packet.get("factor_output_contract_digest") == FACTOR_OUTPUT_CONTRACT_DIGEST
        and packet.get("production_binding_digest") == packet_binding
        and packet.get("full_market_factor_research") is True
        and packet.get("full_market_worker_runtime") is True
        and packet.get("candidate_radar_production_replacement") is False
        and _normalize_uuid4(run_id) == run_id
        and packet.get("provider_scope_hash") == universe.get("scope_hash")
        and packet.get("provider_version_digest") == universe.get("version_digest")
        and packet.get("universe_digest") == universe.get("universe_digest")
        and _integer(packet.get("universe_count")) == universe.get("universe_count")
        and packet.get("validated_trade_date") == universe.get("validated_trade_date")
        and _industry_binding_ready(universe)
        and _industry_binding(packet) == _industry_binding(universe)
        and packet.get("industry_input_digest") == _industry_input_digest(universe)
        and packet.get("factor_batch_input_digest")
        == expected_factor_batch_input_digest
        and packet.get("synthetic_fixture") is False
        and packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("contains_secret") is False
    )

    pointer = parquet_store.versioned_dataset_pointer(
        root=evidence_root / "parquet",
        name=FACTOR_RESULT_DATASET,
        pointer="current",
    )
    last_good_pointer = parquet_store.versioned_dataset_pointer(
        root=evidence_root / "parquet",
        name=FACTOR_RESULT_DATASET,
        pointer="last_good",
    )
    result_path = Path(str(pointer.get("artifact_path") or ""))
    result_rows: list[dict[str, Any]] = []
    if result_path.is_file():
        try:
            import pandas as pd

            result_rows = pd.read_parquet(result_path).to_dict(orient="records")
        except Exception:
            result_rows = []
    result_symbols, duplicate_count, invalid_count = _normalize_symbols(
        [row.get("ts_code") for row in result_rows]
    )
    result_output_hash = _canonical_digest(result_rows) if result_rows else ""
    metric_audit = _factor_metric_validation_audit(
        result_rows,
        universe_digest=str(universe.get("universe_digest") or ""),
        result_output_hash=result_output_hash,
    )
    packet_metric_audit = (
        dict(packet.get("metric_validation_audit"))
        if isinstance(packet.get("metric_validation_audit"), Mapping)
        else {}
    )
    metric_audit_ready = bool(
        metric_audit.get("ready") is True
        and packet_metric_audit == metric_audit
        and packet.get("neutralization_audit_digest") == metric_audit.get("audit_digest")
    )
    result_ready = bool(
        pointer.get("status") == "ready"
        and pointer.get("version_id") == packet.get("result_version_id")
        and pointer.get("artifact_sha256_matches") is True
        and pointer.get("artifact_sha256") == packet.get("result_artifact_sha256")
        and last_good_pointer.get("status") == "ready"
        and last_good_pointer.get("version_id") == pointer.get("version_id")
        and last_good_pointer.get("artifact_sha256") == pointer.get("artifact_sha256")
        and result_rows
        and not duplicate_count
        and not invalid_count
        and result_symbols == universe.get("symbols")
        and len(result_rows) == universe.get("universe_count")
        and result_output_hash == packet.get("result_output_hash")
        and metric_audit_ready
        and all(row.get("does_not_execute_trades") is True for row in result_rows)
        and isinstance(pointer.get("lineage"), Mapping)
        and pointer.get("lineage", {}).get("factor_output_contract_digest")
        == FACTOR_OUTPUT_CONTRACT_DIGEST
        and pointer.get("lineage", {}).get("universe_digest")
        == universe.get("universe_digest")
        and pointer.get("lineage", {}).get("provider_version_digest")
        == universe.get("version_digest")
        and pointer.get("lineage", {}).get("validated_trade_date")
        == universe.get("validated_trade_date")
        and _industry_binding(pointer.get("lineage", {}))
        == _industry_binding(universe)
        and pointer.get("lineage", {}).get("industry_input_digest")
        == _industry_input_digest(universe)
        and pointer.get("lineage", {}).get("factor_batch_input_digest")
        == expected_factor_batch_input_digest
        and pointer.get("lineage", {}).get("neutralization_audit_digest")
        == metric_audit.get("audit_digest")
    )
    output_binding_digest = _factor_output_binding_digest(packet)
    worker_packet_digest = _canonical_digest(packet)
    lineage_event = _matching_production_lineage_event(
        evidence_root,
        event_kind=FACTOR_LINEAGE_EVENT_KIND,
        run_id=run_id,
        worker_packet_digest=worker_packet_digest,
        output_binding_digest=output_binding_digest,
    )
    trusted_lineage_ready = bool(
        lineage_event
        and lineage_event.get("factor_output_contract_digest")
        == FACTOR_OUTPUT_CONTRACT_DIGEST
        and lineage_event.get("neutralization_audit_digest")
        == metric_audit.get("audit_digest")
        and not lineage_event.get("candidate_cache_packet_digest")
        and not lineage_event.get("candidate_cache_write_task_digest")
        and not lineage_event.get("deep_scan_execution_evidence_digest")
        and not lineage_event.get("browser_visual_evidence_digest")
        and not lineage_event.get("browser_performance_evidence_digest")
        and not lineage_event.get("legacy_retirement_evidence_digest")
        and lineage_event.get("global_candidate_cache_overwritten") is False
        and lineage_event.get("deep_scan_worker_execution_verified") is False
        and lineage_event.get("browser_visual_qa_verified") is False
        and lineage_event.get("browser_performance_verified") is False
        and lineage_event.get("legacy_fallback_retired") is False
    )
    checks = {
        "upstream_provider_current_last_good_and_artifacts": universe.get("ready") is True,
        "factor_worker_packet_direct_binding": packet_core_ready and metric_audit_ready,
        PRODUCTION_LINEAGE_EXTERNAL_RUNNER_BLOCKER: trusted_lineage_ready,
        "factor_full_market_rank_zscore_neutralized_output": result_ready,
    }
    blockers = [key for key, passed in checks.items() if not passed]
    ready = not blockers
    return {
        "ready": ready,
        "status": (
            "factor_full_market_research_fact_verified"
            if ready
            else "factor_full_market_research_fact_blocked"
        ),
        "full_market_factor_research": ready,
        "output_kind": "factor_full_market_cross_sectional_research",
        "candidate_radar_output_accepted_as_factor": False,
        "metric_validation_audit": metric_audit,
        "trusted_lineage_event_observed": bool(lineage_event),
        "blockers": blockers,
        "provider_blockers": universe.get("blockers", []),
        "read_only": True,
        "writes_storage": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }


def _validate_full_market_worker_local_fact(
    evidence_root: Path,
    *,
    _candidate_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    db_path = evidence_root / "meta.sqlite"
    candidate_mode = isinstance(_candidate_packet, Mapping)
    packet = dict(_candidate_packet) if candidate_mode else _read_packet_no_init(db_path, PACKET_KEY)
    last_good = _read_packet_no_init(db_path, LAST_GOOD_PACKET_KEY)
    minimum = _bounded_integer(
        packet.get("minimum_universe_size"),
        default=DEFAULT_MINIMUM_UNIVERSE_SIZE,
        minimum=DEFAULT_MINIMUM_UNIVERSE_SIZE,
        maximum=MAXIMUM_MINIMUM_UNIVERSE_SIZE,
    )
    universe = _authoritative_provider_universe(
        evidence_root,
        minimum_universe_size=minimum,
        include_frames=True,
        require_industry_membership=True,
    )
    run_id = str(packet.get("acceptance_run_id") or "")
    production_binding = _canonical_digest(
        {key: value for key, value in packet.items() if key != "production_binding_digest"}
    ) if packet else ""
    packet_call_ledger = [
        dict(item)
        for item in packet.get("call_ledger") or []
        if isinstance(item, Mapping)
    ]
    packet_call_apis = {str(item.get("api") or "") for item in packet_call_ledger}
    packet_status_ready = bool(
        packet.get("status") == "full_market_worker_promotion_pending_direct_validation"
        and packet.get("production_worker_complete") is False
        and packet.get("full_market_worker_runtime") is False
        and packet.get("celery_redis_runtime") is False
        and packet.get("local_production_worker_complete") is True
        and packet.get("local_full_market_worker_runtime") is True
        and packet.get("local_celery_redis_runtime") is True
        and packet.get("candidate_radar_production_replacement") is False
    ) if candidate_mode else bool(
        packet.get("status") == "full_market_worker_production_complete"
        and packet.get("production_worker_complete") is False
        and packet.get("full_market_worker_runtime") is False
        and packet.get("celery_redis_runtime") is False
        and packet.get("local_production_worker_complete") is True
        and packet.get("local_full_market_worker_runtime") is True
        and packet.get("local_celery_redis_runtime") is True
        and packet.get("candidate_radar_production_replacement") is False
    )
    packets_ready = bool(
        packet
        and (candidate_mode or packet == last_good)
        and packet.get("schema_version") == SCHEMA_VERSION
        and packet_status_ready
        and packet.get("production_binding_digest") == production_binding
        and packet.get("synthetic_fixture") is False
        and packet.get("direct_provenance_complete") is True
        and packet.get("global_candidate_cache_overwritten") is False
        and packet.get("provider_scope_hash") == universe.get("scope_hash")
        and packet.get("provider_version_digest") == universe.get("version_digest")
        and packet.get("universe_digest") == universe.get("universe_digest")
        and _integer(packet.get("universe_count")) == universe.get("universe_count")
        and packet.get("validated_trade_date") == universe.get("validated_trade_date")
        and _industry_binding_ready(universe)
        and _industry_binding(packet) == _industry_binding(universe)
        and packet.get("industry_input_digest") == _industry_input_digest(universe)
        and packet.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and packet.get("feature_contract") == FEATURE_CONTRACT
        and packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("contains_secret") is False
        and packet_call_apis
        == {
            "redis_celery_direct_transport_probe",
            "celery_full_market_candidate_batches",
        }
        and all(item.get("contains_secret") is False for item in packet_call_ledger)
        and _ledger_sanitized(packet_call_ledger)
    )

    transport = _read_packet_no_init(db_path, str(packet.get("transport_key") or ""))
    transport_event = _read_packet_no_init(
        db_path,
        str(packet.get("transport_execution_event_key") or ""),
    )
    transport_ready = bool(
        _transport_execution_event_ready(transport, transport_event, run_id=run_id)
        and _canonical_digest(transport) == packet.get("transport_attestation_digest")
        and transport.get("execution_event_key") == packet.get("transport_execution_event_key")
        and transport.get("execution_event_digest") == packet.get("transport_execution_event_digest")
    )

    promotion_journal = _read_json(
        evidence_root / "parquet" / RESULT_DATASET / PROMOTION_JOURNAL_NAME
    )
    journal_binding = _canonical_digest(
        {
            "schema_version": PROMOTION_JOURNAL_SCHEMA_VERSION,
            "acceptance_run_id": run_id,
            "snapshots": promotion_journal.get("snapshots"),
        }
    )
    journal_ready = bool(
        _promotion_journal_ready(promotion_journal)
        and promotion_journal.get("schema_version") == PROMOTION_JOURNAL_SCHEMA_VERSION
        and promotion_journal.get("acceptance_run_id") == run_id
        and promotion_journal.get("journal_binding_digest")
        == packet.get("promotion_journal_binding_digest")
        and promotion_journal.get("journal_binding_digest") == journal_binding
        and (
            promotion_journal.get("status") == "completed"
            or (
                candidate_mode
                and promotion_journal.get("status")
                in {"pending_packet_written", "last_good_pointer_promoted"}
            )
        )
        and promotion_journal.get("contains_secret") is False
    )

    checkpoint = _read_packet_no_init(db_path, str(packet.get("checkpoint_key") or ""))
    coordinator = _read_task_no_init(db_path, f"full-market-coordinator-{run_id}")
    specs = [dict(row) for row in checkpoint.get("batch_specifications") or [] if isinstance(row, Mapping)]
    successes = [dict(row) for row in checkpoint.get("successful_batches") or [] if isinstance(row, Mapping)]
    batch_count = _integer(packet.get("batch_count"))
    checkpoint_ready = bool(
        checkpoint.get("schema_version") == CHECKPOINT_SCHEMA_VERSION
        and checkpoint.get("status") == "complete"
        and checkpoint.get("acceptance_run_id") == run_id
        and checkpoint.get("provider_scope_hash") == universe.get("scope_hash")
        and checkpoint.get("provider_version_digest") == universe.get("version_digest")
        and checkpoint.get("universe_digest") == universe.get("universe_digest")
        and _industry_binding(checkpoint) == _industry_binding(universe)
        and checkpoint.get("industry_input_digest") == _industry_input_digest(universe)
        and checkpoint.get("transport_attestation_digest") == _canonical_digest(transport)
        and checkpoint.get("checkpoint_binding_digest")
        == _canonical_digest(
            {key: value for key, value in checkpoint.items() if key != "checkpoint_binding_digest"}
        )
        and checkpoint.get("checkpoint_binding_digest") == packet.get("checkpoint_binding_digest")
        and checkpoint.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and checkpoint.get("synthetic_fixture") is False
        and checkpoint.get("global_candidate_cache_overwritten") is False
        and len(specs) == batch_count
        and len(successes) == batch_count
        and coordinator.get("task_type") == "run_candidate_radar_full_market_production_acceptance"
        and coordinator.get("status") == "success"
        and coordinator.get("current_step") == "full_market_worker_production_completed"
        and coordinator.get("synthetic_fixture") is False
    )

    tasks_ready = checkpoint_ready and batch_count > 0
    seen_symbols: list[str] = []
    celery_ids: list[str] = []
    worker_ids: list[str] = []
    expected_result_rows: list[dict[str, Any]] = []
    if tasks_ready:
        success_by_index = {_integer(row.get("batch_index"), default=-1): row for row in successes}
        if len(success_by_index) != batch_count:
            tasks_ready = False
        for index, spec in enumerate(specs):
            symbols, duplicates, invalid = _normalize_symbols(spec.get("symbols"))
            success = success_by_index.get(index, {})
            batch = {
                **success,
                "acceptance_run_id": run_id,
                "batch_index": index,
                "batch_count": batch_count,
                "symbols": symbols,
                "batch_symbol_hash": _canonical_digest(symbols),
                "batch_input_hash": _batch_input_hash(universe, symbols),
            }
            task = _read_task_no_init(db_path, str(success.get("worker_task_id") or ""))
            valid, task_rows = _validate_worker_task(
                task,
                batch=batch,
                universe=universe,
                transport=None,
            )
            if (
                duplicates
                or invalid
                or not (MIN_BATCH_SIZE <= len(symbols) <= MAX_BATCH_SIZE)
                or spec.get("batch_symbol_hash") != _canonical_digest(symbols)
                or spec.get("batch_input_hash") != _batch_input_hash(universe, symbols)
                or _industry_binding(spec) != _industry_binding(universe)
                or spec.get("industry_input_digest") != _industry_input_digest(universe)
                or not _dispatch_chain_ready(success, task, run_id=run_id, transport=transport)
                or str(success.get("celery_task_id") or "") in _quarantined_task_ids_for_db(
                    db_path,
                    run_id,
                )
                or not valid
            ):
                tasks_ready = False
                break
            seen_symbols.extend(symbols)
            celery_ids.append(str(success.get("celery_task_id") or ""))
            worker_ids.append(str(success.get("worker_task_id") or ""))
            for row in task_rows:
                expected_result_rows.append(
                    {
                        **row,
                        "batch_index": index,
                        "celery_task_id": str(success.get("celery_task_id") or ""),
                        "worker_task_id": str(success.get("worker_task_id") or ""),
                        "worker_hostname": str(success.get("worker_hostname") or ""),
                        "worker_pid": _integer(success.get("worker_pid")),
                        "worker_queue": str(success.get("worker_queue") or ""),
                        "provider_scope_hash": universe.get("scope_hash"),
                        "universe_digest": universe.get("universe_digest"),
                    }
                )
        if sorted(seen_symbols) != universe.get("symbols") or len(set(seen_symbols)) != len(seen_symbols):
            tasks_ready = False
        if celery_ids != packet.get("celery_task_ids") or worker_ids != packet.get("worker_task_ids"):
            tasks_ready = False
        expected_result_rows = sorted(
            expected_result_rows,
            key=lambda row: (-_integer(row.get("score")), str(row.get("ts_code"))),
        )
        for rank, row in enumerate(expected_result_rows, start=1):
            row["full_market_rank"] = rank
        if _canonical_digest([row.get("dispatch_chain_digest") for row in successes]) != packet.get(
            "dispatch_chain_digest"
        ):
            tasks_ready = False

    stage = _read_packet_no_init(db_path, str(packet.get("stage_key") or ""))
    stage_binding = _canonical_digest(
        {key: value for key, value in stage.items() if key != "stage_binding_digest"}
    ) if stage else ""
    stage_ready = bool(
        stage.get("schema_version") == STAGE_SCHEMA_VERSION
        and stage.get("status") == "full_market_worker_stage_ready_production_pending"
        and stage.get("acceptance_run_id") == run_id
        and stage.get("provider_version_digest") == universe.get("version_digest")
        and _industry_binding(stage) == _industry_binding(universe)
        and stage.get("industry_input_digest") == _industry_input_digest(universe)
        and stage.get("dispatch_chain_digest") == packet.get("dispatch_chain_digest")
        and stage.get("stage_binding_digest") == stage_binding
        and stage.get("stage_binding_digest") == packet.get("stage_binding_digest")
        and stage.get("production_worker_complete") is False
        and stage.get("synthetic_fixture") is False
    )

    pointer = parquet_store.versioned_dataset_pointer(
        root=evidence_root / "parquet",
        name=RESULT_DATASET,
        pointer="current",
    )
    last_good_pointer = parquet_store.versioned_dataset_pointer(
        root=evidence_root / "parquet",
        name=RESULT_DATASET,
        pointer="last_good",
    )
    manifest = parquet_store.versioned_dataset_manifest(
        root=evidence_root / "parquet",
        name=RESULT_DATASET,
    )
    result_path = Path(str(pointer.get("artifact_path") or ""))
    result_frame = None
    if result_path.is_file():
        try:
            import pandas as pd

            result_frame = pd.read_parquet(result_path)
        except Exception:
            result_frame = None
    result_rows = result_frame.to_dict(orient="records") if result_frame is not None else []
    result_symbols, result_duplicates, result_invalid = _normalize_symbols(
        [row.get("ts_code") for row in result_rows]
    )
    last_good_result_ready = bool(
        last_good_pointer.get("status") == "ready"
        and last_good_pointer.get("artifact_sha256_matches") is True
        and (
            candidate_mode
            or (
                last_good_pointer.get("version_id") == pointer.get("version_id")
                and last_good_pointer.get("artifact_sha256") == pointer.get("artifact_sha256")
            )
        )
    )
    result_ready = bool(
        pointer.get("status") == "ready"
        and pointer.get("version_id") == packet.get("result_version_id")
        and pointer.get("artifact_sha256_matches") is True
        and pointer.get("artifact_sha256") == packet.get("result_artifact_sha256")
        and _integer(pointer.get("row_count")) == universe.get("universe_count")
        and isinstance(pointer.get("lineage"), Mapping)
        and pointer.get("lineage", {}).get("acceptance_run_id") == run_id
        and pointer.get("lineage", {}).get("universe_digest") == universe.get("universe_digest")
        and pointer.get("lineage", {}).get("provider_version_digest") == universe.get("version_digest")
        and _industry_binding(pointer.get("lineage", {}))
        == _industry_binding(universe)
        and pointer.get("lineage", {}).get("industry_input_digest")
        == _industry_input_digest(universe)
        and pointer.get("lineage", {}).get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and pointer.get("lineage", {}).get("result_output_hash") == packet.get("result_output_hash")
        and pointer.get("lineage", {}).get("dispatch_chain_digest") == packet.get("dispatch_chain_digest")
        and result_symbols == universe.get("symbols")
        and not result_duplicates
        and not result_invalid
        and len(result_rows) == universe.get("universe_count")
        and _canonical_digest(result_rows) == packet.get("result_output_hash")
        and result_rows == expected_result_rows
        and all(row.get("does_not_execute_trades") is True for row in result_rows)
        and all(row.get("candidate_is_not_buy_instruction") is True for row in result_rows)
        and last_good_result_ready
        and manifest.get("status") == "ready"
        and any(
            row.get("version_id") == packet.get("result_version_id") and row.get("valid") is True
            for row in manifest.get("versions") or []
            if isinstance(row, Mapping)
        )
    )
    candidate_cache_packet = _read_packet_no_init(db_path, CANDIDATE_CACHE_PACKET_KEY)
    candidate_cache_binding = candidate_cache_packet.get("full_market_worker_replacement")
    cache_write_task_id = (
        str(candidate_cache_binding.get("cache_write_task_id") or "")
        if isinstance(candidate_cache_binding, Mapping)
        else ""
    )
    candidate_cache_write_task = _read_task_no_init(db_path, cache_write_task_id)
    authoritative_candidate_cache_ready = _candidate_cache_replacement_ready(
        candidate_cache_packet,
        packet,
        candidate_cache_write_task,
        evidence_root=evidence_root,
    )
    checks = {
        "upstream_provider_current_last_good_and_artifacts": universe.get("ready") is True,
        "production_packets_direct_binding": packets_ready,
        "redis_celery_direct_transport_attestation": transport_ready,
        "durable_promotion_journal": journal_ready,
        "durable_coordinator_checkpoint_resume_state": checkpoint_ready,
        "bound_worker_task_outputs": tasks_ready,
        "sqlite_stage_manifest": stage_ready,
        "atomic_parquet_pointer_and_scored_rows": result_ready,
    }
    blockers = [key for key, passed in checks.items() if not passed]
    ready = not blockers
    candidate_radar_replacement_blockers = []
    if not ready:
        candidate_radar_replacement_blockers.append("full_market_worker_runtime")
    if not authoritative_candidate_cache_ready:
        candidate_radar_replacement_blockers.extend(
            [
                PRODUCTION_LINEAGE_EXTERNAL_RUNNER_BLOCKER,
                "authoritative_candidate_cache_replacement",
                "deep_scan_worker_execution_evidence",
                "browser_visual_performance_evidence",
                "legacy_fallback_retirement_evidence",
            ]
        )
    return {
        "ready": ready,
        "status": (
            "full_market_worker_production_fact_verified"
            if ready
            else "full_market_worker_production_fact_blocked"
        ),
        "full_market_worker_runtime": ready,
        "celery_redis_runtime": ready,
        "local_production_worker_complete": ready,
        "local_full_market_worker_runtime": ready,
        "local_celery_redis_runtime": ready,
        "worker_output_kind": "candidate_radar_full_market_scores",
        "full_market_factor_research": False,
        "candidate_radar_production_replacement": bool(
            ready and authoritative_candidate_cache_ready
        ),
        "authoritative_candidate_cache_replacement": authoritative_candidate_cache_ready,
        "candidate_radar_replacement_blockers": candidate_radar_replacement_blockers,
        "universe_count": universe.get("universe_count", 0),
        "minimum_universe_size": minimum,
        "validated_trade_date": universe.get("validated_trade_date", ""),
        "blockers": blockers,
        "provider_blockers": universe.get("blockers", []),
        "read_only": True,
        "writes_storage": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }


def validate_factor_full_market_research_fact(evidence_root: Path) -> dict[str, Any]:
    """Expose local Factor facts separately; production requires Phase-2 trust."""

    from . import external_production_consumer_service

    local = _validate_factor_full_market_local_fact(evidence_root)
    consumer = external_production_consumer_service.validate_consumer(
        "factor",
        evidence_root=evidence_root,
    )
    ready = bool(local.get("ready") is True and consumer.get("ready") is True)
    blockers = list(local.get("blockers") or [])
    if local.get("ready") is True and consumer.get("ready") is not True:
        blockers.append("external_factor_production_consumer_missing_or_mismatch")
    return {
        **local,
        "ready": ready,
        "status": "factor_full_market_research_fact_verified"
        if ready
        else "factor_full_market_research_fact_blocked",
        "full_market_factor_research": ready,
        "local_full_market_factor_research": local.get("ready") is True,
        "local_fact": local,
        "external_production_consumer": consumer,
        "production_trusted": ready,
        "snapshot_rollback_resistant": ready,
        "blockers": list(dict.fromkeys(blockers)),
    }


def validate_full_market_worker_production_fact(
    evidence_root: Path,
    *,
    _candidate_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep runtime facts visible but never promote old booleans without trust."""

    if isinstance(_candidate_packet, Mapping):
        return _validate_full_market_worker_local_fact(
            evidence_root,
            _candidate_packet=_candidate_packet,
        )
    from . import external_production_consumer_service

    local = _validate_full_market_worker_local_fact(evidence_root)
    worker_consumer = external_production_consumer_service.validate_consumer(
        "worker",
        evidence_root=evidence_root,
    )
    radar_consumer = external_production_consumer_service.validate_consumer(
        "radar",
        evidence_root=evidence_root,
    )
    ready = bool(local.get("ready") is True and worker_consumer.get("ready") is True)
    radar_ready = bool(
        ready
        and local.get("authoritative_candidate_cache_replacement") is True
        and radar_consumer.get("ready") is True
    )
    blockers = list(local.get("blockers") or [])
    if local.get("ready") is True and worker_consumer.get("ready") is not True:
        blockers.append("external_worker_production_consumer_missing_or_mismatch")
    radar_blockers = list(local.get("candidate_radar_replacement_blockers") or [])
    if (
        local.get("authoritative_candidate_cache_replacement") is True
        and radar_consumer.get("ready") is not True
    ):
        radar_blockers.append("external_radar_production_consumer_missing_or_mismatch")
    return {
        **local,
        "ready": ready,
        "status": "full_market_worker_production_fact_verified"
        if ready
        else "full_market_worker_production_fact_blocked",
        "production_worker_complete": ready,
        "full_market_worker_runtime": ready,
        "celery_redis_runtime": ready,
        "local_runtime_fact_ready": local.get("ready") is True,
        "local_full_market_worker_runtime": local.get("full_market_worker_runtime") is True,
        "local_celery_redis_runtime": local.get("celery_redis_runtime") is True,
        "local_fact": local,
        "external_production_consumer": worker_consumer,
        "production_trusted": ready,
        "snapshot_rollback_resistant": ready,
        "candidate_radar_production_replacement": radar_ready,
        "candidate_radar_external_production_consumer": radar_consumer,
        "candidate_radar_replacement_blockers": list(dict.fromkeys(radar_blockers)),
        "blockers": list(dict.fromkeys(blockers)),
    }


def public_full_market_worker_acceptance_response(
    local_packet: Mapping[str, Any],
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Expose local execution separately; only exact Phase-2 trust is production."""

    packet = dict(local_packet)
    fact = validate_full_market_worker_production_fact(evidence_root or EVIDENCE_ROOT)
    consumer = fact.get("external_production_consumer")
    consumer = dict(consumer) if isinstance(consumer, Mapping) else {}
    local_ready = bool(
        packet.get("local_production_worker_complete") is True
        and packet.get("local_full_market_worker_runtime") is True
        and packet.get("local_celery_redis_runtime") is True
        and packet.get("acceptance_run_id")
        and packet.get("result_version_id")
    )
    exact_consumer = bool(
        consumer.get("ready") is True
        and consumer.get("subject") == packet.get("acceptance_run_id")
        and consumer.get("generation") == packet.get("result_version_id")
    )
    production_ready = bool(
        local_ready
        and exact_consumer
        and fact.get("ready") is True
        and fact.get("production_trusted") is True
        and fact.get("snapshot_rollback_resistant") is True
    )
    return {
        **packet,
        "status": (
            "full_market_worker_production_acceptance_external_trust_verified"
            if production_ready
            else "full_market_worker_local_runtime_complete_external_trust_pending"
            if local_ready
            else packet.get("status") or "full_market_worker_production_acceptance_blocked"
        ),
        "local_status": packet.get("status") or "",
        "ready": production_ready,
        "production_worker_complete": production_ready,
        "full_market_worker_runtime": production_ready,
        "celery_redis_runtime": production_ready,
        "local_production_worker_complete": local_ready,
        "local_full_market_worker_runtime": local_ready,
        "local_celery_redis_runtime": local_ready,
        "local_runtime_fact_ready": fact.get("local_runtime_fact_ready") is True,
        "external_production_consumer": consumer,
        "external_consumer_exact_source_match": exact_consumer,
        "external_trust_verified": production_ready,
        "production_trusted": production_ready,
        "snapshot_rollback_resistant": production_ready,
    }


def _run_full_market_worker_production_acceptance_impl(
    payload: Any,
    _register_official_orchestrator: Any,
    _revoke_official_orchestrator: Any,
) -> dict[str, Any]:
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    if payload_map.get("operator_approved") is not True:
        return _blocked_attempt(
            "full_market_worker_production_blocked_operator_approval_required",
            dispatch_count=0,
        )
    recovery = _recover_interrupted_promotion()
    if recovery.get("ready") is not True:
        return _blocked_attempt(
            "full_market_worker_interrupted_promotion_recovery_required",
            dispatch_count=0,
            recovery_status=recovery.get("status"),
            rollback_results=recovery.get("rollback_results", {}),
        )
    minimum = _bounded_integer(
        payload_map.get("minimum_universe_size"),
        default=DEFAULT_MINIMUM_UNIVERSE_SIZE,
        minimum=DEFAULT_MINIMUM_UNIVERSE_SIZE,
        maximum=MAXIMUM_MINIMUM_UNIVERSE_SIZE,
    )
    universe = _authoritative_provider_universe(
        EVIDENCE_ROOT,
        minimum_universe_size=minimum,
        include_frames=True,
        require_industry_membership=True,
    )
    if universe.get("ready") is not True:
        return _blocked_attempt(
            "authoritative_full_market_universe_missing_or_below_threshold",
            dispatch_count=0,
            universe_count=universe.get("universe_count", 0),
            minimum_universe_size=minimum,
            blockers=universe.get("blockers", []),
        )

    raw_resume = str(payload_map.get("resume_run_id") or "").strip()
    requested_resume = _normalize_uuid4(raw_resume) if raw_resume else ""
    run_id = requested_resume or uuid.uuid4().hex
    if raw_resume and not requested_resume:
        return _blocked_attempt("full_market_worker_resume_run_id_invalid", dispatch_count=0)
    if not _acquire_lock(run_id):
        return _blocked_attempt(
            "full_market_worker_coordinator_lock_held",
            run_id=run_id,
            dispatch_count=0,
        )
    app: Any = None
    capability: Any = None
    state: dict[str, Any] = {}
    challenge_secrets: dict[str, bytes] = {}
    challenge_client: Any = None
    try:
        app, probed_transport = _build_and_probe_official_transport(acceptance_run_id=run_id)
        if probed_transport.get("ready") is not True:
            return _blocked_attempt(
                "full_market_worker_production_blocked_real_transport_required",
                run_id=run_id,
                dispatch_count=0,
                transport_status=probed_transport.get("status"),
                call_ledger=probed_transport.get("call_ledger", []),
            )
        capability, state = _register_official_orchestrator(run_id)
        challenge_client = app.backend.client

        def _issue_worker_challenge(specification: Mapping[str, Any]) -> str:
            challenge_id = uuid.uuid4().hex
            secret = os.urandom(32)
            key = _worker_challenge_key(run_id, challenge_id)
            try:
                written = challenge_client.set(
                    key,
                    secret,
                    ex=WORKER_CHALLENGE_TTL_SECONDS,
                    nx=True,
                )
            except Exception:
                return ""
            if written is not True:
                return ""
            challenge_secrets[challenge_id] = secret
            return challenge_id

        def _verify_consumed_worker_challenge(
            task: Mapping[str, Any],
            specification: Mapping[str, Any],
        ) -> bool:
            challenge_id = str(specification.get("worker_challenge_id") or "")
            secret = challenge_secrets.get(challenge_id)
            runtime = task.get("runtime_provenance") if isinstance(task.get("runtime_provenance"), Mapping) else {}
            payload_safe = task.get("payload_safe") if isinstance(task.get("payload_safe"), Mapping) else {}
            if not secret or not _normalize_uuid4(challenge_id):
                return False
            try:
                consumed = challenge_client.get(_worker_challenge_key(run_id, challenge_id)) is None
            except Exception:
                return False
            material = _worker_execution_proof_material(payload_safe, runtime)
            encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
            expected = hmac.new(secret, encoded, hashlib.sha256).hexdigest()
            verified = bool(
                consumed
                and runtime.get("worker_challenge_consumed") is True
                and runtime.get("worker_challenge_id") == challenge_id
                and hmac.compare_digest(
                    str(runtime.get("worker_execution_proof") or ""),
                    expected,
                )
            )
            if verified:
                receipt_value = _worker_execution_receipt_value(task, specification, transport)
                try:
                    written = challenge_client.set(
                        _worker_challenge_receipt_key(run_id, challenge_id),
                        receipt_value,
                        ex=WORKER_RECEIPT_TTL_SECONDS,
                        nx=True,
                    )
                    receipt_readback = challenge_client.get(
                        _worker_challenge_receipt_key(run_id, challenge_id)
                    )
                    if isinstance(receipt_readback, bytes):
                        receipt_readback = receipt_readback.decode("ascii", errors="strict")
                    verified = bool(written is True and receipt_readback == receipt_value)
                except Exception:
                    verified = False
            if verified:
                challenge_secrets.pop(challenge_id, None)
                state["verified_worker_task_ids"].add(str(specification.get("celery_task_id") or ""))
            return verified

        def _verify_resume_worker_receipt(
            success: Mapping[str, Any],
            task: Mapping[str, Any],
        ) -> bool:
            challenge_id = str(success.get("worker_challenge_id") or "")
            if not _normalize_uuid4(challenge_id):
                return False
            expected = _worker_execution_receipt_value(task, success, transport)
            try:
                receipt = challenge_client.get(
                    _worker_challenge_receipt_key(run_id, challenge_id)
                )
                challenge_absent = challenge_client.get(
                    _worker_challenge_key(run_id, challenge_id)
                ) is None
            except Exception:
                return False
            if isinstance(receipt, bytes):
                try:
                    receipt = receipt.decode("ascii", errors="strict")
                except UnicodeDecodeError:
                    return False
            verified = bool(
                challenge_absent
                and _HEX_64_RE.fullmatch(str(receipt or ""))
                and hmac.compare_digest(str(receipt or ""), expected)
            )
            if verified:
                state["verified_worker_task_ids"].add(str(success.get("celery_task_id") or ""))
            return verified

        def _cleanup_worker_challenges(challenge_ids: list[str]) -> None:
            for challenge_id in challenge_ids:
                if not challenge_id:
                    continue
                challenge_secrets.pop(challenge_id, None)
                try:
                    challenge_client.delete(_worker_challenge_key(run_id, challenge_id))
                except Exception:
                    pass

        if requested_resume:
            transport = _read_packet_no_init(SQLITE_META_PATH, _transport_key(run_id))
            execution_event = _read_packet_no_init(SQLITE_META_PATH, _execution_event_key(run_id))
            persisted_workers = sorted(transport.get("eligible_worker_names") or [])
            probed_workers = sorted(probed_transport.get("eligible_worker_names") or [])
            if not (
                _transport_execution_event_ready(transport, execution_event, run_id=run_id)
                and transport.get("broker_endpoint_digest") == probed_transport.get("broker_endpoint_digest")
                and transport.get("backend_endpoint_digest") == probed_transport.get("backend_endpoint_digest")
                and transport.get("official_runtime_origin_digest")
                == probed_transport.get("official_runtime_origin_digest")
                and persisted_workers == probed_workers
            ):
                return _blocked_attempt(
                    "full_market_worker_resume_transport_binding_invalid",
                    run_id=run_id,
                    dispatch_count=0,
                    call_ledger=probed_transport.get("call_ledger", []),
                )
            state["transport_event_persisted"] = True
        else:
            transport, execution_event = _persist_official_transport_execution_event_atomic(
                run_id,
                probed_transport,
                capability=capability,
            )
        if not _transport_execution_event_ready(transport, execution_event, run_id=run_id):
            return _blocked_attempt(
                "full_market_worker_transport_attestation_readback_failed",
                run_id=run_id,
                dispatch_count=0,
                call_ledger=transport.get("call_ledger", []),
            )

        requested_batch = _bounded_integer(
            payload_map.get("batch_size"),
            default=DEFAULT_BATCH_SIZE,
            minimum=MIN_BATCH_SIZE,
            maximum=MAX_BATCH_SIZE,
        )
        batches = _partition_symbols(list(universe.get("symbols") or []), requested_batch)
        if not batches or any(not (MIN_BATCH_SIZE <= len(batch) <= MAX_BATCH_SIZE) for batch in batches):
            return _blocked_attempt(
                "full_market_worker_batch_partition_invalid",
                run_id=run_id,
                dispatch_count=0,
            )
        prior_successes: list[dict[str, Any]] = []
        if requested_resume:
            checkpoint = _read_packet_no_init(SQLITE_META_PATH, _checkpoint_key(run_id))
            prior_successes = _validated_resume_successes(
                checkpoint,
                run_id=run_id,
                universe=universe,
                batches=batches,
                transport=transport,
                execution_event=execution_event,
                resume_proof_verifier=_verify_resume_worker_receipt,
            )
            if checkpoint and not prior_successes:
                return _blocked_attempt(
                    "full_market_worker_resume_checkpoint_invalid",
                    run_id=run_id,
                    dispatch_count=0,
                )
        _write_coordinator_task(
            run_id,
            status="running",
            step="dispatching_candidate_batches",
            checkpoint_key=_checkpoint_key(run_id),
        )
        timeout = _bounded_integer(
            payload_map.get("result_timeout_seconds"),
            default=DEFAULT_RESULT_TIMEOUT_SECONDS,
            minimum=60,
            maximum=MAX_RESULT_TIMEOUT_SECONDS,
        )
        successes, dispatched = _dispatch_batches(
            app,
            batches=batches,
            run_id=run_id,
            universe=universe,
            transport=transport,
            timeout_seconds=timeout,
            prior_successes=prior_successes,
            challenge_issuer=_issue_worker_challenge,
            challenge_verifier=_verify_consumed_worker_challenge,
            challenge_cleanup=_cleanup_worker_challenges,
        )
        if len(successes) != len(batches):
            _write_checkpoint(
                run_id=run_id,
                universe=universe,
                batches=batches,
                successes=successes,
                status="partial_failure_resume_available",
                transport=transport,
            )
            _write_coordinator_task(
                run_id,
                status="failed",
                step="candidate_batches_partial_or_failed",
                checkpoint_key=_checkpoint_key(run_id),
            )
            return _blocked_attempt(
                "full_market_worker_batches_partial_or_failed",
                run_id=run_id,
                dispatch_count=len(dispatched),
                successful_batch_count=len(successes),
                batch_count=len(batches),
                resume_available=bool(successes),
            )
        checkpoint = _write_checkpoint(
            run_id=run_id,
            universe=universe,
            batches=batches,
            successes=successes,
            status="complete",
            transport=transport,
        )
        result_rows = _result_rows_from_batches(
            successes,
            universe=universe,
            transport=transport,
            execution_event=execution_event,
        )
        if len(result_rows) != universe.get("universe_count"):
            _write_coordinator_task(
                run_id,
                status="failed",
                step="candidate_result_merge_failed",
                checkpoint_key=_checkpoint_key(run_id),
            )
            return _blocked_attempt(
                "full_market_worker_candidate_result_merge_failed",
                run_id=run_id,
                dispatch_count=len(dispatched),
            )
        _write_coordinator_task(
            run_id,
            status="success",
            step="full_market_worker_production_completed",
            checkpoint_key=_checkpoint_key(run_id),
        )
        return _promote_official_candidate_results(
            run_id=run_id,
            universe=universe,
            transport=transport,
            checkpoint=checkpoint,
            result_rows=result_rows,
            capability=capability,
        )
    finally:
        if challenge_client is not None:
            for challenge_id in list(challenge_secrets):
                try:
                    challenge_client.delete(_worker_challenge_key(run_id, challenge_id))
                except Exception:
                    pass
            challenge_secrets.clear()
        if capability is not None:
            _revoke_official_orchestrator(capability)
        _release_lock(run_id)
        if app is not None:
            try:
                app.close()
            except Exception:
                pass


run_full_market_worker_production_acceptance, _official_orchestrator_state = (
    _make_public_acceptance_runner(_run_full_market_worker_production_acceptance_impl)
)
del _run_full_market_worker_production_acceptance_impl
