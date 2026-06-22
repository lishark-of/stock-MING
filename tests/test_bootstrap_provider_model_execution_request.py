from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.services import task_service
from server.services.task_service import clear_task_statuses_for_tests


class BootstrapProviderModelExecutionRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self._tmp = tempfile.TemporaryDirectory()
        self.meta_store = Path(self._tmp.name) / "meta.sqlite"
        clear_task_statuses_for_tests()

    def tearDown(self) -> None:
        clear_task_statuses_for_tests()
        self._tmp.cleanup()

    def _with_meta_store(self):
        return patch.object(task_service, "SQLITE_META_PATH", self.meta_store)

    def _with_bootstrap_env(self):
        return patch.dict(
            os.environ,
            {
                "COMMAND_CENTER_BOOTSTRAP_MODE": "live_light",
                "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN": "true",
                "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN": "true",
                "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT": "2",
                "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL": "unit-test-live-pro",
                "TUSHARE_TOKEN": "DROP_TS",
                "DEEPSEEK_API_KEY": "DROP_DS",
            },
            clear=False,
        )

    def _task_from_response(self, response):
        body = response.json()
        self.assertTrue(body["ok"])
        return body["data"]["task"]

    def test_execution_request_binds_latest_dry_run_without_provider_model_call(self) -> None:
        with self._with_meta_store(), self._with_bootstrap_env():
            catalog_entry = next(
                item
                for item in task_service.TASK_CATALOG
                if item["task_type"] == "command_center_live_bootstrap_provider_model_execution_request"
            )
            self.assertEqual(catalog_entry["route"], "POST /api/bootstrap/provider-model-execution-request")
            self.assertTrue(catalog_entry["button_gated"])
            self.assertTrue(catalog_entry["execution_request_only"])
            self.assertFalse(catalog_entry["creates_provider_model_task"])

            dry_run_response = self.client.post(
                "/api/bootstrap/provider-model-acceptance-dry-run",
                json={
                    "source": "unit-test",
                    "approved_by_user": True,
                    "symbols": ["000001.SZ", "600000.SH", "300750.SZ"],
                    "include_tushare": True,
                    "include_deepseek": True,
                    "apis": ["trade_cal", "daily", "moneyflow", "fina_indicator"],
                    "api_key": "SHOULD_DROP",
                    "token": "SHOULD_DROP",
                },
            )
            self.assertEqual(dry_run_response.status_code, 200)
            dry_run_task = self._task_from_response(dry_run_response)
            self.assertEqual(dry_run_task["status"], "success")
            dry_payload = dry_run_task["payload_safe"]
            dry_summary = dry_payload["acceptance_dry_run_summary"]
            self.assertEqual(dry_payload["symbols"], ["000001.SZ", "600000.SH"])
            self.assertTrue(dry_payload["truncated_by_symbol_limit"])
            self.assertEqual(dry_payload["selected_apis"], ["trade_cal", "daily", "moneyflow"])
            self.assertEqual(dry_payload["ignored_apis"], ["fina_indicator"])
            self.assertTrue(dry_summary["ready_for_user_approved_real_acceptance"])
            self.assertEqual(dry_summary["credential_missing_provider_count"], 0)
            scope_hash = dry_summary["acceptance_scope_hash"]
            self.assertRegex(scope_hash, r"^[0-9a-f]{64}$")
            self.assertNotIn("SHOULD_DROP", json.dumps(dry_run_task, ensure_ascii=False))
            self.assertNotIn("DROP_TS", json.dumps(dry_run_task, ensure_ascii=False))
            self.assertNotIn("DROP_DS", json.dumps(dry_run_task, ensure_ascii=False))

            execution_response = self.client.post(
                "/api/bootstrap/provider-model-execution-request",
                json={
                    "source": "unit-test",
                    "requested_by": "operator",
                    "confirmed_by_user": True,
                    "acceptance_scope_hash": scope_hash,
                    "selected_apis": ["trade_cal", "daily", "moneyflow"],
                    "include_tushare": True,
                    "include_deepseek": True,
                    "api_key": "SHOULD_DROP",
                    "token": "SHOULD_DROP",
                },
            )
            self.assertEqual(execution_response.status_code, 200)
            execution_task = self._task_from_response(execution_response)
            self.assertEqual(
                execution_task["task_type"],
                "command_center_live_bootstrap_provider_model_execution_request",
            )
            self.assertEqual(execution_task["status"], "success")
            self.assertEqual(
                execution_task["current_step"],
                "provider_model_execution_request_ready_manual_provider_model_task_pending",
            )
            self.assertEqual(
                execution_task["output_packet_key"],
                "command_center_live_bootstrap_provider_model_execution_request_packet",
            )

            payload = execution_task["payload_safe"]
            receipt = payload["execution_request_receipt"]
            rows = {row["criterion"]: row for row in payload["execution_request_rows"]}
            self.assertTrue(payload["execution_request_only"])
            self.assertFalse(payload["provider_model_task_created"])
            self.assertFalse(payload["provider_model_task_dispatched"])
            self.assertEqual(receipt["status"], "execution_request_ready_manual_provider_model_task_pending")
            self.assertEqual(receipt["latest_acceptance_dry_run_task_id"], dry_run_task["task_id"])
            self.assertEqual(receipt["acceptance_scope_hash"], scope_hash)
            self.assertTrue(receipt["requested_acceptance_scope_hash_matches_latest"])
            self.assertTrue(receipt["user_confirmed"])
            self.assertTrue(receipt["credential_preflight_ready"])
            self.assertTrue(receipt["local_execution_request_ready"])
            self.assertTrue(receipt["ready_for_manual_provider_model_task_submission"])
            self.assertFalse(receipt["provider_model_task_created"])
            self.assertFalse(receipt["provider_model_task_dispatched"])
            self.assertFalse(receipt["provider_execution_implemented"])
            self.assertFalse(receipt["model_execution_implemented"])
            self.assertFalse(receipt["production_live_light_complete"])
            self.assertEqual(receipt["local_blocker_count"], 0)
            self.assertGreater(receipt["production_blocker_count"], 0)
            self.assertTrue(rows["latest_acceptance_dry_run_receipt_visible"]["passed"])
            self.assertTrue(rows["acceptance_scope_hash_bound"]["passed"])
            self.assertTrue(rows["explicit_user_confirmation_recorded"]["passed"])
            self.assertTrue(rows["provider_model_task_not_created"]["production_blocker"])
            self.assertTrue(rows["no_provider_model_trade_secret_boundary"]["passed"])

            ledger = execution_task["call_ledger"][0]
            self.assertEqual(ledger["api"], "local_live_light_provider_model_execution_request")
            self.assertEqual(ledger["call_status"], "local_execution_request_ready_no_external_call")
            self.assertFalse(ledger["external"])
            self.assertFalse(ledger["tushare_called"])
            self.assertFalse(ledger["deepseek_called"])
            self.assertFalse(ledger["github_called"])
            self.assertFalse(execution_task["external_calls_triggered"])
            self.assertFalse(execution_task["tushare_called"])
            self.assertFalse(execution_task["deepseek_called"])
            self.assertFalse(execution_task["github_called"])
            self.assertTrue(execution_task["does_not_execute_trades"])
            self.assertTrue(execution_task["does_not_modify_strategy_action"])
            rendered_task = json.dumps(execution_task, ensure_ascii=False)
            self.assertNotIn("SHOULD_DROP", rendered_task)
            self.assertNotIn("DROP_TS", rendered_task)
            self.assertNotIn("DROP_DS", rendered_task)

            mismatch_response = self.client.post(
                "/api/bootstrap/provider-model-execution-request",
                json={
                    "source": "unit-test",
                    "confirmed_by_user": True,
                    "acceptance_scope_hash": "0" * 64,
                    "selected_apis": ["trade_cal"],
                    "include_tushare": True,
                    "token": "SHOULD_DROP",
                },
            )
            self.assertEqual(mismatch_response.status_code, 200)
            mismatch_task = self._task_from_response(mismatch_response)
            mismatch_payload = mismatch_task["payload_safe"]
            mismatch_receipt = mismatch_payload["execution_request_receipt"]
            self.assertEqual(
                mismatch_receipt["status"],
                "execution_request_blocked_scope_hash_mismatch",
            )
            self.assertFalse(mismatch_receipt["local_execution_request_ready"])
            self.assertFalse(mismatch_receipt["requested_acceptance_scope_hash_matches_latest"])
            self.assertIn("acceptance_scope_hash_bound", mismatch_receipt["blocking_criteria"])
            self.assertFalse(mismatch_task["external_calls_triggered"])
            self.assertFalse(mismatch_task["tushare_called"])
            self.assertFalse(mismatch_task["deepseek_called"])
            self.assertFalse(mismatch_task["github_called"])
            self.assertNotIn("SHOULD_DROP", json.dumps(mismatch_task, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
