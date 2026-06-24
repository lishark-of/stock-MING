from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import cache_envelope
from server.services import next_session_service


router = APIRouter(prefix="/api/next-session")


@router.get("/cache")
def get_next_session_cache() -> dict:
    packet = next_session_service.read_next_session_cache()
    return cache_envelope(
        packet,
        route="GET /api/next-session/cache",
        missing_message="当前没有精确次日操作图谱缓存；请通过按钮任务生成后再查看。",
        include_missing_data=True,
    )


@router.post("/generate")
def generate_next_session(payload: dict[str, Any] | None = None) -> dict:
    task = next_session_service.create_next_session_task(payload)
    return task_envelope(task)


@router.post("/browser-qa-review")
def review_next_session_browser_qa(payload: dict[str, Any] | None = None) -> dict:
    task = next_session_service.run_next_session_browser_qa_review_task(payload)
    return task_envelope(task)


@router.post("/streamlit-parity-review")
def review_next_session_streamlit_parity(payload: dict[str, Any] | None = None) -> dict:
    task = next_session_service.run_next_session_streamlit_parity_review_task(payload)
    return task_envelope(task)


@router.post("/production-promotion-review")
def review_next_session_production_promotion(payload: dict[str, Any] | None = None) -> dict:
    task = next_session_service.run_next_session_production_promotion_review_task(payload)
    return task_envelope(task)
