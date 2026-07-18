"""Byte-write-free SQLite access for local evidence validators."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def immutable_evidence_connection(db_path: Path) -> sqlite3.Connection | None:
    """Open stable evidence without creating journals or shared memory.

    Immutable SQLite cannot safely merge an outstanding WAL. Evidence readers
    therefore fail closed whenever WAL, SHM, or rollback-journal companions are
    present instead of opening the database and risking a checkpoint or new SHM
    file. Callers own and must close the returned connection.
    """

    try:
        if db_path.is_symlink() or not db_path.is_file():
            return None
        companions = tuple(
            Path(f"{db_path}{suffix}") for suffix in ("-wal", "-shm", "-journal")
        )
        if any(path.exists() or path.is_symlink() for path in companions):
            return None
        resolved = db_path.resolve(strict=True)
        connection = sqlite3.connect(
            f"{resolved.as_uri()}?mode=ro&immutable=1",
            uri=True,
        )
        connection.execute("PRAGMA query_only = ON")
        if any(path.exists() or path.is_symlink() for path in companions):
            connection.close()
            return None
        return connection
    except (OSError, sqlite3.Error, ValueError):
        return None
