import json
import time
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, unquote_plus

from config import require_supabase_config
from manager_feeder import feed_manager_from_text, get_deepseek_client


SUPABASE_URL, SUPABASE_KEY = require_supabase_config()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


max_articles_per_manager = 5
per_rss_limit = 8


def url_hash(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def already_processed(url):
    try:
        h = url_hash(url)

        res = (
            supabase
            .table("processed_sources")
            .select("id")
            .eq("url_hash", h)
            .limit(1)
            .execute()
        )

        return bool(res.data)

    except Exception as e:
        print(f"检查去重失败：{e}")
        return False


def mark_processed(manager_name, url, title=""):
    # 只有 manager_rules 真正写入成功(saved > 0)后才记录 processed_sources。
    # saved = 0 的链接保留为未处理，方便 prompt 或抓取逻辑优化后继续重试。
    try:
        supabase.table("processed_sources").insert({
            "manager_name": manager_name,
            "url": url,
            "url_hash": url_hash(url),
            "title": title
        }).execute()

    except Exception as e:
        print(f"记录已处理链接失败：{e}")


def clean_html_text(text):
    if not text:
        return ""

    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(" ", strip=True)


def fetch_rss_items(rss_url, limit=per_rss_limit, source="RSS"):
    feed = feedparser.parse(rss_url)
    items = []

    for entry in feed.entries[:limit]:
        try:
            title = getattr(entry, "title", "")
            link = getattr(entry, "link", "")
            summary = clean_html_text(getattr(entry, "summary", ""))
            published = getattr(entry, "published", "")

            if title and link:
                items.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published,
                    "source": source,
                    "feed_url": rss_url
                })
        except Exception as e:
            print(f"解析 RSS 单条失败，跳过：{e}")

    return items


def build_google_news_rss(query, lang=None, region=None):
    query = (query or "").strip()
    if not query:
        return ""

    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in query)
    if lang is None:
        lang = "zh-CN" if has_chinese else "en-US"
    if region is None:
        region = "CN" if lang.startswith("zh") else "US"

    encoded_query = quote_plus(query)

    if lang == "en-US" or region == "US":
        return f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

    return f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"


def fetch_page_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ManagerFeederBot/1.0)",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text("\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        return clean_text[:20000]

    except Exception as e:
        print(f"抓取页面失败：{url}，原因：{e}")
        return ""


def manager_keyword_hit(text, keywords):
    if not text:
        return False

    for kw in keywords:
        if kw and kw.lower() in text.lower():
            return True

    return False


def is_targeted_rss(rss_url, manager_name, keywords):
    """
    定向 RSS 的 URL/query 里通常已经包含 manager_name 或关键词。
    Google News 的 query 是 URL 编码，先解码再判断；泛资讯源仍做关键词过滤。
    """
    decoded_url = unquote_plus(rss_url).lower()
    manager_name_l = manager_name.lower()
    keyword_l = [kw.lower() for kw in keywords if kw]

    if manager_name_l in decoded_url:
        return True

    if any(kw in decoded_url for kw in keyword_l):
        return True

    generic_hints = [
        "/home/",
        "/news",
        "fastbull/news",
    ]

    if any(hint in decoded_url for hint in generic_hints):
        return False

    return False


def default_search_queries(manager_name):
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in manager_name)

    if has_chinese:
        return [
            manager_name,
            f"{manager_name} 基金经理",
            f"{manager_name} 持仓",
            f"{manager_name} 季报",
            f"{manager_name} 调仓",
            f"{manager_name} 访谈",
            f"{manager_name} 投资框架",
            f"{manager_name} 最新观点",
            f"{manager_name} 一季报",
            f"{manager_name} 年报",
            f"{manager_name} 四季报",
        ]

    return [
        manager_name,
        f"{manager_name} portfolio",
        f"{manager_name} holdings",
        f"{manager_name} 13F",
        f"{manager_name} interview",
        f"{manager_name} market outlook",
        f"{manager_name} AI stocks",
        f"{manager_name} hedge fund",
    ]


def get_manager_search_queries(manager):
    manager_name = manager["manager_name"]
    queries = manager.get("search_queries") or default_search_queries(manager_name)

    if isinstance(queries, str):
        queries = [queries]

    cleaned = []
    for query in queries:
        query = str(query).strip()
        if query and query not in cleaned:
            cleaned.append(query)

    return cleaned


