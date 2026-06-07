import json
import sys
import unittest

import strategy_execution_service as service


def _base_report(action="继续观察", max_drawdown=-12, win_rate=62, warnings=None):
    return {
        "ticker": "002008.SZ",
        "summary": "规则历史表现可参考。",
        "metrics": {
            "round_trip_win_rate": win_rate,
            "max_drawdown_pct": max_drawdown,
            "sharpe": 1.1,
            "trade_count": 12,
        },
        "latest_signal": {
            "action": action,
            "reason": "趋势站稳且未明显过热",
        },
        "trader_brief": {
            "action": action,
            "warnings": warnings or [],
            "plain_summary": "当前建议：继续观察。",
        },
    }


class StrategyExecutionServiceTests(unittest.TestCase):
    def test_missing_cache_outputs_waiting_low_confidence(self):
        packet = service.build_strategy_execution_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["action"], "等待")
        self.assertEqual(packet["confidence"], "低")
        self.assertEqual(packet["data_status"]["quant"], "missing")
        self.assertEqual(packet["data_status"]["backtest"], "missing")
        self.assertFalse(packet["deepseek_called"])
        self.assertIn("strategy_execution_trace", packet)
        self.assertFalse(packet["strategy_execution_trace"]["deepseek_used"])
        self.assertIn("量化推演", packet["strategy_execution_trace"]["missing_inputs"])
        self.assertIn("交易纪律/回测", packet["strategy_execution_trace"]["missing_inputs"])

    def test_cached_quant_and_backtest_generate_advice(self):
        state = {
            "legacy_quant_result": {
                "status": "completed",
                "score": 68,
                "direction": "偏积极但需验证",
                "summary": "量化方向偏积极。",
            },
            "last_backtest_report": _base_report(),
            "command_center_live_packet": {"conclusion": {"summary": "基础数据已刷新"}},
        }
        packet = service.build_strategy_execution_packet(
            state,
            target="002008.SZ",
            position_profile={"normalized_position_state": "未买入，有参考成本/计划价格", "capital_plan": 100000, "allow_trial_entry": True},
        )

        self.assertEqual(packet["status"], "ready")
        self.assertIn(packet["action"], {"等待", "只观察"})
        self.assertIn(packet["confidence"], {"中", "高"})
        self.assertIn("小幅", packet["position_advice"])
        self.assertEqual(packet["data_status"]["quant"], "ready")
        self.assertEqual(packet["data_status"]["backtest"], "ready")
        self.assertFalse(packet["deepseek_called"])
        trace = packet["strategy_execution_trace"]
        self.assertFalse(trace["deepseek_used"])
        self.assertIn("资金/龙虎榜/融资融券", trace["missing_inputs"])

    def test_reduce_or_sell_signal_outputs_reduce_risk(self):
        state = {
            "legacy_quant_result": {"status": "completed", "score": 70, "direction": "偏积极"},
            "last_backtest_report": _base_report(action="减仓", max_drawdown=-10),
        }
        packet = service.build_strategy_execution_packet(state, target="002008.SZ")

        self.assertEqual(packet["action"], "降风险")
        self.assertIn("保护本金", packet["summary"])

    def test_high_drawdown_outputs_observe_or_reduce_risk(self):
        state = {
            "legacy_quant_result": {"status": "completed", "score": 65, "direction": "偏积极"},
            "last_backtest_report": _base_report(max_drawdown=-25),
        }
        packet = service.build_strategy_execution_packet(state, target="002008.SZ")

        self.assertIn(packet["action"], {"只观察", "降风险"})
        self.assertIn(packet["risk_budget"]["risk_level"], {"中", "高"})

    def test_safe_generate_writes_last_success(self):
        state = {
            "legacy_quant_result": {"status": "completed", "score": 64, "direction": "偏积极"},
            "last_backtest_report": _base_report(),
        }
        packet = service.safe_generate_strategy_execution_packet(state, target="002008.SZ")

        self.assertEqual(state[service.PACKET_KEY], packet)
        self.assertEqual(state[service.LAST_SUCCESS_KEY], packet)
        self.assertFalse(packet["deepseek_called"])

    def test_safe_generate_preserves_last_success_on_failure(self):
        state = {service.LAST_SUCCESS_KEY: {"status": "ready", "action": "等待", "deepseek_called": False}}
        original = service.build_strategy_execution_packet

        def boom(*args, **kwargs):
            raise RuntimeError("broken")

        try:
            service.build_strategy_execution_packet = boom
            packet = service.safe_generate_strategy_execution_packet(state)
        finally:
            service.build_strategy_execution_packet = original

        self.assertEqual(packet["status"], "failed")
        self.assertTrue(packet["stale"])
        self.assertEqual(packet["action"], "等待")
        self.assertEqual(packet["last_error"], "broken")
        self.assertFalse(packet["deepseek_called"])

    def test_output_fields_are_complete(self):
        packet = service.build_strategy_execution_packet({
            "legacy_quant_result": {"status": "completed", "score": 58, "direction": "轻量摘要"},
            "last_backtest_report": _base_report(),
        })
        expected_keys = {
            "status",
            "action",
            "confidence",
            "position_advice",
            "add_condition",
            "reduce_condition",
            "invalidation_condition",
            "next_5_10_day_paths",
            "discipline_check",
            "risk_budget",
            "data_status",
            "updated_at",
            "source",
            "deepseek_called",
            "summary",
            "last_error",
        }

        self.assertTrue(expected_keys.issubset(packet.keys()))
        self.assertEqual(len(packet["next_5_10_day_paths"]), 3)
        self.assertIn("strategy_execution_trace", packet)

    def test_trace_explains_observe_when_quant_is_weak(self):
        state = {
            "legacy_quant_result": {"status": "completed", "score": 45, "direction": "防守"},
            "last_backtest_report": _base_report(max_drawdown=-12),
        }
        packet = service.build_strategy_execution_packet(state, target="002008.SZ")
        trace = packet["strategy_execution_trace"]
        joined_rules = json.dumps(trace["rules_fired"], ensure_ascii=False)

        self.assertEqual(packet["action"], "只观察")
        self.assertIn("量化偏弱", joined_rules)
        self.assertIn("降低", joined_rules + json.dumps(trace, ensure_ascii=False))
        self.assertFalse(trace["deepseek_used"])

    def test_deepseek_cache_does_not_feed_strategy_packet(self):
        state = {
            "legacy_quant_result": {"status": "completed", "score": 68, "direction": "偏积极"},
            "last_backtest_report": _base_report(),
            "command_center_2_deepseek_explanation": "大模型解释内容不应参与策略判断",
            "command_center_deepseek_latest_result": "最新解释缓存也不应参与策略判断",
        }
        packet = service.build_strategy_execution_packet(state, target="002008.SZ")
        serialized = json.dumps(packet, ensure_ascii=False)

        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["strategy_execution_trace"]["deepseek_used"])
        self.assertNotIn("大模型解释内容", serialized)
        self.assertNotIn("最新解释缓存", serialized)

    def test_service_does_not_import_streamlit(self):
        self.assertFalse(hasattr(service, "st"))
        self.assertNotIn("streamlit", service.__dict__)
        self.assertFalse("streamlit" in sys.modules and sys.modules["streamlit"] is service)


if __name__ == "__main__":
    unittest.main()
