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
        self.assertIn("task-panel__primary-action", visible)
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
        self.assertIn('className="product-surface-sr-only"', source)
        self.assertNotIn("{status ? <StatusBadge", source)

    def test_packet_card_tone_parser_is_negative_first_and_token_bound(self):
        source = (COMPONENTS / "PacketCard.tsx").read_text(encoding="utf-8")
        negative = source.index("const explicitlyNegatedPositive")
        good = source.index('tokens.some((token) => ["ok", "ready"')

        self.assertLess(negative, good)
        self.assertIn("not[_\\s-]?(?:ok|ready", source)
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
