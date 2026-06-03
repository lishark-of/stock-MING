import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_legacy_a_share_prompt_packets as packets


class CommandCenterLegacyASharePromptPacketsTests(unittest.TestCase):
    def test_next_day_plan_packet_uses_verified_fields(self):
        packet = packets.build_next_day_plan_fact_packet(
            stock_code="002008",
            stock_name="大族激光",
            current_price=12.3,
            position_profile={
                "position_status": "已持仓",
                "normalized_position_state": "已持仓",
                "allow_pnl": True,
                "allow_t_plan": True,
                "allow_reduce_plan": True,
                "cost_price": 10.0,
                "holding_units": 1000,
                "profit_state": "浮盈",
            },
            trade_instruction={"one_line": "只观察"},
            dragon_data={"available": True, "latest_date": "2026-06-03", "reason": "日涨幅偏离", "net_buy_amount_yi": 0.8},
            margin_data={"available": True, "date": "2026-06-03", "financing_balance_yi": 10.1},
            moneyflow_data={"available": True, "date": "2026-06-03", "main_net_yi": 0.5, "five_day_main_net_yi": 1.2},
            limit_emotion_data={
                "available": True,
                "boundary_available": True,
                "records_available": True,
                "latest_date": "2026-06-03",
                "up_limit": 13.5,
                "down_limit": 11.05,
                "limit_records": [{"date": "2026-06-02", "type": "涨停"}],
            },
            chip_radar_data={"available": True, "trade_date": "2026-06-03", "winner_rate": 63.2, "weight_avg": 12.1},
            tushare_verified_source={
                "updated_at": "2026-06-03T20:00:00",
                "api_results": {
                    "daily": {"ok": True, "rows": [1]},
                    "daily_basic": {"ok": True, "rows": [1]},
                },
            },
            market_style_fact_packet={"market_state": "可观察", "risk_switch": "中性"},
            verified_technical_facts={"available": True, "ma20": 12.0},
        )

        self.assertEqual(packet["stock_code"], "002008")
        self.assertTrue(packet["moneyflow"]["available"])
        self.assertEqual(packet["moneyflow"]["main_net_inflow_yi"], 0.5)
        self.assertTrue(packet["price_boundary"]["available"])
        self.assertEqual(packet["price_boundary"]["limit_up_price"], 13.5)
        self.assertEqual(packet["dragon_tiger"]["trade_date"], "2026-06-03")
        self.assertTrue(packet["chip_radar"]["available"])
        self.assertEqual(packet["trade_instruction"], "只观察")
        self.assertEqual(packet["data_missing_items"], [])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_next_day_plan_packet_marks_missing_items_without_mutating_inputs(self):
        moneyflow = {"available": False}
        position = {"normalized_position_state": "未买入，纯观察", "allow_pnl": False}
        before = copy.deepcopy({"moneyflow": moneyflow, "position": position})

        packet = packets.build_next_day_plan_fact_packet(
            stock_code="002008",
            stock_name="大族激光",
            current_price=None,
            position_profile=position,
            trade_instruction={},
            dragon_data={},
            margin_data={},
            moneyflow_data=moneyflow,
            limit_emotion_data={},
            chip_radar_data={},
            updated_at="2026-06-03T09:30:00",
        )

        self.assertEqual({"moneyflow": moneyflow, "position": position}, before)
        self.assertEqual(packet["current_price"], "暂无可验证数据")
        self.assertFalse(packet["moneyflow"]["available"])
        self.assertIn("Tushare moneyflow", packet["data_missing_items"])
        self.assertIn("Tushare daily", packet["data_missing_items"])
        self.assertEqual(packet["updated_at"], "2026-06-03T09:30:00")
        self.assertFalse(packet["deepseek_called"])

    def test_single_stock_war_room_packet_is_stateless(self):
        packet = packets.build_single_stock_war_room_fact_packet(
            stock_code="002008",
            stock_name="大族激光",
            current_price=12.3,
            position_profile={"normalized_position_state": "已持仓", "allow_t_plan": True},
            trade_instruction={"action": "等待"},
            dragon_data={},
            margin_data={},
            moneyflow_data={"available": True, "date": "2026-06-03", "main_net_yi": 0.5},
            limit_emotion_data={},
            chip_radar_data={},
            watch_targets=[{"ticker": "002008.SZ"}],
            ts_code="002008.SZ",
            updated_at="2026-06-03T09:30:00",
        )

        self.assertEqual(packet["stock"]["ts_code"], "002008.SZ")
        self.assertEqual(packet["rotation_context"]["watch_targets"], [{"ticker": "002008.SZ"}])
        self.assertTrue(packet["position_permissions"]["allow_t_plan"])
        self.assertTrue(packet["rules"]["no_auto_order"])
        self.assertEqual(packet["trend_validation_inputs"]["moneyflow"]["main_net_inflow_yi"], 0.5)
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_verified_whale_fact_packet_uses_verified_market_facts(self):
        recent_price_volume = [{"date": "2026-06-03", "close": 12.3, "volume": 100000}]
        moneyflow = {
            "available": True,
            "date": "2026-06-03",
            "main_net_yi": 0.5,
            "five_day_main_net_yi": 1.2,
            "updated_at": "2026-06-03T18:00:00",
        }
        before = copy.deepcopy({"recent_price_volume": recent_price_volume, "moneyflow": moneyflow})

        packet = packets.build_verified_whale_fact_packet(
            stock_code="002008",
            stock_name="大族激光",
            current_price=12.3,
            recent_5d_close_volume=recent_price_volume,
            moneyflow_data=moneyflow,
            dragon_data={
                "available": True,
                "latest_date": "2026-06-03",
                "reason": "日涨幅偏离",
                "net_buy_amount_yi": 0.8,
                "updated_at": "2026-06-03T17:00:00",
            },
            margin_data={"available": True, "date": "2026-06-03", "financing_balance_yi": 10.1},
            limit_emotion_data={
                "available": True,
                "records_available": True,
                "latest_date": "2026-06-03",
                "up_limit": 13.5,
                "limit_records": [{"date": "2026-06-02", "type": "涨停"}],
            },
            verified_technical_facts={"available": True, "ma60_state": "站上"},
        )

        self.assertEqual({"recent_price_volume": recent_price_volume, "moneyflow": moneyflow}, before)
        self.assertEqual(packet["stock_code"], "002008")
        self.assertTrue(packet["price_volume"]["available"])
        self.assertEqual(packet["price_volume"]["source"], "yfinance/get_historical_data")
        self.assertTrue(packet["moneyflow"]["available"])
        self.assertEqual(packet["moneyflow"]["main_net_inflow_yi"], 0.5)
        self.assertEqual(packet["dragon_tiger"]["reason"], "日涨幅偏离")
        self.assertTrue(packet["limit_emotion"]["records_available"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_verified_whale_fact_packet_marks_missing_data(self):
        packet = packets.build_verified_whale_fact_packet(
            stock_code="002008",
            stock_name="大族激光",
            current_price=None,
            recent_5d_close_volume=None,
            moneyflow_data=None,
            dragon_data=None,
            margin_data=None,
            limit_emotion_data=None,
            updated_at="2026-06-03T09:30:00",
        )

        self.assertFalse(packet["price_volume"]["available"])
        self.assertEqual(packet["price_volume"]["note"], "暂无可验证数据")
        self.assertFalse(packet["moneyflow"]["available"])
        self.assertEqual(packet["moneyflow"]["note"], "暂无可验证数据")
        self.assertEqual(packet["updated_at"], "2026-06-03T09:30:00")
        self.assertFalse(packet["deepseek_called"])

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_legacy_a_share_prompt_packets.py").read_text(encoding="utf-8"))
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
