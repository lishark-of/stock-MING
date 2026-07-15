from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class SQLiteMetaStore:
    def __init__(self, db_path: str | Path = ".stock_ming_3/meta.sqlite") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
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
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_digest TEXT NOT NULL
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
                "INSERT INTO task_status_history(task_id, payload_json, updated_at, payload_digest) VALUES (?, ?, ?, ?)",
                (task_id, payload, now, payload_digest),
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

    def read_latest_task_status_history(self, task_id: str) -> dict[str, Any] | None:
        """Read the newest append-only task projection when the live row is absent."""

        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT payload_json, updated_at, payload_digest
                FROM task_status_history
                WHERE task_id = ?
                ORDER BY history_id DESC
                LIMIT 1
                """,
                (str(task_id),),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row[0])
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        payload["storage_source"] = "sqlite_task_status_history"
        payload["history_updated_at"] = str(row[1])
        payload["history_payload_digest"] = str(row[2])
        return payload

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
