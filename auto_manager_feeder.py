import json
import time
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from supabase import create_client, Client
import os
from urllib.parse import quote_plus, unquote_plus

from manager_feeder import feed_manager_from_text


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("缺少 SUPABASE_URL，请检查 GitHub Secrets")

if not SUPABASE_KEY:
    raise ValueError("缺少 SUPABASE_KEY，请检查 GitHub Secrets")

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


def build_google_news_rss(query):
    query = (query or "").strip()
    if not query:
        return ""

    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in query)

    if has_chinese:
        return (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        )

    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )


def default_search_queries(manager_name):
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in manager_name)

    if has_chinese:
        return [
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
    rss_feeds = manager.get("rss_feeds", [])
    search_queries = get_manager_search_queries(manager)
    items = []

    for rss_url in rss_feeds:
        try:
            print(f"读取 RSS：{rss_url}")
            items.extend(fetch_rss_items(rss_url, limit=per_rss_limit, source="RSS"))
        except Exception as e:
            print(f"RSS 抓取失败，继续下一项：{rss_url}，原因：{e}")

    for query in search_queries:
        try:
            google_rss = build_google_news_rss(query)
            print(f"读取 Google News：{query}")
            items.extend(fetch_rss_items(google_rss, limit=per_rss_limit, source="Google"))
        except Exception as e:
            print(f"Google News 抓取失败，继续下一项：{query}，原因：{e}")

        for source, forum_query in build_xueqiu_forum_queries(query):
            try:
                forum_rss = build_google_news_rss(forum_query)
                print(f"读取 {source}：{forum_query}")
                items.extend(fetch_rss_items(forum_rss, limit=per_rss_limit, source=source))
            except Exception as e:
                print(f"{source} 抓取失败，继续下一项：{forum_query}，原因：{e}")

    items = dedupe_items(items)
    print(f"{manager_name} 合并去重后发现文章数：{len(items)}")
    return items


def run_auto_feed():
    with open("sources.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    managers = config.get("managers", [])

    for manager in managers:
        manager_name = manager["manager_name"]
        keywords = list(manager.get("keywords", []))

        if manager_name not in keywords:
            keywords.append(manager_name)

        print(f"\n========== 开始扫描：{manager_name} ==========")

        items = collect_manager_items(manager)
        found_count = len(items)
        skipped_count = 0
        processed_count = 0
        saved_count = 0

        if not items:
            print("本轮暂时没有抓到内容，跳过。")
            print(
                f"{manager_name} 本轮统计：发现 {found_count} 篇，"
                f"跳过 {skipped_count} 篇，处理 {processed_count} 篇，"
                f"成功写入规则 {saved_count} 条。"
            )
            continue

        for item in items:
            if processed_count >= max_articles_per_manager:
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
                    skipped_count += 1
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
                        skipped_count += 1
                        print("泛资讯源关键词不匹配，跳过。")
                        continue

                processed_count += 1
                saved = feed_manager_from_text(
                    manager_name=manager_name,
                    raw_text=combined_text,
                    source=link
                )

                saved_count += saved

                if saved > 0:
                    mark_processed(manager_name, link, title)
                    print(f"文章处理完成，新增规则：{saved}，已记录为处理成功。")
                else:
                    print("文章处理完成，但新增规则为 0。暂不记录 processed_sources，下次仍可重试。")

                time.sleep(2)

            except Exception as e:
                print(f"处理单篇文章失败，继续下一篇：{e}")
                continue

        print(
            f"{manager_name} 本轮统计：发现 {found_count} 篇，"
            f"跳过 {skipped_count} 篇，处理 {processed_count} 篇，"
            f"成功写入规则 {saved_count} 条。"
        )


if __name__ == "__main__":
    run_auto_feed()
