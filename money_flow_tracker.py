import concurrent.futures
import datetime
import json
import math

import pandas as pd
import yfinance as yf


QUICK_TIMEOUT_SECONDS = 10
DEEP_TIMEOUT_SECONDS = 15


def _now_iso():
    return datetime.datetime.utcnow().isoformat()


def _default_source_status(source, timeout_seconds):
    return {
        "source": source,
        "ok": False,
        "used": False,
        "timed_out": False,
        "timeout_seconds": timeout_seconds,
        "error": "",
    }


def _run_with_timeout(label, func, timeout_seconds):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="moneyflow")
    future = executor.submit(func)
    try:
        data = future.result(timeout=timeout_seconds)
        return {
            "ok": True,
            "data": data,
            "error": "",
            "timed_out": False,
            "timeout_seconds": timeout_seconds,
            "label": label,
        }
    except concurrent.futures.TimeoutError:
        future.cancel()
        return {
            "ok": False,
            "data": None,
            "error": f"{label} 超时（>{timeout_seconds}s）",
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "label": label,
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": f"{label} 失败：{exc}",
            "timed_out": False,
            "timeout_seconds": timeout_seconds,
            "label": label,
        }
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _finalize_flow_result(result):
    result["updated_at"] = _now_iso()
    result["available"] = bool(
        result.get("individual_fund_flow")
        or result.get("dragon_tiger")
        or result.get("block_trade")
        or result.get("institutional_holders")
        or result.get("insider_transactions")
        or result.get("options_signal")
        or result.get("etf_proxy_flow")
        or result.get("volume_signal")
    )
    result["partial"] = bool(result.get("errors"))
    result["coverage"] = money_flow_coverage(result)
    result["summary"] = summarize_money_flow(result)
    return result


def ticker_plain(ticker):
    ticker = (ticker or "").upper().strip()
    return ticker.replace(".SZ", "").replace(".SS", "").replace(".HK", "")


def infer_market_type(ticker):
    ticker = (ticker or "").upper().strip()
    if ticker.endswith(".SZ") or ticker.endswith(".SS"):
        return "A_SHARE"
    if ticker.endswith(".HK"):
        return "HK_STOCK"
    return "US_STOCK"


def json_safe(value):
    if value is None:
        return ""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, float):
        return "" if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    if hasattr(value, "item"):
        try:
            return json_safe(value.item())
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def frame_records(df, limit=8):
    if df is None or df.empty:
        return []
    return json_safe(df.head(limit).where(pd.notna(df), "").to_dict("records"))


def collect_money_flow_snapshot(ticker, market_type=None, deep=False):
    market_type = market_type or infer_market_type(ticker)
    if market_type in ["A_SHARE_SH", "A_SHARE_SZ", "A_SHARE"]:
        return collect_a_share_money_flow(ticker, deep=deep)
    if market_type == "HK_STOCK":
        return collect_hk_money_flow(ticker)
    return collect_us_money_flow(ticker)


def collect_us_money_flow(ticker):
    result = {
        "ticker": ticker,
        "market_type": "US_STOCK",
        "data_time": _now_iso(),
        "updated_at": _now_iso(),
        "institutional_holders": [],
        "insider_transactions": [],
        "options_signal": {},
        "etf_proxy_flow": [],
        "warnings": [],
        "errors": [],
        "source_status": {},
        "available": False,
        "partial": False,
    }

    stock = yf.Ticker(ticker)

    try:
        holders = stock.institutional_holders
        if holders is not None and not holders.empty:
            result["institutional_holders"] = frame_records(holders, 8)
        else:
            result["warnings"].append("13F/institutional_holders empty from public source")
    except Exception as e:
        result["errors"].append(f"13F/institutional_holders unavailable: {e}")
        result["warnings"].append(f"13F/institutional_holders unavailable: {e}")

    try:
        insiders = stock.insider_transactions
        if insiders is not None and not insiders.empty:
            result["insider_transactions"] = frame_records(insiders, 8)
        else:
            result["warnings"].append("insider_transactions empty from public source")
    except Exception as e:
        result["errors"].append(f"insider_transactions unavailable: {e}")
        result["warnings"].append(f"insider_transactions unavailable: {e}")

    try:
        expirations = stock.options
        if expirations:
            option_chain = stock.option_chain(expirations[0])
            calls = option_chain.calls
            puts = option_chain.puts
            call_volume = int(calls["volume"].fillna(0).sum()) if not calls.empty else 0
            put_volume = int(puts["volume"].fillna(0).sum()) if not puts.empty else 0
            call_oi = int(calls["openInterest"].fillna(0).sum()) if not calls.empty else 0
            put_oi = int(puts["openInterest"].fillna(0).sum()) if not puts.empty else 0
            result["options_signal"] = {
                "expiry": expirations[0],
                "call_volume": call_volume,
                "put_volume": put_volume,
                "call_put_volume_ratio": round(call_volume / max(put_volume, 1), 2),
                "call_open_interest": call_oi,
                "put_open_interest": put_oi,
                "call_put_oi_ratio": round(call_oi / max(put_oi, 1), 2),
                "top_call_strikes": _top_strikes(calls),
                "top_put_strikes": _top_strikes(puts),
            }
        else:
            result["warnings"].append("options chain empty from public source")
    except Exception as e:
        result["errors"].append(f"options unavailable: {e}")
        result["warnings"].append(f"options unavailable: {e}")

    result["etf_proxy_flow"] = collect_us_etf_proxy_flow(ticker)
    return _finalize_flow_result(result)


