import builtins
import unittest
from unittest import mock

import desktop_app


class DesktopAppLauncherTests(unittest.TestCase):
    def test_desktop_url_uses_embed_mode_to_reduce_streamlit_chrome(self):
        url = desktop_app.build_desktop_app_url(8502)

        self.assertEqual(url, "http://127.0.0.1:8502/?desktop=1&embed=true")
        self.assertIn("embed=true", url)

    def test_streamlit_command_is_headless_and_toolbar_minimal(self):
        cmd = desktop_app._build_streamlit_cmd(8502)

        self.assertIn("--server.headless", cmd)
        self.assertIn("true", cmd)
        self.assertIn("--browser.gatherUsageStats", cmd)
        self.assertIn("false", cmd)
        self.assertIn("--client.toolbarMode", cmd)
        self.assertIn("minimal", cmd)

    def test_pywebview_missing_error_is_user_friendly(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "webview":
                raise ModuleNotFoundError("No module named webview")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(desktop_app.StartupError) as ctx:
                desktop_app._load_webview()

        suggestions = "\n".join(ctx.exception.suggestions)
        self.assertIn("桌面 App 壳依赖 pywebview", suggestions)
        self.assertIn("streamlit run app.py --server.port 8502", suggestions)


if __name__ == "__main__":
    unittest.main()
