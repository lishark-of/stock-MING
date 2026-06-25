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
        self.assertIn("taskCatalogLatestIsCandidateReplay", source)
        self.assertIn('label: "当前任务"', source)
        self.assertIn('label: "任务状态"', source)
        self.assertIn('label: "P2 写回"', source)
        self.assertIn('label: "Tushare-first"', source)
        self.assertIn('label: "P3 结果入口"', source)
        self.assertIn('label: "安全边界"', source)
        self.assertIn("Task Monitor 只读 GET /api/tasks；不创建 task、不补调 Tushare/DeepSeek、不交易", source)
        self.assertIn('aria-label="task monitor ordinary progress actions"', source)
        self.assertIn('aria-label="refresh task monitor ordinary progress"', source)
        self.assertIn('aria-label="open candidate radar from task monitor ordinary progress"', source)
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
