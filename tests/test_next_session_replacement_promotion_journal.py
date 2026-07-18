from __future__ import annotations

import json
import shutil
import stat
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from server.api import routes_next_session
from server.services import next_session_replacement_promotion_service as promotion


HEAD = "a" * 40
REMOTE_DIGEST = "b" * 64
PROVIDER_SCOPE = "c" * 64
DATASET_VERSION = "d" * 64
DAILY_ROWS_DIGEST = "e" * 64
TRADE_CALENDAR_DIGEST = "f" * 64
RELEASE_EVENT_ID = "1" * 64


def _packet(*, real_close: bool = True, maturity_ready: bool = True) -> dict:
    historical = [
        {
            "x": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
            "price": 10.0 + index,
            "source": "tushare.daily.close",
        }
        for index in range(60)
    ]
    maturity = {
        "status": "ready" if maturity_ready else "partial",
        "has_real_60d_close": real_close,
        "scenario_anchor_count": 2,
        "scenario_anchored_count": 2,
    }
    chart = {
        "status": "ready",
        "is_exact_next_session_packet": True,
        "uses_real_daily_close": real_close,
        "historical_points": historical,
        "reference_lines": [{"name": "latest_close"}],
        "operation_zones": [{"name": "observe"}],
        "chart_maturity": maturity,
        "chart_contract": {
            "cache_only": True,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "frontend_computes_trade_action": False,
            "does_not_modify_action": True,
            "does_not_modify_operation_zones": True,
        },
    }
    packet = {
        "schema_version": "next_session_projection.v1",
        "packet_key": "command_center_next_session_projection_packet",
        "status": "ready_cache_replay",
        "chart_payload": chart,
        "chart_summary": {
            "is_exact_next_session_packet": True,
            "uses_real_daily_close": real_close,
        },
        "next_session_same_packet_signal_capability_coverage": {
            "schema_version": "next_session_same_packet_signal_capability_coverage.v1",
            "status": "same_packet_signal_capability_coverage_ready",
            "same_packet": True,
            "lineage_bound": True,
            "direct_evidence_ready": True,
            "required_feature_group_count": 9,
            "retained_feature_group_count": 9,
            "missing_feature_groups": [],
        },
        "contains_secret": False,
    }
    binding = {
        "head_full": HEAD,
        "source_task_id": "provider-task-current-head",
        "symbol": "000001.SZ",
        "data_date": "20260301",
        "provider_scope_hash": PROVIDER_SCOPE,
        "dataset_version_digest": DATASET_VERSION,
        "daily_rows_digest": DAILY_ROWS_DIGEST,
        "trade_calendar_digest": TRADE_CALENDAR_DIGEST,
    }
    packet["chart_payload"]["symbol"] = "000001.SZ"
    packet["production_replacement_provenance"] = {
        "schema_version": "next_session_production_replacement_provenance.v1",
        "status": "authoritative_provider_dataset_current_head",
        **binding,
        "source_task_status": "success",
        "source_task_digest": promotion._digest(binding),
        "provider_backed": True,
        "authoritative_dataset": True,
        "trade_calendar_validated": True,
        "synthetic_fixture": False,
        "local_preview": False,
    }
    return packet


def _authoritative() -> dict:
    return {
        "ready": True,
        "blockers": [],
        "symbol": "000001.SZ",
        "data_date": "20260301",
        "provider_scope_hash": PROVIDER_SCOPE,
        "dataset_version_digest": DATASET_VERSION,
        "daily_rows_digest": DAILY_ROWS_DIGEST,
        "trade_calendar_digest": TRADE_CALENDAR_DIGEST,
        "validated_trade_date": "20260301",
        "row_count": 60,
    }


