import streamlit as st
import yfinance as yf
from openai import OpenAI
from supabase import create_client, Client
import datetime
import hashlib
from html import escape as html_escape
import json
import os
import re
import time
import io
import inspect
import pandas as pd
import numpy as np

import command_center_adapter as cc_adapter
import command_center_home_snapshot as home_snapshot_service
import command_center_projection as projection_service
import command_center_radar_packet as radar_packet_service
import command_center_etf_packet as etf_packet_service
import command_center_packet_registry as packet_registry_service
import command_center_desktop_frontend_readiness as desktop_readiness_service
import command_center_analysis_methods as analysis_methods_service
import command_center_facts_packet as facts_packet_service
import command_center_discipline_packet as discipline_packet_service
import command_center_market_packet as market_packet_service
import command_center_quant_packet as quant_packet_service
import command_center_chip_packet as chip_packet_service
import command_center_moneyflow_packet as moneyflow_packet_service
import command_center_dragon_tiger_packet as dragon_tiger_packet_service
import command_center_margin_packet as margin_packet_service
import command_center_limit_emotion_packet as limit_emotion_packet_service
import command_center_hard_risk_packet as hard_risk_packet_service
import command_center_legacy_packet_sync as legacy_packet_sync_service
import command_center_legacy_a_share_gate as legacy_a_share_gate_service
import command_center_legacy_a_share_prompt_packets as legacy_a_share_prompt_packet_service
import command_center_legacy_a_share_prompts as legacy_a_share_prompt_service
import command_center_legacy_a_share_debug_summary as legacy_a_share_debug_summary_service
import command_center_evidence_summary as evidence_summary_service
import market_data_capability as data_capability
import data_capability_service as data_capability_governance_service
import command_center_toolbox_summary as toolbox_summary_service
import command_center_a_share_manual_checks as a_share_manual_checks_service
import command_center_legacy_a_share_auto_hydrate as legacy_a_share_auto_hydrate_service
import command_center_state_adapter as cc_state_adapter
import command_center_service as cc_service
import command_center_decision_engine as decision_engine
import strategy_execution_service as strategy_service
from command_center_decision_summary import build_decision_summary_view_model
from command_center_module_summary import build_module_summary_view_model
from command_center_overview_summary import build_command_center_overview_view_model
from command_center_refresh_summary import build_refresh_summary_view_model
from command_center_strategy_summary import build_strategy_summary_view_model
from config import get_config_value as read_config_value, get_deepseek_keys, get_supabase_config

try:
    import visual_components as _visual_components

    _VISUAL_COMPONENT_LABELS = {
        "render_action_matrix": "动作辅助矩阵",
        "render_command_center_account_budget_card": "账户金额与预算",
        "render_command_center_decision_hero": "今日总决策主卡",
        "render_command_center_projection_chart": "趋势推演主视觉",
        "render_analysis_methods_card": "市场分析方法",
        "render_command_center_packet_registry_card": "综合中心能力地图",
        "render_command_center_shell": "综合推演中心框架",
        "render_command_center_shell_end": "",
        "render_etf_score_table": "ETF 强弱表",
        "render_discipline_validation_grid": "纪律校验区",
        "render_fusion_summary_card": "融合结论卡",
        "render_home_action_snapshot": "首页交易快照",
        "render_holdings_snapshot_summary": "ETF 持仓差异",
        "render_home_analysis_methods_strip": "首页市场分析口径",
        "render_intraday_etf_snapshot": "ETF 实时快照",
        "render_margin_allocator_chart": "融资ETF配置图",
        "render_margin_bucket_weights_table": "Bucket 权重表",
        "render_margin_candidate_table": "候选 ETF 表",
        "render_margin_etf_data_status": "ETF 数据状态卡",
        "render_margin_etf_research_summary": "ETF 调研解释",
        "render_margin_execution_summary": "今日执行摘要",
        "render_margin_recommended_etf_plan": "今日建议 ETF 配置清单",
        "render_moneyflow_conflict": "资金流冲突仪表",
        "render_next_ticket_holding_card": "下一票持仓卡",
        "render_next_ticket_research_summary": "下一票深度研究摘要",
        "render_observation_pool_card": "观察池",
        "render_path_projection_card": "路径推演图",
        "render_position_waterline": "持仓盈亏水位",
        "render_process_stepper": "流程步骤条",
        "render_price_simulator": "盘中价格情景推演",
        "render_risk_radar_summary": "本地风险雷达摘要",
        "render_signal_confluence_card": "信号共振",
        "render_strategy_execution_command_card": "策略执行操作卡",
        "render_theme_comparison_table": "同赛道 ETF 对比",
    }

    def _missing_visual_component(component_name, display_name):
        def _fallback(*args, **kwargs):
            if display_name:
                st.warning(f"{display_name} 暂不可用：visual_components 缺少 {component_name}")

        return _fallback

    for _component_name, _component_label in _VISUAL_COMPONENT_LABELS.items():
        globals()[_component_name] = getattr(
            _visual_components,
            _component_name,
            _missing_visual_component(_component_name, _component_label),
        )
except Exception as module_error:
    VISUAL_COMPONENTS_MODULE_ERROR = module_error

    def _visual_component_unavailable(name):
        st.warning(f"{name} 暂不可用：{VISUAL_COMPONENTS_MODULE_ERROR}")

    def render_action_matrix(*args, **kwargs):
        _visual_component_unavailable("动作辅助矩阵")

    def render_command_center_account_budget_card(*args, **kwargs):
        _visual_component_unavailable("账户金额与预算")

    def render_command_center_decision_hero(*args, **kwargs):
        _visual_component_unavailable("今日总决策主卡")

    def render_command_center_projection_chart(*args, **kwargs):
        _visual_component_unavailable("趋势推演主视觉")

    def render_analysis_methods_card(*args, **kwargs):
        _visual_component_unavailable("市场分析方法")

    def render_command_center_packet_registry_card(*args, **kwargs):
        _visual_component_unavailable("综合中心能力地图")

    def render_home_action_snapshot(*args, **kwargs):
        _visual_component_unavailable("首页交易快照")

    def render_home_analysis_methods_strip(*args, **kwargs):
        _visual_component_unavailable("首页市场分析口径")

    def render_command_center_shell(*args, **kwargs):
        _visual_component_unavailable("综合推演中心框架")

    def render_command_center_shell_end(*args, **kwargs):
        pass

    def render_discipline_validation_grid(*args, **kwargs):
        _visual_component_unavailable("纪律校验区")

    def render_etf_score_table(*args, **kwargs):
        _visual_component_unavailable("ETF 强弱表")

    def render_fusion_summary_card(*args, **kwargs):
        _visual_component_unavailable("融合结论卡")

    def render_intraday_etf_snapshot(*args, **kwargs):
        _visual_component_unavailable("ETF 实时快照")

    def render_holdings_snapshot_summary(*args, **kwargs):
        _visual_component_unavailable("ETF 持仓差异")

    def render_margin_allocator_chart(*args, **kwargs):
        _visual_component_unavailable("融资ETF配置图")

    def render_margin_bucket_weights_table(*args, **kwargs):
        _visual_component_unavailable("Bucket 权重表")

    def render_margin_candidate_table(*args, **kwargs):
        _visual_component_unavailable("候选 ETF 表")

    def render_margin_etf_data_status(*args, **kwargs):
        _visual_component_unavailable("ETF 数据状态卡")

    def render_margin_etf_research_summary(*args, **kwargs):
        _visual_component_unavailable("ETF 调研解释")

    def render_margin_execution_summary(*args, **kwargs):
        _visual_component_unavailable("今日执行摘要")

    def render_margin_recommended_etf_plan(*args, **kwargs):
        _visual_component_unavailable("今日建议 ETF 配置清单")

    def render_moneyflow_conflict(*args, **kwargs):
        _visual_component_unavailable("资金流冲突仪表")

    def render_next_ticket_holding_card(*args, **kwargs):
        _visual_component_unavailable("下一票持仓卡")

    def render_next_ticket_research_summary(*args, **kwargs):
        _visual_component_unavailable("下一票深度研究摘要")

    def render_observation_pool_card(*args, **kwargs):
        _visual_component_unavailable("观察池")

    def render_path_projection_card(*args, **kwargs):
        _visual_component_unavailable("路径推演图")

    def render_position_waterline(*args, **kwargs):
        _visual_component_unavailable("持仓盈亏水位")

    def render_process_stepper(*args, **kwargs):
        _visual_component_unavailable("流程步骤条")

    def render_price_simulator(*args, **kwargs):
        _visual_component_unavailable("盘中价格情景推演")

    def render_risk_radar_summary(*args, **kwargs):
        _visual_component_unavailable("本地风险雷达摘要")

    def render_signal_confluence_card(*args, **kwargs):
        _visual_component_unavailable("信号共振")

    def render_strategy_execution_command_card(*args, **kwargs):
        _visual_component_unavailable("策略执行操作卡")

    def render_theme_comparison_table(*args, **kwargs):
        _visual_component_unavailable("同赛道 ETF 对比")

try:
    from next_stock_radar import render_next_ticket_radar, run_light_rule_scan_for_command_center
except Exception as module_error:
    NEXT_STOCK_RADAR_MODULE_ERROR = module_error

    def render_next_ticket_radar(*args, **kwargs):
        st.warning(f"下一票作战雷达暂不可用：{NEXT_STOCK_RADAR_MODULE_ERROR}")

    def run_light_rule_scan_for_command_center(*args, **kwargs):
        raise RuntimeError(f"下一票作战雷达暂不可用：{NEXT_STOCK_RADAR_MODULE_ERROR}")

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
    from margin_etf_allocator import calculate_margin_etf_allocation, get_margin_etf_catalog
    MARGIN_ALLOCATOR_MODULE_ERROR = ""
except Exception as module_error:
    MARGIN_ALLOCATOR_MODULE_ERROR = module_error

    def calculate_margin_etf_allocation(account, market_state, risk_profile, etf_scores=None):
        return {
            "action_state": "禁止加融资",
            "risk_level": "模块降级",
            "notes": [f"融资ETF模块降级：{MARGIN_ALLOCATOR_MODULE_ERROR}"],
            "recommended_etf_allocation": {},
            "risk_lines": [],
            "trigger_conditions": [],
            "invalid_conditions": [],
            "scores": {},
        }

    def get_margin_etf_catalog():
        return {}

try:
    from etf_data_engine import (
        COMPARISON_THEMES,
        build_dynamic_etf_universe,
        compare_etfs_within_theme,
        discover_etf_universe_from_tushare,
        fetch_etf_holdings_snapshot,
        fetch_etf_universe_data,
        fetch_intraday_etf_snapshot,
        get_default_etf_universe,
        get_etf_catalog_by_bucket,
        score_etf_universe,
    )
    ETF_DATA_ENGINE_MODULE_ERROR = ""
except Exception as module_error:
    ETF_DATA_ENGINE_MODULE_ERROR = module_error

    def fetch_etf_universe_data(*args, **kwargs):
        return {"available": False, "errors": [str(ETF_DATA_ENGINE_MODULE_ERROR)], "items": [], "latest_data_date": "", "sample_count": 0, "available_count": 0, "has_data_gap": True}

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

    def discover_etf_universe_from_tushare(*args, **kwargs):
        return {"available": False, "used_fallback": True, "items": get_default_etf_universe(), "discovered_count": len(get_default_etf_universe()), "classified_count": len(get_default_etf_universe()), "data_gaps": [str(ETF_DATA_ENGINE_MODULE_ERROR)]}

    def build_dynamic_etf_universe(*args, **kwargs):
        universe = get_default_etf_universe()
        dataset = fetch_etf_universe_data(universe)
        score_packet = score_etf_universe(dataset)
        return {"universe": universe, "score_packet": score_packet, "raw_score_packet": score_packet, "data_status": dataset, "discovery": discover_etf_universe_from_tushare()}

    def compare_etfs_within_theme(*args, **kwargs):
        return {"rows": [], "comparison_reason": [str(ETF_DATA_ENGINE_MODULE_ERROR)]}

    def fetch_etf_holdings_snapshot(*args, **kwargs):
        return {"holdings_available": False, "holdings_errors": [str(ETF_DATA_ENGINE_MODULE_ERROR)], "snapshots": {}}

    def fetch_intraday_etf_snapshot(*args, **kwargs):
        return {"available": False, "errors": [str(ETF_DATA_ENGINE_MODULE_ERROR)], "rows": []}

    def get_default_etf_universe():
        return []

    def get_etf_catalog_by_bucket(universe=None):
        return {}

    def score_etf_universe(etf_market_data):
        return {"rows": [], "data_date": "", "data_source": "rules_only", "sample_count": 0}

try:
    from margin_etf_research import (
        REPORT_TYPE as MARGIN_ETF_DAILY_RESEARCH_REPORT_TYPE,
        build_margin_etf_allocation_hash,
        build_margin_etf_research_prompt,
    )
    MARGIN_ETF_RESEARCH_MODULE_ERROR = ""
except Exception as module_error:
    MARGIN_ETF_RESEARCH_MODULE_ERROR = module_error
    MARGIN_ETF_DAILY_RESEARCH_REPORT_TYPE = "margin_etf_daily_research"

    def build_margin_etf_allocation_hash(allocation_result):
        return hashlib.sha256(json.dumps(allocation_result or {}, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def build_margin_etf_research_prompt(packet):
        return f"融资 ETF 调研模块降级：{MARGIN_ETF_RESEARCH_MODULE_ERROR}\n{json.dumps(packet, ensure_ascii=False, default=str)}"

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
        try:
            st.dataframe(payload, use_container_width=True)
        except Exception as table_error:
            st.warning(f"{title} 表格暂不可用：{type(table_error).__name__}")
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
        if news_rows:
            try:
                st.dataframe(pd.DataFrame(news_rows), use_container_width=True)
            except Exception as table_error:
                st.warning(f"舆情表格暂不可用：{type(table_error).__name__}")
        else:
            st.info("暂无舆情")
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
        if peer_rows:
            try:
                st.dataframe(pd.DataFrame(peer_rows), use_container_width=True)
            except Exception as table_error:
                st.warning(f"同行对比表格暂不可用：{type(table_error).__name__}")
        else:
            st.info("暂无同行对比")
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
    from backtester import (
        DEFAULT_RULES,
        TECH_GROWTH_STOCK_POOL,
        compact_report_for_prompt,
        run_backtest,
        run_batch_strategy_mode_backtests,
        run_multi_mode_backtests,
    )
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
        "mode": "default",
        "tech_rsi_buy_max": 68,
        "tech_rsi_extreme": 78,
        "tech_reduce_gap_days": 5,
        "tech_max_reduce_count": 3,
        "tech_trailing_drawdown_pct": 0.12,
        "tech_atr_multiplier": 2.5,
        "tech_volume_min_ratio": 0.6,
        "tech_break_volume_ratio": 1.3,
        "tech_big_drop_pct": 0.06,
    }
    TECH_GROWTH_STOCK_POOL = [
        {"ts_code": "002008.SZ", "name": "大族激光"},
        {"ts_code": "002837.SZ", "name": "英维克"},
        {"ts_code": "601138.SH", "name": "工业富联"},
        {"ts_code": "002158.SZ", "name": "汉钟精机"},
        {"ts_code": "002335.SZ", "name": "科华数据"},
        {"ts_code": "603986.SH", "name": "兆易创新"},
        {"ts_code": "300308.SZ", "name": "中际旭创"},
        {"ts_code": "300394.SZ", "name": "天孚通信"},
        {"ts_code": "688981.SH", "name": "中芯国际"},
        {"ts_code": "300750.SZ", "name": "宁德时代"},
    ]

    def run_backtest(price_df, rules=None, cost_price=None, initial_cash=100000):
        return {"summary": f"回测模块降级：{BACKTESTER_MODULE_ERROR}", "metrics": {}, "signals": pd.DataFrame(), "trades": pd.DataFrame(), "equity_curve": pd.DataFrame()}

    def run_multi_mode_backtests(price_df, base_rules=None, cost_price=None, initial_cash=100000, modes=None):
        return {"reports": {"default": run_backtest(price_df, base_rules, cost_price, initial_cash)}, "summary": f"多模式回测降级：{BACKTESTER_MODULE_ERROR}"}

    def run_batch_strategy_mode_backtests(stock_pool, start_date, end_date, capital, provider="tushare"):
        return {"aggregate": pd.DataFrame(), "details": pd.DataFrame(), "failures": [], "summary": f"批量回测降级：{BACKTESTER_MODULE_ERROR}"}

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


def compact_tech_batch_for_prompt(batch_result):
    if not batch_result:
        return None
    aggregate = batch_result.get("aggregate")
    aggregate_rows = []
    if aggregate is not None and not aggregate.empty:
        keep_cols = [
            "mode",
            "mode_label",
            "avg_return_pct",
            "median_return_pct",
            "avg_max_drawdown_pct",
            "median_max_drawdown_pct",
            "avg_exit_action_win_rate",
            "avg_round_trip_win_rate",
            "avg_trade_count",
            "avg_entry_count",
            "avg_round_trip_count",
            "avg_open_position_count",
            "avg_effective_round_count",
            "avg_profit_factor",
            "avg_sharpe",
            "avg_calmar",
            "positive_stock_count",
            "tested_stock_count",
            "mode_win_count",
            "worst_stock_return_pct",
            "worst_stock_drawdown_pct",
            "avg_reduce_count",
            "avg_reduce_per_effective_round",
        ]
        show = aggregate[[col for col in keep_cols if col in aggregate.columns]].copy()
        aggregate_rows = show.to_dict("records")
    return {
        "summary": batch_result.get("summary", ""),
        "date_range": batch_result.get("date_range", {}),
        "provider": batch_result.get("provider", ""),
        "aggregate": aggregate_rows,
        "failure_count": len(batch_result.get("failures") or []),
    }


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


@st.cache_data(ttl=900, show_spinner=False)
def cached_money_flow_snapshot(ticker, market_type, deep=False, refresh_token=""):
    return call_with_supported_kwargs(
        collect_money_flow_snapshot,
        ticker,
        market_type=market_type,
        deep=deep,
        refresh_token=refresh_token,
    )


@st.cache_data(ttl=900)
def cached_micro_data(ticker, market_type, deep=False):
    return call_with_supported_kwargs(
        fetch_micro_data,
        ticker,
        market_type=market_type,
        deep=deep,
    )


def build_money_flow_snapshot_placeholder(ticker, market_type, message):
    updated_at = datetime.datetime.now().isoformat(timespec="seconds")
    return {
        "ticker": ticker,
        "market_type": market_type,
        "mode": "quick",
        "available": False,
        "partial": False,
        "updated_at": updated_at,
        "data_time": updated_at,
        "warnings": [message] if message else [],
        "errors": [],
        "source_status": {},
        "summary": {"positive": [], "negative": [], "stance": "未运行"},
        "coverage": {"score": 0, "available": [], "missing": []},
        "individual_fund_flow": [],
        "dragon_tiger": [],
        "block_trade": [],
    }


def render_money_flow_snapshot_status(flow):
    flow = flow or {}
    updated_at = flow.get("updated_at") or flow.get("data_time") or ""
    source_status = flow.get("source_status") or {}
    errors = [str(item) for item in flow.get("errors") or [] if str(item).strip()]
    warnings = [str(item) for item in flow.get("warnings") or [] if str(item).strip()]

    if flow.get("available") and not flow.get("partial"):
        st.success("资金穿透数据已更新")
    elif flow.get("available"):
        st.warning("部分资金数据暂不可用，已使用可得数据")
    elif errors:
        st.error("资金快照暂不可用，请稍后刷新；页面继续展示 Tushare 专业事实。")
    elif warnings:
        st.info(warnings[0])
    else:
        st.info("AkShare 资金穿透暂未运行。")

    if updated_at:
        st.caption(f"AkShare 快照时间：{updated_at}")
    if errors:
        for item in errors:
            st.caption(f"AkShare 错误：{item}")
    if source_status:
        with st.expander("AkShare 数据源状态", expanded=False):
            st.json(source_status)


def render_a_share_tushare_money_summary(moneyflow_data, margin_data, dragon_data, chip_radar_data):
    st.markdown("##### Tushare 可验证资金事实")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "moneyflow",
        "可用" if (moneyflow_data or {}).get("available") else "暂无",
        (_fmt_price((moneyflow_data or {}).get("main_net_yi"), "亿") if (moneyflow_data or {}).get("available") else "主力待验证"),
    )
    c2.metric(
        "融资融券",
        "可用" if (margin_data or {}).get("available") else "暂无",
        (_fmt_price((margin_data or {}).get("financing_balance_yi"), "亿") if (margin_data or {}).get("available") else "余额待验证"),
    )
    c3.metric(
        "龙虎榜",
        "可用" if (dragon_data or {}).get("available") else "暂无",
        ((dragon_data or {}).get("latest_date") or (dragon_data or {}).get("message") or "未见上榜"),
    )
    c4.metric(
        "筹码/胜率",
        "可用" if (chip_radar_data or {}).get("available") else "暂无",
        (_fmt_price((chip_radar_data or {}).get("weight_avg")) if (chip_radar_data or {}).get("available") else "筹码待验证"),
    )

    if (moneyflow_data or {}).get("available"):
        st.caption(
            "Tushare moneyflow："
            f"日期 {(moneyflow_data or {}).get('date') or '未知'}，"
            f"主力净流入 {_fmt_price((moneyflow_data or {}).get('main_net_yi'), '亿')}，"
            f"近5日 {_fmt_price((moneyflow_data or {}).get('five_day_main_net_yi'), '亿')}。"
        )
    if (margin_data or {}).get("available"):
        st.caption(
            "Tushare margin_detail："
            f"日期 {(margin_data or {}).get('date') or '未知'}，"
            f"融资余额 {_fmt_price((margin_data or {}).get('financing_balance_yi'), '亿')}，"
            f"融资买入 {_fmt_price((margin_data or {}).get('financing_buy_yi'), '亿')}。"
        )
    if (dragon_data or {}).get("available"):
        st.caption(
            "Tushare top_list："
            f"上榜日期 {(dragon_data or {}).get('latest_date') or '未知'}，"
            f"原因 {(dragon_data or {}).get('reason') or '待核验'}。"
        )
    if (chip_radar_data or {}).get("available"):
        st.caption(
            "Tushare 筹码/胜率："
            f"交易日 {(chip_radar_data or {}).get('trade_date') or '未知'}，"
            f"筹码中枢 {_fmt_price((chip_radar_data or {}).get('weight_avg'))}，"
            f"{(chip_radar_data or {}).get('chip_pressure_comment') or '筹码压力待验证'}"
        )


MARGIN_ETF_POOL_MODES = [
    "精简核心 ETF 池",
    "Tushare 全量发现",
    "同赛道横向比较",
    "人工重点关注池",
]


def _margin_etf_theme_filter_value(theme_label):
    theme_label = (theme_label or "").strip()
    if theme_label == "半导体设备":
        return "半导体设备"
    return theme_label


@st.cache_data(ttl=1800, show_spinner=False)
def cached_margin_etf_discovery_dataset(refresh_token=""):
    result = discover_etf_universe_from_tushare(tushare_adapter=_tushare_adapter)
    result["refresh_token"] = refresh_token
    return result


@st.cache_data(ttl=1800, show_spinner=False)
def cached_margin_etf_daily_dataset(refresh_token="", universe_mode="core", theme_label=""):
    if universe_mode == "manual_focus":
        universe = [item for item in get_default_etf_universe() if item.get("manual_focus", True)]
    else:
        universe = get_default_etf_universe()
    result = fetch_etf_universe_data(
        universe,
        tushare_adapter=_tushare_adapter,
        include_nav=False,
    )
    result["refresh_token"] = refresh_token
    result["universe_mode"] = universe_mode
    result["theme_label"] = theme_label
    return result


@st.cache_data(ttl=1800, show_spinner=False)
def cached_margin_etf_dynamic_packet(refresh_token="", theme_label="", max_per_theme=5, min_amount_ma20=0.0):
    discovery = cached_margin_etf_discovery_dataset(refresh_token)
    dynamic_packet = build_dynamic_etf_universe(
        max_per_theme=max_per_theme,
        min_amount_ma20=min_amount_ma20 or None,
        tushare_adapter=_tushare_adapter,
        discovery_payload=discovery,
    )
    score_packet = dynamic_packet.get("score_packet") or {}
    if theme_label:
        theme_filter = _margin_etf_theme_filter_value(theme_label)
        filtered_rows = [
            row for row in (score_packet.get("rows") or [])
            if theme_filter in {(row.get("theme") or "").strip(), (row.get("sub_theme") or "").strip()}
        ]
        dynamic_packet["theme_score_packet"] = {
            **score_packet,
            "sample_count": len(filtered_rows),
            "rows": filtered_rows,
        }
        dynamic_packet["theme_comparison"] = compare_etfs_within_theme(dynamic_packet["theme_score_packet"], theme=theme_filter)
    else:
        dynamic_packet["theme_score_packet"] = score_packet
        dynamic_packet["theme_comparison"] = {}
    dynamic_packet["refresh_token"] = refresh_token
    return dynamic_packet


@st.cache_data(ttl=300, show_spinner=False)
def cached_margin_etf_intraday_dataset(refresh_token="", universe_mode="core", theme_label=""):
    if universe_mode == "dynamic":
        packet = cached_margin_etf_dynamic_packet(refresh_token=refresh_token, theme_label=theme_label, max_per_theme=8)
        universe = packet.get("universe") or get_default_etf_universe()
    elif universe_mode == "manual_focus":
        universe = [item for item in get_default_etf_universe() if item.get("manual_focus", True)]
    else:
        universe = get_default_etf_universe()
    result = fetch_intraday_etf_snapshot(
        universe,
        tushare_adapter=_tushare_adapter,
    )
    result["refresh_token"] = refresh_token
    result["universe_mode"] = universe_mode
    result["theme_label"] = theme_label
    return result


@st.cache_data(ttl=900, show_spinner=False)
def cached_margin_etf_holdings_snapshot(refresh_token="", etf_codes=None):
    snapshot = fetch_etf_holdings_snapshot(etf_codes or [], max_etfs=20, tushare_adapter=_tushare_adapter)
    snapshot["refresh_token"] = refresh_token
    return snapshot


def _margin_etf_research_ticker():
    return "__MARGIN_ETF_ALLOCATOR__"


def load_margin_etf_research_cache(data_date, profile_hash, market_state, allocation_hash):
    if not supabase:
        return None, ""
    try:
        res = (
            supabase
            .table("stock_reports")
            .select("report_content, created_at")
            .eq("ticker", _margin_etf_research_ticker())
            .eq("report_type", MARGIN_ETF_DAILY_RESEARCH_REPORT_TYPE)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        for row in res.data or []:
            payload, _ = parse_memory_payload(row.get("report_content", ""))
            if (
                str(payload.get("data_date") or "") == str(data_date or "")
                and str(payload.get("account_risk_profile") or "") == str(profile_hash or "")
                and str(payload.get("market_state") or "") == str(market_state or "")
                and str(payload.get("allocation_hash") or "") == str(allocation_hash or "")
            ):
                return payload, row.get("created_at", "")
    except Exception as exc:
        return None, str(exc)
    return None, ""


def render_margin_allocator_module(result, catalog, etf_data_status=None, intraday_snapshot=None, research_payload=None, research_generated_at="", research_cached=False):
    result = result or {}
    catalog = catalog or {}
    account_state = result.get("account_state") or {}
    render_margin_execution_summary(result)

    st.markdown("#### 当前账户状态")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("净资产", _fmt_price(result.get("net_asset"), "¥"))
    c2.metric("当前风险敞口", _fmt_price(result.get("gross_exposure"), "¥"))
    c3.metric("当前融资比例", f"{result.get('current_margin_debt_ratio', 0):.2f}%")
    c4.metric("当前杠杆倍数", f"{result.get('current_leverage_ratio', 0):.2f}x")

    st.caption(
        f"市场状态：{result.get('market_state') or '未知'}｜账户风格：{result.get('style') or '未知'}｜"
        f"融资模式：{result.get('leverage_mode') or '未知'}｜风险级别：{result.get('risk_level') or '待评估'}"
    )
    for note in result.get("notes") or []:
        st.caption(f"提示：{note}")
    for item in result.get("risk_flags") or []:
        st.caption(f"风险：{item}")

    if etf_data_status:
        st.markdown("#### ETF 数据状态")
        render_margin_etf_data_status(etf_data_status)
        st.caption("ETF 实时强弱来自 Tushare 数据与本地规则模型，DeepSeek 仅用于解释，不直接决定仓位。")

    if result.get("daily_adjustment_reason"):
        st.markdown("#### 今日动态调整原因")
        for item in result.get("daily_adjustment_reason") or []:
            st.markdown(f"- {item}")
    st.caption(
        f"数据日期：{result.get('data_date') or '暂无'}｜数据源：{result.get('data_source') or 'rules_only'}｜"
        f"配置生成时间：{result.get('generated_at') or datetime.datetime.now().isoformat(timespec='seconds')}"
    )
    st.caption(result.get("previous_day_change_text") or "暂无上一交易日配置，后续可接入历史配置对比。")

    st.markdown("#### 今日建议 ETF 执行清单")
    render_margin_recommended_etf_plan(result)
    st.markdown("#### bucket 权重概览")
    st.caption("用于查看方向权重，具体 ETF 以上方执行清单为准。")
    render_margin_allocator_chart(result)

    allocation = result.get("recommended_etf_allocation") or {}
    allocation_rows = []
    for label, payload in allocation.items():
        allocation_rows.append(
            {
                "资产桶": label,
                "建议占净资产比例": f"{payload.get('ratio_pct', 0):.2f}%",
                "建议金额": _fmt_price(payload.get("amount"), "¥"),
                "样例ETF": " / ".join((payload.get("candidate_etfs") or [])[:3]) or "现金缓冲",
            }
        )
    if allocation_rows:
        with st.expander("查看 Bucket 金额拆分", expanded=False):
            st.dataframe(pd.DataFrame(allocation_rows), width="stretch", hide_index=True)

    dynamic_weights = result.get("dynamic_bucket_weights") or {}
    if dynamic_weights:
        st.markdown("#### 动态 Bucket 权重")
        render_margin_bucket_weights_table(
            dynamic_weights,
            overweight_buckets=result.get("overweight_buckets"),
            underweight_buckets=result.get("underweight_buckets"),
        )

    if result.get("selected_etf_candidates"):
        st.markdown("#### 候选 ETF")
        render_margin_candidate_table(result.get("selected_etf_candidates"))

    st.markdown("#### ETF 实时强弱表")
    render_etf_score_table({"rows": result.get("etf_score_table") or []})

    if intraday_snapshot:
        st.markdown("#### 盘中 ETF 实时补充")
        render_intraday_etf_snapshot(intraday_snapshot)

    if catalog:
        with st.expander("内置 ETF 池", expanded=False):
            st.json(catalog)

    st.markdown("#### 风险线")
    for item in result.get("risk_lines") or []:
        st.markdown(f"- {item}")

    risk_cols = st.columns(2)
    with risk_cols[0]:
        st.markdown("#### 触发条件")
        for item in result.get("trigger_conditions") or []:
            st.markdown(f"- {item}")
    with risk_cols[1]:
        st.markdown("#### 失效条件")
        for item in result.get("invalid_conditions") or []:
            st.markdown(f"- {item}")

    scores = result.get("scores") or {}
    if scores:
        st.markdown("#### 风险预算分解")
        st.caption("风险预算分只解释建议背后的结构，不直接替代执行摘要。")
        score_rows = [
            {"维度": label, "分值": value}
            for label, value in scores.items()
        ]
        st.dataframe(pd.DataFrame(score_rows), width="stretch", hide_index=True)

    st.markdown("#### DeepSeek 调研解释")
    render_margin_etf_research_summary(research_payload, generated_at=research_generated_at, cached=research_cached)


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
    try:
        result = action()
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        error_type = type(exc).__name__
        fallback = {
            "available": False,
            "ok": False,
            "message": "该阶段暂不可用，已跳过",
            "error_type": error_type,
            "error": str(exc),
        }
        (status_box or st).write(f"该阶段暂不可用，已跳过：{error_type}")
        if status_box is None:
            st.caption(f"阶段：{label}，用时 {elapsed:.1f}s")
        return fallback

    elapsed = time.perf_counter() - start_time
    result_has_data = has_data(result) if callable(has_data) else _progress_result_has_data(result)
    if result_has_data:
        (status_box or st).write(f"完成：{label}，用时 {elapsed:.1f}s")
    else:
        (status_box or st).write(f"完成：{label}，用时 {elapsed:.1f}s。该项暂无可验证数据，继续分析")
    return result


def build_verified_technical_fact_packet(technical_snapshot):
    """Normalize already-computed technical metrics for prompt fact packets."""
    technical = technical_snapshot or {}
    field_map = [
        ("latest_close", "latest_close", "收盘价"),
        ("ma60", "ma60", "MA60"),
        ("ma60_state", "ma60_state", "MA60状态"),
        ("rsi_14", "rsi", "RSI-14"),
        ("volume_vs_20d", "volume_vs_20d", "量能/20日"),
        ("return_20d", "return_20d", "20日涨跌"),
        ("return_60d", "return_60d", "60日涨跌"),
        ("drawdown_60d", "drawdown_60d", "60日回撤"),
        ("market_date", "data_asof", "行情日期"),
        ("confidence", "confidence", "技术指标可信度"),
    ]

    packet = {
        "available": bool(technical and _num(technical.get("confidence"), 0) > 0),
        "latest_close": "",
        "ma60": "",
        "ma60_state": "",
        "rsi_14": "",
        "volume_vs_20d": "",
        "return_20d": "",
        "return_60d": "",
        "drawdown_60d": "",
        "market_date": "",
        "source": technical.get("source") or "yfinance / compute_technical_snapshot",
        "confidence": "",
        "missing": list(technical.get("missing") or []),
    }

    for output_key, source_key, label in field_map:
        value = technical.get(source_key)
        if value is None or value == "":
            packet["missing"].append(label)
            packet[output_key] = ""
        else:
            packet[output_key] = value

    packet["missing"] = list(dict.fromkeys(str(item) for item in packet["missing"] if item))
    return packet


def format_verified_technical_facts_for_prompt(verified_technical_facts):
    facts = verified_technical_facts or build_verified_technical_fact_packet({})

    def fact_value(key):
        value = facts.get(key)
        return value if value not in [None, ""] else "暂无可验证数据"

    missing = facts.get("missing") or []
    missing_text = "、".join(str(item) for item in missing) if missing else "无"
    available_text = "可用" if facts.get("available") else "不可用或覆盖不足"
    return f"""
【已验证技术事实】
- 可用状态：{available_text}
- 收盘价：{fact_value("latest_close")}
- MA60状态：{fact_value("ma60_state")}（MA60：{fact_value("ma60")}）
- RSI-14：{fact_value("rsi_14")}
- 量能/20日：{fact_value("volume_vs_20d")}
- 20日涨跌：{fact_value("return_20d")}
- 60日涨跌：{fact_value("return_60d")}
- 60日回撤：{fact_value("drawdown_60d")}
- 行情日期：{fact_value("market_date")}
- 数据源：{fact_value("source")}
- 技术指标可信度：{fact_value("confidence")}
- 缺失项：{missing_text}

约束：以上字段存在时，不得再表述为缺少该技术项数据。RSI、MA、量能、涨跌幅、回撤只用于观察条件和验证条件，不得直接推导确定性买卖结论。
强制规则：RSI 高位不等于必跌，RSI 低位不等于必涨；站上 MA60 不等于买入信号；量能放大/缩小不得单独推断主力行为；技术事实必须和 moneyflow、龙虎榜、涨跌停、融资融券分层，不得混为同一类证据。
"""


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


def normalize_news_title(title):
    text = str(title or "").strip().lower()
    text = re.sub(r"\s+-\s+[^-｜|]{2,60}$", "", text)
    text = re.sub(r"[｜|]\s*(新浪财经|东方财富|搜狐网|财富号|yahoo finance|seeking alpha).*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(不斷更新|不断更新|快讯|快報|异动快报|股市要闻|市场)$", "", text, flags=re.IGNORECASE)
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def build_dedupe_key(title, source=None, date=None):
    normalized = normalize_news_title(title)
    parsed = _parse_datetime_safe(date)
    day = parsed.date().isoformat() if parsed else ""
    return "|".join(part for part in [normalized, day] if part) or str(source or title or "")


def _news_row_age_hours(row):
    created = _parse_datetime_safe((row or {}).get("created_at"))
    if not created:
        return None
    return max(0.0, (datetime.datetime.now() - created).total_seconds() / 3600)


SHORT_TICKER_STRONG_NOISE_TERMS = [
    "litefinance",
    "lite finance",
    "forex",
    "gold price",
    "xau",
    "trading platform",
]
SHORT_TICKER_WEAK_NOISE_TERMS = ["broker"]
SHORT_TICKER_COMPANY_TERMS = ["lumentum", "lumentum holdings"]


def alias_matches_news_text(text, alias, market_type=None):
    raw_alias = str(alias or "").strip()
    if len(raw_alias) < 2:
        return False

    text = str(text or "")
    alias_l = raw_alias.lower()
    text_l = text.lower()

    if raw_alias.isdigit() and len(raw_alias) == 6:
        return bool(re.search(rf"(?<!\d){re.escape(raw_alias)}(?!\d)", text))
    if alias_l.isdigit():
        return bool(re.search(rf"(?<!\d){re.escape(alias_l)}(?!\d)", text_l))
    if len(alias_l) <= 5 and alias_l.isascii():
        return bool(re.search(rf"\b{re.escape(alias_l)}\b", text_l))
    return alias_l in text_l


def _short_ticker_news_noise(text, terms):
    text_l = str(text or "").lower()
    if any(term in text_l for term in SHORT_TICKER_COMPANY_TERMS):
        return False
    has_strong_noise = any(term in text_l for term in SHORT_TICKER_STRONG_NOISE_TERMS)
    has_weak_noise = any(term in text_l for term in SHORT_TICKER_WEAK_NOISE_TERMS)
    if not has_strong_noise and not has_weak_noise:
        return False
    if has_weak_noise and not has_strong_noise:
        return False
    for term in terms or []:
        term_l = str(term or "").strip().lower()
        if len(term_l) <= 5 and term_l.isascii() and alias_matches_news_text(text_l, term_l):
            return True
    return False


def _news_query_aliases(keyword):
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    aliases = [keyword]
    try:
        profile = get_supply_chain_profile(keyword.upper())
        aliases.extend([profile.get("name", ""), *(profile.get("aliases") or [])])
    except Exception:
        pass
    return [term for term in dict.fromkeys(str(alias or "").strip() for alias in aliases) if len(term) >= 2]


def _news_primary_hit(row, stock_code=None, stock_name=None):
    terms = []
    for value in [stock_code, stock_name]:
        value = str(value or "").strip()
        if not value:
            continue
        terms.append(value)
        if "." in value:
            terms.append(value.split(".", 1)[0])
    terms = [term for term in dict.fromkeys(terms) if len(term) >= 2]
    if not terms:
        return True
    blob = " ".join(str((row or {}).get(key, "")) for key in ["keyword", "title", "summary", "url"]).lower()
    for term in terms:
        if alias_matches_news_text(blob, term):
            return True
    return False


def _is_broad_auto_news(row):
    keyword = str((row or {}).get("keyword") or "")
    source = str((row or {}).get("source") or "").lower()
    title = str((row or {}).get("title") or "").lower()
    if keyword in {"A股新趋势", "港股新趋势", "全球新趋势", "机构游资调仓", "黄金", "AI算力"}:
        return True
    broad_source_terms = [
        "gold+price+market",
        "%E6%9C%BA%E6%9E%84%E8%B0%83%E4%BB%93",
        "%E6%B6%A8%E5%81%9C+%E6%9D%BF%E5%9D%97",
        "%E6%B8%AF%E8%82%A1+OR",
    ]
    if any(term.lower() in source for term in broad_source_terms):
        return True
    return any(term in title for term in ["恒指", "港股市況", "港股走势", "港股走勢", "gold price forecast"])


def _news_source_quality(row):
    text = " ".join(str((row or {}).get(key, "")) for key in ["title", "source", "url"]).lower()
    reliable_terms = ["证券时报", "上交所", "深交所", "巨潮", "公告", "新华网", "21财经", "财联社", "yahoo finance", "bloomberg", "reuters", "sec.gov"]
    noisy_terms = ["财富号", "股吧", "搜狐", "reddit", "seeking alpha", "motley fool", "gold price forecast"]
    score = 0
    if any(term.lower() in text for term in reliable_terms):
        score += 12
    if any(term.lower() in text for term in noisy_terms):
        score -= 10
    return score


def filter_news_clues_for_prompt(rows, stock_code=None, stock_name=None, max_items=8, hours=48):
    scored = []
    seen = set()
    requires_primary_hit = bool(str(stock_code or "").strip() or str(stock_name or "").strip())

    for row in rows or []:
        title = str((row or {}).get("title") or "").strip()
        if not title:
            continue
        key = normalize_news_title(title)
        if key in seen:
            continue
        seen.add(key)

        if requires_primary_hit and not _news_primary_hit(row, stock_code=stock_code, stock_name=stock_name):
            continue
        terms = []
        for value in [stock_code, stock_name]:
            value = str(value or "").strip()
            if value:
                terms.append(value)
                if "." in value:
                    terms.append(value.split(".", 1)[0])
        blob = " ".join(str((row or {}).get(key, "")) for key in ["keyword", "title", "summary", "url"])
        if terms and _short_ticker_news_noise(blob, terms):
            continue

        age = _news_row_age_hours(row)
        if age is not None and age > float(hours or 48):
            continue

        risk_tag = str((row or {}).get("risk_tag") or "")
        score = 50
        if age is not None and age <= 24:
            score += 20
        elif age is not None and age <= 48:
            score += 10
        if risk_tag and risk_tag not in {"普通新闻", "未知"}:
            score += 16
        if _news_primary_hit(row, stock_code=stock_code, stock_name=stock_name):
            score += 18
        if _is_broad_auto_news(row):
            score -= 25
        score += _news_source_quality(row)

        item = dict(row)
        item["normalized_title"] = normalize_news_title(title)
        item["dedupe_key"] = key
        item["clue_score"] = max(0, min(100, score))
        item["verification_status"] = "新闻线索，需公告/交易所/Tushare/原文进一步验证"
        item["fact_boundary"] = "risk_tag/sentiment/标题均不得替代官方公告或结构化事实"
        scored.append(item)

    scored.sort(key=lambda item: (item.get("clue_score", 0), item.get("created_at", "")), reverse=True)
    return scored[:max_items]


def filter_topic_news_for_prompt(rows, max_items=8, per_topic=2, hours=48):
    filtered = filter_news_clues_for_prompt(rows, max_items=max(max_items * 3, 12), hours=hours)
    counts = {}
    result = []
    for row in filtered:
        topic = str(row.get("keyword") or row.get("source") or "unknown")
        if counts.get(topic, 0) >= per_topic:
            continue
        counts[topic] = counts.get(topic, 0) + 1
        result.append(row)
        if len(result) >= max_items:
            break
    return result


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


def _section_has_rows(section):
    section = section or {}
    return bool(section.get("available") or section.get("rows") or section.get("records_available"))


def _extract_pledge_ratio(pledge_section):
    pledge_section = pledge_section or {}
    for row in pledge_section.get("rows") or []:
        if not isinstance(row, dict):
            continue
        for key in ["pledge_ratio", "p_total_ratio", "h_total_ratio"]:
            value = _num(row.get(key))
            if value is not None:
                return value
    return None


def _date_age_days_yyyymmdd(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        if re.fullmatch(r"\d{8}", text):
            parsed = datetime.datetime.strptime(text, "%Y%m%d")
            return max(0, (datetime.datetime.now() - parsed).days)
    except Exception:
        return None
    return _age_days(text)


def build_local_risk_radar_items(tianyan_packet):
    """Coarse local risk tiering from structured facts. Does not parse DeepSeek text."""
    packet = tianyan_packet or {}
    trading = packet.get("verified_trading_structure_risks") or {}
    hard = packet.get("verified_hard_risks") or {}
    chip_risks = packet.get("verified_chip_risks") or {}
    clues = packet.get("sentiment_and_unverified_clues") or {}

    moneyflow = trading.get("moneyflow") or {}
    dragon_tiger = trading.get("dragon_tiger") or {}
    chip_radar = chip_risks.get("chip_radar") or {}
    announcements = hard.get("announcements") or {}
    free_ann = hard.get("free_announcement_radar") or {}
    holder_reduction = hard.get("holder_reduction") or {}
    pledge = hard.get("pledge") or {}
    news_digest = clues.get("news_digest") or {}

    today_main = _num(moneyflow.get("main_net_yi") if moneyflow.get("main_net_yi") != "" else moneyflow.get("main_net_inflow_yi"))
    five_day_main = _num(
        moneyflow.get("five_day_main_net_yi")
        if moneyflow.get("five_day_main_net_yi") != ""
        else moneyflow.get("five_day_main_net_inflow_yi")
    )
    pledge_ratio = _extract_pledge_ratio(pledge)
    has_reduction = _section_has_rows(holder_reduction) or any("减持" in str(flag) for flag in holder_reduction.get("risk_flags") or [])
    has_announcement_gap = not (_section_has_rows(announcements) or _section_has_rows(free_ann))
    has_news_gap = not _section_has_rows(news_digest)

    red_items = []
    orange_items = []
    yellow_items = []
    improvement_items = []

    if has_reduction and pledge_ratio is not None and pledge_ratio > 15 and five_day_main is not None and five_day_main < 0:
        red_items.append("减持、较高质押与近5日主力流出叠加，风险权重上升")
    if has_reduction:
        orange_items.append("存在股东减持记录，需跟踪进展公告")
    if pledge_ratio is not None and pledge_ratio > 15:
        orange_items.append(f"质押比例约 {pledge_ratio:.2f}%，高于 15% 观察阈值")
    if five_day_main is not None and five_day_main < 0:
        orange_items.append(f"近5日主力净流出 {five_day_main:.2f} 亿，中期资金面仍需验证")
    if today_main is not None and five_day_main is not None and today_main > 0 and five_day_main < 0:
        orange_items.append("今日主力净流入但近5日仍流出，中期资金面仍未扭转")
    if has_announcement_gap:
        yellow_items.append("公告结构化结果缺失，这是信息缺口，不是无风险")
    if has_news_gap:
        yellow_items.append("news_digest 缺失，最新新闻摘要线索不足")
    if not _section_has_rows(chip_radar):
        yellow_items.append("筹码/胜率数据缺失，关键成交密集区需要降级处理")
    dragon_age = _date_age_days_yyyymmdd(dragon_tiger.get("latest_date") or dragon_tiger.get("trade_date"))
    if dragon_age is not None and dragon_age > 5:
        yellow_items.append("龙虎榜超过5天，只能作为历史参考")
    elif not _section_has_rows(dragon_tiger):
        yellow_items.append("龙虎榜结构化结果缺失或未上榜，席位线索不足")
    if today_main is not None and today_main > 0 and five_day_main is not None and five_day_main < 0:
        improvement_items.append("短线修复，未确认反转")
    elif today_main is not None and today_main > 0 and five_day_main is not None and five_day_main > 0:
        improvement_items.append("资金趋势改善")
    elif today_main is not None and today_main > 0:
        improvement_items.append("今日主力资金边际流入")

    return {
        "red_items": red_items,
        "orange_items": orange_items,
        "yellow_items": yellow_items,
        "improvement_items": improvement_items,
        "has_reduction_risk": has_reduction,
        "pledge_ratio": pledge_ratio,
        "has_announcement_gap": has_announcement_gap,
        "has_news_gap": has_news_gap,
        "today_main_net_yi": today_main,
        "five_day_main_net_yi": five_day_main,
    }


def build_position_profile(ticker, current_price, cost_price, holding_units, capital_plan, position_status, currency):
    current = _num(current_price)
    cost = _num(cost_price)
    units = _num(holding_units, 0) or 0
    capital = _num(capital_plan, 0) or 0
    position_text = str(position_status)
    selected_new = position_text.startswith("未买入")
    selected_add = position_text.startswith("想加仓")
    selected_holding = position_text.startswith("已持有") or selected_add
    has_cost = bool(cost and cost > 0)
    has_units = units > 0
    position_warning = ""

    if has_units:
        normalized_position_state = "已持仓"
        position_confidence = "高"
        allow_pnl = True
        allow_t_plan = True
        allow_reduce_plan = True
        allow_trial_entry = False
        if selected_new:
            position_confidence = "中"
            position_warning = "用户选择未买入，但填写了持仓数量，系统按已持仓处理，请核对输入"
    elif selected_holding:
        normalized_position_state = "已持仓但缺少持仓数量"
        position_confidence = "低"
        allow_pnl = False
        allow_t_plan = False
        allow_reduce_plan = False
        allow_trial_entry = False
        position_warning = "用户选择已持仓，但缺少持仓数量，持仓计划将按低置信度处理"
    elif has_cost:
        normalized_position_state = "未买入，有参考成本/计划价格"
        position_confidence = "中"
        allow_pnl = False
        allow_t_plan = False
        allow_reduce_plan = False
        allow_trial_entry = True
    else:
        normalized_position_state = "未买入，纯观察"
        position_confidence = "高"
        allow_pnl = False
        allow_t_plan = False
        allow_reduce_plan = False
        allow_trial_entry = False

    is_adding = selected_add and has_units
    is_holding = normalized_position_state == "已持仓"
    intent = "add" if is_adding else ("hold" if is_holding else "new")
    pnl_pct = None
    pnl_amount = None
    state = "未输入成本价"
    reference_cost_text = ""
    if has_cost:
        reference_cost_text = f"{cost:.3f}".rstrip("0").rstrip(".")
        if "." not in reference_cost_text:
            reference_cost_text += ".0"

    if allow_pnl and current and has_cost:
        pnl_pct = round((current / cost - 1) * 100, 2)
        pnl_amount = round((current - cost) * units, 2)
        if pnl_pct > 0:
            state = f"浮盈 {pnl_pct:.2f}%"
        elif pnl_pct < 0:
            state = f"浮亏 {abs(pnl_pct):.2f}%"
        else:
            state = "接近成本"
    elif normalized_position_state == "未买入，有参考成本/计划价格":
        state = f"未买入；{reference_cost_text}元为参考成本/计划价格，不计算浮盈浮亏。"
    elif normalized_position_state == "未买入，纯观察":
        state = "未买入；未填写参考成本，不计算浮盈浮亏。"
    elif normalized_position_state == "已持仓但缺少持仓数量":
        state = "已选择持仓状态，但缺少持仓数量，不计算精确浮盈浮亏。"
    elif allow_pnl and not has_cost:
        state = "已持仓；未填写成本价，不计算浮盈浮亏。"

    return {
        "ticker": ticker,
        "position_status": position_status,
        "normalized_position_state": normalized_position_state,
        "position_confidence": position_confidence,
        "position_warning": position_warning,
        "allow_pnl": allow_pnl,
        "allow_t_plan": allow_t_plan,
        "allow_reduce_plan": allow_reduce_plan,
        "allow_trial_entry": allow_trial_entry,
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
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    [data-testid="stMainMenu"],
    [data-testid="stDeployButton"],
    footer {
        visibility: hidden !important;
        display: none !important;
        height: 0 !important;
    }
    .stAppDeployButton,
    .stAppToolbar,
    #MainMenu {
        visibility: hidden !important;
        display: none !important;
    }
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


def inject_ui_animations():
    st.markdown("""
    <style>
        :root {
            --hf-ios-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
            --hf-ios-shadow-soft: 0 10px 24px rgba(17, 17, 20, 0.06);
            --hf-ios-shadow-hover: 0 14px 30px rgba(17, 17, 20, 0.10);
            --hf-ios-glow: 0 0 0 rgba(255, 59, 48, 0);
            --hf-ios-glow-peak: 0 0 0 6px rgba(255, 59, 48, 0.06);
        }

        .hf-ios-section {
            position: relative;
        }

        .hf-ios-fade-up {
            opacity: 0;
            transform: translateY(8px);
            animation: hf-ios-fade-up 360ms var(--hf-ios-ease) both;
            will-change: opacity, transform;
        }

        .hf-ios-fade-in {
            opacity: 0;
            animation: hf-ios-fade-in 260ms var(--hf-ios-ease) both;
            will-change: opacity;
        }

        .hf-ios-stagger-1 { animation-delay: 40ms; }
        .hf-ios-stagger-2 { animation-delay: 110ms; }
        .hf-ios-stagger-3 { animation-delay: 180ms; }

        .hf-ios-card {
            transition: transform 220ms var(--hf-ios-ease), box-shadow 220ms var(--hf-ios-ease);
            will-change: transform, box-shadow;
        }

        .hf-ios-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--hf-ios-shadow-hover);
        }

        .hf-ios-soft-glow {
            box-shadow: var(--hf-ios-shadow-soft), var(--hf-ios-glow);
            animation: hf-ios-soft-glow 2.8s ease-in-out 3 both;
        }

        .ming-hero {
            box-shadow: var(--hf-ios-shadow-soft);
            border-radius: 20px;
            padding-left: 16px;
            padding-right: 16px;
        }

        @keyframes hf-ios-fade-up {
            from {
                opacity: 0;
                transform: translateY(8px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes hf-ios-fade-in {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
        }

        @keyframes hf-ios-soft-glow {
            0%, 100% {
                box-shadow: var(--hf-ios-shadow-soft), var(--hf-ios-glow);
            }
            50% {
                box-shadow: var(--hf-ios-shadow-soft), var(--hf-ios-glow-peak);
            }
        }

        @media (max-width: 768px) {
            .ming-hero {
                border-radius: 16px;
                padding-left: 12px;
                padding-right: 12px;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            * {
                animation: none !important;
                transition: none !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)


inject_ui_animations()

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


def render_legacy_data_status(module_name, status="未刷新", updated_at="", data_source="未加载", deepseek_status="未调用"):
    st.caption(
        f"{module_name}｜当前数据状态：{status}｜"
        f"最后刷新时间：{updated_at or '暂无'}｜"
        f"数据来源：{data_source or '未加载'}｜"
        f"DeepSeek：{deepseek_status or '未调用'}"
    )
    if status == "未刷新":
        st.info("当前未运行，请点击按钮获取最新数据。")

# ==========================================
# 2. 核心功能与缓存提速优化
# ==========================================
@st.cache_data(ttl=300)
def get_current_price_detail(ticker, market_type=None):
    normalized = normalize_ticker(ticker)
    detected_market = market_type or infer_market_type(normalized)

    if str(detected_market or "").upper().startswith("A_SHARE"):
        try:
            quote = fetch_realtime_quote(normalized, market_type=detected_market, provider="tushare")
            price = _num((quote or {}).get("price"))
            if price is not None:
                return {
                    "ticker": normalized,
                    "price": round(price, 2),
                    "price_source": "tushare_daily_close",
                    "data_date": (quote or {}).get("asof") or "",
                    "raw_source": (quote or {}).get("source") or "tushare",
                    "fallback": False,
                    "warning": (quote or {}).get("warning") or "",
                }
        except Exception as exc:
            tushare_warning = str(exc)
        else:
            tushare_warning = (quote or {}).get("warning") or "Tushare daily close unavailable"
    else:
        tushare_warning = ""

    try:
        hist = yf.Ticker(normalized).history(period='1d')
        if hist is not None and not hist.empty and "Close" in hist.columns:
            data_date = ""
            try:
                data_date = str(hist.index[-1].date())
            except Exception:
                data_date = ""
            return {
                "ticker": normalized,
                "price": round(float(hist["Close"].iloc[-1]), 2),
                "price_source": "yfinance_fallback" if str(detected_market or "").upper().startswith("A_SHARE") else "yfinance",
                "data_date": data_date,
                "raw_source": "yfinance",
                "fallback": bool(str(detected_market or "").upper().startswith("A_SHARE")),
                "warning": tushare_warning,
            }
    except Exception as exc:
        return {
            "ticker": normalized,
            "price": None,
            "price_source": "unavailable",
            "data_date": "",
            "raw_source": "",
            "fallback": bool(str(detected_market or "").upper().startswith("A_SHARE")),
            "warning": tushare_warning or str(exc),
        }

    return {
        "ticker": normalized,
        "price": None,
        "price_source": "unavailable",
        "data_date": "",
        "raw_source": "",
        "fallback": bool(str(detected_market or "").upper().startswith("A_SHARE")),
        "warning": tushare_warning,
    }


@st.cache_data(ttl=300)
def get_current_price(ticker):
    return get_current_price_detail(ticker).get("price")

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


@st.cache_data(ttl=900, show_spinner=False)
def get_command_center_mock_packet(cache_version="command_center_2_mock_v1"):
    updated_at = datetime.datetime.now().isoformat(timespec="seconds")
    return {
        "score": 78,
        "trend_label": "偏强震荡上行",
        "probability": 67,
        "confidence": "中高",
        "one_sentence": "下一波更可能先分化后强化，主线偏 AI 硬件 / 电力设备。",
        "updated_at": updated_at,
        "account_snapshot": {
            "net_asset": 900000,
            "cash": 200000,
            "stock_value": 600000,
            "etf_value": 100000,
            "margin_debt": 100000,
            "available_cash": 200000,
            "available_margin": 50000,
        },
        "allocation_budget": {
            "risk_budget_amount": 108000,
            "next_ticket_budget_amount": 45000,
            "etf_budget_amount": 180000,
            "cash_buffer_amount": 180000,
            "max_add_amount": 50000,
            "suggested_adjustment_amount": 30000,
        },
        "market_context": {
            "source": "mock_packet",
            "status": "缓存 / mock 展示",
            "risk_temperature": "中性偏暖",
            "note": "页面加载不触发 Tushare 批量请求、AkShare 资金扫描或 DeepSeek。",
        },
        "quant_output": {
            "label": "中性偏强",
            "summary": "未来 5-10 个交易日更像震荡抬升，确认点在量能与主线持续性。",
        },
        "discipline_output": {
            "label": "纪律允许观察",
            "summary": "仓位动作必须等待验证信号，不因单日强势直接追高。",
        },
        "fusion_output": {
            "label": "条件看多",
            "summary": "只有资金、趋势、量价至少三项共振时才升级动作。",
            "composite_score": 78,
            "win_rate": "62%",
            "suggested_position": "12% 观察仓",
            "suggested_amount": 108000,
            "amount_basis": "按风险预算",
        },
        "path_projection": [
            {"day": 1, "乐观路径": 100, "中性路径": 100, "谨慎路径": 100},
            {"day": 2, "乐观路径": 102, "中性路径": 101, "谨慎路径": 99},
            {"day": 3, "乐观路径": 104, "中性路径": 101.5, "谨慎路径": 98},
            {"day": 5, "乐观路径": 107, "中性路径": 103, "谨慎路径": 97},
            {"day": 8, "乐观路径": 111, "中性路径": 105, "谨慎路径": 95},
            {"day": 10, "乐观路径": 114, "中性路径": 106, "谨慎路径": 94},
        ],
        "discipline_checks": [
            {"title": "历史胜率", "value": "62%", "status": "满足", "description": "mock 回测摘要显示规则胜率高于最低阈值。"},
            {"title": "回撤容忍", "value": "12%", "status": "待验证", "description": "当前仅为纪律阈值，未读取最新真实组合回撤。"},
            {"title": "加仓条件", "value": "三信号共振", "status": "待验证", "description": "需要资金、趋势、量价至少三项同步。"},
            {"title": "止盈/减仓规则", "value": "跌破 MA20 或放量失守", "status": "满足", "description": "规则已明确，但未自动执行。"},
            {"title": "验证信号", "value": "次日延续", "status": "待验证", "description": "等待下一交易日量价与资金确认。"},
        ],
        "validated_data": [
            "当前页面使用 mock packet；真实数据接入尚未启用。",
            "DeepSeek 调用次数由顶部 token counter 验证。",
            "旧交易纪律实验室和量化推演页面保留在旧版工作台。",
        ],
        "cautious_inference": [
            "谨慎推断：如果量能无法延续，偏强判断需要降级。",
            "投喂资料观点 / 待验证：AI 硬件和电力设备可能继续占优。",
            "谨慎推断：下一波可能先分化，再由核心主线强化。",
        ],
        "watchlist": [
            "观察资金是否从高位题材扩散到低位补涨。",
            "观察主线 ETF 是否保持相对强度。",
            "观察风险因子是否从黄色信息缺口升级为橙色风险。",
        ],
        "signal_confluence": [
            {"name": "资金流", "strength": "中高", "status": "短线正向", "evaluation": "正向", "comment": "mock：资金回流但仍需次日验证。"},
            {"name": "趋势强度", "strength": "高", "status": "偏强", "evaluation": "正向", "comment": "mock：趋势仍在上行通道内。"},
            {"name": "量价结构", "strength": "中", "status": "待确认", "evaluation": "观察", "comment": "mock：量能延续性是关键。"},
            {"name": "题材热度", "strength": "中高", "status": "分化强化", "evaluation": "正向", "comment": "mock：核心题材占优，非核心分化。"},
            {"name": "风险因子", "strength": "中", "status": "黄色信息缺口", "evaluation": "观察", "comment": "mock：未读取公告和实时监管数据。"},
        ],
        "next_observation_targets": [
            {"code": "002008", "name": "大族激光", "theme": "AI 硬件 / 设备", "focus": "量价能否延续", "action_state": "观察", "observation_budget": 45000, "single_ticket_amount": 15000, "budget_basis": "按风险预算", "ticket_basis": "按可用现金"},
            {"code": "512480", "name": "半导体 ETF", "theme": "芯片", "focus": "相对强度与成交额", "action_state": "等待验证", "observation_budget": 45000, "single_ticket_amount": 15000, "budget_basis": "按风险预算", "ticket_basis": "按可用现金"},
            {"code": "159819", "name": "AI ETF", "theme": "人工智能", "focus": "主线热度是否扩散", "action_state": "观察", "observation_budget": 45000, "single_ticket_amount": 15000, "budget_basis": "按风险预算", "ticket_basis": "按可用现金"},
        ],
    }


def clone_command_center_packet(packet):
    return json.loads(json.dumps(packet or {}, ensure_ascii=False, default=str))


def refresh_command_center_market_context(packet):
    payload = clone_command_center_packet(packet)
    payload["market_context"] = {
        "source": "local_light_refresh",
        "status": "已轻量刷新",
        "risk_temperature": "中性偏暖",
        "note": "本次只更新本地 mock 市场环境，不调用 Tushare / AkShare 批量接口。",
    }
    payload["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    payload.setdefault("validated_data", [])
    payload["validated_data"] = [
        "已轻量刷新市场环境：未触发外部重接口。",
        *payload["validated_data"][:5],
    ]
    return payload


def generate_command_center_fusion(packet, target="", market_badge=""):
    payload = clone_command_center_packet(packet)
    allocation = payload.get("allocation_budget") or {}
    payload.update(
        {
            "score": 80,
            "trend_label": "偏强但需验证",
            "probability": 69,
            "confidence": "中高",
            "one_sentence": f"{target or '当前标的'} 下一波更适合等资金、趋势、量价三项共振后再升级动作。",
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
    )
    payload["fusion_output"] = {
        "label": "等待三信号共振",
        "summary": f"{market_badge or '当前市场'} 采用条件化观察，DeepSeek 不参与本地评分。",
        "composite_score": 80,
        "win_rate": "64%",
        "suggested_position": "12% 观察仓",
        "suggested_amount": allocation.get("risk_budget_amount", 108000),
        "amount_basis": "按风险预算",
    }
    return payload


def run_command_center_discipline_validation(packet):
    payload = clone_command_center_packet(packet)
    payload["discipline_checks"] = [
        {"title": "历史胜率", "value": "64%", "status": "满足", "description": "使用缓存 / mock 回测摘要，达到观察阈值。"},
        {"title": "回撤容忍", "value": "12%", "status": "满足", "description": "当前纪律允许的最大回撤边界清晰。"},
        {"title": "加仓条件", "value": "资金 + 趋势 + 量价", "status": "待验证", "description": "加仓必须等待三项共振，不因单项信号行动。"},
        {"title": "止盈/减仓规则", "value": "失守关键位减仓", "status": "满足", "description": "减仓条件已明确，可用于后续真实链路接入。"},
        {"title": "验证信号", "value": "次日确认", "status": "待验证", "description": "仍需下一交易日验证，不把假设写成事实。"},
    ]
    payload["discipline_output"] = {
        "label": "纪律通过但需验证",
        "summary": "允许观察，不允许因为单次推演直接提高仓位。",
    }
    payload["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    return payload


def _cc_first_text(*values, default=""):
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _cc_round(value, digits=2):
    parsed = _num(value)
    if parsed is None:
        return None
    return round(float(parsed), digits)


def _cc_list(value, limit=3):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()][:limit]
    return [str(value).strip()][:limit]


def _cc_ticker_base(value):
    text = str(value or "").strip().upper()
    return text.split(".")[0] if text else ""


def _cc_now():
    return cc_service.command_center_now()


COMMAND_CENTER_MODULE_META_KEY = cc_service.COMMAND_CENTER_MODULE_META_KEY
COMMAND_CENTER_MODULE_STATE_KEY = cc_service.COMMAND_CENTER_MODULE_STATE_KEY


def _cc_module_meta():
    return cc_service.module_meta(st.session_state)


def _cc_mark_module(module_key, status, source, error=""):
    return cc_service.mark_module(st.session_state, module_key, status, source, error)


def _cc_get_module_meta(module_key):
    return cc_service.get_module_meta(st.session_state, module_key)


def _cc_build_margin_etf_daily_params(force_light=False):
    pool_source = st.session_state.get("margin_etf_pool_source") or MARGIN_ETF_POOL_MODES[0]
    if force_light and pool_source in {"Tushare 全量发现", "同赛道横向比较"}:
        pool_source = "精简核心 ETF 池"
    compare_theme = st.session_state.get("margin_etf_compare_theme") or (COMPARISON_THEMES[0] if COMPARISON_THEMES else "")
    dynamic_max_per_theme = int(st.session_state.get("margin_etf_dynamic_max_per_theme") or 5)
    min_amount_ma20 = float(st.session_state.get("margin_etf_min_amount_ma20") or 0.0)
    params = {
        "pool_source": pool_source,
        "compare_theme": compare_theme if pool_source == "同赛道横向比较" else "",
        "dynamic_max_per_theme": dynamic_max_per_theme,
        "min_amount_ma20": min_amount_ma20,
    }
    params_hash = hashlib.sha256(
        json.dumps(params, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return params, params_hash


def build_command_center_margin_etf_daily_packet(refresh_token, force_light=False):
    params, params_hash = _cc_build_margin_etf_daily_params(force_light=force_light)
    pool_source = params["pool_source"]
    compare_theme = params["compare_theme"]
    dynamic_max_per_theme = int(params["dynamic_max_per_theme"])
    min_amount_ma20 = float(params["min_amount_ma20"])
    theme_comparison = {}
    holdings_snapshot = {}
    if pool_source == "Tushare 全量发现":
        dynamic_packet = cached_margin_etf_dynamic_packet(
            refresh_token=refresh_token,
            max_per_theme=dynamic_max_per_theme,
            min_amount_ma20=min_amount_ma20,
        )
        daily_dataset = dynamic_packet.get("data_status") or {}
        score_packet = dynamic_packet.get("score_packet") or {"rows": []}
        current_universe = dynamic_packet.get("universe") or get_default_etf_universe()
    elif pool_source == "同赛道横向比较":
        dynamic_packet = cached_margin_etf_dynamic_packet(
            refresh_token=refresh_token,
            theme_label=compare_theme,
            max_per_theme=max(dynamic_max_per_theme, 8),
            min_amount_ma20=min_amount_ma20,
        )
        daily_dataset = dynamic_packet.get("data_status") or {}
        score_packet = dynamic_packet.get("score_packet") or {"rows": []}
        current_universe = dynamic_packet.get("universe") or get_default_etf_universe()
        theme_comparison = dynamic_packet.get("theme_comparison") or {}
        comparison_codes = [
            row.get("etf_code")
            for row in (theme_comparison.get("rows") or [])
            if row.get("etf_code")
        ][:8]
        holdings_snapshot = cached_margin_etf_holdings_snapshot(
            refresh_token=refresh_token,
            etf_codes=comparison_codes,
        )
    elif pool_source == "人工重点关注池":
        current_universe = [item for item in get_default_etf_universe() if item.get("manual_focus", True)]
        daily_dataset = cached_margin_etf_daily_dataset(refresh_token, "manual_focus", "")
        score_packet = score_etf_universe(daily_dataset)
    else:
        current_universe = get_default_etf_universe()
        daily_dataset = cached_margin_etf_daily_dataset(refresh_token, "core", "")
        score_packet = score_etf_universe(daily_dataset)
    return {
        "params_hash": params_hash,
        "params": params,
        "refresh_token": refresh_token,
        "daily_dataset": daily_dataset,
        "score_packet": score_packet,
        "current_universe": current_universe,
        "theme_comparison": theme_comparison,
        "holdings_snapshot": holdings_snapshot,
        "updated_at": _cc_now(),
    }


def build_command_center_margin_etf_allocation(daily_packet):
    params = (daily_packet or {}).get("params") or {}
    account = {
        "total_asset": float(st.session_state.get("margin_total_asset", 1000000.0) or 0.0),
        "cash_balance": float(st.session_state.get("margin_cash_balance", 200000.0) or 0.0),
        "stock_market_value": float(st.session_state.get("margin_stock_value", 600000.0) or 0.0),
        "etf_market_value": float(st.session_state.get("margin_etf_value", 100000.0) or 0.0),
        "margin_debt": float(st.session_state.get("margin_debt", 100000.0) or 0.0),
        "available_margin": float(st.session_state.get("margin_available_margin", 0.0) or 0.0),
        "maintenance_ratio": float(st.session_state.get("margin_maintenance_ratio", 0.0) or 0.0),
        "margin_interest_rate": float(st.session_state.get("margin_interest_rate", 6.8) or 0.0),
        "max_drawdown_pct": float(st.session_state.get("margin_max_drawdown", 15) or 0.0),
    }
    profile = {
        "style": st.session_state.get("margin_style", "平衡"),
        "leverage_mode": st.session_state.get("margin_leverage_mode", "小幅使用"),
    }
    daily_dataset = (daily_packet or {}).get("daily_dataset") or {}
    score_packet = (daily_packet or {}).get("score_packet") or {"rows": []}
    allocation = calculate_margin_etf_allocation(
        account,
        st.session_state.get("margin_market_state", "强趋势"),
        profile,
        etf_scores=score_packet,
    )
    allocation["etf_universe_mode"] = params.get("pool_source") or st.session_state.get("margin_etf_pool_source") or MARGIN_ETF_POOL_MODES[0]
    allocation["discovered_etf_count"] = daily_dataset.get("discovered_etf_count") or daily_dataset.get("sample_count") or len((daily_packet or {}).get("current_universe") or [])
    allocation["scored_etf_count"] = daily_dataset.get("scored_etf_count") or len(score_packet.get("rows") or [])
    allocation["theme_comparison"] = (daily_packet or {}).get("theme_comparison") or {}
    allocation["holdings_snapshot"] = (daily_packet or {}).get("holdings_snapshot") or {}
    allocation["holdings_data_gaps"] = (
        ((daily_packet or {}).get("holdings_snapshot") or {}).get("holdings_errors")
        or (["持仓明细暂不可用，当前仅按行情、跟踪指数和流动性比较。"] if allocation["etf_universe_mode"] == "同赛道横向比较" else [])
    )
    allocation["generated_at"] = _cc_now()
    return clone_command_center_packet(allocation)


def _cc_build_next_ticket_callbacks():
    return {
        "compute_technical_snapshot": compute_technical_snapshot,
        "get_current_price_detail": get_current_price_detail,
        "build_tianyan_risk_fact_packet": build_tianyan_risk_fact_packet,
        "build_local_risk_radar_items": build_local_risk_radar_items,
        "load_announcement_watchlist": load_announcement_watchlist,
        "call_deepseek_non_stream": call_deepseek_non_stream,
        "tushare_adapter": _tushare_adapter,
    }


def _cc_build_light_next_ticket_callbacks():
    callbacks = dict(_cc_build_next_ticket_callbacks())
    callbacks.pop("call_deepseek_non_stream", None)
    return callbacks


def _cc_refresh_market_environment(target="", market_type="", price=None, position_profile=None):
    del target, market_type, price, position_profile
    packet = build_market_style_fact_packet()
    st.session_state["legacy_market_style_fact_packet"] = clone_command_center_packet(packet)
    st.session_state["command_center_market_packet"] = market_packet_service.build_command_center_market_packet(st.session_state)
    _cc_mark_module("market", "已刷新", "Tushare 市场风格事实包")
    return {"module": "市场环境", "status": "ok", "updated_at": packet.get("updated_at", "")}


def _cc_generate_quant_summary(target="", market_type="", price=None, position_profile=None):
    market_packet = st.session_state.get("legacy_market_style_fact_packet") or {}
    report = st.session_state.get("last_backtest_report") or {}
    score = None
    metrics = report.get("metrics") or report
    win_rate = _cc_round(metrics.get("win_rate") or metrics.get("win_rate_pct"), 0)
    if win_rate is not None:
        score = max(0, min(100, win_rate if win_rate <= 100 else win_rate * 100))
    elif market_packet:
        risk_switch = market_packet.get("risk_switch") or ""
        score = 58 if "观察" in risk_switch else 62
    direction = "轻量摘要"
    if score is not None and score >= 65:
        direction = "偏积极但需验证"
    elif score is not None and score <= 50:
        direction = "偏防守"
    summary_parts = [
        "综合中心轻量量化摘要已生成。",
        "未运行旧版完整单票诊断，不调用 DeepSeek。",
    ]
    if market_packet:
        summary_parts.append(f"已纳入市场环境：{market_packet.get('market_state') or '待判断'}。")
    if report:
        summary_parts.append(f"已读取回测缓存：{report.get('summary') or report.get('ticker') or target}。")
    else:
        summary_parts.append("未读取到回测缓存，评分仅为轻量状态摘要。")
    quant_result = {
        "status": "completed",
        "mode": "command_center_light_summary",
        "generated_at": _cc_now(),
        "target": target,
        "market_type": market_type,
        "score": score,
        "direction": direction,
        "summary": "".join(summary_parts),
        "source": "综合推演中心轻量摘要 / session_state 缓存",
        "deepseek_called": False,
    }
    st.session_state["legacy_quant_result"] = clone_command_center_packet(quant_result)
    st.session_state["command_center_quant_packet"] = quant_packet_service.build_command_center_quant_packet(
        st.session_state,
        target=target,
    )
    _cc_mark_module("quant", "已刷新", "综合推演中心轻量量化摘要")
    return {"module": "量化推演", "status": "ok", "updated_at": quant_result["generated_at"]}


def _cc_run_discipline_check(target="", market_type="", price=None, position_profile=None):
    del market_type, price, position_profile
    report = st.session_state.get("last_backtest_report") or {}
    multi_result = st.session_state.get("last_multi_backtest") or {}
    if report and target and _cc_ticker_base(report.get("ticker")) != _cc_ticker_base(target):
        report = {}
        multi_result = {}
    payload = {
        "checked_at": _cc_now(),
        "target": target,
        "status": "completed" if report else "skipped",
        "deepseek_called": False,
    }
    if report:
        metrics = report.get("metrics") or report
        payload.update(
            {
                "summary": report.get("summary") or "已读取旧版交易纪律实验室回测缓存。",
                "win_rate": metrics.get("win_rate") or metrics.get("win_rate_pct"),
                "max_drawdown": metrics.get("max_drawdown_pct") or metrics.get("max_drawdown"),
                "multi_summary": (multi_result or {}).get("summary", "") if isinstance(multi_result, dict) else "",
            }
        )
        _cc_mark_module("discipline", "已刷新", "交易纪律实验室回测缓存")
    else:
        payload["summary"] = "请先选择标的或在旧版交易纪律实验室运行回测；综合中心不会自动跑两年全量回测。"
        _cc_mark_module("discipline", "待补充", "交易纪律实验室回测缓存", payload["summary"])
    st.session_state["command_center_discipline_check"] = clone_command_center_packet(payload)
    st.session_state["command_center_discipline_packet"] = discipline_packet_service.build_command_center_discipline_packet(
        st.session_state,
        live_packet={
            "discipline": {
                "updated_at": payload.get("checked_at", ""),
                "source": "交易纪律实验室回测缓存",
            }
        },
        target=target,
    )
    return {"module": "交易纪律", "status": payload["status"], "updated_at": payload["checked_at"], "message": payload["summary"]}


def _cc_refresh_margin_etf_config(target="", market_type="", price=None, position_profile=None):
    del market_type, price, position_profile
    token = _cc_now()
    st.session_state["margin_etf_daily_refresh_token"] = token
    params, params_hash = _cc_build_margin_etf_daily_params(force_light=True)
    previous_daily_packet = st.session_state.get("legacy_margin_etf_daily_packet") or {}
    previous_score_packet = previous_daily_packet.get("score_packet") or {"rows": []}
    current_universe = get_default_etf_universe()
    daily_packet = {
        "params_hash": params_hash,
        "params": params,
        "refresh_token": token,
        "daily_dataset": {
            "status": "manual_basic_local_config",
            "sample_count": len(current_universe),
            "note": "综合中心 manual_basic 只刷新本地 ETF 配置快照，不触发 ETF 全量发现或慢速行情批量请求。",
        },
        "score_packet": previous_score_packet,
        "current_universe": current_universe,
        "theme_comparison": {},
        "holdings_snapshot": {},
        "updated_at": token,
        "source": "融资 ETF 本地配置快照",
        "refresh_level": cc_service.REFRESH_LEVEL_MANUAL_BASIC,
    }
    st.session_state["legacy_margin_etf_daily_packet"] = clone_command_center_packet(daily_packet)
    allocation = build_command_center_margin_etf_allocation(daily_packet)
    allocation["summary"] = "已刷新融资 ETF 本地配置快照；深度行情、全量发现和同赛道比较仍需在旧版/深度入口手动触发。"
    st.session_state["legacy_margin_etf_allocation_result"] = clone_command_center_packet(allocation)
    st.session_state.pop("margin_etf_intraday_snapshot", None)
    st.session_state["command_center_etf_packet"] = legacy_packet_sync_service.sync_legacy_etf_packet(
        st.session_state,
        live_packet={
            "margin_etf": {
                "updated_at": token,
                "source": "融资 ETF 本地配置快照",
            }
        },
    )
    st.session_state["command_center_margin_packet"] = margin_packet_service.build_command_center_margin_packet(
        st.session_state,
        live_packet={
            "margin": {
                "updated_at": token,
                "source": "融资 ETF 本地配置快照",
            }
        },
        target=target,
    )
    _cc_mark_module("margin_etf", "已刷新", "融资 ETF 本地配置快照")
    return {
        "module": "融资 ETF",
        "status": "ok",
        "updated_at": daily_packet.get("updated_at", ""),
        "source": "融资 ETF 精简核心配置",
    }


def _cc_run_next_ticket_radar(target="", market_type="", price=None, position_profile=None):
    del market_type
    token = _cc_now()
    previous_rows = legacy_packet_sync_service.extract_legacy_radar_rows(st.session_state)
    profile = (
        position_profile
        if isinstance(position_profile, dict)
        else st.session_state.get("position_profile")
        or st.session_state.get("current_holding_context")
        or {}
    )
    current_price = (
        _num(price)
        or _num(profile.get("current_price"))
        or _num((st.session_state.get("command_center_direct_price_detail") or {}).get("price"))
    )
    current_name = (
        profile.get("name")
        or profile.get("current_holding_name")
        or st.session_state.get("current_stock_name")
        or ""
    )
    errors = []
    scan_state = {}
    try:
        scan_state = run_light_rule_scan_for_command_center(
            supabase=supabase,
            current_ticker=target,
            current_name=current_name,
            current_price=current_price,
            position_profile=profile,
            callbacks=_cc_build_light_next_ticket_callbacks(),
            candidate_limit=8,
            display_limit=3,
        )
    except Exception as exc:
        errors.append(str(exc))
        scan_state = {}
    generated_at = scan_state.get("generated_at") or token
    raw_rows = scan_state.get("rule_rows") or scan_state.get("results") or []
    light_rows = [
        row
        for row in raw_rows
        if isinstance(row, dict)
        and not row.get("error")
        and ((row.get("candidate") or {}).get("ticker") or (row.get("score") or {}).get("ticker"))
    ]
    rows_source = "综合中心轻量雷达"
    display_rows = light_rows
    if not display_rows and previous_rows:
        display_rows = previous_rows
        rows_source = "上一轮下一票雷达缓存"
    candidate_count = len(display_rows)
    status = "completed" if candidate_count else "skipped"
    insufficiency_reason = ""
    if not candidate_count:
        if errors:
            insufficiency_reason = f"轻量规则扫描失败：{errors[0]}"
        elif raw_rows:
            insufficiency_reason = "轻量候选池返回结果均不可用，可能是单票数据构造失败或关键数据缺失。"
        else:
            insufficiency_reason = "轻量候选池没有生成可用候选；未跑全市场扫描。"
    elif candidate_count < 3:
        insufficiency_reason = f"轻量候选池仅生成 {candidate_count} 个可用候选，首页按实际数量展示。"
    summary = {
        "source_mode": rows_source,
        "deepseek_called": False,
        "deepseek_detail": "未调用",
        "display_count": min(3, candidate_count),
        "total_count": len(display_rows),
        "scan_kind": "command_center_light_rule_scan",
        "candidate_limit": 8,
        "note": (
            f"综合中心轻量雷达已生成下一票 Top{min(3, candidate_count)}；"
            "候选来自轻量样本池/本地规则，不触发全市场扫描或 DeepSeek。"
            if candidate_count
            else f"暂无下一票 Top3：{insufficiency_reason}"
        ),
        "insufficiency_reason": insufficiency_reason,
        "errors": errors,
    }
    scan_state = {
        **(scan_state if isinstance(scan_state, dict) else {}),
        "generated_at": generated_at,
        "status": status,
        "source_mode": rows_source,
        "source_notes": [
            "满血数据刷新运行综合中心轻量雷达，不跑全市场重扫描。",
            f"候选来源：{rows_source}",
        ],
        "summary": summary,
        "rule_rows": clone_command_center_packet(display_rows),
        "results": clone_command_center_packet(display_rows),
        "refresh_level": cc_service.REFRESH_LEVEL_MANUAL_BASIC,
    }
    st.session_state["radar_scan_results"] = clone_command_center_packet(scan_state)
    st.session_state["radar_scan_summary"] = clone_command_center_packet(summary)
    st.session_state["radar_scan_status"] = scan_state["status"]
    st.session_state["radar_scan_finished_at"] = generated_at
    st.session_state["command_center_radar_packet"] = legacy_packet_sync_service.sync_legacy_radar_packet(
        st.session_state,
        live_packet={"next_ticket": {"updated_at": generated_at, "source": rows_source}},
    )
    _cc_mark_module(
        "next_ticket",
        "已刷新" if candidate_count else "待补充",
        rows_source,
        insufficiency_reason,
    )
    return {
        "module": "下一票雷达",
        "status": "ok",
        "updated_at": generated_at,
        "source": rows_source,
        "summary": summary["note"],
        "candidate_count": candidate_count,
        "deepseek_called": False,
    }


COMMAND_CENTER_REFRESH_STEPS = [
    ("market", "市场环境", _cc_refresh_market_environment),
    ("quant", "量化推演", _cc_generate_quant_summary),
    ("discipline", "交易纪律", _cc_run_discipline_check),
    ("margin_etf", "融资 ETF", _cc_refresh_margin_etf_config),
    ("next_ticket", "下一票雷达", _cc_run_next_ticket_radar),
]

COMMAND_CENTER_AUTO_LIGHT_STEPS = [
    ("live_packet", "缓存 / last_success 聚合"),
    ("account", "本地账户快照"),
    ("freshness", "缓存新鲜度检查"),
]


def _cc_run_refresh_step(module_key, target="", market_type="", price=None, position_profile=None):
    step_map = {key: (label, handler) for key, label, handler in COMMAND_CENTER_REFRESH_STEPS}
    label, handler = step_map[module_key]
    return cc_service.safe_refresh_module(
        st.session_state,
        module_key,
        label,
        handler,
        refresh_level=cc_service.REFRESH_LEVEL_MANUAL_BASIC,
        target=target,
        market_type=market_type,
        price=price,
        position_profile=position_profile,
    )


def _build_market_live_section():
    packet = market_packet_service.build_command_center_market_packet(st.session_state)
    meta = _cc_get_module_meta("market")
    if packet.get("data_status") == "missing":
        return {
            "status": "未刷新",
            "summary": meta.get("error") or "本轮自动刷新未取得市场环境；继续展示可用缓存和失败状态。",
            "updated_at": "",
            "source": "Tushare 市场风格事实包",
            "is_fresh": False,
            "last_error": meta.get("error", ""),
        }
    return {
        "status": "已刷新" if packet.get("status") == "ready" else "使用缓存",
        "summary": packet.get("summary") or "市场环境待验证。",
        "updated_at": packet.get("updated_at", ""),
        "source": packet.get("source") or "Tushare 市场风格事实包",
        "market_state": packet.get("market_state"),
        "risk_switch": packet.get("risk_switch"),
        "action_state": packet.get("action_state"),
        "risk_notes": packet.get("risk_notes") or [],
        "is_fresh": packet.get("data_status") == "ready",
        "last_error": meta.get("error", "") if meta.get("status") == "失败" else "",
    }


def _build_quant_live_section():
    packet = quant_packet_service.build_command_center_quant_packet(st.session_state)
    meta = _cc_get_module_meta("quant")
    if packet.get("data_status") == "missing":
        return {
            "status": "未刷新",
            "score": None,
            "summary": meta.get("error") or "本轮自动刷新未取得量化摘要；继续展示可用缓存和失败状态。",
            "updated_at": "",
            "source": "量化推演",
            "is_fresh": False,
            "last_error": meta.get("error", ""),
        }
    return {
        "status": "已刷新" if packet.get("data_status") == "ready" else "使用缓存",
        "score": _cc_round(packet.get("score"), 0),
        "direction": _cc_first_text(packet.get("direction"), default="待验证"),
        "summary": packet.get("summary") or "量化摘要待验证。",
        "updated_at": packet.get("updated_at", ""),
        "source": packet.get("source") or "量化推演",
        "action_state": packet.get("action_state") or "待验证",
        "confidence": packet.get("confidence") or "低",
        "evidence_items": packet.get("evidence_items") or [],
        "risk_notes": packet.get("risk_notes") or [],
        "is_fresh": packet.get("data_status") == "ready",
        "last_error": meta.get("error", "") if meta.get("status") == "失败" else "",
    }


def _build_discipline_live_section(target=""):
    packet = discipline_packet_service.build_command_center_discipline_packet(st.session_state, target=target)
    if packet.get("data_status") == "ready":
        return {
            "status": "已刷新",
            "score": packet.get("score"),
            "summary": packet.get("summary"),
            "updated_at": packet.get("updated_at", ""),
            "source": packet.get("source") or "交易纪律实验室",
            "action_state": packet.get("action_state") or "只观察",
            "key_rules": (packet.get("key_rules") or [])[:3],
            "win_rate": packet.get("win_rate"),
            "max_drawdown": packet.get("max_drawdown"),
            "is_fresh": True,
            "last_error": "",
        }
    check = st.session_state.get("command_center_discipline_check") or {}
    meta = _cc_get_module_meta("discipline")
    return {
        "status": "未刷新" if not check else "待补充",
        "score": None,
        "summary": packet.get("summary") or check.get("summary") or meta.get("error") or "本轮自动刷新未取得交易纪律缓存；不会自动运行两年回测。",
        "updated_at": packet.get("updated_at") or check.get("checked_at", ""),
        "source": "交易纪律实验室",
        "action_state": packet.get("action_state") or "待刷新",
        "key_rules": (packet.get("key_rules") or ["请先选择标的或运行回测。"])[:3],
        "is_fresh": False,
        "last_error": meta.get("error", "") if meta.get("status") == "失败" else "",
    }


def _build_next_ticket_live_section(live_packet=None):
    live_packet = live_packet or st.session_state.get("command_center_live_packet") or {}
    packet = radar_packet_service.build_command_center_radar_packet(
        st.session_state,
        live_packet=live_packet,
    )
    top_candidates = packet.get("top_candidates") or []
    if not top_candidates:
        home_snapshot = st.session_state.get("command_center_home_snapshot") or {}
        if isinstance(home_snapshot, dict):
            snapshot_packet = home_snapshot.get("radar_packet") or {}
            snapshot_candidates = home_snapshot.get("next_ticket_candidates") or []
            if snapshot_packet:
                packet = radar_packet_service.build_command_center_radar_packet(
                    {"command_center_radar_packet": snapshot_packet},
                    live_packet=live_packet,
                )
                top_candidates = packet.get("top_candidates") or []
            if not top_candidates and snapshot_candidates:
                packet = radar_packet_service.build_command_center_radar_packet(
                    {
                        "command_center_radar_packet": {
                            "status": "ready",
                            "source": "Home Snapshot",
                            "generated_at": home_snapshot.get("saved_at") or home_snapshot.get("updated_at") or "",
                            "top_candidates": snapshot_candidates,
                        }
                    },
                    live_packet=live_packet,
                )
                top_candidates = packet.get("top_candidates") or []
    if not top_candidates:
        snapshot_candidates = home_snapshot_service.extract_next_ticket_candidates(
            st.session_state,
            live_packet=live_packet,
        )
        if snapshot_candidates:
            packet = radar_packet_service.build_command_center_radar_packet(
                {
                    "command_center_radar_packet": {
                        **(packet or {}),
                        "status": "ready",
                        "source": (packet or {}).get("source") or "下一票雷达缓存",
                        "generated_at": (packet or {}).get("generated_at") or live_packet.get("updated_at") or live_packet.get("generated_at") or "",
                        "top_candidates": snapshot_candidates,
                    }
                },
                live_packet=live_packet,
            )
            top_candidates = packet.get("top_candidates") or []
    meta = _cc_get_module_meta("next_ticket")
    if not top_candidates:
        empty_reason = (
            packet.get("summary")
            or (st.session_state.get("radar_scan_summary") or {}).get("note")
            or (st.session_state.get("radar_scan_summary") or {}).get("insufficiency_reason")
        )
        excluded_candidates = packet.get("excluded_candidates") or []
        empty_status = (
            "已扫描"
            if packet.get("has_actionable_candidates") is False and excluded_candidates
            else "使用缓存" if packet.get("status") in {"partial", "waiting"} else "未刷新"
        )
        return {
            "status": empty_status,
            "top_candidates": [],
            "excluded_candidates": excluded_candidates,
            "summary": empty_reason or "暂无下一票缓存。可点击满血数据刷新，或进入高级工具箱运行下一票雷达。",
            "updated_at": packet.get("generated_at") or "",
            "source": "下一票雷达缓存",
            "action_state": "待刷新",
            "is_fresh": False,
            "last_error": meta.get("error", ""),
        }
    action_states = [item.get("status_label") or item.get("action_state") for item in top_candidates]
    aggregate_action = "只观察"
    if "可准备" in action_states:
        aggregate_action = "可准备"
    elif "等验证" in action_states:
        aggregate_action = "等验证"
    return {
        "status": "已刷新" if packet.get("data_status") == "ready" else "使用缓存",
        "top_candidates": top_candidates,
        "excluded_candidates": packet.get("excluded_candidates") or [],
        "summary": f"已读取上次成功下一票 Top{len(top_candidates[:3])}。",
        "updated_at": packet.get("generated_at") or packet.get("updated_at") or "",
        "source": _cc_user_source(packet.get("source"), "下一票雷达缓存"),
        "action_state": aggregate_action,
        "is_fresh": packet.get("data_status") == "ready",
        "last_error": meta.get("error", "") if meta.get("status") == "失败" else "",
    }


def _build_margin_etf_live_section(live_packet=None):
    live_packet = live_packet or st.session_state.get("command_center_live_packet") or {}
    packet = etf_packet_service.build_command_center_etf_packet(
        st.session_state,
        live_packet=live_packet,
    )
    recommended_etfs = packet.get("recommended_etfs") or []
    if not recommended_etfs:
        home_snapshot = st.session_state.get("command_center_home_snapshot") or {}
        if isinstance(home_snapshot, dict):
            snapshot_packet = home_snapshot.get("etf_packet") or {}
            snapshot_summary = home_snapshot.get("margin_etf_summary") or {}
            snapshot_etfs = snapshot_packet.get("recommended_etfs") or snapshot_summary.get("recommended_etfs") or []
            if snapshot_etfs:
                packet = etf_packet_service.build_command_center_etf_packet(
                    {
                        "command_center_etf_packet": {
                            **snapshot_packet,
                            "status": snapshot_packet.get("status") or "ready",
                            "source": snapshot_packet.get("source") or "Home Snapshot",
                            "updated_at": snapshot_packet.get("updated_at") or home_snapshot.get("saved_at") or "",
                            "recommended_margin_ratio": snapshot_packet.get("recommended_margin_ratio")
                            or snapshot_summary.get("recommended_margin_ratio"),
                            "recommended_cash_ratio": snapshot_packet.get("recommended_cash_ratio")
                            or snapshot_summary.get("recommended_cash_ratio"),
                            "today_main_direction": snapshot_packet.get("today_main_direction")
                            or snapshot_summary.get("today_main_direction"),
                            "recommended_etfs": snapshot_etfs,
                            "actionable_etfs": snapshot_packet.get("actionable_etfs")
                            or snapshot_summary.get("actionable_etfs"),
                            "watch_etfs": snapshot_packet.get("watch_etfs")
                            or snapshot_summary.get("watch_etfs"),
                            "avoid_etfs": snapshot_packet.get("avoid_etfs")
                            or snapshot_summary.get("avoid_etfs"),
                            "excluded_etfs": snapshot_packet.get("excluded_etfs")
                            or snapshot_summary.get("excluded_etfs"),
                            "watch_not_chase": snapshot_packet.get("watch_not_chase")
                            or snapshot_summary.get("watch_not_chase"),
                        }
                    },
                    live_packet=live_packet,
                )
                recommended_etfs = packet.get("recommended_etfs") or []
    if not recommended_etfs:
        snapshot_summary = home_snapshot_service.build_margin_etf_summary(
            st.session_state,
            live_packet=live_packet,
            etf_packet=packet,
        )
        snapshot_etfs = snapshot_summary.get("recommended_etfs") or []
        if snapshot_etfs:
            packet = etf_packet_service.build_command_center_etf_packet(
                {
                    "command_center_etf_packet": {
                        **(packet or {}),
                        "status": "ready",
                        "source": (packet or {}).get("source") or "融资 ETF 配置缓存",
                        "updated_at": (packet or {}).get("updated_at") or live_packet.get("updated_at") or live_packet.get("generated_at") or "",
                        "recommended_margin_ratio": (packet or {}).get("recommended_margin_ratio")
                        or snapshot_summary.get("recommended_margin_ratio"),
                        "recommended_cash_ratio": (packet or {}).get("recommended_cash_ratio")
                        or snapshot_summary.get("recommended_cash_ratio"),
                        "current_margin_ratio": (packet or {}).get("current_margin_ratio")
                        or snapshot_summary.get("current_margin_ratio"),
                        "today_main_direction": (packet or {}).get("today_main_direction")
                        or snapshot_summary.get("today_main_direction"),
                        "recommended_etfs": snapshot_etfs,
                        "actionable_etfs": (packet or {}).get("actionable_etfs")
                        or snapshot_summary.get("actionable_etfs"),
                        "watch_etfs": (packet or {}).get("watch_etfs")
                        or snapshot_summary.get("watch_etfs"),
                        "avoid_etfs": (packet or {}).get("avoid_etfs")
                        or snapshot_summary.get("avoid_etfs"),
                        "excluded_etfs": (packet or {}).get("excluded_etfs")
                        or snapshot_summary.get("excluded_etfs"),
                        "watch_not_chase": (packet or {}).get("watch_not_chase")
                        or snapshot_summary.get("watch_not_chase"),
                    }
                },
                live_packet=live_packet,
            )
            recommended_etfs = packet.get("recommended_etfs") or []
    meta = _cc_get_module_meta("margin_etf")
    if not recommended_etfs:
        has_non_main_etfs = bool((packet.get("avoid_etfs") or []) or (packet.get("excluded_etfs") or []))
        return {
            "status": "使用缓存" if packet.get("status") == "partial" else "未刷新",
            "recommended_margin_ratio": packet.get("recommended_margin_ratio"),
            "recommended_cash_ratio": packet.get("recommended_cash_ratio"),
            "summary": (
                "本轮 ETF 未产生可配置/观察候选；不追高或数据不足的 ETF 已放入折叠区。"
                if has_non_main_etfs
                else "暂无 ETF 配置。可点击满血数据刷新，或进入高级工具箱的融资 ETF 工具。"
            ),
            "updated_at": packet.get("updated_at") or "",
            "source": "融资 ETF 配置缓存",
            "today_main_direction": "待 ETF 强弱表确认",
            "recommended_etfs": [],
            "actionable_etfs": packet.get("actionable_etfs") or [],
            "watch_etfs": packet.get("watch_etfs") or [],
            "avoid_etfs": packet.get("avoid_etfs") or [],
            "excluded_etfs": packet.get("excluded_etfs") or [],
            "etf_candidates": [],
            "watch_not_chase": packet.get("watch_not_chase") or [],
            "risk_state": packet.get("risk_state") or "待刷新",
            "allow_new_margin": bool(packet.get("allow_new_margin", False)),
            "margin_risk_notice": packet.get("margin_risk_notice") or "",
            "etf_replacement_hint": packet.get("etf_replacement_hint") or "",
            "leverage_guardrail": packet.get("leverage_guardrail") or "不建议因为 ETF 强而额外加杠杆追高。",
            "action_state": "待刷新",
            "is_fresh": False,
            "last_error": meta.get("error", ""),
        }
    return {
        "status": "已刷新" if packet.get("data_status") == "ready" else "使用缓存",
        "recommended_margin_ratio": _cc_round(packet.get("recommended_margin_ratio")),
        "recommended_cash_ratio": _cc_round(packet.get("recommended_cash_ratio")),
        "summary": f"已读取上次成功 ETF 配置 Top{len(recommended_etfs[:3])}。",
        "updated_at": packet.get("updated_at") or "",
        "source": _cc_user_source(packet.get("source"), "融资 ETF 配置缓存"),
        "today_main_direction": packet.get("today_main_direction") or "待 ETF 强弱表确认",
        "recommended_etfs": recommended_etfs,
        "actionable_etfs": packet.get("actionable_etfs") or [],
        "watch_etfs": packet.get("watch_etfs") or [],
        "avoid_etfs": packet.get("avoid_etfs") or [],
        "excluded_etfs": packet.get("excluded_etfs") or [],
        "etf_candidates": [
            f"{item.get('code') or ''} {item.get('name') or ''}".strip()
            for item in recommended_etfs[:5]
        ],
        "watch_not_chase": packet.get("watch_not_chase") or [],
        "risk_state": packet.get("risk_state") or "只观察不追",
        "allow_new_margin": bool(packet.get("allow_new_margin", False)),
        "margin_risk_notice": packet.get("margin_risk_notice") or "",
        "etf_replacement_hint": packet.get("etf_replacement_hint") or "",
        "leverage_guardrail": packet.get("leverage_guardrail") or "不建议因为 ETF 强而额外加杠杆追高。",
        "action_state": packet.get("risk_state") or "待判断",
        "is_fresh": packet.get("data_status") == "ready",
        "last_error": meta.get("error", "") if meta.get("status") == "失败" else "",
    }


def _sync_command_center_home_candidate_packets(live_packet=None):
    live_packet = live_packet or st.session_state.get("command_center_live_packet") or {}
    next_candidates = home_snapshot_service.extract_next_ticket_candidates(
        st.session_state,
        live_packet=live_packet,
    )
    if next_candidates:
        radar_packet = radar_packet_service.build_command_center_radar_packet(
            {
                "command_center_radar_packet": {
                    **(st.session_state.get("command_center_radar_packet") or {}),
                    "status": "ready",
                    "source": (st.session_state.get("command_center_radar_packet") or {}).get("source")
                    or "下一票雷达缓存",
                    "generated_at": (st.session_state.get("command_center_radar_packet") or {}).get("generated_at")
                    or live_packet.get("updated_at")
                    or live_packet.get("generated_at")
                    or "",
                    "top_candidates": next_candidates,
                }
            },
            live_packet=live_packet,
        )
        st.session_state["command_center_radar_packet"] = radar_packet
        if isinstance(live_packet, dict):
            live_section = live_packet.get("next_ticket") if isinstance(live_packet.get("next_ticket"), dict) else {}
            live_packet["next_ticket"] = {
                **live_section,
                "status": "已刷新" if radar_packet.get("data_status") == "ready" else "使用缓存",
                "summary": f"已读取上次成功下一票 Top{len(next_candidates[:3])}。",
                "source": radar_packet.get("source") or live_section.get("source") or "下一票雷达缓存",
                "updated_at": radar_packet.get("generated_at") or radar_packet.get("updated_at") or live_section.get("updated_at") or "",
                "top_candidates": radar_packet.get("top_candidates") or next_candidates,
                "deepseek_called": False,
            }
    etf_packet = etf_packet_service.build_command_center_etf_packet(
        st.session_state,
        live_packet=live_packet,
    )
    margin_summary = home_snapshot_service.build_margin_etf_summary(
        st.session_state,
        live_packet=live_packet,
        etf_packet=etf_packet,
    )
    recommended_etfs = margin_summary.get("recommended_etfs") or []
    split_etfs_available = any(
        margin_summary.get(key)
        for key in ("actionable_etfs", "watch_etfs", "avoid_etfs", "excluded_etfs")
    )
    if recommended_etfs or split_etfs_available:
        etf_packet = etf_packet_service.build_command_center_etf_packet(
            {
                "command_center_etf_packet": {
                    **(etf_packet or {}),
                    "status": "ready",
                    "source": (etf_packet or {}).get("source") or "融资 ETF 配置缓存",
                    "updated_at": (etf_packet or {}).get("updated_at") or live_packet.get("updated_at") or live_packet.get("generated_at") or "",
                    "current_margin_ratio": margin_summary.get("current_margin_ratio"),
                    "recommended_margin_ratio": margin_summary.get("recommended_margin_ratio"),
                    "recommended_cash_ratio": margin_summary.get("recommended_cash_ratio"),
                    "today_main_direction": margin_summary.get("today_main_direction"),
                    "recommended_etfs": recommended_etfs,
                    "actionable_etfs": margin_summary.get("actionable_etfs"),
                    "watch_etfs": margin_summary.get("watch_etfs"),
                    "avoid_etfs": margin_summary.get("avoid_etfs"),
                    "excluded_etfs": margin_summary.get("excluded_etfs"),
                    "watch_not_chase": margin_summary.get("watch_not_chase"),
                    "allow_new_margin": margin_summary.get("allow_new_margin"),
                    "margin_risk_notice": margin_summary.get("margin_risk_notice"),
                    "etf_replacement_hint": margin_summary.get("etf_replacement_hint"),
                    "leverage_guardrail": margin_summary.get("leverage_guardrail"),
                }
            },
            live_packet=live_packet,
        )
        st.session_state["command_center_etf_packet"] = etf_packet
        if isinstance(live_packet, dict):
            live_section = live_packet.get("margin_etf") if isinstance(live_packet.get("margin_etf"), dict) else {}
            live_packet["margin_etf"] = {
                **live_section,
                "status": "已刷新" if etf_packet.get("data_status") == "ready" else "使用缓存",
                "summary": f"已读取上次成功 ETF 配置 Top{len(recommended_etfs[:3])}。",
                "source": etf_packet.get("source") or live_section.get("source") or "融资 ETF 配置缓存",
                "updated_at": etf_packet.get("updated_at") or live_section.get("updated_at") or "",
                "recommended_margin_ratio": etf_packet.get("recommended_margin_ratio"),
                "recommended_cash_ratio": etf_packet.get("recommended_cash_ratio"),
                "current_margin_ratio": etf_packet.get("current_margin_ratio"),
                "today_main_direction": etf_packet.get("today_main_direction"),
                "recommended_etfs": etf_packet.get("recommended_etfs") or recommended_etfs,
                "actionable_etfs": etf_packet.get("actionable_etfs") or margin_summary.get("actionable_etfs") or [],
                "watch_etfs": etf_packet.get("watch_etfs") or margin_summary.get("watch_etfs") or [],
                "avoid_etfs": etf_packet.get("avoid_etfs") or margin_summary.get("avoid_etfs") or [],
                "excluded_etfs": etf_packet.get("excluded_etfs") or margin_summary.get("excluded_etfs") or [],
                "watch_not_chase": etf_packet.get("watch_not_chase") or margin_summary.get("watch_not_chase"),
                "allow_new_margin": bool(etf_packet.get("allow_new_margin", False)),
                "margin_risk_notice": etf_packet.get("margin_risk_notice") or margin_summary.get("margin_risk_notice"),
                "etf_replacement_hint": etf_packet.get("etf_replacement_hint") or margin_summary.get("etf_replacement_hint"),
                "leverage_guardrail": etf_packet.get("leverage_guardrail")
                or margin_summary.get("leverage_guardrail")
                or "不建议因为 ETF 强而额外加杠杆追高。",
                "deepseek_called": False,
            }
    return live_packet


def _build_command_center_live_conclusion(live_packet):
    return cc_service.build_live_conclusion(live_packet)


def build_command_center_live_packet(target="", refresh_level=cc_service.REFRESH_LEVEL_AUTO_LIGHT):
    """Aggregate cached legacy results only. No external data source or DeepSeek call."""
    section_builders = {
        "market": _build_market_live_section,
        "quant": _build_quant_live_section,
        "discipline": lambda: _build_discipline_live_section(target=target),
        "next_ticket": _build_next_ticket_live_section,
        "margin_etf": _build_margin_etf_live_section,
    }
    return cc_service.build_live_packet(st.session_state, section_builders, refresh_level=refresh_level)


def run_command_center_auto_light_snapshot(target=""):
    """Only aggregates local/session_state state; never calls external refresh handlers."""
    packet = build_command_center_live_packet(
        target=target,
        refresh_level=cc_service.REFRESH_LEVEL_AUTO_LIGHT,
    )
    st.session_state["command_center_auto_light_summary"] = {
        "refresh_level": cc_service.REFRESH_LEVEL_AUTO_LIGHT,
        "steps": COMMAND_CENTER_AUTO_LIGHT_STEPS,
        "updated_at": cc_service.command_center_now(),
        "deepseek_called": False,
        "note": "仅聚合 session_state、last_success、本地账户快照与缓存新鲜度，不触发外部数据刷新。",
    }
    return packet


def build_command_center_display_packet(live_packet, fallback_packet=None):
    fallback = fallback_packet or get_command_center_mock_packet()
    return cc_service.build_display_packet(cc_adapter.as_mapping(live_packet), fallback_packet=fallback)


def _get_a_share_fact_recovery_summary_from_state():
    home_snapshot = st.session_state.get("command_center_home_snapshot") or {}
    if not isinstance(home_snapshot, dict):
        return {}
    return home_snapshot.get("a_share_fact_recovery_summary") or {}


def _get_latest_recovery_result_notice_from_state():
    home_snapshot = st.session_state.get("command_center_home_snapshot") or {}
    if isinstance(home_snapshot, dict) and home_snapshot.get("latest_recovery_result_notice"):
        return home_snapshot.get("latest_recovery_result_notice") or {}
    return home_snapshot_service.build_latest_recovery_result_notice(
        st.session_state,
        selected_tab=st.session_state.get("legacy_workspace_selected_tab"),
    )


def _apply_tool_recovery_navigation_state(action, *, persist_snapshot=False, live_packet=None, target="", position_profile=None):
    navigation_state = home_snapshot_service.build_tool_recovery_navigation_state(action)
    for nav_key, nav_value in navigation_state.items():
        st.session_state[nav_key] = nav_value
    if not navigation_state:
        return False
    selected_tab = navigation_state.get("legacy_workspace_selected_tab") or st.session_state.get("legacy_workspace_selected_tab")
    latest_notice = home_snapshot_service.build_latest_recovery_result_notice(
        st.session_state,
        selected_tab=selected_tab,
    )
    if latest_notice:
        st.session_state["latest_recovery_result_notice"] = latest_notice
        recovery_timeline = home_snapshot_service.build_recovery_result_timeline(
            st.session_state,
            latest_notice=latest_notice,
        )
        st.session_state["command_center_recovery_result_timeline"] = recovery_timeline
        st.session_state["recovery_result_timeline"] = recovery_timeline
    if persist_snapshot:
        _persist_home_action_snapshot(
            live_packet=live_packet or st.session_state.get("command_center_live_packet") or {},
            target=target or st.session_state.get("current_stock_code") or "",
            position_profile=position_profile
            or st.session_state.get("position_profile")
            or st.session_state.get("current_holding_context")
            or {},
        )
    return True


def build_command_center_view_model(live_packet=None):
    view_model = cc_state_adapter.build_command_center_view_model_from_state(
        st.session_state,
        live_packet=live_packet,
        strategy_packet_key=strategy_service.PACKET_KEY,
        strategy_last_success_key=strategy_service.LAST_SUCCESS_KEY,
        decision_packet_key=decision_engine.PACKET_KEY,
        decision_last_success_key=decision_engine.LAST_SUCCESS_KEY,
    )
    view_model["refresh_summary"] = build_refresh_summary_view_model(
        live_packet=live_packet,
        refresh_result=st.session_state.get("command_center_refresh_summary") or {},
        refresh_level=cc_adapter.get_nested(live_packet, "refresh_level"),
        generated_at=(
            cc_adapter.get_nested(live_packet, "updated_at")
            or cc_adapter.get_nested(live_packet, "generated_at")
        ),
        a_share_fact_recovery_summary=_get_a_share_fact_recovery_summary_from_state(),
        latest_recovery_result_notice=_get_latest_recovery_result_notice_from_state(),
    )
    st.session_state["command_center_view_model"] = view_model
    return view_model


def _build_home_action_snapshot_display(live_packet=None, target="", position_profile=None):
    local_snapshot = home_snapshot_service.load_home_action_snapshot()
    session_snapshot = home_snapshot_service.build_home_action_snapshot(
        st.session_state,
        target=target,
        position_profile=position_profile,
        live_packet=live_packet,
        decision_packet=_get_command_center_decision_display_packet(),
        strategy_packet=_get_strategy_execution_display_packet(),
        refresh_summary=st.session_state.get("command_center_refresh_summary") or {},
        data_capability_packet=_get_command_center_data_capability_packet(),
        facts_packet=_get_command_center_facts_packet(target=target),
    )
    snapshot = home_snapshot_service.choose_home_action_snapshot(session_snapshot, local_snapshot)
    st.session_state["command_center_home_snapshot"] = snapshot
    return snapshot


def _persist_home_action_snapshot(live_packet=None, target="", position_profile=None, decision_packet=None, strategy_packet=None, refresh_summary=None):
    snapshot = home_snapshot_service.build_home_action_snapshot(
        st.session_state,
        target=target,
        position_profile=position_profile,
        live_packet=live_packet or st.session_state.get("command_center_live_packet") or {},
        decision_packet=decision_packet or _get_command_center_decision_display_packet(),
        strategy_packet=strategy_packet or _get_strategy_execution_display_packet(),
        refresh_summary=refresh_summary or st.session_state.get("command_center_refresh_summary") or {},
        data_capability_packet=_get_command_center_data_capability_packet(),
        facts_packet=_get_command_center_facts_packet(target=target),
    )
    home_snapshot_service.save_home_action_snapshot(snapshot)
    st.session_state["command_center_home_snapshot"] = snapshot
    return snapshot


def _remember_legacy_tool_packet_recovery_result(
    *,
    key="",
    label="",
    writes_packet="",
    target_tab="",
    live_packet=None,
    target="",
    position_profile=None,
):
    if not writes_packet:
        return {}
    st.session_state["command_center_last_recovery_result_source"] = "tool_recovery"
    st.session_state["command_center_last_tool_recovery_key"] = key or writes_packet
    st.session_state["command_center_last_tool_recovery_label"] = label or target_tab or "旧工具能力"
    st.session_state["command_center_last_tool_recovery_writes_packet"] = writes_packet
    st.session_state["command_center_last_tool_recovery_target_tab"] = target_tab or st.session_state.get("legacy_workspace_selected_tab") or "高级工具"
    st.session_state["command_center_last_tool_recovery_policy"] = "navigation_only"
    latest_notice = home_snapshot_service.build_latest_recovery_result_notice(
        st.session_state,
        selected_tab=st.session_state["command_center_last_tool_recovery_target_tab"],
    )
    if latest_notice:
        st.session_state["latest_recovery_result_notice"] = latest_notice
        recovery_timeline = home_snapshot_service.build_recovery_result_timeline(
            st.session_state,
            latest_notice=latest_notice,
        )
        st.session_state["command_center_recovery_result_timeline"] = recovery_timeline
        st.session_state["recovery_result_timeline"] = recovery_timeline
    return _persist_home_action_snapshot(
        live_packet=live_packet or st.session_state.get("command_center_live_packet") or {},
        target=target,
        position_profile=position_profile,
    )


def _sync_tianyan_hard_risk_to_command_center(tianyan_packet, target="", position_profile=None, live_packet=None):
    if not isinstance(tianyan_packet, dict):
        return {}
    st.session_state["tianyan_risk_fact_packet"] = tianyan_packet
    hard_risk_packet = hard_risk_packet_service.build_command_center_hard_risk_packet(
        st.session_state,
        live_packet=live_packet or st.session_state.get("command_center_live_packet") or {},
        target=target,
    )
    st.session_state["command_center_hard_risk_packet"] = hard_risk_packet
    _persist_home_action_snapshot(
        live_packet=live_packet or st.session_state.get("command_center_live_packet") or {},
        target=target,
        position_profile=position_profile,
    )
    return hard_risk_packet


def _get_strategy_execution_display_packet():
    return cc_state_adapter.get_display_packet(
        st.session_state,
        strategy_service.PACKET_KEY,
        strategy_service.LAST_SUCCESS_KEY,
    )


def _attach_strategy_execution_packet(live_packet):
    strategy_packet = _get_strategy_execution_display_packet()
    return cc_state_adapter.attach_command_center_child_packets_for_display(
        live_packet,
        strategy_execution_packet=strategy_packet,
    )


def _get_command_center_decision_display_packet():
    return cc_state_adapter.get_display_packet(
        st.session_state,
        decision_engine.PACKET_KEY,
        decision_engine.LAST_SUCCESS_KEY,
    )


def _attach_command_center_decision_packet(live_packet):
    decision_packet = _get_command_center_decision_display_packet()
    return cc_state_adapter.attach_command_center_child_packets_for_display(
        live_packet,
        decision_packet=decision_packet,
    )


def _generate_command_center_decision(live_packet, refresh_summary=None):
    live_packet = _attach_strategy_execution_packet(live_packet or {})
    decision_packet = decision_engine.safe_generate_command_center_decision_packet(
        st.session_state,
        live_packet=live_packet,
        strategy_packet=_get_strategy_execution_display_packet(),
        refresh_summary=refresh_summary or st.session_state.get("command_center_refresh_summary") or {},
    )
    live_packet = cc_state_adapter.attach_command_center_child_packets_for_display(
        live_packet,
        strategy_execution_packet=live_packet.get("strategy_execution"),
        decision_packet=decision_packet,
    )
    return decision_packet, live_packet


def render_command_center_decision_card(
    live_packet,
    target="",
    position_profile=None,
    analysis_method_packet=None,
    projection_packet=None,
    show_generate_button=True,
    home_compact=False,
):
    live_packet = _attach_command_center_decision_packet(_attach_strategy_execution_packet(live_packet))
    packet = _get_command_center_decision_display_packet()
    notice = st.session_state.pop("command_center_decision_notice", "")
    if notice:
        notice_kind = st.session_state.pop("command_center_decision_notice_kind", "success")
        if notice_kind == "warning":
            st.warning(notice)
        else:
            st.success(notice)
    evidence_radar_vm = evidence_summary_service.build_a_share_evidence_radar_view_model(
        st.session_state.get("command_center_home_snapshot") or {}
    )
    home_snapshot = st.session_state.get("command_center_home_snapshot") or {}
    a_share_diagnostic = (
        home_snapshot.get("a_share_user_data_diagnostic")
        if isinstance(home_snapshot, dict)
        else {}
    ) or {}
    a_share_data_console = (
        a_share_diagnostic.get("status_console")
        if isinstance(a_share_diagnostic, dict)
        else {}
    ) or {}
    a_share_fact_recovery_summary = (
        home_snapshot.get("a_share_fact_recovery_summary")
        if isinstance(home_snapshot, dict)
        else {}
    ) or {}
    data_health_ledger = (
        home_snapshot.get("data_health_ledger")
        if isinstance(home_snapshot, dict)
        else {}
    ) or {}
    data_capability_brief = (
        home_snapshot.get("data_capability_brief")
        if isinstance(home_snapshot, dict)
        else {}
    ) or {}
    latest_recovery_result_notice = (
        home_snapshot.get("latest_recovery_result_notice")
        if isinstance(home_snapshot, dict)
        else {}
    ) or _get_latest_recovery_result_notice_from_state()
    recovery_result_timeline = (
        home_snapshot.get("command_center_recovery_result_timeline")
        or home_snapshot.get("recovery_result_timeline")
        if isinstance(home_snapshot, dict)
        else {}
    ) or {}
    decision_vm = build_decision_summary_view_model(
        packet,
        analysis_method_packet=analysis_method_packet,
        projection_packet=projection_packet,
        data_capability_brief=data_capability_brief,
        evidence_radar_packet=evidence_radar_vm,
        a_share_data_console=a_share_data_console,
        data_health_ledger=data_health_ledger,
        a_share_fact_recovery_summary=a_share_fact_recovery_summary,
        latest_recovery_result_notice=latest_recovery_result_notice,
        recovery_result_timeline=recovery_result_timeline,
        next_ticket_candidates=(
            home_snapshot.get("next_ticket_candidates")
            if isinstance(home_snapshot, dict)
            else []
        ),
        margin_etf_summary=(
            home_snapshot.get("margin_etf_summary")
            if isinstance(home_snapshot, dict)
            else {}
        ),
        old_workspace_packet_bridge=(
            home_snapshot.get("old_workspace_packet_bridge")
            if isinstance(home_snapshot, dict)
            else {}
        ),
        surface="home_compact" if home_compact else "full",
    )
    render_command_center_decision_hero(packet, decision_view_model=decision_vm)
    if packet and packet.get("stale"):
        st.caption("当前展示为上次成功结果；最近一次生成失败。")
    if packet and packet.get("last_error"):
        st.warning(f"上次生成失败：{packet.get('last_error')}")
    if show_generate_button and st.button("生成今日总决策", key="btn_command_center_decision_generate", width="stretch"):
        packet, live_packet = _generate_command_center_decision(live_packet)
        if packet.get("status") == "failed":
            st.session_state["command_center_decision_notice"] = (
                f"今日总决策生成失败，已保留可用缓存：{packet.get('last_error') or '未知错误'}"
            )
            st.session_state["command_center_decision_notice_kind"] = "warning"
        else:
            st.session_state["command_center_decision_notice"] = "今日总决策已生成；DeepSeek：未调用。"
            st.session_state["command_center_decision_notice_kind"] = "success"
        _persist_home_action_snapshot(
            live_packet=live_packet,
            target=target,
            position_profile=position_profile,
            decision_packet=packet,
        )
        st.rerun()
    return live_packet


def render_strategy_execution_card(
    live_packet,
    target="",
    position_profile=None,
    analysis_method_packet=None,
    evidence_radar_packet=None,
    projection_packet=None,
    show_generate_button=True,
    home_compact=False,
):
    live_packet = _attach_strategy_execution_packet(live_packet)
    packet = _get_strategy_execution_display_packet()
    if show_generate_button:
        st.caption("路径：刷新今日基础数据 → 生成策略执行建议 → 查看今日总决策 → 可选 DeepSeek 综合解释")
    if show_generate_button and st.button("生成策略执行建议", key="btn_strategy_execution_generate", width="stretch"):
        packet = strategy_service.safe_generate_strategy_execution_packet(
            st.session_state,
            target=target,
            position_profile=position_profile,
            live_packet=live_packet,
        )
        live_packet = cc_state_adapter.attach_command_center_child_packets_for_display(
            live_packet,
            strategy_execution_packet=packet,
        )
        if packet.get("status") == "failed":
            st.warning(f"策略执行建议生成失败，已保留可用缓存：{packet.get('last_error') or '未知错误'}")
        else:
            st.success("策略执行建议已生成；DeepSeek：未调用。")
        _persist_home_action_snapshot(
            live_packet=live_packet,
            target=target,
            position_profile=position_profile,
            strategy_packet=packet,
        )

    home_snapshot = st.session_state.get("command_center_home_snapshot") or {}
    a_share_diagnostic = home_snapshot.get("a_share_user_data_diagnostic") if isinstance(home_snapshot, dict) else {}
    a_share_data_console = (a_share_diagnostic or {}).get("status_console") if isinstance(a_share_diagnostic, dict) else {}
    a_share_fact_recovery_summary = (
        home_snapshot.get("a_share_fact_recovery_summary")
        if isinstance(home_snapshot, dict)
        else {}
    ) or {}
    data_health_ledger = (
        home_snapshot.get("data_health_ledger")
        if isinstance(home_snapshot, dict)
        else {}
    ) or {}
    latest_recovery_result_notice = (
        home_snapshot.get("latest_recovery_result_notice")
        if isinstance(home_snapshot, dict)
        else {}
    ) or _get_latest_recovery_result_notice_from_state()
    recovery_result_timeline = (
        home_snapshot.get("command_center_recovery_result_timeline")
        or home_snapshot.get("recovery_result_timeline")
        if isinstance(home_snapshot, dict)
        else {}
    ) or {}
    strategy_vm = build_strategy_summary_view_model(
        packet,
        analysis_method_packet=analysis_method_packet,
        projection_packet=projection_packet,
        evidence_radar_packet=evidence_radar_packet,
        a_share_data_console=a_share_data_console,
        data_health_ledger=data_health_ledger,
        a_share_fact_recovery_summary=a_share_fact_recovery_summary,
        latest_recovery_result_notice=latest_recovery_result_notice,
        recovery_result_timeline=recovery_result_timeline,
        surface="home_compact" if home_compact else "full",
    )
    render_strategy_execution_command_card(packet, live_packet=live_packet, strategy_view_model=strategy_vm)
    return live_packet


def _build_analysis_methods_display_packet(live_packet=None, target="", market_type="", home_snapshot=None):
    snapshot = home_snapshot or st.session_state.get("command_center_home_snapshot") or {}
    holding = cc_adapter.as_mapping(snapshot.get("holding_action"))
    ticker = target or holding.get("ticker") or ""
    name = holding.get("name") or ""
    return analysis_methods_service.build_analysis_method_packet(
        market_type=market_type,
        ticker=ticker,
        name=name,
        live_packet=live_packet or st.session_state.get("command_center_live_packet") or {},
        strategy_packet=_get_strategy_execution_display_packet(),
        decision_packet=_get_command_center_decision_display_packet(),
    )


def _get_command_center_data_capability_packet():
    existing_packet = st.session_state.get("command_center_data_capability_packet") or {}
    if isinstance(existing_packet, dict) and existing_packet.get("registry_version") == "mvp_v1":
        return existing_packet
    professional_packet = st.session_state.get("a_share_professional_data_capability") or {}
    health_result = st.session_state.get("last_data_source_healthcheck") or {}
    health_map = health_result if isinstance(health_result, dict) else {}
    if health_map.get("data_capability") and not professional_packet:
        return health_map.get("data_capability") or existing_packet or {}
    unified_packet = data_capability.build_unified_provider_capability_packet(
        health_result=health_map,
        a_share_packet=professional_packet,
        include_manual_providers=bool(health_map or professional_packet or existing_packet),
    )
    if unified_packet.get("items"):
        return unified_packet
    return existing_packet or {}


def _sync_a_share_capability_packet(professional_packet):
    st.session_state["a_share_professional_data_capability"] = professional_packet or {}
    health_result = st.session_state.get("last_data_source_healthcheck") or {}
    health_map = health_result if isinstance(health_result, dict) else {}
    unified_packet = data_capability.build_unified_provider_capability_packet(
        health_result=health_map,
        a_share_packet=professional_packet or {},
        include_manual_providers=bool(health_map or professional_packet),
    )
    if unified_packet.get("items"):
        st.session_state["command_center_data_capability_packet"] = unified_packet
    return unified_packet or professional_packet or {}


def _run_manual_margin_detail_capability_check(target="", position_profile=None, live_packet=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    request = a_share_manual_checks_service.build_margin_detail_check_request(ticker)
    checked_at = _cc_now()
    if not request.get("ts_code"):
        item = a_share_manual_checks_service.build_margin_detail_exception_item("未锁定 A股标的，无法检测 margin_detail。")
    elif not a_share_manual_checks_service.is_a_share_ts_code(request.get("ts_code")):
        item = a_share_manual_checks_service.build_margin_detail_exception_item("当前标的不是 A股代码，不检测 Tushare margin_detail。")
    elif _tushare_adapter is None or not hasattr(_tushare_adapter, "get_margin_detail"):
        item = a_share_manual_checks_service.build_margin_detail_exception_item(
            str(TUSHARE_ADAPTER_MODULE_ERROR) or "tushare_adapter 未接入 margin_detail。"
        )
    else:
        started = time.perf_counter()
        try:
            result = _tushare_adapter.get_margin_detail(
                ts_code=request["ts_code"],
                start_date=request["start_date"],
                end_date=request["end_date"],
            )
            item = a_share_manual_checks_service.build_margin_detail_capability_item(
                result,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        except Exception as exc:
            item = a_share_manual_checks_service.build_margin_detail_exception_item(
                exc,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
    item["checked_at"] = checked_at
    existing_packet = st.session_state.get("a_share_professional_data_capability") or {}
    professional_packet = a_share_manual_checks_service.merge_a_share_capability_item(
        existing_packet,
        item,
        checked_at=checked_at,
    )
    data_packet = _sync_a_share_capability_packet(professional_packet)
    live = live_packet or st.session_state.get("command_center_live_packet") or {}
    st.session_state["command_center_margin_packet"] = margin_packet_service.build_command_center_margin_packet(
        st.session_state,
        live,
        target=ticker,
    )
    _persist_home_action_snapshot(
        live_packet=live,
        target=ticker,
        position_profile=position_profile,
    )
    return {
        "request": request,
        "item": item,
        "professional_packet": professional_packet,
        "data_capability_packet": data_packet,
        "deepseek_called": False,
    }


def _run_manual_dragon_tiger_capability_check(target="", position_profile=None, live_packet=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    request = a_share_manual_checks_service.build_dragon_tiger_check_request(ticker)
    checked_at = _cc_now()
    if not request.get("ts_code"):
        item = a_share_manual_checks_service.build_dragon_tiger_exception_item("未锁定 A股标的，无法检测 top_list/top_inst。")
    elif not a_share_manual_checks_service.is_a_share_ts_code(request.get("ts_code")):
        item = a_share_manual_checks_service.build_dragon_tiger_exception_item("当前标的不是 A股代码，不检测 Tushare top_list/top_inst。")
    elif _tushare_adapter is None or not all(hasattr(_tushare_adapter, name) for name in ["get_top_list", "get_top_inst"]):
        item = a_share_manual_checks_service.build_dragon_tiger_exception_item(
            str(TUSHARE_ADAPTER_MODULE_ERROR) or "tushare_adapter 未接入 top_list/top_inst。"
        )
    else:
        started = time.perf_counter()
        try:
            top_list_result = _tushare_adapter.get_top_list(
                ts_code=request["ts_code"],
                trade_date=request["end_date"],
            )
            top_inst_result = _tushare_adapter.get_top_inst(
                ts_code=request["ts_code"],
                trade_date=request["end_date"],
            )
            item = a_share_manual_checks_service.build_dragon_tiger_capability_item(
                top_list_result,
                top_inst_result,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        except Exception as exc:
            item = a_share_manual_checks_service.build_dragon_tiger_exception_item(
                exc,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
    item["checked_at"] = checked_at
    existing_packet = st.session_state.get("a_share_professional_data_capability") or {}
    professional_packet = a_share_manual_checks_service.merge_a_share_capability_item(
        existing_packet,
        item,
        checked_at=checked_at,
    )
    data_packet = _sync_a_share_capability_packet(professional_packet)
    live = live_packet or st.session_state.get("command_center_live_packet") or {}
    st.session_state["command_center_dragon_tiger_packet"] = dragon_tiger_packet_service.build_command_center_dragon_tiger_packet(
        {"command_center_facts_packet": {"items": [{**item, "key": "dragon_tiger", "state": item.get("capability_state") or ""}]}},
        live_packet=live,
        target=ticker,
    )
    _persist_home_action_snapshot(
        live_packet=live,
        target=ticker,
        position_profile=position_profile,
    )
    return {
        "request": request,
        "item": item,
        "professional_packet": professional_packet,
        "data_capability_packet": data_packet,
        "deepseek_called": False,
    }


def _run_manual_moneyflow_capability_check(target="", position_profile=None, live_packet=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    request = a_share_manual_checks_service.build_moneyflow_check_request(ticker)
    checked_at = _cc_now()
    if not request.get("ts_code"):
        item = a_share_manual_checks_service.build_moneyflow_exception_item("未锁定 A股标的，无法检测 moneyflow。")
    elif not a_share_manual_checks_service.is_a_share_ts_code(request.get("ts_code")):
        item = a_share_manual_checks_service.build_moneyflow_exception_item("当前标的不是 A股代码，不检测 Tushare moneyflow。")
    elif _tushare_adapter is None or not hasattr(_tushare_adapter, "get_moneyflow"):
        item = a_share_manual_checks_service.build_moneyflow_exception_item(
            str(TUSHARE_ADAPTER_MODULE_ERROR) or "tushare_adapter 未接入 moneyflow。"
        )
    else:
        started = time.perf_counter()
        try:
            result = _tushare_adapter.get_moneyflow(
                ts_code=request["ts_code"],
                start_date=request["start_date"],
                end_date=request["end_date"],
            )
            item = a_share_manual_checks_service.build_moneyflow_capability_item(
                result,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        except Exception as exc:
            item = a_share_manual_checks_service.build_moneyflow_exception_item(
                exc,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
    item["checked_at"] = checked_at
    existing_packet = st.session_state.get("a_share_professional_data_capability") or {}
    professional_packet = a_share_manual_checks_service.merge_a_share_capability_item(
        existing_packet,
        item,
        checked_at=checked_at,
    )
    data_packet = _sync_a_share_capability_packet(professional_packet)
    live = live_packet or st.session_state.get("command_center_live_packet") or {}
    st.session_state["command_center_moneyflow_packet"] = moneyflow_packet_service.build_command_center_moneyflow_packet(
        {"command_center_facts_packet": {"items": [{**item, "key": "moneyflow", "state": item.get("capability_state") or ""}]}},
        live_packet=live,
        target=ticker,
    )
    _persist_home_action_snapshot(
        live_packet=live,
        target=ticker,
        position_profile=position_profile,
    )
    return {
        "request": request,
        "item": item,
        "professional_packet": professional_packet,
        "data_capability_packet": data_packet,
        "deepseek_called": False,
    }


def _run_manual_limit_cpt_capability_check(target="", position_profile=None, live_packet=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    request = a_share_manual_checks_service.build_limit_cpt_check_request()
    checked_at = _cc_now()
    if ticker and not a_share_manual_checks_service.is_a_share_ts_code(ticker):
        item = a_share_manual_checks_service.build_limit_cpt_exception_item("当前标的不是 A股代码，不检测 Tushare limit_cpt_list。")
    elif _tushare_adapter is None or not hasattr(_tushare_adapter, "get_limit_cpt_list"):
        item = a_share_manual_checks_service.build_limit_cpt_exception_item(
            str(TUSHARE_ADAPTER_MODULE_ERROR) or "tushare_adapter 未接入 limit_cpt_list。"
        )
    else:
        started = time.perf_counter()
        try:
            result = _tushare_adapter.get_limit_cpt_list(
                start_date=request["start_date"],
                end_date=request["end_date"],
            )
            item = a_share_manual_checks_service.build_limit_cpt_capability_item(
                result,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        except Exception as exc:
            item = a_share_manual_checks_service.build_limit_cpt_exception_item(
                exc,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
    item["checked_at"] = checked_at
    if item.get("capability_state") == data_capability.STATE_AVAILABLE:
        st.session_state["skip_limit_cpt_list"] = False
    elif item.get("capability_state") in {data_capability.STATE_PERMISSION_DENIED, data_capability.STATE_DISABLED_THIS_SESSION}:
        st.session_state["skip_limit_cpt_list"] = True
    existing_packet = st.session_state.get("a_share_professional_data_capability") or {}
    professional_packet = a_share_manual_checks_service.merge_a_share_capability_item(
        existing_packet,
        item,
        checked_at=checked_at,
    )
    data_packet = _sync_a_share_capability_packet(professional_packet)
    live = live_packet or st.session_state.get("command_center_live_packet") or {}
    st.session_state["command_center_limit_emotion_packet"] = limit_emotion_packet_service.build_command_center_limit_emotion_packet(
        {"command_center_facts_packet": {"items": [{**item, "key": "limit_emotion", "state": item.get("capability_state") or ""}]}},
        live_packet=live,
        target=ticker,
    )
    _persist_home_action_snapshot(
        live_packet=live,
        target=ticker,
        position_profile=position_profile,
    )
    return {
        "request": request,
        "item": item,
        "professional_packet": professional_packet,
        "data_capability_packet": data_packet,
        "deepseek_called": False,
    }


def _run_manual_chip_radar_capability_check(target="", position_profile=None, live_packet=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    request = a_share_manual_checks_service.build_chip_radar_check_request(ticker)
    checked_at = _cc_now()
    if not request.get("ts_code"):
        item = a_share_manual_checks_service.build_chip_radar_exception_item("未锁定 A股标的，无法检测 cyq_perf/cyq_chips。")
    elif not a_share_manual_checks_service.is_a_share_ts_code(request.get("ts_code")):
        item = a_share_manual_checks_service.build_chip_radar_exception_item("当前标的不是 A股代码，不检测 Tushare cyq_perf/cyq_chips。")
    elif _tushare_adapter is None or not all(hasattr(_tushare_adapter, name) for name in ["get_cyq_perf", "get_cyq_chips"]):
        item = a_share_manual_checks_service.build_chip_radar_exception_item(
            str(TUSHARE_ADAPTER_MODULE_ERROR) or "tushare_adapter 未接入 cyq_perf/cyq_chips。"
        )
    else:
        started = time.perf_counter()
        try:
            perf_result = _tushare_adapter.get_cyq_perf(
                ts_code=request["ts_code"],
                start_date=request["start_date"],
                end_date=request["end_date"],
            )
            chips_result = _tushare_adapter.get_cyq_chips(
                ts_code=request["ts_code"],
                start_date=request["start_date"],
                end_date=request["end_date"],
            )
            item = a_share_manual_checks_service.build_chip_radar_capability_item(
                perf_result,
                chips_result,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        except Exception as exc:
            item = a_share_manual_checks_service.build_chip_radar_exception_item(
                exc,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
    item["checked_at"] = checked_at
    existing_packet = st.session_state.get("a_share_professional_data_capability") or {}
    professional_packet = a_share_manual_checks_service.merge_a_share_capability_item(
        existing_packet,
        item,
        checked_at=checked_at,
    )
    data_packet = _sync_a_share_capability_packet(professional_packet)
    live = live_packet or st.session_state.get("command_center_live_packet") or {}
    st.session_state["command_center_chip_packet"] = chip_packet_service.build_command_center_chip_packet(
        {"command_center_facts_packet": {"items": [{**item, "key": "chip_radar", "state": item.get("capability_state") or ""}]}},
        live_packet=live,
        target=ticker,
    )
    _persist_home_action_snapshot(
        live_packet=live,
        target=ticker,
        position_profile=position_profile,
    )
    return {
        "request": request,
        "item": item,
        "professional_packet": professional_packet,
        "data_capability_packet": data_packet,
        "deepseek_called": False,
    }


def _call_tushare_hard_risk_api(api_name, method_name, **kwargs):
    if _tushare_adapter is None:
        return {"ok": False, "api": api_name, "error": str(TUSHARE_ADAPTER_MODULE_ERROR) or "tushare_adapter 不可用"}
    if not hasattr(_tushare_adapter, method_name):
        return {"ok": False, "api": api_name, "error": f"tushare_adapter 未接入 {api_name} 接口"}
    try:
        result = getattr(_tushare_adapter, method_name)(**kwargs)
        if isinstance(result, dict):
            result.setdefault("api", api_name)
            return result
        return {"ok": False, "api": api_name, "error": "Tushare 返回结果格式不可识别"}
    except Exception as exc:
        return {"ok": False, "api": api_name, "error": str(exc)}


def _run_manual_hard_risk_capability_check(target="", position_profile=None, live_packet=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    request = a_share_manual_checks_service.build_hard_risk_check_request(ticker)
    checked_at = _cc_now()
    live = live_packet or st.session_state.get("command_center_live_packet") or {}
    if not request.get("ts_code"):
        hard_risk_packet = hard_risk_packet_service.build_command_center_hard_risk_packet({}, live_packet=live, target=ticker)
        item = a_share_manual_checks_service.build_hard_risk_exception_item("未锁定 A股标的，无法检测公告/硬风险。")
    elif not a_share_manual_checks_service.is_a_share_ts_code(request.get("ts_code")):
        hard_risk_packet = hard_risk_packet_service.build_command_center_hard_risk_packet({}, live_packet=live, target=ticker)
        item = a_share_manual_checks_service.build_hard_risk_exception_item("当前标的不是 A股代码，不检测 Tushare 公告/硬风险。")
    else:
        started = time.perf_counter()
        results = {
            "anns_d": _call_tushare_hard_risk_api(
                "anns_d",
                "get_anns_d",
                ts_code=request["ts_code"],
                start_date=request["ann_start_date"],
                end_date=request["end_date"],
            ),
            "forecast": _call_tushare_hard_risk_api(
                "forecast",
                "get_forecast",
                ts_code=request["ts_code"],
                start_date=request["forecast_start_date"],
                end_date=request["end_date"],
            ),
            "stk_holdertrade": _call_tushare_hard_risk_api(
                "stk_holdertrade",
                "get_stk_holdertrade",
                ts_code=request["ts_code"],
                start_date=request["holder_start_date"],
                end_date=request["end_date"],
            ),
            "share_float": _call_tushare_hard_risk_api(
                "share_float",
                "get_share_float",
                ts_code=request["ts_code"],
                start_date=request["unlock_start_date"],
                end_date=request["unlock_end_date"],
            ),
            "pledge_stat": _call_tushare_hard_risk_api(
                "pledge_stat",
                "get_pledge_stat",
                ts_code=request["ts_code"],
            ),
            "pledge_detail": _call_tushare_hard_risk_api(
                "pledge_detail",
                "get_pledge_detail",
                ts_code=request["ts_code"],
            ),
        }
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        tianyan_packet = a_share_manual_checks_service.build_hard_risk_fact_packet_from_results(
            ts_code=request["ts_code"],
            stock_name=profile.get("name") or st.session_state.get("current_stock_name") or "",
            results=results,
            checked_at=checked_at,
        )
        st.session_state["tianyan_risk_fact_packet"] = tianyan_packet
        hard_risk_packet = hard_risk_packet_service.build_command_center_hard_risk_packet(
            {"tianyan_risk_fact_packet": tianyan_packet},
            live_packet=live,
            target=ticker,
        )
        item = a_share_manual_checks_service.build_hard_risk_capability_item(
            results,
            latency_ms=latency_ms,
        )
    item["checked_at"] = checked_at
    st.session_state["command_center_hard_risk_packet"] = hard_risk_packet
    existing_packet = st.session_state.get("a_share_professional_data_capability") or {}
    professional_packet = a_share_manual_checks_service.merge_a_share_capability_item(
        existing_packet,
        item,
        checked_at=checked_at,
    )
    data_packet = _sync_a_share_capability_packet(professional_packet)
    _persist_home_action_snapshot(
        live_packet=live,
        target=ticker,
        position_profile=position_profile,
    )
    return {
        "request": request,
        "item": item,
        "hard_risk_packet": hard_risk_packet,
        "professional_packet": professional_packet,
        "data_capability_packet": data_packet,
        "deepseek_called": False,
    }


def _remember_a_share_manual_recovery_result(result=None, *, key="", label="", writes_packet="", api_hint=""):
    payload = result if isinstance(result, dict) else {}
    item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
    if not item or not writes_packet:
        return {}
    record = {
        "key": key,
        "label": label or item.get("label") or "A股数据",
        "writes_packet": writes_packet,
        "api_hint": api_hint or item.get("api"),
        "capability_state": item.get("capability_state") or item.get("state"),
        "status_label": item.get("status") or item.get("capability_label") or item.get("capability_state") or "待验证",
        "message": item.get("action_hint") or item.get("error") or item.get("message") or "已更新本地数据能力状态。",
        "checked_at": item.get("checked_at") or item.get("updated_at"),
        "deepseek_called": False,
    }
    st.session_state["command_center_last_a_share_diagnostic_recovery_result"] = record
    st.session_state["command_center_last_recovery_result_source"] = "a_share_diagnostic"
    return record


def _render_manual_capability_check_button(
    button_label,
    button_key,
    status_label,
    result_label,
    runner,
    target="",
    position_profile=None,
    live_packet=None,
):
    if not st.button(button_label, key=button_key, width="stretch"):
        return None
    status = st.status(status_label, expanded=True)
    result = runner(
        target=target,
        position_profile=position_profile,
        live_packet=live_packet,
    )
    item = result.get("item") or {}
    state_label = item.get("status") or item.get("capability_label") or item.get("capability_state") or "待验证"
    message = item.get("action_hint") or item.get("error") or item.get("message") or "已更新本地数据能力状态。"
    status.update(label=f"{result_label}检测完成：{state_label}", state="complete", expanded=False)
    if item.get("capability_state") == data_capability.STATE_AVAILABLE:
        st.success(f"{result_label}检测完成：{message}；DeepSeek：未调用。")
    else:
        st.warning(f"{result_label}检测结果：{message}；已回流到 A股数据能力矩阵。DeepSeek：未调用。")
    return result


def _get_legacy_a_share_auto_hydrate_specs():
    return [
        {
            "key": "moneyflow",
            "label": "资金流",
            "api": "moneyflow",
            "source": "Tushare moneyflow",
            "packet_key": "command_center_moneyflow_packet",
            "legacy_packet_key": "legacy_moneyflow_packet",
            "runner": _run_manual_moneyflow_capability_check,
        },
        {
            "key": "dragon_tiger",
            "label": "龙虎榜",
            "api": "top_list/top_inst",
            "source": "Tushare top_list/top_inst",
            "packet_key": "command_center_dragon_tiger_packet",
            "legacy_packet_key": "legacy_dragon_tiger_packet",
            "runner": _run_manual_dragon_tiger_capability_check,
        },
        {
            "key": "margin",
            "label": "融资融券",
            "api": "margin_detail",
            "source": "Tushare margin_detail",
            "packet_key": "command_center_margin_packet",
            "legacy_packet_key": "legacy_margin_packet",
            "runner": _run_manual_margin_detail_capability_check,
        },
        {
            "key": "limit_emotion",
            "label": "涨跌停/情绪",
            "api": "limit_cpt_list",
            "source": "Tushare limit_cpt_list",
            "packet_key": "command_center_limit_emotion_packet",
            "legacy_packet_key": "legacy_limit_emotion_packet",
            "runner": _run_manual_limit_cpt_capability_check,
        },
        {
            "key": "chip_radar",
            "label": "筹码/胜率",
            "api": "cyq_perf/cyq_chips",
            "source": "Tushare cyq_perf/cyq_chips",
            "packet_key": "command_center_chip_packet",
            "legacy_packet_key": "legacy_chip_packet",
            "runner": _run_manual_chip_radar_capability_check,
        },
        {
            "key": "hard_risk",
            "label": "公告/硬风险",
            "api": "anns_d/forecast/stk_holdertrade/share_float/pledge",
            "source": "Tushare 公告/硬风险",
            "packet_key": "command_center_hard_risk_packet",
            "legacy_packet_key": "legacy_hard_risk_packet",
            "runner": _run_manual_hard_risk_capability_check,
        },
    ]


def _run_legacy_a_share_auto_hydrate(
    *,
    target="",
    market_type="A股",
    position_profile=None,
    live_packet=None,
    module_keys=None,
    force=False,
):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    if not (is_a_share_market(market_type) or a_share_manual_checks_service.is_a_share_ts_code(ticker)):
        return {}
    specs = _get_legacy_a_share_auto_hydrate_specs()
    service_specs = [{key: value for key, value in spec.items() if key != "runner"} for spec in specs]
    handler_map = {spec["key"]: spec["runner"] for spec in specs}
    packet = legacy_a_share_auto_hydrate_service.execute_auto_hydrate(
        st.session_state,
        target=ticker,
        market_type=market_type or "A股",
        module_specs=service_specs,
        handlers=handler_map,
        module_keys=module_keys,
        fingerprint_modules=module_keys or [spec["key"] for spec in specs],
        ttl_seconds=st.session_state.get(
            legacy_a_share_auto_hydrate_service.TTL_KEY,
            legacy_a_share_auto_hydrate_service.DEFAULT_TTL_SECONDS,
        ),
        now_text=_cc_now(),
        force=force,
        position_profile=position_profile,
        live_packet=live_packet,
    )
    professional_packet = st.session_state.get("a_share_professional_data_capability") or {}
    if professional_packet:
        st.session_state["legacy_a_share_fact_packet"] = professional_packet
    if packet.get("hydrated") and not module_keys:
        provider_status = _run_legacy_a_share_provider_status_probe(ticker, market_type or "A股")
        if provider_status:
            packet["provider_status"] = provider_status
            st.session_state[legacy_a_share_auto_hydrate_service.STATUS_KEY] = packet
    _persist_home_action_snapshot(
        live_packet=live_packet or st.session_state.get("command_center_live_packet") or {},
        target=ticker,
        position_profile=position_profile,
    )
    return packet


def _legacy_provider_result_line(label, status, detail=""):
    text = f"{label} {status}"
    return f"{text}（{detail}）" if detail else text


def _run_legacy_a_share_provider_status_probe(target="", market_type="A股"):
    checked_at = _cc_now()
    results = []
    normalized_market_type = "A_SHARE" if _cc_is_a_share_market_type(market_type) else market_type
    sample_ts_code = _cc_healthcheck_sample_ts_code(target)
    try:
        health_result = run_data_source_healthcheck(
            sample_ts_code=sample_ts_code,
            include_deepseek_ping=False,
            cache_version=f"legacy_a_share_provider_{sample_ts_code}_{datetime.date.today().isoformat()}",
            _supabase_client=supabase,
            _deepseek_keys=st.session_state.get("ds_keys") or [],
        )
        st.session_state["last_data_source_healthcheck"] = health_result
        if isinstance(health_result, dict) and health_result.get("data_capability"):
            st.session_state["command_center_data_capability_packet"] = health_result.get("data_capability")
        tushare_health = health_result.get("tushare") if isinstance(health_result, dict) else {}
        tushare_total = len((tushare_health or {}).get("items") or [])
        results.append(
            {
                "label": "Tushare",
                "status": "已检测" if tushare_total else "待验证",
                "detail": f"{(tushare_health or {}).get('ok_count', 0)}/{tushare_total} 可用" if tushare_total else "",
                "updated_at": (tushare_health or {}).get("checked_at") or checked_at,
            }
        )
        supabase_health = health_result.get("supabase") if isinstance(health_result, dict) else {}
        supabase_total = len((supabase_health or {}).get("items") or [])
        results.append(
            {
                "label": "Supabase",
                "status": "已检测" if supabase_total else "待验证",
                "detail": f"{(supabase_health or {}).get('ok_count', 0)}/{supabase_total} 可连接" if supabase_total else "",
                "updated_at": (supabase_health or {}).get("checked_at") or checked_at,
            }
        )
    except Exception as exc:
        results.append({"label": "Tushare/Supabase", "status": "失败", "detail": str(exc), "updated_at": checked_at})

    try:
        yfinance_snapshot = _cc_refresh_yfinance_snapshot(target=target, market_type=normalized_market_type)
        yfinance_status = "跳过" if yfinance_snapshot.get("skipped") else ("失败" if yfinance_snapshot.get("error") else "已检测")
        results.append(
            {
                "label": "yfinance",
                "status": yfinance_status,
                "detail": yfinance_snapshot.get("reason") or yfinance_snapshot.get("warning") or yfinance_snapshot.get("data_date") or "",
                "updated_at": yfinance_snapshot.get("updated_at") or checked_at,
            }
        )
    except Exception as exc:
        results.append({"label": "yfinance", "status": "失败", "detail": str(exc), "updated_at": checked_at})

    try:
        akshare_result = _cc_collect_auto_page_akshare_snapshot(target=target, market_type=normalized_market_type)
        akshare_snapshot = akshare_result.get("snapshot") if isinstance(akshare_result, dict) else {}
        akshare_error = akshare_result.get("error") if isinstance(akshare_result, dict) else {}
        warnings = akshare_snapshot.get("warnings") if isinstance(akshare_snapshot, dict) else []
        akshare_status = "失败" if akshare_error else ("跳过" if akshare_snapshot.get("mode") == "skipped" else "已检测")
        results.append(
            {
                "label": "AkShare",
                "status": akshare_status,
                "detail": (warnings or ["轻量资金快照已处理。"])[0],
                "updated_at": akshare_snapshot.get("updated_at") if isinstance(akshare_snapshot, dict) else checked_at,
            }
        )
    except Exception as exc:
        results.append({"label": "AkShare", "status": "失败", "detail": str(exc), "updated_at": checked_at})

    provider_status = {
        "checked_at": checked_at,
        "results": results,
        "summary": "｜".join(
            _legacy_provider_result_line(item.get("label"), item.get("status"), item.get("detail"))
            for item in results
            if item.get("label")
        ),
        "deepseek_called": False,
    }
    st.session_state["legacy_auto_hydrate_provider_status"] = provider_status
    return provider_status


def _legacy_a_share_status_card_tone(status):
    return {
        "available": "success",
        "cached": "info",
        "no_permission": "warning",
        "no_data": "info",
        "skipped": "info",
        "failed": "warning",
    }.get(str(status or ""), "info")


def _render_legacy_a_share_auto_hydrate_cards(
    packet,
    *,
    target="",
    market_type="A股",
    position_profile=None,
    live_packet=None,
    key_prefix="legacy",
    module_filter=None,
    cards_expanded=True,
):
    payload = packet if isinstance(packet, dict) else {}
    modules = [item for item in (payload.get("modules") or []) if isinstance(item, dict)]
    if module_filter:
        allowed = {str(item) for item in module_filter}
        modules = [item for item in modules if str(item.get("key") or "") in allowed]
    if not modules:
        st.info("A股专业数据待检测；页面会在进入该模块时按 TTL 自动尝试刷新。")
        return
    st.caption(
        f"{payload.get('summary_text') or legacy_a_share_auto_hydrate_service.build_main_summary_text(payload)}｜"
        f"TTL {st.session_state.get(legacy_a_share_auto_hydrate_service.TTL_KEY, legacy_a_share_auto_hydrate_service.DEFAULT_TTL_SECONDS)} 秒"
    )
    provider_status = payload.get("provider_status") or st.session_state.get("legacy_auto_hydrate_provider_status") or {}
    if provider_status.get("summary"):
        st.caption(f"数据源覆盖：{provider_status.get('summary')}")
    else:
        st.caption("数据源覆盖：Tushare A股专业接口；AkShare / Supabase / yfinance 进入对应模块时按需读取。")
    if payload.get("skipped_by_ttl"):
        decision = payload.get("decision") or {}
        remaining = decision.get("remaining_seconds")
        st.caption(f"本轮未重复请求外部接口：同一标的仍在 TTL 内{f'，约 {remaining} 秒后可自动刷新' if remaining else ''}。")

    problem_items = [
        item for item in modules
        if str(item.get("status") or "") in {"failed", "no_permission", "skipped"}
    ]
    if not cards_expanded and problem_items:
        st.warning(
            "需处理：" + "；".join(
                f"{item.get('label') or 'A股数据'}：{item.get('status_label') or '待验证'}"
                for item in problem_items[:3]
            )
        )

    def render_status_card_grid():
        card_cols = st.columns(3)
        for index, item in enumerate(modules):
            key = str(item.get("key") or index)
            with card_cols[index % len(card_cols)]:
                with st.container(border=True):
                    st.markdown(f"**{item.get('label') or 'A股数据'}**")
                    status_label = item.get("status_label") or "待验证"
                    status_tone = _legacy_a_share_status_card_tone(item.get("status"))
                    if item.get("runtime_secret_missing"):
                        st.warning(f"状态：{status_label}")
                    elif status_tone == "success":
                        st.success(f"状态：{status_label}")
                    elif status_tone == "warning":
                        st.warning(f"状态：{status_label}")
                    else:
                        st.info(f"状态：{status_label}")
                    st.write(item.get("conclusion") or "等待当前模块自动检测。")
                    st.caption(f"更新时间：{item.get('updated_at') or '暂无'}")
                    st.caption(f"来源：{item.get('source') or 'Tushare'}")
                    if st.button(
                        "重新检测",
                        key=f"btn_{key_prefix}_legacy_a_share_recheck_{key}",
                        width="stretch",
                    ):
                        refreshed_packet = _run_legacy_a_share_auto_hydrate(
                            target=target,
                            market_type=market_type,
                            position_profile=position_profile,
                            live_packet=live_packet,
                            module_keys=[key],
                            force=True,
                        )
                        refreshed_item = next(
                            (
                                module
                                for module in (refreshed_packet.get("modules") or [])
                                if isinstance(module, dict) and module.get("key") == key
                            ),
                            {},
                        )
                        if refreshed_item.get("status") == "available":
                            st.success(f"{refreshed_item.get('label') or '数据'}已重新检测；DeepSeek：未调用。")
                        else:
                            st.warning(
                                f"{refreshed_item.get('label') or '数据'}重新检测完成："
                                f"{refreshed_item.get('status_label') or '待验证'}；DeepSeek：未调用。"
                            )
                        st.rerun()

    if cards_expanded:
        render_status_card_grid()
    else:
        with st.expander("查看接口状态卡 / 重新检测", expanded=False):
            render_status_card_grid()

    with st.expander("查看诊断详情", expanded=False):
        decision = payload.get("decision") or {}
        st.caption(
            f"自动补水原因：{decision.get('reason') or '未知'}｜"
            f"fingerprint：{payload.get('fingerprint') or '暂无'}｜"
            f"DeepSeek：{'已调用' if payload.get('deepseek_called') else '未调用'}"
        )
        detail_rows = []
        for item in modules:
            detail_rows.append(
                {
                    "名称": item.get("label"),
                    "状态": item.get("status_label"),
                    "api": item.get("api"),
                    "writes_packet": item.get("writes_packet"),
                    "legacy_packet": item.get("legacy_packet_key"),
                    "error": item.get("error"),
                    "cache_available": item.get("cache_available"),
                    "updated_at": item.get("updated_at"),
                }
            )
        if detail_rows:
            st.dataframe(pd.DataFrame(detail_rows), width="stretch", hide_index=True)
        provider_rows = (provider_status or {}).get("results") or []
        if provider_rows:
            st.markdown("##### 数据源详情")
            st.dataframe(pd.DataFrame(provider_rows), width="stretch", hide_index=True)


def render_a_share_data_capability_controls(target="", position_profile=None, live_packet=None, key_prefix="cc"):
    packet = _run_legacy_a_share_auto_hydrate(
        target=target,
        market_type="A股",
        position_profile=position_profile,
        live_packet=live_packet,
    )
    with st.container(border=True):
        st.markdown("#### A股专业数据自动检测")
        _render_legacy_a_share_auto_hydrate_cards(
            packet,
            target=target,
            market_type="A股",
            position_profile=position_profile,
            live_packet=live_packet,
            key_prefix=key_prefix,
            cards_expanded=False,
        )
    return packet


def _run_command_center_first_diagnosis_prewarm(
    *,
    target="",
    market_type="",
    position_profile=None,
    live_packet=None,
    force=False,
):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    if not (is_a_share_market(market_type) or a_share_manual_checks_service.is_a_share_ts_code(ticker)):
        packet = {
            "target": ticker,
            "market_type": market_type,
            "status": "skipped",
            "summary": "首诊预热仅对 A股当前标的自动读取公告/减持硬风险。",
            "deepseek_called": False,
            "updated_at": _cc_now(),
        }
        st.session_state["command_center_first_diagnosis_prewarm_packet"] = packet
        return packet

    existing_auto_packet = st.session_state.get(legacy_a_share_auto_hydrate_service.STATUS_KEY) or {}
    existing_modules = [
        module for module in (existing_auto_packet.get("modules") or [])
        if isinstance(module, dict)
    ]
    has_fresh_hard_risk = any(module.get("key") == "hard_risk" for module in existing_modules)
    try:
        last_at = float(st.session_state.get(legacy_a_share_auto_hydrate_service.LAST_AT_KEY) or 0)
    except Exception:
        last_at = 0.0
    ttl_seconds = int(
        st.session_state.get(
            legacy_a_share_auto_hydrate_service.TTL_KEY,
            legacy_a_share_auto_hydrate_service.DEFAULT_TTL_SECONDS,
        )
        or legacy_a_share_auto_hydrate_service.DEFAULT_TTL_SECONDS
    )
    existing_target = str(existing_auto_packet.get("target") or "").strip().upper()
    ticker_text = str(ticker or "").strip().upper()
    can_reuse_existing = (
        not force
        and has_fresh_hard_risk
        and existing_target == ticker_text
        and last_at
        and (time.time() - last_at) < ttl_seconds
    )
    if can_reuse_existing:
        auto_packet = {
            **existing_auto_packet,
            "skipped_by_ttl": True,
            "decision": {
                **(existing_auto_packet.get("decision") or {}),
                "reason": "partition_cache_active",
                "ttl_seconds": ttl_seconds,
            },
        }
    else:
        try:
            auto_packet = _run_legacy_a_share_auto_hydrate(
                target=ticker,
                market_type=market_type or "A股",
                position_profile=position_profile,
                live_packet=live_packet,
                module_keys=["hard_risk"],
                force=force,
            )
        except Exception as exc:
            packet = {
                "target": ticker,
                "market_type": market_type or "A股",
                "status": "failed",
                "status_label": "预热失败",
                "summary": f"公告/减持硬风险预热失败：{exc}；页面继续使用上次缓存。",
                "deepseek_called": False,
                "updated_at": _cc_now(),
            }
            st.session_state["command_center_first_diagnosis_prewarm_packet"] = packet
            return packet
    hard_risk_packet = st.session_state.get("command_center_hard_risk_packet") or {}
    if not isinstance(hard_risk_packet, dict) or not hard_risk_packet:
        hard_risk_packet = hard_risk_packet_service.build_command_center_hard_risk_packet(
            st.session_state,
            live_packet=live_packet or st.session_state.get("command_center_live_packet") or {},
            target=ticker,
        )
        st.session_state["command_center_hard_risk_packet"] = hard_risk_packet

    hard_module = next(
        (
            module
            for module in (auto_packet.get("modules") or [])
            if isinstance(module, dict) and module.get("key") == "hard_risk"
        ),
        {},
    )
    risk_items = [
        item
        for item in (hard_risk_packet.get("risk_items") or hard_risk_packet.get("announcement_items") or [])
        if isinstance(item, dict)
    ]
    status_label = (
        hard_module.get("status_label")
        or hard_risk_packet.get("status_label")
        or hard_risk_packet.get("data_status")
        or "待验证"
    )
    packet = {
        "target": ticker,
        "market_type": market_type or "A股",
        "status": hard_module.get("status") or hard_risk_packet.get("data_status") or "unknown",
        "status_label": status_label,
        "summary": (
            f"公告/减持硬风险：{status_label}；"
            f"线索 {len(risk_items)} 条；同标的短时间内不重复请求。"
        ),
        "hard_risk_packet": hard_risk_packet,
        "auto_hydrate_packet": auto_packet,
        "risk_item_count": len(risk_items),
        "skipped_by_ttl": bool(auto_packet.get("skipped_by_ttl")),
        "deepseek_called": False,
        "updated_at": hard_risk_packet.get("updated_at") or auto_packet.get("updated_at") or _cc_now(),
    }
    st.session_state["command_center_first_diagnosis_prewarm_packet"] = packet
    return packet


def render_home_a_share_diagnostic_recovery_controls(home_snapshot=None, target="", market_type="", position_profile=None, live_packet=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    if not (is_a_share_market(market_type) or a_share_manual_checks_service.is_a_share_ts_code(ticker)):
        return
    diagnostic = home_snapshot.get("a_share_user_data_diagnostic") if isinstance(home_snapshot, dict) else {}
    diagnostic = diagnostic if isinstance(diagnostic, dict) else {}
    actions = [
        action
        for action in (diagnostic.get("recovery_actions") or [])
        if isinstance(action, dict) and action.get("refresh_policy") == "button_gated"
    ]
    if not actions:
        return
    available_keys = {spec["key"] for spec in _get_legacy_a_share_auto_hydrate_specs()}
    runnable_actions = [action for action in actions if str(action.get("key") or "") in available_keys][:6]
    if not runnable_actions:
        return
    module_keys = [str(action.get("key") or "") for action in runnable_actions]
    packet = _run_legacy_a_share_auto_hydrate(
        target=ticker,
        market_type=market_type or "A股",
        position_profile=position_profile,
        live_packet=live_packet,
        module_keys=module_keys,
    )
    with st.container(border=True):
        st.markdown("#### A股专业数据自动补水")
        _render_legacy_a_share_auto_hydrate_cards(
            packet,
            target=ticker,
            market_type=market_type or "A股",
            position_profile=position_profile,
            live_packet=live_packet,
            key_prefix="home_a_share_recovery",
            module_filter=module_keys,
            cards_expanded=False,
        )
        if st.button("强制刷新本页 A股证据", key="btn_home_a_share_force_refresh", width="stretch"):
            _run_legacy_a_share_auto_hydrate(
                target=ticker,
                market_type=market_type or "A股",
                position_profile=position_profile,
                live_packet=live_packet,
                module_keys=module_keys,
                force=True,
            )
            st.rerun()
        notice = home_snapshot_service.build_a_share_diagnostic_recovery_result_notice(st.session_state)
        if notice:
            if notice.get("status") == "recovered":
                st.success(notice["message"])
            elif notice.get("status") == "blocked":
                st.warning(notice["message"])
            else:
                st.info(notice["message"])
            with st.expander("查看诊断详情", expanded=False):
                st.caption(
                    f"回流：{notice.get('writes_packet') or 'command_center_facts_packet'}"
                    f"｜来源：{notice.get('source') or 'A股自动检测'}"
                    f"｜更新时间：{notice.get('updated_at') or '暂无'}"
                    f"｜{notice.get('next_action') or '继续观察。'}"
                )


COMMAND_CENTER_TOOL_RECOVERY_NOTICE_KEYS = [
    "command_center_last_tool_recovery_key",
    "command_center_last_tool_recovery_label",
    "command_center_last_tool_recovery_provider",
    "command_center_last_tool_recovery_api",
    "command_center_last_tool_recovery_writes_packet",
    "command_center_last_tool_recovery_target_tab",
    "command_center_last_tool_recovery_source_type",
    "command_center_last_tool_recovery_source_label",
    "command_center_last_tool_recovery_provider_dependencies",
    "command_center_last_tool_recovery_provider_dependency_summary",
    "command_center_last_tool_recovery_packet_route_summary",
    "command_center_last_tool_recovery_provider_decision_impact",
    "command_center_last_tool_recovery_priority_label",
    "command_center_last_tool_recovery_decision_mode",
    "command_center_last_tool_recovery_decision_impact",
    "command_center_last_tool_recovery_recovery_mode",
    "command_center_last_tool_recovery_recovery_mode_label",
    "command_center_last_tool_recovery_recovery_steps",
    "command_center_last_tool_recovery_button_context",
    "command_center_last_tool_recovery_navigation_label",
    "command_center_last_tool_recovery_policy",
]


def _clear_command_center_tool_recovery_notice_state():
    for recovery_key in COMMAND_CENTER_TOOL_RECOVERY_NOTICE_KEYS:
        st.session_state.pop(recovery_key, None)


def _tool_recovery_user_message(notice, manual_check_hint=None, result_notice=None):
    payload = notice if isinstance(notice, dict) else {}
    hint = manual_check_hint if isinstance(manual_check_hint, dict) else {}
    result = result_notice if isinstance(result_notice, dict) else {}
    label = str(payload.get("label") or hint.get("label") or "这项数据").strip()
    target_tab = str(payload.get("target_tab") or hint.get("target_tab") or payload.get("selected_tab") or "对应模块").strip()
    selected_tab = str(payload.get("selected_tab") or "").strip()
    button_label = str(
        hint.get("module_button_label")
        or hint.get("button_label")
        or result.get("manual_button_label")
        or "刷新"
    ).strip()
    if result.get("status") == "recovered":
        return f"{label} 已同步到综合中心；可返回综合推演中心复核。"
    if label == "融资 ETF" or target_tab == "融资 ETF":
        if selected_tab and selected_tab != target_tab:
            return f"当前在“{selected_tab}”，目标模块是“{target_tab}”。"
        return f"融资 ETF 数据未刷新。请点击“{button_label}”；不会调用 DeepSeek。"
    if label == "量化推演" or target_tab == "量化推演":
        if selected_tab and selected_tab != target_tab:
            return f"当前在“{selected_tab}”，目标模块是“{target_tab}”。"
        return "量化推演已有缓存，可直接生成新推演；不会自动调用 DeepSeek。"
    if label == "龙虎榜":
        return "龙虎榜数据待验证，可展开技术诊断或重新检测。"
    if selected_tab and target_tab and selected_tab != target_tab:
        return f"当前在“{selected_tab}”，目标模块是“{target_tab}”。"
    return f"{label} 数据待补。请点击“{button_label}”；不会调用 DeepSeek。"


def render_legacy_tool_recovery_notice_panel(recovery_notice, *, legacy_tab=""):
    notice = recovery_notice if isinstance(recovery_notice, dict) else {}
    if not notice:
        return
    label = notice.get("label") or legacy_tab or "旧工具能力"
    recovery_result_notice = home_snapshot_service.build_tool_recovery_result_notice(
        st.session_state,
        selected_tab=legacy_tab,
    )
    if recovery_result_notice.get("status") == "recovered":
        _clear_command_center_tool_recovery_notice_state()
        return
    manual_check_hint = home_snapshot_service.build_tool_recovery_manual_check_hint(
        st.session_state,
        selected_tab=legacy_tab,
    )
    target_tab = str(notice.get("target_tab") or manual_check_hint.get("target_tab") or legacy_tab or "").strip()
    selected_tab = str(notice.get("selected_tab") or legacy_tab or "").strip()
    if target_tab and selected_tab and selected_tab != target_tab:
        return
    user_message = _tool_recovery_user_message(
        notice,
        manual_check_hint=manual_check_hint,
        result_notice=recovery_result_notice,
    )
    st.caption(f"待验证证据：{user_message}")
    with st.expander("查看技术诊断", expanded=False):
        st.caption(
            f"原始提示：{notice.get('message') or '暂无'}｜"
            f"{notice.get('action_hint') or ''}｜{notice.get('safety_text') or ''}"
        )
        if recovery_result_notice.get("status") == "recovered":
            st.success(recovery_result_notice["message"])
            st.caption(f"更新时间：{recovery_result_notice.get('updated_at') or '暂无'}｜{recovery_result_notice['next_action']}")
            st.caption(f"来源：{recovery_result_notice.get('source') or '本地 packet'}")
        elif recovery_result_notice:
            st.warning(recovery_result_notice["message"])
            st.caption(recovery_result_notice["next_action"])
        if manual_check_hint.get("available"):
            st.caption(manual_check_hint.get("message") or manual_check_hint.get("help_text") or "当前模块已接入单项检测状态。")
        elif manual_check_hint:
            st.caption(manual_check_hint["message"])
            if manual_check_hint.get("module_button_hint"):
                st.caption(manual_check_hint.get("help_text", ""))
        st.markdown("##### 工程细节")
        if notice.get("provider_dependency_summary"):
            st.caption(f"provider 依赖：{notice['provider_dependency_summary']}")
        if notice.get("packet_route_summary"):
            st.caption(f"packet 路由：{notice['packet_route_summary']}")
        if notice.get("provider_decision_impact"):
            st.caption(f"provider 影响：{notice['provider_decision_impact']}")
        if notice.get("decision_impact"):
            st.caption(f"决策影响：{notice['decision_impact']}")
        recovery_steps = notice.get("recovery_steps") or []
        if recovery_steps:
            st.caption("恢复路径：" + " → ".join(str(step) for step in recovery_steps if step))
        if st.button("忽略本次", key="btn_clear_home_tool_recovery_notice"):
            _clear_command_center_tool_recovery_notice_state()
            st.rerun()


def render_legacy_a_share_gap_recovery_panel(snapshot_context=None, key_prefix="legacy_a_share"):
    payload = snapshot_context if isinstance(snapshot_context, dict) else {}
    legacy_gap_summary = home_snapshot_service.build_legacy_a_share_gap_summary(payload)
    if not isinstance(legacy_gap_summary, dict):
        return
    gap_items = [item for item in (legacy_gap_summary.get("items") or []) if isinstance(item, dict)]
    if not gap_items:
        return
    module_key_map = {
        "command_center_moneyflow_packet": "moneyflow",
        "command_center_dragon_tiger_packet": "dragon_tiger",
        "command_center_margin_packet": "margin",
        "command_center_limit_emotion_packet": "limit_emotion",
        "command_center_chip_packet": "chip_radar",
        "command_center_hard_risk_packet": "hard_risk",
    }
    module_keys = []
    for item in gap_items:
        text = " ".join(
            str(value or "")
            for value in [
                item.get("key"),
                item.get("api"),
                item.get("api_hint"),
                item.get("writes_packet"),
                item.get("label"),
            ]
        )
        matched_key = module_key_map.get(str(item.get("writes_packet") or ""))
        if not matched_key:
            for packet_key, module_key in module_key_map.items():
                if packet_key in text:
                    matched_key = module_key
                    break
        if not matched_key:
            if "龙虎" in text or "top_" in text:
                matched_key = "dragon_tiger"
            elif "融资融券" in text or "margin" in text:
                matched_key = "margin"
            elif "资金" in text or "moneyflow" in text:
                matched_key = "moneyflow"
            elif "涨跌停" in text or "limit" in text:
                matched_key = "limit_emotion"
            elif "筹码" in text or "cyq" in text:
                matched_key = "chip_radar"
            elif "公告" in text or "硬风险" in text or "anns" in text:
                matched_key = "hard_risk"
        if matched_key and matched_key not in module_keys:
            module_keys.append(matched_key)
    ticker = (
        payload.get("target")
        or payload.get("ticker")
        or st.session_state.get("current_stock_code")
        or (st.session_state.get("position_profile") or {}).get("ticker")
        or ""
    )
    auto_packet = {}
    if module_keys:
        auto_packet = _run_legacy_a_share_auto_hydrate(
            target=ticker,
            market_type="A股",
            position_profile=st.session_state.get("position_profile") or st.session_state.get("current_holding_context") or {},
            live_packet=st.session_state.get("command_center_live_packet") or {},
            module_keys=module_keys,
        )
    absence_ledger = home_snapshot_service.build_old_workspace_data_absence_ledger(
        {**payload, "legacy_a_share_gap_summary": legacy_gap_summary}
    )
    with st.container(border=True):
        st.markdown("#### A股专业数据分区预热")
        if auto_packet:
            st.caption(
                f"{auto_packet.get('summary_text') or '已按当前标的自动检测 A股专业数据'}｜"
                "按钮仅用于强制重检；DeepSeek 未调用。"
            )
            _render_legacy_a_share_auto_hydrate_cards(
                auto_packet,
                target=ticker,
                market_type="A股",
                position_profile=st.session_state.get("position_profile") or st.session_state.get("current_holding_context") or {},
                live_packet=st.session_state.get("command_center_live_packet") or {},
                key_prefix=f"{key_prefix}_gap",
                module_filter=module_keys,
                cards_expanded=False,
            )
        else:
            st.caption("当前没有可自动映射的 A股专业分区；页面保留缓存与失败原因，DeepSeek 未调用。")
        with st.expander("查看旧版缺口详情", expanded=False):
            st.caption(
                absence_ledger.get("short_answer")
                or "Tushare 基础连接正常不等于每个旧版专业接口都有当日数据；这里按接口原因分账。"
            )
            st.caption("旧版缺口账只用于排查；当前页面已按分区自动尝试补水，仍不会调用 DeepSeek。")
            detail_rows = []
            for item in gap_items:
                detail_rows.append(
                    {
                        "名称": item.get("label"),
                        "状态": item.get("readable_state") or item.get("status_label"),
                        "原因": item.get("why_not_found") or item.get("diagnostic_answer") or item.get("message"),
                        "决策保护": item.get("decision_guardrail"),
                    }
                )
            if detail_rows:
                st.dataframe(pd.DataFrame(detail_rows), width="stretch", hide_index=True)


def render_home_evidence_backfill_controls(evidence_radar_vm=None, target="", market_type="", position_profile=None, live_packet=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    ticker = target or profile.get("ticker") or st.session_state.get("current_stock_code") or ""
    if not (is_a_share_market(market_type) or a_share_manual_checks_service.is_a_share_ts_code(ticker)):
        return
    runner_map = {
        "moneyflow": ("资金流", _run_manual_moneyflow_capability_check),
        "hard_risk": ("公告/硬风险", _run_manual_hard_risk_capability_check),
        "margin": ("融资融券", _run_manual_margin_detail_capability_check),
        "limit_emotion": ("涨跌停/情绪", _run_manual_limit_cpt_capability_check),
        "dragon_tiger": ("龙虎榜", _run_manual_dragon_tiger_capability_check),
        "chip_radar": ("筹码/胜率", _run_manual_chip_radar_capability_check),
    }
    recovery_summary = evidence_summary_service.build_home_evidence_recovery_summary(
        evidence_radar_vm,
        runnable_keys=runner_map.keys(),
        limit=2,
    )
    actions = recovery_summary.get("actions") or []
    runnable_actions = [
        action
        for action in actions
        if isinstance(action, dict) and str(action.get("key") or "") in runner_map
    ]
    if not runnable_actions:
        return
    module_keys = [str(action.get("key") or "") for action in runnable_actions]
    auto_packet = _run_legacy_a_share_auto_hydrate(
        target=ticker,
        market_type=market_type or "A股",
        position_profile=position_profile,
        live_packet=live_packet,
        module_keys=module_keys,
    )
    with st.container(border=True):
        st.markdown(f"#### A股证据自动补水｜{recovery_summary.get('title') or '关键证据'}")
        st.caption(
            f"{auto_packet.get('summary_text') or recovery_summary.get('summary') or '已按当前标的自动检测关键 Tushare 证据'}｜"
            "同一标的 TTL 内不重复请求；DeepSeek 未调用。"
        )
        if st.button("强制刷新关键 A股证据", key="btn_cc_home_evidence_force_refresh", width="stretch"):
            _run_legacy_a_share_auto_hydrate(
                target=ticker,
                market_type=market_type or "A股",
                position_profile=position_profile,
                live_packet=live_packet,
                module_keys=module_keys,
                force=True,
            )
            st.rerun()
        with st.expander("查看单项状态 / 重新检测", expanded=False):
            cols = st.columns(min(3, len(runnable_actions)))
            for index, action in enumerate(runnable_actions):
                key = str(action.get("key") or "")
                result_label, runner = runner_map[key]
                manual_action = action.get("manual_action") or {}
                button_label = "重新检测" + (action.get("label") or result_label)
                action_hint = action.get("action_hint") or manual_action.get("reason") or "自动补水失败时可单项重试。"
                with cols[index % len(cols)]:
                    st.caption(f"{action.get('evidence_label') or '待验证证据'}｜{action.get('label') or result_label}")
                    st.caption(action_hint)
                    result = _render_manual_capability_check_button(
                        button_label,
                        f"btn_cc_home_evidence_backfill_{key}",
                        f"正在重新检测{result_label}证据...",
                        result_label,
                        runner,
                        target=target,
                        position_profile=position_profile,
                        live_packet=live_packet,
                    )
                    if result:
                        fallback_writes_packets = {
                            "moneyflow": "command_center_moneyflow_packet",
                            "dragon_tiger": "command_center_dragon_tiger_packet",
                            "margin": "command_center_margin_packet",
                            "limit_emotion": "command_center_limit_emotion_packet",
                            "chip_radar": "command_center_chip_packet",
                            "hard_risk": "command_center_hard_risk_packet",
                        }
                        _remember_a_share_manual_recovery_result(
                            result,
                            key=key,
                            label=action.get("label") or result_label,
                            writes_packet=manual_action.get("writes_packet") or fallback_writes_packets.get(key) or f"command_center_{key}_packet",
                            api_hint=manual_action.get("api") or manual_action.get("api_hint"),
                        )
                        _persist_home_action_snapshot(
                            live_packet=live_packet or st.session_state.get("command_center_live_packet") or {},
                            target=ticker,
                            position_profile=position_profile,
                        )


def _get_command_center_facts_packet(target="", name=""):
    return facts_packet_service.build_command_center_facts_packet(
        st.session_state,
        target=target,
        name=name,
    )


def _cc_is_a_share_market_type(market_type):
    text = str(market_type or "").strip()
    upper = text.upper()
    return upper.startswith("A_SHARE") or text in {"A股", "沪深A股"} or "A股" in text


def _cc_healthcheck_sample_ts_code(target=""):
    text = str(target or "").strip().upper()
    if not text:
        return "000001.SZ"
    if text.endswith(".SS"):
        return f"{text[:-3]}.SH"
    if text.endswith((".SH", ".SZ")):
        return text
    if text.isdigit() and len(text) == 6:
        return f"{text}.SH" if text.startswith("6") else f"{text}.SZ"
    return "000001.SZ"


def _cc_provider_refresh_result(module, ok=True, message="", source="", updated_at="", error=""):
    return {
        "module": module,
        "module_key": module,
        "ok": bool(ok),
        "status": "ok" if ok else "failed",
        "updated_at": updated_at or _cc_now(),
        "source": source or module,
        "message": message or ("完成" if ok else error or "失败"),
        "error": "" if ok else str(error or message or "未知错误"),
        "deepseek_called": False,
        "refresh_level": cc_service.REFRESH_LEVEL_MANUAL_BASIC,
    }


def _cc_refresh_yfinance_snapshot(target="", market_type=""):
    if not target:
        return {
            "skipped": True,
            "reason": "未锁定标的，yfinance 本轮跳过。",
            "updated_at": _cc_now(),
        }
    detail = get_current_price_detail(target, market_type)
    raw_source = str((detail or {}).get("raw_source") or "").lower()
    if raw_source != "yfinance":
        return {
            "skipped": True,
            "reason": f"本轮价格来源为 {(detail or {}).get('raw_source') or '不可用'}，未使用 yfinance。",
            "warning": (detail or {}).get("warning") or "",
            "data_date": (detail or {}).get("data_date") or "",
            "updated_at": _cc_now(),
        }
    return detail


def _cc_refresh_akshare_snapshot(target="", market_type=""):
    if not target or not _cc_is_a_share_market_type(market_type):
        return {
            "source_status": {},
            "warnings": ["非 A股标的或未锁定标的，AkShare 资金穿透本轮跳过。"],
            "mode": "skipped",
        }
    refresh_token = _cc_now()
    snapshot = cached_money_flow_snapshot(target, market_type, deep=False, refresh_token=refresh_token)
    session_key = f"akshare_money_flow_{target}_{market_type}"
    st.session_state[session_key] = snapshot
    return snapshot


def _cc_collect_full_data_refresh_probes(target="", market_type=""):
    provider_results = []
    provider_errors = []

    health_result = {}
    try:
        health_result = run_data_source_healthcheck(
            sample_ts_code=_cc_healthcheck_sample_ts_code(target),
            include_deepseek_ping=False,
            cache_version=f"command_center_full_data_{datetime.date.today().isoformat()}",
            _supabase_client=supabase,
            _deepseek_keys=st.session_state.get("ds_keys") or [],
        )
        st.session_state["last_data_source_healthcheck"] = health_result
        provider_results.append(
            _cc_provider_refresh_result(
                "数据源体检",
                ok=True,
                message="Tushare / Supabase 体检完成；DeepSeek 仅记录配置，未 ping。",
                source="run_data_source_healthcheck",
                updated_at=health_result.get("checked_at"),
            )
        )
    except Exception as exc:
        error = str(exc)
        provider_results.append(_cc_provider_refresh_result("数据源体检", ok=False, source="run_data_source_healthcheck", error=error))
        provider_errors.append({"module": "数据源体检", "message": error, "updated_at": _cc_now(), "source": "run_data_source_healthcheck"})

    yfinance_snapshot = {}
    try:
        yfinance_snapshot = _cc_refresh_yfinance_snapshot(target=target, market_type=market_type)
        provider_results.append(
            _cc_provider_refresh_result(
                "yfinance 行情",
                ok=not yfinance_snapshot.get("error"),
                message=yfinance_snapshot.get("reason") or yfinance_snapshot.get("warning") or "yfinance 探测完成。",
                source=yfinance_snapshot.get("raw_source") or "yfinance",
                updated_at=yfinance_snapshot.get("updated_at") or yfinance_snapshot.get("data_date"),
                error=yfinance_snapshot.get("error") or "",
            )
        )
    except Exception as exc:
        error = str(exc)
        yfinance_snapshot = {"price": None, "raw_source": "yfinance", "warning": error}
        provider_results.append(_cc_provider_refresh_result("yfinance 行情", ok=False, source="yfinance", error=error))
        provider_errors.append({"module": "yfinance 行情", "message": error, "updated_at": _cc_now(), "source": "yfinance"})

    akshare_snapshot = {}
    try:
        akshare_snapshot = _cc_refresh_akshare_snapshot(target=target, market_type=market_type)
        warnings = akshare_snapshot.get("warnings") if isinstance(akshare_snapshot, dict) else []
        provider_results.append(
            _cc_provider_refresh_result(
                "AkShare 资金穿透",
                ok=True,
                message=(warnings or ["AkShare 探测完成。"])[0],
                source="cached_money_flow_snapshot",
                updated_at=akshare_snapshot.get("updated_at") if isinstance(akshare_snapshot, dict) else "",
            )
        )
    except Exception as exc:
        error = str(exc)
        akshare_snapshot = {
            "source_status": {
                "individual_fund_flow_primary": {"used": True, "ok": False, "error": error},
                "individual_fund_flow_fallback": {"used": False, "ok": False, "error": ""},
            },
            "warnings": [error],
        }
        provider_results.append(_cc_provider_refresh_result("AkShare 资金穿透", ok=False, source="cached_money_flow_snapshot", error=error))
        provider_errors.append({"module": "AkShare 资金穿透", "message": error, "updated_at": _cc_now(), "source": "cached_money_flow_snapshot"})

    return {
        "health_result": health_result,
        "yfinance_snapshot": yfinance_snapshot,
        "akshare_snapshot": akshare_snapshot,
        "provider_results": provider_results,
        "provider_errors": provider_errors,
    }


def _cc_status_group_summary(packet):
    groups = (packet or {}).get("status_groups") or data_capability_governance_service.summarize_data_capability_packet(packet)
    return (
        f"可用 {len(groups.get('available') or [])}｜"
        f"失败 {len(groups.get('failed') or [])}｜"
        f"权限不足 {len(groups.get('no_permission') or [])}｜"
        f"缓存 {len(groups.get('cached') or [])}｜"
        f"无数据 {len(groups.get('no_data') or [])}｜"
        f"跳过 {len(groups.get('skipped') or [])}｜"
        f"未知 {len(groups.get('unknown') or [])}"
    )


def _run_command_center_full_data_refresh(target="", market_type="", price=None, position_profile=None, status=None):
    del price
    registry = data_capability_governance_service.build_initial_capability_registry(
        target=target,
        market_type=market_type,
        checked_at=_cc_now(),
    )

    def _progress(event, label, result):
        if status is None:
            return
        if event == "start":
            status.update(label=f"正在刷新{label}", state="running")
        elif event == "success":
            status.write(f"{label}：完成")
        elif event == "failure":
            status.write(
                f"{label}：失败，已继续下一步；"
                f"{(result or {}).get('message') or (result or {}).get('error') or (result or {}).get('last_error') or '未知错误'}"
            )

    refresh_summary = cc_service.run_refresh_sequence(
        COMMAND_CENTER_REFRESH_STEPS,
        lambda module_key, _label: _cc_run_refresh_step(
            module_key,
            target=target,
            market_type=market_type,
            price=None,
            position_profile=position_profile,
        ),
        progress_callback=_progress,
        refresh_level=cc_service.REFRESH_LEVEL_MANUAL_BASIC,
    )
    probes = _cc_collect_full_data_refresh_probes(target=target, market_type=market_type)
    for result in probes["provider_results"]:
        refresh_summary.setdefault("results", []).append(result)
        if status is not None:
            if result.get("ok"):
                status.write(f"{result.get('module')}：{result.get('message')}")
            else:
                status.write(f"{result.get('module')}：失败，已继续下一步；{result.get('error') or result.get('message')}")
    refresh_summary.setdefault("errors", []).extend(probes["provider_errors"])
    refresh_summary["mode"] = "full_data_refresh"
    refresh_summary["summary"] = "满血数据刷新完成：已执行 manual_basic 链路，并回流 provider capability 状态。"
    refresh_summary["deepseek_called"] = False

    live_packet = build_command_center_live_packet(
        target=target,
        refresh_level=cc_service.REFRESH_LEVEL_MANUAL_BASIC,
    )
    live_packet = _sync_command_center_home_candidate_packets(live_packet)
    first_snapshot = _persist_home_action_snapshot(
        live_packet=live_packet,
        target=target,
        position_profile=position_profile,
        refresh_summary=refresh_summary,
    )
    registry, data_capability_packet = data_capability_governance_service.apply_basic_refresh_capability_probe(
        registry,
        probes["health_result"],
        probes["yfinance_snapshot"],
        probes["akshare_snapshot"],
        probes["health_result"],
        deepseek_configured=bool(st.session_state.get("ds_keys") or []),
        deepseek_key_count=len(st.session_state.get("ds_keys") or []),
        home_snapshot=first_snapshot,
        market_type=market_type,
    )
    final_snapshot = _persist_home_action_snapshot(
        live_packet=live_packet,
        target=target,
        position_profile=position_profile,
        refresh_summary=refresh_summary,
    )
    registry = data_capability_governance_service.apply_home_snapshot_status(registry, final_snapshot)
    data_capability_packet = data_capability_governance_service.build_data_capability_packet(registry)
    st.session_state["command_center_data_capability_registry"] = registry
    st.session_state["command_center_data_capability_packet"] = data_capability_packet
    refresh_summary["data_capability_status_groups"] = data_capability_packet.get("status_groups") or {}
    refresh_summary["data_capability_summary"] = _cc_status_group_summary(data_capability_packet)
    st.session_state["command_center_refresh_summary"] = refresh_summary
    live_packet = _sync_command_center_home_candidate_packets(live_packet)
    _persist_home_action_snapshot(
        live_packet=live_packet,
        target=target,
        position_profile=position_profile,
        refresh_summary=refresh_summary,
    )
    return refresh_summary, live_packet, data_capability_packet


def _run_command_center_full_war_game(target="", market_type="", position_profile=None):
    data_capability_packet = _get_command_center_data_capability_packet()
    live_packet = build_command_center_live_packet(
        target=target,
        refresh_level=cc_service.REFRESH_LEVEL_MANUAL_DEEP,
    )
    live_packet["data_capability"] = data_capability_packet
    strategy_packet = strategy_service.safe_generate_strategy_execution_packet(
        st.session_state,
        target=target,
        position_profile=position_profile,
        live_packet=live_packet,
    )
    live_packet = cc_state_adapter.attach_command_center_child_packets_for_display(
        live_packet,
        strategy_execution_packet=strategy_packet,
    )
    decision_packet, live_packet = _generate_command_center_decision(
        live_packet,
        refresh_summary=st.session_state.get("command_center_refresh_summary") or {},
    )
    home_snapshot = _persist_home_action_snapshot(
        live_packet=live_packet,
        target=target,
        position_profile=position_profile,
        strategy_packet=strategy_packet,
        decision_packet=decision_packet,
    )
    evidence_radar_packet = evidence_summary_service.build_a_share_evidence_radar_view_model(home_snapshot)
    analysis_method_packet = _build_analysis_methods_display_packet(
        live_packet=live_packet,
        target=target,
        market_type=market_type,
        home_snapshot=home_snapshot,
    )
    projection_packet = projection_service.build_projection_packet(
        decision_packet=decision_packet,
        strategy_packet=strategy_packet,
        live_packet=live_packet,
        home_snapshot=home_snapshot,
        analysis_method_packet=analysis_method_packet,
        evidence_radar_packet=evidence_radar_packet,
        data_health_ledger=home_snapshot.get("data_health_ledger") if isinstance(home_snapshot, dict) else {},
        horizon_days=10,
    )
    st.session_state["command_center_projection_packet"] = projection_packet
    st.session_state["command_center_analysis_method_packet"] = analysis_method_packet
    st.session_state["command_center_evidence_radar_packet"] = evidence_radar_packet
    summary = {
        "status": "completed",
        "generated_at": _cc_now(),
        "data_capability_summary": _cc_status_group_summary(data_capability_packet),
        "strategy_status": strategy_packet.get("status") or "unknown",
        "decision_action": decision_packet.get("overall_action") or "等待",
        "projection_horizon_days": projection_packet.get("horizon_days") or 10,
        "deepseek_called": False,
        "deepseek_note": "本轮未调用 DeepSeek；如需解释请手动点击 DeepSeek 综合解释。",
    }
    st.session_state["command_center_full_war_game_summary"] = summary
    return summary, live_packet, decision_packet, strategy_packet, projection_packet


def _parse_deepseek_json_payload(content):
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}
    text = content.strip()
    if not text:
        return {}
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return {}
    return {}


def _run_command_center_deepseek_projection_overlay(
    *,
    target="",
    market_type="",
    position_profile=None,
    live_packet=None,
    decision_packet=None,
    strategy_packet=None,
    projection_packet=None,
    home_snapshot=None,
):
    base_projection = projection_packet or st.session_state.get("command_center_projection_packet") or {}
    live_payload = live_packet or st.session_state.get("command_center_live_packet") or build_command_center_live_packet(target=target)
    quant_packet = (
        live_payload.get("quant")
        if isinstance(live_payload, dict)
        else {}
    ) or st.session_state.get("command_center_quant_packet") or {}
    discipline_packet = (
        live_payload.get("discipline")
        if isinstance(live_payload, dict)
        else {}
    ) or st.session_state.get("command_center_discipline_packet") or st.session_state.get("discipline_backtest_packet") or {}
    prompt_context = projection_service.build_deepseek_projection_prompt_context(
        target=target,
        market_type=market_type,
        position_profile=position_profile,
        live_packet=live_payload,
        decision_packet=decision_packet or st.session_state.get("command_center_decision_packet") or {},
        strategy_packet=strategy_packet or st.session_state.get("strategy_execution_packet") or {},
        projection_packet=base_projection,
        home_snapshot=home_snapshot or st.session_state.get("command_center_home_snapshot") or {},
        quant_packet=quant_packet,
        discipline_packet=discipline_packet,
    )
    prompt = f"""
你是 stock-MING 的趋势推演整理器。请只基于输入的结构化 packet，手动增强未来 5-10 个交易日三路径曲线。

硬性要求：
1. 只输出 JSON，不要 Markdown，不要解释前缀。
2. 不得编造未在 packet 中出现的公告、资金流、舆情、价格或新闻。
3. 必须把“量化推演”和“交易纪律实验室”的证据纳入路径触发条件；缺失就写“待验证”并降低乐观概率。
4. 公告/硬风险、减持、融资风险、成本价、持仓数量、当前价必须优先进入风险提示。
5. DeepSeek 只做解释和路径整理，不给自动下单指令。
6. 曲线锚定 current_price_anchor；如果没有把握，给 target_pct，不要乱造逐日价格。

JSON schema:
{{
  "summary": "一句话说明本轮路径依据和置信度",
  "probability": {{"optimistic": 25, "neutral": 50, "cautious": 25}},
  "paths": [
    {{
      "name": "乐观路径",
      "probability": 25,
      "target_pct": 3.2,
      "trigger": "触发条件",
      "action": "对应动作",
      "risk": "风险提示",
      "rationale": "为何这样画曲线",
      "points": [{{"t": 0, "value": 100.0}}, {{"t": 5, "value": 102.0}}, {{"t": 10, "value": 103.2}}]
    }},
    {{"name": "中性路径", "probability": 50, "target_pct": 0.8, "trigger": "", "action": "", "risk": "", "rationale": ""}},
    {{"name": "谨慎路径", "probability": 25, "target_pct": -3.0, "trigger": "", "action": "", "risk": "", "rationale": ""}}
  ],
  "quant_notes": ["量化证据或缺口"],
  "discipline_notes": ["交易纪律边界"],
  "risk_alerts": ["公告/融资/价格/数据缺口风险"]
}}

输入 packet:
{json.dumps(prompt_context, ensure_ascii=False, indent=2, default=str)[:14000]}
"""
    raw = call_deepseek_non_stream(
        prompt,
        system_role="你是克制的交易路径建模助手，只基于用户提供的结构化 packet 生成可验证三路径 JSON，不编造实时事实。",
        max_tokens=2200,
    )
    parsed = _parse_deepseek_json_payload(raw)
    enhanced = projection_service.merge_deepseek_projection_overlay(
        base_projection,
        parsed,
        now=_cc_now(),
        model="deepseek-chat",
        raw_text=raw,
        token_estimate=estimate_tokens(raw or ""),
    )
    if parsed:
        st.session_state["command_center_projection_packet"] = enhanced
        page_packet = dict(st.session_state.get("command_center_auto_analysis_packet") or {})
        page_packet["projection_packet"] = enhanced
        st.session_state["command_center_auto_analysis_packet"] = page_packet
        st.session_state["command_center_deepseek_projection_generated_at"] = enhanced.get("updated_at")
        st.session_state["command_center_deepseek_projection_raw"] = raw or ""
    return enhanced, parsed, raw


def _enrich_position_profile_for_command_center(profile=None, *, horizon="", margin_ratio_pct=0):
    enriched = dict(profile or {})
    margin_ratio = _num(margin_ratio_pct, 0) or 0
    enriched["analysis_horizon"] = horizon or enriched.get("analysis_horizon") or "短中期"
    enriched["margin_ratio_pct"] = round(margin_ratio, 2)
    enriched["margin_ratio"] = round(margin_ratio / 100, 4)
    if margin_ratio > 0:
        enriched["margin_note"] = f"当前输入融资比例 {margin_ratio:.1f}%，综合推演仅用于风险预算，不自动下单或融资。"
    else:
        enriched["margin_note"] = "未输入融资比例，按普通持仓风险预算处理。"
    return enriched


def _run_command_center_analysis_chain(target="", market_type="", position_profile=None, *, refresh_level=None, status=None):
    refresh_level = refresh_level or cc_service.REFRESH_LEVEL_MANUAL_BASIC
    errors = []

    def _status_write(message):
        if status is not None:
            status.write(message)

    try:
        live_packet = build_command_center_live_packet(target=target, refresh_level=refresh_level)
        live_packet = _sync_command_center_home_candidate_packets(live_packet)
        live_packet["data_capability"] = _get_command_center_data_capability_packet()
        _status_write("已聚合本地缓存与上次成功数据。")
    except Exception as exc:
        live_packet = {"refresh_level": refresh_level, "status": "partial_failed", "last_error": str(exc)}
        errors.append(f"本地数据聚合失败：{exc}")

    try:
        strategy_packet = strategy_service.safe_generate_strategy_execution_packet(
            st.session_state,
            target=target,
            position_profile=position_profile,
            live_packet=live_packet,
        )
        live_packet = cc_state_adapter.attach_command_center_child_packets_for_display(
            live_packet,
            strategy_execution_packet=strategy_packet,
        )
        _status_write("已生成策略执行建议。")
    except Exception as exc:
        strategy_packet = _get_strategy_execution_display_packet()
        errors.append(f"策略执行建议失败：{exc}")

    try:
        decision_packet, live_packet = _generate_command_center_decision(live_packet)
        _status_write("已生成今日总决策。")
    except Exception as exc:
        decision_packet = _get_command_center_decision_display_packet()
        errors.append(f"今日总决策失败：{exc}")

    try:
        home_snapshot = _persist_home_action_snapshot(
            live_packet=live_packet,
            target=target,
            position_profile=position_profile,
            strategy_packet=strategy_packet,
            decision_packet=decision_packet,
        )
    except Exception as exc:
        home_snapshot = st.session_state.get("command_center_home_snapshot") or {}
        errors.append(f"首页快照更新失败：{exc}")

    try:
        evidence_radar_packet = evidence_summary_service.build_a_share_evidence_radar_view_model(home_snapshot)
        analysis_method_packet = _build_analysis_methods_display_packet(
            live_packet=live_packet,
            target=target,
            market_type=market_type,
            home_snapshot=home_snapshot,
        )
        projection_packet = projection_service.build_projection_packet(
            decision_packet=decision_packet,
            strategy_packet=strategy_packet,
            live_packet=live_packet,
            home_snapshot=home_snapshot,
            analysis_method_packet=analysis_method_packet,
            evidence_radar_packet=evidence_radar_packet,
            data_health_ledger=home_snapshot.get("data_health_ledger") if isinstance(home_snapshot, dict) else {},
            horizon_days=10,
        )
        st.session_state["command_center_projection_packet"] = projection_packet
        st.session_state["command_center_analysis_method_packet"] = analysis_method_packet
        st.session_state["command_center_evidence_radar_packet"] = evidence_radar_packet
        _status_write("已生成未来 5-10 日趋势推演。")
    except Exception as exc:
        evidence_radar_packet = st.session_state.get("command_center_evidence_radar_packet") or {}
        analysis_method_packet = st.session_state.get("command_center_analysis_method_packet") or {}
        projection_packet = st.session_state.get("command_center_projection_packet") or {}
        errors.append(f"趋势推演失败：{exc}")

    st.session_state["command_center_live_packet"] = live_packet
    return {
        "live_packet": live_packet,
        "strategy_packet": strategy_packet,
        "decision_packet": decision_packet,
        "home_snapshot": home_snapshot,
        "evidence_radar_packet": evidence_radar_packet,
        "analysis_method_packet": analysis_method_packet,
        "projection_packet": projection_packet,
        "errors": errors,
        "deepseek_called": False,
    }


def _safe_get_command_center_price_detail(target="", market_type=""):
    try:
        return get_current_price_detail(target, market_type)
    except Exception as exc:
        return {
            "ticker": target,
            "price": None,
            "price_source": "unavailable",
            "data_date": "",
            "raw_source": "",
            "fallback": bool(_cc_is_a_share_market_type(market_type)),
            "warning": str(exc),
        }


def _build_command_center_auto_capability_packet(
    target="",
    market_type="",
    price_detail=None,
    home_snapshot=None,
    akshare_snapshot=None,
):
    registry = data_capability_governance_service.build_initial_capability_registry(
        target=target,
        market_type=market_type,
        checked_at=_cc_now(),
    )
    registry = data_capability_governance_service.apply_yfinance_quote(
        registry,
        price_detail or {},
        market_type=market_type,
    )
    registry = data_capability_governance_service.apply_akshare_snapshot(
        registry,
        akshare_snapshot or {},
    )
    registry = data_capability_governance_service.apply_deepseek_status(
        registry,
        bool(st.session_state.get("ds_keys") or []),
        len(st.session_state.get("ds_keys") or []),
    )
    registry = data_capability_governance_service.apply_home_snapshot_status(
        registry,
        home_snapshot or st.session_state.get("command_center_home_snapshot") or {},
    )
    packet = data_capability_governance_service.build_data_capability_packet(registry)
    st.session_state["command_center_data_capability_registry"] = registry
    st.session_state["command_center_data_capability_packet"] = packet
    return packet


def _cc_collect_auto_page_akshare_snapshot(target="", market_type=""):
    if not target or not _cc_is_a_share_market_type(market_type):
        return {
            "snapshot": {
                "source_status": {},
                "warnings": ["非 A股标的或未锁定标的，AkShare 资金穿透本轮跳过。"],
                "mode": "skipped",
            },
            "result": _cc_provider_refresh_result(
                "AkShare 资金穿透",
                ok=True,
                message="非 A股标的或未锁定标的，AkShare 资金穿透本轮跳过。",
                source="cached_money_flow_snapshot",
            ),
            "error": None,
        }
    try:
        refresh_token = f"command_center_auto_akshare_{target}_{datetime.date.today().isoformat()}"
        snapshot = cached_money_flow_snapshot(target, market_type, deep=False, refresh_token=refresh_token)
        session_key = f"akshare_money_flow_{target}_{market_type}"
        st.session_state[session_key] = snapshot
        warnings = snapshot.get("warnings") if isinstance(snapshot, dict) else []
        return {
            "snapshot": snapshot or {},
            "result": _cc_provider_refresh_result(
                "AkShare 资金穿透",
                ok=True,
                message=(warnings or ["AkShare 轻量资金快照已缓存。"])[0],
                source="cached_money_flow_snapshot",
                updated_at=(snapshot or {}).get("updated_at") if isinstance(snapshot, dict) else "",
            ),
            "error": None,
        }
    except Exception as exc:
        error = str(exc)
        snapshot = {
            "source_status": {
                "individual_fund_flow_primary": {"used": True, "ok": False, "error": error},
                "individual_fund_flow_fallback": {"used": False, "ok": False, "error": ""},
            },
            "warnings": [error],
        }
        return {
            "snapshot": snapshot,
            "result": _cc_provider_refresh_result("AkShare 资金穿透", ok=False, source="cached_money_flow_snapshot", error=error),
            "error": {"module": "AkShare 资金穿透", "message": error, "updated_at": _cc_now(), "source": "cached_money_flow_snapshot"},
        }


def _command_center_auto_refresh_ttl_seconds():
    default_ttl = 300
    value = st.session_state.get("command_center_auto_refresh_ttl_seconds")
    try:
        ttl = int(value)
    except Exception:
        ttl = default_ttl
    ttl = max(180, min(600, ttl or default_ttl))
    st.session_state["command_center_auto_refresh_ttl_seconds"] = ttl
    return ttl


def _command_center_auto_refresh_fingerprint(target="", position_profile=None, refresh_level=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    payload = {
        "ticker": str(target or profile.get("ticker") or ""),
        "shares": _cc_round(_num(profile.get("holding_units"), 0) or 0, 4),
        "cost_price": _cc_round(_num(profile.get("cost_price"), 0) or 0, 4),
        "horizon": str(profile.get("analysis_horizon") or ""),
        "margin_ratio": _cc_round(_num(profile.get("margin_ratio_pct"), 0) or 0, 4),
        "refresh_level": refresh_level or cc_service.REFRESH_LEVEL_MANUAL_BASIC,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _command_center_parse_iso_time(value):
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value))
    except Exception:
        return None


def _command_center_auto_refresh_guard(target="", position_profile=None, refresh_level=None):
    previous_status = st.session_state.get("command_center_auto_refresh_status") or {}
    ttl = _command_center_auto_refresh_ttl_seconds()
    fingerprint = _command_center_auto_refresh_fingerprint(
        target=target,
        position_profile=position_profile,
        refresh_level=refresh_level,
    )
    previous_fingerprint = st.session_state.get("command_center_auto_refresh_fingerprint") or ""
    last_at = st.session_state.get("command_center_auto_refresh_last_at") or ""
    last_dt = _command_center_parse_iso_time(last_at)
    age_seconds = None
    if last_dt is not None:
        age_seconds = max(0, (datetime.datetime.now() - last_dt).total_seconds())
    cached_packet = st.session_state.get("command_center_auto_analysis_packet") or {}
    if not previous_fingerprint or not cached_packet:
        reason = "first_enter"
    elif previous_fingerprint != fingerprint:
        reason = "fingerprint_changed"
    elif age_seconds is None or age_seconds >= ttl:
        reason = "ttl_expired"
    else:
        reason = "ttl_active"
    should_refresh = reason != "ttl_active"
    status = {
        "fingerprint": fingerprint,
        "previous_fingerprint": previous_fingerprint,
        "last_at": last_at,
        "ttl_seconds": ttl,
        "age_seconds": round(age_seconds, 2) if age_seconds is not None else None,
        "should_refresh": should_refresh,
        "reason": reason,
        "run_count": int(previous_status.get("run_count") or 0),
        "deepseek_called": False,
    }
    st.session_state["command_center_auto_refresh_status"] = status
    return status


def _mark_command_center_auto_refresh_guard(status=None, *, reason="completed", forced=False):
    status = dict(status or st.session_state.get("command_center_auto_refresh_status") or {})
    now_text = _cc_now()
    previous_run_count = int((st.session_state.get("command_center_auto_refresh_status") or {}).get("run_count") or 0)
    fingerprint = status.get("fingerprint") or _command_center_auto_refresh_fingerprint()
    st.session_state["command_center_auto_refresh_fingerprint"] = fingerprint
    st.session_state["command_center_auto_refresh_last_at"] = now_text
    status.update(
        {
            "fingerprint": fingerprint,
            "last_at": now_text,
            "should_refresh": False,
            "reason": reason,
            "forced": bool(forced),
            "run_count": previous_run_count + 1,
            "deepseek_called": False,
        }
    )
    st.session_state["command_center_auto_refresh_status"] = status
    return status


def _mark_command_center_auto_refresh_skipped(status=None):
    status = dict(status or st.session_state.get("command_center_auto_refresh_status") or {})
    previous = st.session_state.get("command_center_auto_refresh_status") or {}
    status.update(
        {
            "should_refresh": False,
            "reason": status.get("reason") or "ttl_active",
            "run_count": int(previous.get("run_count") or 0),
            "deepseek_called": False,
        }
    )
    st.session_state["command_center_auto_refresh_status"] = status
    return status


def _run_command_center_auto_page_cycle(
    target="",
    market_type="",
    price_detail=None,
    position_profile=None,
    run_refresh=True,
    run_provider_probes=True,
    refresh_summary=None,
):
    price_detail = price_detail or _safe_get_command_center_price_detail(target, market_type)
    if run_refresh:
        refresh_summary = cc_service.run_refresh_sequence(
            COMMAND_CENTER_REFRESH_STEPS,
            lambda module_key, _label: _cc_run_refresh_step(
                module_key,
                target=target,
                market_type=market_type,
                price=(price_detail or {}).get("price"),
                position_profile=position_profile,
            ),
            refresh_level=cc_service.REFRESH_LEVEL_MANUAL_BASIC,
        )
        refresh_summary["mode"] = "auto_page_refresh"
        refresh_summary["summary"] = "页面自动刷新完成：已执行市场、量化、纪律、ETF、下一票基础链路；DeepSeek 未调用。"
        refresh_summary["deepseek_called"] = False
    else:
        refresh_summary = refresh_summary or st.session_state.get("command_center_refresh_summary") or {}
        refresh_summary.setdefault("mode", "auto_page_refresh")
        refresh_summary.setdefault("summary", "已读取当前刷新摘要并重新生成综合推演；DeepSeek 未调用。")
        refresh_summary["deepseek_called"] = False
    if run_provider_probes:
        akshare_probe = _cc_collect_auto_page_akshare_snapshot(target=target, market_type=market_type)
        refresh_summary.setdefault("results", []).append(akshare_probe["result"])
        if akshare_probe.get("error"):
            refresh_summary.setdefault("errors", []).append(akshare_probe["error"])
    else:
        akshare_probe = {
            "snapshot": st.session_state.get(f"akshare_money_flow_{target}_{market_type}") or {},
            "result": {},
            "error": None,
        }
    st.session_state["command_center_refresh_summary"] = refresh_summary

    analysis_packet = _run_command_center_analysis_chain(
        target=target,
        market_type=market_type,
        position_profile=position_profile,
        refresh_level=cc_service.REFRESH_LEVEL_MANUAL_BASIC,
    )
    live_packet = analysis_packet.get("live_packet") or {}
    strategy_packet = analysis_packet.get("strategy_packet") or {}
    decision_packet = analysis_packet.get("decision_packet") or {}
    home_snapshot = analysis_packet.get("home_snapshot") or st.session_state.get("command_center_home_snapshot") or {}
    data_capability_packet = _build_command_center_auto_capability_packet(
        target=target,
        market_type=market_type,
        price_detail=price_detail,
        home_snapshot=home_snapshot,
        akshare_snapshot=akshare_probe.get("snapshot") or {},
    )
    refresh_summary["data_capability_status_groups"] = data_capability_packet.get("status_groups") or {}
    refresh_summary["data_capability_summary"] = _cc_status_group_summary(data_capability_packet)
    st.session_state["command_center_refresh_summary"] = refresh_summary
    final_snapshot = _persist_home_action_snapshot(
        live_packet=live_packet,
        target=target,
        position_profile=position_profile,
        strategy_packet=strategy_packet,
        decision_packet=decision_packet,
        refresh_summary=refresh_summary,
    )
    evidence_radar_packet = evidence_summary_service.build_a_share_evidence_radar_view_model(final_snapshot)
    analysis_method_packet = _build_analysis_methods_display_packet(
        live_packet=live_packet,
        target=target,
        market_type=market_type,
        home_snapshot=final_snapshot,
    )
    projection_packet = projection_service.build_projection_packet(
        decision_packet=decision_packet,
        strategy_packet=strategy_packet,
        live_packet=live_packet,
        home_snapshot=final_snapshot,
        analysis_method_packet=analysis_method_packet,
        evidence_radar_packet=evidence_radar_packet,
        data_health_ledger=final_snapshot.get("data_health_ledger") if isinstance(final_snapshot, dict) else {},
        horizon_days=10,
    )
    st.session_state["command_center_evidence_radar_packet"] = evidence_radar_packet
    st.session_state["command_center_analysis_method_packet"] = analysis_method_packet
    st.session_state["command_center_projection_packet"] = projection_packet
    live_packet = cc_state_adapter.attach_command_center_child_packets_for_display(
        live_packet,
        strategy_execution_packet=strategy_packet,
        decision_packet=decision_packet,
    )
    live_packet = _sync_command_center_home_candidate_packets(live_packet)
    st.session_state["command_center_live_packet"] = live_packet
    errors = list(refresh_summary.get("errors") or [])
    errors.extend(str(item) for item in (analysis_packet.get("errors") or []) if item)
    if (price_detail or {}).get("price") is None and (price_detail or {}).get("warning"):
        errors.insert(0, f"行情读取失败：{(price_detail or {}).get('warning')}")
    summary = {
        "target": target,
        "generated_at": _cc_now(),
        "price_status": "available" if (price_detail or {}).get("price") is not None else "failed",
        "price": (price_detail or {}).get("price"),
        "price_source": (price_detail or {}).get("price_source") or "unknown",
        "price_data_date": (price_detail or {}).get("data_date") or "",
        "price_warning": (price_detail or {}).get("warning") or "",
        "strategy_action": strategy_packet.get("action") or strategy_packet.get("overall_action") or "等待",
        "decision_action": decision_packet.get("overall_action") or "等待",
        "projection_horizon_days": projection_packet.get("horizon_days") or 10,
        "deepseek_called": False,
        "deepseek_note": "页面自动刷新未调用 DeepSeek；解释入口仍需手动点击。",
        "errors": errors,
    }
    page_packet = {
        **analysis_packet,
        "live_packet": live_packet,
        "strategy_packet": strategy_packet,
        "decision_packet": decision_packet,
        "home_snapshot": final_snapshot,
        "evidence_radar_packet": evidence_radar_packet,
        "analysis_method_packet": analysis_method_packet,
        "projection_packet": projection_packet,
        "price_detail": price_detail,
        "position_profile": position_profile,
        "refresh_summary": refresh_summary,
        "data_capability_packet": data_capability_packet,
        "summary": summary,
        "deepseek_called": False,
    }
    st.session_state["command_center_auto_analysis_packet"] = page_packet
    return page_packet


def _apply_command_center_current_holding(
    target="",
    market_type="",
    currency="",
    position_status="",
    cost_price=0,
    holding_units=0,
    capital_plan=0,
    horizon="短中期",
    margin_ratio_pct=0,
    status=None,
):
    if status is not None:
        status.write("正在读取当前标的行情。")
    try:
        price_detail = get_current_price_detail(target, market_type)
    except Exception as exc:
        price_detail = {
            "ticker": target,
            "price": None,
            "price_source": "unavailable",
            "data_date": "",
            "raw_source": "",
            "warning": str(exc),
        }
    price = _num((price_detail or {}).get("price"))
    effective_position_status = position_status
    if _num(holding_units, 0) and str(position_status or "").startswith("未买入"):
        effective_position_status = "已持有 (持仓/找卖点)"
    position_profile = build_position_profile(
        target,
        price,
        cost_price,
        holding_units,
        capital_plan,
        effective_position_status,
        currency,
    )
    position_profile = _enrich_position_profile_for_command_center(
        position_profile,
        horizon=horizon,
        margin_ratio_pct=margin_ratio_pct,
    )
    position_profile["price_fetch_source"] = (price_detail or {}).get("price_source") or "unknown"
    position_profile["price_fetch_warning"] = (price_detail or {}).get("warning") or ""
    position_profile["price_data_date"] = (price_detail or {}).get("data_date") or ""
    st.session_state["position_profile"] = position_profile
    st.session_state["current_holding_context"] = position_profile
    st.session_state["current_stock_code"] = target
    st.session_state["command_center_direct_price_detail"] = price_detail
    st.session_state["command_center_direct_analysis_target"] = target
    st.session_state["command_center_direct_analysis_requested"] = True

    analysis_packet = _run_command_center_analysis_chain(
        target=target,
        market_type=market_type,
        position_profile=position_profile,
        refresh_level=cc_service.REFRESH_LEVEL_MANUAL_BASIC,
        status=status,
    )
    price_status = "available" if price is not None else "failed"
    warning = (price_detail or {}).get("warning") or ""
    summary = {
        "target": target,
        "generated_at": _cc_now(),
        "price_status": price_status,
        "price": price,
        "price_source": (price_detail or {}).get("price_source") or "unknown",
        "price_data_date": (price_detail or {}).get("data_date") or "",
        "price_warning": warning,
        "profit_state": position_profile.get("profit_state") or "未计算",
        "pnl_amount": position_profile.get("pnl_amount"),
        "pnl_pct": position_profile.get("pnl_pct"),
        "holding_units": position_profile.get("holding_units"),
        "cost_price": position_profile.get("cost_price"),
        "analysis_horizon": position_profile.get("analysis_horizon"),
        "margin_ratio_pct": position_profile.get("margin_ratio_pct"),
        "strategy_action": (analysis_packet.get("strategy_packet") or {}).get("action")
        or (analysis_packet.get("strategy_packet") or {}).get("overall_action")
        or "等待",
        "decision_action": (analysis_packet.get("decision_packet") or {}).get("overall_action") or "等待",
        "projection_horizon_days": (analysis_packet.get("projection_packet") or {}).get("horizon_days") or 10,
        "deepseek_called": False,
        "deepseek_note": "本轮未调用 DeepSeek；解释入口仍需手动点击。",
        "errors": analysis_packet.get("errors") or [],
    }
    if price is None and warning:
        summary["errors"] = [f"行情读取失败：{warning}", *summary["errors"]]
    packet = {
        **analysis_packet,
        "target": target,
        "price_detail": price_detail,
        "position_profile": position_profile,
        "summary": summary,
    }
    st.session_state["command_center_direct_analysis_packet"] = packet
    st.session_state["command_center_direct_analysis_summary"] = summary
    return packet


def _command_center_direct_packet_for_target(target=""):
    packet = st.session_state.get("command_center_direct_analysis_packet") or {}
    if isinstance(packet, dict) and str(packet.get("target") or "") == str(target or ""):
        return packet
    return {}


def _display_text(value, fallback="暂无"):
    if value is None or value == "":
        return fallback
    return str(value)


def _cc_display_ticker(value, fallback="未锁定"):
    text = home_snapshot_service.display_a_share_ticker(value)
    return text or fallback


def _cc_first_number(*values):
    for value in values:
        number = _num(value)
        if number is not None:
            return number
    return None


def _cc_percent_text(value, fallback="待计算"):
    number = _num(value)
    if number is None:
        return fallback
    if 0 < number <= 1:
        number *= 100
    return f"{number:.1f}%"


def _cc_home_refresh_state():
    refresh = st.session_state.get("command_center_refresh_summary") or {}
    if isinstance(refresh, dict) and refresh:
        errors = refresh.get("errors") or refresh.get("error_items") or []
        finished_at = refresh.get("finished_at") or refresh.get("generated_at") or refresh.get("updated_at")
        if errors:
            return "部分刷新", f"部分刷新：{len(errors)} 个模块未取到新数据；当前结论使用已刷新模块和上次成功缓存。"
        if finished_at:
            return "今日已刷新", "今日已刷新；当前结论基于本轮可用数据，缺口仍按缓存或待验证处理。"

    page_packet = st.session_state.get("command_center_auto_analysis_packet") or {}
    summary = page_packet.get("summary") if isinstance(page_packet, dict) else {}
    if isinstance(summary, dict) and summary:
        errors = summary.get("errors") or []
        if errors:
            return "部分刷新", f"部分刷新：{len(errors)} 个项目失败；当前结论会保留可用缓存，不把缺口写成确定信号。"
        if summary.get("generated_at"):
            if summary.get("price_status") == "available":
                return "使用缓存", "已读取当前持仓和轻量行情；重型扫描仍需手动触发。"
            return "使用缓存", "已读取本地缓存；当前价不可用时，交易结论按待验证处理。"

    live_packet = st.session_state.get("command_center_live_packet") or {}
    if isinstance(live_packet, dict) and (live_packet.get("updated_at") or live_packet.get("generated_at")):
        return "使用缓存", "已读取上次成功快照；刷新前不把缺口当作确定依据。"
    return "使用缓存", "当前以本地可用结果展示；需要新数据时点击满血数据刷新。"


def _cc_user_refresh_text(value, fallback=""):
    text = _home_trade_text(value, "")
    if not text:
        return fallback
    if "点击刷新今日基础数据" in text or "刷新今日基础数据" in text:
        return fallback or _cc_home_refresh_state()[1]
    return text


def _cc_user_source(value, fallback="缓存结果"):
    text = _display_text(value, fallback)
    lowered = text.lower()
    debug_terms = (
        "provider",
        "packet",
        "capability",
        "command_center",
        "tushare",
        "akshare",
        "yfinance",
        "supabase",
        "权限",
        "缓存路径",
    )
    if any(term in lowered for term in debug_terms):
        return fallback
    return text


_COMMAND_CENTER_HOME_DEBUG_TERMS = (
    "数据能力",
    "provider",
    "Provider",
    "packet",
    "Packet",
    "恢复入口",
    "根因",
    "权限",
    "缓存路径",
    "A股事实",
    "事实回流",
    "旧能力链",
    "旧能力",
    "缺失证据",
    "待手动",
    "接口未",
    "数据未刷新",
    "回流",
    "接口健康",
)


def _is_command_center_home_debug_text(value):
    text = str(value or "")
    return any(term in text for term in _COMMAND_CENTER_HOME_DEBUG_TERMS)


def _home_trade_text(value, fallback="待验证"):
    text = str(value or "").strip()
    if not text or len(text) > 140 or _is_command_center_home_debug_text(text):
        return fallback
    return text


def _home_trade_items(items, fallback_items=None, limit=4):
    cleaned = []
    for item in items or []:
        text = _home_trade_text(item, "")
        if text:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned or list(fallback_items or [])


def render_command_center_current_holding_panel(target="", market_badge="", price_detail=None, position_profile=None, direct_summary=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    detail = price_detail if isinstance(price_detail, dict) else {}
    summary = direct_summary if isinstance(direct_summary, dict) else {}
    currency = profile.get("currency") or ""
    price = profile.get("current_price")
    if price is None:
        price = detail.get("price")
    price_value = _num(price)
    holding_units = _num(profile.get("holding_units"), 0) or 0
    cost_price = _num(profile.get("cost_price"), 0) or 0
    market_value = round(price_value * holding_units, 2) if price_value is not None and holding_units else None
    cost_amount = round(cost_price * holding_units, 2) if cost_price and holding_units else None
    margin_ratio = _num(profile.get("margin_ratio_pct"), 0) or 0
    decision_packet = st.session_state.get("command_center_decision_packet") or {}
    strategy_packet = st.session_state.get("command_center_strategy_packet") or {}
    holding_action = _home_trade_text(
        decision_packet.get("position_mode")
        or strategy_packet.get("position_advice")
        or summary.get("strategy_action")
        or profile.get("normalized_position_state"),
        "等待确认",
    )
    next_step = _home_trade_text(
        summary.get("next_step")
        or decision_packet.get("summary")
        or strategy_packet.get("add_condition")
        or "先看今日总决策和风险警报；未满足条件前不追高、不加杠杆。",
        "先看今日总决策和风险警报；未满足条件前不追高、不加杠杆。",
    )
    cards = [
        ("标的", _cc_display_ticker(target or profile.get("ticker"))),
        ("持仓状态", profile.get("normalized_position_state") or profile.get("position_status") or "待确认"),
        ("市场", market_badge or "未知"),
        ("当前价", _fmt_price(price, currency)),
        ("持仓数量", _display_text(profile.get("holding_units"), "0")),
        ("持仓市值", _fmt_price(market_value, currency)),
        ("成本价", _fmt_price(profile.get("cost_price"), currency)),
        ("持仓成本", _fmt_price(cost_amount, currency)),
        ("浮动盈亏", profile.get("profit_state") or "未计算"),
        ("盈亏金额", _fmt_price(profile.get("pnl_amount"), currency)),
        ("融资比例", f"{margin_ratio:.1f}%"),
    ]
    card_html = "".join(
        (
            "<div class='cc-holding-info-card'>"
            f"<div class='cc-holding-info-label'>{html_escape(str(label))}</div>"
            f"<div class='cc-holding-info-value'>{html_escape(str(value))}</div>"
            "</div>"
        )
        for label, value in cards
    )
    with st.container(border=True):
        st.markdown(
            """
            <style>
            .cc-holding-info-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
                gap: 10px;
                margin: 8px 0 12px;
            }
            .cc-holding-info-card {
                border: 1px solid rgba(15, 23, 42, .10);
                border-radius: 8px;
                padding: 12px 14px;
                background: rgba(255, 255, 255, .76);
                min-width: 0;
            }
            .cc-holding-info-label {
                color: #64748b;
                font-size: 12px;
                font-weight: 700;
                line-height: 1.25;
                margin-bottom: 6px;
            }
            .cc-holding-info-value {
                color: #0f172a;
                font-size: 20px;
                font-weight: 760;
                line-height: 1.18;
                white-space: normal;
                overflow-wrap: anywhere;
            }
            .cc-holding-info-note {
                border: 1px solid rgba(20, 184, 166, .18);
                background: rgba(240, 253, 250, .56);
                border-radius: 8px;
                padding: 10px 12px;
                color: #0f172a;
                font-size: 13px;
                line-height: 1.55;
                margin-top: 8px;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### 当前持仓")
        st.markdown(f"<div class='cc-holding-info-grid'>{card_html}</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='cc-holding-info-note'>"
            f"当前持仓动作：{html_escape(str(holding_action))}<br>"
            f"下一步操作：{html_escape(str(next_step))}<br>"
            f"周期：{html_escape(str(profile.get('analysis_horizon') or '短中期'))} ｜ "
            f"行情状态：{'已读取' if price is not None else '未读取'}"
            f"{' ｜ 数据日期：' + html_escape(str(detail.get('data_date'))) if detail.get('data_date') else ''}"
            "</div>",
            unsafe_allow_html=True,
        )
        if profile.get("position_warning"):
            st.warning(profile["position_warning"])
        if summary.get("price_status") == "failed":
            st.warning(f"行情读取失败：{summary.get('price_warning') or '未返回可用价格'}")
        elif detail.get("warning"):
            st.caption(f"行情提示：{detail.get('warning')}")


def _command_center_position_context_text(position_profile=None, price_detail=None):
    profile = position_profile if isinstance(position_profile, dict) else {}
    detail = price_detail if isinstance(price_detail, dict) else {}
    currency = profile.get("currency") or ""
    price = profile.get("current_price")
    if price is None:
        price = detail.get("price")
    margin_ratio = _num(profile.get("margin_ratio_pct"), 0) or 0
    pieces = [
        f"标的 {_cc_display_ticker(profile.get('ticker'))}",
        f"状态 {profile.get('normalized_position_state') or profile.get('position_status') or '待确认'}",
        f"持仓 {_display_text(profile.get('holding_units'), '0')} 股",
        f"成本 {_fmt_price(profile.get('cost_price'), currency)}",
        f"当前价 {_fmt_price(price, currency)}",
        str(profile.get("profit_state") or "盈亏未计算"),
        f"盈亏 {_fmt_price(profile.get('pnl_amount'), currency)}",
        f"融资 {margin_ratio:.1f}%",
        f"周期 {profile.get('analysis_horizon') or '短中期'}",
    ]
    return " ｜ ".join(pieces)


def render_command_center_position_context_note(label, position_profile=None, price_detail=None):
    st.caption(f"{label}：{_command_center_position_context_text(position_profile, price_detail)}")


def _first_projection_path_text(projection_packet=None, path_name="", field="trigger", fallback="等待验证。"):
    packet = projection_packet if isinstance(projection_packet, dict) else {}
    for path in packet.get("paths") or []:
        if not isinstance(path, dict):
            continue
        name = str(path.get("name") or "")
        if path_name in name:
            return _home_trade_text(path.get(field) or path.get("condition"), fallback)
    return fallback


def render_command_center_decision_trade_panel(
    decision_packet=None,
    strategy_packet=None,
    position_profile=None,
    price_detail=None,
    projection_packet=None,
):
    decision = decision_packet if isinstance(decision_packet, dict) else {}
    strategy = strategy_packet if isinstance(strategy_packet, dict) else {}
    profile = position_profile if isinstance(position_profile, dict) else {}
    detail = price_detail if isinstance(price_detail, dict) else {}
    action = decision.get("overall_action") or "等待"
    position_mode = decision.get("position_mode") or (strategy.get("risk_budget") or {}).get("position_mode") or "待确认"
    margin_mode = decision.get("margin_mode") or "不使用融资"
    risk_level = decision.get("risk_level") or (strategy.get("risk_budget") or {}).get("risk_level") or "中"
    current_price = profile.get("current_price")
    if current_price is None:
        current_price = detail.get("price")
    cost_price = profile.get("cost_price")
    shares = _num(profile.get("holding_units"), 0) or 0
    margin_ratio = _num(profile.get("margin_ratio_pct"), 0) or 0
    pnl_text = profile.get("profit_state") or "盈亏未计算"
    refresh_label, refresh_impact = _cc_home_refresh_state()
    risk_breakdown = home_snapshot_service.build_risk_breakdown(
        decision,
        position_profile=profile,
        coverage=decision.get("data_coverage") if isinstance(decision.get("data_coverage"), dict) else {},
        price_detail=detail,
        errors=detail.get("errors") or [],
    )
    reason = _home_trade_text(
        decision.get("reason_summary") or strategy.get("summary"),
        "当前结论仍需价格、趋势和纪律条件确认。",
    )
    if shares <= 0:
        today_action = "空仓观察，不追高"
    elif any(key in str(action) for key in ["降风险", "减仓", "禁止", "卖"]):
        today_action = "先降风险，压低仓位"
    elif any(key in str(action) for key in ["进攻", "试探", "加仓", "买入"]):
        today_action = "只允许小幅试探"
    else:
        today_action = "持仓观察，不主动加仓"
    price_anchor = (
        f"现价 {_fmt_price(current_price, profile.get('currency') or '')} ｜ "
        f"成本 {_fmt_price(cost_price, profile.get('currency') or '')} ｜ "
        f"持仓 {_display_text(profile.get('holding_units'), '0')} 股 ｜ "
        f"{pnl_text}"
    )
    trigger_line = _home_trade_text(
        (decision.get("next_validation_conditions") or [None])[0]
        if isinstance(decision.get("next_validation_conditions"), list)
        else "",
        _first_projection_path_text(projection_packet, "乐观", "trigger", "放量站稳关键位，量化和纪律同向后再考虑。"),
    )
    trigger_line = _cc_user_refresh_text(trigger_line, refresh_impact)
    invalidation_line = _home_trade_text(
        (strategy.get("invalidation_condition") or strategy.get("invalid_condition") or "")
        if isinstance(strategy, dict)
        else "",
        _first_projection_path_text(projection_packet, "谨慎", "trigger", "跌破纪律线、公告/硬风险转弱或数据缺口扩大。"),
    )
    margin_line = (
        f"当前融资 {margin_ratio:.1f}%；融资比例存在压力，刷新数据前不建议新增融资。"
        if margin_ratio > 0
        else "当前未使用融资；不因单次推演主动加杠杆。"
    )
    next_button = f"{refresh_label}：{refresh_impact}"
    if projection_packet and (projection_packet or {}).get("deepseek_called"):
        next_button = "下一步：按三路径触发条件观察；若价格/公告变化，先刷新数据再重新增强。"
    validations = _home_trade_items(
        decision.get("next_validation_conditions") or [],
        fallback_items=[trigger_line, "仓位动作必须落在风险预算内。", "触发失效条件后重新生成结论。"],
        limit=3,
    )
    validations = [_cc_user_refresh_text(item, refresh_impact) for item in validations]
    must_not = _home_trade_items(
        decision.get("must_not_do") or [],
        fallback_items=["不追高", "不满仓", "不自动下单"],
        limit=4,
    )
    with st.container(border=True):
        st.markdown("### 今日总决策")
        st.markdown(
            f"""
            <div style="border:1px solid rgba(15,23,42,.10);border-radius:8px;padding:14px 16px;background:rgba(255,255,255,.78);margin:6px 0 12px;">
              <div style="font-size:12px;color:#64748b;font-weight:800;margin-bottom:6px;">今天怎么处理</div>
              <div style="font-size:26px;line-height:1.2;font-weight:850;color:#0f172a;">{html_escape(today_action)}</div>
              <div style="font-size:13px;color:#475569;line-height:1.55;margin-top:8px;">{html_escape(price_anchor)}</div>
              <div style="font-size:13px;color:#475569;line-height:1.55;margin-top:6px;">原因：{html_escape(reason)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cols = st.columns(4)
        cols[0].metric("总动作", action)
        cols[1].metric("当前持仓动作", position_mode)
        cols[2].metric("融资动作", margin_mode)
        cols[3].metric("账户整体风险", risk_breakdown.get("overall", {}).get("level") or risk_level)
        risk_cols = st.columns(4)
        for col, item in zip(risk_cols, risk_breakdown.get("items") or []):
            with col:
                st.metric(item.get("label") or "风险", item.get("level") or "待评估")
                st.caption(item.get("reason") or "暂无说明")
        if risk_breakdown.get("consistency_notice"):
            st.warning(risk_breakdown["consistency_notice"])
        t1, t2, t3 = st.columns(3)
        t1.markdown("**触发条件**")
        t1.write(trigger_line)
        t2.markdown("**失效条件**")
        t2.write(invalidation_line)
        t3.markdown("**融资处理**")
        t3.write(margin_line)
        st.info(next_button)
        risk_notes = home_snapshot_service.build_position_risk_notes(
            profile,
            total_risk_level=risk_level,
        )
        if risk_notes:
            st.warning(" ".join(risk_notes[:3]))
        left, right = st.columns(2)
        with left:
            st.markdown("**明日验证条件**")
            for item in validations:
                st.write(f"- {item}")
        with right:
            st.markdown("**禁止动作**")
            for item in must_not:
                st.write(f"- {item}")


def render_command_center_projection_trade_panel(projection_packet=None):
    packet = projection_packet if isinstance(projection_packet, dict) else {}
    paths = [item for item in (packet.get("paths") or []) if isinstance(item, dict)]
    horizon = packet.get("horizon_days") or 10
    with st.container(border=True):
        st.markdown("### 未来5~10日趋势推演")
        if not paths:
            st.info("趋势推演尚未生成；应用当前持仓或执行满血综合推演后显示路径。")
        else:
            cols = st.columns(min(3, len(paths)))
            for index, path in enumerate(paths[:3]):
                with cols[index % len(cols)]:
                    probability = path.get("probability")
                    probability_text = f"{round(float(probability) * 100)}%" if isinstance(probability, (int, float)) else _display_text(probability)
                    st.metric(path.get("name") or f"路径{index + 1}", probability_text)
                    st.write(_home_trade_text(path.get("action"), "按计划观察，不追高。"))
                    st.caption(f"触发：{_home_trade_text(path.get('trigger'), '等待价格、量能和纪律条件确认。')}")
                    st.caption(f"风险：{_home_trade_text(path.get('risk'), '若方向转弱，按风险预算降级。')}")
        st.caption(f"观察窗口：未来 {horizon} 日")


def render_command_center_strategy_trade_panel(strategy_packet=None):
    packet = strategy_packet if isinstance(strategy_packet, dict) else {}
    action = packet.get("action") or packet.get("overall_action") or "等待"
    risk_budget = packet.get("risk_budget") if isinstance(packet.get("risk_budget"), dict) else {}
    with st.container(border=True):
        st.markdown("### 策略执行实验室")
        cols = st.columns(4)
        cols[0].metric("策略动作", action)
        cols[1].metric("置信度", packet.get("confidence") or "低")
        cols[2].metric("风险预算", risk_budget.get("risk_level") or "待确认")
        cols[3].metric("可加金额", _display_text(risk_budget.get("max_add_amount")))
        st.write(_home_trade_text(packet.get("position_advice"), "等待策略执行建议补齐。"))
        st.write(f"加仓条件：{_home_trade_text(packet.get('add_condition'), '只有量价和纪律同向时才考虑小幅试探。')}")
        st.write(f"减仓条件：{_home_trade_text(packet.get('reduce_condition'), '跌破纪律线或风险扩大时优先降风险。')}")
        st.write(f"失效条件：{_home_trade_text(packet.get('invalidation_condition'), '市场转弱或验证信号反向时，本轮建议失效。')}")
        st.caption("策略只约束仓位和动作边界；不会自动交易。")


def render_command_center_next_ticket_top3(live_packet=None):
    section = _build_next_ticket_live_section(live_packet=live_packet)
    candidates = section.get("top_candidates") or []
    excluded_candidates = section.get("excluded_candidates") or []
    with st.container(border=True):
        st.markdown("### 下一票 Top3")
        if candidates:
            for index, item in enumerate(candidates[:3], start=1):
                ticker = _cc_display_ticker(item.get("ticker"), "未知")
                name = _display_text(item.get("name"), "")
                status_label = item.get("status_label") or item.get("action_state") or "只观察"
                score_text = item.get("score") if item.get("score") is not None else "暂无"
                st.markdown(f"**{index}. {ticker} {name}｜{status_label}｜评分 {score_text}**")
                st.write(f"触发条件：{_home_trade_text(item.get('trigger_condition'), '等待规则雷达触发条件确认。')}")
                st.write(f"失效条件：{_home_trade_text(item.get('invalidation_condition'), '市场转弱、评分下降或纪律信号反向时失效。')}")
                st.caption(
                    f"来源：{_cc_user_source(item.get('source'), '下一票雷达缓存')}｜"
                    f"更新时间：{_display_text(item.get('updated_at'), '暂无')}"
                )
        else:
            st.info(section.get("summary") or "暂无下一票缓存。可点击满血数据刷新，或进入高级工具箱运行下一票雷达。")
        if excluded_candidates:
            with st.expander("未纳入 / 排除原因", expanded=not candidates):
                for item in excluded_candidates[:5]:
                    ticker = _cc_display_ticker(item.get("ticker"), "未知")
                    name = _display_text(item.get("name"), "")
                    status_label = item.get("status_label") or item.get("action_state") or "暂不纳入"
                    score_text = item.get("score") if item.get("score") is not None else "暂无"
                    st.markdown(f"**{ticker} {name}｜{status_label}｜评分 {score_text}**")
                    st.write(_home_trade_text(item.get("reason"), "候选未达主路径展示标准。"))
                    st.caption(
                        f"来源：{_cc_user_source(item.get('source'), '下一票雷达缓存')}｜"
                        f"更新时间：{_display_text(item.get('updated_at'), '暂无')}"
                    )
        st.caption(f"状态：{section.get('status') or '待刷新'}｜更新时间：{section.get('updated_at') or '暂无'}")


def render_command_center_etf_config_panel(live_packet=None, position_profile=None):
    section = _build_margin_etf_live_section(live_packet=live_packet)
    profile = position_profile if isinstance(position_profile, dict) else {}
    current_margin = _num(profile.get("margin_ratio_pct"), _num(section.get("current_margin_ratio"), 0)) or 0
    recommended_margin = _num(section.get("recommended_margin_ratio"))
    recommended_cash = _num(section.get("recommended_cash_ratio"))
    margin_gap = round(current_margin - recommended_margin, 2) if recommended_margin is not None else None
    candidates = section.get("recommended_etfs") or []
    actionable_etfs = section.get("actionable_etfs") or []
    watch_etfs = section.get("watch_etfs") or []
    avoid_etfs = section.get("avoid_etfs") or []
    excluded_etfs = section.get("excluded_etfs") or []
    if not candidates and (actionable_etfs or watch_etfs):
        candidates = [*actionable_etfs, *watch_etfs][:3]
    allow_new_margin = bool(section.get("allow_new_margin", False))

    def _render_etf_item(item, *, compact=False):
        weight = _cc_first_number(
            item.get("recommended_ratio"),
            item.get("suggested_ratio"),
            item.get("target_ratio"),
            item.get("weight"),
        )
        amount = _cc_first_number(
            item.get("recommended_amount"),
            item.get("suggested_amount"),
            item.get("target_amount"),
            item.get("amount"),
        )
        total_asset = _cc_first_number(st.session_state.get("margin_total_asset"))
        if amount is None and weight is not None and total_asset is not None:
            amount = total_asset * (weight / 100 if weight > 1 else weight)
        ratio_text = _cc_percent_text(weight) if weight is not None else "待计算"
        amount_text = _fmt_price(amount, profile.get("currency") or "¥") if amount is not None else "待计算"
        status_label = item.get("status_label") or item.get("action_state") or "观察"
        st.markdown(
            f"**{item.get('name') or 'ETF'}｜{item.get('code') or '暂无代码'}｜{status_label}**"
        )
        st.write(f"主题：{item.get('bucket') or 'ETF'}｜建议比例：{ratio_text}｜建议金额：{amount_text}")
        if not compact:
            st.write(f"理由：{_home_trade_text(item.get('reason'), '等待 ETF 配置理由回填。')}")
            st.write(f"风险提示：{_home_trade_text(item.get('risk_note'), '复核流动性、溢价折价、同类重叠和追高风险。')}")
        st.caption(
            f"来源：{_cc_user_source(item.get('source'), '融资 ETF 配置缓存')}｜"
            f"更新时间：{_display_text(item.get('updated_at'), '暂无')}"
        )

    with st.container(border=True):
        st.markdown("### ETF 配置")
        cols = st.columns(5)
        cols[0].metric("当前融资比例", f"{current_margin:.1f}%")
        cols[1].metric("建议融资比例", f"{recommended_margin:.1f}%" if recommended_margin is not None else "暂无")
        cols[2].metric("融资差距", f"{margin_gap:+.1f}pct" if margin_gap is not None else "待刷新")
        cols[3].metric("建议现金比例", f"{recommended_cash:.1f}%" if recommended_cash is not None else "暂无")
        cols[4].metric("新增融资", "可小额" if allow_new_margin else "不建议")
        st.write(f"主方向：{section.get('today_main_direction') or '待 ETF 强弱表确认'}")
        margin_risk_notice = section.get("margin_risk_notice")
        if margin_risk_notice:
            if current_margin >= 20 or not allow_new_margin:
                st.warning(margin_risk_notice)
            else:
                st.info(margin_risk_notice)
        if margin_gap is not None and margin_gap > 0:
            st.warning(
                f"当前融资 {current_margin:.1f}% 高于建议 {recommended_margin:.1f}%，"
                "本轮优先降风险或维持观察，不新增融资。"
            )
        elif current_margin > 0 and recommended_margin is not None:
            st.info(f"当前融资 {current_margin:.1f}% 未高于建议上限；仍禁止临时加杠杆。")
        elif current_margin > 0:
            st.warning(f"当前输入融资 {current_margin:.1f}%，但 ETF 建议尚未刷新；先按谨慎风险预算处理。")
        if section.get("etf_replacement_hint"):
            st.write(section.get("etf_replacement_hint"))
        if section.get("leverage_guardrail"):
            st.caption(section.get("leverage_guardrail"))
        if candidates:
            st.markdown("**可配置 / 观察 ETF**")
            for item in candidates[:3]:
                _render_etf_item(item)
        else:
            st.info(section.get("summary") or "暂无 ETF 配置。可点击满血数据刷新，或进入高级工具箱的融资 ETF 工具。")
        if avoid_etfs:
            with st.expander("不追高 / 暂不配置 ETF", expanded=not candidates):
                for item in avoid_etfs[:5]:
                    _render_etf_item(item, compact=True)
                    st.write(f"原因：{_home_trade_text(item.get('reason'), '当前不进入主清单。')}")
        if excluded_etfs:
            with st.expander("排除 / 数据不足 ETF", expanded=False):
                for item in excluded_etfs[:5]:
                    _render_etf_item(item, compact=True)
                    st.write(f"原因：{_home_trade_text(item.get('reason'), '数据不足或无法评分，暂不纳入。')}")
        if section.get("watch_not_chase"):
            st.caption("不追高提示：" + "；".join(str(item) for item in (section.get("watch_not_chase") or [])[:2]))
        st.caption(f"状态：{section.get('status') or '待刷新'}｜更新时间：{section.get('updated_at') or '暂无'}")


def render_command_center_risk_alert_panel(
    live_packet=None,
    decision_packet=None,
    strategy_packet=None,
    projection_packet=None,
    price_detail=None,
    direct_summary=None,
    position_profile=None,
):
    alerts = []
    detail = price_detail if isinstance(price_detail, dict) else {}
    summary = direct_summary if isinstance(direct_summary, dict) else {}
    profile = position_profile if isinstance(position_profile, dict) else {}
    margin_section = (live_packet or {}).get("margin_etf") or {}
    current_margin = _num(profile.get("margin_ratio_pct"), 0) or 0
    recommended_margin = _num(margin_section.get("recommended_margin_ratio"))
    packet_errors = summary.get("errors") or []
    risk_breakdown = home_snapshot_service.build_risk_breakdown(
        decision_packet,
        position_profile=profile,
        price_detail=detail,
        errors=packet_errors,
        margin_etf_summary=margin_section,
    )
    alerts.extend(str(item) for item in packet_errors[:3] if item)
    hard_risk_packet = st.session_state.get("command_center_hard_risk_packet") or {}
    if isinstance(hard_risk_packet, dict) and hard_risk_packet:
        hard_items = [
            item
            for item in (hard_risk_packet.get("risk_items") or hard_risk_packet.get("announcement_items") or [])
            if isinstance(item, dict)
        ]
        if hard_items:
            for item in hard_items[:2]:
                message = (
                    item.get("message")
                    or item.get("title")
                    or item.get("summary")
                    or item.get("type")
                    or ""
                )
                if message:
                    alerts.append(f"公告/硬风险：{message}")
        elif hard_risk_packet.get("data_status") not in {"ready", "cached"}:
            alerts.append(
                f"公告/硬风险：{hard_risk_packet.get('status_label') or '待验证'}；"
                "缺口不能当作无风险。"
            )
    if detail.get("price") is None:
        alerts.append(f"当前价不可用：{detail.get('warning') or '行情接口未返回价格'}")
    if current_margin > 0 and recommended_margin is not None:
        gap = round(current_margin - recommended_margin, 2)
        if gap > 0:
            alerts.append(
                f"融资风险：当前融资 {current_margin:.1f}% 高于建议 {recommended_margin:.1f}%（差距 {gap:.1f}pct）；禁止新增融资，优先降风险或保现金。"
            )
        else:
            alerts.append(f"融资风险：当前融资 {current_margin:.1f}% 未高于建议 {recommended_margin:.1f}%；仍需避免临时加杠杆。")
    elif current_margin > 0:
        alerts.append(f"融资风险：当前输入融资 {current_margin:.1f}%，但建议融资比例待刷新；按高谨慎度处理。")
    risk_budget = (strategy_packet or {}).get("risk_budget") or {}
    alerts.extend(
        home_snapshot_service.build_position_risk_notes(
            profile,
            recommended_margin_ratio=recommended_margin,
            total_risk_level=risk_budget.get("risk_level") or (decision_packet or {}).get("risk_level"),
        )
    )
    if risk_breakdown.get("consistency_notice"):
        alerts.append(risk_breakdown["consistency_notice"])
    if risk_budget.get("risk_level"):
        alerts.append(f"策略风险预算：{risk_budget.get('risk_level')}；现金缓冲 {risk_budget.get('cash_buffer') if risk_budget.get('cash_buffer') is not None else '待计算'}")
    invalidation = (strategy_packet or {}).get("invalidation_condition")
    if invalidation:
        alerts.append(f"失效条件：{invalidation}")
    for condition in (decision_packet or {}).get("next_validation_conditions") or []:
        alerts.append(f"验证条件：{condition}")
    for path in (projection_packet or {}).get("paths") or []:
        if not isinstance(path, dict):
            continue
        risk_text = _home_trade_text(path.get("risk"), "")
        if risk_text:
            alerts.append(f"{path.get('name') or '趋势路径'}：{risk_text}")
            break
    if not alerts:
        alerts.append("暂无新增风险警报；仍需按纪律边界复核，不保证收益，不自动下单。")
    display_alerts = []
    for item in alerts:
        if item and item not in display_alerts:
            display_alerts.append(item)
    with st.container(border=True):
        st.markdown("### 风险警报")
        for item in display_alerts[:6]:
            st.write(f"- {item}")
        st.caption("本系统不保证收益，不自动下单。")


def render_command_center_live_cards(live_packet, target="", market_type="", price=None, position_profile=None):
    st.markdown("#### 真实摘要接入")
    cards = [
        ("市场环境", "market", "本轮自动刷新未取得市场环境。", "刷新市场环境"),
        ("量化推演", "quant", "本轮自动刷新未取得量化摘要。", "生成量化推演"),
        ("交易纪律", "discipline", "本轮自动刷新未取得交易纪律缓存。", "运行纪律校验"),
        ("下一票雷达", "next_ticket", "本轮自动刷新未取得下一票雷达缓存。", "运行下一票雷达"),
        ("融资 ETF", "margin_etf", "本轮自动刷新未取得 ETF 配置。", "刷新 ETF 配置"),
    ]
    section_builders = {
        "market": _build_market_live_section,
        "quant": _build_quant_live_section,
        "discipline": lambda: _build_discipline_live_section(target=target),
        "next_ticket": _build_next_ticket_live_section,
        "margin_etf": _build_margin_etf_live_section,
    }
    for row_start in range(0, len(cards), 2):
        cols = st.columns(2)
        for col, (title, key, empty_hint, button_label) in zip(cols, cards[row_start: row_start + 2]):
            section = live_packet.get(key) or {}
            with col:
                with st.container(border=True):
                    st.markdown(f"##### {title}")
                    module_summary = build_module_summary_view_model(section, module_name=title)
                    st.caption(f"数据状态：{module_summary.get('badge')}")
                    if st.button(f"单卡{button_label}", key=f"btn_cc_refresh_{key}", width="stretch"):
                        with st.spinner(f"正在{button_label}..."):
                            result = _cc_run_refresh_step(
                                key,
                                target=target,
                                market_type=market_type,
                                price=price,
                                position_profile=position_profile,
                            )
                        build_command_center_live_packet(target=target)
                        section = section_builders[key]()
                        if result.get("ok"):
                            st.success(f"{title}刷新完成。")
                        else:
                            st.warning(f"{title}刷新失败，已保留上次成功结果：{result.get('error') or '未知错误'}")
                        module_summary = build_module_summary_view_model(section, module_name=title)
                    st.caption(module_summary.get("caption"))
                    if module_summary.get("is_stale"):
                        st.caption(module_summary.get("reason"))
                    if module_summary.get("error_text"):
                        st.warning(f"上次刷新失败：{module_summary.get('error_text')}")
                    if key == "quant":
                        st.metric("评分 / 方向", section.get("score") if section.get("score") is not None else section.get("direction", "暂无"))
                    elif key == "discipline":
                        st.metric("动作边界", section.get("action_state") or "待刷新")
                        for item in (section.get("key_rules") or [])[:3]:
                            st.write(f"- {item}")
                    elif key == "next_ticket":
                        st.metric("动作状态", section.get("action_state") or "待刷新")
                        candidates = section.get("top_candidates") or []
                        if candidates:
                            for item in candidates[:3]:
                                st.write(
                                    f"- {item.get('ticker', '')} {item.get('name', '')}："
                                    f"{item.get('action_state', '只观察')} / {item.get('score', '暂无')}"
                                )
                        else:
                            st.write("- 暂无 Top 候选")
                    elif key == "margin_etf":
                        ratio_col1, ratio_col2 = st.columns(2)
                        ratio_col1.metric("建议融资比例", section.get("recommended_margin_ratio") if section.get("recommended_margin_ratio") is not None else "暂无")
                        ratio_col2.metric("建议现金比例", section.get("recommended_cash_ratio") if section.get("recommended_cash_ratio") is not None else "暂无")
                        st.write(f"今日 ETF 主方向：{section.get('today_main_direction') or '暂无'}")
                    st.write(section.get("summary") or module_summary.get("empty_text") or empty_hint)


def render_command_center_2_page(target, market_badge, price, market_type="", position_profile=None, price_detail=None):
    packet_key = "command_center_2_packet"
    explanation_key = "command_center_2_deepseek_explanation"
    explanation_at_key = "command_center_2_deepseek_generated_at"
    if packet_key not in st.session_state:
        st.session_state[packet_key] = get_command_center_mock_packet()

    st.markdown(
        """
        <style>
        .st-key-btn_cc_refresh_all_basic button,
        .st-key-btn_cc_full_data_refresh button,
        .st-key-btn_cc_full_war_game button,
        .st-key-btn_cc_moneyflow_capability_check button,
        .st-key-btn_cc_dragon_tiger_capability_check button,
        .st-key-btn_cc_margin_capability_check button,
        .st-key-btn_cc_limit_cpt_capability_check button,
        .st-key-btn_cc_chip_capability_check button,
        [class*="st-key-btn_cc_home_evidence_backfill_"] button,
        .st-key-btn_cc_deepseek_explain button,
        .st-key-btn_cc_deepseek_projection_overlay button {
            border-radius: 14px !important;
            border: 1px solid rgba(20, 184, 166, 0.24) !important;
            background: linear-gradient(135deg, rgba(14,165,233,0.10), rgba(20,184,166,0.12)) !important;
            color: #0f766e !important;
            box-shadow: 0 10px 28px rgba(15,23,42,0.06) !important;
        }
        .st-key-btn_cc_deepseek_explain button,
        .st-key-btn_cc_deepseek_projection_overlay button {
            background: linear-gradient(135deg, rgba(139,92,246,0.12), rgba(14,165,233,0.10)) !important;
            color: #6d28d9 !important;
            border-color: rgba(139, 92, 246, 0.20) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    render_command_center_shell()
    render_process_stepper(active_step=4)

    packet = st.session_state[packet_key]
    page_price_detail = price_detail or {
        "ticker": target,
        "price": price,
        "price_source": "input_context" if price is not None else "unavailable",
        "data_date": "",
        "warning": "" if price is not None else "行情暂不可用，页面继续展示可用缓存与失败原因。",
    }
    auto_refresh_status = _command_center_auto_refresh_guard(
        target=target,
        position_profile=position_profile,
        refresh_level=cc_service.REFRESH_LEVEL_MANUAL_BASIC,
    )
    page_packet = st.session_state.get("command_center_auto_analysis_packet") or {}
    live_packet = page_packet.get("live_packet") or st.session_state.get("command_center_live_packet") or build_command_center_live_packet(target=target)
    manual_full_refresh_clicked = False
    manual_war_game_clicked = False
    manual_deepseek_clicked = False
    control_cols = st.columns([1.1, 1.1])
    with control_cols[0]:
        if st.button("满血数据刷新", key="btn_cc_full_data_refresh", type="primary", width="stretch"):
            manual_full_refresh_clicked = True
            status = st.status("正在执行满血数据刷新...", expanded=True)
            refresh_summary, live_packet, data_capability_packet = _run_command_center_full_data_refresh(
                target=target,
                market_type=market_type,
                price=price,
                position_profile=position_profile,
                status=status,
            )
            refresh_status_view = build_refresh_summary_view_model(
                live_packet=live_packet,
                refresh_result=refresh_summary,
                refresh_level=cc_service.REFRESH_LEVEL_MANUAL_BASIC,
                generated_at=refresh_summary.get("finished_at"),
                a_share_fact_recovery_summary=_get_a_share_fact_recovery_summary_from_state(),
                latest_recovery_result_notice=_get_latest_recovery_result_notice_from_state(),
            )
            status.write("刷新结果已写入本轮作战包；诊断细节保留在高级工具箱。")
            fact_summary_text = refresh_status_view.get("a_share_fact_recovery_summary")
            if fact_summary_text:
                status.write("关键证据状态已更新；首页只保留交易结论。")
            errors = refresh_status_view.get("error_items") or refresh_status_view.get("errors") or []
            if errors:
                status.update(label=f"满血数据刷新完成，{len(errors)} 个模块/数据源失败", state="complete", expanded=False)
            else:
                status.update(label="满血数据刷新完成", state="complete", expanded=False)
            page_packet = _run_command_center_auto_page_cycle(
                target=target,
                market_type=market_type,
                price_detail=page_price_detail,
                position_profile=position_profile,
                run_refresh=False,
                run_provider_probes=False,
                refresh_summary=refresh_summary,
            )
            live_packet = page_packet.get("live_packet") or live_packet
            _mark_command_center_auto_refresh_guard(
                auto_refresh_status,
                reason="manual_full_data_refresh",
                forced=True,
            )
    with control_cols[1]:
        if st.button("满血综合推演", key="btn_cc_full_war_game", width="stretch"):
            manual_war_game_clicked = True
            status = st.status("正在执行满血综合推演...", expanded=True)
            summary, live_packet, decision_packet, strategy_packet, projection_packet = _run_command_center_full_war_game(
                target=target,
                market_type=market_type,
                position_profile=position_profile,
            )
            status.write("已读取本轮作战包；诊断细节保留在高级工具箱。")
            status.write(f"策略执行：{strategy_packet.get('overall_action') or strategy_packet.get('status') or '已生成'}")
            status.write(f"今日总决策：{decision_packet.get('overall_action') or '等待'}")
            status.write(f"趋势推演：未来 {summary.get('projection_horizon_days') or 10} 日")
            status.update(label="满血综合推演完成", state="complete", expanded=False)
            page_packet = _run_command_center_auto_page_cycle(
                target=target,
                market_type=market_type,
                price_detail=page_price_detail,
                position_profile=position_profile,
                run_refresh=False,
                run_provider_probes=False,
            )
            live_packet = page_packet.get("live_packet") or live_packet
    with st.expander("高级操作", expanded=False):
        st.caption("DeepSeek 只在这里手动触发；不会随刷新、切换页面或规则推演自动调用。")
        if st.button("DeepSeek 综合解释", key="btn_cc_deepseek_explain", width="stretch"):
            manual_deepseek_clicked = True
            status = st.status("正在调用 DeepSeek 生成解释...", expanded=True)
            current_packet = st.session_state.get("command_center_live_packet") or build_command_center_live_packet(target=target)
            current_packet = _attach_command_center_decision_packet(_attach_strategy_execution_packet(current_packet))
            current_packet["home_action_snapshot"] = st.session_state.get("command_center_home_snapshot") or _build_home_action_snapshot_display(
                live_packet=current_packet,
                target=target,
                position_profile=position_profile,
            )
            current_packet["refresh_level"] = cc_service.REFRESH_LEVEL_MANUAL_DEEP
            prompt = f"""
请基于以下综合推演中心 packet 输出一段克制解释。
要求：
1. 不得把未刷新模块、mock 或投喂资料观点写成事实。
2. 必须说明 DeepSeek 只辅助解释，不直接决定仓位。
3. 输出包含：综合结论、需要验证的信号、纪律边界、数据缺口。

当前标的：{target}
市场：{market_badge}
当前价：{price}
packet:
{json.dumps(current_packet, ensure_ascii=False, indent=2, default=str)}
"""
            result = call_deepseek_non_stream(
                prompt,
                system_role="你是克制的交易推演解释员，只解释缓存事实和待验证假设，不输出直接交易指令。",
                max_tokens=1600,
            )
            st.session_state[explanation_key] = result or ""
            st.session_state[explanation_at_key] = datetime.datetime.now().isoformat(timespec="seconds")
            st.session_state["command_center_deepseek_refresh_level"] = cc_service.REFRESH_LEVEL_MANUAL_DEEP
            status.update(label="DeepSeek 解释已写入 session_state", state="complete")

    suppress_auto_refresh = manual_full_refresh_clicked or manual_war_game_clicked or manual_deepseek_clicked
    if not suppress_auto_refresh:
        if auto_refresh_status.get("should_refresh"):
            page_packet = _run_command_center_auto_page_cycle(
                target=target,
                market_type=market_type,
                price_detail=page_price_detail,
                position_profile=position_profile,
            )
            live_packet = page_packet.get("live_packet") or build_command_center_live_packet(target=target)
            _mark_command_center_auto_refresh_guard(auto_refresh_status, reason=auto_refresh_status.get("reason") or "auto_refresh")
        else:
            _mark_command_center_auto_refresh_skipped(auto_refresh_status)
            if not page_packet:
                page_packet = _run_command_center_auto_page_cycle(
                    target=target,
                    market_type=market_type,
                    price_detail=page_price_detail,
                    position_profile=position_profile,
                    run_refresh=False,
                    run_provider_probes=False,
                )
                live_packet = page_packet.get("live_packet") or live_packet

    active_packet = page_packet
    live_packet = active_packet.get("live_packet") or live_packet or build_command_center_live_packet(target=target)
    first_diagnosis_prewarm_packet = _run_command_center_first_diagnosis_prewarm(
        target=target,
        market_type=market_type,
        position_profile=position_profile,
        live_packet=live_packet,
    )
    strategy_packet = active_packet.get("strategy_packet")
    strategy_packet = strategy_packet or _get_strategy_execution_display_packet()
    decision_packet = active_packet.get("decision_packet")
    decision_packet = decision_packet or _get_command_center_decision_display_packet()
    home_snapshot = active_packet.get("home_snapshot")
    home_snapshot = home_snapshot or _build_home_action_snapshot_display(
        live_packet=live_packet,
        target=target,
        position_profile=position_profile,
    )
    evidence_radar_vm = active_packet.get("evidence_radar_packet")
    evidence_radar_vm = evidence_radar_vm or evidence_summary_service.build_a_share_evidence_radar_view_model(home_snapshot)
    st.session_state["command_center_evidence_radar_packet"] = evidence_radar_vm
    analysis_method_packet = active_packet.get("analysis_method_packet")
    analysis_method_packet = analysis_method_packet or _build_analysis_methods_display_packet(
        live_packet=live_packet,
        target=target,
        market_type=market_type,
        home_snapshot=home_snapshot,
    )
    st.session_state["command_center_analysis_method_packet"] = analysis_method_packet
    projection_packet = active_packet.get("projection_packet")
    projection_packet = projection_packet or projection_service.build_projection_packet(
        decision_packet=decision_packet,
        strategy_packet=strategy_packet,
        live_packet=live_packet,
        home_snapshot=home_snapshot,
        analysis_method_packet=analysis_method_packet,
        evidence_radar_packet=evidence_radar_vm,
        data_health_ledger=home_snapshot.get("data_health_ledger") if isinstance(home_snapshot, dict) else {},
        horizon_days=10,
    )
    st.session_state["command_center_projection_packet"] = projection_packet
    live_packet = cc_state_adapter.attach_command_center_child_packets_for_display(
        live_packet,
        strategy_execution_packet=strategy_packet,
        decision_packet=decision_packet,
    )
    st.session_state["command_center_live_packet"] = live_packet

    direct_summary = active_packet.get("summary") or {}
    deepseek_called_count = st.session_state.token_usage.get("deepseek_calls", 0)
    deepseek_token_count = st.session_state.token_usage.get("estimated_tokens", 0)
    deepseek_status = (
        "已解释"
        if st.session_state.get(explanation_at_key) or st.session_state.get("command_center_deepseek_projection_generated_at")
        else "未调用"
    )
    st.caption(
        f"DeepSeek：{deepseek_status} ｜ 调用次数：{deepseek_called_count} ｜ Token：{deepseek_token_count:,}"
    )
    if isinstance(first_diagnosis_prewarm_packet, dict) and first_diagnosis_prewarm_packet.get("summary"):
        with st.expander("高级诊断状态", expanded=False):
            st.caption(
                f"首诊预热：{first_diagnosis_prewarm_packet.get('summary')}｜"
                f"更新时间：{first_diagnosis_prewarm_packet.get('updated_at') or '暂无'}"
            )

    render_command_center_current_holding_panel(
        target=target,
        market_badge=market_badge,
        price_detail=page_price_detail,
        position_profile=position_profile,
        direct_summary=direct_summary,
    )
    render_command_center_decision_trade_panel(
        decision_packet=decision_packet,
        strategy_packet=strategy_packet,
        position_profile=position_profile,
        price_detail=page_price_detail,
        projection_packet=projection_packet,
    )
    st.markdown("### 未来 5~10 日趋势推演")
    with st.expander("高级趋势增强", expanded=False):
        st.caption("仅在需要大模型整理三路径时手动触发；普通刷新和规则推演不会调用。")
        if st.button(
            "DeepSeek 增强趋势推演",
            key="btn_cc_deepseek_projection_overlay",
            help="手动调用 DeepSeek，把当前量化推演、交易纪律、持仓和风险证据整理成三路径曲线；不会自动下单，也不会在普通刷新或切换页面时触发。",
            width="stretch",
        ):
            status = st.status("正在手动增强趋势推演...", expanded=True)
            status.write("先刷新当前标的作战上下文；DeepSeek 暂未调用。")
            preflight_packet = _run_command_center_auto_page_cycle(
                target=target,
                market_type=market_type,
                price_detail=page_price_detail,
                position_profile=position_profile,
                run_refresh=True,
                run_provider_probes=True,
            )
            live_packet = preflight_packet.get("live_packet") or live_packet
            decision_packet = preflight_packet.get("decision_packet") or decision_packet
            strategy_packet = preflight_packet.get("strategy_packet") or strategy_packet
            projection_packet = preflight_packet.get("projection_packet") or projection_packet
            home_snapshot = preflight_packet.get("home_snapshot") or home_snapshot
            page_price_detail = preflight_packet.get("price_detail") or page_price_detail
            preflight_errors = preflight_packet.get("errors") or []
            status.write("已重算策略执行、今日总决策和规则趋势；现在调用 DeepSeek 整理三路径。")
            if preflight_errors:
                status.write(f"刷新上下文有 {len(preflight_errors)} 个失败项；将继续使用可用缓存和失败原因。")
            enhanced_projection, parsed_overlay, raw_overlay = _run_command_center_deepseek_projection_overlay(
                target=target,
                market_type=market_type,
                position_profile=position_profile,
                live_packet=live_packet,
                decision_packet=decision_packet,
                strategy_packet=strategy_packet,
                projection_packet=projection_packet,
                home_snapshot=home_snapshot,
            )
            if parsed_overlay:
                projection_packet = enhanced_projection
                status.write("DeepSeek 已返回结构化三路径；曲线、概率、触发条件和风险提示已合并。")
                status.update(label="趋势推演已手动增强", state="complete", expanded=False)
            else:
                status.write("DeepSeek 未返回可解析 JSON；页面保留原规则趋势推演。")
                if raw_overlay:
                    with st.expander("查看 DeepSeek 原始返回", expanded=False):
                        st.write(raw_overlay)
                status.update(label="趋势增强未合并，已保留原曲线", state="error", expanded=False)
    render_command_center_projection_chart(projection_packet, home_compact=True)
    st.markdown("### 策略执行实验室")
    live_packet = render_strategy_execution_card(
        live_packet,
        target=target,
        position_profile=position_profile,
        analysis_method_packet=analysis_method_packet,
        evidence_radar_packet=evidence_radar_vm,
        projection_packet=projection_packet,
        show_generate_button=False,
        home_compact=True,
    )
    render_command_center_next_ticket_top3(live_packet)
    render_command_center_etf_config_panel(live_packet, position_profile=position_profile)
    render_command_center_risk_alert_panel(
        live_packet=live_packet,
        decision_packet=decision_packet,
        strategy_packet=strategy_packet,
        projection_packet=projection_packet,
        price_detail=page_price_detail,
        direct_summary=direct_summary,
        position_profile=position_profile,
    )
    render_home_analysis_methods_strip(
        analysis_methods_service.build_home_analysis_method_summary(analysis_method_packet)
    )

    explanation = st.session_state.get(explanation_key)
    if explanation:
        with st.expander("DeepSeek 手动解释缓存", expanded=False):
            st.caption(f"生成时间：{st.session_state.get(explanation_at_key) or '暂无'}")
            st.markdown(explanation)
    render_command_center_shell_end()
    return

    home_evidence_recovery_slot = st.empty()

    render_a_share_data_capability_controls(
        target=target,
        position_profile=position_profile,
        live_packet=live_packet,
    )

    live_packet = live_packet or run_command_center_auto_light_snapshot(target=target)
    command_center_view_model = build_command_center_view_model(live_packet)
    refresh_summary = st.session_state.get("command_center_refresh_summary") or {}
    refresh_summary_view = command_center_view_model.get("refresh_summary") or {}
    overview_vm = build_command_center_overview_view_model(
        live_packet=command_center_view_model.get("live_packet") or live_packet,
        refresh_summary=refresh_summary,
        decision_packet=_get_command_center_decision_display_packet(),
        strategy_packet=_get_strategy_execution_display_packet(),
        deepseek_summary=st.session_state.get(explanation_key),
        data_capability_packet=_get_command_center_data_capability_packet(),
    )
    if refresh_summary:
        summary_payload = refresh_summary_view.get("summary") or {}
        error_items = refresh_summary_view.get("error_items") or []
        errors = refresh_summary_view.get("errors") or []
        ok_modules = (
            refresh_summary_view.get("completed_modules")
            or summary_payload.get("completed_modules")
            or []
        )
        st.caption(
            f"最近一次基础数据刷新：{refresh_summary_view.get('generated_at') or '暂无'} ｜ "
            f"已完成：{'、'.join(ok_modules) if ok_modules else '无'} ｜ "
            f"失败：{len(error_items) if error_items else len(errors)} ｜ "
            f"A股事实：{refresh_summary_view.get('a_share_fact_recovery_summary') or '待验证'} ｜ "
            "DeepSeek：未调用"
        )
        if error_items or errors:
            with st.expander("刷新失败明细", expanded=False):
                if error_items:
                    for item in error_items:
                        st.write(f"- {item.get('module') or '未知模块'}: {item.get('message') or '未知错误'}")
                else:
                    for item in errors:
                        st.write(f"- {item}")
        latest_recovery_result = refresh_summary_view.get("latest_recovery_result_notice") or {}
        if latest_recovery_result:
            st.caption(
                f"最近恢复：{latest_recovery_result.get('title') or '恢复结果'} ｜ "
                f"{latest_recovery_result.get('message') or '已更新本地恢复状态。'} ｜ "
                f"{latest_recovery_result.get('next_action') or '返回综合推演中心查看快照。'}"
            )
        a_share_fact_recovery = refresh_summary_view.get("a_share_fact_recovery") or {}
        a_share_fact_items = a_share_fact_recovery.get("items") or []
        if a_share_fact_recovery.get("summary") and (
            refresh_summary_view.get("has_a_share_fact_blockers")
            or refresh_summary_view.get("has_a_share_fact_waiting")
        ):
            with st.expander("A股事实回流状态", expanded=False):
                st.write(a_share_fact_recovery.get("next_action") or "继续按数据恢复中心手动补齐。")
                for item in a_share_fact_items[:5]:
                    st.write(
                        f"- {item.get('label') or 'A股事实'}："
                        f"{item.get('packet_status_text') or item.get('status_label') or '待验证'}；"
                        f"{item.get('diagnostic_answer') or item.get('next_action') or '需要复核来源、日期和权限。'}"
                    )
                nav_items = [
                    item
                    for item in a_share_fact_items[:5]
                    if item.get("recovery_state") != "recovered"
                    and home_snapshot_service.build_tool_recovery_navigation_state(item)
                ]
                if nav_items:
                    st.caption("恢复入口只切换到高级工具箱，不会自动运行 Tushare、DeepSeek、回测或全市场扫描。")
                    nav_cols = st.columns(min(3, len(nav_items)))
                    for index, item in enumerate(nav_items):
                        with nav_cols[index % len(nav_cols)]:
                            if st.button(
                                f"进入恢复：{item.get('label') or 'A股事实'}",
                                key=f"btn_cc_refresh_fact_recovery_{item.get('key') or index}",
                                help=item.get("navigation_label") or "切换到对应高级工具模块；不自动执行接口请求。",
                                width="stretch",
                            ):
                                _apply_tool_recovery_navigation_state(item)
                                st.rerun()

    live_packet = command_center_view_model["live_packet"]
    live_errors = overview_vm.get("error_items") or []
    if live_errors:
        st.warning(f"基础数据有 {len(live_errors)} 个模块刷新失败，当前继续展示可用缓存和上次成功结果。")
        with st.expander("当前错误状态", expanded=False):
            for item in live_errors:
                st.write(
                    f"- {item.get('module') or '未知模块'}："
                    f"{item.get('message') or '未知错误'}｜"
                    f"{item.get('updated_at') or '暂无时间'}｜"
                    f"{item.get('source') or '未加载'}"
                )
    st.caption(
        f"DeepSeek 调用次数：{st.session_state.token_usage.get('deepseek_calls', 0)} ｜ "
        f"估算 Token：{st.session_state.token_usage.get('estimated_tokens', 0):,} ｜ "
        f"解释生成：{st.session_state.get(explanation_at_key) or '未生成'} ｜ "
        f"{overview_vm.get('deepseek_text') or 'DeepSeek：未调用'} ｜ "
        "页面加载会自动刷新可用基础链路；DeepSeek 仍只手动调用。"
    )
    capability_items = overview_vm.get("data_capability_items") or []
    st.caption(f"数据能力状态：{overview_vm.get('data_capability_summary_text')}")
    if capability_items:
        with st.expander("数据能力明细", expanded=False):
            capability_df = pd.DataFrame(capability_items)
            capability_columns = [
                "label",
                "api",
                "status",
                "governance_status",
                "governance_label",
                "state",
                "latest_date",
                "updated_at",
                "action_hint",
                "error",
            ]
            capability_columns = [column for column in capability_columns if column in capability_df.columns]
            st.dataframe(capability_df[capability_columns], width="stretch", hide_index=True)
    home_snapshot = _build_home_action_snapshot_display(
        live_packet=live_packet,
        target=target,
        position_profile=position_profile,
    )
    render_home_a_share_diagnostic_recovery_controls(
        home_snapshot,
        target=target,
        market_type=market_type,
        position_profile=position_profile,
        live_packet=live_packet,
    )
    evidence_radar_vm = evidence_summary_service.build_a_share_evidence_radar_view_model(home_snapshot)
    st.session_state["command_center_evidence_radar_packet"] = evidence_radar_vm
    with home_evidence_recovery_slot.container():
        render_home_evidence_backfill_controls(
            evidence_radar_vm,
            target=target,
            market_type=market_type,
            position_profile=position_profile,
            live_packet=live_packet,
        )
    st.caption("本系统不自动交易，不保证收益；DeepSeek 只解释当前结构化结果。路径：刷新今日基础数据 → 生成策略执行建议 → 查看今日总决策 → 可选 DeepSeek 综合解释。")
    analysis_method_packet = _build_analysis_methods_display_packet(
        live_packet=live_packet,
        target=target,
        market_type=market_type,
        home_snapshot=home_snapshot,
    )
    st.session_state["command_center_analysis_method_packet"] = analysis_method_packet
    projection_packet = projection_service.build_projection_packet(
        decision_packet=_get_command_center_decision_display_packet(),
        strategy_packet=_get_strategy_execution_display_packet(),
        live_packet=live_packet,
        home_snapshot=home_snapshot,
        analysis_method_packet=analysis_method_packet,
        evidence_radar_packet=evidence_radar_vm,
        data_health_ledger=home_snapshot.get("data_health_ledger") if isinstance(home_snapshot, dict) else {},
        horizon_days=10,
    )
    st.session_state["command_center_projection_packet"] = projection_packet
    home_snapshot = home_snapshot_service.attach_decision_loop_status(
        home_snapshot,
        analysis_method_packet=analysis_method_packet,
        projection_packet=projection_packet,
        strategy_packet=_get_strategy_execution_display_packet(),
        decision_packet=_get_command_center_decision_display_packet(),
        deepseek_summary=st.session_state.get(explanation_key),
    )
    st.session_state["command_center_home_snapshot"] = home_snapshot
    with home_snapshot_slot.container():
        render_home_action_snapshot(home_snapshot)
    with decision_hero_slot.container():
        live_packet = render_command_center_decision_card(
            live_packet,
            target=target,
            position_profile=position_profile,
            analysis_method_packet=analysis_method_packet,
            projection_packet=projection_packet,
        )
    with projection_slot.container():
        render_command_center_projection_chart(projection_packet)
    render_analysis_methods_card(analysis_method_packet)
    readiness_state = dict(st.session_state)
    readiness_state.update(
        {
            "command_center_home_snapshot": home_snapshot,
            "command_center_live_packet": live_packet,
            "command_center_evidence_radar_packet": evidence_radar_vm,
            "command_center_analysis_method_packet": analysis_method_packet,
            "command_center_projection_packet": projection_packet,
            "strategy_execution_packet": _get_strategy_execution_display_packet(),
            "command_center_decision_packet": _get_command_center_decision_display_packet(),
        }
    )
    render_command_center_packet_registry_card(
        packet_registry_service.build_packet_registry_view_model(),
        readiness_view_model=desktop_readiness_service.build_desktop_frontend_readiness_view_model(readiness_state),
    )
    live_packet = render_strategy_execution_card(
        live_packet,
        target=target,
        position_profile=position_profile,
        analysis_method_packet=analysis_method_packet,
        evidence_radar_packet=evidence_radar_vm,
        projection_packet=projection_packet,
    )
    render_command_center_live_cards(
        live_packet,
        target=target,
        market_type=market_type,
        price=price,
        position_profile=position_profile,
    )
    live_packet = build_command_center_live_packet(target=target)
    live_packet = _attach_strategy_execution_packet(live_packet)
    live_packet = _attach_command_center_decision_packet(live_packet)
    command_center_view_model = build_command_center_view_model(live_packet)
    live_packet = command_center_view_model["live_packet"]
    display_packet = build_command_center_display_packet(live_packet, fallback_packet=packet)
    packet = display_packet
    render_command_center_account_budget_card(packet)
    render_fusion_summary_card(packet)
    render_discipline_validation_grid(packet)
    render_observation_pool_card(packet)
    render_signal_confluence_card(packet.get("signal_confluence"))

    st.markdown("#### DeepSeek 深度解释缓存")
    explanation = st.session_state.get(explanation_key)
    if explanation:
        st.caption(f"生成时间：{st.session_state.get(explanation_at_key) or '暂无'}")
        st.markdown(explanation)
    else:
        st.info("当前无 DeepSeek 解释缓存，点击按钮后生成；解释只辅助，不直接决定仓位。")

    render_command_center_shell_end()


COMMAND_CENTER_NAV_ITEMS = [
    "综合推演中心 2.0",
    "高级工具箱入口",
]


def render_command_center_toolbox_entry():
    packet = toolbox_summary_service.build_advanced_toolbox_entry(
        data_capability_packet=_get_command_center_data_capability_packet(),
    )
    item_html = ""
    detail_rows = []
    for item in packet.get("items") or []:
        capability = item.get("capability_summary") or {}
        status = item.get("capability_status") or {}
        dependencies = "、".join(capability.get("depends_on") or item.get("data_dependencies") or [])
        missing_reasons = "；".join(capability.get("why_missing") or item.get("common_missing_reasons") or [])
        matched_items = "；".join(
            f"{row.get('label') or row.get('api') or '数据能力'}：{row.get('status_label') or row.get('state') or '待验证'}"
            for row in (status.get("matched_items") or [])[:3]
        )
        issue_explainer = status.get("issue_explainer") or {}
        root_causes = "；".join(
            f"{row.get('label') or '原因'}：{row.get('detail') or row.get('next_action') or '待验证'}"
            for row in (issue_explainer.get("root_cause_items") or [])[:2]
            if isinstance(row, dict)
        )
        issue_next_actions = "；".join(
            str(action)
            for action in (issue_explainer.get("next_actions") or [])[:2]
            if str(action).strip()
        )
        item_html += f"""
        <div class="cc-mini-card">
          <div class="cc-mini-title">{html_escape(str(item.get("label") or "高级工具"))}</div>
          <div class="cc-mini-value">{html_escape(str(status.get("status_label") or "待检测"))}</div>
          <div class="cc-mini-desc">{html_escape(str(status.get("summary") or "尚未读取到匹配的数据能力检测结果。"))}</div>
          <div class="cc-mini-desc">{html_escape(str(item.get("purpose") or "旧版工具保留。"))}</div>
        </div>
        """
        detail_rows.append(
            {
                "模块": item.get("label"),
                "状态": status.get("status_label"),
                "匹配状态": matched_items or "暂无本地检测结果",
                "根因": root_causes or issue_explainer.get("short_answer") or "",
                "建议": issue_next_actions or status.get("next_action") or item.get("gate"),
                "依赖数据": dependencies,
                "为什么可能没数据": missing_reasons,
                "安全空态": capability.get("safe_empty_state"),
                "回流": item.get("packet"),
                "触发方式": item.get("gate"),
            }
        )
    st.markdown(
        f"""
        <section class="cc-card">
          <div class="cc-card-title">{html_escape(str(packet.get("title") or "高级工具箱"))}</div>
          <div class="cc-card-caption">{html_escape(str(packet.get("summary") or "旧版工作台保留为高级工具。"))}</div>
          <div class="cc-mini-grid">{item_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("查看高级工具诊断详情", expanded=False):
        st.caption(packet.get("data_gap_note") or "数据能力待检测。")
        st.caption(packet.get("manual_note") or "高级工具只在按钮触发时运行。")
        st.caption(packet.get("next_step") or "")
        if detail_rows:
            st.dataframe(pd.DataFrame(detail_rows), width="stretch", hide_index=True)
    st.info("需要进入旧版完整页面时，请使用页面顶部的“高级工具箱（旧版保留）”切换；这里不会自动运行旧版模块。")


def render_command_center_placeholder(nav_name, message=None):
    st.markdown(
        f"""
        <section class="cc-card">
          <div class="cc-card-title">{nav_name}</div>
          <div class="cc-card-caption">高级工具入口 / 暂未接入综合中心；页面切换只更新 session_state，不触发 DeepSeek、Tushare 批量请求或旧版重型 tabs。</div>
          <div class="cc-mini-card">
            <div class="cc-mini-title">当前状态</div>
            <div class="cc-mini-value">暂未接入</div>
            <div class="cc-mini-desc">{message or '需要深度工具时进入高级工具箱；当前首页已提供总动作、持仓、候选、ETF 和趋势推演。'}</div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_command_center_workspace(target, market_badge, price, market_type="", position_profile=None, price_detail=None):
    if "command_center_nav" not in st.session_state:
        st.session_state["command_center_nav"] = "综合推演中心 2.0"
    if st.session_state["command_center_nav"] not in COMMAND_CENTER_NAV_ITEMS:
        st.session_state["command_center_nav"] = "综合推演中心 2.0"

    st.markdown(
        """
        <style>
        div[data-testid="stRadio"] [role="radiogroup"] {
            gap: 4px;
        }
        div[data-testid="stRadio"] label {
            border-radius: 14px;
            padding: 7px 10px;
            border: 1px solid transparent;
        }
        div[data-testid="stRadio"] label:has(input:checked) {
            background: rgba(20, 184, 166, 0.10);
            border-color: rgba(20, 184, 166, 0.18);
            color: #0f766e;
            font-weight: 750;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    nav_col, content_col = st.columns([0.22, 0.78], gap="large")
    with nav_col:
        st.markdown(
            """
            <div class="cc-sidebar">
              <div class="cc-logo">
                <div class="cc-logo-mark">M</div>
                <div>stock-MING<br><span style="color:#64748b;font-size:11px;font-weight:700;">Command Center</span></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.radio(
            "主导航",
            COMMAND_CENTER_NAV_ITEMS,
            key="command_center_nav",
            label_visibility="collapsed",
        )

    selected_nav = st.session_state.get("command_center_nav", "综合推演中心 2.0")
    with content_col:
        if selected_nav == "综合推演中心 2.0":
            render_command_center_2_page(
                target=target,
                market_badge=market_badge,
                price=price,
                market_type=market_type,
                position_profile=position_profile,
                price_detail=price_detail,
            )
        elif selected_nav == "高级工具箱入口":
            render_command_center_shell(active_nav=selected_nav)
            st.markdown("### 数据能力诊断")
            toolbox_live_packet = st.session_state.get("command_center_live_packet") or build_command_center_live_packet(target=target)
            render_a_share_data_capability_controls(
                target=target,
                position_profile=position_profile,
                live_packet=toolbox_live_packet,
                key_prefix="toolbox",
            )
            render_command_center_toolbox_entry()
            data_capability_packet = _get_command_center_data_capability_packet()
            capability_items = data_capability_packet.get("items") if isinstance(data_capability_packet, dict) else []
            if capability_items:
                capability_df = pd.DataFrame(capability_items)
                capability_columns = [
                    "label",
                    "api",
                    "status",
                    "state",
                    "latest_date",
                    "updated_at",
                    "action_hint",
                    "error",
                ]
                capability_columns = [column for column in capability_columns if column in capability_df.columns]
                with st.expander("数据源 capability 明细", expanded=False):
                    st.dataframe(capability_df[capability_columns], width="stretch", hide_index=True)
            render_command_center_packet_registry_card(
                packet_registry_service.build_packet_registry_view_model(),
                readiness_view_model=desktop_readiness_service.build_desktop_frontend_readiness_view_model(dict(st.session_state)),
            )
        else:
            render_command_center_shell(active_nav=selected_nav)
            render_command_center_placeholder(selected_nav)


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

    ANNOUNCEMENT_WATCHLIST_TICKER = "__ANNOUNCEMENT_WATCHLIST__"
    ANNOUNCEMENT_WATCHLIST_REPORT_TYPE = "announcement_watchlist"
    NEWS_DIGEST_REPORT_TYPE = "news_digest"

    @st.cache_data(ttl=300, show_spinner=False)
    def run_data_source_healthcheck(sample_ts_code="000001.SZ", include_deepseek_ping=False, cache_version="healthcheck_v1", _supabase_client=None, _deepseek_keys=None):
        checked_at = datetime.datetime.now().isoformat(timespec="seconds")
        sample_ts_code = str(sample_ts_code or "000001.SZ").strip().upper() or "000001.SZ"
        today = datetime.date.today()
        start_10 = today - datetime.timedelta(days=10)
        start_30 = today - datetime.timedelta(days=30)
        start_90 = today - datetime.timedelta(days=90)
        start_180 = today - datetime.timedelta(days=180)
        unlock_end = today + datetime.timedelta(days=90)

        def date_text(day):
            return day.strftime("%Y-%m-%d")

        def empty_tushare_item(api, error):
            return data_capability.empty_tushare_item(api, error)

        def summarize_tushare_call(api, call):
            start_time = time.perf_counter()
            try:
                result = call()
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                return data_capability.summarize_tushare_result(api, result=result, latency_ms=latency_ms)
            except Exception as exc:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                return data_capability.summarize_tushare_exception(api, exc, latency_ms=latency_ms)

        tushare_api_names = [
            "trade_cal",
            "daily",
            "daily_basic",
            "moneyflow",
            "top_list",
            "top_inst",
            "margin_detail",
            "limit_list_d",
            "limit_cpt_list",
            "cyq_perf",
            "cyq_chips",
            "anns_d",
            "forecast",
            "stk_holdertrade",
            "share_float",
            "pledge_stat",
            "pledge_detail",
            "stk_surv",
        ]
        tushare_items = []
        recent_trade_date = today.strftime("%Y%m%d")
        if _tushare_adapter is None:
            error = str(TUSHARE_ADAPTER_MODULE_ERROR) or "tushare_adapter 不可用"
            tushare_items = [empty_tushare_item(api, error) for api in tushare_api_names]
        else:
            trade_cal_item = summarize_tushare_call(
                "trade_cal",
                lambda: _tushare_adapter.get_trade_cal(date_text(start_30), date_text(today)),
            )
            tushare_items.append(trade_cal_item)
            if trade_cal_item.get("latest_date"):
                recent_trade_date = trade_cal_item["latest_date"]

            tushare_specs = [
                ("daily", lambda: _tushare_adapter.get_daily(sample_ts_code, date_text(start_30), date_text(today))),
                ("daily_basic", lambda: _tushare_adapter.get_daily_basic(sample_ts_code, date_text(start_30), date_text(today))),
                ("moneyflow", lambda: _tushare_adapter.get_moneyflow(ts_code=sample_ts_code, start_date=date_text(start_10), end_date=date_text(today))),
                ("top_list", lambda: _tushare_adapter.get_top_list(trade_date=recent_trade_date)),
                ("top_inst", lambda: _tushare_adapter.get_top_inst(trade_date=recent_trade_date, ts_code=sample_ts_code)),
                ("margin_detail", lambda: _tushare_adapter.get_margin_detail(ts_code=sample_ts_code, start_date=date_text(start_30), end_date=date_text(today))),
                ("limit_list_d", lambda: _tushare_adapter.get_limit_list_d(trade_date=recent_trade_date)),
                ("limit_cpt_list", lambda: _tushare_adapter.get_limit_cpt_list(trade_date=recent_trade_date)),
                ("cyq_perf", lambda: _tushare_adapter.get_cyq_perf(ts_code=sample_ts_code, trade_date=recent_trade_date)),
                ("cyq_chips", lambda: _tushare_adapter.get_cyq_chips(ts_code=sample_ts_code, trade_date=recent_trade_date)),
                ("anns_d", lambda: _tushare_adapter.get_anns_d(ts_code=sample_ts_code, start_date=date_text(start_90), end_date=date_text(today))),
                ("forecast", lambda: _tushare_adapter.get_forecast(ts_code=sample_ts_code, start_date=date_text(start_180), end_date=date_text(today))),
                ("stk_holdertrade", lambda: _tushare_adapter.get_stk_holdertrade(ts_code=sample_ts_code, start_date=date_text(start_180), end_date=date_text(today))),
                ("share_float", lambda: _tushare_adapter.get_share_float(ts_code=sample_ts_code, start_date=date_text(today), end_date=date_text(unlock_end))),
                ("pledge_stat", lambda: _tushare_adapter.get_pledge_stat(ts_code=sample_ts_code)),
                ("pledge_detail", lambda: _tushare_adapter.get_pledge_detail(ts_code=sample_ts_code)),
                ("stk_surv", lambda: _tushare_adapter.get_stk_surv(ts_code=sample_ts_code, start_date=date_text(start_90), end_date=date_text(today))),
            ]
            for api, call in tushare_specs:
                if not hasattr(_tushare_adapter, f"get_{api}"):
                    tushare_items.append(empty_tushare_item(api, f"tushare_adapter 未接入 {api}"))
                    continue
                tushare_items.append(summarize_tushare_call(api, call))

        tushare_result = data_capability.build_tushare_capability_packet(
            tushare_items,
            checked_at=checked_at,
        )

        supabase_tables = ["brain_memory", "market_news", "processed_sources"]
        supabase_items = []
        if _supabase_client is None:
            supabase_items = [
                {
                    "table": table,
                    "ok": False,
                    "rows": 0,
                    "count": "",
                    "latency_ms": 0,
                    "error": "Supabase 未配置或初始化失败",
                    "status": "未配置",
                }
                for table in supabase_tables
            ]
        else:
            for table in supabase_tables:
                start_time = time.perf_counter()
                try:
                    response = _supabase_client.table(table).select("*", count="exact").limit(1).execute()
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    data = response.data if getattr(response, "data", None) else []
                    count = getattr(response, "count", None)
                    supabase_items.append(
                        {
                            "table": table,
                            "ok": True,
                            "rows": len(data),
                            "count": count if count is not None else "",
                            "latency_ms": latency_ms,
                            "error": "",
                            "status": "正常" if data else "可连接但无样本",
                        }
                    )
                except Exception as exc:
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    error_text = data_capability.compact_error(exc)
                    status_state = data_capability.classify_capability_state(ok=False, rows=0, error=error_text)
                    supabase_items.append(
                        {
                            "table": table,
                            "ok": False,
                            "rows": 0,
                            "count": "",
                            "latency_ms": latency_ms,
                            "error": error_text,
                            "status": data_capability.state_label(status_state),
                        }
                    )
        supabase_ok_count = sum(1 for item in supabase_items if item.get("ok"))
        supabase_result = {
            "source": "Supabase",
            "checked_at": checked_at,
            "ok_count": supabase_ok_count,
            "failed_count": len(supabase_items) - supabase_ok_count,
            "items": supabase_items,
        }

        deepseek_keys = list(_deepseek_keys or [])
        deepseek_result = {
            "source": "DeepSeek",
            "checked_at": checked_at,
            "ok": bool(deepseek_keys),
            "key_count": len(deepseek_keys),
            "ping_enabled": bool(include_deepseek_ping),
            "latency_ms": 0,
            "error": "",
            "status": "已配置" if deepseek_keys else "缺少 key",
        }
        if include_deepseek_ping and deepseek_keys:
            start_time = time.perf_counter()
            try:
                client = OpenAI(
                    api_key=deepseek_keys[0],
                    base_url="https://api.deepseek.com/v1",
                    timeout=20.0,
                )
                client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": "ping"}],
                    stream=False,
                    temperature=0,
                    max_tokens=8,
                )
                deepseek_result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                deepseek_result["status"] = "连通"
            except Exception as exc:
                error_text = data_capability.compact_error(exc)
                status_state = data_capability.classify_capability_state(ok=False, rows=0, error=error_text)
                deepseek_result["ok"] = False
                deepseek_result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                deepseek_result["error"] = error_text
                deepseek_result["status"] = data_capability.state_label(status_state)

        data_capability_packet = data_capability.build_unified_provider_capability_packet(
            health_result={
                "checked_at": checked_at,
                "tushare": tushare_result,
                "supabase": supabase_result,
            },
            include_manual_providers=True,
            checked_at=checked_at,
        )

        return {
            "checked_at": checked_at,
            "sample_ts_code": sample_ts_code,
            "tushare": tushare_result,
            "supabase": supabase_result,
            "deepseek": deepseek_result,
            "data_capability": data_capability_packet,
        }

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

    def build_limited_unverified_prompt_block(items, source_label, max_items=10, max_chars=4000, per_item_chars=700):
        lines = []
        used_chars = 0
        seen = set()

        for item in items or []:
            text = compact_prompt_text(item, per_item_chars)
            if not text or text in seen:
                continue
            line = f"{len(lines) + 1}. {text}"
            next_chars = used_chars + len(line) + 1
            if next_chars > max_chars:
                break
            lines.append(line)
            seen.add(text)
            used_chars = next_chars
            if len(lines) >= max_items:
                break

        if not lines:
            return ""

        return (
            "\n\n【投喂资料观点 / 历史假设 / 待验证线索】\n"
            f"来源：{source_label}。以下内容最多 {max_items} 条、总字符不超过 {max_chars}，"
            "只能作为观点、历史假设或待验证线索，不能作为已验证事实。\n"
            + "\n".join(lines)
        )

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
                if (
                    source_table == "stock_reports"
                    and (
                        row.get("ticker") == ANNOUNCEMENT_WATCHLIST_TICKER
                        or row.get("report_type") == ANNOUNCEMENT_WATCHLIST_REPORT_TYPE
                        or row.get("report_type") == NEWS_DIGEST_REPORT_TYPE
                    )
                ):
                    continue
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
        market_rows = []
        processed_rows = []

        try:
            res = (
                supabase
                .table("market_news")
                .select("keyword, title, url, source, summary, risk_tag, sentiment, created_at")
                .order("created_at", desc=True)
                .limit(max(limit * 4, 40))
                .execute()
            )
            market_rows = filter_topic_news_for_prompt(res.data or [], max_items=limit, per_topic=2, hours=48)
            for item in market_rows:
                title = item.get("title", "")
                if not title:
                    continue
                context.append(
                    f"market_news线索｜{item.get('keyword', '')}｜{title}"
                    f"｜情绪:{item.get('sentiment', '')}"
                    f"｜风险:{item.get('risk_tag', '')}"
                    f"｜摘要:{item.get('summary', '')}"
                    f"｜时间:{item.get('created_at', '')}"
                    f"｜边界:{item.get('fact_boundary', '新闻线索，不是官方事实')}"
                )
        except Exception as e:
            context.append(f"market_news 读取失败：{e}")

        try:
            res = (
                supabase
                .table("processed_sources")
                .select("manager_name, title, url, created_at")
                .order("created_at", desc=True)
                .limit(max(limit * 3, 30))
                .execute()
            )
            processed_rows = filter_news_clues_for_prompt(res.data or [], max_items=limit, hours=72)
            for item in processed_rows:
                title = item.get("title", "")
                if not title:
                    continue
                context.append(
                    f"processed_sources待验证｜{item.get('manager_name', '')}｜{title}"
                    f"｜时间:{item.get('created_at', '')}"
                    f"｜链接:{item.get('url', '')}"
                    f"｜边界:投喂资料/历史假设/待验证线索"
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

    def build_today_watchlist_prompt(market_style_fact_packet=None):
        today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        position_status_for_prompt = st.session_state.get("position_status", "未买入 (观望/找买点)")
        capital_plan_for_prompt = st.session_state.get("capital_plan", 0)

        market_style_fact_packet = market_style_fact_packet or build_market_style_fact_packet()
        db = load_cloud_knowledge()

        def sanitize_unverified_prompt_text(text):
            text = str(text or "")
            replacements = {
                "买入条件": "待验证观察条件",
                "买点条件": "待验证观察条件",
                "买点": "观察点",
                "买入": "观察",
                "buy_conditions": "待验证观察条件",
                "加仓": "风格适配线索",
                "增持": "风格适配线索",
                "看好": "风格适配线索",
                "持仓": "风格适配线索",
                "持有": "风格适配线索",
                "关键均线": "待验证技术指标",
            }
            for raw, safe in replacements.items():
                text = text.replace(raw, safe)
            text = re.sub(r"\d[\d,]*(?:股|万股|亿股)", "数量待核验", text)
            text = re.sub(
                r"(站上|站稳|跌破|企稳于|企稳在|附近企稳|回踩|回调至)\s*(MA20|MA50|MA60|MA200|RSI|PB|ROE)",
                "后续需用技术指标验证",
                text,
                flags=re.IGNORECASE,
            )
            return text

        brain_rules = sanitize_unverified_prompt_text("\n".join((db["strategies"] + db["reflections"])[-20:]))
        market_snapshot = "\n".join(fetch_market_snapshot())
        market_context_lines = fetch_recent_market_context()
        verified_market_news_lines = [
            line for line in market_context_lines
            if str(line).startswith("market_news")
        ]
        feed_context_lines = [
            sanitize_unverified_prompt_text(line) for line in market_context_lines
            if not str(line).startswith("market_news")
        ]
        market_news_clues = "\n".join(verified_market_news_lines)
        feed_context = "\n".join(feed_context_lines)
        emerging_trends = summarize_context_trends(market_context_lines)
        dragon_tiger_activity = market_style_fact_packet.get("dragon_tiger_activity") or {}
        concept_strength_top = market_style_fact_packet.get("concept_strength_top") or []
        moneyflow_samples = market_style_fact_packet.get("moneyflow_samples") or {}
        moneyflow_sample_count = len(moneyflow_samples.get("positive_samples") or []) + len(
            moneyflow_samples.get("negative_samples") or []
        )
        missing_sources_text = (
            ", ".join(market_style_fact_packet.get("missing_sources") or [])
            if market_style_fact_packet.get("missing_sources")
            else "暂无"
        )

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
            sanitize_unverified_prompt_text(
                f"{m.get('manager_name')}｜{m.get('rule_type')}｜{m.get('content')}"
            )
            for m in manager_data
        ])

        prompt = f"""
当前时间：{today_str}
用户当前状态：{position_status_for_prompt}
本金/计划仓位：{capital_plan_for_prompt}

你是我的个人投研总控台。请基于分层资料生成【市场风格判断 + 今日关注池 + 次日验证清单】。

输出开头必须先逐项展示以下内容，不得省略，不得只引用 JSON：
【市场风格总览】
- 数据日期：{market_style_fact_packet.get("trade_date") or "暂无可验证数据"}
- 涨停家数：{market_style_fact_packet.get("limit_up_count", 0)}
- 跌停家数：{market_style_fact_packet.get("limit_down_count", 0)}
- 炸板家数：{market_style_fact_packet.get("break_limit_count", 0)}
- 炸板率：{market_style_fact_packet.get("break_limit_rate") if market_style_fact_packet.get("break_limit_rate") is not None else "暂无可验证数据"}
- 最高连板：{market_style_fact_packet.get("max_consecutive_limit") if market_style_fact_packet.get("max_consecutive_limit") is not None else "暂无可验证数据"}
- 龙虎榜活跃数量：{dragon_tiger_activity.get("list_count", 0)}
- 概念强度样本数量：{len(concept_strength_top)}
- 资金流样本数量：{moneyflow_sample_count}
- market_state：{market_style_fact_packet.get("market_state") or "暂无可验证数据"}
- risk_switch：{market_style_fact_packet.get("risk_switch") or "适合只观察不买"}
- missing_sources：{missing_sources_text}

【已验证结构化数据】
只能包含以下两类：
1. Tushare market_style_fact_packet
2. Yahoo Finance 市场快照

market_style_fact_packet:
{json.dumps(market_style_fact_packet, ensure_ascii=False, indent=2, default=str)}

Tushare 数据源说明：
- 优先使用 limit_list_d / top_list / moneyflow 的真实返回。
- 数据日期：{market_style_fact_packet.get("trade_date") or "暂无可验证数据"}
- 缺失项：{missing_sources_text}
- 若 concept_strength_top 有真实返回，只能作为“概念强度 / 题材热度 / 过热风控”引用；不得写成建议追涨。
- 若 concept_strength_top 为空，不得引用未返回的概念强度。

Yahoo Finance 市场快照：
{market_snapshot}

【市场话题线索】
Supabase market_news 新闻线索（每个主题已限量、去重、降权宽 RSS）：
{market_news_clues if market_news_clues else "暂无可用 market_news 新闻线索。"}
说明：Supabase market_news 只能证明系统真实返回了 title / summary / risk_tag / sentiment / created_at 等字段；risk_tag / sentiment 是模型提取标签，不是官方事实；不得把新闻标题外推成公告已确认、订单已落地、客户已确认、监管处罚、诉讼、减持、业绩预告或席位资金事实。

【谨慎推断】
- 市场状态：{market_style_fact_packet.get("market_state") or "暂无可验证数据"}
- 进攻/防守开关：{market_style_fact_packet.get("risk_switch") or "适合只观察不买"}
- 推断边界：只能基于已验证数据和明确标注的待验证线索进行条件式判断；字段不足时必须偏防守，不得硬判，不得把待验证线索写成事实。

【投喂资料观点 / 待验证线索】
以下内容只能作为观点、风格适配或待验证线索，不得写入“已验证数据依据”：

processed_sources / 历史投喂观点：
{feed_context if feed_context else "暂无 processed_sources 待验证线索。"}

新趋势候选：
{emerging_trends}

我的交易外脑 brain_memory：
{brain_rules}

基金经理人格规则 manager_rules：
{manager_text}

manager_rules 说明：当前输入只包含 manager_name / rule_type / content，不包含可核验 source 或 url；基金经理相关内容默认只能写成“风格适配 / 待验证观点”，不得写成或复述某基金经理实际买入、加仓、增持、看好，也不得复述持股数量。

【观察清单】
请输出以下五类关注池。今日关注池不是买入建议，只能写“关注 / 观察 / 验证”。每一类观察标的不超过 3 个，可以为空；如果没有足够真实数据支撑，必须写“暂无可验证数据”，不要为了凑满数量而编标的。
触发条件和放弃条件中如需引用 MA20、MA50、MA60、MA200、RSI、PB、ROE、均线、技术支撑，整行只能写“后续需用 MA20/MA60/MA50/MA200/RSI/PB/ROE 验证”，不得扩写成站上、站稳、跌破、企稳、支撑、关键均线、分位等技术结论。

### 进攻型
- 观察标的：
- 已验证数据依据：
- 谨慎推断：
- 投喂资料观点 / 待验证线索：
- 触发条件：
- 放弃条件：
- 次日验证点：
- 风险提示：

### 防守型
- 观察标的：
- 已验证数据依据：
- 谨慎推断：
- 投喂资料观点 / 待验证线索：
- 触发条件：
- 放弃条件：
- 次日验证点：
- 风险提示：

### 港股反弹型
- 观察标的：
- 已验证数据依据：
- 谨慎推断：
- 投喂资料观点 / 待验证线索：
- 触发条件：
- 放弃条件：
- 次日验证点：
- 风险提示：

### 美股 AI 型
- 观察标的：
- 已验证数据依据：
- 谨慎推断：
- 投喂资料观点 / 待验证线索：
- 触发条件：
- 放弃条件：
- 次日验证点：
- 风险提示：

### 只观察不买型
- 观察标的：
- 已验证数据依据：
- 谨慎推断：
- 投喂资料观点 / 待验证线索：
- 触发条件：
- 放弃条件：
- 次日验证点：
- 风险提示：

最后必须单独输出：

【次日验证清单】
- 市场情绪验证：
- 主线方向验证：
- 风险信号验证：
- 关注池淘汰条件：

强制要求：
1. 不得把【投喂资料观点】当成事实，只能标记为观点、线索或待验证假设。
2. 不得编造龙虎榜、机构席位、连板、炸板、资金流；龙虎榜、机构席位、连板、炸板只能来自 market_style_fact_packet 或 Tushare 真实返回。
3. 没有 Tushare 真实返回时，只能写“暂无可验证数据”。
4. 今日关注池不是买入建议，只能写“关注 / 观察 / 验证”。
5. 不得编造实时价格。
6. 禁止“严禁买入、必涨、满仓、梭哈、确定性机会”等绝对化措辞。
7. 如果没有足够事实支撑，应放入“只观察不买型”。
8. 不要为了凑满数量而编标的。
9. 结论要偏交易实用，不要写空话。
10. “已验证数据依据”只能引用 Tushare 和 Yahoo Finance 市场快照等结构化真实返回；market_news、processed_sources、brain_memory、manager_rules 只能进入“新闻线索 / 投喂资料观点 / 待验证线索”。
11. 如果观察标的只来自投喂资料或记忆，必须在“谨慎推断”中标为“待验证线索”，不得写成已验证资金行为。
12. 没有 Tushare 公告、官方公告或可信原文验证时，不得把订单金额、授权、收购、客户名称写成事实；market_news 标题不能单独构成验证。
13. MA20、MA60、MA50、MA200、RSI、PB、ROE 如果没有当前数值，固定写“后续需用 MA20/MA60/MA50/MA200/RSI/PB/ROE 验证”；不得写“股价在 MA20 附近企稳”“站上 MA60”“站稳 MA50”“跌破 MA60”“RSI 在 40-60”“PB 低于历史分位”等像已计算的条件。
14. 标的名称不确定时写“标的名称待核验”，不得输出 CPOAI 这类自造简称。
15. 基金经理相关内容只能写“风格适配”或“待验证观点”；当前 manager_rules 不含 source/url，不能作为实际交易事实来源。即使 manager_rules 原文包含“买入、加仓、增持、看好、持股数量”等字样，输出时也必须改写为“风格偏好指向该方向”，不得复述交易动作或数量。
16. “只观察不买型”统一使用：“未满足验证条件前仅观察”。
17. 每个方向的“已验证数据依据”必须逐项列出来源名和字段名；如果没有对应真实返回，必须写“暂无可验证数据”，不得用投喂资料补足。
18. market_news 中出现“龙虎榜盘点、席位、机构”等标题时，只能作为新闻线索；不得据此生成具体机构席位、净买入、席位动向或龙虎榜结论。具体龙虎榜数量和样本只能引用 market_style_fact_packet / Tushare top_list 字段。
19. 不得输出 buy_conditions、买入条件、买点条件、买点；统一改写为“待验证观察条件”。
20. market_news / yfinance.news / processed_sources 不得替代公告、监管、诉讼、处罚、减持、业绩预告等官方事实。
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
            aliases = _news_query_aliases(keyword)
            candidate_limit = min(max(limit * 8, 20), 50) if any(
                len(alias) <= 5 and alias.isascii() for alias in aliases
            ) else limit
            query = (
                supabase
                .table("processed_sources")
                .select("title, url, manager_name, created_at")
            )
            if aliases:
                query = query.or_(",".join(f"title.ilike.%{alias}%" for alias in aliases[:8]))
            res = (
                query
                .order("created_at", desc=True)
                .limit(candidate_limit)
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
            aliases = _news_query_aliases(keyword)
            candidate_limit = min(max(limit * 8, 20), 50) if any(
                len(alias) <= 5 and alias.isascii() for alias in aliases
            ) else limit
            query = (
                supabase
                .table("market_news")
                .select("keyword, title, url, summary, risk_tag, sentiment, created_at")
            )
            if aliases:
                query = query.or_(
                    ",".join(
                        f"{column}.ilike.%{alias}%"
                        for alias in aliases[:8]
                        for column in ["keyword", "title", "summary"]
                    )
                )
            res = (
                query
                .order("created_at", desc=True)
                .limit(candidate_limit)
                .execute()
            )

            return res.data or []

        except Exception as e:
            st.warning(f"⚠️ market_news 读取失败: {e}")
            return []

    def _announcement_report_ticker_terms(ticker):
        normalized = normalize_ticker(ticker)
        terms = [ticker, normalized]
        core = _cn_stock_code_6(normalized)
        if core:
            terms.extend([core, f"{core}.SZ", f"{core}.SH", f"{core}.SS"])
        return [term for term in dict.fromkeys(str(term or "").strip().upper() for term in terms) if term]

    def _report_content_matches_ticker(content, ticker):
        target_terms = set(_announcement_report_ticker_terms(ticker))
        if not target_terms:
            return False
        for key in ["stock_code", "ticker", "ts_code"]:
            value_terms = set(_announcement_report_ticker_terms(content.get(key)))
            if value_terms and target_terms.intersection(value_terms):
                return True
        return False

    def _parse_announcement_report_content(content):
        if isinstance(content, dict):
            return content
        try:
            return json.loads(str(content or ""))
        except Exception:
            return {}

    def load_recent_announcement_summaries(ticker, days=14, limit=6):
        updated_at = datetime.datetime.now().isoformat(timespec="seconds")
        section = {
            "available": False,
            "source": "stock_reports.announcement_summary",
            "window_days": days,
            "rows": [],
            "summary": "",
            "risk_flags": [],
            "message": f"暂无近{int(days or 14)}天免费公告摘要",
            "error": "",
            "updated_at": updated_at,
            "policy": {
                "parsed_pdf_is_summary_clue": True,
                "metadata_only_is_title_clue": True,
                "title_is_not_hard_fact": True,
            },
        }
        if not supabase:
            section["message"] = "Supabase 不可用，暂无免费公告雷达。"
            return section

        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=int(days or 14))
        rows = []
        try:
            terms = _announcement_report_ticker_terms(ticker)
            candidate_limit = min(max(limit * 4, 12), 50)
            query = (
                supabase
                .table("stock_reports")
                .select("ticker, report_content, created_at")
                .eq("report_type", "announcement_summary")
                .gte("created_at", cutoff.isoformat())
                .order("created_at", desc=True)
                .limit(candidate_limit)
            )
            if terms:
                query = query.in_("ticker", terms)
            res = query.execute()
            rows = res.data or []
            if not rows and terms:
                fallback_res = (
                    supabase
                    .table("stock_reports")
                    .select("ticker, report_content, created_at")
                    .eq("report_type", "announcement_summary")
                    .gte("created_at", cutoff.isoformat())
                    .order("created_at", desc=True)
                    .limit(candidate_limit)
                    .execute()
                )
                rows = [
                    row for row in (fallback_res.data or [])
                    if _report_content_matches_ticker(
                        _parse_announcement_report_content(row.get("report_content")),
                        ticker,
                    )
                ]
        except Exception as exc:
            section["error"] = str(exc)
            section["message"] = "读取免费公告摘要失败。"
            return section

        seen = set()
        for row in rows:
            payload = _parse_announcement_report_content(row.get("report_content"))
            title = str(payload.get("title") or "").strip()
            ann_date = str(payload.get("ann_date") or "").strip()
            key = (title, ann_date, payload.get("pdf_url") or payload.get("url") or "")
            if not title or key in seen:
                continue
            seen.add(key)
            summary = payload.get("summary") or {}
            if not isinstance(summary, dict):
                summary = {"one_line_summary": str(summary)}
            fetch_status = payload.get("fetch_status") or ""
            boundary = (
                "公告摘要线索：PDF 已解析，AI 摘要不等于公告原文"
                if fetch_status == "parsed_pdf"
                else "公告标题线索：未解析正文，不得下事实结论"
            )
            item = {
                "ticker": payload.get("ticker") or row.get("ticker") or "",
                "ann_date": ann_date,
                "title": title,
                "pdf_url": payload.get("pdf_url") or "",
                "url": payload.get("url") or "",
                "important": bool(payload.get("important")),
                "fetch_status": fetch_status,
                "parse_status": payload.get("parse_status") or "",
                "ai_summary": summary.get("one_line_summary") or "",
                "risk_level": summary.get("impact_level") or "未知",
                "impact_direction": summary.get("impact_direction") or "不确定",
                "risk_tags": summary.get("risk_tags") or payload.get("provider_risk_tags") or [],
                "needs_manual_review": bool(summary.get("needs_manual_review")),
                "source_boundary": payload.get("source_boundary") or boundary,
                "created_at": row.get("created_at") or payload.get("created_at") or "",
            }
            if item["important"]:
                tags = "、".join(str(tag) for tag in item["risk_tags"][:3]) if item["risk_tags"] else "重要公告"
                section["risk_flags"].append(f"免费公告雷达线索：{tags}")
            section["rows"].append(item)
            if len(section["rows"]) >= limit:
                break

        section["available"] = bool(section["rows"])
        if section["available"]:
            parsed_count = sum(1 for item in section["rows"] if item.get("fetch_status") == "parsed_pdf")
            section["summary"] = f"近{days}天读取免费公告摘要 {len(section['rows'])} 条，其中 PDF 已解析 {parsed_count} 条。"
            section["message"] = ""
        return section

    @st.cache_data(ttl=300, show_spinner=False)
    def load_recent_news_digests(ticker, days=4, limit=5):
        updated_at = datetime.datetime.now().isoformat(timespec="seconds")
        section = {
            "available": False,
            "source": "stock_reports.news_digest",
            "window_days": days,
            "rows": [],
            "summary": "",
            "risk_flags": [],
            "message": "暂无最近新闻摘要线索",
            "error": "",
            "updated_at": updated_at,
            "policy": {
                "claims_are_clues_not_facts": True,
                "evidence_is_supporting_material_not_official_fact": True,
                "no_hard_facts": True,
            },
        }
        if not supabase:
            section["message"] = "Supabase 不可用，暂无最近新闻摘要线索。"
            return section

        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=int(days or 4))
        rows = []
        try:
            terms = _announcement_report_ticker_terms(ticker)
            candidate_limit = min(max(limit * 4, 12), 50)
            query = (
                supabase
                .table("stock_reports")
                .select("ticker, report_content, created_at")
                .eq("report_type", NEWS_DIGEST_REPORT_TYPE)
                .gte("created_at", cutoff.isoformat())
                .order("created_at", desc=True)
                .limit(candidate_limit)
            )
            if terms:
                query = query.in_("ticker", terms)
            res = query.execute()
            rows = res.data or []
            if not rows and terms:
                fallback_res = (
                    supabase
                    .table("stock_reports")
                    .select("ticker, report_content, created_at")
                    .eq("report_type", NEWS_DIGEST_REPORT_TYPE)
                    .gte("created_at", cutoff.isoformat())
                    .order("created_at", desc=True)
                    .limit(candidate_limit)
                    .execute()
                )
                rows = [
                    row for row in (fallback_res.data or [])
                    if _report_content_matches_ticker(
                        _parse_announcement_report_content(row.get("report_content")),
                        ticker,
                    )
                ]
        except Exception as exc:
            section["error"] = str(exc)
            section["message"] = "读取新闻摘要线索失败。"
            return section

        seen = set()
        rows_out = []
        latest_summary = ""
        for row in rows:
            payload = _parse_announcement_report_content(row.get("report_content"))
            if not isinstance(payload, dict):
                continue
            if not latest_summary:
                latest_summary = str(payload.get("one_line_summary") or "").strip()
            items = payload.get("items") or []
            if not isinstance(items, list):
                items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                published_at = str(item.get("published_at") or row.get("created_at") or "").strip()
                url = str(item.get("url") or "").strip()
                key = (title, url, published_at)
                if key in seen:
                    continue
                seen.add(key)
                claims = item.get("claims") if isinstance(item.get("claims"), list) else []
                clues = item.get("clues") if isinstance(item.get("clues"), list) else []
                evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else []
                summary = item.get("digest_summary") or item.get("one_line_summary") or ""
                risk_tags = item.get("risk_tags") if isinstance(item.get("risk_tags"), list) else []
                rows_out.append({
                    "ticker": payload.get("ticker") or row.get("ticker") or "",
                    "stock_code": payload.get("stock_code") or "",
                    "stock_name": payload.get("stock_name") or "",
                    "market_type": payload.get("market_type") or "",
                    "published_at": published_at,
                    "title": title,
                    "url": url,
                    "source": item.get("source") or payload.get("source") or "news_digest",
                    "relevance_score": item.get("relevance_score") or 0,
                    "digest_summary": summary,
                    "risk_tag": item.get("risk_tag") or "",
                    "sentiment": item.get("sentiment") or "",
                    "claims": claims,
                    "clues": clues,
                    "evidence": evidence,
                    "verification_status": item.get("verification_status") or "待验证",
                    "source_boundary": item.get("source_boundary") or "新闻只能作为待验证线索，不得进入硬事实层",
                    "matched_aliases": item.get("matched_aliases") or [],
                })

        section["rows"] = rows_out[:limit]
        section["summary"] = latest_summary or "；".join(
            str(item.get("title") or "").strip()
            for item in rows_out[:3]
            if str(item.get("title") or "").strip()
        )
        section["available"] = bool(section["rows"])
        if section["available"]:
            section["message"] = f"已找到 {len(section['rows'])} 条最近新闻摘要线索。"
        return section

    def format_news_digest_radar(section):
        section = section or {}
        if not section.get("available"):
            return section.get("message") or "暂无最近新闻摘要线索。"
        lines = []
        for item in (section.get("rows") or [])[:3]:
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            published_at = str(item.get("published_at") or "").strip()
            risk_tag = str(item.get("risk_tag") or "").strip()
            sentiment = str(item.get("sentiment") or "").strip()
            summary = str(item.get("digest_summary") or "").strip()
            claims = item.get("claims") or []
            clues = item.get("clues") or []
            evidence = item.get("evidence") or []
            line = f"{published_at}｜{title}｜来源:{item.get('source', '')}｜状态:{item.get('verification_status', '待验证')}"
            if risk_tag or sentiment:
                line += f"｜风险标签:{risk_tag or '普通新闻'}/{sentiment or '中性'}"
            if summary:
                line += f"｜摘要:{summary}"
            if claims:
                line += f"｜claims:{';'.join(str(x) for x in claims[:2] if str(x).strip())}"
            if clues:
                line += f"｜clues:{';'.join(str(x) for x in clues[:2] if str(x).strip())}"
            if evidence:
                line += f"｜evidence:{';'.join(str(x) for x in evidence[:2] if str(x).strip())}"
            line += f"｜边界:{item.get('source_boundary', '新闻只能作为待验证线索，不得进入硬事实层')}"
            lines.append(line)
        return "；".join(lines) if lines else section.get("summary") or section.get("message") or "暂无最近新闻摘要线索。"

    def app_check_risk_veto(target, market_type, headlines):
        # Auto news/RSS headlines are intentionally not allowed to trigger a hard veto.
        # Tushare hard-risk sections drive official risk conclusions downstream.
        reasons = []
        soft_clues = []

        if market_type in ["A_SHARE_SH", "A_SHARE_SZ"]:
            if "ST" in str(target or "").upper():
                reasons.append("A股：ST 或退市风险")

        text = "\n".join(str(item) for item in headlines or [])
        if any(word in text for word in ["监管问询", "问询函", "立案调查", "财务造假", "减持", "guidance cut", "insider selling"]):
            soft_clues.append("auto 新闻标题命中风险词，仅作为待验证线索，不触发一票否决")

        return {
            "risk_flag": bool(reasons),
            "reasons": reasons,
            "soft_clues": soft_clues,
            "auto_news_veto_disabled": True,
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

    def _cn_stock_code_6(stock_code):
        text = str(stock_code or "").upper().strip()
        text = text.replace(".SS", "").replace(".SH", "").replace(".SZ", "")
        text = text.split(".")[0]
        digits = re.sub(r"\D", "", text)
        return digits.zfill(6) if digits else text

    def normalize_announcement_watchlist_code(raw_code):
        text = str(raw_code or "").upper().strip()
        text = text.replace(" ", "").replace("。", ".")
        text = text.replace(".SS", ".SH")
        if not text:
            return "", "", "请输入股票代码。"

        suffix = ""
        if text.endswith((".SZ", ".SH", ".BJ")):
            suffix = text[-2:]
            code = text[:-3]
        else:
            code = re.sub(r"\D", "", text)

        if not re.fullmatch(r"\d{6}", code or ""):
            return "", "", "免费公告自动扫描第一阶段仅支持 6 位 A 股代码。"

        if not suffix:
            if code.startswith(("6", "9")):
                suffix = "SH"
            elif code.startswith(("0", "2", "3")):
                suffix = "SZ"
            elif code.startswith(("4", "8")):
                suffix = "BJ"
            else:
                return "", "", "免费公告自动扫描第一阶段仅支持 A 股。"

        if suffix not in {"SZ", "SH", "BJ"}:
            return "", "", "免费公告自动扫描第一阶段仅支持 A 股。"
        return f"{code}.{suffix}", code, ""

    def build_empty_announcement_watchlist():
        return {
            "version": 1,
            "updated_at": "",
            "source": "app_manual",
            "targets": [],
        }

    def normalize_announcement_watchlist_payload(payload):
        data = payload if isinstance(payload, dict) else build_empty_announcement_watchlist()
        now_text = datetime.datetime.now(datetime.timezone.utc).isoformat()
        normalized = {
            "version": int(data.get("version") or 1),
            "updated_at": str(data.get("updated_at") or ""),
            "source": str(data.get("source") or "app_manual"),
            "targets": [],
        }
        seen = set()
        for item in data.get("targets") or []:
            if not isinstance(item, dict):
                continue
            ts_code, stock_code, error = normalize_announcement_watchlist_code(
                item.get("ts_code") or item.get("ticker") or item.get("stock_code")
            )
            if error or not ts_code or ts_code in seen:
                continue
            seen.add(ts_code)
            added_at = str(item.get("added_at") or item.get("created_at") or now_text)
            normalized["targets"].append({
                "ts_code": ts_code,
                "stock_code": stock_code,
                "name": str(item.get("name") or item.get("stock_name") or "").strip(),
                "market_type": "A_SHARE",
                "enabled": bool(item.get("enabled", True)),
                "priority": str(item.get("priority") or "normal"),
                "added_at": added_at,
                "updated_at": str(item.get("updated_at") or added_at),
                "note": str(item.get("note") or "").strip(),
            })
        return normalized

    def load_announcement_watchlist():
        if not supabase:
            return build_empty_announcement_watchlist(), "Supabase 不可用，持续调查池暂不可读取。"
        try:
            res = (
                supabase
                .table("stock_reports")
                .select("report_content, created_at")
                .eq("ticker", ANNOUNCEMENT_WATCHLIST_TICKER)
                .eq("report_type", ANNOUNCEMENT_WATCHLIST_REPORT_TYPE)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            if not rows:
                return build_empty_announcement_watchlist(), ""
            payload, _ = parse_memory_payload(rows[0].get("report_content", ""))
            return normalize_announcement_watchlist_payload(payload), ""
        except Exception as exc:
            return build_empty_announcement_watchlist(), f"读取持续调查池失败：{exc}"

    def save_announcement_watchlist(payload):
        payload = normalize_announcement_watchlist_payload(payload)
        payload["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload["source"] = "app_manual"
        return save_stock_report(
            ANNOUNCEMENT_WATCHLIST_TICKER,
            "A_SHARE",
            ANNOUNCEMENT_WATCHLIST_REPORT_TYPE,
            payload,
        )

    def upsert_announcement_watchlist_target(raw_code, name="", note=""):
        ts_code, stock_code, error = normalize_announcement_watchlist_code(raw_code)
        if error:
            return False, error, None

        payload, load_error = load_announcement_watchlist()
        if load_error:
            return False, load_error, None

        now_text = datetime.datetime.now(datetime.timezone.utc).isoformat()
        targets = payload.get("targets") or []
        matched = False
        for item in targets:
            if item.get("ts_code") != ts_code:
                continue
            matched = True
            item["stock_code"] = stock_code
            item["name"] = str(name or item.get("name") or "").strip()
            item["enabled"] = True
            item["priority"] = item.get("priority") or "normal"
            item["updated_at"] = now_text
            if note:
                item["note"] = str(note).strip()
            break

        if not matched:
            targets.append({
                "ts_code": ts_code,
                "stock_code": stock_code,
                "name": str(name or "").strip(),
                "market_type": "A_SHARE",
                "enabled": True,
                "priority": "normal",
                "added_at": now_text,
                "updated_at": now_text,
                "note": str(note or "").strip(),
            })
        payload["targets"] = targets

        if save_announcement_watchlist(payload):
            return True, "已加入持续调查池。" if not matched else "已更新持续调查池，未重复添加。", ts_code
        return False, "持续调查池写入失败。", ts_code

    def disable_announcement_watchlist_target(raw_code):
        ts_code, _, error = normalize_announcement_watchlist_code(raw_code)
        if error:
            return False, error
        payload, load_error = load_announcement_watchlist()
        if load_error:
            return False, load_error

        now_text = datetime.datetime.now(datetime.timezone.utc).isoformat()
        changed = False
        for item in payload.get("targets") or []:
            if item.get("ts_code") == ts_code:
                item["enabled"] = False
                item["updated_at"] = now_text
                changed = True
                break
        if not changed:
            return False, f"{ts_code} 不在持续调查池中。"
        if save_announcement_watchlist(payload):
            return True, f"已停用 {ts_code}。"
        return False, "持续调查池写入失败。"

    @st.cache_data(ttl=900, show_spinner=False)
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

    def _cn_wan_to_yi(value):
        number = _cn_float(value)
        if number is None:
            return None
        return round(number / 10000, 2)

    def _cn_fmt_yi(value):
        return "暂无" if value is None else f"¥{value:.2f}亿"

    def _cn_fmt_flow_yi(value):
        if value is None:
            return "暂无"
        if value > 0:
            direction = "净流入"
        elif value < 0:
            direction = "净流出"
        else:
            direction = "持平"
        return f"{value:+.2f}亿 {direction}"

    def _cn_fmt_date(value):
        text = str(value or "")
        if len(text) == 8 and text.isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:]}"
        return text or "未知"

    def _format_cn_date_values(values, max_items=4):
        unique_values = []
        for value in values or []:
            text = str(value or "").strip()
            if not text or text in unique_values:
                continue
            unique_values.append(text)
        if not unique_values:
            return "暂无"
        return " / ".join(_cn_fmt_date(item) for item in unique_values[:max_items])

    def _extract_tushare_basic_data_dates(source_payload):
        api_results = (source_payload or {}).get("api_results") or {}
        return _format_cn_date_values(
            [item.get("latest_date") for item in api_results.values() if isinstance(item, dict)]
        )

    def _extract_tianyan_packet_data_dates(packet):
        trading = (packet or {}).get("verified_trading_structure_risks") or {}
        chip = (packet or {}).get("verified_chip_risks") or {}
        moneyflow = trading.get("moneyflow") or {}
        dragon = trading.get("dragon_tiger") or {}
        margin = trading.get("margin") or {}
        limit_emotion = trading.get("limit_emotion") or {}
        chip_radar = chip.get("chip_radar") or {}
        return _format_cn_date_values(
            [
                moneyflow.get("date"),
                dragon.get("latest_date") or dragon.get("trade_date"),
                margin.get("date"),
                limit_emotion.get("latest_date") or limit_emotion.get("concept_date"),
                chip_radar.get("trade_date"),
            ]
        )

    def clear_current_stock_tushare_caches():
        cache_names = [
            "cached_fetch_tushare_a_share_basics",
            "cached_cn_dragon_tiger_board",
            "cached_cn_margin_data",
            "cached_cn_moneyflow_data",
            "cached_cn_limit_emotion_data",
            "get_cn_chip_radar_data",
            "get_cn_hard_risk_radar_data",
            "build_tianyan_risk_fact_packet",
        ]
        cleared = []
        global_namespace = globals()
        for cache_name in cache_names:
            cache_func = global_namespace.get(cache_name)
            clear_func = getattr(cache_func, "clear", None)
            if not callable(clear_func):
                continue
            try:
                clear_func()
                cleared.append(cache_name)
            except Exception:
                continue
        return cleared

    def render_tushare_refresh_control(stock_code, ui_key):
        stock_code_6 = _cn_stock_code_6(stock_code)
        if not stock_code_6:
            return
        with st.expander("强制刷新 / 数据说明", expanded=False):
            if st.button(
                "强制刷新当前标的 Tushare 分区",
                key=f"btn_refresh_tushare_{ui_key}_{stock_code_6}",
                width="stretch",
            ):
                cleared = clear_current_stock_tushare_caches()
                st.session_state["tushare_refresh_last"] = {
                    "stock_code": stock_code_6,
                    "cleared": cleared,
                    "pulled_at": datetime.datetime.now().isoformat(timespec="seconds"),
                }
                st.rerun()
            st.caption(legacy_a_share_gate_service.refresh_caption())

    @st.cache_data(ttl=600, show_spinner=False)
    def build_market_style_fact_packet():
        """构建今日关注池使用的 A 股市场情绪事实包，所有 Tushare 失败都降级为缺失项。"""
        updated_at = datetime.datetime.now().isoformat(timespec="seconds")
        packet = {
            "trade_date": "",
            "limit_up_count": 0,
            "limit_down_count": 0,
            "break_limit_count": 0,
            "break_limit_rate": None,
            "max_consecutive_limit": None,
            "recent_active_limit_samples": [],
            "dragon_tiger_activity": {
                "list_count": 0,
                "sample_rows": [],
            },
            "moneyflow_samples": {
                "positive_samples": [],
                "negative_samples": [],
            },
            "concept_strength_top": [],
            "market_state": "暂无可验证数据",
            "risk_switch": "适合只观察不买",
            "verified_sources": [],
            "missing_sources": [],
            "updated_at": updated_at,
        }

        def add_missing(source, reason="暂无可验证数据"):
            text = f"{source}: {reason}" if reason else source
            if text not in packet["missing_sources"]:
                packet["missing_sources"].append(text)

        def add_verified(source):
            if source not in packet["verified_sources"]:
                packet["verified_sources"].append(source)

        if _tushare_adapter is None:
            add_missing("Tushare", str(TUSHARE_ADAPTER_MODULE_ERROR) or "adapter 不可用")
            return packet

        recent_dates = []
        try:
            recent_dates = _cn_recent_trade_dates(10)[:5]
        except Exception as e:
            add_missing("Tushare trade_cal", str(e))

        if not recent_dates:
            add_missing("Tushare trade_cal", "未取得最近交易日")
            return packet

        def normalize_limit_value(row):
            return str(row.get("limit") or row.get("limit_type") or "").strip().upper()

        def calc_limit_stats(df):
            if df is None or df.empty:
                return None
            rows = df.where(pd.notna(df), None).to_dict("records")
            up_count = 0
            down_count = 0
            break_count = 0
            max_height = None
            for row in rows:
                value = normalize_limit_value(row)
                type_text = str(row.get("type") or row.get("name_type") or "")
                if value == "U" or "涨停" in type_text:
                    up_count += 1
                elif value == "D" or "跌停" in type_text:
                    down_count += 1
                elif value == "Z" or "炸" in type_text:
                    break_count += 1

                height = _cn_float(row.get("limit_times"))
                if height is None:
                    stat_text = str(row.get("up_stat") or "")
                    match = re.search(r"(\d+)\s*连", stat_text)
                    if match:
                        height = _cn_float(match.group(1))
                if height is not None:
                    max_height = int(max(height, max_height or 0))

            denominator = up_count + break_count
            break_rate = round(break_count / denominator, 4) if denominator else None
            return {
                "up_count": up_count,
                "down_count": down_count,
                "break_count": break_count,
                "break_rate": break_rate,
                "max_height": max_height,
                "rows": rows,
            }

        current_limit_stats = None
        previous_limit_stats = None
        limit_error = ""
        for index, trade_date in enumerate(recent_dates):
            try:
                result = _tushare_adapter.get_limit_list_d(trade_date=trade_date)
                if not result.get("ok"):
                    limit_error = result.get("error") or "limit_list_d 调用失败"
                    continue
                df = result.get("data")
                stats = calc_limit_stats(df)
                if not stats:
                    if not packet["trade_date"]:
                        packet["trade_date"] = trade_date
                    continue

                if current_limit_stats is None:
                    current_limit_stats = stats
                    packet["trade_date"] = trade_date
                    packet["limit_up_count"] = stats["up_count"]
                    packet["limit_down_count"] = stats["down_count"]
                    packet["break_limit_count"] = stats["break_count"]
                    packet["break_limit_rate"] = stats["break_rate"]
                    packet["max_consecutive_limit"] = stats["max_height"]
                    samples = []
                    for row in stats["rows"]:
                        value = normalize_limit_value(row)
                        height = _cn_float(row.get("limit_times"))
                        if value in {"U", "Z"} or (height is not None and height >= 2):
                            samples.append(
                                {
                                    "trade_date": row.get("trade_date") or trade_date,
                                    "ts_code": row.get("ts_code") or "",
                                    "name": row.get("name") or "",
                                    "limit_type": value or "暂无",
                                    "limit_times": row.get("limit_times") if row.get("limit_times") is not None else "暂无",
                                    "open_times": row.get("open_times") if row.get("open_times") is not None else "暂无",
                                    "fd_amount_yi": _cn_amount_to_yi(row.get("fd_amount")),
                                }
                            )
                    packet["recent_active_limit_samples"] = samples[:8]
                    add_verified("Tushare limit_list_d")
                elif index > 0:
                    previous_limit_stats = stats
                    break
            except Exception as e:
                limit_error = str(e)

        if current_limit_stats is None:
            add_missing("Tushare limit_list_d", limit_error or "最近交易日无返回")
            packet["trade_date"] = packet["trade_date"] or recent_dates[0]

        if current_limit_stats is not None and previous_limit_stats is None:
            for trade_date in recent_dates[1:]:
                try:
                    result = _tushare_adapter.get_limit_list_d(trade_date=trade_date)
                    if result.get("ok"):
                        previous_limit_stats = calc_limit_stats(result.get("data"))
                        if previous_limit_stats:
                            break
                except Exception:
                    continue

        trade_date_for_market = packet["trade_date"] or recent_dates[0]

        try:
            top_result = _tushare_adapter.get_top_list(trade_date=trade_date_for_market)
            if top_result.get("ok"):
                top_df = top_result.get("data")
                if top_df is not None and not top_df.empty:
                    top_rows = top_df.where(pd.notna(top_df), None).to_dict("records")
                    packet["dragon_tiger_activity"]["list_count"] = len(top_rows)
                    packet["dragon_tiger_activity"]["sample_rows"] = [
                        {
                            "trade_date": row.get("trade_date") or trade_date_for_market,
                            "ts_code": row.get("ts_code") or "",
                            "name": row.get("name") or "",
                            "reason": row.get("explain") or row.get("reason") or "",
                            "net_buy_yi": _cn_amount_to_yi(row.get("net_amount") if row.get("net_amount") is not None else row.get("net_buy")),
                        }
                        for row in top_rows[:8]
                    ]
                    add_verified("Tushare top_list")
                else:
                    add_missing("Tushare top_list", "最近交易日无龙虎榜返回")
            else:
                add_missing("Tushare top_list", top_result.get("error") or "调用失败")
        except Exception as e:
            add_missing("Tushare top_list", str(e))

        try:
            flow_result = _tushare_adapter.get_moneyflow(trade_date=trade_date_for_market)
            if flow_result.get("ok"):
                flow_df = flow_result.get("data")
                if flow_df is not None and not flow_df.empty:
                    flow_rows = flow_df.where(pd.notna(flow_df), None).to_dict("records")

                    def moneyflow_score(row):
                        value = _cn_float(row.get("net_mf_amount"))
                        if value is not None:
                            return value
                        large_buy = _cn_float(row.get("buy_lg_amount"))
                        large_sell = _cn_float(row.get("sell_lg_amount"))
                        extra_buy = _cn_float(row.get("buy_elg_amount"))
                        extra_sell = _cn_float(row.get("sell_elg_amount"))
                        if None not in [large_buy, large_sell, extra_buy, extra_sell]:
                            return (large_buy - large_sell) + (extra_buy - extra_sell)
                        return 0

                    def flow_sample(row):
                        return {
                            "trade_date": row.get("trade_date") or trade_date_for_market,
                            "ts_code": row.get("ts_code") or "",
                            "name": row.get("name") or "",
                            "net_mf_yi": _cn_wan_to_yi(moneyflow_score(row)),
                        }

                    scored_rows = sorted(flow_rows, key=moneyflow_score, reverse=True)
                    packet["moneyflow_samples"]["positive_samples"] = [
                        flow_sample(row) for row in scored_rows if moneyflow_score(row) > 0
                    ][:5]
                    packet["moneyflow_samples"]["negative_samples"] = [
                        flow_sample(row) for row in reversed(scored_rows) if moneyflow_score(row) < 0
                    ][:5]
                    add_verified("Tushare moneyflow")
                else:
                    add_missing("Tushare moneyflow", "最近交易日无资金流返回")
            else:
                add_missing("Tushare moneyflow", flow_result.get("error") or "调用失败")
        except Exception as e:
            add_missing("Tushare moneyflow", str(e))

        try:
            if hasattr(_tushare_adapter, "get_limit_cpt_list"):
                concept_result = _tushare_adapter.get_limit_cpt_list(trade_date=trade_date_for_market)
                if concept_result.get("ok"):
                    concept_df = concept_result.get("data")
                    if concept_df is not None and not concept_df.empty:
                        if "rank" in concept_df.columns:
                            try:
                                concept_df = concept_df.assign(_rank_sort=pd.to_numeric(concept_df["rank"], errors="coerce")).sort_values("_rank_sort")
                            except Exception:
                                pass
                        packet["concept_strength_top"] = [
                            {
                                "name": row.get("name") or row.get("ts_code") or "",
                                "up_nums": row.get("up_nums") if row.get("up_nums") is not None else "",
                                "cons_nums": row.get("cons_nums") if row.get("cons_nums") is not None else "",
                                "up_stat": row.get("up_stat") or "",
                                "rank": row.get("rank") if row.get("rank") is not None else "",
                                "pct_chg": row.get("pct_chg") if row.get("pct_chg") is not None else "",
                            }
                            for row in _cn_frame_records(concept_df, 5)
                        ]
                        if packet["concept_strength_top"]:
                            add_verified("Tushare limit_cpt_list")
                    else:
                        add_missing("Tushare limit_cpt_list", "最近交易日无概念强度返回")
                else:
                    add_missing("Tushare limit_cpt_list", concept_result.get("error") or "调用失败")
        except Exception as e:
            add_missing("Tushare limit_cpt_list", str(e))

        if current_limit_stats is None:
            return packet

        up_count = packet["limit_up_count"]
        down_count = packet["limit_down_count"]
        break_rate = packet["break_limit_rate"]
        max_height = packet["max_consecutive_limit"]
        prev_up = previous_limit_stats.get("up_count") if previous_limit_stats else None
        prev_down = previous_limit_stats.get("down_count") if previous_limit_stats else None
        prev_break_rate = previous_limit_stats.get("break_rate") if previous_limit_stats else None
        prev_height = previous_limit_stats.get("max_height") if previous_limit_stats else None

        high_break = break_rate is not None and break_rate >= 0.45
        low_break = break_rate is not None and break_rate <= 0.25
        adequate_limits = up_count >= 30
        strong_limits = up_count >= 50
        high_height = max_height is not None and max_height >= 3
        down_rising = (
            prev_down is not None and down_count > prev_down
        ) or down_count >= 10
        height_declining = (
            prev_height is not None and max_height is not None and max_height < prev_height
        )
        break_rising = (
            prev_break_rate is not None
            and break_rate is not None
            and break_rate > prev_break_rate
        )
        repairing = (
            prev_up is not None
            and prev_down is not None
            and prev_break_rate is not None
            and break_rate is not None
            and up_count > prev_up
            and down_count <= prev_down
            and break_rate < prev_break_rate
        )

        if strong_limits and low_break and high_height:
            packet["market_state"] = "高潮或强修复"
            packet["risk_switch"] = "适合进攻或轻仓试错"
        elif down_rising and high_break and (height_declining or max_height in [None, 0, 1]):
            packet["market_state"] = "退潮"
            packet["risk_switch"] = "适合防守观察"
        elif repairing:
            packet["market_state"] = "修复"
            packet["risk_switch"] = "适合轻仓试错"
        elif adequate_limits and high_break:
            packet["market_state"] = "分歧"
            packet["risk_switch"] = "适合轻仓试错"
        elif up_count == 0 and down_count == 0 and break_rate is None:
            packet["market_state"] = "暂无可验证数据"
            packet["risk_switch"] = "适合只观察不买"
        else:
            packet["market_state"] = "暂无可验证数据" if up_count == 0 else "分歧"
            packet["risk_switch"] = "适合防守观察"

        return packet

    def get_cn_limit_emotion_data(stock_code, current_price=None):
        """获取 A 股涨跌停边界与情绪数据：Tushare stk_limit / limit_list_d / limit_cpt_list。"""
        ts_code = _cn_ts_code(stock_code)
        updated_at = datetime.datetime.now().isoformat(timespec="seconds")
        base_message = "近5日未取得可验证涨跌停/情绪数据，可能为非交易日、数据尚未更新、接口权限不足或标的暂不覆盖。"
        base = {
            "available": False,
            "boundary_available": False,
            "records_available": False,
            "concept_available": False,
            "message": base_message,
            "record_message": "近5日未见该股涨跌停/炸板记录。",
            "source": "Tushare",
            "api": "stk_limit / limit_list_d / limit_cpt_list",
            "updated_at": updated_at,
            "error": "",
            "errors": [],
            "warning": "",
            "ts_code": ts_code,
            "latest_date": "",
            "up_limit": None,
            "down_limit": None,
            "pre_close": None,
            "current_price": _cn_float(current_price),
            "distance_to_up_pct": None,
            "distance_to_down_pct": None,
            "limit_records": [],
            "concept_top5": [],
            "flags": {
                "has_limit_up": False,
                "has_limit_down": False,
                "has_break_limit": False,
                "has_consecutive_limit": False,
            },
        }

        def classify_error(error):
            text = str(error or "")
            if any(keyword in text for keyword in ["权限", "积分", "permission", "没有访问", "抱歉", "token"]):
                return "Tushare 涨跌停/情绪接口暂不可用，可能需要相应积分或接口权限。"
            if any(keyword in text for keyword in ["Connection", "Network", "timed out", "NameResolution", "Max retries", "网络"]):
                return "涨跌停/情绪数据暂时获取失败，请稍后重试。"
            return base_message

        def remember_error(result):
            if not isinstance(result, dict):
                return
            error = result.get("error") or ""
            if error:
                base["error"] = error
                base["errors"].append(error)
                base["warning"] = classify_error(error)
                base["message"] = base["warning"]
            base["updated_at"] = result.get("updated_at") or base["updated_at"]

        def is_permission_error(result):
            if not isinstance(result, dict):
                return False
            text = " ".join(
                str(result.get(key) or "")
                for key in ["error", "message", "warning"]
            )
            return any(keyword.lower() in text.lower() for keyword in ["权限", "无接口访问权限", "permission", "积分", "没有访问", "抱歉", "token"])

        if _tushare_adapter is None:
            base["error"] = str(TUSHARE_ADAPTER_MODULE_ERROR)
            base["message"] = classify_error(base["error"])
            return base

        missing = [
            name for name in ["get_stk_limit", "get_limit_list_d", "get_limit_cpt_list"]
            if not hasattr(_tushare_adapter, name)
        ]
        if missing:
            base["error"] = f"tushare_adapter 未接入接口：{', '.join(missing)}"
            return base

        try:
            recent_dates = _cn_recent_trade_dates(10)[:5]
            if not recent_dates:
                return base

            for trade_date in recent_dates:
                limit_result = _tushare_adapter.get_stk_limit(ts_code=ts_code, trade_date=trade_date)
                if not limit_result.get("ok"):
                    remember_error(limit_result)
                    break

                limit_df = limit_result.get("data")
                if limit_df is None or limit_df.empty:
                    continue

                row = _cn_frame_records(limit_df, 1)[0]
                up_limit = _cn_float(row.get("up_limit"))
                down_limit = _cn_float(row.get("down_limit"))
                current = base.get("current_price")
                base.update(
                    {
                        "boundary_available": True,
                        "latest_date": row.get("trade_date") or trade_date,
                        "up_limit": up_limit,
                        "down_limit": down_limit,
                        "pre_close": _cn_float(row.get("pre_close")),
                        "updated_at": limit_result.get("updated_at") or base["updated_at"],
                    }
                )
                if current and current > 0 and up_limit is not None:
                    base["distance_to_up_pct"] = round((up_limit - current) / current * 100, 2)
                if current and current > 0 and down_limit is not None:
                    base["distance_to_down_pct"] = round((current - down_limit) / current * 100, 2)
                break

            start_date = min(recent_dates)
            end_date = max(recent_dates)
            records_result = _tushare_adapter.get_limit_list_d(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if records_result.get("ok"):
                records_df = records_result.get("data")
                if records_df is not None and not records_df.empty:
                    raw_records = sorted(
                        _cn_frame_records(records_df, 10),
                        key=lambda item: str(item.get("trade_date") or ""),
                        reverse=True,
                    )[:5]
                    records = []
                    for item in raw_records:
                        limit_value = str(item.get("limit") or item.get("limit_type") or "")
                        type_label = {
                            "U": "涨停",
                            "D": "跌停",
                            "Z": "炸板",
                        }.get(limit_value, limit_value or "未知")
                        limit_times = _cn_float(item.get("limit_times"))
                        base["flags"]["has_limit_up"] = base["flags"]["has_limit_up"] or limit_value == "U" or "涨停" in type_label
                        base["flags"]["has_limit_down"] = base["flags"]["has_limit_down"] or limit_value == "D" or "跌停" in type_label
                        base["flags"]["has_break_limit"] = base["flags"]["has_break_limit"] or limit_value == "Z" or "炸" in type_label
                        base["flags"]["has_consecutive_limit"] = base["flags"]["has_consecutive_limit"] or bool(limit_times and limit_times > 1)
                        records.append(
                            {
                                "日期": _cn_fmt_date(item.get("trade_date")),
                                "类型": type_label,
                                "首次封板": item.get("first_time") or "暂无",
                                "最后封板": item.get("last_time") or "暂无",
                                "开板次数": item.get("open_times") if item.get("open_times") is not None else "暂无",
                                "封单金额(亿)": _cn_amount_to_yi(item.get("fd_amount")),
                                "板上成交额(亿)": _cn_amount_to_yi(item.get("limit_amount")),
                                "连板统计": item.get("up_stat") or "",
                                "连板数": item.get("limit_times") if item.get("limit_times") is not None else "",
                            }
                        )
                    base["limit_records"] = records
                    base["records_available"] = bool(records)
            else:
                remember_error(records_result)

            if st.session_state.get("skip_limit_cpt_list"):
                skip_message = "limit_cpt_list 当前权限不足，已在本会话跳过重复请求。"
                base["warning"] = f"{base['warning']}；{skip_message}" if base.get("warning") else skip_message
                if not base.get("available"):
                    base["message"] = skip_message
            else:
                concept_dates = []
                if base.get("latest_date"):
                    concept_dates.append(base["latest_date"])
                concept_dates.extend([date for date in recent_dates if date not in concept_dates])
                for trade_date in concept_dates:
                    concept_result = _tushare_adapter.get_limit_cpt_list(trade_date=trade_date)
                    if not concept_result.get("ok"):
                        remember_error(concept_result)
                        if is_permission_error(concept_result):
                            st.session_state["skip_limit_cpt_list"] = True
                        break

                    concept_df = concept_result.get("data")
                    if concept_df is None or concept_df.empty:
                        continue
                    if "rank" in concept_df.columns:
                        try:
                            concept_df = concept_df.assign(_rank_sort=pd.to_numeric(concept_df["rank"], errors="coerce")).sort_values("_rank_sort")
                        except Exception:
                            pass
                    concepts = []
                    for item in _cn_frame_records(concept_df, 5):
                        concepts.append(
                            {
                                "概念": item.get("name") or item.get("ts_code") or "未知",
                                "涨停家数": item.get("up_nums") if item.get("up_nums") is not None else "暂无",
                                "连板家数": item.get("cons_nums") if item.get("cons_nums") is not None else "暂无",
                                "连板高度": item.get("up_stat") or "暂无",
                                "涨跌幅": item.get("pct_chg") if item.get("pct_chg") is not None else "暂无",
                                "排名": item.get("rank") if item.get("rank") is not None else "暂无",
                            }
                        )
                    base["concept_top5"] = concepts
                    base["concept_available"] = bool(concepts)
                    base["concept_date"] = trade_date
                    base["updated_at"] = concept_result.get("updated_at") or base["updated_at"]
                    break

            base["available"] = bool(base["boundary_available"] or base["records_available"] or base["concept_available"])
            if base["available"]:
                base["message"] = ""
            if not base["records_available"]:
                base["record_message"] = "近5日未见该股涨跌停/炸板记录。"
            return base
        except Exception as e:
            base["error"] = str(e)
            base["message"] = classify_error(base["error"])
            return base

    def format_cn_limit_emotion_context(limit_emotion_data):
        data = limit_emotion_data or {}
        if not data.get("available"):
            return "\n\n【A股涨跌停与情绪事实】\n暂无可验证涨跌停/情绪数据。"
        records = data.get("limit_records") or []
        concepts = data.get("concept_top5") or []
        return f"""

【A股涨跌停与情绪事实】
数据源：Tushare stk_limit / limit_list_d / limit_cpt_list
涨停价：{data.get('up_limit') if data.get('up_limit') is not None else '暂无'}
跌停价：{data.get('down_limit') if data.get('down_limit') is not None else '暂无'}
距离涨停：{data.get('distance_to_up_pct') if data.get('distance_to_up_pct') is not None else '暂无'}%
距离跌停：{data.get('distance_to_down_pct') if data.get('distance_to_down_pct') is not None else '暂无'}%
近5日涨跌停/炸板记录：{json.dumps(records, ensure_ascii=False, default=str) if records else '近5日未见该股涨跌停/炸板记录。'}
当日涨停概念强度Top5：{json.dumps(concepts, ensure_ascii=False, default=str) if concepts else '暂无'}
约束：没有真实接口返回时，不得编造连板、炸板、封单、题材强度。
"""

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

    def get_cn_moneyflow_data(stock_code):
        """获取 A 股个股资金流向：Tushare moneyflow，金额字段原始单位为万元。"""
        ts_code = _cn_ts_code(stock_code)
        base = {
            "available": False,
            "message": "近5日未取得可验证个股资金流向，可能为非交易日、数据尚未更新、接口权限不足或标的暂不覆盖。",
            "source": "Tushare",
            "api": "moneyflow",
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "error": "",
        }
        if _tushare_adapter is None:
            base["error"] = str(TUSHARE_ADAPTER_MODULE_ERROR)
            return base
        if not hasattr(_tushare_adapter, "get_moneyflow"):
            base["error"] = "tushare_adapter 未接入 moneyflow 接口"
            return base

        def net_amount(row, buy_key, sell_key):
            buy = _cn_float(row.get(buy_key))
            sell = _cn_float(row.get(sell_key))
            if buy is None or sell is None:
                return None
            return buy - sell

        def classify_error(error):
            text = str(error or "")
            if any(keyword in text for keyword in ["权限", "积分", "permission", "没有访问", "抱歉"]):
                return "Tushare moneyflow 暂不可用，可能需要等待积分权限生效或检查接口权限。"
            if any(keyword in text for keyword in ["Connection", "Network", "timed out", "NameResolution", "Max retries", "网络"]):
                return "资金流向数据暂时获取失败，请稍后重试。"
            return base["message"]

        try:
            rows = []
            for trade_date in _cn_recent_trade_dates(10)[:5]:
                flow_result = _tushare_adapter.get_moneyflow(ts_code=ts_code, trade_date=trade_date)
                base["updated_at"] = flow_result.get("updated_at") or base["updated_at"]
                if not flow_result.get("ok"):
                    base["error"] = flow_result.get("error") or ""
                    base["message"] = classify_error(base["error"])
                    return base

                flow_df = flow_result.get("data")
                if flow_df is None or flow_df.empty:
                    continue
                rows.extend(_cn_frame_records(flow_df, 5))

            if not rows:
                return base

            rows = sorted(rows, key=lambda item: str(item.get("trade_date") or ""), reverse=True)[:5]
            latest = rows[0]

            latest_small = net_amount(latest, "buy_sm_amount", "sell_sm_amount")
            latest_medium = net_amount(latest, "buy_md_amount", "sell_md_amount")
            latest_large = net_amount(latest, "buy_lg_amount", "sell_lg_amount")
            latest_extra_large = net_amount(latest, "buy_elg_amount", "sell_elg_amount")
            latest_main = None
            if latest_large is not None and latest_extra_large is not None:
                latest_main = latest_large + latest_extra_large

            five_day_main = 0
            valid_main_days = 0
            for row in rows:
                large = net_amount(row, "buy_lg_amount", "sell_lg_amount")
                extra_large = net_amount(row, "buy_elg_amount", "sell_elg_amount")
                if large is None or extra_large is None:
                    continue
                five_day_main += large + extra_large
                valid_main_days += 1

            if latest_main is None or valid_main_days == 0:
                base["message"] = "资金结构暂无法验证"
                return base

            if latest_main > 0 and five_day_main > 0:
                direction = "主力延续流入"
            elif latest_main < 0 and five_day_main < 0:
                direction = "主力延续流出"
            elif latest_main > 0 and five_day_main <= 0:
                direction = "短线资金回流"
            elif latest_main < 0 and five_day_main >= 0:
                direction = "短线资金转弱"
            else:
                direction = "资金方向分歧"

            values = [latest_large, latest_medium, latest_small]
            same_direction = all(value is not None and value > 0 for value in values) or all(value is not None and value < 0 for value in values)
            if latest_small is None:
                structure = "资金结构暂无法验证"
            elif latest_main > 0 and latest_small < 0:
                structure = "筹码偏向主力集中"
            elif latest_main < 0 and latest_small > 0:
                structure = "主力派发 / 散户承接迹象"
            elif same_direction:
                structure = "资金方向较一致"
            elif latest_main * latest_small < 0:
                structure = "资金结构分化，需结合量价确认"
            else:
                structure = "资金方向分歧"

            return {
                "available": True,
                "date": latest.get("trade_date"),
                "main_net_yi": _cn_wan_to_yi(latest_main),
                "large_net_yi": _cn_wan_to_yi(latest_large),
                "medium_net_yi": _cn_wan_to_yi(latest_medium),
                "small_net_yi": _cn_wan_to_yi(latest_small),
                "net_mf_yi": _cn_wan_to_yi(latest.get("net_mf_amount")),
                "five_day_main_net_yi": _cn_wan_to_yi(five_day_main),
                "direction": direction,
                "structure": structure,
                "source": "Tushare",
                "api": "moneyflow",
                "updated_at": base["updated_at"],
                "rows": rows,
                "message": "",
                "error": "",
            }
        except Exception as e:
            base["error"] = str(e)
            base["message"] = classify_error(base["error"])
            return base

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_cn_chip_radar_data(stock_code, current_price=None):
        """获取 A 股筹码/胜率雷达：Tushare cyq_perf 优先，cyq_chips 补充筹码密集区。"""
        ts_code = _cn_ts_code(stock_code)
        updated_at = datetime.datetime.now().isoformat(timespec="seconds")
        base_message = "暂未取得可验证筹码/胜率数据，可能为数据尚未更新、接口权限不足或标的暂不覆盖。"
        base = {
            "available": False,
            "source": "Tushare",
            "api": "cyq_perf/cyq_chips",
            "trade_date": "",
            "winner_rate": "",
            "weight_avg": "",
            "cost_5pct": "",
            "cost_50pct": "",
            "cost_95pct": "",
            "current_vs_weight_avg_pct": "",
            "chip_band_width": "",
            "chip_pressure_comment": "",
            "chip_structure_comment": "",
            "chips_top_areas": [],
            "message": base_message,
            "updated_at": updated_at,
            "error": "",
        }

        if _tushare_adapter is None:
            base["error"] = str(TUSHARE_ADAPTER_MODULE_ERROR)
            return base
        if not hasattr(_tushare_adapter, "get_cyq_perf"):
            base["error"] = "tushare_adapter 未接入 cyq_perf 接口"
            return base

        try:
            recent_dates = _cn_recent_trade_dates(10)[:5]
            if not recent_dates:
                return base

            perf_row = None
            perf_result = None
            for trade_date in recent_dates:
                result = _tushare_adapter.get_cyq_perf(ts_code=ts_code, trade_date=trade_date)
                perf_result = result
                base["updated_at"] = result.get("updated_at") or base["updated_at"]
                if not result.get("ok"):
                    base["error"] = result.get("error") or ""
                    base["message"] = base_message
                    return base
                perf_df = result.get("data")
                if perf_df is None or perf_df.empty:
                    continue
                perf_row = _cn_frame_records(perf_df, 1)[0]
                break

            if not perf_row:
                return base

            trade_date = perf_row.get("trade_date") or ""
            winner_rate = _cn_float(perf_row.get("winner_rate"))
            weight_avg = _cn_float(perf_row.get("weight_avg"))
            cost_5pct = _cn_float(perf_row.get("cost_5pct"))
            cost_50pct = _cn_float(perf_row.get("cost_50pct"))
            cost_95pct = _cn_float(perf_row.get("cost_95pct"))
            current = _cn_float(current_price)

            current_vs_weight_avg_pct = None
            if current is not None and weight_avg not in [None, 0]:
                current_vs_weight_avg_pct = round((current - weight_avg) / weight_avg * 100, 2)

            chip_band_width = None
            if cost_5pct is not None and cost_95pct is not None and cost_50pct not in [None, 0]:
                chip_band_width = round((cost_95pct - cost_5pct) / cost_50pct * 100, 2)

            if winner_rate is None:
                pressure_comment = "获利盘比例暂无法验证。"
            elif winner_rate >= 70:
                pressure_comment = "获利盘比例较高，兑现压力可能上升；不得据此直接卖出。"
            elif winner_rate <= 30:
                pressure_comment = "获利盘比例较低，套牢盘压力较重；不得据此直接买入。"
            else:
                pressure_comment = "获利盘与套牢盘压力相对均衡，需结合量价和情绪验证。"

            structure_parts = []
            if current_vs_weight_avg_pct is not None:
                if current_vs_weight_avg_pct >= 10:
                    structure_parts.append("当前价高于筹码中枢，需关注获利盘兑现压力。")
                elif current_vs_weight_avg_pct <= -10:
                    structure_parts.append("当前价低于筹码中枢，需关注上方套牢盘压力。")
                else:
                    structure_parts.append("当前价接近筹码中枢，筹码压力需结合成交量确认。")
            if chip_band_width is not None:
                if chip_band_width <= 15:
                    structure_parts.append("筹码成本带相对收敛，但筹码集中不是必涨。")
                elif chip_band_width >= 35:
                    structure_parts.append("筹码成本带较宽，筹码结构偏分散。")
                else:
                    structure_parts.append("筹码成本带宽度中性。")
            chip_structure_comment = " ".join(structure_parts) or "筹码结构暂无法验证。"

            chips_top_areas = []
            if hasattr(_tushare_adapter, "get_cyq_chips") and trade_date:
                chips_result = _tushare_adapter.get_cyq_chips(ts_code=ts_code, trade_date=trade_date)
                if isinstance(chips_result, dict):
                    base["updated_at"] = chips_result.get("updated_at") or base["updated_at"]
                    chips_df = chips_result.get("data") if chips_result.get("ok") else None
                    if chips_df is not None and not chips_df.empty:
                        chips_rows = _cn_frame_records(chips_df, 200)
                        chips_rows = sorted(chips_rows, key=lambda item: _cn_float(item.get("percent")) or 0, reverse=True)[:5]
                        chips_top_areas = [
                            {
                                "trade_date": item.get("trade_date") or trade_date,
                                "price": _cn_float(item.get("price")),
                                "percent": _cn_float(item.get("percent")),
                            }
                            for item in chips_rows
                        ]

            return {
                "available": True,
                "source": "Tushare",
                "api": "cyq_perf/cyq_chips",
                "trade_date": trade_date,
                "winner_rate": winner_rate,
                "weight_avg": weight_avg,
                "cost_5pct": cost_5pct,
                "cost_50pct": cost_50pct,
                "cost_95pct": cost_95pct,
                "current_vs_weight_avg_pct": current_vs_weight_avg_pct,
                "chip_band_width": chip_band_width,
                "chip_pressure_comment": pressure_comment,
                "chip_structure_comment": chip_structure_comment,
                "chips_top_areas": chips_top_areas,
                "message": "",
                "updated_at": (perf_result or {}).get("updated_at") or base["updated_at"],
                "error": "",
            }
        except Exception as e:
            base["error"] = str(e)
            return base

    @st.cache_data(ttl=600, show_spinner=False)
    def cached_cn_dragon_tiger_board(stock_code):
        return get_cn_dragon_tiger_board(stock_code)

    @st.cache_data(ttl=600, show_spinner=False)
    def cached_cn_margin_data(stock_code):
        return get_cn_margin_data(stock_code)

    @st.cache_data(ttl=600, show_spinner=False)
    def cached_cn_moneyflow_data(stock_code):
        return get_cn_moneyflow_data(stock_code)

    @st.cache_data(ttl=300, show_spinner=False)
    def cached_cn_limit_emotion_data(stock_code, current_price):
        return get_cn_limit_emotion_data(stock_code, current_price)

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_cn_hard_risk_radar_data(stock_code):
        """Build verified hard-risk radar data from Tushare with prompt-safe field whitelists."""
        ts_code = _cn_ts_code(_cn_stock_code_6(stock_code))
        today = datetime.date.today()
        updated_at = datetime.datetime.now().isoformat(timespec="seconds")

        def date_str(day):
            return day.strftime("%Y%m%d")

        def window(days, start_day=None, end_day=None):
            end = end_day or today
            start = start_day or (end - datetime.timedelta(days=days))
            return {
                "start_date": date_str(start),
                "end_date": date_str(end),
                "days": days,
            }

        ann_window = window(90)
        forecast_window = window(180)
        holder_window = window(180)
        unlock_window = window(90, start_day=today, end_day=today + datetime.timedelta(days=90))
        survey_window = window(90)

        def empty_section(api, win=None, message="暂无可验证数据"):
            return {
                "available": False,
                "source": "Tushare",
                "api": api,
                "window": win or {},
                "rows": [],
                "summary": "",
                "risk_flags": [],
                "message": message,
                "error": "",
                "updated_at": updated_at,
            }

        packet = {
            "available": False,
            "announcements": empty_section("anns_d", ann_window),
            "earnings_forecast": empty_section("forecast", forecast_window),
            "holder_reduction": empty_section("stk_holdertrade", holder_window),
            "share_unlock": empty_section("share_float", unlock_window),
            "pledge": empty_section("pledge_stat/pledge_detail", {}),
            "institution_surveys": empty_section("stk_surv", survey_window),
            "risk_flags": [],
            "missing_items": [],
            "updated_at": updated_at,
        }

        def add_missing(api, reason):
            text = f"{api}: {reason or '暂无可验证数据'}"
            if text not in packet["missing_items"]:
                packet["missing_items"].append(text)

        def set_result(section_name, section, result=None):
            if isinstance(result, dict):
                section["updated_at"] = result.get("updated_at") or section.get("updated_at") or updated_at
                section["error"] = result.get("error") or ""
            section["available"] = bool(section.get("rows"))
            if section["available"]:
                section["message"] = ""
            else:
                section["message"] = section.get("message") or "暂无可验证数据"
                add_missing(section.get("api", section_name), section.get("error") or section["message"])
            packet[section_name] = section

        def data_frame(result):
            if not isinstance(result, dict) or not result.get("ok"):
                return None
            df = result.get("data")
            if df is None or df.empty:
                return None
            return df

        def rows_from_result(result, limit=5, sort_key=None, reverse=True):
            df = data_frame(result)
            if df is None:
                return []
            rows = df.where(pd.notna(df), None).to_dict("records")
            if sort_key:
                rows = sorted(rows, key=lambda item: str(item.get(sort_key) or ""), reverse=reverse)
            return rows[:limit]

        def has_api(name):
            return _tushare_adapter is not None and hasattr(_tushare_adapter, name)

        def is_parameter_error(result):
            text = str((result or {}).get("error") or "")
            return any(keyword in text for keyword in ["参数", "trade_type", "字段", "unexpected", "got an unexpected"])

        if _tushare_adapter is None:
            reason = str(TUSHARE_ADAPTER_MODULE_ERROR) or "tushare_adapter 不可用"
            for name, section in list(packet.items()):
                if isinstance(section, dict) and section.get("source") == "Tushare":
                    section["error"] = reason
                    section["message"] = "Tushare 适配层不可用，暂无结构化硬风险。"
                    packet[name] = section
            packet["missing_items"].append(reason)
            return packet

        # 公告风险：标题只能作为线索，不当作事实结论。
        section = empty_section("anns_d", ann_window)
        if not has_api("get_anns_d"):
            section["error"] = "tushare_adapter 未接入 anns_d 接口"
            set_result("announcements", section)
        else:
            result = _tushare_adapter.get_anns_d(
                ts_code=ts_code,
                start_date=ann_window["start_date"],
                end_date=ann_window["end_date"],
            )
            rows = []
            risk_keywords = ["处罚", "问询", "监管", "诉讼", "仲裁", "立案", "调查", "退市", "风险提示", "担保", "冻结", "减持", "质押", "解禁", "亏损", "修正"]
            for item in rows_from_result(result, limit=5, sort_key="ann_date"):
                title = str(item.get("title") or "")
                rows.append(
                    {
                        "ann_date": item.get("ann_date") or "",
                        "title": title,
                        "url": item.get("url") or "",
                        "rec_time": item.get("rec_time") or "",
                    }
                )
                matched = [keyword for keyword in risk_keywords if keyword in title]
                if matched:
                    section["risk_flags"].append(f"公告标题线索涉及：{','.join(matched[:3])}")
            section["rows"] = rows
            if rows:
                section["summary"] = f"近90天取得公告标题 {len(rows)} 条；标题仅作公告线索，不能直接下事实结论。"
            set_result("announcements", section, result)

        # 业绩预告风险：只记录预告类型和区间，不当作确定业绩。
        section = empty_section("forecast", forecast_window)
        if not has_api("get_forecast"):
            section["error"] = "tushare_adapter 未接入 forecast 接口"
            set_result("earnings_forecast", section)
        else:
            result = _tushare_adapter.get_forecast(
                ts_code=ts_code,
                start_date=forecast_window["start_date"],
                end_date=forecast_window["end_date"],
            )
            rows = []
            for item in rows_from_result(result, limit=5, sort_key="ann_date"):
                forecast_type = str(item.get("type") or "")
                p_min = _cn_float(item.get("p_change_min"))
                p_max = _cn_float(item.get("p_change_max"))
                rows.append(
                    {
                        "ann_date": item.get("ann_date") or "",
                        "end_date": item.get("end_date") or "",
                        "type": forecast_type,
                        "p_change_min": p_min,
                        "p_change_max": p_max,
                        "net_profit_min": _cn_float(item.get("net_profit_min")),
                        "net_profit_max": _cn_float(item.get("net_profit_max")),
                        "summary": item.get("summary") or "",
                        "change_reason": item.get("change_reason") or "",
                    }
                )
                if forecast_type in ["预减", "首亏", "续亏", "略减"] or (p_max is not None and p_max < 0):
                    section["risk_flags"].append(f"业绩预告偏负面：{forecast_type or '变动区间为负'}")
            section["rows"] = rows
            if rows:
                section["summary"] = f"近180天取得业绩预告 {len(rows)} 条；盈利预测不是业绩确定。"
            set_result("earnings_forecast", section, result)

        # 股东减持风险：优先 DE，参数不支持时全取后过滤。
        section = empty_section("stk_holdertrade", holder_window)
        if not has_api("get_stk_holdertrade"):
            section["error"] = "tushare_adapter 未接入 stk_holdertrade 接口"
            set_result("holder_reduction", section)
        else:
            result = _tushare_adapter.get_stk_holdertrade(
                ts_code=ts_code,
                start_date=holder_window["start_date"],
                end_date=holder_window["end_date"],
                trade_type="DE",
            )
            if not result.get("ok") and is_parameter_error(result):
                result = _tushare_adapter.get_stk_holdertrade(
                    ts_code=ts_code,
                    start_date=holder_window["start_date"],
                    end_date=holder_window["end_date"],
                )
                raw_rows = [
                    item for item in rows_from_result(result, limit=30, sort_key="ann_date")
                    if str(item.get("in_de") or "").upper() == "DE"
                ][:5]
            else:
                raw_rows = rows_from_result(result, limit=5, sort_key="ann_date")
            section["rows"] = [
                {
                    "ann_date": item.get("ann_date") or "",
                    "holder_name": item.get("holder_name") or "",
                    "holder_type": item.get("holder_type") or "",
                    "in_de": item.get("in_de") or "",
                    "change_vol": _cn_float(item.get("change_vol")),
                    "change_ratio": _cn_float(item.get("change_ratio")),
                    "avg_price": _cn_float(item.get("avg_price")),
                    "begin_date": item.get("begin_date") or "",
                    "close_date": item.get("close_date") or "",
                }
                for item in raw_rows
            ]
            if section["rows"]:
                section["summary"] = f"近180天取得股东减持记录 {len(section['rows'])} 条。"
                section["risk_flags"].append("存在股东减持记录")
            set_result("holder_reduction", section, result)

        # 解禁风险：未来90天按 float_date 窗口。
        section = empty_section("share_float", unlock_window)
        if not has_api("get_share_float"):
            section["error"] = "tushare_adapter 未接入 share_float 接口"
            set_result("share_unlock", section)
        else:
            result = _tushare_adapter.get_share_float(
                ts_code=ts_code,
                start_date=unlock_window["start_date"],
                end_date=unlock_window["end_date"],
            )
            rows = []
            for item in rows_from_result(result, limit=5, sort_key="float_date", reverse=False):
                ratio = _cn_float(item.get("float_ratio"))
                rows.append(
                    {
                        "float_date": item.get("float_date") or "",
                        "float_share": _cn_float(item.get("float_share")),
                        "float_ratio": ratio,
                        "holder_name": item.get("holder_name") or "",
                        "share_type": item.get("share_type") or "",
                    }
                )
                if ratio is not None and ratio >= 5:
                    section["risk_flags"].append(f"未来解禁比例较高：{ratio}%")
            section["rows"] = rows
            if rows:
                section["summary"] = f"未来90天取得限售股解禁记录 {len(rows)} 条。"
            set_result("share_unlock", section, result)

        # 股权质押风险：统计取最近一期，明细取最近若干条。
        section = empty_section("pledge_stat/pledge_detail", {})
        stat_result = None
        detail_result = None
        if not has_api("get_pledge_stat") and not has_api("get_pledge_detail"):
            section["error"] = "tushare_adapter 未接入 pledge_stat / pledge_detail 接口"
            set_result("pledge", section)
        else:
            stat_rows = []
            detail_rows = []
            if has_api("get_pledge_stat"):
                stat_result = _tushare_adapter.get_pledge_stat(ts_code=ts_code)
                for item in rows_from_result(stat_result, limit=1, sort_key="end_date"):
                    stat_rows.append(
                        {
                            "end_date": item.get("end_date") or "",
                            "pledge_ratio": _cn_float(item.get("pledge_ratio")),
                            "pledge_count": item.get("pledge_count") if item.get("pledge_count") is not None else "",
                            "unrest_pledge": _cn_float(item.get("unrest_pledge")),
                        }
                    )
                    ratio = _cn_float(item.get("pledge_ratio"))
                    if ratio is not None and ratio >= 30:
                        section["risk_flags"].append(f"最近一期质押比例较高：{ratio}%")
            if has_api("get_pledge_detail"):
                detail_result = _tushare_adapter.get_pledge_detail(ts_code=ts_code)
                raw_detail = rows_from_result(detail_result, limit=20, sort_key="ann_date")
                unreleased = [item for item in raw_detail if str(item.get("is_release") or "").strip() in ["0", "否", "N", "n", ""]]
                detail_limit = 4 if stat_rows else 5
                selected_detail = (unreleased if unreleased else raw_detail)[:detail_limit]
                detail_rows = [
                    {
                        "holder_name": item.get("holder_name") or "",
                        "pledge_amount": _cn_float(item.get("pledge_amount")),
                        "p_total_ratio": _cn_float(item.get("p_total_ratio")),
                        "h_total_ratio": _cn_float(item.get("h_total_ratio")),
                        "is_release": item.get("is_release") if item.get("is_release") is not None else "",
                    }
                    for item in selected_detail
                ]
            section["rows"] = stat_rows + detail_rows
            if section["rows"]:
                section["summary"] = f"取得股权质押统计/明细 {len(section['rows'])} 条，优先展示最近一期和未解押记录。"
            if isinstance(stat_result, dict) and stat_result.get("error"):
                section["error"] = stat_result.get("error") or ""
            if not section["error"] and isinstance(detail_result, dict) and detail_result.get("error"):
                section["error"] = detail_result.get("error") or ""
            section["updated_at"] = max(
                [
                    str(updated_at),
                    str((stat_result or {}).get("updated_at") or ""),
                    str((detail_result or {}).get("updated_at") or ""),
                ]
            )
            set_result("pledge", section, detail_result or stat_result)

        # 机构调研验证：不拉 content 长文本，不当作买入信号。
        section = empty_section("stk_surv", survey_window)
        if not has_api("get_stk_surv"):
            section["error"] = "tushare_adapter 未接入 stk_surv 接口"
            set_result("institution_surveys", section)
        else:
            result = _tushare_adapter.get_stk_surv(
                ts_code=ts_code,
                start_date=survey_window["start_date"],
                end_date=survey_window["end_date"],
            )
            section["rows"] = [
                {
                    "surv_date": item.get("surv_date") or "",
                    "rece_org": item.get("rece_org") or "",
                    "org_type": item.get("org_type") or "",
                    "rece_mode": item.get("rece_mode") or "",
                    "fund_visitors": item.get("fund_visitors") or "",
                    "rece_place": item.get("rece_place") or "",
                    "comp_rece": item.get("comp_rece") or "",
                }
                for item in rows_from_result(result, limit=5, sort_key="surv_date")
            ]
            if section["rows"]:
                section["summary"] = f"近90天取得机构调研记录 {len(section['rows'])} 条；调研记录只作关注度/验证线索，不是买入信号。"
                section["risk_flags"].append("存在机构调研记录，需用于问题验证而非买入判断")
            set_result("institution_surveys", section, result)

        packet["risk_flags"] = []
        for section_name in [
            "announcements",
            "earnings_forecast",
            "holder_reduction",
            "share_unlock",
            "pledge",
            "institution_surveys",
        ]:
            packet["risk_flags"].extend(packet.get(section_name, {}).get("risk_flags") or [])
        packet["available"] = any(
            bool((packet.get(section_name) or {}).get("available"))
            for section_name in [
                "announcements",
                "earnings_forecast",
                "holder_reduction",
                "share_unlock",
                "pledge",
                "institution_surveys",
            ]
        )
        packet["updated_at"] = max(
            [
                str(updated_at),
                *[
                    str((packet.get(section_name) or {}).get("updated_at") or "")
                    for section_name in [
                        "announcements",
                        "earnings_forecast",
                        "holder_reduction",
                        "share_unlock",
                        "pledge",
                        "institution_surveys",
                    ]
                ],
            ]
        )
        return packet

    def build_a_share_professional_fact_packet(
        stock_code,
        stock_name,
        current_price,
        position_profile=None,
        trade_instruction=None,
        dragon_data=None,
        margin_data=None,
        moneyflow_data=None,
        limit_emotion_data=None,
        chip_radar_data=None,
        tushare_verified_source=None,
        market_style_fact_packet=None,
        verified_technical_facts=None,
    ):
        """Build a prompt-safe A-share professional fact bundle from cached data."""
        stock_code_6 = _cn_stock_code_6(stock_code)
        verified_technical_facts = verified_technical_facts or build_verified_technical_fact_packet({})

        try:
            if dragon_data is None:
                dragon_data = cached_cn_dragon_tiger_board(stock_code_6)
            if margin_data is None:
                margin_data = cached_cn_margin_data(stock_code_6)
            if moneyflow_data is None:
                moneyflow_data = cached_cn_moneyflow_data(stock_code_6)
            if limit_emotion_data is None:
                limit_emotion_data = cached_cn_limit_emotion_data(stock_code_6, current_price=current_price)
            if chip_radar_data is None:
                chip_radar_data = get_cn_chip_radar_data(stock_code_6, current_price=current_price)
        except Exception as fact_error:
            return {
                "available": False,
                "stock_code": stock_code_6,
                "moneyflow": {},
                "dragon_tiger": {},
                "margin": {},
                "limit_emotion": {},
                "chip_radar": {},
                "verified_technical_facts": verified_technical_facts,
                "data_source": "Tushare + yfinance technical",
                "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "missing_items": [f"A股专业事实包构造失败：{type(fact_error).__name__}"],
            }

        base_packet = build_next_day_plan_fact_packet(
            stock_code_6,
            stock_name,
            current_price,
            position_profile or {},
            trade_instruction or {},
            dragon_data or {},
            margin_data or {},
            moneyflow_data or {},
            limit_emotion_data or {},
            chip_radar_data=chip_radar_data or {},
            tushare_verified_source=tushare_verified_source or {},
            market_style_fact_packet=market_style_fact_packet or {},
            verified_technical_facts=verified_technical_facts,
        )

        def updated_at_of(*items):
            values = []
            for item in items:
                if isinstance(item, dict) and item.get("updated_at"):
                    values.append(str(item.get("updated_at")))
            values.append(str(base_packet.get("updated_at") or datetime.datetime.now().isoformat(timespec="seconds")))
            return max(values)

        moneyflow_fact = {
            **(base_packet.get("moneyflow") or {}),
            "source": "Tushare",
            "api": "moneyflow",
            "date": (moneyflow_data or {}).get("date", ""),
            "main_net_yi": (moneyflow_data or {}).get("main_net_yi", ""),
            "large_net_yi": (moneyflow_data or {}).get("large_net_yi", ""),
            "medium_net_yi": (moneyflow_data or {}).get("medium_net_yi", ""),
            "small_net_yi": (moneyflow_data or {}).get("small_net_yi", ""),
            "five_day_main_net_yi": (moneyflow_data or {}).get("five_day_main_net_yi", ""),
            "updated_at": (moneyflow_data or {}).get("updated_at", ""),
        }
        dragon_fact = {
            **(base_packet.get("dragon_tiger") or {}),
            "source": "Tushare",
            "api": "top_list/top_inst",
            "latest_date": (dragon_data or {}).get("latest_date", ""),
            "close": (dragon_data or {}).get("close", ""),
            "pct_change": (dragon_data or {}).get("pct_change", ""),
            "buy_amount_yi": (dragon_data or {}).get("buy_amount_yi", ""),
            "sell_amount_yi": (dragon_data or {}).get("sell_amount_yi", ""),
            "net_buy_amount_yi": (dragon_data or {}).get("net_buy_amount_yi", ""),
            "inst_summary": (dragon_data or {}).get("inst_summary", ""),
            "updated_at": (dragon_data or {}).get("updated_at", ""),
        }
        margin_fact = {
            **(base_packet.get("margin") or {}),
            "source": "Tushare",
            "api": "margin_detail",
            "date": (margin_data or {}).get("date", ""),
            "updated_at": (margin_data or {}).get("updated_at", ""),
        }
        limit_fact = {
            **(base_packet.get("limit_emotion") or {}),
            "source": "Tushare",
            "api": "stk_limit / limit_list_d / limit_cpt_list",
            "latest_date": (limit_emotion_data or {}).get("latest_date", ""),
            "concept_date": (limit_emotion_data or {}).get("concept_date", ""),
            "up_limit": (limit_emotion_data or {}).get("up_limit", ""),
            "down_limit": (limit_emotion_data or {}).get("down_limit", ""),
            "distance_to_up_pct": (limit_emotion_data or {}).get("distance_to_up_pct", ""),
            "distance_to_down_pct": (limit_emotion_data or {}).get("distance_to_down_pct", ""),
            "boundary_available": bool((limit_emotion_data or {}).get("boundary_available")),
            "concept_available": bool((limit_emotion_data or {}).get("concept_available")),
            "updated_at": (limit_emotion_data or {}).get("updated_at", ""),
        }
        chip_fact = {
            **(base_packet.get("chip_radar") or {}),
            "source": "Tushare",
            "api": "cyq_perf/cyq_chips",
            "updated_at": (chip_radar_data or {}).get("updated_at", ""),
        }
        missing_items = list(base_packet.get("data_missing_items") or [])
        available = any(
            bool(section.get("available"))
            for section in [moneyflow_fact, dragon_fact, margin_fact, limit_fact, chip_fact]
            if isinstance(section, dict)
        ) or bool((verified_technical_facts or {}).get("available"))
        result_packet = {
            "available": available,
            "stock_code": stock_code_6,
            "moneyflow": moneyflow_fact,
            "dragon_tiger": dragon_fact,
            "margin": margin_fact,
            "limit_emotion": limit_fact,
            "chip_radar": chip_fact,
            "verified_technical_facts": verified_technical_facts,
            "data_source": "Tushare + yfinance technical",
            "updated_at": updated_at_of(
                moneyflow_data,
                dragon_data,
                margin_data,
                limit_emotion_data,
                chip_radar_data,
            ),
            "missing_items": missing_items,
        }
        result_packet["data_capability"] = data_capability.build_a_share_professional_capability_packet(
            result_packet,
            checked_at=result_packet["updated_at"],
        )
        return result_packet

    def format_a_share_professional_facts_for_prompt(a_share_professional_facts):
        facts = a_share_professional_facts or {}
        if not facts:
            return "\n\n【已验证A股专业事实】\n暂无可验证A股专业事实。"
        compact = {
            "available": bool(facts.get("available")),
            "stock_code": facts.get("stock_code", ""),
            "个股资金流": facts.get("moneyflow") or {},
            "龙虎榜": facts.get("dragon_tiger") or {},
            "融资融券": facts.get("margin") or {},
            "涨跌停/概念强度": facts.get("limit_emotion") or {},
            "筹码/胜率": facts.get("chip_radar") or {},
            "技术事实": facts.get("verified_technical_facts") or {},
            "缺失项": facts.get("missing_items") or [],
            "data_source": facts.get("data_source", "Tushare + yfinance technical"),
            "updated_at": facts.get("updated_at", ""),
        }
        return f"""

【已验证A股专业事实】
{json.dumps(compact, ensure_ascii=False, indent=2, default=str)}

【A股专业事实硬规则】
1. A股专业事实只能来自 Tushare / verified_technical_facts。
2. Supabase、brain_memory、manager_rules、processed_sources 只能作为投喂资料观点 / 历史假设 / 待验证线索。
3. 没有 moneyflow 真实数据，不得写主力流入/流出。
4. 没有 top_list/top_inst，不得写机构席位。
5. 没有 cyq_perf/cyq_chips，不得写筹码压力。
6. 筹码集中不是必涨。
7. 获利盘高不是必卖。
8. 融资融券只能代表杠杆资金，不等于主力资金。
9. limit_cpt_list 只能代表概念热度，不是追涨理由。
10. 不得写必买、必卖、满仓、梭哈。
"""

    @st.cache_data(ttl=600, show_spinner=False)
    def build_tianyan_risk_fact_packet(stock_code, stock_name, current_price=None):
        """Build Tianyan risk radar facts from existing cached A-share professional facts."""
        updated_at = datetime.datetime.now().isoformat(timespec="seconds")
        packet = {
            "stock": {
                "ts_code": str(stock_code or ""),
                "name": str(stock_name or ""),
                "current_price": "" if current_price is None else current_price,
            },
            "verified_trading_structure_risks": {
                "moneyflow": {},
                "dragon_tiger": {},
                "margin": {},
                "limit_emotion": {},
            },
            "verified_chip_risks": {
                "chip_radar": {},
            },
            "verified_emotion_risks": {
                "limit_emotion": {},
                "concept_strength": {},
            },
            "verified_hard_risks": {
                "announcements": {},
                "free_announcement_radar": {},
                "earnings_forecast": {},
                "holder_reduction": {},
                "share_unlock": {},
                "pledge": {},
                "institution_surveys": {},
                "policy": {
                    "ann_titles_are_clues_not_conclusions": True,
                    "institution_surveys_are_validation_not_buy_signal": True,
                },
            },
            "sentiment_and_unverified_clues": {
                "market_news": [],
                "processed_sources": [],
                "yfinance_news": [],
                "news_digest": {},
                "note": "processed_sources / brain_memory / manager_rules / news_digest 只能作为待验证线索",
            },
            "missing_items": [],
            "data_source_policy": {
                "hard_fact_sources": ["Tushare"],
                "announcement_summary_sources": ["stock_reports.announcement_summary parsed_pdf"],
                "news_clue_sources": [
                    "Supabase market_news title/url only",
                    "stock_reports.news_digest claims/clues/evidence only",
                    "yfinance.news title only",
                ],
                "unverified_sources": ["processed_sources", "brain_memory", "manager_rules", "news_digest"],
            },
            "updated_at": updated_at,
        }

        try:
            normalized_code, detected_market_type, _, _ = identify_market(str(stock_code or ""))
        except Exception:
            normalized_code = str(stock_code or "")
            detected_market_type = ""

        if not is_a_share_market(detected_market_type):
            packet["missing_items"].append("非A股标的：本阶段不调用 Tushare 结构化风控事实。")
            packet["verified_hard_risks"]["missing_items"] = ["非A股标的：暂无结构化硬风险雷达。"]
            return packet

        stock_code_6 = _cn_stock_code_6(normalized_code or stock_code)
        packet["stock"]["ts_code"] = _cn_ts_code(stock_code_6)

        try:
            hard_risks = get_cn_hard_risk_radar_data(stock_code_6) or {}
            packet["verified_hard_risks"].update(
                {
                    "announcements": hard_risks.get("announcements") or {},
                    "free_announcement_radar": load_recent_announcement_summaries(stock_code_6, days=14, limit=6),
                    "earnings_forecast": hard_risks.get("earnings_forecast") or {},
                    "holder_reduction": hard_risks.get("holder_reduction") or {},
                    "share_unlock": hard_risks.get("share_unlock") or {},
                    "pledge": hard_risks.get("pledge") or {},
                    "institution_surveys": hard_risks.get("institution_surveys") or {},
                    "available": bool(hard_risks.get("available")),
                    "risk_flags": hard_risks.get("risk_flags") or [],
                    "missing_items": hard_risks.get("missing_items") or [],
                    "updated_at": hard_risks.get("updated_at") or updated_at,
                    "policy": {
                        "ann_titles_are_clues_not_conclusions": True,
                        "institution_surveys_are_validation_not_buy_signal": True,
                    },
                }
            )
            packet["sentiment_and_unverified_clues"]["news_digest"] = load_recent_news_digests(stock_code_6, days=4, limit=5)
        except Exception as exc:
            packet["verified_hard_risks"]["missing_items"] = [f"硬风险雷达构造失败：{type(exc).__name__}"]

        try:
            facts = build_a_share_professional_fact_packet(
                stock_code_6,
                stock_name,
                current_price,
            ) or {}
        except Exception as exc:
            packet["missing_items"].append(f"A股专业事实包构造失败：{type(exc).__name__}")
            return packet

        moneyflow = facts.get("moneyflow") or {}
        dragon_tiger = facts.get("dragon_tiger") or {}
        margin = facts.get("margin") or {}
        limit_emotion = facts.get("limit_emotion") or {}
        chip_radar = facts.get("chip_radar") or {}

        packet["verified_trading_structure_risks"] = {
            "moneyflow": moneyflow,
            "dragon_tiger": dragon_tiger,
            "margin": margin,
            "limit_emotion": limit_emotion,
        }
        packet["verified_chip_risks"] = {
            "chip_radar": chip_radar,
        }
        packet["verified_emotion_risks"] = {
            "limit_emotion": limit_emotion,
            "concept_strength": {
                "available": bool(limit_emotion.get("concept_available")),
                "source": "Tushare",
                "api": "limit_cpt_list",
                "date": limit_emotion.get("concept_date") or limit_emotion.get("latest_date") or "",
                "top5": limit_emotion.get("concept_top5") or [],
                "note": "limit_cpt_list 只能代表概念热度，不是追涨理由。",
            },
        }
        packet["missing_items"] = list(facts.get("missing_items") or [])
        packet["missing_items"].extend(packet.get("verified_hard_risks", {}).get("missing_items") or [])
        packet["updated_at"] = max(
            str(facts.get("updated_at") or updated_at),
            str(packet.get("verified_hard_risks", {}).get("updated_at") or updated_at),
        )
        return packet

    def build_hard_risk_sentiment_rows(tianyan_packet, limit=8):
        """Expose announcement and reduction risks inside the sentiment view."""
        packet = tianyan_packet if isinstance(tianyan_packet, dict) else {}
        hard = packet.get("verified_hard_risks") or {}
        rows = []
        seen = set()

        def add_row(*, title, source, date="", url="", risk_tag="公告/硬风险", sentiment="利空/待验证", summary=""):
            title_text = str(title or "").strip()
            if not title_text:
                return
            key = (title_text, str(url or "").strip(), str(date or "").strip(), source)
            if key in seen:
                return
            seen.add(key)
            rows.append(
                {
                    "relevance_score": 100,
                    "market_filter": "A_SHARE_HARD_RISK",
                    "filter_reason": "公告/减持硬风险自动合并到近48小时视图",
                    "keyword": "公告/减持",
                    "title": title_text,
                    "sentiment": sentiment,
                    "risk_tag": risk_tag,
                    "created_at": str(date or packet.get("updated_at") or "").strip(),
                    "url": str(url or "").strip(),
                    "source": source,
                    "summary": str(summary or "").strip(),
                    "verification_status": "公告/交易所/Tushare 硬风险线索，优先于软舆情",
                    "fact_boundary": "公告标题/摘要是风险线索；交易前仍需复核公告原文。",
                }
            )

        for section_name, source_label in [
            ("announcements", "Tushare anns_d"),
            ("free_announcement_radar", "公告雷达"),
        ]:
            section = hard.get(section_name) or {}
            for item in (section.get("rows") or [])[:limit]:
                title = item.get("title") or item.get("message") or item.get("summary")
                joined = " ".join(str(value or "") for value in [title, item.get("ai_summary"), item.get("risk_tags")])
                risk_tag = "公告风险"
                sentiment = "利空/待验证" if any(word in joined for word in ["减持", "处罚", "问询", "诉讼", "立案", "质押", "解禁", "亏损"]) else "中性/待验证"
                add_row(
                    title=title,
                    source=source_label,
                    date=item.get("ann_date") or item.get("published_at") or item.get("updated_at"),
                    url=item.get("pdf_url") or item.get("url"),
                    risk_tag=risk_tag,
                    sentiment=sentiment,
                    summary=item.get("ai_summary") or item.get("summary") or "",
                )

        holder_section = hard.get("holder_reduction") or {}
        for item in (holder_section.get("rows") or [])[:limit]:
            holder = str(item.get("holder_name") or item.get("shareholder") or "股东").strip()
            ratio = item.get("change_ratio")
            ratio_text = f"，变动比例 {ratio}%" if ratio not in [None, ""] else ""
            title = f"股东减持记录：{holder}{ratio_text}"
            add_row(
                title=title,
                source="Tushare stk_holdertrade",
                date=item.get("ann_date") or item.get("begin_date") or item.get("close_date"),
                risk_tag="股东减持",
                sentiment="利空/待验证",
                summary=item.get("change_reason") or "",
            )

        for flag in hard.get("risk_flags") or []:
            add_row(
                title=str(flag),
                source="硬风险汇总",
                date=hard.get("updated_at") or packet.get("updated_at"),
                risk_tag="硬风险",
                sentiment="利空/待验证",
            )

        return rows[: max(1, int(limit or 8))]

    def merge_sentiment_with_hard_risk_rows(news_rows, tianyan_packet, limit=12):
        merged = []
        seen = set()
        for item in build_hard_risk_sentiment_rows(tianyan_packet, limit=6):
            key = (item.get("title"), item.get("url"), item.get("created_at"))
            if key not in seen:
                seen.add(key)
                merged.append(item)
        for item in news_rows or []:
            if not isinstance(item, dict):
                continue
            key = (item.get("title"), item.get("url"), item.get("created_at"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged[: max(1, int(limit or 12))]

    def build_next_day_plan_fact_packet(
        stock_code,
        stock_name,
        current_price,
        position_profile,
        trade_instruction,
        dragon_data,
        margin_data,
        moneyflow_data,
        limit_emotion_data,
        chip_radar_data=None,
        tushare_verified_source=None,
        market_style_fact_packet=None,
        verified_technical_facts=None,
    ):
        """Build a verified fact packet for the next-day observation plan."""
        return legacy_a_share_prompt_packet_service.build_next_day_plan_fact_packet(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=current_price,
            position_profile=position_profile,
            trade_instruction=trade_instruction,
            dragon_data=dragon_data,
            margin_data=margin_data,
            moneyflow_data=moneyflow_data,
            limit_emotion_data=limit_emotion_data,
            chip_radar_data=chip_radar_data,
            tushare_verified_source=tushare_verified_source,
            market_style_fact_packet=market_style_fact_packet,
            verified_technical_facts=verified_technical_facts or build_verified_technical_fact_packet({}),
        )

    def build_single_stock_war_room_fact_packet(
        stock_code,
        stock_name,
        current_price,
        position_profile,
        trade_instruction,
        dragon_data,
        margin_data,
        moneyflow_data,
        limit_emotion_data,
        chip_radar_data=None,
        tushare_verified_source=None,
        market_style_fact_packet=None,
        verified_technical_facts=None,
    ):
        """Build the single-stock war room packet from already-loaded page data."""
        watch_targets = st.session_state.get("single_stock_watch_targets", [])
        if not isinstance(watch_targets, list):
            watch_targets = []
        return legacy_a_share_prompt_packet_service.build_single_stock_war_room_fact_packet(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=current_price,
            position_profile=position_profile,
            trade_instruction=trade_instruction,
            dragon_data=dragon_data,
            margin_data=margin_data,
            moneyflow_data=moneyflow_data,
            limit_emotion_data=limit_emotion_data,
            chip_radar_data=chip_radar_data,
            tushare_verified_source=tushare_verified_source,
            market_style_fact_packet=market_style_fact_packet,
            verified_technical_facts=verified_technical_facts or build_verified_technical_fact_packet({}),
            watch_targets=watch_targets,
            ts_code=_cn_ts_code(stock_code) if stock_code else "",
        )

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

    def display_cn_stock_analysis(target, price, professional_facts=None):
        """A股深度分析 - 集成 akshare 专业数据"""
        
        # 提取 A 股代码（去后缀）
        stock_code = _cn_stock_code_6(target)
        professional_facts = professional_facts or {}
        reuse_professional_facts = bool(
            professional_facts.get("available")
            or any(
                isinstance(professional_facts.get(key), dict) and professional_facts.get(key)
                for key in ["dragon_tiger", "margin", "moneyflow", "limit_emotion", "chip_radar"]
            )
        )
        
        st.markdown("""
        <div class="hf-ios-section hf-ios-fade-up hf-ios-stagger-1">
            <h4 style="margin-bottom: 0;">🇨🇳 A股专业数据穿透系统</h4>
        </div>
        """, unsafe_allow_html=True)
        st.caption("自动读取当前标的 Tushare A股专业事实；失败时显示缓存/空态，DeepSeek 不自动调用。")
        render_tushare_refresh_control(stock_code, "a_share_professional")

        cn_status = st.status("正在检查 A股龙虎榜、融资融券、资金流向与筹码事实...", expanded=False)
        cn_progress = st.progress(0)
        if reuse_professional_facts:
            dragon_data = professional_facts.get("dragon_tiger") or {}
            margin_data = professional_facts.get("margin") or {}
            moneyflow_data = professional_facts.get("moneyflow") or {}
            limit_emotion_data = professional_facts.get("limit_emotion") or {}
            chip_radar_data = professional_facts.get("chip_radar") or {}
            cn_progress.progress(100)
            cn_status.write("完成：复用主诊断A股专业事实包")
        else:
            dragon_data = _run_progress_stage(
                "检查龙虎榜",
                lambda: cached_cn_dragon_tiger_board(stock_code),
                cn_status,
                cn_progress,
                25,
                has_data=lambda data: bool(data and data.get("available")),
            )
            margin_data = _run_progress_stage(
                "检查融资融券",
                lambda: cached_cn_margin_data(stock_code),
                cn_status,
                cn_progress,
                50,
                has_data=lambda data: bool(data and data.get("available")),
            )
            moneyflow_data = _run_progress_stage(
                "检查个股资金流向",
                lambda: cached_cn_moneyflow_data(stock_code),
                cn_status,
                cn_progress,
                75,
                has_data=lambda data: bool(data and data.get("available")),
            )
            limit_emotion_data = _run_progress_stage(
                "检查涨跌停情绪",
                lambda: cached_cn_limit_emotion_data(stock_code, current_price=price),
                cn_status,
                cn_progress,
                90,
                has_data=lambda data: bool(data and data.get("available")),
            )
            chip_radar_data = _run_progress_stage(
                "检查筹码/胜率",
                lambda: get_cn_chip_radar_data(stock_code, current_price=price),
                cn_status,
                cn_progress,
                100,
                has_data=lambda data: bool(data and data.get("available")),
            )
        a_share_fact_payload = {
            "stock_code": stock_code,
            "dragon_tiger": dragon_data or {},
            "margin": margin_data or {},
            "moneyflow": moneyflow_data or {},
            "limit_emotion": limit_emotion_data or {},
            "chip_radar": chip_radar_data or {},
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        st.session_state["a_share_professional_facts"] = a_share_fact_payload
        a_share_capability_packet = data_capability.build_a_share_professional_capability_packet(a_share_fact_payload)
        current_status_strip = legacy_a_share_gate_service.build_a_share_status_strip(
            a_share_fact_payload,
            a_share_capability_packet,
        )
        status_completion_notice = legacy_a_share_gate_service.build_a_share_status_completion_notice(
            current_status_strip,
            task_label="A股盘口与情绪状态整理",
        )
        cn_status.write(status_completion_notice.get("decision_guardrail"))
        cn_status.update(
            label=status_completion_notice.get("label") or "已整理：A股盘口与情绪状态整理",
            state=status_completion_notice.get("state") or "complete",
        )
        st.session_state["a_share_professional_data_capability"] = a_share_capability_packet
        st.session_state["command_center_facts_packet"] = facts_packet_service.build_a_share_facts_packet(
            a_share_fact_payload,
            a_share_capability_packet,
            target=target,
        )
        _sync_a_share_capability_packet(a_share_capability_packet)
        st.session_state["command_center_chip_packet"] = chip_packet_service.build_command_center_chip_packet(
            st.session_state,
            target=target,
        )
        st.session_state["command_center_moneyflow_packet"] = moneyflow_packet_service.build_command_center_moneyflow_packet(
            st.session_state,
            target=target,
        )
        st.session_state["command_center_dragon_tiger_packet"] = dragon_tiger_packet_service.build_command_center_dragon_tiger_packet(
            st.session_state,
            target=target,
        )
        st.session_state["command_center_margin_packet"] = margin_packet_service.build_command_center_margin_packet(
            st.session_state,
            target=target,
        )
        st.session_state["command_center_limit_emotion_packet"] = limit_emotion_packet_service.build_command_center_limit_emotion_packet(
            st.session_state,
            target=target,
        )
        st.session_state["command_center_hard_risk_packet"] = hard_risk_packet_service.build_command_center_hard_risk_packet(
            st.session_state,
            target=target,
        )
        # 第一排：龙虎榜 + 融资融券 + 个股资金流向
        col_a1, col_a2, col_a3 = st.columns(3)
        
        with col_a1:
            st.markdown("**龙虎榜追踪**")
            if dragon_data and dragon_data.get("available"):
                st.metric("上榜日期", _cn_fmt_date(dragon_data.get("latest_date")), "")
                st.caption(f"数据日期：{_cn_fmt_date(dragon_data.get('latest_date'))}")
                if dragon_data.get("reason"):
                    st.caption(f"上榜原因：{dragon_data.get('reason')}")
                st.metric("收盘价 / 涨跌幅", f"{dragon_data.get('close') or '暂无'} / {dragon_data.get('pct_change') or '暂无'}%", "")
                st.metric("买入 / 卖出 / 净买入", f"{_cn_fmt_yi(dragon_data.get('buy_amount_yi'))} / {_cn_fmt_yi(dragon_data.get('sell_amount_yi'))} / {_cn_fmt_yi(dragon_data.get('net_buy_amount_yi'))}", "")
                if dragon_data.get("inst_summary"):
                    st.caption(f"机构席位摘要：{dragon_data.get('inst_summary')}")
            else:
                st.info((dragon_data or {}).get("message") or "近30日未见龙虎榜上榜记录")
            st.caption(f"数据源：{(dragon_data or {}).get('source', 'Tushare')} {(dragon_data or {}).get('api', 'top_list')}｜本地拉取时间：{(dragon_data or {}).get('updated_at', '未知')}")
        
        with col_a2:
            st.markdown("**融资融券监测**")
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
            st.caption(f"数据源：{(margin_data or {}).get('source', 'Tushare')} {(margin_data or {}).get('api', 'margin_detail')}｜本地拉取时间：{(margin_data or {}).get('updated_at', '未知')}")
        
        with col_a3:
            st.markdown("**个股资金流向**")
            if moneyflow_data and moneyflow_data.get("available"):
                st.metric("主力净流入", _cn_fmt_flow_yi(moneyflow_data.get("main_net_yi")), "")
                st.metric("大单净流入", _cn_fmt_flow_yi(moneyflow_data.get("large_net_yi")), "")
                st.metric("中单 / 小单净流入", f"{_cn_fmt_flow_yi(moneyflow_data.get('medium_net_yi'))} / {_cn_fmt_flow_yi(moneyflow_data.get('small_net_yi'))}", "")
                st.metric("近5日主力净流入合计", _cn_fmt_flow_yi(moneyflow_data.get("five_day_main_net_yi")), "")
                st.caption(f"最新数据日期：{_cn_fmt_date(moneyflow_data.get('date'))}")
                st.caption(f"最近资金方向：{moneyflow_data.get('direction') or '资金方向分歧'}")
                st.caption(f"资金结构评价：{moneyflow_data.get('structure') or '资金结构暂无法验证'}")
            else:
                st.info((moneyflow_data or {}).get("message") or "近5日未取得可验证个股资金流向，可能为非交易日、数据尚未更新、接口权限不足或标的暂不覆盖。")
            st.caption(f"数据源：{(moneyflow_data or {}).get('source', 'Tushare')} {(moneyflow_data or {}).get('api', 'moneyflow')}｜本地拉取时间：{(moneyflow_data or {}).get('updated_at', '未知')}")

        st.markdown("**A股情绪与涨跌停边界**")

        def _cn_fmt_limit_price(value):
            number = _cn_float(value)
            return "暂无" if number is None else f"¥{number:.2f}"

        def _cn_fmt_limit_pct(value):
            number = _cn_float(value)
            return "暂无" if number is None else f"{number:+.2f}%"

        if limit_emotion_data and limit_emotion_data.get("available"):
            e1, e2, e3, e4, e5 = st.columns(5)
            e1.metric("涨停价", _cn_fmt_limit_price(limit_emotion_data.get("up_limit")))
            e2.metric("跌停价", _cn_fmt_limit_price(limit_emotion_data.get("down_limit")))
            e3.metric("距涨停", _cn_fmt_limit_pct(limit_emotion_data.get("distance_to_up_pct")))
            e4.metric("距跌停", _cn_fmt_limit_pct(limit_emotion_data.get("distance_to_down_pct")))
            e5.metric("数据日期", _cn_fmt_date(limit_emotion_data.get("latest_date") or limit_emotion_data.get("concept_date")))

            record_rows = limit_emotion_data.get("limit_records") or []
            concept_rows = limit_emotion_data.get("concept_top5") or []
            record_col, concept_col = st.columns(2)
            with record_col:
                st.markdown("##### 近5日涨跌停 / 炸板 / 连板记录")
                if record_rows:
                    try:
                        st.dataframe(pd.DataFrame(record_rows), width="stretch", hide_index=True)
                    except Exception as e:
                        st.caption(f"表格渲染暂不可用：{e}")
                else:
                    st.info("近5日未见该股涨跌停/炸板记录。")
            with concept_col:
                st.markdown("##### 当日涨停概念强度 Top 5")
                if concept_rows:
                    try:
                        st.dataframe(pd.DataFrame(concept_rows), width="stretch", hide_index=True)
                    except Exception as e:
                        st.caption(f"表格渲染暂不可用：{e}")
                else:
                    st.info("暂未取得当日涨停概念强度数据。")
        else:
            st.info((limit_emotion_data or {}).get("message") or "近5日未取得可验证涨跌停/情绪数据，可能为非交易日、数据尚未更新、接口权限不足或标的暂不覆盖。")
        st.caption(
            "数据源："
            f"{(limit_emotion_data or {}).get('source', 'Tushare')} "
            f"{(limit_emotion_data or {}).get('api', 'stk_limit / limit_list_d / limit_cpt_list')}"
            f"｜本地拉取时间：{(limit_emotion_data or {}).get('updated_at', '未知')}"
        )
        if (limit_emotion_data or {}).get("warning"):
            st.caption(f"提示：{(limit_emotion_data or {}).get('warning')}")

        if st.session_state.get("skip_limit_cpt_list"):
            st.info("limit_cpt_list 此前因权限不足被跳过；如已升级权限，请点击重新检测。")
            if st.button("🔄 重新检测 limit_cpt_list 权限", key="btn_reset_limit_cpt_list"):
                st.session_state["skip_limit_cpt_list"] = False
                try:
                    cached_cn_limit_emotion_data.clear()
                    build_market_style_fact_packet.clear()
                except Exception:
                    pass
                st.success("已重置 limit_cpt_list 跳过标记。请刷新页面或重新运行当前分析。")

        st.markdown("**筹码/胜率雷达**")

        def _cn_fmt_price(value):
            number = _cn_float(value)
            return "暂无" if number is None else f"¥{number:.2f}"

        def _cn_fmt_pct_plain(value):
            number = _cn_float(value)
            return "暂无" if number is None else f"{number:.2f}%"

        if chip_radar_data and chip_radar_data.get("available"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("数据日期", _cn_fmt_date(chip_radar_data.get("trade_date")))
            c2.metric("获利盘比例 / 胜率", _cn_fmt_pct_plain(chip_radar_data.get("winner_rate")))
            c3.metric("加权平均筹码成本", _cn_fmt_price(chip_radar_data.get("weight_avg")))
            c4.metric("当前价相对筹码中枢", _cn_fmt_limit_pct(chip_radar_data.get("current_vs_weight_avg_pct")))
            st.caption(
                "筹码成本 5% / 50% / 95% 分位："
                f"{_cn_fmt_price(chip_radar_data.get('cost_5pct'))} / "
                f"{_cn_fmt_price(chip_radar_data.get('cost_50pct'))} / "
                f"{_cn_fmt_price(chip_radar_data.get('cost_95pct'))}"
            )
            st.caption(f"筹码压力评价：{chip_radar_data.get('chip_pressure_comment') or '暂无可验证数据'}")
            st.caption(f"筹码结构评价：{chip_radar_data.get('chip_structure_comment') or '暂无可验证数据'}")
            top_areas = chip_radar_data.get("chips_top_areas") or []
            if top_areas:
                st.caption(
                    "筹码密集区："
                    + "；".join(
                        f"{_cn_fmt_price(item.get('price'))} / {_cn_fmt_pct_plain(item.get('percent'))}"
                        for item in top_areas[:5]
                    )
                )
        else:
            st.info((chip_radar_data or {}).get("message") or "暂未取得可验证筹码/胜率数据，可能为数据尚未更新、接口权限不足或标的暂不覆盖。")
        st.caption(
            "数据源："
            f"{(chip_radar_data or {}).get('source', 'Tushare')} "
            f"{(chip_radar_data or {}).get('api', 'cyq_perf/cyq_chips')}"
            f"｜本地拉取时间：{(chip_radar_data or {}).get('updated_at', '未知')}"
        )

        capability_items = a_share_capability_packet.get("items") or []
        if capability_items:
            with st.expander("接口状态详情", expanded=False):
                st.caption(
                    f"{current_status_strip.get('status_label')}｜"
                    f"{current_status_strip.get('summary')}｜DeepSeek 未调用。"
                )
                capability_df = pd.DataFrame(capability_items)
                capability_columns = [
                    ("label", "数据"),
                    ("status", "状态"),
                    ("latest_date", "最近日期"),
                    ("updated_at", "更新时间"),
                    ("action_hint", "提示"),
                    ("error", "失败原因"),
                ]
                selected_columns = [source for source, _ in capability_columns if source in capability_df.columns]
                if selected_columns:
                    display_df = capability_df[selected_columns].rename(
                        columns={source: label for source, label in capability_columns}
                    )
                    st.dataframe(display_df, width="stretch", hide_index=True)

        with st.expander("数据口径说明", expanded=False):
            st.caption("龙虎榜与机构席位为盘后披露数据，不代表盘中实时席位行为。")
            st.caption("融资融券为交易所/券商披露口径，通常反映上一交易日或已披露时点，不是盘中实时余额。")
            st.caption("个股资金流为交易日盘后口径，不是盘中实时主力流。")
            st.caption("涨跌停记录、炸板、概念强度为盘后统计结果，不是盘中实时热度流。")
            st.caption("筹码/胜率为日度盘后更新结果，不是盘中实时筹码迁移。")
            st.caption("新闻/公告缺失是信息缺口，不是无风险；历史回测不代表未来收益。")
        
        st.markdown("---")
        
        # 第二排：专项扫描 + 单票持仓作战室
        btn_whale = False
        btn_next_day_plan = False
        btn_war_room = False
        btn_deepseek = False
        whale_fact_packet = None
        next_day_plan_fact_packet = None
        single_stock_war_room_fact_packet = None

        st.markdown("#### 🐳 专项资金扫描")
        st.caption("独立检查资金结构、龙虎榜、融资融券和短线资金验证，不自动生成持仓动作。")
        btn_whale = st.button("🐳 巨鲸资金嗅探", type="primary", width="stretch", key="btn_cn_whale")
        whale_output = st.container()

        visual_chip_center = _num((chip_radar_data or {}).get("weight_avg"))
        visual_ma20 = _num((verified_technical_facts or {}).get("ma20") or (verified_technical_facts or {}).get("ma20_value"))
        if visual_ma20 is None:
            visual_ma20 = _num((globals().get("technical_snapshot") or {}).get("ma20"))
        visual_ma60 = _num((verified_technical_facts or {}).get("ma60"))
        visual_limit_up = _num((limit_emotion_data or {}).get("up_limit"))
        visual_limit_down = _num((limit_emotion_data or {}).get("down_limit"))
        visual_today_flow = _num((moneyflow_data or {}).get("main_net_yi"))
        visual_five_day_flow = _num((moneyflow_data or {}).get("five_day_main_net_yi"))
        visual_profile = position_profile if isinstance(position_profile, dict) else (globals().get("position_profile") or {})
        visual_state = visual_profile.get("normalized_position_state") or position_status
        visual_is_holding = "持" in str(visual_state) and "观望" not in str(visual_state)
        visual_cost = visual_profile.get("cost_price") if visual_profile.get("cost_price") else None
        visual_shares = visual_profile.get("holding_units") if visual_profile.get("allow_pnl") else None

        st.markdown("#### 🎮 单票持仓作战室")
        with st.container():
            st.caption("先看持仓水位、资金冲突和动作矩阵，再进入次日计划、做T/减仓和外脑推演。所有内容均为辅助判断，不构成买卖建议。")
            render_position_waterline(
                price,
                cost_price=visual_cost,
                shares=visual_shares,
                chip_center=visual_chip_center,
                ma20=visual_ma20,
                ma60=visual_ma60,
                limit_up=visual_limit_up,
                limit_down=visual_limit_down,
            )
            render_action_matrix(
                price,
                cost_price=visual_cost,
                chip_center=visual_chip_center,
                ma20=visual_ma20,
                ma60=visual_ma60,
                today_main_net_yi=visual_today_flow,
                five_day_main_net_yi=visual_five_day_flow,
                position_status=visual_profile.get("normalized_position_state") or position_status,
            )
            render_moneyflow_conflict(
                visual_today_flow,
                visual_five_day_flow,
            )
            if visual_is_holding:
                render_price_simulator(
                    price,
                    cost_price=visual_cost,
                    shares=visual_shares,
                    chip_center=visual_chip_center,
                    ma20=visual_ma20,
                    ma60=visual_ma60,
                    limit_up=visual_limit_up,
                    limit_down=visual_limit_down,
                    key=f"price_simulator_cn_{stock_code}",
                )
            else:
                st.caption("未确认实际持仓：价格模拟不计算浮盈金额，也不生成做T状态。")

            war_room_view = st.radio(
                "单票作战室子模块",
                ["次日计划", "做T / 减仓推演", "外脑深度推演"],
                horizontal=True,
                key=f"cn_war_room_lazy_view_{stock_code}",
            )
            if war_room_view == "次日计划":
                st.caption("次日计划是验证清单，不是交易指令。")
                btn_next_day_plan = st.button("🧾 生成次日交易计划", width="stretch", key="btn_cn_next_day_plan")
                next_day_plan_output = st.container()
            if war_room_view == "做T / 减仓推演":
                st.caption("围绕当前票的持有、做T、减仓条件做推演；换仓雷达仅作为可选横向观察。")
                btn_war_room = st.button("🎯 生成做T / 减仓推演", width="stretch", key="btn_cn_war_room")
                war_room_output = st.container()
            if war_room_view == "外脑深度推演":
                st.caption("外脑深度推演需要手动触发，不自动调用 DeepSeek。输出长文收纳在下方折叠区。")
                btn_deepseek = st.button("🚀 启动外脑深度推演（A股专用）", width="stretch", key="btn_cn_deepseek")
                deepseek_output = st.container()
        
        if btn_deepseek:
            with deepseek_output:
                with st.spinner("正在从云端调取适配当前市场的量化纪律..."):
                    db = load_cloud_knowledge() 
                    all_rules = db["strategies"] + db["reflections"]
                    filtered_rules = [r for r in all_rules if "🇨🇳" in r or "A股" in r]
                    stock_logic = load_stock_logic_rules(target)
                    unverified_items = [f"brain_memory｜{rule}" for rule in filtered_rules]
                    if stock_logic:
                        unverified_items.append(f"stock_reports.auto_replay_rules｜{stock_logic}")
                    unverified_inject = build_limited_unverified_prompt_block(
                        unverified_items,
                        "brain_memory 云记忆 / stock_reports 历史自动炼丹规则",
                        max_items=10,
                        max_chars=4000,
                        per_item_chars=700,
                    )
            
            p_val = price if price else "未知"
            verified_technical_prompt = format_verified_technical_facts_for_prompt(verified_technical_facts)
            improved_prompt = legacy_a_share_prompt_service.build_a_share_deep_research_prompt(
                target=target,
                current_price=p_val,
                verified_technical_prompt=verified_technical_prompt,
                unverified_inject=unverified_inject,
            )
            
            with deepseek_output:
                with st.expander("📋 深度研报 / 长文分析", expanded=False):
                    st.markdown("### 📋 A股专用深度研报")
                    call_deepseek_stream(improved_prompt, system_role="作为顶级A股量化基金经理")

        if btn_next_day_plan:
            with next_day_plan_output:
                plan_status = st.status("正在生成次日交易计划...", expanded=True)
            next_day_plan_fact_packet = build_next_day_plan_fact_packet(
                stock_code,
                target,
                price,
                position_profile,
                trade_instruction,
                dragon_data,
                margin_data,
                moneyflow_data,
                limit_emotion_data,
                chip_radar_data=chip_radar_data,
                tushare_verified_source=tushare_verified_source,
                market_style_fact_packet=market_style_fact_packet,
                verified_technical_facts=verified_technical_facts,
            )
            verified_technical_prompt = format_verified_technical_facts_for_prompt(verified_technical_facts)
            plan_prompt = legacy_a_share_prompt_service.build_a_share_next_day_plan_prompt(
                target=target,
                fact_packet=next_day_plan_fact_packet,
                verified_technical_prompt=verified_technical_prompt,
            )
            with next_day_plan_output:
                plan_status.write("调用 DeepSeek 推理：生成六段式观察计划")
                st.markdown("### 🧾 次日交易计划")
                call_deepseek_stream(
                    plan_prompt,
                    system_role="你是严格的A股次日观察计划生成器，只能基于已验证数据生成观察预案。",
                )
                plan_status.update(label="完成：次日交易计划", state="complete")

        if btn_war_room:
            with war_room_output:
                war_room_status = st.status("正在生成单票作战室...", expanded=True)
            single_stock_war_room_fact_packet = build_single_stock_war_room_fact_packet(
                stock_code,
                target,
                price,
                position_profile,
                trade_instruction,
                dragon_data,
                margin_data,
                moneyflow_data,
                limit_emotion_data,
                chip_radar_data=chip_radar_data,
                tushare_verified_source=tushare_verified_source,
                market_style_fact_packet=market_style_fact_packet,
                verified_technical_facts=verified_technical_facts,
            )
            verified_technical_prompt = format_verified_technical_facts_for_prompt(verified_technical_facts)
            war_room_prompt = legacy_a_share_prompt_service.build_a_share_war_room_prompt(
                target=target,
                fact_packet=single_stock_war_room_fact_packet,
                verified_technical_prompt=verified_technical_prompt,
            )
            with war_room_output:
                war_room_status.write("调用 DeepSeek 推理：生成单票作战室 / 换仓雷达")
                st.markdown("### 🎯 单票作战室 / 换仓雷达")
                call_deepseek_stream(
                    war_room_prompt,
                    system_role="你是严格的A股单票作战室，只能基于已验证数据生成持仓与换仓观察预案。",
                )
                with st.expander("横向换仓雷达（可选）", expanded=False):
                    st.caption("当前版本沿用原单票作战室输出，换仓候选仍必须标注为待验证线索；后续可拆成独立横向比较模块。")
                war_room_status.update(label="完成：单票作战室 / 换仓雷达", state="complete")

        if btn_whale:
            with whale_output:
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
            
            recent_5d_close_volume = []
            if not hist_5d.empty:
                recent_data = hist_5d[['Close', 'Volume']].tail(5)
                for idx, row in recent_data.iterrows():
                    if hasattr(idx, "date"):
                        date_text = idx.date().isoformat()
                    else:
                        date_text = str(idx)
                    recent_5d_close_volume.append(
                        {
                            "date": date_text,
                            "close": _cn_float(row.get("Close")),
                            "volume": _cn_float(row.get("Volume")),
                        }
                    )

            whale_fact_packet = _run_progress_stage(
                "整理巨鲸资金事实包",
                lambda: legacy_a_share_prompt_packet_service.build_verified_whale_fact_packet(
                    stock_code=stock_code,
                    stock_name=target,
                    current_price=price,
                    recent_5d_close_volume=recent_5d_close_volume,
                    moneyflow_data=moneyflow_data,
                    dragon_data=dragon_data,
                    margin_data=margin_data,
                    limit_emotion_data=limit_emotion_data,
                    verified_technical_facts=verified_technical_facts,
                ),
                whale_status,
                whale_progress,
                50,
                has_data=lambda data: bool(data),
            )
            verified_technical_prompt = format_verified_technical_facts_for_prompt(verified_technical_facts)
            whale_prompt = legacy_a_share_prompt_service.build_a_share_whale_prompt(
                target=target,
                current_price=price,
                fact_packet=whale_fact_packet,
                verified_technical_prompt=verified_technical_prompt,
            )

            def run_whale_deepseek():
                with whale_output:
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

        with st.expander("🧪 AI事实包调试（开发者用）", expanded=False):
            show_debug_panel = st.checkbox("显示AI事实包调试详情", value=False, key="show_ai_fact_debug")
            if show_debug_panel:
                debug_view_model = legacy_a_share_debug_summary_service.build_legacy_a_share_debug_view_model(
                    verified_technical_facts=verified_technical_facts,
                    moneyflow_data=moneyflow_data,
                    dragon_data=dragon_data,
                    margin_data=margin_data,
                    limit_emotion_data=limit_emotion_data,
                    ai_context_packet=ai_context_packet,
                    whale_fact_packet=whale_fact_packet,
                    next_day_plan_fact_packet=next_day_plan_fact_packet,
                    single_stock_war_room_fact_packet=single_stock_war_room_fact_packet,
                )
                st.markdown("##### 一、已验证技术事实摘要")
                st.table(pd.DataFrame(debug_view_model["technical_rows"]))

                st.markdown("##### 二、A股资金事实摘要")
                st.table(pd.DataFrame(debug_view_model["fund_rows"]))

                st.markdown("##### 三、AI输入事实包状态")
                st.table(pd.DataFrame(debug_view_model["packet_status_rows"]))

                st.markdown("##### 四、缺失项汇总")
                st.table(pd.DataFrame(debug_view_model["missing_rows"]))

    # ==========================================
    # 4. 主界面
    # ==========================================
    st.markdown("""
    <section class="ming-hero hf-ios-section hf-ios-card hf-ios-fade-up">
        <div class="ming-kicker hf-ios-fade-in hf-ios-stagger-1">PRIVATE TRADING ASSISTANT</div>
        <h1 class="ming-title hf-ios-fade-up hf-ios-stagger-2">MING 交易工作台</h1>
        <div class="ming-subtitle hf-ios-fade-in hf-ios-stagger-3">从成本价出发，合并量化、资金、舆情和经理规则，给出更克制的交易指令。</div>
    </section>
    """, unsafe_allow_html=True)

    workspace_mode = st.radio(
        "主导航",
        ["综合推演中心 2.0", "高级工具箱（旧版保留）"],
        horizontal=True,
        key="workspace_mode_v2",
        label_visibility="collapsed",
    )
    
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1: 
        raw_target = st.text_input("🎯 锁定目标 (NVDA、0700、6758、600459 等)", "002008", label_visibility="collapsed").upper().strip()
        
        target, market_type, market_badge, currency = identify_market(raw_target)

    with top_c2:
        if workspace_mode == "综合推演中心 2.0":
            price_detail = _safe_get_command_center_price_detail(target, market_type)
            price = price_detail.get("price")
            if price:
                st.metric(f"📡 当前报价 ({market_badge})", f"{currency} {price}")
                source_label = price_detail.get("price_source") or price_detail.get("raw_source") or "unknown"
                st.caption(f"自动读取｜来源：{source_label}｜数据日期：{price_detail.get('data_date') or '未知'}")
            else:
                st.metric(f"📡 行情读取失败 ({market_badge})", "暂无价格")
                st.caption(price_detail.get("warning") or "接口未返回可用价格；综合中心继续展示缓存和失败状态。")
        else:
            price_detail = get_current_price_detail(target, market_type)
            price = price_detail.get("price")
            if price:
                p_display = f"{currency} {price}"
                st.metric(f"📡 卫星报价 ({market_badge})", p_display)
                source_label = price_detail.get("price_source") or "unknown"
                data_date = price_detail.get("data_date") or "日期未知"
                st.caption(f"价格来源：{source_label}｜数据日期：{data_date}")
            else:
                st.metric(f"📡 信号丢失 ({market_badge})", "未查找到该标的")
                if price_detail.get("warning"):
                    st.caption(f"价格读取失败：{price_detail.get('warning')}")

    with st.form("command_center_current_holding_form", clear_on_submit=False):
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
            cost_price_input = st.text_input(
                "成本价/参考价",
                value=str(st.session_state.get("command_center_cost_price_input", "0") or "0"),
                key="command_center_cost_price_input",
                help="已持有时填真实成本价；未买入时可填计划买入参考价。",
            )
        with pos_c4:
            holding_units_input = st.text_input(
                "持仓数量（可选）",
                value=str(st.session_state.get("command_center_holding_units_input", "0") or "0"),
                key="command_center_holding_units_input",
            )

        apply_c1, apply_c2, apply_c3 = st.columns([1.2, 1, 1.2])
        with apply_c1:
            analysis_horizon = st.selectbox(
                "分析周期",
                ["短中期", "短线", "中期", "长期"],
                index=0,
                key="command_center_analysis_horizon",
            )
        with apply_c2:
            margin_ratio_pct_input = st.text_input(
                "融资比例（%）",
                value=str(st.session_state.get("command_center_margin_ratio_pct_input", "0") or "0"),
                key="command_center_margin_ratio_pct_input",
            )
        with apply_c3:
            st.write("")
            st.write("")
            apply_current_holding = st.form_submit_button(
                "应用当前持仓",
                type="primary",
                width="stretch",
            )
    cost_price = _num(cost_price_input, 0) or 0
    holding_units = _num(holding_units_input, 0) or 0
    margin_ratio_pct = max(0, min(100, _num(margin_ratio_pct_input, 0) or 0))

    position_profile_preview = build_position_profile(
        target,
        price,
        cost_price,
        holding_units,
        capital_plan,
        position_status,
        currency,
    )
    position_profile_preview = _enrich_position_profile_for_command_center(
        position_profile_preview,
        horizon=analysis_horizon,
        margin_ratio_pct=margin_ratio_pct,
    )
    if apply_current_holding:
        apply_status = st.status("正在应用当前持仓并生成综合分析...", expanded=True)
        applied_packet = _apply_command_center_current_holding(
            target=target,
            market_type=market_type,
            currency=currency,
            position_status=position_status,
            cost_price=cost_price,
            holding_units=holding_units,
            capital_plan=capital_plan,
            horizon=analysis_horizon,
            margin_ratio_pct=margin_ratio_pct,
            status=apply_status,
        )
        applied_summary = applied_packet.get("summary") or {}
        if applied_summary.get("price_status") == "failed":
            apply_status.update(label="当前持仓已应用，但行情读取失败；页面将展示失败原因。", state="complete", expanded=False)
        else:
            apply_status.update(label="当前持仓已应用，综合分析已生成。", state="complete", expanded=False)
        st.session_state["command_center_apply_current_holding_notice"] = applied_summary
        st.rerun()

    apply_notice = st.session_state.pop("command_center_apply_current_holding_notice", None)
    if isinstance(apply_notice, dict) and apply_notice.get("target") == target:
        if apply_notice.get("price_status") == "failed":
            st.warning(f"当前持仓已进入分析链；行情读取失败：{apply_notice.get('price_warning') or '未返回价格'}")
        else:
            st.success(
                f"当前持仓已进入分析链：今日总决策 {apply_notice.get('decision_action') or '等待'}｜"
                f"策略 {apply_notice.get('strategy_action') or '等待'}｜DeepSeek：未调用。"
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
    if workspace_mode == "综合推演中心 2.0":
        render_command_center_workspace(
            target=target,
            market_badge=market_badge,
            price=price,
            market_type=market_type,
            position_profile=position_profile_preview,
            price_detail=price_detail,
        )
        st.stop()

    legacy_tab = st.radio(
        "高级工具模块",
        [
            "今日关注池",
            "天眼风控",
            "交易纪律实验室",
            "量化推演",
            "融资 ETF",
            "云端外脑",
            "数据源体检",
            "下一票雷达",
        ],
        horizontal=True,
        key="legacy_workspace_selected_tab",
    )

    recovery_notice = home_snapshot_service.build_tool_recovery_context_notice(st.session_state, selected_tab=legacy_tab)
    if recovery_notice:
        render_legacy_tool_recovery_notice_panel(recovery_notice, legacy_tab=legacy_tab)

    if legacy_tab == "今日关注池":
        st.markdown("""
        <div class="hf-ios-section hf-ios-fade-up">
            <h3 style="margin-bottom: 4px;">🏠 今日关注池 / 投研驾驶舱</h3>
            <div style="color: #6E6E73; font-size: 0.92rem;">先判断今天该看什么，再决定用哪个大师人格和哪个诊股模块。</div>
        </div>
        """, unsafe_allow_html=True)

        market_style_key = "legacy_market_style_fact_packet"
        market_style_refreshed_now = False
        if st.button("刷新市场风格数据", key="btn_refresh_market_style_fact_packet", width="stretch"):
            with st.spinner("正在刷新市场风格数据..."):
                st.session_state[market_style_key] = build_market_style_fact_packet()
                market_style_refreshed_now = True

        market_style_fact_packet = st.session_state.get(market_style_key)
        if market_style_fact_packet:
            market_sources = market_style_fact_packet.get("verified_sources") or []
            render_legacy_data_status(
                "今日关注池",
                status="已刷新" if market_style_refreshed_now else "使用缓存",
                updated_at=market_style_fact_packet.get("updated_at", ""),
                data_source=" / ".join(market_sources[:4]) if market_sources else "Tushare 市场风格事实包",
            )
        else:
            render_legacy_data_status(
                "今日关注池",
                status="未刷新",
                data_source="Tushare 市场风格事实包",
            )
        if not market_style_fact_packet:
            market_style_fact_packet = {
                "trade_date": "",
                "limit_up_count": 0,
                "limit_down_count": 0,
                "break_limit_count": 0,
                "break_limit_rate": None,
                "max_consecutive_limit": None,
                "recent_active_limit_samples": [],
                "dragon_tiger_activity": {"list_count": 0, "sample_rows": []},
                "moneyflow_samples": {"positive_samples": [], "negative_samples": []},
                "concept_strength_top": [],
                "market_state": "尚未刷新",
                "risk_switch": "等待刷新",
                "verified_sources": [],
                "missing_sources": ["点击“刷新市场风格数据”后读取 Tushare 市场风格事实包。"],
                "updated_at": "",
            }
        st.markdown("#### 市场风格总览")

        st.markdown(
            "**数据日期：** "
            f"{_cn_fmt_date(market_style_fact_packet.get('trade_date'))}"
            " ｜ **市场状态：** "
            f"{market_style_fact_packet.get('market_state') or '暂无可验证数据'}"
            " ｜ **进攻/防守开关：** "
            f"{market_style_fact_packet.get('risk_switch') or '适合只观察不买'}"
        )

        emotion_cols = st.columns(5)
        break_rate = market_style_fact_packet.get("break_limit_rate")
        break_rate_text = "暂无" if break_rate is None else f"{break_rate * 100:.1f}%"
        emotion_cols[0].metric("涨停家数", market_style_fact_packet.get("limit_up_count", 0))
        emotion_cols[1].metric("跌停家数", market_style_fact_packet.get("limit_down_count", 0))
        emotion_cols[2].metric("炸板家数", market_style_fact_packet.get("break_limit_count", 0))
        emotion_cols[3].metric("炸板率", break_rate_text)
        emotion_cols[4].metric("连板最高高度", market_style_fact_packet.get("max_consecutive_limit") or "暂无")

        activity_cols = st.columns(2)
        activity_cols[0].metric(
            "龙虎榜活跃数量",
            (market_style_fact_packet.get("dragon_tiger_activity") or {}).get("list_count", 0),
        )
        activity_cols[1].metric("资金流样本", len((market_style_fact_packet.get("moneyflow_samples") or {}).get("positive_samples", [])))

        st.caption("数据源：Tushare / Supabase / Yahoo Finance / DeepSeek")
        missing_sources = market_style_fact_packet.get("missing_sources") or []
        if missing_sources:
            st.caption("缺失数据说明：" + "；".join(missing_sources[:4]))
        else:
            st.caption("缺失数据说明：暂无")
        if market_style_fact_packet.get("market_state") == "暂无可验证数据" or missing_sources:
            st.info("市场情绪事实数据暂不完整，今日关注池将偏向防守观察。")

        if st.button("🚀 生成今日关注池", type="primary", width="stretch"):
            prompt = build_today_watchlist_prompt(market_style_fact_packet=market_style_fact_packet)
            call_deepseek_stream(
                prompt,
                system_role="你是冷静的投研总控台，负责生成今日关注池和风险分层。"
            )

        with st.expander("🔎 自动投喂反馈 / 最近入库", expanded=False):
            st.caption("默认不自动读取 Supabase 最近投喂记录；点击按钮后读取并缓存。")
            if st.button("读取最近入库反馈", key="btn_load_auto_feed_feedback", width="stretch"):
                with st.spinner("正在读取最近入库反馈..."):
                    st.session_state["legacy_auto_feed_feedback"] = load_auto_feed_feedback(limit=8)
                    st.session_state["legacy_auto_feed_feedback_loaded_at"] = datetime.datetime.now().isoformat(timespec="seconds")

            feedback = st.session_state.get("legacy_auto_feed_feedback")
            if not feedback:
                st.info("尚未读取最近入库反馈。点击按钮后显示市场新闻、经理规则和自动心跳。")
                feedback = {
                    "market_news": [],
                    "processed_sources": [],
                    "manager_rules": [],
                    "manager_scores": [],
                    "auto_runs": [],
                }
            else:
                st.caption(f"最近读取时间：{st.session_state.get('legacy_auto_feed_feedback_loaded_at', '未知')}")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("市场新闻", len(feedback.get("market_news", [])))
            c2.metric("已处理来源", len(feedback.get("processed_sources", [])))
            c3.metric("新增经理规则", len(feedback.get("manager_rules", [])))
            c4.metric("经理评分", len(feedback.get("manager_scores", [])))
            c5.metric("自动心跳", len(feedback.get("auto_runs", [])))

            st.caption("GitHub Actions 每 30 分钟跑一次自动投喂；这里显示最近写入 Supabase 的记录。")

            feed_view = st.radio(
                "反馈分类",
                [
                "市场新闻",
                "经理来源",
                "经理规则",
                "经理评分",
                "自动心跳",
                ],
                horizontal=True,
                key="legacy_auto_feed_feedback_view",
            )

            if feed_view == "市场新闻":
                if feedback.get("market_news"):
                    st.dataframe(pd.DataFrame(feedback["market_news"]), width="stretch")
                else:
                    st.info("暂时没有最近市场新闻入库。")

            if feed_view == "经理来源":
                if feedback.get("processed_sources"):
                    st.dataframe(pd.DataFrame(feedback["processed_sources"]), width="stretch")
                else:
                    st.info("暂时没有最近处理成功的经理来源。")

            if feed_view == "经理规则":
                if feedback.get("manager_rules"):
                    st.dataframe(pd.DataFrame(feedback["manager_rules"]), width="stretch")
                else:
                    st.info("暂时没有最近新增的经理规则。")

            if feed_view == "经理评分":
                if feedback.get("manager_scores"):
                    st.dataframe(pd.DataFrame(feedback["manager_scores"]), width="stretch")
                else:
                    st.info("暂时没有最近经理评分。")

            if feed_view == "自动心跳":
                if feedback.get("auto_runs"):
                    st.dataframe(pd.DataFrame(feedback["auto_runs"]), width="stretch")
                else:
                    st.warning("还没有看到自动任务心跳。可去 GitHub Actions 手动 Run workflow 验证 secrets 和权限。")
    # 模块 A：天眼风控
    if legacy_tab == "天眼风控":
        st.markdown(
            f"""
            <div class="hf-ios-section hf-ios-fade-up">
                <h3 style="margin-bottom: 0;">🛡️ 极高权限合规审计：{target}</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.info("消耗算力扫描内幕交易、消息抢跑、监管问询等风险。")
        if is_a_share_market(market_type):
            render_tushare_refresh_control(target, "tianyan_risk")
            st.caption("天眼风控里的结构化资金/情绪/筹码事实同样以盘后或披露口径为主，不是盘中实时数据。")

        with st.expander("📡 持续调查池", expanded=True):
            st.caption("公告自动调查第一阶段仅扫描这里 enabled=true 的 A 股标的；每次修改会写入 stock_reports 的最新 watchlist 版本。")
            watchlist_payload, watchlist_error = load_announcement_watchlist()
            if watchlist_error:
                st.warning(watchlist_error)

            add_c1, add_c2, add_c3 = st.columns([1, 1, 2])
            with add_c1:
                wl_code = st.text_input(
                    "股票代码",
                    value="",
                    placeholder="002008 / 002008.SZ / 601138",
                    key="announcement_watchlist_code",
                )
            with add_c2:
                wl_name = st.text_input(
                    "股票名称（可选）",
                    value="",
                    placeholder="大族激光",
                    key="announcement_watchlist_name",
                )
            with add_c3:
                wl_note = st.text_input(
                    "备注（可选）",
                    value="",
                    placeholder="需要跟踪公告风险、订单、中标、减持等",
                    key="announcement_watchlist_note",
                )

            action_c1, action_c2, action_c3 = st.columns([1, 1, 2])
            with action_c1:
                if st.button("加入持续调查池", key="btn_add_announcement_watchlist", width="stretch"):
                    ok, message, added_code = upsert_announcement_watchlist_target(wl_code, wl_name, wl_note)
                    if ok:
                        st.success(f"{message} 标的：{added_code}")
                        st.rerun()
                    else:
                        st.warning(message)
            with action_c2:
                if st.button("刷新调查池", key="btn_refresh_announcement_watchlist", width="stretch"):
                    st.rerun()

            targets_for_display = watchlist_payload.get("targets") or []
            enabled_count = sum(1 for item in targets_for_display if item.get("enabled"))
            st.caption(
                f"当前调查池：{len(targets_for_display)} 只；启用扫描：{enabled_count} 只；"
                f"最新更新时间：{watchlist_payload.get('updated_at') or '暂无'}"
            )
            if targets_for_display:
                display_rows = [
                    {
                        "ts_code": item.get("ts_code", ""),
                        "name": item.get("name", ""),
                        "enabled": bool(item.get("enabled")),
                        "priority": item.get("priority", "normal"),
                        "added_at": item.get("added_at", ""),
                        "note": item.get("note", ""),
                    }
                    for item in targets_for_display
                ]
                st.dataframe(pd.DataFrame(display_rows), width="stretch", hide_index=True)

                enabled_codes = [item.get("ts_code") for item in targets_for_display if item.get("enabled")]
                if enabled_codes:
                    disable_c1, disable_c2 = st.columns([2, 1])
                    with disable_c1:
                        disable_code = st.selectbox(
                            "停用标的",
                            enabled_codes,
                            key="announcement_watchlist_disable_code",
                        )
                    with disable_c2:
                        st.caption(" ")
                        if st.button("停用", key="btn_disable_announcement_watchlist", width="stretch"):
                            ok, message = disable_announcement_watchlist_target(disable_code)
                            if ok:
                                st.success(message)
                                st.rerun()
                            else:
                                st.warning(message)
            else:
                st.info("持续调查池为空。加入 A 股标的后，公告自动调查才会优先扫描这些股票。")
        
        if st.button("🚨 启动全网舆情风控网", key="btn_risk"):
            with st.spinner("正在渗透舆情数据源..."):
                try:
                    try:
                        news_stock_name = get_supply_chain_profile(target).get("name") or raw_target or target
                    except Exception:
                        news_stock_name = raw_target or target

                    def compact_market_news_rows(rows):
                        compact_rows = []
                        for item in filter_news_clues_for_prompt(
                            rows or [],
                            stock_code=target,
                            stock_name=news_stock_name,
                            max_items=8,
                            hours=48,
                        ):
                            title = item.get("title", "")
                            if not title:
                                continue
                            compact_rows.append(
                                {
                                    "title": title,
                                    "source": "Supabase market_news 新闻线索",
                                    "url": item.get("url", ""),
                                    "created_at": item.get("created_at", ""),
                                    "risk_tag": item.get("risk_tag", ""),
                                    "sentiment": item.get("sentiment", ""),
                                    "verification_status": item.get("verification_status", "新闻线索，需验证"),
                                    "fact_boundary": item.get("fact_boundary", "不得替代官方事实"),
                                }
                            )
                        return compact_rows[:8]

                    def compact_processed_source_rows(rows):
                        compact_rows = []
                        for item in filter_news_clues_for_prompt(
                            rows or [],
                            stock_code=target,
                            stock_name=news_stock_name,
                            max_items=8,
                            hours=72,
                        ):
                            title = item.get("title", "")
                            if not title:
                                continue
                            compact_rows.append(
                                {
                                    "title": title,
                                    "source": "processed_sources 待验证投喂线索",
                                    "created_at": item.get("created_at", ""),
                                    "url": item.get("url", ""),
                                    "verification_status": "投喂资料 / 待验证线索",
                                }
                            )
                        return compact_rows[:8]

                    def compact_yfinance_news_rows(rows):
                        compact_rows = []
                        seen = set()
                        for item in rows or []:
                            content = item.get("content") if isinstance(item, dict) else {}
                            title = item.get("title", "") if isinstance(item, dict) else ""
                            title = title or (content or {}).get("title", "")
                            if not title:
                                continue
                            key = normalize_news_title(title)
                            if key in seen:
                                continue
                            seen.add(key)
                            compact_rows.append(
                                {
                                    "title": title,
                                    "source": "yfinance.news 备用新闻线索",
                                    "verification_status": "备用新闻线索，需验证",
                                }
                            )
                        return compact_rows[:6]

                    def first_titles(rows, prefix="", limit=3):
                        titles = [str(item.get("title", "")).strip() for item in rows or [] if item.get("title")]
                        if not titles:
                            return "暂无"
                        text = "；".join(titles[:limit])
                        return f"{prefix}{text}" if prefix else text

                    def section_available(data):
                        data = data or {}
                        return bool(
                            data.get("available")
                            or data.get("records_available")
                            or data.get("boundary_available")
                            or data.get("concept_available")
                        )

                    def fmt_num(value, suffix=""):
                        if value in [None, ""]:
                            return "暂无"
                        return f"{value}{suffix}"

                    def format_free_announcement_radar(free_ann, limit=3):
                        free_ann = free_ann or {}
                        rows = free_ann.get("rows") or []
                        if not free_ann.get("available") or not rows:
                            return "暂无免费公告雷达结果。"

                        lines = []
                        for item in rows[:limit]:
                            title = str(item.get("title") or "").strip() or "无标题"
                            ann_date = str(item.get("ann_date") or "").strip() or "暂无日期"
                            parse_status = str(item.get("parse_status") or "").strip() or "unknown"
                            pdf_url = str(item.get("pdf_url") or item.get("url") or "").strip() or "暂无"
                            ai_summary = str(item.get("ai_summary") or "").strip()
                            risk_tags = item.get("risk_tags") or []
                            risk_tags_text = "、".join(str(tag) for tag in risk_tags[:3]) if risk_tags else "暂无"
                            boundary = str(item.get("source_boundary") or "").strip() or "暂无"
                            line = (
                                f"{ann_date}｜{title}｜parse_status:{parse_status}｜"
                                f"链接:{pdf_url}｜风险标签:{risk_tags_text}｜边界:{boundary}"
                            )
                            if ai_summary:
                                line += f"｜摘要:{ai_summary}"
                            lines.append(line)

                        return "；".join(lines) if lines else "暂无免费公告雷达结果。"

                    def build_tianyan_display_lines(packet):
                        trading = packet.get("verified_trading_structure_risks") or {}
                        chip = packet.get("verified_chip_risks") or {}
                        emotion = packet.get("verified_emotion_risks") or {}
                        hard = packet.get("verified_hard_risks") or {}
                        clues = packet.get("sentiment_and_unverified_clues") or {}
                        free_ann = hard.get("free_announcement_radar") or {}
                        news_digest = clues.get("news_digest") or {}

                        moneyflow = trading.get("moneyflow") or {}
                        if moneyflow.get("available"):
                            moneyflow_line = (
                                f"{moneyflow.get('direction') or '资金方向待验证'}；"
                                f"主力净流入 {fmt_num(moneyflow.get('main_net_yi'), '亿')}；"
                                f"近5日主力净流入 {fmt_num(moneyflow.get('five_day_main_net_yi'), '亿')}"
                            )
                        else:
                            moneyflow_line = "暂无可验证数据"

                        dragon = trading.get("dragon_tiger") or {}
                        if dragon.get("available"):
                            dragon_line = (
                                f"上榜日期 {dragon.get('trade_date') or dragon.get('latest_date') or '暂无'}；"
                                f"净买入 {fmt_num(dragon.get('net_buy_amount') or dragon.get('net_buy_amount_yi'), '亿')}；"
                                f"{dragon.get('institution_summary') or dragon.get('inst_summary') or '席位明细待验证'}"
                            )
                        else:
                            dragon_line = "暂无可验证数据"

                        margin = trading.get("margin") or {}
                        if margin.get("available"):
                            margin_line = (
                                f"融资余额 {fmt_num(margin.get('financing_balance_yi'), '亿')}；"
                                f"融资买入额 {fmt_num(margin.get('financing_buy_yi'), '亿')}；"
                                f"融资融券余额 {fmt_num(margin.get('margin_balance_yi'), '亿')}"
                            )
                        else:
                            margin_line = "暂无可验证数据"

                        chip_radar = chip.get("chip_radar") or {}
                        if chip_radar.get("available"):
                            chip_line = (
                                f"获利盘 {fmt_num(chip_radar.get('winner_rate'), '%')}；"
                                f"筹码中枢 {fmt_num(chip_radar.get('weight_avg'))}；"
                                f"{chip_radar.get('chip_pressure_comment') or '筹码压力待验证'}"
                            )
                        else:
                            chip_line = "暂无可验证数据"

                        limit_emotion = emotion.get("limit_emotion") or {}
                        concept = emotion.get("concept_strength") or {}
                        if section_available(limit_emotion) or concept.get("available"):
                            records = limit_emotion.get("recent_limit_records") or limit_emotion.get("limit_records") or []
                            concept_names = [
                                str(item.get("概念") or item.get("name") or item.get("ts_code") or "")
                                for item in (concept.get("top5") or [])
                            ]
                            concept_names = [name for name in concept_names if name]
                            emotion_line = (
                                f"涨跌停/炸板记录 {len(records)} 条；"
                                f"概念强度 Top5：{'、'.join(concept_names[:5]) if concept_names else '暂无'}"
                            )
                        else:
                            emotion_line = "暂无可验证数据"

                        def hard_line(section, empty_text="暂无可验证数据", fallback_section=None, fallback_prefix="Tushare 官方公告接口未授权；已启用免费公告雷达 fallback。"):
                            section = section or {}
                            if not section.get("available"):
                                fallback_text = format_free_announcement_radar(fallback_section)
                                if fallback_section and fallback_section.get("available"):
                                    return f"{fallback_prefix}{fallback_text}"
                                if fallback_section is not None:
                                    return f"{fallback_prefix}暂无免费公告雷达结果。"
                                return section.get("message") or empty_text
                            summary = section.get("summary") or ""
                            flags = section.get("risk_flags") or []
                            if flags:
                                return f"{summary or '已取得可验证记录'}；风险线索：{'；'.join(flags[:2])}"
                            rows = section.get("rows") or []
                            return summary or f"已取得 {len(rows)} 条可验证记录"

                        return {
                            "moneyflow": moneyflow_line,
                            "dragon_tiger": dragon_line,
                            "margin": margin_line,
                            "chip": chip_line,
                            "emotion": emotion_line,
                            "hard_announcements": hard_line(
                                hard.get("announcements"),
                                fallback_section=free_ann,
                            ),
                            "free_announcement_radar": hard_line(free_ann),
                            "hard_earnings_forecast": hard_line(hard.get("earnings_forecast")),
                            "hard_holder_reduction": hard_line(hard.get("holder_reduction")),
                            "hard_share_unlock": hard_line(hard.get("share_unlock")),
                            "hard_pledge": hard_line(hard.get("pledge")),
                            "hard_institution_surveys": hard_line(hard.get("institution_surveys")),
                            "market_news": first_titles(clues.get("market_news"), limit=3),
                            "processed_sources": first_titles(clues.get("processed_sources"), prefix="待验证线索：", limit=3),
                            "yfinance_news": first_titles(clues.get("yfinance_news"), limit=3),
                            "news_digest": format_news_digest_radar(news_digest),
                        }

                    def build_tianyan_risk_prompt(target, raw_target, price, tianyan_prompt_packet, veto_result):
                        return f"""
当前分析标的：{target}
用户原始输入：{raw_target}
当前价格：{price}

请基于下方【天眼风控雷达事实包】执行结构化风控排雷，把输出从“事实复述”升级成“红橙黄预警雷达”。

【天眼风控雷达事实包】
{tianyan_prompt_packet}

系统一票否决结果：
{veto_result}

公告边界补充：
1. 如果 anns_d 未授权，但 free_announcement_radar 有数据，应写“官方 Tushare 公告缺失，已参考免费公告雷达作为公告线索”。
2. parsed_pdf 可作为“公告 PDF 摘要线索”；metadata_only 只能作为“公告标题线索，需验证”。
3. 没有 PDF 摘要时，不得凭标题补写具体处罚、诉讼、减持、订单、业绩事实。
4. 免费公告雷达是 anns_d fallback，不等于 Tushare 官方公告接口。
5. AI 摘要是模型解读，不是公告原文。

请严格按以下固定结构输出，标题必须逐字出现，不得缺段：

【红色风险】
- 只写高优先级、可触发明显风控升级的事项。
- 重点识别：控股股东减持 + 高质押 / 资金持续恶化 / 重大公告风险叠加；新增监管、处罚、诉讼、业绩大幅下修等硬风险；多个硬风险同时出现。
- 如果没有足够红色风险，明确写“暂无新增红色风险”，但不得把数据缺失写成无风险。

【橙色风险】
- 重点识别：控股股东减持记录；质押比例较高（例如 > 15%）；近5日主力大额净流出；融资余额较高且价格转弱；龙虎榜已过期但被市场反复引用。
- 如果今日主力净流入但近5日仍净流出，橙色风险里必须写“中期资金面仍未扭转”。

【黄色风险】
- 专门写信息缺口、时效下降、证据不足和弱风险。
- 公告缺失、新闻 digest 缺失、筹码缺失、业绩预告缺失、数据日期过旧、机构调研只能作为待验证线索，都必须列在这里。
- 公告/新闻/筹码缺失时，不得写成“无风险”，必须写成黄色信息缺口。

【短线改善信号】
- 只写短线修复或边际改善，不得直接上升为反转结论。
- 如果今日主力净流入 + 近5日主力净流出，必须明确写：
  “短线资金回流，但中期资金仍未扭转” 或 “短线修复，未确认反转”。
- 可以写：今日主力净流入、概念强度高、价格接近涨停/强势区。
- 但若近5日仍流出，必须同时写明“只能视为短线修复，未确认反转”。

【动作建议】
- 只给条件化动作，不给绝对交易指令。
- “暂停加仓”可以直接输出。
- “降低仓位”必须绑定触发条件，例如：次日主力重新净流出；股价无法站稳关键均线 / 筹码中枢；新增减持 / 质押 / 公告风险；今日资金回流无法延续。
- 可以给“继续观察”，也可以给“暂不直接降低仓位，先暂停加仓 / 继续观察”。
- 不得输出：必买、必卖、立即清仓、满仓、梭哈。

【次日验证清单】
- 最多 5 条，必须编号。
- 优先从以下角度给出：
  1. 资金：次日主力是否连续第二日净流入。
  2. 价格：是否站稳关键位 / 均线 / 筹码中枢。
  3. 公告：是否出现减持进展、风险公告、业绩公告。
  4. 题材：概念热度是否延续还是退潮。
  5. 杠杆：融资余额是否继续上升。

【数据缺口】
- 单独汇总当前影响判断质量的缺口。
- 至少检查：公告、新闻 digest、筹码、业绩预告、龙虎榜时效、调研证据边界、数据日期。
- 如果某项缺失或过旧，必须写清楚为什么它会降低判断把握度。

可引用证据边界：

【已验证硬风险】
只能引用：
- anns_d：公告标题、公告日期、URL。标题只能作为公告线索，不能直接下事实结论。
- free_announcement_radar：免费公告雷达。parsed_pdf 只能作为公告摘要线索；metadata_only 只能作为公告标题线索。
- 如果 anns_d 未授权，但 free_announcement_radar 有数据，应优先引用“官方 Tushare 公告缺失，已参考免费公告雷达作为公告线索”。
- 如果没有免费公告雷达结果，再明确写“暂无免费公告雷达结果”。
- forecast：业绩预告类型、净利润变动区间、报告期。
- stk_holdertrade：股东减持记录。
- share_float：未来解禁日期、解禁比例、股东名称。
- pledge_stat / pledge_detail：最近一期质押比例、未解押明细。
- stk_surv：机构调研记录，只能作为关注度/验证线索，不是买入信号。

【已验证交易结构风险】
只能引用：
- moneyflow
- top_list / top_inst
- margin_detail
- limit_list_d / limit_cpt_list

【已验证筹码风险】
只能引用：
- cyq_perf
- cyq_chips

【已验证情绪/题材风险】
只能引用：
- 涨跌停记录
- 炸板/连板
- 概念强度 Top5

【舆情 / 投喂资料 / 待验证线索】
只能引用：
- market_news 新闻线索
- processed_sources 待验证投喂线索
- yfinance.news 备用新闻线索
- stock_reports.news_digest 新闻摘要线索，只能引用 claims / clues / evidence，不能当官方事实
- brain_memory
- manager_rules

触发逻辑与阈值规则：
1. 今日主力净流入 + 近5日主力净流出：必须输出“短线资金回流，但中期资金仍未扭转”或“短线修复，未确认反转”。
2. 龙虎榜超过 3 个交易日：降权为历史资金痕迹。
3. 龙虎榜超过 5 个交易日：不得作为当前买入依据，只能写历史参考。
4. 公告 / 新闻 / 筹码缺失：不得写成“无风险”，必须列为黄色信息缺口。
5. 调研记录：只能写关注度 / 验证线索，不是买入信号。
6. 控股股东减持记录默认至少进入橙色风险；若与高质押、持续资金恶化、重大公告风险叠加，可升级红色风险。
7. 质押比例较高可按 > 15% 识别为橙色风险；若与减持、公告风险、资金恶化叠加，可升级红色风险。
8. 近5日主力大额净流出默认至少进入橙色风险；若今日只是单日回流，不得直接下反转结论。
9. 龙虎榜时效过久时，只能写“历史资金痕迹 / 历史参考”，不得写成当前席位支撑或当前买入理由。
10. 机构调研、概念强度、短线回流，最多进入“短线改善信号”或“黄色风险补充说明”，不能冲抵硬风险。

硬规则：
1. 风控模块不是买卖指令。
2. 不自动下单。
3. 不写必买、必卖、立即清仓、满仓、梭哈。
4. processed_sources / brain_memory / manager_rules 只能作为待验证线索。
5. 没有 Tushare 真实返回时写“暂无可验证数据”。
6. 筹码集中不是必涨。
7. 获利盘高不是必卖。
8. 融资融券只能代表杠杆资金，不等于主力资金。
9. 龙虎榜/游资不是跟随信号。
10. limit_cpt_list 只能代表概念热度，不是追涨理由。
11. market_news 的 risk_tag / sentiment 是系统提取标签，不等同公告事实。
12. market_news / yfinance.news / processed_sources 不得替代公告、监管、诉讼、处罚、减持、业绩预告等官方事实。
13. 没有真实接口返回，不得补写监管处罚、问询、诉讼、减持、质押、解禁。
14. 不得编造事实包以外的公告、新闻、资金、席位、监管或财务信息。
15. 公告标题不是事实裁判；没有阅读全文或结构化字段时，只能写“公告线索显示标题涉及 X”。
16. 机构调研不是利好，不等于机构买入、持仓或推荐。
17. 减持、解禁、质押只能提升风险权重，不能自动推出必跌。
18. 盈利预测不是业绩确定。
19. “暂停加仓” 可以直接输出。
20. “降低仓位” 必须绑定触发条件，且只能在满足以下任一或多项时使用：主力资金继续大幅流出、股价无法收回筹码中枢、放量跌破关键支撑位、硬风险新增或恶化（例如减持、质押、公告风险恶化）。
21. 如果触发条件不足，必须改写为“暂不直接降低仓位，先暂停加仓 / 继续观察”。
22. 风控结论只能给观察建议和条件化动作，不得写成直接交易指令。
23. 免费公告雷达中 parsed_pdf 是 AI 公告摘要线索，不是公告原文；metadata_only 不得作为处罚、诉讼、减持等事实结论。
24. stock_reports.news_digest 只能作为新闻摘要线索，不能写成公告、监管、诉讼、处罚、减持、业绩预告等官方事实；与官方事实冲突时，以官方事实为准。
25. 如果同时存在硬风险、交易结构恶化和信息缺口，不得仅总结为“风险等级：中”，必须展开到红橙黄分层。
"""

                    # 1. 优先查 market_news 股票/市场舆情库
                    market_news = fetch_market_news_from_supabase(raw_target, limit=8)

                    # 如果 raw_target 查不到，再用识别后的 target 查一次
                    if not market_news:
                        market_news = fetch_market_news_from_supabase(target, limit=8)

                    market_news_clues = compact_market_news_rows(market_news)
                    market_headlines = [
                        (
                            f"{item.get('title', '')}｜来源:{item.get('source', '')}"
                            f"｜时间:{item.get('created_at', '')}｜链接:{item.get('url', '')}"
                            f"｜系统标签:{item.get('risk_tag', '')}/{item.get('sentiment', '')}"
                            f"｜状态:{item.get('verification_status', '新闻线索，需验证')}"
                        )
                        for item in market_news_clues
                    ]

                    # 2. 再查 processed_sources，也就是你自动投喂抓到的资讯源
                    local_news = fetch_local_news_from_supabase(raw_target, limit=8)

                    # 如果 raw_target 查不到，再用识别后的 target 查一次
                    if not local_news:
                        local_news = fetch_local_news_from_supabase(target, limit=8)

                    processed_clues = compact_processed_source_rows(local_news)
                    local_headlines = [
                        (
                            f"{item.get('title', '')}｜processed_sources 待验证线索"
                            f"｜时间:{item.get('created_at', '')}｜链接:{item.get('url', '')}"
                            f"｜状态:{item.get('verification_status', '投喂资料 / 待验证线索')}"
                        )
                        for item in processed_clues
                    ]

                    # 3. 最后尝试 yfinance.news 作为备用
                    yf_news_clues = []
                    try:
                        news_data = yf.Ticker(target).news
                        yf_news_clues = compact_yfinance_news_rows(news_data or [])
                    except Exception as e:
                        yf_news_clues = []
                        st.info(f"yfinance 舆情接口受限，已切换本地舆情库。原因：{e}")
                    yf_headlines = [item.get("title", "") for item in yf_news_clues if item.get("title")]

                    # 4. 合并舆情线索，优先级：market_news > processed_sources > yfinance；只作软线索
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
                        st.success("未触发硬性一票否决；auto 新闻/RSS 只作为待验证线索。")
                        if veto_result.get("soft_clues"):
                            st.info("；".join(veto_result["soft_clues"]))

                    tianyan_risk_fact_packet = build_tianyan_risk_fact_packet(
                        target,
                        raw_target or target,
                        current_price=price,
                    )
                    tianyan_risk_fact_packet["sentiment_and_unverified_clues"].update(
                        {
                            "market_news": market_news_clues,
                            "processed_sources": processed_clues,
                            "yfinance_news": yf_news_clues,
                            "news_digest": (tianyan_risk_fact_packet.get("sentiment_and_unverified_clues") or {}).get("news_digest") or {},
                            "note": "processed_sources / brain_memory / manager_rules / news_digest 只能作为待验证线索",
                        }
                    )
                    _sync_tianyan_hard_risk_to_command_center(
                        tianyan_risk_fact_packet,
                        target=target,
                        position_profile=position_profile_preview,
                    )

                    display_lines = build_tianyan_display_lines(tianyan_risk_fact_packet)
                    st.caption(
                        "天眼风控结构化事实"
                        f"｜数据日期：{_extract_tianyan_packet_data_dates(tianyan_risk_fact_packet)}"
                        f"｜本地拉取时间：{tianyan_risk_fact_packet.get('updated_at', '未知')}"
                    )
                    st.markdown("#### 【已验证结构化风险】")
                    st.markdown(f"- 资金风险：{display_lines['moneyflow']}")
                    st.markdown(f"- 龙虎榜风险：{display_lines['dragon_tiger']}")
                    st.markdown(f"- 融资融券风险：{display_lines['margin']}")
                    st.markdown(f"- 筹码风险：{display_lines['chip']}")
                    st.markdown(f"- 情绪/题材风险（涨跌停 / 概念热度风险）：{display_lines['emotion']}")

                    st.markdown("#### 【已验证硬风险】")
                    st.markdown(f"- 公告风险：{display_lines['hard_announcements']}")
                    st.markdown(f"- 业绩预告风险：{display_lines['hard_earnings_forecast']}")
                    st.markdown(f"- 股东减持风险：{display_lines['hard_holder_reduction']}")
                    st.markdown(f"- 解禁风险：{display_lines['hard_share_unlock']}")
                    st.markdown(f"- 质押风险：{display_lines['hard_pledge']}")
                    st.markdown(f"- 机构调研验证：{display_lines['hard_institution_surveys']}")

                    free_ann = (tianyan_risk_fact_packet.get("verified_hard_risks") or {}).get("free_announcement_radar") or {}
                    st.markdown("#### 【免费公告雷达】")
                    st.caption("免费公告雷达只展示已生成摘要的重要公告；普通公告可能仅作为 metadata 存在。")
                    if free_ann.get("available"):
                        st.markdown(f"- 摘要：{display_lines['free_announcement_radar']}")
                        for item in (free_ann.get("rows") or [])[:6]:
                            link = item.get("pdf_url") or item.get("url") or ""
                            st.markdown(
                                f"- {item.get('ann_date', '')}｜{item.get('title', '')}"
                                f"｜important:{item.get('important', False)}"
                                f"｜解析:{item.get('fetch_status', '')}/{item.get('parse_status', '')}"
                                f"｜风险等级:{item.get('risk_level', '未知')}/{item.get('impact_direction', '不确定')}"
                                f"｜摘要:{item.get('ai_summary', '') or '暂无 AI 摘要'}"
                                f"｜链接:{link or '暂无'}"
                                f"｜边界:{item.get('source_boundary', '')}"
                            )
                    else:
                        st.info(free_ann.get("message") or "暂无近14天免费公告摘要。")

                    st.markdown("#### 【舆情与待验证线索】")
                    st.markdown(f"- Supabase market_news 新闻线索：{display_lines['market_news']}")
                    st.markdown(f"- processed_sources 待验证投喂线索：{display_lines['processed_sources']}")
                    st.markdown(f"- yfinance.news 备用新闻线索：{display_lines['yfinance_news']}")
                    st.markdown(f"- news_digest 最近新闻摘要线索：{display_lines['news_digest']}")

                    local_risk_radar = build_local_risk_radar_items(tianyan_risk_fact_packet)
                    render_risk_radar_summary(
                        red_items=local_risk_radar.get("red_items"),
                        orange_items=local_risk_radar.get("orange_items"),
                        yellow_items=local_risk_radar.get("yellow_items"),
                        improvement_items=local_risk_radar.get("improvement_items"),
                    )
                    risk_position_is_holding = position_profile_preview.get("normalized_position_state") == "已持仓"
                    if risk_position_is_holding:
                        risk_chip_center = _num(
                            (
                                (
                                    tianyan_risk_fact_packet.get("verified_chip_risks") or {}
                                ).get("chip_radar") or {}
                            ).get("weight_avg")
                        )
                        render_action_matrix(
                            price,
                            cost_price=position_profile_preview.get("cost_price"),
                            chip_center=risk_chip_center,
                            ma20=None,
                            ma60=None,
                            today_main_net_yi=local_risk_radar.get("today_main_net_yi"),
                            five_day_main_net_yi=local_risk_radar.get("five_day_main_net_yi"),
                            has_reduction_risk=bool(local_risk_radar.get("has_reduction_risk")),
                            pledge_ratio=local_risk_radar.get("pledge_ratio"),
                            has_announcement_gap=bool(local_risk_radar.get("has_announcement_gap")),
                            has_news_gap=bool(local_risk_radar.get("has_news_gap")),
                            position_status=position_profile_preview.get("normalized_position_state") or position_status,
                        )

                    tianyan_prompt_packet = json.dumps(
                        tianyan_risk_fact_packet,
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    )

                    risk_prompt = build_tianyan_risk_prompt(
                        target,
                        raw_target,
                        price,
                        tianyan_prompt_packet,
                        veto_result,
                    )

                    st.markdown(
                        "<div class='risk-alert hf-ios-soft-glow'>正在执行深度排雷协议，请留意红色警告...</div>",
                        unsafe_allow_html=True
                    )

                    call_deepseek_stream(
                        risk_prompt,
                        system_role="你是无情的金融风控稽查员，只能基于已给出的舆情线索判断，不得编造新闻。"
                    )

                except Exception as e:
                    st.error(f"舆情风控模块运行失败: {e}")

    # 模块 B：交易纪律实验室
    if legacy_tab == "交易纪律实验室":
        st.markdown("### 🧪 交易纪律实验室")
        st.caption("先把交易经验和投喂资料炼成纪律，再用历史回测验证纪律是否有效。")

        discipline_view = st.radio(
            "交易纪律子模块",
            ["规则炼丹 / 手动投喂", "回测验证 / 纪律实验"],
            horizontal=True,
            key="legacy_discipline_lazy_view",
        )

        if discipline_view == "规则炼丹 / 手动投喂":
            st.caption("用于从历史行情、投喂资料、基金经理规则中提炼交易纪律。")
            st.markdown(f"### ⏳ 强化学习时光机：{target}")
            st.caption("自动从近两年抽取多个历史窗口，用后续走势反向校验，提炼这只票自己的交易规范。")

            refine_view = st.radio(
                "炼丹方式",
                ["自动多段复盘", "手动单段盲测"],
                horizontal=True,
                key="legacy_discipline_refine_lazy_view",
            )

            if refine_view == "自动多段复盘":
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

            if refine_view == "手动单段盲测":
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

        if discipline_view == "回测验证 / 纪律实验":
            st.caption("用于验证某套交易纪律在历史区间内的表现。")
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
                    ["四模式对比（推荐）", "默认模式", "自由模式", "动态止盈止损模式", "科技成长股模式"],
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
                bt_provider = st.selectbox("行情源", ["auto", "tushare", "akshare", "yfinance"], index=0, key="bt_provider")

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
                "科技成长股模式": ["tech_growth"],
                "三模式对比（推荐）": ["default", "free", "dynamic"],
                "四模式对比（推荐）": ["default", "free", "dynamic", "tech_growth"],
            }
            selected_modes = mode_map.get(bt_mode_choice, ["default", "free", "dynamic", "tech_growth"])
            st.caption("默认模式看固定止盈/止损；自由模式只看趋势/RSI/均线；动态模式会按ATR/波动率自动调止盈止损；科技成长股模式在趋势持有上叠加减仓间隔和ATR回撤风控。")
            st.info("模式选择不是交易指令；历史回测不代表未来收益。")

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
                        st.session_state["command_center_discipline_packet"] = legacy_packet_sync_service.sync_legacy_discipline_packet(
                            st.session_state,
                            live_packet={
                                "discipline": {
                                    "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                                    "source": "交易纪律实验室回测缓存",
                                }
                            },
                            target=target,
                        )
                        _remember_legacy_tool_packet_recovery_result(
                            key="legacy_discipline",
                            label="交易纪律/回测",
                            writes_packet="command_center_discipline_packet",
                            target_tab="交易纪律实验室",
                            target=target,
                            position_profile=position_profile_preview,
                        )
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
                        st.session_state["command_center_discipline_packet"] = legacy_packet_sync_service.sync_legacy_discipline_packet(
                            st.session_state,
                            target=target,
                        )
                        _remember_legacy_tool_packet_recovery_result(
                            key="legacy_discipline",
                            label="交易纪律/回测",
                            writes_packet="command_center_discipline_packet",
                            target_tab="交易纪律实验室",
                            target=target,
                            position_profile=position_profile_preview,
                        )
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
                        "tech_basket_batch_summary": compact_tech_batch_for_prompt(
                            st.session_state.get("last_tech_batch_backtest")
                        ),
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

            st.divider()
            st.markdown("### 科技股样本池批量验证")
            st.caption("用同一套四模式回测跑内置科技成长样本池，先判断自由趋势和科技成长股模式的优势是否能跨股票复现。")
            st.caption("科技股样本池批量验证只用于历史纪律比较，不是买卖建议。它回答的是哪种规则更适配这类股票，而不是当前是否应该买入。")
            pool_df = pd.DataFrame(TECH_GROWTH_STOCK_POOL)
            st.dataframe(pool_df.rename(columns={"ts_code": "代码", "name": "名称"}), width="stretch", hide_index=True)

            bb1, bb2, bb3, bb4 = st.columns([1, 1, 1, 1])
            with bb1:
                batch_start = st.date_input("批量回测起点", default_start, key="batch_bt_start")
            with bb2:
                batch_end = st.date_input("批量回测终点", default_end, key="batch_bt_end")
            with bb3:
                batch_provider = st.selectbox("批量行情源", ["tushare", "auto", "akshare", "yfinance"], index=0, key="batch_bt_provider")
            with bb4:
                batch_cash = st.number_input("单票回测本金", min_value=1000.0, value=float(bt_cash), step=5000.0, key="batch_bt_cash")

            batch_key = f"tech_batch|{batch_start}|{batch_end}|{batch_provider}|{batch_cash}|{len(TECH_GROWTH_STOCK_POOL)}"
            if st.button("运行科技股样本池回测", key="btn_run_tech_batch_backtest", width="stretch"):
                with st.spinner("正在批量拉取行情并运行四模式回测..."):
                    batch_result = run_batch_strategy_mode_backtests(
                        TECH_GROWTH_STOCK_POOL,
                        batch_start.isoformat(),
                        (batch_end + datetime.timedelta(days=1)).isoformat(),
                        batch_cash,
                        provider=batch_provider,
                    )
                    batch_result["date_range"] = {"start": batch_start.isoformat(), "end": batch_end.isoformat()}
                    batch_result["provider"] = batch_provider
                    st.session_state["last_tech_batch_backtest"] = batch_result
                    st.session_state["last_tech_batch_key"] = batch_key

            batch_result = st.session_state.get("last_tech_batch_backtest")
            if batch_result:
                st.markdown("#### 聚合结果表")
                aggregate = batch_result.get("aggregate")
                if aggregate is not None and not aggregate.empty:
                    agg_show = aggregate.rename(columns={
                        "mode_label": "模式",
                        "avg_return_pct": "平均收益",
                        "median_return_pct": "中位数收益",
                        "avg_max_drawdown_pct": "平均最大回撤",
                        "median_max_drawdown_pct": "中位数最大回撤",
                        "avg_exit_action_win_rate": "平均退出动作胜率",
                        "avg_round_trip_win_rate": "平均完整交易胜率",
                        "avg_trade_count": "平均退出动作数",
                        "avg_entry_count": "平均买入次数",
                        "avg_round_trip_count": "平均完整交易数",
                        "avg_open_position_count": "平均未闭合持仓",
                        "avg_effective_round_count": "平均有效交易周期数",
                        "avg_profit_factor": "平均盈亏比",
                        "avg_sharpe": "平均夏普",
                        "avg_calmar": "平均收益回撤比",
                        "positive_stock_count": "正收益股票数",
                        "tested_stock_count": "参与股票数",
                        "mode_win_count": "收益胜出次数",
                        "worst_stock_return_pct": "最差股票收益",
                        "worst_stock_drawdown_pct": "最差股票回撤",
                        "avg_reduce_count": "平均REDUCE次数",
                        "avg_reduce_per_effective_round": "每有效周期平均REDUCE",
                    })
                    show_cols = [
                        "模式", "平均收益", "中位数收益", "平均最大回撤", "中位数最大回撤",
                        "平均退出动作胜率", "平均完整交易胜率", "平均退出动作数", "平均买入次数", "平均完整交易数",
                        "平均未闭合持仓", "平均有效交易周期数",
                        "平均盈亏比", "平均夏普", "平均收益回撤比", "正收益股票数", "参与股票数", "收益胜出次数",
                        "最差股票收益", "最差股票回撤", "平均REDUCE次数", "每有效周期平均REDUCE",
                    ]
                    st.dataframe(agg_show[[col for col in show_cols if col in agg_show.columns]], width="stretch", hide_index=True)
                else:
                    st.warning("批量回测没有形成可汇总结果。")

                st.markdown("#### 单票明细表")
                details = batch_result.get("details")
                if details is not None and not details.empty:
                    detail_show = details.rename(columns={
                        "ticker": "代码",
                        "name": "名称",
                        "mode_label": "模式",
                        "total_return_pct": "收益",
                        "max_drawdown_pct": "最大回撤",
                        "exit_action_win_rate": "退出动作胜率",
                        "round_trip_win_rate": "完整交易胜率",
                        "trade_count": "退出动作数",
                        "entry_count": "买入次数",
                        "round_trip_count": "完整交易数",
                        "open_position_count": "期末未闭合持仓",
                        "effective_round_count": "有效交易周期数",
                        "open_position_return_pct": "期末未闭合持仓收益",
                        "open_position_holding_days": "未闭合持仓天数",
                        "avg_round_trip_return": "平均完整收益",
                        "profit_factor": "盈亏比",
                        "avg_holding_days": "平均持仓天数",
                        "max_single_trade_loss": "最大单笔亏损",
                        "reduce_count": "REDUCE次数",
                        "avg_reduce_per_round_trip": "每笔平均REDUCE",
                        "avg_reduce_per_effective_round": "每有效周期REDUCE",
                        "sharpe": "夏普",
                        "calmar": "收益回撤比",
                        "source": "行情源",
                    })
                    detail_cols = [
                        "代码", "名称", "模式", "收益", "最大回撤", "退出动作胜率", "完整交易胜率",
                        "退出动作数", "买入次数", "完整交易数", "期末未闭合持仓", "有效交易周期数", "期末未闭合持仓收益",
                        "未闭合持仓天数", "平均完整收益", "盈亏比", "平均持仓天数",
                        "最大单笔亏损", "REDUCE次数", "每笔平均REDUCE", "每有效周期REDUCE", "夏普", "收益回撤比", "行情源",
                    ]
                    st.dataframe(detail_show[[col for col in detail_cols if col in detail_show.columns]], width="stretch", hide_index=True)
                else:
                    st.info("暂无单票明细。")

                st.markdown("#### 策略解释摘要")
                st.info(
                    f"{batch_result.get('summary', '')} "
                    "不能只看单票；自由趋势高胜率必须看完整交易胜率，而不是只看包含 REDUCE 的退出动作胜率。"
                    "如果自由趋势完整交易胜率仍然领先，才说明它更适合科技趋势票；"
                    "如果科技成长股模式能降低回撤和 REDUCE 次数且收益不过度掉队，才说明风控改造有效。"
                )
                failures = batch_result.get("failures") or []
                if failures:
                    with st.expander(f"失败股票 {len(failures)} 只", expanded=False):
                        st.dataframe(pd.DataFrame(failures), width="stretch", hide_index=True)

    # 模块 C：主干量化推演 - 多市场版
    if legacy_tab == "量化推演":
        quant_run_now = st.button(
            "生成量化推演",
            key="btn_legacy_quant_generate",
            type="primary",
            width="stretch",
        )
        quant_result = st.session_state.get("legacy_quant_result") or {}
        if quant_run_now:
            quant_result = {
                "status": "running",
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "target": target,
                "market_type": market_type,
            }
            st.session_state["legacy_quant_result"] = quant_result
        quant_status = "使用缓存" if quant_result.get("status") == "completed" else "未刷新"
        if quant_run_now or quant_result.get("status") == "running":
            quant_status = "已刷新"
        render_legacy_data_status(
            "量化推演",
            status=quant_status,
            updated_at=quant_result.get("generated_at", ""),
            data_source="Supabase 记忆 / 估值技术情景 / Tushare A股事实 / 自动回测",
        )
        if not quant_run_now:
            if quant_result:
                st.caption(
                    "上次量化推演状态："
                    f"{quant_result.get('status', '已运行')}｜"
                    f"{quant_result.get('generated_at', '时间未知')}"
                )
            st.stop()
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
        limit_emotion_snapshot = {}
        a_share_professional_stock_code = ""
        a_share_dragon_data = None
        a_share_margin_data = None
        a_share_moneyflow_data = None
        a_share_limit_emotion_data = None
        a_share_chip_radar_data = None
        a_share_professional_facts = {}

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
            verified_technical_facts = build_verified_technical_fact_packet(technical_snapshot)
            verified_technical_prompt = format_verified_technical_facts_for_prompt(verified_technical_facts)
            money_flow_session_key = f"akshare_money_flow_{normalized_target}_{market_type}"
            money_flow_refresh_key = f"{money_flow_session_key}_refresh_token"
            if is_a_share_market(market_type):
                money_flow_snapshot = st.session_state.get(money_flow_session_key) or build_money_flow_snapshot_placeholder(
                    normalized_target,
                    market_type,
                    "默认未自动运行 AkShare 资金穿透；下方优先展示 Tushare 可验证事实。",
                )
            else:
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
                a_share_professional_stock_code = _cn_stock_code_6(normalized_target)
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
                try:
                    a_share_dragon_data = _run_progress_stage(
                        "读取A股龙虎榜事实",
                        lambda: cached_cn_dragon_tiger_board(a_share_professional_stock_code),
                        main_status,
                        main_progress,
                        56,
                        has_data=lambda data: bool(data and data.get("available")),
                    )
                    a_share_margin_data = _run_progress_stage(
                        "读取A股融资融券事实",
                        lambda: cached_cn_margin_data(a_share_professional_stock_code),
                        main_status,
                        main_progress,
                        57,
                        has_data=lambda data: bool(data and data.get("available")),
                    )
                    a_share_moneyflow_data = _run_progress_stage(
                        "读取A股moneyflow事实",
                        lambda: cached_cn_moneyflow_data(a_share_professional_stock_code),
                        main_status,
                        main_progress,
                        58,
                        has_data=lambda data: bool(data and data.get("available")),
                    )
                    a_share_limit_emotion_data = _run_progress_stage(
                        "读取涨跌停情绪事实",
                        lambda: cached_cn_limit_emotion_data(a_share_professional_stock_code, current_price=price),
                        main_status,
                        main_progress,
                        59,
                        has_data=lambda data: bool(data and data.get("available")),
                    )
                    limit_emotion_snapshot = a_share_limit_emotion_data
                    a_share_chip_radar_data = _run_progress_stage(
                        "读取A股筹码/胜率事实",
                        lambda: get_cn_chip_radar_data(a_share_professional_stock_code, current_price=price),
                        main_status,
                        main_progress,
                        60,
                        has_data=lambda data: bool(data and data.get("available")),
                    )
                except Exception as e:
                    limit_emotion_snapshot = {
                        "available": False,
                        "message": "近5日未取得可验证涨跌停/情绪数据，可能为非交易日、数据尚未更新、接口权限不足或标的暂不覆盖。",
                        "error": str(e),
                    }
                    a_share_limit_emotion_data = limit_emotion_snapshot
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
            if is_a_share_market(market_type):
                a_share_professional_facts = _run_progress_stage(
                    "整理A股专业事实包",
                    lambda: build_a_share_professional_fact_packet(
                        a_share_professional_stock_code or normalized_target,
                        target,
                        price,
                        position_profile,
                        trade_instruction,
                        dragon_data=a_share_dragon_data,
                        margin_data=a_share_margin_data,
                        moneyflow_data=a_share_moneyflow_data,
                        limit_emotion_data=a_share_limit_emotion_data or limit_emotion_snapshot,
                        chip_radar_data=a_share_chip_radar_data,
                        tushare_verified_source=tushare_verified_source,
                        market_style_fact_packet=market_style_fact_packet,
                        verified_technical_facts=verified_technical_facts,
                    ),
                    main_status,
                    main_progress,
                    78,
                    has_data=lambda data: bool(data and data.get("available")),
                )
                st.session_state["a_share_professional_facts"] = a_share_professional_facts
                st.session_state["command_center_facts_packet"] = facts_packet_service.build_a_share_facts_packet(
                    a_share_professional_facts,
                    (a_share_professional_facts or {}).get("data_capability") or st.session_state.get("a_share_professional_data_capability") or {},
                    target=normalized_target,
                    name=target,
                )
                st.session_state["command_center_chip_packet"] = chip_packet_service.build_command_center_chip_packet(
                    st.session_state,
                    target=normalized_target,
                )
                st.session_state["command_center_moneyflow_packet"] = moneyflow_packet_service.build_command_center_moneyflow_packet(
                    st.session_state,
                    target=normalized_target,
                )
                st.session_state["command_center_dragon_tiger_packet"] = dragon_tiger_packet_service.build_command_center_dragon_tiger_packet(
                    st.session_state,
                    target=normalized_target,
                )
                st.session_state["command_center_margin_packet"] = margin_packet_service.build_command_center_margin_packet(
                    st.session_state,
                    target=normalized_target,
                )
                st.session_state["command_center_limit_emotion_packet"] = limit_emotion_packet_service.build_command_center_limit_emotion_packet(
                    st.session_state,
                    target=normalized_target,
                )
                st.session_state["command_center_hard_risk_packet"] = hard_risk_packet_service.build_command_center_hard_risk_packet(
                    st.session_state,
                    target=normalized_target,
                )
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
            ai_context_packet += """

【新闻线索边界】
1. 近48小时舆情只允许作为新闻线索，不是官方事实。
2. 只有精确命中当前股票代码或公司名的 market_news 才进入本段；宽行业新闻不得进入严格风控。
3. risk_tag / sentiment 是模型提取标签，不是公告、监管、诉讼、处罚、减持、业绩预告等官方事实。
4. 涉及公告、监管、诉讼、处罚、减持、业绩预告，必须优先引用 Tushare / 交易所 / 公司公告等结构化或官方来源；没有验证则写“待验证线索”。
"""
            ai_context_packet += "\n\n" + verified_technical_prompt
            if is_a_share_market(market_type):
                ai_context_packet += format_cn_limit_emotion_context(limit_emotion_snapshot)
                ai_context_packet += format_a_share_professional_facts_for_prompt(a_share_professional_facts)
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
                f"｜数据日期：{_extract_tushare_basic_data_dates(tushare_verified_source)}"
                f"｜本地拉取时间：{tushare_verified_source.get('updated_at', '')}"
                f"｜{tushare_verified_source.get('status', '')}"
            )
        render_trade_instruction_card(position_profile, trade_instruction)
        render_relevant_memory_context(cloud_memory_context)

        with st.expander("🧭 统一诊股底座：产业链 / 估值 / 舆情 / 风控", expanded=True):
            base_view = st.radio(
                "统一诊股底座子模块",
                [
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
                ],
                horizontal=True,
                key=f"legacy_quant_base_lazy_view_{normalized_target}",
            )
            if base_view == "产业链联动":
                render_supply_chain_module(supply_profile, portfolio_health)
            if base_view == "估值回归":
                render_valuation_module(valuation_snapshot)
            if base_view == "实时指标":
                render_technical_module(technical_snapshot)
            if base_view == "情景推演":
                render_scenario_module(scenario_snapshot)
            if base_view == "近48小时舆情":
                sentiment_rows = recent_news_rows
                if is_a_share_market(market_type):
                    tianyan_for_sentiment = st.session_state.get("tianyan_risk_fact_packet")
                    try:
                        packet_stock = (
                            (tianyan_for_sentiment or {}).get("stock", {}).get("ts_code")
                            if isinstance(tianyan_for_sentiment, dict)
                            else ""
                        )
                        current_ts_code = _cn_ts_code(_cn_stock_code_6(normalized_target))
                        if not isinstance(tianyan_for_sentiment, dict) or packet_stock != current_ts_code:
                            tianyan_for_sentiment = build_tianyan_risk_fact_packet(
                                normalized_target,
                                supply_profile.get("name") or target,
                                current_price=price,
                            )
                            st.session_state["tianyan_risk_fact_packet"] = tianyan_for_sentiment
                        sentiment_rows = merge_sentiment_with_hard_risk_rows(
                            recent_news_rows,
                            tianyan_for_sentiment,
                            limit=12,
                        )
                        if len(sentiment_rows or []) > len(recent_news_rows or []):
                            st.caption("已自动合并公告/减持等硬风险线索；该步骤使用 10 分钟缓存，不调用 DeepSeek。")
                    except Exception as sentiment_error:
                        st.warning(f"公告/硬风险线索合并失败，继续显示软舆情缓存：{sentiment_error}")
                render_recent_sentiment_module(sentiment_rows)
            if base_view == "持仓体检":
                render_portfolio_health_module(portfolio_health)
            if base_view == "资金面":
                st.caption("AkShare 资金穿透为补充数据源，可能受远端接口影响。默认优先展示 Tushare 可验证事实；如需更细资金穿透，可手动刷新。")
                if market_type == "A_SHARE":
                    if st.button("刷新 AkShare 资金穿透快照", key=f"btn_{money_flow_session_key}"):
                        refresh_token = datetime.datetime.now().isoformat(timespec="seconds")
                        st.session_state[money_flow_refresh_key] = refresh_token
                        quick_status = st.status("正在刷新 AkShare 资金穿透快照...", expanded=True)
                        quick_progress = st.progress(0)
                        money_flow_snapshot = _run_progress_stage(
                            "读取 AkShare 个股资金流",
                            lambda: cached_money_flow_snapshot(
                                normalized_target,
                                market_type,
                                deep=False,
                                refresh_token=refresh_token,
                            ),
                            quick_status,
                            quick_progress,
                            100,
                            has_data=lambda data: bool(data and (data.get("available") or data.get("partial"))),
                        )
                        st.session_state[money_flow_session_key] = money_flow_snapshot
                        quick_status.update(label="AkShare 资金穿透快照已结束", state="complete")
                    money_flow_snapshot = st.session_state.get(money_flow_session_key) or money_flow_snapshot
                    render_a_share_tushare_money_summary(
                        a_share_moneyflow_data,
                        a_share_margin_data,
                        a_share_dragon_data,
                        a_share_chip_radar_data,
                    )
                    render_money_flow_snapshot_status(money_flow_snapshot)
                else:
                    render_money_flow_snapshot_status(money_flow_snapshot)
                render_money_flow_module(money_flow_snapshot)
                if market_type == "A_SHARE":
                    st.caption("即使 AkShare 资金穿透暂不可用，也不影响下方 Tushare 龙虎榜、融资融券、moneyflow、筹码等专业事实。")
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
                                has_data=lambda data: bool(data and (data.get("available") or data.get("partial"))),
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
            if base_view == "回测反哺":
                if main_backtest_report:
                    render_backtest_report(main_backtest_report)
                else:
                    st.warning(backtest_warning or "暂无主诊断回测反哺。")
            if base_view == "同行对比":
                render_peer_snapshot(peer_rows)
            if base_view == "深度挖掘":
                render_research_links(research_links)
            if base_view == "禁止买入":
                render_risk_decision(strict_decision)
            if base_view == "可信度":
                render_data_quality_module(data_quality_report)
            if base_view == "新鲜度":
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
            display_cn_stock_analysis(target, price, professional_facts=a_share_professional_facts)

        st.session_state["legacy_quant_result"] = {
            "status": "completed",
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "target": target,
            "market_type": market_type,
        }
        st.session_state["command_center_quant_packet"] = legacy_packet_sync_service.sync_legacy_quant_packet(
            st.session_state,
            target=target,
        )
        _remember_legacy_tool_packet_recovery_result(
            key="legacy_quant",
            label="量化推演",
            writes_packet="command_center_quant_packet",
            target_tab="量化推演",
            target=target,
            position_profile=position_profile_preview,
        )

    if legacy_tab == "融资 ETF":
        st.markdown("### 🧮 融资版 ETF 投资法")
        st.caption("该模块只做仓位与风险预算测算，不构成买卖建议。融资会放大收益和亏损，必须设置风险线。")
        st.info("融资会放大收益和亏损。本模块只做风险预算和仓位测算，不构成买卖建议。")
        st.caption("ETF 实时强弱来自 Tushare 数据与本地规则模型，DeepSeek 仅用于解释，不直接决定仓位。")
        st.markdown(
            """
            <style>
            .st-key-btn_margin_etf_refresh_daily button,
            .st-key-btn_margin_etf_refresh_intraday button,
            [class*="st-key-btn_margin_etf_refresh_daily"] button,
            [class*="st-key-btn_margin_etf_refresh_intraday"] button,
            .st-key-btn_margin_etf_refresh_daily [data-testid^="stBaseButton"],
            .st-key-btn_margin_etf_refresh_intraday [data-testid^="stBaseButton"],
            [class*="st-key-btn_margin_etf_refresh_daily"] [data-testid^="stBaseButton"],
            [class*="st-key-btn_margin_etf_refresh_intraday"] [data-testid^="stBaseButton"] {
                background: rgba(0, 122, 255, 0.08) !important;
                color: rgba(0, 122, 255, 0.92) !important;
                border: 1px solid rgba(0, 122, 255, 0.14) !important;
                box-shadow: none !important;
            }
            .st-key-btn_margin_etf_refresh_daily button:hover,
            .st-key-btn_margin_etf_refresh_intraday button:hover,
            [class*="st-key-btn_margin_etf_refresh_daily"] button:hover,
            [class*="st-key-btn_margin_etf_refresh_intraday"] button:hover,
            .st-key-btn_margin_etf_refresh_daily [data-testid^="stBaseButton"]:hover,
            .st-key-btn_margin_etf_refresh_intraday [data-testid^="stBaseButton"]:hover,
            [class*="st-key-btn_margin_etf_refresh_daily"] [data-testid^="stBaseButton"]:hover,
            [class*="st-key-btn_margin_etf_refresh_intraday"] [data-testid^="stBaseButton"]:hover {
                background: rgba(0, 122, 255, 0.12) !important;
                color: rgba(0, 122, 255, 0.98) !important;
                border-color: rgba(0, 122, 255, 0.18) !important;
            }
            .st-key-btn_margin_etf_recalc button,
            [class*="st-key-btn_margin_etf_recalc"] button,
            .st-key-btn_margin_etf_recalc [data-testid^="stBaseButton"],
            [class*="st-key-btn_margin_etf_recalc"] [data-testid^="stBaseButton"] {
                background: rgba(120, 120, 128, 0.10) !important;
                color: rgba(60, 60, 67, 0.88) !important;
                border: 1px solid rgba(60, 60, 67, 0.12) !important;
                box-shadow: none !important;
            }
            .st-key-btn_margin_etf_recalc button:hover,
            [class*="st-key-btn_margin_etf_recalc"] button:hover,
            .st-key-btn_margin_etf_recalc [data-testid^="stBaseButton"]:hover,
            [class*="st-key-btn_margin_etf_recalc"] [data-testid^="stBaseButton"]:hover {
                background: rgba(120, 120, 128, 0.14) !important;
                color: rgba(29, 29, 31, 0.92) !important;
                border-color: rgba(60, 60, 67, 0.16) !important;
            }
            .st-key-btn_margin_etf_refresh_daily button p,
            .st-key-btn_margin_etf_refresh_intraday button p,
            .st-key-btn_margin_etf_recalc button p,
            [class*="st-key-btn_margin_etf_refresh_daily"] button p,
            [class*="st-key-btn_margin_etf_refresh_intraday"] button p,
            [class*="st-key-btn_margin_etf_recalc"] button p,
            .st-key-btn_margin_etf_refresh_daily [data-testid^="stBaseButton"] p,
            .st-key-btn_margin_etf_refresh_intraday [data-testid^="stBaseButton"] p,
            .st-key-btn_margin_etf_recalc [data-testid^="stBaseButton"] p,
            [class*="st-key-btn_margin_etf_refresh_daily"] [data-testid^="stBaseButton"] p,
            [class*="st-key-btn_margin_etf_refresh_intraday"] [data-testid^="stBaseButton"] p,
            [class*="st-key-btn_margin_etf_recalc"] [data-testid^="stBaseButton"] p {
                color: inherit !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        if "margin_etf_daily_refresh_token" not in st.session_state:
            st.session_state["margin_etf_daily_refresh_token"] = "base"
        if "margin_etf_intraday_refresh_token" not in st.session_state:
            st.session_state["margin_etf_intraday_refresh_token"] = ""
        if "margin_etf_calc_refresh_token" not in st.session_state:
            st.session_state["margin_etf_calc_refresh_token"] = "base"

        pool_col1, pool_col2, pool_col3 = st.columns(3)
        with pool_col1:
            etf_pool_source = st.selectbox("ETF 池来源", MARGIN_ETF_POOL_MODES, index=0, key="margin_etf_pool_source")
        with pool_col2:
            compare_theme = st.selectbox(
                "主题选择",
                COMPARISON_THEMES,
                index=0,
                key="margin_etf_compare_theme",
                disabled=etf_pool_source != "同赛道横向比较",
            )
        with pool_col3:
            dynamic_max_per_theme = st.selectbox(
                "每主题候选上限",
                [3, 4, 5, 6, 8],
                index=2,
                key="margin_etf_dynamic_max_per_theme",
            )

        min_amount_ma20 = st.number_input(
            "成交额 MA20 最低门槛（万元，可选）",
            min_value=0.0,
            value=0.0,
            step=5000.0,
            key="margin_etf_min_amount_ma20",
            help="仅用于动态全量发现/同赛道比较的候选筛选；填 0 表示不过滤。",
        )

        margin_etf_daily_packet_key = "legacy_margin_etf_daily_packet"
        margin_etf_daily_params = {
            "pool_source": etf_pool_source,
            "compare_theme": compare_theme if etf_pool_source == "同赛道横向比较" else "",
            "dynamic_max_per_theme": int(dynamic_max_per_theme),
            "min_amount_ma20": float(min_amount_ma20 or 0.0),
        }
        margin_etf_daily_params_hash = hashlib.sha256(
            json.dumps(margin_etf_daily_params, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        def build_margin_etf_daily_packet(refresh_token):
            packet_theme_comparison = {}
            packet_holdings_snapshot = {}
            if etf_pool_source == "Tushare 全量发现":
                dynamic_packet = cached_margin_etf_dynamic_packet(
                    refresh_token=refresh_token,
                    max_per_theme=dynamic_max_per_theme,
                    min_amount_ma20=min_amount_ma20,
                )
                packet_daily_dataset = dynamic_packet.get("data_status") or {}
                packet_score_packet = dynamic_packet.get("score_packet") or {"rows": []}
                packet_universe = dynamic_packet.get("universe") or get_default_etf_universe()
            elif etf_pool_source == "同赛道横向比较":
                dynamic_packet = cached_margin_etf_dynamic_packet(
                    refresh_token=refresh_token,
                    theme_label=compare_theme,
                    max_per_theme=max(dynamic_max_per_theme, 8),
                    min_amount_ma20=min_amount_ma20,
                )
                packet_daily_dataset = dynamic_packet.get("data_status") or {}
                packet_score_packet = dynamic_packet.get("score_packet") or {"rows": []}
                packet_universe = dynamic_packet.get("universe") or get_default_etf_universe()
                packet_theme_comparison = dynamic_packet.get("theme_comparison") or {}
                comparison_codes = [
                    row.get("etf_code")
                    for row in (packet_theme_comparison.get("rows") or [])
                    if row.get("etf_code")
                ][:8]
                packet_holdings_snapshot = cached_margin_etf_holdings_snapshot(
                    refresh_token=refresh_token,
                    etf_codes=comparison_codes,
                )
            elif etf_pool_source == "人工重点关注池":
                packet_universe = [item for item in get_default_etf_universe() if item.get("manual_focus", True)]
                packet_daily_dataset = cached_margin_etf_daily_dataset(refresh_token, "manual_focus", "")
                packet_score_packet = score_etf_universe(packet_daily_dataset)
            else:
                packet_universe = get_default_etf_universe()
                packet_daily_dataset = cached_margin_etf_daily_dataset(refresh_token, "core", "")
                packet_score_packet = score_etf_universe(packet_daily_dataset)
            return {
                "params_hash": margin_etf_daily_params_hash,
                "params": margin_etf_daily_params,
                "refresh_token": refresh_token,
                "daily_dataset": packet_daily_dataset,
                "score_packet": packet_score_packet,
                "current_universe": packet_universe,
                "theme_comparison": packet_theme_comparison,
                "holdings_snapshot": packet_holdings_snapshot,
                "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            }

        action_col1, action_col2, action_col3 = st.columns(3)
        margin_etf_refreshed_now = False
        with action_col1:
            if st.button("刷新 Tushare ETF 日线数据", key="btn_margin_etf_refresh_daily", width="stretch"):
                token = datetime.datetime.now().isoformat(timespec="seconds")
                st.session_state["margin_etf_daily_refresh_token"] = token
                with st.spinner("正在刷新 Tushare ETF 日线数据..."):
                    st.session_state[margin_etf_daily_packet_key] = build_margin_etf_daily_packet(token)
                    margin_etf_refreshed_now = True
                st.session_state.pop("margin_etf_intraday_snapshot", None)
        with action_col2:
            if st.button("刷新盘中 ETF 实时数据", key="btn_margin_etf_refresh_intraday", width="stretch"):
                token = datetime.datetime.now().isoformat(timespec="seconds")
                st.session_state["margin_etf_intraday_refresh_token"] = token
                intraday_mode = "dynamic" if etf_pool_source in {"Tushare 全量发现", "同赛道横向比较"} else ("manual_focus" if etf_pool_source == "人工重点关注池" else "core")
                intraday_theme = compare_theme if etf_pool_source == "同赛道横向比较" else ""
                st.session_state["margin_etf_intraday_snapshot"] = cached_margin_etf_intraday_dataset(token, intraday_mode, intraday_theme)
        with action_col3:
            if st.button("重新计算权宜比例", key="btn_margin_etf_recalc", width="stretch"):
                st.session_state["margin_etf_calc_refresh_token"] = datetime.datetime.now().isoformat(timespec="seconds")
                st.rerun()

        margin_etf_existing_packet = st.session_state.get(margin_etf_daily_packet_key) or {}
        margin_etf_status = (
            "使用缓存"
            if margin_etf_existing_packet.get("params_hash") == margin_etf_daily_params_hash
            else "未刷新"
        )
        if margin_etf_refreshed_now:
            margin_etf_status = "已刷新"
        margin_etf_source = (
            ((margin_etf_existing_packet.get("daily_dataset") or {}).get("data_source") or "")
            if margin_etf_status in {"已刷新", "使用缓存"}
            else ""
        )
        render_legacy_data_status(
            "融资 ETF",
            status=margin_etf_status,
            updated_at=margin_etf_existing_packet.get("updated_at", ""),
            data_source=margin_etf_source or "Tushare ETF 日线 / 本地规则评分",
        )

        input_col1, input_col2, input_col3 = st.columns(3)
        with input_col1:
            margin_total_asset = st.number_input("账户总资产", min_value=0.0, value=1000000.0, step=10000.0, key="margin_total_asset")
            margin_cash_balance = st.number_input("现金余额", min_value=0.0, value=200000.0, step=10000.0, key="margin_cash_balance")
            margin_stock_value = st.number_input("股票持仓市值", min_value=0.0, value=600000.0, step=10000.0, key="margin_stock_value")
            margin_etf_value = st.number_input("ETF 持仓市值", min_value=0.0, value=100000.0, step=10000.0, key="margin_etf_value")
        with input_col2:
            margin_debt = st.number_input("当前融资负债", min_value=0.0, value=100000.0, step=10000.0, key="margin_debt")
            available_margin = st.number_input(
                "可用保证金（可选）",
                min_value=0.0,
                value=0.0,
                step=10000.0,
                key="margin_available_margin",
                help="如果不清楚，可先保持 0，系统会按保守方式处理。",
            )
            maintenance_ratio = st.number_input(
                "当前维持担保比例（可选）",
                min_value=0.0,
                value=0.0,
                step=5.0,
                key="margin_maintenance_ratio",
                help="如未知可填 0；低于 180% 时会直接禁止新增融资。",
            )
            margin_interest_rate = st.number_input("融资年利率（%）", min_value=0.0, value=6.8, step=0.1, key="margin_interest_rate")
        with input_col3:
            max_drawdown_pct = st.selectbox("最大可接受回撤", [10, 15, 20], index=1, key="margin_max_drawdown")
            margin_style = st.selectbox("账户风格", ["防守", "平衡", "进攻"], index=1, key="margin_style")
            market_state_choice = st.selectbox("市场状态", ["弱势", "震荡", "强趋势", "极强趋势"], index=2, key="margin_market_state")
            leverage_mode = st.selectbox(
                "是否允许使用融资",
                ["不使用", "小幅使用", "中等使用", "火力全开，但默认关闭"],
                index=1,
                key="margin_leverage_mode",
            )

        margin_account = {
            "total_asset": float(st.session_state.get("margin_total_asset", margin_total_asset) or 0.0),
            "cash_balance": float(st.session_state.get("margin_cash_balance", margin_cash_balance) or 0.0),
            "stock_market_value": float(st.session_state.get("margin_stock_value", margin_stock_value) or 0.0),
            "etf_market_value": float(st.session_state.get("margin_etf_value", margin_etf_value) or 0.0),
            "margin_debt": float(st.session_state.get("margin_debt", margin_debt) or 0.0),
            "available_margin": float(st.session_state.get("margin_available_margin", available_margin) or 0.0),
            "maintenance_ratio": float(st.session_state.get("margin_maintenance_ratio", maintenance_ratio) or 0.0),
            "margin_interest_rate": float(st.session_state.get("margin_interest_rate", margin_interest_rate) or 0.0),
            "max_drawdown_pct": float(st.session_state.get("margin_max_drawdown", max_drawdown_pct) or 0.0),
        }
        margin_profile = {
            "style": st.session_state.get("margin_style", margin_style),
            "leverage_mode": st.session_state.get("margin_leverage_mode", leverage_mode),
        }

        refresh_token = st.session_state.get("margin_etf_daily_refresh_token", "base")
        theme_comparison = {}
        holdings_snapshot = {}
        daily_packet = st.session_state.get(margin_etf_daily_packet_key) or {}
        if daily_packet.get("params_hash") == margin_etf_daily_params_hash:
            daily_dataset = daily_packet.get("daily_dataset") or {}
            score_packet = daily_packet.get("score_packet") or {"rows": []}
            current_universe = daily_packet.get("current_universe") or get_default_etf_universe()
            theme_comparison = daily_packet.get("theme_comparison") or {}
            holdings_snapshot = daily_packet.get("holdings_snapshot") or {}
            st.caption(f"ETF 日线数据缓存时间：{daily_packet.get('updated_at') or '未知'}")
        else:
            current_universe = (
                [item for item in get_default_etf_universe() if item.get("manual_focus", True)]
                if etf_pool_source == "人工重点关注池"
                else get_default_etf_universe()
            )
            daily_dataset = {
                "data_source": "not_loaded",
                "status": "尚未刷新 Tushare ETF 日线数据",
                "errors": ["点击“刷新 Tushare ETF 日线数据”后生成。"],
                "sample_count": len(current_universe),
            }
            score_packet = {"rows": [], "data_source": "not_loaded"}
            st.info("ETF 日线数据尚未刷新。默认不拉取 Tushare，点击按钮后生成。")

        intraday_snapshot = st.session_state.get("margin_etf_intraday_snapshot")
        expected_intraday_mode = "dynamic" if etf_pool_source in {"Tushare 全量发现", "同赛道横向比较"} else ("manual_focus" if etf_pool_source == "人工重点关注池" else "core")
        expected_intraday_theme = compare_theme if etf_pool_source == "同赛道横向比较" else ""
        if intraday_snapshot and (
            intraday_snapshot.get("universe_mode") != expected_intraday_mode
            or (expected_intraday_theme and intraday_snapshot.get("theme_label") not in ["", expected_intraday_theme])
        ):
            intraday_snapshot = None

        etf_status_packet = dict(daily_dataset or {})
        if intraday_snapshot:
            etf_status_packet["used_realtime"] = bool((intraday_snapshot or {}).get("used_realtime"))
            etf_status_packet["latest_realtime_update"] = (intraday_snapshot or {}).get("updated_at", "")

        allocation_result = calculate_margin_etf_allocation(
            margin_account,
            market_state_choice,
            margin_profile,
            etf_scores=score_packet,
        )
        allocation_result["etf_universe_mode"] = etf_pool_source
        allocation_result["discovered_etf_count"] = etf_status_packet.get("discovered_etf_count") or etf_status_packet.get("sample_count") or len(current_universe)
        allocation_result["scored_etf_count"] = etf_status_packet.get("scored_etf_count") or len(score_packet.get("rows") or [])
        allocation_result["theme_comparison"] = theme_comparison
        allocation_result["holdings_snapshot"] = holdings_snapshot
        allocation_result["holdings_data_gaps"] = (
            holdings_snapshot.get("holdings_errors")
            or (["持仓明细暂不可用，当前仅按行情、跟踪指数和流动性比较。"] if etf_pool_source == "同赛道横向比较" else [])
        )
        allocation_result["generated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        st.session_state["legacy_margin_etf_allocation_result"] = clone_command_center_packet(allocation_result)
        st.session_state["command_center_etf_packet"] = legacy_packet_sync_service.sync_legacy_etf_packet(
            st.session_state,
            live_packet={
                "margin_etf": {
                    "updated_at": allocation_result.get("generated_at", ""),
                    "source": "融资 ETF 本地配置快照",
                }
            },
        )
        _remember_legacy_tool_packet_recovery_result(
            key="legacy_margin_etf",
            label="融资 ETF",
            writes_packet="command_center_etf_packet",
            target_tab="融资 ETF",
            target=target,
            position_profile=position_profile_preview,
        )

        account_risk_profile = {
            "account": margin_account,
            "risk_profile": margin_profile,
            "market_state": market_state_choice,
        }
        account_risk_profile_hash = hashlib.sha256(
            json.dumps(account_risk_profile, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        allocation_hash = build_margin_etf_allocation_hash(allocation_result)
        if st.session_state.get("margin_etf_research_allocation_hash") not in [None, allocation_hash]:
            st.session_state.pop("margin_etf_research_result", None)
            st.session_state.pop("margin_etf_research_generated_at", None)
            st.session_state.pop("margin_etf_research_cached", None)

        research_result = st.session_state.get("margin_etf_research_result")
        research_generated_at = st.session_state.get("margin_etf_research_generated_at", "")
        research_cached = bool(st.session_state.get("margin_etf_research_cached"))

        render_margin_allocator_module(
            allocation_result,
            get_etf_catalog_by_bucket(current_universe) or get_margin_etf_catalog(),
            etf_data_status=etf_status_packet,
            intraday_snapshot=intraday_snapshot,
            research_payload=research_result,
            research_generated_at=research_generated_at,
            research_cached=research_cached,
        )

        st.warning("同赛道 ETF 可能高度重叠，不应简单叠加配置。")
        st.warning("ETF 持仓会随季报/公告变化，Tushare 持仓数据可能有滞后，配置结论必须结合最新行情和风险线。")

        if etf_pool_source == "同赛道横向比较":
            st.markdown(f"#### 同主题 ETF 横向比较：{compare_theme}")
            render_theme_comparison_table(theme_comparison, holdings_snapshot=holdings_snapshot)
            render_holdings_snapshot_summary(holdings_snapshot)

        research_col1, research_col2 = st.columns([1, 1.2])
        with research_col1:
            force_research = st.checkbox("强制重新调研", value=False, key="margin_etf_force_research")
        with research_col2:
            if st.button("🧠 让 DeepSeek 调研本次 ETF 融资配置", key="btn_margin_etf_deepseek_research", width="stretch"):
                cached_payload = None
                cached_created_at = ""
                cache_error = ""
                if not force_research:
                    cached_payload, cache_error = load_margin_etf_research_cache(
                        allocation_result.get("data_date"),
                        account_risk_profile_hash,
                        market_state_choice,
                        allocation_hash,
                    )
                    cached_created_at = (cached_payload or {}).get("generated_at") or ""
                if cache_error:
                    st.caption(f"缓存读取告警：{cache_error}")
                if cached_payload and not force_research:
                    st.session_state["margin_etf_research_result"] = cached_payload.get("research_result") or cached_payload
                    st.session_state["margin_etf_research_generated_at"] = cached_created_at or cached_payload.get("generated_at", "")
                    st.session_state["margin_etf_research_cached"] = True
                    st.session_state["margin_etf_research_allocation_hash"] = allocation_hash
                    st.rerun()

                research_packet = {
                    "account_state": allocation_result.get("account_state"),
                    "margin_state": {
                        "current_margin_debt_ratio": allocation_result.get("current_margin_debt_ratio"),
                        "recommended_margin_ratio": allocation_result.get("recommended_margin_ratio"),
                        "action_state": allocation_result.get("action_state"),
                    },
                    "market_state": market_state_choice,
                    "risk_profile": margin_profile,
                    "etf_score_table": allocation_result.get("etf_score_table"),
                    "allocation_result": allocation_result,
                    "risk_lines": allocation_result.get("risk_lines"),
                    "data_date": allocation_result.get("data_date"),
                    "data_source": allocation_result.get("data_source"),
                    "etf_universe_mode": etf_pool_source,
                    "discovered_etf_count": allocation_result.get("discovered_etf_count"),
                    "scored_etf_count": allocation_result.get("scored_etf_count"),
                    "theme_comparison": theme_comparison,
                    "selected_etf_candidates": allocation_result.get("selected_etf_candidates"),
                    "holdings_snapshot": holdings_snapshot if holdings_snapshot.get("holdings_available") else {},
                    "holdings_data_gaps": allocation_result.get("holdings_data_gaps"),
                    "intraday_etf_snapshot": intraday_snapshot or {},
                }
                prompt = build_margin_etf_research_prompt(research_packet)
                raw_output = call_deepseek_non_stream(
                    prompt,
                    system_role="你是克制、专业的 ETF 两融配置解释员，只解释规则结果，不直接下交易指令。",
                    max_tokens=2200,
                )
                if raw_output:
                    parsed_payload, _ = parse_memory_payload(raw_output)
                    if not isinstance(parsed_payload, dict) or not parsed_payload:
                        parsed_payload = {
                            "one_sentence_conclusion": str(raw_output)[:80],
                            "today_allocation_explanation": [str(raw_output)],
                            "why_margin_ratio": [],
                            "bucket_adjustments": [],
                            "theme_comparison_explanation": [],
                            "overlap_and_substitution": [],
                            "watch_not_chase": [],
                            "add_margin_triggers": [],
                            "deleverage_triggers": [],
                            "tomorrow_checklist": [],
                            "data_gaps": ["DeepSeek 输出未严格命中 JSON，已按原文降级展示。"],
                            "risk_disclaimer": "融资会放大收益和亏损。本模块只做风险预算和仓位测算，不构成买卖建议。",
                        }
                    generated_at = datetime.datetime.now().isoformat(timespec="seconds")
                    cache_payload = {
                        "report_type": MARGIN_ETF_DAILY_RESEARCH_REPORT_TYPE,
                        "data_date": allocation_result.get("data_date"),
                        "account_risk_profile": account_risk_profile_hash,
                        "market_state": market_state_choice,
                        "allocation_hash": allocation_hash,
                        "generated_at": generated_at,
                        "research_result": parsed_payload,
                        "raw_output": raw_output,
                    }
                    save_stock_report(
                        _margin_etf_research_ticker(),
                        "A_SHARE",
                        MARGIN_ETF_DAILY_RESEARCH_REPORT_TYPE,
                        cache_payload,
                    )
                    st.session_state["margin_etf_research_result"] = parsed_payload
                    st.session_state["margin_etf_research_generated_at"] = generated_at
                    st.session_state["margin_etf_research_cached"] = False
                    st.session_state["margin_etf_research_allocation_hash"] = allocation_hash
                    st.rerun()

    if legacy_tab == "数据源体检":
        st.markdown("### ⚙️ 数据源与权限体检")
        st.caption("进入本页会按 TTL 自动检查连接、权限和返回行数；DeepSeek ping 默认不执行，不展示 token、secrets 或原始数据。")

        health_col1, health_col2, health_col3 = st.columns([1.2, 1, 1])
        with health_col1:
            health_sample_ts_code = st.text_input(
                "Tushare 样例股票",
                value="000001.SZ",
                key="health_sample_ts_code",
                help="仅用于权限体检的样例标的，不进入任何 DeepSeek prompt。",
            )
        with health_col2:
            health_ping_deepseek = st.checkbox(
                "执行 DeepSeek 极小连通测试",
                value=False,
                key="health_ping_deepseek",
                help="默认只统计 key 数量；勾选后会发起一次极小 ping 调用。",
            )
        with health_col3:
            st.caption("缓存 300 秒")
            if st.button("清除体检缓存", key="btn_clear_data_source_healthcheck_cache"):
                try:
                    run_data_source_healthcheck.clear()
                except Exception:
                    pass
                st.session_state.pop("last_data_source_healthcheck", None)
                st.success("已清除体检缓存。")

        health_ttl = st.session_state.get(
            legacy_a_share_auto_hydrate_service.TTL_KEY,
            legacy_a_share_auto_hydrate_service.DEFAULT_TTL_SECONDS,
        )
        health_fingerprint = f"legacy_data_source_health|{health_sample_ts_code}|{datetime.date.today().isoformat()}"
        health_last_fingerprint = st.session_state.get("legacy_data_source_health_fingerprint") or ""
        health_last_at = _num(st.session_state.get("legacy_data_source_health_last_at"), 0) or 0
        should_auto_healthcheck = (
            health_last_fingerprint != health_fingerprint
            or not health_last_at
            or (time.time() - float(health_last_at)) >= int(health_ttl or 600)
        )
        if should_auto_healthcheck:
            _run_legacy_a_share_provider_status_probe(health_sample_ts_code, "A股")
            st.session_state["legacy_data_source_health_fingerprint"] = health_fingerprint
            st.session_state["legacy_data_source_health_last_at"] = time.time()
        elif st.session_state.get("legacy_auto_hydrate_provider_status"):
            st.caption("本轮未重复体检：样例标的仍在 TTL 内。")

        provider_status = st.session_state.get("legacy_auto_hydrate_provider_status") or {}
        if provider_status.get("summary"):
            st.caption(f"数据源覆盖：{provider_status.get('summary')}")

        if st.button("强制体检", type="primary", key="btn_run_data_source_healthcheck", width="stretch"):
            with st.spinner("正在检查 Tushare、Supabase 和 DeepSeek 配置..."):
                st.session_state["last_data_source_healthcheck"] = run_data_source_healthcheck(
                    health_sample_ts_code,
                    health_ping_deepseek,
                    _supabase_client=supabase,
                    _deepseek_keys=ds_keys,
                )
                st.session_state["legacy_data_source_health_fingerprint"] = health_fingerprint
                st.session_state["legacy_data_source_health_last_at"] = time.time()

        health_result = st.session_state.get("last_data_source_healthcheck")
        if not health_result:
            st.info("尚未取得体检结果。可等待自动体检完成，或点击“强制体检”。")
        else:
            checked_at = health_result.get("checked_at", "")
            st.caption(f"最近体检时间：{checked_at}｜样例股票：{health_result.get('sample_ts_code', '')}")

            tushare_health = health_result.get("tushare") or {}
            supabase_health = health_result.get("supabase") or {}
            deepseek_health = health_result.get("deepseek") or {}

            card1, card2, card3 = st.columns(3)
            with card1:
                total = len(tushare_health.get("items") or [])
                st.metric(
                    "Tushare",
                    f"{tushare_health.get('ok_count', 0)}/{total} 可用",
                    f"疑似权限不足 {tushare_health.get('permission_denied_count', 0)}",
                )
            with card2:
                total = len(supabase_health.get("items") or [])
                st.metric(
                    "Supabase",
                    f"{supabase_health.get('ok_count', 0)}/{total} 可连接",
                    f"失败 {supabase_health.get('failed_count', 0)}",
                )
            with card3:
                st.metric(
                    "DeepSeek",
                    deepseek_health.get("status", "未知"),
                    f"key_count {deepseek_health.get('key_count', 0)}",
                )

            st.markdown("#### Tushare 接口权限")
            tushare_items = tushare_health.get("items") or []
            if tushare_items:
                tushare_df = pd.DataFrame(tushare_items)
                display_columns = [
                    "api",
                    "status",
                    "capability_state",
                    "ok",
                    "rows",
                    "latest_date",
                    "latency_ms",
                    "permission_likely",
                    "action_hint",
                    "error",
                ]
                display_columns = [column for column in display_columns if column in tushare_df.columns]
                st.dataframe(tushare_df[display_columns], width="stretch", hide_index=True)
            else:
                st.warning("暂无 Tushare 体检结果。")

            st.markdown("#### Supabase 表连接")
            supabase_items = supabase_health.get("items") or []
            if supabase_items:
                supabase_df = pd.DataFrame(supabase_items)
                st.dataframe(
                    supabase_df[["table", "status", "ok", "rows", "count", "latency_ms", "error"]],
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.warning("暂无 Supabase 体检结果。")

            st.markdown("#### DeepSeek 配置")
            deepseek_display = {
                "status": deepseek_health.get("status", ""),
                "ok": deepseek_health.get("ok", False),
                "key_count": deepseek_health.get("key_count", 0),
                "ping_enabled": deepseek_health.get("ping_enabled", False),
                "latency_ms": deepseek_health.get("latency_ms", 0),
                "error": deepseek_health.get("error", ""),
            }
            st.table(pd.DataFrame([deepseek_display]))

    # ------------------ 下一票作战雷达：规则优先，深度研究手动触发 ------------------
    if legacy_tab == "下一票雷达":
        radar_callbacks = {
            "compute_technical_snapshot": compute_technical_snapshot,
            "get_current_price_detail": get_current_price_detail,
            "build_tianyan_risk_fact_packet": build_tianyan_risk_fact_packet,
            "build_local_risk_radar_items": build_local_risk_radar_items,
            "load_announcement_watchlist": load_announcement_watchlist,
            "call_deepseek_non_stream": call_deepseek_non_stream,
            "tushare_adapter": _tushare_adapter,
        }
        render_next_ticket_radar(
            supabase=supabase,
            current_ticker=target,
            current_name="",
            current_price=price,
            position_profile=position_profile_preview,
            callbacks=radar_callbacks,
        )
        if st.session_state.get("radar_scan_results"):
            st.session_state["command_center_radar_packet"] = legacy_packet_sync_service.sync_legacy_radar_packet(
                st.session_state,
                live_packet={
                    "next_ticket": {
                        "updated_at": st.session_state.get("radar_scan_finished_at", ""),
                        "source": "下一票雷达本地缓存快照",
                    }
                },
            )
            _remember_legacy_tool_packet_recovery_result(
                key="legacy_next_ticket_radar",
                label="下一票雷达",
                writes_packet="command_center_radar_packet",
                target_tab="下一票雷达",
                target=target,
                position_profile=position_profile_preview,
            )
    # 模块 D：云端外脑
    if legacy_tab == "云端外脑":
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
        st.caption("默认不自动读取 Supabase 记忆档案；点击按钮后加载，避免进入旧版外脑时卡顿。")

        if st.button("读取云端记忆档案", key="btn_load_cloud_memories", width="stretch"):
            with st.spinner("正在链接 Supabase 云端突触..."):
                st.session_state["legacy_cloud_memories"] = get_all_cloud_memories()
                st.session_state["legacy_cloud_memories_loaded_at"] = datetime.datetime.now().isoformat(timespec="seconds")

        memories = st.session_state.get("legacy_cloud_memories")
        if memories is None:
            st.info("尚未读取云端记忆档案。点击按钮后显示最近的策略、复盘和投喂记忆。")
        elif memories:
            st.caption(f"最近读取时间：{st.session_state.get('legacy_cloud_memories_loaded_at', '未知')}")
            for m in memories:
                render_feed_extract_card(
                    m.get("content", ""),
                    memory_type=m.get("memory_type", "memory"),
                    raw_payload=m.get("content", ""),
                    card_title=f"云端记忆 #{m.get('id', '')}",
                )
        else:
            st.info("📭 当前云端神经元为空，请在上方投喂你的第一条交易纪律。")
