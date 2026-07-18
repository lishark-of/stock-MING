"""Durable, disk-verifiable Tushare production acceptance storage.

The SQLite packets produced by the task layer are indexes, not truth.  Truth is
the immutable version selected by ``pointer.json`` and is accepted only after
all Parquet files and the provider-run receipt embedded in the manifest are
read back from disk and recomputed.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping


DATASETS = ("stock_basic", "trade_cal", "daily", "daily_basic", "moneyflow")
MIN_UNIVERSE_ROWS = 3000
REQUIRED_SESSIONS = 90
MAX_PROVIDER_CALLS = 300
POINTER_SCHEMA = "tushare_production_pointer.v2"
MANIFEST_SCHEMA = "tushare_production_version_manifest.v2"
EXECUTION_EVENT_SCHEMA = "tushare_official_execution_event.v2"
TRANSPORT_EVENT_SCHEMA = "tushare_inline_transport_evidence.v2"
EXACT_REFRESH_APIS = (
    "daily", "daily_basic", "moneyflow", "trade_cal", "margin_detail", "top_list",
    "top_inst", "stk_limit", "limit_list_d", "limit_cpt_list", "cyq_perf", "cyq_chips",
    "anns_d", "forecast", "fina_indicator", "stk_holdertrade", "share_float", "pledge_stat",
    "pledge_detail", "stk_surv",
)
EXACT_TARGET_GROUPS = (
    "trade_calendar", "margin_financing", "dragon_tiger", "limit_emotion",
    "chip_distribution", "financial_disclosure", "hard_risk",
)
EXACT_SUPPORT_APIS = ("stock_basic",)
REQUIRED_COLUMNS = {
    "stock_basic": ("ts_code", "exchange", "list_status", "list_date"),
    "trade_cal": ("cal_date", "is_open"),
    "daily": ("ts_code", "trade_date", "close", "amount"),
    "daily_basic": ("ts_code", "trade_date", "turnover_rate", "total_mv", "circ_mv"),
    "moneyflow": ("ts_code", "trade_date", "buy_lg_amount", "sell_lg_amount"),
}
EXCHANGE_SUFFIX = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}
SH_PREFIXES = ("600", "601", "603", "605", "688", "689")
SZ_PREFIXES = ("000", "001", "002", "003", "300", "301", "302")
BJ_PREFIXES = ("4", "8", "920")
__all__ = (
    "is_listed_a_share_code",
    "validate_tushare_full_market_production_version",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _digest_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_bytes(path, _canonical_bytes(dict(value)))


def _date(value: Any) -> str:
    return str(value or "").strip().replace("-", "")


def _code_family_valid(code: str, suffix: str) -> bool:
    prefix = code.split(".", 1)[0]
    return bool(
        (suffix == "SH" and prefix.startswith(SH_PREFIXES))
        or (suffix == "SZ" and prefix.startswith(SZ_PREFIXES))
        or (suffix == "BJ" and prefix.startswith(BJ_PREFIXES))
    )


def is_listed_a_share_code(value: Any) -> bool:
    """Return whether a Tushare code belongs to a supported listed A-share family."""

    text = str(value or "").strip().upper()
    prefix, separator, suffix = text.partition(".")
    return bool(
        separator
        and len(prefix) == 6
        and prefix.isdigit()
        and _code_family_valid(text, suffix)
    )


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    if hasattr(value, "where") and hasattr(value, "notna"):
        return value.where(value.notna(), None).to_dict("records")
    return []


def _artifact_summary(path: Path, *, name: str) -> dict[str, Any]:
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    frame = table.to_pandas()
    dates: list[str] = []
    for column in ("trade_date", "cal_date", "list_date"):
        if column in frame.columns:
            dates.extend(_date(value) for value in frame[column].dropna().tolist())
    symbols = (
        {str(value).upper() for value in frame["ts_code"].dropna().tolist()}
        if "ts_code" in frame.columns
        else set()
    )
    return {
        "file": f"{name}.parquet",
        "sha256": _sha256_file(path),
        "rows": int(table.num_rows),
        "columns": sorted(str(column) for column in table.column_names),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
        "symbol_count": len(symbols),
    }


def validate_datasets(
    datasets: Mapping[str, Any],
    *,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Validate provider rows against the authoritative listed universe."""

    material = {name: _rows(datasets.get(name)) for name in DATASETS}
    blockers: list[str] = []
    if set(material) != set(DATASETS):
        blockers.append("dataset_set_incomplete")
    for name, required in REQUIRED_COLUMNS.items():
        rows = material[name]
        if not rows:
            blockers.append(f"{name}_empty")
            continue
        missing = sorted({column for column in required if any(column not in row for row in rows)})
        if missing:
            blockers.append(f"{name}_missing_columns:{','.join(missing)}")

    stock_rows = material["stock_basic"]
    universe: set[str] = set()
    exchanges: set[str] = set()
    list_dates: dict[str, str] = {}
    for row in stock_rows:
        code = str(row.get("ts_code") or "").upper()
        exchange = str(row.get("exchange") or "").upper()
        list_status = str(row.get("list_status") or "").upper()
        list_date = _date(row.get("list_date"))
        suffix = code.rsplit(".", 1)[-1] if "." in code else ""
        if (
            exchange not in EXCHANGE_SUFFIX
            or suffix != EXCHANGE_SUFFIX.get(exchange)
            or not is_listed_a_share_code(code)
            or list_status != "L"
            or len(list_date) != 8
            or not list_date.isdigit()
        ):
            blockers.append("stock_basic_exchange_suffix_or_membership_invalid")
            continue
        if code in universe:
            blockers.append("stock_basic_duplicate_symbol")
        universe.add(code)
        exchanges.add(exchange)
        list_dates[code] = list_date
    if len(universe) < MIN_UNIVERSE_ROWS:
        blockers.append("stock_basic_authoritative_universe_too_small")
    if exchanges != set(EXCHANGE_SUFFIX):
        blockers.append("stock_basic_three_exchange_coverage_incomplete")

    start = _date(start_date)
    end = _date(end_date)
    if len(start) != 8 or len(end) != 8 or start > end:
        blockers.append("invalid_requested_date_scope")
    trade_rows = material["trade_cal"]
    open_dates: set[str] = set()
    seen_calendar: set[str] = set()
    for row in trade_rows:
        cal_date = _date(row.get("cal_date"))
        exchange = str(row.get("exchange") or "SSE").upper()
        if not (start <= cal_date <= end) or exchange not in {"", "SSE"}:
            blockers.append("trade_cal_row_outside_scope")
        if cal_date in seen_calendar:
            blockers.append("trade_cal_duplicate_date")
        seen_calendar.add(cal_date)
        if str(row.get("is_open") or "0").lower() in {"1", "true"}:
            open_dates.add(cal_date)
    selected_dates = sorted(open_dates)[-REQUIRED_SESSIONS:]
    if len(selected_dates) != REQUIRED_SESSIONS:
        blockers.append("trade_cal_required_sessions_incomplete")
    selected_set = set(selected_dates)
    latest = selected_dates[-1] if selected_dates else ""
    eligible = (
        {
            code
            for code in universe
            if list_dates.get(code, "") <= selected_dates[0]
        }
        if selected_dates
        else set()
    )
    excluded_recent = universe - eligible
    if len(eligible) < MIN_UNIVERSE_ROWS:
        blockers.append("eligible_scored_universe_too_small")

    dataset_validation: dict[str, Any] = {}
    for name in ("daily", "daily_basic", "moneyflow"):
        rows = material[name]
        keys: set[tuple[str, str]] = set()
        counts: dict[str, int] = {}
        latest_symbols: set[str] = set()
        for row in rows:
            code = str(row.get("ts_code") or "").upper()
            trade_date = _date(row.get("trade_date"))
            key = (code, trade_date)
            if code not in universe:
                blockers.append(f"{name}_symbol_outside_authoritative_universe")
            if trade_date not in selected_set:
                blockers.append(f"{name}_date_outside_calendar_scope")
            if code in list_dates and trade_date < list_dates[code]:
                blockers.append(f"{name}_date_before_authoritative_list_date")
            if key in keys:
                blockers.append(f"{name}_duplicate_symbol_date")
            keys.add(key)
            counts[code] = counts.get(code, 0) + 1
            if trade_date == latest and code in eligible:
                latest_symbols.add(code)
        minimum = REQUIRED_SESSIONS if name == "daily" else 1 if name == "daily_basic" else min(5, REQUIRED_SESSIONS)
        required_symbols = eligible
        covered = {code for code, count in counts.items() if count >= minimum}
        complete = bool(required_symbols and required_symbols.issubset(covered))
        if not complete:
            blockers.append(f"{name}_coverage_incomplete")
        if name == "daily_basic" and latest_symbols != eligible:
            blockers.append("daily_basic_latest_trade_date_coverage_incomplete")
        dataset_validation[name] = {
            "rows": len(rows),
            "covered_symbol_count": len(covered & eligible),
            "required_symbol_count": len(required_symbols),
            "minimum_sessions_per_symbol": minimum,
            "latest_trade_date_symbol_count": len(latest_symbols),
            "coverage_complete": complete,
        }
    production_datasets = {
        "stock_basic": material["stock_basic"],
        "trade_cal": material["trade_cal"],
        **{
            name: [
                row
                for row in material[name]
                if str(row.get("ts_code") or "").upper() in eligible
            ]
            for name in ("daily", "daily_basic", "moneyflow")
        },
    }
    blockers = sorted(set(blockers))
    return {
        "ready": not blockers,
        "blockers": blockers,
        "datasets": production_datasets,
        "dataset_validation": dataset_validation,
        "universe_count": len(eligible),
        "symbols": sorted(eligible),
        "universe_digest": _digest_value(sorted(eligible)),
        "eligible_universe_count": len(eligible),
        "eligible_universe_digest": _digest_value(sorted(eligible)),
        "excluded_recent_symbols": sorted(excluded_recent),
        "excluded_recent_count": len(excluded_recent),
        "excluded_recent_digest": _digest_value(sorted(excluded_recent)),
        "current_listed_count": len(universe),
        "current_listed_digest": _digest_value(sorted(universe)),
        "scored_universe_policy": "listed_L_on_or_before_selected_90_session_start",
        "exchanges": sorted(exchanges),
        "selected_trade_dates": selected_dates,
        "latest_trade_date": latest,
        "start_date": start,
        "end_date": end,
    }


def _sha256_text(value: Any) -> bool:
    text = str(value or "").lower()
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _receipt_ready(receipt: Any, *, scope_hash: str) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    material = dict(receipt)
    digest = str(material.pop("execution_event_digest", "") or "")
    raw_transport_events = receipt.get("transport_evidence", [])
    transport_events = [
        dict(row)
        for row in raw_transport_events
        if isinstance(row, Mapping)
    ]
    if len(transport_events) != len(raw_transport_events):
        return False
    for event in transport_events:
        event_material = dict(event)
        event_digest = str(event_material.pop("transport_event_digest", "") or "")
        if not (
            event.get("schema_version") == TRANSPORT_EVENT_SCHEMA
            and event.get("run_id") == receipt.get("run_id")
            and event.get("attempt_id") == receipt.get("attempt_id")
            and event.get("scope_hash") == scope_hash
            and event.get("actual_function_call") is True
            and int(event.get("function_call_count") or 0) > 0
            and _sha256_text(event.get("request_scope_digest"))
            and _sha256_text(event.get("transport_receipt_digest"))
            and _sha256_text(event.get("response_digest"))
            and event_digest == _digest_value(event_material)
        ):
            return False
    observed_apis = {str(event.get("api") or "") for event in transport_events}
    total_calls = sum(int(event.get("function_call_count") or 0) for event in transport_events)
    current_calls = int(receipt.get("current_attempt_actual_function_call_count") or 0)
    exact_apis = list(EXACT_REFRESH_APIS)
    exact_targets = list(EXACT_TARGET_GROUPS)
    return bool(
        receipt.get("schema_version") == EXECUTION_EVENT_SCHEMA
        and receipt.get("source") == "public_non_injected_tushare_executor"
        and receipt.get("status") == "official_provider_execution_complete"
        and receipt.get("official_provider_path_completed") is True
        and receipt.get("run_id") == scope_hash
        and receipt.get("scope_hash") == scope_hash
        and len(str(receipt.get("attempt_id") or "")) == 32
        and all(character in "0123456789abcdef" for character in str(receipt.get("attempt_id") or ""))
        and _sha256_text(receipt.get("approval_scope_hash"))
        and _sha256_text(receipt.get("execution_recipe_scope_hash"))
        and receipt.get("required_interface_apis") == exact_apis
        and receipt.get("required_interface_api_digest") == _digest_value(exact_apis)
        and receipt.get("required_target_groups") == exact_targets
        and receipt.get("required_target_group_digest") == _digest_value(exact_targets)
        and receipt.get("required_support_apis") == list(EXACT_SUPPORT_APIS)
        and receipt.get("required_support_api_digest") == _digest_value(list(EXACT_SUPPORT_APIS))
        and observed_apis == set(EXACT_REFRESH_APIS) | set(EXACT_SUPPORT_APIS)
        and 0 < total_calls <= MAX_PROVIDER_CALLS
        and int(receipt.get("original_actual_function_call_count") or 0) == total_calls
        and current_calls == total_calls
        and int(receipt.get("checkpoint_reused_function_call_count") or 0) == 0
        and len({str(event.get("transport_event_digest") or "") for event in transport_events})
        == len(transport_events)
        and _sha256_text(receipt.get("production_dataset_digest"))
        and _sha256_text(receipt.get("production_dataset_validation_digest"))
        and _sha256_text(receipt.get("production_universe_digest"))
        and _sha256_text(receipt.get("selected_trade_dates_digest"))
        and receipt.get("contains_secret") is False
        and receipt.get("tushare_called") is True
        and receipt.get("tushare_called_this_attempt") is True
        and receipt.get("external_calls_triggered") is True
        and receipt.get("does_not_execute_trades") is True
        and digest == _digest_value(material)
    )


