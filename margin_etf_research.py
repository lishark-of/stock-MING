from __future__ import annotations

import hashlib
import json


REPORT_TYPE = "margin_etf_daily_research"


def build_margin_etf_allocation_hash(allocation_result):
    payload = {
        "action_state": (allocation_result or {}).get("action_state"),
        "recommended_margin_ratio": (allocation_result or {}).get("recommended_margin_ratio"),
        "recommended_cash_ratio": (allocation_result or {}).get("recommended_cash_ratio"),
        "recommended_total_exposure_ratio": (allocation_result or {}).get("recommended_total_exposure_ratio"),
        "dynamic_bucket_weights": (allocation_result or {}).get("dynamic_bucket_weights"),
        "selected_etf_candidates": (allocation_result or {}).get("selected_etf_candidates"),
        "overweight_buckets": (allocation_result or {}).get("overweight_buckets"),
        "underweight_buckets": (allocation_result or {}).get("underweight_buckets"),
        "data_date": (allocation_result or {}).get("data_date"),
        "etf_universe_mode": (allocation_result or {}).get("etf_universe_mode"),
        "theme_comparison": (allocation_result or {}).get("theme_comparison"),
        "holdings_snapshot": (allocation_result or {}).get("holdings_snapshot"),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_margin_etf_research_prompt(packet):
    payload_text = json.dumps(packet, ensure_ascii=False, indent=2, default=str)
    return f"""
你是克制、专业的 ETF 两融配置解释员。你的任务是解释规则模型给出的结果，不得擅自改写仓位。

【硬性边界】
1. 只能解释，不直接决定仓位；仓位以 allocation_result 为准。
2. 必须明确说明：融资会放大收益和亏损，不构成买卖建议。
3. 禁止输出绝对化、高杠杆、保证收益、无条件加仓、确定性收益表述。
4. 如果数据缺口存在，必须写入“数据缺口”。
5. 如果某些 ETF 过热或破位，必须明确写“只观察不追”或“等待回踩验证”。
6. 必须明确说明：“同赛道 ETF 可能高度重叠，不应简单叠加配置。”
7. 必须明确说明：“ETF 持仓会随季报/公告变化，Tushare 持仓数据可能有滞后，配置结论必须结合最新行情和风险线。”

【输出格式】
请只输出一个 JSON 对象，字段如下：
{{
  "one_sentence_conclusion": "一句话结论",
  "today_allocation_explanation": ["今日 ETF 配置解释1", "解释2"],
  "why_margin_ratio": ["为什么是这个融资比例"],
  "bucket_adjustments": ["为什么某些 bucket 增配/降配"],
  "theme_comparison_explanation": ["同赛道 ETF 为什么选 A 不选 B"],
  "overlap_and_substitution": ["哪些 ETF 只是同赛道替代品，不应重复配置；是否存在持仓高度重叠"],
  "watch_not_chase": ["哪些 ETF 只观察不追"],
  "add_margin_triggers": ["哪些条件触发加融资"],
  "deleverage_triggers": ["哪些条件触发降融资"],
  "tomorrow_checklist": ["明日验证清单"],
  "data_gaps": ["数据缺口"],
  "risk_disclaimer": "融资会放大收益和亏损。本模块只做风险预算和仓位测算，不构成买卖建议。"
}}

【结构化输入】
{payload_text}
"""
