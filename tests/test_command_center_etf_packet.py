import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_etf_packet as etf_packet


class CommandCenterEtfPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = etf_packet.build_command_center_etf_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertFalse(packet["recommended_etfs"])
        self.assertFalse(packet["actionable_etfs"])
        self.assertFalse(packet["watch_etfs"])
        self.assertFalse(packet["avoid_etfs"])
        self.assertFalse(packet["excluded_etfs"])
        self.assertFalse(packet["deepseek_called"])
        self.assertIn("不自动全量发现", packet["summary"])
        self.assertEqual(packet["packet_role"], "ETF/融资配置证据")
        self.assertEqual(packet["verification_status"], "待验证")
        self.assertIn("暂无 ETF/融资快照", packet["evidence_summary"])
        self.assertTrue(packet["evidence_items"])
        self.assertIn("手动刷新", packet["action_hint"])
        self.assertIn("不能作为买入", packet["decision_guardrail"])
        self.assertEqual(packet["decision_chain_state"], "waiting")

    def test_allocation_candidates_are_flattened_to_top_three(self):
        state = {
            "legacy_margin_etf_allocation_result": {
                "recommended_margin_ratio": 25,
                "recommended_cash_ratio": 20,
                "selected_etf_candidates": {
                    "科技成长ETF": [
                        {"etf_code": "512480.SH", "etf_name": "半导体 ETF", "total_score": 78},
                        {"etf_code": "560780.SH", "etf_name": "半导体设备ETF广发", "total_score": 74},
                    ],
                    "防守ETF": [
                        {"etf_code": "518880.SH", "etf_name": "黄金 ETF", "total_score": 66},
                        {"etf_code": "511880.SH", "etf_name": "银华日利", "total_score": 60},
                    ],
                },
            },
            "legacy_margin_etf_daily_packet": {
                "updated_at": "2026-06-03T10:00:00",
                "daily_dataset": {"status": "manual_basic_local_config"},
            },
        }

        packet = etf_packet.build_command_center_etf_packet(state)

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["recommended_margin_ratio"], 25)
        self.assertEqual(packet["recommended_cash_ratio"], 20)
        self.assertEqual(len(packet["recommended_etfs"]), 3)
        self.assertEqual(packet["recommended_etfs"][0]["code"], "512480.SH")
        self.assertEqual(packet["recommended_etfs"][0]["bucket"], "科技成长ETF")
        self.assertEqual(packet["recommended_etfs"][0]["status_label"], "只观察不追")
        self.assertTrue(packet["recommended_etfs"][0]["evidence_items"])
        self.assertTrue(packet["recommended_etfs"][0]["evidence_chain"])
        chain_keys = {item["key"] for item in packet["recommended_etfs"][0]["evidence_chain"]}
        self.assertEqual(
            chain_keys,
            {"tracking_index", "liquidity", "overlap", "overheat", "margin_cash"},
        )
        self.assertIn("融资", packet["recommended_etfs"][0]["evidence_chain"][-1]["label"])
        self.assertIn("不能放大仓位", packet["recommended_etfs"][0]["action_guardrail"])
        self.assertFalse(packet["recommended_etfs"][0]["deepseek_called"])
        self.assertIn("流动性", "；".join(packet["recommended_etfs"][0]["data_gaps"]))
        self.assertIn("不会自动全量发现", packet["recommended_etfs"][0]["manual_required_text"])
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["cache_state"], "ready")
        self.assertIn("不会自动全量发现", packet["manual_required_text"])
        self.assertEqual(packet["packet_role"], "ETF/融资配置证据")
        self.assertEqual(packet["verification_status"], "待验证")
        self.assertIn("ETF Top3", packet["evidence_summary"])
        self.assertIn("融资：25%", packet["evidence_summary"])
        self.assertIn("现金：20%", packet["evidence_summary"])
        self.assertTrue(packet["evidence_items"])
        self.assertIn("跟踪指数", packet["action_hint"])
        self.assertIn("ETF 候选不是买入指令", packet["decision_guardrail"])
        self.assertEqual(packet["decision_chain_state"], "ready")
        self.assertFalse(packet["deepseek_called"])

    def test_etf_candidates_are_layered_by_actionability(self):
        packet = etf_packet.build_command_center_etf_packet(
            {
                "legacy_margin_etf_allocation_result": {
                    "recommended_margin_ratio": 10,
                    "recommended_cash_ratio": 30,
                    "selected_etf_candidates": [
                        {
                            "code": "512480.SH",
                            "name": "半导体 ETF",
                            "bucket": "科技成长ETF",
                            "score": 82,
                            "state": "可配置",
                            "ratio_pct": 8,
                            "amount": 24000,
                            "reason": "芯片链强于指数。",
                        },
                        {
                            "code": "588000.SH",
                            "name": "科创50ETF",
                            "bucket": "宽基ETF",
                            "score": 75,
                            "state": "等回踩",
                        },
                        {
                            "code": "159915.SZ",
                            "name": "创业板ETF",
                            "bucket": "宽基ETF",
                            "score": 68,
                            "state": "不追高",
                            "reason": "短线过热。",
                        },
                        {
                            "code": "510300.SH",
                            "name": "沪深300ETF",
                            "bucket": "宽基ETF",
                            "state": "数据不足",
                            "reason": "流动性数据缺失。",
                        },
                    ],
                }
            }
        )

        self.assertEqual([item["code"] for item in packet["actionable_etfs"]], ["512480.SH"])
        self.assertEqual([item["code"] for item in packet["watch_etfs"]], ["588000.SH"])
        self.assertEqual([item["code"] for item in packet["avoid_etfs"]], ["159915.SZ"])
        self.assertEqual([item["code"] for item in packet["excluded_etfs"]], ["510300.SH"])
        self.assertEqual([item["code"] for item in packet["recommended_etfs"]], ["512480.SH", "588000.SH"])
        self.assertEqual(packet["recommended_etfs"][0]["status_label"], "可配置")
        self.assertEqual(packet["recommended_etfs"][1]["status_label"], "等回踩")
        self.assertNotIn("159915.SZ", {item["code"] for item in packet["recommended_etfs"]})
        self.assertNotIn("510300.SH", {item["code"] for item in packet["recommended_etfs"]})
        self.assertFalse(packet["deepseek_called"])

    def test_high_margin_makes_actionable_etfs_cash_only_and_blocks_new_margin(self):
        packet = etf_packet.build_command_center_etf_packet(
            {
                "legacy_margin_etf_allocation_result": {
                    "current_margin_debt_ratio": 30,
                    "recommended_margin_ratio": 20,
                    "recommended_cash_ratio": 25,
                    "selected_etf_candidates": [
                        {"code": "512480.SH", "name": "半导体 ETF", "score": 80, "state": "可配置"},
                    ],
                }
            }
        )

        self.assertEqual(packet["actionable_etfs"][0]["status_label"], "可用现金配置")
        self.assertFalse(packet["allow_new_margin"])
        self.assertIn("当前融资比例 30%", packet["margin_risk_notice"])
        self.assertIn("不建议新增融资", packet["margin_risk_notice"])
        self.assertIn("不建议因为 ETF 强", packet["leverage_guardrail"])
        self.assertFalse(packet["deepseek_called"])

    def test_only_avoid_or_excluded_items_do_not_enter_recommended_etfs(self):
        packet = etf_packet.build_command_center_etf_packet(
            {
                "legacy_margin_etf_allocation_result": {
                    "selected_etf_candidates": [
                        {"code": "159915.SZ", "name": "创业板ETF", "state": "过热", "score": 70},
                        {"code": "510300.SH", "name": "沪深300ETF", "state": "数据不足"},
                    ],
                }
            }
        )

        self.assertFalse(packet["recommended_etfs"])
        self.assertEqual([item["code"] for item in packet["avoid_etfs"]], ["159915.SZ"])
        self.assertEqual([item["code"] for item in packet["excluded_etfs"]], ["510300.SH"])
        self.assertFalse(packet["deepseek_called"])

    def test_name_only_etf_does_not_get_treated_as_code(self):
        packet = etf_packet.build_command_center_etf_packet(
            {
                "legacy_margin_etf_allocation_result": {
                    "selected_etf_candidates": [
                        {"code": "沪深300 ETF", "bucket": "宽基ETF", "state": "观察", "score": 70},
                    ],
                }
            }
        )

        candidate = packet["recommended_etfs"][0]
        self.assertEqual(candidate["name"], "沪深300 ETF")
        self.assertEqual(candidate["code"], "")
        self.assertEqual(candidate["status_label"], "观察")

    def test_risk_state_is_conservative_when_current_ratio_exceeds_recommendation(self):
        packet = etf_packet.build_command_center_etf_packet(
            {
                "legacy_margin_etf_allocation_result": {
                    "current_margin_debt_ratio": 30,
                    "recommended_margin_ratio": 20,
                    "selected_etf_candidates": [
                        {"code": "560780.SH", "name": "半导体设备ETF广发", "score": 72},
                    ],
                    "watch_not_chase_etfs": ["半导体 ETF 不追高"],
                }
            }
        )

        self.assertIn("降融资", packet["risk_state"])
        self.assertIn("半导体 ETF 不追高", packet["watch_not_chase"])

    def test_existing_packet_is_normalized_without_mutating_input(self):
        existing = {
            "command_center_etf_packet": {
                "status": "ready",
                "source": "saved",
                "recommended_etfs": [{"etf_code": "159801.SZ", "etf_name": "芯片ETF", "total_score": 70}],
                "watch_not_chase": ["不追高"],
                "risk_notes": ["保持现金缓冲"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(existing)

        packet = etf_packet.build_command_center_etf_packet(existing)

        self.assertEqual(existing, original)
        self.assertEqual(packet["recommended_etfs"][0]["code"], "159801.SZ")
        self.assertTrue(packet["recommended_etfs"][0]["evidence_items"])
        self.assertTrue(packet["recommended_etfs"][0]["evidence_chain"])
        self.assertIn("可参考", packet["recommended_etfs"][0]["evidence_chain_summary"])
        self.assertIn("不会自动全量发现", packet["manual_required_text"])
        self.assertEqual(packet["packet_role"], "ETF/融资配置证据")
        self.assertTrue(packet["evidence_summary"])
        self.assertTrue(packet["evidence_items"])
        self.assertEqual(packet["decision_chain_state"], "ready")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_etf_candidate_evidence_chain_uses_real_context_without_mutating_input(self):
        row = {
            "etf_code": "560780.SH",
            "etf_name": "半导体设备ETF广发",
            "bucket": "科技成长ETF",
            "tracking_index": "中证半导体设备主题指数",
            "turnover_yi": 8.6,
            "holding_overlap": "与芯片 ETF 有重叠",
            "premium_rate": "溢价待复核",
            "trigger_condition": "回踩 MA20 不破且成交额放大",
        }
        original = copy.deepcopy(row)

        candidate = etf_packet.normalize_etf_candidate(
            row,
            margin_context={
                "current_margin_ratio": 28,
                "recommended_margin_ratio": 20,
                "recommended_cash_ratio": 22,
            },
        )

        self.assertEqual(row, original)
        chain = {item["key"]: item for item in candidate["evidence_chain"]}
        self.assertEqual(chain["tracking_index"]["value"], "中证半导体设备主题指数")
        self.assertEqual(chain["liquidity"]["value"], "8.6亿")
        self.assertIn("重叠", chain["overlap"]["value"])
        self.assertIn("溢价", chain["overheat"]["value"])
        self.assertIn("现金缓冲 22%", chain["margin_cash"]["value"])
        self.assertEqual(chain["tracking_index"]["external_call_policy"], "not_triggered")
        self.assertFalse(chain["margin_cash"]["deepseek_called"])
        self.assertIn("不能放大仓位", candidate["action_guardrail"])
        json.dumps(candidate, ensure_ascii=False)

    def test_score_packet_can_supply_candidates_when_allocation_has_no_selected_items(self):
        packet = etf_packet.build_command_center_etf_packet(
            {
                "legacy_margin_etf_daily_packet": {
                    "score_packet": {
                        "rows": [
                            {"etf_code": "588000.SH", "etf_name": "科创50ETF", "total_score": 68},
                        ]
                    },
                    "daily_dataset": {"status": "manual_basic_local_config"},
                }
            }
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["recommended_etfs"][0]["code"], "588000.SH")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_etf_packet.py").read_text(encoding="utf-8"))
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
