from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from numbers import Number
from typing import Any

import command_center_local_api_contract as local_api_contract


PREVIEW_KIND = "command_center_local_api_preview_bundle"
PREVIEW_SOURCE = "session_state_like_mapping"


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _has_payload(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value) and not bool(value.get("is_empty"))
    if isinstance(value, (list, tuple)):
        return bool(value)
    return value not in [None, ""]


def _payload_from_state(state: Any, packet_key: str) -> Any:
    state_map = _as_mapping(state)
    if packet_key in state_map:
        return deepcopy(state_map.get(packet_key))
    if packet_key == "latest_recovery_result_notice":
        snapshot = _as_mapping(state_map.get("command_center_home_snapshot"))
        return deepcopy(snapshot.get("latest_recovery_result_notice") or {})
    return {}


def _status_from_payload(payload: Any, available: bool) -> str:
    if not available:
        return "waiting"
    packet = _as_mapping(payload)
    if packet:
        status = _to_text(
            packet.get("status")
            or packet.get("data_status")
            or packet.get("cache_state")
            or packet.get("state"),
            "ready",
        ).lower()
        if status in {"success", "completed"}:
            return "ok"
        if status in {"failed", "failure", "error"}:
            return "error"
        if status:
            return status
    return "ready"


def _endpoint_candidates(packet_keys: Any = None, include_legacy: bool = True) -> list[dict]:
    manifest = local_api_contract.build_local_api_endpoint_manifest(include_legacy=include_legacy)
    endpoints = manifest.get("endpoints") or []
    requested = {_to_text(item) for item in (packet_keys or []) if _to_text(item)}
    if not requested:
        return endpoints
    return [
        endpoint
        for endpoint in endpoints
        if endpoint.get("packet_key") in requested or endpoint.get("path") in requested
    ]


def build_local_api_preview_bundle(
    state: Any = None,
    packet_keys: Any = None,
    include_legacy: bool = True,
    include_missing: bool = True,
) -> dict:
    endpoints = _endpoint_candidates(packet_keys=packet_keys, include_legacy=include_legacy)
    responses = []
    available_count = 0
    missing_count = 0
    error_count = 0
    for endpoint in endpoints:
        packet_key = _to_text(endpoint.get("packet_key"))
        payload = _payload_from_state(state, packet_key)
        available = _has_payload(payload)
        if not available and not include_missing:
            continue
        status = _status_from_payload(payload, available)
        if available:
            available_count += 1
        else:
            missing_count += 1
        if status == "error":
            error_count += 1
        response = local_api_contract.build_packet_response_envelope(
            packet_key=packet_key,
            payload=payload if available else {},
            status=status,
            warnings=[] if available else [f"{packet_key} not present in current state"],
            meta={
                "available": available,
                "preview_only": True,
                "preview_source": PREVIEW_SOURCE,
                "endpoint_path": endpoint.get("path"),
            },
        )
        responses.append(response)
    return {
        "contract_version": local_api_contract.CONTRACT_VERSION,
        "kind": PREVIEW_KIND,
        "title": "stock-MING command center local API preview",
        "description": "Read-only preview of packet responses that a future local API could expose.",
        "server_started": False,
        "response_count": len(responses),
        "available_count": available_count,
        "missing_count": missing_count,
        "error_count": error_count,
        "responses": responses,
        "safe_mode": {
            "deepseek_called": False,
            "external_call_policy": "not_triggered",
            "secrets_redacted": True,
        },
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def build_local_api_preview_index(
    state: Any = None,
    include_legacy: bool = True,
    include_missing: bool = True,
) -> dict:
    bundle = build_local_api_preview_bundle(
        state=state,
        include_legacy=include_legacy,
        include_missing=include_missing,
    )
    index = {}
    for response in bundle["responses"]:
        path = _to_text(response.get("path"))
        if not path:
            continue
        meta = _as_mapping(response.get("meta"))
        index[path] = {
            "packet_key": response.get("packet_key"),
            "status": response.get("status"),
            "ok": response.get("ok"),
            "available": bool(meta.get("available")),
            "label": meta.get("label"),
            "area": meta.get("area"),
            "refresh_policy": meta.get("refresh_policy"),
            "deepseek_policy": meta.get("deepseek_policy"),
            "external_call_policy": meta.get("external_call_policy"),
        }
    return {
        "contract_version": local_api_contract.CONTRACT_VERSION,
        "kind": "command_center_local_api_preview_index",
        "endpoint_count": len(index),
        "index": index,
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def get_preview_response_for_path(
    state: Any,
    path_or_packet_key: Any,
    include_legacy: bool = True,
) -> dict:
    endpoint = local_api_contract.get_local_api_endpoint_contract(path_or_packet_key)
    if not endpoint:
        return {}
    bundle = build_local_api_preview_bundle(
        state=state,
        packet_keys=[endpoint["packet_key"]],
        include_legacy=include_legacy,
        include_missing=True,
    )
    return bundle["responses"][0] if bundle["responses"] else {}
