import ast
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
