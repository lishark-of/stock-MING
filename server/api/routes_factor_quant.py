from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from server.api.task_response import task_envelope
from server.schemas.packets import cache_envelope, cache_read_call_ledger, cache_read_packet
from server.services import deepseek_benchmark_service, factor_service


router = APIRouter(prefix="/api/factor-quant")


@router.get("/cache")
def get_factor_quant_cache() -> dict:
    packet = factor_service.read_factor_quant_cache()
    current_ledger = cache_read_call_ledger(
        api="local_factor_quant_cache",
        route="GET /api/factor-quant/cache",
        packet=packet,
        existing=packet.get("cache_call_ledger") or packet.get("call_ledger"),
    )
    response_packet = cache_read_packet(packet, cache_call_ledger=current_ledger)
    return cache_envelope(
        response_packet,
        route="GET /api/factor-quant/cache",
        missing_message="当前没有多因子量化图谱缓存；请通过按钮任务生成后再查看。",
        call_ledger=current_ledger,
    )


@router.post("/refresh-data")
def refresh_factor_data(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("refresh_factor_data", payload)
    return task_envelope(task)


@router.post("/run-light")
def run_factor_light(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_light", payload)
    return task_envelope(task)


@router.post("/universe-research-plan")
def plan_factor_universe_research(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_universe_research_plan", payload)
    return task_envelope(task)


@router.post("/universe-worker-batch-dry-run")
def dry_run_factor_universe_worker_batch(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_universe_worker_batch_dry_run", payload)
    return task_envelope(task)


@router.post("/universe-worker-batch-execution-request")
def request_factor_universe_worker_batch_execution(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_universe_worker_batch_execution_request", payload)
    return task_envelope(task)


@router.post("/universe-worker-batch-research")
def record_factor_universe_worker_batch_research(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_universe_worker_batch_research", payload)
    return task_envelope(task)


@router.post("/provider-small-pool-dry-run")
def dry_run_factor_test_provider_small_pool(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_test_provider_small_pool_acceptance_dry_run", payload)
    return task_envelope(task)


@router.post("/provider-small-pool-execution-request")
def request_factor_test_provider_small_pool_execution(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_test_provider_small_pool_execution_request", payload)
    return task_envelope(task)


@router.post("/provider-small-pool-acceptance")
def request_factor_test_provider_small_pool_acceptance(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_factor_test_provider_small_pool_acceptance", payload)
    return task_envelope(task)


@router.post("/provider-industry-membership")
def request_factor_test_provider_industry_membership(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task(
        factor_service.FACTOR_TEST_INDUSTRY_PROVIDER_TASK_TYPE,
        payload,
    )
    return task_envelope(task)


@router.post("/deepseek-explain")
def explain_factor_with_deepseek(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_deepseek_factor_explanation", payload)
    return task_envelope(task)


@router.post("/deepseek-provider-benchmark-scope-ticket")
def create_deepseek_provider_benchmark_scope_ticket(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_deepseek_provider_benchmark_scope_ticket", payload)
    return task_envelope(task)


@router.post("/deepseek-provider-benchmark-execution-request")
def create_deepseek_provider_benchmark_execution_request(payload: dict[str, Any] | None = None) -> dict:
    task = factor_service.create_factor_task("run_deepseek_provider_benchmark_execution_request", payload)
    return task_envelope(task)


@router.post("/deepseek-provider-benchmark")
def run_deepseek_provider_benchmark(payload: dict[str, Any] | None = None) -> dict:
    task = deepseek_benchmark_service.create_deepseek_benchmark_task("run_deepseek_provider_benchmark", payload)
    return task_envelope(task)
