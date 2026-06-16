from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
from pathlib import Path
from typing import Any

from storage.sqlite_meta import SQLiteMetaStore

from .task_service import create_task_record, update_task_status

PACKET_KEY = "command_center_3_desktop_shell_preflight_cache"
SCHEMA_VERSION = "desktop_shell_preflight_cache.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
DESKTOP_ROOT = PROJECT_ROOT / "desktop"
TAURI_RELEASE_BINARY = DESKTOP_ROOT / "src-tauri" / "target" / "release" / "stock_ming_command_center"
TAURI_BUNDLE_ROOT = DESKTOP_ROOT / "src-tauri" / "target" / "release" / "bundle"
TAURI_PACKAGE_ARTIFACT_REVIEW_PACKET_KEY = "command_center_3_tauri_package_artifact_review_packet"
TAURI_PACKAGE_ARTIFACT_REVIEW_TASK_TYPE = "run_tauri_package_artifact_review"
TAURI_PACKAGED_RUNTIME_LAUNCH_REVIEW_PACKET_KEY = "command_center_3_tauri_packaged_runtime_launch_review_packet"
TAURI_PACKAGED_RUNTIME_LAUNCH_REVIEW_TASK_TYPE = "run_tauri_packaged_runtime_launch_review"
TAURI_BACKEND_OFFLINE_PACKAGED_UX_REVIEW_PACKET_KEY = "command_center_3_tauri_backend_offline_packaged_ux_review_packet"
TAURI_BACKEND_OFFLINE_PACKAGED_UX_REVIEW_TASK_TYPE = "run_tauri_backend_offline_packaged_ux_review"
TAURI_BACKEND_STARTUP_RUNTIME_REVIEW_PACKET_KEY = "command_center_3_tauri_backend_startup_runtime_review_packet"
TAURI_BACKEND_STARTUP_RUNTIME_REVIEW_TASK_TYPE = "run_tauri_backend_startup_runtime_review"
FRONTEND_API_CLIENT = DESKTOP_ROOT / "src" / "api" / "client.ts"
FRONTEND_PAGE_STATE_BANNER = DESKTOP_ROOT / "src" / "components" / "PageStateBanner.tsx"
FRONTEND_BACKEND_OFFLINE_NOTICE = DESKTOP_ROOT / "src" / "components" / "BackendOfflineNotice.tsx"
FRONTEND_STYLES = DESKTOP_ROOT / "src" / "styles.css"
ROOT_GITIGNORE = PROJECT_ROOT / ".gitignore"
COMMAND_CENTER_3_LAUNCHER = PROJECT_ROOT / "scripts" / "start_command_center_3.command"
COMMAND_CENTER_3_SHORTCUT_INSTALLER = PROJECT_ROOT / "scripts" / "install_command_center_3_desktop_shortcut.sh"
TAURI_PACKAGE_DURABLE_EVIDENCE_SCHEMA_VERSION = "tauri_package_durable_evidence_recipe.v1"
TAURI_PACKAGE_DURABLE_EVIDENCE_KEYS = (
    "preflight_cache_boundary_visible",
    "release_manifest_visible",
    "readiness_receipt_visible",
    "packaged_runtime_qa_matrix_visible",
    "release_artifact_shape_visible",
    "app_bundle_dmg_evidence_required",
    "packaged_app_launch_qa_required",
    "backend_startup_runtime_evidence_required",
    "backend_offline_packaged_ux_required",
    "config_log_runtime_path_evidence_required",
    "signing_notarization_review_required",
    "production_package_promotion_review_required",
    "no_build_runtime_provider_trade_secret_boundary",
)
TAURI_PACKAGE_DURABLE_EVIDENCE_LABELS = {
    "preflight_cache_boundary_visible": "Preflight cache boundary is visible",
    "release_manifest_visible": "Release manifest is visible",
    "readiness_receipt_visible": "Readiness receipt is visible",
    "packaged_runtime_qa_matrix_visible": "Packaged runtime QA matrix is visible",
    "release_artifact_shape_visible": "Release artifact shape is visible",
    "app_bundle_dmg_evidence_required": ".app/DMG evidence is required",
    "packaged_app_launch_qa_required": "Packaged app launch QA is required",
    "backend_startup_runtime_evidence_required": "Backend startup runtime evidence is required",
    "backend_offline_packaged_ux_required": "Packaged offline UX evidence is required",
    "config_log_runtime_path_evidence_required": "Config/log runtime path evidence is required",
    "signing_notarization_review_required": "Signing/notarization review is required",
    "production_package_promotion_review_required": "Production package promotion review is required",
    "no_build_runtime_provider_trade_secret_boundary": "No build/runtime/provider/trade/secret boundary is preserved",
}


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "desktop_shell_preflight_cache_not_json_serializable"}


