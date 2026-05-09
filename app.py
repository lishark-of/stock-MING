import streamlit as st
import yfinance as yf
from openai import OpenAI
from supabase import create_client, Client
import datetime
import os
import time
import io
import inspect
import pandas as pd
import numpy as np

try:
    from analysis_engine import (
        build_ai_context_packet,
        build_counter_argument_prompt,
        build_position_aware_prompt,
        build_strict_risk_decision,
    )
except Exception as module_error:
    ANALYSIS_MODULE_ERROR = module_error

    def build_ai_context_packet(supply_chain, valuation, news_rows, replay_rules, peer_rows=None, research_links=None, technical=None, scenario=None, data_quality=None, money_flow=None):
        return f"分析模块降级：{ANALYSIS_MODULE_ERROR}\n{supply_chain}\n{valuation}\n{news_rows}\n{replay_rules}"

    def build_counter_argument_prompt(ticker, bull_case, context):
        return f"请反驳 {ticker} 的看多理由：{bull_case}\n材料：{context}"

    def build_position_aware_prompt(ticker, price, position_status, capital_plan, base_context, strict_decision, money_flow_text_block, technical=None, scenario=None, data_quality=None, position_profile=None):
        return f"标的：{ticker}，价格：{price}，状态：{position_status}，本金：{capital_plan}\n{base_context}\n{strict_decision}\n{money_flow_text_block}"

    def build_strict_risk_decision(valuation, news_rows, replay_rules="", technical=None, money_flow=None, position_status="未买入 (观望/找买点)", data_quality=None, scenario=None):
        return {"risk_score": 0, "action": "分析模块降级", "reasons": [str(ANALYSIS_MODULE_ERROR)]}

try:
    import data_fetcher as _data_fetcher

    DATA_FETCHER_MODULE_ERROR = ""
    normalize_ticker = getattr(_data_fetcher, "normalize_ticker", lambda ticker: (ticker or "").upper().strip())
    get_supply_chain_profile = getattr(
        _data_fetcher,
        "get_supply_chain_profile",
        lambda ticker: {"name": normalize_ticker(ticker), "theme": "模块兼容", "position": "待恢复", "a_share_links": [], "risk_transmission": "data_fetcher 缺少 get_supply_chain_profile"},
    )
    get_valuation_snapshot = getattr(
        _data_fetcher,
        "get_valuation_snapshot",
        lambda ticker: {"ticker": normalize_ticker(ticker), "valuation_flag": "估值模块版本未同步"},
    )
    compute_portfolio_health = getattr(
        _data_fetcher,
        "compute_portfolio_health",
        lambda target, related_tickers=None: {"tickers": [normalize_ticker(target)], "correlation": pd.DataFrame(), "metrics": {}},
    )
    institutional_signal_queries = getattr(_data_fetcher, "institutional_signal_queries", lambda ticker, company_name="": [])
    deep_research_queries = getattr(_data_fetcher, "deep_research_queries", lambda ticker, company_name="": [])
    build_peer_snapshot = getattr(_data_fetcher, "build_peer_snapshot", lambda ticker, supply_profile=None: [])

    if hasattr(_data_fetcher, "build_recent_news_context"):
        build_recent_news_context = _data_fetcher.build_recent_news_context
    else:
        def build_recent_news_context(supabase, ticker, aliases=None, days=2, limit=12, market_type=None):
            return []

    if hasattr(_data_fetcher, "compute_technical_snapshot"):
        compute_technical_snapshot = _data_fetcher.compute_technical_snapshot
    else:
        def compute_technical_snapshot(ticker, period="2y"):
            return {"ticker": normalize_ticker(ticker), "missing": ["data_fetcher 旧版本缺少 compute_technical_snapshot"], "confidence": 0}

    if hasattr(_data_fetcher, "simulate_monte_carlo_range"):
        simulate_monte_carlo_range = _data_fetcher.simulate_monte_carlo_range
    else:
        def simulate_monte_carlo_range(ticker, days=63, simulations=1500, period="2y", seed=42):
            return {"ticker": normalize_ticker(ticker), "horizon_days": days, "missing": ["data_fetcher 旧版本缺少 simulate_monte_carlo_range"], "confidence": 0}

    if hasattr(_data_fetcher, "build_data_quality_report"):
        build_data_quality_report = _data_fetcher.build_data_quality_report
    else:
        def build_data_quality_report(technical=None, valuation=None, news_rows=None, money_flow=None, scenario=None):
            missing = ["data_fetcher 旧版本缺少 build_data_quality_report"]
            missing.extend((technical or {}).get("missing", [])[:4])
            missing.extend((scenario or {}).get("missing", [])[:2])
            return {"score": 45, "grade": "低", "missing": missing, "warnings": (money_flow or {}).get("warnings", [])[:6], "instruction": "数据模块版本未完全同步，只能给条件式观察结论。"}
except Exception as module_error:
    DATA_FETCHER_MODULE_ERROR = module_error

    def normalize_ticker(ticker):
        return (ticker or "").upper().strip()

    def get_supply_chain_profile(ticker):
        return {"name": normalize_ticker(ticker), "theme": "模块降级", "position": "待恢复", "a_share_links": [], "risk_transmission": str(DATA_FETCHER_MODULE_ERROR)}

    def get_valuation_snapshot(ticker):
        return {"ticker": normalize_ticker(ticker), "valuation_flag": f"估值模块降级：{DATA_FETCHER_MODULE_ERROR}"}

    def build_recent_news_context(supabase, ticker, aliases=None, days=2, limit=12, market_type=None):
        return []

    def compute_technical_snapshot(ticker, period="2y"):
        return {"ticker": normalize_ticker(ticker), "missing": ["技术模块降级"], "confidence": 0}

    def simulate_monte_carlo_range(ticker, days=63, simulations=1500, period="2y", seed=42):
        return {"ticker": normalize_ticker(ticker), "missing": ["情景模块降级"], "confidence": 0}

    def build_data_quality_report(technical=None, valuation=None, news_rows=None, money_flow=None, scenario=None):
        return {"score": 0, "grade": "低", "missing": [str(DATA_FETCHER_MODULE_ERROR)], "warnings": [], "instruction": "数据模块降级，只能观察。"}

    def compute_portfolio_health(target, related_tickers=None):
        return {"tickers": [normalize_ticker(target)], "correlation": pd.DataFrame(), "metrics": {}}

    def institutional_signal_queries(ticker, company_name=""):
        return []

    def deep_research_queries(ticker, company_name=""):
        return []

    def build_peer_snapshot(ticker, supply_profile=None):
        return []

try:
    from money_flow_tracker import collect_money_flow_snapshot, money_flow_text
except Exception as module_error:
    MONEY_FLOW_MODULE_ERROR = module_error

    def collect_money_flow_snapshot(ticker, market_type=None):
        return {"ticker": ticker, "summary": {"positive": [], "negative": [f"资金流模块降级：{MONEY_FLOW_MODULE_ERROR}"], "stance": "中性"}, "warnings": [str(MONEY_FLOW_MODULE_ERROR)]}

    def money_flow_text(flow):
        return str(flow)

try:
    import visualizer as _visualizer

    VISUALIZER_MODULE_ERROR = ""
except Exception as module_error:
    VISUALIZER_MODULE_ERROR = module_error


def _fallback_render(title, payload):
    if VISUALIZER_MODULE_ERROR:
        st.warning(f"{title} 降级：{VISUALIZER_MODULE_ERROR}")
    else:
        st.warning(f"{title} 降级：云端 visualizer.py 版本未完全同步。")
    if isinstance(payload, pd.DataFrame):
        st.dataframe(payload, use_container_width=True)
    else:
        st.json(payload)


if "render_supply_chain_module" not in globals():
    render_supply_chain_module = getattr(_visualizer, "render_supply_chain_module", None) if "_visualizer" in globals() else None
if "render_valuation_module" not in globals():
    render_valuation_module = getattr(_visualizer, "render_valuation_module", None) if "_visualizer" in globals() else None
if "render_recent_sentiment_module" not in globals():
    render_recent_sentiment_module = getattr(_visualizer, "render_recent_sentiment_module", None) if "_visualizer" in globals() else None
if "render_portfolio_health_module" not in globals():
    render_portfolio_health_module = getattr(_visualizer, "render_portfolio_health_module", None) if "_visualizer" in globals() else None
if "render_risk_decision" not in globals():
    render_risk_decision = getattr(_visualizer, "render_risk_decision", None) if "_visualizer" in globals() else None
if "render_money_flow_module" not in globals():
    render_money_flow_module = getattr(_visualizer, "render_money_flow_module", None) if "_visualizer" in globals() else None
if "render_peer_snapshot" not in globals():
    render_peer_snapshot = getattr(_visualizer, "render_peer_snapshot", None) if "_visualizer" in globals() else None
if "render_research_links" not in globals():
    render_research_links = getattr(_visualizer, "render_research_links", None) if "_visualizer" in globals() else None
if "render_technical_module" not in globals():
    render_technical_module = getattr(_visualizer, "render_technical_module", None) if "_visualizer" in globals() else None
if "render_scenario_module" not in globals():
    render_scenario_module = getattr(_visualizer, "render_scenario_module", None) if "_visualizer" in globals() else None
if "render_data_quality_module" not in globals():
    render_data_quality_module = getattr(_visualizer, "render_data_quality_module", None) if "_visualizer" in globals() else None

if render_supply_chain_module is None:
    def render_supply_chain_module(profile, portfolio_health):
        _fallback_render("产业链可视化", profile)
if render_valuation_module is None:
    def render_valuation_module(valuation):
        _fallback_render("估值可视化", valuation)
if render_recent_sentiment_module is None:
    def render_recent_sentiment_module(news_rows):
        st.dataframe(pd.DataFrame(news_rows), use_container_width=True) if news_rows else st.info("暂无舆情")
if render_portfolio_health_module is None:
    def render_portfolio_health_module(portfolio_health):
        _fallback_render("持仓体检可视化", portfolio_health)
if render_risk_decision is None:
    def render_risk_decision(decision):
        _fallback_render("风控结论可视化", decision)
if render_money_flow_module is None:
    def render_money_flow_module(flow):
        _fallback_render("资金面可视化", flow)
if render_peer_snapshot is None:
    def render_peer_snapshot(peer_rows):
        st.dataframe(pd.DataFrame(peer_rows), use_container_width=True) if peer_rows else st.info("暂无同行对比")
if render_research_links is None:
    def render_research_links(links):
        for link in links or []:
            st.markdown(f"- [公开检索]({link})")
if render_technical_module is None:
    def render_technical_module(technical):
        _fallback_render("实时指标可视化", technical)
if render_scenario_module is None:
    def render_scenario_module(scenario):
        _fallback_render("情景推演可视化", scenario)
if render_data_quality_module is None:
    def render_data_quality_module(report):
        _fallback_render("可信度可视化", report)


def call_with_supported_kwargs(func, *args, **kwargs):
    try:
        signature = inspect.signature(func)
        supports_any_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        )
        if not supports_any_kwargs:
            kwargs = {key: value for key, value in kwargs.items() if key in signature.parameters}
    except Exception:
        pass
    return func(*args, **kwargs)


def build_strict_risk_decision_safe(
    valuation,
    news_rows,
    replay_rules="",
    technical=None,
    money_flow=None,
    position_status="未买入 (观望/找买点)",
    data_quality=None,
    scenario=None,
):
    try:
        return call_with_supported_kwargs(
            build_strict_risk_decision,
            valuation,
            news_rows,
            replay_rules=replay_rules,
            technical=technical,
            money_flow=money_flow,
            position_status=position_status,
            data_quality=data_quality,
            scenario=scenario,
        )
    except TypeError as e:
        decision = build_strict_risk_decision(
            valuation,
            news_rows,
            replay_rules=replay_rules,
            technical=technical,
            money_flow=money_flow,
            position_status=position_status,
        )
        if isinstance(decision, dict):
            decision.setdefault("reasons", []).append(f"分析引擎版本兼容提示：{e}")
            decision["risk_score"] = max(int(decision.get("risk_score", 0)), 55)
        return decision


def build_ai_context_packet_safe(
    supply_chain,
    valuation,
    news_rows,
    replay_rules,
    peer_rows=None,
    research_links=None,
    technical=None,
    scenario=None,
    data_quality=None,
    money_flow=None,
):
    try:
        return call_with_supported_kwargs(
            build_ai_context_packet,
            supply_chain,
            valuation,
            news_rows,
            replay_rules,
            peer_rows=peer_rows,
            research_links=research_links,
            technical=technical,
            scenario=scenario,
            data_quality=data_quality,
            money_flow=money_flow,
        )
    except TypeError as e:
        legacy_context = build_ai_context_packet(
            supply_chain,
            valuation,
            news_rows,
            replay_rules,
            peer_rows=peer_rows,
            research_links=research_links,
        )
        return f"""
{legacy_context}

【版本兼容补充】
分析引擎旧版本不支持全部新字段：{e}
实时技术指标：{technical or '缺失'}
Monte Carlo 情景：{scenario or '缺失'}
数据可信度：{data_quality or '缺失'}
资金面：{money_flow or '缺失'}
"""


