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
TAURI_CONFIG_LOG_RUNTIME_REVIEW_PACKET_KEY = "command_center_3_tauri_config_log_runtime_review_packet"
TAURI_CONFIG_LOG_RUNTIME_REVIEW_TASK_TYPE = "run_tauri_config_log_runtime_review"
TAURI_SIGNING_NOTARIZATION_REVIEW_PACKET_KEY = "command_center_3_tauri_signing_notarization_review_packet"
TAURI_SIGNING_NOTARIZATION_REVIEW_TASK_TYPE = "run_tauri_signing_notarization_review"
TAURI_PRODUCTION_PACKAGE_PROMOTION_REVIEW_PACKET_KEY = (
    "command_center_3_tauri_production_package_promotion_review_packet"
)
TAURI_PRODUCTION_PACKAGE_PROMOTION_REVIEW_TASK_TYPE = "run_tauri_production_package_promotion_review"
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
    bundle_dmg_candidates = []
    for root in (bundle_dmg_root, bundle_app_root):
        if root.exists():
            bundle_dmg_candidates.extend(path for path in root.glob("*.dmg") if path.is_file())
    bundle_dmg_paths = sorted(path for path in bundle_dmg_candidates if not path.name.startswith("rw."))
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
        "P0: local one-click launcher starts/checks FastAPI and React/Vite before opening the page.",
        "Link check: launcher verifies",
        "/api/bootstrap/status before opening the page.",
        "Health check: /health must return stock-MING Command Center 3.0 JSON with external_calls_on_startup=false.",
        "Bootstrap check: /api/bootstrap/status must return command_center_3_bootstrap_runtime_mode_packet JSON before the page opens.",
        "Frontend check: Vite must serve stock-MING Command Center 3.0 index HTML before the page opens.",
        "command_center_health_ready",
        "wait_for_command_center_health",
        "bootstrap_status_ready",
        "wait_for_bootstrap_status",
        "vite_command_center_ready",
        "wait_for_vite_command_center",
        "command_center_3_bootstrap_runtime_mode_packet",
        "stock-MING Command Center 3.0",
        "external_calls_on_startup",
        "可操作诊断",
        "下一步：先关闭占用 8710/5173 的本地进程",
        "P0 success handoff: after readiness, open #candidates; typing stays silent; confirm button creates Tushare-first POST task; DeepSeek remains governed/skipped.",
        "Boundary: one-click startup only links local frontend/backend; it does not enable live_light/provider/model execution.",
        "scripts/dev_server.sh",
        "npm run dev",
        "VITE_API_BASE_URL",
        "STOCK_MING_ALLOW_SYSTEM_PYTHON",
        "desktop/node_modules",
        ".stock_ming_3/logs",
        "open \"$APP_URL\"",
        "COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY",
        "Check-only mode: resolved launcher configuration without starting FastAPI",
        "COMMAND_CENTER_3_LAUNCHER_SKIP_OPEN",
        "Browser open:",
        "Skip-open mode: FastAPI, bootstrap status, and React/Vite are ready",
        "STOCK_MING_FASTAPI_RELOAD=0",
        "no Tushare, DeepSeek, GitHub, or trading call",
    )
    required_installer_markers = (
        "Command Center 3.0 desktop shortcut installer",
        "start_command_center_3.command",
        "ln -sfn",
        "STOCK_MING_DESKTOP_DIR",
        "STOCK_MING_DESKTOP_SHORTCUT_NAME",
        "creates only a local symlink",
        "existing non-symlink target will not be overwritten",
        "desktop target already exists and is not a symlink",
        "Install verification: shortcut symlink points to the local launcher.",
        "Double-click checklist: launcher checks FastAPI /health, bootstrap status, and React/Vite before opening the page.",
        "shortcut install does not start FastAPI/Vite, create tasks, enable live_light, or execute trading",
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
        "status": "local_one_click_launcher_ready" if local_ready else "local_launcher_contract_blocked",
        "scope": "local_one_click_frontend_backend_launcher_not_production_package",
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
        "desktop_shortcut_installer_blocks_regular_file_overwrite": "existing non-symlink target will not be overwritten" in installer_source
        and "desktop target already exists and is not a symlink" in installer_source,
        "desktop_shortcut_installer_verifies_symlink_target": "Install verification: shortcut symlink points to the local launcher." in installer_source
        and "readlink \"$TARGET_PATH\"" in installer_source,
        "desktop_shortcut_installer_prints_double_click_checklist": "Double-click checklist: launcher checks FastAPI /health, bootstrap status, and React/Vite before opening the page." in installer_source,
        "desktop_shortcut_installer_safe_ordinary_label": "安全安装：不会覆盖同名普通文件；安装后验证 symlink 指向本地启动器；双击后才检查 FastAPI、bootstrap status 和 React/Vite。",
        "desktop_shortcut_installer_starts_services": False,
        "desktop_shortcut_installer_reads_credentials": False,
        "api_base": api_base,
        "vite_url": "http://127.0.0.1:5173",
        "uses_project_venv_first": "PROJECT_ROOT}/.venv/bin/python" in source,
        "allows_system_python_only_when_explicit": "STOCK_MING_ALLOW_SYSTEM_PYTHON" in source,
        "requires_node_modules": "desktop/node_modules" in source,
        "starts_fastapi_when_user_runs": "scripts/dev_server.sh" in source,
        "one_click_fastapi_reload_disabled": "STOCK_MING_FASTAPI_RELOAD=0" in source,
        "starts_vite_when_user_runs": "npm run dev" in source,
        "opens_local_browser_when_user_runs": 'open "$APP_URL"' in source,
        "check_only_mode_supported": "COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY" in source
        and "Check-only mode: resolved launcher configuration without starting FastAPI" in source,
        "check_only_mode_starts_services": False,
        "check_only_mode_probes_urls": False,
        "check_only_mode_opens_browser": False,
        "skip_open_mode_supported": "COMMAND_CENTER_3_LAUNCHER_SKIP_OPEN" in source
        and "Skip-open mode: FastAPI, bootstrap status, and React/Vite are ready" in source,
        "skip_open_waits_for_frontend_backend_ready": "wait_for_command_center_health" in source
        and "wait_for_bootstrap_status" in source
        and "wait_for_vite_command_center" in source,
        "skip_open_mode_opens_browser": False,
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
        "note": "This contract exposes the P0 local one-click Command Center 3.0 launcher. It does not run the launcher from GET cache, does not enable provider/model execution, and is not Tauri production package evidence.",
    }


