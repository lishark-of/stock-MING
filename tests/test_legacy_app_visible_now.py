import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "desktop" / "src" / "routes" / "LegacyTools.tsx"


class LegacyAppVisibleNowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.page = PAGE.read_text(encoding="utf-8")

    def test_visible_now_summary_precedes_audit_and_review_buttons(self) -> None:
        card_start = self.page.index('<PacketCard title="Legacy / Admin / Debug"')
        visible_start = self.page.index('aria-label="legacy app visible now summary"', card_start)
        compass_start = self.page.index('aria-label="legacy ordinary replacement compass"', card_start)
        evidence_factory_start = self.page.index('aria-label="legacy streamlit evidence factory task strip"', card_start)

        self.assertLess(visible_start, compass_start)
        self.assertLess(visible_start, evidence_factory_start)
        visible_slice = self.page[visible_start:compass_start]
        self.assertIn("打开 app 能看到什么", visible_slice)
        self.assertIn('aria-label="legacy app visible now sentence"', visible_slice)
        self.assertIn("legacyAppVisibleNowItems", visible_slice)
        self.assertIn('aria-label="legacy app visible now local actions"', visible_slice)
        self.assertIn("首页确认股票", visible_slice)
        self.assertIn("下一票雷达", visible_slice)
        self.assertIn("量化推演", visible_slice)
        self.assertIn("次日图谱", visible_slice)
        self.assertIn("ETF / 融资", visible_slice)

    def test_visible_now_summary_keeps_cache_render_boundary(self) -> None:
        visible_start = self.page.index('aria-label="legacy app visible now summary"')
        compass_start = self.page.index('aria-label="legacy ordinary replacement compass"', visible_start)
        visible_slice = self.page[visible_start:compass_start]

        self.assertNotIn("<button", visible_slice)
        self.assertNotIn("postTask", visible_slice)
        self.assertIn("不打开 Streamlit", visible_slice)
        self.assertIn("不创建 task", visible_slice)
        self.assertIn("不调用 provider/model/GitHub", visible_slice)
        self.assertIn("不执行真实交易", visible_slice)
        self.assertIn("不删除 app.py", visible_slice)


if __name__ == "__main__":
    unittest.main()
