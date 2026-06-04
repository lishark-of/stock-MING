import ast
import json
import unittest
from pathlib import Path

import command_center_a_share_capability_matrix as matrix


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


def sample_capability_packet():
    return {
        "source": "Tushare A股专业事实",
        "items": [
            {"section": "moneyflow", "label": "个股资金流", "api": "moneyflow", "capability_state": "available", "status": "可用"},
            {"section": "dragon_tiger", "label": "龙虎榜", "api": "top_list", "capability_state": "empty_recent", "status": "近期无数据"},
            {"section": "margin", "label": "融资融券", "api": "margin_detail", "capability_state": "permission_denied", "status": "权限不足"},
            {"section": "limit_emotion", "label": "涨跌停/情绪", "api": "limit_cpt_list", "capability_state": "disabled_this_session", "status": "本会话跳过"},
            {"section": "chip_radar", "label": "筹码/胜率", "api": "cyq_perf/cyq_chips", "capability_state": "stale_cache", "status": "使用缓存"},
            {"section": "hard_risk.announcements", "label": "公告风险", "api": "anns_d", "capability_state": "available", "status": "可用"},
            {"section": "hard_risk.pledge", "label": "股权质押", "api": "pledge_stat/pledge_detail", "capability_state": "permission_denied", "status": "权限不足"},
        ],
    }


