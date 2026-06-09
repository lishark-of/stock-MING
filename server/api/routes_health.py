from __future__ import annotations

from fastapi import APIRouter

from server.schemas.packets import envelope


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return envelope(
        {
            "service": "stock-MING Command Center 3.0",
            "status": "ok",
            "legacy_streamlit": "retained_for_admin_debug",
            "external_calls_on_startup": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "real_trading_enabled": False,
        }
    )
