import json
import time
import hashlib
import datetime
import re
import requests
import feedparser
from bs4 import BeautifulSoup
from openai import OpenAI
from supabase import create_client, Client

from config import get_deepseek_keys, require_supabase_config

SUPABASE_URL, SUPABASE_KEY = require_supabase_config()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DEEPSEEK_TOKENS = get_deepseek_keys()

_token_index = 0


def get_deepseek_client():
    global _token_index

    if not DEEPSEEK_TOKENS:
        return None

    token = DEEPSEEK_TOKENS[_token_index]
    _token_index = (_token_index + 1) % len(DEEPSEEK_TOKENS)

    return OpenAI(
        api_key=token,
        base_url="https://api.deepseek.com/v1"
    )


def url_hash(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def normalize_news_title(title):
    text = str(title or "").strip().lower()
    text = re.sub(r"\s+-\s+[^-｜|]{2,80}$", "", text)
    text = re.sub(r"[｜|]\s*(新浪财经|东方财富|搜狐网|财富号|yahoo finance|seeking alpha).*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(不斷更新|不断更新|快讯|快報|异动快报|股市要闻|市场)$", "", text, flags=re.IGNORECASE)
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def build_dedupe_key(title, source=None, date=None):
    return normalize_news_title(title) or str(source or date or title or "").strip().lower()


def load_recent_market_news_title_keys(days=7, limit=800):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    try:
        res = (
            supabase
            .table("market_news")
            .select("title, created_at")
            .gte("created_at", cutoff.isoformat())
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {
            normalize_news_title(row.get("title"))
            for row in (res.data or [])
            if normalize_news_title(row.get("title"))
        }
    except Exception as e:
        print(f"读取 market_news 历史标题去重集失败：{e}")
        return set()


WIDE_MARKET_NEWS_LIMITS = {
    "A股新趋势": 5,
    "港股新趋势": 5,
    "机构游资调仓": 5,
    "黄金": 3,
}


def wide_source_limit(keyword, rss_url="", title=""):
    keyword = str(keyword or "")
    source_text = f"{rss_url} {title}".lower()
    if keyword in WIDE_MARKET_NEWS_LIMITS:
        return WIDE_MARKET_NEWS_LIMITS[keyword]
    if "gold+price+market" in source_text or "gold price" in source_text:
        return 3
    if "%E6%9C%BA%E6%9E%84%E8%B0%83%E4%BB%93".lower() in source_text:
        return 5
    if any(term in source_text for term in ["港股市況", "港股走势", "港股走勢", "恒指"]):
        return 5
    return None


def already_saved(url):
    h = url_hash(url)

    try:
        res = (
            supabase
            .table("market_news")
            .select("id")
            .eq("url_hash", h)
            .limit(1)
            .execute()
        )

        return bool(res.data)

    except Exception as e:
        print(f"检查 market_news 去重失败：{e}")
        return False


def fetch_rss_items(rss_url, limit=5):
    feed = feedparser.parse(rss_url)
    items = []

    for entry in feed.entries[:limit]:
        title = getattr(entry, "title", "")
        link = getattr(entry, "link", "")
        summary = clean_html_text(getattr(entry, "summary", ""))
        published = getattr(entry, "published", "")

        if title and link:
            items.append({
                "title": title,
                "link": link,
                "summary": summary,
                "published": published
            })

    return items


def clean_html_text(text):
    if not text:
        return ""

    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(" ", strip=True)


def fetch_page_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MarketNewsBot/1.0)",
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

        return clean_text[:15000]

    except Exception as e:
        print(f"抓取页面失败：{url}，原因：{e}")
        return ""


def keyword_hit(text, aliases):
    if not text:
        return False

    for alias in aliases:
        if alias.lower() in text.lower():
            return True

    return False


def analyze_news_with_deepseek(keyword, title, text, rss_summary=""):
    material = f"""
RSS摘要：
{rss_summary}

网页正文：
{text}
""".strip()

    if not material:
        return {
            "summary": "正文抓取为空，仅保留标题。",
            "risk_tag": "未知",
            "sentiment": "中性",
            "extract_status": "raw_summary_only",
        }

    if not DEEPSEEK_TOKENS:
        return {
            "summary": (rss_summary or title)[:300],
            "risk_tag": "未知",
            "sentiment": "不确定",
            "extract_status": "needs_ai_extract",
        }

    prompt = f"""
你是股票舆情风控助手。

请分析下面这条新闻是否会影响【{keyword}】。

新闻标题：
{title}

新闻材料：
{material[:8000]}

请严格输出三行，格式如下：

summary: 一句话总结新闻核心
risk_tag: 从下面选择一个：监管风险 / 财报风险 / 产业利好 / 产业利空 / 资金异动 / 宏观影响 / 普通新闻 / 未知
sentiment: 从下面选择一个：利好 / 利空 / 中性 / 不确定

要求：
1. 不要编造新闻里没有的信息。
2. 如果正文与关键词关系不强，risk_tag 写普通新闻，sentiment 写中性。
3. 不要输出多余内容。
"""

    retry_delays = [3, 6, 10]

    for attempt, delay in enumerate(retry_delays, start=1):
        try:
            client = get_deepseek_client()
            if client is None:
                break

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "你是严谨的股票舆情风控分析员，只能基于给定新闻判断。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=500
            )

            content = response.choices[0].message.content or ""

            break

        except Exception as e:
            print(f"DeepSeek 舆情分析失败，第 {attempt} 次重试：{e}")
            time.sleep(delay)

    else:
        return {
            "summary": rss_summary[:300] if rss_summary else "DeepSeek 分析失败，仅保存原始标题。",
            "risk_tag": "未知",
            "sentiment": "不确定",
            "extract_status": "needs_ai_extract",
        }

    result = {
        "summary": "",
        "risk_tag": "未知",
        "sentiment": "不确定",
        "extract_status": "extracted",
    }

    for line in content.splitlines():
        line = line.strip()
        normalized = line.replace("：", ":", 1)

        if normalized.startswith("summary:"):
            result["summary"] = normalized.replace("summary:", "", 1).strip()

        elif normalized.startswith("risk_tag:"):
            result["risk_tag"] = normalized.replace("risk_tag:", "", 1).strip()

        elif normalized.startswith("sentiment:"):
            result["sentiment"] = normalized.replace("sentiment:", "", 1).strip()

    if not result["summary"]:
        result["summary"] = content[:200] or rss_summary[:300]

    return result


