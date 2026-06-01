from __future__ import annotations

from typing import Any

import command_center_adapter as cc_adapter


DEFAULT_LIVE_PACKET_KEY = "command_center_live_packet"


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


def get_display_packet(state: Any, packet_key: str, last_success_key: str) -> dict:
    return cc_adapter.pick_display_packet(
        {
            packet_key: state_get(state, packet_key),
            last_success_key: state_get(state, last_success_key),
        },
        packet_key,
        last_success_key,
    )


def get_command_center_packets_from_state(
    state: Any,
    live_packet_key: str = DEFAULT_LIVE_PACKET_KEY,
    strategy_packet_key: str = "",
    strategy_last_success_key: str = "",
    decision_packet_key: str = "",
    decision_last_success_key: str = "",
) -> dict:
    return {
        "live_packet": cc_adapter.clone_packet(state_get(state, live_packet_key)),
        "strategy_execution_packet": (
            get_display_packet(state, strategy_packet_key, strategy_last_success_key)
            if strategy_packet_key and strategy_last_success_key
            else {}
        ),
        "decision_packet": (
            get_display_packet(state, decision_packet_key, decision_last_success_key)
            if decision_packet_key and decision_last_success_key
            else {}
        ),
    }


def attach_command_center_child_packets_for_display(
    live_packet: Any,
    strategy_execution_packet: Any = None,
    decision_packet: Any = None,
    extra_child_packets: dict[str, Any] | None = None,
) -> dict:
    payload = cc_adapter.clone_packet(live_packet)
    payload = cc_adapter.attach_child_packet(
        payload,
        "strategy_execution",
        strategy_execution_packet,
    )
    payload = cc_adapter.attach_child_packet(payload, "decision", decision_packet)

    for child_key, child_packet in (extra_child_packets or {}).items():
        payload = cc_adapter.attach_child_packet(payload, child_key, child_packet)
    return payload


def build_command_center_view_model_from_state(
    state: Any,
    live_packet: Any = None,
    live_packet_key: str = DEFAULT_LIVE_PACKET_KEY,
    strategy_packet_key: str = "",
    strategy_last_success_key: str = "",
    decision_packet_key: str = "",
    decision_last_success_key: str = "",
) -> dict:
    packets = get_command_center_packets_from_state(
        state,
        live_packet_key=live_packet_key,
        strategy_packet_key=strategy_packet_key,
        strategy_last_success_key=strategy_last_success_key,
        decision_packet_key=decision_packet_key,
        decision_last_success_key=decision_last_success_key,
    )
    effective_live_packet = live_packet if live_packet is not None else packets["live_packet"]
    view_model = cc_adapter.build_command_center_view_model(
        live_packet=effective_live_packet,
        strategy_execution_packet=packets["strategy_execution_packet"],
        decision_packet=packets["decision_packet"],
        refresh_level=cc_adapter.get_nested(effective_live_packet, "refresh_level"),
        generated_at=(
            cc_adapter.get_nested(effective_live_packet, "updated_at")
            or cc_adapter.get_nested(effective_live_packet, "generated_at")
        ),
    )
    return view_model