def build_xueqiu_forum_queries(query):
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in query)

    if has_chinese:
        intent = "调仓 OR 持仓 OR 重仓股 OR 投资策略 OR 明星操作 OR 访谈 OR 最新观点"
        sites = [
            ("Xueqiu", "site:xueqiu.com"),
            ("EastmoneyForum", "site:guba.eastmoney.com"),
            ("EastmoneyFund", "site:fund.eastmoney.com"),
            ("Zhihu", "site:zhihu.com"),
        ]
    else:
        intent = "portfolio OR holdings OR 13F OR interview OR market outlook OR strategy"
        sites = [
            ("SeekingAlpha", "site:seekingalpha.com"),
            ("MarketWatch", "site:marketwatch.com"),
            ("Reddit", "site:reddit.com"),
        ]

    return [(source, f"{query} {intent} {site}") for source, site in sites]


def dedupe_items(items):
    seen = set()
    deduped = []

    for item in items:
        link = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        key = link or title.lower()

        if not key or key in seen:
            continue

        seen.add(key)
        deduped.append(item)

    return deduped


def collect_manager_items(manager):
    manager_name = manager["manager_name"]
    base_rss_feeds = list(manager.get("rss_feeds", []))
    search_queries = get_manager_search_queries(manager)
    has_english_name = all(ord(c) < 128 for c in manager_name)
    lang = "en-US" if has_english_name else "zh-CN"
    region = "US" if has_english_name else "CN"
    items = []

    rss_feeds = []
    seen_feed = set()
    for feed in base_rss_feeds:
        if feed and feed not in seen_feed:
            seen_feed.add(feed)
            rss_feeds.append(feed)

    for rss_url in rss_feeds:
        try:
            print(f"读取 RSS：{rss_url}")
            items.extend(fetch_rss_items(rss_url, limit=per_rss_limit, source="RSS"))
        except Exception as e:
            print(f"RSS 抓取失败，继续下一项：{rss_url}，原因：{e}")

    for query in search_queries:
        try:
            google_rss = build_google_news_rss(query, lang=lang, region=region)
            print(f"读取 Google News：{query}")
            items.extend(fetch_rss_items(google_rss, limit=per_rss_limit, source="Google"))
        except Exception as e:
            print(f"Google News 抓取失败，继续下一项：{query}，原因：{e}")

        for source, forum_query in build_xueqiu_forum_queries(query):
            try:
                forum_rss = build_google_news_rss(forum_query, lang=lang, region=region)
                print(f"读取 {source}：{forum_query}")
                items.extend(fetch_rss_items(forum_rss, limit=per_rss_limit, source=source))
            except Exception as e:
                print(f"{source} 抓取失败，继续下一项：{forum_query}，原因：{e}")

    items = dedupe_items(items)
    print(f"{manager_name} 合并去重后发现文章数：{len(items)}")
    return items


def now_utc():
    return datetime.now(timezone.utc)


def parse_supabase_time(value):
    if not value:
        return None

    try:
        value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except Exception:
        return None


def clamp_score(value, low=0, high=100):
    try:
        value = int(round(value))
    except Exception:
        value = low

    return max(low, min(high, value))


def safe_pct(value):
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def call_deepseek_text(prompt, system_role, max_tokens=1600, temperature=0.2):
    retry_delays = [2, 5, 8]

    for attempt, delay in enumerate(retry_delays, start=1):
        try:
            client = get_deepseek_client()
            if client is None:
                return ""
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_role},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"DeepSeek 调用失败，第 {attempt} 次：{e}")
            time.sleep(delay)

    return ""


def fetch_manager_rules(manager_name, limit=80):
    try:
        res = (
            supabase
            .table("manager_rules")
            .select("rule_type, content, source")
            .eq("manager_name", manager_name)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"读取 manager_rules 失败：{manager_name}，原因：{e}")
        return []


