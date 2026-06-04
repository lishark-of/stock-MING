import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_dragon_tiger_packet as dragon_packet


class CommandCenterDragonTigerPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = dragon_packet.build_command_center_dragon_tiger_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不会自动请求", packet["summary"])
        self.assertIn("手动刷新", packet["manual_required_text"])
        self.assertEqual(packet["packet_role"], "A股龙虎榜席位证据")
        self.assertEqual(packet["verification_status"], "待验证")
        self.assertIn("待手动刷新", packet["evidence_summary"])
        self.assertIn("手动刷新", packet["action_hint"])
        self.assertIn("缺少龙虎榜", packet["decision_guardrail"])
        self.assertEqual(packet["evidence_items"][0]["status"], "待验证")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_a_share_professional_dragon_tiger_is_normalized(self):
        state = {
            "a_share_professional_facts": {
                "dragon_tiger": {
                    "available": True,
                    "latest_date": "20260603",
                    "reason": "日涨幅偏离值达7%",
                    "close": "25.6",
                    "pct_change": "9.8",
                    "buy_amount_yi": "2.4",
                    "sell_amount_yi": "1.1",
                    "net_buy_amount_yi": "1.3",
                    "inst_summary": "席位3条，净买入1.3亿",
                    "inst_rows": [
                        {"name": "机构专用", "buy": "120000000", "sell": "20000000", "net_buy": "100000000"}
                    ],
                    "updated_at": "2026-06-03T16:00:00",
                }
            }
        }

        packet = dragon_packet.build_command_center_dragon_tiger_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["capability_state"], "available")
        self.assertEqual(packet["status_label"], "可用")
        self.assertEqual(packet["recovery_state"], "recovered")
        self.assertEqual(packet["net_buy_amount_yi"], 1.3)
        self.assertEqual(packet["activity_state"], "席位净买入")
        self.assertEqual(packet["inst_rows"][0]["name"], "机构专用")
        self.assertEqual(packet["verification_status"], "已验证")
        self.assertIn("席位行为：席位净买入", packet["evidence_summary"])
        self.assertIn("净买入 1.3 亿", packet["evidence_summary"])
        self.assertIn("席位明细 1 条", packet["evidence_summary"])
        self.assertIn("席位行为线索", packet["action_hint"])
        self.assertIn("不能单独构成买入", packet["decision_guardrail"])
        evidence_by_key = {item["key"]: item for item in packet["evidence_items"]}
        self.assertEqual(evidence_by_key["net_buy_amount"]["value"], "1.3 亿")
        self.assertEqual(evidence_by_key["inst_rows"]["status"], "已回流")
        self.assertIn("不单独构成买入理由", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_empty_recent_is_not_treated_as_support(self):
        packet = dragon_packet.build_command_center_dragon_tiger_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "dragon_tiger",
                            "label": "龙虎榜",
                            "state": "empty_recent",
                            "status": "近期无数据",
                            "api": "top_list",
                            "risk": "近30日未见龙虎榜上榜记录",
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
        self.assertIn("缺少龙虎榜", packet["decision_guardrail"])
        self.assertIn("不等于机构支持", " ".join(packet["risk_notes"]))

    def test_permission_denied_is_blocked_not_support(self):
        packet = dragon_packet.build_command_center_dragon_tiger_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "dragon_tiger",
                            "label": "龙虎榜",
                            "state": "permission_denied",
                            "status": "权限不足",
                            "api": "top_list/top_inst",
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
        self.assertIn("top_list/top_inst 权限", packet["action_hint"])
        self.assertIn("缺少龙虎榜", packet["decision_guardrail"])
        self.assertIn("不等于机构支持", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_available_capability_item_marks_recovered_without_fake_rows(self):
        packet = dragon_packet.build_command_center_dragon_tiger_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "dragon_tiger",
                            "label": "龙虎榜",
                            "state": "available",
                            "status": "可用",
                            "api": "top_list/top_inst",
                            "rows": 1,
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
        self.assertEqual(packet["trade_date"], "20260603")
        self.assertEqual(packet["inst_rows"], [])
        self.assertIn("接口可用", packet["evidence_summary"])
        self.assertIn("不能写成机构支持", packet["action_hint"])
        self.assertIn("状态", packet["summary"])
        self.assertFalse(packet["deepseek_called"])

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_dragon_tiger_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "net_buy_amount_yi": "1.2",
                "activity_state": "席位净买入",
                "summary": "saved",
                "risk_notes": ["风险 A"],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = dragon_packet.build_command_center_dragon_tiger_packet(state, target="002008.SZ")

        self.assertEqual(state, original)
        self.assertEqual(packet["net_buy_amount_yi"], 1.2)
        self.assertEqual(packet["summary"], "saved")
        self.assertFalse(packet["deepseek_called"])

    def test_target_mismatch_ignores_existing_payload(self):
        packet = dragon_packet.build_command_center_dragon_tiger_packet(
            {
                "command_center_dragon_tiger_packet": {
                    "status": "ready",
                    "target": "002008.SZ",
                    "net_buy_amount_yi": 1.1,
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_dragon_tiger_packet.py").read_text(encoding="utf-8"))
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
