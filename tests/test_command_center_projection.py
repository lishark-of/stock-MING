import ast
import json
import unittest
from pathlib import Path

import command_center_projection as projection


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


class CommandCenterProjectionTests(unittest.TestCase):
    def test_missing_data_outputs_waiting_fallback(self):
        packet = projection.build_projection_packet(now="2026-06-01T09:30:00")

        self.assertEqual(packet["status"], "waiting")
        self.assertTrue(packet["is_fallback"])
        self.assertIn("示例路径", packet["note"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_generates_three_paths(self):
        packet = projection.build_projection_packet(
            decision_packet={
                "status": "ready",
                "overall_action": "小幅进攻",
                "risk_level": "中",
                "market_bias": "偏强",
                "updated_at": "2026-06-01T09:30:00",
            },
            strategy_packet={
                "status": "ready",
                "action": "小幅试探",
                "confidence": "中",
            },
            now="2026-06-01T09:30:00",
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(len(packet["paths"]), 3)
        self.assertEqual([path["name"] for path in packet["paths"]], ["乐观路径", "中性路径", "谨慎路径"])

    def test_each_path_has_probability_points_action_and_trigger(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "等待", "updated_at": "2026-06-01T09:30:00"},
            strategy_packet={
                "next_5_10_day_paths": [
                    {"name": "乐观路径", "condition": "放量突破", "action": "小额试探"},
                    {"name": "中性路径", "condition": "继续横盘", "action": "只观察"},
                    {"name": "谨慎路径", "condition": "跌破纪律线", "action": "降风险"},
                ]
            },
        )

        for path in packet["paths"]:
            self.assertIn("probability", path)
            self.assertIn("points", path)
            self.assertIn("action", path)
            self.assertIn("trigger", path)
            self.assertTrue(path["points"])
            self.assertEqual(path["points"][0]["t"], 0)

    def test_deepseek_called_is_always_false_for_projection_build(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "deepseek_called": True},
            strategy_packet={"action": "等待", "deepseek_called": True},
        )

        self.assertFalse(packet["deepseek_called"])

    def test_horizon_days_is_clamped_to_five_to_ten(self):
        short = projection.build_projection_packet(horizon_days=3)
        long = projection.build_projection_packet(horizon_days=30)

        self.assertEqual(short["horizon_days"], 5)
        self.assertEqual(long["horizon_days"], 10)
        self.assertEqual(long["paths"][0]["points"][-1]["t"], 10)

    def test_cached_status_from_stale_home_snapshot(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察"},
            home_snapshot={"data_freshness": {"state": "stale"}, "timestamp": "2026-05-31T10:00:00"},
        )

        self.assertEqual(packet["status"], "cached")

    def test_fallback_tolerates_non_mapping_inputs(self):
        packet = projection.build_projection_packet(
            decision_packet=object(),
            strategy_packet=object(),
            live_packet=object(),
            home_snapshot=object(),
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(len(packet["historical"]), 11)
        self.assertEqual(len(packet["paths"]), 3)

    def test_build_from_state_reads_cached_packets(self):
        packet = projection.build_projection_packet_from_state(
            {
                "command_center_decision_packet": {"overall_action": "降风险", "updated_at": "2026-06-01T10:00:00"},
                "strategy_execution_packet": {"action": "降风险", "confidence": "低"},
            }
        )

        self.assertEqual(packet["status"], "ready")
        self.assertGreater(packet["paths"][2]["probability"], packet["paths"][0]["probability"])

    def test_a_share_analysis_guidance_enriches_path_risk_notes(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "A股")
        self.assertIn("A股资金", packet["path_basis"])
        self.assertIn("资金流改善", packet["paths"][0]["trigger"])
        self.assertIn("涨跌停", joined)
        self.assertIn("龙虎榜", joined)
        self.assertFalse(packet["deepseek_called"])

    def test_us_analysis_guidance_avoids_a_share_terms(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "美股", "summary": "美股分析框架"},
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "美股")
        self.assertIn("财报", joined)
        self.assertIn("RS", joined)
        self.assertIn("宏观利率", joined)
        self.assertNotIn("龙虎榜", joined)
        self.assertIn("无涨跌停", joined)

    def test_etf_analysis_guidance_mentions_sector_and_liquidity(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "ETF", "summary": "ETF分析框架"},
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "ETF")
        self.assertIn("赛道", joined)
        self.assertIn("回踩", joined)
        self.assertIn("流动性", joined)
        self.assertIn("持仓重叠", joined)

    def test_a_share_evidence_radar_enriches_projection_paths(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            evidence_radar_packet={
                "decision_summary": "支持 1｜阻断 1｜缓存 1｜缺失 1",
                "support_items": [{"label": "个股资金流"}],
                "blocker_items": [{"label": "硬风险/公告"}],
                "cached_items": [{"label": "融资融券"}],
                "missing_items": [{"label": "龙虎榜"}],
            },
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertIn("A股证据雷达", packet["path_basis"])
        self.assertIn("支持证据增强乐观路径", packet["paths"][0]["trigger"])
        self.assertIn("个股资金流", packet["paths"][0]["trigger"])
        self.assertIn("硬风险/公告", packet["paths"][2]["trigger"])
        self.assertIn("融资融券", packet["paths"][1]["trigger"])
        self.assertIn("龙虎榜", joined)
        self.assertIn("阻断证据", joined)
        self.assertFalse(packet["deepseek_called"])

    def test_a_share_data_capability_enriches_projection_paths(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            a_share_data_console={
                "decision_readiness_label": "阻断加仓",
                "summary": "可用 1｜受限 1｜暂无数据 1｜待手动 0",
                "groups": [
                    {"key": "permission_denied", "tone": "failed", "count": 1, "items": ["个股资金流"]},
                    {"key": "stale_or_empty", "tone": "stale", "count": 1, "items": ["龙虎榜"]},
                    {"key": "available", "tone": "ready", "count": 1, "items": ["融资融券"]},
                ],
                "deepseek_called": False,
            },
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertIn("A股数据能力", packet["path_basis"])
        self.assertIn("阻断加仓", packet["path_data_capability_summary"])
        self.assertIn("个股资金流", packet["paths"][0]["trigger"])
        self.assertIn("受限数据未恢复", packet["paths"][0]["risk_note"])
        self.assertIn("龙虎榜", packet["paths"][1]["trigger"])
        self.assertIn("数据能力防守线", joined)
        self.assertFalse(packet["deepseek_called"])

    def test_a_share_data_capability_all_available_supports_projection_basis(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            a_share_data_console={
                "decision_readiness_label": "可进入证据链",
                "summary": "可用 4｜受限 0｜暂无数据 0｜待手动 0",
                "groups": [
                    {"key": "available", "tone": "ready", "count": 4, "items": ["个股资金流", "龙虎榜", "融资融券"]},
                ],
                "deepseek_called": False,
            },
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertIn("可进入证据链", packet["path_data_capability_summary"])
        self.assertIn("A股数据能力可进入证据链", packet["paths"][0]["trigger"])
        self.assertIn("个股资金流", joined)

    def test_a_share_fact_recovery_enriches_projection_paths(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            a_share_fact_recovery_summary={
                "summary": "A股事实 5 项：已回流 2｜仍受限 1｜待验证 2",
                "tone": "failed",
                "items": [
                    {"label": "个股资金流", "recovery_state": "recovered", "status_label": "可用", "tone": "ready"},
                    {"label": "龙虎榜", "recovery_state": "blocked", "status_label": "权限不足", "tone": "failed"},
                    {"label": "筹码/胜率", "recovery_state": "waiting", "status_label": "近期无数据", "tone": "missing"},
                ],
                "deepseek_called": False,
            },
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertIn("A股事实回流", packet["path_basis"])
        self.assertIn("仍受限 1", packet["path_fact_recovery_summary"])
        self.assertEqual(packet["path_fact_recovery_tone"], "failed")
        self.assertEqual(len(packet["path_fact_recovery_items"]), 3)
        self.assertIn("乐观路径仍需受限事实恢复", packet["paths"][0]["trigger"])
        self.assertIn("龙虎榜", packet["paths"][0]["trigger"])
        self.assertIn("A股事实仍受限前", packet["paths"][0]["risk_note"])
        self.assertIn("事实回流防守线", joined)
        self.assertFalse(packet["deepseek_called"])

    def test_a_share_evidence_radar_does_not_pollute_us_projection(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "美股", "summary": "美股分析框架"},
            evidence_radar_packet={
                "decision_summary": "支持 0｜阻断 1｜缓存 0｜缺失 0",
                "blocker_items": [{"label": "龙虎榜"}],
            },
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "美股")
        self.assertEqual(packet["path_evidence_summary"], "")
        self.assertNotIn("A股证据雷达", joined)
        self.assertNotIn("龙虎榜", joined)

    def test_a_share_data_capability_does_not_pollute_us_projection(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "美股", "summary": "美股分析框架"},
            a_share_data_console={
                "decision_readiness_label": "阻断加仓",
                "summary": "可用 0｜受限 1｜暂无数据 0｜待手动 0",
                "groups": [{"key": "permission_denied", "tone": "failed", "count": 1, "items": ["龙虎榜"]}],
            },
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "美股")
        self.assertEqual(packet["path_data_capability_summary"], "")
        self.assertNotIn("A股数据能力", joined)
        self.assertNotIn("龙虎榜", joined)

    def test_a_share_fact_recovery_does_not_pollute_us_projection(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "美股", "summary": "美股分析框架"},
            a_share_fact_recovery_summary={
                "summary": "A股事实 5 项：已回流 0｜仍受限 1｜待验证 4",
                "items": [{"label": "龙虎榜", "recovery_state": "blocked", "status_label": "权限不足"}],
            },
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "美股")
        self.assertEqual(packet["path_fact_recovery_summary"], "")
        self.assertEqual(packet["path_fact_recovery_items"], [])
        self.assertNotIn("A股事实回流", joined)
        self.assertNotIn("龙虎榜", joined)

    def test_build_from_state_can_read_evidence_radar_packet(self):
        packet = projection.build_projection_packet_from_state(
            {
                "command_center_decision_packet": {"overall_action": "等待", "updated_at": "2026-06-01T10:00:00"},
                "command_center_analysis_method_packet": {"market": "A股"},
                "command_center_evidence_radar_packet": {
                    "decision_summary": "支持 1｜阻断 0｜缓存 0｜缺失 0",
                    "support_items": [{"label": "个股资金流"}],
                },
            }
        )

        self.assertIn("个股资金流", packet["paths"][0]["trigger"])
        self.assertIn("A股证据雷达", packet["path_basis"])

    def test_build_from_state_reads_home_snapshot_a_share_data_console(self):
        packet = projection.build_projection_packet_from_state(
            {
                "command_center_decision_packet": {"overall_action": "等待", "updated_at": "2026-06-01T10:00:00"},
                "command_center_analysis_method_packet": {"market": "A股"},
                "command_center_home_snapshot": {
                    "a_share_user_data_diagnostic": {
                        "status_console": {
                            "decision_readiness_label": "谨慎验证",
                            "summary": "可用 1｜受限 0｜暂无数据 1｜待手动 0",
                            "groups": [
                                {"key": "stale_or_empty", "tone": "stale", "count": 1, "items": ["龙虎榜"]},
                                {"key": "available", "tone": "ready", "count": 1, "items": ["个股资金流"]},
                            ],
                            "deepseek_called": False,
                        }
                    }
                },
            }
        )

        self.assertIn("A股数据能力", packet["path_basis"])
        self.assertIn("谨慎验证", packet["path_data_capability_summary"])
        self.assertIn("龙虎榜", packet["paths"][1]["trigger"])

    def test_build_from_state_reads_home_snapshot_a_share_fact_recovery(self):
        packet = projection.build_projection_packet_from_state(
            {
                "command_center_decision_packet": {"overall_action": "等待", "updated_at": "2026-06-01T10:00:00"},
                "command_center_analysis_method_packet": {"market": "A股"},
                "command_center_home_snapshot": {
                    "a_share_fact_recovery_summary": {
                        "summary": "A股事实 5 项：已回流 1｜仍受限 0｜待验证 4",
                        "tone": "stale",
                        "items": [
                            {"label": "个股资金流", "recovery_state": "recovered", "status_label": "可用", "tone": "ready"},
                            {"label": "龙虎榜", "recovery_state": "waiting", "status_label": "近期无数据", "tone": "missing"},
                        ],
                        "deepseek_called": False,
                    }
                },
            }
        )

        self.assertIn("A股事实回流", packet["path_basis"])
        self.assertIn("待验证 4", packet["path_fact_recovery_summary"])
        self.assertIn("龙虎榜", packet["paths"][0]["trigger"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_projection.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_projection.py: {name}")


if __name__ == "__main__":
    unittest.main()
