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
        self.assertIn("configured_switch_rule", source)
        self.assertIn("effective_external_call_rule", source)
        self.assertIn("configured=true 只是 operator intent", source)
        self.assertIn("effective external work 仍需 mode/task gate、ledger、redaction、promotion gate", source)
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

    def test_advanced_task_launchers_are_demoted_from_ordinary_cache_actions(self):
        source = (ROOT / "src" / "routes" / "SettingsConfigHealth.tsx").read_text(encoding="utf-8")

        self.assertIn('aria-label="settings config ordinary cache actions"', source)
        self.assertIn('aria-label="settings config advanced task launchers"', source)
        self.assertIn("<summary>高级配置任务</summary>", source)
        self.assertIn("普通用户先看配置健康缓存", source)
        self.assertIn("live_light skeleton 和 provider/model dry-run 只作为显式按钮门控任务", source)
        self.assertIn("不在页面打开或 React render 中自动运行", source)

        ordinary_actions_start = source.index('aria-label="settings config ordinary cache actions"')
        ordinary_actions_end = source.index("</div>", ordinary_actions_start)
        ordinary_actions_slice = source[ordinary_actions_start:ordinary_actions_end]
        advanced_start = source.index('aria-label="settings config advanced task launchers"')
        advanced_slice = source[advanced_start:source.index("<MetricGrid", advanced_start)]

        self.assertIn("查看配置健康缓存", ordinary_actions_slice)
        self.assertNotIn("启动 live_light 本地任务", ordinary_actions_slice)
        self.assertNotIn("生成 provider/model 验收 dry-run", ordinary_actions_slice)
        self.assertIn("启动 live_light 本地任务", advanced_slice)
        self.assertIn("生成 provider/model 验收 dry-run", advanced_slice)
        self.assertLess(source.index('aria-label="settings config ordinary cache actions"'), advanced_start)


if __name__ == "__main__":
    unittest.main()
