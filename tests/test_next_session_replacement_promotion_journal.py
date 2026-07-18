from __future__ import annotations

import json
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


def _packet(*, real_close: bool = True, maturity_ready: bool = True) -> dict:
    historical = [
        {
            "x": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
            "price": 10.0 + index,
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
    return {
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
    ):
        with ExitStack() as stack:
            stack.enter_context(patch.object(promotion, "_current_head", return_value=HEAD))
            stack.enter_context(patch.object(promotion, "_read_next_packet", return_value=packet or _packet()))
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
                    "validate_release_prerequisites",
                    return_value=remote or _remote(),
                )
            )
            yield

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

    def test_literal_approval_writes_one_hmac_event_and_replays_idempotently(self) -> None:
        with self._evidence():
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

    def test_tampered_event_fails_closed(self) -> None:
        with self._evidence():
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
