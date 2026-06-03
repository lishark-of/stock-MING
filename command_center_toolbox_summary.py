from __future__ import annotations

from collections.abc import Iterable
from typing import Any


ADVANCED_TOOLBOX_ITEMS = [
    {
        "key": "today_pool",
        "label": "今日关注池",
        "purpose": "查看市场风格、投喂反馈和旧版投研驾驶舱。",
        "packet": "legacy_market_style_fact_packet / command_center_market_packet",
        "gate": "刷新市场风格数据按钮",
    },
    {
        "key": "tianyan_risk",
        "label": "天眼风控",
        "purpose": "排查公告、减持、质押、解禁等硬风险线索。",
        "packet": "tianyan_risk_fact_packet / command_center_hard_risk_packet",
        "gate": "手动运行风险扫描按钮",
    },
    {
        "key": "discipline_lab",
        "label": "交易纪律实验室",
        "purpose": "查看纪律规则、回测缓存和策略边界。",
        "packet": "last_backtest_report / command_center_discipline_packet",
        "gate": "运行纪律校验 / 回测按钮",
    },
    {
        "key": "quant_projection",
        "label": "量化推演",
        "purpose": "运行旧版完整量化底座和 A股专业事实整理。",
        "packet": "legacy_quant_result / command_center_quant_packet",
        "gate": "生成量化推演按钮",
    },
    {
        "key": "margin_etf",
        "label": "融资 ETF",
        "purpose": "刷新 ETF 日线、融资配置和赛道候选。",
        "packet": "legacy_margin_etf_allocation_result / command_center_etf_packet",
        "gate": "刷新 ETF 配置按钮",
    },
    {
        "key": "data_healthcheck",
        "label": "数据源体检",
        "purpose": "手动检查 Tushare / AkShare / yfinance / Supabase 数据能力。",
        "packet": "last_data_source_healthcheck / data_capability_console",
        "gate": "运行数据源体检按钮",
    },
    {
        "key": "next_ticket_radar",
        "label": "下一票雷达",
        "purpose": "运行候选池扫描和触发条件排查。",
        "packet": "radar_scan_results / command_center_radar_packet",
        "gate": "运行下一票雷达按钮",
    },
    {
        "key": "cloud_brain",
        "label": "云端外脑",
        "purpose": "查看 Supabase 记忆和云端资料缓存。",
        "packet": "legacy_cloud_memories / Supabase capability",
        "gate": "手动读取云端外脑按钮",
    },
]


def _filter_items(items: Iterable[dict[str, Any]], keys: Iterable[str] | None = None) -> list[dict]:
    allowed = {str(key) for key in keys or []}
    result = []
    for item in items:
        payload = dict(item)
        if allowed and payload.get("key") not in allowed and payload.get("label") not in allowed:
            continue
        payload["status"] = "高级工具"
        payload["trigger_policy"] = "button_gated"
        payload["deepseek_policy"] = "manual_only"
        result.append(payload)
    return result


def build_advanced_toolbox_entry(keys: Iterable[str] | None = None) -> dict:
    items = _filter_items(ADVANCED_TOOLBOX_ITEMS, keys=keys)
    return {
        "status": "ready",
        "title": "高级工具箱",
        "summary": "旧版工作台保留为排查和深度工具；综合推演中心仍是默认主入口。",
        "items": items,
        "manual_note": "进入高级工具箱不会自动触发 DeepSeek、回测、全市场扫描或重型数据接口；具体模块仍由按钮手动触发。",
        "next_step": "旧版工具的结果会逐步写入统一 packet，再回到 Home Action Snapshot 和数据能力控制台。",
        "deepseek_called": False,
    }
