import json
import tempfile
import unittest
from pathlib import Path

import command_center_home_snapshot as snapshot


class CommandCenterHomeSnapshotTests(unittest.TestCase):
    def test_missing_snapshot_returns_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = snapshot.load_home_action_snapshot(base_dir=tmp)

        self.assertTrue(payload["is_empty"])
        self.assertEqual(payload["data_freshness"]["state"], "missing")
        self.assertIn("暂无可执行候选", payload["empty_message"])

    def test_save_and_load_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = snapshot.build_home_action_snapshot(
                {
                    "command_center_decision_packet": {
                        "status": "ready",
                        "overall_action": "只观察",
                        "updated_at": "2026-06-01T09:30:00",
                    }
                },
                target="002008",
                now="2026-06-01T09:30:00",
            )
            path = snapshot.save_home_action_snapshot(payload, base_dir=tmp)
            loaded = snapshot.load_home_action_snapshot(base_dir=tmp)

        self.assertEqual(path.name, snapshot.SNAPSHOT_FILENAME)
        self.assertEqual(loaded["today_action"]["overall_action"], "只观察")
        self.assertFalse(loaded["deepseek_called"])

    def test_snapshot_filters_secrets_and_prompts(self):
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "overall_action": "等待",
                    "api_key": "secret-value",
                    "deepseek_prompt": "raw prompt",
                    "nested": {"access_token": "token-value", "safe": "ok"},
                }
            }
        )
        dumped = json.dumps(payload, ensure_ascii=False)

        self.assertNotIn("secret-value", dumped)
        self.assertNotIn("raw prompt", dumped)
        self.assertNotIn("token-value", dumped)
        self.assertIn("ok", dumped)

    def test_missing_fields_are_safe(self):
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": object(),
                "strategy_execution_packet": object(),
                "radar_scan_results": object(),
            },
            position_profile=object(),
        )

        self.assertIsInstance(payload, dict)
        json.dumps(payload, ensure_ascii=False)

    def test_data_freshness_today_stale_missing_and_partial_failed(self):
        self.assertEqual(snapshot.classify_data_freshness("2026-06-01T09:30:00", today="2026-06-01"), "today")
        self.assertEqual(snapshot.classify_data_freshness("2026-05-31T09:30:00", today="2026-06-01"), "stale")
        self.assertEqual(snapshot.classify_data_freshness("", today="2026-06-01"), "missing")
        self.assertEqual(
            snapshot.build_data_freshness("2026-06-01T09:30:00", [{"message": "timeout"}], today="2026-06-01")["state"],
            "partial_failed",
        )

    def test_next_ticket_candidates_extract_top_three(self):
        state = {
            "radar_scan_results": {
                "generated_at": "2026-06-01T10:00:00",
                "rule_rows": [
                    {"candidate": {"ticker": "A", "name": "Alpha"}, "score": {"total_score": 81, "battle_state": "可准备"}},
                    {"candidate": {"ticker": "B", "name": "Beta"}, "score": {"total_score": 72, "battle_state": "等验证"}},
                    {"candidate": {"ticker": "C", "name": "Gamma"}, "score": {"total_score": 61, "battle_state": "只观察"}},
                    {"candidate": {"ticker": "D", "name": "Delta"}, "score": {"total_score": 50, "battle_state": "暂不纳入"}},
                ],
            }
        }

        items = snapshot.extract_next_ticket_candidates(state)

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["ticker"], "A")
        self.assertEqual(items[0]["action_state"], "可准备")

    def test_deepseek_defaults_to_not_called(self):
        payload = snapshot.build_home_action_snapshot({
            "command_center_decision_packet": {"overall_action": "等待"}
        })

        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["data_freshness"]["deepseek_called"])

    def test_snapshot_path_is_under_cache_dir(self):
        path = snapshot.get_home_snapshot_path("/tmp/stock-ming-test")

        self.assertEqual(path.parent.name, snapshot.CACHE_DIR_NAME)
        self.assertEqual(path.name, snapshot.SNAPSHOT_FILENAME)


if __name__ == "__main__":
    unittest.main()
