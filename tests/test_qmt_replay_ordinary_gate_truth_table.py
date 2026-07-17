import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "qmt_replay_ordinary_gate_truth_table.mjs"


class QmtReplayOrdinaryGateTruthTableTests(unittest.TestCase):
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
        self.assertGreaterEqual(report["row_count"], 36)
        self.assertEqual(report["passed_count"], report["row_count"])
        rows = {row["name"]: row for row in report["results"]}
        self.assertTrue(rows["valid_first_launch"]["actual"])
        self.assertTrue(rows["valid_bound_result"]["actual"])
        self.assertTrue(rows["valid_candidate_optional_allowlisted_ledgers"]["actual"])
        for key in (
            "candidate_warning",
            "candidate_ledger_missing",
            "ledger_provider_call",
            "lineage_symbol_mismatch",
            "invalid_calendar_date",
            "authoritative_calendar_missing",
            "qmt_boundary_field_missing",
            "qmt_boundary_trade",
            "ready_result_integrity_missing",
            "ready_result_source_date_mismatch",
            "candidate_next_ledger_swap",
            "qmt_candidate_ledger_swap",
            "candidate_backend_status_wrong",
            "candidate_backend_unknown",
            "candidate_backend_duplicate",
            "qmt_frontend_endpoint_wrong",
            "candidate_ledger_broker_session_opened_true",
            "candidate_ledger_contains_secret_true",
            "candidate_ledger_external_call_count_nonzero",
        ):
            self.assertFalse(rows[key]["actual"], key)


if __name__ == "__main__":
    unittest.main()
