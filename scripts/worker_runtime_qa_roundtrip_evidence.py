#!/usr/bin/env python3
"""Run LTG-06 local Worker runtime QA round-trip evidence.

This direct evidence runner uses the existing button-gated Worker POST chain:
synthetic healthcheck, activation review, production evidence plan, runtime QA
execution request, dry-run, and local runtime QA execution.

By default it uses an isolated temporary SQLite meta store so stale local
receipts cannot mask the execution result. It does not start Celery, ping Redis,
call providers/models/GitHub, execute trades, or mark production complete.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from server.main import app  # noqa: E402
from server.services import task_service, worker_service  # noqa: E402
from server.services.task_service import clear_task_statuses_for_tests, read_task_status  # noqa: E402
from storage.sqlite_meta import SQLiteMetaStore  # noqa: E402


FORBIDDEN_RESPONSE_MARKERS = ("SHOULD_DROP",)
PROJECT_META_CHAIN_PACKET_KEYS = (
    worker_service.PACKET_KEY,
    worker_service.SYNTHETIC_HEALTHCHECK_PACKET_KEY,
    worker_service.ACTIVATION_REVIEW_PACKET_KEY,
    worker_service.PRODUCTION_EVIDENCE_PLAN_PACKET_KEY,
    worker_service.RUNTIME_QA_EXECUTION_REQUEST_PACKET_KEY,
    worker_service.RUNTIME_QA_DRY_RUN_PACKET_KEY,
    worker_service.RUNTIME_QA_EXECUTION_PACKET_KEY,
)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


@contextmanager
def _meta_store(use_project_meta: bool) -> Iterator[dict[str, Any]]:
    original_worker_path = worker_service.SQLITE_META_PATH
    original_task_path = task_service.SQLITE_META_PATH
    if use_project_meta:
        yield {
            "isolated_meta_store": False,
            "project_meta_touched": True,
            "meta_path": _display_path(worker_service.SQLITE_META_PATH),
        }
        return
    with tempfile.TemporaryDirectory(prefix="stock_ming_worker_runtime_qa_") as tmp:
        db_path = Path(tmp) / "worker_runtime_qa.sqlite"
        worker_service.SQLITE_META_PATH = db_path
        task_service.SQLITE_META_PATH = db_path
        try:
            yield {
                "isolated_meta_store": True,
                "project_meta_touched": False,
                "meta_path": db_path.name,
            }
        finally:
            worker_service.SQLITE_META_PATH = original_worker_path
            task_service.SQLITE_META_PATH = original_task_path


def _post(client: TestClient, path: str, payload: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    response = client.post(path, json=payload).json()
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    steps.append(
        {
            "path": path,
            "ok": response.get("ok") is True,
            "status": data.get("status") or "",
            "call_ledger_api": (response.get("call_ledger") or [{}])[0].get("api")
            if isinstance(response.get("call_ledger"), list)
            else "",
        }
    )
    if response.get("ok") is not True:
        raise RuntimeError(f"{path}:not_ok")
    return response


def _reset_project_meta_chain_packets() -> dict[str, Any]:
    db_path = worker_service.SQLITE_META_PATH
    SQLiteMetaStore(db_path)
    if not db_path.exists():
        return {"project_meta_chain_packets_reset": True, "deleted_packet_count": 0}
    placeholders = ",".join("?" for _ in PROJECT_META_CHAIN_PACKET_KEYS)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            f"SELECT COUNT(*) FROM packets WHERE packet_key IN ({placeholders})",
            PROJECT_META_CHAIN_PACKET_KEYS,
        ).fetchone()
        deleted = int(row[0] if row else 0)
        conn.execute(
            f"DELETE FROM packets WHERE packet_key IN ({placeholders})",
            PROJECT_META_CHAIN_PACKET_KEYS,
        )
        conn.commit()
    return {"project_meta_chain_packets_reset": True, "deleted_packet_count": deleted}


def run_evidence(*, use_project_meta: bool = False) -> dict[str, Any]:
    with _meta_store(use_project_meta) as meta:
        reset = _reset_project_meta_chain_packets() if use_project_meta else {
            "project_meta_chain_packets_reset": False,
            "deleted_packet_count": 0,
        }
        client = TestClient(app)
        clear_task_statuses_for_tests(clear_persisted=True)
        steps: list[dict[str, Any]] = []

        _post(
            client,
            "/api/worker/synthetic-healthcheck",
            {"requested_from": "worker_runtime_qa_roundtrip_evidence"},
            steps,
        )
        _post(
            client,
            "/api/worker/activation-review",
            {"requested_from": "worker_runtime_qa_roundtrip_evidence", "operator_approved": True},
            steps,
        )
        _post(
            client,
            "/api/worker/production-evidence-plan",
            {"requested_from": "worker_runtime_qa_roundtrip_evidence", "operator_approved": True},
            steps,
        )

        cache = client.get("/api/worker/cache").json()["data"]
        plan = cache["worker_production_evidence_plan_receipt"]
        recipe = cache["worker_runtime_qa_execution_recipe"]
        request = _post(
            client,
            "/api/worker/runtime-qa-execution-request",
            {
                "requested_from": "worker_runtime_qa_roundtrip_evidence",
                "operator_approved": True,
                "scope_ticket_sha256": plan["scope_ticket_sha256"],
                "runtime_qa_scope_hash": recipe["runtime_qa_scope_hash"],
            },
            steps,
        )["data"]["worker_runtime_qa_execution_request_receipt"]
        dry_run = _post(
            client,
            "/api/worker/runtime-qa-dry-run",
            {
                "requested_from": "worker_runtime_qa_roundtrip_evidence",
                "operator_approved": True,
                "request_task_id": request["request_task_id"],
                "evidence_plan_scope_hash": request["production_evidence_plan_scope_hash"],
                "runtime_qa_scope_hash": request["runtime_qa_scope_hash"],
            },
            steps,
        )["data"]["worker_runtime_qa_dry_run_receipt"]
        execution_packet = _post(
            client,
            "/api/worker/runtime-qa-execution",
            {
                "requested_from": "worker_runtime_qa_roundtrip_evidence",
                "operator_approved": True,
                "dry_run_task_id": dry_run["dry_run_task_id"],
                "evidence_plan_scope_hash": dry_run["production_evidence_plan_scope_hash"],
                "runtime_qa_scope_hash": dry_run["runtime_qa_scope_hash"],
            },
            steps,
        )["data"]

        receipt = execution_packet["worker_runtime_qa_execution_receipt"]
        task = read_task_status(execution_packet["task_id"]) or {}
        cache_after = client.get("/api/worker/cache").json()["data"]
        durable_recipe = cache_after.get("worker_runtime_durable_evidence_recipe") or {}
        call_ledger = execution_packet.get("call_ledger") or []
        first_call = call_ledger[0] if call_ledger and isinstance(call_ledger[0], dict) else {}

        passed = bool(
            receipt.get("status") == "worker_runtime_qa_execution_ready_local_fallback_evidence"
            and receipt.get("local_runtime_qa_execution_done") is True
            and receipt.get("local_fallback_round_trip_verified") is True
            and receipt.get("local_task_round_trip_verified") is True
            and receipt.get("task_log_round_trip_verified") is True
            and receipt.get("append_only_worker_log_verified") is True
            and receipt.get("cross_process_task_control_verified") is True
            and receipt.get("scheduler_default_off_runtime_verified") is True
            and receipt.get("provider_model_no_autoschedule_boundary_verified") is True
            and receipt.get("no_trade_no_action_boundary_verified") is True
            and receipt.get("production_worker_complete") is False
            and receipt.get("worker_started") is False
            and receipt.get("celery_worker_started") is False
            and receipt.get("redis_pinged") is False
            and receipt.get("external_calls_triggered") is False
            and receipt.get("tushare_called") is False
            and receipt.get("deepseek_called") is False
            and receipt.get("github_called") is False
            and receipt.get("does_not_execute_trades") is True
            and receipt.get("does_not_modify_strategy_action") is True
            and receipt.get("contains_secret") is False
            and task.get("status") == "success"
            and task.get("task_type") == "run_worker_runtime_qa_execution"
            and first_call.get("api") == "local_worker_runtime_qa_execution"
            and first_call.get("external") is False
            and durable_recipe.get("runtime_qa_done") is True
        )

        summary = {
            "schema_version": "worker_runtime_qa_roundtrip_evidence.v1",
            "status": "worker_runtime_qa_roundtrip_passed" if passed else "worker_runtime_qa_roundtrip_failed",
            "direct_evidence_layer": "L3_local_worker_runtime_round_trip_not_celery_redis",
            "ltg_ids": ["LTG-06", "LTG-13"],
            **meta,
            **reset,
            "execution_task_id": receipt.get("execution_task_id") or "",
            "execution_status": receipt.get("status") or "",
            "local_runtime_qa_execution_done": receipt.get("local_runtime_qa_execution_done") is True,
            "local_fallback_round_trip_verified": receipt.get("local_fallback_round_trip_verified") is True,
            "local_task_round_trip_verified": receipt.get("local_task_round_trip_verified") is True,
            "task_log_round_trip_verified": receipt.get("task_log_round_trip_verified") is True,
            "append_only_worker_log_verified": receipt.get("append_only_worker_log_verified") is True,
            "cross_process_task_control_verified": receipt.get("cross_process_task_control_verified") is True,
            "scheduler_default_off_runtime_verified": (
                receipt.get("scheduler_default_off_runtime_verified") is True
            ),
            "provider_model_no_autoschedule_boundary_verified": (
                receipt.get("provider_model_no_autoschedule_boundary_verified") is True
            ),
            "no_trade_no_action_boundary_verified": receipt.get("no_trade_no_action_boundary_verified") is True,
            "queue_round_trip_evidence_ready": durable_recipe.get("queue_round_trip_evidence_ready") is True,
            "append_only_worker_log_evidence_ready": (
                durable_recipe.get("append_only_worker_log_evidence_ready") is True
            ),
            "cross_process_controls_evidence_ready": (
                durable_recipe.get("cross_process_controls_evidence_ready") is True
            ),
            "production_worker_complete": receipt.get("production_worker_complete") is True,
            "worker_started": receipt.get("worker_started") is True,
            "celery_worker_started": receipt.get("celery_worker_started") is True,
            "redis_pinged": receipt.get("redis_pinged") is True,
            "scheduler_started": receipt.get("scheduler_started") is True,
            "external_calls_triggered": receipt.get("external_calls_triggered") is True,
            "tushare_called": receipt.get("tushare_called") is True,
            "deepseek_called": receipt.get("deepseek_called") is True,
            "github_called": receipt.get("github_called") is True,
            "does_not_execute_trades": receipt.get("does_not_execute_trades") is True,
            "does_not_modify_strategy_action": receipt.get("does_not_modify_strategy_action") is True,
            "contains_secret": receipt.get("contains_secret") is True,
            "production_blockers": list(receipt.get("production_blockers") or []),
            "call_ledger_api": first_call.get("api") or "",
            "call_ledger_external": first_call.get("external") is True,
            "task_status": task.get("status") or "",
            "task_type": task.get("task_type") or "",
            "payload_safe_has_forbidden_auth_key": "authorization" in (task.get("payload_safe") or {}),
            "steps": steps,
        }
        dumped = json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)
        summary["forbidden_response_marker_found"] = any(marker in dumped for marker in FORBIDDEN_RESPONSE_MARKERS)
        if summary["forbidden_response_marker_found"]:
            summary["status"] = "worker_runtime_qa_roundtrip_failed"
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local Worker runtime QA round-trip direct evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    parser.add_argument(
        "--use-project-meta",
        action="store_true",
        help="Use .stock_ming_3/meta.sqlite instead of an isolated temporary meta store.",
    )
    args = parser.parse_args()
    try:
        summary = run_evidence(use_project_meta=args.use_project_meta)
    except Exception as exc:
        summary = {
            "schema_version": "worker_runtime_qa_roundtrip_evidence.v1",
            "status": "worker_runtime_qa_roundtrip_failed",
            "direct_evidence_layer": "L3_local_worker_runtime_round_trip_not_celery_redis",
            "error_message_safe": f"{type(exc).__name__}",
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
            "production_worker_complete": False,
        }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "worker_runtime_qa_roundtrip: {status}; task={task}; production_worker_complete={prod}".format(
                status=summary.get("status"),
                task=summary.get("execution_task_id") or "",
                prod=summary.get("production_worker_complete"),
            )
        )
    return 0 if summary.get("status") == "worker_runtime_qa_roundtrip_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