def _receipt_dataset_binding_ready(receipt: Mapping[str, Any], validation: Mapping[str, Any]) -> bool:
    return bool(
        receipt.get("production_dataset_digest") == _digest_value(validation.get("datasets"))
        and receipt.get("production_dataset_validation_digest")
        == _digest_value(validation.get("dataset_validation"))
        and receipt.get("production_universe_digest") == validation.get("universe_digest")
        and receipt.get("selected_trade_dates_digest")
        == _digest_value(validation.get("selected_trade_dates"))
    )


def _pointer_payload(
    version_id: str,
    manifest_digest: str,
    previous_pointer: Mapping[str, Any] | None,
) -> dict[str, Any]:
    previous_current = str((previous_pointer or {}).get("current_version") or "")
    previous_manifest = str((previous_pointer or {}).get("current_manifest_digest") or "")
    pointer = {
        "schema_version": POINTER_SCHEMA,
        "current_version": version_id,
        "last_good_version": previous_current or version_id,
        "current_manifest_digest": manifest_digest,
        "last_good_manifest_digest": previous_manifest or manifest_digest,
    }
    pointer["pointer_digest"] = _digest_value(pointer)
    return pointer


def _restore_pointer(pointer_path: Path, previous: bytes | None) -> bool:
    """Idempotently restore the exact pre-promotion pointer."""

    try:
        if previous is None:
            if pointer_path.exists():
                pointer_path.unlink()
        else:
            _atomic_bytes(pointer_path, previous)
        return (not pointer_path.exists()) if previous is None else pointer_path.read_bytes() == previous
    except Exception:
        return False


