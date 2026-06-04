import ast
import json
import unittest
from pathlib import Path

import command_center_loop_status as loop_status


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
    "command_center_service",
}


class CommandCenterLoopStatusTests(unittest.TestCase):
    def test_empty_loop_status_is_safe_and_manual_deepseek(self):
        view_model = loop_status.build_command_center_loop_status_view_model()

        self.assertEqual(view_model["title"], "决策闭环状态")
        self.assertEqual(len(view_model["items"]), 6)
        self.assertEqual(view_model["items"][-1]["key"], "deepseek")
        self.assertEqual(view_model["items"][-1]["status"], "manual")
        self.assertFalse(view_model["deepseek_called"])
        json.dumps(view_model, ensure_ascii=False)

    def test_blocked_data_capability_marks_loop_as_blocked(self):
        view_model = loop_status.build_command_center_loop_status_view_model(
            data_capability_console={
                "headline": "数据能力有 1 个阻断项，不能直接放大仓位。",
                "blocked_count": 1,
                "blocked_items": [{"label": "涨跌停/情绪", "state": "permission_denied"}],
            },
            analysis_method_packet={"market": "A股", "methods": [{"name": "趋势跟踪", "status": "通过"}]},
            projection_packet={"status": "ready"},
            strategy_packet={"status": "ready", "action": "等待"},
            decision_packet={"status": "ready", "overall_action": "只观察"},
        )

        self.assertEqual(view_model["status"], "blocked")
        self.assertEqual(view_model["items"][0]["status"], "blocked")
        self.assertIn("阻断", view_model["headline"])
        self.assertFalse(view_model["deepseek_called"])

    def test_ready_chain_keeps_deepseek_manual(self):
        view_model = loop_status.build_command_center_loop_status_view_model(
            data_capability_console={"ready_count": 3, "headline": "数据能力已读取，3 个接口可进入证据链。"},
            analysis_method_packet={
                "market": "ETF",
                "summary": "ETF 分析框架已有可用证据。",
                "methods": [{"name": "ETF 赛道配置", "status": "通过"}],
            },
            projection_packet={"status": "ready", "path_basis": "ETF 赛道/流动性验证"},
            strategy_packet={"status": "ready", "action": "只观察", "confidence": "中"},
            decision_packet={"status": "ready", "overall_action": "只观察", "risk_level": "中"},
        )
        by_key = {item["key"]: item for item in view_model["items"]}

        self.assertEqual(by_key["data_capability"]["status"], "ready")
        self.assertEqual(by_key["analysis_methods"]["status"], "ready")
        self.assertEqual(by_key["projection"]["status"], "ready")
        self.assertEqual(by_key["strategy_execution"]["status"], "ready")
        self.assertEqual(by_key["decision"]["status"], "ready")
        self.assertEqual(by_key["deepseek"]["status"], "manual")
        self.assertFalse(view_model["deepseek_called"])

    def test_projection_recovery_blocker_blocks_projection_link(self):
        view_model = loop_status.build_command_center_loop_status_view_model(
            projection_packet={
                "status": "ready",
                "path_recovery_impact": {"evidence_state": "blocked", "impact_text": "龙虎榜仍受限"},
            }
        )
        by_key = {item["key"]: item for item in view_model["items"]}

        self.assertEqual(by_key["projection"]["status"], "blocked")
        self.assertEqual(view_model["status"], "blocked")

    def test_recovery_center_actions_attach_to_loop_status(self):
        view_model = loop_status.build_command_center_loop_status_view_model(
            data_capability_console={
                "headline": "数据能力有 1 个阻断项，不能直接放大仓位。",
                "blocked_count": 1,
            },
            data_recovery_center={
                "decision_priority_queue": [
                    {
                        "key": "p0:command_center_dragon_tiger_packet",
                        "source_type": "next_ticket_evidence",
                        "priority_label": "P0 阻断交易判断",
                        "label": "龙虎榜",
                        "status": "permission_denied",
                        "status_label": "权限不足",
                        "action_label": "手动刷新龙虎榜",
                        "toolbox_entry": "高级工具箱 / 下一票雷达",
                        "workspace_target": "高级工具箱（旧版保留）",
                        "workspace_state_key": "workspace_mode_v2",
                        "legacy_tab_state_key": "legacy_workspace_selected_tab",
                        "legacy_tab": "下一票雷达",
                        "writes_packet": "command_center_dragon_tiger_packet",
                        "refresh_policy": "button_gated",
                    }
                ]
            },
        )

        self.assertEqual(view_model["recovery_action_count"], 1)
        action = view_model["recovery_actions"][0]
        self.assertEqual(action["loop_key"], "projection")
        self.assertEqual(action["legacy_tab"], "下一票雷达")
        self.assertEqual(action["writes_packet"], "command_center_dragon_tiger_packet")
        self.assertEqual(action["external_call_policy"], "navigation_only")
        self.assertFalse(action["deepseek_called"])
        by_key = {item["key"]: item for item in view_model["items"]}
        self.assertEqual(by_key["projection"]["recovery_action_count"], 1)
        self.assertIn("龙虎榜", view_model["recovery_summary"])

    def test_analysis_methods_unknown_market_stays_waiting(self):
        view_model = loop_status.build_command_center_loop_status_view_model(
            analysis_method_packet={"market": "未知", "methods": [{"name": "趋势跟踪", "status": "待验证"}]}
        )
        by_key = {item["key"]: item for item in view_model["items"]}

        self.assertEqual(by_key["analysis_methods"]["status"], "waiting")
        self.assertIn("待验证", by_key["analysis_methods"]["status_label"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_loop_status.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_loop_status.py: {name}")


if __name__ == "__main__":
    unittest.main()
