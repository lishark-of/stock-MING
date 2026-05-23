from __future__ import annotations

import math
from html import escape
from textwrap import dedent

import streamlit as st

try:
    import plotly.graph_objects as go
except Exception:  # pragma: no cover - runtime fallback for missing optional dependency
    go = None


SAFE_ACTION_STATES = {
    "允许观察",
    "等待验证",
    "条件触发",
    "暂不建议",
    "未触发",
    "风险升级",
    "谨慎允许",
}


def _to_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            text = (
                value.strip()
                .replace(",", "")
                .replace("¥", "")
                .replace("￥", "")
                .replace("%", "")
                .replace("亿", "")
            )
            if not text or text in {"暂无", "N/A", "None", "nan", "--"}:
                return default
            value = text
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except Exception:
        return default


def _fmt_price(value):
    number = _to_float(value)
    return "暂无" if number is None else f"¥{number:,.2f}"


def _fmt_money(value):
    number = _to_float(value)
    if number is None:
        return "暂无"
    if abs(number) >= 10000:
        return f"¥{number / 10000:,.2f} 万"
    return f"¥{number:,.2f}"


def _fmt_pct(value):
    number = _to_float(value)
    return "暂无" if number is None else f"{number:+.2f}%"


def _fmt_yi(value):
    number = _to_float(value)
    return "暂无" if number is None else f"{number:+.2f} 亿"


