from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from storage import parquet_store
from storage.sqlite_meta import SQLiteMetaStore

from . import external_production_consumer_service, task_service
from .full_market_industry_service import (
    INDUSTRY_BINDING_DIGEST_KEYS,
    INDUSTRY_ROOT_RELATIVE,
    validate_full_market_industry_membership,
)
from .tushare_production_store import (
    REQUIRED_SESSIONS,
    validate_tushare_full_market_production_version,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
SQLITE_META_PATH = EVIDENCE_ROOT / "meta.sqlite"

COORDINATOR_TASK_TYPE = "run_full_market_factor_radar_map_reduce_request"
FACTOR_TASK_TYPE = "run_factor_full_market_map_reduce_request"
RADAR_TASK_TYPE = "run_candidate_radar_authoritative_map_reduce_request"

COORDINATOR_PACKET_KEY = "command_center_3_full_market_factor_radar_map_reduce_request"
FACTOR_REQUEST_PACKET_KEY = "command_center_3_factor_full_market_map_reduce_request"
RADAR_REQUEST_PACKET_KEY = "command_center_3_candidate_radar_map_reduce_request"

FACTOR_TARGET_PACKET_KEY = "command_center_3_factor_full_market_worker_production_acceptance"
FACTOR_TARGET_DATASET = "full_market_factor_research_results"
RADAR_TARGET_PACKET_KEY = "command_center_3_candidate_radar_cache"
RADAR_TARGET_DATASET = "full_market_candidate_radar_results"

SCHEMA_VERSION = "full_market_factor_radar_map_reduce_request.v2"
CHILD_SCHEMA_VERSION = "full_market_map_reduce_child_request.v2"
BUNDLE_SCHEMA_VERSION = "full_market_factor_radar_request_bundle.v2"
EXTERNAL_LINEAGE_BLOCKER = "external_trusted_production_lineage_runner_unavailable"
MINIMUM_UNIVERSE_SIZE = 3000
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_UUID4_HEX = re.compile(r"^[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}$")
FACTOR_EXECUTION_TASK_TYPE = "execute_full_market_factor_research"
FACTOR_PACKET_SCHEMA_VERSION = "factor_full_market_worker_production_acceptance.v2"
FACTOR_EXECUTION_JOURNAL_SCHEMA_VERSION = "factor_full_market_execution_journal.v1"
FACTOR_EXECUTION_JOURNAL_NAME = "execution_journal.json"
_FACTOR_EXECUTION_THREAD_LOCK = threading.Lock()
FACTOR_REQUIRED_RESULT_COLUMNS = (
    "ts_code",
    "data_date",
    "cross_sectional_rank",
    "cross_sectional_zscore",
    "industry_code",
    "industry_neutral_score",
    "market_cap",
    "size_neutral_score",
    "combined_factor_score",
    "provider_version_digest",
    "industry_pointer_digest",
    "factor_batch_input_digest",
    "source_dataset_digest",
    "pit_validated",
    "research_only",
    "does_not_execute_trades",
)


FACTOR_OUTPUT_CONTRACT: dict[str, Any] = {
    "schema_version": "factor_full_market_map_reduce_output.v1",
    "output_kind": "factor_full_market_cross_sectional_research",
    "target_dataset": FACTOR_TARGET_DATASET,
    "target_packet_key": FACTOR_TARGET_PACKET_KEY,
    "required_metrics": [
        "cross_sectional_rank",
        "cross_sectional_zscore",
        "industry_neutral_score",
        "size_neutral_score",
        "combined_factor_score",
    ],
    "requires_effective_dated_industry_membership": True,
    "requires_bound_full_market_batch_input_digest": True,
    "requires_full_universe_symbol_coverage": True,
    "candidate_radar_rows_are_not_factor_rows": True,
    "research_only": True,
    "does_not_execute_trades": True,
}

RADAR_OUTPUT_CONTRACT: dict[str, Any] = {
    "schema_version": "candidate_radar_authoritative_map_reduce_output.v1",
    "output_kind": "candidate_radar_full_market_deep_scan",
    "target_dataset": RADAR_TARGET_DATASET,
    "target_packet_key": RADAR_TARGET_PACKET_KEY,
    "required_fields": [
        "ts_code",
        "data_date",
        "deep_scan_score",
        "rough_score",
        "risk_score",
        "trigger_conditions_json",
        "invalid_conditions_json",
    ],
    "requires_full_universe_symbol_coverage": True,
    "requires_authoritative_candidate_cache_write": True,
    "requires_bound_full_market_batch_input_digest": True,
    "factor_rows_are_not_candidate_radar_rows": True,
    "candidate_is_not_buy_instruction": True,
    "research_only": True,
    "does_not_execute_trades": True,
}


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


FACTOR_OUTPUT_CONTRACT_DIGEST = _digest(FACTOR_OUTPUT_CONTRACT)
RADAR_OUTPUT_CONTRACT_DIGEST = _digest(RADAR_OUTPUT_CONTRACT)


def _current_head_full() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    value = result.stdout.strip().lower() if result.returncode == 0 else ""
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else ""


def _safe_digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if _HEX_64.fullmatch(text) else ""


def _strict_bool(value: Any) -> bool:
    return value is True


def _safe_evidence_root(value: Path) -> bool:
    """Reject redirected production roots and writable-path symlink attacks."""

    root = Path(value)
    if not root.exists() or not root.is_dir() or root.is_symlink():
        return False
    for relative in (
        Path("meta.sqlite"),
        Path("parquet"),
        Path("parquet") / FACTOR_TARGET_DATASET,
        Path("parquet") / FACTOR_TARGET_DATASET / "versions",
        Path("parquet") / FACTOR_TARGET_DATASET / "current.json",
        Path("parquet") / FACTOR_TARGET_DATASET / "last_good.json",
        Path("parquet") / FACTOR_TARGET_DATASET / "manifest.json",
        Path("parquet") / FACTOR_TARGET_DATASET / FACTOR_EXECUTION_JOURNAL_NAME,
        Path(".factor_execution.lock"),
        INDUSTRY_ROOT_RELATIVE,
    ):
        candidate = root / relative
        if candidate.exists() and candidate.is_symlink():
            return False
    return True


def _repository_state() -> dict[str, Any]:
    head = _current_head_full()
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "status", "--porcelain", "--untracked-files=no"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"head_full": head, "clean": False}
    return {"head_full": head, "clean": result.returncode == 0 and not result.stdout.strip()}


def _read_json_regular(path: Path, *, root: Path) -> dict[str, Any]:
    try:
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        if path.is_symlink() or not resolved.is_relative_to(resolved_root) or not resolved.is_file():
            return {}
        raw = resolved.read_bytes()
        if len(raw) > 64 * 1024 * 1024:
            return {}
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return dict(value) if type(value) is dict else {}


def _industry_rows(
    evidence_root: Path,
    *,
    symbols: list[str],
    validated_trade_date: str,
    expected_artifact_sha256: str,
) -> tuple[list[dict[str, Any]], str]:
    industry_root = evidence_root / INDUSTRY_ROOT_RELATIVE
    pointer = _read_json_regular(industry_root / "pointer.json", root=industry_root)
    manifest_file = pointer.get("manifest_file")
    if type(manifest_file) is not str or not manifest_file:
        return [], ""
    manifest = _read_json_regular(industry_root / manifest_file, root=industry_root)
    artifact_file = manifest.get("artifact_file")
    if type(artifact_file) is not str or not artifact_file:
        return [], ""
    artifact_path = industry_root / artifact_file
    artifact = _read_json_regular(artifact_path, root=industry_root)
    try:
        artifact_sha256 = hashlib.sha256(artifact_path.resolve(strict=True).read_bytes()).hexdigest()
    except Exception:
        return [], ""
    raw_rows = artifact.get("rows")
    if artifact_sha256 != expected_artifact_sha256 or type(raw_rows) is not list:
        return [], ""
    active: dict[str, dict[str, Any]] = {}
    for raw in raw_rows:
        if type(raw) is not dict or set(raw) != {
            "effective_from",
            "effective_to",
            "industry_code",
            "source_api",
            "ts_code",
        }:
            return [], ""
        symbol = raw.get("ts_code")
        start = raw.get("effective_from")
        end = raw.get("effective_to")
        industry = raw.get("industry_code")
        if not (
            type(symbol) is str
            and type(start) is str
            and (end is None or type(end) is str)
            and type(industry) is str
            and industry
        ):
            return [], ""
        if start <= validated_trade_date and (not end or validated_trade_date < end):
            if symbol in active:
                return [], ""
            active[symbol] = dict(raw)
    if sorted(active) != symbols:
        return [], ""
    rows = [active[symbol] for symbol in symbols]
    return rows, _digest(rows)


