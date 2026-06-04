import ast
import json
import unittest
from pathlib import Path

import command_center_packet_registry as registry


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


class CommandCenterPacketRegistryTests(unittest.TestCase):
    def test_registry_is_json_friendly(self):
        packet = registry.build_command_center_packet_registry()
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertIn("command_center_home_snapshot", dumped)
        self.assertIn("command_center_projection_packet", dumped)
        self.assertTrue(packet["safe_mode"]["opens_page_without_refresh"])

    def test_core_command_loop_packets_are_registered(self):
        keys = {item["packet_key"] for item in registry.list_command_center_packets()}

        self.assertIn("command_center_live_packet", keys)
        self.assertIn("strategy_execution_packet", keys)
        self.assertIn("command_center_decision_packet", keys)
        self.assertIn("command_center_projection_packet", keys)
        self.assertIn("command_center_analysis_method_packet", keys)
        self.assertIn("command_center_refresh_summary", keys)

    def test_legacy_a_share_evidence_packets_are_manual_or_derived(self):
        for key in [
            "command_center_moneyflow_packet",
            "command_center_dragon_tiger_packet",
            "command_center_margin_packet",
            "command_center_limit_emotion_packet",
            "command_center_chip_packet",
            "command_center_hard_risk_packet",
        ]:
            spec = registry.get_command_center_packet_spec(key)
            self.assertEqual(spec["area"], "a_share_evidence")
            self.assertIn(spec["refresh_policy"], {"manual_recovery", "derived_display"})
            self.assertIn(spec["external_call_policy"], {"button_gated", "not_triggered"})
            self.assertEqual(spec["deepseek_policy"], "never")

    def test_decision_priority_queue_is_recovery_derived_packet(self):
        spec = registry.get_command_center_packet_spec("command_center_decision_priority_queue")

        self.assertEqual(spec["area"], "recovery")
        self.assertEqual(spec["refresh_policy"], "derived_display")
        self.assertEqual(spec["external_call_policy"], "not_triggered")
        self.assertEqual(spec["deepseek_policy"], "never")
        self.assertFalse(spec["writes_session_state"])
        self.assertIn("P0/P1/P2", spec["description"])

    def test_recovery_result_timeline_is_read_only_recovery_packet(self):
        spec = registry.get_command_center_packet_spec("command_center_recovery_result_timeline")

        self.assertEqual(spec["area"], "recovery")
        self.assertEqual(spec["refresh_policy"], "derived_display")
        self.assertEqual(spec["external_call_policy"], "not_triggered")
        self.assertEqual(spec["deepseek_policy"], "never")
        self.assertFalse(spec["writes_session_state"])
        self.assertIn("时间线", spec["description"])

    def test_data_health_visibility_summary_is_read_only_governance_packet(self):
        spec = registry.get_command_center_packet_spec("command_center_data_health_visibility_summary")

        self.assertEqual(spec["area"], "data_governance")
        self.assertEqual(spec["refresh_policy"], "derived_display")
        self.assertEqual(spec["external_call_policy"], "not_triggered")
        self.assertEqual(spec["deepseek_policy"], "never")
        self.assertFalse(spec["writes_session_state"])
        self.assertIn("权限不足", spec["description"])

    def test_data_health_timeline_is_read_only_governance_packet(self):
        spec = registry.get_command_center_packet_spec("command_center_data_health_timeline")

        self.assertEqual(spec["area"], "data_governance")
        self.assertEqual(spec["refresh_policy"], "derived_display")
        self.assertEqual(spec["external_call_policy"], "not_triggered")
        self.assertEqual(spec["deepseek_policy"], "never")
        self.assertFalse(spec["writes_session_state"])
        self.assertIn("最近成功", spec["description"])
        self.assertIn("为什么以前可用但现在搜不到", spec["description"])

    def test_local_api_paths_are_stable_and_unique(self):
        api_map = registry.build_local_api_packet_map()
        paths = [item["path"] for item in api_map.values()]

        self.assertEqual(len(paths), len(set(paths)))
        for key, item in api_map.items():
            self.assertTrue(item["path"].startswith("/api/command-center/packets/"))
            self.assertTrue(item["path"].endswith(key))
            self.assertIn("refresh_policy", item)

    def test_helpers_return_copies(self):
        spec = registry.get_command_center_packet_spec("command_center_live_packet")
        spec["label"] = "mutated"

        fresh = registry.get_command_center_packet_spec("command_center_live_packet")
        self.assertNotEqual(fresh["label"], "mutated")
        self.assertEqual(registry.get_command_center_packet_spec("missing_packet"), {})

    def test_list_filters_area_and_legacy(self):
        command_loop = registry.list_command_center_packets(area="command_loop")
        modern = registry.list_command_center_packets(include_legacy=False)

        self.assertTrue(command_loop)
        self.assertTrue(all(item["area"] == "command_loop" for item in command_loop))
        self.assertTrue(all(item["area"] not in {"legacy_workspace", "a_share_evidence", "recovery"} for item in modern))

    def test_summary_exposes_no_auto_deepseek_or_external_calls(self):
        summary = registry.packet_registry_summary()

        self.assertGreater(summary["packet_count"], 10)
        self.assertEqual(summary["deepseek_auto_count"], 0)
        self.assertEqual(summary["external_auto_count"], 0)
        self.assertGreaterEqual(summary["area_counts"]["command_loop"], 5)
        self.assertGreaterEqual(summary["area_counts"]["a_share_evidence"], 6)

    def test_view_model_is_json_friendly_and_safe_mode_first(self):
        view_model = registry.build_packet_registry_view_model(max_packets=6)
        dumped = json.dumps(view_model, ensure_ascii=False)
        safe_by_label = {item["label"]: item for item in view_model["safe_mode_items"]}

        self.assertEqual(view_model["title"], "综合中心能力地图")
        self.assertFalse(view_model["deepseek_called"])
        self.assertEqual(view_model["external_call_policy"], "not_triggered")
        self.assertEqual(safe_by_label["DeepSeek"]["value"], "0 个自动调用")
        self.assertEqual(safe_by_label["外部接口"]["value"], "0 个自动触发")
        self.assertIn("Local API", safe_by_label)
        self.assertLessEqual(len(view_model["packet_items"]), 6)
        self.assertIn("command_center_live_packet", dumped)
        self.assertIn("按钮触发", dumped)

    def test_view_model_packet_items_have_display_labels(self):
        view_model = registry.build_packet_registry_view_model(max_packets=20)
        item = next(
            packet
            for packet in view_model["packet_items"]
            if packet["packet_key"] == "command_center_projection_packet"
        )

        self.assertEqual(item["area_label"], "决策闭环")
        self.assertEqual(item["refresh_policy_label"], "展示派生")
        self.assertEqual(item["external_call_label"], "不触发外部接口")
        self.assertEqual(item["deepseek_label"], "不调用 DeepSeek")

    def test_registry_has_no_forbidden_imports(self):
        tree = ast.parse(Path("command_center_packet_registry.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_packet_registry.py: {name}")


if __name__ == "__main__":
    unittest.main()
