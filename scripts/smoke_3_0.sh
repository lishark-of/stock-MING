#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 - <<'PY'
from server.services import evidence_service, migration_status_service, packet_service, quant_service, task_service, trade_review_service
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
migration = migration_status_service.build_migration_status()
print("migration_status:", migration["status"], len(migration["progress_baseline"]))
catalog = task_service.build_task_catalog()
print("task_catalog:", catalog["status"], catalog["task_count"])
trade_review = trade_review_service.read_trade_review_cache()
print("trade_review:", trade_review["status"], trade_review["record_count"])
quant = quant_service.read_quant_backtest_cache()
print("quant_cache:", quant["status"], quant["mode"])
evidence = evidence_service.read_a_share_evidence_cache()
print("evidence_cache:", evidence["status"], evidence["mode"])
PY
