from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .full_market_industry_service import (
    MINIMUM_ELIGIBLE_SYMBOLS, PROJECT_ROOT, REQUIRED_EXCHANGES, SOURCE_API,
    _SYMBOL, _date, _digest, _exchange, _interval_blockers, _symbols,
)

PROVIDER_PAGE_SIZE = 2000
PROVIDER_MAX_PAGES_PER_PARTITION = 100
PROVIDER_IS_NEW_PARTITIONS = ("Y", "N")
PROVIDER_RAW_FIELDS = (
    "l1_code", "l1_name", "l2_code", "l2_name", "l3_code", "l3_name",
    "ts_code", "name", "in_date", "out_date", "is_new",
)
def _provider_failure_mode(value: Any) -> str:
    text = str(value or "").lower()
    if any(marker in text for marker in ("permission", "权限", "积分", "access denied")):
        return "permission_denied"
    if any(marker in text for marker in ("empty", "no data", "无数据")):
        return "no_data"
    return "provider_failure"


def _provider_rows(value: Any) -> tuple[list[dict[str, Any]], int]:
    if value is None:
        return [], 0
    if type(value) is list:
        return [dict(row) for row in value if type(row) is dict], sum(
            type(row) is not dict for row in value
        )
    if isinstance(value, Mapping):
        nested = value.get("rows")
        if type(nested) is list:
            return [dict(row) for row in nested if type(row) is dict], sum(
                type(row) is not dict for row in nested
            )
        return [dict(value)], 0
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            rows = to_dict(orient="records")
        except Exception:
            return [], 1
        if type(rows) is list:
            return [dict(row) for row in rows if type(row) is dict], sum(
                type(row) is not dict for row in rows
            )
    return [], 1

def _load_official_index_member_client() -> Any:
    import tushare_adapter

    expected = PROJECT_ROOT / "tushare_adapter.py"
    actual = Path(str(getattr(tushare_adapter, "__file__", "")))
    method = getattr(tushare_adapter, "_call_pro", None)
    if not callable(method) or actual.resolve() != expected.resolve():
        raise RuntimeError("official_index_member_all_adapter_unavailable")
    return tushare_adapter