def _one_click_startup_summary(
    api_base_info: dict[str, Any],
    desktop_launcher_contract: dict[str, Any],
) -> dict[str, Any]:
    launcher_source = _read_source_safe(COMMAND_CENTER_3_LAUNCHER)
    client_source = _read_source_safe(FRONTEND_API_CLIENT)
    offline_notice_source = _read_source_safe(FRONTEND_BACKEND_OFFLINE_NOTICE)
    node_modules_present = (DESKTOP_ROOT / "node_modules").exists()

    def row(
        criterion: str,
        passed: bool,
        evidence: str,
        *,
        user_visible: bool = True,
        blocker: bool | None = None,
    ) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": "passed" if passed else "blocked",
            "passed": bool(passed),
            "user_visible": bool(user_visible),
            "blocker": (not passed) if blocker is None else bool(blocker),
            "evidence": evidence,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    health_identity_ready = (
        'if wait_for_command_center_health "FastAPI" "${API_BASE%/}/health" 40; then'
        in launcher_source
        and "command_center_health_ready" in launcher_source
        and 'data.get("service") != "stock-MING Command Center 3.0"' in launcher_source
        and 'data.get("external_calls_on_startup") is not False' in launcher_source
    )
    api_status_wait_ready = (
        'if wait_for_bootstrap_status "${API_BASE%/}/api/bootstrap/status" 40; then'
        in launcher_source
        and "command_center_3_bootstrap_runtime_mode_packet" in launcher_source
        and "command_center_bootstrap_runtime_mode.v1" in launcher_source
    )
    vite_identity_ready = (
        'if wait_for_vite_command_center "$VITE_URL" 40; then' in launcher_source
        and "vite_command_center_ready" in launcher_source
        and "stock-MING Command Center 3.0" in launcher_source
        and "/src/main.tsx" in launcher_source
    )
    startup_diagnostics_visible = (
        "print_startup_diagnostics" in launcher_source
        and "FastAPI：${API_BASE%/}/health 未返回 Command Center 3.0 健康 JSON" in launcher_source
        and "Bootstrap status：${API_BASE%/}/api/bootstrap/status 未返回 runtime-mode packet" in launcher_source
        and "React/Vite：${VITE_URL} 未返回 Command Center 3.0 前端 HTML" in launcher_source
        and "下一步：先关闭占用 8710/5173 的本地进程" in launcher_source
    )
    open_is_gated = (
        'if [ "$FASTAPI_READY" != "1" ] || [ "$API_STATUS_READY" != "1" ] || [ "$VITE_READY" != "1" ]; then'
        in launcher_source
        and 'open "$APP_URL"' in launcher_source
    )
    success_handoff_visible = (
        "P0 success handoff: after readiness, open #candidates; typing stays silent; confirm button creates Tushare-first POST task; DeepSeek remains governed/skipped."
        in launcher_source
    )
    frontend_api_client_local = "http://127.0.0.1:8710" in client_source and bool(api_base_info.get("is_localhost"))
    offline_notice_ready = (
        FRONTEND_BACKEND_OFFLINE_NOTICE.exists()
        and "BACKEND_OFFLINE_ERROR" in offline_notice_source
        and "backend_offline_or_unreachable" in client_source
    )
    rows = [
        row(
            "local_one_click_launcher_ready",
            desktop_launcher_contract.get("status") == "local_one_click_launcher_ready"
            and desktop_launcher_contract.get("launcher_executable") is True,
            f"{desktop_launcher_contract.get('launcher_path')} executable={desktop_launcher_contract.get('launcher_executable')}",
        ),
        row(
            "frontend_dependencies_present",
            node_modules_present,
            "desktop/node_modules present; launcher will stop with a clear message if missing",
        ),
        row(
            "fastapi_health_wait_before_open",
            health_identity_ready,
            f"{_path_label(COMMAND_CENTER_3_LAUNCHER)} waits for {api_base_info.get('expected_health_endpoint')} to return stock-MING Command Center 3.0 health JSON with external_calls_on_startup=false",
        ),
        row(
            "fastapi_status_api_wait_before_open",
            api_status_wait_ready,
            f"{_path_label(COMMAND_CENTER_3_LAUNCHER)} validates {api_base_info.get('api_base')}/api/bootstrap/status as command_center_3_bootstrap_runtime_mode_packet JSON",
        ),
        row(
            "vite_wait_before_open",
            vite_identity_ready,
            f"{_path_label(COMMAND_CENTER_3_LAUNCHER)} waits for http://127.0.0.1:5173 to serve stock-MING Command Center 3.0 index HTML",
        ),
        row(
            "startup_failure_diagnostics_visible",
            startup_diagnostics_visible,
            "launcher prints separate FastAPI, bootstrap status, and React/Vite diagnostics with 8710/5173 recovery guidance",
        ),
        row(
            "browser_opens_only_after_frontend_backend_ready",
            open_is_gated,
            "launcher exits before opening the page when FastAPI or Vite is not ready",
        ),
        row(
            "p0_success_handoff_to_p1_confirm_visible",
            success_handoff_visible,
            "launcher prints the next ordinary action after readiness: open #candidates, type silently, confirm to create the Tushare-first POST task, and keep DeepSeek governed/skipped",
        ),
        row(
            "frontend_api_client_uses_local_fastapi",
            frontend_api_client_local,
            f"API base={api_base_info.get('api_base')}; frontend uses FastAPI client only",
        ),
        row(
            "backend_offline_notice_available",
            offline_notice_ready,
            "frontend has a local backend-offline notice for unreachable FastAPI",
            blocker=False,
        ),
        row(
            "get_preflight_cache_does_not_start_services",
            True,
            "GET /api/desktop/preflight-cache only reports launcher state; user-run launcher starts services",
        ),
        row(
            "provider_model_trading_boundary_preserved",
            True,
            "one-click startup links local FastAPI/Vite only; no Tushare, DeepSeek, GitHub, or trading call",
        ),
    ]
    ordinary_recovery_steps = [
        {
            "step": "1",
            "title": "打开本地一键入口",
            "when": "页面未打开、健康页显示 check，或本地后端离线",
            "action": "双击 stock-MING Command Center 3.command；或运行 scripts/start_command_center_3.command。",
            "checks": "启动器会依次等待 FastAPI /health、/api/bootstrap/status 和 React/Vite HTML。",
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "step": "2",
            "title": "按启动器诊断定位失败段",
            "when": "启动器没有自动打开页面",
            "action": "先看 FastAPI、bootstrap status、React/Vite 哪一段没有 ready。",
            "checks": "对应检查 8710/5173 端口占用和 .stock_ming_3/logs 下的 fastapi/vite 日志。",
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "step": "3",
            "title": "刷新健康页确认联通",
            "when": "启动器显示三个检查都 ready 后",
            "action": "回到系统健康页，确认 P0 front/back、P0 receipt 和 one-click launcher 都为 ready。",
            "checks": "本页只读 GET /health 与 GET /api/desktop/preflight-cache，不创建 task。",
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
    ]
    blockers = [item["criterion"] for item in rows if item["blocker"] and not item["passed"]]
    ready = not blockers
    return {
        "schema_version": "command_center_3_one_click_startup_summary.v1",
        "priority": "P0",
        "status": "one_click_frontend_backend_ready" if ready else "one_click_frontend_backend_blocked",
        "scope": "ordinary_user_local_startup_and_frontend_backend_connection",
        "headline": "一键启动会启动或复用本地 FastAPI 与 React/Vite，并在后端状态 API 与页面都联通后打开页面。",
        "what_user_should_click_next": "双击 stock-MING Command Center 3.command；或运行 scripts/start_command_center_3.command。",
        "success_condition": "FastAPI /health 必须返回 Command Center 3.0 健康 JSON，/api/bootstrap/status 必须返回 runtime-mode packet，React/Vite 必须返回 Command Center 3.0 前端 HTML 后才打开页面。",
        "blocked_next_action": "若未打开页面，先看启动器的可操作诊断：FastAPI、bootstrap status、React/Vite 哪段失败；再检查 8710/5173 是否被占用，或查看 .stock_ming_3/logs/command_center_3_fastapi.log 与 command_center_3_vite.log。",
        "diagnostic_surfaces": [
            "FastAPI /health Command Center 3.0 JSON",
            "bootstrap status runtime-mode packet",
            "React/Vite Command Center 3.0 HTML",
            "8710/5173 port occupancy guidance",
        ],
        "safe_fallback_path": "后端离线时页面显示本地离线提示；GET preflight 只读展示状态。",
        "success_handoff_visible": success_handoff_visible,
        "success_handoff_label": "联通成功后打开下一票雷达，输入股票代码；只有确认按钮创建 Tushare-first POST task，DeepSeek 保持 governed/skipped。",
        "success_handoff_href": "#candidates",
        "success_handoff_boundary": "启动器和预检页只暴露下一步；页面切换和输入不外联，确认按钮才进入 P1 task。",
        "ordinary_recovery_steps": ordinary_recovery_steps,
        "ordinary_recovery_step_count": len(ordinary_recovery_steps),
        "ordinary_recovery_steps_are_read_only": True,
        "ordinary_recovery_steps_create_task": False,
        "launcher_path": desktop_launcher_contract.get("launcher_path"),
        "desktop_shortcut_target_name": desktop_launcher_contract.get("desktop_shortcut_target_name"),
        "api_health_endpoint": api_base_info.get("expected_health_endpoint"),
        "vite_url": desktop_launcher_contract.get("vite_url"),
        "frontend_backend_connection_ready": ready,
        "launcher_ready": desktop_launcher_contract.get("status") == "local_one_click_launcher_ready",
        "launcher_executable": desktop_launcher_contract.get("launcher_executable") is True,
        "frontend_dependencies_present": node_modules_present,
        "fastapi_health_wait_before_open": health_identity_ready,
        "fastapi_health_identity_validated_before_open": health_identity_ready,
        "fastapi_status_api_wait_before_open": api_status_wait_ready,
        "fastapi_bootstrap_status_json_validated_before_open": api_status_wait_ready,
        "vite_wait_before_open": vite_identity_ready,
        "vite_frontend_identity_validated_before_open": vite_identity_ready,
        "startup_failure_diagnostics_visible": startup_diagnostics_visible,
        "browser_opens_only_after_frontend_backend_ready": open_is_gated,
        "frontend_api_client_uses_local_fastapi": frontend_api_client_local,
        "backend_offline_notice_available": offline_notice_ready,
        "starts_fastapi_when_user_runs": desktop_launcher_contract.get("starts_fastapi_when_user_runs") is True,
        "one_click_fastapi_reload_disabled": desktop_launcher_contract.get("one_click_fastapi_reload_disabled") is True,
        "starts_vite_when_user_runs": desktop_launcher_contract.get("starts_vite_when_user_runs") is True,
        "opens_local_browser_when_user_runs": desktop_launcher_contract.get("opens_local_browser_when_user_runs") is True,
        "check_only_mode_supported": desktop_launcher_contract.get("check_only_mode_supported") is True,
        "check_only_mode_starts_services": False,
        "check_only_mode_probes_urls": False,
        "check_only_mode_opens_browser": False,
        "skip_open_mode_supported": desktop_launcher_contract.get("skip_open_mode_supported") is True,
        "skip_open_waits_for_frontend_backend_ready": desktop_launcher_contract.get("skip_open_waits_for_frontend_backend_ready") is True,
        "skip_open_mode_opens_browser": False,
        "get_preflight_cache_starts_services": False,
        "react_render_starts_services": False,
        "search_typing_starts_services": False,
        "production_package_complete": False,
        "provider_model_execution_enabled": False,
        "deepseek_governed_executor_required_before_real_call": True,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "loads_token_or_key": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "row_count": len(rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "call_ledger": [
            {
                "api": "local_one_click_startup_summary",
                "source": f"{_path_label(COMMAND_CENTER_3_LAUNCHER)}; {_path_label(FRONTEND_API_CLIENT)}",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_startup_summary_read",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
    }


def _p0_local_connection_receipt(
    one_click_startup_summary: dict[str, Any],
    desktop_launcher_contract: dict[str, Any],
) -> dict[str, Any]:
    def row(criterion: str, passed: bool, evidence: str) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": "passed" if passed else "blocked",
            "passed": bool(passed),
            "ordinary_user_visible": True,
            "evidence": evidence,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    rows = [
        row(
            "user_run_launcher_entry_visible",
            bool(one_click_startup_summary.get("what_user_should_click_next"))
            and bool(desktop_launcher_contract.get("launcher_executable")),
            str(one_click_startup_summary.get("what_user_should_click_next") or ""),
        ),
        row(
            "fastapi_health_gate_before_page_open",
            one_click_startup_summary.get("fastapi_health_identity_validated_before_open") is True,
            str(one_click_startup_summary.get("api_health_endpoint") or ""),
        ),
        row(
            "bootstrap_status_gate_before_page_open",
            one_click_startup_summary.get("fastapi_bootstrap_status_json_validated_before_open") is True,
            "GET /api/bootstrap/status returns command_center_3_bootstrap_runtime_mode_packet before opening the page",
        ),
        row(
            "vite_frontend_gate_before_page_open",
            one_click_startup_summary.get("vite_frontend_identity_validated_before_open") is True,
            str(one_click_startup_summary.get("vite_url") or ""),
        ),
        row(
            "browser_open_is_gated_by_all_three_checks",
            one_click_startup_summary.get("browser_opens_only_after_frontend_backend_ready") is True,
            "launcher exits before opening the page when FastAPI health, bootstrap status, or Vite identity is not ready",
        ),
        row(
            "ordinary_recovery_guidance_visible",
            bool(one_click_startup_summary.get("blocked_next_action"))
            and bool(one_click_startup_summary.get("diagnostic_surfaces")),
            str(one_click_startup_summary.get("blocked_next_action") or ""),
        ),
        row(
            "get_cache_and_react_render_remain_read_only",
            one_click_startup_summary.get("get_preflight_cache_starts_services") is False
            and one_click_startup_summary.get("react_render_starts_services") is False,
            "GET /api/desktop/preflight-cache and React render only display this receipt; the launcher runs only when the user opens it",
        ),
        row(
            "provider_model_and_trade_boundary_preserved",
            one_click_startup_summary.get("external_calls_triggered") is False
            and one_click_startup_summary.get("tushare_called") is False
            and one_click_startup_summary.get("deepseek_called") is False
            and one_click_startup_summary.get("github_called") is False
            and one_click_startup_summary.get("does_not_execute_trades") is True,
            "P0 startup links local FastAPI/Vite only; provider/model execution and real trading stay gated elsewhere",
        ),
    ]
    blockers = [item["criterion"] for item in rows if not item["passed"]]
    ready = not blockers
    return {
        "schema_version": "command_center_3_p0_local_connection_receipt.v1",
        "priority": "P0",
        "status": "p0_local_connection_receipt_ready" if ready else "p0_local_connection_receipt_blocked",
        "scope": "user_run_launcher_frontend_backend_connection_receipt",
        "ordinary_label": "本地一键入口会先确认 FastAPI、bootstrap status 和 React/Vite 都就绪，再打开页面。",
        "what_user_clicks": one_click_startup_summary.get("what_user_should_click_next"),
        "success_condition": one_click_startup_summary.get("success_condition"),
        "blocked_next_action": one_click_startup_summary.get("blocked_next_action"),
        "diagnostic_surfaces": one_click_startup_summary.get("diagnostic_surfaces"),
        "success_handoff_visible": one_click_startup_summary.get("success_handoff_visible") is True,
        "success_handoff_label": one_click_startup_summary.get("success_handoff_label"),
        "success_handoff_href": one_click_startup_summary.get("success_handoff_href"),
        "success_handoff_boundary": one_click_startup_summary.get("success_handoff_boundary"),
        "ordinary_recovery_steps": one_click_startup_summary.get("ordinary_recovery_steps"),
        "ordinary_recovery_step_count": one_click_startup_summary.get("ordinary_recovery_step_count"),
        "ordinary_recovery_steps_are_read_only": True,
        "ordinary_recovery_steps_create_task": False,
        "connection_contract_ready": ready,
        "current_runtime_live_connection_verified": False,
        "current_runtime_probe_executed_by_get_cache": False,
        "frontend_backend_connection_ready_when_user_runs_launcher": ready,
        "launcher_user_run_only": True,
        "get_cache_starts_services": False,
        "react_render_starts_services": False,
        "search_typing_starts_services": False,
        "post_task_created": False,
        "provider_model_execution_enabled": False,
        "production_package_complete": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "loads_token_or_key": False,
        "contains_secret": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "rows": rows,
        "row_count": len(rows),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "call_ledger": [
            {
                "api": "local_p0_frontend_backend_connection_receipt",
                "source": "one_click_startup_summary and desktop_launcher_contract",
                "row_count": len(rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_connection_receipt_read",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "note": "This is a local P0 startup receipt. It does not probe the live runtime from GET cache and does not enable live_light/provider/model/trading execution.",
    }


def _p0_ordinary_connection_rows(one_click_startup_summary: dict[str, Any]) -> list[dict[str, Any]]:
    def row(
        segment: str,
        ready: bool,
        user_next_action: str,
        success_condition: str,
        failed_next_action: str,
        boundary: str,
    ) -> dict[str, Any]:
        return {
            "环节": segment,
            "当前状态": "ready" if ready else "check",
            "用户下一步": user_next_action,
            "通过条件": success_condition,
            "失败下一步": failed_next_action,
            "边界": boundary,
            "ordinary_user_visible": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    return [
        row(
            "FastAPI",
            one_click_startup_summary.get("fastapi_health_identity_validated_before_open") is True,
            "如果未 ready，先看启动器 FastAPI 诊断和 command_center_3_fastapi.log。",
            "本地 /health 返回 Command Center 3.0 JSON，且 external_calls_on_startup=false。",
            "检查 8710 是否被占用；必要时重新运行 scripts/start_command_center_3.command。",
            "只读健康检查；GET preflight 不启动 FastAPI、不创建 task。",
        ),
        row(
            "Bootstrap status",
            one_click_startup_summary.get("fastapi_bootstrap_status_json_validated_before_open") is True,
            "如果未 ready，回启动器确认 bootstrap status 段是否返回 runtime-mode packet。",
            "本地 /api/bootstrap/status 返回 command_center_3_bootstrap_runtime_mode_packet。",
            "查看 FastAPI 日志，确认后端是 Command Center 3.0 且 runtime-mode cache 可读。",
            "只读运行模式；不写配置、不启用 live_light。",
        ),
        row(
            "React/Vite",
            one_click_startup_summary.get("vite_frontend_identity_validated_before_open") is True,
            "如果未 ready，检查 5173 是否被占用并查看 command_center_3_vite.log。",
            "本地 Vite 返回 Command Center 3.0 前端 HTML。",
            "关闭旧 dev server 后重新运行一键启动器，或用 skip-open 模式做联通验收。",
            "只读前端入口；不调用 Tushare/DeepSeek/GitHub、不执行真实交易。",
        ),
    ]


def _p0_failure_diagnostic_rows(one_click_startup_summary: dict[str, Any]) -> list[dict[str, Any]]:
    def row(
        segment: str,
        ready: bool,
        how_to_read: str,
        user_action: str,
        log_or_port: str,
        boundary: str,
    ) -> dict[str, Any]:
        return {
            "失败段": segment,
            "当前状态": "ready" if ready else "check",
            "怎么判断": how_to_read,
            "用户动作": user_action,
            "日志/端口": log_or_port,
            "边界": boundary,
            "ordinary_user_visible": True,
            "cache_only_readback": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    return [
        row(
            "FastAPI /health",
            one_click_startup_summary.get("fastapi_health_identity_validated_before_open") is True,
            "启动器必须看到 Command Center 3.0 health JSON，且 external_calls_on_startup=false。",
            "如果这里 check，先看 FastAPI 日志，再检查 8710 是否被占用。",
            ".stock_ming_3/logs/command_center_3_fastapi.log / 8710",
            "只读诊断；GET preflight 和 React render 不启动 FastAPI、不创建 task。",
        ),
        row(
            "Bootstrap status",
            one_click_startup_summary.get("fastapi_bootstrap_status_json_validated_before_open") is True,
            "启动器必须看到 /api/bootstrap/status 返回 command_center_3_bootstrap_runtime_mode_packet。",
            "如果这里 check，说明后端已到 health 但 runtime-mode packet 未就绪，继续看 FastAPI 日志中的 bootstrap status 段。",
            ".stock_ming_3/logs/command_center_3_fastapi.log / /api/bootstrap/status",
            "只读运行模式诊断；不写配置、不启用 live_light、不调用 provider/model。",
        ),
        row(
            "React/Vite HTML",
            one_click_startup_summary.get("vite_frontend_identity_validated_before_open") is True,
            "启动器必须看到 Vite 返回 Command Center 3.0 前端 HTML。",
            "如果这里 check，先看 Vite 日志，再检查 5173 是否被旧 dev server 占用。",
            ".stock_ming_3/logs/command_center_3_vite.log / 5173",
            "只读前端入口诊断；不调用 Tushare、DeepSeek、GitHub、不执行真实交易。",
        ),
        row(
            "端口和日志指引",
            one_click_startup_summary.get("startup_failure_diagnostics_visible") is True,
            "启动器失败时必须打印 FastAPI、Bootstrap status、React/Vite 和 8710/5173 指引。",
            "按启动器输出关闭占用进程，或重新运行 scripts/start_command_center_3.command。",
            "8710 / 5173 / .stock_ming_3/logs",
            "这只是失败定位清单；不启动服务、不创建 POST task、不外联。",
        ),
    ]


def _p0_post_startup_readback_rows(one_click_startup_summary: dict[str, Any]) -> list[dict[str, Any]]:
    ready = one_click_startup_summary.get("frontend_backend_connection_ready") is True
    status = "ready" if ready else "check"

    def row(
        item: str,
        page_view: str,
        success_condition: str,
        failed_next_action: str,
        boundary: str,
    ) -> dict[str, Any]:
        return {
            "复核项": item,
            "当前状态": status,
            "页面看法": page_view,
            "通过条件": success_condition,
            "失败下一步": failed_next_action,
            "边界": boundary,
            "ordinary_user_visible": True,
            "cache_only_readback": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    return [
        row(
            "FastAPI health",
            "系统健康和今日作战台显示本地前后端已联通。",
            "GET /health 返回 Command Center 3.0 JSON，且 external_calls_on_startup=false。",
            "回启动器日志看 FastAPI 诊断，再检查 8710 是否被占用。",
            "只读健康检查，不启动服务、不创建 task。",
        ),
        row(
            "Bootstrap status",
            "普通入口显示运行模式和启动边界。",
            "GET /api/bootstrap/status 返回 runtime-mode packet。",
            "回启动器日志看 bootstrap status 诊断。",
            "只读运行模式，不写配置、不启用 live_light。",
        ),
        row(
            "React/Vite 前端",
            "浏览器打开 Command Center 3.0 今日作战台。",
            "Vite 返回 Command Center 3.0 HTML，且页面入口可点击到预检、健康、雷达和量化推演。",
            "回启动器日志看 React/Vite 诊断，再检查 5173 是否被占用。",
            "只读前端入口，不调用 Tushare/DeepSeek/GitHub、不执行真实交易。",
        ),
    ]


def _p0_to_p1_ordinary_handoff_rows(one_click_startup_summary: dict[str, Any]) -> list[dict[str, Any]]:
    connection_ready = one_click_startup_summary.get("frontend_backend_connection_ready") is True
    return [
        {
            "步骤": "1. 确认本地联通",
            "用户动作": "先看 FastAPI、Bootstrap status、React/Vite 三段是否 ready。",
            "当前状态": "ready：可以进入普通投研入口" if connection_ready else "check：先恢复本地一键入口",
            "下一步": "打开下一票雷达，输入股票代码。" if connection_ready else "回到启动器诊断或桌面壳预检。",
            "边界": "只读 GET health / preflight cache；不启动服务、不创建 task。",
            "ordinary_user_visible": True,
            "cache_only_readback": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "步骤": "2. 进入下一票雷达",
            "用户动作": "去下一票雷达的搜票量化推演卡片。",
            "当前状态": "只读导航提示",
            "下一步": "输入 6 位 A 股代码或带后缀代码。",
            "边界": "页面切换和输入不会调用 Tushare、DeepSeek 或 GitHub。",
            "ordinary_user_visible": True,
            "cache_only_readback": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "步骤": "3. 点击确认并生成",
            "用户动作": "代码通过本地校验后点击确认按钮。",
            "当前状态": "确认按钮才是 P1 工作入口",
            "下一步": "看本地任务编号、TaskStatusPanel 和 cache 回放。",
            "边界": "只有确认按钮可创建 Tushare-first POST task / worker；DeepSeek skipped。",
            "ordinary_user_visible": True,
            "cache_only_readback": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
        {
            "步骤": "4. 回放本地结果",
            "用户动作": "任务完成后刷新本地 cache，再看股票量化推演和次日图谱。",
            "当前状态": "结果来自 cache / ledger / packet",
            "下一步": "按缺口和仅供研究边界复核。",
            "边界": "GET cache / React render 不补调外部数据源，不交易、不改 strategy action。",
            "ordinary_user_visible": True,
            "cache_only_readback": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        },
    ]


def _p0_ordinary_quick_action_rows(
    one_click_startup_summary: dict[str, Any],
    p0_to_p1_ordinary_handoff_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    connection_ready = one_click_startup_summary.get("frontend_backend_connection_ready") is True

    def row(
        quick_action: str,
        user_state: str,
        user_next_step: str,
        entry: str,
        boundary: str,
        handoff_step_index: int,
    ) -> dict[str, Any]:
        handoff_step = p0_to_p1_ordinary_handoff_rows[handoff_step_index]
        return {
            "快速行动": quick_action,
            "当前状态": user_state,
            "用户下一步": user_next_step,
            "入口": entry,
            "证据": handoff_step["步骤"],
            "边界": boundary,
            "source_handoff_step": handoff_step["步骤"],
            "ordinary_user_visible": True,
            "cache_only_readback": True,
            "creates_task_from_readback": False,
            "provider_model_called_from_readback": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "loads_token_or_key": False,
            "contains_secret": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }

    return [
        row(
            "1. 本地联通变绿",
            "ready：可以继续投研" if connection_ready else "check：先恢复本地联通",
            "进入下一票雷达" if connection_ready else "回一键启动预检看 FastAPI / bootstrap / React 哪段失败",
            "今日作战台摘要",
            "只读读取 GET /health、GET /api/bootstrap/status 和 GET /api/desktop/preflight-cache；不启动服务。",
            0,
        ),
        row(
            "2. 打开下一票雷达",
            "只读导航",
            "输入股票代码，先做本地格式校验",
            "下一票雷达",
            "页面切换和输入不会创建 task，也不会调用 Tushare、DeepSeek 或 GitHub。",
            1,
        ),
        row(
            "3. 确认并生成",
            "等待用户点击按钮",
            "点击确认按钮后才进入 Tushare-first POST task",
            "搜票量化推演卡片",
            "只有确认按钮可创建 P1 task；DeepSeek governed executor 完成前保持 skipped。",
            2,
        ),
        row(
            "4. 回放本地结果",
            "等待 cache / ledger / packet 回放",
            "看股票量化推演和次日图谱；缺证据继续显示 pending",
            "量化推演 / 次日图谱",
            "GET cache 和 React render 只回放本地结果；不交易、不改 strategy action。",
            3,
        ),
    ]


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
    artifact_review = (
        packet.get("tauri_package_artifact_review_contract")
        if isinstance(packet.get("tauri_package_artifact_review_contract"), dict)
        else {}
    )
    launch_review = (
        packet.get("tauri_packaged_runtime_launch_review_contract")
        if isinstance(packet.get("tauri_packaged_runtime_launch_review_contract"), dict)
        else {}
    )
    offline_ux_review = (
        packet.get("tauri_backend_offline_packaged_ux_review_contract")
        if isinstance(packet.get("tauri_backend_offline_packaged_ux_review_contract"), dict)
        else {}
    )
    startup_review = (
        packet.get("tauri_backend_startup_runtime_review_contract")
        if isinstance(packet.get("tauri_backend_startup_runtime_review_contract"), dict)
        else {}
    )
    config_log_review = (
        packet.get("tauri_config_log_runtime_review_contract")
        if isinstance(packet.get("tauri_config_log_runtime_review_contract"), dict)
        else {}
    )
    signing_review = (
        packet.get("tauri_signing_notarization_review_contract")
        if isinstance(packet.get("tauri_signing_notarization_review_contract"), dict)
        else {}
    )
    promotion_review = (
        packet.get("tauri_production_package_promotion_review_contract")
        if isinstance(packet.get("tauri_production_package_promotion_review_contract"), dict)
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
    artifact_review_ready = artifact_review.get("local_release_binary_artifact_review_ready") is True
    tauri_build_repeatability_done = artifact_review.get("tauri_build_repeatability_done") is True
    app_bundle_artifact_qa_done = bool(
        artifact_review_ready
        and artifact_review.get("app_bundle_artifact_qa_done") is True
        and build_artifact.get("packaged_app_bundle_detected") is True
    )
    dmg_distribution_artifact_qa_done = bool(
        artifact_review_ready
        and artifact_review.get("dmg_distribution_artifact_qa_done") is True
        and build_artifact.get("distribution_dmg_detected") is True
    )
    app_bundle_dmg_done = bool(app_bundle_artifact_qa_done and dmg_distribution_artifact_qa_done)
    packaged_app_launch_qa_done = launch_review.get("local_packaged_app_launch_review_ready") is True
    backend_startup_runtime_done = startup_review.get("backend_startup_runtime_validated") is True
    offline_packaged_ux_done = offline_ux_review.get("backend_offline_packaged_ux_verified") is True
    config_log_runtime_done = config_log_review.get("config_log_runtime_paths_validated") is True
    signing_notarization_review_done = signing_review.get("local_signing_notarization_review_ready") is True
    signing_notarization_done = signing_review.get("signing_notarization_done") is True
    production_package_complete = blocker_audit.get("package_ready") is True
    promotion_review_done = promotion_review.get("local_production_package_promotion_review_ready") is True
    durable_promotion_ready = promotion_review.get("durable_promotion_ready") is True

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
            evidence=(
                f"app_bundle_reviewed={app_bundle_artifact_qa_done}; "
                f"dmg_reviewed={dmg_distribution_artifact_qa_done}; "
                f"artifact_review_status={artifact_review.get('status') or 'missing'}"
            ),
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
            evidence=f"launch_review_status={launch_review.get('status') or 'missing'}",
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
            evidence=(
                f"strategy={runtime_contract.get('backend_startup_strategy')}; "
                f"startup_review_status={startup_review.get('status') or 'missing'}"
            ),
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
            evidence=(
                f"frontend_contract_ready={offline_ux.get('frontend_contract_ready')}; "
                f"offline_review_status={offline_ux_review.get('status') or 'missing'}"
            ),
            next_action="Open packaged runtime with backend offline and capture the friendly local-only UX evidence.",
            recommended_order=9,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "config_log_runtime_path_evidence_required",
            "durable_evidence",
            "completed" if config_log_runtime_done else "pending_config_log_runtime_path_evidence",
            passed=config_log_runtime_done,
            local_surface_required=False,
            production_blocker=not config_log_runtime_done,
            evidence=(
                f"config={runtime_contract.get('config_file_policy')}; log={runtime_contract.get('log_file_policy')}; "
                f"config_log_review_status={config_log_review.get('status') or 'missing'}"
            ),
            next_action="Validate runtime path behavior without reading config values or writing unsafe logs.",
            recommended_order=10,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "signing_notarization_review_required",
            "durable_evidence",
            (
                "completed"
                if signing_notarization_done
                else (
                    "reviewed_gap_evidence_production_signing_pending"
                    if signing_notarization_review_done
                    else "pending_signing_notarization_review"
                )
            ),
            passed=signing_notarization_done or signing_notarization_review_done,
            local_surface_required=False,
            production_blocker=not (signing_notarization_done or signing_notarization_review_done),
            evidence=(
                f"signing_review_status={signing_review.get('status') or 'missing'}; "
                f"production_signing_notarization_ready={signing_review.get('production_signing_notarization_ready') is True}"
            ),
            next_action="Complete or explicitly waive macOS signing/notarization and distribution review.",
            recommended_order=11,
        ),
        _tauri_package_durable_evidence_recipe_row(
            "production_package_promotion_review_required",
            "durable_evidence",
            (
                "completed"
                if durable_promotion_ready
                else (
                    "reviewed_promotion_blocked"
                    if promotion_review_done
                    else "pending_production_package_promotion_review"
                )
            ),
            passed=durable_promotion_ready,
            local_surface_required=False,
            production_blocker=not durable_promotion_ready,
            evidence=(
                f"promotion_review_status={promotion_review.get('status') or 'missing'}; "
                f"durable_promotion_ready={durable_promotion_ready}; "
                f"remaining_blockers={promotion_review.get('remaining_blockers') or []}; "
                f"package_ready={blocker_audit.get('package_ready')}"
            ),
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
        "durable_promotion_ready": durable_promotion_ready,
        "production_package_complete": False,
        "tauri_build_repeatability_done": tauri_build_repeatability_done,
        "app_bundle_artifact_qa_done": app_bundle_artifact_qa_done,
        "dmg_distribution_artifact_qa_done": dmg_distribution_artifact_qa_done,
        "app_bundle_dmg_qa_done": app_bundle_dmg_done,
        "packaged_app_launch_qa_done": packaged_app_launch_qa_done,
        "backend_startup_strategy_runtime_validated": backend_startup_runtime_done,
        "backend_offline_packaged_ux_verified": offline_packaged_ux_done,
        "config_log_runtime_paths_validated": config_log_runtime_done,
        "signing_notarization_review_done": signing_notarization_review_done,
        "signing_notarization_done": signing_notarization_done,
        "production_package_promotion_review_done": promotion_review_done,
        "production_package_promotion_review_status": promotion_review.get("status") or "",
        "production_package_promotion_remaining_blockers": list(
            promotion_review.get("remaining_blockers") or []
        ),
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


def _attach_tauri_package_durable_evidence_recipe(packet: dict[str, Any]) -> None:
    tauri_package_durable_evidence_recipe = _tauri_package_durable_evidence_recipe(packet)
    packet["tauri_package_durable_evidence_recipe"] = tauri_package_durable_evidence_recipe
    packet["tauri_package_durable_evidence_rows"] = tauri_package_durable_evidence_recipe["rows"]
    packet["counts"]["tauri_package_durable_evidence_row_count"] = tauri_package_durable_evidence_recipe["row_count"]
    packet["counts"]["tauri_package_durable_evidence_blocker_count"] = tauri_package_durable_evidence_recipe[
        "durable_evidence_blocker_count"
    ]
    packet["counts"]["tauri_package_durable_evidence_ready"] = tauri_package_durable_evidence_recipe[
        "local_recipe_ready"
    ]
    packet["runtime"]["tauri_package_durable_evidence_recipe_ready"] = tauri_package_durable_evidence_recipe[
        "local_recipe_ready"
    ]
    packet["runtime"]["tauri_package_durable_evidence_recipe_status"] = tauri_package_durable_evidence_recipe[
        "status"
    ]
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
        "tauri_package_durable_evidence_recipe 汇总 LTG-09 已审查的本地 direct evidence 与剩余生产缺口；不会运行 npm/cargo/Tauri、打开 packaged app、启动 FastAPI、读取配置、写日志、外联或完成生产包。"
    )


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
        "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app/Contents/MacOS/stock_ming_command_center",
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


def _tauri_config_log_runtime_review_call_ledger(
    review: dict[str, Any],
    reviewed_at: str,
) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_tauri_config_log_runtime_review",
            "request_params_safe": {
                "review_scope": "local_tauri_config_log_path_policy_visibility",
                "config_file_policy_observed_safe": review.get("config_file_policy_observed_safe"),
                "log_file_policy_observed_safe": review.get("log_file_policy_observed_safe"),
                "path_policy_panel_visible": review.get("path_policy_panel_visible"),
                "no_config_values_exposed": review.get("no_config_values_exposed"),
                "frontend_token_exposure_absent": review.get("frontend_token_exposure_absent"),
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


def _tauri_config_log_runtime_review_contract(
    *,
    production_runtime_contract: dict[str, Any],
    startup_review: dict[str, Any],
    reviewed_at: str | None = None,
    task_id: str = "",
    explicit_review: bool = False,
    explicit_packaged_app_launch_completed: bool = False,
    path_policy_panel_visible: bool = False,
    config_file_policy_visible: bool = False,
    log_file_policy_visible: bool = False,
    no_config_values_exposed: bool = False,
    no_log_file_written_by_review: bool = False,
    frontend_token_exposure_absent: bool = False,
    config_file_policy_observed: str = "",
    log_file_policy_observed: str = "",
    screenshot_sha256: str = "",
) -> dict[str, Any]:
    config_policy = str(production_runtime_contract.get("config_file_policy") or "")
    log_policy = str(production_runtime_contract.get("log_file_policy") or "")
    runtime_contract_ready = bool(
        production_runtime_contract.get("schema_version") == "tauri_production_runtime_contract.v1"
        and production_runtime_contract.get("config_paths_declared") is True
        and production_runtime_contract.get("log_paths_declared") is True
        and production_runtime_contract.get("reads_config_values") is False
        and production_runtime_contract.get("writes_log_files") is False
        and production_runtime_contract.get("frontend_stores_tokens") is False
        and production_runtime_contract.get("token_key_frontend_exposure") is False
        and production_runtime_contract.get("external_calls_triggered") is False
        and production_runtime_contract.get("tushare_called") is False
        and production_runtime_contract.get("deepseek_called") is False
        and production_runtime_contract.get("github_called") is False
        and production_runtime_contract.get("does_not_execute_trades") is True
        and production_runtime_contract.get("does_not_modify_strategy_action") is True
        and config_policy
        and log_policy
    )
    startup_ready = bool(
        startup_review.get("schema_version") == "tauri_backend_startup_runtime_review.v1"
        and startup_review.get("status") == "tauri_backend_startup_runtime_review_ready"
        and startup_review.get("backend_startup_runtime_validated") is True
        and startup_review.get("backend_startup_runtime_is_completion") is False
        and startup_review.get("config_log_runtime_paths_validated") is False
        and startup_review.get("production_package_complete") is False
        and startup_review.get("external_calls_triggered") is False
        and startup_review.get("tushare_called") is False
        and startup_review.get("deepseek_called") is False
        and startup_review.get("github_called") is False
        and startup_review.get("does_not_execute_trades") is True
        and startup_review.get("does_not_modify_strategy_action") is True
        and startup_review.get("contains_secret") is False
    )
    config_policy_match = bool(config_file_policy_observed == config_policy)
    log_policy_match = bool(log_file_policy_observed == log_policy)
    screenshot_hash_safe = bool(
        len(screenshot_sha256) == 64 and all(char in "0123456789abcdef" for char in screenshot_sha256)
    )
    config_log_ready = bool(
        explicit_review
        and explicit_packaged_app_launch_completed
        and runtime_contract_ready
        and startup_ready
        and path_policy_panel_visible
        and config_file_policy_visible
        and log_file_policy_visible
        and config_policy_match
        and log_policy_match
        and no_config_values_exposed
        and no_log_file_written_by_review
        and frontend_token_exposure_absent
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
            "explicit_post_config_log_runtime_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            explicit_review,
            "POST /api/desktop/tauri-config-log-runtime-review records an explicitly observed config/log path policy review.",
        ),
        _row(
            "prior_packaged_runtime_connection_ready",
            "passed_prior_startup_evidence" if runtime_contract_ready and startup_ready else "pending_prior_startup_evidence",
            runtime_contract_ready and startup_ready,
            (
                f"runtime_contract={production_runtime_contract.get('status')}; "
                f"startup_review={startup_review.get('status')}"
            ),
        ),
        _row(
            "config_log_path_policy_visible",
            "passed_path_policy_visible" if path_policy_panel_visible and config_policy_match and log_policy_match else "pending_path_policy_visibility",
            path_policy_panel_visible and config_policy_match and log_policy_match,
            (
                f"config={config_file_policy_observed if config_policy_match else 'mismatch_or_missing'}; "
                f"log={log_file_policy_observed if log_policy_match else 'mismatch_or_missing'}"
            ),
        ),
        _row(
            "no_config_values_or_log_writes_observed",
            "passed_no_value_or_write" if no_config_values_exposed and no_log_file_written_by_review else "pending_no_value_or_write",
            no_config_values_exposed and no_log_file_written_by_review,
            (
                f"no_config_values_exposed={no_config_values_exposed}; "
                f"log_files_written_by_review={not no_log_file_written_by_review}"
            ),
        ),
        _row(
            "frontend_secret_boundary_visible",
            "passed_no_frontend_secret" if frontend_token_exposure_absent else "pending_frontend_secret_boundary",
            frontend_token_exposure_absent,
            "Frontend path policy view exposes policy strings only; token/key values remain absent.",
        ),
        _row(
            "production_package_still_blocked",
            "passed_production_blockers_visible",
            True,
            "Config/log runtime path evidence is complete, but signing/notarization and production promotion remain required.",
            blocks_review=False,
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_review"]]
    return {
        "schema_version": "tauri_config_log_runtime_review.v1",
        "status": "tauri_config_log_runtime_review_ready" if config_log_ready else "tauri_config_log_runtime_review_pending",
        "scope": "button_gated_local_tauri_config_log_runtime_review_no_secret_no_write_no_provider_no_trade",
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "explicit_review_task_done": explicit_review,
        "explicit_packaged_app_launch_completed_before_review": explicit_packaged_app_launch_completed,
        "path_policy_panel_visible": path_policy_panel_visible,
        "config_file_policy_visible": config_file_policy_visible,
        "log_file_policy_visible": log_file_policy_visible,
        "config_file_policy_observed_safe": config_file_policy_observed if config_policy_match else "",
        "log_file_policy_observed_safe": log_file_policy_observed if log_policy_match else "",
        "no_config_values_exposed": no_config_values_exposed,
        "no_log_file_written_by_review": no_log_file_written_by_review,
        "frontend_token_exposure_absent": frontend_token_exposure_absent,
        "screenshot_sha256": screenshot_sha256 if screenshot_hash_safe else "",
        "local_config_log_runtime_review_ready": config_log_ready,
        "direct_evidence_stage_key": "config_log_runtime_paths" if config_log_ready else "",
        "direct_evidence_stage_keys": ["config_log_runtime_paths"] if config_log_ready else [],
        "backend_startup_runtime_validated": startup_ready,
        "config_log_runtime_paths_validated": config_log_ready,
        "config_log_runtime_paths_is_completion": False,
        "backend_sidecar_autostart_validated": False,
        "backend_autostart_configured": False,
        "packaged_runtime_validated": False,
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
        "note": "This review records config/log path policy visibility and no-secret/no-write boundaries only. It is not signing/notarization evidence or production desktop package completion.",
    }


def _safe_persisted_tauri_config_log_runtime_review(packet: dict[str, Any]) -> dict[str, Any]:
    review = packet.get("tauri_config_log_runtime_review_contract")
    if not isinstance(review, dict):
        return {}
    safe = (
        review.get("schema_version") == "tauri_config_log_runtime_review.v1"
        and review.get("status") == "tauri_config_log_runtime_review_ready"
        and review.get("scope") == "button_gated_local_tauri_config_log_runtime_review_no_secret_no_write_no_provider_no_trade"
        and review.get("explicit_review_task_done") is True
        and review.get("path_policy_panel_visible") is True
        and review.get("config_file_policy_visible") is True
        and review.get("log_file_policy_visible") is True
        and bool(review.get("config_file_policy_observed_safe"))
        and bool(review.get("log_file_policy_observed_safe"))
        and review.get("no_config_values_exposed") is True
        and review.get("no_log_file_written_by_review") is True
        and review.get("frontend_token_exposure_absent") is True
        and len(str(review.get("screenshot_sha256") or "")) == 64
        and review.get("local_config_log_runtime_review_ready") is True
        and review.get("backend_startup_runtime_validated") is True
        and review.get("config_log_runtime_paths_validated") is True
        and review.get("config_log_runtime_paths_is_completion") is False
        and review.get("backend_sidecar_autostart_validated") is False
        and review.get("backend_autostart_configured") is False
        and review.get("packaged_runtime_validated") is False
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


def _read_tauri_config_log_runtime_review_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(TAURI_CONFIG_LOG_RUNTIME_REVIEW_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_tauri_config_log_runtime_review(packet) else {}


def _write_tauri_config_log_runtime_review_packet(
    *,
    review_contract: dict[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": TAURI_CONFIG_LOG_RUNTIME_REVIEW_PACKET_KEY,
        "schema_version": "tauri_config_log_runtime_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "tauri_config_log_runtime_review_contract": dict(review_contract),
        "tauri_config_log_runtime_review_rows": list(review_contract.get("rows") or []),
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
            "This packet is a local review receipt for config/log runtime path policy visibility.",
            "It is not signing/notarization evidence, sidecar/autostart validation, or production package completion.",
        ],
    }
    if _safe_persisted_tauri_config_log_runtime_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(TAURI_CONFIG_LOG_RUNTIME_REVIEW_PACKET_KEY, packet)


def _tauri_signing_notarization_review_call_ledger(
    review: dict[str, Any],
    reviewed_at: str,
) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_tauri_signing_notarization_review",
            "request_params_safe": {
                "review_scope": "local_codesign_spctl_distribution_gap_review",
                "app_bundle_path": review.get("app_bundle_path_observed_safe"),
                "codesign_signature_type": review.get("codesign_signature_type"),
                "codesign_team_identifier_status": review.get("codesign_team_identifier_status"),
                "spctl_assessment_status": review.get("spctl_assessment_status"),
                "dmg_distribution_detected": review.get("dmg_distribution_detected"),
                "temporary_dmg_detected": review.get("temporary_dmg_detected"),
                "external_sources_allowed": False,
                "runs_codesign": False,
                "runs_spctl": False,
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


def _tauri_signing_notarization_review_contract(
    *,
    tauri_build_artifact: dict[str, Any],
    config_log_review: dict[str, Any],
    reviewed_at: str | None = None,
    task_id: str = "",
    explicit_review: bool = False,
    explicit_codesign_inspection_completed: bool = False,
    explicit_spctl_assessment_completed: bool = False,
    app_bundle_path_observed: str = "",
    codesign_signature_type: str = "",
    codesign_flags_observed: str = "",
    codesign_team_identifier_status: str = "",
    codesign_cdhash_observed: str = "",
    spctl_assessment_status: str = "",
    spctl_message_safe: str = "",
    distribution_dmg_detected: bool = False,
    temporary_dmg_detected: bool = False,
    temporary_dmg_ignored_for_distribution: bool = False,
    apple_developer_identity_used: bool = False,
    notarization_ticket_detected: bool = False,
) -> dict[str, Any]:
    app_bundle_path = str(tauri_build_artifact.get("bundle_app_path") or "")
    app_bundle_ready = bool(
        tauri_build_artifact.get("schema_version") == "tauri_build_artifact_detection.v1"
        and tauri_build_artifact.get("packaged_app_bundle_detected") is True
        and int(tauri_build_artifact.get("bundle_app_count") or 0) > 0
        and app_bundle_path
        and app_bundle_path_observed == app_bundle_path
        and tauri_build_artifact.get("artifact_is_gitignored") is True
    )
    config_log_ready = bool(
        config_log_review.get("schema_version") == "tauri_config_log_runtime_review.v1"
        and config_log_review.get("status") == "tauri_config_log_runtime_review_ready"
        and config_log_review.get("config_log_runtime_paths_validated") is True
        and config_log_review.get("production_package_complete") is False
        and config_log_review.get("external_calls_triggered") is False
        and config_log_review.get("tushare_called") is False
        and config_log_review.get("deepseek_called") is False
        and config_log_review.get("github_called") is False
        and config_log_review.get("does_not_execute_trades") is True
        and config_log_review.get("does_not_modify_strategy_action") is True
        and config_log_review.get("contains_secret") is False
    )
    signature_type_safe = codesign_signature_type.strip().lower()[:80]
    team_status_safe = codesign_team_identifier_status.strip().lower()[:80]
    spctl_status_safe = spctl_assessment_status.strip().lower()[:80]
    codesign_flags_safe = codesign_flags_observed.strip()[:160]
    cdhash_safe = codesign_cdhash_observed.strip().lower()[:80]
    spctl_message_trimmed = spctl_message_safe.strip().replace("\n", " ")[:240]
    codesign_observed = bool(
        explicit_codesign_inspection_completed
        and signature_type_safe in {"adhoc", "developer_id", "apple_development", "unknown"}
        and team_status_safe in {"not_set", "set", "unknown"}
        and bool(cdhash_safe)
    )
    spctl_observed = bool(
        explicit_spctl_assessment_completed
        and spctl_status_safe in {"accepted", "rejected", "error", "internal_error", "unknown"}
    )
    production_signing_ready = bool(
        signature_type_safe == "developer_id"
        and team_status_safe == "set"
        and spctl_status_safe == "accepted"
        and apple_developer_identity_used
        and notarization_ticket_detected
        and distribution_dmg_detected
    )
    review_ready = bool(
        explicit_review
        and app_bundle_ready
        and config_log_ready
        and codesign_observed
        and spctl_observed
    )

    def _row(criterion: str, status: str, passed: bool, evidence: str, *, blocks_review: bool = True) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": bool(passed),
            "evidence": evidence,
            "blocks_review": bool(blocks_review and not passed),
            "blocks_production": not bool(passed),
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
            "explicit_post_signing_notarization_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            explicit_review,
            "POST /api/desktop/tauri-signing-notarization-review records a separately observed codesign/spctl review.",
        ),
        _row(
            "prior_package_runtime_evidence_ready",
            "passed_prior_config_log_evidence" if app_bundle_ready and config_log_ready else "pending_prior_config_log_evidence",
            app_bundle_ready and config_log_ready,
            f"app_bundle={app_bundle_path_observed}; config_log_ready={config_log_review.get('config_log_runtime_paths_validated')}",
        ),
        _row(
            "codesign_inspection_observed",
            "passed_codesign_inspection" if codesign_observed else "pending_codesign_inspection",
            codesign_observed,
            (
                f"signature={signature_type_safe or 'missing'}; flags={codesign_flags_safe or 'missing'}; "
                f"team_identifier={team_status_safe or 'missing'}; cdhash_present={bool(cdhash_safe)}"
            ),
        ),
        _row(
            "spctl_assessment_observed",
            "passed_spctl_assessment" if spctl_observed else "pending_spctl_assessment",
            spctl_observed,
            f"spctl_status={spctl_status_safe or 'missing'}; message={spctl_message_trimmed or 'empty'}",
        ),
        _row(
            "production_signing_notarization_ready",
            "passed_production_signing_ready" if production_signing_ready else "blocked_signing_or_notarization",
            production_signing_ready,
            (
                f"developer_identity={apple_developer_identity_used}; notarization_ticket={notarization_ticket_detected}; "
                f"distribution_dmg={distribution_dmg_detected}; temp_dmg={temporary_dmg_detected}"
            ),
            blocks_review=False,
        ),
        _row(
            "production_package_still_blocked",
            "passed_blocker_visible",
            True,
            "Signing/notarization direct review is recorded, but production package promotion remains blocked until Developer ID, notarization, and distribution artifact are ready.",
            blocks_review=False,
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_review"]]
    return {
        "schema_version": "tauri_signing_notarization_review.v1",
        "status": "tauri_signing_notarization_review_ready_blocked"
        if review_ready and not production_signing_ready
        else ("tauri_signing_notarization_review_ready_passed" if production_signing_ready else "tauri_signing_notarization_review_pending"),
        "scope": "button_gated_local_tauri_signing_notarization_gap_review_no_provider_no_trade",
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "explicit_review_task_done": explicit_review,
        "explicit_codesign_inspection_completed": explicit_codesign_inspection_completed,
        "explicit_spctl_assessment_completed": explicit_spctl_assessment_completed,
        "local_signing_notarization_review_ready": review_ready,
        "direct_gap_evidence_stage_key": "signing_notarization_gap_review" if review_ready else "",
        "direct_gap_evidence_stage_keys": ["signing_notarization_gap_review"] if review_ready else [],
        "app_bundle_path_observed_safe": app_bundle_path_observed if app_bundle_ready else "",
        "codesign_signature_type": signature_type_safe,
        "codesign_flags_observed_safe": codesign_flags_safe,
        "codesign_team_identifier_status": team_status_safe,
        "codesign_cdhash_observed_safe": cdhash_safe,
        "spctl_assessment_status": spctl_status_safe,
        "spctl_message_safe": spctl_message_trimmed,
        "distribution_dmg_detected": bool(distribution_dmg_detected),
        "temporary_dmg_detected": bool(temporary_dmg_detected),
        "temporary_dmg_ignored_for_distribution": bool(temporary_dmg_ignored_for_distribution),
        "apple_developer_identity_used": bool(apple_developer_identity_used),
        "notarization_ticket_detected": bool(notarization_ticket_detected),
        "production_signing_notarization_ready": production_signing_ready,
        "signing_notarization_done": production_signing_ready,
        "signing_notarization_is_completion": False,
        "production_package_complete": False,
        "packaged_runtime_validated": False,
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
        "note": "This review records local codesign/spctl/distribution status as direct blocker evidence. It does not notarize, sign, distribute, call providers/models/GitHub, trade, or complete the production desktop package.",
    }


def _safe_persisted_tauri_signing_notarization_review(packet: dict[str, Any]) -> dict[str, Any]:
    review = packet.get("tauri_signing_notarization_review_contract")
    if not isinstance(review, dict):
        return {}
    safe = (
        review.get("schema_version") == "tauri_signing_notarization_review.v1"
        and review.get("status") in {
            "tauri_signing_notarization_review_ready_blocked",
            "tauri_signing_notarization_review_ready_passed",
        }
        and review.get("scope") == "button_gated_local_tauri_signing_notarization_gap_review_no_provider_no_trade"
        and review.get("explicit_review_task_done") is True
        and review.get("explicit_codesign_inspection_completed") is True
        and review.get("explicit_spctl_assessment_completed") is True
        and review.get("local_signing_notarization_review_ready") is True
        and bool(review.get("app_bundle_path_observed_safe"))
        and bool(review.get("codesign_signature_type"))
        and bool(review.get("codesign_cdhash_observed_safe"))
        and bool(review.get("spctl_assessment_status"))
        and review.get("signing_notarization_is_completion") is False
        and review.get("production_package_complete") is False
        and review.get("packaged_runtime_validated") is False
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


def _read_tauri_signing_notarization_review_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(TAURI_SIGNING_NOTARIZATION_REVIEW_PACKET_KEY)
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_tauri_signing_notarization_review(packet) else {}


def _write_tauri_signing_notarization_review_packet(
    *,
    review_contract: dict[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": TAURI_SIGNING_NOTARIZATION_REVIEW_PACKET_KEY,
        "schema_version": "tauri_signing_notarization_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "tauri_signing_notarization_review_contract": dict(review_contract),
        "tauri_signing_notarization_review_rows": list(review_contract.get("rows") or []),
        "call_ledger": list(ledger),
        "cache_only": True,
        "runs_no_build": True,
        "runs_no_codesign_or_spctl": True,
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
            "This packet records local signing/notarization blocker evidence from separately observed codesign/spctl outputs.",
            "It is not signing, notarization, distribution promotion, or production package completion.",
        ],
    }
    if _safe_persisted_tauri_signing_notarization_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(TAURI_SIGNING_NOTARIZATION_REVIEW_PACKET_KEY, packet)


def _tauri_production_package_promotion_review_call_ledger(
    review: dict[str, Any],
    reviewed_at: str,
) -> list[dict[str, Any]]:
    return [
        {
            "api": "local_tauri_production_package_promotion_review",
            "request_params_safe": {
                "review_scope": "local_tauri_production_package_promotion_gate",
                "promotion_review_ready": review.get("local_production_package_promotion_review_ready"),
                "durable_promotion_ready": review.get("durable_promotion_ready"),
                "remaining_blockers": review.get("remaining_blockers", []),
                "direct_gap_evidence_stage_keys": review.get("direct_gap_evidence_stage_keys", []),
                "runs_build": False,
                "opens_packaged_app": False,
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


def _tauri_production_package_promotion_review_contract(
    *,
    packet: dict[str, Any],
    reviewed_at: str | None = None,
    task_id: str = "",
    explicit_review: bool = False,
) -> dict[str, Any]:
    reviewed_at = reviewed_at or _now_iso()
    durable_recipe = (
        packet.get("tauri_package_durable_evidence_recipe")
        if isinstance(packet.get("tauri_package_durable_evidence_recipe"), dict)
        else {}
    )
    durable_rows = [
        row for row in packet.get("tauri_package_durable_evidence_rows", []) if isinstance(row, dict)
    ]
    durable_row_map = {str(row.get("evidence_key")): row for row in durable_rows}
    signing_review = (
        packet.get("tauri_signing_notarization_review_contract")
        if isinstance(packet.get("tauri_signing_notarization_review_contract"), dict)
        else {}
    )
    required_runtime_keys = [
        "app_bundle_dmg_evidence_required",
        "packaged_app_launch_qa_required",
        "backend_startup_runtime_evidence_required",
        "backend_offline_packaged_ux_required",
        "config_log_runtime_path_evidence_required",
        "signing_notarization_review_required",
        "no_build_runtime_provider_trade_secret_boundary",
    ]
    runtime_evidence_ready = all(durable_row_map.get(key, {}).get("passed") is True for key in required_runtime_keys)
    signing_review_ready = signing_review.get("local_signing_notarization_review_ready") is True
    signing_notarization_done = signing_review.get("signing_notarization_done") is True
    production_signing_ready = signing_review.get("production_signing_notarization_ready") is True
    safety_boundary_ready = bool(
        packet.get("external_calls_triggered") is False
        and packet.get("tushare_called") is False
        and packet.get("deepseek_called") is False
        and packet.get("github_called") is False
        and packet.get("does_not_execute_trades") is True
        and packet.get("does_not_modify_strategy_action") is True
        and packet.get("contains_secret") is False
        and durable_recipe.get("cache_get_external_calls") is False
        and durable_recipe.get("react_render_external_calls") is False
        and durable_recipe.get("preflight_runs_build") is False
        and durable_recipe.get("preflight_opens_packaged_app") is False
        and durable_recipe.get("preflight_starts_fastapi") is False
        and durable_recipe.get("preflight_reads_config_values") is False
        and durable_recipe.get("preflight_writes_log_files") is False
    )
    missing_runtime_evidence = [
        key for key in required_runtime_keys if durable_row_map.get(key, {}).get("passed") is not True
    ]
    remaining_blockers = list(missing_runtime_evidence)
    if signing_review_ready and not production_signing_ready:
        remaining_blockers.append("macos_signing_notarization_or_explicit_distribution_waiver_required")
    elif not signing_review_ready:
        remaining_blockers.append("signing_notarization_review_required")
    if not safety_boundary_ready:
        remaining_blockers.append("no_external_trade_secret_boundary")
    durable_promotion_ready = bool(
        explicit_review
        and runtime_evidence_ready
        and production_signing_ready
        and signing_notarization_done
        and safety_boundary_ready
    )
    review_ready = bool(explicit_review and runtime_evidence_ready and signing_review_ready and safety_boundary_ready)
    blocked_after_review = bool(review_ready and not durable_promotion_ready)

    def _row(criterion: str, status: str, passed: bool, evidence: str, *, blocks_review: bool = True) -> dict[str, Any]:
        return {
            "criterion": criterion,
            "status": status,
            "passed": bool(passed),
            "evidence": evidence,
            "blocks_review": bool(blocks_review and not passed),
            "blocks_production": bool(not passed),
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
            "explicit_post_promotion_review_task",
            "passed" if explicit_review else "pending_explicit_post",
            explicit_review,
            "POST /api/desktop/tauri-production-package-promotion-review records the local promotion gate review.",
        ),
        _row(
            "durable_runtime_evidence_ready",
            "passed_durable_runtime_evidence" if runtime_evidence_ready else "blocked_missing_runtime_evidence",
            runtime_evidence_ready,
            f"missing_runtime_evidence={missing_runtime_evidence}",
        ),
        _row(
            "signing_notarization_ready_for_distribution",
            "passed_signing_notarization"
            if production_signing_ready and signing_notarization_done
            else "blocked_signing_notarization_or_distribution_waiver_required",
            production_signing_ready and signing_notarization_done,
            (
                f"signing_review_ready={signing_review_ready}; "
                f"production_signing_notarization_ready={production_signing_ready}; "
                f"signing_notarization_done={signing_notarization_done}; "
                f"status={signing_review.get('status') or 'missing'}"
            ),
        ),
        _row(
            "no_external_trade_secret_boundary",
            "passed_no_external_trade_secret" if safety_boundary_ready else "blocked_safety_boundary",
            safety_boundary_ready,
            "Promotion review calls no providers/models/GitHub, executes no trades, mutates no action, and exposes no secret.",
        ),
        _row(
            "promotion_review_is_not_package_completion",
            "passed_not_completion",
            True,
            "This review is L3 promotion-gate evidence. It does not mark LTG-09 production complete.",
            blocks_review=False,
        ),
    ]
    blocking_rows = [row for row in rows if row["blocks_review"]]
    return {
        "schema_version": "tauri_production_package_promotion_review.v1",
        "status": (
            "tauri_production_package_promotion_review_ready_candidate"
            if durable_promotion_ready
            else (
                "tauri_production_package_promotion_review_ready_blocked"
                if review_ready
                else "tauri_production_package_promotion_review_pending"
            )
        ),
        "scope": "button_gated_local_tauri_production_package_promotion_review_no_build_no_runtime",
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "explicit_review_task_done": explicit_review,
        "local_production_package_promotion_review_ready": review_ready,
        "durable_runtime_evidence_ready": runtime_evidence_ready,
        "durable_promotion_ready": durable_promotion_ready,
        "promotion_review_blocked": blocked_after_review,
        "remaining_blockers": remaining_blockers,
        "direct_evidence_stage_keys": ["production_package_promotion_review"] if durable_promotion_ready else [],
        "direct_gap_evidence_stage_keys": ["production_package_promotion_blocker_review"]
        if blocked_after_review
        else [],
        "missing_runtime_evidence": missing_runtime_evidence,
        "signing_notarization_review_ready": signing_review_ready,
        "production_signing_notarization_ready": production_signing_ready,
        "signing_notarization_done": signing_notarization_done,
        "promotion_review_is_completion": False,
        "production_package_complete": False,
        "packaged_runtime_validated": False,
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
        "note": "This review records the LTG-09 promotion gate result. It does not build, open a packaged app, start FastAPI, read configs, write logs, call providers/models/GitHub, trade, or complete the production desktop package.",
    }


def _safe_persisted_tauri_production_package_promotion_review(packet: dict[str, Any]) -> dict[str, Any]:
    review = packet.get("tauri_production_package_promotion_review_contract")
    if not isinstance(review, dict):
        return {}
    safe = (
        review.get("schema_version") == "tauri_production_package_promotion_review.v1"
        and review.get("status")
        in {
            "tauri_production_package_promotion_review_ready_blocked",
            "tauri_production_package_promotion_review_ready_candidate",
        }
        and review.get("scope") == "button_gated_local_tauri_production_package_promotion_review_no_build_no_runtime"
        and review.get("explicit_review_task_done") is True
        and review.get("local_production_package_promotion_review_ready") is True
        and review.get("promotion_review_is_completion") is False
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


def _read_tauri_production_package_promotion_review_packet() -> dict[str, Any]:
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(
            TAURI_PRODUCTION_PACKAGE_PROMOTION_REVIEW_PACKET_KEY
        )
    except Exception:
        return {}
    if not isinstance(packet, dict):
        return {}
    return packet if _safe_persisted_tauri_production_package_promotion_review(packet) else {}


def _write_tauri_production_package_promotion_review_packet(
    *,
    review_contract: dict[str, Any],
    ledger: list[dict[str, Any]],
    reviewed_at: str,
    task_id: str,
) -> None:
    packet = {
        "packet_key": TAURI_PRODUCTION_PACKAGE_PROMOTION_REVIEW_PACKET_KEY,
        "schema_version": "tauri_production_package_promotion_review_packet.v1",
        "status": review_contract.get("status"),
        "ltg": "LTG-09",
        "task_id": task_id,
        "reviewed_at": reviewed_at,
        "tauri_production_package_promotion_review_contract": dict(review_contract),
        "tauri_production_package_promotion_review_rows": list(review_contract.get("rows") or []),
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
            "This packet records the local LTG-09 production package promotion gate review.",
            "It is not Tauri build execution, packaged runtime launch, signing/notarization, or production package completion.",
        ],
    }
    if _safe_persisted_tauri_production_package_promotion_review(packet):
        SQLiteMetaStore(SQLITE_META_PATH).write_packet(
            TAURI_PRODUCTION_PACKAGE_PROMOTION_REVIEW_PACKET_KEY,
            packet,
        )


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
    one_click_startup_summary = _one_click_startup_summary(api_base_info, desktop_launcher_contract)
    p0_local_connection_receipt = _p0_local_connection_receipt(one_click_startup_summary, desktop_launcher_contract)
    p0_ordinary_connection_rows = _p0_ordinary_connection_rows(one_click_startup_summary)
    p0_failure_diagnostic_rows = _p0_failure_diagnostic_rows(one_click_startup_summary)
    p0_post_startup_readback_rows = _p0_post_startup_readback_rows(one_click_startup_summary)
    p0_to_p1_ordinary_handoff_rows = _p0_to_p1_ordinary_handoff_rows(one_click_startup_summary)
    p0_ordinary_quick_action_rows = _p0_ordinary_quick_action_rows(
        one_click_startup_summary,
        p0_to_p1_ordinary_handoff_rows,
    )
    p0_ordinary_connection_ready_count = sum(1 for row in p0_ordinary_connection_rows if row["当前状态"] == "ready")
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
        "one_click_startup_summary": one_click_startup_summary,
        "one_click_connection_rows": one_click_startup_summary["rows"],
        "p0_recovery_steps": one_click_startup_summary["ordinary_recovery_steps"],
        "p0_local_connection_receipt": p0_local_connection_receipt,
        "p0_local_connection_rows": p0_local_connection_receipt["rows"],
        "p0_ordinary_connection_rows": p0_ordinary_connection_rows,
        "p0_failure_diagnostic_rows": p0_failure_diagnostic_rows,
        "p0_post_startup_readback_rows": p0_post_startup_readback_rows,
        "p0_to_p1_ordinary_handoff_rows": p0_to_p1_ordinary_handoff_rows,
        "p0_ordinary_quick_action_rows": p0_ordinary_quick_action_rows,
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
            "desktop_launcher_ready": 1 if desktop_launcher_contract["status"] == "local_one_click_launcher_ready" else 0,
            "one_click_connection_row_count": one_click_startup_summary["row_count"],
            "one_click_connection_blocker_count": one_click_startup_summary["blocker_count"],
            "one_click_connection_ready": 1 if one_click_startup_summary["frontend_backend_connection_ready"] else 0,
            "p0_local_connection_row_count": p0_local_connection_receipt["row_count"],
            "p0_local_connection_blocker_count": p0_local_connection_receipt["blocker_count"],
            "p0_local_connection_ready": 1 if p0_local_connection_receipt["connection_contract_ready"] else 0,
            "p0_ordinary_connection_row_count": len(p0_ordinary_connection_rows),
            "p0_ordinary_connection_ready_count": p0_ordinary_connection_ready_count,
            "p0_failure_diagnostic_row_count": len(p0_failure_diagnostic_rows),
            "p0_post_startup_readback_row_count": len(p0_post_startup_readback_rows),
            "p0_to_p1_ordinary_handoff_row_count": len(p0_to_p1_ordinary_handoff_rows),
            "p0_ordinary_quick_action_row_count": len(p0_ordinary_quick_action_rows),
            "p0_ordinary_quick_action_visible_count": sum(
                1 for row in p0_ordinary_quick_action_rows if row["ordinary_user_visible"]
            ),
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
            "one_click_frontend_backend_ready": one_click_startup_summary["frontend_backend_connection_ready"],
            "one_click_startup_status": one_click_startup_summary["status"],
            "one_click_startup_next_action": one_click_startup_summary["what_user_should_click_next"],
            "one_click_startup_blocker_count": one_click_startup_summary["blocker_count"],
            "p0_local_connection_status": p0_local_connection_receipt["status"],
            "p0_local_connection_ready": p0_local_connection_receipt["connection_contract_ready"],
            "p0_ordinary_connection_ready_count": p0_ordinary_connection_ready_count,
            "p0_failure_diagnostic_ready_count": sum(
                1 for row in p0_failure_diagnostic_rows if row["当前状态"] == "ready"
            ),
            "p0_post_startup_readback_ready_count": sum(
                1 for row in p0_post_startup_readback_rows if row["当前状态"] == "ready"
            ),
            "p0_to_p1_next_user_action": p0_to_p1_ordinary_handoff_rows[0]["下一步"],
            "p0_ordinary_quick_action_next": p0_ordinary_quick_action_rows[0]["用户下一步"],
            "p0_current_runtime_live_connection_verified": p0_local_connection_receipt[
                "current_runtime_live_connection_verified"
            ],
            "api_health_endpoint": api_base_info["expected_health_endpoint"],
            "desktop_launcher_ready": desktop_launcher_contract["status"] == "local_one_click_launcher_ready",
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
            "desktop_launcher_contract_is_local_one_click": True,
            "desktop_launcher_contract_is_not_production_package": True,
            "desktop_launcher_contract_does_not_run_from_get_cache": True,
            "one_click_startup_summary_is_local": True,
            "one_click_startup_summary_is_user_run_only": True,
            "one_click_startup_summary_does_not_run_from_get_cache": True,
            "one_click_startup_summary_is_not_production_package": True,
            "one_click_startup_summary_does_not_enable_provider_model": True,
            "p0_local_connection_receipt_is_local": True,
            "p0_local_connection_receipt_is_user_run_only": True,
            "p0_local_connection_receipt_does_not_probe_runtime_from_get_cache": True,
            "p0_local_connection_receipt_is_not_production_package": True,
            "p0_local_connection_receipt_does_not_enable_provider_model": True,
            "p0_ordinary_connection_rows_are_cache_only": True,
            "p0_ordinary_connection_rows_do_not_probe_runtime": True,
            "p0_ordinary_connection_rows_do_not_create_task": True,
            "p0_failure_diagnostic_rows_are_cache_only": True,
            "p0_failure_diagnostic_rows_do_not_probe_runtime": True,
            "p0_failure_diagnostic_rows_do_not_create_task": True,
            "p0_failure_diagnostic_rows_do_not_call_provider_model": True,
            "p0_post_startup_readback_rows_are_cache_only": True,
            "p0_post_startup_readback_rows_do_not_probe_runtime": True,
            "p0_post_startup_readback_rows_do_not_create_task": True,
            "p0_to_p1_ordinary_handoff_rows_are_cache_only": True,
            "p0_to_p1_ordinary_handoff_rows_do_not_create_task": True,
            "p0_to_p1_ordinary_handoff_rows_do_not_call_provider_model": True,
            "p0_ordinary_quick_action_rows_are_cache_only": True,
            "p0_ordinary_quick_action_rows_do_not_create_task": True,
            "p0_ordinary_quick_action_rows_do_not_call_provider_model": True,
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
        + one_click_startup_summary["call_ledger"]
        + p0_local_connection_receipt["call_ledger"]
        + [
            {
                "api": "local_p0_ordinary_connection_rows",
                "source": "one_click_startup_summary",
                "row_count": len(p0_ordinary_connection_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_ordinary_connection_rows_read",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ]
        + [
            {
                "api": "local_p0_post_startup_readback_rows",
                "source": "one_click_startup_summary",
                "row_count": len(p0_post_startup_readback_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_post_startup_readback_rows_read",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
            {
                "api": "local_p0_failure_diagnostic_rows",
                "source": "one_click_startup_summary",
                "row_count": len(p0_failure_diagnostic_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_failure_diagnostic_rows_read",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
            {
                "api": "local_p0_to_p1_ordinary_handoff_rows",
                "source": "one_click_startup_summary",
                "row_count": len(p0_to_p1_ordinary_handoff_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_p0_to_p1_handoff_rows_read",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
            {
                "api": "local_p0_ordinary_quick_action_rows",
                "source": "p0_to_p1_ordinary_handoff_rows",
                "row_count": len(p0_ordinary_quick_action_rows),
                "local_fetched_at": _now_iso(),
                "call_status": "local_p0_quick_action_rows_read",
                "external": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
        ]
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
            "P0 本地一键启动器会启动或复用 FastAPI/Vite，等待前后端联通后才打开页面；GET preflight 不会运行它。",
            "若不用一键启动器，Tauri 开发模式仍需人工启动 FastAPI/Vite；预检页只展示状态，不启动服务。",
            "桌面壳预检不读取 token/key，不调用 Tushare、DeepSeek、GitHub，不执行真实交易。",
        ],
    }
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
    persisted_config_log_review_packet = _read_tauri_config_log_runtime_review_packet()
    persisted_config_log_review = _safe_persisted_tauri_config_log_runtime_review(
        persisted_config_log_review_packet
    )
    if persisted_config_log_review:
        packet["tauri_config_log_runtime_review_contract"] = persisted_config_log_review
        packet["tauri_config_log_runtime_review_rows"] = list(persisted_config_log_review.get("rows") or [])
        packet["tauri_config_log_runtime_review_ready"] = True
        packet["counts"]["tauri_config_log_runtime_review_row_count"] = persisted_config_log_review.get(
            "row_count",
            0,
        )
        packet["counts"]["tauri_config_log_runtime_review_blocking_count"] = persisted_config_log_review.get(
            "blocking_review_count",
            0,
        )
        packet["runtime"]["tauri_config_log_runtime_review_ready"] = True
        packet["runtime"]["tauri_config_log_runtime_review_status"] = persisted_config_log_review.get("status")
        packet["runtime"]["config_log_runtime_paths_validated"] = True
        packet["policy"]["tauri_config_log_runtime_review_is_local"] = True
        packet["policy"]["tauri_config_log_runtime_review_is_not_build"] = True
        packet["policy"]["tauri_config_log_runtime_review_did_not_read_config_values"] = True
        packet["policy"]["tauri_config_log_runtime_review_did_not_write_log_files"] = True
        packet["policy"]["tauri_config_log_runtime_review_is_not_production_completion"] = True
        packet["call_ledger"] = packet["call_ledger"] + [
            row for row in persisted_config_log_review_packet.get("call_ledger", []) if isinstance(row, dict)
        ]
        packet["warnings"].append(
            "tauri_config_log_runtime_review 只记录显式本地 config/log path policy 观察；不读取配置值、不写日志、不等于签名/公证或 production package 完成。"
        )
    persisted_signing_review_packet = _read_tauri_signing_notarization_review_packet()
    persisted_signing_review = _safe_persisted_tauri_signing_notarization_review(
        persisted_signing_review_packet
    )
    if persisted_signing_review:
        packet["tauri_signing_notarization_review_contract"] = persisted_signing_review
        packet["tauri_signing_notarization_review_rows"] = list(persisted_signing_review.get("rows") or [])
        packet["tauri_signing_notarization_review_ready"] = True
        packet["counts"]["tauri_signing_notarization_review_row_count"] = persisted_signing_review.get(
            "row_count",
            0,
        )
        packet["counts"]["tauri_signing_notarization_review_blocking_count"] = persisted_signing_review.get(
            "blocking_review_count",
            0,
        )
        packet["runtime"]["tauri_signing_notarization_review_ready"] = True
        packet["runtime"]["tauri_signing_notarization_review_status"] = persisted_signing_review.get("status")
        packet["runtime"]["signing_notarization_done"] = (
            persisted_signing_review.get("signing_notarization_done") is True
        )
        packet["policy"]["tauri_signing_notarization_review_is_local"] = True
        packet["policy"]["tauri_signing_notarization_review_did_not_run_codesign_or_spctl"] = True
        packet["policy"]["tauri_signing_notarization_review_is_not_build"] = True
        packet["policy"]["tauri_signing_notarization_review_is_not_production_completion"] = True
        packet["call_ledger"] = packet["call_ledger"] + [
            row for row in persisted_signing_review_packet.get("call_ledger", []) if isinstance(row, dict)
        ]
        packet["warnings"].append(
            "tauri_signing_notarization_review 只记录显式本地 codesign/spctl gap evidence；不执行签名/公证、不等于 production package 完成。"
        )
    persisted_promotion_review_packet = _read_tauri_production_package_promotion_review_packet()
    persisted_promotion_review = _safe_persisted_tauri_production_package_promotion_review(
        persisted_promotion_review_packet
    )
    if persisted_promotion_review:
        packet["tauri_production_package_promotion_review_contract"] = persisted_promotion_review
        packet["tauri_production_package_promotion_review_rows"] = list(
            persisted_promotion_review.get("rows") or []
        )
        packet["tauri_production_package_promotion_review_ready"] = True
        packet["counts"]["tauri_production_package_promotion_review_row_count"] = persisted_promotion_review.get(
            "row_count",
            0,
        )
        packet["counts"]["tauri_production_package_promotion_review_blocking_count"] = persisted_promotion_review.get(
            "blocking_review_count",
            0,
        )
        packet["runtime"]["tauri_production_package_promotion_review_ready"] = True
        packet["runtime"]["tauri_production_package_promotion_review_status"] = persisted_promotion_review.get(
            "status"
        )
        packet["runtime"]["tauri_production_package_durable_promotion_ready"] = (
            persisted_promotion_review.get("durable_promotion_ready") is True
        )
        packet["policy"]["tauri_production_package_promotion_review_is_local"] = True
        packet["policy"]["tauri_production_package_promotion_review_is_not_build"] = True
        packet["policy"]["tauri_production_package_promotion_review_is_not_runtime_execution"] = True
        packet["policy"]["tauri_production_package_promotion_review_is_not_production_completion"] = True
        packet["call_ledger"] = packet["call_ledger"] + [
            row for row in persisted_promotion_review_packet.get("call_ledger", []) if isinstance(row, dict)
        ]
        packet["warnings"].append(
            "tauri_production_package_promotion_review 只记录本地 production package promotion gate 结论；不运行 build/runtime、不外联、不等于 production package 完成。"
        )
    _attach_tauri_package_durable_evidence_recipe(packet)
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
        "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app/Contents/MacOS/stock_ming_command_center",
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


def run_tauri_config_log_runtime_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, dict) else {}
    screenshot_sha256 = str(payload_map.get("screenshot_sha256") or "").strip().lower()
    config_file_policy_observed = str(payload_map.get("config_file_policy_observed") or "").strip()
    log_file_policy_observed = str(payload_map.get("log_file_policy_observed") or "").strip()
    task = create_task_record(
        TAURI_CONFIG_LOG_RUNTIME_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="tauri_config_log_runtime_review_queued",
        warnings=[
            "Tauri config/log runtime review 只记录用户/测试已显式观察到的 path policy 和无密钥暴露边界。",
            "review 不运行 npm/cargo/Tauri、不启动 FastAPI、不读取配置值、不写日志、不调用 provider/model/GitHub、不交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_tauri_config_log_runtime_evidence",
    )
    packet = read_desktop_shell_preflight_cache()
    reviewed_at = _now_iso()
    review_contract = _tauri_config_log_runtime_review_contract(
        production_runtime_contract=packet.get("production_runtime_contract", {}),
        startup_review=packet.get("tauri_backend_startup_runtime_review_contract", {}),
        explicit_review=True,
        explicit_packaged_app_launch_completed=payload_map.get("explicit_packaged_app_launch_completed") is True,
        path_policy_panel_visible=payload_map.get("path_policy_panel_visible") is True,
        config_file_policy_visible=payload_map.get("config_file_policy_visible") is True,
        log_file_policy_visible=payload_map.get("log_file_policy_visible") is True,
        no_config_values_exposed=payload_map.get("no_config_values_exposed") is True,
        no_log_file_written_by_review=payload_map.get("no_log_file_written_by_review") is True,
        frontend_token_exposure_absent=payload_map.get("frontend_token_exposure_absent") is True,
        config_file_policy_observed=config_file_policy_observed,
        log_file_policy_observed=log_file_policy_observed,
        screenshot_sha256=screenshot_sha256,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    ledger = _tauri_config_log_runtime_review_call_ledger(review_contract, reviewed_at)
    _write_tauri_config_log_runtime_review_packet(
        review_contract=review_contract,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="tauri_config_log_runtime_review_ready"
        if review_contract["local_config_log_runtime_review_ready"]
        else "tauri_config_log_runtime_review_pending",
        call_ledger=ledger,
        warning="tauri_config_log_runtime_review_completed_no_build_no_config_read_no_log_write_no_external_call",
    ) or task


def run_tauri_signing_notarization_review_task(payload: Any = None) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, dict) else {}
    task = create_task_record(
        TAURI_SIGNING_NOTARIZATION_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="tauri_signing_notarization_review_queued",
        warnings=[
            "Tauri signing/notarization review 只记录用户/测试已显式观察到的 codesign/spctl/DMG 状态。",
            "review 不运行 codesign/spctl/notarytool，不运行 npm/cargo/Tauri，不调用 provider/model/GitHub，不交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_tauri_signing_notarization_evidence",
    )
    packet = read_desktop_shell_preflight_cache()
    reviewed_at = _now_iso()
    review_contract = _tauri_signing_notarization_review_contract(
        tauri_build_artifact=packet.get("tauri_build_artifact", {}),
        config_log_review=packet.get("tauri_config_log_runtime_review_contract", {}),
        explicit_review=True,
        explicit_codesign_inspection_completed=payload_map.get("explicit_codesign_inspection_completed") is True,
        explicit_spctl_assessment_completed=payload_map.get("explicit_spctl_assessment_completed") is True,
        app_bundle_path_observed=str(payload_map.get("app_bundle_path_observed") or "").strip(),
        codesign_signature_type=str(payload_map.get("codesign_signature_type") or "").strip(),
        codesign_flags_observed=str(payload_map.get("codesign_flags_observed") or "").strip(),
        codesign_team_identifier_status=str(payload_map.get("codesign_team_identifier_status") or "").strip(),
        codesign_cdhash_observed=str(payload_map.get("codesign_cdhash_observed") or "").strip(),
        spctl_assessment_status=str(payload_map.get("spctl_assessment_status") or "").strip(),
        spctl_message_safe=str(payload_map.get("spctl_message_safe") or "").strip(),
        distribution_dmg_detected=payload_map.get("distribution_dmg_detected") is True,
        temporary_dmg_detected=payload_map.get("temporary_dmg_detected") is True,
        temporary_dmg_ignored_for_distribution=payload_map.get("temporary_dmg_ignored_for_distribution") is True,
        apple_developer_identity_used=payload_map.get("apple_developer_identity_used") is True,
        notarization_ticket_detected=payload_map.get("notarization_ticket_detected") is True,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    ledger = _tauri_signing_notarization_review_call_ledger(review_contract, reviewed_at)
    _write_tauri_signing_notarization_review_packet(
        review_contract=review_contract,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step="tauri_signing_notarization_review_ready_blocked"
        if review_contract["local_signing_notarization_review_ready"]
        else "tauri_signing_notarization_review_pending",
        call_ledger=ledger,
        warning="tauri_signing_notarization_review_completed_no_sign_no_notary_no_external_call",
    ) or task


def run_tauri_production_package_promotion_review_task(payload: Any = None) -> dict[str, Any]:
    task = create_task_record(
        TAURI_PRODUCTION_PACKAGE_PROMOTION_REVIEW_TASK_TYPE,
        output_packet_key=PACKET_KEY,
        payload=payload,
        current_step="tauri_production_package_promotion_review_queued",
        warnings=[
            "Tauri production package promotion review 只审查已有本地 package evidence 和剩余 blocker。",
            "review 不运行 npm/cargo/Tauri、不打开 packaged app、不启动 FastAPI、不读取配置、不写日志、不调用 provider/model/GitHub、不交易。",
        ],
    )
    if task.get("dedupe_reused_existing"):
        return task

    update_task_status(
        task["task_id"],
        status="running",
        progress=0.35,
        current_step="reading_local_tauri_promotion_gate_evidence",
    )
    packet = read_desktop_shell_preflight_cache()
    reviewed_at = _now_iso()
    review_contract = _tauri_production_package_promotion_review_contract(
        packet=packet,
        explicit_review=True,
        task_id=str(task["task_id"]),
        reviewed_at=reviewed_at,
    )
    ledger = _tauri_production_package_promotion_review_call_ledger(review_contract, reviewed_at)
    _write_tauri_production_package_promotion_review_packet(
        review_contract=review_contract,
        ledger=ledger,
        reviewed_at=reviewed_at,
        task_id=str(task["task_id"]),
    )
    if review_contract["durable_promotion_ready"]:
        current_step = "tauri_production_package_promotion_review_ready_candidate"
    elif review_contract["local_production_package_promotion_review_ready"]:
        current_step = "tauri_production_package_promotion_review_ready_blocked"
    else:
        current_step = "tauri_production_package_promotion_review_pending"
    return update_task_status(
        task["task_id"],
        status="success",
        progress=1.0,
        current_step=current_step,
        call_ledger=ledger,
        warning="tauri_production_package_promotion_review_completed_no_build_no_runtime_no_external_call",
    ) or task