def _motion() -> dict:
    rows = []
    for reduced in (False, True):
        for viewport in ("desktop", "laptop", "tablet", "mobile"):
            rows.append(
                {
                    "route": "#next-session-chart",
                    "viewport": viewport,
                    "reduced_motion": reduced,
                    "status": "passed",
                    "visual_qa_complete": True,
                    "performance_trace_complete": True,
                    "long_task_over_50ms_count": 0,
                    "clipped_count": 0,
                }
            )
    return {
        "schema_version": "command_center_3_motion_current_head_evidence_validation.v2",
        "status": "motion_current_head_normal_reduced_pair_verified",
        "expected_head_full": HEAD,
        "motion_current_head_pair_verified": True,
        "frontend_source_digest": "1" * 64,
        "build_identity_digest": "2" * 64,
        "dist_manifest_digest": "3" * 64,
        "package_identity_digest": "4" * 64,
        "normal_run_id": "normal-current",
        "reduced_run_id": "reduced-current",
        "blockers": [],
        "validated_route_rows": {"#next-session-chart": rows},
    }


def _streamlit() -> dict:
    return {
        "schema_version": "streamlit_primary_retirement_validation.v2",
        "status": "streamlit_primary_retirement_direct_evidence_verified",
        "streamlit_primary_retired": True,
        "head_full": HEAD,
        "fallback_disposition": "admin_debug_only_retained",
        "route_count": 6,
        "viewport_count": 2,
        "qa_matrix_count": 12,
        "artifact_set_sha256": "5" * 64,
        "source_contract_digest": "6" * 64,
        "route_matrix_digest": "7" * 64,
        "visual_review_required": True,
        "visual_review_id": "8" * 64,
        "blockers": [],
    }


def _remote(*, semantic_digest: str = REMOTE_DIGEST, run_id: str = "123") -> dict:
    return {
        "head_full": HEAD,
        "rows": [
            {
                "evidence_key": "local_push_gate",
                "ready": False,
                "semantic_digest": "",
                "blockers": ["irrelevant_to_ltg08_remote_binding"],
            },
            {
                "evidence_key": "remote_ci",
                "ready": True,
                "semantic_digest": semantic_digest,
                "blockers": [],
            },
        ],
        "remote_run_id": run_id,
        "remote_artifact_digest": "sha256:" + "9" * 64,
        "ready": False,
        "blockers": ["local_gate_not_required_by_ltg08_fact"],
    }


def _release(*, event_id: str = RELEASE_EVENT_ID) -> dict:
    return {
        "status": "production_release_promoted_current_head",
        "head_full": HEAD,
        "event_id": event_id,
        "release_promotion_current_head": True,
        "blockers": [],
    }


def _blocked_release() -> dict:
    return {
        "status": "production_release_promotion_blocked",
        "head_full": HEAD,
        "event_id": "",
        "release_promotion_current_head": False,
        "blockers": ["production_release_promotion_journal_missing"],
    }


class NextSessionReplacementPromotionJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / ".stock_ming_3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    @contextmanager
    def _evidence(
        self,
        *,
        packet: dict | None = None,
        remote: dict | None = None,
        release: dict | None = None,
    ):
        with ExitStack() as stack:
            stack.enter_context(patch.object(promotion, "_current_head", return_value=HEAD))
            stack.enter_context(patch.object(promotion, "_read_next_packet", return_value=packet or _packet()))
            stack.enter_context(
                patch.object(
                    promotion,
                    "_authoritative_provider_daily_evidence",
                    return_value=_authoritative(),
                )
            )
            stack.enter_context(
                patch.object(
                    promotion.motion_evidence_service,
                    "validate_current_motion_evidence",
                    return_value=_motion(),
                )
            )
            stack.enter_context(
                patch.object(
                    promotion.streamlit_retirement_evidence_service,
                    "validate_streamlit_primary_retirement",
                    return_value=_streamlit(),
                )
            )
            stack.enter_context(
                patch.object(
                    promotion.release_promotion_service,
                    "validate_production_release_promotion",
                    return_value=release or _release(),
                )
            )
            stack.enter_context(
                patch.object(
                    promotion.release_promotion_service,
                    "validate_release_prerequisites",
                    return_value=remote or _remote(),
                )
            )
            yield

    def _approve(self) -> dict:
        preview = promotion._collect_prerequisites(
            self.root,
            expected_head_full=HEAD,
            project_root=Path(self.temp.name),
        )
        review_id = promotion._approval_review_id(
            head_full=HEAD,
            semantic_digest=preview["semantic_digest"],
        )
        return promotion.record_next_session_replacement_approval_ticket(
            evidence_root=self.root,
            expected_head_full=HEAD,
            semantic_digest=preview["semantic_digest"],
            review_id=review_id,
            approved_by_user=True,
            project_root=Path(self.temp.name),
        )

    def test_authoritative_provider_frames_must_match_displayed_closes(self) -> None:
        import pandas as pd

        packet = _packet()
        history = packet["chart_payload"]["historical_points"]
        verified = {
            "ready": True,
            "blockers": [],
            "symbols": ["000001.SZ"],
            "scope_hash": PROVIDER_SCOPE,
            "version_digest": DATASET_VERSION,
            "validated_trade_date": "20260301",
            "frames": {
                "daily": pd.DataFrame(
                    [
                        {
                            "ts_code": "000001.SZ",
                            "trade_date": row["x"].replace("-", ""),
                            "close": row["price"],
                        }
                        for row in history
                    ]
                ),
                "trade_cal": pd.DataFrame(
                    [
                        {"cal_date": row["x"].replace("-", ""), "is_open": 1}
                        for row in history
                    ]
                ),
            },
        }
        with patch(
            "server.services.tushare_production_store.validate_tushare_full_market_production_version",
            return_value=verified,
        ):
            matched = promotion._authoritative_provider_daily_evidence(self.root, packet)
            packet["chart_payload"]["historical_points"][-1]["price"] += 1
            mismatched = promotion._authoritative_provider_daily_evidence(self.root, packet)
        self.assertTrue(matched["ready"])
        self.assertFalse(mismatched["ready"])
        self.assertIn(
            "next_session_displayed_closes_do_not_match_authoritative_provider_rows",
            mismatched["blockers"],
        )

    def test_get_is_zero_write_even_when_all_direct_evidence_is_ready(self) -> None:
        with self._evidence():
            result = promotion.validate_next_session_production_replacement(
                self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn("next_session_replacement_trusted_writer_key_missing", result["blockers"])
        self.assertFalse(self.root.exists())
        self.assertTrue(result["read_only"])
        self.assertFalse(result["writes_storage"])
        self.assertEqual(len(result["approval_semantic_digest"]), 64)
        self.assertEqual(len(result["approval_review_id"]), 64)
        self.assertTrue(result["out_of_band_approval_ticket_required"])

    def test_current_partial_or_short_close_packet_cannot_create_writer(self) -> None:
        packet = _packet(real_close=False, maturity_ready=False)
        packet["chart_payload"]["historical_points"] = packet["chart_payload"]["historical_points"][:5]
        with self._evidence(packet=packet):
            result = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn("next_session_real_close_60_sessions_missing", result["blockers"])
        self.assertIn("next_session_production_maturity_missing", result["blockers"])
        self.assertFalse(self.root.exists())

    def test_caller_cannot_self_seal_with_claimed_evidence(self) -> None:
        payload = {
            "approved_by_user": True,
            "production_replacement_complete": True,
            "next_packet_digest": "f" * 64,
            "motion_pair_digest": "e" * 64,
        }
        with self._evidence():
            result = promotion.promote_next_session_production_replacement(
                payload,
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertIn("explicit_user_next_session_replacement_approval_required", result["blockers"])
        self.assertFalse(result["promotion_written"])
        self.assertFalse(self.root.exists())

    def test_generic_literal_post_cannot_create_key_or_journal_without_out_of_band_ticket(self) -> None:
        with self._evidence():
            result = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn(
            "next_session_replacement_out_of_band_approval_capability_missing",
            result["blockers"],
        )
        self.assertFalse((self.root / promotion.ROOT_NAME).exists())
        self.assertFalse((self.root / promotion.APPROVAL_ROOT_NAME).exists())

    def test_synthetic_packet_and_absent_lineage_cannot_promote(self) -> None:
        packet = _packet()
        packet.pop("production_replacement_provenance")
        with self._evidence(packet=packet):
            result = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn(
            "next_session_authoritative_current_head_lineage_missing_or_invalid",
            result["blockers"],
        )
        self.assertFalse((self.root / promotion.ROOT_NAME).exists())

    def test_symlinked_approval_capability_cannot_authorize_writer(self) -> None:
        self.root.mkdir(mode=0o700)
        outside = Path(self.temp.name) / "approval-outside"
        outside.mkdir(mode=0o700)
        (self.root / promotion.APPROVAL_ROOT_NAME).symlink_to(outside, target_is_directory=True)
        with self._evidence():
            approval = self._approve()
        self.assertFalse(approval["ticket_written"])
        self.assertIn(
            "next_session_replacement_out_of_band_approval_capability_invalid",
            approval["blockers"],
        )
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.root / promotion.ROOT_NAME).exists())

    def test_wrong_mode_approval_capability_cannot_authorize_writer(self) -> None:
        with self._evidence():
            self.assertTrue(self._approve()["ticket_written"])
            approval_root = self.root / promotion.APPROVAL_ROOT_NAME
            approval_root.chmod(0o755)
            result = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn(
            "next_session_replacement_out_of_band_approval_capability_invalid",
            result["blockers"],
        )
        self.assertFalse((self.root / promotion.ROOT_NAME).exists())

    def test_tampered_approval_nonce_is_rejected_before_writer_creation(self) -> None:
        with self._evidence():
            self.assertTrue(self._approve()["ticket_written"])
            ticket_path = (
                self.root
                / promotion.APPROVAL_ROOT_NAME
                / promotion.APPROVAL_TICKET_NAME
            )
            ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
            ticket["nonce_digest"] = "0" * 64
            ticket_path.write_text(json.dumps(ticket, sort_keys=True), encoding="utf-8")
            ticket_path.chmod(0o600)
            result = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn(
            "next_session_replacement_out_of_band_approval_ticket_invalid_or_stale",
            result["blockers"],
        )
        self.assertFalse((self.root / promotion.ROOT_NAME).exists())

    def test_handwritten_remote_receipt_is_insufficient_without_trusted_release_event(self) -> None:
        with self._evidence(release=_blocked_release()):
            result = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn("production_release_promotion_journal_missing", result["blockers"])
        self.assertIn("matching_remote_ci_current_head_missing", result["blockers"])
        self.assertFalse((self.root / promotion.ROOT_NAME).exists())

    def test_stale_head_packet_lineage_cannot_promote(self) -> None:
        packet = _packet()
        packet["production_replacement_provenance"]["head_full"] = "0" * 40
        with self._evidence(packet=packet):
            result = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn(
            "next_session_authoritative_current_head_lineage_missing_or_invalid",
            result["blockers"],
        )

    def test_literal_approval_writes_one_hmac_event_and_replays_idempotently(self) -> None:
        with self._evidence():
            approval = self._approve()
            self.assertTrue(approval["ticket_written"])
            created = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
            replay = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
            validated = promotion.validate_next_session_production_replacement(
                self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertTrue(created["production_replacement_complete"])
        self.assertTrue(created["promotion_written"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertFalse(replay["promotion_written"])
        self.assertTrue(validated["production_replacement_complete"])
        event = self.root / promotion.ROOT_NAME / promotion.EVENTS_NAME / "00000001.json"
        key = self.root / promotion.ROOT_NAME / promotion.TRUST_NAME / promotion.KEY_NAME
        state = self.root / promotion.ROOT_NAME / promotion.TRUST_NAME / promotion.STATE_NAME
        self.assertEqual(stat.S_IMODE(event.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o600)
        self.assertEqual(len(list(event.parent.glob("*.json"))), 1)
        self.assertFalse(
            (self.root / promotion.APPROVAL_ROOT_NAME / promotion.APPROVAL_TICKET_NAME).exists()
        )

    def test_tampered_event_fails_closed(self) -> None:
        with self._evidence():
            self.assertTrue(self._approve()["ticket_written"])
            created = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertTrue(created["production_replacement_complete"])
        event_path = self.root / promotion.ROOT_NAME / promotion.EVENTS_NAME / "00000001.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["remote_run_id"] = "999"
        event_path.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")
        event_path.chmod(0o600)
        with self._evidence():
            result = promotion.validate_next_session_production_replacement(
                self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn("next_session_replacement_event_authentication_failed", result["blockers"])

    def test_tampered_terminal_state_fails_closed(self) -> None:
        with self._evidence():
            self.assertTrue(self._approve()["ticket_written"])
            created = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertTrue(created["production_replacement_complete"])
        state_path = self.root / promotion.ROOT_NAME / promotion.TRUST_NAME / promotion.STATE_NAME
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["sequence_no"] = 2
        state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        state_path.chmod(0o600)
        with self._evidence():
            result = promotion.validate_next_session_production_replacement(
                self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn("next_session_replacement_state_authentication_failed", result["blockers"])

    def test_duplicate_or_malformed_close_rows_cannot_promote(self) -> None:
        packet = _packet()
        packet["chart_payload"]["historical_points"][-1] = dict(
            packet["chart_payload"]["historical_points"][-2]
        )
        with self._evidence(packet=packet):
            result = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn("next_session_real_close_60_sessions_missing", result["blockers"])
        self.assertFalse(self.root.exists())

    def test_symlinked_writer_root_is_rejected_without_external_write(self) -> None:
        self.root.mkdir(mode=0o700)
        outside = Path(self.temp.name) / "outside"
        outside.mkdir(mode=0o700)
        (self.root / promotion.ROOT_NAME).symlink_to(outside, target_is_directory=True)
        with self._evidence():
            self.assertTrue(self._approve()["ticket_written"])
            result = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn("next_session_replacement_trust_directory_invalid", result["blockers"])
        self.assertEqual(list(outside.iterdir()), [])

    def test_changed_remote_evidence_invalidates_previous_event(self) -> None:
        with self._evidence():
            self.assertTrue(self._approve()["ticket_written"])
            created = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertTrue(created["production_replacement_complete"])
        with self._evidence(remote=_remote(semantic_digest="c" * 64, run_id="124")):
            result = promotion.validate_next_session_production_replacement(
                self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn("next_session_replacement_event_evidence_binding_mismatch", result["blockers"])

    def test_rollback_to_older_chain_is_detected_against_current_evidence(self) -> None:
        writer_root = self.root / promotion.ROOT_NAME
        snapshot = Path(self.temp.name) / "old-writer-snapshot"
        with self._evidence():
            self.assertTrue(self._approve()["ticket_written"])
            first = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertTrue(first["production_replacement_complete"])
        shutil.copytree(writer_root, snapshot)
        changed_remote = _remote(semantic_digest="2" * 64, run_id="124")
        changed_release = _release(event_id="3" * 64)
        with self._evidence(remote=changed_remote, release=changed_release):
            self.assertTrue(self._approve()["ticket_written"])
            second = promotion.promote_next_session_production_replacement(
                {"approved_by_user": True},
                evidence_root=self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertTrue(second["production_replacement_complete"])
        self.assertEqual(second["sequence_no"], 2)
        shutil.rmtree(writer_root)
        shutil.copytree(snapshot, writer_root)
        with self._evidence():
            result = promotion.validate_next_session_production_replacement(
                self.root,
                expected_head_full=HEAD,
                project_root=Path(self.temp.name),
            )
        self.assertFalse(result["production_replacement_complete"])
        self.assertIn(
            "next_session_replacement_approval_high_water_rollback_detected",
            result["blockers"],
        )

    def test_routes_expose_read_only_get_and_literal_post_without_task_wrapper(self) -> None:
        blocked = {
            "status": "next_session_production_replacement_blocked",
            "production_replacement_complete": False,
            "blockers": ["blocked"],
        }
        with patch.object(
            routes_next_session.next_session_replacement_promotion_service,
            "validate_next_session_production_replacement",
            return_value=blocked,
        ):
            response = routes_next_session.get_next_session_production_replacement()
        self.assertEqual(response["call_ledger"][0]["request_method"], "GET")
        self.assertFalse(response["call_ledger"][0]["promotion_written"])

        with patch.object(
            routes_next_session.next_session_replacement_promotion_service,
            "promote_next_session_production_replacement",
            return_value={**blocked, "promotion_written": False},
        ) as writer:
            response = routes_next_session.promote_next_session_production_replacement(
                {"approved_by_user": True}
            )
        writer.assert_called_once_with({"approved_by_user": True})
        self.assertEqual(response["call_ledger"][0]["request_method"], "POST")


if __name__ == "__main__":
    unittest.main()
