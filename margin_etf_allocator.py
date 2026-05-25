from __future__ import annotations

from copy import deepcopy


ETF_CATALOG = {
    "宽基ETF": [
        "沪深300 ETF",
        "中证500 ETF",
        "中证1000 ETF",
        "中证A500 ETF",
        "双创50 ETF",
    ],
    "科技成长ETF": [
        "科创50 ETF",
        "半导体 ETF",
        "人工智能 ETF",
        "云计算 ETF",
        "高端装备 ETF",
        "电网设备 ETF",
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
    ],
}


MARKET_STATE_CONFIG = {
    "弱势": {
        "market_score": 25,
        "trend_score": 20,
        "money_score": 25,
        "volatility_score": 75,
        "margin_range": (0, 5),
        "cash_range": (30, 45),
        "weights": {
            "宽基ETF": 0.24,
            "科技成长ETF": 0.06,
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
            "宽基ETF": 0.38,
            "科技成长ETF": 0.18,
            "防守ETF": 0.26,
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
            "宽基ETF": 0.34,
            "科技成长ETF": 0.34,
            "防守ETF": 0.14,
            "商品周期ETF": 0.10,
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
            "宽基ETF": 0.28,
            "科技成长ETF": 0.42,
            "防守ETF": 0.08,
            "商品周期ETF": 0.12,
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
            "科技成长ETF": -0.10,
            "商品周期ETF": -0.03,
            "防守ETF": 0.09,
            "宽基ETF": 0.04,
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
            "科技成长ETF": 0.09,
            "商品周期ETF": 0.04,
            "防守ETF": -0.09,
            "宽基ETF": -0.02,
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


def get_margin_etf_catalog():
    return deepcopy(ETF_CATALOG)


def calculate_margin_etf_allocation(account, market_state, risk_profile):
    account = account or {}
    risk_profile = risk_profile or {}
    market_state = market_state if market_state in MARKET_STATE_CONFIG else "震荡"
    style = risk_profile.get("style") if risk_profile.get("style") in STYLE_ADJUSTMENTS else "平衡"
    leverage_mode = risk_profile.get("leverage_mode") if risk_profile.get("leverage_mode") in LEVERAGE_MODE_CAP else "不使用"

    total_asset = max(_num(account.get("total_asset")), 0.0)
    cash_balance = max(_num(account.get("cash_balance")), 0.0)
    stock_market_value = max(_num(account.get("stock_market_value")), 0.0)
    etf_market_value = max(_num(account.get("etf_market_value")), 0.0)
    margin_debt = max(_num(account.get("margin_debt")), 0.0)
    available_margin = max(_num(account.get("available_margin")), 0.0)
    maintenance_ratio = _num(account.get("maintenance_ratio"), 0.0)
    margin_interest_rate = _num(account.get("margin_interest_rate"), 6.8)
    max_drawdown_pct = max(_num(account.get("max_drawdown_pct"), 15.0), 1.0)

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

    if stock_position_ratio >= 55:
        only_rebalance = True
        notes.append("当前股票仓位较高，优先 ETF 替换，不新增明显杠杆。")
        if current_margin_debt_ratio >= target_margin:
            target_margin = min(target_margin, current_margin_debt_ratio)

    if available_margin and available_margin <= 0:
        target_margin = min(target_margin, current_margin_debt_ratio)
        notes.append("可用保证金不足，默认不新增融资。")

    if leverage_mode == "不使用":
        invalid_conditions.append("用户设置为不使用融资。")
        if current_margin_debt_ratio > 0:
            need_deleverage = True
            risk_flags.append("账户已有融资负债，但当前模式设置为不使用融资。")
    if maintenance_ratio == 0:
        notes.append("维持担保比例未填写，系统按保守约束估算。")
    if available_margin == 0:
        notes.append("可用保证金未填写或为 0，融资空间按保守方式处理。")

    weights = deepcopy(state_config["weights"])
    for key, shift in style_adjust["weight_shift"].items():
        weights[key] = max(weights.get(key, 0) + shift, 0.0)
    weights["现金"] = max(weights.get("现金", 0) + (target_cash / 100.0 - weights.get("现金", 0)), 0.05)

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
    for category in ["宽基ETF", "科技成长ETF", "防守ETF", "商品周期ETF"]:
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

    account_risk_score = 100 - _clamp(current_margin_debt_ratio * 1.4 + max(stock_position_ratio - 50, 0) * 0.6, 0, 100)
    margin_pressure_score = _clamp(100 - current_margin_debt_ratio * 2 - max(180 - maintenance_ratio, 0) * 1.5, 0, 100) if maintenance_ratio else _clamp(100 - current_margin_debt_ratio * 2, 0, 100)
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

    if need_deleverage:
        action_state = "融资过高，建议降杠杆" if current_margin_debt_ratio > 0 else "禁止加融资"
    elif only_rebalance or leverage_mode == "不使用":
        action_state = "只允许调仓" if stock_position_ratio > 0 else "禁止加融资"
    elif target_margin <= 10:
        action_state = "可小幅融资"
    else:
        action_state = "可中等融资"

    risk_lines = [
        f"维持担保比例接近 180% 或自设红线时，停止新增融资并优先降杠杆。",
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
        ]
    )

    if current_margin_debt_ratio > target_margin + 5:
        notes.append("当前融资比例已高于建议值，优先降杠杆后再谈轮动。")
        if current_margin_debt_ratio > target_margin + 8:
            need_deleverage = True
    elif current_margin_debt_ratio < target_margin and not need_deleverage and not only_rebalance and leverage_mode != "不使用":
        notes.append("融资空间尚有余量，但只适合分步执行，不宜一次性加满。")

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
        "risk_level": state_config["risk_level"],
        "action_state": action_state,
        "allow_margin_add": action_state in {"可小幅融资", "可中等融资"},
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
    }
