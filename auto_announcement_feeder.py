import argparse
import datetime
import hashlib
import json
import re
import time

from openai import OpenAI

from announcement_provider import get_cn_announcements_fallback, normalize_ts_code
from announcement_reader import download_and_extract_pdf
from config import get_deepseek_keys, get_deepseek_model, get_supabase_config
from deepseek_safety import (
    DEEPSEEK_SAFETY_REVIEW_MESSAGE,
    build_deepseek_safety_prompt_clause,
    find_deepseek_dangerous_words,
)


TARGETS_FILE = "announcement_targets.json"
DEFAULT_DAYS = 14
DEFAULT_LIMIT = 50
DEFAULT_MAX_PDF_PER_STOCK = 10
WATCHLIST_TICKER = "__ANNOUNCEMENT_WATCHLIST__"
WATCHLIST_REPORT_TYPE = "announcement_watchlist"
BUILTIN_DEFAULT_TARGETS = [
    {"ts_code": "002008.SZ", "name": "大族激光"},
    {"ts_code": "601138.SH", "name": "工业富联"},
    {"ts_code": "600481.SH", "name": "双良节能"},
]

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
                model=get_deepseek_model("feeder"),
                messages=[
                    {"role": "system", "content": f"{system_role}\n{build_deepseek_safety_prompt_clause()}"},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            dangerous_words = find_deepseek_dangerous_words(content)
            if dangerous_words:
                print(f"{DEEPSEEK_SAFETY_REVIEW_MESSAGE} 命中：{'、'.join(dangerous_words)}")
            return content
        except Exception as exc:
            print(f"DeepSeek 公告总结失败，第 {attempt} 次：{exc}")
            time.sleep(delay)
    return ""


def normalize_target(item):
    ts_code = normalize_ts_code(item.get("ts_code") or item.get("ticker") or item.get("stock_code"))
    return {
        "ts_code": ts_code,
        "name": str(item.get("name") or item.get("stock_name") or "").strip(),
    }


def load_json_targets(path=TARGETS_FILE):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"读取 {path} 失败：{exc}")
        return []
    return [target for target in (normalize_target(item) for item in data or []) if target.get("ts_code")]


def load_builtin_default_targets():
    return [target for target in (normalize_target(item) for item in BUILTIN_DEFAULT_TARGETS) if target.get("ts_code")]


def parse_announcement_watchlist(content):
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

    targets, error = parse_announcement_watchlist(rows[0].get("report_content", ""))
    if error:
        return None, error
    return targets, ""


def load_targets_for_run(supabase=None, dry_run=False, use_supabase_watchlist=False):
    if supabase and (not dry_run or use_supabase_watchlist):
        targets, error = load_supabase_watchlist_targets(supabase)
        if targets is not None:
            return targets, "supabase_watchlist", ""
        print(f"Supabase watchlist 不可用，尝试 fallback：{error}")

    json_targets = load_json_targets()
    if json_targets:
        return dedupe_targets(json_targets), "json_fallback", ""

    builtin_targets = load_builtin_default_targets()
    return dedupe_targets(builtin_targets), "builtin_default", ""


def parse_focus_pool_tickers(content):
    text = str(content or "")
    tickers = []
    for match in re.findall(r"\b(?:[036]\d{5}|[48]\d{5})(?:\.(?:SZ|SH|SS|BJ))?\b", text, flags=re.I):
        ts_code = normalize_ts_code(match.upper().replace(".SS", ".SH"))
        if ts_code and ts_code not in tickers:
            tickers.append(ts_code)
    return tickers[:20]


