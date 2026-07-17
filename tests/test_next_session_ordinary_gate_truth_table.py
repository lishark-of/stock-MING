import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "next_session_ordinary_gate_truth_table.mjs"


class NextSessionOrdinaryGateTruthTableTests(unittest.TestCase):
    def test_strict_gate_truth_table(self) -> None:
        result = subprocess.run(
            ["node", str(RUNNER)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertGreaterEqual(report["row_count"], 26)
        self.assertEqual(report["passed_count"], report["row_count"])
        rows = {row["name"]: row for row in report["results"]}
        self.assertTrue(rows["valid_same_packet"]["ready"])
        for key in (
            "validated_is_not_fresh",
            "generic_calendar_conflict",
            "invalid_calendar_date",
            "boolean_task_rejected",
            "number_result_rejected",
            "malformed_scope_rejected",
            "payload_symbol_missing",
            "summary_symbol_mismatch",
            "cache_envelope_warning",
            "packet_warning",
            "packet_degraded",
            "packet_boundary_missing",
            "provider_execution_true",
            "worker_execution_true",
        ):
            self.assertFalse(rows[key]["ready"], key)


if __name__ == "__main__":
    unittest.main()
