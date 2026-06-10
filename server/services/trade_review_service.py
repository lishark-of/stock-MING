from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import trade_review_log


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRADE_REVIEW_LOG_PATH = trade_review_log.DEFAULT_LOG_PATH
PACKET_KEY = "command_center_3_trade_review_cache"
SCHEMA_VERSION = "trade_review_cache.v1"

SENSITIVE_KEY_PARTS = (
    "secret",
    "token",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "credential",
    "authorization",
)
SENSITIVE_TEXT_MARKERS = (
    "traceback",
    "api_key",
    "apikey",
    "authorization:",
    "bearer ",
    "token=",
    "secret=",
    "password=",
    "passwd=",
)


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _path_label(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


def _is_sensitive_key(key: Any) -> bool:
    lower = str(key or "").lower()
    return any(part in lower for part in SENSITIVE_KEY_PARTS)


def _safe_string(value: Any, *, limit: int = 800) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    if any(marker in lower for marker in SENSITIVE_TEXT_MARKERS):
        return "[redacted_sensitive_text]"
    return text[:limit]


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    return _safe_string(value)


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 3:
        return "[truncated]"
    if isinstance(value, Mapping):
        return {
            _safe_string(key, limit=80): _safe_value(val, depth=depth + 1)
            for key, val in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:20]]
    if isinstance(value, tuple):
        return [_safe_value(item, depth=depth + 1) for item in value[:20]]
    return _safe_scalar(value)


def _safe_records(records: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in records if isinstance(records, list) else []:
        if not isinstance(item, Mapping):
            continue
        sanitized = _safe_value(item)
        if isinstance(sanitized, dict):
            result.append(sanitized)
    return result


def _json_safe(payload: Any) -> Any:
    try:
        return json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "trade_review_cache_not_json_serializable"}


def read_trade_review_cache(limit: int = 20, path: Any = None) -> dict[str, Any]:
    log_path = Path(path) if path else TRADE_REVIEW_LOG_PATH
    safe_limit = max(1, min(int(limit or 20), 100))
    source_exists = log_path.exists()
    call_status = "cache_missing"
    warnings: list[str] = []
    records: list[dict[str, Any]] = []
    summary: dict[str, Any] = trade_review_log.summarize_trade_review_records([])
    status = "cache_missing"
    error_message_safe = None

    if source_exists:
        try:
            raw_records = trade_review_log.load_trade_review_records(limit=safe_limit, path=log_path)
            records = _safe_records(raw_records)
            summary = _safe_value(trade_review_log.summarize_trade_review_records(records))
            summary = summary if isinstance(summary, dict) else {}
            status = "ready" if records else "empty"
            call_status = "cache_read"
        except Exception:
            records = []
            summary = trade_review_log.summarize_trade_review_records([])
            status = "read_error"
            call_status = "read_error"
            error_message_safe = "trade_review_cache_read_failed"
            warnings.append("交易复盘本地日志读取失败；已隐藏底层异常细节。")
    else:
        warnings.append("本地交易复盘日志不存在；3.0 只读页不会创建或刷新日志。")

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "cache_only": True,
        "read_only": True,
        "source_path_safe": _path_label(log_path),
        "source_exists": source_exists,
        "loaded_at": _now_iso(),
        "limit": safe_limit,
        "record_count": len(records),
        "records": records,
        "summary": summary,
        "call_ledger": [
            {
                "api": "local_trade_review_log",
                "source_path_safe": _path_label(log_path),
                "row_count": len(records),
                "call_status": call_status,
                "local_fetched_at": _now_iso(),
                "external": False,
            }
        ],
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "does_not_write_cache": True,
        "contains_secret": False,
        "error_message_safe": error_message_safe,
        "warnings": warnings,
    }
    return _json_safe(packet)