def collect_us_etf_proxy_flow(ticker):
    proxies = ["QQQ", "XLK", "SMH", "SOXX"]
    rows = []
    for proxy in proxies:
        try:
            hist = yf.Ticker(proxy).history(period="2mo")
            if hist is None or hist.empty or len(hist) < 22:
                continue
            close = hist["Close"].dropna()
            volume = hist["Volume"].fillna(0)
            rows.append({
                "proxy": proxy,
                "role": {
                    "QQQ": "纳指风险偏好",
                    "XLK": "大型科技ETF",
                    "SMH": "半导体ETF",
                    "SOXX": "半导体ETF",
                }.get(proxy, "ETF proxy"),
                "return_5d_pct": round(float((close.iloc[-1] / close.iloc[-6] - 1) * 100), 2) if len(close) >= 6 else "",
                "return_20d_pct": round(float((close.iloc[-1] / close.iloc[-21] - 1) * 100), 2) if len(close) >= 21 else "",
                "volume_vs_20d": round(float(volume.iloc[-1] / max(volume.tail(20).mean(), 1)), 2) if len(volume) >= 20 else "",
                "data_asof": str(close.index[-1].date()),
            })
        except Exception:
            continue
    return rows


def _filter_code_frame(df, code):
    if df is None or df.empty:
        return df
    code = str(code).zfill(6)
    code_cols = [
        col for col in df.columns
        if any(word in str(col) for word in ["代码", "股票代码", "证券代码", "code", "Code", "symbol"])
    ]
    for col in code_cols:
        try:
            extracted = df[col].astype(str).str.extract(r"(\d{6})", expand=False).fillna("")
            mask = extracted == code
            if mask.any():
                return df[mask]
        except Exception:
            continue
    return df


def collect_a_share_money_flow(ticker, deep=False):
    result = {
        "ticker": ticker,
        "market_type": "A_SHARE",
        "data_time": _now_iso(),
        "updated_at": _now_iso(),
        "mode": "deep" if deep else "quick",
        "individual_fund_flow": [],
        "dragon_tiger": [],
        "block_trade": [],
        "warnings": [],
        "errors": [],
        "source_status": {
            "individual_fund_flow_primary": _default_source_status("ak.stock_individual_fund_flow", QUICK_TIMEOUT_SECONDS),
            "individual_fund_flow_fallback": _default_source_status("ak.stock_fund_flow_individual", QUICK_TIMEOUT_SECONDS),
            "dragon_tiger": _default_source_status("ak.stock_lhb_detail_em", DEEP_TIMEOUT_SECONDS),
            "block_trade": _default_source_status("ak.stock_dzjy_mrmx", DEEP_TIMEOUT_SECONDS),
        },
        "available": False,
        "partial": False,
    }

    code = ticker_plain(ticker)

    primary_result = _run_with_timeout(
        "AkShare 个股资金流主接口",
        lambda: _collect_a_share_fund_flow_primary(code, ticker),
        QUICK_TIMEOUT_SECONDS,
    )
    primary_status = result["source_status"]["individual_fund_flow_primary"]
    primary_status["used"] = True
    primary_status["ok"] = primary_result["ok"]
    primary_status["timed_out"] = primary_result["timed_out"]
    primary_status["error"] = primary_result["error"]

    if primary_result["ok"]:
        result["individual_fund_flow"] = primary_result["data"] or []
    else:
        result["errors"].append(primary_result["error"])
        fallback_result = _run_with_timeout(
            "AkShare 个股资金流回退接口",
            lambda: _collect_a_share_fund_flow_fallback(code),
            QUICK_TIMEOUT_SECONDS,
        )
        fallback_status = result["source_status"]["individual_fund_flow_fallback"]
        fallback_status["used"] = True
        fallback_status["ok"] = fallback_result["ok"]
        fallback_status["timed_out"] = fallback_result["timed_out"]
        fallback_status["error"] = fallback_result["error"]
        if fallback_result["ok"]:
            result["individual_fund_flow"] = fallback_result["data"] or []
            result["warnings"].append("AkShare 个股资金流主接口失败，已回退到备用接口。")
        else:
            result["errors"].append(fallback_result["error"])
            result["warnings"].append("AkShare 个股资金流暂不可用，已跳过该补充数据源。")

    if not deep:
        result["warnings"].append("快速资金模式：未自动运行完整龙虎榜/大宗交易扫描。")
        return _finalize_flow_result(result)

    dragon_result = _run_with_timeout(
        "AkShare 龙虎榜接口",
        lambda: _collect_a_share_dragon_tiger(code),
        DEEP_TIMEOUT_SECONDS,
    )
    dragon_status = result["source_status"]["dragon_tiger"]
    dragon_status["used"] = True
    dragon_status["ok"] = dragon_result["ok"]
    dragon_status["timed_out"] = dragon_result["timed_out"]
    dragon_status["error"] = dragon_result["error"]
    if dragon_result["ok"]:
        result["dragon_tiger"] = dragon_result["data"] or []
    else:
        result["errors"].append(dragon_result["error"])
        result["warnings"].append("AkShare 龙虎榜补充暂不可用。")

    block_result = _run_with_timeout(
        "AkShare 大宗交易接口",
        lambda: _collect_a_share_block_trade(code),
        DEEP_TIMEOUT_SECONDS,
    )
    block_status = result["source_status"]["block_trade"]
    block_status["used"] = True
    block_status["ok"] = block_result["ok"]
    block_status["timed_out"] = block_result["timed_out"]
    block_status["error"] = block_result["error"]
    if block_result["ok"]:
        result["block_trade"] = block_result["data"] or []
    else:
        result["errors"].append(block_result["error"])
        result["warnings"].append("AkShare 大宗交易补充暂不可用。")

    return _finalize_flow_result(result)


def collect_hk_money_flow(ticker):
    result = {
        "ticker": ticker,
        "market_type": "HK_STOCK",
        "data_time": _now_iso(),
        "updated_at": _now_iso(),
        "volume_signal": {},
        "warnings": [],
        "errors": [],
        "source_status": {},
        "available": False,
        "partial": False,
    }
    try:
        hist = yf.Ticker(ticker).history(period="3mo")
        if hist is not None and not hist.empty and "Volume" in hist.columns:
            latest_volume = float(hist["Volume"].iloc[-1])
            avg20 = float(hist["Volume"].tail(20).mean())
            result["volume_signal"] = {
                "latest_volume": latest_volume,
                "volume_vs_20d": round(latest_volume / max(avg20, 1), 2),
            }
    except Exception as e:
        result["errors"].append(f"hk volume unavailable: {e}")
        result["warnings"].append(f"hk volume unavailable: {e}")
    return _finalize_flow_result(result)


def _collect_a_share_fund_flow_primary(code, ticker):
    import akshare as ak

    flow_df = ak.stock_individual_fund_flow(
        stock=code,
        market="sh" if str(ticker).upper().endswith(".SS") else "sz",
    )
    flow_df = _filter_code_frame(flow_df, code)
    return frame_records(flow_df, 8)


def _collect_a_share_fund_flow_fallback(code):
    import akshare as ak

    try:
        flow_df = ak.stock_fund_flow_individual(symbol=code)
    except TypeError:
        flow_df = ak.stock_fund_flow_individual(indicator="即时")
    flow_df = _filter_code_frame(flow_df, code)
    return frame_records(flow_df, 8)


