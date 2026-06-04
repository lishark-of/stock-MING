from __future__ import annotations

from copy import deepcopy
from typing import Any


REGISTRY_VERSION = "2026-06-command-center-packets-v1"

AREA_LABELS = {
    "home": "首页快照",
    "command_loop": "决策闭环",
    "analysis": "市场分析",
    "a_share_evidence": "A股证据",
    "legacy_workspace": "高级工具箱",
    "data_governance": "数据治理",
    "recovery": "恢复记录",
}

REFRESH_POLICY_LABELS = {
    "read_through_cache": "读取缓存",
    "manual_basic_or_auto_light": "手动基础刷新 / 轻量本地状态",
    "derived_display": "展示派生",
    "button_gated": "按钮触发",
    "manual_recovery": "手动恢复",
}

EXTERNAL_POLICY_LABELS = {
    "not_triggered": "不触发外部接口",
    "button_gated": "按钮触发外部接口",
}

DEEPSEEK_POLICY_LABELS = {
    "never": "不调用 DeepSeek",
    "manual_only": "仅手动 DeepSeek",
}


PACKET_SPECS = [
    {
        "packet_key": "command_center_home_snapshot",
        "label": "首页交易快照",
        "area": "home",
        "owner": "command_center_home_snapshot.py",
        "source": "session_state + local snapshot cache",
        "refresh_policy": "read_through_cache",
        "external_call_policy": "not_triggered",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "",
        "local_api_path": "/api/command-center/packets/command_center_home_snapshot",
        "description": "App 首页读取的最近一次可执行交易快照；打开页面不触发外部接口。",
    },
    {
        "packet_key": "command_center_live_packet",
        "label": "综合中心实时基础包",
        "area": "command_loop",
        "owner": "app.py / command_center_service.py",
        "source": "manual_basic refresh result or auto-light local state",
        "refresh_policy": "manual_basic_or_auto_light",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "",
        "local_api_path": "/api/command-center/packets/command_center_live_packet",
        "description": "综合推演中心主数据包；重型数据刷新必须由按钮触发。",
    },
    {
        "packet_key": "command_center_refresh_summary",
        "label": "刷新结果摘要",
        "area": "command_loop",
        "owner": "command_center_refresh_summary.py",
        "source": "refresh result display summary",
        "refresh_policy": "derived_display",
        "external_call_policy": "not_triggered",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "",
        "local_api_path": "/api/command-center/packets/command_center_refresh_summary",
        "description": "只整理刷新状态、错误、缓存和已完成模块，不执行刷新。",
    },
    {
        "packet_key": "strategy_execution_packet",
        "label": "策略执行实验室",
        "area": "command_loop",
        "owner": "strategy_execution_service.py / command_center_strategy_summary.py",
        "source": "button-gated strategy execution generation",
        "refresh_policy": "button_gated",
        "external_call_policy": "not_triggered",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "",
        "local_api_path": "/api/command-center/packets/strategy_execution_packet",
        "description": "策略执行建议和展示摘要；生成动作由按钮触发，不调用 DeepSeek。",
    },
    {
        "packet_key": "command_center_decision_packet",
        "label": "今日总决策",
        "area": "command_loop",
        "owner": "command_center_decision_engine.py / command_center_decision_summary.py",
        "source": "button-gated decision generation",
        "refresh_policy": "button_gated",
        "external_call_policy": "not_triggered",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "",
        "local_api_path": "/api/command-center/packets/command_center_decision_packet",
        "description": "今日总动作、风险等级和依据链；规则不由 registry 修改。",
    },
    {
        "packet_key": "command_center_projection_packet",
        "label": "5-10 日趋势推演",
        "area": "command_loop",
        "owner": "command_center_projection.py",
        "source": "existing packets and fallback path model",
        "refresh_policy": "derived_display",
        "external_call_policy": "not_triggered",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "",
        "local_api_path": "/api/command-center/packets/command_center_projection_packet",
        "description": "未来路径图展示包；不拉行情、不调用外部接口。",
    },
    {
        "packet_key": "command_center_analysis_method_packet",
        "label": "市场分析方法",
        "area": "analysis",
        "owner": "command_center_analysis_methods.py",
        "source": "market profile + existing packets",
        "refresh_policy": "derived_display",
        "external_call_policy": "not_triggered",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "",
        "local_api_path": "/api/command-center/packets/command_center_analysis_method_packet",
        "description": "A股/美股/ETF 分析方法适配结果；只基于已有结构化包。",
    },
    {
        "packet_key": "command_center_evidence_radar_packet",
        "label": "A股证据雷达",
        "area": "a_share_evidence",
        "owner": "command_center_evidence_summary.py",
        "source": "legacy A-share evidence packets",
        "refresh_policy": "derived_display",
        "external_call_policy": "not_triggered",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "综合推演中心 / A股证据",
        "local_api_path": "/api/command-center/packets/command_center_evidence_radar_packet",
        "description": "把资金流、龙虎榜、融资、涨跌停、筹码、硬风险汇成首页证据状态。",
    },
    {
        "packet_key": "command_center_market_packet",
        "label": "市场风格证据",
        "area": "legacy_workspace",
        "owner": "command_center_market_packet.py",
        "source": "legacy market style state",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 今日关注池",
        "local_api_path": "/api/command-center/packets/command_center_market_packet",
        "description": "旧版今日关注池回流的市场风格证据。",
    },
    {
        "packet_key": "command_center_radar_packet",
        "label": "下一票雷达",
        "area": "legacy_workspace",
        "owner": "command_center_radar_packet.py",
        "source": "legacy radar scan state",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "manual_only",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 下一票雷达",
        "local_api_path": "/api/command-center/packets/command_center_radar_packet",
        "description": "候选池与下一票证据；扫描和 Top 候选 DeepSeek 必须手动触发。",
    },
    {
        "packet_key": "command_center_etf_packet",
        "label": "ETF / 融资动作",
        "area": "legacy_workspace",
        "owner": "command_center_etf_packet.py",
        "source": "legacy ETF allocation state",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "manual_only",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 融资 ETF",
        "local_api_path": "/api/command-center/packets/command_center_etf_packet",
        "description": "ETF 配置与融资动作证据；ETF 刷新和调研必须手动触发。",
    },
    {
        "packet_key": "command_center_margin_packet",
        "label": "融资融券证据",
        "area": "a_share_evidence",
        "owner": "command_center_margin_packet.py",
        "source": "Tushare margin_detail packet cache",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 融资 ETF / 融资融券",
        "local_api_path": "/api/command-center/packets/command_center_margin_packet",
        "description": "A股融资融券证据；权限不足时展示缺口，不自动重试。",
    },
    {
        "packet_key": "command_center_discipline_packet",
        "label": "纪律 / 回测证据",
        "area": "legacy_workspace",
        "owner": "command_center_discipline_packet.py",
        "source": "legacy discipline and backtest state",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 交易纪律实验室",
        "local_api_path": "/api/command-center/packets/command_center_discipline_packet",
        "description": "纪律校验和回测摘要；回测必须按钮触发。",
    },
    {
        "packet_key": "command_center_quant_packet",
        "label": "量化推演证据",
        "area": "legacy_workspace",
        "owner": "command_center_quant_packet.py",
        "source": "legacy quant projection state",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 量化推演",
        "local_api_path": "/api/command-center/packets/command_center_quant_packet",
        "description": "量化推演摘要；完整底座和回测不得打开页面自动跑。",
    },
    {
        "packet_key": "command_center_facts_packet",
        "label": "A股事实包",
        "area": "a_share_evidence",
        "owner": "command_center_facts_packet.py",
        "source": "A-share professional facts cache",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / A股专业实盘",
        "local_api_path": "/api/command-center/packets/command_center_facts_packet",
        "description": "A股专业事实集合，承接旧版工具的回流证据。",
    },
    {
        "packet_key": "command_center_moneyflow_packet",
        "label": "个股资金流",
        "area": "a_share_evidence",
        "owner": "command_center_moneyflow_packet.py",
        "source": "Tushare moneyflow packet cache",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / A股专业实盘 / 个股资金流",
        "local_api_path": "/api/command-center/packets/command_center_moneyflow_packet",
        "description": "A股个股资金流证据；缺数据时显示待验证。",
    },
    {
        "packet_key": "command_center_dragon_tiger_packet",
        "label": "龙虎榜证据",
        "area": "a_share_evidence",
        "owner": "command_center_dragon_tiger_packet.py",
        "source": "Tushare top_list/top_inst packet cache",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 下一票雷达 / 龙虎榜",
        "local_api_path": "/api/command-center/packets/command_center_dragon_tiger_packet",
        "description": "A股龙虎榜和机构席位证据；权限或无记录时不伪造成通过。",
    },
    {
        "packet_key": "command_center_limit_emotion_packet",
        "label": "涨跌停 / 情绪证据",
        "area": "a_share_evidence",
        "owner": "command_center_limit_emotion_packet.py",
        "source": "Tushare limit list packet cache",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 数据源体检 / 涨跌停情绪",
        "local_api_path": "/api/command-center/packets/command_center_limit_emotion_packet",
        "description": "A股涨跌停和情绪边界；权限不足时保留缺口说明。",
    },
    {
        "packet_key": "command_center_chip_packet",
        "label": "筹码 / 胜率证据",
        "area": "a_share_evidence",
        "owner": "command_center_chip_packet.py",
        "source": "Tushare cyq packet cache",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 量化推演 / 筹码胜率",
        "local_api_path": "/api/command-center/packets/command_center_chip_packet",
        "description": "A股筹码分布和胜率证据；缺失时显示待刷新。",
    },
    {
        "packet_key": "command_center_hard_risk_packet",
        "label": "公告 / 硬风险证据",
        "area": "a_share_evidence",
        "owner": "command_center_hard_risk_packet.py",
        "source": "A-share announcement risk packet cache",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 天眼风控",
        "local_api_path": "/api/command-center/packets/command_center_hard_risk_packet",
        "description": "公告、减持、质押等硬风险证据；检测必须手动触发。",
    },
    {
        "packet_key": "command_center_data_capability_packet",
        "label": "数据能力状态",
        "area": "data_governance",
        "owner": "command_center_data_capability_console.py",
        "source": "manual data capability checks",
        "refresh_policy": "button_gated",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 数据源体检",
        "local_api_path": "/api/command-center/packets/command_center_data_capability_packet",
        "description": "Tushare/AkShare/yfinance/Supabase 能力状态；体检必须手动触发。",
    },
    {
        "packet_key": "a_share_professional_data_capability",
        "label": "A股专业数据能力",
        "area": "data_governance",
        "owner": "market_data_capability.py",
        "source": "manual A-share capability check",
        "refresh_policy": "button_gated",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / A股专业实盘",
        "local_api_path": "/api/command-center/packets/a_share_professional_data_capability",
        "description": "A股专业接口权限、可用性和缺口状态。",
    },
    {
        "packet_key": "command_center_last_a_share_diagnostic_recovery_result",
        "label": "最近一次A股手动恢复结果",
        "area": "recovery",
        "owner": "app.py / command_center_home_snapshot.py",
        "source": "manual recovery action result",
        "refresh_policy": "manual_recovery",
        "external_call_policy": "button_gated",
        "deepseek_policy": "never",
        "writes_session_state": True,
        "legacy_workspace_entry": "综合中心 / 数据缺口恢复",
        "local_api_path": "/api/command-center/packets/command_center_last_a_share_diagnostic_recovery_result",
        "description": "最近一次手动恢复 A股证据的结果，用于首页说明修复是否生效。",
    },
    {
        "packet_key": "latest_recovery_result_notice",
        "label": "最近恢复结果提示",
        "area": "recovery",
        "owner": "command_center_home_snapshot.py",
        "source": "home snapshot derived notice",
        "refresh_policy": "derived_display",
        "external_call_policy": "not_triggered",
        "deepseek_policy": "never",
        "writes_session_state": False,
        "legacy_workspace_entry": "",
        "local_api_path": "/api/command-center/packets/latest_recovery_result_notice",
        "description": "从首页快照派生的恢复结果提示，不单独触发数据请求。",
    },
    {
        "packet_key": "legacy_margin_etf_allocation_result",
        "label": "旧版融资ETF配置结果",
        "area": "legacy_workspace",
        "owner": "margin_etf_allocator.py",
        "source": "legacy margin ETF allocator state",
        "refresh_policy": "button_gated",
        "external_call_policy": "button_gated",
        "deepseek_policy": "manual_only",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 融资 ETF",
        "local_api_path": "/api/command-center/packets/legacy_margin_etf_allocation_result",
        "description": "旧版 ETF 配置结果，后续应继续回流到 command_center_etf_packet。",
    },
    {
        "packet_key": "radar_scan_results",
        "label": "旧版下一票扫描结果",
        "area": "legacy_workspace",
        "owner": "next_stock_radar.py",
        "source": "legacy radar scan state",
        "refresh_policy": "button_gated",
        "external_call_policy": "button_gated",
        "deepseek_policy": "manual_only",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 下一票雷达",
        "local_api_path": "/api/command-center/packets/radar_scan_results",
        "description": "旧版候选池扫描结果，后续应继续回流到 command_center_radar_packet。",
    },
    {
        "packet_key": "radar_scan_summary",
        "label": "旧版下一票扫描摘要",
        "area": "legacy_workspace",
        "owner": "next_stock_radar.py",
        "source": "legacy radar scan state",
        "refresh_policy": "button_gated",
        "external_call_policy": "button_gated",
        "deepseek_policy": "manual_only",
        "writes_session_state": True,
        "legacy_workspace_entry": "高级工具箱 / 下一票雷达",
        "local_api_path": "/api/command-center/packets/radar_scan_summary",
        "description": "旧版扫描摘要，供首页 Top3 和雷达状态复用。",
    },
]


