import ast
import unittest
from pathlib import Path

import command_center_legacy_a_share_prompts as prompts


class CommandCenterLegacyASharePromptsTests(unittest.TestCase):
    def test_deep_research_prompt_keeps_fact_boundaries(self):
        prompt = prompts.build_a_share_deep_research_prompt(
            target="大族激光",
            current_price=12.3,
            verified_technical_prompt="【已验证技术事实】MA60 可用",
            unverified_inject="【待验证线索】历史云记忆",
        )

        self.assertIn("大族激光", prompt)
        self.assertIn("¥12.3", prompt)
        self.assertIn("资金行为待验证", prompt)
        self.assertIn("云记忆", prompt)
        self.assertIn("已验证事实只能来自 Tushare", prompt)
        self.assertIn("技术指标只能作为观察条件和验证条件", prompt)

    def test_next_day_plan_prompt_embeds_packet_and_manual_rules(self):
        prompt = prompts.build_a_share_next_day_plan_prompt(
            target="大族激光",
            fact_packet={
                "stock_code": "002008",
                "position_profile": {"normalized_position_state": "已持仓"},
                "deepseek_called": False,
            },
            verified_technical_prompt="【已验证技术事实】RSI 可用",
        )

        self.assertIn("【次日交易计划事实包】", prompt)
        self.assertIn('"stock_code": "002008"', prompt)
        self.assertIn('"deepseek_called": false', prompt)
        self.assertIn("不是自动交易指令", prompt)
        self.assertIn("不允许写“必买、必卖、满仓、梭哈、确定上涨、确定反包”", prompt)
        self.assertIn("所有交易动作需要用户人工确认", prompt)
        self.assertIn("筹码/胜率只能作为观察和验证条件", prompt)

    def test_war_room_prompt_embeds_chip_facts_and_hard_rules(self):
        prompt = prompts.build_a_share_war_room_prompt(
            target="大族激光",
            fact_packet={
                "chip_radar": {
                    "winner_rate": 63.2,
                    "weight_avg": 12.1,
                    "cost_5pct": 10.2,
                    "cost_50pct": 11.8,
                    "cost_95pct": 14.5,
                    "chip_pressure_comment": "上方压力待验证",
                },
                "rotation_context": {"watch_targets": []},
                "deepseek_called": False,
            },
            verified_technical_prompt="【已验证技术事实】量能可用",
        )

        self.assertIn("【单票作战室事实包】", prompt)
        self.assertIn("63.2", prompt)
        self.assertIn("上方压力待验证", prompt)
        self.assertIn("不自动下单", prompt)
        self.assertIn("不得建议满仓", prompt)
        self.assertIn("所有结论必须区分“已验证数据”和“待验证线索/谨慎推断”", prompt)
        self.assertIn("不得把筹码数据写成确定性买卖信号", prompt)

    def test_war_room_prompt_handles_missing_packet(self):
        prompt = prompts.build_a_share_war_room_prompt(target="大族激光", fact_packet=None)

        self.assertIn("暂无可验证数据", prompt)
        self.assertIn("【单票作战室】", prompt)

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_legacy_a_share_prompts.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        forbidden = {
            "streamlit",
            "app",
            "data_fetcher",
            "tushare_adapter",
            "akshare",
            "yfinance",
            "openai",
            "backtester",
            "command_center_service",
        }
        self.assertFalse(forbidden.intersection(imports))


if __name__ == "__main__":
    unittest.main()
