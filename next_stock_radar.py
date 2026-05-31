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
RADAR_SCAN_STATUS_KEY = "radar_scan_status"
RADAR_SCAN_STARTED_AT_KEY = "radar_scan_started_at"
RADAR_SCAN_FINISHED_AT_KEY = "radar_scan_finished_at"
RADAR_SCAN_SUMMARY_KEY = "radar_scan_summary"
RADAR_SCAN_ERRORS_KEY = "radar_scan_errors"

RADAR_SCAN_IDLE = "idle"
RADAR_SCAN_RUNNING = "running"
RADAR_SCAN_COMPLETED = "completed"
RADAR_SCAN_PARTIAL_FAILED = "partial_failed"
RADAR_SCAN_FAILED = "failed"

SCAN_STRENGTH_PRESETS = {
    "标准模式": {
        "refine_candidate_limit": 100,
        "display_limit": 20,
        "description": "全量横截面粗筛，精筛 Top 100，展示 Top 20。",
    },
    "深度模式": {
        "refine_candidate_limit": 300,
        "display_limit": 50,
        "description": "全量横截面粗筛，精筛 Top 300，展示 Top 50。",
    },
    "火力全开模式": {
        "refine_candidate_limit": 500,
        "display_limit": 100,
        "description": "全量横截面粗筛，精筛 Top 500；可手动提高到 Top 1000，展示 Top 100。",
    },
}

INDEX_POOL_OPTIONS = {
    "沪深300": {
        "index_code": "000300.SH",
        "description": "沪深两市大盘代表性成分。",
        "default_refine_candidate_limit": 100,
        "default_display_limit": 20,
    },
    "中证500": {
        "index_code": "000905.SH",
        "description": "中盘代表性成分。",
        "default_refine_candidate_limit": 100,
        "default_display_limit": 20,
    },
    "中证1000": {
        "index_code": "000852.SH",
        "description": "小盘成长与行业覆盖更宽。",
        "default_refine_candidate_limit": 100,
        "default_display_limit": 20,
    },
    "中证2000": {
        "index_code": "932000.CSI",
        "description": "覆盖更长尾的小微盘成分，样本更多。",
        "default_refine_candidate_limit": 300,
        "default_display_limit": 50,
    },
    "中证A500": {
        "index_code": "000510.SH",
        "description": "A500 指数代码依 Tushare 权限与收录为准，可能无数据。",
        "default_refine_candidate_limit": 100,
        "default_display_limit": 20,
    },
    "自定义指数代码": {
        "index_code": "",
        "description": "手动输入 Tushare index_code，例如 000300.SH。",
        "default_refine_candidate_limit": 100,
        "default_display_limit": 20,
    },
}


def _ensure_radar_scan_session_state() -> None:
    if RADAR_SCAN_STATUS_KEY not in st.session_state:
        st.session_state[RADAR_SCAN_STATUS_KEY] = RADAR_SCAN_IDLE
    if RADAR_SCAN_STARTED_AT_KEY not in st.session_state:
        st.session_state[RADAR_SCAN_STARTED_AT_KEY] = ""
    if RADAR_SCAN_FINISHED_AT_KEY not in st.session_state:
        st.session_state[RADAR_SCAN_FINISHED_AT_KEY] = ""
    if RADAR_SCAN_SUMMARY_KEY not in st.session_state:
        st.session_state[RADAR_SCAN_SUMMARY_KEY] = {}
    if RADAR_SCAN_ERRORS_KEY not in st.session_state:
        st.session_state[RADAR_SCAN_ERRORS_KEY] = []
    if RADAR_SCAN_STATE_KEY not in st.session_state:
        st.session_state[RADAR_SCAN_STATE_KEY] = {}


def _scan_error(stage: str, message: Any, ticker: str = "") -> dict[str, Any]:
    return sanitize_for_json(
        {
            "time": _now_iso(),
            "stage": str(stage or "未知阶段"),
            "ticker": str(ticker or ""),
            "message": str(message or "未知错误"),
        }
    )


def _limit_scan_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sanitize_for_json((errors or [])[-20:])


def _parse_iso_datetime(value: Any) -> datetime.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed
    except Exception:
        return None


def _elapsed_seconds(started_at: Any, finished_at: Any) -> float:
    start = _parse_iso_datetime(started_at)
    finish = _parse_iso_datetime(finished_at)
    if not start or not finish:
        return 0.0
    return round(max(0.0, (finish - start).total_seconds()), 1)


