"""Disk-backed verifier for distributable Tauri production-package evidence.

The existing packaged-runtime smoke receipts are useful L3 observations, but
they intentionally never claim production completion.  This module is the
shared, read-only verifier used by closeout and by the explicit promotion CLI:
it re-hashes the package on disk, binds online/offline evidence to the same
HEAD and artifact set, then independently validates Developer ID signing,
Gatekeeper acceptance, and stapled notarization tickets for both the App and
DMG before writing an immutable manifest/pointer.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
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
PRODUCTION_BUILD_COMMAND = ".venv/bin/python scripts/tauri_production_build.py"
BUILD_RECEIPT_SCHEMA = "tauri_build_receipt.v2"
PROVENANCE_SCHEMA = "tauri_production_build_provenance.v1"
RELEASE_IDENTITY_POLICY_SCHEMA = "stock_ming_macos_release_identity_policy.v1"
RELEASE_IDENTITY_POLICY_PATH = Path(
    "/Library/Application Support/stock-MING/release-identity/macos-developer-id-policy.json"
)
PROVENANCE_RELATIVE = Path("Contents/Resources/production/command-center-build-provenance.json")
BUILD_ENTRY_RELATIVE = Path("scripts/tauri_production_build.py")
TAURI_CONFIG_RELATIVE = Path("desktop/src-tauri/tauri.conf.json")
SYSTEM_GIT = "/usr/bin/git"
SYSTEM_CODESIGN = "/usr/bin/codesign"
SYSTEM_SPCTL = "/usr/sbin/spctl"
SYSTEM_XCRUN = "/usr/bin/xcrun"
SYSTEM_HDIUTIL = "/usr/bin/hdiutil"
SYSTEM_MOUNT = "/sbin/mount"
SYSTEM_SECURITY = "/usr/bin/security"
_SAFE_TOOL_ENV = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "LANG": "C",
    "LC_ALL": "C",
}


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


def _current_source_binding(project_root: Path = PROJECT_ROOT) -> dict[str, str]:
    """Bind a build to tracked HEAD bytes, not to a mutable checkout label."""

    try:
        archive = subprocess.run(
            [SYSTEM_GIT, "archive", "--format=tar", "HEAD"],
            cwd=project_root,
            capture_output=True,
            timeout=120,
            check=False,
            env=_SAFE_TOOL_ENV,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    build_entry = project_root / BUILD_ENTRY_RELATIVE
    tauri_config = project_root / TAURI_CONFIG_RELATIVE
    if archive.returncode != 0 or not build_entry.is_file() or not tauri_config.is_file():
        return {}
    return {
        "source_archive_sha256": hashlib.sha256(archive.stdout).hexdigest(),
        "build_entry_sha256": _sha256_file(build_entry),
        "tauri_config_sha256": _sha256_file(tauri_config),
    }


def _load_release_identity_policy(path: Path = RELEASE_IDENTITY_POLICY_PATH) -> dict[str, Any]:
    """Read the root-owned, non-secret release identity allowlist fail-closed."""

    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            return {}
        if metadata.st_uid != 0 or metadata.st_mode & 0o022:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(value, Mapping):
        return {}
    exact = {
        "schema_version",
        "approved_for_distribution",
        "team_identifier",
        "developer_id_application_common_name",
        "certificate_sha256",
    }
    if set(value) != exact:
        return {}
    team = str(value.get("team_identifier") or "")
    common_name = str(value.get("developer_id_application_common_name") or "")
    certificate = str(value.get("certificate_sha256") or "").lower()
    if not (
        value.get("schema_version") == RELEASE_IDENTITY_POLICY_SCHEMA
        and value.get("approved_for_distribution") is True
        and re.fullmatch(r"[A-Z0-9]{10}", team)
        and common_name.startswith("Developer ID Application: ")
        and common_name.endswith(f" ({team})")
        and _valid_hex(certificate)
    ):
        return {}
    material = {**dict(value), "certificate_sha256": certificate}
    return {**material, "policy_digest": _digest(material)}


def _read_embedded_provenance(app_path: Path) -> dict[str, Any]:
    path = app_path / PROVENANCE_RELATIVE
    try:
        if path.is_symlink() or not path.is_file():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _validate_embedded_provenance(
    provenance: Mapping[str, Any],
    *,
    head_full: str,
    source_binding: Mapping[str, str],
    policy_digest: str,
    build_receipt: Mapping[str, Any],
) -> list[str]:
    exact = {
        "schema_version",
        "head_full",
        "source_archive_sha256",
        "build_entry_sha256",
        "tauri_config_sha256",
        "release_identity_policy_digest",
        "build_session_nonce_sha256",
        "contains_secret",
        "external_calls_triggered",
        "provenance_digest",
    }
    blockers: list[str] = []
    if set(provenance) != exact or provenance.get("schema_version") != PROVENANCE_SCHEMA:
        return ["embedded_build_provenance_schema_invalid"]
    unsigned = dict(provenance)
    claimed_digest = unsigned.pop("provenance_digest", None)
    if claimed_digest != _digest(unsigned):
        blockers.append("embedded_build_provenance_digest_invalid")
    expected = {
        "head_full": head_full,
        **source_binding,
        "release_identity_policy_digest": policy_digest,
    }
    for field, value in expected.items():
        if not value or provenance.get(field) != value:
            blockers.append(f"embedded_build_provenance_{field}_mismatch")
    nonce_hash = str(provenance.get("build_session_nonce_sha256") or "")
    if not _valid_hex(nonce_hash) or build_receipt.get("build_session_nonce_sha256") != nonce_hash:
        blockers.append("embedded_build_provenance_nonce_not_bound_to_receipt")
    if provenance.get("contains_secret") is not False or provenance.get("external_calls_triggered") is not False:
        blockers.append("embedded_build_provenance_boundary_invalid")
    if build_receipt.get("provenance_digest") != claimed_digest:
        blockers.append("embedded_build_provenance_receipt_digest_mismatch")
    return blockers


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
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _git_head_full(root: Path = PROJECT_ROOT) -> str:
    """Read HEAD without spawning git so GET/readback stays filesystem-only."""

    try:
        dot_git = root / ".git"
        if dot_git.is_file():
            marker = dot_git.read_text(encoding="utf-8").strip()
            if not marker.startswith("gitdir: "):
                return ""
            git_dir = (root / marker[8:]).resolve()
        else:
            git_dir = dot_git.resolve()
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{40}", head):
            return head
        if not head.startswith("ref: refs/"):
            return ""
        reference = head[5:]
        common_dir = git_dir
        common_marker = git_dir / "commondir"
        if common_marker.is_file():
            common_dir = (git_dir / common_marker.read_text(encoding="utf-8").strip()).resolve()
        loose = common_dir / reference
        if loose.is_file():
            value = loose.read_text(encoding="utf-8").strip()
            return value if re.fullmatch(r"[0-9a-f]{40}", value) else ""
        packed = common_dir / "packed-refs"
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.startswith(("#", "^")):
                continue
            sha, _, name = line.partition(" ")
            if name == reference and re.fullmatch(r"[0-9a-f]{40}", sha):
                return sha
    except OSError:
        return ""
    return ""


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


def _run_distribution_check(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    if not command or not Path(command[0]).is_absolute():
        return subprocess.CompletedProcess(command, 127, "", "")
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_SAFE_TOOL_ENV,
        )
    except (OSError, subprocess.SubprocessError):
        return subprocess.CompletedProcess(command, 127, "", "")


def _codesign_identity_observation(
    path: Path,
    *,
    policy: Mapping[str, Any],
    require_hardened_runtime: bool,
) -> dict[str, bool]:
    """Verify signature and bind its leaf certificate to the approved identity."""

    checks = {
        "codesign_verified": False,
        "common_name_matches_policy": False,
        "team_identifier_matches_policy": False,
        "certificate_fingerprint_matches_policy": False,
        "hardened_runtime_verified": not require_hardened_runtime,
    }
    if not policy:
        return checks
    with tempfile.TemporaryDirectory(prefix="stock-ming-codesign-") as temp_dir:
        prefix = str(Path(temp_dir) / "leaf-")
        verify_command = [SYSTEM_CODESIGN, "--verify"]
        if path.suffix == ".app":
            verify_command.append("--deep")
        verify_command.extend(["--strict", "--verbose=2", str(path)])
        verify = _run_distribution_check(
            verify_command, timeout=30
        )
        detail = _run_distribution_check(
            [SYSTEM_CODESIGN, "-d", "--verbose=4", "--extract-certificates", prefix, str(path)],
            timeout=30,
        )
        output = f"{detail.stdout or ''}\n{detail.stderr or ''}"
        authorities = re.findall(r"^Authority=(.+)$", output, re.MULTILINE)
        team_match = re.search(r"^TeamIdentifier=(.+)$", output, re.MULTILINE)
        leaf = Path(f"{prefix}0")
        certificate_sha256 = ""
        try:
            if leaf.is_file() and not leaf.is_symlink():
                certificate_sha256 = _sha256_file(leaf)
        except OSError:
            pass
        checks.update(
            {
                "codesign_verified": verify.returncode == 0 and detail.returncode == 0,
                "common_name_matches_policy": bool(
                    authorities
                    and authorities[0] == policy.get("developer_id_application_common_name")
                ),
                "team_identifier_matches_policy": bool(
                    team_match and team_match.group(1).strip() == policy.get("team_identifier")
                ),
                "certificate_fingerprint_matches_policy": bool(
                    certificate_sha256
                    and certificate_sha256 == policy.get("certificate_sha256")
                ),
                "hardened_runtime_verified": bool(
                    not require_hardened_runtime
                    or re.search(r"flags=0x[0-9a-fA-F]+\([^)]*runtime[^)]*\)", output)
                ),
            }
        )
    return checks


def _verify_mounted_dmg_payload(
    *,
    dmg_path: Path,
    expected_app_bundle_sha256: str,
    expected_executable_sha256: str,
    expected_bundle_identifier: str,
    expected_bundle_version: str,
    expected_provenance_digest: str,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Mount the DMG read-only and bind its sole App byte-for-byte to the measured App."""

    checks: dict[str, bool] = {
        "dmg_attached_readonly": False,
        "dmg_mount_readonly_observed": False,
        "single_mounted_app_detected": False,
        "mounted_app_bundle_hash_matches": False,
        "mounted_app_executable_hash_matches": False,
        "mounted_app_identity_matches": False,
        "mounted_app_codesign_verified": False,
        "mounted_app_developer_id_verified": False,
        "mounted_app_team_identifier_verified": False,
        "mounted_app_certificate_verified": False,
        "mounted_app_hardened_runtime_verified": False,
        "mounted_app_provenance_matches": False,
        "mounted_app_gatekeeper_accepted": False,
        "mounted_app_notarization_ticket_valid": False,
        "dmg_detached": False,
    }
    with tempfile.TemporaryDirectory(prefix="stock-ming-formal-dmg-") as temp_dir:
        mountpoint = Path(temp_dir) / "mount"
        mountpoint.mkdir()
        attach = _run_distribution_check(
            [
                SYSTEM_HDIUTIL,
                "attach",
                "-readonly",
                "-nobrowse",
                "-mountpoint",
                str(mountpoint),
                str(dmg_path),
            ],
            timeout=60,
        )
        if attach.returncode != 0:
            return {**checks, "payload_ready": False, "blockers": ["dmg_payload_attach_failed"]}
        checks["dmg_attached_readonly"] = True
        try:
            mount_table = _run_distribution_check([SYSTEM_MOUNT], timeout=15)
            mount_labels = {str(mountpoint), str(mountpoint.resolve())}
            mount_line = next(
                (
                    line
                    for line in (mount_table.stdout or "").splitlines()
                    if any(f" on {label} " in line for label in mount_labels)
                ),
                "",
            )
            checks["dmg_mount_readonly_observed"] = bool(
                mount_line and ("read-only" in mount_line.lower() or "read only" in mount_line.lower())
            )
            app_candidates = sorted(mountpoint.glob("*.app"))
            checks["single_mounted_app_detected"] = len(app_candidates) == 1
            if len(app_candidates) == 1 and not app_candidates[0].is_symlink():
                mounted_app = app_candidates[0]
                mounted_fingerprint = _bundle_fingerprint(mounted_app)
                checks["mounted_app_bundle_hash_matches"] = (
                    mounted_fingerprint.get("sha256") == expected_app_bundle_sha256
                )
                mounted_provenance = _read_embedded_provenance(mounted_app)
                checks["mounted_app_provenance_matches"] = bool(
                    mounted_provenance.get("provenance_digest") == expected_provenance_digest
                )
                try:
                    identity = _smoke_module(PROJECT_ROOT)._read_bundle_identity(mounted_app)
                    mounted_executable = mounted_app / "Contents" / "MacOS" / str(
                        identity.get("executable_name") or ""
                    )
                    checks["mounted_app_identity_matches"] = bool(
                        identity.get("bundle_id") == expected_bundle_identifier
                        and identity.get("version") == expected_bundle_version
                    )
                    checks["mounted_app_executable_hash_matches"] = bool(
                        mounted_executable.is_file()
                        and _sha256_file(mounted_executable) == expected_executable_sha256
                    )
                except (OSError, ValueError, RuntimeError):
                    pass
                identity_checks = _codesign_identity_observation(
                    mounted_app, policy=policy, require_hardened_runtime=True
                )
                checks["mounted_app_codesign_verified"] = identity_checks["codesign_verified"]
                checks["mounted_app_developer_id_verified"] = identity_checks[
                    "common_name_matches_policy"
                ]
                checks["mounted_app_team_identifier_verified"] = identity_checks[
                    "team_identifier_matches_policy"
                ]
                checks["mounted_app_certificate_verified"] = identity_checks[
                    "certificate_fingerprint_matches_policy"
                ]
                checks["mounted_app_hardened_runtime_verified"] = identity_checks[
                    "hardened_runtime_verified"
                ]
                gatekeeper = _run_distribution_check(
                    [SYSTEM_SPCTL, "--assess", "--type", "execute", "--verbose=4", str(mounted_app)],
                    timeout=30,
                )
                gatekeeper_output = f"{gatekeeper.stdout or ''}\n{gatekeeper.stderr or ''}".lower()
                checks["mounted_app_gatekeeper_accepted"] = bool(
                    gatekeeper.returncode == 0
                    and "override=security disabled" not in gatekeeper_output
                    and "accepted" in gatekeeper_output
                    and "notarized developer id" in gatekeeper_output
                )
                stapler = _run_distribution_check(
                    [SYSTEM_XCRUN, "stapler", "validate", str(mounted_app)], timeout=30
                )
                checks["mounted_app_notarization_ticket_valid"] = stapler.returncode == 0
        finally:
            detach = _run_distribution_check([SYSTEM_HDIUTIL, "detach", str(mountpoint)], timeout=60)
            checks["dmg_detached"] = detach.returncode == 0
    blockers = [f"dmg_payload_{field}_failed" for field, passed in checks.items() if not passed]
    return {**checks, "payload_ready": not blockers, "blockers": blockers}


