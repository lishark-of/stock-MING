import os
from functools import lru_cache
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


CONFIG_NAMES = {
    "COMMAND_CENTER_BOOTSTRAP_MODE",
    "COMMAND_CENTER_LIVE_ALLOW_FULL_POOL",
    "COMMAND_CENTER_LIVE_BOOTSTRAP_RATE_LIMIT_SECONDS",
    "COMMAND_CENTER_LIVE_BOOTSTRAP_SYMBOL_LIMIT",
    "COMMAND_CENTER_LIVE_DEEPSEEK_MODEL",
    "COMMAND_CENTER_LIVE_DEEPSEEK_ON_OPEN",
    "COMMAND_CENTER_LIVE_TUSHARE_ON_OPEN",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_AUTO_EXPLAIN_ENABLED",
    "DEEPSEEK_DEFAULT_MODEL",
    "DEEPSEEK_EXPLAIN_MODEL",
    "DEEPSEEK_FACTOR_EXPLAIN_MODE",
    "DEEPSEEK_FAST_MODEL",
    "DEEPSEEK_TOKEN_1",
    "DEEPSEEK_TOKEN_2",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "DATABASE_URL",
    "TUSHARE_TOKEN",
}

DEEPSEEK_FACTOR_EXPLAIN_MODES = {"manual_only", "auto_after_task", "disabled"}

DEEPSEEK_MODEL_DEFAULTS = {
    "default": "deepseek-v4-pro",
    "explain": "deepseek-v4-pro",
    "projection": "deepseek-v4-pro",
    "factor_explain": "deepseek-v4-pro",
    "fast": "deepseek-v4-flash",
    "healthcheck": "deepseek-v4-flash",
    "feeder": "deepseek-v4-flash",
}

DEEPSEEK_MODEL_CONFIG_KEYS = {
    "default": ("DEEPSEEK_DEFAULT_MODEL",),
    "explain": ("DEEPSEEK_EXPLAIN_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "projection": ("DEEPSEEK_EXPLAIN_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "factor_explain": ("DEEPSEEK_EXPLAIN_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "fast": ("DEEPSEEK_FAST_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "healthcheck": ("DEEPSEEK_FAST_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
    "feeder": ("DEEPSEEK_FAST_MODEL", "DEEPSEEK_DEFAULT_MODEL"),
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


def get_deepseek_model(purpose="default", default=None):
    """Read DeepSeek model selection from secrets/env without exposing credentials."""

    selected_purpose = str(purpose or "default").strip().lower()
    config_keys = DEEPSEEK_MODEL_CONFIG_KEYS.get(selected_purpose, DEEPSEEK_MODEL_CONFIG_KEYS["default"])
    for key in config_keys:
        value = get_config_value(key)
        if value:
            return value
    if default:
        return _clean_value(default, DEEPSEEK_MODEL_DEFAULTS["default"])
    return DEEPSEEK_MODEL_DEFAULTS.get(selected_purpose, DEEPSEEK_MODEL_DEFAULTS["default"])


def get_deepseek_model_strategy():
    """Return the current model strategy for diagnostics without any token/key material."""

    strategy = {
        purpose: get_deepseek_model(purpose)
        for purpose in DEEPSEEK_MODEL_DEFAULTS
    }
    strategy.update({
        "source": "DEEPSEEK_*_MODEL config or safe defaults",
        "contains_secret": False,
    })
    return strategy


def get_deepseek_factor_explain_mode(default="manual_only"):
    """Return the governed DeepSeek factor explanation mode.

    The mode is intentionally separate from model selection: cache reads and
    page renders must remain no-call regardless of the selected model.
    """

    selected = _clean_value(get_config_value("DEEPSEEK_FACTOR_EXPLAIN_MODE"), default)
    selected = str(selected or default).strip().lower()
    return selected if selected in DEEPSEEK_FACTOR_EXPLAIN_MODES else default


def get_deepseek_auto_explain_enabled(default=False):
    value = _clean_value(get_config_value("DEEPSEEK_AUTO_EXPLAIN_ENABLED"))
    if value is None:
        return bool(default)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


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
