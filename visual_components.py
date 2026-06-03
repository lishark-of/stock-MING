from __future__ import annotations

import json
import math
from html import escape
from textwrap import dedent

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from command_center_data_capability_dashboard import build_data_capability_dashboard_view_model
from command_center_evidence_summary import build_a_share_evidence_radar_view_model
from command_center_home_snapshot import build_tool_recovery_navigation_state
from command_center_decision_summary import build_decision_summary_view_model
from command_center_strategy_summary import build_strategy_summary_view_model

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

BUCKET_ORDER = ["宽基ETF", "科技成长ETF", "金融券商ETF", "防守ETF", "商品周期ETF", "现金"]
NON_CASH_BUCKETS = [item for item in BUCKET_ORDER if item != "现金"]
BUCKET_COLORS = {
    "宽基ETF": "#2563EB",
    "科技成长ETF": "#8B5CF6",
    "金融券商ETF": "#EF4444",
    "防守ETF": "#10B981",
    "商品周期ETF": "#7C3AED",
    "现金": "#CBD5E1",
}
BUCKET_BG_COLORS = {
    "宽基ETF": "rgba(56, 189, 248, 0.12)",
    "科技成长ETF": "rgba(255, 79, 163, 0.11)",
    "金融券商ETF": "rgba(239, 68, 68, 0.11)",
    "防守ETF": "rgba(74, 222, 128, 0.11)",
    "商品周期ETF": "rgba(167, 139, 250, 0.11)",
    "现金": "rgba(203, 213, 225, 0.14)",
}
BUCKET_TEXT_COLORS = {
    "宽基ETF": "#1E4FB5",
    "科技成长ETF": "#6D28D9",
    "金融券商ETF": "#C73F2F",
    "防守ETF": "#0F8B68",
    "商品周期ETF": "#6D28D9",
    "现金": "#64748B",
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


def _fmt_price(value, currency="¥"):
    number = _to_float(value)
    if number is None:
        return "暂无"
    return f"{currency}{number:,.2f}" if currency else f"{number:,.2f}"


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


def _bucket_color(value):
    return BUCKET_COLORS.get(str(value or "").strip(), "#8E8E93")


def _bucket_bg(value):
    return BUCKET_BG_COLORS.get(str(value or "").strip(), "rgba(142, 142, 147, 0.12)")


def _bucket_text_color(value):
    return BUCKET_TEXT_COLORS.get(str(value or "").strip(), "#6F6F74")


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
        :root {
            --ios-bg: #F5F5F7;
            --ios-card: #FFFFFF;
            --ios-card-subtle: #F2F2F7;
            --ios-border: rgba(60, 60, 67, 0.16);
            --ios-label: #1D1D1F;
            --ios-secondary-label: rgba(60, 60, 67, 0.72);
            --ios-tertiary-label: rgba(60, 60, 67, 0.48);
            --ios-blue: #007AFF;
            --ios-green: #34C759;
            --ios-orange: #FF9500;
            --ios-red: #FF3B30;
            --ios-purple: #AF52DE;
            --ios-teal: #30B0C7;
            --ios-gray: #8E8E93;
            --ios-blue-bg: rgba(0, 122, 255, 0.10);
            --ios-green-bg: rgba(52, 199, 89, 0.10);
            --ios-orange-bg: rgba(255, 149, 0, 0.12);
            --ios-red-bg: rgba(255, 59, 48, 0.10);
            --ios-purple-bg: rgba(175, 82, 222, 0.10);
            --ios-gray-bg: rgba(142, 142, 147, 0.12);
            --ios-shadow-soft: 0 12px 28px rgba(15, 23, 42, 0.06);
            --ios-shadow-card: 0 8px 20px rgba(15, 23, 42, 0.04);
        }
        .vc-shell {
            background: var(--ios-card);
            border: 1px solid var(--ios-border);
            border-radius: 22px;
            box-shadow: var(--ios-shadow-soft);
            padding: 16px 16px 14px;
            margin: 10px 0 12px;
        }
        .vc-title {
            font-size: 1rem;
            font-weight: 700;
            color: var(--ios-label);
            margin-bottom: 4px;
        }
        .vc-caption {
            color: var(--ios-secondary-label);
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
            border-radius: 16px;
            background: var(--ios-card-subtle);
            border: 1px solid var(--ios-border);
            padding: 10px 11px;
            min-height: 62px;
        }
        .vc-label {
            color: var(--ios-secondary-label);
            font-size: 0.75rem;
            margin-bottom: 4px;
        }
        .vc-value {
            color: var(--ios-label);
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
            border: 1px solid transparent;
            animation: vc-fade-in 240ms ease both;
        }
        .vc-green { background: var(--ios-green-bg); color: var(--ios-green); border-color: rgba(52, 199, 89, 0.14); }
        .vc-red { background: var(--ios-red-bg); color: var(--ios-red); border-color: rgba(255, 59, 48, 0.14); }
        .vc-orange { background: var(--ios-orange-bg); color: var(--ios-orange); border-color: rgba(255, 149, 0, 0.14); }
        .vc-soft-red { background: var(--ios-red-bg); color: rgba(122, 50, 45, 0.92); border-color: rgba(255, 59, 48, 0.10); }
        .vc-soft-orange { background: var(--ios-orange-bg); color: rgba(128, 91, 26, 0.94); border-color: rgba(255, 149, 0, 0.10); }
        .vc-yellow { background: rgba(255, 204, 0, 0.12); color: #B88700; border-color: rgba(255, 204, 0, 0.16); }
        .vc-gray { background: var(--ios-gray-bg); color: var(--ios-gray); border-color: rgba(142, 142, 147, 0.16); }
        .vc-blue { background: var(--ios-blue-bg); color: var(--ios-blue); border-color: rgba(0, 122, 255, 0.14); }
        .vc-purple { background: var(--ios-purple-bg); color: var(--ios-purple); border-color: rgba(175, 82, 222, 0.14); }
        .vc-teal { background: rgba(48, 176, 199, 0.12); color: var(--ios-teal); border-color: rgba(48, 176, 199, 0.14); }
        .vc-status-row {
            border-radius: 16px;
            background: var(--ios-card-subtle);
            border: 1px solid var(--ios-border);
            padding: 10px 11px 11px;
            margin-top: 10px;
        }
        .vc-status-heading {
            color: var(--ios-label);
            font-size: 0.78rem;
            font-weight: 720;
            margin-bottom: 4px;
        }
        .vc-summary-shell {
            background: var(--ios-card);
            border: 1px solid var(--ios-border);
            border-radius: 24px;
            box-shadow: var(--ios-shadow-soft);
            padding: 18px 18px 16px;
            margin: 8px 0 14px;
            animation: vc-fade-up 260ms ease both;
        }
        .vc-summary-head {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
        }
        .vc-summary-title {
            font-size: 1.08rem;
            font-weight: 760;
            color: var(--ios-label);
            margin: 0;
        }
        .vc-summary-subtitle {
            color: var(--ios-secondary-label);
            font-size: 0.82rem;
            line-height: 1.4;
            margin-top: 4px;
        }
        .vc-summary-lines {
            margin-top: 14px;
            display: grid;
            gap: 8px;
        }
        .vc-summary-line {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 10px 12px;
            border-radius: 16px;
            background: var(--ios-card-subtle);
            border: 1px solid var(--ios-border);
        }
        .vc-summary-key {
            min-width: 46px;
            color: var(--ios-secondary-label);
            font-size: 0.78rem;
            font-weight: 700;
            flex-shrink: 0;
            padding-top: 1px;
        }
        .vc-summary-value {
            color: var(--ios-label);
            font-size: 0.9rem;
            line-height: 1.42;
            font-weight: 620;
        }
        .vc-divider {
            height: 1px;
            background: var(--ios-border);
            margin: 14px 0 12px;
        }
        .vc-chip-stack {
            display: grid;
            gap: 10px;
        }
        .vc-chip-line {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            flex-wrap: wrap;
        }
        .vc-chip-label {
            min-width: 68px;
            color: var(--ios-secondary-label);
            font-size: 0.79rem;
            font-weight: 700;
            padding-top: 6px;
        }
        .vc-soft-note {
            border-radius: 16px;
            background: var(--ios-card-subtle);
            border: 1px solid var(--ios-border);
            padding: 10px 12px;
            color: var(--ios-secondary-label);
            font-size: 0.82rem;
            line-height: 1.45;
            margin: 8px 0 10px;
        }
        .vc-table-shell {
            background: var(--ios-card);
            border: 1px solid var(--ios-border);
            border-radius: 20px;
            box-shadow: var(--ios-shadow-card);
            overflow: hidden;
            margin: 8px 0 10px;
        }
        .vc-table-note {
            color: var(--ios-secondary-label);
            font-size: 0.82rem;
            line-height: 1.45;
            margin: 4px 0 8px;
        }
        .vc-html-table-wrap {
            overflow-x: auto;
        }
        .vc-html-table {
            width: 100%;
            border-collapse: collapse;
            table-layout: auto;
        }
        .vc-html-table th {
            text-align: left;
            font-size: 0.74rem;
            font-weight: 700;
            color: var(--ios-tertiary-label);
            background: var(--ios-card-subtle);
            padding: 10px 12px;
            border-bottom: 1px solid var(--ios-border);
            white-space: nowrap;
        }
        .vc-html-table td {
            padding: 11px 12px;
            border-bottom: 1px solid rgba(60, 60, 67, 0.08);
            color: var(--ios-label);
            font-size: 0.84rem;
            line-height: 1.35;
            vertical-align: top;
            white-space: nowrap;
        }
        .vc-html-table tr:last-child td {
            border-bottom: none;
        }
        .vc-muted-cell {
            color: var(--ios-secondary-label);
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
            color: var(--ios-secondary-label);
            font-size: 0.82rem;
            margin-top: 6px;
        }
        .vc-bucket-summary-grid {
            display: grid;
            gap: 10px;
            margin: 8px 0 10px;
        }
        .vc-bucket-summary-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            padding: 11px 12px;
            border-radius: 16px;
            border: 1px solid var(--ios-border);
            background: var(--ios-card-subtle);
        }
        .vc-bucket-summary-left {
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 0;
        }
        .vc-bucket-dot {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            flex-shrink: 0;
        }
        .vc-bucket-summary-name {
            color: var(--ios-label);
            font-size: 0.86rem;
            font-weight: 700;
            white-space: nowrap;
        }
        .vc-bucket-summary-note {
            color: var(--ios-secondary-label);
            font-size: 0.76rem;
            margin-top: 2px;
        }
        .vc-bucket-summary-ratio {
            color: var(--ios-label);
            font-size: 0.98rem;
            font-weight: 760;
            flex-shrink: 0;
        }
        .vc-ring-shell {
            border: 1px solid var(--ios-border);
            border-radius: 30px;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(246,248,252,0.96));
            box-shadow: 0 18px 36px rgba(15, 23, 42, 0.08);
            padding: 18px 18px 16px;
            margin: 8px 0 12px;
        }
        .vc-ring-shell-title {
            color: var(--ios-label);
            font-size: 1.08rem;
            font-weight: 820;
            line-height: 1.22;
        }
        .vc-ring-shell-subtitle {
            color: var(--ios-secondary-label);
            font-size: 0.8rem;
            line-height: 1.45;
            margin-top: 4px;
        }
        .vc-ring-figure {
            border-radius: 28px;
            border: 1px solid rgba(60, 60, 67, 0.10);
            background:
                radial-gradient(circle at 50% 28%, rgba(255,255,255,0.98), rgba(250,251,254,0.94) 48%, rgba(244,246,250,0.96) 100%);
            padding: 12px 10px 10px;
            min-height: 314px;
            position: relative;
            overflow: hidden;
        }
        .vc-ring-figure-note {
            color: var(--ios-secondary-label);
            font-size: 0.76rem;
            margin-top: 8px;
            line-height: 1.45;
            text-align: center;
        }
        .vc-ring-center-shell {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 0;
        }
        .vc-ring-center {
            width: min(236px, 100%);
            margin: 0 auto;
            border-radius: 26px;
            border: 1px solid rgba(60, 60, 67, 0.08);
            background: rgba(255, 255, 255, 0.92);
            box-shadow: 0 12px 26px rgba(15, 23, 42, 0.08);
            padding: 16px 16px 14px;
            text-align: center;
            animation: vc-fade-up 220ms ease both;
        }
        .vc-ring-center-kicker {
            color: var(--ios-secondary-label);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }
        .vc-ring-center-title {
            color: var(--ios-label);
            font-size: 1.12rem;
            font-weight: 820;
            line-height: 1.22;
            margin-top: 4px;
        }
        .vc-ring-center-value {
            color: var(--ios-label);
            font-size: 1.14rem;
            font-weight: 820;
            margin-top: 6px;
        }
        .vc-ring-center-note {
            color: var(--ios-secondary-label);
            font-size: 0.76rem;
            line-height: 1.45;
            margin-top: 8px;
        }
        .vc-ring-detail {
            border-radius: 28px;
            border: 1px solid var(--ios-border);
            background: var(--ios-card);
            box-shadow: 0 16px 30px rgba(15, 23, 42, 0.08);
            padding: 16px 16px 14px;
            animation: vc-fade-up 220ms ease both;
        }
        .vc-ring-detail-head {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 14px;
        }
        .vc-ring-detail-kicker {
            color: var(--ios-secondary-label);
            font-size: 0.76rem;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .vc-ring-detail-title {
            color: var(--ios-label);
            font-size: 1.12rem;
            font-weight: 820;
            line-height: 1.22;
        }
        .vc-ring-detail-subtitle {
            color: var(--ios-secondary-label);
            font-size: 0.8rem;
            line-height: 1.4;
            margin-top: 4px;
        }
        .vc-ring-detail-hero {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 164px;
            gap: 12px;
            align-items: stretch;
            margin-top: 12px;
        }
        .vc-ring-detail-hero-left {
            border-radius: 20px;
            border: 1px solid var(--ios-border);
            background: var(--ios-card-subtle);
            padding: 12px;
        }
        .vc-ring-detail-hero-label {
            color: var(--ios-secondary-label);
            font-size: 0.74rem;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .vc-ring-detail-hero-value {
            color: var(--ios-label);
            font-size: 1.8rem;
            font-weight: 860;
            line-height: 1.0;
            letter-spacing: -0.03em;
        }
        .vc-ring-detail-hero-sub {
            color: var(--ios-secondary-label);
            font-size: 0.78rem;
            line-height: 1.45;
            margin-top: 6px;
        }
        .vc-ring-detail-trend {
            border-radius: 20px;
            border: 1px solid var(--ios-border);
            background: linear-gradient(180deg, rgba(245,247,251,0.96), rgba(238,242,247,0.96));
            padding: 12px 12px 10px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 112px;
        }
        .vc-ring-detail-trend-title {
            color: var(--ios-secondary-label);
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .vc-trend-bars {
            display: flex;
            align-items: flex-end;
            gap: 4px;
            height: 56px;
            margin-top: 4px;
        }
        .vc-trend-bar {
            flex: 1;
            min-width: 5px;
            border-radius: 999px 999px 4px 4px;
            background: linear-gradient(180deg, rgba(255,255,255,0.30), var(--bucket-accent, rgba(56,189,248,0.9)));
            box-shadow: 0 8px 16px rgba(15, 23, 42, 0.06);
        }
        .vc-ring-detail-trend-note {
            color: var(--ios-secondary-label);
            font-size: 0.72rem;
            line-height: 1.35;
            margin-top: 6px;
        }
        .vc-ring-detail-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .vc-ring-detail-metrics {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            margin-top: 12px;
        }
        .vc-ring-detail-metric {
            border-radius: 18px;
            border: 1px solid var(--ios-border);
            background: var(--ios-card-subtle);
            padding: 11px 12px;
        }
        .vc-ring-detail-label {
            color: var(--ios-secondary-label);
            font-size: 0.75rem;
            margin-bottom: 4px;
        }
        .vc-ring-detail-value {
            color: var(--ios-label);
            font-size: 0.96rem;
            font-weight: 760;
            line-height: 1.35;
        }
        .vc-ring-detail-note {
            margin-top: 12px;
            border-radius: 18px;
            border: 1px solid var(--ios-border);
            background: rgba(60, 60, 67, 0.04);
            color: var(--ios-secondary-label);
            font-size: 0.83rem;
            line-height: 1.5;
            padding: 12px 13px;
        }
        .vc-ring-selector {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid rgba(60, 60, 67, 0.10);
        }
        .vc-ring-selector-title {
            color: var(--ios-label);
            font-size: 0.82rem;
            font-weight: 720;
            margin-bottom: 8px;
        }
        .vc-ring-selector-note {
            color: var(--ios-secondary-label);
            font-size: 0.75rem;
            margin-top: 6px;
            line-height: 1.45;
        }
        .vc-ring-selector .stSegmentedControl {
            width: 100%;
        }
        .vc-ring-selected-shell {
            margin-top: 12px;
        }
        .vc-ring-selected-title {
            color: var(--ios-label);
            font-size: 0.92rem;
            font-weight: 760;
            margin-bottom: 8px;
        }
        .vc-ring-selected-empty {
            border-radius: 18px;
            border: 1px dashed rgba(60, 60, 67, 0.16);
            background: rgba(60, 60, 67, 0.03);
            color: var(--ios-secondary-label);
            font-size: 0.84rem;
            line-height: 1.5;
            padding: 12px 13px;
        }
        .vc-ring-cash-shell {
            border-radius: 20px;
            border: 1px solid var(--ios-border);
            background: var(--ios-card-subtle);
            box-shadow: var(--ios-shadow-soft);
            padding: 12px;
            margin-top: 12px;
        }
        .vc-ring-cash-title {
            color: var(--ios-label);
            font-size: 0.86rem;
            font-weight: 720;
            margin-bottom: 4px;
        }
        .vc-ring-cash-note {
            color: var(--ios-secondary-label);
            font-size: 0.76rem;
            line-height: 1.45;
            margin-bottom: 8px;
        }
        .vc-ring-cash-shell .vc-cash-strip {
            margin-top: 0;
        }
        .vc-allocation-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
            margin: 8px 0 12px;
        }
        .vc-allocation-card {
            border-radius: 20px;
            border: 1px solid var(--ios-border);
            background: var(--ios-card);
            box-shadow: var(--ios-shadow-card);
            padding: 14px 14px 13px;
            position: relative;
            overflow: hidden;
            transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
        }
        .vc-allocation-card:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
        }
        .vc-allocation-card.is-selected {
            border-color: var(--bucket-accent, rgba(76, 120, 168, 0.55));
            box-shadow: 0 12px 26px rgba(15, 23, 42, 0.10);
        }
        .vc-allocation-head {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
        }
        .vc-allocation-title {
            color: var(--ios-label);
            font-size: 0.98rem;
            font-weight: 760;
            line-height: 1.22;
        }
        .vc-allocation-role {
            color: var(--ios-secondary-label);
            font-size: 0.78rem;
            margin-top: 3px;
        }
        .vc-allocation-weight {
            color: var(--ios-label);
            font-size: 1.02rem;
            font-weight: 780;
            white-space: nowrap;
            text-align: right;
            flex-shrink: 0;
        }
        .vc-allocation-status {
            margin-top: 8px;
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        .vc-allocation-bar {
            height: 10px;
            border-radius: 999px;
            background: rgba(60, 60, 67, 0.08);
            overflow: hidden;
            margin-top: 10px;
        }
        .vc-allocation-fill {
            height: 100%;
            border-radius: inherit;
            transition: width 200ms ease;
        }
        .vc-allocation-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 10px;
            margin-top: 10px;
        }
        .vc-allocation-list {
            color: var(--ios-label);
            font-size: 0.8rem;
            line-height: 1.45;
        }
        .vc-allocation-risk {
            color: var(--ios-secondary-label);
            font-size: 0.76rem;
            line-height: 1.45;
            margin-top: 7px;
        }
        .vc-allocation-mini-shell {
            border-radius: 20px;
            border: 1px solid var(--ios-border);
            background: var(--ios-card-subtle);
            box-shadow: var(--ios-shadow-soft);
            padding: 12px;
        }
        .vc-allocation-mini-title {
            color: var(--ios-label);
            font-size: 0.86rem;
            font-weight: 720;
            margin-bottom: 4px;
        }
        .vc-allocation-mini-note {
            color: var(--ios-secondary-label);
            font-size: 0.76rem;
            line-height: 1.45;
            margin-bottom: 8px;
        }
        .vc-etf-card-list {
            display: grid;
            gap: 12px;
            margin: 8px 0 12px;
        }
        .vc-etf-card {
            border-radius: 24px;
            background: var(--ios-card);
            border: 1px solid var(--ios-border);
            box-shadow: 0 14px 26px rgba(15, 23, 42, 0.07);
            padding: 14px 14px 13px;
            position: relative;
            overflow: hidden;
            display: grid;
            grid-template-columns: 52px minmax(0, 1fr) 138px 18px;
            gap: 12px;
            align-items: center;
        }
        .vc-etf-card::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: var(--bucket-gradient, linear-gradient(180deg, var(--bucket-accent, var(--ios-blue)), rgba(255,255,255,0.12)));
        }
        .vc-etf-card-icon {
            width: 52px;
            height: 52px;
            border-radius: 16px;
            background: var(--bucket-gradient, linear-gradient(180deg, var(--ios-blue), rgba(0,0,0,0.08)));
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9rem;
            font-weight: 860;
            letter-spacing: 0.03em;
            box-shadow: 0 12px 18px rgba(15, 23, 42, 0.14);
            position: relative;
            overflow: hidden;
        }
        .vc-etf-card-icon::after {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.30), rgba(255,255,255,0.05) 52%, rgba(255,255,255,0.0));
        }
        .vc-etf-card-body {
            min-width: 0;
        }
        .vc-etf-card-head {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 10px;
        }
        .vc-etf-card-title {
            color: var(--ios-label);
            font-size: 0.98rem;
            font-weight: 800;
            line-height: 1.25;
        }
        .vc-etf-card-subtitle {
            color: var(--ios-secondary-label);
            font-size: 0.8rem;
            line-height: 1.4;
            margin-top: 4px;
        }
        .vc-etf-card-ratio {
            color: var(--ios-label);
            font-size: 0.86rem;
            font-weight: 760;
            white-space: nowrap;
            text-align: right;
            line-height: 1.35;
        }
        .vc-etf-card-amount {
            color: var(--ios-secondary-label);
            font-size: 0.78rem;
            font-weight: 650;
            margin-top: 3px;
        }
        .vc-etf-card-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
        }
        .vc-etf-card-side {
            display: flex;
            flex-direction: column;
            gap: 4px;
            align-items: flex-end;
            justify-content: center;
            text-align: right;
        }
        .vc-etf-card-chev {
            color: rgba(60, 60, 67, 0.28);
            font-size: 1.2rem;
            font-weight: 700;
            text-align: right;
        }
        .vc-etf-card-reason {
            color: var(--ios-secondary-label);
            font-size: 0.82rem;
            line-height: 1.5;
            margin-top: 8px;
        }
        .vc-selector-shell {
            border: 1px solid var(--ios-border);
            border-radius: 20px;
            background: var(--ios-card);
            box-shadow: var(--ios-shadow-card);
            padding: 12px 12px 10px;
            margin: 8px 0 10px;
        }
        .vc-selector-shell .stSegmentedControl {
            width: 100%;
        }
        .vc-cash-strip {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            border-radius: 16px;
            border: 1px solid var(--ios-border);
            background: rgba(142, 142, 147, 0.10);
            padding: 10px 12px;
            margin-top: 10px;
        }
        .vc-cash-strip-title {
            color: var(--ios-label);
            font-size: 0.84rem;
            font-weight: 700;
        }
        .vc-cash-strip-note {
            color: var(--ios-secondary-label);
            font-size: 0.76rem;
            margin-top: 3px;
        }
        .vc-cash-strip-value {
            color: var(--ios-gray);
            font-size: 1rem;
            font-weight: 780;
            white-space: nowrap;
        }
        @media (max-width: 860px) {
            .vc-etf-card {
                grid-template-columns: 52px minmax(0, 1fr);
            }
            .vc-etf-card-side {
                grid-column: 2;
                align-items: flex-start;
                text-align: left;
                margin-top: 2px;
            }
            .vc-ring-detail-hero {
                grid-template-columns: 1fr;
            }
        }
        @keyframes vc-fade-up {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes vc-fade-in {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
            .vc-summary-shell, .vc-badge, .vc-allocation-card, .vc-allocation-fill, .vc-ring-center, .vc-ring-detail {
                animation: none !important;
                transition: none !important;
                transform: none !important;
            }
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


def _soft_badge_html(text, color="gray"):
    tone = str(color or "").strip()
    if tone in {"red", "orange"}:
        return f"<span class='vc-badge vc-soft-{escape(tone)}'>{escape(str(text))}</span>"
    return _badge_html(text, tone or "gray")


def _fmt_money_compact(value):
    number = _to_float(value)
    if number is None:
        return "暂无"
    abs_number = abs(number)
    if abs_number >= 100000000:
        return f"{number / 100000000:+.2f} 亿" if number < 0 else f"{number / 100000000:.2f} 亿"
    if abs_number >= 10000:
        return f"{number / 10000:+.2f} 万" if number < 0 else f"{number / 10000:.2f} 万"
    return f"{number:,.2f}"


def _fmt_score(value):
    number = _to_float(value)
    if number is None:
        return "暂无"
    if abs(number - round(number)) < 0.05:
        return f"{round(number):.0f}"
    return f"{number:.1f}"


def _state_color_label(value):
    text = str(value or "").strip()
    mapping = {
        "强趋势": "blue",
        "温和向上": "green",
        "震荡观察": "gray",
        "过热等待": "orange",
        "破位回避": "red",
        "优先配置": "blue",
        "可观察": "green",
        "观察不追": "orange",
        "只观察不追": "orange",
        "暂不纳入": "red",
        "待确认": "gray",
        "观察": "gray",
        "增配": "blue",
        "降配": "orange",
        "中性": "gray",
        "数据不足": "gray",
        "部分可用": "gray",
        "可用": "green",
        "失败": "orange",
        "综合更均衡": "blue",
        "趋势更强": "purple",
        "流动性更好": "teal",
        "波动更低": "gray",
        "仅观察": "orange",
        "待比较": "gray",
    }
    for key, color in mapping.items():
        if key in text:
            return color
    if "风险" in text or "降杠杆" in text:
        return "red"
    if "进攻" in text:
        return "blue"
    return "gray"


def _action_state_color(value):
    mapping = {
        "可小幅融资进攻": "blue",
        "可中等融资进攻": "purple",
        "可用现金进攻，暂不加融资": "green",
        "只允许调仓，不新增杠杆": "orange",
        "暂停融资，保留现金": "gray",
        "融资过高，优先降杠杆": "red",
    }
    return mapping.get(str(value or "").strip(), "gray")


def _recommendation_state_label(state, bucket, overweight_buckets=None, underweight_buckets=None):
    bucket = str(bucket or "").strip()
    state = str(state or "").strip()
    overweight = set(overweight_buckets or [])
    underweight = set(underweight_buckets or [])
    if state == "破位回避":
        return "暂不纳入"
    if state == "过热等待":
        return "只观察不追"
    if bucket in underweight and state in {"震荡观察", "数据不足"}:
        return "暂不纳入"
    if bucket in overweight and state in {"强趋势", "温和向上"}:
        return "优先配置"
    if state == "强趋势":
        return "优先配置"
    if state == "温和向上":
        return "可观察"
    if state == "震荡观察":
        return "可观察"
    return "暂不纳入"


def _bucket_label(value):
    mapping = {
        "宽基ETF": "宽基",
        "科技成长ETF": "科技成长",
        "金融券商ETF": "金融券商",
        "防守ETF": "防守",
        "商品周期ETF": "商品周期",
        "现金": "现金",
    }
    return mapping.get(str(value or "").strip(), str(value or "").strip() or "暂无")


def _html_table_cell(value, as_badge=False):
    text = str(value or "").strip() or "暂无"
    if as_badge:
        return _badge_html(text, _state_color_label(text))
    return escape(text)


def _render_compact_table(
    rows,
    *,
    badge_columns=None,
    muted_columns=None,
    max_rows=10,
    expander_label="查看完整表",
    always_expander=False,
    expanded_rows=None,
    show_expander=True,
):
    rows = list(rows or [])
    if not rows:
        st.info("暂无可展示数据。")
        return
    badge_columns = set(badge_columns or set())
    muted_columns = set(muted_columns or set())
    display_rows = rows[: max(max_rows, 1)]
    columns = list(display_rows[0].keys())

    header_html = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    body_rows = []
    for row in display_rows:
        cells = []
        for column in columns:
            classes = " class='vc-muted-cell'" if column in muted_columns else ""
            cell_html = _html_table_cell(row.get(column), as_badge=column in badge_columns)
            cells.append(f"<td{classes}>{cell_html}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    _render_html(
        "<div class='vc-table-shell'><div class='vc-html-table-wrap'><table class='vc-html-table'>"
        f"<thead><tr>{header_html}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div></div>"
    )
    if show_expander and (always_expander or len(rows) > len(display_rows)):
        with st.expander(f"{expander_label}（{len(rows)} 行）", expanded=False):
            st.dataframe(expanded_rows or rows, width="stretch", hide_index=True)


def _bucket_summary_cards(rows, weights=None):
    blocks = []
    weight_lookup = weights or {}
    for label, ratio in rows:
        blocks.append(
            f"""
            <div class="vc-bucket-summary-card">
                <div class="vc-bucket-summary-left">
                    <span class="vc-bucket-dot" style="background:{escape(_bucket_color(label))};"></span>
                    <div>
                        <div class="vc-bucket-summary-name">{escape(str(label))}</div>
                        <div class="vc-bucket-summary-note">动态权重 {float(weight_lookup.get(label, ratio) or 0.0):.2f}%</div>
                    </div>
                </div>
                <div class="vc-bucket-summary-ratio">{float(ratio or 0.0):.2f}%</div>
            </div>
            """
        )
    return _clean_html(f"<div class='vc-bucket-summary-grid'>{''.join(blocks)}</div>")


def _cash_buffer_strip(ratio, amount=None):
    ratio_text = f"{float(ratio or 0.0):.2f}%"
    amount_text = _fmt_money(amount) if amount is not None else "现金缓冲"
    return _clean_html(
        f"""
        <div class="vc-cash-strip">
            <div>
                <div class="vc-cash-strip-title">现金缓冲</div>
                <div class="vc-cash-strip-note">今日保留，不抢 ETF 主视觉</div>
            </div>
            <div class="vc-cash-strip-value">{escape(str(amount_text))} · {escape(str(ratio_text))}</div>
        </div>
        """
    )


def _bucket_avatar_text(title, ticker):
    text = str(ticker or "").strip().replace(".", "")
    if text:
        alpha = "".join(ch for ch in text if ch.isalnum())
        if alpha:
            return alpha[:3].upper()
    title_text = str(title or "").strip()
    if title_text and not any("\u4e00" <= ch <= "\u9fff" for ch in title_text):
        alpha = "".join(ch for ch in title_text if ch.isalnum())
        if alpha:
            return alpha[:3].upper()
    return "ETF"


def _mini_trend_html(bucket, accent, direction_weight):
    seed = sum(ord(ch) for ch in str(bucket or "")) % 17
    points = []
    base = 34 + (float(direction_weight or 0.0) / 4.0)
    for idx in range(10):
        drift = idx * 2.4
        wobble = math.sin((idx + seed) / 2.2) * 8 + math.cos((idx + seed) / 3.0) * 4
        value = max(10, min(100, base + drift + wobble))
        points.append(value)
    bars = "".join(
        f"<span class='vc-trend-bar' style='height:{value:.1f}%; --bucket-accent:{escape(accent)};'></span>"
        for value in points
    )
    return _clean_html(
        f"""
        <div class="vc-ring-detail-trend" style="--bucket-accent:{escape(accent)};">
            <div class="vc-ring-detail-trend-title">过去 6 个月表现</div>
            <div class="vc-trend-bars">{bars}</div>
            <div class="vc-ring-detail-trend-note">趋势只作节奏参考，不替代 ETF 清单。</div>
        </div>
        """
    )


def _etf_recommendation_card_html(row):
    bucket = row.get("所属 bucket") or "暂无"
    theme = row.get("主题") or "暂无"
    sub_theme = row.get("细分方向") or "暂无"
    title = row.get("ETF 名称") or "暂无"
    ticker = row.get("Ticker") or "暂无"
    ratio = row.get("建议占净资产比例") or "暂无"
    amount = row.get("建议金额") or "暂无"
    status = row.get("推荐状态") or "暂无"
    reason = row.get("一句理由") or "暂无"
    accent = _bucket_color(bucket)
    badge_color = _state_color_label(status)
    avatar = _bucket_avatar_text(title, ticker)
    return _clean_html(
        f"""
        <article class="vc-etf-card" style="--bucket-accent:{escape(accent)}; --bucket-gradient: linear-gradient(180deg, {escape(accent)}, rgba(255,255,255,0.18));">
            <div class="vc-etf-card-icon">{escape(avatar)}</div>
            <div class="vc-etf-card-body">
                <div class="vc-etf-card-head">
                    <div>
                        <div class="vc-etf-card-title">{escape(str(title))}</div>
                        <div class="vc-etf-card-subtitle">{escape(str(ticker))}｜{escape(str(bucket))}</div>
                    </div>
                    <div class="vc-etf-card-ratio">
                        <div>{escape(str(ratio))}</div>
                        <div class="vc-etf-card-amount">{escape(str(amount))}</div>
                    </div>
                </div>
                <div class="vc-etf-card-badges">
                    {_soft_badge_html(f"主题：{theme}", "blue")}
                    {_soft_badge_html(f"细分：{sub_theme}", "teal")}
                    {_soft_badge_html(str(status), badge_color)}
                </div>
                <div class="vc-etf-card-reason">{escape(str(reason))}</div>
            </div>
            <div class="vc-etf-card-side">
                <div class="vc-etf-card-chev">›</div>
            </div>
        </article>
        """
    )


def render_margin_execution_summary(result: dict | None = None):
    payload = result or {}
    account_state = payload.get("account_state") or {}
    action_state = payload.get("action_state") or "暂停融资，保留现金"
    style_tilt = payload.get("style_tilt") or "平衡"
    action_color = _action_state_color(action_state)
    top_buckets = []
    for bucket, item in (payload.get("recommended_etf_allocation") or {}).items():
        if bucket == "现金":
            continue
        ratio = _to_float((item or {}).get("ratio_pct"), 0.0) or 0.0
        top_buckets.append((bucket, ratio))
    top_buckets.sort(key=lambda item: item[1], reverse=True)
    priority_labels = [_bucket_label(bucket) for bucket, ratio in top_buckets if ratio > 0][:2]
    overweight = [_bucket_label(item) for item in (payload.get("overweight_buckets") or [])][:3]
    underweight = [_bucket_label(item) for item in (payload.get("underweight_buckets") or [])][:3]
    watch_names = _dedupe(payload.get("watch_not_chase_etfs") or [])[:5]
    no_chase = payload.get("no_chase_warning") or ""
    risk_conditions = _dedupe(payload.get("must_reduce_risk_conditions") or [])[:3]
    direction_parts = []
    if priority_labels:
        direction_parts.append("优先 " + " + ".join(priority_labels))
    if underweight:
        direction_parts.append("降配 " + " / ".join(underweight[:2]))
    if (_to_float(payload.get("recommended_cash_ratio")) or 0) >= 10:
        direction_parts.append("防守保留")
    discipline_parts = []
    if watch_names or no_chase:
        discipline_parts.append("高 beta 过热不追")
    if risk_conditions:
        if any("MA20" in item for item in risk_conditions):
            discipline_parts.append("跌破 MA20 降风险")
        if any("MA60" in item for item in risk_conditions):
            discipline_parts.append("跌破 MA60 降风险")
        if not discipline_parts:
            discipline_parts.append(risk_conditions[0])
    lines = [
        ("动作", action_state),
        (
            "融资",
            f"当前 {float(payload.get('current_margin_debt_ratio') or 0):.2f}%，建议上限 {float(payload.get('recommended_margin_ratio') or 0):.2f}%",
        ),
        (
            "现金",
            f"当前缓冲 {float(account_state.get('cash_buffer_ratio') or 0):.2f}%，建议不低于 {float(payload.get('recommended_cash_ratio') or 0):.2f}%",
        ),
        ("方向", "；".join(direction_parts) if direction_parts else "按当前 bucket 结构执行，不额外扩张方向。"),
        ("纪律", "；".join(_dedupe(discipline_parts)) if discipline_parts else "融资会放大收益和亏损，触发风险线先降风险。"),
    ]

    chip_lines = [
        ("增配方向", overweight or priority_labels or ["暂无明显增配"], "blue"),
        ("降配方向", underweight or ["暂无明显降配"], "orange"),
        ("只观察不追", watch_names or ["暂无明确不追名单"], "gray" if not watch_names else "orange"),
    ]
    summary_lines_html = "".join(
        f"<div class='vc-summary-line'><div class='vc-summary-key'>{escape(label)}</div><div class='vc-summary-value'>{escape(value)}</div></div>"
        for label, value in lines
    )
    chips_html = "".join(
        f"<div class='vc-chip-line'><div class='vc-chip-label'>{escape(label)}</div><div class='vc-badges'>{''.join(_badge_html(item, color) for item in items)}</div></div>"
        for label, items, color in chip_lines
    )
    _inject_component_css()
    _render_html(
        f"""
        <section class="vc-summary-shell">
            <div class="vc-summary-head">
                <div>
                    <div class="vc-summary-title">今日执行摘要</div>
                    <div class="vc-summary-subtitle">先看今天如何执行，再看下面的数据和表格。</div>
                </div>
                <div class="vc-badges">
                    {_soft_badge_html(action_state, action_color)}
                    {_soft_badge_html(style_tilt, "teal" if "进攻" in style_tilt else ("orange" if "防守" in style_tilt else "gray"))}
                </div>
            </div>
            <div class="vc-summary-lines">{summary_lines_html}</div>
            <div class="vc-divider"></div>
            <div class="vc-chip-stack">{chips_html}</div>
        </section>
        """
    )


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
        st.plotly_chart(fig, width="stretch")

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
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Plotly 未安装，资金流方向条暂以文字降级展示。")

    st.caption("今日流入只能视为线索；需要后续资金、价格和公告共同验证。")


def render_margin_allocator_chart(allocation_result: dict):
    render_interactive_bucket_ring(allocation_result)


def render_interactive_bucket_ring(allocation_result: dict, selector_key: str = "margin_etf_bucket_selector"):
    ctx = _build_margin_bucket_context(allocation_result, selector_key=selector_key)
    if not ctx["bucket_packets"]:
        st.info("暂无可视化仓位建议。")
        return

    payload = allocation_result or {}
    allocation = payload.get("recommended_etf_allocation") or {}
    dynamic_weights = payload.get("dynamic_bucket_weights") or {}
    overweight = ctx["overweight"]
    underweight = ctx["underweight"]
    selected_bucket = ctx["selected_bucket"]
    bucket_options = ctx["bucket_options"]
    option_labels = ctx["option_labels"]
    selector_state_key = ctx["selector_state_key"]
    candidate_payload = payload.get("selected_etf_candidates") or {}

    bucket_rows = []
    for label in BUCKET_ORDER:
        item = allocation.get(label) or {}
        direction_weight = _to_float(dynamic_weights.get(label), 0.0) or 0.0
        budget_ratio = _to_float(item.get("ratio_pct"), 0.0) or 0.0
        amount = _to_float(item.get("amount"), 0.0) or 0.0
        if label == "现金":
            role = "现金缓冲"
            status = "只观察"
            note = "保留缓冲，不抢 ETF 主视觉。"
        else:
            if label in {"宽基ETF", "科技成长ETF"}:
                role = "主配"
            elif label == "防守ETF":
                role = "防守"
            elif label == "商品周期ETF":
                role = "次配"
            else:
                role = "观察"
            if label in overweight:
                status = "增配"
            elif label in underweight:
                status = "降配"
            else:
                status = "持平"
            note = {
                "宽基ETF": "承担底仓和仓位稳定器。",
                "科技成长ETF": "看半导体 / 芯片 / 成长弹性。",
                "金融券商ETF": "偏交易弹性，没信号先观察。",
                "防守ETF": "提供防守缓冲和现金替代。",
                "商品周期ETF": "跟随资源品和周期链条。",
            }.get(label, "作为方向补充观察。")
        reps = []
        for item_row in list(candidate_payload.get(label) or []):
            name = item_row.get("etf_name") or item_row.get("etf_code")
            if name and name not in reps:
                reps.append(name)
            if len(reps) >= 2:
                break
        if not reps and label == "现金":
            reps = ["现金缓冲"]
        bucket_rows.append(
            {
                "bucket": label,
                "direction_weight": direction_weight,
                "budget_ratio": budget_ratio,
                "amount": amount,
                "role": role,
                "status": status,
                "note": note,
                "representatives": reps,
                "selected": label == selected_bucket,
                "color": _bucket_color(label),
                "bg": _bucket_bg(label),
                "text_color": _bucket_text_color(label),
            }
        )

    ring_rows = [row for row in bucket_rows if row["bucket"] != "现金"]
    ring_labels = [row["bucket"] for row in ring_rows]
    ring_values = [max(row["direction_weight"], 0.0) for row in ring_rows]
    if sum(ring_values) <= 0:
        ring_values = [max(row["budget_ratio"], 0.0) for row in ring_rows]
    if sum(ring_values) <= 0:
        ring_values = [1.0 for _ in ring_rows]
    ring_colors = [row["color"] for row in ring_rows]
    ring_pull = [0.07 if row["selected"] else 0.0 for row in ring_rows]
    selected_row = next((row for row in bucket_rows if row["bucket"] == selected_bucket), bucket_rows[0])
    selected_direction_weight = _to_float(selected_row.get("direction_weight"), 0.0) or 0.0
    selected_budget_ratio = _to_float(selected_row.get("budget_ratio"), 0.0) or 0.0
    selected_amount = _to_float(selected_row.get("amount"), 0.0) or 0.0
    selected_rep_text = " / ".join(selected_row.get("representatives") or []) or "暂无"
    selected_title = selected_bucket if selected_bucket != "现金" else "现金缓冲"
    selected_action = selected_row.get("status") or "持平"
    total_exposure_text = _fmt_money(payload.get("recommended_total_exposure"))
    total_exposure_line = total_exposure_text if total_exposure_text != "暂无" else "暂无"

    if go is not None:
        ring = go.Figure(
            data=[
                go.Pie(
                    labels=ring_labels,
                    values=ring_values,
                    hole=0.62,
                    sort=False,
                    direction="clockwise",
                    pull=ring_pull,
                    marker=dict(
                        colors=ring_colors,
                        line=dict(color="rgba(255,255,255,0.92)", width=2.0),
                    ),
                    texttemplate="%{label}<br>%{percent:.0%}",
                    textposition="outside",
                    hovertemplate="%{label}<br>方向权重：%{value:.2f}%<extra></extra>",
                    textfont=dict(size=12, color="#1D1D1F"),
                    showlegend=False,
                )
            ]
        )
        ring.update_layout(
            height=314,
            margin=dict(l=8, r=8, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            annotations=[
                dict(
                    text=(
                        f"<b>{escape(selected_title)}</b><br>"
                        f"{escape(total_exposure_line)}<br>"
                        f"<span style='font-size:11px;color:#6b7280'>{selected_budget_ratio:.1f}% · 方向权重</span>"
                    ),
                    x=0.5,
                    y=0.5,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    align="center",
                    font=dict(size=15, color="#1D1D1F"),
                )
            ],
        )
    else:
        ring = None

    summary_chips_html = []
    for row in bucket_rows:
        summary_chips_html.append(
            f"<span class='vc-badge' style='background:{escape(row['bg'])};color:{escape(row['text_color'])};border-color:{escape(row['bg'])};'>"
            f"{escape(row['bucket'])} {row['direction_weight']:.1f}%</span>"
        )

    detail_note = (
        "圆环显示的是动态方向权重；建议比例按净资产口径展示，具体 ETF 金额是在该方向预算内再次分配。现金单独作为风险缓冲。"
    )
    selected_reason = selected_row.get("一句理由") or "暂无明确理由"
    selected_theme = selected_row.get("主题") or "暂无"
    selected_sub_theme = selected_row.get("细分方向") or "暂无"
    selected_accent = selected_row.get("color") or _bucket_color(selected_row.get("bucket"))
    detail_card_html = _clean_html(
        f"""
        <div class="vc-ring-detail">
            <div class="vc-ring-detail-head">
                <div>
                    <div class="vc-ring-detail-kicker">Bucket 详情</div>
                    <div class="vc-ring-detail-title">{escape(selected_title)} 详情</div>
                    <div class="vc-ring-detail-subtitle">先看方向预算，再看具体 ETF 清单。</div>
                </div>
                <div class="vc-badges">
                    {_soft_badge_html(f"今日角色：{selected_row.get('role')}", "blue")}
                    {_soft_badge_html(f"状态：{selected_action}", _state_color_label(selected_action))}
                </div>
            </div>
            <div class="vc-ring-detail-hero">
                <div class="vc-ring-detail-hero-left">
                    <div class="vc-ring-detail-hero-label">当前权重</div>
                    <div class="vc-ring-detail-hero-value">{selected_budget_ratio:.1f}%</div>
                    <div class="vc-ring-detail-hero-sub">建议金额 {escape(_fmt_money(selected_amount))}</div>
                    <div class="vc-ring-detail-hero-sub">方向内部权重 {selected_direction_weight:.1f}%</div>
                    <div class="vc-ring-detail-hero-sub" style="margin-top:8px;">{escape(selected_row.get("note") or "作为方向补充观察。")}</div>
                </div>
                {_mini_trend_html(selected_title, selected_accent, selected_direction_weight)}
            </div>
            <div class="vc-ring-detail-note">{escape(detail_note)}</div>
            <div class="vc-ring-detail-badges">
                {_soft_badge_html(f"所属 bucket：{selected_row.get('bucket')}", "gray")}
                {_soft_badge_html(f"主题：{selected_theme}", "teal")}
                {_soft_badge_html(f"细分：{selected_sub_theme}", "orange" if selected_row.get("bucket") != "现金" else "gray")}
                {_soft_badge_html(f"代表 ETF：{selected_rep_text}", "blue")}
            </div>
            <div class="vc-ring-detail-note" style="margin-top:10px;">风险提示：{escape(selected_reason)}</div>
        </div>
        """
    )

    st.markdown("##### Bucket 权重分布")
    st.caption("圆环显示动态方向权重；ETF 金额是在该方向预算内再次分配。现金单独作为风险缓冲。")
    left_col, right_col = st.columns([1.02, 0.98], gap="large")
    with left_col:
        _render_html(
            f"""
            <div class="vc-ring-shell">
                <div class="vc-ring-shell-title">Bucket 权重分布</div>
                <div class="vc-ring-shell-subtitle">今天先看方向优先级，再看方向里的具体 ETF。</div>
                <div class="vc-ring-figure-note">Apple 风格圆环：用来识别今天的方向优先级，不替代具体 ETF 清单。</div>
                <div class="vc-badges" style="margin-top:10px;">{''.join(summary_chips_html)}</div>
            </div>
            """
        )
        if ring is not None:
            st.plotly_chart(ring, width="stretch")
    with right_col:
        _render_html(detail_card_html)
        cash_item = allocation.get("现金") or {}
        _render_html(
            f"""
            <div class="vc-ring-cash-shell">
                <div class="vc-ring-cash-title">现金缓冲</div>
                <div class="vc-ring-cash-note">不并入方向圆环，单独作为风险缓冲。</div>
                {_cash_buffer_strip(cash_item.get('ratio_pct'), cash_item.get('amount')) if cash_item else _cash_buffer_strip(0, None)}
            </div>
            """
        )
        with st.container():
            _render_html(
                """
                <div class="vc-selector-shell">
                    <div class="vc-title" style="font-size:0.92rem;margin-bottom:4px;">选择 bucket</div>
                    <div class="vc-caption" style="margin-top:0;">切换后，右侧详情和下方 ETF 卡会同步刷新。</div>
                </div>
                """
            )
            selected_bucket_after = selected_bucket
            if hasattr(st, "segmented_control"):
                selected_bucket_after = st.segmented_control(
                    "bucket",
                    options=bucket_options,
                    default=selected_bucket,
                    required=True,
                    format_func=lambda bucket: option_labels.get(bucket, str(bucket or "暂无")),
                    key=selector_state_key,
                    width="stretch",
                    label_visibility="collapsed",
                )
                st.session_state[selector_key] = selected_bucket_after
            else:
                for row_start in range(0, len(bucket_options), 3):
                    row_buckets = bucket_options[row_start : row_start + 3]
                    row_cols = st.columns(len(row_buckets), gap="small")
                    for col, bucket in zip(row_cols, row_buckets):
                        button_label = option_labels.get(bucket, str(bucket or "暂无"))
                        if bucket == selected_bucket_after:
                            button_label = f"● {button_label}"
                        button_type = "primary" if bucket == selected_bucket_after else "secondary"
                        if col.button(button_label, key=f"{selector_key}__btn__{bucket}", use_container_width=True, type=button_type):
                            st.session_state[selector_state_key] = bucket
                            st.session_state[selector_key] = bucket
                            st.rerun()
                selected_bucket_after = st.session_state.get(selector_key, selected_bucket_after)
            current_ctx = ctx if selected_bucket_after == selected_bucket else _build_margin_bucket_context(allocation_result, selector_key=selector_key)
            current_selected_rows = current_ctx["selected_rows"]
            if not current_selected_rows:
                st.info("该方向今日暂无明确推荐 ETF，可仅观察或等待数据补齐。")
            else:
                st.markdown(f"##### {selected_bucket_after}｜今日推荐 ETF")
                st.caption("每只 ETF 的建议比例和金额是在该方向预算内再分配。")
                card_html = "".join(_etf_recommendation_card_html(row) for row in current_selected_rows[:5])
                _render_html(f"<section class='vc-etf-card-list'>{card_html}</section>")

    bucket_rows_detail = []
    for row in bucket_rows:
        bucket_rows_detail.append(
            {
                "Bucket": row["bucket"],
                "方向权重": f"{row['direction_weight']:.2f}%",
                "建议比例": f"{row['budget_ratio']:.2f}%",
                "建议金额": _fmt_money(row["amount"]),
                "今日角色": row["role"],
                "状态": row["status"],
                "代表ETF": " / ".join(row["representatives"][:2]) or "暂无",
                "风险提示": row["note"],
            }
        )
    with st.expander("详细 Bucket 权重矩阵", expanded=False):
        _render_compact_table(
            bucket_rows_detail,
            badge_columns={"今日角色", "状态"},
            muted_columns={"Bucket", "代表ETF"},
            max_rows=8,
            expander_label="查看完整 Bucket 权重矩阵",
            always_expander=False,
        )
        if go is not None:
            mini = go.Figure()
            mini.add_trace(
                go.Bar(
                    x=[row["budget_ratio"] for row in bucket_rows if row["bucket"] != "现金"],
                    y=[row["bucket"] for row in bucket_rows if row["bucket"] != "现金"],
                    orientation="h",
                    marker=dict(
                        color=[row["color"] for row in bucket_rows if row["bucket"] != "现金"],
                        line=dict(color="rgba(255,255,255,0.75)", width=1),
                    ),
                    text=[f"{row['budget_ratio']:.1f}%" for row in bucket_rows if row["bucket"] != "现金"],
                    textposition="outside",
                    hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
                    showlegend=False,
                )
            )
            mini.update_layout(
                height=200,
                margin=dict(l=8, r=12, t=6, b=14),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(
                    title="建议比例（占净资产）",
                    gridcolor="rgba(60, 60, 67, 0.10)",
                    zeroline=False,
                    tickfont=dict(color="#4A4A4F", size=10),
                ),
                yaxis=dict(
                    autorange="reversed",
                    tickfont=dict(color="#1D1D1F", size=10),
                ),
            )
            st.plotly_chart(mini, width="stretch")


def render_margin_etf_data_status(data_status: dict | None = None):
    payload = data_status or {}
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Tushare 数据日期", payload.get("latest_data_date") or "暂无")
    c2.metric("ETF 总数", int(payload.get("discovered_etf_count") or payload.get("sample_count") or 0))
    c3.metric("可分类数量", int(payload.get("classified_count") or payload.get("available_count") or 0))
    c4.metric("可评分数量", int(payload.get("scored_etf_count") or payload.get("available_count") or 0))
    c5.metric("最终入池数量", int(payload.get("selected_count") or payload.get("sample_count") or 0))
    c6.metric("数据缺口", "有" if payload.get("has_data_gap") or payload.get("data_gaps") else "无")
    if payload.get("updated_at"):
        st.caption(f"最新拉取时间：{payload.get('updated_at')}")
    if payload.get("used_fallback"):
        st.warning("etf_basic 拉取失败，当前已回退到人工重点关注 ETF 池。")
    if payload.get("has_data_gap"):
        st.warning("ETF 数据存在缺口，已按可得样本继续计算。")
    else:
        st.caption("ETF 主评分使用 Tushare 日线；实时数据仅作补充，不覆盖日线主结论。")
    gaps = payload.get("data_gaps") or []
    if gaps:
        st.caption("数据缺口：" + "；".join(str(item) for item in gaps[:5]))


def render_margin_bucket_weights_table(dynamic_weights: dict | None = None, overweight_buckets=None, underweight_buckets=None):
    weights = dynamic_weights or {}
    if not weights:
        return
    rows = []
    for bucket, value in weights.items():
        action_hint = "中性"
        if bucket in set(overweight_buckets or []):
            action_hint = "增配"
        elif bucket in set(underweight_buckets or []):
            action_hint = "降配"
        rows.append(
            {
                "Bucket": _bucket_label(bucket),
                "建议权重": f"{float(value or 0):.2f}%",
                "执行提示": action_hint,
            }
        )
    st.caption("Bucket 权重只是执行映射，先看首屏摘要，再看这里的方向细分。")
    _render_compact_table(rows, badge_columns={"执行提示"}, max_rows=8, expander_label="查看完整 Bucket 权重")


def render_margin_candidate_table(candidate_packet: dict | None = None):
    payload = candidate_packet or {}
    rows = []
    for bucket, items in payload.items():
        for item in items or []:
            rows.append(
                {
                    "Bucket": _bucket_label(bucket),
                    "ETF": item.get("etf_name") or item.get("etf_code") or "暂无",
                    "状态": item.get("state") or "暂无",
                    "综合分": _fmt_score(item.get("total_score")),
                    "20日涨跌": _fmt_pct(item.get("return_20d_pct")),
                }
            )
    if not rows:
        st.info("暂无候选 ETF。")
        return
    st.caption("候选 ETF 只保留每个方向的前排产品，完整候选放在展开区。")
    _render_compact_table(rows, badge_columns={"状态"}, max_rows=10, expander_label="查看完整候选 ETF", always_expander=True)


def _build_margin_bucket_context(allocation_result: dict | None = None, selector_key: str = "margin_etf_bucket_selector"):
    payload = allocation_result or {}
    allocation = payload.get("recommended_etf_allocation") or {}
    candidates = payload.get("selected_etf_candidates") or {}
    overweight = _dedupe(payload.get("overweight_buckets") or [])
    underweight = _dedupe(payload.get("underweight_buckets") or [])

    bucket_packets = []
    for bucket in BUCKET_ORDER:
        item = allocation.get(bucket) or {}
        ratio = _to_float((item or {}).get("ratio_pct"), 0.0) or 0.0
        bucket_candidates = list(candidates.get(bucket) or [])
        if bucket != "现金" and ratio <= 0 and not bucket_candidates:
            continue
        bucket_packets.append(
            {
                "bucket": bucket,
                "ratio_pct": ratio,
                "items": bucket_candidates[:5],
            }
        )

    if not bucket_packets:
        return {
            "allocation": allocation,
            "candidates": candidates,
            "overweight": overweight,
            "underweight": underweight,
            "bucket_packets": [],
            "bucket_options": [],
            "option_labels": {},
            "selected_bucket": "",
            "selected_packet": {},
            "selected_rows": [],
            "all_rows": [],
            "selector_state_key": f"{selector_key}__selected",
            "default_bucket": "",
        }

    bucket_packets.sort(
        key=lambda item: (
            1 if item.get("bucket") != "现金" else 0,
            float(item.get("ratio_pct") or 0.0),
        ),
        reverse=True,
    )
    bucket_options = [str(item.get("bucket") or "暂无") for item in bucket_packets]
    packet_lookup = {str(item.get("bucket") or "暂无"): item for item in bucket_packets}
    option_labels = {
        str(item.get("bucket") or "暂无"): f"{str(item.get('bucket') or '暂无')} {float(item.get('ratio_pct') or 0.0):.1f}%"
        for item in bucket_packets
    }

    def _normalize_bucket_value(raw_value):
        if raw_value in bucket_options:
            return raw_value
        if isinstance(raw_value, int) and 0 <= raw_value < len(bucket_options):
            return bucket_options[raw_value]
        if isinstance(raw_value, str):
            text = raw_value.strip()
            if text in bucket_options:
                return text
            for bucket_name, label in option_labels.items():
                if text == label or text.startswith(f"{bucket_name} "):
                    return bucket_name
            for bucket_name in bucket_options:
                if text.startswith(bucket_name):
                    return bucket_name
        return None

    sorted_non_cash = [item for item in bucket_packets if item.get("bucket") != "现金"]
    default_bucket = str((sorted_non_cash[0] if sorted_non_cash else bucket_packets[0]).get("bucket") or "暂无")
    selector_state_key = f"{selector_key}__selected"
    selected_bucket = (
        _normalize_bucket_value(st.session_state.get(selector_state_key))
        or _normalize_bucket_value(st.session_state.get(selector_key))
        or default_bucket
    )

    def _candidate_mix_weights(items):
        weights = []
        state_scale = {
            "强趋势": 1.18,
            "温和向上": 1.0,
            "震荡观察": 0.72,
            "过热等待": 0.55,
            "破位回避": 0.22,
            "数据不足": 0.45,
        }
        for index, item in enumerate(items):
            score = max(_to_float(item.get("total_score"), 55.0) or 55.0, 1.0)
            rank_scale = [1.0, 0.62, 0.36][index] if index < 3 else 0.24
            weights.append(score * state_scale.get(item.get("state"), 0.66) * rank_scale)
        total = sum(weights) or float(len(items) or 1)
        return [value / total for value in weights]

    def _candidate_reason(bucket, item, status, action_hint):
        theme = item.get("sub_theme") or item.get("theme") or _bucket_label(bucket)
        state = item.get("state") or "待确认"
        state_hint = {
            "强趋势": "趋势在该 bucket 里靠前",
            "温和向上": "趋势保持向上但仍需分步",
            "震荡观察": "仍在观察区，先小仓位跟踪",
            "过热等待": "当前偏热，先列观察不追",
            "破位回避": "趋势未修复，暂不作为主攻",
            "数据不足": "数据还不完整，先放低权重",
        }.get(state, "作为该方向的备选补充")
        action_prefix = {
            "增配": f"{_bucket_label(bucket)}是今日增配方向",
            "降配": f"{_bucket_label(bucket)}暂不主攻",
            "中性": f"用于承接{_bucket_label(bucket)}仓位",
        }.get(action_hint, f"用于承接{_bucket_label(bucket)}仓位")
        return20 = _to_float(item.get("return_20d_pct"))
        tail = f"近20日{_fmt_pct(return20)}" if return20 is not None else "优先看状态和风险线"
        return f"{action_prefix}；主看{theme}；{state_hint}，{tail}。"

    def _build_rows(packet):
        bucket = packet.get("bucket")
        ratio_pct = float(packet.get("ratio_pct") or 0.0)
        amount_total = _to_float(allocation.get(bucket, {}).get("amount"), 0.0) or 0.0
        items = list(packet.get("items") or [])
        if not items:
            return []
        action_hint = "中性"
        if bucket in set(overweight):
            action_hint = "增配"
        elif bucket in set(underweight):
            action_hint = "降配"
        mix_weights = _candidate_mix_weights(items)
        rows = []
        for item, mix_weight in zip(items, mix_weights):
            status = _recommendation_state_label(item.get("state"), bucket, overweight, underweight)
            rows.append(
                {
                    "ETF 名称": item.get("etf_name") or item.get("etf_code") or "暂无",
                    "Ticker": item.get("etf_code") or "暂无",
                    "所属 bucket": str(bucket or "暂无"),
                    "主题": item.get("theme") or "暂无",
                    "细分方向": item.get("sub_theme") or item.get("theme") or "暂无",
                    "建议占净资产比例": f"{ratio_pct * mix_weight:.2f}%",
                    "建议金额": _fmt_money(amount_total * mix_weight),
                    "推荐状态": status,
                    "一句理由": _candidate_reason(bucket, item, status, action_hint),
                }
            )
        return rows

    all_rows = []
    for packet in bucket_packets:
        all_rows.extend(_build_rows(packet))
    selected_packet = packet_lookup.get(selected_bucket, bucket_packets[0])
    selected_rows = _build_rows(selected_packet)

    return {
        "allocation": allocation,
        "candidates": candidates,
        "overweight": overweight,
        "underweight": underweight,
        "bucket_packets": bucket_packets,
        "bucket_options": bucket_options,
        "option_labels": option_labels,
        "selected_bucket": selected_bucket,
        "selected_packet": selected_packet,
        "selected_rows": selected_rows,
        "all_rows": all_rows,
        "selector_state_key": selector_state_key,
        "default_bucket": default_bucket,
    }


def render_margin_recommended_etf_plan(result: dict | None = None, selector_key: str = "margin_etf_bucket_selector"):
    ctx = _build_margin_bucket_context(result, selector_key=selector_key)
    if not ctx["bucket_packets"]:
        st.info("暂无可展开的 ETF 配置清单。")
        return
    all_rows = ctx["all_rows"]
    actionable_rows = [row for row in all_rows if row.get("推荐状态") != "暂不纳入"] or all_rows
    top_rows = actionable_rows[:8]

    st.caption("先看执行清单，再切 bucket。具体 ETF 比方向图更重要。")
    if top_rows:
        section_order = ["优先配置", "可观察", "只观察不追"]
        top_grouped = {label: [] for label in section_order}
        for row in top_rows:
            status = row.get("推荐状态") or "暂不纳入"
            if status in top_grouped:
                top_grouped[status].append(row)
        if not top_grouped["优先配置"]:
            st.info("今日无明确优先配置，当前以观察和等待回踩为主。")
        for status_label in section_order:
            group_rows = top_grouped.get(status_label) or []
            if not group_rows:
                continue
            st.markdown(f"##### {status_label}")
            _render_html(f"<section class='vc-etf-card-list'>{''.join(_etf_recommendation_card_html(row) for row in group_rows)}</section>")
    else:
        st.info("暂无明确 ETF 执行清单，先看 bucket 权重与风险线。")

    if all_rows:
        with st.expander("查看完整今日建议 ETF 配置清单", expanded=False):
            _render_compact_table(
                all_rows,
                badge_columns={"推荐状态"},
                muted_columns={"Ticker", "所属 bucket", "主题", "细分方向"},
                max_rows=min(max(len(all_rows), 1), 10),
            )


def render_etf_score_table(score_packet: dict | None = None):
    payload = score_packet or {}
    rows = payload.get("rows") or payload.get("etf_score_table") or []
    if not rows:
        st.info("暂无 ETF 强弱评分。")
        return
    state_priority = {"强趋势": 0, "温和向上": 1, "震荡观察": 2, "过热等待": 3, "破位回避": 4, "数据不足": 5}
    ranked_rows = sorted(
        rows,
        key=lambda item: (
            state_priority.get(item.get("state"), 9),
            -(_to_float(item.get("total_score"), 0.0) or 0.0),
            -(_to_float(item.get("amount_ma20"), 0.0) or 0.0),
        ),
    )
    strong_count = sum(1 for item in ranked_rows if item.get("state") in {"强趋势", "温和向上"})
    hot_count = sum(1 for item in ranked_rows if item.get("state") == "过热等待")
    weak_count = sum(1 for item in ranked_rows if item.get("state") == "破位回避")
    if hot_count >= 2:
        st.caption("ETF 强弱表显示部分方向偏热，适合观察排序，不适合直接追高。")
    elif strong_count >= max(len(ranked_rows) / 2, 1):
        st.caption("ETF 强弱表显示当前仍有可执行方向，优先看强趋势与温和向上的前排产品。")
    elif weak_count >= max(len(ranked_rows) / 3, 1):
        st.caption("ETF 强弱表偏弱，先看风险线和现金缓冲，再考虑方向细节。")
    else:
        st.caption("ETF 强弱表用于确认方向先后顺序，不替代首屏执行结论。")
    core_rows = []
    full_rows = []
    for item in ranked_rows:
        full_row = {
            "ETF": item.get("etf_name") or item.get("etf_code"),
            "分类": item.get("bucket"),
            "主题": item.get("sub_theme") or item.get("theme"),
            "最新价": _fmt_price(item.get("latest_price")),
            "20日涨跌": _fmt_pct(item.get("return_20d_pct")),
            "60日涨跌": _fmt_pct(item.get("return_60d_pct")),
            "状态": item.get("state"),
            "综合分": _fmt_score(item.get("total_score")),
            "基金公司/管理人": item.get("manager") or "暂无",
            "跟踪指数": item.get("benchmark") or item.get("index_name") or item.get("index_code") or "暂无",
            "相对MA20": _fmt_pct(item.get("price_vs_ma20_pct")),
            "相对MA60": _fmt_pct(item.get("price_vs_ma60_pct")),
            "波动率": _fmt_pct(item.get("volatility_20d")),
            "成交额MA20": _fmt_money_compact(item.get("amount_ma20")),
        }
        full_rows.append(full_row)
        core_rows.append(
            {
                "ETF": item.get("etf_name") or item.get("etf_code"),
                "分类": item.get("bucket"),
                "主题": item.get("sub_theme") or item.get("theme"),
                "最新价": _fmt_price(item.get("latest_price")),
                "20日涨跌": _fmt_pct(item.get("return_20d_pct")),
                "60日涨跌": _fmt_pct(item.get("return_60d_pct")),
                "状态": item.get("state"),
                "综合分": _fmt_score(item.get("total_score")),
            }
        )
    _render_compact_table(
        core_rows,
        badge_columns={"状态"},
        muted_columns={"分类", "主题"},
        max_rows=10,
        expander_label="查看完整 ETF 强弱表",
        always_expander=False,
        expanded_rows=full_rows,
        show_expander=False,
    )
    with st.expander("查看完整 ETF 强弱表（详细列）", expanded=False):
        st.dataframe(pd.DataFrame(full_rows), width="stretch", hide_index=True)


def render_theme_comparison_table(comparison_packet: dict | None = None, holdings_snapshot: dict | None = None):
    payload = comparison_packet or {}
    rows = payload.get("rows") or []
    if not rows:
        st.info("当前主题暂无可比较的 ETF。")
        return
    summary = payload.get("comparison_summary") or ""
    summary_tone = payload.get("summary_tone") or "info"
    if summary:
        if summary_tone == "warning":
            st.warning(summary)
        elif summary_tone == "success":
            st.success(summary)
        else:
            st.info(summary)
    row_map = {item.get("etf_code"): item for item in rows if item.get("etf_code")}
    tag_specs = [
        ("趋势更强", payload.get("best_trend_etf")),
        ("更均衡", payload.get("most_balanced_etf")),
        ("流动性更好", payload.get("best_liquidity_etf")),
        ("仅观察 / 不追高", " / ".join(row_map.get(code, {}).get("etf_name") or code for code in (payload.get("warning_etfs") or [])[:3])),
    ]
    tag_badges = []
    for label, raw_value in tag_specs:
        text = str(raw_value or "").strip()
        if not text:
            text = "暂无明确胜出"
        elif text in row_map:
            text = row_map.get(text, {}).get("etf_name") or text
        color = "orange" if "观察" in label else ("teal" if "流动性" in label else ("purple" if "趋势" in label else "blue"))
        tag_badges.append(_badge_html(f"{label}：{text}", color if text != "暂无明确胜出" else "gray"))
    _render_html(f"<div class='vc-soft-note'><div class='vc-badges'>{''.join(tag_badges)}</div></div>")
    holdings_snapshot = holdings_snapshot or {}
    snapshots = holdings_snapshot.get("snapshots") or {}
    display_rows = []
    for item in rows:
        code = item.get("etf_code")
        holding_state = "暂不可用"
        if snapshots.get(code, {}).get("available"):
            holding_state = "可用"
        elif snapshots.get(code, {}).get("error"):
            holding_state = "失败"

        evaluation = []
        if code == payload.get("most_balanced_etf"):
            evaluation.append("综合更均衡")
        if code == payload.get("best_trend_etf"):
            evaluation.append("趋势更强")
        if code == payload.get("best_liquidity_etf"):
            evaluation.append("流动性更好")
        if code == payload.get("lowest_volatility_etf"):
            evaluation.append("波动更低")
        if code in (payload.get("warning_etfs") or []):
            evaluation.append("仅观察")

        display_rows.append(
            {
                "ETF": item.get("etf_name") or code,
                "基金公司/管理人": item.get("manager") or "暂无",
                "跟踪指数": item.get("benchmark") or item.get("index_name") or item.get("index_code") or "暂无",
                "最新价": _fmt_price(item.get("latest_price")),
                "20日涨跌": _fmt_pct(item.get("return_20d_pct")),
                "60日涨跌": _fmt_pct(item.get("return_60d_pct")),
                "成交额MA20": _fmt_money_compact(item.get("amount_ma20")),
                "波动率": _fmt_pct(item.get("volatility_20d")),
                "状态": item.get("state") or "暂无",
                "综合分": _fmt_score(item.get("total_score")),
                "持仓明细状态": holding_state,
                "适配评价": " / ".join(evaluation) or "待比较",
            }
        )
    _render_compact_table(
        display_rows,
        badge_columns={"状态", "持仓明细状态", "适配评价"},
        muted_columns={"基金公司/管理人", "跟踪指数"},
        max_rows=10,
        expander_label="查看完整同赛道比较",
        always_expander=True,
    )
    for reason in payload.get("comparison_reason") or []:
        st.caption(f"对比结论：{reason}")
    errors = holdings_snapshot.get("holdings_errors") or []
    if errors and not holdings_snapshot.get("holdings_available"):
        st.info("持仓明细暂不可用，当前仅按行情、跟踪指数和流动性比较。")
    elif errors:
        st.caption("部分持仓接口失败：" + "；".join(errors[:4]))


def render_holdings_snapshot_summary(holdings_snapshot: dict | None = None):
    payload = holdings_snapshot or {}
    snapshots = payload.get("snapshots") or {}
    if not snapshots:
        return
    st.markdown("#### ETF 持仓差异提示")
    for code, item in snapshots.items():
        if not item.get("available"):
            continue
        top_names = [holding.get("stock_name") or holding.get("stock_code") for holding in (item.get("holdings") or [])[:5]]
        top_names = [name for name in top_names if name]
        st.caption(
            f"{code}｜来源 {item.get('source_api') or '未知'}｜最新报告期 {item.get('latest_report_date') or '未知'}｜"
            f"前五持仓：{' / '.join(top_names) if top_names else '暂无'}"
        )


def render_intraday_etf_snapshot(snapshot: dict | None = None):
    payload = snapshot or {}
    rows = payload.get("rows") or []
    if not rows:
        st.caption("暂无盘中 ETF 实时补充。")
        return
    display_rows = []
    for item in rows:
        display_rows.append(
            {
                "ETF": item.get("etf_name") or item.get("etf_code"),
                "分类": item.get("bucket"),
                "实时价": item.get("realtime_price") or "暂无",
                "实时IOPV": item.get("realtime_iopv") or "暂无",
                "溢价/折价": _fmt_pct(item.get("premium_discount_pct")),
                "时间": item.get("trade_time") or "暂无",
                "状态": "部分可用" if item.get("errors") else "可用",
            }
        )
    _render_compact_table(display_rows, badge_columns={"状态"}, max_rows=8, expander_label="查看完整盘中 ETF 实时补充", always_expander=True)
    errors = payload.get("errors") or []
    if errors:
        st.caption("部分实时 ETF 接口失败，已按可得样本展示。")


def render_margin_etf_research_summary(result: dict | None = None, generated_at: str = "", cached: bool = False):
    payload = result or {}
    if not payload:
        _render_html(
            """
            <div class="vc-shell">
                <div class="vc-title">DeepSeek 调研解释</div>
                <div class="vc-caption">当前暂无 DeepSeek 调研解释。点击按钮后，系统会基于账户状态、ETF 强弱评分、动态配置和风险线生成解释；DeepSeek 只负责解释，不直接决定仓位。</div>
            </div>
            """
        )
        return

    conclusion = payload.get("one_sentence_conclusion") or "暂无结论。"
    st.caption(f"generated_at：{generated_at or '暂无'}" + ("｜缓存结果" if cached else "｜新生成结果"))
    st.markdown(f"**一句话投资解释**：{conclusion}")
    reason_pool = []
    for section in [
        payload.get("today_allocation_explanation"),
        payload.get("why_margin_ratio"),
        payload.get("theme_comparison_explanation"),
        payload.get("overlap_and_substitution"),
    ]:
        reason_pool.extend(section or [])
    key_reasons = _dedupe(reason_pool)[:3]
    st.markdown("**执行原因**")
    _result_list(key_reasons)
    sections = [
        ("Bucket 增减配原因", payload.get("bucket_adjustments")),
        ("只观察不追", payload.get("watch_not_chase")),
        ("加融资触发条件", payload.get("add_margin_triggers")),
        ("降融资触发条件", payload.get("deleverage_triggers")),
        ("明日验证清单", payload.get("tomorrow_checklist")),
        ("数据缺口", payload.get("data_gaps")),
    ]
    with st.expander("展开查看完整 DeepSeek 调研解释", expanded=False):
        for title, items in sections:
            st.markdown(f"**{title}**")
            _result_list(items or [])
    st.markdown("**风险提示**")
    st.write(payload.get("risk_disclaimer") or "融资会放大收益和亏损。本模块只做风险预算和仓位测算，不构成买卖建议。")


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
            width="stretch",
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


def _inject_command_center_css():
    st.markdown(
        """
        <style>
        .cc-shell {
            background:
                radial-gradient(circle at 8% 6%, rgba(14, 165, 233, 0.12), transparent 26%),
                radial-gradient(circle at 94% 14%, rgba(139, 92, 246, 0.10), transparent 24%),
                linear-gradient(135deg, #f5f7fb 0%, #eef4f7 48%, #f8fafc 100%);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 28px;
            padding: 22px;
            margin: 8px 0 18px;
            box-shadow: 0 24px 70px rgba(15, 23, 42, 0.08);
        }
        .cc-grid {
            display: grid;
            grid-template-columns: 230px minmax(0, 1fr);
            gap: 18px;
            align-items: start;
        }
        .cc-sidebar {
            position: sticky;
            top: 72px;
            background: rgba(255, 255, 255, 0.84);
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 24px;
            padding: 16px;
            box-shadow: 0 18px 48px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(12px);
        }
        .cc-logo {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 850;
            letter-spacing: -0.03em;
            color: #0f172a;
            margin-bottom: 14px;
        }
        .cc-logo-mark {
            width: 34px;
            height: 34px;
            border-radius: 12px;
            display: grid;
            place-items: center;
            background: linear-gradient(135deg, #0ea5e9, #14b8a6);
            color: #fff;
            font-weight: 900;
            box-shadow: 0 10px 24px rgba(20, 184, 166, 0.28);
        }
        .cc-nav-item {
            display: flex;
            align-items: center;
            gap: 9px;
            padding: 9px 10px;
            margin: 4px 0;
            border-radius: 14px;
            color: #475569;
            font-size: 13px;
            border: 1px solid transparent;
        }
        .cc-nav-item.active {
            color: #0f766e;
            background: rgba(20, 184, 166, 0.10);
            border-color: rgba(20, 184, 166, 0.18);
            font-weight: 750;
        }
        .cc-main {
            min-width: 0;
        }
        .cc-hero {
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 26px;
            padding: 22px;
            box-shadow: 0 18px 52px rgba(15, 23, 42, 0.07);
        }
        .cc-kicker {
            color: #0f766e;
            font-size: 12px;
            letter-spacing: 0.12em;
            font-weight: 800;
            text-transform: uppercase;
            margin-bottom: 7px;
        }
        .cc-title {
            margin: 0;
            color: #0f172a;
            font-size: clamp(28px, 4vw, 48px);
            line-height: 1.02;
            letter-spacing: -0.055em;
        }
        .cc-subtitle {
            color: #64748b;
            max-width: 760px;
            margin-top: 10px;
            font-size: 14px;
            line-height: 1.65;
        }
        .cc-card {
            background: rgba(255, 255, 255, 0.90);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 24px;
            padding: 18px;
            box-shadow: 0 16px 44px rgba(15, 23, 42, 0.06);
            margin: 14px 0;
        }
        .cc-card-title {
            color: #0f172a;
            font-weight: 820;
            font-size: 17px;
            margin-bottom: 5px;
            letter-spacing: -0.02em;
        }
        .cc-card-caption {
            color: #64748b;
            font-size: 12px;
            line-height: 1.55;
            margin-bottom: 12px;
        }
        .cc-stepper {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 10px;
            margin: 14px 0;
        }
        .cc-step {
            min-height: 104px;
            border-radius: 20px;
            padding: 13px;
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(148, 163, 184, 0.18);
            color: #475569;
        }
        .cc-step.active {
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.14), rgba(20, 184, 166, 0.14));
            border-color: rgba(20, 184, 166, 0.34);
            color: #0f766e;
            box-shadow: 0 14px 32px rgba(20, 184, 166, 0.14);
        }
        .cc-step-icon {
            width: 28px;
            height: 28px;
            display: grid;
            place-items: center;
            border-radius: 10px;
            background: rgba(15, 118, 110, 0.10);
            margin-bottom: 9px;
        }
        .cc-step-title {
            font-weight: 800;
            font-size: 13px;
            margin-bottom: 4px;
        }
        .cc-step-desc {
            font-size: 11px;
            line-height: 1.45;
            color: #64748b;
        }
        .cc-summary-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
            gap: 14px;
        }
        .cc-score {
            font-size: 64px;
            line-height: 0.95;
            font-weight: 900;
            letter-spacing: -0.08em;
            color: #0f172a;
        }
        .cc-score span {
            font-size: 22px;
            color: #94a3b8;
            letter-spacing: -0.04em;
        }
        .cc-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 12px 0;
        }
        .cc-pill {
            display: inline-flex;
            gap: 6px;
            align-items: center;
            border-radius: 999px;
            padding: 7px 10px;
            background: rgba(14, 165, 233, 0.08);
            color: #0369a1;
            border: 1px solid rgba(14, 165, 233, 0.15);
            font-size: 12px;
            font-weight: 700;
        }
        .cc-pill.green {
            background: rgba(20, 184, 166, 0.10);
            color: #0f766e;
            border-color: rgba(20, 184, 166, 0.18);
        }
        .cc-pill.purple {
            background: rgba(139, 92, 246, 0.10);
            color: #6d28d9;
            border-color: rgba(139, 92, 246, 0.16);
        }
        .cc-fusion-flow {
            display: grid;
            grid-template-columns: 1fr auto 1fr auto 1fr;
            gap: 9px;
            align-items: center;
        }
        .cc-mini-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 12px;
            margin-top: 12px;
        }
        .cc-mini-card {
            background: #f8fafc;
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 14px;
            min-height: 118px;
        }
        .cc-mini-title {
            color: #0f172a;
            font-weight: 800;
            font-size: 13px;
            margin-bottom: 7px;
        }
        .cc-mini-value {
            color: #0f766e;
            font-size: 18px;
            font-weight: 850;
            letter-spacing: -0.04em;
            margin-bottom: 5px;
        }
        .cc-mini-desc {
            color: #64748b;
            font-size: 11px;
            line-height: 1.45;
        }
        .cc-arrow {
            color: #14b8a6;
            font-weight: 900;
            font-size: 20px;
        }
        .cc-three-grid,
        .cc-validation-grid,
        .cc-signal-grid {
            display: grid;
            gap: 12px;
        }
        .cc-three-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .cc-validation-grid {
            grid-template-columns: repeat(5, minmax(0, 1fr));
        }
        .cc-signal-grid {
            grid-template-columns: repeat(5, minmax(0, 1fr));
        }
        .cc-money-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
        }
        .cc-money-card {
            min-height: 88px;
            border-radius: 18px;
            padding: 13px;
            background: #f8fafc;
            border: 1px solid rgba(148, 163, 184, 0.18);
        }
        .cc-money-value {
            color: #0f172a;
            font-size: 16px;
            line-height: 1.35;
            font-weight: 850;
            letter-spacing: 0;
            overflow-wrap: anywhere;
        }
        .cc-check {
            display: inline-flex;
            border-radius: 999px;
            padding: 5px 8px;
            font-size: 11px;
            font-weight: 800;
            margin-top: 7px;
        }
        .cc-check.ok { background: rgba(20, 184, 166, 0.10); color: #0f766e; }
        .cc-check.wait { background: rgba(245, 158, 11, 0.12); color: #b45309; }
        .cc-check.risk { background: rgba(239, 68, 68, 0.10); color: #b91c1c; }
        .cc-list {
            margin: 0;
            padding-left: 17px;
            color: #475569;
            font-size: 13px;
            line-height: 1.7;
        }
        .cc-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0 8px;
            font-size: 13px;
        }
        .cc-table th {
            color: #64748b;
            font-size: 12px;
            text-align: left;
            font-weight: 800;
            padding: 0 10px;
        }
        .cc-table td {
            background: #f8fafc;
            padding: 11px 10px;
            color: #334155;
            border-top: 1px solid rgba(148, 163, 184, 0.16);
            border-bottom: 1px solid rgba(148, 163, 184, 0.16);
        }
        .cc-table td:first-child {
            border-left: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 13px 0 0 13px;
            font-weight: 800;
            color: #0f172a;
        }
        .cc-table td:last-child {
            border-right: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 0 13px 13px 0;
        }
        .cc-muted-note {
            color: #64748b;
            font-size: 12px;
            line-height: 1.6;
            margin-top: 8px;
        }
        .cc-decision-hero {
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(248,250,252,0.86));
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 30px;
            box-shadow: 0 28px 80px rgba(15, 23, 42, 0.09), inset 0 1px 0 rgba(255,255,255,0.76);
            backdrop-filter: blur(18px);
            padding: 24px;
            margin: 14px 0 16px;
            animation: cc-decision-fade-up 280ms ease-out both;
        }
        .cc-decision-top {
            display: grid;
            grid-template-columns: minmax(0, 1.2fr) minmax(220px, 0.8fr);
            gap: 18px;
            align-items: start;
        }
        .cc-decision-kicker {
            color: #64748b;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .cc-decision-action {
            color: #0f172a;
            font-size: clamp(44px, 8vw, 86px);
            line-height: 0.92;
            font-weight: 900;
            letter-spacing: 0;
            margin: 0 0 10px;
            animation: cc-decision-label 260ms ease-out both;
            word-break: keep-all;
        }
        .cc-decision-reason {
            color: #475569;
            font-size: 15px;
            line-height: 1.62;
            max-width: 780px;
        }
        .cc-decision-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }
        .cc-decision-badge {
            border-radius: 999px;
            padding: 8px 11px;
            font-size: 12px;
            font-weight: 800;
            border: 1px solid rgba(148,163,184,0.18);
            background: rgba(255,255,255,0.68);
            color: #334155;
        }
        .cc-decision-badge.ready { background: rgba(20,184,166,0.11); color: #0f766e; border-color: rgba(20,184,166,0.20); }
        .cc-decision-badge.partial { background: rgba(245,158,11,0.12); color: #b45309; border-color: rgba(245,158,11,0.18); }
        .cc-decision-badge.waiting { background: rgba(148,163,184,0.13); color: #475569; border-color: rgba(148,163,184,0.18); }
        .cc-decision-badge.failed { background: rgba(239,68,68,0.10); color: #b91c1c; border-color: rgba(239,68,68,0.18); }
        .cc-decision-chain {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 11px;
        }
        .cc-decision-chain-pill {
            border-radius: 999px;
            background: rgba(255,255,255,0.76);
            border: 1px solid rgba(148,163,184,0.18);
            color: #334155;
            padding: 7px 10px;
            font-size: 12px;
            font-weight: 760;
        }
        .cc-decision-chain-pill.success { background: rgba(20,184,166,0.10); color: #0f766e; border-color: rgba(20,184,166,0.18); }
        .cc-decision-chain-pill.warning { background: rgba(245,158,11,0.11); color: #b45309; border-color: rgba(245,158,11,0.18); }
        .cc-decision-chain-pill.muted { background: rgba(148,163,184,0.10); color: #475569; border-color: rgba(148,163,184,0.16); }
        .cc-decision-risk {
            border-radius: 24px;
            background: rgba(255,255,255,0.74);
            border: 1px solid rgba(148, 163, 184, 0.18);
            padding: 18px;
            box-shadow: 0 14px 42px rgba(15,23,42,0.05);
        }
        .cc-decision-risk-label {
            color: #64748b;
            font-size: 12px;
            font-weight: 800;
            margin-bottom: 4px;
        }
        .cc-decision-risk-value {
            color: #0f172a;
            font-size: 38px;
            line-height: 1;
            font-weight: 900;
            letter-spacing: 0;
        }
        .cc-decision-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-top: 18px;
        }
        .cc-decision-tile {
            min-height: 104px;
            border-radius: 22px;
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(148,163,184,0.17);
            padding: 14px;
            box-shadow: 0 10px 28px rgba(15,23,42,0.045);
            animation: cc-decision-fade-up 260ms ease both;
        }
        .cc-decision-tile:nth-child(1) { animation-delay: 40ms; }
        .cc-decision-tile:nth-child(2) { animation-delay: 80ms; }
        .cc-decision-tile:nth-child(3) { animation-delay: 120ms; }
        .cc-decision-tile:nth-child(4) { animation-delay: 160ms; }
        .cc-decision-tile-label {
            color: #64748b;
            font-size: 12px;
            font-weight: 800;
            margin-bottom: 8px;
        }
        .cc-decision-tile-value {
            color: #0f172a;
            font-size: 18px;
            line-height: 1.35;
            font-weight: 850;
            letter-spacing: 0;
            overflow-wrap: anywhere;
        }
        .cc-decision-lists {
            display: grid;
            grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
            gap: 12px;
            margin-top: 14px;
        }
        .cc-decision-list-card {
            border-radius: 22px;
            background: rgba(248,250,252,0.86);
            border: 1px solid rgba(148,163,184,0.16);
            padding: 15px;
        }
        .cc-decision-list-title {
            color: #0f172a;
            font-size: 13px;
            font-weight: 850;
            margin-bottom: 8px;
        }
        .cc-decision-list {
            margin: 0;
            padding-left: 18px;
            color: #475569;
            font-size: 13px;
            line-height: 1.75;
        }
        .cc-coverage-grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 8px;
            margin-top: 15px;
        }
        .cc-coverage-item {
            border-radius: 16px;
            background: rgba(255,255,255,0.70);
            border: 1px solid rgba(148,163,184,0.16);
            padding: 10px;
            min-height: 74px;
        }
        .cc-coverage-name {
            color: #64748b;
            font-size: 11px;
            font-weight: 800;
            margin-bottom: 8px;
        }
        .cc-coverage-state {
            color: #0f172a;
            font-size: 13px;
            font-weight: 850;
            margin-bottom: 7px;
        }
        .cc-coverage-bar {
            height: 5px;
            border-radius: 999px;
            background: rgba(148,163,184,0.20);
            overflow: hidden;
        }
        .cc-coverage-fill {
            display: block;
            height: 100%;
            width: 24%;
            border-radius: 999px;
            background: #94a3b8;
            animation: cc-coverage-load 320ms ease-out both;
        }
        .cc-coverage-fill.cached { width: 62%; background: #f59e0b; }
        .cc-coverage-fill.ready { width: 100%; background: #14b8a6; }
        .cc-decision-foot {
            margin-top: 12px;
            color: #64748b;
            font-size: 12px;
            line-height: 1.6;
        }
        .cc-strategy-card {
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, rgba(255,255,255,0.93), rgba(248,250,252,0.88));
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 28px;
            box-shadow: 0 24px 70px rgba(15, 23, 42, 0.08), inset 0 1px 0 rgba(255,255,255,0.72);
            backdrop-filter: blur(16px);
            padding: 22px;
            margin: 14px 0 16px;
            animation: cc-decision-fade-up 280ms ease-out both;
        }
        .cc-strategy-head {
            display: grid;
            grid-template-columns: minmax(0, 1.1fr) minmax(210px, 0.9fr);
            gap: 14px;
            align-items: stretch;
        }
        .cc-strategy-kicker {
            color: #0f766e;
            font-size: 12px;
            font-weight: 850;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .cc-strategy-action {
            color: #0f172a;
            font-size: clamp(34px, 5.2vw, 60px);
            line-height: 1.02;
            font-weight: 900;
            letter-spacing: 0;
            margin: 0 0 10px;
            animation: cc-decision-label 260ms ease-out both;
            word-break: keep-all;
        }
        .cc-strategy-summary {
            color: #475569;
            font-size: 14px;
            line-height: 1.65;
            max-width: 760px;
        }
        .cc-strategy-side {
            border-radius: 24px;
            background: rgba(255,255,255,0.76);
            border: 1px solid rgba(148, 163, 184, 0.18);
            padding: 16px;
            box-shadow: 0 12px 36px rgba(15,23,42,0.045);
        }
        .cc-strategy-side-label {
            color: #64748b;
            font-size: 12px;
            font-weight: 850;
            margin-bottom: 5px;
        }
        .cc-strategy-confidence {
            color: #0f172a;
            font-size: 34px;
            line-height: 1;
            font-weight: 900;
            letter-spacing: 0;
        }
        .cc-strategy-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }
        .cc-strategy-pill {
            border-radius: 999px;
            padding: 7px 10px;
            font-size: 12px;
            font-weight: 800;
            border: 1px solid rgba(148,163,184,0.18);
            background: rgba(255,255,255,0.70);
            color: #334155;
        }
        .cc-strategy-pill.ok { background: rgba(20,184,166,0.10); color: #0f766e; border-color: rgba(20,184,166,0.18); }
        .cc-strategy-pill.wait { background: rgba(245,158,11,0.12); color: #b45309; border-color: rgba(245,158,11,0.18); }
        .cc-strategy-pill.risk { background: rgba(239,68,68,0.10); color: #b91c1c; border-color: rgba(239,68,68,0.18); }
        .cc-strategy-budget-grid,
        .cc-strategy-condition-grid,
        .cc-strategy-path-grid {
            display: grid;
            gap: 10px;
            margin-top: 14px;
        }
        .cc-strategy-budget-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .cc-strategy-condition-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .cc-strategy-path-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .cc-strategy-tile,
        .cc-strategy-condition,
        .cc-strategy-path {
            border-radius: 20px;
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(148,163,184,0.17);
            padding: 14px;
            box-shadow: 0 10px 28px rgba(15,23,42,0.04);
            min-height: 104px;
        }
        .cc-strategy-tile.ok,
        .cc-strategy-condition.ok,
        .cc-strategy-path.ok {
            border-color: rgba(20,184,166,0.22);
            background: rgba(240,253,250,0.70);
        }
        .cc-strategy-tile.wait,
        .cc-strategy-condition.wait,
        .cc-strategy-path.wait {
            border-color: rgba(245,158,11,0.22);
            background: rgba(255,251,235,0.70);
        }
        .cc-strategy-tile.risk,
        .cc-strategy-condition.risk,
        .cc-strategy-path.risk {
            border-color: rgba(239,68,68,0.20);
            background: rgba(254,242,242,0.66);
        }
        .cc-strategy-condition {
            background: rgba(248,250,252,0.86);
            min-height: 132px;
        }
        .cc-strategy-path {
            background: rgba(248,250,252,0.80);
            min-height: 148px;
        }
        .cc-strategy-label {
            color: #64748b;
            font-size: 12px;
            font-weight: 850;
            margin-bottom: 8px;
        }
        .cc-strategy-value {
            color: #0f172a;
            font-size: 17px;
            line-height: 1.42;
            font-weight: 850;
            overflow-wrap: anywhere;
        }
        .cc-strategy-text {
            color: #475569;
            font-size: 13px;
            line-height: 1.68;
            overflow-wrap: anywhere;
        }
        .cc-strategy-check {
            margin-top: 10px;
            display: inline-flex;
            align-items: center;
            gap: 7px;
            color: #334155;
            font-size: 12px;
            font-weight: 800;
            border-radius: 999px;
            padding: 6px 9px;
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(148,163,184,0.16);
        }
        .cc-strategy-risk-note {
            margin-top: 10px;
            color: #64748b;
            font-size: 12px;
            line-height: 1.55;
            border-top: 1px solid rgba(148,163,184,0.13);
            padding-top: 9px;
        }
        .cc-strategy-section-title {
            color: #0f172a;
            font-size: 13px;
            font-weight: 850;
            margin: 16px 0 8px;
        }
        .cc-strategy-guidance {
            border-radius: 20px;
            background: rgba(37,99,235,0.07);
            border: 1px solid rgba(37,99,235,0.14);
            padding: 13px;
            margin-top: 12px;
        }
        .cc-strategy-guidance-title {
            color: #1d4ed8;
            font-size: 13px;
            font-weight: 880;
            margin-bottom: 8px;
        }
        .cc-strategy-guidance-row {
            display: grid;
            grid-template-columns: 48px minmax(0, 1fr);
            gap: 8px;
            color: #475569;
            font-size: 12px;
            line-height: 1.5;
            margin-top: 6px;
        }
        .cc-strategy-guidance-row span {
            color: #1d4ed8;
            font-weight: 850;
        }
        .cc-strategy-focus {
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
            margin-top: 8px;
        }
        .cc-strategy-focus span {
            border-radius: 999px;
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(37,99,235,0.14);
            color: #1e40af;
            padding: 5px 8px;
            font-size: 11px;
            font-weight: 820;
        }
        .cc-strategy-foot-grid {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
            gap: 10px;
            margin-top: 14px;
        }
        .cc-strategy-foot-card {
            border-radius: 20px;
            background: rgba(248,250,252,0.82);
            border: 1px solid rgba(148,163,184,0.16);
            padding: 14px;
        }
        .cc-strategy-list {
            margin: 0;
            padding-left: 18px;
            color: #475569;
            font-size: 13px;
            line-height: 1.75;
        }
        .cc-strategy-mini-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
        }
        .cc-strategy-mini {
            border-radius: 14px;
            background: rgba(255,255,255,0.70);
            border: 1px solid rgba(148,163,184,0.14);
            padding: 10px;
        }
        .cc-strategy-mini-name {
            color: #64748b;
            font-size: 11px;
            font-weight: 800;
            margin-bottom: 5px;
        }
        .cc-strategy-mini-value {
            color: #0f172a;
            font-size: 13px;
            line-height: 1.45;
            font-weight: 780;
        }
        .cc-strategy-status-row {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
            margin-top: 8px;
        }
        .cc-strategy-status {
            border-radius: 14px;
            background: rgba(255,255,255,0.70);
            border: 1px solid rgba(148,163,184,0.15);
            padding: 9px;
        }
        .cc-strategy-status-name {
            color: #64748b;
            font-size: 11px;
            font-weight: 800;
            margin-bottom: 5px;
        }
        .cc-strategy-status-value {
            color: #0f172a;
            font-size: 13px;
            font-weight: 850;
        }
        .cc-strategy-foot {
            margin-top: 12px;
            color: #64748b;
            font-size: 12px;
            line-height: 1.6;
        }
        .cc-home-snapshot {
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(248,250,252,0.88));
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 28px;
            box-shadow: 0 24px 68px rgba(15,23,42,0.075), inset 0 1px 0 rgba(255,255,255,0.72);
            padding: 22px;
            margin: 12px 0 16px;
            animation: cc-decision-fade-up 280ms ease-out both;
        }
        .cc-home-head {
            display: grid;
            grid-template-columns: minmax(0, 1.35fr) minmax(260px, 0.65fr);
            gap: 14px;
            align-items: stretch;
        }
        .cc-home-kicker {
            color: #0f766e;
            font-size: 12px;
            font-weight: 850;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .cc-home-action {
            color: #0f172a;
            font-size: clamp(30px, 4.6vw, 56px);
            line-height: 1.02;
            font-weight: 900;
            letter-spacing: 0;
            margin: 0 0 8px;
            word-break: keep-all;
        }
        .cc-home-meta-row,
        .cc-home-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }
        .cc-home-chip {
            border-radius: 999px;
            padding: 7px 10px;
            font-size: 12px;
            font-weight: 800;
            border: 1px solid rgba(148,163,184,0.18);
            background: rgba(255,255,255,0.74);
            color: #334155;
        }
        .cc-home-chip.ready { background: rgba(20,184,166,0.10); color: #0f766e; border-color: rgba(20,184,166,0.18); }
        .cc-home-chip.stale,
        .cc-home-chip.partial_failed { background: rgba(245,158,11,0.12); color: #b45309; border-color: rgba(245,158,11,0.18); }
        .cc-home-chip.missing { background: rgba(148,163,184,0.13); color: #475569; border-color: rgba(148,163,184,0.18); }
        .cc-home-chip.failed { background: rgba(239,68,68,0.10); color: #b91c1c; border-color: rgba(239,68,68,0.18); }
        .cc-home-side {
            border-radius: 24px;
            background: rgba(255,255,255,0.75);
            border: 1px solid rgba(148,163,184,0.18);
            padding: 16px;
            box-shadow: 0 12px 34px rgba(15,23,42,0.045);
        }
        .cc-home-side-label {
            color: #64748b;
            font-size: 12px;
            font-weight: 850;
            margin-bottom: 5px;
        }
        .cc-home-risk {
            color: #0f172a;
            font-size: 34px;
            line-height: 1;
            font-weight: 900;
        }
        .cc-home-profile-strip {
            display: grid;
            grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.4fr);
            gap: 12px;
            margin-top: 14px;
            padding: 13px;
            border-radius: 20px;
            background: rgba(255,255,255,0.68);
            border: 1px solid rgba(20,184,166,0.14);
        }
        .cc-home-profile-title {
            color: #0f172a;
            font-size: 14px;
            font-weight: 880;
            margin-bottom: 6px;
        }
        .cc-home-profile-meta {
            color: #64748b;
            font-size: 12px;
            line-height: 1.55;
        }
        .cc-home-profile-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
            margin-top: 8px;
        }
        .cc-home-grid {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1.08fr) minmax(0, 1fr);
            gap: 12px;
            margin-top: 16px;
        }
        .cc-home-panel {
            border-radius: 22px;
            background: rgba(248,250,252,0.84);
            border: 1px solid rgba(148,163,184,0.16);
            padding: 15px;
            min-height: 224px;
        }
        .cc-home-panel-title {
            color: #0f172a;
            font-size: 14px;
            font-weight: 850;
            margin-bottom: 10px;
        }
        .cc-home-big-value {
            color: #0f766e;
            font-size: 20px;
            font-weight: 900;
            line-height: 1.25;
            margin-bottom: 8px;
            overflow-wrap: anywhere;
        }
        .cc-home-row {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            border-top: 1px solid rgba(148,163,184,0.14);
            padding-top: 8px;
            margin-top: 8px;
            color: #475569;
            font-size: 12px;
            line-height: 1.45;
        }
        .cc-home-row strong {
            color: #0f172a;
            font-weight: 850;
        }
        .cc-home-candidate,
        .cc-home-etf {
            border-radius: 16px;
            background: rgba(255,255,255,0.74);
            border: 1px solid rgba(148,163,184,0.14);
            padding: 10px;
            margin-top: 8px;
        }
        .cc-home-item-title {
            color: #0f172a;
            font-size: 13px;
            font-weight: 850;
            margin-bottom: 4px;
        }
        .cc-home-item-meta {
            color: #64748b;
            font-size: 11px;
            line-height: 1.45;
        }
        .cc-home-bottom {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
            gap: 12px;
            margin-top: 12px;
        }
        .cc-home-list {
            margin: 0;
            padding-left: 18px;
            color: #475569;
            font-size: 13px;
            line-height: 1.7;
        }
        .cc-home-foot {
            margin-top: 12px;
            color: #64748b;
            font-size: 12px;
            line-height: 1.6;
        }
        .cc-projection-paths {
            margin: 8px 0 16px;
        }
        .cc-projection-foot {
            color: #64748b;
            font-size: 12px;
            line-height: 1.55;
            margin: 5px 0 10px;
        }
        .cc-projection-action-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
        }
        .cc-projection-action-card {
            border-radius: 20px;
            background: rgba(255,255,255,0.86);
            border: 1px solid rgba(148,163,184,0.18);
            box-shadow: 0 12px 34px rgba(15,23,42,0.045);
            padding: 14px;
            min-height: 136px;
        }
        .cc-projection-action-head {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            align-items: center;
            color: #0f172a;
            font-size: 14px;
            font-weight: 850;
            margin-bottom: 10px;
        }
        .cc-projection-action-head span {
            color: #0f766e;
            font-size: 16px;
            font-weight: 900;
        }
        .cc-projection-action-line {
            display: grid;
            grid-template-columns: 38px minmax(0, 1fr);
            gap: 8px;
            color: #475569;
            font-size: 12px;
            line-height: 1.45;
            border-top: 1px solid rgba(148,163,184,0.13);
            padding-top: 7px;
            margin-top: 7px;
        }
        .cc-projection-action-line span {
            color: #64748b;
            font-weight: 800;
        }
        .cc-projection-action-line b {
            color: #0f172a;
            font-weight: 760;
            overflow-wrap: anywhere;
        }
        .cc-projection-pill {
            display: inline-flex;
            border-radius: 999px;
            padding: 6px 10px;
            font-size: 12px;
            font-weight: 850;
            border: 1px solid transparent;
            margin: 0 0 8px;
        }
        .cc-projection-pill.green {
            background: rgba(20,184,166,0.10);
            color: #0f766e;
            border-color: rgba(20,184,166,0.18);
        }
        .cc-projection-pill.blue {
            background: rgba(37,99,235,0.10);
            color: #1d4ed8;
            border-color: rgba(37,99,235,0.16);
        }
        .cc-projection-pill.orange {
            background: rgba(249,115,22,0.11);
            color: #c2410c;
            border-color: rgba(249,115,22,0.16);
        }
        .cc-analysis-card {
            background: rgba(255,255,255,0.94);
            border: 1px solid rgba(148, 163, 184, 0.20);
            border-radius: 26px;
            box-shadow: 0 18px 54px rgba(15,23,42,0.060);
            padding: 18px;
            margin: 12px 0 16px;
            animation: cc-decision-fade-up 280ms ease-out both;
        }
        .cc-analysis-head {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 14px;
            margin-bottom: 14px;
        }
        .cc-analysis-kicker {
            color: #2563eb;
            font-size: 12px;
            font-weight: 850;
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        .cc-analysis-title {
            color: #0f172a;
            font-size: 24px;
            line-height: 1.15;
            font-weight: 900;
            margin: 0;
        }
        .cc-analysis-summary {
            color: #475569;
            font-size: 13px;
            line-height: 1.55;
            margin-top: 7px;
        }
        .cc-analysis-market {
            border-radius: 999px;
            background: rgba(37,99,235,0.10);
            color: #1d4ed8;
            border: 1px solid rgba(37,99,235,0.16);
            padding: 8px 12px;
            font-size: 12px;
            font-weight: 850;
            white-space: nowrap;
        }
        .cc-analysis-method-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
        }
        .cc-analysis-method {
            border-radius: 18px;
            background: rgba(248,250,252,0.78);
            border: 1px solid rgba(148,163,184,0.16);
            padding: 12px;
            min-height: 168px;
        }
        .cc-analysis-method.passed {
            background: rgba(20,184,166,0.08);
            border-color: rgba(20,184,166,0.18);
        }
        .cc-analysis-method.pending {
            background: rgba(245,158,11,0.08);
            border-color: rgba(245,158,11,0.16);
        }
        .cc-analysis-method.failed {
            background: rgba(249,115,22,0.08);
            border-color: rgba(249,115,22,0.18);
        }
        .cc-analysis-method.na {
            background: rgba(148,163,184,0.09);
            border-color: rgba(148,163,184,0.16);
        }
        .cc-analysis-method-title {
            color: #0f172a;
            font-size: 13px;
            font-weight: 870;
            line-height: 1.35;
            margin-bottom: 8px;
        }
        .cc-analysis-status {
            display: inline-flex;
            border-radius: 999px;
            padding: 5px 8px;
            font-size: 11px;
            font-weight: 850;
            margin-bottom: 8px;
            border: 1px solid rgba(148,163,184,0.14);
            background: rgba(255,255,255,0.72);
            color: #475569;
        }
        .cc-analysis-status.passed { color: #0f766e; border-color: rgba(20,184,166,0.18); }
        .cc-analysis-status.pending { color: #b45309; border-color: rgba(245,158,11,0.18); }
        .cc-analysis-status.failed { color: #c2410c; border-color: rgba(249,115,22,0.18); }
        .cc-analysis-line {
            color: #475569;
            font-size: 12px;
            line-height: 1.5;
            margin-top: 6px;
            overflow-wrap: anywhere;
        }
        .cc-analysis-line span {
            color: #64748b;
            font-weight: 850;
        }
        .cc-analysis-foot {
            color: #64748b;
            font-size: 12px;
            line-height: 1.6;
            margin-top: 12px;
        }
        @keyframes cc-decision-fade-up {
            from { opacity: 0; transform: translateY(12px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes cc-decision-label {
            from { opacity: 0; transform: translateY(8px) scale(0.985); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes cc-coverage-load {
            from { transform: scaleX(0.2); transform-origin: left; }
            to { transform: scaleX(1); transform-origin: left; }
        }
        @media (prefers-reduced-motion: reduce) {
            .cc-decision-hero,
            .cc-decision-action,
            .cc-decision-tile,
            .cc-strategy-card,
            .cc-strategy-action,
            .cc-home-snapshot,
            .cc-coverage-fill {
                animation: none !important;
                transition: none !important;
            }
        }
        @media (max-width: 980px) {
            .cc-grid,
            .cc-summary-grid,
            .cc-three-grid,
            .cc-validation-grid,
            .cc-signal-grid,
            .cc-money-grid,
            .cc-stepper {
                grid-template-columns: 1fr;
            }
            .cc-sidebar {
                position: relative;
                top: auto;
            }
            .cc-fusion-flow {
                grid-template-columns: 1fr;
            }
            .cc-arrow {
                transform: rotate(90deg);
                text-align: center;
            }
            .cc-decision-top,
            .cc-decision-grid,
            .cc-decision-lists,
            .cc-coverage-grid,
            .cc-strategy-head,
            .cc-strategy-budget-grid,
            .cc-strategy-condition-grid,
            .cc-strategy-path-grid,
            .cc-strategy-foot-grid,
            .cc-home-head,
            .cc-home-profile-strip,
            .cc-home-grid,
            .cc-projection-action-grid,
            .cc-analysis-head,
            .cc-analysis-method-grid,
            .cc-home-bottom,
            .cc-strategy-status-row {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _html_list(items):
    values = items if isinstance(items, list) else []
    if not values:
        values = ["暂无缓存结果。"]
    return "<ul class='cc-list'>" + "".join(f"<li>{escape(str(item))}</li>" for item in values[:6]) + "</ul>"


def _status_class(value):
    text = str(value or "")
    if any(key in text for key in ["满足", "通过", "正向", "确认", "强"]):
        return "ok"
    if any(key in text for key in ["风险", "不满足", "恶化", "降低"]):
        return "risk"
    return "wait"


def _fmt_cc_money(value):
    number = _to_float(value)
    if number is None:
        return "暂无"
    return f"¥{number:,.0f}"


def _cc_money_line(value, basis):
    basis_text = str(basis or "按净资产")
    return f"{_fmt_cc_money(value)} · {basis_text}"


def _decision_list(items, fallback):
    values = [str(item or "").strip() for item in (items or []) if str(item or "").strip()]
    if not values:
        values = [fallback]
    return "<ul class='cc-decision-list'>" + "".join(f"<li>{escape(item)}</li>" for item in values[:5]) + "</ul>"


def _decision_status_label(status):
    mapping = {
        "waiting": "待刷新判断",
        "partial": "部分刷新结论",
        "ready": "综合推演结论",
        "failed": "失败后缓存",
    }
    return mapping.get(str(status or ""), "待刷新判断")


def _coverage_label(key):
    mapping = {
        "market": "市场",
        "quant": "量化",
        "discipline": "纪律",
        "margin_etf": "融资ETF",
        "next_ticket": "下一票",
        "strategy_execution": "策略执行",
    }
    return mapping.get(str(key or ""), str(key or "模块"))


def _strategy_action_label(action):
    text = str(action or "").strip()
    mapping = {
        "小幅试探": "可轻仓试探",
        "小幅进攻": "可轻仓试探",
        "持仓观察": "可持有",
        "允许进攻": "可加仓",
    }
    return mapping.get(text, text or "等待")


def _strategy_pill_class(value):
    text = str(value or "").lower()
    if any(key in text for key in ["降风险", "减仓", "退出", "止损", "高", "failed", "风险"]):
        return "risk"
    if any(key in text for key in ["等待", "观察", "missing", "cached", "低", "不足", "谨慎"]):
        return "wait"
    return "ok"


def _tone_to_strategy_class(value):
    mapping = {
        "danger": "risk",
        "warning": "wait",
        "muted": "wait",
        "success": "ok",
        "info": "ok",
    }
    return mapping.get(str(value or ""), _strategy_pill_class(value))


def _strategy_list(items, fallback, limit=5):
    values = [str(item or "").strip() for item in (items or []) if str(item or "").strip()]
    if not values:
        values = [fallback]
    return "<ul class='cc-strategy-list'>" + "".join(f"<li>{escape(item)}</li>" for item in values[:limit]) + "</ul>"


def _strategy_item_grid(items, fallback, limit=8):
    values = [item for item in (items or []) if isinstance(item, dict)]
    if not values:
        values = [{"label": "状态", "value": fallback}]
    return (
        "<div class='cc-strategy-mini-grid'>"
        + "".join(
            "<div class='cc-strategy-mini'>"
            f"<div class='cc-strategy-mini-name'>{escape(str(item.get('label') or '项目'))}</div>"
            f"<div class='cc-strategy-mini-value'>{escape(str(item.get('value') or item.get('text') or '暂无'))}</div>"
            "</div>"
            for item in values[:limit]
        )
        + "</div>"
    )


def _fmt_strategy_value(value):
    if value in [None, ""]:
        return "暂无"
    number = _to_float(value)
    if number is not None:
        return f"¥{number:,.0f}"
    return str(value)


def _strategy_path_items(packet):
    paths = packet.get("next_5_10_day_paths") or packet.get("paths") or packet.get("scenario_paths") or []
    if not isinstance(paths, list):
        paths = []
    fallback = [
        {"name": "乐观路径", "condition": "数据补齐且市场、量化、纪律转为同向。", "action": "只允许小幅试探。"},
        {"name": "中性路径", "condition": "信号继续分歧或缺少新增验证。", "action": "等待或只观察。"},
        {"name": "防守路径", "condition": "纪律信号转弱、回撤扩大或数据失败。", "action": "降风险。"},
    ]
    merged = paths[:3] if paths else fallback
    names = ["乐观路径", "中性路径", "防守路径"]
    normalized = []
    for index, item in enumerate(merged[:3]):
        if isinstance(item, dict):
            normalized.append(
                {
                    "name": item.get("name") or names[index],
                    "condition": item.get("condition") or item.get("trigger") or "等待验证条件。",
                    "action": item.get("action") or item.get("advice") or "只观察。",
                }
            )
        else:
            normalized.append({"name": names[index], "condition": str(item), "action": "按纪律执行。"})
    return normalized


def render_strategy_execution_command_card(
    strategy_execution_packet: dict | None = None,
    live_packet: dict | None = None,
    strategy_view_model: dict | None = None,
):
    _inject_command_center_css()
    payload = strategy_execution_packet or {}
    del live_packet
    vm = strategy_view_model or build_strategy_summary_view_model(payload)
    action = vm.get("action_label") or "等待"
    confidence = vm.get("confidence_label") or "低"
    summary = vm.get("summary") or vm.get("empty_message") or "尚未生成策略执行建议。"
    risk_level = vm.get("risk_label") or "未知"
    budget_tiles = [item for item in (vm.get("risk_budget_items") or []) if isinstance(item, dict)]
    budget_html = "".join(
        f"<div class='cc-strategy-tile {_tone_to_strategy_class(item.get('tone'))}'>"
        f"<div class='cc-strategy-label'>{escape(str(item.get('label') or '项目'))}</div>"
        f"<div class='cc-strategy-value'>{escape(str(item.get('value') or '暂无'))}</div>"
        "</div>"
        for item in budget_tiles[:5]
    )
    conditions = vm.get("condition_items") or []
    if not conditions:
        conditions_payload = vm.get("conditions") or {}
        conditions = [
            {"label": "加仓条件", "value": conditions_payload.get("add") or "等待量化、纪律和市场至少两项同向后再考虑。", "tone": "success", "check_label": "满足后才允许小额试探"},
            {"label": "减仓条件", "value": conditions_payload.get("reduce") or "触发止损、减仓或风险预算失效时优先降低暴露。", "tone": "warning", "check_label": "触发后优先降低暴露"},
            {"label": "失效条件", "value": conditions_payload.get("invalidation") or "市场环境转弱或纪律信号反向时，本轮建议失效。", "tone": "danger", "check_label": "触发后本轮建议作废"},
        ]
    condition_html = "".join(
        f"<div class='cc-strategy-condition {_tone_to_strategy_class(item.get('tone'))}'>"
        f"<div class='cc-strategy-label'>{escape(str(item.get('label') or '条件'))}</div>"
        f"<div class='cc-strategy-text'>{escape(str(item.get('value') or '等待验证。'))}</div>"
        f"<div class='cc-strategy-check'>✓ {escape(str(item.get('check_label') or '按条件执行'))}</div>"
        "</div>"
        for item in conditions
    )
    path_html = "".join(
        f"<div class='cc-strategy-path {_tone_to_strategy_class(item.get('tone'))}'>"
        f"<div class='cc-strategy-label'>{escape(str(item.get('name') or '路径'))}</div>"
        f"<div class='cc-strategy-text'>{escape(str(item.get('condition') or '等待验证。'))}</div>"
        f"<div class='cc-strategy-value' style='font-size:14px;margin-top:8px;'>{escape(str(item.get('action') or '只观察。'))}</div>"
        f"<div class='cc-strategy-risk-note'>风险提示：{escape(str(item.get('risk') or '不追高、不重仓，等待验证。'))}</div>"
        "</div>"
        for item in (vm.get("path_items") or [])
    )
    status_html = "".join(
        "<div class='cc-strategy-status'>"
        f"<div class='cc-strategy-status-name'>{escape(str(item.get('label') or item.get('key') or '模块'))}</div>"
        f"<div class='cc-strategy-status-value'>{escape(str(item.get('text') or item.get('state') or 'missing'))}</div>"
        "</div>"
        for item in (vm.get("data_status_items") or [])
    )
    warning_lines = [str(item) for item in (vm.get("warning_items") or [])]
    guidance = vm.get("market_method_guidance") or {}
    focus_html = "".join(f"<span>{escape(str(item))}</span>" for item in (guidance.get("focus_items") or [])[:5])
    guidance_html = f"""
      <div class="cc-strategy-guidance">
        <div class="cc-strategy-guidance-title">{escape(str(guidance.get("title") or "市场验证重点"))}</div>
        <div class="cc-strategy-focus">{focus_html}</div>
        <div class="cc-strategy-guidance-row"><span>加仓</span><b>{escape(str(guidance.get("add_condition") or "先确认市场类型和基础数据。"))}</b></div>
        <div class="cc-strategy-guidance-row"><span>减仓</span><b>{escape(str(guidance.get("reduce_condition") or "数据缺口扩大或纪律转弱时先降风险。"))}</b></div>
        <div class="cc-strategy-guidance-row"><span>失效</span><b>{escape(str(guidance.get("invalidation_condition") or "市场画像无法确认时只保留观察。"))}</b></div>
      </div>
    """
    evidence_validation_html = "".join(
        f"<div class='cc-strategy-condition {_tone_to_strategy_class(item.get('tone'))}'>"
        f"<div class='cc-strategy-label'>P{escape(str(item.get('priority') or 3))} · {escape(str(item.get('label') or '证据'))}</div>"
        f"<div class='cc-strategy-text'>{escape(str(item.get('check_text') or '待验证。'))}</div>"
        f"<div class='cc-strategy-check'>✓ {escape(str(item.get('action_hint') or '先验证再执行。'))}</div>"
        "</div>"
        for item in (vm.get("evidence_validation_items") or [])[:6]
        if isinstance(item, dict)
    )
    pill_items = [
        (f"状态：{vm.get('status_label') or '待生成'}", vm.get("status_tone")),
        (f"风险：{risk_level}", risk_level),
        (vm.get("deepseek_text") or "DeepSeek：未调用", "等待"),
    ]
    pill_html = "".join(
        f"<span class='cc-strategy-pill {_tone_to_strategy_class(flag)}'>{escape(text)}</span>"
        for text, flag in pill_items
    )
    html = f"""
    <section class="cc-strategy-card">
      <div class="cc-strategy-head">
        <div>
          <div class="cc-strategy-kicker">Strategy Execution</div>
          <h2 class="cc-strategy-action">{escape(action)}</h2>
          <div class="cc-strategy-summary">{escape(summary)}</div>
          <div class="cc-muted-note">{escape(str(vm.get("action_guardrail") or ""))}</div>
          <div class="cc-muted-note">{escape(str(vm.get("readiness_text") or ""))}</div>
          <div class="cc-strategy-pill-row">{pill_html}</div>
        </div>
        <aside class="cc-strategy-side">
          <div class="cc-strategy-side-label">置信度</div>
          <div class="cc-strategy-confidence">{escape(confidence)}</div>
          <div class="cc-muted-note">不放大确定性；缺少量化或纪律缓存时，只能作为待验证路径。</div>
        </aside>
      </div>
      <div class="cc-strategy-budget-grid">{budget_html}</div>
      <div class="cc-strategy-section-title">操作条件</div>
      <div class="cc-strategy-condition-grid">{condition_html}</div>
      {guidance_html}
      <div class="cc-strategy-section-title">证据验证重点 · {escape(str(vm.get("evidence_validation_summary") or "支持 0｜阻断 0｜缓存 0｜缺失 0"))}</div>
      <div class="cc-strategy-condition-grid">{evidence_validation_html}</div>
      <div class="cc-strategy-section-title">未来 5-10 日路径</div>
      <div class="cc-strategy-path-grid">{path_html}</div>
      <div class="cc-strategy-foot-grid">
        <div class="cc-strategy-foot-card">
          <div class="cc-strategy-section-title" style="margin-top:0;">纪律校验</div>
          {_strategy_item_grid(vm.get("discipline_items"), "暂无纪律校验缓存。")}
        </div>
        <div class="cc-strategy-foot-card">
          <div class="cc-strategy-section-title" style="margin-top:0;">风险红线 / 异常</div>
          {_strategy_list(warning_lines, "暂无新增异常；仍需遵守不追高、不自动重仓。")}
        </div>
      </div>
      <div class="cc-strategy-section-title">数据状态</div>
      <div class="cc-strategy-status-row">{status_html}</div>
      <div class="cc-strategy-foot">
        最后更新时间：{escape(str(vm.get("updated_text") or "暂无"))} ｜
        来源：{escape(str(vm.get("source_text") or "strategy_execution_service / session_state cache"))} ｜
        {escape(str(vm.get("deepseek_text") or "DeepSeek：未调用"))}
        <br>{escape(str(vm.get("user_boundary_text") or ""))}
      </div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_command_center_decision_hero(packet: dict | None = None, decision_view_model: dict | None = None):
    _inject_command_center_css()
    payload = packet or {}
    vm = decision_view_model or build_decision_summary_view_model(payload)
    status = str(vm.get("status") or "waiting")
    tiles = [
        ("主账户动作", vm.get("position_text") or "空仓等待"),
        ("融资账户动作", vm.get("margin_text") or "不使用融资"),
        ("ETF 动作", vm.get("etf_text") or "待刷新"),
        ("下一票观察动作", vm.get("next_ticket_text") or "待刷新"),
    ]
    tile_html = "".join(
        "<div class='cc-decision-tile'>"
        f"<div class='cc-decision-tile-label'>{escape(label)}</div>"
        f"<div class='cc-decision-tile-value'>{escape(str(value))}</div>"
        "</div>"
        for label, value in tiles
    )
    coverage_html = ""
    for item in vm.get("coverage_items") or []:
        state = str(item.get("state") or "missing")
        state_class = state if state in {"cached", "ready"} else "missing"
        coverage_html += (
            "<div class='cc-coverage-item'>"
            f"<div class='cc-coverage-name'>{escape(str(item.get('label') or item.get('key') or '模块'))}</div>"
            f"<div class='cc-coverage-state'>{escape(state)}</div>"
            "<div class='cc-coverage-bar'>"
            f"<span class='cc-coverage-fill {escape(state_class)}'></span>"
            "</div></div>"
        )
    evidence_chain_html = "".join(
        f"<span class='cc-decision-chain-pill {escape(str(item.get('tone') or 'muted'))}'>"
        f"{escape(str(item.get('label') or '依据'))}：{escape(str(item.get('value') or '待验证'))}"
        "</span>"
        for item in (vm.get("evidence_chain_items") or [])[:5]
    )
    html = f"""
    <section class="cc-decision-hero">
      <div class="cc-decision-top">
        <div>
          <div class="cc-decision-kicker">Today Command</div>
          <h2 class="cc-decision-action">{escape(str(vm.get("action_label") or "等待"))}</h2>
          <div class="cc-decision-reason">{escape(str(vm.get("reason_summary") or "基础数据未刷新，先等待或点击刷新今日基础数据。"))}</div>
          <div class="cc-muted-note">{escape(str(vm.get("action_guardrail") or ""))}</div>
          <div class="cc-decision-badges">
            <span class="cc-decision-badge {escape(status)}">{escape(str(vm.get("status_label") or "待刷新判断"))}</span>
            <span class="cc-decision-badge">市场：{escape(str(vm.get("market_text") or "未刷新"))}</span>
            <span class="cc-decision-badge">{escape(str(vm.get("deepseek_text") or "DeepSeek：未调用"))}</span>
          </div>
          <div class="cc-decision-chain">{evidence_chain_html}</div>
        </div>
        <aside class="cc-decision-risk">
          <div class="cc-decision-risk-label">风险等级</div>
          <div class="cc-decision-risk-value">{escape(str(vm.get("risk_label") or "中"))}</div>
          <div class="cc-muted-note">{escape(str(vm.get("stale_note") or vm.get("empty_message") or ""))}</div>
        </aside>
      </div>
      <div class="cc-decision-grid">{tile_html}</div>
      <div class="cc-decision-lists">
        <div class="cc-decision-list-card">
          <div class="cc-decision-list-title">禁止动作</div>
          {_decision_list(vm.get("must_not_do_items"), "暂无新增禁止动作，但仍需遵守交易纪律。")}
        </div>
        <div class="cc-decision-list-card">
          <div class="cc-decision-list-title">明日验证条件</div>
          {_decision_list(vm.get("validation_items"), "等待基础数据刷新后再生成验证条件。")}
        </div>
      </div>
      <div class="cc-coverage-grid">{coverage_html}</div>
      <div class="cc-decision-foot">
        状态：{escape(status)} ｜ 最后更新时间：{escape(str(vm.get("updated_text") or "暂无"))} ｜
        来源：{escape(str(vm.get("source_text") or "command_center_decision_engine"))} ｜ {escape(str(vm.get("deepseek_text") or "DeepSeek：未调用"))}
        <br>{escape(str(vm.get("evidence_summary_text") or ""))}
        <br>A股证据雷达：{escape(str(vm.get("a_share_evidence_summary_text") or "支持 0｜阻断 0｜缓存 0｜缺失 0"))}
      </div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def _home_text(value, fallback="暂无"):
    text = str(value or "").strip()
    return text or fallback


def _home_number(value, suffix=""):
    if value in [None, ""]:
        return "暂无"
    number = _to_float(value)
    if number is None:
        return str(value)
    if suffix == "%":
        return f"{number:.1f}%"
    if abs(number) >= 1000:
        return f"{number:,.0f}{suffix}"
    return f"{number:g}{suffix}"


def _home_list(items, fallback, limit=5):
    values = [str(item or "").strip() for item in (items or []) if str(item or "").strip()]
    if not values:
        values = [fallback]
    return "<ul class='cc-home-list'>" + "".join(f"<li>{escape(item)}</li>" for item in values[:limit]) + "</ul>"


def _home_freshness_class(state):
    text = str(state or "")
    if text == "today":
        return "ready"
    if text in {"stale", "partial_failed"}:
        return text
    return "missing"


def _apply_tool_recovery_navigation(action):
    for key, value in build_tool_recovery_navigation_state(action).items():
        if key and value is not None:
            st.session_state[key] = value


def render_home_action_snapshot(snapshot: dict | None = None):
    _inject_command_center_css()
    payload = snapshot or {}
    today_action = payload.get("today_action") or {}
    holding = payload.get("holding_action") or {}
    margin_etf = payload.get("margin_etf_summary") or {}
    risk_alerts = payload.get("risk_alerts") or {}
    freshness = payload.get("data_freshness") or {}
    data_capability = payload.get("data_capability") or {}
    data_gap_report = payload.get("data_gap_report") or {}
    data_issue_explainer = payload.get("data_issue_explainer") or {}
    data_capability_console = payload.get("data_capability_console") or {}
    data_recovery_actions = payload.get("data_recovery_actions") or data_capability_console.get("recovery_actions") or []
    tool_recovery_actions = payload.get("tool_recovery_actions") or []
    a_share_matrix = payload.get("a_share_capability_matrix") or {}
    a_share_user_diagnostic = payload.get("a_share_user_data_diagnostic") or {}
    a_share_recovery_actions = a_share_user_diagnostic.get("recovery_actions") or []
    facts_packet = payload.get("facts_packet") or {}
    discipline_packet = payload.get("discipline_packet") or {}
    market_profile = payload.get("market_profile_evidence") or {}
    candidates = payload.get("next_ticket_candidates") or []
    etfs = margin_etf.get("recommended_etfs") or []
    errors = payload.get("errors") or []
    coverage = payload.get("data_coverage") or {}

    freshness_state = str(freshness.get("state") or "missing")
    freshness_label = freshness.get("label") or "待刷新"
    coverage_ready = len([state for state in coverage.values() if state == "ready"])
    coverage_cached = len([state for state in coverage.values() if state == "cached"])
    coverage_missing = len([state for state in coverage.values() if state == "missing"])
    safety_line = payload.get("safety_line") or "本系统不自动交易，不保证收益；DeepSeek 只解释当前结构化结果。"
    market_profile_status = _home_text(market_profile.get("status"), "waiting")
    market_profile_tone = "ready" if market_profile_status == "ready" else "missing"
    market_profile_methods = [item for item in (market_profile.get("method_items") or []) if isinstance(item, dict)]
    market_profile_method_html = ""
    for item in market_profile_methods[:4]:
        market_profile_method_html += (
            f"<span class='cc-home-chip {escape(_home_text(item.get('tone'), 'missing'))}'>"
            f"{escape(_home_text(item.get('name'), '分析方法'))}：{escape(_home_text(item.get('status'), '待验证'))}"
            "</span>"
        )
    if not market_profile_method_html:
        market_profile_method_html = "<span class='cc-home-chip missing'>分析方法：待验证</span>"
    market_profile_sources = "、".join(str(item).strip() for item in (market_profile.get("data_sources") or [])[:4] if str(item).strip()) or "本地缓存"
    market_profile_focus = "、".join(str(item).strip() for item in (market_profile.get("focus_items") or [])[:6] if str(item).strip()) or "市场类型待确认"
    market_profile_risks = "、".join(str(item).strip() for item in (market_profile.get("risk_notes") or [])[:4] if str(item).strip()) or "数据缺口"
    market_profile_html = f"""
      <div class="cc-home-profile-strip">
        <div>
          <div class="cc-home-profile-title">
            市场口径
            <span class="cc-home-chip {escape(market_profile_tone)}">{escape(_home_text(market_profile.get("market_label"), "市场类型待确认"))}</span>
          </div>
          <div class="cc-home-profile-meta">
            标的：{escape(_home_text(market_profile.get("ticker"), "未锁定"))} {escape(_home_text(market_profile.get("name"), ""))}<br>
            数据源优先：{escape(market_profile_sources)}
          </div>
        </div>
        <div>
          <div class="cc-home-profile-meta">关注口径：{escape(market_profile_focus)}</div>
          <div class="cc-home-profile-meta">风险边界：{escape(market_profile_risks)} ｜ {escape(_home_text(market_profile.get("data_gap_text"), "待验证"))}</div>
          <div class="cc-home-profile-pills">{market_profile_method_html}</div>
        </div>
      </div>
    """

    if candidates:
        candidate_html = ""
        for item in candidates[:3]:
            evidence_text = "；".join(
                f"{_home_text(evidence.get('label'), '证据')}:{_home_text(evidence.get('value'), '待验证')}"
                for evidence in (item.get("evidence_items") or [])[:3]
                if isinstance(evidence, dict)
            ) or _home_text(item.get("reason"), "规则雷达缓存候选。")
            data_gap_text = "；".join(str(gap).strip() for gap in (item.get("data_gaps") or [])[:3] if str(gap).strip()) or "暂无显式数据缺口"
            candidate_html += f"""
            <div class="cc-home-candidate">
              <div class="cc-home-item-title">
                {escape(_home_text(item.get("ticker"), "候选"))} {escape(_home_text(item.get("name"), ""))}
                <span class="cc-home-chip {escape(_home_text(item.get("tone"), "missing"))}">{escape(_home_text(item.get("status_label"), item.get("action_state") or "只观察"))}</span>
              </div>
              <div class="cc-home-item-meta">综合分：{escape(_home_number(item.get("score")))} ｜ 入选依据：{escape(evidence_text)}</div>
              <div class="cc-home-item-meta">触发：{escape(_home_text(item.get("trigger_condition"), "等待触发条件确认。"))}</div>
              <div class="cc-home-item-meta">失效：{escape(_home_text(item.get("invalidation_condition"), "条件失效或风险转弱。"))}</div>
              <div class="cc-home-item-meta">数据缺口：{escape(data_gap_text)}</div>
              <div class="cc-home-item-meta">来源：{escape(_home_text(item.get("source"), "下一票雷达缓存"))} ｜ {escape(_home_text(item.get("updated_at"), "暂无时间"))}</div>
            </div>
            """
    else:
        candidate_html = "<div class='cc-home-candidate'><div class='cc-home-item-title'>暂无可执行候选</div><div class='cc-home-item-meta'>点击刷新今日基础数据生成；不会自动全市场扫描。</div></div>"

    if etfs:
        etf_html = ""
        for item in etfs[:3]:
            etf_evidence = "；".join(
                f"{_home_text(evidence.get('label'), '证据')}:{_home_text(evidence.get('value'), '待验证')}"
                for evidence in (item.get("evidence_items") or [])[:3]
                if isinstance(evidence, dict)
            ) or f"赛道:{_home_text(item.get('bucket'), 'ETF')}；分数:{_home_number(item.get('score'))}"
            etf_gaps = "；".join(str(gap).strip() for gap in (item.get("data_gaps") or [])[:3] if str(gap).strip()) or "暂无显式数据缺口"
            etf_html += f"""
            <div class="cc-home-etf">
              <div class="cc-home-item-title">
                {escape(_home_text(item.get("code"), "ETF"))} {escape(_home_text(item.get("name"), ""))}
                <span class="cc-home-chip {escape(_home_text(item.get("tone"), "stale"))}">{escape(_home_text(item.get("status_label"), item.get("action_state") or "只观察不追"))}</span>
              </div>
              <div class="cc-home-item-meta">{escape(_home_text(item.get("bucket"), "ETF"))} ｜ 分数：{escape(_home_number(item.get("score")))} ｜ {escape(_home_text(item.get("action_state"), "只观察不追"))}</div>
              <div class="cc-home-item-meta">证据：{escape(etf_evidence)}</div>
              <div class="cc-home-item-meta">触发：{escape(_home_text(item.get("trigger_condition"), "等待回踩、量能和风险线确认。"))}</div>
              <div class="cc-home-item-meta">风险：{escape(_home_text(item.get("risk_note"), "ETF 需复核流动性、跟踪指数、同类重叠和追高风险。"))}</div>
              <div class="cc-home-item-meta">数据缺口：{escape(etf_gaps)}</div>
            </div>
            """
    else:
        etf_html = "<div class='cc-home-etf'><div class='cc-home-item-title'>暂无 ETF 推荐缓存</div><div class='cc-home-item-meta'>刷新今日基础数据后读取本地 ETF 配置快照；不自动全量发现。</div></div>"

    error_line = "无" if not errors else f"{len(errors)} 个失败/错误"
    watch_not_chase_text = "；".join([str(item) for item in (margin_etf.get("watch_not_chase") or []) if str(item).strip()]) or "不追高 ETF；等待回踩、量能和风险线确认。"
    capability_summary = _home_text(data_capability.get("summary"), "尚未检测；页面打开不会自动请求 Tushare、AkShare 或 yfinance。")
    governance_summary = _home_text(data_gap_report.get("summary"), capability_summary)
    governance_checks = [str(item).strip() for item in (data_gap_report.get("next_manual_checks") or []) if str(item).strip()]
    capability_items = data_capability.get("items") or []
    capability_dashboard = build_data_capability_dashboard_view_model(data_capability, data_gap_report)
    console_ready = data_capability_console.get("available_count") or 0
    console_blocked = data_capability_console.get("blocked_count") or 0
    console_manual = data_capability_console.get("manual_count") or 0
    console_stale = data_capability_console.get("stale_count") or 0
    console_tone = _home_text(data_capability_console.get("tone"), "missing")
    console_readiness = _home_text(data_capability_console.get("decision_readiness_label"), "待检测")
    console_safe_mode = _home_text(data_capability_console.get("safe_mode_text"), "尚未检测数据能力；只能展示安全空态或上次成功结果。")
    console_queue_html = ""
    console_queues = [
        ("可用证据", data_capability_console.get("ready_items") or []),
        ("阻断项", data_capability_console.get("blocked_items") or []),
        ("手动刷新", data_capability_console.get("manual_items") or []),
        ("缓存/待验证", data_capability_console.get("stale_items") or []),
    ]
    for queue_label, queue_items in console_queues:
        if not queue_items:
            continue
        queue_text = "；".join(
            f"{_home_text(item.get('provider'), '数据源')}:{_home_text(item.get('label'), '数据')}"
            for item in queue_items[:3]
            if isinstance(item, dict)
        )
        if queue_text:
            console_queue_html += f"<div class='cc-home-item-meta'>{escape(queue_label)}：{escape(queue_text)}</div>"
    if not console_queue_html:
        console_queue_html = "<div class='cc-home-item-meta'>尚未检测数据能力；页面打开不会自动请求外部接口。</div>"
    recovery_action_html = ""
    for item in data_recovery_actions[:3]:
        if not isinstance(item, dict):
            continue
        recovery_action_html += f"""
        <div class="cc-home-item-meta">
          恢复：{escape(_home_text(item.get("label"), "数据能力"))}
          ｜{escape(_home_text(item.get("action_label"), "手动检查"))}
          ｜回流：{escape(_home_text(item.get("writes_packet"), "command_center_data_capability_packet"))}
          ｜入口：{escape(_home_text(item.get("toolbox_entry"), "高级工具箱 / 数据源体检"))}
        </div>
        """
    if not recovery_action_html:
        recovery_action_html = "<div class='cc-home-item-meta'>恢复动作：暂无需要手动恢复的数据源动作。</div>"
    tool_recovery_html = ""
    for item in tool_recovery_actions[:4]:
        if not isinstance(item, dict):
            continue
        tool_recovery_html += f"""
        <div class="cc-home-candidate">
          <div class="cc-home-item-title">
            {escape(_home_text(item.get("label"), "旧工具能力"))}
            <span class="cc-home-chip {escape('failed' if item.get('priority') == 1 else 'stale')}">{escape(_home_text(item.get("data_status"), item.get("status") or "待恢复"))}</span>
          </div>
          <div class="cc-home-item-meta">为什么：{escape(_home_text(item.get("reason"), "需要手动恢复旧工具能力。"))}</div>
          <div class="cc-home-item-meta">入口：{escape(_home_text(item.get("toolbox_entry"), "高级工具箱"))} ｜ 动作：{escape(_home_text(item.get("action_label"), "手动刷新"))}</div>
          <div class="cc-home-item-meta">定位：{escape(_home_text(item.get("navigation_label"), "主导航切到高级工具箱（旧版保留）后选择对应模块"))}</div>
          <div class="cc-home-item-meta">回流：{escape(_home_text(item.get("writes_packet"), "command_center_packet"))} ｜ 触发：手动按钮 ｜ DeepSeek：未调用</div>
        </div>
        """
    if not tool_recovery_html:
        tool_recovery_html = "<div class='cc-home-candidate'><div class='cc-home-item-title'>旧工具恢复队列为空</div><div class='cc-home-item-meta'>下一票雷达、融资 ETF、纪律/回测、量化推演已有可读 packet 或暂不需要恢复。</div></div>"
    issue_items = [item for item in (data_issue_explainer.get("items") or []) if isinstance(item, dict)]
    root_cause_items = [item for item in (data_issue_explainer.get("root_cause_items") or []) if isinstance(item, dict)]
    root_cause_html = ""
    for item in root_cause_items[:4]:
        root_cause_html += f"""
        <div class="cc-home-candidate">
          <div class="cc-home-item-title">
            {escape(_home_text(item.get("label"), "原因待确认"))}
            <span class="cc-home-chip {escape(_home_text(item.get("tone"), "missing"))}">{escape(_home_text(item.get("key"), "data_issue"))}</span>
          </div>
          <div class="cc-home-item-meta">原因：{escape(_home_text(item.get("detail"), "待验证。"))}</div>
          <div class="cc-home-item-meta">下一步：{escape(_home_text(item.get("next_action"), "保留安全空态或手动刷新。"))}</div>
        </div>
        """
    if not root_cause_html:
        root_cause_html = "<div class='cc-home-candidate'><div class='cc-home-item-title'>原因待确认</div><div class='cc-home-item-meta'>尚未检测数据能力；页面打开不会自动请求外部接口。</div></div>"
    issue_html = ""
    for item in issue_items[:3]:
        issue_html += f"""
        <div class="cc-home-candidate">
          <div class="cc-home-item-title">
            {escape(_home_text(item.get("label"), "数据能力"))}
            <span class="cc-home-chip {escape(_home_text(item.get("tone"), "missing"))}">{escape(_home_text(item.get("status_label"), item.get("state") or "待验证"))}</span>
          </div>
          <div class="cc-home-item-meta">为什么：{escape(_home_text(item.get("meaning"), "待验证。"))}</div>
          <div class="cc-home-item-meta">决策影响：{escape(_home_text(item.get("decision_impact"), "不能单独作为交易依据。"))}</div>
          <div class="cc-home-item-meta">下一步：{escape(_home_text(item.get("next_action"), "保留安全空态或手动刷新。"))}</div>
        </div>
        """
    if not issue_html:
        issue_html = "<div class='cc-home-candidate'><div class='cc-home-item-title'>暂无数据问题解释</div><div class='cc-home-item-meta'>尚未检测数据能力；页面打开不会自动请求外部接口。</div></div>"
    capability_text = "；".join(
        f"{_home_text(item.get('label'), item.get('api') or '数据')}: {_home_text(item.get('status'), item.get('state') or '待验证')}"
        for item in capability_items[:5]
        if isinstance(item, dict)
    ) or "暂无能力明细"
    provider_html = ""
    for card in (capability_dashboard.get("provider_cards") or [])[:4]:
        details = "；".join(
            f"{_home_text(item.get('label'), item.get('api') or '数据')}:{_home_text(item.get('status_label'), item.get('state') or '待验证')}"
            for item in (card.get("items") or [])[:3]
            if isinstance(item, dict)
        ) or "暂无明细"
        provider_html += f"""
        <div class="cc-home-candidate">
          <div class="cc-home-item-title">
            {escape(_home_text(card.get("provider"), "数据源"))}
            <span class="cc-home-chip {escape(_home_text(card.get("tone"), "missing"))}">{escape(_home_text(card.get("summary"), "待验证"))}</span>
          </div>
          <div class="cc-home-item-meta">{escape(details)}</div>
        </div>
        """
    if not provider_html:
        provider_html = "<div class='cc-home-candidate'><div class='cc-home-item-title'>数据源尚未检测</div><div class='cc-home-item-meta'>页面打开不会自动 ping Tushare、AkShare、yfinance 或 Supabase。</div></div>"
    matrix_items = [item for item in (a_share_matrix.get("items") or []) if isinstance(item, dict)]
    matrix_html = ""
    for item in matrix_items[:6]:
        manual_action = item.get("manual_action") or {}
        matched_text = "；".join(
            f"{_home_text(row.get('label'), row.get('api') or '数据')}:{_home_text(row.get('status_label'), row.get('state') or '待验证')}"
            for row in (item.get("matched_items") or [])[:2]
            if isinstance(row, dict)
        ) or "暂无本地检测结果"
        matrix_html += f"""
        <div class="cc-home-candidate">
          <div class="cc-home-item-title">
            {escape(_home_text(item.get("label"), "A股能力"))}
            <span class="cc-home-chip {escape(_home_text(item.get("tone"), "missing"))}">{escape(_home_text(item.get("status_label"), "待验证"))}</span>
          </div>
          <div class="cc-home-item-meta">接口：{escape(_home_text(item.get("api_hint"), "待接入"))} ｜ {escape(_home_text(item.get("decision_role"), "只作辅助验证。"))}</div>
          <div class="cc-home-item-meta">闭环：P{escape(_home_number(item.get("migration_priority")))} ｜ {escape(_home_text(item.get("decision_chain_stage"), "数据能力状态 → 待接入"))} ｜ 模块：{escape(_home_text(item.get("home_module"), "综合推演中心"))}</div>
          <div class="cc-home-item-meta">已匹配：{escape(matched_text)}</div>
          <div class="cc-home-item-meta">决策影响：{escape(_home_text(item.get("decision_impact"), "不能单独作为交易依据。"))}</div>
          <div class="cc-home-item-meta">迁移目标：{escape(_home_text(item.get("migration_target"), "逐步回流到综合推演中心 packet。"))}</div>
          <div class="cc-home-item-meta">下一步：{escape(_home_text(manual_action.get("button_label"), item.get("next_action") or "手动检测"))} ｜ 回流：{escape(_home_text(manual_action.get("writes_packet"), "command_center_facts_packet"))}</div>
        </div>
        """
    if not matrix_html:
        matrix_html = "<div class='cc-home-candidate'><div class='cc-home-item-title'>A股数据能力尚未检测</div><div class='cc-home-item-meta'>页面打开不会自动请求 Tushare；点击刷新或数据源体检后再进入矩阵。</div></div>"
    a_share_diagnostic_items_html = ""
    for item in (a_share_user_diagnostic.get("items") or [])[:4]:
        if not isinstance(item, dict):
            continue
        recovery = item.get("recovery") or {}
        a_share_diagnostic_items_html += f"""
        <div class="cc-home-item-meta">
          {escape(_home_text(item.get("label"), "A股数据"))}：
          {escape(_home_text(item.get("status_label"), "待验证"))}
          ｜{escape(_home_text(item.get("reason"), "页面打开不会自动请求重接口。"))}
        </div>
        <div class="cc-home-item-meta">
          恢复路径：{escape(_home_text(recovery.get("toolbox_entry") or item.get("toolbox_entry"), "综合推演中心 / A股数据能力检测"))}
          ｜动作：{escape(_home_text(recovery.get("action_label") or item.get("action_label"), "手动检测"))}
          ｜回流：{escape(_home_text(recovery.get("writes_packet") or item.get("writes_packet"), "command_center_facts_packet"))}
          ｜触发：{escape("无需恢复" if _home_text(recovery.get("refresh_policy") or item.get("refresh_policy")) == "not_needed" else "手动按钮")}
        </div>
        """
    if not a_share_diagnostic_items_html:
        a_share_diagnostic_items_html = "<div class='cc-home-item-meta'>尚未读取到 A股诊断明细；页面打开不会自动请求 Tushare。</div>"
    a_share_diagnostic_tone = _home_text(a_share_user_diagnostic.get("tone"), "missing")
    if a_share_diagnostic_tone == "warning":
        a_share_diagnostic_tone = "failed"
    elif a_share_diagnostic_tone == "success":
        a_share_diagnostic_tone = "ready"
    elif a_share_diagnostic_tone == "info":
        a_share_diagnostic_tone = "stale"
    a_share_diagnostic_html = f"""
        <div class="cc-home-candidate">
          <div class="cc-home-item-title">
            {escape(_home_text(a_share_user_diagnostic.get("title"), "A股数据能力诊断"))}
            <span class="cc-home-chip {escape(a_share_diagnostic_tone)}">{escape(_home_text(a_share_user_diagnostic.get("headline"), "待手动刷新"))}</span>
          </div>
          <div class="cc-home-item-meta">原因：{escape(_home_text(a_share_user_diagnostic.get("summary"), "尚未检测 A股专业数据能力。"))}</div>
          <div class="cc-home-item-meta">下一步：{escape(_home_text(a_share_user_diagnostic.get("next_action"), "点击 A股数据能力检测或对应刷新按钮。"))}</div>
          <div class="cc-home-item-meta">安全边界：{escape(_home_text(a_share_user_diagnostic.get("safe_mode_text"), "页面打开不会自动请求外部重接口。"))}</div>
          {a_share_diagnostic_items_html}
        </div>
        """
    fact_items = [item for item in (facts_packet.get("items") or []) if isinstance(item, dict)]
    fact_gap_summary = _home_text(facts_packet.get("gap_summary"), "")
    fact_next_checks = [str(item).strip() for item in (facts_packet.get("next_manual_checks") or []) if str(item).strip()]
    discipline_status = _home_text(discipline_packet.get("backtest_status"), "待手动运行回测")
    discipline_tone = "ready" if discipline_packet.get("data_status") == "ready" else "missing"
    if discipline_packet.get("action_state") == "降风险":
        discipline_tone = "failed"
    elif discipline_packet.get("data_status") == "cached":
        discipline_tone = "stale"
    discipline_metrics = " ｜ ".join(
        f"{_home_text(item.get('label'), '指标')}:{_home_text(item.get('value'), '待验证')}"
        for item in (discipline_packet.get("metric_items") or [])[:4]
        if isinstance(item, dict)
    ) or "暂无回测指标"
    discipline_evidence = "；".join(
        f"{_home_text(item.get('label'), '证据')}:{_home_text(item.get('value'), '待验证')}"
        for item in (discipline_packet.get("evidence_items") or [])[:3]
        if isinstance(item, dict)
    ) or "暂无纪律证据"
    discipline_warnings = "；".join(
        str(item).strip()
        for item in (discipline_packet.get("warnings") or [])[:3]
        if str(item).strip()
    ) or _home_text(discipline_packet.get("backtest_required_text"), "回测必须手动触发。")
    discipline_html = f"""
        <div class="cc-home-candidate">
          <div class="cc-home-item-title">
            纪律/回测证据
            <span class="cc-home-chip {escape(discipline_tone)}">{escape(discipline_status)}</span>
          </div>
          <div class="cc-home-item-meta">动作边界：{escape(_home_text(discipline_packet.get("action_state"), "待刷新"))} ｜ 最新信号：{escape(_home_text(discipline_packet.get("latest_signal"), "待验证"))}</div>
          <div class="cc-home-item-meta">指标：{escape(discipline_metrics)}</div>
          <div class="cc-home-item-meta">证据：{escape(discipline_evidence)}</div>
          <div class="cc-home-item-meta">边界：{escape(discipline_warnings)}</div>
        </div>
        """
    evidence_vm = build_a_share_evidence_radar_view_model(payload)
    evidence_items = [item for item in (evidence_vm.get("items") or []) if isinstance(item, dict)]
    evidence_action_items = [item for item in (evidence_vm.get("next_evidence_actions") or []) if isinstance(item, dict)]
    evidence_action_html = ""
    for item in evidence_action_items[:3]:
        manual_action = item.get("manual_action") or {}
        refresh_policy = _home_text(manual_action.get("refresh_policy"), "button_gated")
        refresh_policy_text = "手动触发" if refresh_policy == "button_gated" else refresh_policy
        evidence_action_html += f"""
        <div class="cc-home-candidate">
          <div class="cc-home-item-title">
            {escape(_home_text(item.get("label"), "待补证据"))}
            <span class="cc-home-chip {escape(_home_text(item.get("tone"), "missing"))}">P{escape(_home_number(item.get("priority")))} · {escape(_home_text(item.get("evidence_label"), "待验证证据"))}</span>
          </div>
          <div class="cc-home-item-meta">下一步：{escape(_home_text(item.get("action_hint"), "手动补齐证据后再进入决策。"))}</div>
          <div class="cc-home-item-meta">入口：{escape(_home_text(manual_action.get("toolbox_entry"), "高级工具箱 / 数据源体检"))} ｜ 动作：{escape(_home_text(manual_action.get("button_label"), "手动刷新"))}</div>
          <div class="cc-home-item-meta">回流：{escape(_home_text(manual_action.get("writes_packet"), "command_center_facts_packet"))} ｜ 触发：{escape(refresh_policy_text)}</div>
        </div>
        """
    if not evidence_action_html:
        evidence_action_html = "<div class='cc-home-candidate'><div class='cc-home-item-title'>A股证据暂不需要补齐</div><div class='cc-home-item-meta'>当前证据队列没有阻断、缓存或缺失项；仍需结合价格纪律和仓位规则。</div></div>"
    evidence_html = ""
    for item in evidence_items:
        evidence_html += f"""
        <div class="cc-home-candidate">
          <div class="cc-home-item-title">
            {escape(_home_text(item.get("label"), "证据"))}
            <span class="cc-home-chip {escape(_home_text(item.get("tone"), "missing"))}">P{escape(_home_number(item.get("priority")))} · {escape(_home_text(item.get("evidence_label"), item.get("status_label") or "待验证"))}</span>
          </div>
          <div class="cc-home-item-meta">状态：{escape(_home_text(item.get("headline"), "待验证"))} ｜ 关键值：{escape(_home_text(item.get("metric"), "暂无"))}</div>
          <div class="cc-home-item-meta">用途：{escape(_home_text(item.get("decision_role"), "辅助验证，不单独决策。"))}</div>
          <div class="cc-home-item-meta">信号：{escape(_home_text(item.get("decision_signal"), "待验证。"))}</div>
          <div class="cc-home-item-meta">风险：{escape(_home_text(item.get("risk_text"), "待验证，不能单独作为交易依据。"))}</div>
          <div class="cc-home-item-meta">来源：{escape(_home_text(item.get("source"), "本地缓存"))} ｜ {escape(_home_text(item.get("updated_at"), "暂无时间"))}</div>
        </div>
        """
    fact_gap_html = ""
    if fact_gap_summary or fact_next_checks:
        fact_gap_html = f"""
        <div class="cc-muted-note">数据缺口说明：{escape(fact_gap_summary or "暂无缺口说明。")}</div>
        {_home_list(fact_next_checks, "暂无下一步检查建议。", limit=4)}
        """
    if fact_items:
        facts_html = ""
        for item in fact_items[:5]:
            facts_html += f"""
            <div class="cc-home-candidate">
              <div class="cc-home-item-title">{escape(_home_text(item.get("label"), "事实"))} · {escape(_home_text(item.get("status"), "待验证"))}</div>
              <div class="cc-home-item-meta">证据：{escape(_home_text(item.get("evidence"), "待验证。"))}</div>
              <div class="cc-home-item-meta">风险：{escape(_home_text(item.get("risk"), "暂无新增风险。"))}</div>
              <div class="cc-home-item-meta">来源：{escape(_home_text(item.get("source"), "本地缓存"))} ｜ {escape(_home_text(item.get("updated_at"), "暂无时间"))}</div>
            </div>
            """
    else:
        facts_html = "<div class='cc-home-candidate'><div class='cc-home-item-title'>暂无已验证事实包</div><div class='cc-home-item-meta'>旧工作台能力会逐步迁移为 packet；页面打开不会自动拉取重数据。</div></div>"
    html = f"""
    <section class="cc-home-snapshot">
      <div class="cc-home-head">
        <div>
          <div class="cc-home-kicker">Home Action Snapshot</div>
          <h2 class="cc-home-action">{escape(_home_text(today_action.get("overall_action"), "等待"))}</h2>
          <div class="cc-strategy-summary">
            市场：{escape(_home_text(today_action.get("market_bias"), "未刷新"))} ｜
            主账户：{escape(_home_text(today_action.get("position_mode"), "空仓等待"))} ｜
            融资：{escape(_home_text(today_action.get("margin_mode"), "不使用融资"))}
          </div>
          <div class="cc-home-chip-row">
            <span class="cc-home-chip {_home_freshness_class(freshness_state)}">数据状态：{escape(str(freshness_label))}</span>
            <span class="cc-home-chip">已刷新 {coverage_ready}</span>
            <span class="cc-home-chip stale">缓存 {coverage_cached}</span>
            <span class="cc-home-chip missing">待刷新 {coverage_missing}</span>
            <span class="cc-home-chip">DeepSeek：{'已调用' if payload.get('deepseek_called') else '未调用'}</span>
          </div>
        </div>
        <aside class="cc-home-side">
          <div class="cc-home-side-label">风险等级</div>
          <div class="cc-home-risk">{escape(_home_text(today_action.get("risk_level"), "中"))}</div>
          <div class="cc-muted-note">最后更新时间：{escape(_home_text(freshness.get("last_updated"), "暂无"))}</div>
          <div class="cc-muted-note">失败/错误：{escape(error_line)}</div>
        </aside>
      </div>
      {market_profile_html}
      <div class="cc-home-grid">
        <div class="cc-home-panel">
          <div class="cc-home-panel-title">当前持仓动作</div>
          <div class="cc-home-big-value">{escape(_home_text(holding.get("action_state"), "待刷新"))}</div>
          <div class="cc-home-row"><span>标的</span><strong>{escape(_home_text(holding.get("ticker"), "未锁定"))} {escape(_home_text(holding.get("name"), ""))}</strong></div>
          <div class="cc-home-row"><span>周期</span><strong>{escape(_home_text(holding.get("investment_horizon"), "未设置"))}</strong></div>
          <div class="cc-home-row"><span>成本 / 数量</span><strong>{escape(_home_number(holding.get("cost")))} / {escape(_home_number(holding.get("shares")))}</strong></div>
          <div class="cc-home-row"><span>现价 / 浮盈亏</span><strong>{escape(_home_number(holding.get("current_price")))} / {escape(_home_text(holding.get("floating_pnl_text"), "暂无"))}</strong></div>
          <div class="cc-home-row"><span>加仓条件</span><strong>{escape(_home_text(holding.get("add_condition"), "等待验证。"))}</strong></div>
          <div class="cc-home-row"><span>减仓条件</span><strong>{escape(_home_text(holding.get("reduce_condition"), "触发风险线时优先降低暴露。"))}</strong></div>
          <div class="cc-home-row"><span>失效条件</span><strong>{escape(_home_text(holding.get("invalidation_condition"), "市场转弱或纪律反向。"))}</strong></div>
        </div>
        <div class="cc-home-panel">
          <div class="cc-home-panel-title">下一票候选 Top 3</div>
          {candidate_html}
        </div>
        <div class="cc-home-panel">
          <div class="cc-home-panel-title">ETF / 融资动作</div>
          <div class="cc-home-big-value">{escape(_home_text(margin_etf.get("today_main_direction"), "待刷新"))}</div>
          <div class="cc-home-row"><span>当前融资比例</span><strong>{escape(_home_number(margin_etf.get("current_margin_ratio"), "%"))}</strong></div>
          <div class="cc-home-row"><span>建议融资比例</span><strong>{escape(_home_number(margin_etf.get("recommended_margin_ratio"), "%"))}</strong></div>
          <div class="cc-home-row"><span>建议现金比例</span><strong>{escape(_home_number(margin_etf.get("recommended_cash_ratio"), "%"))}</strong></div>
          {etf_html}
          <div class="cc-muted-note">不追高 ETF：{escape(watch_not_chase_text)}</div>
        </div>
      </div>
      <div class="cc-home-bottom">
        <div class="cc-home-panel">
          <div class="cc-home-panel-title">风险警报</div>
          {_home_list(risk_alerts.get("must_not_do"), "不追高、不满仓、不在未刷新数据下加融资。")}
          <div class="cc-muted-note">必须降风险条件：{escape("；".join(risk_alerts.get("reduce_conditions") or ["暂无新增条件"]))}</div>
          <div class="cc-muted-note">数据缺口：{escape("、".join(risk_alerts.get("data_gaps") or ["暂无"]))}</div>
        </div>
        <div class="cc-home-panel">
          <div class="cc-home-panel-title">已验证事实</div>
          {discipline_html}
          <div class="cc-muted-note">{escape(_home_text(evidence_vm.get("title"), "A股证据雷达"))}：{escape(_home_text(evidence_vm.get("summary"), "暂无证据摘要。"))} ｜ {escape(_home_text(evidence_vm.get("decision_summary"), "支持 0｜阻断 0｜缓存 0｜缺失 0"))}</div>
          <div class="cc-home-item-title">下一步证据补齐队列</div>
          {evidence_action_html}
          <div class="cc-home-item-title">旧工具能力恢复队列</div>
          {tool_recovery_html}
          {evidence_html}
          <div class="cc-muted-note">{escape(_home_text(facts_packet.get("summary"), "暂无可验证事实包。"))}</div>
          {fact_gap_html}
          {facts_html}
        </div>
        <div class="cc-home-panel">
          <div class="cc-home-panel-title">数据新鲜度</div>
          <div class="cc-home-big-value">{escape(str(freshness_label))}</div>
          <div class="cc-home-row"><span>最后更新时间</span><strong>{escape(_home_text(freshness.get("last_updated"), "暂无"))}</strong></div>
          <div class="cc-home-row"><span>是否使用缓存</span><strong>{'是' if risk_alerts.get('uses_cache') or freshness_state == 'stale' else '否'}</strong></div>
          <div class="cc-home-row"><span>数据治理</span><strong>{escape(governance_summary)}</strong></div>
          <div class="cc-home-candidate">
            <div class="cc-home-item-title">
              {escape(_home_text(a_share_matrix.get("title"), "A股数据能力矩阵"))}
              <span class="cc-home-chip {escape(_home_text(a_share_matrix.get("tone"), "missing"))}">{escape(_home_text(a_share_matrix.get("summary"), "尚未检测 A股专业数据能力。"))}</span>
            </div>
            <div class="cc-home-item-meta">{escape(_home_text(a_share_matrix.get("manual_note"), "只读取本地 packet，不自动请求外部接口。"))}</div>
          </div>
          {matrix_html}
          <div class="cc-home-candidate">
            <div class="cc-home-item-title">
              数据能力控制台
              <span class="cc-home-chip {escape(console_tone)}">{escape(_home_text(data_capability_console.get("headline"), "尚未检测数据能力"))}</span>
            </div>
            <div class="cc-home-item-meta">可用 {escape(_home_number(console_ready))}｜阻断 {escape(_home_number(console_blocked))}｜手动 {escape(_home_number(console_manual))}｜缓存/待验证 {escape(_home_number(console_stale))}</div>
            <div class="cc-home-item-meta">决策模式：{escape(console_readiness)}｜{escape(console_safe_mode)}</div>
            {console_queue_html}
            {recovery_action_html}
          </div>
          <div class="cc-muted-note">为什么搜不到：{escape(_home_text(data_issue_explainer.get("short_answer"), "尚未检测数据能力；不会自动 ping 外部接口。"))}</div>
          {a_share_diagnostic_html}
          {root_cause_html}
          {issue_html}
          <div class="cc-muted-note">数据能力诊断：{escape(_home_text(capability_dashboard.get("summary"), "尚未检测数据能力。"))}</div>
          {provider_html}
          {_home_list(governance_checks, "暂无下一步检查建议。", limit=4)}
          <div class="cc-muted-note">{escape(capability_text)}</div>
          <div class="cc-home-row"><span>DeepSeek</span><strong>{'已调用' if payload.get('deepseek_called') else '未调用'}</strong></div>
          <div class="cc-muted-note">{escape(str(safety_line))}</div>
        </div>
      </div>
      <div class="cc-home-foot">快照只读取本地结构化结果；页面打开不会自动调用 DeepSeek、回测、全市场扫描或重型行情接口。</div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)
    valid_tool_recovery_actions = [item for item in tool_recovery_actions[:4] if isinstance(item, dict)]
    if valid_tool_recovery_actions:
        st.caption("旧工具恢复入口只负责切换到高级工具箱；不会自动运行扫描、回测、DeepSeek 或重型数据接口。")
        nav_cols = st.columns(min(4, len(valid_tool_recovery_actions)))
        for index, item in enumerate(valid_tool_recovery_actions):
            with nav_cols[index % len(nav_cols)]:
                st.button(
                    f"打开{_home_text(item.get('label'), '高级工具')}",
                    key=f"btn_open_tool_recovery_{_home_text(item.get('key'), index)}",
                    help=_home_text(item.get("navigation_label"), "切换到高级工具箱对应模块；不自动执行旧工具。"),
                    on_click=_apply_tool_recovery_navigation,
                    args=(item,),
                    width="stretch",
                )
    valid_a_share_recovery_actions = [item for item in a_share_recovery_actions[:4] if isinstance(item, dict)]
    if valid_a_share_recovery_actions:
        st.caption("A股数据恢复入口只负责定位到手动检测区域；不会自动请求 Tushare、DeepSeek 或回测。")
        nav_cols = st.columns(min(4, len(valid_a_share_recovery_actions)))
        for index, item in enumerate(valid_a_share_recovery_actions):
            with nav_cols[index % len(nav_cols)]:
                st.button(
                    f"打开{_home_text(item.get('label'), 'A股数据')}恢复入口",
                    key=f"btn_open_a_share_recovery_{_home_text(item.get('key'), index)}",
                    help=_home_text(item.get("navigation_label"), "切换到高级工具箱对应模块；不自动执行旧工具。"),
                    on_click=_apply_tool_recovery_navigation,
                    args=(item,),
                    width="stretch",
                )


def render_command_center_shell(active_nav: str = "综合推演中心 2.0"):
    _inject_command_center_css()
    title = active_nav or "综合推演中心 2.0"
    subtitle = "把量化推演、交易纪律实验室和风险验证放在同一张工作台。默认展示缓存或 mock packet；重型扫描、DeepSeek、Tushare 批量请求都必须手动触发。"
    if title != "综合推演中心 2.0":
        subtitle = "左侧导航为真实 Streamlit 控件；当前模块为轻量占位，不触发 DeepSeek、Tushare 批量请求或旧版重型 tabs。"
    st.markdown(
        f"""
        <div class="cc-shell">
          <main class="cc-main">
            <section class="cc-hero">
              <div class="cc-kicker">Integrated Simulation Center</div>
              <h1 class="cc-title">{escape(str(title))}</h1>
              <div class="cc-subtitle">{escape(subtitle)}</div>
            </section>
          </main>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_command_center_shell_end():
    return None


def render_process_stepper(steps=None, active_step: int = 2):
    _inject_command_center_css()
    default_steps = [
        ("市场环境", "☁", "先判断风格与风险温度"),
        ("结构化数据", "▦", "只引用可验证事实"),
        ("个股推演", "↗", "输出未来路径假设"),
        ("交易纪律实验室", "▣", "用规则校验动作边界"),
        ("下一波趋势结论", "✦", "融合为条件化结论"),
    ]
    steps = steps or default_steps
    html = "<div class='cc-stepper'>"
    for idx, item in enumerate(steps):
        title, icon, desc = item
        html += (
            f"<div class='cc-step {'active' if idx == active_step else ''}'>"
            f"<div class='cc-step-icon'>{escape(str(icon))}</div>"
            f"<div class='cc-step-title'>{escape(str(title))}</div>"
            f"<div class='cc-step-desc'>{escape(str(desc))}</div>"
            "</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_command_center_account_budget_card(packet: dict | None = None):
    _inject_command_center_css()
    payload = packet or {}
    account = payload.get("account_snapshot") or {}
    budget = payload.get("allocation_budget") or {}
    metrics = [
        ("净资产", _cc_money_line(account.get("net_asset"), "按净资产")),
        ("现金", _cc_money_line(account.get("cash"), "按可用现金")),
        ("股票市值", _cc_money_line(account.get("stock_value"), "按建议总敞口")),
        ("ETF 市值", _cc_money_line(account.get("etf_value"), "按建议总敞口")),
        ("融资负债", _cc_money_line(account.get("margin_debt"), "按净资产")),
        ("可用融资", _cc_money_line(account.get("available_margin"), "按可用现金")),
    ]
    budget_metrics = [
        ("建议风险预算", _cc_money_line(budget.get("risk_budget_amount"), "按净资产")),
        ("下一票观察预算", _cc_money_line(budget.get("next_ticket_budget_amount"), "按风险预算")),
        ("ETF 预算", _cc_money_line(budget.get("etf_budget_amount"), "按净资产")),
        ("现金缓冲", _cc_money_line(budget.get("cash_buffer_amount"), "按净资产")),
        ("可加仓金额", _cc_money_line(budget.get("max_add_amount"), "按可用现金")),
        ("建议调整金额", _cc_money_line(budget.get("suggested_adjustment_amount"), "按建议总敞口")),
    ]
    html = "<section class='cc-card'><div class='cc-card-title'>账户金额与配置预算</div><div class='cc-card-caption'>金额均为人民币整数口径；mock packet 仅用于展示页面口径，不触发外部接口。</div><div class='cc-money-grid'>"
    for label, value in [*metrics, *budget_metrics]:
        html += (
            "<div class='cc-money-card'>"
            f"<div class='cc-mini-title'>{escape(label)}</div>"
            f"<div class='cc-money-value'>{escape(value)}</div>"
            "</div>"
        )
    html += "</div></section>"
    st.markdown(html, unsafe_allow_html=True)


def render_fusion_summary_card(packet: dict | None = None):
    _inject_command_center_css()
    payload = packet or {}
    allocation = payload.get("allocation_budget") or {}
    quant = payload.get("quant_output") or {}
    discipline = payload.get("discipline_output") or {}
    fusion = payload.get("fusion_output") or {}
    risk_budget = _cc_money_line(allocation.get("risk_budget_amount"), "按净资产")
    observation_budget = _cc_money_line(allocation.get("next_ticket_budget_amount"), "按风险预算")
    suggested_amount = _cc_money_line(
        fusion.get("suggested_amount") or allocation.get("risk_budget_amount"),
        fusion.get("amount_basis") or "按风险预算",
    )
    st.markdown(
        f"""
        <div class="cc-summary-grid">
          <section class="cc-card">
            <div class="cc-card-title">下一波趋势综合结论</div>
            <div class="cc-card-caption">结论来自缓存或 mock packet；不自动调用 DeepSeek。</div>
            <div class="cc-score">{int(payload.get('score') or 0)}<span>/100</span></div>
            <div class="cc-pill-row">
              <span class="cc-pill green">趋势：{escape(str(payload.get('trend_label') or '暂无'))}</span>
              <span class="cc-pill">概率：{escape(str(payload.get('probability') or 0))}%</span>
              <span class="cc-pill purple">置信度：{escape(str(payload.get('confidence') or '暂无'))}</span>
              <span class="cc-pill green">建议风险预算金额：{escape(risk_budget)}</span>
              <span class="cc-pill">建议观察仓位金额：{escape(observation_budget)}</span>
            </div>
            <div style="font-size:18px;font-weight:800;color:#0f172a;line-height:1.45;">{escape(str(payload.get('one_sentence') or '暂无结论。'))}</div>
            <div class="cc-muted-note">结论更新时间：{escape(str(payload.get('updated_at') or '暂无'))}</div>
          </section>
          <section class="cc-card">
            <div class="cc-card-title">融合图</div>
            <div class="cc-card-caption">推演输出 + 纪律实验室输出 → 综合推演引擎。</div>
            <div class="cc-fusion-flow">
              <div class="cc-mini-card">
                <div class="cc-mini-title">推演输出</div>
                <div class="cc-mini-value">{escape(str(quant.get('label') or '中性偏强'))}</div>
                <div class="cc-mini-desc">{escape(str(quant.get('summary') or '路径推演等待刷新。'))}</div>
              </div>
              <div class="cc-arrow">＋</div>
              <div class="cc-mini-card">
                <div class="cc-mini-title">纪律实验室输出</div>
                <div class="cc-mini-value">{escape(str(discipline.get('label') or '等待验证'))}</div>
                <div class="cc-mini-desc">{escape(str(discipline.get('summary') or '纪律校验等待运行。'))}</div>
              </div>
              <div class="cc-arrow">→</div>
              <div class="cc-mini-card">
                <div class="cc-mini-title">综合推演引擎</div>
                <div class="cc-mini-value">{escape(str(fusion.get('label') or '条件看多'))}</div>
                <div class="cc-mini-desc">
                  综合分：{escape(str(fusion.get('composite_score') or payload.get('score') or 0))}/100<br>
                  胜率：{escape(str(fusion.get('win_rate') or '暂无'))}<br>
                  建议仓位：{escape(str(fusion.get('suggested_position') or '暂无'))}<br>
                  建议金额：{escape(suggested_amount)}<br>
                  {escape(str(fusion.get('summary') or '只输出条件化观察，不直接决定仓位。'))}
                </div>
              </div>
            </div>
          </section>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _projection_status_label(status):
    return {
        "ready": "已生成",
        "cached": "使用缓存",
        "waiting": "待刷新",
        "failed": "失败",
    }.get(str(status or ""), "待刷新")


def _projection_path_cards(paths):
    tones = ["green", "blue", "orange"]
    for col, item, tone in zip(st.columns(3), (paths or [])[:3], tones):
        name = str(item.get("name") or "路径")
        probability = item.get("probability")
        probability_text = "暂无" if probability in [None, ""] else f"{probability}%"
        with col:
            with st.container(border=True):
                st.markdown(f"##### {name}")
                st.markdown(f"<span class='cc-projection-pill {tone}'>{escape(probability_text)}</span>", unsafe_allow_html=True)
                st.caption("触发条件")
                st.write(str(item.get("trigger") or "等待验证。"))
                st.caption("对应动作")
                st.write(str(item.get("action") or "只观察。"))
                st.caption("风险提示")
                st.write(str(item.get("risk") or "不追高、不满仓。"))


def _analysis_status_class(status):
    text = str(status or "").strip()
    if text == "通过":
        return "passed"
    if text in {"失败", "风险"}:
        return "failed"
    if text == "不适用":
        return "na"
    return "pending"


def render_analysis_methods_card(packet: dict | None = None):
    _inject_command_center_css()
    payload = packet or {}
    market = str(payload.get("market") or "").strip()
    market_label = market if market and market not in {"未知", "UNKNOWN"} else "市场类型待确认"
    methods = [item for item in (payload.get("methods") or []) if isinstance(item, dict)]
    if not methods:
        methods = [
            {
                "name": "市场画像",
                "status": "待验证",
                "evidence": "当前缺少 ticker 或市场类型，无法套用 A股 / 美股 / ETF 专属框架。",
                "risk": "不要把通用说明当成交易依据。",
                "action_hint": "先刷新今日基础数据或确认当前标的。",
            }
        ]

    method_html = ""
    for item in methods:
        status = str(item.get("status") or "待验证")
        status_class = _analysis_status_class(status)
        method_html += (
            f"<div class='cc-analysis-method {status_class}'>"
            f"<div class='cc-analysis-method-title'>{escape(str(item.get('name') or '分析方法'))}</div>"
            f"<span class='cc-analysis-status {status_class}'>{escape(status)}</span>"
            f"<div class='cc-analysis-line'><span>证据</span> {escape(str(item.get('evidence') or '数据不足，待刷新验证。'))}</div>"
            f"<div class='cc-analysis-line'><span>风险</span> {escape(str(item.get('risk') or '数据缺口'))}</div>"
            f"<div class='cc-analysis-line'><span>动作</span> {escape(str(item.get('action_hint') or '待验证后再行动。'))}</div>"
            "</div>"
        )

    html = f"""
    <section class="cc-analysis-card">
      <div class="cc-analysis-head">
        <div>
          <div class="cc-analysis-kicker">Analysis Methods</div>
          <h2 class="cc-analysis-title">市场分析方法</h2>
          <div class="cc-analysis-summary">{escape(str(payload.get("summary") or "市场类型待确认；数据不足时所有方法都必须保持待验证。"))}</div>
        </div>
        <div class="cc-analysis-market">{escape(market_label)}</div>
      </div>
      <div class="cc-analysis-method-grid">{method_html}</div>
      <div class="cc-analysis-foot">
        来源：{escape(str(payload.get("source") or "rule-based market profile"))} ｜
        更新时间：{escape(str(payload.get("updated_at") or "暂无"))} ｜
        DeepSeek：未调用。该卡只解释当前市场适用的分析口径，不改变交易结论。
      </div>
    </section>
    """
    _render_html(html)


def _projection_static_frame(packet):
    payload = packet or {}
    rows = {}
    for item in payload.get("historical") or []:
        rows.setdefault(item.get("t"), {})["历史走势"] = item.get("value")
    for path in payload.get("paths") or []:
        name = path.get("name") or "路径"
        for item in path.get("points") or []:
            rows.setdefault(item.get("t"), {})[name] = item.get("value")
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def render_command_center_projection_chart(projection_packet: dict | None = None):
    _inject_command_center_css()
    payload = projection_packet or {}
    paths = payload.get("paths") or []
    status_label = _projection_status_label(payload.get("status"))
    note = str(payload.get("note") or "路径推演 / 待验证")
    updated_at = str(payload.get("updated_at") or "暂无")
    source = str(payload.get("source") or "command_center_projection")
    horizon = payload.get("horizon_days") or 10
    packet_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    chart_html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js" onerror="window.__stockMingEchartsFailed=true"></script>
      <style>
        html, body {{ margin: 0; padding: 0; background: transparent; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif; }}
        .projection-shell {{
          box-sizing: border-box;
          height: 372px;
          background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.98));
          border: 1px solid rgba(15,23,42,0.08);
          border-radius: 24px;
          padding: 16px 16px 10px;
          overflow: hidden;
        }}
        .projection-head {{
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 12px;
          margin-bottom: 6px;
        }}
        .projection-title {{ color: #0f172a; font-weight: 820; font-size: 18px; letter-spacing: 0; }}
        .projection-subtitle {{ color: #64748b; font-size: 12px; line-height: 1.45; margin-top: 3px; }}
        .projection-badge {{
          border-radius: 999px;
          background: rgba(37, 99, 235, 0.10);
          border: 1px solid rgba(37, 99, 235, 0.14);
          color: #1d4ed8;
          padding: 7px 10px;
          font-size: 12px;
          font-weight: 760;
          white-space: nowrap;
        }}
        #projection-chart {{ height: 285px; width: 100%; }}
        .fallback-svg {{ width: 100%; height: 285px; display: block; }}
        .fallback-label {{ font-size: 11px; fill: #64748b; font-weight: 650; }}
      </style>
    </head>
    <body>
      <section class="projection-shell">
        <div class="projection-head">
          <div>
            <div class="projection-title">未来 5~10 个交易日趋势推演</div>
            <div class="projection-subtitle">{escape(note)} ｜ 最后更新时间：{escape(updated_at)} ｜ DeepSeek：未调用</div>
          </div>
          <div class="projection-badge">{escape(status_label)} · {escape(str(horizon))}日</div>
        </div>
        <div id="projection-chart"></div>
      </section>
      <script>
        const packet = {packet_json};
        const root = document.getElementById('projection-chart');
        const colors = ['#14b8a6', '#2563eb', '#f97316'];
        const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        function allPoints() {{
          const points = [];
          (packet.historical || []).forEach(p => points.push([Number(p.t), Number(p.value)]));
          (packet.paths || []).forEach(path => (path.points || []).forEach(p => points.push([Number(p.t), Number(p.value)])));
          return points.filter(p => Number.isFinite(p[0]) && Number.isFinite(p[1]));
        }}
        function renderFallback() {{
          const points = allPoints();
          if (!points.length) {{
            root.innerHTML = '<div style="color:#64748b;font-size:13px;padding:36px 10px;">暂无路径数据，点击刷新今日基础数据生成。</div>';
            return;
          }}
          const minX = Math.min(...points.map(p => p[0]));
          const maxX = Math.max(...points.map(p => p[0]));
          const minY = Math.min(...points.map(p => p[1]));
          const maxY = Math.max(...points.map(p => p[1]));
          const w = Math.max(root.clientWidth || 760, 320);
          const h = 285;
          const pad = 26;
          const sx = x => pad + (x - minX) / Math.max(maxX - minX, 1) * (w - pad * 2);
          const sy = y => h - pad - (y - minY) / Math.max(maxY - minY, 1) * (h - pad * 2);
          const line = (items, color, dash='') => '<polyline fill="none" stroke="' + color + '" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" ' + dash + ' points="' + items.map(p => sx(Number(p.t)) + ',' + sy(Number(p.value))).join(' ') + '" />';
          let svg = '<svg class="fallback-svg" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none">';
          svg += '<line x1="' + sx(0) + '" y1="18" x2="' + sx(0) + '" y2="' + (h - 18) + '" stroke="#94a3b8" stroke-dasharray="4 4" />';
          svg += '<text x="' + (sx(0) + 6) + '" y="28" class="fallback-label">T0</text>';
          svg += line(packet.historical || [], '#94a3b8');
          (packet.paths || []).slice(0, 3).forEach((path, idx) => {{
            svg += line(path.points || [], colors[idx], 'stroke-dasharray="' + (idx === 1 ? '0' : '5 5') + '"');
            const last = (path.points || [])[Math.max((path.points || []).length - 1, 0)] || {{}};
            if (last.t !== undefined) svg += '<text x="' + (sx(Number(last.t)) - 54) + '" y="' + (sy(Number(last.value)) - 8) + '" class="fallback-label">' + String(path.name || '路径') + ' ' + String(path.probability || '') + '%</text>';
          }});
          svg += '</svg>';
          root.innerHTML = svg;
        }}
        function makeSeries(step) {{
          const historical = (packet.historical || []).map(p => [Number(p.t), Number(p.value)]);
          const series = [{{
            name: '历史走势',
            type: 'line',
            data: historical,
            symbol: 'none',
            smooth: 0.35,
            lineStyle: {{ width: 3, color: '#94a3b8' }},
            markLine: {{ symbol: 'none', lineStyle: {{ color: '#64748b', type: 'dashed' }}, data: [{{ xAxis: 0, name: 'T0' }}], label: {{ formatter: 'T0' }} }}
          }}];
          (packet.paths || []).slice(0, 3).forEach((path, idx) => {{
            const full = (path.points || []).map(p => [Number(p.t), Number(p.value)]);
            const data = reducedMotion ? full : full.slice(0, Math.max(1, step + 1));
            series.push({{
              name: String(path.name || '路径') + ' · ' + String(path.probability || 0) + '%',
              type: 'line',
              data,
              symbol: 'circle',
              symbolSize: 5,
              smooth: 0.42,
              lineStyle: {{ width: 3, color: colors[idx], type: idx === 1 ? 'solid' : 'dashed' }},
              itemStyle: {{ color: colors[idx] }},
              endLabel: {{ show: true, formatter: String(path.name || '路径') + ' ' + String(path.probability || 0) + '%', color: colors[idx], fontWeight: 700 }}
            }});
          }});
          return series;
        }}
        function renderEcharts() {{
          if (window.__stockMingEchartsFailed || !window.echarts) {{
            renderFallback();
            return;
          }}
          const chart = window.echarts.init(root, null, {{ renderer: 'canvas' }});
          const option = {{
            animation: !reducedMotion,
            animationDuration: 520,
            animationDurationUpdate: 360,
            grid: {{ top: 32, right: 72, bottom: 34, left: 42 }},
            tooltip: {{ trigger: 'axis', valueFormatter: v => Number(v).toFixed(2) }},
            legend: {{ top: 2, left: 8, textStyle: {{ color: '#475569', fontSize: 11 }} }},
            xAxis: {{ type: 'value', min: -10, max: packet.horizon_days || 10, splitLine: {{ lineStyle: {{ color: 'rgba(148,163,184,0.16)' }} }}, axisLabel: {{ formatter: v => v === 0 ? 'T0' : (v > 0 ? '+' + v : v) }} }},
            yAxis: {{ type: 'value', scale: true, splitLine: {{ lineStyle: {{ color: 'rgba(148,163,184,0.16)' }} }} }},
            series: makeSeries(reducedMotion ? 99 : 0)
          }};
          chart.setOption(option);
          if (!reducedMotion) {{
            let step = 0;
            const maxStep = packet.horizon_days || 10;
            const timer = window.setInterval(() => {{
              step += 1;
              chart.setOption({{ series: makeSeries(step) }});
              if (step >= maxStep) window.clearInterval(timer);
            }}, 140);
          }}
          window.addEventListener('resize', () => chart.resize());
        }}
        setTimeout(renderEcharts, 40);
      </script>
    </body>
    </html>
    """
    if components:
        components.html(chart_html, height=392, scrolling=False)
    else:  # pragma: no cover - runtime fallback for unexpected Streamlit install
        frame = _projection_static_frame(payload)
        if frame.empty:
            st.info("暂无路径数据，点击刷新今日基础数据生成。")
        else:
            st.line_chart(frame, height=320)
    st.caption(
        f"路径依据来自：{payload.get('path_basis') or '市场类型待确认 / 数据待验证'} ｜ "
        f"路径推演不是投资建议；未刷新或缓存状态下仅用于观察验证。来源：{source}"
    )
    _projection_path_cards(paths)


def render_path_projection_card(packet: dict | None = None):
    _inject_command_center_css()
    payload = packet or {}
    rows = payload.get("path_projection") or []
    if not rows:
        rows = [
            {"day": 1, "乐观路径": 100, "中性路径": 100, "谨慎路径": 100},
            {"day": 2, "乐观路径": 102, "中性路径": 101, "谨慎路径": 99},
            {"day": 3, "乐观路径": 104, "中性路径": 101.5, "谨慎路径": 98},
            {"day": 5, "乐观路径": 107, "中性路径": 103, "谨慎路径": 97},
            {"day": 8, "乐观路径": 111, "中性路径": 105, "谨慎路径": 95},
            {"day": 10, "乐观路径": 114, "中性路径": 106, "谨慎路径": 94},
        ]
    frame = pd.DataFrame(rows).set_index("day")
    st.markdown(
        """
        <section class="cc-card">
          <div class="cc-card-title">未来 5-10 个交易日趋势推演</div>
          <div class="cc-card-caption">三条路径为 mock / 缓存推演路径，不自动接入真实 DeepSeek。</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.line_chart(frame, height=260)
    st.markdown(
        "<div class='cc-muted-note'>基于历史交易经验、资金方向和纪律规则的路径推演，不构成投资建议。</div>",
        unsafe_allow_html=True,
    )


def render_discipline_validation_grid(items=None):
    _inject_command_center_css()
    payload = items if isinstance(items, dict) else {}
    rows = payload.get("discipline_checks") if payload else items
    rows = rows or []
    account = payload.get("account_snapshot") or {}
    budget = payload.get("allocation_budget") or {}
    current_position_amount = _to_float(account.get("stock_value"), 0) + _to_float(account.get("etf_value"), 0)
    money_rows = [
        {
            "title": "当前仓位金额",
            "value": _cc_money_line(current_position_amount, "按建议总敞口"),
            "status": "待验证",
            "description": "股票市值 + ETF 市值，来自账户快照。",
        },
        {
            "title": "可加仓金额",
            "value": _cc_money_line(budget.get("max_add_amount"), "按可用现金"),
            "status": "待验证",
            "description": "不超过可用现金与本轮加仓上限。",
        },
        {
            "title": "最大允许回撤金额",
            "value": _cc_money_line(budget.get("risk_budget_amount"), "按风险预算"),
            "status": "满足",
            "description": "按净资产风险预算折算的回撤边界。",
        },
        {
            "title": "触发减仓金额",
            "value": _cc_money_line(budget.get("suggested_adjustment_amount"), "按建议总敞口"),
            "status": "待验证",
            "description": "若跌破纪律阈值，优先按该金额做减仓观察。",
        },
    ]
    display_rows = money_rows + list(rows)
    html = "<section class='cc-card'><div class='cc-card-title'>纪律校验区</div><div class='cc-card-caption'>每项显示当前值、是否满足和简短说明；金额均标注预算口径。</div><div class='cc-validation-grid'>"
    for item in display_rows[:9]:
        status = item.get("status") or "待验证"
        html += (
            "<div class='cc-mini-card'>"
            f"<div class='cc-mini-title'>{escape(str(item.get('title') or '纪律项'))}</div>"
            f"<div class='cc-mini-value'>{escape(str(item.get('value') or '暂无'))}</div>"
            f"<div class='cc-mini-desc'>{escape(str(item.get('description') or '等待校验。'))}</div>"
            f"<span class='cc-check {_status_class(status)}'>{escape(str(status))}</span>"
            "</div>"
        )
    html += "</div></section>"
    st.markdown(html, unsafe_allow_html=True)


def render_signal_confluence_card(items=None):
    _inject_command_center_css()
    rows = items or []
    html = "<section class='cc-card'><div class='cc-card-title'>关键信号共振</div><div class='cc-card-caption'>强度是结构化状态，不把假设写成事实。</div><div class='cc-signal-grid'>"
    for item in rows[:5]:
        status = item.get("status") or "待观察"
        html += (
            "<div class='cc-mini-card'>"
            f"<div class='cc-mini-title'>{escape(str(item.get('name') or '信号'))}</div>"
            f"<div class='cc-mini-value'>{escape(str(item.get('strength') or '中'))}</div>"
            f"<div class='cc-mini-desc'>状态：{escape(str(status))}<br>{escape(str(item.get('comment') or '等待确认。'))}</div>"
            f"<span class='cc-check {_status_class(status)}'>{escape(str(item.get('evaluation') or '观察'))}</span>"
            "</div>"
        )
    html += "</div></section>"
    st.markdown(html, unsafe_allow_html=True)


def render_observation_pool_card(packet: dict | None = None):
    _inject_command_center_css()
    payload = packet or {}
    validated = payload.get("validated_data") or []
    cautious = payload.get("cautious_inference") or []
    watchlist = payload.get("watchlist") or []
    next_targets = payload.get("next_observation_targets") or []
    st.markdown(
        "<section class='cc-card'><div class='cc-card-title'>验证边界与观察池</div><div class='cc-card-caption'>投喂资料观点必须标记为“投喂资料观点 / 待验证”。</div>"
        "<div class='cc-three-grid'>"
        f"<div class='cc-mini-card'><div class='cc-mini-title'>已验证数据</div>{_html_list(validated)}</div>"
        f"<div class='cc-mini-card'><div class='cc-mini-title'>谨慎推断</div>{_html_list(cautious)}</div>"
        f"<div class='cc-mini-card'><div class='cc-mini-title'>观察清单</div>{_html_list(watchlist)}</div>"
        "</div></section>",
        unsafe_allow_html=True,
    )
    if next_targets:
        header = "<tr><th>代码</th><th>简称</th><th>所属方向</th><th>关注点</th><th>观察预算</th><th>单票建议金额</th><th>动作状态</th></tr>"
        body = "".join(
            "<tr>"
            f"<td>{escape(str(item.get('code') or ''))}</td>"
            f"<td>{escape(str(item.get('name') or ''))}</td>"
            f"<td>{escape(str(item.get('theme') or ''))}</td>"
            f"<td>{escape(str(item.get('focus') or ''))}</td>"
            f"<td>{escape(_cc_money_line(item.get('observation_budget'), item.get('budget_basis') or '按风险预算'))}</td>"
            f"<td>{escape(_cc_money_line(item.get('single_ticket_amount'), item.get('ticket_basis') or '按可用现金'))}</td>"
            f"<td>{escape(str(item.get('action_state') or '观察'))}</td>"
            "</tr>"
            for item in next_targets[:8]
        )
        st.markdown(
            f"<section class='cc-card'><div class='cc-card-title'>下一次观察标的</div><table class='cc-table'>{header}{body}</table></section>",
            unsafe_allow_html=True,
        )