def get_today_market_style(market_data=None, news_titles=None):
    """
    输入字段可以来自行情脚本或 App：
    a_share_index, hk_index, nasdaq, usd_jpy, gold,
    semiconductor_etf, new_energy_etf, nonferrous_etf。
    数值建议传日涨跌幅百分比；缺失时按中性处理。
    """
    market_data = market_data or {}
    news_titles = news_titles or []

    a_share = safe_pct(market_data.get("a_share_index"))
    hk = safe_pct(market_data.get("hk_index"))
    nasdaq = safe_pct(market_data.get("nasdaq"))
    usd_jpy = safe_pct(market_data.get("usd_jpy"))
    gold = safe_pct(market_data.get("gold"))
    semiconductor = safe_pct(market_data.get("semiconductor_etf"))
    new_energy = safe_pct(market_data.get("new_energy_etf"))
    nonferrous = safe_pct(market_data.get("nonferrous_etf"))

    sector_scores = {
        "半导体": semiconductor,
        "新能源": new_energy,
        "有色金属": nonferrous,
        "港股": hk,
        "美股科技": nasdaq,
        "黄金避险": gold,
    }
    strong_sectors = [name for name, score in sector_scores.items() if score >= 0.8]
    weak_sectors = [name for name, score in sector_scores.items() if score <= -0.8]

    risk_score = 0
    risk_score += 1 if a_share > 0 else -1 if a_share < -0.7 else 0
    risk_score += 1 if hk > 0 else -1 if hk < -0.7 else 0
    risk_score += 1 if nasdaq > 0 else -1 if nasdaq < -0.7 else 0
    risk_score += 1 if semiconductor > 0.8 else 0
    risk_score += 1 if new_energy > 0.8 else 0
    risk_score += 1 if nonferrous > 0.8 else 0
    risk_score -= 1 if gold > 0.8 else 0
    risk_score -= 1 if usd_jpy > 0.8 else 0

    joined_news = "\n".join(news_titles)
    if any(word in joined_news for word in ["降息", "宽松", "回购", "AI", "算力", "政策支持"]):
        risk_score += 1
    if any(word in joined_news for word in ["监管", "问询", "暴雷", "减持", "地缘", "通胀"]):
        risk_score -= 1

    if risk_score >= 3:
        risk_preference = "偏进攻"
    elif risk_score <= -2:
        risk_preference = "偏防守"
    else:
        risk_preference = "中性震荡"

    if semiconductor >= max(new_energy, nonferrous, hk, gold, nasdaq):
        dominant_style = "科技成长 / 半导体"
        recommended_categories = ["科技成长", "AI基础设施"]
    elif hk >= max(semiconductor, new_energy, nonferrous, gold, nasdaq):
        dominant_style = "港股修复 / 出海资产"
        recommended_categories = ["QDII港股出海", "激进价值"]
    elif gold >= max(semiconductor, new_energy, nonferrous, hk, nasdaq):
        dominant_style = "避险防守 / 黄金资产"
        recommended_categories = ["全球宏观", "深度价值"]
    elif nonferrous >= max(semiconductor, new_energy, hk, gold, nasdaq):
        dominant_style = "周期资源 / 有色金属"
        recommended_categories = ["深度价值", "全球宏观"]
    elif nasdaq > 0:
        dominant_style = "美股 AI / 全球科技"
        recommended_categories = ["AI基础设施", "多策略平台"]
    else:
        dominant_style = "均衡震荡 / 低胜率等待"
        recommended_categories = ["深度价值", "全球宏观", "多策略风控"]

    if risk_preference == "偏防守":
        unsuitable = ["高位题材股", "无盈利小盘股", "高杠杆周期股", "低流动性港股"]
    elif risk_preference == "偏进攻":
        unsuitable = ["纯防守低弹性股票", "缺少催化的低成交标的"]
    else:
        unsuitable = ["连续急涨且无基本面确认的股票", "消息面不透明股票"]

    result = {
        "dominant_style": dominant_style,
        "risk_preference": risk_preference,
        "strong_sectors": strong_sectors,
        "weak_sectors": weak_sectors,
        "recommended_manager_categories": recommended_categories,
        "unsuitable_stock_types": unsuitable,
        "raw_scores": {
            "a_share_index": a_share,
            "hk_index": hk,
            "nasdaq": nasdaq,
            "usd_jpy": usd_jpy,
            "gold": gold,
            "semiconductor_etf": semiconductor,
            "new_energy_etf": new_energy,
            "nonferrous_etf": nonferrous,
        },
    }
    print(f"今日市场风格：{result}")
    return result


