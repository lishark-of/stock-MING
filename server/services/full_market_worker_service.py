from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
import re
import sqlite3
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
SCHEMA_VERSION = "full_market_worker_production_acceptance.v2"
STAGE_SCHEMA_VERSION = "full_market_worker_production_stage.v2"
CHECKPOINT_SCHEMA_VERSION = "full_market_worker_checkpoint.v1"
TRANSPORT_SCHEMA_VERSION = "redis_celery_direct_attestation.v1"

PROVIDER_CURRENT_KEY = "command_center_tushare_full_market_universe_production_current"
PROVIDER_LAST_GOOD_KEY = "command_center_tushare_full_market_universe_production_last_good"
PROVIDER_SCHEMA_VERSION = "tushare_full_market_universe_production.v1"
PROVIDER_COMPLETE_STATUS = "full_market_universe_production_complete"
PROVIDER_DATASET = "full_market_universe"

CANDIDATE_TASK_NAME = "run_candidate_radar_full_pool_local_scan"
CANDIDATE_TASK_TYPE = CANDIDATE_TASK_NAME
CANDIDATE_QUEUE = "command_center_candidate_production"
RESULT_DATASET = "full_market_candidate_radar_results"

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

ARTIFACT_REQUIRED_COLUMNS = {
    "stock_basic": (
        "ts_code",
        "symbol",
        "name",
        "market",
        "exchange",
        "list_status",
        "delist_date",
        "provider_scope_hash",
    ),
    "trade_cal": ("cal_date", "is_open", "provider_scope_hash"),
    "daily": ("ts_code", "trade_date", "close", "amount", "provider_scope_hash"),
    "daily_basic": (
        "ts_code",
        "trade_date",
        "turnover_rate",
        "volume_ratio",
        "total_mv",
        "circ_mv",
        "pe_ttm",
        "pb",
        "provider_scope_hash",
    ),
    "moneyflow": (
        "ts_code",
        "trade_date",
        "buy_lg_amount",
        "sell_lg_amount",
        "buy_elg_amount",
        "sell_elg_amount",
        "provider_scope_hash",
    ),
}
FEATURE_CONTRACT = {
    "schema_version": "candidate_radar_full_market_feature_contract.v1",
    "source_contract": "next_stock_radar_full_market_rough_and_rule_score",
    "daily_target_sessions": TARGET_DAILY_SESSIONS,
    "daily_minimum_sessions": MIN_DAILY_SESSIONS,
    "moneyflow_minimum_sessions": MIN_MONEYFLOW_SESSIONS,
    "required_artifacts": sorted(ARTIFACT_REQUIRED_COLUMNS),
    "required_columns": {
        key: list(value) for key, value in sorted(ARTIFACT_REQUIRED_COLUMNS.items())
    },
    "rough_score_formula": "legacy_base42_ma20_ma60_return20_amount",
    "dimension_weights": {
        "trend": 0.25,
        "money": 0.22,
        "risk": 0.22,
        "position": 0.16,
        "information": 0.10,
        "holding_compare_neutral": 0.05,
    },
    "research_only": True,
    "does_not_execute_trades": True,
}
FEATURE_CONTRACT_DIGEST = hashlib.sha256(
    json.dumps(FEATURE_CONTRACT, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

_HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^[0-9]{8}$")
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


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _integer(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bounded_integer(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(_integer(value, default=default), maximum))


def _read_packet_no_init(db_path: Path, packet_key: str) -> dict[str, Any]:
    if not db_path.is_file():
        return {}
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(db_path)
        row = connection.execute(
            "SELECT payload_json FROM packets WHERE packet_key = ?",
            (packet_key,),
        ).fetchone()
        value = json.loads(row[0]) if row else {}
    except Exception:
        return {}
    finally:
        if connection is not None:
            connection.close()
    return dict(value) if isinstance(value, Mapping) else {}


def _read_task_no_init(db_path: Path, task_id: str) -> dict[str, Any]:
    if not db_path.is_file() or not task_id:
        return {}
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(db_path)
        row = connection.execute(
            "SELECT payload_json FROM task_status WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        value = json.loads(row[0]) if row else {}
    except Exception:
        return {}
    finally:
        if connection is not None:
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
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


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


def _parse_date(value: Any) -> _dt.date | None:
    text = str(value or "").strip().replace("-", "")
    if not _DATE_RE.fullmatch(text):
        return None
    try:
        return _dt.datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _safe_artifact_path(root: Path, relpath: Any) -> Path | None:
    text = str(relpath or "").strip()
    if not text:
        return None
    candidate = Path(text)
    path = candidate if candidate.is_absolute() else root / candidate
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return path


def _read_artifact_frame(
    evidence_root: Path,
    entry: Mapping[str, Any],
    *,
    required_columns: tuple[str, ...],
) -> tuple[Any, dict[str, Any]]:
    path = _safe_artifact_path(evidence_root, entry.get("path") or entry.get("artifact_relpath"))
    expected_sha = str(entry.get("sha256") or entry.get("artifact_sha256") or "").lower()
    if path is None or not path.is_file() or not _HEX_64_RE.fullmatch(expected_sha):
        return None, {"ready": False, "status": "artifact_path_or_digest_invalid"}
    actual_sha = _sha256_file(path)
    if actual_sha != expected_sha:
        return None, {"ready": False, "status": "artifact_digest_mismatch"}
    try:
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(path)
        columns = tuple(str(item) for item in parquet.schema_arrow.names)
        if any(column not in columns for column in required_columns):
            return None, {"ready": False, "status": "artifact_required_columns_missing"}
        frame = pq.read_table(path, columns=list(required_columns)).to_pandas()
    except Exception as exc:
        return None, {"ready": False, "status": f"artifact_read_failed_{type(exc).__name__}"}
    row_count = int(len(frame))
    if row_count != _integer(entry.get("row_count"), default=-1):
        return None, {"ready": False, "status": "artifact_row_count_mismatch"}
    return frame, {
        "ready": True,
        "status": "artifact_verified",
        "path": str(path),
        "sha256": actual_sha,
        "row_count": row_count,
        "columns": list(columns),
    }


def _ledger_direct_provider_ready(
    packet: Mapping[str, Any],
    scope_hash: str,
    artifacts: Mapping[str, Any],
) -> bool:
    ledger = [dict(row) for row in packet.get("call_ledger") or [] if isinstance(row, Mapping)]
    by_api = {str(row.get("api") or ""): row for row in ledger}
    for api in ("stock_basic", "trade_cal", "daily", "daily_basic", "moneyflow"):
        row = by_api.get(api, {})
        artifact = artifacts.get(api) if isinstance(artifacts.get(api), Mapping) else {}
        if not (
            row.get("call_status") == "success"
            and _integer(row.get("row_count")) > 0
            and row.get("external_calls_triggered") is True
            and row.get("tushare_called") is True
            and row.get("real_provider_adapter_used") is True
            and row.get("provider_provenance_validator") is True
            and str(row.get("scope_hash") or "").lower() == scope_hash
            and row.get("does_not_execute_trades") is True
            and row.get("does_not_modify_strategy_action") is True
            and row.get("artifact_sha256") == artifact.get("sha256")
            and _integer(row.get("artifact_row_count"), default=-1)
            == _integer(artifact.get("row_count"), default=-2)
            and row.get("date_start") == artifact.get("date_start")
            and row.get("date_end") == artifact.get("date_end")
            and _integer(row.get("symbol_count"), default=-1)
            == _integer(artifact.get("symbol_count"), default=-2)
        ):
            return False
    return True


def _provider_packet_ready(packet: Mapping[str, Any], scope_hash: str) -> bool:
    artifacts = packet.get("artifacts") if isinstance(packet.get("artifacts"), Mapping) else {}
    return bool(
        packet.get("schema_version") == PROVIDER_SCHEMA_VERSION
        and packet.get("status") == PROVIDER_COMPLETE_STATUS
        and str(packet.get("scope_hash") or "").lower() == scope_hash
        and packet.get("provider_provenance_validator") is True
        and packet.get("real_provider_adapter_used") is True
        and packet.get("durable_stage_readback_verified") is True
        and packet.get("durable_final_promotion_verified") is True
        and packet.get("synthetic_fixture") is False
        and packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and _ledger_direct_provider_ready(packet, scope_hash, artifacts)
    )


def _authoritative_provider_universe(
    evidence_root: Path,
    *,
    minimum_universe_size: int,
    include_frames: bool = False,
) -> dict[str, Any]:
    db_path = evidence_root / "meta.sqlite"
    current = _read_packet_no_init(db_path, PROVIDER_CURRENT_KEY)
    last_good = _read_packet_no_init(db_path, PROVIDER_LAST_GOOD_KEY)
    scope_hash = str(current.get("scope_hash") or "").strip().lower()
    validated_trade_date = str(current.get("validated_trade_date") or "").replace("-", "")
    as_of_date = str(current.get("as_of_date") or "").replace("-", "")
    blockers: list[str] = []

    if not _HEX_64_RE.fullmatch(scope_hash):
        blockers.append("provider_scope_hash_missing_or_invalid")
    if not _provider_packet_ready(current, scope_hash):
        blockers.append("provider_current_strict_validation_failed")
    if not _provider_packet_ready(last_good, scope_hash):
        blockers.append("provider_last_good_strict_validation_failed")
    binding_fields = (
        "scope_hash",
        "universe_digest",
        "validated_trade_date",
        "as_of_date",
        "artifact_manifest_digest",
    )
    if any(current.get(field) != last_good.get(field) for field in binding_fields):
        blockers.append("provider_current_last_good_binding_mismatch")

    trade_day = _parse_date(validated_trade_date)
    as_of = _parse_date(as_of_date)
    today = _dt.datetime.now().date()
    if (
        trade_day is None
        or as_of is None
        or as_of < trade_day
        or today < trade_day
        or (today - trade_day).days > 7
        or current.get("trade_calendar_validated") is not True
    ):
        blockers.append("provider_trade_date_freshness_not_validated")

    provider_root = evidence_root / "parquet" / PROVIDER_DATASET
    pointer = _read_json(provider_root / "current.json")
    expected_stock_relpath = f"parquet/{PROVIDER_DATASET}/versions/{scope_hash}/stock_basic.parquet"
    if not (
        pointer.get("schema_version") == "tushare_full_market_universe_pointer.v1"
        and pointer.get("status") == PROVIDER_COMPLETE_STATUS
        and str(pointer.get("scope_hash") or "").lower() == scope_hash
        and pointer.get("artifact_relpath") == expected_stock_relpath
        and pointer.get("artifact_sha256") == current.get("stock_basic_artifact_sha256")
        and _integer(pointer.get("row_count"), default=-1)
        == _integer(current.get("stock_basic_row_count"), default=-2)
        and pointer.get("validated_trade_date") == current.get("validated_trade_date")
    ):
        blockers.append("provider_atomic_current_pointer_invalid")

    current_artifacts = current.get("artifacts") if isinstance(current.get("artifacts"), Mapping) else {}
    last_artifacts = last_good.get("artifacts") if isinstance(last_good.get("artifacts"), Mapping) else {}
    frames: dict[str, Any] = {}
    artifact_evidence: dict[str, Any] = {}
    for dataset, columns in ARTIFACT_REQUIRED_COLUMNS.items():
        entry = current_artifacts.get(dataset)
        last_entry = last_artifacts.get(dataset)
        entry_map = dict(entry) if isinstance(entry, Mapping) else {}
        last_map = dict(last_entry) if isinstance(last_entry, Mapping) else {}
        if not entry_map or any(
            entry_map.get(field) != last_map.get(field)
            for field in ("path", "sha256", "row_count", "date_start", "date_end", "symbol_count")
        ):
            blockers.append(f"provider_{dataset}_current_last_good_artifact_mismatch")
            continue
        frame, evidence = _read_artifact_frame(
            evidence_root,
            entry_map,
            required_columns=columns,
        )
        artifact_evidence[dataset] = evidence
        if frame is None:
            blockers.append(f"provider_{dataset}_{evidence.get('status')}")
            continue
        scoped_values = set(frame["provider_scope_hash"].fillna("").astype(str).str.lower())
        symbol_count = (
            int(frame["ts_code"].fillna("").astype(str).str.upper().nunique())
            if "ts_code" in frame.columns
            else 0
        )
        date_column = "cal_date" if dataset == "trade_cal" else "trade_date" if "trade_date" in frame.columns else ""
        date_values = (
            sorted(frame[date_column].fillna("").astype(str).str.replace("-", "", regex=False).unique())
            if date_column
            else []
        )
        actual_start = date_values[0] if date_values else validated_trade_date
        actual_end = date_values[-1] if date_values else validated_trade_date
        if (
            scoped_values != {scope_hash}
            or symbol_count != _integer(entry_map.get("symbol_count"), default=-1)
            or actual_start != str(entry_map.get("date_start") or "").replace("-", "")
            or actual_end != str(entry_map.get("date_end") or "").replace("-", "")
        ):
            blockers.append(f"provider_{dataset}_scope_date_or_symbol_metadata_mismatch")
        frames[dataset] = frame

    manifest_rows: list[dict[str, Any]] = []
    for dataset in sorted(ARTIFACT_REQUIRED_COLUMNS):
        raw_entry = current_artifacts.get(dataset)
        entry = dict(raw_entry) if isinstance(raw_entry, Mapping) else {}
        manifest_rows.append(
            {
                "dataset": dataset,
                "path": entry.get("path"),
                "sha256": entry.get("sha256"),
                "row_count": entry.get("row_count"),
                "date_start": entry.get("date_start"),
                "date_end": entry.get("date_end"),
                "symbol_count": entry.get("symbol_count"),
            }
        )
    if _canonical_digest(manifest_rows) != str(current.get("artifact_manifest_digest") or ""):
        blockers.append("provider_artifact_manifest_digest_recompute_mismatch")

    symbols: list[str] = []
    duplicate_count = 0
    invalid_count = 0
    stock_basic = frames.get("stock_basic")
    if stock_basic is not None:
        listed = stock_basic[
            stock_basic["list_status"].astype(str).str.upper().eq("L")
            & stock_basic["delist_date"].fillna("").astype(str).str.strip().isin({"", "None", "nan"})
            & stock_basic["provider_scope_hash"].astype(str).str.lower().eq(scope_hash)
        ]
        symbols, duplicate_count, invalid_count = _normalize_symbols(listed["ts_code"].tolist())
        if len(listed) != len(symbols):
            duplicate_count += max(0, len(listed) - len(symbols) - invalid_count)
        if invalid_count:
            blockers.append("provider_stock_basic_contains_invalid_a_share_codes")
        if duplicate_count:
            blockers.append("provider_stock_basic_contains_duplicate_listed_codes")
        if len(symbols) < minimum_universe_size:
            blockers.append("provider_current_listed_universe_below_minimum")
        if _canonical_digest(symbols) != str(current.get("universe_digest") or ""):
            blockers.append("provider_universe_digest_recompute_mismatch")
        if _integer(current.get("universe_count"), default=-1) != len(symbols):
            blockers.append("provider_universe_count_recompute_mismatch")

    trade_cal = frames.get("trade_cal")
    if trade_cal is not None:
        open_dates = sorted(
            {
                str(value).replace("-", "")
                for value in trade_cal.loc[
                    trade_cal["is_open"].astype(str).isin({"1", "1.0", "True", "true"})
                    & trade_cal["provider_scope_hash"].astype(str).str.lower().eq(scope_hash),
                    "cal_date",
                ].tolist()
            }
        )
        if not open_dates or open_dates[-1] != validated_trade_date:
            blockers.append("provider_trade_cal_latest_open_date_mismatch")

    symbol_set = set(symbols)
    daily = frames.get("daily")
    if daily is not None:
        daily = daily[
            daily["provider_scope_hash"].astype(str).str.lower().eq(scope_hash)
            & daily["ts_code"].astype(str).str.upper().isin(symbol_set)
        ].copy()
        daily["trade_date"] = daily["trade_date"].astype(str).str.replace("-", "", regex=False)
        import pandas as pd

        for column in ("close", "amount"):
            daily[column] = pd.to_numeric(daily[column], errors="coerce")
        coverage = daily.groupby(daily["ts_code"].astype(str).str.upper())["trade_date"].nunique()
        latest = daily.groupby(daily["ts_code"].astype(str).str.upper())["trade_date"].max()
        if (
            len(coverage) != len(symbols)
            or bool((coverage < MIN_DAILY_SESSIONS).any())
            or set(latest.tolist()) != {validated_trade_date}
        ):
            blockers.append("provider_daily_history_or_freshness_coverage_incomplete")
        if daily[["close", "amount"]].isna().any().any():
            blockers.append("provider_daily_required_numeric_values_missing")
        frames["daily"] = daily

    daily_basic = frames.get("daily_basic")
    if daily_basic is not None:
        daily_basic = daily_basic[
            daily_basic["provider_scope_hash"].astype(str).str.lower().eq(scope_hash)
            & daily_basic["ts_code"].astype(str).str.upper().isin(symbol_set)
        ].copy()
        daily_basic["trade_date"] = daily_basic["trade_date"].astype(str).str.replace("-", "", regex=False)
        import pandas as pd

        numeric = ["turnover_rate", "volume_ratio", "total_mv", "circ_mv", "pe_ttm", "pb"]
        for column in numeric:
            daily_basic[column] = pd.to_numeric(daily_basic[column], errors="coerce")
        latest_basic = daily_basic[daily_basic["trade_date"].eq(validated_trade_date)]
        if set(latest_basic["ts_code"].astype(str).str.upper()) != symbol_set:
            blockers.append("provider_daily_basic_latest_full_market_coverage_incomplete")
        if latest_basic[numeric].isna().any().any():
            blockers.append("provider_daily_basic_required_numeric_values_missing")
        frames["daily_basic"] = latest_basic

    moneyflow = frames.get("moneyflow")
    if moneyflow is not None:
        moneyflow = moneyflow[
            moneyflow["provider_scope_hash"].astype(str).str.lower().eq(scope_hash)
            & moneyflow["ts_code"].astype(str).str.upper().isin(symbol_set)
        ].copy()
        moneyflow["trade_date"] = moneyflow["trade_date"].astype(str).str.replace("-", "", regex=False)
        import pandas as pd

        numeric = ["buy_lg_amount", "sell_lg_amount", "buy_elg_amount", "sell_elg_amount"]
        for column in numeric:
            moneyflow[column] = pd.to_numeric(moneyflow[column], errors="coerce")
        coverage = moneyflow.groupby(moneyflow["ts_code"].astype(str).str.upper())["trade_date"].nunique()
        latest = moneyflow.groupby(moneyflow["ts_code"].astype(str).str.upper())["trade_date"].max()
        if (
            len(coverage) != len(symbols)
            or bool((coverage < MIN_MONEYFLOW_SESSIONS).any())
            or set(latest.tolist()) != {validated_trade_date}
        ):
            blockers.append("provider_moneyflow_history_or_freshness_coverage_incomplete")
        if moneyflow[numeric].isna().any().any():
            blockers.append("provider_moneyflow_required_numeric_values_missing")
        frames["moneyflow"] = moneyflow

    ready = not blockers
    result = {
        "ready": ready,
        "status": (
            "authoritative_full_market_universe_ready"
            if ready
            else "authoritative_full_market_universe_missing_or_below_threshold"
        ),
        "provider_current_key": PROVIDER_CURRENT_KEY,
        "provider_last_good_key": PROVIDER_LAST_GOOD_KEY,
        "scope_hash": scope_hash,
        "validated_trade_date": validated_trade_date,
        "as_of_date": as_of_date,
        "symbols": symbols,
        "universe_count": len(symbols),
        "minimum_universe_size": minimum_universe_size,
        "universe_digest": _canonical_digest(symbols) if symbols else "",
        "duplicate_count": duplicate_count,
        "invalid_count": invalid_count,
        "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
        "artifact_evidence": artifact_evidence,
        "blockers": blockers,
        "provider_execution_triggered": False,
        "external_calls_triggered": False,
        "writes_storage": False,
    }
    if include_frames and ready:
        result["_frames"] = frames
    return result


def _clip_score(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def _score_candidate_rows(universe: Mapping[str, Any], symbols: list[str]) -> list[dict[str, Any]]:
    frames = universe.get("_frames") if isinstance(universe.get("_frames"), Mapping) else {}
    daily = frames.get("daily")
    basic = frames.get("daily_basic")
    flow = frames.get("moneyflow")
    if daily is None or basic is None or flow is None:
        return []
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        daily_rows = daily[daily["ts_code"].astype(str).str.upper().eq(symbol)].sort_values("trade_date")
        basic_rows = basic[basic["ts_code"].astype(str).str.upper().eq(symbol)]
        flow_rows = flow[flow["ts_code"].astype(str).str.upper().eq(symbol)].sort_values("trade_date")
        if len(daily_rows) < MIN_DAILY_SESSIONS or basic_rows.empty or len(flow_rows) < MIN_MONEYFLOW_SESSIONS:
            return []
        closes = [float(value) for value in daily_rows["close"].tolist()]
        latest = daily_rows.iloc[-1]
        basic_latest = basic_rows.iloc[-1]
        flow_latest = flow_rows.iloc[-1]
        flow_recent = flow_rows.tail(MIN_MONEYFLOW_SESSIONS)
        close = closes[-1]
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60
        return20 = (close / closes[-21] - 1.0) * 100.0
        today_main = float(flow_latest["buy_lg_amount"]) + float(flow_latest["buy_elg_amount"])
        today_main -= float(flow_latest["sell_lg_amount"]) + float(flow_latest["sell_elg_amount"])
        five_day_main = float(flow_recent["buy_lg_amount"].sum()) + float(flow_recent["buy_elg_amount"].sum())
        five_day_main -= float(flow_recent["sell_lg_amount"].sum()) + float(flow_recent["sell_elg_amount"].sum())

        rough = 42
        rough_notes: list[str] = []
        if close > ma20 > ma60:
            rough += 35
            rough_notes.append("current_price_gt_ma20_gt_ma60")
        if close < ma20:
            rough -= 12
            rough_notes.append("below_ma20")
        if close < ma60:
            rough -= 28
            rough_notes.append("below_ma60")
        if return20 > 60:
            rough -= 20
            rough_notes.append("return20_over_60")
        elif 3 <= return20 <= 35:
            rough += 8
            rough_notes.append("return20_moderate")
        if float(latest["amount"]) < 100000:
            rough -= 12
            rough_notes.append("amount_below_100000")

        trend = 45
        if close > ma20 > ma60:
            trend += 35
        elif close < ma20:
            trend -= 18
        if close < ma60:
            trend -= 28
        if return20 > 25:
            trend -= 6
        money = 45
        if today_main > 0:
            money += 15
        if five_day_main > 0:
            money += 20
        if today_main > 0 and five_day_main < 0:
            money -= 4
        if today_main < 0 and five_day_main < 0:
            money -= 26
        data_gaps = ["chip", "announcement", "news_digest", "margin", "dragon_tiger"]
        risk = 72
        position = 42
        information = _clip_score(100 - len(data_gaps) * 10)
        total = _clip_score(
            _clip_score(trend) * 0.25
            + _clip_score(money) * 0.22
            + _clip_score(risk) * 0.22
            + _clip_score(position) * 0.16
            + information * 0.10
            + 50 * 0.05
        )
        rows.append(
            {
                "ts_code": symbol,
                "data_date": str(latest["trade_date"]),
                "score": total,
                "rough_score": _clip_score(rough),
                "trend_score": _clip_score(trend),
                "money_score": _clip_score(money),
                "risk_score": _clip_score(risk),
                "position_score": _clip_score(position),
                "information_score": information,
                "close": round(close, 6),
                "ma20": round(ma20, 6),
                "ma60": round(ma60, 6),
                "return_20d_pct": round(return20, 6),
                "amount": round(float(latest["amount"]), 6),
                "turnover_rate": round(float(basic_latest["turnover_rate"]), 6),
                "volume_ratio": round(float(basic_latest["volume_ratio"]), 6),
                "total_mv": round(float(basic_latest["total_mv"]), 6),
                "circ_mv": round(float(basic_latest["circ_mv"]), 6),
                "pe_ttm": round(float(basic_latest["pe_ttm"]), 6),
                "pb": round(float(basic_latest["pb"]), 6),
                "today_main_net_amount": round(today_main, 6),
                "five_day_main_net_amount": round(five_day_main, 6),
                "rough_notes": rough_notes,
                "data_gaps": data_gaps,
                "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
                "research_only": True,
                "candidate_is_not_buy_instruction": True,
                "does_not_execute_trades": True,
            }
        )
    return sorted(rows, key=lambda row: str(row["ts_code"]))


def _persist_task(task: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(task)
    SQLiteMetaStore(SQLITE_META_PATH).write_task_status(payload)
    return payload


def execute_candidate_radar_batch_worker(
    payload: Any,
    *,
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    runtime_map = dict(runtime) if isinstance(runtime, Mapping) else {}
    request_id = str(runtime_map.get("celery_request_id") or "")
    symbols, duplicates, invalid = _normalize_symbols(payload_map.get("symbols"))
    worker_task_id = f"candidate-worker-{request_id or uuid.uuid4().hex[:20]}"
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
            "universe_digest": str(payload_map.get("universe_digest") or ""),
            "provider_scope_hash": str(payload_map.get("provider_scope_hash") or ""),
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
    )
    payload_ready = bool(
        payload_map.get("full_market_worker_acceptance") is True
        and payload_map.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and not duplicates
        and not invalid
        and MIN_BATCH_SIZE <= len(symbols) <= MAX_BATCH_SIZE
        and payload_map.get("batch_symbol_hash") == _canonical_digest(symbols)
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
    )
    if not (
        universe.get("ready") is True
        and universe.get("scope_hash") == payload_map.get("provider_scope_hash")
        and universe.get("universe_digest") == payload_map.get("universe_digest")
        and set(symbols).issubset(set(universe.get("symbols") or []))
    ):
        base["failure_reason_safe"] = "worker_independent_provider_universe_validation_failed"
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
            "candidate_row_count": len(candidate_rows),
            "provider_scope_hash": universe["scope_hash"],
            "universe_digest": universe["universe_digest"],
            "validated_trade_date": universe["validated_trade_date"],
            "synthetic_fixture": False,
            "call_ledger": [
                {
                    "api": "local_candidate_radar_full_market_scoring",
                    "call_status": "success",
                    "row_count": len(candidate_rows),
                    "batch_symbol_hash": _canonical_digest(symbols),
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


def _load_celery_app() -> Any:
    try:
        from worker.celery_app import celery_app
    except Exception:
        return None
    return celery_app


def _mock_like(value: Any) -> bool:
    return type(value).__module__.startswith("unittest.mock")


def _transport_probe(app: Any, *, acceptance_run_id: str) -> dict[str, Any]:
    try:
        from celery import Celery
    except Exception:
        Celery = ()  # type: ignore[assignment]
    if not Celery or not isinstance(app, Celery) or _mock_like(app):
        return {"ready": False, "status": "real_celery_app_required", "dispatch_count": 0}
    eager = bool(app.conf.task_always_eager)
    broker_scheme = urlsplit(str(app.conf.broker_url or "")).scheme.lower()
    backend_scheme = urlsplit(str(app.conf.result_backend or "")).scheme.lower()
    if eager or broker_scheme not in {"redis", "rediss"} or backend_scheme not in {"redis", "rediss"}:
        return {"ready": False, "status": "eager_inproc_or_non_redis_transport_rejected", "dispatch_count": 0}

    broker_direct = False
    backend_direct = False
    probe_digest = _canonical_digest({"run": acceptance_run_id, "nonce": uuid.uuid4().hex})
    probe_key = f"cc3:full-market:{acceptance_run_id}:probe"
    try:
        connection = app.connection_for_write()
        if _mock_like(connection):
            raise RuntimeError("mock_connection")
        connection.ensure_connection(max_retries=0)
        channel = connection.channel()
        broker_client = channel.client
        if _mock_like(channel) or _mock_like(broker_client):
            raise RuntimeError("mock_broker_client")
        broker_direct = bool(connection.connected and broker_client.ping() is True)
        channel.close()
        connection.release()
    except Exception:
        broker_direct = False
    try:
        client = app.backend.client
        if _mock_like(client):
            raise RuntimeError("mock_backend")
        ping = client.ping()
        client.set(probe_key, probe_digest, ex=30)
        roundtrip = client.get(probe_key)
        client.delete(probe_key)
        decoded = roundtrip.decode("utf-8") if isinstance(roundtrip, bytes) else str(roundtrip or "")
        backend_direct = ping is True and decoded == probe_digest
    except Exception:
        backend_direct = False
    if not broker_direct or not backend_direct:
        return {"ready": False, "status": "redis_broker_or_backend_direct_probe_failed", "dispatch_count": 0}

    try:
        inspector = app.control.inspect(timeout=3)
        pings = inspector.ping() or {}
        registered = inspector.registered() or {}
        queues = inspector.active_queues() or {}
        if any(_mock_like(value) for value in (inspector, pings, registered, queues)):
            raise RuntimeError("mock_inspector")
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
    return {
        "ready": ready,
        "status": "external_redis_celery_direct_attested" if ready else "registered_task_or_queue_missing",
        "schema_version": TRANSPORT_SCHEMA_VERSION,
        "acceptance_run_id": acceptance_run_id,
        "broker_direct_ping": broker_direct,
        "backend_roundtrip_verified": backend_direct,
        "registered_task_verified": bool(eligible_workers),
        "registered_queue_verified": bool(eligible_workers),
        "eligible_worker_count": len(eligible_workers),
        "eligible_worker_names": eligible_workers,
        "task_always_eager": eager,
        "probe_digest": probe_digest,
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
) -> tuple[bool, list[dict[str, Any]]]:
    payload = task.get("payload_safe") if isinstance(task.get("payload_safe"), Mapping) else {}
    runtime = task.get("runtime_provenance") if isinstance(task.get("runtime_provenance"), Mapping) else {}
    rows = [dict(row) for row in task.get("candidate_rows") or [] if isinstance(row, Mapping)]
    symbols, duplicates, invalid = _normalize_symbols([row.get("ts_code") for row in rows])
    expected_symbols = list(batch.get("symbols") or [])
    ready = bool(
        task.get("task_type") == CANDIDATE_TASK_TYPE
        and task.get("status") == "success"
        and task.get("current_step") == "candidate_radar_full_market_batch_completed"
        and task.get("synthetic_fixture") is False
        and runtime.get("bound_task_request") is True
        and runtime.get("synthetic_fixture") is False
        and runtime.get("celery_request_id") == batch.get("celery_task_id")
        and runtime.get("worker_hostname")
        and _integer(runtime.get("worker_pid")) > 0
        and runtime.get("worker_queue") == CANDIDATE_QUEUE
        and payload.get("acceptance_run_id") == batch.get("acceptance_run_id")
        and payload.get("celery_dispatch_id") == batch.get("celery_task_id")
        and payload.get("batch_symbol_hash") == batch.get("batch_symbol_hash")
        and payload.get("universe_digest") == universe.get("universe_digest")
        and payload.get("provider_scope_hash") == universe.get("scope_hash")
        and symbols == expected_symbols
        and not duplicates
        and not invalid
        and task.get("candidate_output_hash") == _canonical_digest(rows)
        and task.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and all(row.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST for row in rows)
        and all(row.get("does_not_execute_trades") is True for row in rows)
    )
    return ready, rows


def _revoke_and_quarantine(app: Any, task_ids: list[str], run_id: str, reason: str) -> None:
    for task_id in task_ids:
        try:
            app.control.revoke(task_id, terminate=False)
        except Exception:
            pass
    packet = {
        "schema_version": "full_market_worker_late_result_quarantine.v1",
        "status": "late_results_quarantined",
        "acceptance_run_id": run_id,
        "celery_task_ids": sorted(set(task_ids)),
        "reason": reason,
        "global_candidate_cache_overwritten": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }
    try:
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(f"{ATTEMPT_PACKET_KEY}:quarantine:{run_id}", packet)
    except Exception:
        pass


def _dispatch_batches(
    app: Any,
    *,
    batches: list[list[str]],
    run_id: str,
    universe: Mapping[str, Any],
    timeout_seconds: int,
    prior_successes: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    successes = list(prior_successes or [])
    completed_indexes = {_integer(row.get("batch_index"), default=-1) for row in successes}
    sent: list[tuple[Any, dict[str, Any]]] = []
    all_dispatched_ids: list[str] = []
    for batch_index, symbols in enumerate(batches):
        if batch_index in completed_indexes:
            continue
        celery_task_id = f"fmw-{run_id}-{batch_index:04d}"
        specification = {
            "acceptance_run_id": run_id,
            "batch_index": batch_index,
            "batch_count": len(batches),
            "symbols": symbols,
            "batch_symbol_hash": _canonical_digest(symbols),
            "celery_task_id": celery_task_id,
        }
        payload = {
            **specification,
            "celery_dispatch_id": celery_task_id,
            "full_market_worker_acceptance": True,
            "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
            "universe_digest": universe["universe_digest"],
            "provider_scope_hash": universe["scope_hash"],
            "minimum_universe_size": universe["minimum_universe_size"],
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
            _revoke_and_quarantine(app, all_dispatched_ids, run_id, "dispatch_exception")
            return successes, all_dispatched_ids
        if _mock_like(result) or str(result.id or "") != celery_task_id:
            _revoke_and_quarantine(app, all_dispatched_ids + [celery_task_id], run_id, "async_result_id_mismatch")
            return successes, all_dispatched_ids + [celery_task_id]
        sent.append((result, specification))
        all_dispatched_ids.append(celery_task_id)

    deadline = time.monotonic() + timeout_seconds
    for result, specification in sent:
        celery_task_id = specification["celery_task_id"]
        try:
            returned = result.get(timeout=max(0.1, deadline - time.monotonic()))
            async_result = app.AsyncResult(celery_task_id)
            if _mock_like(async_result) or async_result.id != celery_task_id or async_result.state != "SUCCESS":
                raise RuntimeError("async_result_state_or_id_mismatch")
        except Exception:
            outstanding = [row[1]["celery_task_id"] for row in sent if row[1]["celery_task_id"] not in {item.get("celery_task_id") for item in successes}]
            _revoke_and_quarantine(app, outstanding, run_id, "result_timeout_or_failure")
            return successes, all_dispatched_ids
        result_task = dict(returned) if isinstance(returned, Mapping) else {}
        worker_task_id = str(result_task.get("task_id") or "")
        persisted = _read_task_no_init(SQLITE_META_PATH, worker_task_id)
        valid, rows = _validate_worker_task(persisted, batch=specification, universe=universe)
        if not valid or result_task.get("candidate_output_hash") != persisted.get("candidate_output_hash"):
            _revoke_and_quarantine(app, [celery_task_id], run_id, "worker_result_direct_readback_invalid")
            return successes, all_dispatched_ids
        successes.append(
            {
                **specification,
                "worker_task_id": worker_task_id,
                "candidate_output_hash": persisted["candidate_output_hash"],
                "candidate_row_count": len(rows),
                "worker_hostname": persisted.get("runtime_provenance", {}).get("worker_hostname"),
                "worker_pid": persisted.get("runtime_provenance", {}).get("worker_pid"),
                "worker_queue": persisted.get("runtime_provenance", {}).get("worker_queue"),
            }
        )
    return sorted(successes, key=lambda row: _integer(row.get("batch_index"))), all_dispatched_ids


def _write_checkpoint(
    *,
    run_id: str,
    universe: Mapping[str, Any],
    batches: list[list[str]],
    successes: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    packet = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "status": status,
        "acceptance_run_id": run_id,
        "provider_scope_hash": universe.get("scope_hash"),
        "universe_digest": universe.get("universe_digest"),
        "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
        "batch_count": len(batches),
        "batch_specifications": [
            {
                "batch_index": index,
                "symbols": symbols,
                "batch_symbol_hash": _canonical_digest(symbols),
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
    SQLiteMetaStore(SQLITE_META_PATH).write_packet(_checkpoint_key(run_id), packet)
    return packet


def _validated_resume_successes(
    checkpoint: Mapping[str, Any],
    *,
    universe: Mapping[str, Any],
    batches: list[list[str]],
) -> list[dict[str, Any]]:
    if not (
        checkpoint.get("schema_version") == CHECKPOINT_SCHEMA_VERSION
        and checkpoint.get("synthetic_fixture") is False
        and checkpoint.get("provider_scope_hash") == universe.get("scope_hash")
        and checkpoint.get("universe_digest") == universe.get("universe_digest")
        and checkpoint.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and _integer(checkpoint.get("batch_count")) == len(batches)
    ):
        return []
    valid: list[dict[str, Any]] = []
    seen: set[int] = set()
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
        task_ready, _rows = _validate_worker_task(task, batch=specification, universe=universe)
        if not task_ready:
            return []
        seen.add(batch_index)
        valid.append(dict(row))
    return sorted(valid, key=lambda row: _integer(row.get("batch_index")))


def _result_rows_from_batches(
    successes: list[dict[str, Any]],
    *,
    universe: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch in sorted(successes, key=lambda row: _integer(row.get("batch_index"))):
        task = _read_task_no_init(SQLITE_META_PATH, str(batch.get("worker_task_id") or ""))
        ready, task_rows = _validate_worker_task(task, batch=batch, universe=universe)
        if not ready:
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


def _blocked_attempt(status: str, *, run_id: str = "", **fields: Any) -> dict[str, Any]:
    packet = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "acceptance_run_id": run_id,
        "production_worker_complete": False,
        "full_market_worker_runtime": False,
        "celery_redis_runtime": False,
        "candidate_radar_production_replacement": False,
        "global_candidate_cache_overwritten": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
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
    import pandas as pd

    store = SQLiteMetaStore(SQLITE_META_PATH)
    previous_current = _read_packet_no_init(SQLITE_META_PATH, PACKET_KEY)
    previous_last_good = _read_packet_no_init(SQLITE_META_PATH, LAST_GOOD_PACKET_KEY)
    previous_pointer = _pointer_snapshot(PARQUET_ROOT, RESULT_DATASET, "current")
    previous_last_good_pointer = _pointer_snapshot(PARQUET_ROOT, RESULT_DATASET, "last_good")
    output_hash = _canonical_digest(result_rows)
    task_ids = [str(row.get("worker_task_id") or "") for row in checkpoint.get("successful_batches") or []]
    celery_ids = [str(row.get("celery_task_id") or "") for row in checkpoint.get("successful_batches") or []]
    stage = {
        "schema_version": STAGE_SCHEMA_VERSION,
        "status": "full_market_worker_stage_ready_production_pending",
        "acceptance_run_id": run_id,
        "provider_scope_hash": universe.get("scope_hash"),
        "universe_digest": universe.get("universe_digest"),
        "universe_count": universe.get("universe_count"),
        "validated_trade_date": universe.get("validated_trade_date"),
        "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
        "result_output_hash": output_hash,
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
        return _blocked_attempt("full_market_worker_stage_sqlite_readback_failed", run_id=run_id)

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
            "universe_digest": universe.get("universe_digest"),
            "feature_contract_digest": FEATURE_CONTRACT_DIGEST,
            "result_output_hash": output_hash,
            "stage_binding_digest": stage.get("stage_binding_digest"),
            "synthetic_fixture": False,
            "contains_secret": False,
        },
    )
    if promotion.get("atomic_promoted") is not True:
        return _blocked_attempt("full_market_worker_parquet_stage_or_pointer_failed", run_id=run_id)
    current_pointer_payload = _pointer_snapshot(PARQUET_ROOT, RESULT_DATASET, "current")
    if not previous_pointer and not previous_last_good_pointer:
        try:
            first_last_good = dict(current_pointer_payload)
            first_last_good["pointer_kind"] = "last_good"
            first_last_good["preserved_at"] = _now_iso()
            _atomic_write_json(PARQUET_ROOT / RESULT_DATASET / "last_good.json", first_last_good)
        except Exception:
            _restore_pointer(PARQUET_ROOT, RESULT_DATASET, previous_pointer)
            return _blocked_attempt("full_market_worker_first_last_good_pointer_failed", run_id=run_id)
    packet = {
        "schema_version": SCHEMA_VERSION,
        "status": "full_market_worker_production_complete",
        "acceptance_run_id": run_id,
        "provider_current_key": PROVIDER_CURRENT_KEY,
        "provider_last_good_key": PROVIDER_LAST_GOOD_KEY,
        "provider_scope_hash": universe.get("scope_hash"),
        "universe_digest": universe.get("universe_digest"),
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
        "result_row_count": len(result_rows),
        "transport_attestation_digest": _canonical_digest(transport),
        "direct_provenance_complete": True,
        "production_worker_complete": True,
        "full_market_worker_runtime": True,
        "celery_redis_runtime": True,
        "candidate_radar_production_replacement": True,
        "global_candidate_cache_overwritten": False,
        "synthetic_fixture": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
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
    candidate_fact = validate_full_market_worker_production_fact(
        EVIDENCE_ROOT,
        _candidate_packet=pending_packet,
    )
    if not (
        pending_readback.get("production_binding_digest") == pending_packet["production_binding_digest"]
        and candidate_fact.get("ready") is True
    ):
        rollback_pointer = bool(
            _restore_pointer(PARQUET_ROOT, RESULT_DATASET, previous_pointer)
            and _restore_pointer(
                PARQUET_ROOT,
                RESULT_DATASET,
                previous_last_good_pointer,
                pointer="last_good",
            )
        )
        rollback_packets = _restore_packet(PACKET_KEY, previous_current)
        return _blocked_attempt(
            "full_market_worker_direct_candidate_validation_failed_rolled_back",
            run_id=run_id,
            pointer_rollback_verified=rollback_pointer,
            packet_rollback_verified=rollback_packets,
        )
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
        rollback_pointer = bool(
            _restore_pointer(PARQUET_ROOT, RESULT_DATASET, previous_pointer)
            and _restore_pointer(
                PARQUET_ROOT,
                RESULT_DATASET,
                previous_last_good_pointer,
                pointer="last_good",
            )
        )
        rollback_packets = _restore_packet(PACKET_KEY, previous_current)
        return _blocked_attempt(
            "full_market_worker_last_good_pointer_promotion_failed_rolled_back",
            run_id=run_id,
            pointer_rollback_verified=rollback_pointer,
            packet_rollback_verified=rollback_packets,
        )
    try:
        store.write_packet(PACKET_KEY, final_packet)
        store.write_packet(LAST_GOOD_PACKET_KEY, final_packet)
        persisted = store.read_packet(PACKET_KEY) or {}
        persisted_good = store.read_packet(LAST_GOOD_PACKET_KEY) or {}
    except Exception:
        persisted, persisted_good = {}, {}
    fact = validate_full_market_worker_production_fact(EVIDENCE_ROOT)
    if not (
        persisted.get("production_binding_digest") == final_packet["production_binding_digest"]
        and persisted_good.get("production_binding_digest") == final_packet["production_binding_digest"]
        and fact.get("ready") is True
    ):
        rollback_pointer = bool(
            _restore_pointer(PARQUET_ROOT, RESULT_DATASET, previous_pointer)
            and _restore_pointer(
                PARQUET_ROOT,
                RESULT_DATASET,
                previous_last_good_pointer,
                pointer="last_good",
            )
        )
        rollback_packets = bool(
            _restore_packet(PACKET_KEY, previous_current)
            and _restore_packet(LAST_GOOD_PACKET_KEY, previous_last_good)
        )
        return _blocked_attempt(
            "full_market_worker_final_readback_failed_rolled_back",
            run_id=run_id,
            pointer_rollback_verified=rollback_pointer,
            packet_rollback_verified=rollback_packets,
        )
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


def validate_full_market_worker_production_fact(
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
        include_frames=False,
    )
    run_id = str(packet.get("acceptance_run_id") or "")
    production_binding = _canonical_digest(
        {key: value for key, value in packet.items() if key != "production_binding_digest"}
    ) if packet else ""
    packet_status_ready = bool(
        packet.get("status") == "full_market_worker_promotion_pending_direct_validation"
        and packet.get("production_worker_complete") is False
        and packet.get("full_market_worker_runtime") is False
        and packet.get("celery_redis_runtime") is False
        and packet.get("candidate_radar_production_replacement") is False
    ) if candidate_mode else bool(
        packet.get("status") == "full_market_worker_production_complete"
        and packet.get("production_worker_complete") is True
        and packet.get("full_market_worker_runtime") is True
        and packet.get("celery_redis_runtime") is True
        and packet.get("candidate_radar_production_replacement") is True
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
        and packet.get("universe_digest") == universe.get("universe_digest")
        and _integer(packet.get("universe_count")) == universe.get("universe_count")
        and packet.get("validated_trade_date") == universe.get("validated_trade_date")
        and packet.get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and packet.get("feature_contract") == FEATURE_CONTRACT
        and packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("contains_secret") is False
    )

    transport = _read_packet_no_init(db_path, str(packet.get("transport_key") or ""))
    transport_ready = bool(
        transport.get("schema_version") == TRANSPORT_SCHEMA_VERSION
        and transport.get("status") == "external_redis_celery_direct_attested"
        and transport.get("acceptance_run_id") == run_id
        and transport.get("broker_direct_ping") is True
        and transport.get("backend_roundtrip_verified") is True
        and transport.get("registered_task_verified") is True
        and transport.get("registered_queue_verified") is True
        and _integer(transport.get("eligible_worker_count")) > 0
        and transport.get("task_always_eager") is False
        and transport.get("synthetic_fixture") is False
        and _canonical_digest(transport) == packet.get("transport_attestation_digest")
        and _ledger_sanitized(transport)
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
        and checkpoint.get("universe_digest") == universe.get("universe_digest")
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
                "symbols": symbols,
                "batch_symbol_hash": _canonical_digest(symbols),
            }
            task = _read_task_no_init(db_path, str(success.get("worker_task_id") or ""))
            valid, _rows = _validate_worker_task(task, batch=batch, universe=universe)
            if (
                duplicates
                or invalid
                or not (MIN_BATCH_SIZE <= len(symbols) <= MAX_BATCH_SIZE)
                or spec.get("batch_symbol_hash") != _canonical_digest(symbols)
                or not valid
            ):
                tasks_ready = False
                break
            seen_symbols.extend(symbols)
            celery_ids.append(str(success.get("celery_task_id") or ""))
            worker_ids.append(str(success.get("worker_task_id") or ""))
        if sorted(seen_symbols) != universe.get("symbols") or len(set(seen_symbols)) != len(seen_symbols):
            tasks_ready = False
        if celery_ids != packet.get("celery_task_ids") or worker_ids != packet.get("worker_task_ids"):
            tasks_ready = False

    stage = _read_packet_no_init(db_path, str(packet.get("stage_key") or ""))
    stage_binding = _canonical_digest(
        {key: value for key, value in stage.items() if key != "stage_binding_digest"}
    ) if stage else ""
    stage_ready = bool(
        stage.get("schema_version") == STAGE_SCHEMA_VERSION
        and stage.get("status") == "full_market_worker_stage_ready_production_pending"
        and stage.get("acceptance_run_id") == run_id
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
        and pointer.get("lineage", {}).get("feature_contract_digest") == FEATURE_CONTRACT_DIGEST
        and pointer.get("lineage", {}).get("result_output_hash") == packet.get("result_output_hash")
        and result_symbols == universe.get("symbols")
        and not result_duplicates
        and not result_invalid
        and len(result_rows) == universe.get("universe_count")
        and _canonical_digest(result_rows) == packet.get("result_output_hash")
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
    checks = {
        "upstream_provider_current_last_good_and_artifacts": universe.get("ready") is True,
        "production_packets_direct_binding": packets_ready,
        "redis_celery_direct_transport_attestation": transport_ready,
        "durable_coordinator_checkpoint_resume_state": checkpoint_ready,
        "bound_worker_task_outputs": tasks_ready,
        "sqlite_stage_manifest": stage_ready,
        "atomic_parquet_pointer_and_scored_rows": result_ready,
    }
    blockers = [key for key, passed in checks.items() if not passed]
    ready = not blockers
    return {
        "ready": ready,
        "status": "full_market_worker_production_fact_verified" if ready else "full_market_worker_production_fact_blocked",
        "full_market_worker_runtime": ready,
        "celery_redis_runtime": ready,
        "candidate_radar_production_replacement": ready,
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


def run_full_market_worker_production_acceptance(payload: Any = None) -> dict[str, Any]:
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    if payload_map.get("operator_approved") is not True:
        return _blocked_attempt(
            "full_market_worker_production_blocked_operator_approval_required",
            dispatch_count=0,
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
        include_frames=False,
    )
    if universe.get("ready") is not True:
        return _blocked_attempt(
            "authoritative_full_market_universe_missing_or_below_threshold",
            dispatch_count=0,
            universe_count=universe.get("universe_count", 0),
            minimum_universe_size=minimum,
            blockers=universe.get("blockers", []),
        )

    requested_resume = str(payload_map.get("resume_run_id") or "").strip()
    run_id = requested_resume or uuid.uuid4().hex[:20]
    if not re.fullmatch(r"[0-9a-zA-Z-]{8,64}", run_id):
        return _blocked_attempt("full_market_worker_resume_run_id_invalid", dispatch_count=0)
    if not _acquire_lock(run_id):
        return _blocked_attempt(
            "full_market_worker_coordinator_lock_held",
            run_id=run_id,
            dispatch_count=0,
        )
    try:
        app = _load_celery_app()
        transport = _transport_probe(app, acceptance_run_id=run_id)
        if transport.get("ready") is not True:
            return _blocked_attempt(
                "full_market_worker_production_blocked_real_transport_required",
                run_id=run_id,
                dispatch_count=0,
                transport_status=transport.get("status"),
            )
        store = SQLiteMetaStore(SQLITE_META_PATH)
        store.write_packet(_transport_key(run_id), transport)
        transport_readback = store.read_packet(_transport_key(run_id)) or {}
        if _canonical_digest(transport_readback) != _canonical_digest(transport):
            return _blocked_attempt(
                "full_market_worker_transport_attestation_readback_failed",
                run_id=run_id,
                dispatch_count=0,
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
                universe=universe,
                batches=batches,
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
            timeout_seconds=timeout,
            prior_successes=prior_successes,
        )
        if len(successes) != len(batches):
            _write_checkpoint(
                run_id=run_id,
                universe=universe,
                batches=batches,
                successes=successes,
                status="partial_failure_resume_available",
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
        )
        result_rows = _result_rows_from_batches(successes, universe=universe)
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
        return _promote_candidate_results(
            run_id=run_id,
            universe=universe,
            transport=transport,
            checkpoint=checkpoint,
            result_rows=result_rows,
        )
    finally:
        _release_lock(run_id)
