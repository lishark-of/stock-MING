import argparse
import datetime
import hashlib
import json
import re
import time
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from supabase import create_client

from config import get_deepseek_keys, get_supabase_config
from data_fetcher import (
    alias_matches_news_text,
    build_google_news_rss,
    filter_news_clues_for_prompt,
    get_supply_chain_profile,
    has_short_ticker_news_noise,
    infer_market_type,
    normalize_news_title,
    normalize_ticker,
    score_news_relevance,
    ticker_core,
)


TARGETS_FILE = Path(__file__).resolve().with_name("announcement_targets.json")
WATCHLIST_TICKER = "__ANNOUNCEMENT_WATCHLIST__"
WATCHLIST_REPORT_TYPE = "announcement_watchlist"
NEWS_DIGEST_REPORT_TYPE = "news_digest"
BUILTIN_TARGET_NAME_MAP = {
    "002008.SZ": "大族激光",
    "002008": "大族激光",
    "601138.SH": "工业富联",
    "601138": "工业富联",
    "600481.SH": "双良节能",
    "600481": "双良节能",
}
DEFAULT_WINDOW_HOURS = 48
DEFAULT_ITEM_LIMIT = 5
DEFAULT_DIGEST_TOP = 8
MAX_QUERY_ALIASES = 4
MAX_PAGE_TEXT_CHARS = 10000

_token_index = 0


def get_deepseek_client():
    global _token_index

    tokens = get_deepseek_keys()
    if not tokens:
        return None

    token = tokens[_token_index]
    _token_index = (_token_index + 1) % len(tokens)
    return OpenAI(api_key=token, base_url="https://api.deepseek.com/v1")


def call_deepseek_text(prompt, system_role, max_tokens=1600, temperature=0.1):
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
        except Exception as exc:
            print(f"DeepSeek 新闻消化失败，第 {attempt} 次：{exc}")
            time.sleep(delay)
    return ""


def create_supabase_client():
    url, key = get_supabase_config()
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception as exc:
        print(f"Supabase 初始化失败：{exc}")
        return None


def normalize_target_code(raw_code):
    text = str(raw_code or "").upper().strip().replace(" ", "").replace("。", ".")
    if not text:
        return ""
    text = text.replace(".SS", ".SH")
    if re.fullmatch(r"\d{6}\.(SZ|SH|BJ|HK|T)", text):
        return text
    if re.fullmatch(r"\d{6}", text):
        if text.startswith(("6", "9")):
            return f"{text}.SH"
        if text.startswith(("0", "2", "3")):
            return f"{text}.SZ"
        if text.startswith(("4", "8")):
            return f"{text}.BJ"
    return text


def normalize_target(item):
    ts_code = normalize_target_code(item.get("ts_code") or item.get("ticker") or item.get("stock_code"))
    name = resolve_target_name(ts_code, item.get("name") or item.get("stock_name"))
    return {
        "ts_code": ts_code,
        "stock_code": ts_code.split(".")[0] if ts_code else "",
        "name": name,
        "market_type": str(item.get("market_type") or infer_market_type(ts_code) or "").strip() or infer_market_type(ts_code),
    }


def dedupe_targets(targets):
    seen = set()
    result = []
    for target in targets or []:
        ts_code = str(target.get("ts_code") or "").strip().upper()
        if not ts_code or ts_code in seen:
            continue
        seen.add(ts_code)
        result.append(target)
    return result


def load_json_targets(path=TARGETS_FILE):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"读取 {path} 失败：{exc}")
        return []

    if isinstance(data, dict):
        raw_items = data.get("targets") or []
    elif isinstance(data, list):
        raw_items = data
    else:
        raw_items = []
    return dedupe_targets([target for target in (normalize_target(item) for item in raw_items) if target.get("ts_code")])


def load_builtin_targets():
    return dedupe_targets(
        [
            normalize_target({"ts_code": "002008.SZ", "name": "大族激光"}),
            normalize_target({"ts_code": "601138.SH", "name": "工业富联"}),
            normalize_target({"ts_code": "600481.SH", "name": "双良节能"}),
        ]
    )


