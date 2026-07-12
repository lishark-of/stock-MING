from __future__ import annotations

import unittest
from pathlib import Path


APP_SOURCE = Path(__file__).resolve().parents[1] / "desktop/src/App.tsx"


class TauriDefaultHomeRouteTests(unittest.TestCase):
    def test_fresh_tauri_launch_ignores_stored_engineering_route(self):
        source = APP_SOURCE.read_text(encoding="utf-8")

        self.assertIn('window.location.protocol === "tauri:"', source)
        self.assertIn("const explicitRoute = routeFromHash();", source)
        self.assertIn("if (explicitRoute) return explicitRoute;", source)
        self.assertIn('if (isTauriRuntime()) return "home";', source)
        self.assertIn('return routeFromStorage() ?? "home";', source)
        self.assertLess(
            source.index("if (explicitRoute) return explicitRoute;"),
            source.index('if (isTauriRuntime()) return "home";'),
        )


if __name__ == "__main__":
    unittest.main()
