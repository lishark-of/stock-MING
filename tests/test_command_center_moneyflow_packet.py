import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_moneyflow_packet as moneyflow_packet


class CommandCenterMoneyflowPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = moneyflow_packet.build_command_center_moneyflow_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不会自动请求", packet["summary"])
        self.assertIn("手动刷新", packet["manual_required_text"])
        self.assertEqual(packet["packet_role"], "A股个股资金流证据")
        self.assertEqual(packet["verification_status"], "待验证")
        self.assertIn("待手动刷新", packet["evidence_summary"])
        self.assertIn("手动刷新", packet["action_hint"])
        self.assertIn("缺少个股资金流", packet["decision_guardrail"])
        self.assertEqual(packet["evidence_items"][0]["status"], "待验证")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_a_share_professional_moneyflow_is_normalized(self):
        state = {
            "a_share_professional_facts": {
                "moneyflow": {
                    "available": True,
                    "date": "20260603",
                    "main_net_yi": "1.23",
                    "five_day_main_net_yi": "3.45",
                    "large_net_yi": "0.7",
                    "medium_net_yi": "-0.2",
                    "small_net_yi": "-0.1",
                    "direction": "主力回流",
                    "updated_at": "2026-06-03T16:00:00",
                }
            }
        }

        packet = moneyflow_packet.build_command_center_moneyflow_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["capability_state"], "available")
        self.assertEqual(packet["status_label"], "可用")
        self.assertEqual(packet["recovery_state"], "recovered")
        self.assertEqual(packet["main_net_yi"], 1.23)
        self.assertEqual(packet["five_day_main_net_yi"], 3.45)
        self.assertEqual(packet["flow_state"], "主力净流入")
        self.assertEqual(packet["verification_status"], "已验证")
        self.assertIn("资金状态：主力净流入", packet["evidence_summary"])
        self.assertIn("近5日主力净额 3.45 亿", packet["evidence_summary"])
        self.assertIn("当日主力净额 1.23 亿", packet["evidence_summary"])
        self.assertIn("验证线索", packet["action_hint"])
        self.assertIn("不能单独构成买入", packet["decision_guardrail"])
        evidence_by_key = {item["key"]: item for item in packet["evidence_items"]}
        self.assertEqual(evidence_by_key["five_day_main_net"]["value"], "3.45 亿")
        self.assertEqual(evidence_by_key["main_net"]["status"], "已验证")
        self.assertIn("不单独构成买入理由", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_facts_item_empty_recent_stays_missing(self):
        packet = moneyflow_packet.build_command_center_moneyflow_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "moneyflow",
                            "label": "个股资金流",
                            "state": "empty_recent",
                            "status": "近期无数据",
                            "api": "moneyflow",
                            "risk": "近5日未取得可验证个股资金流。",
                        }
                    ]
                }
            }
        )

        self.assertEqual(packet["status"], "partial")
        self.assertEqual(packet["data_status"], "missing")
        self.assertEqual(packet["capability_state"], "empty_recent")
        self.assertEqual(packet["status_label"], "近期无数据")
        self.assertEqual(packet["recovery_state"], "waiting")
        self.assertEqual(packet["verification_status"], "待验证")
        self.assertIn("待手动刷新", packet["evidence_summary"])
        self.assertIn("缺少个股资金流", packet["decision_guardrail"])
        self.assertIn("不能把缺失数据当成无资金风险", " ".join(packet["risk_notes"]))

    def test_permission_denied_is_blocked_not_neutral(self):
        packet = moneyflow_packet.build_command_center_moneyflow_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "moneyflow",
                            "label": "个股资金流",
                            "state": "permission_denied",
                            "status": "权限不足",
                            "api": "moneyflow",
                            "risk": "抱歉，您没有访问该接口的权限。",
                            "checked_at": "2026-06-03T10:02:00",
                        }
                    ]
                }
            }
        )

        self.assertEqual(packet["status"], "failed")
        self.assertEqual(packet["data_status"], "missing")
        self.assertEqual(packet["capability_state"], "permission_denied")
        self.assertEqual(packet["status_label"], "权限不足")
        self.assertEqual(packet["recovery_state"], "blocked")
        self.assertEqual(packet["updated_at"], "2026-06-03T10:02:00")
        self.assertEqual(packet["checked_at"], "2026-06-03T10:02:00")
        self.assertEqual(packet["verification_status"], "阻断决策")
        self.assertIn("权限不足", packet["evidence_summary"])
        self.assertIn("moneyflow 权限", packet["action_hint"])
        self.assertIn("缺少个股资金流", packet["decision_guardrail"])
        self.assertIn("不能把缺失数据当成无资金风险", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_available_capability_item_marks_recovered_without_fake_flow(self):
        packet = moneyflow_packet.build_command_center_moneyflow_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "moneyflow",
                            "label": "个股资金流",
                            "state": "available",
                            "status": "可用",
                            "api": "moneyflow",
                            "rows": 5,
                            "latest_date": "20260603",
                            "checked_at": "2026-06-03T10:02:00",
                        }
                    ]
                }
            }
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["capability_state"], "available")
        self.assertEqual(packet["status_label"], "可用")
        self.assertEqual(packet["recovery_state"], "recovered")
        self.assertEqual(packet["main_net_yi"], None)
        self.assertEqual(packet["trade_date"], "20260603")
        self.assertIn("接口可用", packet["evidence_summary"])
        self.assertIn("不能单独触发买入", packet["action_hint"])
        self.assertIn("状态", packet["summary"])
        self.assertFalse(packet["deepseek_called"])

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_moneyflow_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "main_net_yi": "1.5",
                "flow_state": "主力净流入",
                "summary": "saved",
                "risk_notes": ["风险 A"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = moneyflow_packet.build_command_center_moneyflow_packet(state, target="002008.SZ")

        self.assertEqual(state, original)
        self.assertEqual(packet["main_net_yi"], 1.5)
        self.assertEqual(packet["summary"], "saved")
        self.assertFalse(packet["deepseek_called"])

    def test_target_mismatch_ignores_existing_payload(self):
        packet = moneyflow_packet.build_command_center_moneyflow_packet(
            {
                "command_center_moneyflow_packet": {
                    "status": "ready",
                    "target": "002008.SZ",
                    "main_net_yi": 1.1,
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_moneyflow_packet.py").read_text(encoding="utf-8"))
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
