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
        st.dataframe(pd.DataFrame(link_rows), width="stretch", hide_index=True)

    corr = portfolio_health.get("correlation")
    if corr is not None and not corr.empty:
        st.markdown("##### 相关性表")
        st.dataframe(corr, width="stretch")


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
    st.dataframe(df[cols], width="stretch", hide_index=True)


def render_portfolio_health_module(portfolio_health):
    st.markdown("#### 模拟持仓体检")
    metrics = portfolio_health.get("metrics") or {}
    if not metrics:
        st.info("暂无足够历史数据做持仓体检。")
        return

    df = pd.DataFrame(metrics).T.reset_index().rename(columns={"index": "ticker"})
    st.dataframe(df, width="stretch", hide_index=True)


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
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

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


def render_freshness_module(report):
    st.markdown("#### 数据新鲜度")
    if not report:
        st.warning("暂无数据新鲜度报告。")
        return

    score = report.get("score", 0)
    grade = report.get("grade", "未知")
    if score >= 80:
        st.success(f"新鲜度：{grade}｜{score}/100")
    elif score >= 55:
        st.warning(f"新鲜度：{grade}｜{score}/100")
    else:
        st.error(f"新鲜度：{grade}｜{score}/100")

    st.caption(report.get("instruction", ""))
    rows = report.get("items", [])
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    for warning in report.get("warnings", []):
        st.caption(f"提示：{warning}")


def render_peer_snapshot(peer_rows):
    st.markdown("#### 同行公司数据对比")
    if not peer_rows:
        st.info("暂无可用同行估值对比。")
        return
    st.dataframe(pd.DataFrame(peer_rows), width="stretch", hide_index=True)


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
    trader_brief = report.get("trader_brief", {}) or {}

    summary = trader_brief.get("plain_summary") or report.get("summary", "")
    action = trader_brief.get("action") or latest_signal.get("action", "继续观察")
    if any(word in action for word in ["禁止", "止损", "退出", "减仓"]):
        st.error(summary or action)
    elif any(word in action for word in ["观察", "防守"]):
        st.warning(summary or action)
    else:
        st.success(summary or action)

    if trader_brief.get("warnings"):
        with st.expander("为什么这样说", expanded=True):
            st.markdown(trader_brief.get("explanation", ""))
            for item in trader_brief.get("warnings", []):
                st.caption(f"- {item}")
            st.markdown("##### 下一步")
            for item in trader_brief.get("next_steps", []):
                st.caption(f"- {item}")

    c1, c2, c3 = st.columns(3)
    c1.metric("策略收益", _pct(metrics.get("total_return_pct")))
    c2.metric("最大回撤", _pct(metrics.get("max_drawdown_pct")))
    c3.metric("退出动作数", metrics.get("exit_action_count", metrics.get("trade_count", 0)))

    c4, c5, c6 = st.columns(3)
    c4.metric("退出动作胜率", _pct(metrics.get("exit_action_win_rate", metrics.get("win_rate_pct"))))
    c5.metric("完整交易胜率", _pct(metrics.get("round_trip_win_rate")))
    c6.metric("完整交易数", metrics.get("round_trip_count", 0))

    c7, c8, c9 = st.columns(3)
    c7.metric("夏普", _fmt(metrics.get("sharpe")))
    c8.metric("平均持仓天数", _fmt(metrics.get("avg_holding_days")))
    c9.metric("样本天数", report.get("data_points", trader_brief.get("sample_days", 0)))

    c10, c11, c12 = st.columns(3)
    c10.metric("盈亏比", _fmt(metrics.get("profit_factor")))
    c11.metric("最大单笔亏损", _pct(metrics.get("max_single_trade_loss")))
    c12.metric("REDUCE次数", metrics.get("reduce_count", 0))
    st.caption("退出动作胜率包含 SELL / TAKE_PROFIT / REDUCE；完整交易胜率只统计 BUY 到最终 SELL / TAKE_PROFIT 的闭环交易。")

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
            st.line_chart(chart_df[["equity"]], width="stretch")

    trades = report.get("trades")
    if trades is not None and not trades.empty:
        with st.expander("交易明细", expanded=False):
            show = trades.copy()
            if "date" in show.columns:
                show["date"] = show["date"].astype(str)
            if "pnl_pct" in show.columns:
                show["pnl_pct"] = pd.to_numeric(show["pnl_pct"], errors="coerce")
            st.dataframe(show, width="stretch", hide_index=True)
    else:
        st.info("这段历史里没有触发完整买卖交易，说明规则偏保守或样本不足。")

    signals = report.get("signals")
    if signals is not None and not signals.empty:
        with st.expander("最近信号", expanded=False):
            cols = [col for col in ["date", "close", "ma_mid", "ma_slow", "rsi", "volume_ratio_20", "signal", "signal_reason"] if col in signals.columns]
            show = signals[cols].tail(20).copy()
            if "date" in show.columns:
                show["date"] = show["date"].astype(str)
            st.dataframe(show, width="stretch", hide_index=True)