def verify_current_version(root: Path) -> dict[str, Any]:
    blockers: list[str] = []
    pointer_path = root / "pointer.json"
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except Exception:
        return {"ready": False, "blockers": ["pointer_missing_or_invalid"]}
    pointer_material = dict(pointer)
    pointer_digest = str(pointer_material.pop("pointer_digest", "") or "")
    if pointer.get("schema_version") != POINTER_SCHEMA or pointer_digest != _digest_value(pointer_material):
        blockers.append("pointer_digest_invalid")
    current = str(pointer.get("current_version") or "")
    last_good = str(pointer.get("last_good_version") or "")
    if (
        not current
        or not last_good
        or any(value for value in ("/", "..") if value in current or value in last_good)
    ):
        blockers.append("current_last_good_version_invalid")
    version_dir = root / "versions" / current
    expected_files = {"manifest.json", *(f"{name}.parquet" for name in DATASETS)}
    if not version_dir.is_dir() or {path.name for path in version_dir.iterdir()} != expected_files:
        blockers.append("immutable_version_file_set_invalid")
    try:
        manifest = json.loads((version_dir / "manifest.json").read_text(encoding="utf-8"))
    except Exception:
        return {"ready": False, "blockers": sorted(set(blockers + ["manifest_missing_or_invalid"]))}
    manifest_material = dict(manifest)
    manifest_digest = str(manifest_material.pop("manifest_digest", "") or "")
    if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest_digest != _digest_value(manifest_material):
        blockers.append("manifest_digest_invalid")
    if pointer.get("current_manifest_digest") != manifest_digest or manifest.get("version_id") != current:
        blockers.append("pointer_manifest_binding_invalid")
    scope = manifest.get("scope") if isinstance(manifest.get("scope"), Mapping) else {}
    receipt = manifest.get("official_run_receipt") if isinstance(manifest.get("official_run_receipt"), Mapping) else {}
    if not _receipt_ready(receipt, scope_hash=str(scope.get("scope_hash") or "")):
        blockers.append("official_provider_receipt_invalid")

    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), Mapping) else {}
    recomputed: dict[str, Any] = {}
    frames: dict[str, Any] = {}
    try:
        import pyarrow.parquet as pq

        for name in DATASETS:
            path = version_dir / f"{name}.parquet"
            recomputed[name] = _artifact_summary(path, name=name)
            frames[name] = pq.read_table(path).to_pandas()
            if recomputed[name] != artifacts.get(name):
                blockers.append(f"{name}_artifact_readback_mismatch")
    except Exception:
        blockers.append("parquet_readback_failed")
    if len(frames) == len(DATASETS):
        validation = validate_datasets(
            frames,
            start_date=str(scope.get("start_date") or ""),
            end_date=str(scope.get("end_date") or ""),
        )
        if not validation["ready"]:
            blockers.extend(f"disk_{item}" for item in validation["blockers"])
        if not _receipt_dataset_binding_ready(receipt, validation):
            blockers.append("official_provider_receipt_dataset_binding_invalid")
        if validation.get("dataset_validation") != manifest.get("dataset_validation"):
            blockers.append("dataset_validation_readback_mismatch")
        if validation.get("latest_trade_date") != scope.get("latest_trade_date"):
            blockers.append("latest_trade_date_readback_mismatch")
        if validation.get("universe_count") != scope.get("universe_count"):
            blockers.append("universe_count_readback_mismatch")
        if validation.get("universe_digest") != scope.get("universe_digest"):
            blockers.append("universe_digest_readback_mismatch")
        if validation.get("exchanges") != scope.get("exchanges"):
            blockers.append("exchange_coverage_readback_mismatch")
        if validation.get("selected_trade_dates") != scope.get("selected_trade_dates"):
            blockers.append("trade_session_scope_readback_mismatch")
        for field in (
            "current_listed_count",
            "current_listed_digest",
            "eligible_universe_count",
            "eligible_universe_digest",
            "excluded_recent_symbols",
            "excluded_recent_count",
            "excluded_recent_digest",
            "scored_universe_policy",
        ):
            if validation.get(field) != scope.get(field):
                blockers.append(f"{field}_readback_mismatch")
    lineage = manifest.get("lineage") if isinstance(manifest.get("lineage"), Mapping) else {}
    if not (
        len(str(lineage.get("approval_scope_hash") or "")) == 64
        and len(str(lineage.get("execution_recipe_scope_hash") or "")) == 64
        and len(str(lineage.get("as_of") or "")) == 8
        and lineage.get("as_of") == scope.get("end_date")
        and receipt.get("approval_scope_hash") == lineage.get("approval_scope_hash")
        and receipt.get("execution_recipe_scope_hash") == lineage.get("execution_recipe_scope_hash")
    ):
        blockers.append("approval_recipe_as_of_lineage_invalid")
    version_material = {
        "scope": scope,
        "artifacts": artifacts,
        "dataset_validation": manifest.get("dataset_validation"),
        "official_run_receipt": receipt,
        "lineage": lineage,
    }
    version_digest = _digest_value(version_material)
    if manifest.get("version_digest") != version_digest:
        blockers.append("version_digest_readback_mismatch")
    if last_good == current and pointer.get("last_good_manifest_digest") != manifest_digest:
        blockers.append("last_good_manifest_binding_invalid")
    if last_good != current:
        last_dir = root / "versions" / last_good
        try:
            import pyarrow.parquet as pq

            last_manifest = json.loads((last_dir / "manifest.json").read_text(encoding="utf-8"))
            last_material = dict(last_manifest)
            last_digest = str(last_material.pop("manifest_digest", "") or "")
            if (
                {path.name for path in last_dir.iterdir()} != expected_files
                or last_manifest.get("schema_version") != MANIFEST_SCHEMA
                or last_manifest.get("version_id") != last_good
                or last_digest != _digest_value(last_material)
                or pointer.get("last_good_manifest_digest") != last_digest
            ):
                blockers.append("last_good_manifest_binding_invalid")
            last_artifacts = last_manifest.get("artifacts") if isinstance(last_manifest.get("artifacts"), Mapping) else {}
            last_frames: dict[str, Any] = {}
            for name in DATASETS:
                if _artifact_summary(last_dir / f"{name}.parquet", name=name) != last_artifacts.get(name):
                    blockers.append(f"last_good_{name}_artifact_readback_mismatch")
                last_frames[name] = pq.read_table(last_dir / f"{name}.parquet").to_pandas()
            last_scope = last_manifest.get("scope") if isinstance(last_manifest.get("scope"), Mapping) else {}
            last_lineage = last_manifest.get("lineage") if isinstance(last_manifest.get("lineage"), Mapping) else {}
            last_receipt = (
                last_manifest.get("official_run_receipt")
                if isinstance(last_manifest.get("official_run_receipt"), Mapping)
                else {}
            )
            last_validation = validate_datasets(
                last_frames,
                start_date=str(last_scope.get("start_date") or ""),
                end_date=str(last_scope.get("end_date") or ""),
            )
            last_version_material = {
                "scope": last_scope,
                "artifacts": last_artifacts,
                "dataset_validation": last_manifest.get("dataset_validation"),
                "official_run_receipt": last_receipt,
                "lineage": last_lineage,
            }
            if (
                not last_validation["ready"]
                or last_validation.get("universe_digest") != last_scope.get("universe_digest")
                or last_validation.get("selected_trade_dates") != last_scope.get("selected_trade_dates")
                or not _receipt_ready(
                    last_receipt,
                    scope_hash=str(last_scope.get("scope_hash") or ""),
                )
                or not _receipt_dataset_binding_ready(last_receipt, last_validation)
                or last_manifest.get("version_digest") != _digest_value(last_version_material)
                or last_receipt.get("approval_scope_hash") != last_lineage.get("approval_scope_hash")
                or last_receipt.get("execution_recipe_scope_hash")
                != last_lineage.get("execution_recipe_scope_hash")
            ):
                blockers.append("last_good_semantic_or_lineage_readback_failed")
        except Exception:
            blockers.append("last_good_version_readback_failed")
    blockers = sorted(set(blockers))
    return {
        "ready": not blockers,
        "blockers": blockers,
        "root": str(root),
        "pointer": pointer,
        "manifest": manifest,
        "artifacts": recomputed,
        "current_version": current,
        "last_good_version": last_good,
        "manifest_digest": manifest_digest,
        "version_digest": version_digest,
        "scope_hash": str(scope.get("scope_hash") or ""),
        "approval_scope_hash": str(lineage.get("approval_scope_hash") or ""),
        "execution_recipe_scope_hash": str(lineage.get("execution_recipe_scope_hash") or ""),
        "as_of": str(lineage.get("as_of") or ""),
        "universe_digest": str(scope.get("universe_digest") or ""),
        "universe_count": int(scope.get("universe_count") or 0),
        "validated_trade_date": str(scope.get("latest_trade_date") or ""),
        "symbols": list(validation.get("symbols") or []) if "validation" in locals() else [],
        "excluded_recent_symbols": list(scope.get("excluded_recent_symbols") or []),
        "excluded_recent_count": int(scope.get("excluded_recent_count") or 0),
        "excluded_recent_digest": str(scope.get("excluded_recent_digest") or ""),
        "current_listed_count": int(scope.get("current_listed_count") or 0),
        "current_listed_digest": str(scope.get("current_listed_digest") or ""),
        "scored_universe_policy": str(scope.get("scored_universe_policy") or ""),
    }