def _copy(value: Any) -> Any:
    return deepcopy(value)


def build_command_center_packet_registry() -> dict:
    packets = [_copy(spec) for spec in PACKET_SPECS]
    return {
        "version": REGISTRY_VERSION,
        "title": "stock-MING command center packet registry",
        "description": "Pure local registry for command-center packets, local API planning, and legacy migration boundaries.",
        "packets": packets,
        "areas": sorted({spec["area"] for spec in packets}),
        "safe_mode": {
            "deepseek": "manual_only",
            "external_calls": "button_gated",
            "opens_page_without_refresh": True,
        },
    }


def list_command_center_packets(
    area: str | None = None,
    include_legacy: bool = True,
    refresh_policy: str | None = None,
) -> list[dict]:
    area_text = (area or "").strip()
    refresh_text = (refresh_policy or "").strip()
    result = []
    for spec in PACKET_SPECS:
        if area_text and spec["area"] != area_text:
            continue
        if refresh_text and spec["refresh_policy"] != refresh_text:
            continue
        if not include_legacy and spec["area"] in {"legacy_workspace", "a_share_evidence", "recovery"}:
            continue
        result.append(_copy(spec))
    return result


def get_command_center_packet_spec(packet_key: Any) -> dict:
    key = str(packet_key or "").strip()
    if not key:
        return {}
    for spec in PACKET_SPECS:
        if spec["packet_key"] == key:
            return _copy(spec)
    return {}


