from __future__ import annotations

import unittest

from server.services import next_session_service, packet_service


class NextSessionOrdinaryProducerContractTests(unittest.TestCase):
    def test_exact_chart_keeps_policy_text_out_of_warnings(self) -> None:
        payload = packet_service._exact_next_session_chart_payload(
            {
                "symbol": "000001.SZ",
                "chart_render_model": {
                    "uses_real_daily_close": True,
                    "historical_series": [
                        {"date": "2026-07-15", "value": 10.2},
                        {"date": "2026-07-16", "value": 10.4},
                    ],
                    "scenario_series": [],
                    "operation_zones": [],
                },
            }
        )

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["symbol"], "000001.SZ")
        self.assertEqual(payload["warnings"], [])
        self.assertTrue(payload["notices"])
        self.assertEqual(payload["chart_summary"]["symbol"], "000001.SZ")

    def test_read_notices_preserve_real_warnings_without_creating_one(self) -> None:
        ready = next_session_service._with_next_session_read_notices(
            {"warnings": [], "notices": ["已有说明"]}
        )
        self.assertEqual(ready["warnings"], [])
        self.assertIn("已有说明", ready["notices"])
        self.assertGreater(len(ready["notices"]), 1)

        degraded = next_session_service._with_next_session_read_notices(
            {"warnings": ["真实数据不完整"]}
        )
        self.assertEqual(degraded["warnings"], ["真实数据不完整"])

    def test_v05_lineage_binds_payload_and_summary_to_same_symbol(self) -> None:
        scope_hash = "a" * 64
        normalized = next_session_service._apply_candidate_radar_v05_lineage(
            {
                "candidate_radar_v05_lineage": {
                    "status": "same_packet_lineage_ready",
                    "candidate_task_id": "local-abc123",
                    "candidate_result_version": "candidate-v05-0123456789abcdef",
                    "candidate_scope_hash": scope_hash,
                    "symbol": "000001.SZ",
                    "data_date": "20260716",
                    "freshness_state": {
                        "state": "fresh",
                        "freshness_state": "fresh",
                        "data_date": "20260716",
                        "expected_trade_date": "20260716",
                        "expected_trade_date_calendar_validated": True,
                    },
                },
                "chart_payload": {"status": "ready"},
                "chart_summary": {"status": "ready"},
            }
        )

        chart = normalized["chart_payload"]
        self.assertEqual(chart["symbol"], "000001.SZ")
        self.assertEqual(chart["source_task_id"], "local-abc123")
        self.assertEqual(chart["result_version"], "candidate-v05-0123456789abcdef")
        self.assertEqual(chart["candidate_scope_hash"], scope_hash)
        self.assertEqual(chart["data_date"], "20260716")
        self.assertEqual(normalized["chart_summary"]["symbol"], "000001.SZ")


if __name__ == "__main__":
    unittest.main()
