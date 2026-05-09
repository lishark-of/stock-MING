import pandas as pd
import streamlit as st


def render_supply_chain_module(profile, portfolio_health):
    st.markdown("#### 产业链地位与联动")
    c1, c2, c3 = st.columns(3)
    c1.metric("主题", profile.get("theme", "未知"))
    c2.metric("产业链位置", profile.get("position", "待确认"))
    c3.metric("联动票数量", len(profile.get("a_share_links", [])))

    st.caption(profile.get("risk_transmission", "暂无传导说明"))

    link_rows = profile.get("a_share_links", [])
    if link_rows:
        st.dataframe(pd.DataFrame(link_rows), use_container_width=True, hide_index=True)

    corr = portfolio_health.get("correlation")
    if corr is not None and not corr.empty:
        st.markdown("##### 相关性表")
        st.dataframe(corr, use_container_width=True)


def render_valuation_module(valuation):
    st.markdown("#### 估值回归与现金流")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PE(TTM)", _fmt(valuation.get("trailing_pe")))
    c2.metric("Forward PE", _fmt(valuation.get("forward_pe")))
    c3.metric("PB", _fmt(valuation.get("pb")))
    c4.metric("FCF Yield", f"{valuation.get('fcf_yield')}%" if valuation.get("fcf_yield") is not None else "N/A")
    st.info(f"估值标签：{valuation.get('valuation_flag', '未知')}")


def render_technical_module(technical):
    st.markdown("#### 实时技术指标")
    if not technical or technical.get("confidence", 0) <= 0:
        st.warning("实时价格、MA60、RSI 或成交量暂不可用。")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("收盘价", _fmt(technical.get("latest_close")))
    c2.metric("MA60状态", technical.get("ma60_state", "未知"), _fmt(technical.get("ma60")))
    c3.metric("RSI-14", _fmt(technical.get("rsi")))
    c4.metric("量能/20日", _fmt(technical.get("volume_vs_20d")))

    c5, c6, c7 = st.columns(3)
    c5.metric("20日涨跌", f"{technical.get('return_20d')}%" if technical.get("return_20d") is not None else "N/A")
    c6.metric("60日涨跌", f"{technical.get('return_60d')}%" if technical.get("return_60d") is not None else "N/A")
    c7.metric("60日回撤", f"{technical.get('drawdown_60d')}%" if technical.get("drawdown_60d") is not None else "N/A")
    if technical.get("drawdown") is not None:
        st.caption(f"距离近两年高点回撤：{technical.get('drawdown')}%")

    st.caption(f"行情日期：{technical.get('data_asof') or '未知'}｜技术面可信度：{technical.get('confidence', 0)}")
    if technical.get("missing"):
        st.warning("缺失：" + "、".join(technical.get("missing", [])))


def render_scenario_module(scenario):
    st.markdown("#### Monte Carlo 情景区间")
    if not scenario or scenario.get("confidence", 0) <= 0:
        st.warning("历史样本不足，暂不能生成量化情景区间。")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("基准价", _fmt(scenario.get("base_price")))
    c2.metric("悲观P10", _fmt(scenario.get("p10")))
    c3.metric("中性P50", _fmt(scenario.get("p50")))
    c4.metric("乐观P90", _fmt(scenario.get("p90")))

    c5, c6, c7 = st.columns(3)
    c5.metric("上涨概率", f"{scenario.get('probability_positive_pct')}%")
    c6.metric("跌超10%概率", f"{scenario.get('probability_down_10_pct')}%")
    c7.metric("年化波动", f"{scenario.get('annualized_volatility_pct')}%")
    st.caption(f"周期：{scenario.get('horizon_days')}个交易日｜模拟次数：{scenario.get('simulations')}｜数据日期：{scenario.get('data_asof')}")


def render_recent_sentiment_module(news_rows):
    st.markdown("#### 近48小时舆情过滤")
    if not news_rows:
        st.info("近48小时暂无高相关舆情。")
        return

    df = pd.DataFrame(news_rows)
    cols = [c for c in ["relevance_score", "market_filter", "filter_reason", "keyword", "title", "sentiment", "risk_tag", "created_at", "url"] if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)


def render_portfolio_health_module(portfolio_health):
    st.markdown("#### 模拟持仓体检")
    metrics = portfolio_health.get("metrics") or {}
    if not metrics:
        st.info("暂无足够历史数据做持仓体检。")
        return

    df = pd.DataFrame(metrics).T.reset_index().rename(columns={"index": "ticker"})
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_risk_decision(decision):
    st.markdown("#### 严格止损 / 禁止买入")
    score = decision.get("risk_score", 0)
    action = decision.get("action", "允许继续分析")
    if action.startswith("禁止"):
        st.error(f"{action}｜风险分 {score}")
    elif "谨慎" in action:
        st.warning(f"{action}｜风险分 {score}")
    else:
        st.success(f"{action}｜风险分 {score}")

    for reason in decision.get("reasons", []):
        st.caption(f"- {reason}")


