"""Fail-closed LTG-08 replacement evidence and promotion contract.

The local read path audits fixed-disk prerequisites without writes or external
calls. Same-UID seals remain production-ineligible; promotion is delegated to
the verify-only external approval/high-water journal service.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import stat
import subprocess
import uuid
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import (
    motion_evidence_service,
    next_session_external_promotion_service,
    release_promotion_service,
    streamlit_retirement_evidence_service,
)
from .sqlite_evidence_reader import immutable_evidence_connection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
ROOT_NAME = "next_session_replacement_promotion"
EVENTS_NAME = "events"
TRUST_NAME = ".writer_trust"
KEY_NAME = "writer.key"
STATE_NAME = "writer.state"
APPROVAL_ROOT_NAME = ".next_session_replacement_approval"
APPROVAL_KEY_NAME = "approval.key"
APPROVAL_TICKET_NAME = "approval.ticket.json"
APPROVAL_STATE_NAME = "approval.state.json"

EVENT_SCHEMA = "next_session_production_replacement_event.v1"
STATE_SCHEMA = "next_session_production_replacement_state.v1"
VALIDATION_SCHEMA = "next_session_production_replacement_validation.v1"
APPROVAL_TICKET_SCHEMA = "next_session_production_replacement_approval_ticket.v1"
APPROVAL_STATE_SCHEMA = "next_session_production_replacement_approval_state.v1"
SCOPE = "ltg08_next_session_current_head_production_replacement"
STRUCTURAL_PRODUCTION_BLOCKERS = (
    "external_trusted_approval_capability_unavailable",
    "rollback_resistant_high_water_unavailable",
)

_HEAD = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EVENT_FILE = re.compile(r"^[0-9]{8}\.json$")
_REQUIRED_VIEWPORTS = {"desktop", "laptop", "tablet", "mobile"}
_REQUIRED_FEATURE_COUNT = 9
_MIN_PRODUCTION_CLOSE_POINTS = 60
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
_PROVENANCE_FIELDS = {
    "schema_version",
    "status",
    "head_full",
    "source_task_id",
    "source_task_status",
    "source_task_payload_digest",
    "source_task_call_ledger_digest",
    "official_execution_event_digest",
    "source_task_finished_at",
    "provider_receipt_observed_at_utc",
    "provider_receipt_completed_at_utc",
    "authoritative_calendar_as_of_date",
    "authoritative_current_trade_date",
    "result_version",
    "packet_scope_hash",
    "coverage_rows_digest",
    "symbol",
    "data_date",
    "provider_scope_hash",
    "dataset_version_digest",
    "daily_rows_digest",
    "trade_calendar_digest",
    "provider_backed",
    "authoritative_dataset",
    "trade_calendar_validated",
    "synthetic_fixture",
    "local_preview",
}

_EVENT_FIELDS = {
    "schema_version",
    "status",
    "sequence_no",
    "event_id",
    "semantic_digest",
    "scope",
    "head_full",
    "next_packet_digest",
    "motion_pair_digest",
    "streamlit_retirement_digest",
    "remote_ci_digest",
    "remote_run_id",
    "remote_artifact_digest",
    "release_promotion_event_id",
    "approval_review_id",
    "approval_ticket_id",
    "approval_nonce_digest",
    "approved_by_user",
    "recorded_at_utc",
    "previous_event_mac",
    "event_mac",
}
_APPROVAL_FIELDS = {
    "schema_version",
    "status",
    "scope",
    "head_full",
    "semantic_digest",
    "review_id",
    "ticket_id",
    "nonce_digest",
    "approved_by_user",
    "issued_at_utc",
    "expires_at_utc",
    "ticket_mac",
}
_APPROVAL_STATE_FIELDS = {
    "schema_version",
    "sequence_no",
    "event_id",
    "event_mac",
    "approval_ticket_id",
    "consumed_at_utc",
    "state_mac",
}
_STATE_FIELDS = {
    "schema_version",
    "sequence_no",
    "event_id",
    "event_mac",
    "updated_at_utc",
    "state_mac",
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


def _mac(secret: bytes, value: Any) -> str:
    return hmac.new(secret, _canonical_bytes(value), hashlib.sha256).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _current_shanghai_date() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def _production_timestamp(value: object, *, assume_shanghai: bool = False) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        if not assume_shanghai:
            return None
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return parsed.astimezone(timezone.utc)


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.microsecond == 0


def _normalize_head(value: object) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if _HEAD.fullmatch(candidate) else ""


def _current_head(project_root: Path = PROJECT_ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return _normalize_head(result.stdout) if result.returncode == 0 else ""


def _paths(evidence_root: Path | str) -> tuple[Path, Path, Path, Path]:
    root = Path(evidence_root).expanduser().resolve() / ROOT_NAME
    trust = root / TRUST_NAME
    return root, root / EVENTS_NAME, trust / KEY_NAME, trust / STATE_NAME


def _owned_by_user(metadata: os.stat_result) -> bool:
    getuid = getattr(os, "getuid", None)
    return getuid is None or metadata.st_uid == getuid()


def _secure_regular(path: Path, *, mode: int, max_bytes: int = 4 * 1024 * 1024) -> bytes | None:
    try:
        before = path.lstat()
    except OSError:
        return None
    if not (
        stat.S_ISREG(before.st_mode)
        and not stat.S_ISLNK(before.st_mode)
        and stat.S_IMODE(before.st_mode) == mode
        and _owned_by_user(before)
        and before.st_nlink == 1
        and before.st_size <= max_bytes
    ):
        return None
    flags = os.O_RDONLY | int(getattr(os, "O_CLOEXEC", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or opened.st_size != before.st_size
        ):
            return None
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        return data if len(data) <= max_bytes else None
    except OSError:
        return None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_json(path: Path, *, mode: int = 0o600) -> dict[str, Any]:
    data = _secure_regular(path, mode=mode)
    try:
        value = json.loads(data) if data is not None else None
    except (TypeError, ValueError):
        value = None
    return dict(value) if isinstance(value, Mapping) else {}


def _directory_valid(path: Path, *, mode: int = 0o700) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return bool(
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == mode
        and _owned_by_user(metadata)
    )


def _evidence_anchor_valid(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return bool(
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) & 0o022 == 0
        and _owned_by_user(metadata)
    )


def _evidence_tree_symlink_blocker(path: Path) -> str:
    """Reject a caller-selected evidence tree containing any symlink.

    Resolving the path before checking it would erase the fact that the caller
    supplied a symlink.  A production evidence reader must fail closed for a
    symlink at the root or at any traversed descendant.
    """

    try:
        if path.is_symlink():
            return "next_session_replacement_evidence_root_symlink_invalid"
        if not path.exists():
            return ""
        pending = [path]
        while pending:
            current = pending.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        return "next_session_replacement_evidence_tree_symlink_invalid"
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
    except OSError:
        return "next_session_replacement_evidence_tree_unreadable"
    return ""


def _read_immutable_source_task_status(
    evidence_root: Path,
    task_id: str,
) -> dict[str, Any]:
    """Read the current task and its latest append-only history row in RO mode."""

    db_path = evidence_root / "meta.sqlite"
    try:
        metadata = db_path.lstat()
    except OSError:
        return {}
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        return {}
    connection: sqlite3.Connection | None = None
    try:
        connection = immutable_evidence_connection(db_path)
        if connection is None:
            return {}
        current = connection.execute(
            "SELECT payload_json FROM task_status WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        history = connection.execute(
            """
            SELECT payload_json, payload_digest
            FROM task_status_history
            WHERE task_id = ?
            ORDER BY history_id DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        if current is None or history is None or current[0] != history[0]:
            return {}
        payload_json = str(current[0])
        if hashlib.sha256(payload_json.encode("utf-8")).hexdigest() != str(history[1] or ""):
            return {}
        payload = json.loads(payload_json)
        return dict(payload) if isinstance(payload, Mapping) else {}
    except Exception:
        return {}
    finally:
        if connection is not None:
            connection.close()


