import tempfile
import unittest
from pathlib import Path

from server.services import factor_service
from storage.sqlite_meta import SQLiteMetaStore


class FactorQuantCandidateHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "meta.sqlite"
        self.original_meta_path = factor_service.SQLITE_META_PATH
        factor_service.SQLITE_META_PATH = self.db_path

    def tearDown(self):
        factor_service.SQLITE_META_PATH = self.original_meta_path
        self.tmp.cleanup()

    def _write_candidate_packet(self, **overrides):
        packet = {
            "packet_key": "command_center_3_candidate_radar_cache",
            "latest_confirmed_symbol": "002008.SZ",
            "latest_confirmed_task_id": "local-factor-handoff",
            "latest_confirmed_task_status": "success",
            "latest_confirmed_task_current_step": "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_skipped",
            "search_quant_projection_latest_task_id": "local-factor-handoff",
            "search_quant_projection_receipt": {
                "latest_task_id": "local-factor-handoff",
            },
            "search_quant_projection_small_data_writeback_summary": {
                "small_data_writeback_ready": True,
                "provider_api_success_count": 4,
                "provider_api_call_count": 4,
                "provider_call_source": "post_task_call_ledger",
                "ordinary_readback_summary": "Tushare-first 小数据已写入 cache / ledger / packet。",
            },
            "search_quant_projection_interpretation_summary": {
                "interpretation_ready": True,
                "ordinary_result_summary": "可读结论：Tushare-first 账本已回放 4/4 个接口。",
                "ordinary_result_next_step": "先看支持/压制，再打开次日图谱。",
                "ordinary_result_boundary": "只读本地 cache / ledger / packet；不调用 DeepSeek。",
                "deepseek_governed_executor_status": "skipped_waiting_governed_executor",
                "ordinary_result_quick_read_rows": [{"quick_read_item": "conclusion"}],
            },
        }
        packet.update(overrides)
        SQLiteMetaStore(self.db_path).write_packet("command_center_3_candidate_radar_cache", packet)

    def test_factor_quant_cache_replays_candidate_radar_handoff_read_only(self):
        self._write_candidate_packet()

        packet = factor_service.read_factor_quant_cache()

        handoff = packet["candidate_radar_quant_projection_handoff"]
        self.assertEqual(handoff["schema_version"], "factor_quant_candidate_radar_handoff.v1")
        self.assertEqual(handoff["symbol"], "002008.SZ")
        self.assertEqual(handoff["source_task_id"], "local-factor-handoff")
        self.assertEqual(handoff["source_task_status"], "success")
        self.assertEqual(
            handoff["source_task_current_step"],
            "candidate_radar_quant_projection_tushare_first_chain_submitted_deepseek_skipped",
        )
        self.assertTrue(handoff["p2_small_data_ready"])
        self.assertTrue(handoff["p3_readable_result_ready"])
        self.assertEqual(handoff["provider_api_success_count"], 4)
        self.assertEqual(handoff["provider_api_call_count"], 4)
        self.assertFalse(handoff["creates_task_from_readback"])
        self.assertFalse(handoff["calls_provider_or_model"])
        self.assertFalse(handoff["contains_secret"])
        self.assertTrue(handoff["does_not_execute_trades"])
        self.assertTrue(handoff["does_not_modify_strategy_action"])
        self.assertTrue(handoff["does_not_modify_operation_zones"])

        self.assertEqual(packet["ordinary_quant_candidate_handoff_status"], handoff["status"])
        self.assertEqual(packet["latest_confirmed_symbol"], "002008.SZ")
        self.assertEqual(packet["latest_confirmed_symbol_source"], "candidate_radar_quant_projection_handoff")
        self.assertEqual(packet["latest_confirmed_task_id"], "local-factor-handoff")
        self.assertEqual(packet["latest_confirmed_task_status"], "success")
        self.assertFalse(packet["latest_confirmed_symbol_readback_external_calls_triggered"])
        self.assertFalse(packet["latest_confirmed_symbol_creates_task_from_readback"])
        self.assertEqual(len(packet["ordinary_quant_candidate_handoff_rows"]), 5)
        self.assertTrue(packet["counts"]["factor_quant_candidate_radar_handoff_ready"])
        self.assertTrue(packet["counts"]["factor_quant_latest_confirmed_readback_ready"])
        self.assertEqual(packet["counts"]["factor_quant_candidate_handoff_row_count"], 5)
        self.assertTrue(packet["policy"]["factor_quant_candidate_handoff_is_cache_only"])
        self.assertFalse(packet["policy"]["factor_quant_candidate_handoff_creates_task"])
        self.assertFalse(packet["policy"]["factor_quant_candidate_handoff_calls_provider_or_model"])
        self.assertTrue(packet["policy"]["factor_quant_candidate_handoff_is_not_trade_signal"])
        self.assertTrue(packet["policy"]["factor_quant_latest_confirmed_readback_is_cache_only"])
        self.assertFalse(packet["policy"]["factor_quant_latest_confirmed_readback_creates_task"])
        self.assertFalse(packet["policy"]["factor_quant_latest_confirmed_readback_calls_provider_or_model"])
        self.assertTrue(packet["policy"]["factor_quant_latest_confirmed_readback_is_not_trade_signal"])

        ledger = {row["api"]: row for row in packet["call_ledger"]}
        self.assertIn("local_factor_quant_candidate_radar_handoff", ledger)
        handoff_ledger = ledger["local_factor_quant_candidate_radar_handoff"]
        self.assertFalse(handoff_ledger["external"])
        self.assertFalse(handoff_ledger["tushare_called"])
        self.assertFalse(handoff_ledger["deepseek_called"])
        self.assertFalse(handoff_ledger["github_called"])
        self.assertTrue(handoff_ledger["does_not_execute_trades"])
        self.assertTrue(handoff_ledger["does_not_modify_operation_zones"])
        self.assertIn("Factor Quant CandidateRadar handoff", " / ".join(packet["warnings"]))

    def test_factor_quant_candidate_handoff_blocks_secret_or_model_output(self):
        self._write_candidate_packet(
            search_quant_projection_interpretation_summary={
                "interpretation_ready": True,
                "ordinary_result_summary": "should not replay",
                "uses_model_output": True,
            }
        )

        packet = factor_service.read_factor_quant_cache()

        self.assertNotIn("candidate_radar_quant_projection_handoff", packet)
        self.assertFalse(packet.get("counts", {}).get("factor_quant_candidate_radar_handoff_ready", False))


if __name__ == "__main__":
    unittest.main()
