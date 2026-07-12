from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.services import next_session_service, packet_service, task_service
from server.services.task_service import clear_task_statuses_for_tests
from storage.sqlite_meta import SQLiteMetaStore


class NextSessionCandidateHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "meta.sqlite"
        self.original_next_meta_path = next_session_service.SQLITE_META_PATH
        self.original_packet_meta_path = packet_service.SQLITE_META_PATH
        self.original_task_meta_path = task_service.SQLITE_META_PATH
        next_session_service.SQLITE_META_PATH = self.db_path
        packet_service.SQLITE_META_PATH = self.db_path
        task_service.SQLITE_META_PATH = self.db_path
        clear_task_statuses_for_tests(clear_persisted=True)

    def tearDown(self):
        next_session_service.SQLITE_META_PATH = self.original_next_meta_path
        packet_service.SQLITE_META_PATH = self.original_packet_meta_path
        task_service.SQLITE_META_PATH = self.original_task_meta_path
        clear_task_statuses_for_tests(clear_persisted=True)
        self.tmp.cleanup()

    def _write_candidate_packet(self, *, interpretation_uses_model_output: bool = False):
        interpretation_summary = {
            "interpretation_ready": True,
            "ordinary_result_summary": "可读结论：Tushare-first 账本已回放 4/4 个接口。",
            "ordinary_result_next_step": "先看上游结论，再手动生成完整次日图谱。",
            "ordinary_result_boundary": "只读本地 cache / ledger / packet；不调用 DeepSeek。",
            "deepseek_governed_executor_status": "skipped_waiting_governed_executor",
            "ordinary_result_quick_read_rows": [{"quick_read_item": "conclusion"}],
        }
        if interpretation_uses_model_output:
            interpretation_summary.update(
                {
                    "uses_model_output": True,
                    "uses_deepseek_output": True,
                    "model_output_used": True,
                    "ordinary_result_summary": "模型解释不应作为次日图谱依据。",
                    "deepseek_governed_executor_status": "success",
                }
            )
        SQLiteMetaStore(self.db_path).write_packet(
            "command_center_3_candidate_radar_cache",
            {
                "packet_key": "command_center_3_candidate_radar_cache",
                "latest_confirmed_symbol": "002008.SZ",
                "latest_confirmed_task_id": "local-next-handoff",
                "latest_confirmed_task_status": "success",
                "latest_confirmed_task_current_step": (
                    "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_skipped"
                ),
                "search_quant_projection_receipt": {"latest_task_id": "local-next-handoff"},
                "search_quant_projection_small_data_writeback_summary": {
                    "small_data_writeback_ready": True,
                    "provider_api_success_count": 4,
                    "provider_api_call_count": 4,
                    "provider_call_source": "post_task_call_ledger",
                    "source_task_external_calls_triggered": True,
                    "source_task_tushare_called": True,
                    "source_task_tushare_provider_ledger_ready": True,
                    "ordinary_readback_summary": "Tushare-first 小数据已写入 cache / ledger / packet。",
                },
                "search_quant_projection_interpretation_summary": interpretation_summary,
            },
        )

    def _write_next_session_packet(self, *, ts_code: str | None, source_task_id: str | None = None):
        chart_payload = {
            "status": "ready",
            "is_exact_next_session_packet": True,
            "historical_points": [{"trade_date": "20260610", "close": 10.2}],
            "scenario_series": [{"name": "base", "data": [{"x": "20260611", "y": 10.4}]}],
            "reference_lines": [{"name": "latest close", "value": 10.2}],
            "operation_zones": [{"name": "watch", "low": 9.8, "high": 10.8}],
            "chart_contract": {
                "cache_only": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_action": True,
                "does_not_modify_operation_zones": True,
            },
        }
        if ts_code:
            chart_payload["ts_code"] = ts_code
        if source_task_id:
            chart_payload["source_task_id"] = source_task_id
        packet = {
            "packet_key": "command_center_next_session_projection_packet",
            "schema_version": "next_session_projection.v1",
            "status": "ready",
            "chart_payload": chart_payload,
            "does_not_modify_action": True,
            "does_not_modify_operation_zones": True,
        }
        if source_task_id:
            packet["source_task_id"] = source_task_id
        SQLiteMetaStore(self.db_path).write_packet(
            "command_center_next_session_projection_packet",
            packet,
        )

    def _write_broken_preview_packet(self):
        SQLiteMetaStore(self.db_path).write_packet(
            "command_center_next_session_projection_packet",
            {
                "packet_key": "command_center_next_session_projection_packet",
                "schema_version": "next_session_projection.v1",
                "status": "candidate_readable_result_replay_chart_pending",
                "cache_source": "candidate_radar_p3_handoff_readonly",
                "latest_confirmed_symbol": "002008.SZ",
                "button_gated_local_confirmed_symbol_preview": True,
                "provider_backed": False,
                "chart_payload": {
                    "status": "missing",
                    "historical_points": [],
                    "scenario_series": [],
                    "reference_lines": [],
                    "operation_zones": [],
                },
                "does_not_modify_action": True,
                "does_not_modify_operation_zones": True,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "contains_secret": False,
            },
        )

    def test_next_session_does_not_mark_unbound_chart_ready_for_confirmed_symbol(self):
        self._write_candidate_packet()
        self._write_next_session_packet(ts_code=None)

        packet = next_session_service.read_next_session_cache()

        self.assertEqual(packet["latest_confirmed_symbol"], "002008.SZ")
        self.assertEqual(packet["latest_confirmed_symbol_source"], "candidate_radar_p3_handoff")
        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["status"], "candidate_readable_result_replay_chart_pending")
        self.assertEqual(packet["ordinary_result_replay_status"], summary["status"])
        self.assertTrue(summary["chart_has_drawable_data"])
        self.assertFalse(summary["chart_symbol_matches_confirmed"])
        self.assertFalse(summary["chart_ready_for_confirmed_symbol"])
        self.assertTrue(summary["chart_stale_for_confirmed_symbol"])
        self.assertEqual(summary["confirmed_symbol"], "002008.SZ")
        self.assertEqual(summary["chart_symbol"], "")
        self.assertTrue(packet["counts"]["next_session_chart_has_drawable_data"])
        self.assertFalse(packet["counts"]["next_session_chart_ready_for_confirmed_symbol"])
        self.assertTrue(packet["counts"]["next_session_chart_stale_for_confirmed_symbol"])

        result_rows = {row["surface"]: row for row in packet["ordinary_result_replay_rows"]}
        self.assertIn("完整 next-session 图谱待手动生成", result_rows["次日图谱"]["readable_result"])
        self.assertNotIn("情景=1", result_rows["次日图谱"]["readable_result"])
        self.assertFalse(any(row["external_calls_triggered"] for row in packet["ordinary_result_replay_rows"]))
        self.assertTrue(packet["policy"]["next_session_ordinary_result_replay_rows_are_cache_only"])
        self.assertFalse(packet["policy"]["next_session_ordinary_result_replay_rows_create_task"])
        self.assertFalse(packet["policy"]["next_session_ordinary_result_replay_rows_call_provider_or_model"])

    def test_next_session_accepts_p2_handoff_when_deepseek_interpretation_is_ignored(self):
        self._write_candidate_packet(interpretation_uses_model_output=True)
        self._write_next_session_packet(ts_code=None)

        packet = next_session_service.read_next_session_cache()

        self.assertEqual(packet["latest_confirmed_symbol"], "002008.SZ")
        self.assertEqual(packet["latest_confirmed_symbol_source"], "candidate_radar_p3_handoff")
        handoff = packet["candidate_radar_p3_handoff"]
        self.assertTrue(handoff["p2_small_data_ready"])
        self.assertFalse(handoff["p3_readable_result_ready"])
        self.assertTrue(handoff["p3_model_output_ignored_for_chart"])
        self.assertTrue(handoff["p2_tushare_handoff_used_without_deepseek_output"])
        self.assertFalse(handoff["uses_model_output"])
        self.assertFalse(handoff["uses_deepseek_output"])
        self.assertEqual(
            handoff["deepseek_governed_executor_status"],
            "model_output_ignored_for_next_session_handoff",
        )
        self.assertIn("Tushare-first 小数据", handoff["ordinary_result_summary"])
        self.assertNotIn("模型解释", handoff["ordinary_result_summary"])
        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["status"], "candidate_readable_result_replay_chart_pending")
        self.assertTrue(summary["chart_stale_for_confirmed_symbol"])
        self.assertTrue(packet["counts"]["next_session_candidate_radar_p2_handoff_ready"])

        task = next_session_service.create_next_session_task(
            {
                "schema_version": "next_session_confirmed_symbol_generate_payload.v1",
                "source": "next_session_map_manual_generate_button",
                "symbol": "002008.SZ",
                "source_task_id": "local-next-handoff",
                "p2_small_data_ready": True,
                "p3_readable_result_ready": False,
                "manual_button_required": True,
                "cache_get_external_calls_triggered": False,
                "react_render_external_calls_triggered": False,
                "deepseek_execution_requested": False,
                "does_not_include_token_or_raw_log": True,
                "does_not_execute_trades": True,
                "does_not_modify_operation_zones": True,
            }
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["call_ledger"][0]["call_status"], "local_confirmed_symbol_preview_written")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])

    def test_next_session_handoff_prefers_result_lineage_task_id_for_result_version(self):
        self._write_candidate_packet()
        store = SQLiteMetaStore(self.db_path)
        candidate = store.read_packet("command_center_3_candidate_radar_cache")
        candidate["search_quant_provider_model_acceptance_receipt"] = {
            "task_id": "local-provider-model-task",
            "symbol": "002008.SZ",
        }
        candidate["search_quant_result_lineage"] = {
            "task_id": "local-provider-model-task",
            "symbol": "002008.SZ",
            "result_version": "qrv-current",
        }
        store.write_packet("command_center_3_candidate_radar_cache", candidate)
        self._write_next_session_packet(ts_code="002008.SZ", source_task_id="local-provider-model-task")

        packet = next_session_service.read_next_session_cache()

        self.assertEqual(packet["status"], "ready_cache_replay")
        self.assertEqual(packet["latest_confirmed_task_id"], "local-provider-model-task")
        self.assertEqual(packet["candidate_radar_p3_handoff"]["source_task_id"], "local-provider-model-task")
        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["confirmed_source_task_id"], "local-provider-model-task")
        self.assertTrue(summary["chart_ready_for_confirmed_symbol"])

    def test_next_session_handoff_uses_latest_confirmed_when_chart_is_already_bound(self):
        self._write_candidate_packet()
        store = SQLiteMetaStore(self.db_path)
        candidate = store.read_packet("command_center_3_candidate_radar_cache")
        candidate["search_quant_provider_model_acceptance_receipt"] = {
            "task_id": "local-older-lineage-task",
            "symbol": "002008.SZ",
            "status": "search_quant_provider_model_acceptance_ready_tushare_light_deepseek_skipped",
        }
        candidate["search_quant_result_lineage"] = {
            "task_id": "local-older-lineage-task",
            "symbol": "002008.SZ",
            "result_version": "qrv-current",
            "current_result_promoted": True,
        }
        candidate["search_quant_canonical_result_lineage"] = {
            "task_id": "local-older-lineage-task",
            "symbol": "002008.SZ",
            "result_version": "qrv-current",
            "current_result_version": "qrv-current",
            "same_task_fact_model_result_version_ready": True,
            "current_result_promoted": True,
        }
        store.write_packet("command_center_3_candidate_radar_cache", candidate)
        self._write_next_session_packet(ts_code="002008.SZ", source_task_id="local-next-handoff")

        packet = next_session_service.read_next_session_cache()

        self.assertEqual(packet["status"], "ready_cache_replay")
        self.assertEqual(packet["latest_confirmed_task_id"], "local-next-handoff")
        handoff = packet["candidate_radar_p3_handoff"]
        self.assertEqual(handoff["source_task_id"], "local-next-handoff")
        self.assertEqual(handoff["chart_source_task_id"], "local-next-handoff")
        self.assertTrue(handoff["chart_is_bound_to_latest_confirmed"])
        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["confirmed_source_task_id"], "local-next-handoff")
        self.assertEqual(summary["chart_source_task_id"], "local-next-handoff")
        self.assertTrue(summary["chart_source_task_matches_confirmed"])
        self.assertTrue(summary["chart_ready_for_confirmed_symbol"])
        self.assertFalse(summary["chart_stale_for_confirmed_symbol"])

    def test_next_session_marks_chart_ready_when_bound_to_confirmed_symbol(self):
        self._write_candidate_packet()
        self._write_next_session_packet(ts_code="002008.SZ", source_task_id="local-next-handoff")

        packet = next_session_service.read_next_session_cache()

        self.assertEqual(packet["status"], "ready_cache_replay")
        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["status"], "ready_cache_replay")
        self.assertTrue(summary["chart_has_drawable_data"])
        self.assertTrue(summary["chart_symbol_matches_confirmed"])
        self.assertTrue(summary["chart_ready_for_confirmed_symbol"])
        self.assertFalse(summary["chart_stale_for_confirmed_symbol"])
        self.assertEqual(summary["confirmed_symbol"], "002008.SZ")
        self.assertEqual(summary["confirmed_source_task_id"], "local-next-handoff")
        self.assertEqual(summary["chart_symbol"], "002008.SZ")
        self.assertEqual(summary["chart_source_task_id"], "local-next-handoff")
        result_rows = {row["surface"]: row for row in packet["ordinary_result_replay_rows"]}
        self.assertIn("情景=1", result_rows["次日图谱"]["readable_result"])
        self.assertFalse(any(row["external_calls_triggered"] for row in packet["ordinary_result_replay_rows"]))

    def test_generate_task_rewrites_same_symbol_preview_when_source_task_is_stale(self):
        self._write_candidate_packet()
        self._write_next_session_packet(ts_code="002008.SZ", source_task_id="local-old-handoff")

        before = next_session_service.read_next_session_cache()
        before_summary = before["ordinary_result_replay_summary"]
        self.assertEqual(before_summary["status"], "candidate_readable_result_replay_chart_pending")
        self.assertEqual(before_summary["chart_symbol"], "002008.SZ")
        self.assertEqual(before_summary["chart_source_task_id"], "local-old-handoff")
        self.assertFalse(before_summary["chart_source_task_matches_confirmed"])
        self.assertTrue(before_summary["chart_stale_for_confirmed_symbol"])

        task = next_session_service.create_next_session_task(
            {
                "schema_version": "next_session_confirmed_symbol_generate_payload.v1",
                "source": "candidate_radar_quant_projection_provider_model_acceptance",
                "symbol": "002008.SZ",
                "source_task_id": "local-next-handoff",
                "p2_small_data_ready": True,
                "p3_readable_result_ready": True,
                "manual_button_required": True,
                "cache_get_external_calls_triggered": False,
                "react_render_external_calls_triggered": False,
                "deepseek_execution_requested": False,
                "does_not_include_token_or_raw_log": True,
                "does_not_execute_trades": True,
                "does_not_modify_operation_zones": True,
            }
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["call_ledger"][0]["call_status"], "local_confirmed_symbol_preview_written")
        request_params = task["call_ledger"][0]["request_params_safe"]
        self.assertEqual(request_params["prior_chart_symbol"], "002008.SZ")
        self.assertEqual(request_params["prior_chart_source_task_id"], "local-old-handoff")
        self.assertFalse(request_params["chart_source_task_ready"])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])

        packet = next_session_service.read_next_session_cache()
        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["status"], "ready_cache_replay")
        self.assertTrue(summary["chart_ready_for_confirmed_symbol"])
        self.assertTrue(summary["chart_source_task_matches_confirmed"])
        self.assertEqual(summary["chart_source_task_id"], "local-next-handoff")
        self.assertEqual(packet["chart_payload"]["source_task_id"], "local-next-handoff")

    def test_generate_task_writes_confirmed_symbol_local_preview_when_chart_is_unbound(self):
        self._write_candidate_packet()
        self._write_next_session_packet(ts_code=None)

        before = next_session_service.read_next_session_cache()
        self.assertEqual(
            before["ordinary_result_replay_summary"]["status"],
            "candidate_readable_result_replay_chart_pending",
        )

        task = next_session_service.create_next_session_task(
            {
                "schema_version": "next_session_confirmed_symbol_generate_payload.v1",
                "source": "next_session_map_manual_generate_button",
                "symbol": "002008.SZ",
                "source_task_id": "local-next-handoff",
                "p2_small_data_ready": True,
                "p3_readable_result_ready": True,
                "manual_button_required": True,
                "cache_get_external_calls_triggered": False,
                "react_render_external_calls_triggered": False,
                "deepseek_execution_requested": False,
                "does_not_include_token_or_raw_log": True,
                "does_not_execute_trades": True,
                "does_not_modify_operation_zones": True,
            }
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "next_session_cache_written_to_sqlite")
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertTrue(task["does_not_modify_strategy_action"])
        self.assertEqual(task["call_ledger"][0]["call_status"], "local_confirmed_symbol_preview_written")
        self.assertTrue(task["call_ledger"][0]["does_not_modify_operation_zones"])
        request_params = task["call_ledger"][0]["request_params_safe"]
        self.assertEqual(request_params["symbol"], "002008.SZ")
        self.assertEqual(request_params["source_task_id"], "local-next-handoff")
        self.assertFalse(request_params["local_exact_sample_allowed"])
        self.assertTrue(request_params["local_confirmed_preview_allowed"])
        self.assertFalse(request_params["provider_backed"])
        self.assertFalse(request_params["production_evidence"])

        packet = next_session_service.read_next_session_cache()
        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["status"], "ready_cache_replay")
        self.assertTrue(summary["chart_has_drawable_data"])
        self.assertTrue(summary["chart_symbol_matches_confirmed"])
        self.assertTrue(summary["chart_ready_for_confirmed_symbol"])
        self.assertFalse(summary["chart_stale_for_confirmed_symbol"])
        self.assertEqual(summary["confirmed_symbol"], "002008.SZ")
        self.assertEqual(summary["chart_symbol"], "002008.SZ")
        self.assertTrue(packet["button_gated_local_confirmed_symbol_preview"])
        self.assertFalse(packet["provider_backed"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["contains_secret"])
        chart = packet["chart_payload"]
        self.assertEqual(chart["symbol"], "002008.SZ")
        self.assertEqual(chart["ts_code"], "002008.SZ")
        self.assertEqual(chart["confirmed_symbol"], "002008.SZ")
        result_rows = {row["surface"]: row for row in packet["ordinary_result_replay_rows"]}
        self.assertIn("情景=1", result_rows["次日图谱"]["readable_result"])
        self.assertFalse(any(row["external_calls_triggered"] for row in packet["ordinary_result_replay_rows"]))

    def test_generate_task_recovers_preview_when_packet_service_meta_path_drifted(self):
        self._write_candidate_packet()
        drift_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(drift_tmp.cleanup)
        packet_service.SQLITE_META_PATH = Path(drift_tmp.name) / "drifted.sqlite"

        task = next_session_service.create_next_session_task(
            {
                "schema_version": "next_session_confirmed_symbol_generate_payload.v1",
                "source": "candidate_radar_quant_projection_provider_model_acceptance",
                "symbol": "002008.SZ",
                "source_task_id": "local-next-handoff",
                "p2_small_data_ready": True,
                "p3_readable_result_ready": True,
                "manual_button_required": True,
                "cache_get_external_calls_triggered": False,
                "react_render_external_calls_triggered": False,
                "deepseek_execution_requested": False,
                "does_not_include_token_or_raw_log": True,
                "does_not_execute_trades": True,
                "does_not_modify_operation_zones": True,
            }
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(Path(packet_service.SQLITE_META_PATH), self.db_path)
        self.assertEqual(task["call_ledger"][0]["call_status"], "local_confirmed_symbol_preview_written")
        persisted = SQLiteMetaStore(self.db_path).read_packet("command_center_next_session_projection_packet")
        chart = persisted["chart_payload"]
        self.assertEqual(chart["status"], "ready")
        self.assertEqual(chart["symbol"], "002008.SZ")
        self.assertTrue(chart["historical_points"])
        self.assertTrue(chart["scenario_series"])
        self.assertTrue(chart["operation_zones"])

        packet = next_session_service.read_next_session_cache()
        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["status"], "ready_cache_replay")
        self.assertTrue(summary["chart_ready_for_confirmed_symbol"])
        self.assertEqual(summary["chart_symbol"], "002008.SZ")
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])

    def test_generate_task_recovers_missing_chart_preview_from_cache_handoff(self):
        self._write_candidate_packet()
        self._write_broken_preview_packet()

        before = next_session_service.read_next_session_cache()
        self.assertEqual(
            before["ordinary_result_replay_summary"]["status"],
            "candidate_readable_result_replay_chart_pending",
        )
        self.assertTrue(before["button_gated_local_confirmed_symbol_preview"])
        self.assertFalse(before["ordinary_result_replay_summary"]["chart_ready_for_confirmed_symbol"])

        task = next_session_service.create_next_session_task(
            {
                "schema_version": "next_session_confirmed_symbol_generate_payload.v1",
                "source": "next_session_map_manual_generate_button",
                "symbol": "002008.SZ",
                "source_task_id": "local-next-handoff",
                "manual_button_required": True,
                "cache_get_external_calls_triggered": False,
                "react_render_external_calls_triggered": False,
                "deepseek_execution_requested": False,
                "does_not_include_token_or_raw_log": True,
                "does_not_execute_trades": True,
                "does_not_modify_operation_zones": True,
            }
        )

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "next_session_cache_written_to_sqlite")
        self.assertEqual(task["call_ledger"][0]["call_status"], "local_confirmed_symbol_preview_written")
        request_params = task["call_ledger"][0]["request_params_safe"]
        self.assertTrue(request_params["local_confirmed_preview_allowed"])
        self.assertTrue(request_params["cache_candidate_preview_allowed"])
        self.assertEqual(request_params["cache_confirmed_symbol"], "002008.SZ")
        self.assertFalse(request_params["provider_backed"])
        self.assertFalse(request_params["production_evidence"])
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertFalse(task["deepseek_called"])

        packet = next_session_service.read_next_session_cache()
        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["status"], "ready_cache_replay")
        self.assertTrue(summary["chart_has_drawable_data"])
        self.assertTrue(summary["chart_ready_for_confirmed_symbol"])
        self.assertEqual(summary["confirmed_symbol"], "002008.SZ")
        self.assertEqual(summary["chart_symbol"], "002008.SZ")
        self.assertTrue(packet["button_gated_local_confirmed_symbol_preview"])
        chart = packet["chart_payload"]
        self.assertEqual(chart["status"], "ready")
        self.assertEqual(chart["symbol"], "002008.SZ")
        self.assertEqual(chart["ts_code"], "002008.SZ")
        self.assertTrue(chart["historical_points"])
        self.assertTrue(chart["scenario_series"])
        result_rows = {row["surface"]: row for row in packet["ordinary_result_replay_rows"]}
        self.assertIn("情景=1", result_rows["次日图谱"]["readable_result"])
        self.assertFalse(any(row["external_calls_triggered"] for row in packet["ordinary_result_replay_rows"]))


if __name__ == "__main__":
    unittest.main()