def resolve_target_name(ts_code, stock_name=""):
    name = str(stock_name or "").strip()
    if name:
        return name

    normalized = normalize_target_code(ts_code)
    core = ticker_core(normalized) if normalized else ""
    try:
        profile = get_supply_chain_profile(normalized or ts_code)
    except Exception:
        profile = {}
    profile_name = str(profile.get("name") or "").strip()
    normalized_terms = {
        str(normalized or "").strip().upper(),
        str(normalize_ticker(normalized or ts_code) or "").strip().upper(),
        str(core or "").strip().upper(),
    }
    if profile_name and profile_name.strip().upper() not in normalized_terms:
        return profile_name

    for key in [normalized, core]:
        mapped = BUILTIN_TARGET_NAME_MAP.get(str(key or "").strip().upper())
        if mapped:
            return mapped
    return ""


def parse_watchlist_payload(content):
    try:
        data = json.loads(content) if isinstance(content, str) else (content or {})
    except Exception as exc:
        return [], f"watchlist JSON 解析失败：{exc}"

    if not isinstance(data, dict):
        return [], "watchlist 不是 JSON object"

    raw_targets = data.get("targets")
    if not isinstance(raw_targets, list):
        return [], "watchlist.targets 不是数组"

    enabled_targets = []
    for item in raw_targets:
        if not isinstance(item, dict):
            continue
        if item.get("enabled") is False:
            continue
        target = normalize_target(item)
        if target.get("ts_code"):
            enabled_targets.append(target)
    return dedupe_targets(enabled_targets), ""


def load_supabase_watchlist_targets(supabase):
    if not supabase:
        return None, "Supabase 不可用"
    try:
        res = (
            supabase.table("stock_reports")
            .select("report_content, created_at")
            .eq("ticker", WATCHLIST_TICKER)
            .eq("report_type", WATCHLIST_REPORT_TYPE)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        return None, f"读取 announcement_watchlist 失败：{exc}"

    rows = res.data or []
    if not rows:
        return None, "Supabase 未找到 announcement_watchlist"

    targets, error = parse_watchlist_payload(rows[0].get("report_content", ""))
    if error:
        return None, error
    return targets, ""


def load_targets_for_run(supabase=None, use_supabase_watchlist=False):
    if use_supabase_watchlist:
        targets, error = load_supabase_watchlist_targets(supabase)
        if targets is not None:
            return targets, "supabase_watchlist", ""
        print(f"Supabase watchlist 不可用，尝试 fallback：{error}")

    json_targets = load_json_targets()
    if json_targets:
        return json_targets, "json_fallback", ""

    builtin_targets = load_builtin_targets()
    return builtin_targets, "builtin_default", ""


def normalize_profile_aliases(ticker, stock_name=""):
    aliases = []
    normalized = normalize_target_code(ticker)
    core = ticker_core(normalized) if normalized else ""
    resolved_name = resolve_target_name(normalized or ticker, stock_name)
    profile = {}
    try:
        profile = get_supply_chain_profile(normalized or ticker)
    except Exception:
        profile = {}

    for value in [
        ticker,
        normalized,
        core,
        resolved_name,
        profile.get("name", ""),
    ]:
        text = str(value or "").strip()
        if text:
            aliases.append(text)
    for value in profile.get("aliases") or []:
        text = str(value or "").strip()
        if text:
            aliases.append(text)

    result = []
    seen = set()
    for alias in aliases:
        alias = str(alias or "").strip()
        if len(alias) < 2:
            continue
        if alias not in seen:
            seen.add(alias)
            result.append(alias)
    return result


def build_supabase_or_filter(aliases, columns):
    filters = []
    for alias in aliases or []:
        alias = str(alias or "").strip()
        if len(alias) < 2:
            continue
        safe = alias.replace(",", " ").replace("(", " ").replace(")", " ")
        for column in columns:
            filters.append(f"{column}.ilike.%{safe}%")
    return ",".join(filters[:32])


def fetch_supabase_candidates(supabase, ticker, stock_name, hours, limit):
    if not supabase:
        return []

    aliases = normalize_profile_aliases(ticker, stock_name)
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=int(hours or DEFAULT_WINDOW_HOURS))
    candidate_limit = min(max(int(limit or 0), 1), 20)
    rows = []

    try:
        query = (
            supabase.table("market_news")
            .select("keyword, title, url, summary, risk_tag, sentiment, created_at")
            .gte("created_at", cutoff.isoformat())
        )
        alias_filter = build_supabase_or_filter(aliases, ("keyword", "title", "summary"))
        if alias_filter:
            query = query.or_(alias_filter)
        res = query.order("created_at", desc=True).limit(candidate_limit).execute()
        for row in res.data or []:
            item = dict(row)
            item["source"] = "market_news"
            item["source_tier"] = 3
            rows.append(item)
    except Exception as exc:
        print(f"读取 market_news 候选失败：{exc}")

    try:
        query = (
            supabase.table("processed_sources")
            .select("manager_name, title, url, created_at")
            .gte("created_at", cutoff.isoformat())
        )
        alias_filter = build_supabase_or_filter(aliases, ("title",))
        if alias_filter:
            query = query.or_(alias_filter)
        res = query.order("created_at", desc=True).limit(candidate_limit).execute()
        for row in res.data or []:
            item = dict(row)
            item["source"] = "processed_sources"
            item["source_tier"] = 1
            rows.append(item)
    except Exception as exc:
        print(f"读取 processed_sources 候选失败：{exc}")

    return rows


