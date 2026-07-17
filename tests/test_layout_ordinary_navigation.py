import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "desktop"


class LayoutOrdinaryNavigationTests(unittest.TestCase):
    def test_six_ordinary_entries_follow_the_research_workflow(self):
        source = (ROOT / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")

        self.assertIn('title: "普通入口"', source)
        self.assertIn('{ key: "home", label: "今日作战台" }', source)
        self.assertIn('{ key: "factor", label: "股票量化推演" }', source)
        self.assertIn('{ key: "candidates", label: "下一票雷达" }', source)
        self.assertIn('{ key: "next", label: "次日图谱" }', source)
        self.assertIn('{ key: "marginEtf", label: "ETF / 融资" }', source)
        self.assertIn('{ key: "qmt-replay", label: "QMT 回放" }', source)
        self.assertLess(source.index('title: "普通入口"'), source.index('title: "研究辅助"'))
        self.assertLess(source.index('{ key: "home", label: "今日作战台" }'), source.index('{ key: "candidates", label: "下一票雷达" }'))
        self.assertLess(source.index('{ key: "candidates", label: "下一票雷达" }'), source.index('{ key: "factor", label: "股票量化推演" }'))
        self.assertLess(source.index('{ key: "factor", label: "股票量化推演" }'), source.index('{ key: "next", label: "次日图谱" }'))
        self.assertLess(source.index('{ key: "next", label: "次日图谱" }'), source.index('{ key: "marginEtf", label: "ETF / 融资" }'))
        self.assertLess(source.index('{ key: "marginEtf", label: "ETF / 融资" }'), source.index('{ key: "qmt-replay", label: "QMT 回放" }'))
        self.assertLess(source.index('{ key: "qmt-replay", label: "QMT 回放" }'), source.index('title: "研究辅助"'))
        self.assertEqual(source.count('{ key: "next", label: "次日图谱" }'), 1)

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

        self.assertIn("普通投研主线：今日作战台 → 下一票雷达 → 股票量化推演 → 次日图谱 → QMT 本地回放", source)
        self.assertIn("只做研究辅助，不下单", source)
        self.assertIn("QMT、券商、账户与订单路径保持隔离", source)
        self.assertIn("旧工作台仅作排查回退入口", source)

    def test_navigation_group_hints_keep_ordinary_flow_and_audit_details_separate(self):
        source = (ROOT / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")
        styles = (ROOT / "src" / "styles.css").read_text(encoding="utf-8")
        ordinary_group = source[
            source.index('title: "普通入口"') : source.index('title: "研究辅助"')
        ]
        governance_group = source[
            source.index('title: "数据与治理"') : source.index('title: "系统迁移"')
        ]
        system_group = source[source.index('title: "系统迁移"') :]

        self.assertIn("先从这里开始；每页先显示下一步、来源、缺口、边界和最近缓存。", ordinary_group)
        self.assertIn("补充上下文，只读查看研究状态，不替代普通投研主流程。", source)
        self.assertIn("数据来源、结果记录和排查表在这里，不压过普通用户页面。", governance_group)
        self.assertIn("配置、任务、迁移和旧工作台只作设置、排查或回退入口。", system_group)
        self.assertIn('className="nav-group-hint"', source)
        self.assertIn(".nav-group-hint", styles)

    def test_mobile_hash_targets_clear_the_sticky_navigation(self):
        styles = (ROOT / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn(".content [id]", styles)
        self.assertIn("scroll-margin-top: 237px", styles)

    def test_recent_research_progress_accepts_fraction_or_percent_contracts(self):
        source = (ROOT / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")

        self.assertIn("function normalizeResearchProgress(value: unknown): number", source)
        self.assertIn('value >= 0 && value <= 1 ? value * 100 : value', source)
        self.assertIn("normalizeResearchProgress(latestConfirmedTask.progress)", source)
        self.assertNotIn("Math.round(latestConfirmedTask.progress)", source)

    def test_workspace_boundary_describes_research_without_claiming_read_only(self):
        source = (ROOT / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")

        self.assertIn("研究模式 · 无下单路径", source)
        self.assertNotIn("只读研究 · 无下单路径", source)


if __name__ == "__main__":
    unittest.main()
