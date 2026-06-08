from __future__ import annotations

import datetime as _dt
import json
import math
from collections.abc import Mapping
from numbers import Number
from statistics import NormalDist
from typing import Any

from market_analysis_profile import (
    MARKET_A_SHARE,
    MARKET_ETF,
    MARKET_US_STOCK,
    get_market_analysis_profile,
    identify_market_type,
)


SOURCE = "rule-based market profile"
READY_STATUSES = {"ok", "ready", "completed", "complete", "success", "succeeded", "已刷新"}

CHOKEPOINT_SOURCE = "serenity_chokepoint_bayesian_packet"
FORCED_DOWNGRADE_MESSAGE = "该标的当前无实质半导体散热产能支撑，属于情绪蹭热点"

CHOKEPOINT_SCORE_WEIGHTS = {
    "expansion_cycle_difficulty": 0.08,
    "customer_qualification_strictness": 0.08,
    "material_purity_requirement": 0.07,
    "supplier_scarcity": 0.08,
    "process_knowhow_depth": 0.07,
    "equipment_dependency": 0.06,
    "yield_ramp_uncertainty": 0.06,
    "substitution_difficulty": 0.07,
    "policy_support_intensity": 0.06,
    "import_substitution_urgency": 0.07,
    "downstream_demand_elasticity": 0.06,
    "pricing_power_capture": 0.06,
    "a_share_microstructure_heat": 0.04,
    "disclosure_evidence_quality": 0.08,
    "balance_sheet_capex_capacity": 0.06,
}

CHOKEPOINT_SCORE_DIMENSION_LABELS = {
    "expansion_cycle_difficulty": "扩产周期困难度",
    "customer_qualification_strictness": "客户认证严格度",
    "material_purity_requirement": "材料纯度要求",
    "supplier_scarcity": "供应商数量稀缺性",
    "process_knowhow_depth": "工艺 know-how 深度",
    "equipment_dependency": "核心设备依赖度",
    "yield_ramp_uncertainty": "良率爬坡不确定性",
    "substitution_difficulty": "替代方案切换难度",
    "policy_support_intensity": "政策支持强度",
    "import_substitution_urgency": "国产替代紧迫度",
    "downstream_demand_elasticity": "下游需求弹性",
    "pricing_power_capture": "涨价与利润捕获能力",
    "a_share_microstructure_heat": "A股微观资金热度",
    "disclosure_evidence_quality": "公告与一手证据质量",
    "balance_sheet_capex_capacity": "资产负债表扩产承受力",
}

DEFAULT_CHOKEPOINT_PRIOR_SCORES = {
    "expansion_cycle_difficulty": 55,
    "customer_qualification_strictness": 50,
    "material_purity_requirement": 52,
    "supplier_scarcity": 52,
    "process_knowhow_depth": 54,
    "equipment_dependency": 46,
    "yield_ramp_uncertainty": 50,
    "substitution_difficulty": 48,
    "policy_support_intensity": 55,
    "import_substitution_urgency": 55,
    "downstream_demand_elasticity": 60,
    "pricing_power_capture": 45,
    "a_share_microstructure_heat": 35,
    "disclosure_evidence_quality": 30,
    "balance_sheet_capex_capacity": 40,
}

CHOKEPOINT_HARD_CAPACITY_KEYWORDS = [
    "半导体级CVD",
    "半导体级 CVD",
    "半导体散热",
    "CVD产线",
    "CVD 产线",
    "CVD衬底",
    "CVD 衬底",
    "金刚石铜",
    "金刚石-铜",
    "大尺寸衬底",
    "封装工艺",
    "不浸润",
    "客户认证",
    "送样认证",
    "新增设备订单",
    "研发费用",
    "研发投入",
    "资本开支",
    "量产线",
    "中试线",
]

CHOKEPOINT_HYPE_ONLY_TERMS = [
    "培育钻石",
    "珠宝零售",
    "饰品",
    "黄金珠宝",
    "婚庆消费",
    "钻戒",
]


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _now_iso(now: Any = None) -> str:
    if isinstance(now, _dt.datetime):
        return now.isoformat(timespec="seconds")
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min).isoformat(timespec="seconds")
    if isinstance(now, str) and now.strip():
        return now.strip()
    return _dt.datetime.now().isoformat(timespec="seconds")


def _packet_state(section: Any) -> str:
    payload = _as_mapping(section)
    if not payload:
        return "missing"
    status = _to_text(payload.get("status"))
    if payload.get("is_fresh") is True or status in READY_STATUSES or status.lower() in READY_STATUSES:
        return "ready"
    if payload.get("last_success") or payload.get("stale") or _to_text(payload.get("refresh_label")) == "使用缓存":
        return "cached"
    return "missing"


