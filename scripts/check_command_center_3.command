#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Command Center 3.0 check-only launcher"
echo "Boundary: this wrapper only resolves local launcher configuration; it does not start FastAPI/Vite, probe URLs, open a browser, create tasks, call providers/models, or touch trading paths."

COMMAND_CENTER_3_LAUNCHER_CHECK_ONLY=1 COMMAND_CENTER_3_LAUNCHER_SKIP_OPEN=1 "${SCRIPT_DIR}/start_command_center_3.command"
