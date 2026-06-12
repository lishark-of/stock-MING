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


def read_factor_values(path: str | Path) -> Any:
    status = dependency_status()
    if not status["available"]:
        return {"status": "dependency_missing", **status}
    import pandas as pd

    return pd.read_parquet(path)
