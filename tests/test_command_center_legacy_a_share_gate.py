import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_legacy_a_share_gate as gate
import market_data_capability as capability


class CommandCenterLegacyAShareGateTests(unittest.TestCase):
    def test_missing_facts_do_not_count_as_cache(self):
        self.assertFalse(gate.has_a_share_professional_cache(None))
        self.assertFalse(gate.has_a_share_professional_cache({}))

    def test_manual_gate_packet_does_not_count_as_cache(self):
        packet = gate.build_manual_gate_a_share_professional_facts(
            "002008",
            updated_at="2026-06-03T10:00:00",
        )

        self.assertFalse(gate.has_a_share_professional_cache(packet))
        self.assertFalse(packet["available"])
        self.assertFalse(packet["deepseek_called"])
        self.assertIn("不自动请求 Tushare", packet["missing_items"][0])
        json.dumps(packet, ensure_ascii=False)

    def test_manual_gate_user_text_is_button_gated(self):
        self.assertIn("点击对应检测/刷新按钮后才会请求", gate.refresh_caption())
        self.assertIn("数据能力检测按钮", gate.empty_notice())
        self.assertNotIn("重新请求当前可用最新数据", gate.refresh_caption())

    def test_existing_updated_fact_counts_as_cache_even_if_unavailable(self):
        self.assertTrue(
            gate.has_a_share_professional_cache(
                {
                    "dragon_tiger": {
                        "available": False,
                        "message": "近30日未见龙虎榜上榜记录",
                        "updated_at": "2026-06-03T10:00:00",
                    }
                }
            )
        )

    def test_manual_gate_capability_items_require_manual_refresh(self):
        packet = gate.build_manual_gate_a_share_professional_facts(
            "002008",
            updated_at="2026-06-03T10:00:00",
        )
        by_section = {item["section"]: item for item in packet["data_capability"]["items"]}

        for section in gate.SECTION_SPECS:
            self.assertEqual(by_section[section]["capability_state"], capability.STATE_REQUIRES_MANUAL_REFRESH)
            self.assertEqual(by_section[section]["status"], "需要手动刷新")
            self.assertFalse(by_section[section]["ok"])

    def test_status_strip_summarizes_manual_gate_without_debug_text(self):
        packet = gate.build_manual_gate_a_share_professional_facts(
            "002008",
            updated_at="2026-06-03T10:00:00",
        )
        strip = gate.build_a_share_status_strip(packet, packet["data_capability"])
        dumped = json.dumps(strip, ensure_ascii=False)

        self.assertEqual(strip["status_label"], "待手动刷新")
        self.assertIn("手动刷新", strip["summary"])
        self.assertFalse(strip["deepseek_called"])
        self.assertNotIn("commit", dumped.lower())
        self.assertNotIn("feature present", dumped)

    def test_status_strip_prioritizes_restricted_capability(self):
        packet = {
            "updated_at": "2026-06-03T10:00:00",
            "margin": {"available": False, "updated_at": "2026-06-03T10:00:00"},
            "data_capability": {
                "source": "Tushare A股专业事实",
                "items": [
                    {"section": "moneyflow", "label": "个股资金流", "capability_state": capability.STATE_AVAILABLE, "status": "可用"},
                    {"section": "margin", "label": "融资融券", "capability_state": capability.STATE_PERMISSION_DENIED, "status": "权限不足"},
                ],
            },
        }

        strip = gate.build_a_share_status_strip(packet)

        self.assertEqual(strip["status_label"], "部分接口受限")
        self.assertEqual(strip["tone"], "failed")
        self.assertIn("可用 1", strip["summary"])
        self.assertIn("受限/失败 1", strip["summary"])

    def test_packet_summary_counts_ready_cached_waiting_and_failed(self):
        summary = gate.build_legacy_a_share_packet_summary(
            dragon_tiger_packet={
                "status": "ready",
                "data_status": "ready",
                "source": "Tushare 龙虎榜缓存",
                "api": "top_list/top_inst",
                "updated_at": "2026-06-03T10:00:00",
                "summary": "龙虎榜状态：席位净买入。",
            },
            margin_packet={
                "status": "failed",
                "data_status": "missing",
                "source": "Tushare margin_detail 缓存",
                "error": "权限不足",
            },
            moneyflow_packet={
                "status": "partial",
                "data_status": "cached",
                "summary": "近5日未取得可验证资金流。",
            },
            limit_emotion_packet={"status": "waiting"},
            chip_packet={},
        )

        self.assertEqual(summary["status_label"], "部分接口受限")
        self.assertEqual(summary["counts"], {"ready": 1, "cached": 1, "waiting": 2, "failed": 1})
        self.assertIn("已回流 1", summary["summary"])
        self.assertIn("页面打开不会自动请求 Tushare", summary["manual_note"])
        self.assertFalse(summary["deepseek_called"])
        by_key = {item["key"]: item for item in summary["items"]}
        self.assertEqual(by_key["dragon_tiger"]["status"], "已回流")
        self.assertEqual(by_key["margin"]["status"], "受限/失败")
        self.assertEqual(by_key["moneyflow"]["status"], "使用缓存/待复核")
        self.assertEqual(by_key["chip_radar"]["status"], "待手动刷新")

    def test_packet_summary_is_json_friendly_and_does_not_mutate_input(self):
        packet = {
            "status": "ready",
            "data_status": "ready",
            "risk_notes": ["资金净流入只作验证线索"],
            "updated_at": "2026-06-03T10:00:00",
        }
        before = copy.deepcopy(packet)

        summary = gate.build_legacy_a_share_packet_summary(moneyflow_packet=packet)

        self.assertEqual(packet, before)
        json.dumps(summary, ensure_ascii=False)
        moneyflow_item = [item for item in summary["items"] if item["key"] == "moneyflow"][0]
        self.assertEqual(moneyflow_item["risk_note"], "资金净流入只作验证线索")
        self.assertFalse(any(item["deepseek_called"] for item in summary["items"]))

    def test_packet_summary_handles_empty_packets(self):
        summary = gate.build_legacy_a_share_packet_summary()

        self.assertEqual(summary["status_label"], "待手动刷新")
        self.assertEqual(len(summary["items"]), 5)
        self.assertEqual(summary["counts"]["waiting"], 5)
        self.assertTrue(all(item["status"] == "待手动刷新" for item in summary["items"]))
        json.dumps(summary, ensure_ascii=False)

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_legacy_a_share_gate.py").read_text(encoding="utf-8"))
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
