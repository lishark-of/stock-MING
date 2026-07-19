#!/usr/bin/env python3
"""Verify a downloaded push-gate artifact and import its receipt byte-for-byte.

This tool is deliberately offline.  GitHub metadata and the downloaded ZIP are
inputs; it never fetches either one.  The verified embedded local-gate receipt
is copied without JSON reserialization so later validators can bind the exact
artifact bytes that were reviewed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile
from typing import Any, Mapping
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services import release_promotion_service  # noqa: E402


SCHEMA_VERSION = "command_center_3_remote_push_gate_artifact_import_receipt.v1"
EXPECTED_ARTIFACT_PREFIX = "command-center-3-push-gate-evidence-"
EMBEDDED_RECEIPT_NAME = "command-center-3-local-push-gate-run-receipt.json"
REQUIRED_GREEN_ENTRIES = frozenset(
    {
        "command-center-3-push-gate.log",
        "command-center-3-push-gate-report.md",
        EMBEDDED_RECEIPT_NAME,
    }
)
MAX_ENTRY_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
IMPORT_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "scope",
        "imported_at_utc",
        "receipt_writer",
        "head_full",
        "run_id",
        "artifact_id",
        "artifact_name",
        "artifact_size_bytes",
        "artifact_metadata_digest",
        "artifact_digest",
        "artifact_archive_sha256",
        "artifact_archive_size_bytes",
        "artifact_digest_matches_metadata",
        "artifact_size_matches_metadata",
        "entry_manifest_digest",
        "entry_names",
        "embedded_local_gate_receipt_sha256",
        "embedded_local_gate_receipt_size_bytes",
        "imported_local_gate_receipt_sha256",
        "imported_local_gate_receipt_size_bytes",
        "local_receipt_relative_path",
        "artifact_receipt_bytes_identical",
        "safe_archive_verified",
        "local_gate_schema_verified",
        "writes_local_receipt",
        "network_calls_triggered",
        "external_calls_triggered",
        "tushare_called",
        "deepseek_called",
        "github_called",
        "github_api_called",
        "does_not_execute_trades",
        "does_not_modify_strategy_action",
        "contains_secret",
    }
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256_bytes(value: bytes, *, prefix: bool = False) -> str:
    digest = hashlib.sha256(value).hexdigest()
    return f"sha256:{digest}" if prefix else digest


def _valid_head(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 40 and text == text.lower() and all(c in "0123456789abcdef" for c in text)


def _valid_prefixed_sha256(value: Any) -> bool:
    text = str(value or "")
    return bool(
        text.startswith("sha256:")
        and len(text) == 71
        and text == text.lower()
        and all(c in "0123456789abcdef" for c in text[7:])
    )


def _resolve_output(path_text: str | None, default: Path) -> Path:
    raw = Path(path_text) if path_text else default
    candidate = raw if raw.is_absolute() else PROJECT_ROOT / raw
    project_root = PROJECT_ROOT.resolve(strict=True)
    lexical_output = Path(os.path.abspath(candidate))
    try:
        relative = lexical_output.relative_to(project_root)
    except ValueError:
        return lexical_output.resolve(strict=False)
    if not str(relative).startswith(".stock_ming_3/"):
        raise ValueError("in-repository outputs must stay under .stock_ming_3/")
    current = project_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("in-repository output path must not contain symlinks")
    output = lexical_output.resolve(strict=False)
    if not output.is_relative_to(project_root):
        raise ValueError("in-repository output path must not escape through symlinks")
    return output


def _load_metadata(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("artifact metadata is unreadable") from exc
    if isinstance(value, Mapping) and isinstance(value.get("artifact"), Mapping):
        value = value["artifact"]
    if not isinstance(value, Mapping):
        raise ValueError("artifact metadata must be an object")
    return dict(value)


def _metadata_material(
    metadata: Mapping[str, Any], *, run_id: int, head_full: str
) -> dict[str, Any]:
    workflow_run = metadata.get("workflow_run")
    if not isinstance(workflow_run, Mapping):
        raise ValueError("artifact metadata workflow_run is missing")
    artifact_id = metadata.get("id")
    size_bytes = metadata.get("size_in_bytes")
    expected_name = f"{EXPECTED_ARTIFACT_PREFIX}{run_id}"
    material = {
        "artifact_id": artifact_id,
        "artifact_name": metadata.get("name"),
        "artifact_size_bytes": size_bytes,
        "artifact_digest": metadata.get("digest"),
        "artifact_expired": metadata.get("expired"),
        "workflow_run_id": workflow_run.get("id"),
        "workflow_head_branch": workflow_run.get("head_branch"),
        "workflow_head_sha": workflow_run.get("head_sha"),
    }
    if not (
        type(artifact_id) is int
        and artifact_id > 0
        and type(size_bytes) is int
        and 0 < size_bytes <= MAX_ARCHIVE_BYTES
        and material["artifact_name"] == expected_name
        and _valid_prefixed_sha256(material["artifact_digest"])
        and material["artifact_expired"] is False
        and type(material["workflow_run_id"]) is int
        and material["workflow_run_id"] == run_id
        and material["workflow_head_branch"] == "main"
        and material["workflow_head_sha"] == head_full
    ):
        raise ValueError("artifact metadata identity does not match the reviewed run and HEAD")
    return material


def _safe_zip_entry_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    pure = PurePosixPath(name)
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    if (
        not name
        or info.is_dir()
        or pure.is_absolute()
        or len(pure.parts) != 1
        or any(part in {"", ".", ".."} for part in pure.parts)
        or "\\" in name
        or info.flag_bits & 0x1
        or file_type == stat.S_IFLNK
        or info.file_size < 0
        or info.file_size > MAX_ENTRY_BYTES
        or info.compress_size < 0
        or info.compress_size > MAX_ENTRY_BYTES
    ):
        raise ValueError("artifact ZIP contains an unsafe entry")
    return name


def _read_verified_archive(archive_bytes: bytes) -> tuple[dict[str, bytes], str]:
    if not (0 < len(archive_bytes) <= MAX_ARCHIVE_BYTES):
        raise ValueError("artifact ZIP size is invalid")
    entries: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            infos = archive.infolist()
            names = [_safe_zip_entry_name(info) for info in infos]
            if len(names) != len(set(names)) or set(names) != set(REQUIRED_GREEN_ENTRIES):
                raise ValueError("artifact ZIP entry set is not the exact green evidence set")
            if sum(info.file_size for info in infos) > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise ValueError("artifact ZIP uncompressed size exceeds the safety limit")
            for info in infos:
                data = archive.read(info)
                if len(data) != info.file_size or not data:
                    raise ValueError("artifact ZIP entry readback is incomplete")
                entries[info.filename] = data
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError("artifact ZIP is corrupt or unreadable") from exc
    manifest = [
        {"name": name, "size_bytes": len(entries[name]), "sha256": _sha256_bytes(entries[name])}
        for name in sorted(entries)
    ]
    return entries, _canonical_digest({"entries": manifest})


def _validate_embedded_local_receipt(receipt_bytes: bytes, head_full: str) -> dict[str, Any]:
    try:
        value = json.loads(receipt_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("embedded local gate receipt is not valid UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("embedded local gate receipt must be an object")
    validation = release_promotion_service._validate_local_gate(dict(value), head_full)
    if validation.get("ready") is not True:
        raise ValueError("embedded local gate receipt failed the formal current-HEAD validator")
    return dict(value)


def _atomic_write_exact(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temp_path.unlink(missing_ok=True)


def validate_import_receipt(
    receipt: Any,
    *,
    head_full: str,
    run_id: int,
    artifact_name: str,
    artifact_digest: str,
    imported_local_receipt_bytes: bytes,
) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if not isinstance(receipt, Mapping) or set(receipt) != set(IMPORT_RECEIPT_FIELDS):
        return False, ["artifact_import_receipt_schema_invalid"]
    exact_sha = _sha256_bytes(imported_local_receipt_bytes)
    expected_true = (
        "artifact_digest_matches_metadata",
        "artifact_size_matches_metadata",
        "artifact_receipt_bytes_identical",
        "safe_archive_verified",
        "local_gate_schema_verified",
        "writes_local_receipt",
    )
    expected_false = (
        "network_calls_triggered",
        "external_calls_triggered",
        "tushare_called",
        "deepseek_called",
        "github_called",
        "github_api_called",
        "contains_secret",
    )
    if not (
        receipt.get("schema_version") == SCHEMA_VERSION
        and receipt.get("status") == "remote_push_gate_artifact_import_verified"
        and receipt.get("scope") == "offline_downloaded_push_gate_artifact_byte_import"
        and receipt.get("receipt_writer") == "scripts/import_remote_push_gate_artifact.py"
        and receipt.get("head_full") == head_full
        and receipt.get("run_id") == run_id
        and receipt.get("artifact_name") == artifact_name
        and receipt.get("artifact_digest") == artifact_digest
        and receipt.get("artifact_archive_sha256") == artifact_digest
        and type(receipt.get("artifact_id")) is int
        and receipt.get("artifact_id") > 0
        and type(receipt.get("artifact_size_bytes")) is int
        and receipt.get("artifact_size_bytes") > 0
        and receipt.get("artifact_size_bytes") == receipt.get("artifact_archive_size_bytes")
        and _valid_prefixed_sha256(receipt.get("artifact_digest"))
        and all(receipt.get(field) is True for field in expected_true)
        and all(receipt.get(field) is False for field in expected_false)
        and receipt.get("does_not_execute_trades") is True
        and receipt.get("does_not_modify_strategy_action") is True
        and receipt.get("entry_names") == sorted(REQUIRED_GREEN_ENTRIES)
        and receipt.get("embedded_local_gate_receipt_sha256") == exact_sha
        and receipt.get("imported_local_gate_receipt_sha256") == exact_sha
        and receipt.get("embedded_local_gate_receipt_size_bytes") == len(imported_local_receipt_bytes)
        and receipt.get("imported_local_gate_receipt_size_bytes") == len(imported_local_receipt_bytes)
    ):
        blockers.append("artifact_import_receipt_semantic_binding_invalid")
    for field in (
        "artifact_metadata_digest",
        "entry_manifest_digest",
        "embedded_local_gate_receipt_sha256",
        "imported_local_gate_receipt_sha256",
    ):
        value = str(receipt.get(field) or "")
        if len(value) != 64 or value != value.lower() or any(c not in "0123456789abcdef" for c in value):
            blockers.append("artifact_import_receipt_digest_invalid")
            break
    return not blockers, blockers


def import_artifact(args: argparse.Namespace) -> dict[str, Any]:
    head_full = str(args.head_full or "").lower()
    if not _valid_head(head_full) or type(args.run_id) is not int or args.run_id <= 0:
        raise ValueError("--head-full and --run-id must be exact current-run identities")
    archive_path = Path(args.artifact_zip).expanduser().resolve(strict=True)
    metadata = _load_metadata(Path(args.artifact_metadata).expanduser().resolve(strict=True))
    metadata_material = _metadata_material(metadata, run_id=args.run_id, head_full=head_full)
    archive_bytes = archive_path.read_bytes()
    archive_digest = _sha256_bytes(archive_bytes, prefix=True)
    if archive_digest != metadata_material["artifact_digest"]:
        raise ValueError("downloaded artifact ZIP digest does not match GitHub metadata")
    if len(archive_bytes) != metadata_material["artifact_size_bytes"]:
        raise ValueError("downloaded artifact ZIP size does not match GitHub metadata")
    entries, entry_manifest_digest = _read_verified_archive(archive_bytes)
    embedded = entries[EMBEDDED_RECEIPT_NAME]
    _validate_embedded_local_receipt(embedded, head_full)
    local_output = _resolve_output(
        args.local_receipt_output,
        PROJECT_ROOT / ".stock_ming_3" / "release_gate" / "local_push_gate_run_receipt.json",
    )
    _atomic_write_exact(local_output, embedded)
    imported = local_output.read_bytes()
    if not hmac.compare_digest(imported, embedded):
        raise ValueError("imported local gate receipt is not byte-identical to the artifact")
    relative_path = (
        str(local_output.relative_to(PROJECT_ROOT))
        if local_output.is_relative_to(PROJECT_ROOT)
        else str(local_output)
    )
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "remote_push_gate_artifact_import_verified",
        "scope": "offline_downloaded_push_gate_artifact_byte_import",
        "imported_at_utc": _now_iso(),
        "receipt_writer": "scripts/import_remote_push_gate_artifact.py",
        "head_full": head_full,
        "run_id": args.run_id,
        "artifact_id": metadata_material["artifact_id"],
        "artifact_name": metadata_material["artifact_name"],
        "artifact_size_bytes": metadata_material["artifact_size_bytes"],
        "artifact_metadata_digest": _canonical_digest(metadata_material),
        "artifact_digest": metadata_material["artifact_digest"],
        "artifact_archive_sha256": archive_digest,
        "artifact_archive_size_bytes": len(archive_bytes),
        "artifact_digest_matches_metadata": True,
        "artifact_size_matches_metadata": True,
        "entry_manifest_digest": entry_manifest_digest,
        "entry_names": sorted(entries),
        "embedded_local_gate_receipt_sha256": _sha256_bytes(embedded),
        "embedded_local_gate_receipt_size_bytes": len(embedded),
        "imported_local_gate_receipt_sha256": _sha256_bytes(imported),
        "imported_local_gate_receipt_size_bytes": len(imported),
        "local_receipt_relative_path": relative_path,
        "artifact_receipt_bytes_identical": True,
        "safe_archive_verified": True,
        "local_gate_schema_verified": True,
        "writes_local_receipt": True,
        "network_calls_triggered": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    ready, blockers = validate_import_receipt(
        receipt,
        head_full=head_full,
        run_id=args.run_id,
        artifact_name=str(metadata_material["artifact_name"]),
        artifact_digest=str(metadata_material["artifact_digest"]),
        imported_local_receipt_bytes=imported,
    )
    if not ready:
        raise ValueError(f"artifact import receipt failed readback: {blockers}")
    receipt_output = _resolve_output(
        args.output,
        PROJECT_ROOT / ".stock_ming_3" / "release_gate" / "remote_push_gate_artifact_import_receipt.json",
    )
    _atomic_write_exact(
        receipt_output,
        (json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return {**receipt, "receipt_path": str(receipt_output)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--artifact-metadata", required=True)
    parser.add_argument("--head-full", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--local-receipt-output")
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    try:
        result = import_artifact(parse_args())
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "remote_push_gate_artifact_import_blocked", "error_safe": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "receipt_path": result["receipt_path"],
                "head_full": result["head_full"],
                "run_id": result["run_id"],
                "artifact_id": result["artifact_id"],
                "artifact_digest": result["artifact_digest"],
                "artifact_receipt_bytes_identical": True,
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
