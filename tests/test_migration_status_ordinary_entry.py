import unittest
from pathlib import Path


class MigrationStatusOrdinaryEntryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.page = (self.root / "desktop" / "src" / "routes" / "MigrationStatus.tsx").read_text(
            encoding="utf-8"
        )

    def test_migration_status_first_screen_is_plain_summary_before_audit_tables(self):
        summary_start = self.page.index('title="迁移状态摘要"')
        audit_start = self.page.index('aria-label="migration status developer audit details"', summary_start)
        ordinary_slice = self.page[summary_start:audit_start]
        audit_slice = self.page[audit_start:]

        self.assertLess(summary_start, audit_start)
        self.assertIn("ordinaryMigrationText", self.page)
        self.assertIn('status={migrationLocalConnected ? "本地已接上" : undefined}', ordinary_slice)
        self.assertIn("普通用户只看当前进度、主攻方向、下一步和阻断原因", ordinary_slice)
        self.assertIn("现在迁移到哪、下一步去哪、为什么不能说长期目标全部完成", ordinary_slice)
        self.assertIn("MetricGrid items={migrationOrdinaryStatusItems}", ordinary_slice)
        for label in (
            'label: "当前状态"',
            'label: "长期目标"',
            'label: "当前主攻"',
            'label: "下一步"',
            'label: "阻断原因"',
            'label: "普通入口"',
            'label: "安全边界"',
        ):
            self.assertIn(label, self.page)
        self.assertIn("本地已接上，迁移摘要读取中", self.page)
        self.assertIn("0/14", self.page)
        self.assertIn("页面打开和刷新摘要只读本地结果", ordinary_slice)
        self.assertIn("不调用外部数据、模型、远端检查、后台执行或交易路径", ordinary_slice)
        self.assertIn('aria-label="migration ordinary summary actions"', ordinary_slice)
        self.assertIn("刷新本地摘要", ordinary_slice)
        self.assertIn('href="#home"', ordinary_slice)
        self.assertIn('href="#candidates/candidate-radar-search-quant-projection"', ordinary_slice)
        self.assertIn('href="#factor"', ordinary_slice)
        self.assertIn('href="#next"', ordinary_slice)
        self.assertNotIn("<DataLineageTable", ordinary_slice)
        self.assertNotIn("<JsonDetails", ordinary_slice)
        self.assertNotIn("TaskLaunchReceipt", ordinary_slice)
        self.assertNotIn("TaskStatusPanel", ordinary_slice)
        self.assertNotIn("task_id", ordinary_slice)
        self.assertNotIn("scope hash", ordinary_slice)
        self.assertNotIn("release gate", ordinary_slice)
        self.assertNotIn("strict closeout", ordinary_slice)
        self.assertNotIn("call_ledger", ordinary_slice)
        self.assertNotIn("packet", ordinary_slice)
        self.assertIn("研究辅助 / 工程迁移详情", audit_slice)
        self.assertIn("14 个长期目标完成度", audit_slice)
        self.assertIn("DataLineageTable", audit_slice)

    def test_migration_status_page_open_stays_read_only_and_local(self):
        self.assertIn("getHealth", self.page)
        self.assertIn("getMigrationStatus", self.page)
        self.assertIn("void getHealth().then", self.page)
        self.assertIn("void getMigrationStatus().then", self.page)
        self.assertNotIn("useEffect(() => {\n    void post", self.page)
        self.assertIn("页面打开和刷新摘要只读本地结果", self.page)
        self.assertIn("不调用外部数据、模型、远端检查、后台执行或交易路径", self.page)


if __name__ == "__main__":
    unittest.main()
