#!/usr/bin/env python3
"""Write a local secret/artifact allowlist review receipt.

The script records a manual review that has already happened. It intentionally
does not run scans, read secrets, call GitHub, call providers, push, or trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT_PATH = (
    PROJECT_ROOT / ".stock_ming_3" / "release_gate" / "secret_artifact_allowlist_review_receipt.json"
)
SCHEMA_VERSION = "command_center_3_secret_artifact_allowlist_review_receipt.v1"
ALLOWED_HIGH_RISK_STATUSES = {"clean", "passed_no_high_risk_values"}
ALLOWED_KEYWORD_STATUSES = {
    "reviewed_no_high_risk_values",
    "secret_keyword_review_contract_ready_manual_review_pending",
}
ALLOWED_ARTIFACT_STATUSES = {"clean", "clean_or_allowed_assets_only"}


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
            "refusing to write an allowlist review receipt inside the repository unless it is under .stock_ming_3/"
        )
    return output


def _validate_args(args: argparse.Namespace) -> None:
    if not args.review_authorized:
        raise SystemExit("--review-authorized is required after manual secret/artifact allowlist review")
    if not args.head_full or len(args.head_full) < 12:
        raise SystemExit("--head-full must be the reviewed commit SHA")
    if args.high_risk_secret_scan_status not in ALLOWED_HIGH_RISK_STATUSES:
        raise SystemExit("--high-risk-secret-scan-status is not an allowed clean status")
    if args.secret_keyword_review_status not in ALLOWED_KEYWORD_STATUSES:
        raise SystemExit("--secret-keyword-review-status is not an allowed reviewed status")
    if args.generated_artifact_scan_status not in ALLOWED_ARTIFACT_STATUSES:
        raise SystemExit("--generated-artifact-scan-status is not an allowed clean status")


def build_receipt(args: argparse.Namespace) -> dict[str, Any]:
    # Canonicalize legacy seven-character display input to the formal eight-character receipt SHA.
    head = args.head_full[:8]
    reviewed_at = args.reviewed_at_utc or _now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "secret_artifact_allowlist_review_ready",
        "scope": "ignored_manual_secret_artifact_allowlist_review_no_cache_github_api",
        "reviewed_at_utc": reviewed_at,
        "receipt_writer": "scripts/record_secret_artifact_allowlist_review_receipt.py",
        "reviewer": args.reviewer,
        "branch": args.branch,
        "head": head,
        "head_full": args.head_full,
        "high_risk_secret_scan_status": args.high_risk_secret_scan_status,
        "secret_keyword_review_status": args.secret_keyword_review_status,
        "generated_artifact_scan_status": args.generated_artifact_scan_status,
        "manual_review_note_safe": args.manual_review_note_safe,
        "explicit_user_allowlist_review_authorized": True,
        "periodic_allowlist_review_ready": True,
        "false_positive_allowlist_review_ready": True,
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
    parser.add_argument("--output", help="Receipt path; defaults to .stock_ming_3/release_gate")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--head", default="")
    parser.add_argument("--head-full", required=True)
    parser.add_argument("--reviewer", default="local-reviewer")
    parser.add_argument("--high-risk-secret-scan-status", default="clean")
    parser.add_argument("--secret-keyword-review-status", default="reviewed_no_high_risk_values")
    parser.add_argument("--generated-artifact-scan-status", default="clean_or_allowed_assets_only")
    parser.add_argument("--manual-review-note-safe", default="")
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
                "periodic_allowlist_review_ready": payload["periodic_allowlist_review_ready"],
                "release_gate_complete": False,
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
