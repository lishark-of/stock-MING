"""Data-capability registry schema for governance.

The registry is a pure in-memory state index for the command center capability mesh.
It must not call external APIs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


STATUS_UNKNOWN = "unknown"
STATUS_AVAILABLE = "available"
STATUS_NO_PERMISSION = "no_permission"
STATUS_FAILED = "failed"
STATUS_NO_DATA = "no_data"
STATUS_CACHED = "cached"
STATUS_SKIPPED = "skipped"

TIER_CORE = "core"
TIER_SUPPORT = "support"

MARKET_GLOBAL = "GLOBAL"
MARKET_A_SHARE = "A_SHARE"
MARKET_ETF = "ETF"
MARKET_US = "US"


_CAPABILITY_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "Tushare 日线/行情",
        "provider": "Tushare",
        "market": MARKET_A_SHARE,
        "tier": TIER_CORE,
        "api": "daily",
        "key": "tushare_daily_quote",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "A股日线、基础行情和近似实时行情，是持仓估值与趋势判断的基础数据能力。",
    },
    {
        "name": "Tushare ETF",
        "provider": "Tushare",
        "market": MARKET_ETF,
        "tier": TIER_CORE,
        "api": "etf_basic",
        "key": "tushare_etf",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "ETF 基础资料、跟踪指数和赛道配置数据，用于 ETF / 融资动作判断。",
    },
    {
        "name": "Tushare 个股资金流",
        "provider": "Tushare",
        "market": MARKET_A_SHARE,
        "tier": TIER_CORE,
        "api": "moneyflow",
        "key": "tushare_moneyflow",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "A股个股资金流，用于确认主力资金、短线拥挤度和下一票证据链。",
    },
    {
        "name": "Tushare 龙虎榜",
        "provider": "Tushare",
        "market": MARKET_A_SHARE,
        "tier": TIER_CORE,
        "api": "top_list",
        "key": "tushare_lhb",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "龙虎榜与机构席位线索，用于判断机构行为和题材热度是否可验证。",
    },
    {
        "name": "Tushare 融资融券",
        "provider": "Tushare",
        "market": MARKET_A_SHARE,
        "tier": TIER_CORE,
        "api": "margin_detail",
        "key": "tushare_margin",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "融资融券明细，用于融资账户风险预算、杠杆状态和加减仓约束。",
    },
    {
        "name": "Tushare 公告",
        "provider": "Tushare",
        "market": MARKET_A_SHARE,
        "tier": TIER_CORE,
        "api": "anns_d",
        "key": "tushare_announcements",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "公告、减持、质押和监管风险线索，用于阻断追高或加融资。",
    },
    {
        "name": "Tushare 涨跌停",
        "provider": "Tushare",
        "market": MARKET_A_SHARE,
        "tier": TIER_CORE,
        "api": "limit_cpt_list",
        "key": "tushare_limit_emotion",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "涨跌停、连板和情绪边界，用于识别追高风险和题材温度。",
    },
    {
        "name": "Tushare 指数成分/权重",
        "provider": "Tushare",
        "market": MARKET_A_SHARE,
        "tier": TIER_SUPPORT,
        "api": "index_weight",
        "key": "tushare_index_weight",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "指数成分和权重，用于行业/指数归因和 ETF 替代判断。",
    },
    {
        "name": "Tushare 筹码/胜率",
        "provider": "Tushare",
        "market": MARKET_A_SHARE,
        "tier": TIER_CORE,
        "api": "cyq_perf",
        "key": "tushare_chip_winrate",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "筹码分布、胜率和获利盘压力，用于策略执行与风险路径验证。",
    },
    {
        "name": "AkShare 个股资金",
        "provider": "AkShare",
        "market": MARKET_A_SHARE,
        "tier": TIER_CORE,
        "api": "akshare_money_flow",
        "key": "akshare_money_flow",
        "used_in_decision": True,
        "requires_user_action": True,
        "description": "AkShare 个股资金补充数据；慢接口必须由按钮触发并记录超时/失败。",
    },
    {
        "name": "AkShare 概念",
        "provider": "AkShare",
        "market": MARKET_A_SHARE,
        "tier": TIER_SUPPORT,
        "api": "akshare_concept",
        "key": "akshare_concept",
        "used_in_decision": False,
        "requires_user_action": True,
        "description": "AkShare 概念和题材补充，用于解释 A股题材热度，不自动重刷。",
    },
    {
        "name": "AkShare 行业",
        "provider": "AkShare",
        "market": MARKET_A_SHARE,
        "tier": TIER_SUPPORT,
        "api": "akshare_industry",
        "key": "akshare_industry",
        "used_in_decision": False,
        "requires_user_action": True,
        "description": "AkShare 行业补充数据，用于行业轮动和市场风格解释。",
    },
    {
        "name": "AkShare 盘口/补充数据",
        "provider": "AkShare",
        "market": MARKET_A_SHARE,
        "tier": TIER_SUPPORT,
        "api": "akshare_realtime_board",
        "key": "akshare_realtime_board",
        "used_in_decision": False,
        "requires_user_action": True,
        "description": "AkShare 盘口和补充行情数据，慢接口需要按钮触发并设置超时。",
    },
    {
        "name": "yfinance 行情",
        "provider": "yfinance",
        "market": MARKET_GLOBAL,
        "tier": TIER_CORE,
        "api": "yfinance_quote",
        "key": "yfinance_quote",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "美股/全球行情基础数据，用于价格、持仓估值和趋势确认。",
    },
    {
        "name": "yfinance 财报/基本面",
        "provider": "yfinance",
        "market": MARKET_US,
        "tier": TIER_CORE,
        "api": "yfinance_financials",
        "key": "yfinance_financials",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "美股财报、EPS/Revenue growth 和基本面数据，用于美股分析方法。",
    },
    {
        "name": "yfinance 行业/宏观代理",
        "provider": "yfinance",
        "market": MARKET_US,
        "tier": TIER_SUPPORT,
        "api": "yfinance_market_context",
        "key": "yfinance_market_context",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "美股行业、指数和宏观代理数据，用于 RS、行业轮动和利率压力解释。",
    },
    {
        "name": "Supabase 记忆",
        "provider": "Supabase",
        "market": MARKET_GLOBAL,
        "tier": TIER_CORE,
        "api": "brain_memory",
        "key": "supabase_memory",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "Supabase 记忆，用于历史偏好、投研记录和作战上下文。",
    },
    {
        "name": "Supabase 投喂",
        "provider": "Supabase",
        "market": MARKET_GLOBAL,
        "tier": TIER_SUPPORT,
        "api": "market_news",
        "key": "supabase_feed",
        "used_in_decision": False,
        "requires_user_action": False,
        "description": "Supabase 投喂资料，用于新闻、资料和人工投喂来源回读。",
    },
    {
        "name": "Supabase 历史记录",
        "provider": "Supabase",
        "market": MARKET_GLOBAL,
        "tier": TIER_SUPPORT,
        "api": "trade_history",
        "key": "supabase_trade_history",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "历史交易、复盘和作战记录，用于仓位纪律与胜率归因。",
    },
    {
        "name": "Supabase 回测缓存",
        "provider": "Supabase",
        "market": MARKET_GLOBAL,
        "tier": TIER_SUPPORT,
        "api": "backtest_cache",
        "key": "supabase_backtest_cache",
        "used_in_decision": True,
        "requires_user_action": False,
        "description": "回测缓存和纪律结果缓存，用于避免页面打开自动跑完整回测。",
    },
    {
        "name": "Home Snapshot",
        "provider": "Home Snapshot",
        "market": MARKET_GLOBAL,
        "tier": TIER_SUPPORT,
        "api": "home_action_snapshot",
        "key": "home_snapshot",
        "used_in_decision": False,
        "requires_user_action": False,
        "description": "本地上次作战快照，用于 App 秒开和离线/失败时保留上次成功结果。",
    },
    {
        "name": "DeepSeek 解释",
        "provider": "DeepSeek",
        "market": MARKET_GLOBAL,
        "tier": TIER_SUPPORT,
        "api": "deepseek_explain",
        "key": "deepseek_explain",
        "used_in_decision": False,
        "requires_user_action": True,
        "description": "DeepSeek/大模型解释能力，只在用户点击满血综合推演或解释按钮后记录调用状态。",
    },
]


def _is_etf_target(ticker: str) -> bool:
    code = str((ticker or "").strip().upper())
    if ".SH" in code or ".SZ" in code or ".SS" in code:
        code = code.split(".")[0]
    return bool(code.isdigit() and len(code) == 6 and code.startswith(("5", "15", "16", "18", "159")))


def _market_scope_from_request(market_type: str, target: str = "") -> str:
    normalized = str(market_type or "").strip().upper()
    if _is_etf_target(target):
        return MARKET_ETF
    if normalized.startswith("A_SHARE"):
        return MARKET_A_SHARE
    if normalized.startswith("US") or normalized.startswith("US_STOCK"):
        return MARKET_US
    return MARKET_GLOBAL


def _default_status_for_market(item: dict[str, Any], target_market: str) -> str:
    item_market = str(item.get("market") or "").upper()
    if item_market == MARKET_GLOBAL:
        return STATUS_UNKNOWN
    if target_market == MARKET_ETF:
        return STATUS_UNKNOWN if item_market == MARKET_ETF else STATUS_SKIPPED
    if target_market == MARKET_A_SHARE:
        return STATUS_SKIPPED if item_market == MARKET_US else STATUS_UNKNOWN
    if target_market == MARKET_US:
        return STATUS_SKIPPED if item_market == MARKET_A_SHARE else STATUS_UNKNOWN
    return STATUS_UNKNOWN


def _clone_def(item: dict[str, Any]) -> dict[str, Any]:
    payload = dict(item)
    payload.setdefault("key", payload.get("name") or payload.get("api") or "")
    payload.setdefault("status", STATUS_UNKNOWN)
    payload.setdefault("last_success_at", "")
    payload.setdefault("last_error", "")
    payload.setdefault("requires_user_action", False)
    payload.setdefault("used_in_decision", False)
    payload.setdefault("description", "数据能力治理项。")
    payload.setdefault("latency_ms", 0)
    payload.setdefault("updated_at", "")
    payload.setdefault("action_hint", "页面打开不自动调用。")
    return payload


def build_initial_capability_registry(
    target: str = "",
    market_type: str = "",
    checked_at: str | None = None,
) -> dict[str, Any]:
    """Create a clean registry scaffold. No external calls."""

    now = checked_at or datetime.now().isoformat(timespec="seconds")
    target_market = _market_scope_from_request(market_type, target)
    items = []
    for definition in _CAPABILITY_DEFINITIONS:
        item = _clone_def(definition)
        item.update(
            {
                "status": _default_status_for_market(item, target_market),
                "last_success_at": "",
                "last_error": "",
                "updated_at": "",
            }
        )
        items.append(item)

    return {
        "version": "mvp_v1",
        "market_type": target_market,
        "target": str(target or "").upper().strip(),
        "generated_at": now,
        "updated_at": now,
        "items": items,
    }


def to_status_dict(raw_status: Any) -> str:
    status = str(raw_status or "").strip().lower()
    if status in {
        STATUS_UNKNOWN,
        STATUS_AVAILABLE,
        STATUS_NO_PERMISSION,
        STATUS_FAILED,
        STATUS_NO_DATA,
        STATUS_CACHED,
        STATUS_SKIPPED,
    }:
        return status
    return STATUS_UNKNOWN


def snapshot_to_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for item in registry.get("items") or []:
        if not isinstance(item, dict):
            continue
        keys = {
            str(item.get("key") or ""),
            str(item.get("name") or ""),
            str(item.get("api") or ""),
            str(item.get("provider") or ""),
        }
        for row_key in keys:
            if row_key:
                mapping[row_key.lower()] = item
    return mapping


def _coerce_latency_ms(latency_ms: Any) -> int:
    try:
        return int(latency_ms or 0)
    except Exception:
        return 0


def update_capability_status(
    registry: dict[str, Any],
    name: str,
    status: Any,
    *,
    last_success_at: str = "",
    last_error: str = "",
    requires_user_action: bool | None = None,
    used_in_decision: bool | None = None,
    latency_ms: int | float | None = None,
    provider: str = "",
    api: str = "",
    action_hint: str | None = None,
) -> dict[str, Any]:
    """Return a copy of registry with one item updated."""

    payload = dict(registry)
    normalized = to_status_dict(status)
    target = str(name or "").strip().lower()
    provider_l = str(provider or "").strip().lower()
    api_l = str(api or "").strip().lower()
    now = datetime.now().isoformat(timespec="seconds")

    existing_items = list(payload.get("items") or [])
    updated_items: list[dict[str, Any]] = []
    found = False

    for raw_item in existing_items:
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        key = str(item.get("key") or "").strip().lower()
        item_name = str(item.get("name") or "").strip().lower()
        item_provider = str(item.get("provider") or "").strip().lower()
        item_api = str(item.get("api") or "").strip().lower()

        matched = False
        if key == target:
            matched = True
        elif item_name == target:
            matched = True
        elif item_provider == target and item_api == api_l:
            matched = True
        elif provider_l and item_provider == provider_l and item_api == api_l:
            matched = True
        elif api_l and item_api == api_l:
            matched = True

        if not matched:
            updated_items.append(item)
            continue

        item["status"] = normalized
        item["last_success_at"] = str(last_success_at or item.get("last_success_at") or "")
        item["last_error"] = str(last_error or "")
        item["updated_at"] = now
        if latency_ms is not None:
            item["latency_ms"] = _coerce_latency_ms(latency_ms)
        if requires_user_action is not None:
            item["requires_user_action"] = bool(requires_user_action)
        if used_in_decision is not None:
            item["used_in_decision"] = bool(used_in_decision)
        if action_hint is not None:
            item["action_hint"] = str(action_hint)
        if not item.get("action_hint"):
            item["action_hint"] = "页面打开不自动调用。"
        updated_items.append(item)
        found = True

    if not found and target:
        fallback_name = str(name or api or provider or "数据能力").strip()
        updated_items.append(
            {
                "name": fallback_name,
                "provider": provider or "unknown",
                "market": MARKET_GLOBAL,
                "tier": TIER_SUPPORT,
                "api": api or fallback_name,
                "key": fallback_name,
                "status": normalized,
                "last_success_at": str(last_success_at or ""),
                "last_error": str(last_error or ""),
                "requires_user_action": bool(requires_user_action or False),
                "used_in_decision": bool(used_in_decision or False),
                "latency_ms": _coerce_latency_ms(latency_ms),
                "updated_at": now,
                "action_hint": str(action_hint or "页面打开不自动调用。"),
            }
        )

    payload["items"] = updated_items
    payload["updated_at"] = now
    payload["version"] = payload.get("version", "mvp_v1")
    return payload
