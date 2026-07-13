from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.services import (
    data_health_service,
    migration_status_service,
    packet_service,
    task_service,
    tushare_task_service,
)


def _provider_row(api: str, *, row_count: int, data_date: str | None, status: str = "success") -> dict:
    failure_mode = "none" if status == "success" else "empty_result_or_no_record"
    return {
        "api": api,
        "scope_hash": "provider-scope-hash",
        "scope_hash_short": "provider-scope",
        "payload_hash": "provider-scope-hash",
        "request_params_safe": {"ts_code": "002008.SZ"},
        "row_count": row_count,
        "data_date": data_date,
        "local_fetched_at": "2026-06-30T12:00:00",
        "call_status": status,
        "failure_mode": failure_mode,
        "failure_mode_status": "success_non_empty"
        if status == "success"
        else "validated_empty_not_verified_data",
        "external": True,
        "external_calls_triggered": True,
        "tushare_called": True,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }


class MigrationTushareTaskLedgerSummaryTests(unittest.TestCase):
    def test_refresh_task_call_ledger_rows_include_safe_scope_hash(self):
        class FakeAdapter:
            @staticmethod
            def get_daily(**_params):
                return {
                    "ok": True,
                    "data": [{"ts_code": "002008.SZ", "trade_date": "20260710", "close": 12.3}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_tushare_meta = tushare_task_service.SQLITE_META_PATH
            original_storage_meta = tushare_task_service.storage_service.SQLITE_META_PATH
            original_storage_parquet = tushare_task_service.storage_service.PARQUET_ROOT
            original_task_meta = task_service.SQLITE_META_PATH
            original_tasks = dict(task_service._TASKS)
            tushare_task_service.SQLITE_META_PATH = root / "meta.sqlite"
            tushare_task_service.storage_service.SQLITE_META_PATH = root / "meta.sqlite"
            tushare_task_service.storage_service.PARQUET_ROOT = root / "parquet"
            task_service.SQLITE_META_PATH = root / "meta.sqlite"
            task_service._TASKS.clear()
            self.addCleanup(setattr, tushare_task_service, "SQLITE_META_PATH", original_tushare_meta)
            self.addCleanup(setattr, tushare_task_service.storage_service, "SQLITE_META_PATH", original_storage_meta)
            self.addCleanup(setattr, tushare_task_service.storage_service, "PARQUET_ROOT", original_storage_parquet)
            self.addCleanup(setattr, task_service, "SQLITE_META_PATH", original_task_meta)
            self.addCleanup(task_service._TASKS.clear)
            self.addCleanup(task_service._TASKS.update, original_tasks)

            task = tushare_task_service.run_tushare_refresh_task(
                {
                    "approved_by_user": True,
                    "ts_code": "002008.SZ",
                    "start_date": "20260710",
                    "end_date": "20260710",
                    "apis": ["daily"],
                    "token": "SHOULD_DROP",
                },
                adapter=FakeAdapter,
            )

        ledger = task["call_ledger"]
        self.assertEqual(len(ledger), 1)
        row = ledger[0]
        self.assertEqual(row["api"], "daily")
        self.assertEqual(row["call_status"], "success")
        self.assertRegex(row["scope_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(row["scope_hash_short"], row["scope_hash"][:16])
        self.assertEqual(row["payload_hash"], row["scope_hash"])
        for field in tushare_task_service.CALL_LEDGER_REQUIRED_FIELDS:
            self.assertIn(field, row)
        self.assertNotIn("SHOULD_DROP", json.dumps(task, ensure_ascii=False))

    def test_data_health_summary_surfaces_target_sample_ready_contract(self):
        packet = {
            "status": "success",
            "selected_apis": ["margin_detail"],
            "call_ledger": [_provider_row("margin_detail", row_count=1, data_date="20260710")],
            "provider_target_sample_acceptance_contract": {
                "status": "target_sample_acceptance_ready_for_review",
                "target_sample_acceptance_ready_for_review": True,
                "requested_targets": ["margin_financing"],
                "requested_target_count": 1,
                "ready_target_count": 1,
                "blocking_criterion_count": 0,
            },
            "provider_target_sample_acceptance_rows": [
                {
                    "target": "margin_financing",
                    "requested_for_acceptance": True,
                    "target_sample_acceptance_status": "target_sample_acceptance_ready_for_review",
                    "selected_apis": ["margin_detail"],
                    "non_empty_success_apis": ["margin_detail"],
                    "target_sample_acceptance_blocker_count": 0,
                    "provider_backed_acceptance_done": False,
                    "full_interface_acceptance_done": False,
                    "production_tushare_pipeline_complete": False,
                }
            ],
        }

        summary = data_health_service._local_tushare_refresh_packet_summary(packet)

        self.assertEqual(
            summary["provider_target_sample_acceptance_status"],
            "target_sample_acceptance_ready_for_review",
        )
        self.assertTrue(summary["provider_target_sample_acceptance_ready_for_review"])
        self.assertEqual(summary["provider_target_sample_acceptance_requested_targets"], ["margin_financing"])
        self.assertEqual(summary["provider_target_sample_acceptance_requested_count"], 1)
        self.assertEqual(summary["provider_target_sample_acceptance_ready_count"], 1)
        self.assertEqual(summary["provider_target_sample_acceptance_blocker_count"], 0)
        self.assertEqual(summary["provider_target_sample_acceptance_ready_targets"], ["margin_financing"])
        self.assertEqual(summary["provider_target_sample_acceptance_selected_apis"], ["margin_detail"])
        self.assertFalse(summary["provider_target_sample_acceptance_is_full_interface_acceptance"])
        self.assertFalse(summary["provider_backed_acceptance_done"])
        self.assertFalse(summary["production_tushare_pipeline_complete"])
        self.assertFalse(summary["cache_get_external_calls"])
        self.assertFalse(summary["external_calls_triggered"])
        self.assertFalse(summary["tushare_called"])
        self.assertTrue(summary["does_not_execute_trades"])
        self.assertTrue(summary["does_not_modify_strategy_action"])

    def test_trade_cal_provider_summary_uses_task_ledger_when_packet_was_overwritten(self):
        task_rows = [
            {
                "task_id": "local-new-trade-cal",
                "task_type": "refresh_tushare_facts",
                "status": "success",
                "created_at": "2026-06-30T12:00:00",
                "payload_safe": {
                    "acceptance_mode": "provider_backed_trade_cal_long_window",
                    "apis": ["trade_cal"],
                },
                "call_ledger": [
                    {
                        **_provider_row("trade_cal", row_count=1462, data_date="20260614"),
                        "provider_execution_gate_passed": True,
                    }
                ],
            }
        ]
        overwritten_packet = {
            "local_tushare_refresh_packet_summary": {
                "source_packet_key": "command_center_tushare_refresh_packet",
                "status": "success",
                "available": True,
                "selected_apis": ["trade_cal"],
                "call_ledger_count": 17,
                "trade_cal_call_ledger_count": 17,
                "trade_cal_provider_call_ledger_observed_count": 17,
                "trade_cal_provider_observed_row_count": 902,
                "trade_cal_provider_call_statuses": ["success"],
            },
            "trade_cal_provider_acceptance_promotion_audit": {},
            "trade_cal_provider_freshness_replay_evidence": {},
            "current_evidence_producer_coverage_rows": [],
            "freshness_production_blocker_audit": {},
        }

        with patch.object(task_service, "list_task_statuses", return_value=task_rows), patch.object(
            data_health_service, "read_data_health_timeline_cache", return_value=overwritten_packet
        ):
            summary = migration_status_service._latest_tushare_direct_provider_evidence_summary()

        self.assertEqual(summary["trade_cal_provider_observed_row_count"], 1462)
        self.assertEqual(summary["trade_cal_provider_call_ledger_observed_count"], 17)
        self.assertEqual(summary["task_provider_call_ledger_count"], 1)
        self.assertEqual(summary["task_provider_lookup_source"], "task_service.list_task_statuses_read_only")
        self.assertTrue(summary["trade_cal_provider_call_ledger_evidence_done"])
        self.assertFalse(summary["external_calls_triggered"])
        self.assertFalse(summary["tushare_called_by_lookup"])
        self.assertFalse(summary["deepseek_called"])
        self.assertTrue(summary["does_not_execute_trades"])

    def test_target_sample_handoff_stops_reporting_provider_task_pending_after_task_ledger_exists(self):
        selected_apis = [
            "margin_detail",
            "top_list",
            "top_inst",
            "stk_limit",
            "limit_list_d",
            "limit_cpt_list",
            "cyq_perf",
            "cyq_chips",
            "forecast",
            "fina_indicator",
        ]
        ledger = [
            _provider_row("margin_detail", row_count=1, data_date="20260610"),
            _provider_row("top_list", row_count=0, data_date=None, status="empty"),
            _provider_row("top_inst", row_count=0, data_date=None, status="empty"),
            _provider_row("stk_limit", row_count=1, data_date="20260610"),
            _provider_row("limit_list_d", row_count=0, data_date=None, status="empty"),
            _provider_row("limit_cpt_list", row_count=20, data_date="20260610"),
            _provider_row("cyq_perf", row_count=1, data_date="20260610"),
            _provider_row("cyq_chips", row_count=99, data_date="20260610"),
            _provider_row("forecast", row_count=70, data_date="20250715"),
            _provider_row("fina_indicator", row_count=100, data_date="20260421"),
        ]
        task_rows = [
            {
                "task_id": "local-target-sample",
                "task_type": "refresh_tushare_facts",
                "status": "success",
                "created_at": "2026-06-30T12:01:00",
                "payload_safe": {
                    "acceptance_mode": "provider_target_sample_acceptance",
                    "apis": selected_apis,
                    "target_sample_acceptance_groups": [
                        "margin_financing",
                        "dragon_tiger",
                        "limit_emotion",
                        "chip_distribution",
                        "financial_disclosure",
                    ],
                },
                "call_ledger": ledger,
            }
        ]
        timeline_packet = {
            "counts": {},
            "local_tushare_refresh_packet_summary": {},
            "latest_tushare_provider_target_sample_execution_request": {
                "latest_task_found": True,
                "local_execution_request_ready": True,
                "ready_for_manual_provider_task_submission": True,
                "execution_recipe_scope_hash_matches_latest": True,
                "blocking_row_count": 0,
                "requested_targets": [
                    "margin_financing",
                    "dragon_tiger",
                    "limit_emotion",
                    "chip_distribution",
                    "financial_disclosure",
                ],
                "selected_apis": selected_apis,
                "target_post_task_route": "POST /api/tasks/refresh-tushare-facts",
                "target_task_type": "refresh_tushare_facts",
                "target_acceptance_mode": "provider_target_sample_acceptance",
            },
        }
        overwritten_refresh_packet = {
            "status": "success",
            "selected_apis": ["trade_cal"],
            "call_count": 1,
            "provider_target_sample_acceptance_contract": {
                "status": "target_sample_acceptance_not_requested",
                "target_sample_acceptance_ready_for_review": False,
                "ready_target_count": 0,
            },
            "tushare_durable_evidence_recipe": {
                "status": "tushare_durable_evidence_recipe_ready_provider_pending",
                "local_recipe_ready": True,
            },
            "failure_mode_qa_contract": {
                "status": "failure_mode_qa_ready_provider_acceptance_pending",
                "unsafe_row_count": 0,
            },
            "request_parameter_qa_contract": {
                "status": "request_parameter_qa_ready_provider_acceptance_pending",
            },
            "provider_acceptance_promotion_audit": {"promotion_ready": False},
        }

        with patch.object(task_service, "list_task_statuses", return_value=task_rows), patch.object(
            data_health_service, "read_data_health_timeline_cache", return_value=timeline_packet
        ), patch.object(packet_service, "read_packet", return_value=overwritten_refresh_packet):
            target = migration_status_service._latest_tushare_target_sample_evidence_handoff_summary()
            full = migration_status_service._latest_tushare_full_interface_pipeline_handoff_summary()

        self.assertEqual(target["status"], "target_sample_provider_evidence_visible_review_task_ready")
        self.assertTrue(target["target_sample_provider_task_visible"])
        self.assertEqual(target["target_sample_provider_task_id"], "local-target-sample")
        self.assertEqual(target["target_sample_provider_task_call_ledger_count"], 10)
        self.assertEqual(target["target_sample_provider_task_row_count"], 292)
        self.assertEqual(target["target_sample_provider_task_call_status_counts"], {"success": 7, "empty": 3})
        self.assertEqual(target["provider_call_ledger_count"], 10)
        self.assertEqual(
            target["next_local_step"],
            "POST /api/tasks/tushare-provider-target-sample-failure-window-review",
        )
        self.assertFalse(target["target_sample_failure_window_review_found"])
        self.assertFalse(target["requires_separate_user_approved_provider_task"])
        self.assertFalse(target["target_sample_acceptance_ready_for_review"])
        self.assertFalse(target["production_tushare_pipeline_complete"])
        self.assertFalse(target["external_calls_triggered"])
        self.assertFalse(target["tushare_called"])

        self.assertEqual(
            full["status"],
            "full_interface_pipeline_target_sample_provider_evidence_visible_review_task_ready",
        )
        self.assertTrue(full["target_sample_provider_task_visible"])
        self.assertEqual(full["target_sample_provider_task_call_ledger_count"], 10)
        self.assertEqual(
            full["next_local_step"],
            "POST /api/tasks/tushare-provider-target-sample-failure-window-review",
        )
        self.assertFalse(full["requires_separate_user_approved_provider_task"])
        self.assertFalse(full["production_tushare_pipeline_complete"])

    def test_failure_window_review_receipt_summarizes_existing_provider_task_without_calls(self):
        selected_apis = [
            "margin_detail",
            "top_list",
            "top_inst",
            "stk_limit",
            "limit_list_d",
            "limit_cpt_list",
            "cyq_perf",
            "cyq_chips",
            "forecast",
            "fina_indicator",
        ]
        provider_task = {
            "task_id": "local-target-sample",
            "task_type": "refresh_tushare_facts",
            "status": "success",
            "created_at": "2026-06-30T12:01:00",
            "payload_safe": {
                "acceptance_mode": "provider_target_sample_acceptance",
                "apis": selected_apis,
                "target_sample_acceptance_groups": [
                    "margin_financing",
                    "dragon_tiger",
                    "limit_emotion",
                    "chip_distribution",
                    "financial_disclosure",
                ],
            },
            "call_ledger": [
                _provider_row("margin_detail", row_count=1, data_date="20260610"),
                _provider_row("top_list", row_count=0, data_date=None, status="empty"),
                _provider_row("top_inst", row_count=0, data_date=None, status="empty"),
                _provider_row("stk_limit", row_count=1, data_date="20260610"),
                _provider_row("limit_list_d", row_count=0, data_date=None, status="empty"),
                _provider_row("limit_cpt_list", row_count=20, data_date="20260610"),
                _provider_row("cyq_perf", row_count=1, data_date="20260610"),
                _provider_row("cyq_chips", row_count=99, data_date="20260610"),
                _provider_row("forecast", row_count=70, data_date="20250715"),
                _provider_row("fina_indicator", row_count=100, data_date="20260421"),
            ],
        }

        receipt, rows = tushare_task_service._target_sample_failure_window_review_receipt(
            provider_task=provider_task
        )

        self.assertEqual(receipt["status"], "target_sample_failure_window_review_visible_blockers_recorded")
        self.assertEqual(receipt["provider_task_id"], "local-target-sample")
        self.assertEqual(receipt["provider_call_ledger_count"], 10)
        self.assertEqual(receipt["provider_row_count"], 292)
        self.assertEqual(receipt["provider_success_count"], 7)
        self.assertEqual(receipt["provider_empty_count"], 3)
        self.assertGreater(receipt["blocking_criterion_count"], 0)
        self.assertEqual(len(rows), 6)
        self.assertFalse(receipt["external_calls_triggered"])
        self.assertFalse(receipt["tushare_called"])
        self.assertFalse(receipt["deepseek_called"])
        self.assertFalse(receipt["github_called"])
        self.assertTrue(receipt["does_not_execute_trades"])
        self.assertTrue(receipt["does_not_modify_strategy_action"])

    def test_target_sample_handoff_reads_failure_window_review_receipt(self):
        selected_apis = [
            "margin_detail",
            "top_list",
            "top_inst",
            "stk_limit",
            "limit_list_d",
            "limit_cpt_list",
            "cyq_perf",
            "cyq_chips",
            "forecast",
            "fina_indicator",
        ]
        provider_task = {
            "task_id": "local-target-sample",
            "task_type": "refresh_tushare_facts",
            "status": "success",
            "created_at": "2026-06-30T12:01:00",
            "payload_safe": {
                "acceptance_mode": "provider_target_sample_acceptance",
                "apis": selected_apis,
                "target_sample_acceptance_groups": [
                    "margin_financing",
                    "dragon_tiger",
                    "limit_emotion",
                    "chip_distribution",
                    "financial_disclosure",
                ],
            },
            "call_ledger": [
                _provider_row("margin_detail", row_count=1, data_date="20260610"),
                _provider_row("top_list", row_count=0, data_date=None, status="empty"),
                _provider_row("top_inst", row_count=0, data_date=None, status="empty"),
                _provider_row("stk_limit", row_count=1, data_date="20260610"),
                _provider_row("limit_list_d", row_count=0, data_date=None, status="empty"),
                _provider_row("limit_cpt_list", row_count=20, data_date="20260610"),
                _provider_row("cyq_perf", row_count=1, data_date="20260610"),
                _provider_row("cyq_chips", row_count=99, data_date="20260610"),
                _provider_row("forecast", row_count=70, data_date="20250715"),
                _provider_row("fina_indicator", row_count=100, data_date="20260421"),
            ],
        }
        receipt, rows = tushare_task_service._target_sample_failure_window_review_receipt(
            provider_task=provider_task
        )
        review_task = {
            "task_id": "local-review",
            "task_type": "run_tushare_provider_target_sample_failure_window_review",
            "status": "success",
            "created_at": "2026-06-30T12:02:00",
            "storage_source": "sqlite_meta",
            "payload_safe": {
                "provider_target_sample_failure_window_review_receipt": receipt,
                "provider_target_sample_failure_window_review_rows": rows,
            },
            "call_ledger": receipt["call_ledger"],
        }
        timeline_packet = {
            "counts": {},
            "local_tushare_refresh_packet_summary": {},
            "latest_tushare_provider_target_sample_execution_request": {
                "latest_task_found": True,
                "local_execution_request_ready": True,
                "ready_for_manual_provider_task_submission": True,
                "execution_recipe_scope_hash_matches_latest": True,
                "blocking_row_count": 0,
                "requested_targets": [
                    "margin_financing",
                    "dragon_tiger",
                    "limit_emotion",
                    "chip_distribution",
                    "financial_disclosure",
                ],
                "selected_apis": selected_apis,
                "target_post_task_route": "POST /api/tasks/refresh-tushare-facts",
                "target_task_type": "refresh_tushare_facts",
                "target_acceptance_mode": "provider_target_sample_acceptance",
            },
        }
        overwritten_refresh_packet = {
            "status": "success",
            "selected_apis": ["trade_cal"],
            "provider_target_sample_acceptance_contract": {"status": "target_sample_acceptance_not_requested"},
            "tushare_durable_evidence_recipe": {"local_recipe_ready": True},
            "failure_mode_qa_contract": {"status": "failure_mode_qa_ready_provider_acceptance_pending"},
            "request_parameter_qa_contract": {"status": "request_parameter_qa_ready_provider_acceptance_pending"},
            "provider_acceptance_promotion_audit": {"promotion_ready": False},
        }

        with patch.object(task_service, "list_task_statuses", return_value=[review_task, provider_task]), patch.object(
            data_health_service, "read_data_health_timeline_cache", return_value=timeline_packet
        ), patch.object(packet_service, "read_packet", return_value=overwritten_refresh_packet):
            target = migration_status_service._latest_tushare_target_sample_evidence_handoff_summary()
            full = migration_status_service._latest_tushare_full_interface_pipeline_handoff_summary()

        self.assertEqual(target["status"], "target_sample_failure_window_review_visible_followup_needed")
        self.assertTrue(target["target_sample_failure_window_review_found"])
        self.assertEqual(target["target_sample_failure_window_review_task_id"], "local-review")
        self.assertGreater(target["target_sample_failure_window_review_blocker_count"], 0)
        self.assertEqual(target["next_local_step"], "add_target_sample_window_context_or_collect_failure_mode_evidence")
        self.assertFalse(target["external_calls_triggered"])
        self.assertFalse(target["tushare_called"])
        self.assertEqual(
            full["status"],
            "full_interface_pipeline_target_sample_failure_window_review_visible_followup_needed",
        )
        self.assertFalse(full["production_tushare_pipeline_complete"])

    def test_next_action_queue_uses_review_blocker_after_target_sample_provider_task(self):
        p2_action = next(
            row
            for row in migration_status_service.LTG_NEXT_ACCEPTANCE_ACTION_QUEUE
            if row["queue_id"] == "p2_tushare_target_sample_acceptance"
        )
        local_step_rows = [
            {
                "phase_key": "target_sample_execution_request_ticket",
                "task_type": "run_tushare_provider_target_sample_execution_request",
                "route": "POST /api/tasks/tushare-provider-target-sample-execution-request",
                "receipt_visible": True,
                "local_ready": True,
                "local_queue_required": True,
                "receipt_durable_in_sqlite": True,
                "receipt_memory_only": False,
                "latest_task_id": "local-request",
                "receipt_status": "target_sample_execution_request_ready_manual_provider_task_pending",
                "receipt_blocker_count": 0,
            }
        ]
        target_handoff = {
            "target_sample_provider_task_visible": True,
            "target_sample_acceptance_ready_for_review": False,
            "target_sample_failure_window_review_found": False,
            "next_local_step": "POST /api/tasks/tushare-provider-target-sample-failure-window-review",
        }
        full_handoff = {
            "target_sample_provider_task_visible": True,
            "next_local_step": "POST /api/tasks/tushare-provider-target-sample-failure-window-review",
        }

        with patch.object(migration_status_service, "LTG_NEXT_ACCEPTANCE_ACTION_QUEUE", [p2_action]), patch.object(
            migration_status_service, "_build_ltg_next_action_local_step_rows", return_value=local_step_rows
        ), patch.object(
            migration_status_service,
            "_latest_tushare_target_sample_execution_recipe_preview",
            return_value={},
        ), patch.object(
            migration_status_service,
            "_latest_tushare_target_sample_evidence_handoff_summary",
            return_value=target_handoff,
        ), patch.object(
            migration_status_service,
            "_latest_tushare_full_interface_pipeline_handoff_summary",
            return_value=full_handoff,
        ):
            rows = migration_status_service._build_ltg_next_acceptance_action_rows(
                [
                    {
                        "id": "LTG-02",
                        "completion_estimate": "35%-45%",
                        "completion_bucket": "real_validation_required",
                        "observed_stage_scope_pending_count": 9,
                        "observed_stage_scope_direct_evidence_count": 1,
                    }
                ]
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["queue_id"], "p2_tushare_target_sample_acceptance")
        self.assertEqual(rows[0]["local_receipt_status"], "local_provider_evidence_visible_review_task_ready")
        self.assertEqual(
            rows[0]["next_local_step"],
            "POST /api/tasks/tushare-provider-target-sample-failure-window-review",
        )
        self.assertEqual(
            rows[0]["supporting_tushare_target_sample_evidence_handoff"],
            target_handoff,
        )
        self.assertFalse(rows[0]["external_calls_triggered"])
        self.assertFalse(rows[0]["tushare_called"])


if __name__ == "__main__":
    unittest.main()
