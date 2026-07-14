#!/usr/bin/env python3
"""Validate and optionally promote current packaged Tauri evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from server.services.tauri_package_verifier import EVIDENCE_ROOT, validate_tauri_production_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current-head Tauri package evidence")
    parser.add_argument("--evidence-root", default=str(EVIDENCE_ROOT))
    parser.add_argument("--head-full", default="")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    result = validate_tauri_production_package(
        Path(args.evidence_root), expected_head_full=args.head_full, write_manifest=args.write_manifest
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("production_package_complete") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
