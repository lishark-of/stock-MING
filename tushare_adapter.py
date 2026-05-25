import datetime

try:
    from config import get_tushare_token
except Exception:  # pragma: no cover - keep adapter importable in minimal scripts.
    get_tushare_token = None

try:
    import pandas as pd
except Exception:  # pragma: no cover - pandas is a project dependency.
    pd = None


SOURCE_NAME = "Tushare"

CAPITAL_EVIDENCE_POLICY = {
    "rules": [
        "没有真实龙虎榜数据，不得编造席位。",
        "没有最新基金持仓/股东数据，不得点名具体基金经理。",
        "没有北向/深股通数据，不得声称外资加仓。",
        "投喂资料观点必须标记为历史假设/待验证。",
        "资金推断必须分为“已验证数据 / 谨慎推断 / 观察清单”。",
    ]
}


_PRO_CLIENT = None
_INIT_ERROR = None


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _result(api, ok=False, data=None, error=None):
    return {
        "ok": bool(ok),
        "data": data if ok else None,
        "source": SOURCE_NAME,
        "api": api,
        "updated_at": _now(),
        "error": None if ok else str(error or "unknown error"),
    }


def _normalize_date(value):
    if value is None:
        return None
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    if not text:
        return None
    return text.replace("-", "")


def _normalize_ts_code(ts_code):
    text = (ts_code or "").strip().upper()
    if not text:
        return text
    if text.endswith(".SS"):
        return text[:-3] + ".SH"
    if text.endswith(".SH") or text.endswith(".SZ") or text.endswith(".BJ"):
        return text
    if text.isdigit() and len(text) == 6:
        if text.startswith("6"):
            return f"{text}.SH"
        if text.startswith(("0", "3")):
            return f"{text}.SZ"
        if text.startswith(("4", "8")):
            return f"{text}.BJ"
    return text


def _get_pro_client():
    global _PRO_CLIENT, _INIT_ERROR

    if _PRO_CLIENT is not None:
        return _PRO_CLIENT, None
    if _INIT_ERROR:
        return None, _INIT_ERROR

    token = get_tushare_token() if get_tushare_token is not None else ""
    if not token:
        _INIT_ERROR = "缺少 TUSHARE_TOKEN 配置"
        return None, _INIT_ERROR

    try:
        import tushare as ts

        _PRO_CLIENT = ts.pro_api(token)
        return _PRO_CLIENT, None
    except Exception as exc:
        _INIT_ERROR = f"初始化 Tushare pro_api 失败：{exc}"
        return None, _INIT_ERROR


def _call_pro(api, **params):
    pro, error = _get_pro_client()
    if error:
        return _result(api, error=error)

    cleaned = {key: value for key, value in params.items() if value is not None}
    try:
        method = getattr(pro, api)
    except AttributeError:
        return _result(api, error=f"Tushare pro_api 不支持接口：{api}")

    try:
        data = method(**cleaned)
        if pd is not None and not isinstance(data, pd.DataFrame):
            return _result(api, error=f"{api} 返回类型异常：{type(data).__name__}")
        return _result(api, ok=True, data=data)
    except Exception as exc:
        return _result(api, error=f"{api} 调用失败，可能是接口权限不足、网络失败或参数错误：{exc}")


