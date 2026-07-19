from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import import_remote_push_gate_artifact as artifact_import
from scripts import record_remote_ci_review_receipt
from server.services import audit_service, release_promotion_service


HEAD = "d" * 40
RUN_ID = 9001


def _local_receipt() -> dict:
    return {
        "schema_version": audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION,
        "status": "local_push_gate_passed_current_head",
        "scope": "ignored_local_push_gate_run_receipt_no_push_no_github_api",
        "generated_at_utc": "2026-07-19T00:00:00Z",
        "branch": "main",
        "head": HEAD[:8],
        "head_full": HEAD,
        "origin_ahead_count": "0",
        "report_path": "/runner/temp/command-center-3-push-gate-report.md",
        "checks": sorted(audit_service.LOCAL_PUSH_GATE_REQUIRED_CHECKS),
        "did_not_push": True,
        "git_add_dot_used": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "local_gate_pass_is_not_ci_status": True,
        "remote_actions_status_known": False,
        "latest_remote_run_verified_green": False,
        "explicit_user_push_confirmation_before_push": False,
        "push_confirmation_state": "not_requested_no_push",
        "release_claim_decision": "blocked_remote_ci_unverified",
        "remote_ci_status_note": (
            "local push gate pass is not remote CI green; inspect matching remote "
            "Actions run before release."
        ),
    }


class RemotePushGateArtifactImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "artifact.zip"
        self.metadata = self.root / "artifact.json"
        self.local_output = (
            self.root / ".stock_ming_3" / "release_gate" / "local_push_gate_run_receipt.json"
        )
        self.import_output = (
            self.root
            / ".stock_ming_3"
            / "release_gate"
            / "remote_push_gate_artifact_import_receipt.json"
        )
        self.embedded_bytes = (
            json.dumps(_local_receipt(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        self._write_archive()

    def _write_archive(self, *, extra_name: str = "", local_bytes: bytes | None = None) -> None:
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("command-center-3-push-gate.log", b"PASS\n")
            archive.writestr("command-center-3-push-gate-report.md", b"# PASS\n")
            archive.writestr(
                artifact_import.EMBEDDED_RECEIPT_NAME,
                self.embedded_bytes if local_bytes is None else local_bytes,
            )
            if extra_name:
                archive.writestr(extra_name, b"unexpected\n")
        archive_bytes = self.archive.read_bytes()
        self.digest = "sha256:" + hashlib.sha256(archive_bytes).hexdigest()
        self.metadata.write_text(
            json.dumps(
                {
                    "id": 71,
                    "name": f"command-center-3-push-gate-evidence-{RUN_ID}",
                    "size_in_bytes": len(archive_bytes),
                    "expired": False,
                    "digest": self.digest,
                    "workflow_run": {
                        "id": RUN_ID,
                        "head_branch": "main",
                        "head_sha": HEAD,
                    },
                }
            ),
            encoding="utf-8",
        )

    def _args(self) -> argparse.Namespace:
        return argparse.Namespace(
            artifact_zip=str(self.archive),
            artifact_metadata=str(self.metadata),
            head_full=HEAD,
            run_id=RUN_ID,
            local_receipt_output=str(self.local_output),
            output=str(self.import_output),
        )

    def _import(self) -> dict:
        with patch.object(artifact_import, "PROJECT_ROOT", self.root.resolve()):
            return artifact_import.import_artifact(self._args())

    def test_verified_import_preserves_exact_embedded_bytes_and_binds_remote_v2(self) -> None:
        self._import()
        imported = json.loads(self.import_output.read_text(encoding="utf-8"))
        self.assertEqual(self.local_output.read_bytes(), self.embedded_bytes)
        self.assertTrue(imported["artifact_receipt_bytes_identical"])
        self.assertEqual(imported["artifact_digest"], self.digest)

        remote_args = argparse.Namespace(
            branch="main",
            head=HEAD[:8],
            head_full=HEAD,
            run_id=RUN_ID,
            run_url=f"https://github.com/lishark-of/stock-MING/actions/runs/{RUN_ID}",
            workflow_name=record_remote_ci_review_receipt.EXPECTED_WORKFLOW_NAME,
            event="push",
            actions_status="completed",
            actions_conclusion="success",
            job_name="push-gate",
            job_conclusion="success",
            artifact_name=f"command-center-3-push-gate-evidence-{RUN_ID}",
            artifact_digest=self.digest,
            artifact_digest_unavailable_public_job_page=False,
            artifact_download_status="downloaded_to_local_temp_for_manual_review",
            artifact_import_receipt=str(self.import_output),
            imported_local_gate_receipt=str(self.local_output),
            safe_failure_log_excerpt="",
            no_matching_run_found=False,
            lookup_source="manual_actions_page_or_commit_status_review",
            reviewed_at_utc="2026-07-19T00:01:00Z",
            review_authorized=True,
        )
        record_remote_ci_review_receipt._validate_args(remote_args)
        remote = record_remote_ci_review_receipt.build_receipt(remote_args)
        validation = release_promotion_service._validate_remote_ci(
            remote,
            HEAD,
            json.loads(self.import_output.read_text(encoding="utf-8")),
            self.local_output.read_bytes(),
        )
        self.assertTrue(validation["ready"], validation)
        self.assertTrue(validation["artifact_import_ready"])

        legacy = dict(remote)
        legacy["schema_version"] = "command_center_3_remote_ci_review_receipt.v1"
        for field in (
            "artifact_id",
            "artifact_size_bytes",
            "artifact_archive_sha256",
            "artifact_import_receipt_digest",
            "embedded_local_gate_receipt_sha256",
            "imported_local_gate_receipt_sha256",
            "artifact_receipt_bytes_identical",
            "artifact_import_verified",
        ):
            legacy.pop(field)
        legacy_validation = release_promotion_service._validate_remote_ci(
            legacy,
            HEAD,
            imported,
            self.local_output.read_bytes(),
        )
        self.assertFalse(legacy_validation["ready"])
        self.assertIn("remote_ci_schema_invalid", legacy_validation["blockers"])

        self.local_output.write_bytes(self.embedded_bytes + b" ")
        tampered_validation = release_promotion_service._validate_remote_ci(
            remote,
            HEAD,
            imported,
            self.local_output.read_bytes(),
        )
        self.assertFalse(tampered_validation["ready"])
        self.assertFalse(tampered_validation["artifact_import_ready"])

    def test_digest_size_and_archive_shape_fail_closed_before_import(self) -> None:
        original_local = b"sentinel\n"
        self.local_output.parent.mkdir(parents=True)
        self.local_output.write_bytes(original_local)
        metadata = json.loads(self.metadata.read_text(encoding="utf-8"))
        cases = (
            ("digest", {**metadata, "digest": "sha256:" + "0" * 64}),
            ("size", {**metadata, "size_in_bytes": metadata["size_in_bytes"] + 1}),
        )
        for name, value in cases:
            with self.subTest(name=name):
                self.metadata.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self._import()
                self.assertEqual(self.local_output.read_bytes(), original_local)
        self._write_archive(extra_name="../escape.txt")
        with self.assertRaises(ValueError):
            self._import()
        self.assertEqual(self.local_output.read_bytes(), original_local)

    def test_wrong_head_receipt_and_post_import_tamper_fail_closed(self) -> None:
        wrong = _local_receipt()
        wrong["head_full"] = "e" * 40
        wrong_bytes = (json.dumps(wrong, sort_keys=True) + "\n").encode()
        self._write_archive(local_bytes=wrong_bytes)
        with self.assertRaises(ValueError):
            self._import()

        self._write_archive()
        self._import()
        imported = json.loads(self.import_output.read_text(encoding="utf-8"))
        self.local_output.write_bytes(self.embedded_bytes + b" ")
        ready, blockers = artifact_import.validate_import_receipt(
            imported,
            head_full=HEAD,
            run_id=RUN_ID,
            artifact_name=f"command-center-3-push-gate-evidence-{RUN_ID}",
            artifact_digest=self.digest,
            imported_local_receipt_bytes=self.local_output.read_bytes(),
        )
        self.assertFalse(ready)
        self.assertIn("artifact_import_receipt_semantic_binding_invalid", blockers)

    def test_archive_path_swap_after_snapshot_cannot_change_imported_bytes(self) -> None:
        original_archive = self.archive.read_bytes()
        replacement = self.root / "replacement.zip"
        wrong = _local_receipt()
        wrong["head_full"] = "e" * 40
        with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("command-center-3-push-gate.log", b"PASS\n")
            archive.writestr("command-center-3-push-gate-report.md", b"# PASS\n")
            archive.writestr(
                artifact_import.EMBEDDED_RECEIPT_NAME,
                (json.dumps(wrong, sort_keys=True) + "\n").encode(),
            )
        replacement_archive = replacement.read_bytes()
        original_read_bytes = Path.read_bytes
        swapped = False

        def read_with_swap(path: Path) -> bytes:
            nonlocal swapped
            data = original_read_bytes(path)
            if path == self.archive.resolve() and not swapped:
                swapped = True
                path.write_bytes(replacement_archive)
            return data

        with patch.object(Path, "read_bytes", read_with_swap):
            self._import()

        self.assertTrue(swapped)
        self.assertNotEqual(self.archive.read_bytes(), original_archive)
        self.assertEqual(self.local_output.read_bytes(), self.embedded_bytes)

    def test_default_evidence_output_rejects_symlink_escape(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / ".stock_ming_3").symlink_to(outside, target_is_directory=True)
        with patch.object(artifact_import, "PROJECT_ROOT", self.root.resolve()):
            default = (
                artifact_import.PROJECT_ROOT
                / ".stock_ming_3"
                / "release_gate"
                / "remote_push_gate_artifact_import_receipt.json"
            )
            with self.assertRaisesRegex(ValueError, "symlink"):
                artifact_import._resolve_output(None, default)


if __name__ == "__main__":
    unittest.main()
