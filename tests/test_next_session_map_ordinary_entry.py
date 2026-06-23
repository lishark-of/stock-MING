import unittest
from pathlib import Path


class NextSessionMapOrdinaryEntryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.page = (self.root / "desktop" / "src" / "routes" / "NextSessionMap.tsx").read_text(
            encoding="utf-8"
        )

    def test_next_session_has_three_step_ordinary_result_replay_before_audit(self):
        summary_start = self.page.index('title="普通用户次日图谱摘要"')
        audit_start = self.page.index('<details className="developer-audit-details">')
        ordinary_slice = self.page[summary_start:audit_start]
        source_before_audit = self.page[:audit_start]

        self.assertLess(summary_start, audit_start)
        self.assertIn("ordinaryResultReplayStatus", source_before_audit)
        self.assertIn("ordinaryResultReplayRows", source_before_audit)
        self.assertIn("ordinaryChartReviewRows", source_before_audit)
        self.assertIn("nextSessionLastResultLabel", source_before_audit)
        self.assertIn("三段结果回放", ordinary_slice)
        self.assertIn("DataLineageTable rows={ordinaryResultReplayRows}", ordinary_slice)
        self.assertIn('aria-label="next session ordinary chart review checklist"', ordinary_slice)
        self.assertIn("图谱复核清单", ordinary_slice)
        self.assertIn("按图表路径、参考线、操作区、缺少证据复核", ordinary_slice)
        self.assertIn("DataLineageTable rows={ordinaryChartReviewRows}", ordinary_slice)
        self.assertIn("下一票雷达", source_before_audit)
        self.assertIn("股票量化推演", source_before_audit)
        self.assertIn("次日图谱", source_before_audit)
        self.assertIn('复核项: "图表路径"', source_before_audit)
        self.assertIn('复核项: "参考线"', source_before_audit)
        self.assertIn('复核项: "操作区"', source_before_audit)
        self.assertIn('复核项: "缺少证据"', source_before_audit)
        self.assertIn('label: "最近结果"', ordinary_slice)
        self.assertIn("最近结果：", source_before_audit)
        self.assertIn("只读取图表路径；不重算价格、不调用数据源或模型", source_before_audit)
        self.assertIn("参考线只作研究复核，不生成买卖动作", source_before_audit)
        self.assertIn("不改 operation_zones、不下单、不写 strategy action", source_before_audit)
        self.assertIn("缺口只提示后续补证，不把空结果解释成无风险", source_before_audit)
        self.assertIn("输入和页面打开不外联", source_before_audit)
        self.assertIn("只有确认按钮可创建 Tushare-first 后台 task", source_before_audit)
        self.assertIn("本页只读 cache，不补调 Tushare 或 DeepSeek", source_before_audit)
        self.assertIn("DeepSeek governed executor 单独补", source_before_audit)
        self.assertIn("operation_zones 只表示条件区间和复核提示", source_before_audit)
        self.assertIn('href="#candidates"', ordinary_slice)
        self.assertIn('href="#factor"', ordinary_slice)
        self.assertLess(ordinary_slice.index("三段结果回放"), ordinary_slice.index("图谱复核清单"))
        self.assertLess(ordinary_slice.index("图谱复核清单"), ordinary_slice.index('aria-label="next session replay handoff actions"'))

        self.assertNotIn('label: "QA runbook"', ordinary_slice)
        self.assertNotIn('label: "promotion review"', ordinary_slice)
        self.assertNotIn('label: "cache envelope ledger"', ordinary_slice)
        self.assertNotIn("browserQaEvidenceRows", ordinary_slice)
        self.assertNotIn("productionPromotionReviewRows", ordinary_slice)
        self.assertNotIn("GET cache envelope call_ledger", ordinary_slice)


if __name__ == "__main__":
    unittest.main()
