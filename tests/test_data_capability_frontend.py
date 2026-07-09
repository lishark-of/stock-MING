import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "desktop" / "src" / "routes" / "DataCapabilityConsole.tsx"


class DataCapabilityFrontendTests(unittest.TestCase):
    def setUp(self):
        self.page = PAGE.read_text(encoding="utf-8")

    def test_tushare_data_capability_quick_read_is_user_visible_and_read_only(self):
        card_start = self.page.index('title="Tushare 数据能力速读"')
        provider_start = self.page.index('title="Provider 状态"')
        card = self.page[card_start:provider_start]

        self.assertLess(card_start, provider_start)
        self.assertIn("dataCapabilityTushareSummary", self.page)
        self.assertIn("dataCapabilityTushareNextStep", self.page)
        self.assertIn("dataCapabilityTushareOrdinaryItems", self.page)
        self.assertIn("dataCapabilityTushareReadableRows", self.page)
        self.assertIn("普通用户先看：可用、受限、待补和下一步", card)
        self.assertIn('aria-label="data capability tushare ordinary summary"', card)
        self.assertIn("MetricGrid items={dataCapabilityTushareOrdinaryItems}", card)
        self.assertIn('aria-label="data capability tushare readable rows"', card)
        self.assertIn("DataLineageTable rows={dataCapabilityTushareReadableRows}", card)
        for label in (
            'label: "Tushare 数据"',
            'label: "可用接口"',
            'label: "受限接口"',
            'label: "待补/缓存"',
            'label: "用户下一步"',
            'label: "安全边界"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("GET cache 只读；不 ping Tushare、DeepSeek、GitHub，不创建 task、不交易", self.page)
        self.assertIn("不能当作无数据或低风险", self.page)
        self.assertIn("不会把权限不足、空窗口或缓存降级解释成无风险", card)
        self.assertNotIn("onClick=", card)
        self.assertNotIn("postTask(", card)
        self.assertNotIn("fetch(", card)
        self.assertNotIn("TaskStatusPanel", card)


if __name__ == "__main__":
    unittest.main()
