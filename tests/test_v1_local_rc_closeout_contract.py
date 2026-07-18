from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import v1_local_rc_closeout_contract as contract
from server.services import v1_closeout_service


def _qmt_receipt() -> dict:
    return {
        "schema_version": "qmt_readonly_local_replay_result.v1",
        "status": "local_scope_replay_verified_export_pending",
        "mode": "local_research_replay",
        "external_calls_triggered": False,
        "external_call_count": 0,
        "qmt_called": False,
        "qmt_connection_count": 0,
        "qmt_external_connection_attempted": False,
        "qmt_process_discovered": False,
        "qmt_client_imported": False,
        "xtquant_imported": False,
        "broker_called": False,
        "broker_session_opened": False,
        "broker_session_count": 0,
        "account_query_executed": False,
        "real_order_submitted": False,
        "real_order_count": 0,
        "real_order_cancelled": False,
        "real_trade_executed": False,
        "real_trade_count": 0,
        "real_holdings_modified": False,
        "real_trading_enabled": False,
        "external_qmt_integration_verified": False,
        "paper_trading_sandbox_ready": False,
        "worker_dispatched": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_modify_holdings": True,
        "contains_secret": False,
    }


def _valid_evaluation() -> dict:
    source = {
        "schema_version": "local_rc_contract_fixture.v1",
        "status": "passed",
        "contains_secret": False,
    }
    summary = v1_closeout_service._safe_summary(
        source,
        v1_closeout_service._SAFE_PACKET_FIELDS,
        observed=True,
    )
    version_rows = [
        v1_closeout_service._version_row(version, [summary], True, [])
        for version in contract.EXPECTED_VERSION_IDS
    ]
    facts = {key: False for key in contract.EXPECTED_PRODUCTION_FACT_KEYS}
    facts.update(
        {
            "trade_cal_provider_direct": True,
            "factor_small_pool_provider_direct": True,
            "qmt_research_isolation": True,
        }
    )
    ltg_rows = v1_closeout_service._build_ltg_rows(version_rows, facts)
    done_count = sum(row["can_close"] is True for row in ltg_rows)
    return {
        "packet_key": "command_center_3_v1_local_rc",
        "schema_version": "command_center_3_v1_local_rc.v1",
        "status": "v1_local_evidence_ready_production_closeout_pending",
        "mode": "read_only_local_evidence_closeout",
        "local_direct_evidence_ready": True,
        "local_version_ready_count": 7,
        "local_version_total_count": 7,
        "missing_local_versions": [],
        "production_strict_closeout_complete": False,
        "strict_closeout": f"{done_count}/14",
        "strict_closeout_done_count": done_count,
        "strict_closeout_total_count": 14,
        "strict_closeout_remaining_count": 14 - done_count,
        "version_evidence_rows": version_rows,
        "ltg_closure_rows": ltg_rows,
        "production_fact_rows": [
            {"evidence_key": key, "observed": value}
            for key, value in sorted(facts.items())
        ],
        "qmt_research_isolation_summary": v1_closeout_service._safe_summary(
            _qmt_receipt(),
            v1_closeout_service._SAFE_PACKET_FIELDS,
            observed=True,
        ),
        "cache_only": True,
        "read_only": True,
        "creates_task": False,
        "writes_storage": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "qmt_called": False,
        "broker_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "raw_packet_payloads_exposed": False,
        "raw_account_or_config_exposed": False,
        "evidence_boundary": (
            "v1_local_rc_is_local_direct_evidence_summary_"
            "production_strict_closeout_is_separate"
        ),
    }