def _current_provider_matches_request(
    evidence_root: Path,
    request: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    try:
        from server.services.tushare_production_store import (
            validate_tushare_full_market_production_version,
        )

        source = validate_tushare_full_market_production_version(
            evidence_root,
            include_frames=False,
        )
    except Exception as exc:
        return {}, [f"provider_universe_verifier_failed_{type(exc).__name__}"]
    provider = dict(source) if isinstance(source, Mapping) else {}
    symbols, duplicates, invalid = _symbols(provider.get("symbols"))
    scope = request.get("scope") if type(request.get("scope")) is dict else {}
    blockers = [str(item) for item in provider.get("blockers") or [] if str(item)]
    if provider.get("ready") is not True:
        blockers.append("current_provider_universe_not_ready")
    if duplicates or invalid or len(symbols) < MINIMUM_ELIGIBLE_SYMBOLS:
        blockers.append("current_provider_universe_identity_invalid")
    if provider.get("universe_count") != len(symbols):
        blockers.append("current_provider_universe_count_invalid")
    if provider.get("universe_digest") != _digest(symbols):
        blockers.append("current_provider_universe_digest_invalid")
    exact = {
        "eligible_symbol_count": len(symbols),
        "exchanges": sorted({_exchange(symbol) for symbol in symbols}),
        "universe_digest": provider.get("universe_digest"),
        "provider_scope_digest": provider.get("scope_hash"),
        "provider_version_digest": provider.get("version_digest")
        or provider.get("artifact_manifest_digest"),
        "validated_trade_date": _date(provider.get("validated_trade_date")),
    }
    for key, value in exact.items():
        if scope.get(key) != value:
            blockers.append(f"current_provider_request_{key}_mismatch")
    provider["symbols"] = symbols
    provider["scope_hash"] = str(provider.get("scope_hash") or "")
    provider["version_digest"] = str(
        provider.get("version_digest")
        or provider.get("artifact_manifest_digest")
        or ""
    )
    return provider, list(dict.fromkeys(blockers))

def _normalize_provider_rows(
    rows: list[dict[str, Any]],
    *,
    symbols: list[str],
    validated_trade_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    raw_rows: list[dict[str, Any]] = []
    normalized_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    seen_raw: set[str] = set()
    seen_normalized: set[str] = set()
    for source in rows:
        if any(
            isinstance(source.get(field), (Mapping, list, tuple, set))
            for field in PROVIDER_RAW_FIELDS
        ):
            blockers.append("provider_row_schema_invalid")
            continue
        raw = {
            field: (
                None
                if source.get(field) is None
                else str(source.get(field)).strip()
            )
            for field in PROVIDER_RAW_FIELDS
        }
        raw_digest = _digest(raw)
        if raw_digest in seen_raw:
            blockers.append("provider_duplicate_raw_row")
        seen_raw.add(raw_digest)
        raw_rows.append(raw)
        symbol = str(raw.get("ts_code") or "").upper()
        effective_from = _date(raw.get("in_date"))
        raw_out_date = raw.get("out_date")
        effective_to = _date(raw_out_date) if raw_out_date else None
        industry_code = next(
            (
                str(raw.get(key) or "").strip()
                for key in ("l3_code", "l2_code", "l1_code")
                if str(raw.get(key) or "").strip()
            ),
            "",
        )
        if (
            not _SYMBOL.fullmatch(symbol)
            or not effective_from
            or (raw_out_date and not effective_to)
            or not industry_code
            or raw.get("is_new") not in PROVIDER_IS_NEW_PARTITIONS
            or raw.get("is_new") != source.get("__query_is_new")
        ):
            blockers.append("provider_row_schema_invalid")
            continue
        normalized = {
            "effective_from": effective_from,
            "effective_to": effective_to,
            "industry_code": industry_code,
            "source_api": SOURCE_API,
            "ts_code": symbol,
        }
        normalized_digest = _digest(normalized)
        if normalized_digest in seen_normalized:
            blockers.append("provider_duplicate_normalized_row")
        seen_normalized.add(normalized_digest)
        normalized_rows.append(normalized)
    blockers.extend(
        _interval_blockers(
            normalized_rows,
            expected_symbols=symbols,
            validated_trade_date=validated_trade_date,
        )
    )
    return raw_rows, sorted(
        normalized_rows,
        key=lambda row: (
            row["ts_code"],
            row["effective_from"],
            str(row["effective_to"] or ""),
            row["industry_code"],
        ),
    ), list(dict.fromkeys(blockers))


def _collect_provider_pages(client: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    blockers: list[str] = []
    for partition in PROVIDER_IS_NEW_PARTITIONS:
        offset = 0
        terminal_page_observed = False
        for page_index in range(PROVIDER_MAX_PAGES_PER_PARTITION):
            params = {
                "is_new": partition,
                "limit": PROVIDER_PAGE_SIZE,
                "offset": offset,
            }
            try:
                official_call = getattr(client, "_call_pro", None)
                result = (
                    official_call(SOURCE_API, **params)
                    if callable(official_call)
                    else client.get_index_member_all(**params)
                )
            except Exception as exc:
                result = {
                    "ok": False,
                    "data": None,
                    "error": f"provider_exception_{type(exc).__name__}",
                }
            result = dict(result) if isinstance(result, Mapping) else {
                "ok": False,
                "data": None,
                "error": "provider_result_type_invalid",
            }
            page_rows, non_objects = _provider_rows(result.get("data"))
            failure_mode = (
                "none"
                if result.get("ok") is True and not non_objects
                else _provider_failure_mode(result.get("error"))
                if result.get("ok") is not True
                else "provider_result_type_invalid"
            )
            transport_call_id = str(result.get("transport_call_id") or "")
            try:
                transport = client.consume_transport_receipt(
                    transport_call_id,
                    SOURCE_API,
                )
            except Exception:
                transport = None
            transport = dict(transport) if isinstance(transport, Mapping) else {}
            transport_ready = bool(
                transport_call_id
                and transport.get("api") == SOURCE_API
                and transport.get("sdk_method_invoked") is True
                and transport.get("provider_response_received") is True
                and transport.get("official_client_identity_verified") is True
            )
            call_status = (
                "success"
                if result.get("ok") is True and page_rows and not non_objects and transport_ready
                else "no_data"
                if result.get("ok") is True and not page_rows and not non_objects and transport_ready
                else "permission_denied"
                if failure_mode == "permission_denied"
                else "failed"
            )
            ledger.append(
                {
                    "api": SOURCE_API,
                    "request_params_safe": params,
                    "partition": partition,
                    "page_index": page_index,
                    "row_count": len(page_rows),
                    "call_status": call_status,
                    "failure_mode": failure_mode,
                    "permission_denied": call_status == "permission_denied",
                    "no_data": call_status == "no_data",
                    "provider_transport_verified": transport_ready,
                    "transport_receipt_digest": _digest(transport) if transport else "",
                    "external": True,
                    "external_calls_triggered": True,
                    "tushare_called": True,
                    "deepseek_called": False,
                    "github_called": False,
                    "contains_secret": False,
                    "does_not_execute_trades": True,
                    "does_not_modify_strategy_action": True,
                }
            )
            if call_status not in {"success", "no_data"}:
                blockers.append(f"provider_page_{call_status}")
                return rows, ledger, blockers
            rows.extend({**row, "__query_is_new": partition} for row in page_rows)
            if len(page_rows) < PROVIDER_PAGE_SIZE:
                terminal_page_observed = True
                break
            offset += PROVIDER_PAGE_SIZE
        if not terminal_page_observed:
            blockers.append("provider_pagination_terminal_page_missing")
            return rows, ledger, blockers
    if not rows:
        blockers.append("provider_no_data")
    return rows, ledger, blockers
