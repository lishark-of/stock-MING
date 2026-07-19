from __future__ import annotations

import argparse
from pathlib import Path

from scripts import import_remote_push_gate_artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--artifact-metadata", required=True)
    parser.add_argument("--head-full", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--local-receipt-output", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    # This module runs in a dedicated child process, so the fixture root cannot
    # race with another test that imports the production importer concurrently.
    import_remote_push_gate_artifact.PROJECT_ROOT = Path(args.project_root).resolve(strict=True)
    import_remote_push_gate_artifact.import_artifact(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
