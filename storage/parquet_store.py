from __future__ import annotations

from pathlib import Path
from typing import Any


def dependency_status() -> dict[str, Any]:
    try:
        import pandas as pd  # noqa: F401
        import pyarrow  # noqa: F401
    except Exception as exc:
        return {"available": False, "error_message_safe": str(exc)}
    return {"available": True, "error_message_safe": ""}


def factor_values_path(root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> Path:
    return Path(root) / f"{name}.parquet"


def factor_values_metadata(root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> dict[str, Any]:
    path = factor_values_path(root=root, name=name)
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


def write_factor_values(df: Any, root: str | Path = ".stock_ming_3/parquet", name: str = "factor_values") -> dict[str, Any]:
    status = dependency_status()
    if not status["available"]:
        return {"status": "dependency_missing", **status}
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    out = factor_values_path(root=root_path, name=name)
    df.to_parquet(out, index=False)
    return {"status": "written", "path": str(out), "row_count": int(len(df))}


def read_factor_values(path: str | Path) -> Any:
    status = dependency_status()
    if not status["available"]:
        return {"status": "dependency_missing", **status}
    import pandas as pd

    return pd.read_parquet(path)