def _coverage(live_packet: Any, strategy_packet: Any, decision_packet: Any) -> dict:
    live = _as_mapping(live_packet)
    return {
        "market": _packet_state(live.get("market")),
        "quant": _packet_state(live.get("quant")),
        "discipline": _packet_state(live.get("discipline")),
        "margin_etf": _packet_state(live.get("margin_etf")),
        "next_ticket": _packet_state(live.get("next_ticket")),
        "strategy_execution": _packet_state(strategy_packet),
        "decision": _packet_state(decision_packet),
    }


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _method_status(name: str, profile: Mapping[str, Any], coverage: Mapping[str, str], context_text: str) -> str:
    market = _to_text(profile.get("market"))
    method_names = {item.get("name"): item for item in _as_list(profile.get("methods")) if isinstance(item, Mapping)}
    fit = _to_text(_as_mapping(method_names.get(name)).get("fit"))
    if fit == "不适用":
        return "不适用"

    has_any_data = any(state in {"ready", "cached"} for state in coverage.values())
    if not has_any_data:
        return "待验证"

    if _contains_any(context_text, ["降风险", "禁止", "卖出", "减仓", "回撤过高", "风险高"]):
        if name in {"风险预算 / 仓位管理", "资金流 / 机构行为", "事件驱动 / 财报 / 公告"}:
            return "失败"
        return "待验证"

    if name in {"趋势跟踪", "Stage Analysis", "量价结构"}:
        return "通过" if coverage.get("quant") == "ready" or coverage.get("market") == "ready" else "待验证"
    if name == "风险预算 / 仓位管理":
        return "通过" if coverage.get("strategy_execution") in {"ready", "cached"} or coverage.get("decision") in {"ready", "cached"} else "待验证"
    if name == "ETF 赛道配置":
        return "通过" if market == MARKET_ETF and coverage.get("margin_etf") in {"ready", "cached"} else ("不适用" if market != MARKET_ETF else "待验证")
    if market == MARKET_A_SHARE and name == "资金流 / 机构行为":
        return "通过" if coverage.get("market") == "ready" else "待验证"
    if market == MARKET_US_STOCK and name in {"CAN SLIM / 机构成长股", "事件驱动 / 财报 / 公告", "宏观流动性 / 利率 / 汇率"}:
        return "待验证"
    return "待验证"


def _method_by_name(profile: Mapping[str, Any], name: str) -> dict:
    for item in _as_list(profile.get("methods")):
        payload = _as_mapping(item)
        if payload.get("name") == name:
            return payload
    return {"name": name, "fit": "待适配", "evidence_focus": [], "risk_focus": [], "action_hint": "等待市场画像补齐。"}


def _method_evidence(method: Mapping[str, Any], coverage: Mapping[str, str]) -> str:
    focus = "、".join(_as_list(method.get("evidence_focus"))[:4]) or "暂无证据项"
    ready = [key for key, state in coverage.items() if state == "ready"]
    cached = [key for key, state in coverage.items() if state == "cached"]
    if ready:
        return f"关注 {focus}；已刷新模块：{', '.join(ready)}。"
    if cached:
        return f"关注 {focus}；当前主要使用缓存：{', '.join(cached)}。"
    return f"关注 {focus}；数据不足，待刷新验证。"


def _summary_text(market: str, coverage: Mapping[str, str], methods: list[dict]) -> str:
    passed = [item["name"] for item in methods if item["status"] == "通过"]
    failed = [item["name"] for item in methods if item["status"] == "失败"]
    if failed:
        return f"{market} 分析框架提示风险项：{'、'.join(failed[:3])}。先降风险或等待验证。"
    if passed:
        return f"{market} 分析框架已有可用证据：{'、'.join(passed[:3])}；其余方法继续待验证。"
    if any(state in {"ready", "cached"} for state in coverage.values()):
        return f"{market} 分析框架已读取缓存/刷新结果，但多数方法仍需验证。"
    return f"{market} 分析框架等待数据刷新，不假装生成完整结论。"


def build_analysis_method_packet(
    market_type: Any = None,
    live_packet: Any = None,
    strategy_packet: Any = None,
    decision_packet: Any = None,
    ticker: Any = "",
    name: Any = "",
    profile: Any = None,
    now: Any = None,
) -> dict:
    resolved_market = _to_text(market_type)
    if not resolved_market:
        resolved_market = identify_market_type(ticker=ticker, name=name)
    market_profile = _as_mapping(profile) or get_market_analysis_profile(resolved_market, ticker=ticker, name=name)
    market = _to_text(market_profile.get("market"), resolved_market or "未知")
    coverage = _coverage(live_packet, strategy_packet, decision_packet)
    context_text = " ".join(
        [
            _to_text(_as_mapping(decision_packet).get("overall_action")),
            _to_text(_as_mapping(decision_packet).get("risk_level")),
            _to_text(_as_mapping(strategy_packet).get("action")),
            _to_text(_as_mapping(strategy_packet).get("summary")),
        ]
    )

    method_names = [
        "趋势跟踪",
        "Stage Analysis",
        "CAN SLIM / 机构成长股",
        "VCP / 波动收敛突破",
        "相对强弱 RS / 行业轮动",
        "量价结构",
        "资金流 / 机构行为",
        "风险预算 / 仓位管理",
        "事件驱动 / 财报 / 公告",
        "宏观流动性 / 利率 / 汇率",
        "ETF 赛道配置",
    ]
    methods = []
    for method_name in method_names:
        method = _method_by_name(market_profile, method_name)
        status = _method_status(method_name, market_profile, coverage, context_text)
        methods.append(
            {
                "name": method_name,
                "status": status,
                "evidence": _method_evidence(method, coverage),
                "risk": "、".join(_as_list(method.get("risk_focus"))[:4]) or "数据缺口",
                "action_hint": _to_text(method.get("action_hint"), "待验证后再行动。"),
                "fit": _to_text(method.get("fit"), "待适配"),
            }
        )

    return {
        "market": market,
        "profile": market_profile,
        "methods": methods,
        "summary": _summary_text(market, coverage, methods),
        "data_coverage": dict(coverage),
        "updated_at": _now_iso(now),
        "source": SOURCE,
        "deepseek_called": False,
        "last_error": None,
    }


