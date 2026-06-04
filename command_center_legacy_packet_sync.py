from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import command_center_discipline_packet as discipline_packet_service
import command_center_etf_packet as etf_packet_service
import command_center_quant_packet as quant_packet_service
import command_center_radar_packet as radar_packet_service


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _state_without(state: Any = None, *keys: str) -> dict:
    payload = as_mapping(state)
    for key in keys:
        payload.pop(key, None)
    return payload


def as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _first_rows(*values: Any) -> list:
    for value in values:
        rows = as_list(value)
        if rows:
            return rows
    return []


def extract_legacy_radar_rows(state: Any = None) -> list:
    state_map = as_mapping(state)
    scan = as_mapping(state_map.get("radar_scan_results"))
    summary = as_mapping(state_map.get("radar_scan_summary") or scan.get("summary"))
    existing_packet = as_mapping(state_map.get("command_center_radar_packet"))
    return _first_rows(
        scan.get("rule_rows"),
        scan.get("results"),
        scan.get("top_candidates"),
        scan.get("candidates"),
        scan.get("candidate_rows"),
        summary.get("rule_rows"),
        summary.get("results"),
        summary.get("top_candidates"),
        summary.get("candidates"),
        summary.get("candidate_rows"),
        existing_packet.get("top_candidates"),
    )


def sync_legacy_quant_packet(state: Any = None, live_packet: Any = None, target: str = "") -> dict:
    payload = _state_without(state, "command_center_quant_packet")
    return quant_packet_service.build_command_center_quant_packet(
        payload,
        live_packet=live_packet,
        target=target,
    )


def sync_legacy_discipline_packet(state: Any = None, live_packet: Any = None, target: str = "") -> dict:
    payload = _state_without(state, "command_center_discipline_packet")
    return discipline_packet_service.build_command_center_discipline_packet(
        payload,
        live_packet=live_packet,
        target=target,
    )


def sync_legacy_etf_packet(state: Any = None, live_packet: Any = None) -> dict:
    payload = _state_without(state, "command_center_etf_packet")
    return etf_packet_service.build_command_center_etf_packet(payload, live_packet=live_packet)


def sync_legacy_radar_packet(state: Any = None, live_packet: Any = None) -> dict:
    payload = _state_without(state, "command_center_radar_packet")
    rows = extract_legacy_radar_rows(state)
    scan = as_mapping(payload.get("radar_scan_results"))
    if rows and not _first_rows(scan.get("rule_rows"), scan.get("results"), scan.get("top_candidates")):
        payload["radar_scan_results"] = {**scan, "rule_rows": rows}
        payload.setdefault("radar_scan_status", scan.get("status") or "completed")
    return radar_packet_service.build_command_center_radar_packet(payload, live_packet=live_packet)
