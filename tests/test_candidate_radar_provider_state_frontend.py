import unittest
from pathlib import Path


class CandidateRadarProviderStateFrontendTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.page = (
            root / "desktop" / "src" / "routes" / "CandidateRadar.tsx"
        ).read_text(encoding="utf-8")

    def test_search_panel_replays_cached_tushare_state_without_model_claim(self):
        search_panel_start = self.page.index('title="搜票量化推演"')
        search_panel_end = self.page.index(
            '<details className="developer-audit-details">',
            search_panel_start,
        )
        search_panel = self.page[search_panel_start:search_panel_end]

        self.assertIn("searchQuantProviderModelAcceptance", self.page)
        self.assertIn("search_quant_provider_model_acceptance_receipt", self.page)
        self.assertIn("tushare_call_ledger_evidence_done", self.page)
        self.assertIn("provider_api_success_count", self.page)
        self.assertIn("deepseek_skipped_by_request", self.page)
        self.assertIn("Tushare ledger 已回放", self.page)
        self.assertIn("GET cache 已回放 Tushare provider ledger", self.page)
        self.assertIn("DeepSeek 已跳过：等待 governed executor", self.page)
        self.assertIn('label: "Tushare ledger"', search_panel)
        self.assertIn(
            "Tushare ledger 来自 cache / call_ledger 回放",
            search_panel,
        )
        self.assertIn("普通页不展示 prompt/output", search_panel)
        self.assertIn("不改 action", self.page)

    def test_search_panel_keeps_external_work_button_gated(self):
        submit_start = self.page.index("const launchQuantProjection = () =>")
        submit_end = self.page.index(
            "const launchQuantProjectionAcceptanceDryRun = () =>",
            submit_start,
        )
        submit_slice = self.page[submit_start:submit_end]
        search_panel_start = self.page.index('title="搜票量化推演"')
        search_panel_end = self.page.index(
            '<details className="developer-audit-details">',
            search_panel_start,
        )
        search_panel = self.page[search_panel_start:search_panel_end]

        self.assertIn("include_tushare: true", submit_slice)
        self.assertIn("include_deepseek: false", submit_slice)
        self.assertIn("user_approved: true", submit_slice)
        self.assertNotIn("run_provider_model_now", submit_slice)
        self.assertNotIn("operator_approved", submit_slice)
        self.assertIn("quantProjectionTaskBoundary", search_panel)
        self.assertIn("输入不触发外联", self.page)
        self.assertIn("POST task / worker", search_panel)
        self.assertIn("React render 不直接外联", search_panel)
        self.assertIn("React 渲染不直连 Tushare 或 DeepSeek", self.page)


if __name__ == "__main__":
    unittest.main()