def _home_method_tone(status: str) -> str:
    if status == "通过":
        return "success"
    if status == "失败":
        return "danger"
    if status == "不适用":
        return "muted"
    return "warning"


def _home_method_rank(item: Mapping[str, Any]) -> tuple[int, int]:
    status = _to_text(item.get("status"))
    fit = _to_text(item.get("fit"))
    status_rank = {"失败": 0, "通过": 1, "待验证": 2, "不适用": 9}.get(status, 3)
    fit_rank = {"核心": 0, "辅助": 1, "待适配": 2, "不适用": 9}.get(fit, 3)
    return status_rank, fit_rank


def build_home_analysis_method_summary(packet: Any = None) -> dict:
    payload = _as_mapping(packet)
    profile = _as_mapping(payload.get("profile"))
    market = _to_text(payload.get("market")) or _to_text(profile.get("market")) or "未知"
    label = _to_text(profile.get("label")) or ("市场类型待确认" if market in {"", "未知"} else market)
    methods = [_as_mapping(item) for item in _as_list(payload.get("methods")) if _as_mapping(item)]
    applicable = [item for item in methods if _to_text(item.get("status")) != "不适用"]
    ranked = sorted(applicable, key=_home_method_rank)
    visible_methods = []
    for item in ranked[:4]:
        visible_methods.append(
            {
                "name": _to_text(item.get("name"), "分析方法"),
                "status": _to_text(item.get("status"), "待验证"),
                "tone": _home_method_tone(_to_text(item.get("status"))),
                "fit": _to_text(item.get("fit"), "待适配"),
                "action_hint": _to_text(item.get("action_hint"), "待验证后再行动。"),
            }
        )
    if not visible_methods:
        visible_methods = [
            {
                "name": "市场画像",
                "status": "待验证",
                "tone": "warning",
                "fit": "待适配",
                "action_hint": "先确认标的和市场类型。",
            }
        ]

    coverage = _as_mapping(payload.get("data_coverage"))
    ready_count = len([state for state in coverage.values() if state == "ready"])
    cached_count = len([state for state in coverage.values() if state == "cached"])
    pending_count = len([item for item in visible_methods if item.get("status") == "待验证"])
    failed_count = len([item for item in visible_methods if item.get("status") == "失败"])
    if failed_count:
        headline = f"{label}：先处理风险方法"
        next_action = "风险方法未解除前，主路径只观察或降风险。"
        tone = "danger"
    elif ready_count:
        headline = f"{label}：已有可用分析口径"
        next_action = "按已通过方法验证趋势、仓位和失效条件。"
        tone = "success"
    elif cached_count:
        headline = f"{label}：读取缓存口径"
        next_action = "缓存只辅助判断，执行前等待价格和纪律确认。"
        tone = "warning"
    else:
        headline = f"{label}：等待数据验证"
        next_action = "先刷新基础数据，不把通用框架当成结论。"
        tone = "warning"

    focus_items = _as_list(profile.get("indicator_focus"))[:5]
    risk_items = _as_list(profile.get("risk_focus"))[:4]
    return {
        "market": market or "未知",
        "label": label,
        "headline": headline,
        "summary": _to_text(payload.get("summary"), f"{label} 分析框架等待数据验证。"),
        "tone": tone,
        "method_items": visible_methods,
        "focus_items": focus_items or ["趋势", "量价", "风险预算"],
        "risk_items": risk_items or ["数据缺口", "流动性"],
        "status_counts": {
            "ready_modules": ready_count,
            "cached_modules": cached_count,
            "pending_methods": pending_count,
            "failed_methods": failed_count,
        },
        "next_action": next_action,
        "updated_at": _to_text(payload.get("updated_at"), "暂无"),
        "deepseek_called": False,
        "deepseek_text": "DeepSeek：未调用",
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, Number):
        result = float(value)
        return result if math.isfinite(result) else default
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text.endswith("%"):
            text = text[:-1]
        try:
            result = float(text)
            return result if math.isfinite(result) else default
        except Exception:
            return default
    return default


def _clamp(value: Any, low: float = 0.0, high: float = 100.0) -> float:
    numeric = _safe_float(value, low)
    return max(low, min(high, numeric))


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return _to_text(value)


def get_chokepoint_score_weights() -> dict:
    return dict(CHOKEPOINT_SCORE_WEIGHTS)


