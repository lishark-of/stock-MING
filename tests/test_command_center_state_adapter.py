import sys
import unittest

import command_center_state_adapter as state_adapter


class CommandCenterStateAdapterTests(unittest.TestCase):
    def test_state_get_and_set_are_safe(self):
        state = {}

        self.assertEqual(state_adapter.state_get(state, "missing", "fallback"), "fallback")
        self.assertTrue(state_adapter.state_set(state, "value", 3))
        self.assertEqual(state_adapter.state_get(state, "value"), 3)

    def test_get_display_packet_prefers_current_then_last_success(self):
        state = {
            "packet": {"status": "ready", "value": "current"},
            "last": {"status": "ready", "value": "last"},
        }

        self.assertEqual(
            state_adapter.get_display_packet(state, "packet", "last")["value"],
            "current",
        )
        self.assertEqual(
            state_adapter.get_display_packet({"last": {"value": "last"}}, "packet", "last")["value"],
            "last",
        )
        self.assertEqual(state_adapter.get_display_packet({}, "packet", "last"), {})

    def test_sync_child_packet_updates_live_packet_state_without_mutating_input(self):
        state = {"command_center_live_packet": {"market": {"status": "已刷新"}}}
        live_packet = {"market": {"status": "已刷新"}}
        strategy_packet = {"status": "ready", "action": "等待"}

        payload = state_adapter.sync_child_packet(
            state,
            live_packet,
            "strategy_execution",
            strategy_packet,
        )

        self.assertNotIn("strategy_execution", live_packet)
        self.assertEqual(payload["strategy_execution"]["action"], "等待")
        self.assertEqual(state["command_center_live_packet"]["strategy_execution"]["action"], "等待")

    def test_sync_child_packet_skips_empty_child_state_update(self):
        state = {"command_center_live_packet": {"market": {"status": "已刷新"}}}

        payload = state_adapter.sync_child_packet(
            state,
            {"market": {"status": "已刷新"}},
            "strategy_execution",
            {},
        )

        self.assertNotIn("strategy_execution", payload)
        self.assertNotIn("strategy_execution", state["command_center_live_packet"])

    def test_sync_child_packets_updates_multiple_children(self):
        state = {"command_center_live_packet": {"market": {"status": "已刷新"}}}

        payload = state_adapter.sync_child_packets(
            state,
            {"market": {"status": "已刷新"}},
            {
                "strategy_execution": {"status": "ready", "action": "等待"},
                "decision": {"status": "partial", "overall_action": "只观察"},
            },
        )

        self.assertEqual(payload["strategy_execution"]["action"], "等待")
        self.assertEqual(payload["decision"]["overall_action"], "只观察")
        self.assertEqual(state["command_center_live_packet"]["decision"]["overall_action"], "只观察")

    def test_build_view_model_from_state_stores_view_model(self):
        state = {
            "strategy_packet": {"status": "ready", "action": "等待"},
            "decision_packet": {"status": "partial", "overall_action": "只观察"},
        }
        live_packet = {
            "refresh_level": "manual_basic",
            "market": {"status": "已刷新", "is_fresh": True},
        }

        view_model = state_adapter.build_view_model_from_state(
            state,
            live_packet=live_packet,
            strategy_packet_key="strategy_packet",
            strategy_last_success_key="strategy_last_success",
            decision_packet_key="decision_packet",
            decision_last_success_key="decision_last_success",
        )

        self.assertEqual(state["command_center_view_model"], view_model)
        self.assertEqual(view_model["data_status"]["market"], "ready")
        self.assertEqual(view_model["data_status"]["strategy_execution"], "ready")
        self.assertEqual(view_model["data_status"]["decision"], "ready")
        self.assertEqual(view_model["live_packet"]["strategy_execution"]["action"], "等待")
        self.assertEqual(view_model["live_packet"]["decision"]["overall_action"], "只观察")

    def test_build_view_model_from_state_can_skip_store(self):
        state = {"strategy_last_success": {"status": "ready", "action": "等待"}}

        view_model = state_adapter.build_view_model_from_state(
            state,
            live_packet={},
            strategy_packet_key="strategy_packet",
            strategy_last_success_key="strategy_last_success",
            store=False,
        )

        self.assertNotIn("command_center_view_model", state)
        self.assertTrue(view_model["has_strategy_execution_packet"])

    def test_state_adapter_does_not_import_streamlit_or_external_callers(self):
        self.assertFalse(hasattr(state_adapter, "st"))
        self.assertNotIn("streamlit", state_adapter.__dict__)
        self.assertFalse("streamlit" in sys.modules and sys.modules["streamlit"] is state_adapter)
        for name in (
            "call_deepseek_non_stream",
            "fetch_ohlcv",
            "run_backtest",
            "run_multi_mode_backtests",
            "tushare_adapter",
            "akshare",
            "yfinance",
        ):
            self.assertFalse(hasattr(state_adapter, name))


if __name__ == "__main__":
    unittest.main()
