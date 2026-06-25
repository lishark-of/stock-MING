import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "desktop"


class TaskCatalogOrdinaryEntryTests(unittest.TestCase):
    def test_task_monitor_shows_ordinary_progress_before_engineering_catalog(self):
        source = (ROOT / "src" / "routes" / "TaskCatalog.tsx").read_text(encoding="utf-8")

        self.assertIn("普通任务进度速读", source)
        self.assertIn("确认按钮之后先看这里；工程目录和路由覆盖继续下沉", source)
        self.assertIn("taskCatalogLatestTask", source)
        self.assertIn("taskCatalogOrdinaryProgressItems", source)
        self.assertIn("taskCatalogLatestTushareRows", source)
        self.assertIn("taskCatalogLatestSourceTushareReplayed", source)
        self.assertIn("taskCatalogLatestReadbackExternal", source)
        self.assertIn("taskCatalogOrdinaryReadbackLabel", source)
        self.assertIn("taskCatalogLatestIsCandidateReplay", source)
        self.assertIn('label: "当前任务"', source)
        self.assertIn('label: "任务状态"', source)
        self.assertIn('label: "P2 写回"', source)
        self.assertIn('label: "Tushare-first"', source)
        self.assertIn('label: "读取方式"', source)
        self.assertIn('label: "P3 结果入口"', source)
        self.assertIn('label: "安全边界"', source)
        self.assertIn("Tushare-first ledger 已从 CandidateRadar cache 回放", source)
        self.assertIn("GET 只读回放源任务 Tushare ledger；本次刷新无新增外联", source)
        self.assertIn("Tushare-first 显示的是源任务 call_ledger 回放", source)
        self.assertIn("source_task_tushare_called", source)
        self.assertIn("source_task_provider_ledger_replayed", source)
        self.assertIn("readback_external_calls_triggered", source)
        self.assertIn("Task Monitor 只读 GET /api/tasks；不创建 task、不补调 Tushare/DeepSeek、不交易", source)
        self.assertIn('aria-label="task monitor ordinary progress actions"', source)
        self.assertIn('aria-label="refresh task monitor ordinary progress"', source)
        self.assertIn('const CANDIDATE_CONFIRM_HREF = "#candidates/candidate-radar-search-quant-projection";', source)
        self.assertIn("暂无任务；先回下一票雷达确认输入区输入代码并确认", source)
        self.assertIn('href={CANDIDATE_CONFIRM_HREF}', source)
        self.assertIn('aria-label="open candidate radar confirm input from task monitor ordinary progress"', source)
        self.assertIn('aria-label="open stock quant from task monitor ordinary progress"', source)
        self.assertIn('aria-label="open next session from task monitor ordinary progress"', source)
        self.assertIn("刷新按钮只调用本地 GET /api/tasks", source)
        self.assertIn("不会创建第二个 task、不调用 Tushare/DeepSeek/GitHub、不读取 token/key、不执行真实交易", source)
        self.assertLess(source.index("普通任务进度速读"), source.index('label: "任务数量"'))
        self.assertLess(source.index("普通任务进度速读"), source.index("Tushare 刷新任务"))
        self.assertLess(source.index("普通任务进度速读"), source.index("POST 路由覆盖"))

        card_start = source.index("普通任务进度速读")
        card_end = source.index('<MetricGrid\n        items={[', card_start)
        card = source[card_start:card_end]
        self.assertIn("MetricGrid items={taskCatalogOrdinaryProgressItems}", card)
        self.assertIn("onClick={refreshTasks}", card)
        self.assertNotIn("postTask(", card)
        self.assertNotIn("launchTushareRefresh", card)
        self.assertNotIn("cancelTask(", card)
        self.assertNotIn("retryTask(", card)


if __name__ == "__main__":
    unittest.main()
