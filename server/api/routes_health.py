from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter

from config import get_deepseek_model_strategy
from server.schemas.packets import envelope


router = APIRouter()


@router.get("/health")
def health() -> dict:
    checked_at = _dt.datetime.now().isoformat(timespec="seconds")
    return envelope(
        {
            "service": "stock-MING Command Center 3.0",
            "status": "ok",
            "legacy_streamlit": "retained_for_admin_debug",
            "cache_only": True,
            "read_only": True,
            "external_calls_on_startup": False,
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "provider_or_model_calls": False,
            "real_trading_enabled": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "does_not_modify_operation_zones": True,
            "contains_secret": False,
            "deepseek_model_strategy": get_deepseek_model_strategy(),
        },
        call_ledger=[
            {
                "api": "local_health_check",
                "source": "FastAPI health route and local config",
                "call_status": "cache_read",
                "local_fetched_at": checked_at,
                "external": False,
                "external_calls_triggered": False,
                "tushare_called": False,
                "deepseek_called": False,
                "github_called": False,
                "does_not_execute_trades": True,
                "does_not_modify_strategy_action": True,
            }
        ],
        warnings=[
            "GET /health 只读检查 FastAPI 启动状态和本地模型策略配置；不会调用 Tushare、DeepSeek 或 GitHub。",
            "健康检查不读取 token/key，不执行真实交易，不修改 strategy action。",
        ],
    )
