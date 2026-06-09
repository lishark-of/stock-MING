from __future__ import annotations

import importlib.util
import json
import unittest

from server.services import packet_service
from server.services.task_service import create_task_stub, read_task_status


class CommandCenter3ServerServiceTests(unittest.TestCase):
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

    def test_task_stub_records_safe_status_without_external_work(self):
        task = create_task_stub("refresh_factor_data", payload={"ts_code": "002008.SZ", "token": "SHOULD_NOT_KEEP"})

        self.assertTrue(task["task_id"].startswith("local-"))
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "stub_created_no_external_call")
        self.assertNotIn("token", task["payload_safe"])
        self.assertEqual(read_task_status(task["task_id"])["task_id"], task["task_id"])


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed in this environment")
class CommandCenter3FastAPITests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from server.main import app

        self.client = TestClient(app)

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

    def test_post_task_stub_returns_task_id(self):
        created = self.client.post("/api/factor-quant/refresh-data", json={"ts_code": "002008.SZ"}).json()
        self.assertTrue(created["ok"])
        task_id = created["data"]["task_id"]
        self.assertTrue(task_id.startswith("local-"))

        status = self.client.get(f"/api/tasks/{task_id}").json()
        self.assertTrue(status["ok"])
        self.assertEqual(status["data"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
