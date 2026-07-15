"""Disk-backed verifier for unsigned Tauri production-package evidence.

The existing packaged-runtime smoke receipts are useful L3 observations, but
they intentionally never claim production completion.  This module is the
shared, read-only verifier used by closeout and by the explicit promotion CLI:
it re-hashes the package on disk, binds online/offline evidence to the same
HEAD and artifact set, and only then writes an immutable manifest/pointer.
Developer ID signing and notarization remain independent facts.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
PACKAGE_ROOT = EVIDENCE_ROOT / "desktop_runtime"
BUILD_RECEIPT_PATH = PACKAGE_ROOT / "tauri_build_receipt.json"
ONLINE_SMOKE_PATH = PACKAGE_ROOT / "tauri_packaged_runtime_online_smoke.json"
OFFLINE_SMOKE_PATH = PACKAGE_ROOT / "tauri_packaged_runtime_offline_smoke.json"
MANIFEST_PATH = PACKAGE_ROOT / "tauri_production_package_manifest.json"
POINTER_PATH = PACKAGE_ROOT / "tauri_production_package_pointer.json"
MANIFEST_SCHEMA = "tauri_production_package_manifest.v1"
POINTER_SCHEMA = "tauri_production_package_pointer.v1"
FIXED_APP_RELATIVE = Path(
    "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app"
)
FIXED_DMG_RELATIVE = Path(
    "desktop/src-tauri/target/release/bundle/dmg/stock-MING Command Center_3.0.0_aarch64.dmg"
)
FIXED_EXECUTABLE_NAME = "stock_ming_command_center"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_fingerprint(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    file_count = 0
    for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
        relative = child.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        if child.is_symlink():
            digest.update(b"L")
            digest.update(os.readlink(child).encode("utf-8", errors="replace"))
            continue
        if not child.is_file():
            digest.update(b"D")
            continue
        digest.update(b"F")
        file_count += 1
        size += child.stat().st_size
        with child.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return {"sha256": digest.hexdigest() if file_count else "", "size_bytes": size, "file_count": file_count}


def _smoke_module(project_root: Path = PROJECT_ROOT) -> Any:
    script = project_root / "scripts" / "tauri_packaged_runtime_smoke.py"
    spec = importlib.util.spec_from_file_location("command_center_tauri_packaged_runtime_smoke", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("tauri_smoke_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _git_head_full(root: Path = PROJECT_ROOT) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _relative_path(path: Path, root: Path = PROJECT_ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return ""


def _path_from_smoke(value: Any) -> Path:
    text = str(value or "").strip()
    if not text:
        return Path()
    path = Path(text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _artifact_set_sha256(
    app_bundle_sha256: str,
    dmg_sha256: str,
    bundle_identifier: str,
    bundle_version: str,
) -> str:
    return hashlib.sha256(
        "|".join(
            (app_bundle_sha256, dmg_sha256, bundle_identifier, bundle_version)
        ).encode("utf-8")
    ).hexdigest()


def _fixed_path_is_direct(project_root: Path, path: Path, *, directory: bool) -> bool:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        return False
    cursor = project_root
    try:
        if project_root.is_symlink() or not project_root.is_dir():
            return False
        for part in relative.parts:
            cursor = cursor / part
            metadata = cursor.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                return False
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)


def measure_fixed_tauri_package_artifacts(
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Recompute the one fixed package identity without trusting receipt paths or hashes."""

    project = project_root.absolute()
    app_path = project / FIXED_APP_RELATIVE
    dmg_path = project / FIXED_DMG_RELATIVE
    executable_path = app_path / "Contents" / "MacOS" / FIXED_EXECUTABLE_NAME
    blockers: list[str] = []
    if not _fixed_path_is_direct(project, app_path, directory=True):
        blockers.append("fixed_packaged_app_path_missing_or_aliased")
    if not _fixed_path_is_direct(project, dmg_path, directory=False):
        blockers.append("fixed_packaged_dmg_path_missing_or_aliased")
    if not _fixed_path_is_direct(project, executable_path, directory=False):
        blockers.append("fixed_packaged_executable_path_missing_or_aliased")

    app_fingerprint: dict[str, Any] = {}
    identity: dict[str, Any] = {}
    executable_sha256 = ""
    dmg_sha256 = ""
    if not blockers:
        try:
            smoke = _smoke_module(project)
            identity = smoke._read_bundle_identity(app_path)
            if identity.get("executable_name") != FIXED_EXECUTABLE_NAME:
                blockers.append("fixed_packaged_executable_name_mismatch")
            app_fingerprint = _bundle_fingerprint(app_path)
            executable_sha256 = _sha256_file(executable_path)
            dmg_sha256 = _sha256_file(dmg_path)
        except (OSError, ValueError, RuntimeError):
            blockers.append("fixed_package_disk_measurement_failed")

    app_bundle_sha256 = str(app_fingerprint.get("sha256") or "")
    bundle_identifier = str(identity.get("bundle_id") or "")
    bundle_version = str(identity.get("version") or "")
    artifact_set_sha256 = (
        _artifact_set_sha256(
            app_bundle_sha256,
            dmg_sha256,
            bundle_identifier,
            bundle_version,
        )
        if all(
            (app_bundle_sha256, executable_sha256, dmg_sha256, bundle_identifier, bundle_version)
        )
        else ""
    )
    if not all(
        _valid_hex(value)
        for value in (
            app_bundle_sha256,
            executable_sha256,
            dmg_sha256,
            artifact_set_sha256,
        )
    ):
        blockers.append("fixed_package_disk_identity_incomplete")
    return {
        "app_path": str(app_path),
        "dmg_path": str(dmg_path),
        "app_executable_path": str(executable_path),
        "app_bundle_sha256": app_bundle_sha256,
        "app_executable_sha256": executable_sha256,
        "dmg_sha256": dmg_sha256,
        "artifact_set_sha256": artifact_set_sha256,
        "bundle_identifier": bundle_identifier,
        "bundle_version": bundle_version,
        "app_bundle_size_bytes": int(app_fingerprint.get("size_bytes") or 0),
        "app_bundle_file_count": int(app_fingerprint.get("file_count") or 0),
        "blockers": sorted(set(blockers)),
    }


