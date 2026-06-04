import ast
import json
import unittest
from pathlib import Path

import command_center_legacy_migration_map as migration


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


def sample_data_capability_packet():
    return {
        "source": "Unified data capability",
        "items": [
            {
                "provider": "Tushare",
                "api": "moneyflow",
                "label": "个股资金流",
                "capability_state": "available",
                "status": "可用",
            },
            {
                "provider": "Tushare",
                "api": "margin_detail",
                "label": "融资融券",
                "capability_state": "permission_denied",
                "status": "权限不足",
            },
            {
                "provider": "Tushare",
                "api": "limit_cpt_list",
                "label": "涨跌停/情绪",
                "capability_state": "disabled_this_session",
                "status": "本会话跳过",
            },
            {
                "provider": "AkShare",
                "api": "akshare_manual_refresh",
                "label": "AkShare 重型刷新",
                "capability_state": "requires_manual_refresh",
                "status": "需要手动刷新",
            },
        ],
    }


class CommandCenterLegacyMigrationMapTests(unittest.TestCase):
    def test_extract_packet_targets_keeps_command_center_and_legacy_targets(self):
        targets = migration.extract_packet_targets(
            "legacy_margin_etf_allocation_result / command_center_etf_packet / Supabase capability"
        )

        self.assertEqual(targets, ["legacy_margin_etf_allocation_result", "command_center_etf_packet"])

    def test_build_map_is_json_friendly_and_manual_only(self):
        packet = migration.build_legacy_migration_map(
            {
                "command_center_moneyflow_packet": {
                    "status": "ready",
                    "data_status": "ready",
                }
            },
            data_capability_packet=sample_data_capability_packet(),
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["title"], "旧版能力迁移地图")
        self.assertFalse(packet["deepseek_called"])
        self.assertEqual(packet["external_call_policy"], "not_triggered")
        self.assertIn("不会自动调用 DeepSeek", packet["safe_mode_text"])
        self.assertIn("融资融券", dumped)
        self.assertIn("权限不足", dumped)
        self.assertIn("涨跌停", dumped)
        self.assertIn("本会话跳过", dumped)
        self.assertIn("Tushare token 可用不等于", dumped)

    def test_packet_ready_and_blocked_states_are_separate(self):
        packet = migration.build_legacy_migration_map(
            {
                "command_center_market_packet": {"status": "ready", "data_status": "ready"},
                "command_center_etf_packet": {"status": "ready", "data_status": "cached"},
            },
            data_capability_packet=sample_data_capability_packet(),
        )
        by_key = {item["key"]: item for item in packet["items"]}
        lane_counts = {lane["key"]: lane["count"] for lane in packet["lanes"]}

        self.assertEqual(by_key["today_pool"]["migration_state"], "packet_ready")
        self.assertEqual(by_key["margin_etf"]["migration_state"], "blocked")
        self.assertEqual(by_key["margin_etf"]["data_status_label"], "权限不足")
        self.assertGreaterEqual(lane_counts["blocked"], 1)
        self.assertGreaterEqual(lane_counts["packet_ready"], 1)

    def test_filtering_keeps_next_ticket_mapping(self):
        packet = migration.build_legacy_migration_map(keys=["next_ticket_radar"])
        item = packet["items"][0]

        self.assertEqual(item["key"], "next_ticket_radar")
        self.assertIn("command_center_radar_packet", item["command_center_packets"])
        self.assertEqual(item["trigger_policy"], "button_gated")
        self.assertEqual(item["deepseek_policy"], "manual_only")
        self.assertFalse(item["deepseek_called"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_legacy_migration_map.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        self.assertTrue(FORBIDDEN_IMPORTS.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