def normalize_chokepoint_scores(scores: Any = None) -> dict:
    payload = _as_mapping(scores)
    normalized = {}
    for dimension, default_score in DEFAULT_CHOKEPOINT_PRIOR_SCORES.items():
        normalized[dimension] = round(_clamp(payload.get(dimension, default_score)), 2)
    return normalized


def calculate_true_chokepoint_score(scores: Any = None, weights: Any = None) -> float:
    dimension_scores = normalize_chokepoint_scores(scores)
    dimension_weights = _as_mapping(weights) or CHOKEPOINT_SCORE_WEIGHTS
    weighted_sum = 0.0
    total_weight = 0.0
    for dimension, score in dimension_scores.items():
        weight = _safe_float(dimension_weights.get(dimension), 0.0)
        if weight <= 0:
            continue
        weighted_sum += score * weight
        total_weight += weight
    if total_weight <= 0:
        return 0.0
    return round(weighted_sum / total_weight, 2)


def bayesian_update_probability(prior_probability: Any, likelihood_true: Any, likelihood_false: Any) -> float:
    prior = _safe_float(prior_probability, 0.50)
    if prior > 1:
        prior = prior / 100
    prior = _clamp(prior, 0.01, 0.99)
    likelihood_h = _safe_float(likelihood_true, 0.50)
    likelihood_not_h = _safe_float(likelihood_false, 0.50)
    if likelihood_h > 1:
        likelihood_h = likelihood_h / 100
    if likelihood_not_h > 1:
        likelihood_not_h = likelihood_not_h / 100
    likelihood_h = _clamp(likelihood_h, 0.01, 0.99)
    likelihood_not_h = _clamp(likelihood_not_h, 0.01, 0.99)

    numerator = prior * likelihood_h
    denominator = numerator + (1 - prior) * likelihood_not_h
    if denominator <= 0:
        return round(prior, 4)
    return round(numerator / denominator, 4)


def build_chokepoint_deepseek_prompt(theme: Any, evidence_payload: Any = None, max_candidates: int = 8) -> str:
    theme_text = _to_text(theme, "待分析科技题材")
    evidence_text = _json_text(evidence_payload or {})
    candidate_limit = max(1, min(int(max_candidates or 8), 12))
    forbidden_terms = "、".join(CHOKEPOINT_HYPE_ONLY_TERMS)
    hard_keywords = "、".join(CHOKEPOINT_HARD_CAPACITY_KEYWORDS[:12])

    return f"""
你要把一个模糊科技热点拆成 A 股可验证的产业链卡脖子节点。

【输入题材】
{theme_text}

【已有结构化证据 JSON】
{evidence_text}

【冷酷过滤机制】
1. 禁止把“{forbidden_terms}”当作卡脖子节点输出；这些最多只能作为伪概念/蹭热点风险。
2. 必须命名到材料、设备、工艺、封装、认证或产能层级，例如“半导体级大尺寸 CVD 金刚石衬底”“金刚石与铜的不浸润封装工艺”“CVD 生长设备与良率爬坡”。
3. 如果只能说“金刚石概念”“散热材料”“培育钻石受益”，必须判定为 insufficient_specificity，不得进入候选标的表。
4. 对每个 A 股候选标的，只能用公告、财报、问询函回复、投资者关系记录、设备订单、研发费用、产线投资、客户认证等证据支撑。若缺少 “{hard_keywords}” 这类硬证据，必须逐字输出：
{FORCED_DOWNGRADE_MESSAGE}
5. 资金流、龙虎榜、涨停、算力板块估值溢出只能标记为 speculative accelerant，不得替代真实产能证据。
6. 必须结合 A 股政策导向、国产替代叙事、游资/主力资金短期拔估值特征，把标的分为：
   - Tier 1 真瓶颈：硬证据 + 产能/认证 + 节点不可替代
   - Tier 2 待核实瓶颈：节点匹配但公告证据不足
   - Tier 3 情绪蹭热点：资金强、证据弱或主营偏离
   - Excluded 排除：只沾“培育钻石/珠宝零售/泛材料”概念

【输出 JSON，禁止输出 JSON 以外文字】
{{
  "theme": "{theme_text}",
  "specificity_status": "ok | insufficient_specificity",
  "cycle_stage": {{
    "stage": "需求爆发期 | 技术跃迁期 | 供给受限期 | 待验证",
    "reason": "一句话依据"
  }},
  "supply_chain_layers": [
    {{"layer": "终端/系统/模块/材料/设备/工艺", "node": "具体节点", "bottleneck_risk": "为什么会卡"}}
  ],
  "technical_chokepoint_nodes": [
    {{
      "node": "具体技术卡点",
      "why_it_blocks": "卡住下游的物理原因",
      "technical_specificity": "材料/设备/工艺/认证/良率的具体描述",
      "forbidden_broad_concept_check": "是否避开培育钻石/珠宝零售等伪概念",
      "policy_link": "政策/国产替代/出口管制/算力建设的关系",
      "a_share_microstructure": "短期游资/主力/估值溢出如何影响，但不能替代证据"
    }}
  ],
  "candidate_stocks": [
    {{
      "name": "公司简称",
      "ticker": "A股代码",
      "matched_node": "对应技术卡点",
      "tier": "Tier 1 真瓶颈 | Tier 2 待核实瓶颈 | Tier 3 情绪蹭热点 | Excluded",
      "evidence_level": "公告硬证据 | 财报/IR中证据 | 新闻线索 | 无硬证据",
      "substantive_capacity_evidence": true,
      "downgrade_required": false,
      "downgrade_notice": "",
      "speculative_tags": ["算力板块估值溢出", "主力资金异动", "短线连板情绪"],
      "required_checks": ["还需要核验的公告/财报/问询函字段"]
    }}
  ],
  "bayesian_scorecard": [
    {{
      "ticker": "A股代码或 THEME",
      "prior_probability": 0.45,
      "positive_evidence": ["硬证据"],
      "negative_evidence": ["反证据"],
      "posterior_direction": "up | down | unchanged",
      "dimension_notes": {{"disclosure_evidence_quality": "为什么调整"}}
    }}
  ],
  "anti_thesis": [
    "### 反向加压与伪证模块：至少 3 条否定该题材短期爆发的硬边界"
  ],
  "open_checks": [
    "必须继续核验的一手来源"
  ],
  "candidate_limit": {candidate_limit}
}}
"""


