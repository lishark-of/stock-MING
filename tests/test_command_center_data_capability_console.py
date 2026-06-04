import ast
import json
import unittest
from pathlib import Path

import command_center_data_capability_console as console


FORBIDDEN_IMPORTS = {
    "streamlit",
    "app",
    "tushare_adapter",
    "tushare",
    "akshare",
    "yfinance",
    "data_fetcher",
    "backtester",
    "openai",
    "command_center_service",
}


class CommandCenterDataCapabilityConsoleTests(unittest.TestCase):
    def test_empty_console_is_safe_and_manual(self):
        packet = console.build_data_capability_console_packet()

        self.assertEqual(packet["status"], "missing")
        self.assertIn("不会自动请求", packet["headline"])
        self.assertFalse(packet["provider_cards"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_console_groups_ready_blocked_manual_and_stale_queues(self):
        packet = console.build_data_capability_console_packet(
            data_capability_packet={
                "source": "Unified data capability",
                "items": [
                    {"provider": "Tushare", "api": "moneyflow", "label": "个股资金流", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "api": "margin_detail", "label": "融资融券", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "api": "top_list", "label": "龙虎榜", "capability_state": "empty_recent", "status": "近期无数据"},
                    {"provider": "AkShare", "api": "akshare_manual_refresh", "label": "AkShare 重型刷新", "capability_state": "requires_manual_refresh", "status": "需要手动刷新"},
                ],
            }
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["available_count"], 1)
        self.assertEqual(packet["blocked_count"], 1)
        self.assertEqual(packet["manual_count"], 1)
        self.assertEqual(packet["stale_count"], 1)
        self.assertIn("不能直接放大仓位", packet["headline"])
        self.assertEqual(packet["decision_readiness"], "blocked")
        self.assertEqual(packet["decision_readiness_label"], "阻断加仓")
        self.assertIn("只允许观察、降风险", packet["safe_mode_text"])
        self.assertTrue(any("融资融券" in item for item in packet["decision_blockers"]))
        self.assertTrue(any("AkShare 重型刷新" in item for item in packet["decision_blockers"]))
        self.assertTrue(any("龙虎榜" in item for item in packet["decision_blockers"]))
        self.assertEqual(packet["recovery_actions"][0]["label"], "融资融券")
        self.assertEqual(packet["recovery_actions"][0]["action_label"], "手动刷新融资融券")
        self.assertEqual(packet["recovery_actions"][0]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(packet["recovery_actions"][0]["refresh_policy"], "button_gated")
        self.assertIn("不是“没搜到行情”", packet["recovery_actions"][0]["diagnostic_answer"])
        self.assertIn("token 可用", packet["recovery_actions"][0]["diagnostic_answer"])
        self.assertIn("融资融券", packet["recovery_summary"])
        self.assertEqual(packet["provider_diagnostic_cards"][0]["provider"], "Tushare")
        self.assertIn("不是“没拉满”", packet["provider_diagnostic_cards"][0]["answer"])
        self.assertIn("个股资金流", dumped)
        self.assertIn("融资融券", dumped)
        self.assertIn("AkShare 重型刷新", dumped)
        self.assertFalse(packet["deepseek_called"])

    def test_console_can_reuse_existing_issue_explainer_packet(self):
        packet = console.build_data_capability_console_packet(
            data_issue_explainer={
                "short_answer": "接口可用也可能搜不到。",
                "items": [
                    {
                        "label": "龙虎榜",
                        "provider": "Tushare",
                        "api": "top_list",
                        "state": "empty_recent",
                        "status_label": "近期无数据",
                        "tone": "missing",
                        "meaning": "近期无记录。",
                        "decision_impact": "无记录不能写成利好。",
                        "next_action": "确认是否交易日。",
                    }
                ],
                "deepseek_called": False,
            }
        )

        self.assertEqual(packet["status"], "partial")
        self.assertEqual(packet["decision_readiness"], "caution")
        self.assertEqual(packet["decision_readiness_label"], "谨慎验证")
        self.assertEqual(packet["stale_items"][0]["label"], "龙虎榜")
        self.assertEqual(packet["short_answer"], "接口可用也可能搜不到。")
        self.assertEqual(packet["recovery_actions"][0]["label"], "龙虎榜")
        self.assertEqual(packet["recovery_actions"][0]["writes_packet"], "command_center_dragon_tiger_packet")
        self.assertIn("近窗口无记录", packet["recovery_actions"][0]["diagnostic_answer"])

    def test_console_diagnostic_answer_explains_session_skip(self):
        packet = console.build_data_capability_console_packet(
            data_issue_explainer={
                "items": [
                    {
                        "label": "涨跌停/情绪",
                        "provider": "Tushare",
                        "api": "limit_cpt_list",
                        "state": "disabled_this_session",
                        "status_label": "本会话跳过",
                        "tone": "failed",
                        "next_action": "重新检测权限。",
                    }
                ],
                "deepseek_called": False,
            }
        )
        action = packet["recovery_actions"][0]

        self.assertEqual(action["state"], "disabled_this_session")
        self.assertIn("本会话跳过重复请求", action["diagnostic_answer"])
        self.assertIn("确认接口权限恢复", action["diagnostic_answer"])
        self.assertFalse(action["deepseek_called"])

    def test_console_recovery_action_handles_supabase_configuration(self):
        packet = console.build_data_capability_console_packet(
            data_capability_packet={
                "source": "Unified data capability",
                "items": [
                    {
                        "provider": "Supabase",
                        "api": "brain_memory",
                        "label": "云端记忆",
                        "capability_state": "not_configured",
                        "status": "未配置",
                    }
                ],
            }
        )
        action = packet["recovery_actions"][0]

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(action["provider"], "Supabase")
        self.assertEqual(action["refresh_policy"], "manual_config")
        self.assertIn("检查 Supabase 本地配置", action["action_label"])
        self.assertFalse(action["deepseek_called"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_data_capability_console.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        self.assertTrue(FORBIDDEN_IMPORTS.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
