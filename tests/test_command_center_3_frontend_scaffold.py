from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path("desktop")


class CommandCenter3FrontendScaffoldTests(unittest.TestCase):
    def test_desktop_scaffold_files_exist(self):
        expected = [
            ROOT / "package.json",
            ROOT / "vite.config.ts",
            ROOT / "src" / "App.tsx",
            ROOT / "src" / "api" / "client.ts",
            ROOT / "src" / "routes" / "FactorQuantHub.tsx",
            ROOT / "src-tauri" / "tauri.conf.json",
            ROOT / "src-tauri" / "src" / "main.rs",
        ]
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue(path.exists())

    def test_package_scripts_and_dependencies(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("dev", package["scripts"])
        self.assertIn("build", package["scripts"])
        self.assertIn("tauri", package["scripts"])
        self.assertIn("react", package["dependencies"])
        self.assertIn("echarts", package["dependencies"])

    def test_frontend_uses_api_client_and_button_gated_tasks(self):
        source = (ROOT / "src" / "routes" / "FactorQuantHub.tsx").read_text(encoding="utf-8")
        client = (ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")

        self.assertIn("/api/factor-quant/cache", client)
        self.assertIn("/api/factor-quant/refresh-data", source)
        self.assertIn("/api/factor-quant/run-light", source)
        self.assertIn("/api/factor-quant/deepseek-explain", source)
        self.assertIn("多因子量化不是交易建议", source)
        self.assertNotIn("tushare_adapter", source)
        self.assertNotIn("DEEPSEEK", source)
        self.assertNotIn("GITHUB_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