def build_chokepoint_prompt_packet(theme: Any, evidence_payload: Any = None, max_candidates: int = 8, now: Any = None) -> dict:
    return {
        "theme": _to_text(theme, "待分析科技题材"),
        "prompt": build_chokepoint_deepseek_prompt(theme, evidence_payload=evidence_payload, max_candidates=max_candidates),
        "required_system_prompt": "analysis_engine.build_serenity_chokepoint_system_prompt",
        "schema_version": "2026-06-serenity-chokepoint-v1",
        "updated_at": _now_iso(now),
        "deepseek_called": False,
        "source": CHOKEPOINT_SOURCE,
    }


def _extract_json_object_text(raw: str) -> str:
    text = _to_text(raw)
    if not text:
        return ""
    fence_start = text.find("```")
    if fence_start >= 0:
        stripped = text.replace("```json", "```").replace("```JSON", "```")
        parts = stripped.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()

    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def parse_chokepoint_deepseek_response(raw_response: Any) -> dict:
    if isinstance(raw_response, Mapping):
        return {"parse_status": "json", "payload": dict(raw_response), "raw_text": ""}
    raw_text = _to_text(raw_response)
    if not raw_text:
        return {"parse_status": "empty", "payload": {}, "raw_text": ""}
    json_text = _extract_json_object_text(raw_text)
    if json_text:
        try:
            payload = json.loads(json_text)
            return {"parse_status": "json", "payload": _as_mapping(payload), "raw_text": raw_text}
        except Exception as exc:
            return {"parse_status": "parse_failed", "payload": {}, "raw_text": raw_text, "parse_error": str(exc)}
    return {"parse_status": "raw_text", "payload": {}, "raw_text": raw_text}


def _company_evidence_for_candidate(candidate: Mapping[str, Any], evidence_payload: Any = None) -> Any:
    evidence = _as_mapping(evidence_payload)
    if not evidence:
        return {}
    ticker = _to_text(candidate.get("ticker"))
    name = _to_text(candidate.get("name"))
    company_evidence = evidence.get("company_evidence") or evidence.get("companies") or evidence.get("candidate_evidence") or {}
    if isinstance(company_evidence, Mapping):
        return company_evidence.get(ticker) or company_evidence.get(name) or company_evidence.get(ticker.upper()) or {}
    return {}


def _has_hard_capacity_evidence(value: Any) -> bool:
    text = _json_text(value)
    if not text:
        return False
    return any(keyword in text for keyword in CHOKEPOINT_HARD_CAPACITY_KEYWORDS)


def apply_precision_downgrade_to_candidates(candidates: Any = None, evidence_payload: Any = None) -> list[dict]:
    normalized = []
    for item in _as_list(candidates):
        candidate = _as_mapping(item)
        if not candidate:
            continue
        company_evidence = _company_evidence_for_candidate(candidate, evidence_payload)
        has_evidence = bool(candidate.get("substantive_capacity_evidence")) and _has_hard_capacity_evidence(
            {"candidate": candidate, "company_evidence": company_evidence}
        )
        if not has_evidence:
            candidate["substantive_capacity_evidence"] = False
            candidate["downgrade_required"] = True
            candidate["downgrade_notice"] = FORCED_DOWNGRADE_MESSAGE
            if _to_text(candidate.get("tier")) in {"", "Tier 1 真瓶颈", "Tier 2 待核实瓶颈"}:
                candidate["tier"] = "Tier 3 情绪蹭热点"
            candidate.setdefault("required_checks", [])
            if isinstance(candidate["required_checks"], list):
                candidate["required_checks"].append("核验是否存在半导体级 CVD 产线投资、研发费用或新增设备订单公告")
        else:
            candidate["downgrade_required"] = False
            candidate.setdefault("downgrade_notice", "")
        normalized.append(candidate)
    return normalized


