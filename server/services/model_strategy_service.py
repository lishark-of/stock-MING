from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from config import DEEPSEEK_MODEL_CONFIG_KEYS, DEEPSEEK_MODEL_DEFAULTS, get_config_value, get_deepseek_model


PACKET_KEY = "command_center_3_deepseek_model_strategy_cache"
SCHEMA_VERSION = "deepseek_model_strategy_cache.v1"
MODEL_PURPOSES = ("default", "explain", "projection", "factor_explain", "fast", "healthcheck", "feeder")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return {"serialization_error_safe": "deepseek_model_strategy_cache_not_json_serializable"}


def _active_config_key(purpose: str) -> str | None:
    for key in DEEPSEEK_MODEL_CONFIG_KEYS.get(purpose, ()):
        if get_config_value(key):
            return key
    return None


def _purpose_row(purpose: str) -> dict[str, Any]:
    active_key = _active_config_key(purpose)
    config_keys = list(DEEPSEEK_MODEL_CONFIG_KEYS.get(purpose, ()))
    fallback_model = DEEPSEEK_MODEL_DEFAULTS.get(purpose, DEEPSEEK_MODEL_DEFAULTS["default"])
    return {
        "purpose": purpose,
        "model": get_deepseek_model(purpose),
        "fallback_model": fallback_model,
        "config_keys": config_keys,
        "active_config_key": active_key,
        "uses_configured_value": bool(active_key),
        "uses_safe_default": not bool(active_key),
        "call_policy": "manual_only",
        "external_call_on_cache_read": False,
    }


def read_deepseek_model_strategy_cache() -> dict[str, Any]:
    rows = [_purpose_row(purpose) for purpose in MODEL_PURPOSES]
    configured_count = sum(1 for row in rows if row["uses_configured_value"])
    fast_purposes = [row["purpose"] for row in rows if row["purpose"] in {"fast", "healthcheck", "feeder"}]
    explain_purposes = [row["purpose"] for row in rows if row["purpose"] in {"default", "explain", "projection", "factor_explain"}]
    loaded_at = _now_iso()

    packet = {
        "packet_key": PACKET_KEY,
        "schema_version": SCHEMA_VERSION,
        "status": "ready",
        "mode": "cache_only",
        "cache_only": True,
        "read_only": True,
        "loaded_at": loaded_at,
        "summary": "DeepSeek 模型策略只读展示；模型名来自 DEEPSEEK_*_MODEL 配置或集中默认值，不在调用点硬编码。",
        "model_rows": rows,
        "purpose_groups": {
            "explain_grade": explain_purposes,
            "fast_grade": fast_purposes,
        },
        "counts": {
            "purpose_count": len(rows),
            "configured_count": configured_count,
            "safe_default_count": len(rows) - configured_count,
        },
        "policy": {
            "cache_api_external_calls": False,
            "does_not_call_deepseek": True,
            "does_not_read_api_keys": True,
            "does_not_expose_credentials": True,
            "does_not_call_tushare": True,
            "does_not_call_github": True,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "post_task_required_for_model_call": True,
            "model_names_are_configurable": True,
            "callsite_hardcoding_allowed": False,
            "contains_secret": False,
        },
        "external_calls_triggered": False,
        "tushare_called": False,
        "deepseek_called": False,
        "github_called": False,
        "does_not_execute_trades": True,
        "does_not_modify_strategy_action": True,
        "contains_secret": False,
        "call_ledger": [
            {
                "api": "local_deepseek_model_strategy_cache",
                "source": "config.get_deepseek_model and DEEPSEEK_*_MODEL names",
                "row_count": len(rows),
                "local_fetched_at": loaded_at,
                "call_status": "cache_read",
                "external": False,
            }
        ],
        "warnings": [
            "GET /api/model-strategy/cache 只读展示 DeepSeek 模型策略，不调用模型。",
            "模型名可通过 DEEPSEEK_EXPLAIN_MODEL、DEEPSEEK_FAST_MODEL、DEEPSEEK_DEFAULT_MODEL 调整；页面不展示凭据。",
            "DeepSeek 只能解释已有结构化结果，不作为数据源，也不修改 strategy action。",
        ],
    }
    return _json_safe(packet)