def build_local_api_packet_map() -> dict:
    return {
        spec["packet_key"]: {
            "path": spec["local_api_path"],
            "label": spec["label"],
            "area": spec["area"],
            "owner": spec["owner"],
            "refresh_policy": spec["refresh_policy"],
            "external_call_policy": spec["external_call_policy"],
            "deepseek_policy": spec["deepseek_policy"],
        }
        for spec in PACKET_SPECS
    }


def packet_registry_summary() -> dict:
    packets = list_command_center_packets()
    by_area: dict[str, int] = {}
    by_refresh_policy: dict[str, int] = {}
    manual_or_button_gated = 0
    for spec in packets:
        by_area[spec["area"]] = by_area.get(spec["area"], 0) + 1
        by_refresh_policy[spec["refresh_policy"]] = by_refresh_policy.get(spec["refresh_policy"], 0) + 1
        if spec["external_call_policy"] == "button_gated" or spec["refresh_policy"] in {"button_gated", "manual_recovery"}:
            manual_or_button_gated += 1
    return {
        "version": REGISTRY_VERSION,
        "packet_count": len(packets),
        "area_counts": by_area,
        "refresh_policy_counts": by_refresh_policy,
        "manual_or_button_gated_count": manual_or_button_gated,
        "deepseek_auto_count": sum(1 for spec in packets if spec["deepseek_policy"] == "auto"),
        "external_auto_count": sum(1 for spec in packets if spec["external_call_policy"] == "auto"),
    }


