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


def fetch_rss_items(rss_url, limit=8):
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


def build_google_news_rss(query, lang="zh-CN", region="CN"):
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


def run_auto_feed(max_articles_per_manager=5, per_rss_limit=8):
    with open("sources.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    managers = config.get("managers", [])

    for manager in managers:
        manager_name = manager["manager_name"]
        keywords = list(manager.get("keywords", []))
        base_rss_feeds = list(manager.get("rss_feeds", []))
        search_queries = list(manager.get("search_queries", []))

        if manager_name not in keywords:
            keywords.append(manager_name)

        lang = "en-US" if all(ord(c) < 128 for c in manager_name) else "zh-CN"
        region = "US" if lang == "en-US" else "CN"

        generated_rss = [build_google_news_rss(q, lang=lang, region=region) for q in search_queries if q]

        rss_feeds = []
        seen_feed = set()
        for feed in base_rss_feeds + generated_rss:
            if feed and feed not in seen_feed:
                seen_feed.add(feed)
                rss_feeds.append(feed)

        print(f"\n========== 开始扫描：{manager_name} ==========")
        print(f"search_queries({len(search_queries)}): {search_queries}")

        manager_found = 0
        manager_skipped = 0
        manager_saved_rules = 0
        manager_processed_articles = 0

        for rss_url in rss_feeds:
            if manager_processed_articles >= max_articles_per_manager:
                print(f"已达到经理文章处理上限 {max_articles_per_manager}，停止本轮。")
                break

            print(f"读取 RSS：{rss_url}")
            items = fetch_rss_items(rss_url, limit=per_rss_limit)
            manager_found += len(items)

            if not items:
                print("这个 RSS 暂时没有抓到内容，跳过。")
                continue

            for item in items:
                if manager_processed_articles >= max_articles_per_manager:
                    break

                try:
                    title = item["title"]
                    link = item["link"]
                    summary = item.get("summary", "")
                    published = item.get("published", "")

                    print(f"\n发现文章：{title}")
                    print(link)

                    if already_processed(link):
                        manager_skipped += 1
                        print("已处理过，跳过。")
                        continue

                    text = fetch_page_text(link)

                    combined_text = f"""
标题：{title}
发布时间：{published}
链接：{link}

RSS摘要：
{summary}

网页正文：
{text}

说明：
如果网页正文为空，也请基于标题和RSS摘要提炼可能的投资信息。
"""

                    is_targeted_feed = is_targeted_rss(rss_url, manager_name, keywords)

                    if not is_targeted_feed:
                        keyword_text = title + "\n" + summary + "\n" + text + "\n" + link
                        if not manager_keyword_hit(keyword_text, keywords):
                            manager_skipped += 1
                            print("泛资讯源关键词不匹配，跳过。")
                            continue

                    saved = feed_manager_from_text(
                        manager_name=manager_name,
                        raw_text=combined_text,
                        source=link
                    )

                    manager_processed_articles += 1
                    manager_saved_rules += saved

                    if saved > 0:
                        mark_processed(manager_name, link, title)
                        print(f"文章处理完成，新增规则：{saved}，已记录为处理成功。")
                    else:
                        print("文章处理完成，但新增规则为 0。暂不记录 processed_sources，下次仍可重试。")

                    time.sleep(2)

                except Exception as e:
                    manager_skipped += 1
                    print(f"处理单篇文章失败，继续下一篇：{e}")
                    continue

        print(
            f"扫描完成：经理={manager_name}，发现文章={manager_found}，跳过={manager_skipped}，"
            f"处理文章={manager_processed_articles}，成功写入规则={manager_saved_rules}"
        )


if __name__ == "__main__":
    run_auto_feed()
