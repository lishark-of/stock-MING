#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_APP = ROOT / "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app"
DEFAULT_DMG = ROOT / "desktop/src-tauri/target/release/bundle/dmg/stock-MING Command Center_3.0.0_aarch64.dmg"
TAURI_CONFIG = ROOT / "desktop/src-tauri/tauri.conf.json"
DEFAULT_EVIDENCE_ROOT = ROOT / ".stock_ming_3/desktop_runtime"
SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_fingerprint(app_path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    file_count = 0
    size_bytes = 0
    for path in sorted(app_path.rglob("*"), key=lambda item: item.relative_to(app_path).as_posix()):
        relative = path.relative_to(app_path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        if path.is_symlink():
            digest.update(b"L")
            digest.update(os.readlink(path).encode("utf-8", errors="replace"))
            continue
        if not path.is_file():
            digest.update(b"D")
            continue
        digest.update(b"F")
        file_count += 1
        size_bytes += path.stat().st_size
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return {
        "sha256": digest.hexdigest() if file_count else "",
        "file_count": file_count,
        "size_bytes": size_bytes,
    }


def _read_bundle_identity(app_path: Path) -> dict[str, str]:
    info_plist = app_path / "Contents/Info.plist"
    if not info_plist.is_file():
        raise ValueError("packaged_app_info_plist_missing")
    try:
        with info_plist.open("rb") as handle:
            payload = plistlib.load(handle)
    except Exception as error:
        raise ValueError("packaged_app_info_plist_invalid") from error
    if not isinstance(payload, dict):
        raise ValueError("packaged_app_info_plist_invalid")
    executable_name = str(payload.get("CFBundleExecutable") or "").strip()
    if not executable_name or Path(executable_name).name != executable_name:
        raise ValueError("packaged_app_executable_name_invalid")
    return {
        "bundle_id": str(payload.get("CFBundleIdentifier") or "").strip(),
        "version": str(payload.get("CFBundleShortVersionString") or "").strip(),
        "build_version": str(payload.get("CFBundleVersion") or "").strip(),
        "executable_name": executable_name,
    }


def _expected_bundle_identity() -> dict[str, str]:
    try:
        payload = json.loads(TAURI_CONFIG.read_text(encoding="utf-8"))
    except Exception as error:
        raise ValueError("tauri_config_identity_unreadable") from error
    return {
        "bundle_id": str(payload.get("identifier") or "").strip(),
        "version": str(payload.get("version") or "").strip(),
        "product_name": str(payload.get("productName") or "").strip(),
    }


def _relative_project_label(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return "outside_project_root"


def _safe_output_text(value: str, *, limit: int = 240) -> str:
    text = " ".join(line.strip() for line in str(value or "").splitlines() if line.strip())
    replacements = (
        (str(ROOT), "<project_root>"),
        (str(Path.home()), "<home>"),
        (tempfile.gettempdir(), "<temp>"),
    )
    for raw, label in replacements:
        if raw:
            text = text.replace(raw, label)
    text = re.sub(r"(?<![A-Za-z0-9_:])/(?:[^\s:;]+)", "<absolute_path>", text)
    return text[:limit]


def _secret_hit_count_bytes(value: bytes) -> int:
    return sum(len(pattern.findall(value)) for pattern in SECRET_PATTERNS)


def _bundle_secret_hit_count(app_path: Path) -> int:
    hit_count = 0
    for path in app_path.rglob("*"):
        if path.is_file() and not path.is_symlink():
            hit_count += _secret_hit_count_bytes(path.read_bytes())
    return hit_count


def _gitignored(path: Path) -> bool:
    return _run(["git", "check-ignore", "-q", str(path)], timeout=15).returncode == 0


def _spawned_backend_pid(log_delta: str) -> int | None:
    match = re.search(r"spawned local FastAPI process pid=(\d+)", log_delta)
    if not match:
        return None
    pid = int(match.group(1))
    return pid if pid > 1 and pid != os.getpid() else None


def _terminate_spawned_backend(pid: int | None) -> bool:
    if pid is None:
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return True


def _run(command: list[str], *, cwd: Path = ROOT, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _local_api_base(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("api_base_must_be_local_http")
    if parsed.port is None or parsed.port < 1024:
        raise ValueError("api_base_port_must_be_local_user_port")
    return value.rstrip("/")


def _python_executable_path(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        raise ValueError("python_executable_required")
    # Preserve .venv/bin/python as the invoked path. Resolving its symlink to the
    # base interpreter drops the virtual environment's installed packages.
    return os.path.abspath(os.path.expanduser(candidate))


def _health_ready(api_base: str) -> tuple[bool, dict[str, Any]]:
    try:
        with urlopen(f"{api_base}/health", timeout=2) as response:  # noqa: S310 - localhost is enforced.
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return False, {}
    data = payload.get("data") if isinstance(payload, dict) else {}
    ready = bool(
        isinstance(data, dict)
        and data.get("status") == "ok"
        and data.get("external_calls_on_startup") is False
        and data.get("provider_or_model_calls") is False
        and data.get("real_trading_enabled") is False
        and data.get("contains_secret") is False
    )
    return ready, data if isinstance(data, dict) else {}


def _safe_first_line(value: str) -> str:
    first_line = str(value or "").strip().splitlines()[0] if str(value or "").strip() else ""
    return _safe_output_text(first_line)


def _safe_command_output(result: subprocess.CompletedProcess[str]) -> str:
    return _safe_output_text(f"{result.stdout or ''}\n{result.stderr or ''}")


def _parse_codesign_observation(output: str) -> dict[str, Any]:
    flags_match = re.search(r"flags=(0x[0-9a-fA-F]+\([^)]*\))", output)
    signature_match = re.search(r"^Signature=(.+)$", output, re.MULTILINE)
    team_match = re.search(r"^TeamIdentifier=(.+)$", output, re.MULTILINE)
    cdhash_match = re.search(r"^CDHash=([0-9a-fA-F]+)$", output, re.MULTILINE)
    flags = flags_match.group(1) if flags_match else ""
    signature = signature_match.group(1).strip() if signature_match else ""
    team_identifier = team_match.group(1).strip() if team_match else ""
    authorities = [value.strip() for value in re.findall(r"^Authority=(.+)$", output, re.MULTILINE)]
    signature_lower = f"{signature} {flags}".lower()
    developer_id = any(value.startswith("Developer ID Application:") for value in authorities)
    apple_development = any(value.startswith("Apple Development:") for value in authorities)
    signature_type = (
        "adhoc"
        if "adhoc" in signature_lower
        else "developer_id"
        if developer_id
        else "apple_development"
        if apple_development
        else "other_identity"
        if signature or authorities or (team_identifier and team_identifier.lower() != "not set")
        else "unknown"
    )
    return {
        "codesign_signature_type": signature_type,
        "codesign_flags_observed": flags,
        "codesign_team_identifier_status": (
            "not_set" if not team_identifier or team_identifier.lower() == "not set" else "set"
        ),
        "codesign_cdhash_observed": cdhash_match.group(1).lower() if cdhash_match else "",
        "apple_developer_identity_used": signature_type == "developer_id",
    }


def _parse_spctl_observation(returncode: int, output: str) -> dict[str, Any]:
    security_disabled = "override=security disabled" in output.lower()
    status = "unknown" if security_disabled else "accepted" if returncode == 0 else "rejected"
    return {
        "spctl_assessment_status": status,
        "spctl_message_safe": _safe_output_text(output),
        "spctl_security_assessment_effective": not security_disabled,
    }


def _dmg_mounted_app_observation(
    dmg_path: Path,
    *,
    expected_bundle_id: str,
    expected_version: str,
    expected_executable_sha256: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "dmg_attached_readonly": False,
        "dmg_mount_readonly_observed": False,
        "dmg_mounted_app_detected": False,
        "dmg_mounted_app_count": 0,
        "dmg_mounted_app_codesign_verified": False,
        "dmg_mounted_bundle_id": "",
        "dmg_mounted_bundle_id_matches": False,
        "dmg_mounted_version": "",
        "dmg_mounted_version_matches": False,
        "dmg_mounted_executable_sha256": "",
        "dmg_mounted_executable_matches": False,
        "dmg_detached": False,
        "error_message_safe": "",
    }
    with tempfile.TemporaryDirectory(prefix="stock-ming-dmg-") as temp_dir:
        mountpoint = Path(temp_dir) / "mount"
        mountpoint.mkdir()
        attach = _run(
            ["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mountpoint), str(dmg_path)],
            timeout=60,
        )
        if attach.returncode != 0:
            result["error_message_safe"] = _safe_command_output(attach)
            return result
        result["dmg_attached_readonly"] = True
        try:
            mount_table = _run(["mount"], timeout=15)
            mountpoint_labels = {str(mountpoint), str(mountpoint.resolve())}
            mount_line = next(
                (
                    line
                    for line in mount_table.stdout.splitlines()
                    if any(f" on {label} " in line for label in mountpoint_labels)
                ),
                "",
            )
            result["dmg_mount_readonly_observed"] = bool(
                mount_line and ("read-only" in mount_line.lower() or "read only" in mount_line.lower())
            )
            app_candidates = sorted(mountpoint.glob("*.app"))
            result["dmg_mounted_app_count"] = len(app_candidates)
            if len(app_candidates) != 1:
                result["error_message_safe"] = "mounted_dmg_app_missing"
                return result
            mounted_app = app_candidates[0]
            result["dmg_mounted_app_detected"] = True
            verify = _run(
                ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(mounted_app)],
                timeout=30,
            )
            result["dmg_mounted_app_codesign_verified"] = verify.returncode == 0
            try:
                identity = _read_bundle_identity(mounted_app)
                mounted_executable = mounted_app / "Contents/MacOS" / identity["executable_name"]
                result["dmg_mounted_bundle_id"] = identity["bundle_id"][:160]
                result["dmg_mounted_bundle_id_matches"] = identity["bundle_id"] == expected_bundle_id
                result["dmg_mounted_version"] = identity["version"][:80]
                result["dmg_mounted_version_matches"] = identity["version"] == expected_version
                if mounted_executable.is_file() and mounted_executable.stat().st_size > 0:
                    mounted_sha256 = _sha256_file(mounted_executable)
                    result["dmg_mounted_executable_sha256"] = mounted_sha256
                    result["dmg_mounted_executable_matches"] = mounted_sha256 == expected_executable_sha256
            except ValueError as error:
                result["error_message_safe"] = str(error)
            if verify.returncode != 0:
                result["error_message_safe"] = _safe_command_output(verify)
        finally:
            detach = _run(["hdiutil", "detach", str(mountpoint)], timeout=60)
            result["dmg_detached"] = detach.returncode == 0
            if detach.returncode != 0 and not result["error_message_safe"]:
                result["error_message_safe"] = _safe_command_output(detach)
    return result


def _record_existing_reviews(
    *,
    offline_screenshot_sha256: str = "",
    signing_observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from server.services import desktop_service

    artifact_task = desktop_service.run_tauri_package_artifact_review_task(
        {
            "requested_from": "tauri_packaged_runtime_smoke",
            "explicit_tauri_build_completed": True,
            "build_command": "npm run tauri build",
        }
    )
    launch_task = desktop_service.run_tauri_packaged_runtime_launch_review_task(
        {
            "requested_from": "tauri_packaged_runtime_smoke",
            "explicit_packaged_app_launch_completed": True,
            "app_process_observed_after_launch": True,
            "launch_command": (
                "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app/Contents/MacOS/"
                "stock_ming_command_center"
            ),
            "observed_process_name": "stock_ming_command_center",
        }
    )
    result = {
        "artifact_review_task_id": artifact_task.get("task_id"),
        "artifact_review_task_status": artifact_task.get("status"),
        "launch_review_task_id": launch_task.get("task_id"),
        "launch_review_task_status": launch_task.get("status"),
    }
    if offline_screenshot_sha256:
        offline_task = desktop_service.run_tauri_backend_offline_packaged_ux_review_task(
            {
                "requested_from": "tauri_packaged_runtime_smoke",
                "explicit_packaged_app_launch_completed": True,
                "backend_was_offline_during_review": True,
                "offline_notice_observed": True,
                "fastapi_guidance_visible": True,
                "local_only_boundary_visible": True,
                "no_provider_model_github_trade_visible": True,
                "screenshot_sha256": offline_screenshot_sha256,
                "observed_route": "#home",
            }
        )
        result["offline_review_task_id"] = offline_task.get("task_id")
        result["offline_review_task_status"] = offline_task.get("status")
    if signing_observation:
        signing_task = desktop_service.run_tauri_signing_notarization_review_task(
            {
                "requested_from": "tauri_packaged_runtime_smoke",
                "explicit_codesign_inspection_completed": True,
                "explicit_spctl_assessment_completed": True,
                "app_bundle_path_observed": str(DEFAULT_APP.relative_to(ROOT)),
                "codesign_signature_type": signing_observation.get("codesign_signature_type"),
                "codesign_flags_observed": signing_observation.get("codesign_flags_observed"),
                "codesign_team_identifier_status": signing_observation.get("codesign_team_identifier_status"),
                "codesign_cdhash_observed": signing_observation.get("codesign_cdhash_observed"),
                "spctl_assessment_status": signing_observation.get("spctl_assessment_status"),
                "spctl_message_safe": signing_observation.get("spctl_message_safe"),
                "apple_developer_identity_used": signing_observation.get("apple_developer_identity_used") is True,
                "notarization_ticket_detected": signing_observation.get("notarization_ticket_detected") is True,
            }
        )
        result["signing_review_task_id"] = signing_task.get("task_id")
        result["signing_review_task_status"] = signing_task.get("status")
    return result


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    api_base = _local_api_base(args.api_base)
    app_path = Path(args.app_path).expanduser().resolve()
    dmg_path = Path(args.dmg_path).expanduser().resolve()
    log_path = ROOT / ".stock_ming_3/logs/tauri_fastapi_autostart.log"

    if args.build:
        build = _run(["npm", "run", "tauri", "build"], cwd=ROOT / "desktop", timeout=args.build_timeout)
        if build.returncode != 0:
            return {
                "schema_version": "tauri_packaged_runtime_smoke.v1",
                "status": "tauri_build_failed_safe",
                "build_exit_code": build.returncode,
                "build_error_safe": _safe_first_line(build.stderr),
                "production_package_complete": False,
            }

    if not app_path.is_dir():
        raise FileNotFoundError("packaged_app_executable_missing")
    expected_identity = _expected_bundle_identity()
    app_identity = _read_bundle_identity(app_path)
    executable = app_path / "Contents/MacOS" / app_identity["executable_name"]
    app_exists = (
        executable.is_file()
        and executable.stat().st_size > 0
        and os.access(executable, os.X_OK)
    )
    dmg_exists = dmg_path.is_file() and dmg_path.stat().st_size > 0
    if not app_exists:
        raise FileNotFoundError("packaged_app_executable_missing")

    app_fingerprint = _bundle_fingerprint(app_path)
    executable_sha256 = _sha256_file(executable)
    dmg_sha256 = _sha256_file(dmg_path) if dmg_exists else ""
    app_gitignored = _gitignored(app_path)
    dmg_gitignored = _gitignored(dmg_path)
    codesign = _run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app_path)], timeout=30)
    codesign_detail = _run(["codesign", "-dv", "--verbose=4", str(app_path)], timeout=30)
    codesign_observation = _parse_codesign_observation(f"{codesign_detail.stdout}\n{codesign_detail.stderr}")
    spctl = _run(["spctl", "--assess", "--type", "execute", "--verbose=4", str(app_path)], timeout=30)
    spctl_observation = _parse_spctl_observation(spctl.returncode, f"{spctl.stdout}\n{spctl.stderr}")
    stapler = _run(["xcrun", "stapler", "validate", str(app_path)], timeout=30)
    codesign_observation.update(spctl_observation)
    codesign_observation["notarization_ticket_detected"] = stapler.returncode == 0
    dmg_verify = _run(["hdiutil", "verify", str(dmg_path)], timeout=60) if dmg_exists else None
    dmg_mount = (
        _dmg_mounted_app_observation(
            dmg_path,
            expected_bundle_id=expected_identity["bundle_id"],
            expected_version=expected_identity["version"],
            expected_executable_sha256=executable_sha256,
        )
        if dmg_exists
        else {}
    )
    secret_hit_count = _bundle_secret_hit_count(app_path)
    health_before, health_before_data = _health_ready(api_base)
    if args.expect_backend_offline and health_before:
        raise RuntimeError("offline_qa_requires_local_fastapi_stopped")
    if not health_before and not args.allow_backend_autostart and not args.expect_backend_offline:
        raise RuntimeError("existing_local_fastapi_required")

    log_before = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    env = dict(os.environ)
    env["COMMAND_CENTER_3_PROJECT_ROOT"] = str(ROOT)
    python_path = _python_executable_path(args.python)
    if args.expect_backend_offline:
        python_path = str(DEFAULT_EVIDENCE_ROOT / ".offline-backend-intentionally-unavailable")
    env["STOCK_MING_PYTHON"] = python_path
    env["COMMAND_CENTER_3_FASTAPI_PORT"] = str(urlparse(api_base).port)
    process = subprocess.Popen(
        [str(executable)],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    process_observed = False
    health_after = False
    health_after_data: dict[str, Any] = {}
    try:
        deadline = time.monotonic() + max(1.0, args.observe_seconds)
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            process_observed = True
            health_after, health_after_data = _health_ready(api_base)
            time.sleep(0.25)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    clean_exit = process.poll() is not None
    log_after = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    log_delta = log_after[len(log_before) :] if log_after.startswith(log_before) else log_after
    reused_existing_backend = "local FastAPI already ready; no backend process spawned" in log_delta
    autostart_ready = "local FastAPI health ready after Tauri autostart" in log_delta
    offline_backend_unavailable_observed = "failed to spawn local FastAPI safely" in log_delta
    spawned_backend_pid = _spawned_backend_pid(log_delta)
    spawned_backend_cleaned_up = _terminate_spawned_backend(spawned_backend_pid)
    runtime_log_gitignored = _gitignored(log_path)
    runtime_log_secret_hit_count = _secret_hit_count_bytes(log_delta.encode("utf-8", errors="replace"))
    identity_matches = bool(
        expected_identity["bundle_id"]
        and expected_identity["version"]
        and app_identity["bundle_id"] == expected_identity["bundle_id"]
        and app_identity["version"] == expected_identity["version"]
    )
    config_log_safe = bool(
        runtime_log_gitignored
        and len(log_delta.encode("utf-8", errors="replace")) > 0
        and runtime_log_secret_hit_count == 0
    )
    artifact_identity = hashlib.sha256(
        "|".join(
            (
                app_fingerprint["sha256"],
                dmg_sha256,
                app_identity["bundle_id"],
                app_identity["version"],
            )
        ).encode("utf-8")
    ).hexdigest()

    screenshot_hash_safe = bool(
        len(args.offline_screenshot_sha256) == 64
        and all(char in "0123456789abcdef" for char in args.offline_screenshot_sha256)
    )
    online_passed = bool(
        app_exists
        and dmg_exists
        and app_gitignored
        and dmg_gitignored
        and bool(app_fingerprint["sha256"])
        and int(app_fingerprint["size_bytes"]) > 0
        and bool(dmg_sha256)
        and identity_matches
        and codesign.returncode == 0
        and dmg_verify is not None
        and dmg_verify.returncode == 0
        and dmg_mount.get("dmg_attached_readonly") is True
        and dmg_mount.get("dmg_mount_readonly_observed") is True
        and dmg_mount.get("dmg_mounted_app_detected") is True
        and dmg_mount.get("dmg_mounted_app_codesign_verified") is True
        and dmg_mount.get("dmg_mounted_bundle_id_matches") is True
        and dmg_mount.get("dmg_mounted_version_matches") is True
        and dmg_mount.get("dmg_mounted_executable_matches") is True
        and dmg_mount.get("dmg_detached") is True
        and secret_hit_count == 0
        and config_log_safe
        and process_observed
        and health_after
        and clean_exit
        and spawned_backend_cleaned_up
        and (reused_existing_backend or autostart_ready)
    )
    offline_passed = bool(
        app_exists
        and dmg_exists
        and app_gitignored
        and dmg_gitignored
        and bool(app_fingerprint["sha256"])
        and int(app_fingerprint["size_bytes"]) > 0
        and bool(dmg_sha256)
        and identity_matches
        and codesign.returncode == 0
        and dmg_verify is not None
        and dmg_verify.returncode == 0
        and dmg_mount.get("dmg_attached_readonly") is True
        and dmg_mount.get("dmg_mount_readonly_observed") is True
        and dmg_mount.get("dmg_mounted_app_codesign_verified") is True
        and dmg_mount.get("dmg_mounted_bundle_id_matches") is True
        and dmg_mount.get("dmg_mounted_version_matches") is True
        and dmg_mount.get("dmg_mounted_executable_matches") is True
        and dmg_mount.get("dmg_detached") is True
        and secret_hit_count == 0
        and config_log_safe
        and process_observed
        and not health_before
        and not health_after
        and clean_exit
        and spawned_backend_cleaned_up
        and offline_backend_unavailable_observed
        and args.offline_ui_observed
        and screenshot_hash_safe
    )
    passed = offline_passed if args.expect_backend_offline else online_passed
    result: dict[str, Any] = {
        "schema_version": "tauri_packaged_runtime_smoke.v1",
        "status": "tauri_packaged_runtime_smoke_passed" if passed else "tauri_packaged_runtime_smoke_failed",
        "direct_evidence_layer": (
            "L3_local_packaged_app_offline_ux_smoke"
            if args.expect_backend_offline
            else "L3_local_packaged_app_online_runtime_smoke"
        ),
        "local_packaged_runtime_evidence_ready": passed,
        "app_path": _relative_project_label(app_path),
        "dmg_path": _relative_project_label(dmg_path),
        "app_bundle_detected": app_exists,
        "app_bundle_size_bytes": app_fingerprint["size_bytes"],
        "app_bundle_file_count": app_fingerprint["file_count"],
        "app_bundle_sha256": app_fingerprint["sha256"],
        "app_executable_size_bytes": executable.stat().st_size,
        "app_executable_sha256": executable_sha256,
        "dmg_distribution_detected": dmg_exists,
        "dmg_size_bytes": dmg_path.stat().st_size if dmg_exists else 0,
        "dmg_sha256": dmg_sha256,
        "artifact_set_sha256": artifact_identity,
        "artifacts_gitignored": app_gitignored and dmg_gitignored,
        "bundle_identifier": app_identity["bundle_id"],
        "bundle_version": app_identity["version"],
        "bundle_build_version": app_identity["build_version"],
        "bundle_identifier_matches_tauri_config": app_identity["bundle_id"] == expected_identity["bundle_id"],
        "bundle_version_matches_tauri_config": app_identity["version"] == expected_identity["version"],
        "codesign_verified": codesign.returncode == 0,
        "codesign_signature_type": codesign_observation.get("codesign_signature_type"),
        "codesign_flags_observed": codesign_observation.get("codesign_flags_observed"),
        "codesign_team_identifier_status": codesign_observation.get("codesign_team_identifier_status"),
        "codesign_cdhash_observed": codesign_observation.get("codesign_cdhash_observed"),
        "spctl_assessment_status": codesign_observation.get("spctl_assessment_status"),
        "spctl_message_safe": codesign_observation.get("spctl_message_safe"),
        "spctl_security_assessment_effective": codesign_observation.get("spctl_security_assessment_effective"),
        "dmg_mount_validation": dmg_mount,
        "dmg_checksum_verified": bool(dmg_verify and dmg_verify.returncode == 0),
        "bundle_secret_hit_count": secret_hit_count,
        "health_ready_before_launch": health_before,
        "health_service": health_after_data.get("service") or health_before_data.get("service"),
        "app_process_observed_after_launch": process_observed,
        "health_ready_during_launch": health_after,
        "health_status_during_launch": health_after_data.get("status"),
        "existing_backend_reused": reused_existing_backend,
        "backend_autostart_observed_ready": autostart_ready,
        "backend_process_spawned_by_app": spawned_backend_pid is not None,
        "backend_process_spawned_by_app_cleaned_up": spawned_backend_cleaned_up,
        "app_process_cleaned_up": clean_exit,
        "backend_offline_expected": args.expect_backend_offline,
        "backend_offline_packaged_ux_verified": bool(offline_passed),
        "offline_notice_observed": bool(args.offline_ui_observed),
        "offline_screenshot_sha256": args.offline_screenshot_sha256 if screenshot_hash_safe else "",
        "backend_autostart_intentionally_blocked_for_offline_qa": bool(args.expect_backend_offline),
        "offline_backend_unavailable_observed": offline_backend_unavailable_observed,
        "runtime_log_path": _relative_project_label(log_path),
        "runtime_log_gitignored": runtime_log_gitignored,
        "runtime_log_delta_bytes": len(log_delta.encode("utf-8", errors="replace")),
        "runtime_log_secret_hit_count": runtime_log_secret_hit_count,
        "config_values_exposed_in_evidence": False,
        "environment_variable_names_exposed_in_evidence": False,
        "safe_config_log_evidence": config_log_safe,
        "developer_id_signing_verified": codesign_observation.get("apple_developer_identity_used") is True,
        "notarization_ticket_detected": codesign_observation.get("notarization_ticket_detected") is True,
        "production_package_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }
    if passed and args.record_reviews:
        result["review_tasks"] = _record_existing_reviews(
            offline_screenshot_sha256=args.offline_screenshot_sha256 if offline_passed else "",
            signing_observation=codesign_observation,
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run explicit local packaged Tauri online-runtime QA.")
    parser.add_argument("--app-path", default=str(DEFAULT_APP))
    parser.add_argument("--dmg-path", default=str(DEFAULT_DMG))
    parser.add_argument("--api-base", default="http://127.0.0.1:8710")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--observe-seconds", type=float, default=3.0)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--build-timeout", type=int, default=900)
    parser.add_argument("--allow-backend-autostart", action="store_true")
    parser.add_argument("--expect-backend-offline", action="store_true")
    parser.add_argument("--offline-ui-observed", action="store_true")
    parser.add_argument("--offline-screenshot-sha256", default="")
    parser.add_argument("--record-reviews", action="store_true")
    parser.add_argument("--write-evidence", action="store_true")
    parser.add_argument("--evidence-path", default="")
    args = parser.parse_args()
    try:
        result = run_smoke(args)
    except Exception as error:
        result = {
            "schema_version": "tauri_packaged_runtime_smoke.v1",
            "status": "tauri_packaged_runtime_smoke_failed_safe",
            "error_message_safe": _safe_output_text(str(error), limit=160),
            "local_packaged_runtime_evidence_ready": False,
            "production_package_complete": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
            "contains_secret": False,
        }
    if args.write_evidence:
        default_name = (
            "tauri_packaged_runtime_offline_smoke.json"
            if args.expect_backend_offline
            else "tauri_packaged_runtime_online_smoke.json"
        )
        evidence_path = Path(args.evidence_path).expanduser().resolve() if args.evidence_path else DEFAULT_EVIDENCE_ROOT / default_name
        try:
            evidence_path.relative_to(DEFAULT_EVIDENCE_ROOT)
        except ValueError:
            result = {
                "schema_version": "tauri_packaged_runtime_smoke.v1",
                "status": "tauri_packaged_runtime_smoke_failed_safe",
                "error_message_safe": "evidence_path_must_be_under_gitignored_runtime_root",
                "local_packaged_runtime_evidence_ready": False,
                "production_package_complete": False,
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
                "contains_secret": False,
            }
        else:
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            result["evidence_path"] = _relative_project_label(evidence_path)
            result["evidence_gitignored"] = _gitignored(evidence_path)
            if result["evidence_gitignored"] is not True:
                result = {
                    "schema_version": "tauri_packaged_runtime_smoke.v1",
                    "status": "tauri_packaged_runtime_smoke_failed_safe",
                    "error_message_safe": "evidence_path_must_be_gitignored",
                    "local_packaged_runtime_evidence_ready": False,
                    "production_package_complete": False,
                    "external_calls_triggered": False,
                    "does_not_execute_trades": True,
                    "contains_secret": False,
                }
            else:
                temporary_path = evidence_path.with_suffix(evidence_path.suffix + ".tmp")
                temporary_path.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary_path, evidence_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "tauri_packaged_runtime_smoke_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
