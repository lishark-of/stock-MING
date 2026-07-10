import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "desktop" / "src" / "routes" / "DataCapabilityConsole.tsx"


class DataCapabilityFrontendTests(unittest.TestCase):
    def setUp(self):
        self.page = PAGE.read_text(encoding="utf-8")

    def test_tushare_data_capability_quick_read_is_user_visible_and_read_only(self):
        card_start = self.page.index('title="Tushare 数据能力速读"')
        audit_start = self.page.index('aria-label="data capability provider audit details"', card_start)
        provider_start = self.page.index('title="Provider 状态"', audit_start)
        card = self.page[card_start:audit_start]
        audit = self.page[audit_start:]

        self.assertLess(card_start, audit_start)
        self.assertLess(audit_start, provider_start)
        self.assertIn("dataCapabilityTushareSummary", self.page)
        self.assertIn("dataCapabilityTushareNextStep", self.page)
        self.assertIn("dataCapabilityTushareOrdinaryItems", self.page)
        self.assertIn("dataCapabilityVisibleNowSentence", self.page)
        self.assertIn("dataCapabilityVisibleNowItems", self.page)
        self.assertIn("dataCapabilityTushareSourceLayerLabel", self.page)
        self.assertIn("dataCapabilityRuntimeModeLabel", self.page)
        self.assertIn("dataCapabilityEvidenceLedgerLabel", self.page)
        self.assertIn("dataCapabilityProviderEvidenceGap", self.page)
        self.assertIn("dataCapabilityTushareResultCardSentence", self.page)
        self.assertIn("dataCapabilityTushareResultCardItems", self.page)
        self.assertIn("dataCapabilityTushareDegradedResultRows", self.page)
        self.assertIn("dataCapabilityTushareReadableRows", self.page)
        self.assertIn("dataCapabilityTushareResultHandoffRows", self.page)
        self.assertIn("普通用户先看：可用、受限、待补和下一步", card)
        self.assertIn('aria-label="data capability tushare ordinary summary"', card)
        self.assertIn("MetricGrid items={dataCapabilityTushareOrdinaryItems}", card)
        self.assertIn('aria-label="data capability visible now summary"', card)
        self.assertIn("打开 app 能看到什么", card)
        self.assertIn('aria-label="data capability visible now sentence"', card)
        self.assertIn("MetricGrid items={dataCapabilityVisibleNowItems}", card)
        self.assertIn('aria-label="data capability visible now local actions"', card)
        self.assertIn('aria-label="data capability tushare degraded result card"', card)
        self.assertIn("确认后数据卡怎么读", card)
        self.assertIn('aria-label="data capability tushare degraded result sentence"', card)
        self.assertIn("MetricGrid items={dataCapabilityTushareResultCardItems}", card)
        self.assertIn('aria-label="data capability tushare degraded result rows"', card)
        self.assertIn("<summary>查看 degraded 读法</summary>", card)
        self.assertIn("DataLineageTable rows={dataCapabilityTushareDegradedResultRows}", card)
        self.assertIn('aria-label="data capability tushare readable rows"', card)
        self.assertIn("<summary>查看接口状态明细</summary>", card)
        self.assertIn("接口明细默认收起", card)
        self.assertIn("DataLineageTable rows={dataCapabilityTushareReadableRows}", card)
        self.assertIn('aria-label="data capability tushare result handoff actions"', card)
        self.assertIn('aria-label="data capability tushare result handoff rows"', card)
        self.assertIn("<summary>这些数据去哪看结果</summary>", card)
        self.assertIn("DataLineageTable rows={dataCapabilityTushareResultHandoffRows}", card)
        self.assertIn('href="#home"', card)
        self.assertIn('href="#candidates/candidate-radar-search-quant-projection"', card)
        self.assertIn('href="#factor"', card)
        self.assertIn('href="#next"', card)
        self.assertIn('aria-label="open home from data capability visible now"', card)
        self.assertIn('aria-label="open candidate radar from data capability visible now"', card)
        self.assertIn("这个条带只回答普通用户打开数据能力页能看到什么", card)
        self.assertIn("普通链接只切换本地页面，不刷新外部数据、不创建确认流程、不交易、不改策略", card)
        self.assertIn('结果入口: "今日作战台"', self.page)
        self.assertIn('结果入口: "下一票雷达"', self.page)
        self.assertIn('结果入口: "股票量化推演"', self.page)
        self.assertIn('结果入口: "次日图谱"', self.page)
        self.assertIn("这张小表只把 Tushare 能力状态回流到普通投研入口", card)
        self.assertIn("数据能力 / 审计详情", audit)
        self.assertIn("Provider 状态", audit)
        self.assertIn("cache envelope ledger", audit)
        self.assertIn("原始 data capability cache payload", audit)
        for label in (
            'label: "Tushare 数据"',
            'label: "可用接口"',
            'label: "受限接口"',
            'label: "待补/缓存"',
            'label: "用户下一步"',
            'label: "安全边界"',
            'label: "打开可见"',
            'label: "运行模式"',
            'label: "数据卡读法"',
            'label: "下一步入口"',
            'label: "证据血缘"',
            'label: "补证缺口"',
            'label: "安全说明"',
            'label: "结果读法"',
            'label: "来源层"',
            'label: "确认后看"',
            'label: "degraded 含义"',
            'label: "不会发生"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("权限不足、空窗口、缓存陈旧或待补证据；不是低风险结论", self.page)
        self.assertIn("degraded / pending 不是安全信号", self.page)
        self.assertIn("需要真实补证必须另行授权按钮门控数据任务", self.page)
        self.assertIn("不生成买入、卖出、加仓、融资或交易动作", self.page)
        self.assertLess(
            card.index('aria-label="data capability visible now summary"'),
            card.index('aria-label="data capability tushare degraded result card"'),
        )
        self.assertLess(
            card.index('aria-label="data capability tushare degraded result card"'),
            card.index('aria-label="data capability tushare readable rows"'),
        )
        self.assertIn("页面打开只读本地记录；不探测 Tushare、DeepSeek、GitHub，不创建确认流程、不交易", self.page)
        self.assertIn("cache_only（只读缓存，不外联）", self.page)
        self.assertIn("本地 call_ledger", self.page)
        self.assertIn("真实补证仍需授权 POST task + scope hash + payload + call_ledger + failure-mode", self.page)
        self.assertIn("本地数据健康记录", self.page)
        self.assertIn("本地数据能力摘要", self.page)
        self.assertIn("不能当作无数据或低风险", self.page)
        self.assertIn("不会把权限不足、空窗口或缓存降级解释成无风险", card)
        self.assertNotIn('title="Provider 状态"', card)
        self.assertNotIn("cache envelope ledger", card)
        self.assertNotIn("原始 data capability cache payload", card)
        self.assertNotIn("onClick=", card)
        self.assertNotIn("postTask(", card)
        self.assertNotIn("fetch(", card)
        self.assertNotIn("TaskStatusPanel", card)


if __name__ == "__main__":
    unittest.main()
