import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from server.api import routes_audit
from server.services import audit_service


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "scripts" / "user_route_qa_runbook.py"
RUNNER = ROOT / "scripts" / "user_route_qa_runner.mjs"


class UserRouteQaRunbookTests(unittest.TestCase):
    def test_runbook_pins_ordinary_routes_and_boundaries(self):
        result = subprocess.run(
            [".venv/bin/python", str(RUNBOOK), "--json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["schema_version"], "command_center_3_user_route_qa_runbook.v1")
        self.assertEqual(payload["status"], "user_route_qa_runbook_ready_execution_pending")
        self.assertEqual(payload["route_count"], 5)
        self.assertEqual(payload["viewport_count"], 2)
        self.assertEqual(payload["qa_matrix_count"], 10)
        self.assertEqual({row["route"] for row in payload["qa_routes"]}, {"#home", "#candidates", "#marginEtf", "#factor", "#next"})
        self.assertEqual({row["viewport"] for row in payload["qa_matrix"]}, {"desktop", "mobile"})
        self.assertTrue(payload["opens_no_browser"])
        self.assertTrue(payload["starts_no_servers"])
        self.assertTrue(payload["writes_no_artifacts"])
        self.assertTrue(payload["execution_required_for_visual_qa"])
        self.assertFalse(payload["visual_qa_complete"])
        self.assertFalse(payload["typing_silence_verified"])
        self.assertFalse(payload["production_replacement_complete"])
        self.assertFalse(payload["streamlit_fallback_retirement_ready"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        margin_route = next(row for row in payload["qa_routes"] if row["route"] == "#marginEtf")
        self.assertIn("confirmed radar bridge", margin_route["focus"])
        margin_matrix = [row for row in payload["qa_matrix"] if row["route"] == "#marginEtf"]
        self.assertEqual(len(margin_matrix), 2)
        self.assertTrue(all(row["route_specific_check"] == "margin_etf_confirmed_data_bridge_visible" for row in margin_matrix))
        result_chain_matrix = [row for row in payload["qa_matrix"] if row["route"] in {"#candidates", "#factor", "#next"}]
        self.assertEqual(len(result_chain_matrix), 6)
        self.assertTrue(all(row["route_specific_check"] == "search_quant_same_result_chain_visible" for row in result_chain_matrix))

    def test_runner_plan_is_local_only_and_checks_typing_silence(self):
        result = subprocess.run(
            [
                "node",
                str(RUNNER),
                "--print-plan",
                "--json",
                "--base-url",
                "http://127.0.0.1:5173",
                "--api-base",
                "http://127.0.0.1:8710",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        plan = json.loads(result.stdout)
        runner_source = RUNNER.read_text(encoding="utf-8")

        self.assertEqual(plan["schema_version"], "command_center_3_user_route_qa_plan.v1")
        self.assertEqual(plan["status"], "user_route_qa_plan_ready")
        self.assertEqual(plan["route_count"], 5)
        self.assertEqual(plan["viewport_count"], 2)
        self.assertEqual(plan["qa_matrix_count"], 10)
        self.assertTrue(plan["local_urls_only"])
        self.assertFalse(plan["external_calls_triggered"])
        self.assertFalse(plan["tushare_called"])
        self.assertFalse(plan["deepseek_called"])
        self.assertFalse(plan["github_called"])
        self.assertTrue(plan["does_not_execute_trades"])
        self.assertIn("typing into visible inputs does not create a task", plan["checks"])
        self.assertIn("visible editable inputs must be typed before typing silence is accepted", plan["checks"])
        self.assertIn("candidate/factor/next routes display the same symbol, task id, and result_version when current result cache exists", plan["checks"])
        self.assertIn("optional degraded-last-good replay proves visible degraded reason, last-good retention, and stale-result overwrite guard without writing cache", plan["checks"])
        self.assertIn("route-specific checks verify the margin ETF confirmed data bridge is visible", plan["checks"])
        margin_matrix = [row for row in plan["qa_matrix"] if row["route"] == "#marginEtf"]
        self.assertEqual(len(margin_matrix), 2)
        self.assertTrue(all(row["route_specific_check"] == "margin_etf_confirmed_data_bridge_visible" for row in margin_matrix))
        self.assertTrue(all(row["route_specific_check_required"] for row in margin_matrix))
        result_chain_matrix = [row for row in plan["qa_matrix"] if row["route"] in {"#candidates", "#factor", "#next"}]
        self.assertEqual(len(result_chain_matrix), 6)
        self.assertTrue(all(row["route_specific_check"] == "search_quant_same_result_chain_visible" for row in result_chain_matrix))
        self.assertTrue(all(row["route_specific_check_required"] for row in result_chain_matrix))
        self.assertIn("typed_without_submit", runner_source)
        self.assertIn("editable_visible_input_count", runner_source)
        self.assertIn("typing_required", runner_source)
        self.assertIn("typing_covered", runner_source)
        self.assertIn("task_created_by_render_or_typing", runner_source)
        self.assertIn("route_specific_check_passed", runner_source)
        self.assertIn("search_quant_same_result_chain_visible", runner_source)
        self.assertIn("--candidate-result-scenario", runner_source)
        self.assertIn("degraded-last-good", runner_source)
        self.assertIn("candidate_result_scenario_writes_cache: false", runner_source)
        self.assertIn("buildDegradedLastGoodCandidateEnvelope", runner_source)
        self.assertIn("stale_overwrite_guard_visible", runner_source)
        self.assertIn("candidate_result_chain", runner_source)
        self.assertIn("current_result_matches_latest_task", runner_source)
        self.assertIn("old_task_can_overwrite_current", runner_source)
        self.assertIn("margin_etf_confirmed_data_bridge_visible", runner_source)
        self.assertIn('aria-label="margin etf candidate radar confirmed data bridge"', runner_source)
        self.assertIn("Tushare 数据链", runner_source)
        self.assertIn("结果版本", runner_source)
        self.assertIn("同源账本", runner_source)
        self.assertIn("DeepSeek 解释", runner_source)
        self.assertIn("no_task_on_open_boundary", runner_source)
        self.assertIn("创建 task", runner_source)
        self.assertIn("desktopRequire", runner_source)
        self.assertIn("desktop/node_modules", runner_source)
        self.assertIn("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", runner_source)
        self.assertIn("SYSTEM_CHROMIUM_EXECUTABLE_PATHS", runner_source)
        self.assertIn("Google Chrome.app", runner_source)
        self.assertIn("function chromiumLaunchOptions()", runner_source)
        self.assertIn('waitUntil: "domcontentloaded"', runner_source)
        self.assertIn('waitForSelector("h1, h2, h3", { state: "attached"', runner_source)
        self.assertIn("route_heading", runner_source)
        self.assertIn("screenshots_are_not_tracked: true", runner_source)
        self.assertNotIn("child_process", runner_source)
        self.assertNotIn("place_order", runner_source)

    def test_audit_cache_summarizes_user_route_qa_local_evidence(self):
        routes = ["#home", "#candidates", "#marginEtf", "#factor", "#next"]
        viewports = ["desktop", "mobile"]
        report_rows = [
            {
                "route": route,
                "label": route.strip("#") or "home",
                "viewport": viewport,
                "status": "passed",
                "route_heading": "Candidate Radar" if route == "#candidates" else "Command Center",
                "visual_qa_complete": True,
                "typing_silence_verified": True,
                "task_created_by_render_or_typing": False,
                "task_count_before": 0,
                "task_count_after": 0,
                "clipped_count": 0,
                "disabled_buttons_without_reason_count": 0,
                "audit_noise_count": 0,
                "visible_input_count": 1,
                "editable_visible_input_count": 1,
                "typing_required": True,
                "typing_covered": True,
                "typing_reason": "typed_editable_visible_input",
                "route_specific_check": "margin_etf_confirmed_data_bridge_visible"
                if route == "#marginEtf"
                else "search_quant_same_result_chain_visible"
                if route in {"#candidates", "#factor", "#next"}
                else "generic_route_heading_visible",
                "route_specific_check_passed": True,
                "route_specific_missing": [],
                "candidate_result_scenario": "degraded-last-good",
                "candidate_result_chain": {
                    "status": "degraded_result_recorded_last_good_retained",
                    "degraded_result_visible": True,
                    "degraded_reason": "skipped_missing_facts",
                    "old_task_can_overwrite_current": False,
                    "old_task_overwrite_guard_ready": True,
                    "current_result_matches_latest_task": False,
                }
                if route in {"#candidates", "#factor", "#next"}
                else {},
                "route_observed_ms": 320,
            }
            for route in routes
            for viewport in viewports
        ]
        report = {
            "schema_version": "command_center_3_user_route_qa_result.v1",
            "status": "user_route_qa_passed",
            "run_id": "2026-07-04T07-05-30-085Z",
            "generated_at": "2026-07-04T07:05:30.085Z",
            "route_count": len(routes),
            "viewport_count": len(viewports),
            "qa_matrix_count": len(report_rows),
            "passed_count": len(report_rows),
            "review_required_count": 0,
            "route_specific_review_required_count": 0,
            "margin_etf_confirmed_bridge_row_count": 2,
            "margin_etf_confirmed_bridge_passed": True,
            "console_error_count": 0,
            "visual_qa_complete": True,
            "typing_silence_verified": True,
            "candidate_result_scenario": "degraded-last-good",
            "candidate_result_scenario_replay": True,
            "candidate_result_scenario_writes_cache": False,
            "production_replacement_complete": False,
            "streamlit_fallback_retirement_ready": False,
            "rows": report_rows,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
        }
        original_root = audit_service.USER_ROUTE_QA_ARTIFACT_ROOT
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "user_route_qa"
            report_path = artifact_root / report["run_id"] / "user_route_qa_report.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(json.dumps(report), encoding="utf-8")
            audit_service.USER_ROUTE_QA_ARTIFACT_ROOT = artifact_root
            try:
                evidence, rows = audit_service._user_route_qa_evidence_contract()
                packet = audit_service.read_call_ledger_audit_cache()
                route_envelope = routes_audit.get_user_route_qa_evidence_cache()
            finally:
                audit_service.USER_ROUTE_QA_ARTIFACT_ROOT = original_root

        self.assertEqual(evidence["schema_version"], "command_center_3_user_route_qa_evidence.v1")
        self.assertEqual(evidence["status"], "user_route_qa_evidence_available_review_pending")
        self.assertTrue(evidence["ordinary_route_visual_qa_complete"])
        self.assertTrue(evidence["typing_silence_verified"])
        self.assertTrue(evidence["candidate_route_visual_qa_passed"])
        self.assertEqual(evidence["report_count"], 1)
        self.assertEqual(evidence["passing_report_count"], 1)
        self.assertEqual(evidence["latest_report_status"], "user_route_qa_passed")
        self.assertTrue(evidence["latest_report_passed"])
        self.assertEqual(evidence["latest_report_route_count"], 5)
        self.assertEqual(evidence["latest_report_viewport_count"], 2)
        self.assertEqual(evidence["latest_report_qa_matrix_count"], 10)
        self.assertEqual(evidence["latest_report_passed_count"], 10)
        self.assertEqual(evidence["latest_report_review_required_count"], 0)
        self.assertEqual(evidence["latest_report_console_error_count"], 0)
        self.assertTrue(evidence["latest_report_visual_qa_complete"])
        self.assertTrue(evidence["latest_report_typing_silence_verified"])
        self.assertEqual(evidence["latest_report_candidate_result_scenario"], "degraded-last-good")
        self.assertTrue(evidence["latest_report_candidate_result_scenario_replay"])
        self.assertFalse(evidence["latest_report_candidate_result_scenario_writes_cache"])
        self.assertTrue(evidence["latest_report_degraded_last_good_replay_passed"])
        self.assertEqual(evidence["latest_report_task_silence_failed_count"], 0)
        self.assertEqual(evidence["latest_report_route_specific_failed_count"], 0)
        self.assertEqual(evidence["latest_report_candidate_route_row_count"], 2)
        self.assertTrue(evidence["latest_report_candidate_route_passed"])
        self.assertEqual(evidence["latest_report_margin_etf_confirmed_bridge_row_count"], 2)
        self.assertTrue(evidence["latest_report_margin_etf_confirmed_bridge_passed"])
        self.assertEqual(evidence["row_count"], 10)
        self.assertEqual(evidence["task_silence_failed_count"], 0)
        self.assertFalse(evidence["production_replacement_complete"])
        self.assertFalse(evidence["streamlit_fallback_retirement_ready"])
        self.assertTrue(evidence["reads_ignored_local_reports_only"])
        self.assertTrue(evidence["opens_no_browser"])
        self.assertTrue(evidence["writes_no_artifacts"])
        self.assertFalse(evidence["external_calls_triggered"])
        self.assertFalse(evidence["tushare_called"])
        self.assertFalse(evidence["deepseek_called"])
        self.assertFalse(evidence["github_called"])
        self.assertTrue(evidence["does_not_execute_trades"])
        self.assertTrue(evidence["does_not_modify_strategy_action"])
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["screenshot_artifact_omitted"] for row in rows))
        self.assertTrue(all(row["typing_covered"] for row in rows))
        self.assertEqual(sum(1 for row in rows if row["typing_required"]), 10)
        self.assertEqual(sum(1 for row in rows if row["route"] == "#candidates"), 2)
        self.assertEqual(sum(1 for row in rows if row["route_specific_check"] == "margin_etf_confirmed_data_bridge_visible"), 2)
        self.assertTrue(all(row["route_specific_check_passed"] for row in rows))
        self.assertEqual(
            sum(
                1
                for row in rows
                if row["candidate_result_scenario"] == "degraded-last-good"
                and row["old_task_overwrite_guard_ready"]
                and not row["old_task_can_overwrite_current"]
            ),
            6,
        )

        packet_evidence = packet["user_route_qa_evidence_contract"]
        self.assertEqual(packet_evidence["status"], evidence["status"])
        self.assertEqual(packet["counts"]["user_route_qa_evidence_report_count"], 1)
        self.assertEqual(packet["counts"]["user_route_qa_evidence_passing_report_count"], 1)
        self.assertEqual(packet["counts"]["user_route_qa_evidence_row_count"], 10)
        self.assertTrue(packet["counts"]["user_route_qa_latest_report_passed"])
        self.assertEqual(packet["counts"]["user_route_qa_latest_report_qa_matrix_count"], 10)
        self.assertEqual(packet["counts"]["user_route_qa_latest_report_review_required_count"], 0)
        self.assertEqual(packet["counts"]["user_route_qa_latest_report_console_error_count"], 0)
        self.assertTrue(packet["counts"]["user_route_qa_latest_report_candidate_route_passed"])
        self.assertTrue(packet["counts"]["user_route_qa_latest_report_margin_etf_confirmed_bridge_passed"])
        self.assertEqual(packet["counts"]["user_route_qa_latest_report_margin_etf_confirmed_bridge_row_count"], 2)
        self.assertTrue(packet["counts"]["user_route_qa_visual_complete"])
        self.assertTrue(packet["counts"]["user_route_qa_typing_silence_verified"])
        self.assertTrue(packet["counts"]["user_route_qa_candidate_route_passed"])
        self.assertTrue(packet["counts"]["user_route_qa_margin_etf_confirmed_bridge_passed"])
        self.assertEqual(packet["counts"]["user_route_qa_margin_etf_confirmed_bridge_row_count"], 2)
        self.assertTrue(packet["policy"]["user_route_qa_evidence_is_local_ignored_artifact_summary"])
        self.assertTrue(packet["policy"]["user_route_qa_evidence_does_not_open_browser"])
        self.assertTrue(packet["policy"]["user_route_qa_evidence_is_not_streamlit_retirement"])
        self.assertTrue(packet["policy"]["user_route_qa_evidence_is_not_production_replacement"])

        self.assertTrue(route_envelope["ok"])
        route_packet = route_envelope["data"]
        self.assertEqual(route_packet["packet_key"], "command_center_3_user_route_qa_evidence_cache")
        self.assertEqual(route_packet["status"], "user_route_qa_evidence_available_review_pending")
        self.assertEqual(route_packet["user_route_qa_evidence_contract"]["latest_report_status"], "user_route_qa_passed")
        self.assertTrue(route_packet["counts"]["user_route_qa_latest_report_passed"])
        self.assertTrue(route_packet["counts"]["user_route_qa_latest_report_margin_etf_confirmed_bridge_passed"])
        self.assertTrue(route_packet["policy"]["user_route_qa_evidence_does_not_create_task"])
        self.assertFalse(route_packet["external_calls_triggered"])
        self.assertFalse(route_packet["tushare_called"])
        self.assertFalse(route_packet["deepseek_called"])
        self.assertTrue(route_packet["does_not_execute_trades"])


if __name__ == "__main__":
    unittest.main()
