from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
import uuid


_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")


def dependency_status() -> dict[str, Any]:
    try:
        import pandas as pd  # noqa: F401
        import pyarrow  # noqa: F401
    except Exception as exc:
        return {"available": False, "error_message_safe": str(exc)}
    return {"available": True, "error_message_safe": ""}


def dataset_path(root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> Path:
    return Path(root) / f"{name}.parquet"


def partitioned_dataset_path(root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> Path:
    return Path(root) / name


def dataset_metadata(root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> dict[str, Any]:
    path = dataset_path(root=root, name=name)
    status = dependency_status()
    exists = path.exists()
    return {
        "status": "ready" if exists else "missing",
        "path": str(path),
        "exists": exists,
        "dependency": status,
        "size_bytes": path.stat().st_size if exists else 0,
        "external_calls_triggered": False,
    }


def dataset_schema_metadata(root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> dict[str, Any]:
    path = dataset_path(root=root, name=name)
    status = dependency_status()
    if not status["available"]:
        return {
            "status": "dependency_missing",
            "path": str(path),
            "exists": path.exists(),
            "columns": [],
            "column_count": 0,
            "row_count_metadata": None,
            "row_group_count": None,
            "schema_read_done": False,
            "reads_row_payloads": False,
            "external_calls_triggered": False,
            **status,
        }
    if not path.exists():
        return {
            "status": "missing",
            "path": str(path),
            "exists": False,
            "columns": [],
            "column_count": 0,
            "row_count_metadata": None,
            "row_group_count": None,
            "schema_read_done": False,
            "reads_row_payloads": False,
            "external_calls_triggered": False,
        }
    try:
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(path)
        columns = [str(name) for name in parquet_file.schema_arrow.names]
        metadata = parquet_file.metadata
    except Exception as exc:
        return {
            "status": "read_failed",
            "path": str(path),
            "exists": True,
            "columns": [],
            "column_count": 0,
            "row_count_metadata": None,
            "row_group_count": None,
            "schema_read_done": False,
            "reads_row_payloads": False,
            "error_message_safe": str(exc).splitlines()[0][:240],
            "external_calls_triggered": False,
        }
    return {
        "status": "ready",
        "path": str(path),
        "exists": True,
        "columns": columns,
        "column_count": len(columns),
        "row_count_metadata": int(metadata.num_rows) if metadata is not None else None,
        "row_group_count": int(metadata.num_row_groups) if metadata is not None else None,
        "schema_read_done": True,
        "reads_row_payloads": False,
        "external_calls_triggered": False,
    }


def partitioned_dataset_metadata(root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> dict[str, Any]:
    path = partitioned_dataset_path(root=root, name=name)
    status = dependency_status()
    exists = path.exists()
    files = list(path.rglob("*.parquet")) if exists and path.is_dir() else []
    return {
        "status": "ready" if files else ("empty" if exists else "missing"),
        "path": str(path),
        "exists": exists,
        "file_count": len(files),
        "dependency": status,
        "size_bytes": sum(item.stat().st_size for item in files),
        "partitioned": True,
        "external_calls_triggered": False,
    }


def factor_values_path(root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> Path:
    return dataset_path(root=root, name=name)


def factor_values_metadata(root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> dict[str, Any]:
    return dataset_metadata(root=root, name=name)


def write_dataset(df: Any, root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> dict[str, Any]:
    status = dependency_status()
    if not status["available"]:
        return {"status": "dependency_missing", **status}
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    out = dataset_path(root=root_path, name=name)
    df.to_parquet(out, index=False)
    return {"status": "written", "path": str(out), "row_count": int(len(df)), "external_calls_triggered": False}


def write_partitioned_dataset(
    df: Any,
    root: str | Path = ".stock_ming_3/parquet",
    name: str = "factor_values",
    partition_columns: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    status = dependency_status()
    if not status["available"]:
        return {"status": "dependency_missing", **status}
    columns = list(getattr(df, "columns", []))
    partitions = [str(item) for item in (partition_columns or []) if str(item)]
    missing = [column for column in partitions if column not in columns]
    root_path = Path(root)
    out = partitioned_dataset_path(root=root_path, name=name)
    if not partitions:
        return {
            "status": "partition_columns_missing",
            "path": str(out),
            "row_count": 0,
            "partition_columns": [],
            "missing_partition_columns": [],
            "external_calls_triggered": False,
        }
    if missing:
        return {
            "status": "partition_columns_missing",
            "path": str(out),
            "row_count": 0,
            "partition_columns": partitions,
            "missing_partition_columns": missing,
            "external_calls_triggered": False,
        }
    root_path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False, partition_cols=partitions)
    metadata = partitioned_dataset_metadata(root=root_path, name=name)
    return {
        "status": "written",
        "path": str(out),
        "row_count": int(len(df)),
        "partition_columns": partitions,
        "missing_partition_columns": [],
        "file_count": metadata.get("file_count", 0),
        "partitioned": True,
        "external_calls_triggered": False,
    }


def write_factor_values(df: Any, root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> dict[str, Any]:
    return write_dataset(df, root=root, name=name)


def _safe_component(value: str, *, field: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_COMPONENT_RE.fullmatch(text):
        raise ValueError(f"invalid_{field}")
    return text


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_json_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _version_manifest_record(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "version_id",
            "artifact_relpath",
            "artifact_sha256",
            "row_count",
            "columns",
            "required_columns",
            "created_at",
            "lineage",
            "contains_secret",
        )
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def versioned_dataset_pointer(
    root: str | Path = ".stock_ming_3/parquet",
    name: str = "research_result_lineage",
    pointer: str = "current",
) -> dict[str, Any]:
    try:
        dataset_name = _safe_component(name, field="dataset_name")
        pointer_name = _safe_component(pointer, field="pointer_name")
    except ValueError as exc:
        return {
            "status": "invalid_pointer_request",
            "error_message_safe": str(exc),
            "external_calls_triggered": False,
        }
    root_path = Path(root)
    pointer_path = root_path / dataset_name / f"{pointer_name}.json"
    if not pointer_path.exists():
        return {
            "status": "missing",
            "dataset": dataset_name,
            "pointer": pointer_name,
            "pointer_path": str(pointer_path),
            "exists": False,
            "external_calls_triggered": False,
        }
    try:
        payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "pointer_read_failed",
            "dataset": dataset_name,
            "pointer": pointer_name,
            "pointer_path": str(pointer_path),
            "exists": True,
            "error_message_safe": type(exc).__name__,
            "external_calls_triggered": False,
        }
    if not isinstance(payload, dict):
        return {
            "status": "pointer_invalid",
            "dataset": dataset_name,
            "pointer": pointer_name,
            "pointer_path": str(pointer_path),
            "exists": True,
            "external_calls_triggered": False,
        }
    artifact_relpath = str(payload.get("artifact_relpath") or "")
    artifact_path = root_path / artifact_relpath if artifact_relpath else Path()
    if artifact_relpath:
        try:
            artifact_path.resolve().relative_to(root_path.resolve())
        except ValueError:
            return {
                "status": "pointer_invalid_artifact_path",
                "dataset": dataset_name,
                "pointer": pointer_name,
                "pointer_path": str(pointer_path),
                "exists": True,
                "external_calls_triggered": False,
            }
    artifact_exists = bool(artifact_relpath and artifact_path.exists() and artifact_path.is_file())
    expected_sha256 = str(payload.get("artifact_sha256") or "")
    actual_sha256 = _sha256_file(artifact_path) if artifact_exists else ""
    artifact_sha256_matches = bool(
        artifact_exists
        and len(expected_sha256) == 64
        and actual_sha256 == expected_sha256
    )
    if not artifact_exists:
        pointer_status = "artifact_missing"
    elif not artifact_sha256_matches:
        pointer_status = "artifact_checksum_mismatch"
    else:
        pointer_status = "ready"
    return {
        **payload,
        "status": pointer_status,
        "dataset": dataset_name,
        "pointer": pointer_name,
        "pointer_path": str(pointer_path),
        "artifact_path": str(artifact_path) if artifact_relpath else "",
        "exists": True,
        "artifact_exists": artifact_exists,
        "artifact_sha256_expected": expected_sha256,
        "artifact_sha256_actual": actual_sha256,
        "artifact_sha256_matches": artifact_sha256_matches,
        "external_calls_triggered": False,
    }


def versioned_dataset_manifest(
    root: str | Path = ".stock_ming_3/parquet",
    name: str = "research_result_lineage",
) -> dict[str, Any]:
    try:
        dataset_name = _safe_component(name, field="dataset_name")
    except ValueError as exc:
        return {
            "status": "invalid_manifest_request",
            "error_message_safe": str(exc),
            "external_calls_triggered": False,
        }
    root_path = Path(root)
    manifest_path = root_path / dataset_name / "manifest.json"
    if not manifest_path.exists():
        return {
            "schema_version": "stock_ming_versioned_parquet_manifest.v1",
            "status": "missing",
            "dataset": dataset_name,
            "manifest_path": str(manifest_path),
            "version_count": 0,
            "valid_version_count": 0,
            "versions": [],
            "external_calls_triggered": False,
        }
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "manifest_read_failed",
            "dataset": dataset_name,
            "manifest_path": str(manifest_path),
            "error_message_safe": type(exc).__name__,
            "external_calls_triggered": False,
        }
    if not isinstance(payload, dict) or payload.get("schema_version") != "stock_ming_versioned_parquet_manifest.v1":
        return {
            "status": "manifest_invalid",
            "dataset": dataset_name,
            "manifest_path": str(manifest_path),
            "external_calls_triggered": False,
        }
    raw_versions = payload.get("versions")
    if not isinstance(raw_versions, list):
        raw_versions = []
    versions: list[dict[str, Any]] = []
    seen_versions: set[str] = set()
    for raw in raw_versions:
        item = dict(raw) if isinstance(raw, dict) else {}
        version_id = str(item.get("version_id") or "")
        artifact_relpath = str(item.get("artifact_relpath") or "")
        artifact_path = root_path / artifact_relpath if artifact_relpath else Path()
        path_safe = False
        if artifact_relpath:
            try:
                artifact_path.resolve().relative_to(root_path.resolve())
                path_safe = True
            except ValueError:
                path_safe = False
        artifact_exists = bool(path_safe and artifact_path.exists() and artifact_path.is_file())
        actual_sha256 = _sha256_file(artifact_path) if artifact_exists else ""
        expected_sha256 = str(item.get("artifact_sha256") or "")
        unique_version = bool(version_id and version_id not in seen_versions)
        if version_id:
            seen_versions.add(version_id)
        valid = bool(
            unique_version
            and path_safe
            and artifact_exists
            and len(expected_sha256) == 64
            and actual_sha256 == expected_sha256
            and int(item.get("row_count") or 0) > 0
            and isinstance(item.get("columns"), list)
        )
        versions.append(
            {
                **item,
                "status": "ready" if valid else "invalid",
                "artifact_path": str(artifact_path) if path_safe else "",
                "artifact_exists": artifact_exists,
                "artifact_path_safe": path_safe,
                "artifact_sha256_actual": actual_sha256,
                "artifact_sha256_matches": bool(actual_sha256 and actual_sha256 == expected_sha256),
                "version_id_unique": unique_version,
                "valid": valid,
            }
        )
    valid_count = sum(1 for item in versions if item.get("valid") is True)
    manifest_ready = bool(versions and valid_count == len(versions))
    return {
        **payload,
        "status": "ready" if manifest_ready else "manifest_validation_failed",
        "dataset": dataset_name,
        "manifest_path": str(manifest_path),
        "version_count": len(versions),
        "valid_version_count": valid_count,
        "versions": versions,
        "external_calls_triggered": False,
    }


def resolve_versioned_dataset_current(
    root: str | Path = ".stock_ming_3/parquet",
    name: str = "research_result_lineage",
) -> dict[str, Any]:
    current = versioned_dataset_pointer(root=root, name=name, pointer="current")
    last_good = versioned_dataset_pointer(root=root, name=name, pointer="last_good")
    manifest = versioned_dataset_manifest(root=root, name=name)
    valid_manifest_versions = {
        str(item.get("version_id") or "")
        for item in list(manifest.get("versions") or [])
        if isinstance(item, dict) and item.get("valid") is True
    }
    current_valid = bool(
        current.get("status") == "ready"
        and str(current.get("version_id") or "") in valid_manifest_versions
    )
    last_good_valid = bool(
        last_good.get("status") == "ready"
        and str(last_good.get("version_id") or "") in valid_manifest_versions
    )
    if current_valid:
        status = "resolved_current"
        selected_pointer_kind = "current"
        selected = current
        degraded = False
    elif last_good_valid:
        status = "resolved_last_good_after_current_failure"
        selected_pointer_kind = "last_good"
        selected = last_good
        degraded = True
    else:
        status = "no_valid_version_available"
        selected_pointer_kind = ""
        selected = {}
        degraded = True
    blockers: list[str] = []
    if not current_valid:
        blockers.append(f"current_{current.get('status') or 'missing'}")
    if not selected:
        blockers.append(f"last_good_{last_good.get('status') or 'missing'}")
    if manifest.get("status") not in {"ready", "manifest_validation_failed"}:
        blockers.append(f"manifest_{manifest.get('status') or 'missing'}")
    return {
        "schema_version": "stock_ming_versioned_parquet_resolution.v1",
        "status": status,
        "dataset": str(current.get("dataset") or last_good.get("dataset") or name),
        "selected_pointer_kind": selected_pointer_kind,
        "selected_pointer": dict(selected),
        "selected_version_id": str(selected.get("version_id") or ""),
        "selected_artifact_path": str(selected.get("artifact_path") or ""),
        "current_valid": current_valid,
        "last_good_valid": last_good_valid,
        "degraded_recovery_active": degraded and bool(selected),
        "no_valid_version_available": not bool(selected),
        "blockers": blockers,
        "current_pointer": current,
        "last_good_pointer": last_good,
        "manifest_status": str(manifest.get("status") or "missing"),
        "valid_manifest_version_count": len(valid_manifest_versions),
        "cache_only": True,
        "writes_files": False,
        "external_calls_triggered": False,
    }


def versioned_dataset_ttl_status(
    pointer: dict[str, Any] | None,
    *,
    ttl_seconds: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calculate freshness for a validated pointer without refreshing it."""

    safe_pointer = dict(pointer or {})
    safe_ttl = max(int(ttl_seconds), 1)
    timestamp = str(safe_pointer.get("promoted_at") or "")
    evaluated_at = now or datetime.now(timezone.utc)
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=timezone.utc)
    evaluated_at = evaluated_at.astimezone(timezone.utc)
    promoted_at: datetime | None = None
    if timestamp:
        try:
            promoted_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if promoted_at.tzinfo is None:
                promoted_at = promoted_at.replace(tzinfo=timezone.utc)
            promoted_at = promoted_at.astimezone(timezone.utc)
        except ValueError:
            promoted_at = None
    age_seconds = max(int((evaluated_at - promoted_at).total_seconds()), 0) if promoted_at else None
    if safe_pointer.get("status") != "ready":
        status = "ttl_source_unavailable"
    elif promoted_at is None:
        status = "ttl_timestamp_invalid"
    elif age_seconds is not None and age_seconds > safe_ttl:
        status = "stale"
    else:
        status = "fresh"
    return {
        "schema_version": "stock_ming_versioned_parquet_ttl_status.v1",
        "status": status,
        "version_id": str(safe_pointer.get("version_id") or ""),
        "promoted_at": timestamp,
        "evaluated_at": evaluated_at.isoformat(),
        "age_seconds": age_seconds,
        "ttl_seconds": safe_ttl,
        "fresh": status == "fresh",
        "stale": status == "stale",
        "refresh_recommended": status == "stale",
        "auto_refresh_on_get": False,
        "writes_files": False,
        "external_calls_triggered": False,
    }


def versioned_dataset_retention_plan(
    *,
    root: str | Path = ".stock_ming_3/parquet",
    name: str = "research_result_lineage",
    max_versions: int = 10,
) -> dict[str, Any]:
    """Plan immutable version cleanup while protecting current and last-good."""

    manifest = versioned_dataset_manifest(root=root, name=name)
    current = versioned_dataset_pointer(root=root, name=name, pointer="current")
    last_good = versioned_dataset_pointer(root=root, name=name, pointer="last_good")
    protected_version_ids = {
        str(pointer.get("version_id") or "")
        for pointer in (current, last_good)
        if pointer.get("version_id")
    }
    requested_max = max(int(max_versions), 1)
    effective_max = max(requested_max, len(protected_version_ids))
    valid_versions = [
        dict(item)
        for item in list(manifest.get("versions") or [])
        if isinstance(item, dict) and item.get("valid") is True
    ]
    valid_versions.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("version_id") or "")))
    cleanup_needed = max(len(valid_versions) - effective_max, 0)
    cleanup_candidates = [
        {
            "version_id": str(item.get("version_id") or ""),
            "created_at": str(item.get("created_at") or ""),
            "artifact_path": str(item.get("artifact_path") or ""),
            "artifact_sha256": str(item.get("artifact_sha256") or ""),
            "protected": False,
        }
        for item in valid_versions
        if str(item.get("version_id") or "") not in protected_version_ids
    ][:cleanup_needed]
    invalid_version_ids = [
        str(item.get("version_id") or "")
        for item in list(manifest.get("versions") or [])
        if isinstance(item, dict) and item.get("valid") is not True
    ]
    manifest_usable = manifest.get("status") in {"ready", "manifest_validation_failed"}
    if not manifest_usable:
        status = "retention_plan_blocked_manifest_unavailable"
        cleanup_candidates = []
    elif cleanup_candidates:
        status = "retention_cleanup_candidates_ready"
    else:
        status = "retention_within_limit"
    plan_binding = {
        "schema_version": "stock_ming_versioned_parquet_retention_plan_binding.v1",
        "dataset": str(manifest.get("dataset") or name),
        "requested_max_versions": requested_max,
        "effective_max_versions": effective_max,
        "protected_version_ids": sorted(protected_version_ids),
        "version_inventory": [
            {
                "version_id": str(item.get("version_id") or ""),
                "artifact_sha256": str(item.get("artifact_sha256") or ""),
                "created_at": str(item.get("created_at") or ""),
                "valid": item.get("valid") is True,
            }
            for item in list(manifest.get("versions") or [])
            if isinstance(item, dict)
        ],
        "cleanup_candidate_version_ids": [item["version_id"] for item in cleanup_candidates],
    }
    return {
        "schema_version": "stock_ming_versioned_parquet_retention_plan.v1",
        "status": status,
        "dataset": str(manifest.get("dataset") or name),
        "requested_max_versions": requested_max,
        "effective_max_versions": effective_max,
        "version_count": len(valid_versions),
        "protected_version_ids": sorted(protected_version_ids),
        "protected_version_count": len(protected_version_ids),
        "cleanup_candidate_count": len(cleanup_candidates),
        "cleanup_candidates": cleanup_candidates,
        "cleanup_candidate_version_ids": [item["version_id"] for item in cleanup_candidates],
        "invalid_version_ids_manual_review": invalid_version_ids,
        "plan_hash_algorithm": "sha256",
        "plan_hash": _stable_json_sha256(plan_binding),
        "delete_executed": False,
        "auto_cleanup": False,
        "writes_files": False,
        "cache_only": True,
        "external_calls_triggered": False,
    }


def versioned_dataset_retention_cleanup_journal(
    *,
    root: str | Path = ".stock_ming_3/parquet",
    name: str = "research_result_lineage",
) -> dict[str, Any]:
    """Read interrupted retention cleanup state without mutating storage."""

    try:
        dataset_name = _safe_component(name, field="dataset_name")
    except ValueError as exc:
        return {
            "status": "invalid_cleanup_journal_request",
            "error_message_safe": str(exc),
            "recovery_ready": False,
            "writes_files": False,
            "external_calls_triggered": False,
        }
    root_path = Path(root)
    dataset_root = root_path / dataset_name
    versions_root = dataset_root / "versions"
    journal_path = dataset_root / "retention_cleanup_journal.json"
    if not journal_path.exists():
        return {
            "schema_version": "stock_ming_versioned_parquet_retention_cleanup_journal.v1",
            "status": "missing",
            "dataset": dataset_name,
            "journal_path": str(journal_path),
            "candidate_version_ids": [],
            "pending_artifact_count": 0,
            "recovery_ready": False,
            "cleanup_completed": False,
            "writes_files": False,
            "external_calls_triggered": False,
        }
    try:
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "schema_version": "stock_ming_versioned_parquet_retention_cleanup_journal.v1",
            "status": "journal_read_failed",
            "dataset": dataset_name,
            "journal_path": str(journal_path),
            "error_message_safe": type(exc).__name__,
            "recovery_ready": False,
            "writes_files": False,
            "external_calls_triggered": False,
        }
    if not isinstance(payload, dict) or payload.get("schema_version") != "stock_ming_versioned_parquet_retention_cleanup_journal.v1":
        return {
            "schema_version": "stock_ming_versioned_parquet_retention_cleanup_journal.v1",
            "status": "journal_invalid",
            "dataset": dataset_name,
            "journal_path": str(journal_path),
            "recovery_ready": False,
            "writes_files": False,
            "external_calls_triggered": False,
        }
    candidates: list[dict[str, Any]] = []
    paths_safe = True
    for raw in list(payload.get("candidate_artifacts") or []):
        item = dict(raw) if isinstance(raw, dict) else {}
        artifact_relpath = str(item.get("artifact_relpath") or "")
        artifact_path = root_path / artifact_relpath if artifact_relpath else Path()
        path_safe = False
        if artifact_relpath:
            try:
                artifact_path.resolve().relative_to(versions_root.resolve())
                path_safe = True
            except ValueError:
                path_safe = False
        paths_safe = paths_safe and path_safe
        candidates.append(
            {
                "version_id": str(item.get("version_id") or ""),
                "artifact_relpath": artifact_relpath,
                "artifact_path": str(artifact_path) if path_safe else "",
                "artifact_sha256": str(item.get("artifact_sha256") or ""),
                "artifact_path_safe": path_safe,
                "artifact_exists": bool(path_safe and artifact_path.exists() and artifact_path.is_file()),
            }
        )
    candidate_version_ids = [item["version_id"] for item in candidates if item["version_id"]]
    current = versioned_dataset_pointer(root=root_path, name=dataset_name, pointer="current")
    last_good = versioned_dataset_pointer(root=root_path, name=dataset_name, pointer="last_good")
    protected_version_ids = {
        str(pointer.get("version_id") or "")
        for pointer in (current, last_good)
        if pointer.get("version_id")
    }
    manifest = versioned_dataset_manifest(root=root_path, name=dataset_name)
    manifest_version_ids = {
        str(item.get("version_id") or "")
        for item in list(manifest.get("versions") or [])
        if isinstance(item, dict)
    }
    candidates_removed_from_manifest = bool(
        candidate_version_ids
        and not set(candidate_version_ids).intersection(manifest_version_ids)
    )
    protected_conflict = bool(set(candidate_version_ids).intersection(protected_version_ids))
    pending_artifact_count = sum(1 for item in candidates if item.get("artifact_exists") is True)
    journal_status = str(payload.get("status") or "journal_invalid")
    recoverable_status = journal_status in {"prepared", "manifest_updated", "partial"}
    recovery_ready = bool(
        recoverable_status
        and paths_safe
        and candidates_removed_from_manifest
        and not protected_conflict
    )
    cleanup_completed = bool(
        journal_status == "completed"
        and candidates_removed_from_manifest
        and pending_artifact_count == 0
        and not protected_conflict
    )
    return {
        **payload,
        "status": journal_status,
        "dataset": dataset_name,
        "journal_path": str(journal_path),
        "candidate_artifacts": candidates,
        "candidate_version_ids": candidate_version_ids,
        "protected_version_ids_current": sorted(protected_version_ids),
        "protected_version_conflict": protected_conflict,
        "manifest_status": str(manifest.get("status") or "missing"),
        "candidates_removed_from_manifest": candidates_removed_from_manifest,
        "pending_artifact_count": pending_artifact_count,
        "recovery_ready": recovery_ready,
        "cleanup_completed": cleanup_completed,
        "writes_files": False,
        "external_calls_triggered": False,
    }


def _delete_version_artifact(path: Path) -> None:
    path.unlink(missing_ok=False)


def _resume_versioned_dataset_retention_cleanup(
    *,
    root_path: Path,
    dataset_name: str,
    expected_plan_hash: str,
    expected_candidate_version_ids: list[str],
    approved_by_user: bool,
) -> dict[str, Any] | None:
    journal = versioned_dataset_retention_cleanup_journal(root=root_path, name=dataset_name)
    if not (
        approved_by_user
        and journal.get("recovery_ready") is True
        and str(journal.get("plan_hash") or "") == expected_plan_hash
        and list(journal.get("candidate_version_ids") or []) == expected_candidate_version_ids
    ):
        return None
    recovered_version_ids: list[str] = []
    delete_failed_version_ids: list[str] = []
    for item in list(journal.get("candidate_artifacts") or []):
        if not isinstance(item, dict) or item.get("artifact_path_safe") is not True:
            delete_failed_version_ids.append(str(item.get("version_id") or ""))
            continue
        version_id = str(item.get("version_id") or "")
        artifact_path = Path(str(item.get("artifact_path") or ""))
        if not artifact_path.exists():
            recovered_version_ids.append(version_id)
            continue
        try:
            _delete_version_artifact(artifact_path)
            recovered_version_ids.append(version_id)
        except OSError:
            delete_failed_version_ids.append(version_id)
    current_after = versioned_dataset_pointer(root=root_path, name=dataset_name, pointer="current")
    last_good_after = versioned_dataset_pointer(root=root_path, name=dataset_name, pointer="last_good")
    manifest_after = versioned_dataset_manifest(root=root_path, name=dataset_name)
    completed = bool(
        not delete_failed_version_ids
        and len(recovered_version_ids) == len(expected_candidate_version_ids)
        and manifest_after.get("status") == "ready"
        and current_after.get("status") == "ready"
        and last_good_after.get("status") in {"ready", "missing"}
    )
    journal_path = root_path / dataset_name / "retention_cleanup_journal.json"
    raw_journal = json.loads(journal_path.read_text(encoding="utf-8"))
    raw_journal.update(
        {
            "status": "completed" if completed else "partial",
            "recovery_attempted_at": datetime.now(timezone.utc).isoformat(),
            "recovered_version_ids": recovered_version_ids,
            "delete_failed_version_ids": delete_failed_version_ids,
            "contains_secret": False,
        }
    )
    if completed:
        raw_journal["completed_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(journal_path, raw_journal)
    return {
        "schema_version": "stock_ming_versioned_parquet_retention_cleanup.v1",
        "status": "retention_cleanup_recovered" if completed else "retention_cleanup_recovery_still_partial",
        "dataset": dataset_name,
        "plan_hash": expected_plan_hash,
        "candidate_version_ids": expected_candidate_version_ids,
        "protected_version_ids": list(journal.get("protected_version_ids") or []),
        "deleted_version_ids": recovered_version_ids,
        "delete_failed_version_ids": delete_failed_version_ids,
        "deleted_version_count": len(recovered_version_ids),
        "delete_executed": completed,
        "recovery_execution": True,
        "writes_manifest": False,
        "manifest_status": str(manifest_after.get("status") or "missing"),
        "remaining_version_count": int(manifest_after.get("version_count") or 0),
        "current_pointer_status": str(current_after.get("status") or "missing"),
        "current_version_id": str(current_after.get("version_id") or ""),
        "last_good_pointer_status": str(last_good_after.get("status") or "missing"),
        "last_good_version_id": str(last_good_after.get("version_id") or ""),
        "cleanup_journal_status": "completed" if completed else "partial",
        "external_calls_triggered": False,
    }


def execute_versioned_dataset_retention_cleanup(
    *,
    root: str | Path = ".stock_ming_3/parquet",
    name: str = "research_result_lineage",
    max_versions: int = 10,
    expected_plan_hash: str,
    expected_candidate_version_ids: list[str] | tuple[str, ...],
    approved_by_user: bool,
) -> dict[str, Any]:
    """Delete only versions bound to the current retention plan."""

    try:
        dataset_name = _safe_component(name, field="dataset_name")
    except ValueError as exc:
        return {
            "status": "invalid_retention_cleanup_request",
            "delete_executed": False,
            "error_message_safe": str(exc),
            "external_calls_triggered": False,
        }
    root_path = Path(root)
    expected_candidates = [str(value) for value in expected_candidate_version_ids if str(value)]
    recovery = _resume_versioned_dataset_retention_cleanup(
        root_path=root_path,
        dataset_name=dataset_name,
        expected_plan_hash=str(expected_plan_hash or ""),
        expected_candidate_version_ids=expected_candidates,
        approved_by_user=approved_by_user,
    )
    if recovery is not None:
        return recovery
    plan = versioned_dataset_retention_plan(
        root=root,
        name=dataset_name,
        max_versions=max_versions,
    )
    plan_candidates = [str(value) for value in list(plan.get("cleanup_candidate_version_ids") or [])]
    protected = set(str(value) for value in list(plan.get("protected_version_ids") or []))
    if not approved_by_user:
        status = "retention_cleanup_blocked_user_approval_required"
    elif plan.get("status") != "retention_cleanup_candidates_ready":
        status = "retention_cleanup_not_ready"
    elif len(str(expected_plan_hash or "")) != 64 or expected_plan_hash != plan.get("plan_hash"):
        status = "retention_cleanup_blocked_plan_hash_mismatch"
    elif expected_candidates != plan_candidates:
        status = "retention_cleanup_blocked_candidate_scope_mismatch"
    elif any(version_id in protected for version_id in expected_candidates):
        status = "retention_cleanup_blocked_protected_version"
    else:
        status = "retention_cleanup_scope_validated"
    if status != "retention_cleanup_scope_validated":
        return {
            "schema_version": "stock_ming_versioned_parquet_retention_cleanup.v1",
            "status": status,
            "dataset": dataset_name,
            "plan_hash": str(plan.get("plan_hash") or ""),
            "expected_plan_hash": str(expected_plan_hash or ""),
            "candidate_version_ids": plan_candidates,
            "expected_candidate_version_ids": expected_candidates,
            "protected_version_ids": sorted(protected),
            "delete_executed": False,
            "deleted_version_count": 0,
            "writes_manifest": False,
            "external_calls_triggered": False,
        }

    dataset_root = root_path / dataset_name
    versions_root = dataset_root / "versions"
    manifest_before = versioned_dataset_manifest(root=root_path, name=dataset_name)
    if manifest_before.get("status") != "ready":
        return {
            "schema_version": "stock_ming_versioned_parquet_retention_cleanup.v1",
            "status": "retention_cleanup_blocked_manifest_not_ready",
            "dataset": dataset_name,
            "plan_hash": str(plan.get("plan_hash") or ""),
            "candidate_version_ids": plan_candidates,
            "protected_version_ids": sorted(protected),
            "delete_executed": False,
            "deleted_version_count": 0,
            "writes_manifest": False,
            "external_calls_triggered": False,
        }
    candidate_items = {
        str(item.get("version_id") or ""): dict(item)
        for item in list(manifest_before.get("versions") or [])
        if isinstance(item, dict) and str(item.get("version_id") or "") in expected_candidates
    }
    if set(candidate_items) != set(expected_candidates):
        return {
            "schema_version": "stock_ming_versioned_parquet_retention_cleanup.v1",
            "status": "retention_cleanup_blocked_candidate_manifest_mismatch",
            "dataset": dataset_name,
            "plan_hash": str(plan.get("plan_hash") or ""),
            "candidate_version_ids": plan_candidates,
            "protected_version_ids": sorted(protected),
            "delete_executed": False,
            "deleted_version_count": 0,
            "writes_manifest": False,
            "external_calls_triggered": False,
        }
    artifact_paths: list[Path] = []
    for version_id in expected_candidates:
        artifact_path = Path(str(candidate_items[version_id].get("artifact_path") or ""))
        try:
            artifact_path.resolve().relative_to(versions_root.resolve())
        except ValueError:
            return {
                "schema_version": "stock_ming_versioned_parquet_retention_cleanup.v1",
                "status": "retention_cleanup_blocked_unsafe_artifact_path",
                "dataset": dataset_name,
                "plan_hash": str(plan.get("plan_hash") or ""),
                "candidate_version_ids": plan_candidates,
                "protected_version_ids": sorted(protected),
                "delete_executed": False,
                "deleted_version_count": 0,
                "writes_manifest": False,
                "external_calls_triggered": False,
            }
        artifact_paths.append(artifact_path)

    retained_versions = [
        _version_manifest_record(dict(item))
        for item in list(manifest_before.get("versions") or [])
        if isinstance(item, dict) and str(item.get("version_id") or "") not in expected_candidates
    ]
    now = datetime.now(timezone.utc).isoformat()
    original_manifest = {
        "schema_version": "stock_ming_versioned_parquet_manifest.v1",
        "dataset": dataset_name,
        "versions": [
            _version_manifest_record(dict(item))
            for item in list(manifest_before.get("versions") or [])
            if isinstance(item, dict)
        ],
        "updated_at": str(manifest_before.get("updated_at") or now),
        "contains_secret": False,
    }
    journal_path = dataset_root / "retention_cleanup_journal.json"
    journal_payload = {
        "schema_version": "stock_ming_versioned_parquet_retention_cleanup_journal.v1",
        "status": "prepared",
        "dataset": dataset_name,
        "plan_hash": str(plan.get("plan_hash") or ""),
        "max_versions": max(int(max_versions), 1),
        "candidate_artifacts": [
            {
                "version_id": version_id,
                "artifact_relpath": str(candidate_items[version_id].get("artifact_relpath") or ""),
                "artifact_sha256": str(candidate_items[version_id].get("artifact_sha256") or ""),
            }
            for version_id in expected_candidates
        ],
        "candidate_version_ids": expected_candidates,
        "protected_version_ids": sorted(protected),
        "prepared_at": now,
        "contains_secret": False,
    }
    try:
        _atomic_write_json(journal_path, journal_payload)
    except OSError:
        return {
            "schema_version": "stock_ming_versioned_parquet_retention_cleanup.v1",
            "status": "retention_cleanup_journal_write_failed",
            "dataset": dataset_name,
            "plan_hash": str(plan.get("plan_hash") or ""),
            "candidate_version_ids": plan_candidates,
            "protected_version_ids": sorted(protected),
            "delete_executed": False,
            "deleted_version_count": 0,
            "writes_manifest": False,
            "external_calls_triggered": False,
        }
    _atomic_write_json(
        dataset_root / "manifest.json",
        {
            "schema_version": "stock_ming_versioned_parquet_manifest.v1",
            "dataset": dataset_name,
            "versions": retained_versions,
            "updated_at": now,
            "contains_secret": False,
        },
    )
    manifest_after_write = versioned_dataset_manifest(root=root_path, name=dataset_name)
    if manifest_after_write.get("status") != "ready":
        _atomic_write_json(dataset_root / "manifest.json", original_manifest)
        journal_payload.update(
            {
                "status": "manifest_update_rolled_back",
                "rolled_back_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        _atomic_write_json(journal_path, journal_payload)
        return {
            "schema_version": "stock_ming_versioned_parquet_retention_cleanup.v1",
            "status": "retention_cleanup_manifest_update_failed_rolled_back",
            "dataset": dataset_name,
            "plan_hash": str(plan.get("plan_hash") or ""),
            "candidate_version_ids": plan_candidates,
            "protected_version_ids": sorted(protected),
            "delete_executed": False,
            "deleted_version_count": 0,
            "writes_manifest": False,
            "external_calls_triggered": False,
        }
    journal_payload.update(
        {
            "status": "manifest_updated",
            "manifest_updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _atomic_write_json(journal_path, journal_payload)

    deleted_version_ids: list[str] = []
    delete_failed_version_ids: list[str] = []
    for version_id, artifact_path in zip(expected_candidates, artifact_paths):
        try:
            _delete_version_artifact(artifact_path)
            deleted_version_ids.append(version_id)
        except OSError:
            delete_failed_version_ids.append(version_id)
    current_after = versioned_dataset_pointer(root=root_path, name=dataset_name, pointer="current")
    last_good_after = versioned_dataset_pointer(root=root_path, name=dataset_name, pointer="last_good")
    manifest_after = versioned_dataset_manifest(root=root_path, name=dataset_name)
    completed = bool(
        not delete_failed_version_ids
        and len(deleted_version_ids) == len(expected_candidates)
        and manifest_after.get("status") == "ready"
        and current_after.get("status") == "ready"
        and (last_good_after.get("status") in {"ready", "missing"})
    )
    journal_payload.update(
        {
            "status": "completed" if completed else "partial",
            "deleted_version_ids": deleted_version_ids,
            "delete_failed_version_ids": delete_failed_version_ids,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if completed:
        journal_payload["completed_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(journal_path, journal_payload)
    return {
        "schema_version": "stock_ming_versioned_parquet_retention_cleanup.v1",
        "status": "retention_cleanup_completed" if completed else "retention_cleanup_partial_orphaned_artifacts",
        "dataset": dataset_name,
        "plan_hash": str(plan.get("plan_hash") or ""),
        "candidate_version_ids": plan_candidates,
        "protected_version_ids": sorted(protected),
        "deleted_version_ids": deleted_version_ids,
        "delete_failed_version_ids": delete_failed_version_ids,
        "deleted_version_count": len(deleted_version_ids),
        "delete_executed": completed,
        "writes_manifest": True,
        "manifest_status": str(manifest_after.get("status") or "missing"),
        "remaining_version_count": int(manifest_after.get("version_count") or 0),
        "current_pointer_status": str(current_after.get("status") or "missing"),
        "current_version_id": str(current_after.get("version_id") or ""),
        "last_good_pointer_status": str(last_good_after.get("status") or "missing"),
        "last_good_version_id": str(last_good_after.get("version_id") or ""),
        "cleanup_journal_status": "completed" if completed else "partial",
        "external_calls_triggered": False,
    }


def ensure_versioned_dataset_manifest_entry(
    *,
    root: str | Path = ".stock_ming_3/parquet",
    name: str = "research_result_lineage",
    pointer: str = "current",
) -> dict[str, Any]:
    current = versioned_dataset_pointer(root=root, name=name, pointer=pointer)
    if current.get("status") != "ready":
        return {
            "status": "pointer_not_ready",
            "manifest_entry_ready": False,
            "writes_manifest": False,
            "external_calls_triggered": False,
        }
    artifact_path = Path(str(current.get("artifact_path") or ""))
    artifact_sha256 = _sha256_file(artifact_path) if artifact_path.exists() else ""
    if not artifact_sha256 or artifact_sha256 != str(current.get("artifact_sha256") or ""):
        return {
            "status": "pointer_artifact_checksum_mismatch",
            "manifest_entry_ready": False,
            "writes_manifest": False,
            "external_calls_triggered": False,
        }
    root_path = Path(root)
    dataset_name = _safe_component(name, field="dataset_name")
    manifest_before = versioned_dataset_manifest(root=root_path, name=dataset_name)
    if manifest_before.get("status") not in {"missing", "ready"}:
        return {
            "status": "manifest_validation_failed",
            "manifest_entry_ready": False,
            "writes_manifest": False,
            "external_calls_triggered": False,
        }
    versions = [
        {
            key: item.get(key)
            for key in (
                "version_id",
                "artifact_relpath",
                "artifact_sha256",
                "row_count",
                "columns",
                "required_columns",
                "created_at",
                "lineage",
                "contains_secret",
            )
        }
        for item in list(manifest_before.get("versions") or [])
        if isinstance(item, dict)
    ]
    entry = {
        "version_id": str(current.get("version_id") or ""),
        "artifact_relpath": str(current.get("artifact_relpath") or ""),
        "artifact_sha256": artifact_sha256,
        "row_count": int(current.get("row_count") or 0),
        "columns": list(current.get("columns") or []),
        "required_columns": list(current.get("required_columns") or []),
        "created_at": str(current.get("promoted_at") or datetime.now(timezone.utc).isoformat()),
        "lineage": dict(current.get("lineage") or {}),
        "contains_secret": False,
    }
    existing = next((item for item in versions if item.get("version_id") == entry["version_id"]), None)
    if existing and any(
        existing.get(key) != entry.get(key)
        for key in ("artifact_relpath", "artifact_sha256", "row_count", "columns", "required_columns")
    ):
        return {
            "status": "manifest_version_conflict",
            "manifest_entry_ready": False,
            "writes_manifest": False,
            "external_calls_triggered": False,
        }
    writes_manifest = existing is None
    if writes_manifest:
        versions.append(entry)
        versions.sort(key=lambda item: str(item.get("version_id") or ""))
        _atomic_write_json(
            root_path / dataset_name / "manifest.json",
            {
                "schema_version": "stock_ming_versioned_parquet_manifest.v1",
                "dataset": dataset_name,
                "versions": versions,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "contains_secret": False,
            },
        )
    manifest_after = versioned_dataset_manifest(root=root_path, name=dataset_name)
    entry_ready = any(
        item.get("version_id") == entry["version_id"] and item.get("valid") is True
        for item in list(manifest_after.get("versions") or [])
        if isinstance(item, dict)
    )
    return {
        "status": "manifest_entry_ready" if entry_ready else "manifest_entry_validation_failed",
        "manifest_entry_ready": entry_ready,
        "writes_manifest": writes_manifest,
        "version_id": entry["version_id"],
        "version_manifest": manifest_after,
        "external_calls_triggered": False,
    }


def atomic_promote_versioned_dataset(
    df: Any,
    *,
    root: str | Path = ".stock_ming_3/parquet",
    name: str = "research_result_lineage",
    version_id: str,
    required_columns: list[str] | tuple[str, ...] | None = None,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write an immutable Parquet version and atomically switch its pointer."""

    status = dependency_status()
    if not status["available"]:
        return {
            "status": "dependency_missing",
            "atomic_promoted": False,
            "external_calls_triggered": False,
            **status,
        }
    try:
        dataset_name = _safe_component(name, field="dataset_name")
        safe_version = _safe_component(version_id, field="version_id")
    except ValueError as exc:
        return {
            "status": "invalid_version_request",
            "atomic_promoted": False,
            "error_message_safe": str(exc),
            "external_calls_triggered": False,
        }
    columns = [str(column) for column in list(getattr(df, "columns", []))]
    required = [str(column) for column in (required_columns or []) if str(column)]
    missing_columns = [column for column in required if column not in columns]
    row_count = int(len(df))
    if row_count <= 0 or missing_columns:
        return {
            "status": "validation_failed",
            "dataset": dataset_name,
            "version_id": safe_version,
            "row_count": row_count,
            "columns": columns,
            "missing_required_columns": missing_columns,
            "atomic_promoted": False,
            "current_pointer_unchanged": True,
            "external_calls_triggered": False,
        }

    root_path = Path(root)
    dataset_root = root_path / dataset_name
    versions_root = dataset_root / "versions"
    versions_root.mkdir(parents=True, exist_ok=True)
    artifact_path = versions_root / f"{safe_version}.parquet"
    temp_path = versions_root / f".{safe_version}.{uuid.uuid4().hex}.tmp.parquet"
    current_before = versioned_dataset_pointer(root=root_path, name=dataset_name, pointer="current")
    artifact_reused = False
    try:
        df.to_parquet(temp_path, index=False)
        import pyarrow.parquet as pq

        staged = pq.ParquetFile(temp_path)
        staged_columns = [str(column) for column in staged.schema_arrow.names]
        staged_rows = int(staged.metadata.num_rows) if staged.metadata is not None else 0
        if staged_rows != row_count or staged_columns != columns:
            return {
                "status": "staged_validation_failed",
                "dataset": dataset_name,
                "version_id": safe_version,
                "row_count": staged_rows,
                "columns": staged_columns,
                "atomic_promoted": False,
                "current_pointer_unchanged": True,
                "external_calls_triggered": False,
            }
        staged_sha256 = _sha256_file(temp_path)
        if artifact_path.exists():
            if _sha256_file(artifact_path) != staged_sha256:
                return {
                    "status": "version_conflict",
                    "dataset": dataset_name,
                    "version_id": safe_version,
                    "row_count": row_count,
                    "columns": columns,
                    "atomic_promoted": False,
                    "current_pointer_unchanged": True,
                    "external_calls_triggered": False,
                }
            artifact_reused = True
        else:
            os.replace(temp_path, artifact_path)

        artifact_sha256 = _sha256_file(artifact_path)
        now = datetime.now(timezone.utc).isoformat()
        manifest_before = versioned_dataset_manifest(root=root_path, name=dataset_name)
        if manifest_before.get("status") not in {"missing", "ready"}:
            return {
                "status": "manifest_validation_failed",
                "dataset": dataset_name,
                "version_id": safe_version,
                "atomic_promoted": False,
                "current_pointer_unchanged": True,
                "manifest_status": manifest_before.get("status"),
                "external_calls_triggered": False,
            }
        manifest_versions = [
            {
                key: item.get(key)
                for key in (
                    "version_id",
                    "artifact_relpath",
                    "artifact_sha256",
                    "row_count",
                    "columns",
                    "required_columns",
                    "created_at",
                    "lineage",
                    "contains_secret",
                )
            }
            for item in list(manifest_before.get("versions") or [])
            if isinstance(item, dict)
        ]
        manifest_entry = {
            "version_id": safe_version,
            "artifact_relpath": str(artifact_path.relative_to(root_path)),
            "artifact_sha256": artifact_sha256,
            "row_count": row_count,
            "columns": columns,
            "required_columns": required,
            "created_at": now,
            "lineage": dict(lineage or {}),
            "contains_secret": False,
        }
        existing_manifest_entry = next(
            (item for item in manifest_versions if item.get("version_id") == safe_version),
            None,
        )
        if existing_manifest_entry and any(
            existing_manifest_entry.get(key) != manifest_entry.get(key)
            for key in ("artifact_relpath", "artifact_sha256", "row_count", "columns", "required_columns")
        ):
            return {
                "status": "manifest_version_conflict",
                "dataset": dataset_name,
                "version_id": safe_version,
                "atomic_promoted": False,
                "current_pointer_unchanged": True,
                "external_calls_triggered": False,
            }
        manifest_written = existing_manifest_entry is None
        if manifest_written:
            manifest_versions.append(manifest_entry)
            manifest_versions.sort(key=lambda item: str(item.get("version_id") or ""))
            _atomic_write_json(
                dataset_root / "manifest.json",
                {
                    "schema_version": "stock_ming_versioned_parquet_manifest.v1",
                    "dataset": dataset_name,
                    "versions": manifest_versions,
                    "updated_at": now,
                    "contains_secret": False,
                },
            )
        manifest_after = versioned_dataset_manifest(root=root_path, name=dataset_name)
        manifest_version_ready = any(
            item.get("version_id") == safe_version and item.get("valid") is True
            for item in list(manifest_after.get("versions") or [])
            if isinstance(item, dict)
        )
        if manifest_after.get("status") != "ready" or not manifest_version_ready:
            return {
                "status": "manifest_post_write_validation_failed",
                "dataset": dataset_name,
                "version_id": safe_version,
                "atomic_promoted": False,
                "current_pointer_unchanged": True,
                "manifest_status": manifest_after.get("status"),
                "external_calls_triggered": False,
            }
        pointer_payload = {
            "schema_version": "stock_ming_versioned_parquet_pointer.v1",
            "pointer_kind": "current",
            "dataset": dataset_name,
            "version_id": safe_version,
            "artifact_relpath": str(artifact_path.relative_to(root_path)),
            "artifact_sha256": artifact_sha256,
            "row_count": row_count,
            "columns": columns,
            "required_columns": required,
            "promoted_at": now,
            "lineage": dict(lineage or {}),
            "contains_secret": False,
        }
        last_good_preserved = current_before.get("status") == "ready"
        if last_good_preserved:
            last_good_payload = {
                key: value
                for key, value in current_before.items()
                if key
                not in {
                    "status",
                    "pointer",
                    "pointer_path",
                    "artifact_path",
                    "exists",
                    "artifact_exists",
                    "external_calls_triggered",
                }
            }
            last_good_payload["pointer_kind"] = "last_good"
            last_good_payload["preserved_at"] = now
            _atomic_write_json(dataset_root / "last_good.json", last_good_payload)
        _atomic_write_json(dataset_root / "current.json", pointer_payload)
    except Exception as exc:
        return {
            "status": "atomic_promotion_failed",
            "dataset": dataset_name,
            "version_id": safe_version,
            "row_count": row_count,
            "columns": columns,
            "atomic_promoted": False,
            "current_pointer_unchanged": True,
            "error_message_safe": type(exc).__name__,
            "external_calls_triggered": False,
        }
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "status": "atomic_promoted",
        "dataset": dataset_name,
        "version_id": safe_version,
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_sha256,
        "row_count": row_count,
        "columns": columns,
        "required_columns": required,
        "missing_required_columns": [],
        "atomic_promoted": True,
        "artifact_reused": artifact_reused,
        "last_good_preserved": last_good_preserved,
        "current_pointer_unchanged": False,
        "current_pointer": versioned_dataset_pointer(root=root_path, name=dataset_name, pointer="current"),
        "last_good_pointer": versioned_dataset_pointer(root=root_path, name=dataset_name, pointer="last_good"),
        "version_manifest": versioned_dataset_manifest(root=root_path, name=dataset_name),
        "manifest_version_recorded": True,
        "writes_parquet": not artifact_reused,
        "writes_manifest": manifest_written,
        "writes_pointer": True,
        "external_calls_triggered": False,
    }


def read_factor_values(path: str | Path) -> Any:
    status = dependency_status()
    if not status["available"]:
        return {"status": "dependency_missing", **status}
    import pandas as pd

    return pd.read_parquet(path)
