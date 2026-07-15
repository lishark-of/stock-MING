#!/usr/bin/env python3
"""Run one private LTG-10 packaged challenge; accepts no report or truth boolean."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from server.services.streamlit_retirement_evidence_service import (
    record_streamlit_primary_retirement_attestation,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch the fixed runner with a private nonce and seal only verified packaged evidence."
    )
    parser.add_argument("--evidence-root", default=".stock_ming_3")
    parser.add_argument("--head-full", required=True)
    args = parser.parse_args()
    result = record_streamlit_primary_retirement_attestation(
        Path(args.evidence_root),
        expected_head_full=args.head_full,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("streamlit_primary_retired") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
