from __future__ import annotations

import datetime
import hashlib
import json
import math
import re
from typing import Any, Callable

import pandas as pd
import streamlit as st

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy is optional for sanitizing only
    np = None

try:
    from visual_components import (
        render_next_ticket_holding_card,
        render_next_ticket_research_summary,
    )
except Exception:  # pragma: no cover - UI fallback for partial deployments
    render_next_ticket_holding_card = None
    render_next_ticket_research_summary = None


NEXT_TICKET_REPORT_TYPE = "next_ticket_research"
NEXT_TICKET_SOURCE = "next_ticket_radar_deepseek"
NEXT_TICKET_VERSION = 1

ALLOWED_BATTLE_STATES = ["可准备", "等验证", "只观察", "暂不纳入", "风险过高"]
ALLOWED_SWITCH_RELATIONS = ["接力观察", "替代观察", "防守观察", "暂不替代"]
FORBIDDEN_OUTPUT_WORDS = ["必买", "买入", "满仓", "梭哈", "立即清仓", "保证收益", "预测必涨"]

DEFAULT_CANDIDATES = [
    {"ticker": "002837.SZ", "name": "英维克"},
    {"ticker": "601138.SH", "name": "工业富联"},
    {"ticker": "002158.SZ", "name": "汉钟精机"},
    {"ticker": "002335.SZ", "name": "科华数据"},
    {"ticker": "603986.SH", "name": "兆易创新"},
]

TECH_SAMPLE_POOL = [
    *DEFAULT_CANDIDATES,
    {"ticker": "300308.SZ", "name": "中际旭创"},
    {"ticker": "300502.SZ", "name": "新易盛"},
    {"ticker": "688041.SH", "name": "海光信息"},
]

STOCK_NAME_MAP = {
    item["ticker"]: item["name"] for item in TECH_SAMPLE_POOL
}
STOCK_NAME_MAP.update(
    {
        "002008.SZ": "大族激光",
    }
)

RADAR_SCAN_STATE_KEY = "radar_scan_results"
DEEP_RESEARCH_STATE_KEY = "deep_research_results"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            text = (
                value.strip()
                .replace(",", "")
                .replace("¥", "")
                .replace("￥", "")
                .replace("%", "")
                .replace("亿", "")
                .replace("万元", "")
                .replace("万", "")
            )
            if text in {"", "--", "暂无", "暂无数据", "N/A", "nan", "None"}:
                return default
            value = text
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except Exception:
        return default


def _clip_score(value: Any) -> int:
    number = _num(value, 0) or 0
    return int(max(0, min(100, round(number))))


def _ticker_core(ticker: str) -> str:
    text = str(ticker or "").upper().strip()
    text = text.replace(".SS", "").replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    digits = re.sub(r"\D", "", text.split(".")[0])
    return digits.zfill(6) if digits else text


def normalize_display_ticker(raw: Any) -> str:
    text = str(raw or "").upper().strip()
    text = text.replace("，", ",").replace("。", ".").replace(".SS", ".SH")
    if not text:
        return ""
    if text.endswith((".SZ", ".SH", ".BJ")):
        code = _ticker_core(text)
        suffix = text[-2:]
        return f"{code}.{suffix}" if re.fullmatch(r"\d{6}", code) else text
    code = _ticker_core(text)
    if re.fullmatch(r"\d{6}", code):
        if code.startswith(("6", "9")):
            return f"{code}.SH"
        if code.startswith(("0", "2", "3")):
            return f"{code}.SZ"
        if code.startswith(("4", "8")):
            return f"{code}.BJ"
    return text


def to_app_ticker(display_ticker: str) -> str:
    ticker = normalize_display_ticker(display_ticker)
    return ticker[:-3] + ".SS" if ticker.endswith(".SH") else ticker


def infer_market_type(display_ticker: str) -> str:
    ticker = normalize_display_ticker(display_ticker)
    if ticker.endswith((".SZ", ".SH", ".BJ")):
        return "A_SHARE"
    if ticker.endswith(".HK"):
        return "HK_STOCK"
    if ticker.endswith(".T"):
        return "JP_STOCK"
    return "US_STOCK"


def candidate_name(ticker: str, fallback: str = "") -> str:
    display = normalize_display_ticker(ticker)
    return str(fallback or STOCK_NAME_MAP.get(display) or display).strip()


def sanitize_for_json(value: Any) -> Any:
    """Convert dirty pandas/numpy/runtime values into JSON-safe values."""
    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return {"available": False, "message": "暂无可验证数据", "rows": []}
        safe_df = value.replace([float("inf"), float("-inf")], pd.NA)
        safe_df = safe_df.where(pd.notna(safe_df), None)
        return sanitize_for_json(safe_df.to_dict("records"))
    if isinstance(value, pd.Series):
        return sanitize_for_json(value.to_dict())
    if np is not None:
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            number = float(value)
            return number if math.isfinite(number) else None
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.ndarray):
            return sanitize_for_json(value.tolist())
    if isinstance(value, dict):
        if not value:
            return {"available": False, "message": "暂无可验证数据"}
        return {str(k): sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(item) for item in value]
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        return value
    except Exception:
        return str(value)


def safe_json_dumps(value: Any, **kwargs: Any) -> str:
    options = {"ensure_ascii": False, "allow_nan": False, "default": str}
    options.update(kwargs)
    return json.dumps(sanitize_for_json(value), **options)


def _safe_json_loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except Exception:
        return None


def _safe_call(callbacks: dict[str, Callable[..., Any]], name: str, *args: Any, **kwargs: Any) -> Any:
    func = callbacks.get(name)
    if not callable(func):
        return None
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        return {"available": False, "message": "暂无可验证数据", "error": str(exc)}


def parse_candidate_text(text: str) -> list[dict[str, str]]:
    parts = re.split(r"[,，\n\r\t ]+", str(text or ""))
    rows = []
    seen = set()
    for part in parts:
        ticker = normalize_display_ticker(part)
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        rows.append({"ticker": ticker, "name": candidate_name(ticker)})
    return rows


def _candidate_text(rows: list[dict[str, str]]) -> str:
    return ", ".join(row["ticker"] for row in rows if row.get("ticker"))


def load_watchlist_candidates(callbacks: dict[str, Callable[..., Any]]) -> tuple[list[dict[str, str]], str]:
    loaded = _safe_call(callbacks, "load_announcement_watchlist")
    if isinstance(loaded, tuple) and len(loaded) >= 2:
        payload, error = loaded[0], loaded[1]
    elif isinstance(loaded, dict):
        payload, error = loaded, ""
    else:
        payload, error = {}, "持续调查池暂不可读取"
    if error:
        return [], str(error)
    rows = []
    for item in (payload or {}).get("targets") or []:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        ticker = normalize_display_ticker(item.get("ts_code") or item.get("ticker") or item.get("stock_code"))
        if ticker:
            rows.append({"ticker": ticker, "name": candidate_name(ticker, item.get("name") or item.get("stock_name") or "")})
    return _dedupe_candidates(rows), ""


def _walk_focus_payload(value: Any) -> list[dict[str, str]]:
    rows = []
    if isinstance(value, dict):
        ticker = value.get("ticker") or value.get("ts_code") or value.get("stock_code") or value.get("code")
        if ticker:
            display = normalize_display_ticker(ticker)
            if display:
                rows.append({"ticker": display, "name": candidate_name(display, value.get("name") or value.get("stock_name") or "")})
        for child in value.values():
            if isinstance(child, (dict, list)):
                rows.extend(_walk_focus_payload(child))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_walk_focus_payload(item))
    return rows