def _event_number_hint(event: Mapping[str, Any], keys: list[str]) -> float:
    for key in keys:
        if key in event:
            return _safe_float(event.get(key), 0.0)
    for value in event.values():
        if isinstance(value, Mapping):
            nested = _event_number_hint(value, keys)
            if nested:
                return nested
    return 0.0


def _build_bayesian_evidence_update(event: Any, default_source: str = "") -> dict:
    payload = _as_mapping(event)
    if not payload:
        return {}
    text = _json_text(payload)
    source = _to_text(payload.get("source") or payload.get("event_source"), default_source or "manual_event")
    event_type = _to_text(payload.get("event_type") or payload.get("type") or payload.get("kind"))

    negative_terms = ["问询函", "监管", "澄清", "未涉及", "不涉及", "无实质", "蹭热点", "产能不足", "认证失败", "客户取消"]
    positive_hard = _has_hard_capacity_evidence(payload) and not any(term in text for term in negative_terms)
    negative_hard = any(term in text for term in negative_terms)
    source_lower = source.lower()
    is_money_flow = "money" in source_lower or "资金" in text or "净流入" in text or "净流出" in text or event_type == "money_flow"
    is_disclosure = (
        "data_fetcher" in source_lower
        or "announcement" in source_lower
        or "公告" in text
        or "财报" in text
        or "问询函" in text
        or event_type in {"financial_report", "inquiry_letter", "announcement"}
    )

    if negative_hard:
        return {
            "source": source,
            "event_type": event_type or "negative_disclosure",
            "direction": "down",
            "likelihood_true": 0.24,
            "likelihood_false": 0.78,
            "score_deltas": {
                "disclosure_evidence_quality": -16,
                "customer_qualification_strictness": -8,
                "balance_sheet_capex_capacity": -6,
                "a_share_microstructure_heat": 3,
            },
            "note": "公告/问询/澄清类反证降低真瓶颈概率，资金热度若存在也只保留为短线情绪。",
        }
    if positive_hard and is_disclosure:
        return {
            "source": source,
            "event_type": event_type or "hard_disclosure",
            "direction": "up",
            "likelihood_true": 0.80,
            "likelihood_false": 0.25,
            "score_deltas": {
                "disclosure_evidence_quality": 14,
                "customer_qualification_strictness": 8,
                "balance_sheet_capex_capacity": 7,
                "process_knowhow_depth": 5,
                "policy_support_intensity": 3,
            },
            "note": "一手公告/财报出现半导体级 CVD、产线、设备订单、认证或研发投入硬证据。",
        }
    if positive_hard:
        return {
            "source": source,
            "event_type": event_type or "hard_lead",
            "direction": "up",
            "likelihood_true": 0.68,
            "likelihood_false": 0.35,
            "score_deltas": {
                "disclosure_evidence_quality": 8,
                "process_knowhow_depth": 5,
                "material_purity_requirement": 4,
            },
            "note": "出现硬证据线索，但仍需一手公告或财报复核。",
        }
    if is_money_flow:
        net_flow = _event_number_hint(
            payload,
            ["main_net_inflow", "main_net_amount", "net_main_inflow", "主力净流入", "net_inflow", "amount"],
        )
        if "净流出" in text or net_flow < 0:
            return {
                "source": source,
                "event_type": event_type or "money_flow_out",
                "direction": "down",
                "likelihood_true": 0.40,
                "likelihood_false": 0.65,
                "score_deltas": {"a_share_microstructure_heat": -12, "pricing_power_capture": -3},
                "note": "主力资金转弱只能降低短线热度，不能单独证伪技术瓶颈。",
            }
        return {
            "source": source,
            "event_type": event_type or "money_flow_in",
            "direction": "up",
            "likelihood_true": 0.56,
            "likelihood_false": 0.44,
            "score_deltas": {"a_share_microstructure_heat": 12, "pricing_power_capture": 2},
            "note": "主力资金异动只更新 A 股短线热度，不证明真实半导体产能。",
        }
    if is_disclosure:
        return {
            "source": source,
            "event_type": event_type or "soft_disclosure",
            "direction": "unchanged",
            "likelihood_true": 0.52,
            "likelihood_false": 0.50,
            "score_deltas": {"disclosure_evidence_quality": 2},
            "note": "披露事件未命中硬证据，维持谨慎先验。",
        }
    return {
        "source": source,
        "event_type": event_type or "generic_event",
        "direction": "unchanged",
        "likelihood_true": 0.51,
        "likelihood_false": 0.50,
        "score_deltas": {},
        "note": "未识别为强证据，仅记录为待核验线索。",
    }