def _frame_records(frame: Any, *, symbols: list[str]) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True) or "ts_code" not in frame.columns:
        return []
    subset = frame[frame["ts_code"].astype(str).str.upper().isin(set(symbols))].copy()
    columns = sorted(str(column) for column in subset.columns)
    order = [column for column in ("ts_code", "trade_date", "cal_date") if column in columns]
    subset = subset[columns].sort_values(order or columns, kind="stable").reset_index(drop=True)
    subset = subset.where(subset.notna(), None)
    return [dict(row) for row in subset.to_dict(orient="records")]


def _worker_trust_binding(
    evidence_root: Path,
    *,
    head_full: str,
    attestation_id: str,
    worker_run_id: str,
) -> dict[str, Any]:
    verified = external_production_consumer_service.validate_consumer(
        "worker", evidence_root=evidence_root
    )
    current = (
        dict(verified.get("current_pointer"))
        if type(verified.get("current_pointer")) is dict
        else {}
    )
    packet = current.get("consumer_packet")
    packet = dict(packet) if type(packet) is dict else {}
    source = packet.get("source_binding")
    source = dict(source) if type(source) is dict else {}
    claims = packet.get("claims")
    claims = dict(claims) if type(claims) is dict else {}
    ready = bool(
        verified.get("ready") is True
        and verified.get("production_trusted") is True
        and verified.get("snapshot_rollback_resistant") is True
        and verified.get("head_full") == head_full
        and current.get("attestation_id") == attestation_id
        and packet.get("attestation_id") == attestation_id
        and source.get("head_full") == head_full
        and source.get("dataset") == "full_market_candidate_radar_results"
        and claims.get("worker_run_id") == worker_run_id
        and type(claims.get("eligible_worker_count")) is int
        and claims.get("eligible_worker_count") > 0
        and type(claims.get("batch_count")) is int
        and claims.get("batch_count") > 0
        and type(claims.get("row_count")) is int
        and claims.get("row_count") >= MINIMUM_UNIVERSE_SIZE
        and _safe_digest(claims.get("provider_version_digest"))
        and _safe_digest(claims.get("universe_digest"))
        and re.fullmatch(r"[0-9]{8}", str(claims.get("validated_trade_date") or ""))
        and claims.get("does_not_execute_trades") is True
        and _safe_digest(source.get("artifact_digest"))
    )
    return {
        "ready": ready,
        "attestation_id": attestation_id if ready else "",
        "artifact_digest": source.get("artifact_digest") if ready else "",
        "generation": source.get("generation") if ready else "",
        "scope_hash": source.get("scope_hash") if ready else "",
        "claims": claims if ready else {},
    }


def _zscore(series: Any) -> Any:
    mean = float(series.mean())
    scale = float(series.std(ddof=0))
    if not math.isfinite(scale) or scale <= 1e-12:
        raise ValueError("factor_cross_sectional_variance_missing")
    return (series - mean) / scale


def _compute_factor_rows(
    frames: Mapping[str, Any],
    *,
    symbols: list[str],
    validated_trade_date: str,
    industry_rows: list[dict[str, Any]],
    provider_version_digest: str,
    industry_pointer_digest: str,
    factor_batch_input_digest: str,
    source_dataset_digest: str,
) -> list[dict[str, Any]]:
    import numpy as np
    import pandas as pd

    daily = frames.get("daily")
    basic = frames.get("daily_basic")
    if daily is None or basic is None:
        return []
    daily = daily.copy()
    basic = basic.copy()
    for frame in (daily, basic):
        if "ts_code" not in frame.columns or "trade_date" not in frame.columns:
            return []
        frame["ts_code"] = frame["ts_code"].astype(str).str.upper()
        frame["trade_date"] = frame["trade_date"].astype(str).str.replace("-", "", regex=False)
        frame.drop(frame[frame["trade_date"] > validated_trade_date].index, inplace=True)
    daily = daily[daily["ts_code"].isin(symbols)].sort_values(["ts_code", "trade_date"])
    basic = basic[basic["ts_code"].isin(symbols)].sort_values(["ts_code", "trade_date"])
    if not {"close", "amount"}.issubset(daily.columns) or not {"total_mv", "pb"}.issubset(basic.columns):
        return []
    records: list[dict[str, Any]] = []
    industry_by_symbol = {str(row["ts_code"]): row for row in industry_rows}
    for symbol in symbols:
        daily_rows = daily[daily["ts_code"] == symbol]
        basic_rows = basic[basic["ts_code"] == symbol]
        if len(daily_rows) < 21 or basic_rows.empty:
            return []
        closes = pd.to_numeric(daily_rows["close"], errors="coerce")
        amounts = pd.to_numeric(daily_rows["amount"], errors="coerce")
        latest_basic = basic_rows.iloc[-1]
        close_now = float(closes.iloc[-1])
        close_20 = float(closes.iloc[-21])
        market_cap = float(pd.to_numeric(pd.Series([latest_basic["total_mv"]]), errors="coerce").iloc[0])
        pb = float(pd.to_numeric(pd.Series([latest_basic["pb"]]), errors="coerce").iloc[0])
        amount_20 = float(amounts.tail(20).mean())
        if not all(math.isfinite(value) and value > 0 for value in (close_now, close_20, market_cap, pb, amount_20)):
            return []
        membership = industry_by_symbol.get(symbol) or {}
        records.append(
            {
                "ts_code": symbol,
                "data_date": str(daily_rows.iloc[-1]["trade_date"]),
                "momentum_20d": close_now / close_20 - 1.0,
                "value_signal": -math.log(pb),
                "liquidity_signal": math.log(amount_20),
                "market_cap": market_cap,
                "industry_code": str(membership.get("industry_code") or ""),
                "industry_effective_from": str(membership.get("effective_from") or ""),
                "industry_effective_to": membership.get("effective_to"),
            }
        )
    frame = pd.DataFrame(records)
    if len(frame) != len(symbols) or sorted(frame["ts_code"].tolist()) != symbols:
        return []
    raw = (
        0.55 * _zscore(frame["momentum_20d"])
        + 0.25 * _zscore(frame["value_signal"])
        + 0.20 * _zscore(frame["liquidity_signal"])
    )
    frame["cross_sectional_zscore"] = _zscore(raw)
    frame["cross_sectional_rank"] = raw.rank(method="first", ascending=False).astype(int)
    frame["industry_neutral_score"] = frame["cross_sectional_zscore"] - frame.groupby(
        "industry_code"
    )["cross_sectional_zscore"].transform("mean")
    log_cap = np.log(frame["market_cap"].astype(float).to_numpy())
    centered_size = log_cap - float(log_cap.mean())
    industry_neutral = frame["industry_neutral_score"].astype(float).to_numpy()
    denominator = float(np.dot(centered_size, centered_size))
    if denominator <= 1e-12:
        return []
    residual = industry_neutral - centered_size * float(np.dot(centered_size, industry_neutral) / denominator)
    # A second projection removes floating-point residue from the first pass.
    residual = residual - centered_size * float(np.dot(centered_size, residual) / denominator)
    if float(np.std(residual)) <= 1e-12:
        return []
    frame["size_neutral_score"] = residual
    frame["combined_factor_score"] = (
        0.4 * frame["cross_sectional_zscore"]
        + 0.3 * frame["industry_neutral_score"]
        + 0.3 * frame["size_neutral_score"]
    )
    frame["provider_version_digest"] = provider_version_digest
    frame["industry_pointer_digest"] = industry_pointer_digest
    frame["factor_batch_input_digest"] = factor_batch_input_digest
    frame["source_dataset_digest"] = source_dataset_digest
    frame["pit_validated"] = True
    frame["research_only"] = True
    frame["does_not_execute_trades"] = True
    frame = frame.sort_values("ts_code", kind="stable").reset_index(drop=True)
    return [dict(row) for row in frame.to_dict(orient="records")]


def _factor_result_rows_bound(
    rows: list[dict[str, Any]],
    *,
    symbols: list[str],
    validated_trade_date: str,
    provider_version_digest: str,
    industry_pointer_digest: str,
    factor_batch_input_digest: str,
    source_dataset_digest: str,
) -> bool:
    if len(rows) != len(symbols):
        return False
    if sorted(str(row.get("ts_code") or "") for row in rows) != symbols:
        return False
    return all(
        set(FACTOR_REQUIRED_RESULT_COLUMNS).issubset(row)
        and row.get("data_date") == validated_trade_date
        and row.get("provider_version_digest") == provider_version_digest
        and row.get("industry_pointer_digest") == industry_pointer_digest
        and row.get("factor_batch_input_digest") == factor_batch_input_digest
        and row.get("source_dataset_digest") == source_dataset_digest
        and row.get("pit_validated") is True
        and row.get("research_only") is True
        and row.get("does_not_execute_trades") is True
        for row in rows
    )


