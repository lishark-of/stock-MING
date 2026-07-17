import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "desktop" / "src" / "components"


class SharedUiNoiseReductionTests(unittest.TestCase):
    def test_metric_grid_uses_nonverbal_tone_cues(self):
        source = (COMPONENTS / "MetricGrid.tsx").read_text(encoding="utf-8")

        self.assertIn("toneLabel", source)
        self.assertIn("toneIcon", source)
        self.assertIn('className="metric-card__tone"', source)
        self.assertIn('aria-hidden="true"', source)
        self.assertIn("data-metric-tone={item.tone ?? \"neutral\"}", source)
        self.assertNotIn("<StatusBadge label={item.tone}", source)

    def test_task_panel_keeps_engineering_fields_behind_closed_details(self):
        source = (COMPONENTS / "TaskStatusPanel.tsx").read_text(encoding="utf-8")
        start = source.index("<div className={`task-panel task-panel--${task.status}")
        details = source.index('<details className="task-panel__technical-details"', start)
        visible = source[start:details]
        technical = source[details:]

        self.assertIn("task-panel__plain-result", visible)
        self.assertIn("task-panel__plain-boundary", visible)
        self.assertIn("task-panel__secondary-action--danger", visible)
        self.assertNotIn("任务编号：{task.task_id}", visible)
        self.assertNotIn("任务类型：{task.task_type}", visible)
        self.assertNotIn("call_ledger", visible)
        self.assertNotIn("P2 写回速读", visible)
        self.assertNotIn("P3 结果入口速读", visible)
        self.assertIn("<summary>技术详情</summary>", technical)
        self.assertIn("任务编号：{task.task_id}", technical)
        self.assertIn("任务类型：{task.task_type}", technical)
        self.assertIn('aria-label="task status p2 writeback quick read"', technical)
        self.assertIn('aria-label="task status p3 result replay quick read"', technical)

    def test_task_panel_status_and_safety_are_fail_closed(self):
        source = (COMPONENTS / "TaskStatusPanel.tsx").read_text(encoding="utf-8")

        summary = source[source.index("const taskResultSummary") : source.index("const primaryResultLink")]
        self.assertLess(summary.index('task.status === "failed"'), summary.index('task.status === "running"'))
        self.assertIn('task.status === "cancelled"', summary)
        self.assertNotIn("error_message_safe", summary)
        self.assertIn('task.status === "failed" && task.error_message_safe', source)
        self.assertIn('(task.status === "failed" || !task.error_message_safe)', source)
        self.assertIn("task.does_not_execute_trades === true", source)
        self.assertIn("task.does_not_modify_strategy_action === true", source)
        self.assertIn("边界待确认：旧任务未提供完整交易隔离标记", source)
        self.assertIn("ledgerExternalObserved", source)
        self.assertIn("externalCallsObserved", source)
        self.assertIn("taskBoundaryTechnicalRows", source)
        self.assertIn('summary="边界标记与外联聚合"', source)
        self.assertIn("row.external_calls_triggered === true", source)
        self.assertIn("row.external === true", source)
        self.assertIn("row.provider ?? row.provider_name ?? row.source", source)
        self.assertIn("trade_cal|daily|daily_basic|moneyflow|stock_basic|index_member_all|anns_d", source)
        self.assertIn("task-panel__secondary-action--danger", source)
        self.assertNotIn("正在读取任务状态：{taskId}", source)

    def test_lineage_table_defaults_to_progressive_disclosure(self):
        source = (COMPONENTS / "DataLineageTable.tsx").read_text(encoding="utf-8")
        styles = (COMPONENTS / "ProductSurface.css").read_text(encoding="utf-8")

        self.assertIn("prominent?: boolean", source)
        self.assertIn("defaultOpen?: boolean", source)
        self.assertIn("if (prominent) return table", source)
        self.assertIn('className="lineage-disclosure"', source)
        self.assertIn("open={defaultOpen || undefined}", source)
        self.assertIn("isTechnicalToken", source)
        self.assertIn("technical-token", source)
        self.assertIn("font-family: ui-monospace", styles)
        self.assertIn("overflow-wrap: normal", styles)
        self.assertIn("word-break: normal", styles)

    def test_packet_card_status_remains_accessible_without_visible_label_noise(self):
        source = (COMPONENTS / "PacketCard.tsx").read_text(encoding="utf-8")

        self.assertIn('role="status"', source)
        self.assertIn("aria-label={`状态：${status}`}", source)
        self.assertIn('className="packet-card__state-dot"', source)
        self.assertNotIn("StatusBadge", source)
        self.assertNotIn("product-surface-sr-only", source)

    def test_packet_card_tone_parser_is_negative_first_and_token_bound(self):
        source = (COMPONENTS / "PacketCard.tsx").read_text(encoding="utf-8")
        negative = source.index("const explicitlyNegatedPositive")
        negated_negative = source.index("const negatedNegativePattern")
        bad = source.index('remainingTokens.some((token) => ["failed"')
        good = source.index('remainingTokens.some((token) => ["ok", "ready"')

        self.assertLess(negative, negated_negative)
        self.assertLess(negated_negative, bad)
        self.assertLess(bad, good)
        self.assertIn("not[_\\s-]?(?:ok|ready", source)
        self.assertIn("(?:not|no)[_\\s-]?(?:blocked|blocker|blockers", source)
        self.assertIn('value.replace(negatedNegativePattern, " ")', source)
        for status in ("notready", "unready", "unavailable", "incomplete", "unsuccessful", "unverified"):
            self.assertIn(status, source)

    def test_scoped_styles_use_dark_shell_overridable_tokens(self):
        styles = (COMPONENTS / "ProductSurface.css").read_text(encoding="utf-8")

        for token in (
            "--cc-surface-subtle",
            "--cc-surface-elevated",
            "--cc-border-subtle",
            "--cc-text-primary",
            "--cc-text-secondary",
            "--cc-text-muted",
            "--cc-action-primary",
            "--cc-state-info-surface",
            "--cc-state-good-surface",
            "--cc-state-bad-surface",
        ):
            self.assertIn(f"var({token},", styles)


if __name__ == "__main__":
    unittest.main()