def load_focus_pool_targets(supabase):
    if not supabase:
        return []
    try:
        res = (
            supabase.table("stock_reports")
            .select("report_content, created_at")
            .eq("ticker", "__TODAY_FOCUS_POOL__")
            .eq("report_type", "today_focus_pool")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        print(f"读取 today_focus_pool 失败：{exc}")
        return []

    rows = res.data or []
    if not rows:
        return []
    tickers = parse_focus_pool_tickers(rows[0].get("report_content", ""))
    return [{"ts_code": ticker, "name": ""} for ticker in tickers]


def create_supabase_client():
    url, key = get_supabase_config()
    if not url or not key:
        print("Supabase 配置缺失，公告 auto 将只打印结果。")
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception as exc:
        print(f"Supabase 初始化失败：{exc}")
        return None


def dedupe_targets(targets):
    seen = set()
    result = []
    for target in targets:
        ts_code = target.get("ts_code")
        if not ts_code or ts_code in seen:
            continue
        seen.add(ts_code)
        result.append(target)
    return result


def record_hash(announcement):
    base = "|".join(
        str(announcement.get(key, ""))
        for key in ["ts_code", "ann_date", "title", "pdf_url", "url"]
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def build_summary_prompt(target, announcement, pdf_result):
    body = (pdf_result or {}).get("text_excerpt") or ""
    return f"""
你是A股公告事实摘要器。只能基于公告标题和公告正文，不得编造。

股票：{target.get('ts_code')} {target.get('name')}
公告日期：{announcement.get('ann_date')}
公告标题：{announcement.get('title')}
公告链接：{announcement.get('pdf_url') or announcement.get('url')}
解析状态：{(pdf_result or {}).get('parse_status')}

公告正文节选：
{body[:12000]}

请只输出 JSON：
{{
  "announcement_type": "",
  "one_line_summary": "",
  "hard_facts": [],
  "risk_tags": [],
  "positive_tags": [],
  "impact_level": "高/中/低/未知",
  "impact_direction": "利好/利空/中性/不确定",
  "impact_to_position": "",
  "next_day_validation": [],
  "needs_manual_review": true,
  "manual_review_reason": "",
  "source_boundary": "仅基于公告标题和PDF正文摘要，不构成交易指令"
}}

硬规则：
1. 没有正文时，只能写标题线索，不得下事实结论。
2. 金额、日期、股数、比例必须来自原文。
3. 不预测涨跌。
4. 不写必买、必卖、满仓、梭哈。
5. AI 解读是摘要，不是公告原文。
""".strip()


def parse_summary(content):
    if not content:
        return {}
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start : end + 1])
    except Exception:
        pass
    return {
        "announcement_type": "unknown",
        "one_line_summary": content[:300],
        "hard_facts": [],
        "risk_tags": [],
        "positive_tags": [],
        "impact_level": "未知",
        "impact_direction": "不确定",
        "impact_to_position": "",
        "next_day_validation": [],
        "needs_manual_review": True,
        "manual_review_reason": "DeepSeek 输出不是标准 JSON",
        "source_boundary": "仅基于公告标题和PDF正文摘要，不构成交易指令",
    }


def metadata_only_summary(item, pdf_result):
    return {
        "announcement_type": "metadata_only",
        "one_line_summary": f"公告标题线索：{item.get('title')}",
        "hard_facts": [],
        "risk_tags": item.get("risk_tags") or [],
        "positive_tags": [],
        "impact_level": "未知",
        "impact_direction": "不确定",
        "impact_to_position": "",
        "next_day_validation": ["下载并阅读公告 PDF 原文"],
        "needs_manual_review": True,
        "manual_review_reason": (pdf_result or {}).get("error") or "未解析公告正文",
        "source_boundary": "仅基于公告标题，不能作为硬事实",
    }


def simulated_summary(item, pdf_result):
    parse_status = (pdf_result or {}).get("parse_status") or "unknown"
    return {
        "announcement_type": "dry_run_simulated",
        "one_line_summary": f"dry-run 模拟摘要：{item.get('title')}",
        "hard_facts": [],
        "risk_tags": item.get("risk_tags") or [],
        "positive_tags": [],
        "impact_level": "未知",
        "impact_direction": "不确定",
        "impact_to_position": "dry-run 不生成真实仓位影响判断",
        "next_day_validation": ["人工复核公告原文", "观察次日量价与资金反馈"],
        "needs_manual_review": True,
        "manual_review_reason": f"dry-run 模拟 payload，PDF parse_status={parse_status}",
        "source_boundary": "dry-run 模拟摘要，不构成交易指令，不是公告原文",
    }