def save_market_news(keyword, title, url, source, analysis):
    payload = {
        "keyword": keyword,
        "title": title,
        "url": url,
        "url_hash": url_hash(url),
        "source": source,
        "summary": analysis.get("summary", ""),
        "risk_tag": analysis.get("risk_tag", ""),
        "sentiment": analysis.get("sentiment", ""),
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    try:
        supabase.table("market_news").insert(payload).execute()

        print(f"已写入 market_news：{keyword}｜{title}")
        return True

    except Exception as e:
        print(f"写入 market_news 失败：{e}")
        try:
            fallback_payload = dict(payload)
            fallback_payload.pop("created_at", None)
            supabase.table("market_news").insert(fallback_payload).execute()
            print(f"已兼容旧表结构写入 market_news：{keyword}｜{title}")
            return True
        except Exception as retry_error:
            print(f"兼容写入 market_news 仍失败：{retry_error}")
            return False


def save_run_status(status, detail):
    payload = {
        "ticker": "SYSTEM",
        "market_type": "AUTO",
        "report_type": "auto_run_status",
        "report_content": json.dumps({
            "job": "auto_market_news",
            "status": status,
            "detail": detail,
            "run_at_utc": datetime.datetime.utcnow().isoformat()
        }, ensure_ascii=False),
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    try:
        supabase.table("stock_reports").insert(payload).execute()
    except Exception as e:
        print(f"写入 auto_market_news 心跳失败：{e}")


def run_auto_market_news():
    with open("market_sources.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    targets = config.get("targets", [])
    seen_title_keys = set()
    recent_title_keys = load_recent_market_news_title_keys(days=7)
    wide_source_counts = {}
    total_found = 0
    total_saved = 0
    total_skipped = 0
    total_processed = 0
    skipped_duplicate_title_count = 0
    skipped_wide_source_limit_count = 0

    for target in targets:
        keyword = target.get("keyword", "")
        aliases = target.get("aliases", [])
        rss_feeds = target.get("rss_feeds", [])

        print(f"\n========== 扫描市场舆情：{keyword} ==========")

        for rss_url in rss_feeds:
            print(f"读取 RSS：{rss_url}")

            items = fetch_rss_items(rss_url, limit=5)
            total_found += len(items)

            for item in items:
                try:
                    title = item["title"]
                    link = item["link"]
                    summary = item.get("summary", "")
                    published = item.get("published", "")
                    title_key = build_dedupe_key(title)

                    print(f"\n发现新闻：{title}")
                    print(link)
                    if published:
                        print(f"发布时间：{published}")

                    if title_key and title_key in seen_title_keys:
                        print(f"skip duplicate normalized title: {title_key[:80]}")
                        total_skipped += 1
                        skipped_duplicate_title_count += 1
                        continue
                    if title_key and title_key in recent_title_keys:
                        print(f"skip duplicate normalized title from recent market_news: {title_key[:80]}")
                        total_skipped += 1
                        skipped_duplicate_title_count += 1
                        continue

                    if already_saved(link):
                        print("已保存过，跳过。")
                        total_skipped += 1
                        continue

                    if not keyword_hit(title + " " + summary + " " + link, aliases):
                        print("标题关键词不匹配，跳过。")
                        total_skipped += 1
                        continue

                    limit = wide_source_limit(keyword, rss_url, title)
                    if limit is not None:
                        wide_key = keyword or rss_url
                        current_count = wide_source_counts.get(wide_key, 0)
                        if current_count >= limit:
                            print(f"skip wide source limit: {wide_key} limit={limit}")
                            total_skipped += 1
                            skipped_wide_source_limit_count += 1
                            continue
                        wide_source_counts[wide_key] = current_count + 1

                    seen_title_keys.add(title_key)
                    total_processed += 1

                    text = fetch_page_text(link)

                    if text and not keyword_hit(text + title + summary, aliases):
                        print("正文关键词不匹配，跳过。")
                        total_skipped += 1
                        continue

                    analysis = analyze_news_with_deepseek(
                        keyword=keyword,
                        title=title,
                        text=text,
                        rss_summary=summary
                    )

                    inserted = save_market_news(
                        keyword=keyword,
                        title=title,
                        url=link,
                        source=rss_url,
                        analysis=analysis
                    )
                    if inserted:
                        total_saved += 1

                    time.sleep(1)

                except Exception as e:
                    print(f"处理单条市场新闻失败，继续下一条：{e}")
                    total_skipped += 1
                    continue

    detail = {
        "targets": len(targets),
        "found": total_found,
        "saved": total_saved,
        "skipped": total_skipped,
        "fetched_count": total_found,
        "processed_count": total_processed,
        "inserted_count": total_saved,
        "skipped_duplicate_title_count": skipped_duplicate_title_count,
        "skipped_wide_source_limit_count": skipped_wide_source_limit_count,
    }
    print(f"auto_market_news 运行完成：{detail}")
    print(
        "auto_market_news stats: "
        f"fetched_count={total_found}, "
        f"skipped_duplicate_title_count={skipped_duplicate_title_count}, "
        f"skipped_wide_source_limit_count={skipped_wide_source_limit_count}, "
        f"inserted_count={total_saved}, "
        f"processed_count={total_processed}, "
        f"saved_rules_count=0"
    )
    save_run_status("ok", detail)


if __name__ == "__main__":
    run_auto_market_news()
