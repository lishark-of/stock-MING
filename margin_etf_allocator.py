from __future__ import annotations

from copy import deepcopy
import datetime


ETF_CATALOG = {
    "宽基ETF": [
        "沪深300 ETF",
        "中证500 ETF",
        "中证1000 ETF",
        "中证A500 ETF",
        "双创50 ETF",
        "科创50 ETF",
    ],
    "科技成长ETF": [
        "半导体 ETF",
        "半导体设备ETF广发",
        "人工智能 ETF",
        "云计算 ETF",
        "高端装备 ETF",
        "电网设备 ETF",
    ],
    "金融券商ETF": [
        "券商ETF",
        "证券ETF",
    ],
    "防守ETF": [
        "红利 ETF",
        "黄金 ETF",
        "黄金股 ETF",
        "低波 ETF",
        "债券 ETF",
    ],
    "商品周期ETF": [
        "有色 ETF",
        "煤炭 ETF",
        "能源 ETF",
        "稀土 ETF",
    ],
}


ETF_BUCKETS = [
    "宽基ETF",
    "科技成长ETF",
    "金融券商ETF",
    "防守ETF",
    "商品周期ETF",
]


HIGH_BETA_BUCKETS = {"科技成长ETF", "金融券商ETF"}


MARKET_STATE_CONFIG = {
    "弱势": {
        "market_score": 25,
        "trend_score": 20,
        "money_score": 25,
        "volatility_score": 75,
        "margin_range": (0, 5),
        "cash_range": (30, 45),
        "weights": {
            "宽基ETF": 0.22,
            "科技成长ETF": 0.05,
            "金融券商ETF": 0.03,
            "防守ETF": 0.50,
            "商品周期ETF": 0.04,
            "现金": 0.16,
        },
        "risk_level": "高风险防守",
        "tilt": "偏防守",
    },
    "震荡": {
        "market_score": 50,
        "trend_score": 45,
        "money_score": 50,
        "volatility_score": 55,
        "margin_range": (0, 15),
        "cash_range": (20, 30),
        "weights": {
            "宽基ETF": 0.34,
            "科技成长ETF": 0.16,
            "金融券商ETF": 0.08,
            "防守ETF": 0.24,
            "商品周期ETF": 0.06,
            "现金": 0.12,
        },
        "risk_level": "均衡防守",
        "tilt": "宽基 + 防守",
    },
    "强趋势": {
        "market_score": 72,
        "trend_score": 75,
        "money_score": 70,
        "volatility_score": 40,
        "margin_range": (10, 25),
        "cash_range": (10, 20),
        "weights": {
            "宽基ETF": 0.30,
            "科技成长ETF": 0.26,
            "金融券商ETF": 0.10,
            "防守ETF": 0.14,
            "商品周期ETF": 0.12,
            "现金": 0.08,
        },
        "risk_level": "进攻可控",
        "tilt": "宽基 + 科技成长",
    },
    "极强趋势": {
        "market_score": 86,
        "trend_score": 88,
        "money_score": 84,
        "volatility_score": 35,
        "margin_range": (20, 35),
        "cash_range": (10, 15),
        "weights": {
            "宽基ETF": 0.24,
            "科技成长ETF": 0.30,
            "金融券商ETF": 0.12,
            "防守ETF": 0.08,
            "商品周期ETF": 0.16,
            "现金": 0.10,
        },
        "risk_level": "高弹性高风险",
        "tilt": "科技成长主导",
    },
}


STYLE_ADJUSTMENTS = {
    "防守": {
        "market_score": -6,
        "cash_shift": 10,
        "margin_shift": -8,
        "weight_shift": {
            "科技成长ETF": -0.08,
            "金融券商ETF": -0.03,
            "商品周期ETF": -0.03,
            "防守ETF": 0.09,
            "宽基ETF": 0.05,
        },
    },
    "平衡": {
        "market_score": 0,
        "cash_shift": 0,
        "margin_shift": 0,
        "weight_shift": {},
    },
    "进攻": {
        "market_score": 6,
        "cash_shift": -5,
        "margin_shift": 5,
        "weight_shift": {
            "科技成长ETF": 0.07,
            "金融券商ETF": 0.03,
            "商品周期ETF": 0.04,
            "防守ETF": -0.09,
            "宽基ETF": -0.03,
        },
    },
}


LEVERAGE_MODE_CAP = {
    "不使用": 0,
    "小幅使用": 10,
    "中等使用": 25,
    "火力全开，但默认关闭": 50,
}


