import json
import unittest
from pathlib import Path

import command_center_serenity_method_radar as radar


class CommandCenterSerenityMethodRadarTests(unittest.TestCase):
    def test_default_packet_contains_fixed_10_repo_baseline_without_network_or_deepseek(self):
        packet = radar.build_serenity_method_radar_packet(now="2026-06-08T22:00:00")

        self.assertEqual(packet["packet_key"], "command_center_serenity_method_radar_packet")
        self.assertEqual(len(packet["repositories"]), 10)
        self.assertEqual(packet["github_probe"], {})
        self.assertFalse(packet["deepseek_called"])
        self.assertEqual(packet["source_type"], "user_screenshot_baseline")
        self.assertEqual(packet["updated_at"], "2026-06-08T22:00:00")
        for item in packet["repositories"]:
            self.assertEqual(item["source_type"], "user_screenshot_baseline")
            self.assertEqual(item["github_probe"], {})
        json.dumps(packet, ensure_ascii=False)

    def test_default_repo_names_are_exact_user_screenshot_baseline(self):
        packet = radar.build_serenity_method_radar_packet()
        repos = [item["repo"] for item in packet["repositories"]]

        self.assertEqual(
            repos,
            [
                "muxuuu/serenity-skill",
                "lanfuli/aleabito-serenity-skills",
                "haskaomni/serenity",
                "W-Y-P/Serenity-aleabitoreddit-skill",
                "ZadAnthony/serenity-skill",
                "fadewalk/serenity-stock-choke",
                "leslieyeo/serenity-reply",
                "zongmin-yu/serenity-skills",
                "yan-labs/serenity-aleabitoreddit",
                "xvhaoran778-cyber/Serenity.SKILL",
            ],
        )

    def test_decision_usage_policy_blocks_trading_and_prompt_paths(self):
        packet = radar.build_serenity_method_radar_packet()
        policy = packet["decision_usage_policy"]

        self.assertTrue(policy["display_only"])
        self.assertFalse(policy["enters_chokepoint_score"])
        self.assertFalse(policy["enters_strategy_action"])
        self.assertFalse(policy["enters_next_session_projection"])
        self.assertFalse(policy["enters_deepseek_prompt"])
        self.assertIn("不作为交易信号", policy["note"])

    def test_method_baselines_include_generation_and_summary_source_types(self):
        packet = radar.build_serenity_method_radar_packet()

        self.assertEqual(len(packet["hallucination_defense_evolution"]), 4)
        self.assertEqual(
            [item["generation"] for item in packet["hallucination_defense_evolution"]],
            ["Gen 1", "Gen 2", "Gen 3", "Gen 4"],
        )
        for item in packet["hallucination_defense_evolution"]:
            self.assertEqual(item["source_type"], "user_screenshot_baseline")
        summary_keys = {item["key"] for item in packet["method_summaries"]}
        self.assertEqual(
            summary_keys,
            {
                "chinese_implementation_breakthrough",
                "data_driven_limitations",
                "cross_market_bayesian_framework",
            },
        )
        for item in packet["method_summaries"]:
            self.assertEqual(item["source_type"], "user_screenshot_baseline")

    def test_github_probe_only_updates_allowed_probe_fields_without_overriding_baseline(self):
        packet = radar.build_serenity_method_radar_packet(
            github_probe={
                "muxuuu/serenity-skill": {
                    "http_status": 200,
                    "probe_status": "success",
                    "github_stars": 999,
                    "github_forks": 12,
                    "pushed_at": "2026-06-08T00:00:00Z",
                    "html_url": "https://github.com/muxuuu/serenity-skill",
                    "error_message_safe": "",
                    "screenshot_feature": "should not override",
                    "source_type": "github",
                    "extra": "blocked",
                }
            }
        )
        first = packet["repositories"][0]

        self.assertEqual(first["screenshot_feature"], "核心方法论 + 最系统化")
        self.assertEqual(first["source_type"], "user_screenshot_baseline")
        self.assertEqual(first["github_probe"]["github_stars"], 999)
        self.assertNotIn("screenshot_feature", first["github_probe"])
        self.assertNotIn("source_type", first["github_probe"])
        self.assertNotIn("extra", first["github_probe"])
        self.assertEqual(packet["hallucination_defense_evolution"][0]["source_type"], "user_screenshot_baseline")

    def test_build_packet_does_not_trigger_probe_but_explicit_probe_does(self):
        calls = []
        original = radar._github_probe_for_repo

        def fake_probe(repo, timeout_seconds=8):
            calls.append((repo, timeout_seconds))
            return {"http_status": 403, "probe_status": "http_error", "error_message_safe": "mock 403"}

        try:
            radar._github_probe_for_repo = fake_probe
            packet = radar.build_serenity_method_radar_packet()
            self.assertEqual(calls, [])

            result = radar.probe_github_repositories(["muxuuu/serenity-skill"], timeout_seconds=3)
            self.assertEqual(calls, [("muxuuu/serenity-skill", 3)])
            self.assertEqual(result["muxuuu/serenity-skill"]["http_status"], 403)
        finally:
            radar._github_probe_for_repo = original

    def test_invalid_repo_slug_is_rejected_before_curl(self):
        result = radar._github_probe_for_repo("bad repo/with space", timeout_seconds=1)

        self.assertIsNone(result["http_status"])
        self.assertEqual(result["probe_status"], "invalid_repo")

    def test_serenity_radar_does_not_enter_scoring_strategy_projection_or_deepseek_modules(self):
        blocked_files = [
            "command_center_analysis_methods.py",
            "command_center_next_session_projection.py",
            "command_center_strategy_summary.py",
            "analysis_engine.py",
        ]
        for filename in blocked_files:
            with self.subTest(filename=filename):
                source = Path(filename).read_text(encoding="utf-8")
                self.assertNotIn("command_center_serenity_method_radar_packet", source)
                self.assertNotIn("serenity_method_radar", source)

        app_source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("_render_serenity_method_radar_panel", app_source)
        self.assertIn("serenity_method_radar_service.build_serenity_method_radar_packet", app_source)
        self.assertIn('st.expander("截图本地基线仓库", expanded=False)', app_source)
        self.assertIn('metric("DeepSeek", "不调用")', app_source)
        self.assertIn('metric("决策使用", "只读说明")', app_source)
        self.assertNotIn("serenity_method_radar_service.build_serenity_method_radar_packet(", app_source.split("def _build_chokepoint_evidence_payload", 1)[1].split("def _render_serenity_method_radar_panel", 1)[0])


if __name__ == "__main__":
    unittest.main()
