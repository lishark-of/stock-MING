import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_limit_emotion_packet as limit_packet


class CommandCenterLimitEmotionPacketTests(unittest.TestCase):
    def test_missing_cache_returns_waiting_packet(self):
        packet = limit_packet.build_command_center_limit_emotion_packet({})

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")
        self.assertIn("不会自动请求", packet["summary"])
        self.assertIn("手动刷新", packet["manual_required_text"])
        self.assertEqual(packet["packet_role"], "A股涨跌停/情绪证据")
        self.assertEqual(packet["verification_status"], "待验证")
        self.assertIn("待手动刷新", packet["evidence_summary"])
        self.assertIn("手动刷新", packet["action_hint"])
        self.assertIn("缺少涨跌停/情绪", packet["decision_guardrail"])
        self.assertEqual(packet["evidence_items"][0]["status"], "待验证")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_a_share_professional_limit_emotion_is_normalized(self):
        state = {
            "a_share_professional_facts": {
                "limit_emotion": {
                    "available": True,
                    "boundary_available": True,
                    "records_available": True,
                    "concept_available": True,
                    "latest_date": "20260603",
                    "up_limit": "12.34",
                    "down_limit": "10.10",
                    "current_price": "12.05",
                    "distance_to_up_pct": "2.41",
                    "distance_to_down_pct": "16.18",
                    "limit_records": [
                        {
                            "日期": "2026-06-03",
                            "类型": "炸板",
                            "开板次数": 2,
                            "封单金额(亿)": 1.2,
                            "连板统计": "2连",
                        }
                    ],
                    "concept_top5": [
                        {"概念": "机器人", "涨停家数": 8, "排名": 1},
                    ],
                    "updated_at": "2026-06-03T15:30:00",
                }
            }
        }

        packet = limit_packet.build_command_center_limit_emotion_packet(state, target="002008.SZ")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["up_limit"], 12.34)
        self.assertEqual(packet["distance_to_up_pct"], 2.41)
        self.assertEqual(packet["emotion_state"], "接近涨停/追高区")
        self.assertTrue(packet["flags"]["has_break_limit"])
        self.assertEqual(packet["limit_records"][0]["type"], "炸板")
        self.assertEqual(packet["concept_top5"][0]["name"], "机器人")
        self.assertEqual(packet["verification_status"], "已验证")
        self.assertIn("距涨停 2.41%", packet["evidence_summary"])
        self.assertIn("概念热度 1 项", packet["evidence_summary"])
        self.assertIn("防追高", packet["action_hint"])
        self.assertIn("禁止把热度写成追高理由", packet["decision_guardrail"])
        evidence_by_key = {item["key"]: item for item in packet["evidence_items"]}
        self.assertEqual(evidence_by_key["limit_distance"]["value"], "2.41%")
        self.assertEqual(evidence_by_key["concept_strength"]["status"], "已回流")
        self.assertIn("防追高", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_permission_denied_stays_missing_and_conservative(self):
        packet = limit_packet.build_command_center_limit_emotion_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "limit_emotion",
                            "label": "涨跌停/情绪",
                            "state": "permission_denied",
                            "status": "权限不足",
                            "api": "limit_cpt_list",
                            "risk": "limit_cpt_list 当前权限不足，已在本会话跳过重复请求。",
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
        self.assertEqual(packet["verification_status"], "阻断决策")
        self.assertIn("权限不足", packet["evidence_summary"])
        self.assertIn("Tushare 权限", packet["action_hint"])
        self.assertIn("缺少涨跌停/情绪", packet["decision_guardrail"])
        self.assertIn("不能把缺失数据当成无追高风险", " ".join(packet["risk_notes"]))
        self.assertFalse(packet["deepseek_called"])

    def test_disabled_this_session_keeps_skip_state_and_checked_at(self):
        packet = limit_packet.build_command_center_limit_emotion_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "limit_emotion",
                            "label": "涨跌停/情绪",
                            "state": "disabled_this_session",
                            "status": "本会话跳过",
                            "api": "limit_cpt_list",
                            "message": "limit_cpt_list 当前权限不足，已在本会话跳过重复请求。",
                            "checked_at": "2026-06-03T10:02:00",
                        }
                    ]
                }
            }
        )

        self.assertEqual(packet["status"], "failed")
        self.assertEqual(packet["data_status"], "missing")
        self.assertEqual(packet["capability_state"], "disabled_this_session")
        self.assertEqual(packet["status_label"], "本会话跳过")
        self.assertEqual(packet["recovery_state"], "blocked")
        self.assertEqual(packet["updated_at"], "2026-06-03T10:02:00")
        self.assertEqual(packet["checked_at"], "2026-06-03T10:02:00")
        self.assertIn("本会话跳过", packet["summary"])
        self.assertFalse(packet["deepseek_called"])

    def test_available_capability_item_marks_recovered_without_fake_records(self):
        packet = limit_packet.build_command_center_limit_emotion_packet(
            {
                "command_center_facts_packet": {
                    "items": [
                        {
                            "key": "limit_emotion",
                            "label": "涨跌停/情绪",
                            "state": "available",
                            "status": "可用",
                            "api": "limit_cpt_list",
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
        self.assertEqual(packet["trade_date"], "20260603")
        self.assertEqual(packet["limit_records"], [])
        self.assertEqual(packet["concept_top5"], [])
        self.assertIn("接口可用", packet["evidence_summary"])
        self.assertIn("不能单独触发买入", packet["action_hint"])
        self.assertIn("状态", packet["summary"])
        self.assertFalse(packet["deepseek_called"])

    def test_existing_packet_is_preserved_without_mutating_input(self):
        state = {
            "command_center_limit_emotion_packet": {
                "status": "ready",
                "target": "002008.SZ",
                "up_limit": "12.3",
                "distance_to_up_pct": "1.5",
                "emotion_state": "接近涨停/追高区",
                "summary": "saved",
                "limit_records": [{"type": "涨停", "date": "20260603"}],
                "deepseek_called": True,
            }
        }
        original = copy.deepcopy(state)

        packet = limit_packet.build_command_center_limit_emotion_packet(state, target="002008.SZ")

        self.assertEqual(state, original)
        self.assertEqual(packet["up_limit"], 12.3)
        self.assertEqual(packet["summary"], "saved")
        self.assertEqual(packet["emotion_state"], "接近涨停/追高区")
        self.assertFalse(packet["deepseek_called"])

    def test_target_mismatch_ignores_existing_payload(self):
        packet = limit_packet.build_command_center_limit_emotion_packet(
            {
                "command_center_limit_emotion_packet": {
                    "status": "ready",
                    "target": "002008.SZ",
                    "up_limit": 12.3,
                }
            },
            target="000001.SZ",
        )

        self.assertEqual(packet["status"], "waiting")
        self.assertEqual(packet["data_status"], "missing")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_limit_emotion_packet.py").read_text(encoding="utf-8"))
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
