#!/usr/bin/env python3
"""Seal one explicit human review over the trusted current-head LTG-10 screenshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from server.services.streamlit_retirement_evidence_service import (
    record_streamlit_primary_retirement_visual_review,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Approve one HMAC-authenticated 12-shot LTG-10 visual-review manifest."
    )
    parser.add_argument("--evidence-root", default=".stock_ming_3")
    parser.add_argument("--head-full", required=True)
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--approved-by-user", action="store_true", required=True)
    parser.add_argument("--no-legacy-surface", action="store_true", required=True)
    parser.add_argument("--no-streamlit-surface", action="store_true", required=True)
    parser.add_argument("--no-admin-surface", action="store_true", required=True)
    args = parser.parse_args()
    result = record_streamlit_primary_retirement_visual_review(
        Path(args.evidence_root),
        expected_head_full=args.head_full,
        review_id=args.review_id,
        approved_by_user=args.approved_by_user,
        no_legacy_surface=args.no_legacy_surface,
        no_streamlit_surface=args.no_streamlit_surface,
        no_admin_surface=args.no_admin_surface,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("streamlit_primary_retired") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
