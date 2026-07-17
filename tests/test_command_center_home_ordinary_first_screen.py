from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "desktop" / "src" / "routes" / "CommandCenterHome.tsx"
HOME_CSS = ROOT / "desktop" / "src" / "routes" / "CommandCenterHome.css"


class CommandCenterHomeOrdinaryFirstScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = HOME.read_text(encoding="utf-8")
        cls.css = HOME_CSS.read_text(encoding="utf-8")
        start = cls.source.index('className="home-ordinary-dashboard"')
        end = cls.source.index('className="home-research-technical-details', start)
        cls.visible = cls.source[start:end]

    def test_first_screen_keeps_only_the_five_user_categories(self) -> None:
        for expected in (
            "当前标的",
            "数据日期",
            "当前结论",
            "确认研究标的",
            "市场与新鲜度",
            "仅作研究辅助，不下单、不改交易策略",
        ):
            self.assertIn(expected, self.visible)
        for engineering_surface in ("<MetricGrid", "<DataLineageTable", "<TaskLaunchReceipt", "LTG", "P0–P6"):
            self.assertNotIn(engineering_surface, self.visible)

    def test_research_and_engineering_surfaces_are_closed_by_default(self) -> None:
        details_start = self.source.index('className="home-research-technical-details')
        summary = self.source.index("<summary>研究与技术详情</summary>", details_start)
        first_metric = self.source.index("<MetricGrid", summary)
        self.assertLess(summary, first_metric)
        self.assertNotIn(" open", self.source[details_start:summary])
        self.assertIn(
            ".home-research-technical-details:not([open]) > :not(summary)",
            self.css,
        )

    def test_stale_or_unverified_data_fails_closed(self) -> None:
        self.assertIn("!ordinaryHomeFreshnessIsFresh", self.source)
        self.assertIn("本轮不按今日数据展示", self.source)
        self.assertIn('ordinaryHomeFirstScreenActionKind === "freshness"', self.source)
        self.assertIn('"#dataHealth"', self.source)

    def test_result_binding_is_single_source_current_and_fail_closed(self) -> None:
        binding_start = self.source.index("const ordinaryHomeCandidateCurrentSummaryBinding")
        binding_end = self.source.index("const ordinaryHomeLocalDataSourceContract", binding_start)
        binding = self.source[binding_start:binding_end]

        for field in (
            "current_result_symbol",
            "current_result_task_id",
            "current_result_version",
            "current_result_data_date",
            "current_result_freshness_state",
            "canonical_result_task_id",
            "ordinaryHomeExpectedTradeDateNormalized",
            "ordinaryHomeCalendarValidated",
            "dailyCommandConfirmedSourceTaskId",
            "ordinaryHomeCandidateStorageConflict",
            "sameOrdinaryHomeResultBinding",
            "ordinaryHomeCandidateIdentityConflict",
            "ordinaryHomeResultIdentityConflict",
        ):
            self.assertIn(field, binding)
        self.assertIn("makeStrictHomeResultBinding", binding)
        self.assertIn("selectMatchingHomeResultBinding", binding)
        self.assertIn("isCanonicalHomeResultFreshness(binding.freshness)", binding)
        self.assertIn("ordinaryHomeCandidateCurrentResolution.incomplete", binding)
        self.assertIn("ordinaryHomeCandidateCanonicalResolution.incomplete", binding)
        self.assertIn("ordinaryHomeCandidateResolution.incomplete", binding)
        self.assertIn("dailyCommandConfirmedChainResolution.incomplete", self.source)
        self.assertIn("latest_confirmed_symbol_readback_external_calls_triggered === false", self.source)
        self.assertIn("latest_confirmed_symbol_creates_task_from_readback === false", self.source)
        self.assertIn("binding.symbol === ordinaryHomeConfirmedSymbolForBinding", binding)
        self.assertIn("binding.taskId === dailyCommandConfirmedSourceTaskId", binding)
        self.assertIn("binding.dataDate === ordinaryHomeExpectedTradeDateNormalized", binding)
        self.assertNotIn(
            "dailyCommandP3OneGlanceReadable || ordinaryHomeStorageCurrentReadable",
            binding,
        )

    def test_new_unconfirmed_symbol_cannot_inherit_an_old_result(self) -> None:
        first_screen_start = self.source.index("const ordinaryHomeFirstScreenBinding")
        first_screen_end = self.source.index("return (", first_screen_start)
        first_screen = self.source[first_screen_start:first_screen_end]

        self.assertIn("ordinaryHomeResultInputGateClosed\n    ? null", first_screen)
        self.assertIn("hasUnconfirmedHomeSymbolEdit", self.source)
        self.assertIn("尚未确认；旧标的结果不会套用到新输入", first_screen)
        self.assertIn("旧标的结果保持退出", first_screen)
        self.assertNotIn("ordinaryHomePlainConclusionText", first_screen)
        self.assertIn("ordinaryHomeFirstScreenBinding?.symbol", first_screen)
        self.assertIn('ordinaryHomeFirstScreenActionKind === "result"', first_screen)
        self.assertIn('ordinaryHomeFirstScreenActionKind === "refresh"', first_screen)
        self.assertIn("ordinaryHomePendingResultReplay", first_screen)
        self.assertIn("旧结果继续隐藏", first_screen)

    def test_post_success_keeps_old_result_hidden_until_exact_readback(self) -> None:
        launch_start = self.source.index("const launchHomeQuantProjection")
        launch_end = self.source.index("const launchLiveBootstrap", launch_start)
        launch = self.source[launch_start:launch_end]
        binding_start = self.source.index("const ordinaryHomePendingResultReplay")
        binding_end = self.source.index("const ordinaryHomeLocalDataSourceContract", binding_start)
        binding = self.source[binding_start:binding_end]

        self.assertIn("setHomeQuantPendingResultSymbol(requestedSymbol)", launch)
        self.assertIn("setHomeQuantPendingResultTaskId(nextTaskId)", launch)
        self.assertNotIn("setHomeQuantSymbolTouched(false)", launch)
        self.assertIn("shouldKeepHomeResultPending", binding)
        self.assertIn("ordinaryHomeAuthoritativeResultBinding", binding)
        self.assertIn("setHomeQuantSymbolTouched(false)", binding)

    def test_guarded_supporting_details_hide_old_links_and_metadata(self) -> None:
        details_start = self.source.index('className="home-research-technical-details')
        details = self.source[details_start:]
        self.assertIn('data-authoritative-result-details="true"', details)
        self.assertIn("hidden={!ordinaryHomeSupportingDetailsReady}", details)
        self.assertIn("aria-hidden={!ordinaryHomeSupportingDetailsReady}", details)
        self.assertIn("旧摘要、来源、版本和结果链接保持隐藏", details)
        self.assertIn("shouldShowHomeSupportingDetails", self.source)

    def test_confirm_status_line_uses_the_same_fail_closed_first_screen_state(self) -> None:
        first_screen_start = self.source.index("const ordinaryHomeFirstScreenBinding")
        first_screen_end = self.source.index("return (", first_screen_start)
        first_screen = self.source[first_screen_start:first_screen_end]

        self.assertIn("const ordinaryHomeConfirmStatusLine", first_screen)
        self.assertIn("ordinaryHomeUserEditedNewSymbol", first_screen)
        self.assertIn("!ordinaryHomeFreshnessIsFresh", first_screen)
        self.assertIn("ordinaryHomeResultIdentityConflict", first_screen)
        self.assertIn("ordinaryHomeFirstScreenResultReady", first_screen)
        self.assertNotIn("ordinaryHomeReadableResultReady\n      ? \"已有结果", first_screen)

    def test_input_is_silent_and_only_primary_action_reuses_existing_handlers(self) -> None:
        self.assertIn('id="home-p1-symbol-confirm"', self.visible)
        self.assertIn('title="输入只做本地校验"', self.visible)
        self.assertIn("ordinaryHomeFirstScreenActionKind === \"refresh\" ? refreshHomeResearchReadback : launchHomeQuantProjection", self.visible)
        self.assertNotIn("postCandidateRadarQuantProjection(", self.visible)

    def test_mobile_and_reduced_motion_contracts_are_route_scoped(self) -> None:
        self.assertIn("@media (max-width: 760px)", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn(".home-ordinary-dashboard *", self.css)


if __name__ == "__main__":
    unittest.main()
