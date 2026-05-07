import json
import time
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from supabase import create_client, Client
import os
from urllib.parse import unquote_plus

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
    # 只有 manager_rules 真正写入成功后才记录 processed_sources。
    # saved = 0 的链接保留为“未处理”，方便后续优化 prompt 后自动重试。
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
    判断 RSS 是否是为某个经理定向配置的。
    Google News URL 往往是百分号编码，先解码再匹配。
    泛资讯源如 gelonghui/home、fastbull/news 仍需要后续关键词过滤。
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


def run_auto_feed():
    with open("sources.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    managers = config.get("managers", [])

    for manager in managers:
        manager_name = manager["manager_name"]
        keywords = list(manager.get("keywords", []))
        rss_feeds = manager.get("rss_feeds", [])

        if manager_name not in keywords:
            keywords.append(manager_name)

        print(f"\n========== 开始扫描：{manager_name} ==========")

        for rss_url in rss_feeds:
            print(f"读取 RSS：{rss_url}")

            items = fetch_rss_items(rss_url, limit=5)

            if not items:
                print("这个 RSS 暂时没有抓到内容，跳过。")
                continue

            for item in items:
                title = item["title"]
                link = item["link"]
                summary = item.get("summary", "")
                published = item.get("published", "")

                print(f"\n发现文章：{title}")
                print(link)

                if already_processed(link):
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
                        print("泛资讯源关键词不匹配，跳过。")
                        continue

                saved = feed_manager_from_text(
                    manager_name=manager_name,
                    raw_text=combined_text,
                    source=link
                )

                if saved > 0:
                    mark_processed(manager_name, link, title)
                    print(f"文章处理完成，新增规则：{saved}，已记录为处理成功。")
                else:
                    print("文章处理完成，但新增规则为 0。暂不记录 processed_sources，下次仍可重试。")

                time.sleep(2)


if __name__ == "__main__":
    run_auto_feed()
