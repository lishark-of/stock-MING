import ast
import json
import unittest
from pathlib import Path

import command_center_data_gap_report as report


class CommandCenterDataGapReportTests(unittest.TestCase):
    def test_empty_input_is_safe_and_does_not_imply_refresh(self):
        packet = report.build_command_center_data_gap_report()

        self.assertEqual(packet["status"], "unknown")
        self.assertEqual(packet["trust_level"], "unknown")
        self.assertIn("不会自动请求", packet["summary"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_capability_states_are_grouped_for_decision_use(self):
        packet = report.build_command_center_data_gap_report(
            data_capability_packet={
                "source": "Unified data capability",
                "items": [
                    {"provider": "Tushare", "section": "moneyflow", "label": "个股资金流", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                    {"provider": "Tushare", "section": "margin", "label": "融资融券", "api": "margin_detail", "capability_state": "permission_denied", "status": "权限不足"},
                    {"provider": "Tushare", "section": "limit_emotion", "label": "涨跌停/情绪", "api": "limit_cpt_list", "capability_state": "disabled_this_session", "status": "本会话跳过"},
                    {"provider": "Supabase", "section": "brain_memory", "label": "brain_memory", "api": "brain_memory", "capability_state": "not_configured", "status": "未配置"},
                ],
            }
        )

        self.assertEqual(packet["available_count"], 1)
        self.assertEqual(packet["restricted_count"], 3)
        self.assertEqual(packet["trust_level"], "low")
        self.assertFalse(packet["usable_for_decision"])
        self.assertTrue(any("融资融券权限不足" in item for item in packet["next_manual_checks"]))
        self.assertTrue(any("涨跌停/情绪本会话跳过" in item for item in packet["next_manual_checks"]))
        self.assertIn("Supabase", json.dumps(packet, ensure_ascii=False))

    def test_facts_and_refresh_errors_are_visible(self):
        packet = report.build_command_center_data_gap_report(
            facts_packet={
                "items": [
                    {"key": "moneyflow", "label": "个股资金流", "state": "available", "status": "通过"},
                    {"key": "dragon_tiger", "label": "龙虎榜", "state": "empty_recent", "status": "近期无数据"},
                ],
                "next_manual_checks": ["龙虎榜近期无记录"],
            },
            refresh_summary={
                "errors": [
                    {"module": "下一票雷达", "message": "scan failed", "source": "unit", "updated_at": "2026-06-03T10:00:00"},
                ]
            },
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertIn("龙虎榜", dumped)
        self.assertIn("下一票雷达", dumped)
        self.assertEqual(packet["failed_count"], 1)
        self.assertTrue(any("刷新失败" in item for item in packet["next_manual_checks"]))
        self.assertFalse(packet["deepseek_called"])

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_data_gap_report.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        forbidden = {
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

        self.assertTrue(forbidden.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