def trigger_bayesian_chokepoint_update(
    ticker: Any,
    current_scores: Any = None,
    prior_probability: Any = None,
    money_flow_event: Any = None,
    disclosure_event: Any = None,
    data_fetcher_event: Any = None,
    events: Any = None,
    now: Any = None,
) -> dict:
    prior_scores = normalize_chokepoint_scores(current_scores)
    updated_scores = dict(prior_scores)
    prior_weighted_score = calculate_true_chokepoint_score(prior_scores)
    if prior_probability is None:
        probability = _clamp(prior_weighted_score / 100, 0.01, 0.99)
    else:
        probability = _safe_float(prior_probability, prior_weighted_score / 100)
        if probability > 1:
            probability = probability / 100
        probability = _clamp(probability, 0.01, 0.99)
    starting_probability = probability

    event_list = []
    event_list.extend(_as_list(events))
    for event in [money_flow_event, disclosure_event, data_fetcher_event]:
        if _as_mapping(event):
            event_list.append(event)

    evidence_updates = []
    for event in event_list:
        update = _build_bayesian_evidence_update(event)
        if not update:
            continue
        probability = bayesian_update_probability(
            probability,
            update.get("likelihood_true", 0.51),
            update.get("likelihood_false", 0.50),
        )
        for dimension, delta in _as_mapping(update.get("score_deltas")).items():
            if dimension in updated_scores:
                updated_scores[dimension] = round(_clamp(updated_scores[dimension] + _safe_float(delta, 0.0)), 2)
        update["posterior_probability"] = probability
        evidence_updates.append(update)

    posterior_weighted_score = calculate_true_chokepoint_score(updated_scores)
    posterior_true_score = round(0.70 * posterior_weighted_score + 0.30 * probability * 100, 2)
    prior_true_score = round(0.70 * prior_weighted_score + 0.30 * starting_probability * 100, 2)

    scorecard_rows = []
    for dimension, weight in CHOKEPOINT_SCORE_WEIGHTS.items():
        before = prior_scores[dimension]
        after = updated_scores[dimension]
        scorecard_rows.append(
            {
                "dimension": dimension,
                "label": CHOKEPOINT_SCORE_DIMENSION_LABELS.get(dimension, dimension),
                "weight": weight,
                "prior_score": before,
                "posterior_score": after,
                "delta": round(after - before, 2),
            }
        )

    return {
        "ticker": _to_text(ticker, "THEME"),
        "prior_probability": round(starting_probability, 4),
        "posterior_probability": round(probability, 4),
        "prior_true_bottleneck_score": prior_true_score,
        "posterior_true_bottleneck_score": posterior_true_score,
        "prior_weighted_dimension_score": prior_weighted_score,
        "posterior_weighted_dimension_score": posterior_weighted_score,
        "dimension_scores": updated_scores,
        "scorecard_rows": scorecard_rows,
        "evidence_updates": evidence_updates,
        "updated_at": _now_iso(now),
        "source": CHOKEPOINT_SOURCE,
        "deepseek_called": False,
    }


def _anti_thesis_lines(parsed: Mapping[str, Any]) -> list[str]:
    anti = _as_list(parsed.get("anti_thesis")) or _as_list(parsed.get("反向加压与伪证模块"))
    if len(anti) >= 3:
        return [_to_text(item) for item in anti if _to_text(item)]
    fallback = [
        "### 反向加压与伪证模块：CVD 设备交付和良率爬坡周期可能长于资金炒作窗口。",
        "### 反向加压与伪证模块：下游客户认证若失败或延期，半导体散热故事无法转化为订单。",
        "### 反向加压与伪证模块：主力资金可能只是借算力题材拔估值，缺少产能证据时容易高位套现。",
    ]
    return fallback


def build_chokepoint_scan_packet(
    theme: Any,
    raw_llm_response: Any = None,
    evidence_payload: Any = None,
    money_flow_event: Any = None,
    disclosure_event: Any = None,
    ticker: Any = "THEME",
    now: Any = None,
) -> dict:
    parsed_result = parse_chokepoint_deepseek_response(raw_llm_response)
    parsed = _as_mapping(parsed_result.get("payload"))
    candidates = apply_precision_downgrade_to_candidates(parsed.get("candidate_stocks"), evidence_payload=evidence_payload)
    nodes = _as_list(parsed.get("technical_chokepoint_nodes")) or _as_list(parsed.get("technical_nodes"))
    layers = _as_list(parsed.get("supply_chain_layers"))
    score_update = trigger_bayesian_chokepoint_update(
        ticker=ticker or "THEME",
        current_scores=parsed.get("dimension_scores") or parsed.get("scores") or DEFAULT_CHOKEPOINT_PRIOR_SCORES,
        prior_probability=parsed.get("prior_probability"),
        money_flow_event=money_flow_event,
        disclosure_event=disclosure_event,
        data_fetcher_event=evidence_payload if _as_mapping(evidence_payload) else None,
        now=now,
    )

    summary = _to_text(parsed.get("summary"))
    if not summary:
        if nodes:
            first_node = _to_text(_as_mapping(nodes[0]).get("node"), "具体技术节点")
            summary = f"{_to_text(theme, '题材')} 已拆到 {first_node}；候选标的必须继续用公告/财报核验。"
        else:
            summary = f"{_to_text(theme, '题材')} 尚未形成足够具体的技术卡点，禁止按泛概念输出结论。"

    return {
        "theme": _to_text(theme, "待分析科技题材"),
        "summary": summary,
        "specificity_status": _to_text(parsed.get("specificity_status"), "insufficient_specificity" if not nodes else "ok"),
        "cycle_stage": _as_mapping(parsed.get("cycle_stage")),
        "supply_chain_layers": [_as_mapping(item) for item in layers if _as_mapping(item)],
        "technical_chokepoint_nodes": [_as_mapping(item) for item in nodes if _as_mapping(item)],
        "candidate_stocks": candidates,
        "bayesian_update": score_update,
        "scorecard_rows": score_update.get("scorecard_rows", []),
        "anti_thesis": _anti_thesis_lines(parsed),
        "open_checks": _as_list(parsed.get("open_checks"))
        or ["核验公告/财报是否存在半导体级 CVD 产线投资、研发费用、新增设备订单或客户认证。"],
        "parse_status": parsed_result.get("parse_status"),
        "parse_error": parsed_result.get("parse_error"),
        "raw_text": parsed_result.get("raw_text") or "",
        "deepseek_called": bool(raw_llm_response),
        "updated_at": _now_iso(now),
        "source": CHOKEPOINT_SOURCE,
    }


