import unittest
from pathlib import Path

import config


class TushareDeepSeekLinkageContractProfileTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.script = (root / "scripts" / "tushare_deepseek_linkage_contract.py").read_text(
            encoding="utf-8"
        )

    def test_linkage_contract_pins_live_light_external_execution_profile(self):
        self.assertIn(
            '"COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE"',
            self.script,
        )
        self.assertIn(
            'COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE="light_provider_model"',
            self.script,
        )
        self.assertIn(
            "COMMAND_CENTER_LIVE_EXTERNAL_EXECUTION_PROFILE",
            config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES,
        )
        self.assertIn(
            "light_provider_model",
            config.COMMAND_CENTER_EXTERNAL_EXECUTION_PROFILES,
        )
        self.assertEqual(config.COMMAND_CENTER_DEFAULT_EXTERNAL_EXECUTION_PROFILE, "plan_only")

    def test_linkage_contract_stays_local_and_not_execution_evidence(self):
        required_fragments = (
            "local_tushare_deepseek_linkage_contract_no_provider_or_model_execution",
            "live_light_plans_tushare_deepseek_without_calling",
            "provider_execution_implemented",
            "model_execution_implemented",
            "production_live_light_complete",
            "production_quant_projection_complete",
            "external_calls_triggered",
            "does_not_execute_trades",
            "does_not_modify_strategy_action",
        )
        for fragment in required_fragments:
            self.assertIn(fragment, self.script)

        forbidden_fragments = (
            "tushare_adapter",
            "deepseek_adapter",
            "api.github.com",
            "requests.get",
            "httpx.",
            "curl ",
            "execute_trade(",
            "place_order(",
            "broker.submit",
        )
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, self.script)


if __name__ == "__main__":
    unittest.main()