def _entry_time_to_iso(entry):
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        try:
            dt = datetime.datetime(*parsed[:6], tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    published = getattr(entry, "published", "") or getattr(entry, "updated", "")
    return str(published or "").strip()


def clean_html_text(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(" ", strip=True)


def fetch_page_text(url):
    if not url:
        return ""

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NewsDigestBot/1.0)",
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
        return "\n".join(lines)[:MAX_PAGE_TEXT_CHARS]
    except Exception as exc:
        print(f"抓取新闻正文失败：{url}，原因：{exc}")
        return ""


def fetch_rss_candidates(ticker, stock_name, hours, limit):
    aliases = normalize_profile_aliases(ticker, stock_name)
    queries = []
    for alias in aliases[:MAX_QUERY_ALIASES]:
        lang = "en-US" if alias.isascii() and re.search(r"[A-Za-z]", alias) else "zh-CN"
        region = "US" if lang == "en-US" else "CN"
        queries.append((alias, build_google_news_rss(alias, lang=lang, region=region)))

    rows = []
    candidate_limit = min(max(int(limit or 0), 1), 20)
    seen = set()

    for alias, rss_url in queries:
        feed = feedparser.parse(rss_url)
        for entry in (feed.entries or [])[:candidate_limit]:
            title = str(getattr(entry, "title", "") or "").strip()
            link = str(getattr(entry, "link", "") or getattr(entry, "id", "") or "").strip()
            if not title or not link:
                continue
            dedupe_key = f"{normalize_news_title(title)}|{link}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append(
                {
                    "keyword": alias,
                    "title": title,
                    "summary": clean_html_text(getattr(entry, "summary", "") or ""),
                    "url": link,
                    "created_at": _entry_time_to_iso(entry),
                    "source": "google_news_rss",
                    "source_tier": 2,
                }
            )

    return rows


def candidate_matches_aliases(candidate, aliases):
    blob = " ".join(
        str(candidate.get(k, ""))
        for k in ["keyword", "title", "summary", "url", "manager_name"]
    )
    matched = []
    for alias in aliases or []:
        alias = str(alias or "").strip()
        if len(alias) < 2:
            continue
        if alias_matches_news_text(blob, alias):
            matched.append(alias)
    return list(dict.fromkeys(matched))


def clamp_text(text, limit=220):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def build_local_digest_summary(items):
    titles = [str(item.get("title") or "").strip() for item in items or [] if item.get("title")]
    if not titles:
        return "暂无可验证新闻摘要线索"
    return "；".join(titles[:3])


