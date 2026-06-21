import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "desktop"


class LayoutOrdinaryNavigationTests(unittest.TestCase):
    def test_three_ordinary_entries_are_first_navigation_group(self):
        source = (ROOT / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")

        self.assertIn('title: "普通入口"', source)
        self.assertIn('{ key: "home", label: "今日作战台" }', source)
        self.assertIn('{ key: "factor", label: "股票量化推演" }', source)
        self.assertIn('{ key: "candidates", label: "下一票雷达" }', source)
        self.assertLess(source.index('title: "普通入口"'), source.index('title: "研究辅助"'))
        self.assertLess(source.index('{ key: "home", label: "今日作战台" }'), source.index('{ key: "factor", label: "股票量化推演" }'))
        self.assertLess(source.index('{ key: "factor", label: "股票量化推演" }'), source.index('{ key: "candidates", label: "下一票雷达" }'))
        self.assertLess(source.index('{ key: "candidates", label: "下一票雷达" }'), source.index('title: "研究辅助"'))

    def test_engineering_and_legacy_routes_are_not_in_primary_group(self):
        source = (ROOT / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")
        ordinary_group = source[
            source.index('title: "普通入口"') : source.index('title: "研究辅助"')
        ]

        for label in [
            "调用审计",
            "配置健康",
            "Task Monitor",
            "Worker",
            "Legacy",
            "迁移状态",
        ]:
            self.assertNotIn(label, ordinary_group)

        self.assertIn("三入口先行：今日作战台、股票量化推演、下一票雷达", source)
        self.assertIn("研究-only，不下单", source)
        self.assertIn("旧 Streamlit 仅作 legacy/admin/debug fallback", source)


if __name__ == "__main__":
    unittest.main()