def _read_secret(evidence_root: Path | str) -> tuple[bytes | None, str]:
    root, events, key_path, _ = _paths(evidence_root)
    trust = key_path.parent
    if not root.exists() and not trust.exists() and not key_path.exists():
        return None, "next_session_replacement_trusted_writer_key_missing"
    if not (_directory_valid(root) and _directory_valid(events) and _directory_valid(trust)):
        return None, "next_session_replacement_trust_directory_invalid"
    try:
        root_names = {entry.name for entry in root.iterdir()}
        trust_names = {entry.name for entry in trust.iterdir()}
    except OSError:
        return None, "next_session_replacement_trust_directory_invalid"
    if root_names != {EVENTS_NAME, TRUST_NAME} or not trust_names.issubset({KEY_NAME, STATE_NAME}):
        return None, "next_session_replacement_trust_directory_invalid"
    secret = _secure_regular(key_path, mode=0o600, max_bytes=32)
    if secret is None:
        return None, "next_session_replacement_trusted_writer_key_invalid"
    if len(secret) != 32:
        return None, "next_session_replacement_trusted_writer_key_invalid"
    return secret, ""


def _atomic_private_json(path: Path, value: Mapping[str, Any], *, replace: bool) -> str:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | int(getattr(os, "O_CLOEXEC", 0))
            | int(getattr(os, "O_NOFOLLOW", 0)),
            0o600,
        )
        data = _canonical_bytes(dict(value)) + b"\n"
        try:
            offset = 0
            while offset < len(data):
                offset += os.write(descriptor, data[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
            descriptor = -1
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path, follow_symlinks=False)
            temporary.unlink()
        directory_descriptor = os.open(
            path.parent,
            os.O_RDONLY | int(getattr(os, "O_DIRECTORY", 0)),
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return ""
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return "next_session_replacement_journal_write_failed"


def _approval_paths(evidence_root: Path | str) -> tuple[Path, Path, Path, Path]:
    root = Path(evidence_root).expanduser().resolve() / APPROVAL_ROOT_NAME
    return (
        root,
        root / APPROVAL_KEY_NAME,
        root / APPROVAL_TICKET_NAME,
        root / APPROVAL_STATE_NAME,
    )


def _read_approval_secret(evidence_root: Path | str) -> tuple[bytes | None, str]:
    root, key_path, _, _ = _approval_paths(evidence_root)
    if not root.exists():
        return None, "next_session_replacement_out_of_band_approval_capability_missing"
    if not _directory_valid(root):
        return None, "next_session_replacement_out_of_band_approval_capability_invalid"
    try:
        names = {entry.name for entry in root.iterdir()}
    except OSError:
        return None, "next_session_replacement_out_of_band_approval_capability_invalid"
    if not names.issubset({APPROVAL_KEY_NAME, APPROVAL_TICKET_NAME, APPROVAL_STATE_NAME}):
        return None, "next_session_replacement_out_of_band_approval_capability_invalid"
    secret = _secure_regular(key_path, mode=0o600, max_bytes=32)
    if secret is None or len(secret) != 32:
        return None, "next_session_replacement_out_of_band_approval_capability_invalid"
    return secret, ""


def _approval_without_mac(ticket: Mapping[str, Any]) -> dict[str, Any]:
    return {key: ticket.get(key) for key in sorted(_APPROVAL_FIELDS - {"ticket_mac"})}


def _approval_review_id(*, head_full: str, semantic_digest: str) -> str:
    return _digest({"scope": SCOPE, "head_full": head_full, "semantic_digest": semantic_digest})


def record_next_session_replacement_approval_ticket(
    *,
    evidence_root: Path | str = EVIDENCE_ROOT,
    expected_head_full: str,
    semantic_digest: str,
    review_id: str,
    approved_by_user: bool,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Record no authority: this process can only perform local QA review.

    A same-UID file and key cannot be an out-of-band operator capability.  The
    public recorder therefore never creates a production-eligible ticket.
    """

    root = Path(evidence_root).expanduser().absolute()
    head_full = _normalize_head(expected_head_full)
    symlink_blocker = _evidence_tree_symlink_blocker(root)
    prerequisites = (
        _collect_prerequisites(root, expected_head_full=head_full, project_root=project_root)
        if not symlink_blocker
        else {
            "ready": False,
            "head_full": head_full,
            "semantic_digest": "",
            "blockers": [symlink_blocker],
        }
    )
    expected_review_id = _approval_review_id(
        head_full=head_full,
        semantic_digest=str(prerequisites.get("semantic_digest") or ""),
    )
    blockers = list(prerequisites.get("blockers") or [])
    if approved_by_user is not True:
        blockers.append("explicit_user_next_session_replacement_approval_required")
    if semantic_digest != prerequisites.get("semantic_digest"):
        blockers.append("next_session_replacement_approval_semantic_digest_mismatch")
    if review_id != expected_review_id:
        blockers.append("next_session_replacement_approval_review_id_mismatch")
    blockers.extend(STRUCTURAL_PRODUCTION_BLOCKERS)
    return {
        "status": "next_session_replacement_local_qa_review_only",
        "ticket_written": False,
        "production_eligible": False,
        "local_qa_only": True,
        "review_id": expected_review_id,
        "ticket_id": "",
        "blockers": sorted(set(blockers)),
        "contains_secret": False,
    }


def _load_approval_ticket(
    evidence_root: Path | str,
    *,
    head_full: str,
    semantic_digest: str,
) -> tuple[dict[str, Any] | None, str]:
    secret, blocker = _read_approval_secret(evidence_root)
    if secret is None:
        return None, blocker
    _, _, ticket_path, _ = _approval_paths(evidence_root)
    ticket = _read_json(ticket_path)
    if set(ticket) != _APPROVAL_FIELDS:
        return None, "next_session_replacement_out_of_band_approval_ticket_missing_or_invalid"
    unsigned = _approval_without_mac(ticket)
    expected_id = _digest({key: value for key, value in unsigned.items() if key != "ticket_id"})
    now = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        expires = datetime.fromisoformat(str(ticket.get("expires_at_utc") or "").replace("Z", "+00:00"))
    except ValueError:
        expires = datetime.min.replace(tzinfo=timezone.utc)
    if not (
        ticket.get("schema_version") == APPROVAL_TICKET_SCHEMA
        and ticket.get("status") == "next_session_replacement_approval_ticket_issued"
        and ticket.get("scope") == SCOPE
        and ticket.get("head_full") == head_full
        and ticket.get("semantic_digest") == semantic_digest
        and ticket.get("review_id") == _approval_review_id(head_full=head_full, semantic_digest=semantic_digest)
        and ticket.get("ticket_id") == expected_id
        and _SHA256.fullmatch(str(ticket.get("ticket_id") or ""))
        and _SHA256.fullmatch(str(ticket.get("nonce_digest") or ""))
        and ticket.get("approved_by_user") is True
        and _valid_timestamp(ticket.get("issued_at_utc"))
        and _valid_timestamp(ticket.get("expires_at_utc"))
        and expires >= now
        and _SHA256.fullmatch(str(ticket.get("ticket_mac") or ""))
        and hmac.compare_digest(str(ticket.get("ticket_mac") or ""), _mac(secret, unsigned))
    ):
        return None, "next_session_replacement_out_of_band_approval_ticket_invalid_or_stale"
    return ticket, ""


def _approval_state_without_mac(state: Mapping[str, Any]) -> dict[str, Any]:
    return {key: state.get(key) for key in sorted(_APPROVAL_STATE_FIELDS - {"state_mac"})}


def _approval_high_water_blocker(
    evidence_root: Path | str,
    event: Mapping[str, Any],
) -> str:
    secret, blocker = _read_approval_secret(evidence_root)
    if secret is None:
        return blocker
    _, _, _, state_path = _approval_paths(evidence_root)
    state = _read_json(state_path)
    if set(state) != _APPROVAL_STATE_FIELDS:
        return "next_session_replacement_approval_high_water_state_missing_or_invalid"
    unsigned = _approval_state_without_mac(state)
    if not (
        state.get("schema_version") == APPROVAL_STATE_SCHEMA
        and state.get("sequence_no") == event.get("sequence_no")
        and state.get("event_id") == event.get("event_id")
        and state.get("event_mac") == event.get("event_mac")
        and state.get("approval_ticket_id") == event.get("approval_ticket_id")
        and _valid_timestamp(state.get("consumed_at_utc"))
        and _SHA256.fullmatch(str(state.get("state_mac") or ""))
        and hmac.compare_digest(str(state.get("state_mac") or ""), _mac(secret, unsigned))
    ):
        return "next_session_replacement_approval_high_water_rollback_detected"
    return ""


def _read_next_packet() -> dict[str, Any]:
    from . import next_session_service

    packet = next_session_service.read_next_session_cache()
    return dict(packet) if isinstance(packet, Mapping) else {}


def _valid_production_close_points(rows: object) -> bool:
    if not isinstance(rows, list) or len(rows) < _MIN_PRODUCTION_CLOSE_POINTS:
        return False
    observed_dates: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) < {"x", "price"}:
            return False
        date_text = str(row.get("x") or "").strip()
        normalized = date_text.replace("-", "")
        if not re.fullmatch(r"[0-9]{8}", normalized):
            return False
        try:
            datetime.strptime(normalized, "%Y%m%d")
        except ValueError:
            return False
        price = row.get("price")
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            return False
        if not math.isfinite(float(price)) or float(price) <= 0:
            return False
        observed_dates.append(normalized)
    return len(set(observed_dates)) == len(observed_dates) and observed_dates == sorted(observed_dates)


def _date_text(value: object) -> str:
    text = str(value or "").strip().replace("-", "")
    if text.endswith(".0"):
        text = text[:-2]
    return text if re.fullmatch(r"[0-9]{8}", text) else ""


def _authoritative_provider_daily_evidence(
    evidence_root: Path,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-read immutable provider Parquet truth and compare the displayed closes."""

    try:
        from .tushare_production_store import (
            is_listed_a_share_code,
            validate_tushare_full_market_production_version,
        )

        verified = validate_tushare_full_market_production_version(
            evidence_root,
            include_frames=True,
        )
    except Exception as exc:
        return {
            "ready": False,
            "blockers": [f"next_session_authoritative_provider_verifier_failed_{type(exc).__name__}"],
        }
    chart = packet.get("chart_payload") if isinstance(packet.get("chart_payload"), Mapping) else {}
    historical = chart.get("historical_points") if isinstance(chart.get("historical_points"), list) else []
    provenance = (
        packet.get("production_replacement_provenance")
        if isinstance(packet.get("production_replacement_provenance"), Mapping)
        else {}
    )
    symbol = str(provenance.get("symbol") or chart.get("symbol") or "").strip().upper()
    frames = verified.get("frames") if isinstance(verified.get("frames"), Mapping) else {}
    daily = frames.get("daily")
    trade_cal = frames.get("trade_cal")
    blockers = [str(item) for item in verified.get("blockers") or [] if str(item)]
    if verified.get("ready") is not True:
        blockers.append("next_session_authoritative_provider_version_missing")
    if not is_listed_a_share_code(symbol) or symbol not in set(verified.get("symbols") or []):
        blockers.append("next_session_authoritative_symbol_not_in_provider_universe")
    dates = [_date_text(row.get("x")) for row in historical if isinstance(row, Mapping)]
    if len(dates) != len(historical) or not dates or any(not value for value in dates):
        blockers.append("next_session_authoritative_close_dates_invalid")
    normalized_daily: list[dict[str, Any]] = []
    normalized_calendar: list[dict[str, Any]] = []
    calendar_as_of_date = _current_shanghai_date().strftime("%Y%m%d")
    authoritative_current_trade_date = ""
    try:
        daily_rows = daily.loc[
            (daily["ts_code"].astype(str).str.upper() == symbol)
            & (daily["trade_date"].map(_date_text).isin(dates)),
            ["ts_code", "trade_date", "close"],
        ]
        for row in daily_rows.to_dict("records"):
            normalized_daily.append(
                {
                    "ts_code": str(row["ts_code"]).upper(),
                    "trade_date": _date_text(row["trade_date"]),
                    "close": round(float(row["close"]), 8),
                }
            )
        normalized_daily.sort(key=lambda row: row["trade_date"])
        calendar_rows = trade_cal.loc[
            (trade_cal["cal_date"].map(_date_text).isin(dates))
            & (trade_cal["is_open"].astype(int) == 1),
            ["cal_date", "is_open"],
        ].drop_duplicates(subset=["cal_date"])
        normalized_calendar = sorted(
            (
                {"cal_date": _date_text(row["cal_date"]), "is_open": int(row["is_open"])}
                for row in calendar_rows.to_dict("records")
            ),
            key=lambda row: row["cal_date"],
        )
        full_calendar = [
            {
                "cal_date": _date_text(row["cal_date"]),
                "is_open": int(row["is_open"]),
            }
            for row in trade_cal[["cal_date", "is_open"]].to_dict("records")
        ]
        calendar_dates = [row["cal_date"] for row in full_calendar if row["cal_date"]]
        open_dates = [
            row["cal_date"]
            for row in full_calendar
            if row["cal_date"] <= calendar_as_of_date and row["is_open"] == 1
        ]
        if not calendar_dates or max(calendar_dates) < calendar_as_of_date:
            blockers.append("next_session_authoritative_calendar_not_current")
        authoritative_current_trade_date = max(open_dates) if open_dates else ""
    except Exception:
        blockers.append("next_session_authoritative_provider_frames_invalid")
    displayed = [
        {
            "trade_date": _date_text(row.get("x")),
            "close": round(float(row.get("price")), 8),
        }
        for row in historical
        if isinstance(row, Mapping)
        and not isinstance(row.get("price"), bool)
        and isinstance(row.get("price"), (int, float))
    ]
    provider_display = [
        {"trade_date": row["trade_date"], "close": row["close"]}
        for row in normalized_daily
    ]
    if displayed != provider_display or len(displayed) < _MIN_PRODUCTION_CLOSE_POINTS:
        blockers.append("next_session_displayed_closes_do_not_match_authoritative_provider_rows")
    if [row["cal_date"] for row in normalized_calendar] != dates:
        blockers.append("next_session_displayed_dates_do_not_match_open_trade_calendar")
    if not dates or dates[-1] != str(verified.get("validated_trade_date") or ""):
        blockers.append("next_session_displayed_data_date_not_current_provider_trade_date")
    if authoritative_current_trade_date != str(verified.get("validated_trade_date") or ""):
        blockers.append("next_session_authoritative_validated_trade_date_stale")
    if any(
        not isinstance(row, Mapping) or row.get("source") != "tushare.daily.close"
        for row in historical
    ):
        blockers.append("next_session_authoritative_close_source_labels_invalid")
    blockers = sorted(set(blockers))
    return {
        "ready": not blockers,
        "blockers": blockers,
        "symbol": symbol,
        "data_date": dates[-1] if dates else "",
        "provider_scope_hash": str(verified.get("scope_hash") or ""),
        "dataset_version_digest": str(verified.get("version_digest") or ""),
        "daily_rows_digest": _digest(normalized_daily) if normalized_daily else "",
        "trade_calendar_digest": _digest(normalized_calendar) if normalized_calendar else "",
        "source_task_call_ledger_digest": str(
            verified.get("official_call_ledger_digest") or ""
        ),
        "official_execution_event_digest": str(
            verified.get("official_execution_event_digest") or ""
        ),
        "source_task_finished_at": str(provenance.get("source_task_finished_at") or ""),
        "provider_receipt_observed_at_utc": str(
            verified.get("official_receipt_observed_at_utc") or ""
        ),
        "provider_receipt_completed_at_utc": str(
            verified.get("official_receipt_completed_at_utc") or ""
        ),
        "authoritative_calendar_as_of_date": calendar_as_of_date,
        "authoritative_current_trade_date": authoritative_current_trade_date,
        "validated_trade_date": str(verified.get("validated_trade_date") or ""),
        "row_count": len(normalized_daily),
    }


def _next_packet_evidence(
    packet: Mapping[str, Any],
    *,
    head_full: str,
    authoritative: Mapping[str, Any],
    source_task: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    chart = packet.get("chart_payload") if isinstance(packet.get("chart_payload"), Mapping) else {}
    summary = packet.get("chart_summary") if isinstance(packet.get("chart_summary"), Mapping) else {}
    maturity = chart.get("chart_maturity") if isinstance(chart.get("chart_maturity"), Mapping) else {}
    contract = chart.get("chart_contract") if isinstance(chart.get("chart_contract"), Mapping) else {}
    coverage = (
        packet.get("next_session_same_packet_signal_capability_coverage")
        if isinstance(packet.get("next_session_same_packet_signal_capability_coverage"), Mapping)
        else {}
    )
    coverage_rows = (
        packet.get("next_session_same_packet_signal_capability_coverage_rows")
        if isinstance(packet.get("next_session_same_packet_signal_capability_coverage_rows"), list)
        else coverage.get("rows")
        if isinstance(coverage.get("rows"), list)
        else []
    )
    historical = chart.get("historical_points") if isinstance(chart.get("historical_points"), list) else []
    provenance = (
        packet.get("production_replacement_provenance")
        if isinstance(packet.get("production_replacement_provenance"), Mapping)
        else {}
    )
    anchor_count = int(maturity.get("scenario_anchor_count") or 0)
    anchored_count = int(maturity.get("scenario_anchored_count") or 0)
    exact_packet = bool(
        packet.get("schema_version") == "next_session_projection.v1"
        and packet.get("packet_key") == "command_center_next_session_projection_packet"
        and chart.get("status") == "ready"
        and chart.get("is_exact_next_session_packet") is True
        and summary.get("is_exact_next_session_packet") is True
    )
    task_finished_time = _production_timestamp(
        source_task.get("finished_at"), assume_shanghai=True
    )
    receipt_observed_time = _production_timestamp(
        authoritative.get("provider_receipt_observed_at_utc")
    )
    receipt_completed_time = _production_timestamp(
        authoritative.get("provider_receipt_completed_at_utc")
    )
    now = datetime.now(timezone.utc)
    freshness_binding = bool(
        task_finished_time
        and receipt_observed_time
        and receipt_completed_time
        and receipt_observed_time <= receipt_completed_time <= task_finished_time
        and task_finished_time <= now + timedelta(minutes=1)
        and receipt_completed_time - receipt_observed_time <= timedelta(hours=6)
        and task_finished_time - receipt_completed_time <= timedelta(minutes=5)
        and now - task_finished_time <= timedelta(hours=24)
        and provenance.get("source_task_finished_at") == source_task.get("finished_at")
        and provenance.get("provider_receipt_observed_at_utc")
        == authoritative.get("provider_receipt_observed_at_utc")
        and provenance.get("provider_receipt_completed_at_utc")
        == authoritative.get("provider_receipt_completed_at_utc")
        and provenance.get("authoritative_calendar_as_of_date")
        == authoritative.get("authoritative_calendar_as_of_date")
        and provenance.get("authoritative_current_trade_date")
        == authoritative.get("authoritative_current_trade_date")
        == authoritative.get("validated_trade_date")
    )
    source_task_binding = bool(
        source_task.get("task_id") == provenance.get("source_task_id")
        and source_task.get("status") == "success"
        and source_task.get("task_type") == "refresh_tushare_facts"
        and source_task.get("progress") == 1.0
        and source_task.get("output_packet_key") == "command_center_tushare_refresh_packet"
        and isinstance(source_task.get("payload_safe"), Mapping)
        and source_task.get("payload_safe", {}).get("acceptance_mode")
        == "full_interface_provider_production"
        and source_task.get("external_calls_triggered") is True
        and source_task.get("tushare_called") is True
        and source_task.get("does_not_execute_trades") is True
        and source_task.get("does_not_modify_strategy_action") is True
        and provenance.get("source_task_payload_digest")
        == _digest(source_task.get("payload_safe") or {})
        and provenance.get("source_task_call_ledger_digest")
        == authoritative.get("source_task_call_ledger_digest")
        == _digest(source_task.get("call_ledger") or [])
        and provenance.get("official_execution_event_digest")
        == authoritative.get("official_execution_event_digest")
        and freshness_binding
    )
    chart_structure_digest = _digest(
        {
            "scenario_series": chart.get("scenario_series") or [],
            "reference_lines": chart.get("reference_lines") or [],
            "operation_zones": chart.get("operation_zones") or [],
        }
    )
    coverage_rows_digest = _digest(coverage_rows) if coverage_rows else ""
    coverage_rows_valid = bool(
        len(coverage_rows) == _REQUIRED_FEATURE_COUNT
        and {str(row.get("coverage_key") or "") for row in coverage_rows if isinstance(row, Mapping)}
        == _REQUIRED_COVERAGE_KEYS
        and all(
            isinstance(row, Mapping)
            and row.get("retained") is True
            and row.get("direct_observation") is True
            and row.get("same_packet") is True
            and row.get("external_calls_triggered") is False
            and row.get("does_not_execute_trades") is True
            and row.get("does_not_modify_strategy_action") is True
            and row.get("does_not_modify_operation_zones") is True
            and row.get("contains_secret") is False
            for row in coverage_rows
        )
    )
    binding_material = {
        "scope": "ltg08_next_session_current_head_production_packet",
        "head_full": head_full,
        "source_task_id": provenance.get("source_task_id"),
        "source_task_payload_digest": provenance.get("source_task_payload_digest"),
        "source_task_call_ledger_digest": authoritative.get("source_task_call_ledger_digest"),
        "official_execution_event_digest": authoritative.get("official_execution_event_digest"),
        "source_task_finished_at": authoritative.get("source_task_finished_at"),
        "provider_receipt_observed_at_utc": authoritative.get(
            "provider_receipt_observed_at_utc"
        ),
        "provider_receipt_completed_at_utc": authoritative.get(
            "provider_receipt_completed_at_utc"
        ),
        "authoritative_calendar_as_of_date": authoritative.get(
            "authoritative_calendar_as_of_date"
        ),
        "authoritative_current_trade_date": authoritative.get(
            "authoritative_current_trade_date"
        ),
        "symbol": authoritative.get("symbol"),
        "data_date": authoritative.get("data_date"),
        "provider_scope_hash": authoritative.get("provider_scope_hash"),
        "dataset_version_digest": authoritative.get("dataset_version_digest"),
        "daily_rows_digest": authoritative.get("daily_rows_digest"),
        "trade_calendar_digest": authoritative.get("trade_calendar_digest"),
        "coverage_rows_digest": coverage_rows_digest,
        "chart_structure_digest": chart_structure_digest,
    }
    binding_digest = _digest(binding_material)
    expected_result_version = f"next-session-prod-{binding_digest[:24]}"
    expected_packet_scope_hash = _digest(
        {**binding_material, "result_version": expected_result_version}
    )
    exact_version_binding = bool(
        coverage_rows_valid
        and provenance.get("coverage_rows_digest") == coverage_rows_digest
        and provenance.get("result_version") == expected_result_version
        and provenance.get("packet_scope_hash") == expected_packet_scope_hash
        and packet.get("coverage_rows_digest") == coverage_rows_digest
        and packet.get("result_version") == expected_result_version
        and packet.get("packet_scope_hash") == expected_packet_scope_hash
        and chart.get("result_version") == expected_result_version
        and chart.get("packet_scope_hash") == expected_packet_scope_hash
        and summary.get("result_version") == expected_result_version
    )
    authoritative_lineage = bool(
        set(provenance) == _PROVENANCE_FIELDS
        and provenance.get("schema_version") == "next_session_production_replacement_provenance.v2"
        and provenance.get("status") == "authoritative_provider_dataset_current_head"
        and provenance.get("head_full") == head_full
        and isinstance(provenance.get("source_task_id"), str)
        and bool(provenance.get("source_task_id"))
        and provenance.get("source_task_status") == "success"
        and source_task_binding
        and all(provenance.get(key) == authoritative.get(key) for key in (
            "symbol",
            "data_date",
            "provider_scope_hash",
            "dataset_version_digest",
            "daily_rows_digest",
            "trade_calendar_digest",
            "source_task_call_ledger_digest",
            "official_execution_event_digest",
            "source_task_finished_at",
            "provider_receipt_observed_at_utc",
            "provider_receipt_completed_at_utc",
            "authoritative_calendar_as_of_date",
            "authoritative_current_trade_date",
        ))
        and provenance.get("provider_backed") is True
        and provenance.get("authoritative_dataset") is True
        and provenance.get("trade_calendar_validated") is True
        and provenance.get("synthetic_fixture") is False
        and provenance.get("local_preview") is False
        and exact_version_binding
    )
    real_close = bool(
        chart.get("uses_real_daily_close") is True
        and summary.get("uses_real_daily_close") is True
        and maturity.get("has_real_60d_close") is True
        and _valid_production_close_points(historical)
        and authoritative.get("ready") is True
        and authoritative_lineage
    )
    production_maturity = bool(
        maturity.get("status") in {"ready", "production_ready"}
        and anchor_count > 0
        and anchor_count == anchored_count
        and len(chart.get("reference_lines") or []) > 0
        and len(chart.get("operation_zones") or []) > 0
    )
    retained = bool(
        coverage.get("schema_version") == "next_session_same_packet_signal_capability_coverage.v1"
        and coverage.get("status") == "same_packet_signal_capability_coverage_ready"
        and coverage.get("same_packet") is True
        and coverage.get("lineage_bound") is True
        and coverage.get("direct_evidence_ready") is True
        and coverage.get("required_feature_group_count") == _REQUIRED_FEATURE_COUNT
        and coverage.get("retained_feature_group_count") == _REQUIRED_FEATURE_COUNT
        and coverage.get("missing_feature_groups") == []
        and coverage_rows_valid
    )
    safe = bool(
        contract.get("cache_only") is True
        and contract.get("external_calls_triggered") is False
        and contract.get("tushare_called") is False
        and contract.get("deepseek_called") is False
        and contract.get("github_called") is False
        and contract.get("does_not_execute_trades") is True
        and contract.get("frontend_computes_trade_action") is False
        and contract.get("does_not_modify_action") is True
        and contract.get("does_not_modify_operation_zones") is True
        and packet.get("contains_secret") is not True
    )
    material = {
        "schema_version": packet.get("schema_version"),
        "packet_key": packet.get("packet_key"),
        "status": packet.get("status"),
        "chart_payload": chart,
        "chart_summary": summary,
        "retained_coverage": coverage,
        "production_replacement_provenance": provenance,
        "authoritative_provider_evidence": {
            key: authoritative.get(key)
            for key in (
                "symbol",
                "data_date",
                "provider_scope_hash",
                "dataset_version_digest",
                "daily_rows_digest",
                "trade_calendar_digest",
                "validated_trade_date",
                "row_count",
            )
        },
    }
    blockers: list[str] = []
    if not exact_packet:
        blockers.append("next_session_exact_packet_missing")
    if not real_close:
        blockers.append("next_session_real_close_60_sessions_missing")
    if authoritative.get("ready") is not True:
        blockers.extend(str(item) for item in authoritative.get("blockers") or [])
    if not authoritative_lineage:
        blockers.append("next_session_authoritative_current_head_lineage_missing_or_invalid")
    if not exact_version_binding:
        blockers.append("next_session_exact_result_version_scope_coverage_binding_invalid")
    if not production_maturity:
        blockers.append("next_session_production_maturity_missing")
    if not retained:
        blockers.append("next_session_same_packet_9_of_9_coverage_missing")
    if not safe:
        blockers.append("next_session_read_only_safety_boundary_invalid")
    return {
        "ready": not blockers,
        "digest": _digest(material) if not blockers else "",
        "exact_packet": exact_packet,
        "real_close_60_sessions": real_close,
        "production_maturity": production_maturity,
        "same_packet_coverage_9_of_9": retained,
        "safe_boundary": safe,
        "authoritative_provider_dataset": authoritative.get("ready") is True,
        "authoritative_current_head_lineage": authoritative_lineage,
        "immutable_source_task_status_verified": source_task_binding,
        "exact_result_version_scope_coverage_binding": exact_version_binding,
        "historical_point_count": len(historical),
        "scenario_anchor_count": anchor_count,
        "scenario_anchored_count": anchored_count,
    }, blockers


def _motion_evidence(root: Path, head_full: str, project_root: Path) -> tuple[dict[str, Any], list[str]]:
    result = motion_evidence_service.validate_current_motion_evidence(
        root,
        expected_head_full=head_full,
        project_root=project_root,
    )
    next_rows = (
        result.get("validated_route_rows", {}).get("#next-session-chart", [])
        if isinstance(result.get("validated_route_rows"), Mapping)
        else []
    )
    modes = {row.get("reduced_motion") for row in next_rows if isinstance(row, Mapping)}
    viewports = {
        (bool(row.get("reduced_motion")), str(row.get("viewport") or ""))
        for row in next_rows
        if isinstance(row, Mapping)
    }
    route_ready = bool(
        len(next_rows) == 8
        and modes == {False, True}
        and all((mode, viewport) in viewports for mode in (False, True) for viewport in _REQUIRED_VIEWPORTS)
        and all(
            row.get("status") == "passed"
            and row.get("visual_qa_complete") is True
            and row.get("performance_trace_complete") is True
            and row.get("long_task_over_50ms_count") == 0
            and row.get("clipped_count") == 0
            for row in next_rows
            if isinstance(row, Mapping)
        )
    )
    material = {
        key: result.get(key)
        for key in (
            "schema_version",
            "status",
            "expected_head_full",
            "frontend_source_digest",
            "build_identity_digest",
            "dist_manifest_digest",
            "package_identity_digest",
            "normal_run_id",
            "reduced_run_id",
        )
    }
    material["next_route_rows_digest"] = _digest(next_rows) if next_rows else ""
    blockers = list(result.get("blockers") or [])
    if result.get("motion_current_head_pair_verified") is not True or not route_ready:
        blockers.append("next_session_current_head_motion_pair_missing_or_incomplete")
    return {
        "ready": not blockers,
        "digest": _digest(material) if not blockers else "",
        "normal_run_id": result.get("normal_run_id") or "",
        "reduced_run_id": result.get("reduced_run_id") or "",
        "next_route_row_count": len(next_rows),
    }, sorted(set(str(item) for item in blockers if item))


def _streamlit_evidence(root: Path, head_full: str, project_root: Path) -> tuple[dict[str, Any], list[str]]:
    result = streamlit_retirement_evidence_service.validate_streamlit_primary_retirement(
        root,
        expected_head_full=head_full,
        project_root=project_root,
    )
    ready = bool(
        result.get("streamlit_primary_retired") is True
        and result.get("head_full") == head_full
        and result.get("fallback_disposition") == "admin_debug_only_retained"
        and result.get("route_count") == 6
        and result.get("visual_review_required") is True
        and bool(result.get("visual_review_id"))
    )
    material = {
        key: result.get(key)
        for key in (
            "schema_version",
            "status",
            "head_full",
            "fallback_disposition",
            "route_count",
            "viewport_count",
            "qa_matrix_count",
            "artifact_set_sha256",
            "source_contract_digest",
            "route_matrix_digest",
            "visual_review_id",
        )
    }
    blockers = list(result.get("blockers") or [])
    if not ready:
        blockers.append("ltg10_sealed_visual_retirement_not_current")
    return {
        "ready": not blockers,
        "digest": _digest(material) if not blockers else "",
        "visual_review_event_id": result.get("visual_review_id") or "",
        "fallback_disposition": result.get("fallback_disposition") or "",
    }, sorted(set(str(item) for item in blockers if item))


def _remote_ci_evidence(root: Path, head_full: str) -> tuple[dict[str, Any], list[str]]:
    release = release_promotion_service.validate_production_release_promotion(
        root,
        expected_head_full=head_full,
    )
    prerequisites = release_promotion_service.validate_release_prerequisites(
        root,
        expected_head_full=head_full,
    )
    rows = prerequisites.get("rows") if isinstance(prerequisites.get("rows"), list) else []
    remote = next(
        (row for row in rows if isinstance(row, Mapping) and row.get("evidence_key") == "remote_ci"),
        {},
    )
    ready = bool(
        release.get("release_promotion_current_head") is True
        and release.get("head_full") == head_full
        and _SHA256.fullmatch(str(release.get("event_id") or ""))
        and remote.get("ready") is True
        and _SHA256.fullmatch(str(remote.get("semantic_digest") or ""))
        and str(prerequisites.get("remote_run_id") or "").isdigit()
        and str(prerequisites.get("remote_artifact_digest") or "").startswith("sha256:")
    )
    blockers = list(release.get("blockers") or []) + list(remote.get("blockers") or [])
    if not ready:
        blockers.append("matching_remote_ci_current_head_missing")
    return {
        "ready": ready,
        "digest": str(remote.get("semantic_digest") or "") if ready else "",
        "run_id": str(prerequisites.get("remote_run_id") or "") if ready else "",
        "artifact_digest": str(prerequisites.get("remote_artifact_digest") or "") if ready else "",
        "release_promotion_event_id": str(release.get("event_id") or "") if ready else "",
    }, sorted(set(str(item) for item in blockers if item))


def _collect_prerequisites(
    evidence_root: Path,
    *,
    expected_head_full: str,
    project_root: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    actual = _current_head(project_root)
    if not expected_head_full or actual != expected_head_full:
        blockers.append("next_session_replacement_expected_head_not_current")
    packet = _read_next_packet()
    authoritative = _authoritative_provider_daily_evidence(evidence_root, packet)
    provenance = (
        packet.get("production_replacement_provenance")
        if isinstance(packet.get("production_replacement_provenance"), Mapping)
        else {}
    )
    source_task = _read_immutable_source_task_status(
        evidence_root,
        str(provenance.get("source_task_id") or ""),
    )
    packet_fact, packet_blockers = _next_packet_evidence(
        packet,
        head_full=expected_head_full,
        authoritative=authoritative,
        source_task=source_task,
    )
    motion_fact, motion_blockers = _motion_evidence(evidence_root, expected_head_full, project_root)
    streamlit_fact, streamlit_blockers = _streamlit_evidence(evidence_root, expected_head_full, project_root)
    remote_fact, remote_blockers = _remote_ci_evidence(evidence_root, expected_head_full)
    blockers.extend(packet_blockers + motion_blockers + streamlit_blockers + remote_blockers)
    material = {
        "scope": SCOPE,
        "head_full": expected_head_full,
        "next_packet_digest": packet_fact.get("digest") or "",
        "motion_pair_digest": motion_fact.get("digest") or "",
        "streamlit_retirement_digest": streamlit_fact.get("digest") or "",
        "remote_ci_digest": remote_fact.get("digest") or "",
        "remote_run_id": remote_fact.get("run_id") or "",
        "remote_artifact_digest": remote_fact.get("artifact_digest") or "",
        "release_promotion_event_id": remote_fact.get("release_promotion_event_id") or "",
    }
    blockers = sorted(set(blockers))
    return {
        "ready": not blockers,
        "head_full": expected_head_full,
        "material": material,
        "semantic_digest": _digest(material) if not blockers else "",
        "next_packet": packet_fact,
        "motion_pair": motion_fact,
        "streamlit_retirement": streamlit_fact,
        "remote_ci": remote_fact,
        "blockers": blockers,
    }


def _event_without_mac(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: event.get(key) for key in sorted(_EVENT_FIELDS - {"event_mac"})}


def _load_chain(evidence_root: Path | str, secret: bytes) -> tuple[list[dict[str, Any]], str]:
    _, events_root, _, state_path = _paths(evidence_root)
    if not _directory_valid(events_root):
        return [], "next_session_replacement_events_directory_invalid"
    try:
        paths = sorted(events_root.iterdir())
    except OSError:
        return [], "next_session_replacement_events_directory_invalid"
    if any(not _EVENT_FILE.fullmatch(path.name) for path in paths):
        return [], "next_session_replacement_event_set_invalid"
    events: list[dict[str, Any]] = []
    previous_mac = ""
    previous_timestamp = ""
    for sequence, path in enumerate(paths, start=1):
        if path.name != f"{sequence:08d}.json":
            return [], "next_session_replacement_event_sequence_invalid"
        event = _read_json(path)
        if set(event) != _EVENT_FIELDS:
            return [], "next_session_replacement_event_schema_invalid"
        unsigned = _event_without_mac(event)
        expected_id = _digest({key: value for key, value in unsigned.items() if key != "event_id"})
        if not (
            event.get("schema_version") == EVENT_SCHEMA
            and event.get("status") == "next_session_production_replacement_promoted"
            and event.get("sequence_no") == sequence
            and event.get("scope") == SCOPE
            and _normalize_head(event.get("head_full")) == event.get("head_full")
            and all(
                _SHA256.fullmatch(str(event.get(field) or ""))
                for field in (
                    "event_id",
                    "semantic_digest",
                    "next_packet_digest",
                    "motion_pair_digest",
                    "streamlit_retirement_digest",
                    "remote_ci_digest",
                    "release_promotion_event_id",
                    "approval_review_id",
                    "approval_ticket_id",
                    "approval_nonce_digest",
                    "event_mac",
                )
            )
            and str(event.get("remote_run_id") or "").isdigit()
            and str(event.get("remote_artifact_digest") or "").startswith("sha256:")
            and event.get("approved_by_user") is True
            and _valid_timestamp(event.get("recorded_at_utc"))
            and (not previous_timestamp or str(event["recorded_at_utc"]) >= previous_timestamp)
            and event.get("previous_event_mac") == previous_mac
            and event.get("event_id") == expected_id
            and hmac.compare_digest(str(event.get("event_mac") or ""), _mac(secret, unsigned))
        ):
            return [], "next_session_replacement_event_authentication_failed"
        events.append(event)
        previous_mac = str(event["event_mac"])
        previous_timestamp = str(event["recorded_at_utc"])
    if not events:
        return [], "next_session_replacement_event_missing"
    state = _read_json(state_path)
    if set(state) != _STATE_FIELDS:
        return [], "next_session_replacement_state_invalid"
    unsigned_state = {key: state.get(key) for key in sorted(_STATE_FIELDS - {"state_mac"})}
    latest = events[-1]
    if not (
        state.get("schema_version") == STATE_SCHEMA
        and state.get("sequence_no") == latest.get("sequence_no")
        and state.get("event_id") == latest.get("event_id")
        and state.get("event_mac") == latest.get("event_mac")
        and state.get("updated_at_utc") == latest.get("recorded_at_utc")
        and _SHA256.fullmatch(str(state.get("state_mac") or ""))
        and hmac.compare_digest(str(state.get("state_mac") or ""), _mac(secret, unsigned_state))
    ):
        return [], "next_session_replacement_state_authentication_failed"
    return events, ""


def _public_summary(
    *,
    prerequisites: Mapping[str, Any],
    event: Mapping[str, Any] | None,
    blockers: list[str],
    evidence_root: Path | str,
) -> dict[str, Any]:
    trust = next_session_external_promotion_service.validate_current_promotion(
        prerequisites,
        evidence_root=evidence_root,
    )
    blockers = sorted(set([*blockers, *(trust.get("blockers") or [])]))
    if trust.get("external_approval_verified") is not True:
        blockers.append("external_trusted_approval_capability_unavailable")
    if trust.get("rollback_resistant_high_water_verified") is not True:
        blockers.append("rollback_resistant_high_water_unavailable")
    blockers = sorted(set(blockers))
    ready = bool(prerequisites.get("ready") is True and trust.get("ready") is True and not blockers)
    trusted_event = trust.get("event") if isinstance(trust.get("event"), Mapping) else {}
    if ready:
        event = trusted_event
    semantic_digest = str(prerequisites.get("semantic_digest") or "")
    review_id = (
        _approval_review_id(
            head_full=str(prerequisites.get("head_full") or ""),
            semantic_digest=semantic_digest,
        )
        if prerequisites.get("ready") is True and semantic_digest
        else ""
    )
    return {
        "schema_version": VALIDATION_SCHEMA,
        "status": (
            "next_session_production_replacement_promoted_current_head"
            if ready
            else "next_session_production_replacement_blocked"
        ),
        "scope": SCOPE,
        "head_full": prerequisites.get("head_full") or "",
        "production_replacement_complete": ready,
        "next_session_production_replacement": ready,
        "event_id": event.get("event_id") if ready and event else "",
        "sequence_no": event.get("sequence_no") if ready and event else 0,
        "next_packet_digest": event.get("next_packet_digest") if ready and event else "",
        "motion_pair_digest": event.get("motion_pair_digest") if ready and event else "",
        "streamlit_retirement_digest": event.get("streamlit_retirement_digest") if ready and event else "",
        "remote_ci_digest": event.get("remote_ci_digest") if ready and event else "",
        "remote_run_id": event.get("remote_run_id") if ready and event else "",
        "remote_artifact_digest": event.get("remote_artifact_digest") if ready and event else "",
        "release_promotion_event_id": event.get("release_promotion_event_id") if ready and event else "",
        "approval_review_id": event.get("approval_review_id") if ready and event else review_id,
        "approval_semantic_digest": semantic_digest,
        "out_of_band_approval_ticket_required": True,
        "approval_ticket_id": event.get("approval_id") if ready and event else "",
        "approval_nonce_digest": event.get("approval_nonce_digest") if ready and event else "",
        "next_packet_evidence": prerequisites.get("next_packet") or {},
        "motion_pair_evidence": prerequisites.get("motion_pair") or {},
        "streamlit_retirement_evidence": prerequisites.get("streamlit_retirement") or {},
        "remote_ci_evidence": prerequisites.get("remote_ci") or {},
        "blockers": blockers,
        "promotion_proposal": trust.get("proposal") or {},
        "external_trusted_approval_verified": trust.get("external_approval_verified") is True,
        "rollback_resistant_high_water_verified": (
            trust.get("rollback_resistant_high_water_verified") is True
        ),
        "read_only": True,
        "writes_storage": False,
        "creates_task": False,
        "opens_streamlit": False,
        "opens_browser": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_operation_zones": True,
        "contains_secret": False,
    }


def validate_next_session_production_replacement(
    evidence_root: Path | str = EVIDENCE_ROOT,
    *,
    expected_head_full: str | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Read-only local-QA validation; production remains fail-closed."""

    root = Path(evidence_root).expanduser().absolute()
    head_full = _normalize_head(expected_head_full) if expected_head_full is not None else _current_head(project_root)
    symlink_blocker = _evidence_tree_symlink_blocker(root)
    prerequisites = (
        _collect_prerequisites(root, expected_head_full=head_full, project_root=project_root)
        if not symlink_blocker
        else {
            "ready": False,
            "head_full": head_full,
            "semantic_digest": "",
            "next_packet": {},
            "motion_pair": {},
            "streamlit_retirement": {},
            "remote_ci": {},
            "blockers": [symlink_blocker],
        }
    )
    blockers = list(prerequisites.get("blockers") or [])
    return _public_summary(
        prerequisites=prerequisites,
        event=None,
        blockers=blockers,
        evidence_root=root,
    )


def promote_next_session_production_replacement(
    payload: Any = None,
    *,
    evidence_root: Path | str = EVIDENCE_ROOT,
    expected_head_full: str | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Fail closed without an external approval and rollback-resistant anchor."""

    request = dict(payload) if isinstance(payload, Mapping) else {}
    approved = set(request) == {"approved_by_user"} and request.get("approved_by_user") is True
    root = Path(evidence_root).expanduser().absolute()
    head_full = _normalize_head(expected_head_full) if expected_head_full is not None else _current_head(project_root)
    symlink_blocker = _evidence_tree_symlink_blocker(root)
    prerequisites = (
        _collect_prerequisites(root, expected_head_full=head_full, project_root=project_root)
        if not symlink_blocker
        else {
            "ready": False,
            "head_full": head_full,
            "semantic_digest": "",
            "next_packet": {},
            "motion_pair": {},
            "streamlit_retirement": {},
            "remote_ci": {},
            "blockers": [symlink_blocker],
        }
    )
    blockers = list(prerequisites.get("blockers") or [])
    if not approved:
        blockers.insert(0, "explicit_user_next_session_replacement_approval_required")
    write_result = next_session_external_promotion_service.append_promotion_event(
        request,
        prerequisites,
        evidence_root=root,
    )
    blockers.extend(str(item) for item in write_result.get("blockers") or [])
    result = _public_summary(
        prerequisites=prerequisites,
        event=write_result.get("event") if isinstance(write_result.get("event"), Mapping) else None,
        blockers=blockers,
        evidence_root=root,
    )
    result.update(
        {
            "promotion_written": write_result.get("promotion_written") is True,
            "idempotent_replay": False,
            "read_only": False,
            "writes_storage": write_result.get("promotion_written") is True,
            "local_qa_only": write_result.get("promotion_written") is not True,
            "production_eligible": result.get("production_replacement_complete") is True,
        }
    )
    return result


__all__ = [
    "promote_next_session_production_replacement",
    "record_next_session_replacement_approval_ticket",
    "validate_next_session_production_replacement",
]
