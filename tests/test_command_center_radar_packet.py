import ast
import json
import unittest
from pathlib import Path

import command_center_radar_packet as radar


class CommandCenterRadarPacketTests(unittest.TestCase):
    def test_builds_top_three_candidates_from_scan_cache(self):
        packet = radar.build_command_center_radar_packet(
            {
                "radar_scan_status": "completed",
                "radar_scan_results": {
                    "generated_at": "2026-06-03T10:00:00",
                    "rule_rows": [
                        {
                            "candidate": {"ticker": "300750.SZ", "name": "宁德时代"},
                            "score": {
                                "total_score": 82,
                                "battle_state": "等验证",
                                "battle_state_reason": "趋势较强但等待量能确认。",
                                "trigger_conditions": ["放量站稳 MA20", "行业强于指数"],
                                "invalid_conditions": ["跌破 MA20", "资金流转弱"],
                            },
                            "candidate_context": {"scan_source": "手动候选池"},
                        },
                        {"candidate": {"ticker": "512480.SH", "name": "半导体 ETF"}, "score": {"total_score": 76, "battle_state": "只观察"}},
                        {"candidate": {"ticker": "600519.SH", "name": "贵州茅台"}, "score": {"total_score": 69, "battle_state": "暂不纳入"}},
                        {"candidate": {"ticker": "000001.SZ", "name": "平安银行"}, "score": {"total_score": 50, "battle_state": "暂不纳入"}},
                    ],
                    "summary": {"note": "规则雷达缓存展示。", "deepseek_called": False},
                },
            }
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["display_count"], 2)
        self.assertEqual(packet["top_candidates"][0]["ticker"], "300750.SZ")
        self.assertEqual(packet["top_candidates"][0]["status_label"], "等验证")
        self.assertEqual(packet["top_candidates"][1]["ticker"], "512480.SH")
        self.assertEqual(packet["top_candidates"][1]["status_label"], "只观察")
        self.assertEqual(len(packet["excluded_candidates"]), 2)
        self.assertEqual(packet["excluded_candidates"][0]["ticker"], "600519.SH")
        self.assertEqual(packet["excluded_candidates"][0]["status_label"], "暂不纳入")
        self.assertTrue(packet["has_actionable_candidates"])
        self.assertEqual(packet["top_candidates"][0]["tone"], "stale")
        self.assertEqual(packet["top_candidates"][0]["trigger_condition"], "放量站稳 MA20；行业强于指数")
        self.assertEqual(packet["top_candidates"][0]["invalidation_condition"], "跌破 MA20；资金流转弱")
        self.assertTrue(packet["top_candidates"][0]["evidence_items"])
        chain = {item["key"]: item for item in packet["top_candidates"][0]["evidence_chain"]}
        self.assertEqual(list(chain), ["moneyflow", "dragon_tiger", "limit_emotion", "hard_risk"])
        self.assertEqual(chain["moneyflow"]["status"], "missing")
        self.assertEqual(chain["moneyflow"]["writes_packet"], "command_center_moneyflow_packet")
        self.assertEqual(chain["dragon_tiger"]["writes_packet"], "command_center_dragon_tiger_packet")
        self.assertIn("待补证", packet["top_candidates"][0]["evidence_chain_summary"])
        self.assertIn("候选不是买入指令", packet["top_candidates"][0]["action_guardrail"])
        brief = packet["top_candidates"][0]["decision_brief"]
        self.assertEqual(brief["execution_status"], "verify")
        self.assertEqual(brief["execution_label"], "等验证")
        self.assertEqual(brief["confidence_gate"], "待补证")
        self.assertIn("资金流", brief["missing_evidence"])
        self.assertIn("高级工具箱", brief["recovery_route"])
        self.assertIn("候选不是买入指令", brief["guardrail"])
        self.assertFalse(brief["deepseek_called"])
        self.assertEqual(brief["external_call_policy"], "not_triggered")
        self.assertIn("等验证", packet["decision_summary"]["headline"])
        self.assertFalse(any(item["deepseek_called"] for item in chain.values()))
        self.assertIn("不会自动全市场扫描", packet["top_candidates"][0]["manual_required_text"])
        self.assertIn("不会自动全市场扫描", packet["manual_required_text"])
        self.assertEqual(packet["decision_chain_state"], "ready")
        self.assertTrue(packet["can_enter_decision_chain"])
        self.assertIn("下一票雷达", packet["decision_chain_effect"])
        self.assertEqual(packet["packet_role"], "下一票 Top3 候选证据")
        self.assertEqual(packet["verification_status"], "待验证")
        self.assertIn("下一票 Top2", packet["evidence_summary"])
        self.assertIn("等验证 1", packet["evidence_summary"])
        self.assertTrue(packet["evidence_items"])
        self.assertIn("候选不是买入指令", packet["decision_guardrail"])
        self.assertIn("补齐", packet["action_hint"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_excluded_candidates_do_not_enter_top_three(self):
        packet = radar.build_command_center_radar_packet(
            {
                "radar_scan_status": "completed",
                "radar_scan_results": {
                    "generated_at": "2026-06-06T10:00:00",
                    "rule_rows": [
                        {"candidate": {"ticker": "601138.SH", "name": "工业富联"}, "score": {"total_score": 91, "battle_state": "暂不纳入"}},
                        {"candidate": {"ticker": "688041.SH", "name": "海光信息"}, "score": {"total_score": 68, "battle_state": "只观察"}},
                        {"candidate": {"ticker": "300750.SZ", "name": "宁德时代"}, "score": {"total_score": 64, "battle_state": "等验证"}},
                        {"candidate": {"ticker": "002008.SZ", "name": "大族激光"}, "score": {"total_score": 55, "battle_state": "可准备"}},
                    ],
                    "summary": {"deepseek_called": False},
                },
            }
        )

        self.assertEqual([item["ticker"] for item in packet["top_candidates"]], ["002008.SZ", "300750.SZ", "688041.SH"])
        self.assertEqual([item["status_label"] for item in packet["top_candidates"]], ["可准备", "等验证", "只观察"])
        self.assertEqual(packet["excluded_candidates"][0]["ticker"], "601138.SH")
        self.assertNotIn("601138.SH", [item["ticker"] for item in packet["top_candidates"]])
        self.assertFalse(packet["deepseek_called"])

    def test_packet_empty_main_candidates_keeps_exclusions(self):
        packet = radar.build_command_center_radar_packet(
            {
                "radar_scan_status": "completed",
                "radar_scan_results": {
                    "generated_at": "2026-06-06T10:00:00",
                    "rule_rows": [
                        {"candidate": {"ticker": "601138.SH", "name": "工业富联"}, "score": {"total_score": 91, "battle_state": "暂不纳入"}},
                        {"candidate": {"ticker": "600519.SH", "name": "贵州茅台"}, "score": {"total_score": 70, "battle_state": "风险过高"}},
                    ],
                    "summary": {"deepseek_called": False},
                },
            }
        )

        self.assertEqual(packet["top_candidates"], [])
        self.assertEqual(len(packet["excluded_candidates"]), 2)
        self.assertFalse(packet["has_actionable_candidates"])
        self.assertIn("本轮轻量雷达未产生可执行候选", packet["summary"])
        self.assertFalse(packet["deepseek_called"])

    def test_waiting_packet_when_cache_missing(self):
        packet = radar.build_command_center_radar_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["top_candidates"], [])
        self.assertIn("不会自动全市场扫描", packet["summary"])
        self.assertEqual(packet["cache_state"], "missing")
        self.assertEqual(packet["decision_chain_state"], "waiting")
        self.assertFalse(packet["can_enter_decision_chain"])
        self.assertEqual(packet["packet_role"], "下一票 Top3 候选证据")
        self.assertEqual(packet["verification_status"], "待验证")
        self.assertIn("暂无下一票 Top3", packet["evidence_summary"])
        self.assertIn("手动", packet["action_hint"])
        self.assertIn("不能把下一票雷达写成买入", packet["decision_guardrail"])
        self.assertFalse(packet["deepseek_called"])

    def test_builds_from_top_candidates_cache_shape(self):
        packet = radar.build_command_center_radar_packet(
            {
                "radar_scan_results": {
                    "generated_at": "2026-06-03T10:00:00",
                    "top_candidates": [
                        {
                            "ticker": "300750.SZ",
                            "name": "宁德时代",
                            "score": 82,
                            "action_state": "等验证",
                            "trigger_condition": "放量站稳 MA20",
                            "invalidation_condition": "跌破 MA20",
                        }
                    ],
                    "summary": {"source_mode": "下一票雷达本地缓存", "deepseek_called": False},
                },
            }
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["display_count"], 1)
        self.assertEqual(packet["top_candidates"][0]["ticker"], "300750.SZ")
        self.assertEqual(packet["top_candidates"][0]["status_label"], "等验证")
        self.assertEqual(packet["top_candidates"][0]["decision_brief"]["execution_label"], "等验证")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_existing_packet_is_preserved_without_mutation(self):
        existing = {
            "status": "ready",
            "top_candidates": [{"ticker": "A", "name": "Alpha"}],
            "deepseek_called": False,
        }
        state = {"command_center_radar_packet": existing}
        packet = radar.build_command_center_radar_packet(state)

        self.assertIsNot(packet, existing)
        self.assertEqual(packet["top_candidates"][0]["ticker"], "A")
        self.assertIn("decision_brief", packet["top_candidates"][0])
        self.assertIn("decision_summary", packet)
        self.assertEqual(packet["decision_chain_state"], "ready")
        self.assertTrue(packet["can_enter_decision_chain"])
        self.assertEqual(packet["packet_role"], "下一票 Top3 候选证据")
        self.assertTrue(packet["evidence_summary"])
        self.assertTrue(packet["evidence_items"])
        self.assertEqual(existing, state["command_center_radar_packet"])

    def test_candidate_decision_brief_modes_are_actionable(self):
        ready = radar.build_candidate_decision_brief({"action_state": "可准备", "evidence_chain": []})
        verify = radar.build_candidate_decision_brief(
            {
                "action_state": "等验证",
                "evidence_chain": [{"label": "资金流", "status": "missing"}],
            }
        )
        observe = radar.build_candidate_decision_brief({"action_state": "只观察"})
        blocked = radar.build_candidate_decision_brief({"action_state": "暂不纳入"})

        self.assertEqual(ready["execution_status"], "prepare")
        self.assertIn("触发条件", ready["next_action"])
        self.assertEqual(verify["execution_status"], "verify")
        self.assertIn("资金流", verify["missing_evidence"])
        self.assertEqual(observe["execution_label"], "只观察")
        self.assertEqual(blocked["confidence_gate"], "不可执行")
        for brief in [ready, verify, observe, blocked]:
            self.assertFalse(brief["deepseek_called"])
            json.dumps(brief, ensure_ascii=False)

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_radar_packet.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        forbidden = {
            "streamlit",
            "app",
            "tushare_adapter",
            "tushare",
            "akshare",
            "yfinance",
            "data_fetcher",
            "backtester",
            "openai",
        }
        self.assertTrue(forbidden.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
