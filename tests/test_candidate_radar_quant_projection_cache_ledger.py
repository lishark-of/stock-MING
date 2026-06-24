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
                "p0_confirm_gate_evidence": {
                    "schema_version": "candidate_radar_p0_confirm_gate.v1",
                    "p0_ready": True,
                    "fastapi_cache_get_ready": True,
                    "bootstrap_runtime_mode_ready": True,
                    "desktop_preflight_ready": True,
                    "p0_stability_check_ready": True,
                    "candidate_cache_ready": True,
                    "candidate_cache_status": "ready",
                    "bootstrap_packet_key": "command_center_3_bootstrap_runtime_mode_packet",
                    "desktop_preflight_packet_key": "command_center_3_desktop_shell_preflight_cache",
                    "creates_task_only_after_button": True,
                    "react_render_external_calls": False,
                    "get_cache_external_calls": False,
                    "contains_secret": False,
                },
                "token": "SHOULD_DROP",
            },
        ).json()

        self.assertTrue(response["ok"])
        task = response["data"]["task"]
        self.assertEqual(
            task["current_step"],
            "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_skipped",
        )
        expected_apis = ["trade_cal", "daily", "daily_basic", "moneyflow"]
        task_provider_ledger = [
            row for row in task["call_ledger"] if row.get("api") in expected_apis
        ]
        self.assertEqual([row["api"] for row in task_provider_ledger], expected_apis)
        self.assertTrue(task["call_ledger"][0]["delegated_tushare_first_call_ledger_replayed"])
        self.assertEqual(task["call_ledger"][0]["delegated_tushare_first_call_ledger_count"], 5)
        self.assertEqual(task["call_ledger"][0]["delegated_tushare_first_provider_api_success_count"], 4)
        self.assertTrue(
            any(
                row["api"] == "local_candidate_radar_quant_projection_provider_model_acceptance"
                for row in task["call_ledger"]
            )
        )
        self.assertTrue(task["external_calls_triggered"])
        self.assertTrue(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        confirm_contract = task["payload_safe"]["ordinary_confirm_chain_contract"]
        self.assertEqual(
            confirm_contract["schema_version"],
            "candidate_radar_search_quant_projection_confirm_chain.v1",
        )
        self.assertEqual(confirm_contract["trigger"], "confirmed_symbol_button_post_task")
        self.assertEqual(confirm_contract["route"], "POST /api/candidate-radar/quant-projection")
        self.assertTrue(confirm_contract["user_confirmed"])
        self.assertTrue(confirm_contract["tushare_first_chain_requested"])
        self.assertTrue(confirm_contract["include_tushare_requested"])
        self.assertFalse(confirm_contract["include_deepseek_requested"])
        self.assertTrue(confirm_contract["deepseek_governed_executor_required"])
        self.assertFalse(confirm_contract["deepseek_called_from_confirm_chain"])
        self.assertFalse(confirm_contract["search_input_creates_task"])
        self.assertTrue(confirm_contract["confirm_button_creates_task"])
        self.assertFalse(confirm_contract["cache_get_external_calls"])
        self.assertFalse(confirm_contract["react_render_external_calls"])
        self.assertTrue(confirm_contract["does_not_execute_trades"])
        self.assertTrue(confirm_contract["does_not_modify_strategy_action"])
        self.assertFalse(confirm_contract["production_quant_projection_complete"])

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
        self.assertEqual(small_data["ordinary_readback_status"], "ready_tushare_ledger_replayed")
        self.assertIn("小数据已写入 cache / ledger / packet", small_data["ordinary_readback_summary"])
        self.assertIn("Tushare 4/4", small_data["ordinary_readback_summary"])
        self.assertIn("DeepSeek 未参与", small_data["ordinary_readback_summary"])
        self.assertIn("先看本地量化推演和次日图谱回放", small_data["ordinary_readback_next_step"])
        self.assertEqual(small_data["ordinary_readback_row_count"], 3)
        self.assertTrue(small_data["ordinary_readback_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_readback_rows_create_task"])
        self.assertEqual(small_data["ordinary_task_readback_row_count"], 3)
        self.assertTrue(small_data["ordinary_task_readback_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_task_readback_rows_create_task"])
        self.assertEqual(small_data["ordinary_confirm_outcome_row_count"], 3)
        self.assertTrue(small_data["ordinary_confirm_outcome_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_confirm_outcome_rows_create_task"])
        self.assertFalse(small_data["ordinary_confirm_outcome_rows_call_provider_from_readback"])
        self.assertFalse(small_data["ordinary_confirm_outcome_rows_use_model_output"])
        self.assertTrue(small_data["ordinary_confirm_outcome_rows_are_not_trade_signals"])
        self.assertEqual(small_data["ordinary_post_confirm_action_row_count"], 4)
        self.assertTrue(small_data["ordinary_post_confirm_action_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_post_confirm_action_rows_create_task"])
        self.assertTrue(small_data["ordinary_post_confirm_action_rows_are_not_trade_signals"])
        self.assertEqual(small_data["ordinary_confirm_trigger_boundary_row_count"], 4)
        self.assertTrue(small_data["ordinary_confirm_trigger_boundary_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_confirm_trigger_boundary_rows_create_task"])
        self.assertFalse(small_data["ordinary_confirm_trigger_boundary_rows_call_provider_from_readback"])
        self.assertTrue(small_data["ordinary_confirm_trigger_boundary_rows_are_not_trade_signals"])
        self.assertEqual(small_data["ordinary_confirm_button_readiness_row_count"], 4)
        self.assertTrue(small_data["ordinary_confirm_button_readiness_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_confirm_button_readiness_rows_create_task"])
        self.assertFalse(small_data["ordinary_confirm_button_readiness_rows_call_provider_from_readback"])
        self.assertTrue(small_data["ordinary_confirm_button_readiness_rows_are_not_trade_signals"])
        self.assertEqual(small_data["ordinary_confirm_replay_stage_row_count"], 4)
        self.assertTrue(small_data["ordinary_confirm_replay_stage_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_confirm_replay_stage_rows_create_task"])
        self.assertFalse(small_data["ordinary_confirm_replay_stage_rows_use_model_output"])
        self.assertTrue(small_data["ordinary_confirm_replay_stage_rows_are_not_trade_signals"])
        self.assertEqual(small_data["ordinary_confirmed_task_receipt_row_count"], 6)
        self.assertTrue(small_data["ordinary_confirmed_task_receipt_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_confirmed_task_receipt_rows_create_task"])
        self.assertEqual(small_data["ordinary_provider_api_row_count"], 4)
        self.assertTrue(small_data["ordinary_provider_api_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_provider_api_rows_create_task"])
        self.assertEqual(small_data["ordinary_writeback_action_row_count"], 4)
        self.assertTrue(small_data["ordinary_writeback_action_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_writeback_action_rows_create_task"])
        self.assertTrue(small_data["ordinary_writeback_action_rows_are_not_trade_signals"])
        self.assertEqual(small_data["ordinary_one_screen_action_row_count"], 4)
        self.assertTrue(small_data["ordinary_one_screen_action_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_one_screen_action_rows_create_task"])
        self.assertFalse(small_data["ordinary_one_screen_action_rows_call_provider_from_readback"])
        self.assertFalse(small_data["ordinary_one_screen_action_rows_use_model_output"])
        self.assertTrue(small_data["ordinary_one_screen_action_rows_are_not_trade_signals"])
        self.assertEqual(small_data["ordinary_writeback_integrity_row_count"], 3)
        self.assertTrue(small_data["ordinary_writeback_integrity_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_writeback_integrity_rows_create_task"])
        self.assertTrue(small_data["ordinary_writeback_integrity_rows_are_not_trade_signals"])
        writeback_checkpoint = small_data["ordinary_writeback_checkpoint_contract"]
        self.assertEqual(
            writeback_checkpoint["schema_version"],
            "candidate_radar_search_quant_projection_writeback_checkpoint.v1",
        )
        self.assertEqual(writeback_checkpoint["source_task_route"], "POST /api/candidate-radar/quant-projection")
        self.assertEqual(writeback_checkpoint["readback_route"], "GET /api/candidate-radar/cache")
        self.assertEqual(writeback_checkpoint["packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(writeback_checkpoint["surfaces"], ["cache", "call_ledger", "packet"])
        self.assertEqual(writeback_checkpoint["surface_count"], 3)
        self.assertEqual(writeback_checkpoint["readable_surface_count"], 3)
        self.assertEqual(writeback_checkpoint["complete_surface_count"], 3)
        self.assertTrue(writeback_checkpoint["cache_written"])
        self.assertEqual(writeback_checkpoint["call_ledger_state"], "ready_tushare_post_task_ledger")
        self.assertTrue(writeback_checkpoint["packet_written"])
        self.assertEqual(writeback_checkpoint["provider_call_source"], "post_task_call_ledger")
        self.assertTrue(writeback_checkpoint["provider_ledger_ready"])
        self.assertTrue(writeback_checkpoint["cache_only_readback"])
        self.assertFalse(writeback_checkpoint["creates_task_from_readback"])
        self.assertFalse(writeback_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(writeback_checkpoint["deepseek_called_from_readback"])
        self.assertTrue(writeback_checkpoint["does_not_execute_trades"])
        self.assertTrue(writeback_checkpoint["does_not_modify_strategy_action"])
        self.assertFalse(writeback_checkpoint["production_quant_projection_complete"])
        self.assertEqual(packet["search_quant_projection_writeback_checkpoint"], writeback_checkpoint)
        small_data_checkpoint = packet["search_quant_projection_small_data_readback_checkpoint"]
        self.assertEqual(
            small_data_checkpoint["schema_version"],
            "candidate_radar_search_quant_projection_small_data_readback_checkpoint.v1",
        )
        self.assertEqual(small_data_checkpoint["status"], small_data["status"])
        self.assertTrue(small_data_checkpoint["ready"])
        self.assertEqual(small_data_checkpoint["writeback_surfaces"], ["cache", "call_ledger", "packet"])
        self.assertEqual(small_data_checkpoint["provider_call_source"], "post_task_call_ledger")
        self.assertEqual(small_data_checkpoint["provider_api_success_count"], 4)
        self.assertEqual(small_data_checkpoint["readable_surface_count"], 3)
        self.assertEqual(small_data_checkpoint["complete_surface_count"], 3)
        self.assertTrue(small_data_checkpoint["cache_packet_written"])
        self.assertTrue(small_data_checkpoint["provider_call_ledger_written"])
        self.assertTrue(small_data_checkpoint["packet_written"])
        self.assertTrue(small_data_checkpoint["cache_only_readback"])
        self.assertFalse(small_data_checkpoint["creates_task_from_readback"])
        self.assertFalse(small_data_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(small_data_checkpoint["uses_deepseek_output"])
        self.assertTrue(small_data_checkpoint["does_not_execute_trades"])
        self.assertTrue(small_data_checkpoint["does_not_modify_strategy_action"])
        self.assertTrue(packet["search_quant_projection_small_data_writeback_ready"])
        self.assertEqual(packet["search_quant_projection_small_data_writeback_status"], small_data["status"])
        self.assertEqual(packet["search_quant_projection_writeback_surfaces"], ["cache", "call_ledger", "packet"])
        self.assertTrue(small_data["ordinary_writeback_checkpoint_is_cache_only"])
        self.assertFalse(small_data["ordinary_writeback_checkpoint_creates_task"])
        self.assertTrue(small_data["ordinary_writeback_checkpoint_is_not_trade_signal"])
        self.assertEqual(packet["counts"]["search_quant_projection_small_data_writeback_action_row_count"], 4)
        self.assertEqual(packet["counts"]["search_quant_projection_writeback_integrity_row_count"], 3)
        self.assertEqual(packet["counts"]["search_quant_projection_writeback_checkpoint_surface_count"], 3)
        self.assertEqual(packet["counts"]["search_quant_projection_writeback_checkpoint_readable_surface_count"], 3)
        self.assertEqual(packet["counts"]["search_quant_projection_writeback_checkpoint_complete_surface_count"], 3)
        self.assertEqual(packet["counts"]["search_quant_projection_post_confirm_action_row_count"], 4)
        self.assertEqual(packet["counts"]["search_quant_projection_confirm_trigger_boundary_row_count"], 4)
        self.assertEqual(packet["counts"]["search_quant_projection_confirm_button_readiness_row_count"], 4)
        self.assertEqual(packet["counts"]["search_quant_projection_confirm_replay_stage_row_count"], 4)
        self.assertEqual(packet["counts"]["search_quant_projection_confirm_outcome_row_count"], 3)
        self.assertEqual(packet["counts"]["search_quant_projection_one_screen_action_row_count"], 4)
        self.assertTrue(packet["policy"]["search_quant_projection_small_data_writeback_action_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_small_data_writeback_action_rows_create_task"])
        self.assertTrue(packet["policy"]["search_quant_projection_one_screen_action_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_one_screen_action_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_one_screen_action_rows_call_provider_from_readback"])
        self.assertFalse(packet["policy"]["search_quant_projection_one_screen_action_rows_use_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_one_screen_action_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["search_quant_projection_writeback_integrity_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_writeback_integrity_rows_create_task"])
        self.assertTrue(packet["policy"]["search_quant_projection_writeback_integrity_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["search_quant_projection_writeback_checkpoint_is_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_writeback_checkpoint_creates_task"])
        self.assertTrue(packet["policy"]["search_quant_projection_writeback_checkpoint_is_not_trade_signal"])
        self.assertTrue(packet["policy"]["search_quant_projection_post_confirm_action_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_post_confirm_action_rows_create_task"])
        self.assertTrue(packet["policy"]["search_quant_projection_post_confirm_action_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_trigger_boundary_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_trigger_boundary_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_trigger_boundary_rows_call_provider_from_readback"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_trigger_boundary_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_button_readiness_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_button_readiness_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_button_readiness_rows_call_provider_from_readback"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_button_readiness_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_replay_stage_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_replay_stage_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_replay_stage_rows_use_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_replay_stage_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_outcome_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_outcome_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_outcome_rows_call_provider_from_readback"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_outcome_rows_use_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_outcome_rows_are_not_trade_signals"])
        readback_rows = {row["surface"]: row for row in small_data["ordinary_readback_rows"]}
        self.assertEqual(set(readback_rows), {"cache", "call_ledger", "packet"})
        self.assertEqual(readback_rows["cache"]["status"], "written")
        self.assertEqual(readback_rows["call_ledger"]["status"], "post_task_call_ledger")
        self.assertIn("Tushare provider ledger 已写入", readback_rows["call_ledger"]["ordinary_label"])
        self.assertEqual(readback_rows["packet"]["status"], "written")
        self.assertIn("packet=command_center_3_candidate_radar_cache", readback_rows["packet"]["ordinary_label"])
        for readback_row in readback_rows.values():
            self.assertFalse(readback_row["external_calls_triggered"])
            self.assertFalse(readback_row["tushare_called"])
            self.assertFalse(readback_row["deepseek_called"])
            self.assertFalse(readback_row["github_called"])
            self.assertFalse(readback_row["contains_secret"])
            self.assertTrue(readback_row["does_not_execute_trades"])
            self.assertTrue(readback_row["does_not_modify_strategy_action"])
        task_rows = {row["surface"]: row for row in small_data["ordinary_task_readback_rows"]}
        self.assertEqual(set(task_rows), {"task_id", "current_step", "task_status_panel"})
        self.assertEqual(task_rows["task_id"]["status"], "written")
        self.assertIn(response["data"]["task_id"], task_rows["task_id"]["ordinary_label"])
        self.assertIn(
            "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_skipped",
            task_rows["current_step"]["ordinary_label"],
        )
        self.assertEqual(task_rows["task_status_panel"]["status"], "poll_ready")
        for task_row in task_rows.values():
            self.assertFalse(task_row["external_calls_triggered"])
            self.assertFalse(task_row["tushare_called"])
            self.assertFalse(task_row["deepseek_called"])
            self.assertFalse(task_row["github_called"])
            self.assertFalse(task_row["contains_secret"])
            self.assertTrue(task_row["does_not_execute_trades"])
            self.assertTrue(task_row["does_not_modify_strategy_action"])
            self.assertTrue(task_row["does_not_execute_trades"])
            self.assertTrue(task_row["does_not_modify_strategy_action"])
        outcome_rows = {row["outcome_key"]: row for row in small_data["ordinary_confirm_outcome_rows"]}
        self.assertEqual(set(outcome_rows), {"p1_confirm_result", "p2_writeback_result", "p3_replay_result"})
        self.assertIn(response["data"]["task_id"], outcome_rows["p1_confirm_result"]["当前状态"])
        self.assertIn("Tushare 4/4", outcome_rows["p2_writeback_result"]["当前状态"])
        self.assertIn("结果入口可回放", outcome_rows["p3_replay_result"]["当前状态"])
        for outcome_row in outcome_rows.values():
            self.assertTrue(outcome_row["cache_only_readback"])
            self.assertFalse(outcome_row["creates_task_from_readback"])
            self.assertFalse(outcome_row["readback_external_calls_triggered"])
            self.assertFalse(outcome_row["readback_calls_provider"])
            self.assertFalse(outcome_row["uses_model_output"])
            self.assertFalse(outcome_row["external_calls_triggered"])
            self.assertFalse(outcome_row["tushare_called"])
            self.assertFalse(outcome_row["deepseek_called"])
            self.assertFalse(outcome_row["github_called"])
            self.assertFalse(outcome_row["contains_secret"])
            self.assertTrue(outcome_row["does_not_execute_trades"])
            self.assertTrue(outcome_row["does_not_modify_strategy_action"])
            self.assertTrue(outcome_row["candidate_is_not_buy_instruction"])
        post_confirm_rows = {row["action_key"]: row for row in small_data["ordinary_post_confirm_action_rows"]}
        self.assertEqual(set(post_confirm_rows), {"check_task_id", "poll_task_status", "refresh_cache", "replay_results"})
        self.assertIn(response["data"]["task_id"], post_confirm_rows["check_task_id"]["当前状态"])
        self.assertEqual(post_confirm_rows["poll_task_status"]["入口"], "TaskStatusPanel")
        self.assertIn("cache / ledger / packet 可回放", post_confirm_rows["refresh_cache"]["当前状态"])
        self.assertIn("股票量化推演", post_confirm_rows["replay_results"]["入口"])
        for action_row in post_confirm_rows.values():
            self.assertTrue(action_row["cache_only_readback"])
            self.assertFalse(action_row["creates_task_from_readback"])
            self.assertFalse(action_row["external_calls_triggered"])
            self.assertFalse(action_row["tushare_called"])
            self.assertFalse(action_row["deepseek_called"])
            self.assertFalse(action_row["github_called"])
            self.assertFalse(action_row["contains_secret"])
            self.assertTrue(action_row["does_not_execute_trades"])
            self.assertTrue(action_row["does_not_modify_strategy_action"])
            self.assertTrue(action_row["candidate_is_not_buy_instruction"])
        trigger_rows = {row["trigger_key"]: row for row in small_data["ordinary_confirm_trigger_boundary_rows"]}
        self.assertEqual(
            set(trigger_rows),
            {
                "search_input_local_validation",
                "confirm_button_post_task",
                "post_task_provider_ledger",
                "get_cache_result_replay",
            },
        )
        self.assertIn("输入框只做本地校验", trigger_rows["search_input_local_validation"]["边界"])
        self.assertEqual(trigger_rows["confirm_button_post_task"]["允许动作"], "POST /api/candidate-radar/quant-projection")
        self.assertTrue(trigger_rows["confirm_button_post_task"]["may_create_task_after_confirm"])
        self.assertTrue(trigger_rows["confirm_button_post_task"]["post_task_may_call_tushare"])
        self.assertIn("POST task ledger 已回放", trigger_rows["post_task_provider_ledger"]["当前状态"])
        self.assertTrue(trigger_rows["post_task_provider_ledger"]["post_task_may_call_tushare"])
        self.assertIn("不创建第二个 task", trigger_rows["get_cache_result_replay"]["边界"])
        for trigger_row in trigger_rows.values():
            self.assertTrue(trigger_row["cache_only_readback"])
            self.assertFalse(trigger_row["creates_task_from_readback"])
            self.assertFalse(trigger_row["external_calls_triggered"])
            self.assertFalse(trigger_row["tushare_called"])
            self.assertFalse(trigger_row["deepseek_called"])
            self.assertFalse(trigger_row["github_called"])
            self.assertFalse(trigger_row["contains_secret"])
            self.assertTrue(trigger_row["does_not_execute_trades"])
            self.assertTrue(trigger_row["does_not_modify_strategy_action"])
            self.assertTrue(trigger_row["candidate_is_not_buy_instruction"])
        readiness_rows = {
            row["readiness_key"]: row
            for row in small_data["ordinary_confirm_button_readiness_rows"]
        }
        self.assertEqual(
            set(readiness_rows),
            {
                "input_local_validation",
                "confirm_button_post_task_ready",
                "task_receipt_readback",
                "cache_replay_after_success",
            },
        )
        self.assertIn("输入框和搜索输入只做本地校验", readiness_rows["input_local_validation"]["边界"])
        self.assertEqual(
            readiness_rows["confirm_button_post_task_ready"]["允许动作"],
            "按钮门控 POST /api/candidate-radar/quant-projection",
        )
        self.assertTrue(readiness_rows["confirm_button_post_task_ready"]["may_create_task_after_confirm"])
        self.assertTrue(readiness_rows["confirm_button_post_task_ready"]["post_task_may_call_tushare"])
        self.assertIn(response["data"]["task_id"], readiness_rows["task_receipt_readback"]["当前状态"])
        self.assertIn("只读回放", readiness_rows["cache_replay_after_success"]["允许动作"])
        for readiness_row in readiness_rows.values():
            self.assertTrue(readiness_row["cache_only_readback"])
            self.assertFalse(readiness_row["creates_task_from_readback"])
            self.assertFalse(readiness_row["search_input_external_calls"])
            self.assertFalse(readiness_row["react_render_external_calls"])
            self.assertFalse(readiness_row["get_cache_external_calls"])
            self.assertFalse(readiness_row["external_calls_triggered"])
            self.assertFalse(readiness_row["tushare_called"])
            self.assertFalse(readiness_row["deepseek_called"])
            self.assertFalse(readiness_row["github_called"])
            self.assertFalse(readiness_row["contains_secret"])
            self.assertTrue(readiness_row["does_not_execute_trades"])
            self.assertTrue(readiness_row["does_not_modify_strategy_action"])
            self.assertTrue(readiness_row["candidate_is_not_buy_instruction"])
        stage_rows = {row["stage_key"]: row for row in small_data["ordinary_confirm_replay_stage_rows"]}
        self.assertEqual(
            set(stage_rows),
            {"current_confirm_replay_stage", "task_acceptance", "cache_ledger_packet_replay", "result_replay"},
        )
        self.assertIn("P2 ready", stage_rows["current_confirm_replay_stage"]["当前状态"])
        self.assertIn("Tushare 4/4", stage_rows["cache_ledger_packet_replay"]["当前状态"])
        self.assertIn("DeepSeek governed executor 单独补", stage_rows["result_replay"]["当前状态"])
        for stage_row in stage_rows.values():
            self.assertTrue(stage_row["cache_only_readback"])
            self.assertFalse(stage_row["creates_task_from_readback"])
            self.assertFalse(stage_row["uses_model_output"])
            self.assertFalse(stage_row["external_calls_triggered"])
            self.assertFalse(stage_row["tushare_called"])
            self.assertFalse(stage_row["deepseek_called"])
            self.assertFalse(stage_row["github_called"])
            self.assertFalse(stage_row["contains_secret"])
            self.assertTrue(stage_row["does_not_execute_trades"])
            self.assertTrue(stage_row["does_not_modify_strategy_action"])
            self.assertTrue(stage_row["candidate_is_not_buy_instruction"])
        writeback_action_rows = {row["action_key"]: row for row in small_data["ordinary_writeback_action_rows"]}
        self.assertEqual(
            set(writeback_action_rows),
            {"check_writeback_status", "review_task_status", "review_call_ledger", "refresh_cache_replay"},
        )
        self.assertIn("Tushare ledger 已回放", writeback_action_rows["review_call_ledger"]["当前状态"])
        self.assertIn("股票量化推演", writeback_action_rows["refresh_cache_replay"]["入口"])
        self.assertIn("不会创建 task", writeback_action_rows["check_writeback_status"]["边界"])
        self.assertIn("接口级明细下沉到高级状态", writeback_action_rows["review_call_ledger"]["入口"])
        for action_row in writeback_action_rows.values():
            self.assertTrue(action_row["cache_only_readback"])
            self.assertFalse(action_row["creates_task_from_readback"])
            self.assertFalse(action_row["external_calls_triggered"])
            self.assertFalse(action_row["tushare_called"])
            self.assertFalse(action_row["deepseek_called"])
            self.assertFalse(action_row["github_called"])
            self.assertFalse(action_row["contains_secret"])
            self.assertTrue(action_row["does_not_execute_trades"])
            self.assertTrue(action_row["does_not_modify_strategy_action"])
            self.assertTrue(action_row["candidate_is_not_buy_instruction"])
        one_screen_rows = {row["action_key"]: row for row in small_data["ordinary_one_screen_action_rows"]}
        self.assertEqual(set(one_screen_rows), {"confirm", "task", "writeback", "result"})
        self.assertIn("Tushare-first 已回放", one_screen_rows["confirm"]["当前状态"])
        self.assertEqual(one_screen_rows["task"]["入口"], "TaskStatusPanel")
        self.assertIn("cache / ledger / packet", one_screen_rows["writeback"]["当前状态"])
        self.assertIn("来源=Tushare-first ledger", one_screen_rows["result"]["当前状态"])
        self.assertIn("不调用 DeepSeek", one_screen_rows["result"]["边界"])
        for one_screen_row in one_screen_rows.values():
            self.assertTrue(one_screen_row["cache_only_readback"])
            self.assertFalse(one_screen_row["creates_task_from_readback"])
            self.assertFalse(one_screen_row["readback_external_calls_triggered"])
            self.assertFalse(one_screen_row["readback_calls_provider"])
            self.assertFalse(one_screen_row["uses_model_output"])
            self.assertFalse(one_screen_row["external_calls_triggered"])
            self.assertFalse(one_screen_row["tushare_called"])
            self.assertFalse(one_screen_row["deepseek_called"])
            self.assertFalse(one_screen_row["github_called"])
            self.assertFalse(one_screen_row["contains_secret"])
            self.assertTrue(one_screen_row["does_not_execute_trades"])
            self.assertTrue(one_screen_row["does_not_modify_strategy_action"])
            self.assertTrue(one_screen_row["candidate_is_not_buy_instruction"])
        integrity_rows = {row["integrity_key"]: row for row in small_data["ordinary_writeback_integrity_rows"]}
        self.assertEqual(set(integrity_rows), {"cache_written", "call_ledger_written", "packet_written"})
        self.assertEqual(integrity_rows["cache_written"]["是否齐备"], "ready")
        self.assertEqual(integrity_rows["call_ledger_written"]["是否齐备"], "ready")
        self.assertEqual(integrity_rows["packet_written"]["是否齐备"], "ready")
        self.assertIn("Tushare 4/4", integrity_rows["call_ledger_written"]["当前状态"])
        self.assertIn("不创建 task", integrity_rows["cache_written"]["边界"])
        self.assertIn("不含凭据", integrity_rows["packet_written"]["边界"])
        for integrity_row in integrity_rows.values():
            self.assertTrue(integrity_row["cache_only_readback"])
            self.assertFalse(integrity_row["creates_task_from_readback"])
            self.assertFalse(integrity_row["external_calls_triggered"])
            self.assertFalse(integrity_row["tushare_called"])
            self.assertFalse(integrity_row["deepseek_called"])
            self.assertFalse(integrity_row["github_called"])
            self.assertFalse(integrity_row["contains_secret"])
            self.assertTrue(integrity_row["does_not_execute_trades"])
            self.assertTrue(integrity_row["does_not_modify_strategy_action"])
            self.assertTrue(integrity_row["candidate_is_not_buy_instruction"])
        receipt_rows = {row["receipt_item"]: row for row in small_data["ordinary_confirmed_task_receipt_rows"]}
        self.assertEqual(
            set(receipt_rows),
            {
                "task_id",
                "tushare_first_chain",
                "p1_confirm_contract",
                "p0_confirm_gate",
                "safe_current_step",
                "result_destinations",
            },
        )
        self.assertIn(response["data"]["task_id"], receipt_rows["task_id"]["ordinary_label"])
        self.assertEqual(receipt_rows["tushare_first_chain"]["status"], "tushare_first_confirmed")
        self.assertIn("include_tushare=true / include_deepseek=false", receipt_rows["tushare_first_chain"]["ordinary_label"])
        self.assertEqual(receipt_rows["p1_confirm_contract"]["status"], "confirm_contract_visible")
        self.assertEqual(receipt_rows["p0_confirm_gate"]["status"], "p0_gate_ready")
        self.assertTrue(receipt_rows["p0_confirm_gate"]["p0_ready"])
        self.assertTrue(receipt_rows["p0_confirm_gate"]["fastapi_cache_get_ready"])
        self.assertTrue(receipt_rows["p0_confirm_gate"]["bootstrap_runtime_mode_ready"])
        self.assertTrue(receipt_rows["p0_confirm_gate"]["desktop_preflight_ready"])
        self.assertTrue(receipt_rows["p0_confirm_gate"]["p0_stability_check_ready"])
        self.assertTrue(receipt_rows["p0_confirm_gate"]["candidate_cache_ready"])
        self.assertEqual(
            receipt_rows["p0_confirm_gate"]["desktop_preflight_packet_key"],
            "command_center_3_desktop_shell_preflight_cache",
        )
        self.assertIn("P0 stability", receipt_rows["p0_confirm_gate"]["ordinary_label"])
        self.assertFalse(receipt_rows["p0_confirm_gate"]["creates_task_from_readback"])
        self.assertIn(
            "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_skipped",
            receipt_rows["safe_current_step"]["ordinary_label"],
        )
        self.assertEqual(receipt_rows["result_destinations"]["status"], "local_replay_destinations_visible")
        for receipt_row in receipt_rows.values():
            self.assertFalse(receipt_row["external_calls_triggered"])
            self.assertFalse(receipt_row["tushare_called"])
            self.assertFalse(receipt_row["deepseek_called"])
            self.assertFalse(receipt_row["github_called"])
            self.assertFalse(receipt_row["contains_secret"])
            self.assertTrue(receipt_row["does_not_execute_trades"])
            self.assertTrue(receipt_row["does_not_modify_strategy_action"])
        destination_rows = {row["destination"]: row for row in small_data["ordinary_replay_destination_rows"]}
        self.assertEqual(set(destination_rows), {"stock_quant_projection", "next_session_map", "candidate_pool"})
        next_destination = destination_rows["next_session_map"]
        self.assertEqual(next_destination["P3状态"], "p3_handoff_ready_tushare_ledger")
        self.assertIn("Tushare-first 账本已回放", next_destination["当前状态"])
        self.assertIn("Factor/Next/ECharts 未刷新则显示待补证据", next_destination["当前状态"])
        self.assertIn("operation_zones 来源", next_destination["下一步"])
        self.assertIn("Next Session cache 仍旧", next_destination["下一步"])
        self.assertIn("来源=Tushare-first ledger", next_destination["可解释结果"])
        self.assertIn("缺口=Factor/Next/ECharts local cache replay", next_destination["可解释结果"])
        self.assertIn("不从 #next 链接创建 task 或补调 provider/model", next_destination["缺口处理"])
        self.assertIn("不覆盖 strategy action、不下单", next_destination["operation_zones边界"])
        self.assertTrue(next_destination["cache_only_readback"])
        self.assertFalse(next_destination["creates_task_from_readback"])
        self.assertFalse(next_destination["external_calls_triggered"])
        self.assertFalse(next_destination["tushare_called"])
        self.assertFalse(next_destination["deepseek_called"])
        self.assertFalse(next_destination["github_called"])
        self.assertFalse(next_destination["contains_secret"])
        self.assertTrue(next_destination["does_not_execute_trades"])
        self.assertTrue(next_destination["does_not_modify_strategy_action"])
        self.assertTrue(next_destination["candidate_is_not_buy_instruction"])
        api_rows = {row["api"]: row for row in small_data["ordinary_provider_api_rows"]}
        self.assertEqual(list(api_rows), expected_apis)
        for api, api_row in api_rows.items():
            self.assertEqual(api_row["replay_status"], "post_task_ledger_replayed")
            self.assertIn(f"Tushare {api} ledger", api_row["ordinary_label"])
            self.assertEqual(api_row["row_count"], 3)
            self.assertRegex(api_row["data_date"], r"^\d{8}$")
            self.assertEqual(api_row["call_status"], "success")
            self.assertEqual(api_row["readback_source"], "cache / call_ledger / packet")
            self.assertIn("不补调 provider/model", api_row["boundary"])
            self.assertFalse(api_row["external_calls_triggered"])
            self.assertFalse(api_row["tushare_called"])
            self.assertFalse(api_row["deepseek_called"])
            self.assertFalse(api_row["github_called"])
            self.assertFalse(api_row["contains_secret"])
            self.assertTrue(api_row["does_not_execute_trades"])
            self.assertTrue(api_row["does_not_modify_strategy_action"])
        self.assertIn("GET cache 和 React render 不补调 provider/model", small_data["ordinary_readback_boundary"])
        self.assertEqual(small_data["ordinary_readback_surfaces_label"], "cache / call_ledger / packet")
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
        self.assertEqual(interpretation["ordinary_result_readback_row_count"], 4)
        self.assertTrue(interpretation["ordinary_result_readback_rows_are_cache_only"])
        self.assertFalse(interpretation["ordinary_result_readback_rows_create_task"])
        self.assertFalse(interpretation["ordinary_result_readback_rows_use_model_output"])
        self.assertTrue(interpretation["ordinary_result_readback_rows_are_not_trade_signals"])
        self.assertEqual(interpretation["ordinary_result_handoff_row_count"], 4)
        self.assertTrue(interpretation["ordinary_result_handoff_rows_are_cache_only"])
        self.assertFalse(interpretation["ordinary_result_handoff_rows_create_task"])
        self.assertFalse(interpretation["ordinary_result_handoff_rows_use_model_output"])
        self.assertTrue(interpretation["ordinary_result_handoff_rows_are_not_trade_signals"])
        self.assertEqual(interpretation["ordinary_deepseek_governed_executor_checklist_row_count"], 5)
        self.assertTrue(interpretation["ordinary_deepseek_governed_executor_checklist_rows_are_cache_only"])
        self.assertFalse(interpretation["ordinary_deepseek_governed_executor_checklist_rows_create_task"])
        self.assertFalse(interpretation["ordinary_deepseek_governed_executor_checklist_rows_call_model"])
        self.assertFalse(interpretation["ordinary_deepseek_governed_executor_checklist_rows_use_model_output"])
        self.assertTrue(interpretation["ordinary_deepseek_governed_executor_checklist_rows_are_not_trade_signals"])
        self.assertEqual(packet["counts"]["search_quant_projection_interpretation_handoff_row_count"], 4)
        self.assertEqual(packet["counts"]["search_quant_projection_deepseek_governed_executor_checklist_row_count"], 5)
        self.assertEqual(packet["counts"]["search_quant_projection_deepseek_governed_executor_readiness_row_count"], 6)
        self.assertTrue(packet["policy"]["search_quant_projection_interpretation_handoff_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_interpretation_handoff_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_interpretation_handoff_rows_use_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_interpretation_handoff_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["search_quant_projection_deepseek_governed_executor_checklist_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_deepseek_governed_executor_checklist_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_deepseek_governed_executor_checklist_rows_call_model"])
        self.assertFalse(packet["policy"]["search_quant_projection_deepseek_governed_executor_checklist_rows_use_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_deepseek_governed_executor_checklist_rows_are_not_trade_signals"])
        checklist_rows = {
            row["check_key"]: row
            for row in interpretation["ordinary_deepseek_governed_executor_checklist_rows"]
        }
        self.assertIn("output_acceptance", checklist_rows)
        self.assertIn("output acceptance", checklist_rows["output_acceptance"]["检查项"])
        self.assertFalse(checklist_rows["output_acceptance"]["calls_model_from_readback"])
        self.assertFalse(checklist_rows["output_acceptance"]["uses_model_output"])
        self.assertTrue(checklist_rows["output_acceptance"]["does_not_modify_strategy_action"])
        self.assertTrue(packet["policy"]["search_quant_projection_deepseek_governed_executor_readiness_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_deepseek_governed_executor_readiness_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_deepseek_governed_executor_readiness_rows_call_model"])
        self.assertFalse(packet["policy"]["search_quant_projection_deepseek_governed_executor_readiness_rows_use_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_deepseek_governed_executor_readiness_rows_are_not_trade_signals"])
        readiness_rows = {
            row["readiness_key"]: row
            for row in interpretation["ordinary_deepseek_governed_executor_readiness_rows"]
        }
        self.assertIn("output_acceptance_gate", readiness_rows)
        self.assertIn("output acceptance", readiness_rows["output_acceptance_gate"]["检查项"])
        self.assertFalse(readiness_rows["output_acceptance_gate"]["calls_model_from_readback"])
        self.assertFalse(readiness_rows["output_acceptance_gate"]["uses_model_output"])
        self.assertTrue(readiness_rows["output_acceptance_gate"]["does_not_modify_strategy_action"])
        self.assertEqual(packet["counts"]["search_quant_projection_deepseek_governed_executor_contract_row_count"], 5)
        self.assertTrue(packet["policy"]["search_quant_projection_deepseek_governed_executor_contract_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_deepseek_governed_executor_contract_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_deepseek_governed_executor_contract_rows_call_model"])
        self.assertTrue(packet["policy"]["search_quant_projection_deepseek_governed_executor_contract_rows_are_not_trade_signals"])
        deepseek_contract = interpretation["ordinary_deepseek_governed_executor_contract"]
        self.assertEqual(
            deepseek_contract["schema_version"],
            "candidate_radar_search_quant_projection_deepseek_governed_executor_contract.v1",
        )
        self.assertEqual(deepseek_contract["status"], "waiting_p5_governed_executor_task")
        self.assertFalse(deepseek_contract["task_route_implemented"])
        self.assertFalse(deepseek_contract["blocks_p1_p2_p3"])
        self.assertTrue(deepseek_contract["model_ledger_required"])
        self.assertTrue(deepseek_contract["sanitizer_required"])
        self.assertFalse(deepseek_contract["deepseek_real_call_allowed_now"])
        self.assertFalse(deepseek_contract["deepseek_called"])
        self.assertFalse(deepseek_contract["contains_secret"])
        self.assertFalse(deepseek_contract["production_deepseek_complete"])
        contract_rows = {
            row["contract_key"]: row
            for row in interpretation["ordinary_deepseek_governed_executor_contract_rows"]
        }
        self.assertEqual(
            set(contract_rows),
            {
                "standalone_p5_task",
                "ledger_and_sanitizer",
                "safe_output_scope",
                "output_acceptance_gate",
                "nonblocking_fallback",
            },
        )
        self.assertIn("未来单独 P5 governed executor task", contract_rows["standalone_p5_task"]["当前状态"])
        self.assertIn("model_ledger", contract_rows["ledger_and_sanitizer"]["合同项"])
        self.assertIn("source/gap/next_step/safety_summary", contract_rows["safe_output_scope"]["证据"])
        self.assertIn("output acceptance", contract_rows["output_acceptance_gate"]["合同项"])
        self.assertFalse(contract_rows["output_acceptance_gate"]["creates_task_from_readback"])
        self.assertFalse(contract_rows["output_acceptance_gate"]["calls_model_from_readback"])
        self.assertFalse(contract_rows["nonblocking_fallback"]["blocks_p1_p2_p3"])
        for contract_row in contract_rows.values():
            self.assertTrue(contract_row["cache_only_readback"])
            self.assertFalse(contract_row["creates_task_from_readback"])
            self.assertFalse(contract_row["calls_model_from_readback"])
            self.assertFalse(contract_row["deepseek_called"])
            self.assertFalse(contract_row["uses_model_output"])
            self.assertFalse(contract_row["contains_secret"])
            self.assertFalse(contract_row["blocks_p1_p2_p3"])
            self.assertTrue(contract_row["does_not_execute_trades"])
            self.assertTrue(contract_row["does_not_modify_strategy_action"])
            self.assertTrue(contract_row["candidate_is_not_buy_instruction"])
            self.assertFalse(contract_row["production_deepseek_complete"])
        result_checkpoint = interpretation["ordinary_result_checkpoint_contract"]
        self.assertEqual(packet["search_quant_projection_result_checkpoint"], result_checkpoint)
        self.assertEqual(
            packet["search_quant_projection_result_checkpoint_rows"],
            interpretation["ordinary_result_checkpoint_rows"],
        )
        self.assertEqual(
            result_checkpoint["schema_version"],
            "candidate_radar_search_quant_projection_result_checkpoint.v1",
        )
        self.assertEqual(result_checkpoint["status"], "ready_pending_local_map")
        self.assertEqual(result_checkpoint["readback_route"], "GET /api/candidate-radar/cache")
        self.assertEqual(result_checkpoint["source_packet_key"], "command_center_3_candidate_radar_cache")
        self.assertIn(response["data"]["task_id"], result_checkpoint["source_task_id"])
        self.assertTrue(result_checkpoint["ordinary_result_readable"])
        self.assertTrue(result_checkpoint["provider_data_source_verified"])
        self.assertFalse(result_checkpoint["blocker_explanation_visible"])
        self.assertEqual(result_checkpoint["data_source_state"], "tushare_first_ledger_ready")
        self.assertEqual(result_checkpoint["evidence_source"], "Tushare-first ledger")
        self.assertEqual(result_checkpoint["next_session_map_state"], "pending_local_cache_refresh")
        self.assertEqual(result_checkpoint["missing_evidence"], ["Factor/Next/ECharts local cache replay"])
        self.assertEqual(result_checkpoint["missing_evidence_count"], 1)
        self.assertEqual(result_checkpoint["safe_explanation_fields"], ["source", "gap", "next_step", "safety_summary"])
        self.assertEqual(
            result_checkpoint["deepseek_state"],
            "skipped_by_tushare_first_request_waiting_governed_executor",
        )
        self.assertTrue(result_checkpoint["uses_tushare_ledger"])
        self.assertFalse(result_checkpoint["uses_deepseek_output"])
        self.assertFalse(result_checkpoint["uses_model_output"])
        self.assertTrue(result_checkpoint["cache_only_readback"])
        self.assertFalse(result_checkpoint["creates_task_from_readback"])
        self.assertFalse(result_checkpoint["calls_model_from_readback"])
        self.assertFalse(result_checkpoint["readback_external_calls_triggered"])
        self.assertTrue(result_checkpoint["does_not_execute_trades"])
        self.assertTrue(result_checkpoint["does_not_modify_strategy_action"])
        self.assertFalse(result_checkpoint["production_quant_projection_complete"])
        self.assertTrue(interpretation["ordinary_result_checkpoint_is_cache_only"])
        self.assertFalse(interpretation["ordinary_result_checkpoint_creates_task"])
        self.assertFalse(interpretation["ordinary_result_checkpoint_calls_model"])
        self.assertTrue(interpretation["ordinary_result_checkpoint_is_not_trade_signal"])
        self.assertEqual(packet["counts"]["search_quant_projection_result_checkpoint_missing_evidence_count"], 1)
        self.assertTrue(packet["counts"]["search_quant_projection_result_checkpoint_readable"])
        self.assertEqual(packet["counts"]["search_quant_projection_result_checkpoint_row_count"], 4)
        self.assertTrue(packet["policy"]["search_quant_projection_result_checkpoint_is_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_result_checkpoint_creates_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_result_checkpoint_calls_model"])
        self.assertTrue(packet["policy"]["search_quant_projection_result_checkpoint_is_not_trade_signal"])
        self.assertTrue(packet["policy"]["search_quant_projection_result_checkpoint_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_result_checkpoint_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_result_checkpoint_rows_call_model"])
        self.assertTrue(packet["policy"]["search_quant_projection_result_checkpoint_rows_are_not_trade_signals"])
        checkpoint_rows = {
            row["checkpoint_key"]: row
            for row in interpretation["ordinary_result_checkpoint_rows"]
        }
        self.assertEqual(
            set(checkpoint_rows),
            {"readable_result", "data_source", "gap_and_next_step", "safety_boundary"},
        )
        self.assertIn("可读结论", checkpoint_rows["readable_result"]["检查点"])
        self.assertIn("Tushare-first", checkpoint_rows["data_source"]["当前状态"])
        self.assertIn("missing_evidence_count=1", checkpoint_rows["gap_and_next_step"]["证据"])
        self.assertIn("safe_explanation_fields=source/gap/next_step/safety_summary", checkpoint_rows["safety_boundary"]["证据"])
        for checkpoint_row in checkpoint_rows.values():
            self.assertTrue(checkpoint_row["cache_only_readback"])
            self.assertFalse(checkpoint_row["creates_task_from_readback"])
            self.assertFalse(checkpoint_row["calls_model_from_readback"])
            self.assertFalse(checkpoint_row["uses_deepseek_output"])
            self.assertFalse(checkpoint_row["contains_secret"])
            self.assertTrue(checkpoint_row["does_not_execute_trades"])
            self.assertTrue(checkpoint_row["does_not_modify_strategy_action"])
            self.assertTrue(checkpoint_row["candidate_is_not_buy_instruction"])
            self.assertFalse(checkpoint_row["production_quant_projection_complete"])
        self.assertEqual(interpretation["ordinary_result_action_row_count"], 4)
        self.assertTrue(interpretation["ordinary_result_action_rows_are_cache_only"])
        self.assertFalse(interpretation["ordinary_result_action_rows_create_task"])
        self.assertFalse(interpretation["ordinary_result_action_rows_use_model_output"])
        self.assertTrue(interpretation["ordinary_result_action_rows_are_not_trade_signals"])
        self.assertEqual(packet["counts"]["search_quant_projection_interpretation_action_row_count"], 4)
        self.assertFalse(packet["policy"]["search_quant_projection_interpretation_action_rows_create_task"])
        self.assertTrue(packet["policy"]["search_quant_projection_interpretation_action_rows_are_cache_only"])
        result_rows = {row["surface"]: row for row in interpretation["ordinary_result_readback_rows"]}
        self.assertEqual(
            set(result_rows),
            {"data_source", "quant_projection", "next_session_map", "research_only_boundary"},
        )
        self.assertEqual(result_rows["data_source"]["status"], "tushare_first_ledger_ready")
        self.assertIn("Tushare-first 账本已回放 4/4", result_rows["data_source"]["ordinary_label"])
        self.assertEqual(result_rows["quant_projection"]["status"], "readable_summary")
        self.assertEqual(result_rows["next_session_map"]["status"], "pending_local_cache_refresh")
        self.assertIn("Next Session 图谱仍等待本地 cache 刷新", result_rows["next_session_map"]["ordinary_label"])
        self.assertEqual(result_rows["research_only_boundary"]["status"], "research_only_safe")
        for result_row in result_rows.values():
            self.assertFalse(result_row["external_calls_triggered"])
            self.assertFalse(result_row["uses_deepseek_output"])
            self.assertFalse(result_row["model_output_used"])
            self.assertFalse(result_row["contains_secret"])
            self.assertTrue(result_row["does_not_execute_trades"])
            self.assertTrue(result_row["does_not_modify_strategy_action"])
            self.assertTrue(result_row["candidate_is_not_buy_instruction"])
        handoff_rows = {row["handoff_key"]: row for row in interpretation["ordinary_result_handoff_rows"]}
        self.assertEqual(
            set(handoff_rows),
            {"readable_conclusion", "replay_quant_projection", "replay_next_session_map", "return_candidate_pool"},
        )
        self.assertIn(response["data"]["task_id"], handoff_rows["readable_conclusion"]["来源任务"])
        self.assertEqual(handoff_rows["replay_quant_projection"]["href"], "#factor")
        self.assertEqual(handoff_rows["replay_next_session_map"]["href"], "#next")
        self.assertEqual(handoff_rows["return_candidate_pool"]["href"], "#candidate-pool")
        self.assertIn("pending_local_cache_refresh", handoff_rows["replay_next_session_map"]["当前状态"])
        self.assertIn("不发 POST task", handoff_rows["replay_quant_projection"]["边界"])
        self.assertIn("不生成交易动作", handoff_rows["replay_next_session_map"]["边界"])
        self.assertIn("候选不是买入指令", handoff_rows["return_candidate_pool"]["用户下一步"])
        for handoff_row in handoff_rows.values():
            self.assertTrue(handoff_row["cache_only_readback"])
            self.assertFalse(handoff_row["creates_task_from_readback"])
            self.assertFalse(handoff_row["external_calls_triggered"])
            self.assertFalse(handoff_row["uses_deepseek_output"])
            self.assertFalse(handoff_row["model_output_used"])
            self.assertFalse(handoff_row["contains_secret"])
            self.assertTrue(handoff_row["does_not_execute_trades"])
            self.assertTrue(handoff_row["does_not_modify_strategy_action"])
            self.assertTrue(handoff_row["candidate_is_not_buy_instruction"])
        action_rows = {row["action_key"]: row for row in interpretation["ordinary_result_action_rows"]}
        self.assertEqual(
            set(action_rows),
            {
                "read_interpretable_conclusion",
                "replay_quant_projection",
                "replay_next_session_map",
                "keep_research_only_boundary",
            },
        )
        self.assertIn("读可读结论", action_rows["read_interpretable_conclusion"]["行动"])
        self.assertIn("回放量化推演", action_rows["replay_quant_projection"]["行动"])
        self.assertIn("等待本地 cache 刷新", action_rows["replay_next_session_map"]["当前状态"])
        self.assertIn("不当买入或卖出指令", action_rows["keep_research_only_boundary"]["用户下一步"])
        for action_row in action_rows.values():
            self.assertTrue(action_row["cache_only_readback"])
            self.assertFalse(action_row["creates_task_from_readback"])
            self.assertFalse(action_row["external_calls_triggered"])
            self.assertFalse(action_row["uses_deepseek_output"])
            self.assertFalse(action_row["model_output_used"])
            self.assertFalse(action_row["contains_secret"])
            self.assertTrue(action_row["does_not_execute_trades"])
            self.assertTrue(action_row["does_not_modify_strategy_action"])
            self.assertTrue(action_row["candidate_is_not_buy_instruction"])
        checklist_rows = {row["check_key"]: row for row in interpretation["ordinary_deepseek_governed_executor_checklist_rows"]}
        self.assertEqual(
            set(checklist_rows),
            {"model_ledger_gate", "sanitizer_redaction", "safe_fallback", "output_acceptance", "no_override"},
        )
        self.assertIn("待 P5 governed executor 写入 model_ledger", checklist_rows["model_ledger_gate"]["当前状态"])
        self.assertIn("字段白名单", checklist_rows["sanitizer_redaction"]["当前状态"])
        self.assertIn("pending/skipped", checklist_rows["safe_fallback"]["当前状态"])
        self.assertIn("普通页前必须先通过 output acceptance", checklist_rows["output_acceptance"]["当前状态"])
        self.assertIn("不能覆盖价格、持仓、factor、operation_zones 或 strategy action", checklist_rows["no_override"]["当前状态"])
        for checklist_row in checklist_rows.values():
            self.assertTrue(checklist_row["cache_only_readback"])
            self.assertFalse(checklist_row["creates_task_from_readback"])
            self.assertFalse(checklist_row["calls_model_from_readback"])
            self.assertFalse(checklist_row["uses_model_output"])
            self.assertFalse(checklist_row["contains_secret"])
            self.assertTrue(checklist_row["does_not_execute_trades"])
            self.assertTrue(checklist_row["does_not_modify_strategy_action"])
            self.assertTrue(checklist_row["candidate_is_not_buy_instruction"])
        self.assertEqual(interpretation["ordinary_deepseek_governed_executor_readiness_row_count"], 6)
        self.assertTrue(interpretation["ordinary_deepseek_governed_executor_readiness_rows_are_cache_only"])
        self.assertFalse(interpretation["ordinary_deepseek_governed_executor_readiness_rows_create_task"])
        self.assertFalse(interpretation["ordinary_deepseek_governed_executor_readiness_rows_call_model"])
        self.assertFalse(interpretation["ordinary_deepseek_governed_executor_readiness_rows_use_model_output"])
        self.assertTrue(interpretation["ordinary_deepseek_governed_executor_readiness_rows_are_not_trade_signals"])
        readiness_rows = {
            row["readiness_key"]: row
            for row in interpretation["ordinary_deepseek_governed_executor_readiness_rows"]
        }
        self.assertEqual(
            set(readiness_rows),
            {
                "explicit_p5_task_gate",
                "model_ledger_writeback",
                "sanitized_allowed_fields",
                "nonblocking_fallback",
                "output_acceptance_gate",
                "promotion_boundary",
            },
        )
        self.assertEqual(readiness_rows["explicit_p5_task_gate"]["可执行状态"], "not_ready_no_p5_task")
        self.assertIn("绝不真实调用 DeepSeek", readiness_rows["explicit_p5_task_gate"]["边界"])
        self.assertIn("普通页不得展示模型输出", readiness_rows["model_ledger_writeback"]["当前状态"])
        self.assertIn("source,gap,next_step,safety_summary", readiness_rows["sanitized_allowed_fields"]["证据"])
        self.assertIn("不得自动重试外联", readiness_rows["nonblocking_fallback"]["边界"])
        self.assertIn("output acceptance", readiness_rows["output_acceptance_gate"]["检查项"])
        self.assertIn("不是生产 DeepSeek 验收完成", readiness_rows["promotion_boundary"]["当前状态"])
        for readiness_row in readiness_rows.values():
            self.assertTrue(readiness_row["cache_only_readback"])
            self.assertFalse(readiness_row["creates_task_from_readback"])
            self.assertFalse(readiness_row["calls_model_from_readback"])
            self.assertFalse(readiness_row["external_calls_triggered"])
            self.assertFalse(readiness_row["deepseek_called"])
            self.assertFalse(readiness_row["uses_model_output"])
            self.assertFalse(readiness_row["model_output_used"])
            self.assertFalse(readiness_row["contains_secret"])
            self.assertTrue(readiness_row["does_not_execute_trades"])
            self.assertTrue(readiness_row["does_not_modify_strategy_action"])
            self.assertTrue(readiness_row["does_not_modify_prices"])
            self.assertTrue(readiness_row["candidate_is_not_buy_instruction"])
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
        self.assertEqual(small_data["ordinary_readback_status"], "blocked_missing_credentials")
        self.assertIn("小数据已写入本地阻断", small_data["ordinary_readback_summary"])
        self.assertIn("缺少服务端 Tushare 凭据", small_data["ordinary_readback_summary"])
        self.assertEqual(small_data["ordinary_readback_row_count"], 3)
        self.assertTrue(small_data["ordinary_readback_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_readback_rows_create_task"])
        self.assertEqual(small_data["ordinary_task_readback_row_count"], 3)
        self.assertTrue(small_data["ordinary_task_readback_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_task_readback_rows_create_task"])
        self.assertEqual(small_data["ordinary_post_confirm_action_row_count"], 4)
        self.assertTrue(small_data["ordinary_post_confirm_action_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_post_confirm_action_rows_create_task"])
        self.assertEqual(small_data["ordinary_confirm_replay_stage_row_count"], 4)
        self.assertTrue(small_data["ordinary_confirm_replay_stage_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_confirm_replay_stage_rows_create_task"])
        self.assertFalse(small_data["ordinary_confirm_replay_stage_rows_use_model_output"])
        self.assertEqual(small_data["ordinary_provider_api_row_count"], 4)
        self.assertTrue(small_data["ordinary_provider_api_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_provider_api_rows_create_task"])
        self.assertEqual(small_data["ordinary_writeback_action_row_count"], 4)
        self.assertTrue(small_data["ordinary_writeback_action_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_writeback_action_rows_create_task"])
        self.assertEqual(small_data["ordinary_one_screen_action_row_count"], 4)
        self.assertTrue(small_data["ordinary_one_screen_action_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_one_screen_action_rows_create_task"])
        self.assertFalse(small_data["ordinary_one_screen_action_rows_call_provider_from_readback"])
        self.assertFalse(small_data["ordinary_one_screen_action_rows_use_model_output"])
        self.assertTrue(small_data["ordinary_one_screen_action_rows_are_not_trade_signals"])
        self.assertEqual(small_data["ordinary_writeback_integrity_row_count"], 3)
        self.assertTrue(small_data["ordinary_writeback_integrity_rows_are_cache_only"])
        self.assertFalse(small_data["ordinary_writeback_integrity_rows_create_task"])
        writeback_checkpoint = small_data["ordinary_writeback_checkpoint_contract"]
        self.assertEqual(
            writeback_checkpoint["schema_version"],
            "candidate_radar_search_quant_projection_writeback_checkpoint.v1",
        )
        self.assertEqual(writeback_checkpoint["surfaces"], ["cache", "call_ledger", "packet"])
        self.assertEqual(writeback_checkpoint["readback_route"], "GET /api/candidate-radar/cache")
        self.assertEqual(writeback_checkpoint["readable_surface_count"], 3)
        self.assertEqual(writeback_checkpoint["complete_surface_count"], 2)
        self.assertTrue(writeback_checkpoint["cache_written"])
        self.assertEqual(writeback_checkpoint["call_ledger_state"], "local_blocker_ledger_written")
        self.assertFalse(writeback_checkpoint["provider_ledger_ready"])
        self.assertTrue(writeback_checkpoint["packet_written"])
        self.assertTrue(writeback_checkpoint["cache_only_readback"])
        self.assertFalse(writeback_checkpoint["creates_task_from_readback"])
        self.assertFalse(writeback_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(writeback_checkpoint["deepseek_called_from_readback"])
        self.assertFalse(writeback_checkpoint["production_quant_projection_complete"])
        self.assertEqual(packet["search_quant_projection_writeback_checkpoint"], writeback_checkpoint)
        small_data_checkpoint = packet["search_quant_projection_small_data_readback_checkpoint"]
        self.assertEqual(
            small_data_checkpoint["schema_version"],
            "candidate_radar_search_quant_projection_small_data_readback_checkpoint.v1",
        )
        self.assertEqual(small_data_checkpoint["status"], small_data["status"])
        self.assertFalse(small_data_checkpoint["ready"])
        self.assertEqual(small_data_checkpoint["writeback_surfaces"], ["cache", "call_ledger", "packet"])
        self.assertEqual(small_data_checkpoint["call_ledger_state"], writeback_checkpoint.get("call_ledger_state"))
        self.assertEqual(small_data_checkpoint["readable_surface_count"], 3)
        self.assertEqual(small_data_checkpoint["complete_surface_count"], 2)
        self.assertTrue(small_data_checkpoint["cache_only_readback"])
        self.assertFalse(small_data_checkpoint["creates_task_from_readback"])
        self.assertFalse(small_data_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(small_data_checkpoint["uses_deepseek_output"])
        self.assertTrue(small_data_checkpoint["does_not_execute_trades"])
        self.assertTrue(small_data_checkpoint["does_not_modify_strategy_action"])
        self.assertFalse(packet["search_quant_projection_small_data_writeback_ready"])
        self.assertEqual(packet["search_quant_projection_small_data_writeback_status"], small_data["status"])
        self.assertEqual(packet["search_quant_projection_writeback_surfaces"], ["cache", "call_ledger", "packet"])
        readback_rows = {row["surface"]: row for row in small_data["ordinary_readback_rows"]}
        self.assertEqual(readback_rows["cache"]["status"], "written")
        self.assertEqual(readback_rows["call_ledger"]["status"], "not_called_missing_credentials_local_block")
        self.assertIn("本地阻断 ledger 已写入", readback_rows["call_ledger"]["ordinary_label"])
        self.assertEqual(readback_rows["packet"]["status"], "written")
        for readback_row in readback_rows.values():
            self.assertFalse(readback_row["external_calls_triggered"])
            self.assertFalse(readback_row["tushare_called"])
            self.assertFalse(readback_row["deepseek_called"])
            self.assertFalse(readback_row["github_called"])
            self.assertFalse(readback_row["contains_secret"])
        task_rows = {row["surface"]: row for row in small_data["ordinary_task_readback_rows"]}
        self.assertEqual(set(task_rows), {"task_id", "current_step", "task_status_panel"})
        self.assertEqual(task_rows["task_id"]["status"], "written")
        self.assertIn(task["task_id"], task_rows["task_id"]["ordinary_label"])
        self.assertIn(
            "candidate_radar_quant_projection_tushare_first_chain_blocked_missing_credentials",
            task_rows["current_step"]["ordinary_label"],
        )
        self.assertEqual(task_rows["task_status_panel"]["status"], "poll_ready")
        for task_row in task_rows.values():
            self.assertFalse(task_row["external_calls_triggered"])
            self.assertFalse(task_row["tushare_called"])
            self.assertFalse(task_row["deepseek_called"])
            self.assertFalse(task_row["github_called"])
            self.assertFalse(task_row["contains_secret"])
        post_confirm_rows = {row["action_key"]: row for row in small_data["ordinary_post_confirm_action_rows"]}
        self.assertIn(task["task_id"], post_confirm_rows["check_task_id"]["当前状态"])
        self.assertEqual(post_confirm_rows["poll_task_status"]["当前状态"], "TaskStatusPanel 可轮询本地 FastAPI")
        self.assertIn("缺少服务端 Tushare 凭据", post_confirm_rows["replay_results"]["当前状态"])
        self.assertIn("不要从 GET cache 或链接期待自动补数", post_confirm_rows["replay_results"]["用户下一步"])
        for action_row in post_confirm_rows.values():
            self.assertTrue(action_row["cache_only_readback"])
            self.assertFalse(action_row["creates_task_from_readback"])
            self.assertFalse(action_row["external_calls_triggered"])
            self.assertFalse(action_row["tushare_called"])
            self.assertFalse(action_row["deepseek_called"])
            self.assertFalse(action_row["github_called"])
            self.assertFalse(action_row["contains_secret"])
        stage_rows = {row["stage_key"]: row for row in small_data["ordinary_confirm_replay_stage_rows"]}
        self.assertIn("P2 blocked", stage_rows["current_confirm_replay_stage"]["当前状态"])
        self.assertIn("缺少服务端 Tushare 凭据", stage_rows["current_confirm_replay_stage"]["当前状态"])
        self.assertIn("local_block_replayed_missing_tushare_credentials", stage_rows["current_confirm_replay_stage"]["证据"])
        for stage_row in stage_rows.values():
            self.assertTrue(stage_row["cache_only_readback"])
            self.assertFalse(stage_row["creates_task_from_readback"])
            self.assertFalse(stage_row["uses_model_output"])
            self.assertFalse(stage_row["external_calls_triggered"])
            self.assertFalse(stage_row["tushare_called"])
            self.assertFalse(stage_row["deepseek_called"])
            self.assertFalse(stage_row["github_called"])
            self.assertFalse(stage_row["contains_secret"])
        writeback_action_rows = {row["action_key"]: row for row in small_data["ordinary_writeback_action_rows"]}
        self.assertIn("缺少服务端 Tushare 凭据", writeback_action_rows["review_call_ledger"]["当前状态"])
        self.assertIn("配置服务端凭据后重新点击确认", writeback_action_rows["review_call_ledger"]["用户下一步"])
        self.assertIn("本地阻断", writeback_action_rows["check_writeback_status"]["当前状态"])
        for action_row in writeback_action_rows.values():
            self.assertTrue(action_row["cache_only_readback"])
            self.assertFalse(action_row["creates_task_from_readback"])
            self.assertFalse(action_row["external_calls_triggered"])
            self.assertFalse(action_row["tushare_called"])
            self.assertFalse(action_row["deepseek_called"])
            self.assertFalse(action_row["github_called"])
            self.assertFalse(action_row["contains_secret"])
        one_screen_rows = {row["action_key"]: row for row in small_data["ordinary_one_screen_action_rows"]}
        self.assertEqual(set(one_screen_rows), {"confirm", "task", "writeback", "result"})
        self.assertIn("缺少服务端 Tushare 凭据", one_screen_rows["confirm"]["当前状态"])
        self.assertIn("TaskStatusPanel", one_screen_rows["task"]["入口"])
        self.assertIn("本地阻断", one_screen_rows["writeback"]["当前状态"])
        self.assertIn("只显示阻断原因", one_screen_rows["result"]["当前状态"])
        self.assertIn("不调用 DeepSeek", one_screen_rows["result"]["边界"])
        for one_screen_row in one_screen_rows.values():
            self.assertTrue(one_screen_row["cache_only_readback"])
            self.assertFalse(one_screen_row["creates_task_from_readback"])
            self.assertFalse(one_screen_row["readback_external_calls_triggered"])
            self.assertFalse(one_screen_row["readback_calls_provider"])
            self.assertFalse(one_screen_row["uses_model_output"])
            self.assertFalse(one_screen_row["external_calls_triggered"])
            self.assertFalse(one_screen_row["tushare_called"])
            self.assertFalse(one_screen_row["deepseek_called"])
            self.assertFalse(one_screen_row["github_called"])
            self.assertFalse(one_screen_row["contains_secret"])
            self.assertTrue(one_screen_row["does_not_execute_trades"])
            self.assertTrue(one_screen_row["does_not_modify_strategy_action"])
            self.assertTrue(one_screen_row["candidate_is_not_buy_instruction"])
        destination_rows = {row["destination"]: row for row in small_data["ordinary_replay_destination_rows"]}
        self.assertEqual(set(destination_rows), {"stock_quant_projection", "next_session_map", "candidate_pool"})
        next_destination = destination_rows["next_session_map"]
        self.assertEqual(next_destination["P3状态"], "blocked_missing_credentials")
        self.assertIn("来源=本地阻断或任务状态", next_destination["可解释结果"])
        self.assertIn("缺口=服务端 Tushare 凭据或 provider ledger", next_destination["可解释结果"])
        self.assertIn("显示阻断原因和下一步", next_destination["缺口处理"])
        self.assertIn("不从 GET cache 或 React render 重试外联", next_destination["缺口处理"])
        self.assertIn("不覆盖 strategy action、不下单", next_destination["operation_zones边界"])
        self.assertTrue(next_destination["cache_only_readback"])
        self.assertFalse(next_destination["creates_task_from_readback"])
        self.assertFalse(next_destination["external_calls_triggered"])
        self.assertFalse(next_destination["tushare_called"])
        self.assertFalse(next_destination["deepseek_called"])
        self.assertFalse(next_destination["github_called"])
        self.assertFalse(next_destination["contains_secret"])
        self.assertTrue(next_destination["does_not_execute_trades"])
        self.assertTrue(next_destination["does_not_modify_strategy_action"])
        self.assertTrue(next_destination["candidate_is_not_buy_instruction"])
        integrity_rows = {row["integrity_key"]: row for row in small_data["ordinary_writeback_integrity_rows"]}
        self.assertEqual(integrity_rows["cache_written"]["是否齐备"], "ready")
        self.assertEqual(integrity_rows["call_ledger_written"]["是否齐备"], "blocked_local_ledger_replayed")
        self.assertEqual(integrity_rows["packet_written"]["是否齐备"], "ready")
        self.assertIn("缺少服务端 Tushare 凭据", integrity_rows["call_ledger_written"]["当前状态"])
        self.assertIn("GET cache 和 React render 不调用 Tushare", integrity_rows["call_ledger_written"]["边界"])
        for integrity_row in integrity_rows.values():
            self.assertTrue(integrity_row["cache_only_readback"])
            self.assertFalse(integrity_row["creates_task_from_readback"])
            self.assertFalse(integrity_row["external_calls_triggered"])
            self.assertFalse(integrity_row["tushare_called"])
            self.assertFalse(integrity_row["deepseek_called"])
            self.assertFalse(integrity_row["github_called"])
            self.assertFalse(integrity_row["contains_secret"])
        api_rows = {row["api"]: row for row in small_data["ordinary_provider_api_rows"]}
        self.assertEqual(set(api_rows), {"trade_cal", "daily", "daily_basic", "moneyflow"})
        for api, api_row in api_rows.items():
            self.assertEqual(api_row["replay_status"], "local_block_replayed")
            self.assertIn(f"Tushare {api} 未调用", api_row["ordinary_label"])
            self.assertEqual(api_row["row_count"], 0)
            self.assertEqual(api_row["call_status"], "blocked_missing_credentials")
            self.assertEqual(api_row["readback_source"], "cache / call_ledger / packet")
            self.assertFalse(api_row["external_calls_triggered"])
            self.assertFalse(api_row["tushare_called"])
            self.assertFalse(api_row["deepseek_called"])
            self.assertFalse(api_row["github_called"])
            self.assertFalse(api_row["contains_secret"])
        self.assertIn("GET cache 和 React render 仍保持只读", small_data["ordinary_readback_next_step"])
        self.assertIn("不补调 provider/model", small_data["ordinary_readback_boundary"])
        self.assertFalse(small_data["cache_get_external_calls"])
        self.assertFalse(small_data["external_calls_triggered"])
        self.assertEqual(interpretation["status"], "interpretation_blocked_missing_tushare_credentials")
        self.assertIn("服务端 Tushare 凭据缺失", interpretation["summary_label"])
        self.assertEqual(interpretation["ordinary_result_status"], "blocked_missing_credentials")
        self.assertIn("还没有真实 provider 账本", interpretation["ordinary_result_summary"])
        self.assertIn("配置服务端凭据后重新点击确认", interpretation["ordinary_result_next_step"])
        self.assertIn("不调用 DeepSeek", interpretation["ordinary_result_boundary"])
        self.assertIn("DeepSeek 未参与", interpretation["ordinary_result_evidence"])
        self.assertEqual(interpretation["ordinary_result_readback_row_count"], 4)
        self.assertTrue(interpretation["ordinary_result_readback_rows_are_cache_only"])
        self.assertFalse(interpretation["ordinary_result_readback_rows_create_task"])
        self.assertFalse(interpretation["ordinary_result_readback_rows_use_model_output"])
        self.assertTrue(interpretation["ordinary_result_readback_rows_are_not_trade_signals"])
        self.assertEqual(interpretation["ordinary_result_action_row_count"], 4)
        self.assertTrue(interpretation["ordinary_result_action_rows_are_cache_only"])
        self.assertFalse(interpretation["ordinary_result_action_rows_create_task"])
        self.assertFalse(interpretation["ordinary_result_action_rows_use_model_output"])
        self.assertTrue(interpretation["ordinary_result_action_rows_are_not_trade_signals"])
        result_checkpoint = interpretation["ordinary_result_checkpoint_contract"]
        self.assertEqual(packet["search_quant_projection_result_checkpoint"], result_checkpoint)
        self.assertEqual(
            packet["search_quant_projection_result_checkpoint_rows"],
            interpretation["ordinary_result_checkpoint_rows"],
        )
        self.assertEqual(
            result_checkpoint["schema_version"],
            "candidate_radar_search_quant_projection_result_checkpoint.v1",
        )
        self.assertEqual(result_checkpoint["status"], "blocked_missing_credentials")
        self.assertTrue(result_checkpoint["ordinary_result_readable"])
        self.assertFalse(result_checkpoint["provider_data_source_verified"])
        self.assertTrue(result_checkpoint["blocker_explanation_visible"])
        self.assertEqual(result_checkpoint["data_source_state"], "blocked_missing_credentials")
        self.assertEqual(result_checkpoint["evidence_source"], "local_blocker_or_task_status")
        self.assertIn("Tushare-first provider ledger", result_checkpoint["missing_evidence"])
        self.assertIn("Factor/Next/ECharts local cache replay", result_checkpoint["missing_evidence"])
        self.assertGreaterEqual(result_checkpoint["missing_evidence_count"], 2)
        self.assertFalse(result_checkpoint["uses_tushare_ledger"])
        self.assertFalse(result_checkpoint["uses_deepseek_output"])
        self.assertTrue(result_checkpoint["cache_only_readback"])
        self.assertFalse(result_checkpoint["creates_task_from_readback"])
        self.assertFalse(result_checkpoint["calls_model_from_readback"])
        self.assertFalse(result_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(result_checkpoint["production_quant_projection_complete"])
        self.assertTrue(interpretation["ordinary_result_checkpoint_is_cache_only"])
        self.assertFalse(interpretation["ordinary_result_checkpoint_creates_task"])
        self.assertFalse(interpretation["ordinary_result_checkpoint_calls_model"])
        self.assertTrue(interpretation["ordinary_result_checkpoint_is_not_trade_signal"])
        result_rows = {row["surface"]: row for row in interpretation["ordinary_result_readback_rows"]}
        self.assertEqual(
            set(result_rows),
            {"data_source", "quant_projection", "next_session_map", "research_only_boundary"},
        )
        self.assertEqual(result_rows["data_source"]["status"], "blocked_missing_credentials")
        self.assertIn("服务端 Tushare 凭据缺失", result_rows["data_source"]["ordinary_label"])
        self.assertEqual(result_rows["quant_projection"]["status"], "blocked_missing_credentials")
        self.assertEqual(result_rows["next_session_map"]["status"], "pending_local_cache_refresh")
        self.assertEqual(result_rows["research_only_boundary"]["status"], "research_only_safe")
        for result_row in result_rows.values():
            self.assertFalse(result_row["external_calls_triggered"])
            self.assertFalse(result_row["uses_deepseek_output"])
            self.assertFalse(result_row["model_output_used"])
            self.assertFalse(result_row["contains_secret"])
            self.assertTrue(result_row["does_not_execute_trades"])
        action_rows = {row["action_key"]: row for row in interpretation["ordinary_result_action_rows"]}
        self.assertIn("先完成确认按钮链路", action_rows["replay_quant_projection"]["用户下一步"])
        self.assertIn("token/key 不进入前端", action_rows["keep_research_only_boundary"]["边界"])
        for action_row in action_rows.values():
            self.assertTrue(action_row["cache_only_readback"])
            self.assertFalse(action_row["creates_task_from_readback"])
            self.assertFalse(action_row["external_calls_triggered"])
            self.assertFalse(action_row["uses_deepseek_output"])
            self.assertFalse(action_row["model_output_used"])
            self.assertFalse(action_row["contains_secret"])
            self.assertTrue(action_row["does_not_execute_trades"])
            self.assertTrue(action_row["does_not_modify_strategy_action"])
            self.assertTrue(action_row["candidate_is_not_buy_instruction"])
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
