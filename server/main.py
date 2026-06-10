from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api import (
    routes_chokepoint,
    routes_factor_quant,
    routes_health,
    routes_migration,
    routes_next_session,
    routes_packets,
    routes_quant,
    routes_serenity,
    routes_storage,
    routes_tasks,
    routes_trade_review,
)


app = FastAPI(
    title="stock-MING Command Center 3.0",
    version="3.0.0-mvp",
    description="FastAPI packet/task facade for the Tauri + React Command Center migration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "tauri://localhost"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_migration.router)
app.include_router(routes_packets.router)
app.include_router(routes_next_session.router)
app.include_router(routes_quant.router)
app.include_router(routes_factor_quant.router)
app.include_router(routes_chokepoint.router)
app.include_router(routes_serenity.router)
app.include_router(routes_storage.router)
app.include_router(routes_tasks.router)
app.include_router(routes_trade_review.router)
