from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

from server.services import candidate_service, packet_service, task_service, tushare_task_service
from server.services.task_service import clear_task_statuses_for_tests


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class CandidateRadarQuantProjectionCacheLedgerTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from server.main import app

        self.client = TestClient(app)

    def _with_meta_store(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "meta.sqlite"
        originals = {
            packet_service: packet_service.SQLITE_META_PATH,
            task_service: task_service.SQLITE_META_PATH,
            tushare_task_service: tushare_task_service.SQLITE_META_PATH,
            candidate_service: candidate_service.SQLITE_META_PATH,
        }
        for module in originals:
            module.SQLITE_META_PATH = db_path
        self.addCleanup(temp_dir.cleanup)
        for module, original in originals.items():
            self.addCleanup(setattr, module, "SQLITE_META_PATH", original)

    def _with_snapshot_cache(self, payload):
        original_path = packet_service.SNAPSHOT_CACHE_PATH
        temp_dir = tempfile.TemporaryDirectory()
        cache_path = Path(temp_dir.name) / "command_center_latest.json"
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        packet_service.SNAPSHOT_CACHE_PATH = cache_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SNAPSHOT_CACHE_PATH", original_path)

    def _with_env(self, **values):
        original = {key: os.environ.get(key) for key in values}
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)

        def restore():
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.addCleanup(restore)

    def test_confirm_tushare_first_writes_provider_ledger_to_cache_envelope(self):
        self._with_meta_store()
        self._with_env(TUSHARE_TOKEN="REAL_TUSHARE_SECRET_VALUE", DEEPSEEK_API_KEY="REAL_DEEPSEEK_SECRET_VALUE")
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "radar_packet": {"status": "ready", "summary": "candidate cache"},
                "data_freshness": {"state": "fresh", "expected_trade_date": "2026-06-12"},
            }
        )

        original_run_tushare = candidate_service.tushare_task_service.run_tushare_refresh_task

        def fake_run_tushare_refresh_task(payload, **_kwargs):
            return {
                "task_id": "fake-tushare-light-cache-ledger",
                "status": "success",
                "current_step": "tushare_refresh_completed",
                "call_ledger": [
                    {
                        "api": api,
                        "request_params_safe": {
                            "ts_code": payload["ts_code"],
                            "start_date": payload["start_date"],
                            "end_date": payload["end_date"],
                        },
                        "row_count": 3,
                        "data_date": payload["end_date"],
                        "local_fetched_at": "2026-06-19T10:00:00",
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
                    for api in payload["apis"]
                ],
            }

        candidate_service.tushare_task_service.run_tushare_refresh_task = fake_run_tushare_refresh_task
        self.addCleanup(
            setattr,
            candidate_service.tushare_task_service,
            "run_tushare_refresh_task",
            original_run_tushare,
        )

        response = self.client.post(
            "/api/candidate-radar/quant-projection",
            json={
                "symbol": "002008",
                "include_tushare": True,
                "include_deepseek": False,
                "user_approved": True,
                "token": "SHOULD_DROP",
            },
        ).json()

        self.assertTrue(response["ok"])
        self.assertEqual(
            response["data"]["task"]["current_step"],
            "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_skipped",
        )

        cache = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(cache["ok"])
        packet = cache["data"]
        receipt = packet["search_quant_provider_model_acceptance_receipt"]
        self.assertEqual(
            receipt["status"],
            "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_skipped",
        )
        self.assertTrue(receipt["tushare_call_ledger_evidence_done"])
        self.assertTrue(receipt["deepseek_skipped_by_request"])
        self.assertFalse(receipt["deepseek_called"])
        self.assertFalse(receipt["production_quant_projection_complete"])

        expected_apis = ["trade_cal", "daily", "daily_basic", "moneyflow"]
        packet_provider_ledger = [
            row for row in packet["call_ledger"] if row.get("api") in expected_apis
        ]
        envelope_provider_ledger = [
            row for row in cache["call_ledger"] if row.get("api") in expected_apis
        ]
        self.assertEqual([row["api"] for row in packet_provider_ledger], expected_apis)
        self.assertEqual(envelope_provider_ledger, packet_provider_ledger)
        self.assertTrue(all(row["tushare_called"] is True for row in packet_provider_ledger))
        self.assertFalse(any(row["deepseek_called"] is True for row in packet_provider_ledger))
        self.assertFalse(any(row["github_called"] is True for row in packet_provider_ledger))
        self.assertTrue(
            any(row["api"] == "local_candidate_radar_quant_projection_provider_model_acceptance" for row in packet["call_ledger"])
        )

        dumped = json.dumps(cache, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn("REAL_TUSHARE_SECRET_VALUE", dumped)
        self.assertNotIn("REAL_DEEPSEEK_SECRET_VALUE", dumped)
        self.assertNotIn("TUSHARE_TOKEN", dumped)
        self.assertNotIn("DEEPSEEK_API_KEY", dumped)


if __name__ == "__main__":
    unittest.main()