def _safe_bool(value: Any) -> bool:
    return value is True


def _package_paths(smoke: Mapping[str, Any]) -> tuple[Path, Path]:
    return _path_from_smoke(smoke.get("app_path")), _path_from_smoke(smoke.get("dmg_path"))


def _valid_hex(value: Any, length: int = 64) -> bool:
    text = str(value or "")
    return len(text) == length and all(char in "0123456789abcdef" for char in text.lower())


def _screenshot_exists_for_hash(expected: str, root: Path = PACKAGE_ROOT) -> bool:
    if not _valid_hex(expected):
        return False
    for path in sorted(root.glob("*.png")):
        try:
            if _sha256_file(path) == expected:
                return True
        except OSError:
            continue
    return False


def _evidence_common_checks(
    online: Mapping[str, Any], offline: Mapping[str, Any], build: Mapping[str, Any], *, head_full: str
) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    summary: dict[str, Any] = {}
    for label, smoke in (("online", online), ("offline", offline)):
        if smoke.get("schema_version") != "tauri_packaged_runtime_smoke.v1":
            blockers.append(f"{label}_smoke_schema_invalid")
        if smoke.get("status") != "tauri_packaged_runtime_smoke_passed":
            blockers.append(f"{label}_smoke_not_passed")
        if smoke.get("local_packaged_runtime_evidence_ready") is not True:
            blockers.append(f"{label}_smoke_not_ready")
        if smoke.get("head_full") != head_full:
            blockers.append(f"{label}_head_not_bound_to_current_head")
        if smoke.get("build_head_full") != head_full:
            blockers.append(f"{label}_build_head_not_bound_to_current_head")
        if smoke.get("build_executed") is not True:
            blockers.append(f"{label}_build_provenance_missing")
        if smoke.get("production_package_complete") is True:
            blockers.append(f"{label}_legacy_receipt_claimed_production")
        if smoke.get("contains_secret") is not False:
            blockers.append(f"{label}_secret_boundary_failed")
        if smoke.get("external_calls_triggered") is not False:
            blockers.append(f"{label}_external_boundary_failed")
        if smoke.get("does_not_execute_trades") is not True:
            blockers.append(f"{label}_trade_boundary_failed")
        summary[f"{label}_artifact_set_sha256"] = smoke.get("artifact_set_sha256")
        summary[f"{label}_app_bundle_sha256"] = smoke.get("app_bundle_sha256")
        summary[f"{label}_app_executable_sha256"] = smoke.get("app_executable_sha256")
        summary[f"{label}_dmg_sha256"] = smoke.get("dmg_sha256")
    if build.get("schema_version") != "tauri_build_receipt.v1" or build.get("build_executed") is not True:
        blockers.append("tauri_build_receipt_missing_or_not_executed")
    if build.get("head_full") != head_full:
        blockers.append("tauri_build_head_not_bound_to_current_head")
    if build.get("build_command") != "cd desktop && npm run tauri build":
        blockers.append("tauri_build_command_not_exact")
    if build.get("contains_secret") is not False or build.get("external_calls_triggered") is not False:
        blockers.append("tauri_build_boundary_failed")
    online_artifact = str(online.get("artifact_set_sha256") or "")
    offline_artifact = str(offline.get("artifact_set_sha256") or "")
    if not online_artifact or online_artifact != offline_artifact:
        blockers.append("online_offline_artifact_set_mismatch")
    for field in ("app_bundle_sha256", "app_executable_sha256", "dmg_sha256"):
        left, right = str(online.get(field) or ""), str(offline.get(field) or "")
        if not _valid_hex(left) or left != right:
            blockers.append(f"online_offline_{field}_mismatch")
    if build.get("artifact_set_sha256") != online_artifact:
        blockers.append("build_artifact_set_not_bound_to_smoke")
    return blockers, summary