def get_trade_cal(start_date, end_date, exchange=""):
    return _call_pro(
        "trade_cal",
        exchange=exchange or "",
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_stock_basic(exchange="", list_status="L"):
    return _call_pro(
        "stock_basic",
        exchange=exchange or "",
        list_status=list_status or "L",
    )


def get_index_weight(index_code=None, trade_date=None, start_date=None, end_date=None):
    return _call_pro(
        "index_weight",
        index_code=(index_code or "").strip().upper(),
        trade_date=_normalize_date(trade_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_daily(ts_code, start_date=None, end_date=None):
    return _call_pro(
        "daily",
        ts_code=_normalize_ts_code(ts_code),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_daily_basic(ts_code, start_date=None, end_date=None):
    return _call_pro(
        "daily_basic",
        ts_code=_normalize_ts_code(ts_code),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_adj_factor(ts_code, start_date=None, end_date=None):
    return _call_pro(
        "adj_factor",
        ts_code=_normalize_ts_code(ts_code),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_top_list(trade_date=None, ts_code=None):
    return _call_pro(
        "top_list",
        trade_date=_normalize_date(trade_date),
        ts_code=_normalize_ts_code(ts_code),
    )


def get_top_inst(trade_date=None, ts_code=None):
    return _call_pro(
        "top_inst",
        trade_date=_normalize_date(trade_date),
        ts_code=_normalize_ts_code(ts_code),
    )


def get_margin_detail(trade_date=None, ts_code=None, start_date=None, end_date=None):
    return _call_pro(
        "margin_detail",
        trade_date=_normalize_date(trade_date),
        ts_code=_normalize_ts_code(ts_code),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_moneyflow(ts_code=None, trade_date=None, start_date=None, end_date=None):
    return _call_pro(
        "moneyflow",
        ts_code=_normalize_ts_code(ts_code),
        trade_date=_normalize_date(trade_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_stk_limit(ts_code=None, trade_date=None, start_date=None, end_date=None):
    return _call_pro(
        "stk_limit",
        ts_code=_normalize_ts_code(ts_code),
        trade_date=_normalize_date(trade_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_limit_list_d(ts_code=None, trade_date=None, start_date=None, end_date=None, limit_type=None):
    return _call_pro(
        "limit_list_d",
        ts_code=_normalize_ts_code(ts_code),
        trade_date=_normalize_date(trade_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
        limit_type=limit_type,
    )


def get_limit_cpt_list(trade_date=None, start_date=None, end_date=None):
    return _call_pro(
        "limit_cpt_list",
        trade_date=_normalize_date(trade_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_cyq_perf(ts_code=None, trade_date=None, start_date=None, end_date=None):
    return _call_pro(
        "cyq_perf",
        ts_code=_normalize_ts_code(ts_code),
        trade_date=_normalize_date(trade_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_cyq_chips(ts_code=None, trade_date=None, start_date=None, end_date=None):
    return _call_pro(
        "cyq_chips",
        ts_code=_normalize_ts_code(ts_code),
        trade_date=_normalize_date(trade_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_hk_hold(ts_code=None, trade_date=None, start_date=None, end_date=None, exchange=None):
    return _call_pro(
        "hk_hold",
        ts_code=_normalize_ts_code(ts_code),
        trade_date=_normalize_date(trade_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
        exchange=exchange,
    )


def get_anns_d(ts_code=None, ann_date=None, start_date=None, end_date=None):
    return _call_pro(
        "anns_d",
        ts_code=_normalize_ts_code(ts_code),
        ann_date=_normalize_date(ann_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_forecast(ts_code=None, ann_date=None, start_date=None, end_date=None, period=None):
    return _call_pro(
        "forecast",
        ts_code=_normalize_ts_code(ts_code),
        ann_date=_normalize_date(ann_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
        period=_normalize_date(period),
    )


def get_stk_holdertrade(
    ts_code=None,
    ann_date=None,
    start_date=None,
    end_date=None,
    trade_type=None,
    holder_type=None,
):
    return _call_pro(
        "stk_holdertrade",
        ts_code=_normalize_ts_code(ts_code),
        ann_date=_normalize_date(ann_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
        trade_type=trade_type,
        holder_type=holder_type,
    )


def get_share_float(ts_code=None, ann_date=None, float_date=None, start_date=None, end_date=None):
    return _call_pro(
        "share_float",
        ts_code=_normalize_ts_code(ts_code),
        ann_date=_normalize_date(ann_date),
        float_date=_normalize_date(float_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def get_pledge_stat(ts_code=None, end_date=None):
    return _call_pro(
        "pledge_stat",
        ts_code=_normalize_ts_code(ts_code),
        end_date=_normalize_date(end_date),
    )


def get_pledge_detail(ts_code=None):
    return _call_pro(
        "pledge_detail",
        ts_code=_normalize_ts_code(ts_code),
    )


def get_stk_surv(ts_code=None, trade_date=None, start_date=None, end_date=None):
    return _call_pro(
        "stk_surv",
        ts_code=_normalize_ts_code(ts_code),
        trade_date=_normalize_date(trade_date),
        start_date=_normalize_date(start_date),
        end_date=_normalize_date(end_date),
    )


def _payload_from_result(result, api, ts_code=None):
    data = result.get("data")
    rows = []
    latest = {}
    if result.get("ok") and data is not None and not data.empty:
        rows = data.head(8).where(data.notna(), None).to_dict("records")
        latest = rows[0] if rows else {}

    return {
        "source": SOURCE_NAME,
        "api": api,
        "source_available": result.get("ok", False),
        "verified": bool(rows),
        "ticker": ts_code,
        "rows": rows,
        "latest_date": latest.get("trade_date", ""),
        "error": result.get("error") or "",
        "data_quality": 80 if rows else 0,
        "stale": not bool(rows),
    }


def collect_verified_capital_evidence(ticker, market_type=None):
    """Compatibility layer for app.py; keeps all failures data-shaped."""

    ts_code = _normalize_ts_code(ticker)
    daily_basic_result = get_daily_basic(ts_code)
    daily_basic_payload = _payload_from_result(daily_basic_result, "daily_basic", ts_code=ts_code)

    latest = daily_basic_payload["rows"][0] if daily_basic_payload["rows"] else {}
    daily_basic_payload.update(
        {
            "turnover_rate": latest.get("turnover_rate"),
            "volume_ratio": latest.get("volume_ratio"),
            "pe": latest.get("pe"),
            "pb": latest.get("pb"),
            "total_mv": latest.get("total_mv"),
        }
    )

    unavailable_error = daily_basic_result.get("error") or "最小 Tushare 适配层暂未接入该接口"
    unavailable = {
        "source": SOURCE_NAME,
        "source_available": False,
        "verified": False,
        "ticker": ts_code,
        "rows": [],
        "error": unavailable_error,
        "data_quality": 0,
        "stale": True,
    }

    verified_data = {
        "tushare_moneyflow": dict(unavailable),
        "daily_basic": daily_basic_payload,
        "lhb": dict(unavailable),
        "hsgt": dict(unavailable),
        "margin": dict(unavailable),
        "block_trade": dict(unavailable),
    }

    return {
        "source": "tushare_adapter",
        "capital_evidence_policy": CAPITAL_EVIDENCE_POLICY,
        "verified_data": verified_data,
        "cautious_inference_inputs": {
            "turnover": daily_basic_payload.get("turnover_rate"),
            "price_volume": None,
            "recent_return": None,
        },
        "missing_data": [
            name
            for name, payload in verified_data.items()
            if not payload.get("verified") and not payload.get("rows")
        ],
    }
