from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
from pathlib import Path
from typing import Any


PACKET_KEY = "command_center_3_desktop_shell_preflight_cache"
SCHEMA_VERSION = "desktop_shell_preflight_cache.v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"


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


def _file_row(path: Path, label: str, role: str) -> dict[str, Any]:
    return {
        "label": label,
        "path": _path_label(path),
        "role": role,
        "exists": path.exists(),
        "kind": "directory" if path.is_dir() else "file",
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
            "step": "1",
            "name": "启动 FastAPI 后端",
            "command": "scripts/dev_server.sh",
            "required_for": "React/Tauri 页面读取 cache API",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
        },
        {
            "step": "2",
            "name": "启动 Vite 前端",
            "command": "cd desktop && npm run dev",
            "required_for": "浏览器开发模式",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
        },
        {
            "step": "3",
            "name": "启动 Tauri 桌面壳",
            "command": "cd desktop && npm run tauri dev",
            "required_for": "桌面窗口开发模式；需要 Rust/Cargo",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
        },
        {
            "step": "check",
            "name": "连接检查",
            "command": f"GET {api_base.rstrip('/')}/health",
            "required_for": "确认前端只连接本地 FastAPI",
            "manual": True,
            "external_calls_triggered": False,
            "loads_token_or_key": False,
        },
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
    production_readiness = {
        "status": "tauri_preflight_ready" if tauri_dev_ready else ("vite_ready_tauri_toolchain_pending" if vite_dev_ready else "desktop_scaffold_partial"),
        "scope": "tauri_desktop_production_preflight",
        "vite_build_ready": vite_dev_ready,
        "tauri_dev_ready": tauri_dev_ready,
        "tauri_package_build_attempted": False,
        "tauri_package_build_required_for_production": True,
        "rust_toolchain_required": True,
        "backend_sidecar_autostart_enabled": False,
        "backend_sidecar_autostart_planned": True,
        "frontend_stores_tokens": False,
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
        "dev_launch_plan": _dev_launch_plan(api_base),
        "production_launch_plan": _production_launch_plan(api_base),
        "package_json": package_summary,
        "tauri_config": tauri_config,
        "production_readiness": production_readiness,
        "file_rows": file_rows,
        "command_rows": command_rows,
        "counts": {
            "required_file_count": required_file_count,
            "required_file_ready_count": file_ready_count,
            "command_count": len(command_rows),
            "command_ready_count": sum(1 for row in command_rows if row["available"]),
        },
        "runtime": {
            "node_ready": node_ready,
            "rust_ready": rust_ready,
            "vite_dev_ready": vite_dev_ready,
            "tauri_dev_ready": tauri_dev_ready,
            "node_modules_present": (DESKTOP_ROOT / "node_modules").exists(),
            "dist_present": (DESKTOP_ROOT / "dist").exists(),
            "tauri_cli_declared": bool(package_summary.get("has_tauri_cli")),
            "tauri_build_attempted": False,
            "vite_build_attempted": False,
            "fastapi_dev_server_started": False,
            "api_base_is_localhost": api_base_info["is_localhost"],
            "api_health_endpoint": api_base_info["expected_health_endpoint"],
            "backend_autostart_configured": False,
            "production_package_build_attempted": False,
            "backend_sidecar_autostart_enabled": False,
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
        ],
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
            "桌面壳预检不读取 token/key，不调用 Tushare、DeepSeek、GitHub，不执行真实交易。",
        ],
    }
    return _json_safe(packet)
