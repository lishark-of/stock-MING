from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from scripts import import_remote_push_gate_artifact
from scripts import record_remote_ci_review_receipt
from server.services import audit_service, release_promotion_service


def _local_gate_receipt(*, head_full: str) -> dict[str, object]:
    return {
        "schema_version": audit_service.LOCAL_PUSH_GATE_RUN_RECEIPT_SCHEMA_VERSION,
        "status": "local_push_gate_passed_current_head",
        "scope": "ignored_local_push_gate_run_receipt_no_push_no_github_api",
        "generated_at_utc": "2026-07-19T00:00:00Z",
        "branch": "main",
        "head": head_full[:8],
        "head_full": head_full,
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


def build_verified_remote_ci_fixture(
    root: Path,
    *,
    head_full: str,
    run_id: int,
) -> dict[str, object]:
    """Create a real offline artifact-import chain under an isolated test root."""

    root = root.resolve()
    release_gate = root / ".stock_ming_3" / "release_gate"
    release_gate.mkdir(parents=True, exist_ok=True)
    archive_path = root / "artifact.zip"
    metadata_path = root / "artifact.json"
    local_receipt_path = release_gate / "local_push_gate_run_receipt.json"
    import_receipt_path = release_gate / "remote_push_gate_artifact_import_receipt.json"
    local_bytes = (
        json.dumps(
            _local_gate_receipt(head_full=head_full),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("command-center-3-push-gate.log", b"PASS\n")
        archive.writestr("command-center-3-push-gate-report.md", b"# PASS\n")
        archive.writestr(import_remote_push_gate_artifact.EMBEDDED_RECEIPT_NAME, local_bytes)
    archive_bytes = archive_path.read_bytes()
    artifact_digest = "sha256:" + hashlib.sha256(archive_bytes).hexdigest()
    artifact_name = f"command-center-3-push-gate-evidence-{run_id}"
    metadata_path.write_text(
        json.dumps(
            {
                "id": 71,
                "name": artifact_name,
                "size_in_bytes": len(archive_bytes),
                "expired": False,
                "digest": artifact_digest,
                "workflow_run": {
                    "id": run_id,
                    "head_branch": "main",
                    "head_sha": head_full,
                },
            }
        ),
        encoding="utf-8",
    )
    import_args = argparse.Namespace(
        artifact_zip=str(archive_path),
        artifact_metadata=str(metadata_path),
        head_full=head_full,
        run_id=run_id,
        local_receipt_output=str(local_receipt_path),
        output=str(import_receipt_path),
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.release_artifact_fixture_import",
            "--project-root",
            str(root),
            "--artifact-zip",
            import_args.artifact_zip,
            "--artifact-metadata",
            import_args.artifact_metadata,
            "--head-full",
            import_args.head_full,
            "--run-id",
            str(import_args.run_id),
            "--local-receipt-output",
            import_args.local_receipt_output,
            "--output",
            import_args.output,
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"formal artifact importer fixture failed: {result.stderr}")
    import_receipt = json.loads(import_receipt_path.read_text(encoding="utf-8"))
    remote_args = argparse.Namespace(
        branch="main",
        head=head_full[:8],
        head_full=head_full,
        run_id=run_id,
        run_url=f"https://github.com/lishark-of/stock-MING/actions/runs/{run_id}",
        workflow_name=record_remote_ci_review_receipt.EXPECTED_WORKFLOW_NAME,
        event="push",
        actions_status="completed",
        actions_conclusion="success",
        job_name="push-gate",
        job_conclusion="success",
        artifact_name=artifact_name,
        artifact_digest=artifact_digest,
        artifact_digest_unavailable_public_job_page=False,
        artifact_download_status="downloaded_to_local_temp_for_manual_review",
        artifact_import_receipt=str(import_receipt_path),
        imported_local_gate_receipt=str(local_receipt_path),
        safe_failure_log_excerpt="",
        no_matching_run_found=False,
        lookup_source="manual_actions_page_or_commit_status_review",
        reviewed_at_utc="2026-07-19T00:01:00Z",
        review_authorized=True,
    )
    record_remote_ci_review_receipt._validate_args(remote_args)
    remote_receipt = record_remote_ci_review_receipt.build_receipt(remote_args)
    validation = release_promotion_service._validate_remote_ci(
        remote_receipt,
        head_full,
        import_receipt,
        local_receipt_path.read_bytes(),
    )
    if validation.get("ready") is not True:
        raise AssertionError(f"verified remote CI fixture is invalid: {validation}")
    return {
        "artifact_digest": artifact_digest,
        "artifact_name": artifact_name,
        "local_receipt_path": local_receipt_path,
        "import_receipt_path": import_receipt_path,
        "remote_receipt": remote_receipt,
    }
