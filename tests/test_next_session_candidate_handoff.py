from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.services import next_session_service, packet_service
from storage.sqlite_meta import SQLiteMetaStore


class NextSessionCandidateHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "meta.sqlite"
        self.original_next_meta_path = next_session_service.SQLITE_META_PATH
        self.original_packet_meta_path = packet_service.SQLITE_META_PATH
        next_session_service.SQLITE_META_PATH = self.db_path
        packet_service.SQLITE_META_PATH = self.db_path

    def tearDown(self):
        next_session_service.SQLITE_META_PATH = self.original_next_meta_path
        packet_service.SQLITE_META_PATH = self.original_packet_meta_path
        self.tmp.cleanup()

    def _write_candidate_packet(self):
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
                "search_quant_projection_interpretation_summary": {
                    "interpretation_ready": True,
                    "ordinary_result_summary": "可读结论：Tushare-first 账本已回放 4/4 个接口。",
                    "ordinary_result_next_step": "先看上游结论，再手动生成完整次日图谱。",
                    "ordinary_result_boundary": "只读本地 cache / ledger / packet；不调用 DeepSeek。",
                    "deepseek_governed_executor_status": "skipped_waiting_governed_executor",
                    "ordinary_result_quick_read_rows": [{"quick_read_item": "conclusion"}],
                },
            },
        )

    def _write_next_session_packet(self, *, ts_code: str | None):
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
        SQLiteMetaStore(self.db_path).write_packet(
            "command_center_next_session_projection_packet",
            {
                "packet_key": "command_center_next_session_projection_packet",
                "schema_version": "next_session_projection.v1",
                "status": "ready",
                "chart_payload": chart_payload,
                "does_not_modify_action": True,
                "does_not_modify_operation_zones": True,
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

    def test_next_session_marks_chart_ready_when_bound_to_confirmed_symbol(self):
        self._write_candidate_packet()
        self._write_next_session_packet(ts_code="002008.SZ")

        packet = next_session_service.read_next_session_cache()

        summary = packet["ordinary_result_replay_summary"]
        self.assertEqual(summary["status"], "ready_cache_replay")
        self.assertTrue(summary["chart_has_drawable_data"])
        self.assertTrue(summary["chart_symbol_matches_confirmed"])
        self.assertTrue(summary["chart_ready_for_confirmed_symbol"])
        self.assertFalse(summary["chart_stale_for_confirmed_symbol"])
        self.assertEqual(summary["confirmed_symbol"], "002008.SZ")
        self.assertEqual(summary["chart_symbol"], "002008.SZ")
        result_rows = {row["surface"]: row for row in packet["ordinary_result_replay_rows"]}
        self.assertIn("情景=1", result_rows["次日图谱"]["readable_result"])
        self.assertFalse(any(row["external_calls_triggered"] for row in packet["ordinary_result_replay_rows"]))


if __name__ == "__main__":
    unittest.main()