def normalize_digest_candidate(candidate, target, aliases):
    source = str(candidate.get("source") or "").strip() or "unknown"
    title = str(candidate.get("title") or "").strip()
    if not title:
        return None
    blob = " ".join(
        str(candidate.get(k, ""))
        for k in ["keyword", "title", "summary", "url", "manager_name"]
    )
    matched_aliases = candidate_matches_aliases(candidate, aliases)
    if not matched_aliases and not any(
        alias_matches_news_text(blob, alias) for alias in aliases or []
    ):
        return None
    if has_short_ticker_news_noise(blob, aliases, infer_market_type(target.get("ts_code"))):
        return None

    score = int(candidate.get("relevance_score") or 0)
    if not score:
        score = score_news_relevance(blob, aliases, infer_market_type(target.get("ts_code")))
    source_tier = int(candidate.get("source_tier") or 2)
    if source == "market_news":
        score += 12
    elif source == "google_news_rss":
        score += 8
    elif source == "processed_sources":
        score -= 10
    score += source_tier

    published_at = str(candidate.get("created_at") or candidate.get("published_at") or "").strip()
    summary = clamp_text(candidate.get("summary") or candidate.get("risk_tag") or "", 240)
    return {
        "title": title,
        "url": str(candidate.get("url") or "").strip(),
        "source": source,
        "published_at": published_at,
        "matched_aliases": matched_aliases,
        "relevance_score": max(0, min(100, score)),
        "summary": summary,
        "raw_candidate": candidate,
    }


def fetch_selected_candidates_for_target(target, supabase, hours, limit):
    ticker = target.get("ts_code") or ""
    stock_name = resolve_target_name(ticker, target.get("name") or "")
    aliases = normalize_profile_aliases(ticker, stock_name)
    rows = []
    rows.extend(fetch_supabase_candidates(supabase, ticker, stock_name, hours, limit))
    rows.extend(fetch_rss_candidates(ticker, stock_name, hours, limit))

    filtered = filter_news_clues_for_prompt(
        rows,
        stock_code=ticker,
        stock_name=stock_name,
        aliases=aliases,
        max_items=max(limit * 4, 15),
        hours=hours,
    )

    normalized = []
    seen = set()
    for row in filtered:
        item = normalize_digest_candidate(row, target, aliases)
        if not item:
            continue
        key = f"{normalize_news_title(item['title'])}|{item.get('url','')}"
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)

    source_order = {"market_news": 3, "google_news_rss": 2, "processed_sources": 1}
    normalized.sort(
        key=lambda item: (
            source_order.get(item.get("source"), 0),
            item.get("relevance_score", 0),
            item.get("published_at", ""),
        ),
        reverse=True,
    )
    return normalized[:limit]


def fetch_item_excerpts(items, fetch_pages=True):
    enriched = []
    for item in items or []:
        entry = dict(item)
        excerpt = ""
        if fetch_pages and entry.get("url"):
            excerpt = fetch_page_text(entry["url"])
        entry["excerpt"] = clamp_text(excerpt, 320)
        enriched.append(entry)
    return enriched