def _snapshot_files(paths: list[Path]) -> dict[Path, bytes | None]:
    return {path: path.read_bytes() if path.is_file() and not path.is_symlink() else None for path in paths}


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _restore_files(snapshot: Mapping[Path, bytes | None]) -> None:
    for path, content in snapshot.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_bytes(path, content)


@contextmanager
def _factor_execution_lock(root: Path):
    lock_path = root / ".factor_execution.lock"
    descriptor = -1
    _FACTOR_EXECUTION_THREAD_LOCK.acquire()
    try:
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        if lock_path.is_symlink() or not lock_path.is_file():
            raise RuntimeError("factor_execution_lock_path_unsafe")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        if descriptor >= 0:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
        _FACTOR_EXECUTION_THREAD_LOCK.release()


def _factor_execution_journal_path(root: Path) -> Path:
    return root / "parquet" / FACTOR_TARGET_DATASET / FACTOR_EXECUTION_JOURNAL_NAME


def _journal_snapshot(snapshot: Mapping[Path, bytes | None]) -> dict[str, str | None]:
    return {
        path.name: base64.b64encode(content).decode("ascii") if content is not None else None
        for path, content in snapshot.items()
    }


def _decode_journal_snapshot(
    dataset_root: Path, value: Any
) -> dict[Path, bytes | None] | None:
    expected = {"current.json", "last_good.json", "manifest.json"}
    if type(value) is not dict or set(value) != expected:
        return None
    decoded: dict[Path, bytes | None] = {}
    try:
        for name in sorted(expected):
            encoded = value[name]
            if encoded is None:
                decoded[dataset_root / name] = None
                continue
            if type(encoded) is not str or len(encoded) > 128 * 1024 * 1024:
                return None
            content = base64.b64decode(encoded, validate=True)
            if len(content) > 64 * 1024 * 1024:
                return None
            decoded[dataset_root / name] = content
    except Exception:
        return None
    return decoded


