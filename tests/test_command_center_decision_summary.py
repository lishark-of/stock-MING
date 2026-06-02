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