def _tone_for_policy(spec: dict) -> str:
    if spec.get("external_call_policy") == "button_gated" or spec.get("refresh_policy") in {"button_gated", "manual_recovery"}:
        return "manual"
    if spec.get("refresh_policy") in {"derived_display", "read_through_cache"}:
        return "safe"
    return "neutral"


def build_packet_registry_view_model(max_packets: int = 10) -> dict:
    packets = list_command_center_packets()
    summary = packet_registry_summary()
    area_items = [
        {
            "area": area,
            "label": AREA_LABELS.get(area, area),
            "count": count,
        }
        for area, count in sorted(summary["area_counts"].items())
    ]
    packet_items = []
    for spec in packets[: max(1, int(max_packets or 10))]:
        packet_items.append(
            {
                "packet_key": spec["packet_key"],
                "label": spec["label"],
                "area": spec["area"],
                "area_label": AREA_LABELS.get(spec["area"], spec["area"]),
                "owner": spec["owner"],
                "refresh_policy": spec["refresh_policy"],
                "refresh_policy_label": REFRESH_POLICY_LABELS.get(spec["refresh_policy"], spec["refresh_policy"]),
                "external_call_policy": spec["external_call_policy"],
                "external_call_label": EXTERNAL_POLICY_LABELS.get(spec["external_call_policy"], spec["external_call_policy"]),
                "deepseek_policy": spec["deepseek_policy"],
                "deepseek_label": DEEPSEEK_POLICY_LABELS.get(spec["deepseek_policy"], spec["deepseek_policy"]),
                "local_api_path": spec["local_api_path"],
                "tone": _tone_for_policy(spec),
            }
        )
    local_api_map = build_local_api_packet_map()
    return {
        "version": REGISTRY_VERSION,
        "title": "综合中心能力地图",
        "subtitle": "Packet Registry / Local API Readiness",
        "summary": "把首页、决策闭环、旧版工具回流和数据治理统一成 packet 清单；这里只读展示，不触发刷新。",
        "packet_count": summary["packet_count"],
        "area_items": area_items,
        "packet_items": packet_items,
        "manual_or_button_gated_count": summary["manual_or_button_gated_count"],
        "local_api_endpoint_count": len(local_api_map),
        "deepseek_auto_count": summary["deepseek_auto_count"],
        "external_auto_count": summary["external_auto_count"],
        "safe_mode_items": [
            {
                "label": "DeepSeek",
                "value": "0 个自动调用" if summary["deepseek_auto_count"] == 0 else f"{summary['deepseek_auto_count']} 个自动调用",
                "tone": "safe" if summary["deepseek_auto_count"] == 0 else "danger",
            },
            {
                "label": "外部接口",
                "value": "0 个自动触发" if summary["external_auto_count"] == 0 else f"{summary['external_auto_count']} 个自动触发",
                "tone": "safe" if summary["external_auto_count"] == 0 else "danger",
            },
            {
                "label": "重型能力",
                "value": f"{summary['manual_or_button_gated_count']} 个按钮/手动门控",
                "tone": "manual",
            },
            {
                "label": "Local API",
                "value": f"{len(local_api_map)} 个规划端点",
                "tone": "neutral",
            },
        ],
        "local_api_hint": "未来 local API / Tauri / React 可直接按这些 path 暴露 packet，不需要把旧页面搬过去。",
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }
