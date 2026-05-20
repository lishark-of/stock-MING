import datetime
import re
from functools import lru_cache
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import yfinance as yf


SUPPLY_CHAIN_MAP = {
    "NVDA": {
        "name": "Nvidia",
        "aliases": ["NVDA", "Nvidia", "英伟达"],
        "theme": "AI算力/数据中心",
        "position": "GPU核心算力平台",
        "upstream": ["HBM", "先进封装", "晶圆代工", "高端PCB"],
        "core_modules": ["GPU", "AI服务器", "高速互联", "液冷散热"],
        "downstream": ["云厂商资本开支", "大模型训练", "企业AI应用"],
        "a_share_links": [
            {"ticker": "601138.SS", "name": "工业富联", "role": "AI服务器/代工"},
            {"ticker": "300308.SZ", "name": "中际旭创", "role": "光模块"},
            {"ticker": "300502.SZ", "name": "新易盛", "role": "光模块"},
            {"ticker": "300394.SZ", "name": "天孚通信", "role": "光器件"},
            {"ticker": "002463.SZ", "name": "沪电股份", "role": "高速PCB"},
            {"ticker": "300476.SZ", "name": "胜宏科技", "role": "PCB"},
            {"ticker": "688256.SS", "name": "寒武纪", "role": "国产AI芯片映射"},
        ],
        "risk_transmission": "NVDA业绩/指引/订单若低于预期，A股CPO、PCB、AI服务器映射票容易同步降风险偏好。",
    },
    "TSM": {
        "name": "TSMC",
        "aliases": ["TSM", "TSMC", "台积电"],
        "theme": "半导体制造",
        "position": "先进制程晶圆代工核心",
        "upstream": ["半导体设备", "材料", "EDA/IP"],
        "core_modules": ["先进制程", "CoWoS封装", "晶圆产能"],
        "downstream": ["AI芯片", "手机SoC", "汽车芯片"],
        "a_share_links": [
            {"ticker": "688012.SS", "name": "中微公司", "role": "半导体设备"},
            {"ticker": "688072.SS", "name": "拓荆科技", "role": "薄膜沉积设备"},
            {"ticker": "688126.SS", "name": "沪硅产业", "role": "硅片"},
            {"ticker": "002371.SZ", "name": "北方华创", "role": "半导体设备"},
        ],
        "risk_transmission": "先进制程资本开支变化会传导到设备、材料、封装和AI芯片链。",
    },
    "INTC": {
        "name": "Intel",
        "aliases": ["INTC", "Intel", "英特尔"],
        "theme": "半导体/晶圆制造/PC与服务器CPU",
        "position": "IDM制造与CPU平台，兼具先进制程追赶和代工转型逻辑",
        "upstream": ["半导体设备", "先进封装", "EDA/IP", "晶圆材料"],
        "core_modules": ["CPU", "数据中心芯片", "晶圆制造", "Foundry代工"],
        "downstream": ["PC换机周期", "服务器资本开支", "AI PC", "美国半导体政策"],
        "a_share_links": [
            {"ticker": "688012.SS", "name": "中微公司", "role": "半导体设备映射"},
            {"ticker": "002371.SZ", "name": "北方华创", "role": "半导体设备映射"},
            {"ticker": "688126.SS", "name": "沪硅产业", "role": "硅片材料映射"},
            {"ticker": "688256.SS", "name": "寒武纪", "role": "AI芯片估值映射"},
        ],
        "risk_transmission": "INTC重点看数据中心份额、制程追赶、Foundry资本开支和毛利率修复；若指引下修，会压制半导体设备与AI芯片链风险偏好。",
    },
    "LITE": {
        "name": "Lumentum",
        "aliases": ["LITE", "Lumentum", "Lumentum Holdings"],
        "theme": "光通信/激光器/光学元件",
        "position": "光通信器件与商用激光供应商",
        "upstream": ["光学材料", "半导体激光器", "精密制造"],
        "core_modules": ["光通信器件", "激光器", "数据中心光学需求"],
        "downstream": ["云数据中心", "通信设备商", "工业激光应用"],
        "a_share_links": [],
        "risk_transmission": "LITE重点看云数据中心光器件需求、通信设备资本开支和激光业务周期。",
    },
    "601138.SS": {
        "name": "工业富联",
        "theme": "AI服务器",
        "position": "AI服务器制造/数据中心硬件",
        "upstream": ["GPU", "PCB", "连接器", "电源", "散热"],
        "core_modules": ["AI服务器整机", "云厂商订单", "数据中心交付"],
        "downstream": ["互联网云", "海外AI算力", "企业AI"],
        "a_share_links": [
            {"ticker": "NVDA", "name": "Nvidia", "role": "上游GPU风向"},
            {"ticker": "002463.SZ", "name": "沪电股份", "role": "PCB"},
            {"ticker": "300308.SZ", "name": "中际旭创", "role": "光模块"},
            {"ticker": "300502.SZ", "name": "新易盛", "role": "光模块"},
        ],
        "risk_transmission": "核心看海外AI服务器订单和NVDA链景气度，若上游指引走弱，估值容易回撤。",
    },
    "002008.SZ": {
        "name": "大族激光",
        "theme": "激光设备/制造业自动化",
        "position": "中游设备供应商",
        "upstream": ["激光器", "控制系统", "光学元件"],
        "core_modules": ["消费电子设备", "PCB设备", "新能源设备", "通用激光设备"],
        "downstream": ["消费电子资本开支", "PCB扩产", "新能源制造"],
        "a_share_links": [
            {"ticker": "002475.SZ", "name": "立讯精密", "role": "消费电子需求映射"},
            {"ticker": "002463.SZ", "name": "沪电股份", "role": "PCB景气映射"},
            {"ticker": "300476.SZ", "name": "胜宏科技", "role": "PCB景气映射"},
        ],
        "risk_transmission": "更受制造业资本开支和下游扩产周期影响，若订单确认慢，股价容易走震荡折返。",
    },
    "0700.HK": {
        "name": "腾讯控股",
        "aliases": ["0700.HK", "0700", "腾讯控股", "Tencent", "TCEHY"],
        "theme": "港股互联网/游戏/广告/金融科技",
        "position": "中国互联网平台核心资产，兼具游戏现金流、广告修复、回购和AI应用映射",
        "upstream": ["云计算基础设施", "AI模型与算力", "内容/IP", "支付清算网络"],
        "core_modules": ["游戏流水", "广告加载率", "视频号商业化", "金融科技", "回购强度"],
        "downstream": ["消费复苏", "游戏版号", "港股流动性", "南向资金"],
        "a_share_links": [
            {"ticker": "300413.SZ", "name": "芒果超媒", "role": "内容/广告情绪映射"},
            {"ticker": "002555.SZ", "name": "三七互娱", "role": "游戏景气映射"},
            {"ticker": "002624.SZ", "name": "完美世界", "role": "游戏景气映射"},
            {"ticker": "300059.SZ", "name": "东方财富", "role": "互联网金融情绪映射"},
        ],
        "risk_transmission": "腾讯核心看游戏流水、广告修复、回购力度和港股流动性；若南向资金转弱或游戏/广告低于预期，港股互联网估值容易同步降温。",
    },
}