def validate_tauri_production_package(
    evidence_root: Path | str = EVIDENCE_ROOT, *, expected_head_full: str = "", write_manifest: bool = False
) -> dict[str, Any]:
    """Validate actual package artifacts and optionally write the immutable pointer."""
    root = Path(evidence_root).expanduser().resolve()
    package_root = root / "desktop_runtime"
    online_path = package_root / ONLINE_SMOKE_PATH.name
    offline_path = package_root / OFFLINE_SMOKE_PATH.name
    build_path = package_root / BUILD_RECEIPT_PATH.name
    manifest_path = package_root / MANIFEST_PATH.name
    pointer_path = package_root / POINTER_PATH.name
    online, offline, build = _read_json(online_path), _read_json(offline_path), _read_json(build_path)
    actual_head_full = _git_head_full(PROJECT_ROOT)
    head_full = expected_head_full or actual_head_full
    blockers, summary = _evidence_common_checks(online, offline, build, head_full=head_full)
    if not head_full or head_full != actual_head_full:
        blockers.append("formal_package_expected_head_not_current_repository_head")
    measured = measure_fixed_tauri_package_artifacts(PROJECT_ROOT)
    blockers.extend(str(item) for item in measured.get("blockers", []))
    app_path = Path(str(measured.get("app_path") or ""))
    dmg_path = Path(str(measured.get("dmg_path") or ""))
    expected_app_label = FIXED_APP_RELATIVE.as_posix()
    expected_dmg_label = FIXED_DMG_RELATIVE.as_posix()
    for label, receipt in (("online", online), ("offline", offline), ("build", build)):
        if receipt.get("app_path") != expected_app_label:
            blockers.append(f"{label}_app_path_not_fixed_canonical_target")
        if receipt.get("dmg_path") != expected_dmg_label:
            blockers.append(f"{label}_dmg_path_not_fixed_canonical_target")
        for field in ("app_bundle_sha256", "dmg_sha256", "artifact_set_sha256"):
            if receipt.get(field) != measured.get(field):
                blockers.append(f"{label}_{field}_not_recomputed_from_fixed_disk_target")
    for label, receipt in (("online", online), ("offline", offline)):
        if receipt.get("app_executable_sha256") != measured.get("app_executable_sha256"):
            blockers.append(f"{label}_app_executable_sha256_not_recomputed_from_fixed_disk_target")
        if receipt.get("bundle_identifier") != measured.get("bundle_identifier"):
            blockers.append(f"{label}_bundle_identifier_readback_mismatch")
        if receipt.get("bundle_version") != measured.get("bundle_version"):
            blockers.append(f"{label}_bundle_version_readback_mismatch")
    if not _screenshot_exists_for_hash(str(offline.get("offline_screenshot_sha256") or ""), package_root):
        blockers.append("offline_screenshot_hash_not_found_on_disk")
    for label, smoke in (("online", online), ("offline", offline)):
        for field in (
            "dmg_checksum_verified",
            "codesign_verified",
            "artifacts_gitignored",
            "safe_config_log_evidence",
        ):
            if smoke.get(field) is not True:
                blockers.append(f"{label}_{field}_failed")
    if online.get("health_ready_during_launch") is not True:
        blockers.append("online_health_not_ready_during_launch")
    if offline.get("backend_offline_packaged_ux_verified") is not True or offline.get("offline_notice_observed") is not True:
        blockers.append("offline_packaged_ux_not_verified")
    if offline.get("backend_offline_expected") is not True or offline.get("offline_backend_unavailable_observed") is not True:
        blockers.append("offline_backend_boundary_not_verified")
    production_complete = not blockers
    result = {
        "schema_version": MANIFEST_SCHEMA,
        "status": "tauri_production_package_verified" if production_complete else "tauri_production_package_blocked",
        "production_package_complete": production_complete,
        "head_full": head_full,
        "build_receipt_path": _relative_path(build_path, root.parent),
        "build_executed": build.get("build_executed") is True,
        "build_command": build.get("build_command") or "",
        "app_path": _relative_path(app_path, root.parent),
        "dmg_path": _relative_path(dmg_path, root.parent),
        "app_bundle_sha256": measured.get("app_bundle_sha256") or "",
        "app_executable_sha256": measured.get("app_executable_sha256") or "",
        "dmg_sha256": measured.get("dmg_sha256") or "",
        "artifact_set_sha256": measured.get("artifact_set_sha256") or "",
        "bundle_identifier": measured.get("bundle_identifier") or "",
        "bundle_version": measured.get("bundle_version") or "",
        "online_offline_artifact_match": not any(
            "artifact_set" in item or "fixed_disk_target" in item for item in blockers
        ),
        "online_health_ready": online.get("health_ready_during_launch") is True,
        "offline_ui_verified": offline.get("backend_offline_packaged_ux_verified") is True
        and offline.get("offline_notice_observed") is True,
        "offline_screenshot_sha256": offline.get("offline_screenshot_sha256") or "",
        "dmg_checksum_verified": online.get("dmg_checksum_verified") is True and offline.get("dmg_checksum_verified") is True,
        "codesign_verified": online.get("codesign_verified") is True and offline.get("codesign_verified") is True,
        "developer_id_signing_verified": False,
        "notarization_ticket_detected": False,
        "contains_secret": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "blockers": sorted(set(blockers)),
        "readback_summary": summary,
    }
    if not write_manifest or not production_complete:
        return result
    manifest_material = dict(result)
    manifest_material.pop("blockers", None)
    manifest_material["manifest_schema_version"] = MANIFEST_SCHEMA
    manifest_material["created_at"] = _now_iso()
    manifest_digest = _digest(manifest_material)
    manifest = {**manifest_material, "manifest_digest": manifest_digest}
    pointer = {
        "schema_version": POINTER_SCHEMA,
        "manifest_path": _relative_path(manifest_path, root.parent),
        "manifest_digest": manifest_digest,
        "head_full": head_full,
        "artifact_set_sha256": result["artifact_set_sha256"],
        "immutable": True,
        "created_at": manifest["created_at"],
        "contains_secret": False,
        "external_calls_triggered": False,
    }
    for path, value in ((manifest_path, manifest), (pointer_path, pointer)):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(_canonical_bytes(value) + b"\n")
        os.replace(temporary, path)
    result.update({"manifest_path": _relative_path(manifest_path, root.parent), "pointer_path": _relative_path(pointer_path, root.parent), "manifest_digest": manifest_digest})
    return result