def calculate_manager_score(manager, items=None, saved_rules_count=0, market_style=None):
    manager_name = manager["manager_name"]
    items = items or []
    market_style = market_style or get_today_market_style()
    rules = fetch_manager_rules(manager_name)

    category = manager.get("category", "")
    use_case_text = " ".join(manager.get("use_case", []))
    rule_text = "\n".join(rule.get("content", "") for rule in rules)
    full_text = f"{category}\n{use_case_text}\n{rule_text}"

    recommended = market_style.get("recommended_manager_categories", [])
    strong_sectors = market_style.get("strong_sectors", [])

    market_fit_score = 45
    if category in recommended:
        market_fit_score += 35
    for sector in strong_sectors:
        if sector and sector in full_text:
            market_fit_score += 8
    if market_style.get("risk_preference") == "偏防守" and any(
        word in full_text for word in ["风险", "防守", "低估值", "宏观", "价值"]
    ):
        market_fit_score += 10

    rule_types = {rule.get("rule_type", "") for rule in rules}
    style_clarity_score = 35 + len(rule_types) * 8 + min(len(rules), 20)

    recent_activity_score = 20 + min(len(items) * 5, 45) + min(saved_rules_count * 12, 35)

    risk_words = ["风险", "回撤", "防守", "低估值", "现金流", "纪律", "仓位", "避险", "安全边际"]
    risk_hits = sum(1 for word in risk_words if word in full_text)
    risk_control_score = 35 + risk_hits * 8

    scores = {
        "manager_name": manager_name,
        "market_fit_score": clamp_score(market_fit_score),
        "style_clarity_score": clamp_score(style_clarity_score),
        "recent_activity_score": clamp_score(recent_activity_score),
        "risk_control_score": clamp_score(risk_control_score),
        "trend_fit_reason": (
            f"今日风格={market_style.get('dominant_style')}；"
            f"风险偏好={market_style.get('risk_preference')}；"
            f"经理类别={category}；发现文章={len(items)}；本轮新增规则={saved_rules_count}"
        ),
    }
    print(f"基金经理评分：{scores}")
    return scores


def save_manager_score(score):
    try:
        supabase.table("manager_scores").insert(score).execute()
        print(f"写入 manager_scores 成功：{score['manager_name']}")
        return True
    except Exception as e:
        print(f"写入 manager_scores 失败：{score.get('manager_name')}，原因：{e}")
        return False


def update_manager_score(manager, items=None, saved_rules_count=0, market_style=None):
    score = calculate_manager_score(
        manager=manager,
        items=items,
        saved_rules_count=saved_rules_count,
        market_style=market_style,
    )
    save_manager_score(score)
    return score


def save_run_status(status, detail):
    payload = {
        "ticker": "SYSTEM",
        "market_type": "AUTO",
        "report_type": "auto_run_status",
        "report_content": json.dumps({
            "job": "auto_manager_feeder",
            "status": status,
            "detail": detail,
            "run_at_utc": datetime.utcnow().isoformat()
        }, ensure_ascii=False),
        "created_at": datetime.utcnow().isoformat()
    }

    try:
        supabase.table("stock_reports").insert(payload).execute()
    except Exception as e:
        print(f"写入 auto_manager_feeder 心跳失败：{e}")


def get_cached_stock_report(ticker, market_type="", report_type="stock_diagnosis", cache_hours=6):
    try:
        query = (
            supabase
            .table("stock_reports")
            .select("report_content, created_at")
            .eq("ticker", ticker)
            .eq("report_type", report_type)
            .order("created_at", desc=True)
            .limit(1)
        )
        if market_type:
            query = query.eq("market_type", market_type)

        res = query.execute()
        rows = res.data or []
        if not rows:
            return None

        created_at = parse_supabase_time(rows[0].get("created_at"))
        if created_at and now_utc() - created_at <= timedelta(hours=cache_hours):
            print(f"命中股票诊断缓存：{ticker}，created_at={rows[0].get('created_at')}")
            return rows[0].get("report_content", "")
    except Exception as e:
        print(f"读取 stock_reports 缓存失败：{ticker}，原因：{e}")

    return None


def save_stock_report(ticker, market_type, report_type, report_content):
    try:
        supabase.table("stock_reports").insert({
            "ticker": ticker,
            "market_type": market_type,
            "report_type": report_type,
            "report_content": report_content,
        }).execute()
        print(f"写入 stock_reports 成功：{ticker} / {report_type}")
    except Exception as e:
        print(f"写入 stock_reports 失败：{ticker}，原因：{e}")


