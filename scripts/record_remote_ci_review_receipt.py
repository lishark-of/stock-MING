#!/usr/bin/env python3
"""Write a local remote-CI review receipt from manually reviewed Actions metadata.

The script intentionally performs no network access. It records evidence that
was already reviewed elsewhere, then the audit cache decides whether the receipt
matches the current HEAD.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT_PATH = PROJECT_ROOT / ".stock_ming_3" / "release_gate" / "remote_ci_review_receipt.json"
SCHEMA_VERSION = "command_center_3_remote_ci_review_receipt.v1"
EXPECTED_WORKFLOW_NAME = "Command Center 3 Push Gate"
EXPECTED_REPO_RUN_PREFIX = "https://github.com/lishark-of/stock-MING/actions/runs/"
EXPECTED_ARTIFACT_PREFIX = "command-center-3-push-gate-evidence-"
INCOMPLETE_ACTIONS_STATUSES = {"queued", "in_progress", "waiting", "requested", "pending"}
FAILED_ACTIONS_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}
ARTIFACT_DOWNLOAD_STATUSES = {
    "",
    "not_attempted_by_receipt_writer",
    "public_download_404",
    "requires_authenticated_artifact_access",
    "downloaded_to_local_temp_for_manual_review",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_output(path_text: str | None) -> Path:
    raw_path = Path(path_text) if path_text else DEFAULT_RECEIPT_PATH
    output = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
    output = output.resolve(strict=False)
    try:
        relative = output.relative_to(PROJECT_ROOT)
    except ValueError:
        return output
    if not str(relative).startswith(".stock_ming_3/"):
        raise SystemExit(
            "refusing to write a remote CI review receipt inside the repository unless it is under .stock_ming_3/"
        )
    return output


def _validate_args(args: argparse.Namespace) -> None:
    if not args.review_authorized:
        raise SystemExit("--review-authorized is required after manual Actions review")
    if args.workflow_name != EXPECTED_WORKFLOW_NAME:
        raise SystemExit(f"--workflow-name must be {EXPECTED_WORKFLOW_NAME!r}")
    if args.event != "push":
        raise SystemExit("--event must be 'push'")
    status_is_completed = args.actions_status == "completed"
    status_is_incomplete = args.actions_status in INCOMPLETE_ACTIONS_STATUSES
    conclusion_is_failed = args.actions_conclusion in FAILED_ACTIONS_CONCLUSIONS
    if not (status_is_completed or status_is_incomplete):
        raise SystemExit("--actions-status must be 'completed' or an incomplete Actions status")
    if status_is_completed and args.actions_conclusion != "success" and not conclusion_is_failed:
        raise SystemExit("--actions-conclusion must be 'success' or a reviewed failure conclusion")
    if status_is_incomplete and args.actions_conclusion not in {"", "none", "null", "pending"}:
        raise SystemExit("--actions-conclusion must be empty or pending for an incomplete Actions run")
    if not args.run_url.startswith(EXPECTED_REPO_RUN_PREFIX):
        raise SystemExit("run URL must be the stock-MING GitHub Actions run URL")
    if str(args.run_id) not in args.run_url:
        raise SystemExit("run URL must contain the reviewed run id")
    if status_is_completed:
        if not args.artifact_name.startswith(EXPECTED_ARTIFACT_PREFIX):
            raise SystemExit("artifact name must be a Command Center 3 push-gate evidence artifact")
        if str(args.run_id) not in args.artifact_name:
            raise SystemExit("artifact name must contain the reviewed run id")
    elif args.artifact_name:
        raise SystemExit("--artifact-name is only allowed after a completed Actions run")
    if args.artifact_digest:
        if not args.artifact_digest.startswith("sha256:") or len(args.artifact_digest) < len("sha256:") + 32:
            raise SystemExit("artifact digest must be a sha256 digest")
    elif status_is_completed and not args.artifact_digest_unavailable_public_job_page:
        raise SystemExit(
            "--artifact-digest is required unless --artifact-digest-unavailable-public-job-page is set"
        )
    if conclusion_is_failed and not args.safe_failure_log_excerpt:
        raise SystemExit("--safe-failure-log-excerpt is required for a reviewed failure run")
    if args.artifact_download_status not in ARTIFACT_DOWNLOAD_STATUSES:
        raise SystemExit("--artifact-download-status is not an allowed receipt status")
    if not args.head_full or len(args.head_full) < 12:
        raise SystemExit("--head-full must be the reviewed commit SHA")


def build_receipt(args: argparse.Namespace) -> dict[str, Any]:
    head = args.head or args.head_full[:8]
    reviewed_at = args.reviewed_at_utc or _now_iso()
    artifact_digest_verified = bool(args.artifact_digest)
    actions_incomplete = args.actions_status in INCOMPLETE_ACTIONS_STATUSES
    actions_failed = args.actions_conclusion in FAILED_ACTIONS_CONCLUSIONS
    artifact_download_status = args.artifact_download_status or (
        "not_attempted_by_receipt_writer" if actions_failed else ""
    )
    artifact_download_blocked = artifact_download_status in {
        "public_download_404",
        "requires_authenticated_artifact_access",
    }
    if actions_incomplete:
        status = "remote_ci_review_run_in_progress"
        release_claim_decision = "blocked_remote_ci_incomplete"
        artifact_digest_review_status = "not_available_until_run_completed"
    elif actions_failed:
        status = "remote_ci_review_failed_run_reviewed"
        release_claim_decision = "blocked_remote_ci_failed"
        artifact_digest_review_status = (
            "sha256_digest_recorded"
            if artifact_digest_verified
            else "unavailable_from_public_job_page"
        )
    else:
        status = (
            "remote_ci_review_verified_green"
            if artifact_digest_verified
            else "remote_ci_review_green_artifact_digest_pending"
        )
        release_claim_decision = (
            "remote_ci_green_release_review_pending"
            if artifact_digest_verified
            else "blocked_remote_ci_artifact_digest_unverified"
        )
        artifact_digest_review_status = (
            "sha256_digest_recorded"
            if artifact_digest_verified
            else "unavailable_from_public_job_page"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "scope": "ignored_manual_remote_ci_review_receipt_no_cache_github_api",
        "reviewed_at_utc": reviewed_at,
        "receipt_writer": "scripts/record_remote_ci_review_receipt.py",
        "branch": args.branch,
        "head": head,
        "head_full": args.head_full,
        "workflow_name": args.workflow_name,
        "event": args.event,
        "run_id": args.run_id,
        "run_url": args.run_url,
        "safe_failure_log_excerpt_or_green_run_url": args.safe_failure_log_excerpt or args.run_url,
        "actions_status": args.actions_status,
        "actions_conclusion": args.actions_conclusion,
        "job_name": args.job_name,
        "job_conclusion": args.job_conclusion,
        "artifact_name": args.artifact_name,
        "artifact_digest": args.artifact_digest,
        "artifact_digest_verified": artifact_digest_verified,
        "artifact_digest_review_status": artifact_digest_review_status,
        "failed_step_or_green_status": (
            "remote_actions_run_in_progress"
            if actions_incomplete
            else args.safe_failure_log_excerpt
            if actions_failed
            else "green"
        ),
        "explicit_user_actions_review_authorized": True,
        "remote_actions_status_known": not actions_incomplete,
        "latest_remote_run_verified_green": bool(
            artifact_digest_verified and not actions_incomplete and not actions_failed
        ),
        "remote_ci_job_page_green_observed": bool(not actions_incomplete and not actions_failed),
        "remote_ci_artifact_digest_pending": bool(
            not actions_incomplete and not actions_failed and not artifact_digest_verified
        ),
        "remote_ci_run_observed_for_current_head": actions_incomplete,
        "remote_ci_run_in_progress_for_current_head": actions_incomplete,
        "remote_ci_failure_reviewed_for_current_head": actions_failed,
        "remote_ci_failure_artifact_download_status": artifact_download_status,
        "remote_ci_failure_artifact_download_blocked": artifact_download_blocked,
        "release_claim_decision": release_claim_decision,
        "remote_ci_review_receipt_is_not_release_review": True,
        "release_review_complete": False,
        "release_gate_complete": False,
        "production_release_complete": False,
        "cache_get_external_calls": False,
        "cache_get_calls_github_api": False,
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "github_api_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Receipt path; defaults to .stock_ming_3/release_gate/remote_ci_review_receipt.json")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--head", default="")
    parser.add_argument("--head-full", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--workflow-name", default=EXPECTED_WORKFLOW_NAME)
    parser.add_argument("--event", default="push")
    parser.add_argument("--actions-status", default="completed")
    parser.add_argument("--actions-conclusion", default="success")
    parser.add_argument("--job-name", default="push-gate")
    parser.add_argument("--job-conclusion", default="success")
    parser.add_argument("--artifact-name", default="")
    parser.add_argument("--artifact-digest", default="")
    parser.add_argument("--artifact-digest-unavailable-public-job-page", action="store_true")
    parser.add_argument("--artifact-download-status", default="")
    parser.add_argument("--safe-failure-log-excerpt", default="")
    parser.add_argument("--reviewed-at-utc", default="")
    parser.add_argument("--review-authorized", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _validate_args(args)
    output = _resolve_output(args.output)
    payload = build_receipt(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "receipt_path": str(output),
                "head_full": payload["head_full"],
                "run_id": payload["run_id"],
                "remote_actions_status_known": payload["remote_actions_status_known"],
                "latest_remote_run_verified_green": payload["latest_remote_run_verified_green"],
                "remote_ci_job_page_green_observed": payload["remote_ci_job_page_green_observed"],
                "remote_ci_artifact_digest_pending": payload["remote_ci_artifact_digest_pending"],
                "remote_ci_run_observed_for_current_head": payload["remote_ci_run_observed_for_current_head"],
                "remote_ci_run_in_progress_for_current_head": payload[
                    "remote_ci_run_in_progress_for_current_head"
                ],
                "remote_ci_failure_reviewed_for_current_head": payload[
                    "remote_ci_failure_reviewed_for_current_head"
                ],
                "remote_ci_failure_artifact_download_status": payload[
                    "remote_ci_failure_artifact_download_status"
                ],
                "remote_ci_failure_artifact_download_blocked": payload[
                    "remote_ci_failure_artifact_download_blocked"
                ],
                "release_claim_decision": payload["release_claim_decision"],
                "github_api_called": False,
                "external_calls_triggered": False,
                "does_not_execute_trades": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
