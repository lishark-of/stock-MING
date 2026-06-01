from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import command_center_adapter as cc_adapter


DEFAULT_LIVE_PACKET_KEY = "command_center_live_packet"
DEFAULT_VIEW_MODEL_KEY = "command_center_view_model"


def state_get(state: Any, key: str, default: Any = None) -> Any:
    if hasattr(state, "get"):
        try:
            return state.get(key, default)
        except Exception:
            pass
    try:
        return state[key]
    except Exception:
        return default


def state_set(state: Any, key: str, value: Any) -> bool:
    try:
        state[key] = value
        return True
    except Exception:
        return False


def get_display_packet(state: Any, packet_key: str, last_success_key: str) -> dict:
    return cc_adapter.pick_display_packet(
        {
            packet_key: state_get(state, packet_key),
            last_success_key: state_get(state, last_success_key),
        },
        packet_key,
        last_success_key,
    )


def sync_child_packet(
    state: Any,
    live_packet: Any,
    child_key: str,
    child_packet: Any,
    live_packet_key: str = DEFAULT_LIVE_PACKET_KEY,
) -> dict:
    payload = cc_adapter.attach_child_packet(live_packet, child_key, child_packet)
    if not cc_adapter.as_mapping(child_packet):
        return payload

    current_packet = state_get(state, live_packet_key)
    if isinstance(current_packet, Mapping):
        state_set(
            state,
            live_packet_key,
            cc_adapter.attach_child_packet(current_packet, child_key, child_packet),
        )
    return payload


def sync_child_packets(
    state: Any,
    live_packet: Any,
    child_packets: Mapping[str, Any],
    live_packet_key: str = DEFAULT_LIVE_PACKET_KEY,
) -> dict:
    payload = cc_adapter.clone_packet(live_packet)
    current_packet = state_get(state, live_packet_key)
    current_payload = cc_adapter.clone_packet(current_packet) if isinstance(current_packet, Mapping) else {}
    current_changed = False

    for child_key, child_packet in child_packets.items():
        child = cc_adapter.as_mapping(child_packet)
        if not child:
            continue
        payload = cc_adapter.attach_child_packet(payload, child_key, child)
        if current_payload:
            current_payload = cc_adapter.attach_child_packet(current_payload, child_key, child)
            current_changed = True

    if current_changed:
        state_set(state, live_packet_key, current_payload)
    return payload


def build_view_model_from_state(
    state: Any,
    live_packet: Any = None,
    strategy_packet_key: str = "",
    strategy_last_success_key: str = "",
    decision_packet_key: str = "",
    decision_last_success_key: str = "",
    view_model_key: str = DEFAULT_VIEW_MODEL_KEY,
    store: bool = True,
) -> dict:
    strategy_packet = (
        get_display_packet(state, strategy_packet_key, strategy_last_success_key)
        if strategy_packet_key and strategy_last_success_key
        else {}
    )
    decision_packet = (
        get_display_packet(state, decision_packet_key, decision_last_success_key)
        if decision_packet_key and decision_last_success_key
        else {}
    )
    view_model = cc_adapter.build_command_center_view_model(
        live_packet=live_packet,
        strategy_execution_packet=strategy_packet,
        decision_packet=decision_packet,
        refresh_level=cc_adapter.get_nested(live_packet, "refresh_level"),
        generated_at=(
            cc_adapter.get_nested(live_packet, "updated_at")
            or cc_adapter.get_nested(live_packet, "generated_at")
        ),
    )
    if store:
        state_set(state, view_model_key, view_model)
    return view_model
