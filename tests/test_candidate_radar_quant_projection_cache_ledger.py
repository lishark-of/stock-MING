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
        small_data = packet["search_quant_projection_small_data_writeback_summary"]
        interpretation = packet["search_quant_projection_interpretation_summary"]
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
        self.assertEqual(
            small_data["schema_version"],
            "candidate_radar_search_quant_projection_small_data_writeback.v1",
        )
        self.assertEqual(small_data["status"], "small_data_writeback_ready_tushare_ledger_replayed")
        self.assertIn("Tushare 4/4 个接口", small_data["summary_label"])
        self.assertEqual(small_data["packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(small_data["writeback_surfaces"], ["cache", "call_ledger", "packet"])
        self.assertEqual(small_data["provider_call_source"], "post_task_call_ledger")
        self.assertTrue(small_data["provider_call_observed_only_from_post_task"])
        self.assertIn("GET cache replays stored packet only", small_data["readback_contract"])
        self.assertTrue(small_data["cache_packet_written"])
        self.assertTrue(small_data["small_data_writeback_ready"])
        self.assertTrue(small_data["provider_call_ledger_written"])
        self.assertEqual(small_data["provider_call_ledger_api_count"], 4)
        self.assertEqual(small_data["provider_api_call_count"], 4)
        self.assertEqual(small_data["provider_api_success_count"], 4)
        self.assertTrue(small_data["provider_external_call_observed_in_post_task"])
        self.assertTrue(small_data["deepseek_skipped_by_request"])
        self.assertFalse(small_data["cache_get_external_calls"])
        self.assertFalse(small_data["react_render_external_calls"])
        self.assertFalse(small_data["external_calls_triggered"])
        self.assertFalse(small_data["tushare_called"])
        self.assertFalse(small_data["deepseek_called"])
        self.assertTrue(small_data["does_not_execute_trades"])
        self.assertTrue(small_data["does_not_modify_strategy_action"])
        self.assertEqual(
            interpretation["schema_version"],
            "candidate_radar_search_quant_projection_interpretation.v1",
        )
        self.assertEqual(
            interpretation["status"],
            "interpretation_ready_tushare_ledger_pending_local_map",
        )
        self.assertIn("Tushare 4/4 接口账本已回放", interpretation["summary_label"])
        self.assertEqual(interpretation["ordinary_result_status"], "ready_pending_local_map")
        self.assertIn("可读结论：Tushare-first 账本已回放 4/4 个接口", interpretation["ordinary_result_summary"])
        self.assertIn("先读 Tushare 账本和本地推演摘要", interpretation["ordinary_result_next_step"])
        self.assertIn("解释只基于本地 cache / ledger / packet", interpretation["ordinary_result_boundary"])
        self.assertIn("Tushare 接口 4/4", interpretation["ordinary_result_evidence"])
        self.assertIn("DeepSeek 未参与", interpretation["ordinary_result_evidence"])
        self.assertTrue(interpretation["interpretation_ready"])
        self.assertEqual(interpretation["provider_api_success_count"], 4)
        self.assertEqual(interpretation["next_session_map_state"], "pending_local_cache_refresh")
        self.assertIn("Factor/Next/ECharts local cache replay", interpretation["missing_evidence"])
        self.assertFalse(interpretation["uses_deepseek_output"])
        self.assertFalse(interpretation["model_output_used"])
        self.assertFalse(interpretation["cache_get_external_calls"])
        self.assertFalse(interpretation["react_render_external_calls"])
        self.assertTrue(interpretation["does_not_execute_trades"])
        self.assertTrue(interpretation["does_not_modify_strategy_action"])
        self.assertTrue(interpretation["does_not_modify_prices"])

        dumped = json.dumps(cache, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn("REAL_TUSHARE_SECRET_VALUE", dumped)
        self.assertNotIn("REAL_DEEPSEEK_SECRET_VALUE", dumped)
        self.assertNotIn("TUSHARE_TOKEN", dumped)
        self.assertNotIn("DEEPSEEK_API_KEY", dumped)

    def test_confirm_tushare_first_blocks_missing_credentials_without_provider_call(self):
        self._with_meta_store()
        self._with_env(TUSHARE_TOKEN=None, DEEPSEEK_API_KEY=None)
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "radar_packet": {"status": "ready", "summary": "candidate cache"},
                "data_freshness": {"state": "fresh", "expected_trade_date": "2026-06-12"},
            }
        )

        original_run_tushare = candidate_service.tushare_task_service.run_tushare_refresh_task
        original_credential_presence = candidate_service._quant_acceptance_credential_presence_rows

        def fail_if_provider_called(*_args, **_kwargs):
            raise AssertionError("Tushare provider must not run when server credentials are missing")

        def missing_tushare_credential_presence_rows(*, include_tushare, include_deepseek):
            rows, summary = original_credential_presence(
                include_tushare=include_tushare,
                include_deepseek=include_deepseek,
            )
            rows = [dict(row) for row in rows]
            missing_count = 0
            present_count = 0
            for row in rows:
                if row["required"] and row["provider"] == "tushare":
                    row["present"] = False
                    row["status"] = "missing_no_value_read"
                if row["required"] and row["present"]:
                    present_count += 1
                elif row["required"]:
                    missing_count += 1
            summary = dict(summary)
            summary["status"] = (
                "required_env_key_missing_no_values_read"
                if missing_count
                else "all_required_env_keys_present_no_values_read"
            )
            summary["present_provider_count"] = present_count
            summary["missing_provider_count"] = missing_count
            return rows, summary

        candidate_service.tushare_task_service.run_tushare_refresh_task = fail_if_provider_called
        candidate_service._quant_acceptance_credential_presence_rows = missing_tushare_credential_presence_rows
        self.addCleanup(
            setattr,
            candidate_service.tushare_task_service,
            "run_tushare_refresh_task",
            original_run_tushare,
        )
        self.addCleanup(
            setattr,
            candidate_service,
            "_quant_acceptance_credential_presence_rows",
            original_credential_presence,
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
        task = response["data"]["task"]
        self.assertEqual(task["status"], "success")
        self.assertEqual(
            task["current_step"],
            "candidate_radar_quant_projection_tushare_first_chain_blocked_missing_credentials",
        )
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])

        cache = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(cache["ok"])
        packet = cache["data"]
        dry_run = packet["search_quant_projection_acceptance_dry_run_receipt"]
        execution_request = packet["search_quant_projection_execution_request_receipt"]
        provider_receipt = packet["search_quant_provider_model_acceptance_receipt"]
        small_data = packet["search_quant_projection_small_data_writeback_summary"]
        interpretation = packet["search_quant_projection_interpretation_summary"]

        self.assertEqual(
            dry_run["status"],
            "quant_projection_acceptance_dry_run_blocked_missing_credentials",
        )
        self.assertEqual(dry_run["credential_missing_provider_count"], 1)
        self.assertFalse(dry_run["ready_for_user_approved_real_acceptance"])
        self.assertEqual(
            execution_request["status"],
            "quant_projection_execution_request_blocked_dry_run_not_ready",
        )
        self.assertFalse(execution_request["local_execution_request_ready"])
        self.assertFalse(provider_receipt.get("direct_evidence_verified"))
        self.assertFalse(provider_receipt.get("tushare_call_ledger_evidence_done"))
        self.assertEqual(int(provider_receipt.get("provider_api_call_count") or 0), 0)
        self.assertEqual(small_data["status"], "small_data_writeback_blocked_missing_credentials")
        self.assertIn("缺少服务端 Tushare 凭据", small_data["summary_label"])
        self.assertEqual(small_data["writeback_surfaces"], ["cache", "call_ledger", "packet"])
        self.assertEqual(small_data["provider_call_source"], "not_called_missing_credentials_local_block")
        self.assertFalse(small_data["provider_call_observed_only_from_post_task"])
        self.assertIn("React render does not call provider/model", small_data["readback_contract"])
        self.assertTrue(small_data["cache_packet_written"])
        self.assertFalse(small_data["small_data_writeback_ready"])
        self.assertFalse(small_data["provider_call_ledger_written"])
        self.assertEqual(small_data["credential_missing_provider_count"], 1)
        self.assertEqual(small_data["provider_api_success_count"], 0)
        self.assertFalse(small_data["provider_external_call_observed_in_post_task"])
        self.assertFalse(small_data["cache_get_external_calls"])
        self.assertFalse(small_data["external_calls_triggered"])
        self.assertEqual(interpretation["status"], "interpretation_blocked_missing_tushare_credentials")
        self.assertIn("服务端 Tushare 凭据缺失", interpretation["summary_label"])
        self.assertEqual(interpretation["ordinary_result_status"], "blocked_missing_credentials")
        self.assertIn("还没有真实 provider 账本", interpretation["ordinary_result_summary"])
        self.assertIn("配置服务端凭据后重新点击确认", interpretation["ordinary_result_next_step"])
        self.assertIn("不调用 DeepSeek", interpretation["ordinary_result_boundary"])
        self.assertIn("DeepSeek 未参与", interpretation["ordinary_result_evidence"])
        self.assertFalse(interpretation["interpretation_ready"])
        self.assertIn("Tushare-first provider ledger", interpretation["missing_evidence"])
        self.assertFalse(interpretation["uses_deepseek_output"])
        self.assertFalse(interpretation["cache_get_external_calls"])
        self.assertFalse(interpretation["external_calls_triggered"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])

        dumped = json.dumps(cache, ensure_ascii=False)
        self.assertNotIn("SHOULD_DROP", dumped)
        self.assertNotIn("TUSHARE_TOKEN", dumped)
        self.assertNotIn("DEEPSEEK_API_KEY", dumped)


if __name__ == "__main__":
    unittest.main()
