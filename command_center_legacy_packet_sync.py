from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import command_center_discipline_packet as discipline_packet_service
import command_center_quant_packet as quant_packet_service


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _state_without(state: Any = None, *keys: str) -> dict:
    payload = as_mapping(state)
    for key in keys:
        payload.pop(key, None)
    return payload


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
