import streamlit as st
import yfinance as yf
from openai import OpenAI
from supabase import create_client, Client
import datetime
import hashlib
import json
import os
import re
import time
import io
import inspect
import pandas as pd
import numpy as np

from config import get_config_value as read_config_value, get_deepseek_keys, get_supabase_config

try:
    from analysis_engine import (
        build_ai_context_packet,
        build_backtest_explanation_prompt,
        build_counter_argument_prompt,
        build_position_aware_prompt,
        build_strict_risk_decision,
    )
except Exception as module_error:
    ANALYSIS_MODULE_ERROR = module_error

    def build_ai_context_packet(supply_chain, valuation, news_rows, replay_rules, peer_rows=None, research_links=None, technical=None, scenario=None, data_quality=None, money_flow=None):
        return f"分析模块降级：{ANALYSIS_MODULE_ERROR}\n{supply_chain}\n{valuation}\n{news_rows}\n{replay_rules}"

    def build_backtest_explanation_prompt(ticker, backtest_report, stock_context=None):
        return f"请解释 {ticker} 的回测报告：{backtest_report}\n上下文：{stock_context}"

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
    fetch_ohlcv = getattr(_data_fetcher, "fetch_ohlcv", lambda ticker, market_type=None, start=None, end=None, freq="1d", provider="auto", adjust="qfq": pd.DataFrame())
    fetch_ohlcv_diagnostics = getattr(_data_fetcher, "fetch_ohlcv_diagnostics", lambda ticker, market_type=None, start=None, end=None, freq="1d", provider="auto", adjust="qfq": {"attempts": ["data_fetcher 缺少 fetch_ohlcv_diagnostics"]})
    fetch_realtime_quote = getattr(_data_fetcher, "fetch_realtime_quote", lambda ticker, market_type=None, provider="auto": {"ticker": ticker, "price": None, "warning": "行情模块未同步"})
    fetch_micro_data = getattr(_data_fetcher, "fetch_micro_data", lambda ticker, market_type=None: {"ticker": ticker, "warnings": ["微观数据模块未同步"]})

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

    def fetch_ohlcv(ticker, market_type=None, start=None, end=None, freq="1d", provider="auto", adjust="qfq"):
        return pd.DataFrame()

    def fetch_ohlcv_diagnostics(ticker, market_type=None, start=None, end=None, freq="1d", provider="auto", adjust="qfq"):
        return {"attempts": [str(DATA_FETCHER_MODULE_ERROR)], "rows": 0}

    def fetch_realtime_quote(ticker, market_type=None, provider="auto"):
        return {"ticker": ticker, "price": None, "warning": str(DATA_FETCHER_MODULE_ERROR)}

    def fetch_micro_data(ticker, market_type=None):
        return {"ticker": ticker, "warnings": [str(DATA_FETCHER_MODULE_ERROR)]}

try:
    import tushare_adapter as _tushare_adapter

    TUSHARE_ADAPTER_MODULE_ERROR = ""
except Exception as module_error:
    _tushare_adapter = None
    TUSHARE_ADAPTER_MODULE_ERROR = module_error

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
        st.dataframe(payload, width="stretch")
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
if "render_freshness_module" not in globals():
    render_freshness_module = getattr(_visualizer, "render_freshness_module", None) if "_visualizer" in globals() else None
if "render_backtest_report" not in globals():
    render_backtest_report = getattr(_visualizer, "render_backtest_report", None) if "_visualizer" in globals() else None
if "render_multi_mode_backtest" not in globals():
    render_multi_mode_backtest = getattr(_visualizer, "render_multi_mode_backtest", None) if "_visualizer" in globals() else None

if render_supply_chain_module is None:
    def render_supply_chain_module(profile, portfolio_health):
        _fallback_render("产业链可视化", profile)
if render_valuation_module is None:
    def render_valuation_module(valuation):
        _fallback_render("估值可视化", valuation)
if render_recent_sentiment_module is None:
    def render_recent_sentiment_module(news_rows):
        st.dataframe(pd.DataFrame(news_rows), width="stretch") if news_rows else st.info("暂无舆情")
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
        st.dataframe(pd.DataFrame(peer_rows), width="stretch") if peer_rows else st.info("暂无同行对比")
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
if render_freshness_module is None:
    def render_freshness_module(report):
        _fallback_render("新鲜度可视化", report)
if render_backtest_report is None:
    def render_backtest_report(report):
        _fallback_render("回测报告可视化", report)
if render_multi_mode_backtest is None:
    def render_multi_mode_backtest(result):
        _fallback_render("多模式回测可视化", result)

try:
    from backtester import DEFAULT_RULES, compact_report_for_prompt, run_backtest, run_multi_mode_backtests
except Exception as module_error:
    BACKTESTER_MODULE_ERROR = module_error
    DEFAULT_RULES = {
        "ma_fast": 5,
        "ma_mid": 20,
        "ma_slow": 60,
        "rsi_period": 14,
        "rsi_buy_max": 58,
        "rsi_sell_min": 74,
        "stop_loss_pct": 0.08,
        "take_profit_pct": 0.18,
        "max_drawdown_exit": 0.12,
        "position_size": 1.0,
    }

    def run_backtest(price_df, rules=None, cost_price=None, initial_cash=100000):
        return {"summary": f"回测模块降级：{BACKTESTER_MODULE_ERROR}", "metrics": {}, "signals": pd.DataFrame(), "trades": pd.DataFrame(), "equity_curve": pd.DataFrame()}

    def run_multi_mode_backtests(price_df, base_rules=None, cost_price=None, initial_cash=100000, modes=None):
        return {"reports": {"default": run_backtest(price_df, base_rules, cost_price, initial_cash)}, "summary": f"多模式回测降级：{BACKTESTER_MODULE_ERROR}"}

    def compact_report_for_prompt(report, max_trades=8):
        return {"summary": report.get("summary", "") if isinstance(report, dict) else str(report)}


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
    cloud_memory_context=None,
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
            cloud_memory_context=cloud_memory_context,
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
云端历史投喂资料：{json.dumps(cloud_memory_context or [], ensure_ascii=False, default=str)}
要求：云端资料是历史投喂资料，不一定最新；行业/主题/风险匹配只能作为相关参考。
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


@st.cache_data(ttl=900)
def cached_fetch_ohlcv(ticker, market_type, start, end, provider="auto", cache_version="ohlcv_v3"):
    return fetch_ohlcv(
        ticker,
        market_type=market_type,
        start=str(start),
        end=str(end),
        provider=provider,
    )


@st.cache_data(ttl=900)
def cached_fetch_ohlcv_diagnostics(ticker, market_type, start, end, provider="auto", cache_version="ohlcv_diag_v3"):
    return fetch_ohlcv_diagnostics(
        ticker,
        market_type=market_type,
        start=str(start),
        end=str(end),
        provider=provider,
    )


@st.cache_data(ttl=300)
def cached_realtime_quote(ticker, market_type, provider="auto"):
    return fetch_realtime_quote(ticker, market_type=market_type, provider=provider)


@st.cache_data(ttl=900)
def cached_money_flow_snapshot(ticker, market_type, deep=False):
    return call_with_supported_kwargs(
        collect_money_flow_snapshot,
        ticker,
        market_type=market_type,
        deep=deep,
    )


@st.cache_data(ttl=900)
def cached_micro_data(ticker, market_type, deep=False):
    return call_with_supported_kwargs(
        fetch_micro_data,
        ticker,
        market_type=market_type,
        deep=deep,
    )


def _progress_result_has_data(result):
    if result is None:
        return False
    if hasattr(result, "empty"):
        try:
            return not result.empty
        except Exception:
            return True
    if isinstance(result, (list, tuple, set)):
        return len(result) > 0
    if isinstance(result, str):
        return bool(result.strip())
    if isinstance(result, dict):
        if result.get("available") is False and not result.get("ok"):
            return False
        if result.get("ok") is False and not result.get("available"):
            return False
        meaningful_keys = [
            "individual_fund_flow",
            "dragon_tiger",
            "block_trade",
            "fund_flow",
            "raw_rows",
            "inst_rows",
            "market_news",
            "processed_sources",
            "manager_rules",
            "manager_scores",
            "auto_runs",
        ]
        if any(key in result for key in meaningful_keys):
            return any(result.get(key) for key in meaningful_keys)
        return bool(result)
    return True


def _run_progress_stage(label, action, status_box=None, progress_bar=None, progress_value=None, has_data=None):
    if status_box is not None:
        status_box.update(label=f"{label}...")
    if progress_bar is not None and progress_value is not None:
        progress_bar.progress(progress_value)

    start_time = time.perf_counter()
    result = action()
    elapsed = time.perf_counter() - start_time
    result_has_data = has_data(result) if callable(has_data) else _progress_result_has_data(result)
    if result_has_data:
        (status_box or st).write(f"完成：{label}，用时 {elapsed:.1f}s")
    else:
        (status_box or st).write(f"完成：{label}，用时 {elapsed:.1f}s。该项暂无可验证数据，继续分析")
    return result


def _parse_datetime_safe(value):
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time.min)
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.isna(parsed):
                return None
            return parsed.to_pydatetime().replace(tzinfo=None)
        except Exception:
            return None


def _age_days(value):
    dt = _parse_datetime_safe(value)
    if not dt:
        return None
    return max(0, (datetime.datetime.now() - dt).days)


def _fresh_status(age_days, good_days=2, stale_days=7):
    if age_days is None:
        return "缺失"
    if age_days <= good_days:
        return "新鲜"
    if age_days <= stale_days:
        return "可用但偏旧"
    return "偏旧"


def _latest_created_at(rows):
    best = None
    for row in rows or []:
        candidate = _parse_datetime_safe((row or {}).get("created_at"))
        if candidate and (best is None or candidate > best):
            best = candidate
    return best.isoformat(timespec="seconds") if best else ""


def build_data_freshness_report(technical=None, news_rows=None, money_flow=None, auto_feedback=None, backtest_report=None):
    items = []
    warnings = []
    score = 100

    technical = technical or {}
    market_asof = technical.get("data_asof")
    market_age = _age_days(market_asof)
    market_status = _fresh_status(market_age, good_days=3, stale_days=10)
    if market_status == "缺失":
        score -= 22
    elif market_status == "偏旧":
        score -= 18
    elif market_status == "可用但偏旧":
        score -= 8
    items.append({
        "数据层": "行情/技术指标",
        "最新时间": market_asof or "未知",
        "距今天数": str(market_age) if market_age is not None else "N/A",
        "状态": market_status,
        "说明": f"MA/RSI可信度 {technical.get('confidence', 0)}",
    })

    news_asof = _latest_created_at(news_rows)
    news_age = _age_days(news_asof)
    news_status = _fresh_status(news_age, good_days=2, stale_days=5)
    if not news_rows:
        score -= 18
        warnings.append("近48小时高相关舆情为空，AI结论会自动降权。")
    elif news_status == "偏旧":
        score -= 14
    elif news_status == "可用但偏旧":
        score -= 6
    items.append({
        "数据层": "近48小时舆情",
        "最新时间": news_asof or "无高相关新闻",
        "距今天数": str(news_age) if news_age is not None else "N/A",
        "状态": news_status if news_rows else "缺失",
        "说明": f"命中 {len(news_rows or [])} 条",
    })

    flow = money_flow or {}
    coverage = (flow.get("coverage") or {}).get("score")
    positives = len((flow.get("summary") or {}).get("positive", []) or [])
    negatives = len((flow.get("summary") or {}).get("negative", []) or [])
    if coverage is None:
        flow_status = "可用但需复核" if positives or negatives else "缺失"
        score -= 10 if positives or negatives else 18
    elif coverage >= 65:
        flow_status = "可用"
    elif coverage >= 35:
        flow_status = "覆盖不足"
        score -= 8
    else:
        flow_status = "缺失"
        score -= 16
    items.append({
        "数据层": "资金面",
        "最新时间": "接口实时/近实时" if positives or negatives else "未知",
        "距今天数": "N/A",
        "状态": flow_status,
        "说明": f"正面 {positives} / 负面 {negatives} / 覆盖 {coverage if coverage is not None else 'N/A'}",
    })
    for warning in flow.get("warnings", [])[:3]:
        warnings.append(str(warning))

    feedback = auto_feedback or {}
    auto_rows = []
    for key in ["auto_runs", "market_news", "processed_sources", "manager_rules", "manager_scores"]:
        auto_rows.extend(feedback.get(key, []) or [])
    auto_asof = _latest_created_at(auto_rows)
    auto_age = _age_days(auto_asof)
    auto_status = _fresh_status(auto_age, good_days=1, stale_days=3)
    if auto_status == "缺失":
        score -= 14
        warnings.append("没有看到自动任务心跳，建议检查 GitHub Actions。")
    elif auto_status == "偏旧":
        score -= 12
    elif auto_status == "可用但偏旧":
        score -= 6
    items.append({
        "数据层": "自动投喂",
        "最新时间": auto_asof or "未知",
        "距今天数": str(auto_age) if auto_age is not None else "N/A",
        "状态": auto_status,
        "说明": f"新闻 {len(feedback.get('market_news', []))} / 经理规则 {len(feedback.get('manager_rules', []))} / 心跳 {len(feedback.get('auto_runs', []))}",
    })

    bt_asof = ""
    if backtest_report:
        bt_asof = (backtest_report.get("latest_signal") or {}).get("date") or (backtest_report.get("date_range") or {}).get("end", "")
    bt_age = _age_days(bt_asof)
    bt_status = _fresh_status(bt_age, good_days=10, stale_days=30)
    if not backtest_report:
        score -= 10
    elif bt_status == "偏旧":
        score -= 8
    items.append({
        "数据层": "回测覆盖",
        "最新时间": bt_asof or "未生成",
        "距今天数": str(bt_age) if bt_age is not None else "N/A",
        "状态": bt_status if backtest_report else "缺失",
        "说明": (backtest_report or {}).get("summary", "")[:80] if backtest_report else "主诊断未生成回测反哺",
    })

    score = max(0, min(100, int(score)))
    if score >= 80:
        grade = "高"
        instruction = "数据较新，可以输出较明确的条件式交易建议。"
    elif score >= 55:
        grade = "中"
        instruction = "数据可用但有缺口，建议降低仓位并等待关键数据确认。"
    else:
        grade = "低"
        instruction = "数据偏旧或缺失较多，不适合给确定买入结论。"

    return {
        "score": score,
        "grade": grade,
        "items": items,
        "warnings": list(dict.fromkeys(warnings))[:8],
        "instruction": instruction,
    }


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
    position_text = str(position_status)
    is_adding = position_text.startswith("想加仓")
    is_holding = position_text.startswith("已持有") or is_adding
    intent = "add" if is_adding else ("hold" if position_text.startswith("已持有") else "new")
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
        "position_intent": intent,
        "is_holding": is_holding,
        "is_adding": is_adding,
        "currency": currency,
        "current_price": current,
        "cost_price": cost,
        "holding_units": units,
        "capital_plan": capital,
        "pnl_pct": pnl_pct,
        "pnl_amount": pnl_amount,
        "profit_state": state,
    }