def render_money_flow_module(flow):
    st.markdown("#### 资金面深度调查")
    if not flow:
        st.info("暂无资金面数据。")
        return

    summary = flow.get("summary") or {}
    coverage = flow.get("coverage") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("资金面倾向", summary.get("stance", "中性"))
    c2.metric("正面信号", len(summary.get("positive", [])))
    c3.metric("负面信号", len(summary.get("negative", [])))
    c4.metric("覆盖度", f"{coverage.get('score', 0)}%" if coverage else "N/A")

    for item in summary.get("positive", []):
        st.success(item)
    for item in summary.get("negative", []):
        st.warning(item)

    for key, label in [
        ("institutional_holders", "13F/机构持仓"),
        ("insider_transactions", "内部交易"),
        ("individual_fund_flow", "A股个股资金流"),
        ("dragon_tiger", "龙虎榜"),
        ("block_trade", "大宗交易"),
        ("etf_proxy_flow", "ETF代理资金温度"),
    ]:
        rows = flow.get(key)
        if rows:
            with st.expander(label, expanded=False):
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if flow.get("options_signal"):
        with st.expander("期权异动", expanded=False):
            st.json(flow["options_signal"])

    for warning in flow.get("warnings", []):
        st.caption(f"数据提示：{warning}")


def render_data_quality_module(report):
    st.markdown("#### 数据可信度")
    if not report:
        st.warning("暂无数据可信度报告。")
        return

    score = report.get("score", 0)
    grade = report.get("grade", "未知")
    if score >= 80:
        st.success(f"可信度：{grade}｜{score}/100")
    elif score >= 55:
        st.warning(f"可信度：{grade}｜{score}/100")
    else:
        st.error(f"可信度：{grade}｜{score}/100")
    st.caption(report.get("instruction", ""))

    for item in report.get("missing", []):
        st.caption(f"- {item}")
    for item in report.get("warnings", []):
        st.caption(f"数据接口提示：{item}")


def render_peer_snapshot(peer_rows):
    st.markdown("#### 同行公司数据对比")
    if not peer_rows:
        st.info("暂无可用同行估值对比。")
        return
    st.dataframe(pd.DataFrame(peer_rows), use_container_width=True, hide_index=True)


def render_research_links(links):
    st.markdown("#### 深度信息挖掘入口")
    if not links:
        st.info("暂无深度信息入口。")
        return
    for link in links:
        st.markdown(f"- [公开检索]({link})")


def render_backtest_report(report):
    st.markdown("#### 回测结果卡")
    if not report:
        st.warning("暂无回测报告。")
        return

    metrics = report.get("metrics", {}) or {}
    latest_signal = report.get("latest_signal", {}) or {}
    position_context = report.get("position_context", {}) or {}

    summary = report.get("summary", "")
    action = latest_signal.get("action", "继续观察")
    if any(word in action for word in ["禁止", "止损", "退出", "减仓"]):
        st.error(summary or action)
    elif any(word in action for word in ["观察", "防守"]):
        st.warning(summary or action)
    else:
        st.success(summary or action)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("总收益", _pct(metrics.get("total_return_pct")))
    c2.metric("年化收益", _pct(metrics.get("annual_return_pct")))
    c3.metric("夏普", _fmt(metrics.get("sharpe")))
    c4.metric("最大回撤", _pct(metrics.get("max_drawdown_pct")))
    c5.metric("胜率", _pct(metrics.get("win_rate_pct")))
    c6.metric("交易次数", metrics.get("trade_count", 0))

    p1, p2, p3 = st.columns(3)
    p1.metric("当前信号", action)
    p2.metric("相对成本", position_context.get("state", "未输入成本价"))
    p3.metric("最新信号日", latest_signal.get("date", ""))
    if latest_signal.get("reason"):
        st.caption(f"信号原因：{latest_signal.get('reason')}")

    equity_curve = report.get("equity_curve")
    if equity_curve is not None and not equity_curve.empty:
        chart_df = equity_curve.copy()
        if "date" in chart_df.columns:
            chart_df["date"] = pd.to_datetime(chart_df["date"], errors="coerce")
            chart_df = chart_df.dropna(subset=["date"]).set_index("date")
        if "equity" in chart_df.columns:
            st.line_chart(chart_df[["equity"]], use_container_width=True)

    trades = report.get("trades")
    if trades is not None and not trades.empty:
        with st.expander("交易明细", expanded=False):
            show = trades.copy()
            if "date" in show.columns:
                show["date"] = show["date"].astype(str)
            st.dataframe(show, use_container_width=True, hide_index=True)
    else:
        st.info("这段历史里没有触发完整买卖交易，说明规则偏保守或样本不足。")

    signals = report.get("signals")
    if signals is not None and not signals.empty:
        with st.expander("最近信号", expanded=False):
            cols = [col for col in ["date", "close", "ma_mid", "ma_slow", "rsi", "volume_ratio_20", "signal", "signal_reason"] if col in signals.columns]
            show = signals[cols].tail(20).copy()
            if "date" in show.columns:
                show["date"] = show["date"].astype(str)
            st.dataframe(show, use_container_width=True, hide_index=True)


def _fmt(value):
    try:
        if value is None:
            return "N/A"
        return round(float(value), 2)
    except Exception:
        return "N/A"


def _pct(value):
    try:
        if value is None:
            return "N/A"
        return f"{float(value):.2f}%"
    except Exception:
        return "N/A"