class V1LocalRcCloseoutContractTests(unittest.TestCase):
    def test_ltg04_requires_factor_output_not_generic_candidate_worker_runtime(self):
        self.assertIn("factor_full_market_research", contract.PRODUCTION_REQUIREMENTS["LTG-04"])
        self.assertNotIn("full_market_worker_runtime", contract.PRODUCTION_REQUIREMENTS["LTG-04"])

    def test_valid_contract_accounts_for_14_ltgs_and_closes_only_ltg12(self):
        result = contract.build_contract(evaluation=_valid_evaluation())

        self.assertTrue(result["passed"])
        self.assertEqual(result["status"], "v1_local_rc_closeout_contract_passed")
        self.assertTrue(result["local_rc"]["ready"])
        self.assertEqual(result["local_rc"]["ltg_locally_ready_count"], 14)
        self.assertEqual(result["production_strict"]["closed_ltg_ids"], ["LTG-12"])
        self.assertFalse(result["production_strict"]["complete"])
        self.assertTrue(result["ltg12_research_isolation"]["ready"])
        self.assertEqual(
            [row["version"] for row in result["sealed_version_chain"]],
            list(contract.EXPECTED_VERSION_IDS),
        )

    def test_future_complete_production_evidence_does_not_invalidate_local_contract(self):
        evaluation = _valid_evaluation()
        facts = {key: True for key in contract.EXPECTED_PRODUCTION_FACT_KEYS}
        evaluation["production_fact_rows"] = [
            {"evidence_key": key, "observed": value}
            for key, value in sorted(facts.items())
        ]
        evaluation["ltg_closure_rows"] = v1_closeout_service._build_ltg_rows(
            evaluation["version_evidence_rows"],
            facts,
        )
        evaluation.update(
            {
                "status": "v1_local_evidence_ready_production_closeout_complete",
                "production_strict_closeout_complete": True,
                "strict_closeout": "14/14",
                "strict_closeout_done_count": 14,
                "strict_closeout_remaining_count": 0,
            }
        )

        result = contract.build_contract(evaluation=evaluation)

        self.assertTrue(result["passed"])
        self.assertTrue(result["local_rc"]["ready"])
        self.assertTrue(result["production_strict"]["complete"])
        self.assertEqual(len(result["production_strict"]["closed_ltg_ids"]), 14)

    def test_sealed_chain_digest_is_deterministic_and_uses_exact_allowlist(self):
        first = contract.build_contract(evaluation=_valid_evaluation())
        second = contract.build_contract(evaluation=_valid_evaluation())
        material = {
            "schema_version": "command_center_3_sealed_version_chain.v1",
            "versions": [
                {"version": version, "sealed_sha": sealed_sha}
                for version, sealed_sha in contract.SEALED_VERSION_CHAIN
            ],
        }
        expected = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        self.assertEqual(first["sealed_version_chain_digest"], expected)
        self.assertEqual(second["sealed_version_chain_digest"], expected)

    def test_wrong_version_order_and_duplicate_ltg_are_blocked(self):
        wrong_version = _valid_evaluation()
        wrong_version["version_evidence_rows"][0], wrong_version["version_evidence_rows"][1] = (
            wrong_version["version_evidence_rows"][1],
            wrong_version["version_evidence_rows"][0],
        )
        self.assertFalse(contract.build_contract(evaluation=wrong_version)["passed"])

        duplicate_ltg = _valid_evaluation()
        duplicate_ltg["ltg_closure_rows"][-1] = copy.deepcopy(
            duplicate_ltg["ltg_closure_rows"][0]
        )
        self.assertFalse(contract.build_contract(evaluation=duplicate_ltg)["passed"])

    def test_summary_count_tampering_is_blocked(self):
        evaluation = _valid_evaluation()
        evaluation["strict_closeout_done_count"] = 14
        evaluation["strict_closeout"] = "14/14"

        result = contract.build_contract(evaluation=evaluation)

        self.assertFalse(result["passed"])
        rows = {row["criterion"]: row for row in result["criteria"]}
        self.assertFalse(rows["strict_counts_derived_from_rows"]["passed"])

    def test_missing_external_evidence_cannot_be_claimed_closed(self):
        evaluation = _valid_evaluation()
        ltg01 = evaluation["ltg_closure_rows"][0]
        ltg01["production_complete"] = True
        ltg01["can_close"] = True
        ltg01["closeout_decision"] = "strict_closeout_allowed"
        evaluation["strict_closeout_done_count"] = 2
        evaluation["strict_closeout_remaining_count"] = 12
        evaluation["strict_closeout"] = "2/14"

        result = contract.build_contract(evaluation=evaluation)

        self.assertFalse(result["passed"])
        rows = {row["criterion"]: row for row in result["criteria"]}
        self.assertFalse(rows["ltg_decisions_derived_from_rows"]["passed"])
        self.assertFalse(rows["missing_external_evidence_cannot_close_non_ltg12"]["passed"])

    def test_ltg12_blocks_any_qmt_broker_order_or_trade_activity(self):
        unsafe_values = {
            "qmt_called": True,
            "broker_called": True,
            "real_order_submitted": True,
            "real_trade_executed": True,
            "does_not_modify_strategy_action": False,
            "does_not_modify_holdings": False,
        }
        for field, unsafe_value in unsafe_values.items():
            with self.subTest(field=field, unsafe_value=unsafe_value):
                evaluation = _valid_evaluation()
                summary = evaluation["qmt_research_isolation_summary"]
                summary["safe_fields"][field] = unsafe_value
                summary["safe_evidence_digest"] = v1_closeout_service._canonical_digest(
                    summary["safe_fields"]
                )

                result = contract.build_contract(evaluation=evaluation)

                self.assertFalse(result["passed"])
                self.assertFalse(result["ltg12_research_isolation"]["ready"])

    def test_sensitive_input_is_blocked_and_not_copied_to_output(self):
        evaluation = _valid_evaluation()
        evaluation["api_key"] = "do-not-emit-this-value"

        result = contract.build_contract(evaluation=evaluation)
        rendered = json.dumps(result)

        self.assertFalse(result["passed"])
        self.assertNotIn("do-not-emit-this-value", rendered)
        self.assertNotIn("api_key", rendered)

    def test_task_write_external_and_raw_exposure_flags_are_blocked(self):
        unsafe_values = {
            "creates_task": True,
            "writes_storage": True,
            "external_calls_triggered": True,
            "raw_packet_payloads_exposed": True,
            "raw_account_or_config_exposed": True,
        }
        for field, unsafe_value in unsafe_values.items():
            with self.subTest(field=field):
                evaluation = _valid_evaluation()
                evaluation[field] = unsafe_value

                result = contract.build_contract(evaluation=evaluation)

                self.assertFalse(result["passed"])
                self.assertFalse(result["boundary"]["validated"])

    def test_default_cli_prints_only_and_write_evidence_is_explicit(self):
        evaluation = _valid_evaluation()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            with patch.object(
                contract.v1_closeout_service,
                "build_v1_closeout_evaluation",
                return_value=evaluation,
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = contract.main(["--evidence-root", str(root)])

                self.assertEqual(exit_code, 0)
                self.assertFalse(root.exists())
                self.assertTrue(json.loads(output.getvalue())["passed"])

                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = contract.main(
                        ["--evidence-root", str(root), "--write-evidence"]
                    )

            evidence_path = root / contract.EVIDENCE_FILENAME
            self.assertEqual(exit_code, 0)
            self.assertTrue(evidence_path.is_file())
            written = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(written, json.loads(output.getvalue()))
            self.assertNotIn("evidence_root", written)

    def test_missing_evidence_is_read_only_and_does_not_create_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "missing"

            result = contract.build_contract(evidence_root=root)

            self.assertFalse(result["passed"])
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