def _num(value, default=0.0):
    try:
        if value in [None, ""]:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _clamp(value, low, high):
    return max(low, min(high, value))


def _round2(value):
    return round(float(value), 2)


def _safe_round(value, default=0.0):
    try:
        if value in [None, ""]:
            return default
        return round(float(value), 2)
    except Exception:
        return default


def _dedupe_strings(items):
    seen = set()
    result = []
    for item in items or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _normalize_score_rows(etf_scores):
    if not etf_scores:
        return []
    if isinstance(etf_scores, dict):
        rows = etf_scores.get("rows") or etf_scores.get("etf_score_table") or []
        return rows if isinstance(rows, list) else []
    if isinstance(etf_scores, list):
        return etf_scores
    return []


def _normalize_bucket_weights(weights):
    weights = dict(weights or {})
    cash_weight = max(weights.get("现金", 0.0), 0.05)
    investable = {key: max(float(weights.get(key, 0.0)), 0.0) for key in ETF_BUCKETS}
    investable_total = sum(investable.values())
    target_total = max(1.0 - cash_weight, 0.0)
    if investable_total <= 0:
        base = target_total / max(len(ETF_BUCKETS), 1)
        investable = {key: base for key in ETF_BUCKETS}
    else:
        scale = target_total / investable_total if investable_total else 1.0
        investable = {key: value * scale for key, value in investable.items()}
    normalized = {**investable, "现金": cash_weight}
    return normalized


def _candidate_rows_for_bucket(rows, bucket):
    candidates = [item for item in rows if item.get("bucket") == bucket]
    candidates.sort(
        key=lambda item: (
            item.get("manual_focus", False),
            item.get("total_score") or 0,
            item.get("return_20d_pct") or -999,
            item.get("amount_ma20") or 0,
        ),
        reverse=True,
    )
    return candidates


def _bucket_statistics(etf_rows):
    stats = {}
    for bucket in ETF_BUCKETS:
        rows = _candidate_rows_for_bucket(etf_rows, bucket)
        valid_scores = [float(item.get("total_score") or 0) for item in rows if item.get("state") != "数据不足"]
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
        overheat_count = sum(1 for item in rows if item.get("state") == "过热等待")
        weak_count = sum(1 for item in rows if item.get("state") in {"破位回避", "震荡观察"})
        avg_vol = (
            sum(float(item.get("volatility_20d") or 0) for item in rows if item.get("volatility_20d") is not None) / len(rows)
            if rows
            else 0.0
        )
        avg_return20 = (
            sum(float(item.get("return_20d_pct") or 0) for item in rows if item.get("return_20d_pct") is not None) / len(rows)
            if rows
            else 0.0
        )
        stats[bucket] = {
            "avg_score": avg_score,
            "count": len(rows),
            "overheat_count": overheat_count,
            "weak_count": weak_count,
            "avg_volatility": avg_vol,
            "avg_return_20d": avg_return20,
        }
    return stats


