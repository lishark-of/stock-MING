#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m uvicorn server.main:app --reload --port 8710
