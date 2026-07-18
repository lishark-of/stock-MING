from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import record_release_gate_review_receipt
from scripts import record_remote_ci_review_receipt
from scripts import record_secret_artifact_allowlist_review_receipt
from server.services import audit_service


HEAD_FULL = "d" * 40
RUN_ID = 81234567890
ARTIFACT_DIGEST = "sha256:" + "b" * 64


def _current_head() -> dict[str, object]:
    return {
        "head": HEAD_FULL[:7],
        "head_full": HEAD_FULL,
        "branch": "main",
    }


def _remote_receipt() -> dict[str, object]:
    args = argparse.Namespace(
        branch="main",
        head=HEAD_FULL[:8],
        head_full=HEAD_FULL,
        run_id=RUN_ID,
        run_url=f"https://github.com/lishark-of/stock-MING/actions/runs/{RUN_ID}",
        workflow_name=record_remote_ci_review_receipt.EXPECTED_WORKFLOW_NAME,
        event="push",
        actions_status="completed",
        actions_conclusion="success",
        job_name="push-gate",
        job_conclusion="success",
        artifact_name=f"command-center-3-push-gate-evidence-{RUN_ID}",
        artifact_digest=ARTIFACT_DIGEST,
        artifact_digest_unavailable_public_job_page=False,
        artifact_download_status="",
        safe_failure_log_excerpt="",
        no_matching_run_found=False,
        lookup_source="manual_actions_page_or_commit_status_review",
        reviewed_at_utc="2026-07-18T00:00:00Z",
        review_authorized=True,
    )
    return record_remote_ci_review_receipt.build_receipt(args)


def _allowlist_receipt() -> dict[str, object]:
    args = argparse.Namespace(
        branch="main",
        head=HEAD_FULL[:8],
        head_full=HEAD_FULL,
        reviewer="local-reviewer",
        high_risk_secret_scan_status="clean",
        secret_keyword_review_status="reviewed_no_high_risk_values",
        generated_artifact_scan_status="clean_or_allowed_assets_only",
        manual_review_note_safe="reviewed",
        reviewed_at_utc="2026-07-18T00:01:00Z",
        review_authorized=True,
    )
    return record_secret_artifact_allowlist_review_receipt.build_receipt(args)


def _release_review_receipt() -> dict[str, object]:
    args = argparse.Namespace(
        branch="main",
        head=HEAD_FULL[:8],
        head_full=HEAD_FULL,
        remote_run_id=str(RUN_ID),
        remote_artifact_digest=ARTIFACT_DIGEST,
        decision="release_review_complete_strict_closeout_blocked",
        reviewer="local-reviewer",
        manual_review_note_safe="reviewed",
        reviewed_at_utc="2026-07-18T00:02:00Z",
        review_authorized=True,
    )
    return record_release_gate_review_receipt.build_receipt(args)


class ReleaseEvidenceBindingTests(unittest.TestCase):
    def _write(self, directory: str, name: str, payload: dict[str, object]) -> Path:
        path = Path(directory) / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_remote_reader_requires_full_and_short_head_and_exact_run_artifact(self) -> None:
        attacks = (
            {"head_full": "f" * 40},
            {"head": "f" * 8},
            {"run_url": f"https://github.com/lishark-of/stock-MING/actions/runs/{RUN_ID + 1}"},
            {"artifact_name": f"command-center-3-push-gate-evidence-{RUN_ID + 1}"},
            {"artifact_digest": "sha256:" + "b" * 32},
            {"receipt_writer": "manual.json"},
        )
        for changes in attacks:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                receipt = _remote_receipt()
                receipt.update(changes)
                path = self._write(directory, "remote.json", receipt)
                with (
                    patch.object(audit_service, "REMOTE_CI_REVIEW_RECEIPT_PATH", path),
                    patch.object(audit_service, "_current_git_head_summary", return_value=_current_head()),
                ):
                    result = audit_service._read_remote_ci_review_receipt()
                self.assertFalse(result["remote_ci_review_ready"])
                self.assertFalse(result["latest_remote_run_verified_green"])

    def test_remote_reader_accepts_formal_eight_char_head_with_seven_char_display_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, "remote.json", _remote_receipt())
            with (
                patch.object(audit_service, "REMOTE_CI_REVIEW_RECEIPT_PATH", path),
                patch.object(audit_service, "_current_git_head_summary", return_value=_current_head()),
            ):
                result = audit_service._read_remote_ci_review_receipt()

        self.assertEqual(result["current_head"], HEAD_FULL[:7])
        self.assertEqual(result["head"], HEAD_FULL[:8])
        self.assertTrue(result["head_matches_current"])
        self.assertTrue(result["remote_ci_review_ready"])
        self.assertTrue(result["latest_remote_run_verified_green"])

    def test_allowlist_and_release_review_reject_short_head_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            allowlist = _allowlist_receipt()
            allowlist["head_full"] = "f" * 40
            allowlist_path = self._write(directory, "allowlist.json", allowlist)
            with (
                patch.object(
                    audit_service,
                    "SECRET_ARTIFACT_ALLOWLIST_REVIEW_RECEIPT_PATH",
                    allowlist_path,
                ),
                patch.object(audit_service, "_current_git_head_summary", return_value=_current_head()),
            ):
                allowlist_result = audit_service._read_secret_artifact_allowlist_review_receipt()
            self.assertFalse(allowlist_result["periodic_allowlist_review_ready"])
            self.assertFalse(allowlist_result["head_matches_current"])

            release_review = _release_review_receipt()
            release_review["head_full"] = "f" * 40
            release_path = self._write(directory, "release.json", release_review)
            remote_result = {
                "head_matches_current": True,
                "remote_ci_review_ready": True,
                "latest_remote_run_verified_green": True,
                "run_id": RUN_ID,
                "artifact_digest": ARTIFACT_DIGEST,
            }
            verified_allowlist = {
                "head_matches_current": True,
                "periodic_allowlist_review_ready": True,
            }
            with (
                patch.object(audit_service, "RELEASE_GATE_REVIEW_RECEIPT_PATH", release_path),
                patch.object(audit_service, "_current_git_head_summary", return_value=_current_head()),
            ):
                release_result = audit_service._read_release_gate_review_receipt(
                    remote_result,
                    verified_allowlist,
                )
            self.assertFalse(release_result["release_review_complete"])
            self.assertFalse(release_result["head_matches_current"])


if __name__ == "__main__":
    unittest.main()
