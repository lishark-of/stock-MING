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

    def test_position_context_adds_cost_line_margin_and_path_pnl(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "risk_level": "中", "updated_at": "2026-06-01T09:30:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            home_snapshot={
                "holding_action": {
                    "ticker": "002008.SZ",
                    "name": "大族激光",
                    "shares": 3000,
                    "cost": 98,
                    "current_price": 127.87,
                    "investment_horizon": "短中期",
                },
                "margin_etf_summary": {"current_margin_ratio": 30, "recommended_margin_ratio": 20},
            },
        )

        context = packet["position_context"]
        self.assertEqual(packet["unit"], "price")
        self.assertEqual(context["ticker"], "002008.SZ")
        self.assertEqual(context["cost_amount"], 294000)
        self.assertEqual(context["margin_ratio_pct"], 30)
        self.assertEqual({item["key"] for item in packet["reference_lines"]}, {"current_price", "cost_line"})
        self.assertIn("融资比例 30%", packet["position_context_summary"])
        self.assertIsNotNone(packet["paths"][0]["target_pnl_amount"])
        self.assertIn("不新增融资追高", packet["paths"][0]["risk"])
        self.assertFalse(packet["deepseek_called"])

    def test_missing_current_price_uses_normalized_projection_not_cost_price(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "等待", "updated_at": "2026-06-01T09:30:00"},
            home_snapshot={
                "holding_action": {
                    "ticker": "688041.SH",
                    "shares": 500,
                    "cost": 120,
                    "investment_horizon": "短中期",
                }
            },
        )

        self.assertEqual(packet["unit"], "index")
        self.assertEqual(packet["base_value"], 100.0)
        self.assertEqual(packet["position_context"]["price_basis"], "normalized")
        self.assertEqual(packet["reference_lines"][0]["label"], "归一化基准")
        self.assertIn("当前价未刷新", packet["position_context_summary"])
        self.assertIn("归一化路径", packet["paths"][0]["action"])
        self.assertIn("归一化", packet["paths"][0]["target_label"])
        self.assertIsNone(packet["paths"][0]["target_pnl_amount"])

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

    def test_recovered_limit_and_chip_evidence_surface_in_projection_path_notes(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            evidence_radar_packet={
                "decision_summary": "支持 2｜阻断 0｜缓存 0｜缺失 0",
                "support_items": [
                    {"key": "limit_emotion", "label": "涨跌停/情绪", "headline": "接近涨停/追高区"},
                    {"key": "chip_radar", "label": "筹码/胜率", "headline": "获利盘压力偏高"},
                ],
            },
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertIn("旧能力证据：涨跌停/情绪已回流", packet["path_basis"])
        self.assertIn("筹码/胜率已回流", packet["path_basis"])
        self.assertIn("旧能力已验证", packet["paths"][0]["trigger"])
        self.assertIn("追高和涨跌停情绪边界", packet["paths"][0]["trigger"])
        self.assertIn("压力位、获利盘和胜率口径", packet["paths"][1]["trigger"])
        self.assertIn("涨跌停/情绪只验证短线热度", packet["paths"][2]["risk_note"])
        self.assertIn("筹码/胜率只验证压力", packet["paths"][2]["risk_note"])
        self.assertIn("接近涨停/追高区", dumped)
        self.assertFalse(packet["deepseek_called"])

    def test_missing_limit_and_chip_evidence_keep_projection_defensive(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            evidence_radar_packet={
                "decision_summary": "支持 0｜阻断 1｜缓存 0｜缺失 1",
                "blocker_items": [
                    {"key": "limit_emotion", "label": "涨跌停/情绪", "status_label": "权限不足"},
                ],
                "missing_items": [
                    {"key": "chip_radar", "label": "筹码/胜率", "status_label": "待验证"},
                ],
            },
        )
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertIn("涨跌停/情绪仍受限", packet["path_basis"])
        self.assertIn("筹码/胜率待验证", packet["path_basis"])
        self.assertIn("旧能力待验证限制乐观路径", packet["paths"][0]["risk_note"])
        self.assertIn("不能确认题材温度", packet["paths"][0]["risk_note"])
        self.assertIn("旧能力缺口触发谨慎边界", packet["paths"][2]["trigger"])
        self.assertIn("不能把压力位或胜率写成已验证依据", dumped)
        self.assertFalse(packet["deepseek_called"])

    def test_a_share_evidence_status_groups_surface_on_projection_confidence(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            evidence_radar_packet={
                "decision_summary": "支持 2｜阻断 1｜缓存 1｜缺失 2",
                "evidence_status_groups": [
                    {"key": "recovered", "label": "已回流", "count": 2, "tone": "ready", "labels_text": "个股资金流、公告/硬风险"},
                    {"key": "blocked", "label": "仍受限", "count": 1, "tone": "failed", "labels_text": "龙虎榜"},
                    {"key": "cached", "label": "使用缓存", "count": 1, "tone": "stale", "labels_text": "融资融券"},
                    {"key": "manual", "label": "待手动", "count": 2, "tone": "missing", "labels_text": "筹码/胜率、涨跌停/情绪"},
                ],
            },
        )
        confidence = projection.build_projection_confidence_summary(packet)
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["path_evidence_group_status"], "blocked")
        self.assertEqual(packet["path_evidence_group_label"], "证据分组受限")
        self.assertEqual(packet["path_evidence_group_summary"], "已回流 2｜仍受限 1｜缓存 1｜待手动 2")
        self.assertIn("证据分组：已回流 2｜仍受限 1｜缓存 1｜待手动 2", packet["path_basis"])
        self.assertEqual(confidence["status"], "blocked")
        self.assertIn("证据分组受限", json.dumps(confidence["blocker_items"], ensure_ascii=False))
        self.assertIn("龙虎榜", dumped)
        self.assertIn("筹码/胜率", dumped)
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(confidence["deepseek_called"])

    def test_a_share_evidence_group_summary_falls_back_to_evidence_lists(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "等待", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            evidence_radar_packet={
                "support_items": [{"label": "个股资金流"}, {"label": "公告/硬风险"}],
                "cached_items": [{"label": "融资融券"}],
                "missing_items": [{"label": "龙虎榜"}],
            },
        )

        self.assertEqual(packet["path_evidence_group_status"], "partial")
        self.assertIn("已回流 2｜仍受限 0｜缓存 1｜待手动 1", packet["path_evidence_group_summary"])
        self.assertIn("证据分组：已回流 2", packet["path_basis"])
        self.assertFalse(packet["deepseek_called"])

    def test_latest_recovery_impact_enriches_a_share_projection_paths(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            evidence_radar_packet={
                "decision_summary": "支持 0｜阻断 0｜缓存 0｜缺失 6",
                "latest_recovery_impact": {
                    "status": "recovered",
                    "evidence_state": "supporting",
                    "label": "个股资金流",
                    "impact_text": "个股资金流刚刚回流；可进入证据链，但执行前仍需复核交易日、来源和仓位纪律。",
                    "writes_packet": "command_center_moneyflow_packet",
                    "external_call_policy": "button_gated",
                    "deepseek_called": False,
                },
            },
        )

        self.assertIn("最近恢复：个股资金流 supporting", packet["path_basis"])
        self.assertIn("最近恢复支持乐观路径", packet["paths"][0]["trigger"])
        self.assertIn("不等于自动加仓", packet["paths"][0]["risk_note"])
        self.assertEqual(packet["paths"][0]["latest_recovery_label"], "最近恢复已回流")
        self.assertIn("个股资金流刚刚回流", packet["path_recovery_impact_summary"])
        self.assertFalse(packet["path_recovery_impact"]["deepseek_called"])

    def test_blocked_recovery_impact_keeps_projection_defensive(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            evidence_radar_packet={
                "decision_summary": "支持 0｜阻断 1｜缓存 0｜缺失 5",
                "latest_recovery_impact": {
                    "status": "blocked",
                    "evidence_state": "blocked",
                    "label": "涨跌停/情绪",
                    "impact_text": "涨跌停/情绪恢复仍受限；证据门槛维持阻断，不能把缺失数据当成利好。",
                    "writes_packet": "command_center_limit_emotion_packet",
                    "external_call_policy": "button_gated",
                    "deepseek_called": False,
                },
            },
        )

        self.assertIn("最近恢复：涨跌停/情绪 blocked", packet["path_basis"])
        self.assertIn("最近恢复受限压制乐观路径", packet["paths"][0]["trigger"])
        self.assertIn("不能作为加仓依据", packet["paths"][0]["risk_note"])
        self.assertEqual(packet["paths"][2]["latest_recovery_label"], "最近恢复阻断")
        self.assertFalse(packet["deepseek_called"])

    def test_projection_confidence_summary_marks_blockers_and_guardrail(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            evidence_radar_packet={
                "decision_summary": "支持 0｜阻断 1｜缓存 0｜缺失 5",
                "latest_recovery_impact": {
                    "status": "blocked",
                    "evidence_state": "blocked",
                    "label": "涨跌停/情绪",
                    "impact_text": "涨跌停/情绪恢复仍受限。",
                    "external_call_policy": "button_gated",
                    "deepseek_called": False,
                },
            },
        )
        summary = projection.build_projection_confidence_summary(packet)

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["label"], "路径受限")
        self.assertEqual(summary["tone"], "danger")
        self.assertIn("不能把乐观路径当作加仓依据", summary["guardrail"])
        self.assertIn("涨跌停/情绪", json.dumps(summary["blocker_items"], ensure_ascii=False))
        self.assertFalse(summary["deepseek_called"])

    def test_projection_confidence_summary_marks_partial_when_recovery_is_pending(self):
        summary = projection.build_projection_confidence_summary(
            {
                "status": "ready",
                "path_basis": "A股证据雷达：支持 0｜阻断 0｜缓存 0｜缺失 6",
                "path_recovery_impact": {
                    "evidence_state": "missing",
                    "label": "龙虎榜",
                    "impact_text": "龙虎榜恢复结果待验证。",
                    "deepseek_called": False,
                },
                "deepseek_called": False,
            }
        )

        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["label"], "路径待验证")
        self.assertIn("龙虎榜", json.dumps(summary["pending_items"], ensure_ascii=False))

    def test_legacy_decision_chain_blocks_projection_confidence(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            home_snapshot={
                "timestamp": "2026-06-01T10:00:00",
                "legacy_decision_chain_summary": {
                    "status": "blocked",
                    "headline": "旧能力仍有阻断项",
                    "summary": "已验证 3｜缓存辅助 2｜阻断决策 1｜待验证 3",
                    "priority_items": [
                        {
                            "label": "量化推演",
                            "decision_chain_state": "blocked",
                            "state_label": "阻断决策",
                        }
                    ],
                },
            },
        )
        confidence = projection.build_projection_confidence_summary(packet)

        self.assertEqual(packet["path_legacy_decision_chain_status"], "blocked")
        self.assertIn("旧能力链：已验证 3", packet["path_basis"])
        self.assertIn("旧能力阻断压制乐观路径", packet["paths"][0]["trigger"])
        self.assertIn("量化推演", packet["paths"][0]["risk_note"])
        self.assertEqual(confidence["status"], "blocked")
        self.assertIn("旧能力仍有阻断项", json.dumps(confidence["blocker_items"], ensure_ascii=False))
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(confidence["deepseek_called"])

    def test_legacy_decision_chain_ready_supports_projection_confidence(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "等待", "confidence": "低"},
            home_snapshot={
                "timestamp": "2026-06-01T10:00:00",
                "legacy_decision_chain_summary": {
                    "status": "ready",
                    "headline": "旧能力可进入决策链",
                    "summary": "已验证 9｜缓存辅助 0｜阻断决策 0｜待验证 0",
                    "priority_items": [],
                },
            },
        )
        confidence = projection.build_projection_confidence_summary(packet)

        self.assertEqual(packet["path_legacy_decision_chain_status"], "ready")
        self.assertIn("旧能力链已验证", packet["paths"][0]["trigger"])
        self.assertIn("旧能力可进入决策链", json.dumps(confidence["support_items"], ensure_ascii=False))
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
                    {
                        "label": "龙虎榜",
                        "recovery_state": "blocked",
                        "status_label": "权限不足",
                        "tone": "failed",
                        "root_cause_label": "接口权限不足",
                    },
                    {
                        "label": "筹码/胜率",
                        "recovery_state": "waiting",
                        "status_label": "近期无数据",
                        "tone": "missing",
                        "root_cause_label": "近五日暂无数据",
                    },
                ],
                "deepseek_called": False,
            },
        )
        joined = json.dumps(packet, ensure_ascii=False)
        confidence = projection.build_projection_confidence_summary(packet)

        self.assertIn("A股事实回流", packet["path_basis"])
        self.assertIn("仍受限 1", packet["path_fact_recovery_summary"])
        self.assertEqual(packet["path_fact_recovery_tone"], "failed")
        self.assertEqual(len(packet["path_fact_recovery_items"]), 3)
        self.assertEqual(
            [item["label"] for item in packet["path_fact_recovery_detail_items"]],
            ["受限事实", "待验证事实", "已回流事实"],
        )
        self.assertIn("龙虎榜｜接口权限不足", packet["path_fact_recovery_detail_items"][0]["value"])
        self.assertIn("筹码/胜率｜近五日暂无数据", packet["path_fact_recovery_detail_items"][1]["value"])
        self.assertIn("个股资金流", packet["path_fact_recovery_detail_items"][2]["guardrail"])
        self.assertIn("乐观路径仍需受限事实恢复", packet["paths"][0]["trigger"])
        self.assertIn("龙虎榜", packet["paths"][0]["trigger"])
        self.assertIn("乐观路径不能写成加仓依据", packet["paths"][0]["risk_note"])
        self.assertIn("先恢复 龙虎榜", packet["paths"][0]["fact_recovery_path_impact"])
        self.assertIn("受限事实：龙虎榜", json.dumps(confidence["blocker_items"], ensure_ascii=False))
        self.assertIn("待验证事实：筹码/胜率", json.dumps(confidence["pending_items"], ensure_ascii=False))
        self.assertIn("已回流事实：个股资金流", json.dumps(confidence["support_items"], ensure_ascii=False))
        self.assertIn("事实回流防守线", joined)
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(confidence["deepseek_called"])

    def test_data_health_ledger_enriches_projection_without_changing_path_shape(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            analysis_method_packet={"market": "A股", "summary": "A股分析框架"},
            data_health_ledger={
                "status": "blocked",
                "rows": [
                    {
                        "provider": "Tushare",
                        "api": "moneyflow",
                        "label": "个股资金流",
                        "category": "blocked",
                        "state": "permission_denied",
                        "status_label": "权限不足",
                    }
                ],
            },
        )

        self.assertEqual(len(packet["paths"]), 3)
        self.assertIn("接口健康：阻断加仓", packet["path_basis"])
        self.assertIn("受限接口压制乐观路径", packet["paths"][0]["trigger"])
        self.assertIn("不作为加仓依据", packet["paths"][0]["risk_note"])
        self.assertEqual(packet["path_data_health_impact"]["status"], "blocked")
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
        self.assertEqual(packet["path_fact_recovery_detail_items"], [])
        self.assertNotIn("A股事实回流", joined)
        self.assertNotIn("龙虎榜", joined)

    def test_tushare_health_ledger_does_not_pollute_us_projection(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "只观察", "updated_at": "2026-06-01T10:00:00"},
            analysis_method_packet={"market": "美股", "summary": "美股分析框架"},
            data_health_ledger={
                "status": "blocked",
                "rows": [
                    {
                        "provider": "Tushare",
                        "api": "moneyflow",
                        "label": "个股资金流",
                        "category": "blocked",
                        "state": "permission_denied",
                        "status_label": "权限不足",
                    }
                ],
            },
        )
        joined = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["market_type"], "美股")
        self.assertEqual(packet["path_data_health_summary"], "")
        self.assertEqual(packet["path_data_health_impact"]["status"], "missing")
        self.assertNotIn("接口健康", packet["path_basis"])
        self.assertNotIn("个股资金流", joined)

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

    def test_build_deepseek_projection_prompt_context_keeps_quant_and_discipline(self):
        context = projection.build_deepseek_projection_prompt_context(
            target="002008.SZ",
            market_type="A股",
            position_profile={"shares": 3000, "cost_price": 98, "margin_ratio_pct": 30},
            projection_packet={"base_value": 127.87, "horizon_days": 10, "paths": []},
            quant_packet={"summary": "量化推演偏谨慎"},
            discipline_packet={"summary": "跌破纪律线降风险"},
        )

        self.assertEqual(context["target"], "002008.SZ")
        self.assertEqual(context["current_price_anchor"], 127.87)
        self.assertEqual(context["position_profile"]["margin_ratio_pct"], 30)
        self.assertIn("量化推演偏谨慎", json.dumps(context["quant_packet"], ensure_ascii=False))
        self.assertIn("跌破纪律线", json.dumps(context["discipline_packet"], ensure_ascii=False))

    def test_deepseek_projection_overlay_enhances_paths_without_service_call(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "小幅进攻", "updated_at": "2026-06-01T10:00:00"},
            strategy_packet={"action": "小幅试探", "confidence": "中"},
            live_packet={"market": {"current_price": 100}},
            analysis_method_packet={"market": "A股"},
            now="2026-06-01T10:00:00",
        )
        enhanced = projection.merge_deepseek_projection_overlay(
            packet,
            {
                "summary": "量化强但纪律要求等待突破确认。",
                "probability": {"optimistic": 30, "neutral": 50, "cautious": 20},
                "paths": [
                    {
                        "name": "乐观路径",
                        "target_pct": 4,
                        "trigger": "放量站稳且纪律确认。",
                        "action": "只允许小幅试探。",
                        "risk": "融资比例较高，不追高。",
                        "rationale": "量化与纪律共振后才抬高乐观路径。",
                    },
                    {"name": "中性路径", "target_pct": 1, "trigger": "继续横盘。"},
                    {"name": "谨慎路径", "target_pct": -5, "trigger": "跌破纪律线。"},
                ],
                "quant_notes": ["量化偏强"],
                "discipline_notes": ["等待突破确认"],
                "risk_alerts": ["融资风险"],
            },
            now="2026-06-01T10:05:00",
        )

        self.assertTrue(enhanced["deepseek_called"])
        self.assertEqual(enhanced["deepseek_mode"], "manual_projection_overlay")
        self.assertEqual(enhanced["source"], projection.SOURCE_DEEPSEEK_OVERLAY)
        self.assertEqual(sum(path["probability"] for path in enhanced["paths"]), 100)
        self.assertIn("DeepSeek 手动增强", enhanced["path_basis"])
        self.assertIn("量化强", enhanced["deepseek_projection_summary"])
        self.assertIn("量化与纪律共振", enhanced["paths"][0]["deepseek_rationale"])
        self.assertGreater(enhanced["paths"][0]["points"][-1]["value"], enhanced["base_value"])
        self.assertTrue(enhanced["deepseek_projection"].get("manual_trigger"))

    def test_deepseek_projection_overlay_clamps_extreme_curve_points(self):
        packet = projection.build_projection_packet(
            decision_packet={"overall_action": "等待", "updated_at": "2026-06-01T10:00:00"},
            live_packet={"market": {"current_price": 100}},
            now="2026-06-01T10:00:00",
        )
        enhanced = projection.merge_deepseek_projection_overlay(
            packet,
            {
                "summary": "极端输出应被夹住。",
                "paths": [
                    {"name": "乐观路径", "probability": 500, "points": [{"t": 0, "value": 100}, {"t": 10, "value": 9999}]},
                    {"name": "中性路径", "probability": 0, "target_pct": 99},
                    {"name": "谨慎路径", "probability": -30, "target_pct": -99},
                ],
            },
            now="2026-06-01T10:05:00",
        )

        self.assertEqual(sum(path["probability"] for path in enhanced["paths"]), 100)
        self.assertLessEqual(enhanced["paths"][0]["points"][-1]["value"], enhanced["base_value"] * 1.28)
        self.assertLessEqual(enhanced["paths"][1]["points"][-1]["value"], enhanced["base_value"] * 1.18)
        self.assertGreaterEqual(enhanced["paths"][2]["points"][-1]["value"], enhanced["base_value"] * 0.82)

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
