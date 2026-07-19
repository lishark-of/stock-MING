from __future__ import annotations

import argparse
import hashlib
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
LOCAL_RECEIPT_BYTES = b'{"artifact_fixture":true}\n'


def _artifact_import_receipt(*, head_full: str = HEAD_FULL) -> dict[str, object]:
    local_sha = hashlib.sha256(LOCAL_RECEIPT_BYTES).hexdigest()
    return {
        "schema_version": "command_center_3_remote_push_gate_artifact_import_receipt.v1",
        "status": "remote_push_gate_artifact_import_verified",
        "scope": "offline_downloaded_push_gate_artifact_byte_import",
        "imported_at_utc": "2026-07-13T00:00:00Z",
        "receipt_writer": "scripts/import_remote_push_gate_artifact.py",
        "head_full": head_full,
        "run_id": RUN_ID,
        "artifact_id": 71,
        "artifact_name": f"command-center-3-push-gate-evidence-{RUN_ID}",
        "artifact_size_bytes": 100,
        "artifact_metadata_digest": "1" * 64,
        "artifact_digest": DIGEST,
        "artifact_archive_sha256": DIGEST,
        "artifact_archive_size_bytes": 100,
        "artifact_digest_matches_metadata": True,
        "artifact_size_matches_metadata": True,
        "entry_manifest_digest": "2" * 64,
        "entry_names": [
            "command-center-3-local-push-gate-run-receipt.json",
            "command-center-3-push-gate-report.md",
            "command-center-3-push-gate.log",
        ],
        "embedded_local_gate_receipt_sha256": local_sha,
        "embedded_local_gate_receipt_size_bytes": len(LOCAL_RECEIPT_BYTES),
        "imported_local_gate_receipt_sha256": local_sha,
        "imported_local_gate_receipt_size_bytes": len(LOCAL_RECEIPT_BYTES),
        "local_receipt_relative_path": ".stock_ming_3/release_gate/local_push_gate_run_receipt.json",
        "artifact_receipt_bytes_identical": True,
        "safe_archive_verified": True,
        "local_gate_schema_verified": True,
        "writes_local_receipt": True,
        "network_calls_triggered": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def _write_import_binding(
    release_gate: Path,
    *,
    head_full: str = HEAD_FULL,
) -> None:
    (release_gate / "local_push_gate_run_receipt.json").write_bytes(LOCAL_RECEIPT_BYTES)
    (release_gate / "remote_push_gate_artifact_import_receipt.json").write_text(
        json.dumps(_artifact_import_receipt(head_full=head_full)), encoding="utf-8"
    )


def _remote_args(
    *,
    actions_status: str = "completed",
    actions_conclusion: str = "success",
    no_matching_run_found: bool = False,
    head_full: str = HEAD_FULL,
) -> argparse.Namespace:
    run_id = 0 if no_matching_run_found else RUN_ID
    completed = actions_status == "completed" and not no_matching_run_found
    failed = actions_conclusion == "failure"
    fixture_dir = Path(tempfile.mkdtemp())
    local_receipt = fixture_dir / "local.json"
    import_receipt = fixture_dir / "import.json"
    local_receipt.write_bytes(LOCAL_RECEIPT_BYTES)
    import_receipt.write_text(
        json.dumps(_artifact_import_receipt(head_full=head_full)), encoding="utf-8"
    )
    return argparse.Namespace(
        branch="main",
        head=head_full[:8],
        head_full=head_full,
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
        artifact_import_receipt=str(import_receipt) if completed and not failed else "",
        imported_local_gate_receipt=str(local_receipt) if completed and not failed else "",
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
                if receipt.get("artifact_import_verified") is True:
                    _write_import_binding(release_gate)

                evaluation = v1_closeout_service.build_v1_closeout_evaluation(
                    evidence_root=evidence_root,
                    expected_head_full=expected_head_full,
                )

                self.assertIs(_fact(evaluation, "remote_ci_current_head"), expected)
                self.assertFalse(evaluation["github_called"])
                self.assertFalse(evaluation["external_calls_triggered"])

    def test_v1_remote_ci_fact_rejects_forged_flags_and_mismatched_artifact_identity(self) -> None:
        cases = (
            ("wrong_artifact_run", {"artifact_name": "command-center-3-push-gate-evidence-9002"}),
            ("wrong_run_url", {"run_url": "https://github.com/lishark-of/stock-MING/actions/runs/9002"}),
            ("short_digest", {"artifact_digest": "sha256:" + "a" * 32}),
            ("wrong_writer", {"receipt_writer": "manual.json"}),
            ("unknown_field", {"caller_asserted_green": True}),
        )
        for name, changes in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                evidence_root = Path(directory)
                release_gate = evidence_root / "release_gate"
                release_gate.mkdir(parents=True)
                receipt = _build_remote_receipt()
                receipt.update(changes)
                (release_gate / "remote_ci_review_receipt.json").write_text(
                    json.dumps(receipt), encoding="utf-8"
                )
                _write_import_binding(release_gate)

                evaluation = v1_closeout_service.build_v1_closeout_evaluation(
                    evidence_root=evidence_root,
                    expected_head_full=HEAD_FULL,
                )

                self.assertFalse(_fact(evaluation, "remote_ci_current_head"))
                self.assertFalse(evaluation["github_called"])
                self.assertFalse(evaluation["external_calls_triggered"])

    def test_formal_remote_ci_validation_accepts_reviewed_local_artifact_download(self) -> None:
        receipt = _build_remote_receipt()
        validation = v1_closeout_service.release_promotion_service._validate_remote_ci(
            receipt,
            HEAD_FULL,
            _artifact_import_receipt(),
            LOCAL_RECEIPT_BYTES,
        )
        self.assertTrue(validation["ready"])
        self.assertEqual(validation["blockers"], [])

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
            receipt = _build_remote_receipt(head_full=expected_head_full)
            (release_gate / "remote_ci_review_receipt.json").write_text(
                json.dumps(receipt), encoding="utf-8"
            )
            _write_import_binding(release_gate, head_full=expected_head_full)
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
