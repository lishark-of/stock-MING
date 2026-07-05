import unittest
from pathlib import Path


class StorageWorkerOrdinaryEntryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.storage_page = (
            self.root / "desktop" / "src" / "routes" / "StorageOverview.tsx"
        ).read_text(encoding="utf-8")
        self.worker_page = (
            self.root / "desktop" / "src" / "routes" / "WorkerRuntime.tsx"
        ).read_text(encoding="utf-8")

    def test_storage_first_screen_is_readable_before_audit_tables(self):
        page = self.storage_page
        head_start = page.index("<h1>存储层</h1>")
        first_screen_start = page.index('aria-label="storage ordinary first screen status"')
        metrics_start = page.index('<MetricGrid\n        items={[', first_screen_start)
        blocker_start = page.index('title="Storage production blocker audit"')
        first_screen = page[first_screen_start:metrics_start]

        self.assertLess(head_start, first_screen_start)
        self.assertLess(first_screen_start, blocker_start)
        self.assertIn("storageOrdinaryFirstScreenSentence", page[:blocker_start])
        self.assertIn("storageOrdinaryFirstScreenItems", page[:blocker_start])
        self.assertIn("本地数据底座一眼状态", first_screen)
        self.assertIn('aria-label="storage ordinary first screen sentence"', first_screen)
        self.assertIn("MetricGrid items={storageOrdinaryFirstScreenItems}", first_screen)
        self.assertIn('aria-label="storage ordinary first screen safe actions"', first_screen)
        self.assertIn("onClick={refreshStorage}", first_screen)
        self.assertIn('href="#worker"', first_screen)
        self.assertIn('href="#migration"', first_screen)
        self.assertIn('aria-label="storage ordinary physical evidence task strip"', first_screen)
        self.assertIn("物理证据按钮", first_screen)
        self.assertIn('aria-label="storage ordinary physical evidence sentence"', first_screen)
        self.assertIn("storagePhysicalEvidenceActionItems", page[:blocker_start])
        self.assertIn("用户现在可以从首屏生成 physical execution request", first_screen)
        self.assertIn("两个按钮都只写本地 task/packet 状态", first_screen)
        self.assertIn('aria-label="storage ordinary physical evidence actions"', first_screen)
        self.assertIn("onClick={launchPhysicalExecutionRequest}", first_screen)
        self.assertIn("onClick={launchPhysicalExecutionPhaseA}", first_screen)
        self.assertIn("disabled={!storagePhysicalExecutionRequestCanLaunch}", first_screen)
        self.assertIn("disabled={!storagePhysicalExecutionPhaseACanLaunch}", first_screen)
        self.assertIn("TaskLaunchReceipt receipt={physicalExecutionRequestReceipt}", first_screen)
        self.assertIn("TaskStatusPanel taskId={physicalExecutionRequestTaskId}", first_screen)
        self.assertIn("TaskLaunchReceipt receipt={physicalExecutionPhaseAReceipt}", first_screen)
        self.assertIn("TaskStatusPanel taskId={physicalExecutionPhaseATaskId}", first_screen)
        self.assertIn('href="#storage-physical-execution-details"', first_screen)
        self.assertIn("GET storage 只读", page[:blocker_start])
        self.assertIn("不写 Parquet/manifest、不删除 artifacts、不调用 provider/model、不交易", page[:blocker_start])
        self.assertIn("刷新只读取本地 GET cache", first_screen)
        self.assertIn("不创建 task、不写文件、不调用 Tushare/DeepSeek/GitHub、不下单", first_screen)
        self.assertIn("首屏按钮是显式 POST local task", first_screen)
        self.assertIn("Phase A 仍不是 production storage complete", first_screen)
        self.assertIn('id="storage-physical-execution-details"', page)
        self.assertNotIn("postStorage", first_screen)

    def test_worker_first_screen_is_readable_before_audit_tables(self):
        page = self.worker_page
        head_start = page.index("<h1>Worker 运行时</h1>")
        first_screen_start = page.index('aria-label="worker ordinary first screen status"')
        metrics_start = page.index('<MetricGrid\n        items={[', first_screen_start)
        audit_start = page.index('title="Worker runtime 来源"')
        first_screen = page[first_screen_start:metrics_start]

        self.assertLess(head_start, first_screen_start)
        self.assertLess(first_screen_start, audit_start)
        self.assertIn("workerOrdinaryFirstScreenSentence", page[:audit_start])
        self.assertIn("workerOrdinaryFirstScreenItems", page[:audit_start])
        self.assertIn("运行时一眼状态", first_screen)
        self.assertIn('aria-label="worker ordinary first screen sentence"', first_screen)
        self.assertIn("MetricGrid items={workerOrdinaryFirstScreenItems}", first_screen)
        self.assertIn('aria-label="worker ordinary first screen safe actions"', first_screen)
        self.assertIn("onClick={refreshCache}", first_screen)
        self.assertIn('href="#storage"', first_screen)
        self.assertIn('href="#tasks"', first_screen)
        self.assertIn("GET worker 只读", page[:audit_start])
        self.assertIn("不启动 Celery/Redis/APScheduler、不派发任务、不调用 provider/model、不交易", page[:audit_start])
        self.assertIn("刷新只读取本地 GET cache", first_screen)
        self.assertIn("不创建 task、不调用 Tushare/DeepSeek/GitHub、不下单", first_screen)
        self.assertNotIn("launchRuntimeQaExecution", first_screen)
        self.assertNotIn("launchRuntimeQaDryRun", first_screen)
        self.assertNotIn("runWorker", first_screen)


if __name__ == "__main__":
    unittest.main()
