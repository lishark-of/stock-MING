from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from server.services import (
    candidate_service,
    factor_service,
    next_session_service,
    packet_service,
    task_service,
    tushare_task_service,
)
from server.services.task_service import clear_task_statuses_for_tests
from storage.sqlite_meta import SQLiteMetaStore


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
            factor_service: factor_service.SQLITE_META_PATH,
            next_session_service: next_session_service.SQLITE_META_PATH,
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

    def test_p0_confirm_gate_requires_stability_or_local_link_evidence(self):
        gate = {
            "schema_version": "candidate_radar_p0_confirm_gate.v1",
            "p0_ready": True,
            "fastapi_cache_get_ready": True,
            "bootstrap_runtime_mode_ready": True,
            "desktop_preflight_ready": True,
            "p0_stability_check_ready": False,
            "p0_local_link_ready": False,
            "p0_connection_evidence_ready": False,
            "candidate_cache_ready": True,
            "creates_task_only_after_button": True,
            "react_render_external_calls": False,
            "get_cache_external_calls": False,
            "contains_sensitive_material": False,
        }

        self.assertFalse(candidate_service._quant_projection_p0_confirm_gate_ready(gate))
        gate["p0_local_link_ready"] = True
        gate["p0_connection_evidence_ready"] = True
        self.assertTrue(candidate_service._quant_projection_p0_confirm_gate_ready(gate))

    def test_p0_confirm_gate_accepts_runtime_packet_contract_evidence(self):
        gate = {
            "schema_version": "candidate_radar_p0_confirm_gate.v1",
            "p0_ready": True,
            "fastapi_cache_get_ready": True,
            "bootstrap_runtime_mode_ready": True,
            "desktop_preflight_ready": True,
            "p0_runtime_packets_ready": True,
            "p0_stability_check_ready": False,
            "p0_local_link_ready": False,
            "p0_connection_evidence_ready": False,
            "p0_quick_action_ready": True,
            "p0_contract_evidence_ready": True,
            "candidate_cache_ready": True,
            "creates_task_only_after_button": True,
            "react_render_external_calls": False,
            "get_cache_external_calls": False,
            "contains_sensitive_material": False,
        }

        self.assertTrue(candidate_service._quant_projection_p0_confirm_gate_ready(gate))
        gate["p0_contract_evidence_ready"] = False
        gate["p0_quick_action_ready"] = False
        self.assertFalse(candidate_service._quant_projection_p0_confirm_gate_ready(gate))

    def test_legacy_provider_ledger_without_p0_gate_does_not_show_p2_as_blocked(self):
        packet = {
            "search_quant_projection_receipt": {
                "schema_version": "candidate_radar_search_quant_projection_receipt.v1",
                "status": "quant_projection_local_receipt_ready_provider_model_pending",
                "latest_task_id": "legacy-task-success",
                "latest_task_status": "success",
                "latest_task_current_step": "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_skipped",
                "call_ledger": [
                    {
                        "api": "local_candidate_radar_quant_projection",
                        "request_params_safe": {
                            "include_tushare": True,
                            "include_deepseek": False,
                        },
                    }
                ],
            },
            "search_quant_provider_model_acceptance_receipt": {
                "schema_version": "candidate_radar_search_quant_provider_model_acceptance.v1",
                "status": "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_skipped",
                "include_tushare": True,
                "include_deepseek": False,
                "tushare_call_ledger_evidence_done": True,
                "deepseek_skipped_by_request": True,
                "provider_api_call_count": 4,
                "provider_api_success_count": 4,
                "provider_call_ledger": [
                    {
                        "api": api,
                        "call_status": "success",
                        "external": True,
                        "external_calls_triggered": True,
                        "tushare_called": True,
                        "deepseek_called": False,
                        "github_called": False,
                    }
                    for api in ["trade_cal", "daily", "daily_basic", "moneyflow"]
                ],
            },
        }

        summary = candidate_service._search_quant_projection_small_data_writeback_summary(packet)

        self.assertEqual(summary["status"], "small_data_writeback_ready_tushare_ledger_replayed")
        receipt_rows = {row["receipt_item"]: row for row in summary["ordinary_confirmed_task_receipt_rows"]}
        self.assertEqual(
            receipt_rows["p0_confirm_gate"]["status"],
            "p0_gate_legacy_missing_not_blocking_replay",
        )
        self.assertFalse(receipt_rows["p0_confirm_gate"]["p0_ready"])
        self.assertTrue(receipt_rows["p0_confirm_gate"]["p0_gate_replay_not_blocking"])
        self.assertIn("旧确认任务缺少新版 P0 gate 字段", receipt_rows["p0_confirm_gate"]["ordinary_label"])
        self.assertIn("重新点击确认会写入新版 P0 gate", receipt_rows["p0_confirm_gate"]["ordinary_label"])

    def test_confirm_tushare_first_accepts_local_fastapi_link_without_stability_receipt(self):
        self._with_meta_store()
        self._with_env(TUSHARE_TOKEN="REAL_TUSHARE_SECRET_VALUE")
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
                "task_id": "fake-tushare-local-link-ledger",
                "status": "success",
                "current_step": "tushare_refresh_completed",
                "call_ledger": [
                    {
                        "api": api,
                        "request_params_safe": {"ts_code": payload["ts_code"]},
                        "row_count": 1,
                        "call_status": "success",
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
                    "p0_stability_check_ready": False,
                    "p0_local_link_ready": True,
                    "p0_connection_evidence_ready": True,
                    "p0_local_link_is_ui_gate_only_not_release_evidence": True,
                    "candidate_cache_ready": True,
                    "candidate_cache_status": "ready",
                    "bootstrap_packet_key": "command_center_3_bootstrap_runtime_mode_packet",
                    "desktop_preflight_packet_key": "command_center_3_desktop_shell_preflight_cache",
                    "creates_task_only_after_button": True,
                    "react_render_external_calls": False,
                    "get_cache_external_calls": False,
                    "contains_secret": False,
                },
            },
        ).json()

        self.assertTrue(response["ok"])
        task = response["data"]["task"]
        self.assertEqual(
            task["current_step"],
            "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_skipped",
        )
        self.assertTrue(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])

        cache = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(cache["ok"])
        packet = cache["data"]
        receipt_rows = {
            row["receipt_item"]: row
            for row in packet["search_quant_projection_small_data_writeback_summary"][
                "ordinary_confirmed_task_receipt_rows"
            ]
        }
        self.assertEqual(receipt_rows["p0_confirm_gate"]["status"], "p0_gate_ready")
        self.assertFalse(receipt_rows["p0_confirm_gate"]["p0_stability_check_ready"])
        self.assertTrue(receipt_rows["p0_confirm_gate"]["p0_local_link_ready"])
        self.assertTrue(receipt_rows["p0_confirm_gate"]["p0_connection_evidence_ready"])
        self.assertTrue(
            receipt_rows["p0_confirm_gate"]["p0_local_link_is_ui_gate_only_not_release_evidence"]
        )
        self.assertIn("P0 stability/local link", receipt_rows["p0_confirm_gate"]["ordinary_label"])

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
        self.assertEqual(task["call_ledger"][0]["delegated_tushare_first_call_ledger_count"], 4)
        self.assertEqual(task["call_ledger"][0]["delegated_tushare_first_provider_api_success_count"], 4)
        self.assertEqual(task["call_ledger"][0]["delegated_local_factor_next_refresh_call_ledger_count"], 3)
        self.assertTrue(
            any(
                row["api"] == "local_candidate_radar_quant_projection_provider_model_acceptance"
                for row in task["call_ledger"]
            )
        )
        local_refresh_ledger = [
            row
            for row in task["call_ledger"]
            if str(row.get("api") or "").startswith("local_candidate_quant_projection_")
        ]
        self.assertEqual(
            [row["api"] for row in local_refresh_ledger],
            [
                "local_candidate_quant_projection_factor_light_refresh",
                "local_candidate_quant_projection_next_session_refresh",
                "local_candidate_quant_projection_echarts_payload_readback",
            ],
        )
        self.assertFalse(any(row["external_calls_triggered"] for row in local_refresh_ledger))
        self.assertFalse(any(row["tushare_called"] for row in local_refresh_ledger))
        self.assertFalse(any(row["deepseek_called"] for row in local_refresh_ledger))
        self.assertTrue(all(row["does_not_execute_trades"] for row in local_refresh_ledger))
        self.assertTrue(all(row["does_not_modify_strategy_action"] for row in local_refresh_ledger))
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
        replay_contract = task["payload_safe"]["ordinary_post_confirm_replay_contract"]
        self.assertEqual(
            replay_contract["schema_version"],
            "candidate_radar_search_quant_projection_post_confirm_replay_contract.v1",
        )
        self.assertEqual(replay_contract["trigger"], "after_confirm_button_task_receipt")
        self.assertEqual(replay_contract["route"], "POST /api/candidate-radar/quant-projection")
        self.assertEqual(replay_contract["readback_route"], "GET /api/candidate-radar/cache")
        self.assertEqual(replay_contract["task_status_surface"], "TaskStatusPanel")
        self.assertEqual(
            replay_contract["readback_sequence"],
            [
                "task_id",
                "TaskStatusPanel",
                "GET /api/candidate-radar/cache",
                "cache / call_ledger / packet",
                "factor / next_session replay",
            ],
        )
        self.assertEqual(replay_contract["writeback_surfaces"], ["cache", "call_ledger", "packet"])
        self.assertEqual(replay_contract["result_anchors"], ["#tasks", "#factor", "#next"])
        self.assertTrue(replay_contract["include_tushare_requested"])
        self.assertFalse(replay_contract["include_deepseek_requested"])
        self.assertEqual(replay_contract["deepseek_policy"], "skipped_until_governed_executor")
        self.assertFalse(replay_contract["creates_second_task_from_readback"])
        self.assertFalse(replay_contract["cache_get_external_calls"])
        self.assertFalse(replay_contract["react_render_external_calls"])
        self.assertFalse(replay_contract["readback_calls_provider_or_model"])
        self.assertTrue(replay_contract["safe_payload_material"])
        self.assertTrue(replay_contract["does_not_execute_trades"])
        self.assertTrue(replay_contract["does_not_modify_strategy_action"])
        self.assertFalse(replay_contract["production_quant_projection_complete"])
        self.assertEqual(
            task["call_ledger"][0]["request_params_safe"]["ordinary_post_confirm_replay_contract"],
            replay_contract,
        )

        cache = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(cache["ok"])
        packet = cache["data"]
        receipt = packet["search_quant_provider_model_acceptance_receipt"]
        quant_receipt = packet["search_quant_projection_receipt"]
        small_data = packet["search_quant_projection_small_data_writeback_summary"]
        interpretation = packet["search_quant_projection_interpretation_summary"]
        self.assertEqual(packet["search_quant_projection_latest_confirmed_symbol"], "002008.SZ")
        self.assertEqual(packet["search_quant_projection_confirm_chain_checkpoint"]["symbol"], "002008.SZ")
        self.assertEqual(
            quant_receipt["p1_confirm_chain_status"],
            "p1_confirm_chain_tushare_first_replayed",
        )
        self.assertTrue(quant_receipt["p1_tushare_first_provider_ledger_ready"])
        self.assertEqual(quant_receipt["p1_provider_call_source"], "post_task_call_ledger")
        self.assertEqual(quant_receipt["p1_provider_api_call_count"], 4)
        self.assertEqual(quant_receipt["p1_provider_api_success_count"], 4)
        self.assertTrue(quant_receipt["p1_deepseek_skipped_by_request"])
        self.assertFalse(quant_receipt["p1_cache_readback_external_calls"])
        self.assertFalse(quant_receipt["p1_react_render_external_calls"])
        self.assertTrue(quant_receipt["p1_does_not_execute_trades"])
        self.assertTrue(quant_receipt["p1_does_not_modify_strategy_action"])
        self.assertEqual(
            receipt["status"],
            "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_skipped",
        )
        self.assertTrue(receipt["tushare_call_ledger_evidence_done"])
        self.assertTrue(receipt["deepseek_skipped_by_request"])
        self.assertFalse(receipt["deepseek_called"])
        self.assertTrue(receipt["factor_refresh_executed"])
        self.assertTrue(receipt["next_session_refresh_executed"])
        self.assertTrue(receipt["echarts_payload_refreshed"])
        self.assertEqual(
            receipt["local_factor_next_refresh_status"],
            "local_factor_next_echarts_refreshed",
        )
        self.assertFalse(receipt["production_quant_projection_complete"])
        lineage = packet["search_quant_result_lineage"]
        self.assertEqual(
            lineage["schema_version"],
            "candidate_radar_search_quant_projection_result_lineage.v1",
        )
        self.assertEqual(lineage["task_id"], receipt["task_id"])
        self.assertEqual(lineage["symbol"], "002008.SZ")
        self.assertEqual(lineage["scope_hash"], receipt["acceptance_scope_hash"])
        self.assertEqual(lineage["result_version"], receipt["result_version"])
        self.assertEqual(packet["search_quant_result_version"], lineage["result_version"])
        self.assertEqual(
            packet["search_quant_current_result_lineage"]["result_version"],
            lineage["result_version"],
        )
        self.assertEqual(
            packet["search_quant_last_good_result_lineage"]["result_version"],
            lineage["result_version"],
        )
        self.assertEqual(
            lineage["facts_packet_key"],
            "command_center_candidate_radar_quant_projection_tushare_light_packet",
        )
        self.assertEqual(lineage["data_date"], receipt["data_date"])
        self.assertEqual(lineage["freshness_state"], "fresh_provider")
        self.assertEqual(lineage["provider_call_ledger_ids"], receipt["provider_call_ledger_ids"])
        self.assertEqual(len(lineage["provider_call_ledger_ids"]), 4)
        self.assertIn("command_center_factor_quant_hub_packet", lineage["output_packet_keys"])
        self.assertIn("command_center_next_session_projection_packet", lineage["output_packet_keys"])
        self.assertTrue(lineage["factor_next_same_result_ready"])
        self.assertTrue(lineage["current_result_promoted"])
        self.assertFalse(lineage["old_task_can_overwrite_current"])
        self.assertFalse(lineage["deepseek_is_data_source"])
        for row in receipt["provider_call_ledger"]:
            self.assertTrue(row["call_ledger_id"].startswith("pcl_"))
            self.assertIn(row["call_ledger_id"], lineage["provider_call_ledger_ids"])
        local_refresh = packet["search_quant_projection_local_factor_next_refresh"]
        self.assertEqual(local_refresh["symbol"], "002008.SZ")
        self.assertEqual(local_refresh["status"], "local_factor_next_echarts_refreshed")
        self.assertTrue(local_refresh["factor_refresh_executed"])
        self.assertTrue(local_refresh["next_session_refresh_executed"])
        self.assertTrue(local_refresh["echarts_payload_refreshed"])
        self.assertFalse(local_refresh["external_calls_triggered"])
        self.assertFalse(local_refresh["tushare_called"])
        self.assertFalse(local_refresh["deepseek_called"])
        self.assertTrue(local_refresh["does_not_execute_trades"])
        self.assertTrue(local_refresh["does_not_modify_strategy_action"])
        factor_packet = SQLiteMetaStore(candidate_service.SQLITE_META_PATH).read_packet(
            "command_center_factor_quant_hub_packet"
        )
        next_packet = SQLiteMetaStore(candidate_service.SQLITE_META_PATH).read_packet(
            "command_center_next_session_projection_packet"
        )
        self.assertIn("002008.SZ", factor_packet["universe"]["items"])
        self.assertEqual(next_packet["chart_payload"]["symbol"], "002008.SZ")

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
        p1_shortest = small_data["ordinary_p1_shortest_path_checkpoint"]
        self.assertEqual(
            p1_shortest["schema_version"],
            "candidate_radar_p1_shortest_path_checkpoint.v1",
        )
        self.assertEqual(p1_shortest["status"], "tushare_first_ledger_replayed")
        self.assertTrue(p1_shortest["tushare_first_ledger_ready"])
        self.assertEqual(p1_shortest["route"], "POST /api/candidate-radar/quant-projection")
        self.assertEqual(p1_shortest["task_type"], "run_candidate_radar_quant_projection")
        self.assertIn("P1 最短路径已跑通", p1_shortest["ordinary_label"])
        self.assertIn("Tushare ledger 已回放 4/4", p1_shortest["ordinary_label"])
        self.assertIn("governed explanation 账本或安全降级", p1_shortest["next_action"])
        self.assertFalse(p1_shortest["cache_get_external_calls"])
        self.assertFalse(p1_shortest["react_render_external_calls"])
        self.assertFalse(p1_shortest["readback_creates_task"])
        self.assertTrue(p1_shortest["deepseek_skipped_until_governed_executor"])
        self.assertFalse(p1_shortest["contains_secret"])
        self.assertTrue(p1_shortest["does_not_execute_trades"])
        self.assertTrue(p1_shortest["does_not_modify_strategy_action"])
        self.assertEqual(packet["ordinary_p1_shortest_path_checkpoint"], p1_shortest)
        self.assertTrue(packet["counts"]["search_quant_projection_p1_shortest_path_checkpoint_visible"])
        self.assertTrue(packet["counts"]["search_quant_projection_p1_shortest_path_tushare_ready"])
        self.assertTrue(packet["counts"]["search_quant_projection_p2_three_surface_checkpoint_visible"])
        self.assertTrue(packet["counts"]["search_quant_projection_p2_three_surface_checkpoint_ready"])
        self.assertEqual(packet["counts"]["search_quant_projection_p2_three_surface_checkpoint_readable_surface_count"], 3)
        self.assertEqual(packet["counts"]["search_quant_projection_p2_three_surface_checkpoint_complete_surface_count"], 3)
        self.assertTrue(packet["counts"]["search_quant_projection_p2_cache_ready"])
        self.assertTrue(packet["counts"]["search_quant_projection_p2_ledger_ready"])
        self.assertTrue(packet["counts"]["search_quant_projection_p2_ledger_readable"])
        self.assertTrue(packet["counts"]["search_quant_projection_p2_packet_ready"])
        self.assertTrue(packet["counts"]["search_quant_projection_p2_three_surface_ready"])
        self.assertTrue(packet["counts"]["search_quant_projection_p2_three_surface_readable"])
        self.assertTrue(packet["search_quant_projection_p2_cache_ready"])
        self.assertTrue(packet["search_quant_projection_p2_ledger_ready"])
        self.assertTrue(packet["search_quant_projection_p2_ledger_readable"])
        self.assertTrue(packet["search_quant_projection_p2_packet_ready"])
        self.assertTrue(packet["search_quant_projection_p2_three_surface_ready"])
        self.assertTrue(packet["search_quant_projection_p2_three_surface_readable"])
        self.assertTrue(packet["policy"]["search_quant_projection_p1_shortest_path_checkpoint_is_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_p1_shortest_path_checkpoint_creates_task"])
        self.assertTrue(packet["policy"]["search_quant_projection_p2_three_surface_checkpoint_is_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_p2_three_surface_checkpoint_creates_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_p2_three_surface_checkpoint_calls_provider_from_readback"])
        self.assertFalse(packet["policy"]["search_quant_projection_p2_three_surface_checkpoint_uses_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_p2_three_surface_checkpoint_is_not_trade_signal"])
        self.assertEqual(small_data["packet_key"], "command_center_3_candidate_radar_cache")
        self.assertEqual(small_data["writeback_surfaces"], ["cache", "call_ledger", "packet"])
        self.assertEqual(small_data["provider_call_source"], "post_task_call_ledger")
        self.assertTrue(small_data["provider_call_observed_only_from_post_task"])
        self.assertTrue(small_data["provider_call_ledger_replayed_from_source_task"])
        self.assertTrue(small_data["source_task_external_calls_triggered"])
        self.assertTrue(small_data["source_task_tushare_called"])
        self.assertTrue(small_data["source_task_tushare_provider_ledger_ready"])
        self.assertFalse(small_data["readback_external_calls_triggered"])
        self.assertFalse(small_data["readback_tushare_called"])
        self.assertIn("provider 证据只由 POST task call_ledger 证明", small_data["ordinary_readback_provenance_summary"])
        self.assertIn("GET cache replays stored packet only", small_data["readback_contract"])
        self.assertTrue(small_data["cache_packet_written"])
        self.assertTrue(small_data["cache_ready"])
        self.assertTrue(small_data["small_data_writeback_ready"])
        self.assertTrue(small_data["provider_call_ledger_written"])
        self.assertTrue(small_data["ledger_ready"])
        self.assertTrue(small_data["ledger_readable"])
        self.assertTrue(small_data["packet_ready"])
        self.assertTrue(small_data["p2_three_surface_ready"])
        self.assertTrue(small_data["p2_three_surface_readable"])
        self.assertEqual(small_data["provider_call_ledger_api_count"], 4)
        self.assertEqual(small_data["provider_api_call_count"], 4)
        self.assertEqual(small_data["provider_api_success_count"], 4)
        self.assertTrue(small_data["provider_external_call_observed_in_post_task"])
        self.assertTrue(small_data["deepseek_skipped_by_request"])
        self.assertEqual(small_data["ordinary_readback_status"], "ready_tushare_ledger_replayed")
        self.assertIn("小数据已写入 cache / ledger / packet", small_data["ordinary_readback_summary"])
        self.assertIn("源任务 Tushare 4/4", small_data["ordinary_readback_summary"])
        self.assertIn("本次 GET cache 未外联", small_data["ordinary_readback_summary"])
        self.assertIn("DeepSeek 未请求", small_data["ordinary_readback_summary"])
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
        p2_checkpoint = small_data["ordinary_p2_three_surface_checkpoint"]
        self.assertEqual(p2_checkpoint["schema_version"], "candidate_radar_p2_three_surface_checkpoint.v1")
        self.assertEqual(p2_checkpoint["status"], "p2_three_surface_ready")
        self.assertIn("P2 三面 checkpoint", p2_checkpoint["ordinary_label"])
        self.assertIn("Tushare ledger 4/4", p2_checkpoint["ordinary_label"])
        self.assertEqual(p2_checkpoint["source_task_route"], "POST /api/candidate-radar/quant-projection")
        self.assertEqual(p2_checkpoint["readback_route"], "GET /api/candidate-radar/cache")
        self.assertEqual(p2_checkpoint["surfaces"], ["cache", "call_ledger", "packet"])
        self.assertEqual(p2_checkpoint["readable_surface_count"], 3)
        self.assertEqual(p2_checkpoint["complete_surface_count"], 3)
        self.assertEqual(p2_checkpoint["call_ledger_state"], "ready_tushare_post_task_ledger")
        self.assertTrue(p2_checkpoint["provider_ledger_ready"])
        self.assertTrue(p2_checkpoint["cache_only_readback"])
        self.assertFalse(p2_checkpoint["creates_task_from_readback"])
        self.assertFalse(p2_checkpoint["readback_creates_task"])
        self.assertFalse(p2_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(p2_checkpoint["get_cache_external_calls"])
        self.assertFalse(p2_checkpoint["react_render_external_calls"])
        self.assertFalse(p2_checkpoint["deepseek_called_from_readback"])
        self.assertFalse(p2_checkpoint["uses_deepseek_output"])
        self.assertFalse(p2_checkpoint["contains_secret"])
        self.assertTrue(p2_checkpoint["does_not_execute_trades"])
        self.assertTrue(p2_checkpoint["does_not_modify_strategy_action"])
        self.assertTrue(p2_checkpoint["candidate_is_not_buy_instruction"])
        self.assertFalse(p2_checkpoint["production_quant_projection_complete"])
        self.assertEqual(packet["ordinary_p2_three_surface_checkpoint"], p2_checkpoint)
        confirm_checkpoint = packet["search_quant_projection_confirm_chain_checkpoint"]
        self.assertEqual(
            confirm_checkpoint["schema_version"],
            "candidate_radar_search_quant_projection_confirm_chain_checkpoint.v1",
        )
        self.assertEqual(confirm_checkpoint["status"], "p1_confirm_chain_tushare_first_replayed")
        self.assertTrue(confirm_checkpoint["confirm_task_written"])
        self.assertTrue(confirm_checkpoint["acceptance_dry_run_written"])
        self.assertTrue(confirm_checkpoint["execution_request_written"])
        self.assertTrue(confirm_checkpoint["provider_acceptance_written"])
        self.assertTrue(confirm_checkpoint["provider_ledger_ready"])
        self.assertEqual(confirm_checkpoint["provider_call_source"], "post_task_call_ledger")
        self.assertEqual(confirm_checkpoint["provider_api_success_count"], 4)
        self.assertTrue(confirm_checkpoint["cache_only_readback"])
        self.assertFalse(confirm_checkpoint["search_input_creates_task"])
        self.assertTrue(confirm_checkpoint["confirm_button_creates_task"])
        self.assertFalse(confirm_checkpoint["creates_task_from_readback"])
        self.assertFalse(confirm_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(confirm_checkpoint["deepseek_called_from_confirm_chain"])
        self.assertFalse(confirm_checkpoint["uses_deepseek_output"])
        self.assertTrue(confirm_checkpoint["does_not_execute_trades"])
        self.assertTrue(confirm_checkpoint["does_not_modify_strategy_action"])
        self.assertTrue(confirm_checkpoint["candidate_is_not_buy_instruction"])
        self.assertEqual(packet["search_quant_projection_confirm_chain_status"], confirm_checkpoint["status"])
        self.assertTrue(packet["search_quant_projection_confirm_task_written"])
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
        self.assertTrue(small_data_checkpoint["cache_ready"])
        self.assertTrue(small_data_checkpoint["provider_call_ledger_written"])
        self.assertTrue(small_data_checkpoint["ledger_ready"])
        self.assertTrue(small_data_checkpoint["ledger_readable"])
        self.assertTrue(small_data_checkpoint["packet_written"])
        self.assertTrue(small_data_checkpoint["packet_ready"])
        self.assertTrue(small_data_checkpoint["p2_three_surface_ready"])
        self.assertTrue(small_data_checkpoint["p2_three_surface_readable"])
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
        self.assertTrue(packet["counts"]["search_quant_projection_confirm_chain_checkpoint_visible"])
        self.assertTrue(packet["counts"]["search_quant_projection_confirm_chain_checkpoint_ready"])
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
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_chain_checkpoint_is_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_chain_checkpoint_creates_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_chain_checkpoint_readback_external_calls"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_chain_checkpoint_is_not_trade_signal"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_outcome_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_outcome_rows_create_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_outcome_rows_call_provider_from_readback"])
        self.assertFalse(packet["policy"]["search_quant_projection_confirm_outcome_rows_use_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_confirm_outcome_rows_are_not_trade_signals"])
        self.assertEqual(
            packet["ordinary_one_screen_action_rows"],
            small_data["ordinary_one_screen_action_rows"],
        )
        self.assertEqual(
            packet["ordinary_confirm_outcome_rows"],
            small_data["ordinary_confirm_outcome_rows"],
        )
        self.assertEqual(
            packet["ordinary_writeback_surface_summary_rows"],
            small_data["ordinary_writeback_surface_summary_rows"],
        )
        self.assertEqual(
            packet["ordinary_tushare_first_chain_rows"],
            small_data["ordinary_tushare_first_chain_rows"],
        )
        self.assertEqual(packet["ordinary_one_screen_action_row_count"], 4)
        self.assertEqual(packet["ordinary_confirm_outcome_row_count"], 3)
        self.assertTrue(packet["ordinary_one_screen_action_rows_are_cache_only"])
        self.assertFalse(packet["ordinary_one_screen_action_rows_create_task"])
        self.assertFalse(packet["ordinary_one_screen_action_rows_call_provider_from_readback"])
        self.assertFalse(packet["ordinary_one_screen_action_rows_use_model_output"])
        self.assertTrue(packet["ordinary_one_screen_action_rows_are_not_trade_signals"])
        self.assertTrue(packet["ordinary_confirm_outcome_rows_are_cache_only"])
        self.assertFalse(packet["ordinary_confirm_outcome_rows_create_task"])
        self.assertFalse(packet["ordinary_confirm_outcome_rows_call_provider_from_readback"])
        self.assertFalse(packet["ordinary_confirm_outcome_rows_use_model_output"])
        self.assertTrue(packet["ordinary_confirm_outcome_rows_are_not_trade_signals"])
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
        self.assertIn("DeepSeek 解释只读回放或安全降级", stage_rows["result_replay"]["当前状态"])
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
            "interpretation_ready_tushare_ledger_with_local_map",
        )
        self.assertIn("Tushare 4/4 接口账本已回放", interpretation["summary_label"])
        self.assertEqual(interpretation["ordinary_result_status"], "ready_with_local_map")
        self.assertIn("可读结论：源任务 Tushare-first 账本已回放 4/4 个接口", interpretation["ordinary_result_summary"])
        self.assertIn("本次 GET cache 未外联", interpretation["ordinary_result_summary"])
        self.assertIn("先查看量化推演和次日图谱回放", interpretation["ordinary_result_next_step"])
        self.assertIn("解释只基于本地 cache / ledger / packet", interpretation["ordinary_result_boundary"])
        self.assertIn("源任务 Tushare 接口 4/4", interpretation["ordinary_result_evidence"])
        self.assertIn("本次 GET cache 未外联", interpretation["ordinary_result_evidence"])
        self.assertIn("当前任务未请求 DeepSeek", interpretation["ordinary_result_evidence"])
        self.assertTrue(interpretation["provider_call_ledger_replayed_from_source_task"])
        self.assertTrue(interpretation["source_task_external_calls_triggered"])
        self.assertTrue(interpretation["source_task_tushare_called"])
        self.assertTrue(interpretation["source_task_tushare_provider_ledger_ready"])
        self.assertFalse(interpretation["readback_external_calls_triggered"])
        self.assertFalse(interpretation["readback_tushare_called"])
        self.assertTrue(interpretation["ordinary_result_readable"])
        self.assertTrue(interpretation["p3_explainable_result_ready"])
        self.assertTrue(interpretation["p3_explainable_result_readable"])
        safe_explanation = interpretation["ordinary_result_safe_explanation"]
        self.assertEqual(
            safe_explanation["schema_version"],
            "candidate_radar_p3_safe_explanation.v1",
        )
        self.assertEqual(
            safe_explanation["safe_explanation_fields"],
            ["source", "gap", "next_step", "safety_summary"],
        )
        self.assertIn("Tushare-first", safe_explanation["source"])
        self.assertIn("基础图谱已有本地回放", safe_explanation["gap"])
        self.assertEqual(safe_explanation["next_step"], interpretation["ordinary_result_next_step"])
        self.assertEqual(safe_explanation["safety_summary"], interpretation["ordinary_result_boundary"])
        self.assertTrue(safe_explanation["ordinary_result_readable"])
        self.assertTrue(safe_explanation["provider_data_source_verified"])
        self.assertTrue(safe_explanation["uses_tushare_ledger"])
        self.assertFalse(safe_explanation["uses_deepseek_output"])
        self.assertFalse(safe_explanation["uses_model_output"])
        self.assertTrue(safe_explanation["cache_only_readback"])
        self.assertFalse(safe_explanation["creates_task_from_readback"])
        self.assertFalse(safe_explanation["calls_model_from_readback"])
        self.assertFalse(safe_explanation["readback_external_calls_triggered"])
        self.assertFalse(safe_explanation["contains_secret"])
        self.assertTrue(safe_explanation["does_not_execute_trades"])
        self.assertTrue(safe_explanation["does_not_modify_strategy_action"])
        self.assertFalse(safe_explanation["claims_14_ltg_complete"])
        self.assertEqual(packet["ordinary_result_status"], interpretation["ordinary_result_status"])
        self.assertEqual(packet["ordinary_result_summary"], interpretation["ordinary_result_summary"])
        self.assertEqual(packet["ordinary_result_next_step"], interpretation["ordinary_result_next_step"])
        self.assertEqual(packet["ordinary_result_boundary"], interpretation["ordinary_result_boundary"])
        self.assertEqual(packet["ordinary_result_evidence"], interpretation["ordinary_result_evidence"])
        self.assertTrue(packet["ordinary_result_readable"])
        self.assertEqual(packet["ordinary_result_safe_explanation"], safe_explanation)
        self.assertTrue(packet["search_quant_projection_p3_explainable_result_ready"])
        self.assertTrue(packet["search_quant_projection_p3_explainable_result_readable"])
        self.assertEqual(packet["search_quant_projection_p3_safe_explanation"], safe_explanation)
        self.assertEqual(
            packet["search_quant_projection_p3_safe_explanation_fields"],
            ["source", "gap", "next_step", "safety_summary"],
        )
        self.assertEqual(packet["ordinary_result_missing_evidence"], interpretation["missing_evidence"])
        self.assertEqual(
            packet["ordinary_result_deepseek_governed_executor_status"],
            interpretation["deepseek_governed_executor_status"],
        )
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
        self.assertEqual(
            packet["ordinary_result_quick_read_rows"],
            interpretation["ordinary_result_quick_read_rows"],
        )
        self.assertEqual(
            packet["ordinary_result_decision_brief_rows"],
            interpretation["ordinary_result_decision_brief_rows"],
        )
        self.assertEqual(
            packet["ordinary_result_handoff_rows"],
            interpretation["ordinary_result_handoff_rows"],
        )
        self.assertEqual(
            packet["search_quant_projection_result_quick_read_rows"],
            interpretation["ordinary_result_quick_read_rows"],
        )
        self.assertEqual(
            packet["search_quant_projection_result_handoff_rows"],
            interpretation["ordinary_result_handoff_rows"],
        )
        self.assertEqual(
            packet["search_quant_projection_result_action_rows"],
            interpretation["ordinary_result_action_rows"],
        )
        self.assertEqual(
            packet["ordinary_result_readback_rows"],
            interpretation["ordinary_result_readback_rows"],
        )
        self.assertEqual(
            packet["ordinary_result_action_rows"],
            interpretation["ordinary_result_action_rows"],
        )
        self.assertEqual(
            packet["ordinary_result_checkpoint_rows"],
            interpretation["ordinary_result_checkpoint_rows"],
        )
        self.assertEqual(packet["ordinary_result_quick_read_row_count"], 4)
        self.assertEqual(packet["ordinary_result_decision_brief_row_count"], 3)
        self.assertEqual(packet["ordinary_result_handoff_row_count"], 4)
        self.assertEqual(packet["ordinary_result_readback_row_count"], 4)
        self.assertEqual(packet["ordinary_result_action_row_count"], 4)
        self.assertEqual(packet["ordinary_result_checkpoint_row_count"], 4)
        self.assertEqual(packet["counts"]["ordinary_result_quick_read_row_count"], 4)
        self.assertEqual(packet["counts"]["ordinary_result_decision_brief_row_count"], 3)
        self.assertEqual(packet["counts"]["ordinary_result_handoff_row_count"], 4)
        self.assertEqual(packet["counts"]["ordinary_result_readback_row_count"], 4)
        self.assertEqual(packet["counts"]["ordinary_result_action_row_count"], 4)
        self.assertEqual(packet["counts"]["ordinary_result_checkpoint_row_count"], 4)
        self.assertTrue(packet["policy"]["ordinary_result_quick_read_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["ordinary_result_quick_read_rows_create_task"])
        self.assertFalse(packet["policy"]["ordinary_result_quick_read_rows_call_model"])
        self.assertFalse(packet["policy"]["ordinary_result_quick_read_rows_use_model_output"])
        self.assertTrue(packet["policy"]["ordinary_result_quick_read_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["ordinary_result_decision_brief_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["ordinary_result_decision_brief_rows_create_task"])
        self.assertFalse(packet["policy"]["ordinary_result_decision_brief_rows_call_model"])
        self.assertFalse(packet["policy"]["ordinary_result_decision_brief_rows_use_model_output"])
        self.assertTrue(packet["policy"]["ordinary_result_decision_brief_rows_are_not_trade_signals"])
        decision_brief_rows = {row["brief_key"]: row for row in interpretation["ordinary_result_decision_brief_rows"]}
        self.assertEqual(
            set(decision_brief_rows),
            {"one_minute_conclusion", "one_minute_source", "one_minute_action_boundary"},
        )
        self.assertIn("Tushare-first 账本已回放 4/4 个接口", decision_brief_rows["one_minute_conclusion"]["当前状态"])
        self.assertIn("cache / call_ledger / packet", decision_brief_rows["one_minute_source"]["证据"])
        self.assertIn("不下单、不改 strategy action", decision_brief_rows["one_minute_action_boundary"]["边界"])
        for brief_row in decision_brief_rows.values():
            self.assertTrue(brief_row["cache_only_readback"])
            self.assertFalse(brief_row["creates_task_from_readback"])
            self.assertFalse(brief_row["external_calls_triggered"])
            self.assertFalse(brief_row["uses_deepseek_output"])
            self.assertFalse(brief_row["model_output_used"])
            self.assertFalse(brief_row["contains_secret"])
            self.assertTrue(brief_row["does_not_execute_trades"])
            self.assertTrue(brief_row["does_not_modify_strategy_action"])
        self.assertTrue(packet["policy"]["ordinary_result_handoff_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["ordinary_result_handoff_rows_create_task"])
        self.assertFalse(packet["policy"]["ordinary_result_handoff_rows_call_model"])
        self.assertFalse(packet["policy"]["ordinary_result_handoff_rows_use_model_output"])
        self.assertTrue(packet["policy"]["ordinary_result_handoff_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["ordinary_result_readback_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["ordinary_result_readback_rows_create_task"])
        self.assertFalse(packet["policy"]["ordinary_result_readback_rows_call_model"])
        self.assertTrue(packet["policy"]["ordinary_result_readback_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["ordinary_result_action_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["ordinary_result_action_rows_create_task"])
        self.assertFalse(packet["policy"]["ordinary_result_action_rows_call_model"])
        self.assertTrue(packet["policy"]["ordinary_result_action_rows_are_not_trade_signals"])
        self.assertTrue(packet["policy"]["ordinary_result_checkpoint_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["ordinary_result_checkpoint_rows_create_task"])
        self.assertFalse(packet["policy"]["ordinary_result_checkpoint_rows_call_model"])
        self.assertTrue(packet["policy"]["ordinary_result_checkpoint_rows_are_not_trade_signals"])
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
        self.assertIn("等待按钮门控 governed explanation", contract_rows["standalone_p5_task"]["当前状态"])
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
        self.assertEqual(result_checkpoint["status"], "ready_with_local_map")
        self.assertEqual(result_checkpoint["readback_route"], "GET /api/candidate-radar/cache")
        self.assertEqual(result_checkpoint["source_packet_key"], "command_center_3_candidate_radar_cache")
        self.assertIn(response["data"]["task_id"], result_checkpoint["source_task_id"])
        self.assertTrue(result_checkpoint["ordinary_result_readable"])
        self.assertTrue(result_checkpoint["provider_data_source_verified"])
        self.assertFalse(result_checkpoint["blocker_explanation_visible"])
        self.assertEqual(result_checkpoint["data_source_state"], "tushare_first_ledger_ready")
        self.assertEqual(result_checkpoint["evidence_source"], "Tushare-first ledger")
        self.assertEqual(result_checkpoint["next_session_map_state"], "local_map_ready")
        self.assertEqual(result_checkpoint["missing_evidence"], [])
        self.assertEqual(result_checkpoint["missing_evidence_count"], 0)
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
        p3_checkpoint = interpretation["ordinary_p3_explainable_result_checkpoint"]
        self.assertEqual(
            p3_checkpoint["schema_version"],
            "candidate_radar_p3_explainable_result_checkpoint.v1",
        )
        self.assertEqual(p3_checkpoint["status"], "p3_explainable_result_ready_local_map")
        self.assertIn("P3 结果 checkpoint", p3_checkpoint["ordinary_label"])
        self.assertIn("Tushare-first ledger 回放 4/4", p3_checkpoint["ordinary_label"])
        self.assertEqual(p3_checkpoint["readback_route"], "GET /api/candidate-radar/cache")
        self.assertEqual(p3_checkpoint["source_packet_key"], "command_center_3_candidate_radar_cache")
        self.assertTrue(p3_checkpoint["ordinary_result_readable"])
        self.assertTrue(p3_checkpoint["provider_data_source_verified"])
        self.assertEqual(p3_checkpoint["evidence_source"], "Tushare-first ledger")
        self.assertEqual(p3_checkpoint["missing_evidence_count"], 0)
        self.assertEqual(p3_checkpoint["safe_explanation_fields"], ["source", "gap", "next_step", "safety_summary"])
        self.assertEqual(p3_checkpoint["safe_explanation"], safe_explanation)
        self.assertTrue(p3_checkpoint["uses_tushare_ledger"])
        self.assertFalse(p3_checkpoint["uses_deepseek_output"])
        self.assertFalse(p3_checkpoint["uses_model_output"])
        self.assertTrue(p3_checkpoint["cache_only_readback"])
        self.assertFalse(p3_checkpoint["creates_task_from_readback"])
        self.assertFalse(p3_checkpoint["readback_creates_task"])
        self.assertFalse(p3_checkpoint["calls_model_from_readback"])
        self.assertFalse(p3_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(p3_checkpoint["get_cache_external_calls"])
        self.assertFalse(p3_checkpoint["react_render_external_calls"])
        self.assertFalse(p3_checkpoint["contains_secret"])
        self.assertTrue(p3_checkpoint["does_not_execute_trades"])
        self.assertTrue(p3_checkpoint["does_not_modify_strategy_action"])
        self.assertTrue(p3_checkpoint["candidate_is_not_buy_instruction"])
        self.assertFalse(p3_checkpoint["production_quant_projection_complete"])
        self.assertFalse(p3_checkpoint["claims_14_ltg_complete"])
        self.assertEqual(packet["ordinary_p3_explainable_result_checkpoint"], p3_checkpoint)
        self.assertEqual(packet["search_quant_projection_p3_explainable_result_checkpoint"], p3_checkpoint)
        self.assertTrue(packet["counts"]["search_quant_projection_p3_explainable_result_checkpoint_visible"])
        self.assertTrue(packet["counts"]["search_quant_projection_p3_explainable_result_checkpoint_readable"])
        self.assertTrue(packet["counts"]["search_quant_projection_p3_explainable_result_checkpoint_ready"])
        self.assertTrue(packet["counts"]["search_quant_projection_p3_explainable_result_ready"])
        self.assertTrue(packet["counts"]["search_quant_projection_p3_explainable_result_readable"])
        self.assertEqual(
            packet["counts"]["search_quant_projection_p3_explainable_result_checkpoint_missing_evidence_count"],
            0,
        )
        self.assertTrue(packet["policy"]["search_quant_projection_p3_explainable_result_checkpoint_is_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_p3_explainable_result_checkpoint_creates_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_p3_explainable_result_checkpoint_calls_model"])
        self.assertFalse(packet["policy"]["search_quant_projection_p3_explainable_result_checkpoint_uses_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_p3_explainable_result_checkpoint_is_not_trade_signal"])
        self.assertTrue(packet["policy"]["search_quant_projection_p3_safe_explanation_is_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_p3_safe_explanation_creates_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_p3_safe_explanation_calls_model"])
        self.assertFalse(packet["policy"]["search_quant_projection_p3_safe_explanation_uses_model_output"])
        self.assertTrue(packet["policy"]["search_quant_projection_p3_safe_explanation_is_not_trade_signal"])
        self.assertEqual(packet["counts"]["search_quant_projection_result_checkpoint_missing_evidence_count"], 0)
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
        self.assertIn("missing_evidence_count=0", checkpoint_rows["gap_and_next_step"]["证据"])
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
        self.assertEqual(result_rows["next_session_map"]["status"], "local_map_ready")
        self.assertIn("Next Session 图谱已有本地回放", result_rows["next_session_map"]["ordinary_label"])
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
        self.assertIn("本地图谱可回放", handoff_rows["replay_next_session_map"]["当前状态"])
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
        self.assertIn("本地图谱可回放", action_rows["replay_next_session_map"]["当前状态"])
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
        self.assertEqual(interpretation["next_session_map_state"], "local_map_ready")
        self.assertNotIn("Factor/Next/ECharts local cache replay", interpretation["missing_evidence"])
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

    def test_deepseek_model_call_requests_json_object_response_format(self):
        captured = {}
        original_openai = sys.modules.get("openai")
        original_get_deepseek_model = candidate_service.get_deepseek_model

        class FakeCompletions:
            def create(self, **kwargs):
                captured["create"] = kwargs
                return types.SimpleNamespace(
                    choices=[
                        types.SimpleNamespace(
                            message=types.SimpleNamespace(
                                content=json.dumps(
                                    {
                                        "summary": "ok",
                                        "support_notes": [],
                                        "suppress_notes": [],
                                        "conflict_notes": [],
                                        "missing_data_notes": [],
                                        "discipline_notes": [],
                                    }
                                )
                            )
                        )
                    ],
                    usage=types.SimpleNamespace(prompt_tokens=3, completion_tokens=4, total_tokens=7),
                )

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.chat = types.SimpleNamespace(completions=FakeCompletions())

        sys.modules["openai"] = types.SimpleNamespace(OpenAI=FakeOpenAI)
        candidate_service.get_deepseek_model = lambda purpose="projection": "deepseek-test-model"

        def restore_openai():
            if original_openai is None:
                sys.modules.pop("openai", None)
            else:
                sys.modules["openai"] = original_openai

        self.addCleanup(restore_openai)
        self.addCleanup(setattr, candidate_service, "get_deepseek_model", original_get_deepseek_model)

        result = candidate_service._call_quant_projection_deepseek_model(
            api_key="SAFE_TEST_KEY",
            fact_summary={"symbol": "000001.SZ", "data_source": "Tushare"},
        )

        self.assertEqual(captured["client"]["api_key"], "SAFE_TEST_KEY")
        self.assertEqual(captured["client"]["base_url"], "https://api.deepseek.com/v1")
        self.assertEqual(captured["create"]["model"], "deepseek-test-model")
        self.assertEqual(captured["create"]["response_format"], {"type": "json_object"})
        system_prompt = captured["create"]["messages"][0]["content"]
        self.assertIn("只输出一个 JSON object", system_prompt)
        self.assertIn("不要输出 Markdown", system_prompt)
        self.assertIn("每个数组最多 1 条", system_prompt)
        self.assertIn("总输出控制在 220 个中文字符以内", system_prompt)
        self.assertEqual(captured["create"]["max_tokens"], 1200)
        self.assertEqual(json.loads(captured["create"]["messages"][1]["content"])["symbol"], "000001.SZ")
        self.assertEqual(result["response_format"], "json_object")
        self.assertTrue(result["provider_response_format_requested"])
        self.assertEqual(result["max_tokens"], 1200)
        self.assertTrue(result["content_present"])
        self.assertEqual(result["usage"]["total_tokens"], 7)

    def test_confirm_tushare_first_with_deepseek_explanation_writes_model_ledger(self):
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
        original_call_deepseek = candidate_service._call_quant_projection_deepseek_model
        original_get_deepseek_keys = candidate_service.get_deepseek_keys
        original_get_deepseek_model = candidate_service.get_deepseek_model

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

        def fake_call_deepseek_model(*, api_key, fact_summary):
            self.assertEqual(api_key, "FAKE_DEEPSEEK_KEY")
            self.assertEqual(fact_summary["data_source"], "Tushare")
            self.assertEqual(fact_summary["symbol"], "002008.SZ")
            self.assertEqual(
                [row["api"] for row in fact_summary["provider_rows"]],
                ["trade_cal", "daily", "daily_basic", "moneyflow"],
            )
            return {
                "text": json.dumps(
                    {
                        "summary": "Tushare 数据已回放，模型只解释来源与缺口。",
                        "support_notes": ["四个轻量接口已有成功账本。"],
                        "discipline_notes": ["仅解释，不构成交易指令。"],
                        "strategy_action": "SHOULD_BE_DROPPED",
                    },
                    ensure_ascii=False,
                ),
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            }

        candidate_service.tushare_task_service.run_tushare_refresh_task = fake_run_tushare_refresh_task
        candidate_service._call_quant_projection_deepseek_model = fake_call_deepseek_model
        candidate_service.get_deepseek_keys = lambda: ["FAKE_DEEPSEEK_KEY"]
        candidate_service.get_deepseek_model = lambda purpose="projection": "deepseek-test-model"
        self.addCleanup(
            setattr,
            candidate_service.tushare_task_service,
            "run_tushare_refresh_task",
            original_run_tushare,
        )
        self.addCleanup(setattr, candidate_service, "_call_quant_projection_deepseek_model", original_call_deepseek)
        self.addCleanup(setattr, candidate_service, "get_deepseek_keys", original_get_deepseek_keys)
        self.addCleanup(setattr, candidate_service, "get_deepseek_model", original_get_deepseek_model)

        response = self.client.post(
            "/api/candidate-radar/quant-projection",
            json={
                "symbol": "002008",
                "include_tushare": True,
                "include_deepseek": True,
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
            "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_explained",
        )
        self.assertTrue(task["tushare_called"])
        self.assertTrue(any(row.get("deepseek_called") is True for row in task["call_ledger"]))
        self.assertFalse(task["github_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])

        cache = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(cache["ok"])
        packet = cache["data"]
        receipt = packet["search_quant_provider_model_acceptance_receipt"]
        model_ledger = packet["search_quant_deepseek_model_ledger"]
        explanation = packet["search_quant_deepseek_explanation"]
        payload = explanation["payload"]

        self.assertEqual(
            receipt["status"],
            "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_explained",
        )
        self.assertTrue(receipt["tushare_call_ledger_evidence_done"])
        self.assertTrue(receipt["deepseek_model_ledger_recorded"])
        self.assertTrue(receipt["deepseek_output_acceptance_done"])
        self.assertTrue(receipt["deepseek_called"])
        self.assertFalse(receipt["deepseek_skipped_by_request"])
        self.assertEqual(explanation["status"], "success")
        self.assertEqual(payload["summary"], "Tushare 数据已回放，模型只解释来源与缺口。")
        self.assertNotIn("strategy_action", payload)
        self.assertIn("strategy_action", explanation["ignored_keys"])
        self.assertEqual(model_ledger["model"], "deepseek-test-model")
        self.assertTrue(model_ledger["server_key_present"])
        self.assertEqual(model_ledger["prompt_tokens"], 12)
        self.assertEqual(model_ledger["completion_tokens"], 8)
        self.assertEqual(model_ledger["total_tokens"], 20)
        self.assertEqual(model_ledger["model_ledger_id"], receipt["model_ledger_id"])
        self.assertEqual(explanation["model_ledger_id"], receipt["model_ledger_id"])
        self.assertEqual(packet["search_quant_result_lineage"]["model_ledger_id"], receipt["model_ledger_id"])
        self.assertTrue(receipt["model_ledger_id"].startswith("mlg_"))
        self.assertTrue(model_ledger["input_hash"])
        self.assertTrue(model_ledger["output_hash"])
        self.assertEqual(model_ledger["response_format"], "json_object")
        self.assertTrue(model_ledger["provider_response_format_requested"])
        self.assertEqual(
            model_ledger["provider_response_format_scope"],
            "search_quant_projection_single_call_not_ltg07_production_benchmark",
        )
        self.assertFalse(model_ledger["production_response_format_benchmark_done"])
        self.assertFalse(model_ledger["raw_prompt_stored"])
        self.assertFalse(model_ledger["raw_output_stored"])
        self.assertTrue(model_ledger["does_not_override_numeric_values"])
        self.assertTrue(model_ledger["does_not_modify_strategy_action"])
        deepseek_rows = [
            row for row in packet["call_ledger"] if row.get("api") == "deepseek_quant_projection_explanation"
        ]
        self.assertEqual(len(deepseek_rows), 1)
        self.assertTrue(deepseek_rows[0]["deepseek_called"])
        self.assertFalse(deepseek_rows[0]["tushare_called"])
        self.assertEqual(deepseek_rows[0]["request_params_safe"]["response_format"], "json_object")
        self.assertTrue(deepseek_rows[0]["request_params_safe"]["provider_response_format_requested"])
        self.assertFalse(deepseek_rows[0]["request_params_safe"]["production_response_format_benchmark_done"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))

    def test_confirm_tushare_first_deepseek_empty_output_records_safe_failure_mode(self):
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
        original_call_deepseek = candidate_service._call_quant_projection_deepseek_model
        original_get_deepseek_keys = candidate_service.get_deepseek_keys
        original_get_deepseek_model = candidate_service.get_deepseek_model

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

        def fake_call_deepseek_model(*, api_key, fact_summary):
            self.assertEqual(api_key, "FAKE_DEEPSEEK_KEY")
            self.assertEqual(fact_summary["data_source"], "Tushare")
            return {
                "text": "",
                "usage": {"prompt_tokens": 10, "completion_tokens": 1200, "total_tokens": 1210},
                "response_format": "json_object",
                "provider_response_format_requested": True,
                "finish_reason": "length",
                "max_tokens": 1200,
                "content_present": False,
            }

        candidate_service.tushare_task_service.run_tushare_refresh_task = fake_run_tushare_refresh_task
        candidate_service._call_quant_projection_deepseek_model = fake_call_deepseek_model
        candidate_service.get_deepseek_keys = lambda: ["FAKE_DEEPSEEK_KEY"]
        candidate_service.get_deepseek_model = lambda purpose="projection": "deepseek-test-model"
        self.addCleanup(
            setattr,
            candidate_service.tushare_task_service,
            "run_tushare_refresh_task",
            original_run_tushare,
        )
        self.addCleanup(setattr, candidate_service, "_call_quant_projection_deepseek_model", original_call_deepseek)
        self.addCleanup(setattr, candidate_service, "get_deepseek_keys", original_get_deepseek_keys)
        self.addCleanup(setattr, candidate_service, "get_deepseek_model", original_get_deepseek_model)

        response = self.client.post(
            "/api/candidate-radar/quant-projection",
            json={
                "symbol": "002008",
                "include_tushare": True,
                "include_deepseek": True,
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
            },
        ).json()

        self.assertTrue(response["ok"])
        task = response["data"]["task"]
        self.assertEqual(
            task["current_step"],
            "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_degraded",
        )

        packet = self.client.get("/api/candidate-radar/cache").json()["data"]
        receipt = packet["search_quant_provider_model_acceptance_receipt"]
        model_ledger = packet["search_quant_deepseek_model_ledger"]
        explanation = packet["search_quant_deepseek_explanation"]
        deepseek_rows = [
            row for row in packet["call_ledger"] if row.get("api") == "deepseek_quant_projection_explanation"
        ]

        self.assertEqual(
            receipt["status"],
            "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_degraded",
        )
        self.assertTrue(receipt["tushare_call_ledger_evidence_done"])
        self.assertTrue(receipt["deepseek_model_ledger_recorded"])
        self.assertFalse(receipt["deepseek_output_acceptance_done"])
        self.assertEqual(receipt["deepseek_safe_failure_mode"], "empty_model_output")
        self.assertEqual(model_ledger["safe_failure_mode"], "empty_model_output")
        self.assertEqual(model_ledger["finish_reason"], "length")
        self.assertEqual(model_ledger["max_tokens"], 1200)
        self.assertFalse(model_ledger["content_present"])
        self.assertEqual(explanation["error_message_safe"], "empty_model_output")
        self.assertTrue(explanation["parse_failed"])
        self.assertEqual(deepseek_rows[0]["error_message_safe"], "empty_model_output")
        self.assertFalse(model_ledger["raw_prompt_stored"])
        self.assertFalse(model_ledger["raw_output_stored"])
        self.assertTrue(model_ledger["does_not_modify_strategy_action"])
        self.assertNotIn("REAL_DEEPSEEK_SECRET_VALUE", json.dumps(packet, ensure_ascii=False))

    def test_confirm_tushare_first_deepseek_missing_key_degrades_after_tushare(self):
        self._with_meta_store()
        self._with_env(
            TUSHARE_TOKEN="REAL_TUSHARE_SECRET_VALUE",
            DEEPSEEK_API_KEY=None,
            DEEPSEEK_TOKEN_1=None,
            DEEPSEEK_TOKEN_2=None,
        )
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "radar_packet": {"status": "ready", "summary": "candidate cache"},
                "data_freshness": {"state": "fresh", "expected_trade_date": "2026-06-12"},
            }
        )

        original_run_tushare = candidate_service.tushare_task_service.run_tushare_refresh_task
        original_call_deepseek = candidate_service._call_quant_projection_deepseek_model
        original_get_deepseek_keys = candidate_service.get_deepseek_keys

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
                        "row_count": 2,
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

        def fail_if_deepseek_called(**_kwargs):
            raise AssertionError("DeepSeek must not be called when server key is missing")

        candidate_service.tushare_task_service.run_tushare_refresh_task = fake_run_tushare_refresh_task
        candidate_service._call_quant_projection_deepseek_model = fail_if_deepseek_called
        candidate_service.get_deepseek_keys = lambda: []
        self.addCleanup(
            setattr,
            candidate_service.tushare_task_service,
            "run_tushare_refresh_task",
            original_run_tushare,
        )
        self.addCleanup(setattr, candidate_service, "_call_quant_projection_deepseek_model", original_call_deepseek)
        self.addCleanup(setattr, candidate_service, "get_deepseek_keys", original_get_deepseek_keys)

        response = self.client.post(
            "/api/candidate-radar/quant-projection",
            json={
                "symbol": "002008",
                "include_tushare": True,
                "include_deepseek": True,
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
            },
        ).json()

        self.assertTrue(response["ok"])
        task = response["data"]["task"]
        self.assertEqual(
            task["current_step"],
            "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_degraded",
        )
        self.assertTrue(task["tushare_called"])
        self.assertFalse(any(row.get("deepseek_called") is True for row in task["call_ledger"]))

        cache = self.client.get("/api/candidate-radar/cache").json()
        packet = cache["data"]
        dry_run = packet["search_quant_projection_acceptance_dry_run_receipt"]
        execution_request = packet["search_quant_projection_execution_request_receipt"]
        receipt = packet["search_quant_provider_model_acceptance_receipt"]
        model_ledger = packet["search_quant_deepseek_model_ledger"]
        explanation = packet["search_quant_deepseek_explanation"]
        small_data = packet["search_quant_projection_small_data_writeback_summary"]

        self.assertEqual(dry_run["credential_missing_provider_count"], 1)
        self.assertEqual(dry_run["blocking_credential_missing_provider_count"], 0)
        self.assertTrue(dry_run["deepseek_missing_degrades_without_blocking_tushare"])
        self.assertTrue(execution_request["local_execution_request_ready"])
        self.assertEqual(
            receipt["status"],
            "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_degraded",
        )
        self.assertTrue(receipt["tushare_call_ledger_evidence_done"])
        self.assertTrue(receipt["deepseek_model_ledger_recorded"])
        self.assertTrue(receipt["deepseek_safe_degraded"])
        self.assertFalse(receipt["deepseek_called"])
        self.assertFalse(model_ledger["server_key_present"])
        self.assertEqual(model_ledger["safe_failure_mode"], "missing_server_key")
        self.assertEqual(explanation["status"], "degraded_missing_server_key")
        self.assertEqual(small_data["status"], "small_data_writeback_ready_tushare_ledger_replayed")
        self.assertTrue(small_data["deepseek_model_ledger_recorded"])
        self.assertTrue(small_data["deepseek_safe_degraded"])

    def test_ready_provider_receipt_without_call_ledger_does_not_complete_p2_writeback(self):
        packet = candidate_service._attach_search_quant_projection_small_data_writeback_summary(
            {
                "search_quant_projection_receipt": {
                    "schema_version": "candidate_radar_search_quant_projection_receipt.v1",
                    "status": "quant_projection_local_receipt_ready_provider_model_pending",
                    "symbol": "002008.SZ",
                    "symbol_valid": True,
                    "task_id": "local-confirm-task",
                },
                "search_quant_provider_model_acceptance_receipt": {
                    "schema_version": "candidate_radar_search_quant_provider_model_acceptance.v1",
                    "status": "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_skipped",
                    "symbol": "002008.SZ",
                    "tushare_call_ledger_evidence_done": True,
                    "provider_api_call_count": 4,
                    "provider_api_success_count": 4,
                    "provider_call_ledger": [],
                    "deepseek_skipped_by_request": True,
                },
                "counts": {},
                "policy": {},
            }
        )

        small_data = packet["search_quant_projection_small_data_writeback_summary"]
        self.assertEqual(
            small_data["status"],
            "small_data_writeback_blocked_missing_provider_call_ledger",
        )
        self.assertEqual(small_data["provider_call_source"], "provider_receipt_ready_without_call_ledger")
        self.assertFalse(small_data["small_data_writeback_ready"])
        self.assertFalse(small_data["provider_call_ledger_written"])
        self.assertEqual(small_data["provider_call_ledger_api_count"], 0)
        self.assertEqual(packet["search_quant_projection_small_data_writeback_ready"], False)

        checkpoint = packet["search_quant_projection_writeback_checkpoint"]
        self.assertFalse(checkpoint["provider_ledger_ready"])
        self.assertEqual(checkpoint["call_ledger_state"], "provider_receipt_ready_missing_call_ledger")
        self.assertLess(checkpoint["complete_surface_count"], checkpoint["surface_count"])

        confirm_checkpoint = packet["search_quant_projection_confirm_chain_checkpoint"]
        self.assertEqual(
            confirm_checkpoint["status"],
            "p1_confirm_chain_task_accepted",
        )
        self.assertFalse(confirm_checkpoint["provider_ledger_ready"])

    def test_interpretation_marks_next_session_local_map_ready_from_cache_packet(self):
        self._with_meta_store()
        SQLiteMetaStore(candidate_service.SQLITE_META_PATH).write_packet(
            "command_center_next_session_projection_packet",
            {
                "packet_key": "command_center_next_session_projection_packet",
                "schema_version": "next_session_projection.v1",
                "status": "ready",
                "cache_source": "button_gated_local_preview_no_provider",
                "symbol": "002008.SZ",
                "confirmed_symbol": "002008.SZ",
                "button_gated_local_confirmed_symbol_preview": True,
                "provider_backed": False,
                "chart_payload": {
                    "status": "ready",
                    "symbol": "002008.SZ",
                    "ts_code": "002008.SZ",
                    "confirmed_symbol": "002008.SZ",
                    "historical_points": [{"x": "2026-06-08", "price": 10.0}],
                    "scenario_series": [{"scenario_key": "base", "points": [{"x": "T+1", "price": 10.3}]}],
                    "reference_lines": [{"key": "current", "value": 10.0}],
                    "operation_zones": [{"zone_key": "watch", "price_range": [9.8, 10.5]}],
                },
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
        )
        packet = candidate_service._attach_search_quant_projection_interpretation_summary(
            {
                "packet_key": "command_center_3_candidate_radar_cache",
                "latest_confirmed_symbol": "002008.SZ",
                "search_quant_projection_receipt": {
                    "symbol": "002008.SZ",
                    "task_id": "local-confirm-task",
                    "latest_task_id": "local-confirm-task",
                    "latest_task_status": "success",
                },
                "search_quant_provider_model_acceptance_receipt": {
                    "symbol": "002008.SZ",
                    "provider_api_call_count": 4,
                    "provider_api_success_count": 4,
                    "deepseek_skipped_by_request": True,
                },
                "search_quant_projection_small_data_writeback_summary": {
                    "symbol": "002008.SZ",
                    "small_data_writeback_ready": True,
                    "provider_api_call_count": 4,
                    "provider_api_success_count": 4,
                    "provider_call_ledger_written": True,
                    "source_task_tushare_provider_ledger_ready": True,
                },
                "counts": {},
                "policy": {},
            }
        )

        interpretation = packet["search_quant_projection_interpretation_summary"]
        self.assertEqual(interpretation["status"], "interpretation_ready_tushare_ledger_with_local_map")
        self.assertEqual(interpretation["ordinary_result_status"], "ready_with_local_map")
        self.assertTrue(interpretation["factor_next_echarts_ready"])
        self.assertEqual(interpretation["next_session_map_state"], "local_map_ready")
        self.assertNotIn("Factor/Next/ECharts local cache replay", interpretation["missing_evidence"])
        local_map = interpretation["next_session_local_map_readback"]
        self.assertTrue(local_map["ready"])
        self.assertEqual(local_map["symbol"], "002008.SZ")
        self.assertEqual(local_map["scenario_series_count"], 1)
        self.assertFalse(local_map["external_calls_triggered"])
        self.assertFalse(local_map["tushare_called"])
        self.assertFalse(local_map["deepseek_called"])
        self.assertFalse(local_map["contains_secret"])
        result_rows = {
            row["surface"]: row for row in interpretation["ordinary_result_readback_rows"]
        }
        self.assertEqual(result_rows["next_session_map"]["status"], "local_map_ready")
        handoff_rows = {
            row["handoff_key"]: row for row in interpretation["ordinary_result_handoff_rows"]
        }
        self.assertIn("本地图谱可回放", handoff_rows["replay_next_session_map"]["当前状态"])

    def test_interpretation_surfaces_factor_next_symbol_mismatch_without_external_calls(self):
        self._with_meta_store()
        store = SQLiteMetaStore(candidate_service.SQLITE_META_PATH)
        store.write_packet(
            candidate_service.FACTOR_QUANT_HUB_PACKET_KEY,
            {
                "packet_key": candidate_service.FACTOR_QUANT_HUB_PACKET_KEY,
                "schema_version": "factor_quant_hub.v1",
                "status": "ready",
                "universe": {"type": "current_target", "items": ["002837.SZ"], "size": 1},
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
        )
        store.write_packet(
            candidate_service.NEXT_SESSION_PACKET_KEY,
            {
                "packet_key": candidate_service.NEXT_SESSION_PACKET_KEY,
                "schema_version": "next_session_projection.v1",
                "status": "ready",
                "symbol": "000001.SZ",
                "confirmed_symbol": "000001.SZ",
                "chart_payload": {
                    "status": "ready",
                    "symbol": "000001.SZ",
                    "historical_points": [{"x": "2026-07-10", "price": 10.0}],
                    "scenario_series": [{"scenario_key": "base", "points": [{"x": "T+1", "price": 10.2}]}],
                },
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "contains_secret": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            },
        )

        packet = candidate_service._attach_search_quant_projection_interpretation_summary(
            {
                "packet_key": candidate_service.PACKET_KEY,
                "latest_confirmed_symbol": "000063.SZ",
                "search_quant_projection_receipt": {
                    "symbol": "000063.SZ",
                    "task_id": "local-confirm-task",
                    "latest_task_id": "local-confirm-task",
                    "latest_task_status": "success",
                },
                "search_quant_provider_model_acceptance_receipt": {
                    "symbol": "000063.SZ",
                    "provider_api_call_count": 4,
                    "provider_api_success_count": 4,
                    "deepseek_output_acceptance_done": True,
                    "deepseek_model_ledger_evidence_done": True,
                },
                "search_quant_projection_small_data_writeback_summary": {
                    "symbol": "000063.SZ",
                    "small_data_writeback_ready": True,
                    "provider_api_call_count": 4,
                    "provider_api_success_count": 4,
                    "provider_call_ledger_written": True,
                    "source_task_tushare_provider_ledger_ready": True,
                },
                "counts": {},
                "policy": {},
            }
        )

        interpretation = packet["search_quant_projection_interpretation_summary"]
        alignment = interpretation["ordinary_cross_module_alignment"]
        self.assertEqual(alignment["status"], "mismatch")
        self.assertEqual(alignment["confirmed_symbol"], "000063.SZ")
        self.assertEqual(alignment["factor_alignment_state"], "mismatch")
        self.assertEqual(alignment["next_alignment_state"], "mismatch")
        self.assertFalse(alignment["overall_alignment_ready"])
        self.assertIn("Factor cache 当前是 002837.SZ", alignment["summary_label"])
        self.assertIn("Next cache 当前是 000001.SZ", alignment["summary_label"])
        self.assertFalse(alignment["external_calls_triggered"])
        self.assertFalse(alignment["tushare_called"])
        self.assertFalse(alignment["deepseek_called"])
        self.assertTrue(alignment["does_not_execute_trades"])
        self.assertTrue(alignment["does_not_modify_strategy_action"])

        rows = {row["alignment_key"]: row for row in packet["ordinary_cross_module_alignment_rows"]}
        self.assertIn("Factor cache 当前是 002837.SZ", rows["factor_cache"]["当前状态"])
        self.assertIn("Next Session cache 当前是 000001.SZ", rows["next_session_cache"]["当前状态"])
        for row in rows.values():
            self.assertTrue(row["cache_only_readback"])
            self.assertFalse(row["creates_task_from_readback"])
            self.assertFalse(row["external_calls_triggered"])
            self.assertFalse(row["tushare_called"])
            self.assertFalse(row["deepseek_called"])
            self.assertFalse(row["contains_secret"])
            self.assertTrue(row["does_not_execute_trades"])
            self.assertTrue(row["does_not_modify_strategy_action"])

        self.assertEqual(packet["counts"]["search_quant_projection_cross_module_alignment_row_count"], 4)
        self.assertFalse(packet["counts"]["search_quant_projection_cross_module_alignment_ready"])
        self.assertTrue(packet["policy"]["ordinary_cross_module_alignment_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["ordinary_cross_module_alignment_rows_create_task"])
        self.assertIn("Factor/Next/ECharts local cache replay", interpretation["missing_evidence"])

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
        p1_shortest = small_data["ordinary_p1_shortest_path_checkpoint"]
        self.assertEqual(p1_shortest["status"], "blocked_missing_tushare_credentials")
        self.assertFalse(p1_shortest["tushare_first_ledger_ready"])
        self.assertEqual(p1_shortest["credential_missing_provider_count"], 1)
        self.assertIn("确认任务已接收，但 Tushare 未调用", p1_shortest["ordinary_label"])
        self.assertIn("重新点击确认", p1_shortest["next_action"])
        self.assertFalse(p1_shortest["cache_get_external_calls"])
        self.assertFalse(p1_shortest["react_render_external_calls"])
        self.assertFalse(p1_shortest["readback_creates_task"])
        self.assertTrue(packet["counts"]["search_quant_projection_p1_shortest_path_checkpoint_visible"])
        self.assertFalse(packet["counts"]["search_quant_projection_p1_shortest_path_tushare_ready"])
        self.assertTrue(packet["counts"]["search_quant_projection_p2_three_surface_checkpoint_visible"])
        self.assertFalse(packet["counts"]["search_quant_projection_p2_three_surface_checkpoint_ready"])
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
        p2_checkpoint = small_data["ordinary_p2_three_surface_checkpoint"]
        self.assertEqual(p2_checkpoint["schema_version"], "candidate_radar_p2_three_surface_checkpoint.v1")
        self.assertEqual(p2_checkpoint["status"], "p2_three_surface_blocked_missing_tushare_credentials")
        self.assertIn("P2 三面 checkpoint", p2_checkpoint["ordinary_label"])
        self.assertIn("缺少服务端 Tushare 凭据", p2_checkpoint["ordinary_label"])
        self.assertEqual(p2_checkpoint["readable_surface_count"], 3)
        self.assertEqual(p2_checkpoint["complete_surface_count"], 2)
        self.assertEqual(p2_checkpoint["call_ledger_state"], "local_blocker_ledger_written")
        self.assertTrue(p2_checkpoint["call_ledger_readable"])
        self.assertFalse(p2_checkpoint["call_ledger_complete"])
        self.assertTrue(p2_checkpoint["local_blocker_ledger_written"])
        self.assertFalse(p2_checkpoint["provider_ledger_ready"])
        self.assertEqual(p2_checkpoint["credential_missing_provider_count"], 1)
        self.assertTrue(p2_checkpoint["cache_only_readback"])
        self.assertFalse(p2_checkpoint["creates_task_from_readback"])
        self.assertFalse(p2_checkpoint["readback_creates_task"])
        self.assertFalse(p2_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(p2_checkpoint["get_cache_external_calls"])
        self.assertFalse(p2_checkpoint["react_render_external_calls"])
        self.assertFalse(p2_checkpoint["deepseek_called_from_readback"])
        self.assertFalse(p2_checkpoint["uses_deepseek_output"])
        self.assertTrue(p2_checkpoint["does_not_execute_trades"])
        self.assertTrue(p2_checkpoint["does_not_modify_strategy_action"])
        self.assertFalse(p2_checkpoint["production_quant_projection_complete"])
        self.assertEqual(packet["ordinary_p2_three_surface_checkpoint"], p2_checkpoint)
        confirm_checkpoint = packet["search_quant_projection_confirm_chain_checkpoint"]
        self.assertEqual(
            confirm_checkpoint["schema_version"],
            "candidate_radar_search_quant_projection_confirm_chain_checkpoint.v1",
        )
        self.assertEqual(confirm_checkpoint["status"], "p1_confirm_chain_blocked_missing_tushare_credentials")
        self.assertTrue(confirm_checkpoint["confirm_task_written"])
        self.assertTrue(confirm_checkpoint["acceptance_dry_run_written"])
        self.assertTrue(confirm_checkpoint["execution_request_written"])
        self.assertFalse(confirm_checkpoint["provider_acceptance_written"])
        self.assertFalse(confirm_checkpoint["provider_ledger_ready"])
        self.assertEqual(confirm_checkpoint["credential_missing_provider_count"], 1)
        self.assertTrue(confirm_checkpoint["cache_only_readback"])
        self.assertFalse(confirm_checkpoint["search_input_creates_task"])
        self.assertTrue(confirm_checkpoint["confirm_button_creates_task"])
        self.assertFalse(confirm_checkpoint["creates_task_from_readback"])
        self.assertFalse(confirm_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(confirm_checkpoint["deepseek_called_from_confirm_chain"])
        self.assertFalse(confirm_checkpoint["uses_deepseek_output"])
        self.assertTrue(confirm_checkpoint["does_not_execute_trades"])
        self.assertTrue(confirm_checkpoint["does_not_modify_strategy_action"])
        self.assertEqual(packet["search_quant_projection_confirm_chain_status"], confirm_checkpoint["status"])
        self.assertTrue(packet["search_quant_projection_confirm_task_written"])
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
        self.assertTrue(small_data_checkpoint["cache_ready"])
        self.assertFalse(small_data_checkpoint["ledger_ready"])
        self.assertTrue(small_data_checkpoint["ledger_readable"])
        self.assertTrue(small_data_checkpoint["packet_ready"])
        self.assertFalse(small_data_checkpoint["p2_three_surface_ready"])
        self.assertTrue(small_data_checkpoint["p2_three_surface_readable"])
        self.assertTrue(small_data_checkpoint["cache_only_readback"])
        self.assertFalse(small_data_checkpoint["creates_task_from_readback"])
        self.assertFalse(small_data_checkpoint["readback_external_calls_triggered"])
        self.assertFalse(small_data_checkpoint["uses_deepseek_output"])
        self.assertTrue(small_data_checkpoint["does_not_execute_trades"])
        self.assertTrue(small_data_checkpoint["does_not_modify_strategy_action"])
        self.assertFalse(packet["search_quant_projection_small_data_writeback_ready"])
        self.assertEqual(packet["search_quant_projection_small_data_writeback_status"], small_data["status"])
        self.assertEqual(packet["search_quant_projection_writeback_surfaces"], ["cache", "call_ledger", "packet"])
        self.assertTrue(packet["search_quant_projection_p2_cache_ready"])
        self.assertFalse(packet["search_quant_projection_p2_ledger_ready"])
        self.assertTrue(packet["search_quant_projection_p2_ledger_readable"])
        self.assertTrue(packet["search_quant_projection_p2_packet_ready"])
        self.assertFalse(packet["search_quant_projection_p2_three_surface_ready"])
        self.assertTrue(packet["search_quant_projection_p2_three_surface_readable"])
        self.assertTrue(packet["counts"]["search_quant_projection_confirm_chain_checkpoint_visible"])
        self.assertFalse(packet["counts"]["search_quant_projection_confirm_chain_checkpoint_ready"])
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
        self.assertIn("DeepSeek 不作为数据源", interpretation["ordinary_result_boundary"])
        self.assertIn("DeepSeek 未请求", interpretation["ordinary_result_evidence"])
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
        p3_checkpoint = interpretation["ordinary_p3_explainable_result_checkpoint"]
        self.assertEqual(
            p3_checkpoint["schema_version"],
            "candidate_radar_p3_explainable_result_checkpoint.v1",
        )
        self.assertEqual(p3_checkpoint["status"], "p3_explainable_result_blocked_missing_tushare_credentials")
        self.assertIn("P3 结果 checkpoint", p3_checkpoint["ordinary_label"])
        self.assertIn("缺少服务端 Tushare 凭据", p3_checkpoint["ordinary_label"])
        self.assertTrue(p3_checkpoint["ordinary_result_readable"])
        self.assertFalse(p3_checkpoint["provider_data_source_verified"])
        self.assertTrue(p3_checkpoint["blocker_explanation_visible"])
        self.assertEqual(p3_checkpoint["data_source_state"], "blocked_missing_credentials")
        self.assertEqual(p3_checkpoint["evidence_source"], "local_blocker_or_task_status")
        self.assertGreaterEqual(p3_checkpoint["missing_evidence_count"], 2)
        self.assertEqual(p3_checkpoint["safe_explanation_fields"], ["source", "gap", "next_step", "safety_summary"])
        self.assertEqual(p3_checkpoint["safe_explanation"]["schema_version"], "candidate_radar_p3_safe_explanation.v1")
        self.assertIn("凭据缺失", p3_checkpoint["safe_explanation"]["source"])
        self.assertTrue(p3_checkpoint["safe_explanation"]["ordinary_result_readable"])
        self.assertFalse(p3_checkpoint["safe_explanation"]["provider_data_source_verified"])
        self.assertFalse(p3_checkpoint["safe_explanation"]["uses_deepseek_output"])
        self.assertFalse(p3_checkpoint["safe_explanation"]["creates_task_from_readback"])
        self.assertFalse(p3_checkpoint["uses_tushare_ledger"])
        self.assertFalse(p3_checkpoint["uses_deepseek_output"])
        self.assertTrue(p3_checkpoint["cache_only_readback"])
        self.assertFalse(p3_checkpoint["creates_task_from_readback"])
        self.assertFalse(p3_checkpoint["calls_model_from_readback"])
        self.assertFalse(p3_checkpoint["readback_external_calls_triggered"])
        self.assertTrue(p3_checkpoint["does_not_execute_trades"])
        self.assertTrue(p3_checkpoint["does_not_modify_strategy_action"])
        self.assertFalse(p3_checkpoint["production_quant_projection_complete"])
        self.assertFalse(p3_checkpoint["claims_14_ltg_complete"])
        self.assertEqual(packet["ordinary_p3_explainable_result_checkpoint"], p3_checkpoint)
        self.assertTrue(packet["counts"]["search_quant_projection_p3_explainable_result_checkpoint_visible"])
        self.assertTrue(packet["counts"]["search_quant_projection_p3_explainable_result_checkpoint_readable"])
        self.assertFalse(packet["counts"]["search_quant_projection_p3_explainable_result_checkpoint_ready"])
        self.assertFalse(packet["counts"]["search_quant_projection_p3_explainable_result_ready"])
        self.assertTrue(packet["counts"]["search_quant_projection_p3_explainable_result_readable"])
        self.assertFalse(packet["search_quant_projection_p3_explainable_result_ready"])
        self.assertTrue(packet["search_quant_projection_p3_explainable_result_readable"])
        self.assertTrue(packet["policy"]["search_quant_projection_p3_explainable_result_checkpoint_is_cache_only"])
        self.assertFalse(packet["policy"]["search_quant_projection_p3_explainable_result_checkpoint_creates_task"])
        self.assertFalse(packet["policy"]["search_quant_projection_p3_explainable_result_checkpoint_calls_model"])
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

    def test_provider_receipt_task_id_replays_when_task_status_rows_are_cleared(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        provider_task_id = "local-provider-replay-task"
        provider_rows = [
            {
                "api": api,
                "request_params_safe": {"ts_code": "002008.SZ"},
                "row_count": 3,
                "data_date": "20260612",
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
            for api in ["trade_cal", "daily", "daily_basic", "moneyflow"]
        ]
        SQLiteMetaStore(candidate_service.SQLITE_META_PATH).write_packet(
            candidate_service.PACKET_KEY,
            {
                "packet_key": candidate_service.PACKET_KEY,
                "schema_version": "candidate_radar_cache.v1",
                "status": "ready",
                "scan_mode": "quant_projection_provider_model_acceptance",
                "source_snapshot_hash": "provider-replay-fixture",
                "search_quant_projection_receipt": {
                    "schema_version": "candidate_radar_search_quant_projection_receipt.v1",
                    "status": "quant_projection_local_receipt_ready_provider_model_pending",
                    "symbol": "002008.SZ",
                    "symbol_valid": True,
                    "call_ledger": [],
                },
                "search_quant_provider_model_acceptance_receipt": {
                    "schema_version": "candidate_radar_search_quant_provider_model_acceptance.v1",
                    "task_id": provider_task_id,
                    "status": "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_skipped",
                    "symbol": "002008.SZ",
                    "provider_api_call_count": 4,
                    "provider_api_success_count": 4,
                    "provider_call_ledger": provider_rows,
                    "tushare_call_ledger_evidence_done": True,
                    "external_calls_triggered_by_task": True,
                    "provider_execution_implemented": True,
                    "deepseek_skipped_by_request": True,
                    "deepseek_called": False,
                    "github_called": False,
                    "contains_secret": False,
                    "does_not_execute_trades": True,
                    "does_not_modify_strategy_action": True,
                },
                "call_ledger": provider_rows,
                "counts": {},
                "policy": {},
            },
        )

        cache = self.client.get("/api/candidate-radar/cache").json()
        self.assertTrue(cache["ok"])
        packet = cache["data"]
        quant_receipt = packet["search_quant_projection_receipt"]
        small_data = packet["search_quant_projection_small_data_writeback_summary"]
        self.assertEqual(quant_receipt["latest_task_id"], provider_task_id)
        self.assertEqual(quant_receipt["task_readback_source"], "search_quant_provider_model_acceptance_receipt")
        self.assertEqual(small_data["latest_task_id"], provider_task_id)
        self.assertEqual(small_data["provider_acceptance_task_id"], provider_task_id)
        self.assertEqual(small_data["task_readback_source"], "search_quant_provider_model_acceptance_receipt")
        self.assertTrue(small_data["small_data_writeback_ready"])

        replay = self.client.get(f"/api/tasks/{provider_task_id}").json()
        self.assertTrue(replay["ok"])
        self.assertEqual(replay["data"]["task_id"], provider_task_id)
        self.assertEqual(
            replay["data"]["task_type"],
            "run_candidate_radar_quant_projection_provider_model_acceptance",
        )
        self.assertEqual(
            replay["data"]["payload_safe"]["replay_source_receipt"],
            "search_quant_provider_model_acceptance_receipt",
        )
        self.assertTrue(any(row.get("tushare_called") is True for row in replay["data"]["call_ledger"]))
        self.assertFalse(any(row.get("deepseek_called") is True for row in replay["data"]["call_ledger"]))
        self.assertTrue(replay["data"]["call_ledger_external_calls_replayed"])
        self.assertTrue(replay["data"]["call_ledger_tushare_replayed"])
        self.assertFalse(replay["data"]["call_ledger_deepseek_replayed"])
        self.assertFalse(replay["data"]["readback_external_calls_triggered"])
        self.assertTrue(replay["data"]["does_not_execute_trades"])
        self.assertTrue(replay["data"]["does_not_modify_strategy_action"])

        task_index = self.client.get("/api/tasks").json()
        self.assertTrue(task_index["ok"])
        self.assertEqual(task_index["data"]["latest_task_id"], provider_task_id)
        self.assertEqual(
            task_index["data"]["latest_task_type"],
            "run_candidate_radar_quant_projection_provider_model_acceptance",
        )
        self.assertEqual(task_index["data"]["latest_task_status"], "success")
        self.assertEqual(task_index["data"]["persistence"]["candidate_cache_replay_task_count"], 1)
        self.assertFalse(task_index["data"]["external_calls_triggered"])
        self.assertTrue(task_index["data"]["call_ledger_external_calls_replayed"])
        self.assertTrue(task_index["data"]["call_ledger_tushare_replayed"])
        self.assertFalse(task_index["data"]["call_ledger_deepseek_replayed"])
        self.assertFalse(task_index["data"]["readback_external_calls_triggered"])
        self.assertFalse(task_index["data"]["deepseek_called"])
        self.assertFalse(task_index["data"]["github_called"])
        self.assertTrue(task_index["data"]["does_not_execute_trades"])
        self.assertTrue(task_index["data"]["does_not_modify_strategy_action"])


if __name__ == "__main__":
    unittest.main()
