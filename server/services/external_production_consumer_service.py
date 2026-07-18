from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from storage import parquet_store
from storage.sqlite_meta import SQLiteMetaStore

from . import external_production_attestation_service as external_trust
from .sqlite_evidence_reader import immutable_evidence_connection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / ".stock_ming_3"
SQLITE_META_PATH = EVIDENCE_ROOT / "meta.sqlite"
PARQUET_ROOT = EVIDENCE_ROOT / "parquet"
CONSUMER_SCHEMA_VERSION = "command_center_3_external_production_consumer.v1"
POINTER_SCHEMA_VERSION = "command_center_3_external_production_consumer_pointer.v1"

_CONFIG = {
    "worker": {
        "kind": "worker_runtime_lineage",
        "current_key": "command_center_3_full_market_worker_production_acceptance",
        "source_last_good_key": "command_center_3_full_market_worker_production_acceptance_last_good",
        "dataset": "full_market_candidate_radar_results",
    },
    "factor": {
        "kind": "factor_full_market_lineage",
        "current_key": "command_center_3_factor_full_market_worker_production_acceptance",
        "source_last_good_key": "command_center_3_factor_full_market_worker_production_acceptance_last_good",
        "dataset": "full_market_factor_research_results",
    },
    "radar": {
        "kind": "candidate_radar_lineage",
        "current_key": "command_center_3_candidate_radar_cache",
        "source_last_good_key": "command_center_3_candidate_radar_v05_last_good_packet",
        "dataset": "full_market_candidate_radar_results",
    },
}