def check_risk_veto(ticker, market):
    market_info = market if isinstance(market, dict) else {"market_type": market}
    market_type = str(market_info.get("market_type", "")).upper()
    news_titles = market_info.get("news_titles", []) or []
    joined_news = "\n".join(str(title) for title in news_titles)
    reasons = []

    ticker_upper = str(ticker).upper()
    recent_gain_pct = safe_pct(market_info.get("recent_gain_pct"))
    goodwill_ratio = safe_pct(market_info.get("goodwill_ratio"))
    pledge_ratio = safe_pct(market_info.get("pledge_ratio"))
    short_ratio = safe_pct(market_info.get("short_ratio"))
    valuation_percentile = safe_pct(market_info.get("valuation_percentile"))
    liquidity_score = safe_pct(market_info.get("liquidity_score"))
    rate_change = safe_pct(market_info.get("rate_change"))

    if market_type in {"A", "A股", "CN", "CHINA", "ASHARE"}:
        if "ST" in ticker_upper or "ST" in joined_news:
            reasons.append("A股风险：ST 或疑似退市风险")
        if any(word in joined_news for word in ["监管问询", "问询函", "立案调查"]):
            reasons.append("A股风险：监管问询或立案调查")
        if any(word in joined_news for word in ["财务造假", "会计差错", "审计保留"]):
            reasons.append("A股风险：财务真实性存疑")
        if goodwill_ratio >= 35:
            reasons.append(f"A股风险：商誉占比过高（{goodwill_ratio}%）")
        if pledge_ratio >= 40:
            reasons.append(f"A股风险：股东质押比例过高（{pledge_ratio}%）")
        if recent_gain_pct >= 35:
            reasons.append(f"A股风险：短期涨幅过大（{recent_gain_pct}%）")

    elif market_type in {"US", "美股", "USA"}:
        if any(word in joined_news for word in ["missed earnings", "earnings miss", "财报暴雷"]):
            reasons.append("美股风险：财报低于预期或暴雷")
        if any(word in joined_news for word in ["guidance cut", "lowered guidance", "指引下修"]):
            reasons.append("美股风险：公司指引下修")
        if any(word in joined_news for word in ["insider selling", "内部卖出", "executive sells"]):
            reasons.append("美股风险：内部人卖出")
        if valuation_percentile >= 85 and rate_change > 0:
            reasons.append("美股风险：高估值叠加利率上行")

    elif market_type in {"HK", "港股", "HONGKONG"}:
        if liquidity_score and liquidity_score <= 25:
            reasons.append(f"港股风险：流动性差（score={liquidity_score}）")
        if short_ratio >= 20:
            reasons.append(f"港股风险：沽空比例较高（{short_ratio}%）")
        if any(word in joined_news for word in ["大股东减持", "控股股东减持", "major shareholder sells"]):
            reasons.append("港股风险：大股东减持")
        if any(word in joined_news for word in ["仙股", "合股", "长期低价"]):
            reasons.append("港股风险：仙股化或长期低价")

    else:
        if any(word in joined_news for word in ["财务造假", "监管", "暴雷", "减持", "guidance cut"]):
            reasons.append("通用风险：新闻触发重大负面关键词")

    result = {
        "ticker": ticker,
        "market_type": market_type,
        "risk_flag": bool(reasons),
        "reasons": reasons,
        "can_analyze": not reasons,
    }
    print(f"风险一票否决检查：{result}")
    return result


def diagnose_stock_with_cache(
    ticker,
    market_type="",
    report_type="stock_diagnosis",
    context="",
    market=None,
    force_refresh=False,
):
    if not force_refresh:
        cached = get_cached_stock_report(
            ticker=ticker,
            market_type=market_type,
            report_type=report_type,
            cache_hours=6,
        )
        if cached:
            return cached

    veto = check_risk_veto(ticker, market or market_type)
    prompt = f"""
请为股票 {ticker} 生成诊断报告。

市场类型：{market_type}
风险一票否决结果：{json.dumps(veto, ensure_ascii=False)}

补充资料：
{context}

请输出：
1. 是否可继续分析
2. 核心机会
3. 核心风险
4. 关键验证信号
5. 操作建议：进攻 / 防守 / 观察 / 回避
6. 如果触发风险一票否决，请把风险放在最前面
"""
    report = call_deepseek_text(
        prompt=prompt,
        system_role="你是严谨的股票诊断与风控助手，只能基于给定资料分析，不得编造实时数据。",
        max_tokens=1800,
        temperature=0.15,
    )
    if not report:
        report = f"风险检查：{json.dumps(veto, ensure_ascii=False)}\nDeepSeek 暂时不可用，未生成新诊断。"

    save_stock_report(ticker, market_type, report_type, report)
    return report