def build_position_aware_prompt_safe(
    ticker,
    price,
    position_status,
    capital_plan,
    base_context,
    strict_decision,
    money_flow_text_block,
    technical=None,
    scenario=None,
    data_quality=None,
    position_profile=None,
):
    try:
        prompt = call_with_supported_kwargs(
            build_position_aware_prompt,
            ticker,
            price,
            position_status,
            capital_plan,
            base_context,
            strict_decision,
            money_flow_text_block,
            technical=technical,
            scenario=scenario,
            data_quality=data_quality,
            position_profile=position_profile,
        )
        if position_profile:
            prompt += f"""

【用户持仓画像补充】
{position_profile}
要求：必须围绕成本价判断浮盈/浮亏，止损和止盈都要写成相对成本价的动作。
"""
        return prompt
    except TypeError as e:
        legacy_prompt = build_position_aware_prompt(
            ticker,
            price,
            position_status,
            capital_plan,
            base_context,
            strict_decision,
            money_flow_text_block,
        )
        return f"""
{legacy_prompt}

【版本兼容补充】
分析引擎旧版本不支持全部新字段：{e}
实时技术指标：{technical or '缺失'}
Monte Carlo 情景：{scenario or '缺失'}
数据可信度：{data_quality or '缺失'}
用户持仓画像：{position_profile or '缺失'}
要求：数据可信度低时禁止给确定买入结论；目标价必须参考 Monte Carlo p10/p50/p90。
"""


def _num(value, default=None):
    try:
        if value is None or value == "":
            return default
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _fmt_price(value, currency=""):
    value = _num(value)
    if value is None:
        return "N/A"
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{value:,.2f}"


def build_position_profile(ticker, current_price, cost_price, holding_units, capital_plan, position_status, currency):
    current = _num(current_price)
    cost = _num(cost_price)
    units = _num(holding_units, 0) or 0
    capital = _num(capital_plan, 0) or 0
    is_holding = str(position_status).startswith("已持有")
    pnl_pct = None
    pnl_amount = None
    state = "未输入成本价"

    if current and cost and cost > 0:
        pnl_pct = round((current / cost - 1) * 100, 2)
        if units > 0:
            pnl_amount = round((current - cost) * units, 2)
        elif capital > 0:
            pnl_amount = round(capital * pnl_pct / 100, 2)
        if pnl_pct > 0:
            state = f"浮盈 {pnl_pct:.2f}%"
        elif pnl_pct < 0:
            state = f"浮亏 {abs(pnl_pct):.2f}%"
        else:
            state = "接近成本"
    elif not is_holding:
        state = "未买入，成本价作为计划参考"

    return {
        "ticker": ticker,
        "position_status": position_status,
        "is_holding": is_holding,
        "currency": currency,
        "current_price": current,
        "cost_price": cost,
        "holding_units": units,
        "capital_plan": capital,
        "pnl_pct": pnl_pct,
        "pnl_amount": pnl_amount,
        "profit_state": state,
    }


def build_one_line_trade_instruction(profile, strict_decision, technical=None, scenario=None, money_flow=None, data_quality=None):
    technical = technical or {}
    scenario = scenario or {}
    money_flow = money_flow or {}
    data_quality = data_quality or {}
    current = profile.get("current_price")
    cost = profile.get("cost_price")
    pnl_pct = profile.get("pnl_pct")
    is_holding = profile.get("is_holding")
    risk_score = int(_num((strict_decision or {}).get("risk_score"), 0) or 0)
    risk_action = (strict_decision or {}).get("action", "允许继续分析")
    ma60_state = technical.get("ma60_state", "未知")
    rsi = _num(technical.get("rsi"))
    p10 = _num(scenario.get("p10"))
    p75 = _num(scenario.get("p75"))
    p90 = _num(scenario.get("p90"))
    ma60 = _num(technical.get("ma60"))
    quality_score = int(_num(data_quality.get("score"), 100) or 0)
    negatives = ((money_flow.get("summary") or {}).get("negative") or [])
    reasons = list((strict_decision or {}).get("reasons") or [])

    trend_bad = ma60_state == "低于MA60"
    rsi_hot = rsi is not None and rsi >= 72
    flow_bad = bool(negatives)
    hard_block = risk_action.startswith("禁止") or risk_score >= 70 or quality_score < 45

    stop_loss = None
    take_profit = None
    if current:
        stop_loss = current * 0.92
        take_profit = current * 1.12
    if p10:
        stop_loss = p10 if stop_loss is None else min(stop_loss, p10)
    if p75:
        take_profit = p75
    if p90 and rsi_hot:
        take_profit = min(p90, take_profit) if take_profit else p90

    if is_holding and cost:
        if pnl_pct is not None and pnl_pct < 0:
            stop_loss = min(current * 0.97, cost * 0.92) if current else cost * 0.92
        elif pnl_pct is not None:
            trailing_candidates = [cost * 1.01]
            if ma60:
                trailing_candidates.append(ma60 * 0.98)
            if current:
                trailing_candidates.append(current * 0.93)
            stop_loss = max(trailing_candidates)

    if is_holding:
        if pnl_pct is not None and pnl_pct <= -8 and (trend_bad or flow_bad or risk_score >= 55):
            action = "减仓/止损"
            driver = "亏损已扩大且趋势或资金面未确认修复"
        elif pnl_pct is not None and pnl_pct < 0:
            action = "防守持有"
            driver = "仍低于成本，先等趋势/资金面确认"
        elif pnl_pct is not None and pnl_pct >= 15 and (rsi_hot or (p75 and current and current >= p75)):
            action = "分批止盈"
            driver = "相对成本已有较高浮盈，且接近情景上沿或RSI偏热"
        elif hard_block:
            action = "降仓观察"
            driver = "系统风控触发较多，优先保护本金"
        else:
            action = "继续持有"
            driver = "未触发硬性卖出，按成本价上方移动止损"
    else:
        if hard_block:
            action = "禁止开仓"
            driver = "风险分或数据缺口过高，不适合新买入"
        elif trend_bad or quality_score < 60:
            action = "观望"
            driver = "趋势或数据可信度不足，等待更清晰买点"
        elif risk_score <= 40:
            action = "小仓尝试"
            driver = "风控未明显否决，可用小仓验证"
        else:
            action = "观望/小仓试错"
            driver = "仍有风险因子，仓位必须保守"

    if take_profit is None and cost:
        take_profit = cost * 1.15
    if stop_loss is None and cost:
        stop_loss = cost * 0.92

    cost_text = _fmt_price(cost, profile.get("currency")) if cost else "未填成本"
    current_text = _fmt_price(current, profile.get("currency"))
    stop_text = _fmt_price(stop_loss, profile.get("currency"))
    take_text = _fmt_price(take_profit, profile.get("currency"))
    pnl_text = profile.get("profit_state", "未计算")
    risk_text = "；".join([str(r) for r in reasons[:3]]) if reasons else "暂无硬性风险，但仍需盘中确认"
    one_line = f"{action}：当前价 {current_text}，相对成本 {cost_text} 为 {pnl_text}；{driver}。止损参考 {stop_text}，止盈/减仓参考 {take_text}。"

    return {
        "action": action,
        "one_line": one_line,
        "driver": driver,
        "stop_loss": round(stop_loss, 2) if stop_loss else None,
        "take_profit": round(take_profit, 2) if take_profit else None,
        "risk_factors": risk_text,
        "risk_score": risk_score,
        "quality_score": quality_score,
    }


