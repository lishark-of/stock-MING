import datetime
import re
from urllib.parse import parse_qs, urlparse


IMPORTANT_ANNOUNCEMENT_KEYWORDS = [
    "监管",
    "问询函",
    "关注函",
    "立案",
    "调查",
    "处罚",
    "行政监管",
    "警示函",
    "诉讼",
    "仲裁",
    "冻结",
    "查封",
    "担保",
    "违规",
    "退市",
    "ST",
    "风险提示",
    "减持",
    "增持",
    "回购",
    "质押",
    "解除质押",
    "解禁",
    "业绩预告",
    "业绩快报",
    "亏损",
    "扭亏",
    "修正",
    "商誉减值",
    "资产减值",
    "重大合同",
    "订单",
    "中标",
    "关联交易",
    "并购",
    "重组",
    "定增",
    "可转债",
    "控制权变更",
    "高管变动",
    "审计意见",
]


def normalize_stock_code(stock_code):
    text = str(stock_code or "").strip().upper()
    return re.sub(r"\.(SZ|SS|SH|BJ)$", "", text)


def normalize_ts_code(stock_code):
    code = normalize_stock_code(stock_code)
    if not code:
        return ""
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code


def _date_text(day):
    return day.strftime("%Y%m%d")


def _normalize_ann_date(value):
    text = str(value or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text[:10]


def _risk_tags(title):
    title = str(title or "")
    return [keyword for keyword in IMPORTANT_ANNOUNCEMENT_KEYWORDS if keyword in title]


def _first_value(row, names):
    for name in names:
        value = row.get(name)
        if value not in [None, ""]:
            return value
    return ""


def _cninfo_static_pdf_url(url, ann_date):
    text = str(url or "").strip()
    if not text or "cninfo.com.cn" not in text or "announcementId=" not in text:
        return ""
    try:
        params = parse_qs(urlparse(text).query)
        announcement_id = (params.get("announcementId") or [""])[0]
    except Exception:
        announcement_id = ""
    if not announcement_id:
        return ""
    date = _normalize_ann_date(ann_date)
    if not re.match(r"\d{4}-\d{2}-\d{2}$", date):
        return ""
    return f"https://static.cninfo.com.cn/finalpage/{date}/{announcement_id}.PDF"


def _records_from_frame(df):
    if df is None:
        return []
    try:
        if df.empty:
            return []
        return df.where(df.notna(), "").to_dict("records")
    except Exception:
        return []


def _normalize_item(row, stock_code, stock_name, source):
    title = str(_first_value(row, ["公告标题", "title", "announcementTitle"]) or "").strip()
    ann_date = _normalize_ann_date(
        _first_value(row, ["公告时间", "公告日期", "ann_date", "announcementTime"])
    )
    url = str(_first_value(row, ["公告链接", "网址", "url", "adjunctUrl"]) or "").strip()
    if url.startswith("/"):
        url = f"https://static.cninfo.com.cn{url}"
    elif url and not url.startswith(("http://", "https://")) and ".PDF" in url.upper():
        url = f"https://static.cninfo.com.cn/{url.lstrip('/')}"
    tags = _risk_tags(title)
    code = normalize_stock_code(stock_code)
    pdf_url = url if ".pdf" in url.lower() else _cninfo_static_pdf_url(url, ann_date)
    return {
        "ts_code": normalize_ts_code(stock_code),
        "stock_code": code,
        "stock_name": str(stock_name or _first_value(row, ["简称", "名称", "secName"]) or "").strip(),
        "ann_date": ann_date,
        "title": title,
        "pdf_url": pdf_url,
        "url": url,
        "source": source,
        "important": bool(tags),
        "risk_tags": tags,
    }


def _dedupe_items(items, limit):
    seen = set()
    result = []
    for item in items:
        title = item.get("title", "")
        if not title:
            continue
        key = (item.get("stock_code", ""), title, item.get("ann_date", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def get_cn_announcements_fallback(stock_code, stock_name=None, days=7, limit=20):
    code = normalize_stock_code(stock_code)
    if not code:
        return {
            "available": False,
            "source": "fallback",
            "items": [],
            "message": "缺少股票代码",
            "error": "",
        }

    today = datetime.date.today()
    start = today - datetime.timedelta(days=int(days or 7))
    errors = []

    try:
        import akshare as ak

        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=code,
            market="沪深京",
            keyword="",
            category="",
            start_date=_date_text(start),
            end_date=_date_text(today),
        )
        items = [
            _normalize_item(row, code, stock_name, "akshare_cninfo")
            for row in _records_from_frame(df)
        ]
        items = _dedupe_items(items, limit)
        if items:
            return {
                "available": True,
                "source": "akshare_cninfo",
                "items": items,
                "message": f"获取公告 {len(items)} 条",
                "error": "",
            }
    except Exception as exc:
        errors.append(f"akshare_cninfo: {exc}")

    try:
        import akshare as ak

        df = ak.stock_individual_notice_report(
            security=code,
            symbol="全部",
            begin_date=_date_text(start),
            end_date=_date_text(today),
        )
        items = [
            _normalize_item(row, code, stock_name, "akshare_eastmoney")
            for row in _records_from_frame(df)
        ]
        items = _dedupe_items(items, limit)
        if items:
            return {
                "available": True,
                "source": "akshare_eastmoney",
                "items": items,
                "message": f"获取公告 {len(items)} 条",
                "error": "",
            }
    except Exception as exc:
        errors.append(f"akshare_eastmoney: {exc}")

    return {
        "available": False,
        "source": "fallback",
        "items": [],
        "message": "近期开源公告源未返回数据",
        "error": "；".join(errors),
    }
