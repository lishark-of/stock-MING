#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 - <<'PY'
from fastapi.testclient import TestClient

from server.main import app
from server.services import audit_service, candidate_service, data_capability_service, data_health_service, desktop_service, discipline_service, evidence_service, legacy_service, market_service, migration_status_service, model_strategy_service, packet_service, position_service, quant_service, recovery_service, risk_service, strategy_service, task_service, trade_review_service, worker_service
from server.services.task_service import create_task_stub


def assert_false_when_present(name, packet, key):
    if key in packet and bool(packet.get(key)):
        raise AssertionError(f"{name}.{key} must stay false in smoke_3_0")


def assert_true_when_present(name, packet, key):
    if key in packet and not bool(packet.get(key)):
        raise AssertionError(f"{name}.{key} must stay true in smoke_3_0")


def assert_cache_safety(name, packet):
    for key in ("external_calls_triggered", "tushare_called", "deepseek_called", "github_called"):
        assert_false_when_present(name, packet, key)
    for key in ("does_not_execute_trades", "does_not_modify_strategy_action"):
        assert_true_when_present(name, packet, key)


def assert_api_cache_endpoint(client, path):
    response = client.get(path).json()
    if not response.get("ok"):
        raise AssertionError(f"{path} failed: {response.get('error')}")
    if not response.get("call_ledger"):
        raise AssertionError(f"{path}.call_ledger must be exposed at envelope top level")
    data = response.get("data") or {}
    if not isinstance(data, dict):
        raise AssertionError(f"{path}.data must be a dict")
    assert_cache_safety(path, data)
    return data


print("health: import ok")
for key in [
    "command_center_factor_quant_hub_packet",
    "command_center_serenity_method_radar_packet",
    "command_center_next_session_projection_packet",
]:
    packet = packet_service.read_packet(key)
    assert_cache_safety(key, packet)
    print(key, packet.get("status") or packet.get("mode"))
task = create_task_stub("smoke_3_0")
assert_cache_safety("task_stub", task)
print("task_id:", task["task_id"])
client = TestClient(app)
created = client.post("/api/chokepoint/run", json={"smoke": "task_creation_lineage"}).json()
if not created.get("ok"):
    raise AssertionError(f"task_creation_api failed: {created.get('error')}")
if not created.get("call_ledger"):
    raise AssertionError("task_creation_api.call_ledger must be exposed at envelope top level")
created_task = created.get("data", {}).get("task", {})
assert_cache_safety("task_creation_api", created_task)
print("task_creation_api:", created["data"]["task_id"], created["call_ledger"][0]["call_status"])
api_cache_paths = [
    "/api/packets",
    "/api/packets/command_center_factor_quant_hub_packet",
    "/api/factor-quant/cache",
    "/api/next-session/cache",
    "/api/serenity/cache",
    "/api/chokepoint/cache",
    "/api/model-strategy/cache",
    "/api/audit/cache",
    "/api/legacy/cache",
    "/api/worker/cache",
    "/api/storage",
    "/api/storage/factor-values",
    "/api/storage/daily",
    "/api/storage/daily-basic",
    "/api/storage/moneyflow",
    "/api/storage/backtest-results",
    "/api/storage/sqlite-meta",
    "/api/tasks",
    "/api/tasks/catalog",
]
for path in api_cache_paths:
    data = assert_api_cache_endpoint(client, path)
    print("api_cache:", path, data.get("status") or data.get("mode") or data.get("packet_key"))
