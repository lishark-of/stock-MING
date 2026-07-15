from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import quote


class SQLiteMetaStore:
    def __init__(
        self,
        db_path: str | Path = ".stock_ming_3/meta.sqlite",
        *,
        read_only: bool = False,
    ) -> None:
        self.db_path = Path(db_path)
        self.read_only = bool(read_only)
        if not self.read_only:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init()

    def _connect(self) -> sqlite3.Connection:
        if self.read_only:
            db_uri = f"file:{quote(str(self.db_path.resolve()), safe='/')}?mode=ro"
            return sqlite3.connect(db_uri, uri=True)
        return sqlite3.connect(self.db_path)

    def _init(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS packets (
                    packet_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_status (
                    task_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_status_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    task_type TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_digest TEXT NOT NULL
                )
                """
            )
            history_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(task_status_history)").fetchall()
            }
            if "task_type" not in history_columns:
                conn.execute(
                    "ALTER TABLE task_status_history ADD COLUMN task_type TEXT NOT NULL DEFAULT ''"
                )
            conn.execute(
                """
                UPDATE task_status_history
                SET task_type = json_extract(payload_json, '$.task_type')
                WHERE task_type = ''
                  AND json_valid(payload_json)
                  AND json_type(payload_json, '$.task_type') = 'text'
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_status_history_task_latest
                ON task_status_history(task_id, history_id DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_status_history_type_latest
                ON task_status_history(task_type, history_id DESC, task_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_status_history_payload_type_latest
                ON task_status_history(
                    CASE
                        WHEN json_valid(payload_json)
                        THEN json_extract(payload_json, '$.task_type')
                        ELSE ''
                    END,
                    history_id DESC,
                    task_id
                )
                """
            )
            conn.commit()

    def write_packet(self, packet_key: str, packet: Any) -> dict[str, Any]:
        now = _dt.datetime.now().isoformat(timespec="seconds")
        payload = json.dumps(packet, ensure_ascii=False, default=str)
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?)",
                (packet_key, payload, now),
            )
            conn.commit()
        return {"packet_key": packet_key, "updated_at": now, "status": "written"}

    def promote_packet_atomic(self, packet_key: str, packet: Any) -> dict[str, Any]:
        """Atomically replace a packet and verify the exact payload before commit."""

        now = _dt.datetime.now().isoformat(timespec="microseconds")
        payload = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        payload_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with closing(self._connect()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT OR REPLACE INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?)",
                    (packet_key, payload, now),
                )
                row = conn.execute(
                    "SELECT payload_json FROM packets WHERE packet_key = ?",
                    (packet_key,),
                ).fetchone()
                if row is None or str(row[0]) != payload:
                    raise RuntimeError("atomic_packet_readback_mismatch")
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {
            "packet_key": packet_key,
            "updated_at": now,
            "status": "atomic_promoted",
            "payload_digest": payload_digest,
            "transaction_committed": True,
            "readback_verified_before_commit": True,
        }

    def promote_packet_pair_atomic(
        self,
        current_key: str,
        current_packet: Any,
        last_good_key: str,
        last_good_packet: Any,
    ) -> dict[str, Any]:
        """Atomically replace current and last-good packets with exact readback."""

        now = _dt.datetime.now().isoformat(timespec="microseconds")
        pairs = (
            (current_key, json.dumps(current_packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)),
            (last_good_key, json.dumps(last_good_packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)),
        )
        with closing(self._connect()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                for packet_key, payload in pairs:
                    conn.execute(
                        "INSERT OR REPLACE INTO packets(packet_key, payload_json, updated_at) VALUES (?, ?, ?)",
                        (packet_key, payload, now),
                    )
                    row = conn.execute(
                        "SELECT payload_json FROM packets WHERE packet_key = ?",
                        (packet_key,),
                    ).fetchone()
                    if row is None or str(row[0]) != payload:
                        raise RuntimeError("atomic_packet_pair_readback_mismatch")
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {
            "status": "atomic_pair_promoted",
            "current_key": current_key,
            "last_good_key": last_good_key,
            "updated_at": now,
            "transaction_committed": True,
            "readback_verified_before_commit": True,
            "current_payload_digest": hashlib.sha256(pairs[0][1].encode("utf-8")).hexdigest(),
            "last_good_payload_digest": hashlib.sha256(pairs[1][1].encode("utf-8")).hexdigest(),
        }

    def read_packet(self, packet_key: str) -> Any:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT payload_json FROM packets WHERE packet_key = ?", (packet_key,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def read_packet_with_metadata(self, packet_key: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT payload_json, updated_at FROM packets WHERE packet_key = ?",
                (packet_key,),
            ).fetchone()
        if row is None:
            return None
        return {"payload": json.loads(row[0]), "updated_at": str(row[1])}

    def list_packet_metadata(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT packet_key, payload_json, updated_at FROM packets ORDER BY updated_at DESC, packet_key").fetchall()
        items = []
        for packet_key, payload_json, updated_at in rows:
            try:
                payload = json.loads(payload_json)
            except Exception:
                payload = {}
            items.append(
                {
                    "packet_key": packet_key,
                    "updated_at": updated_at,
                    "schema_version": payload.get("schema_version") if isinstance(payload, dict) else None,
                    "status": payload.get("status") if isinstance(payload, dict) else None,
                    "mode": payload.get("mode") if isinstance(payload, dict) else None,
                    "payload_bytes": len(str(payload_json).encode("utf-8")),
                }
            )
        return items

    def write_task_status(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = str(task.get("task_id") or "")
        if not task_id:
            raise ValueError("task_id is required")
        now = _dt.datetime.now().isoformat(timespec="seconds")
        payload = json.dumps(task, ensure_ascii=False, default=str)
        payload_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT OR REPLACE INTO task_status(task_id, payload_json, updated_at) VALUES (?, ?, ?)",
                (task_id, payload, now),
            )
            conn.execute(
                """
                INSERT INTO task_status_history(
                    task_id, task_type, payload_json, updated_at, payload_digest
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, str(task.get("task_type") or ""), payload, now, payload_digest),
            )
            conn.commit()
        return {
            "task_id": task_id,
            "updated_at": now,
            "status": "written",
            "payload_digest": payload_digest,
            "history_appended": True,
        }

    def read_task_status(self, task_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT payload_json FROM task_status WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def list_task_metadata(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT task_id, payload_json, updated_at FROM task_status ORDER BY updated_at DESC, task_id").fetchall()
        items = []
        for task_id, payload_json, updated_at in rows:
            try:
                payload = json.loads(payload_json)
            except Exception:
                payload = {}
            items.append(
                {
                    "task_id": task_id,
                    "updated_at": updated_at,
                    "task_type": payload.get("task_type") if isinstance(payload, dict) else None,
                    "status": payload.get("status") if isinstance(payload, dict) else None,
                    "progress": payload.get("progress") if isinstance(payload, dict) else None,
                    "current_step": payload.get("current_step") if isinstance(payload, dict) else None,
                    "output_packet_key": payload.get("output_packet_key") if isinstance(payload, dict) else None,
                    "backend": payload.get("backend") if isinstance(payload, dict) else None,
                    "payload_bytes": len(str(payload_json).encode("utf-8")),
                }
            )
        return items

    @staticmethod
    def _validated_task_history_projection(
        row: tuple[Any, ...],
        *,
        expected_task_type: str | None = None,
        expected_receipt_key: str | None = None,
        expected_receipt_schema_version: str | None = None,
    ) -> dict[str, Any]:
        (
            history_id,
            sql_task_id,
            stored_task_type,
            payload_json,
            updated_at,
            stored_digest,
            task_type_binding_source,
        ) = row
        sql_task_id_text = str(sql_task_id or "")
        stored_task_type_text = str(stored_task_type or "")
        payload_json_text = str(payload_json or "")
        stored_digest_text = str(stored_digest or "")
        actual_digest = hashlib.sha256(payload_json_text.encode("utf-8")).hexdigest()
        metadata = {
            "task_id": sql_task_id_text,
            "task_type": expected_task_type or stored_task_type_text,
            "status": "history_integrity_failed_safe",
            "current_step": "historical_evidence_rejected",
            "storage_source": "sqlite_task_status_history_invalid",
            "historical_evidence": True,
            "current_actionable": False,
            "history_integrity_valid": False,
            "history_integrity_error": "",
            "history_id": int(history_id),
            "history_updated_at": str(updated_at),
            "history_payload_digest": stored_digest_text,
            "history_actual_payload_digest": actual_digest,
            "history_lookup_query_count": 1,
            "history_task_type_binding_source": str(task_type_binding_source),
        }
        if actual_digest != stored_digest_text:
            metadata["history_integrity_error"] = "payload_digest_mismatch"
            return metadata
        try:
            payload = json.loads(payload_json_text)
        except Exception:
            metadata["history_integrity_error"] = "payload_json_invalid"
            return metadata
        if not isinstance(payload, dict):
            metadata["history_integrity_error"] = "payload_not_object"
            return metadata
        if str(payload.get("task_id") or "") != sql_task_id_text:
            metadata["history_integrity_error"] = "sql_task_id_payload_task_id_mismatch"
            return metadata
        payload_task_type = str(payload.get("task_type") or "")
        if (
            str(task_type_binding_source) == "stored_task_type_column"
            and stored_task_type_text != payload_task_type
        ):
            metadata["history_integrity_error"] = "stored_task_type_payload_task_type_mismatch"
            return metadata
        if expected_task_type is not None and payload_task_type != str(expected_task_type):
            metadata["history_integrity_error"] = "requested_task_type_payload_task_type_mismatch"
            return metadata
        if expected_receipt_key is not None:
            payload_safe = payload.get("payload_safe")
            receipt = payload_safe.get(expected_receipt_key) if isinstance(payload_safe, dict) else None
            if not isinstance(receipt, dict):
                metadata["history_integrity_error"] = "expected_receipt_missing_or_invalid"
                return metadata
            if (
                expected_receipt_schema_version is not None
                and str(receipt.get("schema_version") or "") != str(expected_receipt_schema_version)
            ):
                metadata["history_integrity_error"] = "expected_receipt_schema_version_mismatch"
                return metadata
        projection = dict(payload)
        projection.update(metadata)
        projection["status"] = payload.get("status")
        projection["current_step"] = payload.get("current_step")
        projection["storage_source"] = "sqlite_task_status_history"
        projection["history_integrity_valid"] = True
        projection["history_integrity_error"] = ""
        return projection

    def read_latest_task_status_history(self, task_id: str) -> dict[str, Any] | None:
        """Read and validate the newest append-only projection for one task id."""

        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT
                    history_id,
                    task_id,
                    task_type,
                    payload_json,
                    updated_at,
                    payload_digest,
                    'stored_task_type_column'
                FROM task_status_history
                WHERE task_id = ?
                ORDER BY history_id DESC
                LIMIT 1
                """,
                (str(task_id),),
            ).fetchone()
        if row is None:
            return None
        return self._validated_task_history_projection(row)

    def read_latest_task_status_history_by_type(
        self,
        task_type: str,
        *,
        expected_receipt_key: str,
        expected_receipt_schema_version: str,
    ) -> dict[str, Any] | None:
        """Read the newest per-task projection of a type in one indexed query."""

        with closing(self._connect()) as conn:
            history_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(task_status_history)").fetchall()
            }
            has_task_type_column = "task_type" in history_columns
            query = self._latest_task_status_history_by_type_query(has_task_type_column)
            params = (
                (str(task_type), str(task_type))
                if has_task_type_column
                else (str(task_type),)
            )
            row = conn.execute(query, params).fetchone()
        if row is None:
            return None
        projection = self._validated_task_history_projection(
            row,
            expected_task_type=str(task_type),
            expected_receipt_key=str(expected_receipt_key),
            expected_receipt_schema_version=str(expected_receipt_schema_version),
        )
        projection["history_schema_probe_query_count"] = 1
        return projection

    @staticmethod
    def _latest_task_status_history_by_type_query(has_task_type_column: bool) -> str:
        payload_task_type = """
            CASE
                WHEN json_valid(h.payload_json)
                THEN json_extract(h.payload_json, '$.task_type')
                ELSE ''
            END
        """
        if has_task_type_column:
            stored_task_type = "h.task_type"
            binding_source = "stored_task_type_column"
            target_match = f"(h.task_type = ? OR {payload_task_type} = ?)"
        else:
            stored_task_type = payload_task_type
            binding_source = "legacy_payload_json_only"
            target_match = f"({payload_task_type} = ?)"
        return f"""
            SELECT
                h.history_id,
                h.task_id,
                {stored_task_type},
                h.payload_json,
                h.updated_at,
                h.payload_digest,
                '{binding_source}'
            FROM task_status_history AS h
            WHERE {target_match}
              AND NOT EXISTS (
                  SELECT 1
                  FROM task_status_history AS newer
                  WHERE newer.task_id = h.task_id
                    AND newer.history_id > h.history_id
              )
            ORDER BY h.history_id DESC
            LIMIT 1
        """

    def explain_latest_task_status_history_by_type_query(self, task_type: str) -> list[str]:
        """Expose the read-only query plan for focused index regression tests."""

        with closing(self._connect()) as conn:
            history_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(task_status_history)").fetchall()
            }
            has_task_type_column = "task_type" in history_columns
            query = self._latest_task_status_history_by_type_query(has_task_type_column)
            params = (
                (str(task_type), str(task_type))
                if has_task_type_column
                else (str(task_type),)
            )
            rows = conn.execute(f"EXPLAIN QUERY PLAN {query}", params).fetchall()
        return [str(row[3]) for row in rows]

    def task_status_history_count(self, task_id: str | None = None) -> int:
        with closing(self._connect()) as conn:
            if task_id is None:
                row = conn.execute("SELECT COUNT(*) FROM task_status_history").fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM task_status_history WHERE task_id = ?",
                    (str(task_id),),
                ).fetchone()
        return int(row[0] if row else 0)

    def clear_task_statuses(self, *, preserve_history: bool = True) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(*) FROM task_status").fetchone()
            deleted = int(row[0] if row else 0)
            conn.execute("DELETE FROM task_status")
            history_deleted = 0
            if not preserve_history:
                history_row = conn.execute("SELECT COUNT(*) FROM task_status_history").fetchone()
                history_deleted = int(history_row[0] if history_row else 0)
                conn.execute("DELETE FROM task_status_history")
            conn.commit()
        return {
            "status": "cleared",
            "deleted_count": deleted,
            "history_preserved": bool(preserve_history),
            "history_deleted_count": history_deleted,
        }
