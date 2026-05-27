from __future__ import annotations

import datetime
from copy import deepcopy

import numpy as np
import pandas as pd


ETF_UNIVERSE = [
    {"code": "510300.SH", "name": "沪深300 ETF", "bucket": "宽基ETF", "risk_level": "中", "theme": "宽基", "sub_theme": "沪深300", "manual_focus": True},
    {"code": "510500.SH", "name": "中证500 ETF", "bucket": "宽基ETF", "risk_level": "中高", "theme": "宽基", "sub_theme": "中证500", "manual_focus": True},
    {"code": "159845.SZ", "name": "中证1000 ETF", "bucket": "宽基ETF", "risk_level": "高", "theme": "宽基", "sub_theme": "中证1000", "manual_focus": True},
    {"code": "159338.SZ", "name": "中证A500 ETF", "bucket": "宽基ETF", "risk_level": "中", "theme": "宽基", "sub_theme": "中证A500", "manual_focus": True},
    {"code": "588350.SH", "name": "双创50 ETF", "bucket": "宽基ETF", "risk_level": "高", "theme": "宽基", "sub_theme": "双创50", "manual_focus": True},
    {"code": "588000.SH", "name": "科创50 ETF", "bucket": "宽基ETF", "risk_level": "高", "theme": "宽基", "sub_theme": "科创50", "manual_focus": True},
    {"code": "512480.SH", "name": "半导体 ETF", "bucket": "科技成长ETF", "risk_level": "高", "theme": "半导体/芯片", "sub_theme": "半导体/芯片", "manual_focus": True},
    {"code": "560780.SH", "name": "半导体设备ETF广发", "bucket": "科技成长ETF", "risk_level": "高", "theme": "半导体/芯片", "sub_theme": "半导体设备", "manual_focus": True},
    {"code": "588170.SH", "name": "科创半导体ETF华夏", "bucket": "科技成长ETF", "risk_level": "高", "theme": "半导体/芯片", "sub_theme": "科创半导体", "manual_focus": True},
    {"code": "513310.SH", "name": "中韩半导体ETF华泰柏瑞", "bucket": "科技成长ETF", "risk_level": "高", "theme": "半导体/芯片", "sub_theme": "中韩半导体", "manual_focus": True},
    {"code": "159801.SZ", "name": "广发国证半导体芯片ETF", "bucket": "科技成长ETF", "risk_level": "高", "theme": "半导体/芯片", "sub_theme": "芯片产业", "manual_focus": True},
    {"code": "159995.SZ", "name": "芯片ETF华夏", "bucket": "科技成长ETF", "risk_level": "高", "theme": "半导体/芯片", "sub_theme": "芯片产业", "manual_focus": True},
    {"code": "515980.SH", "name": "人工智能 ETF", "bucket": "科技成长ETF", "risk_level": "高", "theme": "人工智能", "sub_theme": "人工智能", "manual_focus": True},
    {"code": "516510.SH", "name": "云计算 ETF", "bucket": "科技成长ETF", "risk_level": "高", "theme": "云计算", "sub_theme": "云计算", "manual_focus": True},
    {"code": "516320.SH", "name": "高端装备 ETF", "bucket": "科技成长ETF", "risk_level": "中高", "theme": "高端装备", "sub_theme": "高端装备", "manual_focus": True},
    {"code": "159766.SZ", "name": "电网设备 ETF", "bucket": "科技成长ETF", "risk_level": "中高", "theme": "电网设备", "sub_theme": "电网设备", "manual_focus": True},
    {"code": "512000.SH", "name": "券商ETF", "bucket": "金融券商ETF", "risk_level": "高", "theme": "券商/证券", "sub_theme": "券商", "manual_focus": True},
    {"code": "159842.SZ", "name": "证券ETF", "bucket": "金融券商ETF", "risk_level": "高", "theme": "券商/证券", "sub_theme": "证券", "manual_focus": True},
    {"code": "515180.SH", "name": "红利 ETF", "bucket": "防守ETF", "risk_level": "中低", "theme": "红利/低波", "sub_theme": "红利", "manual_focus": True},
    {"code": "518880.SH", "name": "黄金 ETF", "bucket": "防守ETF", "risk_level": "中", "theme": "黄金/黄金股", "sub_theme": "黄金", "manual_focus": True},
    {"code": "159562.SZ", "name": "黄金股 ETF", "bucket": "防守ETF", "risk_level": "中高", "theme": "黄金/黄金股", "sub_theme": "黄金股", "manual_focus": True},
    {"code": "515300.SH", "name": "低波 ETF", "bucket": "防守ETF", "risk_level": "低", "theme": "红利/低波", "sub_theme": "低波", "manual_focus": True},
    {"code": "511010.SH", "name": "债券 ETF", "bucket": "防守ETF", "risk_level": "低", "theme": "防守资产", "sub_theme": "债券", "manual_focus": True},
    {"code": "512400.SH", "name": "有色 ETF", "bucket": "商品周期ETF", "risk_level": "高", "theme": "商品周期", "sub_theme": "有色", "manual_focus": True},
    {"code": "515220.SH", "name": "煤炭 ETF", "bucket": "商品周期ETF", "risk_level": "中高", "theme": "商品周期", "sub_theme": "煤炭", "manual_focus": True},
    {"code": "159930.SZ", "name": "能源 ETF", "bucket": "商品周期ETF", "risk_level": "高", "theme": "商品周期", "sub_theme": "能源", "manual_focus": True},
    {"code": "516780.SH", "name": "稀土 ETF", "bucket": "商品周期ETF", "risk_level": "高", "theme": "商品周期", "sub_theme": "稀土", "manual_focus": True},
]