def _fmt_count(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "0"
    return f"{int(number):,}"


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


def _metric(value: Any, default: float | None = None) -> float | None:
    """Read a scalar number after an explicit pandas missing-value check."""
    try:
        missing = pd.isna(value)
        if isinstance(missing, bool) and missing:
            return default
        if np is not None and isinstance(missing, np.bool_) and bool(missing):
            return default
    except Exception:
        pass
    return _num(value, default)


def _nonzero_metric(value: Any) -> float:
    return _metric(value, 0.0) or 0.0


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


def _primary_scan_meta(scan_meta: dict[str, Any]) -> dict[str, Any]:
    scan_meta = scan_meta or {}
    if scan_meta.get("index_scan") and not scan_meta.get("broad_scan"):
        return scan_meta.get("index_scan") or {}
    if scan_meta.get("broad_scan"):
        return scan_meta.get("broad_scan") or {}
    if scan_meta.get("index_scan"):
        return scan_meta.get("index_scan") or {}
    return {}


def _scan_total_label(scan_meta: dict[str, Any]) -> str:
    primary = _primary_scan_meta(scan_meta)
    if primary.get("scan_kind") == "index_pool":
        return "指数成分股"
    return "A股主板全量候选池"


def _scan_status_subject(source_mode: str, scan_meta: dict[str, Any]) -> str:
    primary = _primary_scan_meta(scan_meta)
    pool_meta = primary.get("pool") or {}
    if primary.get("scan_kind") == "index_pool":
        index_name = primary.get("index_name") or pool_meta.get("index_name") or "指数"
        count = pool_meta.get("filtered_count") or primary.get("rough_universe_count") or 0
        return f"指数精选池扫描完成：{index_name} 成分 {_fmt_count(count)} 只"
    if (scan_meta or {}).get("broad_scan"):
        count = pool_meta.get("filtered_count") or primary.get("rough_universe_count") or 0
        return f"A股主板广域扫描完成：全量粗筛 {_fmt_count(count)} 只"
    return f"{source_mode or '规则雷达'}扫描完成"


def _build_scan_summary(
    *,
    source_mode: str,
    scan_strength: str,
    refine_candidate_limit: int,
    display_limit: int,
    scan_meta: dict[str, Any],
    rule_rows: list[dict[str, Any]],
    started_at: str,
    finished_at: str,
    failed_stage: str = "",
    error_message: str = "",
) -> dict[str, Any]:
    primary_meta = _primary_scan_meta(scan_meta)
    pool_meta = primary_meta.get("pool") or {}
    cross_meta = primary_meta.get("cross_section") or {}
    success_count = sum(1 for row in rule_rows or [] if not row.get("error"))
    failure_count = len(rule_rows or []) - success_count
    total_pool_count = pool_meta.get("filtered_count")
    if total_pool_count is None:
        total_pool_count = primary_meta.get("rough_universe_count") or len(rule_rows or [])
    evaluable_count = primary_meta.get("evaluable_count") or len(rule_rows or [])
    filtered_count = primary_meta.get("post_filter_count") or len(rule_rows or [])
    used_fallback = bool(primary_meta.get("degraded"))
    used_cross_section = bool((cross_meta.get("daily_rows") or 0) > 0 and not used_fallback)
    return sanitize_for_json(
        {
            "total_pool_label": _scan_total_label(scan_meta),
            "total_pool_count": total_pool_count,
            "evaluable_count": evaluable_count,
            "filtered_count": filtered_count,
            "refine_candidate_limit": int(refine_candidate_limit or 0),
            "refined_success_count": success_count,
            "refined_failure_count": failure_count,
            "display_count": min(len(rule_rows or []), int(display_limit or 0)),
            "display_limit": int(display_limit or 0),
            "elapsed_seconds": _elapsed_seconds(started_at, finished_at),
            "scan_source": source_mode,
            "scan_mode": scan_strength,
            "used_cross_section": used_cross_section,
            "used_fallback": used_fallback,
            "deepseek_called": False,
            "deepseek_detail": "未调用",
            "failed_stage": failed_stage,
            "error_message": error_message,
        }
    )


def _set_scan_state(
    *,
    status: str,
    scan_state: dict[str, Any],
    summary: dict[str, Any],
    errors: list[dict[str, Any]],
    started_at: str,
    finished_at: str,
) -> None:
    st.session_state[RADAR_SCAN_STATUS_KEY] = status
    st.session_state[RADAR_SCAN_STARTED_AT_KEY] = started_at
    st.session_state[RADAR_SCAN_FINISHED_AT_KEY] = finished_at
    st.session_state[RADAR_SCAN_SUMMARY_KEY] = sanitize_for_json(summary or {})
    st.session_state[RADAR_SCAN_ERRORS_KEY] = _limit_scan_errors(errors or [])
    st.session_state[RADAR_SCAN_STATE_KEY] = sanitize_for_json(scan_state or {})


def _clear_scan_state() -> None:
    st.session_state[RADAR_SCAN_STATUS_KEY] = RADAR_SCAN_IDLE
    st.session_state[RADAR_SCAN_STARTED_AT_KEY] = ""
    st.session_state[RADAR_SCAN_FINISHED_AT_KEY] = ""
    st.session_state[RADAR_SCAN_SUMMARY_KEY] = {}
    st.session_state[RADAR_SCAN_ERRORS_KEY] = []
    st.session_state[RADAR_SCAN_STATE_KEY] = {}


def _render_scan_result_panel() -> None:
    _ensure_radar_scan_session_state()
    status = st.session_state.get(RADAR_SCAN_STATUS_KEY) or RADAR_SCAN_IDLE
    summary = st.session_state.get(RADAR_SCAN_SUMMARY_KEY) or {}
    errors = st.session_state.get(RADAR_SCAN_ERRORS_KEY) or []
    if status == RADAR_SCAN_IDLE and not summary and not errors:
        return

    st.markdown("#### 📌 本次扫描结果")
    if status == RADAR_SCAN_COMPLETED:
        st.success("✅ 扫描完成")
    elif status == RADAR_SCAN_PARTIAL_FAILED:
        st.warning("⚠️ 扫描部分完成")
    elif status == RADAR_SCAN_FAILED:
        st.error("❌ 扫描失败")
    elif status == RADAR_SCAN_RUNNING:
        st.warning("上次扫描可能被中断，请点击重新扫描。")
    else:
        st.info("尚未开始本次扫描。")

    deepseek_called = bool(summary.get("deepseek_called"))
    deepseek_text = summary.get("deepseek_detail") or ("是" if deepseek_called else "未调用")
    total_pool_label = summary.get("total_pool_label") or "A股主板全量候选池"
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(total_pool_label, f"{_fmt_count(summary.get('total_pool_count'))} 只")
        st.metric("进入精筛候选", f"Top {summary.get('refine_candidate_limit') or 0}")
        st.metric("精筛成功", f"{_fmt_count(summary.get('refined_success_count'))} 只")
    with col2:
        st.metric("横截面可评估样本", f"{_fmt_count(summary.get('evaluable_count'))} 只")
        st.metric("规则雷达展示", f"Top {summary.get('display_limit') or summary.get('display_count') or 0}")
        st.metric("精筛失败", f"{_fmt_count(summary.get('refined_failure_count'))} 只")
    with col3:
        st.metric("过滤后样本", f"{_fmt_count(summary.get('filtered_count'))} 只")
        st.metric("耗时", f"{_num(summary.get('elapsed_seconds'), 0) or 0} 秒")
        st.metric("DeepSeek", deepseek_text)

    status_text = "已保存到本页 radar_scan_results" if st.session_state.get(RADAR_SCAN_STATE_KEY) else "暂无结果"
    st.caption(
        f"结果状态：{status_text} ｜ "
        f"扫描来源：{summary.get('scan_source') or '暂无'} ｜ "
        f"扫描强度：{summary.get('scan_mode') or '暂无'} ｜ "
        f"横截面：{'已使用' if summary.get('used_cross_section') else '未使用'} ｜ "
        f"fallback：{'是' if summary.get('used_fallback') else '否'}"
    )

    if status == RADAR_SCAN_PARTIAL_FAILED:
        st.warning("已保留成功生成的规则雷达结果；失败项可在下方摘要查看。")
    if status == RADAR_SCAN_FAILED:
        st.error(
            f"失败阶段：{summary.get('failed_stage') or '未知'}；"
            f"错误信息：{summary.get('error_message') or '暂无'}。"
        )
        st.info("建议降低进入精筛候选上限，或调整过滤条件后点击重新扫描。")
    if errors:
        with st.expander("失败原因摘要", expanded=status in {RADAR_SCAN_PARTIAL_FAILED, RADAR_SCAN_FAILED}):
            for item in errors[-20:]:
                ticker = f"｜{item.get('ticker')}" if item.get("ticker") else ""
                st.write(f"{item.get('stage')}{ticker}：{item.get('message')}")


def _mark_scan_deepseek_called(top_n: int) -> None:
    summary = dict(st.session_state.get(RADAR_SCAN_SUMMARY_KEY) or {})
    if not summary:
        return
    summary["deepseek_called"] = True
    summary["deepseek_top_n"] = int(top_n or 0)
    summary["deepseek_detail"] = f"是，仅对 Top {int(top_n or 0)} 候选"
    summary["deepseek_called_at"] = _now_iso()
    st.session_state[RADAR_SCAN_SUMMARY_KEY] = sanitize_for_json(summary)
    scan_state = dict(st.session_state.get(RADAR_SCAN_STATE_KEY) or {})
    if scan_state:
        scan_state["summary"] = sanitize_for_json(summary)
        st.session_state[RADAR_SCAN_STATE_KEY] = sanitize_for_json(scan_state)


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


def _normalize_index_code(value: Any) -> str:
    return str(value or "").strip().upper().replace(".SS", ".SH")


def _index_option_config(index_name: str, custom_index_code: str = "") -> dict[str, Any]:
    config = dict(INDEX_POOL_OPTIONS.get(index_name) or {})
    if index_name == "自定义指数代码":
        config["index_code"] = _normalize_index_code(custom_index_code)
        config["description"] = "自定义 Tushare 指数代码。"
    config["index_name"] = index_name if index_name != "自定义指数代码" else (config.get("index_code") or "自定义指数")
    return config


def load_index_constituent_pool(
    callbacks: dict[str, Callable[..., Any]],
    *,
    index_name: str,
    index_code: str,
    exclude_st: bool = True,
    exclude_chinext: bool = True,
    exclude_star: bool = True,
    exclude_bj: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    adapter = _adapter_from_callbacks(callbacks)
    index_code = _normalize_index_code(index_code)
    meta = {
        "source": "Tushare index_weight",
        "scan_kind": "index_pool",
        "index_name": index_name,
        "index_code": index_code,
        "degraded": False,
        "message": "",
        "raw_count": 0,
        "filtered_count": 0,
    }
    if not index_code:
        meta["degraded"] = True
        meta["message"] = "未提供指数代码，已降级为科技股样本池。"
        return pd.DataFrame(TECH_SAMPLE_POOL), meta
    if adapter is None or not hasattr(adapter, "get_index_weight"):
        meta["degraded"] = True
        meta["message"] = "Tushare index_weight 接口不可用，已降级为科技股样本池。"
        return pd.DataFrame(TECH_SAMPLE_POOL), meta

    dates = recent_trade_dates(callbacks, days=520)
    end_date = max(dates) if dates else datetime.date.today().strftime("%Y%m%d")
    start_candidates = []
    if dates:
        start_candidates.append(dates[-180] if len(dates) > 180 else dates[0])
        start_candidates.append(dates[-360] if len(dates) > 360 else dates[0])
    else:
        start_candidates.extend(
            [
                (datetime.date.today() - datetime.timedelta(days=280)).strftime("%Y%m%d"),
                (datetime.date.today() - datetime.timedelta(days=560)).strftime("%Y%m%d"),
            ]
        )

    frame = pd.DataFrame()
    last_error = ""
    for start_date in list(dict.fromkeys(start_candidates)):
        try:
            result = adapter.get_index_weight(index_code=index_code, start_date=start_date, end_date=end_date)
            frame = _result_frame(result)
            if not frame.empty:
                break
            last_error = (result or {}).get("error") or "index_weight 返回为空"
        except Exception as exc:
            last_error = str(exc)
            frame = pd.DataFrame()

    if frame.empty:
        meta["degraded"] = True
        meta["message"] = f"指数成分接口不可用或无数据（{index_name} {index_code}）：{last_error or '暂无返回'}；已降级为科技股样本池。"
        return pd.DataFrame(TECH_SAMPLE_POOL), meta

    meta["raw_count"] = len(frame)
    if "con_code" not in frame.columns:
        meta["degraded"] = True
        meta["message"] = f"index_weight 返回缺少 con_code（{index_name} {index_code}），已降级为科技股样本池。"
        return pd.DataFrame(TECH_SAMPLE_POOL), meta

    frame["ticker"] = frame["con_code"].map(_display_from_ts_code)
    frame["trade_date"] = frame["trade_date"].astype(str) if "trade_date" in frame.columns else ""
    latest_member_date = max(frame["trade_date"].dropna().astype(str)) if "trade_date" in frame.columns else ""
    if latest_member_date:
        frame = frame[frame["trade_date"].astype(str).eq(latest_member_date)].copy()
    frame["index_weight"] = pd.to_numeric(frame.get("weight"), errors="coerce") if "weight" in frame.columns else None
    frame["index_name"] = index_name
    frame["index_code"] = index_code
    frame["index_member_date"] = latest_member_date
    meta["latest_member_date"] = latest_member_date
    meta["latest_member_count"] = len(frame)

    a_share_mask = frame["ticker"].astype(str).str.endswith((".SH", ".SZ", ".BJ"))
    board_mask = frame["ticker"].map(lambda value: _is_main_board_ticker(value, exclude_chinext, exclude_star, exclude_bj))
    frame = frame[a_share_mask & board_mask].copy()
    meta["after_board_exclusion_count"] = len(frame)

    stock_basic = pd.DataFrame()
    stock_basic_error = ""
    if adapter is not None and hasattr(adapter, "get_stock_basic"):
        try:
            basic_result = adapter.get_stock_basic(exchange="", list_status="L")
            stock_basic = _result_frame(basic_result)
            if stock_basic.empty:
                stock_basic_error = (basic_result or {}).get("error") or "stock_basic 返回为空"
        except Exception as exc:
            stock_basic_error = str(exc)
    if not stock_basic.empty:
        stock_basic["ticker"] = stock_basic["ts_code"].map(_display_from_ts_code) if "ts_code" in stock_basic.columns else ""
        if "list_status" in stock_basic.columns:
            stock_basic = stock_basic[stock_basic["list_status"].astype(str).str.upper().eq("L")].copy()
        keep_cols = [col for col in ["ticker", "symbol", "name", "market", "exchange"] if col in stock_basic.columns]
        frame = frame.merge(stock_basic[keep_cols].drop_duplicates(subset=["ticker"]), on="ticker", how="left")
    else:
        meta["stock_basic_message"] = stock_basic_error or "stock_basic 不可用，指数成分名称使用本地映射兜底。"

    frame["name"] = frame["name"].fillna("") if "name" in frame.columns else ""
    if exclude_st:
        frame = frame[~frame["name"].map(_is_st_or_delisting)].copy()
    meta["after_st_exclusion_count"] = len(frame)

    frame["symbol"] = frame["symbol"].astype(str) if "symbol" in frame.columns else frame["ticker"].map(_ticker_core)
    frame["name"] = frame.apply(lambda row: candidate_name(row.get("ticker"), row.get("name") or ""), axis=1)
    frame["market"] = frame["market"].astype(str) if "market" in frame.columns else ""
    frame["exchange"] = frame["exchange"].astype(str) if "exchange" in frame.columns else ""
    frame = frame.drop_duplicates(subset=["ticker"]).reset_index(drop=True)
    meta["filtered_count"] = len(frame)
    if frame.empty:
        meta["degraded"] = True
        meta["message"] = f"{index_name} 成分过滤后为空，已降级为科技股样本池。"
        return pd.DataFrame(TECH_SAMPLE_POOL), meta
    return frame[
        [
            "ticker",
            "symbol",
            "name",
            "market",
            "exchange",
            "index_name",
            "index_code",
            "index_weight",
            "index_member_date",
        ]
    ], sanitize_for_json(meta)


def build_index_pool_rough_candidates(
    callbacks: dict[str, Callable[..., Any]],
    *,
    index_name: str,
    index_code: str,
    refine_candidate_limit: int,
    exclude_st: bool,
    exclude_chinext: bool,
    exclude_star: bool,
    exclude_bj: bool,
    exclude_low_amount: bool,
    trend_up_only: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool, pool_meta = load_index_constituent_pool(
        callbacks,
        index_name=index_name,
        index_code=index_code,
        exclude_st=exclude_st,
        exclude_chinext=exclude_chinext,
        exclude_star=exclude_star,
        exclude_bj=exclude_bj,
    )
    if pool_meta.get("degraded"):
        candidates = [
            {
                **item,
                "scan_source": "指数精选池 fallback_tech_sample",
                "candidate_source": "指数精选池",
                "rough_context": {"data_gaps": ["指数成分接口不可用"]},
            }
            for item in TECH_SAMPLE_POOL[:refine_candidate_limit]
        ]
        return candidates, {
            "pool": pool_meta,
            "scan_kind": "index_pool",
            "degraded": True,
            "message": pool_meta.get("message"),
            "rough_count": len(candidates),
            "refine_candidate_limit": refine_candidate_limit,
            "refine_candidate_count": len(candidates),
        }

    dates = recent_trade_dates(callbacks, days=150)
    window_dates = dates[-90:] if len(dates) >= 90 else dates
    daily, daily_basic, data_meta = fetch_cross_section_window(callbacks, window_dates)
    if daily.empty:
        candidates = [
            {
                **item,
                "scan_source": "指数精选池 fallback_tech_sample",
                "candidate_source": "指数精选池",
                "rough_context": {"data_gaps": ["daily 横截面不可用"]},
            }
            for item in TECH_SAMPLE_POOL[:refine_candidate_limit]
        ]
        return candidates, {
            "pool": pool_meta,
            "cross_section": data_meta,
            "scan_kind": "index_pool",
            "degraded": True,
            "message": data_meta.get("message"),
            "rough_count": len(candidates),
            "refine_candidate_limit": refine_candidate_limit,
            "refine_candidate_count": len(candidates),
        }

    pool_tickers = set(pool["ticker"].astype(str))
    daily = daily[daily["ticker"].isin(pool_tickers)].copy()
    if daily.empty:
        candidates = [
            {
                **item,
                "scan_source": "指数精选池 fallback_tech_sample",
                "candidate_source": "指数精选池",
                "rough_context": {"data_gaps": ["daily 与指数成分无交集"]},
            }
            for item in TECH_SAMPLE_POOL[:refine_candidate_limit]
        ]
        return candidates, {
            "pool": pool_meta,
            "cross_section": data_meta,
            "scan_kind": "index_pool",
            "degraded": True,
            "message": "daily 与指数成分无交集",
            "rough_count": len(candidates),
            "refine_candidate_limit": refine_candidate_limit,
            "refine_candidate_count": len(candidates),
        }

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
    if "index_weight" in latest.columns:
        latest["index_weight"] = pd.to_numeric(latest["index_weight"], errors="coerce")
        valid_weights = latest["index_weight"].dropna()
        if not valid_weights.empty:
            high_weight_threshold = valid_weights.quantile(0.75)
            high_weight_mask = latest["index_weight"].fillna(0).ge(high_weight_threshold) & latest["index_weight"].fillna(0).gt(0)
            latest.loc[high_weight_mask, "rough_score"] += 3
            latest.loc[high_weight_mask, "rough_notes"] += "指数权重较高，轻微优先；"
    incomplete = latest[["MA20", "MA60"]].isna().any(axis=1)
    latest.loc[incomplete, "rough_score"] -= 25
    latest.loc[incomplete, "rough_notes"] += "MA数据不完整；"
    stale = ~latest["is_latest_trade_date"]
    latest.loc[stale, "rough_score"] -= 25
    latest.loc[stale, "rough_notes"] += "疑似停牌或非最新交易日；"
    if "amount" in latest.columns:
        low_amount_mask = latest["amount"].fillna(0).lt(100000)
    else:
        low_amount_mask = pd.Series(False, index=latest.index)
    if exclude_low_amount:
        latest.loc[low_amount_mask, "rough_score"] -= 12
        latest.loc[low_amount_mask, "rough_notes"] += "成交额偏低；"
    evaluable_mask = ~incomplete & ~stale
    evaluable_count = int(evaluable_mask.sum())
    base_filter_mask = evaluable_mask.copy()
    if exclude_low_amount:
        base_filter_mask &= ~low_amount_mask
        low_amount_pass_count = int(base_filter_mask.sum())
    else:
        low_amount_pass_count = evaluable_count
    trend_pass_count = int((base_filter_mask & trend_mask & ~hot_mask).sum())
    filter_mask = base_filter_mask.copy()
    if trend_up_only:
        filter_mask &= trend_mask & ~hot_mask
    latest = latest[filter_mask].copy()
    post_filter_count = len(latest)

    latest["rough_score"] = latest["rough_score"].clip(0, 100)
    latest = latest.sort_values("rough_score", ascending=False).copy()
    full_rough_ranked_count = len(latest)
    refine_candidate_limit = max(1, int(refine_candidate_limit))
    latest = latest.head(refine_candidate_limit).copy()
    refine_candidate_count = len(latest)

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
            "scan_source": "指数精选池",
            "candidate_source": "指数精选池",
            "index_name": row.get("index_name") or index_name,
            "index_code": row.get("index_code") or index_code,
            "index_weight": _num(row.get("index_weight")),
            "index_member_date": str(row.get("index_member_date") or ""),
        }
        candidates.append(
            {
                "ticker": ticker,
                "name": rough_context["name"],
                "scan_source": "指数精选池",
                "candidate_source": "指数精选池",
                "index_name": rough_context["index_name"],
                "index_code": rough_context["index_code"],
                "index_weight": rough_context["index_weight"],
                "index_member_date": rough_context["index_member_date"],
                "rough_context": rough_context,
            }
        )

    meta = {
        "pool": pool_meta,
        "cross_section": data_meta,
        "scan_kind": "index_pool",
        "degraded": False,
        "index_name": index_name,
        "index_code": index_code,
        "latest_trade_date": latest_trade_date,
        "rough_count": len(candidates),
        "rough_universe_count": len(daily["ticker"].unique()),
        "latest_pre_filter_count": latest_pre_filter_count,
        "evaluable_count": evaluable_count,
        "low_amount_pass_count": low_amount_pass_count,
        "trend_up_pass_count": trend_pass_count,
        "post_filter_count": post_filter_count,
        "full_rough_ranked_count": full_rough_ranked_count,
        "refine_candidate_limit": refine_candidate_limit,
        "refine_candidate_count": refine_candidate_count,
        "full_scan_mode": False,
        "message": "",
    }
    return candidates, sanitize_for_json(meta)


def build_cross_section_rough_candidates(
    callbacks: dict[str, Callable[..., Any]],
    *,
    refine_candidate_limit: int,
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
            for item in TECH_SAMPLE_POOL[:refine_candidate_limit]
        ]
        return candidates, {
            "pool": pool_meta,
            "degraded": True,
            "message": pool_meta.get("message"),
            "rough_count": len(candidates),
            "refine_candidate_limit": refine_candidate_limit,
            "refine_candidate_count": len(candidates),
        }

    dates = recent_trade_dates(callbacks, days=150)
    window_dates = dates[-90:] if len(dates) >= 90 else dates
    daily, daily_basic, data_meta = fetch_cross_section_window(callbacks, window_dates)
    if daily.empty:
        candidates = [
            {**item, "scan_source": "fallback_tech_sample", "rough_context": {"data_gaps": ["daily 横截面不可用"]}}
            for item in TECH_SAMPLE_POOL[:refine_candidate_limit]
        ]
        return candidates, {
            "pool": pool_meta,
            "cross_section": data_meta,
            "degraded": True,
            "message": data_meta.get("message"),
            "rough_count": len(candidates),
            "refine_candidate_limit": refine_candidate_limit,
            "refine_candidate_count": len(candidates),
        }

    pool_tickers = set(pool["ticker"].astype(str))
    daily = daily[daily["ticker"].isin(pool_tickers)].copy()
    if daily.empty:
        candidates = [
            {**item, "scan_source": "fallback_tech_sample", "rough_context": {"data_gaps": ["daily 与主板池无交集"]}}
            for item in TECH_SAMPLE_POOL[:refine_candidate_limit]
        ]
        return candidates, {
            "pool": pool_meta,
            "cross_section": data_meta,
            "degraded": True,
            "message": "daily 与主板池无交集",
            "rough_count": len(candidates),
            "refine_candidate_limit": refine_candidate_limit,
            "refine_candidate_count": len(candidates),
        }

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
    if "amount" in latest.columns:
        low_amount_mask = latest["amount"].fillna(0).lt(100000)
    else:
        low_amount_mask = pd.Series(False, index=latest.index)
    if exclude_low_amount:
        latest.loc[low_amount_mask, "rough_score"] -= 12
        latest.loc[low_amount_mask, "rough_notes"] += "成交额偏低；"
    evaluable_mask = ~incomplete & ~stale
    evaluable_count = int(evaluable_mask.sum())
    base_filter_mask = evaluable_mask.copy()
    if exclude_low_amount:
        base_filter_mask &= ~low_amount_mask
        low_amount_pass_count = int(base_filter_mask.sum())
    else:
        low_amount_pass_count = evaluable_count
    trend_pass_count = int((base_filter_mask & trend_mask & ~hot_mask).sum())
    filter_mask = base_filter_mask.copy()
    if trend_up_only:
        filter_mask &= trend_mask & ~hot_mask
    latest = latest[filter_mask].copy()
    post_filter_count = len(latest)

    latest["rough_score"] = latest["rough_score"].clip(0, 100)
    latest = latest.sort_values("rough_score", ascending=False).copy()
    full_rough_ranked_count = len(latest)
    refine_candidate_limit = max(1, int(refine_candidate_limit))
    latest = latest.head(refine_candidate_limit).copy()
    refine_candidate_count = len(latest)

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
        "full_rough_ranked_count": full_rough_ranked_count,
        "refine_candidate_limit": refine_candidate_limit,
        "refine_candidate_count": refine_candidate_count,
        "full_scan_mode": True,
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


def _rule_dimension_scores(context: dict[str, Any]) -> dict[str, Any]:
    price = _metric(context.get("current_price"))
    ma20 = _metric(context.get("MA20"))
    ma60 = _metric(context.get("MA60"))
    rsi = _metric(context.get("RSI"))
    return_20d = _metric(context.get("twenty_day_return_pct"))
    today_main = _metric(context.get("today_main_net_yi"))
    five_day_main = _metric(context.get("five_day_main_net_yi"))
    pledge_ratio = _metric(context.get("pledge_ratio"))
    chip_center = _metric(context.get("chip_center"))
    winner_rate = _metric(context.get("winner_rate"))
    data_gaps = list(context.get("data_gaps") or [])

    trend = 45
    trend_notes = []
    if price is not None and ma20 is not None and ma60 is not None and price > ma20 > ma60:
        trend += 35
        trend_notes.append("当前价 > MA20 > MA60")
    elif price is not None and ma20 is not None and price < ma20:
        trend -= 18
        trend_notes.append("跌破 MA20")
    if price is not None and ma60 is not None and price < ma60:
        trend -= 28
        trend_notes.append("跌破 MA60")
    if return_20d is not None and return_20d > 25:
        trend -= 6
        trend_notes.append("20日涨幅偏快")
    if rsi is not None and rsi > 78:
        trend -= 8
        trend_notes.append("RSI 偏热")
    if ma20 is None or ma60 is None:
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
    if context.get("has_reduction_risk"):
        risk -= 22
        risk_notes.append("控股股东减持")
    if pledge_ratio is not None and pledge_ratio > 15:
        risk -= 16
        risk_notes.append("质押比例 >15%")
    financing_balance = _metric(((context.get("margin") or {}).get("financing_balance_yi")))
    if financing_balance is not None and financing_balance >= 20 and "跌破" in str(context.get("trend_state")):
        risk -= 10
        risk_notes.append("融资余额高且价格转弱")
    if context.get("dragon_tiger_expired"):
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
    if price is not None and chip_center is not None and chip_center > 0:
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
    if context.get("near_limit_up") or context.get("chase_zone"):
        position -= 18
        position_notes.append("离涨停太近或处于追高区")
    if winner_rate is not None and winner_rate > 75:
        position -= 6
        position_notes.append("获利盘比例偏高")

    completeness = 100 - len(data_gaps) * 10
    if not data_gaps:
        completeness += 5
    completeness = _clip_score(completeness)

    return {
        "trend_score": _clip_score(trend),
        "money_score": _clip_score(money),
        "risk_score": _clip_score(risk),
        "position_score": _clip_score(position),
        "information_score": completeness,
        "money_wait": bool(money_wait),
        "score_notes": {
            "trend": trend_notes,
            "money": money_notes,
            "risk": risk_notes,
            "position": position_notes,
            "data_gaps": data_gaps,
        },
    }


def _weighted_rule_total(dimensions: dict[str, Any], compare_score: int = 50) -> int:
    total = (
        _clip_score(dimensions.get("trend_score")) * 0.25
        + _clip_score(dimensions.get("money_score")) * 0.22
        + _clip_score(dimensions.get("risk_score")) * 0.22
        + _clip_score(dimensions.get("position_score")) * 0.16
        + _clip_score(dimensions.get("information_score")) * 0.10
        + _clip_score(compare_score) * 0.05
    )
    return _clip_score(total)


def _holding_score_baseline(holding_context: dict[str, Any]) -> dict[str, Any]:
    data_gaps = []
    if _metric(holding_context.get("holding_ma20")) is None or _metric(holding_context.get("holding_ma60")) is None:
        data_gaps.append("趋势")
    if (
        _metric(holding_context.get("holding_today_main_net_yi")) is None
        and _metric(holding_context.get("holding_five_day_main_net_yi")) is None
    ):
        data_gaps.append("资金")
    if holding_context.get("holding_has_announcement_gap"):
        data_gaps.append("公告")
    if holding_context.get("holding_has_news_gap"):
        data_gaps.append("news_digest")
    if any("筹码" in str(item) for item in holding_context.get("holding_biggest_risks") or []):
        data_gaps.append("筹码")

    comparable_context = {
        "current_price": holding_context.get("current_price"),
        "MA20": holding_context.get("holding_ma20"),
        "MA60": holding_context.get("holding_ma60"),
        "RSI": holding_context.get("holding_rsi"),
        "MACD": holding_context.get("holding_macd"),
        "twenty_day_return_pct": holding_context.get("holding_20d_return_pct"),
        "today_main_net_yi": holding_context.get("holding_today_main_net_yi"),
        "five_day_main_net_yi": holding_context.get("holding_five_day_main_net_yi"),
        "moneyflow_state": holding_context.get("holding_moneyflow_state"),
        "has_reduction_risk": holding_context.get("holding_has_reduction_risk"),
        "pledge_ratio": holding_context.get("holding_pledge_ratio"),
        "trend_state": holding_context.get("holding_trend_state"),
        "data_gaps": list(dict.fromkeys(data_gaps)),
        "chip_center": None,
        "winner_rate": None,
        "near_limit_up": False,
        "chase_zone": False,
    }
    dimensions = _rule_dimension_scores(comparable_context)
    return {
        "holding_trend_score": dimensions["trend_score"],
        "holding_money_score": dimensions["money_score"],
        "holding_risk_score": dimensions["risk_score"],
        "holding_position_score": dimensions["position_score"],
        "holding_information_score": dimensions["information_score"],
        "holding_total_score": _weighted_rule_total(dimensions),
        "holding_score_notes": dimensions["score_notes"],
    }


def _compare_label(candidate_score: int, holding_score: int, higher_label: str, lower_label: str, tolerance: int = 8) -> str:
    if candidate_score >= holding_score + tolerance:
        return higher_label
    if holding_score >= candidate_score + tolerance:
        return lower_label
    return "接近"


def _holding_has_reduce_pressure(holding_context: dict[str, Any]) -> bool:
    action = str(holding_context.get("holding_action_state") or "")
    if any(keyword in action for keyword in ["减仓", "暂停加仓", "风险升级"]):
        return True
    risks = "；".join(str(item) for item in holding_context.get("holding_biggest_risks") or [])
    return any(keyword in risks for keyword in ["减持", "质押", "资金流出", "公告缺失"])


def determine_candidate_vs_holding_relation(candidate: dict[str, Any], holding_context: dict[str, Any]) -> dict[str, Any]:
    candidate_dimensions = _rule_dimension_scores(candidate)
    holding_baseline = {
        **_holding_score_baseline(holding_context),
        **{key: holding_context.get(key) for key in [
            "holding_trend_score",
            "holding_money_score",
            "holding_risk_score",
            "holding_position_score",
            "holding_information_score",
            "holding_total_score",
        ] if holding_context.get(key) is not None},
    }

    candidate_trend = _clip_score(candidate_dimensions.get("trend_score"))
    candidate_money = _clip_score(candidate_dimensions.get("money_score"))
    candidate_risk = _clip_score(candidate_dimensions.get("risk_score"))
    candidate_position = _clip_score(candidate_dimensions.get("position_score"))
    candidate_info = _clip_score(candidate_dimensions.get("information_score"))
    candidate_total = _weighted_rule_total(candidate_dimensions)

    holding_trend = _clip_score(holding_baseline.get("holding_trend_score"))
    holding_money = _clip_score(holding_baseline.get("holding_money_score"))
    holding_risk = _clip_score(holding_baseline.get("holding_risk_score"))
    holding_position = _clip_score(holding_baseline.get("holding_position_score"))
    holding_total = _clip_score(holding_baseline.get("holding_total_score"))

    today_main = _nonzero_metric(candidate.get("today_main_net_yi"))
    five_day_main = _nonzero_metric(candidate.get("five_day_main_net_yi"))
    return_20d = _nonzero_metric(candidate.get("twenty_day_return_pct"))
    overheated = bool(candidate.get("near_limit_up") or candidate.get("chase_zone") or return_20d > 60 or candidate_position < 45)
    reduce_pressure = _holding_has_reduce_pressure(holding_context)

    trend_advantage = _compare_label(candidate_trend, holding_trend, "候选趋势更强", "当前持仓趋势更强")
    money_advantage = _compare_label(candidate_money, holding_money, "候选资金更强", "当前持仓资金更强")
    risk_advantage = _compare_label(candidate_risk, holding_risk, "候选风险更低", "当前持仓风险更低")
    position_advantage = _compare_label(candidate_position, holding_position, "候选位置更健康", "当前持仓位置更健康")

    if (
        candidate_risk < 42
        or candidate_info < 45
        or candidate_total < max(50, holding_total - 14)
        or (overheated and candidate_money < 62)
        or (today_main < 0 and five_day_main < 0)
    ):
        relation = "暂不替代"
    elif (
        reduce_pressure
        and candidate_total >= holding_total + 8
        and candidate_risk >= holding_risk + 14
        and candidate_trend >= holding_trend - 8
        and candidate_money >= holding_money - 5
        and candidate_position >= 68
    ):
        relation = "替代观察"
    elif (
        candidate_trend >= max(75, holding_trend - 2)
        and candidate_money >= max(62, holding_money + 8)
        and candidate_risk >= holding_risk - 8
        and candidate_position >= 55
        and not overheated
    ):
        relation = "接力观察"
    elif candidate_risk >= max(64, holding_risk + 5) and candidate_position >= 52:
        relation = "防守观察"
    elif (not reduce_pressure) and candidate_total >= holding_total + 8 and candidate_risk >= holding_risk + 8 and candidate_position >= 50:
        relation = "替代观察"
    else:
        relation = "暂不替代"

    return {
        "candidate_vs_holding_trend_advantage": trend_advantage,
        "candidate_vs_holding_moneyflow_advantage": money_advantage,
        "candidate_vs_holding_risk_advantage": risk_advantage,
        "candidate_vs_holding_position_advantage": position_advantage,
        "candidate_switch_relation": relation,
        "candidate_comparable_scores": {
            "candidate_trend_score": candidate_trend,
            "candidate_money_score": candidate_money,
            "candidate_risk_score": candidate_risk,
            "candidate_position_score": candidate_position,
            "candidate_information_score": candidate_info,
            "candidate_total_score_before_relation": candidate_total,
            "holding_trend_score": holding_trend,
            "holding_money_score": holding_money,
            "holding_risk_score": holding_risk,
            "holding_position_score": holding_position,
            "holding_total_score": holding_total,
        },
    }


def build_candidate_trigger_conditions(candidate: dict[str, Any], holding_context: dict[str, Any]) -> list[str]:
    today_main = _nonzero_metric(candidate.get("today_main_net_yi"))
    five_day_main = _nonzero_metric(candidate.get("five_day_main_net_yi"))
    price = _metric(candidate.get("current_price"))
    ma20 = _metric(candidate.get("MA20"))
    ma60 = _metric(candidate.get("MA60"))
    chip_center = _metric(candidate.get("chip_center"))
    return_20d = _nonzero_metric(candidate.get("twenty_day_return_pct"))
    dimensions = _rule_dimension_scores(candidate)
    relation = candidate.get("candidate_switch_relation") or "暂不替代"
    data_gaps = set(candidate.get("data_gaps") or [])

    conditions = []
    if today_main > 0 and five_day_main > 0:
        conditions.append("资金连续性较好，需验证次日主力资金不转流出")
    elif today_main > 0 and five_day_main < 0:
        conditions.append("今日资金回流但中期未扭转，需连续 2 日主力净流入确认")
    elif today_main < 0 and five_day_main < 0:
        conditions.append("资金仍处压力段，需先看到主力资金由流出转为回流")
    else:
        conditions.append("资金方向仍有分歧，需补一日资金确认")

    if price is not None and ma20 is not None and ma60 is not None and price > ma20 > ma60:
        conditions.append("趋势结构保持 MA20 在 MA60 上方，回踩 MA20 不破可继续观察")
    elif price is not None and ma20 is not None and price < ma20:
        conditions.append("当前未站稳 MA20，需先收回 MA20 后再提升准备级别")
    elif ma20 is None or ma60 is None:
        conditions.append("均线数据不完整，需补齐 MA20/MA60 后再确认趋势结构")

    if candidate.get("near_limit_up") or candidate.get("chase_zone") or return_20d > 60 or _clip_score(dimensions.get("position_score")) < 55:
        conditions.append("不追高，需等待回踩后仍站稳关键均线或筹码中枢")
    elif chip_center is not None and price is not None and price >= chip_center:
        conditions.append("价格高于筹码中枢但未明显过热，需确认回踩中枢不破")

    if chip_center is None or "筹码" in data_gaps:
        conditions.append("筹码中枢缺失，需用 MA20/MA60 替代验证，不提高动作级别")
    if "公告" in data_gaps or "news_digest" in data_gaps:
        conditions.append("公告/news_digest 缺口未补齐前，只能进入观察，不进入直接动作")

    if relation == "接力观察":
        conditions.append("当前持仓出现减仓触发后，候选强趋势仍延续才作为接力观察")
    elif relation == "替代观察":
        conditions.append("若当前持仓出现减仓触发，可作为替代观察对象")
    elif relation == "防守观察":
        conditions.append("只有当前持仓风险继续升高时，才把该票作为防守备选")
    else:
        conditions.append("相比当前持仓优势不足，需分数和资金同时改善后再纳入准备池")

    if not _holding_has_reduce_pressure(holding_context):
        conditions.append("当前持仓未触发减仓条件前，候选仅作为准备池，不直接切换")

    return list(dict.fromkeys(conditions))[:5]


def build_candidate_invalidation_conditions(candidate: dict[str, Any], holding_context: dict[str, Any]) -> list[str]:
    dimensions = _rule_dimension_scores(candidate)
    relation = candidate.get("candidate_switch_relation") or "暂不替代"
    data_gaps = set(candidate.get("data_gaps") or [])
    today_main = _nonzero_metric(candidate.get("today_main_net_yi"))
    five_day_main = _nonzero_metric(candidate.get("five_day_main_net_yi"))

    conditions = []
    if _clip_score(dimensions.get("trend_score")) >= 70:
        conditions.append("跌破 MA20 且无法快速收回，趋势观察失效")
        conditions.append("跌破 MA60，中期结构失效")
    else:
        conditions.append("不能重新站稳 MA20，趋势修复假设失效")

    if _clip_score(dimensions.get("money_score")) >= 62:
        conditions.append("主力资金重新连续流出，资金优势失效")
    elif today_main < 0 and five_day_main < 0:
        conditions.append("主力资金继续双周期流出，剔除准备池")
    else:
        conditions.append("资金回流无法延续，维持观察不升级")

    if _clip_score(dimensions.get("position_score")) < 55 or candidate.get("chase_zone") or candidate.get("near_limit_up"):
        conditions.append("高位回落跌破筹码中枢，说明追高风险兑现")
    elif _metric(candidate.get("chip_center")) is not None:
        conditions.append("跌破筹码中枢后无法收回，位置优势失效")

    if _clip_score(dimensions.get("risk_score")) < 62:
        conditions.append("新增减持、质押、监管、业绩或公告负面，直接降级")
    if _clip_score(dimensions.get("information_score")) < 75 or "公告" in data_gaps or "news_digest" in data_gaps:
        conditions.append("公告/news_digest 长时间缺失且出现价格异动，降低置信度")

    if relation == "接力观察":
        conditions.append("候选强势无法延续，不能作为当前持仓接力标的")
    elif relation == "替代观察":
        conditions.append("候选风险优势消失，不能作为当前持仓替代备选")
    elif relation == "防守观察":
        conditions.append("防守属性失效，例如资金转弱或跌破 MA60，则剔除观察池")
    else:
        conditions.append("相比当前持仓仍无优势，继续留在观察外层")

    return list(dict.fromkeys(conditions))[:5]


def _battle_state_from_scores(
    candidate: dict[str, Any],
    dimensions: dict[str, Any],
    total: int,
    relation: str,
) -> tuple[str, str]:
    trend = _clip_score(dimensions.get("trend_score"))
    money = _clip_score(dimensions.get("money_score"))
    risk = _clip_score(dimensions.get("risk_score"))
    position = _clip_score(dimensions.get("position_score"))
    information = _clip_score(dimensions.get("information_score"))
    money_wait = bool(dimensions.get("money_wait"))
    today_main = _nonzero_metric(candidate.get("today_main_net_yi"))
    five_day_main = _nonzero_metric(candidate.get("five_day_main_net_yi"))
    overheated = bool(candidate.get("near_limit_up") or candidate.get("chase_zone") or position < 45)
    has_hard_risk = bool(candidate.get("has_reduction_risk") or (_metric(candidate.get("pledge_ratio")) or 0) > 20)

    if risk < 35 or (has_hard_risk and money < 45):
        return "风险过高", "硬风险或资金压力叠加，优先降级处理"
    if trend < 35 or money < 30 or position < 28:
        return "暂不纳入", "趋势、资金或位置结构不足，不进入作战准备"
    if total >= 72 and risk >= 58 and (trend >= 72 or money >= 72) and position >= 50 and not overheated:
        return "可准备", f"{relation}下趋势/资金至少一项较强，风险未明显失控"
    if money_wait or (today_main > 0 and five_day_main < 0):
        return "等验证", "短线资金改善但近5日尚未确认，需要连续性验证"
    if total >= 58 and (trend >= 62 or money >= 58) and risk >= 45:
        if overheated:
            return "等验证", "趋势有看点但位置偏热，需要回踩确认"
        if information < 70:
            return "等验证", "规则分尚可但信息缺口影响置信度"
        return "等验证", "结构有改善，但仍需资金、位置或持仓切换条件确认"
    if total >= 44 or trend >= 58:
        return "只观察", "题材或趋势有线索，但风险、位置或信息完整度不足"
    return "暂不纳入", "相比当前持仓没有可验证优势，暂不进入准备池"


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

    context = {
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
    context.update(_holding_score_baseline(context))
    return sanitize_for_json(context)


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
        "candidate_source": candidate.get("candidate_source") or rough_context.get("candidate_source") or candidate.get("scan_source") or "手动输入",
        "index_name": candidate.get("index_name") or rough_context.get("index_name") or "",
        "index_code": candidate.get("index_code") or rough_context.get("index_code") or "",
        "index_weight": _num(candidate.get("index_weight") if candidate.get("index_weight") != "" else rough_context.get("index_weight")),
        "index_member_date": candidate.get("index_member_date") or rough_context.get("index_member_date") or "",
        "rough_context": rough_context,
    }
    context.update(compare_candidate_to_holding(context, holding_context))
    return sanitize_for_json(context)


def compare_candidate_to_holding(candidate_context: dict[str, Any], holding_context: dict[str, Any]) -> dict[str, Any]:
    return determine_candidate_vs_holding_relation(candidate_context, holding_context)


def score_candidate(candidate_context: dict[str, Any], holding_context: dict[str, Any]) -> dict[str, Any]:
    dimensions = _rule_dimension_scores(candidate_context)
    compare = 50
    relation = candidate_context.get("candidate_switch_relation") or "暂不替代"
    if relation == "接力观察":
        compare += 18
    elif relation == "替代观察":
        compare += 14
    elif relation == "防守观察":
        compare += 8
    elif relation == "暂不替代":
        compare -= 6

    total = _weighted_rule_total(dimensions, _clip_score(compare))
    index_weight = _num(candidate_context.get("index_weight"))
    index_weight_bonus = 0
    if index_weight is not None and index_weight >= 1:
        index_weight_bonus = 2
    elif index_weight is not None and index_weight >= 0.3:
        index_weight_bonus = 1
    if index_weight_bonus:
        total = _clip_score(total + index_weight_bonus)
        dimensions["score_notes"]["index_weight_bonus"] = f"指数权重 {index_weight:.3f}，轻微加分 {index_weight_bonus}"
    battle_state, battle_reason = _battle_state_from_scores(candidate_context, dimensions, total, relation)
    triggers = build_candidate_trigger_conditions(candidate_context, holding_context)
    invalidations = build_candidate_invalidation_conditions(candidate_context, holding_context)

    return sanitize_for_json(
        {
            "ticker": candidate_context.get("ticker"),
            "name": candidate_context.get("name"),
            "battle_state": battle_state,
            "battle_state_reason": battle_reason,
            "total_score": total,
            "trend_score": dimensions["trend_score"],
            "money_score": dimensions["money_score"],
            "risk_score": dimensions["risk_score"],
            "position_score": dimensions["position_score"],
            "information_score": dimensions["information_score"],
            "holding_compare_score": _clip_score(compare),
            "switch_relation": relation,
            "trigger_conditions": list(dict.fromkeys(triggers))[:5],
            "invalid_conditions": list(dict.fromkeys(invalidations))[:5],
            "score_notes": dimensions["score_notes"],
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
                        "battle_state_reason": "候选数据构造失败，规则层只能保守观察",
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
                "状态理由": score.get("battle_state_reason") or "",
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
                "来源指数": context.get("index_name") or "",
                "指数权重": context.get("index_weight") if context.get("index_weight") is not None else None,
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
    st.info("指数精选池不是荐股池；指数成分仅代表被指数规则纳入，不代表当前适合买入。系统只判断候选票是否值得进入作战准备。")

    _ensure_radar_scan_session_state()
    if DEEP_RESEARCH_STATE_KEY not in st.session_state:
        st.session_state[DEEP_RESEARCH_STATE_KEY] = {}

    holding_context_key = f"next_ticket_holding_context_{normalize_display_ticker(current_ticker)}"
    refresh_holding_context = st.button(
        "刷新当前持仓风险上下文",
        key="next_ticket_refresh_holding_context",
        width="stretch",
    )
    if refresh_holding_context:
        with st.spinner("正在刷新当前持仓技术与风控上下文..."):
            holding_context = build_current_holding_context(
                current_ticker=current_ticker,
                current_name=current_name,
                current_price=current_price,
                position_profile=position_profile or {},
                callbacks=callbacks,
            )
            holding_context["refreshed_at"] = _now_iso()
            holding_context["data_source"] = "技术快照 / Tushare 风控事实包 / 本地规则"
            st.session_state[holding_context_key] = holding_context
    else:
        holding_context = st.session_state.get(holding_context_key)
        if not holding_context:
            display_ticker = normalize_display_ticker(current_ticker)
            holding_context = sanitize_for_json(
                {
                    "current_holding_ticker": display_ticker,
                    "current_holding_name": current_name or candidate_name(display_ticker),
                    "position_status": (position_profile or {}).get("normalized_position_state")
                    or (position_profile or {}).get("position_status")
                    or "暂无数据",
                    "cost_price": (position_profile or {}).get("cost_price"),
                    "shares": (position_profile or {}).get("holding_units"),
                    "current_price": current_price,
                    "floating_profit_pct": (position_profile or {}).get("pnl_pct"),
                    "floating_profit_amount": (position_profile or {}).get("pnl_amount"),
                    "holding_biggest_risks": ["尚未刷新当前持仓风险上下文"],
                    "holding_action_state": "待刷新",
                    "holding_reduce_triggers": [],
                    "next_ticket_mode": "只观察",
                    "data_date": "",
                    "refreshed_at": "",
                    "data_source": "未加载",
                    "raw_data_quality": {
                        "technical_missing": ["未刷新"],
                        "risk_missing": ["未刷新"],
                    },
                }
            )
            holding_context.update(_holding_score_baseline(holding_context))
    holding_status = "已刷新" if refresh_holding_context else ("使用缓存" if holding_context.get("refreshed_at") else "未刷新")
    st.caption(
        "下一票雷达｜当前数据状态："
        f"{holding_status}｜最后刷新时间：{holding_context.get('refreshed_at') or '暂无'}｜"
        f"数据来源：{holding_context.get('data_source') or '未加载'}｜DeepSeek：未调用"
    )
    if holding_status == "未刷新":
        st.info("当前未运行，请点击按钮获取最新数据。")
    if render_next_ticket_holding_card:
        render_next_ticket_holding_card(holding_context)
    else:
        st.json(holding_context)

    st.markdown("#### 候选池输入")
    if "next_ticket_manual_candidates" not in st.session_state:
        st.session_state["next_ticket_manual_candidates"] = _candidate_text(DEFAULT_CANDIDATES)

    source_options = ["手动输入候选", "科技股样本池", "持续调查池", "A股主板广域扫描", "📊 指数精选池", "混合扫描"]
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

    index_name = "沪深300"
    index_code = INDEX_POOL_OPTIONS[index_name]["index_code"]
    index_config = _index_option_config(index_name)
    if source_mode in {"📊 指数精选池", "混合扫描"}:
        st.markdown("#### 📊 指数精选池 / 机构筛选池")
        st.caption(
            "指数精选池不是荐股池，只是使用已被指数规则筛选过的成分股作为候选范围，"
            "再由本系统进行趋势、资金、风险、位置和当前持仓对比评分。"
        )
        idx1, idx2 = st.columns([1.2, 1])
        index_option_names = list(INDEX_POOL_OPTIONS.keys())
        with idx1:
            index_name = st.selectbox(
                "指数选择",
                index_option_names,
                index=index_option_names.index("中证500"),
                key="next_ticket_index_pool_name",
            )
        with idx2:
            custom_index_code = st.text_input(
                "自定义指数代码",
                value="",
                key="next_ticket_custom_index_code",
                placeholder="例如 000300.SH",
                disabled=index_name != "自定义指数代码",
            )
        index_config = _index_option_config(index_name, custom_index_code)
        index_code = index_config.get("index_code") or ""
        st.caption(
            f"{index_name}：{index_code or '待输入'}｜{index_config.get('description') or ''} "
            "指数成分只代表被机构化规则纳入，不构成动作信号。"
        )

    st.markdown("#### 扫描参数")
    strength_options = list(SCAN_STRENGTH_PRESETS.keys())
    scan_strength = st.radio(
        "扫描强度",
        strength_options,
        index=1,
        horizontal=True,
        key="next_ticket_scan_strength",
        help="15000 积分档可承受更高频次，但仍建议用横截面粗筛 + Top 精筛，避免逐票请求导致页面卡顿。",
    )
    strength_preset = SCAN_STRENGTH_PRESETS.get(scan_strength, SCAN_STRENGTH_PRESETS["深度模式"])
    st.caption(f"{scan_strength}：{strength_preset['description']}")

    p1, p2 = st.columns(2)
    refine_options = [100, 300, 500, 1000]
    display_options = [20, 50, 100]
    strength_key = {"标准模式": "standard", "深度模式": "deep", "火力全开模式": "full"}.get(scan_strength, "deep")
    scope_key = "index" if source_mode == "📊 指数精选池" else ("mixed" if source_mode == "混合扫描" else "broad")
    default_refine_limit = int(strength_preset["refine_candidate_limit"])
    default_display_limit = int(strength_preset["display_limit"])
    if source_mode == "📊 指数精选池":
        default_refine_limit = int(index_config.get("default_refine_candidate_limit") or default_refine_limit)
        default_display_limit = int(index_config.get("default_display_limit") or default_display_limit)
    with p1:
        refine_candidate_limit = st.radio(
            "进入精筛候选上限",
            refine_options,
            index=refine_options.index(default_refine_limit if default_refine_limit in refine_options else 100),
            horizontal=True,
            key=f"next_ticket_refine_candidate_limit_{strength_key}_{scope_key}",
            help="不是只扫描这些股票。系统会先对全量候选池做横截面粗筛，再取 Top N 进入精筛。",
        )
    with p2:
        display_limit = st.radio(
            "规则雷达展示数量",
            display_options,
            index=display_options.index(default_display_limit if default_display_limit in display_options else 20),
            horizontal=True,
            key=f"next_ticket_display_limit_{strength_key}_{scope_key}",
        )
    st.caption(
        "进入精筛候选上限不是初始扫描股票数，而是全量横截面粗筛后进入精筛的候选数量。"
        "系统会先尽量覆盖所选候选池，再截取 Top 候选进入精筛。"
    )

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
            "index_name": index_name,
            "index_code": index_code,
            "scan_strength": scan_strength,
            "refine_candidate_limit": refine_candidate_limit,
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

    if source_mode == "A股主板广域扫描":
        start_label = "开始广域扫描"
    elif source_mode == "📊 指数精选池":
        start_label = "开始指数池扫描"
    elif source_mode == "混合扫描":
        start_label = "开始混合扫描"
    else:
        start_label = "生成规则雷达"
    b1, b2, b3 = st.columns(3)
    with b1:
        start_scan = st.button(start_label, type="primary", key="next_ticket_start_scan", width="stretch")
    with b2:
        rescan = st.button("重新扫描", key="next_ticket_rescan", width="stretch")
    with b3:
        clear_scan = st.button("清除本次扫描结果", key="next_ticket_clear_scan", width="stretch")
    if clear_scan:
        _clear_scan_state()
        st.rerun()

    scan_state = st.session_state.get(RADAR_SCAN_STATE_KEY) or {}
    should_scan = bool(start_scan or rescan)
    if should_scan:
        started_at = _now_iso()
        initial_summary = _build_scan_summary(
            source_mode=source_mode,
            scan_strength=scan_strength,
            refine_candidate_limit=int(refine_candidate_limit),
            display_limit=int(display_limit),
            scan_meta={},
            rule_rows=[],
            started_at=started_at,
            finished_at=started_at,
        )
        _set_scan_state(
            status=RADAR_SCAN_RUNNING,
            scan_state={},
            summary=initial_summary,
            errors=[],
            started_at=started_at,
            finished_at="",
        )
        st.session_state[DEEP_RESEARCH_STATE_KEY] = {}
        if source_mode == "📊 指数精选池":
            initial_status_label = "正在获取指数成分……"
        elif source_mode in {"A股主板广域扫描", "混合扫描"}:
            initial_status_label = "正在进行 A股主板全量横截面粗筛……"
        else:
            initial_status_label = "正在生成规则雷达……"
        status_box = st.status(initial_status_label, expanded=False)
        progress = st.progress(0)
        source_notes = []
        candidates: list[dict[str, Any]] = []
        scan_meta: dict[str, Any] = {}
        rule_rows: list[dict[str, Any]] = []
        scan_errors: list[dict[str, Any]] = []
        failed_stage = "初始化"

        try:
            if source_mode in {"📊 指数精选池", "混合扫描"}:
                failed_stage = "指数成分获取"
                status_box.update(label=f"正在获取指数成分并做横截面粗筛：{index_name} {index_code or '待输入'}……", state="running")
                index_candidates, index_meta = build_index_pool_rough_candidates(
                    callbacks,
                    index_name=index_name,
                    index_code=index_code,
                    refine_candidate_limit=int(refine_candidate_limit),
                    exclude_st=bool(exclude_st),
                    exclude_chinext=bool(exclude_chinext),
                    exclude_star=bool(exclude_star),
                    exclude_bj=bool(exclude_bj),
                    exclude_low_amount=bool(exclude_low_amount),
                    trend_up_only=bool(trend_up_only),
                )
                candidates.extend(index_candidates)
                scan_meta["index_scan"] = index_meta
                pool_meta = index_meta.get("pool") or {}
                cross_meta = index_meta.get("cross_section") or {}
                index_pool_count = pool_meta.get("filtered_count") or 0
                evaluable_count = index_meta.get("evaluable_count") or 0
                filter_count = index_meta.get("post_filter_count") or 0
                actual_refine_count = index_meta.get("refine_candidate_count") or len(index_candidates)
                source_notes.append(
                    f"{index_name}({index_code or '无代码'}) 指数成分 {index_pool_count} 只；"
                    f"横截面可评估 {evaluable_count} 只；"
                    f"进入精筛 {actual_refine_count} 只"
                )
                status_box.write(f"指数：{index_name}｜代码：{index_code or '待输入'}")
                status_box.write(f"指数成分原始返回：{pool_meta.get('raw_count') or 0} 行")
                status_box.write(f"最新成分日期：{pool_meta.get('latest_member_date') or '暂无'}")
                status_box.write(f"指数成分股：{index_pool_count} 只")
                status_box.write(f"横截面 daily 行数：{cross_meta.get('daily_rows') or 0}，取数模式：{cross_meta.get('daily_fetch_mode') or '未知'}")
                status_box.write(f"横截面可评估样本：{evaluable_count} 只")
                status_box.write(f"过滤后样本：{filter_count} 只")
                status_box.write(f"进入精筛候选：Top {refine_candidate_limit}；实际进入精筛：{actual_refine_count} 只")
                status_box.write(f"规则雷达展示：Top {display_limit}")
                if index_meta.get("degraded"):
                    degraded_message = index_meta.get("message") or "指数池已降级为科技股样本池"
                    status_box.write(f"指数精选池降级：{degraded_message}")
                    scan_errors.append(_scan_error("指数成分接口降级", degraded_message))
                else:
                    status_box.update(
                        label=(
                            f"指数成分获取完成：{index_name} {index_pool_count} 只，"
                            f"横截面可评估 {evaluable_count} 只；进入精筛 Top {refine_candidate_limit}。"
                        ),
                        state="running",
                    )
            if source_mode in {"A股主板广域扫描", "混合扫描"}:
                failed_stage = "A股主板横截面粗筛"
                status_box.update(label="正在进行 A股主板全量横截面粗筛……", state="running")
                broad_candidates, broad_meta = build_cross_section_rough_candidates(
                    callbacks,
                    refine_candidate_limit=int(refine_candidate_limit),
                    exclude_st=bool(exclude_st),
                    exclude_chinext=bool(exclude_chinext),
                    exclude_star=bool(exclude_star),
                    exclude_bj=bool(exclude_bj),
                    exclude_low_amount=bool(exclude_low_amount),
                    trend_up_only=bool(trend_up_only),
                )
                candidates.extend(broad_candidates)
                scan_meta["broad_scan"] = broad_meta
                source_notes.append(
                    f"A股主板全量横截面粗筛 {broad_meta.get('evaluable_count') or 0} 只；"
                    f"进入精筛候选上限 Top {refine_candidate_limit}；"
                    f"实际进入精筛 {broad_meta.get('refine_candidate_count') or len(broad_candidates)} 只"
                )
                pool_meta = broad_meta.get("pool") or {}
                cross_meta = broad_meta.get("cross_section") or {}
                full_pool_count = pool_meta.get("filtered_count") or 0
                evaluable_count = broad_meta.get("evaluable_count") or 0
                filter_count = broad_meta.get("post_filter_count") or 0
                actual_refine_count = broad_meta.get("refine_candidate_count") or len(broad_candidates)
                status_box.write(f"Tushare 股票基础池：{pool_meta.get('raw_count') or 0} 只")
                status_box.write(f"只保留上市状态 L 后：{pool_meta.get('listed_count') or pool_meta.get('raw_count') or 0} 只")
                status_box.write(f"排除 ST / 退市整理后：{pool_meta.get('after_st_exclusion_count') or pool_meta.get('listed_count') or 0} 只")
                status_box.write(f"排除创业板 / 科创板 / 北交所后：{pool_meta.get('after_board_exclusion_count') or 0} 只")
                status_box.write(f"A股主板全量候选池：{full_pool_count} 只")
                status_box.write(f"横截面 daily 行数：{cross_meta.get('daily_rows') or 0}，取数模式：{cross_meta.get('daily_fetch_mode') or '未知'}")
                status_box.write(f"横截面可评估样本：{evaluable_count} 只")
                status_box.write(f"排除低成交额后：{broad_meta.get('low_amount_pass_count') or 0} 只")
                status_box.write(f"只看趋势向上后：{broad_meta.get('trend_up_pass_count') or 0} 只")
                status_box.write(f"过滤后样本：{filter_count} 只")
                status_box.write(f"进入精筛候选：Top {refine_candidate_limit}；实际进入精筛：{actual_refine_count} 只")
                status_box.write(f"规则雷达展示：Top {display_limit}")
                if broad_meta.get("degraded"):
                    degraded_message = broad_meta.get("message") or "已降级为小样本扫描"
                    status_box.write(f"广域扫描降级：{degraded_message}")
                    scan_errors.append(_scan_error("横截面粗筛降级", degraded_message))
                else:
                    status_box.update(
                        label=(
                            f"全量横截面粗筛完成：A股主板 {full_pool_count} 只，可评估 {evaluable_count} 只；"
                            f"进入精筛 Top {refine_candidate_limit}。"
                        ),
                        state="running",
                    )
            failed_stage = "候选池补充"
            extra_candidates, extra_notes = gather_non_broad_candidates()
            candidates.extend(extra_candidates)
            source_notes.extend(extra_notes)
            candidates = _dedupe_candidates(candidates)

            if not candidates:
                finished_at = _now_iso()
                status_subject = _scan_status_subject(source_mode, scan_meta)
                status_box.update(
                    label=(
                        f"✅ {status_subject}，没有满足过滤条件的候选，"
                        f"展示规则雷达 Top {display_limit}。"
                    ),
                    state="complete",
                    expanded=False,
                )
                summary = _build_scan_summary(
                    source_mode=source_mode,
                    scan_strength=scan_strength,
                    refine_candidate_limit=int(refine_candidate_limit),
                    display_limit=int(display_limit),
                    scan_meta=scan_meta,
                    rule_rows=[],
                    started_at=started_at,
                    finished_at=finished_at,
                )
                scan_state = {
                    "params_hash": params_hash,
                    "params": scan_params,
                    "source_mode": source_mode,
                    "source_notes": source_notes,
                    "rule_rows": [],
                    "results": [],
                    "scan_meta": scan_meta,
                    "summary": summary,
                    "generated_at": finished_at,
                }
                _set_scan_state(
                    status=RADAR_SCAN_COMPLETED,
                    scan_state=scan_state,
                    summary=summary,
                    errors=scan_errors,
                    started_at=started_at,
                    finished_at=finished_at,
                )
            else:
                failed_stage = "Top N 精筛"
                status_box.update(
                    label=(
                        f"正在精筛 Top {refine_candidate_limit}：0/{len(candidates)}；"
                        f"最终展示规则雷达 Top {display_limit}。"
                    ),
                    state="running",
                )

                def progress_callback(index: int, total: int, candidate: dict[str, Any]) -> None:
                    ticker = candidate.get("ticker") or ""
                    name = candidate.get("name") or ""
                    status_box.update(
                        label=(
                            f"正在精筛 Top {refine_candidate_limit}：{index}/{total}，当前 {ticker} {name}；"
                            f"最终展示规则雷达 Top {display_limit}。"
                        ),
                        state="running",
                    )
                    progress.progress(index / max(total, 1))

                rule_rows = build_rule_radar(candidates, holding_context, callbacks, progress_callback=progress_callback)
                failed_stage = "规则雷达表生成"
                status_box.update(label=f"正在生成规则雷达 Top {display_limit}……", state="running")
                success_count = sum(1 for row in rule_rows if not row.get("error"))
                failed_count = len(rule_rows) - success_count
                for row in rule_rows:
                    if row.get("error"):
                        candidate = row.get("candidate") or {}
                        scan_errors.append(_scan_error("单票精筛", row.get("error"), candidate.get("ticker") or ""))
                status_box.write(f"精筛完成：成功 {success_count} 只，失败 {failed_count} 只。")
                status_subject = _scan_status_subject(source_mode, scan_meta)
                finished_at = _now_iso()
                summary = _build_scan_summary(
                    source_mode=source_mode,
                    scan_strength=scan_strength,
                    refine_candidate_limit=int(refine_candidate_limit),
                    display_limit=int(display_limit),
                    scan_meta=scan_meta,
                    rule_rows=rule_rows,
                    started_at=started_at,
                    finished_at=finished_at,
                )
                if success_count > 0 and failed_count > 0:
                    terminal_status = RADAR_SCAN_PARTIAL_FAILED
                    complete_label = (
                        f"⚠️ {status_subject}，"
                        f"精筛成功 {success_count} 只、失败 {failed_count} 只，展示规则雷达 Top {display_limit}。"
                    )
                    status_state = "complete"
                elif success_count == 0 and failed_count > 0:
                    terminal_status = RADAR_SCAN_FAILED
                    summary["failed_stage"] = "Top N 精筛"
                    summary["error_message"] = "全部候选精筛失败"
                    complete_label = "❌ 规则雷达扫描失败：全部候选精筛失败"
                    status_state = "error"
                else:
                    terminal_status = RADAR_SCAN_COMPLETED
                    complete_label = (
                        f"✅ {status_subject}，"
                        f"精筛 Top {refine_candidate_limit}，展示规则雷达 Top {display_limit}。"
                    )
                    status_state = "complete"
                status_box.update(label=complete_label, state=status_state, expanded=False)
                scan_state = {
                    "params_hash": params_hash,
                    "params": scan_params,
                    "source_mode": source_mode,
                    "source_notes": source_notes,
                    "rule_rows": sanitize_for_json(rule_rows),
                    "results": sanitize_for_json(rule_rows),
                    "scan_meta": scan_meta,
                    "summary": summary,
                    "generated_at": finished_at,
                }
                _set_scan_state(
                    status=terminal_status,
                    scan_state=scan_state,
                    summary=summary,
                    errors=scan_errors,
                    started_at=started_at,
                    finished_at=finished_at,
                )
        except Exception as exc:
            finished_at = _now_iso()
            scan_errors.append(_scan_error(failed_stage, exc))
            summary = _build_scan_summary(
                source_mode=source_mode,
                scan_strength=scan_strength,
                refine_candidate_limit=int(refine_candidate_limit),
                display_limit=int(display_limit),
                scan_meta=scan_meta,
                rule_rows=rule_rows,
                started_at=started_at,
                finished_at=finished_at,
                failed_stage=failed_stage,
                error_message=str(exc),
            )
            scan_state = {
                "params_hash": params_hash,
                "params": scan_params,
                "source_mode": source_mode,
                "source_notes": source_notes,
                "rule_rows": sanitize_for_json(rule_rows),
                "results": sanitize_for_json(rule_rows),
                "scan_meta": scan_meta,
                "summary": summary,
                "generated_at": finished_at,
            }
            _set_scan_state(
                status=RADAR_SCAN_FAILED,
                scan_state=scan_state,
                summary=summary,
                errors=scan_errors,
                started_at=started_at,
                finished_at=finished_at,
            )
            status_box.update(label=f"❌ 规则雷达扫描失败：{failed_stage}", state="error", expanded=True)

    scan_state = st.session_state.get(RADAR_SCAN_STATE_KEY) or {}
    rule_rows = scan_state.get("rule_rows") or []
    if rule_rows and st.session_state.get("next_ticket_run_deep"):
        _mark_scan_deepseek_called(int(st.session_state.get("next_ticket_top_n") or 5))
    _render_scan_result_panel()
    scan_status = st.session_state.get(RADAR_SCAN_STATUS_KEY) or RADAR_SCAN_IDLE
    if not rule_rows:
        if scan_status in {RADAR_SCAN_COMPLETED, RADAR_SCAN_PARTIAL_FAILED}:
            st.info(
                "本次扫描没有满足过滤条件的候选。可以尝试：\n"
                "1. 取消只看趋势向上\n"
                "2. 放宽低成交额过滤\n"
                "3. 提高进入精筛候选上限\n"
                "4. 改用混合扫描"
            )
        elif scan_status == RADAR_SCAN_FAILED:
            st.info("本次扫描未生成可展示的规则雷达表，请根据上方失败信息调整后重新扫描。")
        elif scan_status == RADAR_SCAN_RUNNING:
            st.info("上次扫描可能被中断，请点击重新扫描。")
        else:
            st.info("尚未扫描。规则雷达不会在页面加载时自动执行，请点击扫描按钮。")
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
    if (scan_meta.get("index_scan") or {}).get("degraded"):
        st.warning((scan_meta.get("index_scan") or {}).get("message") or "指数成分接口不可用，已降级为科技股样本池。")
    with st.expander("扫描横截面信息", expanded=False):
        st.json(scan_meta or {"message": "非广域扫描或暂无横截面元数据"})

    st.markdown("#### 规则雷达表")
    radar_df = _radar_dataframe(rule_rows[: int(display_limit)])
    st.dataframe(
        radar_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "股票": st.column_config.TextColumn("股票", width="medium"),
            "搞不搞": st.column_config.TextColumn("搞不搞", width="small"),
            "状态理由": st.column_config.TextColumn("状态理由", width="large"),
            "与当前持仓关系": st.column_config.TextColumn("与当前持仓关系", width="medium"),
            "触发条件": st.column_config.TextColumn("触发条件", width="large"),
            "失效条件": st.column_config.TextColumn("失效条件", width="large"),
            "数据缺口": st.column_config.TextColumn("数据缺口", width="medium"),
            "来源指数": st.column_config.TextColumn("来源指数", width="small"),
            "指数权重": st.column_config.NumberColumn("指数权重", width="small", format="%.3f"),
        },
    )

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

    _mark_scan_deepseek_called(int(top_n))
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
