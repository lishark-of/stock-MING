import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "desktop"


class SettingsConfigHealthRuntimeModeTests(unittest.TestCase):
    def test_runtime_mode_policy_rows_are_displayed_read_only(self):
        source = (ROOT / "src" / "routes" / "SettingsConfigHealth.tsx").read_text(encoding="utf-8")

        self.assertIn("runtimeModePolicyRows", source)
        self.assertIn("runtimeModeBoundaryRows", source)
        self.assertIn("bootstrapStatus.runtime_mode_policy_rows", source)
        self.assertIn("运行模式安全口径", source)
        self.assertIn("runtime_mode_policy_rows 只读转发；非 production evidence", source)
        self.assertIn("不写配置、不展示 token/key、不创建 task", source)
        self.assertIn("不能证明完整 live_light 已实现", source)
        self.assertIn("cache_get_rule", source)
        self.assertIn("react_render_rule", source)
        self.assertIn("ledger_rule", source)
        self.assertIn("ordinary_entrance_visibility_rule", source)
        self.assertIn("production_evidence_rule", source)
        self.assertNotIn("runtimeModePolicyRows.map((row) => ({ ...row }))", source)

    def test_provider_model_release_switch_is_visible_without_task_launcher(self):
        source = (ROOT / "src" / "routes" / "SettingsConfigHealth.tsx").read_text(encoding="utf-8")

        self.assertIn("runtimeOperatorSummary", source)
        self.assertIn("providerModelEnablementRows", source)
        self.assertIn("Provider/model release switch", source)
        self.assertIn("operator summary 只读投影；不创建 provider/model task", source)
        self.assertIn("provider_model_enablement_summary_visible", source)
        self.assertIn("provider_model_enablement_source_config", source)
        self.assertIn("provider_model_enablement_configured", source)
        self.assertIn("provider_model_enablement_effective", source)
        self.assertIn("provider_model_enablement_requires_live_light", source)
        self.assertIn("provider_model_enablement_requires_execution_request", source)
        self.assertIn("provider_model_enablement_requires_promotion", source)
        self.assertIn("provider_model_enablement_creates_task", source)
        self.assertIn("provider_model_enablement_creates_provider_model_task", source)
        self.assertIn("provider_model_enablement_calls_provider_model_now", source)
        self.assertIn("provider_model_enablement_frontend_writeback_allowed", source)
        self.assertIn("provider_model_enablement_summary_is_production_evidence", source)
        self.assertNotIn("postBootstrapProviderModelExecutionRequest", source)
        self.assertNotIn("/api/bootstrap/provider-model-execution-request", source)


if __name__ == "__main__":
    unittest.main()
