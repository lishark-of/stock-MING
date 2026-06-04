import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_local_api_contract as contract
import command_center_local_api_preview as preview


FORBIDDEN_IMPORTS = {
    "streamlit",
    "app",
    "command_center_service",
    "strategy_execution_service",
    "command_center_decision_engine",
    "tushare_adapter",
    "tushare",
    "akshare",
    "yfinance",
    "data_fetcher",
    "backtester",
    "openai",
}


def sample_state():
    return {
        "command_center_home_snapshot": {
            "status": "ready",
            "timestamp": "2026-06-04T09:30:00",
            "latest_recovery_result_notice": {
                "status": "ready",
                "writes_packet": "command_center_moneyflow_packet",
            },
        },
        "command_center_live_packet": {
            "status": "ready",
            "market": {"bias": "neutral"},
            "api_key": "sk-live-secret",
        },
        "command_center_projection_packet": {
            "status": "cached",
            "paths": [{"name": "中性路径"}],
        },
        "command_center_decision_packet": {
            "status": "ready",
            "overall_action": "只观察",
        },
    }


class CommandCenterLocalApiPreviewTests(unittest.TestCase):
    def test_preview_bundle_is_json_friendly_and_safe(self):
        bundle = preview.build_local_api_preview_bundle(
            sample_state(),
            packet_keys=["command_center_live_packet", "command_center_projection_packet"],
        )
        dumped = json.dumps(bundle, ensure_ascii=False)

        self.assertEqual(bundle["kind"], preview.PREVIEW_KIND)
        self.assertFalse(bundle["server_started"])
        self.assertFalse(bundle["deepseek_called"])
        self.assertEqual(bundle["external_call_policy"], "not_triggered")
        self.assertEqual(bundle["response_count"], 2)
        self.assertEqual(bundle["available_count"], 2)
        self.assertEqual(bundle["missing_count"], 0)
        self.assertIn("command_center_live_packet", dumped)
        self.assertNotIn("sk-live-secret", dumped)
        self.assertIn(contract.REDACTED_VALUE, dumped)
        for response in bundle["responses"]:
            self.assertTrue(contract.validate_packet_response_envelope(response)["valid"])

    def test_preview_does_not_mutate_state(self):
        state = sample_state()
        before = copy.deepcopy(state)

        preview.build_local_api_preview_bundle(state)

        self.assertEqual(state, before)

    def test_missing_packet_returns_waiting_response(self):
        bundle = preview.build_local_api_preview_bundle(
            {},
            packet_keys=["command_center_decision_packet"],
        )
        response = bundle["responses"][0]

        self.assertEqual(bundle["missing_count"], 1)
        self.assertEqual(response["status"], "waiting")
        self.assertTrue(response["ok"])
        self.assertFalse(response["meta"]["available"])
        self.assertIn("not present", response["warnings"][0])

    def test_can_exclude_missing_responses(self):
        bundle = preview.build_local_api_preview_bundle(
            {},
            packet_keys=["command_center_decision_packet"],
            include_missing=False,
        )

        self.assertEqual(bundle["response_count"], 0)
        self.assertEqual(bundle["available_count"], 0)
        self.assertEqual(bundle["missing_count"], 0)

    def test_latest_recovery_notice_can_be_read_from_home_snapshot(self):
        bundle = preview.build_local_api_preview_bundle(
            sample_state(),
            packet_keys=["latest_recovery_result_notice"],
        )
        response = bundle["responses"][0]

        self.assertEqual(response["packet_key"], "latest_recovery_result_notice")
        self.assertTrue(response["meta"]["available"])
        self.assertEqual(response["payload"]["writes_packet"], "command_center_moneyflow_packet")

    def test_preview_index_maps_paths_to_packet_status(self):
        index = preview.build_local_api_preview_index(
            sample_state(),
            include_legacy=False,
        )
        live_path = "/api/command-center/packets/command_center_live_packet"

        self.assertIn(live_path, index["index"])
        self.assertTrue(index["index"][live_path]["available"])
        self.assertEqual(index["index"][live_path]["status"], "ready")
        self.assertEqual(index["index"][live_path]["external_call_policy"], "button_gated")
        self.assertFalse(index["deepseek_called"])

    def test_get_preview_response_accepts_path_or_packet_key(self):
        by_key = preview.get_preview_response_for_path(sample_state(), "command_center_projection_packet")
        by_path = preview.get_preview_response_for_path(
            sample_state(),
            "/api/command-center/packets/command_center_projection_packet",
        )

        self.assertEqual(by_key, by_path)
        self.assertEqual(by_key["status"], "cached")
        self.assertEqual(preview.get_preview_response_for_path(sample_state(), "unknown"), {})

    def test_error_status_is_counted(self):
        state = {
            "command_center_moneyflow_packet": {
                "status": "failed",
                "last_error": "permission denied",
            }
        }
        bundle = preview.build_local_api_preview_bundle(
            state,
            packet_keys=["command_center_moneyflow_packet"],
        )

        self.assertEqual(bundle["error_count"], 1)
        self.assertFalse(bundle["responses"][0]["ok"])
        self.assertEqual(bundle["responses"][0]["status"], "error")

    def test_preview_has_no_forbidden_imports(self):
        tree = ast.parse(Path("command_center_local_api_preview.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_local_api_preview.py: {name}")


if __name__ == "__main__":
    unittest.main()