def record_tauri_build_receipt(evidence_root: Path | str = EVIDENCE_ROOT, *, head_full: str = "") -> dict[str, Any]:
    """Record hashes immediately after the exact authorized Tauri build command."""
    root = Path(evidence_root).expanduser().resolve()
    package_root = root / "desktop_runtime"
    measured = measure_fixed_tauri_package_artifacts(PROJECT_ROOT)
    app_path = Path(str(measured.get("app_path") or ""))
    dmg_path = Path(str(measured.get("dmg_path") or ""))
    receipt = {
        "schema_version": "tauri_build_receipt.v1",
        "build_executed": not measured.get("blockers"),
        "build_command": "cd desktop && npm run tauri build",
        "head_full": head_full or _git_head_full(PROJECT_ROOT),
        "app_path": _relative_path(app_path, root.parent),
        "dmg_path": _relative_path(dmg_path, root.parent),
        "app_bundle_sha256": measured.get("app_bundle_sha256") or "",
        "dmg_sha256": measured.get("dmg_sha256") or "",
        "artifact_set_sha256": measured.get("artifact_set_sha256") or "",
        "contains_secret": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
    }
    package_root.mkdir(parents=True, exist_ok=True)
    receipt_path = package_root / BUILD_RECEIPT_PATH.name
    temporary = receipt_path.with_suffix(".json.tmp")
    temporary.write_bytes(_canonical_bytes(receipt) + b"\n")
    os.replace(temporary, receipt_path)
    return receipt


__all__ = [
    "measure_fixed_tauri_package_artifacts",
    "record_tauri_build_receipt",
    "validate_tauri_production_package",
]
