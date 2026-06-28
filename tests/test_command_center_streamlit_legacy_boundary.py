from pathlib import Path
import unittest


class CommandCenterStreamlitLegacyBoundaryTests(unittest.TestCase):
    def test_app_declares_streamlit_as_legacy_admin_debug(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('STREAMLIT_LEGACY_MODE_STATUS = "legacy/admin/debug"', source)
        self.assertIn('COMMAND_CENTER_3_OFFICIAL_ENTRY = "React/Vite/Tauri + FastAPI"', source)
        self.assertIn("STREAMLIT_LEGACY_EXIT_POLICY", source)
        self.assertIn('"streamlit_is_primary_entry": False', source)
        self.assertIn('"startup_task_creation": False', source)
        self.assertIn('"can_bypass_strategy_guardrails": False', source)
        self.assertIn("def render_streamlit_legacy_admin_notice", source)
        self.assertIn("当前 Streamlit 工作台已降级为 legacy/admin/debug", source)
        self.assertIn("普通主路径请使用", source)

    def test_legacy_notice_keeps_external_calls_button_gated_and_trading_disabled(self):
        source = Path("app.py").read_text(encoding="utf-8")
        notice_body = source.split("def render_streamlit_legacy_admin_notice", 1)[1].split(
            "# ==========================================",
            1,
        )[0]

        self.assertIn("外部刷新、DeepSeek、GitHub 校验仍需按钮门控", notice_body)
        self.assertIn("不会自动创建任务", notice_body)
        self.assertIn("不会自动执行真实交易", notice_body)
        self.assertIn("不会改写 strategy action", notice_body)
        self.assertNotIn("自动下单", notice_body)

    def test_optional_legacy_deep_link_stays_fallback_navigation_only(self):
        source = Path("app.py").read_text(encoding="utf-8")

        if "def apply_streamlit_legacy_deep_link" not in source:
            self.skipTest("legacy deep link helper is not present in this checkout")

        self.assertIn("LEGACY_WORKSPACE_DEEP_LINK_TABS", source)
        self.assertIn('"next_ticket": "下一票雷达"', source)
        self.assertIn('"radar": "下一票雷达"', source)
        self.assertIn('"data_health": "数据源体检"', source)

        helper_body = source.split("def apply_streamlit_legacy_deep_link", 1)[1].split(
            "# ==========================================",
            1,
        )[0]
        self.assertIn("st.query_params", helper_body)
        self.assertIn("workspace_mode_v2", helper_body)
        self.assertIn("高级工具箱（旧版保留）", helper_body)
        self.assertIn("legacy_workspace_selected_tab", helper_body)
        self.assertIn("_streamlit_legacy_deep_link_signature", helper_body)
        self.assertNotIn("st.rerun", helper_body)
        self.assertNotIn("create_task", helper_body)
        self.assertNotIn("run_task", helper_body)
        self.assertNotIn("open(", helper_body)
        self.assertNotIn("tushare", helper_body.lower())
        self.assertNotIn("deepseek", helper_body.lower())
        self.assertNotIn("trade", helper_body.lower())


if __name__ == "__main__":
    unittest.main()
