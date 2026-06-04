from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from numbers import Number
from typing import Any

import command_center_packet_registry as packet_registry


CONTRACT_VERSION = "2026-06-command-center-local-api-v1"
RESPONSE_KIND = "command_center_packet_response"
MANIFEST_KIND = "command_center_local_api_manifest"

OK_STATUSES = {"ok", "ready", "cached", "partial", "blocked", "missing", "empty", "waiting", "recovered"}
SECRET_KEY_PARTS = ("api_key", "apikey", "secret", "token", "password", "passwd", "credential")
SECRET_VALUE_PREFIXES = ("sk-", "tushare_", "supabase_")
REDACTED_VALUE = "[REDACTED]"


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in [None, ""]:
        return []
    return [value]


def _is_secret_key(key: Any) -> bool:
    text = _to_text(key).lower().replace("-", "_")
    return any(part in text for part in SECRET_KEY_PARTS)


def _is_secret_value(value: str) -> bool:
    text = value.strip().lower()
    return any(text.startswith(prefix) for prefix in SECRET_VALUE_PREFIXES)


def sanitize_for_local_api(value: Any) -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            text_key = _to_text(key)
            result[text_key] = REDACTED_VALUE if _is_secret_key(text_key) else sanitize_for_local_api(item)
        return result
    if isinstance(value, list):
        return [sanitize_for_local_api(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_local_api(item) for item in value]
    if isinstance(value, str):
        return REDACTED_VALUE if _is_secret_value(value) else value
    if isinstance(value, (bool, Number)) or value is None:
        return value
    return _to_text(value)


def _message_items(value: Any) -> list[str]:
    result = []
    seen = set()
    for item in _as_list(value):
        text = _to_text(item)
        if not text:
            continue
        safe = _to_text(sanitize_for_local_api(text))
        if safe and safe not in seen:
            result.append(safe)
            seen.add(safe)
    return result


def normalize_response_status(status: Any = "") -> str:
    text = _to_text(status, "ok").lower()
    if text in {"success", "completed"}:
        return "ok"
    if text in {"error", "failed", "failure"}:
        return "error"
    if text in OK_STATUSES:
        return text
    return "unknown"


def build_packet_response_envelope(
    packet_key: Any,
    payload: Any = None,
    status: Any = "ok",
    errors: Any = None,
    warnings: Any = None,
    meta: Any = None,
    generated_at: Any = "",
) -> dict:
    key = _to_text(packet_key)
    spec = packet_registry.get_command_center_packet_spec(key)
    normalized_status = normalize_response_status(status)
    error_items = _message_items(errors)
    warning_items = _message_items(warnings)
    is_known_packet = bool(spec)
    ok = is_known_packet and normalized_status in OK_STATUSES and not error_items
    local_api_path = spec.get("local_api_path") if spec else ""
    response_meta = {
        "label": spec.get("label", key or "unknown_packet"),
        "area": spec.get("area", "unknown"),
        "owner": spec.get("owner", ""),
        "source": spec.get("source", ""),
        "refresh_policy": spec.get("refresh_policy", "unknown"),
        "external_call_policy": spec.get("external_call_policy", "not_triggered"),
        "deepseek_policy": spec.get("deepseek_policy", "never"),
        "local_api_path": local_api_path,
        "generated_at": _to_text(generated_at),
        **(sanitize_for_local_api(meta) if isinstance(meta, Mapping) else {}),
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "kind": RESPONSE_KIND,
        "ok": ok,
        "status": normalized_status if is_known_packet else "unknown_packet",
        "packet_key": key,
        "path": local_api_path,
        "payload": sanitize_for_local_api(deepcopy(payload)),
        "meta": response_meta,
        "errors": [{"message": item} for item in error_items],
        "warnings": warning_items,
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def build_packet_error_envelope(
    packet_key: Any,
    message: Any,
    status: Any = "error",
    meta: Any = None,
) -> dict:
    return build_packet_response_envelope(
        packet_key=packet_key,
        payload={},
        status=status,
        errors=[message],
        warnings=[],
        meta=meta,
    )


def build_local_api_endpoint_manifest(include_legacy: bool = True) -> dict:
    specs = packet_registry.list_command_center_packets(include_legacy=include_legacy)
    endpoints = []
    for spec in specs:
        endpoints.append(
            {
                "method": "GET",
                "path": spec["local_api_path"],
                "packet_key": spec["packet_key"],
                "label": spec["label"],
                "area": spec["area"],
                "owner": spec["owner"],
                "response_kind": RESPONSE_KIND,
                "read_only": True,
                "refresh_policy": spec["refresh_policy"],
                "external_call_policy": spec["external_call_policy"],
                "deepseek_policy": spec["deepseek_policy"],
            }
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "kind": MANIFEST_KIND,
        "title": "stock-MING command center local API contract",
        "description": "Read-only packet endpoints for future pywebview local API, Tauri, React, or PWA clients.",
        "server_started": False,
        "base_path": "/api/command-center",
        "endpoint_count": len(endpoints),
        "endpoints": endpoints,
        "safe_mode": {
            "deepseek": "manual_only",
            "external_calls": "button_gated",
            "responses_redact_secrets": True,
        },
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def get_local_api_endpoint_contract(path_or_packet_key: Any) -> dict:
    text = _to_text(path_or_packet_key)
    if not text:
        return {}
    manifest = build_local_api_endpoint_manifest()
    for endpoint in manifest["endpoints"]:
        if text in {endpoint["path"], endpoint["packet_key"]}:
            return deepcopy(endpoint)
    return {}


def validate_packet_response_envelope(envelope: Any) -> dict:
    payload = envelope if isinstance(envelope, Mapping) else {}
    errors = []
    if payload.get("contract_version") != CONTRACT_VERSION:
        errors.append("contract_version mismatch")
    if payload.get("kind") != RESPONSE_KIND:
        errors.append("kind must be command_center_packet_response")
    if not _to_text(payload.get("packet_key")):
        errors.append("packet_key is required")
    if not isinstance(payload.get("meta"), Mapping):
        errors.append("meta must be a mapping")
    if not isinstance(payload.get("errors"), list):
        errors.append("errors must be a list")
    if payload.get("external_call_policy") != "not_triggered":
        errors.append("response must not trigger external calls")
    if payload.get("deepseek_called") is not False:
        errors.append("response must not call DeepSeek")
    return {
        "valid": not errors,
        "errors": errors,
    }