def build_trade_explanation_summary(multi_result, position_profile=None):
    reports = (multi_result or {}).get("reports", {}) or {}
    rows = []
    for mode, report in reports.items():
        metrics = report.get("metrics", {}) or {}
        rows.append({
            "mode": mode,
            "label": report.get("mode_label", mode),
            "total": _num(metrics.get("total_return_pct"), 0) or 0,
            "dd": _num(metrics.get("max_drawdown_pct"), 0) or 0,
            "trades": int(_num(metrics.get("trade_count"), 0) or 0),
            "sharpe": _num(metrics.get("sharpe"), 0) or 0,
        })
    if not rows:
        return "暂无足够回测数据生成交易解释摘要。"

    best_return = max(rows, key=lambda row: row["total"])
    best_dd = max(rows, key=lambda row: row["dd"])
    most_trades = max(rows, key=lambda row: row["trades"])
    least_trades = min(rows, key=lambda row: row["trades"])
    dynamic = next((row for row in rows if row["mode"] == "dynamic"), None)
    free = next((row for row in rows if row["mode"] == "free"), None)
    tech = next((row for row in rows if row["mode"] == "tech_growth"), None)

    if max(row["trades"] for row in rows) == 0:
        style = "只观察"
        style_reason = "多种模式都没有形成有效交易，不能把“无交易”误解成策略无效，更适合作为趋势体检。"
    elif tech and tech["total"] >= best_return["total"] - 3 and tech["dd"] >= best_dd["dd"] - 3:
        style = "科技成长"
        style_reason = "科技成长股模式在趋势持有上叠加回撤风控，收益和回撤更接近均衡。"
    elif free and free["total"] >= best_return["total"] - 1 and free["dd"] > -22:
        style = "趋势跟随"
        style_reason = "自由趋势模式能接住主要行情，说明这只票更吃趋势延续。"
    elif dynamic and (dynamic["dd"] >= best_dd["dd"] or dynamic["total"] >= best_return["total"] - 3):
        style = "动态止盈"
        style_reason = "动态止盈止损对收益/回撤更均衡，适合用移动止盈保护利润。"
    elif best_dd["dd"] > -12:
        style = "机械止损"
        style_reason = "回撤控制优先级较高，固定纪律比追求弹性更重要。"
    else:
        style = "只观察"
        style_reason = "收益和回撤质量不够稳定，先把它作为观察样本。"

    pnl_pct = (position_profile or {}).get("pnl_pct")
    intent = (position_profile or {}).get("position_intent")
    position_note = ""
    if pnl_pct is not None and pnl_pct >= 20:
        position_note = " 当前相对成本浮盈较大，优先用动态止盈/分批减仓保护利润；不要把“回测无交易”误解成策略无效，也不建议因为高位强势重新追高开仓。"
    elif intent == "new":
        position_note = " 未买入时重点不是止盈止损，而是等回踩、突破确认和失效条件同时清楚。"
    elif intent == "add":
        position_note = " 想加仓时只看回踩加仓或突破确认加仓，若偏离均线过大就只持有不加。"

    return (
        f"交易解释摘要：收益最好的是 {best_return['label']}（{best_return['total']}%）；"
        f"最大回撤最小的是 {best_dd['label']}（{best_dd['dd']}%）；"
        f"交易次数最多的是 {most_trades['label']}（{most_trades['trades']} 次），"
        f"最少的是 {least_trades['label']}（{least_trades['trades']} 次）。"
        f"综合看更偏向“{style}”：{style_reason}{position_note}"
    )


