import json
import unittest

import command_center_chip_packet as chip_packet
import command_center_dragon_tiger_packet as dragon_tiger_packet
import command_center_legacy_packet_contract as contract
import command_center_limit_emotion_packet as limit_emotion_packet
import command_center_margin_packet as margin_packet
import command_center_moneyflow_packet as moneyflow_packet


class CommandCenterLegacyPacketContractTests(unittest.TestCase):
    def test_contract_maps_ready_cache_blocked_and_waiting(self):
        ready = contract.build_legacy_packet_decision_contract(
            {"status": "ready"},
            label="个股资金流",
            status="ready",
            data_status="ready",
            recovery_state="recovered",
            capability_state="available",
        )
        cached = contract.build_legacy_packet_decision_contract(
            {"decision_chain_state": "cache_only"},
            label="龙虎榜",
            status="ready",
            data_status="ready",
            recovery_state="recovered",
            capability_state="available",
        )
        blocked = contract.build_legacy_packet_decision_contract(
            {"can_enter_decision_chain": False},
            label="融资融券",
            status="ready",
            data_status="ready",
            recovery_state="recovered",
            capability_state="available",
        )
        waiting = contract.build_legacy_packet_decision_contract({}, label="涨跌停/情绪")

        self.assertEqual(ready["decision_chain_state"], "ready")
        self.assertTrue(ready["can_enter_decision_chain"])
        self.assertEqual(cached["decision_chain_state"], "cache_only")
        self.assertTrue(cached["can_enter_decision_chain"])
        self.assertEqual(blocked["decision_chain_state"], "blocked")
        self.assertFalse(blocked["can_enter_decision_chain"])
        self.assertEqual(waiting["decision_chain_state"], "waiting")
        self.assertFalse(waiting["can_enter_decision_chain"])
        self.assertFalse(ready["deepseek_called"])
        json.dumps([ready, cached, blocked, waiting], ensure_ascii=False)

    def test_a_share_legacy_packets_emit_decision_chain_contract(self):
        packet_builders = [
            (
                "command_center_moneyflow_packet",
                moneyflow_packet.build_command_center_moneyflow_packet,
                {"status": "ready", "data_status": "ready", "target": "002008.SZ"},
            ),
            (
                "command_center_margin_packet",
                margin_packet.build_command_center_margin_packet,
                {"status": "ready", "data_status": "ready", "target": "002008.SZ"},
            ),
            (
                "command_center_dragon_tiger_packet",
                dragon_tiger_packet.build_command_center_dragon_tiger_packet,
                {"status": "ready", "data_status": "ready", "target": "002008.SZ"},
            ),
            (
                "command_center_limit_emotion_packet",
                limit_emotion_packet.build_command_center_limit_emotion_packet,
                {"status": "ready", "data_status": "ready", "target": "002008.SZ"},
            ),
            (
                "command_center_chip_packet",
                chip_packet.build_command_center_chip_packet,
                {"status": "ready", "data_status": "ready", "target": "002008.SZ"},
            ),
        ]

        for key, builder, payload in packet_builders:
            with self.subTest(key=key):
                packet = builder({key: payload}, target="002008.SZ")

                self.assertEqual(packet["decision_chain_state"], "ready")
                self.assertEqual(packet["decision_chain_label"], "已验证")
                self.assertTrue(packet["can_enter_decision_chain"])
                self.assertIn("数据能力状态", packet["decision_chain_stage"])
                self.assertIn("可进入证据链", packet["decision_chain_effect"])
                self.assertEqual(packet["external_call_policy"], "not_triggered")
                self.assertFalse(packet["deepseek_called"])
                json.dumps(packet, ensure_ascii=False)

    def test_a_share_legacy_packets_block_permission_gaps(self):
        facts_items = {
            "moneyflow": (moneyflow_packet.build_command_center_moneyflow_packet, "moneyflow"),
            "margin": (margin_packet.build_command_center_margin_packet, "margin"),
            "dragon_tiger": (dragon_tiger_packet.build_command_center_dragon_tiger_packet, "dragon_tiger"),
            "limit_emotion": (limit_emotion_packet.build_command_center_limit_emotion_packet, "limit_emotion"),
            "chip_radar": (chip_packet.build_command_center_chip_packet, "chip_radar"),
        }

        for key, (builder, fact_key) in facts_items.items():
            with self.subTest(key=key):
                packet = builder(
                    {
                        "command_center_facts_packet": {
                            "items": [
                                {
                                    "key": fact_key,
                                    "state": "permission_denied",
                                    "status": "权限不足",
                                    "api": fact_key,
                                }
                            ]
                        }
                    }
                )

                self.assertEqual(packet["decision_chain_state"], "blocked")
                self.assertEqual(packet["decision_chain_label"], "阻断决策")
                self.assertFalse(packet["can_enter_decision_chain"])
                self.assertIn("阻断加仓", packet["decision_chain_effect"])
                self.assertFalse(packet["deepseek_called"])

    def test_explicit_cache_only_state_survives_packet_normalization(self):
        packet = dragon_tiger_packet.build_command_center_dragon_tiger_packet(
            {
                "command_center_dragon_tiger_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "target": "002008.SZ",
                    "decision_chain_state": "cache_only",
                    "can_enter_decision_chain": True,
                    "summary": "只取得龙虎榜上榜事实，席位仍待验证。",
                }
            },
            target="002008.SZ",
        )

        self.assertEqual(packet["decision_chain_state"], "cache_only")
        self.assertEqual(packet["decision_chain_label"], "缓存辅助")
        self.assertTrue(packet["can_enter_decision_chain"])
        self.assertIn("缓存/替代证据", packet["decision_chain_effect"])
        self.assertFalse(packet["deepseek_called"])


if __name__ == "__main__":
    unittest.main()
