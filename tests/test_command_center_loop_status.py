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

    def test_provider_cockpit_blocks_loop_and_preserves_navigation_recovery(self):
        view_model = loop_status.build_command_center_loop_status_view_model(
            provider_data_capability_cockpit={
                "status": "blocked",
                "summary": "Tushare / AkShare / yfinance / Supabase｜可用 1｜受限 2｜需手动 1｜缓存/待验证 1",
                "safe_mode_text": "这里只读取本地数据能力 packet；不会自动调用外部接口。",
                "providers": [
                    {"provider": "Tushare", "status": "blocked"},
                    {"provider": "AkShare", "status": "partial"},
                    {"provider": "yfinance", "status": "partial"},
                    {"provider": "Supabase", "status": "blocked"},
                ],
                "recovery_actions": [
                    {
                        "key": "provider_cockpit:Tushare",
                        "provider": "Tushare",
                        "api": "margin_detail",
                        "label": "Tushare",
                        "status": "blocked",
                        "status_label": "受限",
                        "action_label": "手动检测 Tushare 专业接口",
                        "legacy_tab": "数据源体检",
                        "writes_packet": "command_center_data_capability_packet",
                        "refresh_policy": "button_gated",
                    }
                ],
            }
        )
        by_key = {item["key"]: item for item in view_model["items"]}
        action = view_model["recovery_actions"][0]

        self.assertEqual(view_model["status"], "blocked")
        self.assertEqual(by_key["provider_data_capability"]["status"], "blocked")
        self.assertEqual(by_key["provider_data_capability"]["provider_count"], 4)
        self.assertIn("Tushare / AkShare / yfinance / Supabase", by_key["provider_data_capability"]["summary"])
        self.assertEqual(action["loop_key"], "provider_data_capability")
        self.assertEqual(action["loop_label"], "数据源能力")
        self.assertEqual(action["provider"], "Tushare")
        self.assertEqual(action["external_call_policy"], "navigation_only")
        self.assertFalse(action["deepseek_called"])
        self.assertIn("数据源能力", view_model["recovery_summary"])
        json.dumps(view_model, ensure_ascii=False)

    def test_old_workspace_packet_bridge_blocks_loop_when_legacy_packets_are_missing(self):
        view_model = loop_status.build_command_center_loop_status_view_model(
            old_workspace_packet_bridge={
                "status": "blocked",
                "summary": "已回流 1｜使用缓存 0｜仍阻断 1｜待回流 2",
                "safe_mode_text": "这里只读取旧版迁移地图、本地 packet 和恢复状态；不会自动调用 DeepSeek。",
                "items": [
                    {
                        "label": "融资 ETF",
                        "bridge_status": "blocked",
                        "bridge_label": "权限不足",
                        "action_label": "打开融资 ETF",
                        "toolbox_entry": "高级工具箱 / 融资 ETF",
                        "navigation_label": "主导航切到高级工具箱（旧版保留）→ 高级工具模块选择融资 ETF；手动执行后回流 command_center_margin_packet。",
                        "legacy_tab": "融资 ETF",
                        "writes_packet": "command_center_margin_packet",
                        "decision_guardrail": "融资融券未恢复前不能支持加融资。",
                    },
                    {
                        "label": "下一票雷达",
                        "bridge_status": "recovered",
                        "writes_packet": "command_center_radar_packet",
                    },
                    {
                        "label": "量化推演",
                        "bridge_status": "waiting",
                        "bridge_label": "待回流",
                        "action_label": "打开量化推演",
                        "toolbox_entry": "高级工具箱 / 量化推演",
                        "legacy_tab": "量化推演",
                        "writes_packet": "command_center_quant_packet",
                    },
                ],
            }
        )
        by_key = {item["key"]: item for item in view_model["items"]}
        actions_by_packet = {item["writes_packet"]: item for item in view_model["recovery_actions"]}

        self.assertEqual(view_model["status"], "blocked")
        self.assertEqual(by_key["old_workspace_packets"]["status"], "blocked")
        self.assertEqual(by_key["old_workspace_packets"]["bridge_item_count"], 3)
        self.assertEqual(by_key["old_workspace_packets"]["blocked_bridge_count"], 1)
        self.assertEqual(by_key["old_workspace_packets"]["waiting_bridge_count"], 1)
        self.assertEqual(by_key["old_workspace_packets"]["recovered_bridge_count"], 1)
        self.assertEqual(by_key["old_workspace_packets"]["recovery_action_count"], 2)
        self.assertEqual(view_model["recovery_action_count"], 2)
        self.assertIn("command_center_margin_packet", actions_by_packet)
        self.assertIn("command_center_quant_packet", actions_by_packet)
        self.assertNotIn("command_center_radar_packet", actions_by_packet)
        self.assertEqual(actions_by_packet["command_center_margin_packet"]["loop_key"], "old_workspace_packets")
        self.assertEqual(actions_by_packet["command_center_margin_packet"]["loop_label"], "旧能力回流")
        self.assertEqual(actions_by_packet["command_center_margin_packet"]["toolbox_entry"], "高级工具箱 / 融资 ETF")
        self.assertIn("高级工具箱", actions_by_packet["command_center_margin_packet"]["navigation_label"])
        self.assertIn("不能支持加融资", actions_by_packet["command_center_margin_packet"]["decision_impact"])
        self.assertEqual(actions_by_packet["command_center_margin_packet"]["external_call_policy"], "navigation_only")
        self.assertEqual(actions_by_packet["command_center_margin_packet"]["refresh_policy"], "button_gated")
        self.assertIn("旧工具能力", by_key["old_workspace_packets"]["decision_guardrail"])
        self.assertIn("旧能力回流", view_model["recovery_summary"])
        self.assertFalse(view_model["deepseek_called"])
        self.assertTrue(all(item["deepseek_called"] is False for item in view_model["recovery_actions"]))
        json.dumps(view_model, ensure_ascii=False)

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

    def test_candidate_execution_evidence_enters_loop_before_strategy(self):
        view_model = loop_status.build_command_center_loop_status_view_model(
            candidate_execution_evidence_overview={
                "headline": "候选执行证据需复核",
                "tone": "stale",
                "summary": "已验证 1｜需复核 1｜阻断 0｜待验证 0",
                "stage_text": "下一票/ETF 证据 → 趋势推演 → 策略执行 → 今日总决策",
                "decision_guardrail": "候选票和 ETF 证据未验证前不能作为交易依据。",
                "items": [
                    {"key": "next_ticket_radar", "verification_status": "待验证"},
                    {"key": "margin_etf", "verification_status": "已验证"},
                ],
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            },
            strategy_packet={"status": "ready", "action": "只观察"},
        )
        keys = [item["key"] for item in view_model["items"]]
        by_key = {item["key"]: item for item in view_model["items"]}

        self.assertIn("candidate_execution_evidence", keys)
        self.assertLess(keys.index("candidate_execution_evidence"), keys.index("strategy_execution"))
        self.assertEqual(by_key["candidate_execution_evidence"]["status"], "stale")
        self.assertIn("需复核", by_key["candidate_execution_evidence"]["summary"])
        self.assertIn("下一票/ETF", by_key["candidate_execution_evidence"]["stage_text"])
        self.assertEqual(by_key["candidate_execution_evidence"]["source_item_count"], 2)
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
