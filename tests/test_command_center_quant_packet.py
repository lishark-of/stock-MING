import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_quant_packet as quant_packet


def _backtest_report():
    return {
        "ticker": "002008.SZ",
        "summary": "回测缓存显示趋势纪律可参考。",
        "metrics": {
            "round_trip_win_rate": 62,
            "max_drawdown_pct": -12,
        },
    }


class CommandCenterQuantPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = quant_packet.build_command_center_quant_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertEqual(packet["action_state"], "待刷新")
        self.assertEqual(packet["packet_role"], "量化推演证据")
        self.assertEqual(packet["verification_status"], "待验证")
        self.assertIn("待手动生成", packet["evidence_summary"])
        self.assertIn("手动生成量化推演", packet["action_hint"])
        self.assertIn("不能假装已有评分", packet["decision_guardrail"])
        self.assertIn("手动触发", packet["manual_required_text"])
        self.assertEqual(packet["decision_brief"]["action_mode"], "manual_quant_required")
        self.assertIn("不能假装已有评分", packet["decision_brief"]["guardrail_text"])
        self.assertEqual(packet["decision_chain_state"], "waiting")
        self.assertFalse(packet["can_enter_decision_chain"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_legacy_quant_result_is_normalized(self):
        state = {
            "legacy_quant_result": {
                "status": "completed",
                "generated_at": "2026-06-03T10:00:00",
                "target": "002008.SZ",
                "market_type": "A股",
                "score": 68,
                "direction": "偏积极但需验证",
                "summary": "轻量量化摘要已生成。",
                "source": "综合推演中心轻量摘要",
                "deepseek_called": True,
            },
            "last_backtest_report": _backtest_report(),
        }

        packet = quant_packet.build_command_center_quant_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["score"], 68)
        self.assertEqual(packet["direction"], "偏积极但需验证")
        self.assertEqual(packet["action_state"], "轻仓验证")
        self.assertIn(packet["confidence"], {"低", "中"})
        self.assertEqual(packet["packet_role"], "量化推演证据")
        self.assertEqual(packet["verification_status"], "已验证")
        self.assertIn("量化动作：轻仓验证", packet["evidence_summary"])
        self.assertIn("分数 68", packet["evidence_summary"])
        self.assertIn("置信度", packet["evidence_summary"])
        self.assertIn("置信度证据", packet["action_hint"])
        self.assertIn("不直接决定买卖", packet["decision_guardrail"])
        self.assertIn("回测缓存", packet["backtest_reference"])
        self.assertIn(packet["decision_brief"]["action_mode"], {"usable_evidence", "verify_quant"})
        self.assertEqual(packet["decision_brief"]["quant_policy"], "button_gated")
        self.assertEqual(packet["decision_chain_state"], "ready")
        self.assertTrue(packet["can_enter_decision_chain"])
        self.assertIn("量化推演", packet["decision_chain_effect"])
        self.assertFalse(packet["decision_brief"]["deepseek_called"])
        self.assertFalse(packet["deepseek_called"])

    def test_defensive_quant_result_stays_conservative(self):
        packet = quant_packet.build_command_center_quant_packet(
            {
                "legacy_quant_result": {
                    "status": "completed",
                    "score": 45,
                    "direction": "偏防守",
                    "summary": "风险偏高。",
                }
            }
        )

        self.assertEqual(packet["action_state"], "防守观察")
        self.assertEqual(packet["confidence"], "低")
        self.assertEqual(packet["verification_status"], "阻断决策")
        self.assertIn("量化动作：防守观察", packet["evidence_summary"])
        self.assertIn("不要用轻量摘要支持加仓", packet["action_hint"])
        self.assertIn("不能作为加仓", packet["decision_guardrail"])
        self.assertEqual(packet["decision_brief"]["action_mode"], "defensive_only")
        self.assertIn("不能作为加仓", packet["decision_brief"]["guardrail_text"])
        self.assertIn("缺少回测缓存", " ".join(packet["risk_notes"]))

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_quant_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "summary": "saved",
                "score": "66",
                "direction": "轻仓验证",
                "evidence_items": ["证据 A"],
                "risk_notes": ["风险 B"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = quant_packet.build_command_center_quant_packet(state, target="002008.SZ")

        self.assertEqual(state, original)
        self.assertEqual(packet["score"], 66)
        self.assertEqual(packet["evidence_items"], ["证据 A"])
        self.assertEqual(packet["risk_notes"], ["风险 B"])
        self.assertEqual(packet["packet_role"], "量化推演证据")
        self.assertTrue(packet["evidence_summary"])
        self.assertIn("不直接决定买卖", packet["decision_guardrail"])
        self.assertEqual(packet["decision_brief"]["action_mode"], "verify_quant")
        self.assertEqual(packet["decision_chain_state"], "ready")
        self.assertTrue(packet["can_enter_decision_chain"])
        self.assertFalse(packet["deepseek_called"])

    def test_quant_decision_brief_handles_cached_packet_without_external_calls(self):
        brief = quant_packet.build_quant_decision_brief(
            {
                "status": "partial",
                "data_status": "cached",
                "score": 61,
                "confidence": "低",
                "summary": "轻量量化缓存。",
            }
        )

        self.assertEqual(brief["action_mode"], "verify_quant")
        self.assertEqual(brief["external_call_policy"], "not_triggered")
        self.assertEqual(brief["quant_policy"], "button_gated")
        self.assertFalse(brief["deepseek_called"])
        json.dumps(brief, ensure_ascii=False)

    def test_target_mismatch_ignores_legacy_quant_result(self):
        packet = quant_packet.build_command_center_quant_packet(
            {
                "legacy_quant_result": {
                    "status": "completed",
                    "target": "002008.SZ",
                    "score": 68,
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_quant_packet.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        forbidden = {
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

        self.assertTrue(forbidden.isdisjoint(imports))


if __name__ == "__main__":
    unittest.main()
