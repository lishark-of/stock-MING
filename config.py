import os
from functools import lru_cache
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


CONFIG_NAMES = {
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_TOKEN_1",
    "DEEPSEEK_TOKEN_2",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "DATABASE_URL",
    "TUSHARE_TOKEN",
}


def _clean_value(value, default=None):
    if value is None:
        return default
    value = str(value).strip()
    return value or default


@lru_cache(maxsize=1)
def _load_local_streamlit_secrets():
    secrets_path = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists() or tomllib is None:
        return {}

    try:
        with secrets_path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _get_streamlit_secret(name, default=None):
    try:
        import streamlit as st

        return _clean_value(st.secrets.get(name), default)
    except Exception:
        return default


def get_config_value(name, default=None):
    """Read config from Streamlit secrets first, then environment variables."""

    if name not in CONFIG_NAMES:
        return default

    local_secrets = _load_local_streamlit_secrets()
    value = _clean_value(local_secrets.get(name))
    if value:
        return value

    value = _get_streamlit_secret(name)
    if value:
        return value

    return _clean_value(os.environ.get(name), default)


def get_deepseek_keys(extra_keys=None):
    keys = [
        get_config_value("DEEPSEEK_API_KEY"),
        get_config_value("DEEPSEEK_TOKEN_1"),
        get_config_value("DEEPSEEK_TOKEN_2"),
    ]
    keys.extend(extra_keys or [])

    cleaned = []
    for key in keys:
        key = _clean_value(key)
        if key and key not in cleaned:
            cleaned.append(key)
    return cleaned


def get_supabase_config():
    return get_config_value("SUPABASE_URL"), get_config_value("SUPABASE_KEY")


def get_tushare_token(default=None):
    """Read Tushare token without exposing it in logs or UI."""

    value = _clean_value(os.environ.get("TUSHARE_TOKEN"))
    if value:
        return value

    local_secrets = _load_local_streamlit_secrets()
    value = _clean_value(local_secrets.get("TUSHARE_TOKEN"))
    if value:
        return value

    return _get_streamlit_secret("TUSHARE_TOKEN", default)


def require_supabase_config():
    url, key = get_supabase_config()
    missing = []
    if not url:
        missing.append("SUPABASE_URL")
    if not key:
        missing.append("SUPABASE_KEY")
    if missing:
        raise RuntimeError(f"缺少 Supabase 配置：{', '.join(missing)}")
    return url, key


def require_deepseek_keys():
    keys = get_deepseek_keys()
    if not keys:
        raise RuntimeError("缺少 DeepSeek 配置：DEEPSEEK_API_KEY、DEEPSEEK_TOKEN_1 或 DEEPSEEK_TOKEN_2")
    return keys
