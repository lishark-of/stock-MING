from __future__ import annotations

import ast
import datetime as _dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from server.services import audit_service, candidate_service, data_capability_service, data_health_service, desktop_service, discipline_service, evidence_service, factor_service, legacy_service, market_service, model_strategy_service, next_session_service, packet_service, position_service, quant_service, recovery_service, risk_service, storage_service, strategy_service, task_service, trade_review_service, tushare_task_service, worker_service
from server.services import migration_status_service
from server.services.task_service import clear_task_statuses_for_tests, create_task_stub, read_task_status, update_task_status


class CommandCenter3ServerServiceTests(unittest.TestCase):
    def _with_snapshot_cache(self, payload):
        original_path = packet_service.SNAPSHOT_CACHE_PATH
        temp_dir = tempfile.TemporaryDirectory()
        cache_path = Path(temp_dir.name) / "command_center_latest.json"
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        packet_service.SNAPSHOT_CACHE_PATH = cache_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SNAPSHOT_CACHE_PATH", original_path)
        return cache_path

    def _with_meta_store(self):
        original_packet_path = packet_service.SQLITE_META_PATH
        original_factor_path = factor_service.SQLITE_META_PATH
        original_next_session_path = next_session_service.SQLITE_META_PATH
        original_task_path = task_service.SQLITE_META_PATH
        original_tushare_task_path = tushare_task_service.SQLITE_META_PATH
        original_storage_path = storage_service.SQLITE_META_PATH
        original_candidate_path = candidate_service.SQLITE_META_PATH
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "meta.sqlite"
        packet_service.SQLITE_META_PATH = db_path
        factor_service.SQLITE_META_PATH = db_path
        next_session_service.SQLITE_META_PATH = db_path
        task_service.SQLITE_META_PATH = db_path
        tushare_task_service.SQLITE_META_PATH = db_path
        storage_service.SQLITE_META_PATH = db_path
        candidate_service.SQLITE_META_PATH = db_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SQLITE_META_PATH", original_packet_path)
        self.addCleanup(setattr, factor_service, "SQLITE_META_PATH", original_factor_path)
        self.addCleanup(setattr, next_session_service, "SQLITE_META_PATH", original_next_session_path)
        self.addCleanup(setattr, task_service, "SQLITE_META_PATH", original_task_path)
        self.addCleanup(setattr, tushare_task_service, "SQLITE_META_PATH", original_tushare_task_path)
        self.addCleanup(setattr, storage_service, "SQLITE_META_PATH", original_storage_path)
        self.addCleanup(setattr, candidate_service, "SQLITE_META_PATH", original_candidate_path)
        return db_path

    def _with_parquet_root(self):
        original_root = storage_service.PARQUET_ROOT
        temp_dir = tempfile.TemporaryDirectory()
        storage_service.PARQUET_ROOT = Path(temp_dir.name) / "parquet"
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, storage_service, "PARQUET_ROOT", original_root)
        return storage_service.PARQUET_ROOT

    def assert_local_ledger_boundary(self, row):
        self.assertFalse(row["external"])
        self.assertFalse(row["external_calls_triggered"])
        self.assertFalse(row["tushare_called"])
        self.assertFalse(row["deepseek_called"])
        self.assertFalse(row["github_called"])
        self.assertTrue(row["does_not_execute_trades"])
        self.assertTrue(row["does_not_modify_strategy_action"])

    def _with_deepseek_mode(self, mode=None, auto_enabled=None):
        keys = ("DEEPSEEK_FACTOR_EXPLAIN_MODE", "DEEPSEEK_AUTO_EXPLAIN_ENABLED")
        original = {key: os.environ.get(key) for key in keys}
        if mode is None:
            os.environ.pop("DEEPSEEK_FACTOR_EXPLAIN_MODE", None)
        else:
            os.environ["DEEPSEEK_FACTOR_EXPLAIN_MODE"] = str(mode)
        if auto_enabled is None:
            os.environ.pop("DEEPSEEK_AUTO_EXPLAIN_ENABLED", None)
        else:
            os.environ["DEEPSEEK_AUTO_EXPLAIN_ENABLED"] = "true" if auto_enabled else "false"

        def restore():
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.addCleanup(restore)

    def _discover_fastapi_post_routes(self):
        return self._discover_fastapi_routes("post")

    def _discover_fastapi_get_routes(self):
        return self._discover_fastapi_routes("get")

    def _discover_fastapi_routes(self, method):
        routes = []
        for path in sorted(Path("server/api").glob("routes_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            router_prefixes = {}
            for node in tree.body:
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                    continue
                func = node.value.func
                if not isinstance(func, ast.Name) or func.id != "APIRouter":
                    continue
                prefix = ""
                for keyword in node.value.keywords:
                    if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                        prefix = str(keyword.value.value or "")
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        router_prefixes[target.id] = prefix

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for decorator in node.decorator_list:
                    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                        continue
                    if decorator.func.attr != method or not isinstance(decorator.func.value, ast.Name):
                        continue
                    path_arg = ""
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        path_arg = str(decorator.args[0].value or "")
                    routes.append(f"{method.upper()} {router_prefixes.get(decorator.func.value.id, '')}{path_arg}")
        return sorted(routes)

    def _with_trade_review_log(self, records):
        original_path = trade_review_service.TRADE_REVIEW_LOG_PATH
        temp_dir = tempfile.TemporaryDirectory()
        log_path = Path(temp_dir.name) / "trade_review_log.jsonl"
        with log_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        trade_review_service.TRADE_REVIEW_LOG_PATH = log_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, trade_review_service, "TRADE_REVIEW_LOG_PATH", original_path)
        return log_path

    def test_cache_builders_do_not_call_external_sources(self):
        factor = packet_service.build_factor_quant_cache()
        serenity = packet_service.build_serenity_cache()
        next_session = packet_service.build_next_session_cache()
        migration = migration_status_service.build_migration_status()
        desktop = desktop_service.read_desktop_shell_preflight_cache()
        model_strategy = model_strategy_service.read_deepseek_model_strategy_cache()

        self.assertEqual(factor["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertFalse(factor["deepseek_called"])
        self.assertFalse(factor["tushare_called"])
        self.assertFalse(factor["external_calls_triggered"])
        self.assertFalse(factor["governance"]["allow_core_action"])
        self.assertTrue(factor["next_session_bridge"]["does_not_modify_action"])
        self.assertTrue(factor["next_session_bridge"]["does_not_modify_operation_zones"])

        self.assertEqual(serenity["packet_key"], "command_center_serenity_method_radar_packet")
        self.assertFalse(serenity["deepseek_called"])
        self.assertTrue(serenity["decision_usage_policy"]["display_only"])
        self.assertEqual(serenity["call_ledger"][0]["api"], "local_serenity_method_radar_cache")
        self.assertFalse(serenity["call_ledger"][0]["external"])
        self.assertFalse(serenity["call_ledger"][0]["github_called"])
        self.assertIn("GET /api/serenity/cache", serenity["warnings"][0])

        self.assertEqual(next_session["packet_key"], "command_center_next_session_projection_packet")
        self.assertFalse(next_session["external_calls_triggered"])
        self.assertTrue(next_session["does_not_modify_action"])
        self.assertEqual(migration["packet_key"], "command_center_3_migration_status")
        self.assertEqual(len(migration["progress_baseline"]), 11)
        self.assertEqual(migration["progress_baseline"][0]["module"], "Streamlit 保留为 legacy")
        self.assertEqual(migration["progress_baseline"][-1]["current_degree"], "20%-30%")
        self.assertEqual(migration["call_ledger"][0]["api"], "local_migration_status_cache")
        self.assertFalse(migration["call_ledger"][0]["external"])
        self.assertIn("GET /api/migration/status", migration["warnings"][0])
        self.assertTrue(migration["baseline_policy"]["use_as_planning_baseline"])
        self.assertIn("不使用 git add .。", migration["principles"])
        self.assertIn("不 push，等待用户确认。", migration["principles"])
        self.assertFalse(migration["api_policy"]["external_calls_triggered"])
        self.assertFalse(migration["api_policy"]["tushare_called"])
        self.assertFalse(migration["api_policy"]["deepseek_called"])
        self.assertFalse(migration["api_policy"]["github_called"])
        self.assertTrue(migration["api_policy"]["does_not_modify_strategy_action"])

        self.assertEqual(desktop["packet_key"], "command_center_3_desktop_shell_preflight_cache")
        self.assertEqual(desktop["mode"], "cache_only")
        self.assertTrue(desktop["cache_only"])
        self.assertTrue(desktop["read_only"])
        self.assertFalse(desktop["external_calls_triggered"])
        self.assertFalse(desktop["tushare_called"])
        self.assertFalse(desktop["deepseek_called"])
        self.assertFalse(desktop["github_called"])
        self.assertTrue(desktop["policy"]["does_not_run_npm_install"])
        self.assertTrue(desktop["policy"]["does_not_run_npm_build"])
        self.assertTrue(desktop["policy"]["does_not_run_tauri"])
        self.assertTrue(desktop["policy"]["does_not_run_cargo"])
        self.assertTrue(desktop["policy"]["frontend_must_use_fastapi_api_client"])
        self.assertFalse(desktop["policy"]["backend_autostart_enabled"])
        self.assertTrue(desktop["policy"]["api_base_must_be_localhost"])
        self.assertTrue(desktop["policy"]["production_runtime_contract_is_path_only"])
        self.assertTrue(desktop["policy"]["does_not_read_config_values"])
        self.assertTrue(desktop["policy"]["does_not_write_log_files"])
        self.assertTrue(desktop["api_base_info"]["is_localhost"])
        self.assertEqual(desktop["api_base_info"]["expected_health_endpoint"], "http://127.0.0.1:8710/health")
        self.assertTrue(desktop["api_base_info"]["frontend_uses_fastapi_only"])
        self.assertTrue(desktop["api_base_info"]["does_not_autostart_backend"])
        self.assertEqual(desktop["runtime"]["api_health_endpoint"], "http://127.0.0.1:8710/health")
        self.assertFalse(desktop["runtime"]["backend_autostart_configured"])
        self.assertFalse(desktop["runtime"]["production_package_build_attempted"])
        self.assertFalse(desktop["runtime"]["backend_sidecar_autostart_enabled"])
        self.assertIn("tauri_config", desktop)
        self.assertTrue(desktop["tauri_config"]["available"])
        self.assertTrue(desktop["tauri_config"]["dev_url_is_localhost"])
        self.assertFalse(desktop["tauri_config"]["backend_sidecar_configured"])
        self.assertIn("tauri_build_artifact", desktop)
        build_artifact = desktop["tauri_build_artifact"]
        self.assertEqual(build_artifact["schema_version"], "tauri_build_artifact_detection.v1")
        self.assertIn(build_artifact["status"], {"artifact_detected", "artifact_missing"})
        self.assertEqual(
            build_artifact["binary_path"],
            "desktop/src-tauri/target/release/stock_ming_command_center",
        )
        self.assertFalse(build_artifact["build_command_executed_by_get_cache"])
        self.assertTrue(build_artifact["artifact_is_gitignored"])
        self.assertFalse(build_artifact["packaged_runtime_validated"])
        self.assertFalse(build_artifact["external_calls_triggered"])
        self.assertFalse(build_artifact["tushare_called"])
        self.assertFalse(build_artifact["deepseek_called"])
        self.assertFalse(build_artifact["github_called"])
        self.assertTrue(build_artifact["does_not_execute_trades"])
        self.assertTrue(build_artifact["does_not_modify_strategy_action"])
        self.assertIn("production_readiness", desktop)
        self.assertEqual(desktop["production_readiness"]["scope"], "tauri_desktop_production_preflight")
        self.assertFalse(desktop["production_readiness"]["tauri_package_build_attempted"])
        self.assertEqual(desktop["production_readiness"]["tauri_build_artifact_status"], build_artifact["status"])
        self.assertEqual(desktop["production_readiness"]["tauri_build_artifact_detected"], build_artifact["binary_exists"])
        self.assertTrue(desktop["production_readiness"]["tauri_package_build_required_for_production"])
        self.assertFalse(desktop["production_readiness"]["backend_sidecar_autostart_enabled"])
        self.assertTrue(desktop["production_readiness"]["backend_sidecar_autostart_planned"])
        self.assertFalse(desktop["production_readiness"]["frontend_stores_tokens"])
        self.assertEqual(
            desktop["production_readiness"]["production_runtime_contract_status"],
            "runtime_contract_ready_packaged_validation_pending",
        )
        self.assertEqual(
            desktop["production_readiness"]["backend_offline_ux_contract_status"],
            "frontend_offline_notice_ready_packaged_runtime_validation_pending",
        )
        self.assertTrue(desktop["production_readiness"]["backend_offline_ux_frontend_contract_ready"])
        self.assertTrue(desktop["production_readiness"]["config_log_paths_declared"])
        runtime_contract = desktop["production_runtime_contract"]
        runtime_contract_rows = {row["criterion"]: row for row in desktop["production_runtime_contract_rows"]}
        self.assertEqual(runtime_contract["schema_version"], "tauri_production_runtime_contract.v1")
        self.assertEqual(runtime_contract["status"], "runtime_contract_ready_packaged_validation_pending")
        self.assertEqual(runtime_contract["scope"], "path_policy_and_startup_contract_not_packaged_runtime_validation")
        self.assertEqual(runtime_contract["backend_startup_strategy"], "manual_fastapi_process_current_sidecar_pending")
        self.assertTrue(runtime_contract["manual_backend_launch_required"])
        self.assertFalse(runtime_contract["backend_sidecar_autostart_enabled"])
        self.assertTrue(runtime_contract["api_base_is_localhost"])
        self.assertTrue(runtime_contract["config_paths_declared"])
        self.assertTrue(runtime_contract["log_paths_declared"])
        self.assertFalse(runtime_contract["reads_config_values"])
        self.assertFalse(runtime_contract["writes_log_files"])
        self.assertFalse(runtime_contract["frontend_stores_tokens"])
        self.assertFalse(runtime_contract["token_key_frontend_exposure"])
        self.assertFalse(runtime_contract["packaged_runtime_validated"])
        self.assertFalse(runtime_contract["backend_offline_ui_packaged_runtime_verified"])
        self.assertFalse(runtime_contract["external_calls_triggered"])
        self.assertFalse(runtime_contract["tushare_called"])
        self.assertFalse(runtime_contract["deepseek_called"])
        self.assertFalse(runtime_contract["github_called"])
        self.assertTrue(runtime_contract["does_not_execute_trades"])
        self.assertTrue(runtime_contract["does_not_modify_strategy_action"])
        self.assertTrue(runtime_contract_rows["config_path_policy_declared"]["passed"])
        self.assertTrue(runtime_contract_rows["log_path_policy_declared"]["passed"])
        self.assertFalse(runtime_contract_rows["sidecar_autostart_validation_pending"]["passed"])
        self.assertFalse(runtime_contract_rows["packaged_backend_offline_ux_pending"]["passed"])
        self.assertIn("backend_offline_ux_contract", desktop)
        backend_offline_contract = desktop["backend_offline_ux_contract"]
        backend_offline_rows = {row["criterion"]: row for row in desktop["backend_offline_ux_rows"]}
        self.assertEqual(backend_offline_contract["schema_version"], "tauri_backend_offline_ux_contract.v1")
        self.assertEqual(
            backend_offline_contract["status"],
            "frontend_offline_notice_ready_packaged_runtime_validation_pending",
        )
        self.assertEqual(backend_offline_contract["scope"], "static_frontend_source_contract_not_packaged_runtime_qa")
        self.assertEqual(backend_offline_contract["backend_offline_error_code"], "backend_offline_or_unreachable")
        self.assertTrue(backend_offline_contract["frontend_contract_ready"])
        self.assertTrue(backend_offline_contract["api_client_fetch_error_fallback_ready"])
        self.assertTrue(backend_offline_contract["api_base_display_sanitized"])
        self.assertTrue(backend_offline_contract["offline_notice_component_ready"])
        self.assertTrue(backend_offline_contract["page_state_banner_integration_ready"])
        self.assertTrue(backend_offline_contract["offline_notice_style_ready"])
        self.assertFalse(backend_offline_contract["packaged_runtime_validated"])
        self.assertFalse(backend_offline_contract["backend_offline_ui_packaged_runtime_verified"])
        self.assertFalse(backend_offline_contract["external_calls_triggered"])
        self.assertFalse(backend_offline_contract["tushare_called"])
        self.assertFalse(backend_offline_contract["deepseek_called"])
        self.assertFalse(backend_offline_contract["github_called"])
        self.assertTrue(backend_offline_contract["does_not_execute_trades"])
        self.assertTrue(backend_offline_contract["does_not_modify_strategy_action"])
        self.assertTrue(backend_offline_rows["api_client_fetch_error_fallback"]["passed"])
        self.assertTrue(backend_offline_rows["api_base_display_sanitized"]["passed"])
        self.assertTrue(backend_offline_rows["offline_notice_component"]["passed"])
        self.assertTrue(backend_offline_rows["page_state_banner_integration"]["passed"])
        self.assertTrue(backend_offline_rows["offline_notice_style"]["passed"])
        self.assertFalse(backend_offline_rows["packaged_runtime_offline_qa_pending"]["passed"])
        self.assertIn("packaged_runtime_offline_qa_pending", backend_offline_contract["blockers"])
        self.assertIn("production_blocker_audit", desktop)
        blocker_audit = desktop["production_blocker_audit"]
        blocker_rows = {row["criterion"]: row for row in desktop["production_blocker_rows"]}
        self.assertEqual(blocker_audit["schema_version"], "tauri_production_package_blocker_audit.v1")
        self.assertEqual(blocker_audit["status"], "production_package_blocked")
        self.assertEqual(blocker_audit["scope"], "local_preflight_optional_build_artifact_detection_not_packaged_runtime_qa")
        self.assertFalse(blocker_audit["package_ready"])
        self.assertEqual(blocker_audit["tauri_build_verified"], build_artifact["binary_exists"])
        self.assertEqual(blocker_audit["tauri_build_artifact_status"], build_artifact["status"])
        self.assertEqual(blocker_audit["tauri_build_artifact_path"], build_artifact["binary_path"])
        self.assertEqual(blocker_audit["tauri_build_artifact_size_bytes"], build_artifact["binary_size_bytes"])
        self.assertFalse(blocker_audit["tauri_package_build_attempted"])
        self.assertTrue(blocker_audit["manual_backend_launch_required"])
        self.assertFalse(blocker_audit["backend_sidecar_autostart_enabled"])
        self.assertFalse(blocker_audit["backend_offline_ui_packaged_runtime_verified"])
        self.assertEqual(
            blocker_audit["backend_offline_ux_contract_status"],
            "frontend_offline_notice_ready_packaged_runtime_validation_pending",
        )
        self.assertTrue(blocker_audit["backend_offline_ux_frontend_contract_ready"])
        self.assertTrue(blocker_audit["config_log_paths_declared"])
        self.assertEqual(
            blocker_audit["production_runtime_contract_status"],
            "runtime_contract_ready_packaged_validation_pending",
        )
        self.assertFalse(blocker_audit["macos_signing_notarization_ready"])
        self.assertFalse(blocker_audit["frontend_stores_tokens"])
        self.assertFalse(blocker_audit["external_calls_triggered"])
        self.assertFalse(blocker_audit["tushare_called"])
        self.assertFalse(blocker_audit["deepseek_called"])
        self.assertFalse(blocker_audit["github_called"])
        self.assertTrue(blocker_audit["does_not_execute_trades"])
        self.assertTrue(blocker_audit["does_not_modify_strategy_action"])
        if build_artifact["binary_exists"]:
            self.assertNotIn("tauri_package_build_verified", blocker_audit["blockers"])
        else:
            self.assertIn("tauri_package_build_verified", blocker_audit["blockers"])
        self.assertIn("backend_startup_strategy", blocker_audit["blockers"])
        self.assertNotIn("config_and_log_paths_declared", blocker_audit["blockers"])
        self.assertIn("macos_signing_notarization_ready", blocker_audit["blockers"])
        self.assertEqual(blocker_rows["tauri_package_build_verified"]["passed"], build_artifact["binary_exists"])
        self.assertFalse(blocker_rows["backend_startup_strategy"]["passed"])
        self.assertFalse(blocker_rows["backend_offline_ui_runtime_verified"]["passed"])
        self.assertIn("frontend_contract_ready=True", blocker_rows["backend_offline_ui_runtime_verified"]["evidence"])
        self.assertTrue(blocker_rows["config_and_log_paths_declared"]["passed"])
        self.assertTrue(blocker_rows["frontend_secret_boundary"]["passed"])
        self.assertTrue(blocker_rows["startup_external_call_boundary"]["passed"])
        self.assertIn("packaged_runtime_qa_contract", desktop)
        qa_contract = desktop["packaged_runtime_qa_contract"]
        qa_rows = {row["criterion"]: row for row in desktop["packaged_runtime_qa_rows"]}
        self.assertEqual(qa_contract["schema_version"], "tauri_packaged_runtime_qa_contract.v1")
        self.assertEqual(qa_contract["status"], "packaged_runtime_qa_contract_ready_validation_pending")
        self.assertEqual(qa_contract["scope"], "local_static_qa_matrix_not_packaged_runtime_execution")
        self.assertTrue(qa_contract["qa_contract_ready"])
        self.assertFalse(qa_contract["production_package_ready"])
        self.assertFalse(qa_contract["packaged_runtime_validated"])
        self.assertFalse(qa_contract["browser_or_packaged_app_opened"])
        self.assertFalse(qa_contract["npm_or_cargo_executed"])
        self.assertFalse(qa_contract["config_values_read"])
        self.assertFalse(qa_contract["log_files_written"])
        self.assertFalse(qa_contract["external_calls_triggered"])
        self.assertFalse(qa_contract["tushare_called"])
        self.assertFalse(qa_contract["deepseek_called"])
        self.assertFalse(qa_contract["github_called"])
        self.assertTrue(qa_contract["does_not_execute_trades"])
        self.assertTrue(qa_contract["does_not_modify_strategy_action"])
        self.assertEqual(qa_contract["qa_matrix_count"], len(desktop["packaged_runtime_qa_rows"]))
        self.assertGreaterEqual(qa_contract["pending_qa_count"], 5)
        self.assertIn("release_artifact_qa", qa_rows)
        self.assertIn("backend_startup_strategy_qa", qa_rows)
        self.assertIn("backend_offline_ux_packaged_qa", qa_rows)
        self.assertIn("config_log_runtime_path_qa", qa_rows)
        self.assertIn("macos_signing_notarization_qa", qa_rows)
        self.assertTrue(qa_rows["startup_external_call_boundary"]["passed"])
        self.assertTrue(qa_rows["secret_bundle_boundary"]["passed"])
        self.assertEqual(desktop["counts"]["packaged_runtime_qa_matrix_count"], qa_contract["qa_matrix_count"])
        self.assertEqual(desktop["counts"]["packaged_runtime_pending_qa_count"], qa_contract["pending_qa_count"])
        self.assertTrue(desktop["runtime"]["packaged_runtime_qa_contract_ready"])
        self.assertEqual(desktop["runtime"]["packaged_runtime_pending_qa_count"], qa_contract["pending_qa_count"])
        self.assertTrue(desktop["policy"]["packaged_runtime_qa_contract_is_static"])
        self.assertFalse(desktop["runtime"]["production_package_ready"])
        self.assertGreater(desktop["runtime"]["production_blocker_count"], 0)
        self.assertEqual(desktop["runtime"]["tauri_build_verified"], build_artifact["binary_exists"])
        self.assertEqual(desktop["runtime"]["tauri_release_binary_present"], build_artifact["binary_exists"])
        self.assertEqual(desktop["runtime"]["tauri_release_binary_size_bytes"], build_artifact["binary_size_bytes"])
        self.assertEqual(desktop["runtime"]["production_package_build_artifact_detected"], build_artifact["binary_exists"])
        self.assertTrue(desktop["runtime"]["backend_offline_ux_frontend_contract_ready"])
        self.assertEqual(
            desktop["runtime"]["backend_offline_ux_contract_status"],
            "frontend_offline_notice_ready_packaged_runtime_validation_pending",
        )
        self.assertTrue(desktop["runtime"]["production_runtime_contract_declared"])
        self.assertTrue(desktop["runtime"]["production_runtime_config_paths_declared"])
        self.assertTrue(desktop["runtime"]["production_runtime_log_paths_declared"])
        self.assertFalse(desktop["runtime"]["production_runtime_reads_config_values"])
        self.assertFalse(desktop["runtime"]["production_runtime_writes_log_files"])
        self.assertEqual([row["command"] for row in desktop["dev_launch_plan"][:3]], [
            "scripts/dev_server.sh",
            "cd desktop && npm run dev",
            "cd desktop && npm run tauri dev",
        ])
        self.assertEqual(desktop["production_launch_plan"][0]["command"], "cd desktop && npm run build")
        self.assertEqual(desktop["production_launch_plan"][1]["command"], "cd desktop && npm run tauri build")
        self.assertTrue(all(row["manual"] for row in desktop["dev_launch_plan"]))
        self.assertTrue(all(row["manual"] for row in desktop["production_launch_plan"]))
        self.assertTrue(all(row["external_calls_triggered"] is False for row in desktop["dev_launch_plan"]))
        self.assertTrue(all(row["external_calls_triggered"] is False for row in desktop["production_launch_plan"]))
        self.assertTrue(all(row["loads_token_or_key"] is False for row in desktop["dev_launch_plan"]))
        self.assertTrue(all(row["loads_token_or_key"] is False for row in desktop["production_launch_plan"]))
        self.assertTrue(desktop["does_not_execute_trades"])
        self.assertTrue(desktop["does_not_modify_strategy_action"])
        self.assertEqual(desktop["call_ledger"][0]["api"], "local_desktop_shell_preflight_cache")
        file_labels = {row["label"] for row in desktop["file_rows"]}
        self.assertIn("react_app", file_labels)
        self.assertIn("tauri_config", file_labels)
        self.assertIn("cargo_toml", file_labels)
        self.assertIn("cargo_lock", file_labels)
        self.assertIn("tauri_main", file_labels)
        self.assertIn("tauri_icon", file_labels)
        command_names = {row["command"] for row in desktop["command_rows"]}
        self.assertEqual(command_names, {"node", "npm", "rustc", "cargo"})
        desktop_dump = json.dumps(desktop, ensure_ascii=False)
        self.assertNotIn("DEEPSEEK_API_KEY", desktop_dump)
        self.assertNotIn("TUSHARE_TOKEN", desktop_dump)
        self.assertNotIn("GITHUB_TOKEN", desktop_dump)
        self.assertNotIn("COMMAND_CENTER_REDIS_URL", desktop_dump)

        self.assertEqual(model_strategy["packet_key"], "command_center_3_deepseek_model_strategy_cache")
        self.assertEqual(model_strategy["mode"], "cache_only")
        self.assertTrue(model_strategy["cache_only"])
        self.assertTrue(model_strategy["read_only"])
        self.assertEqual(model_strategy["counts"]["purpose_count"], 7)
        self.assertFalse(model_strategy["external_calls_triggered"])
        self.assertFalse(model_strategy["tushare_called"])
        self.assertFalse(model_strategy["deepseek_called"])
        self.assertFalse(model_strategy["github_called"])
        self.assertTrue(model_strategy["policy"]["does_not_call_deepseek"])
        self.assertTrue(model_strategy["policy"]["model_names_are_configurable"])
        self.assertFalse(model_strategy["policy"]["callsite_hardcoding_allowed"])
        self.assertTrue(model_strategy["does_not_execute_trades"])
        self.assertTrue(model_strategy["does_not_modify_strategy_action"])
        self.assertEqual(model_strategy["call_ledger"][0]["api"], "local_deepseek_model_strategy_cache")
        strategy_dump = json.dumps(model_strategy, ensure_ascii=False).lower()
        self.assertNotIn("deepseek_api_key", strategy_dump)
        self.assertNotIn("tushare_token", strategy_dump)
        self.assertNotIn("github_token", strategy_dump)
        self.assertNotIn("bearer ", strategy_dump)

        json.dumps({"factor": factor, "serenity": serenity, "next": next_session, "migration": migration, "desktop": desktop, "model_strategy": model_strategy}, ensure_ascii=False)

    def test_packet_service_reads_snapshot_alias_without_external_calls(self):
        self._with_snapshot_cache(
            {
                "moneyflow_packet": {
                    "status": "ready",
                    "main_net_yi": 1.25,
                }
            }
        )

        packet = packet_service.read_packet("command_center_moneyflow_packet")

        self.assertEqual(packet["packet_key"], "command_center_moneyflow_packet")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["source_cache_key"], "moneyflow_packet")
        self.assertEqual(packet["cache_source"], "stock_ming_snapshot")
        self.assertFalse(packet["cache_api_external_calls_triggered"])
        self.assertFalse(packet["cache_api_tushare_called"])
        self.assertFalse(packet["cache_api_deepseek_called"])

    def test_factor_quant_cache_links_local_snapshot_context(self):
        self._with_meta_store()
        self._with_snapshot_cache(
            {
                "a_share_fact_lineage_summary": {"items": [{"fact_key": "daily"}]},
                "strategy_packet": {"status": "ready", "action": "wait"},
                "decision_packet": {"status": "ready"},
                "quant_packet": {"status": "ready"},
            }
        )

        packet = packet_service.build_factor_quant_cache()

        self.assertEqual(packet["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertEqual(packet["cache_source"], "local_builder_with_snapshot_context")
        self.assertTrue(packet["source_snapshot_available"])
        self.assertTrue(packet["linked_packets"]["a_share_fact_lineage_summary"])
        self.assertTrue(packet["linked_packets"]["strategy_execution_packet"])
        self.assertTrue(packet["linked_packets"]["decision_packet"])
        self.assertTrue(packet["linked_packets"]["legacy_quant_packet"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])

    def test_next_session_cache_missing_still_exposes_echarts_contract(self):
        self._with_snapshot_cache({})

        packet = packet_service.build_next_session_cache()
        chart = packet["chart_payload"]
        contract = chart["chart_contract"]

        self.assertEqual(packet["packet_key"], "command_center_next_session_projection_packet")
        self.assertEqual(packet["status"], "cache_missing")
        self.assertEqual(chart["status"], "missing")
        self.assertEqual(contract["schema_version"], "next_session_echarts_payload.v1")
        self.assertEqual(contract["renderer"], "ECharts")
        self.assertTrue(contract["cache_only"])
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertFalse(contract["frontend_computes_trade_action"])
        self.assertTrue(contract["does_not_modify_action"])
        self.assertTrue(contract["does_not_modify_operation_zones"])
        self.assertEqual(contract["interaction_contract"]["source_endpoint"], "GET /api/next-session/cache")
        self.assertEqual(contract["interaction_contract"]["click_path_displays"], "trigger_condition")
        self.assertEqual(contract["interaction_contract"]["click_zone_displays"], "guardrail")
        self.assertTrue(contract["interaction_contract"]["y_axis_dynamic_scale"])
        self.assertTrue(contract["interaction_contract"]["frontend_render_only"])
        self.assertTrue(contract["interaction_contract"]["frontend_must_not_calculate_action"])
        self.assertEqual(contract["series_counts"]["historical_points"], 0)
        self.assertEqual(chart["interaction_readiness_audit"]["schema_version"], "next_session_interaction_readiness.v1")
        self.assertEqual(chart["interaction_readiness_audit"]["status"], "interaction_blocked")
        self.assertGreaterEqual(chart["interaction_readiness_audit"]["blocking_count"], 1)
        self.assertFalse(chart["interaction_readiness_audit"]["streamlit_parity_complete"])
        self.assertFalse(chart["interaction_readiness_audit"]["production_replacement_complete"])
        self.assertFalse(chart["interaction_readiness_audit"]["external_calls_triggered"])
        self.assertIn("chart_payload_available", {row["key"] for row in chart["interaction_readiness_rows"]})
        self.assertEqual(chart["chart_summary"]["renderer"], "ECharts")
        self.assertFalse(chart["chart_summary"]["has_drawable_data"])
        self.assertEqual(chart["chart_summary"]["interaction_readiness_status"], "interaction_blocked")
        self.assertEqual(packet["chart_summary"]["historical_point_count"], 0)
        self.assertFalse(packet["chart_summary"]["frontend_computes_trade_action"])
        self.assertFalse(packet["chart_summary"]["external_calls_triggered"])
        self.assertFalse(packet["chart_summary"]["tushare_called"])
        self.assertFalse(packet["chart_summary"]["deepseek_called"])
        self.assertFalse(packet["chart_summary"]["github_called"])
        self.assertTrue(packet["chart_summary"]["does_not_execute_trades"])
        self.assertTrue(packet["chart_summary"]["does_not_modify_operation_zones"])
        self.assertIn("GET /api/next-session/cache 不触发 Tushare", " ".join(contract["guardrails"]))
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])

    def test_next_session_cache_missing_does_not_promote_legacy_projection(self):
        self._with_snapshot_cache(
            {
                "projection_packet": {
                    "base_date": "2026-06-09",
                    "historical_source_label": "当前价锚定的模拟历史段",
                    "historical": [{"t": -1, "value": 99}, {"t": 0, "value": 100}],
                    "paths": [{"name": "中性路径", "points": [{"t": 0, "value": 100}, {"t": 1, "value": 101}]}],
                    "position_context": {"current_price": 100, "cost_price": 96},
                    "reference_lines": [{"key": "current_price", "label": "当前价基准", "value": 100}],
                    "status": "ready",
                    "summary": "legacy projection exists",
                }
            }
        )

        packet = packet_service.build_next_session_cache()

        self.assertEqual(packet["packet_key"], "command_center_next_session_projection_packet")
        self.assertEqual(packet["status"], "cache_missing")
        self.assertTrue(packet["source_snapshot_available"])
        self.assertTrue(packet["legacy_projection_cache"]["available"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_modify_action"])
        self.assertEqual(packet["chart_payload"]["status"], "ready")
        self.assertFalse(packet["chart_payload"]["is_exact_next_session_packet"])
        self.assertFalse(packet["chart_payload"]["uses_real_daily_close"])
        self.assertEqual(packet["chart_payload"]["historical_points"][0]["x"], "T-1")
        self.assertEqual(packet["chart_payload"]["scenario_series"][0]["scenario_name"], "中性路径")
        self.assertIn("前端不得据此计算交易动作", " ".join(packet["chart_payload"]["warnings"]))
        contract = packet["chart_payload"]["chart_contract"]
        self.assertEqual(contract["schema_version"], "next_session_echarts_payload.v1")
        self.assertEqual(contract["renderer"], "ECharts")
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertFalse(contract["frontend_computes_trade_action"])
        self.assertTrue(contract["does_not_modify_action"])
        self.assertTrue(contract["does_not_modify_operation_zones"])
        self.assertEqual(contract["series_counts"]["historical_points"], 2)
        self.assertTrue(packet["chart_summary"]["has_drawable_data"])
        self.assertFalse(packet["chart_summary"]["is_exact_next_session_packet"])
        self.assertEqual(packet["chart_summary"]["historical_point_count"], 2)
        self.assertEqual(packet["chart_summary"]["scenario_series_count"], 1)

    def test_next_session_cache_maps_exact_chart_render_model_for_echarts(self):
        self._with_snapshot_cache(
            {
                "command_center_next_session_projection_packet": {
                    "packet_key": "command_center_next_session_projection_packet",
                    "status": "ready",
                    "chart_render_model": {
                        "historical_series": [
                            {"x": "2026-06-08", "price": 10.0},
                            {"x": "2026-06-09", "close": 10.4},
                        ],
                        "scenario_series": [
                            {
                                "scenario_key": "neutral",
                                "scenario_name": "中性路径",
                                "trigger_condition": "放量但不追高",
                                "confidence_note": "中性路径只作基准",
                                "points": [{"x": "T0", "price": 10.4}, {"x": "T+1_close", "price": 10.8}],
                            }
                        ],
                        "cost_line": 9.8,
                        "current_price_line": 10.4,
                        "limit_lines": [{"label": "涨停参考", "value": 11.44}, {"label": "跌停参考", "value": 9.36}],
                        "support_lines": [9.9],
                        "resistance_lines": [11.0],
                        "operation_zone_overlays": [
                            {
                                "zone_key": "reduce_watch_zone",
                                "zone_name": "止盈/减仓观察区",
                                "price_range": [10.9, 11.3],
                                "action_mode": "condition_only",
                            }
                        ],
                        "y_axis_range": [9.0, 12.0],
                    },
                    "operation_zones": [{"zone_key": "fallback_should_not_win", "price_range": [1, 2]}],
                    "position_context": {"conflict_flags": ["cost_price_conflict"], "source_packet": "position_profile"},
                    "data_trust_summary": {
                        "facts": [{"fact_key": "moneyflow", "call_status": "verified_present"}],
                        "human_summary": ["真实日线：已接入", "持仓：存在冲突，需先核验"],
                        "deepseek": {"label": "DeepSeek", "status": "not_called"},
                    },
                    "deepseek_synthesis": {"status": "not_called"},
                }
            }
        )

        packet = packet_service.build_next_session_cache()
        chart = packet["chart_payload"]

        self.assertEqual(packet["status"], "ready")
        self.assertTrue(chart["is_exact_next_session_packet"])
        self.assertEqual(chart["historical_points"][0]["x"], "2026-06-08")
        self.assertEqual(chart["historical_points"][1]["price"], 10.4)
        self.assertEqual(chart["operation_zones"][0]["zone_key"], "reduce_watch_zone")
        self.assertEqual(chart["operation_zones"][0]["price_range"], [10.9, 11.3])
        self.assertIn("当前价", {item["label"] for item in chart["reference_lines"]})
        self.assertIn("涨停参考", {item["label"] for item in chart["reference_lines"]})
        self.assertIn("支撑 1", {item["label"] for item in chart["reference_lines"]})
        self.assertTrue(packet["does_not_modify_action"])
        self.assertTrue(packet["does_not_modify_operation_zones"])
        self.assertFalse(packet["external_calls_triggered"])
        contract = chart["chart_contract"]
        self.assertEqual(contract["source_packet"], "command_center_next_session_projection_packet")
        self.assertFalse(contract["external_calls_triggered"])
        self.assertFalse(contract["tushare_called"])
        self.assertFalse(contract["deepseek_called"])
        self.assertFalse(contract["github_called"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertEqual(contract["series_counts"]["scenario_series"], 1)
        self.assertEqual(contract["series_counts"]["reference_lines"], 6)
        self.assertEqual(contract["series_counts"]["operation_zones"], 1)
        self.assertEqual(contract["series_counts"]["scenario_anchor_rows"], 1)
        self.assertEqual(contract["interaction_contract"]["hover_displays"], ["price", "source", "trigger_condition", "risk_note"])
        self.assertEqual(contract["interaction_contract"]["source_endpoint"], "GET /api/next-session/cache")
        self.assertTrue(contract["interaction_contract"]["frontend_render_only"])
        self.assertEqual(contract["interaction_contract"]["click_reference_displays"], "line_source")
        self.assertTrue(chart["chart_summary"]["is_exact_next_session_packet"])
        self.assertEqual(chart["latest_close_anchor"]["price"], 10.4)
        self.assertEqual(chart["scenario_anchor_rows"][0]["latest_close"], 10.4)
        self.assertTrue(chart["scenario_anchor_rows"][0]["anchored_to_latest_close"])
        self.assertEqual(chart["scenario_anchor_rows"][0]["trigger_condition"], "放量但不追高")
        self.assertEqual(chart["reference_line_rows"][0]["frontend_mutable"], False)
        self.assertEqual(chart["zone_interaction_rows"][0]["click_displays"], "guardrail")
        self.assertEqual(chart["interaction_readiness_audit"]["schema_version"], "next_session_interaction_readiness.v1")
        self.assertEqual(chart["interaction_readiness_audit"]["status"], "interaction_contract_ready_parity_pending")
        self.assertEqual(chart["interaction_readiness_audit"]["blocking_count"], 0)
        self.assertFalse(chart["interaction_readiness_audit"]["streamlit_parity_complete"])
        self.assertFalse(chart["interaction_readiness_audit"]["production_replacement_complete"])
        self.assertFalse(chart["interaction_readiness_audit"]["external_calls_triggered"])
        readiness_by_key = {row["key"]: row for row in chart["interaction_readiness_rows"]}
        self.assertEqual(readiness_by_key["hover_evidence_contract"]["status"], "ready")
        self.assertEqual(readiness_by_key["zone_click_guardrail"]["status"], "ready")
        self.assertEqual(readiness_by_key["legacy_streamlit_parity"]["status"], "pending")
        self.assertEqual(chart["position_conflict"]["conflict_flags"], ["cost_price_conflict"])
        self.assertEqual(chart["data_trust_summary"]["facts"][0]["fact_key"], "moneyflow")
        self.assertEqual(chart["deepseek_status"], "not_called")
        self.assertEqual(chart["chart_maturity"]["status"], "ready")
        self.assertTrue(chart["chart_maturity"]["position_conflict"])
        self.assertEqual(chart["chart_maturity"]["scenario_anchored_count"], 1)
        self.assertTrue(packet["chart_summary"]["is_exact_next_session_packet"])
        self.assertTrue(packet["chart_summary"]["uses_real_daily_close"])
        self.assertEqual(packet["chart_summary"]["operation_zone_count"], 1)
        self.assertEqual(packet["chart_summary"]["maturity_status"], "ready")
        self.assertTrue(packet["chart_summary"]["position_conflict"])
        self.assertEqual(packet["chart_summary"]["scenario_anchored_count"], 1)
        self.assertEqual(packet["chart_summary"]["deepseek_status"], "not_called")
        self.assertEqual(packet["chart_summary"]["interaction_readiness_status"], "interaction_contract_ready_parity_pending")
        self.assertEqual(packet["chart_summary"]["interaction_blocking_count"], 0)
        self.assertFalse(packet["chart_summary"]["streamlit_parity_complete"])
        self.assertFalse(packet["chart_summary"]["production_replacement_complete"])
        self.assertFalse(packet["chart_summary"]["frontend_computes_trade_action"])
        self.assertIn("前端不得修改 strategy action", " ".join(contract["guardrails"]))

    def test_next_session_cache_exact_packet_without_chart_model_still_has_contract(self):
        self._with_snapshot_cache(
            {
                "command_center_next_session_projection_packet": {
                    "packet_key": "command_center_next_session_projection_packet",
                    "status": "ready",
                }
            }
        )

        packet = packet_service.build_next_session_cache()
        chart = packet["chart_payload"]
        contract = chart["chart_contract"]

        self.assertEqual(chart["status"], "missing")
        self.assertTrue(chart["is_exact_next_session_packet"])
        self.assertEqual(contract["source_packet"], "command_center_next_session_projection_packet")
        self.assertFalse(contract["external_calls_triggered"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertFalse(contract["frontend_computes_trade_action"])
        self.assertEqual(contract["series_counts"]["historical_points"], 0)
        self.assertFalse(packet["chart_summary"]["has_drawable_data"])
        self.assertTrue(packet["chart_summary"]["is_exact_next_session_packet"])
        self.assertIn("精确次日操作图谱 packet 未提供 chart_render_model", " ".join(chart["warnings"]))

    def test_next_session_cache_normalizes_existing_chart_payload_contract(self):
        self._with_snapshot_cache(
            {
                "command_center_next_session_projection_packet": {
                    "packet_key": "command_center_next_session_projection_packet",
                    "status": "ready",
                    "chart_payload": {
                        "status": "ready",
                        "historical_points": [{"x": "2026-06-10", "price": 10.4}],
                    },
                }
            }
        )

        packet = packet_service.build_next_session_cache()
        chart = packet["chart_payload"]
        contract = chart["chart_contract"]

        self.assertEqual(chart["historical_points"][0]["price"], 10.4)
        self.assertEqual(chart["source_packet"], "command_center_next_session_projection_packet")
        self.assertEqual(contract["series_counts"]["historical_points"], 1)
        self.assertEqual(contract["renderer"], "ECharts")
        self.assertFalse(contract["external_calls_triggered"])
        self.assertTrue(contract["does_not_execute_trades"])
        self.assertTrue(contract["does_not_modify_action"])
        self.assertTrue(contract["does_not_modify_operation_zones"])
        self.assertEqual(packet["chart_summary"]["historical_point_count"], 1)
        self.assertTrue(packet["chart_summary"]["has_drawable_data"])

    def test_next_session_cache_reads_persisted_sqlite_packet_without_snapshot(self):
        self._with_meta_store()
        from storage.sqlite_meta import SQLiteMetaStore

        SQLiteMetaStore(packet_service.SQLITE_META_PATH).write_packet(
            "command_center_next_session_projection_packet",
            {
                "packet_key": "command_center_next_session_projection_packet",
                "status": "ready",
                "trade_date": "20260610",
                "chart_render_model": {
                    "historical_series": [{"x": "2026-06-10", "price": 10.4}],
                    "scenario_series": [
                        {
                            "scenario_key": "neutral",
                            "scenario_name": "中性路径",
                            "points": [{"x": "T+1", "price": 10.8}],
                        }
                    ],
                    "current_price_line": 10.4,
                    "cost_line": 9.8,
                },
            },
        )

        packet = packet_service.build_next_session_cache()

        self.assertEqual(packet["packet_key"], "command_center_next_session_projection_packet")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(packet["does_not_modify_action"])
        self.assertTrue(packet["does_not_modify_operation_zones"])
        self.assertTrue(packet["chart_payload"]["is_exact_next_session_packet"])
        self.assertEqual(packet["chart_payload"]["historical_points"][0]["price"], 10.4)

    def test_serenity_cache_reads_persisted_sqlite_packet_without_probe(self):
        self._with_meta_store()
        from storage.sqlite_meta import SQLiteMetaStore

        SQLiteMetaStore(packet_service.SQLITE_META_PATH).write_packet(
            "command_center_serenity_method_radar_packet",
            {
                "packet_key": "command_center_serenity_method_radar_packet",
                "schema_version": "serenity_method_radar.v1",
                "status": "ready",
                "github_status": "not_checked",
                "repositories": [{"repo": "muxuuu/serenity-skill", "source_type": "user_screenshot_baseline"}],
                "decision_usage_policy": {"display_only": True, "enters_strategy_action": False},
                "deepseek_called": False,
                "github_called": False,
            },
        )

        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).get("/api/serenity/cache").json()

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["cache_source"], "sqlite_meta")
        self.assertEqual(response["data"]["repositories"][0]["repo"], "muxuuu/serenity-skill")
        self.assertFalse(response["data"]["github_called"])
        self.assertFalse(response["data"]["deepseek_called"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_serenity_method_radar_cache")
        self.assertEqual(response["call_ledger"][0]["request_params_safe"]["cache_source"], "sqlite_meta")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertFalse(response["call_ledger"][0]["github_called"])
        self.assertFalse(response["call_ledger"][0]["deepseek_called"])
        self.assertIn("GET /api/serenity/cache", response["warnings"][0])

    def test_chokepoint_cache_reads_persisted_sqlite_packet_without_deepseek(self):
        self._with_meta_store()
        from storage.sqlite_meta import SQLiteMetaStore

        SQLiteMetaStore(packet_service.SQLITE_META_PATH).write_packet(
            "command_center_chokepoint_scan_packet",
            {
                "packet_key": "command_center_chokepoint_scan_packet",
                "schema_version": "chokepoint_scan.v1",
                "status": "ready",
                "theme": "英伟达金刚石散热",
                "technical_nodes": [{"name": "半导体级 CVD 衬底"}],
                "enters_strategy_action": False,
                "enters_next_session_projection": False,
                "deepseek_called": False,
            },
        )

        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).get("/api/chokepoint/cache").json()

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["cache_source"], "sqlite_meta")
        self.assertEqual(response["data"]["theme"], "英伟达金刚石散热")
        self.assertFalse(response["data"]["deepseek_called"])
        self.assertFalse(response["data"]["enters_strategy_action"])
        self.assertFalse(response["data"]["enters_next_session_projection"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_chokepoint_scan_cache")
        self.assertEqual(response["call_ledger"][0]["request_params_safe"]["cache_source"], "sqlite_meta")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertFalse(response["call_ledger"][0]["deepseek_called"])
        self.assertFalse(response["call_ledger"][0]["tushare_called"])
        self.assertFalse(response["call_ledger"][0]["github_called"])
        self.assertIn("GET /api/chokepoint/cache", response["warnings"][0])

    def test_packet_index_exposes_snapshot_keys(self):
        self._with_snapshot_cache({"moneyflow_packet": {"status": "ready"}})

        index = packet_service.list_packets()

        self.assertTrue(index["snapshot_available"])
        self.assertIn("moneyflow_packet", index["snapshot_available_keys"])
        self.assertIn("command_center_moneyflow_packet", index["snapshot_alias_keys"])
        self.assertIn("command_center_moneyflow_packet", index["available_cache_keys"])
        self.assertEqual(index["storage_catalog"]["cache_endpoint"], "GET /api/storage/catalog")
        self.assertEqual(index["storage_catalog"]["dataset_count"], 6)
        self.assertEqual({item["dataset"] for item in index["storage_catalog"]["dataset_catalog"]}, {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertFalse(index["storage_catalog"]["external_calls_triggered"])
        self.assertFalse(index["storage_catalog"]["tushare_called"])
        self.assertTrue(index["storage_catalog"]["does_not_execute_trades"])
        self.assertEqual(index["call_ledger"][0]["storage_dataset_count"], 6)

    def test_packet_index_exposes_sqlite_packet_metadata(self):
        self._with_meta_store()
        from storage.sqlite_meta import SQLiteMetaStore

        packet_key = "custom_local_research_packet"
        SQLiteMetaStore(packet_service.SQLITE_META_PATH).write_packet(
            packet_key,
            {"packet_key": packet_key, "schema_version": "custom.v1", "status": "ready"},
        )

        index = packet_service.list_packets()

        self.assertTrue(index["sqlite_meta"]["sqlite_meta_available"])
        self.assertIn(packet_key, index["persisted_packet_keys"])
        self.assertIn(packet_key, index["available_cache_keys"])
        self.assertIn(packet_key, {row["packet_key"] for row in index["packet_source_rows"]})
        source_row = next(row for row in index["packet_source_rows"] if row["packet_key"] == packet_key)
        self.assertTrue(source_row["sqlite_meta"])
        self.assertFalse(source_row["local_builder"])
        self.assertEqual(source_row["read_priority"], "sqlite_meta > snapshot > local_builder > missing")
        self.assertEqual(index["sqlite_meta"]["packet_metadata"][0]["schema_version"], "custom.v1")
        self.assertTrue(index["sqlite_meta"]["does_not_return_payload_json"])
        self.assertIn("metadata_safe_columns", index["sqlite_meta"])
        self.assertIn("metadata_source_rows", index["sqlite_meta"])
        self.assertEqual({row["source"] for row in index["sqlite_meta"]["metadata_source_rows"]}, {"packet_metadata", "task_metadata"})
        self.assertTrue(all(row["payload_json_returned"] is False for row in index["sqlite_meta"]["metadata_source_rows"]))
        self.assertEqual(index["sqlite_meta"]["packet_status_counts"]["ready"], 1)
        self.assertIn("storage_source", index["sqlite_meta"]["metadata_safe_columns"]["task_metadata"])
        self.assertFalse(index["cache_api_policy"]["get_cache_external_calls"])

        packet = packet_service.read_packet(packet_key)

        self.assertEqual(packet["packet_key"], packet_key)
        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertFalse(packet["external_calls_triggered"])

    def test_packet_endpoint_reads_sqlite_only_packet(self):
        self._with_meta_store()
        from storage.sqlite_meta import SQLiteMetaStore

        packet_key = "custom_sqlite_only_packet"
        SQLiteMetaStore(packet_service.SQLITE_META_PATH).write_packet(
            packet_key,
            {"packet_key": packet_key, "schema_version": "custom.sqlite.v1", "status": "ready"},
        )

        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).get(f"/api/packets/{packet_key}").json()

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["packet_key"], packet_key)
        self.assertEqual(response["data"]["cache_source"], "sqlite_meta")
        self.assertFalse(response["data"]["external_calls_triggered"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_packet_cache_read")
        self.assertEqual(response["call_ledger"][0]["cache_source"], "sqlite_meta")
        self.assertEqual(response["call_ledger"][0]["read_priority"], "sqlite_meta > snapshot > local_builder > missing")
        self.assertEqual(response["call_ledger"][0]["source_resolution"], "sqlite_meta")
        self.assertTrue(response["call_ledger"][0]["sqlite_meta_selected"])
        self.assertFalse(response["call_ledger"][0]["snapshot_selected"])
        self.assertFalse(response["call_ledger"][0]["local_builder_selected"])
        self.assertFalse(response["call_ledger"][0]["cache_missing_selected"])
        self.assertFalse(response["call_ledger"][0]["external_calls_triggered"])
        self.assertFalse(response["call_ledger"][0]["tushare_called"])
        self.assertFalse(response["call_ledger"][0]["deepseek_called"])
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertTrue(response["call_ledger"][0]["does_not_execute_trades"])
        self.assertTrue(response["call_ledger"][0]["does_not_modify_strategy_action"])

    def test_packet_endpoint_prefers_sqlite_packet_over_snapshot(self):
        self._with_meta_store()
        self._with_snapshot_cache(
            {
                "custom_priority_packet": {
                    "packet_key": "custom_priority_packet",
                    "status": "stale_snapshot",
                    "value": "snapshot",
                }
            }
        )
        from storage.sqlite_meta import SQLiteMetaStore

        SQLiteMetaStore(packet_service.SQLITE_META_PATH).write_packet(
            "custom_priority_packet",
            {
                "packet_key": "custom_priority_packet",
                "schema_version": "custom.sqlite.v1",
                "status": "fresh_sqlite",
                "value": "sqlite",
            },
        )

        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).get("/api/packets/custom_priority_packet").json()

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["status"], "fresh_sqlite")
        self.assertEqual(response["data"]["value"], "sqlite")
        self.assertEqual(response["data"]["cache_source"], "sqlite_meta")
        self.assertEqual(response["call_ledger"][0]["cache_source"], "sqlite_meta")
        self.assertEqual(response["call_ledger"][0]["source_resolution"], "sqlite_meta")
        self.assertTrue(response["call_ledger"][0]["sqlite_meta_selected"])
        self.assertFalse(response["call_ledger"][0]["external_calls_triggered"])
        self.assertFalse(response["call_ledger"][0]["tushare_called"])
        self.assertFalse(response["call_ledger"][0]["deepseek_called"])

    def test_packet_endpoint_missing_packet_redacts_sensitive_packet_key(self):
        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).get("/api/packets/token=SHOULD_DROP").json()

        self.assertFalse(response["ok"])
        self.assertIsNone(response["data"])
        self.assertEqual(response["error"]["code"], "cache_missing")
        self.assertEqual(response["error"]["details"]["packet_key"], "[redacted_sensitive_text]")
        self.assertEqual(response["call_ledger"][0]["api"], "local_packet_cache_read")
        self.assertEqual(response["call_ledger"][0]["packet_key"], "[redacted_sensitive_text]")
        self.assertEqual(response["call_ledger"][0]["call_status"], "cache_missing")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertFalse(response["call_ledger"][0]["external_calls_triggered"])
        self.assertFalse(response["call_ledger"][0]["tushare_called"])
        self.assertFalse(response["call_ledger"][0]["deepseek_called"])
        self.assertFalse(response["call_ledger"][0]["github_called"])
        self.assertTrue(response["call_ledger"][0]["does_not_execute_trades"])
        self.assertTrue(response["call_ledger"][0]["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

    def test_packet_index_endpoint_exposes_top_level_cache_lineage(self):
        self._with_snapshot_cache({"moneyflow_packet": {"status": "ready"}})

        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).get("/api/packets").json()

        self.assertTrue(response["ok"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_packet_registry_cache")
        self.assertEqual(response["call_ledger"][0]["source_type"], "local_cache_index")
        self.assertEqual(response["call_ledger"][0]["read_priority"], "sqlite_meta > snapshot > local_builder > missing")
        self.assertTrue(response["call_ledger"][0]["snapshot_available"])
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertFalse(response["call_ledger"][0]["external_calls_triggered"])
        self.assertFalse(response["call_ledger"][0]["tushare_called"])
        self.assertFalse(response["call_ledger"][0]["deepseek_called"])
        self.assertFalse(response["call_ledger"][0]["github_called"])
        self.assertTrue(response["call_ledger"][0]["does_not_execute_trades"])
        self.assertTrue(response["call_ledger"][0]["does_not_modify_strategy_action"])
        self.assertTrue(response["call_ledger"][0]["does_not_return_payload_json"])
        self.assertIn("sqlite_packet_count", response["call_ledger"][0])
        self.assertIn("sqlite_task_count", response["call_ledger"][0])
        self.assertIn("metadata_safe_columns_exposed", response["call_ledger"][0])
        self.assertFalse(response["call_ledger"][0]["deepseek_called"])
        self.assertTrue(response["call_ledger"][0]["does_not_modify_strategy_action"])
        self.assertEqual(response["data"]["call_ledger"][0]["api"], "local_packet_registry_cache")
        self.assertIn("command_center_moneyflow_packet", response["data"]["available_cache_keys"])
        self.assertEqual(response["data"]["storage_catalog"]["dataset_count"], 6)
        self.assertEqual(response["call_ledger"][0]["storage_dataset_count"], 6)

    def test_market_context_cache_reads_market_packets_without_refreshing_quotes(self):
        self._with_snapshot_cache(
            {
                "market_packet": {
                    "status": "ready",
                    "summary": "盘面中性偏强",
                    "trade_date": "20260610",
                    "verified_sources": ["moneyflow"],
                    "missing_sources": ["chip"],
                    "api_key": "SHOULD_DROP",
                },
                "market_profile_evidence": {"status": "ready", "market_label": "震荡", "summary": "只读画像"},
                "moneyflow_packet": {"status": "ready", "ticker": "002008.SZ", "main_net_yi": 1.2, "authorization": "Bearer SHOULD_DROP"},
                "margin_packet": {"status": "ready", "margin_balance_yi": 4.5, "leverage_state": "温和"},
                "dragon_tiger_packet": {"status": "ready", "net_buy_amount_yi": 0.8, "inst_rows": [{"name": "机构席位"}]},
                "limit_emotion_packet": {"status": "ready", "emotion_state": "修复", "limit_records": [{"date": "20260610"}]},
                "chip_packet": {"status": "ready", "winner_rate": 0.62, "chips_top_areas": [{"area": "100-105"}]},
                "etf_packet": {"status": "ready", "risk_state": "观察", "etf_replacement_hint": "仅替代说明"},
            }
        )

        packet = market_service.read_market_context_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_market_context_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["trade_date"], "20260610")
        self.assertEqual(packet["counts"]["packet_count"], 8)
        self.assertEqual(packet["counts"]["verified_source_count"], 1)
        self.assertEqual(packet["counts"]["missing_source_count"], 1)
        self.assertEqual(packet["counts"]["limit_record_count"], 1)
        self.assertEqual(packet["counts"]["dragon_tiger_inst_count"], 1)
        self.assertEqual(packet["counts"]["chip_area_count"], 1)
        self.assertEqual(packet["packet_rows"][2]["packet_key"], "moneyflow_packet")
        self.assertNotIn("api_key", packet["market_packet"])
        self.assertNotIn("authorization", packet["moneyflow_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_refresh_quotes"])
        self.assertTrue(packet["policy"]["does_not_refresh_moneyflow"])
        self.assertTrue(packet["policy"]["market_context_is_not_trade_instruction"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_market_context_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_discipline_loop_cache_reads_local_discipline_without_running_backtest(self):
        self._with_snapshot_cache(
            {
                "discipline_packet": {
                    "status": "ready",
                    "score": 72,
                    "win_rate": 0.58,
                    "max_drawdown": -0.12,
                    "metric_items": [{"label": "胜率", "value": 0.58, "api_key": "SHOULD_DROP"}],
                    "key_rules": ["不追高", {"rule": "不裸露强动作", "authorization": "Bearer SHOULD_DROP"}],
                    "token": "SHOULD_DROP",
                },
                "decision_loop_status": {
                    "status": "ready",
                    "ready_count": 2,
                    "blocked_count": 1,
                    "waiting_count": 3,
                    "items": [{"label": "策略已生成"}],
                    "recovery_queue": [{"label": "补数据"}],
                    "recovery_actions": [{"label": "手动刷新"}],
                },
                "today_action": {"overall_action": "只观察", "risk_level": "中"},
                "decision_packet": {"overall_action": "只观察", "api_key": "SHOULD_DROP"},
                "strategy_packet": {"action": "等待", "authorization": "Bearer SHOULD_DROP"},
                "full_refresh_steps": [
                    {"key": "market", "status": "completed", "label": "完成"},
                    {"key": "discipline", "status": "skipped", "label": "已跳过"},
                    {"key": "risk", "status": "failed", "error": "Traceback token=SHOULD_DROP"},
                ],
            }
        )

        packet = discipline_service.read_discipline_loop_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_discipline_loop_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["discipline_packet"]["score"], 72)
        self.assertEqual(packet["counts"]["discipline_metric_count"], 1)
        self.assertEqual(packet["counts"]["discipline_rule_count"], 2)
        self.assertEqual(packet["counts"]["decision_loop_item_count"], 1)
        self.assertEqual(packet["counts"]["recovery_queue_count"], 1)
        self.assertEqual(packet["counts"]["refresh_step_count"], 3)
        self.assertEqual(packet["counts"]["refresh_completed_count"], 1)
        self.assertEqual(packet["counts"]["refresh_skipped_count"], 1)
        self.assertEqual(packet["counts"]["refresh_failed_count"], 1)
        self.assertEqual(packet["counts"]["loop_blocked_count"], 1)
        self.assertNotIn("token", packet["discipline_packet"])
        self.assertNotIn("authorization", packet["strategy_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_run_backtest"])
        self.assertTrue(packet["policy"]["does_not_run_full_refresh"])
        self.assertTrue(packet["policy"]["does_not_recompute_action"])
        self.assertTrue(packet["policy"]["discipline_cache_is_not_trade_instruction"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_decision_packet"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_discipline_loop_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_legacy_bridge_cache_reads_migration_checklist_without_running_legacy_tools(self):
        self._with_snapshot_cache(
            {
                "legacy_migration_map": {
                    "summary": "旧功能迁移中",
                    "items": [{"label": "次日图谱迁移", "status": "ready"}],
                    "lanes": [{"label": "已迁移"}],
                    "token": "SHOULD_DROP",
                },
                "legacy_packet_migration_checklist": {
                    "items": [
                        {"label": "market_packet", "status": "done"},
                        {"label": "legacy risk", "status": "pending", "api_key": "SHOULD_DROP"},
                    ]
                },
                "old_workspace_packet_bridge": {"items": [{"label": "旧 packet bridge"}]},
                "old_workspace_capability_overview": {"checklist_done_count": 1, "checklist_pending_count": 1, "items": [{"label": "旧能力"}]},
                "old_workspace_data_absence_ledger": {"items": [{"label": "缺失账本", "authorization": "Bearer SHOULD_DROP"}]},
                "legacy_decision_chain_summary": {"ready_count": 2, "waiting_count": 1, "blocked_count": 1, "items": [{"label": "旧链"}]},
                "legacy_a_share_fact_recovery_actions": [{"label": "强制刷新融资融券", "status": "cached"}],
            }
        )

        packet = legacy_service.read_legacy_bridge_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_legacy_bridge_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["counts"]["checklist_item_count"], 2)
        self.assertEqual(packet["counts"]["checklist_done_count"], 1)
        self.assertEqual(packet["counts"]["checklist_pending_count"], 1)
        self.assertEqual(packet["counts"]["bridge_item_count"], 1)
        self.assertEqual(packet["counts"]["absence_item_count"], 1)
        self.assertEqual(packet["counts"]["fact_recovery_action_count"], 1)
        self.assertEqual(packet["counts"]["decision_blocked_count"], 1)
        self.assertNotIn("token", packet["legacy_migration_map"])
        self.assertNotIn("api_key", packet["checklist_items"][1])
        self.assertNotIn("authorization", packet["absence_items"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertEqual(packet["policy"]["streamlit_role"], "legacy/admin/debug")
        self.assertEqual(packet["policy"]["official_primary_entry"], "React/Vite/Tauri + FastAPI")
        self.assertFalse(packet["policy"]["streamlit_is_official_primary_entry"])
        self.assertTrue(packet["policy"]["react_tauri_is_primary_entry"])
        self.assertFalse(packet["policy"]["legacy_startup_external_calls"])
        self.assertFalse(packet["policy"]["legacy_startup_task_creation"])
        self.assertFalse(packet["policy"]["legacy_can_bypass_guardrails"])
        self.assertTrue(packet["policy"]["does_not_open_streamlit"])
        self.assertTrue(packet["policy"]["does_not_run_legacy_tools"])
        exit_audit = packet["primary_workflow_exit_audit"]
        exit_rows = {row["criterion"]: row for row in packet["primary_workflow_exit_rows"]}
        route_rows = {row["workflow"]: row for row in packet["primary_workflow_route_rows"]}
        self.assertEqual(exit_audit["schema_version"], "streamlit_primary_workflow_exit_audit.v1")
        self.assertEqual(exit_audit["status"], "ordinary_workflow_exit_partial_fallback_required")
        self.assertEqual(exit_audit["scope"], "local_legacy_policy_and_route_inventory_not_streamlit_execution")
        self.assertFalse(exit_audit["ordinary_workflow_exit_complete"])
        self.assertTrue(exit_audit["streamlit_fallback_retained"])
        self.assertFalse(exit_audit["streamlit_fallback_removal_ready"])
        self.assertTrue(exit_audit["react_tauri_primary_entry"])
        self.assertFalse(exit_audit["streamlit_is_official_primary_entry"])
        self.assertGreater(exit_audit["ordinary_workflow_route_count"], 0)
        self.assertGreater(exit_audit["ordinary_workflow_still_needs_fallback_count"], 0)
        self.assertIn("ordinary_workflows_fully_migrated", exit_audit["blockers"])
        self.assertIn("legacy_fallback_removal_ready", exit_audit["blockers"])
        self.assertFalse(exit_audit["external_calls_triggered"])
        self.assertFalse(exit_audit["tushare_called"])
        self.assertFalse(exit_audit["deepseek_called"])
        self.assertFalse(exit_audit["github_called"])
        self.assertTrue(exit_audit["does_not_open_streamlit"])
        self.assertTrue(exit_audit["does_not_run_legacy_tools"])
        self.assertTrue(exit_audit["source_summary"]["legacy_mode_marker_present"])
        self.assertTrue(exit_audit["source_summary"]["legacy_admin_notice_present"])
        self.assertTrue(exit_rows["legacy_cache_get_read_only"]["passed"])
        self.assertTrue(exit_rows["legacy_startup_does_not_create_tasks"]["passed"])
        self.assertTrue(exit_rows["legacy_startup_does_not_call_external_sources"]["passed"])
        self.assertTrue(exit_rows["legacy_cannot_bypass_guardrails"]["passed"])
        self.assertFalse(exit_rows["ordinary_workflows_fully_migrated"]["passed"])
        self.assertFalse(exit_rows["legacy_fallback_removal_ready"]["passed"])
        self.assertEqual(route_rows["candidate_radar_quick_scan"]["coverage_status"], "partial_migrated")
        self.assertTrue(route_rows["candidate_radar_quick_scan"]["still_needs_streamlit_fallback"])
        self.assertEqual(route_rows["legacy_admin_debug_tools"]["coverage_status"], "fallback_retained")
        self.assertEqual(packet["counts"]["primary_workflow_route_count"], exit_audit["ordinary_workflow_route_count"])
        self.assertEqual(packet["counts"]["primary_workflow_fallback_count"], exit_audit["ordinary_workflow_still_needs_fallback_count"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_legacy_bridge_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_storage_factor_values_status_is_cache_only(self):
        self._with_parquet_root()

        status = storage_service.factor_values_status()

        self.assertEqual(status["dataset"], "factor_values")
        self.assertTrue(status["cache_only"])
        self.assertFalse(status["external_calls_triggered"])
        self.assertFalse(status["tushare_called"])
        self.assertFalse(status["deepseek_called"])
        self.assertTrue(status["does_not_execute_trades"])
        self.assertIn(status["metadata"]["status"], {"missing", "ready"})
        self.assertEqual(status["call_ledger"][0]["api"], "local_storage_factor_values_cache")
        self.assertFalse(status["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/factor-values", status["warnings"][0])
        self.assertEqual(status["cache_ttl"]["ttl_state"], "missing")
        self.assertFalse(status["cache_ttl"]["auto_refresh_on_get"])
        self.assertEqual(status["cache_ttl"]["refresh_policy"], "post_task_required")

    def test_storage_overview_covers_daily_moneyflow_and_factor_values(self):
        self._with_parquet_root()
        self._with_meta_store()

        overview = storage_service.storage_overview()

        self.assertEqual(overview["store"], "parquet_duckdb")
        self.assertEqual(set(overview["dataset_status"]), {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertEqual(overview["dataset_count"], 6)
        self.assertEqual({item["dataset"] for item in overview["dataset_catalog"]}, {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        catalog_by_dataset = {item["dataset"]: item for item in overview["dataset_catalog"]}
        self.assertIn("daily-basic", catalog_by_dataset["daily_basic"]["aliases"])
        self.assertIn("trade-cal", catalog_by_dataset["trade_cal"]["aliases"])
        self.assertIn("backtest-results", catalog_by_dataset["backtest_results"]["aliases"])
        self.assertEqual(catalog_by_dataset["factor_values"]["writer"], "POST /api/factor-quant/run-light")
        self.assertEqual(catalog_by_dataset["trade_cal"]["writer"], "POST /api/tasks/refresh-tushare-facts")
        implementation = overview["dataset_implementation_status"]
        self.assertEqual(implementation["status"], "partial_migration")
        self.assertEqual(implementation["dataset_count"], 6)
        self.assertEqual(implementation["local_pipeline_dataset_count"], 1)
        self.assertEqual(implementation["future_button_gated_dataset_count"], 5)
        self.assertEqual(implementation["tushare_capable_dataset_count"], 4)
        self.assertEqual(implementation["local_compute_capable_dataset_count"], 2)
        self.assertEqual(implementation["schema_contract_ready_count"], 6)
        self.assertEqual(implementation["schema_migration_preflight"]["status"], "preflight_ready")
        self.assertEqual(implementation["schema_migration_preflight"]["dataset_count"], 6)
        self.assertEqual(implementation["schema_migration_preflight"]["contract_ready_count"], 6)
        self.assertEqual(implementation["schema_migration_executed_count"], 0)
        self.assertEqual(implementation["physical_schema_validation_done_count"], 0)
        self.assertEqual(implementation["partition_contract_ready_count"], 6)
        self.assertEqual(implementation["state_counts"]["local_pipeline_enabled"], 1)
        self.assertEqual(implementation["state_counts"]["future_button_gated"], 5)
        self.assertEqual(overview["dataset_implementation_state_counts"], implementation["state_counts"])
        self.assertEqual(overview["dataset_parquet_status_counts"], implementation["parquet_status_counts"])
        self.assertIn("schema_migration_preflight", overview)
        self.assertEqual(overview["schema_migration_preflight_status"], "preflight_ready")
        self.assertEqual(overview["schema_migration_preflight"]["schema_version"], "command_center_3_storage_schema_migration_preflight.v1")
        self.assertEqual(overview["schema_migration_preflight"]["scope"], "schema_version_migration_contract")
        self.assertEqual(overview["schema_migration_preflight"]["mode"], "metadata_only_read_only_preflight")
        self.assertEqual(overview["schema_migration_preflight"]["dataset_count"], 6)
        self.assertEqual(overview["schema_migration_preflight"]["contract_ready_count"], 6)
        self.assertEqual(overview["schema_migration_preflight"]["physical_validation_done_count"], 0)
        self.assertEqual(overview["schema_migration_preflight"]["migration_executed_count"], 0)
        self.assertEqual(overview["schema_migration_preflight"]["schema_migration_ready_count"], 0)
        self.assertTrue(overview["schema_migration_preflight"]["manual_migration_task_required"])
        self.assertFalse(overview["schema_migration_preflight"]["schema_migration_task_executed"])
        self.assertFalse(overview["schema_migration_preflight"]["cache_get_writes_files"])
        self.assertFalse(overview["schema_migration_preflight"]["physical_validation_reads_payloads"])
        self.assertFalse(overview["schema_migration_preflight"]["payload_reads_on_get"])
        self.assertFalse(overview["schema_migration_preflight"]["external_calls_triggered"])
        self.assertFalse(overview["schema_migration_preflight"]["tushare_called"])
        self.assertTrue(overview["schema_migration_preflight"]["does_not_execute_trades"])
        self.assertEqual(len(overview["schema_migration_rows"]), 6)
        self.assertEqual(
            overview["schema_migration_status_counts"]["contract_ready_physical_validation_pending"],
            6,
        )
        self.assertIn("production_readiness", overview)
        self.assertIn(overview["production_readiness"]["status"], {"foundation_ready", "partial_dependency_missing"})
        self.assertEqual(overview["production_readiness"]["scope"], "storage_productionization_preflight")
        self.assertIn("storage_production_blocker_audit", overview)
        storage_blocker = overview["storage_production_blocker_audit"]
        self.assertEqual(storage_blocker["schema_version"], "command_center_3_storage_production_blocker_audit.v1")
        self.assertEqual(storage_blocker["status"], "storage_production_blocked")
        self.assertEqual(storage_blocker["scope"], "ltg_05_storage_duckdb_parquet_productionization")
        self.assertFalse(storage_blocker["production_storage_complete"])
        self.assertTrue(storage_blocker["dry_runs_are_not_production_completion"])
        self.assertTrue(storage_blocker["preflight_is_not_physical_migration"])
        self.assertTrue(storage_blocker["dataset_version_policy_is_not_manifest_validation"])
        self.assertTrue(storage_blocker["dataset_version_manifest_evidence_is_read_only"])
        self.assertEqual(storage_blocker["dataset_version_manifest_evidence_status"], "manifest_missing_validation_pending")
        self.assertFalse(storage_blocker["dataset_version_manifest_evidence_validated"])
        self.assertEqual(storage_blocker["dataset_version_manifest_evidence_validated_count"], 0)
        self.assertGreaterEqual(storage_blocker["blocking_criterion_count"], 6)
        self.assertEqual(len(overview["storage_production_blocker_rows"]), 10)
        self.assertEqual(overview["storage_production_blocker_count"], storage_blocker["blocking_criterion_count"])
        blocker_criteria = {row["criterion"] for row in overview["storage_production_blocker_rows"]}
        self.assertIn("schema_physical_validation_complete", blocker_criteria)
        self.assertIn("schema_migration_executed", blocker_criteria)
        self.assertIn("dataset_version_manifest_validated", blocker_criteria)
        self.assertIn("partition_migration_executed", blocker_criteria)
        self.assertIn("physical_compaction_executed", blocker_criteria)
        self.assertIn("cache_ttl_refresh_pipeline_executed", blocker_criteria)
        self.assertIn("artifact_cleanup_manual_review_visible", blocker_criteria)
        self.assertIn("cache_get_remains_read_only", blocker_criteria)
        readiness_by_component = {row["component"]: row for row in overview["production_readiness"]["rows"]}
        self.assertIn("sqlite_meta", readiness_by_component)
        self.assertIn("schema_migration_preflight", readiness_by_component)
        self.assertIn("dataset_version_policy", readiness_by_component)
        self.assertIn("parquet_store", readiness_by_component)
        self.assertIn("duckdb_query", readiness_by_component)
        self.assertIn("local_data_git_guard", readiness_by_component)
        self.assertIn("artifact_hygiene", readiness_by_component)
        self.assertIn("artifact_cleanup_review", readiness_by_component)
        self.assertEqual(readiness_by_component["schema_migration_preflight"]["status"], "preflight_ready")
        self.assertEqual(readiness_by_component["dataset_version_policy"]["status"], "policy_ready")
        self.assertIn(readiness_by_component["duckdb_query"]["status"], {"service_ready", "dependency_missing"})
        self.assertEqual(readiness_by_component["duckdb_query"]["query_wrapper"], "duckdb_filtered_parquet.v1")
        self.assertEqual(readiness_by_component["duckdb_query"]["max_limit"], 10000)
        self.assertTrue(readiness_by_component["duckdb_query"]["safe_parameter_binding"])
        self.assertTrue(readiness_by_component["duckdb_query"]["typed_projection_enabled"])
        self.assertTrue(readiness_by_component["duckdb_query"]["query_result_contract_enabled"])
        self.assertTrue(readiness_by_component["duckdb_query"]["cursor_pagination_enabled"])
        self.assertFalse(readiness_by_component["duckdb_query"]["frontend_executes_query"])
        self.assertFalse(readiness_by_component["duckdb_query"]["cache_get_writes_files"])
        controls_by_key = {row["control"]: row for row in overview["production_readiness"]["production_control_rows"]}
        self.assertIn("schema_version", controls_by_key)
        self.assertIn("dataset_version_policy", controls_by_key)
        self.assertIn("schema_migration_preflight", controls_by_key)
        self.assertIn("dataset_version_manifest_evidence", controls_by_key)
        self.assertIn("schema_validation_dry_run", controls_by_key)
        self.assertIn("partition_migration_dry_run", controls_by_key)
        self.assertIn("parquet_partitioning", controls_by_key)
        self.assertIn("duckdb_query_wrappers", controls_by_key)
        self.assertIn("cache_ttl", controls_by_key)
        self.assertIn("parquet_compaction", controls_by_key)
        self.assertIn("local_artifact_hygiene", controls_by_key)
        self.assertIn("artifact_cleanup_manual_review", controls_by_key)
        self.assertEqual(controls_by_key["schema_version"]["status"], "local_ready")
        self.assertEqual(controls_by_key["dataset_version_policy"]["status"], "policy_ready")
        self.assertEqual(controls_by_key["dataset_version_manifest_evidence"]["status"], "read_only_evidence_ready")
        self.assertEqual(controls_by_key["schema_migration_preflight"]["status"], "preflight_ready")
        self.assertEqual(controls_by_key["schema_validation_dry_run"]["status"], "button_gated_ready")
        self.assertEqual(controls_by_key["partition_migration_dry_run"]["status"], "button_gated_ready")
        self.assertEqual(controls_by_key["parquet_partitioning"]["status"], "contract_ready")
        self.assertEqual(controls_by_key["cache_ttl"]["status"], "button_gated_ready")
        self.assertEqual(controls_by_key["parquet_compaction"]["status"], "button_gated_ready")
        self.assertEqual(controls_by_key["local_artifact_hygiene"]["status"], "audit_ready")
        self.assertEqual(controls_by_key["artifact_cleanup_manual_review"]["status"], "manual_review_contract_ready")
        self.assertEqual(overview["production_readiness"]["schema_contract_policy"], "canonical datasets expose local schema contracts; physical validation remains explicit and non-refreshing.")
        self.assertEqual(overview["production_readiness"]["dataset_version_policy"], "contract_only_manifest_write_requires_explicit_task")
        self.assertEqual(overview["production_readiness"]["dataset_version_policy_status"], "policy_ready")
        self.assertEqual(overview["production_readiness"]["dataset_version_policy_dataset_count"], 6)
        self.assertEqual(overview["production_readiness"]["dataset_version_declared_count"], 6)
        self.assertEqual(overview["production_readiness"]["physical_dataset_version_validated_count"], 0)
        self.assertEqual(overview["production_readiness"]["dataset_version_migration_executed_count"], 0)
        self.assertFalse(overview["production_readiness"]["dataset_version_manifest_written_on_get"])
        self.assertEqual(overview["production_readiness"]["dataset_version_manifest_evidence_status"], "manifest_missing_validation_pending")
        self.assertEqual(overview["production_readiness"]["dataset_version_manifest_evidence_validated_count"], 0)
        self.assertEqual(overview["production_readiness"]["dataset_version_manifest_evidence_missing_count"], 0)
        self.assertEqual(overview["production_readiness"]["dataset_version_manifest_evidence_mismatch_count"], 0)
        self.assertFalse(overview["production_readiness"]["dataset_version_manifest_evidence_exists"])
        self.assertFalse(overview["production_readiness"]["dataset_version_manifest_evidence_validated"])
        self.assertFalse(overview["production_readiness"]["dataset_version_manifest_evidence_written_on_get"])
        self.assertFalse(overview["production_readiness"]["dataset_version_manifest_evidence_reads_parquet_payloads"])
        self.assertEqual(overview["production_readiness"]["schema_migration_policy"], "preflight_only_no_physical_migration_on_get")
        self.assertEqual(overview["production_readiness"]["schema_migration_preflight_status"], "preflight_ready")
        self.assertEqual(overview["production_readiness"]["schema_migration_dataset_count"], 6)
        self.assertEqual(overview["production_readiness"]["schema_migration_executed_count"], 0)
        self.assertEqual(overview["production_readiness"]["physical_schema_validation_done_count"], 0)
        self.assertEqual(overview["production_readiness"]["schema_validation_dry_run_route"], "POST /api/storage/schema-validation/dry-run")
        self.assertTrue(overview["production_readiness"]["schema_validation_dry_run_button_gated"])
        self.assertFalse(overview["production_readiness"]["schema_validation_dry_run_writes_parquet"])
        self.assertFalse(overview["production_readiness"]["schema_validation_dry_run_reads_row_payloads"])
        self.assertEqual(overview["production_readiness"]["duckdb_query_service_policy"], "read_only_service_wrappers_local_parquet_only")
        self.assertIn(overview["production_readiness"]["duckdb_query_service_status"], {"service_ready", "dependency_missing"})
        self.assertEqual(overview["production_readiness"]["duckdb_query_service_dataset_count"], 6)
        self.assertEqual(overview["production_readiness"]["duckdb_query_wrapper"], "duckdb_filtered_parquet.v1")
        self.assertEqual(overview["production_readiness"]["duckdb_query_max_limit"], 10000)
        self.assertTrue(overview["production_readiness"]["duckdb_query_safe_parameter_binding"])
        self.assertTrue(overview["production_readiness"]["duckdb_query_typed_projection_enabled"])
        self.assertTrue(overview["production_readiness"]["duckdb_query_result_contract_enabled"])
        self.assertEqual(
            overview["production_readiness"]["duckdb_query_result_contract_schema_version"],
            "duckdb_query_result_contract.v1",
        )
        self.assertTrue(overview["production_readiness"]["duckdb_query_cursor_pagination_enabled"])
        self.assertFalse(overview["production_readiness"]["duckdb_query_frontend_executes_queries"])
        self.assertFalse(overview["production_readiness"]["duckdb_query_cache_get_external_calls"])
        self.assertFalse(overview["production_readiness"]["duckdb_query_cache_get_writes_files"])
        self.assertFalse(overview["production_readiness"]["duckdb_query_writes_parquet_on_get"])
        self.assertEqual(overview["production_readiness"]["partition_migration_dry_run_route"], "POST /api/storage/partition-migration/dry-run")
        self.assertTrue(overview["production_readiness"]["partition_migration_dry_run_button_gated"])
        self.assertFalse(overview["production_readiness"]["partition_migration_dry_run_writes_parquet"])
        self.assertFalse(overview["production_readiness"]["partition_migration_dry_run_reads_row_payloads"])
        self.assertEqual(overview["production_readiness"]["cache_ttl_policy"], "dry_run_button_gated_no_auto_refresh")
        self.assertEqual(overview["production_readiness"]["cache_ttl_dry_run_route"], "POST /api/storage/cache-ttl/dry-run")
        self.assertTrue(overview["production_readiness"]["cache_ttl_dry_run_button_gated"])
        self.assertFalse(overview["production_readiness"]["cache_ttl_dry_run_writes_parquet"])
        self.assertFalse(overview["production_readiness"]["cache_ttl_dry_run_reads_row_payloads"])
        self.assertEqual(overview["production_readiness"]["cache_ttl_refresh_executed_count"], 0)
        self.assertEqual(overview["production_readiness"]["compaction_policy"], "dry_run_button_gated_no_parquet_rewrite")
        self.assertEqual(overview["production_readiness"]["compaction_dry_run_route"], "POST /api/storage/compaction/dry-run")
        self.assertTrue(overview["production_readiness"]["compaction_dry_run_button_gated"])
        self.assertFalse(overview["production_readiness"]["compaction_dry_run_writes_parquet"])
        self.assertFalse(overview["production_readiness"]["compaction_dry_run_reads_row_payloads"])
        self.assertEqual(overview["production_readiness"]["compaction_executed_count"], 0)
        self.assertEqual(overview["production_readiness"]["artifact_hygiene_policy"], "path_only_manual_cleanup_no_delete_on_get")
        self.assertEqual(overview["production_readiness"]["artifact_cleanup_dry_run_route"], "POST /api/storage/artifact-hygiene/dry-run")
        self.assertTrue(overview["production_readiness"]["artifact_cleanup_dry_run_button_gated"])
        self.assertFalse(overview["production_readiness"]["artifact_cleanup_dry_run_deletes_files"])
        self.assertIn("manual_review_ready", overview["production_readiness"]["artifact_cleanup_review_status"])
        self.assertTrue(overview["production_readiness"]["artifact_cleanup_manual_review_required"])
        self.assertEqual(overview["production_readiness"]["artifact_cleanup_delete_executed_count"], 0)
        self.assertFalse(overview["production_readiness"]["artifact_cleanup_delete_command_generated"])
        self.assertTrue(overview["production_readiness"]["artifact_cleanup_review_is_not_delete_execution"])
        self.assertFalse(overview["production_readiness"]["artifact_cleanup_production_complete"])
        self.assertIn("artifact_hygiene", overview)
        self.assertIn("artifact_cleanup_review_contract", overview)
        self.assertIn("artifact_cleanup_review_rows", overview)
        self.assertEqual(overview["artifact_hygiene"]["status"], overview["artifact_hygiene_status"])
        self.assertEqual(overview["artifact_hygiene"]["cleanup_policy"], "manual_only_no_delete_on_get")
        self.assertEqual(overview["artifact_hygiene"]["cleanup_task_status"], "dry_run_button_gated")
        self.assertEqual(overview["artifact_hygiene"]["cleanup_dry_run_route"], "POST /api/storage/artifact-hygiene/dry-run")
        self.assertEqual(
            overview["artifact_cleanup_review_contract"]["schema_version"],
            "command_center_3_storage_artifact_cleanup_review_contract.v1",
        )
        self.assertEqual(
            overview["artifact_hygiene"]["artifact_cleanup_review_contract"]["schema_version"],
            "command_center_3_storage_artifact_cleanup_review_contract.v1",
        )
        self.assertTrue(overview["artifact_cleanup_review_contract"]["manual_approval_required"])
        self.assertFalse(overview["artifact_cleanup_review_contract"]["delete_executed"])
        self.assertFalse(overview["artifact_cleanup_review_contract"]["safe_delete_command_generated"])
        self.assertTrue(overview["artifact_cleanup_review_contract"]["cleanup_review_is_not_delete_execution"])
        self.assertFalse(overview["artifact_cleanup_review_contract"]["production_cleanup_complete"])
        self.assertFalse(overview["artifact_cleanup_review_contract"]["post_dry_run_external_calls"])
        self.assertFalse(overview["artifact_cleanup_review_contract"]["reads_payloads"])
        self.assertEqual(
            {row["review_step"] for row in overview["artifact_cleanup_review_rows"]},
            {row["review_step"] for row in overview["artifact_cleanup_review_contract"]["rows"]},
        )
        self.assertTrue(overview["artifact_hygiene"]["dry_run_required_before_delete"])
        self.assertFalse(overview["artifact_hygiene"]["delete_files_on_get"])
        self.assertFalse(overview["artifact_hygiene"]["auto_cleanup_on_get"])
        self.assertTrue(overview["artifact_hygiene"]["does_not_read_file_payloads"])
        self.assertTrue(overview["artifact_hygiene"]["does_not_scan_secret_values"])
        self.assertFalse(overview["artifact_hygiene"]["external_calls_triggered"])
        self.assertFalse(overview["artifact_hygiene"]["tushare_called"])
        self.assertTrue(overview["artifact_hygiene"]["does_not_execute_trades"])
        self.assertFalse(overview["artifact_hygiene"]["data_files_allowed_in_git"])
        self.assertIn("*.parquet", overview["artifact_hygiene"]["git_excluded_patterns"])
        self.assertIn("desktop/node_modules", overview["artifact_hygiene"]["git_excluded_patterns"])
        self.assertIn("duckdb_query_service", overview)
        self.assertEqual(overview["duckdb_query_service"]["schema_version"], "command_center_3_storage_duckdb_query_service.v1")
        self.assertEqual(overview["duckdb_query_service"]["query_wrapper"], "duckdb_filtered_parquet.v1")
        self.assertEqual(overview["duckdb_query_service"]["dataset_count"], 6)
        self.assertEqual(len(overview["duckdb_query_service_rows"]), 6)
        self.assertEqual(overview["duckdb_query_service"]["max_limit"], 10000)
        self.assertTrue(overview["duckdb_query_service"]["safe_limit_enforced"])
        self.assertTrue(overview["duckdb_query_service"]["safe_parameter_binding"])
        self.assertTrue(overview["duckdb_query_service"]["typed_projection_enabled"])
        self.assertTrue(overview["duckdb_query_service"]["query_result_contract_enabled"])
        self.assertTrue(overview["duckdb_query_service"]["cursor_pagination_enabled"])
        self.assertEqual(overview["duckdb_query_service"]["cursor_policy"], "offset_cursor")
        self.assertIn("cursor", overview["duckdb_query_service"]["supported_filter_params"])
        self.assertFalse(overview["duckdb_query_service"]["frontend_executes_query"])
        self.assertFalse(overview["duckdb_query_service"]["ui_direct_dataframe_read"])
        self.assertFalse(overview["duckdb_query_service"]["cache_get_external_calls"])
        self.assertFalse(overview["duckdb_query_service"]["cache_get_writes_files"])
        self.assertFalse(overview["duckdb_query_service"]["writes_parquet_on_get"])
        self.assertEqual(overview["duckdb_query_service"]["call_ledger"][0]["api"], "local_storage_duckdb_query_service_policy")
        query_rows_by_dataset = {row["dataset"]: row for row in overview["duckdb_query_service_rows"]}
        self.assertEqual(query_rows_by_dataset["daily"]["date_column"], "trade_date")
        self.assertIn("close", query_rows_by_dataset["daily"]["projection_columns"])
        self.assertEqual(query_rows_by_dataset["daily"]["query_result_contract_schema_version"], "duckdb_query_result_contract.v1")
        self.assertTrue(query_rows_by_dataset["daily"]["cursor_pagination_enabled"])
        self.assertIn("ts_code", query_rows_by_dataset["daily"]["supported_filter_params"])
        self.assertIn("start_date", query_rows_by_dataset["daily"]["supported_filter_params"])
        self.assertFalse(query_rows_by_dataset["daily"]["frontend_executes_query"])
        self.assertEqual(query_rows_by_dataset["trade_cal"]["date_column"], "cal_date")
        self.assertEqual(set(overview["dataset_ttl_status"]), {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertIn("missing", overview["dataset_ttl_state_counts"])
        self.assertEqual(set(overview["dataset_schema_contract_status"]), {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertIn("dataset_version_policy", overview)
        self.assertEqual(overview["dataset_version_policy"]["schema_version"], "command_center_3_storage_dataset_version_policy.v1")
        self.assertEqual(overview["dataset_version_policy"]["status"], "policy_ready")
        self.assertEqual(overview["dataset_version_policy"]["target_version_declared_count"], 6)
        self.assertEqual(overview["dataset_version_policy"]["physical_dataset_version_validated_count"], 0)
        self.assertEqual(overview["dataset_version_policy"]["dataset_version_migration_executed_count"], 0)
        self.assertFalse(overview["dataset_version_policy"]["manifest_written_on_get"])
        self.assertFalse(overview["dataset_version_policy"]["cache_get_writes_files"])
        self.assertEqual(len(overview["dataset_version_rows"]), 6)
        self.assertEqual(set(overview["dataset_version_status"]), {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertIn("contract_declared_dataset_missing", overview["dataset_version_status_counts"])
        self.assertIn("dataset_version_manifest_evidence_audit", overview)
        manifest_evidence = overview["dataset_version_manifest_evidence_audit"]
        self.assertEqual(manifest_evidence["schema_version"], "command_center_3_storage_dataset_version_manifest_evidence.v1")
        self.assertEqual(manifest_evidence["status"], "manifest_missing_validation_pending")
        self.assertEqual(manifest_evidence["scope"], "read_only_local_manifest_evidence_not_manifest_writer")
        self.assertEqual(manifest_evidence["mode"], "cache_only_read_only_manifest_evidence")
        self.assertFalse(manifest_evidence["manifest_exists"])
        self.assertEqual(manifest_evidence["validated_dataset_count"], 0)
        self.assertFalse(manifest_evidence["dataset_version_manifest_validated"])
        self.assertFalse(manifest_evidence["dataset_version_manifest_written"])
        self.assertFalse(manifest_evidence["manifest_writer_task_executed"])
        self.assertEqual(manifest_evidence["dataset_version_migration_executed_count"], 0)
        self.assertFalse(manifest_evidence["manifest_written_on_get"])
        self.assertFalse(manifest_evidence["cache_get_writes_files"])
        self.assertFalse(manifest_evidence["cache_get_reads_parquet_payloads"])
        self.assertFalse(manifest_evidence["external_calls_triggered"])
        self.assertFalse(manifest_evidence["tushare_called"])
        self.assertFalse(manifest_evidence["deepseek_called"])
        self.assertFalse(manifest_evidence["github_called"])
        self.assertTrue(manifest_evidence["does_not_execute_trades"])
        self.assertEqual(len(overview["dataset_version_manifest_evidence_rows"]), 6)
        self.assertIn("manifest_missing_validation_pending", overview["dataset_version_manifest_evidence_status_counts"])
        self.assertEqual(overview["dataset_version_manifest_evidence_status"], "manifest_missing_validation_pending")
        self.assertEqual(overview["dataset_version_manifest_evidence_validated_count"], 0)
        self.assertFalse(overview["dataset_version_manifest_evidence_validated"])
        self.assertEqual(set(overview["dataset_partition_plan_status"]), {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertEqual(set(overview["dataset_compaction_status"]), {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertTrue(all(status == "contract_ready" for status in overview["dataset_schema_contract_status"].values()))
        self.assertTrue(all(status == "contract_ready" for status in overview["dataset_partition_plan_status"].values()))
        self.assertEqual(overview["manual_compaction_recommended_count"], 0)
        self.assertTrue(all(row["external_calls_triggered"] is False for row in controls_by_key.values()))
        self.assertFalse(overview["production_readiness"]["external_calls_triggered"])
        self.assertFalse(overview["production_readiness"]["tushare_called"])
        self.assertTrue(overview["production_readiness"]["does_not_modify_strategy_action"])
        rows_by_dataset = {row["dataset"]: row for row in implementation["dataset_rows"]}
        self.assertEqual(rows_by_dataset["factor_values"]["implementation_state"], "local_pipeline_enabled")
        self.assertEqual(rows_by_dataset["daily"]["implementation_state"], "future_button_gated")
        self.assertEqual(rows_by_dataset["trade_cal"]["implementation_state"], "future_button_gated")
        self.assertTrue(rows_by_dataset["daily"]["tushare_capable"])
        self.assertTrue(rows_by_dataset["trade_cal"]["tushare_capable"])
        self.assertFalse(rows_by_dataset["factor_values"]["tushare_capable"])
        self.assertEqual(rows_by_dataset["daily"]["schema_version"], "storage.daily.v1")
        self.assertEqual(rows_by_dataset["daily"]["declared_dataset_version"], "storage.daily.v1")
        self.assertEqual(rows_by_dataset["daily"]["dataset_version_status"], "contract_declared_dataset_missing")
        self.assertEqual(rows_by_dataset["daily"]["version_claim_level"], "contract_only_not_physical_proof")
        self.assertFalse(rows_by_dataset["daily"]["physical_dataset_version_validated"])
        self.assertFalse(rows_by_dataset["daily"]["dataset_version_migration_executed"])
        self.assertEqual(rows_by_dataset["daily"]["schema_migration_status"], "contract_ready_physical_validation_pending")
        self.assertEqual(rows_by_dataset["daily"]["physical_schema_validation_status"], "not_run_metadata_only")
        self.assertFalse(rows_by_dataset["daily"]["schema_migration_executed"])
        self.assertTrue(rows_by_dataset["daily"]["manual_migration_task_required"])
        self.assertEqual(rows_by_dataset["trade_cal"]["recommended_partition_columns"], ["exchange"])
        self.assertFalse(rows_by_dataset["daily"]["manual_compaction_recommended"])
        migration_rows_by_dataset = {row["dataset"]: row for row in overview["schema_migration_rows"]}
        self.assertEqual(migration_rows_by_dataset["daily"]["target_schema_version"], "storage.daily.v1")
        self.assertEqual(migration_rows_by_dataset["trade_cal"]["expected_partition_columns"], ["exchange"])
        self.assertEqual(migration_rows_by_dataset["daily"]["physical_column_validation_status"], "not_run_metadata_only")
        self.assertEqual(migration_rows_by_dataset["daily"]["missing_required_columns_status"], "not_evaluated_metadata_only")
        self.assertFalse(migration_rows_by_dataset["daily"]["cache_get_writes_files"])
        self.assertFalse(migration_rows_by_dataset["daily"]["cache_get_reads_payloads"])
        self.assertFalse(migration_rows_by_dataset["daily"]["schema_migration_ready_for_execution"])
        self.assertTrue(migration_rows_by_dataset["daily"]["physical_validation_required_before_migration"])
        self.assertFalse(migration_rows_by_dataset["daily"]["external_calls_triggered"])
        self.assertTrue(migration_rows_by_dataset["daily"]["does_not_modify_strategy_action"])
        self.assertTrue(implementation["all_external_refreshes_button_gated"])
        self.assertTrue(implementation["all_datasets_do_not_modify_strategy_action"])
        self.assertTrue(implementation["all_datasets_do_not_execute_trades"])
        self.assertTrue(all(item["does_not_execute_trades"] for item in overview["dataset_catalog"]))
        self.assertTrue(all(item["does_not_modify_strategy_action"] for item in overview["dataset_catalog"]))
        self.assertTrue(overview["cache_only"])
        self.assertFalse(overview["external_calls_triggered"])
        self.assertFalse(overview["tushare_called"])
        self.assertTrue(overview["does_not_execute_trades"])
        self.assertIn("sqlite_meta", overview)
        self.assertEqual(overview["metadata_store"], "sqlite_meta")
        self.assertEqual(overview["metadata_status"], "missing")
        self.assertEqual(overview["call_ledger"][0]["api"], "local_storage_overview_cache")
        self.assertFalse(overview["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage", overview["warnings"][0])

    def test_storage_cache_ttl_marks_stale_without_auto_refreshing(self):
        if importlib.util.find_spec("pyarrow") is None or importlib.util.find_spec("pandas") is None:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        import pandas as pd

        root = self._with_parquet_root()
        out = storage_service.parquet_store.write_dataset(
            pd.DataFrame({"ts_code": ["002008.SZ"], "trade_date": ["20260611"], "close": [10.8]}),
            root=root,
            name="daily",
        )
        old_timestamp = 1_700_000_000
        os.utime(out["path"], (old_timestamp, old_timestamp))

        status = storage_service.parquet_dataset_status("daily")

        self.assertEqual(status["cache_ttl"]["ttl_state"], "stale")
        self.assertEqual(status["cache_ttl"]["stale_reason"], "age_exceeds_ttl")
        self.assertFalse(status["cache_ttl"]["auto_refresh_on_get"])
        self.assertFalse(status["cache_ttl"]["external_calls_triggered"])
        self.assertFalse(status["cache_ttl"]["tushare_called"])
        self.assertTrue(status["cache_ttl"]["does_not_modify_strategy_action"])
        self.assertTrue(status["cache_ttl"]["does_not_execute_trades"])

    def test_storage_cache_ttl_dry_run_recommends_without_refreshing(self):
        if importlib.util.find_spec("pyarrow") is None or importlib.util.find_spec("pandas") is None:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        import pandas as pd

        db_path = self._with_meta_store()
        root = self._with_parquet_root()
        out = storage_service.parquet_store.write_dataset(
            pd.DataFrame({"ts_code": ["002008.SZ"], "trade_date": ["20260611"], "close": [10.8]}),
            root=root,
            name="daily",
        )
        old_timestamp = 1_700_000_000
        os.utime(out["path"], (old_timestamp, old_timestamp))
        parquet_path = Path(out["path"])
        before_mtime = parquet_path.stat().st_mtime
        clear_task_statuses_for_tests(clear_persisted=True)

        task = storage_service.run_storage_cache_ttl_dry_run_task(
            {"source": "unit_test", "token": "SHOULD_DROP", "refresh_allowed": True, "write_parquet_allowed": True}
        )

        self.assertEqual(task["task_type"], "run_storage_cache_ttl_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_cache_ttl_dry_run_completed")
        self.assertEqual(task["output_packet_key"], "command_center_3_storage_cache_ttl_dry_run_packet")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("token", task["payload_safe"])
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_cache_ttl_dry_run")
        self.assertEqual(task["call_ledger"][0]["endpoint"], "POST /api/storage/cache-ttl/dry-run")
        self.assertEqual(task["call_ledger"][0]["call_status"], "dry_run_completed")
        self.assertFalse(task["call_ledger"][0]["external"])
        self.assertEqual(parquet_path.stat().st_mtime, before_mtime)

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_3_storage_cache_ttl_dry_run_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["schema_version"], "command_center_3_storage_cache_ttl_dry_run.v1")
        self.assertEqual(persisted["mode"], "dry_run")
        self.assertEqual(persisted["dataset_count"], 6)
        self.assertEqual(persisted["refresh_recommended_count"], 1)
        self.assertEqual(persisted["refresh_executed_count"], 0)
        self.assertFalse(persisted["post_dry_run_writes_parquet"])
        self.assertFalse(persisted["post_dry_run_reads_row_payloads"])
        self.assertFalse(persisted["post_dry_run_reads_env_files"])
        self.assertFalse(persisted["auto_refresh_on_get"])
        self.assertFalse(persisted["refresh_executed"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertTrue(persisted["does_not_execute_trades"])
        rows_by_dataset = {row["dataset"]: row for row in persisted["rows"]}
        self.assertEqual(rows_by_dataset["daily"]["cache_ttl_dry_run_status"], "refresh_recommended")
        self.assertEqual(rows_by_dataset["daily"]["ttl_state"], "stale")
        self.assertEqual(rows_by_dataset["daily"]["stale_reason"], "age_exceeds_ttl")
        self.assertTrue(rows_by_dataset["daily"]["refresh_recommended"])
        self.assertTrue(rows_by_dataset["daily"]["refresh_task_required"])
        self.assertFalse(rows_by_dataset["daily"]["auto_refresh_on_post"])
        self.assertFalse(rows_by_dataset["daily"]["would_call_external_source"])
        self.assertFalse(rows_by_dataset["daily"]["would_write_parquet"])
        self.assertEqual(rows_by_dataset["moneyflow"]["cache_ttl_dry_run_status"], "missing_dataset")
        dumped = json.dumps({"task": task, "packet": persisted}, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn('"refresh_allowed": true', dumped)
        self.assertNotIn('"write_parquet_allowed": true', dumped)

    def test_storage_cache_ttl_dry_run_endpoint_is_button_gated_local_task(self):
        self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)
        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).post(
            "/api/storage/cache-ttl/dry-run",
            json={"source": "api_test", "api_key": "SHOULD_DROP", "refresh_allowed": True},
        ).json()

        self.assertTrue(response["ok"])
        self.assertIn("task_id", response["data"])
        task = response["data"]["task"]
        self.assertEqual(task["task_type"], "run_storage_cache_ttl_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_cache_ttl_dry_run_completed")
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_cache_ttl_dry_run")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

    def test_storage_dataset_exposes_schema_contract_and_partition_plan(self):
        self._with_parquet_root()

        status = storage_service.parquet_dataset_status("daily")

        self.assertEqual(status["schema_contract"]["status"], "contract_ready")
        self.assertEqual(status["schema_contract"]["schema_version"], "storage.daily.v1")
        self.assertEqual(status["schema_contract"]["date_column"], "trade_date")
        self.assertEqual(status["schema_contract"]["primary_key"], ["ts_code", "trade_date"])
        self.assertIn("close", status["schema_contract"]["required_columns"])
        self.assertFalse(status["schema_contract"]["physical_migration_done"])
        self.assertFalse(status["schema_contract"]["external_calls_triggered"])
        self.assertEqual(status["dataset_version_policy"]["version_status"], "contract_declared_dataset_missing")
        self.assertEqual(status["dataset_version_policy"]["declared_dataset_version"], "storage.daily.v1")
        self.assertEqual(status["dataset_version_policy"]["version_source"], "local_schema_contract")
        self.assertEqual(status["dataset_version_policy"]["version_claim_level"], "contract_only_not_physical_proof")
        self.assertFalse(status["dataset_version_policy"]["physical_version_validated"])
        self.assertFalse(status["dataset_version_policy"]["dataset_version_migration_executed"])
        self.assertFalse(status["dataset_version_policy"]["manifest_written_on_get"])
        self.assertFalse(status["dataset_version_policy"]["cache_get_writes_files"])
        self.assertFalse(status["dataset_version_policy"]["external_calls_triggered"])
        self.assertEqual(status["schema_migration"]["migration_status"], "contract_ready_physical_validation_pending")
        self.assertEqual(status["schema_migration"]["target_schema_version"], "storage.daily.v1")
        self.assertEqual(status["schema_migration"]["required_column_count"], 8)
        self.assertEqual(status["schema_migration"]["physical_column_validation_status"], "not_run_metadata_only")
        self.assertEqual(status["schema_migration"]["missing_required_columns_status"], "not_evaluated_metadata_only")
        self.assertFalse(status["schema_migration"]["physical_validation_done"])
        self.assertFalse(status["schema_migration"]["schema_migration_executed"])
        self.assertFalse(status["schema_migration"]["cache_get_writes_files"])
        self.assertFalse(status["schema_migration"]["physical_validation_reads_payloads"])
        self.assertFalse(status["schema_migration"]["external_calls_triggered"])
        self.assertTrue(status["schema_migration"]["requires_manual_migration_task"])
        self.assertTrue(status["schema_migration"]["does_not_execute_trades"])
        self.assertEqual(status["partition_plan"]["status"], "contract_ready")
        self.assertEqual(status["partition_plan"]["recommended_partition_columns"], ["trade_date"])
        self.assertTrue(status["partition_plan"]["physical_partitioning_supported"])
        self.assertFalse(status["partition_plan"]["physical_partitioning_enabled"])
        self.assertEqual(status["partition_plan"]["partition_writer"], "storage.parquet_store.write_partitioned_dataset")
        self.assertFalse(status["partition_plan"]["auto_partition_on_get"])
        self.assertTrue(status["partition_plan"]["manual_compaction_required"])
        self.assertTrue(status["partition_plan"]["does_not_modify_strategy_action"])
        self.assertTrue(status["partition_plan"]["does_not_execute_trades"])
        self.assertEqual(status["compaction_plan"]["status"], "not_applicable_missing")
        self.assertFalse(status["compaction_plan"]["auto_compact_on_get"])
        self.assertFalse(status["compaction_plan"]["physical_compaction_executed"])
        self.assertTrue(status["compaction_plan"]["manual_compaction_task_required"])
        self.assertTrue(status["compaction_plan"]["does_not_modify_strategy_action"])

    def test_storage_dataset_version_policy_is_contract_only_cache_read(self):
        self._with_parquet_root()

        policy = storage_service.storage_dataset_version_policy()

        self.assertEqual(policy["schema_version"], "command_center_3_storage_dataset_version_policy.v1")
        self.assertEqual(policy["status"], "policy_ready")
        self.assertEqual(policy["mode"], "cache_only_read_only_policy")
        self.assertEqual(policy["scope"], "dataset_versioning_contract_before_manifest_write")
        self.assertEqual(policy["dataset_count"], 6)
        self.assertEqual(policy["target_version_declared_count"], 6)
        self.assertEqual(policy["version_manifest_present_count"], 0)
        self.assertEqual(policy["physical_dataset_version_validated_count"], 0)
        self.assertEqual(policy["dataset_version_migration_executed_count"], 0)
        self.assertEqual(policy["manifest_written_on_get_count"], 0)
        self.assertEqual(policy["version_policy"], "contract_only_manifest_write_requires_explicit_task")
        self.assertTrue(policy["manifest_write_task_required"])
        self.assertTrue(policy["physical_validation_required_before_version_claim"])
        self.assertFalse(policy["cache_get_writes_files"])
        self.assertFalse(policy["cache_get_reads_payloads"])
        self.assertFalse(policy["manifest_written_on_get"])
        self.assertFalse(policy["external_calls_triggered"])
        self.assertFalse(policy["tushare_called"])
        self.assertFalse(policy["deepseek_called"])
        self.assertFalse(policy["github_called"])
        self.assertTrue(policy["does_not_execute_trades"])
        self.assertTrue(policy["does_not_modify_strategy_action"])
        rows_by_dataset = {row["dataset"]: row for row in policy["rows"]}
        self.assertEqual(rows_by_dataset["daily"]["declared_dataset_version"], "storage.daily.v1")
        self.assertEqual(rows_by_dataset["daily"]["version_status"], "contract_declared_dataset_missing")
        self.assertEqual(rows_by_dataset["daily"]["version_claim_level"], "contract_only_not_physical_proof")
        self.assertFalse(rows_by_dataset["daily"]["version_manifest_present"])
        self.assertFalse(rows_by_dataset["daily"]["physical_version_validated"])
        self.assertFalse(rows_by_dataset["daily"]["dataset_version_migration_executed"])
        self.assertFalse(rows_by_dataset["daily"]["manifest_written_on_get"])
        self.assertFalse(rows_by_dataset["daily"]["cache_get_reads_payloads"])
        self.assertIn("_dataset_versions.json", policy["version_manifest_path"])

    def test_storage_dataset_version_manifest_evidence_is_read_only_local_audit(self):
        root = self._with_parquet_root()

        missing = storage_service.storage_dataset_version_manifest_evidence_audit()

        self.assertEqual(missing["schema_version"], "command_center_3_storage_dataset_version_manifest_evidence.v1")
        self.assertEqual(missing["status"], "manifest_missing_validation_pending")
        self.assertEqual(missing["scope"], "read_only_local_manifest_evidence_not_manifest_writer")
        self.assertEqual(missing["mode"], "cache_only_read_only_manifest_evidence")
        self.assertFalse(missing["manifest_exists"])
        self.assertEqual(missing["dataset_count"], 6)
        self.assertEqual(missing["validated_dataset_count"], 0)
        self.assertFalse(missing["dataset_version_manifest_validated"])
        self.assertFalse(missing["dataset_version_manifest_written"])
        self.assertFalse(missing["manifest_writer_task_executed"])
        self.assertEqual(missing["dataset_version_migration_executed_count"], 0)
        self.assertFalse(missing["manifest_written_on_get"])
        self.assertFalse(missing["cache_get_writes_files"])
        self.assertFalse(missing["cache_get_reads_parquet_payloads"])
        self.assertFalse(missing["external_calls_triggered"])
        self.assertFalse(missing["tushare_called"])
        self.assertFalse(missing["deepseek_called"])
        self.assertFalse(missing["github_called"])
        self.assertTrue(missing["does_not_execute_trades"])
        self.assertEqual(missing["call_ledger"][0]["api"], "local_storage_dataset_version_manifest_evidence")
        self.assertFalse(missing["call_ledger"][0]["external"])

        root.mkdir(parents=True, exist_ok=True)
        manifest_path = root / "_dataset_versions.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "datasets": {
                        dataset: {"schema_version": storage_service.DATASET_SCHEMA_CONTRACTS[dataset]["schema_version"]}
                        for dataset in storage_service.CANONICAL_PARQUET_DATASETS
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        ready = storage_service.storage_dataset_version_manifest_evidence_audit()

        self.assertEqual(ready["status"], "manifest_validation_ready_local_only")
        self.assertTrue(ready["manifest_exists"])
        self.assertTrue(ready["dataset_version_manifest_validated"])
        self.assertEqual(ready["validated_dataset_count"], 6)
        self.assertEqual(ready["dataset_version_migration_executed_count"], 0)
        self.assertFalse(ready["dataset_version_manifest_written"])
        self.assertFalse(ready["manifest_writer_task_executed"])
        self.assertFalse(ready["manifest_written_on_get"])
        self.assertFalse(ready["cache_get_writes_files"])
        self.assertFalse(ready["cache_get_reads_parquet_payloads"])
        self.assertTrue(all(row["version_match"] for row in ready["rows"]))
        self.assertTrue(all(row["dataset_version_migration_executed"] is False for row in ready["rows"]))

    def test_storage_cache_ttl_marks_fresh_local_dataset(self):
        if importlib.util.find_spec("pyarrow") is None or importlib.util.find_spec("pandas") is None:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        import pandas as pd

        root = self._with_parquet_root()
        storage_service.parquet_store.write_dataset(
            pd.DataFrame({"ts_code": ["002008.SZ"], "trade_date": ["20260611"], "close": [10.8]}),
            root=root,
            name="daily",
        )

        status = storage_service.parquet_dataset_status("daily")

        self.assertEqual(status["cache_ttl"]["ttl_state"], "fresh")
        self.assertEqual(status["cache_ttl"]["stale_reason"], "within_ttl")
        self.assertFalse(status["cache_ttl"]["auto_refresh_on_get"])
        self.assertEqual(status["compaction_plan"]["status"], "not_needed")
        self.assertEqual(status["compaction_plan"]["reason"], "size_within_threshold")
        self.assertFalse(status["compaction_plan"]["manual_compaction_recommended"])
        self.assertFalse(status["compaction_plan"]["auto_compact_on_get"])
        self.assertFalse(status["compaction_plan"]["external_calls_triggered"])
        self.assertFalse(status["external_calls_triggered"])

    def test_storage_compaction_plan_recommends_manual_task_for_large_cache(self):
        if importlib.util.find_spec("pyarrow") is None or importlib.util.find_spec("pandas") is None:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        import pandas as pd

        root = self._with_parquet_root()
        out = storage_service.parquet_store.write_dataset(
            pd.DataFrame({"ts_code": ["002008.SZ"], "trade_date": ["20260611"], "close": [10.8]}),
            root=root,
            name="daily",
        )
        original_threshold = storage_service.DATASET_COMPACTION_SIZE_THRESHOLD_BYTES
        storage_service.DATASET_COMPACTION_SIZE_THRESHOLD_BYTES = 1
        self.addCleanup(setattr, storage_service, "DATASET_COMPACTION_SIZE_THRESHOLD_BYTES", original_threshold)

        status = storage_service.parquet_dataset_status("daily")

        self.assertEqual(status["compaction_plan"]["status"], "manual_compaction_recommended")
        self.assertEqual(status["compaction_plan"]["reason"], "size_exceeds_threshold")
        self.assertTrue(status["compaction_plan"]["manual_compaction_recommended"])
        self.assertTrue(status["compaction_plan"]["manual_compaction_task_required"])
        self.assertFalse(status["compaction_plan"]["auto_compact_on_get"])
        self.assertFalse(status["compaction_plan"]["physical_compaction_executed"])
        self.assertFalse(status["compaction_plan"]["external_calls_triggered"])
        self.assertTrue(status["compaction_plan"]["does_not_execute_trades"])

    def test_storage_compaction_dry_run_task_never_rewrites_parquet(self):
        if importlib.util.find_spec("pyarrow") is None or importlib.util.find_spec("pandas") is None:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        import pandas as pd

        db_path = self._with_meta_store()
        root = self._with_parquet_root()
        out = storage_service.parquet_store.write_dataset(
            pd.DataFrame({"ts_code": ["002008.SZ"], "trade_date": ["20260611"], "close": [10.8]}),
            root=root,
            name="daily",
        )
        original_threshold = storage_service.DATASET_COMPACTION_SIZE_THRESHOLD_BYTES
        storage_service.DATASET_COMPACTION_SIZE_THRESHOLD_BYTES = 1
        self.addCleanup(setattr, storage_service, "DATASET_COMPACTION_SIZE_THRESHOLD_BYTES", original_threshold)
        clear_task_statuses_for_tests(clear_persisted=True)
        parquet_path = Path(out["path"])
        before_size = parquet_path.stat().st_size

        task = storage_service.run_storage_compaction_dry_run_task(
            {"source": "unit_test", "token": "SHOULD_DROP", "compaction_allowed": True, "rewrite_parquet_allowed": True}
        )

        self.assertEqual(task["task_type"], "run_storage_compaction_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_compaction_dry_run_completed")
        self.assertEqual(task["output_packet_key"], "command_center_3_storage_compaction_dry_run_packet")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("token", task["payload_safe"])
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_compaction_dry_run")
        self.assertEqual(task["call_ledger"][0]["endpoint"], "POST /api/storage/compaction/dry-run")
        self.assertEqual(task["call_ledger"][0]["call_status"], "dry_run_completed")
        self.assertFalse(task["call_ledger"][0]["external"])
        self.assertTrue(parquet_path.exists())
        self.assertEqual(parquet_path.stat().st_size, before_size)

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_3_storage_compaction_dry_run_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["schema_version"], "command_center_3_storage_compaction_dry_run.v1")
        self.assertEqual(persisted["mode"], "dry_run")
        self.assertEqual(persisted["dataset_count"], 6)
        self.assertEqual(persisted["compaction_ready_count"], 1)
        self.assertEqual(persisted["compaction_executed_count"], 0)
        self.assertFalse(persisted["post_dry_run_writes_parquet"])
        self.assertFalse(persisted["post_dry_run_reads_row_payloads"])
        self.assertFalse(persisted["post_dry_run_reads_env_files"])
        self.assertFalse(persisted["compaction_executed"])
        self.assertFalse(persisted["physical_compaction_executed"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertTrue(persisted["does_not_execute_trades"])
        rows_by_dataset = {row["dataset"]: row for row in persisted["rows"]}
        self.assertEqual(rows_by_dataset["daily"]["compaction_dry_run_status"], "ready_for_manual_compaction")
        self.assertTrue(rows_by_dataset["daily"]["manual_compaction_recommended"])
        self.assertTrue(rows_by_dataset["daily"]["compaction_ready"])
        self.assertFalse(rows_by_dataset["daily"]["would_rewrite_parquet"])
        self.assertFalse(rows_by_dataset["daily"]["post_dry_run_writes_parquet"])
        self.assertEqual(rows_by_dataset["moneyflow"]["compaction_dry_run_status"], "missing_dataset")
        dumped = json.dumps({"task": task, "packet": persisted}, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn('"compaction_allowed": true', dumped)
        self.assertNotIn('"rewrite_parquet_allowed": true', dumped)

    def test_storage_compaction_dry_run_endpoint_is_button_gated_local_task(self):
        self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)
        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).post(
            "/api/storage/compaction/dry-run",
            json={"source": "api_test", "api_key": "SHOULD_DROP", "compaction_allowed": True},
        ).json()

        self.assertTrue(response["ok"])
        self.assertIn("task_id", response["data"])
        task = response["data"]["task"]
        self.assertEqual(task["task_type"], "run_storage_compaction_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_compaction_dry_run_completed")
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_compaction_dry_run")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

    def test_storage_dataset_catalog_is_independent_cache_only_endpoint(self):
        self._with_parquet_root()

        catalog = storage_service.storage_dataset_catalog()

        self.assertEqual(catalog["schema_version"], "command_center_3_storage_dataset_catalog.v1")
        self.assertEqual(catalog["store"], "parquet_duckdb")
        self.assertEqual(catalog["status"], "ready")
        self.assertEqual(catalog["mode"], "cache_only")
        self.assertEqual(catalog["dataset_count"], 6)
        self.assertEqual({item["dataset"] for item in catalog["dataset_catalog"]}, {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertEqual(set(catalog["supported_aliases"]), {"factor-values", "daily-basic", "trade-cal", "backtest-results"})
        self.assertEqual(catalog["dataset_implementation_status"]["status"], "partial_migration")
        self.assertEqual(catalog["dataset_implementation_status"]["local_pipeline_dataset_count"], 1)
        self.assertEqual(catalog["dataset_implementation_status"]["future_button_gated_dataset_count"], 5)
        self.assertEqual(catalog["dataset_implementation_status"]["tushare_capable_dataset_count"], 4)
        self.assertTrue(catalog["dataset_implementation_status"]["all_external_refreshes_button_gated"])
        self.assertTrue(all(item["does_not_execute_trades"] for item in catalog["dataset_catalog"]))
        self.assertTrue(all(item["does_not_modify_strategy_action"] for item in catalog["dataset_catalog"]))
        self.assertTrue(catalog["cache_only"])
        self.assertFalse(catalog["external_calls_triggered"])
        self.assertFalse(catalog["tushare_called"])
        self.assertFalse(catalog["deepseek_called"])
        self.assertFalse(catalog["github_called"])
        self.assertTrue(catalog["does_not_execute_trades"])
        self.assertTrue(catalog["does_not_modify_strategy_action"])
        self.assertIn("artifact_hygiene", catalog)
        self.assertEqual(catalog["artifact_hygiene"]["cleanup_policy"], "manual_only_no_delete_on_get")
        self.assertFalse(catalog["artifact_hygiene"]["delete_files_on_get"])
        self.assertFalse(catalog["artifact_hygiene"]["external_calls_triggered"])
        self.assertIn("artifact_cleanup_review_contract", catalog)
        self.assertIn("artifact_cleanup_review_rows", catalog)
        self.assertEqual(
            catalog["artifact_cleanup_review_contract"]["schema_version"],
            "command_center_3_storage_artifact_cleanup_review_contract.v1",
        )
        self.assertTrue(catalog["artifact_cleanup_review_contract"]["manual_approval_required"])
        self.assertFalse(catalog["artifact_cleanup_review_contract"]["delete_executed"])
        self.assertFalse(catalog["artifact_cleanup_review_contract"]["safe_delete_command_generated"])
        self.assertTrue(catalog["artifact_cleanup_review_contract"]["cleanup_review_is_not_delete_execution"])
        self.assertFalse(catalog["artifact_cleanup_review_contract"]["production_cleanup_complete"])
        self.assertIn("schema_migration_preflight", catalog)
        self.assertEqual(catalog["schema_migration_preflight"]["status"], "preflight_ready")
        self.assertEqual(catalog["schema_migration_preflight"]["dataset_count"], 6)
        self.assertEqual(catalog["schema_migration_preflight"]["migration_executed_count"], 0)
        self.assertEqual(len(catalog["schema_migration_rows"]), 6)
        self.assertEqual(catalog["schema_migration_status_counts"]["contract_ready_physical_validation_pending"], 6)
        self.assertFalse(catalog["schema_migration_preflight"]["cache_get_writes_files"])
        self.assertFalse(catalog["schema_migration_preflight"]["external_calls_triggered"])
        self.assertIn("dataset_version_policy", catalog)
        self.assertEqual(catalog["dataset_version_policy"]["status"], "policy_ready")
        self.assertEqual(catalog["dataset_version_policy"]["target_version_declared_count"], 6)
        self.assertEqual(catalog["dataset_version_policy"]["physical_dataset_version_validated_count"], 0)
        self.assertEqual(catalog["dataset_version_policy"]["dataset_version_migration_executed_count"], 0)
        self.assertFalse(catalog["dataset_version_policy"]["cache_get_writes_files"])
        self.assertEqual(len(catalog["dataset_version_rows"]), 6)
        self.assertIn("contract_declared_dataset_missing", catalog["dataset_version_status_counts"])
        self.assertIn("dataset_version_manifest_evidence_audit", catalog)
        self.assertEqual(
            catalog["dataset_version_manifest_evidence_audit"]["schema_version"],
            "command_center_3_storage_dataset_version_manifest_evidence.v1",
        )
        self.assertEqual(catalog["dataset_version_manifest_evidence_audit"]["status"], "manifest_missing_validation_pending")
        self.assertEqual(catalog["dataset_version_manifest_evidence_audit"]["scope"], "read_only_local_manifest_evidence_not_manifest_writer")
        self.assertFalse(catalog["dataset_version_manifest_evidence_audit"]["dataset_version_manifest_validated"])
        self.assertFalse(catalog["dataset_version_manifest_evidence_audit"]["manifest_written_on_get"])
        self.assertFalse(catalog["dataset_version_manifest_evidence_audit"]["cache_get_writes_files"])
        self.assertFalse(catalog["dataset_version_manifest_evidence_audit"]["cache_get_reads_parquet_payloads"])
        self.assertEqual(len(catalog["dataset_version_manifest_evidence_rows"]), 6)
        self.assertIn("manifest_missing_validation_pending", catalog["dataset_version_manifest_evidence_status_counts"])
        self.assertIn("duckdb_query_service", catalog)
        self.assertEqual(catalog["duckdb_query_service"]["schema_version"], "command_center_3_storage_duckdb_query_service.v1")
        self.assertIn(catalog["duckdb_query_service_status"], {"service_ready", "dependency_missing"})
        self.assertEqual(len(catalog["duckdb_query_service_rows"]), 6)
        self.assertEqual(catalog["duckdb_query_service"]["query_wrapper"], "duckdb_filtered_parquet.v1")
        self.assertEqual(catalog["duckdb_query_service"]["max_limit"], 10000)
        self.assertTrue(catalog["duckdb_query_service"]["safe_parameter_binding"])
        self.assertTrue(catalog["duckdb_query_service"]["typed_projection_enabled"])
        self.assertTrue(catalog["duckdb_query_service"]["query_result_contract_enabled"])
        self.assertTrue(catalog["duckdb_query_service"]["cursor_pagination_enabled"])
        self.assertIn("cursor", catalog["duckdb_query_service"]["supported_filter_params"])
        self.assertFalse(catalog["duckdb_query_service"]["frontend_executes_query"])
        self.assertFalse(catalog["duckdb_query_service"]["cache_get_writes_files"])
        self.assertIn("production_readiness", catalog)
        self.assertIn("storage_production_blocker_audit", catalog)
        self.assertEqual(catalog["storage_production_blocker_audit"]["schema_version"], "command_center_3_storage_production_blocker_audit.v1")
        self.assertEqual(catalog["storage_production_blocker_audit"]["status"], "storage_production_blocked")
        self.assertFalse(catalog["storage_production_blocker_audit"]["production_storage_complete"])
        self.assertTrue(catalog["storage_production_blocker_audit"]["dry_runs_are_not_production_completion"])
        self.assertTrue(catalog["storage_production_blocker_audit"]["dataset_version_manifest_evidence_is_read_only"])
        self.assertEqual(len(catalog["storage_production_blocker_rows"]), 10)
        self.assertEqual(catalog["production_readiness"]["artifact_hygiene_policy"], "path_only_manual_cleanup_no_delete_on_get")
        self.assertIn("manual_review_ready", catalog["production_readiness"]["artifact_cleanup_review_status"])
        self.assertTrue(catalog["production_readiness"]["artifact_cleanup_manual_review_required"])
        self.assertEqual(catalog["production_readiness"]["artifact_cleanup_delete_executed_count"], 0)
        self.assertFalse(catalog["production_readiness"]["artifact_cleanup_delete_command_generated"])
        self.assertTrue(catalog["production_readiness"]["artifact_cleanup_review_is_not_delete_execution"])
        self.assertEqual(catalog["production_readiness"]["dataset_version_policy"], "contract_only_manifest_write_requires_explicit_task")
        self.assertEqual(catalog["production_readiness"]["dataset_version_policy_status"], "policy_ready")
        self.assertEqual(catalog["production_readiness"]["dataset_version_manifest_evidence_status"], "manifest_missing_validation_pending")
        self.assertFalse(catalog["production_readiness"]["dataset_version_manifest_evidence_validated"])
        self.assertFalse(catalog["production_readiness"]["dataset_version_manifest_evidence_written_on_get"])
        self.assertEqual(catalog["production_readiness"]["schema_migration_policy"], "preflight_only_no_physical_migration_on_get")
        self.assertEqual(catalog["production_readiness"]["schema_validation_dry_run_route"], "POST /api/storage/schema-validation/dry-run")
        self.assertTrue(catalog["production_readiness"]["schema_validation_dry_run_button_gated"])
        self.assertEqual(catalog["production_readiness"]["duckdb_query_service_policy"], "read_only_service_wrappers_local_parquet_only")
        self.assertEqual(catalog["production_readiness"]["duckdb_query_service_dataset_count"], 6)
        self.assertTrue(catalog["production_readiness"]["duckdb_query_typed_projection_enabled"])
        self.assertTrue(catalog["production_readiness"]["duckdb_query_result_contract_enabled"])
        self.assertTrue(catalog["production_readiness"]["duckdb_query_cursor_pagination_enabled"])
        self.assertFalse(catalog["production_readiness"]["duckdb_query_frontend_executes_queries"])
        self.assertFalse(catalog["production_readiness"]["duckdb_query_cache_get_external_calls"])
        self.assertFalse(catalog["production_readiness"]["duckdb_query_cache_get_writes_files"])
        self.assertEqual(catalog["production_readiness"]["partition_migration_dry_run_route"], "POST /api/storage/partition-migration/dry-run")
        self.assertTrue(catalog["production_readiness"]["partition_migration_dry_run_button_gated"])
        self.assertEqual(catalog["production_readiness"]["compaction_dry_run_route"], "POST /api/storage/compaction/dry-run")
        self.assertTrue(catalog["production_readiness"]["compaction_dry_run_button_gated"])
        self.assertFalse(catalog["production_readiness"]["compaction_dry_run_writes_parquet"])
        self.assertEqual(catalog["call_ledger"][0]["api"], "local_storage_dataset_catalog_cache")
        self.assertEqual(catalog["call_ledger"][0]["endpoint"], "GET /api/storage/catalog")
        self.assertEqual(catalog["call_ledger"][0]["row_count"], 6)
        self.assertFalse(catalog["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/catalog", catalog["warnings"][0])

    def test_storage_artifact_hygiene_is_path_only_manual_preflight(self):
        original_root = storage_service.PROJECT_ROOT
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        (root / ".stock_ming_3").mkdir()
        (root / ".stock_ming_3" / "meta.sqlite").write_text("local fixture", encoding="utf-8")
        (root / "desktop" / "dist").mkdir(parents=True)
        (root / "desktop" / "src-tauri" / "target").mkdir(parents=True)
        storage_service.PROJECT_ROOT = root
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, storage_service, "PROJECT_ROOT", original_root)

        hygiene = storage_service.storage_artifact_hygiene_status()

        self.assertEqual(hygiene["schema_version"], "command_center_3_storage_artifact_hygiene.v1")
        self.assertEqual(hygiene["status"], "audit_ready")
        self.assertEqual(hygiene["scope"], "local_generated_artifact_hygiene")
        self.assertGreaterEqual(hygiene["present_artifact_count"], 3)
        self.assertEqual(hygiene["review_required_count"], 0)
        self.assertEqual(hygiene["cleanup_policy"], "manual_only_no_delete_on_get")
        self.assertEqual(hygiene["cleanup_task_status"], "dry_run_button_gated")
        self.assertEqual(hygiene["cleanup_dry_run_route"], "POST /api/storage/artifact-hygiene/dry-run")
        self.assertTrue(hygiene["dry_run_required_before_delete"])
        self.assertFalse(hygiene["delete_files_on_get"])
        self.assertFalse(hygiene["auto_cleanup_on_get"])
        self.assertTrue(hygiene["does_not_scan_secret_values"])
        self.assertTrue(hygiene["does_not_read_file_payloads"])
        self.assertTrue(hygiene["does_not_read_env_files"])
        self.assertIn("artifact_cleanup_review_contract", hygiene)
        self.assertIn("artifact_cleanup_review_rows", hygiene)
        review = hygiene["artifact_cleanup_review_contract"]
        self.assertEqual(review["schema_version"], "command_center_3_storage_artifact_cleanup_review_contract.v1")
        self.assertEqual(review["status"], "manual_review_ready_delete_pending")
        self.assertTrue(review["manual_approval_required"])
        self.assertTrue(review["dry_run_required_before_delete"])
        self.assertFalse(review["delete_execution_task_available"])
        self.assertFalse(review["delete_executed"])
        self.assertEqual(review["delete_executed_count"], 0)
        self.assertFalse(review["safe_delete_command_generated"])
        self.assertTrue(review["delete_command_not_generated"])
        self.assertTrue(review["cleanup_review_is_not_delete_execution"])
        self.assertFalse(review["production_cleanup_complete"])
        self.assertFalse(review["reads_payloads"])
        self.assertFalse(review["post_dry_run_external_calls"])
        self.assertEqual(hygiene["artifact_cleanup_review_required_step_count"], review["required_review_step_count"])
        self.assertIn("review_no_delete_execution", {row["review_step"] for row in hygiene["artifact_cleanup_review_rows"]})
        self.assertFalse(hygiene["external_calls_triggered"])
        self.assertFalse(hygiene["tushare_called"])
        self.assertFalse(hygiene["deepseek_called"])
        self.assertFalse(hygiene["github_called"])
        self.assertTrue(hygiene["does_not_execute_trades"])
        self.assertFalse(hygiene["data_files_allowed_in_git"])
        rows_by_artifact = {row["artifact"]: row for row in hygiene["rows"]}
        self.assertEqual(rows_by_artifact["command_center_runtime_cache"]["status"], "present_local_only")
        self.assertEqual(rows_by_artifact["command_center_runtime_cache"]["top_level_entry_count"], 1)
        self.assertEqual(rows_by_artifact["desktop_build_output"]["status"], "present_local_only")
        self.assertEqual(rows_by_artifact["tauri_build_output"]["status"], "present_local_only")
        self.assertFalse(rows_by_artifact["command_center_runtime_cache"]["delete_files_on_get"])
        self.assertTrue(all(row["does_not_read_file_payloads"] for row in hygiene["rows"]))
        self.assertIn("*.sqlite", hygiene["git_excluded_patterns"])
        self.assertIn(".stock_ming_3/", hygiene["git_excluded_patterns"])
        self.assertNotIn("local fixture", json.dumps(hygiene, ensure_ascii=False))

    def test_storage_artifact_cleanup_dry_run_task_never_deletes_or_reads_payloads(self):
        db_path = self._with_meta_store()
        original_root = storage_service.PROJECT_ROOT
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        (root / ".stock_ming_3").mkdir()
        (root / ".stock_ming_3" / "meta.sqlite").write_text("local fixture secret=SHOULD_NOT_LEAK", encoding="utf-8")
        (root / "desktop" / "dist").mkdir(parents=True)
        storage_service.PROJECT_ROOT = root
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, storage_service, "PROJECT_ROOT", original_root)
        clear_task_statuses_for_tests(clear_persisted=True)

        task = storage_service.run_storage_artifact_cleanup_dry_run_task(
            {"source": "unit_test", "api_key": "SHOULD_DROP", "confirm_delete": True}
        )

        self.assertEqual(task["task_type"], "run_storage_artifact_cleanup_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_artifact_cleanup_dry_run_completed")
        self.assertEqual(task["output_packet_key"], "command_center_3_storage_artifact_cleanup_dry_run_packet")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_artifact_cleanup_dry_run")
        self.assertEqual(task["call_ledger"][0]["endpoint"], "POST /api/storage/artifact-hygiene/dry-run")
        self.assertFalse(task["call_ledger"][0]["external"])
        self.assertEqual(task["call_ledger"][0]["call_status"], "dry_run_completed")
        self.assertTrue((root / ".stock_ming_3" / "meta.sqlite").exists())

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_3_storage_artifact_cleanup_dry_run_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["mode"], "dry_run")
        self.assertEqual(persisted["cleanup_policy"], "dry_run_only_no_delete")
        self.assertFalse(persisted["delete_files_on_post"])
        self.assertFalse(persisted["auto_cleanup_on_post"])
        self.assertFalse(persisted["would_delete_files"])
        self.assertIn("artifact_cleanup_review_contract", persisted)
        review = persisted["artifact_cleanup_review_contract"]
        self.assertEqual(review["schema_version"], "command_center_3_storage_artifact_cleanup_review_contract.v1")
        self.assertEqual(review["status"], "manual_review_ready_delete_pending")
        self.assertTrue(review["manual_approval_required"])
        self.assertFalse(review["delete_execution_task_available"])
        self.assertFalse(review["delete_executed"])
        self.assertFalse(review["safe_delete_command_generated"])
        self.assertTrue(review["cleanup_review_is_not_delete_execution"])
        self.assertFalse(review["production_cleanup_complete"])
        self.assertFalse(review["reads_payloads"])
        self.assertFalse(review["post_dry_run_external_calls"])
        self.assertEqual(persisted["artifact_cleanup_review_status"], review["status"])
        self.assertEqual(persisted["artifact_cleanup_review_required_step_count"], review["required_review_step_count"])
        self.assertFalse(persisted["safe_delete_command_generated"])
        self.assertFalse(persisted["production_cleanup_complete"])
        self.assertTrue(persisted["cleanup_review_is_not_delete_execution"])
        self.assertIn("review_manual_approval_required", {row["review_step"] for row in persisted["artifact_cleanup_review_rows"]})
        self.assertTrue(persisted["does_not_read_file_payloads"])
        self.assertTrue(persisted["does_not_scan_secret_values"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertTrue(persisted["does_not_execute_trades"])
        rows_by_artifact = {row["artifact"]: row for row in persisted["candidate_rows"]}
        self.assertEqual(rows_by_artifact["command_center_runtime_cache"]["dry_run_status"], "present_manual_review_required")
        self.assertFalse(rows_by_artifact["command_center_runtime_cache"]["would_delete_on_this_task"])
        self.assertEqual(rows_by_artifact["desktop_build_output"]["candidate_action"], "manual_cleanup_candidate_after_review")
        dumped = json.dumps({"task": task, "packet": persisted}, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn("SHOULD_NOT_LEAK", dumped)

    def test_storage_artifact_cleanup_dry_run_endpoint_is_button_gated_local_task(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).post(
            "/api/storage/artifact-hygiene/dry-run",
            json={"source": "api_test", "token": "SHOULD_DROP", "confirm_delete": True},
        ).json()

        self.assertTrue(response["ok"])
        self.assertIn("task_id", response["data"])
        task = response["data"]["task"]
        self.assertEqual(task["task_type"], "run_storage_artifact_cleanup_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_artifact_cleanup_dry_run_completed")
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_artifact_cleanup_dry_run")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("token", task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

    def test_storage_schema_validation_dry_run_task_reads_schema_metadata_only(self):
        if importlib.util.find_spec("pyarrow") is None or importlib.util.find_spec("pandas") is None:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        import pandas as pd

        db_path = self._with_meta_store()
        root = self._with_parquet_root()
        storage_service.parquet_store.write_dataset(
            pd.DataFrame(
                {
                    "ts_code": ["002008.SZ"],
                    "trade_date": ["20260611"],
                    "open": [10.1],
                    "high": [10.8],
                    "low": [9.9],
                    "close": [10.5],
                    "vol": [12345],
                    "amount": [45678.0],
                }
            ),
            root=root,
            name="daily",
        )
        storage_service.parquet_store.write_dataset(
            pd.DataFrame({"ts_code": ["002008.SZ"], "trade_date": ["20260611"]}),
            root=root,
            name="daily_basic",
        )
        clear_task_statuses_for_tests(clear_persisted=True)

        task = storage_service.run_storage_schema_validation_dry_run_task(
            {"source": "unit_test", "token": "SHOULD_DROP", "write_parquet_allowed": True}
        )

        self.assertEqual(task["task_type"], "run_storage_schema_validation_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_schema_validation_dry_run_completed")
        self.assertEqual(task["output_packet_key"], "command_center_3_storage_schema_validation_dry_run_packet")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("token", task["payload_safe"])
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_schema_validation_dry_run")
        self.assertEqual(task["call_ledger"][0]["endpoint"], "POST /api/storage/schema-validation/dry-run")
        self.assertEqual(task["call_ledger"][0]["call_status"], "dry_run_completed")
        self.assertFalse(task["call_ledger"][0]["external"])

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_3_storage_schema_validation_dry_run_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["schema_version"], "command_center_3_storage_schema_validation_dry_run.v1")
        self.assertEqual(persisted["mode"], "dry_run")
        self.assertEqual(persisted["dataset_count"], 6)
        self.assertEqual(persisted["schema_migration_executed_count"], 0)
        self.assertFalse(persisted["post_dry_run_writes_parquet"])
        self.assertFalse(persisted["post_dry_run_reads_row_payloads"])
        self.assertFalse(persisted["post_dry_run_reads_env_files"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertTrue(persisted["does_not_execute_trades"])
        rows_by_dataset = {row["dataset"]: row for row in persisted["rows"]}
        self.assertEqual(rows_by_dataset["daily"]["validation_status"], "schema_validated")
        self.assertTrue(rows_by_dataset["daily"]["validation_passed"])
        self.assertTrue(rows_by_dataset["daily"]["physical_validation_done"])
        self.assertTrue(rows_by_dataset["daily"]["schema_read_done"])
        self.assertFalse(rows_by_dataset["daily"]["reads_file_payloads"])
        self.assertFalse(rows_by_dataset["daily"]["physical_validation_reads_payloads"])
        self.assertTrue(rows_by_dataset["daily"]["schema_migration_ready_for_execution"])
        self.assertEqual(rows_by_dataset["daily"]["row_count_metadata"], 1)
        self.assertEqual(rows_by_dataset["daily_basic"]["validation_status"], "schema_mismatch")
        self.assertIn("turnover_rate", rows_by_dataset["daily_basic"]["missing_required_columns"])
        self.assertFalse(rows_by_dataset["daily_basic"]["schema_migration_ready_for_execution"])
        self.assertEqual(rows_by_dataset["moneyflow"]["validation_status"], "missing_dataset")
        self.assertGreaterEqual(persisted["missing_dataset_count"], 4)
        dumped = json.dumps({"task": task, "packet": persisted}, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn('"write_parquet_allowed": true', dumped)

    def test_storage_schema_validation_dry_run_endpoint_is_button_gated_local_task(self):
        self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)
        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).post(
            "/api/storage/schema-validation/dry-run",
            json={"source": "api_test", "api_key": "SHOULD_DROP", "write_parquet_allowed": True},
        ).json()

        self.assertTrue(response["ok"])
        self.assertIn("task_id", response["data"])
        task = response["data"]["task"]
        self.assertEqual(task["task_type"], "run_storage_schema_validation_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_schema_validation_dry_run_completed")
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_schema_validation_dry_run")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

    def test_storage_partition_migration_dry_run_plans_without_writing_partitions(self):
        if importlib.util.find_spec("pyarrow") is None or importlib.util.find_spec("pandas") is None:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        import pandas as pd

        db_path = self._with_meta_store()
        root = self._with_parquet_root()
        storage_service.parquet_store.write_dataset(
            pd.DataFrame(
                {
                    "ts_code": ["002008.SZ"],
                    "trade_date": ["20260611"],
                    "open": [10.1],
                    "high": [10.8],
                    "low": [9.9],
                    "close": [10.5],
                    "vol": [12345],
                    "amount": [45678.0],
                }
            ),
            root=root,
            name="daily",
        )
        storage_service.parquet_store.write_dataset(
            pd.DataFrame({"ts_code": ["002008.SZ"], "trade_date": ["20260611"]}),
            root=root,
            name="daily_basic",
        )
        clear_task_statuses_for_tests(clear_persisted=True)

        task = storage_service.run_storage_partition_migration_dry_run_task(
            {"source": "unit_test", "token": "SHOULD_DROP", "partition_migration_allowed": True}
        )

        self.assertEqual(task["task_type"], "run_storage_partition_migration_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_partition_migration_dry_run_completed")
        self.assertEqual(task["output_packet_key"], "command_center_3_storage_partition_migration_dry_run_packet")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("token", task["payload_safe"])
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_partition_migration_dry_run")
        self.assertEqual(task["call_ledger"][0]["endpoint"], "POST /api/storage/partition-migration/dry-run")
        self.assertEqual(task["call_ledger"][0]["call_status"], "dry_run_completed")
        self.assertFalse(task["call_ledger"][0]["external"])

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_3_storage_partition_migration_dry_run_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["schema_version"], "command_center_3_storage_partition_migration_dry_run.v1")
        self.assertEqual(persisted["mode"], "dry_run")
        self.assertEqual(persisted["dataset_count"], 6)
        self.assertEqual(persisted["partition_migration_executed_count"], 0)
        self.assertFalse(persisted["post_dry_run_writes_parquet"])
        self.assertFalse(persisted["post_dry_run_reads_row_payloads"])
        self.assertFalse(persisted["post_dry_run_reads_env_files"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertTrue(persisted["does_not_execute_trades"])
        rows_by_dataset = {row["dataset"]: row for row in persisted["rows"]}
        self.assertEqual(rows_by_dataset["daily"]["partition_migration_status"], "ready_for_manual_partition_migration")
        self.assertEqual(rows_by_dataset["daily"]["partition_columns"], ["trade_date"])
        self.assertTrue(rows_by_dataset["daily"]["partition_migration_ready"])
        self.assertFalse(rows_by_dataset["daily"]["would_write_partitioned_dataset"])
        self.assertFalse(rows_by_dataset["daily"]["post_dry_run_writes_parquet"])
        self.assertFalse(rows_by_dataset["daily"]["post_dry_run_reads_row_payloads"])
        self.assertEqual(rows_by_dataset["daily_basic"]["partition_migration_status"], "blocked_schema_validation")
        self.assertEqual(rows_by_dataset["moneyflow"]["partition_migration_status"], "missing_dataset")
        self.assertGreaterEqual(persisted["missing_dataset_count"], 4)
        self.assertFalse(storage_service.parquet_store.partitioned_dataset_path(root=root, name="daily").exists())
        dumped = json.dumps({"task": task, "packet": persisted}, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn('"partition_migration_allowed": true', dumped)

    def test_storage_partition_migration_dry_run_endpoint_is_button_gated_local_task(self):
        self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)
        from fastapi.testclient import TestClient
        from server.main import app

        response = TestClient(app).post(
            "/api/storage/partition-migration/dry-run",
            json={"source": "api_test", "api_key": "SHOULD_DROP", "partition_migration_allowed": True},
        ).json()

        self.assertTrue(response["ok"])
        self.assertIn("task_id", response["data"])
        task = response["data"]["task"]
        self.assertEqual(task["task_type"], "run_storage_partition_migration_dry_run")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "storage_partition_migration_dry_run_completed")
        self.assertEqual(task["call_ledger"][0]["api"], "local_storage_partition_migration_dry_run")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

    def test_storage_sqlite_meta_status_lists_metadata_without_payloads(self):
        db_path = self._with_meta_store()
        from storage.sqlite_meta import SQLiteMetaStore

        store = SQLiteMetaStore(db_path)
        store.write_packet("command_center_factor_quant_hub_packet", {"packet_key": "command_center_factor_quant_hub_packet", "status": "ready", "token": "SHOULD_DROP"})
        task_service.create_task_stub("refresh_factor_data", payload={"api_key": "DROP"})

        status = storage_service.sqlite_meta_status()

        self.assertEqual(status["store"], "sqlite_meta")
        self.assertEqual(status["status"], "ready")
        self.assertEqual(status["packet_count"], 1)
        self.assertGreaterEqual(status["task_count"], 1)
        self.assertTrue(status["cache_only"])
        self.assertTrue(status["does_not_return_payload_json"])
        self.assertFalse(status["metadata_is_payload_only"])
        self.assertIn("metadata_safe_columns", status)
        self.assertIn("metadata_source_rows", status)
        self.assertEqual({row["source"] for row in status["metadata_source_rows"]}, {"packet_metadata", "task_metadata"})
        self.assertTrue(all(row["payload_json_returned"] is False for row in status["metadata_source_rows"]))
        self.assertEqual(status["packet_status_counts"]["ready"], 1)
        self.assertGreaterEqual(status["task_status_counts"]["success"], 1)
        self.assertEqual(status["task_metadata"][0]["storage_source"], "sqlite_meta")
        self.assertIn("storage_source", status["metadata_safe_columns"]["task_metadata"])
        self.assertFalse(status["external_calls_triggered"])
        self.assertFalse(status["tushare_called"])
        self.assertTrue(status["does_not_execute_trades"])
        self.assertEqual(status["call_ledger"][0]["api"], "local_storage_sqlite_meta_cache")
        self.assertFalse(status["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/sqlite-meta", status["warnings"][0])
        self.assertIn("packet_key", status["packet_metadata"][0])
        self.assertNotIn("payload_json", status["packet_metadata"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(status, ensure_ascii=False))

    def test_storage_dataset_rejects_unsupported_names_without_external_calls(self):
        self._with_parquet_root()

        status = storage_service.parquet_dataset_status("../secret")

        self.assertEqual(status["status"], "unsupported_dataset")
        self.assertEqual(set(status["supported_datasets"]), {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertEqual(set(status["supported_aliases"]), {"factor-values", "daily-basic", "trade-cal", "backtest-results"})
        self.assertFalse(status["external_calls_triggered"])
        self.assertFalse(status["tushare_called"])
        self.assertEqual(status["call_ledger"][0]["api"], "local_storage_dataset_cache")
        self.assertFalse(status["call_ledger"][0]["external"])

    def test_trade_review_cache_reads_local_log_without_external_calls(self):
        self._with_trade_review_log(
            [
                {
                    "id": "r1",
                    "created_at": "2026-06-10T09:30:00",
                    "ticker": "002008.SZ",
                    "user_decision": "观察",
                    "overall_action": "等待",
                    "strategy_action": "wait",
                    "user_note": "复盘纪律",
                    "api_key": "SHOULD_DROP",
                    "deepseek_summary": "Traceback token=SHOULD_DROP",
                }
            ]
        )

        packet = trade_review_service.read_trade_review_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_trade_review_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertTrue(packet["cache_only"])
        self.assertTrue(packet["read_only"])
        self.assertEqual(packet["record_count"], 1)
        self.assertEqual(packet["records"][0]["ticker"], "002008.SZ")
        self.assertNotIn("api_key", packet["records"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertEqual(packet["call_ledger"][0]["api"], "local_trade_review_log")
        self.assertEqual(packet["call_ledger"][0]["call_status"], "cache_read")
        self.assertIn("GET /api/trade-review/cache", packet["warnings"][0])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_write_cache"])
        self.assertFalse(packet["contains_secret"])
        json.dumps(packet, ensure_ascii=False)

    def test_quant_cache_reads_local_quant_packet_without_running_backtest(self):
        self._with_snapshot_cache(
            {
                "quant_packet": {
                    "status": "ready",
                    "score": 68,
                    "confidence": "中",
                    "action_state": "轻仓验证",
                    "data_status": "ready",
                    "summary": "量化缓存可参考",
                    "evidence_items": ["量化分数：68"],
                    "risk_notes": ["回测收益不代表未来收益"],
                    "decision_brief": {"status": "ready", "headline": "量化可进入证据链"},
                    "api_key": "SHOULD_DROP",
                }
            }
        )

        packet = quant_service.read_quant_backtest_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_quant_backtest_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertEqual(packet["source_packet_key"], "command_center_quant_packet")
        self.assertEqual(packet["quant_packet"]["score"], 68)
        self.assertNotIn("api_key", packet["quant_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_run_backtest"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_quant_backtest_cache")
        self.assertIn("GET /api/quant/cache", packet["warnings"][0])
        json.dumps(packet, ensure_ascii=False)

    def test_strategy_trace_cache_reads_strategy_and_decision_without_mutating_action(self):
        self._with_snapshot_cache(
            {
                "strategy_packet": {
                    "status": "ready",
                    "action": "等待",
                    "confidence": "中",
                    "position_advice": "只观察，不追高。",
                    "summary": "结构化规则给出等待。",
                    "strategy_execution_trace": {
                        "input_sources": [{"name": "量化推演", "status": "ready", "used": True, "summary": "缓存可用"}],
                        "rules_fired": [{"rule": "验证不足", "result": "等待", "evidence": "待确认", "impact": "不加仓"}],
                        "missing_inputs": ["交易纪律/回测"],
                        "final_reason": "结构化规则给出等待。",
                        "deepseek_used": False,
                    },
                    "api_key": "SHOULD_DROP",
                },
                "decision_packet": {
                    "status": "ready",
                    "overall_action": "只观察",
                    "market_bias": "中性",
                    "authorization": "Bearer SHOULD_DROP",
                },
            }
        )

        packet = strategy_service.read_strategy_trace_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_strategy_trace_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["action_summary"]["action"], "等待")
        self.assertEqual(packet["action_summary"]["action_source"], "strategy_execution_packet")
        self.assertEqual(packet["decision_summary"]["overall_action"], "只观察")
        self.assertEqual(packet["strategy_trace"]["rules_fired"][0]["rule"], "验证不足")
        self.assertNotIn("api_key", packet["strategy_packet"])
        self.assertNotIn("authorization", packet["decision_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_call_deepseek"])
        self.assertTrue(packet["policy"]["does_not_run_backtest"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_decision_packet"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_strategy_trace_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_position_context_cache_reads_home_snapshot_without_external_calls(self):
        self._with_snapshot_cache(
            {
                "holding_action": {
                    "ticker": "002008.SZ",
                    "name": "大族激光",
                    "shares": 3000,
                    "cost": 108,
                    "current_price": 112,
                    "floating_pnl_text": "浮盈",
                    "action_state": "只观察",
                    "api_key": "SHOULD_DROP",
                },
                "position_risk_budget": {"risk_level": "中", "max_add_amount": 0},
                "risk_breakdown": {"position": "cache"},
                "safety_line": {"stop_loss": 100},
                "today_action": {"overall_action": "只观察"},
                "strategy_packet": {"action": "等待", "confidence": "中", "authorization": "Bearer SHOULD_DROP"},
            }
        )

        packet = position_service.read_position_context_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_position_context_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["position_summary"]["ticker"], "002008.SZ")
        self.assertEqual(packet["holding_action"]["shares"], 3000)
        self.assertEqual(packet["today_action"]["overall_action"], "只观察")
        self.assertEqual(packet["strategy_context"]["action"], "等待")
        self.assertNotIn("api_key", packet["holding_action"])
        self.assertNotIn("authorization", packet["strategy_context"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_call_deepseek"])
        self.assertTrue(packet["policy"]["does_not_recalculate_position"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_position_context_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_candidate_radar_cache_reads_local_candidates_without_market_scan(self):
        self._with_snapshot_cache(
            {
                "radar_packet": {
                    "status": "ready",
                    "summary": "Top3 候选缓存",
                    "manual_required_text": "页面打开不会自动全市场扫描。",
                    "api_key": "SHOULD_DROP",
                },
                "next_ticket_candidates": [
                    {
                        "rank": 1,
                        "ticker": "002837.SZ",
                        "name": "英维克",
                        "score": 47,
                        "status_label": "只观察",
                        "action_state": "只观察",
                        "trigger_condition": "待验证",
                        "authorization": "Bearer SHOULD_DROP",
                    }
                ],
                "candidate_execution_evidence_overview": {"headline": "仍待验证"},
                "next_ticket_evidence_recovery_actions": [{"label": "涨跌停/情绪", "status": "missing"}],
                "a_share_capability_matrix": [
                    {"provider": "Tushare", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "api": "top_list", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "api": "limit_cpt_list", "capability_state": "stale_cache", "status": "使用缓存"},
                    {"provider": "Tushare", "api": "cyq_perf", "capability_state": "empty_recent", "status": "近期无数据"},
                ],
                "data_freshness": {
                    "state": "fresh",
                    "expected_trade_date": "2026-06-12",
                    "data_date": "2026-06-12",
                    "last_updated": "2026-06-12T16:40:00",
                },
            }
        )

        packet = candidate_service.read_candidate_radar_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["counts"]["candidate_count"], 1)
        self.assertEqual(packet["candidate_rows"][0]["ticker"], "002837.SZ")
        self.assertEqual(packet["candidate_rows"][0]["action_state"], "只观察")
        self.assertEqual(packet["freshness_state"]["state"], "fresh")
        self.assertEqual(packet["freshness_state"]["expected_trade_date"], "2026-06-12")
        self.assertGreaterEqual(packet["scan_coverage"]["skipped_reason_count"], 1)
        self.assertEqual(packet["coverage_detail_summary"]["universe_size"], 1)
        self.assertEqual(packet["coverage_detail_summary"]["candidate_input_count"], 1)
        self.assertEqual(packet["coverage_detail_summary"]["candidate_display_limit"], 120)
        self.assertEqual(packet["coverage_detail_summary"]["candidate_display_truncated_count"], 0)
        self.assertFalse(packet["coverage_detail_summary"]["candidate_rows_capped_for_ui"])
        self.assertFalse(packet["coverage_detail_summary"]["large_universe_requires_worker"])
        self.assertEqual(packet["fast_scan_runtime_budget_contract"]["schema_version"], "candidate_radar_fast_scan_runtime_budget.v1")
        self.assertEqual(packet["fast_scan_runtime_budget_contract"]["status"], "fast_scan_runtime_budget_ready")
        self.assertEqual(packet["fast_scan_runtime_budget_contract"]["candidate_input_count"], 1)
        self.assertEqual(packet["fast_scan_runtime_budget_contract"]["candidate_displayed_count"], 1)
        self.assertEqual(packet["fast_scan_runtime_budget_contract"]["candidate_display_truncated_count"], 0)
        self.assertFalse(packet["fast_scan_runtime_budget_contract"]["large_universe_worker_required"])
        self.assertFalse(packet["fast_scan_runtime_budget_contract"]["browser_performance_trace_done"])
        runtime_budget_rows = {row["criterion"]: row for row in packet["fast_scan_runtime_budget_rows"]}
        self.assertEqual(runtime_budget_rows["sync_candidate_display_budget"]["status"], "passed")
        self.assertEqual(runtime_budget_rows["local_pool_sync_input_budget"]["status"], "passed")
        self.assertEqual(runtime_budget_rows["large_universe_worker_boundary"]["status"], "not_required")
        result_delta = packet["result_delta_clarity_contract"]
        result_delta_rows = {row["criterion"]: row for row in packet["result_delta_clarity_rows"]}
        self.assertEqual(result_delta["schema_version"], "candidate_radar_result_delta_clarity.v1")
        self.assertEqual(result_delta["status"], "result_delta_clarity_local_ready_previous_diff_pending")
        self.assertTrue(result_delta["local_result_delta_clarity_ready"])
        self.assertFalse(result_delta["previous_cache_diff_done"])
        self.assertFalse(result_delta["browser_visual_delta_qa_done"])
        self.assertFalse(result_delta["production_radar_replacement_complete"])
        self.assertEqual(result_delta["candidate_count"], 1)
        self.assertEqual(result_delta["provider_gap_count"], 4)
        self.assertGreater(result_delta["visible_gap_count"], 0)
        self.assertEqual(result_delta["production_pending_count"], 2)
        self.assertFalse(result_delta["external_calls_triggered"])
        self.assertFalse(result_delta["tushare_called"])
        self.assertFalse(result_delta["deepseek_called"])
        self.assertFalse(result_delta["github_called"])
        self.assertTrue(result_delta["does_not_execute_trades"])
        self.assertTrue(result_delta["does_not_modify_strategy_action"])
        self.assertEqual(result_delta_rows["candidate_count_and_mix_visible"]["status"], "passed")
        self.assertEqual(result_delta_rows["candidate_display_cap_visible"]["status"], "passed")
        self.assertEqual(result_delta_rows["provider_gap_visibility"]["status"], "gap_reported")
        self.assertEqual(result_delta_rows["previous_cache_diff_pending"]["status"], "pending_previous_cache_diff")
        self.assertEqual(result_delta_rows["browser_visual_delta_qa_pending"]["status"], "pending_visual_qa")
        self.assertTrue(packet["policy"]["result_delta_clarity_contract_is_local"])
        self.assertTrue(packet["policy"]["result_delta_clarity_is_not_previous_cache_diff"])
        self.assertTrue(packet["policy"]["result_delta_clarity_is_not_browser_visual_qa"])
        triage = packet["replacement_gap_triage_contract"]
        triage_rows = {row["gap_key"]: row for row in packet["replacement_gap_triage_rows"]}
        self.assertEqual(triage["schema_version"], "candidate_radar_replacement_gap_triage.v1")
        self.assertEqual(triage["status"], "replacement_gap_triage_local_ready_legacy_retirement_blocked")
        self.assertTrue(triage["local_triage_ready"])
        self.assertFalse(triage["legacy_retirement_ready"])
        self.assertFalse(triage["production_radar_replacement_complete"])
        self.assertTrue(triage["legacy_fallback_required"])
        self.assertGreater(triage["blocking_gap_count"], 0)
        self.assertGreater(triage["critical_gap_count"], 0)
        self.assertIn("legacy_signal_group_mapping", triage["critical_gap_keys"])
        self.assertIn("browser_performance_trace", triage["blocking_gap_keys"])
        self.assertEqual(triage_rows["provider_signal_coverage"]["status"], "gap_reported")
        self.assertEqual(triage_rows["current_freshness_gate"]["status"], "passed")
        self.assertEqual(triage_rows["browser_visual_delta_qa"]["status"], "pending_visual_qa")
        self.assertEqual(triage_rows["full_pool_worker_execution"]["status"], "pending_worker_execution")
        self.assertEqual(triage_rows["deep_scan_execution"]["status"], "pending_worker_execution")
        self.assertEqual(triage_rows["trade_action_isolation"]["status"], "passed")
        self.assertFalse(triage["external_calls_triggered"])
        self.assertFalse(triage["tushare_called"])
        self.assertFalse(triage["deepseek_called"])
        self.assertFalse(triage["github_called"])
        self.assertTrue(triage["does_not_execute_trades"])
        self.assertTrue(triage["does_not_modify_strategy_action"])
        self.assertTrue(packet["policy"]["replacement_gap_triage_contract_is_local"])
        self.assertTrue(packet["policy"]["replacement_gap_triage_is_not_production_replacement"])
        self.assertTrue(packet["policy"]["legacy_radar_retirement_blocked_by_triage"])
        self.assertEqual(packet["coverage_detail_summary"]["provider_signal_group_count"], 5)
        self.assertEqual(packet["coverage_detail_summary"]["provider_blocked_group_count"], 1)
        self.assertEqual(packet["coverage_detail_summary"]["stale_input_group_count"], 1)
        self.assertEqual(packet["coverage_detail_summary"]["missing_provider_data_group_count"], 2)
        self.assertTrue(packet["coverage_detail_summary"]["degraded_mode_active"])
        self.assertFalse(packet["coverage_detail_summary"]["full_pool_scan_done"])
        self.assertTrue(packet["coverage_detail_summary"]["missing_data_is_reported_not_dropped"])
        self.assertEqual(packet["scan_execution_summary"]["schema_version"], "candidate_radar_scan_execution_summary.v1")
        self.assertEqual(packet["scan_execution_summary"]["scan_family"], "cache_view")
        self.assertEqual(packet["scan_execution_summary"]["candidate_input_count"], 1)
        self.assertEqual(packet["scan_execution_summary"]["candidate_row_count"], 1)
        self.assertEqual(packet["scan_execution_summary"]["candidate_display_truncated_count"], 0)
        self.assertEqual(packet["scan_execution_summary"]["provider_gap_count"], 4)
        self.assertTrue(packet["scan_execution_summary"]["cache_view_only"])
        self.assertFalse(packet["scan_execution_summary"]["external_calls_triggered"])
        acceptance_by_key = {row["check_key"]: row for row in packet["scan_acceptance_rows"]}
        self.assertEqual(acceptance_by_key["provider_gap_visibility"]["status"], "gap_reported")
        self.assertEqual(acceptance_by_key["freshness_boundary"]["status"], "passed")
        self.assertEqual(acceptance_by_key["full_pool_boundary"]["status"], "not_executed")
        self.assertEqual(acceptance_by_key["trade_action_boundary"]["status"], "passed")
        provider_by_group = {row["signal_group"]: row for row in packet["provider_coverage_rows"]}
        self.assertEqual(provider_by_group["moneyflow"]["coverage_status"], "available")
        self.assertEqual(provider_by_group["dragon_tiger"]["coverage_status"], "provider_blocked")
        self.assertEqual(provider_by_group["limit_emotion"]["coverage_status"], "stale_input")
        self.assertEqual(provider_by_group["chip_radar"]["coverage_status"], "missing_provider_data")
        self.assertEqual(provider_by_group["hard_risk"]["coverage_status"], "missing_provider_data")
        degraded_by_mode = {row["mode"]: row for row in packet["degraded_mode_rows"]}
        self.assertTrue(degraded_by_mode["provider_blocked"]["active"])
        self.assertTrue(degraded_by_mode["stale_input"]["active"])
        self.assertTrue(degraded_by_mode["missing_provider_data"]["active"])
        self.assertTrue(degraded_by_mode["full_pool_scan_pending"]["active"])
        skipped_reasons = {row["reason"] for row in packet["skipped_reason_rows"]}
        self.assertIn("radar_provider_blocked", skipped_reasons)
        self.assertIn("radar_provider_stale_input", skipped_reasons)
        self.assertIn("radar_provider_missing_data", skipped_reasons)
        self.assertIn("skipped_reason_rows", packet)
        self.assertEqual(packet["legacy_parity_inventory"]["status"], "partial_parity")
        self.assertFalse(packet["legacy_parity_inventory"]["quick_scan_is_full_replacement"])
        self.assertTrue(packet["legacy_parity_inventory"]["slow_paths_are_future_button_tasks"])
        parity_by_key = {row["key"]: row for row in packet["legacy_parity_rows"]}
        self.assertEqual(parity_by_key["top_watch_excluded_split"]["migration_status"], "mapped")
        self.assertIn(parity_by_key["scan_filters"]["migration_status"], {"future_task_required", "missing_reported"})
        self.assertIn("quick_cache_scan", {row["scan_mode"] for row in packet["scan_mode_status_rows"]})
        self.assertIn("full_pool_scan", {row["scan_mode"] for row in packet["scan_mode_status_rows"]})
        output_by_field = {row["field"]: row for row in packet["legacy_output_contract_rows"]}
        self.assertTrue(output_by_field["top_candidates"]["present"])
        self.assertFalse(output_by_field["watch_candidates"]["present"])
        self.assertNotIn("authorization", packet["candidates"][0])
        self.assertNotIn("api_key", packet["radar_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_scan_market"])
        self.assertTrue(packet["policy"]["candidate_is_not_buy_instruction"])
        self.assertTrue(packet["policy"]["provider_gaps_are_reported"])
        self.assertTrue(packet["policy"]["missing_provider_data_is_not_silently_dropped"])
        self.assertTrue(packet["policy"]["stale_inputs_are_research_only"])
        self.assertTrue(packet["policy"]["degraded_modes_are_visible"])
        self.assertTrue(packet["policy"]["full_pool_scan_requires_future_worker"])
        self.assertTrue(packet["policy"]["fast_scan_runtime_budget_contract_visible"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_candidate_radar_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_candidate_radar_large_cache_scan_reports_runtime_budget_without_hiding_gaps(self):
        large_candidates = [
            {
                "rank": index,
                "ticker": f"60{index:04d}.SH",
                "name": f"候选{index}",
                "score": index,
                "action_state": "只观察",
            }
            for index in range(1, 136)
        ]
        self._with_snapshot_cache(
            {
                "radar_packet": {"status": "ready", "summary": "大候选缓存"},
                "next_ticket_candidates": large_candidates,
                "a_share_capability_matrix": [
                    {"provider": "Tushare", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                ],
            }
        )

        packet = candidate_service.read_candidate_radar_cache()

        self.assertEqual(packet["coverage_detail_summary"]["candidate_input_count"], 135)
        self.assertEqual(packet["coverage_detail_summary"]["candidate_display_limit"], 120)
        self.assertEqual(packet["coverage_detail_summary"]["candidate_display_truncated_count"], 15)
        self.assertTrue(packet["coverage_detail_summary"]["candidate_rows_capped_for_ui"])
        self.assertEqual(len(packet["candidate_rows"]), 120)
        self.assertEqual(packet["scan_execution_summary"]["candidate_input_count"], 135)
        self.assertEqual(packet["scan_execution_summary"]["candidate_row_count"], 120)
        self.assertEqual(packet["scan_execution_summary"]["candidate_display_truncated_count"], 15)
        self.assertTrue(packet["scan_execution_summary"]["candidate_rows_capped_for_ui"])
        self.assertEqual(packet["counts"]["candidate_input_count"], 135)
        self.assertEqual(packet["counts"]["candidate_display_truncated_count"], 15)
        budget = packet["fast_scan_runtime_budget_contract"]
        self.assertEqual(budget["status"], "fast_scan_runtime_budget_ready")
        self.assertEqual(budget["candidate_input_count"], 135)
        self.assertEqual(budget["candidate_displayed_count"], 120)
        self.assertEqual(budget["candidate_display_truncated_count"], 15)
        self.assertFalse(budget["large_universe_worker_required"])
        budget_rows = {row["criterion"]: row for row in packet["fast_scan_runtime_budget_rows"]}
        self.assertEqual(budget_rows["sync_candidate_display_budget"]["status"], "capped_visible")
        self.assertEqual(budget_rows["feature_gap_visibility_budget"]["status"], "passed")
        result_delta = packet["result_delta_clarity_contract"]
        result_delta_rows = {row["criterion"]: row for row in packet["result_delta_clarity_rows"]}
        self.assertEqual(result_delta["candidate_display_truncated_count"], 15)
        self.assertIn("candidate_display_cap_visible", result_delta["visible_gaps"])
        self.assertEqual(result_delta_rows["candidate_display_cap_visible"]["status"], "capped_visible")
        self.assertFalse(result_delta["previous_cache_diff_done"])
        skipped_reasons = {row["reason"] for row in packet["skipped_reason_rows"]}
        self.assertIn("candidate_rows_display_capped", skipped_reasons)
        self.assertTrue(packet["policy"]["candidate_rows_capped_for_ui"])
        self.assertFalse(packet["policy"]["large_universe_requires_worker"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])

    def test_candidate_radar_quick_scan_task_persists_local_coverage_without_external_work(self):
        from storage.sqlite_meta import SQLiteMetaStore

        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "radar_packet": {
                    "status": "ready",
                    "summary": "Top3 候选缓存",
                    "api_key": "SHOULD_DROP",
                },
                "next_ticket_candidates": [
                    {
                        "rank": 1,
                        "ticker": "002837.SZ",
                        "name": "英维克",
                        "score": 47,
                        "action_state": "只观察",
                        "authorization": "Bearer SHOULD_DROP",
                    }
                ],
                "candidate_execution_evidence_overview": {"headline": "仍待验证"},
            }
        )

        task = candidate_service.run_candidate_quick_scan_task(
            {"scan_mode": "quick_cache_scan", "universe_mode": "cache_snapshot", "token": "SHOULD_DROP"}
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["task_type"], "run_candidate_radar_quick_scan")
        self.assertEqual(task["output_packet_key"], candidate_service.PACKET_KEY)
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertEqual(task["call_ledger"][0]["api"], "local_candidate_radar_quick_scan")
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["scan_mode"], "quick_cache_scan")
        self.assertFalse(task["call_ledger"][0]["request_params_safe"]["unsupported_scan_mode_fallback"])
        self.assert_local_ledger_boundary(task["call_ledger"][0])

        persisted = SQLiteMetaStore(candidate_service.SQLITE_META_PATH).read_packet(candidate_service.PACKET_KEY)
        self.assertEqual(persisted["packet_key"], candidate_service.PACKET_KEY)
        self.assertEqual(persisted["mode"], "quick_cache_scan")
        self.assertEqual(persisted["scan_mode"], "quick_cache_scan")
        self.assertEqual(persisted["scan_execution_summary"]["scan_family"], "quick_cache_scan")
        self.assertEqual(persisted["scan_execution_summary"]["requested_scan_mode"], "quick_cache_scan")
        self.assertTrue(persisted["scan_execution_summary"]["writes_sqlite_packet"])
        self.assertFalse(persisted["scan_execution_summary"]["cache_view_only"])
        persisted_acceptance = {row["check_key"]: row for row in persisted["scan_acceptance_rows"]}
        self.assertEqual(persisted_acceptance["scan_mode_contract"]["status"], "passed")
        self.assertEqual(persisted_acceptance["freshness_boundary"]["status"], "research_only_reported")
        self.assertEqual(persisted_acceptance["trade_action_boundary"]["status"], "passed")
        self.assertTrue(persisted["quick_scan_supported"])
        self.assertEqual(persisted["candidate_rows"][0]["ticker"], "002837.SZ")
        self.assertGreaterEqual(persisted["scan_coverage"]["mapped_signal_group_count"], 3)
        self.assertGreaterEqual(persisted["scan_coverage"]["missing_signal_group_count"], 1)
        self.assertEqual(persisted["legacy_parity_inventory"]["status"], "partial_parity")
        self.assertFalse(persisted["legacy_parity_inventory"]["quick_scan_is_full_replacement"])
        self.assertTrue(persisted["legacy_parity_inventory"]["deep_research_is_manual_only_future"])
        persisted_parity = {row["key"]: row for row in persisted["legacy_parity_rows"]}
        self.assertEqual(persisted_parity["manual_deep_research"]["migration_status"], "manual_only_future_task")
        self.assertIn("planned_future_task_read_plan_available", {row["status"] for row in persisted["scan_mode_status_rows"]})
        self.assertEqual(persisted["freshness_state"]["state"], "unknown")
        self.assertIn("data_freshness_missing", {row["reason"] for row in persisted["skipped_reason_rows"]})
        self.assertEqual(persisted["scan_coverage"]["freshness_state"], persisted["freshness_state"])
        self.assertTrue(persisted["policy"]["quick_scan_reads_cache_only"])
        self.assertTrue(persisted["policy"]["quick_scan_preserves_legacy_signal_groups"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertFalse(persisted["deepseek_called"])
        self.assertFalse(persisted["github_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(persisted, ensure_ascii=False))

        cache_view = candidate_service.read_candidate_radar_cache()
        self.assertEqual(cache_view["cache_source"], "sqlite_meta")
        self.assertEqual(cache_view["call_ledger"][0]["api"], "local_candidate_radar_cache")
        self.assertEqual(cache_view["call_ledger"][1]["api"], "local_candidate_radar_quick_scan")
        self.assertIn("GET /api/candidate-radar/cache", cache_view["warnings"][0])
        self.assertFalse(cache_view["external_calls_triggered"])

    def test_candidate_radar_quick_scan_computes_previous_cache_diff_when_available(self):
        from storage.sqlite_meta import SQLiteMetaStore

        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        SQLiteMetaStore(candidate_service.SQLITE_META_PATH).write_packet(
            candidate_service.PACKET_KEY,
            {
                "packet_key": candidate_service.PACKET_KEY,
                "schema_version": candidate_service.SCHEMA_VERSION,
                "mode": "quick_cache_scan",
                "cache_source": "quick_cache_scan_task",
                "scan_mode": "quick_cache_scan",
                "candidate_rows": [
                    {"rank": 1, "ticker": "002837.SZ", "name": "英维克", "score": 47, "action_state": "只观察"},
                    {"rank": 2, "ticker": "002008.SZ", "name": "大族激光", "score": 20, "action_state": "只观察"},
                ],
                "result_delta_clarity_contract": {"candidate_delta_signature": "previous-safe-signature"},
                "external_calls_triggered": False,
            },
        )
        self._with_snapshot_cache(
            {
                "radar_packet": {"status": "ready", "summary": "候选缓存"},
                "next_ticket_candidates": [
                    {"rank": 1, "ticker": "002008.SZ", "name": "大族激光", "score": 30, "action_state": "只观察"},
                    {"rank": 2, "ticker": "300750.SZ", "name": "宁德时代", "score": 60, "action_state": "待验证"},
                ],
            }
        )

        task = candidate_service.run_candidate_quick_scan_task({"scan_mode": "quick_cache_scan"})

        self.assertEqual(task["status"], "success")
        persisted = SQLiteMetaStore(candidate_service.SQLITE_META_PATH).read_packet(candidate_service.PACKET_KEY)
        result_delta = persisted["result_delta_clarity_contract"]
        result_delta_rows = {row["criterion"]: row for row in persisted["result_delta_clarity_rows"]}
        self.assertEqual(result_delta["status"], "result_delta_clarity_local_ready_browser_qa_pending")
        self.assertTrue(result_delta["previous_cache_available"])
        self.assertTrue(result_delta["previous_cache_diff_done"])
        self.assertEqual(result_delta["previous_candidate_count"], 2)
        self.assertEqual(result_delta["candidate_added_count"], 1)
        self.assertEqual(result_delta["candidate_removed_count"], 1)
        self.assertEqual(result_delta["candidate_rank_changed_count"], 1)
        self.assertEqual(result_delta["candidate_score_changed_count"], 1)
        self.assertEqual(result_delta["production_pending_count"], 1)
        self.assertEqual(result_delta_rows["previous_cache_diff_pending"]["status"], "completed_previous_cache_diff")
        self.assertEqual(result_delta_rows["browser_visual_delta_qa_pending"]["status"], "pending_visual_qa")
        self.assertIn("300750.SZ", result_delta["added_tickers"])
        self.assertIn("002837.SZ", result_delta["removed_tickers"])
        self.assertIn("002008.SZ", result_delta["rank_changed_tickers"])
        diff_by_type = {row["change_type"]: row for row in persisted["previous_cache_diff_rows"]}
        self.assertEqual(diff_by_type["added"]["ticker"], "300750.SZ")
        self.assertEqual(diff_by_type["removed"]["ticker"], "002837.SZ")
        self.assertEqual(diff_by_type["updated"]["ticker"], "002008.SZ")
        self.assertTrue(diff_by_type["updated"]["rank_changed"])
        self.assertTrue(diff_by_type["updated"]["score_changed"])
        self.assertEqual(persisted["counts"]["result_delta_added_count"], 1)
        self.assertEqual(persisted["counts"]["result_delta_removed_count"], 1)
        self.assertEqual(persisted["counts"]["result_delta_rank_changed_count"], 1)
        self.assertEqual(persisted["counts"]["result_delta_score_changed_count"], 1)
        self.assertTrue(persisted["policy"]["result_delta_clarity_previous_cache_diff_done"])
        self.assertTrue(persisted["policy"]["result_delta_clarity_previous_cache_diff_is_local"])
        self.assertFalse(persisted["policy"]["result_delta_clarity_is_not_previous_cache_diff"])
        self.assertTrue(persisted["policy"]["result_delta_clarity_is_not_browser_visual_qa"])
        self.assertFalse(result_delta["external_calls_triggered"])
        self.assertFalse(result_delta["tushare_called"])
        self.assertFalse(result_delta["deepseek_called"])
        self.assertFalse(result_delta["github_called"])
        self.assertTrue(result_delta["does_not_execute_trades"])
        self.assertTrue(result_delta["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(persisted, ensure_ascii=False))

    def test_candidate_radar_full_pool_plan_task_records_blockers_without_scan(self):
        from storage.sqlite_meta import SQLiteMetaStore

        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "a_share_capability_matrix": [
                    {"provider": "Tushare", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "api": "top_list", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "api": "cyq_chips", "capability_state": "stale_cache", "status": "使用缓存"},
                ],
                "data_freshness": {"state": "fresh", "expected_trade_date": "2026-06-12"},
            }
        )

        task = candidate_service.run_candidate_full_pool_plan_task(
            {"scan_mode": "full_pool_scan", "exclude_star": False, "token": "SHOULD_DROP"}
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["task_type"], "run_candidate_radar_full_pool_plan")
        self.assertEqual(task["current_step"], "candidate_radar_full_pool_plan_ready")
        self.assertEqual(task["call_ledger"][0]["api"], "local_candidate_radar_full_pool_plan")
        self.assertEqual(task["call_ledger"][0]["call_status"], "full_pool_plan_ready")
        self.assertTrue(task["call_ledger"][0]["request_params_safe"]["plan_only"])
        self.assertFalse(task["call_ledger"][0]["request_params_safe"]["full_pool_scan_done"])
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))

        persisted = SQLiteMetaStore(candidate_service.SQLITE_META_PATH).read_packet(candidate_service.PACKET_KEY)
        self.assertEqual(persisted["mode"], "full_pool_plan")
        self.assertEqual(persisted["scan_mode"], "full_pool_plan")
        plan = persisted["full_pool_scan_plan"]
        self.assertEqual(plan["schema_version"], "candidate_radar_full_pool_plan.v1")
        self.assertEqual(plan["status"], "full_pool_plan_ready")
        self.assertFalse(plan["full_pool_scan_done"])
        self.assertFalse(plan["full_pool_validation_done"])
        self.assertTrue(plan["worker_task_required"])
        self.assertTrue(plan["worker_task_consumption_plan_ready"])
        self.assertFalse(plan["page_render_starts_full_pool"])
        self.assertFalse(plan["cache_get_starts_full_pool"])
        self.assertFalse(plan["provider_refresh_executed"])
        self.assertFalse(plan["candidate_scoring_executed"])
        self.assertFalse(plan["candidate_packet_written_by_plan"])
        self.assertTrue(plan["research_only"])
        self.assertTrue(plan["candidate_is_not_buy_instruction"])
        self.assertFalse(plan["external_calls_triggered"])
        self.assertFalse(plan["tushare_called"])
        self.assertFalse(plan["deepseek_called"])
        self.assertFalse(plan["github_called"])
        self.assertEqual(plan["storage_datasets_required"], ["daily", "daily_basic", "moneyflow", "trade_cal"])
        self.assertEqual(persisted["scan_execution_summary"]["scan_family"], "full_pool_plan")
        self.assertTrue(persisted["scan_execution_summary"]["full_pool_plan_ready"])
        self.assertFalse(persisted["scan_execution_summary"]["full_pool_scan_done"])
        self.assertTrue(persisted["scan_execution_summary"]["writes_sqlite_packet"])
        plan_acceptance = {row["check_key"]: row for row in persisted["scan_acceptance_rows"]}
        self.assertEqual(plan_acceptance["full_pool_boundary"]["status"], "plan_only")
        self.assertEqual(plan_acceptance["provider_gap_visibility"]["status"], "gap_reported")
        self.assertEqual(plan_acceptance["trade_action_boundary"]["status"], "passed")
        filters = {row["filter_key"]: row for row in persisted["full_pool_plan_filter_rows"]}
        self.assertFalse(filters["exclude_star"]["enabled"])
        self.assertEqual(filters["exclude_star"]["source"], "payload")
        self.assertFalse(filters["exclude_star"]["applied_now"])
        signal_by_group = {row["signal_group"]: row for row in persisted["full_pool_required_signal_rows"]}
        self.assertTrue(signal_by_group["moneyflow"]["ready_for_full_pool"])
        self.assertFalse(signal_by_group["dragon_tiger"]["ready_for_full_pool"])
        self.assertFalse(signal_by_group["chip_radar"]["ready_for_full_pool"])
        blocker_keys = {row["blocker_key"] for row in persisted["full_pool_blocker_rows"]}
        self.assertIn("worker_required", blocker_keys)
        self.assertIn("provider_dragon_tiger", blocker_keys)
        self.assertIn("provider_chip_radar", blocker_keys)
        stage_by_name = {row["stage"]: row for row in persisted["full_pool_plan_stage_rows"]}
        self.assertFalse(stage_by_name["load_universe"]["executed_now"])
        self.assertFalse(stage_by_name["provider_refresh"]["external_calls_triggered"])
        self.assertTrue(persisted["policy"]["full_pool_plan_is_not_full_pool_scan"])
        self.assertTrue(persisted["policy"]["full_pool_plan_writes_no_candidates"])
        self.assertFalse(persisted["policy"]["full_pool_plan_provider_refresh_executed"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertFalse(persisted["deepseek_called"])
        self.assertFalse(persisted["github_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(persisted, ensure_ascii=False))

        cache_view = candidate_service.read_candidate_radar_cache()
        self.assertEqual(cache_view["cache_source"], "sqlite_meta")
        self.assertEqual(cache_view["full_pool_scan_plan"]["status"], "full_pool_plan_ready")
        self.assertEqual(cache_view["call_ledger"][1]["api"], "local_candidate_radar_full_pool_plan")

    def test_candidate_radar_deep_scan_plan_task_records_no_feature_loss_readiness_without_scan(self):
        from storage.sqlite_meta import SQLiteMetaStore

        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "radar_packet": {
                    "status": "ready",
                    "summary": "候选缓存",
                    "top_candidates": [
                        {
                            "rank": 1,
                            "ticker": "002837.SZ",
                            "name": "英维克",
                            "score": 47,
                            "action_state": "只观察",
                            "trigger_condition": "站稳 MA20",
                            "invalidation_condition": "跌破 MA20",
                        }
                    ],
                    "authorization": "Bearer SHOULD_DROP",
                },
                "candidate_execution_evidence_overview": {"headline": "仍待验证"},
                "a_share_capability_matrix": [
                    {"provider": "Tushare", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "api": "top_inst", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "api": "cyq_chips", "capability_state": "stale_cache", "status": "使用缓存"},
                ],
                "data_freshness": {"state": "fresh", "expected_trade_date": "2026-06-12"},
            }
        )

        task = candidate_service.run_candidate_deep_scan_plan_task(
            {"scan_mode": "deep_scan", "scan_depth": "legacy_parity_first", "token": "SHOULD_DROP"}
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["task_type"], "run_candidate_radar_deep_scan_plan")
        self.assertEqual(task["current_step"], "candidate_radar_deep_scan_plan_ready")
        self.assertEqual(task["call_ledger"][0]["api"], "local_candidate_radar_deep_scan_plan")
        self.assertEqual(task["call_ledger"][0]["call_status"], "deep_scan_plan_ready")
        self.assertTrue(task["call_ledger"][0]["request_params_safe"]["plan_only"])
        self.assertFalse(task["call_ledger"][0]["request_params_safe"]["deep_scan_done"])
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))

        persisted = SQLiteMetaStore(candidate_service.SQLITE_META_PATH).read_packet(candidate_service.PACKET_KEY)
        self.assertEqual(persisted["mode"], "deep_scan_plan")
        self.assertEqual(persisted["scan_mode"], "deep_scan_plan")
        plan = persisted["deep_scan_plan"]
        self.assertEqual(plan["schema_version"], "candidate_radar_deep_scan_plan.v1")
        self.assertEqual(plan["status"], "deep_scan_plan_ready")
        self.assertFalse(plan["deep_scan_done"])
        self.assertFalse(plan["deep_scan_validation_done"])
        self.assertTrue(plan["fast_path_ready"])
        self.assertFalse(plan["page_render_starts_deep_scan"])
        self.assertFalse(plan["cache_get_starts_deep_scan"])
        self.assertFalse(plan["provider_refresh_executed"])
        self.assertFalse(plan["candidate_scoring_executed"])
        self.assertFalse(plan["candidate_packet_written_by_plan"])
        self.assertTrue(plan["worker_task_required"])
        self.assertTrue(plan["worker_task_consumption_plan_ready"])
        self.assertTrue(plan["candidate_is_not_buy_instruction"])
        self.assertFalse(plan["external_calls_triggered"])
        self.assertFalse(plan["tushare_called"])
        self.assertFalse(plan["deepseek_called"])
        self.assertFalse(plan["github_called"])
        self.assertEqual(persisted["scan_execution_summary"]["scan_family"], "deep_scan_plan")
        self.assertTrue(persisted["scan_execution_summary"]["deep_scan_plan_ready"])
        self.assertFalse(persisted["scan_execution_summary"]["deep_scan_done"])
        self.assertTrue(persisted["scan_execution_summary"]["writes_sqlite_packet"])
        acceptance = {row["check_key"]: row for row in persisted["scan_acceptance_rows"]}
        self.assertEqual(acceptance["deep_scan_boundary"]["status"], "plan_only")
        self.assertIn(acceptance["feature_loss_boundary"]["status"], {"passed", "gap_reported"})
        signal_by_group = {row["signal_group"]: row for row in persisted["deep_scan_required_signal_rows"]}
        self.assertTrue(signal_by_group["moneyflow"]["ready_for_deep_scan"])
        self.assertFalse(signal_by_group["dragon_tiger"]["ready_for_deep_scan"])
        self.assertFalse(signal_by_group["chip_radar"]["ready_for_deep_scan"])
        stage_by_name = {row["stage"]: row for row in persisted["deep_scan_stage_rows"]}
        self.assertFalse(stage_by_name["async_worker_execution"]["executed_now"])
        self.assertTrue(stage_by_name["async_worker_execution"]["blocks_deep_scan"])
        blocker_keys = {row["blocker_key"] for row in persisted["deep_scan_blocker_rows"]}
        self.assertIn("stage_async_worker_execution", blocker_keys)
        self.assertIn("provider_dragon_tiger", blocker_keys)
        self.assertIn("provider_chip_radar", blocker_keys)
        self.assertTrue(persisted["policy"]["deep_scan_plan_is_not_deep_scan"])
        self.assertTrue(persisted["policy"]["deep_scan_plan_writes_no_new_candidates"])
        self.assertFalse(persisted["policy"]["deep_scan_plan_provider_refresh_executed"])
        self.assertFalse(persisted["policy"]["deep_scan_plan_deepseek_called"])
        self.assertTrue(persisted["policy"]["deep_scan_feature_loss_gaps_visible"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertFalse(persisted["deepseek_called"])
        self.assertFalse(persisted["github_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(persisted, ensure_ascii=False))

        cache_view = candidate_service.read_candidate_radar_cache()
        self.assertEqual(cache_view["cache_source"], "sqlite_meta")
        self.assertEqual(cache_view["deep_scan_plan"]["status"], "deep_scan_plan_ready")
        self.assertEqual(cache_view["call_ledger"][1]["api"], "local_candidate_radar_deep_scan_plan")

    def test_candidate_radar_quick_scan_task_fails_safe_when_packet_write_fails(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "radar_packet": {"status": "ready", "summary": "候选缓存"},
                "next_ticket_candidates": [{"rank": 1, "ticker": "002837.SZ", "name": "英维克"}],
            }
        )
        temp_dir = tempfile.TemporaryDirectory()
        original_candidate_path = candidate_service.SQLITE_META_PATH
        candidate_service.SQLITE_META_PATH = Path(temp_dir.name)
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, candidate_service, "SQLITE_META_PATH", original_candidate_path)

        task = candidate_service.run_candidate_quick_scan_task({"scan_mode": "quick_cache_scan"})

        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["current_step"], "candidate_radar_quick_scan_storage_write_failed")
        self.assertEqual(task["error_message_safe"], "candidate_radar_sqlite_write_failed")
        self.assertEqual(task["call_ledger"][0]["call_status"], "quick_scan_storage_write_failed")
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])

    def test_candidate_radar_custom_pool_scan_is_local_input_only_and_deduped(self):
        from storage.sqlite_meta import SQLiteMetaStore

        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache({"data_freshness": {"state": "fresh", "expected_trade_date": "2026-06-12"}})

        task = candidate_service.run_candidate_quick_scan_task(
            {
                "scan_mode": "custom_pool_scan",
                "custom_candidates": [
                    {"ticker": "002008.SZ", "name": "大族激光", "api_key": "SHOULD_DROP"},
                    {"ts_code": "002008.SZ", "name": "重复候选"},
                    {"code": "002837.SZ", "name": "禁用候选", "enabled": False},
                    {"name": "缺代码候选"},
                ],
            }
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["call_ledger"][0]["api"], "local_candidate_radar_custom_pool_scan")
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["scan_mode"], "custom_pool_scan")
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["input_candidate_count"], 4)
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["normalized_candidate_count"], 1)
        self.assert_local_ledger_boundary(task["call_ledger"][0])

        persisted = SQLiteMetaStore(candidate_service.SQLITE_META_PATH).read_packet(candidate_service.PACKET_KEY)
        self.assertEqual(persisted["mode"], "custom_pool_scan")
        self.assertEqual(persisted["scan_mode"], "custom_pool_scan")
        self.assertEqual(persisted["scan_execution_summary"]["scan_family"], "local_pool_scan")
        self.assertEqual(persisted["scan_execution_summary"]["local_pool_input_candidate_count"], 4)
        self.assertEqual(persisted["scan_execution_summary"]["local_pool_normalized_candidate_count"], 1)
        custom_acceptance = {row["check_key"]: row for row in persisted["scan_acceptance_rows"]}
        self.assertEqual(custom_acceptance["local_pool_boundary"]["status"], "input_reported")
        self.assertEqual(persisted["candidate_rows"][0]["ticker"], "002008.SZ")
        self.assertEqual(persisted["candidate_rows"][0]["action_state"], "只观察")
        self.assertEqual(persisted["local_candidate_pool_audit"]["input_source"], "payload.custom_candidates")
        self.assertEqual(persisted["local_candidate_pool_audit"]["normalized_candidate_count"], 1)
        self.assertEqual(persisted["local_candidate_pool_audit"]["duplicate_candidate_count"], 1)
        self.assertEqual(persisted["local_candidate_pool_audit"]["disabled_candidate_count"], 1)
        self.assertEqual(persisted["local_candidate_pool_audit"]["invalid_candidate_count"], 1)
        skipped_reasons = {row["reason"] for row in persisted["skipped_reason_rows"]}
        self.assertIn("local_pool_candidate_duplicate", skipped_reasons)
        self.assertIn("local_pool_candidate_disabled", skipped_reasons)
        self.assertIn("local_pool_candidate_missing_code", skipped_reasons)
        self.assertTrue(persisted["policy"]["custom_pool_scan_reads_local_input_only"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertFalse(persisted["deepseek_called"])
        self.assertFalse(persisted["github_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(persisted, ensure_ascii=False))

        cache_view = candidate_service.read_candidate_radar_cache()
        self.assertEqual(cache_view["cache_source"], "sqlite_meta")
        self.assertEqual(cache_view["scan_mode"], "custom_pool_scan")

    def test_candidate_radar_watchlist_scan_reads_snapshot_watchlist_only(self):
        from storage.sqlite_meta import SQLiteMetaStore

        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "announcement_watchlist": {
                    "updated_at": "2026-06-12T09:00:00",
                    "targets": [
                        {"ts_code": "002008.SZ", "name": "大族激光", "enabled": True},
                        {"ts_code": "002837.SZ", "name": "英维克", "enabled": False},
                    ],
                }
            }
        )

        task = candidate_service.run_candidate_quick_scan_task({"scan_mode": "watchlist_scan"})

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["call_ledger"][0]["api"], "local_candidate_radar_watchlist_scan")
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["candidate_pool_source"], "snapshot.announcement_watchlist.targets")
        self.assert_local_ledger_boundary(task["call_ledger"][0])

        persisted = SQLiteMetaStore(candidate_service.SQLITE_META_PATH).read_packet(candidate_service.PACKET_KEY)
        self.assertEqual(persisted["mode"], "watchlist_scan")
        self.assertEqual(persisted["scan_mode"], "watchlist_scan")
        self.assertEqual(persisted["scan_execution_summary"]["scan_family"], "local_pool_scan")
        self.assertEqual(persisted["scan_execution_summary"]["universe_mode"], "local_watchlist")
        self.assertEqual(persisted["candidate_rows"][0]["ticker"], "002008.SZ")
        self.assertEqual(persisted["local_candidate_pool_audit"]["input_candidate_count"], 2)
        self.assertEqual(persisted["local_candidate_pool_audit"]["normalized_candidate_count"], 1)
        self.assertEqual(persisted["local_candidate_pool_audit"]["disabled_candidate_count"], 1)
        self.assertIn("local_pool_candidate_disabled", {row["reason"] for row in persisted["skipped_reason_rows"]})
        self.assertTrue(persisted["policy"]["watchlist_scan_reads_local_input_only"])
        self.assertTrue(persisted["policy"]["does_not_scan_market"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertFalse(persisted["deepseek_called"])
        self.assertFalse(persisted["github_called"])

    def test_risk_guardrails_cache_reads_local_risk_fields_without_external_work(self):
        self._with_snapshot_cache(
            {
                "risk_alerts": {
                    "recovery_priority_summary": "先补齐数据缺口，再看执行护栏。",
                    "data_gaps": ["资金流缺口", {"label": "硬风险公告", "status": "missing", "api_key": "SHOULD_DROP"}],
                    "must_not_do": ["不要追高", {"guardrail": "不越过安全线", "authorization": "Bearer SHOULD_DROP"}],
                    "reduce_conditions": ["跌破安全线降风险"],
                    "hard_risk_alerts": [{"label": "减持公告待核验", "status": "pending"}],
                    "token": "SHOULD_DROP",
                },
                "safety_line": "安全线 100 元",
                "execution_guardrail_overview": {"blocked_count": 2, "headline": "执行被阻断"},
                "legacy_decision_chain_summary": {"blocked_count": 1, "waiting_count": 3, "items": [{"label": "旧链待恢复"}]},
                "strategy_prerequisite_recovery_ledger": {"blocked_count": 1, "items": [{"label": "先补证"}]},
                "position_risk_budget": {"risk_level": "中", "allow_add": False},
                "risk_breakdown": {"items": [{"label": "数据风险", "level": "高"}], "authorization": "Bearer SHOULD_DROP"},
            }
        )

        packet = risk_service.read_risk_guardrails_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_risk_guardrails_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertIn("risk_alerts", packet["source_packet_keys"])
        self.assertEqual(packet["counts"]["data_gap_count"], 2)
        self.assertEqual(packet["counts"]["must_not_do_count"], 2)
        self.assertEqual(packet["counts"]["reduce_condition_count"], 1)
        self.assertEqual(packet["counts"]["hard_risk_alert_count"], 1)
        self.assertEqual(packet["counts"]["execution_blocked_count"], 2)
        self.assertEqual(packet["must_not_do_rows"][0]["guardrail"], "不要追高")
        self.assertEqual(packet["data_gap_rows"][1]["label"], "硬风险公告")
        self.assertEqual(packet["risk_rows"][0]["label"], "数据风险")
        self.assertNotIn("token", packet["risk_alerts"])
        self.assertNotIn("authorization", packet["risk_breakdown"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_clear_risk_flags"])
        self.assertTrue(packet["policy"]["risk_guardrails_are_not_trade_orders"])
        self.assertTrue(packet["policy"]["trade_isolation_audit_is_read_only"])
        self.assertTrue(packet["policy"]["future_trade_integration_requires_separate_approved_design"])
        trade_audit = packet["trade_isolation_audit"]
        self.assertEqual(trade_audit["schema_version"], "command_center_3_trade_isolation_audit.v1")
        self.assertEqual(trade_audit["status"], "trade_isolation_ready")
        self.assertEqual(trade_audit["scope"], "command_center_3_cache_task_frontend_contract")
        self.assertEqual(trade_audit["known_post_route_count"], task_service.build_task_catalog()["route_coverage"]["known_post_route_count"])
        self.assertEqual(trade_audit["blocking_criterion_count"], 0)
        self.assertTrue(trade_audit["no_automatic_order_path_in_task_catalog"])
        self.assertTrue(trade_audit["research_paths_cannot_mutate_strategy_action"])
        self.assertTrue(trade_audit["frontend_surfaces_are_display_only_for_trade_boundaries"])
        self.assertTrue(trade_audit["future_trade_integration_out_of_roadmap"])
        self.assertFalse(trade_audit["external_calls_triggered"])
        self.assertTrue(trade_audit["does_not_execute_trades"])
        self.assertTrue(trade_audit["does_not_modify_strategy_action"])
        trade_criteria = {row["criterion"] for row in packet["trade_isolation_rows"]}
        self.assertIn("task_catalog_all_routes_no_trade", trade_criteria)
        self.assertIn("task_catalog_all_routes_no_strategy_action_mutation", trade_criteria)
        self.assertIn("all_known_post_routes_button_gated", trade_criteria)
        self.assertIn("call_ledger_required_for_all_known_post_routes", trade_criteria)
        self.assertIn("frontend_boundaries_visible", trade_criteria)
        self.assertIn("future_trading_requires_separate_approved_design", trade_criteria)
        self.assertEqual(packet["counts"]["trade_isolation_blocker_count"], 0)
        self.assertEqual(packet["counts"]["trade_boundary_frontend_surface_count"], 3)
        self.assertGreaterEqual(packet["counts"]["task_trade_boundary_row_count"], 18)
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_risk_guardrails_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_a_share_evidence_cache_builds_lineage_without_external_calls(self):
        self._with_snapshot_cache(
            {
                "moneyflow_packet": {
                    "status": "ready",
                    "trade_date": "20260610",
                    "updated_at": "2026-06-10T09:30:00",
                    "flow_state": "主力净流入",
                    "main_net_yi": 1.2,
                    "api_key": "SHOULD_DROP",
                },
                "a_share_fact_lineage_summary": {
                    "schema_version": "a_share_fact_lineage_summary.v1",
                    "summary": "已验证 1｜阻断 0｜缓存 0｜过期 0｜缺失 0｜待验证 0",
                    "items": [{"fact_key": "moneyflow", "status_label": "已验证", "enters_core_action": False}],
                    "counts": {"verified": 1, "blocked": 0, "missing": 0, "cached": 0},
                },
            }
        )

        packet = evidence_service.read_a_share_evidence_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_a_share_evidence_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["mode"], "cache_only")
        self.assertEqual(packet["fact_lineage"]["schema_version"], "a_share_fact_lineage_summary.v1")
        self.assertEqual(packet["counts"]["lineage_verified"], 1)
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertFalse(packet["policy"]["lineage_enters_core_action"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_a_share_evidence_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_data_capability_cache_reads_local_capability_without_provider_ping(self):
        self._with_snapshot_cache(
            {
                "data_capability": {
                    "source": "Unified data capability",
                    "items": [
                        {
                            "provider": "Tushare",
                            "api": "moneyflow",
                            "label": "个股资金流",
                            "capability_state": "available",
                            "status": "可用",
                            "latest_date": "20260610",
                            "api_key": "SHOULD_DROP",
                        },
                        {
                            "provider": "Supabase",
                            "api": "brain_memory",
                            "label": "brain_memory",
                            "capability_state": "not_configured",
                            "status": "未配置",
                        },
                    ],
                }
            }
        )

        packet = data_capability_service.read_data_capability_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_data_capability_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertGreaterEqual(packet["counts"]["available"], 1)
        self.assertGreaterEqual(packet["counts"]["restricted"], 1)
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_ping_tushare"])
        self.assertTrue(packet["policy"]["does_not_ping_supabase"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_data_capability_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_data_health_timeline_cache_reads_provider_diagnostics_without_ping(self):
        self._with_snapshot_cache(
            {
                "data_health_timeline": [
                    {"event": "moneyflow stale", "provider": "Tushare", "error": "Traceback token=SHOULD_DROP"},
                    {"event": "cyq recovered", "provider": "Tushare"},
                ],
                "provider_data_capability_cockpit": {
                    "providers": [
                        {"provider": "Tushare", "status": "partial", "api_key": "SHOULD_DROP"},
                        {"provider": "Supabase", "status": "not_configured"},
                    ]
                },
                "a_share_capability_matrix": [
                    {"provider": "Tushare", "api": "daily_basic", "capability_state": "available"},
                    {"provider": "AkShare", "api": "spot", "capability_state": "pending"},
                ],
                "data_health_ledger": {"rows": [{"provider": "Tushare", "api": "moneyflow", "status": "stale"}]},
                "data_gap_report": {"items": [{"label": "moneyflow missing", "authorization": "Bearer SHOULD_DROP"}]},
                "data_health_timeline_recovery_actions": [{"label": "刷新 moneyflow", "status": "manual"}],
                "data_health_visibility_summary": {"summary": "资金流过期，等待手动恢复。"},
            }
        )

        packet = data_health_service.read_data_health_timeline_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_data_health_timeline_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["counts"]["timeline_count"], 2)
        self.assertEqual(packet["counts"]["provider_count"], 2)
        self.assertEqual(packet["counts"]["capability_count"], 2)
        self.assertEqual(packet["counts"]["ledger_count"], 1)
        self.assertEqual(packet["counts"]["gap_count"], 1)
        self.assertEqual(packet["counts"]["recovery_action_count"], 1)
        self.assertEqual(packet["timeline_rows"][0]["event"], "moneyflow stale")
        self.assertEqual(packet["provider_rows"][0]["provider"], "Tushare")
        self.assertEqual(packet["capability_rows"][0]["api"], "daily_basic")
        self.assertNotIn("api_key", packet["provider_rows"][0])
        self.assertNotIn("authorization", packet["gap_rows"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_ping_tushare"])
        self.assertTrue(packet["policy"]["does_not_ping_supabase"])
        self.assertTrue(packet["policy"]["does_not_refresh_data"])
        self.assertTrue(packet["policy"]["post_task_required_for_provider_probe"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["akshare_called"])
        self.assertFalse(packet["yfinance_called"])
        self.assertFalse(packet["supabase_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_data_health_timeline_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_recovery_center_cache_reads_local_recovery_actions_without_running_them(self):
        self._with_snapshot_cache(
            {
                "data_recovery_center": {"summary": "先恢复资金流，再恢复硬风险。", "token": "SHOULD_DROP"},
                "data_recovery_actions": [
                    {"label": "刷新资金流", "api": "moneyflow", "status": "manual", "api_key": "SHOULD_DROP"},
                    "补齐龙虎榜",
                ],
                "tool_recovery_actions": [{"label": "打开旧工具", "status": "manual"}],
                "recovery_result_timeline": [{"event": "恢复失败", "error": "Traceback token=SHOULD_DROP"}],
                "data_health_timeline_recovery_actions": [{"label": "恢复 data_health", "status": "pending"}],
                "a_share_evidence_recovery_ledger": {"items": [{"label": "补证据雷达"}]},
                "provider_recovery_matrix": {"items": [{"provider": "Tushare", "api": "daily_basic"}]},
                "data_gap_report": {"items": [{"label": "moneyflow missing"}]},
                "recovery_result_status_strip": {"summary": "仍需手动恢复", "next_action": "点击按钮任务"},
                "old_workspace_data_absence_ledger": {"summary": "旧工作台缺口"},
            }
        )

        packet = recovery_service.read_recovery_center_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_recovery_center_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["counts"]["data_recovery_action_count"], 2)
        self.assertEqual(packet["counts"]["tool_recovery_action_count"], 1)
        self.assertEqual(packet["counts"]["evidence_recovery_count"], 1)
        self.assertEqual(packet["counts"]["provider_recovery_count"], 1)
        self.assertEqual(packet["counts"]["data_gap_count"], 1)
        self.assertEqual(packet["action_rows"][0]["label"], "刷新资金流")
        self.assertEqual(packet["action_rows"][1]["label"], "补齐龙虎榜")
        self.assertNotIn("api_key", packet["action_rows"][0])
        self.assertNotIn("token", packet["data_recovery_center"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_run_recovery_actions"])
        self.assertTrue(packet["policy"]["recovery_actions_are_manual_guidance"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_recovery_center_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_factor_value_rows_keep_safe_scalar_contract(self):
        rows = storage_service._factor_value_rows_from_hub(
            {
                "packet_key": "command_center_factor_quant_hub_packet",
                "mode": "light",
                "cache_source": "local_factor_light_pipeline",
                "runtime": {
                    "trade_date": "20260610",
                    "calculated_at": "2026-06-10T09:30:00",
                    "factor_values": [
                        {
                            "factor_key": "momentum_20d",
                            "factor_name": "20日动量",
                            "raw_value": {"not": "scalar"},
                            "zscore": [1, 2],
                            "rank_pct": 0.7,
                            "direction": "support",
                            "data_status": "ready",
                            "status_note": "Traceback token=SHOULD_DROP",
                            "pit_validated": True,
                        }
                    ],
                },
                "universe": {"items": ["002008.SZ"]},
            }
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["ts_code"], "002008.SZ")
        self.assertEqual(row["trade_date"], "20260610")
        self.assertEqual(row["factor_key"], "momentum_20d")
        self.assertEqual(row["data_status"], "ready")
        self.assertEqual(row["rank_pct"], 0.7)
        self.assertIsNone(row["raw_value"])
        self.assertIsNone(row["zscore"])
        self.assertIsNone(row["status_note"])
        self.assertEqual(row["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertEqual(row["source_packet"], "runtime.factor_values")
        self.assertEqual(row["source"], "local_factor_light_pipeline")
        self.assertNotIn("SHOULD_DROP", json.dumps(row, ensure_ascii=False))

        validation = storage_service._schema_validation_for_rows("factor_values", rows)
        self.assertEqual(validation["status"], "valid")
        self.assertEqual(validation["schema_version"], "storage.factor_values.v1")
        self.assertFalse(validation["blocks_write"])
        self.assertFalse(validation["external_calls_triggered"])

    def test_persist_factor_values_blocks_schema_invalid_rows(self):
        original_rows_from_hub = storage_service._factor_value_rows_from_hub
        storage_service._factor_value_rows_from_hub = lambda _hub: [{"factor_key": "momentum_20d"}]
        self.addCleanup(setattr, storage_service, "_factor_value_rows_from_hub", original_rows_from_hub)

        result = storage_service.persist_factor_values_from_hub({"runtime": {"factor_values": [{"factor_key": "momentum_20d"}]}})

        self.assertEqual(result["status"], "schema_invalid")
        self.assertEqual(result["schema_version"], "storage.factor_values.v1")
        self.assertEqual(result["schema_validation_status"], "missing_required_columns")
        self.assertIn("ts_code", result["schema_validation"]["missing_required_columns"])
        self.assertIn("trade_date", result["schema_validation"]["missing_required_columns"])
        self.assertEqual(result["row_count"], 0)
        self.assertFalse(result["external_calls_triggered"])
        self.assertTrue(result["does_not_modify_strategy_action"])

    def test_persist_factor_values_failed_write_returns_safe_status(self):
        self._with_parquet_root()
        original_dependency_status = storage_service.parquet_store.dependency_status
        original_write_dataset = storage_service.parquet_store.write_dataset

        storage_service.parquet_store.dependency_status = lambda: {"available": True, "error_message_safe": ""}

        def fail_write(*args, **kwargs):
            raise RuntimeError('Traceback File "x.py" token=SHOULD_DROP')

        storage_service.parquet_store.write_dataset = fail_write
        self.addCleanup(setattr, storage_service.parquet_store, "dependency_status", original_dependency_status)
        self.addCleanup(setattr, storage_service.parquet_store, "write_dataset", original_write_dataset)

        result = storage_service.persist_factor_values_from_hub(
            {
                "runtime": {
                    "factor_values": [
                        {"factor_key": "momentum_20d", "raw_value": 1.2, "data_status": "ready"},
                    ]
                },
                "universe": {"items": ["002008.SZ"]},
            }
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["dataset"], "factor_values")
        self.assertEqual(result["row_count"], 0)
        self.assertEqual(result["error_message_safe"], "local parquet factor_values write failed")
        self.assertFalse(result["external_calls_triggered"])
        self.assertTrue(result["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(result, ensure_ascii=False))

    def test_task_stub_records_safe_status_without_external_work(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        task = create_task_stub(
            "refresh_factor_data",
            payload={"ts_code": "002008.SZ", "token": "SHOULD_NOT_KEEP", "nested": {"api_key": "DROP", "keep": "ok"}},
        )

        self.assertTrue(task["task_id"].startswith("local-"))
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["progress"], 1.0)
        self.assertEqual(task["current_step"], "stub_created_no_external_call")
        self.assertEqual([item["status"] for item in task["status_history"]], ["pending", "running", "success"])
        self.assertEqual(task["call_ledger"][0]["call_status"], "stub_not_called")
        self.assertEqual(task["backend"], "local_fallback")
        self.assertNotIn("token", task["payload_safe"])
        self.assertEqual(task["payload_safe"]["nested"], {"keep": "ok"})
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertEqual(read_task_status(task["task_id"])["task_id"], task["task_id"])
        task_service._TASKS.clear()
        persisted = read_task_status(task["task_id"])
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["task_id"], task["task_id"])
        self.assertEqual(task_service.list_task_statuses()[0]["task_id"], task["task_id"])

        index = task_service.build_task_status_index()
        self.assertEqual(index["packet_key"], "command_center_3_task_status_index")
        self.assertEqual(index["mode"], "cache_only")
        self.assertEqual(index["task_count"], 1)
        self.assertEqual(index["status_counts"]["success"], 1)
        self.assertEqual(index["latest_task_id"], task["task_id"])
        self.assertEqual(index["call_ledger_count"], 1)
        self.assertTrue(index["policy"]["get_tasks_cache_only"])
        self.assertTrue(index["policy"]["does_not_create_tasks"])
        self.assertFalse(index["external_calls_triggered"])
        self.assertFalse(index["tushare_called"])
        self.assertFalse(index["deepseek_called"])
        self.assertFalse(index["github_called"])
        self.assertTrue(index["does_not_execute_trades"])
        self.assertTrue(index["does_not_modify_strategy_action"])
        self.assertEqual(index["call_ledger"][0]["api"], "local_task_status_index")

    def test_tushare_refresh_task_records_call_ledger_and_local_parquet(self):
        db_path = self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        class FakeTushareAdapter:
            def get_daily(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "trade_date": "20260610", "close": 10.4}], "error": ""}

            def get_daily_basic(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "trade_date": "20260610", "turnover_rate": 3.2}], "error": ""}

            def get_moneyflow(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "trade_date": "20260610", "net_mf_amount": 1200}], "error": ""}

        task = tushare_task_service.run_tushare_refresh_task(
            {"ts_code": "002008.SZ", "apis": ["daily", "daily_basic", "moneyflow"], "token": "SHOULD_DROP"},
            adapter=FakeTushareAdapter(),
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "tushare_refresh_completed")
        self.assertEqual(task["backend"], "local_fallback")
        self.assertTrue(task["external_calls_triggered"])
        self.assertTrue(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("token", task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))
        self.assertEqual([row["api"] for row in task["call_ledger"]], ["daily", "daily_basic", "moneyflow"])
        for row in task["call_ledger"]:
            self.assertTrue(row["external"])
            self.assertTrue(row["external_calls_triggered"])
            self.assertTrue(row["tushare_called"])
            self.assertFalse(row["deepseek_called"])
            self.assertFalse(row["github_called"])
            self.assertTrue(row["does_not_execute_trades"])
            self.assertTrue(row["does_not_modify_strategy_action"])
            self.assertEqual(row["call_status"], "success")
            self.assertEqual(row["row_count"], 1)
            self.assertEqual(row["data_date"], "20260610")
            self.assertNotIn("token", row["request_params_safe"])

        parquet_status = {row["api"]: row["parquet_status"] for row in task["call_ledger"]}
        self.assertEqual(set(parquet_status), {"daily", "daily_basic", "moneyflow"})
        self.assertTrue(all(status in {"written", "dependency_missing"} for status in parquet_status.values()))

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["status"], "success")
        self.assertEqual(persisted["success_count"], 3)
        self.assertEqual(persisted["failed_count"], 0)
        self.assertTrue(persisted["tushare_called"])
        self.assertTrue(persisted["does_not_modify_strategy_action"])
        self.assertIn("api_validation_rows", persisted)
        self.assertEqual(persisted["api_validation_summary"]["selected_api_count"], 3)
        self.assertEqual(persisted["api_validation_summary"]["validated_success_count"], 3)
        self.assertEqual(persisted["api_validation_summary"]["calendar_api_count"], 1)
        self.assertEqual(persisted["api_groups"]["calendar"], ["trade_cal"])
        validation_by_api = {row["api"]: row for row in persisted["api_validation_rows"]}
        self.assertEqual(validation_by_api["daily"]["validation_status"], "validated_success")
        self.assertEqual(validation_by_api["daily"]["validation_scope"], "task_call_result")
        self.assertEqual(validation_by_api["daily"]["group"], "core")
        self.assertTrue(validation_by_api["daily"]["parquet_enabled"])
        self.assertEqual(validation_by_api["trade_cal"]["validation_status"], "not_requested")
        self.assertEqual(validation_by_api["trade_cal"]["validation_scope"], "capability_matrix_only")
        self.assertEqual(validation_by_api["trade_cal"]["group"], "calendar")
        self.assertTrue(validation_by_api["trade_cal"]["parquet_enabled"])
        self.assertFalse(validation_by_api["limit_list_d"]["selected"])
        self.assertTrue(persisted["api_validation_summary"]["does_not_claim_unselected_apis_verified"])
        self.assertIn("trade_cal", persisted["api_validation_matrix_policy"]["matrix_only_apis"])
        self.assertIn("target_readiness_scope", persisted["api_validation_matrix_policy"])
        self.assertIn("acceptance_audit_scope", persisted["api_validation_matrix_policy"])
        self.assertIn("api_acceptance_audit", persisted)
        audit = persisted["api_acceptance_audit"]
        self.assertEqual(audit["schema_version"], "tushare_api_acceptance_audit.v1")
        self.assertEqual(audit["status"], "acceptance_audit_passed")
        self.assertEqual(audit["scope"], "local_call_ledger_semantic_audit_not_provider_call")
        self.assertEqual(audit["selected_api_count"], 3)
        self.assertEqual(audit["called_api_count"], 3)
        self.assertGreater(audit["matrix_only_api_count"], 0)
        self.assertEqual(audit["acceptance_issue_count"], 0)
        self.assertEqual(audit["false_verified_count"], 0)
        self.assertEqual(audit["required_field_gap_count"], 0)
        self.assertEqual(audit["unsafe_request_param_count"], 0)
        self.assertEqual(audit["unsafe_error_message_count"], 0)
        self.assertEqual(audit["false_parquet_write_claim_count"], 0)
        self.assertTrue(audit["selected_interfaces_have_call_ledger"])
        self.assertTrue(audit["does_not_claim_unselected_apis_verified"])
        self.assertTrue(audit["safe_request_params"])
        self.assertTrue(audit["safe_errors_redacted"])
        self.assertFalse(audit["full_interface_acceptance_done"])
        self.assertTrue(audit["provider_validation_done_in_this_task"])
        self.assertFalse(audit["audit_external_calls_triggered"])
        self.assertFalse(audit["audit_calls_tushare"])
        self.assertTrue(persisted["api_acceptance_audit_passed"])
        self.assertEqual(persisted["api_acceptance_issue_count"], 0)
        self.assertFalse(persisted["full_interface_acceptance_done"])
        acceptance_by_api = {row["api"]: row for row in persisted["api_acceptance_audit_rows"]}
        self.assertEqual(acceptance_by_api["daily"]["acceptance_status"], "passed")
        self.assertTrue(acceptance_by_api["daily"]["safe_success_state_visible"])
        self.assertTrue(acceptance_by_api["trade_cal"]["matrix_only_not_verified"])
        self.assertFalse(acceptance_by_api["trade_cal"]["unselected_false_verified"])
        target_by_key = {row["target"]: row for row in persisted["api_validation_target_rows"]}
        self.assertEqual(target_by_key["trade_calendar"]["readiness"], "matrix_only")
        self.assertEqual(target_by_key["margin_financing"]["readiness"], "matrix_only")
        self.assertTrue(target_by_key["trade_calendar"]["does_not_claim_unselected_apis_verified"])
        self.assertEqual(persisted["api_validation_target_summary"]["matrix_only_target_count"], 7)
        self.assertEqual(persisted["api_validation_target_summary"]["validated_target_count"], 0)
        self.assertEqual(persisted["api_validation_matrix_policy"]["call_ledger_required_fields"][0], "api")
        sample_plan = persisted["provider_target_sample_plan_contract"]
        sample_plan_rows = {row["target"]: row for row in persisted["provider_target_sample_plan_rows"]}
        self.assertEqual(sample_plan["schema_version"], "tushare_provider_target_sample_plan_contract.v1")
        self.assertEqual(sample_plan["status"], "local_plan_ready_provider_execution_pending")
        self.assertEqual(sample_plan["scope"], "local_target_sample_plan_not_provider_call")
        self.assertEqual(sample_plan["target_count"], 7)
        self.assertEqual(sample_plan["ready_to_execute_target_count"], 0)
        self.assertEqual(sample_plan["pending_or_blocked_target_count"], 7)
        self.assertFalse(sample_plan["provider_backed_acceptance_done"])
        self.assertFalse(sample_plan["production_tushare_pipeline_complete"])
        self.assertFalse(sample_plan["plan_external_calls_triggered"])
        self.assertFalse(sample_plan["tushare_called_by_plan"])
        self.assertEqual(sample_plan_rows["trade_calendar"]["provider_sample_plan_status"], "matrix_only_plan_pending")
        self.assertIn("start_date", sample_plan_rows["trade_calendar"]["required_context_groups"])
        self.assertIn("open_and_closed_calendar_rows", sample_plan_rows["trade_calendar"]["required_success_evidence"])
        self.assertIn("provider_target_sample_plan_scope", persisted["api_validation_matrix_policy"])

    def test_tushare_refresh_task_validates_trade_calendar_and_extended_apis_without_false_parquet_claims(self):
        db_path = self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        class ExtendedFakeTushareAdapter:
            def get_trade_cal(self, **params):
                return {"ok": True, "data": [{"cal_date": "20260610", "is_open": 1}], "error": ""}

            def get_margin_detail(self, **params):
                return {"ok": True, "data": [], "error": ""}

            def get_top_list(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "trade_date": "20260610", "amount": 1000}], "error": ""}

            def get_top_inst(self, **params):
                return {"ok": True, "data": [], "error": ""}

            def get_stk_limit(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "trade_date": "20260610", "up_limit": 11.44}], "error": ""}

            def get_limit_list_d(self, **params):
                return {"ok": True, "data": [], "error": ""}

            def get_limit_cpt_list(self, **params):
                return {"ok": False, "data": None, "error": "Traceback token=SHOULD_DROP"}

            def get_fina_indicator(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "ann_date": "20260430", "roe": 8.2}], "error": ""}

            def get_stk_surv(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "trade_date": "20260610", "status": "L"}], "error": ""}

        task = tushare_task_service.run_tushare_refresh_task(
            {
                "ts_code": "002008.SZ",
                "start_date": "20260601",
                "end_date": "20260610",
                "apis": ["trade_cal", "margin_detail", "top_list", "top_inst", "stk_limit", "limit_list_d", "limit_cpt_list", "fina_indicator", "stk_surv"],
                "api_key": "SHOULD_DROP",
            },
            adapter=ExtendedFakeTushareAdapter(),
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "tushare_refresh_partial_safe")
        self.assertTrue(task["external_calls_triggered"])
        self.assertTrue(task["tushare_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))

        ledger_by_api = {row["api"]: row for row in task["call_ledger"]}
        self.assertEqual(ledger_by_api["trade_cal"]["call_status"], "success")
        self.assertEqual(ledger_by_api["trade_cal"]["data_date"], "20260610")
        self.assertIn(ledger_by_api["trade_cal"]["parquet_status"], {"written", "dependency_missing"})
        self.assertEqual(ledger_by_api["margin_detail"]["call_status"], "empty")
        self.assertEqual(ledger_by_api["margin_detail"]["parquet_status"], "not_enabled")
        self.assertEqual(ledger_by_api["top_list"]["call_status"], "success")
        self.assertEqual(ledger_by_api["top_list"]["parquet_status"], "not_enabled")
        self.assertEqual(ledger_by_api["top_inst"]["call_status"], "empty")
        self.assertEqual(ledger_by_api["stk_limit"]["call_status"], "success")
        self.assertEqual(ledger_by_api["limit_list_d"]["call_status"], "empty")
        self.assertEqual(ledger_by_api["fina_indicator"]["call_status"], "success")
        self.assertEqual(ledger_by_api["fina_indicator"]["data_date"], "20260430")
        self.assertEqual(ledger_by_api["stk_surv"]["call_status"], "success")
        self.assertEqual(ledger_by_api["limit_cpt_list"]["call_status"], "failed")
        self.assertEqual(ledger_by_api["limit_cpt_list"]["failure_mode"], "provider_error_safe")
        self.assertEqual(ledger_by_api["limit_cpt_list"]["failure_mode_status"], "validated_failed_safe")
        self.assertTrue(ledger_by_api["limit_cpt_list"]["safe_failure_mode_visible"])
        self.assertEqual(ledger_by_api["limit_cpt_list"]["error_message_safe"], "tushare_error_redacted_safe")

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["status"], "success")
        self.assertEqual(persisted["success_count"], 8)
        self.assertEqual(persisted["failed_count"], 1)
        self.assertEqual(persisted["api_validation_summary"]["selected_api_count"], 9)
        self.assertEqual(persisted["api_validation_summary"]["validated_success_count"], 5)
        self.assertEqual(persisted["api_validation_summary"]["validated_empty_count"], 3)
        self.assertEqual(persisted["api_validation_summary"]["validated_failed_count"], 1)
        self.assertEqual(persisted["api_groups"]["margin"], ["margin_detail"])
        self.assertEqual(persisted["api_groups"]["dragon_tiger"], ["top_list", "top_inst"])
        self.assertEqual(persisted["api_groups"]["limit_emotion"], ["stk_limit", "limit_list_d", "limit_cpt_list"])
        self.assertEqual(persisted["api_groups"]["financial_disclosure"], ["forecast", "fina_indicator"])
        validation_by_api = {row["api"]: row for row in persisted["api_validation_rows"]}
        self.assertEqual(validation_by_api["trade_cal"]["group"], "calendar")
        self.assertEqual(validation_by_api["trade_cal"]["validation_status"], "validated_success")
        self.assertEqual(validation_by_api["trade_cal"]["validation_scope"], "task_call_result")
        self.assertTrue(validation_by_api["trade_cal"]["parquet_enabled"])
        self.assertEqual(validation_by_api["margin_detail"]["group"], "extended")
        self.assertEqual(validation_by_api["margin_detail"]["validation_status"], "validated_empty")
        self.assertEqual(validation_by_api["margin_detail"]["validation_scope"], "task_call_result")
        self.assertFalse(validation_by_api["margin_detail"]["parquet_enabled"])
        self.assertEqual(validation_by_api["top_list"]["group"], "extended")
        self.assertEqual(validation_by_api["top_list"]["validation_status"], "validated_success")
        self.assertEqual(validation_by_api["top_inst"]["validation_status"], "validated_empty")
        self.assertEqual(validation_by_api["stk_limit"]["domain"], "limit_emotion")
        self.assertEqual(validation_by_api["stk_limit"]["validation_status"], "validated_success")
        self.assertEqual(validation_by_api["limit_list_d"]["validation_status"], "validated_empty")
        self.assertEqual(validation_by_api["fina_indicator"]["validation_status"], "validated_success")
        self.assertEqual(validation_by_api["stk_surv"]["validation_status"], "validated_success")
        self.assertEqual(validation_by_api["limit_cpt_list"]["validation_status"], "validated_failed")
        self.assertEqual(validation_by_api["limit_cpt_list"]["validation_scope"], "task_call_result")
        self.assertEqual(validation_by_api["daily"]["validation_status"], "not_requested")
        self.assertEqual(validation_by_api["daily"]["validation_scope"], "capability_matrix_only")
        self.assertEqual(persisted["api_validation_summary"]["selected_margin_api_count"], 1)
        self.assertEqual(persisted["api_validation_summary"]["selected_dragon_tiger_api_count"], 2)
        self.assertEqual(persisted["api_validation_summary"]["selected_limit_emotion_api_count"], 3)
        self.assertEqual(persisted["api_validation_summary"]["selected_financial_disclosure_api_count"], 1)
        self.assertEqual(persisted["api_validation_summary"]["validated_margin_api_count"], 1)
        self.assertEqual(persisted["api_validation_summary"]["validated_dragon_tiger_api_count"], 2)
        self.assertEqual(persisted["api_validation_summary"]["validated_limit_emotion_api_count"], 3)
        self.assertEqual(persisted["api_validation_summary"]["validated_financial_disclosure_api_count"], 1)
        self.assertEqual(persisted["api_validation_summary"]["task_call_result_count"], 9)
        self.assertIn("daily", persisted["api_validation_matrix_policy"]["matrix_only_apis"])
        target_by_key = {row["target"]: row for row in persisted["api_validation_target_rows"]}
        self.assertEqual(target_by_key["trade_calendar"]["readiness"], "validated")
        self.assertEqual(target_by_key["margin_financing"]["readiness"], "validated")
        self.assertEqual(target_by_key["dragon_tiger"]["readiness"], "validated")
        self.assertEqual(target_by_key["limit_emotion"]["readiness"], "partial_failed")
        self.assertEqual(target_by_key["financial_disclosure"]["readiness"], "validated")
        self.assertEqual(target_by_key["hard_risk"]["readiness"], "validated")
        self.assertEqual(target_by_key["hard_risk"]["selected_apis"], ["stk_surv"])
        self.assertEqual(target_by_key["chip_distribution"]["readiness"], "matrix_only")
        self.assertEqual(persisted["api_validation_target_summary"]["validated_target_count"], 5)
        self.assertGreaterEqual(persisted["api_validation_target_summary"]["partial_or_failed_target_count"], 1)
        audit = persisted["api_acceptance_audit"]
        self.assertEqual(audit["status"], "acceptance_audit_passed")
        self.assertEqual(audit["selected_api_count"], 9)
        self.assertEqual(audit["called_api_count"], 9)
        self.assertEqual(audit["safe_failure_state_count"], 1)
        self.assertEqual(audit["safe_empty_state_count"], 3)
        self.assertEqual(audit["false_verified_count"], 0)
        self.assertEqual(audit["false_parquet_write_claim_count"], 0)
        self.assertEqual(audit["unsafe_error_message_count"], 0)
        self.assertFalse(audit["full_interface_acceptance_done"])
        acceptance_by_api = {row["api"]: row for row in persisted["api_acceptance_audit_rows"]}
        self.assertEqual(acceptance_by_api["limit_cpt_list"]["acceptance_status"], "passed")
        self.assertEqual(acceptance_by_api["limit_cpt_list"]["failure_mode"], "provider_error_safe")
        self.assertEqual(acceptance_by_api["limit_cpt_list"]["failure_mode_status"], "validated_failed_safe")
        self.assertTrue(acceptance_by_api["limit_cpt_list"]["safe_failure_state_visible"])
        self.assertFalse(acceptance_by_api["limit_cpt_list"]["error_message_safe_has_unsafe_text"])
        self.assertFalse(acceptance_by_api["margin_detail"]["false_parquet_write_claim"])
        failure_mode_qa = persisted["failure_mode_qa_contract"]
        failure_rows = {row["mode"]: row for row in persisted["failure_mode_qa_rows"]}
        self.assertEqual(failure_mode_qa["schema_version"], "tushare_failure_mode_qa_contract.v1")
        self.assertEqual(failure_mode_qa["status"], "failure_mode_qa_ready_provider_acceptance_pending")
        self.assertEqual(failure_mode_qa["scope"], "local_call_ledger_failure_mode_classification_not_provider_acceptance")
        self.assertIn("empty_result_or_no_record", failure_mode_qa["observed_modes"])
        self.assertIn("provider_error_safe", failure_mode_qa["observed_modes"])
        self.assertTrue(failure_mode_qa["empty_result_or_no_record_distinguishable"])
        self.assertTrue(failure_mode_qa["permission_denied_distinguishable"])
        self.assertTrue(failure_mode_qa["parse_failed_or_invalid_result_distinguishable"])
        self.assertTrue(failure_mode_qa["missing_required_parameter_distinguishable"])
        self.assertFalse(failure_mode_qa["provider_backed_acceptance_done"])
        self.assertFalse(failure_mode_qa["production_tushare_pipeline_complete"])
        self.assertFalse(failure_mode_qa["qa_external_calls_triggered"])
        self.assertEqual(failure_mode_qa["unsafe_row_count"], 0)
        self.assertEqual(failure_rows["empty_result_or_no_record"]["status"], "observed")
        self.assertEqual(failure_rows["provider_error_safe"]["status"], "observed")
        self.assertEqual(failure_rows["permission_denied"]["status"], "ready_not_observed")
        self.assertEqual(failure_rows["parse_failed_or_invalid_result"]["status"], "ready_not_observed")
        request_param_qa = persisted["request_parameter_qa_contract"]
        request_rows = {row["api"]: row for row in persisted["request_parameter_qa_rows"]}
        self.assertEqual(request_param_qa["schema_version"], "tushare_request_parameter_qa_contract.v1")
        self.assertEqual(request_param_qa["status"], "request_parameter_qa_ready_provider_acceptance_pending")
        self.assertEqual(request_param_qa["scope"], "local_request_parameter_contract_not_provider_call")
        self.assertEqual(request_param_qa["selected_api_count"], 9)
        self.assertEqual(request_param_qa["missing_required_preflight_api_count"], 0)
        self.assertEqual(request_param_qa["unsafe_request_param_api_count"], 0)
        self.assertTrue(request_param_qa["raw_payload_sensitive_keys_dropped"])
        self.assertFalse(request_param_qa["provider_backed_acceptance_done"])
        self.assertFalse(request_param_qa["production_tushare_pipeline_complete"])
        self.assertFalse(request_param_qa["qa_external_calls_triggered"])
        self.assertEqual(request_rows["trade_cal"]["status"], "request_params_safe")
        self.assertEqual(request_rows["trade_cal"]["required_preflight_params"], [])
        self.assertIn("start_date", request_rows["trade_cal"]["provided_date_context_params"])
        self.assertEqual(request_rows["top_list"]["required_preflight_params"], ["ts_code"])
        self.assertEqual(request_rows["top_list"]["missing_required_preflight_params"], [])
        self.assertEqual(request_rows["daily"]["status"], "matrix_only")
        self.assertFalse(request_rows["daily"]["request_params_safe_has_secret_key"])
        sample_plan = persisted["provider_target_sample_plan_contract"]
        sample_plan_rows = {row["target"]: row for row in persisted["provider_target_sample_plan_rows"]}
        self.assertEqual(sample_plan["status"], "local_plan_ready_provider_execution_pending")
        self.assertEqual(sample_plan["ready_to_execute_target_count"], 3)
        self.assertEqual(sample_plan["pending_or_blocked_target_count"], 4)
        self.assertFalse(sample_plan["provider_backed_acceptance_done"])
        self.assertFalse(sample_plan["production_tushare_pipeline_complete"])
        self.assertFalse(sample_plan["cache_get_external_calls"])
        self.assertFalse(sample_plan["plan_external_calls_triggered"])
        self.assertEqual(sample_plan_rows["trade_calendar"]["provider_sample_plan_status"], "ready_to_execute_provider_sample")
        self.assertEqual(sample_plan_rows["margin_financing"]["provider_sample_plan_status"], "ready_to_execute_provider_sample")
        self.assertEqual(sample_plan_rows["limit_emotion"]["provider_sample_plan_status"], "ready_to_execute_provider_sample")
        self.assertEqual(sample_plan_rows["dragon_tiger"]["provider_sample_plan_status"], "sample_window_context_pending")
        self.assertEqual(sample_plan_rows["financial_disclosure"]["provider_sample_plan_status"], "partial_selection_plan_pending")
        self.assertEqual(sample_plan_rows["hard_risk"]["provider_sample_plan_status"], "partial_selection_plan_pending")
        self.assertEqual(sample_plan_rows["chip_distribution"]["provider_sample_plan_status"], "matrix_only_plan_pending")
        self.assertIn("trade_date", sample_plan_rows["dragon_tiger"]["missing_context_groups"])
        self.assertIn("top_inst_trade_date_rows_or_valid_empty", sample_plan_rows["dragon_tiger"]["required_success_evidence"])
        self.assertEqual(sample_plan_rows["trade_calendar"]["provider_sample_acceptance_status"], "provider_execution_pending")

    def test_tushare_refresh_task_include_extended_adds_calendar_and_blocks_missing_ts_code_safely(self):
        db_path = self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        class CalendarOnlyFakeAdapter:
            def get_trade_cal(self, **params):
                return {"ok": True, "data": [{"cal_date": "20260610", "is_open": 1}], "error": ""}

        task = tushare_task_service.run_tushare_refresh_task(
            {"include_extended": True, "start_date": "20260601", "end_date": "20260610"},
            adapter=CalendarOnlyFakeAdapter(),
        )

        self.assertEqual(task["status"], "success")
        self.assertTrue(task["tushare_called"])
        ledger_by_api = {row["api"]: row for row in task["call_ledger"]}
        self.assertEqual(ledger_by_api["trade_cal"]["call_status"], "success")
        self.assertEqual(ledger_by_api["daily"]["call_status"], "blocked_missing_ts_code")
        self.assertEqual(ledger_by_api["margin_detail"]["call_status"], "blocked_missing_ts_code")
        self.assertEqual(ledger_by_api["limit_cpt_list"]["call_status"], "failed")
        self.assertFalse(ledger_by_api["daily"]["external_calls_triggered"])
        self.assertTrue(ledger_by_api["trade_cal"]["external_calls_triggered"])
        self.assertNotIn("Traceback", json.dumps(task, ensure_ascii=False))

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertIsNotNone(persisted)
        expected_blocked = [
            api for api, spec in tushare_task_service.REFRESH_API_SPECS.items()
            if api != "limit_cpt_list" and "ts_code" in spec["params"]
        ]
        self.assertEqual(persisted["blocked_count"], len(expected_blocked))
        self.assertEqual(persisted["api_validation_summary"]["calendar_api_count"], 1)
        self.assertEqual(persisted["api_validation_summary"]["selected_api_count"], len(tushare_task_service.ALL_REFRESH_APIS))
        self.assertEqual(persisted["api_validation_summary"]["blocked_count"], persisted["blocked_count"])
        self.assertGreater(persisted["api_validation_summary"]["preflight_blocked_count"], 0)
        validation_by_api = {row["api"]: row for row in persisted["api_validation_rows"]}
        self.assertEqual(validation_by_api["daily"]["validation_scope"], "preflight_blocked")
        self.assertEqual(validation_by_api["trade_cal"]["validation_scope"], "task_call_result")
        self.assertEqual(persisted["api_validation_matrix_policy"]["matrix_only_apis"], [])
        provider_readiness = persisted["provider_acceptance_readiness_audit"]
        self.assertEqual(provider_readiness["schema_version"], "tushare_provider_acceptance_readiness_audit.v1")
        self.assertEqual(provider_readiness["status"], "provider_acceptance_pending")
        self.assertEqual(provider_readiness["selected_api_count"], len(tushare_task_service.ALL_REFRESH_APIS))
        self.assertEqual(provider_readiness["matrix_only_api_count"], 0)
        self.assertFalse(provider_readiness["full_interface_acceptance_done"])
        self.assertFalse(provider_readiness["provider_backed_acceptance_done"])
        self.assertFalse(provider_readiness["production_tushare_pipeline_complete"])
        self.assertFalse(provider_readiness["cache_get_external_calls"])
        self.assertFalse(provider_readiness["audit_external_calls_triggered"])
        self.assertTrue(provider_readiness["does_not_execute_trades"])
        self.assertTrue(provider_readiness["does_not_modify_strategy_action"])
        self.assertGreater(provider_readiness["production_blocker_count"], 0)
        readiness_rows = {row["criterion"]: row for row in persisted["provider_acceptance_readiness_rows"]}
        self.assertEqual(readiness_rows["post_task_button_gate"]["status"], "passed")
        self.assertEqual(readiness_rows["call_ledger_semantic_audit"]["status"], "passed")
        self.assertEqual(readiness_rows["all_declared_apis_selected"]["status"], "passed")
        self.assertEqual(readiness_rows["all_selected_success_non_empty"]["status"], "blocked")
        self.assertEqual(readiness_rows["all_target_groups_validated"]["status"], "blocked")
        self.assertEqual(readiness_rows["provider_backed_acceptance_evidence"]["status"], "blocked")
        self.assertEqual(readiness_rows["safe_params_errors_and_parquet_scope"]["status"], "passed")
        self.assertEqual(readiness_rows["trade_and_action_boundary"]["status"], "passed")
        promotion = persisted["provider_acceptance_promotion_audit"]
        promotion_rows = {row["criterion"]: row for row in persisted["provider_acceptance_promotion_rows"]}
        self.assertEqual(promotion["schema_version"], "tushare_provider_acceptance_promotion_audit.v1")
        self.assertEqual(promotion["status"], "provider_acceptance_promotion_pending")
        self.assertEqual(promotion["scope"], "local_call_ledger_promotion_audit_no_provider_execution")
        self.assertFalse(promotion["promotion_ready"])
        self.assertFalse(promotion["provider_backed_acceptance_done"])
        self.assertFalse(promotion["production_tushare_pipeline_complete"])
        self.assertFalse(promotion["audit_external_calls_triggered"])
        self.assertFalse(promotion["tushare_called_by_audit"])
        self.assertEqual(promotion_rows["explicit_provider_backed_acceptance_marker"]["status"], "blocked")
        self.assertEqual(promotion_rows["failure_mode_acceptance_evidence"]["status"], "blocked")
        self.assertEqual(promotion_rows["readiness_audit_still_local"]["status"], "passed")
        self.assertEqual(
            persisted["api_validation_matrix_policy"]["provider_acceptance_readiness_scope"],
            "provider_acceptance_readiness_audit 只汇总生产验收阻断项；不把 fake/local/matrix 证据当 provider-backed acceptance。",
        )
        self.assertIn("provider_acceptance_promotion_scope", persisted["api_validation_matrix_policy"])
        self.assertFalse(persisted["api_validation_matrix_policy"]["provider_acceptance_promotion_ready"])
        self.assertFalse(persisted["api_validation_matrix_policy"]["provider_acceptance_promotion_calls_provider"])
        self.assertFalse(persisted["api_validation_matrix_policy"]["provider_backed_acceptance_done"])
        self.assertFalse(persisted["api_validation_matrix_policy"]["production_tushare_pipeline_complete"])
        audit = persisted["api_acceptance_audit"]
        self.assertEqual(audit["status"], "acceptance_audit_passed")
        self.assertEqual(audit["selected_api_count"], len(tushare_task_service.ALL_REFRESH_APIS))
        self.assertEqual(audit["selected_missing_call_ledger_count"], 0)
        self.assertEqual(audit["safe_blocked_state_count"], len(expected_blocked))
        self.assertGreaterEqual(audit["safe_failure_state_count"], 1)
        self.assertEqual(audit["false_verified_count"], 0)
        self.assertEqual(audit["required_field_gap_count"], 0)
        self.assertEqual(audit["unsafe_error_message_count"], 0)
        self.assertFalse(audit["full_interface_acceptance_done"])
        acceptance_by_api = {row["api"]: row for row in persisted["api_acceptance_audit_rows"]}
        self.assertTrue(acceptance_by_api["daily"]["safe_blocked_state_visible"])
        self.assertEqual(acceptance_by_api["daily"]["acceptance_status"], "passed")
        self.assertEqual(acceptance_by_api["trade_cal"]["acceptance_status"], "passed")
        self.assertEqual(acceptance_by_api["daily"]["failure_mode"], "missing_required_parameter")
        self.assertEqual(acceptance_by_api["daily"]["failure_mode_status"], "preflight_blocked_no_external_call")
        failure_mode_qa = persisted["failure_mode_qa_contract"]
        failure_rows = {row["mode"]: row for row in persisted["failure_mode_qa_rows"]}
        self.assertIn("missing_required_parameter", failure_mode_qa["observed_modes"])
        self.assertEqual(failure_rows["missing_required_parameter"]["status"], "observed")
        self.assertFalse(failure_rows["missing_required_parameter"]["qa_external_calls_triggered"])
        self.assertEqual(failure_rows["matrix_only_not_requested"]["status"], "ready_not_observed")
        request_param_qa = persisted["request_parameter_qa_contract"]
        request_rows = {row["api"]: row for row in persisted["request_parameter_qa_rows"]}
        self.assertEqual(request_param_qa["status"], "request_parameter_qa_ready_provider_acceptance_pending")
        self.assertGreater(request_param_qa["missing_required_preflight_api_count"], 0)
        self.assertEqual(request_param_qa["unsafe_request_param_api_count"], 0)
        self.assertFalse(request_param_qa["raw_payload_sensitive_keys_dropped"])
        self.assertEqual(request_rows["daily"]["status"], "preflight_blocked_missing_required_param")
        self.assertEqual(request_rows["daily"]["missing_required_preflight_params"], ["ts_code"])
        self.assertFalse(request_rows["daily"]["qa_external_calls_triggered"])
        self.assertEqual(request_rows["trade_cal"]["status"], "request_params_safe")
        self.assertIn("start_date", request_rows["trade_cal"]["provided_date_context_params"])
        sample_plan = persisted["provider_target_sample_plan_contract"]
        sample_plan_rows = {row["target"]: row for row in persisted["provider_target_sample_plan_rows"]}
        self.assertEqual(sample_plan["status"], "local_plan_ready_provider_execution_pending")
        self.assertEqual(sample_plan["ready_to_execute_target_count"], 1)
        self.assertEqual(sample_plan["pending_or_blocked_target_count"], 6)
        self.assertFalse(sample_plan["provider_backed_acceptance_done"])
        self.assertFalse(sample_plan["production_tushare_pipeline_complete"])
        self.assertFalse(sample_plan["plan_external_calls_triggered"])
        self.assertEqual(sample_plan_rows["trade_calendar"]["provider_sample_plan_status"], "ready_to_execute_provider_sample")
        self.assertEqual(sample_plan_rows["margin_financing"]["provider_sample_plan_status"], "blocked_missing_required_params")
        self.assertEqual(sample_plan_rows["dragon_tiger"]["provider_sample_plan_status"], "blocked_missing_required_params")
        self.assertEqual(sample_plan_rows["chip_distribution"]["provider_sample_plan_status"], "blocked_missing_required_params")
        self.assertGreater(sample_plan_rows["hard_risk"]["missing_required_param_api_count"], 0)
        self.assertEqual(sample_plan_rows["hard_risk"]["provider_sample_acceptance_status"], "provider_execution_pending")
        self.assertEqual(persisted["provider_acceptance_promotion_status"], "provider_acceptance_promotion_pending")
        self.assertGreater(persisted["provider_acceptance_promotion_blocker_count"], 0)
        self.assertFalse(persisted["provider_acceptance_promotion_ready"])

    def test_tushare_acceptance_audit_requires_non_empty_success_for_full_interface_completion(self):
        call_ledger = []
        for index, api in enumerate(tushare_task_service.REFRESH_API_SPECS):
            is_first = index == 0
            call_ledger.append(
                {
                    "api": api,
                    "request_params_safe": {"ts_code": "002008.SZ"},
                    "row_count": 1 if is_first else 0,
                    "data_date": "20260610" if is_first else None,
                    "local_fetched_at": "2026-06-10T16:31:00",
                    "call_status": "success" if is_first else "empty",
                    "error_message_safe": "",
                    "parquet_status": "written" if tushare_task_service.REFRESH_API_SPECS[api].get("parquet_dataset") and is_first else "not_enabled",
                    "parquet_row_count": 1 if tushare_task_service.REFRESH_API_SPECS[api].get("parquet_dataset") and is_first else 0,
                    "external_calls_triggered": True,
                }
            )

        validation_rows = tushare_task_service._api_validation_rows(tushare_task_service.REFRESH_API_SPECS.keys(), call_ledger)
        audit = tushare_task_service._api_acceptance_audit(validation_rows, call_ledger)

        self.assertEqual(audit["status"], "acceptance_audit_passed")
        self.assertEqual(audit["selected_api_count"], len(tushare_task_service.REFRESH_API_SPECS))
        self.assertEqual(audit["called_api_count"], len(tushare_task_service.REFRESH_API_SPECS))
        self.assertEqual(audit["successful_selected_api_count"], 1)
        self.assertGreater(audit["safe_empty_state_count"], 0)
        self.assertEqual(audit["acceptance_issue_count"], 0)
        self.assertFalse(audit["full_interface_acceptance_done"])
        self.assertIn("non-empty successful samples", audit["full_interface_acceptance_scope"])

    def test_tushare_provider_acceptance_promotion_audit_can_read_prior_full_interface_evidence(self):
        selected_apis = list(tushare_task_service.REFRESH_API_SPECS)
        call_ledger = []
        for index, api in enumerate(selected_apis):
            dataset = tushare_task_service.REFRESH_API_SPECS[api].get("parquet_dataset")
            call_ledger.append(
                {
                    "api": api,
                    "request_params_safe": {
                        "ts_code": "002008.SZ",
                        "trade_date": "20260610",
                        "start_date": "20260601",
                        "end_date": "20260610",
                    },
                    "row_count": 1,
                    "data_date": "20260610",
                    "local_fetched_at": "2026-06-10T16:31:00",
                    "call_status": "success",
                    "error_message_safe": "",
                    "parquet_status": "written" if dataset else "not_enabled",
                    "parquet_row_count": 1 if dataset else 0,
                    "external_calls_triggered": True,
                    "tushare_called": True,
                    "failure_mode_acceptance_done": index == 0,
                    "failure_mode_validated_count": 6 if index == 0 else 0,
                    "provider_acceptance_marker": "provider_backed_full_interface_acceptance" if index == 0 else "",
                }
            )

        payload = {
            "ts_code": "002008.SZ",
            "trade_date": "20260610",
            "start_date": "20260601",
            "end_date": "20260610",
            "ann_date": "20260610",
            "period": "20260630",
            "apis": selected_apis,
        }
        validation_rows = tushare_task_service._api_validation_rows(selected_apis, call_ledger)
        validation_target_rows = tushare_task_service._validation_target_rows(validation_rows)
        acceptance_audit = tushare_task_service._api_acceptance_audit(validation_rows, call_ledger)
        target_sample_plan = tushare_task_service._provider_target_sample_plan_contract(
            selected_apis=selected_apis,
            payload=payload,
            api_validation_rows=validation_rows,
        )
        readiness = tushare_task_service._provider_acceptance_readiness_audit(
            api_validation_rows=validation_rows,
            validation_target_rows=validation_target_rows,
            api_acceptance_audit=acceptance_audit,
        )
        promotion = tushare_task_service._provider_acceptance_promotion_audit(
            api_validation_rows=validation_rows,
            validation_target_rows=validation_target_rows,
            api_acceptance_audit=acceptance_audit,
            provider_target_sample_plan_contract=target_sample_plan,
            provider_acceptance_readiness_audit=readiness,
            call_ledger=call_ledger,
        )
        rows = {row["criterion"]: row for row in promotion["rows"]}

        self.assertEqual(promotion["schema_version"], "tushare_provider_acceptance_promotion_audit.v1")
        self.assertEqual(promotion["status"], "provider_acceptance_promotion_ready")
        self.assertTrue(promotion["promotion_ready"])
        self.assertTrue(promotion["provider_backed_acceptance_done"])
        self.assertFalse(promotion["production_tushare_pipeline_complete"])
        self.assertEqual(promotion["blocking_criterion_count"], 0)
        self.assertFalse(promotion["audit_external_calls_triggered"])
        self.assertFalse(promotion["tushare_called_by_audit"])
        self.assertTrue(rows["all_declared_apis_selected"]["passed"])
        self.assertTrue(rows["all_declared_apis_success_non_empty"]["passed"])
        self.assertTrue(rows["all_target_groups_validated"]["passed"])
        self.assertTrue(rows["explicit_provider_backed_acceptance_marker"]["passed"])
        self.assertTrue(rows["failure_mode_acceptance_evidence"]["passed"])

    def test_tushare_refresh_task_exposes_failure_mode_qa_contract(self):
        db_path = self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        class FailureModeFakeAdapter:
            def get_margin_detail(self, **params):
                return {"ok": True, "data": [], "error": ""}

            def get_top_list(self, **params):
                return {"ok": False, "data": None, "error": "permission denied api_key=SHOULD_DROP"}

            def get_limit_cpt_list(self, **params):
                return ["invalid result list"]

        task = tushare_task_service.run_tushare_refresh_task(
            {
                "ts_code": "002008.SZ",
                "trade_date": "20260610",
                "start_date": "20260601",
                "end_date": "20260610",
                "apis": ["margin_detail", "top_list", "limit_cpt_list"],
                "token": "SHOULD_DROP",
            },
            adapter=FailureModeFakeAdapter(),
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "tushare_refresh_partial_safe")
        self.assertTrue(task["external_calls_triggered"])
        self.assertTrue(task["tushare_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))

        ledger_by_api = {row["api"]: row for row in task["call_ledger"]}
        self.assertEqual(ledger_by_api["margin_detail"]["call_status"], "empty")
        self.assertEqual(ledger_by_api["margin_detail"]["failure_mode"], "empty_result_or_no_record")
        self.assertEqual(ledger_by_api["margin_detail"]["failure_mode_status"], "validated_empty_not_verified_data")
        self.assertEqual(ledger_by_api["top_list"]["call_status"], "failed")
        self.assertEqual(ledger_by_api["top_list"]["failure_mode"], "permission_denied")
        self.assertEqual(ledger_by_api["top_list"]["error_message_safe"], "tushare_error_redacted_safe")
        self.assertEqual(ledger_by_api["limit_cpt_list"]["call_status"], "failed")
        self.assertEqual(ledger_by_api["limit_cpt_list"]["failure_mode"], "parse_failed_or_invalid_result")
        self.assertTrue(ledger_by_api["limit_cpt_list"]["safe_failure_mode_visible"])

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertIsNotNone(persisted)
        failure_mode_qa = persisted["failure_mode_qa_contract"]
        failure_rows = {row["mode"]: row for row in persisted["failure_mode_qa_rows"]}
        self.assertEqual(failure_mode_qa["schema_version"], "tushare_failure_mode_qa_contract.v1")
        self.assertEqual(failure_mode_qa["status"], "failure_mode_qa_ready_provider_acceptance_pending")
        self.assertEqual(failure_mode_qa["selected_api_count"], 3)
        self.assertEqual(failure_mode_qa["called_api_count"], 3)
        self.assertIn("empty_result_or_no_record", failure_mode_qa["observed_modes"])
        self.assertIn("permission_denied", failure_mode_qa["observed_modes"])
        self.assertIn("parse_failed_or_invalid_result", failure_mode_qa["observed_modes"])
        self.assertTrue(failure_mode_qa["safe_error_text"])
        self.assertEqual(failure_mode_qa["unsafe_row_count"], 0)
        self.assertFalse(failure_mode_qa["provider_backed_acceptance_done"])
        self.assertFalse(failure_mode_qa["production_tushare_pipeline_complete"])
        self.assertFalse(failure_mode_qa["qa_external_calls_triggered"])
        self.assertFalse(failure_mode_qa["tushare_called_by_qa"])
        self.assertEqual(failure_rows["empty_result_or_no_record"]["status"], "observed")
        self.assertEqual(failure_rows["permission_denied"]["status"], "observed")
        self.assertEqual(failure_rows["parse_failed_or_invalid_result"]["status"], "observed")
        self.assertEqual(failure_rows["missing_required_parameter"]["status"], "ready_not_observed")
        self.assertEqual(failure_rows["provider_error_safe"]["status"], "ready_not_observed")
        self.assertTrue(all(row["distinguishable"] for row in persisted["failure_mode_qa_rows"]))
        self.assertNotIn("api_key", json.dumps(persisted, ensure_ascii=False))
        self.assertNotIn("SHOULD_DROP", json.dumps(persisted, ensure_ascii=False))

    def test_tushare_request_parameter_qa_tracks_alias_and_date_context_without_provider_acceptance(self):
        db_path = self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        class AliasParamFakeAdapter:
            def get_daily(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "trade_date": "20260610", "close": 10.4}], "error": ""}

        task = tushare_task_service.run_tushare_refresh_task(
            {
                "ticker": "002008.SZ",
                "start_date": "20260601",
                "end_date": "20260610",
                "apis": ["daily"],
                "authorization": "Bearer SHOULD_DROP",
            },
            adapter=AliasParamFakeAdapter(),
        )

        self.assertEqual(task["status"], "success")
        self.assertTrue(task["tushare_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertIsNotNone(persisted)
        request_param_qa = persisted["request_parameter_qa_contract"]
        request_rows = {row["api"]: row for row in persisted["request_parameter_qa_rows"]}
        self.assertEqual(request_param_qa["status"], "request_parameter_qa_ready_provider_acceptance_pending")
        self.assertEqual(request_param_qa["selected_api_count"], 1)
        self.assertEqual(request_param_qa["missing_required_preflight_api_count"], 0)
        self.assertEqual(request_param_qa["unsafe_request_param_api_count"], 0)
        self.assertTrue(request_param_qa["raw_payload_sensitive_keys_dropped"])
        self.assertFalse(request_param_qa["provider_backed_acceptance_done"])
        self.assertFalse(request_param_qa["tushare_called_by_qa"])
        self.assertEqual(request_rows["daily"]["status"], "request_params_safe")
        self.assertTrue(request_rows["daily"]["ts_code_alias_supported"])
        self.assertEqual(request_rows["daily"]["provided_param_keys"], ["end_date", "start_date", "ts_code"])
        self.assertEqual(request_rows["daily"]["provided_date_context_params"], ["start_date", "end_date"])
        self.assertEqual(request_rows["trade_cal"]["status"], "matrix_only")
        self.assertNotIn("authorization", json.dumps(persisted, ensure_ascii=False).lower())
        self.assertNotIn("SHOULD_DROP", json.dumps(persisted, ensure_ascii=False))

    def test_tushare_refresh_task_validates_chip_and_hard_risk_domains(self):
        db_path = self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        class ChipRiskFakeAdapter:
            def get_cyq_perf(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "trade_date": "20260610", "winner_rate": 0.62}], "error": ""}

            def get_cyq_chips(self, **params):
                return {"ok": True, "data": [], "error": ""}

            def get_anns_d(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "ann_date": "20260609", "title": "safe"}], "error": ""}

            def get_forecast(self, **params):
                return {"ok": True, "data": [], "error": ""}

            def get_stk_holdertrade(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "ann_date": "20260608", "holder_name": "holder"}], "error": ""}

            def get_share_float(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "float_date": "20260607", "float_share": 1000}], "error": ""}

            def get_pledge_stat(self, **params):
                return {"ok": False, "data": None, "error": "Traceback token=SHOULD_DROP pledge failed"}

            def get_pledge_detail(self, **params):
                return {"ok": True, "data": [{"ts_code": params["ts_code"], "end_date": "20260606", "pledge_amount": 100}], "error": ""}

        selected_apis = [
            "cyq_perf",
            "cyq_chips",
            "anns_d",
            "forecast",
            "stk_holdertrade",
            "share_float",
            "pledge_stat",
            "pledge_detail",
        ]
        task = tushare_task_service.run_tushare_refresh_task(
            {
                "ts_code": "002008.SZ",
                "start_date": "20260601",
                "end_date": "20260610",
                "apis": selected_apis,
                "authorization": "Bearer SHOULD_DROP",
            },
            adapter=ChipRiskFakeAdapter(),
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "tushare_refresh_partial_safe")
        self.assertTrue(task["external_calls_triggered"])
        self.assertTrue(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))
        self.assertEqual([row["api"] for row in task["call_ledger"]], selected_apis)

        ledger_by_api = {row["api"]: row for row in task["call_ledger"]}
        self.assertEqual(ledger_by_api["cyq_perf"]["call_status"], "success")
        self.assertEqual(ledger_by_api["cyq_perf"]["data_date"], "20260610")
        self.assertEqual(ledger_by_api["cyq_chips"]["call_status"], "empty")
        self.assertEqual(ledger_by_api["anns_d"]["data_date"], "20260609")
        self.assertEqual(ledger_by_api["forecast"]["call_status"], "empty")
        self.assertEqual(ledger_by_api["stk_holdertrade"]["data_date"], "20260608")
        self.assertEqual(ledger_by_api["share_float"]["data_date"], "20260607")
        self.assertEqual(ledger_by_api["pledge_detail"]["data_date"], "20260606")
        self.assertEqual(ledger_by_api["pledge_stat"]["call_status"], "failed")
        self.assertEqual(ledger_by_api["pledge_stat"]["error_message_safe"], "tushare_error_redacted_safe")
        self.assertTrue(
            all(
                row["parquet_status"] == "not_enabled"
                for row in task["call_ledger"]
                if row["call_status"] != "failed"
            )
        )
        self.assertEqual(ledger_by_api["pledge_stat"]["parquet_status"], "not_written_failed_call")

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["status"], "success")
        self.assertEqual(persisted["success_count"], 7)
        self.assertEqual(persisted["failed_count"], 1)
        self.assertEqual(persisted["api_groups"]["chip"], ["cyq_perf", "cyq_chips"])
        self.assertIn("pledge_detail", persisted["api_groups"]["hard_risk"])
        summary = persisted["api_validation_summary"]
        self.assertEqual(summary["selected_api_count"], len(selected_apis))
        self.assertEqual(summary["selected_chip_api_count"], 2)
        self.assertGreaterEqual(summary["selected_hard_risk_api_count"], 5)
        self.assertEqual(summary["validated_chip_api_count"], 2)
        self.assertGreaterEqual(summary["validated_hard_risk_api_count"], 5)
        self.assertEqual(summary["domain_status_counts"]["chip_distribution"]["validated_success"], 1)
        self.assertEqual(summary["domain_status_counts"]["chip_distribution"]["validated_empty"], 1)
        self.assertGreaterEqual(summary["domain_status_counts"]["hard_risk"]["validated_success"], 4)
        self.assertEqual(summary["domain_status_counts"]["hard_risk"]["validated_failed"], 1)

        validation_by_api = {row["api"]: row for row in persisted["api_validation_rows"]}
        self.assertTrue(validation_by_api["cyq_perf"]["chip_api"])
        self.assertEqual(validation_by_api["cyq_perf"]["domain"], "chip_distribution")
        self.assertEqual(validation_by_api["cyq_chips"]["validation_status"], "validated_empty")
        self.assertTrue(validation_by_api["pledge_stat"]["hard_risk_api"])
        self.assertEqual(validation_by_api["pledge_stat"]["domain"], "hard_risk")
        self.assertEqual(validation_by_api["pledge_stat"]["validation_status"], "validated_failed")
        self.assertEqual(validation_by_api["daily"]["validation_status"], "not_requested")
        self.assertEqual(validation_by_api["daily"]["validation_scope"], "capability_matrix_only")
        self.assertTrue(persisted["api_validation_summary"]["does_not_claim_unselected_apis_verified"])
        target_by_key = {row["target"]: row for row in persisted["api_validation_target_rows"]}
        self.assertEqual(target_by_key["chip_distribution"]["readiness"], "validated")
        self.assertEqual(target_by_key["hard_risk"]["readiness"], "partial_failed")
        self.assertEqual(target_by_key["limit_emotion"]["readiness"], "matrix_only")
        self.assertEqual(target_by_key["hard_risk"]["failed_api_count"], 1)
        provider_readiness = persisted["provider_acceptance_readiness_audit"]
        self.assertEqual(provider_readiness["status"], "provider_acceptance_pending")
        self.assertFalse(provider_readiness["provider_backed_acceptance_done"])
        self.assertFalse(provider_readiness["production_tushare_pipeline_complete"])
        self.assertGreater(provider_readiness["matrix_only_api_count"], 0)
        self.assertGreater(provider_readiness["matrix_only_target_count"], 0)
        self.assertGreater(provider_readiness["partial_or_blocked_target_count"], 0)
        readiness_rows = {row["criterion"]: row for row in persisted["provider_acceptance_readiness_rows"]}
        self.assertEqual(readiness_rows["all_declared_apis_selected"]["status"], "blocked")
        self.assertEqual(readiness_rows["all_target_groups_validated"]["status"], "blocked")
        self.assertEqual(readiness_rows["provider_backed_acceptance_evidence"]["status"], "blocked")

    def test_tushare_refresh_task_failure_keeps_safe_error_and_action_boundary(self):
        self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        class FailingTushareAdapter:
            def get_daily(self, **params):
                return {"ok": False, "data": None, "error": "Traceback token=SHOULD_DROP api_key=DROP"}

        task = tushare_task_service.run_tushare_refresh_task(
            {"ts_code": "002008.SZ", "apis": ["daily"], "api_key": "SHOULD_DROP"},
            adapter=FailingTushareAdapter(),
        )

        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["current_step"], "tushare_refresh_failed_safe")
        self.assertTrue(task["external_calls_triggered"])
        self.assertTrue(task["tushare_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertEqual(task["call_ledger"][0]["call_status"], "failed")
        self.assertEqual(task["call_ledger"][0]["error_message_safe"], "tushare_error_redacted_safe")
        dumped = json.dumps(task, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn("Traceback", dumped)
        self.assertNotIn("api_key", dumped)

    def test_tushare_refresh_task_blocks_missing_ts_code_without_external_call(self):
        db_path = self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        class ExplodingTushareAdapter:
            def get_daily(self, **params):
                raise AssertionError("should_not_call_tushare_without_ts_code")

        task = tushare_task_service.run_tushare_refresh_task(
            {"apis": ["daily"], "token": "SHOULD_DROP"},
            adapter=ExplodingTushareAdapter(),
        )

        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["current_step"], "tushare_refresh_blocked_missing_params")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("token", task["payload_safe"])
        self.assertEqual(task["call_ledger"][0]["api"], "daily")
        self.assertEqual(task["call_ledger"][0]["call_status"], "blocked_missing_ts_code")
        self.assertEqual(task["call_ledger"][0]["error_message_safe"], "missing_required_ts_code")
        self.assert_local_ledger_boundary(task["call_ledger"][0])

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["status"], "failed")
        self.assertEqual(persisted["blocked_count"], 1)
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertFalse(persisted["tushare_called"])
        self.assertTrue(persisted["does_not_modify_strategy_action"])
        dumped = json.dumps({"task": task, "persisted": persisted}, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn("should_not_call", dumped)

    def test_smoke_script_includes_task_status_index(self):
        script = Path("scripts/smoke_3_0.sh").read_text(encoding="utf-8")

        self.assertIn("def assert_cache_safety", script)
        self.assertIn("TestClient", script)
        self.assertIn("def assert_api_cache_endpoint", script)
        self.assertIn("def assert_model_strategy_safety", script)
        self.assertIn("tempfile.TemporaryDirectory()", script)
        self.assertIn("_SMOKE_TASK_META_PATH", script)
        self.assertIn("task_service.SQLITE_META_PATH = _SMOKE_TASK_META_PATH", script)
        self.assertIn("clear_task_statuses_for_tests(clear_persisted=True)", script)
        self.assertIn("smoke_task_meta:", script)
        self.assertIn("response.get(\"call_ledger\")", script)
        self.assertIn("api_cache_paths", script)
        self.assertIn("/api/packets", script)
        self.assertIn("/api/packets/command_center_factor_quant_hub_packet", script)
        self.assertIn("/api/factor-quant/cache", script)
        self.assertIn("/api/storage", script)
        self.assertIn("/api/storage/catalog", script)
        self.assertIn("/api/storage/factor-values", script)
        self.assertIn("/api/storage/daily", script)
        self.assertIn("/api/storage/daily-basic", script)
        self.assertIn("/api/storage/moneyflow", script)
        self.assertIn("/api/storage/backtest-results", script)
        self.assertIn("/api/storage/sqlite-meta", script)
        self.assertIn("/api/tasks/catalog", script)
        self.assertIn("api_cache:", script)
        self.assertIn("/api/chokepoint/run", script)
        self.assertIn("task_creation_api:", script)
        self.assertIn("created.get(\"call_ledger\")", script)
        self.assertIn("external_calls_triggered", script)
        self.assertIn("does_not_execute_trades", script)
        self.assertIn("build_task_status_index", script)
        self.assertIn("task_status_index:", script)
        self.assertIn('task_index["call_ledger_count"]', script)
        self.assertIn("discovered_post_routes", script)
        self.assertIn('catalog["route_coverage"]["known_post_routes"]', script)
        self.assertIn("task_route_coverage:", script)
        self.assertIn("call_ledger_required_for_all_known_post_routes", script)
        self.assertIn("model_strategy purposes changed", script)
        self.assertIn("model_strategy explain_grade purposes must stay complete", script)
        self.assertIn("model_strategy fast_grade purposes must stay complete", script)
        self.assertIn("must not hardcode model at callsite", script)
        self.assertIn("must not contain secrets", script)
        self.assertIn("cache read must not external call", script)

    def test_push_gate_script_codifies_local_release_checks_without_push(self):
        path = Path("scripts/push_gate_3_0.sh")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("PYTHON_BIN=\"${PYTHON_BIN:-.venv/bin/python}\"", script)
        self.assertIn("PUSH_GATE_REPORT_PATH=\"${PUSH_GATE_REPORT_PATH:-}\"", script)
        self.assertIn("Do not use system Python", script)
        self.assertIn("-m unittest discover -s tests", script)
        self.assertIn("cd desktop && npm run build", script)
        self.assertIn("scripts/smoke_3_0.sh", script)
        self.assertIn("scripts/data_health_freshness_contract.py", script)
        self.assertIn("Data Health freshness contract", script)
        self.assertIn("data_health_freshness_contract: passed_local_contract_provider_execution_pending", script)
        self.assertIn("scripts/tushare_acceptance_contract.py", script)
        self.assertIn("Tushare acceptance contract", script)
        self.assertIn("tushare_acceptance_contract: passed_local_contract_provider_execution_pending", script)
        self.assertIn("scripts/factor_test_lab_contract.py", script)
        self.assertIn("Factor Test Lab contract", script)
        self.assertIn("factor_test_lab_contract: passed_local_contract_provider_execution_pending", script)
        self.assertIn("scripts/factor_universe_contract.py", script)
        self.assertIn("Factor universe contract", script)
        self.assertIn("factor_universe_contract: passed_local_contract_read_plan_execution_pending", script)
        self.assertIn("scripts/deepseek_governance_contract.py", script)
        self.assertIn("DeepSeek governance contract", script)
        self.assertIn("deepseek_governance_contract: passed_local_contract_provider_benchmark_pending", script)
        self.assertIn("scripts/next_session_map_contract.py", script)
        self.assertIn("Next-session map contract", script)
        self.assertIn("next_session_map_contract: passed_local_contract_streamlit_parity_pending", script)
        self.assertIn("scripts/candidate_radar_contract.py", script)
        self.assertIn("Candidate Radar contract", script)
        self.assertIn("candidate_radar_contract: passed_local_contract_replacement_pending", script)
        self.assertIn("scripts/candidate_radar_browser_qa_runbook.py", script)
        self.assertIn("Candidate Radar browser QA runbook", script)
        self.assertIn("candidate_radar_browser_qa_runbook: passed_runbook_execution_pending", script)
        self.assertIn("scripts/storage_contract.py", script)
        self.assertIn("Storage contract", script)
        self.assertIn("storage_contract: passed_local_contract_physical_migration_pending", script)
        self.assertIn("scripts/worker_contract.py", script)
        self.assertIn("Worker contract", script)
        self.assertIn("worker_contract: passed_local_contract_worker_activation_pending", script)
        self.assertIn("scripts/tauri_desktop_contract.py", script)
        self.assertIn("Tauri desktop contract", script)
        self.assertIn("tauri_desktop_contract: passed_local_contract_package_validation_pending", script)
        self.assertIn("scripts/streamlit_legacy_contract.py", script)
        self.assertIn("Streamlit legacy contract", script)
        self.assertIn("streamlit_legacy_contract: passed_local_contract_retirement_pending", script)
        self.assertIn("scripts/trade_isolation_contract.py", script)
        self.assertIn("Trade isolation contract", script)
        self.assertIn("trade_isolation_contract: passed_local_contract_real_trading_disconnected", script)
        self.assertIn("scripts/motion_viewport_qa_contract.py", script)
        self.assertIn("Motion viewport QA contract", script)
        self.assertIn("motion_viewport_qa_contract: passed_static_contract_visual_run_pending", script)
        self.assertIn("scripts/motion_browser_qa_runbook.py", script)
        self.assertIn("Motion browser QA runbook", script)
        self.assertIn("motion_browser_qa_runbook: passed_runbook_execution_pending", script)
        self.assertIn("scripts/secret_keyword_review_contract.py", script)
        self.assertIn("Secret keyword review contract", script)
        self.assertIn("secret_keyword_review_contract: passed_structured_no_raw_lines", script)
        self.assertIn("git diff --check", script)
        self.assertIn("secret_high_risk_scan", script)
        self.assertIn("artifact_scan", script)
        self.assertIn("write_release_readiness_report", script)
        self.assertIn("Release readiness report", script)
        self.assertIn("release readiness report: skipped", script)
        self.assertIn("worktree_clean_check_runs_after_report: true", script)
        self.assertLess(script.index('run_step "Release readiness report"'), script.index('run_step "Clean worktree check"'))
        self.assertIn("worktree_clean_scan", script)
        self.assertIn("git ls-files", script)
        self.assertIn("node_modules|dist|target|__pycache__", script)
        self.assertIn("desktop/src-tauri/icons/icon.png", script)
        self.assertIn("high-risk secret value scan", script)
        self.assertIn("keyword scan for review", script)
        self.assertIn("raw lines suppressed", script)
        self.assertNotIn("showing first 120", script)
        self.assertIn("did_not_push: true", script)
        self.assertIn("did_not_call_external_providers: true", script)
        self.assertIn("did_not_execute_trades: true", script)
        self.assertIn("Scaffold, preflight, matrix, mock, and sanitizer checks are not production completion evidence.", script)
        self.assertLess(script.index('run_step "Data Health freshness contract"'), script.index('run_step "Motion viewport QA contract"'))
        self.assertLess(script.index('run_step "Data Health freshness contract"'), script.index('run_step "Tushare acceptance contract"'))
        self.assertLess(script.index('run_step "Tushare acceptance contract"'), script.index('run_step "Motion viewport QA contract"'))
        self.assertLess(script.index('run_step "Tushare acceptance contract"'), script.index('run_step "Factor Test Lab contract"'))
        self.assertLess(script.index('run_step "Factor Test Lab contract"'), script.index('run_step "Motion viewport QA contract"'))
        self.assertLess(script.index('run_step "Factor Test Lab contract"'), script.index('run_step "Factor universe contract"'))
        self.assertLess(script.index('run_step "Factor universe contract"'), script.index('run_step "DeepSeek governance contract"'))
        self.assertLess(script.index('run_step "Factor Test Lab contract"'), script.index('run_step "DeepSeek governance contract"'))
        self.assertLess(script.index('run_step "DeepSeek governance contract"'), script.index('run_step "Next-session map contract"'))
        self.assertLess(script.index('run_step "Next-session map contract"'), script.index('run_step "Candidate Radar contract"'))
        self.assertLess(script.index('run_step "Factor Test Lab contract"'), script.index('run_step "Candidate Radar contract"'))
        self.assertLess(script.index('run_step "Candidate Radar contract"'), script.index('run_step "Candidate Radar browser QA runbook"'))
        self.assertLess(script.index('run_step "Candidate Radar browser QA runbook"'), script.index('run_step "Motion viewport QA contract"'))
        self.assertLess(script.index('run_step "Candidate Radar contract"'), script.index('run_step "Storage contract"'))
        self.assertLess(script.index('run_step "Storage contract"'), script.index('run_step "Motion viewport QA contract"'))
        self.assertLess(script.index('run_step "Storage contract"'), script.index('run_step "Worker contract"'))
        self.assertLess(script.index('run_step "Worker contract"'), script.index('run_step "Motion viewport QA contract"'))
        self.assertLess(script.index('run_step "Worker contract"'), script.index('run_step "Tauri desktop contract"'))
        self.assertLess(script.index('run_step "Tauri desktop contract"'), script.index('run_step "Motion viewport QA contract"'))
        self.assertLess(script.index('run_step "Tauri desktop contract"'), script.index('run_step "Streamlit legacy contract"'))
        self.assertLess(script.index('run_step "Streamlit legacy contract"'), script.index('run_step "Motion viewport QA contract"'))
        self.assertLess(script.index('run_step "Streamlit legacy contract"'), script.index('run_step "Trade isolation contract"'))
        self.assertLess(script.index('run_step "Trade isolation contract"'), script.index('run_step "Motion viewport QA contract"'))
        self.assertLess(script.index('run_step "Motion viewport QA contract"'), script.index('run_step "Diff whitespace check"'))
        self.assertLess(script.index('run_step "Motion browser QA runbook"'), script.index('run_step "Diff whitespace check"'))
        self.assertLess(script.index('run_step "Secret scan"'), script.index('run_step "Secret keyword review contract"'))
        self.assertLess(script.index('run_step "Secret keyword review contract"'), script.index('run_step "Generated artifact scan"'))
        self.assertIn("This script did not push", script)
        self.assertIn("did not call external providers", script)
        self.assertIn("did not execute trades", script)
        self.assertNotIn("gh api", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("git push", script)
        self.assertNotIn("git add .", script)
        self.assertNotIn("tushare_adapter", script)

    def test_data_health_freshness_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/data_health_freshness_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("data_health_freshness_push_gate_contract.v1", script)
        self.assertIn("local_cache_contract_no_provider_execution", script)
        self.assertIn("provider_backed_trade_cal_acceptance_done", script)
        self.assertIn("production_freshness_gate_complete", script)
        self.assertIn("trade_cal_provider_acceptance_runbook", script)
        self.assertIn("trade_cal_provider_acceptance_promotion_audit", script)
        self.assertIn("current_evidence_producer_coverage_audit", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "data_health_freshness_push_gate_contract.v1")
        self.assertEqual(payload["scope"], "local_cache_contract_no_provider_execution")
        self.assertEqual(payload["status"], "data_health_freshness_contract_passed")
        self.assertFalse(payload["provider_backed_trade_cal_acceptance_done"])
        self.assertFalse(payload["production_freshness_gate_complete"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("acceptance_matrix_is_not_provider_acceptance", criteria)
        self.assertIn("provider_runbook_execution_pending", criteria)
        self.assertIn("provider_promotion_audit_is_read_only_pending", criteria)
        self.assertIn("producer_coverage_audit_is_read_only", criteria)

    def test_tushare_acceptance_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/tushare_acceptance_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_tushare_acceptance_contract.v1", script)
        self.assertIn("local_matrix_and_readiness_contract_no_provider_execution", script)
        self.assertIn("provider_backed_acceptance_done", script)
        self.assertIn("production_tushare_pipeline_complete", script)
        self.assertIn("matrix_only_rows_not_verified", script)
        self.assertIn("target_sample_plan_is_plan_only", script)
        self.assertIn("provider_readiness_stays_pending", script)
        self.assertIn("provider_promotion_audit_stays_local_pending", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_tushare_acceptance_contract.v1")
        self.assertEqual(payload["scope"], "local_matrix_and_readiness_contract_no_provider_execution")
        self.assertEqual(payload["status"], "tushare_acceptance_contract_passed")
        self.assertFalse(payload["provider_backed_acceptance_done"])
        self.assertFalse(payload["production_tushare_pipeline_complete"])
        self.assertFalse(payload["full_interface_acceptance_done"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertGreaterEqual(payload["api_count"], 20)
        self.assertEqual(payload["matrix_only_api_count"], payload["api_count"])
        self.assertIn("daily", payload["observed"]["default_core_apis"])
        self.assertIn("trade_cal", payload["observed"]["calendar_apis"])
        self.assertIn("trade_cal", payload["observed"]["parquet_enabled_apis"])
        self.assertEqual(payload["observed"]["provider_readiness_status"], "provider_acceptance_pending")
        self.assertEqual(payload["observed"]["provider_promotion_status"], "provider_acceptance_promotion_pending")
        self.assertGreater(payload["observed"]["provider_promotion_blocker_count"], 0)
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("post_task_catalog_button_gate", criteria)
        self.assertIn("api_acceptance_audit_is_semantic_only", criteria)
        self.assertIn("target_sample_plan_is_plan_only", criteria)
        self.assertIn("provider_readiness_stays_pending", criteria)
        self.assertIn("provider_promotion_audit_stays_local_pending", criteria)

    def test_factor_test_lab_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/factor_test_lab_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_factor_test_lab_contract.v1", script)
        self.assertIn("local_factor_test_lab_contract_no_provider_execution", script)
        self.assertIn("provider_backed_small_pool_validation_done", script)
        self.assertIn("production_factor_test_validation_complete", script)
        self.assertIn("small_pool_acceptance_is_local_only", script)
        self.assertIn("storage_query_consumption_is_not_metric_source", script)
        self.assertIn("local_dataset_sample_evidence_is_not_validation", script)
        self.assertIn("production_validation_qa_stays_pending", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_factor_test_lab_contract.v1")
        self.assertEqual(payload["scope"], "local_factor_test_lab_contract_no_provider_execution")
        self.assertEqual(payload["status"], "factor_test_lab_contract_passed")
        self.assertFalse(payload["provider_backed_small_pool_validation_done"])
        self.assertFalse(payload["full_market_validation_done"])
        self.assertFalse(payload["production_factor_test_validation_complete"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertEqual(payload["observed"]["primary_factor_status"], "research_pass")
        self.assertEqual(payload["observed"]["small_pool_status"], "local_small_pool_acceptance_ready")
        self.assertEqual(
            payload["observed"]["production_qa_status"],
            "production_validation_qa_contract_ready_provider_execution_pending",
        )
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("small_pool_acceptance_is_local_only", criteria)
        self.assertIn("research_states_stay_isolated", criteria)
        self.assertIn("storage_query_consumption_is_not_metric_source", criteria)
        self.assertIn("local_dataset_sample_evidence_is_not_validation", criteria)
        self.assertIn("production_validation_qa_stays_pending", criteria)
        self.assertIn("cache_get_factor_boundary", criteria)
        self.assertIn("cache_get_exposes_local_dataset_sample_boundary", criteria)

    def test_factor_universe_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/factor_universe_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_factor_universe_contract.v1", script)
        self.assertIn("local_factor_universe_contract_no_batch_or_provider_execution", script)
        self.assertIn("production_factor_universe_complete", script)
        self.assertIn("full_pool_validation_done", script)
        self.assertIn("cross_sectional_rank_zscore_done", script)
        self.assertIn("local_rank_zscore_dry_run_is_research_only", script)
        self.assertIn("universe_modes_are_declared_not_executed", script)
        self.assertIn("read_plan_consumes_storage_contracts_only", script)
        self.assertIn("execution_readiness_keeps_production_blockers_visible", script)
        self.assertIn("task_catalog_is_button_gated_read_plan_only", script)
        self.assertIn("frontend_displays_plan_and_does_not_compute_universe", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)
        self.assertNotIn("deepseek_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_factor_universe_contract.v1")
        self.assertEqual(payload["scope"], "local_factor_universe_contract_no_batch_or_provider_execution")
        self.assertEqual(payload["status"], "factor_universe_contract_passed")
        self.assertTrue(payload["read_plan_ready"])
        self.assertTrue(payload["storage_query_contract_consumed"])
        self.assertTrue(payload["worker_task_consumption_plan_ready"])
        self.assertFalse(payload["large_universe_pipeline_done"])
        self.assertFalse(payload["watchlist_pipeline_done"])
        self.assertFalse(payload["custom_pool_pipeline_done"])
        self.assertFalse(payload["full_pool_validation_done"])
        self.assertFalse(payload["cross_sectional_rank_zscore_done"])
        self.assertIn("local_rank_zscore_dry_run_executed", payload)
        self.assertFalse(payload["neutralization_done"])
        self.assertFalse(payload["factor_combination_research_done"])
        self.assertFalse(payload["production_factor_universe_complete"])
        self.assertFalse(payload["partial_pool_is_full_market_proof"])
        self.assertTrue(payload["cache_only"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertFalse(payload["frontend_computes_rank_zscore"])
        self.assertFalse(payload["page_render_starts_full_pool"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertEqual(payload["observed"]["read_plan_status"], "read_plan_ready")
        self.assertEqual(payload["observed"]["requested_universe_mode"], "full_pool")
        self.assertEqual(payload["observed"]["read_plan_dataset_count"], 5)
        self.assertEqual(payload["observed"]["readiness_status"], "read_plan_ready_execution_pending")
        self.assertGreaterEqual(payload["observed"]["readiness_production_blocker_count"], 4)
        self.assertEqual(payload["observed"]["task_backend"], "local_storage_query_read_plan_pipeline")
        self.assertEqual(
            set(payload["observed"]["declared_universe_modes"]),
            {"current_target", "watchlist", "custom_pool", "full_pool"},
        )
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("universe_modes_are_declared_not_executed", criteria)
        self.assertIn("read_plan_consumes_storage_contracts_only", criteria)
        self.assertIn("storage_read_rows_do_not_expose_metric_samples", criteria)
        self.assertIn("execution_readiness_keeps_production_blockers_visible", criteria)
        self.assertIn("local_rank_zscore_dry_run_is_research_only", criteria)
        self.assertIn("task_catalog_is_button_gated_read_plan_only", criteria)
        self.assertIn("frontend_displays_plan_and_does_not_compute_universe", criteria)
        self.assertIn("research_outputs_do_not_enter_action_surfaces", criteria)

    def test_deepseek_governance_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/deepseek_governance_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_deepseek_governance_contract.v1", script)
        self.assertIn("local_deepseek_governance_contract_no_model_call", script)
        self.assertIn("provider_benchmark_done", script)
        self.assertIn("production_deepseek_explanation_complete", script)
        self.assertIn("cache_get_governance_is_manual_default_no_model_call", script)
        self.assertIn("sanitizer_whitelist_discards_action_numeric_fields", script)
        self.assertIn("parse_failed_output_is_discarded_and_hashable", script)
        self.assertIn("json_stability_audit_blocks_production_auto", script)
        self.assertIn("response_format_review_is_local_not_provider_enforcement", script)
        self.assertIn("deepseek_task_is_button_gated_and_config_driven", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)
        self.assertNotIn("deepseek_adapter", script)
        self.assertNotIn("deepseek.chat", script)
        self.assertNotIn("deepseek.com", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_deepseek_governance_contract.v1")
        self.assertEqual(payload["scope"], "local_deepseek_governance_contract_no_model_call")
        self.assertEqual(payload["status"], "deepseek_governance_contract_passed")
        self.assertTrue(payload["manual_explanation_ready"])
        self.assertFalse(payload["provider_benchmark_done"])
        self.assertFalse(payload["larger_benchmark_done"])
        self.assertFalse(payload["response_format_enforced"])
        self.assertFalse(payload["retry_repair_policy_ready"])
        self.assertFalse(payload["auto_after_task_production_ready"])
        self.assertFalse(payload["production_deepseek_explanation_complete"])
        self.assertTrue(payload["sanitizer_only"])
        self.assertTrue(payload["cache_only"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertFalse(payload["contains_secret"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertTrue(payload["does_not_override_numeric_values"])
        self.assertTrue(payload["does_not_output_strategy_action"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertEqual(payload["observed"]["governance_mode"], "manual_only")
        self.assertFalse(payload["observed"]["configured_auto_after_task"])
        self.assertFalse(payload["observed"]["auto_after_task"])
        self.assertEqual(payload["observed"]["model_call_status"], "not_called")
        self.assertEqual(payload["observed"]["json_audit_status"], "manual_ready_production_blocked")
        self.assertEqual(
            payload["observed"]["response_format_status"],
            "response_format_review_ready_provider_enforcement_pending",
        )
        self.assertEqual(payload["observed"]["task_backend"], "guarded_prompt_or_payload_sanitizer")
        self.assertTrue(payload["observed"]["task_button_gated"])
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("cache_get_governance_is_manual_default_no_model_call", criteria)
        self.assertIn("sanitizer_whitelist_discards_action_numeric_fields", criteria)
        self.assertIn("parse_failed_output_is_discarded_and_hashable", criteria)
        self.assertIn("json_stability_audit_blocks_production_auto", criteria)
        self.assertIn("response_format_review_is_local_not_provider_enforcement", criteria)
        self.assertIn("local_builders_match_cache_governance_boundaries", criteria)
        self.assertIn("deepseek_task_is_button_gated_and_config_driven", criteria)

    def test_next_session_map_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/next_session_map_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_next_session_map_contract.v1", script)
        self.assertIn("local_next_session_map_contract_no_browser_no_provider", script)
        self.assertIn("streamlit_parity_complete", script)
        self.assertIn("production_replacement_complete", script)
        self.assertIn("browser_visual_qa_done", script)
        self.assertIn("exact_echarts_payload_has_complete_chart_contract", script)
        self.assertIn("interaction_readiness_is_ready_but_parity_pending", script)
        self.assertIn("chart_contract_is_read_only_no_external_no_action", script)
        self.assertIn("current_get_cache_envelope_is_read_only", script)
        self.assertIn("react_echarts_frontend_uses_api_client_and_read_only_display", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)
        self.assertNotIn("deepseek_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_next_session_map_contract.v1")
        self.assertEqual(payload["scope"], "local_next_session_map_contract_no_browser_no_provider")
        self.assertEqual(payload["status"], "next_session_map_contract_passed")
        self.assertTrue(payload["exact_echarts_payload_ready"])
        self.assertTrue(payload["interaction_contract_ready"])
        self.assertTrue(payload["cache_only"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertTrue(payload["does_not_modify_operation_zones"])
        self.assertFalse(payload["streamlit_parity_complete"])
        self.assertFalse(payload["production_replacement_complete"])
        self.assertFalse(payload["browser_visual_qa_done"])
        self.assertFalse(payload["browser_performance_trace_done"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertFalse(payload["frontend_computes_trade_action"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertEqual(payload["observed"]["exact_chart_status"], "ready")
        self.assertEqual(payload["observed"]["chart_maturity_status"], "ready")
        self.assertEqual(payload["observed"]["interaction_status"], "interaction_contract_ready_parity_pending")
        self.assertEqual(payload["observed"]["interaction_blocking_count"], 0)
        self.assertFalse(payload["observed"]["streamlit_parity_complete"])
        self.assertFalse(payload["observed"]["production_replacement_complete"])
        self.assertGreaterEqual(payload["observed"]["historical_point_count"], 2)
        self.assertGreaterEqual(payload["observed"]["scenario_series_count"], 1)
        self.assertGreaterEqual(payload["observed"]["reference_line_count"], 4)
        self.assertGreaterEqual(payload["observed"]["operation_zone_count"], 1)
        self.assertEqual(payload["observed"]["task_backend"], "local_cache_pipeline")
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("exact_echarts_payload_has_complete_chart_contract", criteria)
        self.assertIn("interaction_readiness_is_ready_but_parity_pending", criteria)
        self.assertIn("chart_contract_is_read_only_no_external_no_action", criteria)
        self.assertIn("reference_zone_position_deepseek_status_are_visible", criteria)
        self.assertIn("current_get_cache_envelope_is_read_only", criteria)
        self.assertIn("next_session_task_is_button_gated_local_cache_pipeline", criteria)
        self.assertIn("react_echarts_frontend_uses_api_client_and_read_only_display", criteria)

    def test_candidate_radar_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/candidate_radar_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_candidate_radar_contract.v1", script)
        self.assertIn("local_candidate_radar_contract_no_provider_execution", script)
        self.assertIn("production_radar_replacement_complete", script)
        self.assertIn("legacy_retirement_ready", script)
        self.assertIn("candidate_is_not_buy_instruction", script)
        self.assertIn("no_feature_loss_is_local_not_replacement", script)
        self.assertIn("replacement_gap_triage_blocks_legacy_retirement", script)
        self.assertIn("priority_explanation_is_local_not_trade_signal", script)
        self.assertIn("full_pool_plan_is_plan_only", script)
        self.assertIn("deep_scan_plan_is_plan_only", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_candidate_radar_contract.v1")
        self.assertEqual(payload["scope"], "local_candidate_radar_contract_no_provider_execution")
        self.assertEqual(payload["status"], "candidate_radar_contract_passed")
        self.assertFalse(payload["production_radar_replacement_complete"])
        self.assertFalse(payload["legacy_retirement_ready"])
        self.assertTrue(payload["legacy_fallback_required"])
        self.assertFalse(payload["full_pool_scan_done"])
        self.assertFalse(payload["deep_scan_done"])
        self.assertFalse(payload["provider_backed_acceptance_done"])
        self.assertFalse(payload["browser_performance_trace_done"])
        self.assertFalse(payload["browser_visual_delta_qa_done"])
        self.assertTrue(payload["candidate_browser_qa_runbook_ready"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertTrue(payload["candidate_is_not_buy_instruction"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertEqual(payload["observed"]["fast_scan_readiness_status"], "fast_scan_local_ready_full_pool_pending")
        self.assertEqual(
            payload["observed"]["no_feature_loss_status"],
            "no_feature_loss_acceptance_local_ready_production_pending",
        )
        self.assertEqual(
            payload["observed"]["replacement_gap_status"],
            "replacement_gap_triage_local_ready_legacy_retirement_blocked",
        )
        self.assertIn(
            payload["observed"]["priority_explanation_status"],
            {"candidate_priority_explanation_ready", "candidate_priority_explanation_empty"},
        )
        self.assertIsNotNone(payload["observed"]["priority_explanation_gap_count"])
        self.assertIsNotNone(payload["observed"]["full_pool_plan_blocker_count"])
        self.assertIsNotNone(payload["observed"]["deep_scan_plan_blocker_count"])
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("cache_get_is_read_only_no_scan", criteria)
        self.assertIn("no_feature_loss_is_local_not_replacement", criteria)
        self.assertIn("replacement_gap_triage_blocks_legacy_retirement", criteria)
        self.assertIn("result_delta_clarity_is_local_not_visual_qa", criteria)
        self.assertIn("priority_explanation_is_local_not_trade_signal", criteria)
        self.assertIn("full_pool_plan_is_plan_only", criteria)
        self.assertIn("deep_scan_plan_is_plan_only", criteria)
        self.assertIn("candidate_browser_qa_runbook_is_local_execution_pending", criteria)

    def test_candidate_radar_browser_qa_runbook_script_is_local_static(self):
        path = Path("scripts/candidate_radar_browser_qa_runbook.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("candidate_radar_browser_qa_runbook.v1", script)
        self.assertIn("local_candidate_radar_browser_qa_runbook_not_browser_execution", script)
        self.assertIn("#candidates", script)
        self.assertIn("motion_browser_qa_runner.mjs", script)
        self.assertIn(".stock_ming_3/motion_qa", script)
        self.assertIn("opens_no_browser", script)
        self.assertIn("writes_no_artifacts", script)
        self.assertIn("visual_qa_complete", script)
        self.assertIn("browser_performance_trace_done", script)
        self.assertIn("production_radar_replacement_complete", script)
        self.assertIn("does_not_execute_trades", script)
        self.assertNotIn("requests.", script)
        self.assertNotIn("httpx.", script)
        self.assertNotIn("subprocess", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)
        self.assertNotIn("deepseek_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "candidate_radar_browser_qa_runbook.v1")
        self.assertEqual(payload["scope"], "local_candidate_radar_browser_qa_runbook_not_browser_execution")
        self.assertEqual(payload["status"], "candidate_radar_browser_qa_runbook_ready_execution_pending")
        self.assertTrue(payload["local_runbook_ready"])
        self.assertTrue(payload["runner_available"])
        self.assertTrue(payload["candidate_route_source_ready"])
        self.assertEqual(payload["candidate_route"], "#candidates")
        self.assertEqual(payload["qa_matrix_count"], 4)
        self.assertFalse(payload["visual_qa_complete"])
        self.assertFalse(payload["browser_performance_trace_done"])
        self.assertFalse(payload["production_radar_replacement_complete"])
        self.assertFalse(payload["legacy_retirement_ready"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["candidate_is_not_buy_instruction"])

    def test_storage_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/storage_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_storage_contract.v1", script)
        self.assertIn("local_storage_contract_no_physical_migration", script)
        self.assertIn("production_storage_complete", script)
        self.assertIn("dry_runs_are_not_production_completion", script)
        self.assertIn("schema_validation_dry_run_writes_no_parquet", script)
        self.assertIn("partition_migration_dry_run_writes_no_parquet", script)
        self.assertIn("compaction_dry_run_rewrites_no_parquet", script)
        self.assertIn("cache_ttl_dry_run_refreshes_no_provider", script)
        self.assertIn("artifact_cleanup_review_deletes_nothing", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_storage_contract.v1")
        self.assertEqual(payload["scope"], "local_storage_contract_no_physical_migration")
        self.assertEqual(payload["status"], "storage_contract_passed")
        self.assertFalse(payload["production_storage_complete"])
        self.assertFalse(payload["physical_schema_validation_done"])
        self.assertFalse(payload["schema_migration_executed"])
        self.assertFalse(payload["dataset_version_manifest_validated"])
        self.assertFalse(payload["partition_migration_executed"])
        self.assertFalse(payload["physical_compaction_executed"])
        self.assertFalse(payload["cache_ttl_refresh_executed"])
        self.assertFalse(payload["artifact_cleanup_delete_executed"])
        self.assertTrue(payload["dry_runs_are_not_production_completion"])
        self.assertTrue(payload["cache_only"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertFalse(payload["writes_parquet_on_get"])
        self.assertTrue(payload["does_not_read_row_payloads"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertEqual(payload["observed"]["dataset_count"], 6)
        self.assertEqual(payload["observed"]["storage_production_blocker_status"], "storage_production_blocked")
        self.assertEqual(payload["observed"]["schema_migration_preflight_status"], "preflight_ready")
        self.assertEqual(payload["observed"]["dataset_version_policy_status"], "policy_ready")
        self.assertEqual(payload["observed"]["schema_validation_status"], "dry_run_completed")
        self.assertEqual(payload["observed"]["partition_migration_status"], "dry_run_completed")
        self.assertEqual(payload["observed"]["compaction_status"], "dry_run_completed")
        self.assertEqual(payload["observed"]["cache_ttl_status"], "dry_run_completed")
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("storage_overview_cache_is_read_only", criteria)
        self.assertIn("production_blocker_audit_keeps_storage_blocked", criteria)
        self.assertIn("dataset_version_policy_is_not_manifest_validation", criteria)
        self.assertIn("schema_validation_dry_run_writes_no_parquet", criteria)
        self.assertIn("partition_migration_dry_run_writes_no_parquet", criteria)
        self.assertIn("compaction_dry_run_rewrites_no_parquet", criteria)
        self.assertIn("cache_ttl_dry_run_refreshes_no_provider", criteria)
        self.assertIn("artifact_cleanup_review_deletes_nothing", criteria)
        self.assertIn("duckdb_query_service_is_read_only", criteria)

    def test_worker_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/worker_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_worker_contract.v1", script)
        self.assertIn("local_worker_contract_no_process_start", script)
        self.assertIn("production_worker_complete", script)
        self.assertIn("healthcheck_executed", script)
        self.assertIn("activation_ready", script)
        self.assertIn("worker_cache_is_diagnostic_only", script)
        self.assertIn("dispatch_plan_is_local_fallback_no_auto_scheduler", script)
        self.assertIn("production_blocker_audit_keeps_worker_blocked", script)
        self.assertIn("healthcheck_contract_is_execution_pending", script)
        self.assertIn("activation_review_keeps_manual_activation_pending", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_worker_contract.v1")
        self.assertEqual(payload["scope"], "local_worker_contract_no_process_start")
        self.assertEqual(payload["status"], "worker_contract_passed")
        self.assertFalse(payload["production_worker_complete"])
        self.assertFalse(payload["worker_started"])
        self.assertFalse(payload["redis_pinged"])
        self.assertFalse(payload["scheduler_started"])
        self.assertFalse(payload["healthcheck_executed"])
        self.assertFalse(payload["healthcheck_task_dispatched"])
        self.assertFalse(payload["activation_ready"])
        self.assertTrue(payload["manual_activation_required"])
        self.assertTrue(payload["local_fallback_available"])
        self.assertTrue(payload["cache_only"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertFalse(payload["contains_secret"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertEqual(payload["observed"]["production_blocker_status"], "production_worker_blocked")
        self.assertEqual(payload["observed"]["healthcheck_status"], "worker_healthcheck_qa_contract_ready_execution_pending")
        self.assertEqual(payload["observed"]["activation_review_status"], "worker_activation_review_ready_activation_pending")
        self.assertEqual(payload["observed"]["scheduler_auto_task_count"], 0)
        self.assertEqual(payload["observed"]["cache_get_external_call_count"], 0)
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("worker_cache_is_diagnostic_only", criteria)
        self.assertIn("runtime_does_not_start_processes", criteria)
        self.assertIn("task_catalog_boundary_is_button_gated", criteria)
        self.assertIn("dispatch_plan_is_local_fallback_no_auto_scheduler", criteria)
        self.assertIn("production_blocker_audit_keeps_worker_blocked", criteria)
        self.assertIn("healthcheck_contract_is_execution_pending", criteria)
        self.assertIn("activation_review_keeps_manual_activation_pending", criteria)

    def test_tauri_desktop_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/tauri_desktop_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_tauri_desktop_contract.v1", script)
        self.assertIn("local_tauri_desktop_contract_no_build_or_runtime_execution", script)
        self.assertIn("production_package_complete", script)
        self.assertIn("packaged_runtime_qa_done", script)
        self.assertIn("tauri_build_executed", script)
        self.assertIn("does_not_run_tauri", script)
        self.assertIn("preflight_cache_is_read_only", script)
        self.assertIn("production_runtime_contract_is_policy_only", script)
        self.assertIn("backend_offline_ux_is_source_contract_only", script)
        self.assertIn("packaged_runtime_qa_stays_pending", script)
        self.assertIn("production_blocker_audit_blocks_completion", script)
        self.assertIn("tauri_task_policy_does_not_run_build_or_runtime", script)
        self.assertIn("frontend_does_not_expose_secrets", script)
        self.assertIn("push_gate_runs_tauri_contract_after_worker", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)
        self.assertNotIn("deepseek_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_tauri_desktop_contract.v1")
        self.assertEqual(payload["scope"], "local_tauri_desktop_contract_no_build_or_runtime_execution")
        self.assertEqual(payload["status"], "tauri_desktop_contract_passed")
        self.assertTrue(payload["preflight_cache_ready"])
        self.assertTrue(payload["runtime_contract_visible"])
        self.assertTrue(payload["backend_offline_ux_contract_visible"])
        self.assertTrue(payload["packaged_runtime_qa_visible"])
        self.assertTrue(payload["cache_only"])
        self.assertTrue(payload["does_not_run_tauri"])
        self.assertTrue(payload["does_not_run_npm"])
        self.assertTrue(payload["does_not_run_cargo"])
        self.assertTrue(payload["does_not_read_config_values"])
        self.assertTrue(payload["does_not_write_logs"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertFalse(payload["production_package_complete"])
        self.assertFalse(payload["tauri_build_executed"])
        self.assertFalse(payload["packaged_runtime_qa_done"])
        self.assertFalse(payload["signing_notarization_done"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertFalse(payload["contains_secret"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertIn(
            payload["observed"]["preflight_status"],
            {"tauri_preflight_ready", "vite_ready_tauri_toolchain_pending", "desktop_scaffold_partial"},
        )
        self.assertEqual(payload["observed"]["production_blocker_status"], "production_package_blocked")
        self.assertEqual(
            payload["observed"]["packaged_runtime_qa_status"],
            "packaged_runtime_qa_contract_ready_validation_pending",
        )
        self.assertEqual(
            payload["observed"]["backend_offline_ux_status"],
            "frontend_offline_notice_ready_packaged_runtime_validation_pending",
        )
        self.assertEqual(
            payload["observed"]["production_runtime_status"],
            "runtime_contract_ready_packaged_validation_pending",
        )
        self.assertFalse(payload["observed"]["tauri_package_build_attempted"])
        self.assertFalse(payload["observed"]["backend_offline_ui_packaged_runtime_verified"])
        self.assertFalse(payload["observed"]["macos_signing_notarization_ready"])
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("preflight_cache_is_read_only", criteria)
        self.assertIn("production_runtime_contract_is_policy_only", criteria)
        self.assertIn("backend_offline_ux_is_source_contract_only", criteria)
        self.assertIn("packaged_runtime_qa_stays_pending", criteria)
        self.assertIn("production_blocker_audit_blocks_completion", criteria)
        self.assertIn("tauri_task_policy_does_not_run_build_or_runtime", criteria)
        self.assertIn("frontend_does_not_expose_secrets", criteria)
        self.assertIn("push_gate_runs_tauri_contract_after_worker", criteria)
        self.assertIn("script_is_local_no_build_or_provider_execution", criteria)

    def test_streamlit_legacy_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/streamlit_legacy_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_streamlit_legacy_contract.v1", script)
        self.assertIn("local_streamlit_legacy_contract_not_streamlit_execution", script)
        self.assertIn("ordinary_workflow_exit_complete", script)
        self.assertIn("full_streamlit_removal_ready", script)
        self.assertIn("streamlit_fallback_retained", script)
        self.assertIn("does_not_open_streamlit", script)
        self.assertIn("legacy_cache_is_read_only", script)
        self.assertIn("streamlit_marked_legacy_not_primary", script)
        self.assertIn("primary_exit_audit_keeps_fallback_required", script)
        self.assertIn("fallback_dependency_contract_keeps_retirement_pending", script)
        self.assertIn("react_legacy_page_displays_boundaries", script)
        self.assertIn("legacy_startup_does_not_autocreate_or_autoexternal", script)
        self.assertIn("push_gate_runs_streamlit_contract_after_tauri", script)
        self.assertNotIn("import streamlit", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)
        self.assertNotIn("deepseek_adapter", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_streamlit_legacy_contract.v1")
        self.assertEqual(payload["scope"], "local_streamlit_legacy_contract_not_streamlit_execution")
        self.assertEqual(payload["status"], "streamlit_legacy_contract_passed")
        self.assertTrue(payload["legacy_cache_ready"])
        self.assertTrue(payload["streamlit_marked_legacy"])
        self.assertTrue(payload["react_tauri_primary_entry"])
        self.assertTrue(payload["streamlit_fallback_retained"])
        self.assertTrue(payload["legacy_fallback_required"])
        self.assertTrue(payload["feature_parity_required_before_removal"])
        self.assertTrue(payload["no_feature_cut_allowed"])
        self.assertTrue(payload["cache_only"])
        self.assertTrue(payload["does_not_open_streamlit"])
        self.assertTrue(payload["does_not_run_legacy_tools"])
        self.assertTrue(payload["does_not_create_tasks"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertFalse(payload["ordinary_workflow_exit_complete"])
        self.assertFalse(payload["streamlit_fallback_removal_ready"])
        self.assertFalse(payload["full_streamlit_removal_ready"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertFalse(payload["contains_secret"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertEqual(
            payload["observed"]["primary_exit_status"],
            "ordinary_workflow_exit_partial_fallback_required",
        )
        self.assertEqual(
            payload["observed"]["fallback_contract_status"],
            "streamlit_fallback_dependencies_visible_retirement_pending",
        )
        self.assertGreater(payload["observed"]["ordinary_workflow_still_needs_fallback_count"], 0)
        self.assertGreater(payload["observed"]["ordinary_fallback_dependency_count"], 0)
        self.assertGreater(payload["observed"]["full_streamlit_removal_blocker_count"], 0)
        self.assertIn("candidate_radar_quick_scan", payload["observed"]["ordinary_blocking_workflows"])
        self.assertIn("legacy_admin_debug_tools", payload["observed"]["full_removal_blocking_workflows"])
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("legacy_cache_is_read_only", criteria)
        self.assertIn("streamlit_marked_legacy_not_primary", criteria)
        self.assertIn("primary_exit_audit_keeps_fallback_required", criteria)
        self.assertIn("fallback_dependency_contract_keeps_retirement_pending", criteria)
        self.assertIn("react_legacy_page_displays_boundaries", criteria)
        self.assertIn("legacy_startup_does_not_autocreate_or_autoexternal", criteria)
        self.assertIn("push_gate_runs_streamlit_contract_after_tauri", criteria)
        self.assertIn("script_is_local_no_streamlit_execution", criteria)

    def test_trade_isolation_contract_script_is_local_push_gate_guard(self):
        path = Path("scripts/trade_isolation_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_trade_isolation_contract.v1", script)
        self.assertIn("local_trade_isolation_contract_no_broker_or_order_execution", script)
        self.assertIn("real_trading_connected", script)
        self.assertIn("broker_adapter_connected", script)
        self.assertIn("order_endpoint_present", script)
        self.assertIn("trade_execution_api_enabled", script)
        self.assertIn("future_real_trading_requires_separate_project", script)
        self.assertIn("risk_cache_is_read_only_no_trade", script)
        self.assertIn("trade_isolation_audit_keeps_real_trading_disabled", script)
        self.assertIn("task_catalog_has_no_trade_execution_routes", script)
        self.assertIn("task_lifecycle_records_no_trade_no_action", script)
        self.assertIn("frontend_trade_boundaries_visible", script)
        self.assertIn("push_gate_runs_trade_isolation_contract_after_streamlit", script)
        self.assertIn("script_is_local_no_broker_or_order_execution", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("subprocess", script)
        self.assertNotIn("api.github.com", script)
        self.assertNotIn("tushare_adapter", script)
        self.assertNotIn("deepseek_adapter", script)
        self.assertNotIn("execute_trade(", script)
        self.assertNotIn("place_order(", script)
        self.assertNotIn("broker.submit(", script)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_trade_isolation_contract.v1")
        self.assertEqual(payload["scope"], "local_trade_isolation_contract_no_broker_or_order_execution")
        self.assertEqual(payload["status"], "trade_isolation_contract_passed")
        self.assertTrue(payload["risk_cache_ready"])
        self.assertTrue(payload["trade_isolation_audit_visible"])
        self.assertEqual(payload["trade_isolation_status"], "trade_isolation_ready")
        self.assertTrue(payload["task_catalog_boundary_visible"])
        self.assertTrue(payload["frontend_boundary_visible"])
        self.assertTrue(payload["push_gate_step_ready"])
        self.assertTrue(payload["cache_only"])
        self.assertFalse(payload["real_trading_connected"])
        self.assertFalse(payload["broker_adapter_connected"])
        self.assertFalse(payload["order_endpoint_present"])
        self.assertFalse(payload["trade_execution_api_enabled"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertTrue(payload["does_not_modify_holdings"])
        self.assertTrue(payload["future_real_trading_requires_separate_project"])
        self.assertFalse(payload["contains_secret"])
        self.assertEqual(payload["blocking_criterion_count"], 0)
        self.assertGreaterEqual(payload["task_boundary_row_count"], 18)
        self.assertEqual(payload["observed"]["trade_isolation_status"], "trade_isolation_ready")
        criteria = {row["criterion"] for row in payload["rows"]}
        self.assertIn("risk_cache_is_read_only_no_trade", criteria)
        self.assertIn("trade_isolation_audit_keeps_real_trading_disabled", criteria)
        self.assertIn("task_catalog_has_no_trade_execution_routes", criteria)
        self.assertIn("task_lifecycle_records_no_trade_no_action", criteria)
        self.assertIn("frontend_trade_boundaries_visible", criteria)
        self.assertIn("push_gate_runs_trade_isolation_contract_after_streamlit", criteria)
        self.assertIn("script_is_local_no_broker_or_order_execution", criteria)
        self.assertIn("future_real_trading_requires_separate_project", criteria)

    def test_secret_keyword_review_contract_is_structured_and_local(self):
        path = Path("scripts/secret_keyword_review_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_secret_keyword_review_contract.v1", script)
        self.assertIn("raw_keyword_lines_emitted", script)
        self.assertIn("outputs_source_line_text", script)
        self.assertIn("category_rows", script)
        self.assertIn("git\", \"grep\"", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("httpx", script)
        self.assertNotIn("api.github.com", script)

        result = subprocess.run(
            [sys.executable, str(path)],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_secret_keyword_review_contract.v1")
        self.assertEqual(payload["scope"], "local_tracked_source_keyword_review_no_raw_line_output")
        self.assertFalse(payload["raw_keyword_lines_emitted"])
        self.assertFalse(payload["outputs_source_line_text"])
        self.assertEqual(payload["high_risk_tracked_value_count"], 0)
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertGreaterEqual(payload["keyword_hit_count"], 1)
        categories = {row["category"] for row in payload["category_rows"]}
        self.assertIn("docs_policy_or_plan", categories)
        self.assertIn("tests_fixture_or_assertion", categories)

    def test_motion_viewport_qa_contract_script_is_local_static(self):
        path = Path("scripts/motion_viewport_qa_contract.py")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_motion_viewport_qa_contract.v1", script)
        self.assertIn("local_static_contract_not_browser_execution", script)
        self.assertIn("motion_viewport_qa_contract_ready_visual_run_pending", script)
        self.assertIn("QA_ROUTES", script)
        self.assertIn("QA_VIEWPORTS", script)
        self.assertIn("#candidates", script)
        self.assertIn("#next", script)
        self.assertIn("#tasks", script)
        self.assertIn("visual_qa_complete", script)
        self.assertIn("browser_performance_verified", script)
        self.assertIn("production_motion_complete", script)
        self.assertIn("explicit_browser_runner_script_available", script)
        self.assertIn("mobile_responsive_motion_layout", script)
        self.assertIn("motion_browser_qa_runner.mjs", script)
        self.assertIn("external_calls_triggered", script)
        self.assertIn("does_not_execute_trades", script)
        self.assertNotIn("requests.", script)
        self.assertNotIn("httpx.", script)
        self.assertNotIn("subprocess", script)
        self.assertNotIn("openai", script.lower())

    def test_motion_browser_qa_runbook_script_is_local_static(self):
        path = Path("scripts/motion_browser_qa_runbook.py")
        script = path.read_text(encoding="utf-8")
        runner_path = Path("scripts/motion_browser_qa_runner.mjs")
        runner = runner_path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_mode & 0o111)
        self.assertTrue(runner_path.exists())
        self.assertTrue(runner_path.stat().st_mode & 0o111)
        self.assertIn("command_center_3_motion_browser_qa_runbook.v1", script)
        self.assertIn("local_browser_qa_runbook_not_browser_execution", script)
        self.assertIn("motion_browser_qa_runbook_ready_execution_pending", script)
        self.assertIn("motion_browser_qa_runner.mjs", script)
        self.assertIn("browser_runner_available", script)
        self.assertIn("runner_executes_only_when_called", script)
        self.assertIn("QA_ROUTES", script)
        self.assertIn("QA_VIEWPORTS", script)
        self.assertIn("VISUAL_ACCEPTANCE_CRITERIA", script)
        self.assertIn("PERFORMANCE_BUDGETS", script)
        self.assertIn("127.0.0.1:5173", script)
        self.assertIn("127.0.0.1:8710", script)
        self.assertIn(".stock_ming_3/motion_qa", script)
        self.assertIn("opens_no_browser", script)
        self.assertIn("writes_no_artifacts", script)
        self.assertIn("external_calls_triggered", script)
        self.assertIn("does_not_execute_trades", script)
        self.assertNotIn("requests.", script)
        self.assertNotIn("httpx.", script)
        self.assertNotIn("subprocess", script)
        self.assertNotIn("openai", script.lower())
        self.assertIn("command_center_3_motion_browser_qa_result.v1", runner)
        self.assertIn("explicit_local_browser_visual_performance_run", runner)
        self.assertIn("chromium.launch", runner)
        self.assertIn("page.goto", runner)
        self.assertIn(".stock_ming_3/motion_qa", runner)
        self.assertIn("starts_no_servers", runner)
        self.assertIn("local_urls_only", runner)
        self.assertIn("external_calls_triggered: false", runner)
        self.assertIn("does_not_execute_trades: true", runner)
        self.assertNotIn("child_process", runner)
        self.assertNotIn("uvicorn", runner)
        self.assertNotIn("npm run dev", runner)
        self.assertNotIn("tushare_adapter", runner)
        self.assertNotIn("deepseek_adapter", runner)
        self.assertNotIn("api.github.com", runner)
        self.assertNotIn("place_order", runner)

        result = subprocess.run(
            [sys.executable, str(path), "--json"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "command_center_3_motion_browser_qa_runbook.v1")
        self.assertEqual(payload["scope"], "local_browser_qa_runbook_not_browser_execution")
        self.assertTrue(payload["local_runbook_ready"])
        self.assertTrue(payload["browser_runner_available"])
        self.assertTrue(payload["runner_executes_only_when_called"])
        self.assertTrue(payload["runner_starts_no_servers"])
        self.assertTrue(payload["runner_writes_ignored_local_artifacts"])
        self.assertEqual(payload["runner_script"], "scripts/motion_browser_qa_runner.mjs")
        self.assertFalse(payload["visual_qa_complete"])
        self.assertFalse(payload["browser_performance_verified"])
        self.assertTrue(payload["opens_no_browser"])
        self.assertTrue(payload["writes_no_artifacts"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertEqual(payload["route_count"], 5)
        self.assertEqual(payload["viewport_count"], 4)
        self.assertEqual(payload["qa_matrix_count"], 20)
        self.assertGreaterEqual(len(payload["performance_budgets"]), 4)

    def test_dev_server_script_prefers_project_python(self):
        path = Path("scripts/dev_server.sh")
        script = path.read_text(encoding="utf-8")

        self.assertTrue(path.exists())
        self.assertIn('PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"', script)
        self.assertIn('if [[ ! -x "$PYTHON_BIN" ]]', script)
        self.assertIn('"$PYTHON_BIN" -m uvicorn server.main:app --reload --port 8710', script)

    def test_next_session_generate_task_writes_exact_cache_packet_without_external_work(self):
        db_path = self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "command_center_next_session_projection_packet": {
                    "packet_key": "command_center_next_session_projection_packet",
                    "status": "ready",
                    "trade_date": "20260610",
                    "chart_render_model": {
                        "historical_series": [{"x": "2026-06-10", "price": 10.4}],
                        "scenario_series": [{"scenario_key": "neutral", "scenario_name": "中性路径", "points": [{"x": "T+1", "price": 10.8}]}],
                        "current_price_line": 10.4,
                        "cost_line": 9.8,
                        "operation_zone_overlays": [{"zone_key": "observe", "price_range": [10.6, 10.9], "action_mode": "condition_only"}],
                    },
                }
            }
        )

        task = next_session_service.create_next_session_task({"ts_code": "002008.SZ", "token": "SHOULD_DROP"})

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "next_session_cache_written_to_sqlite")
        self.assertEqual(task["call_ledger"][0]["api"], "local_next_session_cache")
        self.assertEqual(task["call_ledger"][0]["call_status"], "exact_cache_read")
        self.assertEqual(task["call_ledger"][0]["data_date"], "20260610")
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertTrue(task["call_ledger"][0]["does_not_modify_operation_zones"])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("token", task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_next_session_projection_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["packet_key"], "command_center_next_session_projection_packet")
        self.assertEqual(persisted["status"], "ready")
        self.assertTrue(persisted["does_not_modify_action"])
        self.assertTrue(persisted["does_not_modify_operation_zones"])
        self.assertFalse(persisted["external_calls_triggered"])
        self.assertEqual(persisted["task_call_ledger"][0]["call_status"], "exact_cache_read")
        self.assert_local_ledger_boundary(persisted["task_call_ledger"][0])
        self.assertTrue(persisted["task_call_ledger"][0]["does_not_modify_operation_zones"])

    def test_next_session_generate_task_does_not_persist_cache_missing_packet(self):
        db_path = self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "projection_packet": {
                    "base_date": "2026-06-10",
                    "historical": [{"t": 0, "value": 10.4}],
                    "paths": [{"name": "中性路径", "points": [{"t": 1, "value": 10.8}]}],
                    "status": "ready",
                }
            }
        )

        task = next_session_service.create_next_session_task({"ts_code": "002008.SZ", "api_key": "SHOULD_DROP"})

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "next_session_cache_missing_no_packet_written")
        self.assertEqual(task["call_ledger"][0]["api"], "local_next_session_cache")
        self.assertEqual(task["call_ledger"][0]["call_status"], "cache_missing")
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertTrue(task["call_ledger"][0]["does_not_modify_operation_zones"])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))

        from storage.sqlite_meta import SQLiteMetaStore

        self.assertIsNone(SQLiteMetaStore(db_path).read_packet("command_center_next_session_projection_packet"))

    def test_task_catalog_documents_button_gated_external_boundaries(self):
        catalog = task_service.build_task_catalog()

        self.assertEqual(catalog["packet_key"], "command_center_3_task_catalog")
        self.assertEqual(catalog["task_count"], 16)
        self.assertTrue(catalog["policy"]["get_catalog_cache_only"])
        self.assertTrue(catalog["policy"]["all_tasks_button_gated"])
        self.assertTrue(catalog["policy"]["all_known_post_routes_button_gated"])
        self.assertTrue(catalog["policy"]["call_ledger_required_for_all"])
        self.assertTrue(catalog["policy"]["call_ledger_required_for_all_known_post_routes"])
        self.assertTrue(catalog["policy"]["supports_local_task_cancel"])
        self.assertTrue(catalog["policy"]["retry_policy_audit_ready"])
        self.assertFalse(catalog["policy"]["automatic_retry_enabled"])
        self.assertTrue(catalog["policy"]["manual_retry_requires_post_task"])
        self.assertFalse(catalog["policy"]["cancel_task_external_calls"])
        self.assertFalse(catalog["policy"]["retry_task_external_calls"])
        self.assertTrue(catalog["policy"]["cancel_route_in_lifecycle_catalog"])
        self.assertTrue(catalog["policy"]["retry_route_in_lifecycle_catalog"])
        self.assertFalse(catalog["external_calls_triggered"])
        self.assertFalse(catalog["tushare_called"])
        self.assertFalse(catalog["deepseek_called"])
        self.assertFalse(catalog["github_called"])
        self.assertEqual(catalog["call_ledger"][0]["api"], "local_task_catalog_cache")
        self.assertEqual(catalog["call_ledger"][0]["row_count"], 16)
        self.assertEqual(catalog["call_ledger"][0]["call_status"], "cache_read")
        self.assert_local_ledger_boundary(catalog["call_ledger"][0])
        self.assertIn("GET /api/tasks/catalog", catalog["warnings"][0])
        self.assertTrue(catalog["policy"]["does_not_execute_trades"])
        self.assertTrue(catalog["policy"]["does_not_modify_strategy_action"])
        self.assertEqual(set(catalog["external_sources"]), {"deepseek", "github", "tushare"})
        by_type = {item["task_type"]: item for item in catalog["tasks"]}
        route_coverage = catalog["route_coverage"]
        implementation_status = catalog["implementation_status"]
        retry_policy_summary = catalog["retry_policy_summary"]
        self.assertEqual(route_coverage["known_post_route_count"], 18)
        self.assertEqual(route_coverage["task_creation_route_count"], 16)
        self.assertEqual(route_coverage["local_lifecycle_route_count"], 2)
        self.assertEqual(route_coverage["uncovered_post_routes"], [])
        self.assertTrue(route_coverage["all_known_post_routes_button_gated"])
        self.assertTrue(route_coverage["call_ledger_required_for_all_known_post_routes"])
        self.assertFalse(route_coverage["cancel_routes_external_calls"])
        self.assertFalse(route_coverage["retry_routes_external_calls"])
        self.assertFalse(route_coverage["lifecycle_routes_external_calls"])
        self.assertEqual(implementation_status["status"], "partial_migration")
        self.assertEqual(implementation_status["task_count"], 16)
        self.assertEqual(implementation_status["stub_task_count"], 2)
        self.assertEqual(implementation_status["local_pipeline_task_count"], 13)
        self.assertEqual(implementation_status["guarded_local_task_count"], 1)
        self.assertEqual(implementation_status["implemented_local_task_count"], 14)
        self.assertEqual(implementation_status["external_capable_task_count"], 5)
        self.assertEqual(
            set(implementation_status["stub_task_types"]),
            {"run_chokepoint_scan", "probe_serenity_github"},
        )
        self.assertEqual(
            set(implementation_status["local_pipeline_task_types"]),
            {
                "refresh_tushare_facts",
                "refresh_factor_data",
                "run_factor_light",
                "run_factor_universe_research_plan",
                "build_next_session_projection",
                "run_candidate_radar_quick_scan",
                "run_candidate_radar_full_pool_plan",
                "run_candidate_radar_deep_scan_plan",
                "run_storage_artifact_cleanup_dry_run",
                "run_storage_schema_validation_dry_run",
                "run_storage_partition_migration_dry_run",
                "run_storage_compaction_dry_run",
                "run_storage_cache_ttl_dry_run",
            },
        )
        self.assertEqual(implementation_status["guarded_local_task_types"], ["run_deepseek_factor_explanation"])
        self.assertEqual(
            set(implementation_status["implemented_local_task_types"]),
            {
                "refresh_tushare_facts",
                "refresh_factor_data",
                "run_factor_light",
                "run_factor_universe_research_plan",
                "build_next_session_projection",
                "run_candidate_radar_quick_scan",
                "run_candidate_radar_full_pool_plan",
                "run_candidate_radar_deep_scan_plan",
                "run_storage_artifact_cleanup_dry_run",
                "run_storage_schema_validation_dry_run",
                "run_storage_partition_migration_dry_run",
                "run_storage_compaction_dry_run",
                "run_storage_cache_ttl_dry_run",
                "run_deepseek_factor_explanation",
            },
        )
        self.assertTrue(implementation_status["all_external_capable_tasks_are_button_gated"])
        self.assertTrue(implementation_status["all_external_capable_tasks_require_call_ledger"])
        self.assertIn("local_fallback_stub", implementation_status["backend_counts"])
        self.assertTrue(catalog["policy"]["implementation_status_is_read_only"])
        self.assertTrue(catalog["policy"]["stub_tasks_must_not_be_reported_as_complete"])
        self.assertIn("误读为完整生产迁移", implementation_status["note"])
        self.assertEqual(retry_policy_summary["status"], "audit_ready")
        self.assertFalse(retry_policy_summary["auto_retry_enabled"])
        self.assertTrue(retry_policy_summary["manual_retry_supported"])
        self.assertTrue(retry_policy_summary["manual_retry_requires_new_task_id"])
        self.assertFalse(retry_policy_summary["cache_api_can_retry"])
        self.assertEqual(set(retry_policy_summary["task_policies"]), set(by_type))
        self.assertIn("POST /api/tasks/{task_id}/cancel", route_coverage["known_post_routes"])
        self.assertIn("POST /api/tasks/{task_id}/retry", route_coverage["known_post_routes"])
        self.assertEqual(catalog["task_lifecycle_routes"][0]["route"], "POST /api/tasks/{task_id}/cancel")
        self.assertEqual(catalog["task_lifecycle_routes"][0]["external_call_policy"], "local_cancel_no_external_call")
        self.assertEqual(catalog["task_lifecycle_routes"][1]["route"], "POST /api/tasks/{task_id}/retry")
        self.assertEqual(catalog["task_lifecycle_routes"][1]["external_call_policy"], "local_retry_no_external_call")
        self.assertEqual(by_type["refresh_tushare_facts"]["route"], "POST /api/tasks/refresh-tushare-facts")
        self.assertEqual(by_type["refresh_tushare_facts"]["current_backend"], "button_gated_tushare_pipeline")
        self.assertFalse(by_type["refresh_tushare_facts"]["retry_policy"]["auto_retry_enabled"])
        self.assertTrue(by_type["refresh_tushare_facts"]["retry_policy"]["manual_retry_allowed"])
        self.assertFalse(by_type["refresh_tushare_facts"]["retry_policy"]["manual_retry_eligible"])
        self.assertEqual(by_type["refresh_tushare_facts"]["retry_policy"]["max_attempts"], 3)
        self.assertEqual(by_type["refresh_tushare_facts"]["lock_policy"]["lock_scope"], "task_type_payload")
        self.assertFalse(by_type["refresh_tushare_facts"]["lock_policy"]["lock_enforced"])
        self.assertTrue(by_type["refresh_tushare_facts"]["lock_policy"]["lock_enforcement_enabled"])
        self.assertFalse(by_type["refresh_tushare_facts"]["lock_policy"]["audit_only"])
        self.assertTrue(by_type["refresh_tushare_facts"]["lock_policy"]["conflict_detection_enabled"])
        self.assertFalse(by_type["refresh_tushare_facts"]["lock_policy"]["cache_api_can_acquire_lock"])
        self.assertTrue(by_type["refresh_tushare_facts"]["lock_policy"]["auto_blocks_task_creation"])
        self.assertEqual(by_type["refresh_tushare_facts"]["dedupe_policy"]["dedupe_scope"], "task_type_payload")
        self.assertTrue(by_type["refresh_tushare_facts"]["dedupe_policy"]["duplicate_detection_enabled"])
        self.assertTrue(by_type["refresh_tushare_facts"]["dedupe_policy"]["dispatch_dedupe_enabled"])
        self.assertFalse(by_type["refresh_tushare_facts"]["dedupe_policy"]["dispatch_dedupe_enforced"])
        self.assertFalse(by_type["refresh_tushare_facts"]["dedupe_policy"]["audit_only"])
        self.assertFalse(by_type["refresh_tushare_facts"]["dedupe_policy"]["cache_api_can_dedupe"])
        self.assertTrue(by_type["refresh_tushare_facts"]["dedupe_policy"]["auto_blocks_task_creation"])
        self.assertIn("tushare", by_type["refresh_tushare_facts"]["possible_external_sources"])
        self.assertEqual(by_type["refresh_tushare_facts"]["default_core_apis"], ["daily", "daily_basic", "moneyflow"])
        self.assertEqual(by_type["refresh_tushare_facts"]["calendar_apis"], ["trade_cal"])
        self.assertIn("limit_cpt_list", by_type["refresh_tushare_facts"]["optional_extended_apis"])
        self.assertIn("top_list", by_type["refresh_tushare_facts"]["optional_extended_apis"])
        self.assertIn("top_inst", by_type["refresh_tushare_facts"]["optional_extended_apis"])
        self.assertIn("fina_indicator", by_type["refresh_tushare_facts"]["optional_extended_apis"])
        self.assertIn("stk_surv", by_type["refresh_tushare_facts"]["optional_extended_apis"])
        self.assertEqual(by_type["refresh_tushare_facts"]["parquet_enabled_apis"], ["daily", "daily_basic", "moneyflow", "trade_cal"])
        self.assertIn("unselected APIs are capability matrix only", by_type["refresh_tushare_facts"]["api_validation_matrix_policy"])
        self.assertIn("call_ledger_required_fields", by_type["refresh_tushare_facts"]["api_acceptance_audit_contract"])
        self.assertIn("permission_denied", by_type["refresh_tushare_facts"]["failure_mode_qa_contract"])
        self.assertIn("missing_required_parameter", by_type["refresh_tushare_facts"]["failure_mode_qa_contract"])
        self.assertFalse(by_type["refresh_tushare_facts"]["failure_mode_qa_is_provider_acceptance"])
        self.assertIn("ts_code preflight", by_type["refresh_tushare_facts"]["request_parameter_qa_contract"])
        self.assertIn("date context params", by_type["refresh_tushare_facts"]["request_parameter_qa_contract"])
        self.assertFalse(by_type["refresh_tushare_facts"]["request_parameter_qa_is_provider_acceptance"])
        self.assertIn("target-domain sample windows", by_type["refresh_tushare_facts"]["provider_target_sample_plan_contract"])
        self.assertFalse(by_type["refresh_tushare_facts"]["provider_target_sample_plan_is_provider_acceptance"])
        self.assertFalse(by_type["refresh_tushare_facts"]["full_interface_acceptance_done"])
        self.assertFalse(by_type["refresh_tushare_facts"]["cache_get_external_calls"])
        self.assertEqual(by_type["refresh_factor_data"]["route"], "POST /api/factor-quant/refresh-data")
        self.assertEqual(by_type["refresh_factor_data"]["current_backend"], "button_gated_tushare_pipeline")
        self.assertIn("tushare", by_type["refresh_factor_data"]["possible_external_sources"])
        self.assertEqual(by_type["refresh_factor_data"]["calendar_apis"], ["trade_cal"])
        self.assertIn("fina_indicator", by_type["refresh_factor_data"]["optional_extended_apis"])
        self.assertEqual(by_type["refresh_factor_data"]["parquet_enabled_apis"], ["daily", "daily_basic", "moneyflow", "trade_cal"])
        self.assertIn("call_ledger semantic audit", by_type["refresh_factor_data"]["api_acceptance_audit_contract"])
        self.assertIn("failure_mode_qa_contract", by_type["refresh_factor_data"]["failure_mode_qa_contract"])
        self.assertFalse(by_type["refresh_factor_data"]["failure_mode_qa_is_provider_acceptance"])
        self.assertIn("request_parameter_qa_contract", by_type["refresh_factor_data"]["request_parameter_qa_contract"])
        self.assertFalse(by_type["refresh_factor_data"]["request_parameter_qa_is_provider_acceptance"])
        self.assertIn("provider_target_sample_plan_contract", by_type["refresh_factor_data"]["provider_target_sample_plan_contract"])
        self.assertFalse(by_type["refresh_factor_data"]["provider_target_sample_plan_is_provider_acceptance"])
        self.assertFalse(by_type["refresh_factor_data"]["full_interface_acceptance_done"])
        self.assertFalse(by_type["refresh_factor_data"]["cache_get_external_calls"])
        self.assertIn("deepseek", by_type["run_deepseek_factor_explanation"]["possible_external_sources"])
        self.assertEqual(by_type["run_deepseek_factor_explanation"]["deepseek_model_strategy_purpose"], "factor_explain")
        self.assertIn("DEEPSEEK_EXPLAIN_MODEL", by_type["run_deepseek_factor_explanation"]["deepseek_model_config_keys"])
        self.assertTrue(by_type["run_deepseek_factor_explanation"]["does_not_hardcode_deepseek_model"])
        factor_strategy = by_type["run_deepseek_factor_explanation"]["deepseek_model_strategy"]
        self.assertEqual(factor_strategy["purpose"], "factor_explain")
        self.assertIn("DEEPSEEK_EXPLAIN_MODEL", factor_strategy["config_keys"])
        self.assertTrue(factor_strategy["does_not_hardcode_model"])
        self.assertFalse(factor_strategy["contains_secret"])
        self.assertFalse(factor_strategy["external_call_on_cache_read"])
        self.assertIn("github", by_type["probe_serenity_github"]["possible_external_sources"])
        self.assertEqual(by_type["run_chokepoint_scan"]["deepseek_model_strategy_purpose"], "explain")
        self.assertIn("DEEPSEEK_EXPLAIN_MODEL", by_type["run_chokepoint_scan"]["deepseek_model_config_keys"])
        self.assertTrue(by_type["run_chokepoint_scan"]["does_not_hardcode_deepseek_model"])
        chokepoint_strategy = by_type["run_chokepoint_scan"]["deepseek_model_strategy"]
        self.assertEqual(chokepoint_strategy["purpose"], "explain")
        self.assertIn("DEEPSEEK_EXPLAIN_MODEL", chokepoint_strategy["config_keys"])
        self.assertTrue(chokepoint_strategy["does_not_hardcode_model"])
        self.assertFalse(chokepoint_strategy["contains_secret"])
        self.assertFalse(chokepoint_strategy["external_call_on_cache_read"])
        self.assertEqual(by_type["run_factor_light"]["possible_external_sources"], [])
        self.assertEqual(by_type["run_factor_light"]["universe_modes"], ["current_target"])
        self.assertEqual(by_type["run_factor_light"]["future_universe_modes"], ["watchlist", "custom_pool", "full_pool"])
        self.assertEqual(
            by_type["run_factor_light"]["factor_universe_contract_status"],
            "current_target_only_local_light_pipeline",
        )
        self.assertTrue(by_type["run_factor_light"]["full_pool_requires_worker"])
        self.assertFalse(by_type["run_factor_light"]["frontend_computes_rank_zscore"])
        self.assertFalse(by_type["run_factor_light"]["page_render_starts_full_pool"])
        self.assertFalse(by_type["run_factor_light"]["partial_pool_is_full_market_proof"])
        self.assertEqual(by_type["run_factor_universe_research_plan"]["route"], "POST /api/factor-quant/universe-research-plan")
        self.assertEqual(by_type["run_factor_universe_research_plan"]["possible_external_sources"], [])
        self.assertEqual(by_type["run_factor_universe_research_plan"]["universe_modes"], ["watchlist", "custom_pool", "full_pool"])
        self.assertEqual(
            by_type["run_factor_universe_research_plan"]["external_call_policy"],
            "local_storage_query_contract_only_no_external_call",
        )
        self.assertTrue(by_type["run_factor_universe_research_plan"]["storage_query_contract_consumed"])
        self.assertTrue(by_type["run_factor_universe_research_plan"]["worker_task_consumption_plan_ready"])
        self.assertFalse(by_type["run_factor_universe_research_plan"]["large_universe_pipeline_done"])
        self.assertFalse(by_type["run_factor_universe_research_plan"]["full_pool_validation_done"])
        self.assertTrue(by_type["run_factor_universe_research_plan"]["full_pool_requires_worker"])
        self.assertFalse(by_type["run_factor_universe_research_plan"]["frontend_computes_rank_zscore"])
        self.assertFalse(by_type["run_factor_universe_research_plan"]["page_render_starts_full_pool"])
        self.assertFalse(by_type["run_factor_universe_research_plan"]["partial_pool_is_full_market_proof"])
        self.assertFalse(by_type["run_factor_universe_research_plan"]["cache_get_external_calls"])
        self.assertTrue(by_type["run_factor_universe_research_plan"]["call_ledger_required"])
        self.assertEqual(by_type["build_next_session_projection"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["build_next_session_projection"]["possible_external_sources"], [])
        self.assertEqual(by_type["run_candidate_radar_quick_scan"]["route"], "POST /api/candidate-radar/scan-quick")
        self.assertEqual(by_type["run_candidate_radar_quick_scan"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["run_candidate_radar_quick_scan"]["possible_external_sources"], [])
        self.assertEqual(by_type["run_candidate_radar_quick_scan"]["external_call_policy"], "local_cache_only_current_mvp")
        self.assertFalse(by_type["run_candidate_radar_quick_scan"]["cache_get_external_calls"])
        self.assertEqual(
            by_type["run_candidate_radar_quick_scan"]["scan_modes"],
            ["quick_cache_scan", "watchlist_scan", "custom_pool_scan"],
        )
        self.assertTrue(by_type["run_candidate_radar_quick_scan"]["runtime_budget_contract_visible"])
        self.assertTrue(by_type["run_candidate_radar_quick_scan"]["result_delta_clarity_contract_visible"])
        self.assertFalse(by_type["run_candidate_radar_quick_scan"]["result_delta_clarity_is_previous_cache_diff"])
        self.assertTrue(by_type["run_candidate_radar_quick_scan"]["result_delta_clarity_previous_cache_diff_supported"])
        self.assertTrue(by_type["run_candidate_radar_quick_scan"]["result_delta_clarity_previous_cache_diff_requires_persisted_cache"])
        self.assertFalse(by_type["run_candidate_radar_quick_scan"]["result_delta_clarity_is_browser_visual_qa"])
        self.assertEqual(by_type["run_candidate_radar_quick_scan"]["sync_candidate_display_limit"], 120)
        self.assertEqual(by_type["run_candidate_radar_quick_scan"]["local_pool_input_limit"], 50)
        self.assertTrue(by_type["run_candidate_radar_quick_scan"]["large_universe_requires_worker"])
        self.assertIn("full_pool_scan", by_type["run_candidate_radar_quick_scan"]["future_scan_modes"])
        self.assertEqual(by_type["run_candidate_radar_full_pool_plan"]["route"], "POST /api/candidate-radar/full-pool-plan")
        self.assertEqual(by_type["run_candidate_radar_full_pool_plan"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["run_candidate_radar_full_pool_plan"]["possible_external_sources"], [])
        self.assertEqual(
            by_type["run_candidate_radar_full_pool_plan"]["external_call_policy"],
            "local_full_pool_plan_only_no_external_call",
        )
        self.assertEqual(by_type["run_candidate_radar_full_pool_plan"]["scan_modes"], ["full_pool_scan"])
        self.assertTrue(by_type["run_candidate_radar_full_pool_plan"]["plan_only"])
        self.assertFalse(by_type["run_candidate_radar_full_pool_plan"]["full_pool_scan_done"])
        self.assertFalse(by_type["run_candidate_radar_full_pool_plan"]["full_pool_validation_done"])
        self.assertTrue(by_type["run_candidate_radar_full_pool_plan"]["result_delta_clarity_contract_visible"])
        self.assertFalse(by_type["run_candidate_radar_full_pool_plan"]["result_delta_clarity_is_previous_cache_diff"])
        self.assertTrue(by_type["run_candidate_radar_full_pool_plan"]["result_delta_clarity_previous_cache_diff_supported"])
        self.assertTrue(by_type["run_candidate_radar_full_pool_plan"]["result_delta_clarity_previous_cache_diff_requires_persisted_cache"])
        self.assertFalse(by_type["run_candidate_radar_full_pool_plan"]["result_delta_clarity_is_browser_visual_qa"])
        self.assertTrue(by_type["run_candidate_radar_full_pool_plan"]["worker_task_consumption_plan_ready"])
        self.assertFalse(by_type["run_candidate_radar_full_pool_plan"]["cache_get_external_calls"])
        self.assertFalse(by_type["run_candidate_radar_full_pool_plan"]["page_render_starts_full_pool"])
        self.assertFalse(by_type["run_candidate_radar_full_pool_plan"]["provider_refresh_executed"])
        self.assertFalse(by_type["run_candidate_radar_full_pool_plan"]["candidate_scoring_executed"])
        self.assertTrue(by_type["run_candidate_radar_full_pool_plan"]["candidate_is_not_buy_instruction"])
        self.assertTrue(by_type["run_candidate_radar_full_pool_plan"]["call_ledger_required"])
        self.assertEqual(by_type["run_candidate_radar_deep_scan_plan"]["route"], "POST /api/candidate-radar/deep-scan-plan")
        self.assertEqual(by_type["run_candidate_radar_deep_scan_plan"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["run_candidate_radar_deep_scan_plan"]["possible_external_sources"], [])
        self.assertEqual(
            by_type["run_candidate_radar_deep_scan_plan"]["external_call_policy"],
            "local_deep_scan_readiness_plan_only_no_external_call",
        )
        self.assertEqual(by_type["run_candidate_radar_deep_scan_plan"]["scan_modes"], ["deep_scan"])
        self.assertTrue(by_type["run_candidate_radar_deep_scan_plan"]["plan_only"])
        self.assertFalse(by_type["run_candidate_radar_deep_scan_plan"]["deep_scan_done"])
        self.assertFalse(by_type["run_candidate_radar_deep_scan_plan"]["deep_scan_validation_done"])
        self.assertTrue(by_type["run_candidate_radar_deep_scan_plan"]["result_delta_clarity_contract_visible"])
        self.assertFalse(by_type["run_candidate_radar_deep_scan_plan"]["result_delta_clarity_is_previous_cache_diff"])
        self.assertTrue(by_type["run_candidate_radar_deep_scan_plan"]["result_delta_clarity_previous_cache_diff_supported"])
        self.assertTrue(by_type["run_candidate_radar_deep_scan_plan"]["result_delta_clarity_previous_cache_diff_requires_persisted_cache"])
        self.assertFalse(by_type["run_candidate_radar_deep_scan_plan"]["result_delta_clarity_is_browser_visual_qa"])
        self.assertTrue(by_type["run_candidate_radar_deep_scan_plan"]["worker_task_consumption_plan_ready"])
        self.assertFalse(by_type["run_candidate_radar_deep_scan_plan"]["cache_get_external_calls"])
        self.assertFalse(by_type["run_candidate_radar_deep_scan_plan"]["page_render_starts_deep_scan"])
        self.assertFalse(by_type["run_candidate_radar_deep_scan_plan"]["provider_refresh_executed"])
        self.assertFalse(by_type["run_candidate_radar_deep_scan_plan"]["deepseek_called"])
        self.assertFalse(by_type["run_candidate_radar_deep_scan_plan"]["candidate_scoring_executed"])
        self.assertTrue(by_type["run_candidate_radar_deep_scan_plan"]["feature_loss_gaps_visible"])
        self.assertTrue(by_type["run_candidate_radar_deep_scan_plan"]["candidate_is_not_buy_instruction"])
        self.assertTrue(by_type["run_candidate_radar_deep_scan_plan"]["call_ledger_required"])
        self.assertEqual(by_type["run_storage_artifact_cleanup_dry_run"]["route"], "POST /api/storage/artifact-hygiene/dry-run")
        self.assertEqual(by_type["run_storage_artifact_cleanup_dry_run"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["run_storage_artifact_cleanup_dry_run"]["possible_external_sources"], [])
        self.assertEqual(by_type["run_storage_artifact_cleanup_dry_run"]["external_call_policy"], "local_dry_run_no_delete_no_external_call")
        self.assertEqual(by_type["run_storage_artifact_cleanup_dry_run"]["cleanup_policy"], "dry_run_only_no_delete")
        self.assertTrue(by_type["run_storage_artifact_cleanup_dry_run"]["artifact_cleanup_review_contract_visible"])
        self.assertTrue(by_type["run_storage_artifact_cleanup_dry_run"]["manual_delete_requires_separate_approval"])
        self.assertTrue(by_type["run_storage_artifact_cleanup_dry_run"]["cleanup_review_is_not_delete_execution"])
        self.assertFalse(by_type["run_storage_artifact_cleanup_dry_run"]["safe_delete_command_generated"])
        self.assertFalse(by_type["run_storage_artifact_cleanup_dry_run"]["production_cleanup_complete"])
        self.assertFalse(by_type["run_storage_artifact_cleanup_dry_run"]["cache_get_external_calls"])
        self.assertFalse(by_type["run_storage_artifact_cleanup_dry_run"]["delete_files_on_post"])
        self.assertFalse(by_type["run_storage_artifact_cleanup_dry_run"]["reads_file_payloads"])
        self.assertFalse(by_type["run_storage_artifact_cleanup_dry_run"]["reads_env_files"])
        self.assertTrue(by_type["run_storage_artifact_cleanup_dry_run"]["call_ledger_required"])
        self.assertEqual(by_type["run_storage_schema_validation_dry_run"]["route"], "POST /api/storage/schema-validation/dry-run")
        self.assertEqual(by_type["run_storage_schema_validation_dry_run"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["run_storage_schema_validation_dry_run"]["possible_external_sources"], [])
        self.assertEqual(
            by_type["run_storage_schema_validation_dry_run"]["external_call_policy"],
            "local_schema_metadata_only_no_external_call",
        )
        self.assertEqual(
            by_type["run_storage_schema_validation_dry_run"]["validation_policy"],
            "dry_run_only_no_migration_no_parquet_write",
        )
        self.assertFalse(by_type["run_storage_schema_validation_dry_run"]["cache_get_external_calls"])
        self.assertFalse(by_type["run_storage_schema_validation_dry_run"]["writes_parquet_on_post"])
        self.assertFalse(by_type["run_storage_schema_validation_dry_run"]["reads_row_payloads"])
        self.assertFalse(by_type["run_storage_schema_validation_dry_run"]["reads_env_files"])
        self.assertFalse(by_type["run_storage_schema_validation_dry_run"]["schema_migration_executed"])
        self.assertTrue(by_type["run_storage_schema_validation_dry_run"]["call_ledger_required"])
        self.assertEqual(by_type["run_storage_partition_migration_dry_run"]["route"], "POST /api/storage/partition-migration/dry-run")
        self.assertEqual(by_type["run_storage_partition_migration_dry_run"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["run_storage_partition_migration_dry_run"]["possible_external_sources"], [])
        self.assertEqual(
            by_type["run_storage_partition_migration_dry_run"]["external_call_policy"],
            "local_partition_plan_only_no_external_call",
        )
        self.assertEqual(
            by_type["run_storage_partition_migration_dry_run"]["partition_policy"],
            "dry_run_only_no_partition_write_no_migration",
        )
        self.assertFalse(by_type["run_storage_partition_migration_dry_run"]["cache_get_external_calls"])
        self.assertFalse(by_type["run_storage_partition_migration_dry_run"]["writes_parquet_on_post"])
        self.assertFalse(by_type["run_storage_partition_migration_dry_run"]["reads_row_payloads"])
        self.assertFalse(by_type["run_storage_partition_migration_dry_run"]["reads_env_files"])
        self.assertFalse(by_type["run_storage_partition_migration_dry_run"]["partition_migration_executed"])
        self.assertTrue(by_type["run_storage_partition_migration_dry_run"]["call_ledger_required"])
        self.assertEqual(by_type["run_storage_compaction_dry_run"]["route"], "POST /api/storage/compaction/dry-run")
        self.assertEqual(by_type["run_storage_compaction_dry_run"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["run_storage_compaction_dry_run"]["possible_external_sources"], [])
        self.assertEqual(
            by_type["run_storage_compaction_dry_run"]["external_call_policy"],
            "local_compaction_plan_only_no_external_call",
        )
        self.assertEqual(
            by_type["run_storage_compaction_dry_run"]["compaction_policy"],
            "dry_run_only_no_parquet_rewrite",
        )
        self.assertFalse(by_type["run_storage_compaction_dry_run"]["cache_get_external_calls"])
        self.assertFalse(by_type["run_storage_compaction_dry_run"]["writes_parquet_on_post"])
        self.assertFalse(by_type["run_storage_compaction_dry_run"]["reads_row_payloads"])
        self.assertFalse(by_type["run_storage_compaction_dry_run"]["reads_env_files"])
        self.assertFalse(by_type["run_storage_compaction_dry_run"]["physical_compaction_executed"])
        self.assertTrue(by_type["run_storage_compaction_dry_run"]["call_ledger_required"])
        self.assertEqual(by_type["run_storage_cache_ttl_dry_run"]["route"], "POST /api/storage/cache-ttl/dry-run")
        self.assertEqual(by_type["run_storage_cache_ttl_dry_run"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["run_storage_cache_ttl_dry_run"]["possible_external_sources"], [])
        self.assertEqual(
            by_type["run_storage_cache_ttl_dry_run"]["external_call_policy"],
            "local_ttl_plan_only_no_external_call",
        )
        self.assertEqual(
            by_type["run_storage_cache_ttl_dry_run"]["ttl_policy"],
            "dry_run_only_no_refresh_no_external_call",
        )
        self.assertFalse(by_type["run_storage_cache_ttl_dry_run"]["cache_get_external_calls"])
        self.assertFalse(by_type["run_storage_cache_ttl_dry_run"]["refreshes_external_sources_on_post"])
        self.assertFalse(by_type["run_storage_cache_ttl_dry_run"]["writes_parquet_on_post"])
        self.assertFalse(by_type["run_storage_cache_ttl_dry_run"]["reads_row_payloads"])
        self.assertFalse(by_type["run_storage_cache_ttl_dry_run"]["reads_env_files"])
        self.assertFalse(by_type["run_storage_cache_ttl_dry_run"]["refresh_executed"])
        self.assertTrue(by_type["run_storage_cache_ttl_dry_run"]["call_ledger_required"])

    def test_task_catalog_covers_all_fastapi_post_routes(self):
        catalog = task_service.build_task_catalog()
        route_coverage = catalog["route_coverage"]
        discovered_routes = self._discover_fastapi_post_routes()

        self.assertEqual(sorted(route_coverage["known_post_routes"]), discovered_routes)
        self.assertEqual(route_coverage["known_post_route_count"], len(discovered_routes))
        self.assertEqual(route_coverage["uncovered_post_routes"], [])
        self.assertTrue(route_coverage["all_known_post_routes_button_gated"])
        self.assertTrue(route_coverage["call_ledger_required_for_all_known_post_routes"])
        self.assertIn("POST /api/tasks/{task_id}/cancel", discovered_routes)
        self.assertIn("POST /api/tasks/refresh-tushare-facts", discovered_routes)
        self.assertIn("POST /api/factor-quant/run-light", discovered_routes)
        self.assertIn("POST /api/factor-quant/universe-research-plan", discovered_routes)
        self.assertIn("POST /api/factor-quant/deepseek-explain", discovered_routes)
        self.assertIn("POST /api/candidate-radar/scan-quick", discovered_routes)
        self.assertIn("POST /api/candidate-radar/full-pool-plan", discovered_routes)
        self.assertIn("POST /api/candidate-radar/deep-scan-plan", discovered_routes)
        self.assertIn("POST /api/storage/artifact-hygiene/dry-run", discovered_routes)
        self.assertIn("POST /api/storage/schema-validation/dry-run", discovered_routes)
        self.assertIn("POST /api/storage/partition-migration/dry-run", discovered_routes)
        self.assertIn("POST /api/storage/compaction/dry-run", discovered_routes)
        self.assertIn("POST /api/storage/cache-ttl/dry-run", discovered_routes)

    def test_worker_runtime_cache_reads_local_scaffold_without_starting_backends(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        packet = worker_service.read_worker_runtime_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_worker_runtime_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertTrue(packet["runtime"]["local_fallback_enabled"])
        self.assertFalse(packet["runtime"]["celery_worker_started"])
        self.assertFalse(packet["runtime"]["scheduler_started"])
        self.assertFalse(packet["runtime"]["redis_pinged"])
        self.assertFalse(packet["runtime"]["redis_url_exposed"])
        self.assertEqual(packet["task_catalog_summary"]["task_count"], task_service.build_task_catalog()["task_count"])
        self.assertTrue(packet["task_catalog_summary"]["all_tasks_button_gated"])
        self.assertTrue(packet["task_catalog_summary"]["call_ledger_required_for_all"])
        self.assertEqual(packet["task_catalog_summary"]["implementation_status"], "partial_migration")
        self.assertEqual(packet["task_catalog_summary"]["stub_task_count"], 2)
        self.assertEqual(packet["task_catalog_summary"]["local_pipeline_task_count"], 13)
        self.assertEqual(packet["task_catalog_summary"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["task_catalog_summary"]["implemented_local_task_count"], 14)
        self.assertEqual(packet["task_catalog_summary"]["retry_policy_status"], "audit_ready")
        self.assertFalse(packet["task_catalog_summary"]["auto_retry_enabled"])
        self.assertEqual(packet["task_implementation_status"]["status"], "partial_migration")
        self.assertEqual(packet["task_implementation_status"]["stub_task_count"], 2)
        self.assertEqual(packet["task_implementation_status"]["local_pipeline_task_count"], 13)
        self.assertEqual(packet["task_implementation_status"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["task_implementation_status"]["implemented_local_task_count"], 14)
        self.assertIn("refresh_tushare_facts", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("refresh_factor_data", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_factor_light", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_factor_universe_research_plan", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_candidate_radar_full_pool_plan", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_candidate_radar_deep_scan_plan", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_storage_schema_validation_dry_run", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_storage_partition_migration_dry_run", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_storage_compaction_dry_run", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_storage_cache_ttl_dry_run", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_deepseek_factor_explanation", packet["task_implementation_status"]["guarded_local_task_types"])
        self.assertIn("task_retry_policy_summary", packet)
        self.assertEqual(packet["task_retry_policy_summary"]["status"], "audit_ready")
        self.assertFalse(packet["task_retry_policy_summary"]["auto_retry_enabled"])
        self.assertTrue(packet["task_retry_policy_summary"]["manual_retry_supported"])
        self.assertFalse(packet["task_retry_policy_summary"]["cache_api_can_retry"])
        self.assertEqual(packet["task_status_summary"]["packet_key"], "command_center_3_task_status_index")
        self.assertIn("status_counts", packet["task_status_summary"])
        self.assertIn("call_ledger_count", packet["task_status_summary"])
        self.assertIn("persistence", packet["task_status_summary"])
        self.assertIn("persistence_source_rows", packet["task_status_summary"])
        self.assertIn("memory_task_count", packet["task_status_summary"])
        self.assertIn("sqlite_task_count", packet["task_status_summary"])
        self.assertIn("deduplicated_task_count", packet["task_status_summary"])
        self.assertIn("task_log_count", packet["task_status_summary"])
        self.assertIn("task_persistence", packet)
        self.assertIn("task_persistence_source_rows", packet)
        self.assertIn("production_readiness", packet)
        self.assertEqual(packet["production_readiness"]["scope"], "worker_task_pipeline_productionization_preflight")
        self.assertTrue(packet["production_readiness"]["local_fallback_available"])
        self.assertTrue(packet["production_readiness"]["cache_api_starts_no_workers"])
        self.assertTrue(packet["production_readiness"]["cache_api_pings_no_redis"])
        self.assertFalse(packet["production_readiness"]["external_calls_triggered"])
        blocker_audit = packet["production_readiness"]["production_blocker_audit"]
        self.assertEqual(blocker_audit["schema_version"], "worker_production_blocker_audit.v1")
        self.assertEqual(blocker_audit["status"], "production_worker_blocked")
        self.assertEqual(blocker_audit["scope"], "local_worker_runtime_blocker_audit_no_process_start")
        self.assertGreater(blocker_audit["blocking_criterion_count"], 0)
        self.assertFalse(blocker_audit["production_worker_complete"])
        self.assertFalse(blocker_audit["cache_api_started_workers"])
        self.assertFalse(blocker_audit["cache_api_pinged_redis"])
        self.assertFalse(blocker_audit["cache_api_started_scheduler"])
        self.assertFalse(blocker_audit["external_calls_triggered"])
        self.assertTrue(blocker_audit["does_not_execute_trades"])
        self.assertTrue(blocker_audit["does_not_modify_strategy_action"])
        self.assertEqual(packet["worker_production_blocker_audit"], blocker_audit)
        self.assertEqual(packet["worker_production_blocker_rows"], blocker_audit["rows"])
        blocker_by_criterion = {row["criterion"]: row for row in blocker_audit["rows"]}
        self.assertIn("celery_worker_started", blocker_by_criterion)
        self.assertEqual(blocker_by_criterion["celery_worker_started"]["status"], "blocked")
        self.assertFalse(blocker_by_criterion["celery_worker_started"]["cache_api_can_resolve"])
        self.assertTrue(blocker_by_criterion["celery_worker_started"]["operator_action_required"])
        self.assertIn("stub_tasks_migrated", blocker_by_criterion)
        self.assertTrue(blocker_by_criterion["external_tasks_button_gated"]["status"], "passed")
        self.assertTrue(blocker_by_criterion["external_tasks_call_ledger_required"]["status"], "passed")
        self.assertTrue(blocker_by_criterion["scheduler_default_off"]["status"], "passed")
        self.assertTrue(blocker_by_criterion["cache_get_never_dispatches_external_work"]["status"], "passed")
        self.assertTrue(all(row["external_calls_triggered"] is False for row in blocker_audit["rows"]))
        self.assertTrue(all(row["redis_pinged"] is False for row in blocker_audit["rows"]))
        self.assertFalse(packet["production_readiness"]["production_worker_complete"])
        activation_review = packet["production_readiness"]["worker_activation_review_contract"]
        self.assertEqual(activation_review["schema_version"], "worker_activation_review_contract.v1")
        self.assertEqual(activation_review["status"], "worker_activation_review_ready_activation_pending")
        self.assertEqual(activation_review["scope"], "manual_worker_activation_review_no_process_start")
        self.assertEqual(
            activation_review["review_policy"],
            "manual_activation_required_after_blocker_and_healthcheck_review",
        )
        self.assertFalse(activation_review["activation_ready"])
        self.assertFalse(activation_review["production_worker_complete"])
        self.assertTrue(activation_review["manual_activation_required"])
        self.assertTrue(activation_review["healthcheck_required_before_activation"])
        self.assertFalse(activation_review["healthcheck_executed"])
        self.assertFalse(activation_review["worker_started_by_cache_api"])
        self.assertFalse(activation_review["redis_pinged_by_cache_api"])
        self.assertFalse(activation_review["scheduler_started_by_cache_api"])
        self.assertFalse(activation_review["task_dispatched_by_cache_api"])
        self.assertFalse(activation_review["cache_get_external_calls"])
        self.assertFalse(activation_review["external_calls_triggered"])
        self.assertFalse(activation_review["tushare_called"])
        self.assertFalse(activation_review["deepseek_called"])
        self.assertFalse(activation_review["github_called"])
        self.assertTrue(activation_review["does_not_execute_trades"])
        self.assertTrue(activation_review["does_not_modify_strategy_action"])
        self.assertFalse(activation_review["contains_secret"])
        self.assertGreater(activation_review["activation_blocker_count"], 0)
        self.assertEqual(packet["worker_activation_review_contract"], activation_review)
        self.assertEqual(packet["worker_activation_review_rows"], activation_review["rows"])
        activation_steps = {row["review_step"]: row for row in activation_review["rows"]}
        self.assertIn("review_production_blockers", activation_steps)
        self.assertIn("review_redis_broker_configuration", activation_steps)
        self.assertIn("review_celery_manual_start", activation_steps)
        self.assertIn("review_synthetic_healthcheck", activation_steps)
        self.assertIn("review_provider_model_isolation", activation_steps)
        self.assertEqual(activation_steps["review_provider_model_isolation"]["status"], "passed")
        self.assertFalse(activation_steps["review_provider_model_isolation"]["external_calls_triggered"])
        self.assertFalse(any(row["cache_api_can_execute"] for row in activation_review["rows"]))
        self.assertFalse(any(row["cache_api_started_workers"] for row in activation_review["rows"]))
        self.assertFalse(any(row["cache_api_pinged_redis"] for row in activation_review["rows"]))
        self.assertFalse(any(row["task_dispatched"] for row in activation_review["rows"]))
        preflight_by_key = {row["step_key"]: row for row in packet["production_readiness"]["manual_preflight_steps"]}
        self.assertIn("configure_redis_broker", preflight_by_key)
        self.assertIn("start_celery_worker", preflight_by_key)
        self.assertIn("enable_scheduler", preflight_by_key)
        self.assertFalse(preflight_by_key["configure_redis_broker"]["cache_api_can_execute"])
        self.assertFalse(preflight_by_key["start_celery_worker"]["cache_api_can_execute"])
        self.assertEqual(preflight_by_key["enable_scheduler"]["status"], "disabled_by_default")
        self.assertIn("不会 ping Redis", preflight_by_key["configure_redis_broker"]["safe_note"])
        readiness_by_component = {row["component"]: row for row in packet["production_readiness"]["rows"]}
        self.assertIn("local_fallback_runner", readiness_by_component)
        self.assertIn("celery_worker_process", readiness_by_component)
        self.assertIn("redis_broker", readiness_by_component)
        self.assertIn("apscheduler", readiness_by_component)
        worker_controls = {row["control"]: row for row in packet["production_readiness"]["production_control_rows"]}
        self.assertEqual(worker_controls["retry_policy"]["status"], "local_ready")
        self.assertIn("POST /api/tasks/{task_id}/retry", worker_controls["retry_policy"]["current_coverage"])
        self.assertIn("React Task Monitor", worker_controls["retry_policy"]["current_coverage"])
        self.assertIn("automatic retry/backoff remains disabled", worker_controls["retry_policy"]["current_coverage"])
        self.assertEqual(worker_controls["task_cancel"]["status"], "local_ready")
        self.assertEqual(worker_controls["concurrency_lock"]["status"], "local_ready")
        self.assertIn("lock_policy", worker_controls["concurrency_lock"]["current_coverage"])
        self.assertIn("local dispatch reuses active tasks", worker_controls["concurrency_lock"]["current_coverage"])
        self.assertEqual(worker_controls["task_dedupe"]["status"], "local_ready")
        self.assertIn("dedupe_policy", worker_controls["task_dedupe"]["current_coverage"])
        self.assertIn("local dispatch reuses active tasks", worker_controls["task_dedupe"]["current_coverage"])
        self.assertEqual(worker_controls["task_logs"]["status"], "local_ready")
        self.assertIn("task_log", worker_controls["task_logs"]["current_coverage"])
        self.assertEqual(worker_controls["worker_dispatch_plan"]["status"], "contract_ready")
        self.assertIn("future Celery queue", worker_controls["worker_dispatch_plan"]["current_coverage"])
        self.assertTrue(all(row["external_calls_triggered"] is False for row in worker_controls.values()))
        self.assertEqual(packet["dispatch_plan_status"], "contract_ready_local_fallback")
        self.assertEqual(len(packet["dispatch_plan_rows"]), task_service.build_task_catalog()["task_count"])
        self.assertEqual(packet["dispatch_plan_summary"]["task_count"], len(packet["dispatch_plan_rows"]))
        self.assertGreaterEqual(packet["dispatch_plan_summary"]["local_fallback_supported_count"], 1)
        self.assertEqual(packet["dispatch_plan_summary"]["cache_get_external_call_count"], 0)
        self.assertEqual(packet["dispatch_plan_summary"]["scheduler_auto_task_count"], 0)
        self.assertFalse(packet["dispatch_plan_summary"]["redis_pinged"])
        self.assertFalse(packet["dispatch_plan_summary"]["celery_started"])
        self.assertFalse(packet["dispatch_plan_summary"]["external_calls_triggered"])
        self.assertTrue(packet["dispatch_plan_summary"]["all_routes_button_gated"])
        self.assertIn("provider_refresh", packet["dispatch_plan_summary"]["queue_names"])
        self.assertIn("local_compute", packet["dispatch_plan_summary"]["queue_names"])
        dispatch_by_task = {row["task_type"]: row for row in packet["dispatch_plan_rows"]}
        self.assertEqual(dispatch_by_task["refresh_tushare_facts"]["future_queue"], "provider_refresh")
        self.assertEqual(dispatch_by_task["run_deepseek_factor_explanation"]["future_queue"], "model_explain")
        self.assertEqual(dispatch_by_task["run_storage_artifact_cleanup_dry_run"]["future_queue"], "local_maintenance")
        self.assertEqual(dispatch_by_task["run_storage_schema_validation_dry_run"]["future_queue"], "local_maintenance")
        self.assertEqual(dispatch_by_task["run_storage_partition_migration_dry_run"]["future_queue"], "local_maintenance")
        self.assertEqual(dispatch_by_task["run_storage_compaction_dry_run"]["future_queue"], "local_maintenance")
        self.assertEqual(dispatch_by_task["run_storage_cache_ttl_dry_run"]["future_queue"], "local_maintenance")
        self.assertEqual(dispatch_by_task["probe_serenity_github"]["future_queue"], "external_probe")
        self.assertTrue(all(row["local_fallback_supported"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["redis_required_for_celery"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["retry_policy_required"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["cancel_policy_required"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["lock_policy_required"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["dedupe_policy_required"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["safe_task_log_required"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["error_message_safe_required"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["button_gated"] for row in packet["dispatch_plan_rows"]))
        self.assertFalse(any(row["automatic_scheduler_allowed"] for row in packet["dispatch_plan_rows"]))
        self.assertFalse(any(row["redis_pinged"] for row in packet["dispatch_plan_rows"]))
        self.assertFalse(any(row["celery_started"] for row in packet["dispatch_plan_rows"]))
        self.assertFalse(any(row["external_calls_triggered"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["does_not_execute_trades"] for row in packet["dispatch_plan_rows"]))
        self.assertTrue(all(row["does_not_modify_strategy_action"] for row in packet["dispatch_plan_rows"]))
        self.assertIn("memory_task_count", packet["counts"])
        self.assertIn("sqlite_task_count", packet["counts"])
        self.assertIn("deduplicated_task_count", packet["counts"])
        self.assertIn("production_blocker_count", packet["counts"])
        self.assertEqual(packet["counts"]["production_blocker_audit_count"], blocker_audit["blocking_criterion_count"])
        self.assertEqual(packet["counts"]["worker_activation_review_step_count"], activation_review["review_step_count"])
        self.assertEqual(packet["counts"]["worker_activation_blocker_count"], activation_review["activation_blocker_count"])
        self.assertEqual(
            packet["counts"]["worker_activation_operator_action_count"],
            activation_review["operator_action_required_count"],
        )
        self.assertEqual(packet["counts"]["dispatch_plan_task_count"], len(packet["dispatch_plan_rows"]))
        self.assertEqual(packet["counts"]["dispatch_plan_queue_count"], len(packet["dispatch_plan_summary"]["queue_names"]))
        self.assertEqual(packet["counts"]["manual_preflight_step_count"], len(packet["production_readiness"]["manual_preflight_steps"]))
        self.assertGreaterEqual(packet["counts"]["manual_preflight_operator_action_count"], 1)
        self.assertEqual(packet["task_persistence"], packet["task_status_summary"]["persistence"])
        self.assertEqual(packet["task_persistence_source_rows"], packet["task_status_summary"]["persistence_source_rows"])
        self.assertFalse(packet["task_status_summary"]["external_calls_triggered"])
        self.assertTrue(packet["task_status_summary"]["does_not_execute_trades"])
        self.assertTrue(packet["task_status_summary"]["does_not_modify_strategy_action"])
        self.assertIn("task_status_count", packet["counts"])
        self.assertIn("task_status_call_ledger_count", packet["counts"])
        self.assertIn("task_log_count", packet["task_status_summary"])
        self.assertEqual(packet["counts"]["stub_task_count"], 2)
        self.assertEqual(packet["counts"]["local_pipeline_task_count"], 13)
        self.assertEqual(packet["counts"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["counts"]["implemented_local_task_count"], 14)
        self.assertTrue(packet["policy"]["does_not_ping_redis"])
        self.assertTrue(packet["policy"]["does_not_start_celery_worker"])
        self.assertTrue(packet["policy"]["does_not_start_scheduler"])
        self.assertTrue(packet["policy"]["does_not_schedule_real_tasks"])
        self.assertTrue(packet["policy"]["task_implementation_status_is_read_only"])
        self.assertTrue(packet["policy"]["stub_tasks_must_not_be_reported_as_complete"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["redis_pinged"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_worker_runtime_cache")
        self.assertNotIn("COMMAND_CENTER_REDIS_URL", json.dumps(packet, ensure_ascii=False))
        json.dumps(packet, ensure_ascii=False)

    def test_call_ledger_audit_cache_aggregates_local_ledgers_without_external_work(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        task = task_service.create_task_record(
            "build_next_session_projection",
            output_packet_key="command_center_next_session_projection_packet",
            payload={"api_key": "SHOULD_DROP", "ts_code": "002008.SZ"},
        )
        update_task_status(
            task["task_id"],
            status="success",
            progress=1.0,
            current_step="local audit fixture",
            call_ledger=[
                {
                    "api": "local_test_task",
                    "call_status": "cache_read",
                    "error_message_safe": "Traceback token=SHOULD_DROP",
                    "external": False,
                }
            ],
        )
        self._with_snapshot_cache(
            {
                "moneyflow_packet": {
                    "status": "ready",
                    "call_ledger": [{"api": "local_moneyflow_cache", "call_status": "cache_read"}],
                    "authorization": "Bearer SHOULD_DROP",
                }
            }
        )

        packet = audit_service.read_call_ledger_audit_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_call_ledger_audit_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertGreater(packet["counts"]["cache_endpoint_count"], 10)
        self.assertGreaterEqual(packet["counts"]["task_count"], 1)
        self.assertIn("memory_task_count", packet["counts"])
        self.assertIn("sqlite_task_count", packet["counts"])
        self.assertIn("deduplicated_task_count", packet["counts"])
        self.assertGreaterEqual(packet["counts"]["call_ledger_count"], 1)
        self.assertEqual(packet["counts"]["model_strategy_purpose_count"], 7)
        self.assertEqual(packet["counts"]["model_strategy_cache_read_external_call_count"], 0)
        self.assertEqual(packet["counts"]["stub_task_count"], 2)
        self.assertEqual(packet["counts"]["local_pipeline_task_count"], 13)
        self.assertEqual(packet["counts"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["counts"]["implemented_local_task_count"], 14)
        self.assertEqual(packet["counts"]["external_capable_task_count"], 5)
        self.assertEqual(packet["counts"]["external_call_count"], 0)
        self.assertEqual(packet["counts"]["action_risk_count"], 0)
        endpoint_by_source = {row["source"]: row for row in packet["endpoint_rows"]}
        self.assertIn("health", endpoint_by_source)
        self.assertIn("model_strategy", endpoint_by_source)
        self.assertIn("desktop_preflight", endpoint_by_source)
        self.assertIn("task_status_index", endpoint_by_source)
        self.assertEqual(endpoint_by_source["health"]["endpoint"], "GET /health")
        self.assertEqual(endpoint_by_source["model_strategy"]["endpoint"], "GET /api/model-strategy/cache")
        self.assertEqual(endpoint_by_source["desktop_preflight"]["endpoint"], "GET /api/desktop/preflight-cache")
        self.assertEqual(endpoint_by_source["task_status_index"]["endpoint"], "GET /api/tasks")
        self.assertEqual(endpoint_by_source["factor_quant"]["endpoint"], "GET /api/factor-quant/cache")
        self.assertFalse(endpoint_by_source["health"]["external_calls_triggered"])
        self.assertFalse(endpoint_by_source["model_strategy"]["external_calls_triggered"])
        self.assertFalse(endpoint_by_source["desktop_preflight"]["external_calls_triggered"])
        self.assertFalse(endpoint_by_source["task_status_index"]["external_calls_triggered"])
        self.assertFalse(endpoint_by_source["factor_quant"]["external_calls_triggered"])
        self.assertGreaterEqual(endpoint_by_source["health"]["call_ledger_count"], 1)
        self.assertGreaterEqual(endpoint_by_source["model_strategy"]["call_ledger_count"], 1)
        self.assertGreaterEqual(endpoint_by_source["desktop_preflight"]["call_ledger_count"], 1)
        self.assertGreaterEqual(endpoint_by_source["task_status_index"]["call_ledger_count"], 1)
        self.assertGreaterEqual(endpoint_by_source["factor_quant"]["call_ledger_count"], 1)
        self.assertIn("local_health_check", {row.get("api") for row in packet["endpoint_call_ledger_rows"]})
        self.assertIn("local_task_status_index", {row.get("api") for row in packet["endpoint_call_ledger_rows"]})
        self.assertIn("local_factor_quant_cache", {row.get("api") for row in packet["endpoint_call_ledger_rows"]})
        self.assertIn("task_persistence", packet)
        self.assertIn("task_persistence_source_rows", packet)
        self.assertEqual(packet["task_implementation_status"]["status"], "partial_migration")
        self.assertEqual(packet["task_implementation_status"]["stub_task_count"], 2)
        self.assertEqual(packet["task_implementation_status"]["local_pipeline_task_count"], 13)
        self.assertEqual(packet["task_implementation_status"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["task_implementation_status"]["implemented_local_task_count"], 14)
        self.assertIn("refresh_tushare_facts", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("refresh_factor_data", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_factor_light", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_factor_universe_research_plan", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_candidate_radar_full_pool_plan", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_candidate_radar_deep_scan_plan", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_storage_schema_validation_dry_run", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_storage_partition_migration_dry_run", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_storage_compaction_dry_run", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_storage_cache_ttl_dry_run", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_deepseek_factor_explanation", packet["task_implementation_status"]["guarded_local_task_types"])
        self.assertEqual(packet["task_persistence"]["storage_backend"], "memory_plus_sqlite_fallback")
        self.assertTrue(packet["task_persistence"]["task_rows_include_storage_source"])
        self.assertEqual({row["source"] for row in packet["task_persistence_source_rows"]}, {"memory", "sqlite_meta", "deduplicated"})
        self.assertIn("storage_source", packet["task_rows"][0])
        model_rows = {row["purpose"]: row for row in packet["model_strategy_rows"]}
        self.assertEqual(
            set(model_rows),
            {"default", "explain", "projection", "factor_explain", "fast", "healthcheck", "feeder"},
        )
        self.assertTrue(all(row["does_not_hardcode_model"] for row in model_rows.values()))
        self.assertFalse(any(row["contains_secret"] for row in model_rows.values()))
        self.assertFalse(any(row["external_call_on_cache_read"] for row in model_rows.values()))
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["policy"]["audit_is_read_only"])
        self.assertTrue(packet["policy"]["post_task_required_for_external_work"])
        self.assertTrue(packet["policy"]["task_implementation_status_is_read_only"])
        self.assertTrue(packet["policy"]["stub_tasks_must_not_be_reported_as_complete"])
        self.assertTrue(packet["policy"]["reads_memory_and_sqlite_fallback"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_call_ledger_audit_cache")
        self.assertEqual(packet["call_ledger"][0]["storage_backend"], "memory_plus_sqlite_fallback")
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        json.dumps(packet, ensure_ascii=False)

    def test_call_ledger_audit_covers_all_fastapi_get_routes(self):
        packet = audit_service.read_call_ledger_audit_cache()
        coverage = packet["get_route_coverage"]
        discovered_routes = self._discover_fastapi_get_routes()

        self.assertEqual(sorted(coverage["known_get_routes"]), discovered_routes)
        self.assertEqual(coverage["known_get_route_count"], len(discovered_routes))
        self.assertEqual(coverage["uncovered_get_routes"], [])
        self.assertTrue(coverage["all_known_get_routes_cache_only"])
        self.assertTrue(coverage["cache_routes_create_no_tasks"])
        self.assertFalse(coverage["external_calls_triggered"])
        self.assertIn("GET /api/audit/cache", coverage["known_get_routes"])
        self.assertIn("GET /api/packets/{packet_key}", coverage["known_get_routes"])
        self.assertIn("GET /api/tasks/{task_id}", coverage["known_get_routes"])
        self.assertIn("GET /api/tasks/{task_id}/logs", coverage["known_get_routes"])
        self.assertIn("GET /api/storage/{dataset}", coverage["known_get_routes"])
        self.assertTrue(any(row.get("source") == "call_ledger_audit_self" and row.get("not_invoked_by_audit_reader") for row in coverage["parameterized_local_routes"]))
        endpoint_by_source = {row["source"]: row for row in packet["endpoint_rows"]}
        self.assertIn("task_catalog", endpoint_by_source)
        self.assertIn("storage_dataset_catalog", endpoint_by_source)
        self.assertEqual(endpoint_by_source["storage_dataset_catalog"]["endpoint"], "GET /api/storage/catalog")
        self.assertIn("storage_factor_values", endpoint_by_source)
        self.assertIn("storage_sqlite_meta", endpoint_by_source)

    def test_cancel_task_marks_pending_task_without_external_work(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        task = task_service.create_task_record(
            "build_next_session_projection",
            output_packet_key="command_center_next_session_projection_packet",
            payload={"ts_code": "002008.SZ", "api_key": "SHOULD_DROP"},
        )

        cancelled = task_service.cancel_task(task["task_id"], {"reason": "user requested token=SHOULD_DROP"})

        self.assertIsNotNone(cancelled)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["current_step"], "cancelled_by_user_no_external_call")
        self.assertEqual(cancelled["call_ledger"][-1]["api"], "local_task_cancel")
        self.assertEqual(cancelled["call_ledger"][-1]["call_status"], "cancelled_locally_no_external_call")
        self.assertEqual(cancelled["call_ledger"][-1]["request_params_safe"]["reason"], "[redacted_sensitive_text]")
        self.assert_local_ledger_boundary(cancelled["call_ledger"][-1])
        self.assertNotIn("api_key", cancelled["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(cancelled, ensure_ascii=False))
        self.assertFalse(cancelled["external_calls_triggered"])
        self.assertFalse(cancelled["tushare_called"])
        self.assertFalse(cancelled["deepseek_called"])
        self.assertFalse(cancelled["github_called"])
        self.assertTrue(cancelled["does_not_execute_trades"])
        self.assertTrue(cancelled["does_not_modify_strategy_action"])
        task_service._TASKS.clear()
        persisted = read_task_status(task["task_id"])
        self.assertEqual(persisted["status"], "cancelled")

    def test_task_records_include_safe_idempotency_and_lock_keys(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        task_a = task_service.create_task_record(
            "refresh_tushare_facts",
            output_packet_key="command_center_tushare_refresh_packet",
            payload={"ts_code": "002008.SZ", "api_key": "SHOULD_DROP_A"},
        )
        task_b = task_service.create_task_record(
            "refresh_tushare_facts",
            output_packet_key="command_center_tushare_refresh_packet",
            payload={"ts_code": "002008.SZ", "api_key": "SHOULD_DROP_B"},
        )

        self.assertEqual(task_a["input_hash"], task_b["input_hash"])
        self.assertEqual(task_a["idempotency_key"], task_b["idempotency_key"])
        self.assertTrue(task_a["idempotency_key"].startswith("refresh_tushare_facts:"))
        self.assertTrue(task_a["lock_key"].startswith("lock:refresh_tushare_facts:"))
        self.assertFalse(task_a["lock_enforced"])
        self.assertFalse(task_a["retry_policy"]["enabled"])
        self.assertFalse(task_a["retry_policy"]["auto_retry_enabled"])
        self.assertTrue(task_a["retry_policy"]["manual_retry_allowed"])
        self.assertFalse(task_a["retry_policy"]["manual_retry_eligible"])
        self.assertTrue(task_a["retry_policy"]["requires_new_task_id"])
        self.assertEqual(task_a["retry_policy"]["max_attempts"], 3)
        self.assertEqual(task_a["retry_policy"]["attempt_number"], 1)
        self.assertEqual(task_a["retry_policy"]["attempts_remaining"], 2)
        self.assertEqual(task_a["retry_policy"]["retryable_statuses"], ["failed"])
        self.assertFalse(task_a["retry_policy"]["external_calls_triggered"])
        self.assertTrue(task_a["retry_policy"]["does_not_execute_trades"])
        self.assertTrue(task_a["retry_policy"]["does_not_modify_strategy_action"])
        self.assertFalse(task_a["lock_policy"]["lock_enforced"])
        self.assertTrue(task_a["lock_policy"]["lock_enforcement_enabled"])
        self.assertFalse(task_a["lock_policy"]["audit_only"])
        self.assertTrue(task_a["lock_policy"]["conflict_detection_enabled"])
        self.assertFalse(task_a["lock_policy"]["lock_conflict_detected"])
        self.assertEqual(task_a["lock_policy"]["active_conflict_count"], 0)
        self.assertFalse(task_a["lock_policy"]["cache_api_can_acquire_lock"])
        self.assertEqual(task_b["task_id"], task_a["task_id"])
        self.assertTrue(task_b["dedupe_reused_existing"])
        self.assertEqual(task_b["dedupe_reuse_count"], 1)
        self.assertTrue(task_b["lock_policy"]["lock_enforcement_enabled"])
        self.assertTrue(task_b["lock_policy"]["lock_enforced"])
        self.assertTrue(task_b["lock_policy"]["lock_conflict_detected"])
        self.assertEqual(task_b["lock_policy"]["active_conflict_count"], 1)
        self.assertTrue(task_b["lock_policy"]["auto_blocks_task_creation"])
        self.assertEqual(task_b["lock_policy"]["blocked_duplicate_creation_count"], 1)
        self.assertEqual(task_b["lock_policy"]["reused_existing_task_id"], task_a["task_id"])
        self.assertFalse(task_b["lock_policy"]["external_calls_triggered"])
        self.assertTrue(task_b["lock_policy"]["does_not_execute_trades"])
        self.assertTrue(task_b["lock_policy"]["does_not_modify_strategy_action"])
        self.assertTrue(task_b["dedupe_policy"]["dispatch_dedupe_enabled"])
        self.assertTrue(task_b["dedupe_policy"]["dispatch_dedupe_enforced"])
        self.assertFalse(task_b["dedupe_policy"]["audit_only"])
        self.assertTrue(task_b["dedupe_policy"]["duplicate_detected"])
        self.assertEqual(task_b["dedupe_policy"]["blocked_duplicate_creation_count"], 1)
        self.assertEqual(task_b["dedupe_policy"]["reused_existing_task_id"], task_a["task_id"])
        self.assertFalse(task_b["dedupe_policy"]["cache_api_can_dedupe"])
        self.assertTrue(task_b["dedupe_policy"]["auto_blocks_task_creation"])
        self.assertFalse(task_b["dedupe_policy"]["external_calls_triggered"])
        self.assertTrue(task_b["dedupe_policy"]["does_not_execute_trades"])
        self.assertTrue(task_b["dedupe_policy"]["does_not_modify_strategy_action"])
        self.assertEqual(task_a["task_log"][0]["event"], "task_created")
        self.assertFalse(task_a["task_log"][0]["external_calls_triggered"])
        self.assertFalse(task_a["task_log"][0]["stack_trace_included"])
        self.assertEqual(task_b["task_log"][-1]["event"], "task_creation_deduped_reused_active_task")
        self.assertEqual(task_b["call_ledger"][-2]["api"], "local_task_dispatch_dedupe")
        self.assertEqual(task_b["call_ledger"][-2]["call_status"], "reused_active_task_no_external_call")
        self.assertEqual(task_b["call_ledger"][-1]["api"], "local_task_dispatch_lock")
        self.assertEqual(task_b["call_ledger"][-1]["call_status"], "lock_reused_active_task_no_external_call")
        self.assertNotIn("api_key", task_a["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps([task_a, task_b], ensure_ascii=False))

        listing = task_service.build_task_status_index()
        self.assertTrue(listing["persistence"]["task_rows_include_idempotency_key"])
        self.assertTrue(listing["persistence"]["task_rows_include_dedupe_policy"])
        self.assertTrue(listing["persistence"]["task_rows_include_lock_key"])
        self.assertTrue(listing["persistence"]["task_rows_include_lock_policy"])
        self.assertTrue(listing["persistence"]["task_rows_include_retry_policy"])
        self.assertTrue(listing["persistence"]["task_rows_include_task_log"])
        self.assertEqual(listing["persistence"]["idempotency_key_count"], 1)
        self.assertEqual(listing["persistence"]["duplicate_idempotency_key_count"], 0)
        self.assertEqual(listing["persistence"]["dedupe_duplicate_audit_count"], 1)
        self.assertEqual(listing["persistence"]["dispatch_dedupe_enforced_count"], 1)
        self.assertEqual(listing["persistence"]["dedupe_blocked_creation_count"], 1)
        self.assertEqual(listing["persistence"]["lock_blocked_creation_count"], 1)
        self.assertEqual(listing["persistence"]["manual_retry_eligible_count"], 0)
        self.assertEqual(listing["persistence"]["automatic_retry_enabled_count"], 0)
        self.assertEqual(listing["persistence"]["lock_conflict_audit_count"], 1)
        self.assertEqual(listing["persistence"]["lock_enforced_task_count"], 1)
        self.assertEqual(listing["persistence"]["task_log_count"], 2)
        self.assertEqual(listing["task_log_count"], 2)
        self.assertEqual(listing["call_ledger"][0]["idempotency_key_count"], 1)
        self.assertEqual(listing["call_ledger"][0]["duplicate_idempotency_key_count"], 0)
        self.assertEqual(listing["call_ledger"][0]["dedupe_duplicate_audit_count"], 1)
        self.assertEqual(listing["call_ledger"][0]["dispatch_dedupe_enforced_count"], 1)
        self.assertEqual(listing["call_ledger"][0]["dedupe_blocked_creation_count"], 1)
        self.assertEqual(listing["call_ledger"][0]["lock_blocked_creation_count"], 1)
        self.assertEqual(listing["call_ledger"][0]["manual_retry_eligible_count"], 0)
        self.assertEqual(listing["call_ledger"][0]["automatic_retry_enabled_count"], 0)
        self.assertEqual(listing["call_ledger"][0]["lock_conflict_audit_count"], 1)
        self.assertEqual(listing["call_ledger"][0]["lock_enforced_task_count"], 1)
        self.assertEqual(listing["call_ledger"][0]["task_log_count"], 2)
        self.assertTrue(listing["policy"]["task_logs_safe"])
        self.assertTrue(listing["policy"]["task_logs_include_no_raw_payload"])
        self.assertFalse(listing["external_calls_triggered"])
        self.assertTrue(listing["does_not_execute_trades"])
        self.assertTrue(listing["does_not_modify_strategy_action"])

    def test_task_status_update_supports_failed_state_without_secret_leak(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        task = create_task_stub("run_factor_light", payload={"authorization": "Bearer secret", "ts_code": "002008.SZ"})

        updated = update_task_status(
            task["task_id"],
            status="failed",
            progress=0.7,
            current_step="safe_failure_recorded",
            error_message_safe="mock failure with token=SHOULD_DROP",
            warning="safe warning",
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "failed")
        self.assertEqual(updated["current_step"], "safe_failure_recorded")
        self.assertEqual(updated["error_message_safe"], "[redacted_sensitive_text]")
        self.assertFalse(updated["retry_policy"]["enabled"])
        self.assertFalse(updated["retry_policy"]["auto_retry_enabled"])
        self.assertTrue(updated["retry_policy"]["manual_retry_allowed"])
        self.assertTrue(updated["retry_policy"]["manual_retry_eligible"])
        self.assertEqual(updated["retry_policy"]["retryable_statuses"], ["failed"])
        self.assertFalse(updated["retry_policy"]["external_calls_triggered"])
        self.assertTrue(updated["retry_policy"]["does_not_execute_trades"])
        self.assertTrue(updated["retry_policy"]["does_not_modify_strategy_action"])
        self.assertFalse(updated["lock_policy"]["lock_active"])
        self.assertFalse(updated["lock_policy"]["lock_enforced"])
        self.assertTrue(updated["lock_policy"]["lock_enforcement_enabled"])
        self.assertFalse(updated["lock_policy"]["lock_conflict_detected"])
        self.assertEqual(updated["lock_policy"]["active_conflict_count"], 0)
        self.assertTrue(updated["lock_policy"]["auto_blocks_task_creation"])
        self.assertTrue(updated["dedupe_policy"]["dispatch_dedupe_enabled"])
        self.assertFalse(updated["dedupe_policy"]["dispatch_dedupe_enforced"])
        self.assertTrue(updated["dedupe_policy"]["auto_blocks_task_creation"])
        self.assertEqual([row["event"] for row in updated["task_log"]], ["task_created", "task_status_updated", "task_status_updated", "task_status_updated"])
        self.assertEqual(updated["task_log"][-1]["message_safe"], "[redacted_sensitive_text]")
        self.assertFalse(updated["task_log"][-1]["external_calls_triggered"])
        self.assertFalse(updated["task_log"][-1]["stack_trace_included"])
        self.assertNotIn("authorization", updated["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(updated, ensure_ascii=False))
        self.assertIn("safe warning", updated["warnings"])

        listing = task_service.build_task_status_index()
        self.assertEqual(listing["persistence"]["manual_retry_eligible_count"], 1)
        self.assertEqual(listing["persistence"]["automatic_retry_enabled_count"], 0)
        self.assertEqual(listing["persistence"]["lock_enforced_task_count"], 0)
        self.assertEqual(listing["persistence"]["lock_blocked_creation_count"], 0)
        self.assertEqual(listing["persistence"]["dispatch_dedupe_enforced_count"], 0)
        self.assertEqual(listing["persistence"]["dedupe_blocked_creation_count"], 0)

    def test_factor_run_light_writes_local_cache_without_external_calls(self):
        self._with_snapshot_cache(
            {
                "timestamp": "2026-06-10T09:30:00",
                "moneyflow_packet": {"status": "ready", "ticker": "002008.SZ", "main_net_yi": 1.2, "small_net_yi": -0.4},
                "hard_risk_packet": {"status": "ready", "risk_flags": []},
                "limit_emotion_packet": {"status": "ready", "limit_heat_score": 1},
                "chip_packet": {"status": "ready", "winner_rate": 40},
                "strategy_packet": {"status": "ready", "action": "wait"},
                "decision_packet": {"status": "ready"},
                "quant_packet": {"status": "ready"},
                "a_share_fact_lineage_summary": {"items": [{"fact_key": "moneyflow"}]},
            }
        )
        self._with_meta_store()
        self._with_parquet_root()

        task = factor_service.create_factor_task(
            "run_factor_light",
            payload={"ts_code": "002008.SZ", "api_key": "SHOULD_DROP"},
        )
        packet = packet_service.build_factor_quant_cache()
        cache_packet = factor_service.read_factor_quant_cache()

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "factor_light_completed_from_local_cache")
        self.assertEqual(task["call_ledger"][0]["call_status"], "cache_read")
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        storage_ledger = [item for item in task["call_ledger"] if item.get("api") == "local_parquet_factor_values"]
        self.assertEqual(len(storage_ledger), 1)
        self.assertIn(storage_ledger[0]["call_status"], {"written", "dependency_missing", "empty"})
        self.assert_local_ledger_boundary(storage_ledger[0])
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertFalse(task["external_calls_triggered"])

        self.assertEqual(packet["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertEqual(packet["mode"], "light")
        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertEqual(packet["factor_values_storage"]["dataset"], "factor_values")
        self.assertIn(packet["factor_values_storage"]["status"], {"written", "dependency_missing", "empty"})
        self.assertIn("local_parquet_factor_values", {item.get("api") for item in packet["storage_call_ledger"]})
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_action"])
        support_keys = {item.get("factor_key") for item in packet["score"]["support_factors"]}
        suppress_keys = {item.get("factor_key") for item in packet["score"]["suppress_factors"]}
        self.assertNotIn("serenity_method_source", support_keys | suppress_keys)
        self.assertNotIn("chokepoint_method_hint", support_keys | suppress_keys)
        self.assertIn("roe_latest", {item.get("factor_key") for item in packet["score"]["missing_factors"]})
        chart_payload = cache_packet["score_chart_payload"]
        self.assertEqual(chart_payload["chart_type"], "factor_score_bucket_bar")
        self.assertEqual(chart_payload["chart_contract"]["schema_version"], "factor_quant_score_echarts_payload.v1")
        self.assertFalse(chart_payload["chart_contract"]["external_calls_triggered"])
        self.assertFalse(chart_payload["chart_contract"]["tushare_called"])
        self.assertFalse(chart_payload["chart_contract"]["deepseek_called"])
        self.assertFalse(chart_payload["chart_contract"]["github_called"])
        self.assertTrue(chart_payload["chart_contract"]["does_not_execute_trades"])
        self.assertFalse(chart_payload["chart_contract"]["frontend_computes_trade_action"])
        self.assertTrue(chart_payload["chart_contract"]["does_not_modify_action"])
        self.assertTrue(chart_payload["chart_contract"]["does_not_modify_operation_zones"])
        self.assertEqual(chart_payload["chart_contract"]["series_counts"]["bucket_rows"], 5)
        self.assertEqual(chart_payload["chart_contract"]["series_counts"]["missing"], len(packet["score"]["missing_factors"]))
        self.assertIn("不执行真实交易", " ".join(chart_payload["chart_contract"]["guardrails"]))
        self.assertIn("因子图表不得修改 strategy action", " ".join(chart_payload["chart_contract"]["guardrails"]))

    def test_deepseek_explanation_task_prepares_prompt_without_model_call(self):
        self._with_meta_store()
        self._with_deepseek_mode()

        task = factor_service.create_factor_task("run_deepseek_factor_explanation", payload={"ts_code": "002008.SZ"})
        packet = packet_service.build_factor_quant_cache()

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "deepseek_prompt_ready_without_model_call")
        self.assertEqual(task["call_ledger"][0]["call_status"], "not_called")
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        task_model_strategy = task["call_ledger"][0]["request_params_safe"]["deepseek_model_strategy"]
        self.assertEqual(task_model_strategy["purpose"], "factor_explain")
        self.assertIn("DEEPSEEK_EXPLAIN_MODEL", task_model_strategy["config_keys"])
        self.assertTrue(task_model_strategy["does_not_hardcode_model"])
        self.assertFalse(task_model_strategy["contains_secret"])
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["model_used"], task_model_strategy["model"])
        self.assertTrue(task["call_ledger"][0]["request_params_safe"]["input_hash"])
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["model_call_status"], "not_called")
        self.assertFalse(task["call_ledger"][0]["request_params_safe"]["parse_failed"])
        self.assertGreater(task["call_ledger"][0]["request_params_safe"]["token_estimate"], 0)
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])
        self.assertTrue(task["does_not_execute_trades"])

        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["deepseek_model_called"])
        self.assertFalse(packet["deepseek_task_external_calls_triggered"])
        self.assertEqual(packet["deepseek_explanation"]["status"], "not_called")
        self.assertEqual(packet["deepseek_explanation"]["payload"], None)
        self.assertEqual(packet["deepseek_explanation"]["model_used"], task_model_strategy["model"])
        self.assertTrue(packet["deepseek_explanation"]["input_hash"])
        self.assertEqual(packet["deepseek_explanation"]["output_hash"], "")
        self.assertEqual(packet["deepseek_explanation"]["token_estimate"], 0)
        self.assertFalse(packet["deepseek_explanation_prompt_preview"]["enters_deepseek_prompt"])
        self.assertTrue(packet["deepseek_explanation_prompt_preview"]["would_enter_deepseek_prompt_if_user_authorizes"])
        self.assertEqual(packet["deepseek_explanation_prompt_preview"]["model_used"], task_model_strategy["model"])
        self.assertTrue(packet["deepseek_explanation_prompt_preview"]["input_hash"])
        self.assertGreater(packet["deepseek_explanation_prompt_preview"]["token_estimate"], 0)
        self.assertEqual(packet["deepseek_model_strategy"]["purpose"], "factor_explain")
        self.assertEqual(packet["deepseek_explain_governance"]["mode"], "manual_only")
        self.assertFalse(packet["deepseek_explain_governance"]["auto_after_task"])
        self.assertFalse(packet["deepseek_explain_governance"]["configured_auto_after_task"])
        self.assertTrue(packet["deepseek_explanation_cache_key"]["input_hash"])
        self.assertEqual(packet["deepseek_explanation_cache_key"]["model_name"], task_model_strategy["model"])
        self.assertEqual(packet["deepseek_explanation_cache_key"]["prompt_version"], "factor_deepseek_explanation_prompt.v1")
        self.assertEqual(packet["deepseek_explanation_prompt_preview"]["deepseek_model_strategy"]["purpose"], "factor_explain")
        self.assertEqual(packet["deepseek_validation_summary"]["status"], "not_called")
        self.assertEqual(packet["deepseek_validation_summary"]["validation_mode"], "local_sanitizer_only")
        self.assertEqual(packet["deepseek_validation_summary"]["model_call_status"], "not_called")
        self.assertFalse(packet["deepseek_validation_summary"]["parse_failed"])
        self.assertFalse(packet["deepseek_validation_summary"]["deepseek_called"])
        self.assertFalse(packet["deepseek_validation_summary"]["external_calls_triggered"])
        self.assertTrue(packet["deepseek_validation_summary"]["does_not_modify_strategy_action"])
        self.assertFalse(packet["deepseek_model_strategy"]["contains_secret"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_action"])

    def test_deepseek_explanation_task_sanitizes_payload_without_overwriting_values(self):
        self._with_meta_store()
        self._with_deepseek_mode()
        forbidden = {
            "summary": "只解释已有结构化结果",
            "support_notes": ["量能支持"],
            "strategy_action": "buy",
            "action": "买入",
            "price": 99,
            "position": {"shares": 1000},
            "factor_values": [{"raw_value": 1.2}],
            "packet": {"full": True},
        }

        task = factor_service.create_factor_task(
            "run_deepseek_factor_explanation",
            payload={"provided_explanation": forbidden, "api_key": "DROP"},
        )
        packet = packet_service.build_factor_quant_cache()
        explanation = packet["deepseek_explanation"]

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "deepseek_explanation_sanitized_without_model_call")
        self.assertEqual(task["call_ledger"][0]["call_status"], "provided_payload_sanitized")
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertEqual(
            task["call_ledger"][0]["request_params_safe"]["deepseek_model_strategy"]["purpose"],
            "factor_explain",
        )
        self.assertTrue(task["call_ledger"][0]["request_params_safe"]["input_hash"])
        self.assertTrue(task["call_ledger"][0]["request_params_safe"]["output_hash"])
        self.assertFalse(task["call_ledger"][0]["request_params_safe"]["parse_failed"])
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["model_call_status"], "not_called")
        self.assertGreater(task["call_ledger"][0]["request_params_safe"]["token_estimate"], 0)
        self.assertEqual(task["payload_safe"], {"provided_explanation_payload": True})
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertNotIn("provided_explanation", task["payload_safe"])
        self.assertNotIn("price", json.dumps(task["payload_safe"], ensure_ascii=False))
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])

        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["deepseek_model_called"])
        self.assertEqual(packet["deepseek_model_strategy"]["purpose"], "factor_explain")
        self.assertEqual(packet["deepseek_explain_governance"]["mode"], "manual_only")
        self.assertTrue(packet["deepseek_explanation_cache_key"]["input_hash"])
        self.assertEqual(explanation["deepseek_model_strategy"]["purpose"], "factor_explain")
        self.assertEqual(explanation["status"], "success")
        self.assertFalse(explanation["parse_failed"])
        self.assertEqual(explanation["model_used"], packet["deepseek_model_strategy"]["model"])
        self.assertTrue(explanation["input_hash"])
        self.assertTrue(explanation["output_hash"])
        self.assertGreater(explanation["token_estimate"], 0)
        self.assertEqual(packet["deepseek_validation_summary"]["status"], "success")
        self.assertEqual(packet["deepseek_validation_summary"]["output_hash"], explanation["output_hash"])
        self.assertEqual(packet["deepseek_validation_summary"]["ignored_key_count"], 6)
        self.assertFalse(packet["deepseek_validation_summary"]["parse_failed"])
        self.assertFalse(packet["deepseek_validation_summary"]["deepseek_called"])
        self.assertTrue(packet["deepseek_validation_summary"]["does_not_override_numeric_values"])
        self.assertTrue(packet["deepseek_validation_summary"]["does_not_output_strategy_action"])
        self.assertEqual(explanation["payload"]["summary"], "只解释已有结构化结果")
        self.assertEqual(set(explanation["payload"]), {
            "summary",
            "support_notes",
            "suppress_notes",
            "conflict_notes",
            "missing_data_notes",
            "discipline_notes",
        })
        for forbidden_key in ("strategy_action", "action", "price", "position", "factor_values", "packet"):
            self.assertIn(forbidden_key, explanation["ignored_keys"])
            self.assertNotIn(forbidden_key, explanation["payload"])

    def test_deepseek_explanation_task_marks_invalid_json_as_parse_failed_without_pollution(self):
        self._with_meta_store()
        self._with_deepseek_mode()

        task = factor_service.create_factor_task(
            "run_deepseek_factor_explanation",
            payload={"mock_deepseek_output": "not json price=99 action=buy token=DROP"},
        )
        packet = packet_service.build_factor_quant_cache()
        explanation = packet["deepseek_explanation"]
        validation = packet["deepseek_validation_summary"]

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["call_ledger"][0]["call_status"], "provided_payload_parse_failed")
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertTrue(task["call_ledger"][0]["request_params_safe"]["parse_failed"])
        self.assertTrue(task["call_ledger"][0]["request_params_safe"]["output_hash"])
        self.assertNotIn("price=99", json.dumps(task, ensure_ascii=False))
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])

        self.assertEqual(explanation["status"], "parse_failed")
        self.assertTrue(explanation["parse_failed"])
        self.assertEqual(explanation["payload"]["summary"], "")
        self.assertEqual(explanation["payload"]["support_notes"], [])
        self.assertTrue(explanation["output_hash"])
        self.assertEqual(validation["status"], "parse_failed")
        self.assertTrue(validation["parse_failed"])
        self.assertTrue(validation["invalid_output_discarded"])
        self.assertEqual(validation["model_call_status"], "not_called")
        self.assertFalse(validation["deepseek_called"])
        self.assertFalse(validation["external_calls_triggered"])
        self.assertTrue(validation["does_not_modify_strategy_action"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_action"])
        self.assertTrue(explanation["does_not_override_numeric_values"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_operation_zones"])

    def test_deepseek_disabled_mode_rejects_explanation_task_without_model_call(self):
        self._with_meta_store()
        self._with_deepseek_mode("disabled", auto_enabled=False)

        task = factor_service.create_factor_task("run_deepseek_factor_explanation", payload={"ts_code": "002008.SZ"})

        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["current_step"], "deepseek_explanation_disabled_by_governance")
        self.assertEqual(task["error_message_safe"], "deepseek_factor_explain_disabled")
        self.assertEqual(task["call_ledger"][0]["call_status"], "disabled_by_governance")
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["mode"], "disabled")
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["model_call_status"], "disabled")
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])

    def test_run_light_manual_only_does_not_auto_queue_deepseek_even_if_payload_requests_it(self):
        self._with_meta_store()
        self._with_parquet_root()
        self._with_deepseek_mode("manual_only", auto_enabled=True)
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "timestamp": "2026-06-10T09:30:00",
                "moneyflow_packet": {"status": "ready", "ticker": "002008.SZ", "main_net_yi": 1.2},
                "strategy_packet": {"status": "ready", "action": "wait"},
                "decision_packet": {"status": "ready"},
                "quant_packet": {"status": "ready"},
            }
        )

        task = factor_service.create_factor_task("run_factor_light", payload={"ts_code": "002008.SZ", "auto_after_task": True})
        packet = packet_service.build_factor_quant_cache()
        task_types = [item["task_type"] for item in task_service.list_task_statuses()]

        self.assertEqual(task["status"], "success")
        self.assertEqual(task_types.count("run_factor_light"), 1)
        self.assertNotIn("run_deepseek_factor_explanation", task_types)
        self.assertEqual(packet["deepseek_explain_governance"]["mode"], "manual_only")
        self.assertFalse(packet["deepseek_explain_governance"]["auto_after_task"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["governance"]["allow_core_action"])

    def test_run_light_auto_after_task_requires_mode_config_and_payload(self):
        self._with_meta_store()
        self._with_parquet_root()
        self._with_deepseek_mode("auto_after_task", auto_enabled=True)
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "timestamp": "2026-06-10T09:30:00",
                "moneyflow_packet": {"status": "ready", "ticker": "002008.SZ", "main_net_yi": 1.2},
                "strategy_packet": {"status": "ready", "action": "wait"},
                "decision_packet": {"status": "ready"},
                "quant_packet": {"status": "ready"},
            }
        )

        task = factor_service.create_factor_task("run_factor_light", payload={"ts_code": "002008.SZ", "auto_after_task": True})
        packet = packet_service.build_factor_quant_cache()
        tasks = task_service.list_task_statuses()
        task_types = [item["task_type"] for item in tasks]

        self.assertEqual(task["status"], "success")
        self.assertIn("run_deepseek_factor_explanation", task_types)
        self.assertTrue(any(str(warning).startswith("auto_after_task_created:") for warning in task["warnings"]))
        self.assertEqual(packet["deepseek_explain_governance"]["mode"], "auto_after_task")
        self.assertTrue(packet["deepseek_explain_governance"]["auto_after_task"])
        self.assertTrue(packet["deepseek_explain_governance"]["manual_task_allowed"])
        self.assertTrue(packet["deepseek_explain_governance"]["auto_after_task_queued"])
        self.assertEqual(packet["deepseek_explanation"]["status"], "not_called")
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["deepseek_explanation_cache_key"]["input_hash"])
        self.assertFalse(packet["governance"]["allow_core_action"])

    def test_deepseek_explanation_same_input_hash_uses_cache_hit_no_duplicate_call(self):
        self._with_meta_store()
        self._with_deepseek_mode("manual_only", auto_enabled=False)
        clear_task_statuses_for_tests(clear_persisted=True)

        first = factor_service.create_factor_task(
            "run_deepseek_factor_explanation",
            payload={"provided_explanation": {"summary": "缓存一次", "discipline_notes": ["不改 action"]}},
        )
        second = factor_service.create_factor_task("run_deepseek_factor_explanation", payload={"ts_code": "002008.SZ"})
        packet = packet_service.build_factor_quant_cache()

        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "success")
        self.assertEqual(second["current_step"], "deepseek_explanation_cache_hit_no_model_call")
        self.assertEqual(second["call_ledger"][0]["call_status"], "cache_hit_no_duplicate_model_call")
        self.assertEqual(packet["deepseek_explanation_cache_hit"], True)
        self.assertEqual(packet["deepseek_explanation"]["payload"]["summary"], "缓存一次")
        self.assertFalse(second["deepseek_called"])
        self.assertFalse(packet["deepseek_called"])


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed in this environment")
class CommandCenter3FastAPITests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from server.main import app

        self.client = TestClient(app)

    def _with_snapshot_cache(self, payload):
        original_path = packet_service.SNAPSHOT_CACHE_PATH
        temp_dir = tempfile.TemporaryDirectory()
        cache_path = Path(temp_dir.name) / "command_center_latest.json"
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        packet_service.SNAPSHOT_CACHE_PATH = cache_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SNAPSHOT_CACHE_PATH", original_path)
        return cache_path

    def _with_meta_store(self):
        original_packet_path = packet_service.SQLITE_META_PATH
        original_factor_path = factor_service.SQLITE_META_PATH
        original_next_session_path = next_session_service.SQLITE_META_PATH
        original_task_path = task_service.SQLITE_META_PATH
        original_tushare_task_path = tushare_task_service.SQLITE_META_PATH
        original_candidate_path = candidate_service.SQLITE_META_PATH
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "meta.sqlite"
        packet_service.SQLITE_META_PATH = db_path
        factor_service.SQLITE_META_PATH = db_path
        next_session_service.SQLITE_META_PATH = db_path
        task_service.SQLITE_META_PATH = db_path
        tushare_task_service.SQLITE_META_PATH = db_path
        candidate_service.SQLITE_META_PATH = db_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SQLITE_META_PATH", original_packet_path)
        self.addCleanup(setattr, factor_service, "SQLITE_META_PATH", original_factor_path)
        self.addCleanup(setattr, next_session_service, "SQLITE_META_PATH", original_next_session_path)
        self.addCleanup(setattr, task_service, "SQLITE_META_PATH", original_task_path)
        self.addCleanup(setattr, tushare_task_service, "SQLITE_META_PATH", original_tushare_task_path)
        self.addCleanup(setattr, candidate_service, "SQLITE_META_PATH", original_candidate_path)
        return db_path

    def _with_parquet_root(self):
        original_root = storage_service.PARQUET_ROOT
        temp_dir = tempfile.TemporaryDirectory()
        storage_service.PARQUET_ROOT = Path(temp_dir.name) / "parquet"
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, storage_service, "PARQUET_ROOT", original_root)
        return storage_service.PARQUET_ROOT

    def assert_local_ledger_boundary(self, row):
        self.assertFalse(row["external"])
        self.assertFalse(row["external_calls_triggered"])
        self.assertFalse(row["tushare_called"])
        self.assertFalse(row["deepseek_called"])
        self.assertFalse(row["github_called"])
        self.assertTrue(row["does_not_execute_trades"])
        self.assertTrue(row["does_not_modify_strategy_action"])

    def _with_trade_review_log(self, records):
        original_path = trade_review_service.TRADE_REVIEW_LOG_PATH
        temp_dir = tempfile.TemporaryDirectory()
        log_path = Path(temp_dir.name) / "trade_review_log.jsonl"
        with log_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        trade_review_service.TRADE_REVIEW_LOG_PATH = log_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, trade_review_service, "TRADE_REVIEW_LOG_PATH", original_path)
        return log_path

    def test_p2_cache_missing_uses_structured_error_without_external_calls(self):
        self._with_meta_store()
        self._with_snapshot_cache({})

        for route, expected_api in (
            ("/api/next-session/cache", "local_next_session_cache"),
            ("/api/chokepoint/cache", "local_chokepoint_scan_cache"),
            ("/api/packets/not_present_packet", "local_packet_cache_read"),
        ):
            response = self.client.get(route).json()
            self.assertFalse(response["ok"], route)
            self.assertIsNone(response["data"], route)
            self.assertEqual(response["error"]["code"], "cache_missing")
            self.assertIn("message", response["error"])
            self.assertEqual(response["call_ledger"][0]["api"], expected_api)
            self.assertIn(response["call_ledger"][0]["call_status"], {"cache_missing", "cache_ready"})
            self.assertFalse(response["call_ledger"][0]["external"])
            self.assertFalse(response["call_ledger"][0]["external_calls_triggered"])
            self.assertFalse(response["call_ledger"][0]["tushare_called"])
            self.assertFalse(response["call_ledger"][0]["deepseek_called"])
            self.assertFalse(response["call_ledger"][0]["github_called"])
            self.assertTrue(response["call_ledger"][0]["does_not_execute_trades"])
            self.assertTrue(response["call_ledger"][0]["does_not_modify_strategy_action"])

    def test_health_and_cache_endpoints(self):
        self._with_meta_store()
        self._with_parquet_root()
        health = self.client.get("/health").json()
        self.assertTrue(health["ok"])
        self.assertFalse(health["data"]["external_calls_on_startup"])
        self.assertFalse(health["data"]["deepseek_called"])
        self.assertFalse(health["data"]["tushare_called"])
        self.assertEqual(health["call_ledger"][0]["api"], "local_health_check")
        self.assertFalse(health["call_ledger"][0]["external"])
        self.assertIn("GET /health", health["warnings"][0])
        model_strategy = health["data"]["deepseek_model_strategy"]
        model_purposes = set(model_strategy) - {"source", "contains_secret"}
        self.assertEqual(
            model_purposes,
            {"default", "explain", "projection", "factor_explain", "fast", "healthcheck", "feeder"},
        )
        self.assertEqual(model_strategy["default"], model_strategy["explain"])
        self.assertEqual(model_strategy["projection"], model_strategy["explain"])
        self.assertEqual(model_strategy["factor_explain"], model_strategy["explain"])
        self.assertEqual(model_strategy["healthcheck"], model_strategy["fast"])
        self.assertEqual(model_strategy["feeder"], model_strategy["fast"])
        self.assertFalse(model_strategy["contains_secret"])
        self.assertNotIn("token", json.dumps(model_strategy, ensure_ascii=False).lower())
        self.assertNotIn("api_key", json.dumps(model_strategy, ensure_ascii=False).lower())

        audit = self.client.get("/api/audit/cache").json()
        self.assertTrue(audit["ok"])
        self.assertTrue(audit["data"]["cache_only"])
        self.assertFalse(audit["data"]["external_calls_triggered"])
        self.assertFalse(audit["data"]["tushare_called"])
        self.assertFalse(audit["data"]["deepseek_called"])
        self.assertFalse(audit["data"]["github_called"])
        self.assertTrue(audit["data"]["policy"]["audit_is_read_only"])
        self.assertTrue(audit["data"]["policy"]["post_task_required_for_external_work"])
        self.assertTrue(audit["data"]["does_not_execute_trades"])
        self.assertTrue(audit["data"]["does_not_modify_strategy_action"])

        factor = self.client.get("/api/factor-quant/cache").json()
        self.assertTrue(factor["ok"])
        self.assertEqual(factor["data"]["mode"], "cache_only")
        self.assertFalse(factor["data"]["external_calls_triggered"])

        market = self.client.get("/api/market/cache").json()
        self.assertTrue(market["ok"])
        self.assertTrue(market["data"]["cache_only"])
        self.assertFalse(market["data"]["external_calls_triggered"])
        self.assertFalse(market["data"]["tushare_called"])
        self.assertFalse(market["data"]["deepseek_called"])
        self.assertTrue(market["data"]["policy"]["does_not_refresh_quotes"])
        self.assertTrue(market["data"]["policy"]["market_context_is_not_trade_instruction"])
        self.assertTrue(market["data"]["does_not_modify_strategy_action"])
        self.assertTrue(market["data"]["does_not_execute_trades"])
        self.assertEqual(market["call_ledger"][0]["api"], "local_market_context_cache")
        self.assertFalse(market["call_ledger"][0]["external"])
        self.assertIn("GET /api/market/cache", market["warnings"][0])

        discipline = self.client.get("/api/discipline/cache").json()
        self.assertTrue(discipline["ok"])
        self.assertTrue(discipline["data"]["cache_only"])
        self.assertFalse(discipline["data"]["external_calls_triggered"])
        self.assertFalse(discipline["data"]["tushare_called"])
        self.assertFalse(discipline["data"]["deepseek_called"])
        self.assertTrue(discipline["data"]["policy"]["does_not_run_backtest"])
        self.assertTrue(discipline["data"]["policy"]["does_not_recompute_action"])
        self.assertTrue(discipline["data"]["does_not_modify_strategy_action"])
        self.assertTrue(discipline["data"]["does_not_execute_trades"])
        self.assertEqual(discipline["call_ledger"][0]["api"], "local_discipline_loop_cache")
        self.assertFalse(discipline["call_ledger"][0]["external"])
        self.assertIn("GET /api/discipline/cache", discipline["warnings"][0])

        serenity = self.client.get("/api/serenity/cache").json()
        self.assertTrue(serenity["ok"])
        self.assertFalse(serenity["data"]["deepseek_called"])
        self.assertEqual(serenity["call_ledger"][0]["api"], "local_serenity_method_radar_cache")
        self.assertFalse(serenity["call_ledger"][0]["external"])
        self.assertFalse(serenity["call_ledger"][0]["github_called"])
        self.assertIn("GET /api/serenity/cache", serenity["warnings"][0])

        chokepoint = self.client.get("/api/chokepoint/cache").json()
        if chokepoint["ok"]:
            self.assertFalse(chokepoint["data"]["deepseek_called"])
            self.assertFalse(chokepoint["data"]["enters_strategy_action"])
        else:
            self.assertIsNone(chokepoint["data"])
            self.assertEqual(chokepoint["error"]["code"], "cache_missing")
        self.assertEqual(chokepoint["call_ledger"][0]["api"], "local_chokepoint_scan_cache")
        self.assertFalse(chokepoint["call_ledger"][0]["external"])
        self.assertFalse(chokepoint["call_ledger"][0]["deepseek_called"])
        self.assertIn("GET /api/chokepoint/cache", chokepoint["warnings"][0])

        next_session = self.client.get("/api/next-session/cache").json()
        if next_session["ok"]:
            self.assertFalse(next_session["data"]["external_calls_triggered"])
        else:
            self.assertIsNone(next_session["data"])
            self.assertEqual(next_session["error"]["code"], "cache_missing")
        self.assertEqual(next_session["call_ledger"][0]["api"], "local_next_session_cache")
        self.assertFalse(next_session["call_ledger"][0]["external"])
        self.assertIn("GET /api/next-session/cache", next_session["warnings"][0])

        storage = self.client.get("/api/storage/factor-values").json()
        self.assertTrue(storage["ok"])
        self.assertTrue(storage["data"]["cache_only"])
        self.assertFalse(storage["data"]["external_calls_triggered"])
        self.assertEqual(storage["call_ledger"][0]["api"], "local_storage_factor_values_cache")
        self.assertFalse(storage["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/factor-values", storage["warnings"][0])

        sqlite_meta = self.client.get("/api/storage/sqlite-meta").json()
        self.assertTrue(sqlite_meta["ok"])
        self.assertTrue(sqlite_meta["data"]["cache_only"])
        self.assertFalse(sqlite_meta["data"]["external_calls_triggered"])
        self.assertTrue(sqlite_meta["data"].get("does_not_return_payload_json", True))
        self.assertEqual(sqlite_meta["call_ledger"][0]["api"], "local_storage_sqlite_meta_cache")
        self.assertFalse(sqlite_meta["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/sqlite-meta", sqlite_meta["warnings"][0])

        storage_overview = self.client.get("/api/storage").json()
        self.assertTrue(storage_overview["ok"])
        self.assertEqual(set(storage_overview["data"]["dataset_status"]), {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertEqual(storage_overview["data"]["dataset_count"], 6)
        self.assertEqual({item["dataset"] for item in storage_overview["data"]["dataset_catalog"]}, {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertIn("sqlite_meta", storage_overview["data"])
        self.assertEqual(storage_overview["data"]["schema_migration_preflight"]["status"], "preflight_ready")
        self.assertEqual(storage_overview["data"]["schema_migration_preflight"]["migration_executed_count"], 0)
        self.assertFalse(storage_overview["data"]["schema_migration_preflight"]["cache_get_writes_files"])
        self.assertEqual(storage_overview["data"]["storage_production_blocker_audit"]["status"], "storage_production_blocked")
        self.assertFalse(storage_overview["data"]["storage_production_blocker_audit"]["production_storage_complete"])
        self.assertTrue(storage_overview["data"]["storage_production_blocker_audit"]["dry_runs_are_not_production_completion"])
        self.assertGreaterEqual(storage_overview["data"]["storage_production_blocker_count"], 6)
        self.assertFalse(storage_overview["data"]["external_calls_triggered"])
        self.assertEqual(storage_overview["call_ledger"][0]["api"], "local_storage_overview_cache")
        self.assertFalse(storage_overview["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage", storage_overview["warnings"][0])

        storage_catalog = self.client.get("/api/storage/catalog").json()
        self.assertTrue(storage_catalog["ok"])
        self.assertTrue(storage_catalog["data"]["cache_only"])
        self.assertEqual(storage_catalog["data"]["status"], "ready")
        self.assertEqual(storage_catalog["data"]["dataset_count"], 6)
        self.assertEqual({item["dataset"] for item in storage_catalog["data"]["dataset_catalog"]}, {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal", "backtest_results"})
        self.assertFalse(storage_catalog["data"]["external_calls_triggered"])
        self.assertFalse(storage_catalog["data"]["tushare_called"])
        self.assertFalse(storage_catalog["data"]["deepseek_called"])
        self.assertFalse(storage_catalog["data"]["github_called"])
        self.assertEqual(storage_catalog["data"]["schema_migration_preflight"]["status"], "preflight_ready")
        self.assertEqual(storage_catalog["data"]["schema_migration_preflight"]["physical_validation_done_count"], 0)
        self.assertFalse(storage_catalog["data"]["schema_migration_preflight"]["external_calls_triggered"])
        self.assertEqual(storage_catalog["data"]["storage_production_blocker_audit"]["status"], "storage_production_blocked")
        self.assertFalse(storage_catalog["data"]["storage_production_blocker_audit"]["production_storage_complete"])
        self.assertEqual(storage_catalog["call_ledger"][0]["api"], "local_storage_dataset_catalog_cache")
        self.assertFalse(storage_catalog["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/catalog", storage_catalog["warnings"][0])

        daily_storage = self.client.get("/api/storage/daily").json()
        self.assertTrue(daily_storage["ok"])
        self.assertEqual(daily_storage["data"]["dataset"], "daily")
        self.assertFalse(daily_storage["data"]["external_calls_triggered"])
        self.assertEqual(daily_storage["call_ledger"][0]["api"], "local_storage_dataset_cache")
        self.assertFalse(daily_storage["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/daily", daily_storage["warnings"][0])

        daily_basic_storage = self.client.get("/api/storage/daily-basic").json()
        self.assertTrue(daily_basic_storage["ok"])
        self.assertEqual(daily_basic_storage["data"]["dataset"], "daily_basic")
        self.assertFalse(daily_basic_storage["data"]["external_calls_triggered"])
        self.assertEqual(daily_basic_storage["call_ledger"][0]["api"], "local_storage_dataset_cache")
        self.assertFalse(daily_basic_storage["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/daily_basic", daily_basic_storage["warnings"][0])

        trade_cal_storage = self.client.get("/api/storage/trade-cal").json()
        self.assertTrue(trade_cal_storage["ok"])
        self.assertEqual(trade_cal_storage["data"]["dataset"], "trade_cal")
        self.assertFalse(trade_cal_storage["data"]["external_calls_triggered"])
        self.assertEqual(trade_cal_storage["call_ledger"][0]["api"], "local_storage_dataset_cache")
        self.assertFalse(trade_cal_storage["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/trade_cal", trade_cal_storage["warnings"][0])

        backtest_storage = self.client.get("/api/storage/backtest-results").json()
        self.assertTrue(backtest_storage["ok"])
        self.assertEqual(backtest_storage["data"]["dataset"], "backtest_results")
        self.assertFalse(backtest_storage["data"]["external_calls_triggered"])
        self.assertEqual(backtest_storage["call_ledger"][0]["api"], "local_storage_dataset_cache")
        self.assertFalse(backtest_storage["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/backtest_results", backtest_storage["warnings"][0])

        if importlib.util.find_spec("duckdb") is not None and importlib.util.find_spec("pyarrow") is not None and importlib.util.find_spec("pandas") is not None:
            import pandas as pd

            root = self._with_parquet_root()
            storage_service.parquet_store.write_dataset(
                pd.DataFrame(
                    {
                        "ts_code": ["002008.SZ", "002008.SZ", "600519.SH"],
                        "trade_date": ["20260603", "20260611", "20260611"],
                        "close": [10.1, 10.8, 1600.0],
                    }
                ),
                root=root,
                name="daily",
            )
            filtered_storage = self.client.get(
                "/api/storage/daily",
                params={"ts_code": "002008.SZ", "start_date": "2026-06-01", "end_date": "2026-06-10", "limit": 10},
            ).json()
            self.assertTrue(filtered_storage["ok"])
            self.assertEqual(filtered_storage["data"]["query_wrapper"], "duckdb_filtered_parquet.v1")
            self.assertEqual(filtered_storage["data"]["row_count"], 1)
            self.assertEqual(filtered_storage["data"]["query"]["rows"][0]["ts_code"], "002008.SZ")
            self.assertEqual(filtered_storage["data"]["query"]["rows"][0]["trade_date"], "20260603")
            self.assertEqual(filtered_storage["data"]["query_result_contract"]["schema_version"], "duckdb_query_result_contract.v1")
            self.assertEqual(filtered_storage["data"]["query_result_contract"]["row_count"], 1)
            self.assertEqual(filtered_storage["data"]["query_result_contract"]["returned_row_count"], 1)
            self.assertEqual(filtered_storage["data"]["query_result_contract"]["limit"], 10)
            self.assertFalse(filtered_storage["data"]["query_result_contract"]["has_more"])
            self.assertIn("ts_code", filtered_storage["data"]["query_result_contract"]["projected_columns"])
            self.assertIn("trade_date", filtered_storage["data"]["query_result_contract"]["projected_columns"])
            self.assertIn("close", filtered_storage["data"]["query_result_contract"]["projected_columns"])
            self.assertIn("open", filtered_storage["data"]["query_result_contract"]["missing_projected_columns"])
            self.assertEqual(filtered_storage["data"]["page_info"]["cursor_status"], "not_provided")
            self.assertFalse(filtered_storage["data"]["page_info"]["has_more"])
            self.assertEqual(filtered_storage["data"]["query_service_policy"]["cursor_pagination"], "offset_cursor")
            self.assertTrue(filtered_storage["data"]["query_service_policy"]["typed_projection_enabled"])
            self.assertTrue(filtered_storage["data"]["query_service_policy"]["query_result_contract_enabled"])
            self.assertTrue(filtered_storage["data"]["query_service_policy"]["cursor_pagination_enabled"])
            self.assertEqual({item["filter"] for item in filtered_storage["data"]["applied_filters"]}, {"ts_code", "start_date", "end_date"})
            self.assertFalse(filtered_storage["data"]["skipped_filters"])
            self.assertFalse(filtered_storage["data"]["external_calls_triggered"])
            self.assertFalse(filtered_storage["data"]["tushare_called"])
            self.assertFalse(filtered_storage["data"]["deepseek_called"])
            self.assertFalse(filtered_storage["data"]["github_called"])
            self.assertTrue(filtered_storage["data"]["does_not_modify_strategy_action"])
            self.assertTrue(filtered_storage["data"]["does_not_execute_trades"])
            self.assertEqual(filtered_storage["call_ledger"][0]["api"], "local_storage_dataset_cache")
            self.assertFalse(filtered_storage["call_ledger"][0]["external"])

            first_page = self.client.get("/api/storage/daily", params={"limit": 1}).json()
            self.assertTrue(first_page["ok"])
            self.assertEqual(first_page["data"]["row_count"], 1)
            self.assertTrue(first_page["data"]["page_info"]["has_more"])
            self.assertEqual(first_page["data"]["page_info"]["next_cursor"], "offset:1")
            self.assertEqual(first_page["data"]["query_result_contract"]["next_cursor"], "offset:1")
            self.assertEqual(first_page["data"]["query"]["rows"][0]["trade_date"], "20260603")
            self.assertEqual(first_page["data"]["query_result_contract"]["order_columns"], ["trade_date", "ts_code"])
            self.assertFalse(first_page["data"]["external_calls_triggered"])

            second_page = self.client.get("/api/storage/daily", params={"limit": 1, "cursor": "offset:1"}).json()
            self.assertTrue(second_page["ok"])
            self.assertEqual(second_page["data"]["page_info"]["cursor"], "offset:1")
            self.assertEqual(second_page["data"]["page_info"]["cursor_status"], "accepted")
            self.assertEqual(second_page["data"]["page_info"]["offset"], 1)
            self.assertEqual(second_page["data"]["query"]["rows"][0]["trade_date"], "20260611")
            self.assertEqual(second_page["data"]["query_result_contract"]["offset"], 1)
            self.assertFalse(second_page["data"]["external_calls_triggered"])

        migration = self.client.get("/api/migration/status").json()
        self.assertTrue(migration["ok"])
        self.assertEqual(migration["data"]["status"], "active_migration")
        self.assertEqual(len(migration["data"]["progress_baseline"]), 11)
        self.assertTrue(migration["data"]["baseline_policy"]["do_not_reestimate_every_turn"])
        self.assertIn("不使用 git add .。", migration["data"]["principles"])
        self.assertIn("不 push，等待用户确认。", migration["data"]["principles"])
        self.assertTrue(migration["data"]["api_policy"]["cache_only"])
        self.assertFalse(migration["data"]["api_policy"]["external_calls_triggered"])
        self.assertTrue(migration["data"]["api_policy"]["does_not_execute_trades"])
        self.assertEqual(migration["call_ledger"][0]["api"], "local_migration_status_cache")
        self.assertFalse(migration["call_ledger"][0]["external"])
        self.assertIn("GET /api/migration/status", migration["warnings"][0])

        model_strategy = self.client.get("/api/model-strategy/cache").json()
        self.assertTrue(model_strategy["ok"])
        self.assertTrue(model_strategy["data"]["cache_only"])
        self.assertTrue(model_strategy["data"]["read_only"])
        self.assertEqual(model_strategy["data"]["mode"], "cache_only")
        self.assertEqual(model_strategy["data"]["counts"]["purpose_count"], 7)
        self.assertEqual(
            set(model_strategy["data"]["purpose_groups"]["explain_grade"]),
            {"default", "explain", "projection", "factor_explain"},
        )
        self.assertEqual(
            set(model_strategy["data"]["purpose_groups"]["fast_grade"]),
            {"fast", "healthcheck", "feeder"},
        )
        for row in model_strategy["data"]["model_rows"]:
            self.assertTrue(row["does_not_hardcode_model"])
            self.assertFalse(row["contains_secret"])
            self.assertFalse(row["external_call_on_cache_read"])
            self.assertTrue(row["config_keys"])
        self.assertFalse(model_strategy["data"]["external_calls_triggered"])
        self.assertFalse(model_strategy["data"]["tushare_called"])
        self.assertFalse(model_strategy["data"]["deepseek_called"])
        self.assertFalse(model_strategy["data"]["github_called"])
        self.assertTrue(model_strategy["data"]["policy"]["does_not_call_deepseek"])
        self.assertTrue(model_strategy["data"]["policy"]["does_not_read_api_keys"])
        self.assertTrue(model_strategy["data"]["policy"]["model_names_are_configurable"])
        self.assertFalse(model_strategy["data"]["policy"]["callsite_hardcoding_allowed"])
        self.assertEqual(model_strategy["data"]["call_ledger"][0]["api"], "local_deepseek_model_strategy_cache")
        self.assertEqual(model_strategy["call_ledger"][0]["api"], "local_deepseek_model_strategy_cache")
        self.assertFalse(model_strategy["call_ledger"][0]["external"])
        self.assertIn("GET /api/model-strategy/cache", model_strategy["warnings"][0])

        legacy = self.client.get("/api/legacy/cache").json()
        self.assertTrue(legacy["ok"])
        self.assertTrue(legacy["data"]["cache_only"])
        self.assertFalse(legacy["data"]["external_calls_triggered"])
        self.assertFalse(legacy["data"]["tushare_called"])
        self.assertFalse(legacy["data"]["deepseek_called"])
        self.assertTrue(legacy["data"]["policy"]["does_not_open_streamlit"])
        self.assertTrue(legacy["data"]["policy"]["does_not_run_legacy_tools"])
        self.assertTrue(legacy["data"]["policy"]["react_tauri_is_primary_entry"])
        self.assertFalse(legacy["data"]["policy"]["streamlit_is_official_primary_entry"])
        self.assertFalse(legacy["data"]["policy"]["legacy_startup_task_creation"])
        self.assertFalse(legacy["data"]["policy"]["legacy_can_bypass_guardrails"])
        self.assertEqual(
            legacy["data"]["primary_workflow_exit_audit"]["status"],
            "ordinary_workflow_exit_partial_fallback_required",
        )
        self.assertFalse(legacy["data"]["primary_workflow_exit_audit"]["ordinary_workflow_exit_complete"])
        self.assertTrue(legacy["data"]["primary_workflow_exit_audit"]["streamlit_fallback_retained"])
        self.assertFalse(legacy["data"]["primary_workflow_exit_audit"]["streamlit_fallback_removal_ready"])
        self.assertGreater(legacy["data"]["primary_workflow_exit_audit"]["ordinary_workflow_still_needs_fallback_count"], 0)
        fallback_contract = legacy["data"]["streamlit_fallback_dependency_contract"]
        self.assertEqual(fallback_contract["schema_version"], "streamlit_fallback_dependency_contract.v1")
        self.assertEqual(fallback_contract["status"], "streamlit_fallback_dependencies_visible_retirement_pending")
        self.assertEqual(fallback_contract["scope"], "local_route_dependency_contract_not_streamlit_execution")
        self.assertFalse(fallback_contract["ordinary_primary_exit_ready"])
        self.assertFalse(fallback_contract["full_streamlit_removal_ready"])
        self.assertGreater(fallback_contract["ordinary_fallback_dependency_count"], 0)
        self.assertGreater(fallback_contract["full_streamlit_removal_blocker_count"], 0)
        self.assertIn("candidate_radar_quick_scan", fallback_contract["ordinary_blocking_workflows"])
        self.assertIn("legacy_admin_debug_tools", fallback_contract["full_removal_blocking_workflows"])
        self.assertFalse(fallback_contract["external_calls_triggered"])
        self.assertFalse(fallback_contract["tushare_called"])
        self.assertFalse(fallback_contract["deepseek_called"])
        self.assertFalse(fallback_contract["github_called"])
        self.assertTrue(fallback_contract["does_not_open_streamlit"])
        self.assertTrue(fallback_contract["does_not_run_legacy_tools"])
        self.assertTrue(fallback_contract["does_not_create_tasks"])
        self.assertTrue(fallback_contract["does_not_execute_trades"])
        self.assertTrue(fallback_contract["does_not_modify_strategy_action"])
        self.assertTrue(legacy["data"]["does_not_modify_strategy_action"])

        task_catalog = self.client.get("/api/tasks/catalog").json()
        self.assertTrue(task_catalog["ok"])
        self.assertEqual(task_catalog["data"]["task_count"], 16)
        self.assertIn("POST /api/factor-quant/universe-research-plan", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertIn("POST /api/tasks/refresh-tushare-facts", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertIn("POST /api/candidate-radar/scan-quick", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertIn("POST /api/candidate-radar/full-pool-plan", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertIn("POST /api/candidate-radar/deep-scan-plan", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertIn("POST /api/storage/artifact-hygiene/dry-run", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertIn("POST /api/storage/schema-validation/dry-run", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertIn("POST /api/storage/partition-migration/dry-run", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertIn("POST /api/storage/compaction/dry-run", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertIn("POST /api/storage/cache-ttl/dry-run", task_catalog["data"]["route_coverage"]["known_post_routes"])
        self.assertTrue(task_catalog["data"]["policy"]["get_catalog_cache_only"])
        self.assertTrue(task_catalog["data"]["policy"]["all_tasks_button_gated"])
        self.assertTrue(task_catalog["data"]["policy"]["call_ledger_required_for_all"])
        self.assertFalse(task_catalog["data"]["external_calls_triggered"])
        self.assertFalse(task_catalog["data"]["tushare_called"])
        self.assertFalse(task_catalog["data"]["deepseek_called"])
        self.assertFalse(task_catalog["data"]["github_called"])
        self.assertEqual(task_catalog["call_ledger"][0]["api"], "local_task_catalog_cache")
        self.assertEqual(task_catalog["call_ledger"][0]["call_status"], "cache_read")
        self.assertFalse(task_catalog["call_ledger"][0]["external"])
        self.assertIn("GET /api/tasks/catalog", task_catalog["warnings"][0])

        original_runner = tushare_task_service.run_tushare_refresh_task

        def fake_runner(payload=None):
            task = task_service.build_task_record(
                "refresh_tushare_facts",
                output_packet_key="command_center_tushare_refresh_packet",
                payload=payload,
                status="success",
                progress=1.0,
                current_step="tushare_refresh_completed",
                call_ledger=[
                    {
                        "api": "daily",
                        "request_params_safe": {"ts_code": "002008.SZ"},
                        "row_count": 1,
                        "data_date": "20260610",
                        "local_fetched_at": "2026-06-10T15:00:00",
                        "call_status": "success",
                        "error_message_safe": "",
                        "external": True,
                        "external_calls_triggered": True,
                        "tushare_called": True,
                        "deepseek_called": False,
                        "github_called": False,
                        "does_not_execute_trades": True,
                        "does_not_modify_strategy_action": True,
                    }
                ],
            )
            task["external_calls_triggered"] = True
            task["tushare_called"] = True
            return task

        tushare_task_service.run_tushare_refresh_task = fake_runner
        self.addCleanup(setattr, tushare_task_service, "run_tushare_refresh_task", original_runner)

        refresh_response = self.client.post(
            "/api/tasks/refresh-tushare-facts",
            json={"ts_code": "002008.SZ", "token": "SHOULD_DROP"},
        ).json()
        self.assertTrue(refresh_response["ok"])
        self.assertTrue(refresh_response["data"]["task_id"].startswith("local-"))
        refresh_task = refresh_response["data"]["task"]
        self.assertEqual(refresh_task["task_type"], "refresh_tushare_facts")
        self.assertTrue(refresh_task["call_ledger"][0]["tushare_called"])
        self.assertTrue(refresh_task["call_ledger"][0]["external_calls_triggered"])
        self.assertTrue(refresh_task["call_ledger"][0]["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(refresh_response, ensure_ascii=False))

        worker = self.client.get("/api/worker/cache").json()
        self.assertTrue(worker["ok"])
        self.assertTrue(worker["data"]["cache_only"])
        self.assertFalse(worker["data"]["external_calls_triggered"])
        self.assertFalse(worker["data"]["redis_pinged"])
        self.assertFalse(worker["data"]["tushare_called"])
        self.assertFalse(worker["data"]["deepseek_called"])
        self.assertFalse(worker["data"]["github_called"])
        self.assertTrue(worker["data"]["runtime"]["local_fallback_enabled"])
        self.assertFalse(worker["data"]["runtime"]["celery_worker_started"])
        self.assertFalse(worker["data"]["runtime"]["scheduler_started"])
        self.assertTrue(worker["data"]["policy"]["does_not_ping_redis"])
        self.assertTrue(worker["data"]["policy"]["does_not_start_celery_worker"])
        self.assertTrue(worker["data"]["does_not_modify_strategy_action"])
        self.assertTrue(worker["data"]["does_not_execute_trades"])

        trade_review = self.client.get("/api/trade-review/cache").json()
        self.assertTrue(trade_review["ok"])
        self.assertTrue(trade_review["data"]["cache_only"])
        self.assertFalse(trade_review["data"]["external_calls_triggered"])
        self.assertFalse(trade_review["data"]["tushare_called"])
        self.assertFalse(trade_review["data"]["deepseek_called"])
        self.assertTrue(trade_review["data"]["does_not_execute_trades"])
        self.assertEqual(trade_review["call_ledger"][0]["api"], "local_trade_review_log")
        self.assertFalse(trade_review["call_ledger"][0]["external"])
        self.assertIn("GET /api/trade-review/cache", trade_review["warnings"][0])

        quant = self.client.get("/api/quant/cache").json()
        self.assertTrue(quant["ok"])
        self.assertTrue(quant["data"]["cache_only"])
        self.assertTrue(quant["data"]["policy"]["does_not_run_backtest"])
        self.assertFalse(quant["data"]["external_calls_triggered"])
        self.assertFalse(quant["data"]["tushare_called"])
        self.assertFalse(quant["data"]["deepseek_called"])
        self.assertTrue(quant["data"]["does_not_modify_strategy_action"])
        self.assertEqual(quant["call_ledger"][0]["api"], "local_quant_backtest_cache")
        self.assertFalse(quant["call_ledger"][0]["external"])
        self.assertIn("GET /api/quant/cache", quant["warnings"][0])

        strategy = self.client.get("/api/strategy/cache").json()
        self.assertTrue(strategy["ok"])
        self.assertTrue(strategy["data"]["cache_only"])
        self.assertFalse(strategy["data"]["external_calls_triggered"])
        self.assertFalse(strategy["data"]["tushare_called"])
        self.assertFalse(strategy["data"]["deepseek_called"])
        self.assertTrue(strategy["data"]["policy"]["does_not_run_backtest"])
        self.assertTrue(strategy["data"]["does_not_modify_strategy_action"])
        self.assertTrue(strategy["data"]["does_not_execute_trades"])
        self.assertEqual(strategy["call_ledger"][0]["api"], "local_strategy_trace_cache")
        self.assertFalse(strategy["call_ledger"][0]["external"])
        self.assertIn("GET /api/strategy/cache", strategy["warnings"][0])

        position = self.client.get("/api/position/cache").json()
        self.assertTrue(position["ok"])
        self.assertTrue(position["data"]["cache_only"])
        self.assertFalse(position["data"]["external_calls_triggered"])
        self.assertFalse(position["data"]["tushare_called"])
        self.assertFalse(position["data"]["deepseek_called"])
        self.assertTrue(position["data"]["policy"]["does_not_recalculate_position"])
        self.assertTrue(position["data"]["does_not_modify_strategy_action"])
        self.assertTrue(position["data"]["does_not_modify_holdings"])
        self.assertTrue(position["data"]["does_not_execute_trades"])
        self.assertEqual(position["call_ledger"][0]["api"], "local_position_context_cache")
        self.assertFalse(position["call_ledger"][0]["external"])
        self.assertIn("GET /api/position/cache", position["warnings"][0])

        candidate = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(candidate["ok"])
        self.assertTrue(candidate["data"]["cache_only"])
        self.assertFalse(candidate["data"]["external_calls_triggered"])
        self.assertFalse(candidate["data"]["tushare_called"])
        self.assertFalse(candidate["data"]["deepseek_called"])
        self.assertTrue(candidate["data"]["policy"]["does_not_scan_market"])
        self.assertTrue(candidate["data"]["policy"]["candidate_is_not_buy_instruction"])
        self.assertTrue(candidate["data"]["does_not_modify_strategy_action"])
        self.assertTrue(candidate["data"]["does_not_execute_trades"])
        self.assertEqual(candidate["call_ledger"][0]["api"], "local_candidate_radar_cache")
        self.assertFalse(candidate["call_ledger"][0]["external"])
        self.assertIn("GET /api/candidate-radar/cache", candidate["warnings"][0])

        risk = self.client.get("/api/risk/cache").json()
        self.assertTrue(risk["ok"])
        self.assertTrue(risk["data"]["cache_only"])
        self.assertFalse(risk["data"]["external_calls_triggered"])
        self.assertFalse(risk["data"]["tushare_called"])
        self.assertFalse(risk["data"]["deepseek_called"])
        self.assertTrue(risk["data"]["policy"]["does_not_clear_risk_flags"])
        self.assertTrue(risk["data"]["policy"]["risk_guardrails_are_not_trade_orders"])
        self.assertTrue(risk["data"]["does_not_modify_strategy_action"])
        self.assertTrue(risk["data"]["does_not_modify_holdings"])
        self.assertTrue(risk["data"]["does_not_execute_trades"])
        self.assertEqual(risk["call_ledger"][0]["api"], "local_risk_guardrails_cache")
        self.assertFalse(risk["call_ledger"][0]["external"])
        self.assertIn("GET /api/risk/cache", risk["warnings"][0])

        evidence = self.client.get("/api/evidence/cache").json()
        self.assertTrue(evidence["ok"])
        self.assertTrue(evidence["data"]["cache_only"])
        self.assertFalse(evidence["data"]["external_calls_triggered"])
        self.assertFalse(evidence["data"]["tushare_called"])
        self.assertFalse(evidence["data"]["deepseek_called"])
        self.assertTrue(evidence["data"]["does_not_modify_strategy_action"])

        data_capability = self.client.get("/api/data-capability/cache").json()
        self.assertTrue(data_capability["ok"])
        self.assertTrue(data_capability["data"]["cache_only"])
        self.assertFalse(data_capability["data"]["external_calls_triggered"])
        self.assertFalse(data_capability["data"]["tushare_called"])
        self.assertFalse(data_capability["data"]["deepseek_called"])
        self.assertTrue(data_capability["data"]["policy"]["does_not_ping_tushare"])
        self.assertTrue(data_capability["data"]["does_not_modify_strategy_action"])

        data_health = self.client.get("/api/data-health/cache").json()
        self.assertTrue(data_health["ok"])
        self.assertTrue(data_health["data"]["cache_only"])
        self.assertFalse(data_health["data"]["external_calls_triggered"])
        self.assertFalse(data_health["data"]["tushare_called"])
        self.assertFalse(data_health["data"]["deepseek_called"])
        self.assertFalse(data_health["data"]["github_called"])
        self.assertTrue(data_health["data"]["policy"]["does_not_ping_tushare"])
        self.assertTrue(data_health["data"]["policy"]["does_not_ping_supabase"])
        self.assertTrue(data_health["data"]["policy"]["does_not_refresh_data"])
        self.assertTrue(data_health["data"]["policy"]["post_task_required_for_provider_probe"])
        self.assertTrue(data_health["data"]["policy"]["freshness_acceptance_matrix_is_local_contract"])
        self.assertFalse(data_health["data"]["policy"]["freshness_acceptance_matrix_calls_trade_cal"])
        self.assertTrue(data_health["data"]["policy"]["freshness_long_window_sample_is_local_fixture"])
        self.assertTrue(data_health["data"]["policy"]["freshness_long_window_sample_uses_actual_gate"])
        self.assertFalse(data_health["data"]["policy"]["freshness_long_window_sample_calls_trade_cal"])
        self.assertIn("trade_cal_physical_validation", data_health["data"])
        self.assertTrue(data_health["data"]["policy"]["trade_cal_physical_validation_is_local_artifact"])
        self.assertFalse(data_health["data"]["policy"]["trade_cal_physical_validation_calls_trade_cal_provider"])
        self.assertFalse(data_health["data"]["policy"]["real_trade_cal_long_window_validation_done"])
        self.assertEqual(
            data_health["data"]["freshness_long_window_sample_validation"]["status"],
            "local_sample_validation_passed",
        )
        self.assertTrue(data_health["data"]["does_not_modify_strategy_action"])
        self.assertTrue(data_health["data"]["does_not_execute_trades"])

        desktop = self.client.get("/api/desktop/preflight-cache").json()
        self.assertTrue(desktop["ok"])
        self.assertTrue(desktop["data"]["cache_only"])
        self.assertTrue(desktop["data"]["read_only"])
        self.assertEqual(desktop["data"]["mode"], "cache_only")
        self.assertFalse(desktop["data"]["external_calls_triggered"])
        self.assertFalse(desktop["data"]["tushare_called"])
        self.assertFalse(desktop["data"]["deepseek_called"])
        self.assertFalse(desktop["data"]["github_called"])
        self.assertTrue(desktop["data"]["policy"]["does_not_run_npm_install"])
        self.assertTrue(desktop["data"]["policy"]["does_not_run_npm_build"])
        self.assertTrue(desktop["data"]["policy"]["does_not_run_tauri"])
        self.assertTrue(desktop["data"]["policy"]["does_not_run_cargo"])
        self.assertTrue(desktop["data"]["does_not_modify_strategy_action"])
        self.assertTrue(desktop["data"]["does_not_execute_trades"])
        self.assertEqual(desktop["data"]["call_ledger"][0]["api"], "local_desktop_shell_preflight_cache")
        self.assertEqual(desktop["call_ledger"][0]["api"], "local_desktop_shell_preflight_cache")
        self.assertFalse(desktop["call_ledger"][0]["external"])
        self.assertIn("GET /api/desktop/preflight-cache", desktop["warnings"][0])

        recovery = self.client.get("/api/recovery/cache").json()
        self.assertTrue(recovery["ok"])
        self.assertTrue(recovery["data"]["cache_only"])
        self.assertFalse(recovery["data"]["external_calls_triggered"])
        self.assertFalse(recovery["data"]["tushare_called"])
        self.assertFalse(recovery["data"]["deepseek_called"])
        self.assertTrue(recovery["data"]["policy"]["does_not_run_recovery_actions"])
        self.assertTrue(recovery["data"]["policy"]["recovery_actions_are_manual_guidance"])
        self.assertTrue(recovery["data"]["does_not_modify_strategy_action"])
        self.assertTrue(recovery["data"]["does_not_execute_trades"])

    def test_trade_review_cache_endpoint_returns_sanitized_local_records(self):
        self._with_trade_review_log(
            [
                {
                    "id": "r2",
                    "created_at": "2026-06-10T10:00:00",
                    "ticker": "002008.SZ",
                    "user_decision": "观察",
                    "overall_action": "等待",
                    "authorization": "Bearer SHOULD_DROP",
                    "user_note": "不要追高",
                }
            ]
        )

        response = self.client.get("/api/trade-review/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_trade_review_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["record_count"], 1)
        self.assertEqual(packet["records"][0]["ticker"], "002008.SZ")
        self.assertNotIn("authorization", packet["records"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_trade_review_log")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/trade-review/cache", response["warnings"][0])

    def test_quant_cache_endpoint_returns_cached_quant_without_external_work(self):
        self._with_snapshot_cache(
            {
                "quant_packet": {
                    "status": "ready",
                    "score": 71,
                    "confidence": "中",
                    "action_state": "只观察",
                    "authorization": "Bearer SHOULD_DROP",
                }
            }
        )

        response = self.client.get("/api/quant/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_quant_backtest_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["quant_packet"]["score"], 71)
        self.assertNotIn("authorization", packet["quant_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_run_backtest"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_quant_backtest_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/quant/cache", response["warnings"][0])

    def test_market_context_cache_endpoint_returns_local_market_context(self):
        self._with_snapshot_cache(
            {
                "market_packet": {"status": "ready", "summary": "市场缓存", "trade_date": "20260610"},
                "moneyflow_packet": {"status": "ready", "main_net_yi": 1.1, "authorization": "Bearer SHOULD_DROP"},
                "limit_emotion_packet": {"status": "ready", "emotion_state": "偏强"},
            }
        )

        response = self.client.get("/api/market/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_market_context_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["trade_date"], "20260610")
        self.assertGreaterEqual(packet["counts"]["packet_count"], 3)
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_refresh_moneyflow"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_market_context_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/market/cache", response["warnings"][0])

    def test_discipline_loop_cache_endpoint_returns_local_discipline_context(self):
        self._with_snapshot_cache(
            {
                "discipline_packet": {"status": "ready", "score": 66, "key_rules": ["不追高"]},
                "decision_loop_status": {"status": "ready", "ready_count": 1, "blocked_count": 0},
                "full_refresh_steps": [{"key": "market", "status": "completed"}],
                "decision_packet": {"overall_action": "只观察", "authorization": "Bearer SHOULD_DROP"},
            }
        )

        response = self.client.get("/api/discipline/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_discipline_loop_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["discipline_packet"]["score"], 66)
        self.assertEqual(packet["counts"]["discipline_rule_count"], 1)
        self.assertEqual(packet["counts"]["refresh_step_count"], 1)
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_run_backtest"])
        self.assertTrue(packet["policy"]["does_not_run_full_refresh"])
        self.assertTrue(packet["policy"]["does_not_recompute_action"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_discipline_loop_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/discipline/cache", response["warnings"][0])

    def test_legacy_bridge_cache_endpoint_returns_legacy_migration_context(self):
        self._with_snapshot_cache(
            {
                "legacy_packet_migration_checklist": {
                    "items": [{"label": "策略 Trace", "status": "done", "authorization": "Bearer SHOULD_DROP"}]
                },
                "old_workspace_packet_bridge": {"items": [{"label": "旧 packet 桥接"}]},
                "old_workspace_capability_overview": {"checklist_done_count": 1, "checklist_pending_count": 0},
            }
        )

        response = self.client.get("/api/legacy/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_legacy_bridge_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["counts"]["checklist_item_count"], 1)
        self.assertEqual(packet["counts"]["bridge_item_count"], 1)
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_open_streamlit"])
        self.assertTrue(packet["policy"]["does_not_run_legacy_tools"])
        self.assertEqual(packet["primary_workflow_exit_audit"]["status"], "ordinary_workflow_exit_partial_fallback_required")
        self.assertFalse(packet["primary_workflow_exit_audit"]["ordinary_workflow_exit_complete"])
        self.assertTrue(packet["primary_workflow_exit_audit"]["does_not_open_streamlit"])
        self.assertTrue(packet["primary_workflow_exit_audit"]["does_not_run_legacy_tools"])
        fallback_contract = packet["streamlit_fallback_dependency_contract"]
        self.assertEqual(fallback_contract["schema_version"], "streamlit_fallback_dependency_contract.v1")
        self.assertFalse(fallback_contract["ordinary_primary_exit_ready"])
        self.assertFalse(fallback_contract["full_streamlit_removal_ready"])
        self.assertGreater(fallback_contract["full_streamlit_removal_blocker_count"], 0)
        dependency_rows = {row["workflow"]: row for row in packet["streamlit_fallback_dependency_rows"]}
        self.assertEqual(dependency_rows["candidate_radar_quick_scan"]["dependency_class"], "ordinary_flow_partial_fallback_required")
        self.assertEqual(dependency_rows["legacy_admin_debug_tools"]["dependency_class"], "legacy_admin_debug_retained")
        self.assertTrue(dependency_rows["home_status"]["replacement_must_preserve_features"])
        self.assertTrue(fallback_contract["does_not_open_streamlit"])
        self.assertTrue(fallback_contract["does_not_run_legacy_tools"])
        self.assertTrue(fallback_contract["does_not_create_tasks"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_legacy_bridge_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/legacy/cache", response["warnings"][0])

    def test_strategy_trace_cache_endpoint_returns_strategy_trace_without_external_work(self):
        self._with_snapshot_cache(
            {
                "strategy_packet": {
                    "status": "ready",
                    "action": "等待",
                    "confidence": "中",
                    "summary": "本地规则等待",
                    "authorization": "Bearer SHOULD_DROP",
                },
                "decision_packet": {
                    "status": "ready",
                    "overall_action": "只观察",
                    "api_key": "SHOULD_DROP",
                },
            }
        )

        response = self.client.get("/api/strategy/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_strategy_trace_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["action_summary"]["action"], "等待")
        self.assertEqual(packet["decision_summary"]["overall_action"], "只观察")
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_call_deepseek"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_strategy_trace_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/strategy/cache", response["warnings"][0])

    def test_position_context_cache_endpoint_returns_position_without_external_work(self):
        self._with_snapshot_cache(
            {
                "holding_action": {
                    "ticker": "002008.SZ",
                    "shares": 1200,
                    "cost": 105,
                    "current_price": 111,
                    "action_state": "只观察",
                    "authorization": "Bearer SHOULD_DROP",
                },
                "position_risk_budget": {"risk_level": "中"},
                "today_action": {"overall_action": "只观察"},
                "strategy_packet": {"action": "等待"},
            }
        )

        response = self.client.get("/api/position/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_position_context_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["position_summary"]["ticker"], "002008.SZ")
        self.assertEqual(packet["holding_action"]["shares"], 1200)
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_recalculate_position"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_position_context_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/position/cache", response["warnings"][0])

    def test_candidate_radar_cache_endpoint_returns_candidates_without_external_work(self):
        self._with_snapshot_cache(
            {
                "radar_packet": {"status": "ready", "summary": "候选缓存", "authorization": "Bearer SHOULD_DROP"},
                "next_ticket_candidates": [
                    {"rank": 1, "ticker": "002837.SZ", "name": "英维克", "score": 47, "action_state": "只观察"}
                ],
                "a_share_capability_matrix": [
                    {"provider": "Tushare", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "api": "top_inst", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "api": "cyq_chips", "capability_state": "stale_cache", "status": "使用缓存"},
                ],
            }
        )

        response = self.client.get("/api/candidate-radar/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["candidate_rows"][0]["ticker"], "002837.SZ")
        self.assertEqual(packet["coverage_detail_summary"]["provider_blocked_group_count"], 1)
        self.assertEqual(packet["coverage_detail_summary"]["stale_input_group_count"], 1)
        self.assertGreaterEqual(packet["coverage_detail_summary"]["missing_provider_data_group_count"], 1)
        self.assertIn("provider_coverage_rows", packet)
        self.assertIn("degraded_mode_rows", packet)
        self.assertEqual(packet["fast_scan_readiness_audit"]["schema_version"], "candidate_radar_fast_scan_readiness.v1")
        self.assertEqual(packet["fast_scan_readiness_audit"]["status"], "fast_scan_local_ready_full_pool_pending")
        self.assertTrue(packet["fast_scan_readiness_audit"]["local_fast_scan_ready"])
        self.assertFalse(packet["fast_scan_readiness_audit"]["production_radar_replacement_complete"])
        self.assertFalse(packet["fast_scan_readiness_audit"]["full_pool_scan_done"])
        self.assertFalse(packet["fast_scan_readiness_audit"]["deep_scan_done"])
        self.assertFalse(packet["fast_scan_readiness_audit"]["provider_backed_acceptance_done"])
        self.assertEqual(packet["fast_scan_readiness_audit"]["blocking_criterion_count"], 0)
        fast_rows = {row["criterion"]: row for row in packet["fast_scan_readiness_rows"]}
        self.assertEqual(fast_rows["page_render_does_not_scan"]["status"], "passed")
        self.assertEqual(fast_rows["local_scan_modes_supported"]["status"], "passed")
        self.assertEqual(fast_rows["provider_gap_visible"]["status"], "gap_reported")
        self.assertEqual(fast_rows["production_full_replacement_pending"]["status"], "pending")
        browser_qa = packet["candidate_browser_qa_runbook_contract"]
        self.assertEqual(browser_qa["schema_version"], "candidate_radar_browser_qa_runbook.v1")
        self.assertEqual(browser_qa["status"], "candidate_radar_browser_qa_runbook_ready_execution_pending")
        self.assertTrue(browser_qa["local_runbook_ready"])
        self.assertTrue(browser_qa["runner_available"])
        self.assertTrue(browser_qa["candidate_route_source_ready"])
        self.assertEqual(browser_qa["candidate_route"], "#candidates")
        self.assertEqual(browser_qa["qa_matrix_count"], 4)
        self.assertFalse(browser_qa["visual_qa_complete"])
        self.assertFalse(browser_qa["browser_performance_trace_done"])
        self.assertFalse(browser_qa["browser_visual_delta_qa_done"])
        self.assertFalse(browser_qa["production_radar_replacement_complete"])
        self.assertFalse(browser_qa["legacy_retirement_ready"])
        self.assertFalse(browser_qa["external_calls_triggered"])
        self.assertFalse(browser_qa["tushare_called"])
        self.assertFalse(browser_qa["deepseek_called"])
        self.assertFalse(browser_qa["github_called"])
        self.assertTrue(browser_qa["does_not_execute_trades"])
        self.assertEqual(len(packet["candidate_browser_qa_matrix_rows"]), 4)
        self.assertEqual(packet["counts"]["candidate_browser_qa_matrix_count"], 4)
        self.assertTrue(packet["policy"]["candidate_browser_qa_runbook_contract_is_local"])
        self.assertTrue(packet["policy"]["candidate_browser_qa_runbook_ready"])
        self.assertTrue(packet["policy"]["candidate_browser_qa_is_not_visual_qa"])
        self.assertTrue(packet["policy"]["candidate_browser_qa_is_not_production_replacement"])
        no_loss = packet["no_feature_loss_acceptance_contract"]
        self.assertEqual(no_loss["schema_version"], "candidate_radar_no_feature_loss_acceptance.v1")
        self.assertEqual(no_loss["status"], "no_feature_loss_acceptance_local_ready_production_pending")
        self.assertTrue(no_loss["local_no_feature_loss_contract_ready"])
        self.assertFalse(no_loss["production_radar_replacement_complete"])
        self.assertTrue(no_loss["legacy_fallback_required"])
        self.assertFalse(no_loss["full_pool_scan_done"])
        self.assertFalse(no_loss["deep_scan_done"])
        self.assertFalse(no_loss["provider_backed_acceptance_done"])
        self.assertFalse(no_loss["browser_performance_trace_done"])
        self.assertFalse(no_loss["external_calls_triggered"])
        self.assertFalse(no_loss["tushare_called"])
        self.assertFalse(no_loss["deepseek_called"])
        self.assertFalse(no_loss["github_called"])
        self.assertGreater(no_loss["production_blocker_count"], 0)
        no_loss_rows = {row["criterion"]: row for row in packet["no_feature_loss_acceptance_rows"]}
        self.assertTrue(no_loss_rows["cache_get_external_boundary"]["production_ready"])
        self.assertEqual(no_loss_rows["legacy_signal_groups_visible"]["status"], "gap_reported")
        self.assertEqual(no_loss_rows["provider_signal_gaps_visible"]["status"], "gap_reported")
        self.assertEqual(no_loss_rows["freshness_research_only_boundary"]["status"], "research_only_reported")
        self.assertEqual(no_loss_rows["browser_performance_trace_pending"]["status"], "pending_visual_perf_trace")
        self.assertEqual(no_loss_rows["full_pool_execution_pending"]["status"], "pending_worker_execution")
        self.assertEqual(no_loss_rows["deep_scan_execution_pending"]["status"], "pending_worker_execution")
        self.assertEqual(no_loss_rows["provider_backed_acceptance_pending"]["status"], "pending_provider_acceptance")
        self.assertTrue(no_loss_rows["trade_action_isolation"]["production_ready"])
        self.assertTrue(packet["policy"]["no_feature_loss_acceptance_contract_is_local"])
        self.assertTrue(packet["policy"]["no_feature_loss_acceptance_is_not_production_replacement"])
        self.assertTrue(packet["policy"]["legacy_fallback_required_until_full_pool_deep_scan_acceptance"])
        triage = packet["replacement_gap_triage_contract"]
        triage_rows = {row["gap_key"]: row for row in packet["replacement_gap_triage_rows"]}
        self.assertEqual(triage["schema_version"], "candidate_radar_replacement_gap_triage.v1")
        self.assertEqual(triage["status"], "replacement_gap_triage_local_ready_legacy_retirement_blocked")
        self.assertTrue(triage["local_triage_ready"])
        self.assertFalse(triage["legacy_retirement_ready"])
        self.assertFalse(triage["production_radar_replacement_complete"])
        self.assertGreater(triage["blocking_gap_count"], 0)
        self.assertGreater(triage["pending_gap_count"], 0)
        self.assertIn("provider_backed_acceptance", triage["blocking_gap_keys"])
        self.assertEqual(triage_rows["provider_backed_acceptance"]["status"], "pending_provider_acceptance")
        self.assertEqual(triage_rows["trade_action_isolation"]["status"], "passed")
        self.assertFalse(triage["external_calls_triggered"])
        self.assertFalse(triage["tushare_called"])
        self.assertFalse(triage["deepseek_called"])
        self.assertFalse(triage["github_called"])
        self.assertTrue(packet["policy"]["replacement_gap_triage_contract_is_local"])
        self.assertTrue(packet["policy"]["replacement_gap_triage_is_not_production_replacement"])
        self.assertTrue(packet["policy"]["legacy_radar_retirement_blocked_by_triage"])
        self.assertTrue(packet["policy"]["fast_scan_readiness_audit_is_local"])
        self.assertTrue(packet["policy"]["fast_scan_readiness_is_not_full_replacement"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_scan_market"])
        self.assertTrue(packet["policy"]["candidate_is_not_buy_instruction"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_candidate_radar_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/candidate-radar/cache", response["warnings"][0])

    def test_candidate_radar_quick_scan_endpoint_is_button_gated_local_cache_only(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "radar_packet": {"status": "ready", "summary": "候选缓存", "authorization": "Bearer SHOULD_DROP"},
                "next_ticket_candidates": [
                    {"rank": 1, "ticker": "002837.SZ", "name": "英维克", "score": 47, "action_state": "只观察"}
                ],
                "candidate_execution_evidence_overview": {"headline": "仍待验证"},
            }
        )

        response = self.client.post(
            "/api/candidate-radar/scan-quick",
            json={"scan_mode": "quick_cache_scan", "universe_mode": "cache_snapshot", "token": "SHOULD_DROP"},
        ).json()

        self.assertTrue(response["ok"])
        task = response["data"]["task"]
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["task_type"], "run_candidate_radar_quick_scan")
        self.assertEqual(task["output_packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(task["call_ledger"][0]["api"], "local_candidate_radar_quick_scan")
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["scan_mode"], "quick_cache_scan")
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

        cache = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(cache["ok"])
        packet = cache["data"]
        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertEqual(packet["candidate_rows"][0]["ticker"], "002837.SZ")
        self.assertEqual(packet["scan_mode"], "quick_cache_scan")
        self.assertEqual(packet["call_ledger"][1]["api"], "local_candidate_radar_quick_scan")
        self.assertTrue(packet["policy"]["quick_scan_reads_cache_only"])
        self.assertTrue(packet["scan_coverage"]["does_not_call_external_sources"])
        self.assertEqual(packet["freshness_state"]["source"], "missing")
        self.assertIn("data_freshness_missing", {row["reason"] for row in packet["skipped_reason_rows"]})
        self.assertEqual(packet["legacy_parity_inventory"]["status"], "partial_parity")
        self.assertFalse(packet["legacy_parity_inventory"]["quick_scan_is_full_replacement"])
        self.assertIn("full_pool_scan", {row["scan_mode"] for row in packet["scan_mode_status_rows"]})
        self.assertTrue(packet["fast_scan_readiness_audit"]["local_fast_scan_ready"])
        self.assertFalse(packet["fast_scan_readiness_audit"]["production_radar_replacement_complete"])
        quick_fast_rows = {row["criterion"]: row for row in packet["fast_scan_readiness_rows"]}
        self.assertEqual(quick_fast_rows["button_task_receipt_contract"]["status"], "passed")
        self.assertEqual(quick_fast_rows["last_success_cache_visible"]["status"], "passed")
        self.assertEqual(quick_fast_rows["full_pool_boundary_plan_only"]["status"], "not_executed")
        priority = packet["candidate_priority_explanation_contract"]
        self.assertEqual(priority["schema_version"], "candidate_radar_priority_explanation.v1")
        self.assertEqual(priority["scope"], "local_cache_rank_explanation_not_rescore_or_trade_signal")
        self.assertEqual(priority["status"], "candidate_priority_explanation_ready")
        self.assertEqual(priority["sort_order_source"], "existing_candidate_rows_order")
        self.assertTrue(priority["cached_rank_preserved"])
        self.assertTrue(priority["cached_score_preserved"])
        self.assertTrue(priority["uses_existing_rank_only"])
        self.assertTrue(priority["uses_existing_score_only"])
        self.assertTrue(priority["does_not_recompute_score"])
        self.assertTrue(priority["does_not_sort_candidates"])
        self.assertTrue(priority["does_not_calculate_action"])
        self.assertTrue(priority["priority_explanation_is_not_trade_signal"])
        self.assertFalse(priority["production_radar_replacement_complete"])
        priority_rows = packet["candidate_priority_explanation_rows"]
        self.assertEqual(priority_rows[0]["ticker"], "002837.SZ")
        self.assertEqual(priority_rows[0]["rank_source"], "existing_candidate_rows_order")
        self.assertTrue(priority_rows[0]["uses_existing_rank_only"])
        self.assertTrue(priority_rows[0]["uses_existing_score_only"])
        self.assertTrue(priority_rows[0]["candidate_is_not_buy_instruction"])
        self.assertTrue(packet["policy"]["candidate_priority_explanation_contract_is_local"])
        self.assertTrue(packet["policy"]["candidate_priority_explanation_uses_existing_rank_only"])
        self.assertTrue(packet["policy"]["candidate_priority_explanation_uses_existing_score_only"])
        self.assertTrue(packet["policy"]["candidate_priority_explanation_is_not_trade_signal"])
        self.assertGreaterEqual(packet["counts"]["priority_explanation_row_count"], 1)
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertIn("GET /api/candidate-radar/cache", cache["warnings"][0])

    def test_candidate_radar_full_pool_plan_endpoint_is_button_gated_plan_only(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "a_share_capability_matrix": [
                    {"provider": "Tushare", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "api": "top_inst", "capability_state": "permission_denied", "status": "权限不足"},
                ],
                "data_freshness": {"state": "fresh", "expected_trade_date": "2026-06-12"},
            }
        )

        response = self.client.post(
            "/api/candidate-radar/full-pool-plan",
            json={"scan_mode": "full_pool_scan", "plan_only": True, "token": "SHOULD_DROP"},
        ).json()

        self.assertTrue(response["ok"])
        task = response["data"]["task"]
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["task_type"], "run_candidate_radar_full_pool_plan")
        self.assertEqual(task["output_packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(task["current_step"], "candidate_radar_full_pool_plan_ready")
        self.assertEqual(task["call_ledger"][0]["api"], "local_candidate_radar_full_pool_plan")
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["scan_mode"], "full_pool_scan")
        self.assertTrue(task["call_ledger"][0]["request_params_safe"]["plan_only"])
        self.assertFalse(task["call_ledger"][0]["request_params_safe"]["full_pool_scan_done"])
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

        cache = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(cache["ok"])
        packet = cache["data"]
        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertEqual(packet["scan_mode"], "full_pool_plan")
        self.assertEqual(packet["full_pool_scan_plan"]["status"], "full_pool_plan_ready")
        self.assertFalse(packet["full_pool_scan_plan"]["full_pool_scan_done"])
        self.assertFalse(packet["full_pool_scan_plan"]["provider_refresh_executed"])
        self.assertFalse(packet["full_pool_scan_plan"]["candidate_scoring_executed"])
        self.assertFalse(packet["full_pool_scan_plan"]["candidate_packet_written_by_plan"])
        self.assertTrue(packet["policy"]["full_pool_plan_is_not_full_pool_scan"])
        self.assertTrue(packet["policy"]["full_pool_plan_writes_no_candidates"])
        self.assertIn("worker_required", {row["blocker_key"] for row in packet["full_pool_blocker_rows"]})
        self.assertIn("provider_dragon_tiger", {row["blocker_key"] for row in packet["full_pool_blocker_rows"]})
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertIn("GET /api/candidate-radar/cache", cache["warnings"][0])

    def test_candidate_radar_deep_scan_plan_endpoint_is_button_gated_plan_only(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "radar_packet": {
                    "status": "ready",
                    "top_candidates": [{"rank": 1, "ticker": "002837.SZ", "name": "英维克", "action_state": "只观察"}],
                    "authorization": "Bearer SHOULD_DROP",
                },
                "a_share_capability_matrix": [
                    {"provider": "Tushare", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "api": "top_inst", "capability_state": "permission_denied", "status": "权限不足"},
                ],
                "data_freshness": {"state": "fresh", "expected_trade_date": "2026-06-12"},
            }
        )

        response = self.client.post(
            "/api/candidate-radar/deep-scan-plan",
            json={"scan_mode": "deep_scan", "plan_only": True, "token": "SHOULD_DROP"},
        ).json()

        self.assertTrue(response["ok"])
        task = response["data"]["task"]
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["task_type"], "run_candidate_radar_deep_scan_plan")
        self.assertEqual(task["output_packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(task["current_step"], "candidate_radar_deep_scan_plan_ready")
        self.assertEqual(task["call_ledger"][0]["api"], "local_candidate_radar_deep_scan_plan")
        self.assertEqual(task["call_ledger"][0]["request_params_safe"]["scan_mode"], "deep_scan")
        self.assertTrue(task["call_ledger"][0]["request_params_safe"]["plan_only"])
        self.assertFalse(task["call_ledger"][0]["request_params_safe"]["deep_scan_done"])
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

        cache = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(cache["ok"])
        packet = cache["data"]
        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertEqual(packet["scan_mode"], "deep_scan_plan")
        self.assertEqual(packet["deep_scan_plan"]["status"], "deep_scan_plan_ready")
        self.assertFalse(packet["deep_scan_plan"]["deep_scan_done"])
        self.assertFalse(packet["deep_scan_plan"]["provider_refresh_executed"])
        self.assertFalse(packet["deep_scan_plan"]["candidate_scoring_executed"])
        self.assertFalse(packet["deep_scan_plan"]["candidate_packet_written_by_plan"])
        self.assertTrue(packet["policy"]["deep_scan_plan_is_not_deep_scan"])
        self.assertTrue(packet["policy"]["deep_scan_feature_loss_gaps_visible"])
        self.assertIn("stage_async_worker_execution", {row["blocker_key"] for row in packet["deep_scan_blocker_rows"]})
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertIn("GET /api/candidate-radar/cache", cache["warnings"][0])

    def test_risk_guardrails_cache_endpoint_returns_local_risk_boundaries(self):
        self._with_snapshot_cache(
            {
                "risk_alerts": {
                    "data_gaps": ["资金流缺口"],
                    "must_not_do": ["不追高"],
                    "reduce_conditions": ["跌破安全线降风险"],
                    "hard_risk_alerts": ["公告待核验"],
                    "authorization": "Bearer SHOULD_DROP",
                },
                "safety_line": "安全线 100 元",
                "execution_guardrail_overview": {"blocked_count": 1, "headline": "执行护栏"},
                "legacy_decision_chain_summary": {"blocked_count": 0, "waiting_count": 1},
            }
        )

        response = self.client.get("/api/risk/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_risk_guardrails_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["counts"]["data_gap_count"], 1)
        self.assertEqual(packet["counts"]["must_not_do_count"], 1)
        self.assertEqual(packet["must_not_do_rows"][0]["guardrail"], "不追高")
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_clear_risk_flags"])
        self.assertEqual(packet["trade_isolation_audit"]["status"], "trade_isolation_ready")
        self.assertTrue(packet["trade_isolation_audit"]["no_automatic_order_path_in_task_catalog"])
        self.assertTrue(packet["trade_isolation_audit"]["research_paths_cannot_mutate_strategy_action"])
        self.assertEqual(packet["counts"]["trade_isolation_blocker_count"], 0)
        self.assertIn("trade_isolation_audit", packet)
        self.assertIn("trade_isolation_rows", packet)
        self.assertIn("trade_isolation_boundary_rows", packet)
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_risk_guardrails_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/risk/cache", response["warnings"][0])

    def test_evidence_cache_endpoint_returns_lineage_without_external_work(self):
        self._with_snapshot_cache(
            {
                "a_share_fact_lineage_summary": {
                    "schema_version": "a_share_fact_lineage_summary.v1",
                    "summary": "已验证 1｜阻断 0｜缓存 0｜过期 0｜缺失 0｜待验证 0",
                    "items": [{"fact_key": "moneyflow", "status_label": "已验证", "enters_core_action": False}],
                    "counts": {"verified": 1, "blocked": 0, "missing": 0, "cached": 0},
                }
            }
        )

        response = self.client.get("/api/evidence/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_a_share_evidence_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertEqual(packet["counts"]["lineage_verified"], 1)
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["policy"]["lineage_enters_core_action"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_a_share_evidence_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/evidence/cache", response["warnings"][0])

    def test_data_capability_cache_endpoint_returns_safe_local_status(self):
        self._with_snapshot_cache(
            {
                "data_capability": {
                    "items": [
                        {
                            "provider": "Tushare",
                            "api": "margin_detail",
                            "label": "融资融券",
                            "capability_state": "permission_denied",
                            "status": "权限不足",
                            "authorization": "Bearer SHOULD_DROP",
                        }
                    ]
                }
            }
        )

        response = self.client.get("/api/data-capability/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_data_capability_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertGreaterEqual(packet["counts"]["restricted"], 1)
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["policy"]["does_not_ping_tushare"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_data_capability_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/data-capability/cache", response["warnings"][0])

    def test_data_health_cache_endpoint_returns_provider_timeline_without_ping(self):
        self._with_parquet_root()
        self._with_snapshot_cache(
            {
                "data_health_timeline": [{"event": "daily_basic stale", "provider": "Tushare"}],
                "provider_data_capability_cockpit": {"providers": [{"provider": "Tushare", "status": "partial"}]},
                "a_share_capability_matrix": [{"provider": "Tushare", "api": "daily_basic"}],
                "data_health_ledger": {"rows": [{"provider": "Tushare", "api": "daily_basic"}]},
                "data_gap_report": {"items": [{"label": "daily_basic missing", "token": "SHOULD_DROP"}]},
            }
        )

        response = self.client.get("/api/data-health/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_data_health_timeline_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertEqual(packet["counts"]["timeline_count"], 1)
        self.assertEqual(packet["counts"]["provider_count"], 1)
        self.assertEqual(packet["counts"]["capability_count"], 1)
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(packet["policy"]["does_not_ping_tushare"])
        self.assertTrue(packet["policy"]["does_not_refresh_data"])
        self.assertTrue(packet["policy"]["post_task_required_for_provider_probe"])
        self.assertTrue(packet["policy"]["freshness_acceptance_matrix_is_local_contract"])
        self.assertFalse(packet["policy"]["freshness_acceptance_matrix_calls_trade_cal"])
        self.assertEqual(packet["trade_cal_physical_validation"]["status"], "local_trade_cal_dataset_missing")
        self.assertFalse(packet["trade_cal_physical_validation"]["trade_cal_long_window_validation_done"])
        self.assertFalse(packet["trade_cal_physical_validation"]["real_provider_validation_done"])
        self.assertFalse(packet["trade_cal_physical_validation"]["provider_backed_long_window_acceptance_done"])
        self.assertFalse(packet["trade_cal_physical_validation"]["external_calls_triggered"])
        self.assertFalse(packet["trade_cal_physical_validation"]["tushare_called"])
        self.assertFalse(packet["policy"]["real_trade_cal_long_window_validation_done"])
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_runbook_is_local"])
        self.assertFalse(packet["policy"]["trade_cal_provider_acceptance_runbook_calls_provider"])
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_still_pending"])
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_promotion_audit_is_local"])
        self.assertFalse(packet["policy"]["trade_cal_provider_acceptance_promotion_audit_calls_provider"])
        self.assertFalse(packet["policy"]["trade_cal_provider_acceptance_promotion_ready"])
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_promotion_still_pending"])
        runbook = packet["trade_cal_provider_acceptance_runbook"]
        self.assertEqual(runbook["schema_version"], "data_health_trade_cal_provider_acceptance_runbook.v1")
        self.assertEqual(runbook["status"], "trade_cal_provider_acceptance_runbook_ready_execution_pending")
        self.assertEqual(runbook["scope"], "local_provider_acceptance_runbook_not_provider_execution")
        self.assertTrue(runbook["local_runbook_ready"])
        self.assertFalse(runbook["provider_backed_long_window_acceptance_done"])
        self.assertFalse(runbook["provider_refresh_called_by_runbook"])
        self.assertFalse(runbook["external_calls_triggered"])
        self.assertFalse(runbook["tushare_called"])
        self.assertTrue(runbook["does_not_execute_trades"])
        self.assertEqual(runbook["post_task_route"], "POST /api/tasks/refresh-tushare-facts")
        self.assertEqual(runbook["required_api"], "trade_cal")
        promotion = packet["trade_cal_provider_acceptance_promotion_audit"]
        self.assertEqual(promotion["schema_version"], "data_health_trade_cal_provider_acceptance_promotion_audit.v1")
        self.assertEqual(promotion["status"], "trade_cal_provider_acceptance_promotion_pending")
        self.assertEqual(promotion["scope"], "local_snapshot_evidence_promotion_audit_no_provider_execution")
        self.assertFalse(promotion["promotion_ready"])
        self.assertFalse(promotion["provider_backed_long_window_acceptance_done"])
        self.assertFalse(promotion["provider_refresh_called_by_audit"])
        self.assertFalse(promotion["external_calls_triggered"])
        self.assertFalse(promotion["tushare_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_data_health_timeline_cache")
        self.assertEqual(response["call_ledger"][0]["freshness_acceptance_scenario_count"], 8)
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/data-health/cache", response["warnings"][0])

    def test_data_health_cache_exposes_freshness_acceptance_matrix_as_local_contract(self):
        self._with_parquet_root()
        self._with_snapshot_cache(
            {
                "data_freshness": {
                    "state": "stale",
                    "expected_trade_date": "2026-06-12",
                    "data_date": "2026-06-11",
                    "authorization": "Bearer SHOULD_DROP",
                }
            }
        )

        response = self.client.get("/api/data-health/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        matrix = packet["freshness_acceptance_matrix"]
        summary = packet["freshness_acceptance_summary"]
        sample = packet["freshness_long_window_sample_validation"]
        physical = packet["trade_cal_physical_validation"]
        current_evidence = packet["current_evidence_freshness_qa_contract"]
        decision_surface = packet["current_evidence_decision_surface_audit"]
        producer_coverage = packet["current_evidence_producer_coverage_audit"]
        provider_runbook = packet["trade_cal_provider_acceptance_runbook"]
        provider_promotion = packet["trade_cal_provider_acceptance_promotion_audit"]
        provider_runbook_rows = {row["criterion"]: row for row in packet["trade_cal_provider_acceptance_runbook_rows"]}
        provider_promotion_rows = {
            row["criterion"]: row for row in packet["trade_cal_provider_acceptance_promotion_rows"]
        }
        current_evidence_rows = {
            row["criterion"]: row for row in packet["current_evidence_freshness_qa_rows"]
        }
        decision_surface_rows = {
            row["surface"]: row for row in packet["current_evidence_decision_surface_rows"]
        }
        producer_coverage_rows = {
            row["producer"]: row for row in packet["current_evidence_producer_coverage_rows"]
        }
        sample_rows = {row["scenario_id"]: row for row in packet["freshness_long_window_sample_rows"]}
        rows_by_id = {row["scenario_id"]: row for row in matrix}

        self.assertEqual(summary["status"], "acceptance_matrix_ready")
        self.assertEqual(summary["scope"], "local_contract_not_real_trade_cal_validation")
        self.assertEqual(summary["scenario_count"], 8)
        self.assertFalse(summary["trade_cal_long_window_validation_done"])
        self.assertFalse(summary["real_provider_validation_done"])
        self.assertTrue(summary["current_evidence_requires_expected_trade_date"])
        self.assertTrue(summary["stale_expired_historical_unknown_are_research_only"])
        self.assertTrue(summary["blocks_composite_score"])
        self.assertTrue(summary["blocks_support_factors"])
        self.assertTrue(summary["blocks_evidence_preview"])
        self.assertTrue(summary["blocks_next_session_bridge_preview"])
        self.assertTrue(summary["provider_delay_grace_is_bounded"])
        self.assertTrue(summary["missing_trade_cal_falls_back_with_warning"])
        self.assertTrue(summary["does_not_modify_strategy_action"])
        self.assertTrue(summary["does_not_execute_trades"])

        self.assertEqual(packet["counts"]["freshness_acceptance_scenario_count"], 8)
        self.assertEqual(packet["counts"]["freshness_long_window_sample_scenario_count"], 9)
        self.assertEqual(packet["counts"]["freshness_long_window_sample_passed_count"], 9)
        self.assertEqual(packet["counts"]["freshness_long_window_sample_failed_count"], 0)
        self.assertEqual(packet["counts"]["trade_cal_physical_validation_row_count"], 5)
        self.assertGreater(packet["counts"]["trade_cal_physical_validation_blocker_count"], 0)
        self.assertGreater(packet["counts"]["trade_cal_provider_acceptance_runbook_row_count"], 0)
        self.assertGreater(packet["counts"]["trade_cal_provider_acceptance_pending_count"], 0)
        self.assertEqual(packet["counts"]["trade_cal_provider_acceptance_promotion_row_count"], 10)
        self.assertGreater(packet["counts"]["trade_cal_provider_acceptance_promotion_blocker_count"], 0)
        self.assertEqual(packet["counts"]["trade_cal_provider_acceptance_evidence_row_count"], 0)
        self.assertEqual(packet["counts"]["current_evidence_freshness_qa_row_count"], 8)
        self.assertEqual(packet["counts"]["current_evidence_freshness_qa_blocker_count"], 3)
        self.assertEqual(packet["counts"]["current_evidence_decision_surface_row_count"], 5)
        self.assertEqual(packet["counts"]["current_evidence_decision_surface_blocker_count"], 0)
        self.assertEqual(packet["counts"]["current_evidence_producer_coverage_row_count"], 6)
        self.assertEqual(packet["counts"]["current_evidence_producer_coverage_blocker_count"], 0)
        self.assertEqual(sample["status"], "local_sample_validation_passed")
        self.assertEqual(sample["scope"], "local_synthetic_long_window_not_real_trade_cal_validation")
        self.assertTrue(sample["local_sample_validation_done"])
        self.assertTrue(sample["uses_actual_freshness_gate"])
        self.assertTrue(sample["fixture_is_synthetic"])
        self.assertFalse(sample["trade_cal_long_window_validation_done"])
        self.assertFalse(sample["external_calls_triggered"])
        self.assertEqual(physical["status"], "local_trade_cal_dataset_missing")
        self.assertEqual(physical["scope"], "local_physical_trade_cal_parquet_validation")
        self.assertFalse(physical["fixture_is_synthetic"])
        self.assertFalse(physical["trade_cal_long_window_validation_done"])
        self.assertFalse(physical["real_provider_validation_done"])
        self.assertFalse(physical["provider_backed_long_window_acceptance_done"])
        self.assertIn("local_trade_cal_parquet_missing", physical["blockers"])
        self.assertFalse(physical["external_calls_triggered"])
        self.assertFalse(physical["tushare_called"])
        self.assertFalse(physical["deepseek_called"])
        self.assertFalse(physical["github_called"])
        self.assertTrue(physical["does_not_execute_trades"])
        self.assertTrue(physical["does_not_modify_strategy_action"])
        self.assertFalse(packet["policy"]["freshness_long_window_sample_calls_trade_cal"])
        self.assertTrue(packet["policy"]["trade_cal_physical_validation_is_local_artifact"])
        self.assertFalse(packet["policy"]["trade_cal_physical_validation_calls_trade_cal_provider"])
        self.assertTrue(packet["policy"]["trade_cal_physical_validation_reads_local_rows"])
        self.assertFalse(packet["policy"]["trade_cal_physical_validation_writes_files"])
        self.assertFalse(packet["policy"]["real_trade_cal_long_window_validation_done"])
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_runbook_is_local"])
        self.assertFalse(packet["policy"]["trade_cal_provider_acceptance_runbook_calls_provider"])
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_still_pending"])
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_promotion_audit_is_local"])
        self.assertFalse(packet["policy"]["trade_cal_provider_acceptance_promotion_audit_calls_provider"])
        self.assertFalse(packet["policy"]["trade_cal_provider_acceptance_promotion_ready"])
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_promotion_still_pending"])
        self.assertTrue(packet["policy"]["current_evidence_freshness_qa_is_local_contract"])
        self.assertTrue(packet["policy"]["current_evidence_requires_expected_trade_date"])
        self.assertTrue(packet["policy"]["historical_samples_are_research_only"])
        self.assertTrue(packet["policy"]["provider_backed_trade_cal_acceptance_still_pending"])
        self.assertTrue(packet["policy"]["current_evidence_decision_surface_audit_is_local"])
        self.assertFalse(packet["policy"]["current_evidence_decision_surface_audit_rescores"])
        self.assertFalse(packet["policy"]["current_evidence_decision_surface_audit_mutates_action"])
        self.assertTrue(packet["policy"]["current_evidence_producer_coverage_audit_is_local"])
        self.assertFalse(packet["policy"]["current_evidence_producer_coverage_audit_builds_missing_packets"])
        self.assertTrue(packet["policy"]["current_evidence_producer_coverage_requires_expected_trade_date"])
        self.assertEqual(current_evidence["schema_version"], "data_health_current_evidence_freshness_qa.v1")
        self.assertEqual(
            current_evidence["status"],
            "current_evidence_qa_ready_provider_trade_cal_acceptance_pending",
        )
        self.assertEqual(current_evidence["scope"], "local_cache_only_current_evidence_boundary_contract")
        self.assertEqual(current_evidence["data_freshness_state"], "stale")
        self.assertEqual(current_evidence["expected_trade_date"], "2026-06-12")
        self.assertEqual(current_evidence["data_date"], "2026-06-11")
        self.assertFalse(current_evidence["date_matches_expected_trade_date"])
        self.assertEqual(current_evidence["current_evidence_candidate_status"], "research_only")
        self.assertIn("data_date_does_not_match_expected_trade_date", current_evidence["current_evidence_blockers"])
        self.assertIn("state_stale_research_only", current_evidence["current_evidence_blockers"])
        self.assertIn("provider_backed_trade_cal_acceptance_pending", current_evidence["current_evidence_blockers"])
        self.assertFalse(current_evidence["provider_backed_long_window_acceptance_done"])
        self.assertFalse(current_evidence["provider_refresh_called_by_validation"])
        self.assertTrue(current_evidence["historical_samples_are_research_only"])
        self.assertTrue(current_evidence["stale_expired_historical_unknown_are_research_only"])
        self.assertTrue(current_evidence["blocks_composite_score"])
        self.assertTrue(current_evidence["blocks_support_factors"])
        self.assertTrue(current_evidence["blocks_evidence_preview"])
        self.assertTrue(current_evidence["blocks_next_session_bridge_preview"])
        self.assertTrue(current_evidence["does_not_execute_trades"])
        self.assertTrue(current_evidence["does_not_modify_strategy_action"])
        self.assertFalse(current_evidence["external_calls_triggered"])
        self.assertEqual(decision_surface["schema_version"], "data_health_current_evidence_decision_surface_audit.v1")
        self.assertEqual(decision_surface["status"], "decision_surface_audit_ready_no_observed_blockers")
        self.assertEqual(decision_surface["scope"], "local_snapshot_only_no_rescore_no_action_mutation")
        self.assertEqual(decision_surface["current_evidence_candidate_status"], "research_only")
        self.assertEqual(decision_surface["row_count"], 5)
        self.assertEqual(decision_surface["observed_surface_count"], 0)
        self.assertEqual(decision_surface["blocked_surface_count"], 0)
        self.assertTrue(decision_surface["read_only_snapshot_audit"])
        self.assertTrue(decision_surface["does_not_rescore"])
        self.assertTrue(decision_surface["does_not_filter_packet"])
        self.assertTrue(decision_surface["does_not_mutate_decision_surfaces"])
        self.assertFalse(decision_surface["external_calls_triggered"])
        self.assertTrue(decision_surface["does_not_modify_strategy_action"])
        self.assertEqual(decision_surface_rows["composite_score"]["status"], "not_observed")
        self.assertEqual(decision_surface_rows["support_factors"]["status"], "not_observed")
        self.assertEqual(decision_surface_rows["next_session_bridge.preview"]["status"], "not_observed")
        self.assertEqual(decision_surface_rows["strategy_action"]["status"], "not_observed")
        self.assertEqual(producer_coverage["schema_version"], "data_health_current_evidence_producer_coverage.v1")
        self.assertEqual(producer_coverage["status"], "producer_freshness_coverage_ready_no_observed_blockers")
        self.assertEqual(producer_coverage["scope"], "local_snapshot_only_expected_date_field_coverage")
        self.assertEqual(producer_coverage["producer_count"], 6)
        self.assertEqual(producer_coverage["observed_producer_count"], 1)
        self.assertEqual(producer_coverage["blocked_producer_count"], 0)
        self.assertTrue(producer_coverage["not_observed_is_not_production_proof"])
        self.assertTrue(producer_coverage["does_not_build_missing_packets"])
        self.assertFalse(producer_coverage["external_calls_triggered"])
        self.assertEqual(producer_coverage_rows["global_data_freshness"]["status"], "date_mismatch_research_only")
        self.assertEqual(producer_coverage_rows["global_data_freshness"]["expected_trade_date"], "2026-06-12")
        self.assertEqual(producer_coverage_rows["global_data_freshness"]["data_date"], "2026-06-11")
        self.assertEqual(producer_coverage_rows["factor_quant_hub"]["status"], "not_observed")
        self.assertEqual(producer_coverage_rows["candidate_radar"]["status"], "not_observed")
        self.assertEqual(provider_runbook["schema_version"], "data_health_trade_cal_provider_acceptance_runbook.v1")
        self.assertEqual(provider_runbook["status"], "trade_cal_provider_acceptance_runbook_ready_execution_pending")
        self.assertEqual(provider_runbook["scope"], "local_provider_acceptance_runbook_not_provider_execution")
        self.assertTrue(provider_runbook["local_runbook_ready"])
        self.assertFalse(provider_runbook["provider_backed_long_window_acceptance_done"])
        self.assertFalse(provider_runbook["provider_refresh_called_by_runbook"])
        self.assertFalse(provider_runbook["production_freshness_gate_complete"])
        self.assertEqual(provider_runbook["required_payload_safe"]["apis"], ["trade_cal"])
        self.assertEqual(provider_runbook["minimum_acceptance_window_days"], 730)
        self.assertGreater(provider_runbook["pending_execution_count"], 0)
        self.assertFalse(provider_runbook["external_calls_triggered"])
        self.assertFalse(provider_runbook["tushare_called"])
        self.assertFalse(provider_runbook["deepseek_called"])
        self.assertFalse(provider_runbook["github_called"])
        self.assertEqual(provider_runbook_rows["explicit_post_task_required"]["status"], "passed_static_policy")
        self.assertEqual(provider_runbook_rows["call_ledger_required"]["status"], "execution_ready")
        self.assertEqual(provider_runbook_rows["long_window_sample_required"]["status"], "execution_pending")
        self.assertEqual(provider_runbook_rows["current_evidence_boundary"]["status"], "passed_static_policy")
        self.assertEqual(
            provider_promotion["schema_version"],
            "data_health_trade_cal_provider_acceptance_promotion_audit.v1",
        )
        self.assertEqual(provider_promotion["status"], "trade_cal_provider_acceptance_promotion_pending")
        self.assertEqual(provider_promotion["scope"], "local_snapshot_evidence_promotion_audit_no_provider_execution")
        self.assertFalse(provider_promotion["promotion_ready"])
        self.assertFalse(provider_promotion["provider_backed_long_window_acceptance_done"])
        self.assertFalse(provider_promotion["production_freshness_gate_complete"])
        self.assertFalse(provider_promotion["provider_refresh_called_by_audit"])
        self.assertFalse(provider_promotion["provider_evidence_from_prior_task"])
        self.assertFalse(provider_promotion["explicit_promotion_marker_found"])
        self.assertFalse(provider_promotion["external_calls_triggered"])
        self.assertFalse(provider_promotion["tushare_called"])
        self.assertTrue(provider_promotion["does_not_execute_trades"])
        self.assertEqual(provider_promotion_rows["explicit_provider_call_ledger"]["status"], "blocked")
        self.assertEqual(provider_promotion_rows["safe_call_ledger_fields"]["status"], "blocked")
        self.assertEqual(provider_promotion_rows["minimum_long_window"]["status"], "blocked")
        self.assertEqual(provider_promotion_rows["current_evidence_boundary_rechecked"]["status"], "passed")
        self.assertEqual(provider_promotion_rows["audit_is_read_only_no_provider_call"]["status"], "passed")
        self.assertEqual(current_evidence_rows["expected_trade_date_required"]["status"], "passed")
        self.assertEqual(current_evidence_rows["current_data_date_matches_expected"]["status"], "research_only")
        self.assertEqual(current_evidence_rows["freshness_state_allows_current_evidence"]["status"], "research_only")
        self.assertEqual(current_evidence_rows["historical_sample_separation"]["status"], "enforced")
        self.assertEqual(
            current_evidence_rows["provider_backed_trade_cal_acceptance"]["status"],
            "pending_provider_backed_acceptance",
        )
        self.assertEqual(response["call_ledger"][0]["freshness_long_window_sample_scenario_count"], 9)
        self.assertEqual(response["call_ledger"][0]["freshness_long_window_sample_status"], "local_sample_validation_passed")
        self.assertEqual(response["call_ledger"][0]["trade_cal_physical_validation_status"], "local_trade_cal_dataset_missing")
        self.assertFalse(response["call_ledger"][0]["trade_cal_physical_validation_done"])
        self.assertEqual(
            response["call_ledger"][0]["trade_cal_provider_acceptance_runbook_status"],
            "trade_cal_provider_acceptance_runbook_ready_execution_pending",
        )
        self.assertGreater(response["call_ledger"][0]["trade_cal_provider_acceptance_pending_count"], 0)
        self.assertEqual(
            response["call_ledger"][0]["trade_cal_provider_acceptance_promotion_audit_status"],
            "trade_cal_provider_acceptance_promotion_pending",
        )
        self.assertGreater(response["call_ledger"][0]["trade_cal_provider_acceptance_promotion_blocker_count"], 0)
        self.assertEqual(response["call_ledger"][0]["trade_cal_provider_acceptance_evidence_row_count"], 0)
        self.assertFalse(response["call_ledger"][0]["trade_cal_provider_acceptance_promotion_ready"])
        self.assertEqual(
            response["call_ledger"][0]["current_evidence_freshness_qa_status"],
            "current_evidence_qa_ready_provider_trade_cal_acceptance_pending",
        )
        self.assertEqual(response["call_ledger"][0]["current_evidence_candidate_status"], "research_only")
        self.assertEqual(response["call_ledger"][0]["current_evidence_freshness_qa_blocker_count"], 3)
        self.assertEqual(
            response["call_ledger"][0]["current_evidence_decision_surface_audit_status"],
            "decision_surface_audit_ready_no_observed_blockers",
        )
        self.assertEqual(response["call_ledger"][0]["current_evidence_decision_surface_blocker_count"], 0)
        self.assertEqual(
            response["call_ledger"][0]["current_evidence_producer_coverage_audit_status"],
            "producer_freshness_coverage_ready_no_observed_blockers",
        )
        self.assertEqual(response["call_ledger"][0]["current_evidence_producer_coverage_blocker_count"], 0)
        self.assertEqual(sample_rows["sample_intraday_current_day_blocked"]["actual_state"], "future_unavailable")
        self.assertTrue(sample_rows["sample_intraday_current_day_blocked"]["blocks_composite_score"])
        self.assertEqual(sample_rows["sample_provider_delay_grace_previous_day"]["actual_state"], "provider_delay_grace")
        self.assertEqual(sample_rows["sample_missing_today_blocks_current_evidence"]["actual_state"], "unknown")
        self.assertEqual(rows_by_id["premarket_open_day"]["expected_trade_date_rule"], "previous_completed_trading_day")
        self.assertEqual(rows_by_id["postclose_after_1630"]["expected_trade_date_rule"], "current_trading_day")
        self.assertEqual(rows_by_id["weekend_or_holiday"]["expected_trade_date_rule"], "most_recent_completed_trading_day")
        self.assertIn("fallback", rows_by_id["trade_cal_missing_fallback"]["expected_trade_date_rule"])
        self.assertIn("bounded", rows_by_id["provider_delay_grace"]["provider_delay_grace"])
        self.assertIn(
            "cannot_enter_score_support_evidence_preview_next_session_bridge_or_strategy_action",
            rows_by_id["stale_expired_historical_unknown"]["action_boundary"],
        )
        for row in matrix:
            self.assertTrue(row["current_evidence_requires_expected_trade_date"])
            self.assertTrue(row["stale_expired_historical_unknown_are_research_only"])
            self.assertTrue(row["blocks_composite_score"])
            self.assertTrue(row["blocks_support_factors"])
            self.assertTrue(row["blocks_evidence_preview"])
            self.assertTrue(row["blocks_next_session_bridge_preview"])
            self.assertTrue(row["does_not_modify_strategy_action"])
            self.assertTrue(row["does_not_execute_trades"])
            self.assertFalse(row["external_calls_triggered"])
            self.assertFalse(row["tushare_called"])
            self.assertFalse(row["deepseek_called"])
            self.assertFalse(row["github_called"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

    def test_data_health_producer_coverage_audit_exposes_missing_expected_trade_date(self):
        self._with_parquet_root()
        self._with_snapshot_cache(
            {
                "data_freshness": {
                    "state": "fresh",
                    "expected_trade_date": "2026-06-12",
                    "data_date": "2026-06-12",
                },
                "command_center_factor_quant_hub_packet": {
                    "data_freshness_gate": {
                        "status": "fresh",
                        "expected_data_date": "2026-06-12",
                        "latest_data_date": "2026-06-12",
                    }
                },
                "command_center_3_candidate_radar_cache": {
                    "freshness_state": {
                        "state": "fresh",
                        "data_date": "2026-06-12",
                    }
                },
                "command_center_next_session_projection_packet": {
                    "data_freshness": {
                        "state": "fresh",
                        "expected_trade_date": "2026-06-12",
                        "data_date": "2026-06-11",
                    }
                },
            }
        )

        response = self.client.get("/api/data-health/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        audit = packet["current_evidence_producer_coverage_audit"]
        rows = {row["producer"]: row for row in packet["current_evidence_producer_coverage_rows"]}
        self.assertEqual(audit["schema_version"], "data_health_current_evidence_producer_coverage.v1")
        self.assertEqual(audit["status"], "producer_freshness_coverage_ready_blockers_visible")
        self.assertEqual(audit["producer_count"], 6)
        self.assertEqual(audit["observed_producer_count"], 4)
        self.assertEqual(audit["blocked_producer_count"], 1)
        self.assertEqual(audit["blocked_producer_keys"], ["candidate_radar"])
        self.assertFalse(audit["all_observed_producers_have_expected_trade_date"])
        self.assertTrue(audit["does_not_build_missing_packets"])
        self.assertFalse(audit["external_calls_triggered"])
        self.assertFalse(audit["tushare_called"])
        self.assertFalse(audit["deepseek_called"])
        self.assertFalse(audit["github_called"])
        self.assertEqual(rows["global_data_freshness"]["status"], "passed_read_only_contract")
        self.assertEqual(rows["factor_quant_hub"]["status"], "passed_read_only_contract")
        self.assertEqual(rows["candidate_radar"]["status"], "blocked_expected_trade_date_missing")
        self.assertEqual(rows["candidate_radar"]["missing_fields"], ["expected_trade_date"])
        self.assertEqual(rows["next_session_projection"]["status"], "date_mismatch_research_only")
        self.assertEqual(rows["a_share_evidence_radar"]["status"], "not_observed")
        self.assertEqual(rows["market_context"]["status"], "not_observed")
        self.assertEqual(packet["counts"]["current_evidence_producer_coverage_blocker_count"], 1)
        self.assertEqual(
            response["call_ledger"][0]["current_evidence_producer_coverage_audit_status"],
            "producer_freshness_coverage_ready_blockers_visible",
        )
        self.assertEqual(response["call_ledger"][0]["current_evidence_producer_coverage_blocker_count"], 1)

    def test_data_health_decision_surface_audit_exposes_research_only_surface_blockers(self):
        self._with_parquet_root()
        self._with_snapshot_cache(
            {
                "data_freshness": {
                    "state": "stale",
                    "expected_trade_date": "2026-06-12",
                    "data_date": "2026-06-11",
                },
                "command_center_factor_quant_hub_packet": {
                    "score": {
                        "composite_score": 68.5,
                        "support_factors": [
                            {
                                "factor_key": "moneyflow",
                                "freshness_state": "stale",
                                "enters_composite_score": True,
                            }
                        ],
                    },
                    "evidence_preview": [
                        {
                            "factor_key": "preview_moneyflow",
                            "data_status": "stale_data",
                        }
                    ],
                    "next_session_bridge": {
                        "preview": [
                            {
                                "factor_key": "bridge_moneyflow",
                                "freshness_state": "expired",
                            }
                        ]
                    },
                },
                "strategy_execution_packet": {"action": "观察", "token": "SHOULD_DROP"},
            }
        )

        response = self.client.get("/api/data-health/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        audit = packet["current_evidence_decision_surface_audit"]
        rows = {row["surface"]: row for row in packet["current_evidence_decision_surface_rows"]}
        self.assertEqual(audit["schema_version"], "data_health_current_evidence_decision_surface_audit.v1")
        self.assertEqual(audit["status"], "decision_surface_audit_ready_blockers_visible")
        self.assertEqual(audit["current_evidence_candidate_status"], "research_only")
        self.assertEqual(audit["observed_surface_count"], 5)
        self.assertEqual(audit["blocked_surface_count"], 4)
        self.assertEqual(
            audit["blocked_surface_keys"],
            ["composite_score", "support_factors", "evidence_preview", "next_session_bridge.preview"],
        )
        self.assertEqual(packet["counts"]["current_evidence_decision_surface_blocker_count"], 4)
        self.assertEqual(rows["composite_score"]["status"], "blocked_current_evidence_not_ready")
        self.assertEqual(rows["support_factors"]["status"], "blocked_bad_freshness_state_observed")
        self.assertEqual(rows["support_factors"]["bad_freshness_state_count"], 1)
        self.assertEqual(rows["evidence_preview"]["status"], "blocked_bad_freshness_state_observed")
        self.assertEqual(rows["next_session_bridge.preview"]["status"], "blocked_bad_freshness_state_observed")
        self.assertEqual(rows["strategy_action"]["status"], "observed_read_only")
        self.assertTrue(rows["strategy_action"]["does_not_modify_strategy_action"])
        self.assertTrue(audit["does_not_rescore"])
        self.assertTrue(audit["does_not_filter_packet"])
        self.assertTrue(audit["does_not_mutate_decision_surfaces"])
        self.assertFalse(audit["external_calls_triggered"])
        self.assertFalse(audit["tushare_called"])
        self.assertFalse(audit["deepseek_called"])
        self.assertFalse(audit["github_called"])
        self.assertTrue(audit["does_not_execute_trades"])
        self.assertTrue(audit["does_not_modify_strategy_action"])
        self.assertEqual(
            response["call_ledger"][0]["current_evidence_decision_surface_audit_status"],
            "decision_surface_audit_ready_blockers_visible",
        )
        self.assertEqual(response["call_ledger"][0]["current_evidence_decision_surface_blocker_count"], 4)
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

    def test_data_health_cache_validates_local_trade_cal_parquet_without_provider_call(self):
        if importlib.util.find_spec("pyarrow") is None or importlib.util.find_spec("pandas") is None:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        import pandas as pd

        root = self._with_parquet_root()
        today = _dt.date.today()
        start = today - _dt.timedelta(days=220)
        end = today + _dt.timedelta(days=20)
        rows = []
        cursor = start
        previous_open = ""
        while cursor <= end:
            is_open = cursor.weekday() < 5
            rows.append(
                {
                    "exchange": "SSE",
                    "cal_date": cursor.strftime("%Y%m%d"),
                    "is_open": 1 if is_open else 0,
                    "pretrade_date": previous_open,
                }
            )
            if is_open:
                previous_open = cursor.strftime("%Y%m%d")
            cursor += _dt.timedelta(days=1)
        storage_service.parquet_store.write_dataset(pd.DataFrame(rows), root=root, name="trade_cal")
        self._with_snapshot_cache({"data_freshness": {"state": "fresh", "expected_trade_date": today.strftime("%Y-%m-%d")}})

        packet = data_health_service.read_data_health_timeline_cache()
        physical = packet["trade_cal_physical_validation"]

        self.assertEqual(physical["status"], "local_trade_cal_validation_passed")
        self.assertEqual(physical["scope"], "local_physical_trade_cal_parquet_validation")
        self.assertTrue(physical["local_trade_cal_physical_validation_done"])
        self.assertTrue(physical["trade_cal_long_window_validation_done"])
        self.assertFalse(physical["real_provider_validation_done"])
        self.assertFalse(physical["provider_backed_long_window_acceptance_done"])
        self.assertTrue(physical["uses_actual_freshness_gate"])
        self.assertFalse(physical["fixture_is_synthetic"])
        self.assertFalse(physical["provider_refresh_called_by_validation"])
        self.assertFalse(physical["external_calls_triggered"])
        self.assertFalse(physical["tushare_called"])
        self.assertFalse(physical["deepseek_called"])
        self.assertFalse(physical["github_called"])
        self.assertTrue(physical["does_not_execute_trades"])
        self.assertTrue(physical["does_not_modify_strategy_action"])
        self.assertEqual(physical["blockers"], [])
        self.assertGreaterEqual(physical["window_days"], 180)
        self.assertGreaterEqual(physical["open_day_count"], 60)
        self.assertGreater(physical["closed_day_count"], 0)
        self.assertTrue(physical["today_row_found"])
        self.assertIsNotNone(physical["latest_completed_trading_day"])
        self.assertTrue(packet["policy"]["local_trade_cal_physical_validation_done"])
        self.assertEqual(packet["policy"]["real_trade_cal_long_window_validation_done"], False)
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_still_pending"])
        provider_runbook = packet["trade_cal_provider_acceptance_runbook"]
        self.assertTrue(provider_runbook["local_artifact_cross_check_done"])
        self.assertGreaterEqual(provider_runbook["local_artifact_window_days"], 180)
        self.assertFalse(provider_runbook["provider_backed_long_window_acceptance_done"])
        promotion = packet["trade_cal_provider_acceptance_promotion_audit"]
        promotion_rows = {row["criterion"]: row for row in packet["trade_cal_provider_acceptance_promotion_rows"]}
        self.assertEqual(promotion["status"], "trade_cal_provider_acceptance_promotion_pending")
        self.assertFalse(promotion["promotion_ready"])
        self.assertTrue(promotion["local_artifact_cross_check_done"])
        self.assertFalse(promotion["provider_evidence_from_prior_task"])
        self.assertEqual(promotion_rows["schema_and_local_artifact_cross_check"]["status"], "passed")
        self.assertEqual(promotion_rows["explicit_provider_call_ledger"]["status"], "blocked")
        self.assertEqual(packet["call_ledger"][0]["trade_cal_physical_validation_status"], "local_trade_cal_validation_passed")
        self.assertTrue(packet["call_ledger"][0]["trade_cal_physical_validation_done"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))

    def test_data_health_trade_cal_provider_promotion_audit_accepts_prior_evidence_without_calling_provider(self):
        if importlib.util.find_spec("pyarrow") is None or importlib.util.find_spec("pandas") is None:
            self.skipTest("pyarrow/pandas parquet dependency missing")
        import pandas as pd

        root = self._with_parquet_root()
        today = _dt.date.today()
        start = today - _dt.timedelta(days=820)
        end = today + _dt.timedelta(days=20)
        rows = []
        cursor = start
        previous_open = ""
        while cursor <= end:
            is_open = cursor.weekday() < 5
            rows.append(
                {
                    "exchange": "SSE",
                    "cal_date": cursor.strftime("%Y%m%d"),
                    "is_open": 1 if is_open else 0,
                    "pretrade_date": previous_open,
                }
            )
            if is_open:
                previous_open = cursor.strftime("%Y%m%d")
            cursor += _dt.timedelta(days=1)
        storage_service.parquet_store.write_dataset(pd.DataFrame(rows), root=root, name="trade_cal")
        self._with_snapshot_cache(
            {
                "data_freshness": {
                    "state": "fresh",
                    "expected_trade_date": today.strftime("%Y-%m-%d"),
                    "data_date": today.strftime("%Y-%m-%d"),
                },
                "data_health_ledger": {
                    "rows": [
                        {
                            "api": "trade_cal",
                            "call_status": "success",
                            "external": True,
                            "provider_called": True,
                            "row_count": 841,
                            "window_days": 841,
                            "open_day_count": 600,
                            "data_date": today.strftime("%Y-%m-%d"),
                            "window_end": today.strftime("%Y-%m-%d"),
                            "local_fetched_at": "2026-06-13T10:00:00",
                            "acceptance_mode": "provider_backed_trade_cal_long_window",
                            "provider_backed_long_window_acceptance_done": True,
                            "freshness_replay_passed": True,
                            "freshness_replay_scenario_count": 8,
                            "failure_modes_validated": True,
                            "failure_mode_validated_count": 6,
                            "error_message_safe": "",
                        }
                    ]
                },
            }
        )

        packet = data_health_service.read_data_health_timeline_cache()
        promotion = packet["trade_cal_provider_acceptance_promotion_audit"]
        promotion_rows = {row["criterion"]: row for row in packet["trade_cal_provider_acceptance_promotion_rows"]}

        self.assertEqual(promotion["schema_version"], "data_health_trade_cal_provider_acceptance_promotion_audit.v1")
        self.assertEqual(promotion["status"], "trade_cal_provider_acceptance_promotion_ready")
        self.assertTrue(promotion["promotion_ready"])
        self.assertTrue(promotion["provider_backed_long_window_acceptance_done"])
        self.assertTrue(promotion["provider_evidence_from_prior_task"])
        self.assertTrue(promotion["explicit_promotion_marker_found"])
        self.assertEqual(promotion["blocking_criterion_count"], 0)
        self.assertFalse(promotion["provider_refresh_called_by_audit"])
        self.assertFalse(promotion["external_calls_triggered"])
        self.assertFalse(promotion["tushare_called"])
        self.assertTrue(packet["policy"]["trade_cal_provider_acceptance_promotion_ready"])
        self.assertFalse(packet["policy"]["trade_cal_provider_acceptance_promotion_still_pending"])
        self.assertEqual(packet["counts"]["trade_cal_provider_acceptance_evidence_row_count"], 1)
        self.assertEqual(packet["counts"]["trade_cal_provider_acceptance_promotion_blocker_count"], 0)
        self.assertEqual(promotion_rows["explicit_provider_call_ledger"]["status"], "passed")
        self.assertEqual(promotion_rows["minimum_long_window"]["status"], "passed")
        self.assertEqual(promotion_rows["freshness_gate_replay_evidence"]["status"], "passed")
        self.assertEqual(promotion_rows["failure_mode_evidence"]["status"], "passed")
        self.assertEqual(promotion_rows["explicit_promotion_marker"]["status"], "passed")
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])

    def test_recovery_center_cache_endpoint_returns_manual_recovery_plan(self):
        self._with_snapshot_cache(
            {
                "data_recovery_actions": [
                    {"label": "恢复 daily_basic", "api": "daily_basic", "authorization": "Bearer SHOULD_DROP"}
                ],
                "tool_recovery_actions": ["检查旧工具"],
                "recovery_result_timeline": [{"event": "等待手动恢复"}],
                "provider_recovery_matrix": {"items": [{"provider": "Tushare", "api": "moneyflow"}]},
                "data_gap_report": {"items": [{"label": "moneyflow missing"}]},
            }
        )

        response = self.client.get("/api/recovery/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_recovery_center_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["counts"]["action_count"], 3)
        self.assertEqual(packet["counts"]["timeline_count"], 1)
        self.assertEqual(packet["action_rows"][0]["label"], "恢复 daily_basic")
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_run_recovery_actions"])
        self.assertTrue(packet["policy"]["recovery_actions_are_manual_guidance"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_recovery_center_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/recovery/cache", response["warnings"][0])

    def test_post_task_stub_returns_task_id(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        created = self.client.post("/api/chokepoint/run", json={"ts_code": "002008.SZ"}).json()
        self.assertTrue(created["ok"])
        task_id = created["data"]["task_id"]
        self.assertTrue(task_id.startswith("local-"))
        self.assertEqual(created["call_ledger"][0]["call_status"], "stub_not_called")
        self.assert_local_ledger_boundary(created["call_ledger"][0])
        self.assertIn("本地 lifecycle stub", created["warnings"][0])

        status = self.client.get(f"/api/tasks/{task_id}").json()
        self.assertTrue(status["ok"])
        self.assertEqual(status["data"]["status"], "success")
        self.assertEqual(status["data"]["progress"], 1.0)
        self.assertEqual(status["data"]["storage_source"], "memory_and_sqlite")
        self.assertEqual(status["data"]["call_ledger"][0]["call_status"], "stub_not_called")
        self.assert_local_ledger_boundary(status["data"]["call_ledger"][0])
        self.assertEqual(status["call_ledger"][0]["call_status"], "stub_not_called")
        self.assert_local_ledger_boundary(status["call_ledger"][0])
        self.assertIn("本地 lifecycle stub", status["warnings"][0])

        logs = self.client.get(f"/api/tasks/{task_id}/logs").json()
        self.assertTrue(logs["ok"])
        self.assertEqual(logs["data"]["packet_key"], "command_center_3_task_log_packet")
        self.assertEqual(logs["data"]["mode"], "cache_only")
        self.assertEqual(logs["data"]["task_id"], task_id)
        self.assertEqual(logs["data"]["task_log_count"], 3)
        self.assertEqual(logs["data"]["status_history_count"], 3)
        self.assertTrue(logs["data"]["policy"]["get_task_logs_cache_only"])
        self.assertTrue(logs["data"]["policy"]["task_logs_safe"])
        self.assertFalse(logs["data"]["external_calls_triggered"])
        self.assertFalse(logs["data"]["tushare_called"])
        self.assertFalse(logs["data"]["deepseek_called"])
        self.assertFalse(logs["data"]["github_called"])
        self.assertTrue(logs["data"]["does_not_execute_trades"])
        self.assertTrue(logs["data"]["does_not_modify_strategy_action"])
        self.assertEqual(logs["call_ledger"][0]["api"], "local_task_log_lookup")
        self.assertEqual(logs["call_ledger"][0]["call_status"], "cache_read")
        self.assertEqual(logs["call_ledger"][0]["row_count"], 3)
        self.assert_local_ledger_boundary(logs["call_ledger"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(logs, ensure_ascii=False))

        listing = self.client.get("/api/tasks").json()
        self.assertTrue(listing["ok"])
        self.assertEqual(listing["data"]["packet_key"], "command_center_3_task_status_index")
        self.assertEqual(listing["data"]["mode"], "cache_only")
        self.assertEqual(listing["data"]["task_count"], 1)
        self.assertEqual(listing["data"]["status_counts"]["success"], 1)
        self.assertEqual(listing["data"]["call_ledger_count"], 1)
        self.assertEqual(listing["data"]["persistence"]["storage_backend"], "memory_plus_sqlite_fallback")
        self.assertTrue(listing["data"]["persistence"]["sqlite_fallback_enabled"])
        self.assertEqual(listing["data"]["persistence"]["memory_task_count"], 1)
        self.assertEqual(listing["data"]["persistence"]["sqlite_task_count"], 1)
        self.assertEqual(listing["data"]["persistence"]["deduplicated_task_count"], 1)
        self.assertEqual(listing["data"]["persistence"]["memory_and_sqlite_task_count"], 1)
        self.assertTrue(listing["data"]["persistence"]["task_rows_include_storage_source"])
        self.assertEqual({row["source"] for row in listing["data"]["persistence_source_rows"]}, {"memory", "sqlite_meta", "deduplicated"})
        self.assertFalse(listing["data"]["external_calls_triggered"])
        self.assertFalse(listing["data"]["tushare_called"])
        self.assertFalse(listing["data"]["deepseek_called"])
        self.assertFalse(listing["data"]["github_called"])
        self.assertTrue(listing["data"]["does_not_execute_trades"])
        self.assertTrue(listing["data"]["does_not_modify_strategy_action"])
        self.assertEqual(listing["call_ledger"][0]["api"], "local_task_status_index")
        self.assertEqual(listing["call_ledger"][0]["storage_backend"], "memory_plus_sqlite_fallback")
        self.assertEqual(listing["call_ledger"][0]["memory_task_count"], 1)
        self.assertEqual(listing["call_ledger"][0]["sqlite_task_count"], 1)
        self.assertEqual(listing["call_ledger"][0]["deduplicated_task_count"], 1)
        self.assert_local_ledger_boundary(listing["call_ledger"][0])
        self.assertEqual(listing["data"]["tasks"][0]["task_id"], task_id)
        self.assertEqual(listing["data"]["tasks"][0]["storage_source"], "memory_and_sqlite")
        task_service._TASKS.clear()
        persisted_status = self.client.get(f"/api/tasks/{task_id}").json()
        self.assertTrue(persisted_status["ok"])
        self.assertEqual(persisted_status["data"]["task_id"], task_id)
        self.assertEqual(persisted_status["data"]["backend"], "local_fallback")
        self.assertEqual(persisted_status["data"]["storage_source"], "sqlite_meta")
        self.assertEqual(persisted_status["call_ledger"][0]["call_status"], "stub_not_called")

        persisted_listing = self.client.get("/api/tasks").json()
        self.assertEqual(persisted_listing["data"]["persistence"]["memory_task_count"], 0)
        self.assertEqual(persisted_listing["data"]["persistence"]["sqlite_task_count"], 1)
        self.assertEqual(persisted_listing["data"]["persistence"]["sqlite_only_task_count"], 1)
        self.assertEqual(persisted_listing["data"]["tasks"][0]["storage_source"], "sqlite_meta")

    def test_missing_task_detail_and_cancel_return_safe_local_lineage(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)

        missing = self.client.get("/api/tasks/token=SHOULD_DROP").json()

        self.assertFalse(missing["ok"])
        self.assertEqual(missing["error"], "task_not_found")
        self.assertEqual(missing["call_ledger"][0]["api"], "local_task_status_lookup")
        self.assertEqual(missing["call_ledger"][0]["call_status"], "task_not_found_no_external_call")
        self.assertEqual(missing["call_ledger"][0]["error_message_safe"], "task_not_found")
        self.assertEqual(missing["call_ledger"][0]["request_params_safe"]["task_id"], "[redacted_sensitive_text]")
        self.assert_local_ledger_boundary(missing["call_ledger"][0])
        self.assertIn("GET /api/tasks/{task_id}", missing["warnings"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(missing, ensure_ascii=False))

        missing_logs = self.client.get("/api/tasks/token=SHOULD_DROP/logs").json()
        self.assertFalse(missing_logs["ok"])
        self.assertEqual(missing_logs["error"], "task_not_found")
        self.assertEqual(missing_logs["call_ledger"][0]["api"], "local_task_log_lookup")
        self.assertEqual(missing_logs["call_ledger"][0]["call_status"], "task_not_found_no_external_call")
        self.assertEqual(missing_logs["call_ledger"][0]["request_params_safe"]["task_id"], "[redacted_sensitive_text]")
        self.assert_local_ledger_boundary(missing_logs["call_ledger"][0])
        self.assertIn("GET /api/tasks/{task_id}/logs", missing_logs["warnings"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(missing_logs, ensure_ascii=False))

        cancelled = self.client.post("/api/tasks/token=SHOULD_DROP/cancel", json={"reason": "token=SHOULD_DROP"}).json()

        self.assertFalse(cancelled["ok"])
        self.assertEqual(cancelled["error"], "task_not_found")
        self.assertEqual(cancelled["call_ledger"][0]["api"], "local_task_cancel")
        self.assertEqual(cancelled["call_ledger"][0]["call_status"], "task_not_found_no_external_call")
        self.assertEqual(cancelled["call_ledger"][0]["request_params_safe"]["task_id"], "[redacted_sensitive_text]")
        self.assert_local_ledger_boundary(cancelled["call_ledger"][0])
        self.assertIn("POST /api/tasks/{task_id}/cancel", cancelled["warnings"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(cancelled, ensure_ascii=False))

        retried = self.client.post("/api/tasks/token=SHOULD_DROP/retry", json={"reason": "token=SHOULD_DROP"}).json()

        self.assertFalse(retried["ok"])
        self.assertEqual(retried["error"], "task_not_found")
        self.assertEqual(retried["call_ledger"][0]["api"], "local_task_retry")
        self.assertEqual(retried["call_ledger"][0]["call_status"], "task_not_found_no_external_call")
        self.assertEqual(retried["call_ledger"][0]["request_params_safe"]["task_id"], "[redacted_sensitive_text]")
        self.assert_local_ledger_boundary(retried["call_ledger"][0])
        self.assertIn("POST /api/tasks/{task_id}/retry", retried["warnings"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(retried, ensure_ascii=False))

    def test_button_gated_stub_task_endpoints_expose_top_level_lineage(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)

        for path in ("/api/chokepoint/run", "/api/serenity/github-probe"):
            response = self.client.post(path, json={"token": "SHOULD_DROP"}).json()
            self.assertTrue(response["ok"])
            self.assertTrue(response["data"]["task_id"].startswith("local-"))
            self.assertEqual(response["call_ledger"][0]["call_status"], "stub_not_called")
            self.assert_local_ledger_boundary(response["call_ledger"][0])
            request_params_safe = response["call_ledger"][0]["request_params_safe"]
            if path == "/api/chokepoint/run":
                model_strategy = request_params_safe["deepseek_model_strategy"]
                self.assertEqual(model_strategy["purpose"], "explain")
                self.assertIn("DEEPSEEK_EXPLAIN_MODEL", model_strategy["config_keys"])
                self.assertTrue(model_strategy["does_not_hardcode_model"])
                self.assertFalse(model_strategy["contains_secret"])
            else:
                self.assertNotIn("deepseek_model_strategy", request_params_safe)
            self.assertIn("本地 lifecycle stub", response["warnings"][0])
            self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))

    def test_next_session_generate_endpoint_uses_local_cache_pipeline(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "command_center_next_session_projection_packet": {
                    "packet_key": "command_center_next_session_projection_packet",
                    "status": "ready",
                    "trade_date": "20260610",
                    "chart_render_model": {
                        "historical_series": [{"x": "2026-06-10", "price": 10.4}],
                        "scenario_series": [{"scenario_key": "neutral", "scenario_name": "中性路径", "points": [{"x": "T+1", "price": 10.8}]}],
                        "current_price_line": 10.4,
                    },
                }
            }
        )

        created = self.client.post("/api/next-session/generate", json={"ts_code": "002008.SZ", "authorization": "Bearer SHOULD_DROP"}).json()

        self.assertTrue(created["ok"])
        task = created["data"]["task"]
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "next_session_cache_written_to_sqlite")
        self.assertEqual(task["call_ledger"][0]["api"], "local_next_session_cache")
        self.assertEqual(task["call_ledger"][0]["call_status"], "exact_cache_read")
        self.assertEqual(created["call_ledger"][0]["call_status"], "exact_cache_read")
        self.assertIn("当前只执行本地 cache pipeline", created["warnings"][0])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertNotIn("authorization", task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(created, ensure_ascii=False))

        cache = self.client.get("/api/next-session/cache").json()
        self.assertTrue(cache["ok"])
        self.assertEqual(cache["data"]["status"], "ready")
        self.assertFalse(cache["data"]["external_calls_triggered"])
        self.assertTrue(cache["data"]["does_not_modify_action"])
        self.assertEqual(cache["call_ledger"][0]["api"], "local_next_session_cache")
        self.assertIn(cache["call_ledger"][0]["call_status"], {"cache_read", "exact_cache_read"})
        self.assertFalse(cache["call_ledger"][0]["external"])

    def test_task_cancel_endpoint_marks_pending_task_without_external_work(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        task = task_service.create_task_record(
            "build_next_session_projection",
            output_packet_key="command_center_next_session_projection_packet",
            payload={"authorization": "Bearer SHOULD_DROP", "ts_code": "002008.SZ"},
        )

        cancelled = self.client.post(f"/api/tasks/{task['task_id']}/cancel", json={"reason": "manual"}).json()

        self.assertTrue(cancelled["ok"])
        packet = cancelled["data"]["task"]
        self.assertEqual(packet["status"], "cancelled")
        self.assertEqual(packet["current_step"], "cancelled_by_user_no_external_call")
        self.assertEqual(packet["call_ledger"][-1]["api"], "local_task_cancel")
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(cancelled, ensure_ascii=False))

    def test_task_retry_endpoint_creates_new_pending_task_without_external_work(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        task = task_service.create_task_record(
            "run_factor_light",
            output_packet_key="command_center_factor_quant_hub_packet",
            payload={"authorization": "Bearer SHOULD_DROP", "ts_code": "002008.SZ"},
        )
        failed = task_service.update_task_status(
            task["task_id"],
            status="failed",
            progress=0.4,
            current_step="failed_before_retry",
            error_message_safe="provider unavailable token=SHOULD_DROP",
        )

        retried = self.client.post(f"/api/tasks/{task['task_id']}/retry", json={"reason": "manual token=SHOULD_DROP"}).json()

        self.assertTrue(retried["ok"])
        new_task = retried["data"]["task"]
        self.assertNotEqual(new_task["task_id"], task["task_id"])
        self.assertEqual(new_task["status"], "pending")
        self.assertEqual(new_task["task_type"], "run_factor_light")
        self.assertEqual(new_task["retry_source_task_id"], task["task_id"])
        self.assertEqual(new_task["current_step"], "manual_retry_queued_no_external_call")
        self.assertEqual(new_task["call_ledger"][0]["api"], "local_task_retry")
        self.assertEqual(new_task["call_ledger"][0]["call_status"], "manual_retry_created_no_external_call")
        self.assertEqual(new_task["call_ledger"][0]["request_params_safe"]["source_task_id"], task["task_id"])
        self.assertEqual(new_task["retry_policy"]["attempt_number"], failed["retry_policy"]["attempt_number"] + 1)
        self.assertFalse(new_task["retry_policy"]["auto_retry_enabled"])
        self.assertFalse(new_task["external_calls_triggered"])
        self.assertFalse(new_task["tushare_called"])
        self.assertFalse(new_task["deepseek_called"])
        self.assertFalse(new_task["github_called"])
        self.assertTrue(new_task["does_not_execute_trades"])
        self.assertTrue(new_task["does_not_modify_strategy_action"])
        self.assertNotIn("authorization", new_task["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(retried, ensure_ascii=False))

        source = self.client.get(f"/api/tasks/{task['task_id']}").json()["data"]
        self.assertIn("manual_retry_spawned_new_task_no_external_call", source["warnings"])
        self.assertEqual(source["task_log"][-1]["event"], "manual_retry_spawned_new_task")

    def test_task_retry_endpoint_rejects_non_failed_task_without_external_work(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        task = task_service.create_task_record(
            "run_factor_light",
            output_packet_key="command_center_factor_quant_hub_packet",
            payload={"ts_code": "002008.SZ"},
        )

        retried = self.client.post(f"/api/tasks/{task['task_id']}/retry", json={"reason": "manual"}).json()

        self.assertFalse(retried["ok"])
        self.assertEqual(retried["error"], "manual_retry_not_eligible")
        packet = retried["data"]["task"]
        self.assertEqual(packet["status"], "pending")
        self.assertEqual(retried["call_ledger"][0]["api"], "local_task_retry")
        self.assertEqual(retried["call_ledger"][0]["call_status"], "manual_retry_not_eligible_no_external_call")
        self.assert_local_ledger_boundary(retried["call_ledger"][0])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])

    def test_worker_runtime_cache_endpoint_returns_local_backend_readiness(self):
        response = self.client.get("/api/worker/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_worker_runtime_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertGreaterEqual(packet["counts"]["backend_count"], 4)
        self.assertGreaterEqual(packet["counts"]["worker_module_count"], 6)
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["redis_pinged"])
        self.assertFalse(packet["runtime"]["celery_worker_started"])
        self.assertFalse(packet["runtime"]["scheduler_started"])
        self.assertTrue(packet["policy"]["post_task_required_for_work"])
        self.assertTrue(packet["policy"]["worker_runtime_is_diagnostic_only"])
        self.assertEqual(packet["worker_production_blocker_audit"]["status"], "production_worker_blocked")
        self.assertFalse(packet["worker_production_blocker_audit"]["production_worker_complete"])
        self.assertGreater(packet["worker_production_blocker_audit"]["blocking_criterion_count"], 0)
        self.assertIn("celery_worker_started", {row["criterion"] for row in packet["worker_production_blocker_rows"]})
        healthcheck = packet["worker_healthcheck_qa_contract"]
        self.assertEqual(healthcheck["schema_version"], "worker_healthcheck_qa_contract.v1")
        self.assertEqual(healthcheck["status"], "worker_healthcheck_qa_contract_ready_execution_pending")
        self.assertEqual(healthcheck["scope"], "local_static_healthcheck_contract_no_process_start")
        self.assertFalse(healthcheck["production_worker_complete"])
        self.assertFalse(healthcheck["healthcheck_executed"])
        self.assertFalse(healthcheck["healthcheck_task_dispatched"])
        self.assertFalse(healthcheck["cache_api_started_workers"])
        self.assertFalse(healthcheck["cache_api_pinged_redis"])
        self.assertFalse(healthcheck["cache_api_started_scheduler"])
        self.assertFalse(healthcheck["external_calls_triggered"])
        self.assertFalse(healthcheck["tushare_called"])
        self.assertFalse(healthcheck["deepseek_called"])
        self.assertFalse(healthcheck["github_called"])
        self.assertTrue(healthcheck["synthetic_task_only"])
        self.assertFalse(healthcheck["provider_model_task_validation_in_scope"])
        self.assertTrue(healthcheck["does_not_execute_trades"])
        self.assertTrue(healthcheck["does_not_modify_strategy_action"])
        self.assertGreater(healthcheck["pending_criterion_count"], 0)
        healthcheck_criteria = {row["criterion"] for row in packet["worker_healthcheck_qa_rows"]}
        self.assertIn("celery_worker_process_visible", healthcheck_criteria)
        self.assertIn("redis_broker_reachable", healthcheck_criteria)
        self.assertIn("task_round_trip_healthcheck", healthcheck_criteria)
        self.assertIn("provider_model_tasks_not_autoscheduled", healthcheck_criteria)
        self.assertIn("external_call_boundary", healthcheck_criteria)
        activation_review = packet["worker_activation_review_contract"]
        self.assertEqual(activation_review["schema_version"], "worker_activation_review_contract.v1")
        self.assertEqual(activation_review["status"], "worker_activation_review_ready_activation_pending")
        self.assertFalse(activation_review["activation_ready"])
        self.assertFalse(activation_review["production_worker_complete"])
        self.assertFalse(activation_review["worker_started_by_cache_api"])
        self.assertFalse(activation_review["redis_pinged_by_cache_api"])
        self.assertFalse(activation_review["task_dispatched_by_cache_api"])
        self.assertFalse(activation_review["external_calls_triggered"])
        self.assertTrue(activation_review["manual_activation_required"])
        activation_review_steps = {row["review_step"] for row in packet["worker_activation_review_rows"]}
        self.assertIn("review_celery_manual_start", activation_review_steps)
        self.assertIn("review_synthetic_healthcheck", activation_review_steps)
        self.assertIn("review_provider_model_isolation", activation_review_steps)
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_worker_runtime_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/worker/cache", response["warnings"][0])

    def test_call_ledger_audit_cache_endpoint_returns_read_only_audit(self):
        response = self.client.get("/api/audit/cache").json()

        self.assertTrue(response["ok"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_call_ledger_audit_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_call_ledger_audit_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertGreater(packet["counts"]["cache_endpoint_count"], 10)
        endpoint_sources = {row["source"] for row in packet["endpoint_rows"]}
        self.assertIn("model_strategy", endpoint_sources)
        self.assertIn("desktop_preflight", endpoint_sources)
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["policy"]["audit_is_read_only"])
        self.assertTrue(packet["policy"]["does_not_refresh_data"])
        self.assertEqual(packet["task_implementation_status"]["status"], "partial_migration")
        self.assertTrue(packet["policy"]["task_implementation_status_is_read_only"])
        self.assertTrue(packet["policy"]["release_gate_audit_is_static"])
        self.assertTrue(packet["policy"]["release_gate_audit_runs_no_commands"])
        self.assertTrue(packet["policy"]["release_gate_audit_calls_no_github_api"])
        self.assertTrue(packet["policy"]["release_gate_local_ready_is_not_ci_status"])
        self.assertTrue(packet["policy"]["motion_clarity_audit_is_static"])
        self.assertTrue(packet["policy"]["motion_clarity_audit_runs_no_commands"])
        self.assertTrue(packet["policy"]["motion_clarity_static_ready_is_not_visual_qa"])
        release_gate = packet["release_gate_readiness_audit"]
        self.assertEqual(release_gate["schema_version"], "command_center_3_release_gate_readiness_audit.v1")
        self.assertEqual(release_gate["scope"], "local_static_push_gate_contract_not_ci_status")
        self.assertEqual(release_gate["status"], "local_gate_ready_allowlist_review_pending")
        self.assertTrue(release_gate["local_gate_ready"])
        self.assertFalse(release_gate["release_gate_complete"])
        self.assertTrue(release_gate["ci_mirror_ready"])
        self.assertFalse(release_gate["provider_calls_triggered"])
        self.assertFalse(release_gate["external_calls_triggered"])
        self.assertFalse(release_gate["tushare_called"])
        self.assertFalse(release_gate["deepseek_called"])
        self.assertFalse(release_gate["github_api_called"])
        self.assertTrue(release_gate["does_not_execute_trades"])
        self.assertTrue(release_gate["push_gate_script_exists"])
        self.assertTrue(release_gate["push_gate_script_executable"])
        self.assertTrue(release_gate["uses_project_venv_python"])
        self.assertTrue(release_gate["refuses_missing_project_python"])
        self.assertTrue(release_gate["python_unittest_step"])
        self.assertTrue(release_gate["desktop_build_step"])
        self.assertTrue(release_gate["smoke_step"])
        self.assertTrue(release_gate["data_health_freshness_contract_exists"])
        self.assertTrue(release_gate["data_health_freshness_contract_step"])
        self.assertTrue(release_gate["data_health_freshness_contract_is_local"])
        self.assertTrue(release_gate["tushare_acceptance_contract_exists"])
        self.assertTrue(release_gate["tushare_acceptance_contract_step"])
        self.assertTrue(release_gate["tushare_acceptance_contract_is_local"])
        self.assertTrue(release_gate["factor_test_lab_contract_exists"])
        self.assertTrue(release_gate["factor_test_lab_contract_step"])
        self.assertTrue(release_gate["factor_test_lab_contract_is_local"])
        self.assertTrue(release_gate["factor_universe_contract_exists"])
        self.assertTrue(release_gate["factor_universe_contract_step"])
        self.assertTrue(release_gate["factor_universe_contract_is_local"])
        self.assertTrue(release_gate["deepseek_governance_contract_exists"])
        self.assertTrue(release_gate["deepseek_governance_contract_step"])
        self.assertTrue(release_gate["deepseek_governance_contract_is_local"])
        self.assertTrue(release_gate["next_session_map_contract_exists"])
        self.assertTrue(release_gate["next_session_map_contract_step"])
        self.assertTrue(release_gate["next_session_map_contract_is_local"])
        self.assertTrue(release_gate["candidate_radar_contract_exists"])
        self.assertTrue(release_gate["candidate_radar_contract_step"])
        self.assertTrue(release_gate["candidate_radar_contract_is_local"])
        self.assertTrue(release_gate["candidate_radar_browser_qa_runbook_exists"])
        self.assertTrue(release_gate["candidate_radar_browser_qa_runbook_step"])
        self.assertTrue(release_gate["candidate_radar_browser_qa_runbook_is_local"])
        self.assertTrue(release_gate["storage_contract_exists"])
        self.assertTrue(release_gate["storage_contract_step"])
        self.assertTrue(release_gate["storage_contract_is_local"])
        self.assertTrue(release_gate["worker_contract_exists"])
        self.assertTrue(release_gate["worker_contract_step"])
        self.assertTrue(release_gate["worker_contract_is_local"])
        self.assertTrue(release_gate["tauri_desktop_contract_exists"])
        self.assertTrue(release_gate["tauri_desktop_contract_step"])
        self.assertTrue(release_gate["tauri_desktop_contract_is_local"])
        self.assertTrue(release_gate["streamlit_legacy_contract_exists"])
        self.assertTrue(release_gate["streamlit_legacy_contract_step"])
        self.assertTrue(release_gate["streamlit_legacy_contract_is_local"])
        self.assertTrue(release_gate["trade_isolation_contract_exists"])
        self.assertTrue(release_gate["trade_isolation_contract_step"])
        self.assertTrue(release_gate["trade_isolation_contract_is_local"])
        self.assertTrue(release_gate["motion_viewport_qa_contract_exists"])
        self.assertTrue(release_gate["motion_viewport_qa_contract_step"])
        self.assertTrue(release_gate["motion_viewport_qa_contract_is_local_static"])
        self.assertTrue(release_gate["motion_browser_qa_runbook_exists"])
        self.assertTrue(release_gate["motion_browser_qa_runbook_step"])
        self.assertTrue(release_gate["motion_browser_qa_runbook_is_local_static"])
        self.assertTrue(release_gate["secret_keyword_review_contract_exists"])
        self.assertTrue(release_gate["secret_keyword_review_contract_step"])
        self.assertTrue(release_gate["secret_keyword_review_contract_is_structured"])
        self.assertTrue(release_gate["diff_check_step"])
        self.assertTrue(release_gate["high_risk_secret_scan_step"])
        self.assertTrue(release_gate["keyword_review_scan_step"])
        self.assertTrue(release_gate["keyword_review_raw_lines_suppressed"])
        self.assertTrue(release_gate["generated_artifact_scan_step"])
        self.assertTrue(release_gate["release_report_step"])
        self.assertTrue(release_gate["clean_worktree_after_report"])
        self.assertTrue(release_gate["no_git_push"])
        self.assertTrue(release_gate["no_git_add_dot"])
        self.assertNotIn("ci_mirror_not_proven", release_gate["blockers"])
        self.assertIn("false_positive_allowlist_review_pending", release_gate["soft_blockers"])
        release_gate_criteria = {row["criterion"] for row in packet["release_gate_readiness_rows"]}
        self.assertIn("python_unittest", release_gate_criteria)
        self.assertIn("desktop_build", release_gate_criteria)
        self.assertIn("command_center_3_smoke", release_gate_criteria)
        self.assertIn("data_health_freshness_contract_exists", release_gate_criteria)
        self.assertIn("data_health_freshness_contract_step", release_gate_criteria)
        self.assertIn("data_health_freshness_contract_is_local", release_gate_criteria)
        self.assertIn("tushare_acceptance_contract_exists", release_gate_criteria)
        self.assertIn("tushare_acceptance_contract_step", release_gate_criteria)
        self.assertIn("tushare_acceptance_contract_is_local", release_gate_criteria)
        self.assertIn("factor_test_lab_contract_exists", release_gate_criteria)
        self.assertIn("factor_test_lab_contract_step", release_gate_criteria)
        self.assertIn("factor_test_lab_contract_is_local", release_gate_criteria)
        self.assertIn("factor_universe_contract_exists", release_gate_criteria)
        self.assertIn("factor_universe_contract_step", release_gate_criteria)
        self.assertIn("factor_universe_contract_is_local", release_gate_criteria)
        self.assertIn("deepseek_governance_contract_exists", release_gate_criteria)
        self.assertIn("deepseek_governance_contract_step", release_gate_criteria)
        self.assertIn("deepseek_governance_contract_is_local", release_gate_criteria)
        self.assertIn("next_session_map_contract_exists", release_gate_criteria)
        self.assertIn("next_session_map_contract_step", release_gate_criteria)
        self.assertIn("next_session_map_contract_is_local", release_gate_criteria)
        self.assertIn("candidate_radar_contract_exists", release_gate_criteria)
        self.assertIn("candidate_radar_contract_step", release_gate_criteria)
        self.assertIn("candidate_radar_contract_is_local", release_gate_criteria)
        self.assertIn("candidate_radar_browser_qa_runbook_exists", release_gate_criteria)
        self.assertIn("candidate_radar_browser_qa_runbook_step", release_gate_criteria)
        self.assertIn("candidate_radar_browser_qa_runbook_is_local", release_gate_criteria)
        self.assertIn("storage_contract_exists", release_gate_criteria)
        self.assertIn("storage_contract_step", release_gate_criteria)
        self.assertIn("storage_contract_is_local", release_gate_criteria)
        self.assertIn("worker_contract_exists", release_gate_criteria)
        self.assertIn("worker_contract_step", release_gate_criteria)
        self.assertIn("worker_contract_is_local", release_gate_criteria)
        self.assertIn("tauri_desktop_contract_exists", release_gate_criteria)
        self.assertIn("tauri_desktop_contract_step", release_gate_criteria)
        self.assertIn("tauri_desktop_contract_is_local", release_gate_criteria)
        self.assertIn("streamlit_legacy_contract_exists", release_gate_criteria)
        self.assertIn("streamlit_legacy_contract_step", release_gate_criteria)
        self.assertIn("streamlit_legacy_contract_is_local", release_gate_criteria)
        self.assertIn("trade_isolation_contract_exists", release_gate_criteria)
        self.assertIn("trade_isolation_contract_step", release_gate_criteria)
        self.assertIn("trade_isolation_contract_is_local", release_gate_criteria)
        self.assertIn("motion_viewport_qa_contract_exists", release_gate_criteria)
        self.assertIn("motion_viewport_qa_contract_step", release_gate_criteria)
        self.assertIn("motion_viewport_qa_contract_is_local_static", release_gate_criteria)
        self.assertIn("motion_browser_qa_runbook_exists", release_gate_criteria)
        self.assertIn("motion_browser_qa_runbook_step", release_gate_criteria)
        self.assertIn("motion_browser_qa_runbook_is_local_static", release_gate_criteria)
        self.assertIn("secret_keyword_review_contract_exists", release_gate_criteria)
        self.assertIn("secret_keyword_review_contract_step", release_gate_criteria)
        self.assertIn("secret_keyword_review_contract_is_structured", release_gate_criteria)
        self.assertIn("diff_whitespace_check", release_gate_criteria)
        self.assertIn("high_risk_secret_scan", release_gate_criteria)
        self.assertIn("keyword_review_raw_lines_suppressed", release_gate_criteria)
        self.assertIn("generated_artifact_scan", release_gate_criteria)
        self.assertIn("release_readiness_report", release_gate_criteria)
        self.assertIn("clean_worktree_after_report", release_gate_criteria)
        self.assertIn("no_git_push", release_gate_criteria)
        self.assertIn("no_git_add_dot", release_gate_criteria)
        workflow_rows = {row["workflow"]: row for row in packet["release_gate_workflow_rows"]}
        self.assertIn(".github/workflows/command-center-3-push-gate.yml", workflow_rows)
        ci_workflow = workflow_rows[".github/workflows/command-center-3-push-gate.yml"]
        self.assertEqual(ci_workflow["status"], "mirrors_push_gate")
        self.assertTrue(ci_workflow["mirrors_local_push_gate"])
        self.assertTrue(ci_workflow["contains_smoke_step"])
        self.assertFalse(ci_workflow["github_api_call_detected"])
        self.assertGreaterEqual(packet["counts"]["release_gate_check_count"], 20)
        self.assertGreaterEqual(packet["counts"]["release_gate_workflow_count"], 0)
        self.assertTrue(packet["counts"]["release_gate_local_ready"])
        self.assertTrue(packet["counts"]["release_gate_ci_mirror_ready"])
        self.assertFalse(packet["counts"]["release_gate_complete"])
        motion = packet["motion_clarity_audit"]
        self.assertEqual(motion["schema_version"], "command_center_3_motion_clarity_audit.v1")
        self.assertEqual(motion["scope"], "local_static_source_audit_not_browser_visual_qa")
        self.assertEqual(motion["status"], "motion_clarity_static_ready_visual_qa_pending")
        self.assertTrue(motion["static_ready"])
        self.assertFalse(motion["production_motion_complete"])
        self.assertFalse(motion["visual_qa_complete"])
        self.assertFalse(motion["browser_performance_verified"])
        self.assertFalse(motion["external_calls_triggered"])
        self.assertFalse(motion["tushare_called"])
        self.assertFalse(motion["deepseek_called"])
        self.assertFalse(motion["github_called"])
        self.assertTrue(motion["does_not_execute_trades"])
        self.assertTrue(motion["does_not_modify_packets"])
        self.assertEqual(motion["blocking_criterion_count"], 0)
        self.assertIn("desktop_mobile_viewport_visual_qa_pending", motion["soft_blockers"])
        self.assertIn("browser_performance_trace_pending", motion["soft_blockers"])
        motion_criteria = {row["criterion"] for row in packet["motion_clarity_rows"]}
        self.assertIn("motion_tokens_present", motion_criteria)
        self.assertIn("reduced_motion_css", motion_criteria)
        self.assertIn("navigation_context_cue", motion_criteria)
        self.assertIn("status_badge_context_cue", motion_criteria)
        self.assertIn("chart_reduced_motion_runtime", motion_criteria)
        self.assertIn("task_phase_confirmation_cue", motion_criteria)
        self.assertIn("task_receipt_confirmation_cue", motion_criteria)
        self.assertIn("cache_refresh_confirmation_cue", motion_criteria)
        self.assertIn("motion_viewport_qa_contract_ready", motion_criteria)
        self.assertIn("motion_browser_qa_runbook_ready", motion_criteria)
        self.assertIn("radar_clarity_scope", motion_criteria)
        self.assertIn("mobile_responsive_motion_layout", motion_criteria)
        self.assertIn("no_timer_or_raf_motion_loop", motion_criteria)
        self.assertIn("desktop_mobile_viewport_visual_qa_pending", motion_criteria)
        self.assertTrue(packet["counts"]["motion_clarity_static_ready"])
        self.assertTrue(motion["navigation_context_cue"])
        self.assertTrue(motion["status_badge_context_cue"])
        self.assertTrue(motion["task_phase_confirmation_cue"])
        self.assertTrue(motion["task_receipt_confirmation_cue"])
        self.assertTrue(motion["cache_refresh_confirmation_cue"])
        self.assertTrue(motion["mobile_responsive_motion_layout"])
        self.assertTrue(motion["motion_viewport_qa_contract_ready"])
        self.assertTrue(motion["motion_browser_qa_runbook_ready"])
        self.assertEqual(packet["counts"]["motion_clarity_blocker_count"], 0)
        production_motion = packet["motion_production_qa_contract"]
        self.assertEqual(production_motion["schema_version"], "command_center_3_motion_production_qa_contract.v1")
        self.assertEqual(production_motion["scope"], "local_motion_production_qa_contract_not_browser_visual_or_perf_proof")
        self.assertEqual(production_motion["status"], "motion_production_qa_local_ready_visual_perf_pending")
        self.assertEqual(production_motion["design_intent"], "state_clarity_first_restrained_keynote_motion")
        self.assertTrue(production_motion["local_motion_qa_ready"])
        self.assertFalse(production_motion["production_motion_complete"])
        self.assertFalse(production_motion["visual_qa_complete"])
        self.assertFalse(production_motion["browser_performance_verified"])
        self.assertFalse(production_motion["external_calls_triggered"])
        self.assertFalse(production_motion["tushare_called"])
        self.assertFalse(production_motion["deepseek_called"])
        self.assertFalse(production_motion["github_called"])
        self.assertTrue(production_motion["does_not_execute_trades"])
        self.assertTrue(production_motion["does_not_modify_packets"])
        self.assertGreater(production_motion["production_blocker_count"], 0)
        self.assertGreater(production_motion["visual_pending_count"], 0)
        self.assertGreater(production_motion["performance_pending_count"], 0)
        production_motion_criteria = {row["criterion"] for row in packet["motion_production_qa_rows"]}
        self.assertIn("purposeful_motion_tokens", production_motion_criteria)
        self.assertIn("state_change_clarity", production_motion_criteria)
        self.assertIn("chart_and_radar_motion_scope", production_motion_criteria)
        self.assertIn("reduced_motion_accessibility", production_motion_criteria)
        self.assertIn("layout_containment_and_readability", production_motion_criteria)
        self.assertIn("visual_qa_execution_pending", production_motion_criteria)
        self.assertIn("browser_qa_runbook_ready", production_motion_criteria)
        self.assertIn("performance_trace_pending", production_motion_criteria)
        self.assertIn("provider_and_trade_isolation", production_motion_criteria)
        self.assertTrue(packet["counts"]["motion_production_qa_local_ready"])
        self.assertGreater(packet["counts"]["motion_production_blocker_count"], 0)
        self.assertGreater(packet["counts"]["motion_performance_pending_count"], 0)
        self.assertTrue(packet["policy"]["motion_production_qa_contract_is_local"])
        self.assertTrue(packet["policy"]["motion_production_qa_is_not_browser_visual_or_perf_proof"])
        runbook = packet["motion_browser_qa_runbook_contract"]
        self.assertEqual(runbook["schema_version"], "command_center_3_motion_browser_qa_runbook.v1")
        self.assertEqual(runbook["scope"], "local_browser_qa_runbook_not_browser_execution")
        self.assertEqual(runbook["status"], "motion_browser_qa_runbook_ready_execution_pending")
        self.assertTrue(runbook["local_runbook_ready"])
        self.assertTrue(runbook["browser_runner_available"])
        self.assertTrue(runbook["runner_executes_only_when_called"])
        self.assertTrue(runbook["runner_starts_no_servers"])
        self.assertTrue(runbook["runner_writes_ignored_local_artifacts"])
        self.assertEqual(runbook["runner_script"], "scripts/motion_browser_qa_runner.mjs")
        self.assertFalse(runbook["visual_qa_complete"])
        self.assertFalse(runbook["browser_performance_verified"])
        self.assertFalse(runbook["production_motion_complete"])
        self.assertTrue(runbook["opens_no_browser"])
        self.assertTrue(runbook["writes_no_artifacts"])
        self.assertFalse(runbook["external_calls_triggered"])
        self.assertFalse(runbook["tushare_called"])
        self.assertFalse(runbook["deepseek_called"])
        self.assertFalse(runbook["github_called"])
        self.assertTrue(runbook["does_not_execute_trades"])
        self.assertTrue(runbook["does_not_modify_strategy_action"])
        self.assertEqual(runbook["route_count"], 5)
        self.assertEqual(runbook["viewport_count"], 4)
        self.assertEqual(runbook["qa_matrix_count"], 20)
        self.assertGreaterEqual(runbook["performance_budget_count"], 4)
        runbook_phases = {row["phase"] for row in packet["motion_browser_qa_runbook_rows"]}
        self.assertIn("start_fastapi_backend", runbook_phases)
        self.assertIn("capture_performance_trace", runbook_phases)
        self.assertIn("explicit_runner_available", runbook_phases)
        matrix_routes = {row.get("route") for row in packet["motion_browser_qa_matrix_rows"] if row.get("route")}
        self.assertIn("#candidates", matrix_routes)
        budget_metrics = {row.get("metric") for row in packet["motion_browser_qa_matrix_rows"] if row.get("metric")}
        self.assertIn("route_transition_observed_ms", budget_metrics)
        self.assertTrue(packet["counts"]["motion_browser_qa_runbook_ready"])
        self.assertEqual(packet["counts"]["motion_browser_qa_matrix_count"], 20)
        self.assertGreaterEqual(packet["counts"]["motion_browser_qa_performance_budget_count"], 4)
        self.assertTrue(packet["policy"]["motion_browser_qa_runbook_is_local"])
        self.assertTrue(packet["policy"]["motion_browser_qa_runbook_is_not_browser_execution"])
        evidence = packet["motion_browser_qa_evidence_contract"]
        self.assertEqual(evidence["schema_version"], "command_center_3_motion_browser_qa_evidence.v1")
        self.assertEqual(evidence["scope"], "local_ignored_browser_qa_reports_summary_not_tracked_artifact")
        self.assertIn(
            evidence["status"],
            {"motion_browser_qa_evidence_available_review_pending", "motion_browser_qa_evidence_pending"},
        )
        self.assertTrue(evidence["reads_ignored_local_reports_only"])
        self.assertTrue(evidence["screenshots_are_not_tracked"])
        self.assertTrue(evidence["report_artifacts_are_not_tracked"])
        self.assertFalse(evidence["production_motion_complete"])
        self.assertFalse(evidence["external_calls_triggered"])
        self.assertFalse(evidence["tushare_called"])
        self.assertFalse(evidence["deepseek_called"])
        self.assertFalse(evidence["github_called"])
        self.assertTrue(evidence["does_not_execute_trades"])
        self.assertTrue(evidence["does_not_modify_strategy_action"])
        self.assertEqual(len(packet["motion_browser_qa_evidence_rows"]), evidence["row_count"])
        self.assertEqual(packet["counts"]["motion_browser_qa_evidence_report_count"], evidence["report_count"])
        self.assertEqual(
            packet["counts"]["motion_browser_qa_evidence_passing_report_count"],
            evidence["passing_report_count"],
        )
        self.assertEqual(packet["counts"]["motion_browser_qa_default_passed"], evidence["default_motion_passed"])
        self.assertEqual(packet["counts"]["motion_browser_qa_reduced_motion_passed"], evidence["reduced_motion_passed"])
        if evidence["visual_qa_complete"]:
            self.assertTrue(evidence["default_motion_passed"])
            self.assertTrue(evidence["reduced_motion_passed"])
            self.assertTrue(evidence["browser_performance_verified"])
            self.assertGreaterEqual(evidence["passing_report_count"], 2)
        self.assertTrue(packet["policy"]["motion_browser_qa_evidence_is_local_ignored_artifact_summary"])
        self.assertTrue(packet["policy"]["motion_browser_qa_evidence_is_not_production_completion"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])

    def test_run_light_endpoint_writes_factor_cache(self):
        self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "timestamp": "2026-06-10T09:30:00",
                "moneyflow_packet": {"status": "ready", "ticker": "002008.SZ", "main_net_yi": 1.2},
                "strategy_packet": {"status": "ready", "action": "wait"},
                "decision_packet": {"status": "ready"},
                "quant_packet": {"status": "ready"},
            }
        )
        created = self.client.post("/api/factor-quant/run-light", json={"ts_code": "002008.SZ", "token": "DROP"}).json()
        self.assertTrue(created["ok"])
        task = created["data"]["task"]
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "factor_light_completed_from_local_cache")
        self.assertEqual(task["call_ledger"][0]["call_status"], "cache_read")
        self.assertEqual(created["call_ledger"][0]["call_status"], "cache_read")
        self.assertIn("light mode 仅读取本地 cache", created["warnings"][0])
        self.assertIn("local_parquet_factor_values", {item.get("api") for item in task["call_ledger"]})
        self.assertNotIn("token", task["payload_safe"])

        factor = self.client.get("/api/factor-quant/cache").json()
        self.assertTrue(factor["ok"])
        self.assertEqual(factor["data"]["mode"], "light")
        self.assertEqual(factor["data"]["cache_source"], "sqlite_meta")
        self.assertFalse(factor["data"]["external_calls_triggered"])
        self.assertEqual(factor["call_ledger"][0]["api"], "local_factor_quant_cache")
        self.assertEqual(factor["call_ledger"][0]["call_status"], "cache_read")
        self.assertFalse(factor["call_ledger"][0]["external"])
        self.assertIn("GET /api/factor-quant/cache", factor["warnings"][0])
        self.assertIn("local_parquet_factor_values", {item.get("api") for item in factor["call_ledger"]})
        self.assertIn("local_factor_test_storage_query_consumption", {item.get("api") for item in factor["call_ledger"]})
        self.assertIn("local_factor_test_local_dataset_sample_evidence", {item.get("api") for item in factor["call_ledger"]})
        self.assertEqual(factor["data"]["factor_values_storage"]["dataset"], "factor_values")
        self.assertFalse(factor["data"]["governance"]["allow_core_action"])
        storage_query = factor["data"]["factor_tests"]["storage_query_consumption"]
        self.assertEqual(storage_query["schema_version"], "factor_test_storage_query_consumption.v1")
        self.assertEqual(storage_query["dataset"], "factor_values")
        self.assertEqual(storage_query["source_endpoint"], "GET /api/storage/factor-values")
        self.assertEqual(storage_query["query_result_contract_schema_version"], "duckdb_query_result_contract.v1")
        self.assertTrue(storage_query["query_result_contract_consumed"])
        self.assertTrue(storage_query["typed_projection_consumed"])
        self.assertTrue(storage_query["cursor_pagination_consumed"])
        self.assertFalse(storage_query["metrics_computed_from_storage_query"])
        self.assertFalse(storage_query["storage_query_enters_strategy_action"])
        self.assertFalse(storage_query["full_market_validation_done"])
        self.assertFalse(storage_query["real_small_pool_validation_done"])
        self.assertFalse(storage_query["external_calls_triggered"])
        self.assertFalse(storage_query["tushare_called"])
        self.assertFalse(storage_query["deepseek_called"])
        self.assertFalse(storage_query["github_called"])
        self.assertTrue(storage_query["does_not_execute_trades"])
        self.assertTrue(storage_query["does_not_modify_strategy_action"])
        self.assertEqual(storage_query["call_ledger"][0]["api"], "local_factor_test_storage_query_consumption")
        self.assert_local_ledger_boundary(storage_query["call_ledger"][0])
        local_dataset_sample = factor["data"]["factor_tests"]["local_dataset_sample_evidence"]
        self.assertEqual(local_dataset_sample["schema_version"], "factor_test_local_dataset_sample_evidence.v1")
        self.assertEqual(local_dataset_sample["scope"], "local_parquet_sample_sufficiency_audit_not_metric_validation")
        self.assertIn(
            local_dataset_sample["status"],
            {"local_dataset_sample_missing", "local_dataset_sample_blocked_not_enough_data"},
        )
        self.assertFalse(local_dataset_sample["metrics_computed_from_local_dataset"])
        self.assertFalse(local_dataset_sample["storage_query_rows_used_as_metrics"])
        self.assertFalse(local_dataset_sample["real_small_pool_validation_done"])
        self.assertFalse(local_dataset_sample["provider_backed_small_pool_validation_done"])
        self.assertFalse(local_dataset_sample["full_market_validation_done"])
        self.assertFalse(local_dataset_sample["production_factor_test_validation_complete"])
        self.assertFalse(local_dataset_sample["external_calls_triggered"])
        self.assertFalse(local_dataset_sample["tushare_called"])
        self.assertFalse(local_dataset_sample["deepseek_called"])
        self.assertFalse(local_dataset_sample["github_called"])
        self.assertTrue(local_dataset_sample["does_not_execute_trades"])
        self.assertTrue(local_dataset_sample["does_not_modify_strategy_action"])
        self.assertEqual(local_dataset_sample["call_ledger"][0]["api"], "local_factor_test_local_dataset_sample_evidence")
        self.assert_local_ledger_boundary(local_dataset_sample["call_ledger"][0])
        sample_criteria = {row["criterion"] for row in factor["data"]["factor_tests"]["local_dataset_sample_evidence_rows"]}
        self.assertIn("factor_values_dataset_present", sample_criteria)
        self.assertIn("forward_return_sample", sample_criteria)
        self.assertIn("provider_backed_sample", sample_criteria)
        self.assertIn("trade_action_isolation", sample_criteria)
        small_pool = factor["data"]["factor_tests"]["small_pool_acceptance"]
        self.assertEqual(small_pool["schema_version"], "factor_test_small_pool_acceptance.v1")
        self.assertEqual(small_pool["status"], "local_small_pool_acceptance_blocked")
        self.assertFalse(small_pool["local_light_observation_acceptance_done"])
        self.assertFalse(small_pool["storage_query_rows_used_as_metrics"])
        self.assertFalse(small_pool["real_small_pool_validation_done"])
        self.assertFalse(small_pool["full_market_validation_done"])
        self.assertFalse(small_pool["external_calls_triggered"])
        self.assertEqual(factor["data"]["factor_tests"]["small_pool_acceptance_rows"][0]["criterion"], "local_light_observations_present")
        production_validation = factor["data"]["factor_tests"]["production_validation_qa_contract"]
        self.assertEqual(production_validation["schema_version"], "factor_test_production_validation_qa_contract.v1")
        self.assertEqual(
            production_validation["status"],
            "production_validation_qa_contract_ready_provider_execution_pending",
        )
        self.assertEqual(
            production_validation["scope"],
            "local_factor_test_validation_contract_not_provider_backed_execution",
        )
        self.assertFalse(production_validation["provider_backed_small_pool_validation_done"])
        self.assertFalse(production_validation["full_market_validation_done"])
        self.assertFalse(production_validation["production_factor_test_validation_complete"])
        self.assertFalse(production_validation["storage_query_rows_used_as_metrics"])
        self.assertFalse(production_validation["external_calls_triggered"])
        self.assertFalse(production_validation["tushare_called"])
        self.assertFalse(production_validation["deepseek_called"])
        self.assertFalse(production_validation["github_called"])
        self.assertTrue(production_validation["does_not_execute_trades"])
        self.assertTrue(production_validation["does_not_modify_strategy_action"])
        self.assertTrue(production_validation["does_not_modify_core_action"])
        self.assertTrue(production_validation["does_not_enter_evidence_effects"])
        self.assertTrue(production_validation["does_not_enter_next_session_projection"])
        self.assertGreater(production_validation["pending_criterion_count"], 0)
        validation_criteria = {row["criterion"] for row in factor["data"]["factor_tests"]["production_validation_qa_rows"]}
        self.assertIn("provider_backed_small_pool_sample", validation_criteria)
        self.assertIn("multi_horizon_forward_returns", validation_criteria)
        self.assertIn("rolling_window_ic_icir", validation_criteria)
        self.assertIn("transaction_cost_assumptions", validation_criteria)
        self.assertIn("neutralization_stability", validation_criteria)
        self.assertIn("trade_action_isolation", validation_criteria)
        self.assertIn(
            "local_factor_test_production_validation_qa_contract",
            {item.get("api") for item in factor["call_ledger"]},
        )
        self.assertEqual(factor["data"]["factor_tests"]["acceptance_contract"]["storage_query_contract_consumed"], True)
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["storage_query_metrics_computed"])
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["storage_query_enters_strategy_action"])
        self.assertTrue(factor["data"]["factor_tests"]["acceptance_contract"]["local_dataset_sample_evidence_ready"])
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["local_dataset_sample_sufficiency_done"])
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["local_dataset_sample_metrics_computed"])
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["local_dataset_rows_used_as_metrics"])
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["local_light_observation_acceptance_done"])
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["storage_query_rows_used_as_metrics"])
        self.assertTrue(factor["data"]["factor_tests"]["acceptance_contract"]["production_validation_qa_contract_ready"])
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["production_factor_test_validation_complete"])
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["provider_backed_small_pool_validation_done"])
        self.assertFalse(factor["data"]["factor_tests"]["acceptance_contract"]["full_market_validation_done"])
        self.assertEqual(factor["data"]["factor_tests"]["storage_query_consumption_rows"][0]["dataset"], "factor_values")

    def test_factor_universe_research_plan_endpoint_is_local_read_plan(self):
        self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        created = self.client.post(
            "/api/factor-quant/universe-research-plan",
            json={"universe_mode": "full_pool", "universe": ["002008.SZ", "300750.SZ"], "token": "DROP"},
        ).json()

        self.assertTrue(created["ok"])
        task = created["data"]["task"]
        self.assertEqual(task["task_type"], "run_factor_universe_research_plan")
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "factor_universe_research_plan_ready")
        self.assertEqual(task["payload_safe"]["universe_mode"], "full_pool")
        self.assertEqual(task["payload_safe"]["universe_size"], 2)
        self.assertNotIn("token", task["payload_safe"])
        self.assertNotIn("DROP", json.dumps(created, ensure_ascii=False))
        self.assertEqual(task["call_ledger"][0]["api"], "local_factor_universe_research_read_plan")
        self.assertEqual(task["call_ledger"][0]["call_status"], "read_plan_ready")
        self.assert_local_ledger_boundary(task["call_ledger"][0])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])

        factor = self.client.get("/api/factor-quant/cache").json()
        self.assertTrue(factor["ok"])
        packet = factor["data"]
        plan = packet["universe_research_task_plan"]
        self.assertEqual(plan["schema_version"], "factor_universe_research_read_plan.v1")
        self.assertEqual(plan["status"], "read_plan_ready")
        self.assertEqual(plan["requested_universe_mode"], "full_pool")
        self.assertEqual(plan["universe_size"], 2)
        self.assertTrue(plan["worker_task_consumption_plan_ready"])
        self.assertFalse(plan["large_universe_pipeline_done"])
        self.assertFalse(plan["full_pool_validation_done"])
        self.assertFalse(plan["metrics_computed"])
        self.assertFalse(plan["cross_sectional_rank_zscore_done"])
        self.assertFalse(plan["neutralization_done"])
        self.assertFalse(plan["page_render_starts_full_pool"])
        self.assertFalse(plan["frontend_computes_rank_zscore"])
        self.assertFalse(plan["partial_pool_is_full_market_proof"])
        self.assertFalse(plan["external_calls_triggered"])
        self.assertFalse(plan["tushare_called"])
        self.assertFalse(plan["deepseek_called"])
        self.assertFalse(plan["github_called"])
        self.assertTrue(plan["does_not_execute_trades"])
        self.assertTrue(plan["does_not_modify_strategy_action"])
        rows_by_dataset = {row["dataset"]: row for row in packet["universe_research_task_plan_rows"]}
        self.assertEqual(set(rows_by_dataset), {"factor_values", "daily", "daily_basic", "moneyflow", "trade_cal"})
        for row in rows_by_dataset.values():
            self.assertEqual(row["query_result_contract_schema_version"], "duckdb_query_result_contract.v1")
            self.assertFalse(row["row_payload_exposed_to_factor_research"])
            self.assertFalse(row["metrics_computed_from_storage_query"])
            self.assertFalse(row["full_pool_validation_done"])
            self.assertFalse(row["large_universe_pipeline_done"])
            self.assertFalse(row["external_calls_triggered"])
            self.assertFalse(row["tushare_called"])
            self.assertFalse(row["deepseek_called"])
            self.assertFalse(row["github_called"])
            self.assertTrue(row["does_not_execute_trades"])
            self.assertTrue(row["does_not_modify_strategy_action"])
        contract = packet["universe_research_contract"]
        self.assertTrue(contract["storage_query_contract_consumed"])
        self.assertTrue(contract["worker_task_consumption_plan_ready"])
        self.assertFalse(contract["large_universe_pipeline_done"])
        self.assertFalse(contract["full_pool_validation_done"])
        self.assertFalse(contract["page_render_starts_full_pool"])
        self.assertFalse(contract["frontend_computes_rank_zscore"])
        self.assertFalse(contract["partial_pool_is_full_market_proof"])
        self.assertEqual(contract["execution_readiness_status"], "read_plan_ready_execution_pending")
        self.assertFalse(contract["production_factor_universe_complete"])
        audit = packet["universe_execution_readiness_audit"]
        self.assertEqual(audit["schema_version"], "factor_universe_execution_readiness_audit.v1")
        self.assertEqual(audit["status"], "read_plan_ready_execution_pending")
        self.assertEqual(audit["requested_universe_mode"], "full_pool")
        self.assertTrue(audit["read_plan_ready"])
        self.assertTrue(audit["storage_query_contract_consumed"])
        self.assertTrue(audit["worker_task_consumption_plan_ready"])
        self.assertFalse(audit["large_universe_pipeline_done"])
        self.assertFalse(audit["full_pool_validation_done"])
        self.assertFalse(audit["cross_sectional_rank_zscore_done"])
        self.assertFalse(audit["neutralization_done"])
        self.assertFalse(audit["production_factor_universe_complete"])
        self.assertFalse(audit["partial_pool_is_full_market_proof"])
        self.assertFalse(audit["page_render_starts_full_pool"])
        self.assertFalse(audit["frontend_computes_rank_zscore"])
        self.assertFalse(audit["external_calls_triggered"])
        self.assertFalse(audit["tushare_called"])
        self.assertFalse(audit["deepseek_called"])
        self.assertFalse(audit["github_called"])
        self.assertTrue(audit["does_not_execute_trades"])
        self.assertTrue(audit["does_not_modify_strategy_action"])
        self.assertGreaterEqual(audit["production_blocker_count"], 4)
        readiness_rows = {row["criterion"]: row for row in packet["universe_execution_readiness_rows"]}
        self.assertEqual(readiness_rows["button_gated_read_plan"]["status"], "passed")
        self.assertEqual(readiness_rows["storage_query_contract_consumed"]["status"], "passed")
        self.assertEqual(readiness_rows["worker_batch_execution_pending"]["status"], "blocked")
        self.assertEqual(readiness_rows["cross_sectional_rank_zscore_pending"]["status"], "blocked")
        self.assertEqual(readiness_rows["neutralization_pending"]["status"], "blocked")
        self.assertEqual(readiness_rows["full_pool_validation_pending"]["status"], "blocked")
        self.assertEqual(readiness_rows["frontend_read_only_boundary"]["status"], "passed")
        self.assertEqual(readiness_rows["research_trade_boundary"]["status"], "passed")
        rank_zscore = packet["universe_local_rank_zscore_dry_run"]
        self.assertEqual(rank_zscore["schema_version"], "factor_universe_local_rank_zscore_dry_run.v1")
        self.assertEqual(rank_zscore["scope"], "local_factor_values_rank_zscore_dry_run_not_full_pool_validation")
        self.assertIn(
            rank_zscore["status"],
            {"local_rank_zscore_dry_run_blocked_not_enough_data", "local_rank_zscore_dry_run_ready_research_only"},
        )
        self.assertTrue(rank_zscore["metrics_are_research_only"])
        self.assertFalse(rank_zscore["cross_sectional_rank_zscore_done"])
        self.assertFalse(rank_zscore["neutralization_done"])
        self.assertFalse(rank_zscore["large_universe_pipeline_done"])
        self.assertFalse(rank_zscore["full_pool_validation_done"])
        self.assertFalse(rank_zscore["production_factor_universe_complete"])
        self.assertFalse(rank_zscore["page_render_starts_full_pool"])
        self.assertFalse(rank_zscore["frontend_computes_rank_zscore"])
        self.assertFalse(rank_zscore["partial_pool_is_full_market_proof"])
        self.assertFalse(rank_zscore["external_calls_triggered"])
        self.assertFalse(rank_zscore["tushare_called"])
        self.assertFalse(rank_zscore["deepseek_called"])
        self.assertFalse(rank_zscore["github_called"])
        self.assertTrue(rank_zscore["does_not_execute_trades"])
        self.assertTrue(rank_zscore["does_not_modify_strategy_action"])
        rank_rows = {row["criterion"]: row for row in packet["universe_local_rank_zscore_rows"]}
        self.assertIn("usable_cross_section_present", rank_rows)
        self.assertIn("production_flags_stay_false", rank_rows)
        self.assertIn("frontend_does_not_compute_rank_zscore", rank_rows)
        self.assertIn("trade_action_isolation", rank_rows)
        self.assertIn("local_factor_universe_rank_zscore_dry_run", {item.get("api") for item in packet["call_ledger"]})
        self.assertIn("local_factor_universe_research_read_plan", {item.get("api") for item in packet["call_ledger"]})
        self.assertNotIn("DROP", json.dumps(factor, ensure_ascii=False))

    def test_deepseek_explain_endpoint_is_guarded_and_sanitized(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)

        created = self.client.post(
            "/api/factor-quant/deepseek-explain",
            json={
                "provided_explanation": {
                    "summary": "整理摘要",
                    "support_notes": ["支持说明"],
                    "price": 100,
                    "strategy_action": "buy",
                    "factor_values": [1, 2],
                }
            },
        ).json()
        self.assertTrue(created["ok"])
        task = created["data"]["task"]
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["call_ledger"][0]["call_status"], "provided_payload_sanitized")
        self.assertEqual(created["call_ledger"][0]["call_status"], "provided_payload_sanitized")
        self.assertIn("DeepSeek 因子解释任务本轮不调用模型", created["warnings"][0])
        self.assertEqual(task["payload_safe"], {"provided_explanation_payload": True})
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])

        factor = self.client.get("/api/factor-quant/cache").json()
        self.assertTrue(factor["ok"])
        explanation = factor["data"]["deepseek_explanation"]
        json_audit = factor["data"]["deepseek_json_stability_audit"]
        json_audit_rows = {row["criterion"]: row for row in factor["data"]["deepseek_json_stability_rows"]}
        response_format_review = factor["data"]["deepseek_response_format_review_contract"]
        response_format_rows = {row["criterion"]: row for row in factor["data"]["deepseek_response_format_review_rows"]}
        self.assertFalse(factor["data"]["deepseek_called"])
        self.assertEqual(explanation["payload"]["summary"], "整理摘要")
        self.assertIn("price", explanation["ignored_keys"])
        self.assertIn("strategy_action", explanation["ignored_keys"])
        self.assertIn("factor_values", explanation["ignored_keys"])
        self.assertEqual(json_audit["status"], "manual_ready_production_blocked")
        self.assertEqual(json_audit["scope"], "local_sanitizer_prompt_contract_not_model_call")
        self.assertTrue(json_audit["manual_explanation_ready"])
        self.assertFalse(json_audit["production_ready"])
        self.assertFalse(json_audit["auto_after_task_production_ready"])
        self.assertEqual(json_audit["required_json_success_rate"], 0.9)
        self.assertEqual(json_audit["last_known_mini_benchmark_success_rate"], 0.75)
        self.assertFalse(json_audit["larger_benchmark_done"])
        self.assertFalse(json_audit["response_format_enforced"])
        self.assertEqual(json_audit["model_call_status"], "not_called")
        self.assertFalse(json_audit["deepseek_called"])
        self.assertIn("json_success_rate_threshold", json_audit["production_blockers"])
        self.assertIn("larger_benchmark_done", json_audit["production_blockers"])
        self.assertIn("response_format_enforced", json_audit["production_blockers"])
        self.assertTrue(json_audit_rows["allowed_top_level_schema"]["passed"])
        self.assertTrue(json_audit_rows["auto_after_task_default_off"]["passed"])
        self.assertFalse(json_audit_rows["json_success_rate_threshold"]["passed"])
        self.assertFalse(json_audit_rows["response_format_enforced"]["passed"])
        self.assertEqual(
            response_format_review["schema_version"],
            "factor_deepseek_response_format_review_contract.v1",
        )
        self.assertEqual(response_format_review["status"], "response_format_review_ready_provider_enforcement_pending")
        self.assertEqual(response_format_review["scope"], "local_response_format_review_no_model_call")
        self.assertEqual(
            response_format_review["review_policy"],
            "manual_explanation_only_until_response_format_retry_and_benchmark_pass",
        )
        self.assertTrue(response_format_review["local_response_format_review_ready"])
        self.assertTrue(response_format_review["manual_explanation_ready"])
        self.assertFalse(response_format_review["production_ready"])
        self.assertFalse(response_format_review["provider_response_format_enforced"])
        self.assertFalse(response_format_review["retry_repair_policy_ready"])
        self.assertFalse(response_format_review["larger_benchmark_done"])
        self.assertFalse(response_format_review["auto_after_task_production_ready"])
        self.assertEqual(response_format_review["model_call_status"], "not_called")
        self.assertTrue(response_format_review["prompt_only_json_instruction"])
        self.assertFalse(response_format_review["parse_failed"])
        self.assertFalse(response_format_review["deepseek_called"])
        self.assertFalse(response_format_review["external_calls_triggered"])
        self.assertFalse(response_format_review["contains_secret"])
        self.assertTrue(response_format_review["does_not_override_numeric_values"])
        self.assertTrue(response_format_review["does_not_output_strategy_action"])
        self.assertEqual(
            set(response_format_review["allowed_top_level_keys"]),
            {"summary", "support_notes", "suppress_notes", "conflict_notes", "missing_data_notes", "discipline_notes"},
        )
        self.assertIn("provider_response_format_enforced", response_format_review["production_blockers"])
        self.assertIn("retry_repair_policy_ready", response_format_review["production_blockers"])
        self.assertIn("larger_benchmark_required", response_format_review["production_blockers"])
        self.assertTrue(response_format_rows["json_object_instruction_present"]["passed"])
        self.assertTrue(response_format_rows["allowed_top_level_keys_exact"]["passed"])
        self.assertFalse(response_format_rows["provider_response_format_enforced"]["passed"])
        self.assertFalse(response_format_rows["retry_repair_policy_ready"]["passed"])
        self.assertTrue(response_format_rows["cache_render_no_model_call"]["passed"])
        self.assertEqual(
            factor["data"]["deepseek_explain_governance"]["json_stability_audit_status"],
            "manual_ready_production_blocked",
        )
        self.assertEqual(
            factor["data"]["deepseek_explain_governance"]["response_format_review_status"],
            "response_format_review_ready_provider_enforcement_pending",
        )
        self.assertFalse(factor["data"]["deepseek_explain_governance"]["response_format_production_ready"])
        self.assertFalse(factor["data"]["deepseek_explain_governance"]["response_format_retry_repair_ready"])
        self.assertFalse(factor["data"]["governance"]["allow_core_action"])
        self.assertTrue(factor["data"]["next_session_bridge"]["does_not_modify_action"])


if __name__ == "__main__":
    unittest.main()
