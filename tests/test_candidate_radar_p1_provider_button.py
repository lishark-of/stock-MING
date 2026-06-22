import unittest
from pathlib import Path


class CandidateRadarP1ProviderButtonTests(unittest.TestCase):
    def test_provider_acceptance_button_is_explicit_tushare_first_after_execution_request(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "desktop" / "src" / "routes" / "CandidateRadar.tsx"
        ).read_text(encoding="utf-8")

        submit_start = source.index("const launchQuantProjection = () =>")
        submit_end = source.index("const launchQuantProjectionAcceptanceDryRun = () =>", submit_start)
        submit_slice = source[submit_start:submit_end]
        provider_start = source.index("const launchQuantProjectionProviderModelAcceptance = () =>")
        provider_end = source.index("const launchWorkerExecutionRequest = () =>", provider_start)
        provider_slice = source[provider_start:provider_end]
        execution_request_start = source.index("search_quant_projection_execution_request_receipt")
        execution_request_slice = source[execution_request_start:source.index("<DataLineageTable rows={objectRow(searchQuantProjectionExecutionRequest)}", execution_request_start)]

        self.assertIn("postCandidateRadarQuantProjectionProviderModelAcceptance", source)
        self.assertIn('scan_mode: "quant_projection_provider_model_acceptance"', provider_slice)
        self.assertIn("operator_approved: true", provider_slice)
        self.assertIn("acceptance_scope_hash: String(searchQuantProjectionExecutionRequest.acceptance_scope_hash ?? \"\")", provider_slice)
        self.assertIn("include_deepseek: false", provider_slice)
        self.assertIn('requested_by: "candidate_radar_page"', provider_slice)
        self.assertIn("确认 Tushare-first 补证", execution_request_slice)
        self.assertIn("disabled={!searchQuantProjectionExecutionRequest.acceptance_scope_hash}", execution_request_slice)
        self.assertIn("POST task 触发 Tushare light provider ledger", execution_request_slice)
        self.assertIn("DeepSeek 保持 skipped", execution_request_slice)
        self.assertIn("不交易、不改 strategy action", execution_request_slice)
        self.assertIn("点击后本区域会显示任务创建记录和状态", execution_request_slice)
        self.assertIn("成功后自动刷新本地 cache", execution_request_slice)
        self.assertIn("search_quant_provider_model_acceptance_receipt / call_ledger / packet", execution_request_slice)
        self.assertIn("不在 React render 里补调 provider", execution_request_slice)
        self.assertIn("<TaskLaunchReceipt receipt={taskReceipt} />", execution_request_slice)
        self.assertIn("<TaskStatusPanel taskId={taskId} onSuccess={refreshCache} />", execution_request_slice)
        self.assertNotIn("postCandidateRadarQuantProjectionProviderModelAcceptance", submit_slice)
        self.assertNotIn("operator_approved", submit_slice)
        self.assertNotIn("include_deepseek: false", submit_slice)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("TUSHARE_TOKEN", source)
        self.assertNotIn("DEEPSEEK_API_KEY", source)
        self.assertNotIn("GITHUB_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
