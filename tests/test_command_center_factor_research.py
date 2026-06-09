import json
import unittest
from pathlib import Path

import command_center_factor_research as factor_research


class CommandCenterFactorResearchTests(unittest.TestCase):
    def test_factor_library_is_local_research_only_scaffold(self):
        packet = factor_research.build_factor_library_packet(now="2026-06-09T10:00:00")

        self.assertEqual(packet["packet_key"], "command_center_factor_library_packet")
        self.assertEqual(packet["updated_at"], "2026-06-09T10:00:00")
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertGreaterEqual(packet["factor_count"], 20)
        self.assertLessEqual(packet["factor_count"], 30)
        json.dumps(packet, ensure_ascii=False)

    def test_every_factor_has_required_research_fields_and_no_core_action_usage(self):
        packet = factor_research.build_factor_library_packet()

        for factor in packet["factors"]:
            with self.subTest(factor_key=factor.get("factor_key")):
                self.assertTrue(factor.get("factor_key"))
                self.assertTrue(factor.get("factor_name"))
                self.assertTrue(factor.get("category"))
                self.assertTrue(factor.get("formula_summary"))
                self.assertTrue(factor.get("source_interfaces"))
                self.assertIn("PIT_safe", factor)
                self.assertTrue(factor.get("pit_requirement"))
                self.assertFalse(factor.get("pit_validated"))
                self.assertTrue(factor.get("lookahead_risk_note"))
                self.assertIn(factor.get("first_stage_usage"), {"research_only", "evidence_effect_only"})
                self.assertFalse(factor["enters_core_action"])
                self.assertFalse(factor["enters_strategy_action"])
                self.assertFalse(factor["enters_next_session_projection"])
                self.assertFalse(factor["enters_deepseek_prompt"])

    def test_decision_usage_policy_blocks_trading_projection_and_deepseek_paths(self):
        for packet in [
            factor_research.build_factor_library_packet(),
            factor_research.build_factor_data_ledger_packet(),
            factor_research.build_factor_governance_packet(),
        ]:
            policy = packet["decision_usage_policy"]
            self.assertTrue(policy["display_only"])
            self.assertFalse(policy["enters_strategy_action"])
            self.assertFalse(policy["enters_core_action"])
            self.assertFalse(policy["enters_next_session_projection"])
            self.assertFalse(policy["enters_evidence_effects"])
            self.assertFalse(policy["enters_deepseek_prompt"])
            self.assertIn("不作为交易指令", policy["note"])

    def test_data_ledger_uses_available_packet_presence_without_fetching(self):
        library = factor_research.build_factor_library_packet()
        ledger = factor_research.build_factor_data_ledger_packet(
            factor_library=library,
            available_packets={
                "daily_close_packet": {"status": "cached"},
                "command_center_moneyflow_packet": {"status": "cached"},
            },
            now="2026-06-09T10:30:00",
        )
        by_key = {row["factor_key"]: row for row in ledger["ledger_rows"]}

        self.assertEqual(ledger["packet_key"], "command_center_factor_data_ledger_packet")
        self.assertEqual(ledger["updated_at"], "2026-06-09T10:30:00")
        self.assertFalse(ledger["deepseek_called"])
        self.assertFalse(ledger["tushare_called"])
        self.assertFalse(ledger["external_calls_triggered"])
        self.assertEqual(by_key["momentum_20d"]["status"], "verified_present")
        self.assertFalse(by_key["momentum_20d"]["pit_validated"])
        self.assertFalse(by_key["momentum_20d"]["point_in_time_safe"])
        self.assertEqual(by_key["main_net_5d"]["status"], "verified_present")
        self.assertEqual(by_key["roe_latest"]["status"], "not_loaded")
        self.assertIn("公告日期", by_key["roe_latest"]["pit_requirement"])
        self.assertIn("公告日错位", by_key["roe_latest"]["lookahead_risk_note"])
        for row in ledger["ledger_rows"]:
            self.assertFalse(row["enters_strategy_action"])
            self.assertFalse(row["enters_core_action"])
            self.assertFalse(row["enters_next_session_projection"])
            self.assertFalse(row["enters_deepseek_prompt"])

    def test_governance_defaults_allow_only_research_display(self):
        packet = factor_research.build_factor_governance_packet()

        self.assertTrue(packet["allow_research_display"])
        self.assertFalse(packet["allow_evidence_effects"])
        self.assertFalse(packet["allow_strategy_trace"])
        self.assertFalse(packet["allow_core_action"])
        self.assertIn("因子研究不是交易建议。", packet["risk_boundaries"])

    def test_factor_research_does_not_enter_strategy_projection_or_deepseek_modules(self):
        blocked_files = [
            "strategy_execution_service.py",
            "command_center_next_session_projection.py",
            "analysis_engine.py",
            "command_center_strategy_summary.py",
        ]
        for filename in blocked_files:
            with self.subTest(filename=filename):
                source = Path(filename).read_text(encoding="utf-8")
                self.assertNotIn("command_center_factor_library_packet", source)
                self.assertNotIn("command_center_factor_data_ledger_packet", source)
                self.assertNotIn("factor_research_service", source)

        app_source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("_render_factor_research_lab_panel", app_source)
        self.assertIn("factor_research_service.build_factor_library_packet", app_source)
        self.assertIn('"PIT要求": factor.get("pit_requirement")', app_source)
        self.assertIn('"PIT已验证": "否"', app_source)
        self.assertIn("PIT requirement 已声明但验证待完成", app_source)
        self.assertIn("尚未完成 IC / Rank IC / ICIR / 分组收益 / 换手 / 成本后收益检验", app_source)
        self.assertIn("不调用 Tushare，不调用 DeepSeek，不回测，不生成交易动作", app_source)
        self.assertNotIn("运行因子回测", app_source)
        self.assertNotIn("按因子买入", app_source)
        self.assertNotIn("按因子卖出", app_source)


if __name__ == "__main__":
    unittest.main()