def normalize_ticker(ticker):
    ticker = (ticker or "").strip().upper()
    if ticker.endswith(".SH"):
        ticker = ticker[:-3] + ".SS"
    if ticker.isdigit() and len(ticker) == 6:
        if ticker.startswith("6"):
            return f"{ticker}.SS"
        if ticker.startswith(("0", "3")):
            return f"{ticker}.SZ"
    return ticker


def infer_market_type(ticker):
    normalized = normalize_ticker(ticker)
    if normalized.endswith(".SZ") or normalized.endswith(".SS") or normalized.endswith(".SH"):
        return "A_SHARE"
    if normalized.endswith(".HK"):
        return "HK_STOCK"
    if normalized.endswith(".T"):
        return "JP_STOCK"
    return "US_STOCK"


def ticker_core(ticker):
    return normalize_ticker(ticker).replace(".SZ", "").replace(".SS", "").replace(".SH", "").replace(".HK", "").replace(".T", "")


def market_family(market_type):
    value = (market_type or "").upper()
    if value in {"A_SHARE", "A_SHARE_SH", "A_SHARE_SZ", "CN", "CHINA"}:
        return "A_SHARE"
    if value in {"HK", "HK_STOCK", "HONGKONG"}:
        return "HK_STOCK"
    if value in {"JP", "JP_STOCK", "JAPAN"}:
        return "JP_STOCK"
    if value in {"US", "US_STOCK", "USA"}:
        return "US_STOCK"
    return value or "US_STOCK"


def standardize_ohlcv_frame(raw_df, market_type="", source=""):
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()

    df = raw_df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(col[0] or col[-1]) for col in df.columns]

    rename_map = {
        "Date": "date",
        "Datetime": "date",
        "日期": "date",
        "时间": "date",
        "Open": "open",
        "开盘": "open",
        "High": "high",
        "最高": "high",
        "Low": "low",
        "最低": "low",
        "Close": "close",
        "收盘": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
        "成交量": "volume",
        "Amount": "amount",
        "成交额": "amount",
        "Turnover": "turnover_rate",
        "换手率": "turnover_rate",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
    }
    df = df.rename(columns={col: rename_map.get(str(col), str(col).lower()) for col in df.columns})
    if "date" not in df.columns:
        df = df.reset_index()
        df = df.rename(columns={col: rename_map.get(str(col), str(col).lower()) for col in df.columns})
        if "date" not in df.columns and "index" in df.columns:
            df = df.rename(columns={"index": "date"})

    for col in ["open", "high", "low", "close", "adj_close", "volume", "amount", "turnover_rate", "pct_change", "change"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        df["date"] = pd.NaT

    keep_cols = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "amount",
        "turnover_rate",
        "pct_change",
        "change",
    ]
    keep_cols = [col for col in keep_cols if col in df.columns]
    df = df[keep_cols].dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    if df.empty:
        return df
    df["market_type"] = market_family(market_type)
    df["source"] = source or "unknown"
    return df


def _yf_symbol(ticker, market_type=None):
    raw = (ticker or "").strip().upper()
    market = market_family(market_type or infer_market_type(raw))
    if market == "A_SHARE":
        return normalize_ticker(raw)
    if market == "HK_STOCK" and raw.isdigit():
        return f"{raw.zfill(4)}.HK"
    if market == "JP_STOCK" and raw.isdigit():
        return f"{raw}.T"
    return normalize_ticker(raw)


def _fetch_ohlcv_yfinance(ticker, market_type, start=None, end=None, interval="1d"):
    symbol = _yf_symbol(ticker, market_type)
    try:
        data = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        frame = standardize_ohlcv_frame(data, market_type=market_type, source=f"yfinance:{symbol}")
        if frame.empty:
            frame.attrs["warning"] = f"yfinance:{symbol} 返回空数据"
        return frame
    except Exception as exc:
        frame = pd.DataFrame()
        frame.attrs["warning"] = f"yfinance:{symbol} 异常：{exc}"
        return frame


def _fetch_ohlcv_akshare(ticker, start=None, end=None, adjust="qfq"):
    code = ticker_core(ticker)
    if not code.isdigit():
        frame = pd.DataFrame()
        frame.attrs["warning"] = f"akshare 需要6位A股代码，当前为 {ticker}"
        return frame

    start_date = pd.to_datetime(start or datetime.date.today() - datetime.timedelta(days=365 * 2)).strftime("%Y%m%d")
    end_date = pd.to_datetime(end or datetime.date.today()).strftime("%Y%m%d")
    try:
        import akshare as ak

        data = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        frame = standardize_ohlcv_frame(data, market_type="A_SHARE", source=f"akshare:{code}")
        if frame.empty:
            frame.attrs["warning"] = f"akshare:{code} 返回空数据，区间 {start_date}-{end_date}"
        return frame
    except Exception as exc:
        frame = pd.DataFrame()
        frame.attrs["warning"] = f"akshare:{code} 异常：{exc}"
        return frame


def _tushare_ts_code(ticker):
    text = normalize_ticker(ticker).upper().strip()
    if text.endswith(".SS"):
        return text[:-3] + ".SH"
    if text.endswith((".SH", ".SZ", ".BJ")):
        return text
    code = ticker_core(text)
    if code.isdigit() and len(code) == 6:
        if code.startswith(("6", "9")):
            return f"{code}.SH"
        if code.startswith(("0", "2", "3")):
            return f"{code}.SZ"
        if code.startswith(("4", "8")):
            return f"{code}.BJ"
    return text


def _tushare_result_frame(result):
    if not isinstance(result, dict) or not result.get("ok") or result.get("data") is None:
        return pd.DataFrame()
    data = result.get("data")
    return data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data)


