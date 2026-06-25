import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "desktop"


class TaskStatusPanelOrdinaryEntryTests(unittest.TestCase):
    def test_task_status_panel_surfaces_confirmed_symbol_without_new_external_work(self):
        source = (ROOT / "src" / "components" / "TaskStatusPanel.tsx").read_text(encoding="utf-8")

        self.assertIn("firstNonEmptyString", source)
        self.assertIn("taskPayloadSafe = task.payload_safe ?? {}", source)
        self.assertIn("taskPayloadSafe.symbol", source)
        self.assertIn("taskPayloadSafe.ts_code", source)
        self.assertIn("taskPayloadSafe.stock_code", source)
        self.assertIn("taskPayloadSafe.ticker", source)
        self.assertIn("taskConfirmedSymbolLabel", source)
        self.assertIn("当前标的：{taskConfirmedSymbolLabel}；确认任务：{taskConfirmTaskLabel}。", source)
        self.assertIn('label: "当前标的"', source)
        self.assertIn('label: "确认任务"', source)
        self.assertIn("candidateRadarResultReplay ? task.task_id : \"按当前任务查看\"", source)
        self.assertIn("任务速读：普通用户先看状态、写回、Tushare-first、结果入口和安全边界", source)
        self.assertIn("TaskStatusPanel 只轮询本地 FastAPI 任务状态；不会补调 provider/model。", source)

        ordinary_summary = source[
            source.index('aria-label="task status ordinary summary"') : source.index('aria-label="task status p3 result replay links"')
        ]
        self.assertIn("taskConfirmedSymbolLabel", ordinary_summary)
        self.assertIn("taskConfirmTaskLabel", ordinary_summary)
        self.assertIn("MetricGrid items={taskOrdinarySummaryItems}", ordinary_summary)
        self.assertNotIn("postTask(", ordinary_summary)
        self.assertNotIn("cancelTask(", ordinary_summary)
        self.assertNotIn("TUSHARE_TOKEN", ordinary_summary)
        self.assertNotIn("DEEPSEEK_API_KEY", ordinary_summary)


if __name__ == "__main__":
    unittest.main()