def render_multi_mode_backtest(multi_result):
    st.markdown("#### 多模式回测对照")
    if not multi_result:
        st.warning("暂无多模式回测结果。")
        return

    reports = multi_result.get("reports", {}) or {}
    summary = multi_result.get("summary", "")
    if summary:
        st.info(summary)

    rows = []
    for mode, report in reports.items():
        metrics = report.get("metrics", {}) or {}
        latest = report.get("latest_signal", {}) or {}
        brief = report.get("trader_brief", {}) or {}
        rows.append({
            "模式": report.get("mode_label", mode),
            "策略收益": _pct(metrics.get("total_return_pct")),
            "最大回撤": _pct(metrics.get("max_drawdown_pct")),
            "退出动作数": metrics.get("exit_action_count", metrics.get("trade_count", 0)),
            "退出动作胜率": _pct(metrics.get("exit_action_win_rate", metrics.get("win_rate_pct"))),
            "完整交易数": metrics.get("round_trip_count", 0),
            "完整交易胜率": _pct(metrics.get("round_trip_win_rate")),
            "平均完整收益": _pct(metrics.get("avg_round_trip_return")),
            "盈亏比": _fmt(metrics.get("profit_factor")),
            "平均持仓天数": _fmt(metrics.get("avg_holding_days")),
            "最大单笔亏损": _pct(metrics.get("max_single_trade_loss")),
            "REDUCE次数": metrics.get("reduce_count", 0),
            "夏普": _fmt(metrics.get("sharpe")),
            "当前信号": brief.get("action") or latest.get("action", "继续观察"),
            "状态总结": brief.get("verdict", ""),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    explanation = multi_result.get("trade_explanation")
    if not explanation:
        explanation = build_trade_explanation_summary(multi_result, multi_result.get("position_profile"))
    st.markdown("#### 交易解释摘要")
    st.info(explanation)

    if reports:
        chart_parts = []
        for mode, report in reports.items():
            curve = report.get("equity_curve")
            if curve is None or curve.empty or "equity" not in curve.columns:
                continue
            label = report.get("mode_label", mode)
            part = curve[["date", "equity"]].copy()
            part["date"] = pd.to_datetime(part["date"], errors="coerce")
            part = part.dropna(subset=["date"]).set_index("date").rename(columns={"equity": label})
            chart_parts.append(part[[label]])
        if chart_parts:
            chart_df = pd.concat(chart_parts, axis=1).sort_index()
            st.line_chart(chart_df, width="stretch")

    tabs = st.tabs([report.get("mode_label", mode) for mode, report in reports.items()]) if reports else []
    for tab, (mode, report) in zip(tabs, reports.items()):
        with tab:
            render_backtest_report(report)


def _fmt(value):
    try:
        if value is None:
            return "N/A"
        return round(float(value), 2)
    except Exception:
        return "N/A"


def _num(value, default=None):
    try:
        if value is None or value == "":
            return default
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _pct(value):
    try:
        if value is None:
            return "N/A"
        return f"{float(value):.2f}%"
    except Exception:
        return "N/A"