def _write_factor_execution_journal(root: Path, payload: Mapping[str, Any]) -> None:
    journal_path = _factor_execution_journal_path(root)
    if journal_path.exists() and journal_path.is_symlink():
        raise RuntimeError("factor_execution_journal_path_unsafe")
    _atomic_bytes(
        journal_path,
        json.dumps(
            dict(payload),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
    )


def _recover_factor_execution(root: Path, db_path: Path) -> dict[str, Any]:
    journal_path = _factor_execution_journal_path(root)
    if not journal_path.exists():
        return {"ready": True, "status": "factor_execution_recovery_not_needed"}
    if journal_path.is_symlink() or not journal_path.is_file():
        return {"ready": False, "status": "factor_execution_journal_unsafe"}
    journal = _read_json_regular(journal_path, root=journal_path.parent)
    snapshot_value = journal.get("snapshot")
    snapshot = _decode_journal_snapshot(journal_path.parent, snapshot_value)
    expected_snapshot_digest = _digest(snapshot_value) if type(snapshot_value) is dict else ""
    run_id = str(journal.get("acceptance_run_id") or "")
    version_id = f"fmf-{run_id}"
    artifact_path = journal_path.parent / "versions" / f"{version_id}.parquet"
    if not (
        journal.get("schema_version") == FACTOR_EXECUTION_JOURNAL_SCHEMA_VERSION
        and journal.get("state") in {"prepared", "parquet_promoted", "sqlite_committed"}
        and _HEX_40.fullmatch(str(journal.get("head_full") or ""))
        and _UUID4_HEX.fullmatch(run_id)
        and journal.get("version_id") == version_id
        and type(journal.get("artifact_existed_before")) is bool
        and snapshot is not None
        and journal.get("snapshot_digest") == expected_snapshot_digest
        and (not artifact_path.exists() or not artifact_path.is_symlink())
    ):
        return {"ready": False, "status": "factor_execution_journal_invalid"}

    packet = {}
    task = {}
    if db_path.exists() and not db_path.is_symlink():
        try:
            store = SQLiteMetaStore(db_path, read_only=True)
            packet = store.read_packet(FACTOR_TARGET_PACKET_KEY) or {}
            task = store.read_task_status(run_id) or {}
        except Exception:
            packet = {}
            task = {}
    packet_digest = _digest(packet) if packet else ""
    task_digest = _digest(task) if task else ""
    current_pointer = parquet_store.versioned_dataset_pointer(
        root=root / "parquet", name=FACTOR_TARGET_DATASET, pointer="current"
    )
    committed = bool(
        journal.get("state") in {"parquet_promoted", "sqlite_committed"}
        and _safe_digest(journal.get("target_packet_digest")) == packet_digest
        and _safe_digest(journal.get("target_task_digest")) == task_digest
        and packet.get("result_version_id") == version_id
        and packet.get("result_artifact_sha256")
        == journal.get("target_artifact_sha256")
        and current_pointer.get("status") == "ready"
        and current_pointer.get("version_id") == version_id
        and current_pointer.get("artifact_sha256")
        == journal.get("target_artifact_sha256")
        and current_pointer.get("artifact_sha256_matches") is True
    )
    if committed:
        journal_path.unlink(missing_ok=True)
        return {"ready": True, "status": "factor_execution_committed_recovered"}
    if journal.get("state") == "sqlite_committed":
        return {"ready": False, "status": "factor_execution_committed_state_mismatch"}
    _restore_files(snapshot)
    if artifact_path.is_file() and journal.get("artifact_existed_before") is False:
        artifact_path.unlink(missing_ok=True)
    journal_path.unlink(missing_ok=True)
    return {"ready": True, "status": "factor_execution_precommit_rolled_back"}


def execute_full_market_factor_research(
    payload: Any,
    *,
    evidence_root: Path | None = None,
    meta_path: Path | None = None,
) -> dict[str, Any]:
    root = Path(evidence_root or EVIDENCE_ROOT)
    try:
        if not _safe_evidence_root(root):
            raise RuntimeError("factor_execution_root_unsafe")
        with _factor_execution_lock(root):
            return _execute_full_market_factor_research_locked(
                payload,
                evidence_root=root,
                meta_path=meta_path,
            )
    except Exception as exc:
        return {
            "ready": False,
            "status": "factor_full_market_executor_lock_or_recovery_blocked",
            "blockers": [type(exc).__name__],
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }


def _execute_full_market_factor_research_locked(
    payload: Any,
    *,
    evidence_root: Path | None = None,
    meta_path: Path | None = None,
) -> dict[str, Any]:
    """Execute the current-head Factor reduce from already verified local inputs.

    This is a POST-only service entry point.  It never calls a provider or starts
    a worker; it requires the externally trusted worker consumer from the same
    HEAD and reads the immutable provider/industry artifacts from disk.
    """

    payload_map = dict(payload) if type(payload) is dict else {}
    allowed = {
        "approved_by_user",
        "head_full",
        "acceptance_run_id",
        "request_bundle_id",
        "factor_task_id",
        "worker_attestation_id",
        "worker_run_id",
    }
    root = Path(evidence_root or EVIDENCE_ROOT)
    db_path = Path(meta_path or (root / "meta.sqlite"))
    before = _repository_state()
    blockers: list[str] = []
    if set(payload_map) != allowed:
        blockers.append("factor_executor_payload_schema_not_exact")
    if not _strict_bool(payload_map.get("approved_by_user")):
        blockers.append("factor_executor_explicit_approval_missing")
    if (
        not _safe_evidence_root(root)
        or db_path.is_symlink()
        or db_path.resolve(strict=False)
        != (root / "meta.sqlite").resolve(strict=False)
    ):
        blockers.append("factor_executor_evidence_root_unsafe")
    head_full = str(payload_map.get("head_full") or "").lower()
    if not _HEX_40.fullmatch(head_full) or head_full != before.get("head_full"):
        blockers.append("factor_executor_current_head_mismatch")
    if before.get("clean") is not True:
        blockers.append("factor_executor_worktree_not_clean")
    run_id = str(payload_map.get("acceptance_run_id") or "").lower()
    if not _UUID4_HEX.fullmatch(run_id):
        blockers.append("factor_executor_acceptance_run_id_invalid")
    for key in ("request_bundle_id", "worker_attestation_id"):
        if not _safe_digest(payload_map.get(key)):
            blockers.append(f"factor_executor_{key}_invalid")
    factor_task_id = str(payload_map.get("factor_task_id") or "")
    if not re.fullmatch(r"local-[0-9a-f]{12}", factor_task_id):
        blockers.append("factor_executor_factor_task_id_invalid")
    worker_run_id = str(payload_map.get("worker_run_id") or "").lower()
    if not _UUID4_HEX.fullmatch(worker_run_id):
        blockers.append("factor_executor_worker_run_id_invalid")
    if blockers:
        return {
            "ready": False,
            "status": "factor_full_market_executor_blocked",
            "blockers": blockers,
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }

    recovery = _recover_factor_execution(root, db_path)
    if recovery.get("ready") is not True:
        return {
            "ready": False,
            "status": "factor_full_market_executor_recovery_blocked",
            "blockers": [str(recovery.get("status") or "factor_execution_recovery_failed")],
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }

    try:
        request_store = SQLiteMetaStore(db_path, read_only=True)
        factor_request = request_store.read_packet(FACTOR_REQUEST_PACKET_KEY) or {}
        radar_request = request_store.read_packet(RADAR_REQUEST_PACKET_KEY) or {}
    except Exception:
        factor_request = {}
        radar_request = {}
    if not (
        factor_request.get("head_full") == head_full
        and factor_request.get("request_bundle_id") == payload_map["request_bundle_id"]
        and factor_request.get("task_id") == factor_task_id
        and factor_request.get("target_dataset") == FACTOR_TARGET_DATASET
        and factor_request.get("output_contract_digest") == FACTOR_OUTPUT_CONTRACT_DIGEST
    ):
        blockers.append("factor_executor_request_packet_binding_invalid")
    independence = validate_independent_output_requests(
        factor_request, radar_request, evidence_root=root
    )
    if independence.get("ready") is not True:
        blockers.append("factor_executor_request_bundle_invalid")
    worker_trust = _worker_trust_binding(
        root,
        head_full=head_full,
        attestation_id=str(payload_map["worker_attestation_id"]),
        worker_run_id=worker_run_id,
    )
    if worker_trust.get("ready") is not True:
        blockers.append("factor_executor_external_worker_trust_missing_or_mismatched")
    universe = validate_tushare_full_market_production_version(root, include_frames=True)
    symbols = sorted(str(item).upper() for item in universe.get("symbols") or [])
    if not (
        universe.get("ready") is True
        and len(symbols) >= MINIMUM_UNIVERSE_SIZE
        and len(symbols) == len(set(symbols)) == universe.get("universe_count")
        and _digest(symbols) == universe.get("universe_digest")
        and _safe_digest(universe.get("version_digest"))
    ):
        blockers.append("factor_executor_authoritative_provider_input_invalid")
    if not (
        worker_trust.get("scope_hash") == universe.get("scope_hash")
        and type(worker_trust.get("claims", {}).get("row_count")) is int
        and worker_trust.get("claims", {}).get("row_count") == len(symbols)
        and worker_trust.get("claims", {}).get("provider_version_digest")
        == universe.get("version_digest")
        and worker_trust.get("claims", {}).get("universe_digest")
        == universe.get("universe_digest")
        and worker_trust.get("claims", {}).get("validated_trade_date")
        == universe.get("validated_trade_date")
    ):
        blockers.append("factor_executor_worker_provider_scope_or_count_mismatch")
    industry = validate_full_market_industry_membership(
        root,
        expected_symbols=symbols,
        expected_universe_digest=universe.get("universe_digest"),
        expected_validated_trade_date=universe.get("validated_trade_date"),
    )
    industry_rows, industry_rows_digest = _industry_rows(
        root,
        symbols=symbols,
        validated_trade_date=str(universe.get("validated_trade_date") or ""),
        expected_artifact_sha256=str(industry.get("artifact_sha256") or ""),
    )
    if industry.get("ready") is not True or not industry_rows_digest:
        blockers.append("factor_executor_authoritative_industry_input_invalid")
    frames = universe.get("frames") if type(universe.get("frames")) is dict else {}
    source_dataset_digest = _digest(
        {
            name: _frame_records(frames.get(name), symbols=symbols)
            for name in ("daily", "daily_basic")
        }
    )
    industry_binding = {
        "industry_scope_digest": industry.get("scope_digest"),
        "industry_source_version_digest": industry.get("source_version_digest"),
        "industry_artifact_sha256": industry.get("artifact_sha256"),
        "industry_manifest_digest": industry.get("manifest_digest"),
        "industry_pointer_digest": industry.get("pointer_digest"),
        "industry_semantic_evidence_sha256": industry.get("semantic_evidence_sha256"),
    }
    industry_input_digest = _digest(industry_binding)
    factor_batch_input_digest = _digest(
        {
            "provider_scope_hash": universe.get("scope_hash"),
            "provider_version_digest": universe.get("version_digest"),
            "universe_digest": universe.get("universe_digest"),
            "validated_trade_date": universe.get("validated_trade_date"),
            "symbols": symbols,
            "industry_binding": industry_binding,
            "industry_input_digest": industry_input_digest,
        }
    )
    if factor_request.get("factor_batch_input_digest") != factor_batch_input_digest:
        blockers.append("factor_executor_request_input_digest_mismatch")
    if blockers:
        return {
            "ready": False,
            "status": "factor_full_market_executor_blocked",
            "blockers": list(dict.fromkeys(blockers)),
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }

    rows = _compute_factor_rows(
        frames,
        symbols=symbols,
        validated_trade_date=str(universe.get("validated_trade_date")),
        industry_rows=industry_rows,
        provider_version_digest=str(universe.get("version_digest")),
        industry_pointer_digest=str(industry.get("pointer_digest")),
        factor_batch_input_digest=factor_batch_input_digest,
        source_dataset_digest=source_dataset_digest,
    )
    from . import full_market_worker_service as worker_contract

    output_hash = _digest(rows) if rows else ""
    metric_audit = worker_contract._factor_metric_validation_audit(
        rows,
        universe_digest=str(universe.get("universe_digest") or ""),
        result_output_hash=output_hash,
    )
    after_compute = _repository_state()
    if not (
        rows
        and _factor_result_rows_bound(
            rows,
            symbols=symbols,
            validated_trade_date=str(universe.get("validated_trade_date") or ""),
            provider_version_digest=str(universe.get("version_digest") or ""),
            industry_pointer_digest=str(industry.get("pointer_digest") or ""),
            factor_batch_input_digest=factor_batch_input_digest,
            source_dataset_digest=source_dataset_digest,
        )
        and metric_audit.get("ready") is True
        and after_compute == before
    ):
        return {
            "ready": False,
            "status": "factor_full_market_executor_compute_validation_failed",
            "blockers": list(metric_audit.get("blockers") or [])
            + (["factor_executor_head_or_clean_state_changed"] if after_compute != before else []),
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }

    import pandas as pd

    parquet_root = root / "parquet"
    dataset_root = parquet_root / FACTOR_TARGET_DATASET
    snapshot_paths = [
        dataset_root / "current.json",
        dataset_root / "last_good.json",
        dataset_root / "manifest.json",
    ]
    snapshot = _snapshot_files(snapshot_paths)
    version_id = f"fmf-{run_id}"
    artifact_path = dataset_root / "versions" / f"{version_id}.parquet"
    if artifact_path.exists() and artifact_path.is_symlink():
        return {
            "ready": False,
            "status": "factor_full_market_executor_artifact_path_unsafe",
            "blockers": ["factor_result_artifact_symlink_rejected"],
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
    artifact_existed_before = artifact_path.is_file() and not artifact_path.is_symlink()
    snapshot_value = _journal_snapshot(snapshot)
    journal = {
        "schema_version": FACTOR_EXECUTION_JOURNAL_SCHEMA_VERSION,
        "state": "prepared",
        "head_full": head_full,
        "acceptance_run_id": run_id,
        "version_id": version_id,
        "artifact_existed_before": artifact_existed_before,
        "snapshot": snapshot_value,
        "snapshot_digest": _digest(snapshot_value),
        "target_packet_digest": "",
        "target_task_digest": "",
        "target_artifact_sha256": "",
        "contains_secret": False,
        "does_not_execute_trades": True,
    }
    try:
        _write_factor_execution_journal(root, journal)
    except Exception:
        return {
            "ready": False,
            "status": "factor_full_market_executor_journal_prepare_failed",
            "blockers": ["factor_execution_journal_prepare_failed"],
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
    try:
        promotion = parquet_store.atomic_promote_versioned_dataset(
            pd.DataFrame(rows),
            root=parquet_root,
            name=FACTOR_TARGET_DATASET,
            version_id=version_id,
            required_columns=list(FACTOR_REQUIRED_RESULT_COLUMNS),
            lineage={
                "head_full": head_full,
                "acceptance_run_id": run_id,
                "provider_scope_hash": universe.get("scope_hash"),
                "provider_version_digest": universe.get("version_digest"),
                "universe_digest": universe.get("universe_digest"),
                "validated_trade_date": universe.get("validated_trade_date"),
                **industry_binding,
                "industry_input_digest": industry_input_digest,
                "industry_rows_digest": industry_rows_digest,
                "factor_batch_input_digest": factor_batch_input_digest,
                "source_dataset_digest": source_dataset_digest,
                "factor_output_contract_digest": worker_contract.FACTOR_OUTPUT_CONTRACT_DIGEST,
                "neutralization_audit_digest": metric_audit.get("audit_digest"),
                "external_worker_attestation_id": worker_trust.get("attestation_id"),
                "external_worker_artifact_digest": worker_trust.get("artifact_digest"),
                "synthetic_fixture": False,
                "contains_secret": False,
            },
        )
    except Exception:
        _restore_files(snapshot)
        if artifact_path.is_file() and not artifact_existed_before:
            artifact_path.unlink(missing_ok=True)
        promotion = {"atomic_promoted": False, "status": "parquet_promotion_exception"}
    if promotion.get("atomic_promoted") is not True:
        _restore_files(snapshot)
        if artifact_path.is_file() and not artifact_existed_before:
            artifact_path.unlink(missing_ok=True)
        _factor_execution_journal_path(root).unlink(missing_ok=True)
        return {
            "ready": False,
            "status": "factor_full_market_executor_parquet_promotion_failed",
            "blockers": [str(promotion.get("status") or "parquet_promotion_failed")],
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
    current_path = dataset_root / "current.json"
    try:
        current_pointer_payload = json.loads(current_path.read_text(encoding="utf-8"))
        last_good_payload = {**current_pointer_payload, "pointer_kind": "last_good"}
        _atomic_bytes(
            dataset_root / "last_good.json",
            json.dumps(last_good_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        )
    except Exception:
        _restore_files(snapshot)
        if artifact_path.is_file() and not artifact_existed_before:
            artifact_path.unlink(missing_ok=True)
        _factor_execution_journal_path(root).unlink(missing_ok=True)
        return {
            "ready": False,
            "status": "factor_full_market_executor_pointer_pair_failed",
            "blockers": ["factor_result_current_last_good_pointer_pair_failed"],
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
    packet = {
        "schema_version": FACTOR_PACKET_SCHEMA_VERSION,
        "status": "factor_full_market_worker_production_complete",
        "head_full": head_full,
        "acceptance_run_id": run_id,
        "output_kind": FACTOR_OUTPUT_CONTRACT["output_kind"],
        "factor_output_contract": dict(worker_contract.FACTOR_OUTPUT_CONTRACT),
        "factor_output_contract_digest": worker_contract.FACTOR_OUTPUT_CONTRACT_DIGEST,
        "full_market_factor_research": True,
        "full_market_worker_runtime": True,
        "celery_redis_runtime": True,
        "candidate_radar_production_replacement": False,
        "provider_scope_hash": universe.get("scope_hash"),
        "provider_version_digest": universe.get("version_digest"),
        "universe_digest": universe.get("universe_digest"),
        "universe_count": len(symbols),
        "minimum_universe_size": MINIMUM_UNIVERSE_SIZE,
        "validated_trade_date": universe.get("validated_trade_date"),
        **industry_binding,
        "industry_input_digest": industry_input_digest,
        "industry_rows_digest": industry_rows_digest,
        "factor_batch_input_digest": factor_batch_input_digest,
        "source_dataset_digest": source_dataset_digest,
        "result_dataset": FACTOR_TARGET_DATASET,
        "result_version_id": promotion.get("version_id"),
        "result_artifact_sha256": promotion.get("artifact_sha256"),
        "result_output_hash": output_hash,
        "result_row_count": len(rows),
        "metric_validation_audit": metric_audit,
        "neutralization_audit_digest": metric_audit.get("audit_digest"),
        "external_worker_attestation_id": worker_trust.get("attestation_id"),
        "external_worker_artifact_digest": worker_trust.get("artifact_digest"),
        "source_request_bundle_id": str(payload_map["request_bundle_id"]),
        "factor_request_task_id": factor_task_id,
        "synthetic_fixture": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    execution_bundle_id = _digest(
        {"head_full": head_full, "acceptance_run_id": run_id, "result_output_hash": output_hash}
    )
    execution_bundle_digest = _digest(
        {
            "request_bundle_id": execution_bundle_id,
            "head_full": head_full,
            "acceptance_run_id": run_id,
            "source_request_bundle_id": packet["source_request_bundle_id"],
            "result_version_id": packet["result_version_id"],
            "result_artifact_sha256": packet["result_artifact_sha256"],
            "result_output_hash": output_hash,
        }
    )
    packet["request_bundle_id"] = execution_bundle_id
    packet["bundle_digest"] = execution_bundle_digest
    packet["production_binding_digest"] = _digest(
        {key: value for key, value in packet.items() if key != "production_binding_digest"}
    )
    task = task_service.build_task_record(
        FACTOR_EXECUTION_TASK_TYPE,
        task_id=run_id,
        output_packet_key=FACTOR_TARGET_PACKET_KEY,
        payload={
            "request_bundle_id": execution_bundle_id,
            "bundle_digest": execution_bundle_digest,
            "head_full": head_full,
            "result_version_id": promotion.get("version_id"),
        },
        status="success",
        progress=1.0,
        current_step="factor_full_market_executor_durable_result_written",
        warnings=["research_only_no_provider_dispatch_no_trade"],
        call_ledger=[
            {
                "api": "local_verified_full_market_factor_executor",
                "call_status": "success",
                "row_count": len(rows),
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "redis_called": False,
                "celery_called": False,
                "does_not_execute_trades": True,
                "contains_secret": False,
            }
        ],
    )
    journal.update(
        {
            "state": "parquet_promoted",
            "target_packet_digest": _digest(packet),
            "target_task_digest": _digest(task),
            "target_artifact_sha256": promotion.get("artifact_sha256"),
        }
    )
    try:
        _write_factor_execution_journal(root, journal)
    except Exception:
        _restore_files(snapshot)
        if artifact_path.is_file() and not artifact_existed_before:
            artifact_path.unlink(missing_ok=True)
        return {
            "ready": False,
            "status": "factor_full_market_executor_journal_promoted_state_failed",
            "blockers": ["factor_execution_journal_promoted_state_failed"],
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
    try:
        write_result = SQLiteMetaStore(db_path).write_packet_task_bundle_atomic(
            packets={
                FACTOR_TARGET_PACKET_KEY: packet,
                f"{FACTOR_TARGET_PACKET_KEY}_last_good": packet,
            },
            tasks=[task],
            request_bundle_id=execution_bundle_id,
            bundle_digest=execution_bundle_digest,
        )
    except Exception:
        _restore_files(snapshot)
        if artifact_path.is_file() and not artifact_existed_before:
            artifact_path.unlink(missing_ok=True)
        _factor_execution_journal_path(root).unlink(missing_ok=True)
        return {
            "ready": False,
            "status": "factor_full_market_executor_sqlite_bundle_failed_rolled_back",
            "blockers": ["factor_packet_task_atomic_write_failed"],
            "writes_storage": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
    journal["state"] = "sqlite_committed"
    try:
        _write_factor_execution_journal(root, journal)
        _factor_execution_journal_path(root).unlink(missing_ok=True)
    except Exception:
        return {
            "ready": False,
            "status": "factor_full_market_executor_commit_recovery_required",
            "blockers": ["factor_execution_committed_journal_finalize_failed"],
            "writes_storage": True,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
        }
    return {
        **packet,
        "ready": True,
        "status": "factor_full_market_executor_durable_result_written_external_attestation_pending",
        "write_result": write_result,
        "external_factor_attestation_pending": True,
        "production_complete": False,
        "writes_storage": True,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
    }


def _provider_contract(evidence_root: Path) -> dict[str, Any]:
    raw = validate_tushare_full_market_production_version(
        evidence_root,
        include_frames=False,
    )
    provider = dict(raw) if isinstance(raw, Mapping) else {}
    raw_symbols = provider.get("symbols")
    symbols = (
        [str(item).strip().upper() for item in raw_symbols]
        if type(raw_symbols) is list
        else []
    )
    blockers = [str(item) for item in provider.get("blockers") or [] if str(item)]
    required_digests = {
        "provider_scope_hash": _safe_digest(provider.get("scope_hash")),
        "provider_version_digest": _safe_digest(provider.get("version_digest")),
        "universe_digest": _safe_digest(provider.get("universe_digest")),
        "artifact_manifest_digest": _safe_digest(provider.get("artifact_manifest_digest")),
    }
    raw_universe_count = provider.get("universe_count")
    universe_count = raw_universe_count if type(raw_universe_count) is int else 0
    validated_trade_date = str(provider.get("validated_trade_date") or "")
    if provider.get("ready") is not True:
        blockers.append("authoritative_provider_pointer_not_ready")
    if universe_count < MINIMUM_UNIVERSE_SIZE:
        blockers.append("authoritative_provider_universe_below_3000")
    if len(symbols) != universe_count or len(set(symbols)) != universe_count:
        blockers.append("authoritative_provider_symbol_identity_invalid")
    if required_digests["universe_digest"] != _digest(sorted(symbols)):
        blockers.append("authoritative_provider_universe_digest_mismatch")
    if any(not value for value in required_digests.values()):
        blockers.append("authoritative_provider_digest_binding_incomplete")
    if not (len(validated_trade_date) == 8 and validated_trade_date.isdigit()):
        blockers.append("authoritative_provider_trade_date_invalid")
    blockers = list(dict.fromkeys(blockers))
    return {
        "ready": not blockers,
        "status": (
            "authoritative_provider_pointer_ready_for_shared_map_reduce"
            if not blockers
            else "authoritative_provider_pointer_blocked"
        ),
        "universe_count": universe_count,
        "minimum_universe_size": MINIMUM_UNIVERSE_SIZE,
        "required_sessions": REQUIRED_SESSIONS,
        "validated_trade_date": validated_trade_date,
        "_symbols": sorted(symbols),
        **required_digests,
        "blockers": blockers,
        "read_only": True,
        "writes_storage": False,
        "external_calls_triggered": False,
    }


def build_full_market_factor_radar_map_reduce_contract(
    payload: Any = None,
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    root = Path(evidence_root or EVIDENCE_ROOT)
    provider_internal = _provider_contract(root)
    symbols = list(provider_internal.get("_symbols") or [])
    provider = {
        key: value for key, value in provider_internal.items() if key != "_symbols"
    }
    industry_raw = validate_full_market_industry_membership(
        root,
        expected_symbols=symbols,
        expected_universe_digest=provider.get("universe_digest"),
        expected_validated_trade_date=provider.get("validated_trade_date"),
    )
    industry = dict(industry_raw) if isinstance(industry_raw, Mapping) else {}
    industry_binding = {
        "industry_scope_digest": _safe_digest(industry.get("scope_digest")),
        "industry_source_version_digest": _safe_digest(
            industry.get("source_version_digest")
        ),
        "industry_artifact_sha256": _safe_digest(industry.get("artifact_sha256")),
        "industry_manifest_digest": _safe_digest(industry.get("manifest_digest")),
        "industry_pointer_digest": _safe_digest(industry.get("pointer_digest")),
        "industry_semantic_evidence_sha256": _safe_digest(
            industry.get("semantic_evidence_sha256")
        ),
    }
    industry_input_digest = _digest(industry_binding)
    full_market_batch_input_digest = _digest(
        {
            "provider_scope_hash": provider.get("provider_scope_hash"),
            "provider_version_digest": provider.get("provider_version_digest"),
            "universe_digest": provider.get("universe_digest"),
            "validated_trade_date": provider.get("validated_trade_date"),
            "symbols": symbols,
            "industry_binding": industry_binding,
            "industry_input_digest": industry_input_digest,
        }
    )
    head_full = _current_head_full()
    requested_industry_digest = _safe_digest(
        payload_map.get("effective_dated_industry_membership_digest")
    )
    blockers = list(provider.get("blockers") or [])
    blockers.extend(str(item) for item in industry.get("blockers") or [] if str(item))
    if not head_full:
        blockers.append("current_head_binding_missing")
    if industry.get("ready") is not True or not all(industry_binding.values()):
        blockers.append("authoritative_effective_dated_industry_membership_missing")
    if (
        requested_industry_digest
        and requested_industry_digest != industry_binding["industry_pointer_digest"]
    ):
        blockers.append("requested_industry_pointer_digest_mismatch")
    blockers.append(EXTERNAL_LINEAGE_BLOCKER)
    shared_material = {
        "schema_version": SCHEMA_VERSION,
        "head_full": head_full,
        "provider_scope_hash": provider.get("provider_scope_hash"),
        "provider_version_digest": provider.get("provider_version_digest"),
        "universe_digest": provider.get("universe_digest"),
        "artifact_manifest_digest": provider.get("artifact_manifest_digest"),
        "universe_count": provider.get("universe_count"),
        "required_sessions": REQUIRED_SESSIONS,
        "validated_trade_date": provider.get("validated_trade_date"),
        "requested_effective_dated_industry_membership_digest": industry_binding[
            "industry_pointer_digest"
        ],
        **industry_binding,
        "industry_input_digest": industry_input_digest,
        "full_market_batch_input_digest": full_market_batch_input_digest,
        "effective_dated_industry_membership_verified": industry.get("ready") is True,
        "factor_output_contract_digest": FACTOR_OUTPUT_CONTRACT_DIGEST,
        "radar_output_contract_digest": RADAR_OUTPUT_CONTRACT_DIGEST,
    }
    shared_scope_hash = _digest(shared_material)
    factor_request_material = {
        **shared_material,
        "output_kind": FACTOR_OUTPUT_CONTRACT["output_kind"],
        "target_dataset": FACTOR_TARGET_DATASET,
        "target_packet_key": FACTOR_TARGET_PACKET_KEY,
        "output_contract_digest": FACTOR_OUTPUT_CONTRACT_DIGEST,
    }
    radar_request_material = {
        **shared_material,
        "output_kind": RADAR_OUTPUT_CONTRACT["output_kind"],
        "target_dataset": RADAR_TARGET_DATASET,
        "target_packet_key": RADAR_TARGET_PACKET_KEY,
        "output_contract_digest": RADAR_OUTPUT_CONTRACT_DIGEST,
    }
    request_scope_ready = bool(
        provider.get("ready") is True
        and industry.get("ready") is True
        and not provider.get("blockers")
        and not industry.get("blockers")
        and all(industry_binding.values())
        and head_full
        and (
            not requested_industry_digest
            or requested_industry_digest
            == industry_binding["industry_pointer_digest"]
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "full_market_factor_radar_execution_request_recorded_authoritative_inputs_pending"
            if request_scope_ready
            else "full_market_factor_radar_execution_request_blocked"
        ),
        "head_full": head_full,
        "provider": provider,
        "industry_membership": industry,
        "shared_scope_hash": shared_scope_hash,
        "shared_scope_material": shared_material,
        "factor_output_contract": dict(FACTOR_OUTPUT_CONTRACT),
        "factor_output_contract_digest": FACTOR_OUTPUT_CONTRACT_DIGEST,
        "factor_request_digest": _digest(factor_request_material),
        "radar_output_contract": dict(RADAR_OUTPUT_CONTRACT),
        "radar_output_contract_digest": RADAR_OUTPUT_CONTRACT_DIGEST,
        "radar_request_digest": _digest(radar_request_material),
        "output_contracts_are_independent": (
            FACTOR_OUTPUT_CONTRACT_DIGEST != RADAR_OUTPUT_CONTRACT_DIGEST
            and FACTOR_TARGET_DATASET != RADAR_TARGET_DATASET
            and FACTOR_TARGET_PACKET_KEY != RADAR_TARGET_PACKET_KEY
        ),
        "shared_map_reduce_reuses_verified_provider_reads": True,
        "factor_and_radar_are_separate_reduce_outputs": True,
        "execution_request_scope_ready": request_scope_ready,
        "execution_request_ready": False,
        "production_prerequisites_ready": False,
        "dispatch_allowed": False,
        "external_trusted_lineage_runner_available": False,
        "blockers": list(dict.fromkeys(blockers)),
        "production_complete": False,
        "factor_production_complete": False,
        "candidate_radar_production_replacement": False,
        "global_candidate_cache_overwritten": False,
        "provider_execution_triggered": False,
        "worker_execution_triggered": False,
        "redis_called": False,
        "celery_called": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _exact_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, int):
        return type(actual) is int and actual == expected
    return actual == expected


def _bundle_identity(contract: Mapping[str, Any]) -> dict[str, str]:
    request_bundle_id = _digest(
        {
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "head_full": contract.get("head_full"),
            "shared_scope_hash": contract.get("shared_scope_hash"),
            "factor_request_digest": contract.get("factor_request_digest"),
            "radar_request_digest": contract.get("radar_request_digest"),
        }
    )

    def task_id(role: str) -> str:
        return f"local-{_digest({'request_bundle_id': request_bundle_id, 'role': role})[:12]}"

    return {
        "request_bundle_id": request_bundle_id,
        "factor_task_id": task_id("factor"),
        "radar_task_id": task_id("radar"),
        "coordinator_task_id": task_id("coordinator"),
    }


def _child_packet_digest(packet: Mapping[str, Any]) -> str:
    return _digest(
        {
            key: value
            for key, value in packet.items()
            if key not in {"packet_digest", "bundle_digest"}
        }
    )


def _expected_request_bundle(contract: Mapping[str, Any]) -> dict[str, Any]:
    provider = contract.get("provider") if isinstance(contract.get("provider"), Mapping) else {}
    shared = (
        contract.get("shared_scope_material")
        if isinstance(contract.get("shared_scope_material"), Mapping)
        else {}
    )
    identity = _bundle_identity(contract)
    expected_common = {
        "schema_version": CHILD_SCHEMA_VERSION,
        "status": (
            "execution_request_recorded_authoritative_inputs_pending"
            if contract.get("execution_request_scope_ready") is True
            else "execution_request_blocked_prerequisites_missing"
        ),
        "head_full": contract.get("head_full"),
        "shared_scope_hash": contract.get("shared_scope_hash"),
        "request_bundle_id": identity["request_bundle_id"],
        "coordinator_task_id": identity["coordinator_task_id"],
        "provider_scope_hash": provider.get("provider_scope_hash"),
        "provider_version_digest": provider.get("provider_version_digest"),
        "universe_digest": provider.get("universe_digest"),
        "artifact_manifest_digest": provider.get("artifact_manifest_digest"),
        "universe_count": provider.get("universe_count"),
        "required_sessions": REQUIRED_SESSIONS,
        "validated_trade_date": provider.get("validated_trade_date"),
        "requested_effective_dated_industry_membership_digest": shared.get(
            "requested_effective_dated_industry_membership_digest"
        ),
        **{
            key: shared.get(key) for key in INDUSTRY_BINDING_DIGEST_KEYS
        },
        "industry_input_digest": shared.get("industry_input_digest"),
        "full_market_batch_input_digest": shared.get(
            "full_market_batch_input_digest"
        ),
        "effective_dated_industry_membership_verified": shared.get(
            "effective_dated_industry_membership_verified"
        )
        is True,
        "blockers": list(contract.get("blockers") or []),
        "dispatch_allowed": False,
        "external_trusted_lineage_runner_available": False,
        "production_complete": False,
        "writes_target_dataset": False,
        "writes_target_packet": False,
        "global_candidate_cache_overwritten": False,
        "provider_execution_triggered": False,
        "worker_execution_triggered": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    factor_packet = {
        **expected_common,
        "task_id": identity["factor_task_id"],
        "request_digest": contract.get("factor_request_digest"),
        "output_kind": FACTOR_OUTPUT_CONTRACT["output_kind"],
        "target_dataset": FACTOR_TARGET_DATASET,
        "target_packet_key": FACTOR_TARGET_PACKET_KEY,
        "output_contract_digest": FACTOR_OUTPUT_CONTRACT_DIGEST,
        "factor_batch_input_digest": shared.get("full_market_batch_input_digest"),
    }
    radar_packet = {
        **expected_common,
        "task_id": identity["radar_task_id"],
        "request_digest": contract.get("radar_request_digest"),
        "output_kind": RADAR_OUTPUT_CONTRACT["output_kind"],
        "target_dataset": RADAR_TARGET_DATASET,
        "target_packet_key": RADAR_TARGET_PACKET_KEY,
        "output_contract_digest": RADAR_OUTPUT_CONTRACT_DIGEST,
        "radar_full_market_input_digest": shared.get(
            "full_market_batch_input_digest"
        ),
    }
    factor_packet_digest = _child_packet_digest(factor_packet)
    radar_packet_digest = _child_packet_digest(radar_packet)
    bundle_material = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "request_bundle_id": identity["request_bundle_id"],
        "coordinator_task_id": identity["coordinator_task_id"],
        "head_full": contract.get("head_full"),
        "shared_scope_hash": contract.get("shared_scope_hash"),
        "provider_scope_hash": provider.get("provider_scope_hash"),
        "provider_version_digest": provider.get("provider_version_digest"),
        "universe_digest": provider.get("universe_digest"),
        "artifact_manifest_digest": provider.get("artifact_manifest_digest"),
        **{
            key: shared.get(key) for key in INDUSTRY_BINDING_DIGEST_KEYS
        },
        "industry_input_digest": shared.get("industry_input_digest"),
        "full_market_batch_input_digest": shared.get(
            "full_market_batch_input_digest"
        ),
        "factor_task_id": identity["factor_task_id"],
        "factor_request_digest": contract.get("factor_request_digest"),
        "factor_packet_digest": factor_packet_digest,
        "radar_task_id": identity["radar_task_id"],
        "radar_request_digest": contract.get("radar_request_digest"),
        "radar_packet_digest": radar_packet_digest,
    }
    bundle_digest = _digest(bundle_material)
    factor_packet["bundle_digest"] = bundle_digest
    factor_packet["packet_digest"] = factor_packet_digest
    radar_packet["bundle_digest"] = bundle_digest
    radar_packet["packet_digest"] = radar_packet_digest
    return {
        **identity,
        "bundle_material": bundle_material,
        "bundle_digest": bundle_digest,
        "factor_packet": factor_packet,
        "radar_packet": radar_packet,
    }


def _validate_independent_output_requests(
    factor_request: Mapping[str, Any],
    radar_request: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    provider = contract.get("provider") if isinstance(contract.get("provider"), Mapping) else {}
    shared = (
        contract.get("shared_scope_material")
        if isinstance(contract.get("shared_scope_material"), Mapping)
        else {}
    )
    expected_bundle = _expected_request_bundle(contract)
    expected_factor = expected_bundle["factor_packet"]
    expected_radar = expected_bundle["radar_packet"]

    def packet_checks(
        prefix: str,
        packet: Mapping[str, Any],
        expected: Mapping[str, Any],
    ) -> dict[str, bool]:
        task_id = str(packet.get("task_id") or "")
        return {
            f"{prefix}_fields_exact": set(packet) == set(expected),
            f"{prefix}_task_id_valid": bool(re.fullmatch(r"local-[0-9a-f]{12}", task_id)),
            f"{prefix}_authoritative_fields_exact": all(
                _exact_value(packet.get(key), value) for key, value in expected.items()
            ),
            f"{prefix}_packet_digest_exact": (
                _safe_digest(packet.get("packet_digest"))
                == _child_packet_digest(packet)
            ),
        }

    checks = {
        "current_head_exact": bool(
            re.fullmatch(r"[0-9a-f]{40}", str(contract.get("head_full") or ""))
            and contract.get("head_full") == _current_head_full()
        ),
        "shared_scope_recomputed": (
            _safe_digest(contract.get("shared_scope_hash")) == _digest(shared)
        ),
        "bundle_digest_recomputed": (
            _safe_digest(factor_request.get("bundle_digest"))
            == expected_bundle["bundle_digest"]
            == _safe_digest(radar_request.get("bundle_digest"))
        ),
        "provider_digests_complete": all(
            _safe_digest(provider.get(key))
            for key in (
                "provider_scope_hash",
                "provider_version_digest",
                "universe_digest",
                "artifact_manifest_digest",
            )
        ),
        "industry_digests_complete": all(
            _safe_digest(shared.get(key)) for key in INDUSTRY_BINDING_DIGEST_KEYS
        ),
        "industry_input_digest_recomputed": (
            _safe_digest(shared.get("industry_input_digest"))
            == _digest({key: shared.get(key) for key in INDUSTRY_BINDING_DIGEST_KEYS})
        ),
        "full_market_batch_input_digest_complete": bool(
            _safe_digest(shared.get("full_market_batch_input_digest"))
            and factor_request.get("factor_batch_input_digest")
            == shared.get("full_market_batch_input_digest")
            and radar_request.get("radar_full_market_input_digest")
            == shared.get("full_market_batch_input_digest")
        ),
        **packet_checks("factor", factor_request, expected_factor),
        **packet_checks("radar", radar_request, expected_radar),
        "output_digests_are_distinct": (
            factor_request.get("output_contract_digest")
            != radar_request.get("output_contract_digest")
        ),
        "target_datasets_are_distinct": (
            factor_request.get("target_dataset") != radar_request.get("target_dataset")
        ),
        "target_packets_are_distinct": (
            factor_request.get("target_packet_key") != radar_request.get("target_packet_key")
        ),
        "shared_scope_exact": bool(
            factor_request.get("shared_scope_hash")
            and factor_request.get("shared_scope_hash") == radar_request.get("shared_scope_hash")
        ),
        "request_digests_are_distinct": bool(
            _safe_digest(factor_request.get("request_digest"))
            and _safe_digest(radar_request.get("request_digest"))
            and factor_request.get("request_digest") != radar_request.get("request_digest")
        ),
        "packet_digests_are_distinct": bool(
            _safe_digest(factor_request.get("packet_digest"))
            and _safe_digest(radar_request.get("packet_digest"))
            and factor_request.get("packet_digest") != radar_request.get("packet_digest")
        ),
        "task_ids_are_distinct": bool(
            factor_request.get("task_id")
            and factor_request.get("task_id") != radar_request.get("task_id")
        ),
    }
    blockers = [key for key, ready in checks.items() if ready is not True]
    return {
        "ready": not blockers,
        "checks": checks,
        "blockers": blockers,
        "factor_rows_accepted_as_radar": False,
        "radar_rows_accepted_as_factor": False,
        "production_complete": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
    }


def validate_independent_output_requests(
    factor_request: Mapping[str, Any],
    radar_request: Mapping[str, Any],
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Rebuild authoritative local bindings before validating two request packets."""

    requested_digest = factor_request.get("industry_pointer_digest")
    contract = build_full_market_factor_radar_map_reduce_contract(
        {"effective_dated_industry_membership_digest": requested_digest},
        evidence_root=evidence_root,
    )
    return _validate_independent_output_requests(factor_request, radar_request, contract)


def _request_packet(
    contract: Mapping[str, Any],
    *,
    output_kind: str,
    target_dataset: str,
    target_packet_key: str,
    output_contract_digest: str,
    request_digest: str,
) -> dict[str, Any]:
    bundle = _expected_request_bundle(contract)
    factor_exact = (
        output_kind == FACTOR_OUTPUT_CONTRACT["output_kind"]
        and target_dataset == FACTOR_TARGET_DATASET
        and target_packet_key == FACTOR_TARGET_PACKET_KEY
        and output_contract_digest == FACTOR_OUTPUT_CONTRACT_DIGEST
        and request_digest == contract.get("factor_request_digest")
    )
    radar_exact = (
        output_kind == RADAR_OUTPUT_CONTRACT["output_kind"]
        and target_dataset == RADAR_TARGET_DATASET
        and target_packet_key == RADAR_TARGET_PACKET_KEY
        and output_contract_digest == RADAR_OUTPUT_CONTRACT_DIGEST
        and request_digest == contract.get("radar_request_digest")
    )
    if factor_exact:
        return dict(bundle["factor_packet"])
    if radar_exact:
        return dict(bundle["radar_packet"])
    raise ValueError("request_packet_contract_identity_invalid")


def _local_request_ledger(api: str, packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "api": api,
            "request_params_safe": {
                "head_full": packet.get("head_full"),
                "shared_scope_hash": packet.get("shared_scope_hash"),
                "request_digest": packet.get("request_digest"),
                "target_dataset": packet.get("target_dataset"),
                "universe_count": packet.get("universe_count"),
                "required_sessions": packet.get("required_sessions"),
            },
            "row_count": 0,
            "call_status": str(packet.get("status") or "execution_request_blocked"),
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "redis_called": False,
            "celery_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    ]


def run_full_market_factor_radar_map_reduce_request(
    payload: Any = None,
    *,
    evidence_root: Path | None = None,
    meta_path: Path | None = None,
) -> dict[str, Any]:
    """Persist local execution requests; never dispatch provider or workers."""

    contract = build_full_market_factor_radar_map_reduce_contract(
        payload,
        evidence_root=evidence_root,
    )
    bundle = _expected_request_bundle(contract)
    factor_task_id = str(bundle["factor_task_id"])
    radar_task_id = str(bundle["radar_task_id"])
    coordinator_task_id = str(bundle["coordinator_task_id"])
    factor_packet = dict(bundle["factor_packet"])
    radar_packet = dict(bundle["radar_packet"])
    independence = _validate_independent_output_requests(factor_packet, radar_packet, contract)
    if independence.get("ready") is not True:
        raise RuntimeError("independent_output_request_integrity_failed")
    factor_ledger = _local_request_ledger("local_factor_full_market_map_reduce_request", factor_packet)
    radar_ledger = _local_request_ledger("local_candidate_radar_map_reduce_request", radar_packet)
    factor_task = task_service.build_task_record(
        FACTOR_TASK_TYPE,
        task_id=factor_task_id,
        output_packet_key=FACTOR_REQUEST_PACKET_KEY,
        payload=factor_packet,
        status="success",
        progress=1.0,
        current_step=str(factor_packet["status"]),
        warnings=["execution_request_only_no_provider_worker_or_production_write"],
        call_ledger=factor_ledger,
    )
    radar_task = task_service.build_task_record(
        RADAR_TASK_TYPE,
        task_id=radar_task_id,
        output_packet_key=RADAR_REQUEST_PACKET_KEY,
        payload=radar_packet,
        status="success",
        progress=1.0,
        current_step=str(radar_packet["status"]),
        warnings=["execution_request_only_no_provider_worker_or_candidate_cache_write"],
        call_ledger=radar_ledger,
    )
    coordinator_payload = {
        **dict(contract),
        "task_id": coordinator_task_id,
        "request_bundle_id": bundle["request_bundle_id"],
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_material": bundle["bundle_material"],
        "bundle_digest": bundle["bundle_digest"],
        "factor_task_id": factor_task_id,
        "factor_request_packet_key": FACTOR_REQUEST_PACKET_KEY,
        "factor_request_packet_digest": factor_packet.get("packet_digest"),
        "radar_task_id": radar_task_id,
        "radar_request_packet_key": RADAR_REQUEST_PACKET_KEY,
        "radar_request_packet_digest": radar_packet.get("packet_digest"),
        "independent_output_request_validation": independence,
    }
    coordinator_payload["packet_digest"] = _digest(coordinator_payload)
    coordinator_ledger = _local_request_ledger(
        "local_full_market_factor_radar_map_reduce_request",
        {
            **coordinator_payload,
            "request_digest": coordinator_payload.get("packet_digest"),
            "target_dataset": "two_independent_outputs",
            "universe_count": contract.get("provider", {}).get("universe_count"),
            "required_sessions": REQUIRED_SESSIONS,
        },
    )
    coordinator = task_service.build_task_record(
        COORDINATOR_TASK_TYPE,
        task_id=coordinator_task_id,
        output_packet_key=COORDINATOR_PACKET_KEY,
        payload=coordinator_payload,
        status="success",
        progress=1.0,
        current_step=str(contract.get("status") or "execution_request_blocked"),
        warnings=[
            "shared_map_reduce_execution_request_only_no_provider_redis_celery_dispatch",
            "factor_and_candidate_radar_outputs_require_independent_trusted_lineage",
        ],
        call_ledger=coordinator_ledger,
    )
    store = SQLiteMetaStore(Path(meta_path or SQLITE_META_PATH))
    write_result = store.write_packet_task_bundle_atomic(
        packets={
            FACTOR_REQUEST_PACKET_KEY: factor_packet,
            RADAR_REQUEST_PACKET_KEY: radar_packet,
            COORDINATOR_PACKET_KEY: coordinator_payload,
        },
        tasks=[factor_task, radar_task, coordinator],
        request_bundle_id=str(bundle["request_bundle_id"]),
        bundle_digest=str(bundle["bundle_digest"]),
    )
    if write_result.get("status") == "packet_task_bundle_reused":
        persisted = SQLiteMetaStore(
            Path(meta_path or SQLITE_META_PATH), read_only=True
        ).read_task_status(coordinator_task_id)
        if not isinstance(persisted, dict):
            raise RuntimeError("idempotent_bundle_coordinator_readback_failed")
        coordinator = persisted
    coordinator["payload_safe"] = coordinator_payload
    coordinator["external_calls_triggered"] = False
    coordinator["tushare_called"] = False
    coordinator["deepseek_called"] = False
    coordinator["github_called"] = False
    coordinator["does_not_execute_trades"] = True
    coordinator["does_not_modify_strategy_action"] = True
    return coordinator
