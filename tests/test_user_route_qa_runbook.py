import json
import subprocess
import unittest
from pathlib import Path


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
        self.assertIn("typed_without_submit", runner_source)
        self.assertIn("task_created_by_render_or_typing", runner_source)
        self.assertIn('waitUntil: "domcontentloaded"', runner_source)
        self.assertIn('waitForSelector("h1, h2, h3", { state: "attached"', runner_source)
        self.assertIn("route_heading", runner_source)
        self.assertIn("screenshots_are_not_tracked: true", runner_source)
        self.assertNotIn("child_process", runner_source)
        self.assertNotIn("place_order", runner_source)


if __name__ == "__main__":
    unittest.main()