def log_trade_review(ticker, action, buy_price=None, sell_price=None, reason="", result=""):
    prompt = f"""
请复盘这笔交易，重点分析交易纪律。

股票：{ticker}
动作：{action}
买入价：{buy_price}
卖出价：{sell_price}
交易理由：{reason}
结果：{result}

请只输出一段 lesson，不超过 120 字，必须具体、可执行。
"""
    lesson = call_deepseek_text(
        prompt=prompt,
        system_role="你是交易复盘教练，擅长把交易行为提炼成下一次可执行的纪律。",
        max_tokens=300,
        temperature=0.2,
    ).strip()

    if not lesson:
        lesson = "复盘未生成：请补充买卖价格、理由和结果，下一次至少明确入场条件、退出条件和仓位纪律。"

    row = {
        "ticker": ticker,
        "action": action,
        "buy_price": buy_price,
        "sell_price": sell_price,
        "reason": reason,
        "result": result,
        "lesson": lesson,
    }

    try:
        supabase.table("trade_reviews").insert(row).execute()
        print(f"写入 trade_reviews 成功：{ticker} / {action}")
    except Exception as e:
        print(f"写入 trade_reviews 失败：{ticker}，原因：{e}")

    try:
        supabase.table("brain_memory").insert({
            "memory_type": "trade_review",
            "content": f"{ticker} {action}：{lesson}",
        }).execute()
        print("已同步交易复盘到 brain_memory")
    except Exception as e:
        print(f"同步 brain_memory 失败，可忽略：{e}")

    return row


def fetch_recent_brain_memory(limit=30):
    try:
        res = (
            supabase
            .table("brain_memory")
            .select("memory_type, content")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"读取 brain_memory 失败：{e}")
        return []


def fetch_latest_manager_scores(limit=30):
    try:
        res = (
            supabase
            .table("manager_scores")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"读取 manager_scores 失败：{e}")
        return []


def generate_today_focus_pool(market_data=None, news_titles=None):
    market_style = get_today_market_style(market_data=market_data, news_titles=news_titles)
    scores = fetch_latest_manager_scores()
    memories = fetch_recent_brain_memory()

    def total_score(row):
        return (
            int(row.get("market_fit_score") or 0)
            + int(row.get("style_clarity_score") or 0)
            + int(row.get("recent_activity_score") or 0)
            + int(row.get("risk_control_score") or 0)
        )

    top_managers = sorted(scores, key=total_score, reverse=True)[:8]
    memory_text = "\n".join(item.get("content", "") for item in memories[:12])

    prompt = f"""
请生成今日关注池。

今日市场风格：
{json.dumps(market_style, ensure_ascii=False, indent=2)}

今日适配大师：
{json.dumps(top_managers, ensure_ascii=False, indent=2)}

交易外脑：
{memory_text}

请严格按 JSON 输出，包含五个 key：
offensive 进攻型
defensive 防守型
hk_rebound 港股反弹型
us_ai 美股AI型
watch_only 只观察不买型

每个 key 的值是数组，每个元素包含 ticker、reason、matched_manager、risk_note。
不要编造实时价格。
"""
    content = call_deepseek_text(
        prompt=prompt,
        system_role="你是今日股票关注池生成器，必须把风险放在机会前面，不能编造实时数据。",
        max_tokens=2200,
        temperature=0.2,
    )

    if not content:
        content = json.dumps({
            "offensive": [],
            "defensive": [],
            "hk_rebound": [],
            "us_ai": [],
            "watch_only": [
                {
                    "ticker": "",
                    "reason": "DeepSeek 暂时不可用，今日只观察。",
                    "matched_manager": "",
                    "risk_note": "缺少新生成的关注池",
                }
            ],
        }, ensure_ascii=False, indent=2)

    save_stock_report(
        ticker="__TODAY_FOCUS_POOL__",
        market_type="GLOBAL",
        report_type="today_focus_pool",
        report_content=content,
    )
    print("今日关注池已生成并写入 stock_reports 缓存")
    return content


