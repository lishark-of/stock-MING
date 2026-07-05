import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "desktop" / "src" / "routes" / "DesktopShellPreflight.tsx"


class DesktopAppVisibleNowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.page = PAGE.read_text(encoding="utf-8")

    def test_visible_now_summary_precedes_runtime_and_package_review(self) -> None:
        card_start = self.page.index('<PacketCard title="P0 一键启动联通摘要"')
        readiness_start = self.page.index('aria-label="p0 ordinary one click readiness"', card_start)
        visible_start = self.page.index('aria-label="desktop app visible now summary"', card_start)
        runtime_start = self.page.index('aria-label="p0 current runtime readback"', card_start)
        package_review_start = self.page.index('aria-label="desktop package evidence factory task strip"', card_start)

        self.assertLess(readiness_start, visible_start)
        self.assertLess(visible_start, runtime_start)
        self.assertLess(visible_start, package_review_start)

        visible_slice = self.page[visible_start:runtime_start]
        self.assertIn("打开 app 能看到什么", visible_slice)
        self.assertIn('aria-label="desktop app visible now sentence"', visible_slice)
        self.assertIn("desktopAppVisibleNowItems", visible_slice)
        self.assertIn('aria-label="desktop app visible now local actions"', visible_slice)
        self.assertIn("首页确认股票", visible_slice)
        self.assertIn("下一票雷达", visible_slice)
        self.assertIn("任务进度", visible_slice)
        self.assertIn("系统健康", visible_slice)

    def test_visible_now_summary_is_local_read_only_navigation(self) -> None:
        visible_start = self.page.index('aria-label="desktop app visible now summary"')
        runtime_start = self.page.index('aria-label="p0 current runtime readback"', visible_start)
        visible_slice = self.page[visible_start:runtime_start]

        self.assertNotIn("<button", visible_slice)
        self.assertNotIn("postTask", visible_slice)
        self.assertNotIn("launchDesktopPackageReview", visible_slice)
        self.assertIn("不启动 FastAPI/Vite", visible_slice)
        self.assertIn("不运行 npm/cargo/Tauri", visible_slice)
        self.assertIn("不创建 task", visible_slice)
        self.assertIn("不读取配置值", visible_slice)
        self.assertIn("不写日志", visible_slice)
        self.assertIn("不调用外部数据或模型", visible_slice)
        self.assertIn("不执行真实交易", visible_slice)


if __name__ == "__main__":
    unittest.main()
