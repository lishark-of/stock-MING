from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from numbers import Number
from typing import Any
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
TASK_TYPE = "refresh_margin_etf_local_packets"
TASK_ROUTE = "POST /api/market/margin-etf-local-refresh"
TASK_OUTPUT_PACKET_KEY = "command_center_margin_etf_refresh_receipt"
SOURCE_IDENTITY = "margin_etf_local_packet_replay.v1"
SOURCE_PROJECTION_SCHEMA_VERSION = "margin_etf_source_projection.v1"
REQUESTED_PACKET_KEYS = ["command_center_etf_packet", "command_center_margin_packet"]
FALSE_SAFETY_FIELDS = (
    "external",
    "external_calls_triggered",
    "provider_or_model_calls",
    "provider_called",
    "model_called",
    "worker_called",
    "tushare_called",
    "deepseek_called",
    "github_called",
    "trade_called",
    "trading_called",
    "broker_called",
    "order_called",
    "real_trading_enabled",
    "contains_secret",
)
TRUE_SAFETY_FIELDS = ("does_not_execute_trades", "does_not_modify_strategy_action")
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_TARGET_RE = re.compile(r"^\d{6}\.(?:SH|SZ|BJ)$")
_ETF_RE = re.compile(r"^\d{6}\.(?:SH|SZ)$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def strict_text(value: Any, *, limit: int = 160) -> str:
    if not isinstance(value, str) or value != value.strip() or not value or len(value) > limit:
        return ""
    return value


def strict_identity(value: Any, *, limit: int = 160) -> str:
    text = strict_text(value, limit=limit)
    return text if text and _IDENTITY_RE.fullmatch(text) else ""


def strict_hash(value: Any) -> str:
    text = strict_text(value, limit=64)
    return text if _HASH_RE.fullmatch(text) else ""


def strict_target(value: Any) -> str:
    text = strict_text(value, limit=9)
    return text if _TARGET_RE.fullmatch(text) else ""


def strict_yyyymmdd(value: Any) -> str:
    text = strict_text(value, limit=8)
    if len(text) != 8 or not text.isdigit():
        return ""
    try:
        parsed = dt.datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return ""
    return text if parsed.strftime("%Y%m%d") == text else ""


def strict_timestamp_shanghai(value: Any) -> dt.datetime | None:
    text = strict_text(value, limit=64)
    if not text or "T" not in text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI)


def canonical_timestamp_shanghai(value: Any) -> str:
    parsed = strict_timestamp_shanghai(value)
    return parsed.isoformat(timespec="seconds") if parsed is not None else ""