def _path_label(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _read_source_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _file_row(path: Path, label: str, role: str) -> dict[str, Any]:
    return {
        "label": label,
        "path": _path_label(path),
        "role": role,
        "exists": path.exists(),
        "kind": "directory" if path.is_dir() else "file",
    }


def _tauri_build_artifact_summary() -> dict[str, Any]:
    binary_exists = TAURI_RELEASE_BINARY.exists() and TAURI_RELEASE_BINARY.is_file()
    stat = TAURI_RELEASE_BINARY.stat() if binary_exists else None
    bundle_root = TAURI_BUNDLE_ROOT
    bundle_app_root = bundle_root / "macos"
    bundle_dmg_root = bundle_root / "dmg"
    bundle_app_paths = sorted(path for path in bundle_app_root.glob("*.app") if path.is_dir()) if bundle_app_root.exists() else []
    bundle_dmg_paths = sorted(path for path in bundle_dmg_root.glob("*.dmg") if path.is_file()) if bundle_dmg_root.exists() else []
    temp_dmg_paths = sorted(path for path in bundle_root.glob("**/rw.*.dmg") if path.is_file()) if bundle_root.exists() else []
    bundle_app_count = len(bundle_app_paths)
    bundle_dmg_count = len(bundle_dmg_paths)
    binary_executable = bool(binary_exists and os.access(TAURI_RELEASE_BINARY, os.X_OK))
    return {
        "schema_version": "tauri_build_artifact_detection.v1",
        "status": "artifact_detected" if binary_exists else "artifact_missing",
        "binary_path": _path_label(TAURI_RELEASE_BINARY),
        "binary_exists": binary_exists,
        "binary_size_bytes": stat.st_size if stat else 0,
        "binary_modified_at": _dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") if stat else None,
        "binary_executable": binary_executable,
        "binary_kind": "macos_mach_o_release_binary" if binary_exists else "missing",
        "bundle_root_path": _path_label(bundle_root),
        "bundle_root_exists": bundle_root.exists(),
        "bundle_app_count": bundle_app_count,
        "bundle_dmg_count": bundle_dmg_count,
        "bundle_app_path": _path_label(bundle_app_paths[0]) if bundle_app_paths else "",
        "bundle_dmg_path": _path_label(bundle_dmg_paths[0]) if bundle_dmg_paths else "",
        "temporary_dmg_count": len(temp_dmg_paths),
        "temporary_dmg_ignored_for_distribution": bool(temp_dmg_paths),
        "packaged_app_bundle_detected": bundle_app_count > 0,
        "distribution_dmg_detected": bundle_dmg_count > 0,
        "detected_by_get_cache": True,
        "build_command_executed_by_get_cache": False,
        "artifact_is_gitignored": True,
        "packaged_runtime_validated": False,
        "backend_offline_ui_packaged_runtime_verified": False,
        "macos_signing_notarization_ready": False,
        "contains_secret": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "GET desktop preflight only detects a local Tauri release artifact; it does not run npm, cargo, Tauri, backend sidecars, signing, providers, models, GitHub, or trades.",
    }


def _gitignore_contains(pattern: str) -> bool:
    return pattern in _read_source_safe(ROOT_GITIGNORE)


def _release_manifest_row(
    criterion: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    local_contract_required: bool = True,
    production_blocker: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "local_contract_required": bool(local_contract_required),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "loads_token_or_key": False,
        "reads_config_values": False,
        "writes_log_files": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _tauri_release_manifest_contract(
    *,
    tauri_config: dict[str, Any],
    production_runtime_contract: dict[str, Any],
    tauri_build_artifact: dict[str, Any],
    packaged_runtime_qa_contract: dict[str, Any],
) -> dict[str, Any]:
    product_name = str(tauri_config.get("product_name") or "")
    app_version = str(tauri_config.get("version") or "")
    bundle_identifier = str(tauri_config.get("identifier") or "")
    frontend_dist = str(tauri_config.get("frontend_dist") or "")
    dev_url = str(tauri_config.get("dev_url") or "")
    before_build_command = str(tauri_config.get("before_build_command") or "")
    icon_path = DESKTOP_ROOT / "src-tauri" / "icons" / "icon.png"
    dist_gitignored = _gitignore_contains("desktop/dist/")
    target_gitignored = _gitignore_contains("desktop/src-tauri/target/")
    local_manifest_ready = all(
        (
            bool(product_name),
            bool(app_version),
            bool(bundle_identifier),
            frontend_dist == "../dist",
            bool(tauri_config.get("dev_url_is_localhost")),
            production_runtime_contract.get("config_paths_declared") is True,
            production_runtime_contract.get("log_paths_declared") is True,
            packaged_runtime_qa_contract.get("schema_version") == "tauri_packaged_runtime_qa_contract.v1",
        )
    )
    rows = [
        _release_manifest_row(
            "app_identity_manifest_declared",
            "passed" if product_name and app_version and bundle_identifier else "blocked",
            bool(product_name and app_version and bundle_identifier),
            evidence=f"productName={product_name or 'missing'}; version={app_version or 'missing'}; identifier={bundle_identifier or 'missing'}",
        ),
        _release_manifest_row(
            "frontend_dist_manifest_declared",
            "passed" if frontend_dist == "../dist" and before_build_command == "npm run build" else "blocked",
            frontend_dist == "../dist" and before_build_command == "npm run build",
            evidence=f"frontendDist={frontend_dist or 'missing'}; beforeBuildCommand={before_build_command or 'missing'}",
        ),
        _release_manifest_row(
            "local_dev_url_manifest_declared",
            "passed" if tauri_config.get("dev_url_is_localhost") else "blocked",
            bool(tauri_config.get("dev_url_is_localhost")),
            evidence=f"devUrl={dev_url or 'missing'}",
        ),
        _release_manifest_row(
            "icon_asset_present",
            "passed" if icon_path.exists() else "blocked",
            icon_path.exists(),
            evidence=f"icon={_path_label(icon_path)}; exists={icon_path.exists()}",
        ),
        _release_manifest_row(
            "generated_artifacts_gitignored",
            "passed" if dist_gitignored and target_gitignored else "blocked",
            dist_gitignored and target_gitignored,
            evidence=f"desktop/dist/ ignored={dist_gitignored}; desktop/src-tauri/target/ ignored={target_gitignored}",
        ),
        _release_manifest_row(
            "backend_startup_policy_manifest_declared",
            "passed",
            True,
            evidence=f"strategy={production_runtime_contract.get('backend_startup_strategy')}; manual_backend_launch_required={production_runtime_contract.get('manual_backend_launch_required')}",
        ),
        _release_manifest_row(
            "config_log_path_manifest_declared",
            "passed"
            if production_runtime_contract.get("config_paths_declared") and production_runtime_contract.get("log_paths_declared")
            else "blocked",
            bool(production_runtime_contract.get("config_paths_declared") and production_runtime_contract.get("log_paths_declared")),
            evidence=f"config={production_runtime_contract.get('config_file_policy')}; log={production_runtime_contract.get('log_file_policy')}",
        ),
        _release_manifest_row(
            "release_artifact_manifest_observed",
            "passed" if tauri_build_artifact.get("binary_exists") else "pending",
            bool(tauri_build_artifact.get("binary_exists")),
            evidence=f"artifact_status={tauri_build_artifact.get('status')}; path={tauri_build_artifact.get('binary_path')}",
            local_contract_required=False,
            production_blocker=not bool(tauri_build_artifact.get("binary_exists")),
        ),
        _release_manifest_row(
            "packaged_runtime_qa_manifest_pending",
            "pending",
            False,
            evidence=f"qa_status={packaged_runtime_qa_contract.get('status')}; pending_qa_count={packaged_runtime_qa_contract.get('pending_qa_count')}",
            local_contract_required=False,
            production_blocker=True,
        ),
        _release_manifest_row(
            "signing_notarization_manifest_pending",
            "pending",
            False,
            evidence="macOS signing, notarization, and distribution review remain future explicit production-package acceptance steps",
            local_contract_required=False,
            production_blocker=True,
        ),
        _release_manifest_row(
            "startup_safety_boundary_declared",
            "passed",
            True,
            evidence="release manifest contract does not start Tushare, DeepSeek, GitHub probes, FastAPI, Tauri, packaged app, or trade paths",
        ),
    ]
    local_blockers = [row["criterion"] for row in rows if row.get("local_contract_required") and not row.get("passed")]
    production_blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    return {
        "schema_version": "tauri_release_manifest_contract.v1",
        "status": "release_manifest_contract_ready_packaged_execution_pending" if not local_blockers else "release_manifest_contract_blocked",
        "scope": "local_tauri_release_manifest_contract_no_build_or_runtime_execution",
        "ltg": "LTG-09",
        "local_release_manifest_ready": not local_blockers,
        "ready_for_explicit_tauri_build_review": not local_blockers,
        "ready_for_production_package_promotion": False,
        "production_package_complete": False,
        "product_name": product_name,
        "app_version": app_version,
        "bundle_identifier": bundle_identifier,
        "frontend_dist": frontend_dist,
        "before_build_command": before_build_command,
        "dev_url": dev_url,
        "dev_url_is_localhost": bool(tauri_config.get("dev_url_is_localhost")),
        "icon_asset_path": _path_label(icon_path),
        "icon_asset_present": icon_path.exists(),
        "desktop_dist_gitignored": dist_gitignored,
        "tauri_target_gitignored": target_gitignored,
        "backend_startup_strategy": production_runtime_contract.get("backend_startup_strategy"),
        "manual_backend_launch_required": True,
        "backend_sidecar_autostart_enabled": False,
        "config_file_policy": production_runtime_contract.get("config_file_policy"),
        "log_file_policy": production_runtime_contract.get("log_file_policy"),
        "release_artifact_status": tauri_build_artifact.get("status"),
        "release_artifact_path": tauri_build_artifact.get("binary_path"),
        "packaged_runtime_qa_status": packaged_runtime_qa_contract.get("status"),
        "packaged_runtime_pending_qa_count": packaged_runtime_qa_contract.get("pending_qa_count"),
        "tauri_build_executed": False,
        "npm_or_cargo_executed": False,
        "tauri_runtime_started": False,
        "packaged_app_opened": False,
        "fastapi_started": False,
        "config_values_read": False,
        "log_files_written": False,
        "signing_notarization_done": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "local_blocker_count": len(local_blockers),
        "production_blocker_count": len(production_blockers),
        "local_blockers": local_blockers,
        "production_blockers": production_blockers,
        "row_count": len(rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tauri_release_manifest_contract",
                "source": "tauri config, gitignore, desktop runtime contract, packaged QA contract",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_release_manifest_contract",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This release manifest contract makes package identity, dist, artifact ignore policy, backend startup policy, config/log path policy, packaged QA gaps, and signing/notarization gaps visible. It does not run npm, cargo, Tauri, packaged app, FastAPI, providers, models, GitHub probes, config reads, log writes, trades, or production package promotion.",
    }


def _command_row(name: str, role: str, required_for: str) -> dict[str, Any]:
    executable = shutil.which(name)
    return {
        "command": name,
        "role": role,
        "required_for": required_for,
        "available": bool(executable),
        "path_available": bool(executable),
    }


def _package_json_summary() -> dict[str, Any]:
    path = DESKTOP_ROOT / "package.json"
    if not path.exists():
        return {"available": False, "scripts": [], "dependencies": [], "dev_dependencies": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"available": False, "error_message_safe": str(exc).splitlines()[0][:240], "scripts": [], "dependencies": [], "dev_dependencies": []}
    scripts = payload.get("scripts") if isinstance(payload.get("scripts"), dict) else {}
    dependencies = payload.get("dependencies") if isinstance(payload.get("dependencies"), dict) else {}
    dev_dependencies = payload.get("devDependencies") if isinstance(payload.get("devDependencies"), dict) else {}
    return {
        "available": True,
        "name": payload.get("name"),
        "version": payload.get("version"),
        "scripts": sorted(str(key) for key in scripts),
        "dependencies": sorted(str(key) for key in dependencies),
        "dev_dependencies": sorted(str(key) for key in dev_dependencies),
        "has_vite": "vite" in dependencies,
        "has_react": "react" in dependencies and "react-dom" in dependencies,
        "has_echarts": "echarts" in dependencies,
        "has_tauri_cli": "@tauri-apps/cli" in dev_dependencies,
        "has_build_script": "build" in scripts,
        "has_dev_script": "dev" in scripts,
        "has_tauri_script": "tauri" in scripts,
    }


def _tauri_config_summary() -> dict[str, Any]:
    path = DESKTOP_ROOT / "src-tauri" / "tauri.conf.json"
    if not path.exists():
        return {"available": False, "path": _path_label(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"available": False, "path": _path_label(path), "error_message_safe": str(exc).splitlines()[0][:240]}
    build = payload.get("build") if isinstance(payload.get("build"), dict) else {}
    app = payload.get("app") if isinstance(payload.get("app"), dict) else {}
    windows = app.get("windows") if isinstance(app.get("windows"), list) else []
    dev_url = str(build.get("devUrl") or "")
    return {
        "available": True,
        "path": _path_label(path),
        "product_name": payload.get("productName"),
        "version": payload.get("version"),
        "identifier": payload.get("identifier"),
        "frontend_dist": build.get("frontendDist"),
        "dev_url": dev_url,
        "dev_url_is_localhost": dev_url.startswith("http://127.0.0.1") or dev_url.startswith("http://localhost"),
        "before_dev_command": build.get("beforeDevCommand"),
        "before_build_command": build.get("beforeBuildCommand"),
        "window_count": len(windows),
        "backend_sidecar_configured": False,
        "production_package_build_attempted": False,
        "contains_secret": False,
    }


def _api_base_summary(api_base: str) -> dict[str, Any]:
    normalized = str(api_base or "").strip()
    is_local = normalized.startswith("http://127.0.0.1") or normalized.startswith("http://localhost")
    return {
        "api_base": normalized,
        "is_localhost": is_local,
        "expected_health_endpoint": f"{normalized.rstrip('/')}/health" if normalized else "",
        "configured_by": "VITE_API_BASE_URL" if os.getenv("VITE_API_BASE_URL") else "default_localhost_8710",
        "frontend_uses_fastapi_only": True,
        "contains_secret": False,
        "does_not_autostart_backend": True,
    }


def _dev_launch_plan(api_base: str) -> list[dict[str, Any]]:
    return [
        {
            "step": "shortcut",
            "name": "双击 Command Center 3.0 本地入口",
            "command": "scripts/start_command_center_3.command",
            "required_for": "开发/日常本地入口：启动 FastAPI、Vite 并打开本地 3.0 页面",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
            "starts_when_user_runs": True,
            "production_package_complete": False,
        },
        {
            "step": "1",
            "name": "启动 FastAPI 后端",
            "command": "scripts/dev_server.sh",
            "required_for": "React/Tauri 页面读取 cache API",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
            "starts_when_user_runs": True,
        },
        {
            "step": "2",
            "name": "启动 Vite 前端",
            "command": "cd desktop && npm run dev",
            "required_for": "浏览器开发模式",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
            "starts_when_user_runs": True,
        },
        {
            "step": "3",
            "name": "启动 Tauri 桌面壳",
            "command": "cd desktop && npm run tauri dev",
            "required_for": "桌面窗口开发模式；需要 Rust/Cargo",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
            "starts_when_user_runs": True,
        },
        {
            "step": "check",
            "name": "连接检查",
            "command": f"GET {api_base.rstrip('/')}/health",
            "required_for": "确认前端只连接本地 FastAPI",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
            "starts_when_user_runs": False,
        },
    ]


def _desktop_launcher_contract(api_base: str) -> dict[str, Any]:
    source = _read_source_safe(COMMAND_CENTER_3_LAUNCHER)
    installer_source = _read_source_safe(COMMAND_CENTER_3_SHORTCUT_INSTALLER)
    required_markers = (
        "Command Center 3.0 local launcher",
        "scripts/dev_server.sh",
        "npm run dev",
        "VITE_API_BASE_URL",
        "STOCK_MING_ALLOW_SYSTEM_PYTHON",
        "desktop/node_modules",
        ".stock_ming_3/logs",
        "open \"$VITE_URL\"",
        "no Tushare, DeepSeek, GitHub, or trading call",
    )
    required_installer_markers = (
        "Command Center 3.0 desktop shortcut installer",
        "start_command_center_3.command",
        "ln -sfn",
        "STOCK_MING_DESKTOP_DIR",
        "STOCK_MING_DESKTOP_SHORTCUT_NAME",
        "creates only a local symlink",
        "no Tushare, DeepSeek, GitHub, or trading call",
    )
    marker_rows = [
        {
            "criterion": f"launcher_marker:{marker}",
            "status": "passed" if marker in source else "blocked",
            "passed": marker in source,
            "evidence": _path_label(COMMAND_CENTER_3_LAUNCHER),
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
        for marker in required_markers
    ] + [
        {
            "criterion": f"shortcut_installer_marker:{marker}",
            "status": "passed" if marker in installer_source else "blocked",
            "passed": marker in installer_source,
            "evidence": _path_label(COMMAND_CENTER_3_SHORTCUT_INSTALLER),
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
        for marker in required_installer_markers
    ]
    local_ready = (
        COMMAND_CENTER_3_LAUNCHER.exists()
        and COMMAND_CENTER_3_SHORTCUT_INSTALLER.exists()
        and all(row["passed"] for row in marker_rows)
    )
    return {
        "schema_version": "command_center_3_local_launcher_contract.v1",
        "status": "local_launcher_ready_dev_only" if local_ready else "local_launcher_contract_blocked",
        "scope": "manual_local_dev_launcher_not_production_package",
        "ltg": "LTG-09",
        "launcher_path": _path_label(COMMAND_CENTER_3_LAUNCHER),
        "launcher_exists": COMMAND_CENTER_3_LAUNCHER.exists(),
        "launcher_executable": os.access(COMMAND_CENTER_3_LAUNCHER, os.X_OK),
        "shortcut_installer_path": _path_label(COMMAND_CENTER_3_SHORTCUT_INSTALLER),
        "shortcut_installer_exists": COMMAND_CENTER_3_SHORTCUT_INSTALLER.exists(),
        "shortcut_installer_executable": os.access(COMMAND_CENTER_3_SHORTCUT_INSTALLER, os.X_OK),
        "desktop_shortcut_target_name": "stock-MING Command Center 3.command",
        "desktop_shortcut_install_command": "scripts/install_command_center_3_desktop_shortcut.sh",
        "desktop_shortcut_installer_creates_symlink": "ln -sfn" in installer_source,
        "desktop_shortcut_installer_starts_services": False,
        "desktop_shortcut_installer_reads_credentials": False,
        "api_base": api_base,
        "vite_url": "http://127.0.0.1:5173",
        "uses_project_venv_first": "PROJECT_ROOT}/.venv/bin/python" in source,
        "allows_system_python_only_when_explicit": "STOCK_MING_ALLOW_SYSTEM_PYTHON" in source,
        "requires_node_modules": "desktop/node_modules" in source,
        "starts_fastapi_when_user_runs": "scripts/dev_server.sh" in source,
        "starts_vite_when_user_runs": "npm run dev" in source,
        "opens_local_browser_when_user_runs": 'open "$VITE_URL"' in source,
        "writes_ignored_local_logs_when_user_runs": ".stock_ming_3/logs" in source,
        "cache_get_starts_launcher": False,
        "cache_get_installs_shortcut": False,
        "cache_get_starts_fastapi": False,
        "cache_get_starts_vite": False,
        "production_package_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "loads_token_or_key": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": marker_rows,
        "row_count": len(marker_rows),
        "call_ledger": [
            {
                "api": "local_command_center_3_launcher_contract",
                "source": f"{_path_label(COMMAND_CENTER_3_LAUNCHER)}; {_path_label(COMMAND_CENTER_3_SHORTCUT_INSTALLER)}",
                "row_count": len(marker_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_launcher_contract",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This contract exposes a manual local Command Center 3.0 dev launcher. It does not run the launcher from GET cache and is not Tauri production package evidence.",
    }


def _production_launch_plan(api_base: str) -> list[dict[str, Any]]:
    return [
        {
            "step": "1",
            "name": "构建 React/Vite 静态资源",
            "command": "cd desktop && npm run build",
            "required_for": "Tauri package build",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
        },
        {
            "step": "2",
            "name": "打包 Tauri 桌面应用",
            "command": "cd desktop && npm run tauri build",
            "required_for": "生产桌面包；需要 Rust/Cargo",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
        },
        {
            "step": "3",
            "name": "启动 FastAPI 本地后端",
            "command": "scripts/dev_server.sh",
            "required_for": f"当前阶段桌面壳连接 {api_base.rstrip('/')}",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
        },
    ]


def _production_runtime_row(
    criterion: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    production_blocker: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "external_calls_triggered": False,
        "loads_token_or_key": False,
        "reads_config_values": False,
        "writes_log_files": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _production_runtime_contract(api_base_info: dict[str, Any], tauri_config: dict[str, Any]) -> dict[str, Any]:
    config_dir = "~/.stock_ming_3"
    log_dir = "~/.stock_ming_3/logs"
    rows = [
        _production_runtime_row(
            "backend_startup_strategy_declared",
            "passed",
            True,
            evidence="current package uses manual FastAPI launch; sidecar remains a future explicit packaging decision",
        ),
        _production_runtime_row(
            "api_base_localhost_contract",
            "passed" if api_base_info.get("is_localhost") else "blocked",
            bool(api_base_info.get("is_localhost")),
            evidence=f"api_base={api_base_info.get('api_base') or 'missing'}",
            production_blocker=not bool(api_base_info.get("is_localhost")),
        ),
        _production_runtime_row(
            "config_path_policy_declared",
            "passed",
            True,
            evidence=f"config_dir={config_dir}; frontend receives no token/key config values",
        ),
        _production_runtime_row(
            "log_path_policy_declared",
            "passed",
            True,
            evidence=f"log_dir={log_dir}; preflight declares path only and writes no files",
        ),
        _production_runtime_row(
            "frontend_secret_boundary",
            "passed",
            True,
            evidence="Tauri frontend connects to local FastAPI only; secrets remain backend/env scoped",
        ),
        _production_runtime_row(
            "sidecar_autostart_validation_pending",
            "pending",
            False,
            evidence=f"backend_sidecar_configured={bool(tauri_config.get('backend_sidecar_configured'))}; manual launch is current policy",
            production_blocker=True,
        ),
        _production_runtime_row(
            "packaged_backend_offline_ux_pending",
            "pending",
            False,
            evidence="React error states exist, but offline UX has not been validated in packaged Tauri runtime",
            production_blocker=True,
        ),
    ]
    blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    return {
        "schema_version": "tauri_production_runtime_contract.v1",
        "status": "runtime_contract_ready_packaged_validation_pending" if not any(row.get("status") == "blocked" for row in rows) else "runtime_contract_blocked",
        "scope": "path_policy_and_startup_contract_not_packaged_runtime_validation",
        "backend_startup_strategy": "manual_fastapi_process_current_sidecar_pending",
        "manual_backend_launch_required": True,
        "backend_sidecar_autostart_enabled": False,
        "backend_sidecar_configured": bool(tauri_config.get("backend_sidecar_configured")),
        "api_base": api_base_info.get("api_base"),
        "api_base_is_localhost": bool(api_base_info.get("is_localhost")),
        "config_dir_policy": config_dir,
        "config_file_policy": f"{config_dir}/desktop.local.json",
        "log_dir_policy": log_dir,
        "log_file_policy": f"{log_dir}/command_center_3.log",
        "config_paths_declared": True,
        "log_paths_declared": True,
        "reads_config_values": False,
        "writes_log_files": False,
        "frontend_stores_tokens": False,
        "token_key_frontend_exposure": False,
        "packaged_runtime_validated": False,
        "backend_offline_ui_packaged_runtime_verified": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "production_blocker_count": len(blockers),
        "blockers": blockers,
        "rows": rows,
        "note": "This contract declares production runtime paths and startup boundaries only; it does not run Tauri build, start FastAPI, read config values, write logs, or validate packaged runtime UX.",
    }


def _backend_offline_ux_row(
    criterion: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    production_blocker: bool = False,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "production_blocker": bool(production_blocker),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "loads_token_or_key": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _backend_offline_ux_contract(api_base_info: dict[str, Any]) -> dict[str, Any]:
    client_source = _read_source_safe(FRONTEND_API_CLIENT)
    banner_source = _read_source_safe(FRONTEND_PAGE_STATE_BANNER)
    notice_source = _read_source_safe(FRONTEND_BACKEND_OFFLINE_NOTICE)
    style_source = _read_source_safe(FRONTEND_STYLES)
    api_client_fallback_ready = all(
        marker in client_source
        for marker in (
            "BACKEND_OFFLINE_ERROR",
            "backend_offline_or_unreachable",
            "failedRequestEnvelope",
            "catch (error)",
            "frontend_fastapi_request",
            "external_calls_triggered: false",
            "does_not_execute_trades: true",
            "does_not_modify_strategy_action: true",
        )
    )
    api_base_display_sanitized = all(
        marker in client_source
        for marker in (
            "API_BASE_DISPLAY_URL",
            "safeApiBaseDisplay",
            'parsed.search = ""',
            'parsed.hash = ""',
            "parsed.username",
            "parsed.password",
        )
    ) and "API_BASE_DISPLAY_URL" in notice_source
    notice_component_ready = all(
        marker in notice_source
        for marker in (
            "BackendOfflineNotice",
            "data-backend-offline",
            "BACKEND_OFFLINE_ERROR",
            "不会调用 Tushare",
            "不会执行真实交易",
        )
    )
    banner_integration_ready = "BackendOfflineNotice" in banner_source and "<BackendOfflineNotice error={error}" in banner_source
    style_ready = ".backend-offline-notice" in style_source and "data-backend-offline" in notice_source
    frontend_contract_ready = all(
        (
            api_client_fallback_ready,
            api_base_display_sanitized,
            notice_component_ready,
            banner_integration_ready,
            style_ready,
        )
    )
    rows = [
        _backend_offline_ux_row(
            "api_client_fetch_error_fallback",
            "passed" if api_client_fallback_ready else "blocked",
            api_client_fallback_ready,
            evidence=f"{_path_label(FRONTEND_API_CLIENT)} catches fetch failures and returns a safe local envelope",
            production_blocker=not api_client_fallback_ready,
        ),
        _backend_offline_ux_row(
            "api_base_display_sanitized",
            "passed" if api_base_display_sanitized else "blocked",
            api_base_display_sanitized,
            evidence="offline notice uses a display-safe API base without query string, hash, username, or password",
            production_blocker=not api_base_display_sanitized,
        ),
        _backend_offline_ux_row(
            "offline_notice_component",
            "passed" if notice_component_ready else "blocked",
            notice_component_ready,
            evidence=f"{_path_label(FRONTEND_BACKEND_OFFLINE_NOTICE)} displays offline state and safety boundaries",
            production_blocker=not notice_component_ready,
        ),
        _backend_offline_ux_row(
            "page_state_banner_integration",
            "passed" if banner_integration_ready else "blocked",
            banner_integration_ready,
            evidence=f"{_path_label(FRONTEND_PAGE_STATE_BANNER)} renders BackendOfflineNotice for backend offline errors",
            production_blocker=not banner_integration_ready,
        ),
        _backend_offline_ux_row(
            "offline_notice_style",
            "passed" if style_ready else "blocked",
            style_ready,
            evidence=f"{_path_label(FRONTEND_STYLES)} includes backend offline notice styling",
            production_blocker=not style_ready,
        ),
        _backend_offline_ux_row(
            "packaged_runtime_offline_qa_pending",
            "pending",
            False,
            evidence="source contract is static-audited only; offline UI has not been opened and validated inside packaged Tauri runtime",
            production_blocker=True,
        ),
    ]
    blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    return {
        "schema_version": "tauri_backend_offline_ux_contract.v1",
        "status": "frontend_offline_notice_ready_packaged_runtime_validation_pending" if frontend_contract_ready else "frontend_offline_notice_contract_incomplete",
        "scope": "static_frontend_source_contract_not_packaged_runtime_qa",
        "api_base": api_base_info.get("api_base"),
        "api_base_is_localhost": bool(api_base_info.get("is_localhost")),
        "backend_offline_error_code": "backend_offline_or_unreachable",
        "frontend_contract_ready": frontend_contract_ready,
        "api_client_fetch_error_fallback_ready": api_client_fallback_ready,
        "api_base_display_sanitized": api_base_display_sanitized,
        "offline_notice_component_ready": notice_component_ready,
        "page_state_banner_integration_ready": banner_integration_ready,
        "offline_notice_style_ready": style_ready,
        "frontend_notice_component": _path_label(FRONTEND_BACKEND_OFFLINE_NOTICE),
        "api_client_path": _path_label(FRONTEND_API_CLIENT),
        "page_state_banner_path": _path_label(FRONTEND_PAGE_STATE_BANNER),
        "packaged_runtime_validated": False,
        "backend_offline_ui_packaged_runtime_verified": False,
        "contains_secret": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "production_blocker_count": len(blockers),
        "blockers": blockers,
        "rows": rows,
        "note": "This contract statically verifies the frontend offline UX source path only; it does not start FastAPI, run Tauri, call providers/models/GitHub, execute trades, or validate packaged runtime UX.",
    }


def _production_package_blocker_audit(
    *,
    package_summary: dict[str, Any],
    tauri_config: dict[str, Any],
    production_readiness: dict[str, Any],
    node_ready: bool,
    rust_ready: bool,
    scaffold_ready: bool,
    api_base_info: dict[str, Any],
    runtime_contract: dict[str, Any],
    tauri_build_artifact: dict[str, Any],
    backend_offline_ux_contract: dict[str, Any],
) -> dict[str, Any]:
    frontend_dist = str(tauri_config.get("frontend_dist") or "")
    config_log_paths_declared = bool(runtime_contract.get("config_paths_declared") and runtime_contract.get("log_paths_declared"))
    tauri_build_verified = bool(tauri_build_artifact.get("binary_exists"))
    backend_offline_frontend_ready = bool(backend_offline_ux_contract.get("frontend_contract_ready"))
    rows = [
        {
            "criterion": "react_vite_scaffold_ready",
            "status": "passed" if scaffold_ready and node_ready else "blocked",
            "passed": scaffold_ready and node_ready,
            "evidence": f"build_script={bool(package_summary.get('has_build_script'))}; node_ready={node_ready}",
            "production_blocker": not (scaffold_ready and node_ready),
        },
        {
            "criterion": "tauri_cli_declared",
            "status": "passed" if package_summary.get("has_tauri_cli") else "blocked",
            "passed": bool(package_summary.get("has_tauri_cli")),
            "evidence": "@tauri-apps/cli in devDependencies",
            "production_blocker": not bool(package_summary.get("has_tauri_cli")),
        },
        {
            "criterion": "rust_cargo_toolchain_visible",
            "status": "passed" if rust_ready else "blocked",
            "passed": rust_ready,
            "evidence": "rustc and cargo are checked by path availability only",
            "production_blocker": not rust_ready,
        },
        {
            "criterion": "tauri_config_frontend_dist",
            "status": "passed" if frontend_dist == "../dist" else "blocked",
            "passed": frontend_dist == "../dist",
            "evidence": f"frontendDist={frontend_dist or 'missing'}",
            "production_blocker": frontend_dist != "../dist",
        },
        {
            "criterion": "tauri_config_local_dev_url",
            "status": "passed" if tauri_config.get("dev_url_is_localhost") else "blocked",
            "passed": bool(tauri_config.get("dev_url_is_localhost")),
            "evidence": f"devUrl={tauri_config.get('dev_url') or 'missing'}",
            "production_blocker": not bool(tauri_config.get("dev_url_is_localhost")),
        },
        {
            "criterion": "tauri_package_build_verified",
            "status": "passed" if tauri_build_verified else "blocked",
            "passed": tauri_build_verified,
            "evidence": f"release_binary={tauri_build_artifact.get('binary_path')}; binary_exists={tauri_build_verified}; GET preflight did not execute build",
            "production_blocker": not tauri_build_verified,
        },
        {
            "criterion": "backend_startup_strategy",
            "status": "blocked",
            "passed": False,
            "evidence": f"runtime_contract={runtime_contract.get('backend_startup_strategy')}; packaged strategy not validated",
            "production_blocker": True,
        },
        {
            "criterion": "backend_offline_ui_runtime_verified",
            "status": "blocked",
            "passed": False,
            "evidence": f"frontend_contract_ready={backend_offline_frontend_ready}; packaged_runtime_verified=false",
            "production_blocker": True,
        },
        {
            "criterion": "config_and_log_paths_declared",
            "status": "passed" if config_log_paths_declared else "blocked",
            "passed": config_log_paths_declared,
            "evidence": f"config={runtime_contract.get('config_file_policy')}; log={runtime_contract.get('log_file_policy')}",
            "production_blocker": not config_log_paths_declared,
        },
        {
            "criterion": "macos_signing_notarization_ready",
            "status": "blocked",
            "passed": False,
            "evidence": "signing, notarization, and distribution checks are not part of current preflight",
            "production_blocker": True,
        },
        {
            "criterion": "frontend_secret_boundary",
            "status": "passed",
            "passed": True,
            "evidence": "frontend connects to local FastAPI and preflight reports contains_secret=false",
            "production_blocker": False,
        },
        {
            "criterion": "startup_external_call_boundary",
            "status": "passed",
            "passed": True,
            "evidence": "desktop cache does not start providers, models, GitHub probes, or trades",
            "production_blocker": False,
        },
        {
            "criterion": "api_base_localhost",
            "status": "passed" if api_base_info.get("is_localhost") else "blocked",
            "passed": bool(api_base_info.get("is_localhost")),
            "evidence": f"api_base={api_base_info.get('api_base') or 'missing'}",
            "production_blocker": not bool(api_base_info.get("is_localhost")),
        },
    ]
    blockers = [row["criterion"] for row in rows if row.get("production_blocker")]
    package_ready = not blockers
    return {
        "schema_version": "tauri_production_package_blocker_audit.v1",
        "status": "production_package_ready" if package_ready else "production_package_blocked",
        "scope": "local_preflight_optional_build_artifact_detection_not_packaged_runtime_qa",
        "package_ready": package_ready,
        "tauri_dev_ready": bool(production_readiness.get("tauri_dev_ready")),
        "tauri_build_verified": tauri_build_verified,
        "tauri_build_artifact_status": tauri_build_artifact.get("status"),
        "tauri_build_artifact_path": tauri_build_artifact.get("binary_path"),
        "tauri_build_artifact_size_bytes": tauri_build_artifact.get("binary_size_bytes"),
        "tauri_package_build_attempted": False,
        "backend_sidecar_autostart_enabled": False,
        "manual_backend_launch_required": True,
        "backend_offline_ui_packaged_runtime_verified": False,
        "backend_offline_ux_contract_status": backend_offline_ux_contract.get("status"),
        "backend_offline_ux_frontend_contract_ready": backend_offline_frontend_ready,
        "config_log_paths_declared": config_log_paths_declared,
        "production_runtime_contract_status": runtime_contract.get("status"),
        "macos_signing_notarization_ready": False,
        "frontend_stores_tokens": False,
        "contains_secret": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "rows": rows,
        "note": "This audit separates desktop dev/preflight readiness and optional local build artifact detection from production packaged runtime QA; GET cache never runs npm, cargo, Tauri, providers, models, GitHub, or trades.",
    }


def _packaged_runtime_qa_row(
    criterion: str,
    status: str,
    passed: bool,
    *,
    evidence: str,
    qa_required: bool = True,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "status": status,
        "passed": bool(passed),
        "qa_required": bool(qa_required),
        "evidence": evidence,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _packaged_runtime_qa_contract(
    *,
    production_runtime_contract: dict[str, Any],
    tauri_build_artifact: dict[str, Any],
    backend_offline_ux_contract: dict[str, Any],
    production_blocker_audit: dict[str, Any],
) -> dict[str, Any]:
    release_binary_qa_passed = (
        tauri_build_artifact.get("binary_exists") is True
        and int(tauri_build_artifact.get("binary_size_bytes") or 0) > 0
        and tauri_build_artifact.get("binary_executable") is True
        and tauri_build_artifact.get("build_command_executed_by_get_cache") is False
    )
    qa_rows = [
        _packaged_runtime_qa_row(
            "release_artifact_qa",
            "passed_local_binary_artifact" if release_binary_qa_passed else "pending",
            release_binary_qa_passed,
            evidence=(
                f"artifact_status={tauri_build_artifact.get('status')}; "
                f"binary_path={tauri_build_artifact.get('binary_path')}; "
                f"binary_size_bytes={tauri_build_artifact.get('binary_size_bytes')}; "
                f"binary_executable={tauri_build_artifact.get('binary_executable')}; "
                f"bundle_app_count={tauri_build_artifact.get('bundle_app_count')}; "
                "artifact detection is not packaged app launch QA"
            ),
            qa_required=False,
        ),
        _packaged_runtime_qa_row(
            "backend_startup_strategy_qa",
            "pending",
            False,
            evidence=f"strategy={production_runtime_contract.get('backend_startup_strategy')}; sidecar/manual strategy not validated in packaged app",
        ),
        _packaged_runtime_qa_row(
            "backend_offline_ux_packaged_qa",
            "pending",
            False,
            evidence=f"frontend_contract_ready={backend_offline_ux_contract.get('frontend_contract_ready')}; packaged runtime offline notice not opened yet",
        ),
        _packaged_runtime_qa_row(
            "config_log_runtime_path_qa",
            "pending",
            False,
            evidence=f"config={production_runtime_contract.get('config_file_policy')}; log={production_runtime_contract.get('log_file_policy')}; path behavior not validated at runtime",
        ),
        _packaged_runtime_qa_row(
            "macos_signing_notarization_qa",
            "pending",
            False,
            evidence="signing, notarization, and distribution artifact checks remain outside current preflight",
        ),
        _packaged_runtime_qa_row(
            "startup_external_call_boundary",
            "passed",
            True,
            evidence="packaged runtime QA must not start Tushare, DeepSeek, GitHub probes, or trade paths during app startup",
            qa_required=False,
        ),
        _packaged_runtime_qa_row(
            "secret_bundle_boundary",
            "passed",
            True,
            evidence="frontend package must not contain token/key; backend/env remains the only secret boundary",
            qa_required=False,
        ),
    ]
    pending = [row["criterion"] for row in qa_rows if row.get("status") == "pending"]
    return {
        "schema_version": "tauri_packaged_runtime_qa_contract.v1",
        "status": "packaged_runtime_qa_contract_ready_validation_pending",
        "scope": "local_static_qa_matrix_not_packaged_runtime_execution",
        "production_package_ready": False,
        "packaged_runtime_validated": False,
        "qa_contract_ready": True,
        "qa_matrix_count": len(qa_rows),
        "pending_qa_count": len(pending),
        "pending_qa": pending,
        "release_artifact_status": tauri_build_artifact.get("status"),
        "release_artifact_path": tauri_build_artifact.get("binary_path"),
        "release_binary_qa_passed": release_binary_qa_passed,
        "release_binary_executable": tauri_build_artifact.get("binary_executable") is True,
        "packaged_app_bundle_detected": tauri_build_artifact.get("packaged_app_bundle_detected") is True,
        "distribution_dmg_detected": tauri_build_artifact.get("distribution_dmg_detected") is True,
        "production_blocker_status": production_blocker_audit.get("status"),
        "backend_offline_ux_contract_status": backend_offline_ux_contract.get("status"),
        "production_runtime_contract_status": production_runtime_contract.get("status"),
        "browser_or_packaged_app_opened": False,
        "npm_or_cargo_executed": False,
        "config_values_read": False,
        "log_files_written": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": qa_rows,
        "note": "This QA contract pins the packaged-runtime acceptance matrix only; it does not run npm, cargo, Tauri, packaged app, FastAPI, providers, models, GitHub, or trades.",
    }


def _tauri_production_readiness_receipt(
    *,
    production_readiness: dict[str, Any],
    production_runtime_contract: dict[str, Any],
    tauri_build_artifact: dict[str, Any],
    backend_offline_ux_contract: dict[str, Any],
    production_blocker_audit: dict[str, Any],
    packaged_runtime_qa_contract: dict[str, Any],
) -> dict[str, Any]:
    blocker_count = int(production_blocker_audit.get("blocker_count") or 0)
    pending_qa_count = int(packaged_runtime_qa_contract.get("pending_qa_count") or 0)
    artifact_detected = bool(tauri_build_artifact.get("binary_exists"))
    local_receipt_ready = (
        production_readiness.get("scope") == "tauri_desktop_production_preflight"
        and production_runtime_contract.get("schema_version") == "tauri_production_runtime_contract.v1"
        and tauri_build_artifact.get("schema_version") == "tauri_build_artifact_detection.v1"
        and backend_offline_ux_contract.get("schema_version") == "tauri_backend_offline_ux_contract.v1"
        and production_blocker_audit.get("schema_version") == "tauri_production_package_blocker_audit.v1"
        and packaged_runtime_qa_contract.get("schema_version") == "tauri_packaged_runtime_qa_contract.v1"
        and production_runtime_contract.get("reads_config_values") is False
        and production_runtime_contract.get("writes_log_files") is False
        and tauri_build_artifact.get("build_command_executed_by_get_cache") is False
        and packaged_runtime_qa_contract.get("npm_or_cargo_executed") is False
    )
    ready_for_explicit_tauri_build = bool(local_receipt_ready)
    ready_for_packaged_runtime_qa = bool(local_receipt_ready and artifact_detected)
    ready_for_production_package_promotion = bool(
        local_receipt_ready and production_blocker_audit.get("package_ready") is True and pending_qa_count == 0
    )

    def _row(criterion: str, status: str, detail: str, required_evidence: str) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": status == "passed",
            "production_blocker": status != "passed",
            "detail": detail,
            "required_evidence": required_evidence,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [
        _row(
            "local_tauri_contracts_visible",
            "passed" if local_receipt_ready else "blocked",
            "Desktop preflight exposes production readiness, runtime contract, artifact detection, offline UX contract, blocker audit, and packaged QA matrix.",
            "All local desktop contracts remain visible in GET /api/desktop/preflight-cache.",
        ),
        _row(
            "explicit_build_task_boundary",
            "passed" if local_receipt_ready else "blocked",
            "The next build step is manual/explicit; GET cache never runs npm, cargo, Tauri, or FastAPI.",
            "Operator explicitly runs npm build / tauri build outside cache GET.",
        ),
        _row(
            "artifact_detection_not_runtime_qa",
            "blocked" if not artifact_detected else "passed",
            f"release_artifact_status={tauri_build_artifact.get('status')}; artifact detection does not validate launch/runtime behavior.",
            "A release artifact exists and is followed by packaged runtime QA.",
        ),
        _row(
            "packaged_runtime_qa_pending",
            "blocked" if pending_qa_count > 0 else "passed",
            f"{pending_qa_count} packaged runtime QA item(s) remain pending.",
            "Packaged app launch QA covers backend startup strategy, offline UX, config/log paths, signing/notarization, startup external-call boundary, and secret boundary.",
        ),
        _row(
            "backend_startup_strategy_pending",
            "blocked" if production_runtime_contract.get("manual_backend_launch_required") is True else "passed",
            f"backend_startup_strategy={production_runtime_contract.get('backend_startup_strategy')}; sidecar autostart enabled={production_runtime_contract.get('backend_sidecar_autostart_enabled')}.",
            "Production package acceptance chooses and validates manual FastAPI or sidecar startup strategy.",
        ),
        _row(
            "backend_offline_packaged_ux_pending",
            "blocked" if backend_offline_ux_contract.get("backend_offline_ui_packaged_runtime_verified") is False else "passed",
            f"frontend_contract_ready={backend_offline_ux_contract.get('frontend_contract_ready')}; packaged_runtime_verified={backend_offline_ux_contract.get('backend_offline_ui_packaged_runtime_verified')}.",
            "Open packaged runtime with backend offline and verify friendly local-only UX.",
        ),
        _row(
            "config_log_runtime_validation_pending",
            "blocked",
            "Config/log paths are declared, but packaged runtime path behavior has not been validated.",
            "Packaged runtime validates config/log paths without exposing token/key values or writing unsafe logs.",
        ),
        _row(
            "signing_notarization_pending",
            "blocked" if production_blocker_audit.get("macos_signing_notarization_ready") is False else "passed",
            "macOS signing/notarization is not complete in current preflight.",
            "Signing, notarization, and distribution artifact checks are completed or explicitly waived.",
        ),
        _row(
            "startup_external_call_boundary",
            "passed",
            "Receipt does not start providers, models, GitHub probes, FastAPI, Tauri, or trading paths.",
            "Startup QA preserves no Tushare/DeepSeek/GitHub/trade calls.",
        ),
        _row(
            "secret_bundle_boundary",
            "passed",
            "Frontend package must not contain token/key material; backend/env remains the secret boundary.",
            "Packaged artifact review confirms token/key are absent from frontend, logs, packet, and cache.",
        ),
        _row(
            "production_completion_evidence_ticket",
            "blocked",
            "This receipt is next-step evidence only; production_package_complete remains false.",
            "A future production package ticket proves build, packaged runtime QA, backend startup strategy, config/log behavior, signing/notarization, and safety boundaries.",
        ),
    ]
    blocked_rows = [row for row in rows if row["status"] != "passed"]
    status = (
        "tauri_package_readiness_receipt_ready_for_promotion_review"
        if ready_for_production_package_promotion
        else "tauri_package_readiness_receipt_ready_packaged_qa_pending"
        if ready_for_packaged_runtime_qa
        else "tauri_package_readiness_receipt_ready_build_pending"
        if ready_for_explicit_tauri_build
        else "tauri_package_readiness_receipt_blocked_local_contract"
    )
    return {
        "schema_version": "tauri_production_package_readiness_receipt.v1",
        "status": status,
        "scope": "local_tauri_production_package_readiness_receipt_no_build_or_runtime_execution",
        "ltg": "LTG-09",
        "local_receipt_ready": bool(local_receipt_ready),
        "ready_for_explicit_tauri_build": ready_for_explicit_tauri_build,
        "ready_for_packaged_runtime_qa": ready_for_packaged_runtime_qa,
        "ready_for_production_package_promotion": ready_for_production_package_promotion,
        "allowed_next_step": "explicit_tauri_build_then_packaged_runtime_qa_review",
        "not_allowed_next_steps": [
            "GET /api/desktop/preflight-cache npm build",
            "GET /api/desktop/preflight-cache cargo build",
            "GET /api/desktop/preflight-cache tauri build",
            "GET /api/desktop/preflight-cache packaged app launch",
            "GET /api/desktop/preflight-cache FastAPI autostart",
            "release artifact detection as packaged runtime QA",
            "preflight receipt as production package completion",
        ],
        "missing_evidence_items": [
            "repeatable_tauri_build_log",
            "packaged_app_launch_qa",
            "backend_startup_strategy_acceptance",
            "backend_offline_packaged_ux_evidence",
            "config_log_runtime_path_evidence",
            "macos_signing_notarization_evidence",
            "frontend_secret_bundle_review",
        ],
        "production_blocker_count": blocker_count,
        "packaged_runtime_pending_qa_count": pending_qa_count,
        "tauri_build_artifact_detected": artifact_detected,
        "production_package_complete": False,
        "tauri_build_executed_by_receipt": False,
        "npm_or_cargo_executed_by_receipt": False,
        "tauri_runtime_started_by_receipt": False,
        "packaged_app_opened_by_receipt": False,
        "fastapi_started_by_receipt": False,
        "config_values_read_by_receipt": False,
        "log_files_written_by_receipt": False,
        "provider_model_task_dispatched_by_receipt": False,
        "receipt_external_calls_triggered": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "criterion_count": len(rows),
        "blocking_criterion_count": len(blocked_rows),
        "rows": rows,
        "call_ledger": [
            {
                "api": "local_tauri_production_package_readiness_receipt",
                "source": "desktop preflight local contracts",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_readiness_receipt",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This receipt selects the next safe LTG-09 step only. It does not run npm, cargo, Tauri, packaged app, FastAPI, providers, models, GitHub probes, config reads, log writes, trades, or production package promotion.",
    }


def _tauri_package_durable_evidence_recipe_row(
    evidence_key: str,
    category: str,
    status: str,
    *,
    passed: bool,
    local_surface_required: bool,
    production_blocker: bool,
    evidence: str,
    next_action: str,
    recommended_order: int,
) -> dict[str, Any]:
    return {
        "schema_version": TAURI_PACKAGE_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "evidence_key": evidence_key,
        "evidence_label": TAURI_PACKAGE_DURABLE_EVIDENCE_LABELS[evidence_key],
        "category": category,
        "status": status,
        "passed": bool(passed),
        "local_surface_required": bool(local_surface_required),
        "production_blocker": bool(production_blocker),
        "recommended_order": recommended_order,
        "evidence": evidence,
        "next_action": next_action,
        "recipe_only": True,
        "cache_only": True,
        "does_not_run_npm": True,
        "does_not_run_cargo": True,
        "does_not_run_tauri": True,
        "does_not_open_packaged_app": True,
        "does_not_start_fastapi": True,
        "does_not_read_config_values": True,
        "does_not_write_log_files": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


def _tauri_package_durable_evidence_recipe(packet: dict[str, Any]) -> dict[str, Any]:
    policy = packet.get("policy") if isinstance(packet.get("policy"), dict) else {}
    runtime = packet.get("runtime") if isinstance(packet.get("runtime"), dict) else {}
    build_artifact = packet.get("tauri_build_artifact") if isinstance(packet.get("tauri_build_artifact"), dict) else {}
    release_manifest = (
        packet.get("tauri_release_manifest_contract")
        if isinstance(packet.get("tauri_release_manifest_contract"), dict)
        else {}
    )
    readiness_receipt = (
        packet.get("production_package_readiness_receipt")
        if isinstance(packet.get("production_package_readiness_receipt"), dict)
        else {}
    )
    packaged_qa = (
        packet.get("packaged_runtime_qa_contract")
        if isinstance(packet.get("packaged_runtime_qa_contract"), dict)
        else {}
    )
    blocker_audit = (
        packet.get("production_blocker_audit")
        if isinstance(packet.get("production_blocker_audit"), dict)
        else {}
    )
    offline_ux = (
        packet.get("backend_offline_ux_contract")
        if isinstance(packet.get("backend_offline_ux_contract"), dict)
        else {}
    )
    runtime_contract = (
        packet.get("production_runtime_contract")
        if isinstance(packet.get("production_runtime_contract"), dict)
        else {}
    )

    preflight_boundary_visible = (
        packet.get("cache_only") is True
        and packet.get("read_only") is True
        and policy.get("does_not_run_npm_build") is True
        and policy.get("does_not_run_tauri") is True
        and policy.get("does_not_run_cargo") is True
        and policy.get("does_not_start_fastapi") is True
        and policy.get("does_not_read_config_values") is True
        and policy.get("does_not_write_log_files") is True
        and packet.get("external_calls_triggered") is False
    )
    release_manifest_visible = (
        release_manifest.get("schema_version") == "tauri_release_manifest_contract.v1"
        and release_manifest.get("local_release_manifest_ready") is True
    )
    readiness_receipt_visible = (
        readiness_receipt.get("schema_version") == "tauri_production_package_readiness_receipt.v1"
        and readiness_receipt.get("local_receipt_ready") is True
    )
    packaged_runtime_qa_visible = (
        packaged_qa.get("schema_version") == "tauri_packaged_runtime_qa_contract.v1"
        and packaged_qa.get("qa_contract_ready") is True
    )
    release_artifact_shape_visible = (
        build_artifact.get("schema_version") == "tauri_build_artifact_detection.v1"
        and build_artifact.get("detected_by_get_cache") is True
        and build_artifact.get("build_command_executed_by_get_cache") is False
    )
    no_build_runtime_provider_trade_secret_boundary = (
        packet.get("external_calls_triggered") is False
        and packet.get("tushare_called") is False
        and packet.get("deepseek_called") is False
        and packet.get("github_called") is False
        and packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("contains_secret") is False
        and policy.get("does_not_run_npm_build") is True
        and policy.get("does_not_run_tauri") is True
        and policy.get("does_not_run_cargo") is True
        and policy.get("does_not_read_config_values") is True
        and policy.get("does_not_write_log_files") is True
    )
    app_bundle_dmg_done = bool(
        build_artifact.get("packaged_app_bundle_detected") is True
        and build_artifact.get("distribution_dmg_detected") is True
    )
    packaged_app_launch_qa_done = packaged_qa.get("packaged_runtime_validated") is True
    backend_startup_runtime_done = blocker_audit.get("package_ready") is True and runtime.get("backend_autostart_configured") is True
    offline_packaged_ux_done = offline_ux.get("backend_offline_ui_packaged_runtime_verified") is True
    config_log_runtime_done = False
    signing_notarization_done = blocker_audit.get("macos_signing_notarization_ready") is True
    production_package_complete = blocker_audit.get("package_ready") is True

    rows = [
        _tauri_package_durable_evidence_recipe_row(
            "preflight_cache_boundary_visible",
            "local_surface",
            "passed_preflight_boundary" if preflight_boundary_visible else "blocked_preflight_boundary",
            passed=preflight_boundary_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"cache_only={packet.get('cache_only')}; does_not_run_tauri={policy.get('does_not_run_tauri')}",
            next_action="Keep GET desktop preflight read-only and build/runtime silent.",
            recommended_order=1,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "release_manifest_visible",
            "local_surface",
            "passed_release_manifest" if release_manifest_visible else "blocked_release_manifest",
            passed=release_manifest_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"status={release_manifest.get('status')}; local_ready={release_manifest.get('local_release_manifest_ready')}",
            next_action="Keep app identity, dist, ignore policy, backend startup, config/log path, and signing gaps visible.",
            recommended_order=2,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "readiness_receipt_visible",
            "local_surface",
            "passed_readiness_receipt" if readiness_receipt_visible else "blocked_readiness_receipt",
            passed=readiness_receipt_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"status={readiness_receipt.get('status')}; blockers={readiness_receipt.get('blocking_criterion_count')}",
            next_action="Use readiness receipt as next-step routing only, not as package completion.",
            recommended_order=3,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "packaged_runtime_qa_matrix_visible",
            "local_surface",
            "passed_packaged_qa_matrix" if packaged_runtime_qa_visible else "blocked_packaged_qa_matrix",
            passed=packaged_runtime_qa_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=f"status={packaged_qa.get('status')}; pending={packaged_qa.get('pending_qa_count')}",
            next_action="Keep packaged runtime QA explicit and outside GET preflight.",
            recommended_order=4,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "release_artifact_shape_visible",
            "local_surface",
            "passed_artifact_shape" if release_artifact_shape_visible else "blocked_artifact_shape",
            passed=release_artifact_shape_visible,
            local_surface_required=True,
            production_blocker=False,
            evidence=(
                f"status={build_artifact.get('status')}; binary_exists={build_artifact.get('binary_exists')}; "
                f"bundle_app_count={build_artifact.get('bundle_app_count')}; dmg_count={build_artifact.get('bundle_dmg_count')}"
            ),
            next_action="Treat local artifact detection as shape evidence only; packaged launch QA remains required.",
            recommended_order=5,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "app_bundle_dmg_evidence_required",
            "durable_evidence",
            "completed" if app_bundle_dmg_done else "pending_app_bundle_dmg_evidence",
            passed=app_bundle_dmg_done,
            local_surface_required=False,
            production_blocker=not app_bundle_dmg_done,
            evidence=f"app_bundle={build_artifact.get('packaged_app_bundle_detected')}; dmg={build_artifact.get('distribution_dmg_detected')}",
            next_action="Attach .app and DMG artifact QA or an explicit accepted equivalent before production package promotion.",
            recommended_order=6,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "packaged_app_launch_qa_required",
            "durable_evidence",
            "completed" if packaged_app_launch_qa_done else "pending_packaged_app_launch_qa",
            passed=packaged_app_launch_qa_done,
            local_surface_required=False,
            production_blocker=not packaged_app_launch_qa_done,
            evidence=f"packaged_runtime_validated={packaged_qa.get('packaged_runtime_validated')}",
            next_action="Open the packaged app in an explicit QA run and record launch/runtime evidence.",
            recommended_order=7,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "backend_startup_runtime_evidence_required",
            "durable_evidence",
            "completed" if backend_startup_runtime_done else "pending_backend_startup_runtime_evidence",
            passed=backend_startup_runtime_done,
            local_surface_required=False,
            production_blocker=not backend_startup_runtime_done,
            evidence=f"strategy={runtime_contract.get('backend_startup_strategy')}; package_ready={blocker_audit.get('package_ready')}",
            next_action="Validate the chosen manual/sidecar backend startup behavior in packaged runtime.",
            recommended_order=8,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "backend_offline_packaged_ux_required",
            "durable_evidence",
            "completed" if offline_packaged_ux_done else "pending_backend_offline_packaged_ux",
            passed=offline_packaged_ux_done,
            local_surface_required=False,
            production_blocker=not offline_packaged_ux_done,
            evidence=f"frontend_contract_ready={offline_ux.get('frontend_contract_ready')}; packaged_verified={offline_packaged_ux_done}",
            next_action="Open packaged runtime with backend offline and capture the friendly local-only UX evidence.",
            recommended_order=9,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "config_log_runtime_path_evidence_required",
            "durable_evidence",
            "completed" if config_log_runtime_done else "pending_config_log_runtime_path_evidence",
            passed=config_log_runtime_done,
            local_surface_required=False,
            production_blocker=True,
            evidence=(
                f"config={runtime_contract.get('config_file_policy')}; log={runtime_contract.get('log_file_policy')}; "
                "runtime_path_validation=false"
            ),
            next_action="Validate runtime path behavior without reading config values or writing unsafe logs.",
            recommended_order=10,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "signing_notarization_review_required",
            "durable_evidence",
            "completed" if signing_notarization_done else "pending_signing_notarization_review",
            passed=signing_notarization_done,
            local_surface_required=False,
            production_blocker=not signing_notarization_done,
            evidence=f"macos_signing_notarization_ready={signing_notarization_done}",
            next_action="Complete or explicitly waive macOS signing/notarization and distribution review.",
            recommended_order=11,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "production_package_promotion_review_required",
            "durable_evidence",
            "completed" if production_package_complete else "pending_production_package_promotion_review",
            passed=production_package_complete,
            local_surface_required=False,
            production_blocker=not production_package_complete,
            evidence=f"production_package_complete={production_package_complete}; package_ready={blocker_audit.get('package_ready')}",
            next_action="Promote only after artifact, runtime, backend, config/log, signing, secret, provider, and trade boundaries are reviewed.",
            recommended_order=12,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "no_build_runtime_provider_trade_secret_boundary",
            "safety",
            "passed_no_build_runtime_provider_trade_secret"
            if no_build_runtime_provider_trade_secret_boundary
            else "blocked_safety_boundary",
            passed=no_build_runtime_provider_trade_secret_boundary,
            local_surface_required=True,
            production_blocker=not no_build_runtime_provider_trade_secret_boundary,
            evidence="Durable recipe runs no npm/cargo/Tauri, opens no packaged app, starts no FastAPI, reads no config values, writes no logs, calls no providers/models/GitHub, executes no trades, and exposes no secret.",
            next_action="Preserve no-build/no-runtime/no-provider/no-trade/no-secret boundaries while production evidence improves.",
            recommended_order=13,
        ),
    ]
    local_blockers = [row["evidence_key"] for row in rows if row["local_surface_required"] and not row["passed"]]
    durable_blockers = [row["evidence_key"] for row in rows if row["production_blocker"] and not row["passed"]]
    local_ready = not local_blockers
    contract = {
        "schema_version": TAURI_PACKAGE_DURABLE_EVIDENCE_SCHEMA_VERSION,
        "status": (
            "tauri_package_durable_evidence_recipe_ready_production_pending"
            if local_ready
            else "tauri_package_durable_evidence_recipe_blocked_local_surface"
        ),
        "scope": "local_tauri_package_durable_evidence_recipe_no_build_or_runtime_execution",
        "ltg": "LTG-09/LTG-14",
        "local_recipe_ready": local_ready,
        "durable_evidence_complete": False,
        "durable_promotion_ready": False,
        "production_package_complete": False,
        "tauri_build_repeatability_done": False,
        "app_bundle_dmg_qa_done": app_bundle_dmg_done,
        "packaged_app_launch_qa_done": packaged_app_launch_qa_done,
        "backend_startup_strategy_runtime_validated": backend_startup_runtime_done,
        "backend_offline_packaged_ux_verified": offline_packaged_ux_done,
        "config_log_runtime_paths_validated": False,
        "signing_notarization_done": signing_notarization_done,
        "provider_execution_implemented": False,
        "model_execution_implemented": False,
        "cache_get_external_calls": False,
        "react_render_external_calls": False,
        "preflight_runs_build": False,
        "preflight_opens_packaged_app": False,
        "preflight_starts_fastapi": False,
        "preflight_reads_config_values": False,
        "preflight_writes_log_files": False,
        "evidence_keys": list(TAURI_PACKAGE_DURABLE_EVIDENCE_KEYS),
        "missing_durable_evidence": durable_blockers,
        "required_evidence": [
            ".app bundle and DMG artifact QA or explicit accepted equivalent",
            "packaged app launch QA",
            "backend startup strategy runtime evidence",
            "packaged backend-offline UX evidence",
            "config/log runtime path evidence without secret values",
            "macOS signing/notarization review",
            "frontend bundle secret review",
            "production package promotion review",
        ],
        "not_allowed_next_steps": [
            "treat durable recipe as production desktop package",
            "treat release binary detection as packaged app launch QA",
            "treat readiness receipt as production package completion",
            "run npm, cargo, or Tauri from GET preflight",
            "open packaged app from GET preflight",
            "start FastAPI from GET preflight",
            "read config values or write log files from durable recipe",
            "call Tushare, DeepSeek, or GitHub from GET preflight or React render",
            "store raw token/key in frontend, packet, cache, ledger, or log",
        ],
        "allowed_next_step": "run_explicit_tauri_build_then_packaged_runtime_qa_then_durable_promotion_review",
        "row_count": len(rows),
        "evidence_key_count": len(TAURI_PACKAGE_DURABLE_EVIDENCE_KEYS),
        "local_blocker_count": len(local_blockers),
        "durable_evidence_blocker_count": len(durable_blockers),
        "production_blocker_count": len(durable_blockers),
        "local_blockers": local_blockers,
        "rows": rows,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "note": "This recipe fixes the durable evidence checklist for LTG-09. It does not run npm, cargo, Tauri, packaged app, FastAPI, providers, models, GitHub, config reads, log writes, trades, or production desktop package promotion.",
    }
    contract["call_ledger"] = [
        {
            "api": "local_tauri_package_durable_evidence_recipe",
            "source": "desktop preflight local contracts",
            "row_count": len(rows),
            "local_fetched_at": _now_iso(),
            "call_status": contract["status"],
            "external": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]
    return contract


def _tauri_package_artifact_review_call_ledger(review: dict[str, Any], reviewed_at: str) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_tauri_package_artifact_review",
            "request_params_safe": {
                "review_scope": "local_tauri_release_binary_artifact",
                "binary_path": review.get("release_binary_path"),
                "release_binary_review_ready": review.get("local_release_binary_artifact_review_ready"),
                "tauri_build_repeatability_done": review.get("tauri_build_repeatability_done"),
                "app_bundle_artifact_qa_done": review.get("app_bundle_artifact_qa_done"),
                "dmg_distribution_artifact_qa_done": review.get("dmg_distribution_artifact_qa_done"),
                "build_command_reviewed_safe": review.get("build_command_reviewed_safe"),
                "external_sources_allowed": False,
                "opens_packaged_app": False,
                "runs_build": False,
                "production_package_complete": False,
            },
            "row_count": review.get("row_count", 0),
            "data_date": reviewed_at,
            "local_fetched_at": reviewed_at,
            "call_status": review.get("status"),
            "error_message_safe": "",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def _tauri_package_artifact_review_contract(
    *,
    tauri_build_artifact: dict[str, Any],
    packaged_runtime_qa_contract: dict[str, Any],
    reviewed_at: str | None = None,
    task_id: str = "",
    explicit_review: bool = False,
    explicit_tauri_build_completed: bool = False,
    build_command_reviewed_safe: str = "",
) -> dict[str, Any]:
    release_binary_ready = bool(
        tauri_build_artifact.get("schema_version") == "tauri_build_artifact_detection.v1"
        and tauri_build_artifact.get("binary_exists") is True
        and int(tauri_build_artifact.get("binary_size_bytes") or 0) > 0
        and tauri_build_artifact.get("binary_executable") is True
        and tauri_build_artifact.get("binary_kind") == "macos_mach_o_release_binary"
        and tauri_build_artifact.get("build_command_executed_by_get_cache") is False
        and tauri_build_artifact.get("artifact_is_gitignored") is True
    )
    boundary_ready = bool(
        tauri_build_artifact.get("external_calls_triggered") is False
        and tauri_build_artifact.get("tushare_called") is False
        and tauri_build_artifact.get("deepseek_called") is False
        and tauri_build_artifact.get("github_called") is False
        and tauri_build_artifact.get("does_not_execute_trades") is True
        and tauri_build_artifact.get("does_not_modify_strategy_action") is True
        and tauri_build_artifact.get("contains_secret") is False
    )
    local_ready = bool(explicit_review and release_binary_ready and boundary_ready)
    accepted_build_command = build_command_reviewed_safe in {
        "npm run tauri build",
        "cd desktop && npm run tauri build",
    }
    build_repeatability_ready = bool(local_ready and explicit_tauri_build_completed and accepted_build_command)
    app_bundle_ready = bool(
        local_ready
        and tauri_build_artifact.get("packaged_app_bundle_detected") is True
        and int(tauri_build_artifact.get("bundle_app_count") or 0) > 0
        and tauri_build_artifact.get("bundle_app_path")
    )
    dmg_distribution_ready = bool(
        local_ready
        and tauri_build_artifact.get("distribution_dmg_detected") is True
        and int(tauri_build_artifact.get("bundle_dmg_count") or 0) > 0
        and tauri_build_artifact.get("bundle_dmg_path")
    )
    app_bundle_dmg_ready = bool(app_bundle_ready and dmg_distribution_ready)

    def _row(criterion: str, status: str, passed: bool, evidence: str, *, blocks_review: bool = True) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": bool(passed),
            "evidence": evidence,
            "blocks_review": bool(blocks_review and not passed),
            "blocks_production": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }

    rows = [
        _row(
            "explicit_post_artifact_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            explicit_review,
            "POST /api/desktop/tauri-package-artifact-review performs the local release-binary artifact review.",
        ),
        _row(
            "release_binary_exists_and_executable",
            "passed_local_binary_artifact" if release_binary_ready else "pending_release_binary_artifact",
            release_binary_ready,
            (
                f"path={tauri_build_artifact.get('binary_path')}; "
                f"exists={tauri_build_artifact.get('binary_exists')}; "
                f"size={tauri_build_artifact.get('binary_size_bytes')}; "
                f"executable={tauri_build_artifact.get('binary_executable')}; "
                f"kind={tauri_build_artifact.get('binary_kind')}"
            ),
        ),
        _row(
            "artifact_detection_did_not_run_build",
            "passed_no_build_from_review",
            tauri_build_artifact.get("build_command_executed_by_get_cache") is False,
            "Review reads an existing ignored artifact only; it does not run npm, cargo, or Tauri.",
        ),
        _row(
            "explicit_tauri_build_repeatability_review",
            "passed_explicit_build_review" if build_repeatability_ready else "pending_explicit_build_review",
            build_repeatability_ready,
            (
                f"explicit_tauri_build_completed={explicit_tauri_build_completed}; "
                f"build_command_reviewed={build_command_reviewed_safe or 'missing'}; "
                f"binary_modified_at={tauri_build_artifact.get('binary_modified_at')}; "
                "review records the result of a separately executed explicit local Tauri build."
            ),
            blocks_review=False,
        ),
        _row(
            "app_bundle_artifact_detected",
            "passed_local_app_bundle_artifact" if app_bundle_ready else "pending_app_bundle_artifact",
            app_bundle_ready,
            (
                f"app_bundle={tauri_build_artifact.get('packaged_app_bundle_detected')}; "
                f"app_count={tauri_build_artifact.get('bundle_app_count')}; "
                f"app_path={tauri_build_artifact.get('bundle_app_path') or 'missing'}; "
                "app bundle artifact is local package-shape evidence only, not launch/runtime QA."
            ),
            blocks_review=False,
        ),
        _row(
            "dmg_distribution_artifact_still_pending",
            "passed_local_dmg_artifact" if dmg_distribution_ready else "pending_dmg_distribution_artifact",
            dmg_distribution_ready,
            (
                f"dmg={tauri_build_artifact.get('distribution_dmg_detected')}; "
                f"dmg_count={tauri_build_artifact.get('bundle_dmg_count')}; "
                f"dmg_path={tauri_build_artifact.get('bundle_dmg_path') or 'missing'}; "
                f"temporary_dmg_count={tauri_build_artifact.get('temporary_dmg_count')}; "
                "temporary rw.*.dmg files are ignored as distribution evidence."
            ),
            blocks_review=False,
        ),
        _row(
            "packaged_launch_runtime_still_pending",
            "pending_packaged_launch_runtime_qa",
            False,
            (
                f"packaged_runtime_validated={packaged_runtime_qa_contract.get('packaged_runtime_validated')}; "
                "release binary artifact QA is not packaged app launch QA."
            ),
            blocks_review=False,
        ),
        _row(
            "production_package_still_blocked",
            "passed_production_blockers_visible",
            True,
            "Backend startup, offline UX, config/log runtime paths, signing/notarization, and promotion review remain required.",
            blocks_review=False,
        ),
        _row(
            "no_external_trade_secret_boundary",
            "passed_no_external_trade_secret",
            boundary_ready,
            "Review calls no providers/models/GitHub, executes no trades, mutates no strategy action, and exposes no secret.",
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_review"]]
    direct_evidence_stage_keys = ["release_binary_artifact_qa"] if local_ready else []
    if build_repeatability_ready:
        direct_evidence_stage_keys.append("tauri_build_repeatability")
    if app_bundle_ready:
        direct_evidence_stage_keys.append("app_bundle_artifact_qa")
    if dmg_distribution_ready:
        direct_evidence_stage_keys.append("dmg_distribution_artifact_qa")
    return {
        "schema_version": "tauri_package_artifact_review.v1",
        "status": "tauri_package_artifact_review_ready_local_binary"
        if local_ready
        else "tauri_package_artifact_review_pending",
        "scope": "button_gated_local_tauri_release_binary_artifact_review_no_build_no_runtime",
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "explicit_review_task_done": explicit_review,
        "local_release_binary_artifact_review_ready": local_ready,
        "direct_evidence_stage_key": "release_binary_artifact_qa" if local_ready else "",
        "direct_evidence_stage_keys": direct_evidence_stage_keys,
        "release_binary_path": tauri_build_artifact.get("binary_path"),
        "release_binary_exists": tauri_build_artifact.get("binary_exists") is True,
        "release_binary_size_bytes": tauri_build_artifact.get("binary_size_bytes"),
        "release_binary_modified_at": tauri_build_artifact.get("binary_modified_at"),
        "release_binary_executable": tauri_build_artifact.get("binary_executable") is True,
        "release_binary_kind": tauri_build_artifact.get("binary_kind"),
        "release_binary_is_completion": False,
        "bundle_app_count": tauri_build_artifact.get("bundle_app_count"),
        "bundle_dmg_count": tauri_build_artifact.get("bundle_dmg_count"),
        "app_bundle_path": tauri_build_artifact.get("bundle_app_path") or "",
        "dmg_distribution_path": tauri_build_artifact.get("bundle_dmg_path") or "",
        "temporary_dmg_count": tauri_build_artifact.get("temporary_dmg_count"),
        "temporary_dmg_ignored_for_distribution": tauri_build_artifact.get(
            "temporary_dmg_ignored_for_distribution"
        )
        is True,
        "explicit_tauri_build_completed_before_review": explicit_tauri_build_completed,
        "build_command_reviewed_safe": build_command_reviewed_safe if accepted_build_command else "",
        "tauri_build_repeatability_done": build_repeatability_ready,
        "tauri_build_repeatability_is_completion": False,
        "app_bundle_detected": tauri_build_artifact.get("packaged_app_bundle_detected") is True,
        "dmg_distribution_detected": tauri_build_artifact.get("distribution_dmg_detected") is True,
        "app_bundle_artifact_qa_done": app_bundle_ready,
        "app_bundle_is_completion": False,
        "dmg_distribution_artifact_qa_done": dmg_distribution_ready,
        "dmg_distribution_is_completion": False,
        "app_bundle_dmg_qa_done": app_bundle_dmg_ready,
        "packaged_runtime_validated": False,
        "packaged_app_launch_qa_done": False,
        "backend_startup_runtime_validated": False,
        "backend_offline_packaged_ux_verified": False,
        "config_log_runtime_paths_validated": False,
        "signing_notarization_done": False,
        "production_package_complete": False,
        "tauri_build_executed_by_review": False,
        "npm_or_cargo_executed_by_review": False,
        "tauri_runtime_started_by_review": False,
        "packaged_app_opened_by_review": False,
        "fastapi_started_by_review": False,
        "config_values_read_by_review": False,
        "log_files_written_by_review": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "row_count": len(rows),
        "blocking_review_count": len(blocking_rows),
        "rows": rows,
        "note": "This review is local release-binary artifact evidence only. It does not build, open the packaged app, start FastAPI, validate runtime UX, sign/notarize, call providers/models/GitHub, execute trades, or complete LTG-09.",
    }


def _safe_persisted_tauri_package_artifact_review(packet: dict[str, Any]) -> dict[str, Any]:
    review = packet.get("tauri_package_artifact_review_contract")
    if not isinstance(review, dict):
        return {}
    safe = (
        review.get("schema_version") == "tauri_package_artifact_review.v1"
        and review.get("scope") == "button_gated_local_tauri_release_binary_artifact_review_no_build_no_runtime"
        and review.get("explicit_review_task_done") is True
        and review.get("local_release_binary_artifact_review_ready") is True
        and review.get("release_binary_is_completion") is False
        and review.get("production_package_complete") is False
        and review.get("packaged_runtime_validated") is False
        and review.get("tauri_build_executed_by_review") is False
        and review.get("npm_or_cargo_executed_by_review") is False
        and review.get("tauri_runtime_started_by_review") is False
        and review.get("packaged_app_opened_by_review") is False
        and review.get("fastapi_started_by_review") is False
        and review.get("config_values_read_by_review") is False
        and review.get("log_files_written_by_review") is False
        and review.get("external_calls_triggered") is False
        and review.get("tushare_called") is False
        and review.get("deepseek_called") is False
        and review.get("github_called") is False
        and review.get("does_not_execute_trades") is True
        and review.get("does_not_modify_strategy_action") is True
        and review.get("contains_secret") is False
    )
    return review if safe else {}


def _read_tauri_package_artifact_review_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(TAURI_PACKAGE_ARTIFACT_REVIEW_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_tauri_package_artifact_review(packet) else {}


def _write_tauri_package_artifact_review_packet(
    *,
    review_contract: dict[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": TAURI_PACKAGE_ARTIFACT_REVIEW_PACKET_KEY,
        "schema_version": "tauri_package_artifact_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "tauri_package_artifact_review_contract": dict(review_contract),
        "tauri_package_artifact_review_rows": list(review_contract.get("rows") or []),
        "call_ledger": list(ledger),
        "cache_only": True,
        "runs_no_build": True,
        "opens_no_packaged_app": True,
        "starts_no_fastapi": True,
        "reads_no_config_values": True,
        "writes_no_log_files": True,
        "production_package_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "warnings": [
            "This packet is a local review receipt for an ignored Tauri release binary artifact only.",
            "It is not packaged app launch QA, signing/notarization evidence, or production package completion.",
        ],
    }
    if _safe_persisted_tauri_package_artifact_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(TAURI_PACKAGE_ARTIFACT_REVIEW_PACKET_KEY, packet)


def _tauri_packaged_runtime_launch_review_call_ledger(review: dict[str, Any], reviewed_at: str) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_tauri_packaged_runtime_launch_review",
            "request_params_safe": {
                "review_scope": "local_tauri_packaged_app_launch_smoke",
                "app_bundle_path": review.get("app_bundle_path"),
                "launch_command_reviewed_safe": review.get("launch_command_reviewed_safe"),
                "app_process_observed_after_launch": review.get("app_process_observed_after_launch"),
                "packaged_app_launch_smoke_done": review.get("packaged_app_launch_smoke_done"),
                "external_sources_allowed": False,
                "runs_build": False,
                "starts_fastapi": False,
                "production_package_complete": False,
            },
            "row_count": review.get("row_count", 0),
            "data_date": reviewed_at,
            "local_fetched_at": reviewed_at,
            "call_status": review.get("status"),
            "error_message_safe": "",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def _tauri_packaged_runtime_launch_review_contract(
    *,
    tauri_build_artifact: dict[str, Any],
    reviewed_at: str | None = None,
    task_id: str = "",
    explicit_review: bool = False,
    explicit_packaged_app_launch_completed: bool = False,
    app_process_observed_after_launch: bool = False,
    launch_command_reviewed_safe: str = "",
    observed_process_name: str = "",
) -> dict[str, Any]:
    app_bundle_ready = bool(
        tauri_build_artifact.get("schema_version") == "tauri_build_artifact_detection.v1"
        and tauri_build_artifact.get("packaged_app_bundle_detected") is True
        and int(tauri_build_artifact.get("bundle_app_count") or 0) > 0
        and tauri_build_artifact.get("bundle_app_path")
        and tauri_build_artifact.get("build_command_executed_by_get_cache") is False
        and tauri_build_artifact.get("artifact_is_gitignored") is True
    )
    boundary_ready = bool(
        tauri_build_artifact.get("external_calls_triggered") is False
        and tauri_build_artifact.get("tushare_called") is False
        and tauri_build_artifact.get("deepseek_called") is False
        and tauri_build_artifact.get("github_called") is False
        and tauri_build_artifact.get("does_not_execute_trades") is True
        and tauri_build_artifact.get("does_not_modify_strategy_action") is True
        and tauri_build_artifact.get("contains_secret") is False
    )
    accepted_launch_command = launch_command_reviewed_safe in {
        "open -n desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app",
        "open desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app",
    }
    launch_smoke_ready = bool(
        explicit_review
        and app_bundle_ready
        and boundary_ready
        and explicit_packaged_app_launch_completed
        and app_process_observed_after_launch
        and accepted_launch_command
    )

    def _row(criterion: str, status: str, passed: bool, evidence: str, *, blocks_review: bool = True) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": bool(passed),
            "evidence": evidence,
            "blocks_review": bool(blocks_review and not passed),
            "blocks_production": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }

    rows = [
        _row(
            "explicit_post_launch_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            explicit_review,
            "POST /api/desktop/tauri-packaged-runtime-launch-review records a separately executed local .app launch smoke.",
        ),
        _row(
            "app_bundle_artifact_ready",
            "passed_local_app_bundle_artifact" if app_bundle_ready else "pending_app_bundle_artifact",
            app_bundle_ready,
            (
                f"app_bundle={tauri_build_artifact.get('packaged_app_bundle_detected')}; "
                f"app_count={tauri_build_artifact.get('bundle_app_count')}; "
                f"app_path={tauri_build_artifact.get('bundle_app_path') or 'missing'}"
            ),
        ),
        _row(
            "explicit_packaged_app_launch_observed",
            "passed_launch_process_observed" if launch_smoke_ready else "pending_launch_process_observation",
            launch_smoke_ready,
            (
                f"explicit_launch={explicit_packaged_app_launch_completed}; "
                f"process_observed={app_process_observed_after_launch}; "
                f"process_name={observed_process_name or 'missing'}; "
                f"launch_command={launch_command_reviewed_safe or 'missing'}"
            ),
        ),
        _row(
            "backend_offline_ux_still_pending",
            "pending_backend_offline_packaged_ux",
            False,
            "Launch smoke does not prove backend-offline UI copy, visual state, or recovery behavior.",
            blocks_review=False,
        ),
        _row(
            "config_log_runtime_paths_still_pending",
            "pending_config_log_runtime_paths",
            False,
            "Launch smoke does not read config values or validate log-path behavior.",
            blocks_review=False,
        ),
        _row(
            "production_package_still_blocked",
            "passed_production_blockers_visible",
            True,
            "DMG distribution, backend startup, offline UX, config/log runtime paths, signing/notarization, and promotion review remain required.",
            blocks_review=False,
        ),
        _row(
            "no_external_trade_secret_boundary",
            "passed_no_external_trade_secret",
            boundary_ready,
            "Review records no provider/model/GitHub/trade call and exposes no secret.",
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_review"]]
    return {
        "schema_version": "tauri_packaged_runtime_launch_review.v1",
        "status": "tauri_packaged_runtime_launch_review_ready_local_launch_smoke"
        if launch_smoke_ready
        else "tauri_packaged_runtime_launch_review_pending",
        "scope": "button_gated_local_tauri_packaged_app_launch_review_no_provider_no_trade",
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "explicit_review_task_done": explicit_review,
        "explicit_packaged_app_launch_completed_before_review": explicit_packaged_app_launch_completed,
        "launch_command_reviewed_safe": launch_command_reviewed_safe if accepted_launch_command else "",
        "app_process_observed_after_launch": app_process_observed_after_launch,
        "observed_process_name": observed_process_name,
        "local_packaged_app_launch_review_ready": launch_smoke_ready,
        "direct_evidence_stage_key": "packaged_app_launch_smoke" if launch_smoke_ready else "",
        "direct_evidence_stage_keys": ["packaged_app_launch_smoke"] if launch_smoke_ready else [],
        "release_binary_path": tauri_build_artifact.get("binary_path"),
        "app_bundle_path": tauri_build_artifact.get("bundle_app_path") or "",
        "app_bundle_detected": tauri_build_artifact.get("packaged_app_bundle_detected") is True,
        "packaged_app_launch_smoke_done": launch_smoke_ready,
        "packaged_app_launch_qa_done": launch_smoke_ready,
        "packaged_app_launch_is_completion": False,
        "packaged_runtime_validated": False,
        "backend_startup_runtime_validated": False,
        "backend_offline_packaged_ux_verified": False,
        "config_log_runtime_paths_validated": False,
        "dmg_distribution_artifact_qa_done": False,
        "signing_notarization_done": False,
        "production_package_complete": False,
        "tauri_build_executed_by_review": False,
        "npm_or_cargo_executed_by_review": False,
        "tauri_runtime_started_by_review": False,
        "packaged_app_opened_by_review": launch_smoke_ready,
        "fastapi_started_by_review": False,
        "config_values_read_by_review": False,
        "log_files_written_by_review": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "row_count": len(rows),
        "blocking_review_count": len(blocking_rows),
        "blocking_review_criteria": [row["criterion"] for row in blocking_rows],
        "call_ledger": [],
        "note": "This review records a local .app launch smoke only. It is not backend-offline UX QA, config/log runtime validation, signing/notarization, or production desktop package completion.",
    }


def _safe_persisted_tauri_packaged_runtime_launch_review(packet: dict[str, Any]) -> dict[str, Any]:
    review = packet.get("tauri_packaged_runtime_launch_review_contract")
    if not isinstance(review, dict):
        return {}
    safe = (
        review.get("schema_version") == "tauri_packaged_runtime_launch_review.v1"
        and review.get("scope") == "button_gated_local_tauri_packaged_app_launch_review_no_provider_no_trade"
        and review.get("explicit_review_task_done") is True
        and review.get("local_packaged_app_launch_review_ready") is True
        and review.get("packaged_app_launch_smoke_done") is True
        and review.get("packaged_app_launch_is_completion") is False
        and review.get("packaged_runtime_validated") is False
        and review.get("production_package_complete") is False
        and review.get("fastapi_started_by_review") is False
        and review.get("config_values_read_by_review") is False
        and review.get("log_files_written_by_review") is False
        and review.get("external_calls_triggered") is False
        and review.get("tushare_called") is False
        and review.get("deepseek_called") is False
        and review.get("github_called") is False
        and review.get("does_not_execute_trades") is True
        and review.get("does_not_modify_strategy_action") is True
        and review.get("contains_secret") is False
    )
    return review if safe else {}


def _read_tauri_packaged_runtime_launch_review_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(TAURI_PACKAGED_RUNTIME_LAUNCH_REVIEW_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_tauri_packaged_runtime_launch_review(packet) else {}


def _write_tauri_packaged_runtime_launch_review_packet(
    *,
    review_contract: dict[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": TAURI_PACKAGED_RUNTIME_LAUNCH_REVIEW_PACKET_KEY,
        "schema_version": "tauri_packaged_runtime_launch_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "tauri_packaged_runtime_launch_review_contract": dict(review_contract),
        "tauri_packaged_runtime_launch_review_rows": list(review_contract.get("rows") or []),
        "call_ledger": list(ledger),
        "cache_only": True,
        "runs_no_build": True,
        "starts_no_fastapi": True,
        "reads_no_config_values": True,
        "writes_no_log_files": True,
        "production_package_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "warnings": [
            "This packet is a local review receipt for a separately executed Tauri .app launch smoke.",
            "It is not backend-offline UX QA, config/log runtime validation, signing/notarization evidence, or production package completion.",
        ],
    }
    if _safe_persisted_tauri_packaged_runtime_launch_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(TAURI_PACKAGED_RUNTIME_LAUNCH_REVIEW_PACKET_KEY, packet)


def _tauri_backend_offline_packaged_ux_review_call_ledger(
    review: dict[str, Any],
    reviewed_at: str,
) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_tauri_backend_offline_packaged_ux_review",
            "request_params_safe": {
                "review_scope": "local_tauri_backend_offline_packaged_ux",
                "app_bundle_path": review.get("app_bundle_path"),
                "offline_notice_observed": review.get("offline_notice_observed"),
                "fastapi_guidance_visible": review.get("fastapi_guidance_visible"),
                "local_only_boundary_visible": review.get("local_only_boundary_visible"),
                "screenshot_sha256": review.get("screenshot_sha256"),
                "external_sources_allowed": False,
                "runs_build": False,
                "starts_fastapi": False,
                "reads_config_values": False,
                "writes_log_files": False,
                "production_package_complete": False,
            },
            "row_count": review.get("row_count", 0),
            "data_date": reviewed_at,
            "local_fetched_at": reviewed_at,
            "call_status": review.get("status"),
            "error_message_safe": "",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def _tauri_backend_offline_packaged_ux_review_contract(
    *,
    tauri_build_artifact: dict[str, Any],
    launch_review: dict[str, Any],
    backend_offline_ux_contract: dict[str, Any],
    reviewed_at: str | None = None,
    task_id: str = "",
    explicit_review: bool = False,
    explicit_packaged_app_launch_completed: bool = False,
    backend_was_offline_during_review: bool = False,
    offline_notice_observed: bool = False,
    fastapi_guidance_visible: bool = False,
    local_only_boundary_visible: bool = False,
    no_provider_model_github_trade_visible: bool = False,
    screenshot_sha256: str = "",
    observed_route: str = "",
) -> dict[str, Any]:
    app_bundle_ready = bool(
        tauri_build_artifact.get("schema_version") == "tauri_build_artifact_detection.v1"
        and tauri_build_artifact.get("packaged_app_bundle_detected") is True
        and int(tauri_build_artifact.get("bundle_app_count") or 0) > 0
        and tauri_build_artifact.get("bundle_app_path")
        and tauri_build_artifact.get("build_command_executed_by_get_cache") is False
        and tauri_build_artifact.get("artifact_is_gitignored") is True
    )
    launch_smoke_ready = bool(
        launch_review.get("schema_version") == "tauri_packaged_runtime_launch_review.v1"
        and launch_review.get("status") == "tauri_packaged_runtime_launch_review_ready_local_launch_smoke"
        and launch_review.get("packaged_app_launch_smoke_done") is True
        and launch_review.get("packaged_app_launch_qa_done") is True
        and launch_review.get("packaged_app_launch_is_completion") is False
        and launch_review.get("production_package_complete") is False
        and launch_review.get("external_calls_triggered") is False
        and launch_review.get("tushare_called") is False
        and launch_review.get("deepseek_called") is False
        and launch_review.get("github_called") is False
        and launch_review.get("does_not_execute_trades") is True
        and launch_review.get("does_not_modify_strategy_action") is True
        and launch_review.get("contains_secret") is False
    )
    frontend_contract_ready = bool(
        backend_offline_ux_contract.get("schema_version") == "tauri_backend_offline_ux_contract.v1"
        and backend_offline_ux_contract.get("frontend_contract_ready") is True
        and backend_offline_ux_contract.get("offline_notice_component_ready") is True
        and backend_offline_ux_contract.get("page_state_banner_integration_ready") is True
        and backend_offline_ux_contract.get("external_calls_triggered") is False
        and backend_offline_ux_contract.get("tushare_called") is False
        and backend_offline_ux_contract.get("deepseek_called") is False
        and backend_offline_ux_contract.get("github_called") is False
        and backend_offline_ux_contract.get("does_not_execute_trades") is True
        and backend_offline_ux_contract.get("does_not_modify_strategy_action") is True
        and backend_offline_ux_contract.get("contains_secret") is False
    )
    screenshot_hash_safe = bool(
        len(screenshot_sha256) == 64 and all(char in "0123456789abcdef" for char in screenshot_sha256)
    )
    observed_route_safe = observed_route[:120]
    offline_ux_ready = bool(
        explicit_review
        and app_bundle_ready
        and launch_smoke_ready
        and frontend_contract_ready
        and explicit_packaged_app_launch_completed
        and backend_was_offline_during_review
        and offline_notice_observed
        and fastapi_guidance_visible
        and local_only_boundary_visible
        and no_provider_model_github_trade_visible
        and screenshot_hash_safe
    )

    def _row(criterion: str, status: str, passed: bool, evidence: str, *, blocks_review: bool = True) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": bool(passed),
            "evidence": evidence,
            "blocks_review": bool(blocks_review and not passed),
            "blocks_production": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }

    rows = [
        _row(
            "explicit_post_offline_ux_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            explicit_review,
            "POST /api/desktop/tauri-backend-offline-packaged-ux-review records a separately observed packaged offline UX run.",
        ),
        _row(
            "app_bundle_and_launch_smoke_ready",
            "passed_app_bundle_launch_smoke" if app_bundle_ready and launch_smoke_ready else "pending_launch_smoke",
            app_bundle_ready and launch_smoke_ready,
            (
                f"app_bundle={tauri_build_artifact.get('packaged_app_bundle_detected')}; "
                f"launch_smoke={launch_review.get('packaged_app_launch_smoke_done')}; "
                f"app_path={tauri_build_artifact.get('bundle_app_path') or 'missing'}"
            ),
        ),
        _row(
            "frontend_offline_contract_ready",
            "passed_frontend_contract" if frontend_contract_ready else "pending_frontend_contract",
            frontend_contract_ready,
            (
                f"frontend_contract_ready={backend_offline_ux_contract.get('frontend_contract_ready')}; "
                f"notice_ready={backend_offline_ux_contract.get('offline_notice_component_ready')}; "
                f"banner_ready={backend_offline_ux_contract.get('page_state_banner_integration_ready')}"
            ),
        ),
        _row(
            "backend_offline_notice_observed_in_packaged_app",
            "passed_packaged_offline_notice" if offline_ux_ready else "pending_packaged_offline_notice",
            offline_ux_ready,
            (
                f"backend_offline={backend_was_offline_during_review}; "
                f"notice={offline_notice_observed}; fastapi_guidance={fastapi_guidance_visible}; "
                f"local_only={local_only_boundary_visible}; safe_boundary={no_provider_model_github_trade_visible}; "
                f"screenshot_sha256={screenshot_sha256 if screenshot_hash_safe else 'missing'}; "
                f"route={observed_route_safe or 'unknown'}"
            ),
        ),
        _row(
            "backend_startup_runtime_still_pending",
            "pending_backend_startup_runtime",
            False,
            "Offline UX QA does not validate manual/sidecar backend startup strategy.",
            blocks_review=False,
        ),
        _row(
            "config_log_runtime_paths_still_pending",
            "pending_config_log_runtime_paths",
            False,
            "Offline UX QA does not read config values or validate log-path behavior.",
            blocks_review=False,
        ),
        _row(
            "production_package_still_blocked",
            "passed_production_blockers_visible",
            True,
            "DMG distribution, backend startup, config/log runtime paths, signing/notarization, and promotion review remain required.",
            blocks_review=False,
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_review"]]
    return {
        "schema_version": "tauri_backend_offline_packaged_ux_review.v1",
        "status": "tauri_backend_offline_packaged_ux_review_ready"
        if offline_ux_ready
        else "tauri_backend_offline_packaged_ux_review_pending",
        "scope": "button_gated_local_tauri_backend_offline_packaged_ux_review_no_provider_no_trade",
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "explicit_review_task_done": explicit_review,
        "explicit_packaged_app_launch_completed_before_review": explicit_packaged_app_launch_completed,
        "backend_was_offline_during_review": backend_was_offline_during_review,
        "offline_notice_observed": offline_notice_observed,
        "fastapi_guidance_visible": fastapi_guidance_visible,
        "local_only_boundary_visible": local_only_boundary_visible,
        "no_provider_model_github_trade_visible": no_provider_model_github_trade_visible,
        "screenshot_sha256": screenshot_sha256 if screenshot_hash_safe else "",
        "observed_route": observed_route_safe,
        "local_backend_offline_packaged_ux_review_ready": offline_ux_ready,
        "direct_evidence_stage_key": "backend_offline_packaged_ux" if offline_ux_ready else "",
        "direct_evidence_stage_keys": ["backend_offline_packaged_ux"] if offline_ux_ready else [],
        "app_bundle_path": tauri_build_artifact.get("bundle_app_path") or "",
        "app_bundle_detected": tauri_build_artifact.get("packaged_app_bundle_detected") is True,
        "packaged_app_launch_smoke_done": launch_smoke_ready,
        "packaged_app_launch_qa_done": launch_smoke_ready,
        "backend_offline_packaged_ux_verified": offline_ux_ready,
        "backend_offline_packaged_ux_is_completion": False,
        "packaged_runtime_validated": False,
        "backend_startup_runtime_validated": False,
        "config_log_runtime_paths_validated": False,
        "dmg_distribution_artifact_qa_done": False,
        "signing_notarization_done": False,
        "production_package_complete": False,
        "tauri_build_executed_by_review": False,
        "npm_or_cargo_executed_by_review": False,
        "tauri_runtime_started_by_review": False,
        "packaged_app_opened_by_review": False,
        "fastapi_started_by_review": False,
        "config_values_read_by_review": False,
        "log_files_written_by_review": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "row_count": len(rows),
        "blocking_review_count": len(blocking_rows),
        "blocking_review_criteria": [row["criterion"] for row in blocking_rows],
        "call_ledger": [],
        "note": "This review records a separately observed packaged backend-offline UX smoke only. It is not backend startup validation, config/log runtime validation, signing/notarization, or production desktop package completion.",
    }


def _safe_persisted_tauri_backend_offline_packaged_ux_review(packet: dict[str, Any]) -> dict[str, Any]:
    review = packet.get("tauri_backend_offline_packaged_ux_review_contract")
    if not isinstance(review, dict):
        return {}
    safe = (
        review.get("schema_version") == "tauri_backend_offline_packaged_ux_review.v1"
        and review.get("scope") == "button_gated_local_tauri_backend_offline_packaged_ux_review_no_provider_no_trade"
        and review.get("explicit_review_task_done") is True
        and review.get("local_backend_offline_packaged_ux_review_ready") is True
        and review.get("backend_offline_packaged_ux_verified") is True
        and review.get("backend_offline_packaged_ux_is_completion") is False
        and review.get("packaged_runtime_validated") is False
        and review.get("production_package_complete") is False
        and review.get("fastapi_started_by_review") is False
        and review.get("config_values_read_by_review") is False
        and review.get("log_files_written_by_review") is False
        and review.get("external_calls_triggered") is False
        and review.get("tushare_called") is False
        and review.get("deepseek_called") is False
        and review.get("github_called") is False
        and review.get("does_not_execute_trades") is True
        and review.get("does_not_modify_strategy_action") is True
        and review.get("contains_secret") is False
    )
    return review if safe else {}


def _read_tauri_backend_offline_packaged_ux_review_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(TAURI_BACKEND_OFFLINE_PACKAGED_UX_REVIEW_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_tauri_backend_offline_packaged_ux_review(packet) else {}


def _write_tauri_backend_offline_packaged_ux_review_packet(
    *,
    review_contract: dict[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": TAURI_BACKEND_OFFLINE_PACKAGED_UX_REVIEW_PACKET_KEY,
        "schema_version": "tauri_backend_offline_packaged_ux_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "tauri_backend_offline_packaged_ux_review_contract": dict(review_contract),
        "tauri_backend_offline_packaged_ux_review_rows": list(review_contract.get("rows") or []),
        "call_ledger": list(ledger),
        "cache_only": True,
        "runs_no_build": True,
        "starts_no_fastapi": True,
        "reads_no_config_values": True,
        "writes_no_log_files": True,
        "production_package_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "warnings": [
            "This packet is a local review receipt for separately observed packaged backend-offline UX.",
            "It is not backend startup validation, config/log runtime validation, signing/notarization evidence, or production package completion.",
        ],
    }
    if _safe_persisted_tauri_backend_offline_packaged_ux_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(TAURI_BACKEND_OFFLINE_PACKAGED_UX_REVIEW_PACKET_KEY, packet)


def _tauri_backend_startup_runtime_review_call_ledger(
    review: dict[str, Any],
    reviewed_at: str,
) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_tauri_backend_startup_runtime_review",
            "request_params_safe": {
                "review_scope": "local_tauri_manual_fastapi_packaged_runtime_connection",
                "app_bundle_path": review.get("app_bundle_path"),
                "api_base_observed_safe": review.get("api_base_observed_safe"),
                "fastapi_health_observed_ok": review.get("fastapi_health_observed_ok"),
                "packaged_app_fastapi_online_observed": review.get("packaged_app_fastapi_online_observed"),
                "screenshot_sha256": review.get("screenshot_sha256"),
                "external_sources_allowed": False,
                "starts_fastapi": False,
                "runs_build": False,
                "reads_config_values": False,
                "writes_log_files": False,
                "production_package_complete": False,
            },
            "row_count": review.get("row_count", 0),
            "data_date": reviewed_at,
            "local_fetched_at": reviewed_at,
            "call_status": review.get("status"),
            "error_message_safe": "",
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
    ]


def _tauri_backend_startup_runtime_review_contract(
    *,
    tauri_build_artifact: dict[str, Any],
    launch_review: dict[str, Any],
    offline_ux_review: dict[str, Any],
    reviewed_at: str | None = None,
    task_id: str = "",
    explicit_review: bool = False,
    explicit_packaged_app_launch_completed: bool = False,
    manual_fastapi_started_before_review: bool = False,
    fastapi_health_observed_ok: bool = False,
    packaged_app_fastapi_online_observed: bool = False,
    api_base_observed: str = "",
    health_status_observed: str = "",
    screenshot_sha256: str = "",
) -> dict[str, Any]:
    app_bundle_ready = bool(
        tauri_build_artifact.get("schema_version") == "tauri_build_artifact_detection.v1"
        and tauri_build_artifact.get("packaged_app_bundle_detected") is True
        and int(tauri_build_artifact.get("bundle_app_count") or 0) > 0
        and tauri_build_artifact.get("bundle_app_path")
        and tauri_build_artifact.get("build_command_executed_by_get_cache") is False
        and tauri_build_artifact.get("artifact_is_gitignored") is True
    )
    launch_smoke_ready = bool(
        launch_review.get("schema_version") == "tauri_packaged_runtime_launch_review.v1"
        and launch_review.get("status") == "tauri_packaged_runtime_launch_review_ready_local_launch_smoke"
        and launch_review.get("packaged_app_launch_smoke_done") is True
        and launch_review.get("packaged_app_launch_qa_done") is True
        and launch_review.get("packaged_app_launch_is_completion") is False
        and launch_review.get("production_package_complete") is False
        and launch_review.get("external_calls_triggered") is False
        and launch_review.get("tushare_called") is False
        and launch_review.get("deepseek_called") is False
        and launch_review.get("github_called") is False
        and launch_review.get("does_not_execute_trades") is True
        and launch_review.get("does_not_modify_strategy_action") is True
        and launch_review.get("contains_secret") is False
    )
    offline_ux_ready = bool(
        offline_ux_review.get("schema_version") == "tauri_backend_offline_packaged_ux_review.v1"
        and offline_ux_review.get("status") == "tauri_backend_offline_packaged_ux_review_ready"
        and offline_ux_review.get("backend_offline_packaged_ux_verified") is True
        and offline_ux_review.get("backend_offline_packaged_ux_is_completion") is False
        and offline_ux_review.get("production_package_complete") is False
        and offline_ux_review.get("external_calls_triggered") is False
        and offline_ux_review.get("tushare_called") is False
        and offline_ux_review.get("deepseek_called") is False
        and offline_ux_review.get("github_called") is False
        and offline_ux_review.get("does_not_execute_trades") is True
        and offline_ux_review.get("does_not_modify_strategy_action") is True
        and offline_ux_review.get("contains_secret") is False
    )
    accepted_api_base = api_base_observed in {"http://127.0.0.1:8710", "http://localhost:8710"}
    health_status_safe = health_status_observed.strip()[:80]
    screenshot_hash_safe = bool(
        len(screenshot_sha256) == 64 and all(char in "0123456789abcdef" for char in screenshot_sha256)
    )
    startup_ready = bool(
        explicit_review
        and app_bundle_ready
        and launch_smoke_ready
        and offline_ux_ready
        and explicit_packaged_app_launch_completed
        and manual_fastapi_started_before_review
        and fastapi_health_observed_ok
        and packaged_app_fastapi_online_observed
        and accepted_api_base
        and health_status_safe in {"ok", "ready", "healthy"}
        and screenshot_hash_safe
    )

    def _row(criterion: str, status: str, passed: bool, evidence: str, *, blocks_review: bool = True) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": bool(passed),
            "evidence": evidence,
            "blocks_review": bool(blocks_review and not passed),
            "blocks_production": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }

    rows = [
        _row(
            "explicit_post_backend_startup_runtime_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            explicit_review,
            "POST /api/desktop/tauri-backend-startup-runtime-review records a separately observed manual FastAPI packaged runtime connection.",
        ),
        _row(
            "app_bundle_launch_and_offline_baseline_ready",
            "passed_prior_packaged_evidence" if app_bundle_ready and launch_smoke_ready and offline_ux_ready else "pending_prior_packaged_evidence",
            app_bundle_ready and launch_smoke_ready and offline_ux_ready,
            (
                f"app_bundle={tauri_build_artifact.get('packaged_app_bundle_detected')}; "
                f"launch_smoke={launch_review.get('packaged_app_launch_smoke_done')}; "
                f"offline_ux={offline_ux_review.get('backend_offline_packaged_ux_verified')}"
            ),
        ),
        _row(
            "manual_fastapi_runtime_observed",
            "passed_manual_fastapi_runtime" if startup_ready else "pending_manual_fastapi_runtime",
            startup_ready,
            (
                f"manual_fastapi_started={manual_fastapi_started_before_review}; "
                f"health_ok={fastapi_health_observed_ok}; health_status={health_status_safe or 'missing'}; "
                f"api_base={api_base_observed if accepted_api_base else 'unsafe_or_missing'}; "
                f"packaged_online={packaged_app_fastapi_online_observed}; "
                f"screenshot_sha256={screenshot_sha256 if screenshot_hash_safe else 'missing'}"
            ),
        ),
        _row(
            "sidecar_autostart_still_pending",
            "pending_sidecar_autostart",
            False,
            "Manual FastAPI startup works for packaged runtime, but sidecar/autostart remains unvalidated.",
            blocks_review=False,
        ),
        _row(
            "config_log_runtime_paths_still_pending",
            "pending_config_log_runtime_paths",
            False,
            "Backend startup runtime QA does not read config values or validate log-path behavior.",
            blocks_review=False,
        ),
        _row(
            "production_package_still_blocked",
            "passed_production_blockers_visible",
            True,
            "DMG distribution, config/log runtime paths, signing/notarization, sidecar decision, and promotion review remain required.",
            blocks_review=False,
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_review"]]
    return {
        "schema_version": "tauri_backend_startup_runtime_review.v1",
        "status": "tauri_backend_startup_runtime_review_ready"
        if startup_ready
        else "tauri_backend_startup_runtime_review_pending",
        "scope": "button_gated_local_tauri_manual_fastapi_runtime_review_no_provider_no_trade",
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "explicit_review_task_done": explicit_review,
        "explicit_packaged_app_launch_completed_before_review": explicit_packaged_app_launch_completed,
        "manual_fastapi_started_before_review": manual_fastapi_started_before_review,
        "fastapi_health_observed_ok": fastapi_health_observed_ok,
        "packaged_app_fastapi_online_observed": packaged_app_fastapi_online_observed,
        "api_base_observed_safe": api_base_observed if accepted_api_base else "",
        "health_status_observed": health_status_safe,
        "screenshot_sha256": screenshot_sha256 if screenshot_hash_safe else "",
        "local_backend_startup_runtime_review_ready": startup_ready,
        "direct_evidence_stage_key": "backend_startup_runtime" if startup_ready else "",
        "direct_evidence_stage_keys": ["backend_startup_runtime"] if startup_ready else [],
        "app_bundle_path": tauri_build_artifact.get("bundle_app_path") or "",
        "app_bundle_detected": tauri_build_artifact.get("packaged_app_bundle_detected") is True,
        "packaged_app_launch_smoke_done": launch_smoke_ready,
        "backend_offline_packaged_ux_verified": offline_ux_ready,
        "backend_startup_runtime_validated": startup_ready,
        "backend_startup_runtime_is_completion": False,
        "backend_sidecar_autostart_validated": False,
        "backend_autostart_configured": False,
        "packaged_runtime_validated": False,
        "config_log_runtime_paths_validated": False,
        "dmg_distribution_artifact_qa_done": False,
        "signing_notarization_done": False,
        "production_package_complete": False,
        "tauri_build_executed_by_review": False,
        "npm_or_cargo_executed_by_review": False,
        "tauri_runtime_started_by_review": False,
        "packaged_app_opened_by_review": False,
        "fastapi_started_by_review": False,
        "config_values_read_by_review": False,
        "log_files_written_by_review": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "rows": rows,
        "row_count": len(rows),
        "blocking_review_count": len(blocking_rows),
        "blocking_review_criteria": [row["criterion"] for row in blocking_rows],
        "call_ledger": [],
        "note": "This review records a separately observed manual FastAPI packaged runtime connection only. It is not sidecar/autostart validation, config/log runtime validation, signing/notarization, or production desktop package completion.",
    }


def _safe_persisted_tauri_backend_startup_runtime_review(packet: dict[str, Any]) -> dict[str, Any]:
    review = packet.get("tauri_backend_startup_runtime_review_contract")
    if not isinstance(review, dict):
        return {}
    safe = (
        review.get("schema_version") == "tauri_backend_startup_runtime_review.v1"
        and review.get("status") == "tauri_backend_startup_runtime_review_ready"
        and review.get("scope") == "button_gated_local_tauri_manual_fastapi_runtime_review_no_provider_no_trade"
        and review.get("explicit_review_task_done") is True
        and review.get("manual_fastapi_started_before_review") is True
        and review.get("fastapi_health_observed_ok") is True
        and review.get("packaged_app_fastapi_online_observed") is True
        and review.get("api_base_observed_safe") in {"http://127.0.0.1:8710", "http://localhost:8710"}
        and review.get("health_status_observed") in {"ok", "ready", "healthy"}
        and len(str(review.get("screenshot_sha256") or "")) == 64
        and review.get("local_backend_startup_runtime_review_ready") is True
        and review.get("backend_startup_runtime_validated") is True
        and review.get("backend_startup_runtime_is_completion") is False
        and review.get("backend_sidecar_autostart_validated") is False
        and review.get("backend_autostart_configured") is False
        and review.get("packaged_runtime_validated") is False
        and review.get("config_log_runtime_paths_validated") is False
        and review.get("dmg_distribution_artifact_qa_done") is False
        and review.get("signing_notarization_done") is False
        and review.get("production_package_complete") is False
        and review.get("fastapi_started_by_review") is False
        and review.get("config_values_read_by_review") is False
        and review.get("log_files_written_by_review") is False
        and review.get("external_calls_triggered") is False
        and review.get("tushare_called") is False
        and review.get("deepseek_called") is False
        and review.get("github_called") is False
        and review.get("does_not_execute_trades") is True
        and review.get("does_not_modify_strategy_action") is True
        and review.get("contains_secret") is False
    )
    return review if safe else {}


def _read_tauri_backend_startup_runtime_review_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(TAURI_BACKEND_STARTUP_RUNTIME_REVIEW_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_tauri_backend_startup_runtime_review(packet) else {}


def _write_tauri_backend_startup_runtime_review_packet(
    *,
    review_contract: dict[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": TAURI_BACKEND_STARTUP_RUNTIME_REVIEW_PACKET_KEY,
        "schema_version": "tauri_backend_startup_runtime_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "tauri_backend_startup_runtime_review_contract": dict(review_contract),
        "tauri_backend_startup_runtime_review_rows": list(review_contract.get("rows") or []),
        "call_ledger": list(ledger),
        "cache_only": True,
        "runs_no_build": True,
        "starts_no_fastapi": True,
        "reads_no_config_values": True,
        "writes_no_log_files": True,
        "production_package_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "warnings": [
            "This packet is a local review receipt for separately observed manual FastAPI packaged runtime connection.",
            "It is not sidecar/autostart validation, config/log runtime validation, signing/notarization evidence, or production package completion.",
        ],
    }
    if _safe_persisted_tauri_backend_startup_runtime_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(TAURI_BACKEND_STARTUP_RUNTIME_REVIEW_PACKET_KEY, packet)


def read_desktop_shell_preflight_cache() -> dict[str, Any]:
    package_summary = _package_json_summary()
    tauri_config = _tauri_config_summary()
    file_rows = [
        _file_row(DESKTOP_ROOT / "package.json", "package_json", "React/Vite package manifest"),
        _file_row(DESKTOP_ROOT / "package-lock.json", "package_lock", "Reproducible npm dependency lockfile"),
        _file_row(DESKTOP_ROOT / "vite.config.ts", "vite_config", "Vite frontend config"),
        _file_row(DESKTOP_ROOT / "tsconfig.json", "tsconfig", "TypeScript strict config"),
        _file_row(DESKTOP_ROOT / "src" / "App.tsx", "react_app", "React route shell"),
        _file_row(DESKTOP_ROOT / "src-tauri" / "tauri.conf.json", "tauri_config", "Tauri v2 config"),
        _file_row(DESKTOP_ROOT / "src-tauri" / "Cargo.toml", "cargo_toml", "Rust package manifest"),
        _file_row(DESKTOP_ROOT / "src-tauri" / "Cargo.lock", "cargo_lock", "Reproducible Rust dependency lockfile"),
        _file_row(DESKTOP_ROOT / "src-tauri" / "src" / "main.rs", "tauri_main", "Tauri app entry"),
        _file_row(DESKTOP_ROOT / "src-tauri" / "icons" / "icon.png", "tauri_icon", "Tauri desktop window and app icon"),
        _file_row(COMMAND_CENTER_3_LAUNCHER, "command_center_3_launcher", "Manual local Command Center 3.0 launcher"),
        _file_row(
            COMMAND_CENTER_3_SHORTCUT_INSTALLER,
            "command_center_3_shortcut_installer",
            "Manual local Desktop shortcut installer",
        ),
        _file_row(DESKTOP_ROOT / "node_modules", "node_modules", "Installed frontend dependencies"),
        _file_row(DESKTOP_ROOT / "dist", "dist", "Vite build output, should not be committed"),
    ]
    command_rows = [
        _command_row("node", "Node.js runtime", "Vite dev/build"),
        _command_row("npm", "npm package manager", "Frontend dependency install/build"),
        _command_row("rustc", "Rust compiler", "Tauri dev/build"),
        _command_row("cargo", "Rust package manager", "Tauri dev/build"),
    ]
    required_file_count = 10
    file_ready_count = sum(1 for row in file_rows[:required_file_count] if row["exists"])
    rust_ready = all(row["available"] for row in command_rows if row["command"] in {"rustc", "cargo"})
    node_ready = all(row["available"] for row in command_rows if row["command"] in {"node", "npm"})
    scaffold_ready = file_ready_count == required_file_count and bool(package_summary.get("has_vite")) and bool(package_summary.get("has_tauri_cli"))
    vite_dev_ready = scaffold_ready and node_ready
    tauri_dev_ready = vite_dev_ready and rust_ready
    api_base = os.getenv("VITE_API_BASE_URL") or "http://127.0.0.1:8710"
    api_base_info = _api_base_summary(api_base)
    desktop_launcher_contract = _desktop_launcher_contract(api_base)
    production_runtime_contract = _production_runtime_contract(api_base_info, tauri_config)
    tauri_build_artifact = _tauri_build_artifact_summary()
    backend_offline_ux_contract = _backend_offline_ux_contract(api_base_info)
    production_readiness = {
        "status": "tauri_preflight_ready" if tauri_dev_ready else ("vite_ready_tauri_toolchain_pending" if vite_dev_ready else "desktop_scaffold_partial"),
        "scope": "tauri_desktop_production_preflight",
        "vite_build_ready": vite_dev_ready,
        "tauri_dev_ready": tauri_dev_ready,
        "tauri_package_build_attempted": False,
        "tauri_build_artifact_status": tauri_build_artifact["status"],
        "tauri_build_artifact_detected": tauri_build_artifact["binary_exists"],
        "tauri_package_build_required_for_production": True,
        "rust_toolchain_required": True,
        "backend_sidecar_autostart_enabled": False,
        "backend_sidecar_autostart_planned": True,
        "frontend_stores_tokens": False,
        "production_runtime_contract_status": production_runtime_contract["status"],
        "backend_offline_ux_contract_status": backend_offline_ux_contract["status"],
        "backend_offline_ux_frontend_contract_ready": backend_offline_ux_contract["frontend_contract_ready"],
        "config_log_paths_declared": production_runtime_contract["config_paths_declared"] and production_runtime_contract["log_paths_declared"],
        "api_base_is_localhost": api_base_info["is_localhost"],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "blockers": [] if tauri_dev_ready else (["rust_cargo_missing"] if vite_dev_ready else ["desktop_scaffold_incomplete"]),
        "note": "当前阶段验证 React/Vite 与 Tauri scaffold；生产 package build 和 FastAPI sidecar 自动拉起仍需后续阶段。",
    }
    production_blocker_audit = _production_package_blocker_audit(
        package_summary=package_summary,
        tauri_config=tauri_config,
        production_readiness=production_readiness,
        node_ready=node_ready,
        rust_ready=rust_ready,
        scaffold_ready=scaffold_ready,
        api_base_info=api_base_info,
        runtime_contract=production_runtime_contract,
        tauri_build_artifact=tauri_build_artifact,
        backend_offline_ux_contract=backend_offline_ux_contract,
    )
    packaged_runtime_qa_contract = _packaged_runtime_qa_contract(
        production_runtime_contract=production_runtime_contract,
        tauri_build_artifact=tauri_build_artifact,
        backend_offline_ux_contract=backend_offline_ux_contract,
        production_blocker_audit=production_blocker_audit,
    )
    tauri_release_manifest_contract = _tauri_release_manifest_contract(
        tauri_config=tauri_config,
        production_runtime_contract=production_runtime_contract,
        tauri_build_artifact=tauri_build_artifact,
        packaged_runtime_qa_contract=packaged_runtime_qa_contract,
    )
    production_package_readiness_receipt = _tauri_production_readiness_receipt(
        production_readiness=production_readiness,
        production_runtime_contract=production_runtime_contract,
        tauri_build_artifact=tauri_build_artifact,
        backend_offline_ux_contract=backend_offline_ux_contract,
        production_blocker_audit=production_blocker_audit,
        packaged_runtime_qa_contract=packaged_runtime_qa_contract,
    )

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if scaffold_ready else "partial",
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": _now_iso(),
        "api_base": api_base,
        "api_base_info": api_base_info,
        "desktop_launcher_contract": desktop_launcher_contract,
        "desktop_launcher_rows": desktop_launcher_contract["rows"],
        "dev_launch_plan": _dev_launch_plan(api_base),
        "production_launch_plan": _production_launch_plan(api_base),
        "package_json": package_summary,
        "tauri_config": tauri_config,
        "tauri_build_artifact": tauri_build_artifact,
        "production_readiness": production_readiness,
        "production_runtime_contract": production_runtime_contract,
        "production_runtime_contract_rows": production_runtime_contract["rows"],
        "backend_offline_ux_contract": backend_offline_ux_contract,
        "backend_offline_ux_rows": backend_offline_ux_contract["rows"],
        "production_blocker_audit": production_blocker_audit,
        "production_blocker_rows": production_blocker_audit["rows"],
        "packaged_runtime_qa_contract": packaged_runtime_qa_contract,
        "packaged_runtime_qa_rows": packaged_runtime_qa_contract["rows"],
        "tauri_release_manifest_contract": tauri_release_manifest_contract,
        "tauri_release_manifest_rows": tauri_release_manifest_contract["rows"],
        "production_package_readiness_receipt": production_package_readiness_receipt,
        "production_package_readiness_receipt_rows": production_package_readiness_receipt["rows"],
        "file_rows": file_rows,
        "command_rows": command_rows,
        "counts": {
            "required_file_count": required_file_count,
            "required_file_ready_count": file_ready_count,
            "command_count": len(command_rows),
            "command_ready_count": sum(1 for row in command_rows if row["available"]),
            "desktop_launcher_row_count": desktop_launcher_contract["row_count"],
            "desktop_launcher_ready": 1 if desktop_launcher_contract["status"] == "local_launcher_ready_dev_only" else 0,
            "packaged_runtime_qa_matrix_count": packaged_runtime_qa_contract["qa_matrix_count"],
            "packaged_runtime_pending_qa_count": packaged_runtime_qa_contract["pending_qa_count"],
            "tauri_release_manifest_row_count": tauri_release_manifest_contract["row_count"],
            "tauri_release_manifest_local_blocker_count": tauri_release_manifest_contract["local_blocker_count"],
            "tauri_release_manifest_production_blocker_count": tauri_release_manifest_contract["production_blocker_count"],
            "production_package_readiness_receipt_ready": 1 if production_package_readiness_receipt["local_receipt_ready"] else 0,
            "production_package_readiness_receipt_blocker_count": production_package_readiness_receipt["blocking_criterion_count"],
        },
        "runtime": {
            "node_ready": node_ready,
            "rust_ready": rust_ready,
            "vite_dev_ready": vite_dev_ready,
            "tauri_dev_ready": tauri_dev_ready,
            "node_modules_present": (DESKTOP_ROOT / "node_modules").exists(),
            "dist_present": (DESKTOP_ROOT / "dist").exists(),
            "tauri_release_binary_present": tauri_build_artifact["binary_exists"],
            "tauri_release_binary_size_bytes": tauri_build_artifact["binary_size_bytes"],
            "tauri_cli_declared": bool(package_summary.get("has_tauri_cli")),
            "tauri_build_attempted": False,
            "vite_build_attempted": False,
            "fastapi_dev_server_started": False,
            "api_base_is_localhost": api_base_info["is_localhost"],
            "api_health_endpoint": api_base_info["expected_health_endpoint"],
            "desktop_launcher_ready": desktop_launcher_contract["status"] == "local_launcher_ready_dev_only",
            "desktop_launcher_executable": desktop_launcher_contract["launcher_executable"],
            "desktop_launcher_path": desktop_launcher_contract["launcher_path"],
            "desktop_shortcut_installer_ready": desktop_launcher_contract["shortcut_installer_exists"]
            and desktop_launcher_contract["shortcut_installer_executable"],
            "desktop_shortcut_installer_path": desktop_launcher_contract["shortcut_installer_path"],
            "backend_autostart_configured": False,
            "production_package_build_attempted": False,
            "production_package_build_artifact_detected": tauri_build_artifact["binary_exists"],
            "backend_sidecar_autostart_enabled": False,
            "production_package_ready": production_blocker_audit["package_ready"],
            "production_blocker_count": production_blocker_audit["blocker_count"],
            "tauri_build_verified": production_blocker_audit["tauri_build_verified"],
            "backend_offline_ui_packaged_runtime_verified": production_blocker_audit["backend_offline_ui_packaged_runtime_verified"],
            "backend_offline_ux_frontend_contract_ready": production_blocker_audit["backend_offline_ux_frontend_contract_ready"],
            "backend_offline_ux_contract_status": production_blocker_audit["backend_offline_ux_contract_status"],
            "config_log_paths_declared": production_blocker_audit["config_log_paths_declared"],
            "production_runtime_contract_status": production_runtime_contract["status"],
            "production_runtime_contract_declared": True,
            "production_runtime_config_paths_declared": production_runtime_contract["config_paths_declared"],
            "production_runtime_log_paths_declared": production_runtime_contract["log_paths_declared"],
            "production_runtime_reads_config_values": production_runtime_contract["reads_config_values"],
            "production_runtime_writes_log_files": production_runtime_contract["writes_log_files"],
            "macos_signing_notarization_ready": production_blocker_audit["macos_signing_notarization_ready"],
            "packaged_runtime_qa_contract_ready": packaged_runtime_qa_contract["qa_contract_ready"],
            "packaged_runtime_pending_qa_count": packaged_runtime_qa_contract["pending_qa_count"],
            "tauri_release_manifest_ready": tauri_release_manifest_contract["local_release_manifest_ready"],
            "tauri_release_manifest_status": tauri_release_manifest_contract["status"],
            "tauri_release_manifest_production_blocker_count": tauri_release_manifest_contract["production_blocker_count"],
            "production_package_readiness_receipt_ready": production_package_readiness_receipt["local_receipt_ready"],
            "production_package_readiness_receipt_status": production_package_readiness_receipt["status"],
            "production_package_readiness_receipt_blocker_count": production_package_readiness_receipt["blocking_criterion_count"],
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_run_npm_install": True,
            "does_not_run_npm_build": True,
            "does_not_run_tauri": True,
            "does_not_run_cargo": True,
            "does_not_start_fastapi": True,
            "frontend_must_use_fastapi_api_client": True,
            "backend_autostart_enabled": False,
            "api_base_must_be_localhost": True,
            "production_runtime_contract_is_path_only": True,
            "packaged_runtime_qa_contract_is_static": True,
            "desktop_launcher_contract_is_local": True,
            "desktop_launcher_contract_is_manual_dev_only": True,
            "desktop_launcher_contract_is_not_production_package": True,
            "desktop_launcher_contract_does_not_run_from_get_cache": True,
            "desktop_shortcut_installer_contract_is_local": True,
            "desktop_shortcut_installer_does_not_run_from_get_cache": True,
            "desktop_shortcut_installer_does_not_start_services": True,
            "tauri_release_manifest_contract_is_local": True,
            "tauri_release_manifest_contract_is_not_build": True,
            "tauri_release_manifest_contract_is_not_runtime_execution": True,
            "tauri_release_manifest_contract_is_not_production_completion": True,
            "production_package_readiness_receipt_is_local": True,
            "production_package_readiness_receipt_is_not_build": True,
            "production_package_readiness_receipt_is_not_runtime_execution": True,
            "production_package_readiness_receipt_is_not_production_completion": True,
            "does_not_read_config_values": True,
            "does_not_write_log_files": True,
            "does_not_call_tushare": True,
            "does_not_call_deepseek": True,
            "does_not_call_github": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        },
        "call_ledger": [
            {
                "api": "local_desktop_shell_preflight_cache",
                "source": "desktop scaffold files and local command availability",
                "row_count": len(file_rows) + len(command_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "cache_read",
                "external": False,
            }
        ]
        + tauri_release_manifest_contract["call_ledger"]
        + desktop_launcher_contract["call_ledger"]
        + production_package_readiness_receipt["call_ledger"],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "warnings": [
            "GET /api/desktop/preflight-cache 只读检查本地 React/Tauri scaffold；不会运行 npm install、npm build、cargo 或 Tauri。",
            "Rust/Cargo 缺失不阻断 Vite 前端；只有 Tauri dev/build 需要 Rust 工具链。",
            "Tauri 开发模式当前不自动拉起 FastAPI；请先运行 scripts/dev_server.sh，再启动 Vite 或 Tauri dev。",
            "scripts/start_command_center_3.command 是手动双击入口：仅在用户运行时启动本地 FastAPI/Vite 并打开本地页面；GET preflight 不会运行它。",
            "桌面壳预检不读取 token/key，不调用 Tushare、DeepSeek、GitHub，不执行真实交易。",
        ],
    }
    tauri_package_durable_evidence_recipe = _tauri_package_durable_evidence_recipe(packet)
    packet["tauri_package_durable_evidence_recipe"] = tauri_package_durable_evidence_recipe
    packet["tauri_package_durable_evidence_rows"] = tauri_package_durable_evidence_recipe["rows"]
    packet["counts"]["tauri_package_durable_evidence_row_count"] = tauri_package_durable_evidence_recipe["row_count"]
    packet["counts"]["tauri_package_durable_evidence_blocker_count"] = tauri_package_durable_evidence_recipe[
        "durable_evidence_blocker_count"
    ]
    packet["counts"]["tauri_package_durable_evidence_ready"] = tauri_package_durable_evidence_recipe["local_recipe_ready"]
    packet["runtime"]["tauri_package_durable_evidence_recipe_ready"] = tauri_package_durable_evidence_recipe[
        "local_recipe_ready"
    ]
    packet["runtime"]["tauri_package_durable_evidence_recipe_status"] = tauri_package_durable_evidence_recipe["status"]
    packet["runtime"]["tauri_package_durable_evidence_blocker_count"] = tauri_package_durable_evidence_recipe[
        "durable_evidence_blocker_count"
    ]
    packet["policy"]["tauri_package_durable_evidence_recipe_is_local"] = True
    packet["policy"]["tauri_package_durable_evidence_recipe_is_not_build"] = True
    packet["policy"]["tauri_package_durable_evidence_recipe_is_not_runtime_execution"] = True
    packet["policy"]["tauri_package_durable_evidence_recipe_is_not_production_completion"] = True
    packet["policy"]["tauri_package_durable_evidence_recipe_requires_packaged_runtime_evidence"] = True
    packet["call_ledger"] = packet["call_ledger"] + tauri_package_durable_evidence_recipe["call_ledger"]
    packet["warnings"].append(
        "tauri_package_durable_evidence_recipe 只固定 LTG-09 生产桌面包 durable evidence 清单；不会运行 npm/cargo/Tauri、打开 packaged app、启动 FastAPI、读取配置、写日志、外联或完成生产包。"
    )
    persisted_artifact_review_packet = _read_tauri_package_artifact_review_packet()
    persisted_artifact_review = _safe_persisted_tauri_package_artifact_review(persisted_artifact_review_packet)
    if persisted_artifact_review:
        packet["tauri_package_artifact_review_contract"] = persisted_artifact_review
        packet["tauri_package_artifact_review_rows"] = list(persisted_artifact_review.get("rows") or [])
        packet["tauri_package_artifact_review_ready"] = True
        packet["counts"]["tauri_package_artifact_review_row_count"] = persisted_artifact_review.get("row_count", 0)
        packet["counts"]["tauri_package_artifact_review_blocking_count"] = persisted_artifact_review.get(
            "blocking_review_count",
            0,
        )
        packet["runtime"]["tauri_package_artifact_review_ready"] = True
        packet["runtime"]["tauri_package_artifact_review_status"] = persisted_artifact_review.get("status")
        packet["runtime"]["tauri_release_binary_artifact_reviewed"] = True
        packet["policy"]["tauri_package_artifact_review_is_local"] = True
        packet["policy"]["tauri_package_artifact_review_is_not_build"] = True
        packet["policy"]["tauri_package_artifact_review_is_not_runtime_execution"] = True
        packet["policy"]["tauri_package_artifact_review_is_not_production_completion"] = True
        packet["call_ledger"] = packet["call_ledger"] + [
            row for row in persisted_artifact_review_packet.get("call_ledger", []) if isinstance(row, dict)
        ]
        packet["warnings"].append(
            "tauri_package_artifact_review 只审查本地 release binary artifact；不等于 packaged app launch QA、签名/公证或 production package 完成。"
        )
    persisted_launch_review_packet = _read_tauri_packaged_runtime_launch_review_packet()
    persisted_launch_review = _safe_persisted_tauri_packaged_runtime_launch_review(persisted_launch_review_packet)
    if persisted_launch_review:
        packet["tauri_packaged_runtime_launch_review_contract"] = persisted_launch_review
        packet["tauri_packaged_runtime_launch_review_rows"] = list(persisted_launch_review.get("rows") or [])
        packet["tauri_packaged_runtime_launch_review_ready"] = True
        packet["counts"]["tauri_packaged_runtime_launch_review_row_count"] = persisted_launch_review.get("row_count", 0)
        packet["counts"]["tauri_packaged_runtime_launch_review_blocking_count"] = persisted_launch_review.get(
            "blocking_review_count",
            0,
        )
        packet["runtime"]["tauri_packaged_runtime_launch_review_ready"] = True
        packet["runtime"]["tauri_packaged_runtime_launch_review_status"] = persisted_launch_review.get("status")
        packet["runtime"]["tauri_packaged_app_launch_smoke_done"] = True
        packet["policy"]["tauri_packaged_runtime_launch_review_is_local"] = True
        packet["policy"]["tauri_packaged_runtime_launch_review_is_not_build"] = True
        packet["policy"]["tauri_packaged_runtime_launch_review_is_not_backend_start"] = True
        packet["policy"]["tauri_packaged_runtime_launch_review_is_not_production_completion"] = True
        packet["call_ledger"] = packet["call_ledger"] + [
            row for row in persisted_launch_review_packet.get("call_ledger", []) if isinstance(row, dict)
        ]
        packet["warnings"].append(
            "tauri_packaged_runtime_launch_review 只记录显式本地 .app 启动 smoke；不等于离线 UX、配置/日志、签名/公证或 production package 完成。"
        )
    persisted_offline_review_packet = _read_tauri_backend_offline_packaged_ux_review_packet()
    persisted_offline_review = _safe_persisted_tauri_backend_offline_packaged_ux_review(
        persisted_offline_review_packet
    )
    if persisted_offline_review:
        packet["tauri_backend_offline_packaged_ux_review_contract"] = persisted_offline_review
        packet["tauri_backend_offline_packaged_ux_review_rows"] = list(persisted_offline_review.get("rows") or [])
        packet["tauri_backend_offline_packaged_ux_review_ready"] = True
        packet["counts"]["tauri_backend_offline_packaged_ux_review_row_count"] = persisted_offline_review.get(
            "row_count",
            0,
        )
        packet["counts"]["tauri_backend_offline_packaged_ux_review_blocking_count"] = persisted_offline_review.get(
            "blocking_review_count",
            0,
        )
        packet["runtime"]["tauri_backend_offline_packaged_ux_review_ready"] = True
        packet["runtime"]["tauri_backend_offline_packaged_ux_review_status"] = persisted_offline_review.get("status")
        packet["runtime"]["backend_offline_packaged_ux_verified"] = True
        packet["policy"]["tauri_backend_offline_packaged_ux_review_is_local"] = True
        packet["policy"]["tauri_backend_offline_packaged_ux_review_is_not_build"] = True
        packet["policy"]["tauri_backend_offline_packaged_ux_review_is_not_backend_start"] = True
        packet["policy"]["tauri_backend_offline_packaged_ux_review_is_not_production_completion"] = True
        packet["call_ledger"] = packet["call_ledger"] + [
            row for row in persisted_offline_review_packet.get("call_ledger", []) if isinstance(row, dict)
        ]
        packet["warnings"].append(
            "tauri_backend_offline_packaged_ux_review 只记录显式本地 packaged offline UX 观察；不等于 backend startup、配置/日志、签名/公证或 production package 完成。"
        )
    persisted_startup_review_packet = _read_tauri_backend_startup_runtime_review_packet()
    persisted_startup_review = _safe_persisted_tauri_backend_startup_runtime_review(persisted_startup_review_packet)
    if persisted_startup_review:
        packet["tauri_backend_startup_runtime_review_contract"] = persisted_startup_review
        packet["tauri_backend_startup_runtime_review_rows"] = list(persisted_startup_review.get("rows") or [])
        packet["tauri_backend_startup_runtime_review_ready"] = True
        packet["counts"]["tauri_backend_startup_runtime_review_row_count"] = persisted_startup_review.get(
            "row_count",
            0,
        )
        packet["counts"]["tauri_backend_startup_runtime_review_blocking_count"] = persisted_startup_review.get(
            "blocking_review_count",
            0,
        )
        packet["runtime"]["tauri_backend_startup_runtime_review_ready"] = True
        packet["runtime"]["tauri_backend_startup_runtime_review_status"] = persisted_startup_review.get("status")
        packet["runtime"]["backend_startup_runtime_validated"] = True
        packet["policy"]["tauri_backend_startup_runtime_review_is_local"] = True
        packet["policy"]["tauri_backend_startup_runtime_review_is_not_build"] = True
        packet["policy"]["tauri_backend_startup_runtime_review_did_not_start_fastapi"] = True
        packet["policy"]["tauri_backend_startup_runtime_review_is_not_production_completion"] = True
        packet["call_ledger"] = packet["call_ledger"] + [
            row for row in persisted_startup_review_packet.get("call_ledger", []) if isinstance(row, dict)
        ]
        packet["warnings"].append(
            "tauri_backend_startup_runtime_review 只记录显式本地 manual FastAPI packaged runtime 观察；不等于 sidecar/autostart、配置/日志、签名/公证或 production package 完成。"
        )
    return _json_safe(packet)


def run_tauri_package_artifact_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, dict) else {}
    explicit_tauri_build_completed = payload_map.get("explicit_tauri_build_completed") is True
    requested_command = str(payload_map.get("build_command") or "").strip()
    build_command_reviewed_safe = requested_command if requested_command in {
        "npm run tauri build",
        "cd desktop && npm run tauri build",
    } else ("npm run tauri build" if explicit_tauri_build_completed else "")
    task = create_task_record(
        TAURI_PACKAGE_ARTIFACT_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="tauri_package_artifact_review_queued",
        warnings=[
            "Tauri package artifact review 只读取本地 ignored release binary；不会运行 npm/cargo/Tauri。",
            "review 结果只代表本地 release binary artifact QA；不代表 packaged runtime、签名/公证或 production package 完成。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_tauri_release_binary_artifact",
    )
    packet = read_desktop_shell_preflight_cache()
    reviewed_at = _now_iso()
    review_contract = _tauri_package_artifact_review_contract(
        tauri_build_artifact=packet.get("tauri_build_artifact", {}),
        packaged_runtime_qa_contract=packet.get("packaged_runtime_qa_contract", {}),
        explicit_review=True,
        explicit_tauri_build_completed=explicit_tauri_build_completed,
        build_command_reviewed_safe=build_command_reviewed_safe,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    ledger = _tauri_package_artifact_review_call_ledger(review_contract, reviewed_at)
    _write_tauri_package_artifact_review_packet(
        review_contract=review_contract,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="tauri_package_artifact_review_ready"
        if review_contract["local_release_binary_artifact_review_ready"]
        else "tauri_package_artifact_review_pending",
        call_ledger=ledger,
        warning="tauri_package_artifact_review_completed_no_build_no_runtime_no_external_call",
    ) or task


def run_tauri_packaged_runtime_launch_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, dict) else {}
    explicit_launch_completed = payload_map.get("explicit_packaged_app_launch_completed") is True
    process_observed = payload_map.get("app_process_observed_after_launch") is True
    requested_command = str(payload_map.get("launch_command") or "").strip()
    launch_command_reviewed_safe = requested_command if requested_command in {
        "open -n desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app",
        "open desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app",
    } else ""
    observed_process_name = str(payload_map.get("observed_process_name") or "").strip()[:120]
    task = create_task_record(
        TAURI_PACKAGED_RUNTIME_LAUNCH_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="tauri_packaged_runtime_launch_review_queued",
        warnings=[
            "Tauri packaged runtime launch review 只记录用户/测试已显式执行的本地 .app 启动 smoke。",
            "review 不运行 npm/cargo/Tauri、不启动 FastAPI、不读取配置、不写日志、不调用 provider/model/GitHub、不交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_tauri_packaged_app_launch_evidence",
    )
    packet = read_desktop_shell_preflight_cache()
    reviewed_at = _now_iso()
    review_contract = _tauri_packaged_runtime_launch_review_contract(
        tauri_build_artifact=packet.get("tauri_build_artifact", {}),
        explicit_review=True,
        explicit_packaged_app_launch_completed=explicit_launch_completed,
        app_process_observed_after_launch=process_observed,
        launch_command_reviewed_safe=launch_command_reviewed_safe,
        observed_process_name=observed_process_name,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    ledger = _tauri_packaged_runtime_launch_review_call_ledger(review_contract, reviewed_at)
    _write_tauri_packaged_runtime_launch_review_packet(
        review_contract=review_contract,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="tauri_packaged_runtime_launch_review_ready"
        if review_contract["local_packaged_app_launch_review_ready"]
        else "tauri_packaged_runtime_launch_review_pending",
        call_ledger=ledger,
        warning="tauri_packaged_runtime_launch_review_completed_no_build_no_backend_no_external_call",
    ) or task


def run_tauri_backend_offline_packaged_ux_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, dict) else {}
    screenshot_sha256 = str(payload_map.get("screenshot_sha256") or "").strip().lower()
    observed_route = str(payload_map.get("observed_route") or "").strip()
    task = create_task_record(
        TAURI_BACKEND_OFFLINE_PACKAGED_UX_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="tauri_backend_offline_packaged_ux_review_queued",
        warnings=[
            "Tauri backend offline packaged UX review 只记录用户/测试已显式观察到的本地 .app 离线提示。",
            "review 不运行 npm/cargo/Tauri、不启动 FastAPI、不读取配置、不写日志、不调用 provider/model/GitHub、不交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_tauri_backend_offline_packaged_ux_evidence",
    )
    packet = read_desktop_shell_preflight_cache()
    reviewed_at = _now_iso()
    review_contract = _tauri_backend_offline_packaged_ux_review_contract(
        tauri_build_artifact=packet.get("tauri_build_artifact", {}),
        launch_review=packet.get("tauri_packaged_runtime_launch_review_contract", {}),
        backend_offline_ux_contract=packet.get("backend_offline_ux_contract", {}),
        explicit_review=True,
        explicit_packaged_app_launch_completed=payload_map.get("explicit_packaged_app_launch_completed") is True,
        backend_was_offline_during_review=payload_map.get("backend_was_offline_during_review") is True,
        offline_notice_observed=payload_map.get("offline_notice_observed") is True,
        fastapi_guidance_visible=payload_map.get("fastapi_guidance_visible") is True,
        local_only_boundary_visible=payload_map.get("local_only_boundary_visible") is True,
        no_provider_model_github_trade_visible=payload_map.get("no_provider_model_github_trade_visible") is True,
        screenshot_sha256=screenshot_sha256,
        observed_route=observed_route,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    ledger = _tauri_backend_offline_packaged_ux_review_call_ledger(review_contract, reviewed_at)
    _write_tauri_backend_offline_packaged_ux_review_packet(
        review_contract=review_contract,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="tauri_backend_offline_packaged_ux_review_ready"
        if review_contract["local_backend_offline_packaged_ux_review_ready"]
        else "tauri_backend_offline_packaged_ux_review_pending",
        call_ledger=ledger,
        warning="tauri_backend_offline_packaged_ux_review_completed_no_build_no_backend_no_external_call",
    ) or task


def run_tauri_backend_startup_runtime_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, dict) else {}
    screenshot_sha256 = str(payload_map.get("screenshot_sha256") or "").strip().lower()
    api_base_observed = str(payload_map.get("api_base_observed") or "").strip().rstrip("/")
    health_status_observed = str(payload_map.get("health_status_observed") or "").strip().lower()
    task = create_task_record(
        TAURI_BACKEND_STARTUP_RUNTIME_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="tauri_backend_startup_runtime_review_queued",
        warnings=[
            "Tauri backend startup runtime review 只记录用户/测试已显式观察到的 manual FastAPI packaged runtime 连接。",
            "review 不运行 npm/cargo/Tauri、不启动 FastAPI、不读取配置、不写日志、不调用 provider/model/GitHub、不交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_tauri_backend_startup_runtime_evidence",
    )
    packet = read_desktop_shell_preflight_cache()
    reviewed_at = _now_iso()
    review_contract = _tauri_backend_startup_runtime_review_contract(
        tauri_build_artifact=packet.get("tauri_build_artifact", {}),
        launch_review=packet.get("tauri_packaged_runtime_launch_review_contract", {}),
        offline_ux_review=packet.get("tauri_backend_offline_packaged_ux_review_contract", {}),
        explicit_review=True,
        explicit_packaged_app_launch_completed=payload_map.get("explicit_packaged_app_launch_completed") is True,
        manual_fastapi_started_before_review=payload_map.get("manual_fastapi_started_before_review") is True,
        fastapi_health_observed_ok=payload_map.get("fastapi_health_observed_ok") is True,
        packaged_app_fastapi_online_observed=payload_map.get("packaged_app_fastapi_online_observed") is True,
        api_base_observed=api_base_observed,
        health_status_observed=health_status_observed,
        screenshot_sha256=screenshot_sha256,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    ledger = _tauri_backend_startup_runtime_review_call_ledger(review_contract, reviewed_at)
    _write_tauri_backend_startup_runtime_review_packet(
        review_contract=review_contract,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="tauri_backend_startup_runtime_review_ready"
        if review_contract["local_backend_startup_runtime_review_ready"]
        else "tauri_backend_startup_runtime_review_pending",
        call_ledger=ledger,
        warning="tauri_backend_startup_runtime_review_completed_no_build_no_backend_no_external_call",
    ) or task
