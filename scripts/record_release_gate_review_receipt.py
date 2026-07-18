#!/usr/bin/env python3
"""Write a local release-gate review receipt after matching remote CI green.

The script records a manual release review that has already happened. It does
not call GitHub, run the gate, push, call providers/models, or trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT_PATH = PROJECT_ROOT / ".stock_ming_3" / "release_gate" / "release_gate_review_receipt.json"
SCHEMA_VERSION = "command_center_3_release_gate_review_receipt.v1"


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
            "refusing to write a release review receipt inside the repository unless it is under .stock_ming_3/"
        )
    return output


def _validate_args(args: argparse.Namespace) -> None:
    if not args.review_authorized:
        raise SystemExit("--review-authorized is required after manual release review")
    if not args.head_full or len(args.head_full) < 12:
        raise SystemExit("--head-full must be the reviewed commit SHA")
    if not args.remote_run_id:
        raise SystemExit("--remote-run-id is required")
    if not args.remote_artifact_digest.startswith("sha256:") or len(args.remote_artifact_digest) < len("sha256:") + 32:
        raise SystemExit("--remote-artifact-digest must be a sha256 digest")
    if args.decision != "release_review_complete_strict_closeout_blocked":
        raise SystemExit("--decision must keep strict closeout blocked")


def build_receipt(args: argparse.Namespace) -> dict[str, Any]:
    # Canonicalize legacy seven-character display input to the formal eight-character receipt SHA.
    head = args.head_full[:8]
    reviewed_at = args.reviewed_at_utc or _now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "release_gate_review_ready",
        "scope": "ignored_manual_release_gate_review_no_cache_github_api",
        "reviewed_at_utc": reviewed_at,
        "receipt_writer": "scripts/record_release_gate_review_receipt.py",
        "reviewer": args.reviewer,
        "branch": args.branch,
        "head": head,
        "head_full": args.head_full,
        "remote_run_id": str(args.remote_run_id),
        "remote_artifact_digest": args.remote_artifact_digest,
        "decision": args.decision,
        "manual_review_note_safe": args.manual_review_note_safe,
        "explicit_user_release_review_authorized": True,
        "release_review_complete": True,
        "release_gate_complete": False,
        "strict_closeout_ready": False,
        "can_close_goal": False,
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
    parser.add_argument("--remote-run-id", required=True)
    parser.add_argument("--remote-artifact-digest", required=True)
    parser.add_argument("--decision", default="release_review_complete_strict_closeout_blocked")
    parser.add_argument("--reviewer", default="local-reviewer")
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
                "remote_run_id": payload["remote_run_id"],
                "release_review_complete": True,
                "release_gate_complete": False,
                "strict_closeout_ready": False,
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
