from pathlib import Path
import unittest


class CommandCenterStreamlitLegacyBoundaryTests(unittest.TestCase):
    def test_app_declares_streamlit_as_legacy_admin_debug(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('STREAMLIT_LEGACY_MODE_STATUS = "legacy/admin/debug"', source)
        self.assertIn('COMMAND_CENTER_3_OFFICIAL_ENTRY = "React/Vite/Tauri + FastAPI"', source)
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
        self.assertIn("不会自动执行真实交易", notice_body)
        self.assertNotIn("自动下单", notice_body)


if __name__ == "__main__":
    unittest.main()