def _fetch_ohlcv_tushare(ticker, start=None, end=None, adjust="qfq"):
    normalized = normalize_ticker(ticker)
    market = market_family(infer_market_type(normalized))
    if market != "A_SHARE":
        frame = pd.DataFrame()
        frame.attrs["warning"] = f"tushare 仅支持A股，当前为 {ticker}"
        return frame

    ts_code = _tushare_ts_code(normalized)
    start_date = pd.to_datetime(start or datetime.date.today() - datetime.timedelta(days=365 * 2)).strftime("%Y%m%d")
    end_date = pd.to_datetime(end or datetime.date.today()).strftime("%Y%m%d")

    try:
        import tushare_adapter
    except Exception as exc:
        frame = pd.DataFrame()
        frame.attrs["warning"] = f"tushare_adapter 不可用：{exc}"
        return frame

    daily_result = tushare_adapter.get_daily(ts_code, start_date, end_date)
    daily = _tushare_result_frame(daily_result)
    if daily.empty:
        frame = pd.DataFrame()
        error = daily_result.get("error") if isinstance(daily_result, dict) else "daily 返回空数据"
        frame.attrs["warning"] = f"tushare:{ts_code} daily 不可用：{error}"
        return frame

    df = daily.rename(
        columns={
            "trade_date": "date",
            "vol": "volume",
            "pct_chg": "pct_change",
        }
    ).copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")

    for col in ["open", "high", "low", "close", "volume", "amount", "pct_change", "change"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    warnings = []
    adjustment = "unadjusted"

    basic_result = tushare_adapter.get_daily_basic(ts_code, start_date, end_date)
    basic = _tushare_result_frame(basic_result)
    if not basic.empty and "trade_date" in basic.columns:
        keep_cols = [col for col in ["trade_date", "turnover_rate", "volume_ratio"] if col in basic.columns]
        basic = basic[keep_cols].copy()
        basic["date"] = pd.to_datetime(basic["trade_date"], format="%Y%m%d", errors="coerce")
        for col in ["turnover_rate", "volume_ratio"]:
            if col in basic.columns:
                basic[col] = pd.to_numeric(basic[col], errors="coerce")
        df = df.merge(basic.drop(columns=["trade_date"], errors="ignore"), on="date", how="left")
    elif isinstance(basic_result, dict) and basic_result.get("error"):
        warnings.append(f"daily_basic 不可用：{basic_result.get('error')}")

    if str(adjust or "").lower() == "qfq":
        adj_result = tushare_adapter.get_adj_factor(ts_code, start_date, end_date)
        adj = _tushare_result_frame(adj_result)
        if not adj.empty and {"trade_date", "adj_factor"}.issubset(adj.columns):
            adj = adj[["trade_date", "adj_factor"]].copy()
            adj["date"] = pd.to_datetime(adj["trade_date"], format="%Y%m%d", errors="coerce")
            adj["adj_factor"] = pd.to_numeric(adj["adj_factor"], errors="coerce")
            df = df.merge(adj.drop(columns=["trade_date"], errors="ignore"), on="date", how="left")
            latest_adj = df.sort_values("date")["adj_factor"].dropna()
            latest_adj_factor = float(latest_adj.iloc[-1]) if not latest_adj.empty else None
            if latest_adj_factor and latest_adj_factor > 0:
                ratio = df["adj_factor"] / latest_adj_factor
                for col in ["open", "high", "low", "close"]:
                    if col in df.columns:
                        df[col] = df[col] * ratio
                adjustment = "qfq"
            else:
                warnings.append("Tushare 当前使用未复权日线，adj_factor 不可用。")
        else:
            error = adj_result.get("error") if isinstance(adj_result, dict) else "adj_factor 返回空数据"
            warnings.append(f"Tushare 当前使用未复权日线，adj_factor 不可用。{error}")

    frame = standardize_ohlcv_frame(df, market_type="A_SHARE", source=f"tushare:{ts_code}:{adjustment}")
    frame.attrs["provider"] = "tushare"
    frame.attrs["price_adjustment"] = adjustment
    if warnings:
        frame.attrs["warning"] = "；".join(warnings)
    if frame.empty and not frame.attrs.get("warning"):
        frame.attrs["warning"] = f"tushare:{ts_code} 返回空数据，区间 {start_date}-{end_date}"
    return frame


def fetch_ohlcv(ticker, market_type=None, start=None, end=None, freq="1d", provider="auto", adjust="qfq"):
    normalized = normalize_ticker(ticker)
    market = market_family(market_type or infer_market_type(normalized))
    provider = (provider or "auto").lower()
    attempts = []

    if market == "A_SHARE" and provider in {"auto", "tushare", "ts"}:
        data = _fetch_ohlcv_tushare(normalized, start=start, end=end, adjust=adjust)
        attempts.append(data.attrs.get("warning") or f"tushare:{_tushare_ts_code(normalized)} 成功 {len(data)} 行")
        if not data.empty:
            data.attrs["attempts"] = attempts
            return data

    if provider in {"tushare", "ts"} and market != "A_SHARE":
        data = _fetch_ohlcv_tushare(normalized, start=start, end=end, adjust=adjust)
        attempts.append(data.attrs.get("warning") or f"tushare:{normalized} 不支持非A股")

    if market == "A_SHARE" and provider in {"auto", "akshare"}:
        data = _fetch_ohlcv_akshare(normalized, start=start, end=end, adjust=adjust)
        attempts.append(data.attrs.get("warning") or f"akshare:{ticker_core(normalized)} 成功 {len(data)} 行")
        if not data.empty:
            data.attrs["attempts"] = attempts
            return data

    if provider in {"auto", "yfinance", "yf", "tushare", "ts"}:
        data = _fetch_ohlcv_yfinance(normalized, market, start=start, end=end, interval=freq)
        attempts.append(data.attrs.get("warning") or f"yfinance:{_yf_symbol(normalized, market)} 成功 {len(data)} 行")
        if not data.empty:
            data.attrs["attempts"] = attempts
            return data

    if market == "A_SHARE" and provider in {"akshare"}:
        data = _fetch_ohlcv_yfinance(normalized, market, start=start, end=end, interval=freq)
        attempts.append(data.attrs.get("warning") or f"yfinance:{_yf_symbol(normalized, market)} 备用成功 {len(data)} 行")
        if not data.empty:
            data.attrs["attempts"] = attempts
            return data

    if market == "A_SHARE" and provider not in {"akshare"}:
        data = _fetch_ohlcv_akshare(normalized, start=start, end=end, adjust=adjust)
        attempts.append(data.attrs.get("warning") or f"akshare:{ticker_core(normalized)} 备用成功 {len(data)} 行")
        if not data.empty:
            data.attrs["attempts"] = attempts
            return data

    empty = pd.DataFrame()
    empty.attrs["attempts"] = attempts or [f"未匹配可用行情源：{normalized}/{market}/{provider}"]
    return empty


def fetch_ohlcv_diagnostics(ticker, market_type=None, start=None, end=None, freq="1d", provider="auto", adjust="qfq"):
    data = fetch_ohlcv(
        ticker,
        market_type=market_type,
        start=start,
        end=end,
        freq=freq,
        provider=provider,
        adjust=adjust,
    )
    return {
        "ticker": normalize_ticker(ticker),
        "market_type": market_family(market_type or infer_market_type(ticker)),
        "provider": provider,
        "rows": int(len(data)) if data is not None else 0,
        "source": data["source"].iloc[-1] if data is not None and not data.empty and "source" in data.columns else "",
        "attempts": data.attrs.get("attempts", []) if data is not None else [],
        "start": str(start),
        "end": str(end),
    }


def fetch_realtime_quote(ticker, market_type=None, provider="auto"):
    end = datetime.date.today() + datetime.timedelta(days=1)
    start = end - datetime.timedelta(days=10)
    data = fetch_ohlcv(
        ticker,
        market_type=market_type,
        start=start.isoformat(),
        end=end.isoformat(),
        provider=provider,
    )
    if data.empty:
        return {
            "ticker": normalize_ticker(ticker),
            "price": None,
            "asof": "",
            "source": provider,
            "warning": "暂无可用实时/近实时行情",
        }
    latest = data.iloc[-1]
    return {
        "ticker": normalize_ticker(ticker),
        "price": round(float(latest.get("close")), 4),
        "asof": str(latest.get("date").date()) if pd.notna(latest.get("date")) else "",
        "source": latest.get("source", provider),
        "volume": float(latest.get("volume")) if pd.notna(latest.get("volume")) else None,
    }


def _filter_micro_frame_by_code(df, code):
    if df is None or df.empty:
        return df
    code = str(code).zfill(6)
    text_cols = [col for col in df.columns if "代码" in str(col) or "名称" in str(col)]
    if not text_cols:
        return df
    mask = pd.Series(False, index=df.index)
    for col in text_cols:
        mask = mask | df[col].astype(str).str.contains(code, na=False)
    return df[mask]


def fetch_micro_data(ticker, market_type=None, deep=False):
    normalized = normalize_ticker(ticker)
    market = market_family(market_type or infer_market_type(normalized))
    result = {
        "ticker": normalized,
        "market_type": market,
        "fund_flow": [],
        "dragon_tiger": [],
        "block_trade": [],
        "warnings": [],
        "mode": "deep" if deep else "quick",
    }

    if market != "A_SHARE":
        result["warnings"].append("当前微观数据优先覆盖A股；港股/美股使用资金面模块代理。")
        return result

    code = ticker_core(normalized)
    try:
        import akshare as ak

        try:
            flow = ak.stock_individual_fund_flow(stock=code, market="sh" if normalized.endswith(".SS") else "sz")
            if flow is not None and not flow.empty:
                result["fund_flow"] = flow.tail(8).to_dict("records")
        except Exception as exc:
            result["warnings"].append(f"个股资金流暂不可用：{exc}")

        if not deep:
            result["warnings"].append("快速模式：未运行完整龙虎榜/大宗交易扫描。")
            return result

        try:
            lhb = ak.stock_lhb_detail_em(start_date=(datetime.date.today() - datetime.timedelta(days=90)).strftime("%Y%m%d"), end_date=datetime.date.today().strftime("%Y%m%d"))
            if lhb is not None and not lhb.empty:
                result["dragon_tiger"] = _filter_micro_frame_by_code(lhb, code).tail(8).to_dict("records")
        except Exception as exc:
            result["warnings"].append(f"龙虎榜暂不可用：{exc}")

        try:
            block = ak.stock_dzjy_mrmx(symbol=datetime.date.today().strftime("%Y%m%d"))
            if block is not None and not block.empty:
                result["block_trade"] = _filter_micro_frame_by_code(block, code).tail(8).to_dict("records")
        except Exception as exc:
            result["warnings"].append(f"大宗交易暂不可用：{exc}")
    except Exception as exc:
        result["warnings"].append(f"Akshare微观接口不可用：{exc}")

    return result


def build_google_news_rss(query, lang="zh-CN", region="CN"):
    encoded = quote_plus(query)
    ceid = "US:en" if lang == "en-US" else f"{region}:zh-Hans"
    return f"https://news.google.com/rss/search?q={encoded}&hl={lang}&gl={region}&ceid={ceid}"


def get_supply_chain_profile(ticker):
    normalized = normalize_ticker(ticker)
    if normalized in SUPPLY_CHAIN_MAP:
        return SUPPLY_CHAIN_MAP[normalized]

    if normalized.endswith(".SZ") or normalized.endswith(".SS"):
        return {
            "name": normalized,
            "theme": "A股通用产业链",
            "position": "需结合主营业务确认上中下游",
            "upstream": ["原材料", "核心零部件", "设备"],
            "core_modules": ["主营产品", "渠道/订单", "产能利用率"],
            "downstream": ["终端需求", "行业景气", "政策周期"],
            "a_share_links": [],
            "risk_transmission": "建议接入公司主营、机构调仓和公告后再做精细联动。",
        }

    return {
        "name": normalized,
        "theme": "海外资产通用映射",
        "position": "需人工补充产业链映射",
        "upstream": ["供应链", "资本开支", "宏观流动性"],
        "core_modules": ["核心产品", "盈利周期", "估值锚"],
        "downstream": ["客户需求", "行业beta"],
        "a_share_links": [],
        "risk_transmission": "未配置专属映射，暂按行业beta和新闻舆情处理。",
    }


@lru_cache(maxsize=128)
def _fetch_price_history_cached(normalized_ticker, period):
    try:
        data = yf.Ticker(normalized_ticker).history(period=period)
        if data is None or data.empty:
            return pd.DataFrame()
        return data.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


def fetch_price_history(ticker, period="2y"):
    normalized = normalize_ticker(ticker)
    return _fetch_price_history_cached(normalized, period).copy()


def _period_to_start_date(period):
    text = str(period or "2y").strip().lower()
    today = datetime.date.today()
    match = re.fullmatch(r"(\d+)([ymd])", text)
    if not match:
        return today - datetime.timedelta(days=365 * 2)
    count = int(match.group(1))
    unit = match.group(2)
    if unit == "y":
        return today - datetime.timedelta(days=365 * count)
    if unit == "m":
        return today - datetime.timedelta(days=31 * count)
    return today - datetime.timedelta(days=count)


def _ohlcv_to_price_history(frame):
    if frame is None or frame.empty or "close" not in frame.columns:
        return pd.DataFrame()
    hist = pd.DataFrame(index=pd.to_datetime(frame.get("date"), errors="coerce"))
    hist["Close"] = pd.to_numeric(frame.get("close"), errors="coerce").to_numpy()
    if "volume" in frame.columns:
        hist["Volume"] = pd.to_numeric(frame.get("volume"), errors="coerce").to_numpy()
    if "open" in frame.columns:
        hist["Open"] = pd.to_numeric(frame.get("open"), errors="coerce").to_numpy()
    if "high" in frame.columns:
        hist["High"] = pd.to_numeric(frame.get("high"), errors="coerce").to_numpy()
    if "low" in frame.columns:
        hist["Low"] = pd.to_numeric(frame.get("low"), errors="coerce").to_numpy()
    hist = hist.dropna(subset=["Close"]).sort_index()
    hist.attrs.update(frame.attrs)
    if "source" in frame.columns and not frame.empty:
        hist.attrs["source"] = str(frame["source"].iloc[-1])
    return hist


def compute_rsi(close, period=14):
    if close is None or len(close) < period + 2:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    latest = rsi.dropna()
    if latest.empty:
        return None
    return round(float(latest.iloc[-1]), 2)


def compute_technical_snapshot(ticker, period="2y"):
    normalized = normalize_ticker(ticker)
    source = "yfinance"
    fallback_warning = ""
    hist = pd.DataFrame()

    if market_family(infer_market_type(normalized)) == "A_SHARE":
        try:
            start = _period_to_start_date(period).isoformat()
            end = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
            ohlcv = fetch_ohlcv(normalized, market_type="A_SHARE", start=start, end=end, provider="tushare", adjust="qfq")
            hist = _ohlcv_to_price_history(ohlcv)
            if not hist.empty:
                source = "tushare"
            else:
                fallback_warning = (ohlcv.attrs.get("warning") if hasattr(ohlcv, "attrs") else "") or "Tushare OHLCV empty"
        except Exception as exc:
            fallback_warning = str(exc)

    if hist.empty:
        hist = fetch_price_history(normalized, period=period)
        if not hist.empty:
            source = "yfinance_fallback" if market_family(infer_market_type(normalized)) == "A_SHARE" else "yfinance"

    missing = []
    if hist.empty or "Close" not in hist.columns:
        return {
            "ticker": normalized,
            "data_asof": "",
            "missing": ["price_history", "MA20", "MA60", "MA120", "RSI", "volume"],
            "confidence": 0,
            "source": "unavailable",
            "fallback_warning": fallback_warning,
        }

    close = hist["Close"].dropna()
    latest = float(close.iloc[-1]) if len(close) else None
    ma5 = float(close.rolling(5).mean().iloc[-1]) if len(close) >= 5 else None
    ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else None
    ma120 = float(close.rolling(120).mean().iloc[-1]) if len(close) >= 120 else None
    rsi = compute_rsi(close, 14)
    if ma5 is None:
        missing.append("MA5")
    if ma20 is None:
        missing.append("MA20")
    if ma60 is None:
        missing.append("MA60")
    if ma120 is None:
        missing.append("MA120")
    if rsi is None:
        missing.append("RSI")

    volume_vs_20d = None
    if "Volume" in hist.columns and hist["Volume"].fillna(0).sum() > 0 and len(hist) >= 20:
        latest_volume = float(hist["Volume"].iloc[-1])
        avg_volume = float(hist["Volume"].tail(20).mean())
        volume_vs_20d = round(latest_volume / max(avg_volume, 1), 2)
    else:
        missing.append("volume")

    returns = close.pct_change().dropna()
    drawdown = None
    volatility_20d = None
    if len(close) > 20:
        peak = close.cummax()
        drawdown = round(float((close / peak - 1).iloc[-1] * 100), 2)
        volatility_20d = round(float(returns.tail(20).std() * np.sqrt(252) * 100), 2) if len(returns) >= 20 else None
    drawdown_20d = None
    drawdown_60d = None
    if len(close) >= 20:
        peak_20d = close.tail(20).cummax()
        drawdown_20d = round(float((close.tail(20) / peak_20d - 1).iloc[-1] * 100), 2)
    if len(close) >= 60:
        peak_60d = close.tail(60).cummax()
        drawdown_60d = round(float((close.tail(60) / peak_60d - 1).iloc[-1] * 100), 2)

    macd = None
    macd_signal = None
    macd_hist = None
    if len(close) >= 35:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd = round(float(macd_line.iloc[-1]), 4)
        macd_signal = round(float(signal_line.iloc[-1]), 4)
        macd_hist = round(float((macd_line.iloc[-1] - signal_line.iloc[-1]) * 2), 4)
    else:
        missing.append("MACD")

    confidence = max(0, 100 - len(missing) * 22)
    return {
        "ticker": normalized,
        "data_asof": str(close.index[-1].date()) if len(close) else "",
        "latest_close": round(latest, 2) if latest else None,
        "ma5": round(ma5, 2) if ma5 else None,
        "ma20": round(ma20, 2) if ma20 else None,
        "ma60": round(ma60, 2) if ma60 else None,
        "ma120": round(ma120, 2) if ma120 else None,
        "ma20_state": "站上MA20" if latest and ma20 and latest >= ma20 else ("低于MA20" if latest and ma20 else "未知"),
        "ma60_state": "站上MA60" if latest and ma60 and latest >= ma60 else ("低于MA60" if latest and ma60 else "未知"),
        "ma120_state": "站上MA120" if latest and ma120 and latest >= ma120 else ("低于MA120" if latest and ma120 else "未知"),
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "volume_vs_20d": volume_vs_20d,
        "return_20d": round(float((close.iloc[-1] / close.iloc[-21] - 1) * 100), 2) if len(close) >= 21 else None,
        "return_60d": round(float((close.iloc[-1] / close.iloc[-61] - 1) * 100), 2) if len(close) >= 61 else None,
        "price_vs_ma20_pct": round(float((latest / ma20 - 1) * 100), 2) if latest and ma20 else None,
        "price_vs_ma60_pct": round(float((latest / ma60 - 1) * 100), 2) if latest and ma60 else None,
        "drawdown": drawdown,
        "drawdown_20d": drawdown_20d,
        "drawdown_60d": drawdown_60d,
        "annualized_vol_20d": volatility_20d,
        "missing": missing,
        "confidence": confidence,
        "source": source,
        "fallback_warning": fallback_warning,
    }


def simulate_monte_carlo_range(ticker, days=63, simulations=1500, period="2y", seed=42):
    normalized = normalize_ticker(ticker)
    hist = fetch_price_history(normalized, period=period)
    if hist.empty or "Close" not in hist.columns or len(hist) < 80:
        return {
            "ticker": normalized,
            "horizon_days": days,
            "missing": ["insufficient_price_history"],
            "confidence": 0,
        }

    close = hist["Close"].dropna()
    log_returns = np.log(close / close.shift(1)).dropna()
    if len(log_returns) < 60:
        return {
            "ticker": normalized,
            "horizon_days": days,
            "missing": ["insufficient_return_series"],
            "confidence": 0,
        }

    rng = np.random.default_rng(seed)
    sampled = rng.choice(log_returns.tail(504).values, size=(simulations, days), replace=True)
    terminal = float(close.iloc[-1]) * np.exp(sampled.sum(axis=1))
    p10, p25, p50, p75, p90 = np.percentile(terminal, [10, 25, 50, 75, 90])
    down_10 = float((terminal <= float(close.iloc[-1]) * 0.9).mean() * 100)
    up_10 = float((terminal >= float(close.iloc[-1]) * 1.1).mean() * 100)
    positive = float((terminal > float(close.iloc[-1])).mean() * 100)

    return {
        "ticker": normalized,
        "data_asof": str(close.index[-1].date()),
        "base_price": round(float(close.iloc[-1]), 2),
        "horizon_days": days,
        "simulations": simulations,
        "p10": round(float(p10), 2),
        "p25": round(float(p25), 2),
        "p50": round(float(p50), 2),
        "p75": round(float(p75), 2),
        "p90": round(float(p90), 2),
        "probability_positive_pct": round(positive, 1),
        "probability_down_10_pct": round(down_10, 1),
        "probability_up_10_pct": round(up_10, 1),
        "annualized_volatility_pct": round(float(log_returns.std() * np.sqrt(252) * 100), 2),
        "missing": [],
        "confidence": 85,
    }


def get_valuation_snapshot(ticker):
    normalized = normalize_ticker(ticker)
    hist = fetch_price_history(normalized, period="3y")
    info = {}
    try:
        info = yf.Ticker(normalized).info or {}
    except Exception:
        info = {}

    close = hist["Close"] if not hist.empty else pd.Series(dtype=float)
    latest = float(close.iloc[-1]) if len(close) else None
    one_year = close.tail(252)
    price_percentile = None
    if latest and len(one_year) > 20:
        price_percentile = round(float((one_year <= latest).mean() * 100), 1)

    market_cap = info.get("marketCap")
    free_cashflow = info.get("freeCashflow")
    fcf_yield = None
    if market_cap and free_cashflow:
        try:
            fcf_yield = round(float(free_cashflow) / float(market_cap) * 100, 2)
        except Exception:
            fcf_yield = None

    return {
        "ticker": normalized,
        "latest": round(latest, 2) if latest else None,
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb": info.get("priceToBook"),
        "fcf_yield": fcf_yield,
        "market_cap": market_cap,
        "price_percentile_1y": price_percentile,
        "valuation_flag": classify_valuation(info.get("trailingPE"), info.get("priceToBook"), price_percentile, fcf_yield),
    }


def classify_valuation(pe, pb, price_percentile, fcf_yield):
    flags = []
    try:
        if pe and pe > 60:
            flags.append("高PE")
        if pb and pb > 8:
            flags.append("高PB")
        if price_percentile and price_percentile > 85:
            flags.append("价格处于1年高位")
        if fcf_yield is not None and fcf_yield < 1:
            flags.append("自由现金流收益率偏低")
    except Exception:
        pass
    return "；".join(flags) if flags else "估值未触发明显高危标签"


def calc_return_metrics(price_map):
    returns = {}
    for ticker, hist in price_map.items():
        if hist is None or hist.empty:
            continue
        series = hist["Close"].pct_change().dropna()
        if len(series) > 20:
            returns[ticker] = series
    if not returns:
        return pd.DataFrame(), {}

    df = pd.DataFrame(returns).dropna(how="all").fillna(0)
    metrics = {}
    for ticker in df.columns:
        r = df[ticker]
        ann_ret = float(r.mean() * 252)
        ann_vol = float(r.std() * np.sqrt(252))
        sharpe = ann_ret / ann_vol if ann_vol else 0
        dd = float(((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min())
        metrics[ticker] = {
            "annual_return": round(ann_ret * 100, 2),
            "annual_vol": round(ann_vol * 100, 2),
            "max_drawdown": round(dd * 100, 2),
            "sharpe": round(sharpe, 2),
        }
    return df.corr().round(2), metrics


def compute_portfolio_health(target, related_tickers=None):
    tickers = [normalize_ticker(target)]
    for item in related_tickers or []:
        t = normalize_ticker(item.get("ticker", ""))
        if t and t not in tickers:
            tickers.append(t)
    tickers = tickers[:8]

    price_map = {ticker: fetch_price_history(ticker, period="1y") for ticker in tickers}
    corr, metrics = calc_return_metrics(price_map)
    return {"tickers": tickers, "correlation": corr, "metrics": metrics}


SHORT_TICKER_STRONG_NOISE_TERMS = [
    "litefinance",
    "lite finance",
    "forex",
    "gold price",
    "xau",
    "trading platform",
]
SHORT_TICKER_WEAK_NOISE_TERMS = ["broker"]
SHORT_TICKER_COMPANY_TERMS = ["lumentum", "lumentum holdings"]


def alias_matches_news_text(text, alias, market_type=None):
    raw_alias = str(alias or "").strip()
    if len(raw_alias) < 2:
        return False

    text = str(text or "")
    alias_l = raw_alias.lower()
    text_l = text.lower()

    if raw_alias.isdigit() and len(raw_alias) == 6:
        return bool(re.search(rf"(?<!\d){re.escape(raw_alias)}(?!\d)", text))
    if alias_l.isdigit():
        return bool(re.search(rf"(?<!\d){re.escape(alias_l)}(?!\d)", text_l))
    if len(alias_l) <= 5 and alias_l.isascii():
        return bool(re.search(rf"\b{re.escape(alias_l)}\b", text_l))
    return alias_l in text_l


def has_short_ticker_news_noise(text, aliases, market_type=None):
    text_l = str(text or "").lower()
    if any(term in text_l for term in SHORT_TICKER_COMPANY_TERMS):
        return False
    has_strong_noise = any(term in text_l for term in SHORT_TICKER_STRONG_NOISE_TERMS)
    has_weak_noise = any(term in text_l for term in SHORT_TICKER_WEAK_NOISE_TERMS)
    if not has_strong_noise and not has_weak_noise:
        return False
    if has_weak_noise and not has_strong_noise:
        return False
    for alias in aliases or []:
        alias_l = str(alias or "").strip().lower()
        if len(alias_l) <= 5 and alias_l.isascii() and alias_matches_news_text(text_l, alias_l, market_type):
            return True
    return False


def score_news_relevance(text, aliases, market_type=None):
    text = text or ""
    if has_short_ticker_news_noise(text, aliases, market_type):
        return 0
    score = 0
    for alias in aliases:
        if alias_matches_news_text(text, alias, market_type):
            score += 35
    hot_words = ["调仓", "持仓", "龙虎榜", "机构", "游资", "大宗交易", "回购", "减持", "增持", "订单", "业绩", "guidance", "insider"]
    for word in hot_words:
        if word.lower() in str(text).lower():
            score += 8
    return min(score, 100)


def normalize_news_title(title):
    text = str(title or "").strip().lower()
    text = re.sub(r"\s+-\s+[^-｜|]{2,60}$", "", text)
    text = re.sub(r"[｜|]\s*(新浪财经|东方财富|搜狐网|财富号|yahoo finance|seeking alpha).*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(不斷更新|不断更新|快讯|快報|异动快报|股市要闻|市场)$", "", text, flags=re.IGNORECASE)
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def build_dedupe_key(title, source=None, date=None):
    normalized = normalize_news_title(title)
    day = ""
    parsed = parse_created_at(date) if date else None
    if parsed:
        day = parsed.date().isoformat()
    return "|".join(part for part in [normalized, day] if part) or str(source or title or "")


def _news_age_hours(row):
    created = parse_created_at((row or {}).get("created_at"))
    if not created:
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=datetime.timezone.utc)
    return max(0.0, (now - created).total_seconds() / 3600)


def _is_broad_news_row(row):
    keyword = str((row or {}).get("keyword") or "")
    source = str((row or {}).get("source") or "").lower()
    title = str((row or {}).get("title") or "").lower()
    broad_keywords = {"A股新趋势", "港股新趋势", "全球新趋势", "机构游资调仓", "黄金", "AI算力"}
    if keyword in broad_keywords:
        return True
    broad_source_terms = [
        "gold+price+market",
        "%E6%9C%BA%E6%9E%84%E8%B0%83%E4%BB%93",
        "%E6%B6%A8%E5%81%9C+%E6%9D%BF%E5%9D%97",
        "%E6%B8%AF%E8%82%A1+OR",
    ]
    if any(term.lower() in source for term in broad_source_terms):
        return True
    if any(term in title for term in ["恒指", "港股市況", "港股走势", "gold price forecast"]):
        return True
    return False


def build_news_filter_aliases(stock_code=None, stock_name=None, aliases=None):
    terms = []
    for value in [stock_code, ticker_core(stock_code or ""), stock_name, *(aliases or [])]:
        text = str(value or "").strip()
        if len(text) >= 2:
            terms.append(text)
    return list(dict.fromkeys(terms))


def filter_news_clues_for_prompt(rows, stock_code=None, stock_name=None, aliases=None, max_items=8, hours=48):
    aliases = build_news_filter_aliases(stock_code=stock_code, stock_name=stock_name, aliases=aliases)
    cutoff_hours = float(hours or 48)
    scored = []
    seen = set()

    for row in rows or []:
        title = str((row or {}).get("title") or "")
        if not title:
            continue
        key = normalize_news_title(title)
        if key in seen:
            continue
        seen.add(key)

        blob = " ".join(str((row or {}).get(k, "")) for k in ["keyword", "title", "summary", "url"])
        primary_hit = True if not aliases else has_primary_alias(blob, aliases)
        if not primary_hit:
            continue
        if has_short_ticker_news_noise(blob, aliases):
            continue

        age = _news_age_hours(row)
        if age is not None and age > cutoff_hours:
            continue

        score = score_news_relevance(blob, aliases)
        if age is not None and age <= 24:
            score += 20
        elif age is not None and age <= 48:
            score += 10
        if str((row or {}).get("risk_tag") or "") not in {"", "普通新闻", "未知"}:
            score += 18
        if _is_broad_news_row(row):
            score -= 25

        item = dict(row)
        item["normalized_title"] = normalize_news_title(title)
        item["dedupe_key"] = key
        item["relevance_score"] = min(100, max(0, score))
        item["verification_status"] = "新闻线索，需公告/交易所/Tushare/原文进一步验证"
        item["fact_boundary"] = "risk_tag/sentiment 为模型提取标签，不是官方事实"
        scored.append(item)

    scored.sort(key=lambda item: (item.get("relevance_score", 0), item.get("created_at", "")), reverse=True)
    return scored[:max_items]


def has_primary_alias(text, aliases):
    for alias in aliases or []:
        if alias_matches_news_text(text, alias):
            return True
    return False


def looks_like_a_share_noise(text):
    text = text or ""
    cn_stock_code = re.search(r"\b(60|68|00|30)\d{4}\b", text)
    cn_terms = ["A股", "沪深", "涨停", "跌停", "龙虎榜", "北向资金", "融资融券", "股吧", "东方财富", "证券时报", "券商中国"]
    return bool(cn_stock_code or any(term in text for term in cn_terms))


def looks_like_us_noise_for_cn(text):
    text = (text or "").lower()
    us_terms = ["nasdaq", "nyse", "sec", "13f", "earnings call", "options", "insider trading"]
    return any(term in text for term in us_terms)


def should_keep_news_row(row, normalized, aliases, market_type):
    blob = " ".join(str(row.get(k, "")) for k in ["keyword", "title", "summary", "url"])
    primary_hit = has_primary_alias(blob, aliases)
    if primary_hit and has_short_ticker_news_noise(blob, aliases, market_type):
        return False, "过滤：短ticker命中外汇/黄金/平台噪音"
    if market_type == "US_STOCK":
        if looks_like_a_share_noise(blob) and not primary_hit:
            return False, "过滤：美股标的排除A股泛新闻"
        if not primary_hit:
            return False, "过滤：未命中美股ticker/公司名"
    elif market_type in ["A_SHARE", "A_SHARE_SH", "A_SHARE_SZ"]:
        if looks_like_us_noise_for_cn(blob) and not primary_hit:
            return False, "过滤：A股标的排除美股泛新闻"
        if not primary_hit and score_news_relevance(blob, aliases) < 45:
            return False, "过滤：未命中A股代码/公司名"
    elif market_type == "HK_STOCK":
        if not primary_hit and score_news_relevance(blob, aliases) < 40:
            return False, "过滤：未命中港股代码/公司名"
    return True, "命中标的别名/高相关关键词"


def parse_created_at(value):
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _supabase_ilike_filter(aliases, columns=("keyword", "title", "summary")):
    filters = []
    for alias in aliases or []:
        alias = str(alias or "").strip()
        if len(alias) < 2:
            continue
        alias = alias.replace(",", " ").replace("(", " ").replace(")", " ")
        for column in columns:
            filters.append(f"{column}.ilike.*{alias}*")
    return ",".join(filters[:24])


def build_recent_news_context(supabase, ticker, aliases=None, days=2, limit=12, market_type=None):
    if not supabase:
        return []

    normalized = normalize_ticker(ticker)
    market_type = market_type or infer_market_type(normalized)
    aliases = list(dict.fromkeys([normalized, ticker_core(normalized), *(aliases or [])]))
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    rows = []

    try:
        alias_filter = _supabase_ilike_filter(aliases)
        query = (
            supabase.table("market_news")
            .select("keyword, title, url, summary, risk_tag, sentiment, created_at")
            .gte("created_at", cutoff.isoformat())
        )
        if alias_filter:
            query = query.or_(alias_filter)
        candidate_limit = min(max(limit * 8, 20), 50)
        res = query.order("created_at", desc=True).limit(candidate_limit).execute()
        rows.extend(res.data or [])
    except Exception:
        pass

    if not rows:
        try:
            res = (
                supabase.table("market_news")
                .select("keyword, title, url, summary, risk_tag, sentiment, created_at")
                .order("created_at", desc=True)
                .limit(80)
                .execute()
            )
            rows.extend(res.data or [])
        except Exception:
            pass

    filtered = []
    for row in rows:
        created = parse_created_at(row.get("created_at"))
        if created and created < cutoff:
            continue
        blob = " ".join(str(row.get(k, "")) for k in ["keyword", "title", "summary"])
        relevance = score_news_relevance(blob, aliases, market_type)
        keep, filter_reason = should_keep_news_row(row, normalized, aliases, market_type)
        primary_hit = has_primary_alias(blob, aliases)
        if keep and primary_hit and relevance >= 25:
            row = dict(row)
            row["relevance_score"] = relevance
            row["market_filter"] = market_type
            row["filter_reason"] = filter_reason
            filtered.append(row)

    return filter_news_clues_for_prompt(
        filtered,
        stock_code=None,
        stock_name=None,
        aliases=aliases,
        max_items=min(limit, 8),
        hours=days * 24,
    )


def institutional_signal_queries(ticker, company_name=""):
    normalized = normalize_ticker(ticker)
    raw = normalized.replace(".SZ", "").replace(".SS", "")
    base = f"{company_name or raw} {raw}".strip()
    if infer_market_type(normalized) == "US_STOCK":
        return [
            build_google_news_rss(f"{base} 13F institutional ownership increased decreased", lang="en-US", region="US"),
            build_google_news_rss(f"{base} insider trading sale purchase Form 4", lang="en-US", region="US"),
            build_google_news_rss(f"{base} unusual options activity call put volume", lang="en-US", region="US"),
            f"https://www.sec.gov/edgar/search/#/q={quote_plus(raw)}",
        ]
    return [
        build_google_news_rss(f"{base} 机构 调仓 持仓 增持 减持"),
        build_google_news_rss(f"{base} 龙虎榜 游资 席位"),
        build_google_news_rss(f"{base} 大宗交易 融资融券 股东户数"),
        build_google_news_rss(f"{base} site:finance.sina.com.cn 机构"),
        build_google_news_rss(f"{base} site:eastmoney.com 龙虎榜"),
    ]


def deep_research_queries(ticker, company_name=""):
    normalized = normalize_ticker(ticker)
    raw = normalized.replace(".SZ", "").replace(".SS", "").replace(".HK", "")
    base = f"{company_name or raw} {raw}".strip()
    has_cn = normalized.endswith(".SZ") or normalized.endswith(".SS") or normalized.endswith(".HK")
    if has_cn:
        return [
            build_google_news_rss(f"{base} 财报 电话会 业绩说明会 问答 风险"),
            build_google_news_rss(f"{base} 同行业 对比 毛利率 订单 风险"),
            build_google_news_rss(f"{base} 研报 风险提示 不及预期"),
            build_google_news_rss(f"{base} 公告 减持 回购 业绩预告"),
        ]
    return [
        build_google_news_rss(f"{base} earnings call transcript risk guidance", lang="en-US", region="US"),
        build_google_news_rss(f"{base} 10-Q risk factors gross margin inventory capex", lang="en-US", region="US"),
        build_google_news_rss(f"{base} conference call transcript management commentary", lang="en-US", region="US"),
        build_google_news_rss(f"{base} peers comparison margin revenue risk", lang="en-US", region="US"),
        build_google_news_rss(f"{base} analyst report risks downside", lang="en-US", region="US"),
        build_google_news_rss(f"{base} insider selling guidance cut earnings miss", lang="en-US", region="US"),
        f"https://www.sec.gov/edgar/search/#/q={quote_plus(raw)}&forms=10-K%2C10-Q%2C8-K",
    ]


def build_peer_snapshot(ticker, supply_profile=None):
    rows = []
    profile = supply_profile or get_supply_chain_profile(ticker)
    for peer in profile.get("a_share_links", [])[:6]:
        peer_ticker = peer.get("ticker")
        if not peer_ticker:
            continue
        valuation = get_valuation_snapshot(peer_ticker)
        rows.append({
            "ticker": peer_ticker,
            "name": peer.get("name", ""),
            "role": peer.get("role", ""),
            "pe": valuation.get("trailing_pe"),
            "pb": valuation.get("pb"),
            "price_percentile_1y": valuation.get("price_percentile_1y"),
            "valuation_flag": valuation.get("valuation_flag"),
        })
    return rows


def build_data_quality_report(technical=None, valuation=None, news_rows=None, money_flow=None, scenario=None):
    missing = []
    warnings = []
    score = 100

    for field in (technical or {}).get("missing", []):
        missing.append(f"技术面缺失：{field}")
        score -= 12
    if not (technical or {}).get("data_asof"):
        missing.append("技术面缺失：行情日期")
        score -= 15

    valuation = valuation or {}
    for field in ["trailing_pe", "pb", "fcf_yield"]:
        if valuation.get(field) in [None, ""]:
            missing.append(f"估值缺失：{field}")
            score -= 6

    if not news_rows:
        missing.append("舆情缺失：近48小时无高相关新闻")
        score -= 14

    money_flow = money_flow or {}
    for item in money_flow.get("warnings", []):
        warnings.append(str(item))
        score -= 5
    if not money_flow.get("institutional_holders") and money_flow.get("market_type") == "US_STOCK":
        missing.append("资金面缺失：13F/机构持仓")
        score -= 8
    if not money_flow.get("options_signal") and money_flow.get("market_type") == "US_STOCK":
        missing.append("资金面缺失：期权链")
        score -= 8
    if money_flow.get("market_type") == "A_SHARE":
        if not money_flow.get("individual_fund_flow"):
            missing.append("资金面缺失：A股个股资金流")
            score -= 8
        if not money_flow.get("dragon_tiger"):
            missing.append("资金面缺失：龙虎榜")
            score -= 4
        if not money_flow.get("block_trade"):
            missing.append("资金面缺失：大宗交易")
            score -= 4
    if money_flow.get("market_type") == "HK_STOCK" and not money_flow.get("volume_signal"):
        missing.append("资金面缺失：港股成交量代理")
        score -= 8

    if (scenario or {}).get("confidence", 0) <= 0:
        missing.append("情景推演缺失：历史波动样本不足")
        score -= 10

    score = max(0, min(100, int(score)))
    if score >= 80:
        grade = "高"
        instruction = "可以输出明确观点，但仍需标注实时数据来源。"
    elif score >= 55:
        grade = "中"
        instruction = "只能给条件式结论，仓位建议需要保守。"
    else:
        grade = "低"
        instruction = "禁止给确定买卖结论，只能列触发条件和待验证清单。"

    return {
        "score": score,
        "grade": grade,
        "missing": list(dict.fromkeys(missing)),
        "warnings": warnings[:8],
        "instruction": instruction,
    }
