#!/usr/bin/env python3
"""Record one operator-approved LTG-08 promotion ticket without using FastAPI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from server.services.next_session_replacement_promotion_service import (
    record_next_session_replacement_approval_ticket,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", default=".stock_ming_3")
    parser.add_argument("--head-full", required=True)
    parser.add_argument("--semantic-digest", required=True)
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--approved-by-user", action="store_true")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    result = record_next_session_replacement_approval_ticket(
        evidence_root=Path(args.evidence_root),
        expected_head_full=args.head_full,
        semantic_digest=args.semantic_digest,
        review_id=args.review_id,
        approved_by_user=args.approved_by_user,
        project_root=project_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ticket_written") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