migration = migration_status_service.build_migration_status()
assert_cache_safety("migration_status", migration)
print("migration_status:", migration["status"], len(migration["progress_baseline"]))
model_strategy = model_strategy_service.read_deepseek_model_strategy_cache()
assert_cache_safety("model_strategy", model_strategy)
print("model_strategy:", model_strategy["status"], model_strategy["mode"], model_strategy["counts"]["purpose_count"])
audit = audit_service.read_call_ledger_audit_cache()
assert_cache_safety("call_ledger_audit", audit)
print("call_ledger_audit:", audit["status"], audit["mode"], audit["counts"]["call_ledger_count"])
legacy = legacy_service.read_legacy_bridge_cache()
assert_cache_safety("legacy_bridge", legacy)
print("legacy_bridge:", legacy["status"], legacy["mode"], legacy["counts"]["checklist_item_count"])
catalog = task_service.build_task_catalog()
assert_cache_safety("task_catalog", catalog)
discovered_post_routes = sorted(
    f"POST {route.path}"
    for route in app.routes
    if "POST" in getattr(route, "methods", set()) and str(route.path).startswith("/api/")
)
known_post_routes = sorted(catalog["route_coverage"]["known_post_routes"])
if discovered_post_routes != known_post_routes:
    raise AssertionError(
        "task_catalog.route_coverage must cover every FastAPI POST route: "
        f"discovered={discovered_post_routes}, known={known_post_routes}"
    )
if catalog["route_coverage"]["uncovered_post_routes"]:
    raise AssertionError("task_catalog.route_coverage.uncovered_post_routes must stay empty")
if not catalog["route_coverage"]["call_ledger_required_for_all_known_post_routes"]:
    raise AssertionError("every known POST route must require call_ledger")
print("task_catalog:", catalog["status"], catalog["task_count"])
print("task_route_coverage:", len(discovered_post_routes), "post routes covered")
task_index = task_service.build_task_status_index()
assert_cache_safety("task_status_index", task_index)
print("task_status_index:", task_index["status"], task_index["task_count"], task_index["call_ledger_count"])
worker = worker_service.read_worker_runtime_cache()
assert_cache_safety("worker_runtime", worker)
print("worker_runtime:", worker["status"], worker["mode"], worker["counts"]["worker_module_ready_count"])
trade_review = trade_review_service.read_trade_review_cache()
assert_cache_safety("trade_review", trade_review)
print("trade_review:", trade_review["status"], trade_review["record_count"])
market = market_service.read_market_context_cache()
assert_cache_safety("market_context", market)
print("market_context:", market["status"], market["mode"], market["counts"]["packet_count"])
discipline = discipline_service.read_discipline_loop_cache()
assert_cache_safety("discipline_loop", discipline)
print("discipline_loop:", discipline["status"], discipline["mode"], discipline["counts"]["refresh_step_count"])
quant = quant_service.read_quant_backtest_cache()
assert_cache_safety("quant_cache", quant)
print("quant_cache:", quant["status"], quant["mode"])
evidence = evidence_service.read_a_share_evidence_cache()
assert_cache_safety("evidence_cache", evidence)
print("evidence_cache:", evidence["status"], evidence["mode"])
capability = data_capability_service.read_data_capability_cache()
assert_cache_safety("data_capability", capability)
print("data_capability:", capability["status"], capability["mode"])
data_health = data_health_service.read_data_health_timeline_cache()
assert_cache_safety("data_health", data_health)
print("data_health:", data_health["status"], data_health["mode"], data_health["counts"]["timeline_count"])
desktop = desktop_service.read_desktop_shell_preflight_cache()
assert_cache_safety("desktop_preflight", desktop)
print("desktop_preflight:", desktop["status"], desktop["mode"], desktop["runtime"]["tauri_dev_ready"])
recovery = recovery_service.read_recovery_center_cache()
assert_cache_safety("recovery_center", recovery)
print("recovery_center:", recovery["status"], recovery["mode"], recovery["counts"]["action_count"])
strategy = strategy_service.read_strategy_trace_cache()
assert_cache_safety("strategy_trace", strategy)
print("strategy_trace:", strategy["status"], strategy["mode"])
position = position_service.read_position_context_cache()
assert_cache_safety("position_context", position)
print("position_context:", position["status"], position["mode"])
candidate = candidate_service.read_candidate_radar_cache()
assert_cache_safety("candidate_radar", candidate)
print("candidate_radar:", candidate["status"], candidate["mode"], candidate["counts"]["candidate_count"])
risk = risk_service.read_risk_guardrails_cache()
assert_cache_safety("risk_guardrails", risk)
print("risk_guardrails:", risk["status"], risk["mode"], risk["counts"]["data_gap_count"])
PY
