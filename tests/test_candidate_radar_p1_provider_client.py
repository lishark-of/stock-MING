import unittest
from pathlib import Path


class CandidateRadarP1ProviderClientTests(unittest.TestCase):
    def test_quant_projection_provider_acceptance_route_is_frontend_callable_only_via_post_task(self):
        root = Path(__file__).resolve().parents[1]
        client = (root / "desktop" / "src" / "api" / "client.ts").read_text(
            encoding="utf-8"
        )
        task_catalog = (root / "server" / "services" / "task_service.py").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "postCandidateRadarQuantProjectionProviderModelAcceptance",
            client,
        )
        self.assertIn(
            '"/api/candidate-radar/quant-projection-provider-model-acceptance"',
            client,
        )
        self.assertIn("method: \"POST\"", client)
        self.assertIn("body: JSON.stringify(payload)", client)
        self.assertIn(
            '"task_type": "run_candidate_radar_quant_projection_provider_model_acceptance"',
            task_catalog,
        )
        self.assertIn(
            '"external_call_policy": "button_gated_tushare_light_provider_task_deepseek_skipped"',
            task_catalog,
        )
        self.assertIn('"possible_external_sources": ["tushare"]', task_catalog)
        self.assertIn('"future_external_sources": ["deepseek"]', task_catalog)
        self.assertIn('"tushare_called_only_from_post_task": True', task_catalog)
        self.assertIn('"deepseek_called": False', task_catalog)
        self.assertIn('"cache_get_external_calls": False', task_catalog)
        self.assertIn('"page_render_external_calls": False', task_catalog)
        self.assertIn('"does_not_execute_trades": True', task_catalog)
        self.assertNotIn("TUSHARE_TOKEN", client)
        self.assertNotIn("DEEPSEEK_API_KEY", client)
        self.assertNotIn("GITHUB_TOKEN", client)


if __name__ == "__main__":
    unittest.main()
