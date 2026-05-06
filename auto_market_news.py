import os
import json
import time
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from openai import OpenAI
from supabase import create_client, Client


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("缺少 SUPABASE_URL")

if not SUPABASE_KEY:
    raise ValueError("缺少 SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


DEEPSEEK_TOKENS = [
    os.getenv("DEEPSEEK_TOKEN_1"),
    os.getenv("DEEPSEEK_TOKEN_2")
]

DEEPSEEK_TOKENS = [t for t in DEEPSEEK_TOKENS if t]

if not DEEPSEEK_TOKENS:
    raise ValueError("缺少 DEEPSEEK_TOKEN_1 或 DEEPSEEK_TOKEN_2")

_token_index = 0


def get_deepseek_client():
    global _token_index

    token = DEEPSEEK_TOKENS[_token_index]
    _token_index = (_token_index + 1) % len(DEEPSEEK_TOKENS)

    return OpenAI(
        api_key=token,
        base_url="https://api.deepseek.com/v1"
    )


def url_hash(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


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

        if title and link:
            items.append({
                "title": title,
                "link": link
            })

    return items


def fetch_page_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MarketNewsBot/1.0)"
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


def analyze_news_with_deepseek(keyword, title, text):
    if not text:
        return {
            "summary": "正文抓取为空，仅保留标题。",
            "risk_tag": "未知",
            "sentiment": "中性"
        }

    prompt = f"""
你是股票舆情风控助手。

请分析下面这条新闻是否会影响【{keyword}】。

新闻标题：
{title}

新闻正文：
{text[:8000]}

请严格输出三行，格式如下：

summary: 一句话总结新闻核心
risk_tag: 从下面选择一个：监管风险 / 财报风险 / 产业利好 / 产业利空 / 资金异动 / 宏观影响 / 普通新闻 / 未知
sentiment: 从下面选择一个：利好 / 利空 / 中性 / 不确定

要求：
1. 不要编造新闻里没有的信息。
2. 如果正文与关键词关系不强，risk_tag 写普通新闻，sentiment 写中性。
3. 不要输出多余内容。
"""

    try:
        client = get_deepseek_client()

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

        result = {
            "summary": "",
            "risk_tag": "未知",
            "sentiment": "不确定"
        }

        for line in content.splitlines():
            line = line.strip()

            if line.startswith("summary:"):
                result["summary"] = line.replace("summary:", "", 1).strip()

            elif line.startswith("risk_tag:"):
                result["risk_tag"] = line.replace("risk_tag:", "", 1).strip()

            elif line.startswith("sentiment:"):
                result["sentiment"] = line.replace("sentiment:", "", 1).strip()

        if not result["summary"]:
            result["summary"] = content[:200]

        return result

    except Exception as e:
        print(f"DeepSeek 舆情分析失败：{e}")
        return {
            "summary": "DeepSeek 分析失败，仅保存原始标题。",
            "risk_tag": "未知",
            "sentiment": "不确定"
        }


def save_market_news(keyword, title, url, source, analysis):
    try:
        supabase.table("market_news").insert({
            "keyword": keyword,
            "title": title,
            "url": url,
            "url_hash": url_hash(url),
            "source": source,
            "summary": analysis.get("summary", ""),
            "risk_tag": analysis.get("risk_tag", ""),
            "sentiment": analysis.get("sentiment", "")
        }).execute()

        print(f"已写入 market_news：{keyword}｜{title}")

    except Exception as e:
        print(f"写入 market_news 失败：{e}")


def run_auto_market_news():
    with open("market_sources.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    targets = config.get("targets", [])

    for target in targets:
        keyword = target.get("keyword", "")
        aliases = target.get("aliases", [])
        rss_feeds = target.get("rss_feeds", [])

        print(f"\n========== 扫描市场舆情：{keyword} ==========")

        for rss_url in rss_feeds:
            print(f"读取 RSS：{rss_url}")

            items = fetch_rss_items(rss_url, limit=5)

            for item in items:
                title = item["title"]
                link = item["link"]

                print(f"\n发现新闻：{title}")
                print(link)

                if already_saved(link):
                    print("已保存过，跳过。")
                    continue

                if not keyword_hit(title + " " + link, aliases):
                    print("标题关键词不匹配，跳过。")
                    continue

                text = fetch_page_text(link)

                if text and not keyword_hit(text + title, aliases):
                    print("正文关键词不匹配，跳过。")
                    continue

                analysis = analyze_news_with_deepseek(
                    keyword=keyword,
                    title=title,
                    text=text
                )

                save_market_news(
                    keyword=keyword,
                    title=title,
                    url=link,
                    source=rss_url,
                    analysis=analysis
                )

                time.sleep(1)


if __name__ == "__main__":
    run_auto_market_news()
