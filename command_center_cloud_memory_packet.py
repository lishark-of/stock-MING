from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from numbers import Number
from typing import Any


MAX_ITEMS = 5


def as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def to_int(value: Any, default: int = 0) -> int:
    if value in [None, ""]:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, Number):
        return int(value)
    try:
        return int(float(str(value).strip().replace(",", "")))
    except Exception:
        return default


def now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def parse_memory_content(value: Any = None) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    text = to_text(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return dict(parsed) if isinstance(parsed, Mapping) else {"raw_text": text}
    except Exception:
        return {"raw_text": text}


def normalize_memory_item(row: Any = None, *, source: str = "云端外脑") -> dict:
    payload = as_mapping(row)
    content = parse_memory_content(payload.get("content") or payload.get("report_content") or payload)
    metadata = as_mapping(content.get("metadata"))
    title = (
        to_text(content.get("core_view"))
        or to_text(content.get("summary"))
        or to_text(content.get("raw_text"))
        or to_text(payload.get("content"))
        or "历史投喂资料"
    )
    title = " ".join(title.split())[:160]
    memory_type = to_text(payload.get("memory_type") or content.get("memory_type") or content.get("document_type"), "memory")
    source_text = to_text(content.get("source") or metadata.get("source_file") or payload.get("source"), source)
    risks = [
        to_text(item)
        for item in as_list(content.get("risk_triggers") or content.get("invalid_conditions"))
        if to_text(item)
    ][:3]
    return {
        "id": payload.get("id"),
        "memory_type": memory_type,
        "title": title,
        "source": source_text,
        "status": to_text(content.get("status") or content.get("extraction_status"), "已保存"),
        "document_type": to_text(content.get("document_type") or metadata.get("document_type"), "unknown"),
        "created_at": to_text(payload.get("created_at") or content.get("created_at") or metadata.get("created_at")),
        "risk_triggers": risks,
        "reference_note": "历史投喂资料只作为待验证线索，不直接决定买卖。",
    }


def _build_from_existing(existing: Mapping[str, Any]) -> dict:
    items = [normalize_memory_item(item) for item in as_list(existing.get("items"))]
    status = to_text(existing.get("status"), "ready" if items else "waiting")
    updated_at = to_text(existing.get("updated_at") or existing.get("generated_at"), now_iso())
    summary = to_text(existing.get("summary"))
    if not summary:
        summary = f"已回流 {len(items)} 条云端记忆摘要。" if items else "暂无云端外脑记忆缓存。"
    return {
        **dict(existing),
        "status": status,
        "data_status": "ready" if items else "missing",
        "items": items[:MAX_ITEMS],
        "memory_count": to_int(existing.get("memory_count"), len(items)),
        "summary": summary,
        "updated_at": updated_at,
        "source": to_text(existing.get("source"), "云端外脑缓存"),
        "manual_required_text": "云端外脑只在旧版高级工具箱按钮触发后回流；首页不会自动读取 Supabase。",
        "decision_guardrail": "投喂资料是历史观点或待验证线索，不能直接作为买卖依据。",
        "deepseek_called": bool(existing.get("deepseek_called", False)),
    }


def build_command_center_cloud_memory_packet(state: Any = None, live_packet: Any = None) -> dict:
    state_map = as_mapping(state)
    existing = as_mapping(state_map.get("command_center_cloud_memory_packet"))
    if existing and existing.get("items") and not state_map.get("legacy_cloud_memories") and not state_map.get("legacy_cloud_memory_write_result"):
        return _build_from_existing(existing)

    memories = as_list(state_map.get("legacy_cloud_memories"))
    write_result = as_mapping(state_map.get("legacy_cloud_memory_write_result"))
    extract_result = as_mapping(state_map.get("legacy_cloud_memory_extract_result"))
    loaded_at = to_text(state_map.get("legacy_cloud_memories_loaded_at"))
    written_at = to_text(state_map.get("legacy_cloud_memory_written_at"))
    live_section = as_mapping(as_mapping(live_packet).get("cloud_memory"))
    items = [normalize_memory_item(item) for item in memories]
    if extract_result:
        items.insert(
            0,
            normalize_memory_item(
                {
                    "memory_type": "strategy",
                    "content": extract_result,
                    "source": extract_result.get("source") or "手动投喂",
                    "created_at": written_at,
                },
                source="云端外脑投喂",
            ),
        )
    memory_count = len(memories)
    written_count = to_int(write_result.get("brain_memory")) + to_int(write_result.get("stock_reports"))
    if items or written_count:
        status = "ready"
        summary = (
            f"已回流 {len(items[:MAX_ITEMS])} 条云端记忆摘要；本次写入 {written_count} 条。"
            if written_count
            else f"已回流 {len(items[:MAX_ITEMS])} 条云端记忆摘要。"
        )
    elif existing:
        return _build_from_existing(existing)
    else:
        status = "waiting"
        summary = "暂无云端外脑记忆缓存。进入高级工具箱读取云端记忆或投喂资料后，首页会自动回流摘要。"
    updated_at = written_at or loaded_at or to_text(live_section.get("updated_at")) or now_iso()
    return {
        "status": status,
        "data_status": "ready" if status == "ready" else "missing",
        "items": items[:MAX_ITEMS],
        "memory_count": memory_count,
        "written_count": written_count,
        "summary": summary,
        "updated_at": updated_at,
        "source": to_text(live_section.get("source"), "云端外脑缓存"),
        "manual_required_text": "云端外脑只在旧版高级工具箱按钮触发后回流；首页不会自动读取 Supabase。",
        "decision_guardrail": "投喂资料是历史观点或待验证线索，不能直接作为买卖依据。",
        "deepseek_called": False,
    }
