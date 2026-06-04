import ast
import json
import unittest
from pathlib import Path

import command_center_strategy_summary as summary


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
    "strategy_execution_service",
}


class CommandCenterStrategySummaryTests(unittest.TestCase):
    def test_empty_packet_uses_waiting_defaults(self):
        view_model = summary.build_strategy_summary_view_model(None)

        self.assertEqual(view_model["status"], "waiting")
        self.assertEqual(view_model["status_label"], "待生成")
        self.assertEqual(view_model["action_label"], "尚未生成")
        self.assertEqual(view_model["confidence_label"], "待生成")
        self.assertEqual(len(view_model["path_items"]), 3)
        json.dumps(view_model, ensure_ascii=False)

    def test_status_labels_cover_waiting_ready_failed(self):
        self.assertEqual(summary.strategy_status_label({"status": "waiting"}), "待生成")
        self.assertEqual(summary.strategy_status_label({"status": "ready"}), "策略建议已生成")
        self.assertEqual(summary.strategy_status_label({"status": "failed"}), "失败后缓存")

    def test_action_and_confidence_tones(self):
        self.assertEqual(summary.strategy_action_tone({"action": "等待"}), "warning")
        self.assertEqual(summary.strategy_action_tone({"action": "小幅进攻"}), "success")
        self.assertEqual(summary.strategy_action_tone({"action": "只观察"}), "warning")
        self.assertEqual(summary.strategy_action_tone({"action": "降风险"}), "danger")
        self.assertEqual(summary.strategy_action_tone({"action": "买入"}), "success")
        self.assertEqual(summary.strategy_action_tone({"action": "卖出"}), "danger")
        self.assertEqual(summary.strategy_confidence_tone({"confidence": "低"}), "muted")
        self.assertEqual(summary.strategy_confidence_tone({"confidence": "中"}), "warning")
        self.assertEqual(summary.strategy_confidence_tone({"confidence": "高"}), "success")

    def test_action_guardrails_reduce_beginner_misinterpretation(self):
        attack = summary.build_strategy_summary_view_model({"action": "小幅进攻"})
        wait = summary.build_strategy_summary_view_model({"action": "等待"})
        observe = summary.build_strategy_summary_view_model({"action": "只观察"})
        reduce = summary.build_strategy_summary_view_model({"action": "降风险"})

        self.assertIn("只允许小额试探", attack["action_guardrail"])
        self.assertIn("今天不是必须交易", wait["action_guardrail"])
        self.assertIn("今天不是必须交易", observe["action_guardrail"])
        self.assertIn("降杠杆", reduce["action_guardrail"])

    def test_strategy_boundary_text_keeps_deepseek_and_backtest_manual(self):
        view_model = summary.build_strategy_summary_view_model({})
        boundary = view_model["user_boundary_text"]

        self.assertIn("不自动调用 DeepSeek", boundary)
        self.assertIn("不自动回测", boundary)
        self.assertIn("不构成收益承诺", boundary)
        for dangerous in ["必买", "稳赚"]:
            self.assertNotIn(dangerous, " ".join([boundary, view_model["action_guardrail"]]))

    def test_missing_paths_use_default_three_paths(self):
        paths = summary.build_strategy_path_items({})

        self.assertEqual(len(paths), 3)
        self.assertEqual(paths[0]["name"], "乐观路径")
        self.assertIn("risk", paths[0])
        self.assertIn("不", paths[0]["risk"])

    def test_conditions_are_checklist_ready(self):
        items = summary.build_strategy_condition_cards({
            "add_condition": "突破关键位后小额试探。",
            "reduce_condition": "跌破纪律线先减仓。",
            "invalidation_condition": "趋势反向则失效。",
        })

        self.assertEqual([item["key"] for item in items], ["add", "reduce", "invalidation"])
        self.assertIn("小额", items[0]["check_label"])
        self.assertEqual(items[2]["tone"], "danger")

    def test_missing_discipline_and_risk_budget_are_safe(self):
        view_model = summary.build_strategy_summary_view_model({"status": "ready"})

        self.assertTrue(view_model["discipline_items"])
        self.assertTrue(view_model["risk_budget_items"])
        self.assertEqual(view_model["risk_budget_items"][0]["label"], "仓位建议")

    def test_data_status_items_cover_missing_cached_ready(self):
        items = summary.build_strategy_data_status_items({
            "data_status": {
                "quant": "ready",
                "backtest": "cached",
                "live_packet": "missing",
            }
        })
        by_key = {item["key"]: item for item in items}

        self.assertEqual(by_key["quant"]["state"], "ready")
        self.assertEqual(by_key["backtest"]["state"], "cached")
        self.assertEqual(by_key["live_packet"]["state"], "missing")
        self.assertEqual(by_key["quant"]["text"], "已就绪")
        self.assertEqual(by_key["backtest"]["text"], "使用缓存")
        self.assertEqual(by_key["live_packet"]["text"], "待刷新")

    def test_readiness_text_marks_missing_data_as_unfinished(self):
        empty = summary.build_strategy_summary_view_model({})
        partial = summary.build_strategy_summary_view_model({
            "status": "ready",
            "data_status": {
                "quant": "ready",
                "backtest": "missing",
                "live_packet": "cached",
            },
        })

        self.assertIn("待刷新", empty["readiness_text"])
        self.assertIn("数据不足", partial["readiness_text"])
        self.assertIn("纪律/回测", partial["readiness_text"])

    def test_deepseek_false_and_last_error_are_visible(self):
        view_model = summary.build_strategy_summary_view_model({
            "deepseek_called": False,
            "last_error": "timeout",
            "status": "failed",
        })

        self.assertEqual(view_model["deepseek_text"], "DeepSeek：未调用")
        self.assertEqual(view_model["last_error_text"], "timeout")
        self.assertIn("上次生成失败：timeout", view_model["warning_items"])

    def test_a_share_market_guidance_mentions_money_flow_ma_and_announcements(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "只观察"},
            analysis_method_packet={"market": "A股"},
        )
        guidance = view_model["market_method_guidance"]
        joined = json.dumps(guidance, ensure_ascii=False)

        self.assertEqual(guidance["market"], "A股")
        self.assertIn("资金流", joined)
        self.assertIn("MA20", joined)
        self.assertIn("公告", joined)

    def test_us_market_guidance_mentions_rs_earnings_and_macro_without_a_share_terms(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "只观察"},
            analysis_method_packet={"market": "美股"},
        )
        joined = json.dumps(view_model["market_method_guidance"], ensure_ascii=False)

        self.assertIn("RS", joined)
        self.assertIn("财报", joined)
        self.assertIn("宏观利率", joined)
        self.assertNotIn("龙虎榜", joined)
        self.assertNotIn("涨跌停", joined)

    def test_etf_market_guidance_mentions_sector_pullback_and_liquidity(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "只观察"},
            analysis_method_packet={"market": "ETF"},
        )
        joined = json.dumps(view_model["market_method_guidance"], ensure_ascii=False)

        self.assertIn("赛道", joined)
        self.assertIn("回踩", joined)
        self.assertIn("流动性", joined)

    def test_a_share_evidence_validation_items_block_unverified_execution(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "小幅进攻"},
            analysis_method_packet={"market": "A股"},
            evidence_radar_packet={
                "decision_summary": "支持 1｜阻断 1｜缓存 1｜缺失 1",
                "decision_evidence_queue": [
                    {
                        "key": "hard_risk",
                        "label": "硬风险/公告",
                        "priority": 1,
                        "evidence_state": "blocked",
                        "evidence_label": "阻断证据",
                        "decision_signal": "硬风险/公告失败/受限，不能支撑加仓或放大仓位。",
                    },
                    {
                        "key": "margin",
                        "label": "融资融券",
                        "priority": 2,
                        "evidence_state": "cached",
                        "evidence_label": "缓存证据",
                    },
                    {
                        "key": "dragon_tiger",
                        "label": "龙虎榜",
                        "priority": 3,
                        "evidence_state": "missing",
                        "evidence_label": "缺失证据",
                    },
                ],
            },
        )
        items = view_model["evidence_validation_items"]
        dumped = json.dumps(items, ensure_ascii=False)

        self.assertEqual(view_model["evidence_validation_summary"], "支持 1｜阻断 1｜缓存 1｜缺失 1")
        self.assertEqual(items[0]["key"], "hard_risk")
        self.assertEqual(items[0]["tone"], "danger")
        self.assertIn("不能支撑加仓", dumped)
        self.assertIn("复核 融资融券 缓存", dumped)
        self.assertIn("先补齐 龙虎榜", dumped)

    def test_a_share_evidence_radar_card_sets_strategy_execution_gate(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "小幅进攻"},
            analysis_method_packet={"market": "A股"},
            evidence_radar_packet={
                "decision_summary": "支持 1｜阻断 1｜缓存 0｜缺失 4",
                "radar_card": {
                    "status": "blocked",
                    "status_label": "阻断加仓",
                    "tone": "danger",
                    "confidence_gate": "低置信度",
                    "execution_guardrail": "公告/硬风险未排除前只能观察或降风险。",
                    "deepseek_called": False,
                },
                "decision_evidence_queue": [
                    {
                        "key": "hard_risk",
                        "label": "公告/硬风险",
                        "priority": 1,
                        "evidence_state": "blocked",
                        "decision_signal": "公告/硬风险失败/受限，不能支撑加仓。",
                    }
                ],
            },
        )

        self.assertEqual(view_model["evidence_confidence_gate"], "低置信度")
        self.assertIn("只能观察", view_model["evidence_execution_guardrail"])
        self.assertEqual(view_model["evidence_radar_card"]["status_label"], "阻断加仓")
        json.dumps(view_model, ensure_ascii=False)

    def test_a_share_evidence_status_groups_drive_strategy_condition_gate(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "小幅进攻"},
            analysis_method_packet={"market": "A股"},
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
        guidance = view_model["a_share_evidence_group_guidance"]
        dumped = json.dumps(guidance, ensure_ascii=False)

        self.assertEqual(guidance["status"], "blocked")
        self.assertEqual(guidance["tone"], "danger")
        self.assertEqual(guidance["summary"], "已回流 2｜仍受限 1｜缓存 1｜待手动 2")
        self.assertIn("不支持加仓", guidance["add_condition_guardrail"])
        self.assertIn("优先减暴露", guidance["reduce_condition_guardrail"])
        self.assertIn("本轮进攻路径失效", guidance["invalidation_guardrail"])
        self.assertIn("龙虎榜", dumped)
        self.assertIn("筹码/胜率", dumped)
        self.assertFalse(guidance["deepseek_called"])
        json.dumps(view_model, ensure_ascii=False)

    def test_a_share_evidence_group_guidance_falls_back_to_evidence_lists(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "只观察"},
            analysis_method_packet={"market": "A股"},
            evidence_radar_packet={
                "support_items": [{"label": "个股资金流"}, {"label": "公告/硬风险"}],
                "cached_items": [{"label": "融资融券"}],
                "missing_items": [{"label": "龙虎榜"}],
            },
        )
        guidance = view_model["a_share_evidence_group_guidance"]
        dumped = json.dumps(guidance, ensure_ascii=False)

        self.assertEqual(guidance["status"], "partial")
        self.assertIn("已回流 2｜仍受限 0｜缓存 1｜待手动 1", guidance["summary"])
        self.assertIn("加仓前需复核交易日", guidance["add_condition_guardrail"])
        self.assertIn("个股资金流", dumped)
        self.assertIn("龙虎榜", dumped)
        self.assertFalse(guidance["deepseek_called"])

    def test_a_share_data_capability_blocks_strategy_execution_when_restricted(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "小幅进攻"},
            analysis_method_packet={"market": "A股"},
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
        items = view_model["evidence_validation_items"]
        dumped = json.dumps(items, ensure_ascii=False)

        self.assertEqual(items[0]["key"], "a_share_data_capability")
        self.assertEqual(items[0]["tone"], "danger")
        self.assertIn("阻断加仓", view_model["a_share_data_validation_summary"])
        self.assertIn("个股资金流", dumped)
        self.assertIn("未恢复前策略只能降级", dumped)
        self.assertIn("龙虎榜", dumped)
        self.assertFalse("DeepSeek" in dumped)

    def test_data_health_ledger_blocks_strategy_execution_when_interface_restricted(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "小幅进攻"},
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
        items = view_model["evidence_validation_items"]
        dumped = json.dumps(items, ensure_ascii=False)

        self.assertIn("data_health_ledger", dumped)
        self.assertIn("接口健康账本", dumped)
        self.assertIn("阻断加仓", dumped)
        self.assertIn("观察/小额试探", dumped)
        self.assertEqual(view_model["data_health_impact"]["status"], "blocked")

    def test_projection_confidence_summary_is_visible_to_strategy_view_model(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "小幅进攻"},
            projection_packet={
                "status": "ready",
                "path_basis": "A股证据雷达：支持 0｜阻断 0｜缓存 0｜缺失 6",
                "path_recovery_impact": {
                    "evidence_state": "missing",
                    "label": "龙虎榜",
                    "impact_text": "龙虎榜恢复结果待验证。",
                    "deepseek_called": False,
                },
                "deepseek_called": False,
            },
        )
        projection_summary = view_model["projection_confidence_summary"]

        self.assertEqual(projection_summary["status"], "partial")
        self.assertEqual(projection_summary["label"], "路径待验证")
        self.assertIn("龙虎榜", json.dumps(projection_summary, ensure_ascii=False))
        self.assertFalse(projection_summary["deepseek_called"])

    def test_a_share_data_capability_all_available_enters_evidence_chain(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "只观察"},
            analysis_method_packet={"market": "A股"},
            a_share_data_console={
                "decision_readiness_label": "可进入证据链",
                "summary": "可用 4｜受限 0｜暂无数据 0｜待手动 0",
                "groups": [
                    {"key": "available", "tone": "ready", "count": 4, "items": ["个股资金流", "龙虎榜", "融资融券"]},
                ],
                "deepseek_called": False,
            },
        )
        items = view_model["evidence_validation_items"]
        dumped = json.dumps(items, ensure_ascii=False)

        self.assertEqual(items[0]["tone"], "success")
        self.assertIn("可进入证据链", items[0]["check_text"])
        self.assertIn("个股资金流", dumped)
        self.assertIn("可进入证据链", view_model["a_share_data_validation_summary"])
        json.dumps(view_model, ensure_ascii=False)

    def test_a_share_fact_recovery_blocks_strategy_execution_when_restricted(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "小幅进攻"},
            analysis_method_packet={"market": "A股"},
            a_share_fact_recovery_summary={
                "summary": "A股事实 5 项：已回流 2｜仍受限 1｜待验证 2",
                "recovered_count": 2,
                "blocked_count": 1,
                "waiting_count": 2,
                "total_count": 5,
                "items": [
                    {"label": "个股资金流", "recovery_state": "recovered", "status_label": "可用"},
                    {"label": "龙虎榜", "recovery_state": "blocked", "status_label": "权限不足"},
                    {"label": "筹码/胜率", "recovery_state": "waiting", "status_label": "近期无数据"},
                ],
                "deepseek_called": False,
            },
        )
        items = view_model["evidence_validation_items"]
        dumped = json.dumps(items, ensure_ascii=False)

        self.assertEqual(items[0]["key"], "a_share_fact_recovery")
        self.assertEqual(items[0]["tone"], "danger")
        self.assertIn("仍受限 1", view_model["a_share_fact_recovery_validation_summary"])
        self.assertIn("龙虎榜", dumped)
        self.assertIn("未恢复前策略只能降级", dumped)
        self.assertIn("筹码/胜率", dumped)
        self.assertFalse("DeepSeek" in dumped)
        json.dumps(view_model, ensure_ascii=False)

    def test_a_share_fact_recovery_counts_block_even_without_item_details(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "小幅进攻"},
            analysis_method_packet={"market": "A股"},
            a_share_fact_recovery_summary={
                "summary": "A股事实 5 项：已回流 3｜仍受限 1｜待验证 1",
                "recovered_count": 3,
                "blocked_count": 1,
                "waiting_count": 1,
                "total_count": 5,
                "deepseek_called": False,
            },
        )
        item = view_model["evidence_validation_items"][0]

        self.assertEqual(item["key"], "a_share_fact_recovery")
        self.assertEqual(item["tone"], "danger")
        self.assertIn("五类事实", item["action_hint"])
        json.dumps(view_model, ensure_ascii=False)

    def test_a_share_fact_recovery_all_recovered_supports_strategy_validation(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "只观察"},
            analysis_method_packet={"market": "A股"},
            a_share_fact_recovery_summary={
                "summary": "A股事实 5 项：已回流 5｜仍受限 0｜待验证 0",
                "recovered_count": 5,
                "blocked_count": 0,
                "waiting_count": 0,
                "total_count": 5,
                "items": [
                    {"label": "个股资金流", "recovery_state": "recovered", "status_label": "可用"},
                    {"label": "龙虎榜", "recovery_state": "recovered", "status_label": "可用"},
                    {"label": "融资融券", "recovery_state": "recovered", "status_label": "可用"},
                ],
                "deepseek_called": False,
            },
        )
        dumped = json.dumps(view_model["evidence_validation_items"], ensure_ascii=False)

        self.assertEqual(view_model["evidence_validation_items"][0]["tone"], "success")
        self.assertIn("已回流 5", view_model["a_share_fact_recovery_validation_summary"])
        self.assertIn("仍需价格、纪律和仓位预算共振", dumped)
        json.dumps(view_model, ensure_ascii=False)

    def test_latest_recovery_result_supports_strategy_validation_when_recovered(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "只观察"},
            analysis_method_packet={"market": "A股"},
            latest_recovery_result_notice={
                "status": "recovered",
                "tone": "ready",
                "title": "A股数据恢复结果已回流",
                "label": "个股资金流",
                "message": "个股资金流：可用｜已读取到最近资金流数据。",
                "next_action": "继续查看 Home Action Snapshot。",
                "writes_packet": "command_center_moneyflow_packet",
                "external_call_policy": "button_gated",
                "deepseek_called": False,
            },
        )
        items = view_model["evidence_validation_items"]
        dumped = json.dumps(items, ensure_ascii=False)

        self.assertEqual(items[0]["key"], "latest_recovery_result")
        self.assertEqual(items[0]["tone"], "success")
        self.assertIn("刚刚回流", dumped)
        self.assertIn("个股资金流", view_model["latest_recovery_validation_summary"])
        self.assertFalse("DeepSeek" in dumped)
        json.dumps(view_model, ensure_ascii=False)

    def test_latest_recovery_result_blocks_strategy_validation_when_restricted(self):
        view_model = summary.build_strategy_summary_view_model(
            {"status": "ready", "action": "小幅进攻"},
            analysis_method_packet={"market": "A股"},
            latest_recovery_result_notice={
                "status": "blocked",
                "tone": "failed",
                "title": "A股数据恢复仍受限",
                "label": "涨跌停/情绪",
                "message": "涨跌停/情绪：权限不足｜limit_cpt_list 权限不足。",
                "next_action": "保持安全空态或缓存观察。",
                "writes_packet": "command_center_limit_emotion_packet",
                "external_call_policy": "button_gated",
                "deepseek_called": False,
            },
        )
        items = view_model["evidence_validation_items"]
        dumped = json.dumps(items, ensure_ascii=False)

        self.assertEqual(items[0]["key"], "latest_recovery_result")
        self.assertEqual(items[0]["tone"], "danger")
        self.assertIn("恢复仍受限", dumped)
        self.assertIn("策略只能降级", dumped)
        self.assertIn("涨跌停/情绪", view_model["latest_recovery_validation_summary"])
        json.dumps(view_model, ensure_ascii=False)

    def test_missing_evidence_validation_is_safe(self):
        view_model = summary.build_strategy_summary_view_model({"status": "ready"}, evidence_radar_packet={})

        self.assertEqual(view_model["evidence_validation_items"][0]["key"], "a_share_evidence_missing")
        self.assertIn("先刷新今日基础数据", view_model["evidence_validation_items"][0]["action_hint"])
        self.assertFalse("DeepSeek" in json.dumps(view_model["evidence_validation_items"], ensure_ascii=False))

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_strategy_summary.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_strategy_summary.py: {name}")


if __name__ == "__main__":
    unittest.main()
