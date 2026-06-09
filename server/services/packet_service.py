from __future__ import annotations

import datetime as _dt
import json
from typing import Any

import command_center_factor_research as factor_research
import command_center_next_session_projection as next_session_projection
import command_center_packet_registry as packet_registry
import command_center_serenity_method_radar as serenity_radar


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "packet could not be JSON serialized"}


def build_packet_registry_cache() -> dict[str, Any]:
    return json_safe(packet_registry.build_command_center_packet_registry())


def build_factor_quant_cache() -> dict[str, Any]:
    now = _now_iso()
    library = factor_research.build_factor_library_packet(now=now)
    ledger = factor_research.build_factor_data_ledger_packet(factor_library=library, now=now)
    return json_safe(
        factor_research.build_factor_quant_hub_packet(
            mode="cache_only",
            factor_library=library,
            data_ledger=ledger,
            serenity_packet=serenity_radar.build_serenity_method_radar_packet(now=now),
            now=now,
        )
    )


def build_serenity_cache() -> dict[str, Any]:
    return json_safe(serenity_radar.build_serenity_method_radar_packet(now=_now_iso()))


def build_next_session_cache() -> dict[str, Any]:
    return {
        "packet_key": next_session_projection.PACKET_KEY,
        "schema_version": next_session_projection.SCHEMA_VERSION,
        "mode": "cache_only",
        "status": "cache_missing",
        "summary": "Command Center 3.0 cache API 不触发 Tushare/DeepSeek；当前未接入持久化次日图谱缓存。",
        "deepseek_called": False,
        "tushare_called": False,
        "external_calls_triggered": False,
        "does_not_modify_action": True,
        "does_not_modify_operation_zones": True,
        "updated_at": _now_iso(),
    }


def build_chokepoint_cache() -> dict[str, Any]:
    return {
        "packet_key": "command_center_chokepoint_scan_packet",
        "schema_version": "chokepoint_scan.cache.v1",
        "mode": "cache_only",
        "status": "cache_missing",
        "summary": "产业链瓶颈扫描在 3.0 MVP 中仅暴露 cache/stub API；运行必须由按钮任务触发。",
        "deepseek_called": False,
        "tushare_called": False,
        "external_calls_triggered": False,
        "enters_strategy_action": False,
        "enters_next_session_projection": False,
        "updated_at": _now_iso(),
    }


PACKET_BUILDERS = {
    "command_center_packet_registry": build_packet_registry_cache,
    "command_center_factor_quant_hub_packet": build_factor_quant_cache,
    "command_center_serenity_method_radar_packet": build_serenity_cache,
    next_session_projection.PACKET_KEY: build_next_session_cache,
    "command_center_chokepoint_scan_packet": build_chokepoint_cache,
}


def list_packets() -> dict[str, Any]:
    registry = build_packet_registry_cache()
    specs = registry.get("packets") or registry.get("packet_specs") or []
    return {
        "schema_version": "command_center_3_packet_index.v1",
        "available_cache_keys": sorted(PACKET_BUILDERS),
        "registry_count": len(specs) if isinstance(specs, list) else 0,
        "registry": registry,
        "cache_api_policy": {
            "get_cache_external_calls": False,
            "post_tasks_button_gated": True,
            "does_not_modify_strategy_action": True,
        },
    }


def read_packet(packet_key: str) -> dict[str, Any]:
    builder = PACKET_BUILDERS.get(str(packet_key))
    if builder is None:
        return {
            "packet_key": packet_key,
            "status": "cache_missing",
            "summary": "3.0 MVP 尚未接入该 packet 的持久化 cache builder。",
            "deepseek_called": False,
            "tushare_called": False,
            "external_calls_triggered": False,
        }
    return builder()
