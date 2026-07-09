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
        self.assertIn("dataCapabilityTushareResultCardSentence", self.page)
        self.assertIn("dataCapabilityTushareResultCardItems", self.page)
        self.assertIn("dataCapabilityTushareDegradedResultRows", self.page)
        self.assertIn("dataCapabilityTushareReadableRows", self.page)
        self.assertIn("dataCapabilityTushareResultHandoffRows", self.page)
        self.assertIn("普通用户先看：可用、受限、待补和下一步", card)
        self.assertIn('aria-label="data capability tushare ordinary summary"', card)
        self.assertIn("MetricGrid items={dataCapabilityTushareOrdinaryItems}", card)
        self.assertIn('aria-label="data capability tushare degraded result card"', card)
        self.assertIn("确认后数据卡怎么读", card)
        self.assertIn('aria-label="data capability tushare degraded result sentence"', card)
        self.assertIn("MetricGrid items={dataCapabilityTushareResultCardItems}", card)
        self.assertIn('aria-label="data capability tushare degraded result rows"', card)
        self.assertIn("<summary>查看 degraded 读法</summary>", card)
        self.assertIn("DataLineageTable rows={dataCapabilityTushareDegradedResultRows}", card)
        self.assertIn('aria-label="data capability tushare readable rows"', card)
        self.assertIn("DataLineageTable rows={dataCapabilityTushareReadableRows}", card)
        self.assertIn('aria-label="data capability tushare result handoff actions"', card)
        self.assertIn('aria-label="data capability tushare result handoff rows"', card)
        self.assertIn("<summary>这些数据去哪看结果</summary>", card)
        self.assertIn("DataLineageTable rows={dataCapabilityTushareResultHandoffRows}", card)
        self.assertIn('href="#home"', card)
        self.assertIn('href="#candidates/candidate-radar-search-quant-projection"', card)
        self.assertIn('href="#factor"', card)
        self.assertIn('href="#next"', card)
        self.assertIn('结果入口: "今日作战台"', self.page)
        self.assertIn('结果入口: "下一票雷达"', self.page)
        self.assertIn('结果入口: "股票量化推演"', self.page)
        self.assertIn('结果入口: "次日图谱"', self.page)
        self.assertIn("这张小表只把 Tushare 能力状态回流到普通投研入口", card)
        for label in (
            'label: "Tushare 数据"',
            'label: "可用接口"',
            'label: "受限接口"',
            'label: "待补/缓存"',
            'label: "用户下一步"',
            'label: "安全边界"',
            'label: "结果读法"',
            'label: "来源层"',
            'label: "确认后看"',
            'label: "degraded 含义"',
            'label: "不会发生"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("权限不足、空窗口、缓存陈旧或待补证据；不是低风险结论", self.page)
        self.assertIn("degraded / pending 不是安全信号", self.page)
        self.assertIn("需要真实补证必须另行授权按钮门控 provider run", self.page)
        self.assertIn("不生成买入、卖出、加仓、融资或交易动作", self.page)
        self.assertLess(
            card.index('aria-label="data capability tushare degraded result card"'),
            card.index('aria-label="data capability tushare readable rows"'),
        )
        self.assertIn("GET cache 只读；不 ping Tushare、DeepSeek、GitHub，不创建 task、不交易", self.page)
        self.assertIn("不能当作无数据或低风险", self.page)
        self.assertIn("不会把权限不足、空窗口或缓存降级解释成无风险", card)
        self.assertNotIn("onClick=", card)
        self.assertNotIn("postTask(", card)
        self.assertNotIn("fetch(", card)
        self.assertNotIn("TaskStatusPanel", card)


if __name__ == "__main__":
    unittest.main()
