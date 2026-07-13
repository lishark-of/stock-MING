"""Explicit, governed DeepSeek benchmark executor for LTG-07 evidence.

The public entry point is POST-task only.  It validates a previously approved
scope-bound execution request before loading a credential or constructing the
model client.  Packets and ledgers never retain prompts, outputs, credentials,
or exception text.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import secrets
import sqlite3
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import config
from deepseek_safety import find_deepseek_dangerous_words
from storage.sqlite_meta import SQLiteMetaStore

from .task_service import create_task_record, update_task_status


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_META_PATH = PROJECT_ROOT / ".stock_ming_3" / "meta.sqlite"
FACTOR_HUB_PACKET_KEY = "command_center_factor_quant_hub_packet"
CURRENT_PACKET_KEY = "command_center_deepseek_provider_benchmark_current"
LAST_GOOD_PACKET_KEY = "command_center_deepseek_provider_benchmark_last_good"
TASK_TYPE = "run_deepseek_provider_benchmark"
SAMPLE_COUNT = 40
SUCCESS_RATE_THRESHOLD = 0.9
MAX_RETRIES_PER_SAMPLE = 2
MODEL_TIMEOUT_SECONDS = 25.0
MODEL_MAX_TOKENS = 420
GLOBAL_DEADLINE_SECONDS = 180.0
MODEL_TEMPERATURE = 0
SDK_MAX_RETRIES = 0
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
ALLOWED_DEEPSEEK_BASE_URLS = (DEEPSEEK_BASE_URL,)
RESPONSE_FORMAT = "json_object"
BENCHMARK_CONTRACT_VERSION = "factor_deepseek_provider_benchmark_contract.v3"
PROMPT_VERSION = "factor_deepseek_provider_benchmark_prompt.v3"
OUTPUT_SCHEMA_VERSION = "factor_deepseek_provider_benchmark_output.v2"
LEDGER_SCHEMA_VERSION = "factor_deepseek_provider_benchmark_model_ledger.v3"
SCOPE_TICKET_SCHEMA_VERSION = "factor_deepseek_provider_benchmark_scope_ticket.v3"
SCOPE_RECEIPT_SCHEMA_VERSION = "factor_deepseek_provider_benchmark_scope_ticket_receipt.v2"
SCOPE_READY_STATUS = "deepseek_provider_benchmark_scope_ticket_ready_model_execution_pending"
EXECUTION_RECEIPT_SCHEMA_VERSION = "factor_deepseek_provider_benchmark_execution_request.v2"
EXECUTION_READY_STATUS = "deepseek_provider_benchmark_execution_request_ready_manual_model_task_pending"
MODEL_COST_ESTIMATE_VERSION = "conservative_upper_bound_not_provider_invoice.v1"
MODEL_COST_CEILING_USD_PER_MILLION_TOKENS = 10.0
MODEL_COST_BUDGET_USD = 1.0
ALLOWED_OUTPUT_FIELDS = (
    "summary",
    "support_notes",
    "suppress_notes",
    "conflict_notes",
    "missing_data_notes",
    "discipline_notes",
)
NOTE_FIELDS = ALLOWED_OUTPUT_FIELDS[1:]
FORBIDDEN_ACTION_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "建仓",
    "清仓",
    "满仓",
    "下单",
    "止盈",
    "止损",
    "做多",
    "做空",
    "增持",
    "减持",
    "介入",
    "退出",
    "仓位",
    "持仓比例",
    "目标价",
    "价格目标",
    "上涨",
    "下跌",
    "涨幅",
    "跌幅",
    "预测",
    "预计涨",
    "预计跌",
    "百分之",
    "buy",
    "sell",
    "long",
    "short",
    "entry",
    "enter",
    "exit",
    "position",
    "allocation",
    "exposure",
    "target price",
    "price target",
    "upside",
    "downside",
    "rise",
    "fall",
)
_ENGLISH_ACTION_RE = re.compile(
    r"\b(?:buy|sell|long|short|entry|enter|exit|position|allocation|exposure|upside|downside|rise|fall)\b|"
    r"\b(?:target\s+price|price\s+target|increase\s+exposure|decrease\s+exposure|add\s+exposure|reduce\s+exposure)\b",
    re.IGNORECASE,
)
_NUMERIC_OUTPUT_RE = re.compile(r"[0-9０-９]|(?:百分之|成仓|成持仓)")
SYSTEM_PROMPT = (
    "你是只读投研解释 benchmark。只能解释给定合成研究状态，不能生成买卖、增减仓、仓位比例、介入退出、"
    "目标价、涨跌预测、收益承诺或任何数字。只输出一个 JSON object，不得输出 Markdown、代码块、思维过程或额外正文。"
    "顶层字段必须且只能是 summary、support_notes、suppress_notes、conflict_notes、missing_data_notes、discipline_notes。"
    "summary 必须是无数字、无交易动作的简短文字；其余字段只能从输入 evidence_ids 中逐字引用标识符，不得生成新的事实或数值。"
)
SYSTEM_PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(ALLOWED_OUTPUT_FIELDS),
    "properties": {
        "summary": {"type": "string", "minLength": 1, "maxLength": 240},
        **{
            field: {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string", "maxLength": 80, "pattern": "^[A-Z_]+$"},
            }
            for field in NOTE_FIELDS
        },
    },
}

ModelCall = Callable[[Mapping[str, Any], int, bool, float], Mapping[str, Any]]


class GovernedModelCallError(Exception):
    def __init__(
        self,
        safe_code: str,
        *,
        network_attempted: bool,
        provider_call_dispatched: bool,
    ) -> None:
        super().__init__(safe_code)
        self.safe_code = safe_code
        self.network_attempted = network_attempted
        self.provider_call_dispatched = provider_call_dispatched


_PRODUCTION_TRANSPORT_CAPABILITY = object()


LEDGER_CONTRACT_FIELDS = (
    "schema_version",
    "sample_id",
    "attempt",
    "retry_count",
    "attempt_kind",
    "network_retry_count",
    "output_repair_count",
    "network_retry_attempted",
    "output_repair_attempted",
    "repair_attempted",
    "model_used",
    "requested_model",
    "returned_model",
    "returned_model_matches_requested",
    "finish_reason",
    "provider_request_id_present",
    "provider_request_id_hash",
    "system_fingerprint_present",
    "transport_provenance",
    "transport_production_eligible",
    "base_url_allowlisted",
    "request_temperature",
    "sdk_max_retries",
    "system_prompt_sha256",
    "authorization_nonce_digest",
    "authorization_nonce_present",
    "authorization_nonce_consumed",
    "status",
    "failure_code",
    "token_usage",
    "latency_ms",
    "parse_status",
    "cache_hit_or_miss",
    "input_hash",
    "output_hash",
    "response_format",
    "provider_response_format_requested",
    "provider_call_dispatched",
    "provider_response_observed",
    "safety_checked",
    "safety_passed",
    "raw_prompt_stored",
    "raw_output_stored",
    "contains_secret",
    "external_calls_triggered",
    "deepseek_called",
    "tushare_called",
    "github_called",
    "does_not_execute_trades",
    "does_not_modify_strategy_action",
    "does_not_override_numeric_values",
)


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _digest(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def authorization_nonce_digest(value: Any) -> str:
    text = str(value or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _fixed_samples() -> list[dict[str, Any]]:
    conditions = (
        "normal_support",
        "weak_support",
        "conflicting_factors",
        "missing_fundamental",
        "missing_flow",
        "stale_market_data",
        "suppressed_by_risk",
        "discipline_heavy",
    )
    samples: list[dict[str, Any]] = []
    for index in range(SAMPLE_COUNT):
        condition = conditions[index % len(conditions)]
        samples.append(
            {
                "sample_id": f"benchmark-{index + 1:02d}",
                "condition": condition,
                "factor_direction": ("support", "neutral", "suppress")[index % 3],
                "data_completeness": ("complete", "partial")[index % 2],
                "conflict_present": condition == "conflicting_factors",
                "evidence_ids": [
                    "FACTOR_DIRECTION_EVIDENCE",
                    "DATA_COMPLETENESS_EVIDENCE",
                    "CONFLICT_STATE_EVIDENCE",
                    "RESEARCH_BOUNDARY_EVIDENCE",
                ],
                "research_only": True,
            }
        )
    return samples


FIXED_SAMPLES = tuple(_fixed_samples())
FIXED_SCOPE_HASH = _digest(list(FIXED_SAMPLES))
FIXED_SAMPLE_IDS = tuple(str(sample["sample_id"]) for sample in FIXED_SAMPLES)
FIXED_SAMPLE_IDS_HASH = _digest(list(FIXED_SAMPLE_IDS))
FIXED_SAMPLE_INPUT_HASHES = {
    str(sample["sample_id"]): _digest(sample)
    for sample in FIXED_SAMPLES
}
OUTPUT_SCHEMA_HASH = _digest(RESPONSE_SCHEMA)
LEDGER_CONTRACT_HASH = _digest(list(LEDGER_CONTRACT_FIELDS))


def build_benchmark_scope_contract(model: str) -> dict[str, Any]:
    return {
        "contract_version": BENCHMARK_CONTRACT_VERSION,
        "model": str(model or ""),
        "model_purpose": "factor_explain",
        "sample_count": SAMPLE_COUNT,
        "sample_ids": list(FIXED_SAMPLE_IDS),
        "sample_ids_hash": FIXED_SAMPLE_IDS_HASH,
        "sample_set_hash": FIXED_SCOPE_HASH,
        "sample_input_hashes": dict(FIXED_SAMPLE_INPUT_HASHES),
        "required_json_success_rate": SUCCESS_RATE_THRESHOLD,
        "response_format": RESPONSE_FORMAT,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "output_schema_hash": OUTPUT_SCHEMA_HASH,
        "allowed_output_fields": list(ALLOWED_OUTPUT_FIELDS),
        "prompt_version": PROMPT_VERSION,
        "system_prompt_sha256": SYSTEM_PROMPT_SHA256,
        "base_url": DEEPSEEK_BASE_URL,
        "base_url_allowlist": list(ALLOWED_DEEPSEEK_BASE_URLS),
        "temperature": MODEL_TEMPERATURE,
        "sdk_max_retries": SDK_MAX_RETRIES,
        "max_retry_per_sample": MAX_RETRIES_PER_SAMPLE,
        "max_network_attempts_per_sample": MAX_RETRIES_PER_SAMPLE + 1,
        "max_network_retries_per_sample": MAX_RETRIES_PER_SAMPLE,
        "max_output_repairs_per_sample": MAX_RETRIES_PER_SAMPLE,
        "timeout_seconds": MODEL_TIMEOUT_SECONDS,
        "global_deadline_seconds": GLOBAL_DEADLINE_SECONDS,
        "max_tokens_per_attempt": MODEL_MAX_TOKENS,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "ledger_contract_fields": list(LEDGER_CONTRACT_FIELDS),
        "ledger_contract_hash": LEDGER_CONTRACT_HASH,
        "cost_estimate_version": MODEL_COST_ESTIMATE_VERSION,
        "cost_ceiling_usd_per_million_tokens": MODEL_COST_CEILING_USD_PER_MILLION_TOKENS,
        "cost_budget_usd": MODEL_COST_BUDGET_USD,
        "authorization_nonce_required": True,
    }


def benchmark_scope_hash(contract: Mapping[str, Any]) -> str:
    return _digest(dict(contract))


def _scope_contract_matches(scope: Mapping[str, Any], model: str) -> bool:
    expected = build_benchmark_scope_contract(model)
    contract = {key: scope.get(key) for key in expected}
    return bool(
        model
        and contract == expected
        and str(scope.get("benchmark_scope_hash") or "") == benchmark_scope_hash(expected)
    )


def _safe_payload(payload: Any) -> dict[str, Any]:
    source = payload if isinstance(payload, Mapping) else {}
    nonce = str(source.get("authorization_nonce") or "")
    return {
        "approved_by_user": source.get("approved_by_user") is True,
        "provider_run_approved_by_user": source.get("provider_run_approved_by_user") is True,
        "benchmark_scope_hash": str(source.get("benchmark_scope_hash") or source.get("scope_hash") or "").strip(),
        "authorization_nonce_present": bool(nonce),
        "authorization_nonce_digest": authorization_nonce_digest(nonce),
    }


def _read_factor_hub() -> dict[str, Any]:
    if not SQLITE_META_PATH.is_file():
        return {}
    try:
        packet = SQLiteMetaStore(SQLITE_META_PATH).read_packet(FACTOR_HUB_PACKET_KEY)
    except Exception:
        return {}
    return dict(packet) if isinstance(packet, Mapping) else {}


def _execution_scope(hub: Mapping[str, Any], payload: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    receipt_raw = hub.get("deepseek_provider_benchmark_execution_request_receipt")
    receipt = dict(receipt_raw) if isinstance(receipt_raw, Mapping) else {}
    scope_receipt_raw = hub.get("deepseek_provider_benchmark_scope_ticket_receipt")
    scope_receipt = dict(scope_receipt_raw) if isinstance(scope_receipt_raw, Mapping) else {}
    requested_hash = str(payload.get("benchmark_scope_hash") or "")
    approved_hash = str(receipt.get("benchmark_scope_hash") or "")
    contract_raw = receipt.get("approved_scope_contract")
    contract = dict(contract_raw) if isinstance(contract_raw, Mapping) else {}
    scope_contract_raw = scope_receipt.get("approved_scope_contract")
    scope_contract = dict(scope_contract_raw) if isinstance(scope_contract_raw, Mapping) else {}
    contract_model = str(contract.get("model") or "")
    expected_contract = build_benchmark_scope_contract(contract_model)
    expected_hash = benchmark_scope_hash(expected_contract)
    nonce_digest = str(payload.get("authorization_nonce_digest") or "")
    scope_nonce_digest = str(scope_receipt.get("authorization_nonce_digest") or "")
    execution_nonce_digest = str(receipt.get("authorization_nonce_digest") or "")
    blockers: list[str] = []
    if payload.get("approved_by_user") is not True or payload.get("provider_run_approved_by_user") is not True:
        blockers.append("explicit_provider_run_approval_required")
    if scope_receipt.get("schema_version") != SCOPE_RECEIPT_SCHEMA_VERSION:
        blockers.append("approved_scope_ticket_receipt_schema_invalid")
    if scope_receipt.get("status") != SCOPE_READY_STATUS:
        blockers.append("approved_scope_ticket_receipt_not_ready")
    if scope_receipt.get("local_scope_ticket_ready") is not True:
        blockers.append("approved_scope_ticket_local_readiness_missing")
    if scope_receipt.get("ready_for_explicit_provider_benchmark_task") is not True:
        blockers.append("approved_scope_ticket_provider_readiness_missing")
    ticket = scope_receipt.get("benchmark_scope_ticket")
    if not isinstance(ticket, Mapping) or ticket.get("schema_version") != SCOPE_TICKET_SCHEMA_VERSION:
        blockers.append("approved_scope_ticket_schema_invalid")
    if receipt.get("schema_version") != EXECUTION_RECEIPT_SCHEMA_VERSION:
        blockers.append("approved_execution_request_missing")
    if receipt.get("status") != EXECUTION_READY_STATUS:
        blockers.append("approved_execution_request_not_ready")
    if receipt.get("requested_scope_hash_matches_latest") is not True:
        blockers.append("execution_request_scope_not_bound")
    if receipt.get("scope_ticket_user_approved") is not True:
        blockers.append("scope_ticket_user_approval_missing")
    if receipt.get("execution_request_user_approved") is not True:
        blockers.append("execution_request_user_approval_missing")
    if receipt.get("provider_run_approved_by_user") is not True:
        blockers.append("provider_run_approval_not_bound_to_execution_request")
    if not requested_hash or requested_hash != approved_hash:
        blockers.append("benchmark_scope_hash_missing_or_mismatch")
    if not contract_model or contract != expected_contract:
        blockers.append("approved_scope_contract_not_exact")
    if approved_hash != expected_hash or receipt.get("approved_scope_contract_hash") != expected_hash:
        blockers.append("approved_scope_contract_hash_mismatch")
    if scope_contract != expected_contract:
        blockers.append("current_scope_ticket_contract_mismatch")
    if scope_receipt.get("benchmark_scope_hash") != expected_hash:
        blockers.append("current_scope_ticket_hash_mismatch")
    if scope_receipt.get("scope_ticket_user_approved") is not True:
        blockers.append("current_scope_ticket_approval_missing")
    if receipt.get("current_scope_receipt_hash_matches") is not True:
        blockers.append("execution_request_not_bound_to_current_scope_receipt")
    if payload.get("authorization_nonce_present") is not True or not nonce_digest:
        blockers.append("authorization_nonce_required")
    if scope_receipt.get("authorization_nonce_status") != "issued":
        blockers.append("authorization_nonce_not_issued_or_already_consumed")
    if receipt.get("authorization_nonce_status") != "issued":
        blockers.append("execution_authorization_nonce_not_issued_or_already_consumed")
    if not scope_nonce_digest or nonce_digest != scope_nonce_digest or nonce_digest != execution_nonce_digest:
        blockers.append("authorization_nonce_digest_mismatch")
    if scope_receipt.get("authorization_nonce_present") is not True:
        blockers.append("scope_authorization_nonce_missing")
    if receipt.get("authorization_nonce_present") is not True:
        blockers.append("execution_authorization_nonce_missing")
    scope = dict(expected_contract)
    scope.update(
        {
            "benchmark_scope_hash": expected_hash,
            "scope_binding_valid": not blockers,
            "approval_nonce_enforced": True,
            "authorization_nonce_digest": nonce_digest,
            "authorization_nonce_present": bool(nonce_digest),
            "authorization_nonce_consumed": False,
            "approval_replay_boundary": "single_use_sqlite_compare_and_consume_before_http",
        }
    )
    return scope, blockers


def _consume_authorization_nonce(
    *,
    raw_nonce: str,
    payload_safe: Mapping[str, Any],
) -> tuple[bool, str]:
    if not raw_nonce or authorization_nonce_digest(raw_nonce) != payload_safe.get("authorization_nonce_digest"):
        return False, "authorization_nonce_missing_or_invalid"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(SQLITE_META_PATH, timeout=5, isolation_level=None)
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT payload_json FROM packets WHERE packet_key = ?",
            (FACTOR_HUB_PACKET_KEY,),
        ).fetchone()
        hub = json.loads(row[0]) if row else {}
        if not isinstance(hub, Mapping):
            connection.rollback()
            return False, "authorization_hub_missing"
        scope, blockers = _execution_scope(hub, payload_safe)
        scope_receipt = dict(hub.get("deepseek_provider_benchmark_scope_ticket_receipt") or {})
        execution_receipt = dict(hub.get("deepseek_provider_benchmark_execution_request_receipt") or {})
        if blockers or scope.get("scope_binding_valid") is not True:
            connection.rollback()
            return False, blockers[0] if blockers else "authorization_scope_invalid"
        if scope_receipt.get("authorization_nonce") != raw_nonce:
            connection.rollback()
            return False, "authorization_nonce_compare_failed"
        consumed_at = _now_iso()
        scope_receipt.pop("authorization_nonce", None)
        scope_receipt.update(
            {
                "status": "deepseek_provider_benchmark_scope_ticket_consumed_new_authorization_required",
                "local_scope_ticket_ready": False,
                "ready_for_explicit_provider_benchmark_task": False,
                "authorization_nonce_present": False,
                "authorization_nonce_status": "consumed",
                "authorization_nonce_consumed_at": consumed_at,
            }
        )
        execution_receipt.update(
            {
                "status": "deepseek_provider_benchmark_execution_request_consumed_new_authorization_required",
                "local_execution_request_ready": False,
                "ready_for_manual_model_task_submission": False,
                "authorization_nonce_present": False,
                "authorization_nonce_status": "consumed",
                "authorization_nonce_consumed_at": consumed_at,
            }
        )
        updated_hub = dict(hub)
        updated_hub["deepseek_provider_benchmark_scope_ticket_receipt"] = scope_receipt
        updated_hub["deepseek_provider_benchmark_execution_request_receipt"] = execution_receipt
        updated_at = _dt.datetime.now().isoformat(timespec="seconds")
        cursor = connection.execute(
            "UPDATE packets SET payload_json = ?, updated_at = ? WHERE packet_key = ?",
            (
                json.dumps(updated_hub, ensure_ascii=False, default=str),
                updated_at,
                FACTOR_HUB_PACKET_KEY,
            ),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            return False, "authorization_nonce_atomic_update_failed"
        connection.commit()
        return True, "authorization_nonce_consumed"
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        return False, "authorization_nonce_atomic_consume_failed"
    finally:
        if connection is not None:
            connection.close()


def _validate_output(value: Any, sample: Mapping[str, Any]) -> tuple[bool, str, str, bool, bool, bool]:
    output_hash = _digest(value) if value not in (None, "") else ""
    safety_text = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if isinstance(value, Mapping)
        else str(value or "")
    )
    safety_text_folded = safety_text.casefold()
    action_safe = not (
        find_deepseek_dangerous_words(safety_text)
        or any(term.casefold() in safety_text_folded for term in FORBIDDEN_ACTION_TERMS)
        or _ENGLISH_ACTION_RE.search(safety_text) is not None
    )
    numeric_safe = _NUMERIC_OUTPUT_RE.search(safety_text) is None
    if find_deepseek_dangerous_words(safety_text):
        return False, "unsafe_claim_detected", output_hash, False, action_safe, numeric_safe
    if not action_safe:
        return False, "strategy_action_language_detected", output_hash, False, False, numeric_safe
    if not numeric_safe:
        return False, "numeric_output_detected", output_hash, False, True, False
    parsed: Any = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return False, "json_parse_failed", output_hash, True, True, True
    if not isinstance(parsed, Mapping):
        return False, "response_not_object", output_hash, True, True, True
    if set(parsed) != set(ALLOWED_OUTPUT_FIELDS):
        return False, "response_schema_keys_invalid", output_hash, True, True, True
    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 240:
        return False, "response_summary_invalid", output_hash, True, True, True
    evidence_ids = {
        str(item)
        for item in sample.get("evidence_ids", [])
        if isinstance(item, str) and item
    }
    for field in NOTE_FIELDS:
        notes = parsed.get(field)
        if not isinstance(notes, list) or len(notes) > 4:
            return False, "response_note_array_invalid", output_hash, True, True, True
        if any(not isinstance(note, str) or len(note) > 80 for note in notes):
            return False, "response_note_item_invalid", output_hash, True, True, True
        if any(note not in evidence_ids for note in notes):
            return False, "response_note_not_input_evidence_id", output_hash, True, True, True
    return True, "", _digest(dict(parsed)), True, True, True


def _ledger_row(
    *,
    sample: Mapping[str, Any],
    attempt: int,
    evidence_source: str,
    model_used: str,
    result: Mapping[str, Any],
    valid: bool,
    failure_code: str,
    output_hash: str,
    latency_ms: int,
    safety_passed: bool,
    action_safe: bool,
    numeric_safe: bool,
    attempt_kind: str,
    network_retry_count: int,
    output_repair_count: int,
    scope: Mapping[str, Any],
    transport_provenance: str,
    transport_production_eligible: bool,
    base_url_allowlisted: bool,
) -> dict[str, Any]:
    usage = result.get("usage") if isinstance(result.get("usage"), Mapping) else {}
    is_real = evidence_source == "real_provider"
    provider_call_dispatched = is_real and result.get("provider_call_dispatched") is True
    network_attempted = is_real and result.get("network_attempted") is True
    provider_response_observed = provider_call_dispatched and result.get("provider_response_observed") is True
    requested_model = str(result.get("requested_model") or model_used)
    returned_model = str(result.get("returned_model") or "")
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "sample_id": str(sample.get("sample_id") or ""),
        "attempt": attempt,
        "retry_count": max(0, attempt - 1),
        "attempt_kind": attempt_kind,
        "network_retry_count": network_retry_count,
        "output_repair_count": output_repair_count,
        "network_retry_attempted": network_retry_count > 0,
        "output_repair_attempted": output_repair_count > 0,
        "repair_attempted": output_repair_count > 0,
        "model_used": model_used,
        "requested_model": requested_model,
        "returned_model": returned_model,
        "returned_model_matches_requested": bool(returned_model and returned_model == requested_model == model_used),
        "finish_reason": str(result.get("finish_reason") or ""),
        "provider_request_id_present": result.get("provider_request_id_present") is True,
        "provider_request_id_hash": str(result.get("provider_request_id_hash") or ""),
        "system_fingerprint_present": result.get("system_fingerprint_present") is True,
        "transport_provenance": transport_provenance,
        "transport_production_eligible": transport_production_eligible,
        "base_url_allowlisted": base_url_allowlisted,
        "request_temperature": MODEL_TEMPERATURE,
        "sdk_max_retries": SDK_MAX_RETRIES,
        "system_prompt_sha256": SYSTEM_PROMPT_SHA256,
        "authorization_nonce_digest": str(scope.get("authorization_nonce_digest") or ""),
        "authorization_nonce_present": scope.get("authorization_nonce_present") is True,
        "authorization_nonce_consumed": scope.get("authorization_nonce_consumed") is True,
        "status": "accepted" if valid else "discarded",
        "failure_code": failure_code,
        "token_usage": {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
        "latency_ms": max(0, latency_ms),
        "parse_status": "schema_safe" if valid else failure_code,
        "cache_hit_or_miss": "miss",
        "input_hash": _digest(sample),
        "output_hash": output_hash,
        "response_format": RESPONSE_FORMAT,
        "provider_response_format_requested": result.get("provider_response_format_requested") is True,
        "provider_call_dispatched": provider_call_dispatched,
        "provider_response_observed": provider_response_observed,
        "safety_checked": True,
        "safety_passed": safety_passed,
        "raw_prompt_stored": False,
        "raw_output_stored": False,
        "contains_secret": False,
        "external_calls_triggered": bool(network_attempted and transport_production_eligible),
        "deepseek_called": bool(provider_call_dispatched and transport_production_eligible),
        "tushare_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": action_safe,
        "does_not_override_numeric_values": numeric_safe,
    }


def _execute_benchmark(
    scope: Mapping[str, Any],
    model_call: ModelCall,
    *,
    evidence_source: str,
    model_used: str,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    ledger: list[dict[str, Any]] = []
    success_count = 0
    unsafe_discard_count = 0
    retry_count = 0
    network_retry_count = 0
    output_repair_count = 0
    started_all = clock()
    deadline = started_all + float(scope.get("global_deadline_seconds") or GLOBAL_DEADLINE_SECONDS)
    deadline_exceeded = False
    transport_provenance = str(getattr(model_call, "transport_provenance", "injected_callable_test_only"))
    transport_production_eligible = bool(
        isinstance(model_call, _OpenAIModelCaller)
        and getattr(model_call, "production_eligible", False) is True
    )
    base_url_allowlisted = getattr(model_call, "base_url_allowlisted", False) is True
    for sample in FIXED_SAMPLES:
        previous_failure_kind = ""
        sample_network_retry_count = 0
        sample_output_repair_count = 0
        for attempt in range(1, int(scope.get("max_retry_per_sample") or 0) + 2):
            remaining = deadline - clock()
            if remaining <= 0:
                deadline_exceeded = True
                break
            attempt_kind = (
                "initial"
                if attempt == 1
                else "network_retry"
                if previous_failure_kind == "network"
                else "output_repair"
            )
            if attempt_kind == "network_retry":
                network_retry_count += 1
                sample_network_retry_count += 1
            elif attempt_kind == "output_repair":
                output_repair_count += 1
                sample_output_repair_count += 1
            started = clock()
            result: Mapping[str, Any]
            non_retryable = False
            try:
                candidate = model_call(
                    sample,
                    attempt,
                    attempt_kind == "output_repair",
                    min(MODEL_TIMEOUT_SECONDS, remaining),
                )
                result = candidate if isinstance(candidate, Mapping) else {}
                valid, failure_code, output_hash, safety_passed, action_safe, numeric_safe = _validate_output(
                    result.get("text"), sample
                )
                if result.get("provider_response_format_requested") is not True:
                    valid = False
                    failure_code = "provider_response_format_not_requested"
                if evidence_source == "real_provider":
                    requested_model = str(result.get("requested_model") or "")
                    returned_model = str(result.get("returned_model") or "")
                    finish_reason = str(result.get("finish_reason") or "")
                    if requested_model != model_used or returned_model != requested_model:
                        valid = False
                        failure_code = "provider_returned_model_mismatch"
                    elif finish_reason != "stop":
                        valid = False
                        failure_code = "provider_finish_reason_not_stop"
                    elif result.get("provider_request_id_present") is not True or not result.get("provider_request_id_hash"):
                        valid = False
                        failure_code = "provider_request_id_missing"
                    elif result.get("provider_response_observed") is not True:
                        valid = False
                        failure_code = "provider_response_not_observed"
                previous_failure_kind = "output" if not valid else ""
            except GovernedModelCallError as exc:
                result = {
                    "network_attempted": exc.network_attempted,
                    "provider_call_dispatched": exc.provider_call_dispatched,
                    "provider_response_observed": False,
                    "provider_response_format_requested": exc.provider_call_dispatched,
                }
                valid, failure_code, output_hash = False, exc.safe_code, ""
                safety_passed = action_safe = numeric_safe = True
                non_retryable = exc.safe_code == "model_request_locally_rejected"
                previous_failure_kind = "local" if non_retryable else "network"
            except TimeoutError:
                result = {
                    "network_attempted": False,
                    "provider_call_dispatched": False,
                    "provider_response_observed": False,
                }
                valid, failure_code, output_hash = False, "model_timeout", ""
                safety_passed = action_safe = numeric_safe = True
                previous_failure_kind = "network"
            except Exception:
                result = {
                    "network_attempted": False,
                    "provider_call_dispatched": False,
                    "provider_response_observed": False,
                }
                valid, failure_code, output_hash = False, "model_call_failed", ""
                safety_passed = action_safe = numeric_safe = True
                previous_failure_kind = "network"
            latency_ms = int(max(0.0, clock() - started) * 1000)
            row = _ledger_row(
                sample=sample,
                attempt=attempt,
                evidence_source=evidence_source,
                model_used=model_used,
                result=result,
                valid=valid,
                failure_code=failure_code,
                output_hash=output_hash,
                latency_ms=latency_ms,
                safety_passed=safety_passed,
                action_safe=action_safe,
                numeric_safe=numeric_safe,
                attempt_kind=attempt_kind,
                network_retry_count=sample_network_retry_count,
                output_repair_count=sample_output_repair_count,
                scope=scope,
                transport_provenance=transport_provenance,
                transport_production_eligible=transport_production_eligible,
                base_url_allowlisted=base_url_allowlisted,
            )
            ledger.append(row)
            if failure_code in {"unsafe_claim_detected", "strategy_action_language_detected", "numeric_output_detected"}:
                unsafe_discard_count += 1
            if valid:
                success_count += 1
                break
            if non_retryable:
                break
            if attempt <= int(scope.get("max_retry_per_sample") or 0):
                retry_count += 1
        if deadline_exceeded:
            break

    sample_count = len(FIXED_SAMPLES)
    success_rate = success_count / sample_count if sample_count else 0.0
    is_real = evidence_source == "real_provider"
    accepted_rows = [row for row in ledger if row.get("status") == "accepted"]
    response_schema_validated = success_count == sample_count and all(
        row.get("parse_status") == "schema_safe" for row in accepted_rows
    )
    reviewed_sample_ids = {
        str(row.get("sample_id") or "")
        for row in ledger
        if row.get("safety_checked") is True
    }
    safety_reviewed_ledger_count = sum(1 for row in ledger if row.get("safety_checked") is True)
    safety_review_passed = bool(
        reviewed_sample_ids == set(FIXED_SAMPLE_IDS)
        and safety_reviewed_ledger_count == len(ledger)
        and len(accepted_rows) == sample_count
        and all(row.get("safety_passed") is True for row in accepted_rows)
    )
    provider_response_format_enforced = bool(
        is_real
        and transport_production_eligible
        and base_url_allowlisted
        and len(accepted_rows) == sample_count
        and all(row.get("provider_response_format_requested") is True for row in accepted_rows)
        and all(row.get("provider_response_observed") is True for row in accepted_rows)
    )
    per_sample_attempts = {
        sample_id: [row for row in ledger if row.get("sample_id") == sample_id]
        for sample_id in FIXED_SAMPLE_IDS
    }
    actual_max_attempts = max((len(rows) for rows in per_sample_attempts.values()), default=0)
    ledger_contract_valid = bool(
        set(row.get("sample_id") for row in ledger) == set(FIXED_SAMPLE_IDS)
        and all(set(LEDGER_CONTRACT_FIELDS).issubset(row) for row in ledger)
        and all(
            [int(row.get("attempt") or 0) for row in rows] == list(range(1, len(rows) + 1))
            and 1 <= len(rows) <= MAX_RETRIES_PER_SAMPLE + 1
            and sum(1 for row in rows if row.get("status") == "accepted") == 1
            and rows[-1].get("status") == "accepted"
            and all(
                row.get("schema_version") == LEDGER_SCHEMA_VERSION
                and row.get("model_used") == model_used
                and row.get("response_format") == RESPONSE_FORMAT
                and row.get("input_hash") == FIXED_SAMPLE_INPUT_HASHES[sample_id]
                and row.get("raw_prompt_stored") is False
                and row.get("raw_output_stored") is False
                and row.get("contains_secret") is False
                for row in rows
            )
            for sample_id, rows in per_sample_attempts.items()
        )
    )
    scope_binding_valid = bool(
        scope.get("scope_binding_valid") is True
        and _scope_contract_matches(scope, model_used)
        and scope.get("approval_nonce_enforced") is True
        and scope.get("authorization_nonce_present") is True
        and scope.get("authorization_nonce_consumed") is True
        and bool(scope.get("authorization_nonce_digest"))
    )
    token_total = sum(int((row.get("token_usage") or {}).get("total_tokens") or 0) for row in ledger)
    retry_token_total = sum(
        int((row.get("token_usage") or {}).get("total_tokens") or 0)
        for row in ledger
        if int(row.get("attempt") or 0) > 1
    )
    token_usage_complete = bool(
        len(accepted_rows) == sample_count
        and all(int((row.get("token_usage") or {}).get("total_tokens") or 0) > 0 for row in accepted_rows)
        and token_total > 0
    )
    cost_estimate_usd = round(
        token_total * MODEL_COST_CEILING_USD_PER_MILLION_TOKENS / 1_000_000,
        8,
    )
    token_budget_cost_evidence_complete = bool(
        token_usage_complete
        and cost_estimate_usd > 0
        and cost_estimate_usd <= MODEL_COST_BUDGET_USD
    )
    provider_call_count = sum(1 for row in ledger if row.get("provider_call_dispatched") is True)
    provider_response_count = sum(1 for row in ledger if row.get("provider_response_observed") is True)
    provider_metadata_complete = bool(
        len(accepted_rows) == sample_count
        and all(
            row.get("requested_model") == model_used
            and row.get("returned_model") == model_used
            and row.get("returned_model_matches_requested") is True
            and row.get("finish_reason") == "stop"
            and row.get("provider_request_id_present") is True
            and len(str(row.get("provider_request_id_hash") or "")) == 64
            and all(
                char in "0123456789abcdef"
                for char in str(row.get("provider_request_id_hash") or "")
            )
            for row in accepted_rows
        )
    )
    action_safety_validated = bool(
        len(accepted_rows) == sample_count
        and all(row.get("does_not_modify_strategy_action") is True for row in accepted_rows)
    )
    numeric_safety_validated = bool(
        len(accepted_rows) == sample_count
        and all(row.get("does_not_override_numeric_values") is True for row in accepted_rows)
    )
    elapsed_seconds = max(0.0, clock() - started_all)
    production_fact_ready = bool(
        is_real
        and success_count == sample_count
        and success_rate >= SUCCESS_RATE_THRESHOLD
        and scope_binding_valid
        and provider_response_format_enforced
        and response_schema_validated
        and safety_review_passed
        and ledger_contract_valid
        and actual_max_attempts <= MAX_RETRIES_PER_SAMPLE + 1
        and provider_call_count >= sample_count
        and provider_response_count >= sample_count
        and token_budget_cost_evidence_complete
        and provider_metadata_complete
        and transport_production_eligible
        and base_url_allowlisted
        and action_safety_validated
        and numeric_safety_validated
        and not deadline_exceeded
        and elapsed_seconds <= float(scope.get("global_deadline_seconds") or GLOBAL_DEADLINE_SECONDS)
    )
    approved_contract = build_benchmark_scope_contract(model_used)
    packet = {
        "packet_key": CURRENT_PACKET_KEY,
        "schema_version": "factor_deepseek_provider_benchmark_result.v1",
        "status": "deepseek_provider_benchmark_passed" if production_fact_ready else "deepseek_provider_benchmark_not_promoted",
        "created_at": _now_iso(),
        "evidence_source": evidence_source,
        "benchmark_scope_hash": str(scope.get("benchmark_scope_hash") or ""),
        "approved_scope_contract": approved_contract,
        "approved_scope_contract_hash": benchmark_scope_hash(approved_contract),
        "scope_binding_valid": scope_binding_valid,
        "approval_nonce_enforced": scope.get("approval_nonce_enforced") is True,
        "authorization_nonce_digest": str(scope.get("authorization_nonce_digest") or ""),
        "authorization_nonce_present": scope.get("authorization_nonce_present") is True,
        "authorization_nonce_consumed": scope.get("authorization_nonce_consumed") is True,
        "approval_replay_boundary": "single_use_sqlite_compare_and_consume_before_http",
        "fixed_sample_ids": list(FIXED_SAMPLE_IDS),
        "fixed_sample_ids_hash": FIXED_SAMPLE_IDS_HASH,
        "fixed_sample_set_hash": FIXED_SCOPE_HASH,
        "sample_count": sample_count,
        "success_count": success_count,
        "failed_count": sample_count - success_count,
        "json_success_rate": round(success_rate, 6),
        "required_json_success_rate": float(scope.get("required_json_success_rate") or SUCCESS_RATE_THRESHOLD),
        "response_format": RESPONSE_FORMAT,
        "provider_response_format_enforced": provider_response_format_enforced,
        "provider_response_metadata_complete": provider_metadata_complete,
        "response_schema_validated": response_schema_validated,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "output_schema_hash": OUTPUT_SCHEMA_HASH,
        "prompt_version": PROMPT_VERSION,
        "max_retry_per_sample": MAX_RETRIES_PER_SAMPLE,
        "max_network_attempts_per_sample": MAX_RETRIES_PER_SAMPLE + 1,
        "actual_max_attempts_per_sample": actual_max_attempts,
        "timeout_seconds": MODEL_TIMEOUT_SECONDS,
        "global_deadline_seconds": float(scope.get("global_deadline_seconds") or GLOBAL_DEADLINE_SECONDS),
        "global_elapsed_seconds": round(elapsed_seconds, 6),
        "global_deadline_exceeded": deadline_exceeded,
        "retry_count": retry_count,
        "network_retry_count": network_retry_count,
        "output_repair_count": output_repair_count,
        "unsafe_output_discarded_count": unsafe_discard_count,
        "unsafe_output_accepted_count": 0,
        "safety_reviewed_sample_count": len(reviewed_sample_ids),
        "safety_reviewed_ledger_count": safety_reviewed_ledger_count,
        "safety_review_passed": safety_review_passed,
        "model_used": model_used,
        "transport_provenance": transport_provenance,
        "transport_production_eligible": transport_production_eligible,
        "base_url_allowlisted": base_url_allowlisted,
        "request_temperature": MODEL_TEMPERATURE,
        "sdk_max_retries": SDK_MAX_RETRIES,
        "system_prompt_sha256": SYSTEM_PROMPT_SHA256,
        "model_ledger_count": len(ledger),
        "model_ledger_complete": ledger_contract_valid,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "ledger_contract_hash": LEDGER_CONTRACT_HASH,
        "model_ledger": ledger,
        "total_tokens": token_total,
        "retry_tokens": retry_token_total,
        "token_usage_complete": token_usage_complete,
        "model_cost_estimate_usd": cost_estimate_usd,
        "cost_estimate_version": MODEL_COST_ESTIMATE_VERSION,
        "cost_budget_usd": MODEL_COST_BUDGET_USD,
        "cost_budget_status": "within_bound" if token_budget_cost_evidence_complete else "not_verified_or_over_bound",
        "token_budget_cost_evidence_complete": token_budget_cost_evidence_complete,
        "provider_call_count": provider_call_count,
        "provider_response_count": provider_response_count,
        "provider_benchmark_done": production_fact_ready,
        "production_fact_ready": production_fact_ready,
        "governed_model_runtime": production_fact_ready,
        "production_deepseek_explanation_complete": production_fact_ready,
        "raw_prompt_stored": False,
        "raw_output_stored": False,
        "contains_secret": False,
        "external_calls_triggered": any(row.get("external_calls_triggered") is True for row in ledger),
        "deepseek_called": any(row.get("deepseek_called") is True for row in ledger),
        "tushare_called": False,
        "github_called": False,
        "worker_dispatched": False,
        "qmt_called": False,
        "broker_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": action_safety_validated,
        "does_not_override_numeric_values": numeric_safety_validated,
        "evidence_boundary": "real_provider_quality_and_safety_pass_required_synthetic_never_closes_ltg07",
    }
    return packet


def _failure_packet(scope: Mapping[str, Any], failure_code: str) -> dict[str, Any]:
    return {
        "packet_key": CURRENT_PACKET_KEY,
        "schema_version": "factor_deepseek_provider_benchmark_result.v1",
        "status": "deepseek_provider_benchmark_blocked",
        "created_at": _now_iso(),
        "evidence_source": "not_executed",
        "safe_failure_code": failure_code,
        "benchmark_scope_hash": str(scope.get("benchmark_scope_hash") or ""),
        "scope_binding_valid": False,
        "approval_nonce_enforced": scope.get("approval_nonce_enforced") is True,
        "authorization_nonce_digest": str(scope.get("authorization_nonce_digest") or ""),
        "authorization_nonce_present": scope.get("authorization_nonce_present") is True,
        "authorization_nonce_consumed": scope.get("authorization_nonce_consumed") is True,
        "approval_replay_boundary": "single_use_sqlite_compare_and_consume_before_http",
        "fixed_sample_ids": list(FIXED_SAMPLE_IDS),
        "fixed_sample_ids_hash": FIXED_SAMPLE_IDS_HASH,
        "fixed_sample_set_hash": FIXED_SCOPE_HASH,
        "sample_count": SAMPLE_COUNT,
        "success_count": 0,
        "failed_count": SAMPLE_COUNT,
        "json_success_rate": 0.0,
        "required_json_success_rate": SUCCESS_RATE_THRESHOLD,
        "response_format": RESPONSE_FORMAT,
        "provider_response_format_enforced": False,
        "provider_response_metadata_complete": False,
        "response_schema_validated": False,
        "safety_review_passed": False,
        "model_ledger_count": 0,
        "model_ledger_complete": False,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "ledger_contract_hash": LEDGER_CONTRACT_HASH,
        "model_ledger": [],
        "global_deadline_seconds": GLOBAL_DEADLINE_SECONDS,
        "global_elapsed_seconds": 0.0,
        "global_deadline_exceeded": False,
        "total_tokens": 0,
        "token_usage_complete": False,
        "model_cost_estimate_usd": 0.0,
        "cost_estimate_version": MODEL_COST_ESTIMATE_VERSION,
        "cost_budget_status": "not_verified_or_over_bound",
        "token_budget_cost_evidence_complete": False,
        "provider_benchmark_done": False,
        "production_fact_ready": False,
        "governed_model_runtime": False,
        "production_deepseek_explanation_complete": False,
        "raw_prompt_stored": False,
        "raw_output_stored": False,
        "contains_secret": False,
        "external_calls_triggered": False,
        "deepseek_called": False,
        "tushare_called": False,
        "github_called": False,
        "worker_dispatched": False,
        "qmt_called": False,
        "broker_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": False,
        "does_not_override_numeric_values": False,
    }


class _OpenAIModelCaller:
    def __init__(
        self,
        client: Any,
        model: str,
        *,
        base_url: str = DEEPSEEK_BASE_URL,
        production_capability: object | None = None,
        explicit_http_client: bool = True,
    ) -> None:
        self._client = client
        self._model = model
        self._base_url = base_url
        self.production_eligible = bool(
            production_capability is _PRODUCTION_TRANSPORT_CAPABILITY
            and not explicit_http_client
            and base_url in ALLOWED_DEEPSEEK_BASE_URLS
        )
        self.base_url_allowlisted = base_url in ALLOWED_DEEPSEEK_BASE_URLS
        self.transport_provenance = (
            "sdk_managed_allowlisted_https"
            if self.production_eligible
            else "explicit_http_client_or_injected_transport_test_only"
        )

    def __call__(
        self,
        sample: Mapping[str, Any],
        attempt: int,
        repair: bool,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        import openai

        user_payload = dict(sample)
        user_payload["output_contract"] = {
            "allowed_fields": list(ALLOWED_OUTPUT_FIELDS),
            "notes_must_be_input_evidence_ids": True,
            "numbers_forbidden": True,
            "strategy_action_language_forbidden": True,
            "repair_only": repair,
        }
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=MODEL_TEMPERATURE,
                max_tokens=MODEL_MAX_TOKENS,
                timeout=timeout_seconds,
                response_format={"type": RESPONSE_FORMAT},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True)},
                ],
            )
        except (TypeError, ValueError):
            raise GovernedModelCallError(
                "model_request_locally_rejected",
                network_attempted=False,
                provider_call_dispatched=False,
            ) from None
        except openai.APITimeoutError:
            raise GovernedModelCallError(
                "model_timeout",
                network_attempted=True,
                provider_call_dispatched=True,
            ) from None
        except openai.APIConnectionError:
            raise GovernedModelCallError(
                "model_connection_failed",
                network_attempted=True,
                provider_call_dispatched=False,
            ) from None
        except openai.APIStatusError:
            raise GovernedModelCallError(
                "provider_request_rejected",
                network_attempted=True,
                provider_call_dispatched=True,
            ) from None
        except openai.APIError:
            raise GovernedModelCallError(
                "model_api_failed",
                network_attempted=True,
                provider_call_dispatched=False,
            ) from None
        choice = response.choices[0] if getattr(response, "choices", None) else None
        message = getattr(choice, "message", None)
        usage = getattr(response, "usage", None)
        request_id = str(getattr(response, "id", "") or "")
        return {
            "text": str(getattr(message, "content", "") if message else ""),
            "usage": {
                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
            },
            "provider_response_format_requested": True,
            "requested_model": self._model,
            "returned_model": str(getattr(response, "model", "") or ""),
            "finish_reason": str(getattr(choice, "finish_reason", "") or ""),
            "provider_request_id_present": bool(request_id),
            "provider_request_id_hash": hashlib.sha256(request_id.encode("utf-8")).hexdigest() if request_id else "",
            "system_fingerprint_present": bool(getattr(response, "system_fingerprint", None)),
            "network_attempted": True,
            "provider_call_dispatched": True,
            "provider_response_observed": True,
        }

    def close(self) -> None:
        self._client.close()


def _build_real_model_call(
    credential: str,
    model: str,
    *,
    http_client: Any | None = None,
    base_url: str = DEEPSEEK_BASE_URL,
) -> _OpenAIModelCaller:
    from openai import OpenAI

    if base_url not in ALLOWED_DEEPSEEK_BASE_URLS:
        raise ValueError("deepseek_base_url_not_allowlisted")
    kwargs: dict[str, Any] = {
        "api_key": credential,
        "base_url": base_url,
        "timeout": MODEL_TIMEOUT_SECONDS,
        "max_retries": SDK_MAX_RETRIES,
    }
    if http_client is not None:
        kwargs["http_client"] = http_client
    return _OpenAIModelCaller(
        OpenAI(**kwargs),
        model,
        base_url=base_url,
        production_capability=None if http_client is not None else _PRODUCTION_TRANSPORT_CAPABILITY,
        explicit_http_client=http_client is not None,
    )


def _write_current(packet: Mapping[str, Any]) -> None:
    store = SQLiteMetaStore(SQLITE_META_PATH)
    store.write_packet(CURRENT_PACKET_KEY, dict(packet))
    if packet.get("production_fact_ready") is True:
        promoted = dict(packet)
        promoted["packet_key"] = LAST_GOOD_PACKET_KEY
        store.write_packet(LAST_GOOD_PACKET_KEY, promoted)


def run_deepseek_provider_benchmark_task(payload: Any = None) -> dict[str, Any]:
    source = payload if isinstance(payload, Mapping) else {}
    raw_nonce = str(source.get("authorization_nonce") or "")
    payload_safe = _safe_payload(payload)
    payload_safe["invocation_id"] = secrets.token_hex(12)
    task = create_task_record(
        TASK_TYPE,
        output_packet_key=CURRENT_PACKET_KEY,
        payload=payload_safe,
        current_step="deepseek_provider_benchmark_queued",
        warnings=["模型 benchmark 仅允许显式 POST、已批准 scope、固定 40 样本；失败不会覆盖 last-good。"],
    )
    if task.get("dedupe_reused_existing"):
        return task
    update_task_status(task["task_id"], status="running", progress=0.05, current_step="validating_governed_benchmark_scope")
    hub = _read_factor_hub()
    scope, blockers = _execution_scope(hub, payload_safe)
    if blockers:
        packet = _failure_packet(scope, blockers[0])
        _write_current(packet)
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="deepseek_provider_benchmark_blocked_scope",
            error_message_safe=blockers[0],
            call_ledger=[],
        ) or task

    consumed, consume_status = _consume_authorization_nonce(
        raw_nonce=raw_nonce,
        payload_safe=payload_safe,
    )
    if not consumed:
        packet = _failure_packet(scope, consume_status)
        _write_current(packet)
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="deepseek_provider_benchmark_blocked_nonce_consume",
            error_message_safe=consume_status,
            call_ledger=[],
        ) or task
    scope = dict(scope)
    scope["authorization_nonce_consumed"] = True

    try:
        model = config.get_deepseek_model("factor_explain")
    except Exception:
        model = ""
    if not _scope_contract_matches(scope, model):
        packet = _failure_packet(scope, "configured_model_no_longer_matches_approved_scope")
        _write_current(packet)
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="deepseek_provider_benchmark_blocked_configured_model_scope_mismatch",
            error_message_safe="configured_model_no_longer_matches_approved_scope",
            call_ledger=[],
        ) or task

    try:
        credentials = config.get_deepseek_keys()
    except Exception:
        credentials = []
    if not credentials:
        packet = _failure_packet(scope, "model_credential_unavailable")
        _write_current(packet)
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="deepseek_provider_benchmark_blocked_credential_unavailable",
            error_message_safe="model_credential_unavailable",
            call_ledger=[],
        ) or task

    try:
        model_call = _build_real_model_call(credentials[0], model)
    except Exception:
        packet = _failure_packet(scope, "model_client_or_configuration_unavailable")
        _write_current(packet)
        return update_task_status(
            task["task_id"],
            status="failed",
            progress=1.0,
            current_step="deepseek_provider_benchmark_blocked_model_client_unavailable",
            error_message_safe="model_client_or_configuration_unavailable",
            call_ledger=[],
        ) or task
    update_task_status(task["task_id"], status="running", progress=0.15, current_step="running_fixed_scope_provider_benchmark")
    try:
        packet = _execute_benchmark(
            scope,
            model_call,
            evidence_source="real_provider",
            model_used=model,
        )
    finally:
        close = getattr(model_call, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
    _write_current(packet)
    passed = packet.get("production_fact_ready") is True
    return update_task_status(
        task["task_id"],
        status="success" if passed else "failed",
        progress=1.0,
        current_step=(
            "deepseek_provider_benchmark_quality_safety_passed"
            if passed
            else "deepseek_provider_benchmark_quality_safety_not_promoted"
        ),
        error_message_safe=None if passed else "provider_benchmark_quality_or_safety_gate_failed",
        call_ledger=list(packet.get("model_ledger") or []),
    ) or task


def create_deepseek_benchmark_task(task_type: str, payload: Any = None) -> dict[str, Any]:
    if task_type != TASK_TYPE:
        raise ValueError("unsupported_deepseek_benchmark_task_type")
    return run_deepseek_provider_benchmark_task(payload)