def _macos_distribution_verification(
    *,
    app_path: Path,
    dmg_path: Path,
    head_full: str,
    measured: Mapping[str, Any],
    provenance_digest: str,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-evaluate the signed App and DMG without trusting smoke booleans."""

    blockers: list[str] = []
    if sys.platform != "darwin":
        blockers.append("macos_distribution_verification_requires_macos")
        return {
            "schema_version": "tauri_macos_distribution_verification.v1",
            "head_full": head_full,
            "artifact_set_sha256": measured.get("artifact_set_sha256") or "",
            "app_bundle_sha256": measured.get("app_bundle_sha256") or "",
            "app_executable_sha256": measured.get("app_executable_sha256") or "",
            "dmg_sha256": measured.get("dmg_sha256") or "",
            "bundle_identifier": measured.get("bundle_identifier") or "",
            "bundle_version": measured.get("bundle_version") or "",
            "developer_id_signing_verified": False,
            "app_gatekeeper_accepted": False,
            "app_notarization_ticket_valid": False,
            "dmg_gatekeeper_accepted": False,
            "dmg_notarization_ticket_valid": False,
            "distribution_ready": False,
            "blockers": blockers,
        }

    app_identity = _codesign_identity_observation(
        app_path, policy=policy, require_hardened_runtime=True
    )
    dmg_identity = _codesign_identity_observation(
        dmg_path, policy=policy, require_hardened_runtime=False
    )

    app_gatekeeper = _run_distribution_check(
        [SYSTEM_SPCTL, "--assess", "--type", "execute", "--verbose=4", str(app_path)], timeout=30
    )
    app_gatekeeper_output = f"{app_gatekeeper.stdout or ''}\n{app_gatekeeper.stderr or ''}".lower()
    app_gatekeeper_enabled = "override=security disabled" not in app_gatekeeper_output
    app_gatekeeper_accepted = bool(
        app_gatekeeper.returncode == 0
        and app_gatekeeper_enabled
        and "accepted" in app_gatekeeper_output
        and "notarized developer id" in app_gatekeeper_output
    )
    app_stapler = _run_distribution_check([SYSTEM_XCRUN, "stapler", "validate", str(app_path)], timeout=30)

    dmg_verify = _run_distribution_check([SYSTEM_HDIUTIL, "verify", str(dmg_path)], timeout=60)
    dmg_gatekeeper = _run_distribution_check(
        [
            SYSTEM_SPCTL,
            "--assess",
            "--type",
            "open",
            "--context",
            "context:primary-signature",
            "--verbose=4",
            str(dmg_path),
        ],
        timeout=30,
    )
    dmg_gatekeeper_output = f"{dmg_gatekeeper.stdout or ''}\n{dmg_gatekeeper.stderr or ''}".lower()
    dmg_gatekeeper_enabled = "override=security disabled" not in dmg_gatekeeper_output
    dmg_gatekeeper_accepted = bool(
        dmg_gatekeeper.returncode == 0
        and dmg_gatekeeper_enabled
        and "accepted" in dmg_gatekeeper_output
        and "notarized developer id" in dmg_gatekeeper_output
    )
    dmg_stapler = _run_distribution_check([SYSTEM_XCRUN, "stapler", "validate", str(dmg_path)], timeout=30)
    dmg_payload = _verify_mounted_dmg_payload(
        dmg_path=dmg_path,
        expected_app_bundle_sha256=str(measured.get("app_bundle_sha256") or ""),
        expected_executable_sha256=str(measured.get("app_executable_sha256") or ""),
        expected_bundle_identifier=str(measured.get("bundle_identifier") or ""),
        expected_bundle_version=str(measured.get("bundle_version") or ""),
        expected_provenance_digest=provenance_digest,
        policy=policy,
    )

    checks = {
        "app_codesign_verified": app_identity["codesign_verified"],
        "developer_id_application_verified": app_identity["common_name_matches_policy"],
        "team_identifier_present": app_identity["team_identifier_matches_policy"],
        "app_certificate_fingerprint_verified": app_identity[
            "certificate_fingerprint_matches_policy"
        ],
        "hardened_runtime_verified": app_identity["hardened_runtime_verified"],
        "dmg_codesign_verified": dmg_identity["codesign_verified"],
        "dmg_developer_id_application_verified": dmg_identity["common_name_matches_policy"],
        "dmg_team_identifier_verified": dmg_identity["team_identifier_matches_policy"],
        "dmg_certificate_fingerprint_verified": dmg_identity[
            "certificate_fingerprint_matches_policy"
        ],
        "app_gatekeeper_accepted": app_gatekeeper_accepted,
        "app_notarization_ticket_valid": app_stapler.returncode == 0,
        "dmg_checksum_verified": dmg_verify.returncode == 0,
        "dmg_gatekeeper_accepted": dmg_gatekeeper_accepted,
        "dmg_notarization_ticket_valid": dmg_stapler.returncode == 0,
    }
    for field, passed in checks.items():
        if not passed:
            blockers.append(f"macos_distribution_{field}_failed")
    blockers.extend(str(item) for item in dmg_payload.get("blockers", []))
    return {
        "schema_version": "tauri_macos_distribution_verification.v1",
        "head_full": head_full,
        "artifact_set_sha256": measured.get("artifact_set_sha256") or "",
        "app_bundle_sha256": measured.get("app_bundle_sha256") or "",
        "app_executable_sha256": measured.get("app_executable_sha256") or "",
        "dmg_sha256": measured.get("dmg_sha256") or "",
        "bundle_identifier": measured.get("bundle_identifier") or "",
        "bundle_version": measured.get("bundle_version") or "",
        "release_identity_policy_digest": str(policy.get("policy_digest") or ""),
        "provenance_digest": provenance_digest,
        **checks,
        "dmg_payload_verification": dmg_payload,
        "developer_id_signing_verified": bool(
            checks["app_codesign_verified"]
            and checks["developer_id_application_verified"]
            and checks["team_identifier_present"]
            and checks["app_certificate_fingerprint_verified"]
            and checks["hardened_runtime_verified"]
            and checks["dmg_codesign_verified"]
            and checks["dmg_developer_id_application_verified"]
            and checks["dmg_team_identifier_verified"]
            and checks["dmg_certificate_fingerprint_verified"]
        ),
        "distribution_ready": not blockers,
        "blockers": sorted(set(blockers)),
    }


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
    provenance: dict[str, Any] = {}
    if not blockers:
        try:
            smoke = _smoke_module(project)
            identity = smoke._read_bundle_identity(app_path)
            if identity.get("executable_name") != FIXED_EXECUTABLE_NAME:
                blockers.append("fixed_packaged_executable_name_mismatch")
            app_fingerprint = _bundle_fingerprint(app_path)
            executable_sha256 = _sha256_file(executable_path)
            dmg_sha256 = _sha256_file(dmg_path)
            provenance = _read_embedded_provenance(app_path)
            if not provenance:
                blockers.append("embedded_build_provenance_missing")
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
        "build_provenance": provenance,
        "provenance_digest": str(provenance.get("provenance_digest") or ""),
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
            if not path.is_symlink() and path.is_file() and _sha256_file(path) == expected:
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
    if build.get("schema_version") != BUILD_RECEIPT_SCHEMA or build.get("build_executed") is not True:
        blockers.append("tauri_build_receipt_missing_or_not_executed")
    if build.get("head_full") != head_full:
        blockers.append("tauri_build_head_not_bound_to_current_head")
    if build.get("head_binding_valid") is not True:
        blockers.append("tauri_build_head_binding_not_verified")
    if build.get("build_command") != PRODUCTION_BUILD_COMMAND:
        blockers.append("tauri_build_command_not_exact")
    if build.get("contains_secret") is not False or build.get("external_calls_triggered") is not False:
        blockers.append("tauri_build_boundary_failed")
    unsigned_build = dict(build)
    claimed_receipt_digest = unsigned_build.pop("receipt_digest", None)
    if claimed_receipt_digest != _digest(unsigned_build):
        blockers.append("tauri_build_receipt_digest_invalid")
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


def _read_formal_manifest(
    *,
    manifest_path: Path,
    pointer_path: Path,
    head_full: str,
    measured: Mapping[str, Any],
    policy_digest: str,
    provenance_digest: str,
) -> tuple[dict[str, Any], list[str]]:
    """Pure file readback for GET/evaluator; never invokes platform tooling."""

    manifest = _read_json(manifest_path)
    pointer = _read_json(pointer_path)
    blockers: list[str] = []
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        blockers.append("formal_package_manifest_missing_or_invalid")
        return {}, blockers
    unsigned = dict(manifest)
    claimed = unsigned.pop("manifest_digest", None)
    if claimed != _digest(unsigned):
        blockers.append("formal_package_manifest_digest_invalid")
    if pointer.get("schema_version") != POINTER_SCHEMA or pointer.get("immutable") is not True:
        blockers.append("formal_package_pointer_missing_or_invalid")
    if pointer.get("manifest_digest") != claimed:
        blockers.append("formal_package_pointer_digest_mismatch")
    expected = {
        "head_full": head_full,
        "artifact_set_sha256": measured.get("artifact_set_sha256"),
        "app_bundle_sha256": measured.get("app_bundle_sha256"),
        "app_executable_sha256": measured.get("app_executable_sha256"),
        "dmg_sha256": measured.get("dmg_sha256"),
        "bundle_identifier": measured.get("bundle_identifier"),
        "bundle_version": measured.get("bundle_version"),
        "release_identity_policy_digest": policy_digest,
        "build_provenance_digest": provenance_digest,
    }
    for field, value in expected.items():
        if not value or manifest.get(field) != value:
            blockers.append(f"formal_package_manifest_{field}_mismatch")
    if pointer.get("head_full") != head_full or pointer.get("artifact_set_sha256") != measured.get(
        "artifact_set_sha256"
    ):
        blockers.append("formal_package_pointer_current_artifact_binding_invalid")
    distribution = manifest.get("macos_distribution_verification")
    if not isinstance(distribution, Mapping) or distribution.get("distribution_ready") is not True:
        blockers.append("formal_package_distribution_attestation_not_ready")
        return {}, blockers
    if distribution.get("blockers") != []:
        blockers.append("formal_package_distribution_attestation_has_blockers")
    required_security_attestations = (
        "app_codesign_verified",
        "developer_id_application_verified",
        "team_identifier_present",
        "app_certificate_fingerprint_verified",
        "hardened_runtime_verified",
        "dmg_codesign_verified",
        "dmg_developer_id_application_verified",
        "dmg_team_identifier_verified",
        "dmg_certificate_fingerprint_verified",
        "developer_id_signing_verified",
        "app_gatekeeper_accepted",
        "app_notarization_ticket_valid",
        "dmg_checksum_verified",
        "dmg_gatekeeper_accepted",
        "dmg_notarization_ticket_valid",
    )
    for field in required_security_attestations:
        if distribution.get(field) is not True:
            blockers.append(f"formal_package_distribution_{field}_not_attested")
    payload = distribution.get("dmg_payload_verification")
    if not isinstance(payload, Mapping) or payload.get("payload_ready") is not True:
        blockers.append("formal_package_distribution_dmg_payload_not_attested")
    else:
        required_payload_attestations = (
            "dmg_attached_readonly",
            "dmg_mount_readonly_observed",
            "single_mounted_app_detected",
            "mounted_app_bundle_hash_matches",
            "mounted_app_executable_hash_matches",
            "mounted_app_identity_matches",
            "mounted_app_codesign_verified",
            "mounted_app_developer_id_verified",
            "mounted_app_team_identifier_verified",
            "mounted_app_certificate_verified",
            "mounted_app_hardened_runtime_verified",
            "mounted_app_provenance_matches",
            "mounted_app_gatekeeper_accepted",
            "mounted_app_notarization_ticket_valid",
            "dmg_detached",
        )
        for field in required_payload_attestations:
            if payload.get(field) is not True:
                blockers.append(f"formal_package_distribution_dmg_payload_{field}_not_attested")
        if payload.get("blockers") != []:
            blockers.append("formal_package_distribution_dmg_payload_has_blockers")
    for field, value in expected.items():
        distribution_field = "provenance_digest" if field == "build_provenance_digest" else field
        if field == "release_identity_policy_digest":
            distribution_field = field
        if distribution.get(distribution_field) != value:
            blockers.append(f"formal_package_distribution_{distribution_field}_mismatch")
    return dict(distribution), blockers


def validate_tauri_production_package(
    evidence_root: Path | str = EVIDENCE_ROOT, *, expected_head_full: str = "", write_manifest: bool = False
) -> dict[str, Any]:
    """Validate actual package artifacts and optionally write the immutable pointer."""
    requested_root = Path(evidence_root).expanduser().absolute()
    root_aliased = requested_root.is_symlink()
    root = requested_root.resolve()
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
    if root_aliased or package_root.is_symlink() or not package_root.is_dir():
        blockers.append("formal_package_evidence_root_missing_or_aliased")
    if not head_full or head_full != actual_head_full:
        blockers.append("formal_package_expected_head_not_current_repository_head")
    measured = measure_fixed_tauri_package_artifacts(PROJECT_ROOT)
    blockers.extend(str(item) for item in measured.get("blockers", []))
    policy = _load_release_identity_policy()
    if not policy:
        blockers.append("approved_release_identity_policy_missing_or_invalid")
    if write_manifest:
        source_binding = _current_source_binding(PROJECT_ROOT)
    else:
        source_binding = {
            "source_archive_sha256": str(build.get("source_archive_sha256") or ""),
            "build_entry_sha256": (
                _sha256_file(PROJECT_ROOT / BUILD_ENTRY_RELATIVE)
                if (PROJECT_ROOT / BUILD_ENTRY_RELATIVE).is_file()
                else ""
            ),
            "tauri_config_sha256": (
                _sha256_file(PROJECT_ROOT / TAURI_CONFIG_RELATIVE)
                if (PROJECT_ROOT / TAURI_CONFIG_RELATIVE).is_file()
                else ""
            ),
        }
    if not source_binding:
        blockers.append("current_source_binding_unavailable")
    provenance = measured.get("build_provenance")
    provenance = dict(provenance) if isinstance(provenance, Mapping) else {}
    blockers.extend(
        _validate_embedded_provenance(
            provenance,
            head_full=head_full,
            source_binding=source_binding,
            policy_digest=str(policy.get("policy_digest") or ""),
            build_receipt=build,
        )
    )
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
    if write_manifest:
        distribution = _macos_distribution_verification(
            app_path=app_path,
            dmg_path=dmg_path,
            head_full=head_full,
            measured=measured,
            provenance_digest=str(provenance.get("provenance_digest") or ""),
            policy=policy,
        )
        post_validation_measurement = measure_fixed_tauri_package_artifacts(PROJECT_ROOT)
        for field in (
            "artifact_set_sha256",
            "app_bundle_sha256",
            "app_executable_sha256",
            "dmg_sha256",
            "provenance_digest",
        ):
            if post_validation_measurement.get(field) != measured.get(field):
                blockers.append(f"formal_package_{field}_changed_during_validation")
        evidence_source = "explicit_current_artifact_system_validation"
    else:
        distribution, formal_blockers = _read_formal_manifest(
            manifest_path=manifest_path,
            pointer_path=pointer_path,
            head_full=head_full,
            measured=measured,
            policy_digest=str(policy.get("policy_digest") or ""),
            provenance_digest=str(provenance.get("provenance_digest") or ""),
        )
        blockers.extend(formal_blockers)
        evidence_source = "same_head_formal_manifest_readback"
    distribution = {**distribution, "blockers": list(distribution.get("blockers") or [])}
    blockers.extend(str(item) for item in distribution.get("blockers", []))
    if distribution.get("distribution_ready") is not True:
        blockers.append("macos_distribution_not_ready")
    if distribution.get("head_full") != head_full:
        blockers.append("macos_distribution_head_binding_mismatch")
    for field in (
        "artifact_set_sha256",
        "app_bundle_sha256",
        "app_executable_sha256",
        "dmg_sha256",
        "bundle_identifier",
        "bundle_version",
    ):
        if distribution.get(field) != measured.get(field):
            blockers.append(f"macos_distribution_{field}_binding_mismatch")
    for label, smoke in (("online", online), ("offline", offline)):
        if smoke.get("developer_id_signing_verified") is not True:
            blockers.append(f"{label}_developer_id_signing_not_observed")
        if smoke.get("notarization_ticket_detected") is not True:
            blockers.append(f"{label}_app_notarization_ticket_not_observed")
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
        "release_identity_policy_digest": str(policy.get("policy_digest") or ""),
        "build_provenance_digest": str(provenance.get("provenance_digest") or ""),
        "online_offline_artifact_match": not any(
            "artifact_set" in item or "fixed_disk_target" in item for item in blockers
        ),
        "online_health_ready": online.get("health_ready_during_launch") is True,
        "offline_ui_verified": offline.get("backend_offline_packaged_ux_verified") is True
        and offline.get("offline_notice_observed") is True,
        "offline_screenshot_sha256": offline.get("offline_screenshot_sha256") or "",
        "dmg_checksum_verified": online.get("dmg_checksum_verified") is True and offline.get("dmg_checksum_verified") is True,
        "codesign_verified": online.get("codesign_verified") is True and offline.get("codesign_verified") is True,
        "developer_id_signing_verified": distribution.get("developer_id_signing_verified") is True,
        "notarization_ticket_detected": bool(
            distribution.get("app_notarization_ticket_valid") is True
            and distribution.get("dmg_notarization_ticket_valid") is True
        ),
        "app_gatekeeper_accepted": distribution.get("app_gatekeeper_accepted") is True,
        "dmg_gatekeeper_accepted": distribution.get("dmg_gatekeeper_accepted") is True,
        "macos_distribution_verification": distribution,
        "macos_distribution_evidence_source": evidence_source,
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


def record_tauri_build_receipt(
    evidence_root: Path | str = EVIDENCE_ROOT,
    *,
    head_full: str,
    build_session_nonce: str,
) -> dict[str, Any]:
    """Issue a receipt only when the just-built signed resource proves this session.

    ``build_session_nonce`` is deliberately mandatory and is never persisted.  A
    generic post-hoc caller therefore cannot relabel an old signed App as a new
    HEAD merely by supplying a commit string.
    """
    requested_root = Path(evidence_root).expanduser().absolute()
    root_aliased = requested_root.is_symlink()
    root = requested_root.resolve()
    package_root = root / "desktop_runtime"
    measured = measure_fixed_tauri_package_artifacts(PROJECT_ROOT)
    app_path = Path(str(measured.get("app_path") or ""))
    dmg_path = Path(str(measured.get("dmg_path") or ""))
    actual_head_full = _git_head_full(PROJECT_ROOT)
    requested_head_full = head_full
    head_binding_valid = bool(requested_head_full and requested_head_full == actual_head_full)
    provenance = measured.get("build_provenance")
    provenance = dict(provenance) if isinstance(provenance, Mapping) else {}
    try:
        raw_nonce = bytes.fromhex(build_session_nonce)
    except (TypeError, ValueError):
        raw_nonce = b""
    nonce_sha256 = hashlib.sha256(raw_nonce).hexdigest() if len(raw_nonce) == 32 else ""
    policy = _load_release_identity_policy()
    source_binding = _current_source_binding(PROJECT_ROOT)
    blockers = list(measured.get("blockers") or [])
    if root_aliased or package_root.is_symlink():
        blockers.append("tauri_build_receipt_evidence_root_aliased")
    if not head_binding_valid:
        blockers.append("tauri_build_receipt_head_not_current")
    if not policy:
        blockers.append("tauri_build_receipt_release_identity_policy_invalid")
    if not source_binding:
        blockers.append("tauri_build_receipt_source_binding_unavailable")
    blockers.extend(
        _validate_embedded_provenance(
            provenance,
            head_full=requested_head_full,
            source_binding=source_binding,
            policy_digest=str(policy.get("policy_digest") or ""),
            build_receipt={
                "build_session_nonce_sha256": nonce_sha256,
                "provenance_digest": provenance.get("provenance_digest"),
            },
        )
    )
    if provenance.get("build_session_nonce_sha256") != nonce_sha256:
        blockers.append("tauri_build_receipt_session_nonce_invalid")
    material = {
        "schema_version": BUILD_RECEIPT_SCHEMA,
        "build_executed": not blockers,
        "build_command": PRODUCTION_BUILD_COMMAND,
        "head_full": requested_head_full,
        "head_binding_valid": head_binding_valid,
        "app_path": _relative_path(app_path, root.parent),
        "dmg_path": _relative_path(dmg_path, root.parent),
        "app_bundle_sha256": measured.get("app_bundle_sha256") or "",
        "dmg_sha256": measured.get("dmg_sha256") or "",
        "artifact_set_sha256": measured.get("artifact_set_sha256") or "",
        "source_archive_sha256": source_binding.get("source_archive_sha256") or "",
        "release_identity_policy_digest": policy.get("policy_digest") or "",
        "provenance_digest": provenance.get("provenance_digest") or "",
        "build_session_nonce_sha256": nonce_sha256,
        "contains_secret": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "blockers": sorted(set(blockers)),
    }
    receipt = {**material, "receipt_digest": _digest(material)}
    if blockers:
        return receipt
    package_root.mkdir(parents=True, exist_ok=True)
    receipt_path = package_root / BUILD_RECEIPT_PATH.name
    temporary = receipt_path.with_name(f".{receipt_path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(_canonical_bytes(receipt) + b"\n")
    os.replace(temporary, receipt_path)
    return receipt


__all__ = [
    "measure_fixed_tauri_package_artifacts",
    "record_tauri_build_receipt",
    "validate_tauri_production_package",
]