def _digest(value: Mapping[str, Any] | list[Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def _safe_int(value: Any) -> int:
    return value if type(value) is int and 0 <= value <= (2**63 - 1) else 0


def _strict_positive_int(value: Any) -> bool:
    return type(value) is int and 1 <= value <= (2**63 - 1)


def _read_packet(path: Path, key: str) -> dict[str, Any]:
    connection = immutable_evidence_connection(path)
    if connection is None:
        return {}
    try:
        row = connection.execute(
            "SELECT payload_json FROM packets WHERE packet_key = ?",
            (key,),
        ).fetchone()
        packet = json.loads(str(row[0])) if row else {}
    except Exception:
        return {}
    finally:
        connection.close()
    return dict(packet) if isinstance(packet, Mapping) else {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _consumer_keys(consumer: str) -> tuple[str, str, str]:
    prefix = f"command_center_3_external_{consumer}_production_consumer"
    return prefix, f"{prefix}_current", f"{prefix}_last_good"


def _source_identity(consumer: str, packet: Mapping[str, Any]) -> dict[str, Any]:
    if consumer == "worker":
        run_id = str(packet.get("acceptance_run_id") or "")
        celery_ids = [str(value) for value in packet.get("celery_task_ids") or [] if str(value)]
        claims = {
            "worker_run_id": run_id,
            "redis_transport_digest": str(packet.get("transport_attestation_digest") or ""),
            "celery_task_ids_digest": _digest(celery_ids),
            "eligible_worker_count": len(
                {str(value) for value in packet.get("worker_task_ids") or [] if str(value)}
            ),
            "batch_count": _safe_int(packet.get("batch_count")),
            "row_count": _safe_int(packet.get("result_row_count")),
            "does_not_execute_trades": True,
        }
        return {
            "subject": run_id,
            "task_id": f"full-market-coordinator-{run_id}",
            "scope_hash": str(packet.get("provider_scope_hash") or "").lower(),
            "generation": str(packet.get("result_version_id") or ""),
            "claims": claims,
        }
    if consumer == "factor":
        run_id = str(packet.get("acceptance_run_id") or "")
        version_id = str(packet.get("result_version_id") or "")
        claims = {
            "result_dataset": "full_market_factor_research_results",
            "result_version_id": version_id,
            "universe_digest": str(packet.get("universe_digest") or ""),
            "universe_count": _safe_int(packet.get("universe_count")),
            "metric_validation_digest": str(packet.get("neutralization_audit_digest") or ""),
            "full_market_factor_research": True,
            "does_not_execute_trades": True,
        }
        return {
            "subject": version_id,
            "task_id": f"factor-full-market-{run_id}",
            "scope_hash": str(packet.get("provider_scope_hash") or "").lower(),
            "generation": version_id,
            "claims": claims,
        }
    binding = packet.get("full_market_worker_replacement")
    binding = dict(binding) if isinstance(binding, Mapping) else {}
    claims = {
        "candidate_cache_packet_key": "command_center_3_candidate_radar_cache",
        "cache_write_task_id": str(binding.get("cache_write_task_id") or ""),
        "universe_digest": str(binding.get("universe_digest") or ""),
        "candidate_row_count": _safe_int(binding.get("candidate_row_count")),
        "browser_evidence_digest": str(binding.get("browser_visual_evidence_digest") or ""),
        "performance_evidence_digest": str(binding.get("browser_performance_evidence_digest") or ""),
        "legacy_retirement_evidence_digest": str(
            binding.get("legacy_retirement_evidence_digest") or ""
        ),
        "candidate_radar_production_replacement": True,
        "candidate_is_not_buy_instruction": True,
        "does_not_execute_trades": True,
    }
    return {
        "subject": "command_center_3_candidate_radar_cache",
        "task_id": claims["cache_write_task_id"],
        "scope_hash": str(binding.get("binding_digest") or "").lower(),
        "generation": str(binding.get("source_result_version_id") or ""),
        "claims": claims,
    }


def _source_binding(consumer: str, *, evidence_root: Path | None = None) -> dict[str, Any]:
    config = _CONFIG.get(str(consumer or ""))
    if not config:
        return {"ready": False, "status": "external_consumer_unknown"}
    root = Path(evidence_root or EVIDENCE_ROOT)
    db_path = root / "meta.sqlite" if evidence_root is not None else SQLITE_META_PATH
    parquet_root = root / "parquet" if evidence_root is not None else PARQUET_ROOT
    current_packet = _read_packet(db_path, config["current_key"])
    last_good_packet = _read_packet(db_path, config["source_last_good_key"])
    identity = _source_identity(consumer, current_packet)
    current_pointer = parquet_store.versioned_dataset_pointer(
        root=parquet_root, name=config["dataset"], pointer="current"
    )
    last_good_pointer = parquet_store.versioned_dataset_pointer(
        root=parquet_root, name=config["dataset"], pointer="last_good"
    )
    current_pointer_raw = _read_json(parquet_root / config["dataset"] / "current.json")
    last_good_pointer_raw = _read_json(parquet_root / config["dataset"] / "last_good.json")
    binding_value = current_packet.get("full_market_worker_replacement")
    binding = dict(binding_value) if isinstance(binding_value, Mapping) else {}
    last_good_binding_value = last_good_packet.get("full_market_worker_replacement")
    last_good_binding = (
        dict(last_good_binding_value)
        if isinstance(last_good_binding_value, Mapping)
        else {}
    )
    expected_artifact = (
        str(current_packet.get("result_artifact_sha256") or "")
        if consumer != "radar"
        else str(binding.get("source_result_artifact_sha256") or "")
    )
    expected_version = identity.get("generation")
    last_good_expected_artifact = (
        str(last_good_packet.get("result_artifact_sha256") or "")
        if consumer != "radar"
        else str(last_good_binding.get("source_result_artifact_sha256") or "")
    )
    last_good_expected_version = (
        str(last_good_packet.get("result_version_id") or "")
        if consumer != "radar"
        else str(last_good_binding.get("source_result_version_id") or "")
    )
    if consumer == "worker":
        consumer_shape_ready = bool(
            current_packet.get("result_dataset") == config["dataset"]
            and current_packet.get("result_version_id")
            and current_packet.get("result_artifact_sha256")
            and current_packet.get("transport_attestation_digest")
            and _safe_int(current_packet.get("batch_count")) > 0
            and _safe_int(current_packet.get("result_row_count")) > 0
        )
        last_good_shape_ready = bool(
            last_good_packet.get("result_dataset") == config["dataset"]
            and last_good_expected_version
            and last_good_expected_artifact
        )
    elif consumer == "factor":
        consumer_shape_ready = bool(
            current_packet.get("result_dataset") == "full_market_factor_research_results"
            and current_packet.get("full_market_factor_research") is True
            and _safe_int(current_packet.get("universe_count")) >= 3000
            and current_packet.get("neutralization_audit_digest")
        )
        last_good_shape_ready = bool(
            last_good_packet.get("result_dataset") == "full_market_factor_research_results"
            and last_good_expected_version
            and last_good_expected_artifact
        )
    else:
        consumer_shape_ready = bool(
            current_packet.get("packet_key") == "command_center_3_candidate_radar_cache"
            and binding.get("source_result_dataset") == config["dataset"]
            and binding.get("source_result_version_id")
            and binding.get("source_result_artifact_sha256")
            and _safe_int(binding.get("candidate_row_count")) > 0
            and binding.get("binding_digest")
            == _digest({key: value for key, value in binding.items() if key != "binding_digest"})
        )
        last_good_shape_ready = bool(
            last_good_packet.get("packet_key") == "command_center_3_candidate_radar_cache"
            and last_good_binding.get("source_result_dataset") == config["dataset"]
            and last_good_expected_version
            and last_good_expected_artifact
            and last_good_binding.get("binding_digest")
            == _digest(
                {
                    key: value
                    for key, value in last_good_binding.items()
                    if key != "binding_digest"
                }
            )
        )
    source_ready = bool(
        current_packet
        and last_good_packet
        and consumer_shape_ready
        and last_good_shape_ready
        and identity.get("subject")
        and identity.get("task_id")
        and len(str(identity.get("scope_hash") or "")) == 64
        and identity.get("generation")
        and current_pointer.get("status") == "ready"
        and last_good_pointer.get("status") == "ready"
        and current_pointer.get("version_id") == expected_version
        and current_pointer.get("artifact_sha256") == expected_artifact
        and current_pointer.get("artifact_sha256_actual") == expected_artifact
        and current_pointer.get("artifact_sha256_matches") is True
        and last_good_pointer.get("artifact_sha256_matches") is True
        and last_good_pointer.get("version_id") == last_good_expected_version
        and last_good_pointer.get("artifact_sha256") == last_good_expected_artifact
        and last_good_pointer.get("artifact_sha256_actual") == last_good_expected_artifact
        and current_pointer_raw
        and last_good_pointer_raw
    )
    material = {
        "schema_version": "command_center_3_external_production_source_binding.v1",
        "consumer": consumer,
        "head_full": external_trust._current_head_full(),
        "attestation_kind": config["kind"],
        "dataset": config["dataset"],
        "subject": identity.get("subject"),
        "task_id": identity.get("task_id"),
        "scope_hash": identity.get("scope_hash"),
        "generation": identity.get("generation"),
        "last_good_generation": last_good_expected_version,
        "source_current_packet_digest": _digest(current_packet) if current_packet else "",
        "source_last_good_packet_digest": _digest(last_good_packet) if last_good_packet else "",
        "current_pointer_digest": _digest(current_pointer_raw) if current_pointer_raw else "",
        "last_good_pointer_digest": _digest(last_good_pointer_raw) if last_good_pointer_raw else "",
        "current_artifact_file_digest": str(current_pointer.get("artifact_sha256_actual") or ""),
        "last_good_artifact_file_digest": str(
            last_good_pointer.get("artifact_sha256_actual") or ""
        ),
    }
    artifact_digest = _digest(material)
    return {
        **material,
        "ready": source_ready,
        "status": "external_consumer_source_exact_binding_verified"
        if source_ready
        else "external_consumer_source_binding_blocked",
        "artifact_digest": artifact_digest,
        "claims": identity.get("claims") or {},
        "writes_performed": False,
    }


def build_consumer_attestation_material(
    consumer: str, *, evidence_root: Path | None = None
) -> dict[str, Any]:
    """GET-safe material an external signer must bind; never writes or promotes."""

    return _source_binding(consumer, evidence_root=evidence_root)


def _write_packets_atomic(packets: Mapping[str, Mapping[str, Any]]) -> None:
    SQLiteMetaStore(SQLITE_META_PATH)
    encoded = {
        key: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        for key, value in packets.items()
    }
    now = datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(SQLITE_META_PATH, timeout=5)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for key, payload in encoded.items():
            connection.execute(
                "INSERT OR REPLACE INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?)",
                (key, payload, now),
            )
        rows = dict(
            connection.execute(
                f"SELECT packet_key, payload_json FROM packets WHERE packet_key IN ({','.join('?' for _ in encoded)})",
                tuple(encoded),
            ).fetchall()
        )
        if rows != encoded:
            raise RuntimeError("external_consumer_atomic_readback_mismatch")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _validate_claims(consumer: str, event: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    config = _CONFIG[consumer]
    return bool(
        event.get("attestation_kind") == config["kind"]
        and event.get("head_full") == source.get("head_full")
        and event.get("subject") == source.get("subject")
        and event.get("task_id") == source.get("task_id")
        and event.get("scope_hash") == source.get("scope_hash")
        and event.get("artifact_digest") == source.get("artifact_digest")
        and event.get("claims") == source.get("claims")
        and event.get("external_trust_verified") is True
        and event.get("production_trusted") is True
        and event.get("snapshot_rollback_resistant") is True
    )


def _strict_registry_consumer_matches(
    consumer: str,
    registry: Mapping[str, Any],
    canonical_registry: Mapping[str, Any],
    packet: Mapping[str, Any],
    event: Mapping[str, Any],
) -> bool:
    events = registry.get("events")
    events = [dict(row) for row in events] if isinstance(events, list) else []
    latest = events[-1] if events else {}
    source = packet.get("source_binding")
    source = dict(source) if isinstance(source, Mapping) else {}
    source_material = {
        key: value for key, value in source.items() if key != "artifact_digest"
    }
    consumer_key, _, _ = _consumer_keys(consumer)
    return bool(
        dict(registry) == dict(canonical_registry)
        and registry.get("schema_version") == external_trust.REGISTRY_SCHEMA_VERSION
        and registry.get("packet_key") == external_trust.REGISTRY_PACKET_KEY
        and registry.get("status")
        == "external_attestation_registry_production_trust_verified"
        and registry.get("head_full") == external_trust._current_head_full()
        and registry.get("head_full") == latest.get("head_full")
        and _strict_positive_int(registry.get("event_count"))
        and registry.get("event_count") == len(events)
        and registry.get("last_attestation_id") == latest.get("attestation_id")
        and _strict_positive_int(registry.get("last_monotonic_counter"))
        and registry.get("last_monotonic_counter") == latest.get("monotonic_counter")
        and _strict_positive_int(registry.get("head_key_epoch"))
        and registry.get("head_key_epoch") == latest.get("head_key_epoch")
        and registry.get("head_key_epoch_digest") == latest.get("head_key_epoch_digest")
        and registry.get("monotonic_anchor_digest") == latest.get("monotonic_anchor_digest")
        and registry.get("external_signature_verified") is True
        and registry.get("external_trust_verified") is True
        and registry.get("production_trusted") is True
        and registry.get("snapshot_rollback_resistant") is True
        and registry.get("private_key_generated") is False
        and registry.get("private_key_loaded") is False
        and registry.get("external_calls_triggered") is False
        and registry.get("contains_secret") is False
        and registry.get("does_not_execute_trades") is True
        and registry.get("blockers") == []
        and all(
            row.get("head_full") == registry.get("head_full")
            and _strict_positive_int(row.get("monotonic_counter"))
            and _strict_positive_int(row.get("head_key_epoch"))
            and row.get("external_signature_verified") is True
            and row.get("external_trust_verified") is True
            and row.get("production_trusted") is True
            and row.get("snapshot_rollback_resistant") is True
            and row.get("private_key_generated") is False
            and row.get("private_key_loaded") is False
            and row.get("contains_secret") is False
            and row.get("does_not_execute_trades") is True
            for row in events
        )
        and packet.get("schema_version") == CONSUMER_SCHEMA_VERSION
        and packet.get("packet_key") == consumer_key
        and packet.get("consumer") == consumer
        and packet.get("attestation_id") == event.get("attestation_id")
        and _strict_positive_int(packet.get("monotonic_counter"))
        and _strict_positive_int(event.get("monotonic_counter"))
        and packet.get("monotonic_counter") == event.get("monotonic_counter")
        and _strict_positive_int(packet.get("head_key_epoch"))
        and _strict_positive_int(event.get("head_key_epoch"))
        and packet.get("head_key_epoch") == event.get("head_key_epoch")
        and packet.get("head_key_epoch_digest") == event.get("head_key_epoch_digest")
        and packet.get("monotonic_anchor_digest") == event.get("monotonic_anchor_digest")
        and packet.get("external_signature_verified") is True
        and packet.get("external_trust_verified") is True
        and packet.get("production_trusted") is True
        and packet.get("snapshot_rollback_resistant") is True
        and packet.get("private_key_generated") is False
        and packet.get("private_key_loaded") is False
        and packet.get("external_calls_triggered") is False
        and packet.get("does_not_execute_trades") is True
        and packet.get("contains_secret") is False
        and source.get("consumer") == consumer
        and source.get("schema_version")
        == "command_center_3_external_production_source_binding.v1"
        and source.get("artifact_digest") == _digest(source_material)
        and event.get("attestation_kind") == _CONFIG[consumer]["kind"]
        and event.get("head_full") == source.get("head_full")
        and event.get("subject") == source.get("subject")
        and event.get("task_id") == source.get("task_id")
        and event.get("scope_hash") == source.get("scope_hash")
        and event.get("artifact_digest") == source.get("artifact_digest")
        and event.get("claims") == packet.get("claims")
        and event.get("external_trust_verified") is True
        and event.get("production_trusted") is True
        and event.get("snapshot_rollback_resistant") is True
    )


def _previous_current_matches_source_last_good(
    pointer: Mapping[str, Any],
    source: Mapping[str, Any],
) -> bool:
    packet = pointer.get("consumer_packet")
    packet = dict(packet) if isinstance(packet, Mapping) else {}
    previous_source = packet.get("source_binding")
    previous_source = (
        dict(previous_source) if isinstance(previous_source, Mapping) else {}
    )
    return bool(
        pointer.get("generation") == source.get("last_good_generation")
        and previous_source.get("generation") == source.get("last_good_generation")
        and previous_source.get("source_current_packet_digest")
        == source.get("source_last_good_packet_digest")
        and previous_source.get("current_artifact_file_digest")
        == source.get("last_good_artifact_file_digest")
    )


def _stored_pointer_matches(
    consumer: str,
    registry: Mapping[str, Any],
    canonical_registry: Mapping[str, Any],
    pointer: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    pointer_kind: str,
) -> bool:
    packet = pointer.get("consumer_packet")
    packet = dict(packet) if isinstance(packet, Mapping) else {}
    source = packet.get("source_binding")
    source = dict(source) if isinstance(source, Mapping) else {}
    _, current_key, last_good_key = _consumer_keys(consumer)
    return bool(
        pointer.get("schema_version") == POINTER_SCHEMA_VERSION
        and pointer.get("packet_key")
        == (current_key if pointer_kind == "current" else last_good_key)
        and pointer.get("pointer") == pointer_kind
        and pointer.get("consumer") == consumer
        and pointer.get("immutable") is True
        and pointer.get("attestation_id")
        == packet.get("attestation_id")
        == event.get("attestation_id")
        and pointer.get("generation") == source.get("generation")
        and pointer.get("consumer_packet_digest") == _digest(packet)
        and _strict_registry_consumer_matches(
            consumer,
            registry,
            canonical_registry,
            packet,
            event,
        )
    )


def validate_consumer(
    consumer: str, *, evidence_root: Path | None = None
) -> dict[str, Any]:
    consumer = str(consumer or "")
    if consumer not in _CONFIG:
        return {"ready": False, "status": "external_consumer_unknown", "writes_performed": False}
    db_path = Path(evidence_root) / "meta.sqlite" if evidence_root is not None else SQLITE_META_PATH
    consumer_key, current_key, last_good_key = _consumer_keys(consumer)
    packet = _read_packet(db_path, consumer_key)
    current = _read_packet(db_path, current_key)
    last_good = _read_packet(db_path, last_good_key)
    source = _source_binding(consumer, evidence_root=evidence_root)
    has_local_consumer_state = bool(source.get("ready") is True and packet and current and last_good)
    trusted = (
        external_trust.validate_trusted_registry()
        if has_local_consumer_state
        else {"ready": False}
    )
    canonical_validation = (
        external_trust.validate_registry()
        if has_local_consumer_state
        else {"canonical_registry": {}}
    )
    canonical_registry = canonical_validation.get("canonical_registry")
    canonical_registry = (
        dict(canonical_registry) if isinstance(canonical_registry, Mapping) else {}
    )
    registry_source, _ = (
        external_trust._read_registry_no_init()
        if has_local_consumer_state
        else ({}, "consumer_state_missing")
    )
    events = registry_source.get("events") if isinstance(registry_source.get("events"), list) else []
    consumer_events = [
        dict(row)
        for row in events
        if isinstance(row, Mapping)
        and row.get("attestation_kind") == _CONFIG[consumer]["kind"]
    ]
    event = next(
        (
            dict(row)
            for row in events
            if isinstance(row, Mapping)
            and row.get("attestation_id") == packet.get("attestation_id")
        ),
        {},
    )
    last_good_packet = last_good.get("consumer_packet")
    last_good_packet = (
        dict(last_good_packet) if isinstance(last_good_packet, Mapping) else {}
    )
    last_good_event = next(
        (
            dict(row)
            for row in events
            if isinstance(row, Mapping)
            and row.get("attestation_id") == last_good_packet.get("attestation_id")
        ),
        {},
    )
    expected_current_event = consumer_events[-1] if consumer_events else {}
    expected_last_good_event = (
        consumer_events[-2] if len(consumer_events) > 1 else expected_current_event
    )
    packet_digest = _digest(packet) if packet else ""
    ready = bool(
        source.get("ready") is True
        and trusted.get("ready") is True
        and packet.get("schema_version") == CONSUMER_SCHEMA_VERSION
        and packet.get("consumer") == consumer
        and packet.get("claims") == source.get("claims")
        and packet.get("source_binding") == {
            key: source.get(key)
            for key in source
            if key not in {"ready", "status", "claims", "writes_performed"}
        }
        and _validate_claims(consumer, event, source)
        and event == expected_current_event
        and _stored_pointer_matches(
            consumer,
            registry_source,
            canonical_registry,
            current,
            event,
            pointer_kind="current",
        )
        and current.get("generation") == source.get("generation")
        and current.get("consumer_packet_digest") == packet_digest
        and current.get("consumer_packet") == packet
        and last_good_event == expected_last_good_event
        and _stored_pointer_matches(
            consumer,
            registry_source,
            canonical_registry,
            last_good,
            last_good_event,
            pointer_kind="last_good",
        )
        and _previous_current_matches_source_last_good(last_good, source)
    )
    blockers: list[str] = []
    if source.get("ready") is not True:
        blockers.append("external_consumer_source_binding_missing_or_changed")
    if trusted.get("ready") is not True:
        blockers.append("external_consumer_trusted_registry_or_high_water_missing")
    if not packet or not current or not last_good:
        blockers.append("external_consumer_atomic_current_last_good_missing")
    if packet and not _validate_claims(consumer, event, source):
        blockers.append("external_consumer_attestation_exact_binding_mismatch")
    if not ready and not blockers:
        blockers.append("external_consumer_current_last_good_mismatch")
    return {
        "ready": ready,
        "status": f"external_{consumer}_production_consumer_verified"
        if ready
        else f"external_{consumer}_production_consumer_blocked",
        "consumer": consumer,
        "head_full": source.get("head_full") or external_trust._current_head_full(),
        "subject": source.get("subject") or "",
        "task_id": source.get("task_id") or "",
        "scope_hash": source.get("scope_hash") or "",
        "artifact_digest": source.get("artifact_digest") or "",
        "generation": source.get("generation") or "",
        "dataset": source.get("dataset") or "",
        "local_source_binding_ready": source.get("ready") is True,
        "external_trust_verified": trusted.get("ready") is True,
        "snapshot_rollback_resistant": ready,
        "production_trusted": ready,
        "blockers": blockers,
        "current_pointer": current,
        "last_good_pointer": last_good,
        "read_only": True,
        "writes_performed": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }


def import_and_promote_consumer(consumer: str, payload: Any) -> dict[str, Any]:
    consumer = str(consumer or "")
    if consumer not in _CONFIG:
        return {"ready": False, "status": "external_consumer_unknown", "writes_performed": False}
    external_trust.IMPORT_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with external_trust.IMPORT_LOCK_PATH.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        source = _source_binding(consumer)
        if source.get("ready") is not True:
            return {
                **source,
                "ready": False,
                "status": f"external_{consumer}_consumer_source_binding_blocked",
                "writes_performed": False,
            }
        prepared = external_trust.prepare_external_trusted_attestation(
            payload,
            expected_kind=_CONFIG[consumer]["kind"],
        )
        registry_packet = prepared.pop("_registry_packet", None)
        if prepared.get("ready") is not True or not isinstance(registry_packet, Mapping):
            return {**prepared, "ready": False, "writes_performed": False}
        if not _validate_claims(consumer, prepared, source):
            return {
                **prepared,
                "ready": False,
                "status": f"external_{consumer}_consumer_attestation_binding_invalid",
                "writes_performed": False,
            }
        consumer_key, current_key, last_good_key = _consumer_keys(consumer)
        source_packet = {
            key: source.get(key)
            for key in source
            if key not in {"ready", "status", "claims", "writes_performed"}
        }
        packet = {
            "schema_version": CONSUMER_SCHEMA_VERSION,
            "packet_key": consumer_key,
            "consumer": consumer,
            "attestation_id": prepared["attestation_id"],
            "monotonic_counter": prepared["monotonic_counter"],
            "head_key_epoch": prepared["head_key_epoch"],
            "head_key_epoch_digest": prepared["head_key_epoch_digest"],
            "monotonic_anchor_digest": prepared["monotonic_anchor_digest"],
            "source_binding": source_packet,
            "claims": source["claims"],
            "external_signature_verified": True,
            "external_trust_verified": True,
            "production_trusted": True,
            "snapshot_rollback_resistant": True,
            "private_key_generated": False,
            "private_key_loaded": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
            "contains_secret": False,
        }
        packet_digest = _digest(packet)
        current = {
            "schema_version": POINTER_SCHEMA_VERSION,
            "packet_key": current_key,
            "consumer": consumer,
            "pointer": "current",
            "generation": source["generation"],
            "attestation_id": prepared["attestation_id"],
            "consumer_packet_digest": packet_digest,
            "consumer_packet": packet,
            "immutable": True,
        }
        previous_current = _read_packet(SQLITE_META_PATH, current_key)
        previous_last_good = _read_packet(SQLITE_META_PATH, last_good_key)
        registry_events = [
            dict(row)
            for row in registry_packet.get("events") or []
            if isinstance(row, Mapping)
            and row.get("attestation_kind") == _CONFIG[consumer]["kind"]
        ]
        current_event = registry_events[-1] if registry_events else {}
        prior_event = registry_events[-2] if len(registry_events) > 1 else {}
        idempotent = prepared.get("idempotent_reuse") is True
        registry_current_ready = bool(
            current_event.get("attestation_id") == prepared.get("attestation_id")
            and current_event.get("attestation_kind") == _CONFIG[consumer]["kind"]
        )
        history_ready = False
        if idempotent:
            expected_last_good_event = prior_event or current_event
            history_ready = bool(
                registry_current_ready
                and _stored_pointer_matches(
                    consumer,
                    registry_packet,
                    registry_packet,
                    previous_current,
                    current_event,
                    pointer_kind="current",
                )
                and previous_current.get("generation") == source.get("generation")
                and _stored_pointer_matches(
                    consumer,
                    registry_packet,
                    registry_packet,
                    previous_last_good,
                    expected_last_good_event,
                    pointer_kind="last_good",
                )
                and _previous_current_matches_source_last_good(
                    previous_last_good,
                    source,
                )
            )
        elif prior_event:
            history_ready = bool(
                registry_current_ready
                and _stored_pointer_matches(
                    consumer,
                    registry_packet,
                    registry_packet,
                    previous_current,
                    prior_event,
                    pointer_kind="current",
                )
                and _previous_current_matches_source_last_good(
                    previous_current,
                    source,
                )
            )
        else:
            history_ready = bool(
                registry_current_ready
                and not previous_current
                and not previous_last_good
                and source.get("last_good_generation") == source.get("generation")
                and source.get("source_last_good_packet_digest")
                == source.get("source_current_packet_digest")
                and source.get("last_good_artifact_file_digest")
                == source.get("current_artifact_file_digest")
            )
        if not history_ready:
            return {
                "ready": False,
                "status": f"external_{consumer}_consumer_generation_history_invalid",
                "writes_performed": False,
                "production_trusted": False,
                "snapshot_rollback_resistant": False,
                "blockers": [
                    "external_consumer_last_good_previous_current_generation_mismatch"
                ],
            }
        if idempotent:
            last_good = previous_last_good
        elif prior_event:
            last_good = {
                **previous_current,
                "packet_key": last_good_key,
                "pointer": "last_good",
            }
        else:
            last_good = {
                **current,
                "packet_key": last_good_key,
                "pointer": "last_good",
            }
        packets = {
            external_trust.REGISTRY_PACKET_KEY: dict(registry_packet),
            consumer_key: packet,
            current_key: current,
            last_good_key: last_good,
        }
        try:
            _write_packets_atomic(packets)
        except Exception:
            readback = validate_consumer(consumer)
            if readback.get("ready") is True and current == readback.get("current_pointer"):
                return {
                    **readback,
                    "status": f"external_{consumer}_consumer_promoted_after_exception_reconciled",
                    "writes_performed": True,
                    "post_commit_exception_reconciled": True,
                }
            return {
                "ready": False,
                "status": f"external_{consumer}_consumer_atomic_promotion_failed",
                "writes_performed": False,
                "production_trusted": False,
                "snapshot_rollback_resistant": False,
                "blockers": ["external_consumer_registry_current_last_good_atomic_write_failed"],
            }
        readback = validate_consumer(consumer)
        return {
            **readback,
            "writes_performed": True,
            "promotion_written": readback.get("ready") is True,
            "post_commit_exception_reconciled": False,
        }


def read_phase2_status() -> dict[str, Any]:
    rows = [validate_consumer(name) for name in _CONFIG]
    return {
        "schema_version": "command_center_3_external_production_consumers_phase2.v1",
        "status": "external_production_consumers_phase2_ready"
        if all(row.get("ready") is True for row in rows)
        else "external_production_consumers_phase2_blocked",
        "ready": all(row.get("ready") is True for row in rows),
        "ready_count": sum(row.get("ready") is True for row in rows),
        "consumer_count": len(rows),
        "rows": rows,
        "get_writes_performed": False,
        "external_calls_triggered": False,
        "does_not_execute_trades": True,
        "contains_secret": False,
    }
