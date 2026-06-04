import ast
import json
import unittest
from pathlib import Path

import command_center_decision_summary as summary


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
    "command_center_decision_engine",
}


class CommandCenterDecisionSummaryTests(unittest.TestCase):
    def test_empty_packet_uses_waiting_defaults(self):
        view_model = summary.build_decision_summary_view_model(None)

        self.assertEqual(view_model["status"], "waiting")
        self.assertEqual(view_model["status_label"], "待刷新判断")
        self.assertEqual(view_model["action_label"], "等待")
        self.assertEqual(view_model["risk_label"], "中")
        self.assertEqual(view_model["updated_text"], "暂无")
        self.assertEqual(view_model["source_text"], "command_center_decision_engine")
        json.dumps(view_model, ensure_ascii=False)

    def test_status_labels_cover_waiting_partial_ready_failed(self):
        expected = {
            "waiting": "待刷新判断",
            "partial": "部分刷新结论",
            "ready": "综合推演结论",
            "failed": "失败后缓存",
        }

        for status, label in expected.items():
            self.assertEqual(summary.decision_status_label({"status": status}), label)

    def test_action_and_risk_tones(self):
        self.assertEqual(summary.decision_action_tone({"overall_action": "小幅进攻"}), "success")
        self.assertEqual(summary.decision_action_tone({"overall_action": "降风险"}), "danger")
        self.assertEqual(summary.decision_action_tone({"overall_action": "等待"}), "warning")
        self.assertEqual(summary.decision_action_tone({"overall_action": "只观察"}), "warning")
        self.assertEqual(summary.decision_risk_tone({"risk_level": "低"}), "success")
        self.assertEqual(summary.decision_risk_tone({"risk_level": "中"}), "warning")
        self.assertEqual(summary.decision_risk_tone({"risk_level": "高"}), "danger")

    def test_action_guardrails_reduce_beginner_misinterpretation(self):
        attack = summary.build_decision_summary_view_model({"overall_action": "小幅进攻"})
        wait = summary.build_decision_summary_view_model({"overall_action": "等待"})
        observe = summary.build_decision_summary_view_model({"overall_action": "只观察"})
        reduce = summary.build_decision_summary_view_model({"overall_action": "降风险"})

        self.assertIn("只允许小额试探", attack["action_guardrail"])
        self.assertIn("今天不是必须交易", wait["action_guardrail"])
        self.assertIn("今天不是必须交易", observe["action_guardrail"])
        self.assertIn("降杠杆", reduce["action_guardrail"])

    def test_user_boundary_text_blocks_dangerous_interpretation(self):
        view_model = summary.build_decision_summary_view_model({})
        boundary = view_model["user_boundary_text"]
        combined = " ".join([
            view_model["empty_message"],
            view_model["action_guardrail"],
            boundary,
        ])

        self.assertIn("不是荐股", boundary)
        self.assertIn("不保证收益", boundary)
        self.assertIn("DeepSeek 只解释", boundary)
        for dangerous in ["必买", "稳赚"]:
            self.assertNotIn(dangerous, combined)

    def test_empty_lists_use_fallback_items(self):
        view_model = summary.build_decision_summary_view_model({
            "must_not_do": [],
            "next_validation_conditions": [],
        })

        self.assertEqual(len(view_model["must_not_do_items"]), 1)
        self.assertEqual(len(view_model["validation_items"]), 1)

    def test_data_coverage_items_support_missing_cached_ready(self):
        packet = {
            "data_coverage": {
                "market": "ready",
                "quant": "cached",
                "discipline": "missing",
            }
        }

        items = summary.build_data_coverage_items(packet)
        by_key = {item["key"]: item for item in items}

        self.assertEqual(by_key["market"]["state"], "ready")
        self.assertEqual(by_key["market"]["tone"], "success")
        self.assertEqual(by_key["quant"]["state"], "cached")
        self.assertEqual(by_key["quant"]["tone"], "warning")
        self.assertEqual(by_key["discipline"]["state"], "missing")
        self.assertEqual(by_key["discipline"]["tone"], "muted")

    def test_evidence_summary_text_is_visible_for_professional_review(self):
        view_model = summary.build_decision_summary_view_model({
            "data_coverage": {
                "market": "ready",
                "quant": "cached",
                "discipline": "missing",
            }
        })

        self.assertIn("已刷新：市场", view_model["evidence_summary_text"])
        self.assertIn("使用缓存：量化", view_model["evidence_summary_text"])
        self.assertIn("待验证：纪律", view_model["evidence_summary_text"])

    def test_deepseek_called_false_and_missing_source_defaults(self):
        self.assertEqual(summary.decision_deepseek_text({"deepseek_called": False}), "DeepSeek：未调用")
        self.assertEqual(summary.decision_updated_text({}), "暂无")
        self.assertEqual(summary.decision_source_text({}), "command_center_decision_engine")

    def test_evidence_chain_includes_market_passed_pending_and_not_applicable_methods(self):
        view_model = summary.build_decision_summary_view_model(
            {"status": "ready", "overall_action": "只观察"},
            analysis_method_packet={
                "market": "A股",
                "source": "rule-based market profile",
                "methods": [
                    {"name": "趋势跟踪", "status": "通过"},
                    {"name": "资金流 / 机构行为", "status": "待验证"},
                    {"name": "ETF 赛道配置", "status": "不适用"},
                ],
            },
        )
        joined = json.dumps(view_model["evidence_chain_items"], ensure_ascii=False)

        self.assertIn("A股", joined)
        self.assertIn("趋势跟踪", joined)
        self.assertIn("资金流", joined)
        self.assertIn("ETF 赛道配置", joined)

    def test_evidence_chain_includes_a_share_evidence_radar_counts(self):
        view_model = summary.build_decision_summary_view_model(
            {"status": "ready", "overall_action": "等待"},
            analysis_method_packet={"market": "A股", "methods": [{"name": "趋势跟踪", "status": "通过"}]},
            evidence_radar_packet={
                "decision_summary": "支持 1｜阻断 1｜缓存 1｜缺失 3",
                "support_items": [{"label": "个股资金流"}],
                "blocker_items": [{"label": "硬风险/公告"}],
                "cached_items": [{"label": "融资融券"}],
                "missing_items": [{"label": "龙虎榜"}, {"label": "筹码/胜率"}, {"label": "涨跌停/情绪"}],
            },
        )
        joined = json.dumps(view_model["evidence_chain_items"], ensure_ascii=False)

        self.assertIn("阻断证据", joined)
        self.assertIn("支持证据", joined)
        self.assertEqual(view_model["a_share_evidence_summary_text"], "支持 1｜阻断 1｜缓存 1｜缺失 3")

    def test_evidence_chain_includes_a_share_data_capability_blockers(self):
        console = {
            "decision_readiness_label": "阻断加仓",
            "summary": "可用 1｜受限 1｜暂无数据 1｜待手动 0",
            "groups": [
                {"key": "available", "tone": "ready", "count": 1, "items": ["融资融券"]},
                {"key": "permission_denied", "tone": "failed", "count": 1, "items": ["个股资金流"]},
                {"key": "stale_or_empty", "tone": "stale", "count": 1, "items": ["龙虎榜"]},
            ],
            "deepseek_called": False,
        }
        view_model = summary.build_decision_summary_view_model(
            {"status": "ready", "overall_action": "只观察"},
            analysis_method_packet={"market": "A股", "methods": [{"name": "趋势跟踪", "status": "通过"}]},
            a_share_data_console=console,
        )
        joined = json.dumps(view_model["evidence_chain_items"], ensure_ascii=False)
        basis = json.dumps(view_model["a_share_data_basis_items"], ensure_ascii=False)

        self.assertIn("A股数据能力", joined)
        self.assertIn("阻断加仓", joined)
        self.assertIn("个股资金流", basis)
        self.assertIn("龙虎榜", basis)
        self.assertEqual(view_model["a_share_data_basis_items"][0]["tone"], "danger")
        self.assertIn("受限 1", view_model["a_share_data_basis_summary_text"])
        json.dumps(view_model, ensure_ascii=False)

    def test_a_share_data_basis_marks_all_available_as_decision_ready(self):
        view_model = summary.build_decision_summary_view_model(
            {},
            analysis_method_packet={"market": "A股", "methods": []},
            a_share_data_console={
                "decision_readiness_label": "可进入证据链",
                "summary": "可用 4｜受限 0｜暂无数据 0｜待手动 0",
                "groups": [
                    {"key": "available", "tone": "ready", "count": 4, "items": ["个股资金流", "龙虎榜", "融资融券"]},
                ],
                "deepseek_called": False,
            },
        )
        basis = view_model["a_share_data_basis_items"]

        self.assertEqual(basis[0]["tone"], "success")
        self.assertEqual(basis[0]["value"], "可进入证据链")
        self.assertIn("个股资金流", json.dumps(basis, ensure_ascii=False))

    def test_evidence_chain_includes_a_share_fact_recovery_blockers(self):
        view_model = summary.build_decision_summary_view_model(
            {"status": "ready", "overall_action": "只观察"},
            analysis_method_packet={"market": "A股", "methods": [{"name": "趋势跟踪", "status": "通过"}]},
            a_share_fact_recovery_summary={
                "summary": "A股事实 5 项：已回流 2｜仍受限 1｜待验证 2",
                "recovered_count": 2,
                "blocked_count": 1,
                "waiting_count": 2,
                "total_count": 5,
                "deepseek_called": False,
            },
        )
        joined = json.dumps(view_model["evidence_chain_items"], ensure_ascii=False)

        self.assertIn("A股事实回流", joined)
        self.assertIn("仍受限 1", joined)
        self.assertEqual(view_model["a_share_fact_recovery_basis_item"]["tone"], "danger")
        self.assertIn("已回流 2", view_model["a_share_fact_recovery_summary_text"])
        json.dumps(view_model, ensure_ascii=False)

    def test_a_share_fact_recovery_marks_all_recovered_as_success(self):
        item = summary.build_a_share_fact_recovery_basis_item(
            {
                "summary": "A股事实 5 项：已回流 5｜仍受限 0｜待验证 0",
                "recovered_count": 5,
                "blocked_count": 0,
                "waiting_count": 0,
                "total_count": 5,
            }
        )

        self.assertEqual(item["tone"], "success")
        self.assertIn("已回流 5", item["value"])

    def test_evidence_chain_includes_latest_recovery_result(self):
        view_model = summary.build_decision_summary_view_model(
            {"status": "ready", "overall_action": "只观察"},
            analysis_method_packet={"market": "A股", "methods": [{"name": "资金流", "status": "待验证"}]},
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
        joined = json.dumps(view_model["evidence_chain_items"], ensure_ascii=False)

        self.assertIn("最近恢复", joined)
        self.assertIn("涨跌停/情绪", joined)
        self.assertEqual(view_model["latest_recovery_result_basis_item"]["tone"], "danger")
        self.assertIn("权限不足", view_model["latest_recovery_result_summary_text"])
        self.assertEqual(view_model["latest_recovery_result_basis_item"]["external_call_policy"], "button_gated")
        json.dumps(view_model, ensure_ascii=False)

    def test_evidence_chain_keeps_blockers_when_method_list_is_full(self):
        view_model = summary.build_decision_summary_view_model(
            {},
            analysis_method_packet={
                "market": "A股",
                "methods": [
                    {"name": "趋势跟踪", "status": "通过"},
                    {"name": "量价结构", "status": "通过"},
                    {"name": "资金流", "status": "待验证"},
                    {"name": "ETF 赛道配置", "status": "不适用"},
                ],
            },
            evidence_radar_packet={
                "decision_summary": "支持 0｜阻断 1｜缓存 0｜缺失 5",
                "blocker_items": [{"label": "硬风险/公告"}],
                "support_items": [],
                "cached_items": [],
                "missing_items": [{}, {}, {}, {}, {}],
            },
        )
        joined = json.dumps(view_model["evidence_chain_items"], ensure_ascii=False)

        self.assertIn("阻断证据", joined)
        self.assertNotIn("来源", joined)

    def test_empty_evidence_chain_is_safe(self):
        view_model = summary.build_decision_summary_view_model({}, analysis_method_packet=None)

        self.assertEqual(view_model["evidence_chain_items"][0]["value"], "市场类型待确认")
        json.dumps(view_model["evidence_chain_items"], ensure_ascii=False)

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_decision_summary.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_decision_summary.py: {name}")


if __name__ == "__main__":
    unittest.main()