def _dedupe(items):
    result = []
    seen = set()
    for item in items or []:
        text = str(item or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _clean_html(markup):
    """Normalize HTML so Streamlit Markdown does not treat indented tags as code."""
    text = dedent(str(markup or "")).strip()
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _render_html(markup):
    html = _clean_html(markup)
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def _inject_component_css():
    _render_html(
        """
        <style>
        .vc-shell {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 18px;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
            padding: 14px 14px 12px;
            margin: 8px 0 10px;
        }
        .vc-title {
            font-size: 1rem;
            font-weight: 700;
            color: #111827;
            margin-bottom: 4px;
        }
        .vc-caption {
            color: #6b7280;
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: 5px;
        }
        .vc-metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
            gap: 8px;
            margin: 10px 0 6px;
        }
        .vc-metric {
            border-radius: 14px;
            background: rgba(249, 250, 251, 0.92);
            border: 1px solid rgba(17, 24, 39, 0.06);
            padding: 9px 10px;
            min-height: 62px;
        }
        .vc-label {
            color: #6b7280;
            font-size: 0.75rem;
            margin-bottom: 4px;
        }
        .vc-value {
            color: #111827;
            font-size: 1rem;
            font-weight: 720;
            line-height: 1.25;
            word-break: break-word;
        }
        .vc-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }
        .vc-badge {
            border-radius: 999px;
            padding: 6px 10px;
            font-size: 0.78rem;
            font-weight: 650;
            border: 1px solid rgba(17, 24, 39, 0.07);
        }
        .vc-green { background: #e8f7ef; color: #137a3f; }
        .vc-red { background: #fdecec; color: #b42318; }
        .vc-orange { background: #fff3e3; color: #b45309; }
        .vc-yellow { background: #fff9db; color: #8a5a00; }
        .vc-gray { background: #f3f4f6; color: #374151; }
        .vc-blue { background: #eaf2ff; color: #1d4ed8; }
        .vc-purple { background: #f1edff; color: #6d28d9; }
        .vc-status-row {
            border-radius: 14px;
            background: rgba(248, 250, 252, 0.92);
            border: 1px solid rgba(17, 24, 39, 0.06);
            padding: 9px 10px 10px;
            margin-top: 10px;
        }
        .vc-status-heading {
            color: #374151;
            font-size: 0.78rem;
            font-weight: 720;
            margin-bottom: 4px;
        }
        .vc-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(138px, 1fr));
            gap: 8px;
            margin-top: 10px;
        }
        .vc-action-card {
            border-radius: 18px;
            padding: 12px 12px 11px;
            border: 1px solid rgba(17, 24, 39, 0.06);
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
        }
        .vc-action-name {
            color: #111827;
            font-size: 0.95rem;
            font-weight: 720;
            margin-bottom: 7px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .vc-action-state {
            display: inline-block;
            border-radius: 999px;
            padding: 5px 9px;
            font-size: 0.78rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .vc-action-note {
            color: #4b5563;
            font-size: 0.78rem;
            line-height: 1.42;
        }
        .vc-icon {
            display: inline-flex;
            width: 22px;
            height: 22px;
            border-radius: 999px;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(17, 24, 39, 0.08);
            font-size: 0.82rem;
            font-weight: 800;
        }
        .vc-risk-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin: 12px 0 8px;
        }
        .vc-risk-card {
            border-radius: 18px;
            padding: 16px 14px;
            border: 1px solid rgba(17, 24, 39, 0.06);
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.07);
        }
        .vc-risk-count {
            font-size: 1.65rem;
            font-weight: 800;
            line-height: 1.1;
            color: #111827;
        }
        .vc-risk-label {
            color: #4b5563;
            font-size: 0.82rem;
            margin-top: 6px;
        }
        </style>
        """
    )


def _render_shell_start(title, caption="辅助判断，不构成买卖建议。"):
    _inject_component_css()
    _render_html(
        f"""
        <div class="vc-shell">
            <div class="vc-title">{escape(str(title))}</div>
            <div class="vc-caption">{escape(str(caption))}</div>
        </div>
        """
    )


def _metric_html(items):
    blocks = []
    for label, value in items:
        blocks.append(
            f"""
            <div class="vc-metric">
                <div class="vc-label">{escape(str(label))}</div>
                <div class="vc-value">{escape(str(value))}</div>
            </div>
            """
        )
    return _clean_html(f"<div class='vc-metric-grid'>{''.join(blocks)}</div>")


def _badge_html(text, color="gray"):
    return f"<span class='vc-badge vc-{escape(str(color))}'>{escape(str(text))}</span>"


def _action_color(state):
    return {
        "允许观察": "green",
        "等待验证": "yellow",
        "条件触发": "orange",
        "暂不建议": "gray",
        "未触发": "gray",
        "风险升级": "red",
        "谨慎允许": "blue",
    }.get(state, "gray")


def _state_card_html(name, state, note):
    if state not in SAFE_ACTION_STATES:
        state = "等待验证"
    color = _action_color(state)
    icon = {
        "加仓": "+",
        "持有": "◎",
        "做 T": "T",
        "减仓": "-",
        "清仓 / 退出观察": "!",
        "退出观察": "!",
    }.get(name, "•")
    return _clean_html(f"""
    <div class="vc-action-card vc-{color}">
        <div class="vc-action-name"><span class="vc-icon">{escape(icon)}</span>{escape(str(name))}</div>
        <div class="vc-action-state vc-{color}">{escape(str(state))}</div>
        <div class="vc-action-note">{escape(str(note))}</div>
    </div>
    """)


def render_position_waterline(
    current_price: float,
    cost_price: float | None = None,
    shares: int | float | None = None,
    chip_center: float | None = None,
    ma20: float | None = None,
    ma60: float | None = None,
    limit_up: float | None = None,
    limit_down: float | None = None,
    title: str = "持仓盈亏水位",
):
    """Render a fixed price-waterline component from structured facts only."""
    _inject_component_css()
    current = _to_float(current_price)
    cost = _to_float(cost_price)
    units = _to_float(shares)
    chip = _to_float(chip_center)
    ma20_value = _to_float(ma20)
    ma60_value = _to_float(ma60)
    up_limit = _to_float(limit_up)
    down_limit = _to_float(limit_down)

    if current is None:
        _render_html(
            f"""
            <div class="vc-shell">
                <div class="vc-title">{escape(str(title))}</div>
                <div class="vc-caption">当前价缺失，价格水位暂无法绘制；不构成买卖建议。</div>
                {_metric_html([("当前价", "暂无"), ("浮盈金额", "暂无"), ("浮盈比例", "暂无"), ("仓位市值", "暂无"), ("筹码位置", "暂无"), ("MA20 / MA60", "暂无")])}
            </div>
            """
        )
        st.info("当前价缺失，价格水位暂无法绘制。")
        return

    pnl_amount = None
    pnl_pct = None
    market_value = None
    if cost is not None and units is not None and units > 0:
        pnl_amount = (current - cost) * units
        pnl_pct = (current / cost - 1) * 100 if cost else None
        market_value = current * units
    elif cost is not None:
        pnl_pct = (current / cost - 1) * 100 if cost else None

    if chip is None:
        chip_status = "暂无"
    else:
        chip_gap = (current / chip - 1) * 100 if chip else None
        chip_status = f"{'上方' if current >= chip else '跌破'} {_fmt_pct(chip_gap)}"

    ma_status_parts = []
    if ma20_value is not None:
        ma20_gap = (current / ma20_value - 1) * 100 if ma20_value else None
        ma_status_parts.append(f"MA20 {'上方' if current >= ma20_value else '跌破'} {_fmt_pct(ma20_gap)}")
    if ma60_value is not None:
        ma60_gap = (current / ma60_value - 1) * 100 if ma60_value else None
        ma_status_parts.append(f"MA60 {'上方' if current >= ma60_value else '跌破'} {_fmt_pct(ma60_gap)}")
    ma_status = " / ".join(ma_status_parts) if ma_status_parts else "暂无"

    metrics = [
        ("当前价", _fmt_price(current)),
        ("浮盈金额", _fmt_money(pnl_amount)),
        ("浮盈比例", _fmt_pct(pnl_pct)),
        ("仓位市值", _fmt_money(market_value)),
        ("筹码位置", chip_status),
        ("MA20 / MA60", ma_status),
    ]

    status_badges = []
    if ma60_value is not None and current < ma60_value:
        status_badges.extend([_badge_html("跌破 MA60", "red"), _badge_html("风险升级观察", "red")])
    elif ma20_value is not None and current < ma20_value:
        status_badges.extend([_badge_html("跌破 MA20", "orange"), _badge_html("条件化减仓", "orange")])
    elif chip is not None and current < chip:
        status_badges.extend([_badge_html("跌破筹码中枢", "orange"), _badge_html("风险升级观察", "orange")])
    else:
        if cost is not None and current > cost:
            status_badges.append(_badge_html("浮盈保护区", "green"))
        if chip is not None and current >= chip:
            status_badges.append(_badge_html("筹码中枢上方", "purple"))
        status_badges.append(_badge_html("持有验证", "green"))
    if up_limit is not None and current >= up_limit * 0.97:
        status_badges.append(_badge_html("接近涨停，暂停追高加仓", "gray"))
    if not status_badges:
        status_badges.append(_badge_html("暂停追高加仓", "yellow"))

    _render_html(
        f"""
        <div class="vc-shell">
            <div class="vc-title">{escape(str(title))}</div>
            <div class="vc-caption">辅助判断，不构成买卖建议；加仓需要验证信号，减仓需要条件触发。</div>
            <div class="vc-status-row">
                <div class="vc-status-heading">当前状态</div>
                <div class="vc-badges">{''.join(status_badges)}</div>
            </div>
            {_metric_html(metrics)}
        </div>
        """
    )

    price_points = [
        value
        for value in [current, cost, chip, ma20_value, ma60_value, up_limit, down_limit]
        if value is not None and value > 0
    ]
    min_price = min(price_points)
    max_price = max(price_points)
    span = max(max_price - min_price, max(abs(current) * 0.08, 1))
    x_min = min(down_limit, min_price - span * 0.2) if down_limit is not None else min_price - span * 0.35
    x_max = max(up_limit, max_price + span * 0.2) if up_limit is not None else max_price + span * 0.35
    if x_min == x_max:
        x_min = current * 0.95
        x_max = current * 1.05

    if go is None:
        st.info("Plotly 未安装，价格水位图暂以指标卡降级展示。")
    else:
        fig = go.Figure()

        overheat_start = up_limit * 0.97 if up_limit is not None and up_limit > 0 else x_max - (x_max - x_min) * 0.14
        boundaries = [x_min, x_max]
        for value in [ma60_value, ma20_value, chip, cost, overheat_start]:
            if value is not None and x_min < value < x_max:
                boundaries.append(value)
        boundaries = sorted(set(round(value, 6) for value in boundaries))
        zone_style = {
            "风险区": ("#fdecec", "#b42318"),
            "修复区": ("#fff3e3", "#b45309"),
            "观察区": ("#fff9db", "#8a5a00"),
            "浮盈保护区": ("#e8f7ef", "#137a3f"),
            "追高风险区": ("#f3f4f6", "#374151"),
        }
        for left, right in zip(boundaries[:-1], boundaries[1:]):
            if right <= left:
                continue
            midpoint = (left + right) / 2
            if ma60_value is not None and midpoint < ma60_value:
                zone_name = "风险区"
            elif ma20_value is not None and midpoint < ma20_value:
                zone_name = "修复区"
            elif chip is not None and midpoint < chip:
                zone_name = "观察区"
            elif midpoint >= overheat_start:
                zone_name = "追高风险区"
            elif cost is not None and midpoint < cost and ma20_value is None and ma60_value is None:
                zone_name = "观察区"
            else:
                zone_name = "浮盈保护区"
            fill, font_color = zone_style[zone_name]
            fig.add_vrect(x0=left, x1=right, fillcolor=fill, opacity=0.62, line_width=0)
            if (right - left) / (x_max - x_min) >= 0.16:
                fig.add_annotation(
                    x=(left + right) / 2,
                    y=0.83,
                    xref="x",
                    yref="paper",
                    text=zone_name,
                    showarrow=False,
                    font=dict(size=11, color=font_color),
                )

        fig.add_shape(
            type="line",
            x0=x_min,
            x1=x_max,
            y0=0,
            y1=0,
            xref="x",
            yref="y",
            line=dict(color="#cbd5e1", width=6),
        )
        markers = [
            ("跌停", down_limit, "#fca5a5", 1, "dot", 0.10),
            ("涨停", up_limit, "#86efac", 1, "dot", 0.10),
            ("成本", cost, "#2563eb", 2, "solid", 0.94),
            ("筹码中枢", chip, "#7c3aed", 2, "solid", 1.02),
            ("MA20", ma20_value, "#d97706", 2, "solid", 0.86),
            ("MA60", ma60_value, "#4f46e5", 2, "solid", 0.78),
            ("当前价", current, "#111827", 4, "solid", 1.12),
        ]
        for label, value, color, width, dash, y_pos in markers:
            if value is None:
                continue
            fig.add_shape(
                type="line",
                x0=value,
                x1=value,
                y0=-0.42,
                y1=0.42,
                xref="x",
                yref="y",
                line=dict(color=color, width=width, dash=dash),
            )
            fig.add_annotation(
                x=value,
                y=y_pos,
                xref="x",
                yref="paper",
                text=label,
                showarrow=False,
                font=dict(size=11, color=color),
                yanchor="bottom",
            )
        fig.add_trace(
            go.Scatter(
                x=[current],
                y=[0],
                mode="markers+text",
                marker=dict(size=20, color="#111827", symbol="diamond", line=dict(color="white", width=2)),
                text=["当前价"],
                textposition="bottom center",
                textfont=dict(size=12, color="#111827"),
                hovertemplate="当前价: %{customdata}<extra></extra>",
                customdata=[_fmt_price(current)],
                showlegend=False,
            )
        )
        fig.update_layout(
            height=240,
            margin=dict(l=10, r=10, t=38, b=24),
            xaxis=dict(range=[x_min, x_max], tickprefix="¥", showgrid=True, gridcolor="#eef2f7"),
            yaxis=dict(range=[-1, 1], visible=False),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.caption("涨停价/跌停价仅作为交易边界参考；历史回测不代表未来收益。")


def render_moneyflow_conflict(
    today_main_net_yi: float | None,
    five_day_main_net_yi: float | None,
    title: str = "资金流冲突仪表",
):
    """Render two directional bars for today and five-day main net flow."""
    _inject_component_css()
    today = _to_float(today_main_net_yi)
    five_day = _to_float(five_day_main_net_yi)

    if today is None or five_day is None:
        status = "资金流数据缺口"
        color = "yellow"
    else:
        if today > 0 and five_day < 0:
            status, color = "短线修复，未确认反转", "orange"
        elif today > 0 and five_day > 0:
            status, color = "资金趋势改善", "green"
        elif today < 0 and five_day < 0:
            status, color = "资金压力延续", "red"
        elif today < 0 and five_day > 0:
            status, color = "短线分歧，观察承接", "orange"
        else:
            status, color = "资金方向待验证", "yellow"

    _render_html(
        f"""
        <div class="vc-shell">
            <div class="vc-title">{escape(str(title))}</div>
            <div class="vc-caption">资金流是盘后口径，只能作为辅助判断，不把单日流入写成买入依据。</div>
            <div class="vc-status-row">
                <div class="vc-status-heading">资金状态</div>
                <div class="vc-badges">{_badge_html(status, color)}</div>
            </div>
            {_metric_html([("今日主力资金", _fmt_yi(today)), ("近5日主力资金", _fmt_yi(five_day))])}
        </div>
        """
    )

    if today is None or five_day is None:
        st.info("资金流字段缺失，冲突仪表降级为数据缺口提示。")
    else:
        if go is not None:
            values = [today, five_day]
            max_abs = max(abs(value) for value in values) or 1
            fig = go.Figure()
            fig.add_vrect(x0=-max_abs * 1.25, x1=0, fillcolor="#fdecec", opacity=0.34, line_width=0)
            fig.add_vrect(x0=0, x1=max_abs * 1.25, fillcolor="#e8f7ef", opacity=0.34, line_width=0)
            fig.add_trace(
                go.Bar(
                    x=values,
                    y=["今日", "近5日"],
                    orientation="h",
                    marker_color=["#16a34a" if value >= 0 else "#dc2626" for value in values],
                    text=[_fmt_yi(value) for value in values],
                    textposition="outside",
                    hovertemplate="%{y}: %{text}<extra></extra>",
                    showlegend=False,
                )
            )
            fig.add_vline(x=0, line_color="#111827", line_width=1)
            fig.add_annotation(x=-max_abs * 0.85, y=1.18, xref="x", yref="paper", text="流出", showarrow=False, font=dict(size=12, color="#b42318"))
            fig.add_annotation(x=max_abs * 0.85, y=1.18, xref="x", yref="paper", text="流入", showarrow=False, font=dict(size=12, color="#137a3f"))
            fig.update_layout(
                height=250,
                margin=dict(l=42, r=36, t=32, b=24),
                xaxis=dict(range=[-max_abs * 1.25, max_abs * 1.25], zeroline=False, gridcolor="#eef2f7"),
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Plotly 未安装，资金流方向条暂以文字降级展示。")

    st.caption("今日流入只能视为线索；需要后续资金、价格和公告共同验证。")


def render_action_matrix(
    current_price: float,
    cost_price: float | None,
    chip_center: float | None,
    ma20: float | None,
    ma60: float | None,
    today_main_net_yi: float | None,
    five_day_main_net_yi: float | None,
    has_reduction_risk: bool = False,
    pledge_ratio: float | None = None,
    has_announcement_gap: bool = False,
    has_news_gap: bool = False,
    position_status: str = "已持仓",
):
    """Render a fixed five-action matrix with bounded action states."""
    _inject_component_css()
    current = _to_float(current_price)
    cost = _to_float(cost_price)
    chip = _to_float(chip_center)
    ma20_value = _to_float(ma20)
    ma60_value = _to_float(ma60)
    today = _to_float(today_main_net_yi)
    five_day = _to_float(five_day_main_net_yi)
    pledge = _to_float(pledge_ratio)
    status_text = str(position_status or "")
    is_holding = "已持" in status_text or "已持仓" in status_text or "加仓" in status_text
    is_not_bought = "未买入" in status_text or "纯观察" in status_text
    if is_not_bought:
        is_holding = False

    pnl_pct = (current / cost - 1) * 100 if current and cost else None
    big_profit = pnl_pct is not None and pnl_pct >= 20
    below_chip = bool(current and chip and current < chip)
    below_ma20 = bool(current and ma20_value and current < ma20_value)
    below_ma60 = bool(current and ma60_value and current < ma60_value)
    short_repair = bool(today is not None and five_day is not None and today > 0 and five_day < 0)
    flow_pressure = bool(five_day is not None and five_day < 0)
    single_day_outflow = bool(today is not None and today < 0)
    high_pledge = bool(pledge is not None and pledge > 15)
    hard_risk = bool(has_reduction_risk and high_pledge)

    if not is_holding:
        cards = [
            ("加仓", "未触发", "未确认实际持仓，不能把参考价当作加仓依据。"),
            ("持有", "未触发", "未确认实际持仓，不计算持有动作。"),
            ("做 T", "暂不建议", "未确认实际持仓，不做 T。"),
            ("减仓", "未触发", "未确认实际持仓，不生成减仓动作。"),
            ("退出观察", "等待验证", "仅保留退出观察条件，不构成交易指令。"),
        ]
    else:
        add_state = "等待验证"
        add_note = "需要连续资金验证和关键位站稳，不能把单日流入当作加仓依据。"
        if big_profit or short_repair or flow_pressure or hard_risk or below_ma20 or below_ma60:
            add_state = "暂不建议"
            if big_profit:
                add_note = "浮盈较大时优先保护成本优势，追高加仓需要更强验证。"
            if short_repair:
                add_note = "今日流入但近5日仍流出，等待连续资金验证。"
            if hard_risk:
                add_note = "减持与较高质押叠加，先降低加仓优先级。"
            if below_ma20 or below_ma60:
                add_note = "价格跌破趋势线后，加仓降级为等待修复验证。"
        elif today is not None and five_day is not None and today > 0 and five_day > 0 and not below_chip:
            add_state = "等待验证"
            add_note = "资金趋势改善时仍需连续验证，不自动提升为加仓动作。"

        hold_state = "允许观察"
        hold_note = "未触发硬性退出条件，继续观察资金延续和关键线。"
        if below_ma60:
            hold_state = "等待验证"
            hold_note = "中期趋势失效，持有需要重新验证。"
        elif below_ma20 or below_chip:
            hold_state = "等待验证"
            hold_note = "价格进入验证区，观察能否收回筹码中枢或 MA20。"

        t_state = "谨慎允许"
        t_note = "做 T 只能依赖盘中波动和执行纪律，不能替代减仓纪律。"
        if below_ma20 or below_ma60 or hard_risk:
            t_state = "暂不建议"
            t_note = "趋势或硬风险降级时，做 T 优先级下降。"

        reduce_state = "未触发"
        reduce_note = "减仓需要条件触发，例如资金重新流出或关键位失守。"
        if short_repair:
            reduce_state = "条件触发"
            reduce_note = "若次日重新流出或无法收回关键位，再进入条件化观察。"
        if below_chip or below_ma20 or flow_pressure or single_day_outflow or hard_risk:
            reduce_state = "条件触发"
            reduce_note = "触发项来自资金压力、关键位失守或硬风险叠加。"

        exit_state = "未触发"
        exit_note = "退出观察只看风险升级条件，不做无条件动作。"
        if below_ma60:
            exit_state = "风险升级"
            exit_note = "跌破 MA60 后风险升级，需验证能否快速修复。"
        elif has_announcement_gap or has_news_gap:
            exit_state = "等待验证"
            exit_note = "公告或新闻缺失是信息缺口，不是无风险。"

        cards = [
            ("加仓", add_state, add_note),
            ("持有", hold_state, hold_note),
            ("做 T", t_state, t_note),
            ("减仓", reduce_state, reduce_note),
            ("退出观察", exit_state, exit_note),
        ]

    _render_html(
        """
        <div class="vc-shell">
            <div class="vc-title">动作辅助矩阵</div>
            <div class="vc-caption">所有状态都是辅助判断，不构成买卖建议；减仓需要条件触发，加仓需要验证信号。</div>
            <div class="vc-card-grid">
        """
        + "".join(_state_card_html(name, state, note) for name, state, note in cards)
        + """
            </div>
            <div class="vc-caption">新闻/公告缺失是信息缺口，不是无风险；历史回测不代表未来收益。</div>
        </div>
        """
    )


def render_price_simulator(
    current_price: float,
    cost_price: float | None,
    shares: int | float | None,
    chip_center: float | None = None,
    ma20: float | None = None,
    ma60: float | None = None,
    limit_up: float | None = None,
    limit_down: float | None = None,
    key: str = "price_simulator",
):
    """Render a Streamlit slider for position scenario simulation."""
    _inject_component_css()
    current = _to_float(current_price)
    cost = _to_float(cost_price)
    units = _to_float(shares)
    chip = _to_float(chip_center)
    ma20_value = _to_float(ma20)
    ma60_value = _to_float(ma60)
    up_limit = _to_float(limit_up)
    down_limit = _to_float(limit_down)

    _render_html(
        """
        <div class="vc-shell">
            <div class="vc-title">盘中价格情景推演</div>
            <div class="vc-caption">模拟价格仅用于持仓情景推演，不代表预测。</div>
        </div>
        """
    )
    if current is None:
        st.info("当前价缺失，模拟器暂不可用。")
        return

    points = [value for value in [current, cost, chip, ma20_value, ma60_value, up_limit, down_limit] if value is not None and value > 0]
    base_min = min(points) if points else current
    base_max = max(points) if points else current
    min_price = min(down_limit, base_min * 0.98) if down_limit is not None else base_min * 0.88
    max_price = max(up_limit, base_max * 1.02) if up_limit is not None else base_max * 1.12
    if min_price >= max_price:
        min_price, max_price = current * 0.9, current * 1.1
    step = max(round((max_price - min_price) / 200, 3), 0.001)
    simulated = st.slider(
        "模拟盘中价格",
        min_value=float(round(min_price, 3)),
        max_value=float(round(max_price, 3)),
        value=float(round(current, 3)),
        step=float(step),
        format="%.3f",
        key=key,
    )

    if ma60_value is not None and simulated < ma60_value:
        action, color = "风险升级", "red"
    elif ma20_value is not None and simulated < ma20_value:
        action, color = "条件化减仓", "orange"
    elif chip is not None and simulated < chip:
        action, color = "减仓预警", "yellow"
    else:
        action, color = "持有验证", "green"
    _render_html(f"<div class='vc-badges'>{_badge_html(action, color)}</div>")

    metrics = [("模拟价格", _fmt_price(simulated))]
    if cost is not None and units is not None and units > 0:
        metrics.extend(
            [
                ("模拟浮盈金额", _fmt_money((simulated - cost) * units)),
                ("模拟浮盈比例", _fmt_pct((simulated / cost - 1) * 100 if cost else None)),
            ]
        )
    else:
        metrics.append(("模拟浮盈", "缺少成本或持仓数量"))

    breach_items = []
    if chip is not None:
        breach_items.append(("筹码中枢", "跌破" if simulated < chip else "上方"))
    if ma20_value is not None:
        breach_items.append(("MA20", "跌破" if simulated < ma20_value else "上方"))
    if ma60_value is not None:
        breach_items.append(("MA60", "跌破" if simulated < ma60_value else "上方"))
    if up_limit is not None:
        near_up = simulated >= up_limit * 0.98
        breach_items.append(("涨停边界", "接近" if near_up else "未接近"))
    if down_limit is not None:
            near_down = simulated <= down_limit * 1.02
            breach_items.append(("跌停边界", "接近" if near_down else "未接近"))
    metrics.extend(breach_items)
    _render_html(_metric_html(metrics))
    st.caption("这是模拟工具，不是交易指令；临近涨跌停只代表交易边界变化。")


def render_risk_radar_summary(
    red_items: list[str] | None = None,
    orange_items: list[str] | None = None,
    yellow_items: list[str] | None = None,
    improvement_items: list[str] | None = None,
):
    """Render a local risk summary without relying on DeepSeek output."""
    _inject_component_css()
    red = _dedupe(red_items)
    orange = _dedupe(orange_items)
    yellow = _dedupe(yellow_items)
    improvements = _dedupe(improvement_items)
    cards = [
        ("红色风险", len(red), "red"),
        ("橙色风险", len(orange), "orange"),
        ("黄色信息缺口", len(yellow), "yellow"),
        ("改善信号", len(improvements), "green"),
    ]
    risk_cards_html = "<div class='vc-risk-grid'>" + "".join(
        f"""
        <div class="vc-risk-card vc-{color}">
            <div class="vc-risk-count">{count}</div>
            <div class="vc-risk-label">{name}</div>
        </div>
        """
        for name, count, color in cards
    ) + "</div>"
    _render_html(
        """
        <div class="vc-shell">
            <div class="vc-title">本地风险雷达摘要</div>
            <div class="vc-caption">基于结构化事实本地粗分层，不依赖 DeepSeek 输出，不构成买卖建议。</div>
        """
        + risk_cards_html
        + "<div class='vc-badges'>"
        + "".join(_badge_html(f"{name}: {count}", color) for name, count, color in cards)
        + """
            </div>
            <div class="vc-caption">新闻/公告缺失是信息缺口，不是无风险；减仓需要条件触发，加仓需要验证信号。</div>
        </div>
        """
    )
    groups = [
        ("红色风险", red),
        ("橙色风险", orange),
        ("黄色信息缺口", yellow),
        ("改善信号", improvements),
    ]
    for label, items in groups:
        with st.expander(f"{label}明细（{len(items)}）", expanded=False):
            if items:
                for item in items:
                    st.markdown(f"- {item}")
            else:
                st.caption("暂无结构化条目。")


def render_next_ticket_holding_card(holding_context: dict | None = None):
    """Render the current holding comparison card for the next-ticket radar."""
    _inject_component_css()
    context = holding_context or {}
    ticker = context.get("current_holding_ticker") or "暂无"
    name = context.get("current_holding_name") or ""
    price = _fmt_price(context.get("current_price"))
    pnl_pct = _fmt_pct(context.get("floating_profit_pct"))
    action_state = context.get("holding_action_state") or "只观察"
    next_mode = context.get("next_ticket_mode") or "只观察"
    risks = _dedupe(context.get("holding_biggest_risks") or [])[:4]
    risk_text = "；".join(risks) if risks else "暂无可验证风险"
    metrics = [
        ("当前持仓票", f"{ticker} {name}".strip()),
        ("当前价", price),
        ("浮盈", pnl_pct),
        ("当前动作状态", action_state),
        ("当前持仓最大风险", risk_text),
        ("下一票模式", next_mode),
    ]
    mode_color = {
        "接力": "blue",
        "低吸": "purple",
        "防守": "orange",
        "只观察": "gray",
    }.get(str(next_mode), "gray")
    action_color = "orange" if "减仓" in str(action_state) or "暂停" in str(action_state) else ("red" if "风险" in str(action_state) else "green")
    _render_html(
        """
        <div class="vc-shell">
            <div class="vc-title">当前持仓卡</div>
            <div class="vc-caption">这是候选票对比标尺，不输出交易指令。</div>
        """
        + _metric_html(metrics)
        + "<div class='vc-badges'>"
        + _badge_html(action_state, action_color)
        + _badge_html(f"下一票模式：{next_mode}", mode_color)
        + "</div></div>"
    )


def _result_list(items):
    values = _dedupe(items if isinstance(items, list) else [items])
    if not values:
        st.caption("暂无可验证数据。")
        return
    for item in values:
        st.markdown(f"- {item}")


def render_next_ticket_research_summary(result: dict | None = None, generated_at: str = "", cached: bool = False):
    """Render one DeepSeek research result in a controlled structure."""
    payload = result or {}
    if payload.get("parse_status") == "markdown":
        st.caption(f"generated_at：{generated_at or '暂无'}" + ("｜缓存" if cached else ""))
        st.markdown(payload.get("raw_output") or "暂无可验证数据。")
        return

    state = payload.get("battle_state") or payload.get("作战状态") or "只观察"
    score = payload.get("total_score") or payload.get("综合评分") or 0
    relation = payload.get("relation_to_current_holding") or payload.get("与当前持仓票的关系") or "暂不替代"
    conclusion = payload.get("one_sentence_conclusion") or payload.get("一句话结论") or "暂无可验证数据。"
    breakdown = payload.get("score_breakdown") or payload.get("评分拆解") or {}

    c1, c2, c3 = st.columns(3)
    c1.metric("作战状态", state)
    c2.metric("综合评分", score)
    c3.metric("与当前持仓票关系", relation)
    st.caption(f"generated_at：{generated_at or '暂无'}" + ("｜缓存结果" if cached else "｜新生成结果"))
    st.markdown(f"**一句话结论**：{conclusion}")

    if isinstance(breakdown, dict) and breakdown:
        st.markdown("**评分拆解**")
        st.dataframe(
            [{"维度": key, "评分": value} for key, value in breakdown.items()],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("**入手触发条件**")
    _result_list(payload.get("entry_triggers") or payload.get("入手触发条件") or [])
    st.markdown("**失效条件**")
    _result_list(payload.get("invalid_conditions") or payload.get("失效条件") or [])
    st.markdown("**最大风险**")
    _result_list(payload.get("biggest_risks") or payload.get("最大风险") or [])
    st.markdown("**数据缺口**")
    _result_list(payload.get("data_gaps") or payload.get("数据缺口") or [])
    st.markdown("**为什么不是直接行动**")
    st.write(payload.get("why_not_direct_action") or payload.get("为什么不是直接买") or "需要等待验证，且不构成交易建议。")