def _apply_etf_score_adjustments(weights, target_margin, target_cash, etf_rows):
    reasons = []
    overweight = []
    underweight = []
    bucket_stats = _bucket_statistics(etf_rows)

    tech_score = bucket_stats["科技成长ETF"]["avg_score"]
    broker_score = bucket_stats["金融券商ETF"]["avg_score"]
    broad_score = bucket_stats["宽基ETF"]["avg_score"]
    defense_score = bucket_stats["防守ETF"]["avg_score"]
    cycle_score = bucket_stats["商品周期ETF"]["avg_score"]
    high_beta_score = (tech_score + broker_score) / 2
    overall_score = sum(item["avg_score"] for item in bucket_stats.values()) / max(len(bucket_stats), 1)
    avg_volatility = sum(item["avg_volatility"] for item in bucket_stats.values()) / max(len(bucket_stats), 1)

    if tech_score >= broad_score + 8 and tech_score >= 65:
        shift = 0.07 if tech_score >= broad_score + 15 else 0.04
        weights["科技成长ETF"] += shift
        weights["宽基ETF"] = max(weights["宽基ETF"] - shift * 0.5, 0.05)
        weights["现金"] = max(weights["现金"] - shift * 0.5, 0.05)
        reasons.append("科技成长 ETF 平均分明显高于宽基，今日提高科技成长权重。")
        overweight.append("科技成长ETF")
        underweight.append("宽基ETF")

    if broker_score >= broad_score + 6 and broker_score >= 62:
        shift = 0.05 if broker_score >= broad_score + 12 else 0.03
        weights["金融券商ETF"] += shift
        weights["宽基ETF"] = max(weights["宽基ETF"] - shift * 0.45, 0.05)
        weights["现金"] = max(weights["现金"] - shift * 0.55, 0.05)
        reasons.append("金融券商 ETF 强于宽基，允许提高同类配置权重，但不单独放宽融资比例。")
        overweight.append("金融券商ETF")
        underweight.append("宽基ETF")

    if defense_score >= high_beta_score + 8 and defense_score >= 62:
        shift = 0.08 if defense_score >= high_beta_score + 15 else 0.05
        weights["防守ETF"] += shift
        weights["科技成长ETF"] = max(weights["科技成长ETF"] - shift * 0.35, 0.03)
        weights["金融券商ETF"] = max(weights["金融券商ETF"] - shift * 0.25, 0.02)
        weights["商品周期ETF"] = max(weights["商品周期ETF"] - shift * 0.15, 0.02)
        target_margin = max(target_margin - 5, 0)
        target_cash = min(target_cash + 5, 60)
        reasons.append("防守 ETF 强于进攻 ETF，今日提高防守权重并压低融资比例。")
        overweight.append("防守ETF")
        underweight.extend(["科技成长ETF", "金融券商ETF"])

    if overall_score and overall_score < 55:
        target_margin = max(target_margin - 5, 0)
        target_cash = min(target_cash + 8, 60)
        weights["现金"] += 0.06
        weights["防守ETF"] += 0.03
        weights["科技成长ETF"] = max(weights["科技成长ETF"] - 0.04, 0.03)
        weights["金融券商ETF"] = max(weights["金融券商ETF"] - 0.02, 0.02)
        reasons.append("全市场 ETF 趋势偏弱，今日提高现金缓冲并压低融资。")
        overweight.append("现金")
        underweight.extend(["科技成长ETF", "金融券商ETF"])

    if bucket_stats["科技成长ETF"]["overheat_count"] > 0 or bucket_stats["金融券商ETF"]["overheat_count"] > 0:
        weights["科技成长ETF"] = max(weights["科技成长ETF"] - 0.03, 0.03)
        weights["金融券商ETF"] = max(weights["金融券商ETF"] - 0.02, 0.02)
        weights["宽基ETF"] += 0.02
        weights["现金"] += 0.03
        reasons.append("高 beta ETF 中存在过热品种，降低追高比例，等待回踩 MA20 或量能确认。")

    if cycle_score >= 65 and defense_score < 60:
        weights["商品周期ETF"] += 0.03
        weights["宽基ETF"] = max(weights["宽基ETF"] - 0.02, 0.05)
        reasons.append("商品周期 ETF 评分回升，允许保留小幅周期弹性。")
        overweight.append("商品周期ETF")

    if avg_volatility >= 28 or high_beta_score >= 72 and (bucket_stats["科技成长ETF"]["avg_volatility"] > 24 or bucket_stats["金融券商ETF"]["avg_volatility"] > 24):
        target_margin = max(target_margin - 5, 0)
        target_cash = min(target_cash + 3, 60)
        reasons.append("高 beta / 高波动 ETF 占优时，融资比例按波动约束下调。")

    high_beta_weight = weights.get("科技成长ETF", 0.0) + weights.get("金融券商ETF", 0.0)
    if high_beta_weight > 0.42:
        excess = high_beta_weight - 0.42
        weights["科技成长ETF"] = max(weights["科技成长ETF"] - excess * 0.6, 0.03)
        weights["金融券商ETF"] = max(weights["金融券商ETF"] - excess * 0.4, 0.02)
        weights["宽基ETF"] += excess * 0.45
        weights["现金"] += excess * 0.55
        reasons.append("同属高 beta 的科技成长与金融券商不能无限叠加，已自动限制合计权重。")

    weights["现金"] = max(weights.get("现金", 0.0) + (target_cash / 100.0 - weights.get("现金", 0.0)), 0.05)
    dynamic_weights = _normalize_bucket_weights(weights)
    if not reasons:
        reasons.append("ETF 强弱分布未触发明显偏离，维持基础 bucket 结构。")
    overweight = list(dict.fromkeys(overweight))
    underweight = [item for item in list(dict.fromkeys(underweight)) if item not in overweight]
    return dynamic_weights, target_margin, target_cash, reasons, overweight, underweight, bucket_stats


def get_margin_etf_catalog():
    return deepcopy(ETF_CATALOG)


