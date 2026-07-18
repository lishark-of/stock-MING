from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import cache_read_call_ledger, cache_read_packet, envelope
from server.services import audit_service, external_production_attestation_service, release_promotion_service


router = APIRouter(prefix="/api/audit")


def _production_release_promotion_ledger(packet: dict, *, request_method: str) -> list[dict]:
    return [
        {
            "api": "local_production_release_promotion_journal",
            "endpoint": f"{request_method} /api/audit/production-release-promotion",
            "request_method": request_method,
            "mode": "read_only_validation" if request_method == "GET" else "explicit_local_control_plane_write",
            "call_status": str(packet.get("status") or "production_release_promotion_blocked"),
            "row_count": 1 if packet.get("release_promotion_current_head") is True else 0,
            "row_count_semantics": "validated_current_pointer_visibility_not_insert_count",
            "promotion_written": packet.get("promotion_written") is True,
            "idempotent_replay": packet.get("idempotent_replay") is True,
            "external": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "github_api_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "contains_secret": False,
        }
    ]


@router.get("/cache")
def get_call_ledger_audit_cache() -> dict:
    packet = audit_service.read_call_ledger_audit_cache()
    return envelope(packet, call_ledger=packet.get("call_ledger"), warnings=packet.get("warnings"))


@router.get("/production-release-promotion")
def get_production_release_promotion() -> dict:
    packet = release_promotion_service.validate_production_release_promotion()
    return envelope(
        packet,
        call_ledger=_production_release_promotion_ledger(packet, request_method="GET"),
        warnings=packet.get("blockers"),
    )


@router.post("/production-release-promotion")
def promote_production_release(payload: dict | None = None) -> dict:
    packet = release_promotion_service.promote_production_release(payload)
    return envelope(
        packet,
        call_ledger=_production_release_promotion_ledger(packet, request_method="POST"),
        warnings=packet.get("blockers"),
    )


@router.get("/external-production-attestation")
def get_external_production_attestation() -> dict:
    packet = external_production_attestation_service.read_external_attestation_status()
    return envelope(packet, call_ledger=[], warnings=[])


@router.post("/external-production-attestation")
def import_external_production_attestation(payload: dict | None = None) -> dict:
    packet = external_production_attestation_service.import_signed_attestation(payload)
    return envelope(packet, call_ledger=[], warnings=[] if packet.get("ready") else [packet.get("status")])


@router.get("/user-route-qa")
def get_user_route_qa_evidence_cache() -> dict:
    evidence, rows = audit_service._user_route_qa_evidence_contract()
    packet = {
        "packet_key": "command_center_3_user_route_qa_evidence_cache",
        "schema_version": "command_center_3_user_route_qa_evidence_cache.v1",
        "status": evidence.get("status", "user_route_qa_evidence_pending"),
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "summary": "轻量读取 ignored 本地普通路线 QA 报告摘要；不打开浏览器、不提交截图、不创建任务。",
        "user_route_qa_evidence_contract": evidence,
        "user_route_qa_evidence_rows": rows,
        "counts": {
            "user_route_qa_evidence_report_count": evidence.get("report_count", 0),
            "user_route_qa_evidence_passing_report_count": evidence.get("passing_report_count", 0),
            "user_route_qa_evidence_row_count": evidence.get("row_count", 0),
            "user_route_qa_latest_report_passed": evidence.get("latest_report_passed") is True,
            "user_route_qa_latest_report_qa_matrix_count": evidence.get("latest_report_qa_matrix_count", 0),
            "user_route_qa_latest_report_review_required_count": evidence.get("latest_report_review_required_count", 0),
            "user_route_qa_latest_report_console_error_count": evidence.get("latest_report_console_error_count", 0),
            "user_route_qa_latest_report_candidate_route_passed": evidence.get("latest_report_candidate_route_passed") is True,
            "user_route_qa_latest_report_margin_etf_confirmed_bridge_passed": evidence.get(
                "latest_report_margin_etf_confirmed_bridge_passed"
            )
            is True,
            "user_route_qa_latest_report_margin_etf_confirmed_bridge_row_count": evidence.get(
                "latest_report_margin_etf_confirmed_bridge_row_count",
                0,
            ),
            "user_route_qa_visual_complete": evidence.get("ordinary_route_visual_qa_complete") is True,
            "user_route_qa_typing_silence_verified": evidence.get("typing_silence_verified") is True,
            "user_route_qa_candidate_route_passed": evidence.get("candidate_route_visual_qa_passed") is True,
            "user_route_qa_margin_etf_confirmed_bridge_passed": evidence.get(
                "margin_etf_confirmed_bridge_passed"
            )
            is True,
            "user_route_qa_margin_etf_confirmed_bridge_row_count": evidence.get(
                "margin_etf_confirmed_bridge_row_count",
                0,
            ),
            "user_route_qa_task_silence_failed_count": evidence.get("task_silence_failed_count", 0),
        },
        "policy": {
            "user_route_qa_evidence_is_local_ignored_artifact_summary": True,
            "user_route_qa_evidence_does_not_open_browser": True,
            "user_route_qa_evidence_does_not_create_task": True,
            "user_route_qa_evidence_is_not_streamlit_retirement": True,
            "user_route_qa_evidence_is_not_production_replacement": True,
        },
        "call_ledger": [
            {
                "api": "GET /api/audit/user-route-qa",
                "mode": "cache_only",
                "source": ".stock_ming_3/user_route_qa ignored local reports",
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        "warnings": [],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
    }
    current_ledger = cache_read_call_ledger(
        api="GET /api/audit/user-route-qa",
        route="GET /api/audit/user-route-qa",
        packet=packet,
        existing=packet.get("call_ledger"),
    )
    response_packet = cache_read_packet(packet, cache_call_ledger=current_ledger)
    return envelope(response_packet, call_ledger=current_ledger, warnings=packet.get("warnings"))


@router.post("/motion-browser-qa-review")
def review_motion_browser_qa(payload: dict | None = None) -> dict:
    task = audit_service.run_motion_browser_qa_review_task(payload)
    return envelope({"task_id": task["task_id"], "task": task}, call_ledger=task.get("call_ledger"), warnings=task.get("warnings"))

@router.post("/motion-production-promotion-dry-run")
def create_motion_production_promotion_dry_run(payload: dict | None = None) -> dict:
    task = audit_service.run_motion_production_promotion_dry_run_task(payload)
    return envelope({"task_id": task["task_id"], "task": task}, call_ledger=task.get("call_ledger"), warnings=task.get("warnings"))


@router.post("/motion-visual-performance-promotion-review")
def review_motion_visual_performance_promotion(payload: dict | None = None) -> dict:
    task = audit_service.run_motion_visual_performance_promotion_review_task(payload)
    return envelope({"task_id": task["task_id"], "task": task}, call_ledger=task.get("call_ledger"), warnings=task.get("warnings"))
