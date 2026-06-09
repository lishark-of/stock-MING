#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 - <<'PY'
from server.services import packet_service
from server.services.task_service import create_task_stub

print("health: import ok")
for key in [
    "command_center_factor_quant_hub_packet",
    "command_center_serenity_method_radar_packet",
    "command_center_next_session_projection_packet",
]:
    packet = packet_service.read_packet(key)
    print(key, packet.get("status") or packet.get("mode"))
task = create_task_stub("smoke_3_0")
print("task_id:", task["task_id"])
PY
