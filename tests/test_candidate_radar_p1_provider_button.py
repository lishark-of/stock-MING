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
        ordinary_quant_start = source.index('title="搜票量化推演"')
        ordinary_quant_slice = source[ordinary_quant_start:source.index('<details className="developer-audit-details">', ordinary_quant_start)]

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
        self.assertIn("quantProjectionTushareFirstState", ordinary_quant_slice)
        self.assertIn("quantProjectionSubmitAriaLabel", source)
        self.assertIn("quantProjectionInputBoundaryLabel", source)
        self.assertIn("quantProjectionSubmitButtonLabel", source)
        self.assertIn("title={quantProjectionInputBoundaryLabel}", ordinary_quant_slice)
        self.assertIn("title={quantProjectionSubmitButtonLabel}", ordinary_quant_slice)
        self.assertIn("aria-label={quantProjectionSubmitAriaLabel}", ordinary_quant_slice)
        self.assertIn("点击确认才创建 ${quantProjectionSymbolValidation.normalized} 的 Tushare-first POST task；DeepSeek skipped，成功后通过 GET cache 回放", source)
        self.assertIn("按钮不可用原因：先输入股票代码；输入本身不会创建 task", source)
        self.assertIn("search_quant_projection_small_data_writeback_summary", source)
        self.assertIn("searchQuantProjectionSmallDataWriteback.summary_label", source)
        self.assertIn("searchQuantProjectionSmallDataWriteback.ordinary_readback_summary", source)
        self.assertIn("searchQuantProjectionSmallDataWriteback.ordinary_readback_next_step", source)
        self.assertIn("searchQuantProjectionSmallDataWriteback.ordinary_readback_boundary", source)
        self.assertIn("quantProjectionSmallDataReady", ordinary_quant_slice)
        self.assertIn("quantProjectionSmallDataNextStep", ordinary_quant_slice)
        self.assertIn('label: "小数据下一步"', ordinary_quant_slice)
        self.assertIn("search_quant_projection_interpretation_summary", source)
        self.assertIn("quantProjectionInterpretationState", ordinary_quant_slice)
        self.assertIn('label: "解释结果"', ordinary_quant_slice)
        self.assertIn('label: "解释下一步"', ordinary_quant_slice)
        self.assertNotIn("确认 Tushare-first 补证", ordinary_quant_slice)
        self.assertNotIn("disabled={!searchQuantProjectionExecutionRequest.acceptance_scope_hash}", ordinary_quant_slice)
        self.assertIn('label: "Tushare-first"', ordinary_quant_slice)
        self.assertIn('label: "最近任务"', ordinary_quant_slice)
        self.assertIn('label: "任务回放"', ordinary_quant_slice)
        self.assertIn('label: "结果回放"', ordinary_quant_slice)
        self.assertIn("quantProjectionLatestTaskState", ordinary_quant_slice)
        self.assertIn("quantProjectionTaskReadbackState", ordinary_quant_slice)
        self.assertIn("quantProjectionResultReplayState", ordinary_quant_slice)
        self.assertIn("search_quant_provider_model_acceptance_receipt / call_ledger / packet", source)
        self.assertIn("最近任务只显示本地 FastAPI 返回的 task id 和安全步骤", ordinary_quant_slice)
        self.assertIn("最近任务会优先从本地 cache / packet 回放 task id 和安全 current_step", ordinary_quant_slice)
        self.assertIn("GET cache 不会因此补调 provider", ordinary_quant_slice)
        self.assertIn("不在普通页面展开审计表", ordinary_quant_slice)
        self.assertIn("DeepSeek 保持 skipped", ordinary_quant_slice)
        self.assertIn("确认后创建 Tushare-first 按钮门控 POST task / worker", ordinary_quant_slice)
        self.assertIn("不交易、不改 strategy action", ordinary_quant_slice)
        self.assertNotIn("postCandidateRadarQuantProjectionProviderModelAcceptance", submit_slice)
        self.assertNotIn("operator_approved", submit_slice)
        self.assertIn("include_deepseek: false", submit_slice)
        self.assertIn("user_approved: true", submit_slice)
        self.assertIn("refreshCache();", submit_slice)
        self.assertIn("任务接收后立即回读本地 cache receipt", ordinary_quant_slice)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("TUSHARE_TOKEN", source)
        self.assertNotIn("DEEPSEEK_API_KEY", source)
        self.assertNotIn("GITHUB_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