def load_today_focus_structured_candidates(supabase: Any) -> tuple[list[dict[str, str]], str]:
    if not supabase:
        return [], "Supabase 不可用，今日关注池结构化候选暂不可读取。"
    try:
        res = (
            supabase.table("stock_reports")
            .select("report_content, created_at")
            .eq("report_type", "today_focus_pool")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return [], "未找到今日关注池缓存。"
        payload = _safe_json_loads(rows[0].get("report_content"))
        if not isinstance(payload, (dict, list)):
            return [], "今日关注池当前不是结构化 JSON，本阶段不解析 DeepSeek 长文。"
        return _dedupe_candidates(_walk_focus_payload(payload)), ""
    except Exception as exc:
        return [], f"读取今日关注池结构化候选失败：{exc}"


def _dedupe_candidates(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result = []
    seen = set()
    for row in rows or []:
        ticker = normalize_display_ticker((row or {}).get("ticker"))
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        item = dict(row or {})
        item["ticker"] = ticker
        item["name"] = candidate_name(ticker, item.get("name") or "")
        result.append(item)
    return result


def _scan_params_hash(params: dict[str, Any]) -> str:
    return hashlib.sha256(safe_json_dumps(params, sort_keys=True).encode("utf-8")).hexdigest()


def _adapter_from_callbacks(callbacks: dict[str, Callable[..., Any]]) -> Any:
    adapter = callbacks.get("tushare_adapter")
    if adapter is not None:
        return adapter
    try:
        import tushare_adapter as adapter_module

        return adapter_module
    except Exception:
        return None


def _result_frame(result: Any) -> pd.DataFrame:
    if not isinstance(result, dict) or not result.get("ok"):
        return pd.DataFrame()
    data = result.get("data")
    if isinstance(data, pd.DataFrame):
        return data.copy()
    return pd.DataFrame()


def _display_from_ts_code(value: Any) -> str:
    return normalize_display_ticker(str(value or "").replace(".SS", ".SH"))


def _is_main_board_ticker(ticker: str, exclude_chinext: bool, exclude_star: bool, exclude_bj: bool) -> bool:
    display = normalize_display_ticker(ticker)
    code = _ticker_core(display)
    if display.endswith(".BJ"):
        return not exclude_bj
    if display.endswith(".SH"):
        if code.startswith("688"):
            return not exclude_star
        return code.startswith(("600", "601", "603", "605", "606", "609", "900"))
    if display.endswith(".SZ"):
        if code.startswith("300"):
            return not exclude_chinext
        return code.startswith(("000", "001", "002", "003"))
    return False


def _is_st_or_delisting(name: Any) -> bool:
    text = str(name or "").upper().replace(" ", "")
    return any(flag in text for flag in ["ST", "*ST", "退市", "退", "PT"])


def load_a_share_main_board_pool(
    callbacks: dict[str, Callable[..., Any]],
    *,
    exclude_st: bool = True,
    exclude_chinext: bool = True,
    exclude_star: bool = True,
    exclude_bj: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    adapter = _adapter_from_callbacks(callbacks)
    meta = {
        "source": "Tushare stock_basic",
        "degraded": False,
        "message": "",
        "raw_count": 0,
        "filtered_count": 0,
    }
    if adapter is None or not hasattr(adapter, "get_stock_basic"):
        meta["degraded"] = True
        meta["message"] = "Tushare stock_basic 不可用，已降级为科技股样本池。"
        return pd.DataFrame(TECH_SAMPLE_POOL), meta

    try:
        result = adapter.get_stock_basic(exchange="", list_status="L")
        frame = _result_frame(result)
        if frame.empty:
            meta["degraded"] = True
            meta["message"] = (result or {}).get("error") or "stock_basic 返回为空，已降级为科技股样本池。"
            return pd.DataFrame(TECH_SAMPLE_POOL), meta
    except Exception as exc:
        meta["degraded"] = True
        meta["message"] = f"stock_basic 读取失败，已降级为科技股样本池：{exc}"
        return pd.DataFrame(TECH_SAMPLE_POOL), meta

    meta["raw_count"] = len(frame)
    if "list_status" in frame.columns:
        frame = frame[frame["list_status"].astype(str).str.upper().eq("L")].copy()
    meta["listed_count"] = len(frame)
    frame["ticker"] = frame["ts_code"].map(_display_from_ts_code) if "ts_code" in frame.columns else ""
    frame["symbol"] = frame["symbol"].astype(str) if "symbol" in frame.columns else frame["ticker"].map(_ticker_core)
    frame["name"] = frame["name"].astype(str) if "name" in frame.columns else ""
    frame["market"] = frame["market"].astype(str) if "market" in frame.columns else ""
    frame["exchange"] = frame["exchange"].astype(str) if "exchange" in frame.columns else ""
    board_mask = frame["ticker"].map(lambda value: _is_main_board_ticker(value, exclude_chinext, exclude_star, exclude_bj))
    st_mask = ~frame["name"].map(_is_st_or_delisting)
    meta["after_st_exclusion_count"] = int(st_mask.sum()) if exclude_st else len(frame)
    meta["after_board_exclusion_count"] = int(board_mask.sum())
    frame = frame[board_mask].copy()
    if exclude_st:
        frame = frame[~frame["name"].map(_is_st_or_delisting)].copy()
    frame = frame.drop_duplicates(subset=["ticker"]).reset_index(drop=True)
    meta["filtered_count"] = len(frame)
    if frame.empty:
        meta["degraded"] = True
        meta["message"] = "A股主板过滤后为空，已降级为科技股样本池。"
        return pd.DataFrame(TECH_SAMPLE_POOL), meta
    return frame[["ticker", "symbol", "name", "market", "exchange"]], meta


def recent_trade_dates(callbacks: dict[str, Callable[..., Any]], days: int = 130) -> list[str]:
    adapter = _adapter_from_callbacks(callbacks)
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days)
    if adapter is not None and hasattr(adapter, "get_trade_cal"):
        try:
            result = adapter.get_trade_cal(start.isoformat(), today.isoformat())
            frame = _result_frame(result)
            if not frame.empty and "cal_date" in frame.columns:
                if "is_open" in frame.columns:
                    frame = frame[pd.to_numeric(frame["is_open"], errors="coerce").fillna(0).astype(int).eq(1)]
                dates = sorted(str(item) for item in frame["cal_date"].dropna().astype(str).unique())
                if dates:
                    return dates
        except Exception:
            pass
    fallback = []
    day = start
    while day <= today:
        if day.weekday() < 5:
            fallback.append(day.strftime("%Y%m%d"))
        day += datetime.timedelta(days=1)
    return fallback


def fetch_cross_section_window(
    callbacks: dict[str, Callable[..., Any]],
    trade_dates: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    adapter = _adapter_from_callbacks(callbacks)
    meta = {
        "daily_source": "Tushare daily 横截面",
        "daily_basic_source": "Tushare daily_basic 横截面",
        "daily_rows": 0,
        "daily_basic_rows": 0,
        "latest_trade_date": max(trade_dates) if trade_dates else "",
        "degraded": False,
        "message": "",
        "daily_fetch_mode": "range_cross_section",
        "daily_requests": 1,
    }
    if adapter is None or not hasattr(adapter, "get_daily"):
        meta["degraded"] = True
        meta["message"] = "Tushare daily 横截面接口不可用。"
        return pd.DataFrame(), pd.DataFrame(), meta

    if not trade_dates:
        meta["degraded"] = True
        meta["message"] = "未取得交易日历。"
        return pd.DataFrame(), pd.DataFrame(), meta

    start_date = min(trade_dates)
    end_date = max(trade_dates)
    try:
        daily_result = adapter.get_daily("", start_date, end_date)
        daily = _result_frame(daily_result)
        if daily.empty:
            meta["degraded"] = True
            meta["message"] = (daily_result or {}).get("error") or "daily 横截面返回为空。"
            return pd.DataFrame(), pd.DataFrame(), meta
    except Exception as exc:
        meta["degraded"] = True
        meta["message"] = f"daily 横截面读取失败：{exc}"
        return pd.DataFrame(), pd.DataFrame(), meta

    daily["ticker"] = daily["ts_code"].map(_display_from_ts_code) if "ts_code" in daily.columns else ""
    daily["trade_date"] = daily["trade_date"].astype(str) if "trade_date" in daily.columns else ""
    unique_dates = daily["trade_date"].dropna().astype(str).nunique() if "trade_date" in daily.columns else 0
    if unique_dates < 60:
        frames = []
        request_count = 0
        # Still cross-sectional: one full-market request per trade date, never one request per ticker.
        for trade_date in trade_dates[-70:]:
            try:
                day_result = adapter.get_daily("", trade_date, trade_date)
                day_frame = _result_frame(day_result)
                request_count += 1
                if not day_frame.empty:
                    frames.append(day_frame)
            except Exception:
                request_count += 1
                continue
        if frames:
            daily = pd.concat(frames, ignore_index=True)
            daily["ticker"] = daily["ts_code"].map(_display_from_ts_code) if "ts_code" in daily.columns else ""
            daily["trade_date"] = daily["trade_date"].astype(str) if "trade_date" in daily.columns else ""
            meta["daily_fetch_mode"] = "per_trade_date_cross_section"
            meta["daily_requests"] = request_count
        else:
            meta["daily_fetch_mode"] = "range_cross_section_insufficient"
    meta["daily_rows"] = len(daily)

    daily_basic = pd.DataFrame()
    if hasattr(adapter, "get_daily_basic"):
        try:
            basic_result = adapter.get_daily_basic("", end_date, end_date)
            daily_basic = _result_frame(basic_result)
            if not daily_basic.empty:
                daily_basic["ticker"] = daily_basic["ts_code"].map(_display_from_ts_code) if "ts_code" in daily_basic.columns else ""
                daily_basic["trade_date"] = daily_basic["trade_date"].astype(str) if "trade_date" in daily_basic.columns else ""
                meta["daily_basic_rows"] = len(daily_basic)
            else:
                meta["daily_basic_message"] = (basic_result or {}).get("error") or "daily_basic 横截面返回为空。"
        except Exception as exc:
            meta["daily_basic_message"] = f"daily_basic 横截面读取失败：{exc}"
    return daily, daily_basic, meta


def build_cross_section_rough_candidates(
    callbacks: dict[str, Callable[..., Any]],
    *,
    scan_limit: int,
    refine_limit: int,
    exclude_st: bool,
    exclude_chinext: bool,
    exclude_star: bool,
    exclude_bj: bool,
    exclude_low_amount: bool,
    trend_up_only: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool, pool_meta = load_a_share_main_board_pool(
        callbacks,
        exclude_st=exclude_st,
        exclude_chinext=exclude_chinext,
        exclude_star=exclude_star,
        exclude_bj=exclude_bj,
    )
    if pool_meta.get("degraded"):
        candidates = [
            {**item, "scan_source": "fallback_tech_sample", "rough_context": {"data_gaps": ["A股主板横截面池不可用"]}}
            for item in TECH_SAMPLE_POOL[:refine_limit]
        ]
        return candidates, {"pool": pool_meta, "degraded": True, "message": pool_meta.get("message"), "rough_count": len(candidates)}

    dates = recent_trade_dates(callbacks, days=150)
    window_dates = dates[-90:] if len(dates) >= 90 else dates
    daily, daily_basic, data_meta = fetch_cross_section_window(callbacks, window_dates)
    if daily.empty:
        candidates = [
            {**item, "scan_source": "fallback_tech_sample", "rough_context": {"data_gaps": ["daily 横截面不可用"]}}
            for item in TECH_SAMPLE_POOL[:refine_limit]
        ]
        return candidates, {"pool": pool_meta, "cross_section": data_meta, "degraded": True, "message": data_meta.get("message"), "rough_count": len(candidates)}

    pool_tickers = set(pool["ticker"].astype(str))
    daily = daily[daily["ticker"].isin(pool_tickers)].copy()
    if daily.empty:
        candidates = [
            {**item, "scan_source": "fallback_tech_sample", "rough_context": {"data_gaps": ["daily 与主板池无交集"]}}
            for item in TECH_SAMPLE_POOL[:refine_limit]
        ]
        return candidates, {"pool": pool_meta, "cross_section": data_meta, "degraded": True, "message": "daily 与主板池无交集", "rough_count": len(candidates)}

    daily["close"] = pd.to_numeric(daily.get("close"), errors="coerce")
    daily["amount"] = pd.to_numeric(daily.get("amount"), errors="coerce")
    daily = daily.dropna(subset=["ticker", "trade_date", "close"]).sort_values(["ticker", "trade_date"])
    grouped = daily.groupby("ticker", group_keys=False)
    daily["MA20"] = grouped["close"].transform(lambda series: series.rolling(20, min_periods=20).mean())
    daily["MA60"] = grouped["close"].transform(lambda series: series.rolling(60, min_periods=60).mean())
    daily["close_20d_ago"] = grouped["close"].shift(20)
    daily["twenty_day_return_pct"] = (daily["close"] / daily["close_20d_ago"] - 1) * 100

    latest = grouped.tail(1).copy()
    latest_trade_date = max(daily["trade_date"].dropna().astype(str)) if not daily.empty else data_meta.get("latest_trade_date", "")
    latest["is_latest_trade_date"] = latest["trade_date"].astype(str).eq(str(latest_trade_date))
    latest = latest.merge(pool, on="ticker", how="left", suffixes=("", "_pool"))
    if not daily_basic.empty:
        keep = [
            col for col in ["ticker", "turnover_rate", "volume_ratio", "total_mv", "circ_mv", "pe_ttm", "pb"]
            if col in daily_basic.columns
        ]
        if keep:
            latest = latest.merge(daily_basic[keep].drop_duplicates(subset=["ticker"]), on="ticker", how="left")

    latest["price_vs_ma20_pct"] = (latest["close"] / latest["MA20"] - 1) * 100
    latest["price_vs_ma60_pct"] = (latest["close"] / latest["MA60"] - 1) * 100
    latest["rough_score"] = 42.0
    latest["rough_notes"] = ""
    latest_pre_filter_count = len(latest)

    trend_mask = latest["close"].gt(latest["MA20"]) & latest["MA20"].gt(latest["MA60"])
    latest.loc[trend_mask, "rough_score"] += 35
    latest.loc[trend_mask, "rough_notes"] += "当前价>MA20>MA60；"
    ma20_break = latest["close"].lt(latest["MA20"])
    latest.loc[ma20_break, "rough_score"] -= 12
    latest.loc[ma20_break, "rough_notes"] += "跌破MA20；"
    ma60_break = latest["close"].lt(latest["MA60"])
    latest.loc[ma60_break, "rough_score"] -= 28
    latest.loc[ma60_break, "rough_notes"] += "跌破MA60；"
    hot_mask = latest["twenty_day_return_pct"].gt(60)
    latest.loc[hot_mask, "rough_score"] -= 20
    latest.loc[hot_mask, "rough_notes"] += "20日涨幅>60%，追高风险；"
    moderate = latest["twenty_day_return_pct"].between(3, 35, inclusive="both")
    latest.loc[moderate, "rough_score"] += 8
    latest.loc[moderate, "rough_notes"] += "20日趋势温和；"
    incomplete = latest[["MA20", "MA60"]].isna().any(axis=1)
    latest.loc[incomplete, "rough_score"] -= 25
    latest.loc[incomplete, "rough_notes"] += "MA数据不完整；"
    stale = ~latest["is_latest_trade_date"]
    latest.loc[stale, "rough_score"] -= 25
    latest.loc[stale, "rough_notes"] += "疑似停牌或非最新交易日；"
    if exclude_low_amount and "amount" in latest.columns:
        low_amount = latest["amount"].fillna(0).lt(100000)
        latest.loc[low_amount, "rough_score"] -= 12
        latest.loc[low_amount, "rough_notes"] += "成交额偏低；"
        low_amount_pass_count = int((~low_amount).sum())
    else:
        low_amount_pass_count = len(latest)
    evaluable_mask = ~incomplete & ~stale
    trend_pass_count = int((trend_mask & ~hot_mask & ~incomplete & ~stale).sum())
    evaluable_count = int(evaluable_mask.sum())
    if trend_up_only:
        latest = latest[trend_mask & ~hot_mask & ~incomplete & ~stale].copy()
    else:
        latest = latest[~incomplete & ~stale].copy()
    post_filter_count = len(latest)

    latest["rough_score"] = latest["rough_score"].clip(0, 100)
    latest = latest.sort_values("rough_score", ascending=False).head(int(scan_limit)).copy()
    rough_sample_count = len(latest)
    latest = latest.head(int(refine_limit))

    candidates = []
    for _, row in latest.iterrows():
        ticker = normalize_display_ticker(row.get("ticker"))
        rough_context = {
            "cross_section_available": True,
            "ticker": ticker,
            "name": str(row.get("name") or candidate_name(ticker)),
            "current_price": _num(row.get("close")),
            "data_date": str(row.get("trade_date") or ""),
            "MA20": _num(row.get("MA20")),
            "MA60": _num(row.get("MA60")),
            "twenty_day_return_pct": _num(row.get("twenty_day_return_pct")),
            "price_vs_MA20_pct": _num(row.get("price_vs_ma20_pct")),
            "price_vs_MA60_pct": _num(row.get("price_vs_ma60_pct")),
            "amount": _num(row.get("amount")),
            "turnover_rate": _num(row.get("turnover_rate")),
            "rough_score": _num(row.get("rough_score")),
            "rough_notes": str(row.get("rough_notes") or "").strip("；"),
            "scan_source": "A股主板广域扫描",
        }
        candidates.append(
            {
                "ticker": ticker,
                "name": rough_context["name"],
                "scan_source": "A股主板广域扫描",
                "rough_context": rough_context,
            }
        )

    meta = {
        "pool": pool_meta,
        "cross_section": data_meta,
        "degraded": False,
        "latest_trade_date": latest_trade_date,
        "rough_count": len(candidates),
        "rough_universe_count": len(daily["ticker"].unique()),
        "latest_pre_filter_count": latest_pre_filter_count,
        "evaluable_count": evaluable_count,
        "low_amount_pass_count": low_amount_pass_count,
        "trend_up_pass_count": trend_pass_count,
        "post_filter_count": post_filter_count,
        "rough_sample_count": rough_sample_count,
        "scan_limit": scan_limit,
        "refine_limit": refine_limit,
        "message": "",
    }
    return candidates, sanitize_for_json(meta)


def _date_age_days(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if re.fullmatch(r"\d{8}", text):
            parsed = datetime.datetime.strptime(text, "%Y%m%d").date()
        else:
            parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return max(0, (datetime.datetime.now().date() - parsed).days)
    except Exception:
        return None


def _moneyflow_state(today: float | None, five_day: float | None) -> str:
    if today is None and five_day is None:
        return "资金数据缺失"
    if today is not None and today > 0 and five_day is not None and five_day > 0:
        return "资金趋势改善"
    if today is not None and today > 0 and five_day is not None and five_day < 0:
        return "短线修复，未确认反转"
    if today is not None and today < 0 and five_day is not None and five_day < 0:
        return "资金压力延续"
    return "短线分歧"


def _trend_state(price: float | None, ma20: float | None, ma60: float | None, return_20d: float | None = None) -> str:
    if price is None:
        return "趋势数据缺失"
    if ma60 is not None and price < ma60:
        return "跌破 MA60"
    if ma20 is not None and price < ma20:
        return "跌破 MA20"
    if ma20 is not None and ma60 is not None and price > ma20 > ma60:
        if return_20d is not None and return_20d >= 18:
            return "高位加速"
        return "强趋势"
    if ma20 is not None and price >= ma20:
        return "回踩验证"
    return "趋势待验证"


def _extract_tianyan_sections(packet: dict[str, Any]) -> dict[str, Any]:
    packet = packet or {}
    trading = packet.get("verified_trading_structure_risks") or {}
    hard = packet.get("verified_hard_risks") or {}
    chip = packet.get("verified_chip_risks") or {}
    clues = packet.get("sentiment_and_unverified_clues") or {}
    return {
        "moneyflow": trading.get("moneyflow") or {},
        "dragon_tiger": trading.get("dragon_tiger") or {},
        "margin": trading.get("margin") or {},
        "limit_emotion": trading.get("limit_emotion") or {},
        "chip_radar": chip.get("chip_radar") or {},
        "announcements": hard.get("announcements") or {},
        "free_announcement_radar": hard.get("free_announcement_radar") or {},
        "holder_reduction": hard.get("holder_reduction") or {},
        "pledge": hard.get("pledge") or {},
        "news_digest": clues.get("news_digest") or {},
        "missing_items": packet.get("missing_items") or [],
        "hard_risk_flags": hard.get("risk_flags") or [],
    }


def _section_available(section: dict[str, Any]) -> bool:
    return bool(
        section
        and (
            section.get("available")
            or section.get("rows")
            or section.get("records_available")
            or section.get("boundary_available")
        )
    )


def _extract_pledge_ratio(pledge: dict[str, Any]) -> float | None:
    for row in (pledge or {}).get("rows") or []:
        if not isinstance(row, dict):
            continue
        for key in ["pledge_ratio", "p_total_ratio", "h_total_ratio"]:
            number = _num(row.get(key))
            if number is not None:
                return number
    return None


def _risk_flags_from_sections(sections: dict[str, Any], risk_summary: dict[str, Any]) -> list[str]:
    flags = []
    flags.extend(str(item) for item in (sections.get("hard_risk_flags") or []) if str(item).strip())
    if risk_summary.get("has_reduction_risk"):
        flags.append("控股股东减持")
    pledge_ratio = _num(risk_summary.get("pledge_ratio"))
    if pledge_ratio is not None and pledge_ratio > 15:
        flags.append("质押比例较高")
    five = _num(risk_summary.get("five_day_main_net_yi"))
    if five is not None and five < 0:
        flags.append("近5日资金流出")
    if risk_summary.get("has_announcement_gap"):
        flags.append("公告缺失")
    if risk_summary.get("has_news_gap"):
        flags.append("新闻摘要缺失")
    if not _section_available(sections.get("chip_radar") or {}):
        flags.append("筹码缺失")
    return list(dict.fromkeys(flags))[:8]


def build_current_holding_context(
    current_ticker: str,
    current_name: str,
    current_price: float | None,
    position_profile: dict[str, Any],
    callbacks: dict[str, Callable[..., Any]],
) -> dict[str, Any]:
    display_ticker = normalize_display_ticker(current_ticker)
    app_ticker = to_app_ticker(display_ticker)
    stock_code = _ticker_core(display_ticker)
    name = current_name or candidate_name(display_ticker)

    technical = _safe_call(callbacks, "compute_technical_snapshot", app_ticker) or {}
    price = _num(current_price) or _num((technical or {}).get("latest_close"))
    tianyan = _safe_call(callbacks, "build_tianyan_risk_fact_packet", stock_code, name, price) or {}
    risk_summary = _safe_call(callbacks, "build_local_risk_radar_items", tianyan) or {}
    sections = _extract_tianyan_sections(tianyan if isinstance(tianyan, dict) else {})

    ma20 = _num((technical or {}).get("ma20"))
    ma60 = _num((technical or {}).get("ma60"))
    rsi = _num((technical or {}).get("rsi"))
    macd = _num((technical or {}).get("macd"))
    price_vs_ma20 = _num((technical or {}).get("price_vs_ma20_pct"))
    price_vs_ma60 = _num((technical or {}).get("price_vs_ma60_pct"))
    return_20d = _num((technical or {}).get("return_20d"))
    trend_state = _trend_state(price, ma20, ma60, return_20d)
    today_main = _num(risk_summary.get("today_main_net_yi"))
    five_day_main = _num(risk_summary.get("five_day_main_net_yi"))
    money_state = _moneyflow_state(today_main, five_day_main)
    risks = _risk_flags_from_sections(sections, risk_summary)

    if "跌破 MA60" in trend_state or any("减持" in item for item in risks):
        action_state = "风险升级观察"
    elif "跌破 MA20" in trend_state or any("质押" in item for item in risks):
        action_state = "暂停加仓"
    elif money_state == "资金压力延续":
        action_state = "条件化减仓"
    else:
        action_state = "持有观察"

    if any("减持" in item or "质押" in item for item in risks):
        next_ticket_mode = "防守"
    elif trend_state in {"强趋势", "高位加速"}:
        next_ticket_mode = "接力"
    elif trend_state == "跌破 MA20" and ma60 and price and price >= ma60:
        next_ticket_mode = "低吸"
    else:
        next_ticket_mode = "只观察"

    reduce_triggers = ["跌破 MA20", "跌破筹码中枢", "次日主力重新流出", "新增减持/质押/公告风险"]
    if ma60:
        reduce_triggers.append("跌破 MA60")

    return sanitize_for_json(
        {
            "current_holding_ticker": display_ticker,
            "current_holding_name": name,
            "position_status": position_profile.get("normalized_position_state") or position_profile.get("position_status") or "暂无数据",
            "cost_price": position_profile.get("cost_price"),
            "shares": position_profile.get("holding_units"),
            "current_price": price,
            "floating_profit_pct": position_profile.get("pnl_pct"),
            "floating_profit_amount": position_profile.get("pnl_amount"),
            "holding_ma20": ma20,
            "holding_ma60": ma60,
            "holding_rsi": rsi,
            "holding_macd": macd,
            "holding_price_vs_ma20_pct": price_vs_ma20,
            "holding_price_vs_ma60_pct": price_vs_ma60,
            "holding_20d_return_pct": return_20d,
            "holding_trend_state": trend_state,
            "holding_today_main_net_yi": today_main,
            "holding_five_day_main_net_yi": five_day_main,
            "holding_moneyflow_state": money_state,
            "holding_has_reduction_risk": bool(risk_summary.get("has_reduction_risk")),
            "holding_pledge_ratio": _num(risk_summary.get("pledge_ratio")),
            "holding_has_announcement_gap": bool(risk_summary.get("has_announcement_gap")),
            "holding_has_news_gap": bool(risk_summary.get("has_news_gap")),
            "holding_biggest_risks": risks or ["暂无可验证数据"],
            "holding_action_state": action_state,
            "holding_reduce_triggers": list(dict.fromkeys(reduce_triggers))[:6],
            "next_ticket_mode": next_ticket_mode,
            "data_date": (technical or {}).get("data_asof") or "",
            "raw_data_quality": {
                "technical_missing": (technical or {}).get("missing") or [],
                "risk_missing": sections.get("missing_items") or [],
            },
        }
    )


def build_candidate_context(
    candidate: dict[str, str],
    holding_context: dict[str, Any],
    callbacks: dict[str, Callable[..., Any]],
) -> dict[str, Any]:
    display_ticker = normalize_display_ticker(candidate.get("ticker"))
    app_ticker = to_app_ticker(display_ticker)
    stock_code = _ticker_core(display_ticker)
    name = candidate_name(display_ticker, candidate.get("name") or "")
    rough_context = candidate.get("rough_context") if isinstance(candidate, dict) else {}
    rough_context = rough_context if isinstance(rough_context, dict) else {}

    if rough_context.get("cross_section_available"):
        technical = {
            "latest_close": rough_context.get("current_price"),
            "ma20": rough_context.get("MA20"),
            "ma60": rough_context.get("MA60"),
            "rsi": rough_context.get("RSI"),
            "macd": rough_context.get("MACD"),
            "return_20d": rough_context.get("twenty_day_return_pct"),
            "price_vs_ma20_pct": rough_context.get("price_vs_MA20_pct"),
            "price_vs_ma60_pct": rough_context.get("price_vs_MA60_pct"),
            "data_asof": rough_context.get("data_date"),
            "missing": ["RSI", "MACD"] if not rough_context.get("RSI") or not rough_context.get("MACD") else [],
            "confidence": 70,
            "source": "Tushare daily 横截面",
        }
        price_detail = {"price": rough_context.get("current_price"), "data_date": rough_context.get("data_date")}
    else:
        technical = _safe_call(callbacks, "compute_technical_snapshot", app_ticker) or {}
        price_detail = _safe_call(callbacks, "get_current_price_detail", app_ticker, "A_SHARE") or {}
    current_price = _num((price_detail or {}).get("price")) or _num((technical or {}).get("latest_close"))

    tianyan = _safe_call(callbacks, "build_tianyan_risk_fact_packet", stock_code, name, current_price) or {}
    risk_summary = _safe_call(callbacks, "build_local_risk_radar_items", tianyan) or {}
    sections = _extract_tianyan_sections(tianyan if isinstance(tianyan, dict) else {})

    moneyflow = sections["moneyflow"]
    dragon_tiger = sections["dragon_tiger"]
    margin = sections["margin"]
    limit_emotion = sections["limit_emotion"]
    chip_radar = sections["chip_radar"]
    announcement = sections["free_announcement_radar"] or sections["announcements"]
    news_digest = sections["news_digest"]

    ma20 = _num((technical or {}).get("ma20"))
    ma60 = _num((technical or {}).get("ma60"))
    rsi = _num((technical or {}).get("rsi"))
    macd = _num((technical or {}).get("macd"))
    return_20d = _num((technical or {}).get("return_20d"))
    price_vs_ma20 = _num((technical or {}).get("price_vs_ma20_pct"))
    price_vs_ma60 = _num((technical or {}).get("price_vs_ma60_pct"))
    today_main = _num(moneyflow.get("main_net_yi") if moneyflow.get("main_net_yi") != "" else risk_summary.get("today_main_net_yi"))
    five_day_main = _num(moneyflow.get("five_day_main_net_yi") if moneyflow.get("five_day_main_net_yi") != "" else risk_summary.get("five_day_main_net_yi"))
    pledge_ratio = _extract_pledge_ratio(sections["pledge"])
    if pledge_ratio is None:
        pledge_ratio = _num(risk_summary.get("pledge_ratio"))

    dragon_date = dragon_tiger.get("latest_date") or dragon_tiger.get("trade_date")
    dragon_age = _date_age_days(dragon_date)
    dragon_expired = dragon_age is not None and dragon_age > 5
    limit_up = _num(limit_emotion.get("up_limit"))
    limit_down = _num(limit_emotion.get("down_limit"))
    distance_to_up = _num(limit_emotion.get("distance_to_up_pct"))
    chip_center = _num(chip_radar.get("weight_avg"))
    winner_rate = _num(chip_radar.get("winner_rate"))
    near_limit_up = bool(distance_to_up is not None and distance_to_up <= 3)
    chase_zone = bool(near_limit_up or (chip_center and current_price and current_price >= chip_center * 1.15))

    data_gaps = []
    if not _section_available(moneyflow):
        data_gaps.append("资金")
    if not ma20 or not ma60:
        data_gaps.append("趋势")
    if not _section_available(chip_radar):
        data_gaps.append("筹码")
    if not _section_available(announcement):
        data_gaps.append("公告")
    if not _section_available(news_digest):
        data_gaps.append("news_digest")
    if not _section_available(margin):
        data_gaps.append("融资")
    if not _section_available(dragon_tiger):
        data_gaps.append("龙虎榜")

    context = {
        "ticker": display_ticker,
        "name": name,
        "market_type": "A_SHARE",
        "current_price": current_price,
        "data_date": (technical or {}).get("data_asof") or (price_detail or {}).get("data_date") or "",
        "MA20": ma20,
        "MA60": ma60,
        "RSI": rsi,
        "MACD": macd,
        "twenty_day_return_pct": return_20d,
        "price_vs_MA20_pct": price_vs_ma20,
        "price_vs_MA60_pct": price_vs_ma60,
        "trend_state": _trend_state(current_price, ma20, ma60, return_20d),
        "today_main_net_yi": today_main,
        "five_day_main_net_yi": five_day_main,
        "large_order_net_yi": _num(moneyflow.get("large_net_yi")),
        "medium_order_net_yi": _num(moneyflow.get("medium_net_yi")),
        "small_order_net_yi": _num(moneyflow.get("small_net_yi")),
        "moneyflow_state": _moneyflow_state(today_main, five_day_main),
        "has_reduction_risk": bool(risk_summary.get("has_reduction_risk")),
        "pledge_ratio": pledge_ratio,
        "margin": {
            "available": bool(margin.get("available")),
            "financing_balance_yi": _num(margin.get("financing_balance_yi")),
            "financing_buy_yi": _num(margin.get("financing_buy_yi")),
            "margin_balance_yi": _num(margin.get("margin_balance_yi")),
            "date": margin.get("date") or "",
        },
        "dragon_tiger_date": dragon_date or "",
        "dragon_tiger_expired": bool(dragon_expired),
        "announcement_summary": (announcement or {}).get("summary") or (announcement or {}).get("message") or "暂无可验证数据",
        "news_digest": (news_digest or {}).get("summary") or (news_digest or {}).get("message") or "暂无可验证数据",
        "data_gaps": data_gaps,
        "chip_center": chip_center,
        "winner_rate": winner_rate,
        "limit_up_price": limit_up,
        "limit_down_price": limit_down,
        "near_limit_up": near_limit_up,
        "chase_zone": chase_zone,
        "raw_sections": {
            "moneyflow": moneyflow,
            "margin": margin,
            "dragon_tiger": dragon_tiger,
            "chip_radar": chip_radar,
            "limit_emotion": limit_emotion,
        },
        "scan_source": candidate.get("scan_source") or rough_context.get("scan_source") or "手动输入",
        "rough_context": rough_context,
    }
    context.update(compare_candidate_to_holding(context, holding_context))
    return sanitize_for_json(context)


def compare_candidate_to_holding(candidate_context: dict[str, Any], holding_context: dict[str, Any]) -> dict[str, Any]:
    candidate_trend_gap = _num(candidate_context.get("price_vs_MA20_pct"), 0) or 0
    holding_trend_gap = _num(holding_context.get("holding_price_vs_ma20_pct"), 0) or 0
    candidate_money = _num(candidate_context.get("five_day_main_net_yi"), 0) or 0
    holding_money = _num(holding_context.get("holding_five_day_main_net_yi"), 0) or 0
    candidate_risk_count = len(candidate_context.get("data_gaps") or [])
    holding_risk_count = len(holding_context.get("holding_biggest_risks") or [])
    candidate_position = _num(candidate_context.get("price_vs_MA20_pct"), 0) or 0
    holding_position = _num(holding_context.get("holding_price_vs_ma20_pct"), 0) or 0

    trend_advantage = "候选更强" if candidate_trend_gap > holding_trend_gap + 2 else ("持仓更强" if holding_trend_gap > candidate_trend_gap + 2 else "接近")
    money_advantage = "候选更强" if candidate_money > holding_money else ("持仓更强" if holding_money > candidate_money else "接近")
    risk_advantage = "候选更安全" if candidate_risk_count < holding_risk_count else ("持仓风险更低" if holding_risk_count < candidate_risk_count else "接近")
    position_advantage = "候选位置更低" if candidate_position < holding_position - 5 else ("持仓位置更低" if holding_position < candidate_position - 5 else "接近")

    holding_action = str(holding_context.get("holding_action_state") or "")
    if "风险" in holding_action or "减仓" in holding_action:
        relation = "替代观察" if trend_advantage in {"候选更强", "接近"} else "防守观察"
    elif trend_advantage == "候选更强" and money_advantage == "候选更强":
        relation = "接力观察"
    elif risk_advantage == "候选更安全" and position_advantage == "候选位置更低":
        relation = "防守观察"
    else:
        relation = "暂不替代"

    return {
        "candidate_vs_holding_trend_advantage": trend_advantage,
        "candidate_vs_holding_moneyflow_advantage": money_advantage,
        "candidate_vs_holding_risk_advantage": risk_advantage,
        "candidate_vs_holding_position_advantage": position_advantage,
        "candidate_switch_relation": relation,
    }


def score_candidate(candidate_context: dict[str, Any], holding_context: dict[str, Any]) -> dict[str, Any]:
    price = _num(candidate_context.get("current_price"))
    ma20 = _num(candidate_context.get("MA20"))
    ma60 = _num(candidate_context.get("MA60"))
    rsi = _num(candidate_context.get("RSI"))
    return_20d = _num(candidate_context.get("twenty_day_return_pct"))
    today_main = _num(candidate_context.get("today_main_net_yi"))
    five_day_main = _num(candidate_context.get("five_day_main_net_yi"))
    pledge_ratio = _num(candidate_context.get("pledge_ratio"))
    chip_center = _num(candidate_context.get("chip_center"))
    winner_rate = _num(candidate_context.get("winner_rate"))
    data_gaps = list(candidate_context.get("data_gaps") or [])

    trend = 45
    trend_notes = []
    if price and ma20 and ma60 and price > ma20 > ma60:
        trend += 35
        trend_notes.append("当前价 > MA20 > MA60")
    elif price and ma20 and price < ma20:
        trend -= 18
        trend_notes.append("跌破 MA20")
    if price and ma60 and price < ma60:
        trend -= 28
        trend_notes.append("跌破 MA60")
    if return_20d is not None and return_20d > 25:
        trend -= 6
        trend_notes.append("20日涨幅偏快")
    if rsi is not None and rsi > 78:
        trend -= 8
        trend_notes.append("RSI 偏热")
    if not ma20 or not ma60:
        trend = min(trend, 42)
        trend_notes.append("MA20/MA60 缺口")

    money = 45
    money_wait = False
    money_notes = []
    if today_main is not None and today_main > 0:
        money += 15
        money_notes.append("今日主力净流入")
    if five_day_main is not None and five_day_main > 0:
        money += 20
        money_notes.append("近5日主力净流入")
    if today_main is not None and five_day_main is not None and today_main > 0 and five_day_main < 0:
        money_wait = True
        money -= 4
        money_notes.append("今日回流但5日仍流出")
    if today_main is not None and five_day_main is not None and today_main < 0 and five_day_main < 0:
        money -= 26
        money_notes.append("今日与近5日都流出")
    if today_main is None and five_day_main is None:
        money = 40
        money_notes.append("资金数据缺失")

    risk = 82
    risk_notes = []
    if candidate_context.get("has_reduction_risk"):
        risk -= 22
        risk_notes.append("控股股东减持")
    if pledge_ratio is not None and pledge_ratio > 15:
        risk -= 16
        risk_notes.append("质押比例 >15%")
    financing_balance = _num(((candidate_context.get("margin") or {}).get("financing_balance_yi")))
    if financing_balance is not None and financing_balance >= 20 and "跌破" in str(candidate_context.get("trend_state")):
        risk -= 10
        risk_notes.append("融资余额高且价格转弱")
    if candidate_context.get("dragon_tiger_expired"):
        risk -= 4
        risk_notes.append("龙虎榜超过5个交易日，仅作历史参考")
    if "公告" in data_gaps:
        risk -= 5
        risk_notes.append("公告缺口")
    if "news_digest" in data_gaps:
        risk -= 5
        risk_notes.append("news_digest 缺口")

    position = 48
    position_notes = []
    if price and chip_center:
        gap = (price / chip_center - 1) * 100
        if 0 <= gap <= 12:
            position += 24
            position_notes.append("高于筹码中枢但未明显过热")
        elif gap < 0:
            position -= 18
            position_notes.append("跌破筹码中枢")
        elif gap > 18:
            position -= 10
            position_notes.append("高于筹码中枢较多")
    else:
        position = min(position, 42)
        position_notes.append("筹码中枢缺失")
    if candidate_context.get("near_limit_up") or candidate_context.get("chase_zone"):
        position -= 18
        position_notes.append("离涨停太近或处于追高区")
    if winner_rate is not None and winner_rate > 75:
        position -= 6
        position_notes.append("获利盘比例偏高")

    completeness = 100 - len(data_gaps) * 10
    if not data_gaps:
        completeness += 5
    completeness = _clip_score(completeness)

    compare = 50
    relation = candidate_context.get("candidate_switch_relation") or "暂不替代"
    if relation == "接力观察":
        compare += 18
    elif relation in {"替代观察", "防守观察"}:
        compare += 10
    elif relation == "暂不替代":
        compare -= 6

    total = (
        _clip_score(trend) * 0.25
        + _clip_score(money) * 0.22
        + _clip_score(risk) * 0.22
        + _clip_score(position) * 0.16
        + completeness * 0.10
        + _clip_score(compare) * 0.05
    )
    total = _clip_score(total)

    if _clip_score(risk) < 35:
        battle_state = "风险过高"
    elif total >= 72 and _clip_score(risk) >= 58 and _clip_score(trend) >= 62 and _clip_score(money) >= 58:
        battle_state = "可准备"
    elif total >= 58 or money_wait:
        battle_state = "等验证"
    elif total >= 44:
        battle_state = "只观察"
    else:
        battle_state = "暂不纳入"

    triggers = [
        "连续资金回流",
        "站稳 MA20 / 筹码中枢",
        "公告/news_digest 无新增负面",
    ]
    if relation in {"接力观察", "替代观察", "防守观察"}:
        triggers.append("当前持仓票出现减仓触发后再考虑切换")
    invalidations = [
        "跌破 MA20",
        "跌破 MA60",
        "主力资金重新流出",
        "新增减持/质押/公告风险",
        "题材退潮",
    ]
    if chip_center:
        invalidations.append("跌破筹码中枢")

    return sanitize_for_json(
        {
            "ticker": candidate_context.get("ticker"),
            "name": candidate_context.get("name"),
            "battle_state": battle_state,
            "total_score": total,
            "trend_score": _clip_score(trend),
            "money_score": _clip_score(money),
            "risk_score": _clip_score(risk),
            "position_score": _clip_score(position),
            "information_score": completeness,
            "holding_compare_score": _clip_score(compare),
            "switch_relation": relation,
            "trigger_conditions": list(dict.fromkeys(triggers))[:5],
            "invalid_conditions": list(dict.fromkeys(invalidations))[:6],
            "score_notes": {
                "trend": trend_notes,
                "money": money_notes,
                "risk": risk_notes,
                "position": position_notes,
                "data_gaps": data_gaps,
            },
        }
    )


def build_rule_radar(
    candidates: list[dict[str, str]],
    holding_context: dict[str, Any],
    callbacks: dict[str, Callable[..., Any]],
    progress_callback: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    deduped = _dedupe_candidates(candidates)
    total = len(deduped)
    for index, candidate in enumerate(deduped, start=1):
        if callable(progress_callback):
            progress_callback(index, total, candidate)
        try:
            context = build_candidate_context(candidate, holding_context, callbacks)
            score = score_candidate(context, holding_context)
            rows.append(
                {
                    "candidate": candidate,
                    "candidate_context": context,
                    "score": score,
                    "scan_source": candidate.get("scan_source") or context.get("scan_source") or "手动输入",
                    "error": "",
                }
            )
        except Exception as exc:
            ticker = normalize_display_ticker(candidate.get("ticker"))
            rows.append(
                {
                    "candidate": {"ticker": ticker, "name": candidate_name(ticker, candidate.get("name") or "")},
                    "candidate_context": {
                        "ticker": ticker,
                        "name": candidate_name(ticker, candidate.get("name") or ""),
                        "data_gaps": ["候选数据构造失败"],
                    },
                    "score": {
                        "ticker": ticker,
                        "name": candidate_name(ticker, candidate.get("name") or ""),
                        "battle_state": "只观察",
                        "total_score": 0,
                        "trend_score": 0,
                        "money_score": 0,
                        "risk_score": 0,
                        "position_score": 0,
                        "information_score": 0,
                        "holding_compare_score": 0,
                        "switch_relation": "暂不替代",
                        "trigger_conditions": ["补齐资金数据", "补齐趋势数据", "补齐公告/news_digest"],
                        "invalid_conditions": ["数据缺口无法修复", "新增减持/质押/公告风险", "主力资金继续流出"],
                        "score_notes": {"data_gaps": ["候选数据构造失败"]},
                    },
                    "scan_source": candidate.get("scan_source") or "手动输入",
                    "error": str(exc),
                }
            )
    return sorted(rows, key=lambda item: _num((item.get("score") or {}).get("total_score"), 0) or 0, reverse=True)


def _radar_dataframe(rule_rows: list[dict[str, Any]]) -> pd.DataFrame:
    table_rows = []
    for rank, item in enumerate(rule_rows, start=1):
        score = item.get("score") or {}
        candidate = item.get("candidate") or {}
        context = item.get("candidate_context") or {}
        gaps = context.get("data_gaps") or (score.get("score_notes") or {}).get("data_gaps") or []
        table_rows.append(
            {
                "排名": rank,
                "股票": f"{candidate.get('ticker', '')} {candidate.get('name', '')}".strip(),
                "搞不搞": score.get("battle_state") or "只观察",
                "综合分": score.get("total_score", 0),
                "趋势": score.get("trend_score", 0),
                "资金": score.get("money_score", 0),
                "风险": score.get("risk_score", 0),
                "位置": score.get("position_score", 0),
                "信息完整度": score.get("information_score", 0),
                "与当前持仓关系": score.get("switch_relation") or "暂不替代",
                "触发条件": "；".join(score.get("trigger_conditions") or []),
                "失效条件": "；".join(score.get("invalid_conditions") or []),
                "数据缺口": "；".join(str(item) for item in gaps) if gaps else "无",
                "扫描来源": item.get("scan_source") or context.get("scan_source") or "手动输入",
            }
        )
    return pd.DataFrame(table_rows)


def parse_supabase_time(value: Any) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def load_cached_research(
    supabase: Any,
    candidate_ticker: str,
    current_holding_ticker: str,
    cache_hours: int = 24,
) -> dict[str, Any] | None:
    if not supabase:
        return None
    candidate_display = normalize_display_ticker(candidate_ticker)
    holding_display = normalize_display_ticker(current_holding_ticker)
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=cache_hours)
    ticker_terms = list(dict.fromkeys([candidate_display, to_app_ticker(candidate_display)]))
    try:
        query = (
            supabase.table("stock_reports")
            .select("report_content, created_at, ticker")
            .eq("report_type", NEXT_TICKET_REPORT_TYPE)
            .gte("created_at", cutoff.isoformat())
            .order("created_at", desc=True)
            .limit(20)
        )
        if ticker_terms:
            query = query.in_("ticker", ticker_terms)
        rows = query.execute().data or []
    except Exception:
        return None

    for row in rows:
        payload = _safe_json_loads(row.get("report_content"))
        if not isinstance(payload, dict):
            continue
        if normalize_display_ticker(payload.get("candidate_ticker")) != candidate_display:
            continue
        if normalize_display_ticker(payload.get("current_holding_ticker")) != holding_display:
            continue
        generated_at = payload.get("generated_at") or row.get("created_at") or ""
        return {
            "payload": payload,
            "generated_at": generated_at,
            "created_at": row.get("created_at") or generated_at,
        }
    return None


def save_research_report(
    supabase: Any,
    candidate_ticker: str,
    market_type: str,
    payload: dict[str, Any],
) -> bool:
    if not supabase:
        return False
    try:
        supabase.table("stock_reports").insert(
            {
                "ticker": normalize_display_ticker(candidate_ticker),
                "market_type": market_type or "A_SHARE",
                "report_type": NEXT_TICKET_REPORT_TYPE,
                "report_content": safe_json_dumps(payload),
            }
        ).execute()
        return True
    except Exception as exc:
        st.warning(f"深度研究缓存写入失败：{exc}")
        return False


def sanitize_deepseek_result(value: Any) -> tuple[Any, list[str]]:
    found = []

    def clean_text(text: str) -> str:
        cleaned = str(text)
        for word in FORBIDDEN_OUTPUT_WORDS:
            if word in cleaned:
                found.append(word)
                cleaned = cleaned.replace(word, "【已屏蔽绝对化建议】")
        return cleaned

    def walk(item: Any) -> Any:
        if isinstance(item, str):
            return clean_text(item)
        if isinstance(item, dict):
            return {key: walk(val) for key, val in item.items()}
        if isinstance(item, list):
            return [walk(val) for val in item]
        return item

    return walk(value), list(dict.fromkeys(found))


def _parse_deepseek_output(raw_output: str) -> dict[str, Any]:
    raw = str(raw_output or "").strip()
    if not raw:
        return {"raw_output": "", "parse_status": "empty"}
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S | re.I)
    candidate = fenced.group(1).strip() if fenced else raw
    parsed = _safe_json_loads(candidate)
    if isinstance(parsed, dict):
        parsed["parse_status"] = "json"
        return parsed
    return {"raw_output": raw, "parse_status": "markdown"}


def build_deepseek_prompt(
    current_holding_context: dict[str, Any],
    candidate_context: dict[str, Any],
    rule_score_snapshot: dict[str, Any],
) -> str:
    facts = {
        "current_holding_context": current_holding_context,
        "candidate_context": candidate_context,
        "candidate_vs_holding": {
            "trend_advantage": candidate_context.get("candidate_vs_holding_trend_advantage"),
            "moneyflow_advantage": candidate_context.get("candidate_vs_holding_moneyflow_advantage"),
            "risk_advantage": candidate_context.get("candidate_vs_holding_risk_advantage"),
            "position_advantage": candidate_context.get("candidate_vs_holding_position_advantage"),
            "switch_relation": candidate_context.get("candidate_switch_relation"),
        },
        "rule_score_snapshot": rule_score_snapshot,
        "data_gaps": candidate_context.get("data_gaps") or [],
        "generated_at": _now_iso(),
        "data_date": candidate_context.get("data_date") or current_holding_context.get("data_date") or "",
    }
    return f"""
你是一个克制的 A 股候选票作战准备研究员，只能基于输入的结构化事实做候选分层。

核心边界：
1. 这不是荐股，不构成买卖建议。
2. 禁止输出这些词或同义动作：{", ".join(FORBIDDEN_OUTPUT_WORDS)}。
3. 只能使用这些作战状态：{", ".join(ALLOWED_BATTLE_STATES)}。
4. 与当前持仓票关系只能使用：{", ".join(ALLOWED_SWITCH_RELATIONS)}。
5. 不能编造事实；缺少事实必须写入数据缺口。
6. 一句话结论只能判断“是否值得进入作战准备”，不得写交易指令。

请严格输出 JSON，不要输出额外解释。JSON schema:
{{
  "battle_state": "可准备/等验证/只观察/暂不纳入/风险过高",
  "total_score": 0,
  "score_breakdown": {{
    "trend": 0,
    "money": 0,
    "risk": 0,
    "position": 0,
    "information": 0,
    "holding_compare": 0
  }},
  "one_sentence_conclusion": "",
  "entry_triggers": ["至少3条"],
  "invalid_conditions": ["至少3条"],
  "biggest_risks": ["具体风险"],
  "data_gaps": ["公告/新闻/筹码/融资/龙虎榜等缺失项"],
  "relation_to_current_holding": "接力观察/替代观察/防守观察/暂不替代",
  "why_not_direct_action": "一句话说明需要等待验证或不构成交易建议"
}}

结构化事实如下：
{safe_json_dumps(facts, indent=2)}
"""


def run_deep_research_for_candidate(
    supabase: Any,
    row: dict[str, Any],
    holding_context: dict[str, Any],
    callbacks: dict[str, Callable[..., Any]],
    use_cache: bool,
    force_refresh: bool,
) -> dict[str, Any]:
    candidate_context = row.get("candidate_context") or {}
    score = row.get("score") or {}
    candidate_ticker = normalize_display_ticker(candidate_context.get("ticker") or score.get("ticker"))
    current_holding_ticker = normalize_display_ticker(holding_context.get("current_holding_ticker"))

    cached = load_cached_research(supabase, candidate_ticker, current_holding_ticker) if use_cache or not force_refresh else None
    if cached and not force_refresh:
        payload = cached["payload"]
        result = payload.get("deepseek_result") or {}
        sanitized, found = sanitize_deepseek_result(result)
        payload["deepseek_result"] = sanitized
        return {
            "ticker": candidate_ticker,
            "name": candidate_context.get("name") or score.get("name") or "",
            "status": "cached",
            "cached": True,
            "generated_at": cached.get("generated_at") or payload.get("generated_at") or "",
            "payload": payload,
            "result": sanitized,
            "forbidden_words": found,
            "error": "",
        }

    prompt = build_deepseek_prompt(holding_context, candidate_context, score)
    call_deepseek = callbacks.get("call_deepseek_non_stream")
    if not callable(call_deepseek):
        return {
            "ticker": candidate_ticker,
            "name": candidate_context.get("name") or "",
            "status": "failed",
            "cached": False,
            "generated_at": "",
            "payload": {},
            "result": {},
            "forbidden_words": [],
            "error": "DeepSeek 调用函数不可用",
        }

    raw = call_deepseek(
        prompt,
        system_role="你是克制的A股候选票作战准备研究员，只输出结构化 JSON，不给买卖建议。",
        max_tokens=2600,
    )
    if not raw:
        return {
            "ticker": candidate_ticker,
            "name": candidate_context.get("name") or "",
            "status": "failed",
            "cached": False,
            "generated_at": "",
            "payload": {},
            "result": {},
            "forbidden_words": [],
            "error": "DeepSeek 未返回内容",
        }

    parsed = _parse_deepseek_output(raw)
    sanitized, found = sanitize_deepseek_result(parsed)
    generated_at = _now_iso()
    payload = sanitize_for_json(
        {
            "current_holding_ticker": current_holding_ticker,
            "candidate_ticker": candidate_ticker,
            "generated_at": generated_at,
            "source": NEXT_TICKET_SOURCE,
            "version": NEXT_TICKET_VERSION,
            "deepseek_result": sanitized,
            "rule_score_snapshot": score,
            "current_holding_context": holding_context,
            "candidate_context": candidate_context,
        }
    )
    saved = save_research_report(supabase, candidate_ticker, candidate_context.get("market_type") or "A_SHARE", payload)
    return {
        "ticker": candidate_ticker,
        "name": candidate_context.get("name") or score.get("name") or "",
        "status": "success",
        "cached": False,
        "saved": saved,
        "generated_at": generated_at,
        "payload": payload,
        "result": sanitized,
        "forbidden_words": found,
        "error": "",
    }


def _render_result_expander(item: dict[str, Any]) -> None:
    ticker = item.get("ticker") or ""
    name = item.get("name") or ""
    cached = bool(item.get("cached"))
    generated_at = item.get("generated_at") or ""
    result = item.get("result") or {}
    label_prefix = "缓存" if cached else ("失败" if item.get("error") else "新生成")
    with st.expander(f"{ticker} {name}｜{label_prefix}", expanded=not cached):
        if item.get("error"):
            st.error(item.get("error"))
            return
        if cached:
            st.warning(f"这是缓存研究结果，生成时间为：{generated_at}；盘中数据变化后请谨慎使用。")
        if item.get("forbidden_words"):
            st.warning("DeepSeek 输出含绝对化措辞，渲染前已屏蔽：" + "、".join(item["forbidden_words"]))
        if render_next_ticket_research_summary:
            render_next_ticket_research_summary(result, generated_at=generated_at, cached=cached)
        else:
            st.json(result)
        with st.expander("查看缓存 JSON / 原始结构", expanded=False):
            st.json(item.get("payload") or result)


def render_next_ticket_radar(
    *,
    supabase: Any,
    current_ticker: str,
    current_name: str,
    current_price: float | None,
    position_profile: dict[str, Any],
    callbacks: dict[str, Callable[..., Any]],
) -> None:
    st.markdown("### 🧭 下一票作战雷达")
    st.caption("不是荐股，只判断候选票是否值得进入作战准备。")
    st.warning("该模块不是荐股，不构成买卖建议；广域扫描仅用于发现候选观察对象。加仓需要验证，减仓需要条件触发。")

    if RADAR_SCAN_STATE_KEY not in st.session_state:
        st.session_state[RADAR_SCAN_STATE_KEY] = {}
    if DEEP_RESEARCH_STATE_KEY not in st.session_state:
        st.session_state[DEEP_RESEARCH_STATE_KEY] = {}

    holding_context = build_current_holding_context(
        current_ticker=current_ticker,
        current_name=current_name,
        current_price=current_price,
        position_profile=position_profile or {},
        callbacks=callbacks,
    )
    if render_next_ticket_holding_card:
        render_next_ticket_holding_card(holding_context)
    else:
        st.json(holding_context)

    st.markdown("#### 候选池输入")
    if "next_ticket_manual_candidates" not in st.session_state:
        st.session_state["next_ticket_manual_candidates"] = _candidate_text(DEFAULT_CANDIDATES)

    source_options = ["手动输入候选", "科技股样本池", "持续调查池", "A股主板广域扫描", "混合扫描"]
    source_mode = st.selectbox("候选池来源选择器", source_options, index=3, key="next_ticket_source_mode")

    quick1, quick2, quick3 = st.columns(3)
    with quick1:
        if st.button("填入科技股样本池", key="next_ticket_use_tech_pool", width="stretch"):
            st.session_state["next_ticket_manual_candidates"] = _candidate_text(TECH_SAMPLE_POOL)
            st.rerun()
    with quick2:
        watchlist_rows, watchlist_error = load_watchlist_candidates(callbacks)
        if st.button("填入持续调查池", key="next_ticket_use_watchlist", width="stretch"):
            if watchlist_rows:
                st.session_state["next_ticket_manual_candidates"] = _candidate_text(watchlist_rows)
                st.rerun()
            else:
                st.warning(watchlist_error or "持续调查池为空。")
    with quick3:
        include_focus = st.checkbox("加入今日关注池结构化候选", value=False, key="next_ticket_include_focus")

    manual_text = st.text_area(
        "手动输入候选股票，逗号分隔",
        key="next_ticket_manual_candidates",
        height=82,
        help="规则雷达和广域扫描都不调用 DeepSeek。深度研究按钮才会调用。",
    )

    st.markdown("#### A股主板广域扫描参数")
    p1, p2, p3 = st.columns(3)
    with p1:
        scan_limit = st.radio(
            "扫描数量上限",
            [50, 100, 200, 300],
            index=1,
            horizontal=True,
            key="next_ticket_scan_limit",
            help="这是粗筛样本上限，不代表只读取这些股票；系统会先做 A股主板横截面过滤，再截取 Top 样本进入精筛。",
        )
    with p2:
        refine_limit = st.radio("精筛数量", [20, 30, 50], index=1, horizontal=True, key="next_ticket_refine_limit")
    with p3:
        display_limit = st.radio("规则雷达展示", [10, 20], index=1, horizontal=True, key="next_ticket_display_limit")
    st.caption("扫描数量上限是粗筛样本上限，不代表只读取对应数量股票；系统会先做 A股主板横截面过滤，再截取 Top 样本进入精筛。")

    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        exclude_st = st.checkbox("排除 ST / 退市整理", value=True, key="next_ticket_exclude_st")
    with f2:
        exclude_chinext = st.checkbox("排除创业板 300", value=True, key="next_ticket_exclude_chinext")
    with f3:
        exclude_star = st.checkbox("排除科创板 688", value=True, key="next_ticket_exclude_star")
    with f4:
        exclude_low_amount = st.checkbox("排除低成交额", value=True, key="next_ticket_exclude_low_amount")
    with f5:
        trend_up_only = st.checkbox("只看趋势向上", value=True, key="next_ticket_trend_up_only")
    exclude_bj = st.checkbox("排除北交所", value=True, key="next_ticket_exclude_bj")

    scan_params = sanitize_for_json(
        {
            "source_mode": source_mode,
            "manual_text": manual_text,
            "include_focus": include_focus,
            "scan_limit": scan_limit,
            "refine_limit": refine_limit,
            "display_limit": display_limit,
            "exclude_st": exclude_st,
            "exclude_chinext": exclude_chinext,
            "exclude_star": exclude_star,
            "exclude_bj": exclude_bj,
            "exclude_low_amount": exclude_low_amount,
            "trend_up_only": trend_up_only,
            "current_holding_ticker": holding_context.get("current_holding_ticker"),
            "current_price": holding_context.get("current_price"),
            "cost_price": holding_context.get("cost_price"),
            "shares": holding_context.get("shares"),
        }
    )
    params_hash = _scan_params_hash(scan_params)

    def gather_non_broad_candidates() -> tuple[list[dict[str, Any]], list[str]]:
        rows: list[dict[str, Any]] = []
        notes = []
        if source_mode in {"手动输入候选", "混合扫描"}:
            manual_rows = parse_candidate_text(manual_text)
            for item in manual_rows:
                item["scan_source"] = "手动输入"
            rows.extend(manual_rows)
            notes.append(f"手动输入 {len(manual_rows)} 只")
        if source_mode in {"科技股样本池", "混合扫描"}:
            tech_rows = [{**item, "scan_source": "科技股样本池"} for item in TECH_SAMPLE_POOL]
            rows.extend(tech_rows)
            notes.append(f"科技股样本池 {len(tech_rows)} 只")
        if source_mode in {"持续调查池", "混合扫描"}:
            wl_rows, wl_error = load_watchlist_candidates(callbacks)
            for item in wl_rows:
                item["scan_source"] = "持续调查池"
            rows.extend(wl_rows)
            notes.append(f"持续调查池 {len(wl_rows)} 只")
            if not wl_rows and wl_error:
                st.info(wl_error)
        if include_focus:
            focus_rows, focus_error = load_today_focus_structured_candidates(supabase)
            for item in focus_rows:
                item["scan_source"] = "今日关注池结构化候选"
            rows.extend(focus_rows)
            notes.append(f"今日关注池结构化候选 {len(focus_rows)} 只")
            if not focus_rows and focus_error:
                st.info(focus_error)
        return _dedupe_candidates(rows), notes

    start_label = "开始广域扫描" if source_mode in {"A股主板广域扫描", "混合扫描"} else "生成规则雷达"
    b1, b2 = st.columns(2)
    with b1:
        start_scan = st.button(start_label, type="primary", key="next_ticket_start_scan", width="stretch")
    with b2:
        rescan = st.button("重新扫描", key="next_ticket_rescan", width="stretch")

    scan_state = st.session_state.get(RADAR_SCAN_STATE_KEY) or {}
    should_scan = bool(start_scan or rescan)
    if should_scan:
        status_box = st.status("正在进行 A股主板广域扫描……", expanded=False)
        progress = st.progress(0)
        source_notes = []
        candidates: list[dict[str, Any]] = []
        scan_meta: dict[str, Any] = {}

        try:
            if source_mode in {"A股主板广域扫描", "混合扫描"}:
                status_box.update(label="正在进行 A股主板横截面粗筛……", state="running")
                broad_candidates, broad_meta = build_cross_section_rough_candidates(
                    callbacks,
                    scan_limit=int(scan_limit),
                    refine_limit=int(refine_limit),
                    exclude_st=bool(exclude_st),
                    exclude_chinext=bool(exclude_chinext),
                    exclude_star=bool(exclude_star),
                    exclude_bj=bool(exclude_bj),
                    exclude_low_amount=bool(exclude_low_amount),
                    trend_up_only=bool(trend_up_only),
                )
                candidates.extend(broad_candidates)
                scan_meta["broad_scan"] = broad_meta
                source_notes.append(f"A股主板广域扫描粗筛 {broad_meta.get('rough_count', len(broad_candidates))} 只")
                pool_meta = broad_meta.get("pool") or {}
                cross_meta = broad_meta.get("cross_section") or {}
                status_box.write(f"Tushare 股票基础池：{pool_meta.get('raw_count') or 0} 只")
                status_box.write(f"只保留上市状态 L 后：{pool_meta.get('listed_count') or pool_meta.get('raw_count') or 0} 只")
                status_box.write(f"排除 ST / 退市整理后：{pool_meta.get('after_st_exclusion_count') or pool_meta.get('listed_count') or 0} 只")
                status_box.write(f"排除创业板 / 科创板 / 北交所后：{pool_meta.get('after_board_exclusion_count') or 0} 只")
                status_box.write(f"A股主板候选池：{pool_meta.get('filtered_count') or 0} 只")
                status_box.write(f"横截面 daily 行数：{cross_meta.get('daily_rows') or 0}，取数模式：{cross_meta.get('daily_fetch_mode') or '未知'}")
                status_box.write(f"横截面可评估样本：{broad_meta.get('evaluable_count') or 0} 只")
                status_box.write(f"排除低成交额阈值后可优先入选：{broad_meta.get('low_amount_pass_count') or 0} 只")
                status_box.write(f"只看趋势向上后：{broad_meta.get('trend_up_pass_count') or 0} 只")
                status_box.write(f"过滤条件后进入粗筛排序：{broad_meta.get('post_filter_count') or 0} 只")
                status_box.write(f"本次粗筛样本上限：Top {scan_limit}；实际粗筛样本：{broad_meta.get('rough_sample_count') or len(broad_candidates)} 只")
                status_box.write(f"精筛数量：Top {refine_limit}；最终展示数量：Top {display_limit}")
                if broad_meta.get("degraded"):
                    status_box.write(f"广域扫描降级：{broad_meta.get('message') or '已降级为小样本扫描'}")
                else:
                    status_box.update(
                        label=(
                            f"第一层横截面粗筛已完成：从 A股主板池中筛出 Top {scan_limit}；"
                            f"准备精筛 Top {refine_limit}；最终展示规则雷达 Top {display_limit}。"
                        ),
                        state="running",
                    )
            extra_candidates, extra_notes = gather_non_broad_candidates()
            candidates.extend(extra_candidates)
            source_notes.extend(extra_notes)
            candidates = _dedupe_candidates(candidates)

            if not candidates:
                status_box.update(label="候选池为空", state="error")
                st.warning("候选池为空，无法生成规则雷达。")
                return

            status_box.update(
                label=(
                    f"第二层正在精筛 Top {refine_limit}：0/{len(candidates)}；"
                    f"最终将展示规则雷达 Top {display_limit}。"
                ),
                state="running",
            )

            def progress_callback(index: int, total: int, candidate: dict[str, Any]) -> None:
                ticker = candidate.get("ticker") or ""
                name = candidate.get("name") or ""
                status_box.update(
                    label=(
                        f"第二层正在精筛 Top {refine_limit}：{index}/{total}，当前 {ticker} {name}；"
                        f"最终将展示规则雷达 Top {display_limit}。"
                    ),
                    state="running",
                )
                progress.progress(index / max(total, 1))

            rule_rows = build_rule_radar(candidates, holding_context, callbacks, progress_callback=progress_callback)
            status_box.update(label=f"正在生成规则雷达 Top {display_limit}……", state="running")
            success_count = sum(1 for row in rule_rows if not row.get("error"))
            failed_count = len(rule_rows) - success_count
            status_box.write(f"成功/失败数量：成功 {success_count} 只，失败 {failed_count} 只。")
            status_box.update(label=f"✅ A股主板广域扫描完成：展示规则雷达 Top {display_limit}", state="complete", expanded=False)
            scan_state = {
                "params_hash": params_hash,
                "params": scan_params,
                "source_mode": source_mode,
                "source_notes": source_notes,
                "rule_rows": sanitize_for_json(rule_rows),
                "scan_meta": scan_meta,
                "generated_at": _now_iso(),
            }
            st.session_state[RADAR_SCAN_STATE_KEY] = scan_state
            st.session_state[DEEP_RESEARCH_STATE_KEY] = {}
        except Exception as exc:
            status_box.update(label="规则雷达扫描失败", state="error")
            st.error(f"扫描失败：{exc}")
            return

    scan_state = st.session_state.get(RADAR_SCAN_STATE_KEY) or {}
    rule_rows = scan_state.get("rule_rows") or []
    if not rule_rows:
        st.info("尚未扫描。A股主板广域扫描不会在页面加载时自动执行，请点击“开始广域扫描”。")
        return
    if scan_state.get("params_hash") != params_hash:
        st.warning("扫描参数或当前持仓标尺已变化。当前展示的是上一次扫描结果；请点击“重新扫描”刷新规则雷达。")

    st.caption(
        f"扫描来源：{scan_state.get('source_mode') or source_mode} ｜ "
        f"生成时间：{scan_state.get('generated_at') or '暂无'} ｜ "
        + "；".join(scan_state.get("source_notes") or [])
    )
    scan_meta = scan_state.get("scan_meta") or {}
    if (scan_meta.get("broad_scan") or {}).get("degraded"):
        st.warning((scan_meta.get("broad_scan") or {}).get("message") or "广域扫描已降级为小样本扫描。")
    with st.expander("广域扫描横截面信息", expanded=False):
        st.json(scan_meta or {"message": "非广域扫描或暂无横截面元数据"})

    st.markdown("#### 规则雷达表")
    st.dataframe(_radar_dataframe(rule_rows[: int(display_limit)]), use_container_width=True, hide_index=True)

    with st.expander("规则评分口径", expanded=False):
        st.markdown(
            """
- 趋势：当前价 > MA20 > MA60 加分；跌破 MA20 扣分；跌破 MA60 大扣分。
- 资金：今日与近5日主力净流入加分；今日流入但5日流出标记等验证；今日和5日都流出扣分。
- 风险：减持、质押比例高、融资余额高且价格转弱、过期龙虎榜、公告/news_digest 缺口都会降权。
- 位置：高于筹码中枢但不过热加分；跌破筹码中枢扣分；离涨停太近扣分。
- 信息完整度：资金、趋势、筹码、风险、公告/news_digest 越完整，置信度越高。
"""
        )

    st.markdown("#### 深度研究控制区")
    ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 1.2])
    with ctrl1:
        top_n = st.radio("Top N 选择", [3, 5, 8], index=1, horizontal=True, key="next_ticket_top_n")
    with ctrl2:
        use_cache = st.checkbox("使用 24 小时缓存", value=True, key="next_ticket_use_cache")
    with ctrl3:
        force_refresh = st.checkbox("强制重新研究", value=False, key="next_ticket_force_refresh")

    if not use_cache and not force_refresh:
        st.caption("为避免重复消耗 token，若发现 24 小时内缓存且未勾选强制重新研究，本模块仍会优先展示缓存。")

    selected_rows = (st.session_state.get(RADAR_SCAN_STATE_KEY) or {}).get("rule_rows", [])[: int(top_n)]
    run_deep = st.button("🧠 深度研究 Top 候选", type="primary", key="next_ticket_run_deep", width="stretch")
    if not run_deep:
        st.caption("未点击深度研究按钮时，不会调用 DeepSeek，也不会写入 stock_reports。")
        cached_results = (st.session_state.get(DEEP_RESEARCH_STATE_KEY) or {}).get("results") or []
        if cached_results:
            st.markdown("#### 深度研究结果")
            for item in cached_results:
                _render_result_expander(item)
        return

    results = []
    status_box = st.status("准备深度研究 Top 候选", expanded=True)
    progress = st.progress(0)
    total = len(selected_rows)
    for index, row in enumerate(selected_rows, start=1):
        candidate = row.get("candidate") or {}
        ticker = candidate.get("ticker") or ""
        name = candidate.get("name") or ""
        status_box.update(label=f"正在研究 {index}/{total}：{ticker} {name}", state="running")
        try:
            result = run_deep_research_for_candidate(
                supabase=supabase,
                row=row,
                holding_context=holding_context,
                callbacks=callbacks,
                use_cache=use_cache,
                force_refresh=force_refresh,
            )
            results.append(result)
            if result.get("error"):
                status_box.write(f"{ticker} 失败：{result.get('error')}")
            elif result.get("cached"):
                status_box.write(f"{ticker} 命中缓存：{result.get('generated_at')}")
            else:
                status_box.write(f"{ticker} 完成并尝试写入缓存：{result.get('generated_at')}")
        except Exception as exc:
            results.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "status": "failed",
                    "cached": False,
                    "generated_at": "",
                    "payload": {},
                    "result": {},
                    "forbidden_words": [],
                    "error": str(exc),
                }
            )
            status_box.write(f"{ticker} 失败：{exc}")
        progress.progress(index / max(total, 1))
    status_box.update(label="深度研究完成", state="complete")
    st.session_state[DEEP_RESEARCH_STATE_KEY] = {
        "scan_params_hash": (st.session_state.get(RADAR_SCAN_STATE_KEY) or {}).get("params_hash"),
        "generated_at": _now_iso(),
        "results": sanitize_for_json(results),
    }

    st.markdown("#### 深度研究结果")
    for item in results:
        _render_result_expander(item)