def _collect_a_share_dragon_tiger(code):
    import akshare as ak

    today = datetime.datetime.now().strftime("%Y%m%d")
    lhb_df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
    if lhb_df is not None and not lhb_df.empty:
        lhb_df = _filter_code_frame(lhb_df, code)
    return frame_records(lhb_df, 8)


def _collect_a_share_block_trade(code):
    import akshare as ak

    block_df = ak.stock_dzjy_mrmx(symbol=datetime.datetime.now().strftime("%Y%m%d"))
    if block_df is not None and not block_df.empty:
        block_df = _filter_code_frame(block_df, code)
    return frame_records(block_df, 8)


def summarize_money_flow(flow):
    positives = []
    negatives = []

    options = flow.get("options_signal") or {}
    if options.get("call_put_volume_ratio", 1) >= 1.8:
        positives.append("期权Call活跃度明显高于Put")
    if options.get("call_put_volume_ratio", 1) <= 0.7:
        negatives.append("期权Put活跃度偏高")

    if flow.get("insider_transactions"):
        text = json.dumps(json_safe(flow.get("insider_transactions", [])[:5]), ensure_ascii=False).lower()
        if "sale" in text or "sell" in text or "出售" in text:
            negatives.append("近期存在内部人卖出线索")
        if "purchase" in text or "buy" in text or "买入" in text:
            positives.append("近期存在内部人买入线索")

    if flow.get("dragon_tiger"):
        positives.append("出现龙虎榜数据，需进一步识别机构/游资席位")
    if flow.get("block_trade"):
        negatives.append("出现大宗交易数据，需检查折溢价和交易对手")

    volume_signal = flow.get("volume_signal") or {}
    if volume_signal.get("volume_vs_20d", 1) >= 2:
        positives.append("成交量显著放大")

    for row in flow.get("etf_proxy_flow", [])[:4]:
        role = row.get("role", row.get("proxy", "ETF"))
        ret_5d = row.get("return_5d_pct")
        volume_ratio = row.get("volume_vs_20d")
        try:
            if ret_5d != "" and float(ret_5d) >= 3 and volume_ratio != "" and float(volume_ratio) >= 1.2:
                positives.append(f"{role} 5日放量走强")
            if ret_5d != "" and float(ret_5d) <= -3 and volume_ratio != "" and float(volume_ratio) >= 1.2:
                negatives.append(f"{role} 5日放量走弱")
        except Exception:
            pass

    if flow.get("warnings") and not positives and not negatives:
        negatives.append("资金面公开接口不完整，需人工复核")

    return {
        "positive": positives,
        "negative": negatives,
        "stance": "偏多" if len(positives) > len(negatives) else ("偏空/谨慎" if negatives else "中性"),
    }


def money_flow_coverage(flow):
    market_type = flow.get("market_type")
    if market_type == "A_SHARE":
        checks = {
            "individual_fund_flow": bool(flow.get("individual_fund_flow")),
            "dragon_tiger": bool(flow.get("dragon_tiger")),
            "block_trade": bool(flow.get("block_trade")),
        }
    elif market_type == "HK_STOCK":
        checks = {
            "volume_signal": bool(flow.get("volume_signal")),
        }
    else:
        checks = {
            "institutional_holders": bool(flow.get("institutional_holders")),
            "insider_transactions": bool(flow.get("insider_transactions")),
            "options_signal": bool(flow.get("options_signal")),
            "etf_proxy_flow": bool(flow.get("etf_proxy_flow")),
        }
    available = sum(1 for ok in checks.values() if ok)
    missing = [key for key, ok in checks.items() if not ok]
    return {
        "score": int(available / max(len(checks), 1) * 100),
        "available": [key for key, ok in checks.items() if ok],
        "missing": missing,
    }


def _top_strikes(df):
    if df is None or df.empty or "openInterest" not in df.columns:
        return []
    cols = [c for c in ["strike", "lastPrice", "volume", "openInterest", "impliedVolatility"] if c in df.columns]
    return frame_records(df.sort_values("openInterest", ascending=False)[cols], 5)


def money_flow_text(flow):
    return json.dumps(json_safe(flow), ensure_ascii=False, default=str)[:6000]