class CommandCenterAShareCapabilityMatrixTests(unittest.TestCase):
    def test_missing_input_returns_safe_matrix(self):
        packet = matrix.build_a_share_capability_matrix()

        self.assertEqual(packet["status"], "missing")
        self.assertEqual(len(packet["items"]), 6)
        self.assertIn("不会自动请求 Tushare", packet["summary"])
        self.assertEqual(matrix.build_a_share_capability_summary_text(packet), "尚未检测 A股数据能力")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_matrix_distinguishes_core_a_share_states(self):
        packet = matrix.build_a_share_capability_matrix(sample_capability_packet())
        by_key = {item["key"]: item for item in packet["items"]}
        explainer = packet["tushare_gap_explainer"]
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["tone"], "failed")
        self.assertEqual(by_key["moneyflow"]["state"], "available")
        self.assertEqual(by_key["margin"]["state"], "permission_denied")
        self.assertEqual(by_key["limit_emotion"]["state"], "disabled_this_session")
        self.assertEqual(by_key["chip_radar"]["state"], "stale_cache")
        self.assertEqual(by_key["hard_risk"]["state"], "permission_denied")
        self.assertEqual(by_key["moneyflow"]["migration_priority"], 1)
        self.assertIn("策略执行", by_key["moneyflow"]["decision_chain_stage"])
        self.assertIn("ETF / 融资动作", by_key["margin"]["home_module"])
        self.assertIn("禁止动作", by_key["hard_risk"]["migration_target"])
        self.assertEqual(by_key["margin"]["manual_action"]["refresh_policy"], "button_gated")
        self.assertIn("融资融券", by_key["margin"]["manual_action"]["button_label"])
        self.assertIn("command_center_margin_packet", by_key["margin"]["manual_action"]["writes_packet"])
        self.assertFalse(by_key["margin"]["manual_action"]["deepseek_called"])
        self.assertIn("龙虎榜", dumped)
        self.assertIn("融资融券", dumped)
        self.assertIn("涨跌停", dumped)
        self.assertIn("筹码", dumped)
        self.assertEqual(explainer["status"], "blocked")
        self.assertIn("拉满基础数据", explainer["headline"])
        self.assertIn("之前“拉满”", explainer["plain_answer"])
        self.assertIn("细分专业接口权限", explainer["plain_answer"])
        self.assertIn("原因分类", explainer["cause_summary"])
        self.assertIn("接口权限/积分", explainer["cause_summary"])
        self.assertIn("本会话跳过", explainer["cause_summary"])
        self.assertIn("基础行情或 token 正常", explainer["explanation"])
        self.assertEqual(explainer["external_call_policy"], "not_triggered")
        self.assertFalse(explainer["deepseek_called"])
        self.assertFalse(packet["deepseek_called"])

    def test_tushare_gap_explainer_turns_search_failures_into_user_reasons(self):
        packet = matrix.build_a_share_capability_matrix(sample_capability_packet())
        explainer = packet["tushare_gap_explainer"]
        by_key = {item["key"]: item for item in explainer["items"]}

        self.assertEqual(by_key["margin"]["action_mode"], "blocked")
        self.assertEqual(by_key["margin"]["cause_code"], "permission_scope")
        self.assertEqual(by_key["margin"]["cause_label"], "接口权限/积分")
        self.assertIn("权限", by_key["margin"]["why_not_found"])
        self.assertIn("不是“没搜到”", by_key["margin"]["diagnostic_answer"])
        self.assertIn("之前拉满基础数据", by_key["margin"]["diagnostic_answer"])
        self.assertIn("之前“拉满”", by_key["margin"]["why_previous_full_not_enough"])
        self.assertIn("单独权限/积分", by_key["margin"]["why_previous_full_not_enough"])
        self.assertIn("阻断加仓", by_key["margin"]["decision_guardrail"])
        self.assertEqual(len(by_key["margin"]["safe_recovery_steps"]), 3)
        self.assertIn("权限/积分", by_key["margin"]["safe_recovery_steps"][0])
        self.assertEqual(by_key["limit_emotion"]["action_mode"], "blocked")
        self.assertEqual(by_key["limit_emotion"]["cause_code"], "session_skip")
        self.assertIn("本会话跳过", by_key["limit_emotion"]["why_not_found"])
        self.assertIn("跳过重复请求", by_key["limit_emotion"]["diagnostic_answer"])
        self.assertIn("防卡顿", by_key["limit_emotion"]["why_previous_full_not_enough"])
        self.assertEqual(by_key["dragon_tiger"]["action_mode"], "verify_window")
        self.assertEqual(by_key["dragon_tiger"]["cause_code"], "publish_window")
        self.assertIn("近期无记录", by_key["dragon_tiger"]["why_not_found"])
        self.assertIn("标的未上榜", by_key["dragon_tiger"]["diagnostic_answer"])
        self.assertEqual(by_key["chip_radar"]["action_mode"], "verify_cache")
        self.assertEqual(by_key["chip_radar"]["cause_code"], "cache_guard")
        self.assertIn("防白屏", by_key["chip_radar"]["why_not_found"])
        self.assertIn("不是实时新数据", by_key["chip_radar"]["diagnostic_answer"])
        self.assertEqual(by_key["moneyflow"]["action_mode"], "usable")
        self.assertEqual(by_key["moneyflow"]["cause_code"], "available")
        self.assertIn("command_center_margin_packet", by_key["margin"]["writes_packet"])
        self.assertEqual(by_key["margin"]["refresh_policy"], "button_gated")
        self.assertFalse(any(item["deepseek_called"] for item in by_key.values()))
        json.dumps(explainer, ensure_ascii=False)

    def test_summary_text_counts_available_blocked_and_pending_items(self):
        packet = matrix.build_a_share_capability_matrix(sample_capability_packet())
        summary = matrix.build_a_share_capability_summary_text(packet)

        self.assertEqual(summary, "可用 1｜受限 3｜待验证 2")

    def test_permission_does_not_become_positive_evidence(self):
        packet = matrix.build_a_share_capability_matrix(sample_capability_packet())
        margin = {item["key"]: item for item in packet["items"]}["margin"]

        self.assertIn("不能把缺失数据当成利好", margin["decision_impact"])
        self.assertIn("接口权限", margin["next_action"])

    def test_manual_action_queue_excludes_available_items(self):
        packet = matrix.build_a_share_capability_matrix(sample_capability_packet())
        queued_keys = {item["action_key"] for item in packet["manual_action_queue"]}

        self.assertNotIn("manual_check_moneyflow", queued_keys)
        self.assertIn("manual_check_margin_detail", queued_keys)
        self.assertIn("manual_check_limit_emotion", queued_keys)
        self.assertIn("manual_check_hard_risk", queued_keys)
        for item in packet["manual_action_queue"]:
            self.assertEqual(item["refresh_policy"], "button_gated")
            self.assertFalse(item["deepseek_called"])

    def test_migration_queue_prioritizes_decision_blockers(self):
        packet = matrix.build_a_share_capability_matrix(sample_capability_packet())
        queue = packet["migration_queue"]
        labels = [item["label"] for item in queue[:3]]

        self.assertEqual(queue[0]["priority"], 1)
        self.assertIn("公告/硬风险", labels)
        self.assertIn("今日总决策", queue[0]["home_module"])
        for item in queue:
            self.assertTrue(item["migration_target"])
            self.assertTrue(item["decision_chain_stage"])
            self.assertEqual(item["manual_action"]["refresh_policy"], "button_gated")
            self.assertFalse(item["deepseek_called"])

    def test_cache_and_empty_are_visible_but_not_decisive(self):
        packet = matrix.build_a_share_capability_matrix(sample_capability_packet())
        by_key = {item["key"]: item for item in packet["items"]}

        self.assertIn("近期无记录", by_key["dragon_tiger"]["decision_impact"])
        self.assertIn("使用缓存", by_key["chip_radar"]["status_label"])
        self.assertIn("复核交易日", by_key["chip_radar"]["decision_impact"])

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_a_share_capability_matrix.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        self.assertTrue(FORBIDDEN_IMPORTS.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