CLASSIFICATION_RULES = [
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "沪深300",
        "risk_level": "中",
        "keywords": ["沪深300"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "中证500",
        "risk_level": "中高",
        "keywords": ["中证500"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "中证1000",
        "risk_level": "高",
        "keywords": ["中证1000"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "中证2000",
        "risk_level": "高",
        "keywords": ["中证2000"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "中证A500",
        "risk_level": "中",
        "keywords": ["中证a500", "a500"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "上证50",
        "risk_level": "中",
        "keywords": ["上证50"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "创业板",
        "risk_level": "高",
        "keywords": ["创业板"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "双创50",
        "risk_level": "高",
        "keywords": ["双创50"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "科创50",
        "risk_level": "高",
        "keywords": ["科创50"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "深证100",
        "risk_level": "中",
        "keywords": ["深证100"],
    },
    {
        "bucket": "宽基ETF",
        "theme": "宽基",
        "sub_theme": "全指",
        "risk_level": "中",
        "keywords": ["全指"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "半导体/芯片",
        "sub_theme": "半导体设备",
        "risk_level": "高",
        "keywords": ["半导体设备"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "半导体/芯片",
        "sub_theme": "科创半导体",
        "risk_level": "高",
        "keywords": ["科创半导体"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "半导体/芯片",
        "sub_theme": "中韩半导体",
        "risk_level": "高",
        "keywords": ["中韩半导体"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "半导体/芯片",
        "sub_theme": "芯片产业",
        "risk_level": "高",
        "keywords": ["国证半导体芯片", "芯片ETF"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "半导体/芯片",
        "sub_theme": "半导体材料",
        "risk_level": "高",
        "keywords": ["半导体材料"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "半导体/芯片",
        "sub_theme": "科创芯片",
        "risk_level": "高",
        "keywords": ["科创芯片"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "半导体/芯片",
        "sub_theme": "半导体/芯片",
        "risk_level": "高",
        "keywords": ["半导体", "芯片"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "人工智能",
        "sub_theme": "人工智能",
        "risk_level": "高",
        "keywords": ["人工智能", "ai"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "云计算",
        "sub_theme": "云计算",
        "risk_level": "高",
        "keywords": ["云计算", "数据中心", "信创"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "高端装备",
        "sub_theme": "机器人",
        "risk_level": "中高",
        "keywords": ["机器人", "智能制造"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "高端装备",
        "sub_theme": "高端装备",
        "risk_level": "中高",
        "keywords": ["高端装备"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "电网设备",
        "sub_theme": "电网设备",
        "risk_level": "中高",
        "keywords": ["电网设备"],
    },
    {
        "bucket": "科技成长ETF",
        "theme": "5G/通信",
        "sub_theme": "5G/通信",
        "risk_level": "高",
        "keywords": ["5g", "通信", "电子"],
    },
    {
        "bucket": "金融券商ETF",
        "theme": "券商/证券",
        "sub_theme": "券商",
        "risk_level": "高",
        "keywords": ["券商", "证券公司"],
    },
    {
        "bucket": "金融券商ETF",
        "theme": "券商/证券",
        "sub_theme": "证券",
        "risk_level": "高",
        "keywords": ["证券"],
    },
    {
        "bucket": "金融券商ETF",
        "theme": "银行",
        "sub_theme": "银行",
        "risk_level": "中",
        "keywords": ["银行"],
    },
    {
        "bucket": "金融券商ETF",
        "theme": "保险",
        "sub_theme": "保险",
        "risk_level": "中高",
        "keywords": ["保险"],
    },
    {
        "bucket": "金融券商ETF",
        "theme": "非银金融",
        "sub_theme": "非银",
        "risk_level": "高",
        "keywords": ["非银", "金融"],
    },
    {
        "bucket": "防守ETF",
        "theme": "红利/低波",
        "sub_theme": "红利",
        "risk_level": "中低",
        "keywords": ["红利"],
    },
    {
        "bucket": "防守ETF",
        "theme": "红利/低波",
        "sub_theme": "低波",
        "risk_level": "低",
        "keywords": ["低波", "价值"],
    },
    {
        "bucket": "防守ETF",
        "theme": "黄金/黄金股",
        "sub_theme": "黄金股",
        "risk_level": "中高",
        "keywords": ["黄金股"],
    },
    {
        "bucket": "防守ETF",
        "theme": "黄金/黄金股",
        "sub_theme": "黄金",
        "risk_level": "中",
        "keywords": ["黄金"],
    },
    {
        "bucket": "防守ETF",
        "theme": "防守资产",
        "sub_theme": "国债",
        "risk_level": "低",
        "keywords": ["国债", "政金债"],
    },
    {
        "bucket": "防守ETF",
        "theme": "防守资产",
        "sub_theme": "信用债",
        "risk_level": "低",
        "keywords": ["信用债"],
    },
    {
        "bucket": "防守ETF",
        "theme": "防守资产",
        "sub_theme": "短债",
        "risk_level": "低",
        "keywords": ["短债"],
    },
    {
        "bucket": "防守ETF",
        "theme": "防守资产",
        "sub_theme": "债券",
        "risk_level": "低",
        "keywords": ["债券"],
    },
    {
        "bucket": "防守ETF",
        "theme": "防守资产",
        "sub_theme": "货币",
        "risk_level": "低",
        "keywords": ["货币", "现金"],
    },
    {
        "bucket": "商品周期ETF",
        "theme": "商品周期",
        "sub_theme": "有色",
        "risk_level": "高",
        "keywords": ["有色", "铜", "铝"],
    },
    {
        "bucket": "商品周期ETF",
        "theme": "商品周期",
        "sub_theme": "稀土",
        "risk_level": "高",
        "keywords": ["稀土"],
    },
    {
        "bucket": "商品周期ETF",
        "theme": "商品周期",
        "sub_theme": "煤炭",
        "risk_level": "中高",
        "keywords": ["煤炭"],
    },
    {
        "bucket": "商品周期ETF",
        "theme": "商品周期",
        "sub_theme": "能源",
        "risk_level": "高",
        "keywords": ["能源", "石油"],
    },
    {
        "bucket": "商品周期ETF",
        "theme": "商品周期",
        "sub_theme": "化工",
        "risk_level": "中高",
        "keywords": ["化工"],
    },
    {
        "bucket": "商品周期ETF",
        "theme": "商品周期",
        "sub_theme": "钢铁",
        "risk_level": "中高",
        "keywords": ["钢铁", "建材", "周期"],
    },
    {
        "bucket": "消费医药ETF",
        "theme": "消费医药",
        "sub_theme": "消费",
        "risk_level": "中",
        "keywords": ["消费", "食品饮料", "酒"],
    },
    {
        "bucket": "消费医药ETF",
        "theme": "消费医药",
        "sub_theme": "医药",
        "risk_level": "中高",
        "keywords": ["医药", "医疗", "创新药", "生物医药", "疫苗", "中药"],
    },
    {
        "bucket": "港股/海外ETF",
        "theme": "港股/海外",
        "sub_theme": "港股",
        "risk_level": "高",
        "keywords": ["恒生", "港股", "h股"],
    },
    {
        "bucket": "港股/海外ETF",
        "theme": "港股/海外",
        "sub_theme": "美股",
        "risk_level": "高",
        "keywords": ["纳斯达克", "标普"],
    },
    {
        "bucket": "港股/海外ETF",
        "theme": "港股/海外",
        "sub_theme": "海外",
        "risk_level": "高",
        "keywords": ["日经", "德国", "海外", "qdii"],
    },
]


DEFAULT_DYNAMIC_BUCKETS = [
    "宽基ETF",
    "科技成长ETF",
    "金融券商ETF",
    "防守ETF",
    "商品周期ETF",
]


COMPARISON_THEMES = [
    "半导体/芯片",
    "半导体设备",
    "科创半导体",
    "中韩半导体",
    "芯片产业",
    "券商/证券",
    "人工智能",
    "云计算",
    "电网设备",
    "高端装备",
    "黄金/黄金股",
    "红利/低波",
    "宽基",
    "商品周期",
]


def _today():
    return datetime.date.today()


def _normalize_date(value):
    if value is None:
        return None
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    if not text:
        return None
    return text.replace("-", "")


def _normalize_etf_code(code):
    text = str(code or "").strip().upper()
    if not text:
        return ""
    if text.endswith(".SS"):
        return text[:-3] + ".SH"
    if text.endswith((".SH", ".SZ", ".BJ")):
        return text
    if text.isdigit() and len(text) == 6:
        if text.startswith("6") or text.startswith("5"):
            return f"{text}.SH"
        if text.startswith(("0", "1", "3")):
            return f"{text}.SZ"
    return text


def _normalize_text(value):
    return str(value or "").strip()


def _frame_from_result(result):
    data = (result or {}).get("data")
    return data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame()


def _error_text(result, default="暂无可验证数据"):
    return str((result or {}).get("error") or default)


def _safe_float(value):
    try:
        if value in [None, ""]:
            return None
        number = float(value)
        if np.isnan(number) or np.isinf(number):
            return None
        return number
    except Exception:
        return None


def _round2(value):
    number = _safe_float(value)
    return None if number is None else round(number, 2)


def _first_not_empty(*values):
    for value in values:
        text = _normalize_text(value)
        if text:
            return text
    return ""


def _normalize_basic_payload(raw=None, manual_item=None, index_info=None):
    raw = raw or {}
    manual_item = manual_item or {}
    index_info = index_info or {}
    code = _normalize_etf_code(raw.get("ts_code") or manual_item.get("ts_code") or manual_item.get("code"))
    return {
        "ts_code": code,
        "code": code,
        "name": _first_not_empty(raw.get("name"), raw.get("csname"), raw.get("extname"), raw.get("cname"), manual_item.get("name")),
        "fund_type": _first_not_empty(raw.get("fund_type"), raw.get("etf_type"), manual_item.get("fund_type")),
        "market": _first_not_empty(raw.get("market"), raw.get("exchange"), manual_item.get("market")),
        "list_date": _normalize_date(raw.get("list_date") or raw.get("setup_date") or manual_item.get("list_date")) or "",
        "manager": _first_not_empty(raw.get("manager"), raw.get("mgr_name"), manual_item.get("manager")),
        "custodian": _first_not_empty(raw.get("custodian"), raw.get("custod_name"), manual_item.get("custodian")),
        "benchmark": _first_not_empty(raw.get("benchmark"), raw.get("index_name"), index_info.get("benchmark"), index_info.get("index_name"), manual_item.get("benchmark")),
        "index_code": _first_not_empty(raw.get("index_code"), index_info.get("index_code"), manual_item.get("index_code")),
        "index_name": _first_not_empty(raw.get("index_name"), index_info.get("index_name"), manual_item.get("index_name")),
        "invest_type": _first_not_empty(raw.get("invest_type"), raw.get("etf_type"), manual_item.get("invest_type")),
        "status": _first_not_empty(raw.get("status"), raw.get("list_status"), manual_item.get("status")) or "L",
    }


def _dedupe_strings(values):
    result = []
    seen = set()
    for value in values or []:
        text = _normalize_text(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _series_last_value(series, column):
    if column not in series.columns:
        return None
    return _safe_float(series[column].iloc[-1])


def _data_completeness_ratio(item):
    keys = [
        "latest_price",
        "MA20",
        "MA60",
        "return_20d_pct",
        "return_60d_pct",
        "volatility_20d",
        "amount_ma20",
        "benchmark",
        "manager",
    ]
    available = sum(1 for key in keys if item.get(key) not in [None, "", []])
    return available / max(len(keys), 1)


def get_default_etf_universe():
    return deepcopy(ETF_UNIVERSE)


def get_etf_catalog_by_bucket(universe=None):
    catalog = {}
    for item in universe or ETF_UNIVERSE:
        bucket = item.get("bucket") or "其他ETF"
        name = item.get("name") or item.get("etf_name") or item.get("code") or item.get("etf_code")
        if name:
            catalog.setdefault(bucket, []).append(name)
    return {key: _dedupe_strings(value) for key, value in catalog.items()}


def _match_classification_rule(text, priority_buckets=None, blocked_keywords=None):
    text = _normalize_text(text).lower()
    if not text:
        return None, None
    blocked_keywords = {str(item).lower() for item in (blocked_keywords or set())}
    buckets = priority_buckets or [
        "科技成长ETF",
        "金融券商ETF",
        "防守ETF",
        "商品周期ETF",
        "消费医药ETF",
        "港股/海外ETF",
        "宽基ETF",
    ]
    for bucket in buckets:
        for rule in CLASSIFICATION_RULES:
            if rule["bucket"] != bucket:
                continue
            for keyword in rule["keywords"]:
                normalized_keyword = keyword.lower()
                if normalized_keyword in blocked_keywords:
                    continue
                if normalized_keyword in text:
                    return rule, keyword
    return None, None


def classify_etf_theme(etf_row):
    row = dict(etf_row or {})
    name_text = _normalize_text(row.get("name")).lower()
    benchmark_text = " | ".join(
        _normalize_text(value).lower()
        for value in [row.get("benchmark"), row.get("index_name"), row.get("index_code")]
        if _normalize_text(value)
    )
    supporting_text = " | ".join(
        _normalize_text(value).lower()
        for value in [row.get("fund_type"), row.get("invest_type")]
        if _normalize_text(value)
    )
    combined_text = " | ".join(text for text in [name_text, benchmark_text, supporting_text] if text)
    if "中韩半导体" in combined_text or ("半导体" in combined_text and any(keyword in combined_text for keyword in ["krx", "韩交所", "korea"])):
        return {
            "bucket": "科技成长ETF",
            "theme": "半导体/芯片",
            "sub_theme": "中韩半导体",
            "risk_level": "高",
            "classification_reason": "名称/指数命中关键词：中韩半导体（跨市场半导体）",
        }
    if "科创半导体" in combined_text:
        return {
            "bucket": "科技成长ETF",
            "theme": "半导体/芯片",
            "sub_theme": "科创半导体",
            "risk_level": "高",
            "classification_reason": "名称/指数命中关键词：科创半导体",
        }
    if "国证半导体芯片" in combined_text or "芯片etf" in name_text:
        return {
            "bucket": "科技成长ETF",
            "theme": "半导体/芯片",
            "sub_theme": "芯片产业",
            "risk_level": "高",
            "classification_reason": "名称/指数命中关键词：芯片产业",
        }
    if "半导体设备" in name_text:
        return {
            "bucket": "科技成长ETF",
            "theme": "半导体/芯片",
            "sub_theme": "半导体设备",
            "risk_level": "高",
            "classification_reason": "名称直接命中关键词：半导体设备",
        }
    broker_keywords = ["证券公司", "证券公司指数", "券商", "全指证券", "证券龙头"]
    if any(keyword in benchmark_text for keyword in broker_keywords):
        return {
            "bucket": "金融券商ETF",
            "theme": "券商/证券",
            "sub_theme": "券商",
            "risk_level": "高",
            "classification_reason": "跟踪指数/benchmark 命中券商证券关键词。",
        }
    benchmark_rule, benchmark_keyword = _match_classification_rule(
        benchmark_text,
        priority_buckets=[
            "科技成长ETF",
            "防守ETF",
            "商品周期ETF",
            "消费医药ETF",
            "港股/海外ETF",
            "宽基ETF",
            "金融券商ETF",
        ],
        blocked_keywords={"证券"},
    )
    if benchmark_rule:
        return {
            "bucket": benchmark_rule["bucket"],
            "theme": benchmark_rule["theme"],
            "sub_theme": benchmark_rule["sub_theme"],
            "risk_level": benchmark_rule["risk_level"],
            "classification_reason": f"跟踪指数/benchmark 命中关键词：{benchmark_keyword}",
        }
    if any(keyword in name_text for keyword in ["券商etf", "证券etf", "证券公司etf", "证券龙头etf", "全指证券"]):
        return {
            "bucket": "金融券商ETF",
            "theme": "券商/证券",
            "sub_theme": "券商",
            "risk_level": "高",
            "classification_reason": "ETF 产品名称命中券商证券主题关键词。",
        }
    matched_rule, matched_keyword = _match_classification_rule(combined_text, blocked_keywords={"证券"})
    if matched_rule:
        return {
            "bucket": matched_rule["bucket"],
            "theme": matched_rule["theme"],
            "sub_theme": matched_rule["sub_theme"],
            "risk_level": matched_rule["risk_level"],
            "classification_reason": f"名称/指数命中关键词：{matched_keyword}",
        }

    default_bucket = "其他ETF"
    default_reason = "未命中预设主题关键词，保留为其他ETF。"
    if "etf" in combined_text and any(keyword in combined_text for keyword in ["bond", "债", "货币"]):
        default_bucket = "防守ETF"
        default_reason = "根据 fund_type / 名称推断为防守类 ETF。"
    return {
        "bucket": default_bucket,
        "theme": "其他ETF",
        "sub_theme": "其他ETF",
        "risk_level": row.get("risk_level") or "中",
        "classification_reason": default_reason,
    }


def _build_manual_universe_records(fallback_universe=None):
    records = []
    for item in fallback_universe or ETF_UNIVERSE:
        record = {
            "ts_code": _normalize_etf_code(item.get("code") or item.get("ts_code")),
            "code": _normalize_etf_code(item.get("code") or item.get("ts_code")),
            "name": item.get("name") or item.get("etf_name") or "",
            "fund_type": item.get("fund_type") or "ETF",
            "market": item.get("market") or "",
            "list_date": _normalize_date(item.get("list_date")) or "",
            "manager": item.get("manager") or "",
            "custodian": item.get("custodian") or "",
            "benchmark": item.get("benchmark") or "",
            "index_code": item.get("index_code") or "",
            "index_name": item.get("index_name") or "",
            "invest_type": item.get("invest_type") or "",
            "status": item.get("status") or "L",
            "manual_focus": True,
        }
        classification = classify_etf_theme({**record, **item})
        record.update(classification)
        record["bucket"] = item.get("bucket") or record["bucket"]
        record["theme"] = item.get("theme") or record["theme"]
        record["sub_theme"] = item.get("sub_theme") or record["sub_theme"]
        record["risk_level"] = item.get("risk_level") or record["risk_level"]
        records.append(record)
    return records


def discover_etf_universe_from_tushare(tushare_adapter=None, fallback_universe=None):
    adapter = tushare_adapter
    fallback_records = _build_manual_universe_records(fallback_universe)
    result = {
        "data_source": "tushare",
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "used_fallback": False,
        "available": False,
        "discovered_count": 0,
        "classified_count": 0,
        "items": [],
        "theme_counts": {},
        "bucket_counts": {},
        "errors": [],
        "data_gaps": [],
    }

    if adapter is None:
        result["used_fallback"] = True
        result["data_source"] = "manual_fallback"
        result["errors"].append("tushare_adapter 不可用")
        result["items"] = fallback_records
        result["discovered_count"] = len(fallback_records)
        result["classified_count"] = len([item for item in fallback_records if item.get("bucket") != "其他ETF"])
        result["available"] = bool(result["items"])
        return _finalize_discovery_result(result)

    basic_frame = pd.DataFrame()
    basic_errors = []
    for params in [{"status": "L"}, {}]:
        basic_result = adapter.get_etf_basic(**params)
        frame = _frame_from_result(basic_result)
        if basic_result.get("ok") and not frame.empty:
            basic_frame = frame
            break
        basic_errors.append(_error_text(basic_result))

    if basic_frame.empty:
        result["used_fallback"] = True
        result["data_source"] = "manual_fallback"
        result["errors"].append("etf_basic 获取失败，已回退人工 ETF_UNIVERSE。")
        result["data_gaps"].extend(_dedupe_strings(basic_errors))
        result["items"] = fallback_records
        result["discovered_count"] = len(fallback_records)
        result["classified_count"] = len([item for item in fallback_records if item.get("bucket") != "其他ETF"])
        result["available"] = bool(result["items"])
        return _finalize_discovery_result(result)

    index_map = {}
    if hasattr(adapter, "get_etf_index"):
        index_result = adapter.get_etf_index()
        index_frame = _frame_from_result(index_result)
        if index_result.get("ok") and not index_frame.empty:
            for _, row in index_frame.iterrows():
                ts_code = _normalize_etf_code(row.get("ts_code"))
                if ts_code and ts_code not in index_map:
                    index_map[ts_code] = row.where(row.notna(), None).to_dict()
        elif index_result.get("error"):
            result["data_gaps"].append(f"etf_index: {_error_text(index_result)}")

    manual_map = {item["ts_code"]: item for item in fallback_records if item.get("ts_code")}
    items = []
    for _, row in basic_frame.iterrows():
        raw = row.where(row.notna(), None).to_dict()
        ts_code = _normalize_etf_code(raw.get("ts_code"))
        if not ts_code:
            continue
        index_info = index_map.get(ts_code, {})
        seed = _normalize_basic_payload(raw=raw, manual_item=manual_map.get(ts_code), index_info=index_info)
        seed["manual_focus"] = bool(manual_map.get(ts_code))
        classification = classify_etf_theme(seed)
        if manual_map.get(ts_code):
            seed["name"] = _first_not_empty(seed.get("name"), manual_map[ts_code].get("name"))
            classification["bucket"] = manual_map[ts_code].get("bucket") or classification["bucket"]
            classification["theme"] = manual_map[ts_code].get("theme") or classification["theme"]
            classification["sub_theme"] = manual_map[ts_code].get("sub_theme") or classification["sub_theme"]
            classification["risk_level"] = manual_map[ts_code].get("risk_level") or classification["risk_level"]
            classification["classification_reason"] = f"{classification['classification_reason']}；人工重点关注补充。"
        seed.update(classification)
        items.append(seed)

    for manual_code, manual_item in manual_map.items():
        if manual_code not in {item["ts_code"] for item in items}:
            items.append(dict(manual_item))
            result["data_gaps"].append(f"{manual_code} 未出现在 etf_basic 中，已保留人工重点关注。")

    result["items"] = _dedupe_discovery_items(items)
    result["discovered_count"] = len(result["items"])
    result["classified_count"] = len([item for item in result["items"] if item.get("bucket") != "其他ETF"])
    result["available"] = bool(result["items"])
    return _finalize_discovery_result(result)


def _dedupe_discovery_items(items):
    deduped = {}
    for item in items or []:
        code = _normalize_etf_code(item.get("ts_code") or item.get("code"))
        if not code:
            continue
        payload = dict(item)
        payload["ts_code"] = code
        payload["code"] = code
        if code not in deduped or payload.get("manual_focus"):
            deduped[code] = payload
    return list(deduped.values())


def _finalize_discovery_result(result):
    items = result.get("items") or []
    bucket_counts = {}
    theme_counts = {}
    for item in items:
        bucket = item.get("bucket") or "其他ETF"
        theme = item.get("sub_theme") or item.get("theme") or "其他ETF"
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        theme_counts[theme] = theme_counts.get(theme, 0) + 1
    result["bucket_counts"] = bucket_counts
    result["theme_counts"] = theme_counts
    result["errors"] = _dedupe_strings(result.get("errors"))
    result["data_gaps"] = _dedupe_strings(result.get("data_gaps"))
    return result


def fetch_etf_universe_data(etf_universe, start_date=None, end_date=None, tushare_adapter=None, include_nav=False):
    adapter = tushare_adapter
    end_date = _normalize_date(end_date) or _today().strftime("%Y%m%d")
    start_date = _normalize_date(start_date) or (_today() - datetime.timedelta(days=180)).strftime("%Y%m%d")

    result = {
        "data_source": "tushare",
        "trade_window": {"start_date": start_date, "end_date": end_date},
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "latest_data_date": "",
        "sample_count": len(etf_universe or []),
        "available_count": 0,
        "available": False,
        "used_realtime": False,
        "has_data_gap": False,
        "errors": [],
        "data_gaps": [],
        "items": [],
    }
    if adapter is None:
        result["errors"].append("tushare_adapter 不可用")
        result["has_data_gap"] = True
        return result

    latest_dates = []
    for item in etf_universe or []:
        code = _normalize_etf_code(item.get("code") or item.get("ts_code"))
        basic_seed = _normalize_basic_payload(
            manual_item={
                "ts_code": code,
                "code": code,
                "name": item.get("name") or item.get("etf_name") or code,
                "fund_type": item.get("fund_type") or "",
                "market": item.get("market") or "",
                "list_date": item.get("list_date") or "",
                "manager": item.get("manager") or "",
                "custodian": item.get("custodian") or "",
                "benchmark": item.get("benchmark") or "",
                "index_code": item.get("index_code") or "",
                "index_name": item.get("index_name") or "",
                "invest_type": item.get("invest_type") or "",
                "status": item.get("status") or "",
            }
        )
        payload = dict(item)
        payload.update(
            {
                "code": code,
                "ts_code": code,
                "available": False,
                "latest_trade_date": "",
                "market_data": pd.DataFrame(),
                "basic_info": basic_seed,
                "index_info": {"index_code": basic_seed["index_code"], "index_name": basic_seed["index_name"], "benchmark": basic_seed["benchmark"]},
                "nav_info": {},
                "errors": [],
            }
        )

        daily_result = adapter.get_fund_daily(ts_code=code, start_date=start_date, end_date=end_date)
        daily_frame = _frame_from_result(daily_result)
        if not daily_result.get("ok") or daily_frame.empty:
            payload["errors"].append(f"fund_daily: {_error_text(daily_result)}")
        else:
            daily_frame = daily_frame.sort_values("trade_date").reset_index(drop=True)
            payload["market_data"] = daily_frame
            payload["available"] = True
            payload["latest_trade_date"] = str(daily_frame["trade_date"].iloc[-1])
            latest_dates.append(payload["latest_trade_date"])

        if not payload["basic_info"].get("benchmark") or not payload["basic_info"].get("manager"):
            basic_result = adapter.get_etf_basic(ts_code=code)
            basic_frame = _frame_from_result(basic_result)
            if basic_result.get("ok") and not basic_frame.empty:
                payload["basic_info"] = _normalize_basic_payload(
                    raw=basic_frame.iloc[0].where(basic_frame.iloc[0].notna(), None).to_dict(),
                    manual_item=payload["basic_info"],
                )
            else:
                payload["errors"].append(f"etf_basic: {_error_text(basic_result)}")

        if not payload["index_info"].get("index_code") and hasattr(adapter, "get_etf_index"):
            index_result = adapter.get_etf_index(ts_code=code)
            index_frame = _frame_from_result(index_result)
            if index_result.get("ok") and not index_frame.empty:
                payload["index_info"] = index_frame.iloc[0].where(index_frame.iloc[0].notna(), None).to_dict()
            elif index_result.get("error"):
                payload["errors"].append(f"etf_index: {_error_text(index_result)}")

        if include_nav and hasattr(adapter, "get_fund_nav"):
            nav_result = adapter.get_fund_nav(ts_code=code, end_date=end_date)
            nav_frame = _frame_from_result(nav_result)
            if nav_result.get("ok") and not nav_frame.empty:
                payload["nav_info"] = nav_frame.iloc[0].where(nav_frame.iloc[0].notna(), None).to_dict()
            elif nav_result.get("error"):
                payload["errors"].append(f"fund_nav: {_error_text(nav_result)}")

        if payload["errors"]:
            result["has_data_gap"] = True
            result["errors"].extend([f"{code}｜{message}" for message in payload["errors"][:3]])

        result["items"].append(payload)

    result["available_count"] = sum(1 for item in result["items"] if item.get("available"))
    result["available"] = result["available_count"] > 0
    result["latest_data_date"] = max(latest_dates) if latest_dates else ""
    result["errors"] = _dedupe_strings(result["errors"])
    result["data_gaps"] = list(result["errors"])
    return result


def _score_state(price, ma20, ma60, ret20, volatility20):
    if price is None or ma20 is None:
        return "数据不足"
    if ma60 is not None and price < ma60:
        return "破位回避"
    if ret20 is not None and ret20 > 35:
        return "过热等待"
    if price > ma20 and ma60 is not None and ma20 > ma60:
        return "强趋势"
    if price > ma20:
        return "温和向上"
    if volatility20 is not None and volatility20 > 32:
        return "震荡观察"
    return "震荡观察"


def _build_indicator_snapshot(frame):
    series = frame.sort_values("trade_date").reset_index(drop=True).copy()
    series["close"] = pd.to_numeric(series["close"], errors="coerce")
    series["amount"] = pd.to_numeric(series.get("amount"), errors="coerce")
    series["pct"] = series["close"].pct_change()
    series["ma5"] = series["close"].rolling(5).mean()
    series["ma20"] = series["close"].rolling(20).mean()
    series["ma60"] = series["close"].rolling(60).mean()
    series["ret20"] = series["close"].pct_change(20) * 100
    series["ret60"] = series["close"].pct_change(60) * 100
    series["vol20"] = series["pct"].rolling(20).std() * np.sqrt(20) * 100
    series["amount_ma20"] = series["amount"].rolling(20).mean()
    last = series.iloc[-1]

    latest_price = _safe_float(last.get("close"))
    ma5 = _safe_float(last.get("ma5"))
    ma20 = _safe_float(last.get("ma20"))
    ma60 = _safe_float(last.get("ma60"))
    ret20 = _safe_float(last.get("ret20"))
    ret60 = _safe_float(last.get("ret60"))
    vol20 = _safe_float(last.get("vol20"))
    amount_ma20 = _safe_float(last.get("amount_ma20"))
    price_vs_ma20 = ((latest_price / ma20) - 1) * 100 if latest_price and ma20 else None
    price_vs_ma60 = ((latest_price / ma60) - 1) * 100 if latest_price and ma60 else None

    trend_score = 8.0
    if latest_price and ma20 and latest_price > ma20:
        trend_score += 10
    if latest_price and ma20 and ma60 and latest_price > ma20 > ma60:
        trend_score += 17
    elif latest_price and ma60 and latest_price < ma60:
        trend_score -= 6
    trend_score = max(min(trend_score, 35), 0)

    momentum_score = 8.0
    if ret20 is not None:
        if 3 <= ret20 <= 25:
            momentum_score += 12
        elif ret20 > 25:
            momentum_score += 7
        elif ret20 < -5:
            momentum_score -= 5
    if ret60 is not None and ret60 > 8:
        momentum_score += 5
    momentum_score = max(min(momentum_score, 25), 0)

    volatility_score = 15.0
    if vol20 is not None:
        if vol20 <= 12:
            volatility_score += 5
        elif vol20 <= 22:
            volatility_score += 2
        elif vol20 > 30:
            volatility_score -= 6
    volatility_score = max(min(volatility_score, 20), 0)

    liquidity_score = 8.0
    if amount_ma20 is not None:
        if amount_ma20 >= 150000:
            liquidity_score += 7
        elif amount_ma20 >= 50000:
            liquidity_score += 4
        elif amount_ma20 < 15000:
            liquidity_score -= 5
    liquidity_score = max(min(liquidity_score, 15), 0)

    risk_score = 10.0
    if price_vs_ma20 is not None and price_vs_ma20 > 8:
        risk_score -= 2
    if ret20 is not None and ret20 > 35:
        risk_score -= 6
    if latest_price and ma20 and latest_price < ma20:
        risk_score -= 5
    if latest_price and ma60 and latest_price < ma60:
        risk_score -= 8
    if vol20 is not None and vol20 > 30:
        risk_score -= 3
    risk_score = max(min(risk_score, 15), 0)

    total_score = trend_score + momentum_score + volatility_score + liquidity_score + risk_score
    state = _score_state(latest_price, ma20, ma60, ret20, vol20)
    if latest_price and ma20 and latest_price < ma20:
        state = "震荡观察" if state != "破位回避" else state

    return {
        "latest_price": _round2(latest_price),
        "MA5": _round2(ma5),
        "MA20": _round2(ma20),
        "MA60": _round2(ma60),
        "return_20d_pct": _round2(ret20),
        "return_60d_pct": _round2(ret60),
        "volatility_20d": _round2(vol20),
        "amount_ma20": _round2(amount_ma20),
        "price_vs_ma20_pct": _round2(price_vs_ma20),
        "price_vs_ma60_pct": _round2(price_vs_ma60),
        "trend_score": _round2(trend_score),
        "momentum_score": _round2(momentum_score),
        "volatility_score": _round2(volatility_score),
        "liquidity_score": _round2(liquidity_score),
        "risk_score": _round2(risk_score),
        "total_score": _round2(total_score),
        "state": state,
    }


def score_etf_universe(etf_market_data):
    rows = []
    items = (etf_market_data or {}).get("items") or []
    data_date = (etf_market_data or {}).get("latest_data_date") or ""
    for item in items:
        code = item.get("code") or item.get("ts_code") or ""
        name = item.get("name") or item.get("etf_name") or code
        bucket = item.get("bucket") or "其他ETF"
        frame = item.get("market_data")
        basic_info = item.get("basic_info") or {}
        index_info = item.get("index_info") or {}
        benchmark = _first_not_empty(item.get("benchmark"), basic_info.get("benchmark"), index_info.get("benchmark"), index_info.get("index_name"))
        manager = _first_not_empty(item.get("manager"), basic_info.get("manager"))
        index_code = _first_not_empty(item.get("index_code"), basic_info.get("index_code"), index_info.get("index_code"))
        index_name = _first_not_empty(item.get("index_name"), index_info.get("index_name"))
        base_row = {
            "etf_code": code,
            "etf_name": name,
            "bucket": bucket,
            "theme": item.get("theme", ""),
            "sub_theme": item.get("sub_theme", ""),
            "risk_level": item.get("risk_level", ""),
            "classification_reason": item.get("classification_reason", ""),
            "benchmark": benchmark,
            "manager": manager,
            "index_code": index_code,
            "index_name": index_name,
            "fund_type": _first_not_empty(item.get("fund_type"), basic_info.get("fund_type")),
            "market": _first_not_empty(item.get("market"), basic_info.get("market")),
            "list_date": _first_not_empty(item.get("list_date"), basic_info.get("list_date")),
            "invest_type": _first_not_empty(item.get("invest_type"), basic_info.get("invest_type")),
            "status": _first_not_empty(item.get("status"), basic_info.get("status")),
            "manual_focus": bool(item.get("manual_focus")),
            "data_date": item.get("latest_trade_date") or data_date,
        }
        if not isinstance(frame, pd.DataFrame) or frame.empty or "close" not in frame.columns:
            rows.append(
                {
                    **base_row,
                    "latest_price": None,
                    "MA5": None,
                    "MA20": None,
                    "MA60": None,
                    "return_20d_pct": None,
                    "return_60d_pct": None,
                    "volatility_20d": None,
                    "amount_ma20": None,
                    "price_vs_ma20_pct": None,
                    "price_vs_ma60_pct": None,
                    "trend_score": 0.0,
                    "momentum_score": 0.0,
                    "volatility_score": 0.0,
                    "liquidity_score": 0.0,
                    "risk_score": 0.0,
                    "total_score": 0.0,
                    "data_completeness": 0.0,
                    "state": "数据不足",
                }
            )
            continue

        indicator = _build_indicator_snapshot(frame)
        row = {**base_row, **indicator}
        row["data_completeness"] = _round2(_data_completeness_ratio(row) * 100)
        rows.append(row)

    rows.sort(
        key=lambda item: (
            item.get("manual_focus", False),
            item.get("total_score") or 0,
            item.get("amount_ma20") or 0,
            item.get("data_date") or "",
        ),
        reverse=True,
    )
    return {
        "data_source": "tushare",
        "data_date": data_date,
        "sample_count": len(rows),
        "rows": rows,
    }


def _selection_priority(item):
    state_score = {
        "强趋势": 4,
        "温和向上": 3,
        "震荡观察": 2,
        "过热等待": 1,
        "破位回避": 0,
        "数据不足": -1,
    }.get(item.get("state"), 0)
    return (
        1 if item.get("manual_focus") else 0,
        state_score,
        _safe_float(item.get("total_score")) or 0,
        _safe_float(item.get("amount_ma20")) or 0,
        _safe_float(item.get("data_completeness")) or 0,
    )


def build_dynamic_etf_universe(
    include_buckets=None,
    max_per_theme=5,
    min_amount_ma20=None,
    tushare_adapter=None,
    start_date=None,
    end_date=None,
    discovery_payload=None,
):
    buckets = include_buckets or DEFAULT_DYNAMIC_BUCKETS
    discovery = discovery_payload or discover_etf_universe_from_tushare(tushare_adapter=tushare_adapter)
    discovered_items = discovery.get("items") or []
    filtered_items = [
        item for item in discovered_items
        if item.get("bucket") in buckets and str(item.get("ts_code") or item.get("code") or "").endswith((".SH", ".SZ"))
    ]
    if not filtered_items:
        filtered_items = discovered_items

    grouped_prefetch = {}
    for item in filtered_items:
        theme_key = item.get("theme") or item.get("sub_theme") or "其他ETF"
        grouped_prefetch.setdefault(theme_key, []).append(item)

    shortlist = []
    for theme_key, items in grouped_prefetch.items():
        ranked = sorted(
            items,
            key=lambda item: (
                item.get("manual_focus", False),
                1 if item.get("status") in {"L", "D"} else 0,
                1 if item.get("benchmark") else 0,
                item.get("list_date") or "",
            ),
            reverse=True,
        )
        shortlist.extend(ranked[: max(max_per_theme * 4, 8)])

    shortlist = _dedupe_discovery_items(shortlist)
    daily_dataset = fetch_etf_universe_data(
        shortlist,
        start_date=start_date,
        end_date=end_date,
        tushare_adapter=tushare_adapter,
        include_nav=False,
    )
    raw_score_packet = score_etf_universe(daily_dataset)
    rows = raw_score_packet.get("rows") or []

    selected_rows = []
    for theme_key in grouped_prefetch:
        themed_rows = [
            row for row in rows
            if (row.get("theme") or row.get("sub_theme") or "其他ETF") == theme_key
        ]
        if min_amount_ma20 is not None:
            liquid_rows = [row for row in themed_rows if (_safe_float(row.get("amount_ma20")) or 0) >= float(min_amount_ma20)]
            if liquid_rows:
                themed_rows = liquid_rows
        themed_rows = sorted(themed_rows, key=_selection_priority, reverse=True)
        selected_rows.extend(themed_rows[: max_per_theme])

    selected_map = {row.get("etf_code"): row for row in selected_rows if row.get("etf_code")}
    for item in discovered_items:
        code = item.get("ts_code") or item.get("code")
        if item.get("manual_focus") and code not in selected_map and item.get("bucket") in buckets:
            selected_map[code] = {
                "etf_code": code,
                "etf_name": item.get("name") or code,
                "bucket": item.get("bucket"),
                "theme": item.get("theme"),
                "sub_theme": item.get("sub_theme"),
                "risk_level": item.get("risk_level"),
                "classification_reason": item.get("classification_reason"),
                "benchmark": item.get("benchmark"),
                "manager": item.get("manager"),
                "index_code": item.get("index_code"),
                "index_name": item.get("index_name"),
                "fund_type": item.get("fund_type"),
                "market": item.get("market"),
                "list_date": item.get("list_date"),
                "invest_type": item.get("invest_type"),
                "status": item.get("status"),
                "manual_focus": True,
                "data_date": daily_dataset.get("latest_data_date"),
                "latest_price": None,
                "MA5": None,
                "MA20": None,
                "MA60": None,
                "return_20d_pct": None,
                "return_60d_pct": None,
                "volatility_20d": None,
                "amount_ma20": None,
                "price_vs_ma20_pct": None,
                "price_vs_ma60_pct": None,
                "trend_score": 0.0,
                "momentum_score": 0.0,
                "volatility_score": 0.0,
                "liquidity_score": 0.0,
                "risk_score": 0.0,
                "total_score": 0.0,
                "data_completeness": 0.0,
                "state": "数据不足",
            }

    selected_rows = sorted(selected_map.values(), key=_selection_priority, reverse=True)
    selected_universe = []
    row_map = {row.get("etf_code"): row for row in selected_rows if row.get("etf_code")}
    for item in shortlist + discovered_items:
        code = item.get("ts_code") or item.get("code")
        if code in row_map and code not in {entry.get("code") for entry in selected_universe}:
            selected_universe.append({**item, "code": code, "ts_code": code})

    score_packet = {
        "data_source": raw_score_packet.get("data_source") or "tushare",
        "data_date": raw_score_packet.get("data_date") or daily_dataset.get("latest_data_date") or "",
        "sample_count": len(selected_rows),
        "rows": selected_rows,
    }
    theme_counts = {}
    for row in selected_rows:
        key = row.get("theme") or row.get("sub_theme") or "其他ETF"
        theme_counts[key] = theme_counts.get(key, 0) + 1

    data_status = dict(daily_dataset)
    data_status.update(
        {
            "universe_mode": "dynamic",
            "discovered_etf_count": discovery.get("discovered_count", 0),
            "classified_count": discovery.get("classified_count", 0),
            "scored_etf_count": len(rows),
            "selected_count": len(selected_rows),
            "theme_counts": theme_counts,
            "used_fallback": discovery.get("used_fallback", False),
            "data_gaps": _dedupe_strings((discovery.get("data_gaps") or []) + (daily_dataset.get("errors") or [])),
        }
    )
    return {
        "universe": selected_universe,
        "score_packet": score_packet,
        "raw_score_packet": raw_score_packet,
        "data_status": data_status,
        "discovery": discovery,
    }


def compare_etfs_within_theme(etf_scores, theme=None):
    rows = []
    if isinstance(etf_scores, dict):
        rows = etf_scores.get("rows") or etf_scores.get("etf_score_table") or []
    elif isinstance(etf_scores, list):
        rows = etf_scores

    filtered = []
    for row in rows:
        row_theme = row.get("theme") or ""
        row_sub_theme = row.get("sub_theme") or ""
        if theme and theme not in {row_theme, row_sub_theme}:
            continue
        filtered.append(dict(row))

    filtered = sorted(filtered, key=_selection_priority, reverse=True)
    if not filtered:
        return {
            "theme": theme or "",
            "best_liquidity_etf": None,
            "best_trend_etf": None,
            "lowest_volatility_etf": None,
            "most_balanced_etf": None,
            "warning_etfs": [],
            "comparison_reason": ["当前主题没有可比较的 ETF 数据。"],
            "rows": [],
        }

    liquidity_best = max(filtered, key=lambda item: _safe_float(item.get("amount_ma20")) or -1)
    trend_best = max(filtered, key=lambda item: ((_safe_float(item.get("trend_score")) or 0), (_safe_float(item.get("return_20d_pct")) or -999)))
    low_vol_best = min(
        [item for item in filtered if item.get("volatility_20d") is not None] or filtered,
        key=lambda item: _safe_float(item.get("volatility_20d")) or 999,
    )

    def _balanced_score(item):
        total = _safe_float(item.get("total_score")) or 0
        liquidity = min((_safe_float(item.get("amount_ma20")) or 0) / 50000, 12)
        vol = _safe_float(item.get("volatility_20d")) or 30
        completeness = (_safe_float(item.get("data_completeness")) or 0) / 10
        return total + liquidity + completeness - abs(vol - 18) * 0.25

    most_balanced = max(filtered, key=_balanced_score)
    warning_rows = [
        item for item in filtered
        if item.get("state") in {"破位回避", "过热等待", "数据不足"}
        or ((_safe_float(item.get("amount_ma20")) or 0) < 15000)
        or ((_safe_float(item.get("data_completeness")) or 0) < 60)
    ]
    reasons = [
        f"流动性优先看 {liquidity_best.get('etf_name')}，其成交额 MA20 更高。",
        f"趋势优先看 {trend_best.get('etf_name')}，其趋势/动量分更靠前。",
        f"波动更低的是 {low_vol_best.get('etf_name')}，更适合保守替代。",
        f"综合平衡优先看 {most_balanced.get('etf_name')}，兼顾流动性、趋势和数据完整度。",
    ]
    if warning_rows:
        reasons.append("部分 ETF 出现过热、破位或流动性不足，只适合观察，不适合简单叠加配置。")

    avg_score = sum(_safe_float(item.get("total_score")) or 0 for item in filtered) / max(len(filtered), 1)
    overheat_count = sum(1 for item in filtered if item.get("state") == "过热等待")
    weak_count = sum(1 for item in filtered if item.get("state") in {"破位回避", "震荡观察"})
    strong_count = sum(1 for item in filtered if item.get("state") in {"强趋势", "温和向上"})
    theme_name = theme or filtered[0].get("theme") or filtered[0].get("sub_theme") or "当前主题"
    if theme_name in {"黄金/黄金股", "红利/低波"}:
        comparison_summary = f"{theme_name}：防守属性较强，可作为现金替代观察。同赛道 ETF 高度重叠，不建议重复配置多只同类产品。"
        summary_tone = "info"
    elif weak_count >= max(len(filtered) / 2, 1):
        comparison_summary = f"{theme_name}：整体偏弱，暂不作为主攻方向。同赛道 ETF 高度重叠，不建议重复配置多只同类产品。"
        summary_tone = "warning"
    elif overheat_count >= 1 and avg_score >= 68:
        comparison_summary = f"{theme_name}：趋势强，但多只 ETF 过热，适合观察，不适合追高。同赛道 ETF 高度重叠，不建议重复配置多只同类产品。"
        summary_tone = "warning"
    elif strong_count >= max(len(filtered) / 2, 1):
        comparison_summary = f"{theme_name}：趋势偏强，优先看更均衡或趋势更强的产品。同赛道 ETF 高度重叠，不建议重复配置多只同类产品。"
        summary_tone = "success"
    else:
        comparison_summary = f"{theme_name}：强弱分化，优先看更均衡、流动性更好的产品。同赛道 ETF 高度重叠，不建议重复配置多只同类产品。"
        summary_tone = "info"

    return {
        "theme": theme or filtered[0].get("sub_theme") or filtered[0].get("theme") or "",
        "best_liquidity_etf": liquidity_best.get("etf_code"),
        "best_trend_etf": trend_best.get("etf_code"),
        "lowest_volatility_etf": low_vol_best.get("etf_code"),
        "most_balanced_etf": most_balanced.get("etf_code"),
        "warning_etfs": [item.get("etf_code") for item in warning_rows],
        "comparison_summary": comparison_summary,
        "summary_tone": summary_tone,
        "comparison_reason": reasons,
        "rows": filtered,
    }


def _normalize_holding_records(frame):
    records = []
    for _, row in frame.iterrows():
        payload = row.where(row.notna(), None).to_dict()
        stock_code = _first_not_empty(payload.get("stock_code"), payload.get("symbol"), payload.get("con_code"), payload.get("ts_code"))
        stock_name = _first_not_empty(payload.get("stock_name"), payload.get("name"), payload.get("con_name"))
        weight = _safe_float(
            payload.get("weight")
            or payload.get("stk_mkv_ratio")
            or payload.get("hold_ratio")
            or payload.get("amount_ratio")
            or payload.get("position_ratio")
        )
        position_ratio = _safe_float(payload.get("position_ratio") or payload.get("hold_ratio") or payload.get("stk_mkv_ratio") or weight)
        if not stock_code and not stock_name:
            continue
        records.append(
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "weight": _round2(weight),
                "position_ratio": _round2(position_ratio),
                "report_date": _first_not_empty(payload.get("report_date"), payload.get("ann_date")),
                "end_date": _first_not_empty(payload.get("end_date"), payload.get("period"), payload.get("trade_date")),
            }
        )
    records.sort(key=lambda item: _safe_float(item.get("weight")) or -1, reverse=True)
    return records


def fetch_etf_holdings_snapshot(etf_codes, max_etfs=20, tushare_adapter=None):
    adapter = tushare_adapter
    normalized_codes = []
    for code in etf_codes or []:
        normalized = _normalize_etf_code(code)
        if normalized and normalized not in normalized_codes:
            normalized_codes.append(normalized)
    normalized_codes = normalized_codes[: max(max_etfs, 0)]

    result = {
        "holdings_available": False,
        "holdings_errors": [],
        "snapshots": {},
    }
    if adapter is None:
        result["holdings_errors"].append("tushare_adapter 不可用，持仓明细暂不可用。")
        return result

    fetchers = [
        ("fund_portfolio", getattr(adapter, "get_fund_portfolio", None)),
        ("fund_holdings", getattr(adapter, "get_fund_holdings", None)),
        ("fund_top10", getattr(adapter, "get_fund_top10", None)),
        ("fund_report_stock", getattr(adapter, "get_fund_report_stock", None)),
    ]
    fetchers = [(name, call) for name, call in fetchers if callable(call)]
    if not fetchers:
        result["holdings_errors"].append("持仓接口未接入，当前仅按行情、跟踪指数和流动性比较。")
        return result

    for code in normalized_codes:
        snapshot = {
            "available": False,
            "source_api": "",
            "latest_report_date": "",
            "holdings": [],
            "error": "",
        }
        for api_name, fetcher in fetchers:
            try:
                api_result = fetcher(ts_code=code)
            except TypeError:
                api_result = fetcher(code)
            frame = _frame_from_result(api_result)
            if api_result.get("ok") and not frame.empty:
                holdings = _normalize_holding_records(frame)
                if holdings:
                    snapshot["available"] = True
                    snapshot["source_api"] = api_name
                    snapshot["latest_report_date"] = _first_not_empty(
                        holdings[0].get("report_date"),
                        holdings[0].get("end_date"),
                    )
                    snapshot["holdings"] = holdings[:10]
                    result["holdings_available"] = True
                    break
            if api_result.get("error"):
                snapshot["error"] = _error_text(api_result)
        if not snapshot["available"] and snapshot["error"]:
            result["holdings_errors"].append(f"{code}｜{snapshot['error']}")
        result["snapshots"][code] = snapshot

    result["holdings_errors"] = _dedupe_strings(result["holdings_errors"])
    return result


def fetch_intraday_etf_snapshot(etf_universe, tushare_adapter=None):
    adapter = tushare_adapter
    snapshot = {
        "data_source": "tushare_realtime",
        "available": False,
        "used_realtime": False,
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "rows": [],
        "errors": [],
    }
    if adapter is None:
        snapshot["errors"].append("tushare_adapter 不可用")
        return snapshot

    for item in etf_universe or []:
        code = _normalize_etf_code(item.get("code") or item.get("ts_code"))
        row = {
            "etf_code": code,
            "etf_name": item.get("name") or item.get("etf_name") or code,
            "bucket": item.get("bucket") or "",
            "realtime_price": None,
            "trade_time": "",
            "realtime_iopv": None,
            "premium_discount_pct": None,
            "source_status": {},
            "errors": [],
        }

        rt_result = adapter.get_rt_etf_k(ts_code=code)
        rt_frame = _frame_from_result(rt_result)
        if rt_result.get("ok") and not rt_frame.empty:
            rt_latest = rt_frame.iloc[0]
            row["realtime_price"] = _round2(rt_latest.get("close"))
            row["trade_time"] = str(rt_latest.get("trade_time") or rt_latest.get("date") or "")
            row["source_status"]["rt_etf_k"] = "ok"
            snapshot["used_realtime"] = True
            snapshot["available"] = True
        else:
            row["errors"].append(f"rt_etf_k: {_error_text(rt_result)}")
            row["source_status"]["rt_etf_k"] = "error"

        if code.endswith(".SZ"):
            iopv_result = adapter.get_rt_etf_sz_iopv(ts_code=code)
            iopv_frame = _frame_from_result(iopv_result)
            if iopv_result.get("ok") and not iopv_frame.empty:
                iopv_latest = iopv_frame.iloc[0]
                row["realtime_iopv"] = _round2(iopv_latest.get("iopv"))
                row["source_status"]["rt_etf_sz_iopv"] = "ok"
                if row["realtime_price"] and row["realtime_iopv"]:
                    row["premium_discount_pct"] = _round2((row["realtime_price"] / row["realtime_iopv"] - 1) * 100)
            else:
                row["errors"].append(f"rt_etf_sz_iopv: {_error_text(iopv_result)}")
                row["source_status"]["rt_etf_sz_iopv"] = "error"

        if row["errors"]:
            snapshot["errors"].extend([f"{code}｜{message}" for message in row["errors"][:2]])
        snapshot["rows"].append(row)
    snapshot["errors"] = _dedupe_strings(snapshot["errors"])
    return snapshot
