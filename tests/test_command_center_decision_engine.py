import sys
import unittest

import command_center_decision_engine as engine


def _section(status="已刷新", summary="", **extra):
    payload = {
        "status": status,
        "summary": summary,
        "is_fresh": status in {"已刷新", "ready", "completed", "ok"},
    }
    payload.update(extra)
    return payload


class CommandCenterDecisionEngineTests(unittest.TestCase):
    def test_missing_data_outputs_waiting(self):
        packet = engine.build_command_center_decision_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["overall_action"], "等待")
        self.assertEqual(packet["risk_level"], "中")
        self.assertEqual(packet["data_coverage"]["market"], "missing")
        self.assertFalse(packet["deepseek_called"])

    def test_weak_market_and_reduce_strategy_outputs_reduce_risk(self):
        live_packet = {
            "market": _section(summary="市场偏弱，风险退潮"),
            "discipline": _section(summary="纪律提示减仓，回撤偏大", action_state="降风险"),
        }
        strategy_packet = {
            "status": "ready",
            "action": "降风险",
            "risk_budget": {"risk_level": "高"},
        }

        packet = engine.build_command_center_decision_packet(
            {},
            live_packet=live_packet,
            strategy_packet=strategy_packet,
        )

        self.assertEqual(packet["overall_action"], "降风险")
        self.assertIn(packet["margin_mode"], {"降低杠杆", "禁止融资"})
        self.assertIn("不加融资", packet["must_not_do"])
        self.assertEqual(packet["risk_level"], "高")

    def test_conflicting_signals_outputs_observe(self):
        live_packet = {
            "market": _section(summary="市场偏强，主线活跃"),
            "quant": _section(summary="量化偏积极", score=68, direction="偏积极"),
            "discipline": _section(summary="纪律提示减仓", action_state="降风险"),
        }
        strategy_packet = {"status": "ready", "action": "等待"}

        packet = engine.build_command_center_decision_packet(
            {},
            live_packet=live_packet,
            strategy_packet=strategy_packet,
        )

        self.assertEqual(packet["overall_action"], "只观察")
        self.assertIn("冲突", packet["reason_summary"])

    def test_data_coverage_marks_missing_cached_ready(self):
        live_packet = {
            "market": _section(summary="市场偏强"),
            "quant": {"status": "failed", "last_success": {"summary": "old"}},
            "discipline": {},
        }
        strategy_packet = {"status": "ready", "action": "等待"}

        packet = engine.build_command_center_decision_packet(
            {},
            live_packet=live_packet,
            strategy_packet=strategy_packet,
        )

        self.assertEqual(packet["data_coverage"]["market"], "ready")
        self.assertEqual(packet["data_coverage"]["quant"], "cached")
        self.assertEqual(packet["data_coverage"]["discipline"], "missing")
        self.assertEqual(packet["data_coverage"]["strategy_execution"], "ready")

    def test_output_fields_are_complete(self):
        packet = engine.build_command_center_decision_packet({})
        expected_keys = {
            "status",
            "overall_action",
            "market_bias",
            "position_mode",
            "margin_mode",
            "etf_priority",
            "next_ticket_priority",
            "risk_level",
            "must_not_do",
            "next_validation_conditions",
            "reason_summary",
            "data_coverage",
            "updated_at",
            "source",
            "deepseek_called",
            "last_error",
        }

        self.assertTrue(expected_keys.issubset(packet.keys()))
        self.assertFalse(packet["deepseek_called"])

    def test_safe_generate_writes_last_success(self):
        state = {}
        packet = engine.safe_generate_command_center_decision_packet(
            state,
            live_packet={"market": _section(summary="震荡")},
            strategy_packet={"status": "ready", "action": "等待"},
        )

        self.assertEqual(state[engine.PACKET_KEY], packet)
        self.assertEqual(state[engine.LAST_SUCCESS_KEY], packet)
        self.assertFalse(packet["deepseek_called"])

    def test_safe_generate_preserves_last_success_on_failure(self):
        state = {engine.LAST_SUCCESS_KEY: {"status": "ready", "overall_action": "只观察", "deepseek_called": False}}
        original = engine.build_command_center_decision_packet

        def boom(*args, **kwargs):
            raise RuntimeError("broken")

        try:
            engine.build_command_center_decision_packet = boom
            packet = engine.safe_generate_command_center_decision_packet(state)
        finally:
            engine.build_command_center_decision_packet = original

        self.assertEqual(packet["status"], "failed")
        self.assertTrue(packet["stale"])
        self.assertEqual(packet["overall_action"], "只观察")
        self.assertEqual(packet["last_error"], "broken")
        self.assertFalse(packet["deepseek_called"])

    def test_engine_does_not_import_streamlit_or_external_callers(self):
        self.assertFalse(hasattr(engine, "st"))
        self.assertNotIn("streamlit", engine.__dict__)
        self.assertFalse("streamlit" in sys.modules and sys.modules["streamlit"] is engine)
        for name in ("fetch_ohlcv", "run_backtest", "run_multi_mode_backtests", "call_deepseek_non_stream"):
            self.assertFalse(hasattr(engine, name))


if __name__ == "__main__":
    unittest.main()
