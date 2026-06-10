from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from server.services import factor_service, packet_service, storage_service, task_service
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
        original_task_path = task_service.SQLITE_META_PATH
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "meta.sqlite"
        packet_service.SQLITE_META_PATH = db_path
        factor_service.SQLITE_META_PATH = db_path
        task_service.SQLITE_META_PATH = db_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SQLITE_META_PATH", original_packet_path)
        self.addCleanup(setattr, factor_service, "SQLITE_META_PATH", original_factor_path)
        self.addCleanup(setattr, task_service, "SQLITE_META_PATH", original_task_path)
        return db_path

    def _with_parquet_root(self):
        original_root = storage_service.PARQUET_ROOT
        temp_dir = tempfile.TemporaryDirectory()
        storage_service.PARQUET_ROOT = Path(temp_dir.name) / "parquet"
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, storage_service, "PARQUET_ROOT", original_root)
        return storage_service.PARQUET_ROOT

    def test_cache_builders_do_not_call_external_sources(self):
        factor = packet_service.build_factor_quant_cache()
        serenity = packet_service.build_serenity_cache()
        next_session = packet_service.build_next_session_cache()

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

        self.assertEqual(next_session["packet_key"], "command_center_next_session_projection_packet")
        self.assertFalse(next_session["external_calls_triggered"])
        self.assertTrue(next_session["does_not_modify_action"])

        json.dumps({"factor": factor, "serenity": serenity, "next": next_session}, ensure_ascii=False)

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

    def test_packet_index_exposes_snapshot_keys(self):
        self._with_snapshot_cache({"moneyflow_packet": {"status": "ready"}})

        index = packet_service.list_packets()

        self.assertTrue(index["snapshot_available"])
        self.assertIn("moneyflow_packet", index["snapshot_available_keys"])
        self.assertIn("command_center_moneyflow_packet", index["snapshot_alias_keys"])
        self.assertIn("command_center_moneyflow_packet", index["available_cache_keys"])

    def test_packet_index_exposes_sqlite_packet_metadata(self):
        self._with_meta_store()
        from storage.sqlite_meta import SQLiteMetaStore

        SQLiteMetaStore(packet_service.SQLITE_META_PATH).write_packet(
            "command_center_factor_quant_hub_packet",
            {"packet_key": "command_center_factor_quant_hub_packet", "schema_version": "factor_quant_hub.v1", "mode": "light"},
        )

        index = packet_service.list_packets()

        self.assertTrue(index["sqlite_meta"]["sqlite_meta_available"])
        self.assertIn("command_center_factor_quant_hub_packet", index["persisted_packet_keys"])
        self.assertIn("command_center_factor_quant_hub_packet", index["available_cache_keys"])
        self.assertEqual(index["sqlite_meta"]["packet_metadata"][0]["schema_version"], "factor_quant_hub.v1")
        self.assertFalse(index["cache_api_policy"]["get_cache_external_calls"])

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

    def test_task_status_update_supports_failed_state_without_secret_leak(self):
        self._with_meta_store()
        task = create_task_stub("run_factor_light", payload={"authorization": "Bearer secret", "ts_code": "002008.SZ"})

        updated = update_task_status(
            task["task_id"],
            status="failed",
            progress=0.7,
            current_step="safe_failure_recorded",
            error_message_safe="mock failure",
            warning="safe warning",
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "failed")
        self.assertEqual(updated["current_step"], "safe_failure_recorded")
        self.assertEqual(updated["error_message_safe"], "mock failure")
        self.assertNotIn("authorization", updated["payload_safe"])
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

        task = factor_service.create_factor_task(
            "run_factor_light",
            payload={"ts_code": "002008.SZ", "api_key": "SHOULD_DROP"},
        )
        packet = packet_service.build_factor_quant_cache()

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "factor_light_completed_from_local_cache")
        self.assertEqual(task["call_ledger"][0]["call_status"], "cache_read")
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertFalse(task["external_calls_triggered"])

        self.assertEqual(packet["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertEqual(packet["mode"], "light")
        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_action"])
        support_keys = {item.get("factor_key") for item in packet["score"]["support_factors"]}
        suppress_keys = {item.get("factor_key") for item in packet["score"]["suppress_factors"]}
        self.assertNotIn("serenity_method_source", support_keys | suppress_keys)
        self.assertNotIn("chokepoint_method_hint", support_keys | suppress_keys)
        self.assertIn("roe_latest", {item.get("factor_key") for item in packet["score"]["missing_factors"]})

    def test_deepseek_explanation_task_prepares_prompt_without_model_call(self):
        self._with_meta_store()

        task = factor_service.create_factor_task("run_deepseek_factor_explanation", payload={"ts_code": "002008.SZ"})
        packet = packet_service.build_factor_quant_cache()

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "deepseek_prompt_ready_without_model_call")
        self.assertEqual(task["call_ledger"][0]["call_status"], "not_called")
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])
        self.assertTrue(task["does_not_execute_trades"])

        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["deepseek_model_called"])
        self.assertFalse(packet["deepseek_task_external_calls_triggered"])
        self.assertEqual(packet["deepseek_explanation"]["status"], "not_called")
        self.assertEqual(packet["deepseek_explanation"]["payload"], None)
        self.assertFalse(packet["deepseek_explanation_prompt_preview"]["enters_deepseek_prompt"])
        self.assertTrue(packet["deepseek_explanation_prompt_preview"]["would_enter_deepseek_prompt_if_user_authorizes"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_action"])

    def test_deepseek_explanation_task_sanitizes_payload_without_overwriting_values(self):
        self._with_meta_store()
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
        self.assertEqual(task["payload_safe"], {"provided_explanation_payload": True})
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertNotIn("provided_explanation", task["payload_safe"])
        self.assertNotIn("price", json.dumps(task["payload_safe"], ensure_ascii=False))
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])

        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["deepseek_model_called"])
        self.assertEqual(explanation["status"], "success")
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
        self.assertTrue(explanation["does_not_override_numeric_values"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_operation_zones"])


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
        original_task_path = task_service.SQLITE_META_PATH
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "meta.sqlite"
        packet_service.SQLITE_META_PATH = db_path
        factor_service.SQLITE_META_PATH = db_path
        task_service.SQLITE_META_PATH = db_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SQLITE_META_PATH", original_packet_path)
        self.addCleanup(setattr, factor_service, "SQLITE_META_PATH", original_factor_path)
        self.addCleanup(setattr, task_service, "SQLITE_META_PATH", original_task_path)
        return db_path

    def _with_parquet_root(self):
        original_root = storage_service.PARQUET_ROOT
        temp_dir = tempfile.TemporaryDirectory()
        storage_service.PARQUET_ROOT = Path(temp_dir.name) / "parquet"
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, storage_service, "PARQUET_ROOT", original_root)
        return storage_service.PARQUET_ROOT

    def test_health_and_cache_endpoints(self):
        health = self.client.get("/health").json()
        self.assertTrue(health["ok"])
        self.assertFalse(health["data"]["external_calls_on_startup"])

        factor = self.client.get("/api/factor-quant/cache").json()
        self.assertTrue(factor["ok"])
        self.assertEqual(factor["data"]["mode"], "cache_only")
        self.assertFalse(factor["data"]["external_calls_triggered"])

        serenity = self.client.get("/api/serenity/cache").json()
        self.assertTrue(serenity["ok"])
        self.assertFalse(serenity["data"]["deepseek_called"])

        next_session = self.client.get("/api/next-session/cache").json()
        self.assertTrue(next_session["ok"])
        self.assertFalse(next_session["data"]["external_calls_triggered"])

        storage = self.client.get("/api/storage/factor-values").json()
        self.assertTrue(storage["ok"])
        self.assertTrue(storage["data"]["cache_only"])
        self.assertFalse(storage["data"]["external_calls_triggered"])

    def test_post_task_stub_returns_task_id(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        created = self.client.post("/api/factor-quant/refresh-data", json={"ts_code": "002008.SZ"}).json()
        self.assertTrue(created["ok"])
        task_id = created["data"]["task_id"]
        self.assertTrue(task_id.startswith("local-"))

        status = self.client.get(f"/api/tasks/{task_id}").json()
        self.assertTrue(status["ok"])
        self.assertEqual(status["data"]["status"], "success")
        self.assertEqual(status["data"]["progress"], 1.0)
        self.assertEqual(status["data"]["call_ledger"][0]["call_status"], "stub_not_called")

        listing = self.client.get("/api/tasks").json()
        self.assertTrue(listing["ok"])
        self.assertEqual(listing["data"]["tasks"][0]["task_id"], task_id)
        task_service._TASKS.clear()
        persisted_status = self.client.get(f"/api/tasks/{task_id}").json()
        self.assertTrue(persisted_status["ok"])
        self.assertEqual(persisted_status["data"]["task_id"], task_id)
        self.assertEqual(persisted_status["data"]["backend"], "local_fallback")

    def test_run_light_endpoint_writes_factor_cache(self):
        self._with_meta_store()
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
        self.assertNotIn("token", task["payload_safe"])

        factor = self.client.get("/api/factor-quant/cache").json()
        self.assertTrue(factor["ok"])
        self.assertEqual(factor["data"]["mode"], "light")
        self.assertEqual(factor["data"]["cache_source"], "sqlite_meta")
        self.assertFalse(factor["data"]["external_calls_triggered"])
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
