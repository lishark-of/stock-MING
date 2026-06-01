import ast
import copy
import json
import sys
import unittest
from pathlib import Path

import command_center_state_adapter as state_adapter


FORBIDDEN_IMPORTS = {
    "streamlit",
    "pywebview",
    "webview",
    "data_fetcher",
    "backtester",
    "tushare_adapter",
    "yfinance",
    "akshare",
    "tushare",
    "openai",
    "app",
}


class CommandCenterStateAdapterTests(unittest.TestCase):
    def test_state_get_is_safe(self):
        state = {}

        self.assertEqual(state_adapter.state_get(state, "missing", "fallback"), "fallback")
        self.assertEqual(state_adapter.state_get(None, "missing", "fallback"), "fallback")
        self.assertEqual(state_adapter.state_get(object(), "missing", "fallback"), "fallback")

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

    def test_get_command_center_packets_from_state_does_not_mutate_state(self):
        state = {
            "command_center_live_packet": {"market": {"bias": "neutral"}},
            "strategy_execution_packet": {"action": "wait"},
            "command_center_decision_packet": {"overall_action": "observe"},
        }
        before = copy.deepcopy(state)

        packets = state_adapter.get_command_center_packets_from_state(
            state,
            strategy_packet_key="strategy_execution_packet",
            strategy_last_success_key="strategy_execution_last_success",
            decision_packet_key="command_center_decision_packet",
            decision_last_success_key="command_center_decision_last_success",
        )

        self.assertEqual(state, before)
        self.assertEqual(packets["live_packet"]["market"]["bias"], "neutral")
        self.assertEqual(packets["strategy_execution_packet"]["action"], "wait")
        self.assertEqual(packets["decision_packet"]["overall_action"], "observe")
        self.assertNotIn("strategy_execution", state["command_center_live_packet"])
        self.assertNotIn("decision", state["command_center_live_packet"])

    def test_build_view_model_from_state_does_not_mutate_state(self):
        state = {
            "command_center_live_packet": {"market": {"bias": "neutral"}},
            "strategy_execution_packet": {"action": "wait", "status": "ready"},
            "command_center_decision_packet": {"overall_action": "observe", "status": "partial"},
        }
        before = copy.deepcopy(state)

        view_model = state_adapter.build_command_center_view_model_from_state(
            state,
            strategy_packet_key="strategy_execution_packet",
            strategy_last_success_key="strategy_execution_last_success",
            decision_packet_key="command_center_decision_packet",
            decision_last_success_key="command_center_decision_last_success",
        )

        self.assertEqual(state, before)
        self.assertNotIn("command_center_view_model", state)
        self.assertEqual(view_model["live_packet"]["strategy_execution"]["action"], "wait")
        self.assertEqual(view_model["live_packet"]["decision"]["overall_action"], "observe")

    def test_attach_child_packets_for_display_does_not_mutate_inputs(self):
        live_packet = {"market": {"bias": "neutral"}}
        strategy_packet = {"action": "wait"}
        decision_packet = {"overall_action": "observe"}
        live_before = copy.deepcopy(live_packet)
        strategy_before = copy.deepcopy(strategy_packet)
        decision_before = copy.deepcopy(decision_packet)

        display_packet = state_adapter.attach_command_center_child_packets_for_display(
            live_packet,
            strategy_execution_packet=strategy_packet,
            decision_packet=decision_packet,
        )

        self.assertIsNot(display_packet, live_packet)
        self.assertEqual(live_packet, live_before)
        self.assertEqual(strategy_packet, strategy_before)
        self.assertEqual(decision_packet, decision_before)
        self.assertEqual(display_packet["strategy_execution"]["action"], "wait")
        self.assertEqual(display_packet["decision"]["overall_action"], "observe")

    def test_build_view_model_from_state_is_json_friendly(self):
        state = {
            "strategy_execution_packet": {"action": "wait", "status": "ready"},
            "command_center_decision_packet": {"overall_action": "observe", "status": "partial"},
        }

        view_model = state_adapter.build_command_center_view_model_from_state(
            state,
            live_packet={"market": {"bias": "neutral"}},
            strategy_packet_key="strategy_execution_packet",
            strategy_last_success_key="strategy_execution_last_success",
            decision_packet_key="command_center_decision_packet",
            decision_last_success_key="command_center_decision_last_success",
        )

        json.dumps(view_model, ensure_ascii=False)

    def test_empty_none_and_non_mapping_inputs_do_not_raise(self):
        for value in (None, {}, object(), [], "bad packet"):
            packets = state_adapter.get_command_center_packets_from_state(value)
            self.assertEqual(packets["live_packet"], {})
            view_model = state_adapter.build_command_center_view_model_from_state(value, live_packet=value)
            self.assertIn("live_packet", view_model)
            display_packet = state_adapter.attach_command_center_child_packets_for_display(value)
            self.assertEqual(display_packet, {})

    def test_state_adapter_forbidden_imports_are_absent(self):
        for filename in ("command_center_adapter.py", "command_center_state_adapter.py"):
            tree = ast.parse(Path(filename).read_text())
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "")

            for name in FORBIDDEN_IMPORTS:
                self.assertNotIn(name, imports, f"Forbidden import in {filename}: {name}")

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
