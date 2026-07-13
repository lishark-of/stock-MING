from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import record_release_gate_review_receipt
from scripts import record_remote_ci_review_receipt
from server.services import v1_closeout_service


HEAD_FULL = "e" * 40
RUN_ID = 9001
DIGEST = "sha256:" + "a" * 64


def _remote_args(
    *,
    actions_status: str = "completed",
    actions_conclusion: str = "success",
    no_matching_run_found: bool = False,
) -> argparse.Namespace:
    run_id = 0 if no_matching_run_found else RUN_ID
    completed = actions_status == "completed" and not no_matching_run_found
    failed = actions_conclusion == "failure"
    return argparse.Namespace(
        branch="main",
        head=HEAD_FULL[:8],
        head_full=HEAD_FULL,
        run_id=run_id,
        run_url=(
            ""
            if no_matching_run_found
            else f"https://github.com/lishark-of/stock-MING/actions/runs/{run_id}"
        ),
        workflow_name=record_remote_ci_review_receipt.EXPECTED_WORKFLOW_NAME,
        event="push",
        actions_status=actions_status,
        actions_conclusion=actions_conclusion,
        job_name="push-gate",
        job_conclusion=actions_conclusion,
        artifact_name=(
            f"{record_remote_ci_review_receipt.EXPECTED_ARTIFACT_PREFIX}{run_id}"
            if completed
            else ""
        ),
        artifact_digest=DIGEST if completed else "",
        artifact_digest_unavailable_public_job_page=False,
        artifact_download_status=(
            "downloaded_to_local_temp_for_manual_review" if completed else ""
        ),
        safe_failure_log_excerpt="safe reviewed failure" if failed else "",
        no_matching_run_found=no_matching_run_found,
        lookup_source="manual_actions_page_or_commit_status_review",
        reviewed_at_utc="2026-07-13T00:00:00Z",
        review_authorized=True,
    )


def _build_remote_receipt(**overrides: object) -> dict[str, object]:
    args = _remote_args(**overrides)
    record_remote_ci_review_receipt._validate_args(args)
    return record_remote_ci_review_receipt.build_receipt(args)


def _fact(evaluation: dict[str, object], key: str) -> bool:
    rows = evaluation["production_fact_rows"]
    assert isinstance(rows, list)
    return next(
        bool(row["observed"])
        for row in rows
        if isinstance(row, dict) and row.get("evidence_key") == key
    )


class RemoteCiReceiptObservationTests(unittest.TestCase):
    def test_matching_run_is_observed_without_weakening_green_gate(self) -> None:
        cases = (
            ("green", {}, True, True, True),
            (
                "in_progress",
                {"actions_status": "in_progress", "actions_conclusion": "pending"},
                True,
                False,
                False,
            ),
            (
                "failed",
                {"actions_status": "completed", "actions_conclusion": "failure"},
                True,
                False,
                True,
            ),
            ("no_match", {"no_matching_run_found": True}, False, False, False),
        )

        for name, overrides, observed, verified_green, digest_verified in cases:
            with self.subTest(name=name):
                receipt = _build_remote_receipt(**overrides)
                self.assertIs(
                    receipt["remote_ci_run_observed_for_current_head"], observed
                )
                self.assertIs(
                    receipt["latest_remote_run_verified_green"], verified_green
                )
                self.assertIs(receipt["artifact_digest_verified"], digest_verified)

    def test_v1_remote_ci_fact_requires_current_head_observed_green_and_digest(self) -> None:
        cases = (
            ("current_green", {}, HEAD_FULL, True),
            ("stale_green", {}, "f" * 40, False),
            ("head_unavailable", {}, "", False),
            (
                "in_progress",
                {"actions_status": "in_progress", "actions_conclusion": "pending"},
                HEAD_FULL,
                False,
            ),
            (
                "failed",
                {"actions_status": "completed", "actions_conclusion": "failure"},
                HEAD_FULL,
                False,
            ),
            ("no_match", {"no_matching_run_found": True}, HEAD_FULL, False),
        )

        for name, overrides, expected_head_full, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                evidence_root = Path(directory)
                release_gate = evidence_root / "release_gate"
                release_gate.mkdir(parents=True)
                receipt = _build_remote_receipt(**overrides)
                (release_gate / "remote_ci_review_receipt.json").write_text(
                    json.dumps(receipt), encoding="utf-8"
                )

                evaluation = v1_closeout_service.build_v1_closeout_evaluation(
                    evidence_root=evidence_root,
                    expected_head_full=expected_head_full,
                )

                self.assertIs(_fact(evaluation, "remote_ci_current_head"), expected)
                self.assertFalse(evaluation["github_called"])
                self.assertFalse(evaluation["external_calls_triggered"])

    def test_authoritative_head_reader_supports_linked_worktree_gitfile(self) -> None:
        def run_git(cwd: Path, *args: str) -> str:
            result = subprocess.run(
                ["git", *args],
                cwd=cwd,
                text=True,
                capture_output=True,
                check=True,
            )
            return result.stdout.strip()

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repository"
            worktree = Path(directory) / "linked-worktree"
            repository.mkdir()
            run_git(repository, "init")
            run_git(repository, "config", "user.name", "Remote CI Receipt Test")
            run_git(repository, "config", "user.email", "remote-ci@example.invalid")
            (repository / "tracked.txt").write_text("fixture\n", encoding="utf-8")
            run_git(repository, "add", "tracked.txt")
            run_git(repository, "commit", "-m", "fixture")
            run_git(repository, "worktree", "add", "-b", "fixture-worktree", str(worktree))
            expected_head_full = run_git(worktree, "rev-parse", "HEAD")

            self.assertTrue((worktree / ".git").is_file())
            self.assertEqual(
                v1_closeout_service._read_current_head_full(worktree),
                expected_head_full,
            )

            evidence_root = Path(directory) / "evidence"
            release_gate = evidence_root / "release_gate"
            release_gate.mkdir(parents=True)
            receipt = _build_remote_receipt()
            receipt["head"] = expected_head_full[:8]
            receipt["head_full"] = expected_head_full
            (release_gate / "remote_ci_review_receipt.json").write_text(
                json.dumps(receipt), encoding="utf-8"
            )
            with patch.object(v1_closeout_service, "PROJECT_ROOT", worktree):
                evaluation = v1_closeout_service.build_v1_closeout_evaluation(
                    evidence_root=evidence_root
                )

            self.assertTrue(_fact(evaluation, "remote_ci_current_head"))

    def test_release_review_receipt_keeps_production_release_blocked(self) -> None:
        args = argparse.Namespace(
            branch="main",
            head=HEAD_FULL[:8],
            head_full=HEAD_FULL,
            remote_run_id=str(RUN_ID),
            remote_artifact_digest=DIGEST,
            decision="release_review_complete_strict_closeout_blocked",
            reviewer="local-reviewer",
            manual_review_note_safe="reviewed without release promotion",
            reviewed_at_utc="2026-07-13T00:00:00Z",
            review_authorized=True,
        )
        record_release_gate_review_receipt._validate_args(args)

        receipt = record_release_gate_review_receipt.build_receipt(args)

        self.assertTrue(receipt["release_review_complete"])
        self.assertFalse(receipt["release_gate_complete"])
        self.assertFalse(receipt["strict_closeout_ready"])
        self.assertFalse(receipt["can_close_goal"])
        self.assertFalse(receipt["production_release_complete"])


if __name__ == "__main__":
    unittest.main()