def calculate_jump_diffusion(
    spot_price: Any,
    drift: Any = 0.0,
    volatility: Any = 0.40,
    jump_intensity: Any = 0.50,
    jump_mean: Any = 0.0,
    jump_volatility: Any = 0.25,
    horizon_days: Any = 30,
    trading_days: Any = 252,
) -> dict:
    spot = max(_safe_float(spot_price, 0.0), 0.0)
    mu = _safe_float(drift, 0.0)
    sigma = max(_safe_float(volatility, 0.40), 0.0001)
    lam = max(_safe_float(jump_intensity, 0.50), 0.0)
    jump_mu = _safe_float(jump_mean, 0.0)
    jump_sigma = max(_safe_float(jump_volatility, 0.25), 0.0)
    days = max(_safe_float(horizon_days, 30), 1.0)
    year_days = max(_safe_float(trading_days, 252), 1.0)
    horizon = days / year_days

    jump_expectation = math.exp(jump_mu + 0.5 * jump_sigma * jump_sigma) - 1
    effective_drift = mu + lam * jump_expectation
    expected_terminal_price = spot * math.exp(effective_drift * horizon)
    log_variance = max((sigma * sigma + lam * (jump_sigma * jump_sigma + jump_mu * jump_mu)) * horizon, 0.000001)
    log_std = math.sqrt(log_variance)
    normal = NormalDist()
    median_price = spot * math.exp((mu - 0.5 * sigma * sigma + lam * jump_mu) * horizon)
    p05 = median_price * math.exp(normal.inv_cdf(0.05) * log_std)
    p95 = median_price * math.exp(normal.inv_cdf(0.95) * log_std)

    return {
        "model": "merton_jump_diffusion_placeholder",
        "spot_price": round(spot, 4),
        "horizon_days": int(days),
        "expected_terminal_price": round(expected_terminal_price, 4),
        "median_terminal_price": round(median_price, 4),
        "p05_terminal_price": round(p05, 4),
        "p95_terminal_price": round(p95, 4),
        "effective_drift": round(effective_drift, 6),
        "jump_expectation": round(jump_expectation, 6),
        "model_note": "占位接口：用于突发供货商确认等不连续催化的情景定价，不构成买卖建议。",
    }


def calculate_real_options(
    project_value: Any,
    exercise_cost: Any,
    time_to_expiry_years: Any = 1.0,
    risk_free_rate: Any = 0.02,
    volatility: Any = 0.60,
    dividend_yield: Any = 0.0,
) -> dict:
    value = max(_safe_float(project_value, 0.0), 0.0)
    cost = max(_safe_float(exercise_cost, 0.0), 0.0001)
    tenor = max(_safe_float(time_to_expiry_years, 1.0), 0.0001)
    rate = _safe_float(risk_free_rate, 0.02)
    sigma = max(_safe_float(volatility, 0.60), 0.0001)
    carry = _safe_float(dividend_yield, 0.0)
    normal = NormalDist()

    if value <= 0:
        d1 = -999.0
        d2 = -999.0
        option_value = 0.0
    else:
        d1 = (math.log(value / cost) + (rate - carry + 0.5 * sigma * sigma) * tenor) / (sigma * math.sqrt(tenor))
        d2 = d1 - sigma * math.sqrt(tenor)
        option_value = value * math.exp(-carry * tenor) * normal.cdf(d1) - cost * math.exp(-rate * tenor) * normal.cdf(d2)
    intrinsic_value = max(value - cost, 0.0)

    return {
        "model": "black_scholes_real_option_placeholder",
        "project_value": round(value, 4),
        "exercise_cost": round(cost, 4),
        "time_to_expiry_years": round(tenor, 4),
        "option_value": round(max(option_value, 0.0), 4),
        "intrinsic_value": round(intrinsic_value, 4),
        "d1": round(d1, 6),
        "d2": round(d2, 6),
        "model_note": "占位接口：把未投产实验室技术视为看涨期权，后续可接入公司现金流和产能达产概率。",
    }