def strict_decimal_text(value: Any, *, minimum: float, maximum: float) -> str:
    if isinstance(value, bool) or not isinstance(value, Number):
        return ""
    number = float(value)
    if not math.isfinite(number) or number < minimum or number > maximum:
        return ""
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return ""
    text = format(decimal, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def safety_projection(packet: Mapping[str, Any]) -> dict[str, bool] | None:
    explicit_fields = packet.get("cache_api_explicit_safety_fields")
    required_fields = {*FALSE_SAFETY_FIELDS, *TRUE_SAFETY_FIELDS}
    if explicit_fields is not None and (
        not isinstance(explicit_fields, list)
        or not all(isinstance(field, str) for field in explicit_fields)
        or set(explicit_fields) != required_fields
    ):
        return None
    if not isinstance(packet.get("warnings"), list) or packet.get("warnings") != []:
        return None
    if not all(packet.get(field) is False for field in FALSE_SAFETY_FIELDS):
        return None
    if not all(packet.get(field) is True for field in TRUE_SAFETY_FIELDS):
        return None
    return {
        **{field: False for field in FALSE_SAFETY_FIELDS},
        **{field: True for field in TRUE_SAFETY_FIELDS},
    }


def _candidate_projection(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        return []
    result: list[dict[str, str]] = []
    for raw in value[:3]:
        if not isinstance(raw, Mapping):
            return []
        code = strict_text(raw.get("code"), limit=9)
        name = strict_text(raw.get("name"), limit=120)
        reason = strict_text(raw.get("reason"), limit=500)
        if not _ETF_RE.fullmatch(code) or not name or not reason:
            return []
        result.append({"code": code, "name": name, "reason": reason})
    return result


def build_source_projection(
    etf_packet: Any,
    margin_packet: Any,
    *,
    target: Any,
) -> dict[str, Any] | None:
    if not isinstance(etf_packet, Mapping) or not isinstance(margin_packet, Mapping):
        return None
    target_text = strict_target(target)
    etf_safety = safety_projection(etf_packet)
    margin_safety = safety_projection(margin_packet)
    etf_date = strict_yyyymmdd(etf_packet.get("data_date"))
    margin_date = strict_yyyymmdd(margin_packet.get("trade_date"))
    etf_updated = canonical_timestamp_shanghai(etf_packet.get("updated_at"))
    margin_updated = canonical_timestamp_shanghai(margin_packet.get("updated_at"))
    candidates = _candidate_projection(etf_packet.get("recommended_etfs"))
    available_cash = strict_decimal_text(etf_packet.get("available_cash"), minimum=0, maximum=1_000_000_000_000_000)
    recommended_cash_ratio = strict_decimal_text(etf_packet.get("recommended_cash_ratio"), minimum=0, maximum=100)
    current_margin_ratio = strict_decimal_text(etf_packet.get("current_margin_ratio"), minimum=0, maximum=100)
    recommended_margin_ratio = strict_decimal_text(etf_packet.get("recommended_margin_ratio"), minimum=0, maximum=100)
    financing_balance = strict_decimal_text(margin_packet.get("financing_balance_yi"), minimum=0, maximum=1_000_000_000)
    financing_buy = strict_decimal_text(margin_packet.get("financing_buy_yi"), minimum=-1_000_000_000, maximum=1_000_000_000)
    margin_balance = strict_decimal_text(margin_packet.get("margin_balance_yi"), minimum=0, maximum=1_000_000_000)
    margin_fields_present = all(
        margin_packet.get(field) not in (None, "")
        for field in ("financing_balance_yi", "financing_buy_yi", "margin_balance_yi")
    )
    source_labels = {
        "etf": strict_text(etf_packet.get("source"), limit=240),
        "margin": strict_text(margin_packet.get("source"), limit=240),
    }
    ready = bool(
        target_text
        and etf_safety
        and margin_safety
        and etf_date
        and etf_date == margin_date
        and etf_updated
        and margin_updated
        and strict_text(etf_packet.get("status"), limit=32).lower() == "ready"
        and strict_text(etf_packet.get("data_status") or etf_packet.get("cache_state"), limit=32).lower() == "ready"
        and strict_text(margin_packet.get("status"), limit=32).lower() == "ready"
        and strict_text(margin_packet.get("data_status") or margin_packet.get("cache_state"), limit=32).lower() == "ready"
        and strict_text(etf_packet.get("verification_status"), limit=32) == "已验证"
        and strict_text(margin_packet.get("verification_status"), limit=32) == "已验证"
        and source_labels["etf"]
        and source_labels["margin"]
        and candidates
        and available_cash
        and recommended_cash_ratio
        and current_margin_ratio
        and recommended_margin_ratio
        and margin_fields_present
        and financing_balance
        and financing_buy
        and margin_balance
        and isinstance(etf_packet.get("allow_new_margin"), bool)
    )
    if not ready:
        return None
    return {
        "schema_version": SOURCE_PROJECTION_SCHEMA_VERSION,
        "target": target_text,
        "packet_keys": list(REQUESTED_PACKET_KEYS),
        "etf": {
            "status": "ready",
            "data_status": "ready",
            "data_date": etf_date,
            "updated_at": etf_updated,
            "source": source_labels["etf"],
            "verification_status": "已验证",
            "available_cash": available_cash,
            "recommended_cash_ratio": recommended_cash_ratio,
            "current_margin_ratio": current_margin_ratio,
            "recommended_margin_ratio": recommended_margin_ratio,
            "allow_new_margin": etf_packet.get("allow_new_margin"),
            "recommended_etfs": candidates,
            "safety": etf_safety,
            "warnings": [],
        },
        "margin": {
            "status": "ready",
            "data_status": "ready",
            "trade_date": margin_date,
            "updated_at": margin_updated,
            "source": source_labels["margin"],
            "verification_status": "已验证",
            "financing_balance_yi": financing_balance,
            "financing_buy_yi": financing_buy,
            "margin_balance_yi": margin_balance,
            "safety": margin_safety,
            "warnings": [],
        },
    }


def build_source_scope_material(*, target: str, source_projection_sha256: str) -> dict[str, Any]:
    result_version = f"margin-etf-source:{source_projection_sha256}"
    return {
        "route": TASK_ROUTE,
        "mode": "local_packet_replay",
        "requested_packet_keys": list(REQUESTED_PACKET_KEYS),
        "target": target,
        "source_identity": SOURCE_IDENTITY,
        "source_result_version": result_version,
        "source_projection_sha256": source_projection_sha256,
    }
