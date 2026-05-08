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


def render_recent_sentiment_module(news_rows):
    st.markdown("#### 近48小时舆情过滤")
    if not news_rows:
        st.info("近48小时暂无高相关舆情。")
        return

    df = pd.DataFrame(news_rows)
    cols = [c for c in ["relevance_score", "keyword", "title", "sentiment", "risk_tag", "created_at", "url"] if c in df.columns]
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
    c1, c2, c3 = st.columns(3)
    c1.metric("资金面倾向", summary.get("stance", "中性"))
    c2.metric("正面信号", len(summary.get("positive", [])))
    c3.metric("负面信号", len(summary.get("negative", [])))

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


def _fmt(value):
    try:
        if value is None:
            return "N/A"
        return round(float(value), 2)
    except Exception:
        return "N/A"
