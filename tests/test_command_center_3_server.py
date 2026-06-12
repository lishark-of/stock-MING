from __future__ import annotations

import ast
import importlib.util
import json
import os
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
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "meta.sqlite"
        packet_service.SQLITE_META_PATH = db_path
        factor_service.SQLITE_META_PATH = db_path
        next_session_service.SQLITE_META_PATH = db_path
        task_service.SQLITE_META_PATH = db_path
        tushare_task_service.SQLITE_META_PATH = db_path
        storage_service.SQLITE_META_PATH = db_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SQLITE_META_PATH", original_packet_path)
        self.addCleanup(setattr, factor_service, "SQLITE_META_PATH", original_factor_path)
        self.addCleanup(setattr, next_session_service, "SQLITE_META_PATH", original_next_session_path)
        self.addCleanup(setattr, task_service, "SQLITE_META_PATH", original_task_path)
        self.addCleanup(setattr, tushare_task_service, "SQLITE_META_PATH", original_tushare_task_path)
        self.addCleanup(setattr, storage_service, "SQLITE_META_PATH", original_storage_path)
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
        self.assertTrue(desktop["api_base_info"]["is_localhost"])
        self.assertEqual(desktop["api_base_info"]["expected_health_endpoint"], "http://127.0.0.1:8710/health")
        self.assertTrue(desktop["api_base_info"]["frontend_uses_fastapi_only"])
        self.assertTrue(desktop["api_base_info"]["does_not_autostart_backend"])
        self.assertEqual(desktop["runtime"]["api_health_endpoint"], "http://127.0.0.1:8710/health")
        self.assertFalse(desktop["runtime"]["backend_autostart_configured"])
        self.assertEqual([row["command"] for row in desktop["dev_launch_plan"][:3]], [
            "scripts/dev_server.sh",
            "cd desktop && npm run dev",
            "cd desktop && npm run tauri dev",
        ])
        self.assertTrue(all(row["manual"] for row in desktop["dev_launch_plan"]))
        self.assertTrue(all(row["external_calls_triggered"] is False for row in desktop["dev_launch_plan"]))
        self.assertTrue(all(row["loads_token_or_key"] is False for row in desktop["dev_launch_plan"]))
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
        self.assertEqual(chart["chart_summary"]["renderer"], "ECharts")
        self.assertFalse(chart["chart_summary"]["has_drawable_data"])
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
        self.assertEqual(implementation["state_counts"]["local_pipeline_enabled"], 1)
        self.assertEqual(implementation["state_counts"]["future_button_gated"], 5)
        self.assertEqual(overview["dataset_implementation_state_counts"], implementation["state_counts"])
        self.assertEqual(overview["dataset_parquet_status_counts"], implementation["parquet_status_counts"])
        rows_by_dataset = {row["dataset"]: row for row in implementation["dataset_rows"]}
        self.assertEqual(rows_by_dataset["factor_values"]["implementation_state"], "local_pipeline_enabled")
        self.assertEqual(rows_by_dataset["daily"]["implementation_state"], "future_button_gated")
        self.assertEqual(rows_by_dataset["trade_cal"]["implementation_state"], "future_button_gated")
        self.assertTrue(rows_by_dataset["daily"]["tushare_capable"])
        self.assertTrue(rows_by_dataset["trade_cal"]["tushare_capable"])
        self.assertFalse(rows_by_dataset["factor_values"]["tushare_capable"])
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

    def test_storage_dataset_catalog_is_independent_cache_only_endpoint(self):
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
        self.assertEqual(catalog["call_ledger"][0]["api"], "local_storage_dataset_catalog_cache")
        self.assertEqual(catalog["call_ledger"][0]["endpoint"], "GET /api/storage/catalog")
        self.assertEqual(catalog["call_ledger"][0]["row_count"], 6)
        self.assertFalse(catalog["call_ledger"][0]["external"])
        self.assertIn("GET /api/storage/catalog", catalog["warnings"][0])

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
        self.assertNotIn("authorization", packet["candidates"][0])
        self.assertNotIn("api_key", packet["radar_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_scan_market"])
        self.assertTrue(packet["policy"]["candidate_is_not_buy_instruction"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_candidate_radar_cache")
        json.dumps(packet, ensure_ascii=False)

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
        self.assertEqual(persisted["api_validation_matrix_policy"]["call_ledger_required_fields"][0], "api")

    def test_tushare_refresh_task_validates_trade_calendar_and_extended_apis_without_false_parquet_claims(self):
        db_path = self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)

        class ExtendedFakeTushareAdapter:
            def get_trade_cal(self, **params):
                return {"ok": True, "data": [{"cal_date": "20260610", "is_open": 1}], "error": ""}

            def get_margin_detail(self, **params):
                return {"ok": True, "data": [], "error": ""}

            def get_limit_cpt_list(self, **params):
                return {"ok": False, "data": None, "error": "Traceback token=SHOULD_DROP"}

        task = tushare_task_service.run_tushare_refresh_task(
            {
                "ts_code": "002008.SZ",
                "start_date": "20260601",
                "end_date": "20260610",
                "apis": ["trade_cal", "margin_detail", "limit_cpt_list"],
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
        self.assertEqual(ledger_by_api["limit_cpt_list"]["call_status"], "failed")
        self.assertEqual(ledger_by_api["limit_cpt_list"]["error_message_safe"], "tushare_error_redacted_safe")

        from storage.sqlite_meta import SQLiteMetaStore

        persisted = SQLiteMetaStore(db_path).read_packet("command_center_tushare_refresh_packet")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["status"], "success")
        self.assertEqual(persisted["success_count"], 2)
        self.assertEqual(persisted["failed_count"], 1)
        self.assertEqual(persisted["api_validation_summary"]["selected_api_count"], 3)
        self.assertEqual(persisted["api_validation_summary"]["validated_success_count"], 1)
        self.assertEqual(persisted["api_validation_summary"]["validated_empty_count"], 1)
        self.assertEqual(persisted["api_validation_summary"]["validated_failed_count"], 1)
        validation_by_api = {row["api"]: row for row in persisted["api_validation_rows"]}
        self.assertEqual(validation_by_api["trade_cal"]["group"], "calendar")
        self.assertEqual(validation_by_api["trade_cal"]["validation_status"], "validated_success")
        self.assertEqual(validation_by_api["trade_cal"]["validation_scope"], "task_call_result")
        self.assertTrue(validation_by_api["trade_cal"]["parquet_enabled"])
        self.assertEqual(validation_by_api["margin_detail"]["group"], "extended")
        self.assertEqual(validation_by_api["margin_detail"]["validation_status"], "validated_empty")
        self.assertEqual(validation_by_api["margin_detail"]["validation_scope"], "task_call_result")
        self.assertFalse(validation_by_api["margin_detail"]["parquet_enabled"])
        self.assertEqual(validation_by_api["limit_cpt_list"]["validation_status"], "validated_failed")
        self.assertEqual(validation_by_api["limit_cpt_list"]["validation_scope"], "task_call_result")
        self.assertEqual(validation_by_api["daily"]["validation_status"], "not_requested")
        self.assertEqual(validation_by_api["daily"]["validation_scope"], "capability_matrix_only")
        self.assertEqual(persisted["api_validation_summary"]["task_call_result_count"], 3)
        self.assertIn("daily", persisted["api_validation_matrix_policy"]["matrix_only_apis"])

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
        self.assertEqual(catalog["task_count"], 7)
        self.assertTrue(catalog["policy"]["get_catalog_cache_only"])
        self.assertTrue(catalog["policy"]["all_tasks_button_gated"])
        self.assertTrue(catalog["policy"]["all_known_post_routes_button_gated"])
        self.assertTrue(catalog["policy"]["call_ledger_required_for_all"])
        self.assertTrue(catalog["policy"]["call_ledger_required_for_all_known_post_routes"])
        self.assertTrue(catalog["policy"]["supports_local_task_cancel"])
        self.assertFalse(catalog["policy"]["cancel_task_external_calls"])
        self.assertTrue(catalog["policy"]["cancel_route_in_lifecycle_catalog"])
        self.assertFalse(catalog["external_calls_triggered"])
        self.assertFalse(catalog["tushare_called"])
        self.assertFalse(catalog["deepseek_called"])
        self.assertFalse(catalog["github_called"])
        self.assertEqual(catalog["call_ledger"][0]["api"], "local_task_catalog_cache")
        self.assertEqual(catalog["call_ledger"][0]["row_count"], 7)
        self.assertEqual(catalog["call_ledger"][0]["call_status"], "cache_read")
        self.assert_local_ledger_boundary(catalog["call_ledger"][0])
        self.assertIn("GET /api/tasks/catalog", catalog["warnings"][0])
        self.assertTrue(catalog["policy"]["does_not_execute_trades"])
        self.assertTrue(catalog["policy"]["does_not_modify_strategy_action"])
        self.assertEqual(set(catalog["external_sources"]), {"deepseek", "github", "tushare"})
        by_type = {item["task_type"]: item for item in catalog["tasks"]}
        route_coverage = catalog["route_coverage"]
        implementation_status = catalog["implementation_status"]
        self.assertEqual(route_coverage["known_post_route_count"], 8)
        self.assertEqual(route_coverage["task_creation_route_count"], 7)
        self.assertEqual(route_coverage["local_lifecycle_route_count"], 1)
        self.assertEqual(route_coverage["uncovered_post_routes"], [])
        self.assertTrue(route_coverage["all_known_post_routes_button_gated"])
        self.assertTrue(route_coverage["call_ledger_required_for_all_known_post_routes"])
        self.assertFalse(route_coverage["cancel_routes_external_calls"])
        self.assertEqual(implementation_status["status"], "partial_migration")
        self.assertEqual(implementation_status["task_count"], 7)
        self.assertEqual(implementation_status["stub_task_count"], 2)
        self.assertEqual(implementation_status["local_pipeline_task_count"], 4)
        self.assertEqual(implementation_status["guarded_local_task_count"], 1)
        self.assertEqual(implementation_status["implemented_local_task_count"], 5)
        self.assertEqual(implementation_status["external_capable_task_count"], 5)
        self.assertEqual(
            set(implementation_status["stub_task_types"]),
            {"run_chokepoint_scan", "probe_serenity_github"},
        )
        self.assertEqual(
            set(implementation_status["local_pipeline_task_types"]),
            {"refresh_tushare_facts", "refresh_factor_data", "run_factor_light", "build_next_session_projection"},
        )
        self.assertEqual(implementation_status["guarded_local_task_types"], ["run_deepseek_factor_explanation"])
        self.assertEqual(
            set(implementation_status["implemented_local_task_types"]),
            {"refresh_tushare_facts", "refresh_factor_data", "run_factor_light", "build_next_session_projection", "run_deepseek_factor_explanation"},
        )
        self.assertTrue(implementation_status["all_external_capable_tasks_are_button_gated"])
        self.assertTrue(implementation_status["all_external_capable_tasks_require_call_ledger"])
        self.assertIn("local_fallback_stub", implementation_status["backend_counts"])
        self.assertTrue(catalog["policy"]["implementation_status_is_read_only"])
        self.assertTrue(catalog["policy"]["stub_tasks_must_not_be_reported_as_complete"])
        self.assertIn("误读为完整生产迁移", implementation_status["note"])
        self.assertIn("POST /api/tasks/{task_id}/cancel", route_coverage["known_post_routes"])
        self.assertEqual(catalog["task_lifecycle_routes"][0]["route"], "POST /api/tasks/{task_id}/cancel")
        self.assertEqual(catalog["task_lifecycle_routes"][0]["external_call_policy"], "local_cancel_no_external_call")
        self.assertEqual(by_type["refresh_tushare_facts"]["route"], "POST /api/tasks/refresh-tushare-facts")
        self.assertEqual(by_type["refresh_tushare_facts"]["current_backend"], "button_gated_tushare_pipeline")
        self.assertIn("tushare", by_type["refresh_tushare_facts"]["possible_external_sources"])
        self.assertEqual(by_type["refresh_tushare_facts"]["default_core_apis"], ["daily", "daily_basic", "moneyflow"])
        self.assertEqual(by_type["refresh_tushare_facts"]["calendar_apis"], ["trade_cal"])
        self.assertIn("limit_cpt_list", by_type["refresh_tushare_facts"]["optional_extended_apis"])
        self.assertEqual(by_type["refresh_tushare_facts"]["parquet_enabled_apis"], ["daily", "daily_basic", "moneyflow", "trade_cal"])
        self.assertIn("unselected APIs are capability matrix only", by_type["refresh_tushare_facts"]["api_validation_matrix_policy"])
        self.assertFalse(by_type["refresh_tushare_facts"]["cache_get_external_calls"])
        self.assertEqual(by_type["refresh_factor_data"]["route"], "POST /api/factor-quant/refresh-data")
        self.assertEqual(by_type["refresh_factor_data"]["current_backend"], "button_gated_tushare_pipeline")
        self.assertIn("tushare", by_type["refresh_factor_data"]["possible_external_sources"])
        self.assertEqual(by_type["refresh_factor_data"]["calendar_apis"], ["trade_cal"])
        self.assertEqual(by_type["refresh_factor_data"]["parquet_enabled_apis"], ["daily", "daily_basic", "moneyflow", "trade_cal"])
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
        self.assertEqual(by_type["build_next_session_projection"]["current_backend"], "local_cache_pipeline")
        self.assertEqual(by_type["build_next_session_projection"]["possible_external_sources"], [])

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
        self.assertIn("POST /api/factor-quant/deepseek-explain", discovered_routes)

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
        self.assertEqual(packet["task_catalog_summary"]["local_pipeline_task_count"], 4)
        self.assertEqual(packet["task_catalog_summary"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["task_catalog_summary"]["implemented_local_task_count"], 5)
        self.assertEqual(packet["task_implementation_status"]["status"], "partial_migration")
        self.assertEqual(packet["task_implementation_status"]["stub_task_count"], 2)
        self.assertEqual(packet["task_implementation_status"]["local_pipeline_task_count"], 4)
        self.assertEqual(packet["task_implementation_status"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["task_implementation_status"]["implemented_local_task_count"], 5)
        self.assertIn("refresh_tushare_facts", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("refresh_factor_data", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_factor_light", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_deepseek_factor_explanation", packet["task_implementation_status"]["guarded_local_task_types"])
        self.assertEqual(packet["task_status_summary"]["packet_key"], "command_center_3_task_status_index")
        self.assertIn("status_counts", packet["task_status_summary"])
        self.assertIn("call_ledger_count", packet["task_status_summary"])
        self.assertIn("persistence", packet["task_status_summary"])
        self.assertIn("persistence_source_rows", packet["task_status_summary"])
        self.assertIn("memory_task_count", packet["task_status_summary"])
        self.assertIn("sqlite_task_count", packet["task_status_summary"])
        self.assertIn("deduplicated_task_count", packet["task_status_summary"])
        self.assertIn("task_persistence", packet)
        self.assertIn("task_persistence_source_rows", packet)
        self.assertIn("memory_task_count", packet["counts"])
        self.assertIn("sqlite_task_count", packet["counts"])
        self.assertIn("deduplicated_task_count", packet["counts"])
        self.assertEqual(packet["task_persistence"], packet["task_status_summary"]["persistence"])
        self.assertEqual(packet["task_persistence_source_rows"], packet["task_status_summary"]["persistence_source_rows"])
        self.assertFalse(packet["task_status_summary"]["external_calls_triggered"])
        self.assertTrue(packet["task_status_summary"]["does_not_execute_trades"])
        self.assertTrue(packet["task_status_summary"]["does_not_modify_strategy_action"])
        self.assertIn("task_status_count", packet["counts"])
        self.assertIn("task_status_call_ledger_count", packet["counts"])
        self.assertEqual(packet["counts"]["stub_task_count"], 2)
        self.assertEqual(packet["counts"]["local_pipeline_task_count"], 4)
        self.assertEqual(packet["counts"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["counts"]["implemented_local_task_count"], 5)
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
        self.assertEqual(packet["counts"]["local_pipeline_task_count"], 4)
        self.assertEqual(packet["counts"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["counts"]["implemented_local_task_count"], 5)
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
        self.assertEqual(packet["task_implementation_status"]["local_pipeline_task_count"], 4)
        self.assertEqual(packet["task_implementation_status"]["guarded_local_task_count"], 1)
        self.assertEqual(packet["task_implementation_status"]["implemented_local_task_count"], 5)
        self.assertIn("refresh_tushare_facts", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("refresh_factor_data", packet["task_implementation_status"]["local_pipeline_task_types"])
        self.assertIn("run_factor_light", packet["task_implementation_status"]["local_pipeline_task_types"])
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

    def test_task_status_update_supports_failed_state_without_secret_leak(self):
        self._with_meta_store()
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
        self.assertNotIn("authorization", updated["payload_safe"])
        self.assertNotIn("SHOULD_DROP", json.dumps(updated, ensure_ascii=False))
        self.assertIn("safe warning", updated["warnings"])

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
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "meta.sqlite"
        packet_service.SQLITE_META_PATH = db_path
        factor_service.SQLITE_META_PATH = db_path
        next_session_service.SQLITE_META_PATH = db_path
        task_service.SQLITE_META_PATH = db_path
        tushare_task_service.SQLITE_META_PATH = db_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SQLITE_META_PATH", original_packet_path)
        self.addCleanup(setattr, factor_service, "SQLITE_META_PATH", original_factor_path)
        self.addCleanup(setattr, next_session_service, "SQLITE_META_PATH", original_next_session_path)
        self.addCleanup(setattr, task_service, "SQLITE_META_PATH", original_task_path)
        self.addCleanup(setattr, tushare_task_service, "SQLITE_META_PATH", original_tushare_task_path)
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
        self.assertTrue(legacy["data"]["does_not_modify_strategy_action"])

        task_catalog = self.client.get("/api/tasks/catalog").json()
        self.assertTrue(task_catalog["ok"])
        self.assertEqual(task_catalog["data"]["task_count"], 7)
        self.assertIn("POST /api/tasks/refresh-tushare-facts", task_catalog["data"]["route_coverage"]["known_post_routes"])
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
            }
        )

        response = self.client.get("/api/candidate-radar/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["candidate_rows"][0]["ticker"], "002837.SZ")
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_scan_market"])
        self.assertTrue(packet["policy"]["candidate_is_not_buy_instruction"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_candidate_radar_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/candidate-radar/cache", response["warnings"][0])

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
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(response["call_ledger"][0]["api"], "local_data_health_timeline_cache")
        self.assertFalse(response["call_ledger"][0]["external"])
        self.assertIn("GET /api/data-health/cache", response["warnings"][0])

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

        cancelled = self.client.post("/api/tasks/token=SHOULD_DROP/cancel", json={"reason": "token=SHOULD_DROP"}).json()

        self.assertFalse(cancelled["ok"])
        self.assertEqual(cancelled["error"], "task_not_found")
        self.assertEqual(cancelled["call_ledger"][0]["api"], "local_task_cancel")
        self.assertEqual(cancelled["call_ledger"][0]["call_status"], "task_not_found_no_external_call")
        self.assertEqual(cancelled["call_ledger"][0]["request_params_safe"]["task_id"], "[redacted_sensitive_text]")
        self.assert_local_ledger_boundary(cancelled["call_ledger"][0])
        self.assertIn("POST /api/tasks/{task_id}/cancel", cancelled["warnings"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(cancelled, ensure_ascii=False))

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
        self.assertEqual(factor["data"]["factor_values_storage"]["dataset"], "factor_values")
        self.assertFalse(factor["data"]["governance"]["allow_core_action"])

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
        self.assertFalse(factor["data"]["deepseek_called"])
        self.assertEqual(explanation["payload"]["summary"], "整理摘要")
        self.assertIn("price", explanation["ignored_keys"])
        self.assertIn("strategy_action", explanation["ignored_keys"])
        self.assertIn("factor_values", explanation["ignored_keys"])
        self.assertFalse(factor["data"]["governance"]["allow_core_action"])
        self.assertTrue(factor["data"]["next_session_bridge"]["does_not_modify_action"])


if __name__ == "__main__":
    unittest.main()
