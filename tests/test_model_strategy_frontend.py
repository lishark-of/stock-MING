import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "desktop" / "src" / "routes" / "ModelStrategy.tsx"


class ModelStrategyFrontendTests(unittest.TestCase):
    def setUp(self):
        self.page = PAGE.read_text(encoding="utf-8")

    def test_deepseek_app_visible_now_is_first_screen_read_only(self):
        summary_start = self.page.index('aria-label="deepseek ordinary top summary boundary"')
        visible_start = self.page.index('aria-label="deepseek app visible now summary"')
        technical_details_start = self.page.index('aria-label="deepseek model strategy top technical counters"')
        ordinary_card_start = self.page.index("普通用户 DeepSeek 状态")
        ticket_details_start = self.page.index('aria-label="deepseek governed executor ticket and gate details"')
        visible_slice = self.page[visible_start:technical_details_start]

        self.assertLess(summary_start, visible_start)
        self.assertLess(visible_start, technical_details_start)
        self.assertLess(visible_start, ordinary_card_start)
        self.assertLess(visible_start, ticket_details_start)
        self.assertIn("governedExecutorVisibleNowSentence", self.page)
        self.assertIn("governedExecutorVisibleNowItems", self.page)
        self.assertIn("打开 app 能看到什么", visible_slice)
        self.assertIn('aria-label="deepseek app visible now sentence"', visible_slice)
        self.assertIn("{governedExecutorVisibleNowSentence}", visible_slice)
        self.assertIn("MetricGrid items={governedExecutorVisibleNowItems}", visible_slice)
        self.assertIn('aria-label="deepseek app visible now local actions"', visible_slice)
        self.assertIn('href="#candidates"', visible_slice)
        self.assertIn('href="#factor"', visible_slice)
        self.assertIn('href="#next"', visible_slice)
        self.assertIn('label: "模型状态"', self.page)
        self.assertIn('label: "可先用"', self.page)
        self.assertIn('label: "真实调用"', self.page)
        self.assertIn('label: "下一步"', self.page)
        self.assertIn('label: "凭据"', self.page)
        self.assertIn('label: "边界"', self.page)
        self.assertIn("打开 app 能看到 DeepSeek 当前未调用", self.page)
        self.assertIn("Tushare-first、股票量化推演和次日图谱可以先走", self.page)
        self.assertIn("model_ledger / sanitizer / output acceptance", self.page)
        self.assertIn("普通链接只切换本地页面", visible_slice)
        self.assertIn("不创建 task、不调用 DeepSeek/Tushare/GitHub、不交易", visible_slice)
        self.assertIn("不改 operation_zones 或 strategy action", visible_slice)
        self.assertNotIn("onClick=", visible_slice)
        self.assertNotIn("postDeepseekProviderBenchmarkScopeTicket", visible_slice)
        self.assertNotIn("postDeepseekProviderBenchmarkExecutionRequest", visible_slice)
        self.assertNotIn("TaskLaunchReceipt", visible_slice)


if __name__ == "__main__":
    unittest.main()
