import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_hard_risk_packet as hard_risk


class CommandCenterHardRiskPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_manual_packet(self):
        packet = hard_risk.build_command_center_hard_risk_packet({}, target="002008.SZ")

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertEqual(packet["risk_state"], "待验证")
        self.assertIn("不会自动请求", packet["summary"])
        self.assertIn("不能视为无风险", packet["manual_required_text"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_normalizes_a_share_professional_hard_risk_cache(self):
        state = {
            "a_share_professional_facts": {
                "verified_hard_risks": {
                    "available": True,
                    "target": "002008.SZ",
                    "updated_at": "2026-06-03T10:00:00",
                    "risk_flags": ["硬风险总览：减持与质押待验证"],
                    "announcements": {
                        "source": "Tushare",
                        "api": "anns_d",
                        "updated_at": "2026-06-03T10:01:00",
                        "rows": [
                            {"ann_date": "20260602", "title": "关于股东减持计划的公告", "source": "Tushare anns_d"}
                        ],
                        "risk_flags": ["公告标题线索涉及：减持"],
                    },
                    "pledge": {
                        "source": "Tushare",
                        "api": "pledge_stat/pledge_detail",
                        "rows": [
                            {"end_date": "20260531", "pledge_ratio": 31, "summary": "最近一期质押比例较高"}
                        ],
                        "risk_flags": ["最近一期质押比例较高：31%"],
                    },
                }
            }
        }

        packet = hard_risk.build_command_center_hard_risk_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["risk_state"], "风险线索存在")
        self.assertEqual(packet["risk_level"], "high")
        self.assertGreaterEqual(packet["risk_item_count"], 2)
        self.assertIn("减持", json.dumps(packet["announcement_items"], ensure_ascii=False))
        self.assertIn("质押", json.dumps(packet["pledge_items"], ensure_ascii=False))
        self.assertFalse(packet["deepseek_called"])

    def test_permission_denied_is_conservative(self):
        state = {
            "command_center_hard_risk_packet": {
                "status": "failed",
                "data_status": "missing",
                "source": "Tushare",
                "api": "anns_d",
                "error": "权限不足",
                "updated_at": "2026-06-03T10:00:00",
            }
        }

        packet = hard_risk.build_command_center_hard_risk_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "failed")
        self.assertEqual(packet["data_status"], "missing")
        self.assertEqual(packet["risk_state"], "硬风险待排查")
        self.assertIn("不能把缺口写成无风险", "；".join(packet["risk_notes"]))

    def test_existing_packet_is_preserved_without_mutation(self):
        state = {
            "command_center_hard_risk_packet": {
                "status": "ready",
                "data_status": "ready",
                "ticker": "002008.SZ",
                "risk_items": [{"type": "公告风险", "message": "监管问询待验证"}],
                "deepseek_called": True,
            }
        }
        before = copy.deepcopy(state)

        packet = hard_risk.build_command_center_hard_risk_packet(state, target="002008.SZ")

        self.assertEqual(state, before)
        self.assertEqual(packet["risk_state"], "风险线索存在")
        self.assertFalse(packet["deepseek_called"])

    def test_target_mismatch_ignores_payload(self):
        state = {
            "command_center_hard_risk_packet": {
                "status": "ready",
                "data_status": "ready",
                "ticker": "600519.SH",
                "risk_items": [{"type": "公告风险", "message": "旧标的公告线索"}],
            }
        }

        packet = hard_risk.build_command_center_hard_risk_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertEqual(packet["risk_items"], [])

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_hard_risk_packet.py").read_text(encoding="utf-8"))
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