def build_one_line_trade_instruction(profile, strict_decision, technical=None, scenario=None, money_flow=None, data_quality=None, backtest_report=None):
    technical = technical or {}
    scenario = scenario or {}
    money_flow = money_flow or {}
    data_quality = data_quality or {}
    backtest_report = backtest_report or {}
    current = profile.get("current_price")
    cost = profile.get("cost_price")
    pnl_pct = profile.get("pnl_pct")
    intent = profile.get("position_intent") or ("hold" if profile.get("is_holding") else "new")
    is_holding = intent in {"hold", "add"}
    risk_score = int(_num((strict_decision or {}).get("risk_score"), 0) or 0)
    risk_action = (strict_decision or {}).get("action", "允许继续分析")
    ma60_state = technical.get("ma60_state", "未知")
    rsi = _num(technical.get("rsi"))
    ma20 = _num(technical.get("ma20"))
    p10 = _num(scenario.get("p10"))
    p75 = _num(scenario.get("p75"))
    p90 = _num(scenario.get("p90"))
    ma60 = _num(technical.get("ma60"))
    volume_vs_20d = _num(technical.get("volume_vs_20d"))
    drawdown_20d = _num(technical.get("drawdown_20d"))
    drawdown_60d = _num(technical.get("drawdown_60d"))
    quality_score = int(_num(data_quality.get("score"), 100) or 0)
    negatives = ((money_flow.get("summary") or {}).get("negative") or [])
    reasons = list((strict_decision or {}).get("reasons") or [])
    backtest_signal = backtest_report.get("latest_signal") or {}
    backtest_metrics = backtest_report.get("metrics") or {}
    backtest_action = backtest_signal.get("action", "")
    backtest_summary = backtest_report.get("summary", "")
    bt_dd = _num(backtest_metrics.get("max_drawdown_pct"))
    bt_sharpe = _num(backtest_metrics.get("sharpe"))
    bt_trade_count = int(_num(backtest_metrics.get("trade_count"), 0) or 0)

    if backtest_action:
        reasons.append(f"回测最新信号：{backtest_action}，{backtest_signal.get('reason', '')}")
    if bt_dd is not None and bt_dd <= -22:
        reasons.append(f"回测风险：历史最大回撤 {bt_dd}% 偏深，仓位必须降档")
    if bt_trade_count >= 2 and bt_sharpe is not None and bt_sharpe < 0.2:
        reasons.append(f"回测风险：夏普 {bt_sharpe} 偏低，规则历史收益质量不足")

    trend_bad = ma60_state == "低于MA60" or (current and ma60 and current < ma60)
    ma_stack = bool(current and ma20 and ma60 and current >= ma20 >= ma60)
    rsi_hot = rsi is not None and rsi >= 72
    rsi_extreme = rsi is not None and rsi >= 82
    extended_from_ma20 = bool(current and ma20 and current >= ma20 * 1.08)
    healthy_volume = volume_vs_20d is None or 0.55 <= volume_vs_20d <= 2.8
    strong_trend = ma_stack and not trend_bad and healthy_volume and (drawdown_20d is None or drawdown_20d > -10)
    flow_bad = bool(negatives)
    backtest_blocks = any(word in backtest_action for word in ["禁止", "止损", "退出"]) or (bt_dd is not None and bt_dd <= -28)
    severe_data_gap = quality_score < 45
    trend_break = trend_bad or (drawdown_60d is not None and drawdown_60d <= -18)
    hard_block = severe_data_gap or (backtest_blocks and trend_break) or (risk_score >= 85 and trend_break)

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

    if intent == "hold":
        if pnl_pct is not None and pnl_pct <= -8 and (trend_bad or flow_bad or risk_score >= 55):
            action = "趋势破位离场"
            driver = "亏损已扩大且趋势或资金面未确认修复"
        elif pnl_pct is not None and pnl_pct < 0:
            action = "继续持有"
            driver = "仍低于成本，先等趋势/资金面确认"
        elif pnl_pct is not None and pnl_pct >= 20 and (rsi_hot or extended_from_ma20):
            action = "移动止盈"
            driver = "相对成本已有较高浮盈，优先用MA20/MA60或成本上方保护利润，不机械清仓"
        elif pnl_pct is not None and pnl_pct >= 12 and (p75 and current and current >= p75):
            action = "分批减仓"
            driver = "已接近情景上沿，可分批锁定部分利润，剩余仓位用移动止盈跟踪"
        elif hard_block:
            action = "分批减仓"
            driver = "系统风控或回测纪律触发较多，优先保护本金"
        else:
            action = "继续持有"
            driver = "未触发硬性卖出，按成本价上方移动止损"
    elif intent == "add":
        if hard_block or trend_break:
            action = "减仓观察"
            driver = "趋势或数据质量不足，不做加仓；已有仓位先保护利润或降低风险"
        elif pnl_pct is not None and pnl_pct >= 20 and (rsi_extreme or extended_from_ma20):
            action = "禁止加仓但可持有"
            driver = "浮盈较大且价格偏离均线，允许持仓跟踪，不允许高位继续抬成本"
        elif strong_trend and rsi_hot:
            action = "只允许回踩加仓"
            driver = "趋势仍强但短线偏热，只等缩量回踩MA20/MA30或突破位不破后再加"
        elif strong_trend and backtest_action in {"小仓尝试", "继续观察"}:
            action = "只允许突破确认加仓"
            driver = "多头结构仍在，可等放量突破后2-5日回踩不破突破位再加"
        else:
            action = "禁止加仓但可持有"
            driver = "加仓信号不完整，先持有观察，等回踩或突破确认"
    else:
        if hard_block:
            action = "暂不参与"
            driver = "趋势破坏、数据缺口或回测纪律不足，先不寻找新买点"
        elif trend_bad or quality_score < 60:
            action = "暂不参与"
            driver = "趋势或数据可信度不足，等待结构修复"
        elif strong_trend and (rsi_hot or extended_from_ma20):
            action = "等回踩"
            driver = "强趋势仍在，但当前位置不可追高；等MA20/MA30附近企稳、缩量回踩不破平台或突破位回踩确认"
        elif backtest_action == "小仓尝试" and risk_score <= 45:
            action = "可试探"
            driver = "回测最新信号允许试错，但仓位需受止损纪律约束"
        elif strong_trend:
            action = "等突破确认"
            driver = "多头结构健康，优先等放量突破后2-5日回踩不破突破位"
        elif risk_score <= 40:
            action = "可试探"
            driver = "风控未明显否决，可用小仓验证"
        else:
            action = "禁止追高"
            driver = "仍有风险因子，不能追价，等待回踩、缩量企稳或RSI降温后转强"

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
    if intent == "new":
        one_line = f"{action}：当前价 {current_text}；{driver}。入场只看新结构，参考买点为回踩企稳/突破确认，失效参考 {stop_text}，首次仓位建议小。"
    elif intent == "add":
        one_line = f"{action}：当前价 {current_text}，相对成本 {cost_text} 为 {pnl_text}；{driver}。加仓后移动止损参考 {stop_text}，不把低成本浮盈当作追高理由。"
    else:
        one_line = f"{action}：当前价 {current_text}，相对成本 {cost_text} 为 {pnl_text}；{driver}。移动止损参考 {stop_text}，止盈/减仓参考 {take_text}。"

    return {
        "action": action,
        "one_line": one_line,
        "driver": driver,
        "stop_loss": round(stop_loss, 2) if stop_loss else None,
        "take_profit": round(take_profit, 2) if take_profit else None,
        "risk_factors": risk_text,
        "risk_score": risk_score,
        "quality_score": quality_score,
        "backtest_summary": backtest_summary,
        "backtest_action": backtest_action,
        "position_intent": intent,
        "strong_trend": strong_trend,
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
    if instruction.get("backtest_summary"):
        st.caption(f"回测反哺：{instruction.get('backtest_summary')}")


def get_config_value(name, default=""):
    return read_config_value(name, default)

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
st.set_page_config(page_title="MING 交易工作台", page_icon="🦈", layout="wide")

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
	    .ming-hero {
	        padding: 22px 0 14px 0;
	        border-bottom: 1px solid #E5E5EA;
	        margin-bottom: 18px;
	    }
	    .ming-kicker {
	        color: #6E6E73;
	        font-size: 0.82rem;
	        font-weight: 600;
	        letter-spacing: 0;
	        margin-bottom: 6px;
	    }
	    .ming-title {
	        color: #111114;
	        font-size: clamp(2rem, 3.2vw, 3.25rem);
	        line-height: 1.05;
	        font-weight: 750;
	        letter-spacing: 0;
	        margin: 0;
	    }
	    .ming-subtitle {
	        color: #515154;
	        font-size: 1rem;
	        line-height: 1.55;
	        margin-top: 10px;
	        max-width: 760px;
	    }
	    .login-shell {
	        max-width: 560px;
	        margin: 15vh auto 0 auto;
	        text-align: center;
	    }
	    .login-title {
	        color: #111114;
	        font-size: clamp(2.2rem, 4vw, 4rem);
	        line-height: 1.05;
	        font-weight: 760;
	        letter-spacing: 0;
	        margin: 0 0 12px 0;
	    }
	    .login-subtitle {
	        color: #6E6E73;
	        font-size: 1rem;
	        line-height: 1.5;
	        margin-bottom: 26px;
	    }
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


def is_a_share_market(market_type):
    try:
        return str(market_type or "").startswith("A_SHARE")
    except Exception:
        return False


def _safe_tushare_rows(data, limit=3):
    try:
        if data is None or data.empty:
            return []
        return data.head(limit).where(data.notna(), None).to_dict("records")
    except Exception:
        return []


@st.cache_data(ttl=300)
def cached_fetch_tushare_a_share_basics(ticker, start_str=None, end_str=None, cache_version="tushare_a_share_v1"):
    updated_at = datetime.datetime.now().isoformat(timespec="seconds")
    base = {
        "ok": False,
        "partial": False,
        "data_source": "",
        "api_name": "",
        "updated_at": updated_at,
        "status": "未启用",
        "successful_apis": [],
        "failed_apis": [],
        "api_results": {},
        "error": "",
    }

    try:
        if _tushare_adapter is None:
            base["status"] = "Tushare 适配层不可用"
            base["error"] = str(TUSHARE_ADAPTER_MODULE_ERROR)
            return base

        today = datetime.date.today()
        end_date = end_str or today.isoformat()
        start_date = start_str or (today - datetime.timedelta(days=30)).isoformat()
        api_calls = [
            ("daily", _tushare_adapter.get_daily),
            ("daily_basic", _tushare_adapter.get_daily_basic),
            ("adj_factor", _tushare_adapter.get_adj_factor),
        ]

        for api_name, api_func in api_calls:
            try:
                result = api_func(ticker, start_date, end_date)
                rows = _safe_tushare_rows(result.get("data") if isinstance(result, dict) else None)
                ok = bool(isinstance(result, dict) and result.get("ok") and rows)
                api_updated_at = result.get("updated_at") if isinstance(result, dict) else updated_at
                summary = {
                    "ok": ok,
                    "api_name": api_name,
                    "updated_at": api_updated_at or updated_at,
                    "rows": rows,
                    "row_count": len(result.get("data")) if isinstance(result, dict) and result.get("data") is not None else 0,
                    "latest_date": (rows[0] or {}).get("trade_date", "") if rows else "",
                    "error": "" if ok else (result.get("error") if isinstance(result, dict) else "Tushare 返回异常"),
                }
                base["api_results"][api_name] = summary
                if ok:
                    base["successful_apis"].append(api_name)
                    base["updated_at"] = summary["updated_at"]
                else:
                    base["failed_apis"].append(api_name)
            except Exception as exc:
                base["api_results"][api_name] = {
                    "ok": False,
                    "api_name": api_name,
                    "updated_at": updated_at,
                    "rows": [],
                    "row_count": 0,
                    "latest_date": "",
                    "error": str(exc),
                }
                base["failed_apis"].append(api_name)

        if base["successful_apis"]:
            base["ok"] = True
            base["partial"] = bool(base["failed_apis"])
            base["data_source"] = "Tushare"
            base["api_name"] = ", ".join(base["successful_apis"])
            base["status"] = "部分接口成功" if base["partial"] else "全部接口成功"
        else:
            base["status"] = "全部接口失败"
            errors = [
                f"{name}: {payload.get('error')}"
                for name, payload in base["api_results"].items()
                if payload.get("error")
            ]
            base["error"] = "；".join(errors[:3])
        return base
    except Exception as exc:
        base["status"] = "Tushare 补充失败"
        base["error"] = str(exc)
        return base


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
        st.warning("缺少 DeepSeek key，本次只展示行情、回测和结构化分析，不调用模型。")
        return None

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
        st.warning("缺少 DeepSeek key，本次只展示行情、回测和结构化分析，不调用模型。")
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

    if raw_input.endswith((".SZ", ".SS", ".SH")):
        normalized = raw_input[:-3] + ".SS" if raw_input.endswith(".SH") else raw_input
        if normalized.endswith(".SS"):
            return normalized, "A_SHARE_SH", "🇨🇳 A股 (沪)", "¥"
        return normalized, "A_SHARE_SZ", "🇨🇳 A股 (深)", "¥"
    
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
if 'user_role' not in st.session_state or st.session_state.user_role is None:
    st.session_state.user_role = "Admin"

if st.session_state.user_role is None:
    st.markdown("""
    <div class="login-shell">
        <div class="ming-kicker">PRIVATE RESEARCH DESK</div>
        <h1 class="login-title">MING 交易工作台</h1>
        <div class="login-subtitle">把成本、趋势、资金和风险放到同一张桌面上。</div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("", type="password", placeholder="输入访问密钥", label_visibility="collapsed")
        if st.button("接入系统"):
            if pwd == "888888": st.session_state.user_role = "Admin"; st.rerun()
            elif pwd == "guest": st.session_state.user_role = "Guest"; st.rerun()
            else: st.error("密钥验证失败")
else:
    ds_keys = get_deepseek_keys()
    st.session_state.ds_keys = ds_keys
    st.session_state.ds_key = ds_keys[0] if ds_keys else None
    if "ds_key_index" not in st.session_state:
        st.session_state.ds_key_index = 0
    if not ds_keys:
        st.warning("缺少 DeepSeek key，本次只展示行情、回测和结构化分析，不调用模型。")

    supabase = None
    sb_url, sb_key = get_supabase_config()
    if not sb_url or not sb_key:
        st.warning("Supabase 配置缺失，云端记忆、自动投喂和历史新闻读取暂不可用；行情、回测和本地结构化分析会继续运行。")
    else:
        try:
            supabase: Client = create_client(sb_url, sb_key)
        except Exception as e:
            st.warning(f"Supabase 初始化失败，云端功能暂不可用：{e}")
            supabase = None

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
        if not supabase: return False
        try:
            supabase.table("brain_memory").insert({"memory_type": m_type, "content": content}).execute()
            return True
        except:
            return False

    def get_all_cloud_memories():
        if not supabase: return []
        try:
            res = supabase.table("brain_memory").select("id, memory_type, content").order("id", desc=True).execute()
            return res.data
        except: return []

    FEED_MISSING_TEXT = "原文未提供/暂无明确提取"
    FEED_DOCUMENT_TYPES = {
        "stock_report",
        "industry_report",
        "news",
        "manager_interview",
        "trade_review",
        "user_rule",
        "article",
        "unknown",
    }
    FEED_THEME_KEYWORDS = [
        "CPO", "AI算力", "AI", "PCB", "光刻", "液冷", "低空经济", "机器人", "半导体",
        "新能源", "储能", "光伏", "医药", "创新药", "消费电子", "数据中心", "算力",
    ]
    FEED_INDUSTRY_KEYWORDS = [
        "半导体", "通信", "传媒", "计算机", "电子", "新能源", "汽车", "医药", "消费",
        "军工", "机械", "银行", "地产", "有色", "煤炭", "电力", "化工", "食品饮料",
    ]
    FEED_RISK_KEYWORDS = [
        "估值风险", "业绩风险", "政策风险", "流动性风险", "竞争加剧", "订单不及预期",
        "需求不及预期", "毛利率下滑", "汇率风险", "减持", "解禁", "商誉", "退市风险",
    ]

    def parse_memory_payload(content):
        if isinstance(content, dict):
            return content, content
        if not isinstance(content, str):
            return {}, content

        text = content.strip()
        try:
            return json.loads(text), text
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1]), text
            except Exception:
                pass

        return {"raw_text": text}, text

    def compact_display_text(value):
        if value is None:
            return ""
        if isinstance(value, str):
            return " ".join(value.split())
        if isinstance(value, (int, float, bool)):
            return str(value)
        return ""

    def normalize_feed_text_for_hash(raw_text):
        return " ".join((raw_text or "").split())

    def generate_content_hash(raw_text):
        normalized = normalize_feed_text_for_hash(raw_text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""

    def normalize_metadata_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            values = value
        elif isinstance(value, str):
            values = re.split(r"[,，、\n;；]+", value)
        else:
            values = [value]

        cleaned = []
        for item in values:
            if isinstance(item, dict):
                item = item.get("name") or item.get("ticker") or item.get("value") or item.get("content")
            text = compact_display_text(item)
            if text and text not in {"原文未提供", "暂无明确提取", "low_confidence", "unknown"} and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def keyword_hits(raw_text, keywords):
        text = raw_text or ""
        return [keyword for keyword in keywords if keyword and keyword in text]

    def detect_tickers(raw_text):
        text = raw_text or ""
        patterns = [
            r"\b[0368]\d{5}\b",
            r"\b\d{6}\.(?:SH|SZ|BJ|SS)\b",
            r"\b\d{4,5}\.HK\b",
            r"\bHK[:：]?\s*\d{4,5}\b",
        ]
        tickers = []
        for pattern in patterns:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                ticker = compact_display_text(match).upper().replace(" ", "")
                if ticker and ticker not in tickers:
                    tickers.append(ticker)
        return tickers[:12]

    def infer_document_type(raw_text, source):
        haystack = f"{source or ''}\n{raw_text or ''}"
        lowered = haystack.lower()
        if any(word in haystack for word in ["基金经理", "访谈", "调研纪要", "路演"]):
            return "manager_interview"
        if any(word in haystack for word in ["复盘", "交易记录", "止损", "止盈"]) and "研报" not in haystack:
            return "trade_review"
        if any(word in haystack for word in ["纪律", "规则", "盘感"]) or "手动碎片投喂" in haystack:
            return "user_rule"
        if any(word in haystack for word in ["行业报告", "行业深度", "产业链"]) or "industry" in lowered:
            return "industry_report"
        if any(word in haystack for word in ["研报", "公司报告", "深度报告"]) or "report" in lowered:
            return "stock_report"
        if any(word in haystack for word in ["新闻", "快讯", "公告"]) or "news" in lowered:
            return "news"
        if any(word in haystack for word in ["文章", "专栏"]) or "article" in lowered:
            return "article"
        return "unknown"

    def normalize_extraction_status(status, raw_text):
        if status == "extracted":
            return "extracted"
        if status == "extracted_text":
            return "low_confidence"
        if status == "needs_ai_extract":
            return "pending_extract" if raw_text else "raw_saved"
        return "low_confidence" if raw_text else "raw_saved"

    def build_feed_metadata(extract_result, raw_text, source="手动投喂"):
        extract_result = extract_result or {}
        source_metadata = extract_result.get("metadata") if isinstance(extract_result.get("metadata"), dict) else {}
        content_hash = source_metadata.get("content_hash") or generate_content_hash(raw_text)
        raw_document_type = compact_display_text(source_metadata.get("document_type") or extract_result.get("document_type"))
        document_type = raw_document_type if raw_document_type in FEED_DOCUMENT_TYPES else infer_document_type(raw_text, source)
        extraction_status = compact_display_text(
            source_metadata.get("extraction_status") or extract_result.get("extraction_status")
        ) or normalize_extraction_status(extract_result.get("status"), raw_text)

        evidence_summary = compact_display_text(
            source_metadata.get("evidence_summary") or extract_result.get("evidence") or extract_result.get("core_view")
        )
        if not evidence_summary:
            evidence_summary = FEED_MISSING_TEXT

        metadata = {
            "document_type": document_type,
            "extraction_status": extraction_status,
            "tickers": normalize_metadata_list(source_metadata.get("tickers") or extract_result.get("tickers")) or detect_tickers(raw_text),
            "company_names": normalize_metadata_list(source_metadata.get("company_names") or extract_result.get("company_names")),
            "industries": normalize_metadata_list(source_metadata.get("industries") or extract_result.get("industries")) or keyword_hits(raw_text, FEED_INDUSTRY_KEYWORDS),
            "themes": normalize_metadata_list(source_metadata.get("themes") or extract_result.get("themes")) or keyword_hits(raw_text, FEED_THEME_KEYWORDS),
            "risk_tags": normalize_metadata_list(source_metadata.get("risk_tags") or extract_result.get("risk_tags")) or keyword_hits(raw_text, FEED_RISK_KEYWORDS),
            "time_window": compact_display_text(source_metadata.get("time_window") or extract_result.get("time_window")) or "原文未提供",
            "source_file": compact_display_text(source_metadata.get("source_file") or source) or "原文未提供",
            "content_hash": content_hash,
            "extracted_at": source_metadata.get("extracted_at") or datetime.datetime.now().isoformat(timespec="seconds"),
            "evidence_summary": evidence_summary[:800],
        }
        if extraction_status not in {"extracted", "pending_extract", "low_confidence", "raw_saved"}:
            metadata["extraction_status"] = "low_confidence"
        return metadata

    def attach_feed_metadata(extract_result, raw_text, source="手动投喂"):
        result = dict(extract_result or {})
        metadata = build_feed_metadata(result, raw_text, source)
        result["metadata"] = metadata
        result["content_hash"] = metadata["content_hash"]
        result["document_type"] = metadata["document_type"]
        result["extraction_status"] = metadata["extraction_status"]
        return result

    def extract_payload_content_hash(payload):
        data, _ = parse_memory_payload(payload)
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        return compact_display_text(data.get("content_hash") or metadata.get("content_hash"))

    def find_existing_content_hash(content_hash):
        result = {"duplicate": False, "brain_memory": False, "stock_reports": False}
        if not supabase or not content_hash:
            return result
        try:
            brain = (
                supabase
                .table("brain_memory")
                .select("id")
                .ilike("content", f"%{content_hash}%")
                .limit(1)
                .execute()
            )
            result["brain_memory"] = bool(brain.data)
        except Exception:
            result["brain_memory_check_failed"] = True
        try:
            reports = (
                supabase
                .table("stock_reports")
                .select("id")
                .ilike("report_content", f"%{content_hash}%")
                .limit(1)
                .execute()
            )
            result["stock_reports"] = bool(reports.data)
        except Exception:
            result["stock_reports_check_failed"] = True
        result["duplicate"] = result["brain_memory"] or result["stock_reports"]
        return result

    def normalize_memory_match_token(value):
        text = compact_display_text(value).upper()
        if not text:
            return ""
        text = text.replace("HK:", "").replace("HK：", "")
        if text.endswith(".SH"):
            text = text[:-3] + ".SS"
        return text

    def build_ticker_match_terms(ticker):
        normalized = normalize_memory_match_token(ticker)
        terms = []
        for term in [ticker, normalized]:
            clean = normalize_memory_match_token(term)
            if clean and clean not in terms:
                terms.append(clean)
        if normalized.endswith((".SS", ".SZ", ".HK", ".T")):
            core = normalized.rsplit(".", 1)[0]
            if core and core not in terms:
                terms.append(core)
        return terms

    def compact_prompt_text(value, limit=360):
        text = compact_display_text(value)
        return text[:limit] + ("..." if len(text) > limit else "")

    def value_matches_any(value, terms):
        values = normalize_metadata_list(value)
        if not values and compact_display_text(value):
            values = [compact_display_text(value)]
        haystack = " ".join(normalize_memory_match_token(item) for item in values)
        return any(term and term in haystack for term in terms)

    def text_matches_any(text, terms):
        haystack = normalize_memory_match_token(text)
        return any(term and term in haystack for term in terms)

    def memory_identity(row):
        payload = row.get("payload") or {}
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        content_hash = compact_display_text(payload.get("content_hash") or metadata.get("content_hash"))
        if content_hash:
            return f"hash:{content_hash}"
        return f"{row.get('memory_type')}:{row.get('id')}:{row.get('source')}:{row.get('created_at')}"

    def parse_memory_row(row, source_table):
        if source_table == "brain_memory":
            payload, _ = parse_memory_payload(row.get("content", ""))
            return {
                "id": row.get("id"),
                "source_table": source_table,
                "memory_type": row.get("memory_type", "memory"),
                "payload": payload,
                "created_at": row.get("created_at", ""),
            }
        if source_table == "stock_reports":
            payload, _ = parse_memory_payload(row.get("report_content", ""))
            if "ticker" not in payload and row.get("ticker"):
                payload["ticker"] = row.get("ticker")
            return {
                "id": row.get("id"),
                "source_table": source_table,
                "memory_type": row.get("report_type", "stock_report"),
                "payload": payload,
                "created_at": row.get("created_at", ""),
            }

        content = compact_prompt_text(row.get("content", ""), 500)
        payload = {
            "source": row.get("source", "manager_rules"),
            "core_view": content,
            "rules": [content] if content else [],
            "metadata": {
                "source_file": row.get("source", "manager_rules"),
                "document_type": "manager_rule",
                "extraction_status": "extracted",
                "evidence_summary": content,
            },
        }
        return {
            "id": row.get("id"),
            "source_table": source_table,
            "memory_type": row.get("rule_type", "manager_rule"),
            "payload": payload,
            "created_at": row.get("created_at", ""),
        }

    def match_memory_payload(parsed_row, ticker_terms, company_terms, industry_terms, theme_terms, risk_terms):
        payload = parsed_row.get("payload") or {}
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        searchable_text = json.dumps(payload, ensure_ascii=False, default=str)

        if value_matches_any(metadata.get("tickers"), ticker_terms) or text_matches_any(payload.get("ticker"), ticker_terms):
            return "ticker"
        if text_matches_any(searchable_text, ticker_terms):
            return "ticker"
        if value_matches_any(metadata.get("company_names"), company_terms) or text_matches_any(searchable_text, company_terms):
            return "company"
        if value_matches_any(metadata.get("industries"), industry_terms):
            return "industry"
        if value_matches_any(metadata.get("themes"), theme_terms):
            return "theme"
        if value_matches_any(metadata.get("risk_tags"), risk_terms):
            return "risk"
        if text_matches_any(searchable_text, industry_terms):
            return "industry"
        if text_matches_any(searchable_text, theme_terms):
            return "theme"
        if text_matches_any(searchable_text, risk_terms):
            return "risk"
        return ""

    def format_relevant_memory(parsed_row, match_level):
        payload = parsed_row.get("payload") or {}
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        return {
            "memory_type": compact_display_text(parsed_row.get("memory_type") or payload.get("document_type")) or "memory",
            "match_level": match_level,
            "match_strength": "strong" if match_level in {"ticker", "company"} else "related",
            "source": compact_prompt_text(
                payload.get("source") or metadata.get("source_file") or parsed_row.get("source_table") or "云端记忆",
                120,
            ),
            "core_view": compact_prompt_text(payload.get("core_view") or payload.get("summary") or payload.get("raw_text"), 420),
            "buy_conditions": [compact_prompt_text(item, 140) for item in list_display_items(payload.get("buy_conditions"))[:4]],
            "sell_conditions": [compact_prompt_text(item, 140) for item in list_display_items(payload.get("sell_conditions"))[:4]],
            "risk_triggers": [compact_prompt_text(item, 140) for item in list_display_items(payload.get("risk_triggers"))[:4]],
            "evidence_summary": compact_prompt_text(metadata.get("evidence_summary") or payload.get("evidence"), 320),
            "extracted_at": compact_prompt_text(metadata.get("extracted_at") or parsed_row.get("created_at"), 80),
            "reference_note": (
                "股票/公司专属记忆，仍需用当前行情验证。"
                if match_level in {"ticker", "company"}
                else "主题相关记忆，只能作为相关参考，不代表该股票专属资料。"
            ),
        }

    @st.cache_data(ttl=300)
    def load_relevant_memory_for_stock(ticker, company_name=None, industry=None, themes=None, risk_tags=None, limit=5):
        if not supabase:
            return []

        ticker_terms = build_ticker_match_terms(ticker)
        company_terms = [term for term in normalize_metadata_list(company_name) if term]
        industry_terms = [term for term in normalize_metadata_list(industry) if term]
        theme_terms = [term for term in normalize_metadata_list(themes) if term]
        risk_terms = [term for term in normalize_metadata_list(risk_tags) if term]
        query_terms = ticker_terms + company_terms + industry_terms + theme_terms + risk_terms
        if not query_terms:
            return []

        candidates = []

        def add_rows(source_table, rows):
            for row in rows or []:
                candidates.append(parse_memory_row(row, source_table))

        def query_brain_by_content(term, row_limit=8):
            try:
                add_rows(
                    "brain_memory",
                    supabase.table("brain_memory")
                    .select("id, memory_type, content, created_at")
                    .ilike("content", f"%{term}%")
                    .order("id", desc=True)
                    .limit(row_limit)
                    .execute()
                    .data,
                )
            except Exception:
                pass

        def query_reports_by_content(term, row_limit=8):
            try:
                add_rows(
                    "stock_reports",
                    supabase.table("stock_reports")
                    .select("id, ticker, market_type, report_type, report_content, created_at")
                    .ilike("report_content", f"%{term}%")
                    .order("created_at", desc=True)
                    .limit(row_limit)
                    .execute()
                    .data,
                )
            except Exception:
                pass

        for term in ticker_terms[:3]:
            try:
                add_rows(
                    "stock_reports",
                    supabase.table("stock_reports")
                    .select("id, ticker, market_type, report_type, report_content, created_at")
                    .eq("ticker", term)
                    .order("created_at", desc=True)
                    .limit(12)
                    .execute()
                    .data,
                )
            except Exception:
                pass
            query_brain_by_content(term, row_limit=8)
            query_reports_by_content(term, row_limit=8)

        for term in company_terms[:3]:
            query_brain_by_content(term, row_limit=8)
            query_reports_by_content(term, row_limit=8)

        related_terms = (industry_terms + theme_terms + risk_terms)[:4]
        for term in related_terms:
            query_brain_by_content(term, row_limit=5)
            query_reports_by_content(term, row_limit=5)

        for term in (company_terms + related_terms)[:4]:
            try:
                add_rows(
                    "manager_rules",
                    supabase.table("manager_rules")
                    .select("id, manager_name, rule_type, content, source, created_at")
                    .ilike("content", f"%{term}%")
                    .order("created_at", desc=True)
                    .limit(6)
                    .execute()
                    .data,
                )
            except Exception:
                pass

        best_by_identity = {}
        priority = {"ticker": 0, "company": 1, "industry": 2, "theme": 3, "risk": 4}
        for row in candidates:
            identity = memory_identity(row)
            match_level = match_memory_payload(row, ticker_terms, company_terms, industry_terms, theme_terms, risk_terms)
            if not match_level:
                continue
            memory = format_relevant_memory(row, match_level)
            score = priority.get(match_level, 9)
            existing = best_by_identity.get(identity)
            if existing is None or score < existing[0]:
                best_by_identity[identity] = (score, memory)

        return [memory for _, memory in sorted(best_by_identity.values(), key=lambda item: item[0])[:limit]]

    def render_relevant_memory_context(memories):
        st.markdown("#### 已召回云端记忆")
        if not memories:
            st.info("暂无匹配云端记忆，本次仅基于行情/估值/回测/资金流分析。")
            return

        label_map = {
            "ticker": "股票专属",
            "company": "公司名匹配",
            "industry": "行业主题相关",
            "theme": "行业主题相关",
            "risk": "风险标签相关",
        }
        strong_count = sum(1 for item in memories if item.get("match_strength") == "strong")
        related_count = len(memories) - strong_count
        st.caption(f"召回 {len(memories)} 条：股票/公司专属 {strong_count} 条，主题相关参考 {related_count} 条。")

        for idx, item in enumerate(memories, start=1):
            match_label = label_map.get(item.get("match_level"), item.get("match_level", "相关"))
            title = f"{idx}. {match_label}｜{item.get('source') or '云端记忆'}"
            with st.expander(title, expanded=idx == 1):
                st.caption(item.get("reference_note", "历史投喂资料，需结合当前行情验证。"))
                st.markdown("**核心观点**")
                st.write(item.get("core_view") or FEED_MISSING_TEXT)
                risks = item.get("risk_triggers") or []
                if risks:
                    st.markdown("**风险提示**")
                    for risk in risks:
                        st.markdown(f"- {risk}")
                if item.get("evidence_summary"):
                    st.markdown("**证据摘要**")
                    st.write(item["evidence_summary"])
                if item.get("extracted_at"):
                    st.caption(f"提炼时间：{item['extracted_at']}")

    def list_display_items(value):
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if compact_display_text(item) or isinstance(item, dict)]
        if compact_display_text(value):
            return [value]
        return []

    def render_memory_list_section(title, value):
        items = list_display_items(value)
        if not items:
            return False

        st.markdown(f"**{title}**")
        for item in items:
            if isinstance(item, dict):
                summary = item.get("content") or item.get("rule") or item.get("title") or item.get("summary")
                st.markdown(f"- {compact_display_text(summary) or FEED_MISSING_TEXT}")
            else:
                st.markdown(f"- {compact_display_text(item) or FEED_MISSING_TEXT}")
        return True

    def render_metadata_tags(metadata):
        if not isinstance(metadata, dict):
            metadata = {}
        document_type = compact_display_text(metadata.get("document_type")) or "unknown"
        extraction_status = compact_display_text(metadata.get("extraction_status")) or "low_confidence"
        duplicate_hit = metadata.get("duplicate_hit")
        duplicate_text = "命中重复资料" if duplicate_hit else "未命中重复资料"
        st.caption(f"资料类型：{document_type} ｜ 提炼状态：{extraction_status} ｜ 去重：{duplicate_text}")

        tag_groups = [
            ("股票", normalize_metadata_list(metadata.get("tickers"))),
            ("公司", normalize_metadata_list(metadata.get("company_names"))),
            ("行业", normalize_metadata_list(metadata.get("industries"))),
            ("主题", normalize_metadata_list(metadata.get("themes"))),
            ("风险标签", normalize_metadata_list(metadata.get("risk_tags"))),
        ]
        display_parts = []
        for label, values in tag_groups:
            display_parts.append(f"{label}：{', '.join(values) if values else '[]'}")
        st.caption(" ｜ ".join(display_parts))
        st.caption(f"时间窗口：{compact_display_text(metadata.get('time_window')) or '原文未提供'}")

    def render_feed_write_summary(counts, extract_result):
        metadata = extract_result.get("metadata") if isinstance(extract_result.get("metadata"), dict) else {}
        if counts.get("duplicate_hit"):
            st.warning("该资料已存在，已跳过重复写入。")
        else:
            st.caption(
                f"写入 brain_memory {counts['brain_memory']} 条 / "
                f"stock_reports {counts['stock_reports']} 条 / "
                f"manager_rules {counts['manager_rules']} 条"
            )
        render_metadata_tags(metadata)
        if counts.get("manager_rules") == 0:
            st.info(f"manager_rules 为 0：{counts.get('manager_rules_reason') or '未生成可写入规则。'}")

    def render_feed_extract_card(payload, memory_type="strategy", raw_payload=None, card_title="资料提炼结果"):
        data, raw = parse_memory_payload(payload)
        raw_payload = raw_payload if raw_payload is not None else raw
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        memory_label = compact_display_text(memory_type).upper() or "MEMORY"
        source = compact_display_text(data.get("source"))
        status = compact_display_text(data.get("extraction_status") or data.get("status") or metadata.get("extraction_status"))
        market = compact_display_text(data.get("market"))
        core_view = compact_display_text(data.get("core_view") or data.get("summary") or data.get("raw_text"))
        evidence = compact_display_text(data.get("evidence") or metadata.get("evidence_summary"))

        with st.container(border=True):
            st.markdown(f"**[{memory_label}] {card_title}**")
            meta_parts = []
            source = source or compact_display_text(metadata.get("source_file"))
            if source:
                meta_parts.append(f"来源：{source}")
            if status:
                status_text = "等待 AI 提炼" if status in {"needs_ai_extract", "pending_extract"} else status
                meta_parts.append(f"状态：{status_text}")
            if market:
                meta_parts.append(f"市场：{market}")
            if meta_parts:
                st.caption(" ｜ ".join(meta_parts))
            render_metadata_tags(metadata)

            if memory_type == "reflection":
                st.markdown("**复盘记忆**")
            else:
                st.markdown("**核心观点**")
            st.write(core_view or FEED_MISSING_TEXT)

            rendered_sections = False
            if memory_type == "strategy":
                sections = [
                    ("买入条件", "buy_conditions"),
                    ("加仓条件", "add_conditions"),
                    ("卖出/减仓条件", "sell_conditions"),
                    ("风险触发", "risk_triggers"),
                    ("失效条件", "invalid_conditions"),
                    ("可复用交易规则", "rules"),
                ]
            else:
                sections = [
                    ("可复用规则", "rules"),
                    ("证据/来源线索", "evidence"),
                ]

            for title, key in sections:
                if key == "evidence":
                    if evidence:
                        st.markdown(f"**{title}**")
                        st.write(evidence)
                        rendered_sections = True
                    continue
                rendered_sections = render_memory_list_section(title, data.get(key)) or rendered_sections

            if not rendered_sections and not evidence:
                st.caption(FEED_MISSING_TEXT)

            if evidence and memory_type == "strategy":
                st.markdown("**证据/来源线索**")
                st.write(evidence)

            with st.expander("查看原始提炼 JSON", expanded=False):
                if isinstance(raw_payload, (dict, list)):
                    st.json(raw_payload)
                elif isinstance(raw_payload, str):
                    parsed_raw, _ = parse_memory_payload(raw_payload)
                    if parsed_raw and "raw_text" not in parsed_raw:
                        st.json(parsed_raw)
                    else:
                        st.json({"raw_content": raw_payload})
                else:
                    st.json({"raw_content": str(raw_payload)})

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

    def save_stock_report(ticker, market_type, report_type, payload):
        if not supabase or not payload:
            return False

        try:
            if isinstance(payload, str):
                content = payload
            else:
                content = json.dumps(payload, ensure_ascii=False, default=str)
            supabase.table("stock_reports").insert({
                "ticker": ticker,
                "market_type": market_type,
                "report_type": report_type,
                "report_content": content,
            }).execute()
            return True
        except Exception as e:
            st.warning(f"股票报告写入失败：{e}")
            return False

    def save_manager_rule(manager_name, rule_type, content, source="手动投喂"):
        if not supabase or not manager_name or not content:
            return False
        try:
            supabase.table("manager_rules").insert({
                "manager_name": manager_name,
                "rule_type": rule_type or "其他",
                "content": content,
                "source": source,
            }).execute()
            return True
        except Exception as e:
            st.warning(f"manager_rules 写入失败：{e}")
            return False

    def split_feed_chunks(text, chunk_size=2800, overlap=250):
        text = (text or "").strip()
        chunks = []
        start = 0
        while start < len(text):
            chunk = text[start:start + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
            start += max(1, chunk_size - overlap)
        return chunks or ([text] if text else [])

    def extract_uploaded_text(uploaded_file):
        if not uploaded_file:
            return ""
        name = uploaded_file.name.lower()
        data = uploaded_file.getvalue()
        if name.endswith(".txt"):
            return data.decode("utf-8", errors="ignore")
        if name.endswith(".docx"):
            try:
                import docx

                doc = docx.Document(io.BytesIO(data))
                return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception as e:
                st.warning(f"Word 解析失败：{e}")
                return ""
        if name.endswith(".pdf"):
            try:
                import PyPDF2

                reader = PyPDF2.PdfReader(io.BytesIO(data))
                pages = []
                for page in reader.pages[:20]:
                    pages.append(page.extract_text() or "")
                return "\n".join(pages)
            except Exception as e:
                st.warning(f"PDF 解析失败：{e}")
                return ""
        return ""

    def fallback_feed_extract(raw_text, source="手动投喂"):
        summary = " ".join((raw_text or "").split())[:500]
        result = {
            "status": "needs_ai_extract",
            "core_view": summary or "原文为空，等待补充资料。",
            "market": "待识别",
            "buy_conditions": [],
            "add_conditions": [],
            "sell_conditions": [],
            "risk_triggers": [],
            "invalid_conditions": [],
            "rules": ["needs_ai_extract|原文已保存摘要，等待 AI 提炼。"],
            "evidence": f"来源：{source}；原文摘要：{summary}",
        }
        return attach_feed_metadata(result, raw_text, source)

    def parse_feed_extract(content, raw_text, source):
        try:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                parsed = json.loads(content[start:end + 1])
                parsed.setdefault("status", "extracted")
                parsed.setdefault("rules", [])
                parsed.setdefault("evidence", f"来源：{source}")
                return attach_feed_metadata(parsed, raw_text, source)
        except Exception:
            pass
        result = fallback_feed_extract(raw_text, source)
        result["status"] = "extracted_text"
        result["extraction_status"] = "low_confidence"
        result["metadata"] = build_feed_metadata(result, raw_text, source)
        result["content_hash"] = result["metadata"].get("content_hash", "")
        result["document_type"] = result["metadata"].get("document_type", "unknown")
        result["core_view"] = (content or result["core_view"])[:900]
        return result

    def extract_feed_knowledge(raw_text, source="手动投喂"):
        chunks = split_feed_chunks(raw_text)
        if not st.session_state.get("ds_keys"):
            result = fallback_feed_extract(raw_text, source)
            result["chunk_count"] = len(chunks)
            return result

        chunk_summaries = []
        for i, chunk in enumerate(chunks[:6], start=1):
            prompt = f"""
请把下面投研资料第 {i}/{len(chunks)} 段提炼成结构化交易记忆，只能基于原文，不要编造。
输出 JSON，字段固定：
core_view, market, buy_conditions, add_conditions, sell_conditions, risk_triggers, invalid_conditions, rules, evidence, metadata。
rules 用数组，每条格式为 rule_type|content，其中 rule_type 可用：买入条件/加仓条件/减仓条件/风险触发/失效条件/行业判断/其他。
metadata 必须包含：
document_type, extraction_status, tickers, company_names, industries, themes, risk_tags, time_window, source_file, evidence_summary。
document_type 只能用 stock_report / industry_report / news / manager_interview / trade_review / user_rule / article / unknown。
extraction_status 只能用 extracted / pending_extract / low_confidence / raw_saved。
如果原文没有明确股票、公司、行业、主题或风险标签，对应数组用 []；不要编造。
time_window 缺失时写“原文未提供”。

资料来源：{source}
资料片段：
{chunk[:2800]}
"""
            content = call_deepseek_non_stream(
                prompt,
                system_role="你是交易知识提炼器，负责把研报、复盘和文章压缩成可复用规则。",
                max_tokens=900,
            )
            if content:
                chunk_summaries.append(content[:2200])

        if not chunk_summaries:
            result = fallback_feed_extract(raw_text, source)
            result["chunk_count"] = len(chunks)
            return result

        merge_prompt = f"""
请合并以下分段提炼，输出最终 JSON，字段固定：
core_view, market, buy_conditions, add_conditions, sell_conditions, risk_triggers, invalid_conditions, rules, evidence, metadata。
要求高度浓缩，rules 最多 8 条，不要包含原文长段落。
metadata 保留并去重明确来自原文的 tickers/company_names/industries/themes/risk_tags；缺失用 [] 或“原文未提供”，不得补全猜测。

分段提炼：
{json.dumps(chunk_summaries, ensure_ascii=False)}
"""
        merged = call_deepseek_non_stream(
            merge_prompt,
            system_role="你是交易知识合并器，负责生成长期记忆和可执行规则。",
            max_tokens=1200,
        )
        result = parse_feed_extract(merged or "\n".join(chunk_summaries), raw_text, source)
        result["chunk_count"] = len(chunks)
        return result

    def persist_extracted_knowledge(extract_result, raw_text="", ticker="", market_type="", manager_name="", source="手动投喂"):
        original_result = extract_result if isinstance(extract_result, dict) else None
        extract_result = attach_feed_metadata(extract_result, raw_text, source)
        if original_result is not None:
            original_result.clear()
            original_result.update(extract_result)
            extract_result = original_result
        status = extract_result.get("status", "needs_ai_extract")
        core = extract_result.get("core_view", "")
        metadata = dict(extract_result.get("metadata") or {})
        duplicate = find_existing_content_hash(metadata.get("content_hash", ""))
        metadata["duplicate_hit"] = duplicate.get("duplicate", False)
        metadata["duplicate_scope"] = [
            scope for scope in ["brain_memory", "stock_reports"] if duplicate.get(scope)
        ]
        extract_result["metadata"] = metadata
        extract_result["content_hash"] = metadata.get("content_hash", "")
        extract_result["document_type"] = metadata.get("document_type", "unknown")
        extract_result["extraction_status"] = metadata.get("extraction_status", "low_confidence")
        memory_content = json.dumps({
            "status": status,
            "extraction_status": metadata.get("extraction_status"),
            "document_type": metadata.get("document_type"),
            "source": source,
            "source_file": metadata.get("source_file"),
            "content_hash": metadata.get("content_hash"),
            "metadata": metadata,
            "core_view": core,
            "market": extract_result.get("market", ""),
            "buy_conditions": extract_result.get("buy_conditions", []),
            "add_conditions": extract_result.get("add_conditions", []),
            "sell_conditions": extract_result.get("sell_conditions", []),
            "risk_triggers": extract_result.get("risk_triggers", []),
            "invalid_conditions": extract_result.get("invalid_conditions", []),
            "evidence": extract_result.get("evidence", ""),
        }, ensure_ascii=False, default=str)
        counts = {
            "brain_memory": 0,
            "stock_reports": 0,
            "manager_rules": 0,
            "duplicate_hit": duplicate.get("duplicate", False),
            "duplicate_scope": metadata.get("duplicate_scope", []),
            "content_hash": metadata.get("content_hash", ""),
            "manager_rules_reason": "",
        }
        if duplicate.get("duplicate"):
            counts["skipped_reason"] = "该资料已存在，已跳过重复写入。"
            counts["manager_rules_reason"] = "重复资料已跳过，避免重复生成规则。"
            return counts

        if insert_cloud_memory("strategy", memory_content):
            counts["brain_memory"] += 1
        if ticker and save_stock_report(ticker, market_type or "UNKNOWN", "manual_feed_extract", extract_result):
            counts["stock_reports"] += 1

        rules = [str(rule).strip() for rule in extract_result.get("rules", [])[:8] if str(rule).strip()]
        if not manager_name:
            counts["manager_rules_reason"] = "未填写关联基金经理/大师。"
        elif not rules:
            counts["manager_rules_reason"] = "提炼结果没有可写入的 manager_rules 规则。"
        for rule in rules:
            rule_type, content = ("其他", rule)
            if "|" in rule:
                rule_type, content = rule.split("|", 1)
            manager_source = f"{source} | hash:{metadata.get('content_hash', '')[:12]}"
            if manager_name and save_manager_rule(manager_name, rule_type.strip(), content.strip(), source=manager_source):
                counts["manager_rules"] += 1
        if manager_name and rules and counts["manager_rules"] == 0:
            counts["manager_rules_reason"] = "manager_rules 写入失败或 Supabase 暂不可用。"
        return counts

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

    def _cn_ts_code(stock_code):
        code = str(stock_code or "").split(".")[0].zfill(6)
        if code.startswith("6"):
            return f"{code}.SH"
        if code.startswith(("0", "3")):
            return f"{code}.SZ"
        if code.startswith(("4", "8")):
            return f"{code}.BJ"
        return code

    def _cn_recent_trade_dates(days=30):
        today = datetime.date.today()
        start = today - datetime.timedelta(days=days)
        if _tushare_adapter is not None and hasattr(_tushare_adapter, "get_trade_cal"):
            cal_result = _tushare_adapter.get_trade_cal(start.isoformat(), today.isoformat())
            cal_df = cal_result.get("data") if isinstance(cal_result, dict) else None
            if cal_df is not None and not cal_df.empty and "cal_date" in cal_df.columns:
                if "is_open" in cal_df.columns:
                    cal_df = cal_df[cal_df["is_open"].astype(str) == "1"]
                dates = sorted(cal_df["cal_date"].astype(str).tolist(), reverse=True)
                if dates:
                    return dates
        return [
            (today - datetime.timedelta(days=offset)).strftime("%Y%m%d")
            for offset in range(days + 1)
            if (today - datetime.timedelta(days=offset)).weekday() < 5
        ]

    def _cn_frame_records(df, limit=8):
        if df is None or df.empty:
            return []
        return df.head(limit).where(pd.notna(df), None).to_dict("records")

    def _cn_float(value):
        try:
            if value is None or pd.isna(value):
                return None
            return float(value)
        except Exception:
            return None

    def _cn_amount_to_yi(value):
        number = _cn_float(value)
        if number is None:
            return None
        return round(number / 100000000, 2)

    def _cn_fmt_yi(value):
        return "暂无" if value is None else f"¥{value:.2f}亿"

    def _cn_fmt_date(value):
        text = str(value or "")
        if len(text) == 8 and text.isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:]}"
        return text or "未知"

    def get_cn_dragon_tiger_board(stock_code):
        """获取 A 股龙虎榜数据：Tushare top_list 优先，近30日回看。"""
        ts_code = _cn_ts_code(stock_code)
        base = {
            "available": False,
            "message": "近30日未见龙虎榜上榜记录",
            "source": "Tushare",
            "api": "top_list",
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "error": "",
        }
        if _tushare_adapter is None:
            base["error"] = str(TUSHARE_ADAPTER_MODULE_ERROR)
            return base

        try:
            for trade_date in _cn_recent_trade_dates(30):
                top_result = _tushare_adapter.get_top_list(trade_date=trade_date, ts_code=ts_code)
                base["updated_at"] = top_result.get("updated_at") or base["updated_at"]
                if not top_result.get("ok"):
                    base["error"] = top_result.get("error") or ""
                    break

                top_df = top_result.get("data")
                if top_df is None or top_df.empty:
                    continue

                row = _cn_frame_records(top_df, 1)[0]
                inst_rows = []
                inst_summary = ""
                if hasattr(_tushare_adapter, "get_top_inst"):
                    inst_result = _tushare_adapter.get_top_inst(trade_date=trade_date, ts_code=ts_code)
                    inst_df = inst_result.get("data") if isinstance(inst_result, dict) else None
                    inst_rows = _cn_frame_records(inst_df, 8)
                    buy_total = sum((_cn_float(item.get("buy")) or 0) for item in inst_rows)
                    sell_total = sum((_cn_float(item.get("sell")) or 0) for item in inst_rows)
                    net_total = sum((_cn_float(item.get("net_buy")) or 0) for item in inst_rows)
                    if inst_rows:
                        inst_summary = (
                            f"席位{len(inst_rows)}条，买入{_cn_fmt_yi(_cn_amount_to_yi(buy_total))}，"
                            f"卖出{_cn_fmt_yi(_cn_amount_to_yi(sell_total))}，"
                            f"净买入{_cn_fmt_yi(_cn_amount_to_yi(net_total))}"
                        )

                return {
                    "available": True,
                    "latest_date": row.get("trade_date") or trade_date,
                    "reason": row.get("explain") or row.get("reason") or "",
                    "close": _cn_float(row.get("close")),
                    "pct_change": _cn_float(row.get("pct_change")),
                    "buy_amount_yi": _cn_amount_to_yi(row.get("buy")),
                    "sell_amount_yi": _cn_amount_to_yi(row.get("sell")),
                    "net_buy_amount_yi": _cn_amount_to_yi(row.get("net_amount") if row.get("net_amount") is not None else row.get("net_buy")),
                    "source": "Tushare",
                    "api": "top_list",
                    "updated_at": top_result.get("updated_at") or base["updated_at"],
                    "raw_rows": _cn_frame_records(top_df, 3),
                    "inst_rows": inst_rows,
                    "inst_summary": inst_summary,
                    "message": "",
                    "error": "",
                }
            return base
        except Exception as e:
            base["error"] = str(e)
            return base

    def get_cn_margin_data(stock_code):
        """获取 A 股融资融券数据：Tushare margin_detail 优先。"""
        ts_code = _cn_ts_code(stock_code)
        base = {
            "available": False,
            "message": "融资融券数据暂不可用或权限不足",
            "source": "Tushare",
            "api": "margin_detail",
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "error": "",
        }
        if _tushare_adapter is None:
            base["error"] = str(TUSHARE_ADAPTER_MODULE_ERROR)
            return base

        try:
            for trade_date in _cn_recent_trade_dates(30):
                margin_result = _tushare_adapter.get_margin_detail(trade_date=trade_date, ts_code=ts_code)
                base["updated_at"] = margin_result.get("updated_at") or base["updated_at"]
                if not margin_result.get("ok"):
                    base["error"] = margin_result.get("error") or ""
                    break

                margin_df = margin_result.get("data")
                if margin_df is None or margin_df.empty:
                    continue

                row = _cn_frame_records(margin_df, 1)[0]
                return {
                    "available": True,
                    "date": row.get("trade_date") or trade_date,
                    "financing_balance_yi": _cn_amount_to_yi(row.get("rzye")),
                    "financing_buy_yi": _cn_amount_to_yi(row.get("rzmre")),
                    "short_sell_volume": _cn_float(row.get("rqyl")),
                    "margin_balance_yi": _cn_amount_to_yi(row.get("rzrqye")),
                    "source": "Tushare",
                    "api": "margin_detail",
                    "updated_at": margin_result.get("updated_at") or base["updated_at"],
                    "message": "",
                    "error": "",
                }
            return base
        except Exception as e:
            base["error"] = str(e)
            return base

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

    def get_cn_north_bound_data(stock_code=None):
        """获取北向持股披露口径数据，不推断实时买卖方向。"""
        ts_code = _cn_ts_code(stock_code) if stock_code else None
        base = {
            "available": False,
            "message": "北向持股数据暂不可用，受披露规则限制。",
            "status": "北向资金日度披露口径已调整，实时买卖方向不可直接推断。",
            "source": "Tushare",
            "api": "hk_hold",
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "error": "",
        }
        try:
            if _tushare_adapter is not None and hasattr(_tushare_adapter, "get_hk_hold"):
                for trade_date in _cn_recent_trade_dates(30):
                    hold_result = _tushare_adapter.get_hk_hold(ts_code=ts_code, trade_date=trade_date)
                    base["updated_at"] = hold_result.get("updated_at") or base["updated_at"]
                    if not hold_result.get("ok"):
                        base["error"] = hold_result.get("error") or ""
                        break

                    hold_df = hold_result.get("data")
                    if hold_df is None or hold_df.empty:
                        continue

                    row = _cn_frame_records(hold_df, 1)[0]
                    return {
                        "available": True,
                        "date": row.get("trade_date") or trade_date,
                        "hold_vol": _cn_float(row.get("vol")),
                        "hold_ratio": _cn_float(row.get("ratio")),
                        "exchange": row.get("exchange") or "",
                        "source": "Tushare",
                        "api": "hk_hold",
                        "updated_at": hold_result.get("updated_at") or base["updated_at"],
                        "status": base["status"],
                        "message": "",
                        "error": "",
                    }
                if base["error"]:
                    return base

            try:
                import akshare as ak
                df = ak.stock_hsgt_hold_stock_em(market="北向", indicator="今日排行")
                if df is not None and not df.empty:
                    code = str(stock_code or "").zfill(6)
                    code_cols = [col for col in df.columns if "代码" in str(col)]
                    for col in code_cols:
                        match = df[df[col].astype(str).str.contains(code, na=False)]
                        if not match.empty:
                            row = match.head(1).where(pd.notna(match), None).to_dict("records")[0]
                            return {
                                "available": True,
                                "date": row.get("日期") or "最新披露",
                                "hold_vol": _cn_float(row.get("持股数")),
                                "hold_ratio": _cn_float(row.get("持股占比")),
                                "exchange": "",
                                "source": "Akshare",
                                "api": "stock_hsgt_hold_stock_em",
                                "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                                "status": "非实时/口径可能受限。北向资金日度披露口径已调整，实时买卖方向不可直接推断。",
                                "message": "",
                                "error": "",
                            }
            except Exception as fallback_error:
                if not base["error"]:
                    base["error"] = str(fallback_error)
            return base
        except Exception as e:
            base["error"] = str(e)
            return base

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

        cn_status = st.status("正在检查 A股龙虎榜与融资融券...", expanded=False)
        cn_progress = st.progress(0)
        dragon_data = _run_progress_stage(
            "检查龙虎榜",
            lambda: get_cn_dragon_tiger_board(stock_code),
            cn_status,
            cn_progress,
            33,
            has_data=lambda data: bool(data and data.get("available")),
        )
        margin_data = _run_progress_stage(
            "检查融资融券",
            lambda: get_cn_margin_data(stock_code),
            cn_status,
            cn_progress,
            66,
            has_data=lambda data: bool(data and data.get("available")),
        )
        north_data = _run_progress_stage(
            "检查北向持股披露",
            lambda: get_cn_north_bound_data(stock_code),
            cn_status,
            cn_progress,
            100,
            has_data=lambda data: bool(data and data.get("available")),
        )
        cn_status.update(label="完成：A股盘口数据检查", state="complete")
        
        # 第一排：龙虎榜 + 融资融券 + 北向资金
        col_a1, col_a2, col_a3 = st.columns(3)
        
        with col_a1:
            st.markdown("**🐯 龙虎榜追踪**")
            if dragon_data and dragon_data.get("available"):
                st.metric("上榜日期", _cn_fmt_date(dragon_data.get("latest_date")), "")
                if dragon_data.get("reason"):
                    st.caption(f"上榜原因：{dragon_data.get('reason')}")
                st.metric("收盘价 / 涨跌幅", f"{dragon_data.get('close') or '暂无'} / {dragon_data.get('pct_change') or '暂无'}%", "")
                st.metric("买入 / 卖出 / 净买入", f"{_cn_fmt_yi(dragon_data.get('buy_amount_yi'))} / {_cn_fmt_yi(dragon_data.get('sell_amount_yi'))} / {_cn_fmt_yi(dragon_data.get('net_buy_amount_yi'))}", "")
                if dragon_data.get("inst_summary"):
                    st.caption(f"机构席位摘要：{dragon_data.get('inst_summary')}")
            else:
                st.info((dragon_data or {}).get("message") or "近30日未见龙虎榜上榜记录")
            st.caption(f"数据源：{(dragon_data or {}).get('source', 'Tushare')} {(dragon_data or {}).get('api', 'top_list')}｜更新时间：{(dragon_data or {}).get('updated_at', '未知')}")
        
        with col_a2:
            st.markdown("**💰 融资融券监测**")
            if margin_data and margin_data.get("available"):
                st.metric("融资余额", _cn_fmt_yi(margin_data.get("financing_balance_yi")), "")
                st.metric("融资买入额", _cn_fmt_yi(margin_data.get("financing_buy_yi")), "")
                margin_balance = margin_data.get("margin_balance_yi")
                if margin_balance is not None:
                    st.metric("融资融券余额", _cn_fmt_yi(margin_balance), "")
                else:
                    st.metric("融券余量", margin_data.get("short_sell_volume") or "暂无", "")
                st.caption(f"数据日期：{_cn_fmt_date(margin_data.get('date'))}")
            else:
                st.info((margin_data or {}).get("message") or "融资融券数据暂不可用或权限不足")
            st.caption(f"数据源：{(margin_data or {}).get('source', 'Tushare')} {(margin_data or {}).get('api', 'margin_detail')}｜更新时间：{(margin_data or {}).get('updated_at', '未知')}")
        
        with col_a3:
            st.markdown("**🌍 北向资金动向**")
            st.caption((north_data or {}).get("status") or "北向资金日度披露口径已调整，实时买卖方向不可直接推断。")
            if north_data and north_data.get("available"):
                st.metric("持股日期", _cn_fmt_date(north_data.get("date")), "")
                st.metric("持股数量", north_data.get("hold_vol") or "暂无", "")
                st.metric("持股占比", f"{north_data.get('hold_ratio'):.4f}%" if north_data.get("hold_ratio") is not None else "暂无", "")
            else:
                st.info((north_data or {}).get("message") or "北向持股数据暂不可用，受披露规则限制。")
            st.caption(f"数据源：{(north_data or {}).get('source', 'Tushare')} {(north_data or {}).get('api', 'hk_hold')}｜更新时间：{(north_data or {}).get('updated_at', '未知')}")
        
        st.markdown("---")
        
        # 第二排：两个按钮
        col_cn1, col_cn2 = st.columns(2)
        
        with col_cn1:
            btn_deepseek = st.button("🚀 启动外脑深度推演（A股专用）", width="stretch", key="btn_cn_deepseek")
        
        with col_cn2:
            btn_whale = st.button("🐳 巨鲸资金嗅探", type="primary", width="stretch", key="btn_cn_whale")
        
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
            whale_status = st.status("正在分析巨鲸资金...", expanded=True)
            whale_progress = st.progress(0)
            hist_5d = _run_progress_stage(
                "读取近 5 日量价",
                lambda: get_historical_data(target, 
                    (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y-%m-%d'), 
                    datetime.datetime.now().strftime('%Y-%m-%d')),
                whale_status,
                whale_progress,
                25,
            )
            
            volume_data = "近期无数据"
            if not hist_5d.empty:
                recent_data = hist_5d[['Close', 'Volume']].tail(5)
                volume_data = recent_data.to_string()

            def build_whale_lhb_context():
                if dragon_data and dragon_data.get("available"):
                    return json.dumps(
                        {
                            "source": "Tushare",
                            "api": "top_list/top_inst",
                            "latest_date": dragon_data.get("latest_date"),
                            "reason": dragon_data.get("reason"),
                            "buy_amount_yi": dragon_data.get("buy_amount_yi"),
                            "sell_amount_yi": dragon_data.get("sell_amount_yi"),
                            "net_buy_amount_yi": dragon_data.get("net_buy_amount_yi"),
                            "inst_summary": dragon_data.get("inst_summary"),
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                return "未见龙虎榜上榜记录"

            lhb_context = _run_progress_stage(
                "整理龙虎榜上下文",
                build_whale_lhb_context,
                whale_status,
                whale_progress,
                50,
                has_data=lambda data: bool(data and data != "未见龙虎榜上榜记录"),
            )
            
            whale_prompt = f"""
		                你是陆家嘴资金流向分析师。标的：{target}。当前价：¥{price}。
		                
		                请执行【宏观机构与微观盘口双重穿透】：
		                1. 只能基于已给材料判断机构关注度；没有真实材料时不得点名基金经理或具体机构
		                2. 近期是否有新的大基金申报或清仓迹象；没有真实材料时写“未验证”
	                3. 龙虎榜分析只能引用下方 Tushare top_list/top_inst 真实返回；没有真实返回时只能写“未见龙虎榜上榜记录”，不得编造机构席位、游资席位、基金经理
	                4. 冷血的跟庄或避险建议
	                
	                量价数据：{volume_data}
	                龙虎榜真实数据：{lhb_context}
	                """

            def run_whale_deepseek():
                st.markdown("### 🐳 巨鲸资金嗅探")
                call_deepseek_stream(whale_prompt, system_role="你是A股盘口与机构解剖机器")
                return True

            _run_progress_stage(
                "调用 DeepSeek 推理",
                run_whale_deepseek,
                whale_status,
                whale_progress,
                85,
                has_data=lambda _: True,
            )
            _run_progress_stage(
                "生成巨鲸资金结果",
                lambda: True,
                whale_status,
                whale_progress,
                100,
                has_data=lambda _: True,
            )
            whale_status.update(label="完成：巨鲸资金结果", state="complete")

    # ==========================================
    # 4. 主界面
    # ==========================================
    st.markdown("""
    <section class="ming-hero">
        <div class="ming-kicker">PRIVATE TRADING ASSISTANT</div>
        <h1 class="ming-title">MING 交易工作台</h1>
        <div class="ming-subtitle">从成本价出发，合并量化、资金、舆情和经理规则，给出更克制的交易指令。</div>
    </section>
    """, unsafe_allow_html=True)
    
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
            ["未买入 (观望/找买点)", "已持有 (持仓/找卖点)", "想加仓 (已有底仓/找加仓点)"],
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

    tab_home, tab_risk, tab_rl, tab_backtest, tab_main, tab_brain, tab_screener = st.tabs([
    "🏠 今日关注池",
    "🛡️ 天眼风控 (排雷)", 
    "⏳ 炼丹炉 (强化学习)", 
    "📊 回测实验室",
    "📈 量化推演 (多市场)", 
    "☁️ 云端外脑 (数据中心)",
    "🎯 大师选股 (策略雷达)"
])
    with tab_home:
        st.markdown("### 🏠 今日关注池 / 投研驾驶舱")
        st.caption("先判断今天该看什么，再决定用哪个大师人格和哪个诊股模块。")

        if st.button("🚀 生成今日关注池", type="primary", width="stretch"):
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
                    st.dataframe(pd.DataFrame(feedback["market_news"]), width="stretch")
                else:
                    st.info("暂时没有最近市场新闻入库。")

            with feed_tab2:
                if feedback.get("processed_sources"):
                    st.dataframe(pd.DataFrame(feedback["processed_sources"]), width="stretch")
                else:
                    st.info("暂时没有最近处理成功的经理来源。")

            with feed_tab3:
                if feedback.get("manager_rules"):
                    st.dataframe(pd.DataFrame(feedback["manager_rules"]), width="stretch")
                else:
                    st.info("暂时没有最近新增的经理规则。")

            with feed_tab4:
                if feedback.get("manager_scores"):
                    st.dataframe(pd.DataFrame(feedback["manager_scores"]), width="stretch")
                else:
                    st.info("暂时没有最近经理评分。")

            with feed_tab5:
                if feedback.get("auto_runs"):
                    st.dataframe(pd.DataFrame(feedback["auto_runs"]), width="stretch")
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
                    st.dataframe(case_df, width="stretch")

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

    # 模块 B2：回测实验室
    with tab_backtest:
        st.markdown(f"### 📊 单票回测实验室：{target}")
        st.caption("先选你现在的交易目的，系统会自动套一组纪律；参数想细调时再打开高级设置。")

        default_end = datetime.date.today()
        default_start = default_end - datetime.timedelta(days=365 * 2)
        b0, bm, b1, b2 = st.columns([1.2, 1.1, 1, 1])
        with b0:
            bt_preset = st.selectbox(
                "这次想解决什么",
                ["持仓体检（推荐）", "找买点", "找卖点/止盈", "短线试错", "自定义参数"],
                key="bt_preset_v2",
            )
        with bm:
            bt_mode_choice = st.selectbox(
                "回测方式",
                ["三模式对比（推荐）", "默认模式", "自由模式", "动态止盈止损模式"],
                key="bt_mode_choice_v1",
            )
        with b1:
            bt_start = st.date_input("回测起点", default_start, key="bt_start")
        with b2:
            bt_end = st.date_input("回测终点", default_end, key="bt_end")

        b3, b4 = st.columns([1, 1])
        with b3:
            bt_cash = st.number_input("回测本金", min_value=1000.0, value=float(capital_plan or 100000.0), step=5000.0, key="bt_cash")
        with b4:
            bt_provider = st.selectbox("行情源", ["auto", "akshare", "yfinance"], index=0, key="bt_provider")

        preset_rules = {
            "持仓体检（推荐）": {
                **DEFAULT_RULES,
                "stop_loss_pct": 0.10,
                "take_profit_pct": 0.18,
                "max_drawdown_exit": 0.12,
                "position_size": 0.6,
                "rsi_buy_max": 62,
                "rsi_sell_min": 75,
                "ma_slow": 60,
            },
            "找买点": {
                **DEFAULT_RULES,
                "stop_loss_pct": 0.08,
                "take_profit_pct": 0.16,
                "max_drawdown_exit": 0.10,
                "position_size": 0.35,
                "rsi_buy_max": 58,
                "rsi_sell_min": 72,
                "ma_slow": 60,
            },
            "找卖点/止盈": {
                **DEFAULT_RULES,
                "stop_loss_pct": 0.09,
                "take_profit_pct": 0.12,
                "max_drawdown_exit": 0.08,
                "position_size": 0.5,
                "rsi_buy_max": 64,
                "rsi_sell_min": 68,
                "ma_slow": 40,
            },
            "短线试错": {
                **DEFAULT_RULES,
                "stop_loss_pct": 0.05,
                "take_profit_pct": 0.10,
                "max_drawdown_exit": 0.06,
                "position_size": 0.25,
                "rsi_buy_max": 66,
                "rsi_sell_min": 70,
                "ma_slow": 40,
            },
        }
        bt_rules = preset_rules.get(bt_preset, DEFAULT_RULES.copy())

        if bt_preset != "自定义参数":
            st.info(
                f"当前模式：{bt_preset}。系统会自动使用止损 {int(bt_rules['stop_loss_pct'] * 100)}%、"
                f"止盈 {int(bt_rules['take_profit_pct'] * 100)}%、慢线 {bt_rules['ma_slow']} 日、"
                f"单次仓位 {int(bt_rules['position_size'] * 100)}%。"
            )
        else:
            with st.expander("高级参数", expanded=True):
                r1, r2, r3, r4 = st.columns(4)
                with r1:
                    bt_stop = st.slider("止损比例", 3, 20, int(DEFAULT_RULES["stop_loss_pct"] * 100), key="bt_stop_v2") / 100
                with r2:
                    bt_take = st.slider("止盈比例", 6, 40, int(DEFAULT_RULES["take_profit_pct"] * 100), key="bt_take_v2") / 100
                with r3:
                    bt_trailing = st.slider("持仓回撤退出", 5, 30, int(DEFAULT_RULES["max_drawdown_exit"] * 100), key="bt_trailing_v2") / 100
                with r4:
                    bt_position = st.slider("单次仓位", 10, 100, int(DEFAULT_RULES["position_size"] * 100), step=5, key="bt_position_v2") / 100

                r5, r6, r7 = st.columns(3)
                with r5:
                    bt_rsi_buy = st.slider("买入RSI上限", 35, 70, int(DEFAULT_RULES["rsi_buy_max"]), key="bt_rsi_buy_v2")
                with r6:
                    bt_rsi_sell = st.slider("止盈RSI参考", 55, 85, int(DEFAULT_RULES["rsi_sell_min"]), key="bt_rsi_sell_v2")
                with r7:
                    bt_ma_slow = st.selectbox("慢线周期", [40, 60, 120], index=1, key="bt_ma_slow_v2")

                bt_rules = {
                    **DEFAULT_RULES,
                    "rsi_buy_max": bt_rsi_buy,
                    "rsi_sell_min": bt_rsi_sell,
                    "stop_loss_pct": bt_stop,
                    "take_profit_pct": bt_take,
                    "max_drawdown_exit": bt_trailing,
                    "position_size": bt_position,
                    "ma_slow": bt_ma_slow,
                }

        if (bt_end - bt_start).days < 365:
            st.warning("这段回测不足一年，结论只能当短期体检。想看规则是否可靠，建议把起点拉到近两年。")

        mode_map = {
            "默认模式": ["default"],
            "自由模式": ["free"],
            "动态止盈止损模式": ["dynamic"],
            "三模式对比（推荐）": ["default", "free", "dynamic"],
        }
        selected_modes = mode_map.get(bt_mode_choice, ["default", "free", "dynamic"])
        st.caption("默认模式看固定止盈/止损；自由模式只看趋势/RSI/均线；动态模式会按ATR/波动率自动调止盈止损。")

        bt_key = f"{target}|{market_type}|{bt_start}|{bt_end}|{bt_provider}|{cost_price}|{bt_cash}|{bt_rules}|{selected_modes}"
        if st.button("运行回测", key="btn_run_backtest", type="primary", width="stretch"):
            with st.spinner("正在拉取历史行情并跑回测..."):
                price_frame = fetch_ohlcv(
                    target,
                    market_type=market_type,
                    start=bt_start.isoformat(),
                    end=(bt_end + datetime.timedelta(days=1)).isoformat(),
                    provider=bt_provider,
                )
                if price_frame.empty and market_type.startswith("A_SHARE") and bt_provider != "auto":
                    price_frame = fetch_ohlcv(
                        target,
                        market_type=market_type,
                        start=bt_start.isoformat(),
                        end=(bt_end + datetime.timedelta(days=1)).isoformat(),
                        provider="auto",
                    )
                if price_frame.empty:
                    st.session_state["last_backtest_report"] = None
                    st.session_state["last_multi_backtest"] = None
                    st.session_state["last_backtest_key"] = bt_key
                    st.warning("没有抓到可用行情。")
                    st.caption(f"识别结果：{target}｜{market_type}｜行情源：{bt_provider}｜区间：{bt_start} 至 {bt_end}")
                    diag = cached_fetch_ohlcv_diagnostics(
                        target,
                        market_type,
                        bt_start.isoformat(),
                        (bt_end + datetime.timedelta(days=1)).isoformat(),
                        provider=bt_provider,
                    )
                    attempts = diag.get("attempts") or []
                    if attempts:
                        st.markdown("##### 数据源尝试记录")
                        for item in attempts:
                            st.caption(f"- {item}")
                    if market_type.startswith("A_SHARE"):
                        st.info("A股请优先输入 6 位代码或带 .SZ/.SS 后缀，例如 002008、002008.SZ、600459、600459.SS。若 akshare 为空，系统会自动再试 yfinance。")
                    elif market_type == "HK_STOCK":
                        st.info("港股请用 0700 或 0700.HK 这种格式，行情源用 auto/yfinance。")
                    elif market_type == "JP_STOCK":
                        st.info("日股请用 6758 或 6758.T 这种格式，行情源用 auto/yfinance。")
                    else:
                        st.info("美股请用 NVDA、INTC 这种 ticker，行情源用 auto/yfinance。")
                else:
                    multi_result = run_multi_mode_backtests(
                        price_frame,
                        base_rules=bt_rules,
                        cost_price=cost_price if cost_price > 0 else None,
                        initial_cash=bt_cash,
                        modes=selected_modes,
                    )
                    reports = multi_result.get("reports", {})
                    primary_mode = selected_modes[0] if selected_modes else "default"
                    report = reports.get(primary_mode) or next(iter(reports.values()))
                    report["ticker"] = target
                    report["market_type"] = market_type
                    report["source"] = price_frame["source"].iloc[-1] if "source" in price_frame.columns and not price_frame.empty else bt_provider
                    report["date_range"] = {"start": bt_start.isoformat(), "end": bt_end.isoformat()}
                    for mode_report in reports.values():
                        mode_report["ticker"] = target
                        mode_report["market_type"] = market_type
                        mode_report["source"] = report["source"]
                        mode_report["date_range"] = report["date_range"]
                    multi_result["ticker"] = target
                    multi_result["market_type"] = market_type
                    multi_result["source"] = report["source"]
                    multi_result["date_range"] = report["date_range"]
                    multi_result["position_profile"] = position_profile_preview
                    st.session_state["last_backtest_report"] = report
                    st.session_state["last_multi_backtest"] = multi_result
                    st.session_state["last_backtest_key"] = bt_key
                    st.success(f"回测完成：{multi_result.get('summary') or report.get('summary', '')}")

        report = st.session_state.get("last_backtest_report")
        multi_result = st.session_state.get("last_multi_backtest")
        if report and report.get("ticker") != target:
            report = None
            multi_result = None
        if report:
            st.caption(f"行情源：{report.get('source', 'unknown')}｜区间：{report.get('date_range', {}).get('start')} 至 {report.get('date_range', {}).get('end')}｜样本数：{report.get('data_points', 0)}")
            if multi_result and len((multi_result.get("reports") or {})) > 1:
                render_multi_mode_backtest(multi_result)
            else:
                render_backtest_report(report)

            with st.expander("A股微观数据补充", expanded=False):
                micro_key = f"micro_{target}_{market_type}"
                if st.button("深度资金扫描 / 刷新龙虎榜", key=f"btn_{micro_key}"):
                    with st.spinner("正在抓取完整公开微观数据，可能较慢..."):
                        st.session_state[micro_key] = cached_micro_data(target, market_type, deep=True)
                micro = st.session_state.get(micro_key, {})
                if micro.get("fund_flow"):
                    st.markdown("##### 个股资金流")
                    st.dataframe(pd.DataFrame(micro["fund_flow"]), width="stretch")
                if micro.get("dragon_tiger"):
                    st.markdown("##### 龙虎榜")
                    st.dataframe(pd.DataFrame(micro["dragon_tiger"]), width="stretch")
                if micro.get("block_trade"):
                    st.markdown("##### 大宗交易")
                    st.dataframe(pd.DataFrame(micro["block_trade"]), width="stretch")
                for warning in micro.get("warnings", []):
                    st.caption(f"提示：{warning}")
                if not micro:
                    st.info("需要时再点刷新，避免每次打开页面都慢。")

            if st.button("让 DeepSeek 解释这次回测", key="btn_explain_backtest", width="stretch"):
                if multi_result and multi_result.get("reports"):
                    compact_report = {
                        "summary": multi_result.get("summary", ""),
                        "reports": {
                            mode: compact_report_for_prompt(mode_report)
                            for mode, mode_report in multi_result.get("reports", {}).items()
                        },
                    }
                else:
                    compact_report = compact_report_for_prompt(report)
                replay_rules_for_bt = load_stock_logic_rules(target)
                context_for_bt = {
                    "position_status": position_status,
                    "capital_plan": capital_plan,
                    "cost_price": cost_price,
                    "current_price": price,
                    "stock_logic_rules": replay_rules_for_bt[:1200] if replay_rules_for_bt else "",
                }
                prompt = build_backtest_explanation_prompt(target, compact_report, context_for_bt)
                call_deepseek_stream(
                    prompt,
                    system_role="你是严格的私人量化回测教练，必须把历史回测和成本价纪律说清楚。",
                )

            if st.button("保存这次回测到云端", key="btn_save_backtest_report", width="stretch"):
                if multi_result and multi_result.get("reports"):
                    compact_report = {
                        "summary": multi_result.get("summary", ""),
                        "reports": {
                            mode: compact_report_for_prompt(mode_report)
                            for mode, mode_report in multi_result.get("reports", {}).items()
                        },
                    }
                else:
                    compact_report = compact_report_for_prompt(report)
                compact_report["ticker"] = target
                compact_report["market_type"] = market_type
                compact_report["source"] = report.get("source", "")
                compact_report["date_range"] = report.get("date_range", {})
                compact_report["saved_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                if save_stock_report(target, market_type, "backtest_report", compact_report):
                    insert_cloud_memory("reflection", f"【回测报告 - {target}】{compact_report.get('summary', '')}")
                    st.success("✅ 回测报告已写入 stock_reports，并同步一条摘要到云端外脑。")
        else:
            st.info("先运行一次回测。建议起点覆盖近两年，成本价填真实持仓成本或计划买入价。")

    # 模块 C：主干量化推演 - 多市场版
    with tab_main:
        st.markdown(f"### 📈 实时穿透：{target} ({market_badge})")
        main_status = st.status("正在生成单票深度诊断...", expanded=True)
        main_progress = st.progress(0)
        stock_logic_rules = _run_progress_stage(
            "读取炼丹炉规则",
            lambda: load_stock_logic_rules(target),
            main_status,
            main_progress,
            5,
        )
        stock_logic_inject = (
            f"\n\n【{target} 自动炼丹专属规则】\n{stock_logic_rules}"
            if stock_logic_rules else ""
        )
        normalized_target = normalize_ticker(target)
        supply_profile = _run_progress_stage(
            "读取基础行情与估值",
            lambda: get_supply_chain_profile(normalized_target),
            main_status,
            main_progress,
            10,
        )
        aliases = [raw_target, target, normalized_target, supply_profile.get("name", ""), *supply_profile.get("aliases", [])]
        memory_themes = [
            supply_profile.get("theme", ""),
            supply_profile.get("position", ""),
            *supply_profile.get("core_modules", [])[:3],
            *supply_profile.get("downstream", [])[:2],
        ]
        tushare_verified_source = {}

        if True:
            cloud_memory_context = _run_progress_stage(
                "召回云端记忆",
                lambda: load_relevant_memory_for_stock(
                    normalized_target,
                    company_name=[supply_profile.get("name", ""), *supply_profile.get("aliases", [])],
                    industry=supply_profile.get("theme", ""),
                    themes=memory_themes,
                    limit=5,
                ),
                main_status,
                main_progress,
                20,
            )

            def load_base_snapshots():
                return (
                    get_valuation_snapshot(normalized_target),
                    compute_technical_snapshot(normalized_target),
                    simulate_monte_carlo_range(normalized_target),
                )

            valuation_snapshot, technical_snapshot, scenario_snapshot = _run_progress_stage(
                "读取基础行情与估值",
                load_base_snapshots,
                main_status,
                main_progress,
                30,
            )
            money_flow_snapshot = _run_progress_stage(
                "合并资金面数据",
                lambda: cached_money_flow_snapshot(normalized_target, market_type, deep=False),
                main_status,
                main_progress,
                40,
            )
            recent_news_rows = _run_progress_stage(
                "召回近48小时舆情",
                lambda: call_with_supported_kwargs(
                    build_recent_news_context,
                    supabase,
                    normalized_target,
                    aliases=aliases,
                    days=2,
                    limit=12,
                    market_type=market_type,
                ),
                main_status,
                main_progress,
                48,
            )
            if is_a_share_market(market_type):
                try:
                    tushare_end = datetime.date.today()
                    tushare_start = tushare_end - datetime.timedelta(days=30)
                    tushare_verified_source = _run_progress_stage(
                        "读取基础行情与估值",
                        lambda: cached_fetch_tushare_a_share_basics(
                            normalized_target,
                            tushare_start.isoformat(),
                            tushare_end.isoformat(),
                            cache_version="main_diag_tushare_v1",
                        ),
                        main_status,
                        main_progress,
                        55,
                        has_data=lambda data: bool(data and data.get("ok")),
                    )
                except Exception as e:
                    tushare_verified_source = {
                        "ok": False,
                        "status": "Tushare 补充失败",
                        "error": str(e),
                    }
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
            main_backtest_report = None
            backtest_warning = ""
            try:
                bt_end_auto = datetime.date.today()
                bt_start_auto = bt_end_auto - datetime.timedelta(days=365 * 2)
                bt_price_frame = _run_progress_stage(
                    "读取基础行情与估值",
                    lambda: cached_fetch_ohlcv(
                        normalized_target,
                        market_type,
                        bt_start_auto.isoformat(),
                        (bt_end_auto + datetime.timedelta(days=1)).isoformat(),
                        provider="auto",
                        cache_version="main_auto_v3",
                    ),
                    main_status,
                    main_progress,
                    62,
                )
                if not bt_price_frame.empty:
                    main_backtest_report = run_backtest(
                        bt_price_frame,
                        rules=DEFAULT_RULES,
                        cost_price=cost_price if cost_price > 0 else None,
                        initial_cash=float(capital_plan or 100000),
                    )
                    main_backtest_report["ticker"] = normalized_target
                    main_backtest_report["market_type"] = market_type
                    main_backtest_report["source"] = bt_price_frame["source"].iloc[-1] if "source" in bt_price_frame.columns else "auto"
                    main_backtest_report["date_range"] = {"start": bt_start_auto.isoformat(), "end": bt_end_auto.isoformat()}
                else:
                    backtest_warning = "主诊断未抓到可用行情，回测反哺为空。"
            except Exception as e:
                backtest_warning = f"主诊断回测反哺失败：{e}"
            auto_feedback_for_freshness = _run_progress_stage(
                "召回云端记忆",
                lambda: load_auto_feed_feedback(limit=4),
                main_status,
                main_progress,
                70,
            )
            freshness_report = build_data_freshness_report(
                technical=technical_snapshot,
                news_rows=recent_news_rows,
                money_flow=money_flow_snapshot,
                auto_feedback=auto_feedback_for_freshness,
                backtest_report=main_backtest_report,
            )
            if backtest_warning:
                freshness_report.setdefault("warnings", []).append(backtest_warning)
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
                backtest_report=main_backtest_report,
            )
            position_profile["local_trade_instruction"] = trade_instruction
            position_profile["backtest_summary"] = (main_backtest_report or {}).get("summary", "")
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
                cloud_memory_context=cloud_memory_context,
            )
            if main_backtest_report:
                ai_context_packet += "\n\n【回测反哺】\n" + json.dumps(
                    compact_report_for_prompt(main_backtest_report),
                    ensure_ascii=False,
                    default=str,
                )
            if freshness_report:
                ai_context_packet += "\n\n【数据新鲜度】\n" + json.dumps(
                    freshness_report,
                    ensure_ascii=False,
                    default=str,
                )
            if tushare_verified_source.get("ok"):
                verified_context = {
                    "data_source": "Tushare",
                    "api_name": tushare_verified_source.get("api_name", ""),
                    "updated_at": tushare_verified_source.get("updated_at", ""),
                    "verification_status": tushare_verified_source.get("status", ""),
                    "successful_apis": tushare_verified_source.get("successful_apis", []),
                    "failed_apis": tushare_verified_source.get("failed_apis", []),
                    "api_results": tushare_verified_source.get("api_results", {}),
                }
                ai_context_packet += "\n\n【已验证数据来源】\n" + json.dumps(
                    verified_context,
                    ensure_ascii=False,
                    default=str,
                )

            _run_progress_stage(
                "生成单票深度诊断",
                lambda: True,
                main_status,
                main_progress,
                90,
                has_data=lambda _: True,
            )
            main_status.write("调用 DeepSeek 推理：等待点击“生成私人交易助手建议”后执行")
            main_progress.progress(100)
            main_status.update(label="完成：单票深度诊断底座", state="complete")

        if tushare_verified_source.get("ok"):
            st.caption(
                "已验证数据来源：Tushare"
                f"｜接口：{tushare_verified_source.get('api_name', '')}"
                f"｜更新时间：{tushare_verified_source.get('updated_at', '')}"
                f"｜{tushare_verified_source.get('status', '')}"
            )
        render_trade_instruction_card(position_profile, trade_instruction)
        render_relevant_memory_context(cloud_memory_context)

        with st.expander("🧭 统一诊股底座：产业链 / 估值 / 舆情 / 风控", expanded=True):
            base_tab1, base_tab2, base_tab3, base_tab4, base_tab5, base_tab6, base_tab7, base_tab8, base_tab9, base_tab10, base_tab11, base_tab12, base_tab13 = st.tabs([
                "产业链联动",
                "估值回归",
                "实时指标",
                "情景推演",
                "近48小时舆情",
                "持仓体检",
                "资金面",
                "回测反哺",
                "同行对比",
                "深度挖掘",
                "禁止买入",
                "可信度",
                "新鲜度",
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
                if market_type == "A_SHARE":
                    st.caption("主报告默认使用快速资金模式；完整龙虎榜/大宗交易扫描需要手动触发，避免阻塞诊股。")
                    deep_key = f"deep_money_flow_{normalized_target}_{market_type}"
                    if st.button("深度资金扫描 / 运行完整龙虎榜与资金流", key=f"btn_{deep_key}"):
                        deep_status = st.status("正在运行完整资金扫描，可能较慢...", expanded=True)
                        deep_progress = st.progress(0)
                        try:
                            deep_result = _run_progress_stage(
                                "读取 Akshare 个股资金流",
                                lambda: cached_money_flow_snapshot(normalized_target, market_type, deep=True),
                                deep_status,
                                deep_progress,
                                35,
                            )
                            _run_progress_stage(
                                "检查龙虎榜",
                                lambda: (deep_result or {}).get("dragon_tiger", []),
                                deep_status,
                                deep_progress,
                                60,
                            )
                            _run_progress_stage(
                                "检查大宗交易",
                                lambda: (deep_result or {}).get("block_trade", []),
                                deep_status,
                                deep_progress,
                                80,
                            )
                            _run_progress_stage(
                                "生成资金扫描结论",
                                lambda: (deep_result or {}).get("summary", {}),
                                deep_status,
                                deep_progress,
                                100,
                                has_data=lambda _: True,
                            )
                            st.session_state[deep_key] = deep_result
                            deep_status.update(label="完成：完整资金扫描", state="complete")
                        except Exception as e:
                            st.session_state[deep_key] = {"warnings": [f"深度资金扫描失败：{e}"]}
                            deep_status.update(label="完整资金扫描结束", state="complete")
                    if st.session_state.get(deep_key):
                        st.markdown("##### 深度资金扫描结果")
                        render_money_flow_module(st.session_state[deep_key])
            with base_tab8:
                if main_backtest_report:
                    render_backtest_report(main_backtest_report)
                else:
                    st.warning(backtest_warning or "暂无主诊断回测反哺。")
            with base_tab9:
                render_peer_snapshot(peer_rows)
            with base_tab10:
                render_research_links(research_links)
            with base_tab11:
                render_risk_decision(strict_decision)
            with base_tab12:
                render_data_quality_module(data_quality_report)
            with base_tab13:
                render_freshness_module(freshness_report)

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
            assistant_status = st.status("正在调用 DeepSeek 推理...", expanded=True)
            assistant_progress = st.progress(0)
            assistant_prompt = _run_progress_stage(
                "生成单票深度诊断",
                lambda: build_position_aware_prompt_safe(
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
                ),
                assistant_status,
                assistant_progress,
                35,
            )
            _run_progress_stage(
                "调用 DeepSeek 推理",
                lambda: call_deepseek_stream(
                    assistant_prompt,
                    system_role="你是私人交易助手，必须先处理风险，再给建仓或持仓动作。",
                ),
                assistant_status,
                assistant_progress,
                85,
                has_data=lambda _: True,
            )
            _run_progress_stage(
                "生成单票深度诊断",
                lambda: True,
                assistant_status,
                assistant_progress,
                100,
                has_data=lambda _: True,
            )
            assistant_status.update(label="完成：DeepSeek 单票诊断", state="complete")
        
        if market_type == "US_STOCK":
            st.markdown("""
            <div class="us-card">
            <h4>🇺🇸 华尔街机构级分析</h4>
            </div>
            """, unsafe_allow_html=True)
            display_us_stock_analysis(target, price)
            
            if st.button("💡 启动 AI 华尔街策略顾问", width="stretch", key="btn_us_ai"):
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
            with col_hk1: btn_hk_ai = st.button("💡 启动 AI 港股策略顾问", width="stretch")
            with col_hk2: btn_hk_whale = st.button("🐳 离岸巨鲸资金嗅探", type="primary", width="stretch")
            
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
            with col_jp1: btn_jp_ai = st.button("💡 启动 AI 日股策略顾问", width="stretch")
            with col_jp2: btn_jp_whale = st.button("🐳 华尔街/日银外资嗅探", type="primary", width="stretch")
            
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
                    st.markdown("### 🎯 东京市场交易建议")
                    call_deepseek_stream(jp_prompt, system_role="你是顶尖全球宏观对冲基金分析师，擅长用美股科技成长框架解剖亚洲资产。")
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
                    call_deepseek_stream(whale_jp_prompt, system_role="你是日股资金流与外资套利盘口分析师，只能基于已给材料输出。")
                    
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
            run_scan = st.button("🚀 启动大师选股", type="primary", width="stretch")

        with col_b:
            show_rules = st.button("📚 查看该大师规则库", width="stretch")

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
            feed_manager_name = st.text_input("关联基金经理/大师（可选）", value="", key="feed_manager_name")
            if st.button("🧠 提交入库", width="stretch"):
                if feed_text:
                    with st.spinner("正在切分资料并提炼交易记忆..."):
                        extract_result = extract_feed_knowledge(feed_text, source="手动碎片投喂")
                        counts = persist_extracted_knowledge(
                            extract_result,
                            raw_text=feed_text,
                            ticker=target,
                            market_type=market_type,
                            manager_name=feed_manager_name.strip(),
                            source="手动碎片投喂",
                        )
                    if extract_result.get("status") == "needs_ai_extract":
                        st.warning("已保存，等待 AI 提炼。")
                    else:
                        st.success("已提炼入脑。")
                    render_feed_write_summary(counts, extract_result)
                    render_feed_extract_card(
                        extract_result,
                        memory_type="strategy",
                        raw_payload=extract_result,
                        card_title="手动碎片投喂",
                    )
                else: 
                    st.warning("⚠️ 内容为空。")
        
        with c_feed2:
            st.markdown("#### 📂 2. 研报文档直投 (基金经理训练)")
            uploaded_file = st.file_uploader("上传 PDF/Word 研报进行深度向量化", type=["pdf", "docx", "txt"])
            if st.button("🚀 解析并挂载到神经元", width="stretch"):
                if uploaded_file:
                    file_name = uploaded_file.name
                    raw_doc_text = extract_uploaded_text(uploaded_file)
                    if not raw_doc_text.strip():
                        st.warning("原文已上传但未解析出有效文本，未写入结构化记忆。")
                    else:
                        with st.spinner("正在解析文档并提炼结构化记忆..."):
                            extract_result = extract_feed_knowledge(raw_doc_text, source=file_name)
                            counts = persist_extracted_knowledge(
                                extract_result,
                                raw_text=raw_doc_text,
                                ticker=target,
                                market_type=market_type,
                                manager_name=feed_manager_name.strip(),
                                source=file_name,
                            )
                        if extract_result.get("status") == "needs_ai_extract":
                            st.warning(f"文件 {file_name} 已保存摘要，等待 AI 提炼。")
                        else:
                            st.success(f"文件 {file_name} 已提炼入脑。")
                        render_feed_write_summary(counts, extract_result)
                        render_feed_extract_card(
                            extract_result,
                            memory_type="strategy",
                            raw_payload=extract_result,
                            card_title=file_name,
                        )
                else:
                    st.warning("⚠️ 请先上传研报或投研记录。")
# --- 记忆显示器（完美接回） ---
        st.markdown("---")
        st.markdown("#### 🗄️ 云端神经元记忆档案")
        
        with st.spinner("正在链接 Supabase 云端突触..."):
            memories = get_all_cloud_memories()
            
            if memories:
                for m in memories:
                    render_feed_extract_card(
                        m.get("content", ""),
                        memory_type=m.get("memory_type", "memory"),
                        raw_payload=m.get("content", ""),
                        card_title=f"云端记忆 #{m.get('id', '')}",
                    )
            else:
                st.info("📭 当前云端神经元为空，请在上方投喂你的第一条交易纪律。")
