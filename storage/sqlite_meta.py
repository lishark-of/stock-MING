from __future__ import annotations

import datetime as _dt
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

    def read_packet(self, packet_key: str) -> Any:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT payload_json FROM packets WHERE packet_key = ?", (packet_key,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def write_task_status(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = str(task.get("task_id") or "")
        if not task_id:
            raise ValueError("task_id is required")
        now = _dt.datetime.now().isoformat(timespec="seconds")
        payload = json.dumps(task, ensure_ascii=False, default=str)
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO task_status(task_id, payload_json, updated_at) VALUES (?, ?, ?)",
                (task_id, payload, now),
            )
            conn.commit()
        return {"task_id": task_id, "updated_at": now, "status": "written"}

    def read_task_status(self, task_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT payload_json FROM task_status WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0])