def build_digest_prompt(target, items, hours, digest_top):
    aliases = normalize_profile_aliases(target.get("ts_code"), target.get("name"))
    source_blob = []
    for item in items or []:
        source_blob.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "published_at": item.get("published_at", ""),
                "matched_aliases": item.get("matched_aliases", []),
                "summary": item.get("summary", ""),
                "excerpt": item.get("excerpt", ""),
                "relevance_score": item.get("relevance_score", 0),
            }
        )

    return f"""
你是严格的股票新闻消化器。
只能基于给定新闻标题、摘要、正文片段和股票别名消化。
新闻不是公告事实。
risk_tag / sentiment 只是新闻层判断，不等于官方事实。
金额、客户、订单、处罚、诉讼、减持、业绩等只能写入 claims，且 verification_status 必须是“待验证”。
不要预测涨跌。
不要写必买、必卖、满仓、梭哈。

目标股票：
- ticker: {target.get("ts_code", "")}
- stock_code: {target.get("stock_code", "")}
- stock_name: {target.get("name", "")}
- market_type: {target.get("market_type", "")}
- window_hours: {hours}
- digest_top: {digest_top}
- aliases: {aliases}

候选新闻：
{json.dumps(source_blob, ensure_ascii=False, indent=2)}

请只输出 JSON object，不要 markdown，不要解释：
{{
  "digest_type": "news_digest",
  "version": 1,
  "updated_at": "",
  "ticker": "{target.get('ts_code', '')}",
  "stock_code": "{target.get('stock_code', '')}",
  "stock_name": "{target.get('name', '')}",
  "market_type": "{target.get('market_type', '')}",
  "window_hours": {hours},
  "items": [
    {{
      "title": "",
      "url": "",
      "source": "",
      "published_at": "",
      "matched_aliases": [],
      "relevance_score": 0,
      "digest_summary": "",
      "risk_tag": "",
      "sentiment": "",
      "claims": [],
      "clues": [],
      "evidence": [],
      "verification_status": "待验证",
      "source_boundary": "仅基于新闻标题/正文，不构成官方事实"
    }}
  ],
  "one_line_summary": "",
  "risk_tags": [],
  "positive_tags": [],
  "negative_tags": [],
  "needs_manual_review": true,
  "source_boundary": "新闻只能作为待验证线索，不得进入硬事实层"
}}

硬规则：
1. 只基于标题、摘要、正文片段和股票别名消化。
2. 新闻不是公告事实。
3. risk_tag / sentiment 只是新闻层判断，不等于官方事实。
4. 金额、客户、订单、处罚、诉讼、减持、业绩等只能写入 claims，且 verification_status=待验证。
5. 不预测涨跌。
6. 不写必买、必卖、满仓、梭哈。
7. 不得把标题直接升级为官方事实。
8. processed_sources 只能作为更弱的待验证线索。
""".strip()


def parse_json_blob(text):
    if not text:
        return {}
    if isinstance(text, dict):
        return text
    text = str(text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        return {}


def build_heuristic_digest(target, items, hours, digest_top):
    normalized_items = []
    risk_tags = []
    positive_tags = []
    negative_tags = []
    for item in items or []:
        summary = item.get("summary") or ""
        excerpt = item.get("excerpt") or ""
        digest_summary = clamp_text(summary or excerpt or item.get("title") or "", 180)
        risk_tag = "普通新闻"
        sentiment = "中性"
        if str(item.get("source") or "") == "market_news":
            risk_tag = str((item.get("raw_candidate") or {}).get("risk_tag") or "普通新闻")
            sentiment = str((item.get("raw_candidate") or {}).get("sentiment") or "中性")
        normalized_items.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "published_at": item.get("published_at", ""),
                "matched_aliases": item.get("matched_aliases", []),
                "relevance_score": item.get("relevance_score", 0),
                "digest_summary": digest_summary,
                "risk_tag": risk_tag,
                "sentiment": sentiment,
                "claims": [clamp_text(digest_summary, 120)] if digest_summary else [],
                "clues": [
                    f"命中别名：{'、'.join(item.get('matched_aliases', [])[:4])}" if item.get("matched_aliases") else "命中股票关键词"
                ],
                "evidence": [
                    f"标题：{clamp_text(item.get('title'), 160)}",
                    f"链接：{item.get('url', '')}",
                ],
                "verification_status": "待验证",
                "source_boundary": "仅基于新闻标题/正文，不构成官方事实",
            }
        )
        if risk_tag and risk_tag not in {"普通新闻", "未知"}:
            risk_tags.append(risk_tag)
        if sentiment in {"利好", "利空"}:
            if sentiment == "利好":
                positive_tags.append(risk_tag or "利好")
            elif sentiment == "利空":
                negative_tags.append(risk_tag or "利空")

    if not normalized_items:
        one_line_summary = "暂无可验证新闻摘要线索"
    else:
        one_line_summary = "；".join(item["digest_summary"] for item in normalized_items[:3] if item.get("digest_summary"))[:500]

    return {
        "digest_type": "news_digest",
        "version": 1,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ticker": target.get("ts_code", ""),
        "stock_code": target.get("stock_code", ""),
        "stock_name": target.get("name", ""),
        "market_type": target.get("market_type", ""),
        "window_hours": hours,
        "items": normalized_items[:digest_top],
        "one_line_summary": one_line_summary,
        "risk_tags": list(dict.fromkeys(risk_tags))[:8],
        "positive_tags": list(dict.fromkeys(positive_tags))[:8],
        "negative_tags": list(dict.fromkeys(negative_tags))[:8],
        "needs_manual_review": True,
        "source_boundary": "新闻只能作为待验证线索，不得进入硬事实层",
    }


