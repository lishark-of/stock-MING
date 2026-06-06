import json
import unittest

import command_center_cloud_memory_packet as packet


class CommandCenterCloudMemoryPacketTests(unittest.TestCase):
    def test_builds_packet_from_loaded_legacy_memories(self):
        state = {
            "legacy_cloud_memories": [
                {
                    "id": 7,
                    "memory_type": "strategy",
                    "content": json.dumps(
                        {
                            "core_view": "跌破 MA20 后先降风险。",
                            "risk_triggers": ["跌破 MA20", "放量下跌"],
                            "source": "手动碎片投喂",
                            "status": "extracted",
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            "legacy_cloud_memories_loaded_at": "2026-06-06T10:00:00",
        }

        result = packet.build_command_center_cloud_memory_packet(state)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["data_status"], "ready")
        self.assertEqual(result["items"][0]["title"], "跌破 MA20 后先降风险。")
        self.assertIn("跌破 MA20", result["items"][0]["risk_triggers"])
        self.assertIn("已回流 1 条", result["summary"])
        self.assertFalse(result["deepseek_called"])

    def test_empty_packet_is_clear_waiting_state(self):
        result = packet.build_command_center_cloud_memory_packet({})

        self.assertEqual(result["status"], "waiting")
        self.assertEqual(result["data_status"], "missing")
        self.assertEqual(result["items"], [])
        self.assertIn("进入高级工具箱", result["summary"])
        self.assertFalse(result["deepseek_called"])


if __name__ == "__main__":
    unittest.main()
