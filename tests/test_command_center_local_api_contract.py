import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_local_api_contract as contract


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


class CommandCenterLocalApiContractTests(unittest.TestCase):
    def test_manifest_is_json_friendly_and_read_only(self):
        manifest = contract.build_local_api_endpoint_manifest()
        dumped = json.dumps(manifest, ensure_ascii=False)

        self.assertEqual(manifest["kind"], contract.MANIFEST_KIND)
        self.assertFalse(manifest["server_started"])
        self.assertFalse(manifest["deepseek_called"])
        self.assertEqual(manifest["external_call_policy"], "not_triggered")
        self.assertGreater(manifest["endpoint_count"], 10)
        self.assertIn("/api/command-center/packets/command_center_live_packet", dumped)
        self.assertIn("/api/command-center/packets/command_center_decision_priority_queue", dumped)
        self.assertIn("/api/command-center/packets/command_center_data_health_visibility_summary", dumped)
        for endpoint in manifest["endpoints"]:
            self.assertEqual(endpoint["method"], "GET")
            self.assertTrue(endpoint["read_only"])
            self.assertTrue(endpoint["path"].startswith("/api/command-center/packets/"))
            self.assertNotEqual(endpoint["deepseek_policy"], "auto")
            self.assertNotEqual(endpoint["external_call_policy"], "auto")

    def test_manifest_can_exclude_legacy_packets(self):
        manifest = contract.build_local_api_endpoint_manifest(include_legacy=False)
        areas = {endpoint["area"] for endpoint in manifest["endpoints"]}

        self.assertNotIn("legacy_workspace", areas)
        self.assertNotIn("a_share_evidence", areas)
        self.assertIn("command_loop", areas)

    def test_packet_response_envelope_includes_registry_metadata(self):
        response = contract.build_packet_response_envelope(
            "command_center_projection_packet",
            payload={"status": "ready", "paths": [{"name": "中性路径"}]},
            status="ready",
            generated_at="2026-06-04T09:30:00",
        )

        self.assertTrue(response["ok"])
        self.assertEqual(response["kind"], contract.RESPONSE_KIND)
        self.assertEqual(response["packet_key"], "command_center_projection_packet")
        self.assertEqual(response["meta"]["area"], "command_loop")
        self.assertEqual(response["meta"]["local_api_path"], "/api/command-center/packets/command_center_projection_packet")
        self.assertEqual(response["meta"]["generated_at"], "2026-06-04T09:30:00")
        self.assertFalse(response["deepseek_called"])
        self.assertEqual(contract.validate_packet_response_envelope(response), {"valid": True, "errors": []})

    def test_blocked_status_is_valid_for_read_only_governance_packets(self):
        response = contract.build_packet_response_envelope(
            "command_center_data_health_visibility_summary",
            payload={"status": "blocked", "headline": "Tushare 拉满 ≠ 每个专业接口都有权限"},
            status="blocked",
        )

        self.assertTrue(response["ok"])
        self.assertEqual(response["status"], "blocked")
        self.assertEqual(response["meta"]["area"], "data_governance")
        self.assertTrue(contract.validate_packet_response_envelope(response)["valid"])

    def test_packet_response_redacts_secrets_without_mutating_input(self):
        payload = {
            "ticker": "002008.SZ",
            "api_key": "sk-test-secret",
            "nested": {
                "token": "tushare_token_value",
                "normal": "visible",
            },
            "items": [{"password": "secret-password"}],
        }
        before = copy.deepcopy(payload)
        response = contract.build_packet_response_envelope("command_center_live_packet", payload=payload)
        dumped = json.dumps(response, ensure_ascii=False)

        self.assertEqual(payload, before)
        self.assertIn(contract.REDACTED_VALUE, dumped)
        self.assertNotIn("sk-test-secret", dumped)
        self.assertNotIn("tushare_token_value", dumped)
        self.assertNotIn("secret-password", dumped)
        self.assertIn("visible", dumped)

    def test_unknown_packet_response_is_not_ok(self):
        response = contract.build_packet_response_envelope("missing_packet", payload={"status": "ready"})
        validation = contract.validate_packet_response_envelope(response)

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "unknown_packet")
        self.assertEqual(response["meta"]["area"], "unknown")
        self.assertTrue(validation["valid"])

    def test_error_envelope_is_safe_and_valid(self):
        response = contract.build_packet_error_envelope(
            "command_center_moneyflow_packet",
            "Tushare permission denied",
            meta={"api_key": "sk-hidden"},
        )
        dumped = json.dumps(response, ensure_ascii=False)

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["message"], "Tushare permission denied")
        self.assertNotIn("sk-hidden", dumped)
        self.assertEqual(response["meta"]["api_key"], contract.REDACTED_VALUE)
        self.assertTrue(contract.validate_packet_response_envelope(response)["valid"])

    def test_get_endpoint_contract_accepts_path_or_packet_key(self):
        by_key = contract.get_local_api_endpoint_contract("command_center_decision_packet")
        by_path = contract.get_local_api_endpoint_contract("/api/command-center/packets/command_center_decision_packet")

        self.assertEqual(by_key, by_path)
        self.assertEqual(by_key["packet_key"], "command_center_decision_packet")
        self.assertEqual(contract.get_local_api_endpoint_contract("unknown"), {})

    def test_decision_priority_queue_endpoint_is_read_only_derived_recovery(self):
        endpoint = contract.get_local_api_endpoint_contract("command_center_decision_priority_queue")

        self.assertEqual(endpoint["path"], "/api/command-center/packets/command_center_decision_priority_queue")
        self.assertEqual(endpoint["area"], "recovery")
        self.assertEqual(endpoint["refresh_policy"], "derived_display")
        self.assertEqual(endpoint["external_call_policy"], "not_triggered")
        self.assertEqual(endpoint["deepseek_policy"], "never")
        self.assertTrue(endpoint["read_only"])

    def test_validate_packet_response_envelope_reports_contract_errors(self):
        validation = contract.validate_packet_response_envelope(
            {
                "contract_version": "old",
                "kind": "wrong",
                "packet_key": "",
                "meta": [],
                "errors": {},
                "external_call_policy": "button_gated",
                "deepseek_called": True,
            }
        )

        self.assertFalse(validation["valid"])
        self.assertGreaterEqual(len(validation["errors"]), 6)

    def test_contract_has_no_forbidden_imports(self):
        tree = ast.parse(Path("command_center_local_api_contract.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_local_api_contract.py: {name}")


if __name__ == "__main__":
    unittest.main()
