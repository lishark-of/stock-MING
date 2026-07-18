#!/usr/bin/env python3
"""Fail-closed production Tauri build entry for signed/notarized distribution.

This is intentionally separate from ordinary frontend CI.  It refuses a
dirty tree, removes the two fixed stale package targets, embeds current tracked
source provenance inside the App before signing, binds signing to a root-owned
Team/certificate policy, then atomically issues the nonce-bound build receipt.
It does not print certificate, Team, credential, or environment values.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services.tauri_package_verifier import (
    EVIDENCE_ROOT,
    FIXED_APP_RELATIVE,
    FIXED_DMG_RELATIVE,
    PROVENANCE_RELATIVE,
    PROVENANCE_SCHEMA,
    SYSTEM_GIT,
    SYSTEM_SECURITY,
    _canonical_bytes,
    _current_source_binding,
    _digest,
    _load_release_identity_policy,
    _read_embedded_provenance,
    record_tauri_build_receipt,
)


DESKTOP_ROOT = PROJECT_ROOT / "desktop"
SYSTEM_NODE = Path("/opt/homebrew/bin/node")
NPM_CLI = Path("/opt/homebrew/lib/node_modules/npm/bin/npm-cli.js")
IDENTITY_OVERRIDE_NAMES = {
    "APPLE_CERTIFICATE",
    "APPLE_CERTIFICATE_PASSWORD",
    "APPLE_SIGNING_IDENTITY",
    "TAURI_SIGNING_PRIVATE_KEY",
    "TAURI_SIGNING_PRIVATE_KEY_PASSWORD",
}


def _controlled_build_env(policy: dict[str, object]) -> dict[str, str] | None:
    if any(name in os.environ for name in IDENTITY_OVERRIDE_NAMES):
        return None
    expected_team = str(policy.get("team_identifier") or "")
    if "APPLE_TEAM_ID" in os.environ and os.environ.get("APPLE_TEAM_ID") != expected_team:
        return None
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DYLD_", "NPM_CONFIG_", "TAURI_"))
        and key not in {"PYTHONPATH", "NODE_OPTIONS"}
    }
    environment["PATH"] = (
        "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:"
        f"{Path.home() / '.cargo/bin'}"
    )
    environment["LANG"] = "C"
    environment["LC_ALL"] = "C"
    return environment


def _repository_clean_and_head() -> str:
    try:
        status = subprocess.run(
            [SYSTEM_GIT, "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"},
        )
        head = subprocess.run(
            [SYSTEM_GIT, "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if status.returncode != 0 or status.stdout or head.returncode != 0:
        return ""
    value = head.stdout.strip()
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else ""


def _matching_keychain_identity(policy: dict[str, object]) -> bool:
    common_name = str(policy.get("developer_id_application_common_name") or "")
    certificate_sha256 = str(policy.get("certificate_sha256") or "")
    try:
        identities = subprocess.run(
            [SYSTEM_SECURITY, "find-identity", "-v", "-p", "codesigning"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"},
        )
        certificate = subprocess.run(
            [SYSTEM_SECURITY, "find-certificate", "-c", common_name, "-p"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return False
    identity_names = re.findall(r'"(Developer ID Application: [^"]+)"', identities.stdout or "")
    if identities.returncode != 0 or identity_names.count(common_name) != 1 or certificate.returncode != 0:
        return False
    pem_blocks = re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        certificate.stdout or "",
        re.DOTALL,
    )
    fingerprints: list[str] = []
    for block in pem_blocks:
        try:
            der = ssl.PEM_cert_to_DER_cert(block)
            fingerprints.append(hashlib.sha256(der).hexdigest())
        except ValueError:
            return False
    return fingerprints == [certificate_sha256]


def _remove_fixed_old_artifacts() -> bool:
    for relative, directory in ((FIXED_APP_RELATIVE, True), (FIXED_DMG_RELATIVE, False)):
        path = PROJECT_ROOT / relative
        try:
            cursor = PROJECT_ROOT
            if cursor.is_symlink() or not cursor.is_dir():
                return False
            for index, part in enumerate(relative.parts):
                cursor = cursor / part
                try:
                    metadata = cursor.lstat()
                except FileNotFoundError:
                    break
                if stat.S_ISLNK(metadata.st_mode):
                    return False
                if index < len(relative.parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
                    return False
            if not path.exists():
                continue
            metadata = path.lstat()
            if directory and not stat.S_ISDIR(metadata.st_mode):
                return False
            if not directory and not stat.S_ISREG(metadata.st_mode):
                return False
            shutil.rmtree(path) if directory else path.unlink()
        except OSError:
            return False
    return True


def main() -> int:
    if platform.system() != "Darwin":
        print("production_tauri_build_blocked: macos_required", file=sys.stderr)
        return 2
    policy = _load_release_identity_policy()
    if not policy:
        print("production_tauri_build_blocked: approved_release_identity_policy_required", file=sys.stderr)
        return 3
    environment = _controlled_build_env(policy)
    if environment is None:
        print("production_tauri_build_blocked: signing_environment_conflicts_with_policy", file=sys.stderr)
        return 4
    head_full = _repository_clean_and_head()
    if not head_full:
        print("production_tauri_build_blocked: repository_must_be_clean", file=sys.stderr)
        return 5
    source_binding = _current_source_binding(PROJECT_ROOT)
    if not source_binding or not _matching_keychain_identity(policy):
        print("production_tauri_build_blocked: approved_signing_identity_unavailable", file=sys.stderr)
        return 6
    if not SYSTEM_NODE.is_file() or not NPM_CLI.is_file() or not _remove_fixed_old_artifacts():
        print("production_tauri_build_blocked: trusted_build_entry_or_target_invalid", file=sys.stderr)
        return 7

    nonce = secrets.token_bytes(32)
    unsigned_provenance = {
        "schema_version": PROVENANCE_SCHEMA,
        "head_full": head_full,
        **source_binding,
        "release_identity_policy_digest": policy["policy_digest"],
        "build_session_nonce_sha256": hashlib.sha256(nonce).hexdigest(),
        "contains_secret": False,
        "external_calls_triggered": False,
    }
    provenance = {**unsigned_provenance, "provenance_digest": _digest(unsigned_provenance)}
    overlay = {
        "bundle": {
            "resources": {},
            "macOS": {
                "signingIdentity": policy["developer_id_application_common_name"],
                "hardenedRuntime": True,
            },
        }
    }
    try:
        with tempfile.TemporaryDirectory(prefix="stock-ming-tauri-production-") as temp_dir:
            temp = Path(temp_dir)
            provenance_path = temp / "command-center-build-provenance.json"
            overlay_path = temp / "tauri-production-overlay.json"
            provenance_path.write_bytes(_canonical_bytes(provenance) + b"\n")
            overlay["bundle"]["resources"] = {
                str(provenance_path): PROVENANCE_RELATIVE.relative_to("Contents/Resources").as_posix()
            }
            overlay_path.write_bytes(_canonical_bytes(overlay) + b"\n")
            build = subprocess.run(
                [
                    str(SYSTEM_NODE),
                    str(NPM_CLI),
                    "run",
                    "tauri",
                    "--",
                    "build",
                    "--config",
                    str(overlay_path),
                ],
                cwd=DESKTOP_ROOT,
                timeout=1800,
                check=False,
                env=environment,
            )
    except (OSError, subprocess.SubprocessError):
        print("production_tauri_build_failed_safe: build_process_failed", file=sys.stderr)
        return 8
    if build.returncode != 0:
        print("production_tauri_build_failed_safe: tauri_build_failed", file=sys.stderr)
        return int(build.returncode or 9)
    if _repository_clean_and_head() != head_full:
        print("production_tauri_build_failed_safe: repository_changed_during_build", file=sys.stderr)
        return 10
    embedded = _read_embedded_provenance(PROJECT_ROOT / FIXED_APP_RELATIVE)
    if embedded != provenance:
        print("production_tauri_build_failed_safe: signed_provenance_missing", file=sys.stderr)
        return 11
    receipt = record_tauri_build_receipt(
        EVIDENCE_ROOT,
        head_full=head_full,
        build_session_nonce=nonce.hex(),
    )
    if receipt.get("build_executed") is not True:
        print("production_tauri_build_failed_safe: provenance_receipt_rejected", file=sys.stderr)
        return 12
    print("production_tauri_build_completed: formal_distribution_verification_required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
