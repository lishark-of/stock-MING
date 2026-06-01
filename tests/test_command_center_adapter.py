import sys
import unittest

import command_center_adapter as adapter


class CommandCenterAdapterTests(unittest.TestCase):
    def test_as_mapping_and_get_nested_are_safe(self):
        self.assertEqual(adapter.as_mapping(None), {})
        self.assertEqual(adapter.as_mapping(["not", "mapping"]), {})
        self.assertEqual(adapter.as_mapping({"a": 1}), {"a": 1})
        self.assertEqual(adapter.get_nested({"a": {"b": 2}}, "a.b"), 2)
        self.assertEqual(adapter.get_nested({"a": None}, "a.b", "fallback"), "fallback")
        self.assertEqual(adapter.get_nested(None, "a.b", "fallback"), "fallback")

    def test_pick_display_packet_prefers_current_then_last_success(self):
        state = {
            "packet": {"status": "ready", "value": 1},
            "last": {"status": "ready", "value": 2},
        }
        self.assertEqual(adapter.pick_display_packet(state, "packet", "last")["value"], 1)
        self.assertEqual(adapter.pick_display_packet({"last": {"value": 2}}, "packet", "last")["value"], 2)
        self.assertEqual(adapter.pick_display_packet({}, "packet", "last"), {})

    def test_attach_child_packet_does_not_mutate_input(self):
        live_packet = {"market": {"status": "已刷新"}}
        strategy_packet = {"status": "ready", "action": "等待"}

        attached = adapter.attach_child_packet(live_packet, "strategy_execution", strategy_packet)

        self.assertNotIn("strategy_execution", live_packet)
        self.assertEqual(attached["strategy_execution"]["action"], "等待")
        strategy_packet["action"] = "降风险"
        self.assertEqual(attached["strategy_execution"]["action"], "等待")

    def test_build_command_center_view_model_outputs_stable_shape(self):
        live_packet = {
            "refresh_level": "manual_basic",
            "updated_at": "2026-06-01T10:00:00",
            "market": {"status": "已刷新", "is_fresh": True, "source": "unit"},
            "quant": {"status": "failed", "last_success": {"summary": "old"}, "stale": True},
            "discipline": {},
        }
        strategy_packet = {"status": "ready", "action": "等待"}
        decision_packet = {"status": "partial", "overall_action": "只观察"}

        view_model = adapter.build_command_center_view_model(
            live_packet=live_packet,
            strategy_execution_packet=strategy_packet,
            decision_packet=decision_packet,
        )

        self.assertTrue(view_model["has_live_packet"])
        self.assertTrue(view_model["has_strategy_execution_packet"])
        self.assertTrue(view_model["has_decision_packet"])
        self.assertEqual(view_model["refresh_level"], "manual_basic")
        self.assertEqual(view_model["generated_at"], "2026-06-01T10:00:00")
        self.assertEqual(view_model["data_status"]["market"], "ready")
        self.assertEqual(view_model["data_status"]["quant"], "cached")
        self.assertEqual(view_model["data_status"]["discipline"], "missing")
        self.assertEqual(view_model["data_status"]["strategy_execution"], "ready")
        self.assertEqual(view_model["data_status"]["decision"], "ready")
        self.assertEqual(view_model["live_packet"]["strategy_execution"]["action"], "等待")
        self.assertEqual(view_model["live_packet"]["decision"]["overall_action"], "只观察")
        self.assertEqual(len(view_model["module_statuses"]), 5)
        self.assertEqual([step["key"] for step in view_model["workflow_steps"]], [
            "refresh_basic",
            "strategy_execution",
            "daily_decision",
            "deepseek_explain",
        ])

    def test_build_command_center_view_model_does_not_mutate_inputs(self):
        live_packet = {"market": {"status": "已刷新"}}
        strategy_packet = {"status": "ready"}
        decision_packet = {"status": "ready"}

        adapter.build_command_center_view_model(live_packet, strategy_packet, decision_packet)

        self.assertNotIn("strategy_execution", live_packet)
        self.assertNotIn("decision", live_packet)

    def test_adapter_does_not_import_streamlit_or_external_callers(self):
        self.assertFalse(hasattr(adapter, "st"))
        self.assertNotIn("streamlit", adapter.__dict__)
        self.assertFalse("streamlit" in sys.modules and sys.modules["streamlit"] is adapter)
        for name in (
            "call_deepseek_non_stream",
            "fetch_ohlcv",
            "run_backtest",
            "run_multi_mode_backtests",
            "tushare_adapter",
            "akshare",
            "yfinance",
        ):
            self.assertFalse(hasattr(adapter, name))


if __name__ == "__main__":
    unittest.main()
