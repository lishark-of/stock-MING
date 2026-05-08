import datetime
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import yfinance as yf


SUPPLY_CHAIN_MAP = {
    "NVDA": {
        "name": "Nvidia",
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
}


def normalize_ticker(ticker):
    ticker = (ticker or "").strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        if ticker.startswith("6"):
            return f"{ticker}.SS"
        if ticker.startswith(("0", "3")):
            return f"{ticker}.SZ"
    return ticker


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


def fetch_price_history(ticker, period="2y"):
    try:
        data = yf.Ticker(normalize_ticker(ticker)).history(period=period)
        if data is None or data.empty:
            return pd.DataFrame()
        return data.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


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


def score_news_relevance(text, aliases):
    text = (text or "").lower()
    score = 0
    for alias in aliases:
        alias = str(alias).lower()
        if alias and alias in text:
            score += 35
    hot_words = ["调仓", "持仓", "龙虎榜", "机构", "游资", "大宗交易", "回购", "减持", "增持", "订单", "业绩", "guidance", "insider"]
    for word in hot_words:
        if word.lower() in text:
            score += 8
    return min(score, 100)


def parse_created_at(value):
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def build_recent_news_context(supabase, ticker, aliases=None, days=2, limit=12):
    if not supabase:
        return []

    normalized = normalize_ticker(ticker)
    aliases = list(dict.fromkeys([normalized, normalized.replace(".SZ", "").replace(".SS", ""), *(aliases or [])]))
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    rows = []

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
        relevance = score_news_relevance(blob, aliases)
        if relevance >= 25:
            row = dict(row)
            row["relevance_score"] = relevance
            filtered.append(row)

    filtered.sort(key=lambda x: (x.get("relevance_score", 0), x.get("created_at", "")), reverse=True)
    return filtered[:limit]


def institutional_signal_queries(ticker, company_name=""):
    normalized = normalize_ticker(ticker)
    raw = normalized.replace(".SZ", "").replace(".SS", "")
    base = f"{company_name or raw} {raw}".strip()
    return [
        build_google_news_rss(f"{base} 机构 调仓 持仓 增持 减持"),
        build_google_news_rss(f"{base} 龙虎榜 游资 席位"),
        build_google_news_rss(f"{base} 大宗交易 融资融券 股东户数"),
        build_google_news_rss(f"{base} site:finance.sina.com.cn 机构"),
        build_google_news_rss(f"{base} site:eastmoney.com 龙虎榜"),
    ]