def calculate_margin_etf_allocation(account, market_state, risk_profile, etf_scores=None):
    account = account or {}
    risk_profile = risk_profile or {}
    market_state = market_state if market_state in MARKET_STATE_CONFIG else "震荡"
    style = risk_profile.get("style") if risk_profile.get("style") in STYLE_ADJUSTMENTS else "平衡"
    leverage_mode = risk_profile.get("leverage_mode") if risk_profile.get("leverage_mode") in LEVERAGE_MODE_CAP else "不使用"

    raw_available_margin = account.get("available_margin")
    raw_maintenance_ratio = account.get("maintenance_ratio")
    raw_margin_interest_rate = account.get("margin_interest_rate")
    has_available_margin_input = raw_available_margin not in [None, ""] and _num(raw_available_margin, 0.0) > 0
    has_maintenance_ratio_input = raw_maintenance_ratio not in [None, ""] and _num(raw_maintenance_ratio, 0.0) > 0

    total_asset = max(_num(account.get("total_asset")), 0.0)
    cash_balance = max(_num(account.get("cash_balance")), 0.0)
    stock_market_value = max(_num(account.get("stock_market_value")), 0.0)
    etf_market_value = max(_num(account.get("etf_market_value")), 0.0)
    margin_debt = max(_num(account.get("margin_debt")), 0.0)
    available_margin = max(_num(raw_available_margin), 0.0)
    maintenance_ratio = _num(raw_maintenance_ratio, 0.0)
    margin_interest_rate = _num(raw_margin_interest_rate, 6.8)
    max_drawdown_pct = max(_num(account.get("max_drawdown_pct"), 15.0), 1.0)
    score_rows = _normalize_score_rows(etf_scores)
    score_packet = etf_scores if isinstance(etf_scores, dict) else {"rows": score_rows}
    data_date = score_packet.get("data_date") or ""
    score_source = score_packet.get("data_source") or ("tushare" if score_rows else "rules_only")

    position_assets = stock_market_value + etf_market_value
    gross_assets = max(total_asset, cash_balance + position_assets, margin_debt)
    net_asset = max(gross_assets - margin_debt, 0.0)
    current_leverage_ratio = (position_assets / net_asset) if net_asset > 0 else 0.0
    current_margin_debt_ratio = (margin_debt / net_asset * 100) if net_asset > 0 else 0.0
    cash_buffer_ratio = (cash_balance / net_asset * 100) if net_asset > 0 else 0.0
    stock_position_ratio = (stock_market_value / net_asset * 100) if net_asset > 0 else 0.0
    etf_position_ratio = (etf_market_value / net_asset * 100) if net_asset > 0 else 0.0

    state_config = deepcopy(MARKET_STATE_CONFIG[market_state])
    style_adjust = STYLE_ADJUSTMENTS[style]
    leverage_cap = LEVERAGE_MODE_CAP[leverage_mode]

    min_margin, max_margin = state_config["margin_range"]
    min_cash, max_cash = state_config["cash_range"]
    target_margin = _clamp((min_margin + max_margin) / 2 + style_adjust["margin_shift"], 0, 50)
    target_cash = _clamp((min_cash + max_cash) / 2 + style_adjust["cash_shift"], 5, 60)

    if leverage_mode == "不使用":
        target_margin = 0.0
    else:
        target_margin = min(target_margin, leverage_cap)

    if max_drawdown_pct < 10:
        target_margin = min(target_margin, 10.0)
    elif max_drawdown_pct < 15:
        target_margin = min(target_margin, 15.0)

    if market_state == "弱势":
        target_margin = min(target_margin, 5.0)
    if market_state == "震荡" and leverage_mode == "火力全开，但默认关闭":
        target_margin = min(target_margin, 20.0)
    if market_state != "极强趋势" and leverage_cap > 35:
        target_margin = min(target_margin, 35.0)

    risk_flags = []
    notes = []
    trigger_conditions = []
    invalid_conditions = []
    need_deleverage = False
    only_rebalance = False

    if net_asset <= 0:
        target_margin = 0.0
        need_deleverage = True
        risk_flags.append("净资产不可用，无法承受新增融资。")

    if current_margin_debt_ratio > 40:
        target_margin = min(target_margin, max(current_margin_debt_ratio - 10, 0))
        need_deleverage = True
        risk_flags.append("当前融资负债 / 净资产已超过 40%。")

    if maintenance_ratio and maintenance_ratio < 180:
        target_margin = 0.0
        need_deleverage = True
        risk_flags.append("当前维持担保比例低于 180%。")

    if max_drawdown_pct < 10 and current_margin_debt_ratio > 10:
        need_deleverage = True
        risk_flags.append("账户可承受回撤低于 10%，融资应压到 10% 以内。")

    if market_state == "弱势" and style == "进攻":
        target_margin = 0.0
        only_rebalance = True
        risk_flags.append("弱势阶段不允许进攻型融资。")

    if stock_position_ratio >= 68:
        only_rebalance = True
        notes.append("当前股票仓位过高，优先 ETF 替换，不新增杠杆。")
        if current_margin_debt_ratio >= target_margin:
            target_margin = min(target_margin, current_margin_debt_ratio)
    elif stock_position_ratio >= 55:
        notes.append("当前股票仓位偏高，优先 ETF 替换，不直接堆加杠杆。")
        if style in {"防守", "平衡"}:
            only_rebalance = True
        elif current_margin_debt_ratio >= target_margin or cash_buffer_ratio < target_cash:
            only_rebalance = True

    if raw_available_margin not in [None, ""] and available_margin <= 0:
        target_margin = min(target_margin, current_margin_debt_ratio)
        notes.append("可用保证金不足，默认不新增融资。")

    if leverage_mode == "不使用":
        invalid_conditions.append("用户设置为不使用融资。")
        if current_margin_debt_ratio > 0:
            need_deleverage = True
            risk_flags.append("账户已有融资负债，但当前模式设置为不使用融资。")
    if not has_maintenance_ratio_input:
        notes.append("维持担保比例未填写，系统按保守约束估算。")
    if not has_available_margin_input:
        notes.append("可用保证金未填写或为 0，融资空间按保守方式处理。")

    weights = deepcopy(state_config["weights"])
    for key, shift in style_adjust["weight_shift"].items():
        weights[key] = max(weights.get(key, 0) + shift, 0.0)
    weights["现金"] = max(weights.get("现金", 0) + (target_cash / 100.0 - weights.get("现金", 0)), 0.05)

    dynamic_reasons = []
    overweight_buckets = []
    underweight_buckets = []
    bucket_score_stats = {}
    if score_rows:
        weights, target_margin, target_cash, dynamic_reasons, overweight_buckets, underweight_buckets, bucket_score_stats = _apply_etf_score_adjustments(
            weights,
            target_margin,
            target_cash,
            score_rows,
        )
        if data_date:
            notes.append(f"已接入 Tushare ETF 数据，评分日期 {data_date}。")
    else:
        weights = _normalize_bucket_weights(weights)
        dynamic_reasons.append("暂无 ETF 强弱评分，当前按基础规则模板测算。")

    high_beta_strength = (
        bucket_score_stats.get("科技成长ETF", {}).get("avg_score", 0)
        + bucket_score_stats.get("金融券商ETF", {}).get("avg_score", 0)
    ) / 2 if bucket_score_stats else 0
    defensive_strength = bucket_score_stats.get("防守ETF", {}).get("avg_score", 0) if bucket_score_stats else 0
    overheat_rows = [
        item for item in score_rows
        if item.get("state") == "过热等待" and item.get("bucket") in HIGH_BETA_BUCKETS
    ]
    overheat_names = [item.get("etf_name") or item.get("etf_code") for item in overheat_rows if item.get("etf_name") or item.get("etf_code")]
    if high_beta_strength >= 70:
        notes.append("高 beta ETF 整体偏强时，只提高内部配置权重，不自动突破账户融资硬约束。")
    if defensive_strength >= high_beta_strength + 6 and score_rows:
        notes.append("防守 ETF 强、进攻 ETF 弱时，模型会优先降低融资比例。")
    if overheat_names:
        notes.append("高 beta ETF 存在过热，进攻节奏应等回踩或量能二次确认。")

    investable_weight_total = sum(value for key, value in weights.items() if key != "现金")
    if investable_weight_total <= 0:
        investable_weight_total = 1.0

    recommended_total_exposure_ratio = _clamp(100 - target_cash + target_margin, 0, 150)
    recommended_total_exposure = net_asset * recommended_total_exposure_ratio / 100
    recommended_cash_amount = net_asset * target_cash / 100
    recommended_margin_amount = net_asset * target_margin / 100

    base_stock_reserve_ratio = min(stock_position_ratio, recommended_total_exposure_ratio)
    recommended_etf_capacity_ratio = max(recommended_total_exposure_ratio - base_stock_reserve_ratio, 0.0)
    recommended_etf_capacity_amount = net_asset * recommended_etf_capacity_ratio / 100

    if stock_position_ratio > recommended_total_exposure_ratio:
        only_rebalance = True
        notes.append("当前股票仓位已高于建议总仓位，新增 ETF 需要以替换为主。")

    recommended_allocation = {}
    for category in ETF_BUCKETS:
        normalized_weight = weights.get(category, 0.0) / investable_weight_total
        ratio_to_net_asset = recommended_etf_capacity_ratio * normalized_weight
        recommended_allocation[category] = {
            "ratio_pct": _round2(ratio_to_net_asset),
            "amount": _round2(net_asset * ratio_to_net_asset / 100),
            "candidate_etfs": ETF_CATALOG.get(category, []),
            "weight_in_etf_bucket_pct": _round2(normalized_weight * 100),
        }
    recommended_allocation["现金"] = {
        "ratio_pct": _round2(target_cash),
        "amount": _round2(recommended_cash_amount),
        "candidate_etfs": [],
        "weight_in_etf_bucket_pct": 0.0,
    }

    dynamic_bucket_weights = {key: _round2(value * 100) for key, value in weights.items()}

    account_risk_score = 100 - _clamp(current_margin_debt_ratio * 1.4 + max(stock_position_ratio - 50, 0) * 0.6, 0, 100)
    margin_pressure_score = (
        _clamp(100 - current_margin_debt_ratio * 2 - max(180 - maintenance_ratio, 0) * 1.5, 0, 100)
        if maintenance_ratio
        else _clamp(100 - current_margin_debt_ratio * 2, 0, 100)
    )
    risk_budget_score = _round2(
        (
            state_config["market_score"]
            + state_config["trend_score"]
            + state_config["money_score"]
            + (100 - state_config["volatility_score"])
            + account_risk_score
            + margin_pressure_score
            + style_adjust["market_score"]
        ) / 6
    )

    maintenance_safe = maintenance_ratio >= 230 if has_maintenance_ratio_input else False
    margin_headroom = max(target_margin - current_margin_debt_ratio, 0.0)
    cash_ready = cash_buffer_ratio >= max(target_cash - 2, 8)
    strong_market = market_state in {"强趋势", "极强趋势"}
    defensive_dominant = bool(score_rows and defensive_strength >= high_beta_strength + 6)

    if need_deleverage:
        action_state = "融资过高，优先降杠杆"
    elif leverage_mode == "不使用":
        action_state = "暂停融资，保留现金"
    elif only_rebalance:
        action_state = "只允许调仓，不新增杠杆"
    elif market_state == "弱势":
        action_state = "暂停融资，保留现金"
    elif style == "防守":
        action_state = "可用现金进攻，暂不加融资" if strong_market and cash_ready and not defensive_dominant else "暂停融资，保留现金"
    elif strong_market and cash_ready and current_margin_debt_ratio >= max(target_margin - 1.5, 0):
        action_state = "可用现金进攻，暂不加融资"
    elif strong_market and maintenance_safe and margin_headroom >= 4:
        if overheat_names:
            action_state = "可小幅融资进攻"
        elif style == "进攻" and leverage_mode == "火力全开，但默认关闭" and margin_headroom >= 8 and target_margin >= 18:
            action_state = "可中等融资进攻"
        else:
            action_state = "可小幅融资进攻"
    elif strong_market and cash_ready:
        action_state = "可用现金进攻，暂不加融资"
    else:
        action_state = "暂停融资，保留现金"

    if defensive_dominant and action_state in {"可小幅融资进攻", "可中等融资进攻"}:
        action_state = "可用现金进攻，暂不加融资"
    if overheat_names and action_state == "可中等融资进攻":
        action_state = "可小幅融资进攻"

    if need_deleverage:
        notes.append("当前先处理风险暴露，再谈进攻节奏。")
    elif action_state == "可用现金进攻，暂不加融资":
        notes.append("当前更适合先用现金执行，再观察是否需要动用融资额度。")
    elif action_state == "可小幅融资进攻":
        notes.append("允许分步小幅融资进攻，但不能一次性加满。")
    elif action_state == "可中等融资进攻":
        notes.append("允许中等融资进攻，但仍需保留强制撤退线和现金缓冲。")

    risk_lines = [
        "同赛道 ETF 可能高度重叠，不应简单叠加配置。",
        "ETF 持仓会随季报/公告变化，Tushare 持仓数据可能有滞后，配置结论必须结合最新行情和风险线。",
        "维持担保比例接近 180% 或自设红线时，停止新增融资并优先降杠杆。",
        "ETF 跌破 MA20：停止加融资，只允许观察或调仓。",
        "ETF 跌破 MA60：降低融资，优先回收现金缓冲。",
        f"账户净值回撤达到 {max_drawdown_pct:.0f}% 附近时，触发降融资或缩减总仓位。",
    ]
    trigger_conditions.extend(
        [
            f"{market_state} 阶段优先执行“{state_config['tilt']}”配置。",
            f"建议现金缓冲维持在 {target_cash:.0f}% 左右，不把现金打满。",
            f"融资年利率按 {margin_interest_rate:.2f}% 估算时，只有在趋势延续时才考虑放大仓位。",
        ]
    )
    invalid_conditions.extend(
        [
            "禁止输出绝对化、高杠杆、保证收益类表述。",
            "没有新增胜率验证前，不把单一行业 ETF 当作唯一仓位。",
            "同赛道 ETF 高度重叠时，不应简单叠加配置。",
        ]
    )
    if score_rows:
        trigger_conditions.append("ETF 主评分使用 Tushare 日线，不把盘中实时快照直接覆盖日线结论。")
        invalid_conditions.append("ETF 过热时不追高，等待回踩 MA20 或成交额二次确认。")

    if current_margin_debt_ratio > target_margin + 5:
        notes.append("当前融资比例已高于建议值，优先降杠杆后再谈轮动。")
        if current_margin_debt_ratio > target_margin + 8:
            need_deleverage = True
    elif current_margin_debt_ratio < target_margin and not need_deleverage and not only_rebalance and leverage_mode != "不使用":
        notes.append("融资空间尚有余量，但只适合分步执行，不宜一次性加满。")

    if action_state in {"可小幅融资进攻", "可中等融资进攻"} and overheat_names:
        notes.append("进攻方向虽强，但应等待回踩后再执行，不把强势直接等同于追高。")

    if need_deleverage or market_state == "弱势" or defensive_dominant:
        style_tilt = "偏防守"
    elif strong_market and (style == "进攻" or high_beta_strength >= max(defensive_strength + 4, 68)):
        style_tilt = "偏进攻"
    else:
        style_tilt = "平衡"

    execution_reasons = [
        f"市场处于 {market_state}，账户风格为 {style}，融资模式为 {leverage_mode}。",
        f"当前融资比例 {current_margin_debt_ratio:.2f}% ，建议上限 {target_margin:.2f}%。",
        (
            f"维持担保比例 {maintenance_ratio:.0f}% ，安全边际较充足。"
            if has_maintenance_ratio_input
            else "维持担保比例未填写，结果已按保守约束估算。"
        ),
        (
            f"当前现金缓冲 {cash_buffer_ratio:.2f}% ，建议现金比例 {target_cash:.2f}%。"
            if cash_balance > 0 or net_asset > 0
            else "当前现金缓冲不足，先保留流动性。"
        ),
    ]
    if stock_position_ratio >= 55:
        execution_reasons.append("股票仓位偏高，ETF 操作以替换和结构优化优先。")
    if defensive_dominant:
        execution_reasons.append("防守 ETF 强于成长方向，融资节奏需要压低。")
    if overheat_names:
        execution_reasons.append(f"过热方向包括 {' / '.join(overheat_names[:3])}，不适合直接追高。")
    if margin_headroom >= 4 and strong_market and maintenance_safe:
        execution_reasons.append("担保比例和融资空间仍有余量，可以按风格分步执行。")
    execution_reasons = _dedupe_strings(execution_reasons)

    must_reduce_risk_conditions = _dedupe_strings(
        [
            "维持担保比例接近 180% 或低于自设红线。",
            "主攻 ETF 连续跌破 MA20 或直接跌破 MA60。",
            f"账户净值回撤接近 {max_drawdown_pct:.0f}% 上限。",
        ]
    )
    no_chase_warning = (
        f"不追高：{' / '.join(overheat_names[:4])} 当前过热，等待回踩或量能二次确认。"
        if overheat_names
        else ""
    )
    attack_budget_upper_ratio = _round2(target_margin)
    if action_state == "可中等融资进攻":
        attack_budget_upper_ratio = _round2(min(target_margin, current_margin_debt_ratio + 10))
    elif action_state == "可小幅融资进攻":
        attack_budget_upper_ratio = _round2(min(target_margin, max(current_margin_debt_ratio + 5, target_margin)))
    elif action_state == "可用现金进攻，暂不加融资":
        attack_budget_upper_ratio = _round2(current_margin_debt_ratio)

    selected_candidates = {}
    for category in ETF_BUCKETS:
        ranked = _candidate_rows_for_bucket(score_rows, category)
        selected_candidates[category] = [
            {
                "etf_code": item.get("etf_code"),
                "etf_name": item.get("etf_name"),
                "state": item.get("state"),
                "total_score": _safe_round(item.get("total_score")),
                "return_20d_pct": _safe_round(item.get("return_20d_pct")),
                "theme": item.get("theme"),
                "sub_theme": item.get("sub_theme"),
                "manager": item.get("manager"),
                "benchmark": item.get("benchmark"),
            }
            for item in ranked[:3]
        ]

    previous_change_message = "暂无上一交易日配置，后续可接入历史配置对比。"

    return {
        "account_state": {
            "gross_assets": _round2(gross_assets),
            "net_asset": _round2(net_asset),
            "cash_balance": _round2(cash_balance),
            "stock_market_value": _round2(stock_market_value),
            "etf_market_value": _round2(etf_market_value),
            "margin_debt": _round2(margin_debt),
            "cash_buffer_ratio": _round2(cash_buffer_ratio),
            "stock_position_ratio": _round2(stock_position_ratio),
            "etf_position_ratio": _round2(etf_position_ratio),
        },
        "market_state": market_state,
        "style": style,
        "leverage_mode": leverage_mode,
        "net_asset": _round2(net_asset),
        "gross_exposure": _round2(position_assets),
        "current_leverage_ratio": _round2(current_leverage_ratio),
        "current_margin_debt_ratio": _round2(current_margin_debt_ratio),
        "recommended_margin_ratio": _round2(target_margin),
        "recommended_margin_amount": _round2(recommended_margin_amount),
        "recommended_total_exposure": _round2(recommended_total_exposure),
        "recommended_total_exposure_ratio": _round2(recommended_total_exposure_ratio),
        "recommended_cash_ratio": _round2(target_cash),
        "recommended_cash_amount": _round2(recommended_cash_amount),
        "recommended_etf_capacity_amount": _round2(recommended_etf_capacity_amount),
        "recommended_etf_capacity_ratio": _round2(recommended_etf_capacity_ratio),
        "recommended_etf_allocation": recommended_allocation,
        "dynamic_bucket_weights": dynamic_bucket_weights,
        "risk_level": state_config["risk_level"],
        "style_tilt": style_tilt,
        "action_state": action_state,
        "allow_margin_add": action_state in {"可小幅融资进攻", "可中等融资进攻"},
        "only_rebalance": bool(only_rebalance),
        "need_deleverage": bool(need_deleverage),
        "risk_budget_score": risk_budget_score,
        "scores": {
            "market_score": state_config["market_score"],
            "trend_score": state_config["trend_score"],
            "money_score": state_config["money_score"],
            "volatility_score": state_config["volatility_score"],
            "account_risk_score": _round2(account_risk_score),
            "margin_pressure_score": _round2(margin_pressure_score),
        },
        "risk_lines": risk_lines,
        "trigger_conditions": trigger_conditions,
        "invalid_conditions": invalid_conditions,
        "notes": notes,
        "risk_flags": risk_flags,
        "execution_reasons": execution_reasons[:3],
        "no_chase_warning": no_chase_warning,
        "must_reduce_risk_conditions": must_reduce_risk_conditions,
        "attack_budget_upper_ratio": attack_budget_upper_ratio,
        "watch_not_chase_etfs": overheat_names[:6],
        "input_snapshot": {
            "available_margin": _round2(available_margin),
            "maintenance_ratio": _round2(maintenance_ratio),
            "margin_interest_rate": _round2(margin_interest_rate),
            "available_margin_provided": bool(has_available_margin_input),
            "maintenance_ratio_provided": bool(has_maintenance_ratio_input),
        },
        "etf_score_table": score_rows,
        "selected_etf_candidates": selected_candidates,
        "overweight_buckets": overweight_buckets,
        "underweight_buckets": underweight_buckets,
        "daily_adjustment_reason": dynamic_reasons,
        "bucket_score_stats": bucket_score_stats,
        "data_date": data_date or datetime.date.today().strftime("%Y%m%d"),
        "data_source": score_source,
        "latest_market_update": data_date or "",
        "previous_day_change_text": previous_change_message,
    }