def validate_tushare_full_market_production_version(
    evidence_root: Path,
    *,
    include_frames: bool = False,
) -> dict[str, Any]:
    """The one shared read-only production truth verifier.

    ``evidence_root`` may be ``.stock_ming_3`` or the production-universe root
    itself.  No SQLite packet or in-memory task ledger is consulted.
    """

    candidate = Path(evidence_root)
    root = (
        candidate
        if (candidate / "pointer.json").is_file() or candidate.name == "full_market_universe"
        else candidate / "parquet" / "full_market_universe"
    )
    result = verify_current_version(root)
    shared = {
        "ready": result.get("ready") is True,
        "status": "production_version_verified" if result.get("ready") is True else "production_version_blocked",
        "blockers": list(result.get("blockers") or []),
        "scope_hash": str(result.get("scope_hash") or ""),
        "approval_scope_hash": str(result.get("approval_scope_hash") or ""),
        "execution_recipe_scope_hash": str(result.get("execution_recipe_scope_hash") or ""),
        "universe_digest": str(result.get("universe_digest") or ""),
        "universe_count": int(result.get("universe_count") or 0),
        "validated_trade_date": str(result.get("validated_trade_date") or ""),
        "as_of": str(result.get("as_of") or ""),
        "symbols": list(result.get("symbols") or []),
        "excluded_recent_symbols": list(result.get("excluded_recent_symbols") or []),
        "excluded_recent_count": int(result.get("excluded_recent_count") or 0),
        "excluded_recent_digest": str(result.get("excluded_recent_digest") or ""),
        "current_listed_count": int(result.get("current_listed_count") or 0),
        "current_listed_digest": str(result.get("current_listed_digest") or ""),
        "scored_universe_policy": str(result.get("scored_universe_policy") or ""),
        "artifact_manifest_digest": str(result.get("manifest_digest") or ""),
        "version_digest": str(result.get("version_digest") or ""),
        "current_version": str(result.get("current_version") or ""),
        "official_call_ledger_digest": str(
            (
                result.get("manifest", {}).get("official_run_receipt", {})
                if isinstance(result.get("manifest"), Mapping)
                else {}
            ).get("sanitized_call_ledger_digest")
            or ""
        ),
        "official_execution_event_digest": str(
            (
                result.get("manifest", {}).get("official_run_receipt", {})
                if isinstance(result.get("manifest"), Mapping)
                else {}
            ).get("execution_event_digest")
            or ""
        ),
    }
    if include_frames and shared["ready"]:
        import pyarrow.parquet as pq

        version_dir = root / "versions" / str(result.get("current_version") or "")
        shared["frames"] = {
            name: pq.read_table(version_dir / f"{name}.parquet").to_pandas()
            for name in DATASETS
        }
    return shared


def _review_external_promotion_request(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """External/module-level callers can only receive a non-production review."""

    return {
        "promotion_verified": False,
        "status": "module_level_promotion_disabled_use_public_non_injected_executor",
        "blockers": ["module_level_promotion_disabled"],
    }