def build_stock_report_payload(target, item, pdf_result, summary, content_hash=None):
    pdf_result = pdf_result or {}
    content_hash = content_hash or pdf_result.get("content_hash") or record_hash(item)
    return {
        "ticker": item.get("ts_code"),
        "stock_code": item.get("stock_code"),
        "stock_name": item.get("stock_name") or target.get("name"),
        "market_type": "A_SHARE",
        "source": item.get("source"),
        "ann_date": item.get("ann_date"),
        "title": item.get("title"),
        "pdf_url": item.get("pdf_url"),
        "url": item.get("url"),
        "important": bool(item.get("important")),
        "provider_risk_tags": item.get("risk_tags") or [],
        "fetch_status": "parsed_pdf" if pdf_result.get("parse_status") == "ok" else "metadata_only",
        "parse_status": pdf_result.get("parse_status"),
        "parse_error": pdf_result.get("error", ""),
        "content_hash": content_hash,
        "summary": summary or {},
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_boundary": "parsed_pdf 可作为公告摘要线索；metadata_only 只能作为公告标题线索",
    }


def print_pdf_parse_check(item, pdf_result):
    print(
        "PDF解析测试｜"
        f"parse_status={pdf_result.get('parse_status')}｜"
        f"content_hash={pdf_result.get('content_hash') or ''}｜"
        f"excerpt_length={len(pdf_result.get('text_excerpt') or '')}｜"
        f"title={item.get('title')}"
    )
    if pdf_result.get("error"):
        print(f"PDF解析提示：{pdf_result.get('error')}")