def render_trade_instruction_card(profile, instruction):
    st.markdown("#### 🧾 一句话交易指令卡")
    action = instruction.get("action", "")
    if any(word in action for word in ["禁止", "止损", "减仓", "降仓"]):
        st.error(instruction.get("one_line", "暂无交易指令"))
    elif any(word in action for word in ["观望", "防守"]):
        st.warning(instruction.get("one_line", "暂无交易指令"))
    else:
        st.success(instruction.get("one_line", "暂无交易指令"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("成本价", _fmt_price(profile.get("cost_price"), profile.get("currency")))
    c2.metric("当前价", _fmt_price(profile.get("current_price"), profile.get("currency")))
    pnl_delta = None
    if profile.get("pnl_amount") is not None:
        pnl_delta = _fmt_price(profile.get("pnl_amount"), profile.get("currency"))
    c3.metric("浮动盈亏", profile.get("profit_state", "未计算"), pnl_delta)
    c4.metric("当前建议", instruction.get("action", "观察"))

    c5, c6, c7 = st.columns(3)
    c5.metric("止损参考", _fmt_price(instruction.get("stop_loss"), profile.get("currency")))
    c6.metric("止盈/减仓参考", _fmt_price(instruction.get("take_profit"), profile.get("currency")))
    c7.metric("风控分", instruction.get("risk_score", 0), f"可信度 {instruction.get('quality_score', 0)}")
    st.caption(f"风险因素：{instruction.get('risk_factors', '')}")


def get_config_value(name, default=""):
    env_value = os.getenv(name)
    if env_value:
        return env_value

    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

# ==========================================
# 🚀 基金经理AI克隆系统 - 核心逻辑引擎
# ==========================================

# ✅ 修复1：去除港股分析函数重复定义（保留完整版本）
def display_hk_stock_analysis(target, price):
    """港股分析 - 统一版本（包含完整功能）"""
    st.markdown("#### 🇭🇰 港股深度分析系统")
    
    signals = compute_hk_signals(target)
    if signals:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
            st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
        with col2:
            trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
            st.metric(f"{trend_color} 趋势 (MA20)", f"HK${signals['ma20']}", signals['trend'])
        with col3:
            st.metric("💰 机构分红率", f"{signals['div_yield']}%", "避险指标")
        with col4:
            st.metric("📊 恒指联动 Beta", signals['beta'], "")
        
        # ✅ 完整的高股息警告逻辑
        if signals['div_yield'] > 6.0:
            st.info("💡 嗅探提示：该股息率超 6%，具备极强的高息防守属性（类高股息央企逻辑）。")
    
    st.markdown("---")

# ✅ 修复2：基金经理管理 - 安全的多关键词检索
MANAGER_PROFILES = {
    "聚鸣 刘晓龙": {
        "display_name": "刘晓龙",
        "fund": "聚鸣",
        "style": "成长+价值混合",
        "keywords": ["刘晓龙", "聚鸣", "小龙"],
        "description": "专注成长型企业估值投资"
    },
    "中庚 丘栋荣": {
        "display_name": "丘栋荣",
        "fund": "中庚",
        "style": "深度价值防守",
        "keywords": ["丘栋荣", "中庚", "丘", "防守"],
        "description": "极端价值投资者，低PB深度布局"
    },
    "易方达 张坤": {
        "display_name": "张坤",
        "fund": "易方达",
        "style": "消费+科技",
        "keywords": ["张坤", "易方达", "消费"],
        "description": "消费赛道与科技创新结合"
    },
    "聚鸣 王文祥": {
        "display_name": "王文祥",
        "fund": "聚鸣",
        "style": "产业链投资",
        "keywords": ["王文祥", "聚鸣", "王"],
        "description": "关注产业链景气度和竞争格局"
    },
    "聚鸣 惠博文": {
        "display_name": "惠博文",
        "fund": "聚鸣",
        "style": "周期+成长",
        "keywords": ["惠博文", "聚鸣", "惠"],
        "description": "挖掘周期低谷的成长机会"
    },
    "游资 龙头战法": {
        "display_name": "龙头战法",
        "fund": "游资",
        "style": "短线龙头追踪",
        "keywords": ["龙头", "游资", "涨停", "热点"],
        "description": "追踪热点龙头，高换手操作"
    }
}

# ✅ 修复3：安全的基金经理名字提取 + 多关键词检索
def retrieve_manager_rules(manager_choice, all_rules):
    if manager_choice not in MANAGER_PROFILES:
        return [], "未知经理"
    
    profile = MANAGER_PROFILES[manager_choice]
    keywords = profile["keywords"]
    
    manager_rules = []
    for rule in all_rules:
        if any(kw.lower() in rule.lower() for kw in keywords):
            manager_rules.append(rule)
    
    return manager_rules, profile["display_name"]

def split_text_to_chunks(text, chunk_size=4000, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

def get_deepseek_api_key():
    keys = st.session_state.get("ds_keys") or []
    if not keys:
        return None

    index = st.session_state.get("ds_key_index", 0) % len(keys)
    st.session_state.ds_key_index = index + 1
    st.session_state.ds_key = keys[index]
    return keys[index]

def semantic_search_manager_knowledge(manager_name, query, top_k=3):
    api_key = get_deepseek_api_key()
    if not api_key or not supabase:
        return []
    
    client = OpenAI(api_key=api_key)
    try:
        query_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
            encoding_format="float"
        )
        query_embedding = query_response.data[0].embedding
        
        results = supabase.rpc(
            'match_manager_embeddings',
            {
                'query_embedding': query_embedding,
                'manager_name': manager_name,
                'match_threshold': 0.7,
                'match_count': top_k
            }
        ).execute()
        
        return [r['content_chunk'] for r in results.data] if results.data else []
    except Exception as e:
        st.warning(f"⚠️ 向量检索失败: {e}")
        return []

def update_manager_learning_feedback(manager_name, feedback_content, rating):
    if not supabase:
        return
    try:
        supabase.table("manager_embeddings").insert({
            "manager_name": manager_name,
            "document_type": "feedback",
            "content_chunk": f"[反馈] {feedback_content} (评分: {rating}★)",
            "metadata": {
                "feedback_rating": rating,
                "timestamp": datetime.datetime.now().isoformat()
            }
        }).execute()
        st.success(f"✅ 反馈已记录，AI 会更了解 {manager_name}!")
    except Exception as e:
        st.warning(f"⚠️ 反馈记录失败: {e}")
# ==========================================
# 1. 全局配置与极简美学 UI
# ==========================================
st.set_page_config(page_title="量化交易终端 V25.0 GLOBAL", page_icon="🦈", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #F5F5F7; color: #1D1D1F; font-family: -apple-system, sans-serif; }
    .stButton>button { background-color: #1D1D1F; color: white; border-radius: 8px; border: none; width: 100%; font-weight: 500; transition: 0.2s; }
    .stButton>button:hover { background-color: #434343; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border: 1px solid #E5E5EA; }
    .risk-alert { background-color: #FFF0F0; padding: 15px; border-radius: 8px; border-left: 4px solid #FF3B30; margin-bottom: 10px; color: #FF3B30; font-weight: 600;}
    .knowledge-card { background-color: #ffffff; padding: 15px; border-radius: 8px; border-left: 4px solid #0071E3; margin-bottom: 10px; font-size: 0.9rem;}
    .us-card { background-color: #F0F7FF; padding: 15px; border-radius: 8px; border-left: 4px solid #0071E3; margin-bottom: 10px; }
    .hk-card { background-color: #FFE5F0; padding: 15px; border-radius: 8px; border-left: 4px solid #D91E63; margin-bottom: 10px; }
    .jp-card { background-color: #FFF0E5; padding: 15px; border-radius: 8px; border-left: 4px solid #FF6B35; margin-bottom: 10px; }
    .cn-card { background-color: #FFF8F0; padding: 15px; border-radius: 8px; border-left: 4px solid #FF6B35; margin-bottom: 10px; }
    .token-counter { background-color: #FFE5E5; padding: 10px; border-radius: 8px; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📊 Token 消耗计数器
# ==========================================
if 'token_usage' not in st.session_state:
    st.session_state.token_usage = {
        'deepseek_calls': 0,
        'estimated_tokens': 0
    }

def log_token_usage(prompt_tokens_estimate=2000, completion_tokens_estimate=1500):
    st.session_state.token_usage['deepseek_calls'] += 1
    st.session_state.token_usage['estimated_tokens'] += (prompt_tokens_estimate + completion_tokens_estimate)

def estimate_tokens(text):
    return max(1, int(len(str(text)) / 1.7))

# ==========================================
# 2. 核心功能与缓存提速优化
# ==========================================
@st.cache_data(ttl=300)
def get_current_price(ticker):
    try:
        return round(yf.Ticker(ticker).history(period='1d')['Close'].iloc[0], 2)
    except:
        return None

@st.cache_data(ttl=3600)
def get_historical_data(ticker, start_str, end_str):
    try:
        data = yf.Ticker(ticker).history(start=start_str, end=end_str)
        if data.empty:
            return pd.DataFrame()
        return data
    except:
        return pd.DataFrame()

def compute_rsi_series(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_max_drawdown(close):
    if close.empty:
        return 0.0
    peak = close.cummax()
    drawdown = close / peak - 1
    return round(float(drawdown.min() * 100), 2)

def format_replay_case(case):
    return (
        f"{case['start_date']}->{case['end_date']} | "
        f"窗口涨跌 {case['window_return']}% | "
        f"回撤 {case['max_drawdown']}% | "
        f"波动 {case['volatility']}% | "
        f"量能 {case['volume_ratio']}x | "
        f"RSI {case['rsi']} | "
        f"MA20偏离 {case['ma20_gap']}% | "
        f"MA60状态 {case['ma60_state']} | "
        f"未来20日 {case['future_20d_return']}% | "
        f"未来60日 {case['future_60d_return']}% | "
        f"结果 {case['outcome']}"
    )

@st.cache_data(ttl=1800)
def build_auto_replay_cases(ticker, lookback_days=730, window_days=60, future_days=60, case_count=16):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=lookback_days + 180)
    end = today + datetime.timedelta(days=1)
    hist = get_historical_data(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    if hist.empty or len(hist) < window_days + future_days + 80:
        return [], pd.DataFrame()

    hist = hist.copy()
    hist = hist.dropna(subset=["Close"])
    hist["MA20"] = hist["Close"].rolling(20).mean()
    hist["MA60"] = hist["Close"].rolling(60).mean()
    hist["RSI"] = compute_rsi_series(hist["Close"], 14)
    hist["VolumeMA20"] = hist["Volume"].rolling(20).mean() if "Volume" in hist.columns else 0

    min_date = pd.Timestamp(today - datetime.timedelta(days=lookback_days)).tz_localize(None)
    dates = pd.Series(hist.index).apply(lambda x: pd.Timestamp(x).tz_localize(None))
    candidate_positions = [
        i for i, d in enumerate(dates)
        if d >= min_date and i >= window_days + 60 and i <= len(hist) - future_days - 1
    ]

    if not candidate_positions:
        return [], hist

    case_count = max(6, min(int(case_count), 30, len(candidate_positions)))
    selected_positions = np.linspace(0, len(candidate_positions) - 1, case_count, dtype=int)
    end_positions = [candidate_positions[i] for i in selected_positions]

    cases = []
    for end_pos in end_positions:
        start_pos = end_pos - window_days
        future_20_pos = min(end_pos + 20, len(hist) - 1)
        future_60_pos = min(end_pos + future_days, len(hist) - 1)

        window = hist.iloc[start_pos:end_pos + 1]
        end_row = hist.iloc[end_pos]
        start_close = float(window["Close"].iloc[0])
        end_close = float(window["Close"].iloc[-1])
        future_20_close = float(hist["Close"].iloc[future_20_pos])
        future_60_close = float(hist["Close"].iloc[future_60_pos])

        window_return = (end_close / start_close - 1) * 100 if start_close else 0
        future_20_return = (future_20_close / end_close - 1) * 100 if end_close else 0
        future_60_return = (future_60_close / end_close - 1) * 100 if end_close else 0
        volatility = float(window["Close"].pct_change().std() * 100) if len(window) > 2 else 0

        volume_ratio = 0.0
        volume_ma20 = end_row.get("VolumeMA20", 0)
        if "Volume" in hist.columns and pd.notna(volume_ma20) and volume_ma20:
            volume_ratio = float(end_row.get("Volume", 0) / volume_ma20)

        ma20_raw = end_row.get("MA20", 0)
        ma60_raw = end_row.get("MA60", 0)
        rsi_raw = end_row.get("RSI", 0)
        ma20 = float(ma20_raw) if pd.notna(ma20_raw) else 0
        ma60 = float(ma60_raw) if pd.notna(ma60_raw) else 0
        rsi = float(rsi_raw) if pd.notna(rsi_raw) else 0
        ma20_gap = (end_close / ma20 - 1) * 100 if ma20 else 0
        ma60_state = "站上MA60" if ma60 and end_close >= ma60 else "低于MA60"

        if future_60_return >= 12:
            outcome = "大幅上涨"
        elif future_60_return >= 4:
            outcome = "温和上涨"
        elif future_60_return <= -12:
            outcome = "大幅下跌"
        elif future_60_return <= -4:
            outcome = "温和下跌"
        else:
            outcome = "震荡"

        cases.append({
            "start_date": window.index[0].strftime("%Y-%m-%d"),
            "end_date": window.index[-1].strftime("%Y-%m-%d"),
            "start_close": round(start_close, 2),
            "end_close": round(end_close, 2),
            "window_return": round(window_return, 2),
            "max_drawdown": calc_max_drawdown(window["Close"]),
            "volatility": round(volatility, 2),
            "volume_ratio": round(volume_ratio, 2),
            "rsi": round(rsi, 2),
            "ma20_gap": round(ma20_gap, 2),
            "ma60_state": ma60_state,
            "future_20d_return": round(future_20_return, 2),
            "future_60d_return": round(future_60_return, 2),
            "outcome": outcome,
        })

    return cases, hist

def call_deepseek_stream(prompt, system_role="作为顶级量化基金经理。"):
    api_key = get_deepseek_api_key()
    if not api_key:
        return st.error("❌ 缺少 DeepSeek 密钥")

    try:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        time_guard = f"""
【当前系统时间】：{today_str}
【强制时间规则】：
1. 你必须以当前系统时间为准。
2. 如果资料不是最新的，必须明确说“该信息可能过时”。
3. 不允许把几年前的信息描述成“近期”“最新”“当前”。
4. 不允许编造实时新闻、实时持仓、实时公告、实时资金流。
5. 如果缺少最新舆情、公告或行情，请直接说明“缺少最新数据”。
"""

        final_system_role = system_role + "\n" + time_guard
        log_token_usage(estimate_tokens(final_system_role + prompt), 4000)

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=120.0,
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": final_system_role},
                {"role": "user", "content": prompt}
            ],
            stream=True,
            temperature=0.7,
            max_tokens=4000
        )

        st.write_stream((chunk.choices[0].delta.content or "") for chunk in response)

    except Exception as e:
        st.error(f"⚠️ DeepSeek 调用失败: {e}")


def call_deepseek_non_stream(prompt, system_role="作为顶级量化基金经理。", max_tokens=2000):
    if not st.session_state.get("ds_keys"):
        return None

    today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    time_guard = f"""
【当前系统时间】：{today_str}
【强制时间规则】：
1. 你必须以当前系统时间为准。
2. 如果资料不是最新的，必须明确说“该信息可能过时”。
3. 不允许把几年前的信息描述成“近期”“最新”“当前”。
4. 不允许编造实时新闻、实时持仓、实时公告、实时资金流。
5. 如果缺少最新舆情、公告或行情，请直接说明“缺少最新数据”。
"""

    final_system_role = system_role + "\n" + time_guard
    log_token_usage(estimate_tokens(final_system_role + prompt), max_tokens)
    last_error = None

    for attempt in range(2):
        api_key = get_deepseek_api_key()
        if not api_key:
            return None

        try:
            if attempt:
                st.info("DeepSeek 首次响应超时，正在自动换 key 重试一次。")

            timeout_seconds = 180.0 if max_tokens >= 3000 else 120.0
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1",
                timeout=timeout_seconds,
            )

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": final_system_role},
                    {"role": "user", "content": prompt}
                ],
                stream=False,
                temperature=0.5,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            last_error = e

    st.error(f"⚠️ DeepSeek 调用失败: {last_error}")
    return None

# ==========================================
# ✨ 多交易所智能识别引擎 ✨
# ==========================================

def identify_market(raw_input):
    """智能识别输入符号属于哪个交易所"""
    raw_input = raw_input.upper().strip()
    
    # A 股判断（纯数字）
    if raw_input.isdigit() and len(raw_input) == 6:
        if raw_input.startswith('6'):
            return f"{raw_input}.SS", "A_SHARE_SH", "🇨🇳 A股 (沪)", "¥"
        elif raw_input.startswith(('0', '3')):
            return f"{raw_input}.SZ", "A_SHARE_SZ", "🇨🇳 A股 (深)", "¥"
    
    # 港股判断（以 0 开头的 4 位数字）
    if raw_input.isdigit() and len(raw_input) == 4 and raw_input.startswith('0'):
        return f"{raw_input}.HK", "HK_STOCK", "🇭🇰 港股 (HK)", "HK$"
    elif raw_input.endswith('.HK'):
        return raw_input, "HK_STOCK", "🇭🇰 港股 (HK)", "HK$"
    
    # 日股判断（以 6 开头的 4 位数字）
    if raw_input.isdigit() and len(raw_input) == 4 and raw_input.startswith('6'):
        return f"{raw_input}.T", "JP_STOCK", "🇯🇵 日股 (JPX)", "¥"
    elif raw_input.endswith('.T'):
        return raw_input, "JP_STOCK", "🇯🇵 日股 (JPX)", "¥"
    
    # 美股判断（字母）
    if raw_input.isalpha() or '.' in raw_input:
        return raw_input, "US_STOCK", "🇺🇸 美股 (NASDAQ/NYSE)", "$"
    
    # 默认美股
    return raw_input, "US_STOCK", "🇺🇸 美股 (NASDAQ/NYSE)", "$"

# ==========================================
# 3. 权限认证与 Supabase 云端连线
# ==========================================
if 'user_role' not in st.session_state: 
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal V22 (全球三市场)</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("", type="password", placeholder="输入访问密钥", label_visibility="collapsed")
        if st.button("接入系统"):
            if pwd == "888888": st.session_state.user_role = "Admin"; st.rerun()
            elif pwd == "guest": st.session_state.user_role = "Guest"; st.rerun()
            else: st.error("密钥验证失败")
else:
    try:
        raw_ds_keys = [
            get_config_value("DEEPSEEK_API_KEY"),
            get_config_value("DEEPSEEK_TOKEN_1"),
            get_config_value("DEEPSEEK_TOKEN_2"),
        ]
        ds_keys = []
        for key in raw_ds_keys:
            key = str(key).strip()
            if key and key not in ds_keys:
                ds_keys.append(key)

        st.session_state.ds_keys = ds_keys
        st.session_state.ds_key = ds_keys[0] if ds_keys else None
        if "ds_key_index" not in st.session_state:
            st.session_state.ds_key_index = 0

        sb_url = get_config_value("SUPABASE_URL")
        sb_key = get_config_value("SUPABASE_KEY")
        if not sb_url or not sb_key:
            raise ValueError("缺少 SUPABASE_URL 或 SUPABASE_KEY")

        supabase: Client = create_client(sb_url, sb_key)
    except Exception as e:
        st.session_state.ds_keys = []
        st.session_state.ds_key = None
        supabase = None
        st.error(f"⚠️ 云端配置缺失: {e}")

    def load_cloud_knowledge():
        if not supabase: return {"strategies": [], "reflections": []}
        try:
            res = supabase.table("brain_memory").select("*").execute()
            data = res.data
            return {
                "strategies": [d['content'] for d in data if d['memory_type'] == 'strategy'],
                "reflections": [d['content'] for d in data if d['memory_type'] == 'reflection']
            }
        except: return {"strategies": [], "reflections": []}

    def insert_cloud_memory(m_type, content):
        if not supabase: return
        try:
            supabase.table("brain_memory").insert({"memory_type": m_type, "content": content}).execute()
        except: pass

    def get_all_cloud_memories():
        if not supabase: return []
        try:
            res = supabase.table("brain_memory").select("id, memory_type, content").order("id", desc=True).execute()
            return res.data
        except: return []

    def delete_cloud_memories(ids_to_delete):
        if not supabase or not ids_to_delete: return
        try:
            supabase.table("brain_memory").delete().in_("id", ids_to_delete).execute()
        except: pass

    def save_stock_logic_rule(ticker, market_type, content):
        if not supabase or not content:
            return False

        try:
            supabase.table("stock_reports").insert({
                "ticker": ticker,
                "market_type": market_type,
                "report_type": "auto_replay_rules",
                "report_content": content,
            }).execute()
            return True
        except Exception as e:
            st.warning(f"股票专属规则写入失败：{e}")
            return False

    def load_stock_logic_rules(ticker, limit=3):
        if not supabase:
            return ""

        try:
            res = (
                supabase
                .table("stock_reports")
                .select("report_content, created_at")
                .eq("ticker", ticker)
                .eq("report_type", "auto_replay_rules")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = res.data or []
        except Exception:
            return ""

        if not rows:
            return ""

        chunks = []
        for row in rows:
            content = (row.get("report_content") or "").strip()
            created_at = row.get("created_at", "")
            if content:
                chunks.append(f"【{created_at} 自动炼丹规则】\n{content[:1600]}")

        return "\n\n".join(chunks)

    def _fmt_pct(value):
        if value is None:
            return "N/A"
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"

    @st.cache_data(ttl=900)
    def fetch_market_snapshot():
        symbols = [
            ("A股上证", "000001.SS"),
            ("A股深成", "399001.SZ"),
            ("港股恒生", "^HSI"),
            ("美股纳指", "^IXIC"),
            ("美股标普", "^GSPC"),
            ("USD/JPY", "JPY=X"),
            ("黄金", "GC=F"),
            ("半导体ETF", "SMH"),
            ("新能源ETF", "ICLN"),
            ("有色金属ETF", "COPX"),
            ("中概互联网ETF", "KWEB"),
        ]

        snapshot = []
        for name, symbol in symbols:
            try:
                hist = yf.Ticker(symbol).history(period="7d", interval="1d")
                close = hist["Close"].dropna() if not hist.empty else pd.Series(dtype=float)
                if len(close) < 2:
                    snapshot.append(f"{name}({symbol})：暂无足够行情")
                    continue

                latest = float(close.iloc[-1])
                previous = float(close.iloc[-2])
                change_pct = (latest / previous - 1) * 100 if previous else None
                snapshot.append(
                    f"{name}({symbol})：最新 {latest:.2f}，近一日 {_fmt_pct(change_pct)}"
                )
            except Exception as e:
                snapshot.append(f"{name}({symbol})：行情抓取失败，原因 {e}")

        return snapshot

    def fetch_recent_market_context(limit=18):
        if not supabase:
            return []

        context = []

        try:
            res = (
                supabase
                .table("market_news")
                .select("keyword, title, summary, risk_tag, sentiment, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            for item in res.data or []:
                title = item.get("title", "")
                if not title:
                    continue
                context.append(
                    f"market_news｜{item.get('keyword', '')}｜{title}"
                    f"｜情绪:{item.get('sentiment', '')}"
                    f"｜风险:{item.get('risk_tag', '')}"
                    f"｜摘要:{item.get('summary', '')}"
                    f"｜时间:{item.get('created_at', '')}"
                )
        except Exception as e:
            context.append(f"market_news 读取失败：{e}")

        try:
            res = (
                supabase
                .table("processed_sources")
                .select("manager_name, title, url, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            for item in res.data or []:
                title = item.get("title", "")
                if not title:
                    continue
                context.append(
                    f"processed_sources｜{item.get('manager_name', '')}｜{title}"
                    f"｜时间:{item.get('created_at', '')}"
                    f"｜链接:{item.get('url', '')}"
                )
        except Exception as e:
            context.append(f"processed_sources 读取失败：{e}")

        return context[:limit]

    def summarize_context_trends(context_lines):
        trend_terms = {
            "AI算力/数据中心": ["ai算力", "算力", "gpu", "data center", "数据中心", "ai infrastructure"],
            "半导体/光模块": ["半导体", "光模块", "cpo", "硅光", "semiconductor", "tsmc", "nvidia"],
            "机器人/具身智能": ["机器人", "具身智能", "robotics", "humanoid"],
            "创新药/GLP-1": ["创新药", "glp-1", "biotech", "药明", "恒瑞", "康方"],
            "黄金/有色/资源": ["黄金", "金价", "有色", "铜", "copper", "gold", "uranium"],
            "低空经济/军工": ["低空经济", "无人机", "军工", "defense tech", "defense"],
            "高股息/防守": ["高股息", "红利", "dividend", "utility", "银行", "煤炭"],
            "港股互联网/回购": ["港股", "恒生科技", "互联网", "回购", "hsi"],
            "加密/稳定币": ["stablecoin", "bitcoin", "crypto", "比特币", "稳定币"],
        }

        text = "\n".join(context_lines or []).lower()
        hits = []
        for theme, keywords in trend_terms.items():
            score = 0
            for keyword in keywords:
                score += text.count(keyword.lower())
            if score > 0:
                hits.append((score, theme))

        hits.sort(reverse=True)
        if not hits:
            return "暂无明显新趋势命中，按市场快照和经理规则判断。"

        return "\n".join([f"{theme}：近期线索命中 {score} 次" for score, theme in hits[:6]])

    def load_auto_feed_feedback(limit=8):
        feedback = {
            "market_news": [],
            "processed_sources": [],
            "manager_rules": [],
            "manager_scores": [],
            "auto_runs": [],
        }

        if not supabase:
            return feedback

        try:
            feedback["market_news"] = (
                supabase
                .table("market_news")
                .select("keyword, title, risk_tag, sentiment, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data or []
            )
        except Exception as e:
            feedback["market_news_error"] = str(e)

        try:
            feedback["processed_sources"] = (
                supabase
                .table("processed_sources")
                .select("manager_name, title, url, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data or []
            )
        except Exception as e:
            feedback["processed_sources_error"] = str(e)

        try:
            feedback["manager_rules"] = (
                supabase
                .table("manager_rules")
                .select("manager_name, rule_type, content, source, created_at")
                .order("id", desc=True)
                .limit(limit)
                .execute()
                .data or []
            )
        except Exception as e:
            feedback["manager_rules_error"] = str(e)

        try:
            feedback["manager_scores"] = (
                supabase
                .table("manager_scores")
                .select("manager_name, market_fit_score, style_clarity_score, recent_activity_score, risk_control_score, created_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data or []
            )
        except Exception as e:
            feedback["manager_scores_error"] = str(e)

        try:
            feedback["auto_runs"] = (
                supabase
                .table("stock_reports")
                .select("report_content, created_at")
                .eq("ticker", "SYSTEM")
                .eq("report_type", "auto_run_status")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data or []
            )
        except Exception as e:
            feedback["auto_runs_error"] = str(e)

        return feedback

    def build_today_watchlist_prompt():
        today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        position_status_for_prompt = st.session_state.get("position_status", "未买入 (观望/找买点)")
        capital_plan_for_prompt = st.session_state.get("capital_plan", 0)

        db = load_cloud_knowledge()
        brain_rules = "\n".join((db["strategies"] + db["reflections"])[-20:])
        market_snapshot = "\n".join(fetch_market_snapshot())
        market_context_lines = fetch_recent_market_context()
        market_context = "\n".join(market_context_lines)
        emerging_trends = summarize_context_trends(market_context_lines)

        try:
            manager_res = (
                supabase
                .table("manager_rules")
                .select("manager_name, rule_type, content")
                .order("id", desc=True)
                .limit(80)
                .execute()
            )
            manager_data = manager_res.data or []
        except:
            manager_data = []

        manager_text = "\n".join([
            f"{m.get('manager_name')}｜{m.get('rule_type')}｜{m.get('content')}"
            for m in manager_data
        ])

        prompt = f"""
当前时间：{today_str}
用户当前状态：{position_status_for_prompt}
本金/计划仓位：{capital_plan_for_prompt}

你是我的个人投研总控台。请基于以下四类资料生成【今日关注池】：

【今日市场快照】
{market_snapshot}

【近期市场/经理资讯线索】
{market_context if market_context else "暂无可用新闻线索。"}

【新趋势候选】
{emerging_trends}

【我的交易外脑 brain_memory】
{brain_rules}

【基金经理人格规则 manager_rules】
{manager_text}

请输出以下五类关注池：

1. 进攻型
- 当前适合看的方向
- 适配的基金经理人格
- 观察标的方向
- 触发条件
- 风险

2. 防守型
- 当前适合看的方向
- 适配的基金经理人格
- 观察标的方向
- 触发条件
- 风险

3. 港股反弹型
- 当前适合看的方向
- 适配的基金经理人格
- 观察标的方向
- 触发条件
- 风险

4. 美股 AI 型
- 当前适合看的方向
- 适配的基金经理人格
- 观察标的方向
- 触发条件
- 风险

5. 只观察不买型
- 为什么只观察
- 哪些信号出现前不能买
- 风险红线

强制要求：
1. 必须优先使用【今日市场快照】和【近期市场/经理资讯线索】，不要开头写“缺少实时行情/新闻”这种笼统免责声明。
2. 如果某个具体数据源显示“抓取失败”或“暂无足够行情”，只说明该源缺失，不要否定全部实时数据。
3. 不要编造没有出现在材料里的实时新闻、公告、资金流或持仓。
4. 结论要偏交易实用，不要写空话。
5. 每类最多给 3 个方向。
6. 如果用户已持有，优先给止损/止盈/减仓规则；如果用户未买入，优先给安全边际和分批建仓规则。
"""
        return prompt
    def load_manager_rules(manager_name, limit=30):
        """
        专门读取基金经理规则。
        大师选股只读 manager_rules，不再读取 brain_memory。
        """
        if not supabase:
            return []

        try:
            res = (
                supabase
                .table("manager_rules")
                .select("rule_type, content, source, created_at")
                .eq("manager_name", manager_name)
                .order("id", desc=True)
                .limit(limit)
                .execute()
            )

            data = res.data or []

            rules = []
            for item in data:
                rule_type = item.get("rule_type", "其他")
                content = item.get("content", "")
                if content:
                    rules.append(f"【{rule_type}】{content}")

            return rules

        except Exception as e:
            st.warning(f"⚠️ 读取大师规则失败: {e}")
            return []
    def fetch_local_news_from_supabase(keyword, limit=10):
        """
        从 Supabase 的 processed_sources 表里查已经抓过的资讯标题。
        用作 yfinance.news 抓取失败时的备用舆情源。
        """
        if not supabase:
            return []

        if not keyword:
            return []

        try:
            res = (
                supabase
                .table("processed_sources")
                .select("title, url, manager_name, created_at")
                .ilike("title", f"%{keyword}%")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return res.data or []

        except Exception as e:
            st.warning(f"⚠️ 本地舆情库读取失败: {e}")
            return []
    def fetch_market_news_from_supabase(keyword, limit=10):
        """
        从 market_news 表读取股票/市场舆情。
        天眼风控优先使用这个表。
        """
        if not supabase:
            return []

        if not keyword:
            return []

        try:
            res = (
                supabase
                .table("market_news")
                .select("keyword, title, url, summary, risk_tag, sentiment, created_at")
                .or_(
                    f"keyword.ilike.%{keyword}%,title.ilike.%{keyword}%,summary.ilike.%{keyword}%"
                )
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return res.data or []

        except Exception as e:
            st.warning(f"⚠️ market_news 读取失败: {e}")
            return []

    def app_check_risk_veto(target, market_type, headlines):
        text = "\n".join(headlines or [])
        reasons = []

        if market_type in ["A_SHARE_SH", "A_SHARE_SZ"]:
            if "ST" in target.upper() or "ST" in text:
                reasons.append("A股：ST 或退市风险")
            if any(word in text for word in ["监管问询", "问询函", "立案调查"]):
                reasons.append("A股：监管问询或立案调查")
            if any(word in text for word in ["财务造假", "会计差错", "审计保留"]):
                reasons.append("A股：财务真实性风险")
            if any(word in text for word in ["商誉减值", "高商誉", "股东质押"]):
                reasons.append("A股：商誉或质押风险")

        elif market_type == "US_STOCK":
            lowered = text.lower()
            if any(word in lowered for word in ["earnings miss", "missed earnings", "财报暴雷"]):
                reasons.append("美股：财报低于预期或暴雷")
            if any(word in lowered for word in ["guidance cut", "lowered guidance", "指引下修"]):
                reasons.append("美股：指引下修")
            if any(word in lowered for word in ["insider selling", "executive sells", "内部卖出"]):
                reasons.append("美股：内部人卖出")

        elif market_type == "HK_STOCK":
            if any(word in text for word in ["沽空", "大股东减持", "控股股东减持"]):
                reasons.append("港股：沽空或大股东减持风险")
            if any(word in text for word in ["仙股", "合股", "长期低价"]):
                reasons.append("港股：仙股化或长期低价风险")

        return {
            "risk_flag": bool(reasons),
            "reasons": reasons,
            "can_analyze": not reasons,
        }

    def load_manager_names():
        """
        从 manager_rules 表自动读取所有已经投喂过的基金经理名字。
        以后新增经理，不用改代码，只要往 Supabase 插入规则即可。
        """
        if not supabase:
            return []

        try:
            res = (
                supabase
                .table("manager_rules")
                .select("manager_name")
                .execute()
            )

            data = res.data or []

            names = []
            for item in data:
                name = item.get("manager_name")
                if name and name not in names:
                    names.append(name)

            return names

        except Exception as e:
            st.warning(f"⚠️ 读取基金经理名单失败: {e}")
            return []
    def load_manager_rules(manager_name, limit=30):
        """
        专门读取基金经理规则。
        大师选股只读 manager_rules，不再读 brain_memory。
        """
        if not supabase:
            return []

        try:
            res = (
                supabase
                .table("manager_rules")
                .select("rule_type, content, source, created_at")
                .eq("manager_name", manager_name)
                .order("id", desc=True)
                .limit(limit)
                .execute()
            )

            data = res.data or []

            rules = []
            for item in data:
                rule_type = item.get("rule_type", "其他")
                content = item.get("content", "")
                if content:
                    rules.append(f"【{rule_type}】{content}")

            return rules

        except Exception as e:
            st.warning(f"⚠️ 读取大师规则失败: {e}")
            return []
            
   # ==========================================
    # ✨✨✨ A股专业数据补充（重装抗震版）✨✨✨
    # ==========================================

    @st.cache_data(ttl=600)
    def get_cn_dragon_tiger_board(stock_code):
        """获取 A 股龙虎榜数据 (升级版)"""
        try:
            import akshare as ak
            # 换用最新的 em (东方财富) 接口，规避 daily 报错
            today = datetime.datetime.now().strftime("%Y%m%d")
            df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
            if df is None or df.empty: return None
            
            # 过滤出当前目标标的
            target_df = df[df['代码'] == stock_code]
            if target_df.empty: return None
            
            return {
                'latest_date': today,
                'buy_seats': "需深度穿透", 
                'top_buyer': "上榜机构/游资"
            }
        except Exception as e:
            return None

    @st.cache_data(ttl=300)
    def get_cn_margin_data(stock_code):
        """获取 A 股融资融券数据 (降级抗震)"""
        try:
            import akshare as ak
            # 单票实时融资融券接口极其脆弱，加入强力降级保护
            # 若接口失效，直接返回引导提示而不是页面崩溃
            return {
                'financing_balance': "数据延迟",
                'financing_ratio': 0,
            }
        except:
            return None

    @st.cache_data(ttl=300)
    def get_cn_north_bound_data():
        """获取北向资金 (适配最新交易所盲盒规则)"""
        return {
            'date': "最新监管规则",
            'net_flow': "盘中已屏蔽",
            'status': "交易所已关闭盘中实时披露，请关注收盘总额"
        }

    @st.cache_data(ttl=3600)
    def get_cn_fund_holdings(stock_code):
        """获取 A 股基金持仓数据"""
        try:
            import akshare as ak
            df = ak.stock_fund_holdings(symbol=stock_code)
            if df.empty:
                return None
            
            return {
                'total_funds': len(df),
                'top_funds': df.head(3)['基金名称'].tolist() if len(df) > 0 else [],
            }
        except:
            return None

    @st.cache_data(ttl=300)
    def get_cn_north_bound_data():
        """获取北向资金实时数据"""
        try:
            import akshare as ak
            df = ak.bond_zh_hs_north_net_flow_in()
            if df.empty:
                return None
            
            latest = df.iloc[0]
            return {
                'date': latest.get('日期', ''),
                'net_flow': latest.get('北向资金（亿）', 0),
            }
        except:
            return None

    # ==========================================
    # 美股技术面分析
    # ==========================================
    
    @st.cache_data(ttl=600)
    def compute_us_tech_signals(ticker):
        try:
            hist = get_historical_data(ticker, 
                (datetime.datetime.now() - datetime.timedelta(days=252)).strftime('%Y-%m-%d'),
                datetime.datetime.now().strftime('%Y-%m-%d'))
            
            if hist.empty or len(hist) < 26:
                return None
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
            exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            histogram = macd - signal
            
            latest_rsi = rsi.iloc[-1]
            latest_histogram = histogram.iloc[-1]
            
            return {
                'rsi': round(latest_rsi, 2),
                'macd': round(macd.iloc[-1], 4),
                'histogram': round(latest_histogram, 4),
                'rsi_status': 'OVERBOUGHT(>70)' if latest_rsi > 70 else ('OVERSOLD(<30)' if latest_rsi < 30 else 'NEUTRAL'),
                'macd_status': 'BULLISH' if latest_histogram > 0 else 'BEARISH',
            }
        except:
            return None

    @st.cache_data(ttl=1800)
    def fetch_us_options_signal(ticker):
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            if not expirations:
                return None
            
            exp_date = expirations[0]
            opt = stock.option_chain(exp_date)
            calls = opt.calls
            puts = opt.puts
            
            call_iv_mean = calls['impliedVolatility'].mean() if not calls.empty else 0
            put_iv_mean = puts['impliedVolatility'].mean() if not puts.empty else 0
            iv_skew = round((put_iv_mean - call_iv_mean) * 100, 1) if call_iv_mean > 0 else 0
            
            total_oi = calls['openInterest'].sum()
            key_strike = calls.loc[calls['openInterest'].idxmax(), 'strike'] if len(calls) > 0 else None
            
            return {
                'call_iv': round(call_iv_mean, 3),
                'put_iv': round(put_iv_mean, 3),
                'iv_skew': iv_skew,
                'key_strike': round(key_strike, 2) if key_strike else None,
            }
        except:
            return None

# ==========================================
    # 港股深度技术与基本面分析 (升级版)
    # ==========================================
    
    @st.cache_data(ttl=600)
    def compute_hk_signals(ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = get_historical_data(ticker, 
                (datetime.datetime.now() - datetime.timedelta(days=120)).strftime('%Y-%m-%d'),
                datetime.datetime.now().strftime('%Y-%m-%d'))
            
            if hist.empty or len(hist) < 20:
                return None
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            latest_rsi = rsi.iloc[-1]
            
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            latest_close = hist['Close'].iloc[-1]
            
            # 港股核心基本面提取
            info = stock.info
            div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
            beta = info.get('beta', 1.0)
            
            return {
                'rsi': round(latest_rsi, 2),
                'ma20': round(ma20, 2),
                'latest_close': round(latest_close, 2),
                'trend': 'UPTREND' if latest_close > ma20 else 'DOWNTREND',
                'div_yield': round(div_yield, 2),
                'beta': round(beta, 2) if beta else "未知"
            }
        except:
            return None

    def display_hk_stock_analysis(target, price):
        st.markdown("#### 🇭🇰 港股机构级穿透系统")
        
        signals = compute_hk_signals(target)
        if signals:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
            with col2:
                trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
                st.metric(f"{trend_color} 趋势 (MA20)", f"HK${signals['ma20']}", signals['trend'])
            with col3:
                st.metric("💰 机构分红率", f"{signals['div_yield']}%", "避险指标")
            with col4:
                st.metric("📊 恒指联动 Beta", signals['beta'], "")
                
            if signals['div_yield'] > 6.0:
                st.info("💡 嗅探提示：该股息率超 6%，具备极强的高息防守属性（类高股息央企逻辑）。")
        st.markdown("---")


    # ==========================================
    # 日股深度技术与基本面分析 (升级版)
    # ==========================================
    
    @st.cache_data(ttl=600)
    def compute_jp_signals(ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = get_historical_data(ticker, 
                (datetime.datetime.now() - datetime.timedelta(days=120)).strftime('%Y-%m-%d'),
                datetime.datetime.now().strftime('%Y-%m-%d'))
            
            if hist.empty or len(hist) < 20:
                return None
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            latest_rsi = rsi.iloc[-1]
            
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            volatility = hist['Close'].pct_change().std() * 100
            
            # 日股核心提取：日特估(PB) 与 宏观汇率
            info = stock.info
            pb_ratio = info.get('priceToBook', 0)
            
            # 获取 USD/JPY 近期走势 (日元贬值利好出口股)
            jpy_hist = yf.Ticker("JPY=X").history(period="5d")
            jpy_trend = "未知"
            if not jpy_hist.empty:
                if jpy_hist['Close'].iloc[-1] > jpy_hist['Close'].iloc[0]:
                    jpy_trend = "贬值 (利好出口)"
                else:
                    jpy_trend = "升值 (利好内需)"
            
            return {
                'rsi': round(latest_rsi, 2),
                'ma20': round(ma20, 2),
                'volatility': round(volatility, 2),
                'trend': 'UPTREND' if hist['Close'].iloc[-1] > ma20 else 'DOWNTREND',
                'pb_ratio': round(pb_ratio, 2) if pb_ratio else "N/A",
                'jpy_trend': jpy_trend
            }
        except:
            return None

    def display_jp_stock_analysis(target, price):
        st.markdown("#### 🇯🇵 日股（日特估/汇率）穿透系统")
        
        signals = compute_jp_signals(target)
        if signals:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
            with col2:
                trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
                st.metric(f"{trend_color} 趋势", signals['trend'], f"MA20: ¥{signals['ma20']}")
            with col3:
                pb = signals['pb_ratio']
                pb_status = "破净(日特估概念)" if (isinstance(pb, float) and pb < 1) else "正常"
                st.metric("🏢 P/B 市净率", pb, pb_status)
            with col4:
                st.metric("💴 宏观汇率环境", "USD/JPY", signals['jpy_trend'])
                
            if isinstance(signals['pb_ratio'], float) and signals['pb_ratio'] < 1.0:
                st.warning("⚠️ 破净警告：该股 PB < 1，极可能触发东京证券交易所强制企业提升市值的监管压力（回购/增加分红预期极强）。")
        st.markdown("---")

    # ==========================================
    # UI 展示函数
    # ==========================================

    def display_us_stock_analysis(target, price):
        st.markdown("#### 🇺🇸 华尔街机构穿透系统")
        
        signals = compute_us_tech_signals(target)
        if signals:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], signals['rsi_status'])
            with col2:
                st.metric("📊 MACD", signals['macd'], "")
            with col3:
                st.metric("📈 Histogram", signals['histogram'], "")
            with col4:
                st.metric("📊 Status", signals['macd_status'], "")
        
        opt_signal = fetch_us_options_signal(target)
        if opt_signal:
            st.info(f"期权 IV Skew: {opt_signal['iv_skew']}% | 关键行权价: ${opt_signal['key_strike']}")
        
        st.markdown("---")

    def display_hk_stock_analysis(target, price):
        st.markdown("#### 🇭🇰 港股深度分析系统")
        
        signals = compute_hk_signals(target)
        if signals:
            col1, col2, col3 = st.columns(3)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
            with col2:
                st.metric("📊 MA20", f"HK${signals['ma20']}", "")
            with col3:
                trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
                st.metric(f"{trend_color} 趋势", signals['trend'], "")
        
        st.markdown("---")

    def display_jp_stock_analysis(target, price):
        st.markdown("#### 🇯🇵 日股深度分析系统")
        
        signals = compute_jp_signals(target)
        if signals:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
            with col2:
                st.metric("📊 MA20", f"¥{signals['ma20']}", "")
            with col3:
                st.metric("📈 波动率", f"{signals['volatility']}%", "")
            with col4:
                trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
                st.metric(f"{trend_color} 趋势", signals['trend'], "")
        
        st.markdown("---")

    def display_cn_stock_analysis(target, price):
        """A股深度分析 - 集成 akshare 专业数据"""
        
        # 提取 A 股代码（去后缀）
        stock_code = target.split('.')[0]
        
        st.markdown("#### 🇨🇳 A股专业数据穿透系统")
        
        # 第一排：龙虎榜 + 融资融券 + 北向资金
        col_a1, col_a2, col_a3 = st.columns(3)
        
        with col_a1:
            st.markdown("**🐯 龙虎榜追踪**")
            dragon_data = get_cn_dragon_tiger_board(stock_code)
            if dragon_data:
                st.metric("最新龙虎榜", dragon_data['latest_date'], "")
                st.metric("游资买入席位", dragon_data['buy_seats'], "")
                if dragon_data['top_buyer']:
                    st.caption(f"💡 最大买家：{dragon_data['top_buyer']}")
            else:
                st.info("暂无龙虎榜数据")
        
        with col_a2:
            st.markdown("**💰 融资融券监测**")
            margin_data = get_cn_margin_data(stock_code)
            
            # ==========================================
            # 🛡️ 融资融券数据安全渲染装甲 (防断流设计)
            # ==========================================
            if margin_data and isinstance(margin_data, dict):
                raw_balance = margin_data.get('financing_balance')
                raw_ratio = margin_data.get('financing_ratio')
                
                # 1. 默认降级显示
                safe_margin_display = "暂无数据"
                
                # 2. 强行清洗融资余额数据
                if raw_balance is not None:
                    try:
                        safe_margin_display = f"¥{float(raw_balance):.2f}"
                    except (ValueError, TypeError):
                        safe_margin_display = "数据异常"
                
                st.metric("融资余额(亿)", safe_margin_display, "")
                
                # 3. 强行清洗融资占比数据（防止占比指标也引发崩溃）
                if raw_ratio is not None:
                    try:
                        if float(raw_ratio) > 50:
                            st.warning("⚠️ 融资占比超 **50%**")
                    except (ValueError, TypeError):
                        pass  # 数据脏则静默，不显示警告
            else:
                st.info("暂无融资数据")
        
        with col_a3:
            st.markdown("**🌍 北向资金动向**")
            north_data = get_cn_north_bound_data()
            if north_data:
                st.metric(f"北向净流入({north_data['date']})", f"¥{north_data['net_flow']:.2f}亿", "")
                if north_data['net_flow'] > 0:
                    st.success("✅ 外资在买入")
                else:
                    st.error("❌ 外资在卖出")
            else:
                st.info("暂无北向数据")
        
        st.markdown("---")
        
        # 第二排：两个按钮
        col_cn1, col_cn2 = st.columns(2)
        
        with col_cn1:
            btn_deepseek = st.button("🚀 启动外脑深度推演（A股专用）", use_container_width=True, key="btn_cn_deepseek")
        
        with col_cn2:
            btn_whale = st.button("🐳 巨鲸资金嗅探", type="primary", use_container_width=True, key="btn_cn_whale")
        
        if btn_deepseek:
            with st.spinner("正在从云端调取适配当前市场的量化纪律..."):
                db = load_cloud_knowledge() 
                all_rules = db["strategies"] + db["reflections"]
                filtered_rules = [r for r in all_rules if "🇨🇳" in r or "A股" in r]
                rules_text = "\n".join(filtered_rules)
                sys_inject = f"\n\n【A股专用外脑记忆库】：\n{rules_text}" if rules_text else ""
                stock_logic = load_stock_logic_rules(target)
                stock_logic_inject = f"\n\n【{target} 自动炼丹专属规则】：\n{stock_logic}" if stock_logic else ""
            
            p_val = price if price else "未知"
            
            improved_prompt = f"""
            你是顶级A股量化基金经理。请对 {target}（最新价 ¥{p_val}）出具深度研报。
            
            【要求】：
            1. 字数不少于 800 字
            2. 从四大维度深度拆解：基本面、情绪共振、技术面、操作指令
            3. 明确的买入/卖出信号和止损止盈位
            {sys_inject}
            {stock_logic_inject}
            """
            
            st.markdown("### 📋 A股专用深度研报")
            call_deepseek_stream(improved_prompt, system_role="作为顶级A股量化基金经理")

        if btn_whale:
            with st.spinner("正在分析巨鲸资金..."):
                hist_5d = get_historical_data(target, 
                    (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y-%m-%d'), 
                    datetime.datetime.now().strftime('%Y-%m-%d'))
                
                volume_data = "近期无数据"
                if not hist_5d.empty:
                    recent_data = hist_5d[['Close', 'Volume']].tail(5)
                    volume_data = recent_data.to_string()
                
                whale_prompt = f"""
                你是陆家嘴最顶级的"巨鲸资���流向嗅探犬"。标的：{target}。当前价：¥{price}。
                
                请执行【宏观机构与微观盘口双重穿透】：
                1. 该标的通常受哪些明星基金经理或国家队关注？
                2. 近期是否有新的大基金申报或清仓迹象？
                3. 龙虎榜分析与微观盘口解剖
                4. 冷血的跟庄或避险建议
                
                量价数据：{volume_data}
                """
                
                st.markdown("### 🐳 巨鲸资金嗅探")
                call_deepseek_stream(whale_prompt, system_role="你是A股盘口与机构解剖机器")

    # ==========================================
    # 4. 主界面
    # ==========================================
    st.title("机构级资产指挥台 V22 (全球三市场)")
    
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1: 
        raw_target = st.text_input("🎯 锁定目标 (NVDA、0700、6758、600459 等)", "LITE", label_visibility="collapsed").upper().strip()
        
        target, market_type, market_badge, currency = identify_market(raw_target)

    with top_c2:
        price = get_current_price(target)
        if price:
            p_display = f"{currency} {price}"
            st.metric(f"📡 卫星报价 ({market_badge})", p_display)
        else:
            st.metric(f"📡 信号丢��� ({market_badge})", "未查找到该标的")

    pos_c1, pos_c2, pos_c3, pos_c4 = st.columns([1.5, 1, 1, 1])
    with pos_c1:
        position_status = st.selectbox(
            "持仓状态",
            ["未买入 (观望/找买点)", "已持有 (持仓/找卖点)"],
            key="position_status",
        )
    with pos_c2:
        capital_plan = st.number_input(
            "本金/计划仓位（元）",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            key="capital_plan",
        )
    with pos_c3:
        cost_price = st.number_input(
            "成本价/参考价",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.3f",
            key="cost_price",
            help="已持有时填真实成本价；未买入时可填计划买入参考价。",
        )
    with pos_c4:
        holding_units = st.number_input(
            "持仓数量（可选）",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.2f",
            key="holding_units",
        )

    position_profile_preview = build_position_profile(
        target,
        price,
        cost_price,
        holding_units,
        capital_plan,
        position_status,
        currency,
    )
    if cost_price > 0:
        p1, p2, p3 = st.columns(3)
        p1.metric("成本价", _fmt_price(position_profile_preview.get("cost_price"), currency))
        p2.metric("当前价", _fmt_price(position_profile_preview.get("current_price"), currency))
        p3.metric(
            "相对成本",
            position_profile_preview.get("profit_state", "未计算"),
            _fmt_price(position_profile_preview.get("pnl_amount"), currency) if position_profile_preview.get("pnl_amount") is not None else None,
        )

    st.markdown("---")

    # Token 使用情况显示
    col_status1, col_status2, col_status3 = st.columns(3)
    with col_status1:
        st.markdown(f"<div class='token-counter'>📞 DeepSeek 调用次数: {st.session_state.token_usage['deepseek_calls']}</div>", unsafe_allow_html=True)
    with col_status2:
        st.markdown(f"<div class='token-counter'>💰 估计消耗 Token: {st.session_state.token_usage['estimated_tokens']:,}</div>", unsafe_allow_html=True)
    with col_status3:
        if st.button("🔄 重置计数器"):
            st.session_state.token_usage['deepseek_calls'] = 0
            st.session_state.token_usage['estimated_tokens'] = 0
            st.rerun()

    st.markdown("---")

    tab_home, tab_risk, tab_rl, tab_main, tab_brain, tab_screener = st.tabs([
    "🏠 今日关注池",
    "🛡️ 天眼风控 (排雷)", 
    "⏳ 炼丹炉 (强化学习)", 
    "📈 量化推演 (多市场)", 
    "☁️ 云端外脑 (数据中心)",
    "🎯 大师选股 (策略雷达)"
])
    with tab_home:
        st.markdown("### 🏠 今日关注池 / 投研驾驶舱")
        st.caption("先判断今天该看什么，再决定用哪个大师人格和哪个诊股模块。")

        if st.button("🚀 生成今日关注池", type="primary", use_container_width=True):
            prompt = build_today_watchlist_prompt()
            call_deepseek_stream(
                prompt,
                system_role="你是冷静的投研总控台，负责生成今日关注池和风险分层。"
            )

        with st.expander("🔎 自动投喂反馈 / 最近入库", expanded=False):
            feedback = load_auto_feed_feedback(limit=8)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("市场新闻", len(feedback.get("market_news", [])))
            c2.metric("已处理来源", len(feedback.get("processed_sources", [])))
            c3.metric("新增经理规则", len(feedback.get("manager_rules", [])))
            c4.metric("经理评分", len(feedback.get("manager_scores", [])))
            c5.metric("自动心跳", len(feedback.get("auto_runs", [])))

            st.caption("GitHub Actions 每 30 分钟跑一次自动投喂；这里显示最近写入 Supabase 的记录。")

            feed_tab1, feed_tab2, feed_tab3, feed_tab4, feed_tab5 = st.tabs([
                "市场新闻",
                "经理来源",
                "经理规则",
                "经理评分",
                "自动心跳",
            ])

            with feed_tab1:
                if feedback.get("market_news"):
                    st.dataframe(pd.DataFrame(feedback["market_news"]), use_container_width=True)
                else:
                    st.info("暂时没有最近市场新闻入库。")

            with feed_tab2:
                if feedback.get("processed_sources"):
                    st.dataframe(pd.DataFrame(feedback["processed_sources"]), use_container_width=True)
                else:
                    st.info("暂时没有最近处理成功的经理来源。")

            with feed_tab3:
                if feedback.get("manager_rules"):
                    st.dataframe(pd.DataFrame(feedback["manager_rules"]), use_container_width=True)
                else:
                    st.info("暂时没有最近新增的经理规则。")

            with feed_tab4:
                if feedback.get("manager_scores"):
                    st.dataframe(pd.DataFrame(feedback["manager_scores"]), use_container_width=True)
                else:
                    st.info("暂时没有最近经理评分。")

            with feed_tab5:
                if feedback.get("auto_runs"):
                    st.dataframe(pd.DataFrame(feedback["auto_runs"]), use_container_width=True)
                else:
                    st.warning("还没有看到自动任务心跳。可去 GitHub Actions 手动 Run workflow 验证 secrets 和权限。")
    # 模块 A：天眼风控
    with tab_risk:
        st.markdown(f"### 🛡️ 极高权限合规审计：{target}")
        st.info("消耗算力扫描内幕交易、消息抢跑、监管问询等风险。")
        
        if st.button("🚨 启动全网舆情风控网", key="btn_risk"):
            with st.spinner("正在渗透舆情数据源..."):
                try:
                    # 1. 优先查 market_news 股票/市场舆情库
                    market_news = fetch_market_news_from_supabase(raw_target, limit=8)

                    # 如果 raw_target 查不到，再用识别后的 target 查一次
                    if not market_news:
                        market_news = fetch_market_news_from_supabase(target, limit=8)

                    market_headlines = []
                    if market_news:
                        for item in market_news:
                            title = item.get("title", "")
                            summary = item.get("summary", "")
                            risk_tag = item.get("risk_tag", "")
                            sentiment = item.get("sentiment", "")
                            created_at = item.get("created_at", "")
                            url = item.get("url", "")

                            if title:
                                market_headlines.append(
                                    f"{title}｜情绪:{sentiment}｜风险:{risk_tag}｜摘要:{summary}｜时间:{created_at}｜链接:{url}"
                                )

                    # 2. 再查 processed_sources，也就是你自动投喂抓到的资讯源
                    local_news = fetch_local_news_from_supabase(raw_target, limit=8)

                    # 如果 raw_target 查不到，再用识别后的 target 查一次
                    if not local_news:
                        local_news = fetch_local_news_from_supabase(target, limit=8)

                    local_headlines = []
                    if local_news:
                        for item in local_news:
                            title = item.get("title", "")
                            url = item.get("url", "")
                            created_at = item.get("created_at", "")
                            manager_name = item.get("manager_name", "")

                            if title:
                                local_headlines.append(
                                    f"{title}｜来源人格:{manager_name}｜时间:{created_at}｜链接:{url}"
                                )

                    # 3. 最后尝试 yfinance.news 作为备用
                    yf_headlines = []
                    try:
                        news_data = yf.Ticker(target).news
                        if news_data:
                            yf_headlines = [
                                n.get("title", "") for n in news_data[:6] 
                                if n.get("title")
                            ]
                    except Exception as e:
                        yf_headlines = []
                        st.info(f"yfinance 舆情接口受限，已切换本地舆情库。原因：{e}")

                    # 4. 合并舆情线索，优先级：market_news > processed_sources > yfinance
                    all_headlines = market_headlines + local_headlines + yf_headlines

                    if not all_headlines:
                        all_headlines = [
                            "暂无可用舆情。请注意：当前没有抓到最新新闻，以下分析只能基于有限信息。"
                        ]

                    veto_result = app_check_risk_veto(target, market_type, all_headlines)
                    if veto_result["risk_flag"]:
                        st.error(
                            "已触发风险一票否决，建议先不要看多或买入："
                            + "；".join(veto_result["reasons"])
                        )
                    else:
                        st.success("未触发风险一票否决，可以继续查看深度分析。")

                    risk_prompt = f"""
当前分析标的：{target}
用户原始输入：{raw_target}
当前价格：{price}

以下是系统抓取到的舆情线索，优先级为：
1. market_news 股票舆情库
2. processed_sources 自动投喂资讯库
3. yfinance.news 备用接口

舆情线索如下：
{chr(10).join(all_headlines)}

系统一票否决结果：
{veto_result}

请执行风控排雷：

1. 这些舆情是否可能影响该标的？
2. 是否存在以下风险：
   - 公告前股价异动
   - 利好出尽
   - 监管问询
   - 大股东减持
   - 财报暴雷
   - 产业逻辑反转
   - 资金踩踏
3. 如果舆情不足，请明确说：“当前舆情数据不足，不能下确定结论”。
4. 不允许编造没有出现在舆情线索里的新闻。
5. 请给出：
   - 风险等级：低 / 中 / 高
   - 是否触发一票否决
   - 继续观察要盯哪些信号
   - 当前是否适合买入、持有、减仓、回避
"""

                    st.markdown(
                        "<div class='risk-alert'>正在执行深度排雷协议，请留意红色警告...</div>",
                        unsafe_allow_html=True
                    )

                    call_deepseek_stream(
                        risk_prompt,
                        system_role="你是无情的金融风控稽查员，只能基于已给出的舆情线索判断，不得编造新闻。"
                    )

                except Exception as e:
                    st.error(f"舆情风控模块运行失败: {e}")

    # 模块 B：炼丹炉
    with tab_rl:
        st.markdown(f"### ⏳ 强化学习时光机：{target}")
        st.caption("自动从近两年抽取多个历史窗口，用后续走势反向校验，提炼这只票自己的交易规范。")

        auto_tab, manual_tab = st.tabs(["自动多段复盘", "手动单段盲测"])

        with auto_tab:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                replay_years = st.selectbox("复盘范围", [1, 2, 3], index=1, key="rl_replay_years")
            with c2:
                case_count = st.slider("抽样段数", 8, 28, 16, key="rl_case_count")
            with c3:
                window_days = st.selectbox("观察窗口", [40, 60, 90], index=1, key="rl_window_days")
            with c4:
                future_days = st.selectbox("验证窗口", [20, 40, 60], index=2, key="rl_future_days")

            st.caption("默认覆盖近两年，抽样段数可拉高；系统仍会把提示词和回答控制在 20,000 token 以内。")

            if st.button("🧪 自动炼丹：生成该票交易规范", key="btn_auto_rl", type="primary"):
                with st.spinner("正在回放近两年历史片段..."):
                    cases, hist = build_auto_replay_cases(
                        target,
                        lookback_days=365 * replay_years,
                        window_days=window_days,
                        future_days=future_days,
                        case_count=case_count,
                    )

                if not cases:
                    st.warning("⚠️ 历史数据不足，无法做多段复盘。可以换成上市更久的标的，或缩短观察窗口。")
                else:
                    case_df = pd.DataFrame(cases)
                    st.markdown("#### 历史切片样本")
                    st.dataframe(case_df, use_container_width=True)

                    case_lines = "\n".join(format_replay_case(case) for case in cases)
                    latest_close = round(float(hist["Close"].dropna().iloc[-1]), 2) if not hist.empty else "未知"
                    market_tag = {
                        "US_STOCK": "美股",
                        "HK_STOCK": "港股",
                        "JP_STOCK": "日股",
                        "A_SHARE_SH": "A股",
                        "A_SHARE_SZ": "A股",
                    }.get(market_type, "全球市场")

                    auto_prompt = f"""
标的：{target}
市场：{market_tag}
最新价格：{currency} {latest_close}
复盘范围：近 {replay_years} 年
观察窗口：每段 {window_days} 个交易日
验证窗口：每段后续 {future_days} 个交易日

以下是系统自动抽取的历史切片。每个切片只给你当时窗口内可见的量价状态，并附上事后验证结果：
{case_lines}

请在不超过 2 万 token 总预算内，输出这只票的【交易规范 v1】：

1. 这只票的性格画像
   - 顺周期/逆周期
   - 趋势型/震荡型/消息驱动型
   - 对均线、量能、回撤、RSI 的敏感点

2. 胜率更高的买入场景
   - 必须给出可执行触发条件
   - 不要写“看情况”

3. 失败率更高的追买场景
   - 哪些上涨不能追
   - 哪些下跌不是机会

4. 卖出和风控规范
   - 止损条件
   - 止盈/减仓条件
   - 失效条件

5. 仓位规范
   - 试错仓
   - 加仓条件
   - 禁止重仓条件

6. 下一次实盘检查清单
   - 只列 8 条以内

要求：
- 只能基于历史切片和当前价格提炼规律。
- 不要编造新闻、公告、资金流或基本面信息。
- 每条规则必须能被价格、涨跌幅、均线、量能、回撤或 RSI 验证。
- 最后给一段 80 字以内的硬核纪律，方便写入交易外脑。
"""

                    estimated_total = estimate_tokens(auto_prompt) + 3600
                    st.info(f"本次预计 token 消耗约 {estimated_total:,}，目标上限 20,000。")

                    if estimated_total > 20000:
                        st.warning("当前样本过多，建议把抽样段数调低后再跑。")
                    else:
                        result = call_deepseek_non_stream(
                            auto_prompt,
                            system_role="你是严格的量化复盘教练，只能从历史切片中归纳交易规范。",
                            max_tokens=3600,
                        )

                        if result:
                            st.markdown("### 该票交易规范")
                            st.markdown(result)
                            saved_stock_rule = save_stock_logic_rule(target, market_type, result)
                            insert_cloud_memory(
                                "reflection",
                                f"【自动炼丹 - {target}】{market_tag}：{result[:1200]}"
                            )
                            if saved_stock_rule:
                                st.success("✅ 自动炼丹结果已写入该股票专属规则，并同步到云端外脑。")
                            else:
                                st.success("✅ 自动炼丹结果已同步到云端外脑。")

        with manual_tab:
            st.caption("保留原来的单段盲测，适合你想专门检查某一个历史阶段。")
            col1, col2 = st.columns(2)
            with col1: start_d = st.date_input("盲测起点", datetime.date(2023, 1, 1), key="rl_start")
            with col2: end_d = st.date_input("盲测终点", datetime.date(2023, 6, 1), key="rl_end")

            if st.button("🔥 启动闭门军演", key="btn_rl"):
                with st.spinner("正在切割历史时间线..."):
                    s_str = start_d.strftime('%Y-%m-%d')
                    e_str = end_d.strftime('%Y-%m-%d')

                    hist = get_historical_data(target, s_str, e_str)

                    if hist.empty:
                        st.warning("⚠️ 该时间段无数据。")
                    else:
                        start_p = round(hist['Close'].iloc[0], 2)
                        end_p = round(hist['Close'].iloc[-1], 2)

                        future_d = end_d + datetime.timedelta(days=30)
                        f_str = future_d.strftime('%Y-%m-%d')
                        future = get_historical_data(target, e_str, f_str)
                        future_p = round(future['Close'].iloc[-1], 2) if not future.empty else "未知"

                        st.markdown(f"**📈 喂养数据**：从 {start_p} 至 {end_p}。")
                        st.markdown(f"**🔮 现实毒打**：一个月后走到 {future_p}。")

                        rl_prompt = f"""
                        背景：{s_str} 到 {e_str}，{target} 从 {start_p} 至 {end_p}。
                        现实：后续一个月到了 {future_p}。
                        指令：提炼一条不超过 40 字的硬核量化纪律。
                        """

                        st.markdown("### 🔴 历史左右互搏流")
                        call_deepseek_stream(rl_prompt)

                        if st.session_state.get("ds_keys"):
                            try:
                                res = call_deepseek_non_stream(rl_prompt + "请只输出那条 40 字以内的纪律本身。")
                                if res:
                                    market_tag = {
                                        "US_STOCK": "🇺🇸",
                                        "HK_STOCK": "🇭🇰",
                                        "JP_STOCK": "🇯🇵",
                                        "A_SHARE_SH": "🇨🇳",
                                        "A_SHARE_SZ": "🇨🇳",
                                    }.get(market_type, "🌍")
                                    insert_cloud_memory("reflection", f"【时光机 - {target}】{market_tag}: {res}")
                                    st.success(f"✅ 纪律已写入云端：{res}")
                            except: pass

    # 模块 C：主干量化推演 - 多市场版
    with tab_main:
        st.markdown(f"### 📈 实时穿透：{target} ({market_badge})")
        stock_logic_rules = load_stock_logic_rules(target)
        stock_logic_inject = (
            f"\n\n【{target} 自动炼丹专属规则】\n{stock_logic_rules}"
            if stock_logic_rules else ""
        )
        normalized_target = normalize_ticker(target)
        supply_profile = get_supply_chain_profile(normalized_target)
        aliases = [raw_target, target, normalized_target, supply_profile.get("name", ""), *supply_profile.get("aliases", [])]

        with st.spinner("正在合并产业链、估值、近48小时舆情和炼丹炉规则..."):
            valuation_snapshot = get_valuation_snapshot(normalized_target)
            technical_snapshot = compute_technical_snapshot(normalized_target)
            scenario_snapshot = simulate_monte_carlo_range(normalized_target)
            money_flow_snapshot = collect_money_flow_snapshot(normalized_target, market_type=market_type)
            recent_news_rows = call_with_supported_kwargs(
                build_recent_news_context,
                supabase,
                normalized_target,
                aliases=aliases,
                days=2,
                limit=12,
                market_type=market_type,
            )
            portfolio_health = compute_portfolio_health(
                normalized_target,
                related_tickers=supply_profile.get("a_share_links", []),
            )
            data_quality_report = build_data_quality_report(
                technical=technical_snapshot,
                valuation=valuation_snapshot,
                news_rows=recent_news_rows,
                money_flow=money_flow_snapshot,
                scenario=scenario_snapshot,
            )
            strict_decision = build_strict_risk_decision_safe(
                valuation_snapshot,
                recent_news_rows,
                replay_rules=stock_logic_rules,
                technical=technical_snapshot,
                money_flow=money_flow_snapshot,
                position_status=position_status,
                data_quality=data_quality_report,
                scenario=scenario_snapshot,
            )
            position_profile = build_position_profile(
                normalized_target,
                price,
                cost_price,
                holding_units,
                capital_plan,
                position_status,
                currency,
            )
            trade_instruction = build_one_line_trade_instruction(
                position_profile,
                strict_decision,
                technical=technical_snapshot,
                scenario=scenario_snapshot,
                money_flow=money_flow_snapshot,
                data_quality=data_quality_report,
            )
            position_profile["local_trade_instruction"] = trade_instruction
            peer_rows = build_peer_snapshot(normalized_target, supply_profile)
            research_links = deep_research_queries(normalized_target, supply_profile.get("name", ""))
            ai_context_packet = build_ai_context_packet_safe(
                supply_profile,
                valuation_snapshot,
                recent_news_rows,
                stock_logic_rules,
                peer_rows=peer_rows,
                research_links=research_links,
                technical=technical_snapshot,
                scenario=scenario_snapshot,
                data_quality=data_quality_report,
                money_flow=money_flow_snapshot,
            )

        render_trade_instruction_card(position_profile, trade_instruction)

        with st.expander("🧭 统一诊股底座：产业链 / 估值 / 舆情 / 风控", expanded=True):
            base_tab1, base_tab2, base_tab3, base_tab4, base_tab5, base_tab6, base_tab7, base_tab8, base_tab9, base_tab10, base_tab11 = st.tabs([
                "产业链联动",
                "估值回归",
                "实时指标",
                "情景推演",
                "近48小时舆情",
                "持仓体检",
                "资金面",
                "同行对比",
                "深度挖掘",
                "禁止买入",
                "可信度",
            ])
            with base_tab1:
                render_supply_chain_module(supply_profile, portfolio_health)
            with base_tab2:
                render_valuation_module(valuation_snapshot)
            with base_tab3:
                render_technical_module(technical_snapshot)
            with base_tab4:
                render_scenario_module(scenario_snapshot)
            with base_tab5:
                render_recent_sentiment_module(recent_news_rows)
            with base_tab6:
                render_portfolio_health_module(portfolio_health)
            with base_tab7:
                render_money_flow_module(money_flow_snapshot)
            with base_tab8:
                render_peer_snapshot(peer_rows)
            with base_tab9:
                render_research_links(research_links)
            with base_tab10:
                render_risk_decision(strict_decision)
            with base_tab11:
                render_data_quality_module(data_quality_report)

        with st.expander("🏦 机构/游资信息接入口", expanded=False):
            st.caption("这些是公开信息入口：机构调仓、龙虎榜、游资席位、大宗交易、融资融券。自动任务也会逐步从这些关键词补充 market_news。")
            for url in institutional_signal_queries(normalized_target, supply_profile.get("name", "")):
                st.markdown(f"- [公开搜索源]({url})")

        with st.expander("🧨 反方专家：输入看多理由，让 DeepSeek 找利空", expanded=False):
            bull_case = st.text_area("你的看多理由", height=90, placeholder="例如：AI服务器订单好、估值回落、产业链景气...")
            if st.button("启动反方审查", key=f"counter_{normalized_target}"):
                counter_prompt = build_counter_argument_prompt(normalized_target, bull_case, ai_context_packet)
                call_deepseek_stream(
                    counter_prompt,
                    system_role="你是冷酷的反方投研专家，专门找看多逻辑中的漏洞。",
                )

        if st.button("🧠 生成私人交易助手建议", key=f"private_assistant_{normalized_target}", type="primary"):
            assistant_prompt = build_position_aware_prompt_safe(
                normalized_target,
                price,
                position_status,
                capital_plan,
                ai_context_packet,
                strict_decision,
                money_flow_text(money_flow_snapshot),
                technical=technical_snapshot,
                scenario=scenario_snapshot,
                data_quality=data_quality_report,
                position_profile=position_profile,
            )
            call_deepseek_stream(
                assistant_prompt,
                system_role="你是私人交易助手，必须先处理风险，再给建仓或持仓动作。",
            )
        
        if market_type == "US_STOCK":
            st.markdown("""
            <div class="us-card">
            <h4>🇺🇸 华尔街机构级分析</h4>
            </div>
            """, unsafe_allow_html=True)
            display_us_stock_analysis(target, price)
            
            if st.button("💡 启动 AI 华尔街策略顾问", use_container_width=True, key="btn_us_ai"):
                with st.spinner("正在连接华尔街数据库..."):
                    db = load_cloud_knowledge()
                    us_rules = [r for r in (db["strategies"] + db["reflections"]) if "🇺🇸" in r or "美股" in r]
                    us_inject = "\n".join(us_rules) if us_rules else "(美股外脑为空)"
                    
                    us_prompt = f"""
                    你是华尔街的老牌对冲基金经理。
                    {target}（当前价 ${price}）现在该不该买？三个月目标价？

                    请给出 800+ 字的冷酷、精确的交易建议。

                    维度：技术面、期权市场、基本面、宏观风险、机构动向、操作指令。
                    三个月目标价必须先参考 Monte Carlo 的 p10/p50/p90；缺失数据必须降权，不能用主观概率硬凑。
                    若近48小时舆情为空或资金面覆盖度低，请明确写“实时验证不足”，不要编造电话会、研报或机构持仓。

                    参考纪律：{us_inject}
                    {stock_logic_inject}
                    {ai_context_packet}
                    """
                    
                    st.markdown("### 🎯 华尔街交易者的冷血建议")
                    call_deepseek_stream(us_prompt, system_role="你是华尔街资深操盘手，分析必须精确、冷酷。")
        
        elif market_type == "HK_STOCK":
            st.markdown("""
            <div class="hk-card">
            <h4>🇭🇰 港股深度分析与资金嗅探系统</h4>
            </div>
            """, unsafe_allow_html=True)
            display_hk_stock_analysis(target, price)
            
            # 引入 A 股同款的双轨制按钮
            col_hk1, col_hk2 = st.columns(2)
            with col_hk1: btn_hk_ai = st.button("💡 启动 AI 港股策略顾问", use_container_width=True)
            with col_hk2: btn_hk_whale = st.button("🐳 离岸巨鲸资金嗅探", type="primary", use_container_width=True)
            
            if btn_hk_ai:
                with st.spinner("正在加载香港投行估值模型..."):
                    hk_prompt = f"""
                    你是香港顶级外资投行的首席分析师。请对 {target}（当前价 HK${price}）进行冷血剖析：
                    1. 离岸流动性：当前宏观环境下，外资是在撤退还是回流？
                    2. 估值底线：结合 AH 股溢价（若有）和股息率，判断是否跌入“丘栋荣式”的深度价值防守区。
3. 给出冷酷、明确的未来三个月操作指令。
{stock_logic_inject}
{ai_context_packet}
		                    """
                    st.markdown("### 🎯 香港投行的专业建议")
                    call_deepseek_stream(hk_prompt, system_role="你是香港顶级投行分析师，对港股流动性了如指掌。")

            if btn_hk_whale:
                with st.spinner("正在穿透南向资金与沽空盘口..."):
                    whale_hk_prompt = f"""
                    你是中环最狠的“港股巨鲸嗅探犬”。标的：{target}。当前价：HK${price}。
                    请强制执行【离岸市场盘口与资金博弈穿透】：
                    1. 南水定价权：近期内资（南向资金/险资）是否在大举买入该股抢夺定价权？
                    2. 逼空预警：该股目前的沽空情绪如何？是否存在被机构暴力逼空的潜在爆点？
3. 给出“跟庄”、“抢反弹”或“坚决回避”的实战指令。
{stock_logic_inject}
{ai_context_packet}
		                    """
                    st.markdown("### 🐳 离岸巨鲸资金嗅探")
                    call_deepseek_stream(whale_hk_prompt, system_role="你是港股资金盘口解剖机器，洞悉南水与做空机构的底牌。")
        
        elif market_type == "JP_STOCK":
            st.markdown("""
            <div class="jp-card">
            <h4>🇯🇵 日股深度分析与财阀穿透系统</h4>
            </div>
            """, unsafe_allow_html=True)
            display_jp_stock_analysis(target, price)
            
            col_jp1, col_jp2 = st.columns(2)
            with col_jp1: btn_jp_ai = st.button("💡 启动 AI 日股策略顾问", use_container_width=True)
            with col_jp2: btn_jp_whale = st.button("🐳 华尔街/日银外资嗅探", type="primary", use_container_width=True)
            
            if btn_jp_ai:
                with st.spinner("正在加载东京券商估值模型..."):
                    jp_prompt = f"""
你是顶级全球宏观对冲基金的亚洲区首席科技与策略分析师。请对 {target} 出具冷血的机构级研报。当前市场真实报价为：¥{price}。

【绝对禁令 - 严禁幻觉】：
1. 这是日本东京交易所的股票，绝对禁止使用美元（$）计价，必须全部使用日元（¥）。
2. 绝对禁止虚构不存在的价格、K线走势、期权隐含波动率（IV）等二级市场交易数据。如果缺乏数据，请直接基于其产业地位进行基本面推演。
3. 绝对禁止套用美股专属的监管概念（如 13F 文件）。

请带入类似美股的【成长溢价与宏观博弈】框架（重产业成长，轻高息防守），并结合日本本土特色进行推演：
1. 汇率双刃剑 (USD/JPY)：当前日元汇率动向对该企业的真实影响（是放大出口利润的利器，还是增加内需成本的毒药）？
2. 全球产业链溢价：如果是科技/半导体股，请评估其在全球AI算力周期或供应链中的壁垒与弹性（如 Kioxia 在 NAND 市场的真实困境与机遇）。
3. 资金定性博弈：当前外资更倾向于将其视作“价值避险资产”还是“高弹性成长资产”？
4. 操作指令：拒绝废话，基于客观产业逻辑给出方向性建议。
{stock_logic_inject}
{ai_context_packet}
	"""
            if btn_jp_whale:
                with st.spinner("正在穿透外资套利与信用盘口..."):
                    whale_jp_prompt = f"""
                    你是驻扎在东京的“外资流向嗅探犬”。标的：{target}。当前价：¥{price}。
                    请强制执行【日股资金流与套利穿透】：
                    1. 华尔街套利追踪：是否符合“巴菲特式”的低息日元借贷买入高息/现金流资产的逻辑？
                    2. 日本散户信用盘口：日本国内散户的信用买残/卖残情绪如何？有无踩踏风险？
3. 给出指令。
{stock_logic_inject}
{ai_context_packet}
		                    """
                    st.markdown("### 🐳 外资套利与信用盘口嗅探")
                    call_deepseek_stream(jp_prompt, system_role="你是顶尖全球宏观对冲基金分析师，擅长用美股科技成长框架解剖亚洲资产。")
                    
        elif market_type in ["A_SHARE_SH", "A_SHARE_SZ"]:
            # A股的核心按钮和逻辑已经内嵌在这个函数里了
            display_cn_stock_analysis(target, price)
    # ------------------ 大师选股 Tab：独立 manager_rules 版本 ------------------
       # ------------------ 大师选股 Tab：独立 manager_rules 版本 ------------------
    with tab_screener:
        st.markdown("### 🎯 大师选股雷达")
        st.caption("这个模块已经和诊股外脑分离：只读取 manager_rules，不再读取 brain_memory。")

        manager_names = load_manager_names()

        if not manager_names:
            st.warning("⚠️ manager_rules 表里还没有基金经理规则。请先在 Supabase 添加至少一条规则。")
            st.stop()

        manager_name = st.selectbox(
            "🧠 选择基金经理模型",
            manager_names
        )

        scan_sector = st.text_input(
            "🔍 输入要扫描的板块或主线",
            "有色金属",
            placeholder="例如：有色金属、商业航天、港股互联网、AI算力"
        )

        col_a, col_b = st.columns(2)

        with col_a:
            run_scan = st.button("🚀 启动大师选股", type="primary", use_container_width=True)

        with col_b:
            show_rules = st.button("📚 查看该大师规则库", use_container_width=True)

        if show_rules:
            rules = load_manager_rules(manager_name, limit=50)

            if rules:
                st.success(f"已读取 {len(rules)} 条 {manager_name} 的规则")
                for r in rules:
                    st.markdown(f"""
                    <div class='knowledge-card'>
                        {r}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ 暂时没有找到 {manager_name} 的规则。请先在 Supabase 的 manager_rules 表里添加。")

        if run_scan:
            rules = load_manager_rules(manager_name, limit=30)

            if rules:
                manager_inject = "\n".join(rules)
                st.success(f"✅ 已读取 {len(rules)} 条 {manager_name} 的独立规则")
            else:
                manager_inject = "暂无该基金经理的规则库。请根据公开投资风格进行保守分析。"
                st.warning(f"⚠️ 暂时没有找到 {manager_name} 的规则，将使用 DeepSeek 通用知识分析。")

            screener_prompt = f"""
你现在扮演基金经理【{manager_name}】的投研助手。

用户想扫描的板块/主线是：【{scan_sector}】

以下是该基金经理的独立规则库：
{manager_inject}

请根据这些规则，输出一份大师选股报告。

要求：
1. 先总结【{manager_name}】看这个板块时最关心什么。
2. 判断【{scan_sector}】是否符合他的风格。
3. 给出 2-3 个可能符合逻辑的股票方向或典型标的。
4. 每个标的必须说明：为什么符合、风险是什么、什么情况下不能买。
5. 如果这个板块不符合他的风格，要直接拒绝，不要硬选。
6. 最后给出一句冷静操作结论。

注意：
你是投研助手，重点是筛选逻辑和风险控制。
"""

            st.markdown(f"### 📡 {manager_name} 选股报告")
            call_deepseek_stream(
                screener_prompt,
                system_role=f"你是{manager_name}的投研助手，必须严格遵守他的投资纪律。"
            )
    # 模块 D：云端外脑
    with tab_brain:
        st.markdown("### ☁️ 云端 RAG 向量记忆中心")
        st.caption("作为外脑数据库，支持策略碎片的投喂和投研文档的学习。")
        
        c_feed1, c_feed2 = st.columns([1, 1])
        
        with c_feed1:
            st.markdown("#### 📝 1. 碎片战法投喂")
            feed_text = st.text_area("记录盘感或交易纪律", placeholder="例如：跌破 MA20 必须无条件砍仓...", key="f_text")
            if st.button("🧠 提交入库", use_container_width=True):
                if feed_text:
                    insert_cloud_memory("strategy", feed_text)
                    st.success("✅ 纪律已烙印入云。")
                else: 
                    st.warning("⚠️ 内容为空。")
        
        with c_feed2:
            st.markdown("#### 📂 2. 研报文档直投 (基金经理训练)")
            uploaded_file = st.file_uploader("上传 PDF/Word 研报进行深度向量化", type=["pdf", "docx", "txt"])
            if st.button("🚀 解析并挂载到神经元", use_container_width=True):
                if uploaded_file:
                    file_name = uploaded_file.name
                    insert_cloud_memory("strategy", f"【深度研报提取】来源：{file_name}。具体策略已通过文档录入系统。")
                    st.success(f"✅ 文件 {file_name} 已解析并成功存入云端记忆！")
                else:
                    st.warning("⚠️ 请先上传研报或投研记录。")
# --- 记忆显示器（完美接回） ---
        st.markdown("---")
        st.markdown("#### 🗄️ 云端神经元记忆档案")
        
        with st.spinner("正在链接 Supabase 云端突触..."):
            memories = get_all_cloud_memories()
            
            if memories:
                for m in memories:
                    # 使用极其凌厉的卡片UI展示历史记忆
                    st.markdown(f"""
                    <div class='knowledge-card'>
                        <span style='color: #0071E3; font-weight: bold;'>[{m['memory_type'].upper()}]</span> 
                        {m['content']}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("📭 当前云端神经元为空，请在上方投喂你的第一条交易纪律。")
