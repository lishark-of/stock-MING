#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 - <<'PY'
from server.services import audit_service, candidate_service, data_capability_service, data_health_service, discipline_service, evidence_service, legacy_service, market_service, migration_status_service, packet_service, position_service, quant_service, recovery_service, risk_service, strategy_service, task_service, trade_review_service, worker_service
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
audit = audit_service.read_call_ledger_audit_cache()
print("call_ledger_audit:", audit["status"], audit["mode"], audit["counts"]["call_ledger_count"])
legacy = legacy_service.read_legacy_bridge_cache()
print("legacy_bridge:", legacy["status"], legacy["mode"], legacy["counts"]["checklist_item_count"])
catalog = task_service.build_task_catalog()
print("task_catalog:", catalog["status"], catalog["task_count"])
worker = worker_service.read_worker_runtime_cache()
print("worker_runtime:", worker["status"], worker["mode"], worker["counts"]["worker_module_ready_count"])
trade_review = trade_review_service.read_trade_review_cache()
print("trade_review:", trade_review["status"], trade_review["record_count"])
market = market_service.read_market_context_cache()
print("market_context:", market["status"], market["mode"], market["counts"]["packet_count"])
discipline = discipline_service.read_discipline_loop_cache()
print("discipline_loop:", discipline["status"], discipline["mode"], discipline["counts"]["refresh_step_count"])
quant = quant_service.read_quant_backtest_cache()
print("quant_cache:", quant["status"], quant["mode"])
evidence = evidence_service.read_a_share_evidence_cache()
print("evidence_cache:", evidence["status"], evidence["mode"])
capability = data_capability_service.read_data_capability_cache()
print("data_capability:", capability["status"], capability["mode"])
data_health = data_health_service.read_data_health_timeline_cache()
print("data_health:", data_health["status"], data_health["mode"], data_health["counts"]["timeline_count"])
recovery = recovery_service.read_recovery_center_cache()
print("recovery_center:", recovery["status"], recovery["mode"], recovery["counts"]["action_count"])
strategy = strategy_service.read_strategy_trace_cache()
print("strategy_trace:", strategy["status"], strategy["mode"])
position = position_service.read_position_context_cache()
print("position_context:", position["status"], position["mode"])
candidate = candidate_service.read_candidate_radar_cache()
print("candidate_radar:", candidate["status"], candidate["mode"], candidate["counts"]["candidate_count"])
risk = risk_service.read_risk_guardrails_cache()
print("risk_guardrails:", risk["status"], risk["mode"], risk["counts"]["data_gap_count"])
PY