def already_saved(supabase, ticker, content_hash):
    if not supabase or not content_hash:
        return False
    try:
        res = (
            supabase.table("stock_reports")
            .select("id")
            .eq("ticker", ticker)
            .eq("report_type", "announcement_summary")
            .ilike("report_content", f"%{content_hash}%")
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as exc:
        print(f"检查公告摘要去重失败：{ticker}，原因：{exc}")
        return False


def save_announcement_summary(supabase, payload):
    if not supabase:
        print("Supabase 不可用，跳过公告摘要写入。")
        return False
    try:
        supabase.table("stock_reports").insert(
            {
                "ticker": payload.get("ticker", ""),
                "market_type": "A_SHARE",
                "report_type": "announcement_summary",
                "report_content": json.dumps(payload, ensure_ascii=False, default=str),
            }
        ).execute()
        print(f"已写入 announcement_summary：{payload.get('ticker')}｜{payload.get('title')}")
        return True
    except Exception as exc:
        print(f"写入 announcement_summary 失败：{exc}")
        return False


def run_auto_announcement_feeder(
    dry_run=False,
    days=DEFAULT_DAYS,
    limit=DEFAULT_LIMIT,
    max_pdf_per_stock=DEFAULT_MAX_PDF_PER_STOCK,
    force_read_one=False,
    simulate_summary=False,
    use_supabase_watchlist=False,
):
    supabase = None if dry_run and not use_supabase_watchlist else create_supabase_client()
    targets, target_source, target_error = load_targets_for_run(
        supabase=supabase,
        dry_run=dry_run,
        use_supabase_watchlist=use_supabase_watchlist,
    )
    targets = dedupe_targets(targets)

    stats = {
        "targets": len(targets),
        "announcements": 0,
        "important": 0,
        "pdf_parsed": 0,
        "saved": 0,
        "deepseek_called": 0,
        "dry_run": bool(dry_run),
        "force_read_one": bool(force_read_one),
        "simulate_summary": bool(simulate_summary),
        "max_pdf_per_stock": int(max_pdf_per_stock or DEFAULT_MAX_PDF_PER_STOCK),
        "target_source": target_source,
        "target_error": target_error,
    }
    print(f"公告 auto 启动：dry_run={dry_run} targets={len(targets)} target_source={target_source}")
    if target_error:
        print(f"目标池提示：{target_error}")

    for target in targets:
        print(f"\n========== 扫描公告：{target.get('ts_code')} {target.get('name')} ==========")
        result = get_cn_announcements_fallback(
            target.get("ts_code"),
            stock_name=target.get("name"),
            days=days,
            limit=limit,
        )
        items = result.get("items") or []
        stats["announcements"] += len(items)
        print(
            f"provider={result.get('source')} available={result.get('available')} "
            f"items={len(items)} message={result.get('message')} error={result.get('error')}"
        )
        for item in items[:limit]:
            marker = "IMPORTANT" if item.get("important") else "normal"
            print(f"- [{marker}] {item.get('ann_date')} {item.get('title')} | {item.get('pdf_url') or item.get('url')}")

        if dry_run and force_read_one:
            parsed_read_count = 0
            for item in items:
                if not item.get("important"):
                    continue
                if parsed_read_count >= max(1, int(max_pdf_per_stock or DEFAULT_MAX_PDF_PER_STOCK)):
                    break
                parsed_read_count += 1
                pdf_url = item.get("pdf_url")
                if not pdf_url:
                    print(f"PDF解析测试跳过：公告源未提供 PDF URL｜title={item.get('title')}")
                    continue
                pdf_result = download_and_extract_pdf(pdf_url)
                print_pdf_parse_check(item, pdf_result)
                if pdf_result.get("parse_status") == "ok":
                    stats["pdf_parsed"] += 1
                if simulate_summary and pdf_result.get("parse_status") == "ok":
                    payload = build_stock_report_payload(
                        target,
                        item,
                        pdf_result,
                        simulated_summary(item, pdf_result),
                    )
                    print("dry-run 模拟 stock_reports.report_content：")
                    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

        deep_read_count = 0
        for item in items:
            if not item.get("important"):
                continue
            stats["important"] += 1
            if deep_read_count >= max(1, int(max_pdf_per_stock or DEFAULT_MAX_PDF_PER_STOCK)):
                continue
            deep_read_count += 1

            if dry_run:
                continue

            pdf_url = item.get("pdf_url")
            pdf_result = download_and_extract_pdf(pdf_url) if pdf_url else {
                "ok": False,
                "parse_status": "failed",
                "text_excerpt": "",
                "content_hash": "",
                "error": "公告源未提供 PDF URL",
            }
            if pdf_result.get("parse_status") == "ok":
                stats["pdf_parsed"] += 1

            content_hash = pdf_result.get("content_hash") or record_hash(item)
            if already_saved(supabase, item.get("ts_code"), content_hash):
                print(f"公告摘要已存在，跳过：{item.get('title')}")
                continue

            summary = {}
            if pdf_result.get("parse_status") == "ok":
                prompt = build_summary_prompt(target, item, pdf_result)
                content = call_deepseek_text(
                    prompt,
                    system_role="你是严谨的A股公告摘要器，只能基于公告原文提取事实。",
                    max_tokens=1600,
                    temperature=0.1,
                )
                stats["deepseek_called"] += 1
                summary = parse_summary(content)
            else:
                summary = metadata_only_summary(item, pdf_result)

            payload = build_stock_report_payload(target, item, pdf_result, summary, content_hash=content_hash)
            if save_announcement_summary(supabase, payload):
                stats["saved"] += 1

    print("\n公告 auto 运行完成：")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return stats


def main():
    parser = argparse.ArgumentParser(description="Free A-share announcement auto feeder PoC")
    parser.add_argument("--dry-run", action="store_true", help="只抓公告元数据，不写 Supabase，不调用 DeepSeek")
    parser.add_argument("--force-read-one", action="store_true", help="dry-run 下按重要公告精读，受 --max-pdf-per-stock 限制")
    parser.add_argument("--simulate-summary", action="store_true", help="dry-run 下为解析成功公告打印模拟 stock_reports payload")
    parser.add_argument("--use-supabase-watchlist", action="store_true", help="dry-run 下也优先读取 Supabase announcement_watchlist")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--max-pdf-per-stock", type=int, default=DEFAULT_MAX_PDF_PER_STOCK)
    args = parser.parse_args()
    run_auto_announcement_feeder(
        dry_run=args.dry_run,
        days=args.days,
        limit=args.limit,
        max_pdf_per_stock=args.max_pdf_per_stock,
        force_read_one=args.force_read_one,
        simulate_summary=args.simulate_summary,
        use_supabase_watchlist=args.use_supabase_watchlist,
    )


if __name__ == "__main__":
    main()
