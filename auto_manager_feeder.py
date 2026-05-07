import json
import time
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from supabase import create_client, Client
import os

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
    try:
        supabase.table("processed_sources").insert({
            "manager_name": manager_name,
            "url": url,
            "url_hash": url_hash(url),
            "title": title
        }).execute()

    except Exception as e:
        print(f"记录已处理链接失败：{e}")


def fetch_rss_items(rss_url, limit=3):
    feed = feedparser.parse(rss_url)
    items = []

    for entry in feed.entries[:limit]:
        title = getattr(entry, "title", "")
        link = getattr(entry, "link", "")

        if title and link:
            items.append({
                "title": title,
                "link": link
            })

    return items


def fetch_page_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ManagerFeederBot/1.0)"
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
        if kw in text:
            return True

    return False


def run_auto_feed():
    with open("sources.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    managers = config.get("managers", [])

    for manager in managers:
        manager_name = manager["manager_name"]
        keywords = manager.get("keywords", [])
        rss_feeds = manager.get("rss_feeds", [])

        # 自动把 manager_name 加进关键词，避免忘写名字导致过滤失败
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

                print(f"\n发现文章：{title}")
                print(link)

                if already_processed(link):
                    print("已处理过，跳过。")
                    continue

                # 先抓正文，不要只靠标题判断
                text = fetch_page_text(link)

                # 如果正文抓不到，就用标题 + 链接也尝试投喂
                combined_text = f"""
标题：{title}
链接：{link}
正文：
{text}
"""

                # 判断是否是“定向 RSS”
                # 如果 RSS 链接里本身包含经理名字，说明这个源就是专门搜这个经理的，可以放宽
                is_targeted_rss = manager_name in rss_url or any(kw in rss_url for kw in keywords)

                # 普通泛资讯源才需要关键词过滤
                if not is_targeted_rss:
                    if not manager_keyword_hit(title + "\n" + text + "\n" + link, keywords):
                        print("标题和正文关键词都不匹配，跳过。")
                        # 注意：这里不要 mark_processed，避免以后关键词改好后无法重新处理
                        continue

                # 如果正文太短，也不要直接放弃，交给 manager_feeder 判断
                saved = feed_manager_from_text(
                    manager_name=manager_name,
                    raw_text=combined_text,
                    source=link
                )

                # 只有处理过的文章才记录，避免无效链接占坑
                mark_processed(manager_name, link, title)

                print(f"文章处理完成，新增规则：{saved}")

                time.sleep(2)
                if __name__ == "__main__":
    run_auto_feed()