def run_auto_feed(max_articles_per_manager=max_articles_per_manager, per_rss_limit=per_rss_limit):
    with open("sources.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    managers = config.get("managers", [])
    today_market_style = get_today_market_style()
    total_found = 0
    total_skipped = 0
    total_processed_articles = 0
    total_saved_rules = 0

    for manager in managers:
        manager_name = manager["manager_name"]
        keywords = list(manager.get("keywords", []))

        if manager_name not in keywords:
            keywords.append(manager_name)

        print(f"\n========== 开始扫描：{manager_name} ==========")
        search_queries = get_manager_search_queries(manager)
        print(f"search_queries({len(search_queries)}): {search_queries}")

        items = collect_manager_items(manager)
        manager_found = len(items)
        total_found += manager_found
        manager_skipped = 0
        manager_saved_rules = 0
        manager_processed_articles = 0

        if not items:
            print("本轮暂时没有抓到内容，跳过。")
            print(
                f"扫描完成：经理={manager_name}，发现文章={manager_found}，跳过={manager_skipped}，"
                f"处理文章={manager_processed_articles}，成功写入规则={manager_saved_rules}"
            )
            update_manager_score(
                manager=manager,
                items=items,
                saved_rules_count=manager_saved_rules,
                market_style=today_market_style,
            )
            continue

        for item in items:
            if manager_processed_articles >= max_articles_per_manager:
                print(f"已达到经理文章处理上限 {max_articles_per_manager}，停止本轮。")
                break

            try:
                title = item["title"]
                link = item["link"]
                summary = item.get("summary", "")
                published = item.get("published", "")
                source_name = item.get("source", "RSS")

                print(f"\n发现文章：[{source_name}] {title}")
                print(link)

                if already_processed(link):
                    manager_skipped += 1
                    total_skipped += 1
                    print("已处理过，跳过。")
                    continue

                text = fetch_page_text(link)

                combined_text = f"""
标题：{title}
发布时间：{published}
链接：{link}
来源：{source_name}

RSS摘要：
{summary}

网页正文：
{text}

说明：
如果网页正文为空，也请基于标题和RSS摘要提炼可能的投资信息。
"""

                is_targeted_feed = source_name in {
                    "Google",
                    "Xueqiu",
                    "EastmoneyForum",
                    "EastmoneyFund",
                    "Zhihu",
                    "SeekingAlpha",
                    "MarketWatch",
                    "Reddit",
                } or (
                    source_name == "RSS"
                    and is_targeted_rss(item.get("feed_url", ""), manager_name, keywords)
                )

                if not is_targeted_feed:
                    keyword_text = title + "\n" + summary + "\n" + text + "\n" + link
                    if not manager_keyword_hit(keyword_text, keywords):
                        manager_skipped += 1
                        total_skipped += 1
                        print("泛资讯源关键词不匹配，跳过。")
                        continue

                saved = feed_manager_from_text(
                    manager_name=manager_name,
                    raw_text=combined_text,
                    source=link
                )

                manager_processed_articles += 1
                manager_saved_rules += saved
                total_processed_articles += 1
                total_saved_rules += saved

                if saved > 0:
                    mark_processed(manager_name, link, title)
                    print(f"文章处理完成，新增规则：{saved}，已记录为处理成功。")
                else:
                    print("文章处理完成，但新增规则为 0。暂不记录 processed_sources，下次仍可重试。")

                time.sleep(2)

            except Exception as e:
                manager_skipped += 1
                total_skipped += 1
                print(f"处理单篇文章失败，继续下一篇：{e}")
                continue

        print(
            f"扫描完成：经理={manager_name}，发现文章={manager_found}，跳过={manager_skipped}，"
            f"处理文章={manager_processed_articles}，成功写入规则={manager_saved_rules}"
        )

        update_manager_score(
            manager=manager,
            items=items,
            saved_rules_count=manager_saved_rules,
            market_style=today_market_style,
        )

    detail = {
        "managers": len(managers),
        "found": total_found,
        "skipped": total_skipped,
        "processed_articles": total_processed_articles,
        "saved_rules": total_saved_rules,
    }
    print(f"auto_manager_feeder 运行完成：{detail}")
    save_run_status("ok", detail)


if __name__ == "__main__":
    run_auto_feed()