def normalize_digest_payload(target, payload, hours, digest_top):
    if not isinstance(payload, dict):
        return {}

    items = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title:
            continue
        matched_aliases = item.get("matched_aliases") or []
        if isinstance(matched_aliases, str):
            matched_aliases = [matched_aliases]
        items.append(
            {
                "title": title,
                "url": url,
                "source": str(item.get("source") or "").strip() or "unknown",
                "published_at": str(item.get("published_at") or "").strip(),
                "matched_aliases": [str(alias).strip() for alias in matched_aliases if str(alias).strip()],
                "relevance_score": int(item.get("relevance_score") or 0),
                "digest_summary": clamp_text(item.get("digest_summary") or item.get("one_line_summary") or "", 180),
                "risk_tag": str(item.get("risk_tag") or "普通新闻").strip() or "普通新闻",
                "sentiment": str(item.get("sentiment") or "中性").strip() or "中性",
                "claims": item.get("claims") if isinstance(item.get("claims"), list) else [],
                "clues": item.get("clues") if isinstance(item.get("clues"), list) else [],
                "evidence": item.get("evidence") if isinstance(item.get("evidence"), list) else [],
                "verification_status": str(item.get("verification_status") or "待验证"),
                "source_boundary": str(item.get("source_boundary") or "仅基于新闻标题/正文，不构成官方事实"),
                "excerpt": clamp_text(item.get("excerpt") or "", 320),
            }
        )

    normalized = {
        "digest_type": "news_digest",
        "version": int(payload.get("version") or 1),
        "updated_at": str(payload.get("updated_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()),
        "ticker": str(payload.get("ticker") or target.get("ts_code") or ""),
        "stock_code": str(payload.get("stock_code") or target.get("stock_code") or ""),
        "stock_name": str(payload.get("stock_name") or target.get("name") or ""),
        "market_type": str(payload.get("market_type") or target.get("market_type") or ""),
        "window_hours": int(payload.get("window_hours") or hours or DEFAULT_WINDOW_HOURS),
        "items": items[:digest_top],
        "one_line_summary": str(payload.get("one_line_summary") or build_local_digest_summary(items)),
        "risk_tags": [str(x).strip() for x in (payload.get("risk_tags") or []) if str(x).strip()],
        "positive_tags": [str(x).strip() for x in (payload.get("positive_tags") or []) if str(x).strip()],
        "negative_tags": [str(x).strip() for x in (payload.get("negative_tags") or []) if str(x).strip()],
        "needs_manual_review": bool(payload.get("needs_manual_review", True)),
        "source_boundary": str(payload.get("source_boundary") or "新闻只能作为待验证线索，不得进入硬事实层"),
    }
    if normalized["items"] and not normalized["one_line_summary"]:
        normalized["one_line_summary"] = build_local_digest_summary(normalized["items"])
    return normalized


def digest_hash(payload):
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def save_news_digest(supabase, payload):
    if not supabase or not payload:
        return False
    try:
        supabase.table("stock_reports").insert(
            {
                "ticker": payload.get("ticker", ""),
                "market_type": payload.get("market_type", ""),
                "report_type": NEWS_DIGEST_REPORT_TYPE,
                "report_content": json.dumps(payload, ensure_ascii=False, default=str),
            }
        ).execute()
        return True
    except Exception as exc:
        print(f"写入 news_digest 失败：{exc}")
        return False


def run_for_target(
    target,
    supabase,
    dry_run=False,
    simulate_summary=False,
    hours=DEFAULT_WINDOW_HOURS,
    limit=DEFAULT_ITEM_LIMIT,
    digest_top=DEFAULT_DIGEST_TOP,
):
    candidates = fetch_selected_candidates_for_target(target, supabase, hours, limit)
    if not candidates:
        return None, "无候选新闻"

    fetch_pages = not dry_run or simulate_summary
    candidates = fetch_item_excerpts(candidates, fetch_pages=fetch_pages)

    if dry_run or simulate_summary or not get_deepseek_keys():
        payload = build_heuristic_digest(target, candidates, hours, digest_top)
        mode = "heuristic"
    else:
        prompt = build_digest_prompt(target, candidates, hours, digest_top)
        raw = call_deepseek_text(
            prompt,
            system_role="你是严谨的股票新闻消化器，只能基于给定新闻标题、摘要、正文片段和股票别名生成 JSON。",
            max_tokens=2000,
            temperature=0.1,
        )
        payload = normalize_digest_payload(target, parse_json_blob(raw), hours, digest_top)
        if not payload or not payload.get("items"):
            payload = build_heuristic_digest(target, candidates, hours, digest_top)
            mode = "heuristic_fallback"
        else:
            mode = "deepseek"

    payload["digest_hash"] = digest_hash(payload)
    payload["mode"] = mode
    payload["candidate_count"] = len(candidates)
    payload["source_aliases"] = normalize_profile_aliases(target.get("ts_code"), target.get("name"))

    if not payload.get("items"):
        return payload, "无可用新闻条目"

    if dry_run:
        return payload, ""

    saved = save_news_digest(supabase, payload)
    if not saved:
        return payload, "写库失败"
    return payload, ""


def main():
    parser = argparse.ArgumentParser(description="持续调查池新闻消化器 PoC")
    parser.add_argument("--dry-run", action="store_true", help="只打印结果，不写 Supabase，不调用 DeepSeek")
    parser.add_argument("--use-supabase-watchlist", action="store_true", help="优先读取 Supabase announcement_watchlist")
    parser.add_argument("--simulate-summary", action="store_true", help="dry-run 时打印模拟 digest JSON 摘要")
    parser.add_argument("--hours", type=int, default=72, help="回看窗口小时数")
    parser.add_argument("--limit", type=int, default=20, help="每只股票最多保留候选新闻条数")
    parser.add_argument("--digest-top", type=int, default=DEFAULT_DIGEST_TOP, help="每只股票最终保留的高价值线索数")
    args = parser.parse_args()

    supabase = create_supabase_client()
    targets, target_source, target_error = load_targets_for_run(
        supabase=supabase,
        use_supabase_watchlist=args.use_supabase_watchlist,
    )

    print(
        f"[news-digest] target_source={target_source} "
        f"targets={len(targets)} dry_run={bool(args.dry_run)} hours={args.hours} limit={args.limit} digest_top={args.digest_top}"
    )
    if target_error:
        print(f"[news-digest] target_error={target_error}")

    if not targets:
        print("[news-digest] 无可扫描标的。")
        return

    saved_count = 0
    for target in targets:
        target = normalize_target(target)
        payload, error = run_for_target(
            target,
            supabase,
            dry_run=args.dry_run,
            simulate_summary=args.simulate_summary,
            hours=args.hours,
            limit=args.limit,
            digest_top=args.digest_top,
        )
        if not payload:
            print(f"[news-digest] {target.get('ts_code')} 无结果：{error}")
            continue

        print(
            f"[news-digest] {target.get('ts_code')} items={len(payload.get('items') or [])} "
            f"mode={payload.get('mode')} hash={payload.get('digest_hash', '')[:12]}"
        )
        if args.dry_run and args.simulate_summary:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

        if not args.dry_run and error:
            print(f"[news-digest] {target.get('ts_code')} {error}")
        if not args.dry_run and not error and payload.get("items"):
            saved_count += 1

    if args.dry_run:
        print("[news-digest] dry-run 完成：未写库，未调用 DeepSeek。")
    else:
        print(f"[news-digest] 完成：写入 {saved_count} 条 digest。")


if __name__ == "__main__":
    main()
